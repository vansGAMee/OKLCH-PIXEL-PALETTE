from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from ml.palettebrain.c11_palette_semantics import (
    SemanticRule,
    load_palette_semantic_policy,
    score_palette_semantics,
    validate_policy_anti_leak,
)
from ml.palettebrain.color_distribution import (
    palette_or_pixels_to_oklch_histogram,
)


ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "ml/palettebrain/c11_palette_semantic_policy.v1.json"
CONCEPTS = ROOT / "ml/palettebrain/c11_training_concepts.v1.json"
PROTECTED = (
    ROOT / "ml/palettebrain/benchmark_semantic_v3.json",
    ROOT / "ml/palettebrain/benchmark_visual_semantic_v2.json",
)


def _histogram(*colors: tuple[float, float, float, float]) -> np.ndarray:
    oklab: list[list[float]] = []
    weights: list[float] = []
    for lightness, chroma, hue_degrees, weight in colors:
        hue = math.radians(hue_degrees)
        oklab.append(
            [lightness, chroma * math.cos(hue), chroma * math.sin(hue)]
        )
        weights.append(weight)
    return palette_or_pixels_to_oklch_histogram(
        np.asarray(oklab, dtype=np.float32),
        np.asarray(weights, dtype=np.float32),
    )


def test_constrained_rule_accepts_matching_palette_and_rejects_wrong_hue() -> None:
    rule = SemanticRule(
        rule_id="green-vegetation",
        mode="constrained",
        hue_arcs=((105.0, 170.0),),
        lightness=(0.20, 0.90),
        chroma=(0.03, 0.30),
        include_neutral=False,
        minimum_mass=0.55,
        confidence=0.90,
    )

    matching = _histogram((0.60, 0.14, 135.0, 0.80), (0.45, 0.02, 0.0, 0.20))
    wrong = _histogram((0.55, 0.14, 55.0, 0.85), (0.40, 0.02, 0.0, 0.15))

    accepted = score_palette_semantics(matching, rule)
    rejected = score_palette_semantics(wrong, rule)

    assert accepted.passed
    assert accepted.score >= rule.minimum_mass
    assert not rejected.passed
    assert rejected.score < rule.minimum_mass
    assert rejected.reason == "matching_mass_below_minimum"


def test_observational_rule_does_not_assert_a_hue_answer() -> None:
    rule = SemanticRule(
        rule_id="observational",
        mode="observational",
        hue_arcs=(),
        lightness=(0.0, 1.0),
        chroma=(0.0, 1.0),
        include_neutral=True,
        minimum_mass=0.0,
        confidence=1.0,
    )
    result = score_palette_semantics(_histogram((0.5, 0.1, 280.0, 1.0)), rule)
    assert result.passed
    assert result.score == pytest.approx(1.0)
    assert result.reason == "observational"


def test_real_policy_covers_each_training_concept_without_prompt_or_answer_leakage() -> None:
    policy = load_palette_semantic_policy(POLICY)
    concepts = json.loads(CONCEPTS.read_text(encoding="utf-8"))["concepts"]

    assert set(policy) == {str(concept["concept_id"]) for concept in concepts}
    assert all(
        len(rule.retrieval_hint.split()) <= 2
        for rule in policy.values()
        if rule.mode == "constrained"
    )
    validate_policy_anti_leak(POLICY, PROTECTED)


def test_policy_loader_rejects_duplicate_concept_assignment(tmp_path: Path) -> None:
    policy_path = tmp_path / "duplicate.json"
    policy_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "conceptBankSha256": "0" * 64,
                "defaultRule": {"mode": "observational"},
                "rules": [
                    {
                        "id": "one",
                        "mode": "constrained",
                        "concepts": ["same"],
                        "hueArcs": [[0, 30]],
                        "lightness": [0.1, 0.9],
                        "chroma": [0.03, 0.3],
                        "includeNeutral": False,
                        "minimumMass": 0.5,
                        "confidence": 0.8,
                    },
                    {
                        "id": "two",
                        "mode": "constrained",
                        "concepts": ["same"],
                        "hueArcs": [[30, 60]],
                        "lightness": [0.1, 0.9],
                        "chroma": [0.03, 0.3],
                        "includeNeutral": False,
                        "minimumMass": 0.5,
                        "confidence": 0.8,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="assigned more than once"):
        load_palette_semantic_policy(policy_path)
