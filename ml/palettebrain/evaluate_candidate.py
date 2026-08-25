"""Serious, frozen-fixture evaluation for a PaletteBrain candidate checkpoint.

The evaluator intentionally exercises the raw decoder contract.  It never
restores locks, clips model colors, repairs direct-color prompts, removes near
duplicates, or otherwise post-processes a prediction before scoring it.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import sys
import time
from typing import Any

import numpy as np

try:
    from .color_math import (
        is_in_srgb_gamut,
        oklch_to_srgb,
        representation_to_oklab_numpy,
    )
    from .dataset import (
        MAX_COLORS,
        SPLIT_IDS,
        seed_noise_from_uint32,
        validate_prepared_archive,
    )
    from .release_metrics import (
        aggregate_direct_prompt_scores,
        hungarian_matched_distances,
        hungarian_matched_set_distance,
        load_color_family_fixture,
        load_semantic_release_fixture,
        near_duplicate_palette_rate,
        score_direct_prompt,
        summarize_matched_set_distances,
        summarize_modifier_sensitivity,
        summarize_ru_en_parity,
    )
except ImportError:  # Support ``python ml/palettebrain/evaluate_candidate.py``.
    from color_math import (  # type: ignore[no-redef]
        is_in_srgb_gamut,
        oklch_to_srgb,
        representation_to_oklab_numpy,
    )
    from dataset import (  # type: ignore[no-redef]
        MAX_COLORS,
        SPLIT_IDS,
        seed_noise_from_uint32,
        validate_prepared_archive,
    )
    from release_metrics import (  # type: ignore[no-redef]
        aggregate_direct_prompt_scores,
        hungarian_matched_distances,
        hungarian_matched_set_distance,
        load_color_family_fixture,
        load_semantic_release_fixture,
        near_duplicate_palette_rate,
        score_direct_prompt,
        summarize_matched_set_distances,
        summarize_modifier_sensitivity,
        summarize_ru_en_parity,
    )


PACKAGE_DIR = Path(__file__).resolve().parent
COLOR_FIXTURE_PATH = PACKAGE_DIR / "benchmark_color_families.v1.json"
SEMANTIC_FIXTURE_PATH = PACKAGE_DIR / "benchmark_semantic_release.v1.json"
COVERAGE_FIXTURE_PATH = PACKAGE_DIR / "benchmark_prompts.v1.json"
EVALUATION_CONFIG_PATH = PACKAGE_DIR / "reports" / "evaluation-freeze.v1.json"
E5_PARITY_REPORT_PATH = PACKAGE_DIR / "reports" / "e5-parity.v1.json"
REPORT_SCHEMA_VERSION = 1
REAL_PALETTE_ORIGINS = frozenset({"human_curated", "human_curated_extracted"})
NON_REAL_SOURCES = frozenset({"direct_anchors", "legacy_synthetic"})


@dataclass(frozen=True, order=True)
class GenerationRequest:
    """One native decoder request identified by semantic and stochastic inputs."""

    prompt: str
    seed: int
    count: int


@dataclass
class LoadedCandidate:
    """A model plus the safe metadata loaded from its checkpoint."""

    model: Any
    checkpoint: Mapping[str, Any]


EmbeddingProvider = Callable[[Sequence[str]], np.ndarray]
ModelLoader = Callable[[Path, str], LoadedCandidate]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json_object(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON fixture must contain an object: {path}")
    return value


def _unique_strings(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value).strip()
        if not value:
            raise ValueError("frozen benchmark contains an empty prompt")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def collect_benchmark_texts(
    color_fixture: Mapping[str, Any],
    semantic_fixture: Mapping[str, Any],
    coverage_fixture: Mapping[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Collect and de-duplicate every text that the frozen release metrics use."""

    direct_cases = color_fixture.get("prompts")
    if not isinstance(direct_cases, Sequence):
        raise ValueError("color fixture prompts must be an array")
    direct = _unique_strings([case["prompt"] for case in direct_cases])

    modifier_values = [
        prompt
        for pair in semantic_fixture.get("modifierPairs", [])
        for prompt in pair
    ]
    translation_values = [
        prompt
        for pair in semantic_fixture.get("translationPairs", [])
        for prompt in pair
    ]
    sanity_values = semantic_fixture.get(
        "requiredSanityOutputs", semantic_fixture.get("sanityPrompts", [])
    )
    if not isinstance(sanity_values, Sequence) or isinstance(sanity_values, str):
        raise ValueError("semantic fixture sanity prompts must be an array")
    modifier = _unique_strings(modifier_values)
    translation = _unique_strings(translation_values)
    sanity = _unique_strings(list(sanity_values))
    group_values = [
        prompt
        for prompts in semantic_fixture.get("groups", {}).values()
        for prompt in prompts
    ]
    semantic_groups = _unique_strings(group_values)
    coverage_values: list[Any] = []
    if coverage_fixture is not None:
        cases = coverage_fixture.get("prompts", [])
        if not isinstance(cases, Sequence) or isinstance(cases, str):
            raise ValueError("coverage fixture prompts must be an array")
        coverage_values = [case["prompt"] for case in cases]
    coverage = _unique_strings(coverage_values)
    all_prompts = _unique_strings(
        direct + modifier + translation + sanity + semantic_groups + coverage
    )
    return {
        "direct": direct,
        "modifier": modifier,
        "translation": translation,
        "sanity": sanity,
        "semanticGroups": semantic_groups,
        "coverage": coverage,
        "all": all_prompts,
    }


def _frozen_seeds(*fixtures: Mapping[str, Any]) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    for fixture in fixtures:
        raw_seeds = fixture.get("seeds", [])
        if not isinstance(raw_seeds, Sequence):
            raise ValueError("fixture seeds must be an array")
        for raw_seed in raw_seeds:
            seed = int(raw_seed)
            if not 0 <= seed <= 0xFFFF_FFFF:
                raise ValueError("frozen seeds must be uint32 values")
            if seed not in seen:
                seen.add(seed)
                ordered.append(seed)
    if len(ordered) < 2:
        raise ValueError("serious seed evaluation requires at least two frozen seeds")
    return ordered


def build_generation_requests(
    prompts: Sequence[str], seeds: Sequence[int]
) -> list[GenerationRequest]:
    """Exercise every frozen prompt and seed at every supported native count."""

    return [
        GenerationRequest(prompt=prompt, seed=int(seed), count=count)
        for prompt in prompts
        for seed in seeds
        for count in range(2, MAX_COLORS + 1)
    ]


def _resolve_device(requested: str) -> str:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - serious environment only
        raise RuntimeError("PyTorch is required for candidate evaluation") from exc
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return str(device)


