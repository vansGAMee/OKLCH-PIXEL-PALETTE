"""Measure real cached-embedding decoder latency and artifact sizes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time
from typing import Callable

try:
    import torch
except ImportError as exc:  # pragma: no cover - depends on local ML environment
    raise SystemExit(
        "PyTorch is required for benchmarking. Install requirements.txt."
    ) from exc

try:
    from .model import PaletteDecoder, PaletteDecoderConfig
    from .dataset import seed_noise_from_uint32
except ImportError:
    from model import PaletteDecoder, PaletteDecoderConfig
    from dataset import seed_noise_from_uint32


def synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def measure(
    call: Callable[[int], None],
    *,
    iterations: int,
    warmup: int,
    device: torch.device,
) -> dict[str, float | int]:
    with torch.no_grad():
        for index in range(warmup):
            call(index)
        synchronize(device)
        samples_ms: list[float] = []
        for index in range(iterations):
            start = time.perf_counter_ns()
            call(index)
            synchronize(device)
            samples_ms.append((time.perf_counter_ns() - start) / 1_000_000.0)
    ordered = sorted(samples_ms)
    p95_index = min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))
    return {
        "iterations": iterations,
        "meanMs": statistics.fmean(samples_ms),
        "medianMs": statistics.median(samples_ms),
        "p95Ms": ordered[p95_index],
        "minMs": ordered[0],
        "maxMs": ordered[-1],
    }


def make_mask(batch_size: int, count: int, device: torch.device) -> torch.Tensor:
    mask = torch.zeros(batch_size, 9, device=device)
    mask[:, :count] = 1.0
    return mask


def benchmark(args: argparse.Namespace) -> dict[str, object]:
    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"checkpoint not found: {checkpoint_path}")
    device = torch.device(args.device)
    if args.threads is not None and device.type == "cpu":
        torch.set_num_threads(args.threads)

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    config = PaletteDecoderConfig(**checkpoint["model_config"])
    model = PaletteDecoder(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()

    generator = torch.Generator(device=device).manual_seed(args.seed)
    embedding = torch.randn(
        args.batch_size, 384, generator=generator, device=device
    )
    embedding = torch.nn.functional.normalize(embedding, dim=-1)
    seed_variants = [
        torch.from_numpy(seed_noise_from_uint32((args.seed + offset) & 0xFFFF_FFFF))
        .to(device)
        .unsqueeze(0)
        .expand(args.batch_size, -1, -1)
        for offset in range(8)
    ]
    count_variants = [make_mask(args.batch_size, count, device) for count in range(2, 10)]
    unlocked_mask = torch.zeros(args.batch_size, 9, device=device)
    unlocked_colors = torch.zeros(args.batch_size, 9, 4, device=device)
    locked_mask = torch.zeros(args.batch_size, 9, device=device)
    locked_mask[:, [0, 3]] = 1.0
    locked_colors = torch.zeros(args.batch_size, 9, 4, device=device)
    locked_colors[..., 0] = 0.55
    locked_colors[..., 1] = 0.08
    locked_colors[..., 3] = 1.0

    def base_call(index: int) -> None:
        model(
            embedding,
            count_variants[3],
            seed_variants[0],
            unlocked_mask,
            unlocked_colors,
        )

    def seed_call(index: int) -> None:
        model(
            embedding,
            count_variants[3],
            seed_variants[index % len(seed_variants)],
            unlocked_mask,
            unlocked_colors,
        )

    def count_call(index: int) -> None:
        model(
            embedding,
            count_variants[index % len(count_variants)],
            seed_variants[0],
            unlocked_mask,
            unlocked_colors,
        )

    def locked_call(index: int) -> None:
        model(
            embedding,
            count_variants[5],
            seed_variants[index % len(seed_variants)],
            locked_mask,
            locked_colors,
        )

    latency = {
        "warmGeneration": measure(
            base_call,
            iterations=args.iterations,
            warmup=args.warmup,
            device=device,
        ),
        "seedRegenerationCachedEmbedding": measure(
            seed_call,
            iterations=args.iterations,
            warmup=args.warmup,
            device=device,
        ),
        "countChangeCachedEmbedding": measure(
            count_call,
            iterations=args.iterations,
            warmup=args.warmup,
            device=device,
        ),
        "lockedRegenerationCachedEmbedding": measure(
            locked_call,
            iterations=args.iterations,
            warmup=args.warmup,
            device=device,
        ),
    }
    artifact_sizes = {"checkpointBytes": checkpoint_path.stat().st_size}
    if args.onnx:
        onnx_path = Path(args.onnx)
        artifact_sizes["onnxBytes"] = (
            onnx_path.stat().st_size if onnx_path.is_file() else None
        )

    return {
        "schemaVersion": 1,
        "measured": True,
        "scope": "decoder_only_with_cached_384d_text_embedding",
        "productionReady": False,
        "device": str(device),
        "torchThreads": torch.get_num_threads() if device.type == "cpu" else None,
        "batchSize": args.batch_size,
        "parameterCount": model.count_parameters(),
        "checkpointSmoke": bool(checkpoint.get("smoke", False)),
        "latency": latency,
        "artifactSizes": artifact_sizes,
        "excludes": [
            "text_encoder_initialization",
            "text_encoding",
            "browser_worker_message_overhead",
            "OKLCH_to_sRGB_postprocessing",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint", default="ml/palettebrain/checkpoints/best.pt"
    )
    parser.add_argument("--onnx")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=25)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = benchmark(args)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
