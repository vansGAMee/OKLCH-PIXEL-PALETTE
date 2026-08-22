"""
Loss functions for palette intent prediction.
All math exactly as specified in the implementation spec.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

L_MIN = 0.07
L_MAX = 0.93

_smooth_l1 = nn.SmoothL1Loss(reduction="mean")
_ce = nn.CrossEntropyLoss(reduction="mean")


def decode_L(lightness_logit: torch.Tensor) -> torch.Tensor:
    return L_MIN + torch.sigmoid(lightness_logit) * (L_MAX - L_MIN)


def decode_relative_chroma(relative_chroma_logit: torch.Tensor) -> torch.Tensor:
    return torch.sigmoid(relative_chroma_logit)


def normalize_hue_vector(
    hue_sin_raw: torch.Tensor,
    hue_cos_raw: torch.Tensor,
    eps: float = 1e-8,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Returns (hue_sin_norm, hue_cos_norm, norm)."""
    norm = torch.sqrt(hue_sin_raw.square() + hue_cos_raw.square() + eps)
    return hue_sin_raw / norm, hue_cos_raw / norm, norm


def palette_loss(
    pred: torch.Tensor,       # [B, 7]
    targets: dict[str, torch.Tensor],
    loss_weights: dict[str, float] | None = None,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """
    Compute total loss as per spec §7.
    Returns (total_loss, component_losses_dict).
    """
    if loss_weights is None:
        loss_weights = {
            "lightness": 1.0,
            "hue": 1.0,
            "chroma": 0.8,
            "harmony": 0.6,
            "hue_norm": 0.02,
        }

    # Unpack predictions
    lightness_logit       = pred[:, 0]
    hue_sin_raw           = pred[:, 1]
    hue_cos_raw           = pred[:, 2]
    relative_chroma_logit = pred[:, 3]
    harmony_logits        = pred[:, 4:7]   # [B, 3]

    # Decode
    pred_L             = decode_L(lightness_logit)
    pred_rel_chroma    = decode_relative_chroma(relative_chroma_logit)
    pred_hue_sin, pred_hue_cos, hue_norm = normalize_hue_vector(hue_sin_raw, hue_cos_raw)

    # --- Lightness loss ---
    target_L = targets["target_L"]
    lightness_loss = _smooth_l1(pred_L, target_L)

    # --- Hue loss ---
    target_hue_sin = targets["target_hue_sin"]
    target_hue_cos = targets["target_hue_cos"]
    target_abs_chroma = targets["target_absolute_chroma"]

    hue_cosine_loss = 1.0 - (
        pred_hue_sin * target_hue_sin
        + pred_hue_cos * target_hue_cos
    )  # [B]

    # Weight by absolute chroma importance
    hue_weight = torch.clamp(
        (target_abs_chroma - 0.01) / 0.04, 0.0, 1.0
    )  # [B]
    weighted_hue_loss = (hue_weight * hue_cosine_loss).mean()

    # Norm penalty: encourage unit vector
    hue_norm_penalty = (hue_norm - 1.0).square().mean()

    # --- Chroma loss ---
    target_rel_chroma = targets["target_relative_chroma"]
    chroma_loss = _smooth_l1(pred_rel_chroma, target_rel_chroma)

    # --- Harmony loss ---
    target_harmony = targets["target_harmony_class"]
    harmony_loss = _ce(harmony_logits, target_harmony)

    # --- Total ---
    total_loss = (
        loss_weights["lightness"] * lightness_loss
        + loss_weights["hue"] * weighted_hue_loss
        + loss_weights["chroma"] * chroma_loss
        + loss_weights["harmony"] * harmony_loss
        + loss_weights["hue_norm"] * hue_norm_penalty
    )

    components = {
        "lightness": lightness_loss.detach(),
        "weighted_hue": weighted_hue_loss.detach(),
        "chroma": chroma_loss.detach(),
        "harmony": harmony_loss.detach(),
        "hue_norm": hue_norm_penalty.detach(),
    }

    return total_loss, components
