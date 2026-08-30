from ml.palettebrain.select_candidate11_checkpoint import selection_key
import argparse
import hashlib
from pathlib import Path

import ml.palettebrain.select_candidate11_checkpoint as selector


def _report(**overrides):
    metrics = {
        "count": 1.0, "inactive": 1.0, "gamut": 1.0, "determinism": 1.0,
        "directEn": 0.8, "directRu": 0.8, "nearDuplicateRate": 0.1,
        "semanticFamilyWin": 0.7, "paletteStructureWinRate": 0.6,
        "ruEnSemanticAgreement": 0.8,
    }
    metrics.update(overrides)
    return {"metrics": metrics}


def test_semantics_and_structure_outrank_validation_loss() -> None:
    better_dev = selection_key(_report(semanticFamilyWin=0.8), 2.0)
    lower_loss = selection_key(_report(semanticFamilyWin=0.7), 0.1)
    assert better_dev > lower_loss


def test_engineering_invalid_candidate_is_rejected_first() -> None:
    invalid = selection_key(_report(count=0.0, semanticFamilyWin=1.0), 0.01)
    valid = selection_key(_report(semanticFamilyWin=0.1), 10.0)
    assert valid > invalid


def test_checkpoint_selection_uses_dev_only_and_accepts_save_contract_resume(tmp_path, monkeypatch) -> None:
    dataset = tmp_path / "data.npz"
    dataset.write_bytes(b"dataset")
    output = tmp_path / "stage-a-best.pt"
    candidate = tmp_path / "stage-a-dev-epoch-001.pt"
    candidate.write_bytes(b"checkpoint")
    expected_dependency = "05bb4b0691c3ae52e5a49a3d5afdaa04f0ec224f776726d1539332f77b2c44d3"
    checkpoint = {
        "candidate": "candidate-11", "stage": "a",
        "dataset_identity": {"primary": hashlib.sha256(b"dataset").hexdigest()},
        "dependency_fingerprint": expected_dependency,
        "training_args": {
            "stage": "a", "epochs": 30, "batch_size": 32,
            "new_lr": 3e-4, "inherited_lr": 2e-5, "seed": 20260826,
        },
        "history": [{"val": {"loss": 1.0}}],
    }
    seen_splits = []
    monkeypatch.setattr(selector.torch, "load", lambda *_args, **_kwargs: checkpoint)
    monkeypatch.setattr(selector, "training_dependency_fingerprint", lambda: "current-dependency")
    monkeypatch.setattr(selector, "atomic_copy", lambda _source, destination: destination.write_bytes(b"best"))
    def evaluate(args):
        seen_splits.append(args.evaluation_split)
        return _report()
    monkeypatch.setattr(selector, "evaluate", evaluate)
    args = argparse.Namespace(
        output=output, report=tmp_path / "selection.json", dataset=str(dataset),
        stage="a", benchmark_v2="dev-v2.json", benchmark_v3="dev-v3.json",
        cache_dir="cache", parity_report="parity.json", device="cpu",
        engineering_smoke=False,
    )
    selector.select(args)
    assert seen_splits == ["val"]
