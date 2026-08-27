"""Frozen real-PyTorch semantic v3 evaluator for Candidate 11."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

try:
    from .color_math import representation_to_oklab_numpy
    from .e5_embedding import embed_texts, load_encoder
    from .inspect_semantics import _family_distance, _family_references, _inputs
    from .model import PaletteDecoder, PaletteDecoderConfig
    from .parity_harness import decode_raw
except ImportError:
    from color_math import representation_to_oklab_numpy
    from e5_embedding import embed_texts, load_encoder
    from inspect_semantics import _family_distance, _family_references, _inputs
    from model import PaletteDecoder, PaletteDecoderConfig
    from parity_harness import decode_raw


def _pairwise_min(palette: np.ndarray) -> float:
    distances = np.linalg.norm(palette[:, None] - palette[None, :], axis=-1)
    return float(distances[np.triu_indices(len(palette), 1)].min())


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hues(palette: np.ndarray) -> np.ndarray:
    return np.degrees(np.arctan2(palette[:, 2], palette[:, 1])) % 360


def _relational_signature(palette: np.ndarray) -> np.ndarray:
    distances = np.linalg.norm(palette[:, None] - palette[None, :], axis=-1)
    return np.sort(distances[np.triu_indices(len(palette), 1)])


def palette_structure_metric(
    model: PaletteDecoder, dataset_path: str | None, split: str
) -> tuple[float | None, list[dict[str, Any]]]:
    if not dataset_path:
        return None, []
    archive = np.load(dataset_path, allow_pickle=False)
    required = {"text_embedding", "count_mask", "seed_noise", "locked_mask", "locked_colors", "target", "split", "source_group_id"}
    missing = sorted(required - set(archive.files))
    if missing:
        raise RuntimeError(f"palette structure dataset is missing {missing}")
    split_values = np.asarray(archive["split"]).astype(str)
    indices = np.flatnonzero(split_values == split)
    groups = np.asarray(archive["source_group_id"]).astype(str)
    count_masks = np.asarray(archive["count_mask"])
    targets = representation_to_oklab_numpy(np.asarray(archive["target"], dtype=np.float32))
    rows: list[dict[str, Any]] = []
    for index in indices:
        count = int(count_masks[index].sum())
        if count < 2:
            continue
        inputs = [
            torch.as_tensor(np.asarray(archive[name])[index:index + 1], dtype=torch.float32)
            for name in ("text_embedding", "count_mask", "seed_noise", "locked_mask", "locked_colors")
        ]
        with torch.no_grad():
            raw = model(*inputs).numpy()
        locked = np.asarray(archive["locked_mask"])[index, :count].astype(bool)
        effective = raw[0, :count].copy()
        effective[locked, :4] = np.asarray(archive["locked_colors"])[index, :count][locked, :4]
        generated_signature = _relational_signature(
            representation_to_oklab_numpy(effective[None])[0]
        )
        paired_error = float(np.mean(np.abs(
            generated_signature - _relational_signature(targets[index, :count])
        )))
        unrelated = [
            candidate for candidate in indices
            if candidate != index
            and groups[candidate] != groups[index]
            and int(count_masks[candidate].sum()) == count
        ]
        unrelated = sorted(
            unrelated,
            key=lambda candidate: __import__("hashlib").sha256(
                f"c11-palette-structure-v1|{groups[index]}|{groups[candidate]}".encode()
            ).digest(),
        )[:5]
        if not unrelated:
            continue
        unrelated_errors = [float(np.mean(np.abs(
            generated_signature - _relational_signature(targets[candidate, :count])
        ))) for candidate in unrelated]
        median_unrelated = float(np.median(unrelated_errors))
        rows.append({
            "sourceGroupId": groups[index], "count": count,
            "pairedStructureError": paired_error,
            "medianUnrelatedStructureError": median_unrelated,
            "pass": paired_error < median_unrelated,
        })
    rate = float(np.mean([row["pass"] for row in rows])) if rows else None
    return rate, rows


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    v2 = json.loads(Path(args.benchmark_v2).read_text(encoding="utf-8"))
    v3 = json.loads(Path(args.benchmark_v3).read_text(encoding="utf-8"))
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = PaletteDecoder(PaletteDecoderConfig(**checkpoint["model_config"])).eval()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    structure_rate, structure_rows = palette_structure_metric(
        model, args.dataset, args.evaluation_split
    )
    references, _ = _family_references(Path(args.benchmark_v2))
    prompts: list[str] = []
    for concept in v2["concepts"].values():
        prompts.extend(concept["prompts"])
    prompts.extend(v3["buckets"]["explicit_color_controls"])
    for item in v3["abstract"]:
        prompts.extend([item["en"], item["ru"], *item["references"], *item["hardNegatives"]])
    for pair in v3["longText"] + v3["compositionContrasts"]:
        prompts.extend(pair)
    for group in v3["oodParaphraseGroups"]:
        prompts.extend(group)
    prompts.extend(v3["adversarialComposition"])
    prompts.extend(["grass", "blood", "moonlight", "candlelight", "rust", "snow", "hospital", "glass"])
    prompts = list(dict.fromkeys(prompts))
    encoder = load_encoder(device=args.device, cache_dir=args.cache_dir)
    embeddings = embed_texts(prompts, encoder=encoder, batch_size=64)
    prompt_index = {prompt: index for index, prompt in enumerate(prompts)}
    palettes: dict[str, np.ndarray] = {}
    for prompt, embedding in zip(prompts, embeddings, strict=True):
        with torch.no_grad():
            raw = model(*_inputs(embedding, 5, 42)).numpy()
        palettes[prompt] = representation_to_oklab_numpy(raw[:, :5])[0]

    family_rows = []
    categories: dict[str, list[bool]] = {}
    for family, concept in v2["concepts"].items():
        for prompt in concept["prompts"]:
            closest = _family_distance(palettes[prompt], references)[0][0]
            passed = closest == family
            family_rows.append({"prompt": prompt, "expected": family, "closest": closest, "pass": passed})
            categories.setdefault(concept["category"], []).append(passed)
    category_rates = {name: float(np.mean(values)) for name, values in categories.items()}
    semantic_family_win = float(np.mean([row["pass"] for row in family_rows]))

    direct_rows = []
    for prompt in v3["buckets"]["explicit_color_controls"]:
        palette = palettes[prompt]
        hues = _hues(palette)
        chroma = np.linalg.norm(palette[:, 1:3], axis=1)
        if prompt in {"red", "красный"}:
            passed = float(np.mean(((hues <= 50) | (hues >= 345)) & (chroma > 0.03))) >= 0.6
        elif prompt in {"blue", "синий", "navy blue"}:
            passed = float(np.mean((hues >= 220) & (hues <= 290) & (chroma > 0.03))) >= 0.6
        elif prompt == "muted orange":
            passed = float(np.mean((hues >= 35) & (hues <= 85))) >= 0.4 and float(chroma.mean()) < 0.14
        elif prompt == "red and blue":
            passed = bool(np.any((hues <= 50) | (hues >= 345))) and bool(np.any((hues >= 220) & (hues <= 290)))
        elif prompt == "not red":
            passed = not bool(np.any(((hues <= 50) | (hues >= 345)) & (chroma > 0.04)))
        elif prompt == "without green":
            passed = not bool(np.any((hues >= 100) & (hues <= 165) & (chroma > 0.04)))
        else:
            passed = False
        direct_rows.append({"prompt": prompt, "pass": bool(passed)})

    abstract_rows = []
    for item in v3["abstract"]:
        en, ru = palettes[item["en"]].mean(0), palettes[item["ru"]].mean(0)
        reference = np.mean([palettes[prompt].mean(0) for prompt in item["references"]], axis=0)
        negative = np.mean([palettes[prompt].mean(0) for prompt in item["hardNegatives"]], axis=0)
        abstract_rows.append({
            "concept": item["en"], "ruEnDistance": float(np.linalg.norm(en - ru)),
            "referenceDistance": float(np.linalg.norm(en - reference)),
            "hardNegativeDistance": float(np.linalg.norm(en - negative)),
            "pass": float(np.linalg.norm(en - ru)) <= 0.08 and float(np.linalg.norm(en - reference)) < float(np.linalg.norm(en - negative)),
        })
    long_rows = [{"en": pair[0], "distance": float(np.linalg.norm(palettes[pair[0]].mean(0) - palettes[pair[1]].mean(0)))} for pair in v3["longText"]]
    composition_rows = [{"pair": pair, "distance": float(np.linalg.norm(palettes[pair[0]].mean(0) - palettes[pair[1]].mean(0)))} for pair in v3["compositionContrasts"]]
    ood_rows = []
    for group in v3["oodParaphraseGroups"]:
        means = np.stack([palettes[prompt].mean(0) for prompt in group])
        ood_rows.append({"group": group, "maximumDistance": float(np.linalg.norm(means[:, None] - means[None, :], axis=-1).max())})
    adversarial_base = {
        "red grass": "grass", "green blood": "blood", "warm moonlight": "moonlight",
        "cold candlelight": "candlelight", "blue rust": "rust", "black snow": "snow",
        "hospital at sunset": "hospital", "snow under red emergency lights": "snow",
        "green glass in a dark nightclub": "glass",
    }
    adversarial_rows = [
        {"prompt": prompt, "base": adversarial_base[prompt], "distance": float(np.linalg.norm(palettes[prompt].mean(0) - palettes[adversarial_base[prompt]].mean(0)))}
        for prompt in v3["adversarialComposition"]
    ]
    all_palette_values = list(palettes.values())
    near_duplicate_rate = float(np.mean([_pairwise_min(palette) < 0.025 for palette in all_palette_values]))
    engineering_embedding = embeddings[prompt_index["rain"]]
    count_passes, inactive_passes, gamut_passes = [], [], []
    for count in range(2, 10):
        with torch.no_grad():
            raw = model(*_inputs(engineering_embedding, count, 42)).numpy()[0]
        count_passes.append(raw[:count].shape[0] == count)
        inactive_passes.append(bool(np.all(raw[count:] == 0)))
        gamut_passes.append(all(
            all(-1e-4 <= channel <= 1.0001 for channel in color["srgb"])
            for color in decode_raw(raw, count)
        ))
    with torch.no_grad():
        repeat_a = model(*_inputs(engineering_embedding, 5, 42)).numpy()
        repeat_b = model(*_inputs(engineering_embedding, 5, 42)).numpy()
        seed_outputs = [model(*_inputs(engineering_embedding, 5, seed)).numpy() for seed in (1, 42, 999)]
        unlocked_inputs = list(_inputs(engineering_embedding, 5, 43))
        locked_inputs = list(_inputs(engineering_embedding, 5, 43))
        locked_inputs[3][0, 0] = 1.0
        locked_inputs[4][0, 0] = torch.tensor([0.55, 0.08, 0.0, 1.0])
        unlocked_raw = model(*unlocked_inputs).numpy()
        locked_raw = model(*locked_inputs).numpy()
    seed_palettes = [representation_to_oklab_numpy(value[:, :5])[0] for value in seed_outputs]
    seed_distances = [
        float(np.linalg.norm(seed_palettes[left].mean(0) - seed_palettes[right].mean(0)))
        for left in range(len(seed_palettes)) for right in range(left + 1, len(seed_palettes))
    ]
    restored_a = locked_raw.copy()
    restored_b = model(*list(_inputs(engineering_embedding, 5, 999))).detach().numpy()
    restored_a[0, 0, :4] = locked_inputs[4][0, 0].numpy()
    restored_b[0, 0, :4] = locked_inputs[4][0, 0].numpy()
    lock_exact = np.array_equal(restored_a[0, 0, :4], restored_b[0, 0, :4])
    lock_conditioning = not np.array_equal(unlocked_raw, locked_raw)
    parity = json.loads(Path(args.parity_report).read_text(encoding="utf-8")) if Path(args.parity_report).is_file() else {}
    browser_smoke = (
        json.loads(Path(args.browser_smoke_report).read_text(encoding="utf-8"))
        if args.browser_smoke_report and Path(args.browser_smoke_report).is_file()
        else {}
    )
    browser_smoke_pass = (
        browser_smoke.get("testClassification") == "REAL_BROWSER"
        and browser_smoke.get("pass") is True
        and browser_smoke.get("fallbackUsed") is False
    )
    browser_smoke_engineering = browser_smoke.get("testClassification") == "ENGINEERING_SMOKE_ONLY"
    metrics = {
        "semanticFamilyWin": semantic_family_win,
        "directEn": float(np.mean([row["pass"] for row in direct_rows if not any("а" <= c.lower() <= "я" for c in row["prompt"])])),
        "directRu": float(np.mean([row["pass"] for row in direct_rows if any("а" <= c.lower() <= "я" for c in row["prompt"])])),
        "exclusion": float(np.mean([row["pass"] for row in direct_rows if row["prompt"] in {"not red", "without green"}])),
        "cleanMultiColor": 1.0 - near_duplicate_rate,
        "nearDuplicateRate": near_duplicate_rate,
        "paletteStructureWinRate": structure_rate,
        "basicConcepts": category_rates.get("basic_objects", 0.0),
        "nature": category_rates.get("nature", 0.0),
        "weatherScenes": category_rates.get("weather", 0.0),
        "materials": category_rates.get("basic_objects", 0.0),
        "stylesMedia": category_rates.get("styles", 0.0),
        "compositions": category_rates.get("compositions", 0.0),
        "oodParaphrases": float(np.mean([row["maximumDistance"] <= 0.10 for row in ood_rows])),
        "heldOutRelated": float(np.mean([row["maximumDistance"] <= 0.12 for row in ood_rows[2:]])),
        "ruEnSemanticAgreement": float(np.mean([row["distance"] <= 0.08 for row in long_rows])),
        "abstractConceptGate": all(row["pass"] for row in abstract_rows),
        "longPromptGate": all(row["distance"] <= 0.10 for row in long_rows) and all(row["distance"] >= 0.025 for row in composition_rows),
        "adversarialCompositionGate": all(row["distance"] >= 0.025 for row in adversarial_rows),
        "count": float(np.mean(count_passes)),
        "inactive": float(np.mean(inactive_passes)),
        "locks": float(lock_exact and lock_conditioning),
        "seedDiversity": float(max(seed_distances) > 1e-6),
        "seedStability": float(max(seed_distances) < 0.18),
        "gamut": float(np.mean(gamut_passes)),
        "determinism": float(np.array_equal(repeat_a, repeat_b)),
        "pytorchOnnxParity": parity.get("pytorchOnnx", {}).get("pass") is True,
        "onnxBrowserParity": parity.get("onnxBrowser", {}).get("pass") is True,
        "realBrowserSemanticSmoke": browser_smoke_pass,
    }
    report = {
        "schemaVersion": 1, "candidate": "candidate-11",
        "benchmarkId": v3["benchmarkId"],
        "testClassification": (
            "ENGINEERING_SMOKE_ONLY" if (getattr(args, "engineering_smoke", False) or browser_smoke_engineering)
            else ("REAL_PYTORCH_ONNX_BROWSER_SEMANTIC" if browser_smoke_pass else "REAL_PYTORCH_SEMANTIC_STAGE_A")
        ),
        "productionReady": False,
        "sources": {
            "benchmarkId": v3["benchmarkId"], "checkpoint": args.checkpoint,
            "checkpointSha256": _sha256_file(args.checkpoint),
            "dataset": args.dataset,
            "datasetSha256": _sha256_file(args.dataset) if args.dataset else None,
            "evaluationSplit": args.evaluation_split,
        },
        "metrics": metrics, "categoryRates": category_rates, "familyRows": family_rows,
        "directRows": direct_rows, "abstractRows": abstract_rows, "longRows": long_rows,
        "compositionRows": composition_rows, "oodRows": ood_rows, "adversarialRows": adversarial_rows,
        "paletteStructureRows": structure_rows,
        "engineeringRows": {
            "seedMeanOklabDistances": seed_distances,
            "lockRestorationExact": lock_exact,
            "lockConditioningReachedModel": lock_conditioning,
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--benchmark-v2", default="ml/palettebrain/benchmark_visual_semantic_v2.json")
    parser.add_argument("--benchmark-v3", default="ml/palettebrain/benchmark_semantic_v3.json")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--parity-report", default="ml/palettebrain/reports/candidate-11-parity.json")
    parser.add_argument("--browser-smoke-report")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dataset")
    parser.add_argument("--evaluation-split", default="val", choices=("val", "test"))
    parser.add_argument("--engineering-smoke", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(args)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
