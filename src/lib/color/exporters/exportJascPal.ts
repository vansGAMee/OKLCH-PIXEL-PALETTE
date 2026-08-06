import { Palette } from '@/types/palette';

/**
 * Generates JASC Palette (.pal) string representation.
 */
export function generateJascPalString(palette: Palette): string {
  if (!palette || (!palette.colors && !palette.base)) {
    return `JASC-PAL\n0100\n0\n`;
  }

  const colors = palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent].filter(Boolean);

  const numColors = colors.length;

  let output = `JASC-PAL\n0100\n${numColors}\n`;

  colors.forEach((col) => {
    const cleanHex = (col.hex || '#000000').replace(/^#/, '');
    const r = parseInt(cleanHex.slice(0, 2), 16) || 0;
    const g = parseInt(cleanHex.slice(2, 4), 16) || 0;
    const b = parseInt(cleanHex.slice(4, 6), 16) || 0;
    output += `${r} ${g} ${b}\n`;
  });

  return output;
}
