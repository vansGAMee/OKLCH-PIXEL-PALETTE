"""
train_head.py
Trains a lightweight palette regression head on top of frozen 384-d multilingual-e5-small embeddings.
Exports trained head to ONNX at public/models/palette-head.onnx.
"""
import math
import random
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

ROOT = Path(__file__).resolve().parent.parent
DATA_NPZ = ROOT / "ml" / "dataset_embeddings.npz"
CHECKPOINT_PATH = ROOT / "ml" / "checkpoints" / "palette_head.pt"
ONNX_EXPORT_PATH = ROOT / "public" / "models" / "palette-head.onnx"

class PaletteHead(nn.Module):
    def __init__(self, in_dim: int = 384, hidden_dim: int = 128, out_dim: int = 7):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(0.10),
            nn.Linear(hidden_dim, out_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

class PaletteDataset(Dataset):
    def __init__(self, embeddings, hue_sin, hue_cos, lightnesses, chromas, harmonies, is_anchors):
        self.embeddings = torch.tensor(embeddings, dtype=torch.float32)
        self.hue_sin = torch.tensor(hue_sin, dtype=torch.float32)
        self.hue_cos = torch.tensor(hue_cos, dtype=torch.float32)
        self.lightnesses = torch.tensor(lightnesses, dtype=torch.float32)
        self.chromas = torch.tensor(chromas, dtype=torch.float32)
        self.harmonies = torch.tensor(harmonies, dtype=torch.long)
        self.is_anchors = torch.tensor(is_anchors, dtype=torch.float32)

    def __len__(self):
        return len(self.embeddings)

    def __getitem__(self, idx):
        return {
            "embedding": self.embeddings[idx],
            "hue_sin": self.hue_sin[idx],
            "hue_cos": self.hue_cos[idx],
            "lightness": self.lightnesses[idx],
            "chroma": self.chromas[idx],
            "harmony": self.harmonies[idx],
            "is_anchor": self.is_anchors[idx],
        }

def compute_loss(pred: torch.Tensor, batch: dict) -> tuple[torch.Tensor, dict]:
    # pred shape: [batch, 7]
    pred_l_logit = pred[:, 0]
    pred_h_sin = pred[:, 1]
    pred_h_cos = pred[:, 2]
    pred_c_logit = pred[:, 3]
    pred_harm_logits = pred[:, 4:7]

    # Target values
    tgt_h_sin = batch["hue_sin"]
    tgt_h_cos = batch["hue_cos"]
    tgt_l = batch["lightness"]
    tgt_c = batch["chroma"]
    tgt_harm = batch["harmony"]
    is_anchor = batch["is_anchor"]

    # 1. Angular Hue Loss
    pred_norm = torch.sqrt(pred_h_sin ** 2 + pred_h_cos ** 2 + 1e-8)
    unit_sin = pred_h_sin / pred_norm
    unit_cos = pred_h_cos / pred_norm
    # Cosine similarity between predicted unit vector and target unit vector
    cos_sim = unit_sin * tgt_h_sin + unit_cos * tgt_h_cos
    loss_hue = torch.mean((1.0 - cos_sim) * (1.0 + 2.0 * is_anchor))

    # 2. Lightness Loss (in [0, 1] sigmoid space)
    pred_l = torch.sigmoid(pred_l_logit)
    loss_l = F.smooth_l1_loss(pred_l, tgt_l, beta=0.05)

    # 3. Chroma Loss (in [0, 1] sigmoid space)
    pred_c = torch.sigmoid(pred_c_logit)
    loss_c = F.smooth_l1_loss(pred_c, tgt_c, beta=0.05)

    # 4. Harmony Classification Loss
    loss_harm = F.cross_entropy(pred_harm_logits, tgt_harm)

    # Total loss
    total_loss = 4.0 * loss_hue + 2.5 * loss_l + 2.0 * loss_c + 0.8 * loss_harm
    metrics = {
        "loss_hue": loss_hue.item(),
        "loss_l": loss_l.item(),
        "loss_c": loss_c.item(),
        "loss_harm": loss_harm.item(),
        "total_loss": total_loss.item(),
    }
    return total_loss, metrics

def evaluate(model: nn.Module, loader: DataLoader) -> dict:
    model.eval()
    total_hue_err_deg = 0.0
    total_l_err = 0.0
    total_samples = 0
    with torch.no_grad():
        for batch in loader:
            pred = model(batch["embedding"])
            pred_sin = pred[:, 1].numpy()
            pred_cos = pred[:, 2].numpy()
            pred_hues = (np.arctan2(pred_sin, pred_cos) * 180.0 / np.pi) % 360.0

            tgt_sin = batch["hue_sin"].numpy()
            tgt_cos = batch["hue_cos"].numpy()
            tgt_hues = (np.arctan2(tgt_sin, tgt_cos) * 180.0 / np.pi) % 360.0

            # Shortest circular angular error
            diff = np.abs(pred_hues - tgt_hues)
            diff = np.minimum(diff, 360.0 - diff)
            total_hue_err_deg += np.sum(diff)

            pred_l = torch.sigmoid(pred[:, 0]).numpy()
            tgt_l = batch["lightness"].numpy()
            total_l_err += np.sum(np.abs(pred_l - tgt_l))

            total_samples += len(pred)

    return {
        "mean_hue_error_deg": total_hue_err_deg / max(1, total_samples),
        "mean_lightness_error": total_l_err / max(1, total_samples),
    }

def main():
    torch.manual_seed(42)
    np.random.seed(42)
    random.seed(42)

    data = np.load(DATA_NPZ, allow_pickle=True)
    embeddings = data["embeddings"]
    hue_sin = data["hue_sin"]
    hue_cos = data["hue_cos"]
    lightnesses = data["lightnesses"]
    chromas = data["chromas"]
    harmonies = data["harmonies"]
    is_anchors = data["is_anchors"]
    groups = data["groups"]

    # Stratified/Group split
    unique_groups = list(set(groups))
    random.shuffle(unique_groups)
    val_cut = int(len(unique_groups) * 0.15)
    val_groups = set(unique_groups[:val_cut])
    train_groups = set(unique_groups[val_cut:])

    train_idx = [i for i, g in enumerate(groups) if g in train_groups]
    val_idx = [i for i, g in enumerate(groups) if g in val_groups]

    print(f"Total samples: {len(embeddings)} (Train: {len(train_idx)}, Val: {len(val_idx)})")

    train_ds = PaletteDataset(
        embeddings[train_idx], hue_sin[train_idx], hue_cos[train_idx],
        lightnesses[train_idx], chromas[train_idx], harmonies[train_idx], is_anchors[train_idx]
    )
    val_ds = PaletteDataset(
        embeddings[val_idx], hue_sin[val_idx], hue_cos[val_idx],
        lightnesses[val_idx], chromas[val_idx], harmonies[val_idx], is_anchors[val_idx]
    )

    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=32, shuffle=False)

    model = PaletteHead(in_dim=384, hidden_dim=128, out_dim=7)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=150, eta_min=1e-5)

    epochs = 150
    best_val_err = float("inf")
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("\nStarting Training...")
    for epoch in range(1, epochs + 1):
        model.train()
        for batch in train_loader:
            optimizer.zero_grad()
            pred = model(batch["embedding"])
            loss, _ = compute_loss(pred, batch)
            loss.backward()
            optimizer.step()
        scheduler.step()

        if epoch % 25 == 0 or epoch == epochs:
            val_eval = evaluate(model, val_loader)
            print(f"Epoch {epoch:03d}/{epochs:03d} | Val Hue Err: {val_eval['mean_hue_error_deg']:.2f}° | Val L Err: {val_eval['mean_lightness_error']:.4f}")
            if val_eval["mean_hue_error_deg"] < best_val_err:
                best_val_err = val_eval["mean_hue_error_deg"]
                torch.save(model.state_dict(), CHECKPOINT_PATH)

    # Load best checkpoint
    model.load_state_dict(torch.load(CHECKPOINT_PATH))
    model.eval()
    print(f"\nTraining Complete! Best Val Hue Error: {best_val_err:.2f}°")

    # Export to ONNX
    ONNX_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dummy_input = torch.randn(1, 384, dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy_input,
        str(ONNX_EXPORT_PATH),
        input_names=["embedding"],
        output_names=["logits"],
        dynamic_axes={"embedding": {0: "batch_size"}, "logits": {0: "batch_size"}},
        opset_version=14
    )
    print(f"ONNX Model successfully exported to: {ONNX_EXPORT_PATH} ({ONNX_EXPORT_PATH.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    main()
