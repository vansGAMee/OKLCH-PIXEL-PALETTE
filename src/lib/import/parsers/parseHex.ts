/**
 * src/lib/import/parsers/parseHex.ts
 * HEX color list parser — one hex per line, with or without #.
 */
import type { PaletteColor } from '@/types/palette';

interface ParseResult {
  colors: PaletteColor[];
  error?: string;
}

const HEX_RE = /^#?([0-9a-fA-F]{6})$/;

export function parseHex(content: string): ParseResult {
  const lines = content.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);

  const colors: PaletteColor[] = [];

  for (const line of lines) {
    const match = line.match(HEX_RE);
    if (!match) continue;

    const hex = `#${match[1].toLowerCase()}`;
    colors.push({ role: `color_${colors.length}`, hex, oklch: { l: 0.5, c: 0.1, h: null } });

    if (colors.length >= 9) break;
  }

  if (colors.length === 0) {
    return { colors: [], error: 'No valid HEX colors found. Use one color per line (e.g. #a855f7).' };
  }

  return { colors };
}
