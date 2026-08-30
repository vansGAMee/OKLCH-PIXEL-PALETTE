from __future__ import annotations

from pathlib import Path

import torch
import numpy as np
import onnxruntime as ort
import pytest

from ml.palettebrain.model import (
    PaletteDecoder,
    PaletteDecoderConfig,
    load_inherited_state,
)
from ml.palettebrain.train_candidate11 import (
    configure_stage_parameters,
    stage_b_mixture_weights,
)


PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _inputs() -> tuple[torch.Tensor, ...]:
    return (
        torch.nn.functional.normalize(torch.randn(2, 384), dim=-1),
        torch.tensor([[1] * 5 + [0] * 4, [1] * 9], dtype=torch.float32),
        torch.randn(2, 9, 4),
        torch.zeros(2, 9),
        torch.zeros(2, 9, 4),
    )


def test_repaired_visual_conditioning_is_slot_specific_and_onnx_friendly() -> None:
    torch.manual_seed(11)
    model = PaletteDecoder(
        PaletteDecoderConfig(visual_conditioning="slot_cross_attention")
    ).eval()
    inputs = _inputs()
    output = model(*inputs)
    attention = model.visual_attention_weights(inputs[0])

    assert output.shape == (2, 9, 5)
    assert attention is not None
    assert attention.shape == (2, 9, 4)
    assert torch.allclose(attention.sum(dim=-1), torch.ones(2, 9), atol=1e-6)
    assert not torch.allclose(attention[:, 0], attention[:, 1])
    assert torch.count_nonzero(output[0, 5:]) == 0


def test_legacy_checkpoint_remains_loadable_without_mutation() -> None:
    path = PACKAGE_DIR / "checkpoints" / "candidate-11-best.pt"
    if not path.is_file():
        return
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    model = PaletteDecoder(PaletteDecoderConfig(**checkpoint["model_config"]))
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    assert model.visual_cross_attention is None


def test_stage_a_freezes_inherited_and_stage_b_unfreezes_it() -> None:
    checkpoint = torch.load(
        PACKAGE_DIR / "checkpoints" / "candidate-11-best.pt",
        map_location="cpu",
        weights_only=True,
    )
    model = PaletteDecoder(PaletteDecoderConfig(**checkpoint["model_config"]))
    stage_a = configure_stage_parameters(model, "a")
    assert stage_a["trainable"]
    assert stage_a["frozen"]
    assert all(name.startswith(("bridge.", "visual_cross_attention.")) for name in stage_a["trainable"])
    stage_b = configure_stage_parameters(model, "b")
    assert stage_b["trainable"]
    assert not stage_b["frozen"]


def test_stage_a_optimizer_treats_only_visual_cross_attention_as_new() -> None:
    from ml.palettebrain.train_candidate11 import partition_trainable_parameters

    model = PaletteDecoder(
        PaletteDecoderConfig(visual_conditioning="slot_cross_attention")
    )
    configure_stage_parameters(model, "a")
    groups = partition_trainable_parameters(model)

    assert groups["new_names"]
    assert all(name.startswith("visual_cross_attention.") for name in groups["new_names"])
    assert groups["inherited_names"]
    assert all(name.startswith("bridge.") for name in groups["inherited_names"])


def test_stage_a_stability_loss_detects_joint_decoder_drift() -> None:
    from ml.palettebrain.train_candidate11 import stage_a_semantic_stability_loss

    torch.manual_seed(11)
    teacher = PaletteDecoder(PaletteDecoderConfig()).eval()
    student = PaletteDecoder(
        PaletteDecoderConfig(visual_conditioning="slot_cross_attention")
    ).eval()
    student.load_state_dict(teacher.state_dict(), strict=False)
    inputs = _inputs()

    initial = stage_a_semantic_stability_loss(student, teacher, inputs)
    with torch.no_grad():
        student.bridge.prior_proj.weight.normal_(mean=0.0, std=0.2)
        student.visual_cross_attention.output.weight.normal_(mean=0.0, std=0.2)
    drifted = stage_a_semantic_stability_loss(student, teacher, inputs)

    assert float(initial.detach()) < 1e-3
    assert float(drifted.detach()) > float(initial.detach()) + 1e-3


def test_stage_a_prior_stability_detects_semantic_histogram_drift() -> None:
    from ml.palettebrain.train_candidate11 import stage_a_prior_stability_loss

    torch.manual_seed(11)
    teacher = PaletteDecoder(PaletteDecoderConfig()).eval()
    student = PaletteDecoder(
        PaletteDecoderConfig(visual_conditioning="slot_cross_attention")
    ).eval()
    student.load_state_dict(teacher.state_dict(), strict=False)
    text_embedding = _inputs()[0]

    initial = stage_a_prior_stability_loss(student, teacher, text_embedding)
    with torch.no_grad():
        student.bridge.color_prior_head.weight.normal_(mean=0.0, std=0.2)
    drifted = stage_a_prior_stability_loss(student, teacher, text_embedding)

    assert float(initial.detach()) < 1e-7
    assert float(drifted.detach()) > 1e-3


