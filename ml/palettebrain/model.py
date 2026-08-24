"""Tiny conditional full-palette decoder.

The decoder consumes a cached 384-dimensional text embedding and produces up
to nine interacting color slots. The first four output channels use
``[L_logit, relative_C_logit, sin(H), cos(H)]``; the fifth is a bounded
importance score. Locked inputs are physical ``[L, C, sin(H), cos(H)]`` values.
They condition every slot through self-attention. The browser runtime restores
locked values after decoding as a defense-in-depth immutability guard.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import torch
from torch import Tensor, nn
import torch.nn.functional as F


TEXT_EMBEDDING_DIM = 384
MAX_COLORS = 9
SEED_CHANNELS = 4
LOCKED_COLOR_CHANNELS = 4
OUTPUT_CHANNELS = 5


@dataclass(frozen=True)
class PaletteDecoderConfig:
    embedding_dim: int = TEXT_EMBEDDING_DIM
    max_colors: int = MAX_COLORS
    seed_channels: int = SEED_CHANNELS
    locked_color_channels: int = LOCKED_COLOR_CHANNELS
    d_model: int = 64
    heads: int = 4
    layers: int = 2
    ff_multiplier: int = 2
    dropout: float = 0.0

    def __post_init__(self) -> None:
        if self.max_colors != MAX_COLORS:
            raise ValueError(f"PaletteBrain v1 requires max_colors={MAX_COLORS}")
        if self.embedding_dim != TEXT_EMBEDDING_DIM:
            raise ValueError(
                f"PaletteBrain v1 requires embedding_dim={TEXT_EMBEDDING_DIM}"
            )
        if self.d_model % self.heads != 0:
            raise ValueError("d_model must be divisible by heads")
        if self.layers < 1:
            raise ValueError("layers must be positive")

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


class PaletteSelfAttentionBlock(nn.Module):
    """Small pre-normalized self-attention block with an ONNX-friendly mask."""

    def __init__(self, config: PaletteDecoderConfig) -> None:
        super().__init__()
        self.heads = config.heads
        self.head_dim = config.d_model // config.heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        self.attention_norm = nn.LayerNorm(config.d_model)
        self.qkv = nn.Linear(config.d_model, config.d_model * 3)
        self.attention_output = nn.Linear(config.d_model, config.d_model)
        self.attention_dropout = nn.Dropout(config.dropout)

        hidden_dim = config.d_model * config.ff_multiplier
        self.feed_forward_norm = nn.LayerNorm(config.d_model)
        self.feed_forward = nn.Sequential(
            nn.Linear(config.d_model, hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(hidden_dim, config.d_model),
            nn.Dropout(config.dropout),
        )

    def forward(self, slots: Tensor, count_mask: Tensor) -> Tensor:
        batch_size, slot_count, model_dim = slots.shape
        normalized = self.attention_norm(slots)
        qkv = self.qkv(normalized)
        qkv = qkv.reshape(
            batch_size, slot_count, 3, self.heads, self.head_dim
        ).permute(2, 0, 3, 1, 4)
        query, key, value = qkv.unbind(dim=0)

        scores = torch.matmul(query, key.transpose(-2, -1)) * self.scale
        key_mask = count_mask[:, None, None, :]
        scores = scores.masked_fill(key_mask < 0.5, -10_000.0)
        attention = torch.softmax(scores, dim=-1)
        attended = torch.matmul(attention, value)
        attended = attended.transpose(1, 2).reshape(
            batch_size, slot_count, model_dim
        )

        slots = slots + self.attention_dropout(self.attention_output(attended))
        slots = slots * count_mask.unsqueeze(-1)
        slots = slots + self.feed_forward(self.feed_forward_norm(slots))
        return slots * count_mask.unsqueeze(-1)


class PaletteDecoder(nn.Module):
    """Decode cached text semantics into a complete, lock-aware palette."""

    def __init__(self, config: PaletteDecoderConfig | None = None) -> None:
        super().__init__()
        self.config = config or PaletteDecoderConfig()
        cfg = self.config

        self.query_slots = nn.Parameter(torch.empty(cfg.max_colors, cfg.d_model))
        nn.init.normal_(self.query_slots, mean=0.0, std=0.02)

        self.text_projection = nn.Sequential(
            nn.LayerNorm(cfg.embedding_dim),
            nn.Linear(cfg.embedding_dim, cfg.d_model),
            nn.GELU(),
        )
        self.count_projection = nn.Linear(cfg.max_colors, cfg.d_model)
        self.seed_projection = nn.Linear(cfg.seed_channels, cfg.d_model)
        self.lock_projection = nn.Linear(
            cfg.locked_color_channels + 1, cfg.d_model
        )
        self.blocks = nn.ModuleList(
            PaletteSelfAttentionBlock(cfg) for _ in range(cfg.layers)
        )
        self.output_norm = nn.LayerNorm(cfg.d_model)
        self.output_head = nn.Linear(cfg.d_model, OUTPUT_CHANNELS)

    def _validate_inputs(
        self,
        text_embedding: Tensor,
        count_mask: Tensor,
        seed_noise: Tensor,
        locked_mask: Tensor,
        locked_colors: Tensor,
    ) -> None:
        if text_embedding.ndim != 2 or text_embedding.shape[1] != 384:
            raise ValueError("text_embedding must have shape [B, 384]")
        batch_size = text_embedding.shape[0]
        if count_mask.shape != (batch_size, 9):
            raise ValueError("count_mask must have shape [B, 9]")
        if seed_noise.shape != (batch_size, 9, 4):
            raise ValueError("seed_noise must have shape [B, 9, 4]")
        if locked_mask.shape != (batch_size, 9):
            raise ValueError("locked_mask must have shape [B, 9]")
        if locked_colors.shape != (batch_size, 9, 4):
            raise ValueError("locked_colors must have shape [B, 9, 4]")
        active_counts = count_mask.sum(dim=1)
        if bool(((active_counts < 2) | (active_counts > 9)).any()):
            raise ValueError("each count_mask must activate between 2 and 9 slots")

    def forward(
        self,
        text_embedding: Tensor,
        count_mask: Tensor,
        seed_noise: Tensor,
        locked_mask: Tensor,
        locked_colors: Tensor,
    ) -> Tensor:
        """Return ``palette`` with shape ``[B, 9, 5]``.

        Inactive slots are zero. Locked inputs condition generation, while the
        output remains entirely in the decoder representation. Runtime code
        replaces locked slots with the original physical colors after decode.
        """

        if not torch.jit.is_tracing() and not torch.jit.is_scripting():
            self._validate_inputs(
                text_embedding,
                count_mask,
                seed_noise,
                locked_mask,
                locked_colors,
            )

        active = count_mask.clamp(0.0, 1.0)
        locks = locked_mask.clamp(0.0, 1.0) * active
        batch_size = text_embedding.shape[0]

        slots = self.query_slots.unsqueeze(0).expand(batch_size, -1, -1)
        text_context = self.text_projection(text_embedding).unsqueeze(1)
        count_context = self.count_projection(active).unsqueeze(1)
        seed_context = self.seed_projection(seed_noise)
        effective_locked_colors = locked_colors * locks.unsqueeze(-1)
        lock_context = self.lock_projection(
            torch.cat((effective_locked_colors, locks.unsqueeze(-1)), dim=-1)
        )
        slots = slots + text_context + count_context + seed_context + lock_context
        slots = slots * active.unsqueeze(-1)

        for block in self.blocks:
            slots = block(slots, active)

        raw = self.output_head(self.output_norm(slots))
        predicted_hue = F.normalize(raw[..., 2:4], dim=-1, eps=1e-6)
        output_core = torch.cat((raw[..., 0:2], predicted_hue), dim=-1)
        importance = torch.sigmoid(raw[..., 4:5])
        palette = torch.cat((output_core, importance), dim=-1)
        return palette * active.unsqueeze(-1)

    def count_parameters(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())
