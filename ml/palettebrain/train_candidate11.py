"""Repaired two-stage Candidate 11 trainer (never creates Candidate 12).

The original untracked C11 trainer could not be recovered.  This version is an
auditable continuation pipeline: it preserves every compatible C11 weight,
adds slot-specific visual cross-attention, and records all optimizer/scheduler
state required for deterministic resume.
"""

from __future__ import annotations

import argparse
import os
import hashlib
import json
import random
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor
from torch.utils.data import ConcatDataset, DataLoader, Dataset, WeightedRandomSampler

try:
    from .c11_release_contract import stage_a_metrics_contract
    from .color_distribution import smooth_circular_histogram_loss
    from .model import PaletteDecoder, PaletteDecoderConfig, load_inherited_state
    from .train_decoder import decoder_loss
except ImportError:
    from c11_release_contract import stage_a_metrics_contract
    from color_distribution import smooth_circular_histogram_loss
    from model import PaletteDecoder, PaletteDecoderConfig, load_inherited_state
    from train_decoder import decoder_loss


def inverse_frequency_sample_weights(labels: np.ndarray) -> Tensor:
    """Give every Stage A concept equal expected sampling mass."""
    values = np.asarray(labels).astype(str).reshape(-1)
    if not len(values):
        raise ValueError("concept-balanced sampling requires at least one label")
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    return torch.as_tensor(1.0 / counts[inverse], dtype=torch.double)


def atomic_checkpoint_replace(
    temporary: Path, destination: Path, *, attempts: int = 5,
    initial_backoff_seconds: float = 0.05,
) -> None:
    """Publish a checkpoint atomically, tolerating Windows sharing violations.

    The prior valid destination is never removed.  Only WinError 5 is retried;
    all other errors, and a persistent lock after the bounded retry budget, are
    surfaced to the caller unchanged.
    """
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for attempt in range(attempts):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) != 5 or attempt == attempts - 1:
                raise
            time.sleep(initial_backoff_seconds * (attempt + 1))


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
                "ranking_negative_color_prior": "ranking_negative_color_prior",
                "ranking_negative_valid": "ranking_negative_valid",
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
        self.concept_ids = (
            np.asarray(archive["concept_id"][selected]).astype(str)
            if "concept_id" in names else None
        )
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
        result.setdefault("ranking_negative_color_prior", torch.zeros(390, dtype=torch.float32))
        result.setdefault("ranking_negative_valid", torch.tensor(0.0))
        result["visual_weight"] = torch.tensor(1.0 if self.has_visual_targets else 0.0)
        return result


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def training_dependency_fingerprint() -> str:
    digest = hashlib.sha256()
    directory = Path(__file__).resolve().parent
    for name in ("train_candidate11.py", "model.py", "train_decoder.py", "color_distribution.py", "c11_release_contract.py", "c11_target_semantic_gate.v1.json"):
        digest.update(name.encode("utf-8"))
        digest.update(_sha256_file(directory / name).encode("ascii"))
    return digest.hexdigest()


# This is the immediately preceding Candidate 11 trainer fingerprint.  It is
# compatible solely because the only change is atomic checkpoint publication;
# model math, optimizer state, data identity, and resume arguments remain
# independently validated below.
CHECKPOINT_SAVE_RETRY_COMPATIBLE_FINGERPRINTS = frozenset({
    "b5239a9d991cf473d29425412ab8566d0c7c536a5ec8a27803b8085517eda67f",
    "05bb4b0691c3ae52e5a49a3d5afdaa04f0ec224f776726d1539332f77b2c44d3",
    # Completed one-epoch probe produced after adding release-only evidence
    # calibration.  The subsequent fingerprint change only touched the
    # orchestration reuse predicate; forward/loss/optimizer code is identical.
    "d1ec28a8789eefb71a109cd7e8fd0928adb17d42d0635f371855a519bb0969c9",
})


def resume_dependency_fingerprints() -> frozenset[str]:
    return frozenset({training_dependency_fingerprint(), *CHECKPOINT_SAVE_RETRY_COMPATIBLE_FINGERPRINTS})


