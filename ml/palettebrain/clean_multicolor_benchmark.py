"""
Clean multi-color held-out benchmark for Candidate 3 vs Candidate 4.

Steps:
  1. Define CLEAN prompts with ZERO normalized overlap with C4 training texts.
  2. Freeze the benchmark with a SHA-256 hash (before any model outputs are seen).
  3. Run C3 and C4 on it with identical count / seed settings.
  4. Score: every requested color family must be represented by a DISTINCT
     active slot in the predicted palette (permutation-invariant assignment).
     One purple cannot satisfy both red and blue.
  5. Report clean scores separately from the old contaminated score.
"""

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]   # repo root (ml/palettebrain -> ml -> repo)
sys.path.insert(0, str(ROOT))

from ml.palettebrain.e5_embedding import load_encoder, embed_texts
from ml.palettebrain.model import PaletteDecoder, PaletteDecoderConfig
from ml.palettebrain.dataset import seed_noise_from_uint32, MAX_COLORS
from ml.palettebrain.color_math import representation_to_oklab_numpy

import torch

# ---------------------------------------------------------------------------
# Normalization (conservative: lower, trim, collapse spaces, strip punct)
# ---------------------------------------------------------------------------

def normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[\s]+", " ", s)
    s = re.sub(r"[,;:.!?]", "", s)
    return s


# ---------------------------------------------------------------------------
# Candidate 4 training prompts (all texts from MULTI_COLOR_SPECS, both EN+RU)
# ---------------------------------------------------------------------------

C4_TRAINING_TEXTS = [
    "red and blue", "красный и синий",
    "blue and red", "синий и красный",
    "red and yellow", "красный и жёлтый",
    "yellow and red", "жёлтый и красный",
    "purple and cyan", "фиолетовый и голубой",
    "cyan and purple", "голубой и фиолетовый",
    "green and orange", "зелёный и оранжевый",
    "orange and green", "оранжевый и зелёный",
    "blue and yellow", "синий и жёлтый",
    "yellow and blue", "жёлтый и синий",
    "red and green", "красный и зелёный",
    "green and red", "зелёный и красный",
    "pink and teal", "розовый и бирюзовый",
    "teal and pink", "бирюзовый и розовый",
    "orange and violet", "оранжевый и фиолетовый",
    "violet and orange", "фиолетовый и оранжевый",
    "magenta and green", "малиновый и зелёный",
    "blue and orange", "синий и оранжевый",
    "red and cyan", "красный и циан",
    "yellow and purple", "жёлтый и фиолетовый",
    "red blue yellow", "красный синий жёлтый",
    "blue yellow red", "синий жёлтый красный",
    "red green blue", "красный зелёный синий",
    "orange purple cyan", "оранжевый фиолетовый голубой",
    "pink blue yellow", "розовый синий жёлтый",
    "teal orange violet", "бирюзовый оранжевый фиолетовый",
    "palette with red and blue", "палитра с красным и синим",
    "colors: red, blue, yellow", "цвета: красный, синий, жёлтый",
    "red alongside blue", "красный рядом с синим",
    "combining red with yellow", "сочетание красного с жёлтым",
]

C4_TRAINING_NORM = {normalize(t) for t in C4_TRAINING_TEXTS}

# ---------------------------------------------------------------------------
# Frozen evaluation multi-color prompts (from benchmark_color_families.v1.json)
# ---------------------------------------------------------------------------

FROZEN_EVAL_MC = [
    {"id": "red-blue-en",   "prompt": "red and blue",        "language": "en", "required": ["red",   "blue"]},
    {"id": "red-blue-ru",   "prompt": "красный и синий",     "language": "ru", "required": ["red",   "blue"]},
    {"id": "black-gold-en", "prompt": "black and gold",      "language": "en", "required": ["black", "gold"]},
    {"id": "black-gold-ru", "prompt": "чёрный и золотой",    "language": "ru", "required": ["black", "gold"]},
]

# ---------------------------------------------------------------------------
# CLEAN held-out multi-color benchmark
#   Rules:
#   - normalize(prompt) NOT in C4_TRAINING_NORM
#   - Both RU and EN
#   - Pairs AND triples
#   - Natural wording distinct from C4 training templates
#   - Tests distant AND neighboring color families
# ---------------------------------------------------------------------------