def load_checkpoint_candidate(path: Path, device: str) -> LoadedCandidate:
    """Load the repository's decoder checkpoint without allowing arbitrary pickle."""

    try:
        import torch
        try:
            from .model import PaletteDecoder, PaletteDecoderConfig
        except ImportError:
            from model import PaletteDecoder, PaletteDecoderConfig  # type: ignore
    except ImportError as exc:  # pragma: no cover - serious environment only
        raise RuntimeError("PyTorch is required for candidate evaluation") from exc

    checkpoint = torch.load(path, map_location=device, weights_only=True)
    if not isinstance(checkpoint, Mapping):
        raise ValueError("checkpoint must contain a metadata mapping")
    if "model_config" not in checkpoint or "model_state_dict" not in checkpoint:
        raise ValueError("checkpoint is missing model_config or model_state_dict")
    config = PaletteDecoderConfig(**checkpoint["model_config"])
    model = PaletteDecoder(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()
    return LoadedCandidate(model=model, checkpoint=checkpoint)


def make_pinned_e5_provider(
    *, device: str, cache_dir: str | Path
) -> tuple[EmbeddingProvider, dict[str, Any]]:
    """Load the pinned E5 path lazily so injected unit tests never load E5."""

    try:
        from .e5_embedding import (
            BROWSER_E5_MODEL_ID,
            BROWSER_E5_REVISION,
            BROWSER_E5_SHA256,
            E5_MODEL_ID,
            E5_REVISION,
            EMBEDDING_DIMENSION,
            MAX_CONTEXT_TOKENS,
            QUERY_PREFIX,
            embed_texts,
            load_encoder,
        )
    except ImportError:
        from e5_embedding import (  # type: ignore[no-redef]
            BROWSER_E5_MODEL_ID,
            BROWSER_E5_REVISION,
            BROWSER_E5_SHA256,
            E5_MODEL_ID,
            E5_REVISION,
            EMBEDDING_DIMENSION,
            MAX_CONTEXT_TOKENS,
            QUERY_PREFIX,
            embed_texts,
            load_encoder,
        )

    encoder = load_encoder(
        device=device,
        cache_dir=cache_dir,
        local_files_only=True,
    )

    def provider(texts: Sequence[str]) -> np.ndarray:
        return embed_texts(texts, encoder=encoder)

    metadata = {
        "provider": "pinned_pytorch_e5",
        "modelId": E5_MODEL_ID,
        "revision": E5_REVISION,
        "browserModelId": BROWSER_E5_MODEL_ID,
        "browserRevision": BROWSER_E5_REVISION,
        "browserArtifactSha256": BROWSER_E5_SHA256,
        "dimension": EMBEDDING_DIMENSION,
        "queryPrefix": QUERY_PREFIX,
        "maximumContextTokens": MAX_CONTEXT_TOKENS,
        "pooling": "attention-mask mean pooling followed by L2 normalization",
        "device": str(encoder.device),
        "cacheDirectory": str(Path(cache_dir).as_posix()),
        "localFilesOnly": True,
    }
    return provider, metadata


def _prepare_model(model: Any, device: str) -> Any:
    if hasattr(model, "to"):
        model = model.to(device)
    if hasattr(model, "eval"):
        model = model.eval()
    return model


def _extract_model_output(value: Any) -> Any:
    if isinstance(value, Mapping):
        if "palette" not in value:
            raise ValueError("decoder output mapping has no 'palette' value")
        return value["palette"]
    if isinstance(value, (tuple, list)):
        if len(value) != 1:
            raise ValueError("decoder must return one palette tensor")
        return value[0]
    return value


def run_raw_decoder(
    model: Any,
    embeddings: np.ndarray,
    counts: np.ndarray,
    seeds: np.ndarray,
    *,
    device: str,
    batch_size: int = 256,
    count_masks: np.ndarray | None = None,
    seed_noise: np.ndarray | None = None,
    locked_masks: np.ndarray | None = None,
    locked_colors: np.ndarray | None = None,
) -> np.ndarray:
    """Run the decoder's native nine-slot output without any runtime guard."""

    try:
        import torch
    except ImportError as exc:  # pragma: no cover - serious environment only
        raise RuntimeError("PyTorch is required for decoder inference") from exc
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    embeddings = np.asarray(embeddings, dtype=np.float32)
    counts = np.asarray(counts, dtype=np.int64)
    seeds = np.asarray(seeds, dtype=np.uint64)
    rows = len(counts)
    if embeddings.shape != (rows, 384):
        raise ValueError(f"embeddings must have shape ({rows}, 384)")
    if seeds.shape != (rows,):
        raise ValueError("seeds must have shape [N]")
    if np.any((counts < 2) | (counts > MAX_COLORS)):
        raise ValueError("requested counts must be in 2..9")

    expected_masks = (
        np.arange(MAX_COLORS, dtype=np.int64)[None, :] < counts[:, None]
    ).astype(np.float32)
    if count_masks is None:
        count_masks = expected_masks
    else:
        count_masks = np.asarray(count_masks, dtype=np.float32)
        if count_masks.shape != (rows, MAX_COLORS):
            raise ValueError("count_masks must have shape [N, 9]")
        if not np.array_equal(count_masks > 0.5, expected_masks > 0.5):
            raise ValueError("count_masks must natively activate the requested count")
    if seed_noise is None:
        seed_noise = np.stack(
            [seed_noise_from_uint32(int(seed)) for seed in seeds], axis=0
        )
    else:
        seed_noise = np.asarray(seed_noise, dtype=np.float32)
    if seed_noise.shape != (rows, MAX_COLORS, 4):
        raise ValueError("seed_noise must have shape [N, 9, 4]")
    if locked_masks is None:
        locked_masks = np.zeros((rows, MAX_COLORS), dtype=np.float32)
    else:
        locked_masks = np.asarray(locked_masks, dtype=np.float32)
    if locked_colors is None:
        locked_colors = np.zeros((rows, MAX_COLORS, 4), dtype=np.float32)
    else:
        locked_colors = np.asarray(locked_colors, dtype=np.float32)
    if locked_masks.shape != (rows, MAX_COLORS):
        raise ValueError("locked_masks must have shape [N, 9]")
    if locked_colors.shape != (rows, MAX_COLORS, 4):
        raise ValueError("locked_colors must have shape [N, 9, 4]")

    outputs: list[np.ndarray] = []
    model = _prepare_model(model, device)
    with torch.inference_mode():
        for start in range(0, rows, batch_size):
            stop = min(rows, start + batch_size)
            output = model(
                text_embedding=torch.as_tensor(
                    embeddings[start:stop], dtype=torch.float32, device=device
                ),
                count_mask=torch.as_tensor(
                    count_masks[start:stop], dtype=torch.float32, device=device
                ),
                seed_noise=torch.as_tensor(
                    seed_noise[start:stop], dtype=torch.float32, device=device
                ),
                locked_mask=torch.as_tensor(
                    locked_masks[start:stop], dtype=torch.float32, device=device
                ),
                locked_colors=torch.as_tensor(
                    locked_colors[start:stop], dtype=torch.float32, device=device
                ),
            )
            output = _extract_model_output(output)
            if not hasattr(output, "detach"):
                raise ValueError("decoder output must be a tensor")
            values = output.detach().float().cpu().numpy()
            if values.ndim != 3 or values.shape[1] != MAX_COLORS:
                raise ValueError("decoder output must have shape [B, 9, channels]")
            if values.shape[2] < 4:
                raise ValueError("decoder output must contain at least four channels")
            outputs.append(values)
    if not outputs:
        return np.empty((0, MAX_COLORS, 5), dtype=np.float32)
    return np.concatenate(outputs, axis=0).astype(np.float32, copy=False)


def _decode_active_rows(
    raw: np.ndarray, counts: np.ndarray
) -> list[np.ndarray | None]:
    """Decode valid active slots; invalid rows remain invalid rather than repaired."""

    result: list[np.ndarray | None] = []
    for row, count in zip(raw, counts, strict=True):
        active_raw = row[: int(count)]
        if not np.isfinite(active_raw).all():
            result.append(None)
            continue
        physical = representation_to_oklab_numpy(active_raw[None, ...])[0]
        if not np.isfinite(physical).all():
            result.append(None)
            continue
        result.append(np.asarray(physical, dtype=np.float64))
    return result


def _oklab_to_oklch(palette: np.ndarray) -> np.ndarray:
    palette = np.asarray(palette, dtype=np.float64)
    chroma = np.linalg.norm(palette[:, 1:3], axis=1)
    hue = np.degrees(np.arctan2(palette[:, 2], palette[:, 1])) % 360.0
    hue = np.where(chroma > 1e-12, hue, 0.0)
    return np.column_stack((palette[:, 0], chroma, hue))


def _palette_is_in_gamut(palette: np.ndarray | None) -> bool:
    if palette is None:
        return False
    return all(
        is_in_srgb_gamut(float(lightness), float(chroma), float(hue))
        for lightness, chroma, hue in _oklab_to_oklch(palette)
    )


def _rate(values: Sequence[bool]) -> float | None:
    return sum(bool(value) for value in values) / len(values) if values else None


def summarize_engineering_contract(
    requests: Sequence[GenerationRequest],
    raw: np.ndarray,
    repeated_raw: np.ndarray,
    palettes: Sequence[np.ndarray | None],
) -> dict[str, Any]:
    """Report exact native slot behavior separately for every count 2..9."""

    if len(requests) != len(raw) or raw.shape != repeated_raw.shape:
        raise ValueError("engineering inputs must describe the same requests")
    rows: list[dict[str, Any]] = []
    for index, request in enumerate(requests):
        expected = np.arange(MAX_COLORS) < request.count
        predicted_active = np.any(raw[index] != 0.0, axis=-1)
        inactive_values = raw[index, ~expected]
        active_values = raw[index, expected]
        rows.append(
            {
                "count": request.count,
                "exact_count": bool(predicted_active.sum() == request.count),
                "mask_exact": bool(np.array_equal(predicted_active, expected)),
                "inactive_exact": bool(
                    inactive_values.size == 0 or np.all(inactive_values == 0.0)
                ),
                "inactive_abs_max": (
                    float(np.max(np.abs(inactive_values)))
                    if inactive_values.size and np.isfinite(inactive_values).all()
                    else (None if inactive_values.size else 0.0)
                ),
                "finite_active": bool(np.isfinite(active_values).all()),
                "gamut": _palette_is_in_gamut(palettes[index]),
                "deterministic": bool(np.array_equal(raw[index], repeated_raw[index])),
            }
        )

    def summarize(selected: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        inactive_maxima = [
            float(row["inactive_abs_max"])
            for row in selected
            if row["inactive_abs_max"] is not None
        ]
        return {
            "requestCount": len(selected),
            "exactCountRate": _rate([bool(row["exact_count"]) for row in selected]),
            "exactActiveMaskRate": _rate([bool(row["mask_exact"]) for row in selected]),
            "inactiveExactZeroRate": _rate(
                [bool(row["inactive_exact"]) for row in selected]
            ),
            "inactiveOutputAbsMax": max(inactive_maxima, default=None),
            "finiteActiveRate": _rate(
                [bool(row["finite_active"]) for row in selected]
            ),
            "srgbGamutPaletteRate": _rate([bool(row["gamut"]) for row in selected]),
            "sameSeedExactDeterminismRate": _rate(
                [bool(row["deterministic"]) for row in selected]
            ),
        }

    by_count = {
        str(count): summarize([row for row in rows if row["count"] == count])
        for count in range(2, MAX_COLORS + 1)
    }
    return {
        "rawDecoder": True,
        "runtimeColorGuardApplied": False,
        "postCorrectionApplied": False,
        "overall": summarize(rows),
        "byCount": by_count,
    }


def _invalid_direct_score(
    prompt_case: Mapping[str, Any], seed: int
) -> dict[str, Any]:
    return {
        "id": prompt_case.get("id"),
        "prompt": prompt_case.get("prompt"),
        "language": prompt_case.get("language"),
        "required": list(prompt_case.get("required", [])),
        "excluded": list(prompt_case.get("excluded", [])),
        "standalone": bool(prompt_case.get("standalone", False)),
        "seed": seed,
        "passed": False,
        "required_passed": False,
        "exclusion_passed": False,
        "consistency_passed": False,
        "error": "non_finite_raw_decoder_output",
    }


def evaluate_direct_predictions(
    color_fixture: Mapping[str, Any],
    seeds: Sequence[int],
    default_count: int,
    palette_by_request: Mapping[GenerationRequest, np.ndarray | None],
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for prompt_case in color_fixture["prompts"]:
        prompt = str(prompt_case["prompt"])
        for seed in seeds:
            palette = palette_by_request[
                GenerationRequest(prompt, int(seed), default_count)
            ]
            if palette is None:
                sample = _invalid_direct_score(prompt_case, int(seed))
            else:
                sample = score_direct_prompt(
                    palette,
                    prompt_case,
                    fixture=color_fixture,
                    color_space="oklab",
                )
                sample["seed"] = int(seed)
            samples.append(sample)
    aggregate = aggregate_direct_prompt_scores(samples)

    def decision_summary(
        rows: Sequence[Mapping[str, Any]], key: str
    ) -> dict[str, Any]:
        values = [bool(row.get(key, False)) for row in rows]
        passed = sum(values)
        return {
            "total": len(values),
            "passed": passed,
            "failed": len(values) - passed,
            "accuracy": passed / len(values) if values else None,
        }

    required_rows = [sample for sample in samples if sample.get("required")]
    standalone_rows = [sample for sample in samples if sample.get("standalone")]
    aggregate["required_family"] = decision_summary(
        required_rows, "required_passed"
    )
    aggregate["standalone_consistency"] = decision_summary(
        standalone_rows, "consistency_passed"
    )
    return {
        "rawDecoder": True,
        "defaultCount": default_count,
        "seeds": [int(seed) for seed in seeds],
        "samples": samples,
        "aggregate": aggregate,
    }


def summarize_seed_behavior(
    prompts: Sequence[str],
    seeds: Sequence[int],
    default_count: int,
    palette_by_request: Mapping[GenerationRequest, np.ndarray | None],
    direct_report: Mapping[str, Any],
    determinism_rate: float | None,
) -> dict[str, Any]:
    pair_rows: list[dict[str, Any]] = []
    invalid_pairs = 0
    for prompt in prompts:
        distances: list[float] = []
        samples: list[dict[str, Any]] = []
        for left_seed, right_seed in itertools.combinations(seeds, 2):
            left = palette_by_request[
                GenerationRequest(prompt, int(left_seed), default_count)
            ]
            right = palette_by_request[
                GenerationRequest(prompt, int(right_seed), default_count)
            ]
            if left is None or right is None:
                invalid_pairs += 1
                continue
            distance = hungarian_matched_set_distance(left, right)
            distances.append(distance)
            samples.append(
                {
                    "leftSeed": int(left_seed),
                    "rightSeed": int(right_seed),
                    "distance": distance,
                }
            )
        pair_rows.append(
            {
                "prompt": prompt,
                "pairCount": len(samples),
                "meanDistance": float(np.mean(distances)) if distances else None,
                "medianDistance": float(np.median(distances)) if distances else None,
                "samples": samples,
            }
        )
    all_distances = [
        float(sample["distance"])
        for row in pair_rows
        for sample in row["samples"]
    ]

    required_samples = [
        sample
        for sample in direct_report["samples"]
        if sample.get("required")
    ]
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for sample in required_samples:
        grouped[str(sample.get("id"))].append(sample)
    anchor_rows = []
    for prompt_id, samples in sorted(grouped.items()):
        required_passes = [bool(sample.get("required_passed")) for sample in samples]
        full_passes = [bool(sample.get("passed")) for sample in samples]
        anchor_rows.append(
            {
                "promptId": prompt_id,
                "prompt": samples[0].get("prompt"),
                "seedCount": len(samples),
                "requiredFamilyRetentionRate": _rate(required_passes),
                "requiredFamilyStableAcrossAllSeeds": all(required_passes),
                "fullDirectPassRate": _rate(full_passes),
                "fullDirectStableAcrossAllSeeds": all(full_passes),
            }
        )

    return {
        "sameSeed": {
            "definition": "exact ordered equality of repeated raw 9-slot tensors",
            "exactEqualityRate": determinism_rate,
        },
        "crossSeed": {
            "definition": "physical Hungarian mean OKLab set distance",
            "promptCount": len(pair_rows),
            "evaluatedPairCount": len(all_distances),
            "invalidPairCount": invalid_pairs,
            "meanDistance": (
                float(np.mean(all_distances)) if all_distances else None
            ),
            "medianDistance": (
                float(np.median(all_distances)) if all_distances else None
            ),
            "perPrompt": pair_rows,
        },
        "explicitAnchorStability": {
            "promptCount": len(anchor_rows),
            "allSeedRequiredFamilyStableRate": _rate(
                [
                    bool(row["requiredFamilyStableAcrossAllSeeds"])
                    for row in anchor_rows
                ]
            ),
            "requiredFamilyRetentionRate": _rate(
                [bool(sample.get("required_passed")) for sample in required_samples]
            ),
            "perPrompt": anchor_rows,
        },
    }


def _byte_from_unit(value: float) -> int:
    clipped = min(1.0, max(0.0, value))
    return min(255, max(0, int(math.floor(clipped * 255.0 + 0.5))))


def palette_to_hex(palette: np.ndarray) -> list[str]:
    """Render already-scored physical colors; clipping is display-only."""

    result: list[str] = []
    for lightness, chroma, hue in _oklab_to_oklch(palette):
        red, green, blue = oklch_to_srgb(
            float(lightness), float(chroma), float(hue)
        )
        result.append(
            f"#{_byte_from_unit(red):02X}{_byte_from_unit(green):02X}{_byte_from_unit(blue):02X}"
        )
    return result


def build_sanity_outputs(
    sanity_prompts: Sequence[str],
    predetermined_seed: int,
    default_count: int,
    palette_by_request: Mapping[GenerationRequest, np.ndarray | None],
) -> dict[str, Any]:
    rows = []
    for prompt in sanity_prompts:
        palette = palette_by_request[
            GenerationRequest(prompt, predetermined_seed, default_count)
        ]
        rows.append(
            {
                "prompt": prompt,
                "hex": palette_to_hex(palette) if palette is not None else None,
                "validRawOutput": palette is not None,
            }
        )
    return {
        "selectionPolicy": "first seed in the frozen semantic fixture",
        "seed": predetermined_seed,
        "count": default_count,
        "palettes": rows,
    }


def _string_counter(values: np.ndarray) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values.tolist()).items()))


