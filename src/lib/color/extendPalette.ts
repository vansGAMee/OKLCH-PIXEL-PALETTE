/**
 * extendPalette.ts
 * Deterministically resizes a generated 4-color Palette to 2–9 colors.
 * - count 2–4: return the requested number of anchors unchanged
 * - count 5–9: derive additional colors by OKLCH interpolation + max-min ΔE selection
 */
import type { Palette, PaletteColor, OklchColor } from '@/types/palette';
import { fitToSrgb } from '@/lib/color/gamut';
import { oklchToHex, hexToOklch } from '@/lib/color/conversions';
import { calculateDeltaE } from '@/lib/color/validation';

export interface DisplayPaletteColor {
  id: string;
  label: string;
  role: string;
  hex: string;
  oklch: OklchColor;
  anchorRole?: 'shadow' | 'base' | 'highlight' | 'accent';
  derived: boolean;
}

export const MIN_PALETTE_COLOR_COUNT = 2;
export const MAX_PALETTE_COLOR_COUNT = 9;

export function clampPaletteColorCount(count: number): number {
  return Math.max(MIN_PALETTE_COLOR_COUNT, Math.min(MAX_PALETTE_COLOR_COUNT, Math.round(count)));
}

function roleForIndex(index: number): string {
  return ['shadow', 'base', 'highlight', 'accent'][index] ?? `color${index + 1}`;
}

/**
 * Builds the single Palette value consumed by the studio and every downstream
 * preview/export surface. Named roles remain compatibility aliases into colors.
 */
export function createCanonicalPalette(
  colors: readonly PaletteColor[],
  harmony: Palette['harmony'],
  seed: number,
): Palette {
  if (colors.length < MIN_PALETTE_COLOR_COUNT || colors.length > MAX_PALETTE_COLOR_COUNT) {
    throw new Error(`Palette must contain ${MIN_PALETTE_COLOR_COUNT}–${MAX_PALETTE_COLOR_COUNT} colors.`);
  }

  const canonicalColors = colors.map((color, index) => ({
    role: color.role || roleForIndex(index),
    hex: color.hex,
    oklch: { ...color.oklch },
  }));
  const last = canonicalColors.length - 1;
  const findRole = (role: string, fallbackIndex: number) =>
    canonicalColors.find((color) => color.role === role) ?? canonicalColors[Math.min(fallbackIndex, last)];

  return {
    colors: canonicalColors,
    count: canonicalColors.length,
    shadow: findRole('shadow', 0),
    base: findRole('base', 1),
    highlight: findRole('highlight', 2),
    accent: findRole('accent', 3),
    harmony,
    seed,
  };
}

/** Replaces only unlocked slots while keeping locked HEX and OKLCH values exact. */
export function mergeLockedPalette(
  current: Palette,
  candidate: Palette,
  lockedIndices: ReadonlySet<number>,
): Palette {
  const colors = candidate.colors.map((color, index) =>
    lockedIndices.has(index) && current.colors[index] ? current.colors[index] : color
  );
  return createCanonicalPalette(colors, candidate.harmony, candidate.seed);
}

/** Converts direct model OKLCH output to a canonical, gamut-safe Palette. */
export function createCanonicalPaletteFromOklch(
  colors: readonly OklchColor[],
  harmony: Palette['harmony'],
  seed: number,
): Palette {
  const converted = colors.map((color, index): PaletteColor => {
    if (
      !Number.isFinite(color.l) ||
      !Number.isFinite(color.c) ||
      (color.h !== null && !Number.isFinite(color.h))
    ) {
      throw new Error(`AI returned an invalid OKLCH color at index ${index}.`);
    }

    const fitted = fitToSrgb(color);
    const hex = oklchToHex(fitted);
    return {
      role: roleForIndex(index),
      hex,
      oklch: hexToOklch(hex) ?? fitted,
    };
  });

  return createCanonicalPalette(converted, harmony, seed);
}

