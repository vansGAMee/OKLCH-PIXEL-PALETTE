import { Palette } from '@/types/palette';
import { getPaletteColorLabel } from '../colorNaming';

/**
 * Generates Structured JSON (.json) string representation.
 */
export function generateJsonString(palette: Palette, _locale: 'en' | 'ru' = 'en'): string {
  if (!palette || (!palette.colors && !palette.base)) {
    return JSON.stringify({ name: 'Empty Palette', colorSpace: 'OKLCH', colors: [] }, null, 2);
  }

  const colors = palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent].filter(Boolean);

  const numColors = colors.length;

  const data = {
    name: `OKLCH Pixel Palette (${numColors} Colors)`,
    colorSpace: 'OKLCH',
    harmony: palette.harmony,
    seed: palette.seed,
    colors: colors.map((col, idx) => ({
      name: getPaletteColorLabel(col.role, idx, numColors, col.oklch),
      role: col.role,
      hex: (col.hex || '#000000').toUpperCase(),
      oklch: {
        l: Number(col.oklch.l.toFixed(4)),
        c: Number(col.oklch.c.toFixed(4)),
        h: col.oklch.h !== null ? Number(col.oklch.h.toFixed(2)) : null,
      },
    })),
  };

  return JSON.stringify(data, null, 2);
}
