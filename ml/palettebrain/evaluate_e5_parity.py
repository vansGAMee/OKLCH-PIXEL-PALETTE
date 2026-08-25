"""Compare pinned CUDA E5 embeddings with the shipped local q8 WASM path."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

try:
    from .e5_embedding import (
        BROWSER_E5_MODEL_ID,
        BROWSER_E5_REVISION,
        BROWSER_E5_SHA256,
        E5_MODEL_ID,
        E5_REVISION,
        MAX_CONTEXT_TOKENS,
        QUERY_PREFIX,
        embed_texts,
        load_encoder,
        parity_metrics,
    )
except ImportError:
    from e5_embedding import (  # type: ignore[no-redef]
        BROWSER_E5_MODEL_ID,
        BROWSER_E5_REVISION,
        BROWSER_E5_SHA256,
        E5_MODEL_ID,
        E5_REVISION,
        MAX_CONTEXT_TOKENS,
        QUERY_PREFIX,
        embed_texts,
        load_encoder,
        parity_metrics,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expanded_prompts(fixture: dict[str, Any]) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    texts: list[str] = []
    for item in fixture["prompts"]:
        repeat = int(item.get("repeat", 1))
        if repeat < 1:
            raise ValueError("parity repeat must be positive")
        ids.append(str(item["id"]))
        texts.append(" ".join([str(item["text"])] * repeat))
    return ids, texts


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    fixture_path = Path(args.fixture)
    browser_path = Path(args.browser_output)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    browser = json.loads(browser_path.read_text(encoding="utf-8"))
    ids, texts = expanded_prompts(fixture)
    browser_by_id = {str(item["id"]): item for item in browser["results"]}
    if set(browser_by_id) != set(ids):
        raise ValueError("browser parity output does not match frozen fixture ids")
    browser_embeddings = np.asarray(
        [browser_by_id[item_id]["embedding"] for item_id in ids], dtype=np.float32
    )

    encoder = load_encoder(
        device=args.device,
        cache_dir=args.cache_dir,
        local_files_only=not args.allow_download,
    )
    cuda_embeddings = embed_texts(texts, encoder=encoder, batch_size=args.batch_size)
    aggregate = parity_metrics(browser_embeddings, cuda_embeddings)
    per_prompt: list[dict[str, Any]] = []
    for index, item_id in enumerate(ids):
        metrics = parity_metrics(
            browser_embeddings[index : index + 1],
            cuda_embeddings[index : index + 1],
        )
        tokenized = encoder.tokenizer(  # type: ignore[operator]
            QUERY_PREFIX + texts[index], truncation=False
        )
        per_prompt.append(
            {
                "id": item_id,
                "untruncatedTokens": len(tokenized["input_ids"]),
                "effectiveTokens": min(len(tokenized["input_ids"]), MAX_CONTEXT_TOKENS),
                "cosine": metrics["meanCosine"],
                "meanAbsoluteError": metrics["meanAbsoluteError"],
                "maximumAbsoluteError": metrics["maximumAbsoluteError"],
            }
        )

    thresholds = fixture["releaseThresholds"]
    passed = (
        aggregate["meanCosine"] >= float(thresholds["meanCosine"])
        and aggregate["minimumCosine"] >= float(thresholds["minimumCosine"])
    )
    runtime = browser.get("runtime", {})
    return {
        "schemaVersion": 1,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "fixtureVersion": fixture["fixtureVersion"],
        "fixtureSha256": sha256_file(fixture_path),
        "browserOutputSha256": sha256_file(browser_path),
        "pytorchEncoder": {
            "modelId": E5_MODEL_ID,
            "revision": E5_REVISION,
            "device": str(encoder.device),
        },
        "browserEncoder": {
            "modelId": BROWSER_E5_MODEL_ID,
            "revision": BROWSER_E5_REVISION,
            "artifactSha256": BROWSER_E5_SHA256,
            "backend": runtime.get("backend"),
            "packages": runtime.get("packages"),
            "artifacts": runtime.get("artifacts"),
        },
        "contract": {
            "prefix": QUERY_PREFIX,
            "maximumContextTokens": MAX_CONTEXT_TOKENS,
            "pooling": "attention-mask mean pooling followed by L2 normalization",
            "dimensions": int(cuda_embeddings.shape[1]),
        },
        "thresholds": thresholds,
        "metrics": aggregate,
        "perPrompt": per_prompt,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture", default="ml/palettebrain/e5_parity_prompts.v1.json"
    )
    parser.add_argument(
        "--browser-output", default="ml/.cache/e5_browser_parity.json"
    )
    parser.add_argument(
        "--output", default="ml/palettebrain/reports/e5-parity.v1.json"
    )
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--allow-download", action="store_true")
    args = parser.parse_args()
    result = evaluate(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "status": result["status"],
                "metrics": result["metrics"],
                "output": str(output_path),
            },
            sort_keys=True,
        )
    )
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
