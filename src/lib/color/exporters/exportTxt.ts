import { Palette } from '@/types/palette';
import { getPaletteColorLabel } from '../colorNaming';

/**
 * Generates Plain Text (.txt) string representation.
 */
export function generateTxtString(palette: Palette, locale: 'en' | 'ru' = 'en'): string {
  if (!palette || (!palette.colors && !palette.base)) {
    return 'Palette: Empty\n';
  }

  const colors = palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent].filter(Boolean);

  const numColors = colors.length;
  const isRu = locale === 'ru';
  const title = isRu ? 'Палитра OKLCH Pixel Palette' : 'OKLCH Pixel Palette Breakdown';
  const harmonyLabel = isRu ? 'Гармония' : 'Harmony';
  const colorsLabel = isRu ? 'Количество цветов' : 'Total Colors';

  let output = `${title}\n`;
  output += `${colorsLabel}: ${numColors}\n`;
  output += `${harmonyLabel}: ${palette.harmony.toUpperCase()}\n`;
  output += `----------------------------------------\n\n`;

  colors.forEach((col, idx) => {
    const label = getPaletteColorLabel(col.role, idx, numColors, col.oklch);
    const hex = (col.hex || '#000000').toUpperCase();
    const l = col.oklch.l.toFixed(4);
    const c = col.oklch.c.toFixed(4);
    const h = col.oklch.h !== null ? col.oklch.h.toFixed(2) + '°' : 'neutral';

    output += `${idx + 1}. ${label}\n`;
    output += `   HEX:   ${hex}\n`;
    output += `   OKLCH: oklch(${l} ${c} ${h})\n\n`;
  });

  return output;
}
