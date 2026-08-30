"""Training-only palette-semantic policy for Candidate 11 source images.

This module deliberately knows nothing about benchmark answer palettes.  It
scores the 390-bin OKLCH histograms already extracted from acquisition images.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Literal, Sequence

import numpy as np

from ml.palettebrain.color_distribution import (
    CHROMA_EDGES,
    LIGHT_EDGES,
    NUM_CHROMA_BINS,
    NUM_HUE_BINS,
    NUM_LIGHT_BINS,
    NUM_NEUTRAL_BINS,
    TOTAL_HISTOGRAM_BINS,
)


Mode = Literal["constrained", "observational"]
SEMANTIC_MIN_PASS_IMAGES_PER_CONSTRAINED_CONCEPT = 2
SEMANTIC_MIN_CONCEPT_PASS_FRACTION = 0.20


@dataclass(frozen=True)
class SemanticRule:
    rule_id: str
    mode: Mode
    hue_arcs: tuple[tuple[float, float], ...]
    lightness: tuple[float, float]
    chroma: tuple[float, float]
    include_neutral: bool
    minimum_mass: float
    confidence: float
    retrieval_hint: str = ""


@dataclass(frozen=True)
class SemanticScore:
    score: float
    passed: bool
    reason: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pair(
    value: Any,
    *,
    name: str,
    minimum: float,
    maximum: float,
) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a two-number list")
    low, high = (float(item) for item in value)
    if not (math.isfinite(low) and math.isfinite(high)):
        raise ValueError(f"{name} must be finite")
    if low < minimum or high > maximum or low > high:
        raise ValueError(f"{name} must stay within [{minimum}, {maximum}]")
    return low, high


def _parse_rule(raw: dict[str, Any], *, fallback_id: str) -> SemanticRule:
    mode = str(raw.get("mode", ""))
    if mode not in {"constrained", "observational"}:
        raise ValueError(f"invalid palette semantic mode: {mode!r}")

    rule_id = str(raw.get("id", fallback_id)).strip()
    if not rule_id:
        raise ValueError("palette semantic rule id must not be empty")

    if mode == "observational":
        return SemanticRule(
            rule_id=rule_id,
            mode="observational",
            hue_arcs=(),
            lightness=(0.0, 1.0),
            chroma=(0.0, 1.0),
            include_neutral=True,
            minimum_mass=0.0,
            confidence=1.0,
            retrieval_hint=str(raw.get("retrievalHint", "")).strip(),
        )

    hue_arcs = tuple(
        _pair(arc, name=f"{rule_id}.hueArcs", minimum=0.0, maximum=360.0)
        for arc in raw.get("hueArcs", [])
    )
    include_neutral = bool(raw.get("includeNeutral", False))
    if not hue_arcs and not include_neutral:
        raise ValueError(
            f"constrained rule {rule_id!r} needs a hue arc or neutral mass"
        )

    minimum_mass = float(raw.get("minimumMass", math.nan))
    confidence = float(raw.get("confidence", math.nan))
    if not (0.0 < minimum_mass <= 1.0):
        raise ValueError(f"{rule_id}.minimumMass must be in (0, 1]")
    if not (0.0 < confidence <= 1.0):
        raise ValueError(f"{rule_id}.confidence must be in (0, 1]")

    return SemanticRule(
        rule_id=rule_id,
        mode="constrained",
        hue_arcs=hue_arcs,
        lightness=_pair(
            raw.get("lightness"),
            name=f"{rule_id}.lightness",
            minimum=0.0,
            maximum=1.0,
        ),
        chroma=_pair(
            raw.get("chroma"),
            name=f"{rule_id}.chroma",
            minimum=0.0,
            maximum=0.5,
        ),
        include_neutral=include_neutral,
        minimum_mass=minimum_mass,
        confidence=confidence,
        retrieval_hint=str(raw.get("retrievalHint", "")).strip(),
    )


def load_palette_semantic_policy(path: Path | str) -> dict[str, SemanticRule]:
    policy_path = Path(path)
    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    if raw.get("schemaVersion") != 1:
        raise ValueError("palette semantic policy schemaVersion must be 1")

    default_rule = _parse_rule(
        dict(raw.get("defaultRule", {"mode": "observational"})),
        fallback_id="observational",
    )
    concept_ids: list[str] = []
    bank_name = raw.get("conceptBankPath")
    if bank_name:
        bank_path = (policy_path.parent / str(bank_name)).resolve()
        expected_sha = str(raw.get("conceptBankSha256", "")).lower()
        if not expected_sha or _sha256(bank_path) != expected_sha:
            raise ValueError("palette semantic policy concept bank SHA-256 mismatch")
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        concept_ids = [str(item["concept_id"]) for item in bank["concepts"]]
        if len(concept_ids) != len(set(concept_ids)):
            raise ValueError("concept bank contains duplicate concept ids")

    result = {concept_id: default_rule for concept_id in concept_ids}
    assigned: set[str] = set()
    for raw_rule in raw.get("rules", []):
        rule = _parse_rule(dict(raw_rule), fallback_id="")
        concepts = raw_rule.get("concepts")
        if not isinstance(concepts, list) or not concepts:
            raise ValueError(f"rule {rule.rule_id!r} must list concepts")
        for value in concepts:
            concept_id = str(value)
            if concept_id in assigned:
                raise ValueError(
                    f"concept {concept_id!r} is assigned more than once"
                )
            if concept_ids and concept_id not in result:
                raise ValueError(
                    f"policy references unknown training concept {concept_id!r}"
                )
            assigned.add(concept_id)
            result[concept_id] = rule

    if not result:
        raise ValueError("palette semantic policy covers no concepts")
    return result


def _histogram_bin_coordinates() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    hue = np.full(TOTAL_HISTOGRAM_BINS, np.nan, dtype=np.float64)
    lightness = np.zeros(TOTAL_HISTOGRAM_BINS, dtype=np.float64)
    chroma = np.zeros(TOTAL_HISTOGRAM_BINS, dtype=np.float64)
    neutral = np.zeros(TOTAL_HISTOGRAM_BINS, dtype=bool)

    offset = 0
    for hue_index in range(NUM_HUE_BINS):
        for light_index in range(NUM_LIGHT_BINS):
            for chroma_index in range(NUM_CHROMA_BINS):
                hue[offset] = (hue_index + 0.5) * (360.0 / NUM_HUE_BINS)
                lightness[offset] = float(
                    (LIGHT_EDGES[light_index] + LIGHT_EDGES[light_index + 1]) / 2
                )
                chroma[offset] = float(
                    (CHROMA_EDGES[chroma_index] + CHROMA_EDGES[chroma_index + 1]) / 2
                )
                offset += 1

    for light_index in range(NUM_NEUTRAL_BINS):
        neutral[offset] = True
        lightness[offset] = float(
            (LIGHT_EDGES[light_index] + LIGHT_EDGES[light_index + 1]) / 2
        )
        offset += 1
    return hue, lightness, chroma, neutral


_BIN_HUE, _BIN_LIGHTNESS, _BIN_CHROMA, _BIN_NEUTRAL = (
    _histogram_bin_coordinates()
)


def _hue_mask(arcs: Sequence[tuple[float, float]]) -> np.ndarray:
    selected = np.zeros(TOTAL_HISTOGRAM_BINS, dtype=bool)
    for start, end in arcs:
        if start == 0.0 and end == 360.0:
            selected |= ~_BIN_NEUTRAL
        elif start <= end:
            selected |= (~_BIN_NEUTRAL) & (_BIN_HUE >= start) & (_BIN_HUE <= end)
        else:
            selected |= (~_BIN_NEUTRAL) & ((_BIN_HUE >= start) | (_BIN_HUE <= end))
    return selected


def score_palette_semantics(
    color_prior: np.ndarray,
    rule: SemanticRule,
) -> SemanticScore:
    histogram = np.asarray(color_prior, dtype=np.float64).reshape(-1)
    if histogram.shape != (TOTAL_HISTOGRAM_BINS,):
        raise ValueError(
            f"color_prior must have {TOTAL_HISTOGRAM_BINS} bins"
        )
    if not np.isfinite(histogram).all() or np.any(histogram < 0):
        raise ValueError("color_prior must be finite and non-negative")
    total = float(histogram.sum())
    if total <= 0.0:
        raise ValueError("color_prior must have positive mass")

    if rule.mode == "observational":
        return SemanticScore(score=1.0, passed=True, reason="observational")

    light_mask = (
        (_BIN_LIGHTNESS >= rule.lightness[0])
        & (_BIN_LIGHTNESS <= rule.lightness[1])
    )
    chroma_mask = (
        (_BIN_CHROMA >= rule.chroma[0])
        & (_BIN_CHROMA <= rule.chroma[1])
    )
    selected = _hue_mask(rule.hue_arcs) & light_mask & chroma_mask
    if rule.include_neutral:
        selected |= _BIN_NEUTRAL & light_mask
    score = float(histogram[selected].sum() / total)
    passed = score + 1e-12 >= rule.minimum_mass
    return SemanticScore(
        score=score,
        passed=passed,
        reason="passed" if passed else "matching_mass_below_minimum",
    )


def _normalise_text(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE))


def _protected_prompts(value: Any, key: str = "") -> list[str]:
    prompt_keys = {"prompt", "prompts", "prompt_a", "prompt_b", "en", "ru"}
    found: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key in prompt_keys:
                if isinstance(child, str):
                    found.append(child)
                elif isinstance(child, list):
                    found.extend(item for item in child if isinstance(item, str))
            else:
                found.extend(_protected_prompts(child, child_key))
    elif isinstance(value, list):
        for child in value:
            found.extend(_protected_prompts(child, key))
    return found


def _policy_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _policy_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _policy_strings(child)]
    return []


def validate_policy_anti_leak(
    policy_path: Path | str,
    protected_paths: Sequence[Path | str],
) -> None:
    """Reject protected prompt strings or answer-shaped data in the policy.

    Only prompt-bearing fields are read from protected files; hue ranges and
    reference palettes are intentionally never inspected.
    """
    raw_policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    policy_texts = {
        _normalise_text(item)
        for item in _policy_strings(raw_policy)
        if len(_normalise_text(item).split()) >= 4
    }
    serialised = json.dumps(raw_policy, ensure_ascii=False)
    if re.search(r"#[0-9a-fA-F]{6}\b", serialised):
        raise ValueError("palette semantic policy contains answer-shaped hex data")
    forbidden_keys = {"referencePalettes", "reference_palettes", "expected_hue_range"}
    if forbidden_keys.intersection(raw_policy):
        raise ValueError("palette semantic policy contains benchmark answer fields")

    collisions: list[str] = []
    for protected_path in protected_paths:
        protected = json.loads(Path(protected_path).read_text(encoding="utf-8"))
        for prompt in _protected_prompts(protected):
            normalised = _normalise_text(prompt)
            if len(normalised.split()) >= 4 and normalised in policy_texts:
                collisions.append(normalised)
    if collisions:
        raise ValueError(
            "palette semantic policy contains protected prompt text: "
            + ", ".join(sorted(set(collisions))[:5])
        )
