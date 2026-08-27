"""Generate the Candidate 11 semantic-to-color inspector (HTML, CSV, maps)."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

try:
    from .color_math import representation_to_oklab_numpy
    from .dataset import seed_noise_from_uint32
    from .e5_embedding import embed_texts, load_encoder
    from .model import PaletteDecoder, PaletteDecoderConfig
    from .palette_targets import hex_to_oklab
    from .parity_harness import decode_raw
except ImportError:
    from color_math import representation_to_oklab_numpy
    from dataset import seed_noise_from_uint32
    from e5_embedding import embed_texts, load_encoder
    from model import PaletteDecoder, PaletteDecoderConfig
    from palette_targets import hex_to_oklab
    from parity_harness import decode_raw


REQUIRED_PROMPTS = [
    "red", "blue", "green", "black", "white", "красный", "синий", "зелёный", "чёрный", "белый",
    "rain", "дождь", "drizzle", "storm", "fog", "туман", "grass", "трава", "leaf", "лист",
    "forest", "лес", "meadow", "moss", "apple", "яблоко", "pear", "plum", "hospital", "больница",
    "clinic", "ward", "snow", "снег", "ice", "glass", "стекло", "rust", "ржавчина", "steel",
    "wet concrete", "old paper", "moonlight", "лунный свет", "dawn", "рассвет", "sunset", "watercolor",
    "акварель", "film noir", "gothic", "constructivist poster", "cyberpunk", "painful nostalgia",
    "болезненная ностальгия", "quiet dread", "тихая тревога", "warm childhood memory",
    "стерильное одиночество", "gentle melancholy", "fragile optimism",
]


def _pca(values: np.ndarray) -> np.ndarray:
    centered = values - values.mean(axis=0, keepdims=True)
    if len(values) < 2:
        return np.zeros((len(values), 2), dtype=np.float32)
    _, _, right = np.linalg.svd(centered, full_matrices=False)
    result = centered @ right[:2].T
    if result.shape[1] == 1:
        result = np.column_stack((result, np.zeros(len(result))))
    return result.astype(np.float32)


def _cosine_neighbors(values: np.ndarray, prompts: list[str], index: int, count: int = 5) -> list[tuple[str, float]]:
    normalized = values / np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-8)
    similarities = normalized @ normalized[index]
    order = [item for item in np.argsort(-similarities) if item != index][:count]
    return [(prompts[item], float(similarities[item])) for item in order]


def _inputs(embedding: np.ndarray, count: int, seed: int) -> tuple[torch.Tensor, ...]:
    mask = np.zeros((1, 9), dtype=np.float32)
    mask[:, :count] = 1
    return (
        torch.from_numpy(embedding.reshape(1, 384).astype(np.float32)),
        torch.from_numpy(mask),
        torch.from_numpy(seed_noise_from_uint32(seed).reshape(1, 9, 4)),
        torch.zeros(1, 9),
        torch.zeros(1, 9, 4),
    )


def _bridge_hidden(model: PaletteDecoder, embeddings: torch.Tensor) -> torch.Tensor:
    bridge = model.bridge
    x = bridge.act(bridge.fc_in(bridge.norm(embeddings)))
    x = x + bridge.res1_fc2(bridge.act(bridge.res1_fc1(x)))
    return x + bridge.res2_fc2(bridge.act(bridge.res2_fc1(x)))


def _family_references(path: Path) -> tuple[dict[str, list[np.ndarray]], dict[str, str]]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    references: dict[str, list[np.ndarray]] = {}
    prompt_to_family: dict[str, str] = {}
    for family, record in fixture["concepts"].items():
        references[family] = [np.stack([hex_to_oklab(color) for color in palette]) for palette in record["reference_palettes"]]
        for prompt in record["prompts"]:
            prompt_to_family[prompt] = family
    return references, prompt_to_family


def _family_distance(palette: np.ndarray, references: dict[str, list[np.ndarray]]) -> list[tuple[str, float]]:
    mean = palette.mean(axis=0)
    rows = []
    for family, variants in references.items():
        distance = min(float(np.linalg.norm(mean - variant.mean(axis=0))) for variant in variants)
        rows.append((family, distance))
    return sorted(rows, key=lambda item: item[1])


def _diversity(palette: np.ndarray) -> float:
    if len(palette) < 2:
        return 0.0
    distances = np.linalg.norm(palette[:, None] - palette[None, :], axis=-1)
    return float(distances[np.triu_indices(len(palette), 1)].mean())


def _bin_label(index: int) -> str:
    if index >= 384:
        return f"NEUTRAL L≈{0.15 + (index - 384 + 0.5) * 0.125:.2f}"
    hue = index // 24
    remainder = index % 24
    lightness = remainder // 4
    chroma = remainder % 4
    return f"H≈{(hue + 0.5) * 22.5:.1f}°, L≈{0.15 + (lightness + 0.5) * 0.125:.2f}, C≈{0.03 + (chroma + 0.5) * 0.055:.3f}"


def _svg_map(title: str, projection: np.ndarray, prompts: list[str], colors: list[str]) -> str:
    low, high = projection.min(axis=0), projection.max(axis=0)
    span = np.maximum(high - low, 1e-6)
    points = 30 + (projection - low) / span * np.array([740, 440])
    elements = [f'<h2>{html.escape(title)}</h2><svg viewBox="0 0 800 500" role="img" aria-label="{html.escape(title)}">']
    for (x, y), prompt, color in zip(points, prompts, colors, strict=True):
        label = html.escape(prompt)
        elements.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"><title>{label}</title></circle>')
        elements.append(f'<text x="{x + 7:.1f}" y="{y + 3:.1f}">{label}</text>')
    elements.append('</svg>')
    return "".join(elements)


def _load_browser_status(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"available": False, "modelVersions": [], "fallback": False}
    report = json.loads(path.read_text(encoding="utf-8"))
    results = report.get("results", [])
    return {
        "available": True,
        "modelVersions": sorted({row.get("result", {}).get("modelVersion") for row in results}),
        "fallback": any(row.get("result", {}).get("fallback") for row in results),
    }


def generate(args: argparse.Namespace) -> dict[str, Any]:
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = PaletteDecoder(PaletteDecoderConfig(**checkpoint["model_config"]))
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    v3 = json.loads(Path(args.benchmark_v3).read_text(encoding="utf-8"))
    prompts = list(REQUIRED_PROMPTS)
    for pair in v3["longText"]:
        prompts.extend(pair)
    if args.prompt:
        prompts.insert(0, args.prompt)
    prompts = list(dict.fromkeys(prompts))
    encoder = load_encoder(device=args.device, cache_dir=args.cache_dir)
    embeddings = embed_texts(prompts, encoder=encoder, batch_size=32)
    embedding_tensor = torch.from_numpy(embeddings)
    with torch.no_grad():
        bridge_hidden = _bridge_hidden(model, embedding_tensor).numpy()
        prior_logits, style_latents, _, _ = model.bridge(embedding_tensor)
        priors = torch.softmax(prior_logits, dim=-1).numpy()
    references, prompt_to_family = _family_references(Path(args.benchmark_v2))
    browser = _load_browser_status(Path(args.browser_report) if args.browser_report else None)
    parity = json.loads(Path(args.parity_report).read_text(encoding="utf-8")) if Path(args.parity_report).is_file() else {}
    expected_version = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["modelVersion"]
    rows: list[dict[str, Any]] = []
    palettes: list[np.ndarray] = []
    dominant_colors: list[str] = []
    for index, prompt in enumerate(prompts):
        inputs = _inputs(embeddings[index], 5, 42)
        with torch.no_grad():
            raw = model(*inputs).numpy()[0]
        decoded = decode_raw(raw, 5)
        palette = representation_to_oklab_numpy(raw[None, :5])[0]
        palettes.append(palette)
        nearest_families = _family_distance(palette, references)
        expected_family = prompt_to_family.get(prompt)
        prior = priors[index]
        top_bins = np.argsort(-prior)[:10]
        prior_entropy = float(-(prior * np.log(np.maximum(prior, 1e-12))).sum())
        seed_families = []
        for seed in (0, 1, 2, 42, 137, 999):
            with torch.no_grad():
                variant = model(*_inputs(embeddings[index], 5, seed)).numpy()[0]
            seed_families.append(_family_distance(representation_to_oklab_numpy(variant[None, :5])[0], references)[0][0])
        count_families = []
        for count in (2, 3, 5, 8, 9):
            with torch.no_grad():
                variant = model(*_inputs(embeddings[index], count, 42)).numpy()[0]
            count_families.append(_family_distance(representation_to_oklab_numpy(variant[None, :count])[0], references)[0][0])
        flags: list[str] = []
        attention = model.visual_attention_weights(
            torch.as_tensor(embeddings[index:index + 1], dtype=torch.float32)
        )
        if attention is None:
            flags.append("ALL_SLOTS_SAME_VISUAL_CONTEXT")
        if prior_entropy > math.log(390) * 0.9:
            flags.append("COLOR_PRIOR_HIGH_ENTROPY")
        if expected_family and nearest_families[0][0] != expected_family:
            flags.append("COLOR_PRIOR_WRONG_FAMILY")
        e5_good = expected_family is not None and any(
            prompt_to_family.get(neighbor) == expected_family
            for neighbor, _ in _cosine_neighbors(embeddings, prompts, index)
        )
        bridge_good = expected_family is not None and any(
            prompt_to_family.get(neighbor) == expected_family
            for neighbor, _ in _cosine_neighbors(bridge_hidden, prompts, index)
        )
        if e5_good and not bridge_good:
            flags.append("E5_GOOD_BRIDGE_BAD")
        if bridge_good and nearest_families[0][0] != expected_family:
            flags.append("BRIDGE_GOOD_DECODER_BAD")
        if _diversity(palette) < 0.025:
            flags.append("PALETTE_NEAR_DUPLICATE_COLLAPSE")
        if len(set(seed_families)) > 1:
            flags.append("SEED_CHANGES_SEMANTIC_FAMILY")
        if len(set(count_families)) > 1:
            flags.append("COUNT_CHANGES_SEMANTIC_FAMILY")
        if browser["fallback"]:
            flags.append("PROCEDURAL_FALLBACK_USED")
        if browser["available"] and browser["modelVersions"] != [expected_version]:
            flags.append("WRONG_MODEL_LOADED")
        if parity.get("pytorchOnnx", {}).get("pass") is not True:
            flags.append("PT_ONNX_MISMATCH")
        if parity.get("onnxBrowser", {}).get("pass") is not True:
            flags.append("ONNX_BROWSER_MISMATCH")
        row = {
            "prompt": prompt,
            "language": "RU" if any("а" <= character.lower() <= "я" or character.lower() == "ё" for character in prompt) else "EN",
            "e5Neighbors": _cosine_neighbors(embeddings, prompts, index),
            "bridgeNeighbors": _cosine_neighbors(bridge_hidden, prompts, index),
            "predictedHueFamilies": [_bin_label(int(item)) for item in top_bins[:3]],
            "dominantLightness": float(palette[:, 0].mean()),
            "dominantChroma": float(np.linalg.norm(palette[:, 1:3], axis=1).mean()),
            "neutralProbability": float(prior[384:].sum()),
            "topBins": [(_bin_label(int(item)), float(prior[item])) for item in top_bins],
            "priorEntropy": prior_entropy,
            "palette": decoded,
            "meanOklab": palette.mean(axis=0).tolist(),
            "diversity": _diversity(palette),
            "closestFamily": nearest_families[0],
            "hardNegative": nearest_families[1],
            "expectedFamily": expected_family,
            "semanticFamilyWin": expected_family is not None and nearest_families[0][0] == expected_family,
            "ruEnAgreement": None,
            "seedStability": seed_families.count(seed_families[3]) / len(seed_families),
            "countStability": count_families.count(count_families[2]) / len(count_families),
            "attention": attention[0].tolist() if attention is not None else None,
            "flags": flags,
            "parity": (
                "PASS" if parity.get("pytorchOnnx", {}).get("pass") is True
                and parity.get("onnxBrowser", {}).get("pass") is True else "FAIL"
            ),
            "styleLatentNorm": float(torch.linalg.vector_norm(style_latents[index])),
        }
        rows.append(row)
        dominant_colors.append(decoded[0]["hex"])

    row_by_prompt = {row["prompt"]: row for row in rows}
    palette_by_prompt = {prompt: palette for prompt, palette in zip(prompts, palettes, strict=True)}
    for en, ru in v3["bilingualPairs"]:
        if en in row_by_prompt and ru in row_by_prompt:
            distance = float(np.linalg.norm(palette_by_prompt[en].mean(0) - palette_by_prompt[ru].mean(0)))
            agreement = max(0.0, 1.0 - distance / 0.20)
            row_by_prompt[en]["ruEnAgreement"] = agreement
            row_by_prompt[ru]["ruEnAgreement"] = agreement
            if agreement < 0.85:
                row_by_prompt[en]["flags"].append("RU_EN_DISAGREEMENT")
                row_by_prompt[ru]["flags"].append("RU_EN_DISAGREEMENT")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "semantic_color_table.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=[
            "prompt", "language", "e5_neighbors", "bridge_neighbors", "dominant_regions", "final_colors",
            "closest_family", "hard_negative", "semantic_family_win", "ru_en_agreement", "seed_stability", "count_stability", "flags",
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "prompt": row["prompt"], "language": row["language"],
                "e5_neighbors": json.dumps(row["e5Neighbors"], ensure_ascii=False),
                "bridge_neighbors": json.dumps(row["bridgeNeighbors"], ensure_ascii=False),
                "dominant_regions": json.dumps(row["predictedHueFamilies"], ensure_ascii=False),
                "final_colors": " ".join(color["hex"] for color in row["palette"]),
                "closest_family": row["closestFamily"][0], "hard_negative": row["hardNegative"][0],
                "semantic_family_win": row["semanticFamilyWin"], "seed_stability": row["seedStability"],
                "ru_en_agreement": row["ruEnAgreement"],
                "count_stability": row["countStability"], "flags": "|".join(row["flags"]),
            })
    style = "body{font:14px system-ui;background:#111;color:#eee;margin:24px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #444;padding:6px;vertical-align:top}th{position:sticky;top:0;background:#222}.sw{display:inline-block;width:28px;height:28px;border:1px solid #777}.bad{color:#ff8585}.ok{color:#86e29b}svg{background:#181818;border:1px solid #444;width:100%;height:auto}svg text{fill:#ddd;font-size:9px}nav a{margin-right:14px;color:#9cf}"
    detailed = []
    simple = []
    for row in rows:
        swatches = "".join(f'<span class="sw" title="{color["hex"]}" style="background:{color["hex"]}"></span>' for color in row["palette"])
        verdict = "PASS" if row["semanticFamilyWin"] else ("FAIL" if row["expectedFamily"] else "DIAGNOSTIC")
        detailed.append("<tr>" + "".join(f"<td>{value}</td>" for value in [
            html.escape(row["prompt"]), row["language"], html.escape(json.dumps(row["e5Neighbors"], ensure_ascii=False)),
            html.escape(json.dumps(row["bridgeNeighbors"], ensure_ascii=False)), html.escape("; ".join(row["predictedHueFamilies"])),
            f'{row["dominantLightness"]:.3f}', f'{row["dominantChroma"]:.3f}', f'{row["neutralProbability"]:.3f}',
            html.escape(json.dumps(row["topBins"], ensure_ascii=False)), f'{row["priorEntropy"]:.3f}', swatches,
            f'{row["diversity"]:.4f}', html.escape(str(row["closestFamily"])), html.escape(str(row["hardNegative"])),
            verdict, "n/a" if row["ruEnAgreement"] is None else f'{row["ruEnAgreement"]:.2f}',
            f'{row["seedStability"]:.2f}', f'{row["countStability"]:.2f}', row["parity"], html.escape(" | ".join(row["flags"])),
        ]) + "</tr>")
        bridge_summary = row["bridgeNeighbors"][0][0] if row["bridgeNeighbors"] else "n/a"
        simple.append(f'<tr><td>{html.escape(row["prompt"])}</td><td>{html.escape(", ".join(item[0] for item in row["e5Neighbors"][:3]) or "n/a")}</td><td>{html.escape(bridge_summary)}</td><td>{html.escape(row["predictedHueFamilies"][0])}</td><td>{swatches}</td><td>{verdict}</td></tr>')
    headers = ["Prompt", "Language", "E5 nearest + cosine", "Bridge nearest", "Predicted hue regions", "L", "C", "Neutral mass", "Top prior bins", "Entropy", "Final palette", "Diversity", "Closest reference", "Hard negative", "Family win", "RU/EN agreement", "Seed stability", "Count stability", "PT/ORT/browser", "Flags"]
    table_html = f'<!doctype html><meta charset="utf-8"><style>{style}</style><h1>Candidate 11 Semantic → Color Inspector</h1><p>Experimental; 2D maps are diagnostic only. Pass/fail uses original vectors and perceptual metrics.</p><h2>Simple view</h2><table><tr><th>PROMPT</th><th>E5 THINKS IT IS CLOSE TO</th><th>BRIDGE PREDICTS</th><th>DOMINANT COLOR REGIONS</th><th>FINAL COLORS</th><th>VERDICT</th></tr>{"".join(simple)}</table><h2>Full diagnostic view</h2><table><tr>{"".join(f"<th>{h}</th>" for h in headers)}</tr>{"".join(detailed)}</table>'
    html_path = output_dir / "semantic_color_table.html"
    html_path.write_text(table_html, encoding="utf-8")
    map_html = f'<!doctype html><meta charset="utf-8"><style>{style}</style><h1>Candidate 11 diagnostic vector spaces</h1><p>Projection proximity is not qualification evidence.</p>' + _svg_map("E5 semantic space (384-d PCA)", _pca(embeddings), prompts, ["#65a9ff"] * len(prompts)) + _svg_map("VisualPaletteBridge space (256-d PCA)", _pca(bridge_hidden), prompts, ["#d597ff"] * len(prompts)) + _svg_map("Predicted color-distribution space (390-d PCA)", _pca(priors), prompts, dominant_colors)
    map_path = output_dir / "semantic_embedding_map.html"
    map_path.write_text(map_html, encoding="utf-8")
    report = {"rows": len(rows), "html": str(html_path), "csv": str(csv_path), "map": str(map_path)}
    if args.prompt:
        row = next(item for item in rows if item["prompt"] == args.prompt)
        trace_index = prompts.index(args.prompt)
        print(json.dumps({
            "TEXT": row["prompt"], "TOKENIZATION_SUMMARY": "query prefix; <=512 tokens; mean pool; L2 norm",
            "E5_NEIGHBORS": row["e5Neighbors"], "E5_VECTOR_SUMMARY": {"norm": float(np.linalg.norm(embeddings[trace_index]))},
            "BRIDGE_REPRESENTATION": {"neighbors": row["bridgeNeighbors"], "styleNorm": row["styleLatentNorm"]},
            "COLOR_PRIOR_TOP_BINS": row["topBins"], "COLOR_PRIOR_ENTROPY": row["priorEntropy"],
            "DECODER_SLOTS": [{"slot": item["slot"] + 1, "visualAttention": row["attention"][item["slot"]] if row["attention"] else "LEGACY_BROADCAST", "oklch": item["oklch"]} for item in row["palette"]],
            "FINAL_PALETTE": [item["hex"] for item in row["palette"]], "REFERENCE_FAMILY": row["expectedFamily"],
            "HARD_NEGATIVE": row["hardNegative"], "SEED_STABILITY": row["seedStability"], "COUNT_STABILITY": row["countStability"],
            "FINAL_VERDICT": "FAIL" if row["flags"] else "PASS", "FLAGS": row["flags"],
        }, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="ml/palettebrain/checkpoints/candidate-11-best.pt")
    parser.add_argument("--benchmark-v2", default="ml/palettebrain/benchmark_visual_semantic_v2.json")
    parser.add_argument("--benchmark-v3", default="ml/palettebrain/benchmark_semantic_v3.json")
    parser.add_argument("--manifest", default="public/models/palettebrain-v2.manifest.json")
    parser.add_argument("--browser-report", default="ml/palettebrain/reports/candidate-11-browser-current-parity.json")
    parser.add_argument("--parity-report", default="ml/palettebrain/reports/candidate-11-parity.json")
    parser.add_argument("--output-dir", default="ml/palettebrain/reports")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--prompt")
    args = parser.parse_args()
    print(json.dumps(generate(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
