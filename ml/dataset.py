"""
PyTorch Dataset for palette intent prediction.
Loads JSONL records lazily; no pandas / HF datasets.
"""
import json
from pathlib import Path
import torch
from torch.utils.data import Dataset
from tokenizer import load_vocab, tokenize, MAX_LENGTH


class PaletteDataset(Dataset):
    """
    Each record has:
      text, target_L, target_hue_sin, target_hue_cos,
      target_relative_chroma, target_harmony_class, target_absolute_chroma
    """

    def __init__(self, jsonl_path: str | Path, vocab: dict[str, int]) -> None:
        self.vocab = vocab
        self.records: list[dict] = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.records.append(json.loads(line))

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        rec = self.records[idx]
        token_ids = tokenize(rec["text"], self.vocab, MAX_LENGTH)

        return {
            "token_ids": torch.tensor(token_ids, dtype=torch.int64),
            "target_L": torch.tensor(rec["target_L"], dtype=torch.float32),
            "target_hue_sin": torch.tensor(rec["target_hue_sin"], dtype=torch.float32),
            "target_hue_cos": torch.tensor(rec["target_hue_cos"], dtype=torch.float32),
            "target_relative_chroma": torch.tensor(rec["target_relative_chroma"], dtype=torch.float32),
            "target_harmony_class": torch.tensor(rec["target_harmony_class"], dtype=torch.int64),
            "target_absolute_chroma": torch.tensor(rec["target_absolute_chroma"], dtype=torch.float32),
        }
