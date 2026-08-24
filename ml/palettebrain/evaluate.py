"""Evaluate a PaletteBrain checkpoint and validate benchmark coverage."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

import numpy as np


BENCHMARK_SCHEMA_VERSION = 1


def summarize_benchmark(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != BENCHMARK_SCHEMA_VERSION:
        raise ValueError("unsupported benchmark schemaVersion")
    prompts = payload.get("prompts")
    if not isinstance(prompts, list) or len(prompts) < 100:
        raise ValueError("benchmark must contain at least 100 prompts")

    ids: set[str] = set()
    languages: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    counts: Counter[int] = Counter()
    locked_cases = 0
    for item in prompts:
        prompt_id = str(item.get("id", ""))
        if not prompt_id or prompt_id in ids:
            raise ValueError(f"missing or duplicate benchmark id: {prompt_id!r}")
        ids.add(prompt_id)
        prompt = item.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"benchmark item {prompt_id} has an empty prompt")
        language = str(item.get("language"))
        category = str(item.get("category"))
        count = int(item.get("count", 0))
        if language not in {"en", "ru"}:
            raise ValueError(f"benchmark item {prompt_id} has invalid language")
        if count < 2 or count > 9:
            raise ValueError(f"benchmark item {prompt_id} has invalid count")
        locked_indices = item.get("lockedIndices", [])
        if not isinstance(locked_indices, list):
            raise ValueError(f"benchmark item {prompt_id} has invalid lockedIndices")
        if len(set(locked_indices)) != len(locked_indices):
            raise ValueError(f"benchmark item {prompt_id} repeats a locked index")
        if any(not isinstance(index, int) or index < 0 or index >= count for index in locked_indices):
            raise ValueError(f"benchmark item {prompt_id} locks an inactive slot")
        if len(locked_indices) >= count:
            raise ValueError(f"benchmark item {prompt_id} must leave a free slot")

        languages[language] += 1
        categories[category] += 1
        counts[count] += 1
        locked_cases += int(bool(locked_indices))

    missing_counts = sorted(set(range(2, 10)).difference(counts))
    if missing_counts:
        raise ValueError(f"benchmark is missing counts: {missing_counts}")
    if not languages["en"] or not languages["ru"]:
        raise ValueError("benchmark must include both English and Russian")
    if locked_cases == 0:
        raise ValueError("benchmark must include locked-completion cases")

    return {
        "schemaVersion": payload["schemaVersion"],
        "benchmarkVersion": payload.get("benchmarkVersion"),
        "promptCount": len(prompts),
        "languages": dict(sorted(languages.items())),
        "categories": dict(sorted(categories.items())),
        "counts": {str(key): value for key, value in sorted(counts.items())},
        "lockedCases": locked_cases,
        "hasHumanRatings": bool(payload.get("hasHumanRatings", False)),
        "productionQualityClaim": False,
    }


def _masked_mean(values: np.ndarray, mask: np.ndarray) -> float | None:
    selected = values[mask]
    return float(selected.mean()) if selected.size else None


def _duplicate_rate(
    lightness: np.ndarray,
    relative_chroma: np.ndarray,
    hue_sin: np.ndarray,
    hue_cos: np.ndarray,
    active: np.ndarray,
    threshold: float = 0.12,
) -> float:
    duplicates = 0
    pairs = 0
    for batch_index in range(lightness.shape[0]):
        indices = np.flatnonzero(active[batch_index])
        features = np.stack(
            (
                lightness[batch_index, indices],
                relative_chroma[batch_index, indices],
                hue_sin[batch_index, indices],
                hue_cos[batch_index, indices],
            ),
            axis=-1,
        )
        for left in range(len(indices)):
            for right in range(left + 1, len(indices)):
                pairs += 1
                duplicates += int(
                    float(np.linalg.norm(features[left] - features[right])) < threshold
                )
    return float(duplicates / pairs) if pairs else 0.0


def evaluate_checkpoint(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import torch
        from torch.utils.data import DataLoader
    except ImportError as exc:  # pragma: no cover - depends on ML environment
        raise SystemExit(
            "PyTorch is required for checkpoint evaluation. Install requirements.txt."
        ) from exc

    try:
        from .dataset import (
            CHROMA_HEADROOM,
            LIGHTNESS_MIN,
            LIGHTNESS_RANGE,
            PaletteBrainDataset,
            is_in_srgb_gamut,
            max_srgb_chroma_at,
        )
        from .model import PaletteDecoder, PaletteDecoderConfig
    except ImportError:
        from dataset import (
            CHROMA_HEADROOM,
            LIGHTNESS_MIN,
            LIGHTNESS_RANGE,
            PaletteBrainDataset,
            is_in_srgb_gamut,
            max_srgb_chroma_at,
        )
        from model import PaletteDecoder, PaletteDecoderConfig

    device = torch.device(args.device)
    dataset = PaletteBrainDataset(
        args.data, args.split, max_samples=args.max_samples
    )
    if len(dataset) == 0:
        raise RuntimeError("selected dataset split is empty")
    loader = DataLoader(
        dataset, batch_size=args.batch_size, shuffle=False, num_workers=0
    )
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=True)
    config = PaletteDecoderConfig(**checkpoint["model_config"])
    model = PaletteDecoder(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()

    outputs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    count_masks: list[np.ndarray] = []
    locked_masks: list[np.ndarray] = []
    locked_colors: list[np.ndarray] = []
    with torch.no_grad():
        for batch in loader:
            inputs = {
                "text_embedding": batch["text_embedding"].to(device),
                "count_mask": batch["count_mask"].to(device),
                "seed_noise": batch["seed_noise"].to(device),
                "locked_mask": batch["locked_mask"].to(device),
                "locked_colors": batch["locked_colors"].to(device),
            }
            outputs.append(model(**inputs).cpu().numpy())
            targets.append(batch["target"].numpy())
            count_masks.append(batch["count_mask"].numpy())
            locked_masks.append(batch["locked_mask"].numpy())
            locked_colors.append(batch["locked_colors"].numpy())

    output = np.concatenate(outputs)
    target = np.concatenate(targets)
    count_mask = np.concatenate(count_masks)
    locked_mask = np.concatenate(locked_masks)
    locked_color = np.concatenate(locked_colors)
    active = count_mask > 0.5
    locked = active & (locked_mask > 0.5)
    free = active & ~locked

    predicted_l = LIGHTNESS_MIN + LIGHTNESS_RANGE / (
        1.0 + np.exp(-output[..., 0])
    )
    target_l = LIGHTNESS_MIN + LIGHTNESS_RANGE / (
        1.0 + np.exp(-target[..., 0])
    )
    predicted_relative_c = 1.0 / (1.0 + np.exp(-output[..., 1]))
    target_relative_c = 1.0 / (1.0 + np.exp(-target[..., 1]))
    hue_norm = np.maximum(
        np.linalg.norm(output[..., 2:4], axis=-1, keepdims=True), 1e-8
    )
    target_hue_norm = np.maximum(
        np.linalg.norm(target[..., 2:4], axis=-1, keepdims=True), 1e-8
    )
    predicted_hue = output[..., 2:4] / hue_norm
    target_hue = target[..., 2:4] / target_hue_norm
    predicted_hue_degrees = (
        np.degrees(np.arctan2(predicted_hue[..., 0], predicted_hue[..., 1]))
        % 360.0
    )
    target_hue_degrees = (
        np.degrees(np.arctan2(target_hue[..., 0], target_hue[..., 1])) % 360.0
    )
    predicted_max_c = np.empty_like(predicted_l)
    target_max_c = np.empty_like(target_l)
    for row in range(predicted_l.shape[0]):
        for slot in range(predicted_l.shape[1]):
            predicted_max_c[row, slot] = max_srgb_chroma_at(
                float(predicted_l[row, slot]),
                float(predicted_hue_degrees[row, slot]),
            )
            target_max_c[row, slot] = max_srgb_chroma_at(
                float(target_l[row, slot]), float(target_hue_degrees[row, slot])
            )
    predicted_c = predicted_relative_c * predicted_max_c * CHROMA_HEADROOM
    target_c = target_relative_c * target_max_c * CHROMA_HEADROOM
    hue_dot = np.clip((predicted_hue * target_hue).sum(axis=-1), -1.0, 1.0)
    hue_error = np.degrees(np.arccos(hue_dot))

    predicted_active = np.abs(output).sum(axis=-1) > 1e-8
    expected_counts = active.sum(axis=1)
    predicted_counts = predicted_active.sum(axis=1)
    gamut_ok = np.zeros_like(active)
    for row, slot in zip(*np.nonzero(active)):
        gamut_ok[row, slot] = is_in_srgb_gamut(
            float(predicted_l[row, slot]),
            float(predicted_c[row, slot]),
            float(predicted_hue_degrees[row, slot]),
        )
    inactive = ~active
    locked_hue_norm = np.maximum(
        np.linalg.norm(locked_color[..., 2:4], axis=-1, keepdims=True), 1e-8
    )
    locked_hue = locked_color[..., 2:4] / locked_hue_norm
    locked_hue_dot = np.clip(
        (predicted_hue * locked_hue).sum(axis=-1), -1.0, 1.0
    )
    locked_hue_error = np.degrees(np.arccos(locked_hue_dot))
    lock_l_error = np.abs(predicted_l - locked_color[..., 0])
    lock_c_error = np.abs(predicted_c - locked_color[..., 1])
    lock_close = (
        (lock_l_error <= 0.01)
        & (lock_c_error <= 0.01)
        & (locked_hue_error <= 5.0)
    )

    metrics: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "synthetic_baseline_evaluation",
        "productionReady": False,
        "split": args.split,
        "examples": int(output.shape[0]),
        "exactCountRate": float(np.mean(predicted_counts == expected_counts)),
        "inactiveOutputAbsMax": float(np.abs(output[inactive]).max())
        if inactive.any()
        else 0.0,
        "finiteActiveRate": float(np.isfinite(output[active]).all(axis=-1).mean()),
        "duplicatePairRate": _duplicate_rate(
            predicted_l,
            predicted_relative_c,
            predicted_hue[..., 0],
            predicted_hue[..., 1],
            active,
        ),
        "srgbGamutPassRate": _masked_mean(gamut_ok, active),
        "freeLightnessMae": _masked_mean(np.abs(predicted_l - target_l), free),
        "freeChromaMae": _masked_mean(np.abs(predicted_c - target_c), free),
        "freeHueMaeDegrees": _masked_mean(hue_error, free),
        "activeImportanceMae": _masked_mean(
            np.abs(output[..., 4] - target[..., 4]), active
        ),
        "lockedSlots": int(locked.sum()),
        "modelLockedLightnessMae": _masked_mean(lock_l_error, locked),
        "modelLockedChromaMae": _masked_mean(lock_c_error, locked),
        "modelLockedHueMaeDegrees": _masked_mean(locked_hue_error, locked),
        "modelLockedCloseRate": _masked_mean(lock_close, locked),
        "runtimeLockGuardRequired": True,
        "checkpointTrainingKind": checkpoint.get("training_data_kind"),
        "checkpointSmoke": bool(checkpoint.get("smoke", False)),
        "warning": (
            "sRGB gamut uses the same Culori-derived conversion and 20-step "
            "chroma search as the runtime. Model lock metrics measure learned "
            "reconstruction; the runtime restores physical locked colors exactly. "
            "Quality metrics compare against synthetic targets, not preference."
        ),
    }
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        default="ml/palettebrain/benchmark_prompts.v1.json",
    )
    parser.add_argument("--validate-benchmark-only", action="store_true")
    parser.add_argument(
        "--data", default="ml/palettebrain/data/palettebrain_synthetic_v1.npz"
    )
    parser.add_argument(
        "--checkpoint", default="ml/palettebrain/checkpoints/best.pt"
    )
    parser.add_argument("--split", choices=("train", "val", "test"), default="test")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output")
    args = parser.parse_args()

    benchmark = summarize_benchmark(args.benchmark)
    result: dict[str, Any] = {"benchmarkCoverage": benchmark}
    if not args.validate_benchmark_only:
        result["modelMetrics"] = evaluate_checkpoint(args)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
