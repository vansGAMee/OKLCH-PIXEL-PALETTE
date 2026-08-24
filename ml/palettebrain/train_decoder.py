"""Train the tiny PaletteBrain decoder on prepared complete-palette examples."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import time

import numpy as np

try:
    import torch
    from torch import Tensor
    import torch.nn.functional as F
    from torch.utils.data import DataLoader
except ImportError as exc:  # pragma: no cover - depends on local ML environment
    raise SystemExit(
        "PyTorch is required for training. Install ml/palettebrain/requirements.txt."
    ) from exc

try:
    from .dataset import PaletteBrainDataset
    from .model import PaletteDecoder, PaletteDecoderConfig
except ImportError:
    from dataset import PaletteBrainDataset
    from model import PaletteDecoder, PaletteDecoderConfig


METRICS_VERSION = 1


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def masked_mean(values: Tensor, mask: Tensor) -> Tensor:
    return (values * mask).sum() / mask.sum().clamp_min(1.0)


def decoder_loss(
    output: Tensor,
    target: Tensor,
    count_mask: Tensor,
    locked_mask: Tensor,
) -> tuple[Tensor, dict[str, Tensor]]:
    active = count_mask.clamp(0.0, 1.0)
    locked = active * locked_mask.clamp(0.0, 1.0)
    free = active * (1.0 - locked_mask.clamp(0.0, 1.0))

    lightness = masked_mean(
        F.smooth_l1_loss(output[..., 0], target[..., 0], reduction="none"), free
    )
    chroma = masked_mean(
        F.smooth_l1_loss(output[..., 1], target[..., 1], reduction="none"), free
    )
    predicted_hue = F.normalize(output[..., 2:4], dim=-1, eps=1e-6)
    target_hue = F.normalize(target[..., 2:4], dim=-1, eps=1e-6)
    hue = masked_mean(1.0 - (predicted_hue * target_hue).sum(dim=-1), free)
    importance = masked_mean(
        F.smooth_l1_loss(output[..., 4], target[..., 4], reduction="none"),
        active,
    )
    locked_lightness = masked_mean(
        F.smooth_l1_loss(output[..., 0], target[..., 0], reduction="none"),
        locked,
    )
    locked_chroma = masked_mean(
        F.smooth_l1_loss(output[..., 1], target[..., 1], reduction="none"),
        locked,
    )
    locked_hue = masked_mean(
        1.0 - (predicted_hue * target_hue).sum(dim=-1), locked
    )

    decoded = torch.stack(
        (
            torch.sigmoid(output[..., 0]),
            torch.sigmoid(output[..., 1]),
            predicted_hue[..., 0],
            predicted_hue[..., 1],
        ),
        dim=-1,
    )
    distances = torch.cdist(decoded, decoded)
    pair_mask = active.unsqueeze(1) * active.unsqueeze(2)
    upper_triangle = torch.triu(
        torch.ones_like(pair_mask), diagonal=1
    )
    pair_mask = pair_mask * upper_triangle
    duplicate_penalty = masked_mean(F.relu(0.12 - distances), pair_mask)

    total = (
        lightness
        + chroma
        + 1.5 * hue
        + 0.25 * importance
        + 0.20 * duplicate_penalty
        + 0.25 * (locked_lightness + locked_chroma + locked_hue)
    )
    return total, {
        "lightness": lightness,
        "chroma": chroma,
        "hue": hue,
        "importance": importance,
        "duplicatePenalty": duplicate_penalty,
        "lockedLightness": locked_lightness,
        "lockedChroma": locked_chroma,
        "lockedHue": locked_hue,
    }


def run_epoch(
    model: PaletteDecoder,
    loader: DataLoader,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    totals: dict[str, float] = {"loss": 0.0}
    batches = 0

    for batch in loader:
        inputs = {
            "text_embedding": batch["text_embedding"].to(device),
            "count_mask": batch["count_mask"].to(device),
            "seed_noise": batch["seed_noise"].to(device),
            "locked_mask": batch["locked_mask"].to(device),
            "locked_colors": batch["locked_colors"].to(device),
        }
        target = batch["target"].to(device)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training):
            output = model(**inputs)
            loss, components = decoder_loss(
                output, target, inputs["count_mask"], inputs["locked_mask"]
            )
        if not torch.isfinite(loss):
            raise RuntimeError("non-finite training loss")
        if training:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

        totals["loss"] += float(loss.detach())
        for name, value in components.items():
            totals[name] = totals.get(name, 0.0) + float(value.detach())
        batches += 1

    if batches == 0:
        raise RuntimeError("dataset split produced zero batches")
    return {name: value / batches for name, value in totals.items()}


def choose_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def train(args: argparse.Namespace) -> dict[str, object]:
    set_seed(args.seed)
    device = choose_device(args.device)
    max_train = 64 if args.smoke else args.max_train_samples
    max_val = 32 if args.smoke else args.max_val_samples
    epochs = 1 if args.smoke else args.epochs
    batch_size = min(args.batch_size, 8) if args.smoke else args.batch_size

    train_dataset = PaletteBrainDataset(
        args.data, "train", max_samples=max_train
    )
    val_dataset = PaletteBrainDataset(args.data, "val", max_samples=max_val)
    if len(train_dataset) == 0 or len(val_dataset) == 0:
        raise RuntimeError("prepared dataset must contain non-empty train and val splits")
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    config = PaletteDecoderConfig(
        d_model=args.d_model,
        heads=args.heads,
        layers=args.layers,
        ff_multiplier=args.ff_multiplier,
        dropout=args.dropout,
    )
    model = PaletteDecoder(config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    best_val_loss = math.inf
    history: list[dict[str, object]] = []
    start = time.perf_counter()

    for epoch in range(1, epochs + 1):
        train_metrics = run_epoch(model, train_loader, device, optimizer)
        with torch.no_grad():
            val_metrics = run_epoch(model, val_loader, device, None)
        record = {
            "epoch": epoch,
            "train": train_metrics,
            "val": val_metrics,
        }
        history.append(record)
        print(json.dumps(record, sort_keys=True))

        checkpoint = {
            "schema_version": 1,
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "model_config": config.to_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "val_loss": val_metrics["loss"],
            "training_data_kind": train_dataset.metadata.get("kind"),
            "training_data_synthesis_version": train_dataset.metadata.get(
                "synthesisVersion"
            ),
            "production_ready": False,
            "smoke": bool(args.smoke),
        }
        torch.save(checkpoint, output_dir / "last.pt")
        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            torch.save(checkpoint, output_dir / "best.pt")

    metrics = {
        "schemaVersion": METRICS_VERSION,
        "status": "smoke_only" if args.smoke else "synthetic_baseline_training",
        "productionReady": False,
        "dataset": str(args.data),
        "datasetKind": train_dataset.metadata.get("kind"),
        "device": str(device),
        "parameterCount": model.count_parameters(),
        "epochs": epochs,
        "trainExamples": len(train_dataset),
        "valExamples": len(val_dataset),
        "bestValLoss": best_val_loss,
        "elapsedSeconds": time.perf_counter() - start,
        "history": history,
        "warning": (
            "Checkpoint was trained on deterministic synthetic targets and is "
            "not evidence of production palette quality."
        ),
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", default="ml/palettebrain/data/palettebrain_synthetic_v1.npz"
    )
    parser.add_argument("--output-dir", default="ml/palettebrain/checkpoints")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--d-model", type=int, default=64)
    parser.add_argument("--heads", type=int, default=4)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--ff-multiplier", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-val-samples", type=int)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    print(json.dumps(train(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
