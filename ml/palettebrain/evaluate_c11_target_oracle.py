"""Read-only semantic-family oracle over existing Candidate 11 full-photo targets.

Frozen benchmark text is used exclusively at evaluation time.  This module does
not write datasets, checkpoints, or any training-facing artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

try:
    from .color_math import representation_to_oklab_numpy
    from .e5_embedding import embed_texts, load_encoder
    from .inspect_semantics import _family_distance, _family_references
except ImportError:
    from color_math import representation_to_oklab_numpy
    from e5_embedding import embed_texts, load_encoder
    from inspect_semantics import _family_distance, _family_references


def normalized(values: np.ndarray) -> np.ndarray:
    return values / np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-12)


def evaluate_oracle(
    *,
    dataset: Path,
    benchmark_v2: Path,
    cache_dir: str,
    split: str = "test",
) -> dict[str, Any]:
    """Measure what genuine target palettes can score without model inference.

    ``paletteUpperBound`` ignores text to establish whether real full-photo
    palettes can ever satisfy each frozen family. ``textRetrievalOracle`` then
    uses only stored E5 target-prompt embeddings to select the nearest existing
    held-out target for each frozen prompt.
    """
    with np.load(dataset, allow_pickle=False) as archive:
        required = {"target", "count", "split", "text_embedding", "prompt", "source_group_id"}
        missing = sorted(required - set(archive.files))
        if missing:
            raise RuntimeError(f"dataset missing oracle fields: {missing}")
        indices = np.flatnonzero(archive["split"].astype(str) == split)
        targets = np.asarray(archive["target"][indices], dtype=np.float32)
        counts = np.asarray(archive["count"][indices], dtype=np.int64)
        embeddings = np.asarray(archive["text_embedding"][indices], dtype=np.float32)
        prompts = archive["prompt"][indices].astype(str)
        groups = archive["source_group_id"][indices].astype(str)
    if len(indices) == 0:
        raise RuntimeError(f"no {split!r} rows available for target oracle")

    palettes = representation_to_oklab_numpy(targets)
    references, _ = _family_references(benchmark_v2)
    benchmark = json.loads(benchmark_v2.read_text(encoding="utf-8"))
    all_prompts = [
        prompt
        for record in benchmark["concepts"].values()
        for prompt in record["prompts"]
    ]
    encoder = load_encoder(device="auto", cache_dir=cache_dir)
    frozen_embeddings = embed_texts(all_prompts, encoder=encoder, batch_size=64)
    candidate_embeddings = normalized(embeddings)
    frozen_embeddings = normalized(frozen_embeddings)
    prompt_embedding = dict(zip(all_prompts, frozen_embeddings, strict=True))

    family_rows: list[dict[str, Any]] = []
    palette_upper_rows: list[dict[str, Any]] = []
    for family, record in benchmark["concepts"].items():
        classified = np.asarray([
            _family_distance(palette[:count], references)[0][0]
            for palette, count in zip(palettes, counts, strict=True)
        ])
        matching = np.flatnonzero(classified == family)
        palette_upper_rows.append({
            "expected": family,
            "matchingRealTargetRows": int(len(matching)),
            "pass": bool(len(matching)),
        })
        for prompt in record["prompts"]:
            similarities = candidate_embeddings @ prompt_embedding[prompt]
            selected = int(np.argmax(similarities))
            closest = str(classified[selected])
            family_rows.append({
                "prompt": prompt,
                "expected": family,
                "closest": closest,
                "pass": closest == family,
                "retrievalCosine": float(similarities[selected]),
                "sourcePrompt": str(prompts[selected]),
                "sourceGroupId": str(groups[selected]),
            })

    return {
        "schemaVersion": 1,
        "testClassification": "READ_ONLY_REAL_TARGET_ORACLE",
        "trainingDataModified": False,
        "networkRequests": 0,
        "dataset": str(dataset).replace("\\", "/"),
        "evaluationSplit": split,
        "targetRows": int(len(indices)),
        "targetGroups": int(len(set(groups.tolist()))),
        "paletteUpperBoundFamilyWin": float(np.mean([row["pass"] for row in palette_upper_rows])),
        "textRetrievalTargetFamilyWin": float(np.mean([row["pass"] for row in family_rows])),
        "meanRetrievalCosine": float(np.mean([row["retrievalCosine"] for row in family_rows])),
        "paletteUpperRows": palette_upper_rows,
        "familyRows": family_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--benchmark-v2", default="ml/palettebrain/benchmark_visual_semantic_v2.json", type=Path)
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite oracle report: {args.output}")
    result = evaluate_oracle(
        dataset=args.dataset,
        benchmark_v2=args.benchmark_v2,
        cache_dir=args.cache_dir,
        split=args.split,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
