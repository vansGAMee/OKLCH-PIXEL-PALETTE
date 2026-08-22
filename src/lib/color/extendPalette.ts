/**
 * extendPalette.ts
 * Deterministically extends a 4-color Palette to 4–9 display colors.
 * - count === 4: return original anchors unchanged
 * - count 5–9: derive additional colors by OKLCH interpolation + max-min ΔE selection
 */
import type { Palette, PaletteColor, OklchColor } from '@/types/palette';
import { fitToSrgb } from '@/lib/color/gamut';
import { oklchToHex, hexToOklch } from '@/lib/color/conversions';
import { calculateDeltaE } from '@/lib/color/validation';

export interface DisplayPaletteColor {
  id: string;
  label: string;
  hex: string;
  oklch: OklchColor;
  anchorRole?: 'shadow' | 'base' | 'highlight' | 'accent';
  derived: boolean;
}

function paletteColorToDisplay(
  pc: PaletteColor,
  anchorRole: 'shadow' | 'base' | 'highlight' | 'accent',
): DisplayPaletteColor {
  return {
    id: anchorRole,
    label: anchorRole.charAt(0).toUpperCase() + anchorRole.slice(1),
    hex: pc.hex,
    oklch: pc.oklch,
    anchorRole,
    derived: false,
  };
}

/** Shortest circular arc interpolation of hue in degrees. */
function lerpHue(h1: number | null, h2: number | null, t: number): number | null {
  if (h1 === null && h2 === null) return null;
  const a = h1 ?? h2!;
  const b = h2 ?? h1!;
  let diff = ((b - a) + 360) % 360;
  if (diff > 180) diff -= 360;
  return ((a + diff * t) + 360) % 360;
}

function lerpOklch(a: OklchColor, b: OklchColor, t: number): OklchColor {
  return {
    l: a.l + (b.l - a.l) * t,
    c: a.c + (b.c - a.c) * t,
    h: lerpHue(a.h, b.h, t),
  };
}

function oklchEqual(a: OklchColor, b: OklchColor): boolean {
  return (
    Math.abs(a.l - b.l) < 0.001 &&
    Math.abs(a.c - b.c) < 0.001 &&
    (a.h === null && b.h === null || Math.abs((a.h ?? 0) - (b.h ?? 0)) < 0.5)
  );
}

const LERP_FACTORS = [0.33, 0.50, 0.67];

function generateCandidates(palette: Palette): OklchColor[] {
  const s = palette.shadow.oklch;
  const b = palette.base.oklch;
  const hi = palette.highlight.oklch;
  const ac = palette.accent.oklch;

  const pairs: [OklchColor, OklchColor][] = [
    [s, b],
    [b, hi],
    [b, ac],
    [s, ac],
    [hi, ac],
  ];

  const candidates: OklchColor[] = [];
  for (const [a, z] of pairs) {
    for (const t of LERP_FACTORS) {
      candidates.push(lerpOklch(a, z, t));
    }
  }

  // Extra variations if we need more
  const varOklch: OklchColor[] = [
    { l: Math.max(0.07, s.l - 0.08), c: s.c, h: s.h },
    { l: Math.min(0.93, hi.l + 0.06), c: hi.c * 0.8, h: hi.h },
    { l: b.l, c: Math.max(0, b.c - 0.04), h: ac.h },
    { l: b.l + 0.10, c: b.c * 0.9, h: b.h },
  ];
  candidates.push(...varOklch);

  // Gamut-fit all
  return candidates.map(c => fitToSrgb(c));
}

function deltaE(a: OklchColor, b: OklchColor): number {
  return calculateDeltaE(
    { role: 'a', hex: oklchToHex(a), oklch: a },
    { role: 'b', hex: oklchToHex(b), oklch: b },
  );
}

/** Max-min ΔE greedy selection. */
function selectByMaxMinDeltaE(
  anchors: OklchColor[],
  candidates: OklchColor[],
  n: number,
): OklchColor[] {
  const selected = [...anchors];

  // Remove candidates too similar to anchors
  const viable = candidates.filter(cand => {
    return selected.every(sel => !oklchEqual(cand, sel));
  });

  for (let i = 0; i < n; i++) {
    if (viable.length === 0) break;

    let bestIdx = 0;
    let bestMinDist = -1;

    for (let j = 0; j < viable.length; j++) {
      const minDist = Math.min(...selected.map(sel => deltaE(viable[j], sel)));
      if (minDist > bestMinDist) {
        bestMinDist = minDist;
        bestIdx = j;
      }
    }

    selected.push(viable[bestIdx]);
    viable.splice(bestIdx, 1);
  }

  return selected.slice(anchors.length);
}

/**
 * Extend a 4-color Palette to the requested display count (4–9).
 * count === 4: anchors only, unchanged.
 * count 5–9: anchors + derived colors, deterministic.
 */
export function extendPalette(
  palette: Palette,
  count: number,
): DisplayPaletteColor[] {
  const safeCount = Math.max(4, Math.min(9, Math.round(count)));

  const anchors: DisplayPaletteColor[] = [
    paletteColorToDisplay(palette.shadow, 'shadow'),
    paletteColorToDisplay(palette.base, 'base'),
    paletteColorToDisplay(palette.highlight, 'highlight'),
    paletteColorToDisplay(palette.accent, 'accent'),
  ];

  if (safeCount === 4) {
    return anchors;
  }

  const needed = safeCount - 4;
  const anchorOklch = anchors.map(a => a.oklch);
  const candidates = generateCandidates(palette);
  const derived = selectByMaxMinDeltaE(anchorOklch, candidates, needed);

  const derivedColors: DisplayPaletteColor[] = derived.slice(0, needed).map((oklch, i) => {
    const fitted = fitToSrgb(oklch);
    const hex = oklchToHex(fitted);
    const exactOklch = hexToOklch(hex) || fitted;
    return {
      id: `derived-${i}`,
      label: `Extra ${i + 1}`,
      hex,
      oklch: exactOklch,
      derived: true,
    };
  });

  return [...anchors, ...derivedColors];
}
