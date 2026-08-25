"""Physical palette targets for legal curated data and training-only anchors."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

try:
    from .color_math import (
        CHROMA_HEADROOM,
        LIGHTNESS_MIN,
        LIGHTNESS_RANGE,
        max_srgb_chroma_at,
    )
except ImportError:
    from color_math import (  # type: ignore[no-redef]
        CHROMA_HEADROOM,
        LIGHTNESS_MIN,
        LIGHTNESS_RANGE,
        max_srgb_chroma_at,
    )


MAX_COLORS = 9


def _safe_logit(value: float, epsilon: float = 1e-4) -> float:
    clipped = min(1.0 - epsilon, max(epsilon, float(value)))
    return math.log(clipped / (1.0 - clipped))


def _parse_hex(value: str) -> tuple[float, float, float]:
    normalized = value.strip().lstrip("#")
    if len(normalized) == 3:
        normalized = "".join(character * 2 for character in normalized)
    if len(normalized) != 6:
        raise ValueError(f"invalid six-digit HEX color: {value!r}")
    try:
        channels = tuple(int(normalized[index : index + 2], 16) / 255.0 for index in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"invalid HEX color: {value!r}") from exc
    return channels  # type: ignore[return-value]


def _srgb_to_linear(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def hex_to_oklab(value: str) -> np.ndarray:
    """Convert sRGB HEX to physical OKLab using the Culori/runtime matrices."""

    red, green, blue = (_srgb_to_linear(channel) for channel in _parse_hex(value))
    l_value = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    m_value = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    s_value = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    l_root = np.cbrt(l_value)
    m_root = np.cbrt(m_value)
    s_root = np.cbrt(s_value)
    return np.asarray(
        [
            0.2104542553 * l_root + 0.7936177850 * m_root - 0.0040720468 * s_root,
            1.9779984951 * l_root - 2.4285922050 * m_root + 0.4505937099 * s_root,
            0.0259040371 * l_root + 0.7827717662 * m_root - 0.8086757660 * s_root,
        ],
        dtype=np.float32,
    )


def oklab_to_oklch(oklab: Sequence[float]) -> tuple[float, float, float | None]:
    lightness, a_axis, b_axis = (float(value) for value in oklab)
    chroma = math.hypot(a_axis, b_axis)
    hue = math.degrees(math.atan2(b_axis, a_axis)) % 360.0 if chroma > 1e-7 else None
    return lightness, chroma, hue


def physical_oklch_to_target(
    lightness: float,
    chroma: float,
    hue: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Encode a gamut-safe physical color to target and lock representations."""

    lightness = min(LIGHTNESS_MIN + LIGHTNESS_RANGE, max(LIGHTNESS_MIN, lightness))
    normalized_hue = 0.0 if hue is None else float(hue) % 360.0
    maximum = max_srgb_chroma_at(lightness, normalized_hue) * CHROMA_HEADROOM
    bounded_chroma = min(maximum, max(0.0, chroma))
    relative_chroma = bounded_chroma / maximum if maximum > 1e-8 else 0.0
    radians = math.radians(normalized_hue)
    hue_sin = math.sin(radians)
    hue_cos = math.cos(radians)
    target = np.asarray(
        [
            _safe_logit((lightness - LIGHTNESS_MIN) / LIGHTNESS_RANGE),
            _safe_logit(relative_chroma),
            hue_sin,
            hue_cos,
            0.0,
        ],
        dtype=np.float32,
    )
    locked = np.asarray(
        [lightness, bounded_chroma, hue_sin, hue_cos], dtype=np.float32
    )
    return target, locked


def hex_to_target(value: str) -> tuple[np.ndarray, np.ndarray]:
    return physical_oklch_to_target(*oklab_to_oklch(hex_to_oklab(value)))


