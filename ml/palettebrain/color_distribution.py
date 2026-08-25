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
    if oklab_colors.ndim == 1:
        oklab_colors = oklab_colors.reshape(1, 3)
    N = len(oklab_colors)
    if weights is None:
        weights = np.ones(N, dtype=np.float32) / N
    else:
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

        if c_val < NEUTRAL_CHROMA_CUTOFF:
            l_idx = int(np.clip((l_val - 0.15) / (0.75 / NUM_NEUTRAL_BINS), 0, NUM_NEUTRAL_BINS - 1))
            hist[384 + l_idx] += w
        else:
            h_float = (h_val / (2 * np.pi)) * NUM_HUE_BINS
            h_low = int(math.floor(h_float)) % NUM_HUE_BINS
            h_high = (h_low + 1) % NUM_HUE_BINS
            h_w_high = h_float - math.floor(h_float)
            h_w_low = 1.0 - h_w_high

            l_idx = int(np.clip((l_val - 0.15) / (0.75 / NUM_LIGHT_BINS), 0, NUM_LIGHT_BINS - 1))
            c_idx = int(np.clip((c_val - 0.03) / (0.22 / NUM_CHROMA_BINS), 0, NUM_CHROMA_BINS - 1))

            base_low = (h_low * NUM_LIGHT_BINS * NUM_CHROMA_BINS) + (l_idx * NUM_CHROMA_BINS) + c_idx
            base_high = (h_high * NUM_LIGHT_BINS * NUM_CHROMA_BINS) + (l_idx * NUM_CHROMA_BINS) + c_idx

            hist[base_low] += w * h_w_low
            hist[base_high] += w * h_w_high

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
