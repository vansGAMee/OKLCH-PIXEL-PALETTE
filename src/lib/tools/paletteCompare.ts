/**
 * paletteCompare.ts
 * Compare two palettes by OKLCH metrics — no value judgements, just description.
 */
import { hexToOklch, normalizeHex } from '@/lib/color/conversions';
import { calculateDeltaE } from '@/lib/color/validation';
import type { OklchColor } from '@/types/palette';

export interface ComparedColor {
  hex: string;
  oklch: OklchColor;
  index: number;
}

export interface PaletteMetrics {
  colors: ComparedColor[];
  lightnessRange: number;
  chromaRange: number;
  hueSpan: number;
  avgChroma: number;
  avgLightness: number;
  uniqueColors: number;
}

export interface PaletteComparison {
  paletteA: PaletteMetrics;
  paletteB: PaletteMetrics;
  /** Average minimum ΔE between each color in A and its nearest in B */
  avgNearestDE: number;
  parseErrorsA: string[];
  parseErrorsB: string[];
}

function parseHex(input: string): { colors: ComparedColor[]; errors: string[] } {
  const tokens = input.replace(/[,;\n\r\t]+/g, ' ').split(/\s+/).map(t => t.trim()).filter(Boolean);
  const colors: ComparedColor[] = [];
  const errors: string[] = [];
  for (const token of tokens) {
    const norm = normalizeHex(token.startsWith('#') ? token : `#${token}`);
    if (!norm) { errors.push(`"${token}" is not a valid hex`); continue; }
    const oklch = hexToOklch(norm);
    if (!oklch) { errors.push(`Cannot convert ${norm}`); continue; }
    colors.push({ hex: norm, oklch, index: colors.length });
  }
  return { colors, errors };
}

function metrics(colors: ComparedColor[]): PaletteMetrics {
  const ls = colors.map(c => c.oklch.l);
  const cs = colors.map(c => c.oklch.c);
  const chromatic = colors.filter(c => c.oklch.c > 0.04 && c.oklch.h !== null);
  const hues = chromatic.map(c => c.oklch.h!).sort((a, b) => a - b);

  let hueSpan = 0;
  if (hues.length >= 2) {
    const gaps = hues.map((h, i) => ((hues[(i + 1) % hues.length] - h) + 360) % 360);
    hueSpan = 360 - Math.max(...gaps);
  }

  return {
    colors,
    lightnessRange: Math.max(...ls) - Math.min(...ls),
    chromaRange: Math.max(...cs) - Math.min(...cs),
    hueSpan,
    avgChroma: cs.reduce((s, c) => s + c, 0) / Math.max(1, cs.length),
    avgLightness: ls.reduce((s, l) => s + l, 0) / Math.max(1, ls.length),
    uniqueColors: colors.length,
  };
}

function avgNearestDE(a: ComparedColor[], b: ComparedColor[]): number {
  if (a.length === 0 || b.length === 0) return 0;
  const dists = a.map(ca => Math.min(...b.map(cb => calculateDeltaE(ca.oklch, cb.oklch))));
  return dists.reduce((s, d) => s + d, 0) / dists.length;
}

export function comparePalettes(inputA: string, inputB: string): PaletteComparison {
  const a = parseHex(inputA);
  const b = parseHex(inputB);
  return {
    paletteA: metrics(a.colors),
    paletteB: metrics(b.colors),
    avgNearestDE: avgNearestDE(a.colors, b.colors),
    parseErrorsA: a.errors,
    parseErrorsB: b.errors,
  };
}
