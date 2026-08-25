"""Train the tiny PaletteBrain decoder on prepared complete-palette examples."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re
import time

import numpy as np

try:
    import torch
    from torch import Tensor
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, WeightedRandomSampler
except ImportError as exc:  # pragma: no cover - depends on local ML environment
    raise SystemExit(
        "PyTorch is required for training. Install ml/palettebrain/requirements.txt."
    ) from exc

try:
    from .color_math import hue_relevance_from_oklab, representation_to_oklab
    from .dataset import PaletteBrainDataset
    from .matching import match_free_targets
    from .model import PaletteDecoder, PaletteDecoderConfig
except ImportError:
    from color_math import (  # type: ignore[no-redef]
        hue_relevance_from_oklab,
        representation_to_oklab,
    )
    from dataset import PaletteBrainDataset
    from matching import match_free_targets
    from model import PaletteDecoder, PaletteDecoderConfig


METRICS_VERSION = 1
DUPLICATE_OKLAB_THRESHOLD = 0.025
DUPLICATE_LOSS_WEIGHT = 0.10
IMPORTANCE_LOSS_WEIGHT = 0.0


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_torch_save(payload: dict[str, object], path: Path) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        torch.save(payload, temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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

    predicted_oklab = representation_to_oklab(output)
    with torch.no_grad():
        target_oklab = representation_to_oklab(target)
        matched_target, matched_target_oklab = match_free_targets(
            target,
            predicted_oklab,
            target_oklab,
            count_mask,
            locked_mask,
        )

    lightness = masked_mean(
        F.smooth_l1_loss(
            output[..., 0], matched_target[..., 0], reduction="none"
        ),
        free,
    )
    chroma = masked_mean(
        F.smooth_l1_loss(
            output[..., 1], matched_target[..., 1], reduction="none"
        ),
        free,
    )
    predicted_hue = F.normalize(output[..., 2:4], dim=-1, eps=1e-6)
    target_hue = F.normalize(matched_target[..., 2:4], dim=-1, eps=1e-6)
    hue_error = 1.0 - (predicted_hue * target_hue).sum(dim=-1)
    hue_relevance = hue_relevance_from_oklab(matched_target_oklab)
    hue = masked_mean(hue_error * hue_relevance, free)

    # Channel five remains in the browser/ONNX contract, but palette order is
    # not trustworthy importance supervision. Candidate training gives it no
    # objective or metric credit unless real labels are introduced explicitly.
    importance = output.new_zeros(())
    importance_weight = output.new_tensor(IMPORTANCE_LOSS_WEIGHT)

    locked_lightness = masked_mean(
        F.smooth_l1_loss(
            output[..., 0], matched_target[..., 0], reduction="none"
        ),
        locked,
    )
    locked_chroma = masked_mean(
        F.smooth_l1_loss(
            output[..., 1], matched_target[..., 1], reduction="none"
        ),
        locked,
    )
    locked_hue = masked_mean(
        hue_error * hue_relevance,
        locked,
    )

    distances = torch.cdist(predicted_oklab, predicted_oklab)
    pair_mask = free.unsqueeze(1) * free.unsqueeze(2)
    upper_triangle = torch.triu(
        torch.ones_like(pair_mask), diagonal=1
    )
    pair_mask = pair_mask * upper_triangle
    duplicate_penalty = masked_mean(
        F.relu(DUPLICATE_OKLAB_THRESHOLD - distances), pair_mask
    )

    total = (
        lightness
        + chroma
        + 1.5 * hue
        + IMPORTANCE_LOSS_WEIGHT * importance
        + DUPLICATE_LOSS_WEIGHT * duplicate_penalty
        + 0.25 * (locked_lightness + locked_chroma + locked_hue)
    )
    return total, {
        "lightness": lightness,
        "chroma": chroma,
        "hue": hue,
        "importance": importance,
        "importanceWeight": importance_weight,
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
    device = (
        torch.device(requested)
        if requested != "auto"
        else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return device


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
    sampler_generator = torch.Generator().manual_seed(args.seed)
    sampler = WeightedRandomSampler(
        torch.as_tensor(train_dataset.sampling_weights, dtype=torch.double),
        num_samples=len(train_dataset),
        replacement=True,
        generator=sampler_generator,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        sampler=sampler,
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
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.candidate_id):
        raise ValueError("candidate-id may contain only letters, digits, '_' and '-'")
    artifact_stem = args.candidate_id
    last_path = output_dir / f"{artifact_stem}-last.pt"
    best_path = output_dir / f"{artifact_stem}-best.pt"
    config_path = output_dir / f"{artifact_stem}-config.json"
    metrics_path = output_dir / f"{artifact_stem}-metrics.json"
    data_path = Path(args.data)
    dataset_sha256 = sha256_file(data_path)
    loss_config = {
        "matching": "detached_physical_oklab_hungarian",
        "lightnessWeight": 1.0,
        "relativeChromaWeight": 1.0,
        "circularHueWeight": 1.5,
        "neutralHueDisabledBelowChroma": 0.02,
        "neutralHueFullAboveChroma": 0.05,
        "duplicateOklabThreshold": DUPLICATE_OKLAB_THRESHOLD,
        "duplicateWeight": DUPLICATE_LOSS_WEIGHT,
        "lockedAuxiliaryWeight": 0.25,
        "importanceWeight": IMPORTANCE_LOSS_WEIGHT,
    }
    training_config = {
        "schemaVersion": 1,
        "candidateId": artifact_stem,
        "dataset": str(data_path.as_posix()),
        "datasetSha256": dataset_sha256,
        "datasetVersion": train_dataset.metadata.get("datasetVersion"),
        "encoderRevision": train_dataset.metadata.get("encoderRevision"),
        "modelConfig": config.to_dict(),
        "lossConfig": loss_config,
        "trainingSeed": args.seed,
        "batchSize": batch_size,
        "learningRate": args.learning_rate,
        "weightDecay": args.weight_decay,
        "maximumEpochs": epochs,
        "earlyStoppingPatience": args.patience,
        "earlyStoppingMinimumDelta": args.min_delta,
        "weightedSampling": True,
        "torchVersion": torch.__version__,
    }
    rendered_config = json.dumps(training_config, indent=2, sort_keys=True)
    config_path.write_text(rendered_config + "\n", encoding="utf-8")
    config_hash = hashlib.sha256(rendered_config.encode("utf-8")).hexdigest()
    best_val_loss = math.inf
    best_epoch = 0
    stale_epochs = 0
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
            "dataset_version": train_dataset.metadata.get("datasetVersion"),
            "dataset_sha256": dataset_sha256,
            "dataset_content_hash": train_dataset.metadata.get("contentHash"),
            "encoder_revision": train_dataset.metadata.get("encoderRevision"),
            "encoder_artifact_sha256": train_dataset.metadata.get(
                "encoderArtifactSha256"
            ),
            "training_seed": args.seed,
            "training_config_hash": config_hash,
            "loss_config": loss_config,
            "candidate_id": artifact_stem,
            "production_ready": False,
            "smoke": bool(args.smoke),
        }
        atomic_torch_save(checkpoint, last_path)
        if val_metrics["loss"] < best_val_loss - args.min_delta:
            best_val_loss = val_metrics["loss"]
            best_epoch = epoch
            stale_epochs = 0
            atomic_torch_save(checkpoint, best_path)
        else:
            stale_epochs += 1
        if not args.smoke and stale_epochs >= args.patience:
            break

    elapsed_seconds = time.perf_counter() - start
    metrics = {
        "schemaVersion": METRICS_VERSION,
        "status": "smoke_only" if args.smoke else "candidate_training_complete",
        "productionReady": False,
        "candidateId": artifact_stem,
        "dataset": str(args.data),
        "datasetKind": train_dataset.metadata.get("kind"),
        "datasetVersion": train_dataset.metadata.get("datasetVersion"),
        "datasetSha256": dataset_sha256,
        "datasetContentHash": train_dataset.metadata.get("contentHash"),
        "trainingConfigHash": config_hash,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "torchVersion": torch.__version__,
        "parameterCount": model.count_parameters(),
        "maximumEpochs": epochs,
        "epochsCompleted": len(history),
        "bestEpoch": best_epoch,
        "earlyStopped": len(history) < epochs,
        "trainExamples": len(train_dataset),
        "valExamples": len(val_dataset),
        "bestValLoss": best_val_loss,
        "elapsedSeconds": elapsed_seconds,
        "bestCheckpoint": str(best_path.as_posix()),
        "bestCheckpointSha256": sha256_file(best_path),
        "lastCheckpoint": str(last_path.as_posix()),
        "effectiveSamplingContribution": train_dataset.metadata.get(
            "effectiveSamplingContribution"
        ),
        "lossConfig": loss_config,
        "history": history,
        "warning": (
            "Training completion is not a release decision. Frozen semantic, "
            "holdout, ONNX, and browser gates must still pass."
        ),
    }
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", default="ml/palettebrain/data/palettebrain_synthetic_v1.npz"
    )
    parser.add_argument("--output-dir", default="ml/palettebrain/checkpoints")
    parser.add_argument("--candidate-id", default="candidate-1")
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
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--min-delta", type=float, default=1e-4)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    print(json.dumps(train(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
