"""Training-only physical color decoding and palette-set matching helpers."""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment
import torch
from torch import Tensor


def match_free_targets(
    target: Tensor,
    predicted_oklab: Tensor,
    target_oklab: Tensor,
    count_mask: Tensor,
    locked_mask: Tensor,
) -> tuple[Tensor, Tensor]:
    """Align free targets to prediction slots with detached OKLab Hungarian cost.

    Locked target slots remain at their original indices and are excluded from
    both sides of the assignment. The returned target tensors are detached;
    assignment selection is never part of the gradient graph.
    """

    if target.ndim != 3 or target.shape[-1] < 4:
        raise ValueError("target must have shape [B, S, >=4]")
    if predicted_oklab.shape != (*target.shape[:2], 3):
        raise ValueError("predicted_oklab must have shape [B, S, 3]")
    if target_oklab.shape != predicted_oklab.shape:
        raise ValueError("target_oklab must match predicted_oklab")
    if count_mask.shape != target.shape[:2] or locked_mask.shape != target.shape[:2]:
        raise ValueError("count_mask and locked_mask must have shape [B, S]")

    active = count_mask > 0.5
    locked = active & (locked_mask > 0.5)
    free = active & ~locked
    aligned_target = target.detach().clone()
    aligned_target_oklab = target_oklab.detach().clone()

    for batch_index in range(target.shape[0]):
        free_indices = torch.nonzero(free[batch_index], as_tuple=False).flatten()
        if free_indices.numel() <= 1:
            continue

        pairwise_cost = torch.cdist(
            predicted_oklab[batch_index, free_indices].detach(),
            target_oklab[batch_index, free_indices].detach(),
        ).cpu().numpy()
        if not np.isfinite(pairwise_cost).all():
            raise RuntimeError("non-finite OKLab matching cost")
        prediction_rows, target_columns = linear_sum_assignment(pairwise_cost)
        prediction_slots = free_indices[
            torch.as_tensor(prediction_rows, device=free_indices.device)
        ]
        target_slots = free_indices[
            torch.as_tensor(target_columns, device=free_indices.device)
        ]
        aligned_target[batch_index, prediction_slots] = target.detach()[
            batch_index, target_slots
        ]
        aligned_target_oklab[batch_index, prediction_slots] = target_oklab.detach()[
            batch_index, target_slots
        ]

    return aligned_target, aligned_target_oklab
