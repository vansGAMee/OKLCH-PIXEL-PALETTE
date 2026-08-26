from __future__ import annotations

from pathlib import Path

import torch
import numpy as np
import onnxruntime as ort

from ml.palettebrain.model import (
    PaletteDecoder,
    PaletteDecoderConfig,
    load_inherited_state,
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
