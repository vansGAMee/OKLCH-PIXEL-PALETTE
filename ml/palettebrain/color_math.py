"""Shared physical color math for PaletteBrain training and evaluation."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from torch import Tensor


LIGHTNESS_MIN = 0.07
LIGHTNESS_RANGE = 0.86
CHROMA_HEADROOM = 0.92
HUE_VECTOR_EPSILON = 1e-8
HUE_DISABLED_CHROMA = 0.02
HUE_FULL_CHROMA = 0.05


def oklch_to_srgb(
    lightness: float, chroma: float, hue_degrees: float
) -> tuple[float, float, float]:
    """Match the browser's Culori-derived OKLCH to gamma-sRGB conversion."""

    angle = math.radians(float(hue_degrees) % 360.0)
    a_axis = float(chroma) * math.cos(angle)
    b_axis = float(chroma) * math.sin(angle)
    l_value = float(lightness)
    l_cube = (
        l_value + 0.3963377773761749 * a_axis + 0.2158037573099136 * b_axis
    ) ** 3
    m_cube = (
        l_value - 0.1055613458156586 * a_axis - 0.0638541728258133 * b_axis
    ) ** 3
    s_cube = (
        l_value - 0.0894841775298119 * a_axis - 1.2914855480194092 * b_axis
    ) ** 3
    linear = (
        4.0767416360759574 * l_cube
        - 3.3077115392580616 * m_cube
        + 0.2309699031821044 * s_cube,
        -1.2684379732850317 * l_cube
        + 2.6097573492876887 * m_cube
        - 0.3413193760026573 * s_cube,
        -0.0041960761386756 * l_cube
        - 0.7034186179359362 * m_cube
        + 1.7076146940746117 * s_cube,
    )

    def gamma(value: float) -> float:
        if abs(value) > 0.0031308:
            return math.copysign(
                1.055 * (abs(value) ** (1.0 / 2.4)) - 0.055, value
            )
        return 12.92 * value

    return tuple(gamma(value) for value in linear)


def is_in_srgb_gamut(
    lightness: float, chroma: float, hue_degrees: float
) -> bool:
    return all(
        -1e-4 <= channel <= 1.0001
        for channel in oklch_to_srgb(lightness, chroma, hue_degrees)
    )


def max_srgb_chroma_at(lightness: float, hue_degrees: float) -> float:
    """Match the browser's doubling search plus 20 binary-search iterations."""

    normalized_lightness = min(1.0, max(0.0, float(lightness)))
    normalized_hue = float(hue_degrees) % 360.0
    low = 0.0
    high = 0.05
    while high < 1.0 and is_in_srgb_gamut(
        normalized_lightness, high, normalized_hue
    ):
        low = high
        high *= 2.0
    high = min(high, 1.0)
    for _ in range(20):
        middle = (low + high) / 2.0
        if is_in_srgb_gamut(normalized_lightness, middle, normalized_hue):
            low = middle
        else:
            high = middle
    return low


def representation_to_oklab(representation: Tensor) -> Tensor:
    """Decode decoder channels to physical OKLab with Torch gradients.

    Forward values match the browser's relative-chroma contract. The gamut
    boundary is a detached scale factor, so callers retain gradients through L,
    relative C, and normalized hue without differentiating through the search.
    """

    if representation.ndim != 3 or representation.shape[-1] < 4:
        raise ValueError("representation must have shape [B, S, >=4]")

    import torch
    import torch.nn.functional as F

    lightness = LIGHTNESS_MIN + LIGHTNESS_RANGE * torch.sigmoid(
        representation[..., 0]
    )
    hue_raw = representation[..., 2:4]
    hue_norm = torch.linalg.vector_norm(hue_raw, dim=-1)
    normalized_hue = F.normalize(hue_raw, dim=-1, eps=HUE_VECTOR_EPSILON)
    hue_is_defined = hue_norm >= HUE_VECTOR_EPSILON

    with torch.no_grad():
        hue_degrees = torch.remainder(
            torch.rad2deg(
                torch.atan2(normalized_hue[..., 0], normalized_hue[..., 1])
            ),
            360.0,
        )
        flat_lightness = lightness.detach().reshape(-1).cpu().tolist()
        flat_hue = hue_degrees.detach().reshape(-1).cpu().tolist()
        flat_defined = hue_is_defined.detach().reshape(-1).cpu().tolist()
        max_chroma_values = [
            max_srgb_chroma_at(l_value, h_value) if is_defined else 0.0
            for l_value, h_value, is_defined in zip(
                flat_lightness, flat_hue, flat_defined, strict=True
            )
        ]
        max_chroma = torch.as_tensor(
            max_chroma_values,
            dtype=representation.dtype,
            device=representation.device,
        ).reshape(lightness.shape)

    chroma = (
        torch.sigmoid(representation[..., 1])
        * max_chroma
        * CHROMA_HEADROOM
        * hue_is_defined.to(representation.dtype)
    )
    a_axis = chroma * normalized_hue[..., 1]
    b_axis = chroma * normalized_hue[..., 0]
    return torch.stack((lightness, a_axis, b_axis), dim=-1)


def representation_to_oklab_numpy(representation: np.ndarray) -> np.ndarray:
    """Decode decoder channels to physical OKLab without a Torch dependency."""

    values = np.asarray(representation)
    if values.ndim < 2 or values.shape[-1] < 4:
        raise ValueError("representation must have shape [..., S, >=4]")
    output_dtype = values.dtype if np.issubdtype(values.dtype, np.floating) else np.float32
    working = values.astype(np.float64, copy=False)

    lightness = LIGHTNESS_MIN + LIGHTNESS_RANGE / (
        1.0 + np.exp(-np.clip(working[..., 0], -80.0, 80.0))
    )
    hue_raw = working[..., 2:4]
    hue_norm = np.linalg.norm(hue_raw, axis=-1)
    hue_is_defined = hue_norm >= HUE_VECTOR_EPSILON
    normalized_hue = np.divide(
        hue_raw,
        np.maximum(hue_norm[..., None], HUE_VECTOR_EPSILON),
        out=np.zeros_like(hue_raw),
    )
    hue_degrees = (
        np.degrees(np.arctan2(normalized_hue[..., 0], normalized_hue[..., 1]))
        % 360.0
    )
    max_chroma = np.zeros_like(lightness)
    for index in np.ndindex(lightness.shape):
        if hue_is_defined[index]:
            max_chroma[index] = max_srgb_chroma_at(
                float(lightness[index]), float(hue_degrees[index])
            )

    relative_chroma = 1.0 / (
        1.0 + np.exp(-np.clip(working[..., 1], -80.0, 80.0))
    )
    chroma = relative_chroma * max_chroma * CHROMA_HEADROOM
    oklab = np.stack(
        (
            lightness,
            chroma * normalized_hue[..., 1],
            chroma * normalized_hue[..., 0],
        ),
        axis=-1,
    )
    return oklab.astype(output_dtype, copy=False)


def hue_relevance_from_oklab(oklab: Tensor) -> Tensor:
    """Return a 0..1 hue weight based on target physical chroma."""

    import torch

    physical_chroma = torch.linalg.vector_norm(oklab[..., 1:3], dim=-1)
    return (
        (physical_chroma - HUE_DISABLED_CHROMA)
        / (HUE_FULL_CHROMA - HUE_DISABLED_CHROMA)
    ).clamp(0.0, 1.0)