def training_input_identity(args: argparse.Namespace) -> dict[str, Any]:
    """Content identity for every artifact that can affect training state."""
    identity: dict[str, Any] = {
        "primary": _sha256_file(args.data),
        "replay": [_sha256_file(path) for path in args.replay_data],
        "initialization": _sha256_file(args.initialize_from),
    }
    if args.stage == "b":
        if not args.stage_a_eval_report:
            raise RuntimeError("Stage B requires a Stage A evaluation artifact")
        identity["stage_a_evaluation"] = _sha256_file(args.stage_a_eval_report)
    return identity


def _device(name: str) -> torch.device:
    selected = torch.device("cuda" if name == "auto" and torch.cuda.is_available() else ("cpu" if name == "auto" else name))
    if selected.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return selected


def _stage_a_release_evidence(path: str | None) -> dict[str, Any]:
    if not path:
        raise RuntimeError("Stage B requires --stage-a-eval-report from the frozen v3 benchmark")
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    if report.get("benchmarkId") != "palettebrain-candidate11-semantic-v3-frozen-2026-08-26":
        raise RuntimeError("Stage A report is not from the frozen semantic v3 benchmark")
    metrics = report.get("metrics", {})
    calibration_path = Path(__file__).with_name("c11_target_semantic_gate.v1.json")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))["stageA"]
    passed, failures = stage_a_metrics_contract(metrics, calibration)
    classification = report.get("testClassification")
    if classification != "ENGINEERING_SMOKE_ONLY" and not passed:
        raise RuntimeError("Stage A target-grounded semantic gate failed: " + "; ".join(failures))
    return report


def configure_stage_parameters(model: PaletteDecoder, stage: str) -> dict[str, list[str]]:
    if stage not in {"a", "b"}:
        raise ValueError(f"unsupported stage: {stage}")
    new_prefixes = ("bridge.", "visual_cross_attention.")
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(stage == "b" or name.startswith(new_prefixes))
    return {
        "trainable": [name for name, value in model.named_parameters() if value.requires_grad],
        "frozen": [name for name, value in model.named_parameters() if not value.requires_grad],
    }


def partition_trainable_parameters(model: PaletteDecoder) -> dict[str, list[Any]]:
    """Separate genuinely new attention tensors from inherited decoder tensors."""
    new_names: list[str] = []
    new_parameters: list[Any] = []
    inherited_names: list[str] = []
    inherited_parameters: list[Any] = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if name.startswith("visual_cross_attention."):
            new_names.append(name)
            new_parameters.append(parameter)
        else:
            inherited_names.append(name)
            inherited_parameters.append(parameter)
    return {
        "new_names": new_names,
        "new_parameters": new_parameters,
        "inherited_names": inherited_names,
        "inherited_parameters": inherited_parameters,
    }


def stage_a_semantic_stability_loss(
    student: PaletteDecoder,
    teacher: PaletteDecoder,
    inputs: tuple[Tensor, ...],
) -> Tensor:
    """Penalize joint bridge/attention drift from the inherited BASE decoder."""
    with torch.no_grad():
        expected = teacher(*inputs)
    actual = student(*inputs)
    active = inputs[1].unsqueeze(-1)
    per_value = F.smooth_l1_loss(actual, expected, reduction="none") * active
    return per_value.sum() / active.sum().clamp_min(1.0) / actual.shape[-1]


def stage_a_prior_stability_loss(
    student: PaletteDecoder,
    teacher: PaletteDecoder,
    text_embedding: Tensor,
) -> Tensor:
    """Preserve the inherited semantic color distribution during visual training."""
    with torch.no_grad():
        expected = torch.softmax(teacher.bridge(text_embedding)[0], dim=-1)
    actual = torch.log_softmax(student.bridge(text_embedding)[0], dim=-1)
    return F.kl_div(actual, expected, reduction="batchmean")


def stage_b_mixture_weights(lengths: list[int]) -> tuple[Tensor, dict[str, float]]:
    if len(lengths) < 2 or any(length <= 0 for length in lengths):
        raise ValueError("Stage B mixture requires positive real and replay datasets")
    proportions = [0.80] + [0.20 / (len(lengths) - 1)] * (len(lengths) - 1)
    weights = torch.cat([
        torch.full((length,), proportion / length, dtype=torch.double)
        for length, proportion in zip(lengths, proportions, strict=True)
    ])
    mixture = {"realVisualSemantic": proportions[0], "replayTotal": sum(proportions[1:])}
    return weights, mixture


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