CLEAN_BENCHMARK_RAW = [
    # --- EN pairs (distinct wording from training) ---
    # distant families
    {"id": "cb-en-01", "prompt": "crimson meets cobalt",        "language": "en", "required": ["red", "blue"]},
    {"id": "cb-en-02", "prompt": "scarlet with navy",           "language": "en", "required": ["red", "blue"]},
    {"id": "cb-en-03", "prompt": "emerald and rust",            "language": "en", "required": ["green", "orange"]},
    {"id": "cb-en-04", "prompt": "sky blue and flame",          "language": "en", "required": ["blue", "orange"]},
    {"id": "cb-en-05", "prompt": "violet paired with amber",    "language": "en", "required": ["purple", "yellow"]},
    {"id": "cb-en-06", "prompt": "jade alongside magenta",      "language": "en", "required": ["green", "pink"]},
    # neighboring families
    {"id": "cb-en-07", "prompt": "rose and fuchsia together",   "language": "en", "required": ["red", "pink"]},
    {"id": "cb-en-08", "prompt": "azure and cyan combined",     "language": "en", "required": ["blue", "cyan"]},
    # --- EN triples ---
    {"id": "cb-en-09", "prompt": "warm red cool blue pale yellow", "language": "en", "required": ["red", "blue", "yellow"]},
    {"id": "cb-en-10", "prompt": "forest tones with coral and gold", "language": "en", "required": ["green", "orange", "yellow"]},
    {"id": "cb-en-11", "prompt": "neon green purple orange",    "language": "en", "required": ["green", "purple", "orange"]},
    # --- RU pairs ---
    {"id": "cb-ru-01", "prompt": "алый с лазурным",             "language": "ru", "required": ["red", "blue"]},
    {"id": "cb-ru-02", "prompt": "тёмно-красный плюс синий",    "language": "ru", "required": ["red", "blue"]},
    {"id": "cb-ru-03", "prompt": "изумрудный и рыжий",          "language": "ru", "required": ["green", "orange"]},
    {"id": "cb-ru-04", "prompt": "небесный совместно с янтарным", "language": "ru", "required": ["blue", "yellow"]},
    {"id": "cb-ru-05", "prompt": "сиреневый вместе с коралловым", "language": "ru", "required": ["purple", "pink"]},
    {"id": "cb-ru-06", "prompt": "морской волны и алый",        "language": "ru", "required": ["cyan", "red"]},
    # neighboring
    {"id": "cb-ru-07", "prompt": "малиновый и розовый",         "language": "ru", "required": ["red", "pink"]},
    {"id": "cb-ru-08", "prompt": "голубой да циановый",         "language": "ru", "required": ["blue", "cyan"]},
    # --- RU triples ---
    {"id": "cb-ru-09", "prompt": "ярко-красный синий и жёлтый оттенки", "language": "ru", "required": ["red", "blue", "yellow"]},
    {"id": "cb-ru-10", "prompt": "изумруд коралл золото",       "language": "ru", "required": ["green", "orange", "yellow"]},
    {"id": "cb-ru-11", "prompt": "неоновый зелёный фиолетовый оранжевый", "language": "ru", "required": ["green", "purple", "orange"]},
]


def verify_no_contamination(benchmark: list[dict]) -> dict:
    """Assert all benchmark prompts have zero normalized overlap with C4 training."""
    contaminated = []
    for item in benchmark:
        n = normalize(item["prompt"])
        if n in C4_TRAINING_NORM:
            contaminated.append(item)
    return {"contaminated_count": len(contaminated), "contaminated": contaminated}


