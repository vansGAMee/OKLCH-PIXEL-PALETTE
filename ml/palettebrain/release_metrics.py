"""Frozen, physical release metrics for PaletteBrain palette predictions.

This module deliberately has no model, tokenizer, or embedding dependency.  It
scores already-decoded palettes in physical OKLab or OKLCH space using only the
thresholds, prototypes, prompts, and pairs stored in the frozen benchmark
fixtures next to this file.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
import json
import math
from typing import Any, Literal, TypeAlias

import numpy as np
from scipy.optimize import linear_sum_assignment


ColorSpace: TypeAlias = Literal["oklab", "oklch"]
PaletteLike: TypeAlias = Sequence[Sequence[float]] | np.ndarray

COLOR_FAMILY_FIXTURE = Path(__file__).with_name(
    "benchmark_color_families.v1.json"
)
SEMANTIC_RELEASE_FIXTURE = Path(__file__).with_name(
    "benchmark_semantic_release.v1.json"
)


def _load_json_object(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"benchmark fixture must contain an object: {resolved}")
    return value


def load_color_family_fixture(
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Load the frozen family prototypes, prompt cases, and metric thresholds."""

    fixture = _load_json_object(path or COLOR_FAMILY_FIXTURE)
    required = {"thresholds", "families", "prompts"}
    missing = sorted(required.difference(fixture))
    if missing:
        raise ValueError(f"color-family fixture is missing: {', '.join(missing)}")
    return fixture


