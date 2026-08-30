from __future__ import annotations

from pathlib import Path

from ml.palettebrain import train_candidate11 as trainer


def test_checkpoint_replace_retries_only_winerror_five_without_removing_destination(
    tmp_path, monkeypatch
) -> None:
    destination = tmp_path / "last.pt"
    temporary = tmp_path / "last.pt.tmp"
    destination.write_bytes(b"known-good-checkpoint")
    temporary.write_bytes(b"new-checkpoint")
    real_replace = trainer.os.replace
    calls = 0
    delays: list[float] = []

    def transient_replace(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            error = PermissionError(13, "sharing violation", str(target))
            error.winerror = 5
            raise error
        real_replace(source, target)

    monkeypatch.setattr(trainer.os, "replace", transient_replace)
    monkeypatch.setattr(trainer.time, "sleep", delays.append)

    trainer.atomic_checkpoint_replace(temporary, destination, attempts=4)

    assert calls == 3
    assert delays == [0.05, 0.1]
    assert destination.read_bytes() == b"new-checkpoint"
    assert not temporary.exists()