def select_real_holdout_mask(
    archive: Mapping[str, np.ndarray]
) -> tuple[np.ndarray, dict[str, Any]]:
    """Select the prepared test holdout without synthetic/direct-anchor leakage."""

    if "splits" not in archive:
        raise ValueError("prepared data has no splits array")
    splits = np.asarray(archive["splits"])
    if splits.ndim != 1:
        raise ValueError("splits must have shape [N]")
    test = splits == SPLIT_IDS["test"]
    provenance = np.ones_like(test, dtype=bool)
    provenance_available = False
    if "palette_origins" in archive:
        origins = np.asarray(archive["palette_origins"]).astype(str)
        if origins.shape != test.shape:
            raise ValueError("palette_origins must have shape [N]")
        provenance &= np.isin(origins, list(REAL_PALETTE_ORIGINS))
        provenance_available = True
    if "sources" in archive:
        sources = np.asarray(archive["sources"]).astype(str)
        if sources.shape != test.shape:
            raise ValueError("sources must have shape [N]")
        provenance &= ~np.isin(sources, list(NON_REAL_SOURCES))
        provenance_available = True

    mode: str
    eligible_provenance_violations = np.zeros_like(test, dtype=bool)
    if "holdout_eligible" in archive:
        eligible = np.asarray(archive["holdout_eligible"], dtype=bool)
        if eligible.shape != test.shape:
            raise ValueError("holdout_eligible must have shape [N]")
        eligible_provenance_violations = test & eligible & ~provenance
        selected = test & eligible & provenance
        mode = "holdout_eligible_provenance_and_test_split"
    elif provenance_available:
        selected = test & provenance
        mode = "palette_origin_and_source_fallback"
    else:
        selected = test
        mode = "unfiltered_test_split_no_provenance_arrays"
    return selected, {
        "selectionMode": mode,
        "provenanceFilteringAvailable": provenance_available,
        "eligibleProvenanceViolationRows": int(
            eligible_provenance_violations.sum()
        ),
        "provenanceIntegrityPassed": bool(
            provenance_available and not eligible_provenance_violations.any()
        ),
        "testRows": int(test.sum()),
        "selectedRows": int(selected.sum()),
        "excludedTestRows": int((test & ~selected).sum()),
        "allowedPaletteOrigins": sorted(REAL_PALETTE_ORIGINS),
        "excludedSources": sorted(NON_REAL_SOURCES),
    }


