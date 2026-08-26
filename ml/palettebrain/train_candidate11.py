"""Repaired two-stage Candidate 11 trainer (never creates Candidate 12).

The original untracked C11 trainer could not be recovered.  This version is an
auditable continuation pipeline: it preserves every compatible C11 weight,
adds slot-specific visual cross-attention, and records all optimizer/scheduler
state required for deterministic resume.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor
from torch.utils.data import ConcatDataset, DataLoader, Dataset, WeightedRandomSampler

try:
    from .color_distribution import smooth_circular_histogram_loss
    from .model import PaletteDecoder, PaletteDecoderConfig, load_inherited_state
    from .train_decoder import decoder_loss
except ImportError:
    from color_distribution import smooth_circular_histogram_loss
    from model import PaletteDecoder, PaletteDecoderConfig, load_inherited_state
    from train_decoder import decoder_loss


class C11Dataset(Dataset[dict[str, Tensor]]):
    def __init__(self, path: str | Path, split: str) -> None:
        archive = np.load(path, allow_pickle=False)
        names = set(archive.files)
        if {"text_embedding", "split"} <= names:
            mapping = {
                "text_embedding": "text_embedding", "color_prior": "color_prior",
                "teacher_latent": "teacher_latent", "count_mask": "count_mask",
                "seed_noise": "seed_noise", "locked_mask": "locked_mask",
                "locked_colors": "locked_colors", "target": "target",
                "quality_weight": "quality_weight", "split": "split",
            }
            selected = np.asarray(archive[mapping["split"]] == split)
        elif {"embeddings", "splits"} <= names:
            mapping = {
                "text_embedding": "embeddings", "count_mask": "count_masks",
                "seed_noise": "seed_noise", "locked_mask": "locked_masks",
                "locked_colors": "locked_colors", "target": "targets",
                "quality_weight": "quality_weights", "split": "splits",
            }
            split_id = {"train": 0, "val": 1, "test": 2}[split]
            selected = np.asarray(archive[mapping["split"]] == split_id)
        else:
            raise ValueError(f"unsupported PaletteBrain archive schema: {sorted(names)}")
        self.values: dict[str, np.ndarray] = {}
        for output_name, source_name in mapping.items():
            if output_name == "split" or source_name not in names:
                continue
            self.values[output_name] = np.asarray(archive[source_name][selected])
        self.length = int(selected.sum())
        self.has_visual_targets = "color_prior" in self.values and "teacher_latent" in self.values
        if self.length == 0:
            raise ValueError(f"{path} has no {split} records")

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, index: int) -> dict[str, Tensor]:
        result = {
            name: torch.as_tensor(value[index], dtype=torch.float32)
            for name, value in self.values.items()
        }
        result.setdefault("color_prior", torch.zeros(390, dtype=torch.float32))
        result.setdefault("teacher_latent", torch.zeros(128, dtype=torch.float32))
        result["visual_weight"] = torch.tensor(1.0 if self.has_visual_targets else 0.0)
        return result


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _device(name: str) -> torch.device:
    selected = torch.device("cuda" if name == "auto" and torch.cuda.is_available() else ("cpu" if name == "auto" else name))
    if selected.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return selected


def _stage_a_release_evidence(path: str | None) -> None:
    if not path:
        raise RuntimeError("Stage B requires --stage-a-eval-report from the frozen v3 benchmark")
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    if report.get("benchmarkId") != "palettebrain-candidate11-semantic-v3-frozen-2026-08-26":
        raise RuntimeError("Stage A report is not from the frozen semantic v3 benchmark")
    if float(report.get("metrics", {}).get("semanticFamilyWin", 0.0)) < 0.80:
        raise RuntimeError("Stage A honest semantic family win is below 80%; repair Candidate 11")


def _configure_model(args: argparse.Namespace) -> PaletteDecoder:
    checkpoint = torch.load(args.initialize_from, map_location="cpu", weights_only=True)
    config_values = dict(checkpoint["model_config"])
    config_values.setdefault("histogram_bins", 390)
    config_values.setdefault("visual_latent_dim", 128)
    config_values["visual_conditioning"] = "slot_cross_attention"
    config_values["auxiliary_conditioning_scale"] = 0.35
    model = PaletteDecoder(PaletteDecoderConfig(**config_values))
    load_inherited_state(
        model,
        checkpoint["model_state_dict"],
        allowed_missing_prefixes=("visual_cross_attention.",),
        allowed_unexpected_prefixes=(),
    )
    return model


def _stage_a_loss(model: PaletteDecoder, batch: dict[str, Tensor]) -> tuple[Tensor, dict[str, Tensor]]:
    prior_logits, style_latent, _, _ = model.bridge(batch["text_embedding"])
    prior = smooth_circular_histogram_loss(prior_logits, batch["color_prior"])
    style = F.smooth_l1_loss(style_latent, batch["teacher_latent"])
    predicted = F.normalize(torch.softmax(prior_logits, dim=-1), dim=-1)
    expected = F.normalize(batch["color_prior"], dim=-1)
    positive = (predicted * expected).sum(dim=-1)
    negative = (predicted * expected.roll(1, 0)).sum(dim=-1)
    ranking = F.relu(0.10 - positive + negative).mean()
    output = model(
        batch["text_embedding"], batch["count_mask"], batch["seed_noise"],
        batch["locked_mask"], batch["locked_colors"],
    )
    palette, _ = decoder_loss(
        output, batch["target"], batch["count_mask"], batch["locked_mask"]
    )
    total = prior + 0.25 * style + 0.5 * ranking + 0.25 * palette
    return total, {"prior": prior, "style": style, "ranking": ranking, "palette": palette}


def _stage_b_loss(model: PaletteDecoder, batch: dict[str, Tensor]) -> tuple[Tensor, dict[str, Tensor]]:
    output = model(
        batch["text_embedding"], batch["count_mask"], batch["seed_noise"],
        batch["locked_mask"], batch["locked_colors"],
    )
    palette, components = decoder_loss(
        output, batch["target"], batch["count_mask"], batch["locked_mask"]
    )
    if float(batch["visual_weight"].sum()) > 0:
        prior_logits, style_latent, _, _ = model.bridge(batch["text_embedding"])
        visual_weight = batch["visual_weight"]
        target = batch["color_prior"] + 1e-6
        target = target / target.sum(dim=-1, keepdim=True)
        prior_by_row = F.kl_div(F.log_softmax(prior_logits, dim=-1), target, reduction="none").sum(dim=-1)
        prior = (prior_by_row * visual_weight).sum() / visual_weight.sum().clamp_min(1)
        style_by_row = F.smooth_l1_loss(style_latent, batch["teacher_latent"], reduction="none").mean(dim=-1)
        style = (style_by_row * visual_weight).sum() / visual_weight.sum().clamp_min(1)
    else:
        prior = palette.new_zeros(())
        style = palette.new_zeros(())
    total = palette + 0.25 * prior + 0.05 * style
    return total, {"palette": palette, "prior": prior, "style": style, **components}


def train(args: argparse.Namespace) -> dict[str, Any]:
    if args.stage == "b":
        _stage_a_release_evidence(args.stage_a_eval_report)
    _seed_everything(args.seed)
    device = _device(args.device)
    model = _configure_model(args).to(device)
    if args.stage == "a":
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(name.startswith(("bridge.", "visual_cross_attention.")))
    new_parameters, inherited_parameters = [], []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        (new_parameters if name.startswith(("bridge.", "visual_cross_attention.")) else inherited_parameters).append(parameter)
    parameter_groups = [{"params": new_parameters, "lr": args.new_lr}]
    if inherited_parameters:
        parameter_groups.append({"params": inherited_parameters, "lr": args.inherited_lr})
    optimizer = torch.optim.AdamW(parameter_groups, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    start_epoch = 0
    if args.resume:
        resumed = torch.load(args.resume, map_location="cpu", weights_only=True)
        model.load_state_dict(resumed["model_state_dict"], strict=True)
        optimizer.load_state_dict(resumed["optimizer_state_dict"])
        scheduler.load_state_dict(resumed["scheduler_state_dict"])
        start_epoch = int(resumed["epoch"]) + 1

    train_sets: list[Dataset[dict[str, Tensor]]] = [C11Dataset(args.data, "train")]
    val_sets: list[Dataset[dict[str, Tensor]]] = [C11Dataset(args.data, "val")]
    if args.stage == "b":
        for replay_path in args.replay_data:
            train_sets.append(C11Dataset(replay_path, "train"))
            val_sets.append(C11Dataset(replay_path, "val"))
    train_data = train_sets[0] if len(train_sets) == 1 else ConcatDataset(train_sets)
    val_data = val_sets[0] if len(val_sets) == 1 else ConcatDataset(val_sets)
    sampler = None
    if len(train_sets) > 1:
        group_weight = 1.0 / len(train_sets)
        weights = torch.cat([
            torch.full((len(dataset),), group_weight / len(dataset), dtype=torch.double)
            for dataset in train_sets
        ])
        sampler = WeightedRandomSampler(
            weights, num_samples=len(train_data), replacement=True,
            generator=torch.Generator().manual_seed(args.seed),
        )
    train_loader = DataLoader(
        train_data, batch_size=args.batch_size, sampler=sampler,
        shuffle=sampler is None, generator=torch.Generator().manual_seed(args.seed),
    )
    val_loader = DataLoader(val_data, batch_size=args.batch_size, shuffle=False)
    loss_function = _stage_a_loss if args.stage == "a" else _stage_b_loss
    history: list[dict[str, Any]] = []
    best_loss = float("inf")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(start_epoch, args.epochs):
        row: dict[str, Any] = {"epoch": epoch}
        for split, loader in (("train", train_loader), ("val", val_loader)):
            model.train(split == "train")
            totals: dict[str, float] = {}
            batches = 0
            for source_batch in loader:
                batch = {name: value.to(device) for name, value in source_batch.items()}
                if split == "train":
                    optimizer.zero_grad(set_to_none=True)
                with torch.set_grad_enabled(split == "train"):
                    loss, components = loss_function(model, batch)
                if not torch.isfinite(loss):
                    raise RuntimeError("non-finite training loss")
                if split == "train":
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                totals["loss"] = totals.get("loss", 0.0) + float(loss.detach())
                for name, value in components.items():
                    totals[name] = totals.get(name, 0.0) + float(value.detach())
                batches += 1
            row[split] = {name: value / batches for name, value in totals.items()}
        scheduler.step()
        history.append(row)
        if row["val"]["loss"] < best_loss:
            best_loss = row["val"]["loss"]
            payload = {
                "candidate": "candidate-11", "stage": args.stage, "epoch": epoch,
                "model_config": model.config.to_dict(), "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(), "scheduler_state_dict": scheduler.state_dict(),
                "training_args": vars(args), "history": history,
            }
            temporary = output.with_suffix(output.suffix + ".tmp")
            torch.save(payload, temporary)
            temporary.replace(output)
        print(json.dumps(row, sort_keys=True))
    return {"candidate": "candidate-11", "stage": args.stage, "bestValLoss": best_loss, "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("a", "b"), required=True)
    parser.add_argument("--data", default="ml/palettebrain/data/palettebrain_c11_v1.npz")
    parser.add_argument("--initialize-from", default="ml/palettebrain/checkpoints/candidate-11-best.pt")
    parser.add_argument("--resume")
    parser.add_argument("--stage-a-eval-report")
    parser.add_argument("--replay-data", action="append", default=[])
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--new-lr", type=float, default=3e-4)
    parser.add_argument("--inherited-lr", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    print(json.dumps(train(args), indent=2))


if __name__ == "__main__":
    main()
