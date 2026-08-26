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
    oklab_colors: np.ndarray,  # shape [N, 3] or [B, N, 3]
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
    N = len(oklab_colors)
    if weights is None:
        weights = np.ones(N, dtype=np.float32) / N
    else:
        weights = np.asarray(weights, dtype=np.float32).reshape(-1)
        if len(weights) != N or not np.isfinite(weights).all() or np.any(weights < 0):
            raise ValueError("weights must be finite, non-negative, and match the colors")
        if float(np.sum(weights)) <= 0:
            raise ValueError("weights must have positive mass")
        weights = weights / (np.sum(weights) + 1e-8)

    L = oklab_colors[:, 0]
    a = oklab_colors[:, 1]
    b = oklab_colors[:, 2]
    C = np.sqrt(a**2 + b**2)
    h_rad = np.arctan2(b, a) % (2 * np.pi)

    hist = np.zeros(TOTAL_HISTOGRAM_BINS, dtype=np.float32)

    for i in range(N):
        l_val = L[i]
        c_val = C[i]
        h_val = h_rad[i]
        w = weights[i]

        l_float = float(np.clip((l_val - 0.15) / (0.75 / NUM_LIGHT_BINS), 0, NUM_LIGHT_BINS - 1))
        l_low = int(math.floor(l_float))
        l_high = min(l_low + 1, NUM_LIGHT_BINS - 1)
        l_w_high = l_float - l_low
        l_weights = ((l_low, 1.0 - l_w_high), (l_high, l_w_high))

        if c_val < NEUTRAL_CHROMA_CUTOFF:
            for l_idx, l_weight in l_weights:
                hist[384 + l_idx] += w * l_weight
        else:
            h_float = (h_val / (2 * np.pi)) * NUM_HUE_BINS
            h_low = int(math.floor(h_float)) % NUM_HUE_BINS
            h_high = (h_low + 1) % NUM_HUE_BINS
            h_w_high = h_float - math.floor(h_float)
            h_w_low = 1.0 - h_w_high

            c_float = float(np.clip((c_val - 0.03) / (0.22 / NUM_CHROMA_BINS), 0, NUM_CHROMA_BINS - 1))
            c_low = int(math.floor(c_float))
            c_high = min(c_low + 1, NUM_CHROMA_BINS - 1)
            c_w_high = c_float - c_low
            for h_idx, h_weight in ((h_low, h_w_low), (h_high, h_w_high)):
                for l_idx, l_weight in l_weights:
                    for c_idx, c_weight in ((c_low, 1.0 - c_w_high), (c_high, c_w_high)):
                        index = (
                            h_idx * NUM_LIGHT_BINS * NUM_CHROMA_BINS
                            + l_idx * NUM_CHROMA_BINS
                            + c_idx
                        )
                        hist[index] += w * h_weight * l_weight * c_weight

    s = np.sum(hist)
    if s > 0:
        hist = hist / s
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
