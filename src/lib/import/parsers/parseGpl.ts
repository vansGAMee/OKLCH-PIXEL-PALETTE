/**
 * src/lib/import/parsers/parseGpl.ts
 * GIMP Palette (.gpl) format parser.
 * Spec: https://docs.gimp.org/2.10/en/gimp-concepts-palettes.html
 */
import type { PaletteColor } from '@/types/palette';

interface ParseResult {
  colors: PaletteColor[];
  name?: string;
  error?: string;
}

export function parseGpl(content: string): ParseResult {
  const lines = content.split(/\r?\n/).map((l) => l.trim());

  // Validate header
  if (lines[0] !== 'GIMP Palette') {
    return { colors: [], error: 'Not a valid GIMP Palette file (missing GIMP Palette header)' };
  }

  const colors: PaletteColor[] = [];
  let name: string | undefined;

  for (const line of lines.slice(1)) {
    if (!line || line.startsWith('#')) continue;

    if (line.startsWith('Name:')) {
      name = line.slice(5).trim();
      continue;
    }

    if (line.startsWith('Columns:') || line.startsWith('Columns :')) continue;

    // Color line: "R G B [name]"
    const match = line.match(/^(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})(?:\s+(.+))?$/);
    if (!match) continue;

    const r = parseInt(match[1], 10);
    const g = parseInt(match[2], 10);
    const b = parseInt(match[3], 10);
    const role = match[4]?.trim() ?? `color_${colors.length}`;

    if ([r, g, b].some((v) => isNaN(v) || v < 0 || v > 255)) continue;

    const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    colors.push({ role: role.toLowerCase().replace(/\s+/g, '_'), hex, oklch: { l: 0.5, c: 0.1, h: null } });
  }

  if (colors.length === 0) return { colors: [], error: 'No colors found in GPL file' };
  if (colors.length > 9) return { colors: colors.slice(0, 9), name, error: undefined }; // truncate to max

  return { colors, name };
}
