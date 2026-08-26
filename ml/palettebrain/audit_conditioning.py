"""Measure Candidate 11 conditioning activation norms and semantic drift."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

try:
    from .color_math import representation_to_oklab_numpy
    from .dataset import seed_noise_from_uint32
    from .e5_embedding import embed_texts, load_encoder
    from .model import PaletteDecoder, PaletteDecoderConfig
except ImportError:
    from color_math import representation_to_oklab_numpy
    from dataset import seed_noise_from_uint32
    from e5_embedding import embed_texts, load_encoder
    from model import PaletteDecoder, PaletteDecoderConfig


PROMPTS = ["rain", "дождь", "grass", "трава", "snow", "снег", "hospital", "больница", "glass", "red"]
SEEDS = [0, 1, 2, 42, 137, 999]
COUNTS = [2, 3, 5, 8, 9]


def evaluate(args: argparse.Namespace) -> dict[str, object]:
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = PaletteDecoder(PaletteDecoderConfig(**checkpoint["model_config"])).eval()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    encoder = load_encoder(device=args.device, cache_dir=args.cache_dir)
    embeddings = embed_texts(PROMPTS, encoder=encoder)
    rows = []
    for prompt, embedding in zip(PROMPTS, embeddings, strict=True):
        text = torch.from_numpy(embedding[None])
        count_mask = torch.tensor([[1] * 5 + [0] * 4], dtype=torch.float32)
        seed = torch.from_numpy(seed_noise_from_uint32(42)[None])
        locks = torch.zeros(1, 9)
        locked_colors = torch.zeros(1, 9, 4)
        with torch.no_grad():
            _, _, color_tokens, style_token = model.bridge(text)
            contexts = {
                "text": model.text_projection(text).unsqueeze(1),
                "visualMean": color_tokens.mean(dim=1, keepdim=True),
                "style": style_token,
                "count": model.count_projection(count_mask).unsqueeze(1),
                "seed": model.seed_projection(seed),
                "lock": model.lock_projection(torch.cat((locked_colors, locks.unsqueeze(-1)), dim=-1)),
            }
        means = []
        for seed_value in SEEDS:
            with torch.no_grad():
                raw = model(text, count_mask, torch.from_numpy(seed_noise_from_uint32(seed_value)[None]), locks, locked_colors).numpy()
            means.append(representation_to_oklab_numpy(raw[:, :5])[0].mean(axis=0))
        count_means = []
        for count in COUNTS:
            mask = torch.zeros(1, 9)
            mask[:, :count] = 1
            with torch.no_grad():
                raw = model(text, mask, seed, locks, locked_colors).numpy()
            count_means.append(representation_to_oklab_numpy(raw[:, :count])[0].mean(axis=0))
        rows.append({
            "prompt": prompt,
            "activationNorms": {name: float(torch.linalg.vector_norm(value, dim=-1).mean()) for name, value in contexts.items()},
            "seedMeanOklabMaximumDrift": float(np.max(np.linalg.norm(np.asarray(means) - means[3], axis=1))),
            "countMeanOklabMaximumDrift": float(np.max(np.linalg.norm(np.asarray(count_means) - count_means[2], axis=1))),
        })
    report = {
        "schemaVersion": 1, "candidate": "candidate-11", "rows": rows,
        "summary": {
            "seedMaximumDrift": max(row["seedMeanOklabMaximumDrift"] for row in rows),
            "countMaximumDrift": max(row["countMeanOklabMaximumDrift"] for row in rows),
            "semanticBranchesOverpowered": any(
                row["activationNorms"][branch] > row["activationNorms"]["text"] * 2
                for row in rows for branch in ("seed", "count")
            ),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="ml/palettebrain/checkpoints/candidate-11-best.pt")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", default="ml/palettebrain/reports/candidate-11-conditioning-audit.json")
    args = parser.parse_args()
    print(json.dumps(evaluate(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
