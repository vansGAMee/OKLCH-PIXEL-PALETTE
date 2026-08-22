"""
Export CharCNN to ONNX and validate against Python ORT.
"""
import sys
import hashlib
import json
import math
import argparse
from pathlib import Path

import torch
import onnx
import onnxruntime as ort
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from model import CharCNN
from tokenizer import load_vocab, tokenize, MAX_LENGTH

HARMONY_NAMES = ["splitComplementary", "complementary", "analogous"]
OUTPUT_NAMES = [
    "lightness_logit",
    "hue_sin",
    "hue_cos",
    "relative_chroma_logit",
    "splitComplementary",
    "complementary",
    "analogous",
]

TEST_PROMPTS = [
    "winter starry forest",
    "зимний звездный лес",
    "ржавый завод на закате",
    "нежная весенняя сакура",
    "токсичное зеленое болото",
    "туманное холодное утро",
    "ночной океан под луной",
    "уютная осенняя кофейня",
    "неоновый киберпанк под дождем",
    "rusty abandoned factory at sunset",
    "soft spring sakura",
    "toxic green swamp",
    "foggy cold morning",
    "moonlit ocean",
    "warm cozy autumn cafe",
    "neon cyberpunk rain",
    "dark volcanic landscape",
    "warm desert sunset",
    "bright summer meadow",
    "deep space galaxy",
    "ancient wood forest",
    "snowy mountain peak",
    "golden autumn forest",
    "cold steel factory",
]


def export_and_validate(args: argparse.Namespace) -> None:
    vocab_path = Path(args.vocab)
    onnx_path = Path(args.onnx)
    manifest_path = Path(args.manifest)

    vocab = load_vocab(str(vocab_path))
    vocab_size = len(vocab)

    # Load checkpoint
    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model_cfg = ckpt.get("model_config", {})
    # Ensure dropout=0 for export
    model_cfg["dropout"] = 0.0
    model = CharCNN(**model_cfg)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    print(f"Model parameters: {model.count_parameters():,}")

    # Dummy input [1, 96]
    dummy_ids = torch.zeros(1, MAX_LENGTH, dtype=torch.int64)

    onnx_path.parent.mkdir(parents=True, exist_ok=True)

    # Export using legacy API to produce single self-contained ONNX file
    # Explicitly use legacy (TorchScript-based) export to avoid external .onnx.data
    import warnings
    with torch.no_grad():
        # PyTorch 2.x: force legacy exporter
        try:
            torch.onnx.export(
                model,
                dummy_ids,
                str(onnx_path),
                input_names=["token_ids"],
                output_names=["output"],
                dynamic_axes={"token_ids": {0: "batch"}, "output": {0: "batch"}},
                opset_version=14,
                do_constant_folding=True,
                export_params=True,
                dynamo=False,  # PyTorch 2.x flag
            )
        except TypeError:
            # Older torch without dynamo kwarg
            torch.onnx.export(
                model,
                dummy_ids,
                str(onnx_path),
                input_names=["token_ids"],
                output_names=["output"],
                dynamic_axes={"token_ids": {0: "batch"}, "output": {0: "batch"}},
                opset_version=14,
                do_constant_folding=True,
                export_params=True,
            )
    print(f"Exported ONNX: {onnx_path}")

    # ONNX checker
    model_proto = onnx.load(str(onnx_path))
    onnx.checker.check_model(model_proto)
    print("ONNX checker: PASS")

    # Python ORT validation
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    max_error = 0.0
    print(f"\nRunning parity check on {len(TEST_PROMPTS)} prompts...")
    for prompt in TEST_PROMPTS:
        ids = tokenize(prompt, vocab, MAX_LENGTH)
        ids_tensor = torch.tensor([ids], dtype=torch.int64)

        with torch.no_grad():
            pt_out = model(ids_tensor).numpy()

        ort_out = sess.run(None, {"token_ids": np.array([ids], dtype=np.int64)})[0]

        err = float(np.abs(pt_out - ort_out).max())
        max_error = max(max_error, err)

    print(f"Max |PyTorch - ORT| error: {max_error:.2e}")
    if max_error > 1e-4:
        print(f"WARNING: error {max_error:.2e} exceeds 1e-4 target")
    else:
        print("Parity: PASS")

    # SHA256
    with open(onnx_path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    onnx_size = onnx_path.stat().st_size
    print(f"ONNX size: {onnx_size:,} bytes ({onnx_size/1024:.1f} KB)")

    if onnx_size > 3 * 1024 * 1024:
        print("ERROR: ONNX exceeds 3 MB hard limit!")
        sys.exit(1)

    # Write manifest
    manifest = {
        "version": 1,
        "model": onnx_path.name,
        "vocab": vocab_path.name,
        "maxLength": MAX_LENGTH,
        "parameterCount": model.count_parameters(),
        "harmonies": HARMONY_NAMES,
        "outputs": OUTPUT_NAMES,
        "sha256": sha256,
        "onnxSizeBytes": onnx_size,
        "pytorchOnnxMaxError": max_error,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written: {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, default="ml/checkpoints/best.pt")
    parser.add_argument("--vocab", type=str, default="public/models/paletta-v1.vocab.json")
    parser.add_argument("--onnx", type=str, default="public/models/paletta-v1.onnx")
    parser.add_argument("--manifest", type=str, default="public/models/paletta-v1.manifest.json")
    args = parser.parse_args()
    export_and_validate(args)


if __name__ == "__main__":
    main()
