"""Pinned CUDA embedding path compatible with the shipped E5 browser encoder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer


E5_MODEL_ID = "intfloat/multilingual-e5-small"
E5_REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
BROWSER_E5_MODEL_ID = "Xenova/multilingual-e5-small"
BROWSER_E5_REVISION = "ae61bf0193ce3851dc8a45147e459b04ed783d8a"
BROWSER_E5_SHA256 = (
    "f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193"
)
EMBEDDING_DIMENSION = 384
MAX_CONTEXT_TOKENS = 512
QUERY_PREFIX = "query: "


@dataclass(frozen=True)
class E5Encoder:
    tokenizer: object
    model: torch.nn.Module
    device: torch.device


def choose_device(requested: str = "auto") -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return device


def load_encoder(
    *,
    device: str = "auto",
    cache_dir: str | Path = "ml/.cache/hub",
    local_files_only: bool = True,
) -> E5Encoder:
    """Load the exact pinned upstream checkpoint used by the q8 browser export."""

    resolved_device = choose_device(device)
    tokenizer = AutoTokenizer.from_pretrained(
        E5_MODEL_ID,
        revision=E5_REVISION,
        cache_dir=str(cache_dir),
        local_files_only=local_files_only,
    )
    model = AutoModel.from_pretrained(
        E5_MODEL_ID,
        revision=E5_REVISION,
        cache_dir=str(cache_dir),
        local_files_only=local_files_only,
    )
    model.to(resolved_device).eval()
    return E5Encoder(tokenizer=tokenizer, model=model, device=resolved_device)


@torch.inference_mode()
def embed_texts(
    texts: Sequence[str],
    *,
    encoder: E5Encoder,
    batch_size: int = 128,
) -> np.ndarray:
    """Embed text with the production prefix/truncation/pooling/normalization contract."""

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    normalized = [str(text).strip() for text in texts]
    if any(not text for text in normalized):
        raise ValueError("embedding text must be non-empty")
    if not normalized:
        return np.empty((0, EMBEDDING_DIMENSION), dtype=np.float32)

    chunks: list[np.ndarray] = []
    for start in range(0, len(normalized), batch_size):
        batch = [QUERY_PREFIX + text for text in normalized[start : start + batch_size]]
        encoded = encoder.tokenizer(  # type: ignore[operator]
            batch,
            padding=True,
            truncation=True,
            max_length=MAX_CONTEXT_TOKENS,
            return_tensors="pt",
        )
        model_inputs = {
            name: value.to(encoder.device) for name, value in encoded.items()
        }
        output = encoder.model(**model_inputs)  # type: ignore[operator]
        hidden = output.last_hidden_state
        attention = model_inputs["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * attention).sum(dim=1) / attention.sum(dim=1).clamp_min(1)
        embeddings = F.normalize(pooled, p=2, dim=1)
        chunks.append(embeddings.float().cpu().numpy())

    result = np.concatenate(chunks, axis=0).astype(np.float32, copy=False)
    if result.shape != (len(normalized), EMBEDDING_DIMENSION):
        raise RuntimeError(f"unexpected E5 output shape {result.shape}")
    if not np.isfinite(result).all():
        raise RuntimeError("E5 produced a non-finite embedding")
    return result


def parity_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    """Compare two normalized embedding matrices without hiding outliers."""

    reference = np.asarray(reference, dtype=np.float32)
    candidate = np.asarray(candidate, dtype=np.float32)
    if reference.shape != candidate.shape or reference.ndim != 2:
        raise ValueError("parity matrices must have the same [N, D] shape")
    reference = reference / np.maximum(
        np.linalg.norm(reference, axis=1, keepdims=True), 1e-8
    )
    candidate = candidate / np.maximum(
        np.linalg.norm(candidate, axis=1, keepdims=True), 1e-8
    )
    cosine = np.sum(reference * candidate, axis=1)
    error = np.abs(reference - candidate)
    return {
        "meanCosine": float(cosine.mean()),
        "minimumCosine": float(cosine.min()),
        "meanAbsoluteError": float(error.mean()),
        "maximumAbsoluteError": float(error.max()),
    }
