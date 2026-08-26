"""Versioned, reproducible Candidate 11 ONNX export with raw PT/ORT parity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch

try:
    from .dataset import seed_noise_from_uint32
    from .model import PaletteDecoder, PaletteDecoderConfig
except ImportError:
    from dataset import seed_noise_from_uint32
    from model import PaletteDecoder, PaletteDecoderConfig


INPUT_NAMES = ["text_embedding", "count_mask", "seed_noise", "locked_mask", "locked_colors"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parity_inputs() -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(20260826)
    embeddings = rng.standard_normal((6, 384), dtype=np.float32)
    embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)
    count_mask = np.zeros((6, 9), dtype=np.float32)
    for row, count in enumerate((2, 3, 5, 7, 8, 9)):
        count_mask[row, :count] = 1
    seed_noise = np.stack([seed_noise_from_uint32(seed) for seed in (0, 1, 2, 42, 137, 999)])
    locked_mask = np.zeros((6, 9), dtype=np.float32)
    locked_mask[1, 0] = 1
    locked_mask[3, [1, 4]] = 1
    locked_colors = np.zeros((6, 9, 4), dtype=np.float32)
    locked_colors[..., 0] = 0.55
    locked_colors[..., 1] = 0.08
    locked_colors[..., 3] = 1.0
    locked_colors *= locked_mask[..., None]
    return embeddings, count_mask, seed_noise.astype(np.float32), locked_mask, locked_colors


def export(args: argparse.Namespace) -> dict[str, object]:
    checkpoint_path = Path(args.checkpoint)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if checkpoint.get("candidate") not in (None, "candidate-11"):
        raise RuntimeError("refusing to export a checkpoint that is not Candidate 11")
    config = PaletteDecoderConfig(**checkpoint["model_config"])
    model = PaletteDecoder(config).eval()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    inputs = parity_inputs()
    example = tuple(torch.from_numpy(value[:1]) for value in inputs)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        torch.onnx.export(
            model, example, str(temporary), input_names=INPUT_NAMES, output_names=["palette"],
            dynamic_axes={**{name: {0: "batch"} for name in INPUT_NAMES}, "palette": {0: "batch"}},
            opset_version=args.opset, do_constant_folding=True, dynamo=False,
        )
        onnx.checker.check_model(onnx.load(str(temporary)))
        session = ort.InferenceSession(str(temporary), providers=["CPUExecutionProvider"])
        with torch.no_grad():
            pytorch_output = model(*(torch.from_numpy(value) for value in inputs)).numpy()
        ort_output = session.run(["palette"], dict(zip(INPUT_NAMES, inputs, strict=True)))[0]
        maximum_delta = float(np.max(np.abs(pytorch_output - ort_output)))
        if maximum_delta > args.tolerance:
            raise RuntimeError(f"PT/ORT max delta {maximum_delta} exceeds {args.tolerance}")
        if not np.isfinite(ort_output).all():
            raise RuntimeError("ORT output is not finite")
        inactive_error = float(np.max(np.abs(ort_output[inputs[1] < 0.5])))
        if inactive_error > args.tolerance:
            raise RuntimeError(f"inactive slot max error {inactive_error} exceeds {args.tolerance}")
        size_bytes = temporary.stat().st_size
        if size_bytes > args.max_bytes:
            raise RuntimeError(f"ONNX is {size_bytes} bytes; hard limit is {args.max_bytes}")
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)

    sha256 = sha256_file(output_path)
    manifest = {
        "schemaVersion": 2,
        "modelVersion": f"palettebrain-v4-candidate11-{sha256[:8]}",
        "codename": None,
        "trainedFromCandidate": 11,
        "productionReady": False,
        "decoder": {
            "path": f"/models/{output_path.name}", "url": f"/models/{output_path.name}",
            "sha256": sha256, "bytes": output_path.stat().st_size,
            "sizeBytes": output_path.stat().st_size, "format": "onnx", "opset": args.opset,
            "inputs": {
                "text_embedding": [None, 384], "count_mask": [None, 9],
                "seed_noise": [None, 9, 4], "locked_mask": [None, 9],
                "locked_colors": [None, 9, 4],
            },
            "outputs": {"palette": [None, 9, 5]},
        },
        "textEncoder": {
            "id": "intfloat/multilingual-e5-small", "browserId": "multilingual-e5-small",
            "dimension": 384, "prefix": "query: ", "pooling": "mean", "l2Normalized": True,
            "sha256": "f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193",
            "bytes": 118308185, "revision": "ae61bf0193ce3851dc8a45147e459b04ed783d8a",
        },
        "qualification": {
            "pytorchOnnxMaxAbsDelta": maximum_delta,
            "inactiveSlotMaxAbsError": inactive_error,
            "parameterCount": model.count_parameters(),
            "checkpointEpoch": checkpoint.get("epoch"),
            "visualConditioning": config.visual_conditioning,
        },
    }
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--tolerance", type=float, default=1e-4)
    parser.add_argument("--max-bytes", type=int, default=5 * 1024 * 1024)
    args = parser.parse_args()
    print(json.dumps(export(args), indent=2))


if __name__ == "__main__":
    main()
