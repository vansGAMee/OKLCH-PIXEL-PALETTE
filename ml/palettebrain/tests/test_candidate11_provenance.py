from __future__ import annotations

import hashlib
import json

from ml.palettebrain import run_candidate11_release
from ml.palettebrain.run_candidate11_release import training_artifact_matches_source


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_training_artifact_is_rejected_when_visual_source_changes(tmp_path) -> None:
    source = tmp_path / "source.npz"
    training = tmp_path / "training.npz"
    report = tmp_path / "audit.json"
    source.write_bytes(b"visual-source-v1")
    training.write_bytes(b"training-data")
    report.write_text(json.dumps({
        "pass": True,
        "sha256": _sha(training),
        "sourceSha256": _sha(source),
    }), encoding="utf-8")
    assert training_artifact_matches_source(report, training, source)
    source.write_bytes(b"visual-source-v2")
    assert not training_artifact_matches_source(report, training, source)


def test_release_rejects_structurally_valid_failed_qualification(tmp_path) -> None:
    qualification_artifact_valid = getattr(
        run_candidate11_release, "qualification_artifact_valid", None
    )
    assert callable(qualification_artifact_valid)
    checkpoint = tmp_path / "stage-b.pt"
    dataset = tmp_path / "dataset.npz"
    checkpoint.write_bytes(b"checkpoint")
    dataset.write_bytes(b"dataset")
    manifest = {"decoder": {"sha256": "decoder"}}
    report = {
        "candidate": "candidate-11",
        "pass": False,
        "productionReady": False,
        "manifestDecoderSha256": "decoder",
        "checkpointSha256": _sha(checkpoint),
        "datasetSha256": _sha(dataset),
    }
    assert not qualification_artifact_valid(report, manifest, checkpoint, dataset)
    report["testClassification"] = "ENGINEERING_SMOKE_ONLY"
    assert qualification_artifact_valid(
        report, manifest, checkpoint, dataset, require_success=False
    )
    report["pass"] = True
    report["productionReady"] = True
    assert qualification_artifact_valid(report, manifest, checkpoint, dataset)


def test_stage_a_probe_contract_preserves_base_and_requires_clear_family_gain() -> None:
    base = {
        "semanticFamilyWin": 0.06,
        "directEn": 4 / 7,
        "directRu": 1.0,
        "basicConcepts": 0.15,
        "paletteStructureWinRate": 0.459,
    }
    passing = {
        "semanticFamilyWin": 0.15,
        "directEn": 4 / 7,
        "directRu": 1.0,
        "basicConcepts": 0.15,
        "paletteStructureWinRate": 0.42,
    }
    valid, evidence = run_candidate11_release.probe_metrics_contract(base, passing)
    assert valid
    assert evidence["minimumSemanticFamilyWin"] == 0.15
    assert evidence["failures"] == []

    broken = {**passing, "semanticFamilyWin": 0.14, "directRu": 0.0}
    valid, evidence = run_candidate11_release.probe_metrics_contract(base, broken)
    assert not valid
    assert any("semanticFamilyWin" in value for value in evidence["failures"])
    assert any("directRu" in value for value in evidence["failures"])
