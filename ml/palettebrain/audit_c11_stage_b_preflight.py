"""One-batch real-artifact preflight required before Candidate 11 Stage B."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import torch

try:
    from .train_candidate11 import (
        C11Dataset,
        _configure_model,
        _stage_b_loss,
        atomic_checkpoint_replace,
        configure_stage_parameters,
        partition_trainable_parameters,
        stage_b_mixture_weights,
    )
except ImportError:
    from train_candidate11 import (
        C11Dataset,
        _configure_model,
        _stage_b_loss,
        atomic_checkpoint_replace,
        configure_stage_parameters,
        partition_trainable_parameters,
        stage_b_mixture_weights,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    checkpoint_path = Path(args.checkpoint)
    evaluation_path = Path(args.stage_a_evaluation)
    primary_path = Path(args.data)
    replay_path = Path(args.replay_data)
    checkpoint_sha = sha256_file(checkpoint_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    if checkpoint.get("candidate") != "candidate-11" or checkpoint.get("stage") != "a":
        failures.append("initialization is not the selected Candidate 11 Stage A checkpoint")
    if evaluation.get("sources", {}).get("checkpointSha256") != checkpoint_sha:
        failures.append("Stage A evaluation does not identify the initialization checkpoint")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    model = _configure_model(argparse.Namespace(initialize_from=str(checkpoint_path))).to(device)
    teacher = copy.deepcopy(model).eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    parameter_contract = configure_stage_parameters(model, "b")
    partition = partition_trainable_parameters(model)
    all_names = [name for name, _ in model.named_parameters()]
    if parameter_contract["frozen"]:
        failures.append(f"Stage B unexpectedly froze {len(parameter_contract['frozen'])} parameters")
    if sorted(parameter_contract["trainable"]) != sorted(all_names):
        failures.append("Stage B trainable parameter set is incomplete")
    if not partition["new_names"] or not partition["inherited_names"]:
        failures.append("Stage B optimizer partition is missing a required group")

    optimizer = torch.optim.AdamW([
        {"params": partition["new_parameters"], "lr": args.new_lr},
        {"params": partition["inherited_parameters"], "lr": args.inherited_lr},
    ])
    learning_rates = [float(group["lr"]) for group in optimizer.param_groups]
    if learning_rates != [args.new_lr, args.inherited_lr]:
        failures.append(f"unexpected Stage B learning-rate groups: {learning_rates}")

    primary = C11Dataset(primary_path, "train")
    replay = C11Dataset(replay_path, "train")
    mixture_weights, mixture = stage_b_mixture_weights([len(primary), len(replay)])
    if mixture != {"realVisualSemantic": 0.8, "replayTotal": 0.2}:
        failures.append(f"unexpected Stage B mixture: {mixture}")
    if len(mixture_weights) != len(primary) + len(replay):
        failures.append("Stage B mixture weights do not cover both datasets")

    def pair(dataset: C11Dataset) -> dict[str, torch.Tensor]:
        rows = [dataset[index] for index in range(min(2, len(dataset)))]
        return {name: torch.stack([row[name] for row in rows]) for name in rows[0]}

    primary_batch = pair(primary)
    replay_batch = pair(replay)
    batch = {
        name: torch.cat([primary_batch[name], replay_batch[name]], dim=0).to(device)
        for name in primary_batch
    }

    model.eval()
    with torch.no_grad():
        shared = {name: value[:1].expand(2, *value.shape[1:]).clone() for name, value in batch.items()}
        shared["text_embedding"] = batch["text_embedding"][:2]
        conditioned = model(
            shared["text_embedding"], shared["count_mask"], shared["seed_noise"],
            shared["locked_mask"], shared["locked_colors"],
        )
        prompt_conditioning_delta = float((conditioned[0] - conditioned[1]).abs().mean())
    if prompt_conditioning_delta <= 1e-5:
        failures.append(f"prompt conditioning delta is too small: {prompt_conditioning_delta}")

    batch_started = time.perf_counter()
    model.train()
    optimizer.zero_grad(set_to_none=True)
    loss, components = _stage_b_loss(model, batch, teacher=teacher)
    if not torch.isfinite(loss):
        failures.append("Stage B preflight loss is non-finite")
    else:
        loss.backward()
    batch_seconds = time.perf_counter() - batch_started

    gradients: dict[str, float] = {}
    missing_gradients: list[str] = []
    for name, parameter in model.named_parameters():
        if parameter.grad is None:
            missing_gradients.append(name)
        else:
            gradients[name] = float(parameter.grad.detach().norm())
    new_gradient_norm = sum(gradients.get(name, 0.0) for name in partition["new_names"])
    inherited_gradient_norm = sum(
        gradients.get(name, 0.0) for name in partition["inherited_names"]
    )
    if missing_gradients:
        failures.append(f"trainable parameters without gradients: {missing_gradients}")
    if new_gradient_norm <= 0.0 or inherited_gradient_norm <= 0.0:
        failures.append("one or more Stage B optimizer groups received no gradient")

    save_resume_pass = False
    with tempfile.TemporaryDirectory(prefix="c11-stage-b-preflight-", dir=checkpoint_path.parent) as directory:
        directory_path = Path(directory)
        final = directory_path / "resume.pt"
        temporary = final.with_suffix(".pt.tmp")
        torch.save({
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "stage": "b",
            "sourceCheckpointSha256": checkpoint_sha,
        }, temporary)
        atomic_checkpoint_replace(temporary, final)
        reloaded = torch.load(final, map_location="cpu", weights_only=True)
        save_resume_pass = (
            reloaded.get("stage") == "b"
            and reloaded.get("sourceCheckpointSha256") == checkpoint_sha
            and set(reloaded.get("model_state_dict", {})) == set(model.state_dict())
            and bool(reloaded.get("optimizer_state_dict", {}).get("param_groups"))
        )
    if not save_resume_pass:
        failures.append("atomic checkpoint save/reload contract failed")

    elapsed = time.perf_counter() - started
    report = {
        "schemaVersion": 1,
        "testClassification": "REAL_STAGE_B_ONE_BATCH_PREFLIGHT",
        "pass": not failures,
        "failures": failures,
        "sources": {
            "stageACheckpoint": str(checkpoint_path.as_posix()),
            "stageACheckpointSha256": checkpoint_sha,
            "stageAEvaluation": str(evaluation_path.as_posix()),
            "stageAEvaluationSha256": sha256_file(evaluation_path),
            "dataset": str(primary_path.as_posix()),
            "datasetSha256": sha256_file(primary_path),
            "replayDataset": str(replay_path.as_posix()),
            "replayDatasetSha256": sha256_file(replay_path),
        },
        "parameterContract": {
            "trainableCount": len(parameter_contract["trainable"]),
            "frozenCount": len(parameter_contract["frozen"]),
            "newGroupCount": len(partition["new_names"]),
            "inheritedGroupCount": len(partition["inherited_names"]),
            "learningRates": learning_rates,
        },
        "datasetMixture": mixture,
        "loss": float(loss.detach()) if torch.isfinite(loss) else None,
        "lossComponents": {name: float(value.detach()) for name, value in components.items()},
        "newGradientNorm": new_gradient_norm,
        "inheritedGradientNorm": inherited_gradient_norm,
        "missingGradientCount": len(missing_gradients),
        "promptConditioningDelta": prompt_conditioning_delta,
        "checkpointSaveReloadPass": save_resume_pass,
        "batchSamples": int(batch["text_embedding"].shape[0]),
        "batchSeconds": batch_seconds,
        "batchSamplesPerSecond": float(batch["text_embedding"].shape[0]) / batch_seconds,
        "elapsedSeconds": elapsed,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(output.suffix + ".tmp")
    temporary_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    atomic_checkpoint_replace(temporary_output, output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--stage-a-evaluation", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--replay-data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--new-lr", type=float, default=1e-4)
    parser.add_argument("--inherited-lr", type=float, default=2e-5)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
