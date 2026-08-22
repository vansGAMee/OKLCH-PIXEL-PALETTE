"""
Deterministic text normalizer. Must match tokenizer.ts byte-for-byte.
"""
import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    return re.sub(r"\s+", " ", text)