function paletteColorToDisplay(
  pc: PaletteColor,
  anchorRole: 'shadow' | 'base' | 'highlight' | 'accent',
): DisplayPaletteColor {
  return {
    id: anchorRole,
    label: anchorRole.charAt(0).toUpperCase() + anchorRole.slice(1),
    role: anchorRole,
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

const LERP_FACTORS = [0.2, 0.33, 0.50, 0.67, 0.8];

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
    [s, hi],
  ];

  const candidates: OklchColor[] = [];
  for (const [a, z] of pairs) {
    for (const t of LERP_FACTORS) {
      candidates.push(lerpOklch(a, z, t));
    }
  }

  // Extra rich hue/lightness variations across the space
  for (const offset of [-40, -25, -15, 15, 25, 40]) {
    const baseH = b.h ?? 0;
    candidates.push({
      l: Math.max(0.12, Math.min(0.88, (s.l + b.l) / 2)),
      c: Math.max(0.04, b.c * 0.85),
      h: (baseH + offset + 360) % 360,
    });
    candidates.push({
      l: Math.max(0.12, Math.min(0.88, (b.l + hi.l) / 2)),
      c: Math.max(0.04, b.c * 0.9),
      h: (baseH + offset + 360) % 360,
    });
  }

  // Gamut-fit all
  return candidates.map(c => fitToSrgb(c));
}

function deltaE(a: OklchColor, b: OklchColor): number {
  const hexA = oklchToHex(a);
  const hexB = oklchToHex(b);
  const qA = hexToOklch(hexA) || a;
  const qB = hexToOklch(hexB) || b;
  return calculateDeltaE(qA, qB);
}

/** Max-min ΔE greedy selection with minimum separation guarantee. */
function selectByMaxMinDeltaE(
  anchors: OklchColor[],
  candidates: OklchColor[],
  n: number,
): OklchColor[] {
  const selected = [...anchors];
  const selectedHexes = new Set(selected.map(s => oklchToHex(s).toLowerCase()));

  // Remove candidates too close or identical in HEX to anchors
  const viable = candidates.filter(cand => {
    const hex = oklchToHex(cand).toLowerCase();
    if (selectedHexes.has(hex)) return false;
    return selected.every(sel => deltaE(cand, sel) >= 0.028);
  });

  for (let i = 0; i < n; i++) {
    let bestIdx = -1;
    let bestMinDist = -1;

    for (let j = 0; j < viable.length; j++) {
      const minDist = Math.min(...selected.map(sel => deltaE(viable[j], sel)));
      if (minDist >= 0.026 && minDist > bestMinDist) {
        bestMinDist = minDist;
        bestIdx = j;
      }
    }

    if (bestIdx === -1) {
      // Fallback: synthesize a distinct color with guaranteed deltaE >= 0.03
      const base = selected[1] || selected[0];
      const fallback: OklchColor = fitToSrgb({
        l: Math.max(0.12, Math.min(0.88, 0.2 + ((i * 0.17) % 0.6))),
        c: Math.max(0.08, base.c),
        h: ((base.h ?? 0) + (i + 1) * 55 + 360) % 360,
      });
      selected.push(fallback);
      selectedHexes.add(oklchToHex(fallback).toLowerCase());
      continue;
    }

    const chosen = viable[bestIdx];
    selected.push(chosen);
    selectedHexes.add(oklchToHex(chosen).toLowerCase());
    viable.splice(bestIdx, 1);
  }

  return selected.slice(anchors.length);
}

/**
 * Resize a 4-color Palette to the requested display count (2–9).
 * count 2–4: requested anchors only, unchanged.
 * count 5–9: anchors + derived colors, deterministic.
 */
export function extendPalette(
  palette: Palette,
  count: number,
): DisplayPaletteColor[] {
  const safeCount = clampPaletteColorCount(count);

  const anchors: DisplayPaletteColor[] = [
    paletteColorToDisplay(palette.shadow, 'shadow'),
    paletteColorToDisplay(palette.base, 'base'),
    paletteColorToDisplay(palette.highlight, 'highlight'),
    paletteColorToDisplay(palette.accent, 'accent'),
  ];

  if (safeCount <= 4) {
    return anchors.slice(0, safeCount);
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
      role: `color${i + 5}`,
      hex,
      oklch: exactOklch,
      derived: true,
    };
  });

  return [...anchors, ...derivedColors];
}

/** Turns the deterministic manual generator output into the canonical Palette. */
export function canonicalizeGeneratedPalette(palette: Palette, count: number): Palette {
  return createCanonicalPalette(extendPalette(palette, count), palette.harmony, palette.seed);
}
