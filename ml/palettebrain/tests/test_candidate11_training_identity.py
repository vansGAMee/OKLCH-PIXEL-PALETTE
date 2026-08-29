from __future__ import annotations

import argparse

from ml.palettebrain import train_candidate11
from ml.palettebrain import run_candidate11_release


def _args(tmp_path):
    primary = tmp_path / "primary.npz"
    replay = tmp_path / "replay.npz"
    initialize = tmp_path / "stage-a.pt"
    stage_a_report = tmp_path / "stage-a.json"
    for path, value in (
        (primary, b"primary"),
        (replay, b"replay"),
        (initialize, b"stage-a"),
        (stage_a_report, b"evaluation"),
    ):
        path.write_bytes(value)
    return argparse.Namespace(
        stage="b",
        data=str(primary),
        replay_data=[str(replay)],
        initialize_from=str(initialize),
        stage_a_eval_report=str(stage_a_report),
    )


def test_stage_b_identity_changes_with_stage_a_checkpoint(tmp_path) -> None:
    helper = getattr(train_candidate11, "training_input_identity", None)
    assert callable(helper)
    args = _args(tmp_path)
    before = helper(args)
    with open(args.initialize_from, "wb") as destination:
        destination.write(b"changed-stage-a")
    assert helper(args) != before


def test_stage_b_identity_changes_with_gate_and_replay(tmp_path) -> None:
    helper = getattr(train_candidate11, "training_input_identity", None)
    assert callable(helper)
    args = _args(tmp_path)
    before = helper(args)
    with open(args.stage_a_eval_report, "wb") as destination:
        destination.write(b"changed-evaluation")
    assert helper(args) != before
    after_gate = helper(args)
    with open(args.replay_data[0], "wb") as destination:
        destination.write(b"changed-replay")
    assert helper(args) != after_gate


def test_release_validator_uses_the_trainer_dependency_fingerprint(
    tmp_path, monkeypatch,
) -> None:
    smoke_source = tmp_path / "source.npz"
    smoke_source.write_bytes(b"source")
    monkeypatch.setattr(
        run_candidate11_release, "TRAIN_DATA", tmp_path / "engineering_smoke.npz"
    )
    monkeypatch.setattr(run_candidate11_release, "SMOKE_SOURCE", smoke_source)
    assert (
        run_candidate11_release.training_dependency_fingerprint()
        == train_candidate11.training_dependency_fingerprint()
    )
