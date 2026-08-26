"""Deterministic Candidate 11 E5 -> PyTorch -> desktop ORT parity trace.

This harness never changes weights.  It records raw decoder tensors as well as
decoded perceptual colors so runtime bugs cannot be hidden by HEX-only checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import torch

try:
    from .color_math import CHROMA_HEADROOM, max_srgb_chroma_at, oklch_to_srgb
    from .dataset import seed_noise_from_uint32
    from .e5_embedding import embed_texts, load_encoder
    from .model import PaletteDecoder, PaletteDecoderConfig
except ImportError:
    from color_math import CHROMA_HEADROOM, max_srgb_chroma_at, oklch_to_srgb
    from dataset import seed_noise_from_uint32
    from e5_embedding import embed_texts, load_encoder
    from model import PaletteDecoder, PaletteDecoderConfig


DEFAULT_PROMPTS = [
    "rain", "дождь", "grass", "трава", "snow", "снег", "hospital",
    "больница", "glass", "стекло", "red", "red and blue",
]
INPUT_NAMES = [
    "text_embedding", "count_mask", "seed_noise", "locked_mask", "locked_colors"
]


def _sha256_float32(value: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(value, dtype="<f4").tobytes()).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hex_from_srgb(rgb: tuple[float, float, float]) -> str:
    values = [round(min(1.0, max(0.0, channel)) * 255.0) for channel in rgb]
    return "#" + "".join(f"{value:02X}" for value in values)


def decode_raw(raw: np.ndarray, count: int) -> list[dict[str, Any]]:
    decoded: list[dict[str, Any]] = []
    for slot in range(count):
        lightness = 0.07 + 0.86 / (1.0 + math.exp(-float(raw[slot, 0])))
        hue_sin, hue_cos = map(float, raw[slot, 2:4])
        hue_norm = math.hypot(hue_sin, hue_cos)
        if hue_norm < 1e-8:
            chroma, hue = 0.0, None
            rgb = oklch_to_srgb(lightness, chroma, 0.0)
        else:
            hue = math.degrees(math.atan2(hue_sin / hue_norm, hue_cos / hue_norm)) % 360.0
            relative_chroma = 1.0 / (1.0 + math.exp(-float(raw[slot, 1])))
            chroma = relative_chroma * max_srgb_chroma_at(lightness, hue) * CHROMA_HEADROOM
            rgb = oklch_to_srgb(lightness, chroma, hue)
        decoded.append(
            {
                "slot": slot,
                "oklch": [lightness, chroma, hue],
                "srgb": list(rgb),
                "hex": _hex_from_srgb(rgb),
            }
        )
    return decoded


def _inputs(embedding: np.ndarray, count: int, seed: int) -> tuple[np.ndarray, ...]:
    count_mask = np.zeros((1, 9), dtype=np.float32)
    count_mask[0, :count] = 1.0
    return (
        embedding.reshape(1, 384).astype(np.float32),
        count_mask,
        seed_noise_from_uint32(seed).reshape(1, 9, 4).astype(np.float32),
        np.zeros((1, 9), dtype=np.float32),
        np.zeros((1, 9, 4), dtype=np.float32),
    )


def _load_browser_embeddings(path: Path) -> dict[str, np.ndarray]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("mode") != "embeddings":
        raise ValueError("browser embedding report must use mode=embeddings")
    output: dict[str, np.ndarray] = {}
    for row in report.get("results", []):
        output[str(row["prompt"])] = np.asarray(row["embedding"], dtype=np.float32)
    return output


def _load_browser_raw(path: Path) -> dict[str, np.ndarray]:
    report = json.loads(path.read_text(encoding="utf-8"))
    output: dict[str, np.ndarray] = {}
    for row in report.get("results", []):
        raw = row.get("rawDecoderOutput")
        if raw and raw.get("dims") == [1, 9, 5]:
            output[str(row["request"]["prompt"])] = np.asarray(raw["data"], dtype=np.float32).reshape(1, 9, 5)
    return output


def run(args: argparse.Namespace) -> dict[str, Any]:
    checkpoint_path = Path(args.checkpoint)
    onnx_path = Path(args.onnx)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    config = PaletteDecoderConfig(**checkpoint["model_config"])
    model = PaletteDecoder(config)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    encoder = load_encoder(device=args.device, cache_dir=args.cache_dir)
    prompts = args.prompt or DEFAULT_PROMPTS
    full_embeddings = embed_texts(prompts, encoder=encoder, batch_size=32)
    browser_embeddings = (
        _load_browser_embeddings(Path(args.browser_embeddings))
        if args.browser_embeddings
        else {}
    )
    browser_raw = _load_browser_raw(Path(args.browser_palette_report)) if args.browser_palette_report else {}

    rows: list[dict[str, Any]] = []
    max_delta = 0.0
    maximum_browser_delta = 0.0
    for index, prompt in enumerate(prompts):
        full_embedding = full_embeddings[index]
        decoder_embedding = browser_embeddings.get(prompt, full_embedding)
        inputs_np = _inputs(decoder_embedding, args.count, args.seed)
        with torch.no_grad():
            pt_raw = model(*(torch.from_numpy(value) for value in inputs_np)).numpy()
            prior_logits, style_latent, color_tokens, style_token = model.bridge(
                torch.from_numpy(inputs_np[0])
            )
        ort_raw = session.run(["palette"], dict(zip(INPUT_NAMES, inputs_np, strict=True)))[0]
        delta = float(np.max(np.abs(pt_raw - ort_raw)))
        max_delta = max(max_delta, delta)
        browser_delta = (
            float(np.max(np.abs(ort_raw - browser_raw[prompt])))
            if prompt in browser_raw else None
        )
        if browser_delta is not None:
            maximum_browser_delta = max(maximum_browser_delta, browser_delta)
        cosine = float(np.dot(full_embedding, decoder_embedding))
        row = {
            "prompt": prompt,
            "embedding": {
                "source": "browser_q8" if prompt in browser_embeddings else "pytorch_full",
                "sha256": _sha256_float32(decoder_embedding),
                "fullPrecisionSha256": _sha256_float32(full_embedding),
                "fullVsBrowserCosine": cosine,
                "norm": float(np.linalg.norm(decoder_embedding)),
            },
            "decoderInputs": {
                name: {"shape": list(value.shape), "sha256": _sha256_float32(value)}
                for name, value in zip(INPUT_NAMES, inputs_np, strict=True)
            },
            "bridge": {
                "priorTopBins": np.argsort(-prior_logits.numpy()[0])[:10].tolist(),
                "priorEntropy": float(
                    -(torch.softmax(prior_logits, -1) * torch.log_softmax(prior_logits, -1)).sum()
                ),
                "styleNorm": float(torch.linalg.vector_norm(style_latent)),
                "colorTokenNorms": torch.linalg.vector_norm(color_tokens, dim=-1)[0].tolist(),
                "styleTokenNorm": float(torch.linalg.vector_norm(style_token)),
            },
            "pytorchRaw": pt_raw[0].tolist(),
            "onnxRaw": ort_raw[0].tolist(),
            "pytorchOnnxMaxAbsDelta": delta,
            "onnxBrowserMaxAbsDelta": browser_delta,
            "decoded": decode_raw(ort_raw[0], args.count),
        }
        rows.append(row)

    report = {
        "schemaVersion": 1,
        "candidate": "candidate-11",
        "case": {"count": args.count, "seed": args.seed, "locks": []},
        "artifacts": {
            "checkpoint": str(checkpoint_path).replace("\\", "/"),
            "onnx": str(onnx_path).replace("\\", "/"),
            "onnxSha256": _sha256_file(onnx_path),
            "architecture": config.to_dict(),
        },
        "pytorchOnnx": {
            "pass": max_delta <= args.tolerance,
            "tolerance": args.tolerance,
            "maxAbsDelta": max_delta,
        },
        "onnxBrowser": {
            "pass": bool(browser_raw) and maximum_browser_delta <= args.tolerance,
            "tolerance": args.tolerance,
            "maxAbsDelta": maximum_browser_delta if browser_raw else None,
            "rawPromptCount": len(browser_raw),
        },
        "rows": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="ml/palettebrain/checkpoints/candidate-11-best.pt")
    parser.add_argument("--onnx", default="public/models/palettebrain-v4-candidate11-b1bc9346.onnx")
    parser.add_argument("--output", default="ml/palettebrain/reports/candidate-11-parity.json")
    parser.add_argument("--browser-embeddings")
    parser.add_argument("--browser-palette-report")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tolerance", type=float, default=1e-4)
    parser.add_argument("--prompt", action="append")
    args = parser.parse_args()
    report = run(args)
    print(json.dumps(report["pytorchOnnx"], indent=2))


if __name__ == "__main__":
    main()
