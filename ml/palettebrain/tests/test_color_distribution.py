from __future__ import annotations

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
