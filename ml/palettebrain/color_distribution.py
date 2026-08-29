"""
Perceptual OKLCH Color Histogram (390 bins) for PaletteBrain C11.
Circular hue (16 bins), lightness (6 bins), chroma (4 bins) + neutral lightness (6 bins).
"""

from __future__ import annotations

import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

NUM_HUE_BINS = 16
NUM_LIGHT_BINS = 6
NUM_CHROMA_BINS = 4
NUM_NEUTRAL_BINS = 6
TOTAL_HISTOGRAM_BINS = NUM_HUE_BINS * NUM_LIGHT_BINS * NUM_CHROMA_BINS + NUM_NEUTRAL_BINS  # 384 + 6 = 390

LIGHT_EDGES = np.linspace(0.15, 0.90, NUM_LIGHT_BINS + 1)
CHROMA_EDGES = np.linspace(0.03, 0.25, NUM_CHROMA_BINS + 1)
NEUTRAL_CHROMA_CUTOFF = 0.03

def palette_or_pixels_to_oklch_histogram(
    oklab_colors: np.ndarray,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Compute soft 390-bin OKLCH perceptual histogram."""
    oklab_colors = np.asarray(oklab_colors, dtype=np.float32)

    if oklab_colors.ndim == 1:
        oklab_colors = oklab_colors.reshape(1, 3)

    if oklab_colors.ndim not in (2, 3) or oklab_colors.shape[-1] != 3:
        raise ValueError("oklab_colors must have shape [N,3] or [B,N,3]")

    oklab_colors = oklab_colors.reshape(-1, 3)

    if len(oklab_colors) == 0 or not np.isfinite(oklab_colors).all():
        raise ValueError("oklab_colors must be non-empty and finite")

    n = len(oklab_colors)

    if weights is None:
        weights = np.full(n, 1.0 / n, dtype=np.float32)
    else:
        weights = np.asarray(weights, dtype=np.float32).reshape(-1)

        if (
            len(weights) != n
            or not np.isfinite(weights).all()
            or np.any(weights < 0)
        ):
            raise ValueError(
                "weights must be finite, non-negative, and match the colors"
            )

        weight_sum = np.sum(weights)

        if float(weight_sum) <= 0:
            raise ValueError("weights must have positive mass")

        weights = weights / (weight_sum + 1e-8)

    lightness = oklab_colors[:, 0]
    a = oklab_colors[:, 1]
    b = oklab_colors[:, 2]

    chroma = np.sqrt(a * a + b * b)
    hue = np.mod(np.arctan2(b, a), 2 * np.pi)

    l_float = np.clip(
        (lightness - 0.15) / (0.75 / NUM_LIGHT_BINS),
        0,
        NUM_LIGHT_BINS - 1,
    )

    l_low = np.floor(l_float).astype(np.intp)
    l_high = np.minimum(l_low + 1, NUM_LIGHT_BINS - 1)

    l_w_high = (l_float - l_low).astype(np.float32)
    l_w_low = 1.0 - l_w_high

    hist = np.zeros(TOTAL_HISTOGRAM_BINS, dtype=np.float32)

    neutral = chroma < NEUTRAL_CHROMA_CUTOFF

    if np.any(neutral):
        neutral_base = (
            NUM_HUE_BINS * NUM_LIGHT_BINS * NUM_CHROMA_BINS
        )

        hist += np.bincount(
            neutral_base + l_low[neutral],
            weights=weights[neutral] * l_w_low[neutral],
            minlength=TOTAL_HISTOGRAM_BINS,
        ).astype(np.float32)

        hist += np.bincount(
            neutral_base + l_high[neutral],
            weights=weights[neutral] * l_w_high[neutral],
            minlength=TOTAL_HISTOGRAM_BINS,
        ).astype(np.float32)

    chromatic = ~neutral

    if np.any(chromatic):
        h_float = (
            hue[chromatic] / (2 * np.pi)
        ) * NUM_HUE_BINS

        h_floor = np.floor(h_float)
        h_low = h_floor.astype(np.intp) % NUM_HUE_BINS
        h_high = (h_low + 1) % NUM_HUE_BINS

        h_w_high = (h_float - h_floor).astype(np.float32)
        h_w_low = 1.0 - h_w_high

        c_float = np.clip(
            (chroma[chromatic] - 0.03)
            / (0.22 / NUM_CHROMA_BINS),
            0,
            NUM_CHROMA_BINS - 1,
        )

        c_low = np.floor(c_float).astype(np.intp)
        c_high = np.minimum(c_low + 1, NUM_CHROMA_BINS - 1)

        c_w_high = (c_float - c_low).astype(np.float32)
        c_w_low = 1.0 - c_w_high

        ll = l_low[chromatic]
        lh = l_high[chromatic]

        lwl = l_w_low[chromatic]
        lwh = l_w_high[chromatic]

        w = weights[chromatic]

        # Only eight NumPy reductions remain.
        # The old code executed these operations once per pixel in Python.
        for h_idx, h_weight in (
            (h_low, h_w_low),
            (h_high, h_w_high),
        ):
            for l_idx, l_weight in (
                (ll, lwl),
                (lh, lwh),
            ):
                for c_idx, c_weight in (
                    (c_low, c_w_low),
                    (c_high, c_w_high),
                ):
                    indices = (
                        h_idx
                        * NUM_LIGHT_BINS
                        * NUM_CHROMA_BINS
                        + l_idx * NUM_CHROMA_BINS
                        + c_idx
                    )

                    hist += np.bincount(
                        indices,
                        weights=(
                            w
                            * h_weight
                            * l_weight
                            * c_weight
                        ),
                        minlength=TOTAL_HISTOGRAM_BINS,
                    ).astype(np.float32)

    total = np.sum(hist)

    if total > 0:
        hist = hist / total

    return hist

def smooth_circular_histogram_loss(
    predicted_logits: torch.Tensor,  # [B, 390]
    target_distribution: torch.Tensor,  # [B, 390]
) -> torch.Tensor:
    """KL divergence with soft target distribution."""
    log_probs = F.log_softmax(predicted_logits, dim=-1)
    target_smooth = target_distribution + 1e-6
    target_smooth = target_smooth / target_smooth.sum(dim=-1, keepdim=True)
    kl = F.kl_div(log_probs, target_smooth, reduction="batchmean")
    return kl