def test_stage_a_concept_weights_equalize_sampling_mass() -> None:
    from ml.palettebrain.train_candidate11 import inverse_frequency_sample_weights

    labels = np.asarray(["frequent"] * 8 + ["rare"] * 2 + ["singleton"])
    weights = inverse_frequency_sample_weights(labels)

    assert float(weights[labels == "frequent"].sum()) == pytest.approx(1.0)
    assert float(weights[labels == "rare"].sum()) == pytest.approx(1.0)
    assert float(weights[labels == "singleton"].sum()) == pytest.approx(1.0)


def test_stage_b_mixture_is_explicit_eighty_twenty() -> None:
    weights, mixture = stage_b_mixture_weights([80, 20])
    assert mixture == {"realVisualSemantic": 0.8, "replayTotal": 0.2}
    assert float(weights[:80].sum()) == pytest.approx(0.8)
    assert float(weights[80:].sum()) == pytest.approx(0.2)


def test_stage_b_loss_distills_selected_stage_a_semantics() -> None:
    from ml.palettebrain.train_candidate11 import _stage_b_loss

    torch.manual_seed(11)
    config = PaletteDecoderConfig(visual_conditioning="slot_cross_attention")
    teacher = PaletteDecoder(config).eval()
    student = PaletteDecoder(config)
    student.load_state_dict(teacher.state_dict(), strict=True)
    inputs = _inputs()
    with torch.no_grad():
        target = teacher(*inputs)
        student.output_head.weight.add_(0.05)
        student.bridge.color_prior_head.weight.normal_(mean=0.0, std=0.2)
    batch = {
        "text_embedding": inputs[0],
        "count_mask": inputs[1],
        "seed_noise": inputs[2],
        "locked_mask": inputs[3],
        "locked_colors": inputs[4],
        "target": target,
        "color_prior": torch.softmax(torch.randn(2, 390), dim=-1),
        "teacher_latent": torch.randn(2, 128),
        "visual_weight": torch.ones(2),
    }

    _, components = _stage_b_loss(student, batch, teacher=teacher)

    assert float(components["semanticStability"].detach()) > 0
    assert float(components["priorStability"].detach()) > 0


def test_candidate8_inheritance_keeps_every_compatible_decoder_block() -> None:
    path = PACKAGE_DIR / "checkpoints" / "candidate-8-best.pt"
    if not path.is_file():
        return
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    model = PaletteDecoder(
        PaletteDecoderConfig(visual_conditioning="slot_cross_attention")
    )
    before = model.output_head.weight.detach().clone()
    missing, unexpected = load_inherited_state(model, checkpoint["model_state_dict"])
    assert not torch.equal(before, model.output_head.weight)
    assert "visual_adapter.proj_to_model.weight" in unexpected
    assert all(
        name.startswith(("bridge.", "visual_cross_attention.")) for name in missing
    )


def test_repaired_residual_starts_close_to_legacy_c11_behavior() -> None:
    path = PACKAGE_DIR / "checkpoints" / "candidate-11-best.pt"
    if not path.is_file():
        return
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    legacy = PaletteDecoder(PaletteDecoderConfig(**checkpoint["model_config"])).eval()
    legacy.load_state_dict(checkpoint["model_state_dict"], strict=True)
    repaired_config = dict(checkpoint["model_config"])
    repaired_config["visual_conditioning"] = "slot_cross_attention"
    torch.manual_seed(11)
    repaired = PaletteDecoder(PaletteDecoderConfig(**repaired_config)).eval()
    repaired.load_state_dict(checkpoint["model_state_dict"], strict=False)
    inputs = _inputs()
    with torch.no_grad():
        maximum_delta = torch.max(torch.abs(legacy(*inputs) - repaired(*inputs))).item()
    assert maximum_delta < 0.01


def test_repaired_cross_attention_exports_with_ort_parity(tmp_path: Path) -> None:
    torch.manual_seed(11)
    model = PaletteDecoder(PaletteDecoderConfig(
        visual_conditioning="slot_cross_attention",
        auxiliary_conditioning_scale=0.35,
    )).eval()
    inputs = tuple(value[:1] for value in _inputs())
    output_path = tmp_path / "repaired-c11.onnx"
    names = ["text_embedding", "count_mask", "seed_noise", "locked_mask", "locked_colors"]
    torch.onnx.export(
        model, inputs, str(output_path), input_names=names, output_names=["palette"],
        opset_version=17, dynamo=False,
    )
    with torch.no_grad():
        expected = model(*inputs).numpy()
    session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    actual = session.run(["palette"], {
        name: value.numpy() for name, value in zip(names, inputs, strict=True)
    })[0]
    assert np.max(np.abs(expected - actual)) < 1e-4