def perceptual_subset(colors: Sequence[str], requested_count: int) -> list[str]:
    """Reduce a palette while retaining value endpoints and perceptual spacing."""

    unique: list[str] = []
    seen: set[str] = set()
    for color in colors:
        normalized = "#" + color.strip().lstrip("#").lower()
        if normalized not in seen:
            _parse_hex(normalized)
            seen.add(normalized)
            unique.append(normalized)
    if requested_count < 2 or requested_count > MAX_COLORS:
        raise ValueError("requested_count must be between 2 and 9")
    if len(unique) < requested_count:
        raise ValueError("perceptual_subset does not invent expansion colors")
    if len(unique) == requested_count:
        return unique

    points = np.stack([hex_to_oklab(color) for color in unique])
    selected = [int(np.argmin(points[:, 0]))]
    lightest = int(np.argmax(points[:, 0]))
    if lightest not in selected:
        selected.append(lightest)
    while len(selected) < requested_count:
        remaining = [index for index in range(len(unique)) if index not in selected]
        minimum_distances = [
            min(float(np.linalg.norm(points[index] - points[chosen])) for chosen in selected)
            for index in remaining
        ]
        selected.append(remaining[int(np.argmax(minimum_distances))])
    return [unique[index] for index in sorted(selected)]


def family_palette(
    anchor_hex: str,
    count: int,
    *,
    family: str,
    modifier: str = "base",
) -> tuple[np.ndarray, np.ndarray]:
    """Create bounded training-only monochromatic grounding supervision."""

    if count < 2 or count > MAX_COLORS:
        raise ValueError("count must be between 2 and 9")
    anchor_l, _, anchor_h = oklab_to_oklch(hex_to_oklab(anchor_hex))
    positions = np.linspace(-1.0, 1.0, count, dtype=np.float32)

    if family == "black":
        lightnesses = np.linspace(0.07, 0.34, count)
        fractions = np.full(count, 0.025)
        anchor_h = 0.0
    elif family == "white":
        lightnesses = np.linspace(0.70, 0.93, count)
        fractions = np.full(count, 0.02)
        anchor_h = 90.0
    elif family == "gray":
        lightnesses = np.linspace(0.28, 0.78, count)
        fractions = np.full(count, 0.03)
        anchor_h = 250.0
    else:
        center_shift = {
            "dark": -0.16,
            "deep": -0.13,
            "bright": 0.05,
            "pale": 0.16,
            "neon": 0.08,
            "dirty": -0.05,
        }.get(modifier, 0.0)
        spread = 0.14 if modifier == "pale" else 0.18
        lightnesses = np.clip(anchor_l + center_shift + spread * positions, 0.09, 0.91)
        peak = {
            "pale": 0.38,
            "dirty": 0.34,
            "bright": 0.96,
            "neon": 0.98,
            "deep": 0.86,
            "dark": 0.78,
        }.get(modifier, 0.88)
        fractions = 0.18 + (peak - 0.18) * (1.0 - np.abs(positions))

    targets = np.zeros((MAX_COLORS, 5), dtype=np.float32)
    locks = np.zeros((MAX_COLORS, 4), dtype=np.float32)
    for index, (lightness, fraction) in enumerate(zip(lightnesses, fractions, strict=True)):
        hue = float(anchor_h or 0.0)
        chroma = max_srgb_chroma_at(float(lightness), hue) * CHROMA_HEADROOM * float(fraction)
        targets[index], locks[index] = physical_oklch_to_target(
            float(lightness), chroma, hue
        )
    return targets, locks


def hex_palette_target(colors: Iterable[str]) -> tuple[np.ndarray, np.ndarray]:
    normalized = list(colors)
    if not 2 <= len(normalized) <= MAX_COLORS:
        raise ValueError("palette target must contain 2..9 colors")
    targets = np.zeros((MAX_COLORS, 5), dtype=np.float32)
    locks = np.zeros((MAX_COLORS, 4), dtype=np.float32)
    for index, color in enumerate(normalized):
        targets[index], locks[index] = hex_to_target(color)
    return targets, locks
