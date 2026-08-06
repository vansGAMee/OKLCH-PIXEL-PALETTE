import { Palette } from '@/types/palette';

/**
 * Generates HEX Code List (.hex) string representation.
 */
export function generateHexListString(palette: Palette): string {
  if (!palette || (!palette.colors && !palette.base)) {
    return '';
  }

  const colors = palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent].filter(Boolean);

  return colors.map((c) => (c.hex || '#000000').toUpperCase()).join('\n') + '\n';
}
