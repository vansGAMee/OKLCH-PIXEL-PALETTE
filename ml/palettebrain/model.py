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
    histogram_bins: int = 390
    visual_latent_dim: int = 128
    max_colors: int = MAX_COLORS
    seed_channels: int = SEED_CHANNELS
    locked_color_channels: int = LOCKED_COLOR_CHANNELS
    d_model: int = 64
    heads: int = 4
    layers: int = 2
    ff_multiplier: int = 2
    dropout: float = 0.0
    visual_conditioning: str = "legacy_mean"
    auxiliary_conditioning_scale: float = 1.0

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
        if self.visual_conditioning not in {"legacy_mean", "slot_cross_attention"}:
            raise ValueError(
                "visual_conditioning must be legacy_mean or slot_cross_attention"
            )
        if not 0.0 < self.auxiliary_conditioning_scale <= 1.0:
            raise ValueError("auxiliary_conditioning_scale must be in (0, 1]")

    def to_dict(self) -> dict[str, int | float | str]:
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


class VisualPaletteBridge(nn.Module):
    """Visual Palette Bridge: maps E5 text embedding to Color Distribution Prior and Visual Style Latent."""

    def __init__(
        self,
        embedding_dim: int = TEXT_EMBEDDING_DIM,
        histogram_bins: int = 390,
        style_latent_dim: int = 128,
        d_model: int = 64,
    ) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(embedding_dim)
        self.fc_in = nn.Linear(embedding_dim, 256)
        self.act = nn.GELU()

        # Residual Block 1
        self.res1_fc1 = nn.Linear(256, 256)
        self.res1_fc2 = nn.Linear(256, 256)

        # Residual Block 2
        self.res2_fc1 = nn.Linear(256, 256)
        self.res2_fc2 = nn.Linear(256, 256)

        # Output Heads
        self.color_prior_head = nn.Linear(256, histogram_bins)
        self.style_latent_head = nn.Linear(256, style_latent_dim)

        # Conditioning projections to PaletteDecoder
        self.prior_proj = nn.Linear(histogram_bins, 4 * d_model)
        self.style_proj = nn.Linear(style_latent_dim, d_model)

        # Zero-initialize the conditioning projections so at initialization, C11 matches base exactly
        nn.init.zeros_(self.prior_proj.weight)
        nn.init.zeros_(self.prior_proj.bias)
        nn.init.zeros_(self.style_proj.weight)
        nn.init.zeros_(self.style_proj.bias)

    def forward(
        self, text_embedding: Tensor
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        """Return (prior_logits, style_latent, color_tokens, style_token)."""
        x = self.act(self.fc_in(self.norm(text_embedding)))
        x = x + self.res1_fc2(self.act(self.res1_fc1(x)))
        x = x + self.res2_fc2(self.act(self.res2_fc1(x)))

        prior_logits = self.color_prior_head(x)
        style_latent = self.style_latent_head(x)

        prior_probs = F.softmax(prior_logits, dim=-1)
        b_size = text_embedding.shape[0]
        color_tokens = self.prior_proj(prior_probs).view(b_size, 4, -1)
        style_token = self.style_proj(style_latent).view(b_size, 1, -1)

        return prior_logits, style_latent, color_tokens, style_token


class PaletteVisualCrossAttention(nn.Module):
    """Tiny slot-to-visual-token attention with an ONNX-friendly implementation.

    The output projection is near-zero initialized. A repaired Candidate 11
    therefore starts extremely close to its inherited decoder behavior while
    gradients can immediately break the legacy identical-token symmetry.
    """

    def __init__(self, config: PaletteDecoderConfig) -> None:
        super().__init__()
        self.heads = config.heads
        self.head_dim = config.d_model // config.heads
        self.scale = 1.0 / math.sqrt(self.head_dim)
        self.slot_norm = nn.LayerNorm(config.d_model)
        self.visual_norm = nn.LayerNorm(config.d_model)
        self.query = nn.Linear(config.d_model, config.d_model)
        self.key = nn.Linear(config.d_model, config.d_model)
        self.value = nn.Linear(config.d_model, config.d_model)
        self.output = nn.Linear(config.d_model, config.d_model)
        self.token_identity = nn.Parameter(torch.empty(4, config.d_model))
        nn.init.normal_(self.token_identity, mean=0.0, std=0.02)
        nn.init.normal_(self.output.weight, mean=0.0, std=1e-4)
        nn.init.zeros_(self.output.bias)

    def forward(self, slots: Tensor, visual_tokens: Tensor) -> tuple[Tensor, Tensor]:
        batch_size, slot_count, model_dim = slots.shape
        visual_count = visual_tokens.shape[1]
        query = self.query(self.slot_norm(slots)).reshape(
            batch_size, slot_count, self.heads, self.head_dim
        ).transpose(1, 2)
        visual_tokens = visual_tokens + self.token_identity.unsqueeze(0)
        normalized_visual = self.visual_norm(visual_tokens)
        key = self.key(normalized_visual).reshape(
            batch_size, visual_count, self.heads, self.head_dim
        ).transpose(1, 2)
        value = self.value(normalized_visual).reshape(
            batch_size, visual_count, self.heads, self.head_dim
        ).transpose(1, 2)
        attention = torch.softmax(
            torch.matmul(query, key.transpose(-2, -1)) * self.scale, dim=-1
        )
        attended = torch.matmul(attention, value).transpose(1, 2).reshape(
            batch_size, slot_count, model_dim
        )
        return self.output(attended), attention


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
        self.bridge = VisualPaletteBridge(
            cfg.embedding_dim,
            cfg.histogram_bins,
            cfg.visual_latent_dim,
            cfg.d_model,
        )
        self.visual_cross_attention = (
            PaletteVisualCrossAttention(cfg)
            if cfg.visual_conditioning == "slot_cross_attention"
            else None
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
        
        _, _, color_tokens, style_token = self.bridge(text_embedding)
        if self.visual_cross_attention is None:
            # Compatibility path for the already-trained broken C11 checkpoint.
            # New/repaired C11 training must select slot_cross_attention.
            visual_color_context = color_tokens.mean(dim=1, keepdim=True)
        else:
            slot_visual_context, _ = self.visual_cross_attention(slots, color_tokens)
            visual_color_context = (
                color_tokens.mean(dim=1, keepdim=True) + slot_visual_context
            )
        visual_style_context = style_token

        auxiliary_scale = self.config.auxiliary_conditioning_scale
        count_context = self.count_projection(active).unsqueeze(1) * auxiliary_scale
        seed_context = self.seed_projection(seed_noise) * auxiliary_scale
        effective_locked_colors = locked_colors * locks.unsqueeze(-1)
        lock_context = self.lock_projection(
            torch.cat((effective_locked_colors, locks.unsqueeze(-1)), dim=-1)
        )
        slots = (
            slots
            + text_context
            + visual_color_context
            + visual_style_context
            + count_context
            + seed_context
            + lock_context
        )
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

    @torch.no_grad()
    def visual_attention_weights(self, text_embedding: Tensor) -> Tensor | None:
        """Return mean-over-head per-slot visual attention for diagnostics."""

        if self.visual_cross_attention is None:
            return None
        batch_size = text_embedding.shape[0]
        slots = self.query_slots.unsqueeze(0).expand(batch_size, -1, -1)
        _, _, color_tokens, _ = self.bridge(text_embedding)
        _, attention = self.visual_cross_attention(slots, color_tokens)
        return attention.mean(dim=1)


def load_inherited_state(
    model: PaletteDecoder,
    inherited_state: dict[str, Tensor],
    *,
    allowed_missing_prefixes: tuple[str, ...] = ("bridge.", "visual_cross_attention."),
    allowed_unexpected_prefixes: tuple[str, ...] = ("visual_adapter.",),
) -> tuple[list[str], list[str]]:
    """Load all compatible inherited weights and reject accidental decoder loss."""

    compatible = {
        name: value
        for name, value in inherited_state.items()
        if name in model.state_dict() and model.state_dict()[name].shape == value.shape
    }
    result = model.load_state_dict(compatible, strict=False)
    missing = list(result.missing_keys)
    unexpected = [
        name for name in inherited_state if name not in compatible
    ]
    bad_missing = [
        name
        for name in missing
        if not name.startswith(allowed_missing_prefixes)
    ]
    bad_unexpected = [
        name
        for name in unexpected
        if not name.startswith(allowed_unexpected_prefixes)
    ]
    print(f"missing inherited keys: {missing}")
    print(f"unexpected inherited keys: {unexpected}")
    if bad_missing or bad_unexpected:
        raise RuntimeError(
            "inherited decoder load lost major blocks: "
            f"missing={bad_missing}, unexpected={bad_unexpected}"
        )
    return missing, unexpected
