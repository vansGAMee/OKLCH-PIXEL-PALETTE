"""Read-only component trace for the Candidate 11 Stage-A semantic path.

The frozen benchmark is used only to diagnose already-trained checkpoints.  No
prompts, answers, or derived values are written to a training artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

try:
    from .color_math import representation_to_oklab_numpy
    from .evaluate_semantic_v3 import decode_embeddings, load_static_evaluation_context
    from .inspect_semantics import _family_distance
    from .model import PaletteDecoder, PaletteDecoderConfig, load_inherited_state
except ImportError:
    from color_math import representation_to_oklab_numpy
    from evaluate_semantic_v3 import decode_embeddings, load_static_evaluation_context
    from inspect_semantics import _family_distance
    from model import PaletteDecoder, PaletteDecoderConfig, load_inherited_state


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_checkpoint(path: Path, device: torch.device) -> PaletteDecoder:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    model = PaletteDecoder(PaletteDecoderConfig(**checkpoint["model_config"]))
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    return model.to(device).eval()


def recreate_pretraining_c11(base: Path, device: torch.device, seed: int) -> PaletteDecoder:
    """Recreate the untrained C11 adapter exactly; BASE weights stay untouched."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    checkpoint = torch.load(base, map_location="cpu", weights_only=True)
    values = dict(checkpoint["model_config"])
    values.setdefault("histogram_bins", 390)
    values.setdefault("visual_latent_dim", 128)
    values["visual_conditioning"] = "slot_cross_attention"
    values["auxiliary_conditioning_scale"] = 0.35
    model = PaletteDecoder(PaletteDecoderConfig(**values))
    load_inherited_state(
        model, checkpoint["model_state_dict"],
        allowed_missing_prefixes=("visual_cross_attention.",),
        allowed_unexpected_prefixes=(),
    )
    return model.to(device).eval()


def forward_components(model: PaletteDecoder, embeddings: torch.Tensor) -> dict[str, torch.Tensor]:
    """Mirror the real decoder and expose its bridge/cross-attention boundary."""
    count = 5
    batch = embeddings.shape[0]
    active = torch.zeros(batch, 9, device=embeddings.device)
    active[:, :count] = 1.0
    seed = torch.zeros(batch, 9, 4, device=embeddings.device)
    locks = torch.zeros(batch, 9, device=embeddings.device)
    locked_colors = torch.zeros(batch, 9, 4, device=embeddings.device)
    slots = model.query_slots.unsqueeze(0).expand(batch, -1, -1)
    text = model.text_projection(embeddings).unsqueeze(1)
    prior_logits, style_latent, color_tokens, style_token = model.bridge(embeddings)
    if model.visual_cross_attention is None:
        cross = torch.zeros_like(slots)
        attention = None
    else:
        cross, attention = model.visual_cross_attention(slots, color_tokens)
        cross = cross - cross.mean(dim=1, keepdim=True)
    bridge_context = color_tokens.mean(dim=1, keepdim=True) + cross + style_token
    auxiliary = (
        model.count_projection(active).unsqueeze(1) * model.config.auxiliary_conditioning_scale
        + model.seed_projection(seed) * model.config.auxiliary_conditioning_scale
        + model.lock_projection(torch.cat((locked_colors, locks.unsqueeze(-1)), dim=-1))
    )
    hidden = (slots + text + bridge_context + auxiliary) * active.unsqueeze(-1)
    for block in model.blocks:
        hidden = block(hidden, active)
    raw = model.output_head(model.output_norm(hidden))
    hue = torch.nn.functional.normalize(raw[..., 2:4], dim=-1, eps=1e-6)
    palette = torch.cat((raw[..., :2], hue, torch.sigmoid(raw[..., 4:5])), dim=-1)
    return {
        "prior_logits": prior_logits,
        "style_latent": style_latent,
        "color_tokens": color_tokens,
        "style_token": style_token,
        "cross": cross,
        "bridge_context": bridge_context,
        "text": text,
        "output": palette * active.unsqueeze(-1),
        "attention": attention if attention is not None else torch.empty(0, device=embeddings.device),
    }


def mean_norm(value: torch.Tensor) -> float:
    return float(torch.linalg.vector_norm(value.flatten(1), dim=1).mean().item())


def mean_pairwise_std(value: torch.Tensor) -> float:
    return float(value.flatten(1).std(dim=0).mean().item())


