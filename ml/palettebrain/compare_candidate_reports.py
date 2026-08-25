"""Paired real-holdout comparison for frozen PaletteBrain evaluations."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


BOOTSTRAP_SEED = 20260825
BOOTSTRAP_ITERATIONS = 10_000


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_report(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"evaluation report must be an object: {path}")
    return value


def _metric_rows(
    report: Mapping[str, Any], key: str
) -> tuple[list[int], np.ndarray]:
    holdout = report.get("realPaletteHoldout")
    if not isinstance(holdout, Mapping) or holdout.get("status") != "evaluated":
        raise ValueError("both reports must contain an evaluated real holdout")
    if int(holdout.get("invalidPredictionRows", -1)) != 0:
        raise ValueError("paired comparison requires zero invalid holdout predictions")
    indices = [int(value) for value in holdout.get("selectedRowIndices", [])]
    if key == "matchedOklab":
        raw = holdout.get("matchedOklab", {}).get("set_distances", [])
    elif key == "lightnessDistribution":
        raw = holdout.get("lightnessDistribution", {}).get("perPaletteErrors", [])
    else:  # pragma: no cover - internal misuse
        raise ValueError(f"unsupported paired metric: {key}")
    values = np.asarray(raw, dtype=np.float64)
    if values.shape != (len(indices),) or not np.isfinite(values).all():
        raise ValueError(f"{key} rows must be finite and align with selected indices")
    return indices, values


def _group_bootstrap(
    deltas: np.ndarray,
    group_ids: Sequence[str],
    *,
    seed: int = BOOTSTRAP_SEED,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for group_id, delta in zip(group_ids, deltas, strict=True):
        grouped[str(group_id)].append(float(delta))
    names = sorted(grouped)
    if len(names) < 2:
        raise ValueError("paired holdout comparison requires at least two source groups")
    group_means = np.asarray(
        [np.mean(grouped[name]) for name in names], dtype=np.float64
    )
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(names), size=(iterations, len(names)))
    bootstrap_means = group_means[draws].mean(axis=1)
    lower, upper = np.quantile(bootstrap_means, [0.025, 0.975])
    point = float(group_means.mean())
    return {
        "aggregation": "equal_weight_mean_of_source_group_means",
        "sourceGroupCount": len(names),
        "bootstrapSeed": seed,
        "bootstrapIterations": iterations,
        "candidateMinusBaselineMean": point,
        "confidenceInterval95": {"lower": float(lower), "upper": float(upper)},
        "improvedSourceGroupFraction": float(np.mean(group_means < 0.0)),
        "perSourceGroup": [
            {
                "sourceGroupId": name,
                "rowCount": len(grouped[name]),
                "candidateMinusBaselineMean": float(group_means[index]),
            }
            for index, name in enumerate(names)
        ],
    }


def _direct_accuracy(report: Mapping[str, Any], *keys: str) -> float:
    value: Any = report["directColor"]["aggregate"]
    for key in keys:
        value = value[key]
    return float(value)


def compare_reports(
    baseline_report: str | Path,
    candidate_report: str | Path,
    data_path: str | Path,
) -> dict[str, Any]:
    baseline_path = Path(baseline_report).resolve()
    candidate_path = Path(candidate_report).resolve()
    archive_path = Path(data_path).resolve()
    baseline = _load_report(baseline_path)
    candidate = _load_report(candidate_path)
    archive_sha256 = sha256_file(archive_path)
    baseline_dataset_sha = str(baseline.get("dataset", {}).get("sha256", ""))
    candidate_dataset_sha = str(candidate.get("dataset", {}).get("sha256", ""))
    if not (
        archive_sha256 == baseline_dataset_sha == candidate_dataset_sha
    ):
        raise ValueError("baseline, candidate, and archive SHA-256 must match")

    baseline_indices, baseline_set = _metric_rows(baseline, "matchedOklab")
    candidate_indices, candidate_set = _metric_rows(candidate, "matchedOklab")
    if baseline_indices != candidate_indices:
        raise ValueError("baseline and candidate selected different holdout rows")
    _, baseline_lightness = _metric_rows(baseline, "lightnessDistribution")
    _, candidate_lightness = _metric_rows(candidate, "lightnessDistribution")

    with np.load(archive_path, allow_pickle=False) as archive:
        if "source_group_ids" not in archive:
            raise ValueError("archive has no source_group_ids for independent comparison")
        group_ids = np.asarray(archive["source_group_ids"])[baseline_indices].astype(str)
        if "holdout_eligible" in archive and not np.asarray(
            archive["holdout_eligible"]
        )[baseline_indices].all():
            raise ValueError("paired rows include a non-holdout-eligible record")

    matched = _group_bootstrap(candidate_set - baseline_set, group_ids)
    matched.update(
        {
            "rowCount": len(baseline_indices),
            "baselineMeanSetDistance": float(np.mean(baseline_set)),
            "candidateMeanSetDistance": float(np.mean(candidate_set)),
        }
    )
    lightness = _group_bootstrap(
        candidate_lightness - baseline_lightness, group_ids
    )
    lightness.update(
        {
            "rowCount": len(baseline_indices),
            "baselineMeanError": float(np.mean(baseline_lightness)),
            "candidateMeanError": float(np.mean(candidate_lightness)),
        }
    )
    interval = matched["confidenceInterval95"]
    materially_better = bool(
        matched["candidateMinusBaselineMean"] < 0.0 and interval["upper"] < 0.0
    )

    def delta(*keys: str) -> dict[str, float]:
        left = _direct_accuracy(baseline, *keys)
        right = _direct_accuracy(candidate, *keys)
        return {"baseline": left, "candidate": right, "delta": right - left}

    return {
        "schemaVersion": 1,
        "status": "paired_candidate_comparison_complete",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "productionReady": False,
        "promotionPerformed": False,
        "baselineModelLabel": baseline.get("modelLabel"),
        "candidateModelLabel": candidate.get("modelLabel"),
        "evidence": {
            "datasetSha256": archive_sha256,
            "baselineReportSha256": sha256_file(baseline_path),
            "candidateReportSha256": sha256_file(candidate_path),
            "identicalHoldoutRows": True,
            "allHoldoutPredictionsFinite": True,
        },
        "realPaletteHoldout": {
            "matchedOklab": matched,
            "lightnessDistribution": lightness,
            "materiallyImprovesRealHoldout": materially_better,
            "decisionRule": (
                "candidate-minus-baseline equal-source-group mean and upper 95% "
                "group-bootstrap bound must both be below zero"
            ),
        },
        "directColor": {
            "raw": delta("raw_direct_color", "accuracy"),
            "en": delta("raw_direct_color_by_language", "en", "accuracy"),
            "ru": delta("raw_direct_color_by_language", "ru", "accuracy"),
            "multiColor": delta("multi_color_anchor", "accuracy"),
            "exclusion": delta("exclusion", "accuracy"),
        },
        "note": (
            "This paired offline comparison is necessary but cannot promote a "
            "model; candidate ONNX and exact q8 browser gates remain separate."
        ),
    }


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = compare_reports(args.baseline, args.candidate, args.data)
    output_path = Path(args.output).resolve()
    _atomic_write(output_path, result)
    summary = {
        "status": result["status"],
        "materiallyImprovesRealHoldout": result["realPaletteHoldout"][
            "materiallyImprovesRealHoldout"
        ],
        "candidateMinusBaselineMean": result["realPaletteHoldout"][
            "matchedOklab"
        ]["candidateMinusBaselineMean"],
        "output": str(output_path.as_posix()),
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
