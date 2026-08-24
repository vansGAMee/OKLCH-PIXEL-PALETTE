"""Prepare deterministic synthetic 2..9-color decoder training examples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

try:
    from .dataset import (
        SPLIT_IDS,
        build_synthetic_examples,
        dataset_metadata,
    )
except ImportError:
    from dataset import SPLIT_IDS, build_synthetic_examples, dataset_metadata


def parse_counts(raw: str) -> tuple[int, ...]:
    try:
        counts = tuple(sorted(set(int(value.strip()) for value in raw.split(","))))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("counts must be comma-separated integers") from exc
    if not counts or counts[0] < 2 or counts[-1] > 9:
        raise argparse.ArgumentTypeError("counts must be a subset of 2..9")
    return counts


def prepare(args: argparse.Namespace) -> dict[str, object]:
    source_path = Path(args.source)
    output_path = Path(args.output)
    counts = parse_counts(args.counts)

    with np.load(source_path, allow_pickle=False) as source_archive:
        source = {name: np.asarray(source_archive[name]) for name in source_archive.files}
    examples = build_synthetic_examples(
        source,
        counts,
        split_seed=args.split_seed,
        lock_probability=args.lock_probability,
        limit=args.limit,
    )
    source_rows = len(set(int(value) for value in examples["source_indices"]))
    metadata = dataset_metadata(
        source_path=str(source_path.as_posix()),
        source_rows=source_rows,
        example_count=int(examples["counts"].shape[0]),
        counts=counts,
        split_seed=args.split_seed,
        lock_probability=args.lock_probability,
    )
    examples["metadata_json"] = np.asarray(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".tmp")
    try:
        with temporary_path.open("wb") as output_file:
            np.savez_compressed(output_file, **examples)
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    split_counts = {
        split: int((examples["splits"] == split_id).sum())
        for split, split_id in SPLIT_IDS.items()
    }
    result = {
        "output": str(output_path),
        "bytes": output_path.stat().st_size,
        "sourceRows": source_rows,
        "examples": int(examples["counts"].shape[0]),
        "splitExamples": split_counts,
        "counts": list(counts),
        "kind": metadata["kind"],
        "productionReady": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="ml/dataset_embeddings.npz")
    parser.add_argument(
        "--output",
        default="ml/palettebrain/data/palettebrain_synthetic_v1.npz",
    )
    parser.add_argument("--counts", default="2,3,4,5,6,7,8,9")
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--lock-probability", type=float, default=0.25)
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit source rows for a fast plumbing smoke check.",
    )
    args = parser.parse_args()
    print(json.dumps(prepare(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
