import { Palette, PaletteColor } from '@/types/palette';
import { getPaletteColorLabel } from '../colorNaming';

function getColors(palette: Palette): PaletteColor[] {
  if (!palette || (!palette.colors && !palette.base)) return [];
  return palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent].filter(Boolean);
}

function tokenKey(color: PaletteColor, index: number, count: number): string {
  const label = getPaletteColorLabel(color.role, index, count, color.oklch)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return label || `color-${index + 1}`;
}

/**
 * Generates Tailwind CSS configuration object snippet or W3C Design Tokens JSON.
 */
export function generateTailwindConfigString(palette: Palette): string {
  const colors = getColors(palette);
  if (colors.length === 0) return '{\n  "colors": {}\n}\n';

  const tokenObj: Record<string, string> = {};
  colors.forEach((col, idx) => {
    const key = tokenKey(col, idx, colors.length);
    tokenObj[key] = (col.hex || '#000000').toUpperCase();
  });

  return JSON.stringify({ theme: { extend: { colors: { palette: tokenObj } } } }, null, 2);
}

/**
 * Generates W3C Community Group Design Tokens format.
 */
export function generateDesignTokensJson(palette: Palette): string {
  const colors = getColors(palette);
  if (colors.length === 0) return '{\n  "color": {}\n}\n';

  const tokens: Record<string, { $value: string; $type: string; $description: string }> = {};
  colors.forEach((col, idx) => {
    const key = tokenKey(col, idx, colors.length);
    tokens[key] = {
      $value: (col.hex || '#000000').toUpperCase(),
      $type: 'color',
      $description: `OKLCH: L=${(col.oklch.l * 100).toFixed(1)}% C=${col.oklch.c.toFixed(3)} H=${col.oklch.h !== null ? col.oklch.h.toFixed(1) : 'none'}`,
    };
  });

  return JSON.stringify({ color: tokens }, null, 2);
}