def _lightness_distribution_summary(
    predicted: Sequence[np.ndarray], target: Sequence[np.ndarray]
) -> dict[str, Any]:
    errors = [
        float(np.mean(np.abs(np.sort(left[:, 0]) - np.sort(right[:, 0]))))
        for left, right in zip(predicted, target, strict=True)
    ]
    return {
        "definition": "mean absolute error between sorted physical OKLab lightness values",
        "paletteCount": len(errors),
        "meanError": float(np.mean(errors)) if errors else None,
        "medianError": float(np.median(errors)) if errors else None,
        "perPaletteErrors": errors,
    }


def _locked_color_to_oklab(color: np.ndarray) -> np.ndarray:
    lightness, chroma, hue_sin, hue_cos = map(float, color[:4])
    norm = math.hypot(hue_sin, hue_cos)
    if norm < 1e-8 or chroma <= 0.0:
        return np.asarray([lightness, 0.0, 0.0], dtype=np.float64)
    return np.asarray(
        [
            lightness,
            chroma * hue_cos / norm,
            chroma * hue_sin / norm,
        ],
        dtype=np.float64,
    )


def _empty_holdout_report(selection: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "selection": dict(selection),
        "status": "no_real_holdout_rows",
        "rawUnconditioned": True,
        "runtimeLockGuardApplied": False,
        "validPredictionRows": 0,
        "invalidPredictionRows": 0,
        "validPredictionRate": None,
        "matchedOklab": {
            "palette_count": 0,
            "matched_color_count": 0,
            "mean_distance": None,
            "median_distance": None,
            "mean_set_distance": None,
            "set_distances": [],
            "matched_distances": [],
        },
        "lightnessDistribution": _lightness_distribution_summary([], []),
        "learnedLockCompletion": {
            "status": "no_locked_real_holdout_rows",
            "runtimeLockGuardApplied": False,
            "caseCount": 0,
            "lockedSlotCount": 0,
        },
    }


