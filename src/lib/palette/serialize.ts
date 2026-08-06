/**
 * src/lib/palette/serialize.ts
 * Converts frontend Palette type to database-safe JSONB format.
 */
import { Palette } from '@/types/palette';
import { Json } from '@/lib/supabase/types';

export function serializePaletteColors(palette: Palette): Json {
  return palette.colors.map((c) => ({
    role: c.role,
    hex: c.hex,
    oklch: {
      l: c.oklch.l,
      c: c.oklch.c,
      h: c.oklch.h,
    },
  })) as Json;
}

export function generateSlug(title: string, existingSlugs: string[] = []): string {
  const base = title
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);

  if (!existingSlugs.includes(base)) return base;

  // Append random suffix if slug is taken
  const suffix = Math.random().toString(36).slice(2, 7);
  return `${base}-${suffix}`;
}
