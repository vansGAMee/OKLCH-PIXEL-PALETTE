"""
Surgical fine-tuning for Candidate 6 starting from Candidate 5 best checkpoint.
Goal:
1. Clean multi-color generalization: 66.99% -> >= 70.0%
2. Near-duplicate rate: 9.53% -> <= 5.0%
3. Preserve direct colors (>= 95%), RU (>= 95%), EN (>= 95%), and real holdout distance (<= 0.145).
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
from ml.palettebrain.finetune_candidate5 import (
    COLOR_FAMILIES,
    FAMILY_PROTOTYPES,
    family_set_split,
    generate_multi_anchor_records,
    distinct_multi_anchor_loss,
)

# ---------------------------------------------------------------------------
# Calibrated Target-Aware Duplicate Loss
# ---------------------------------------------------------------------------

def calibrated_duplicate_loss(
    raw_pred: torch.Tensor,
    count_mask: torch.Tensor,
    min_dist: float = 0.040,
    device: torch.device = None,
) -> torch.Tensor:
    """Penalizes active slots whose predicted OKLab distance is < min_dist (0.040)."""
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
    parser.add_argument("--checkpoint", default="ml/palettebrain/checkpoints/candidate-5-best.pt")
    parser.add_argument("--data", default="ml/palettebrain/data/palettebrain_candidate3_direct8_v1.npz")
    parser.add_argument("--output-dir", default="ml/palettebrain/checkpoints")
    parser.add_argument("--candidate-id", default="candidate-6")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=8e-6)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dup-weight", type=float, default=0.24)
    parser.add_argument("--mc-weight", type=float, default=1.60)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() and args.device != "cpu" else "cpu")
    print(f"Using device: {device} ({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")

    # 1. Load C5 checkpoint
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
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.learning_rate * 0.2)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt_path = out_dir / f"{args.candidate_id}-best.pt"
    last_ckpt_path = out_dir / f"{args.candidate_id}-last.pt"
    metrics_path = out_dir / f"{args.candidate_id}-metrics.json"

    best_val_score = -float("inf")
    best_epoch = 0
    patience_left = args.patience
    epoch_logs = []

    print(f"\nStarting {args.candidate_id} surgical fine-tuning for up to {args.epochs} epochs (patience={args.patience})...\n")

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_train_loss = 0.0
        n_batches = 0
        
        mc_perm = np.random.permutation(len(train_mc))
        mc_idx = 0
        mc_bs = 64

        for batch in train_loader:
            optimizer.zero_grad()
            
            text_emb = batch["text_embedding"].to(device)
            count_mask = batch["count_mask"].to(device)
            seed_noise = batch["seed_noise"].to(device)
            locked_mask = batch["locked_mask"].to(device)
            locked_colors = batch["locked_colors"].to(device)
            target = batch["target"].to(device)
            q_weights = batch["quality_weight"].to(device)

            raw_pred = model(text_emb, count_mask, seed_noise, locked_mask, locked_colors)
            
            # Reconstruction loss on free slots
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

            dup_loss = calibrated_duplicate_loss(raw_pred, count_mask, min_dist=0.040, device=device)
            loss = rec_loss + args.dup_weight * dup_loss

            # Multi-anchor mini-batch
            if mc_idx + mc_bs <= len(train_mc):
                batch_indices = mc_perm[mc_idx:mc_idx+mc_bs]
                mc_idx += mc_bs
                mc_emb = torch.as_tensor(train_mc_embs[batch_indices], dtype=torch.float32, device=device)
                mc_req = [train_mc[i]["required"] for i in batch_indices]
                mc_count_mask = torch.zeros(mc_bs, MAX_COLORS, dtype=torch.float32, device=device)
                mc_count_mask[:, :5] = 1.0
                mc_noise = torch.as_tensor(
                    np.stack([seed_noise_from_uint32(np.random.randint(0, 10000)) for _ in range(mc_bs)]),
                    dtype=torch.float32, device=device
                )
                mc_locked_mask = torch.zeros(mc_bs, MAX_COLORS, dtype=torch.float32, device=device)
                mc_locked_colors = torch.zeros(mc_bs, MAX_COLORS, 4, dtype=torch.float32, device=device)
                
                mc_pred = model(mc_emb, mc_count_mask, mc_noise, mc_locked_mask, mc_locked_colors)
                mc_loss = distinct_multi_anchor_loss(mc_pred, mc_count_mask, mc_req, device)
                loss = loss + args.mc_weight * mc_loss

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_train_loss += float(loss.item())
            n_batches += 1

        scheduler.step()
        avg_train_loss = total_train_loss / max(1, n_batches)

        # Validation & Dev Gates Evaluation
        model.eval()
        with torch.no_grad():
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

            # Direct color dev gate
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

            # Multi-color Val Accuracy (sample 150 prompts)
            mc_val_pass = 0
            n_mc_val = min(150, len(val_mc))
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

        eligible = (total_direct_acc >= 0.95) and (ru_direct_acc >= 0.95) and (en_direct_acc >= 0.95)
        score = (mc_val_acc * 3.0) - avg_val_loss if eligible else -999.0

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
        "sourceCandidateId": "candidate-5",
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
