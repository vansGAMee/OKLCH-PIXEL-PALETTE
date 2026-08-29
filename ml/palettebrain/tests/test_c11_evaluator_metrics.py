from __future__ import annotations

import numpy as np
import torch
import json

from ml.palettebrain import evaluate_semantic_v3
from ml.palettebrain.evaluate_semantic_v3 import (
    adversarial_semantics_pass,
    clean_multicolor_rate,
    composition_semantics_pass,
    cross_prompt_collapse_metric,
)


def _palette(hue_degrees: float, *, lightness: float = 0.55) -> np.ndarray:
    hue = np.radians(hue_degrees)
    colors = []
    for chroma in (0.05, 0.10, 0.15, 0.20, 0.25):
        colors.append([lightness, chroma * np.cos(hue), chroma * np.sin(hue)])
    return np.asarray(colors, dtype=np.float32)


def test_clean_multicolor_is_not_inverse_near_duplicate_proxy() -> None:
    palette = np.asarray([
        [0.50, 0.00, 0.00],
        [0.53, 0.00, 0.00],
        [0.70, 0.10, 0.00],
    ], dtype=np.float32)
    # Minimum distance 0.03 is not a near duplicate at the separate 0.025
    # diagnostic threshold, but it fails the stricter cleanliness behavior.
    assert clean_multicolor_rate([palette]) == 0.0


def test_adversarial_gate_requires_modifier_semantics_not_only_change() -> None:
    green_base = _palette(135)
    unrelated_blue = _palette(250)
    red_modifier = _palette(10)
    assert not adversarial_semantics_pass("red grass", unrelated_blue, green_base)
    assert adversarial_semantics_pass("red grass", red_modifier, green_base)


def test_composition_gate_requires_expected_lighting_relation() -> None:
    cold = _palette(240)
    warm = _palette(55)
    pair = ["hospital at sunset", "hospital under moonlight"]
    assert composition_semantics_pass(pair, warm, cold)
    assert not composition_semantics_pass(pair, cold, warm)


def test_cross_prompt_collapse_rejects_constant_and_accepts_diverse_palettes() -> None:
    diverse = [_palette(hue) for hue in (10, 70, 140, 220, 290)]
    rate, passed = cross_prompt_collapse_metric(diverse)
    assert passed and rate == 0.0
    constant = [_palette(40) for _ in range(8)]
    rate, passed = cross_prompt_collapse_metric(constant)
    assert not passed and rate == 1.0


class _CountingDecoder(torch.nn.Module):
    def __init__(self, device: torch.device = torch.device("cpu")) -> None:
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros((), device=device))
        self.calls = 0

    def forward(self, text, count_mask, seed_noise, locked_mask, locked_colors):
        self.calls += 1
        assert text.device == self.anchor.device
        output = torch.zeros((len(text), 9, 5), device=text.device)
        output[..., 0] = 0.5
        output[..., 3] = count_mask
        return output


def _structure_archive(path, rows: int = 12) -> None:
    count_mask = np.zeros((rows, 9), dtype=np.float32)
    count_mask[:, :3] = 1.0
    target = np.zeros((rows, 9, 5), dtype=np.float32)
    target[:, :3, 0] = np.linspace(0.3, 0.7, rows)[:, None]
    target[:, :3, 3] = 1.0
    np.savez(
        path,
        text_embedding=np.zeros((rows, 384), dtype=np.float32),
        count_mask=count_mask,
        seed_noise=np.zeros((rows, 9, 4), dtype=np.float32),
        locked_mask=np.zeros((rows, 9), dtype=np.float32),
        locked_colors=np.zeros((rows, 9, 4), dtype=np.float32),
        target=target,
        split=np.asarray(["val"] * rows),
        source_group_id=np.asarray([f"group-{index}" for index in range(rows)]),
    )


