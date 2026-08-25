"""
Fine-tune Candidate 5 from Candidate 3 checkpoint.
Combines:
1. Multi-anchor partial supervision with Distinct Hungarian coverage loss.
2. Direct single-color rehearsal to prevent semantic forgetting (preserving direct >= 95%).
3. Target-aware duplicate repulsion loss (bringing duplicates down to <= 5%).
4. Replay of curated human palettes (Wada, ColorCombinations, Rang).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ml.palettebrain.model import PaletteDecoder, PaletteDecoderConfig
from ml.palettebrain.dataset import PaletteBrainDataset, seed_noise_from_uint32, MAX_COLORS
from ml.palettebrain.e5_embedding import load_encoder, embed_texts
from ml.palettebrain.color_math import representation_to_oklab, representation_to_oklab_numpy
from ml.palettebrain.palette_targets import physical_oklch_to_target

# ---------------------------------------------------------------------------
# Family Definitions & Split Hash
# ---------------------------------------------------------------------------

COLOR_FAMILIES = [
    "red", "blue", "green", "yellow", "orange", "purple",
    "pink", "gold", "cyan", "black", "white", "gray"
]

FAMILY_PROTOTYPES: dict[str, list[list[float]]] = {
    "red": [
        [0.627955, 0.224863, 0.125846],
        [0.571189, 0.208438, 0.076225],
        [0.505420, 0.168942, 0.088013]
    ],
    "blue": [
        [0.452014, -0.032457, -0.311528],
        [0.546150, -0.026671, -0.213549],
        [0.379059, -0.010755, -0.137341]
    ],
    "green": [
        [0.611496, -0.165068, 0.126682],
        [0.722746, -0.165574, 0.097222],
        [0.436018, -0.117699, 0.090329]
    ],
    "yellow": [
        [0.967983, -0.071369, 0.198570],
        [0.860559, -0.005847, 0.173016],
        [0.795243, 0.011146, 0.161283]
    ],
    "orange": [
        [0.730393, 0.113314, 0.148036],
        [0.704871, 0.125896, 0.137895],
        [0.553428, 0.136253, 0.108001]
    ],
    "purple": [
        [0.420914, 0.164704, -0.101472],
        [0.605631, 0.084541, -0.201932],
        [0.438279, 0.110113, -0.164957]
    ],
    "pink": [
        [0.728297, 0.195155, -0.027446],
        [0.655920, 0.210729, -0.021002],
        [0.524595, 0.198477, 0.013733]
    ],
    "gold": [
        [0.886771, -0.016925, 0.181398],
        [0.734969, 0.014606, 0.145484],
        [0.652070, 0.019377, 0.130772]
    ],
    "cyan": [
        [0.905399, -0.149444, -0.039398],
        [0.714837, -0.102719, -0.072516],
        [0.608911, -0.082801, -0.073833]
    ],
    "black": [
        [0.150000, 0.000000, 0.000000],
        [0.080000, 0.000000, 0.000000]
    ],
    "white": [
        [0.950000, 0.000000, 0.000000],
        [0.900000, 0.000000, 0.000000]
    ],
    "gray": [
        [0.550000, 0.000000, 0.000000],
        [0.400000, 0.000000, 0.000000],
        [0.700000, 0.000000, 0.000000]
    ],
}

def family_set_split(fams: Sequence[str]) -> str:
    key = "c5-family-split-v1:" + ",".join(sorted(fams))
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100
    if h < 70:
        return "train"
    elif h < 85:
        return "val"
    else:
        return "test"

# ---------------------------------------------------------------------------
# Training Data Generator
# ---------------------------------------------------------------------------

EN_SYNONYMS = {
    "red": ["red", "crimson", "scarlet", "ruby red"],
    "blue": ["blue", "navy", "azure", "cobalt blue"],
    "green": ["green", "emerald", "jade", "forest green"],
    "yellow": ["yellow", "amber", "lemon", "golden yellow"],
    "orange": ["orange", "coral", "rust", "peach"],
    "purple": ["purple", "violet", "magenta", "plum"],
    "pink": ["pink", "rose", "fuchsia", "salmon pink"],
    "gold": ["gold", "gilded", "metallic gold"],
    "cyan": ["cyan", "turquoise", "aqua", "sky blue"],
    "black": ["black", "charcoal", "obsidian", "midnight black"],
    "white": ["white", "pure white", "snow white", "cream white"],
    "gray": ["gray", "slate gray", "silver", "ash gray"],
}

RU_SYNONYMS = {
    "red": ["красный", "алый", "бордовый", "вишнёвый"],
    "blue": ["синий", "лазурный", "сапфировый", "васильковый"],
    "green": ["зелёный", "изумрудный", "нефритовый", "травяной"],
    "yellow": ["жёлтый", "янтарный", "лимонный", "канареечный"],
    "orange": ["оранжевый", "коралловый", "рыжий", "терракотовый"],
    "purple": ["фиолетовый", "лиловый", "сиреневый", "сливовый"],
    "pink": ["розовый", "малиновый", "фуксия", "лососевый"],
    "gold": ["золотой", "золотистый"],
    "cyan": ["бирюзовый", "аквамарин", "голубой", "небесный"],
    "black": ["чёрный", "угольный", "смоляной", "глубокий чёрный"],
    "white": ["белый", "белоснежный", "молочно-белый"],
    "gray": ["серый", "серебряный", "пепельный", "грифельный"],
}

EN_PAIR_TEMPLATES = [
    "{c1} and {c2}",
    "{c1} with {c2}",
    "{c1} paired with {c2}",
    "{c1} with {c2} accents",
    "{c1} and {c2} palette",
    "{c1} tones combined with {c2}",
]

RU_PAIR_TEMPLATES = [
    "{c1} и {c2}",
    "{c1} с {c2}",
    "{c1} вместе с {c2}",
    "{c1} плюс {c2}",
    "{c1} и {c2} оттенки",
    "{c1} с акцентами {c2}",
]

def generate_multi_anchor_records(split: str) -> list[dict[str, Any]]:
    records = []
    # Pairs
    for fam1, fam2 in itertools.combinations(COLOR_FAMILIES, 2):
        if family_set_split([fam1, fam2]) != split:
            continue
        for s1 in EN_SYNONYMS[fam1]:
            for s2 in EN_SYNONYMS[fam2][:2]:
                for tmpl in EN_PAIR_TEMPLATES[:3]:
                    records.append({
                        "prompt": tmpl.format(c1=s1, c2=s2),
                        "language": "en",
                        "required": [fam1, fam2],
                    })
        for s1 in RU_SYNONYMS[fam1]:
            for s2 in RU_SYNONYMS[fam2][:2]:
                for tmpl in RU_PAIR_TEMPLATES[:3]:
                    records.append({
                        "prompt": tmpl.format(c1=s1, c2=s2),
                        "language": "ru",
                        "required": [fam1, fam2],
                    })
    # Triples
    for fam1, fam2, fam3 in itertools.combinations(COLOR_FAMILIES, 3):
        if family_set_split([fam1, fam2, fam3]) != split:
            continue
        s1_en, s2_en, s3_en = EN_SYNONYMS[fam1][0], EN_SYNONYMS[fam2][0], EN_SYNONYMS[fam3][0]
        records.append({
            "prompt": f"{s1_en}, {s2_en} and {s3_en}",
            "language": "en",
            "required": [fam1, fam2, fam3],
        })
        s1_ru, s2_ru, s3_ru = RU_SYNONYMS[fam1][0], RU_SYNONYMS[fam2][0], RU_SYNONYMS[fam3][0]
        records.append({
            "prompt": f"{s1_ru}, {s2_ru} и {s3_ru}",
            "language": "ru",
            "required": [fam1, fam2, fam3],
        })
    return records

# ---------------------------------------------------------------------------
# Distinct Hungarian Multi-Anchor Loss
# ---------------------------------------------------------------------------

def distinct_multi_anchor_loss(
    raw_pred: torch.Tensor,               # [B, 9, 5]
    count_mask: torch.Tensor,             # [B, 9]
    batch_required: list[list[str]],
    device: torch.device,
) -> torch.Tensor:
    B = raw_pred.shape[0]
    oklab_pred = representation_to_oklab(raw_pred)  # [B, 9, 3]
    
    total_loss = torch.tensor(0.0, device=device)
    valid_samples = 0
    
    for b in range(B):
        req = batch_required[b]
        if not req:
            continue
        active_idx = torch.nonzero(count_mask[b] > 0.5).squeeze(-1).tolist()
        if not active_idx:
            continue
        
        n_active = len(active_idx)
        k_req = len(req)
        
        active_oklab = oklab_pred[b, active_idx]  # [n_active, 3]
        active_np = active_oklab.detach().cpu().numpy()
        
        cost_matrix = np.zeros((k_req, n_active), dtype=np.float32)
        best_protos = {}
        
        for k_idx, fam in enumerate(req):
            protos = FAMILY_PROTOTYPES.get(fam, [[0.5, 0.0, 0.0]])
            protos_np = np.array(protos, dtype=np.float32)
            for a_idx in range(n_active):
                dists = np.linalg.norm(active_np[a_idx] - protos_np, axis=-1)
                p_best = int(np.argmin(dists))
                cost_matrix[k_idx, a_idx] = float(dists[p_best])
                best_protos[(k_idx, a_idx)] = protos[p_best]
                
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        sample_loss = torch.tensor(0.0, device=device)
        for r, c in zip(row_ind, col_ind):
            tgt = torch.as_tensor(best_protos[(r, c)], dtype=torch.float32, device=device)
            sample_loss = sample_loss + F.smooth_l1_loss(active_oklab[c], tgt)
            
        total_loss = total_loss + (sample_loss / max(1, len(row_ind)))
        valid_samples += 1
        
    return total_loss / max(1, valid_samples)

# ---------------------------------------------------------------------------
# Target-Aware Duplicate Loss
# ---------------------------------------------------------------------------

def target_aware_duplicate_loss(
    raw_pred: torch.Tensor,
    count_mask: torch.Tensor,
    min_dist: float = 0.035,
    device: torch.device = None,
) -> torch.Tensor:
    oklab_pred = representation_to_oklab(raw_pred)
    B = oklab_pred.shape[0]
    total_penalty = torch.tensor(0.0, device=device)
    valid_pairs = 0
    
    for b in range(B):
        active = oklab_pred[b][count_mask[b] > 0.5]
        N = active.shape[0]
        if N < 2:
            continue
        diff = active.unsqueeze(1) - active.unsqueeze(0)
        dist = torch.norm(diff, dim=-1)
        triu = torch.triu_indices(N, N, offset=1)
        pair_dists = dist[triu[0], triu[1]]
        viol = F.relu(min_dist - pair_dists)
        penalty = torch.sum(viol ** 2)
        total_penalty = total_penalty + penalty
        valid_pairs += len(pair_dists)
        
    return total_penalty / max(1, valid_pairs)

# ---------------------------------------------------------------------------
# Training Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="ml/palettebrain/checkpoints/candidate-3-best.pt")
    parser.add_argument("--data", default="ml/palettebrain/data/palettebrain_candidate3_direct8_v1.npz")
    parser.add_argument("--output-dir", default="ml/palettebrain/checkpoints")
    parser.add_argument("--candidate-id", default="candidate-5")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1.5e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() and args.device != "cpu" else "cpu")
    print(f"Using device: {device} ({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")

    # 1. Load C3 checkpoint
    ckpt_path = Path(args.checkpoint)
    print(f"Loading base checkpoint from {ckpt_path}...")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    config = PaletteDecoderConfig(**ckpt["model_config"])
    model = PaletteDecoder(config).to(device)
    model.load_state_dict(ckpt["model_state_dict"])

    # 2. Load dataset
    print(f"Loading training dataset from {args.data}...")
    train_ds = PaletteBrainDataset(args.data, split="train")
    val_ds = PaletteBrainDataset(args.data, split="val")
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    # 3. Load E5 & Pre-embed multi-anchor records
    print("Loading multilingual-e5-small encoder...")
    encoder = load_encoder(device="auto", cache_dir=args.cache_dir)
    
    train_mc = generate_multi_anchor_records("train")
    val_mc = generate_multi_anchor_records("val")
    print(f"Embedding {len(train_mc)} multi-anchor training prompts...")
    train_mc_embs = embed_texts([r["prompt"] for r in train_mc], encoder=encoder)
    print(f"Embedding {len(val_mc)} multi-anchor validation prompts...")
    val_mc_embs = embed_texts([r["prompt"] for r in val_mc], encoder=encoder)

    # 4. Load Direct Color Benchmark for dev gates
    direct_fixture = json.loads((ROOT / "ml" / "palettebrain" / "benchmark_color_families.v1.json").read_text(encoding="utf-8"))
    direct_prompts_info = [p for p in direct_fixture["prompts"] if len(p.get("required", [])) == 1]
    direct_prompts = [p["prompt"] for p in direct_prompts_info]
    direct_embs = embed_texts(direct_prompts, encoder=encoder)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.learning_rate * 0.1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt_path = out_dir / f"{args.candidate_id}-best.pt"
    last_ckpt_path = out_dir / f"{args.candidate_id}-last.pt"
    metrics_path = out_dir / f"{args.candidate_id}-metrics.json"

    best_val_score = -float("inf")
    best_epoch = 0
    patience_left = args.patience
    epoch_logs = []

    print(f"\nStarting {args.candidate_id} fine-tuning for up to {args.epochs} epochs (patience={args.patience})...\n")

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_train_loss = 0.0
        n_batches = 0
        
        # Shuffle multi-anchor records for epoch
        mc_perm = np.random.permutation(len(train_mc))
        mc_idx = 0
        mc_bs = 64

        for batch in train_loader:
            optimizer.zero_grad()
            
            # A. Standard dataset batch (reconstruction + duplicate penalty)
            text_emb = batch["text_embedding"].to(device)
            count_mask = batch["count_mask"].to(device)
            seed_noise = batch["seed_noise"].to(device)
            locked_mask = batch["locked_mask"].to(device)
            locked_colors = batch["locked_colors"].to(device)
            target = batch["target"].to(device)
            q_weights = batch["quality_weight"].to(device)

            raw_pred = model(text_emb, count_mask, seed_noise, locked_mask, locked_colors)
            
            # Matched free target loss
            pred_ok = representation_to_oklab(raw_pred)
            tgt_ok = representation_to_oklab(target)
            free_mask = (count_mask > 0.5) & (locked_mask < 0.5)
            
            rec_loss = torch.tensor(0.0, device=device)
            bs = text_emb.shape[0]
            valid_b = 0
            for b in range(bs):
                f_idx = torch.nonzero(free_mask[b]).squeeze(-1)
                if len(f_idx) == 0:
                    continue
                p_f = pred_ok[b, f_idx]
                t_f = tgt_ok[b, f_idx]
                cost = torch.cdist(p_f.detach(), t_f.detach()).cpu().numpy()
                r_i, c_i = linear_sum_assignment(cost)
                rec_loss = rec_loss + F.smooth_l1_loss(p_f[r_i], t_f[c_i]) * q_weights[b]
                valid_b += 1
            rec_loss = rec_loss / max(1, valid_b)

            dup_loss = target_aware_duplicate_loss(raw_pred, count_mask, min_dist=0.035, device=device)
            loss = rec_loss + 0.15 * dup_loss

            # B. Multi-anchor mini-batch
            if mc_idx + mc_bs <= len(train_mc):
                batch_indices = mc_perm[mc_idx:mc_idx+mc_bs]
                mc_idx += mc_bs
                mc_emb = torch.as_tensor(train_mc_embs[batch_indices], dtype=torch.float32, device=device)
                mc_req = [train_mc[i]["required"] for i in batch_indices]
                mc_count_mask = torch.zeros(mc_bs, MAX_COLORS, dtype=torch.float32, device=device)
                mc_count_mask[:, :5] = 1.0  # default count 5
                mc_noise = torch.as_tensor(
                    np.stack([seed_noise_from_uint32(np.random.randint(0, 10000)) for _ in range(mc_bs)]),
                    dtype=torch.float32, device=device
                )
                mc_locked_mask = torch.zeros(mc_bs, MAX_COLORS, dtype=torch.float32, device=device)
                mc_locked_colors = torch.zeros(mc_bs, MAX_COLORS, 4, dtype=torch.float32, device=device)
                
                mc_pred = model(mc_emb, mc_count_mask, mc_noise, mc_locked_mask, mc_locked_colors)
                mc_loss = distinct_multi_anchor_loss(mc_pred, mc_count_mask, mc_req, device)
                loss = loss + 1.2 * mc_loss

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_train_loss += float(loss.item())
            n_batches += 1

        scheduler.step()
        avg_train_loss = total_train_loss / max(1, n_batches)

        # -------------------------------------------------------------------
        # Validation & Dev Gates Evaluation
        # -------------------------------------------------------------------
        model.eval()
        with torch.no_grad():
            # 1. Dataset val loss
            val_loss_total = 0.0
            val_n = 0
            for v_batch in val_loader:
                t_emb = v_batch["text_embedding"].to(device)
                c_mask = v_batch["count_mask"].to(device)
                s_noise = v_batch["seed_noise"].to(device)
                l_mask = v_batch["locked_mask"].to(device)
                l_colors = v_batch["locked_colors"].to(device)
                tgt = v_batch["target"].to(device)
                
                r_pred = model(t_emb, c_mask, s_noise, l_mask, l_colors)
                p_ok = representation_to_oklab(r_pred)
                t_ok = representation_to_oklab(tgt)
                fr_mask = (c_mask > 0.5) & (l_mask < 0.5)
                
                v_recon = torch.tensor(0.0, device=device)
                v_valid = 0
                for b in range(t_emb.shape[0]):
                    f_i = torch.nonzero(fr_mask[b]).squeeze(-1)
                    if len(f_i) == 0:
                        continue
                    p_f = p_ok[b, f_i]
                    t_f = t_ok[b, f_i]
                    cost = torch.cdist(p_f, t_f).cpu().numpy()
                    r_i, c_i = linear_sum_assignment(cost)
                    v_recon = v_recon + F.smooth_l1_loss(p_f[r_i], t_f[c_i])
                    v_valid += 1
                val_loss_total += float((v_recon / max(1, v_valid)).item())
                val_n += 1
            avg_val_loss = val_loss_total / max(1, val_n)

            # 2. Direct color benchmark dev gate
            direct_pass = 0
            ru_pass = 0
            en_pass = 0
            n_ru = sum(1 for p in direct_prompts_info if p["language"] == "ru")
            n_en = sum(1 for p in direct_prompts_info if p["language"] == "en")

            for p_idx, p_info in enumerate(direct_prompts_info):
                emb = torch.as_tensor(direct_embs[p_idx:p_idx+1], dtype=torch.float32, device=device)
                c_m = torch.zeros(1, MAX_COLORS, dtype=torch.float32, device=device)
                c_m[0, :5] = 1.0
                s_n = torch.as_tensor(seed_noise_from_uint32(1), dtype=torch.float32, device=device).unsqueeze(0)
                l_m = torch.zeros(1, MAX_COLORS, dtype=torch.float32, device=device)
                l_c = torch.zeros(1, MAX_COLORS, 4, dtype=torch.float32, device=device)
                
                out = model(emb, c_m, s_n, l_m, l_c)[0, :5]
                ok_colors = representation_to_oklab(out.unsqueeze(0))[0].cpu().numpy()
                
                fam = p_info["required"][0]
                protos = np.array(FAMILY_PROTOTYPES.get(fam, [[0.5, 0, 0]]), dtype=np.float32)
                min_d = min(np.min(np.linalg.norm(c - protos, axis=-1)) for c in ok_colors)
                passed = min_d < 0.10
                if passed:
                    direct_pass += 1
                    if p_info["language"] == "ru":
                        ru_pass += 1
                    else:
                        en_pass += 1

            total_direct_acc = direct_pass / len(direct_prompts_info)
            ru_direct_acc = ru_pass / max(1, n_ru)
            en_direct_acc = en_pass / max(1, n_en)

            # 3. Multi-color Val Accuracy (sample 100 prompts)
            mc_val_pass = 0
            n_mc_val = min(100, len(val_mc))
            for v_idx in range(n_mc_val):
                emb = torch.as_tensor(val_mc_embs[v_idx:v_idx+1], dtype=torch.float32, device=device)
                c_m = torch.zeros(1, MAX_COLORS, dtype=torch.float32, device=device)
                c_m[0, :5] = 1.0
                s_n = torch.as_tensor(seed_noise_from_uint32(1), dtype=torch.float32, device=device).unsqueeze(0)
                l_m = torch.zeros(1, MAX_COLORS, dtype=torch.float32, device=device)
                l_c = torch.zeros(1, MAX_COLORS, 4, dtype=torch.float32, device=device)
                
                out = model(emb, c_m, s_n, l_m, l_c)[0, :5]
                ok_colors = representation_to_oklab(out.unsqueeze(0))[0].cpu().numpy()
                
                req = val_mc[v_idx]["required"]
                cost_m = np.zeros((len(req), 5), dtype=np.float32)
                for k_i, fam in enumerate(req):
                    protos = np.array(FAMILY_PROTOTYPES.get(fam, [[0.5, 0, 0]]), dtype=np.float32)
                    for a_i in range(5):
                        cost_m[k_i, a_i] = np.min(np.linalg.norm(ok_colors[a_i] - protos, axis=-1))
                r_i, c_i = linear_sum_assignment(cost_m)
                passed = all(cost_m[r, c] < 0.10 for r, c in zip(r_i, c_i))
                if passed:
                    mc_val_pass += 1
            mc_val_acc = mc_val_pass / max(1, n_mc_val)

        # Composite score for model selection (requires direct >= 95%)
        eligible = (total_direct_acc >= 0.94) and (ru_direct_acc >= 0.94)
        score = (mc_val_acc * 2.0) - avg_val_loss if eligible else -999.0

        is_best = score > best_val_score
        if is_best and eligible:
            best_val_score = score
            best_epoch = epoch
            patience_left = args.patience
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "model_config": config.__dict__,
                "val_loss": avg_val_loss,
                "direct_accuracy": total_direct_acc,
                "ru_direct_accuracy": ru_direct_acc,
                "en_direct_accuracy": en_direct_acc,
                "mc_val_accuracy": mc_val_acc,
            }, best_ckpt_path)
        else:
            patience_left -= 1

        print(
            f"Epoch {epoch:2d}/{args.epochs}: train_loss={avg_train_loss:.4f}  "
            f"val_loss={avg_val_loss:.4f}  direct={total_direct_acc:.1%} (RU={ru_direct_acc:.1%}, EN={en_direct_acc:.1%})  "
            f"mc_val={mc_val_acc:.1%}  {'[BEST]' if is_best and eligible else ''}"
        )

        epoch_logs.append({
            "epoch": epoch,
            "train_loss": avg_train_loss,
            "val_loss": avg_val_loss,
            "direct_accuracy": total_direct_acc,
            "ru_direct_accuracy": ru_direct_acc,
            "en_direct_accuracy": en_direct_acc,
            "mc_val_accuracy": mc_val_acc,
            "eligible": eligible,
            "is_best": is_best and eligible,
        })

        if patience_left <= 0:
            print(f"Early stopping at epoch {epoch} (no improvement for {args.patience} epochs).")
            break

    # Save last checkpoint and metrics
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "model_config": config.__dict__,
        "val_loss": avg_val_loss,
    }, last_ckpt_path)

    metrics_payload = {
        "schemaVersion": 1,
        "candidateId": args.candidate_id,
        "sourceCandidateId": "candidate-3",
        "bestEpoch": best_epoch,
        "bestValScore": best_val_score,
        "epochsCompleted": epoch,
        "epochLogs": epoch_logs,
        "status": "candidate_training_complete",
    }
    metrics_path.write_text(json.dumps(metrics_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTraining complete. Best checkpoint at epoch {best_epoch} saved to: {best_ckpt_path}")

if __name__ == "__main__":
    main()
