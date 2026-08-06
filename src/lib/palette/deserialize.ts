/**
 * src/lib/palette/deserialize.ts
 * Converts database JSONB format back to frontend Palette type.
 */
import { Palette, PaletteColor } from '@/types/palette';
import { Json } from '@/lib/supabase/types';
import { PaletteRow } from '@/lib/supabase/types';

function parseColorFromJson(raw: Json): PaletteColor | null {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return null;
  const obj = raw as Record<string, Json>;
  if (
    typeof obj.role !== 'string' ||
    typeof obj.hex !== 'string' ||
    typeof obj.oklch !== 'object' ||
    obj.oklch === null
  ) return null;

  const oklch = obj.oklch as Record<string, Json>;
  return {
    role: obj.role,
    hex: obj.hex,
    oklch: {
      l: typeof oklch.l === 'number' ? oklch.l : 0.5,
      c: typeof oklch.c === 'number' ? oklch.c : 0.1,
      h: typeof oklch.h === 'number' ? oklch.h : null,
    },
  };
}

export function deserializePaletteRow(row: PaletteRow): Palette | null {
  try {
    const rawColors = row.colors;
    if (!Array.isArray(rawColors) || rawColors.length < 2) return null;

    const colors: PaletteColor[] = rawColors
      .map((c) => parseColorFromJson(c))
      .filter((c): c is PaletteColor => c !== null);

    if (colors.length < 2) return null;

    const shadow = colors.find((c) => c.role === 'shadow') ?? colors[0];
    const base = colors.find((c) => c.role === 'base') ?? colors[1] ?? colors[0];
    const highlight = colors.find((c) => c.role === 'highlight') ?? colors[colors.length - 1] ?? base;
    const accent = colors.find((c) => c.role === 'accent') ?? highlight;

    return {
      colors,
      count: colors.length,
      shadow,
      base,
      highlight,
      accent,
      harmony: (row.harmony as Palette['harmony']) ?? 'splitComplementary',
      seed: row.seed ?? 0,
    };
  } catch {
    return null;
  }
}
