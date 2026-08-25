"""Dataset utilities and deterministic synthetic complete-palette targets.

The target generator in this module is a plumbing baseline, not a learned or
human-rated source of palette quality. It deterministically expands the scalar
intent labels in ``ml/dataset_embeddings.npz`` into 2..9 slot targets so the
decoder, lock conditioning, losses, export, and browser contract can be tested
before licensed full-palette training data is available.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

try:
    import torch
    from torch.utils.data import Dataset
except ImportError:  # Data preparation and metadata inspection still work.
    torch = None
    Dataset = object  # type: ignore[assignment,misc]


DATASET_VERSION = 1
SYNTHESIS_VERSION = "deterministic-synthetic-palette-v1"
MAX_COLORS = 9
EMBEDDING_DIM = 384
LIGHTNESS_MIN = 0.07
LIGHTNESS_RANGE = 0.86
CHROMA_HEADROOM = 0.92
SPLIT_IDS = {"train": 0, "val": 1, "test": 2}


def stable_uint64(*parts: object) -> int:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def seed_noise_from_uint32(seed: int) -> np.ndarray:
    """Match the browser Mulberry32 + Box-Muller 9x4 seed-noise contract."""

    if not isinstance(seed, (int, np.integer)) or not 0 <= int(seed) <= 0xFFFF_FFFF:
        raise ValueError("seed must be an integer in 0..0xffffffff")
    state = int(seed) & 0xFFFF_FFFF

    def random_unit() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFF_FFFF
        value = state
        value = ((value ^ (value >> 15)) * (value | 1)) & 0xFFFF_FFFF
        multiplied = ((value ^ (value >> 7)) * (value | 61)) & 0xFFFF_FFFF
        value = (value ^ ((value + multiplied) & 0xFFFF_FFFF)) & 0xFFFF_FFFF
        return ((value ^ (value >> 14)) & 0xFFFF_FFFF) / 4294967296.0

    noise = np.empty(MAX_COLORS * 4, dtype=np.float32)
    for index in range(0, noise.size, 2):
        u1 = max(random_unit(), 2.220446049250313e-16)
        u2 = random_unit()
        radius = math.sqrt(-2.0 * math.log(u1))
        angle = 2.0 * math.pi * u2
        noise[index] = np.float32(radius * math.cos(angle))
        noise[index + 1] = np.float32(radius * math.sin(angle))
    return noise.reshape(MAX_COLORS, 4)


def safe_logit(value: np.ndarray | float, epsilon: float = 1e-4) -> np.ndarray:
    clipped = np.clip(np.asarray(value, dtype=np.float32), epsilon, 1.0 - epsilon)
    return np.log(clipped / (1.0 - clipped)).astype(np.float32)


def _wrap_degrees(angle: np.ndarray) -> np.ndarray:
    return ((angle + 180.0) % 360.0) - 180.0


def oklch_to_srgb(lightness: float, chroma: float, hue_degrees: float) -> tuple[float, float, float]:
    """Match the runtime's Culori-derived OKLCH to gamma-sRGB conversion."""

    angle = math.radians(float(hue_degrees) % 360.0)
    a = float(chroma) * math.cos(angle)
    b = float(chroma) * math.sin(angle)
    l_value = float(lightness)
    l_cube = (
        l_value + 0.3963377773761749 * a + 0.2158037573099136 * b
    ) ** 3
    m_cube = (
        l_value - 0.1055613458156586 * a - 0.0638541728258133 * b
    ) ** 3
    s_cube = (
        l_value - 0.0894841775298119 * a - 1.2914855480194092 * b
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
            return math.copysign(1.055 * (abs(value) ** (1.0 / 2.4)) - 0.055, value)
        return 12.92 * value

    return tuple(gamma(value) for value in linear)


def is_in_srgb_gamut(lightness: float, chroma: float, hue_degrees: float) -> bool:
    return all(
        -1e-4 <= channel <= 1.0001
        for channel in oklch_to_srgb(lightness, chroma, hue_degrees)
    )


def max_srgb_chroma_at(lightness: float, hue_degrees: float) -> float:
    """Match the runtime's doubling search plus 20 binary-search iterations."""

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


def encode_lightness(lightness: np.ndarray | float) -> np.ndarray:
    relative = (np.asarray(lightness, dtype=np.float32) - LIGHTNESS_MIN) / LIGHTNESS_RANGE
    return safe_logit(relative)


def decode_lightness(logit: np.ndarray) -> np.ndarray:
    return LIGHTNESS_MIN + LIGHTNESS_RANGE / (1.0 + np.exp(-logit))


def _hue_offsets(harmony: int, count: int) -> np.ndarray:
    position = np.linspace(-1.0, 1.0, count, dtype=np.float32)
    if harmony == 2:  # analogous
        return position * 55.0
    if harmony == 1:  # complementary, with local variation around both poles
        roles = np.asarray(
            [0.0, 180.0, -14.0, 166.0, 14.0, -166.0, -28.0, 152.0, 28.0],
            dtype=np.float32,
        )
        return roles[:count]
    # split complementary
    roles = np.asarray(
        [0.0, 150.0, -150.0, 18.0, 168.0, -168.0, -18.0, 132.0, -132.0],
        dtype=np.float32,
    )
    return roles[:count]


def synthesize_complete_palette(
    base_lightness: float,
    base_chroma_fraction: float,
    base_hue_degrees: float,
    harmony: int,
    count: int,
) -> np.ndarray:
    """Create a deterministic synthetic target with shape ``[9, 5]``.

    This deliberately simple rule creates lightness structure, multiple hue
    roles, and variable importance. It is only a reproducible target for
    exercising a complete-palette neural pipeline.
    """

    if count < 2 or count > MAX_COLORS:
        raise ValueError("count must be between 2 and 9")
    position = np.linspace(-1.0, 1.0, count, dtype=np.float32)
    offsets = _hue_offsets(int(harmony), count)

    lightness = np.clip(
        float(base_lightness)
        + 0.30 * position
        + 0.035 * np.sin((np.arange(count, dtype=np.float32) + 1.0) * 1.7),
        0.07,
        LIGHTNESS_MIN + LIGHTNESS_RANGE,
    )
    offset_strength = np.abs(_wrap_degrees(offsets)) / 180.0
    chroma_fraction = np.clip(
        float(base_chroma_fraction)
        * (0.62 + 0.24 * np.cos(position * math.pi))
        + 0.12 * np.abs(position)
        + 0.13 * offset_strength,
        0.025,
        0.98,
    )
    hue_radians = np.deg2rad((float(base_hue_degrees) + offsets) % 360.0)
    importance = np.clip(
        0.25 + 0.42 * np.abs(position) + 0.28 * offset_strength,
        0.05,
        1.0,
    )

    target = np.zeros((MAX_COLORS, 5), dtype=np.float32)
    target[:count, 0] = encode_lightness(lightness)
    target[:count, 1] = safe_logit(chroma_fraction)
    target[:count, 2] = np.sin(hue_radians).astype(np.float32)
    target[:count, 3] = np.cos(hue_radians).astype(np.float32)
    target[:count, 4] = importance.astype(np.float32)
    return target


def _split_id(text: str, source_index: int, split_seed: int) -> int:
    bucket = stable_uint64("split", split_seed, source_index, text) % 100
    if bucket < 80:
        return SPLIT_IDS["train"]
    if bucket < 90:
        return SPLIT_IDS["val"]
    return SPLIT_IDS["test"]


def _make_lock_mask(
    rng: np.random.Generator,
    count: int,
    mode_key: int,
    lock_probability: float,
) -> np.ndarray:
    mask = np.zeros(MAX_COLORS, dtype=np.float32)
    mode = mode_key % 10
    if mode < 3:
        return mask
    if mode == 3:
        mask[int(rng.integers(0, count))] = 1.0
        return mask
    if mode == 4:
        mask[:count] = 1.0
        mask[int(rng.integers(0, count))] = 0.0
        return mask

    drawn = rng.random(count) < lock_probability
    if not drawn.any():
        drawn[int(rng.integers(0, count))] = True
    if drawn.all():
        drawn[int(rng.integers(0, count))] = False
    mask[:count] = drawn.astype(np.float32)
    return mask


def validate_source_archive(source: Mapping[str, np.ndarray]) -> None:
    required = {
        "embeddings",
        "texts",
        "hues",
        "lightnesses",
        "chromas",
        "harmonies",
    }
    missing = sorted(required.difference(source.keys()))
    if missing:
        raise ValueError(f"source archive is missing arrays: {', '.join(missing)}")
    row_count = int(source["embeddings"].shape[0])
    if source["embeddings"].shape != (row_count, EMBEDDING_DIM):
        raise ValueError("embeddings must have shape [N, 384]")
    for name in required - {"embeddings"}:
        if int(source[name].shape[0]) != row_count:
            raise ValueError(f"{name} row count does not match embeddings")


def build_synthetic_examples(
    source: Mapping[str, np.ndarray],
    counts: Iterable[int] = range(2, 10),
    *,
    split_seed: int = 42,
    lock_probability: float = 0.25,
    limit: int | None = None,
) -> dict[str, np.ndarray]:
    """Expand each source embedding into deterministic examples for all counts."""

    validate_source_archive(source)
    requested_counts = tuple(sorted(set(int(count) for count in counts)))
    if not requested_counts or requested_counts[0] < 2 or requested_counts[-1] > 9:
        raise ValueError("counts must be a non-empty subset of 2..9")
    if not 0.0 <= lock_probability < 1.0:
        raise ValueError("lock_probability must be in [0, 1)")

    source_rows = int(source["embeddings"].shape[0])
    if limit is not None:
        source_rows = min(source_rows, max(1, int(limit)))

    records: dict[str, list[Any]] = {
        "example_ids": [],
        "source_indices": [],
        "texts": [],
        "embeddings": [],
        "counts": [],
        "seeds": [],
        "count_masks": [],
        "seed_noise": [],
        "locked_masks": [],
        "locked_colors": [],
        "targets": [],
        "splits": [],
    }

    for source_index in range(source_rows):
        text = str(source["texts"][source_index])
        split_id = _split_id(text, source_index, split_seed)
        for count in requested_counts:
            example_seed = stable_uint64(
                SYNTHESIS_VERSION, split_seed, source_index, text, count
            )
            rng = np.random.default_rng(example_seed)
            target = synthesize_complete_palette(
                float(source["lightnesses"][source_index]),
                float(source["chromas"][source_index]),
                float(source["hues"][source_index]),
                int(source["harmonies"][source_index]),
                count,
            )
            count_mask = np.zeros(MAX_COLORS, dtype=np.float32)
            count_mask[:count] = 1.0
            browser_seed = int(example_seed & 0xFFFF_FFFF)
            seed_noise = seed_noise_from_uint32(browser_seed)
            locked_mask = _make_lock_mask(
                rng,
                count,
                int(example_seed),
                lock_probability,
            )
            locked_colors = np.zeros((MAX_COLORS, 4), dtype=np.float32)
            locked = locked_mask.astype(bool)
            if locked.any():
                for slot_index in np.flatnonzero(locked):
                    slot_l = float(
                        LIGHTNESS_MIN
                        + LIGHTNESS_RANGE / (1.0 + math.exp(-float(target[slot_index, 0])))
                    )
                    slot_h = math.degrees(
                        math.atan2(
                            float(target[slot_index, 2]),
                            float(target[slot_index, 3]),
                        )
                    ) % 360.0
                    relative_c = 1.0 / (
                        1.0 + math.exp(-float(target[slot_index, 1]))
                    )
                    slot_c = (
                        relative_c
                        * max_srgb_chroma_at(slot_l, slot_h)
                        * CHROMA_HEADROOM
                    )
                    locked_colors[slot_index] = np.asarray(
                        [
                            slot_l,
                            slot_c,
                            target[slot_index, 2],
                            target[slot_index, 3],
                        ],
                        dtype=np.float32,
                    )

            records["example_ids"].append(
                f"pb1-{source_index:06d}-{count}-{example_seed & 0xFFFF_FFFF:08x}"
            )
            records["source_indices"].append(source_index)
            records["texts"].append(text)
            records["embeddings"].append(source["embeddings"][source_index])
            records["counts"].append(count)
            records["seeds"].append(browser_seed)
            records["count_masks"].append(count_mask)
            records["seed_noise"].append(seed_noise)
            records["locked_masks"].append(locked_mask)
            records["locked_colors"].append(locked_colors)
            records["targets"].append(target)
            records["splits"].append(split_id)

    return {
        "example_ids": np.asarray(records["example_ids"]),
        "source_indices": np.asarray(records["source_indices"], dtype=np.int32),
        "texts": np.asarray(records["texts"]),
        "embeddings": np.asarray(records["embeddings"], dtype=np.float32),
        "counts": np.asarray(records["counts"], dtype=np.int64),
        "seeds": np.asarray(records["seeds"], dtype=np.uint32),
        "count_masks": np.asarray(records["count_masks"], dtype=np.float32),
        "seed_noise": np.asarray(records["seed_noise"], dtype=np.float32),
        "locked_masks": np.asarray(records["locked_masks"], dtype=np.float32),
        "locked_colors": np.asarray(records["locked_colors"], dtype=np.float32),
        "targets": np.asarray(records["targets"], dtype=np.float32),
        "splits": np.asarray(records["splits"], dtype=np.int8),
    }


def dataset_metadata(
    *,
    source_path: str,
    source_rows: int,
    example_count: int,
    counts: Iterable[int],
    split_seed: int,
    lock_probability: float,
) -> dict[str, Any]:
    return {
        "schemaVersion": DATASET_VERSION,
        "kind": "deterministic_synthetic_baseline",
        "synthesisVersion": SYNTHESIS_VERSION,
        "productionReady": False,
        "sourcePath": source_path,
        "sourceRows": int(source_rows),
        "exampleCount": int(example_count),
        "counts": list(int(count) for count in counts),
        "splitSeed": int(split_seed),
        "lockProbability": float(lock_probability),
        "embeddingDimension": EMBEDDING_DIM,
        "maxColors": MAX_COLORS,
        "seedNoiseAlgorithm": "Mulberry32+BoxMuller-slot-major-v1",
        "lockedColorRepresentation": [
            "L_physical",
            "C_physical",
            "sin_hue",
            "cos_hue",
        ],
        "targetRepresentation": [
            "L_logit",
            "relative_C_logit_against_runtime_gamut_max_times_0.92",
            "sin_hue",
            "cos_hue",
            "importance_0_to_1",
        ],
        "warning": (
            "Targets are deterministic procedural expansions of scalar intent "
            "labels. They are for pipeline validation, not production quality."
        ),
    }


def read_metadata(path: str | Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        if "metadata_json" not in archive.files:
            raise ValueError("dataset has no metadata_json")
        return json.loads(str(archive["metadata_json"].item()))


def validate_prepared_archive(archive: Mapping[str, np.ndarray]) -> dict[str, int]:
    """Validate the complete decoder tensor contract and group split isolation."""

    required = {
        "embeddings",
        "counts",
        "count_masks",
        "seed_noise",
        "locked_masks",
        "locked_colors",
        "targets",
        "splits",
    }
    missing = sorted(required.difference(archive.keys()))
    if missing:
        raise ValueError(f"prepared archive is missing arrays: {', '.join(missing)}")

    rows = int(archive["counts"].shape[0])
    expected_shapes = {
        "embeddings": (rows, EMBEDDING_DIM),
        "counts": (rows,),
        "count_masks": (rows, MAX_COLORS),
        "seed_noise": (rows, MAX_COLORS, 4),
        "locked_masks": (rows, MAX_COLORS),
        "locked_colors": (rows, MAX_COLORS, 4),
        "targets": (rows, MAX_COLORS, 5),
        "splits": (rows,),
    }
    for name, shape in expected_shapes.items():
        if archive[name].shape != shape:
            raise ValueError(f"{name} must have shape {shape}, got {archive[name].shape}")
    if rows == 0:
        raise ValueError("prepared archive must contain at least one row")

    counts = np.asarray(archive["counts"], dtype=np.int64)
    if np.any((counts < 2) | (counts > MAX_COLORS)):
        raise ValueError("counts must be in 2..9")
    masks = np.asarray(archive["count_masks"], dtype=np.float32)
    expected_masks = np.arange(MAX_COLORS)[None, :] < counts[:, None]
    if not np.array_equal(masks > 0.5, expected_masks):
        raise ValueError("count_masks must activate exactly the leading count slots")
    locked_masks = np.asarray(archive["locked_masks"], dtype=np.float32)
    if np.any((locked_masks > 0.5) & ~expected_masks):
        raise ValueError("locked_masks may not lock an inactive slot")

    for name in ("embeddings", "seed_noise", "locked_colors", "targets"):
        if not np.isfinite(archive[name]).all():
            raise ValueError(f"{name} contains a non-finite value")
    embedding_norms = np.linalg.norm(archive["embeddings"], axis=1)
    if float(np.max(np.abs(embedding_norms - 1.0))) > 5e-3:
        raise ValueError("embeddings must be L2 normalized")
    inactive = ~expected_masks
    if np.any(np.abs(archive["targets"][inactive]) > 1e-7):
        raise ValueError("inactive targets must be exactly zero")
    if np.any(np.abs(archive["locked_colors"][locked_masks <= 0.5]) > 1e-7):
        raise ValueError("unlocked physical lock inputs must be exactly zero")
    if not set(np.unique(archive["splits"]).tolist()).issubset(set(SPLIT_IDS.values())):
        raise ValueError("splits contain an unknown split id")

    if "quality_weights" in archive:
        weights = np.asarray(archive["quality_weights"], dtype=np.float32)
        if weights.shape != (rows,) or not np.isfinite(weights).all() or np.any(weights <= 0):
            raise ValueError("quality_weights must be finite positive [N] values")

    if "source_group_ids" in archive:
        group_ids = np.asarray(archive["source_group_ids"])
        if group_ids.shape != (rows,):
            raise ValueError("source_group_ids must have shape [N]")
        group_splits: dict[str, int] = {}
        for group_id, split_id in zip(group_ids, archive["splits"], strict=True):
            key = str(group_id)
            current = int(split_id)
            previous = group_splits.setdefault(key, current)
            if previous != current:
                raise ValueError(f"source group crosses splits: {key}")

    return {
        "rows": rows,
        "train": int(np.sum(archive["splits"] == SPLIT_IDS["train"])),
        "val": int(np.sum(archive["splits"] == SPLIT_IDS["val"])),
        "test": int(np.sum(archive["splits"] == SPLIT_IDS["test"])),
    }


class PaletteBrainDataset(Dataset):  # type: ignore[misc]
    """PyTorch view over a prepared PaletteBrain NPZ split."""

    def __init__(
        self,
        path: str | Path,
        split: str,
        *,
        max_samples: int | None = None,
    ) -> None:
        if torch is None:
            raise RuntimeError("PyTorch is required to use PaletteBrainDataset")
        if split not in SPLIT_IDS:
            raise ValueError(f"unknown split {split!r}")
        with np.load(path, allow_pickle=False) as archive:
            validate_prepared_archive({name: archive[name] for name in archive.files})
            indices = np.flatnonzero(archive["splits"] == SPLIT_IDS[split])
            if max_samples is not None:
                indices = indices[: max(0, int(max_samples))]
            self.metadata = json.loads(str(archive["metadata_json"].item()))
            self.arrays = {
                name: np.asarray(archive[name][indices])
                for name in (
                    "embeddings",
                    "counts",
                    "seeds",
                    "count_masks",
                    "seed_noise",
                    "locked_masks",
                    "locked_colors",
                    "targets",
                )
            }
            if "quality_weights" in archive.files:
                self.arrays["quality_weights"] = np.asarray(
                    archive["quality_weights"][indices], dtype=np.float32
                )
            else:
                self.arrays["quality_weights"] = np.ones(
                    len(indices), dtype=np.float32
                )

    def __len__(self) -> int:
        return int(self.arrays["counts"].shape[0])

    def __getitem__(self, index: int) -> dict[str, Any]:
        assert torch is not None
        return {
            "text_embedding": torch.as_tensor(
                self.arrays["embeddings"][index], dtype=torch.float32
            ),
            "count": torch.as_tensor(
                self.arrays["counts"][index], dtype=torch.int64
            ),
            "seed": torch.as_tensor(
                int(self.arrays["seeds"][index]), dtype=torch.int64
            ),
            "count_mask": torch.as_tensor(
                self.arrays["count_masks"][index], dtype=torch.float32
            ),
            "seed_noise": torch.as_tensor(
                self.arrays["seed_noise"][index], dtype=torch.float32
            ),
            "locked_mask": torch.as_tensor(
                self.arrays["locked_masks"][index], dtype=torch.float32
            ),
            "locked_colors": torch.as_tensor(
                self.arrays["locked_colors"][index], dtype=torch.float32
            ),
            "target": torch.as_tensor(
                self.arrays["targets"][index], dtype=torch.float32
            ),
            "quality_weight": torch.as_tensor(
                self.arrays["quality_weights"][index], dtype=torch.float32
            ),
        }

    @property
    def sampling_weights(self) -> np.ndarray:
        return np.asarray(self.arrays["quality_weights"], dtype=np.float64)
