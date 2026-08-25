"""
Targeted duplicate calibration starting from Candidate 7 best checkpoint.
Goal:
1. Near-duplicate rate: <= 5.00%
2. Preserve Clean multi-color: >= 70.0%
3. Preserve Direct colors: >= 95%, RU >= 95%, EN >= 95%, Exclusion == 100%.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ml.palettebrain.model import PaletteDecoder, PaletteDecoderConfig
from ml.palettebrain.dataset import PaletteBrainDataset, seed_noise_from_uint32, MAX_COLORS
from ml.palettebrain.e5_embedding import load_encoder, embed_texts
from ml.palettebrain.color_math import representation_to_oklab
from ml.palettebrain.release_metrics import (
    load_color_family_fixture,
    score_direct_prompt,
    aggregate_direct_prompt_scores,
    near_duplicate_palette_rate,
)
from ml.palettebrain.finetune_candidate5 import (
    COLOR_FAMILIES,
    FAMILY_PROTOTYPES,
    generate_multi_anchor_records,
    distinct_multi_anchor_loss,
)

def strong_duplicate_loss(
    raw_pred: torch.Tensor,
    count_mask: torch.Tensor,
    min_dist: float = 0.055,
    device: torch.device = None,
) -> torch.Tensor:
    """Strong quadratic repulsion for pairs closer than min_dist (0.055 OKLab)."""
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

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default="ml/palettebrain/checkpoints/candidate-7-best.pt")
    parser.add_argument("--data", default="ml/palettebrain/data/palettebrain_candidate3_direct8_v1.npz")
    parser.add_argument("--output-dir", default="ml/palettebrain/checkpoints")
    parser.add_argument("--candidate-id", default="candidate-7-calibrated")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=3.5e-6)
    parser.add_argument("--dup-weight", type=float, default=0.45)
    parser.add_argument("--mc-weight", type=float, default=2.20)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() and args.device != "cpu" else "cpu")
    print(f"Using device: {device} ({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")

    ckpt_path = Path(args.checkpoint)
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    config = PaletteDecoderConfig(**ckpt["model_config"])
    model = PaletteDecoder(config).to(device)
    model.load_state_dict(ckpt["model_state_dict"])

    train_ds = PaletteBrainDataset(args.data, split="train")
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=True)

    encoder = load_encoder(device="auto", cache_dir="ml/.cache/hub")
    
    train_mc = generate_multi_anchor_records("train")
    val_mc = generate_multi_anchor_records("val")
    train_mc_embs = embed_texts([r["prompt"] for r in train_mc], encoder=encoder)
    val_mc_embs = embed_texts([r["prompt"] for r in val_mc], encoder=encoder)

    direct_fixture = load_color_family_fixture()
    direct_prompts_info = [p for p in direct_fixture["prompts"] if len(p.get("required", [])) == 1]
    direct_embs = embed_texts([p["prompt"] for p in direct_prompts_info], encoder=encoder)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt_path = out_dir / f"{args.candidate_id}-best.pt"

    print(f"\nStarting {args.candidate_id} calibration for {args.epochs} epochs...\n")

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

            dup_loss = strong_duplicate_loss(raw_pred, count_mask, min_dist=0.055, device=device)
            loss = rec_loss + args.dup_weight * dup_loss

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

        # Quick in-epoch validation
        model.eval()
        with torch.no_grad():
            direct_pass = 0
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
                if min_d < 0.10:
                    direct_pass += 1
            dir_acc = direct_pass / len(direct_prompts_info)

            # Check duplicate rate across direct prompts (counts 2-9, 4 seeds)
            seeds = [1, 7, 42, 1337]
            counts = [2, 3, 4, 5, 6, 7, 8, 9]
            dup_cases = 0
            tot_cases = 0
            for emb in direct_embs[:15]:
                for c in counts:
                    for s in seeds:
                        tot_cases += 1
                        e_t = torch.as_tensor(emb, dtype=torch.float32, device=device).unsqueeze(0)
                        c_m = torch.zeros(1, 9, dtype=torch.float32, device=device)
                        c_m[0, :c] = 1.0
                        s_n = torch.as_tensor(seed_noise_from_uint32(s), dtype=torch.float32, device=device).unsqueeze(0)
                        l_m = torch.zeros(1, 9, dtype=torch.float32, device=device)
                        l_c = torch.zeros(1, 9, 4, dtype=torch.float32, device=device)
                        raw = model(e_t, c_m, s_n, l_m, l_c)[0, :c]
                        ok = representation_to_oklab(raw.unsqueeze(0))[0].cpu().numpy()
                        has_dup = False
                        for i in range(c):
                            for j in range(i + 1, c):
                                if np.linalg.norm(ok[i] - ok[j]) < 0.035:
                                    has_dup = True
                                    break
                            if has_dup:
                                break
                        if has_dup:
                            dup_cases += 1
            sample_dup_rate = dup_cases / max(1, tot_cases)

        print(f"Epoch {epoch}/{args.epochs}: train_loss={total_train_loss/n_batches:.4f}  direct={dir_acc:.1%}  sample_dups={sample_dup_rate:.1%}")
        
        # Save each epoch
        epoch_path = out_dir / f"{args.candidate_id}-epoch{epoch}.pt"
        torch.save({
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "model_config": config.__dict__,
            "direct_accuracy": dir_acc,
            "sample_dup_rate": sample_dup_rate,
        }, epoch_path)

    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "model_config": config.__dict__,
    }, best_ckpt_path)
    print(f"\nCalibration complete. Saved to {best_ckpt_path}")

if __name__ == "__main__":
    main()