def family_score(raw: np.ndarray, prompts: list[str], v2: dict[str, Any], references: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    expected = {
        prompt: family
        for family, concept in v2["concepts"].items()
        for prompt in concept["prompts"]
    }
    for index, prompt in enumerate(prompts):
        if prompt not in expected:
            continue
        palette = representation_to_oklab_numpy(raw[index:index + 1, :5])[0]
        closest = _family_distance(palette, references)[0][0]
        rows.append({"prompt": prompt, "expected": expected[prompt], "closest": closest, "pass": closest == expected[prompt]})
    return float(np.mean([row["pass"] for row in rows])), rows


def summarize(name: str, model: PaletteDecoder, embeddings: torch.Tensor, prompts: list[str], v2: dict[str, Any], references: dict[str, Any]) -> dict[str, Any]:
    with torch.inference_mode():
        values = forward_components(model, embeddings)
    raw = values["output"].detach().cpu().numpy()
    score, rows = family_score(raw, prompts, v2, references)
    return {
        "semanticFamilyWin": score,
        "bridgePriorEntropy": float((-(torch.softmax(values["prior_logits"], -1) * torch.log_softmax(values["prior_logits"], -1)).sum(-1)).mean().item()),
        "componentMeanNorm": {
            "text": mean_norm(values["text"]),
            "colorTokens": mean_norm(values["color_tokens"]),
            "styleToken": mean_norm(values["style_token"]),
            "crossAttention": mean_norm(values["cross"]),
            "bridgeContext": mean_norm(values["bridge_context"]),
            "finalPalette": mean_norm(values["output"]),
        },
        "componentPromptVariation": {
            "text": mean_pairwise_std(values["text"]),
            "colorTokens": mean_pairwise_std(values["color_tokens"]),
            "styleToken": mean_pairwise_std(values["style_token"]),
            "crossAttention": mean_pairwise_std(values["cross"]),
            "bridgeContext": mean_pairwise_std(values["bridge_context"]),
            "finalPalette": mean_pairwise_std(values["output"]),
        },
        "familyRows": rows,
        "raw": raw,
    }


def state_delta(left: PaletteDecoder, right: PaletteDecoder, prefix: str) -> dict[str, float]:
    left_state, right_state = left.state_dict(), right.state_dict()
    values = [
        (left_state[name].float() - right_state[name].float()).abs()
        for name in left_state.keys() & right_state.keys() if name.startswith(prefix)
    ]
    if not values:
        return {"tensorCount": 0, "meanAbsDelta": 0.0, "maxAbsDelta": 0.0}
    return {
        "tensorCount": len(values),
        "meanAbsDelta": float(torch.cat([item.flatten() for item in values]).mean().item()),
        "maxAbsDelta": float(max(item.max().item() for item in values)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--benchmark-v2", type=Path, default=Path("ml/palettebrain/benchmark_visual_semantic_v2.json"))
    parser.add_argument("--benchmark-v3", type=Path, default=Path("ml/palettebrain/benchmark_semantic_v3.json"))
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite trace: {args.output}")
    started = time.perf_counter()
    device = torch.device(args.device)
    static = load_static_evaluation_context(args.benchmark_v2, args.benchmark_v3, cache_dir=args.cache_dir, device=device)
    prompts = [prompt for family in static["v2"]["concepts"].values() for prompt in family["prompts"]]
    embeddings = torch.as_tensor(np.asarray([static["embeddings"][static["prompt_index"][prompt]] for prompt in prompts], dtype=np.float32), device=device)
    base = load_checkpoint(args.base, device)
    historical = load_checkpoint(args.historical, device)
    pretraining = recreate_pretraining_c11(args.base, device, args.seed)
    probe = load_checkpoint(args.probe, device)
    models = {"base": base, "historicalC11": historical, "preTrainingC11": pretraining, "oneEpochProbe": probe}
    summaries = {name: summarize(name, model, embeddings, prompts, static["v2"], static["references"]) for name, model in models.items()}
    raw = {name: row.pop("raw") for name, row in summaries.items()}
    result = {
        "schemaVersion": 1,
        "testClassification": "READ_ONLY_REAL_STAGE_A_PATH_TRACE",
        "trainingDataModified": False,
        "networkRequests": 0,
        "frozenBenchmarkUsedForEvaluationOnly": True,
        "checkpointSha256": {"base": sha256(args.base), "historicalC11": sha256(args.historical), "oneEpochProbe": sha256(args.probe)},
        "promptCount": len(prompts),
        "models": summaries,
        "checkpointParameterDelta": {
            "historicalVsBase": state_delta(historical, base, ""),
            "probeVsPreTrainingBridge": state_delta(probe, pretraining, "bridge."),
            "probeVsPreTrainingVisualCrossAttention": state_delta(probe, pretraining, "visual_cross_attention."),
        },
        "finalPaletteMeanAbsDelta": {
            "baseToPreTrainingC11": float(np.abs(raw["base"] - raw["preTrainingC11"]).mean()),
            "preTrainingC11ToProbe": float(np.abs(raw["preTrainingC11"] - raw["oneEpochProbe"]).mean()),
            "baseToProbe": float(np.abs(raw["base"] - raw["oneEpochProbe"]).mean()),
        },
        "elapsedSeconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "models"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
