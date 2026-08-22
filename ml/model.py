"""
Character CNN for palette intent prediction.
Input: int64 [batch, 96]
Output: float32 [batch, 7]
  0: lightness_logit
  1: hue_sin_raw
  2: hue_cos_raw
  3: relative_chroma_logit
  4: harmony_splitComplementary_logit
  5: harmony_complementary_logit
  6: harmony_analogous_logit
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

PAD_ID = 0


class CharCNN(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        embed_dim: int = 48,
        conv_channels: int = 64,
        hidden_dim: int = 128,
        max_length: int = 96,
        dropout: float = 0.10,
    ) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=PAD_ID)
        self.max_length = max_length

        # Parallel conv branches
        self.conv3 = nn.Conv1d(embed_dim, conv_channels, kernel_size=3, padding=1)
        self.conv5 = nn.Conv1d(embed_dim, conv_channels, kernel_size=5, padding=2)
        self.conv7 = nn.Conv1d(embed_dim, conv_channels, kernel_size=7, padding=3)

        merged_dim = conv_channels * 3 * 2  # 3 branches × (max+mean)
        self.norm = nn.LayerNorm(merged_dim)
        self.fc1 = nn.Linear(merged_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(hidden_dim, 7)

    def _masked_pool(
        self,
        x: torch.Tensor,         # [B, C, L]
        mask: torch.Tensor,       # [B, L] True=valid
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Returns (masked_max, masked_mean) each [B, C].
        """
        mask_f = mask.float().unsqueeze(1)   # [B, 1, L]

        # Max pool: mask invalid positions to -1e9
        x_max = x + (1.0 - mask_f) * (-1e9)
        pooled_max, _ = x_max.max(dim=2)     # [B, C]

        # Mean pool: zero invalid, divide by valid count
        x_mean = x * mask_f
        valid_count = mask_f.sum(dim=2).clamp(min=1.0)  # [B, 1]
        pooled_mean = x_mean.sum(dim=2) / valid_count    # [B, C]

        return pooled_max, pooled_mean

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        """
        token_ids: int64 [B, L]
        returns: float32 [B, 7]
        """
        mask = (token_ids != PAD_ID)    # [B, L]

        emb = self.embed(token_ids)     # [B, L, E]
        emb = emb.transpose(1, 2)      # [B, E, L]

        # Three parallel branches
        c3 = F.gelu(self.conv3(emb))   # [B, C, L]
        c5 = F.gelu(self.conv5(emb))   # [B, C, L]
        c7 = F.gelu(self.conv7(emb))   # [B, C, L]

        max3, mean3 = self._masked_pool(c3, mask)
        max5, mean5 = self._masked_pool(c5, mask)
        max7, mean7 = self._masked_pool(c7, mask)

        merged = torch.cat([max3, mean3, max5, mean5, max7, mean7], dim=1)
        merged = self.norm(merged)

        h = F.gelu(self.fc1(merged))
        h = self.dropout(h)
        return self.fc2(h)

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
