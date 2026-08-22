# ML Pipeline

Character CNN trained on synthetic RU/EN text → palette intent.

## Setup

```bash
cd ml
python3 -m venv .venv
source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install onnx onnxruntime numpy
```

## Pipeline

```bash
# 1. Generate dataset
python generate_dataset.py --samples 40000 --out ml/data

# 2. Smoke train (verify forward/backward)
python train.py --smoke --data-dir ml/data/smoke

# 3. Full train
python train.py --data-dir ml/data --epochs 15 --batch-size 128

# 4. Export ONNX
python export_onnx.py

# 5. Disk check
python check_disk_budget.py
```

## Architecture

- Input: int64 [batch, 96] Unicode code points
- Embedding: dim=48, padding_idx=0
- Conv1D branches: kernel 3,5,7, channels=64 each, GELU
- Masked global max+mean pooling per branch
- Concat → LayerNorm → Linear(384→128) → GELU → Dropout(0.1) → Linear(128→7)
- Parameters: ~200K

## Output Schema

| Index | Name | Description |
|-------|------|-------------|
| 0 | lightness_logit | sigmoid → [L_MIN, L_MAX] |
| 1 | hue_sin_raw | L2-normalized with hue_cos → sin(H) |
| 2 | hue_cos_raw | L2-normalized with hue_sin → cos(H) |
| 3 | relative_chroma_logit | sigmoid → [0, 1] |
| 4 | splitComplementary | harmony logit |
| 5 | complementary | harmony logit |
| 6 | analogous | harmony logit |

## Tokenizer

- 0 = PAD, 1 = UNK
- NFKC normalize → lowercase → trim → collapse whitespace
- Max 96 Unicode code points (Array.from() in browser)
- Shared vocab: public/models/paletta-v1.vocab.json