def evaluate_real_holdout(
    model: Any,
    data_path: str | Path,
    *,
    device: str,
    batch_size: int,
    duplicate_threshold: float,
) -> dict[str, Any]:
    """Evaluate target palettes unconditioned; score learned locks separately."""

    with np.load(data_path, allow_pickle=False) as loaded:
        archive = {name: np.asarray(loaded[name]) for name in loaded.files}
    selected_mask, selection = select_real_holdout_mask(archive)
    indices = np.flatnonzero(selected_mask)
    if not len(indices):
        return _empty_holdout_report(selection)

    required = {
        "embeddings",
        "counts",
        "seeds",
        "count_masks",
        "seed_noise",
        "locked_masks",
        "locked_colors",
        "targets",
    }
    missing = sorted(required.difference(archive))
    if missing:
        raise ValueError(f"prepared holdout is missing arrays: {', '.join(missing)}")

    counts = np.asarray(archive["counts"][indices], dtype=np.int64)
    count_masks = np.asarray(archive["count_masks"][indices], dtype=np.float32)
    seeds = np.asarray(archive["seeds"][indices], dtype=np.uint64)
    embeddings = np.asarray(archive["embeddings"][indices], dtype=np.float32)
    seed_noise = np.asarray(archive["seed_noise"][indices], dtype=np.float32)
    archived_locks = np.asarray(archive["locked_masks"][indices], dtype=np.float32)
    archived_locked_colors = np.asarray(
        archive["locked_colors"][indices], dtype=np.float32
    )
    targets_raw = np.asarray(archive["targets"][indices], dtype=np.float32)

    zero_locks = np.zeros_like(archived_locks)
    zero_locked_colors = np.zeros_like(archived_locked_colors)
    predicted_raw = run_raw_decoder(
        model,
        embeddings,
        counts,
        seeds,
        device=device,
        batch_size=batch_size,
        count_masks=count_masks,
        seed_noise=seed_noise,
        locked_masks=zero_locks,
        locked_colors=zero_locked_colors,
    )
    predicted_rows = _decode_active_rows(predicted_raw, counts)
    target_rows = _decode_active_rows(targets_raw, counts)
    valid_indices = [
        index
        for index, (predicted, target) in enumerate(
            zip(predicted_rows, target_rows, strict=True)
        )
        if predicted is not None and target is not None
    ]
    valid_predictions = [predicted_rows[index] for index in valid_indices]
    valid_targets = [target_rows[index] for index in valid_indices]
    typed_predictions = [
        np.asarray(value, dtype=np.float64) for value in valid_predictions
    ]
    typed_targets = [np.asarray(value, dtype=np.float64) for value in valid_targets]
    matched = summarize_matched_set_distances(typed_predictions, typed_targets)
    lightness = _lightness_distribution_summary(typed_predictions, typed_targets)

    provenance: dict[str, Any] = {}
    for name in (
        "sources",
        "palette_origins",
        "text_origins",
        "prompt_kinds",
        "semantic_alignments",
        "licenses",
    ):
        if name in archive:
            provenance[name] = _string_counter(np.asarray(archive[name][indices]))
    for name in ("native_counts", "derived_counts", "holdout_eligible"):
        if name in archive:
            values = np.asarray(archive[name][indices])
            provenance[name] = _string_counter(values)

    locked_case_local_indices = np.flatnonzero(
        np.any(archived_locks > 0.5, axis=1)
    )
    learned_locks: dict[str, Any]
    if len(locked_case_local_indices):
        locked_raw = run_raw_decoder(
            model,
            embeddings[locked_case_local_indices],
            counts[locked_case_local_indices],
            seeds[locked_case_local_indices],
            device=device,
            batch_size=batch_size,
            count_masks=count_masks[locked_case_local_indices],
            seed_noise=seed_noise[locked_case_local_indices],
            locked_masks=archived_locks[locked_case_local_indices],
            locked_colors=archived_locked_colors[locked_case_local_indices],
        )
        repeated_locked_raw = run_raw_decoder(
            model,
            embeddings[locked_case_local_indices],
            counts[locked_case_local_indices],
            seeds[locked_case_local_indices],
            device=device,
            batch_size=batch_size,
            count_masks=count_masks[locked_case_local_indices],
            seed_noise=seed_noise[locked_case_local_indices],
            locked_masks=archived_locks[locked_case_local_indices],
            locked_colors=archived_locked_colors[locked_case_local_indices],
        )
        locked_predictions = _decode_active_rows(
            locked_raw, counts[locked_case_local_indices]
        )
        locked_targets = _decode_active_rows(
            targets_raw[locked_case_local_indices],
            counts[locked_case_local_indices],
        )
        locked_slot_distances: list[float] = []
        completion_set_distances: list[float] = []
        full_set_distances: list[float] = []
        invalid_cases = 0
        for subset_index, local_index in enumerate(locked_case_local_indices):
            prediction = locked_predictions[subset_index]
            target = locked_targets[subset_index]
            if prediction is None or target is None:
                invalid_cases += 1
                continue
            count = int(counts[local_index])
            lock_mask = archived_locks[local_index, :count] > 0.5
            for slot in np.flatnonzero(lock_mask):
                expected_lock = _locked_color_to_oklab(
                    archived_locked_colors[local_index, slot]
                )
                locked_slot_distances.append(
                    float(np.linalg.norm(prediction[slot] - expected_lock))
                )
            free_mask = ~lock_mask
            if np.any(free_mask):
                completion_set_distances.append(
                    hungarian_matched_set_distance(
                        prediction[free_mask], target[free_mask]
                    )
                )
            full_set_distances.append(
                hungarian_matched_set_distance(prediction, target)
            )
        learned_locks = {
            "status": "measured_raw_model_behavior",
            "runtimeLockGuardApplied": False,
            "caseCount": int(len(locked_case_local_indices)),
            "invalidCaseCount": invalid_cases,
            "sameSeedSameLocksExactDeterminismRate": _rate(
                [
                    bool(np.array_equal(left, right))
                    for left, right in zip(
                        locked_raw, repeated_locked_raw, strict=True
                    )
                ]
            ),
            "lockedSlotCount": len(locked_slot_distances),
            "lockedSlotMeanOklabDistance": (
                float(np.mean(locked_slot_distances))
                if locked_slot_distances
                else None
            ),
            "lockedSlotMedianOklabDistance": (
                float(np.median(locked_slot_distances))
                if locked_slot_distances
                else None
            ),
            "lockedSlotCloseThreshold": duplicate_threshold,
            "lockedSlotCloseRate": (
                sum(value <= duplicate_threshold for value in locked_slot_distances)
                / len(locked_slot_distances)
                if locked_slot_distances
                else None
            ),
            "freeCompletionMeanHungarianSetDistance": (
                float(np.mean(completion_set_distances))
                if completion_set_distances
                else None
            ),
            "freeCompletionMedianHungarianSetDistance": (
                float(np.median(completion_set_distances))
                if completion_set_distances
                else None
            ),
            "fullPaletteMeanHungarianSetDistance": (
                float(np.mean(full_set_distances)) if full_set_distances else None
            ),
        }
    else:
        learned_locks = {
            "status": "no_locked_real_holdout_rows",
            "runtimeLockGuardApplied": False,
            "caseCount": 0,
            "lockedSlotCount": 0,
        }

    return {
        "selection": selection,
        "status": "evaluated",
        "rawUnconditioned": True,
        "targetDerivedLocksRemovedForPrimaryMetrics": True,
        "runtimeLockGuardApplied": False,
        "selectedRowIndices": indices.astype(int).tolist(),
        "validPredictionRows": len(valid_indices),
        "invalidPredictionRows": len(indices) - len(valid_indices),
        "validPredictionRate": len(valid_indices) / len(indices),
        "provenance": provenance,
        "matchedOklab": matched,
        "lightnessDistribution": lightness,
        "nearDuplicates": near_duplicate_palette_rate(
            typed_predictions,
            color_space="oklab",
        ),
        "learnedLockCompletion": learned_locks,
    }


def _gate_at_least(value: float | None, target: float) -> dict[str, Any]:
    return {
        "value": value,
        "target": target,
        "operator": ">=",
        "passed": bool(value is not None and value >= target),
    }


def _gate_at_most(value: float | None, target: float) -> dict[str, Any]:
    return {
        "value": value,
        "target": target,
        "operator": "<=",
        "passed": bool(value is not None and value <= target),
    }


def build_release_decision(
    release_targets: Mapping[str, Any],
    direct_report: Mapping[str, Any],
    engineering: Mapping[str, Any],
    duplicates: Mapping[str, Any],
    holdout: Mapping[str, Any],
    evidence_gates: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    overall = engineering["overall"]
    gates = {
        "rawDirectColor": _gate_at_least(
            direct_report["aggregate"]["raw_direct_color"]["accuracy"],
            float(release_targets["rawDirectColorRate"]),
        ),
        "exactNativeCount": _gate_at_least(
            overall["exactCountRate"],
            float(release_targets["exactCountRate"]),
        ),
        "inactiveSlots": _gate_at_least(
            overall["inactiveExactZeroRate"],
            float(release_targets["inactiveSlotRate"]),
        ),
        "finiteActiveOutputs": _gate_at_least(
            overall["finiteActiveRate"], 1.0
        ),
        "srgbGamut": _gate_at_least(
            overall["srgbGamutPaletteRate"],
            float(release_targets["srgbGamutRate"]),
        ),
        "sameSeedDeterminism": _gate_at_least(
            overall["sameSeedExactDeterminismRate"],
            float(release_targets["determinismRate"]),
        ),
        "nearDuplicatePalettes": _gate_at_most(
            duplicates.get("rate"),
            float(release_targets["maximumNearDuplicatePaletteRate"]),
        ),
        "realHoldoutFiniteOutputs": _gate_at_least(
            holdout.get("validPredictionRate"), 1.0
        ),
        "realHoldoutProvenance": _gate_at_least(
            (
                1.0
                if holdout.get("selection", {}).get(
                    "provenanceIntegrityPassed", False
                )
                else 0.0
            ),
            1.0,
        ),
    }
    all_frozen = all(bool(gate["passed"]) for gate in gates.values())
    real_holdout_available = bool(
        holdout.get("status") == "evaluated"
        and holdout.get("validPredictionRows", 0) > 0
    )
    learned_lock_measured = bool(
        holdout.get("learnedLockCompletion", {}).get("caseCount", 0) > 0
    )
    blockers = []
    blockers.extend(name for name, gate in gates.items() if not gate["passed"])
    blockers.extend(
        name for name, gate in evidence_gates.items() if not gate["passed"]
    )
    if not real_holdout_available:
        blockers.append("realPaletteHoldoutUnavailable")
    blockers.extend(
        [
            "runtimeLockPreservationNotEvaluatedHere",
            "onnxAndBrowserReleaseGatesNotEvaluatedHere",
            "blindHumanPreferenceNotEstablished",
        ]
    )
    return {
        "frozenNumericGates": gates,
        "allFrozenNumericGatesPassed": all_frozen,
        "evidenceIntegrityGates": dict(evidence_gates),
        "allEvidenceIntegrityGatesPassed": all(
            bool(gate["passed"]) for gate in evidence_gates.values()
        ),
        "realPaletteHoldoutAvailable": real_holdout_available,
        "learnedLockCompletionMeasured": learned_lock_measured,
        "runtimeLockPreservationGatePassed": False,
        "releaseReady": False,
        "productionReady": False,
        "promotionPerformed": False,
        "failedOrUnevaluatedGates": blockers,
        "note": (
            "Passing raw numeric gates is necessary but not sufficient. This "
            "entry point never promotes a checkpoint and does not evaluate the "
            "runtime lock guard, ONNX/browser parity, or blind human preference."
        ),
    }


def _parameter_count(model: Any) -> int | None:
    if hasattr(model, "count_parameters"):
        return int(model.count_parameters())
    if hasattr(model, "parameters"):
        return int(sum(parameter.numel() for parameter in model.parameters()))
    return None


def _software_and_device(device: str) -> dict[str, Any]:
    try:
        import scipy
        import torch
    except ImportError as exc:  # pragma: no cover - serious environment only
        raise RuntimeError("SciPy and PyTorch are required for evaluation") from exc
    details: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "torch": torch.__version__,
        "cudaRuntime": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "requestedResolvedDevice": device,
        "cudaAvailable": bool(torch.cuda.is_available()),
    }
    resolved = torch.device(device)
    if resolved.type == "cuda":
        properties = torch.cuda.get_device_properties(resolved)
        details["gpu"] = {
            "name": properties.name,
            "totalMemoryBytes": int(properties.total_memory),
            "computeCapability": [int(properties.major), int(properties.minor)],
        }
    else:
        details["gpu"] = None
    try:
        import transformers

        details["transformers"] = transformers.__version__
    except ImportError:
        details["transformers"] = None
    return details


