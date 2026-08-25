"""
Comprehensive Clean Multi-Color Held-Out Benchmark v2 Evaluator.
Evaluates any candidate against Candidate 3 on benchmark_clean_multicolor_v2.json
(824 zero-overlap test prompts across 50 held-out family sets).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ml.palettebrain.e5_embedding import load_encoder, embed_texts
from ml.palettebrain.model import PaletteDecoder, PaletteDecoderConfig
from ml.palettebrain.dataset import seed_noise_from_uint32, MAX_COLORS
from ml.palettebrain.color_math import representation_to_oklab_numpy

FAMILY_PROTOTYPES = {
    "red": [[0.627955, 0.224863, 0.125846], [0.571189, 0.208438, 0.076225], [0.50542, 0.168942, 0.088013]],
    "blue": [[0.452014, -0.032457, -0.311528], [0.54615, -0.026671, -0.213549], [0.379059, -0.010755, -0.137341]],
    "green": [[0.611496, -0.165068, 0.126682], [0.722746, -0.165574, 0.097222], [0.436018, -0.117699, 0.090329]],
    "yellow": [[0.967983, -0.071369, 0.19857], [0.860559, -0.005847, 0.173016], [0.795243, 0.011146, 0.161283]],
    "orange": [[0.730393, 0.113314, 0.148036], [0.704871, 0.125896, 0.137895], [0.553428, 0.136253, 0.108001]],
    "purple": [[0.420914, 0.164704, -0.101472], [0.605631, 0.084541, -0.201932], [0.438279, 0.110113, -0.164957]],
    "pink": [[0.728297, 0.195155, -0.027446], [0.65592, 0.210729, -0.021002], [0.524595, 0.198477, 0.013733]],
    "gold": [[0.886771, -0.016925, 0.181398], [0.734969, 0.014606, 0.145484], [0.65207, 0.019377, 0.130772]],
    "cyan": [[0.905399, -0.149444, -0.039398], [0.714837, -0.102719, -0.072516], [0.608911, -0.082801, -0.073833]],
    "black": [[0.15, 0.0, 0.0], [0.08, 0.0, 0.0]],
    "white": [[0.95, 0.0, 0.0], [0.90, 0.0, 0.0]],
    "gray": [[0.55, 0.0, 0.0], [0.40, 0.0, 0.0], [0.70, 0.0, 0.0]],
}

MATCH_THRESHOLD = 0.10

def load_model(ckpt_path: Path, device: torch.device) -> PaletteDecoder:
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cfg = PaletteDecoderConfig(**ckpt["model_config"])
    model = PaletteDecoder(cfg).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model

@torch.inference_mode()
def infer_palette(model: PaletteDecoder, emb: np.ndarray, count: int, seed: int, device: torch.device) -> np.ndarray:
    text_emb = torch.as_tensor(emb, dtype=torch.float32).unsqueeze(0).to(device)
    count_mask = torch.zeros(1, MAX_COLORS, dtype=torch.float32, device=device)
    count_mask[0, :count] = 1.0
    seed_noise = torch.as_tensor(seed_noise_from_uint32(seed), dtype=torch.float32).unsqueeze(0).to(device)
    locked_mask = torch.zeros(1, MAX_COLORS, dtype=torch.float32, device=device)
    locked_colors = torch.zeros(1, MAX_COLORS, 4, dtype=torch.float32, device=device)
    out = model(text_emb, count_mask, seed_noise, locked_mask, locked_colors)[0, :count].cpu().numpy()
    return representation_to_oklab_numpy(out[None, ...])[0]

def score_distinct_palette(oklab_colors: np.ndarray, required: list[str]) -> bool:
    k_req = len(required)
    n_slots = oklab_colors.shape[0]
    cost = np.zeros((k_req, n_slots), dtype=np.float32)
    for k_i, fam in enumerate(required):
        protos = np.array(FAMILY_PROTOTYPES.get(fam, [[0.5, 0, 0]]), dtype=np.float32)
        for s_i in range(n_slots):
            cost[k_i, s_i] = np.min(np.linalg.norm(oklab_colors[s_i] - protos, axis=-1))
    r_i, c_i = linear_sum_assignment(cost)
    return all(cost[r, c] < MATCH_THRESHOLD for r, c in zip(r_i, c_i))

def evaluate_models(
    baseline_path: Path,
    candidate_path: Path,
    benchmark_path: Path,
    output_path: Path,
    device_str: str = "auto",
    cache_dir: str = "ml/.cache/hub",
    seeds: list[int] = [1, 7, 42, 1337],
    count: int = 5,
) -> dict[str, Any]:
    device = torch.device("cuda" if torch.cuda.is_available() and device_str != "cpu" else "cpu")
    print(f"Using device: {device}")
    
    bmark_data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    prompts = bmark_data["prompts"]
    print(f"Loaded frozen benchmark v2: {len(prompts)} prompts (SHA-256: {bmark_data['benchmarkSha256']})")
    
    encoder = load_encoder(device="auto", cache_dir=cache_dir)
    print(f"Embedding {len(prompts)} prompts with E5...")
    embs = embed_texts([p["prompt"] for p in prompts], encoder=encoder)
    
    print(f"Loading Baseline model from {baseline_path}...")
    model_base = load_model(baseline_path, device)
    print(f"Loading Candidate model from {candidate_path}...")
    model_cand = load_model(candidate_path, device)
    
    base_passes = 0
    cand_passes = 0
    base_ru_passes = 0
    cand_ru_passes = 0
    base_en_passes = 0
    cand_en_passes = 0
    n_ru = 0
    n_en = 0
    
    results = []
    
    for idx, p_info in enumerate(prompts):
        emb = embs[idx]
        req = p_info["required"]
        lang = p_info["language"]
        
        base_seed_pass = any(score_distinct_palette(infer_palette(model_base, emb, count, s, device), req) for s in seeds)
        cand_seed_pass = any(score_distinct_palette(infer_palette(model_cand, emb, count, s, device), req) for s in seeds)
        
        if base_seed_pass:
            base_passes += 1
            if lang == "ru": base_ru_passes += 1
            else: base_en_passes += 1
            
        if cand_seed_pass:
            cand_passes += 1
            if lang == "ru": cand_ru_passes += 1
            else: cand_en_passes += 1
            
        if lang == "ru": n_ru += 1
        else: n_en += 1
        
        results.append({
            "id": p_info["id"],
            "prompt": p_info["prompt"],
            "language": lang,
            "required": req,
            "family_set": p_info["family_set"],
            "baseline_passed": base_seed_pass,
            "candidate_passed": cand_seed_pass,
        })
        
    n_total = len(prompts)
    base_acc = base_passes / n_total
    cand_acc = cand_passes / n_total
    
    summary = {
        "schemaVersion": 2,
        "benchmarkSha256": bmark_data["benchmarkSha256"],
        "promptCount": n_total,
        "baselinePath": str(baseline_path),
        "candidatePath": str(candidate_path),
        "baselineAccuracy": base_acc,
        "candidateAccuracy": cand_acc,
        "delta": cand_acc - base_acc,
        "baselineRuAccuracy": base_ru_passes / max(1, n_ru),
        "candidateRuAccuracy": cand_ru_passes / max(1, n_ru),
        "baselineEnAccuracy": base_en_passes / max(1, n_en),
        "candidateEnAccuracy": cand_en_passes / max(1, n_en),
        "candidateImprovedOverBaseline": cand_acc > base_acc,
        "results": results,
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    
    print("\n=== CLEAN MULTI-COLOR BENCHMARK v2 RESULTS ===")
    print(f"  Total Held-Out Prompts: {n_total} (50 disjoint family sets)")
    print(f"  Baseline Accuracy:      {base_acc:.1%} ({base_passes}/{n_total})")
    print(f"  Candidate Accuracy:     {cand_acc:.1%} ({cand_passes}/{n_total})")
    print(f"  Delta:                  {summary['delta']:+.1%}")
    print(f"  RU Accuracy:            {summary['candidateRuAccuracy']:.1%} vs Base {summary['baselineRuAccuracy']:.1%}")
    print(f"  EN Accuracy:            {summary['candidateEnAccuracy']:.1%} vs Base {summary['baselineEnAccuracy']:.1%}")
    print(f"  Improved on Clean Test: {'YES' if summary['candidateImprovedOverBaseline'] else 'NO'}")
    print(f"Report written to: {output_path}")
    
    return summary

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="ml/palettebrain/checkpoints/candidate-3-best.pt")
    parser.add_argument("--candidate", default="ml/palettebrain/checkpoints/candidate-5-best.pt")
    parser.add_argument("--benchmark", default="ml/palettebrain/benchmark_clean_multicolor_v2.json")
    parser.add_argument("--output", default="ml/palettebrain/reports/clean-multicolor-benchmark-v2.json")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    args = parser.parse_args()
    
    evaluate_models(
        baseline_path=Path(args.baseline),
        candidate_path=Path(args.candidate),
        benchmark_path=Path(args.benchmark),
        output_path=Path(args.output),
        device_str=args.device,
        cache_dir=args.cache_dir,
    )

if __name__ == "__main__":
    main()
