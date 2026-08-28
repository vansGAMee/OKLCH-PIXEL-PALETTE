from __future__ import annotations

import numpy as np

from ml.palettebrain.evaluate_semantic_v3 import (
    adversarial_semantics_pass,
    clean_multicolor_rate,
    composition_semantics_pass,
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
