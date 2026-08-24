"""Export a trained PaletteBrain decoder to ONNX and verify ORT parity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

try:
    import onnx
    import onnxruntime as ort
    import torch
except ImportError as exc:  # pragma: no cover - depends on local ML environment
    raise SystemExit(
        "Export requires torch, onnx, and onnxruntime from requirements.txt."
    ) from exc

try:
    from .model import PaletteDecoder, PaletteDecoderConfig
    from .dataset import seed_noise_from_uint32
except ImportError:
    from model import PaletteDecoder, PaletteDecoderConfig
    from dataset import seed_noise_from_uint32


INPUT_NAMES = [
    "text_embedding",
    "count_mask",
    "seed_noise",
    "locked_mask",
    "locked_colors",
]
OUTPUT_NAME = "palette"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parity_inputs() -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(20260824)
    batch_size = 4
    text_embedding = rng.standard_normal((batch_size, 384), dtype=np.float32)
    text_embedding /= np.maximum(
        np.linalg.norm(text_embedding, axis=1, keepdims=True), 1e-8
    )
    count_mask = np.zeros((batch_size, 9), dtype=np.float32)
    for row, count in enumerate((2, 4, 7, 9)):
        count_mask[row, :count] = 1.0
    seed_noise = np.stack(
        [seed_noise_from_uint32(seed) for seed in (0, 1234, 42, 0xFFFF_FFFF)]
    )
    locked_mask = np.zeros((batch_size, 9), dtype=np.float32)
    locked_mask[1, 0] = 1.0
    locked_mask[2, [1, 5]] = 1.0
    locked_mask[3, [0, 3, 7]] = 1.0
    locked_colors = np.zeros((batch_size, 9, 4), dtype=np.float32)
    locked_colors[..., 0] = rng.uniform(0.15, 0.9, (batch_size, 9))
    locked_colors[..., 1] = rng.uniform(0.01, 0.16, (batch_size, 9))
    locked_colors[..., 2:4] = rng.standard_normal(
        (batch_size, 9, 2), dtype=np.float32
    )
    hue = locked_colors[..., 2:4]
    hue /= np.maximum(np.linalg.norm(hue, axis=-1, keepdims=True), 1e-8)
    locked_colors[..., 2:4] = hue
    locked_colors *= locked_mask[..., None]
    return text_embedding, count_mask, seed_noise, locked_mask, locked_colors


def export(args: argparse.Namespace) -> dict[str, object]:
    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(
            f"checkpoint not found: {checkpoint_path}. No random weights are exported."
        )
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    config = PaletteDecoderConfig(**checkpoint["model_config"])
    model = PaletteDecoder(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    output_path = Path(args.output)
    manifest_path = Path(args.manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inputs_np = parity_inputs()
    inputs_torch = tuple(torch.from_numpy(value[:1]) for value in inputs_np)
    dynamic_axes = {name: {0: "batch"} for name in INPUT_NAMES}
    dynamic_axes[OUTPUT_NAME] = {0: "batch"}

    with torch.no_grad():
        export_kwargs = {
            "input_names": INPUT_NAMES,
            "output_names": [OUTPUT_NAME],
            "dynamic_axes": dynamic_axes,
            "opset_version": args.opset,
            "do_constant_folding": True,
            "export_params": True,
        }
        try:
            torch.onnx.export(
                model,
                inputs_torch,
                str(output_path),
                dynamo=False,
                **export_kwargs,
            )
        except TypeError:
            torch.onnx.export(model, inputs_torch, str(output_path), **export_kwargs)

    model_proto = onnx.load(str(output_path))
    onnx.checker.check_model(model_proto)
    session = ort.InferenceSession(
        str(output_path), providers=["CPUExecutionProvider"]
    )
    with torch.no_grad():
        pytorch_output = model(
            *(torch.from_numpy(value) for value in inputs_np)
        ).numpy()
    ort_output = session.run(
        [OUTPUT_NAME], dict(zip(INPUT_NAMES, inputs_np, strict=True))
    )[0]
    parity_error = float(np.max(np.abs(pytorch_output - ort_output)))
    if parity_error > args.parity_tolerance:
        raise RuntimeError(
            f"PyTorch/ORT max error {parity_error:.3e} exceeds "
            f"{args.parity_tolerance:.3e}"
        )

    if not np.isfinite(ort_output).all():
        raise RuntimeError("ONNX output contains a non-finite value")
    inactive = inputs_np[1] < 0.5
    inactive_error = float(np.max(np.abs(ort_output[inactive])))
    if inactive_error > args.parity_tolerance:
        raise RuntimeError(f"inactive ONNX slot error is {inactive_error:.3e}")

    size_bytes = output_path.stat().st_size
    max_bytes = int(args.max_size_mb * 1024 * 1024)
    if size_bytes > max_bytes:
        raise RuntimeError(
            f"decoder ONNX is {size_bytes} bytes, above {args.max_size_mb} MiB"
        )

    manifest: dict[str, object] = {
        "schemaVersion": 1,
        "modelVersion": args.model_version,
        "status": "synthetic_baseline_only",
        "productionReady": False,
        "model": output_path.name,
        "opset": args.opset,
        "inputs": {
            "text_embedding": ["batch", 384],
            "count_mask": ["batch", 9],
            "seed_noise": ["batch", 9, 4],
            "locked_mask": ["batch", 9],
            "locked_colors": ["batch", 9, 4],
        },
        "lockedColorRepresentation": [
            "L_physical",
            "C_physical",
            "sin_hue",
            "cos_hue",
        ],
        "output": {"palette": ["batch", 9, 5]},
        "outputRepresentation": [
            "L_logit",
            "relative_C_logit_against_runtime_gamut_max_times_0.92",
            "sin_hue",
            "cos_hue",
            "importance_0_to_1",
        ],
        "parameterCount": model.count_parameters(),
        "onnxSizeBytes": size_bytes,
        "sha256": sha256_file(output_path),
        "pytorchOnnxMaxError": parity_error,
        "inactiveSlotMaxAbsError": inactive_error,
        "runtimeLockGuardRequired": True,
        "checkpointEpoch": checkpoint.get("epoch"),
        "checkpointSmoke": bool(checkpoint.get("smoke", False)),
        "trainingDataKind": checkpoint.get("training_data_kind"),
        "warning": (
            "This export inherits synthetic training limitations and must not "
            "be described as production-quality without human evaluation."
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint", default="ml/palettebrain/checkpoints/best.pt"
    )
    parser.add_argument(
        "--output", default="ml/palettebrain/artifacts/palettebrain-decoder-v1.onnx"
    )
    parser.add_argument(
        "--manifest",
        default="ml/palettebrain/artifacts/palettebrain-decoder-v1.manifest.json",
    )
    parser.add_argument("--model-version", default="palettebrain-decoder-v1-synthetic")
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--parity-tolerance", type=float, default=1e-4)
    parser.add_argument("--max-size-mb", type=float, default=2.0)
    args = parser.parse_args()
    try:
        print(json.dumps(export(args), indent=2, sort_keys=True))
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
