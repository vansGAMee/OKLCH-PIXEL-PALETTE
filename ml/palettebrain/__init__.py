"""PaletteBrain 2 experimental decoder training package.

No production weights are bundled. Model imports are lazy so NumPy-only data
preparation and benchmark validation still work where PyTorch is unavailable.
"""

from typing import Any

__all__ = ["PaletteDecoder", "PaletteDecoderConfig"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .model import PaletteDecoder, PaletteDecoderConfig

        return {
            "PaletteDecoder": PaletteDecoder,
            "PaletteDecoderConfig": PaletteDecoderConfig,
        }[name]
    raise AttributeError(name)
