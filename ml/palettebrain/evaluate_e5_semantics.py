"""Cheap frozen E5 semantic diagnostic; the encoder is never trained."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

try:
    from .e5_embedding import embed_texts, load_encoder
except ImportError:
    from e5_embedding import embed_texts, load_encoder


GROUPS = {
    "weather": ["rain", "drizzle", "storm"],
    "vegetation": ["grass", "meadow", "moss"],
    "clinical": ["hospital", "clinic", "ward"],
    "transparent_material": ["glass", "window", "transparent material"],
    "painting": ["watercolor", "painting", "ink wash"],
    "melancholy": ["painful nostalgia", "melancholy", "sadness"],
}
BILINGUAL = [
    ("rain", "дождь"), ("grass", "трава"), ("hospital", "больница"),
    ("snow", "снег"), ("glass", "стекло"),
]


def evaluate(args: argparse.Namespace) -> dict[str, object]:
    prompts = list(dict.fromkeys([item for group in GROUPS.values() for item in group] + [item for pair in BILINGUAL for item in pair]))
    encoder = load_encoder(device=args.device, cache_dir=args.cache_dir)
    embeddings = embed_texts(prompts, encoder=encoder)
    index = {prompt: position for position, prompt in enumerate(prompts)}
    similarity = embeddings @ embeddings.T
    prompt_group = {prompt: group for group, values in GROUPS.items() for prompt in values}
    group_rows = []
    for group, values in GROUPS.items():
        positive = []
        negative = []
        for left_position, left in enumerate(values):
            for right in values[left_position + 1:]:
                positive.append(float(similarity[index[left], index[right]]))
            for other in GROUPS:
                if other != group:
                    negative.append(float(similarity[index[left], index[GROUPS[other][0]]]))
        group_rows.append({
            "group": group, "positiveMean": float(np.mean(positive)),
            "hardNegativeMaximum": float(np.max(negative)),
            "meanNegative": float(np.mean(negative)),
            "meanMargin": float(np.mean(positive) - np.mean(negative)),
        })
    bilingual_rows = [
        {"en": en, "ru": ru, "cosine": float(similarity[index[en], index[ru]])}
        for en, ru in BILINGUAL
    ]
    passed = all(row["meanMargin"] > 0 for row in group_rows) and min(row["cosine"] for row in bilingual_rows) >= 0.80
    report = {
        "schemaVersion": 1, "encoder": "intfloat/multilingual-e5-small",
        "groups": group_rows, "bilingual": bilingual_rows, "pass": passed,
        "interpretation": "PASS means semantic signal exists in E5; it does not qualify the color decoder.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", default="ml/palettebrain/reports/e5-semantic-diagnostic.json")
    args = parser.parse_args()
    print(json.dumps(evaluate(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
