/**
 * src/lib/import/parsers/parseJson.ts
 * Parses the site's own JSON palette export format.
 */
import type { PaletteColor } from '@/types/palette';

interface ParseResult {
  colors: PaletteColor[];
  name?: string;
  harmony?: string;
  seed?: number;
  error?: string;
}

const HEX_RE = /^#[0-9a-fA-F]{6}$/;

export function parseJson(content: string): ParseResult {
  let data: unknown;

  try {
    data = JSON.parse(content);
  } catch {
    return { colors: [], error: 'Invalid JSON' };
  }

  if (typeof data !== 'object' || data === null) {
    return { colors: [], error: 'JSON must be an object' };
  }

  const obj = data as Record<string, unknown>;

  // Support site's own export format: { name?, harmony?, seed?, colors: [{role, hex, oklch}] }
  if (!Array.isArray(obj.colors)) {
    return { colors: [], error: 'JSON must have a "colors" array' };
  }

  const colors: PaletteColor[] = [];

  for (const item of obj.colors) {
    if (typeof item !== 'object' || item === null) continue;
    const c = item as Record<string, unknown>;

    if (typeof c.hex !== 'string' || !HEX_RE.test(c.hex)) continue;

    const oklch = typeof c.oklch === 'object' && c.oklch !== null
      ? c.oklch as { l?: number; c?: number; h?: number | null }
      : {};

    colors.push({
      role: typeof c.role === 'string' ? c.role : `color_${colors.length}`,
      hex: c.hex,
      oklch: {
        l: typeof oklch.l === 'number' ? Math.max(0, Math.min(1, oklch.l)) : 0.5,
        c: typeof oklch.c === 'number' ? Math.max(0, Math.min(0.4, oklch.c)) : 0.1,
        h: typeof oklch.h === 'number' ? oklch.h : null,
      },
    });

    if (colors.length >= 9) break;
  }

  if (colors.length < 2) {
    return { colors: [], error: 'JSON palette must have at least 2 valid colors' };
  }

  return {
    colors,
    name: typeof obj.name === 'string' ? obj.name : undefined,
    harmony: typeof obj.harmony === 'string' ? obj.harmony : undefined,
    seed: typeof obj.seed === 'number' ? obj.seed : undefined,
  };
}
