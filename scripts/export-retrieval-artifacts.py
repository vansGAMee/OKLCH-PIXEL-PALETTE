from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


def layer(state: dict[str, torch.Tensor], index: int, activation: str) -> dict:
    weight = state[f"layers.{index}.weight"].detach().cpu().numpy().astype("float32")
    bias = state[f"layers.{index}.bias"].detach().cpu().numpy().astype("float32")
    return {
        "inFeatures": int(weight.shape[1]),
        "outFeatures": int(weight.shape[0]),
        "weights": weight.reshape(-1).tolist(),
        "bias": bias.tolist(),
        "activation": activation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the PAT retrieval palette engine for the browser")
    parser.add_argument("source", type=Path, help="palette_ai repository containing data/processed and models/tone.pt")
    parser.add_argument("output", type=Path, help="website public/models directory")
    args = parser.parse_args()

    payload = json.loads((args.source / "data/processed/pat.json").read_text(encoding="utf-8"))
    embeddings = np.load(args.source / "data/processed/embeddings.npy").astype("float32")
    embeddings /= np.maximum(np.linalg.norm(embeddings, axis=1, keepdims=True), 1e-8)
    if embeddings.shape != (len(payload["palettes"]), 384):
        raise ValueError(f"Unexpected PAT embedding shape: {embeddings.shape}")

    tone = torch.load(args.source / "models/tone.pt", map_location="cpu", weights_only=True)
    state = tone["state_dict"]
    tone_artifact = {
        "layers": [layer(state, 0, "relu"), layer(state, 2, "relu"), layer(state, 4, "linear")],
        "targetMean": tone["target_mean"].detach().cpu().numpy().astype("float32").tolist(),
        "targetStd": tone["target_std"].detach().cpu().numpy().astype("float32").tolist(),
    }

    args.output.mkdir(parents=True, exist_ok=True)
    binary_path = args.output / "palette-retrieval-v1.f32"
    binary_path.write_bytes(embeddings.astype("<f4", copy=False).tobytes(order="C"))
    binary = binary_path.read_bytes()
    manifest = {
        "schemaVersion": 1,
        "version": "pat-e5-tone-scorer-v1",
        "dimension": 384,
        "recordCount": len(payload["palettes"]),
        "embeddings": {
            "path": "/models/palette-retrieval-v1.f32",
            "bytes": len(binary),
            "sha256": hashlib.sha256(binary).hexdigest(),
        },
        "palettes": payload["palettes"],
        "tone": tone_artifact,
    }
    (args.output / "palette-retrieval-v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Exported {len(payload['palettes']):,} palettes and {embeddings.shape} embeddings")


if __name__ == "__main__":
    main()
