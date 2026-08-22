"""
Check disk budget before/after ML operations.
"""
import os
import sys
from pathlib import Path


GB = 1024 ** 3
MB = 1024 ** 2

LIMITS = {
    "dataset_mb": 200,
    "checkpoints_mb": 100,
    "onnx_mb": 3,
    "total_added_gb": 50,
}

DIRS_TO_CHECK = {
    "ml/data": "Dataset",
    "ml/checkpoints": "Checkpoints",
    "public/models": "Production models",
    "public/ort": "WASM assets",
    "ml/.venv": "Python venv",
}


def dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def check_budget(baseline_bytes: int | None = None) -> bool:
    ok = True
    print("=== Disk Budget Check ===\n")

    # Check each dir
    for rel_path, label in DIRS_TO_CHECK.items():
        path = Path(rel_path)
        size = dir_size_bytes(path)
        if size > 0:
            print(f"  {label} ({rel_path}): {size / MB:.1f} MB")

    # Specific limits
    onnx_path = Path("public/models/paletta-v1.onnx")
    if onnx_path.exists():
        onnx_size = onnx_path.stat().st_size
        onnx_mb = onnx_size / MB
        status = "OK" if onnx_mb <= LIMITS["onnx_mb"] else "OVER LIMIT"
        print(f"\n  ONNX model: {onnx_mb:.2f} MB [{status}]")
        if onnx_mb > LIMITS["onnx_mb"]:
            ok = False

    dataset_size = dir_size_bytes(Path("ml/data")) / MB
    if dataset_size > 0:
        status = "OK" if dataset_size <= LIMITS["dataset_mb"] else "OVER LIMIT"
        print(f"  Dataset: {dataset_size:.1f} MB [{status}]")
        if dataset_size > LIMITS["dataset_mb"]:
            ok = False

    ckpt_size = dir_size_bytes(Path("ml/checkpoints")) / MB
    if ckpt_size > 0:
        status = "OK" if ckpt_size <= LIMITS["checkpoints_mb"] else "OVER LIMIT"
        print(f"  Checkpoints: {ckpt_size:.1f} MB [{status}]")
        if ckpt_size > LIMITS["checkpoints_mb"]:
            ok = False

    # Total disk
    stat = os.statvfs(".")
    free_gb = stat.f_frsize * stat.f_bavail / GB
    print(f"\n  Free disk: {free_gb:.1f} GB")

    print(f"\n{'BUDGET: OK' if ok else 'BUDGET: OVER LIMIT'}")
    return ok


if __name__ == "__main__":
    baseline = int(sys.argv[1]) if len(sys.argv) > 1 else None
    ok = check_budget(baseline)
    sys.exit(0 if ok else 1)
