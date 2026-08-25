from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ml.palettebrain.compare_candidate_reports import compare_reports


def _report(path: Path, dataset_sha: str, distances: list[float]) -> None:
    lightness = [value / 2.0 for value in distances]
    value = {
        "modelLabel": path.stem,
        "dataset": {"sha256": dataset_sha},
        "realPaletteHoldout": {
            "status": "evaluated",
            "selectedRowIndices": [0, 1, 2, 3],
            "validPredictionRows": 4,
            "invalidPredictionRows": 0,
            "matchedOklab": {"set_distances": distances},
            "lightnessDistribution": {"perPaletteErrors": lightness},
        },
        "directColor": {
            "aggregate": {
                "raw_direct_color": {"accuracy": 0.5},
                "raw_direct_color_by_language": {
                    "en": {"accuracy": 0.5},
                    "ru": {"accuracy": 0.5},
                },
                "multi_color_anchor": {"accuracy": 0.5},
                "exclusion": {"accuracy": 0.5},
            }
        },
    }
    path.write_text(json.dumps(value), encoding="utf-8")


def test_group_paired_bootstrap_recognizes_clear_improvement(tmp_path: Path) -> None:
    data = tmp_path / "candidate.npz"
    np.savez_compressed(
        data,
        source_group_ids=np.asarray(["a", "a", "b", "b"]),
        holdout_eligible=np.ones(4, dtype=np.bool_),
    )
    import hashlib

    dataset_sha = hashlib.sha256(data.read_bytes()).hexdigest()
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    _report(baseline, dataset_sha, [0.3, 0.3, 0.4, 0.4])
    _report(candidate, dataset_sha, [0.1, 0.1, 0.2, 0.2])

    result = compare_reports(baseline, candidate, data)

    comparison = result["realPaletteHoldout"]
    assert comparison["materiallyImprovesRealHoldout"] is True
    assert comparison["matchedOklab"]["sourceGroupCount"] == 2
    assert comparison["matchedOklab"]["confidenceInterval95"]["upper"] < 0
    assert result["productionReady"] is False


def test_comparison_rejects_dataset_or_validity_mismatch(tmp_path: Path) -> None:
    data = tmp_path / "candidate.npz"
    np.savez_compressed(
        data,
        source_group_ids=np.asarray(["a", "a", "b", "b"]),
        holdout_eligible=np.ones(4, dtype=np.bool_),
    )
    import hashlib

    dataset_sha = hashlib.sha256(data.read_bytes()).hexdigest()
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    _report(baseline, dataset_sha, [0.3, 0.3, 0.4, 0.4])
    _report(candidate, "0" * 64, [0.1, 0.1, 0.2, 0.2])
    with pytest.raises(ValueError, match="SHA-256"):
        compare_reports(baseline, candidate, data)

    _report(candidate, dataset_sha, [0.1, 0.1, 0.2, 0.2])
    value = json.loads(candidate.read_text(encoding="utf-8"))
    value["realPaletteHoldout"]["invalidPredictionRows"] = 1
    candidate.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="zero invalid"):
        compare_reports(baseline, candidate, data)
