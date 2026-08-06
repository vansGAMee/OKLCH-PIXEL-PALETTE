/**
 * src/lib/import/parsers/parsePal.ts
 * JASC Paint Shop Pro Palette (.pal) format parser.
 */
import type { PaletteColor } from '@/types/palette';

interface ParseResult {
  colors: PaletteColor[];
  error?: string;
}

export function parsePal(content: string): ParseResult {
  const lines = content.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);

  if (lines[0] !== 'JASC-PAL') {
    return { colors: [], error: 'Not a valid JASC PAL file (missing JASC-PAL header)' };
  }

  if (lines[1] !== '0100') {
    return { colors: [], error: 'Unsupported JASC PAL version (expected 0100)' };
  }

  const declaredCount = parseInt(lines[2], 10);
  if (isNaN(declaredCount) || declaredCount < 1) {
    return { colors: [], error: 'Invalid color count in PAL file' };
  }

  const colors: PaletteColor[] = [];

  for (let i = 3; i < lines.length && colors.length < Math.min(declaredCount, 9); i++) {
    const parts = lines[i].split(/\s+/);
    if (parts.length < 3) continue;

    const r = parseInt(parts[0], 10);
    const g = parseInt(parts[1], 10);
    const b = parseInt(parts[2], 10);

    if ([r, g, b].some((v) => isNaN(v) || v < 0 || v > 255)) continue;

    const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    colors.push({ role: `color_${colors.length}`, hex, oklch: { l: 0.5, c: 0.1, h: null } });
  }

  if (colors.length === 0) return { colors: [], error: 'No colors found in PAL file' };

  return { colors };
}