def benchmark_hash(benchmark: list[dict]) -> str:
    """Deterministic SHA-256 of the benchmark (before any model outputs)."""
    payload = json.dumps(benchmark, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Color family scoring using fixture oklabPrototypes
# ---------------------------------------------------------------------------

# Fallback single centroids if a family has no fixture prototypes.
FALLBACK_FAMILY_CENTROIDS: dict[str, list[float]] = {
    "red":    [0.627955,  0.224863,  0.125846],
    "blue":   [0.452014, -0.032457, -0.311528],
    "yellow": [0.866025, -0.093476,  0.187154],
    "green":  [0.519807, -0.182235,  0.107317],
    "orange": [0.703873,  0.138054,  0.145623],
    "purple": [0.442000,  0.083000, -0.198000],
    "cyan":   [0.728297, -0.145155, -0.097446],
    "pink":   [0.728297,  0.195155, -0.027446],
    "black":  [0.153000,  0.000000,  0.000000],
    "white":  [0.940000,  0.000000,  0.000000],
    "gold":   [0.779000,  0.025000,  0.165000],
}

# Threshold from fixture thresholds.anchorOklabDistance
FAMILY_MATCH_THRESHOLD = 0.10


def load_color_family_fixture() -> dict:
    path = ROOT / "ml" / "palettebrain" / "benchmark_color_families.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def build_family_prototypes(fixture: dict) -> tuple[dict[str, list[list[float]]], float]:
    """Build dict: family_name -> list-of-OKLab-points, and return the threshold."""
    families = fixture.get("families", {})
    threshold = float(fixture.get("thresholds", {}).get("anchorOklabDistance", FAMILY_MATCH_THRESHOLD))
    result: dict[str, list[list[float]]] = {}
    for name, info in families.items():
        protos = info.get("oklabPrototypes", [])
        if protos:
            result[name] = [list(p) for p in protos]
        elif name in FALLBACK_FAMILY_CENTROIDS:
            result[name] = [FALLBACK_FAMILY_CENTROIDS[name]]
    # Add families present in FALLBACK but absent from fixture
    for name, centroid in FALLBACK_FAMILY_CENTROIDS.items():
        if name not in result:
            result[name] = [centroid]
    return result, threshold


def min_dist_to_family(
    oklab_point: np.ndarray,
    family_name: str,
    prototypes: dict[str, list[list[float]]],
) -> float:
    """Min OKLab distance from oklab_point to any prototype for family_name."""
    protos = prototypes.get(family_name)
    if not protos:
        centroid = FALLBACK_FAMILY_CENTROIDS.get(family_name, [0.5, 0.0, 0.0])
        return float(np.linalg.norm(oklab_point - np.array(centroid, dtype=np.float32)))
    return min(
        float(np.linalg.norm(oklab_point - np.array(p, dtype=np.float32)))
        for p in protos
    )


def score_palette_multicolor(
    palette_oklab: np.ndarray,
    required_families: list[str],
    prototypes: dict[str, list[list[float]]],
    threshold: float = FAMILY_MATCH_THRESHOLD,
) -> dict:
    """Score multi-color: every required family matched to a DISTINCT active slot.

    Uses nearest-prototype distance (matches fixture scoring).
    One slot can satisfy at most one family — permutation-invariant.
    """
    n_required = len(required_families)
    n_slots = palette_oklab.shape[0]

    cost = np.zeros((n_required, n_slots), dtype=np.float32)
    for r_idx, fam in enumerate(required_families):
        for s_idx in range(n_slots):
            cost[r_idx, s_idx] = min_dist_to_family(palette_oklab[s_idx], fam, prototypes)

    assigned: list[tuple[int, int, float]] = []
    used_slots: set[int] = set()
    for r_idx in range(n_required):
        row = cost[r_idx].copy()
        if used_slots:
            row[list(used_slots)] = 1e9
        best_slot = int(np.argmin(row))
        best_dist = float(row[best_slot])
        if best_dist < threshold:
            used_slots.add(best_slot)
            assigned.append((r_idx, best_slot, best_dist))

    matched = len(assigned)
    passed = matched == n_required
    return {
        "passed": passed,
        "matched_count": matched,
        "required_count": n_required,
        "threshold": threshold,
        "assignments": [
            {"required_family": required_families[r], "slot": s, "distance": float(d)}
            for r, s, d in assigned
        ],
    }


# ---------------------------------------------------------------------------
# Inference helper
# ---------------------------------------------------------------------------

def load_model(checkpoint_path: Path, device: torch.device) -> PaletteDecoder:
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = PaletteDecoderConfig(**ckpt["model_config"])
    model = PaletteDecoder(config).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model


@torch.inference_mode()
def run_inference(
    model: PaletteDecoder,
    embedding: np.ndarray,   # [384]
    count: int,
    seed: int,
    device: torch.device,
) -> np.ndarray:
    """Run one inference pass and return raw output [9, 5]."""
    text_emb = torch.as_tensor(embedding, dtype=torch.float32).unsqueeze(0).to(device)
    count_mask = torch.zeros(1, MAX_COLORS, dtype=torch.float32, device=device)
    count_mask[0, :count] = 1.0
    seed_noise = torch.as_tensor(
        seed_noise_from_uint32(seed & 0xFFFF_FFFF), dtype=torch.float32
    ).unsqueeze(0).to(device)
    locked_mask = torch.zeros(1, MAX_COLORS, dtype=torch.float32, device=device)
    locked_colors = torch.zeros(1, MAX_COLORS, 4, dtype=torch.float32, device=device)
    output = model(
        text_embedding=text_emb,
        count_mask=count_mask,
        seed_noise=seed_noise,
        locked_mask=locked_mask,
        locked_colors=locked_colors,
    )
    return output.squeeze(0).cpu().numpy()  # [9, 5]


def output_to_oklab(raw_output: np.ndarray, count: int) -> np.ndarray:
    """Convert raw model output [9,5] -> OKLab [count, 3]."""
    return representation_to_oklab_numpy(raw_output[:count])


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def run_clean_benchmark(
    checkpoint_c3: Path,
    checkpoint_c4: Path,
    benchmark: list[dict],
    prototypes: dict[str, list[list[float]]],
    threshold: float,
    device: torch.device,
    cache_dir: str,
    count: int = 5,
    seeds: list[int] = [1, 7, 42, 1337],
) -> dict:
    """Run C3 and C4 on the clean benchmark, identical settings."""
    print(f"Loading E5 encoder...")
    encoder = load_encoder(device="auto", cache_dir=cache_dir)

    # Embed all prompts
    texts = [item["prompt"] for item in benchmark]
    print(f"Embedding {len(texts)} clean benchmark prompts...")
    embeddings = embed_texts(texts, encoder=encoder)

    print(f"Loading Candidate 3 from {checkpoint_c3}...")
    model_c3 = load_model(checkpoint_c3, device)
    print(f"Loading Candidate 4 from {checkpoint_c4}...")
    model_c4 = load_model(checkpoint_c4, device)

    results = []
    for item_idx, item in enumerate(benchmark):
        emb = embeddings[item_idx]
        required = item["required"]
        per_seed_c3 = []
        per_seed_c4 = []

        for seed in seeds:
            raw_c3 = run_inference(model_c3, emb, count, seed, device)
            raw_c4 = run_inference(model_c4, emb, count, seed, device)

            oklab_c3 = output_to_oklab(raw_c3, count)
            oklab_c4 = output_to_oklab(raw_c4, count)

            score_c3 = score_palette_multicolor(oklab_c3, required, prototypes, threshold)
            score_c4 = score_palette_multicolor(oklab_c4, required, prototypes, threshold)

            per_seed_c3.append(score_c3)
            per_seed_c4.append(score_c4)

        # A prompt passes if it passes on ANY seed (consistent with existing eval logic)
        passed_c3 = any(s["passed"] for s in per_seed_c3)
        passed_c4 = any(s["passed"] for s in per_seed_c4)

        results.append({
            "id": item["id"],
            "prompt": item["prompt"],
            "language": item["language"],
            "required": required,
            "c3_passed": passed_c3,
            "c4_passed": passed_c4,
            "c3_per_seed": per_seed_c3,
            "c4_per_seed": per_seed_c4,
        })
        print(f"  [{item_idx+1:2d}/{len(benchmark)}] {item['prompt']!r:50s}  "
              f"C3={'[PASS]' if passed_c3 else '[FAIL]'}  C4={'[PASS]' if passed_c4 else '[FAIL]'}")

    n = len(results)
    c3_pass = sum(1 for r in results if r["c3_passed"])
    c4_pass = sum(1 for r in results if r["c4_passed"])

    return {
        "count_setting": count,
        "seeds": seeds,
        "n_prompts": n,
        "c3_passed": c3_pass,
        "c4_passed": c4_pass,
        "c3_accuracy": c3_pass / n if n > 0 else 0.0,
        "c4_accuracy": c4_pass / n if n > 0 else 0.0,
        "c4_delta": (c4_pass - c3_pass) / n if n > 0 else 0.0,
        "per_prompt": results,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c3", default="ml/palettebrain/checkpoints/candidate-3-best.pt")
    parser.add_argument("--c4", default="ml/palettebrain/checkpoints/candidate-4-best.pt")
    parser.add_argument("--output", default="ml/palettebrain/reports/clean-multicolor-benchmark.v1.json")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Step 1: Verify clean benchmark has zero overlap with C4 training
    # -----------------------------------------------------------------------
    contamination = verify_no_contamination(CLEAN_BENCHMARK_RAW)
    if contamination["contaminated_count"] > 0:
        print("ERROR: Clean benchmark has contaminated prompts!")
        for item in contamination["contaminated"]:
            print(f"  CONTAMINATED: {item['prompt']!r}")
        sys.exit(1)
    print(f"[OK] Zero contamination verified ({len(CLEAN_BENCHMARK_RAW)} prompts, "
          f"0 overlap with C4 training)")

    # -----------------------------------------------------------------------
    # Step 2: Compute frozen overlap with EXISTING evaluation fixture
    # -----------------------------------------------------------------------
    frozen_eval_norm = {normalize(p["prompt"]): p for p in FROZEN_EVAL_MC}
    training_norm_set = C4_TRAINING_NORM
    contaminated_frozen = [
        p for p in FROZEN_EVAL_MC if normalize(p["prompt"]) in training_norm_set
    ]
    clean_frozen = [
        p for p in FROZEN_EVAL_MC if normalize(p["prompt"]) not in training_norm_set
    ]
    print(f"\nFrozen eval multi-color prompts: {len(FROZEN_EVAL_MC)}")
    print(f"  Contaminated (seen verbatim in C4 training): {len(contaminated_frozen)}")
    for p in contaminated_frozen:
        print(f"    {p['prompt']!r}")
    print(f"  Clean (not in C4 training): {len(clean_frozen)}")
    for p in clean_frozen:
        print(f"    {p['prompt']!r}")

    # -----------------------------------------------------------------------
    # Step 3: Freeze benchmark hash BEFORE running models
    # -----------------------------------------------------------------------
    bmark_hash = benchmark_hash(CLEAN_BENCHMARK_RAW)
    print(f"\nClean benchmark hash (frozen before model outputs): {bmark_hash}")

    # -----------------------------------------------------------------------
    # Step 4: Run both models
    # -----------------------------------------------------------------------
    device_str = args.device
    if device_str == "auto":
        import torch
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        import torch
        device = torch.device(device_str)

    fixture = load_color_family_fixture()
    prototypes, threshold = build_family_prototypes(fixture)
    print(f"Using {len(prototypes)} color family prototype sets from fixture (threshold={threshold}).")

    print(f"\nRunning clean benchmark (count={args.count}, seeds=[1,7,42,1337])...")
    results = run_clean_benchmark(
        checkpoint_c3=Path(args.c3),
        checkpoint_c4=Path(args.c4),
        benchmark=CLEAN_BENCHMARK_RAW,
        prototypes=prototypes,
        threshold=threshold,
        device=device,
        cache_dir=args.cache_dir,
        count=args.count,
        seeds=[1, 7, 42, 1337],
    )

    # -----------------------------------------------------------------------
    # Step 5: Assemble final report
    # -----------------------------------------------------------------------
    report = {
        "schemaVersion": 1,
        "purpose": "clean_multicolor_held_out_benchmark_c3_vs_c4",
        "contamination": {
            "c4_training_prompt_count": len(C4_TRAINING_TEXTS),
            "frozen_eval_total_mc_prompts": len(FROZEN_EVAL_MC),
            "contaminated_frozen_count": len(contaminated_frozen),
            "contaminated_frozen_prompts": [p["prompt"] for p in contaminated_frozen],
            "clean_frozen_count": len(clean_frozen),
            "clean_frozen_prompts": [p["prompt"] for p in clean_frozen],
            "note": (
                "Contaminated frozen prompts are demoted to sanity checks. "
                "They must NOT be credited toward multi-color generalization."
            ),
        },
        "cleanBenchmark": {
            "promptCount": len(CLEAN_BENCHMARK_RAW),
            "benchmarkHash": bmark_hash,
            "frozenBeforeModelOutputs": True,
            "zeroOverlapWithC4Training": True,
            "prompts": CLEAN_BENCHMARK_RAW,
        },
        "results": results,
        "summary": {
            "c3_clean_accuracy": results["c3_accuracy"],
            "c4_clean_accuracy": results["c4_accuracy"],
            "c4_delta_vs_c3": results["c4_delta"],
            "c4_improved_over_c3_on_clean_benchmark": results["c4_accuracy"] > results["c3_accuracy"],
            "note": (
                "Multi-color generalization credit is ONLY granted on the clean "
                "zero-overlap benchmark. The contaminated frozen prompts "
                "('red and blue', 'красный и синий') are excluded from this score."
            ),
        },
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"\n=== CLEAN MULTI-COLOR BENCHMARK RESULTS ===")
    print(f"  Contaminated frozen prompts (sanity only): {len(contaminated_frozen)}")
    print(f"  Clean held-out prompts: {results['n_prompts']}")
    print(f"  C3 clean accuracy: {results['c3_accuracy']:.1%}  ({results['c3_passed']}/{results['n_prompts']})")
    print(f"  C4 clean accuracy: {results['c4_accuracy']:.1%}  ({results['c4_passed']}/{results['n_prompts']})")
    print(f"  C4 delta vs C3:    {results['c4_delta']:+.1%}")
    improved = results["c4_accuracy"] > results["c3_accuracy"]
    print(f"  C4 improved over C3 on CLEAN benchmark: {'YES' if improved else 'NO'}")
    print(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
