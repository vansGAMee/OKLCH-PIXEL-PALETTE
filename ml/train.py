"""
Training script for CharCNN palette intent predictor.
Usage:
  python train.py [--smoke] [--data-dir ml/data] [--epochs 15] [--batch-size 128]
"""
import argparse
import os
import sys
import random
import math
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Add ml/ to path so sibling imports work
sys.path.insert(0, str(Path(__file__).parent))

from model import CharCNN
from dataset import PaletteDataset
from losses import palette_loss
from evaluate import evaluate
from tokenizer import build_vocab, save_vocab, load_vocab, MAX_LENGTH


HARMONY_NAMES = ["splitComplementary", "complementary", "analogous"]
VOCAB_PATH = "public/models/paletta-v1.vocab.json"
CHECKPOINT_DIR = Path("ml/checkpoints")


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)


def train(args: argparse.Namespace) -> None:
    set_seed(42)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Vocab ---
    vocab_path = Path(VOCAB_PATH)
    if vocab_path.exists():
        vocab = load_vocab(str(vocab_path))
        print(f"Loaded vocab: {len(vocab)} entries")
    else:
        vocab = build_vocab()
        save_vocab(vocab, str(vocab_path))
        print(f"Built vocab: {len(vocab)} entries")

    vocab_size = len(vocab)

    # --- Data ---
    data_dir = Path(args.data_dir)
    train_ds = PaletteDataset(data_dir / "train.jsonl", vocab)
    val_ds   = PaletteDataset(data_dir / "val.jsonl", vocab)

    num_workers = min(4, os.cpu_count() or 1)
    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=False, drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size * 2, shuffle=False,
        num_workers=num_workers,
    )

    print(f"Train: {len(train_ds)}, Val: {len(val_ds)}")

    # --- Model ---
    model_config = {
        "vocab_size": vocab_size,
        "embed_dim": 48,
        "conv_channels": 64,
        "hidden_dim": 128,
        "max_length": MAX_LENGTH,
        "dropout": 0.10,
    }
    model = CharCNN(**model_config)
    device = torch.device("cpu")
    model.to(device)
    print(f"Parameters: {model.count_parameters():,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr=3e-4,
        epochs=args.epochs,
        steps_per_epoch=len(train_loader),
        pct_start=0.1,
    )

    best_val_loss = float("inf")
    patience_count = 0
    patience = args.patience

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        n_batches = 0

        for batch in train_loader:
            token_ids = batch["token_ids"].to(device)
            targets = {k: v.to(device) for k, v in batch.items() if k != "token_ids"}

            optimizer.zero_grad()
            pred = model(token_ids)
            loss, _ = palette_loss(pred, targets)

            if not torch.isfinite(loss):
                print(f"WARNING: non-finite loss {loss.item()}, skipping batch")
                continue

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()

            epoch_loss += loss.item()
            n_batches += 1

        avg_train_loss = epoch_loss / max(n_batches, 1)

        # Validation
        model.eval()
        val_loss_total = 0.0
        val_batches = 0
        with torch.no_grad():
            for batch in val_loader:
                token_ids = batch["token_ids"].to(device)
                targets = {k: v.to(device) for k, v in batch.items() if k != "token_ids"}
                pred = model(token_ids)
                loss, _ = palette_loss(pred, targets)
                if torch.isfinite(loss):
                    val_loss_total += loss.item()
                    val_batches += 1

        avg_val_loss = val_loss_total / max(val_batches, 1)

        print(
            f"Epoch {epoch:3d}/{args.epochs} | "
            f"train_loss={avg_train_loss:.4f} | val_loss={avg_val_loss:.4f}"
        )

        # Save best
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_count = 0
            ckpt = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_loss": avg_val_loss,
                "model_config": {
                    "vocab_size": vocab_size,
                    "embed_dim": 48,
                    "conv_channels": 64,
                    "hidden_dim": 128,
                    "max_length": MAX_LENGTH,
                    "dropout": 0.0,  # No dropout at eval
                },
            }
            torch.save(ckpt, CHECKPOINT_DIR / "best.pt")
            print(f"  ✓ New best val_loss={best_val_loss:.4f}")
        else:
            patience_count += 1
            if patience_count >= patience:
                print(f"Early stopping at epoch {epoch}")
                break

    # Save last
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "val_loss": avg_val_loss,
        "model_config": {
            "vocab_size": vocab_size,
            "embed_dim": 48,
            "conv_channels": 64,
            "hidden_dim": 128,
            "max_length": MAX_LENGTH,
            "dropout": 0.0,
        },
    }, CHECKPOINT_DIR / "last.pt")

    print(f"\nTraining complete. Best val_loss={best_val_loss:.4f}")

    # Final evaluation on val set using best checkpoint
    ckpt = torch.load(CHECKPOINT_DIR / "best.pt", map_location=device, weights_only=True)
    model.load_state_dict(ckpt["model_state_dict"])
    metrics = evaluate(model, val_loader, device)
    print("\n=== Val Metrics (best checkpoint) ===")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Quick smoke test with tiny data")
    parser.add_argument("--data-dir", type=str, default="ml/data")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--patience", type=int, default=4)
    args = parser.parse_args()

    if args.smoke:
        args.data_dir = "ml/data/smoke"
        args.epochs = 5
        args.batch_size = 64
        args.patience = 3

    train(args)


if __name__ == "__main__":
    main()
