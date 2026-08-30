"""Offline palette-semantic rescore for an existing Candidate 11 source NPZ.

The command performs no network I/O and never mutates its input.  It filters at
source-group (image) granularity and creates a new versioned archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.palettebrain.c11_palette_semantics import (
    SEMANTIC_MIN_CONCEPT_PASS_FRACTION,
    SEMANTIC_MIN_PASS_IMAGES_PER_CONSTRAINED_CONCEPT,
    SemanticRule,
    load_palette_semantic_policy,
    score_palette_semantics,
    validate_policy_anti_leak,
)


PROTECTED_BENCHMARKS = (
    ROOT / "ml/palettebrain/benchmark_semantic_v3.json",
    ROOT / "ml/palettebrain/benchmark_visual_semantic_v2.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_only_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as target:
            np.savez_compressed(target, **arrays)
            target.flush()
            os.fsync(target.fileno())
        if path.exists():
            raise FileExistsError(
                f"refusing to overwrite existing artifact: {path}"
            )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _create_only_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as target:
            json.dump(payload, target, ensure_ascii=False, indent=2, allow_nan=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        if path.exists():
            raise FileExistsError(
                f"refusing to overwrite existing artifact: {path}"
            )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _group_diagnostics(
    *,
    policy: dict[str, SemanticRule],
    evaluations: list[tuple[str, float, bool, str]],
) -> tuple[dict[str, Any], list[str]]:
    by_concept: dict[str, dict[str, Any]] = {
        concept_id: {
            "mode": rule.mode,
            "ruleId": rule.rule_id,
            "evaluated": 0,
            "passed": 0,
            "rejected": 0,
            "scoreTotal": 0.0,
        }
        for concept_id, rule in policy.items()
    }
    for concept_id, score, passed, _ in evaluations:
        details = by_concept[concept_id]
        details["evaluated"] += 1
        details["passed" if passed else "rejected"] += 1
        details["scoreTotal"] += score

    deficient: list[str] = []
    public: dict[str, dict[str, Any]] = {}
    for concept_id, details in by_concept.items():
        evaluated = int(details["evaluated"])
        passed = int(details["passed"])
        fraction = passed / evaluated if evaluated else 0.0
        row = {key: value for key, value in details.items() if key != "scoreTotal"}
        row["passFraction"] = fraction
        row["meanScore"] = (
            float(details["scoreTotal"]) / evaluated if evaluated else 0.0
        )
        public[concept_id] = row
        if details["mode"] == "constrained" and (
            passed < SEMANTIC_MIN_PASS_IMAGES_PER_CONSTRAINED_CONCEPT
            or fraction < SEMANTIC_MIN_CONCEPT_PASS_FRACTION
        ):
            deficient.append(concept_id)
    return public, sorted(deficient)


def rescore_source(
    *,
    input_path: Path,
    output_path: Path,
    report_path: Path,
    policy_path: Path,
) -> dict[str, Any]:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    report_path = report_path.resolve()
    policy_path = policy_path.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"source archive not found: {input_path}")
    if output_path == input_path or report_path == input_path:
        raise ValueError("versioned output/report must differ from the input")
    for target in (output_path, report_path):
        if target.exists():
            raise FileExistsError(
                f"refusing to overwrite existing artifact: {target}"
            )

    validate_policy_anti_leak(policy_path, PROTECTED_BENCHMARKS)
    policy = load_palette_semantic_policy(policy_path)
    input_sha = sha256_file(input_path)
    policy_sha = sha256_file(policy_path)

    with np.load(input_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    required = {"source_group_id", "image_id", "concept_id", "color_prior"}
    missing = sorted(required - set(arrays))
    if missing:
        raise ValueError(f"source archive lacks semantic rescore fields: {missing}")

    groups = arrays["source_group_id"].astype(str)
    concepts = arrays["concept_id"].astype(str)
    priors = np.asarray(arrays["color_prior"], dtype=np.float32)
    row_count = len(groups)
    if len(concepts) != row_count or len(priors) != row_count:
        raise ValueError("source archive row fields have inconsistent lengths")
    if not set(concepts.tolist()).issubset(policy):
        unknown = sorted(set(concepts.tolist()) - set(policy))
        raise ValueError(f"policy lacks source concepts: {unknown}")

    keep = np.zeros(row_count, dtype=bool)
    row_scores = np.zeros(row_count, dtype=np.float32)
    row_rules = np.empty(row_count, dtype=object)
    evaluations: list[tuple[str, float, bool, str]] = []
    accepted_groups: list[str] = []
    rejected_groups: list[dict[str, Any]] = []

    unique_groups, first_indices = np.unique(groups, return_index=True)
    order = np.argsort(first_indices)
    for group_id in unique_groups[order]:
        indices = np.flatnonzero(groups == group_id)
        group_concepts = set(concepts[indices].tolist())
        if len(group_concepts) != 1:
            raise ValueError(
                f"source group {group_id!r} spans concepts: {sorted(group_concepts)}"
            )
        concept_id = next(iter(group_concepts))
        reference_prior = priors[indices[0]]
        if not np.allclose(priors[indices], reference_prior, rtol=1e-5, atol=1e-7):
            raise ValueError(
                f"source group {group_id!r} has inconsistent color priors"
            )
        rule = policy[concept_id]
        result = score_palette_semantics(reference_prior, rule)
        evaluations.append((concept_id, result.score, result.passed, rule.rule_id))
        row_scores[indices] = result.score
        row_rules[indices] = rule.rule_id
        if result.passed:
            keep[indices] = True
            accepted_groups.append(str(group_id))
        else:
            rejected_groups.append(
                {
                    "sourceGroupId": str(group_id),
                    "imageId": str(arrays["image_id"][indices[0]]),
                    "conceptId": concept_id,
                    "ruleId": rule.rule_id,
                    "score": result.score,
                    "minimumMass": rule.minimum_mass,
                    "reason": result.reason,
                }
            )

    by_concept, deficient = _group_diagnostics(
        policy=policy,
        evaluations=evaluations,
    )
    output_arrays: dict[str, np.ndarray] = {}
    for name, value in arrays.items():
        if value.ndim >= 1 and value.shape[0] == row_count:
            output_arrays[name] = value[keep]
        else:
            output_arrays[name] = value

    output_arrays["palette_semantic_score"] = row_scores[keep]
    output_arrays["palette_semantic_rule_id"] = np.asarray(
        row_rules[keep].tolist(), dtype=str
    )
    output_arrays["palette_semantic_pass"] = np.ones(
        int(keep.sum()), dtype=bool
    )
    if "quality_weight" in output_arrays:
        weights = np.asarray(output_arrays["quality_weight"], dtype=np.float32)
        kept_concepts = concepts[keep]
        confidence = np.asarray(
            [policy[concept_id].confidence for concept_id in kept_concepts],
            dtype=np.float32,
        )
        output_arrays["quality_weight"] = np.minimum(weights, confidence)
    output_arrays["palette_semantic_policy_sha256"] = np.asarray(
        policy_sha, dtype=str
    )
    output_arrays["rescore_source_sha256"] = np.asarray(input_sha, dtype=str)

    _create_only_npz(output_path, output_arrays)
    if sha256_file(input_path) != input_sha:
        raise RuntimeError("input source changed during semantic rescore")
    output_sha = sha256_file(output_path)
    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "reportId": "palettebrain-c11-source-semantic-rescore-v1",
        "testClassification": "REAL_OFFLINE_SOURCE_SEMANTIC_RESCORE",
        "productionReady": False,
        "networkRequests": 0,
        "input": str(input_path).replace("\\", "/"),
        "inputSha256": input_sha,
        "inputRows": row_count,
        "inputUniqueImages": len(unique_groups),
        "output": str(output_path).replace("\\", "/"),
        "outputSha256": output_sha,
        "outputRows": int(keep.sum()),
        "outputUniqueImages": len(accepted_groups),
        "rejectedUniqueImages": len(rejected_groups),
        "policy": str(policy_path).replace("\\", "/"),
        "policySha256": policy_sha,
        "minimumPassImagesPerConstrainedConcept": (
            SEMANTIC_MIN_PASS_IMAGES_PER_CONSTRAINED_CONCEPT
        ),
        "minimumConstrainedConceptPassFraction": (
            SEMANTIC_MIN_CONCEPT_PASS_FRACTION
        ),
        "provenDeficientConcepts": deficient,
        "byConcept": by_concept,
        "rejectedGroups": rejected_groups,
    }
    _create_only_json(report_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescore an existing C11 source archive without network I/O."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--policy",
        default="ml/palettebrain/c11_palette_semantic_policy.v1.json",
    )
    args = parser.parse_args()
    summary = rescore_source(
        input_path=Path(args.input),
        output_path=Path(args.output),
        report_path=Path(args.report),
        policy_path=Path(args.policy),
    )
    console = {
        key: value
        for key, value in summary.items()
        if key not in {"byConcept", "rejectedGroups"}
    }
    console["reportedConcepts"] = len(summary["byConcept"])
    console["reportedRejectedGroups"] = len(summary["rejectedGroups"])
    print(json.dumps(console, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