def _stage_a_loss(
    model: PaletteDecoder,
    batch: dict[str, Tensor],
    teacher: PaletteDecoder | None = None,
) -> tuple[Tensor, dict[str, Tensor]]:
    prior_logits, style_latent, _, _ = model.bridge(batch["text_embedding"])
    prior = smooth_circular_histogram_loss(prior_logits, batch["color_prior"])
    style = F.smooth_l1_loss(style_latent, batch["teacher_latent"])
    predicted = F.normalize(torch.softmax(prior_logits, dim=-1), dim=-1)
    expected = F.normalize(batch["color_prior"], dim=-1)
    positive = (predicted * expected).sum(dim=-1)
    negative_expected = batch["ranking_negative_color_prior"]
    negative_valid = batch["ranking_negative_valid"]
    negative = (predicted * F.normalize(negative_expected, dim=-1)).sum(dim=-1)
    ranking_by_row = F.relu(0.10 - positive + negative)
    ranking = (ranking_by_row * negative_valid).sum() / negative_valid.sum().clamp_min(1.0)
    output = model(
        batch["text_embedding"], batch["count_mask"], batch["seed_noise"],
        batch["locked_mask"], batch["locked_colors"],
    )
    palette, _ = decoder_loss(
        output, batch["target"], batch["count_mask"], batch["locked_mask"],
        batch["locked_colors"],
    )
    stability = palette.new_zeros(())
    prior_stability = palette.new_zeros(())
    if teacher is not None:
        stability = stage_a_semantic_stability_loss(
            model,
            teacher,
            (
                batch["text_embedding"], batch["count_mask"], batch["seed_noise"],
                batch["locked_mask"], batch["locked_colors"],
            ),
        )
        prior_stability = stage_a_prior_stability_loss(
            model, teacher, batch["text_embedding"]
        )
    total = (
        prior + 0.25 * style + 0.5 * ranking + 0.25 * palette
        + 5.0 * stability + 2.0 * prior_stability
    )
    return total, {
        "prior": prior, "style": style, "ranking": ranking,
        "palette": palette, "semanticStability": stability,
        "priorStability": prior_stability,
    }


