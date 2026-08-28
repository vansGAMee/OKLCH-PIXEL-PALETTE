"""Bounded DEV-only checkpoint selection for Candidate 11."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import torch

try:
    from .evaluate_semantic_v3 import evaluate
    from .train_candidate11 import training_dependency_fingerprint
except ImportError:
    from evaluate_semantic_v3 import evaluate
    from train_candidate11 import training_dependency_fingerprint


def selection_key(report: dict[str, Any], validation_loss: float) -> tuple[Any, ...]:
    metrics = report.get("metrics", {})
    engineering_valid = (
        metrics.get("count") == 1.0
        and metrics.get("inactive") == 1.0
        and metrics.get("gamut") == 1.0
        and metrics.get("determinism") == 1.0
        and float(metrics.get("directEn", 0.0)) >= 0.20
        and float(metrics.get("directRu", 0.0)) >= 0.20
        and float(metrics.get("nearDuplicateRate", 1.0)) < 0.95
    )
    return (
        int(engineering_valid),
        float(metrics.get("semanticFamilyWin", 0.0)),
        float(metrics.get("paletteStructureWinRate") or 0.0),
        float(metrics.get("ruEnSemanticAgreement", 0.0)),
        -float(metrics.get("nearDuplicateRate", 1.0)),
        -float(validation_loss),
    )


def atomic_copy(source: Path, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select(args: argparse.Namespace) -> dict[str, Any]:
    prefix = args.output.stem.removesuffix("-best")
    candidates = sorted(args.output.parent.glob(f"{prefix}-dev-epoch-*{args.output.suffix}"))
    last_path = args.output.with_name(f"{prefix}-last{args.output.suffix}")
    if last_path.is_file():
        candidates.append(last_path)
    if not candidates:
        raise RuntimeError("no bounded DEV checkpoint candidates were retained")
    rows: list[dict[str, Any]] = []
    expected_training_args = {
        "stage": args.stage,
        "epochs": 1 if args.engineering_smoke else (30 if args.stage == "a" else 20),
        "batch_size": 32,
        "new_lr": 3e-4 if args.stage == "a" else 1e-4,
        "inherited_lr": 2e-5,
        "seed": 20260826,
    }
    expected_dependency = training_dependency_fingerprint()
    for candidate in candidates:
        checkpoint = torch.load(candidate, map_location="cpu", weights_only=True)
        candidate_args = checkpoint.get("training_args", {})
        if (
            checkpoint.get("candidate") != "candidate-11"
            or checkpoint.get("stage") != args.stage
            or checkpoint.get("dataset_identity", {}).get("primary") != sha256_file(Path(args.dataset))
            or checkpoint.get("dependency_fingerprint") != expected_dependency
            or any(candidate_args.get(key) != value for key, value in expected_training_args.items())
        ):
            continue
        history = checkpoint.get("history", [])
        validation_loss = float(history[-1]["val"]["loss"])
        report_path = args.report.parent / f"{args.report.stem}-{candidate.stem}.json"
        evaluation_args = argparse.Namespace(
            checkpoint=str(candidate), benchmark_v2=args.benchmark_v2,
            benchmark_v3=args.benchmark_v3, cache_dir=args.cache_dir,
            parity_report=args.parity_report, browser_smoke_report=None,
            device=args.device, output=str(report_path), dataset=args.dataset,
            evaluation_split="val",
            engineering_smoke=args.engineering_smoke,
        )
        report = evaluate(evaluation_args)
        row = {
            "checkpoint": candidate.as_posix(), "report": report_path.as_posix(),
            "validationLoss": validation_loss, "metrics": report["metrics"],
        }
        row["selectionKey"] = list(selection_key(report, validation_loss))
        rows.append(row)
    if not rows:
        raise RuntimeError("no compatible bounded DEV checkpoints remain")
    selected = max(rows, key=lambda row: tuple(row["selectionKey"]))
    if selected["selectionKey"][0] != 1:
        raise RuntimeError("all bounded DEV candidates are catastrophically invalid")
    atomic_copy(Path(selected["checkpoint"]), args.output)
    selection = {
        "schemaVersion": 1, "candidate": "candidate-11", "stage": args.stage,
        "testClassification": "ENGINEERING_SMOKE_ONLY" if args.engineering_smoke else "DEV_CHECKPOINT_SELECTION",
        "productionReady": False,
        "selectionOrder": [
            "engineering validity", "semantic quality", "palette structure",
            "RU/EN agreement", "near-duplicate avoidance", "validation loss",
        ],
        "selectedCheckpoint": args.output.as_posix(),
        "selectedCheckpointSha256": sha256_file(args.output),
        "datasetSha256": sha256_file(Path(args.dataset)),
        "selectedSourceCheckpoint": selected["checkpoint"],
        "candidates": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return selection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("a", "b"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--benchmark-v2", default="ml/palettebrain/benchmark_visual_semantic_v2.json")
    parser.add_argument("--benchmark-v3", default="ml/palettebrain/benchmark_semantic_v3.json")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--parity-report", default="ml/palettebrain/reports/candidate-11-parity.json")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--engineering-smoke", action="store_true")
    args = parser.parse_args()
    print(json.dumps(select(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
