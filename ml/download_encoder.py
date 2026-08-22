"""
download_encoder.py
Downloads quantized Xenova/multilingual-e5-small model and tokenizer assets
directly into public/models/multilingual-e5-small/ for local browser inference.
"""
import os
import urllib.request
from pathlib import Path

BASE_URL = "https://huggingface.co/Xenova/multilingual-e5-small/resolve/main"

FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "onnx/model_quantized.onnx",
]

DEST_DIR = Path(__file__).resolve().parent.parent / "public" / "models" / "multilingual-e5-small"

def download_file(rel_path: str):
    url = f"{BASE_URL}/{rel_path}"
    dest_path = DEST_DIR / rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    if dest_path.exists() and dest_path.stat().st_size > 0:
        print(f"Already exists: {rel_path} ({dest_path.stat().st_size / 1024 / 1024:.2f} MB)")
        return

    print(f"Downloading {url} -> {dest_path}...")
    req = urllib.request.Request(url, headers={"User-Agent": "aipalette-downloader"})
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as f:
        f.write(resp.read())
    print(f"Done: {rel_path} ({dest_path.stat().st_size / 1024 / 1024:.2f} MB)")

def main():
    print(f"Target directory: {DEST_DIR}")
    for f in FILES:
        download_file(f)

    total_bytes = sum(p.stat().st_size for p in DEST_DIR.glob("**/*") if p.is_file())
    print(f"\nTotal multilingual-e5-small asset size: {total_bytes / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    main()
