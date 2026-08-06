import { Palette } from '@/types/palette';
import { getPaletteColorLabel } from '../colorNaming';

/**
 * Generates GIMP Palette (.gpl) string representation.
 */
export function generateGplString(palette: Palette, _locale: 'en' | 'ru' = 'en'): string {
  if (!palette || (!palette.colors && !palette.base)) {
    return 'GIMP Palette\nName: Empty Palette\nColumns: 0\n#\n';
  }

  const colors = palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent].filter(Boolean);

  const numColors = colors.length;
  const paletteName = `OKLCH Palette (${numColors} Colors)`;

  let output = `GIMP Palette\n`;
  output += `Name: ${paletteName}\n`;
  output += `Columns: ${numColors}\n`;
  output += `#\n`;

  colors.forEach((col, idx) => {
    const label = getPaletteColorLabel(col.role, idx, numColors, col.oklch);
    const cleanHex = (col.hex || '#000000').replace(/^#/, '');
    const r = parseInt(cleanHex.slice(0, 2), 16) || 0;
    const g = parseInt(cleanHex.slice(2, 4), 16) || 0;
    const b = parseInt(cleanHex.slice(4, 6), 16) || 0;

    const rStr = r.toString().padStart(3, ' ');
    const gStr = g.toString().padStart(3, ' ');
    const bStr = b.toString().padStart(3, ' ');

    output += `${rStr} ${gStr} ${bStr}\t${label}\n`;
  });

  return output;
}