def load_semantic_release_fixture(
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Load the frozen modifier and RU/EN translation pair definitions."""

    fixture = _load_json_object(path or SEMANTIC_RELEASE_FIXTURE)
    required = {"modifierPairs", "translationPairs"}
    missing = sorted(required.difference(fixture))
    if missing:
        raise ValueError(f"semantic fixture is missing: {', '.join(missing)}")
    return fixture


def _color_fixture(fixture: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return fixture if fixture is not None else load_color_family_fixture()


def _semantic_fixture(fixture: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return fixture if fixture is not None else load_semantic_release_fixture()


def _threshold(fixture: Mapping[str, Any], name: str) -> float:
    thresholds = fixture.get("thresholds")
    if not isinstance(thresholds, Mapping) or name not in thresholds:
        raise ValueError(f"color-family fixture has no threshold {name!r}")
    value = float(thresholds[name])
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"threshold {name!r} must be finite and non-negative")
    return value


def palette_to_oklab(
    palette: PaletteLike,
    *,
    color_space: ColorSpace = "oklab",
    allow_empty: bool = False,
) -> np.ndarray:
    """Validate a physical palette and return an independent float64 OKLab array.

    OKLCH is interpreted as ``[L, C, h_degrees]``.  No gamut mapping or decoder
    representation conversion happens here: callers must provide physical
    colors, as required by the release benchmark.
    """

    values = np.asarray(palette, dtype=np.float64)
    if values.ndim != 2 or values.shape[1:] != (3,):
        raise ValueError("palette must have shape [colors, 3]")
    if not allow_empty and values.shape[0] == 0:
        raise ValueError("palette must contain at least one color")
    if not np.isfinite(values).all():
        raise ValueError("palette must contain only finite physical colors")
    if color_space == "oklab":
        return values.copy()
    if color_space != "oklch":
        raise ValueError("color_space must be 'oklab' or 'oklch'")
    if np.any(values[:, 1] < 0.0):
        raise ValueError("physical OKLCH chroma must be non-negative")
    angles = np.deg2rad(np.mod(values[:, 2], 360.0))
    return np.column_stack(
        (values[:, 0], values[:, 1] * np.cos(angles), values[:, 1] * np.sin(angles))
    )


def _family_definition(
    family: str, fixture: Mapping[str, Any]
) -> Mapping[str, Any]:
    families = fixture.get("families")
    if not isinstance(families, Mapping) or family not in families:
        raise KeyError(f"unknown frozen color family: {family!r}")
    definition = families[family]
    if not isinstance(definition, Mapping) or "kind" not in definition:
        raise ValueError(f"invalid frozen color family definition: {family!r}")
    return definition


def _neutral_region_distance(
    color: np.ndarray, kind: str, fixture: Mapping[str, Any]
) -> float:
    lightness = float(color[0])
    chroma = float(np.linalg.norm(color[1:3]))
    maximum_chroma = _threshold(fixture, "neutralMaximumChroma")
    chroma_error = max(0.0, chroma - maximum_chroma)
    if kind == "black":
        lightness_error = max(
            0.0, lightness - _threshold(fixture, "blackMaximumLightness")
        )
    elif kind == "white":
        lightness_error = max(
            0.0, _threshold(fixture, "whiteMinimumLightness") - lightness
        )
    elif kind == "gray":
        minimum = _threshold(fixture, "grayMinimumLightness")
        maximum = _threshold(fixture, "grayMaximumLightness")
        lightness_error = max(0.0, minimum - lightness, lightness - maximum)
    else:  # pragma: no cover - guarded by the frozen fixture validation path
        raise ValueError(f"unsupported neutral family kind: {kind!r}")
    return math.hypot(lightness_error, chroma_error)


def family_distance(
    color: Sequence[float] | np.ndarray,
    family: str,
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> float:
    """Return physical distance from one color to a frozen family.

    Chromatic families use the closest OKLab prototype.  Neutral families use
    Euclidean distance to their frozen lightness/chroma region, and therefore
    have distance zero exactly when the color lies inside that region.
    """

    benchmark = _color_fixture(fixture)
    physical = palette_to_oklab([color], color_space=color_space)[0]
    definition = _family_definition(family, benchmark)
    kind = str(definition["kind"])
    if kind != "chromatic":
        return _neutral_region_distance(physical, kind, benchmark)
    prototypes = np.asarray(definition.get("oklabPrototypes"), dtype=np.float64)
    if prototypes.ndim != 2 or prototypes.shape[1:] != (3,):
        raise ValueError(f"chromatic family {family!r} has invalid prototypes")
    return float(np.min(np.linalg.norm(prototypes - physical, axis=1)))


def matches_family(
    color: Sequence[float] | np.ndarray,
    family: str,
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> bool:
    """Whether a color satisfies a chromatic anchor or neutral physical range."""

    benchmark = _color_fixture(fixture)
    definition = _family_definition(family, benchmark)
    distance = family_distance(
        color, family, fixture=benchmark, color_space=color_space
    )
    if definition["kind"] == "chromatic":
        return distance <= _threshold(benchmark, "anchorOklabDistance")
    return distance == 0.0


def match_required_families(
    palette: PaletteLike,
    required_families: Sequence[str],
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Assign every required family to a distinct generated color.

    Assignment first minimizes the number of invalid family/color matches, then
    physical distance.  This prevents one lucky color from satisfying two
    requested families and avoids a raw-distance assignment hiding a feasible
    all-valid assignment.
    """

    benchmark = _color_fixture(fixture)
    physical = palette_to_oklab(palette, color_space=color_space)
    required = [str(family) for family in required_families]
    for family in required:
        _family_definition(family, benchmark)
    if not required:
        return {
            "passed": True,
            "required_count": 0,
            "matched_count": 0,
            "assignments": [],
            "unmatched_families": [],
            "mean_matched_distance": None,
        }
    distances = np.asarray(
        [
            [family_distance(color, family, fixture=benchmark) for color in physical]
            for family in required
        ],
        dtype=np.float64,
    )
    valid = np.asarray(
        [
            [matches_family(color, family, fixture=benchmark) for color in physical]
            for family in required
        ],
        dtype=bool,
    )
    maximum_distance = float(np.max(distances)) if distances.size else 0.0
    invalid_penalty = (maximum_distance + 1.0) * (len(required) + 1)
    rows, columns = linear_sum_assignment(
        distances + (~valid).astype(np.float64) * invalid_penalty
    )

    assignments: list[dict[str, Any]] = []
    matched_families: set[int] = set()
    for row, column in zip(rows.tolist(), columns.tolist(), strict=True):
        is_match = bool(valid[row, column])
        if is_match:
            matched_families.add(row)
        assignments.append(
            {
                "required_index": row,
                "family": required[row],
                "color_index": column,
                "distance": float(distances[row, column]),
                "matched": is_match,
            }
        )
    assignments.sort(key=lambda item: int(item["required_index"]))
    matched_distances = [
        float(item["distance"]) for item in assignments if item["matched"]
    ]
    unmatched = [
        family for index, family in enumerate(required) if index not in matched_families
    ]
    return {
        "passed": len(matched_families) == len(required),
        "required_count": len(required),
        "matched_count": len(matched_families),
        "assignments": assignments,
        "unmatched_families": unmatched,
        "mean_matched_distance": (
            float(np.mean(matched_distances)) if matched_distances else None
        ),
    }


def score_exclusions(
    palette: PaletteLike,
    excluded_families: Sequence[str],
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Check frozen exclusions against all active physical palette colors."""

    benchmark = _color_fixture(fixture)
    physical = palette_to_oklab(palette, color_space=color_space)
    excluded = [str(family) for family in excluded_families]
    chromatic_cutoff = _threshold(benchmark, "chromaticChroma")
    exclusion_cutoff = _threshold(benchmark, "exclusionOklabDistance")
    chroma = np.linalg.norm(physical[:, 1:3], axis=1)
    violations: list[dict[str, Any]] = []
    for family in excluded:
        definition = _family_definition(family, benchmark)
        for color_index, color in enumerate(physical):
            if definition["kind"] == "chromatic":
                violates = bool(
                    chroma[color_index] > chromatic_cutoff
                    and family_distance(color, family, fixture=benchmark)
                    <= exclusion_cutoff
                )
            else:
                violates = matches_family(color, family, fixture=benchmark)
            if violates:
                violations.append(
                    {
                        "family": family,
                        "color_index": color_index,
                        "distance": family_distance(
                            color, family, fixture=benchmark
                        ),
                    }
                )
    return {
        "passed": not violations,
        "excluded_count": len(excluded),
        "violations": violations,
    }


def standalone_unrelated_ratio(
    palette: PaletteLike,
    required_families: str | Sequence[str],
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Measure whole-palette consistency for a standalone family prompt.

    Neutral colors accompanying a chromatic request are ignored.  A chromatic
    generated color is unrelated when it is farther than the frozen strongly-
    unrelated cutoff from every requested chromatic family.  For a standalone
    neutral request, every chromatic generated color is unrelated.
    """

    benchmark = _color_fixture(fixture)
    physical = palette_to_oklab(palette, color_space=color_space)
    required = (
        [required_families]
        if isinstance(required_families, str)
        else [str(family) for family in required_families]
    )
    chromatic_required = [
        family
        for family in required
        if _family_definition(family, benchmark)["kind"] == "chromatic"
    ]
    chroma = np.linalg.norm(physical[:, 1:3], axis=1)
    chromatic_indices = np.flatnonzero(
        chroma > _threshold(benchmark, "chromaticChroma")
    )
    unrelated_indices: list[int] = []
    strongly_unrelated = _threshold(
        benchmark, "stronglyUnrelatedOklabDistance"
    )
    for index in chromatic_indices.tolist():
        minimum_distance = min(
            (
                family_distance(physical[index], family, fixture=benchmark)
                for family in chromatic_required
            ),
            default=math.inf,
        )
        if minimum_distance > strongly_unrelated:
            unrelated_indices.append(index)
    ratio = (
        len(unrelated_indices) / len(chromatic_indices)
        if len(chromatic_indices)
        else 0.0
    )
    maximum = _threshold(benchmark, "maximumUnrelatedChromaticRatio")
    return {
        "passed": ratio <= maximum,
        "ratio": float(ratio),
        "chromatic_count": int(len(chromatic_indices)),
        "unrelated_count": len(unrelated_indices),
        "unrelated_color_indices": unrelated_indices,
    }


def score_direct_prompt(
    palette: PaletteLike,
    prompt_case: Mapping[str, Any],
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Score one raw generated palette against one frozen direct prompt case."""

    benchmark = _color_fixture(fixture)
    required = [str(value) for value in prompt_case.get("required", [])]
    excluded = [str(value) for value in prompt_case.get("excluded", [])]
    required_result = match_required_families(
        palette, required, fixture=benchmark, color_space=color_space
    )
    exclusion_result = score_exclusions(
        palette, excluded, fixture=benchmark, color_space=color_space
    )
    standalone = bool(prompt_case.get("standalone", False))
    consistency_result = (
        standalone_unrelated_ratio(
            palette, required, fixture=benchmark, color_space=color_space
        )
        if standalone
        else {
            "passed": True,
            "ratio": None,
            "chromatic_count": None,
            "unrelated_count": None,
            "unrelated_color_indices": [],
        }
    )
    return {
        "id": prompt_case.get("id"),
        "prompt": prompt_case.get("prompt"),
        "language": prompt_case.get("language"),
        "required": required,
        "excluded": excluded,
        "standalone": standalone,
        "passed": bool(
            required_result["passed"]
            and exclusion_result["passed"]
            and consistency_result["passed"]
        ),
        "required_passed": bool(required_result["passed"]),
        "exclusion_passed": bool(exclusion_result["passed"]),
        "consistency_passed": bool(consistency_result["passed"]),
        "required_match": required_result,
        "exclusion": exclusion_result,
        "consistency": consistency_result,
    }


def _rate_summary(values: Iterable[bool]) -> dict[str, Any]:
    decisions = [bool(value) for value in values]
    passed = sum(decisions)
    return {
        "total": len(decisions),
        "passed": passed,
        "failed": len(decisions) - passed,
        "accuracy": passed / len(decisions) if decisions else None,
    }


def aggregate_direct_prompt_scores(
    scores: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate raw direct scores, including separate frozen RU and EN rates."""

    rows = list(scores)
    raw_direct = [
        row
        for row in rows
        if len(row.get("required", [])) == 1 and not row.get("excluded", [])
    ]
    multi_color = [row for row in rows if len(row.get("required", [])) > 1]
    exclusions = [row for row in rows if row.get("excluded", [])]
    languages = sorted(
        {"en", "ru"}
        | {
            str(row["language"])
            for row in rows
            if row.get("language") is not None
        }
    )
    return {
        "overall": _rate_summary(row.get("passed", False) for row in rows),
        "raw_direct_color": _rate_summary(
            row.get("passed", False) for row in raw_direct
        ),
        "raw_direct_color_by_language": {
            language: _rate_summary(
                row.get("passed", False)
                for row in raw_direct
                if row.get("language") == language
            )
            for language in languages
        },
        "by_language": {
            language: _rate_summary(
                row.get("passed", False)
                for row in rows
                if row.get("language") == language
            )
            for language in languages
        },
        "multi_color_anchor": _rate_summary(
            row.get("required_passed", False) for row in multi_color
        ),
        "exclusion": _rate_summary(
            row.get("exclusion_passed", False) for row in exclusions
        ),
    }


def evaluate_direct_color_records(
    records: Iterable[Mapping[str, Any]],
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Score generated direct-color records without performing model inference.

    Each record must contain ``palette`` and either ``prompt_id`` or ``prompt``.
    Any ``seed`` is copied into the sample report.  This intentionally leaves
    generation and frozen-seed orchestration to the evaluator.
    """

    benchmark = _color_fixture(fixture)
    prompt_cases = benchmark.get("prompts")
    if not isinstance(prompt_cases, Sequence):
        raise ValueError("color-family fixture prompts must be an array")
    by_id = {case.get("id"): case for case in prompt_cases}
    by_prompt = {case.get("prompt"): case for case in prompt_cases}
    samples: list[dict[str, Any]] = []
    for record in records:
        case = None
        if record.get("prompt_id") is not None:
            case = by_id.get(record["prompt_id"])
        if case is None and record.get("prompt") is not None:
            case = by_prompt.get(record["prompt"])
        if case is None:
            identifier = record.get("prompt_id", record.get("prompt"))
            raise KeyError(f"record does not reference a frozen prompt: {identifier!r}")
        if "palette" not in record:
            raise ValueError("direct-color record is missing 'palette'")
        sample = score_direct_prompt(
            record["palette"], case, fixture=benchmark, color_space=color_space
        )
        if "seed" in record:
            sample["seed"] = record["seed"]
        samples.append(sample)
    return {"samples": samples, "aggregate": aggregate_direct_prompt_scores(samples)}


def palette_has_near_duplicate(
    palette: PaletteLike,
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> bool:
    """Whether any physical pair is closer than the frozen duplicate cutoff."""

    benchmark = _color_fixture(fixture)
    physical = palette_to_oklab(palette, color_space=color_space)
    threshold = _threshold(benchmark, "nearDuplicateOklabDistance")
    if len(physical) < 2:
        return False
    distances = np.linalg.norm(
        physical[:, None, :] - physical[None, :, :], axis=-1
    )
    upper = distances[np.triu_indices(len(physical), k=1)]
    return bool(np.any(upper < threshold))


def near_duplicate_palette_rate(
    palettes: Iterable[PaletteLike],
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Return the fraction of palettes containing at least one near duplicate."""

    benchmark = _color_fixture(fixture)
    flags = [
        palette_has_near_duplicate(
            palette, fixture=benchmark, color_space=color_space
        )
        for palette in palettes
    ]
    affected = sum(flags)
    return {
        "palette_count": len(flags),
        "near_duplicate_palette_count": affected,
        "rate": affected / len(flags) if flags else None,
        "threshold": _threshold(benchmark, "nearDuplicateOklabDistance"),
    }


def hungarian_matched_distances(
    left: PaletteLike,
    right: PaletteLike,
    *,
    left_color_space: ColorSpace = "oklab",
    right_color_space: ColorSpace = "oklab",
) -> np.ndarray:
    """Return optimal one-to-one physical OKLab distances for equal-size sets."""

    left_physical = palette_to_oklab(left, color_space=left_color_space)
    right_physical = palette_to_oklab(right, color_space=right_color_space)
    if len(left_physical) != len(right_physical):
        raise ValueError("matched palette sets must have the same number of colors")
    pairwise = np.linalg.norm(
        left_physical[:, None, :] - right_physical[None, :, :], axis=-1
    )
    rows, columns = linear_sum_assignment(pairwise)
    return pairwise[rows, columns].astype(np.float64, copy=False)


def hungarian_matched_set_distance(
    left: PaletteLike,
    right: PaletteLike,
    *,
    left_color_space: ColorSpace = "oklab",
    right_color_space: ColorSpace = "oklab",
) -> float:
    """Mean optimal one-to-one OKLab set distance (permutation invariant)."""

    return float(
        np.mean(
            hungarian_matched_distances(
                left,
                right,
                left_color_space=left_color_space,
                right_color_space=right_color_space,
            )
        )
    )


def summarize_matched_set_distances(
    predicted: Iterable[PaletteLike],
    target: Iterable[PaletteLike],
    *,
    predicted_color_space: ColorSpace = "oklab",
    target_color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Summarize per-palette Hungarian distance for a real-palette holdout."""

    predicted_values = list(predicted)
    target_values = list(target)
    if len(predicted_values) != len(target_values):
        raise ValueError("predicted and target collections must have equal length")
    matched_by_palette = [
        hungarian_matched_distances(
            prediction,
            expected,
            left_color_space=predicted_color_space,
            right_color_space=target_color_space,
        )
        for prediction, expected in zip(
            predicted_values, target_values, strict=True
        )
    ]
    set_distances = [float(np.mean(values)) for values in matched_by_palette]
    matched_distances = [
        float(distance)
        for palette_distances in matched_by_palette
        for distance in palette_distances
    ]
    return {
        "palette_count": len(set_distances),
        "matched_color_count": len(matched_distances),
        "mean_distance": (
            float(np.mean(matched_distances)) if matched_distances else None
        ),
        "median_distance": (
            float(np.median(matched_distances)) if matched_distances else None
        ),
        "mean_set_distance": (
            float(np.mean(set_distances)) if set_distances else None
        ),
        "set_distances": set_distances,
        "matched_distances": matched_distances,
    }


def _palette_variants(value: Any) -> dict[Any, PaletteLike]:
    if isinstance(value, Mapping):
        return dict(value)
    values = np.asarray(value, dtype=np.float64)
    if values.ndim == 2:
        return {"default": values}
    if values.ndim == 3:
        return {index: values[index] for index in range(values.shape[0])}
    raise ValueError(
        "prompt palettes must be one palette, a palette stack, or seed mapping"
    )


def _paired_prompt_distances(
    palettes_by_prompt: Mapping[str, Any],
    left_prompt: str,
    right_prompt: str,
    *,
    color_space: ColorSpace,
) -> tuple[list[dict[str, Any]], list[str]]:
    missing = [
        prompt
        for prompt in (left_prompt, right_prompt)
        if prompt not in palettes_by_prompt
    ]
    if missing:
        return [], missing
    left = _palette_variants(palettes_by_prompt[left_prompt])
    right = _palette_variants(palettes_by_prompt[right_prompt])
    common = sorted(set(left).intersection(right), key=str)
    return [
        {
            "variant": variant,
            "distance": hungarian_matched_set_distance(
                left[variant],
                right[variant],
                left_color_space=color_space,
                right_color_space=color_space,
            ),
        }
        for variant in common
    ], []


def _summarize_pair_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    distances = [
        float(sample["distance"])
        for row in rows
        for sample in row.get("samples", [])
    ]
    return {
        "pair_count": len(rows),
        "evaluated_pair_count": sum(bool(row.get("samples")) for row in rows),
        "sample_count": len(distances),
        "mean_distance": float(np.mean(distances)) if distances else None,
        "median_distance": float(np.median(distances)) if distances else None,
    }


def summarize_modifier_sensitivity(
    palettes_by_prompt: Mapping[str, Any],
    *,
    semantic_fixture: Mapping[str, Any] | None = None,
    color_fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Summarize same-variant set changes for all frozen modifier pairs."""

    semantic = _semantic_fixture(semantic_fixture)
    benchmark = _color_fixture(color_fixture)
    perceptible_threshold = _threshold(
        benchmark, "nearDuplicateOklabDistance"
    )
    rows: list[dict[str, Any]] = []
    for raw_pair in semantic["modifierPairs"]:
        left_prompt, right_prompt = map(str, raw_pair)
        samples, missing = _paired_prompt_distances(
            palettes_by_prompt,
            left_prompt,
            right_prompt,
            color_space=color_space,
        )
        for sample in samples:
            sample["perceptible_change"] = (
                float(sample["distance"]) >= perceptible_threshold
            )
        distances = [float(sample["distance"]) for sample in samples]
        rows.append(
            {
                "base_prompt": left_prompt,
                "modified_prompt": right_prompt,
                "missing_prompts": missing,
                "sample_count": len(samples),
                "mean_distance": float(np.mean(distances)) if distances else None,
                "median_distance": (
                    float(np.median(distances)) if distances else None
                ),
                "perceptible_change_rate": (
                    sum(bool(sample["perceptible_change"]) for sample in samples)
                    / len(samples)
                    if samples
                    else None
                ),
                "samples": samples,
            }
        )
    summary = _summarize_pair_rows(rows)
    all_samples = [sample for row in rows for sample in row["samples"]]
    summary.update(
        {
            "perceptible_threshold": perceptible_threshold,
            "perceptible_change_rate": (
                sum(bool(sample["perceptible_change"]) for sample in all_samples)
                / len(all_samples)
                if all_samples
                else None
            ),
            "pairs": rows,
        }
    )
    return summary


def recognized_families(
    palette: PaletteLike,
    *,
    fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> list[str]:
    """Return frozen family names represented by at least one palette color."""

    benchmark = _color_fixture(fixture)
    physical = palette_to_oklab(palette, color_space=color_space)
    families = benchmark.get("families")
    if not isinstance(families, Mapping):
        raise ValueError("color-family fixture families must be an object")
    return sorted(
        family
        for family in families
        if any(matches_family(color, family, fixture=benchmark) for color in physical)
    )


def summarize_ru_en_parity(
    palettes_by_prompt: Mapping[str, Any],
    *,
    semantic_fixture: Mapping[str, Any] | None = None,
    color_fixture: Mapping[str, Any] | None = None,
    color_space: ColorSpace = "oklab",
) -> dict[str, Any]:
    """Summarize set distance and recognized-family agreement for RU/EN pairs."""

    semantic = _semantic_fixture(semantic_fixture)
    benchmark = _color_fixture(color_fixture)
    rows: list[dict[str, Any]] = []
    for raw_pair in semantic["translationPairs"]:
        en_prompt, ru_prompt = map(str, raw_pair)
        samples, missing = _paired_prompt_distances(
            palettes_by_prompt,
            en_prompt,
            ru_prompt,
            color_space=color_space,
        )
        if not missing:
            en_variants = _palette_variants(palettes_by_prompt[en_prompt])
            ru_variants = _palette_variants(palettes_by_prompt[ru_prompt])
            for sample in samples:
                variant = sample["variant"]
                en_families = set(
                    recognized_families(
                        en_variants[variant], fixture=benchmark, color_space=color_space
                    )
                )
                ru_families = set(
                    recognized_families(
                        ru_variants[variant], fixture=benchmark, color_space=color_space
                    )
                )
                union = en_families | ru_families
                sample["en_families"] = sorted(en_families)
                sample["ru_families"] = sorted(ru_families)
                sample["family_agreement"] = (
                    len(en_families & ru_families) / len(union) if union else 1.0
                )
        distances = [float(sample["distance"]) for sample in samples]
        agreements = [float(sample["family_agreement"]) for sample in samples]
        rows.append(
            {
                "en_prompt": en_prompt,
                "ru_prompt": ru_prompt,
                "missing_prompts": missing,
                "sample_count": len(samples),
                "mean_distance": float(np.mean(distances)) if distances else None,
                "median_distance": (
                    float(np.median(distances)) if distances else None
                ),
                "mean_family_agreement": (
                    float(np.mean(agreements)) if agreements else None
                ),
                "samples": samples,
            }
        )
    summary = _summarize_pair_rows(rows)
    all_agreements = [
        float(sample["family_agreement"])
        for row in rows
        for sample in row["samples"]
    ]
    summary.update(
        {
            "mean_family_agreement": (
                float(np.mean(all_agreements)) if all_agreements else None
            ),
            "pairs": rows,
        }
    )
    return summary


def deterministic_palette_equality(*palettes: PaletteLike) -> bool:
    """Require exact ordered numeric equality across repeated generation outputs."""

    if len(palettes) < 2:
        raise ValueError("determinism requires at least two palette outputs")
    values = [np.asarray(palette) for palette in palettes]
    return all(
        value.shape == values[0].shape and np.array_equal(value, values[0])
        for value in values[1:]
    )


# Concise compatibility aliases for evaluators that prefer metric-style names.
family_matches = matches_family
hungarian_set_distance = hungarian_matched_set_distance
is_deterministic_equal = deterministic_palette_equality


__all__ = [
    "COLOR_FAMILY_FIXTURE",
    "SEMANTIC_RELEASE_FIXTURE",
    "aggregate_direct_prompt_scores",
    "deterministic_palette_equality",
    "evaluate_direct_color_records",
    "family_distance",
    "family_matches",
    "hungarian_matched_distances",
    "hungarian_matched_set_distance",
    "hungarian_set_distance",
    "is_deterministic_equal",
    "load_color_family_fixture",
    "load_semantic_release_fixture",
    "match_required_families",
    "matches_family",
    "near_duplicate_palette_rate",
    "palette_has_near_duplicate",
    "palette_to_oklab",
    "recognized_families",
    "score_direct_prompt",
    "score_exclusions",
    "standalone_unrelated_ratio",
    "summarize_matched_set_distances",
    "summarize_modifier_sensitivity",
    "summarize_ru_en_parity",
]