def test_palette_structure_batches_decoder_calls(tmp_path) -> None:
    archive = tmp_path / "structure.npz"
    _structure_archive(archive)
    model = _CountingDecoder()

    rate, rows = evaluate_semantic_v3.palette_structure_metric(model, str(archive), "val")

    assert rate is not None
    assert len(rows) == 12
    assert model.calls <= 2


def test_palette_structure_static_metadata_is_content_addressed_and_reused(tmp_path) -> None:
    archive = tmp_path / "structure-cache.npz"
    _structure_archive(archive)
    loader = getattr(evaluate_semantic_v3, "load_palette_structure_context", None)
    clear = getattr(evaluate_semantic_v3, "clear_static_evaluation_context_cache", None)
    assert callable(loader) and callable(clear)
    clear()
    first = loader(archive, "val")
    second = loader(archive, "val")
    assert first is second
    _structure_archive(archive, rows=13)
    third = loader(archive, "val")
    assert third is not first


def test_main_prompt_decoder_has_a_batched_device_safe_entry_point() -> None:
    decode_embeddings = getattr(evaluate_semantic_v3, "decode_embeddings", None)
    assert callable(decode_embeddings)
    model = _CountingDecoder()
    embeddings = np.zeros((130, 384), dtype=np.float32)
    raw = decode_embeddings(model, embeddings, count=5, seed=42, batch_size=64)
    assert raw.shape == (130, 9, 5)
    assert model.calls == 3


def test_palette_structure_uses_cuda_inputs_when_decoder_is_on_cuda(tmp_path) -> None:
    if not torch.cuda.is_available():
        return
    archive = tmp_path / "structure-cuda.npz"
    _structure_archive(archive, rows=6)
    model = _CountingDecoder(torch.device("cuda"))
    evaluate_semantic_v3.palette_structure_metric(model, str(archive), "val")
    assert model.calls == 1


def test_auto_evaluation_device_selects_cuda_when_available() -> None:
    helper = getattr(evaluate_semantic_v3, "resolve_evaluation_device", None)
    assert callable(helper)
    expected = "cuda" if torch.cuda.is_available() else "cpu"
    assert helper("auto").type == expected


def test_static_evaluation_context_is_content_addressed_and_reused(
    tmp_path, monkeypatch,
) -> None:
    load_context = getattr(evaluate_semantic_v3, "load_static_evaluation_context", None)
    clear_context = getattr(evaluate_semantic_v3, "clear_static_evaluation_context_cache", None)
    assert callable(load_context) and callable(clear_context)
    v2 = tmp_path / "v2.json"
    v3 = tmp_path / "v3.json"
    v2.write_text(json.dumps({"concepts": {"red": {"prompts": ["red"]}}}), encoding="utf-8")
    v3_payload = {
        "buckets": {"explicit_color_controls": ["red"]},
        "bilingualPairs": [], "abstract": [], "longText": [],
        "compositionContrasts": [], "oodParaphraseGroups": [],
        "adversarialComposition": [],
    }
    v3.write_text(json.dumps(v3_payload), encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        evaluate_semantic_v3,
        "load_encoder",
        lambda **kwargs: calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        evaluate_semantic_v3,
        "embed_texts",
        lambda prompts, **_kwargs: np.zeros((len(prompts), 384), dtype=np.float32),
    )
    monkeypatch.setattr(evaluate_semantic_v3, "_family_references", lambda _path: ({}, {}))
    clear_context()
    first = load_context(v2, v3, cache_dir="cache", device=torch.device("cpu"))
    second = load_context(v2, v3, cache_dir="cache", device=torch.device("cpu"))
    assert first is second
    assert len(calls) == 1
    v3_payload["buckets"]["explicit_color_controls"].append("blue")
    v3.write_text(json.dumps(v3_payload), encoding="utf-8")
    third = load_context(v2, v3, cache_dir="cache", device=torch.device("cpu"))
    assert third is not first
    assert len(calls) == 2
