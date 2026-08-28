from __future__ import annotations

import hashlib
import json

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
