from __future__ import annotations

import math
import numpy as np
import pytest
import torch

from ml.palettebrain.color_distribution import (
    TOTAL_HISTOGRAM_BINS,
    palette_or_pixels_to_oklch_histogram,
    smooth_circular_histogram_loss,
)


def _oklab(lightness: float, chroma: float, hue_degrees: float) -> np.ndarray:
    angle = np.deg2rad(hue_degrees)
    return np.array(
        [lightness, chroma * np.cos(angle), chroma * np.sin(angle)],
        dtype=np.float32,
    )


def _scalar_reference(colors: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    values = np.asarray(colors, dtype=np.float32).reshape(-1, 3)
    if weights is None:
        weights = np.ones(len(values), dtype=np.float32) / len(values)
    else:
        weights = np.asarray(weights, dtype=np.float32).reshape(-1)
        weights = weights / (weights.sum() + 1e-8)
    histogram = np.zeros(TOTAL_HISTOGRAM_BINS, dtype=np.float32)
    chroma = np.sqrt(values[:, 1] ** 2 + values[:, 2] ** 2)
    hue = np.arctan2(values[:, 2], values[:, 1]) % (2 * np.pi)
    for index in range(len(values)):
        light_float = float(np.clip((values[index, 0] - 0.15) / (0.75 / 6), 0, 5))
        light_low = int(math.floor(light_float))
        light_weights = ((light_low, 1 - (light_float - light_low)), (min(light_low + 1, 5), light_float - light_low))
        if chroma[index] < 0.03:
            for light_bin, light_weight in light_weights:
                histogram[384 + light_bin] += weights[index] * light_weight
            continue
        hue_float = hue[index] / (2 * np.pi) * 16
        hue_low = int(math.floor(hue_float)) % 16
        hue_weights = ((hue_low, 1 - (hue_float - math.floor(hue_float))), ((hue_low + 1) % 16, hue_float - math.floor(hue_float)))
        chroma_float = float(np.clip((chroma[index] - 0.03) / (0.22 / 4), 0, 3))
        chroma_low = int(math.floor(chroma_float))
        chroma_weights = ((chroma_low, 1 - (chroma_float - chroma_low)), (min(chroma_low + 1, 3), chroma_float - chroma_low))
        for hue_bin, hue_weight in hue_weights:
            for light_bin, light_weight in light_weights:
                for chroma_bin, chroma_weight in chroma_weights:
                    histogram[hue_bin * 24 + light_bin * 4 + chroma_bin] += weights[index] * hue_weight * light_weight * chroma_weight
    return histogram / histogram.sum()


def test_histogram_is_normalized_and_supports_batched_pixels() -> None:
    pixels = np.stack([
        _oklab(0.4, 0.12, 359.9),
        _oklab(0.6, 0.10, 0.1),
        _oklab(0.8, 0.0, 0.0),
        _oklab(0.2, 0.02, 180.0),
    ]).reshape(2, 2, 3)
    histogram = palette_or_pixels_to_oklch_histogram(pixels)
    assert histogram.shape == (TOTAL_HISTOGRAM_BINS,)
    assert np.isfinite(histogram).all()
    assert np.isclose(histogram.sum(), 1.0, atol=1e-6)
    assert histogram[384:].sum() == pytest.approx(0.5, abs=1e-6)


def test_circular_hue_assignment_is_continuous_at_zero_degrees() -> None:
    left = palette_or_pixels_to_oklch_histogram(_oklab(0.55, 0.12, 359.99))
    right = palette_or_pixels_to_oklch_histogram(_oklab(0.55, 0.12, 0.01))
    assert np.abs(left - right).sum() < 0.01
    assert left[:24].sum() > 0
    assert left[-24 - 6:-6].sum() > 0


def test_lightness_and_chroma_receive_soft_assignment() -> None:
    histogram = palette_or_pixels_to_oklch_histogram(_oklab(0.51, 0.11, 90.0))
    assert np.count_nonzero(histogram) >= 4
    assert np.isclose(histogram.sum(), 1.0, atol=1e-6)


@pytest.mark.parametrize(
    "value",
    [np.empty((0, 3), dtype=np.float32), np.array([[np.nan, 0, 0]], dtype=np.float32)],
)
def test_invalid_colors_are_rejected(value: np.ndarray) -> None:
    with pytest.raises(ValueError):
        palette_or_pixels_to_oklch_histogram(value)


def test_histogram_kl_has_finite_gradients() -> None:
    logits = torch.randn(3, TOTAL_HISTOGRAM_BINS, requires_grad=True)
    targets = torch.from_numpy(
        np.stack([
            palette_or_pixels_to_oklch_histogram(_oklab(0.2 + i * 0.2, 0.1, i * 120))
            for i in range(3)
        ])
    )
    loss = smooth_circular_histogram_loss(logits, targets)
    loss.backward()
    assert torch.isfinite(loss)
    assert logits.grad is not None and torch.isfinite(logits.grad).all()


def test_vectorized_histogram_matches_scalar_reference_at_boundaries_and_random() -> None:
    rng = np.random.RandomState(20260829)
    boundary = np.stack([
        _oklab(0.15, 0.0, 0.0), _oklab(0.90, 0.0, 0.0),
        _oklab(0.55, 0.029999, 359.999), _oklab(0.55, 0.030001, 0.001),
    ])
    random = rng.normal(size=(10_000, 3)).astype(np.float32)
    random = random * np.asarray([0.15, 0.08, 0.08], dtype=np.float32) + np.asarray([0.55, 0, 0], dtype=np.float32)
    for values in (boundary, random):
        expected = _scalar_reference(values)
        actual = palette_or_pixels_to_oklch_histogram(values)
        np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-7)
        assert np.isfinite(actual).all()
        assert actual.sum() == pytest.approx(1.0, abs=1e-6)


def test_vectorized_histogram_matches_scalar_reference_with_weights() -> None:
    values = np.stack([_oklab(0.2 + index * 0.1, 0.02 + index * 0.03, index * 51) for index in range(7)])
    weights = np.asarray([1, 2, 3, 4, 5, 6, 7], dtype=np.float32)
    np.testing.assert_allclose(
        palette_or_pixels_to_oklch_histogram(values, weights),
        _scalar_reference(values, weights),
        rtol=1e-6,
        atol=1e-7,
    )
