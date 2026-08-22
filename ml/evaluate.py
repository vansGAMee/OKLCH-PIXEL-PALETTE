"""
Evaluate model on a dataset split. Reports actual metrics.
"""
import math
import torch
from torch.utils.data import DataLoader
from model import CharCNN
from dataset import PaletteDataset
from losses import decode_L, decode_relative_chroma, normalize_hue_vector
import argparse
from pathlib import Path
from tokenizer import load_vocab

HARMONY_NAMES = ["splitComplementary", "complementary", "analogous"]


@torch.no_grad()
def evaluate(
    model: CharCNN,
    loader: DataLoader,
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    total_hue_err = 0.0
    total_l_err = 0.0
    total_chroma_err = 0.0
    harmony_correct = 0
    n = 0

    for batch in loader:
        token_ids = batch["token_ids"].to(device)
        pred = model(token_ids)

        pred_L = decode_L(pred[:, 0])
        pred_hue_sin, pred_hue_cos, _ = normalize_hue_vector(pred[:, 1], pred[:, 2])
        pred_rel_chroma = decode_relative_chroma(pred[:, 3])
        pred_harmony = pred[:, 4:7].argmax(dim=1)

        target_L = batch["target_L"].to(device)
        target_hue_sin = batch["target_hue_sin"].to(device)
        target_hue_cos = batch["target_hue_cos"].to(device)
        target_rel_chroma = batch["target_relative_chroma"].to(device)
        target_harmony = batch["target_harmony_class"].to(device)

        # Circular hue MAE in degrees
        # angle of prediction - angle of target
        pred_angle = torch.atan2(pred_hue_sin, pred_hue_cos) * 180 / math.pi
        target_angle = torch.atan2(target_hue_sin, target_hue_cos) * 180 / math.pi
        diff = (pred_angle - target_angle + 180) % 360 - 180
        total_hue_err += diff.abs().sum().item()

        total_l_err += (pred_L - target_L).abs().sum().item()
        total_chroma_err += (pred_rel_chroma - target_rel_chroma).abs().sum().item()
        harmony_correct += (pred_harmony == target_harmony).sum().item()
        n += token_ids.size(0)

    return {
        "hue_mae_deg": total_hue_err / n,
        "lightness_mae": total_l_err / n,
        "chroma_mae": total_chroma_err / n,
        "harmony_accuracy": harmony_correct / n,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--split", type=str, default="test", choices=["train", "val", "test"])
    parser.add_argument("--data-dir", type=str, default="ml/data")
    parser.add_argument("--vocab", type=str, default="public/models/paletta-v1.vocab.json")
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    device = torch.device("cpu")
    vocab = load_vocab(args.vocab)
    dataset = PaletteDataset(Path(args.data_dir) / f"{args.split}.jsonl", vocab)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False)

    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=True)
    model_cfg = ckpt.get("model_config", {})
    model = CharCNN(**model_cfg)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)

    metrics = evaluate(model, loader, device)
    print(f"\n=== Evaluation on {args.split} ===")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")


if __name__ == "__main__":
    main()