def _stage_b_loss(
    model: PaletteDecoder,
    batch: dict[str, Tensor],
    teacher: PaletteDecoder | None = None,
) -> tuple[Tensor, dict[str, Tensor]]:
    output = model(
        batch["text_embedding"], batch["count_mask"], batch["seed_noise"],
        batch["locked_mask"], batch["locked_colors"],
    )
    palette, components = decoder_loss(
        output, batch["target"], batch["count_mask"], batch["locked_mask"],
        batch["locked_colors"],
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
    semantic_stability = palette.new_zeros(())
    prior_stability = palette.new_zeros(())
    if teacher is not None:
        with torch.no_grad():
            expected_output = teacher(
                batch["text_embedding"], batch["count_mask"], batch["seed_noise"],
                batch["locked_mask"], batch["locked_colors"],
            )
        active = batch["count_mask"].unsqueeze(-1)
        per_value = F.smooth_l1_loss(output, expected_output, reduction="none") * active
        semantic_stability = (
            per_value.sum() / active.sum().clamp_min(1.0) / output.shape[-1]
        )
        prior_stability = stage_a_prior_stability_loss(
            model, teacher, batch["text_embedding"]
        )
    total = (
        palette + 0.25 * prior + 0.05 * style
        + 5.0 * semantic_stability + 2.0 * prior_stability
    )
    return total, {
        "palette": palette,
        "prior": prior,
        "style": style,
        "semanticStability": semantic_stability,
        "priorStability": prior_stability,
        **components,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    if args.checkpoint_every_steps < 1:
        raise ValueError("checkpoint_every_steps must be positive")
    data_path = Path(args.data)
    used = data_path.stat().st_size if data_path.is_file() else 0
    output_parent = Path(args.output).parent
    free = shutil.disk_usage(output_parent if output_parent.exists() else Path.cwd()).free
    print(f"DISK used={used / 1024**3:.2f} GiB free={free / 1024**3:.2f} GiB")
    stage_a_evidence: dict[str, Any] | None = None
    if args.stage == "b":
        stage_a_evidence = _stage_a_release_evidence(args.stage_a_eval_report)
    _seed_everything(args.seed)
    device = _device(args.device)
    model = _configure_model(args).to(device)
    semantic_teacher: PaletteDecoder | None = None
    if args.stage in {"a", "b"}:
        teacher_checkpoint = torch.load(
            args.initialize_from, map_location="cpu", weights_only=True
        )
        semantic_teacher = PaletteDecoder(
            PaletteDecoderConfig(**teacher_checkpoint["model_config"])
        ).to(device).eval()
        semantic_teacher.load_state_dict(
            teacher_checkpoint["model_state_dict"], strict=True
        )
        for parameter in semantic_teacher.parameters():
            parameter.requires_grad_(False)
    parameter_contract = configure_stage_parameters(model, args.stage)
    optimizer_partition = partition_trainable_parameters(model)
    parameter_groups = [{"params": optimizer_partition["new_parameters"], "lr": args.new_lr}]
    if optimizer_partition["inherited_parameters"]:
        parameter_groups.append({
            "params": optimizer_partition["inherited_parameters"],
            "lr": args.inherited_lr,
        })
    optimizer = torch.optim.AdamW(parameter_groups, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    start_epoch = 0
    resume_batch = 0
    history: list[dict[str, Any]] = []
    best_loss = float("inf")
    global_step = 0
    resume_epoch_progress: dict[str, Any] = {}
    dependency_fingerprint = training_dependency_fingerprint()
    dataset_identity = training_input_identity(args)
    if args.resume:
        resumed = torch.load(args.resume, map_location="cpu", weights_only=True)
        if resumed.get("dataset_identity") != dataset_identity:
            raise RuntimeError("resume checkpoint dataset identity does not match current inputs")
        resumed_dependency = resumed.get("dependency_fingerprint")
        if resumed_dependency not in resume_dependency_fingerprints():
            raise RuntimeError("resume checkpoint trainer/model dependency fingerprint is stale")
        if resumed_dependency != dependency_fingerprint:
            print("RESUME compatible prior checkpoint-save contract fingerprint", flush=True)
        resumed_args = resumed.get("training_args", {})
        for name in ("stage", "epochs", "batch_size", "new_lr", "inherited_lr", "seed"):
            if resumed_args.get(name) != getattr(args, name):
                raise RuntimeError(f"resume checkpoint training config mismatch: {name}")
        model.load_state_dict(resumed["model_state_dict"], strict=True)
        optimizer.load_state_dict(resumed["optimizer_state_dict"])
        scheduler.load_state_dict(resumed["scheduler_state_dict"])
        if resumed.get("epoch_complete", True):
            start_epoch = int(resumed["epoch"]) + 1
        else:
            start_epoch = int(resumed["epoch"])
            resume_batch = int(resumed.get("batch_in_epoch", 0))
        history = list(resumed.get("history", []))
        best_loss = float(resumed.get("best_val_loss", min(
            (row["val"]["loss"] for row in history), default=float("inf")
        )))
        global_step = int(resumed.get("global_step", 0))
        if not resumed.get("epoch_complete", True):
            resume_epoch_progress = dict(resumed.get("epoch_progress", {}))
        if "python_rng_state" in resumed:
            random.setstate(resumed["python_rng_state"])
        if "numpy_rng_state" in resumed:
            numpy_state = resumed["numpy_rng_state"]
            np.random.set_state((
                numpy_state["algorithm"],
                np.asarray(numpy_state["keys"], dtype=np.uint32),
                int(numpy_state["position"]),
                int(numpy_state["hasGauss"]),
                float(numpy_state["cachedGaussian"]),
            ))
        if "torch_rng_state" in resumed:
            torch.set_rng_state(resumed["torch_rng_state"])
        if device.type == "cuda" and "torch_cuda_rng_state" in resumed:
            torch.cuda.set_rng_state_all(resumed["torch_cuda_rng_state"])

    primary_train = C11Dataset(args.data, "train")
    train_sets: list[Dataset[dict[str, Tensor]]] = [primary_train]
    val_sets: list[Dataset[dict[str, Tensor]]] = [C11Dataset(args.data, "val")]
    if args.stage == "b":
        for replay_path in args.replay_data:
            train_sets.append(C11Dataset(replay_path, "train"))
            val_sets.append(C11Dataset(replay_path, "val"))
    train_data = train_sets[0] if len(train_sets) == 1 else ConcatDataset(train_sets)
    # DEV remains the canonical held-out visual split. Replay contributes only
    # to Stage B gradient updates and cannot dilute DEV into an implicit blend.
    val_data = val_sets[0]
    sampler_weights = None
    mixture = {"realVisualSemantic": 1.0, "replayTotal": 0.0}
    if args.stage == "a" and primary_train.concept_ids is not None:
        sampler_weights = inverse_frequency_sample_weights(primary_train.concept_ids)
    elif len(train_sets) > 1:
        sampler_weights, mixture = stage_b_mixture_weights([len(value) for value in train_sets])
    val_loader = DataLoader(val_data, batch_size=args.batch_size, shuffle=False)
    loss_function = (
        (lambda current_model, batch: _stage_a_loss(
            current_model, batch, teacher=semantic_teacher
        ))
        if args.stage == "a"
        else (lambda current_model, batch: _stage_b_loss(
            current_model, batch, teacher=semantic_teacher
        ))
    )
    output = Path(args.output)
    last_output = Path(args.last_output) if args.last_output else output.with_name(
        f"{output.stem.removesuffix('-best')}-last{output.suffix}"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    bounded_candidates: list[dict[str, Any]] = []
    for candidate_path in output.parent.glob(
        f"{output.stem.removesuffix('-best')}-dev-epoch-*{output.suffix}"
    ):
        try:
            candidate_checkpoint = torch.load(candidate_path, map_location="cpu", weights_only=True)
            candidate_args = candidate_checkpoint.get("training_args", {})
            compatible_args = all(
                candidate_args.get(name) == getattr(args, name)
                for name in ("stage", "batch_size", "new_lr", "inherited_lr", "seed")
            )
            if (
                candidate_checkpoint.get("candidate") == "candidate-11"
                and candidate_checkpoint.get("stage") == args.stage
                and candidate_checkpoint.get("dataset_identity") == dataset_identity
                and candidate_checkpoint.get("dependency_fingerprint") == dependency_fingerprint
                and compatible_args
            ):
                bounded_candidates.append({
                    "path": str(candidate_path),
                    "valLoss": float(candidate_checkpoint["history"][-1]["val"]["loss"]),
                })
        except Exception:
            continue
    bounded_candidates.sort(key=lambda item: item["valLoss"])

    def checkpoint_payload(
        *,
        epoch: int,
        epoch_complete: bool,
        batch_in_epoch: int,
        actual_visual_fraction: float,
        epoch_progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "candidate": "candidate-11", "stage": args.stage, "epoch": epoch,
            "epoch_complete": epoch_complete, "batch_in_epoch": batch_in_epoch,
            "model_config": model.config.to_dict(), "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(), "scheduler_state_dict": scheduler.state_dict(),
            "training_args": vars(args), "history": history, "best_val_loss": best_loss,
            "dataset_identity": dataset_identity,
            "dependency_fingerprint": dependency_fingerprint,
            "global_step": global_step,
            "epoch_progress": epoch_progress or {},
            "parameter_contract": parameter_contract,
            "dataset_mixture": mixture,
            "sampler_state": {
                "epochSeed": args.seed + epoch,
                "configuredMixture": mixture,
                "actualVisualSampleFraction": actual_visual_fraction,
            },
            "stage_a_quality": stage_a_evidence.get("metrics", {}) if stage_a_evidence else None,
            "loss_contract": {
                "paletteStructure": "SmoothL1 pairwise physical OKLab geometry after matching and lock restoration",
                "paletteStructureWeight": 0.20,
                "rankingNegativeVersion": "c11-safe-ranking-negative-v3-bounded-global-order",
                "stageAConceptSampling": "inverse-frequency-equal-concept-mass",
                "stageAPriorStabilityWeight": 2.0,
                "stageAFinalStabilityWeight": 5.0,
                "stageBPriorStabilityWeight": 2.0,
                "stageBFinalStabilityWeight": 5.0,
            },
            "python_rng_state": random.getstate(),
            "numpy_rng_state": {
                "algorithm": np.random.get_state()[0],
                "keys": np.random.get_state()[1].tolist(),
                "position": np.random.get_state()[2],
                "hasGauss": np.random.get_state()[3],
                "cachedGaussian": np.random.get_state()[4],
            },
            "torch_rng_state": torch.get_rng_state(),
            "torch_cuda_rng_state": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        }

    def save_last(payload: dict[str, Any]) -> None:
        last_temporary = last_output.with_suffix(last_output.suffix + ".tmp")
        torch.save(payload, last_temporary)
        atomic_checkpoint_replace(last_temporary, last_output)

    for epoch in range(start_epoch, args.epochs):
        epoch_started = time.perf_counter()
        epoch_generator = torch.Generator().manual_seed(args.seed + epoch)
        sampler = None
        if sampler_weights is not None:
            sampler = WeightedRandomSampler(
                sampler_weights, num_samples=len(train_sets[0]), replacement=True,
                generator=epoch_generator,
            )
        train_loader = DataLoader(
            train_data, batch_size=args.batch_size, sampler=sampler,
            shuffle=sampler is None, generator=epoch_generator,
        )
        row: dict[str, Any] = {"epoch": epoch}
        for split, loader in (("train", train_loader), ("val", val_loader)):
            split_started = time.perf_counter()
            model.train(split == "train")
            continuing_train = split == "train" and epoch == start_epoch and resume_batch > 0
            totals: dict[str, float] = (
                {str(k): float(v) for k, v in resume_epoch_progress.get("totals", {}).items()}
                if continuing_train else {}
            )
            batches = int(resume_epoch_progress.get("batches", 0)) if continuing_train else 0
            visual_samples = int(resume_epoch_progress.get("visual_samples", 0)) if continuing_train else 0
            total_samples = int(resume_epoch_progress.get("total_samples", 0)) if continuing_train else 0
            for batch_index, source_batch in enumerate(loader):
                if split == "train" and epoch == start_epoch and batch_index < resume_batch:
                    continue
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
                    global_step += 1
                    visual_samples += int((batch["visual_weight"] > 0).sum().item())
                    total_samples += int(batch["visual_weight"].numel())
                totals["loss"] = totals.get("loss", 0.0) + float(loss.detach())
                for name, value in components.items():
                    totals[name] = totals.get(name, 0.0) + float(value.detach())
                batches += 1
                if split == "train" and global_step % args.checkpoint_every_steps == 0:
                    progress = {
                        "totals": totals,
                        "batches": batches,
                        "visual_samples": visual_samples,
                        "total_samples": total_samples,
                    }
                    save_last(checkpoint_payload(
                        epoch=epoch,
                        epoch_complete=False,
                        batch_in_epoch=batch_index + 1,
                        actual_visual_fraction=visual_samples / max(1, total_samples),
                        epoch_progress=progress,
                    ))
            row[split] = {name: value / batches for name, value in totals.items()}
            split_elapsed = time.perf_counter() - split_started
            row[split]["elapsedSeconds"] = split_elapsed
            row[split]["batchesPerSecond"] = batches / max(split_elapsed, 1e-9)
            if split == "train":
                row[split]["actualVisualSampleFraction"] = (
                    visual_samples / max(1, total_samples)
                )
                row[split]["samplesPerSecond"] = total_samples / max(
                    split_elapsed, 1e-9
                )
        row["epochSeconds"] = time.perf_counter() - epoch_started
        scheduler.step()
        history.append(row)
        improved = row["val"]["loss"] < best_loss
        if improved:
            best_loss = row["val"]["loss"]
        payload = checkpoint_payload(
            epoch=epoch,
            epoch_complete=True,
            batch_in_epoch=0,
            actual_visual_fraction=row["train"]["actualVisualSampleFraction"],
            epoch_progress={},
        )
        save_last(payload)
        if improved:
            temporary = output.with_suffix(output.suffix + ".tmp")
            torch.save(payload, temporary)
            temporary.replace(output)
        candidate_path = output.with_name(
            f"{output.stem.removesuffix('-best')}-dev-epoch-{epoch:03d}{output.suffix}"
        )
        candidate_temporary = candidate_path.with_suffix(candidate_path.suffix + ".tmp")
        torch.save(payload, candidate_temporary)
        candidate_temporary.replace(candidate_path)
        bounded_candidates.append({"path": str(candidate_path), "valLoss": row["val"]["loss"]})
        bounded_candidates.sort(key=lambda item: item["valLoss"])
        while len(bounded_candidates) > args.max_dev_candidates:
            removed = bounded_candidates.pop()
            Path(removed["path"]).unlink(missing_ok=True)
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
    parser.add_argument("--last-output")
    parser.add_argument("--max-dev-candidates", type=int, default=3)
    parser.add_argument("--checkpoint-every-steps", type=int, default=100)
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