def _fixture_and_config_evidence(
    color_path: Path,
    semantic_path: Path,
    coverage_path: Path,
    evaluation_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evaluation_config = _load_json_object(evaluation_path)
    paths = {
        "colorFamilies": color_path,
        "semanticRelease": semantic_path,
    }
    evidence: dict[str, Any] = {}
    expected_fixtures = evaluation_config.get("fixtures", {})
    if "coverage" in expected_fixtures:
        paths["coverage"] = coverage_path
    paths["evaluationConfig"] = evaluation_path
    for name, path in paths.items():
        actual = sha256_file(path)
        expected = None
        if name in expected_fixtures:
            expected = expected_fixtures[name].get("sha256")
        evidence[name] = {
            "path": str(path.as_posix()),
            "sha256": actual,
            "expectedSha256": expected,
            "matchesFrozenHash": expected is None or actual == expected,
        }
    evidence["evaluationConfig"]["configHash"] = evaluation_config.get(
        "configHash"
    )
    return evaluation_config, evidence


def _checkpoint_evidence(
    checkpoint_path: Path,
    checkpoint: Mapping[str, Any],
    model: Any,
) -> dict[str, Any]:
    model_config = checkpoint.get("model_config", {})
    checkpoint_sha256 = sha256_file(checkpoint_path)
    candidate_id = checkpoint.get("candidate_id")
    completion_path = (
        checkpoint_path.parent / f"{candidate_id}-metrics.json"
        if candidate_id
        else None
    )
    completion: dict[str, Any] | None = None
    if completion_path is not None and completion_path.is_file():
        completion = _load_json_object(completion_path)
    serious_training_complete = bool(
        completion
        and completion.get("status") == "candidate_training_complete"
        and completion.get("candidateId") == candidate_id
        and completion.get("bestCheckpointSha256") == checkpoint_sha256
        and completion.get("datasetSha256") == checkpoint.get("dataset_sha256")
        and not checkpoint.get("smoke", False)
    )
    return {
        "path": str(checkpoint_path.as_posix()),
        "sha256": checkpoint_sha256,
        "candidateId": candidate_id,
        "epoch": checkpoint.get("epoch"),
        "trainingDataKind": checkpoint.get("training_data_kind"),
        "datasetSha256RecordedAtTraining": checkpoint.get("dataset_sha256"),
        "datasetContentHashRecordedAtTraining": checkpoint.get(
            "dataset_content_hash"
        ),
        "trainingConfigHash": checkpoint.get("training_config_hash"),
        "encoderRevision": checkpoint.get("encoder_revision"),
        "encoderArtifactSha256": checkpoint.get("encoder_artifact_sha256"),
        "modelConfig": model_config,
        "modelConfigHash": canonical_json_sha256(model_config),
        "parameterCount": _parameter_count(model),
        "checkpointProductionReadyClaim": bool(
            checkpoint.get("production_ready", False)
        ),
        "checkpointSmoke": bool(checkpoint.get("smoke", False)),
        "trainingCompletionReport": (
            {
                "path": str(completion_path.as_posix()),
                "sha256": sha256_file(completion_path),
                "status": completion.get("status"),
            }
            if completion_path is not None and completion is not None
            else None
        ),
        "seriousTrainingComplete": serious_training_complete,
    }


def _dataset_evidence(data_path: Path) -> dict[str, Any]:
    with np.load(data_path, allow_pickle=False) as archive:
        validation = validate_prepared_archive(archive)
        metadata: dict[str, Any] = {}
        if "metadata_json" in archive.files:
            raw_metadata = json.loads(str(archive["metadata_json"].item()))
            if isinstance(raw_metadata, dict):
                metadata = raw_metadata
        rows = int(archive["counts"].shape[0]) if "counts" in archive.files else None
        arrays = sorted(archive.files)
    return {
        "path": str(data_path.as_posix()),
        "sha256": sha256_file(data_path),
        "rows": rows,
        "arrayNames": arrays,
        "datasetVersion": metadata.get("datasetVersion"),
        "kind": metadata.get("kind"),
        "contentHash": metadata.get("contentHash"),
        "sourceHash": metadata.get("sourceHash"),
        "sourceHashes": metadata.get("sourceHashes"),
        "preparationConfigHash": metadata.get("configHash"),
        "evaluationConfigHash": metadata.get("evaluationConfigHash"),
        "encoderRevision": metadata.get("encoderRevision"),
        "encoderArtifactSha256": metadata.get("encoderArtifactSha256"),
        "metadataHash": canonical_json_sha256(metadata),
        "archiveValidation": validation,
    }


def _boolean_evidence_gate(
    passed: bool, **details: Any
) -> dict[str, Any]:
    return {"passed": bool(passed), **details}


def build_evidence_integrity_gates(
    *,
    frozen_evidence: Mapping[str, Mapping[str, Any]],
    evaluation_config: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    dataset: Mapping[str, Any],
    encoder: Mapping[str, Any],
    parity_reference: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    fixture_names = tuple(
        name
        for name in ("colorFamilies", "semanticRelease", "coverage")
        if name in frozen_evidence
    )
    frozen_hashes_match = all(
        bool(frozen_evidence[name].get("matchesFrozenHash", False))
        for name in fixture_names
    )
    checkpoint_dataset_hash = checkpoint.get("datasetSha256RecordedAtTraining")
    dataset_hash = dataset.get("sha256")
    encoder_revision = encoder.get("revision")
    dataset_encoder_revision = dataset.get("encoderRevision")
    checkpoint_encoder_revision = checkpoint.get("encoderRevision")
    dataset_encoder_artifact = dataset.get("encoderArtifactSha256")
    checkpoint_encoder_artifact = checkpoint.get("encoderArtifactSha256")
    evaluator_browser_artifact = encoder.get("browserArtifactSha256")
    expected_eval_config_hash = evaluation_config.get("configHash")
    dataset_eval_config_hash = dataset.get("evaluationConfigHash")
    return {
        "frozenFixtureHashes": _boolean_evidence_gate(
            frozen_hashes_match,
            checked=list(fixture_names),
        ),
        "checkpointDatasetHash": _boolean_evidence_gate(
            bool(
                checkpoint_dataset_hash
                and dataset_hash
                and checkpoint_dataset_hash == dataset_hash
            ),
            checkpointSha256=checkpoint_dataset_hash,
            evaluatedDataSha256=dataset_hash,
        ),
        "seriousCompletedTraining": _boolean_evidence_gate(
            bool(checkpoint.get("seriousTrainingComplete", False)),
            checkpointSmoke=checkpoint.get("checkpointSmoke"),
            trainingCompletionReport=checkpoint.get("trainingCompletionReport"),
        ),
        "preparedArchiveValidated": _boolean_evidence_gate(
            bool(dataset.get("archiveValidation")),
            validation=dataset.get("archiveValidation"),
        ),
        "evaluationConfigMatchesDataset": _boolean_evidence_gate(
            bool(
                expected_eval_config_hash
                and dataset_eval_config_hash
                and expected_eval_config_hash == dataset_eval_config_hash
            ),
            frozenConfigHash=expected_eval_config_hash,
            datasetConfigHash=dataset_eval_config_hash,
        ),
        "pinnedEncoderMatchesDatasetAndCheckpoint": _boolean_evidence_gate(
            bool(
                encoder.get("provider") == "pinned_pytorch_e5"
                and encoder_revision
                and encoder_revision == dataset_encoder_revision
                and encoder_revision == checkpoint_encoder_revision
                and dataset_encoder_artifact
                and dataset_encoder_artifact == checkpoint_encoder_artifact
                and dataset_encoder_artifact == evaluator_browser_artifact
            ),
            evaluatorRevision=encoder_revision,
            datasetRevision=dataset_encoder_revision,
            checkpointRevision=checkpoint_encoder_revision,
            datasetBrowserArtifactSha256=dataset_encoder_artifact,
            checkpointBrowserArtifactSha256=checkpoint_encoder_artifact,
            evaluatorBrowserArtifactSha256=evaluator_browser_artifact,
        ),
        "browserEncoderParityReference": _boolean_evidence_gate(
            bool(
                parity_reference
                and parity_reference.get("passed", False)
                and parity_reference.get("pytorchRevision") == encoder_revision
                and parity_reference.get("browserRevision")
                == encoder.get("browserRevision")
                and parity_reference.get("browserArtifactSha256")
                == evaluator_browser_artifact
                and parity_reference.get("fixtureSha256")
                == parity_reference.get("actualFixtureSha256")
            ),
            reportSha256=(parity_reference or {}).get("sha256"),
            pytorchRevision=(parity_reference or {}).get("pytorchRevision"),
            browserRevision=(parity_reference or {}).get("browserRevision"),
            browserArtifactSha256=(parity_reference or {}).get(
                "browserArtifactSha256"
            ),
            fixtureSha256=(parity_reference or {}).get("fixtureSha256"),
            actualFixtureSha256=(parity_reference or {}).get(
                "actualFixtureSha256"
            ),
        ),
    }


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def evaluate_candidate(
    *,
    checkpoint_path: str | Path,
    data_path: str | Path,
    output_path: str | Path | None,
    device: str,
    cache_dir: str | Path,
    model_label: str,
    color_fixture_path: str | Path = COLOR_FIXTURE_PATH,
    semantic_fixture_path: str | Path = SEMANTIC_FIXTURE_PATH,
    coverage_fixture_path: str | Path = COVERAGE_FIXTURE_PATH,
    evaluation_config_path: str | Path = EVALUATION_CONFIG_PATH,
    embedding_provider: EmbeddingProvider | None = None,
    loaded_candidate: LoadedCandidate | None = None,
    batch_size: int = 256,
) -> dict[str, Any]:
    """Run the complete candidate evaluation and optionally persist its report."""

    started = time.perf_counter()
    timings: dict[str, float] = {}
    resolved_device = _resolve_device(device)
    checkpoint_path = Path(checkpoint_path).resolve()
    data_path = Path(data_path).resolve()
    color_path = Path(color_fixture_path).resolve()
    semantic_path = Path(semantic_fixture_path).resolve()
    coverage_path = Path(coverage_fixture_path).resolve()
    evaluation_path = Path(evaluation_config_path).resolve()
    for path, description in (
        (checkpoint_path, "checkpoint"),
        (data_path, "prepared data"),
        (color_path, "color fixture"),
        (semantic_path, "semantic fixture"),
        (evaluation_path, "evaluation config"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{description} does not exist: {path}")

    stage = time.perf_counter()
    color_fixture = load_color_family_fixture(color_path)
    semantic_fixture = load_semantic_release_fixture(semantic_path)
    evaluation_config, frozen_evidence = _fixture_and_config_evidence(
        color_path, semantic_path, coverage_path, evaluation_path
    )
    coverage_fixture = (
        _load_json_object(coverage_path)
        if "coverage" in evaluation_config.get("fixtures", {})
        else None
    )
    texts = collect_benchmark_texts(
        color_fixture, semantic_fixture, coverage_fixture
    )
    seeds = _frozen_seeds(color_fixture, semantic_fixture)
    default_count = int(
        semantic_fixture.get(
            "defaultCount", color_fixture.get("defaultCount", 5)
        )
    )
    if not 2 <= default_count <= MAX_COLORS:
        raise ValueError("frozen defaultCount must be in 2..9")
    timings["loadFixturesSeconds"] = time.perf_counter() - stage

    stage = time.perf_counter()
    if loaded_candidate is None:
        loader: ModelLoader = load_checkpoint_candidate
        candidate = loader(checkpoint_path, resolved_device)
    else:
        candidate = loaded_candidate
    model = _prepare_model(candidate.model, resolved_device)
    timings["loadCheckpointSeconds"] = time.perf_counter() - stage

    stage = time.perf_counter()
    if embedding_provider is None:
        embedding_provider, encoder_metadata = make_pinned_e5_provider(
            device=resolved_device,
            cache_dir=cache_dir,
        )
    else:
        encoder_metadata = {
            "provider": "injected",
            "device": resolved_device,
            "deduplicatedTextCount": len(texts["all"]),
        }
    embeddings = np.asarray(embedding_provider(texts["all"]), dtype=np.float32)
    if embeddings.shape != (len(texts["all"]), 384):
        raise ValueError(
            "embedding provider must return [unique frozen texts, 384]"
        )
    if not np.isfinite(embeddings).all():
        raise ValueError("embedding provider returned non-finite values")
    embedding_norms = np.linalg.norm(embeddings, axis=1)
    if float(np.max(np.abs(embedding_norms - 1.0))) > 5e-3:
        raise ValueError("frozen prompt embeddings must be L2 normalized")
    embeddings_by_text = dict(zip(texts["all"], embeddings, strict=True))
    encoder_metadata["deduplicatedTextCount"] = len(texts["all"])
    encoder_metadata["embeddingReuseAcrossSeedAndCount"] = True
    timings["loadAndEmbedE5Seconds"] = time.perf_counter() - stage

    requests = build_generation_requests(texts["all"], seeds)
    request_embeddings = np.stack(
        [embeddings_by_text[request.prompt] for request in requests]
    ).astype(np.float32, copy=False)
    request_counts = np.asarray([request.count for request in requests], dtype=np.int64)
    request_seeds = np.asarray([request.seed for request in requests], dtype=np.uint64)

    stage = time.perf_counter()
    raw = run_raw_decoder(
        model,
        request_embeddings,
        request_counts,
        request_seeds,
        device=resolved_device,
        batch_size=batch_size,
    )
    repeated_raw = run_raw_decoder(
        model,
        request_embeddings,
        request_counts,
        request_seeds,
        device=resolved_device,
        batch_size=batch_size,
    )
    timings["rawDecoderAndRepeatSeconds"] = time.perf_counter() - stage

    stage = time.perf_counter()
    palettes = _decode_active_rows(raw, request_counts)
    palette_by_request = dict(zip(requests, palettes, strict=True))
    engineering = summarize_engineering_contract(
        requests, raw, repeated_raw, palettes
    )
    timings["decodeAndEngineeringSeconds"] = time.perf_counter() - stage

    stage = time.perf_counter()
    direct = evaluate_direct_predictions(
        color_fixture,
        seeds,
        default_count,
        palette_by_request,
    )
    semantic_palettes: dict[str, dict[int, np.ndarray]] = {}
    for prompt in texts["all"]:
        by_seed: dict[int, np.ndarray] = {}
        for seed in seeds:
            palette = palette_by_request[
                GenerationRequest(prompt, int(seed), default_count)
            ]
            if palette is not None:
                by_seed[int(seed)] = palette
        semantic_palettes[prompt] = by_seed
    modifier = summarize_modifier_sensitivity(
        semantic_palettes,
        semantic_fixture=semantic_fixture,
        color_fixture=color_fixture,
        color_space="oklab",
    )
    modifier["interpretation"] = (
        "Distance establishes whether the modifier changes the set; it does not "
        "by itself establish that the semantic direction is artistically correct."
    )
    translation = summarize_ru_en_parity(
        semantic_palettes,
        semantic_fixture=semantic_fixture,
        color_fixture=color_fixture,
        color_space="oklab",
    )
    default_palettes = [
        palette_by_request[GenerationRequest(prompt, int(seed), default_count)]
        for prompt in texts["all"]
        for seed in seeds
    ]
    valid_default_palettes = [
        palette for palette in default_palettes if palette is not None
    ]
    duplicates = near_duplicate_palette_rate(
        valid_default_palettes,
        fixture=color_fixture,
        color_space="oklab",
    )
    duplicates["invalidPaletteCount"] = len(default_palettes) - len(
        valid_default_palettes
    )
    seed_behavior = summarize_seed_behavior(
        texts["all"],
        seeds,
        default_count,
        palette_by_request,
        direct,
        engineering["overall"]["sameSeedExactDeterminismRate"],
    )
    semantic_seed_values = semantic_fixture.get("seeds", seeds)
    if not isinstance(semantic_seed_values, Sequence) or not semantic_seed_values:
        raise ValueError("semantic fixture must contain a non-empty seeds array")
    sanity_seed = int(
        semantic_fixture.get("sanitySeed", semantic_seed_values[0])
    )
    if sanity_seed not in seeds:
        raise ValueError("semantic sanitySeed must be one of the frozen seeds")
    sanity = build_sanity_outputs(
        texts["sanity"],
        sanity_seed,
        default_count,
        palette_by_request,
    )
    sanity["interpretation"] = (
        "Frozen scene/style outputs are saved for fixed-seed qualitative review; "
        "no human preference score is fabricated."
    )
    timings["semanticMetricsSeconds"] = time.perf_counter() - stage

    stage = time.perf_counter()
    duplicate_threshold = float(
        color_fixture["thresholds"]["nearDuplicateOklabDistance"]
    )
    holdout = evaluate_real_holdout(
        model,
        data_path,
        device=resolved_device,
        batch_size=batch_size,
        duplicate_threshold=duplicate_threshold,
    )
    timings["realHoldoutSeconds"] = time.perf_counter() - stage

    stage = time.perf_counter()
    release_targets = evaluation_config.get("releaseTargets")
    if not isinstance(release_targets, Mapping):
        raise ValueError("evaluation config has no releaseTargets object")
    checkpoint_info = _checkpoint_evidence(
        checkpoint_path, candidate.checkpoint, model
    )
    dataset_info = _dataset_evidence(data_path)
    checkpoint_dataset_hash = checkpoint_info[
        "datasetSha256RecordedAtTraining"
    ]
    dataset_info["matchesCheckpointDatasetSha256"] = bool(
        checkpoint_dataset_hash
        and checkpoint_dataset_hash == dataset_info["sha256"]
    )

    parity_evidence: dict[str, Any] | None = None
    if E5_PARITY_REPORT_PATH.is_file():
        parity_payload = _load_json_object(E5_PARITY_REPORT_PATH)
        pytorch_encoder = parity_payload.get("pytorchEncoder", {})
        browser_encoder = parity_payload.get("browserEncoder", {})
        parity_evidence = {
            "path": str(E5_PARITY_REPORT_PATH.as_posix()),
            "sha256": sha256_file(E5_PARITY_REPORT_PATH),
            "passed": bool(parity_payload.get("passed", False)),
            "metrics": parity_payload.get("metrics"),
            "thresholds": parity_payload.get("thresholds"),
            "fixtureSha256": parity_payload.get("fixtureSha256"),
            "actualFixtureSha256": sha256_file(
                PACKAGE_DIR / "e5_parity_prompts.v1.json"
            ),
            "pytorchRevision": pytorch_encoder.get("revision"),
            "browserRevision": browser_encoder.get("revision"),
            "browserArtifactSha256": browser_encoder.get("artifactSha256"),
        }
    evidence_gates = build_evidence_integrity_gates(
        frozen_evidence=frozen_evidence,
        evaluation_config=evaluation_config,
        checkpoint=checkpoint_info,
        dataset=dataset_info,
        encoder=encoder_metadata,
        parity_reference=parity_evidence,
    )
    release_decision = build_release_decision(
        release_targets,
        direct,
        engineering,
        duplicates,
        holdout,
        evidence_gates,
    )
    timings["evidenceAndDecisionSeconds"] = time.perf_counter() - stage
    timings["totalSeconds"] = time.perf_counter() - started

    report: dict[str, Any] = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "status": "candidate_evaluation_complete",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "modelLabel": model_label,
        "productionReady": False,
        "promotionPerformed": False,
        "rawEvaluationPolicy": {
            "nativeRequestedCounts": True,
            "runtimeColorGuardApplied": False,
            "runtimeLockRestorationApplied": False,
            "postCorrectionApplied": False,
            "seedSelectionAfterInspection": False,
        },
        "evaluationParameters": {
            "device": resolved_device,
            "batchSize": batch_size,
            "embeddingCacheDirectory": str(Path(cache_dir).as_posix()),
            "defaultSemanticCount": default_count,
            "sanitySeed": sanity_seed,
        },
        "frozenEvidence": frozen_evidence,
        "checkpoint": checkpoint_info,
        "dataset": dataset_info,
        "encoder": encoder_metadata,
        "encoderParityReference": parity_evidence,
        "benchmarkCoverage": {
            "uniqueEmbeddedTexts": len(texts["all"]),
            "directTexts": len(texts["direct"]),
            "modifierTexts": len(texts["modifier"]),
            "translationTexts": len(texts["translation"]),
            "sanityTexts": len(texts["sanity"]),
            "semanticGroupTexts": len(texts["semanticGroups"]),
            "coverageTexts": len(texts["coverage"]),
            "frozenSeeds": seeds,
            "nativeCounts": list(range(2, MAX_COLORS + 1)),
            "decoderRequests": len(requests),
            "decoderRequestsIncludingDeterminismRepeat": len(requests) * 2,
        },
        "engineering": engineering,
        "directColor": direct,
        "nearDuplicates": duplicates,
        "modifierSensitivity": modifier,
        "ruEnParity": translation,
        "seedBehavior": seed_behavior,
        "sanityOutputs": sanity,
        "realPaletteHoldout": holdout,
        "releaseDecision": release_decision,
        "softwareAndDevice": _software_and_device(resolved_device),
        "timingsSeconds": timings,
    }
    if output_path is not None:
        _atomic_write_json(Path(output_path).resolve(), report)
    return report


def _compact_summary(report: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    direct = report["directColor"]["aggregate"]["raw_direct_color"]
    holdout = report["realPaletteHoldout"]
    return {
        "status": report["status"],
        "modelLabel": report["modelLabel"],
        "report": str(output_path.as_posix()),
        "rawDirectColorAccuracy": direct["accuracy"],
        "realHoldoutMeanMatchedOklabDistance": holdout["matchedOklab"][
            "mean_distance"
        ],
        "allFrozenNumericGatesPassed": report["releaseDecision"][
            "allFrozenNumericGatesPassed"
        ],
        "releaseReady": False,
        "productionReady": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--device",
        default="cuda",
        help="CUDA is the serious-evaluation default; pass cpu only as an explicit fallback.",
    )
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--model-label", required=True)
    args = parser.parse_args()
    output_path = Path(args.output).resolve()
    report = evaluate_candidate(
        checkpoint_path=args.checkpoint,
        data_path=args.data,
        output_path=output_path,
        device=args.device,
        cache_dir=args.cache_dir,
        model_label=args.model_label,
    )
    print(
        json.dumps(
            _compact_summary(report, output_path),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
