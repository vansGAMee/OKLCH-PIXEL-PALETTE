"""
Unicode code-point tokenizer.
Vocabulary: 0=PAD, 1=UNK, 2..N=character code points.
Shared between Python training and TypeScript inference via paletta-v1.vocab.json.
"""
import json
import unicodedata
import re
from pathlib import Path
from normalize import normalize_text

MAX_LENGTH = 96
PAD_ID = 0
UNK_ID = 1

# Characters: Russian, English, digits, space, basic punctuation
_BASE_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    "0123456789"
    " -_.,!?'\"()"
)


def build_vocab(extra_chars: str = "") -> dict[str, int]:
    """Build vocabulary from base chars + extras. 0=PAD, 1=UNK."""
    seen: dict[str, int] = {}
    idx = 2  # 0=PAD, 1=UNK
    for ch in (_BASE_CHARS + extra_chars):
        if ch not in seen:
            seen[ch] = idx
            idx += 1
    return seen


def save_vocab(vocab: dict[str, int], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)


def load_vocab(path: str) -> dict[str, int]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def tokenize(text: str, vocab: dict[str, int], max_length: int = MAX_LENGTH) -> list[int]:
    normalized = normalize_text(text)
    chars = list(normalized)[:max_length]
    ids = [vocab.get(ch, UNK_ID) for ch in chars]
    # Pad
    ids += [PAD_ID] * (max_length - len(ids))
    return ids


def batch_tokenize(texts: list[str], vocab: dict[str, int], max_length: int = MAX_LENGTH) -> list[list[int]]:
    return [tokenize(t, vocab, max_length) for t in texts]
