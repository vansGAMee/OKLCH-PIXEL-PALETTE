import { HarmonyMode, OklchColor, Palette, PaletteColor } from '@/types/palette';
import { hexToOklch, normalizeHex, oklchToHex, shiftHueToward } from './conversions';
import { fitToSrgb } from './gamut';
import { generateAccentCandidate } from './harmony';
import { calculateDeltaE } from './validation';
import { createPrng } from './seed';

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

/**
 * Generates the Shadow color given a Base OKLCH color and seed offset.
 */
export function generateShadow(base: OklchColor, seedL: number = 0, seedC: number = 0, seedH: number = 0): OklchColor {
  const isNeutral = base.c < 0.025;

  let targetL = clamp(base.l - 0.22 + seedL * 0.07, 0.04, 0.72);
  // Ensure shadow lightness is distinctly lower than base lightness
  if (targetL >= base.l - 0.08) {
    targetL = Math.max(0.04, base.l - 0.12);
  }

  let targetC = isNeutral
    ? 0.008
    : clamp(base.c * 0.9 + seedC * 0.04, 0.025, 0.22);

  // Hue shift towards cold blue-violet (~265 deg)
  const maxHueShift = 12 + seedH * 12; // 12 deg to 24 deg
  const targetHue = isNeutral
    ? base.h
    : shiftHueToward(base.h, 265, maxHueShift);

  const rawShadow: OklchColor = {
    l: targetL,
    c: targetC,
    h: targetHue,
  };

  return fitToSrgb(rawShadow);
}

/**
 * Generates the Highlight color given a Base OKLCH color and seed offset.
 */
export function generateHighlight(base: OklchColor, seedL: number = 0, seedC: number = 0, seedH: number = 0): OklchColor {
  const isNeutral = base.c < 0.025;

  const maxL = base.l > 0.75 ? 0.995 : 0.97;
  let targetL = clamp(base.l + 0.22 + seedL * 0.07, 0.28, maxL);
  // Ensure highlight lightness is distinctly higher than base lightness
  if (targetL <= base.l + 0.015) {
    targetL = Math.min(maxL, base.l + 0.018);
  }

  let targetC = isNeutral
    ? 0.008
    : clamp(base.c * 0.72 + seedC * 0.04, 0.015, 0.18);

  // Hue shift towards warm yellow (~90 deg)
  const maxHueShift = 8 + seedH * 10; // 8 deg to 18 deg
  const targetHue = isNeutral
    ? base.h
    : shiftHueToward(base.h, 90, maxHueShift);

  const rawHighlight: OklchColor = {
    l: targetL,
    c: targetC,
    h: targetHue,
  };

  return fitToSrgb(rawHighlight);
}

/**
 * Repairs a generated palette if lightness order or minimum distinctions are violated.
 * Base color remains 100% untouched.
 */
export function repairPalette(
  shadow: OklchColor,
  base: OklchColor,
  highlight: OklchColor,
  accent: OklchColor
): { shadow: OklchColor; base: OklchColor; highlight: OklchColor; accent: OklchColor } {
  let s = { ...shadow };
  let b = { ...base }; // Read-only base
  let h = { ...highlight };
  let a = { ...accent };

  // Enforce Lightness hierarchy: s.l < b.l < h.l
  if (s.l >= b.l) {
    s.l = Math.max(0.04, b.l - 0.12);
  }

  if (h.l <= b.l) {
    const maxL = b.l > 0.75 ? 0.995 : 0.97;
    h.l = Math.min(maxL, b.l + 0.015);
  }

  // Ensure minimum Delta E OK distinction
  if (calculateDeltaE(s, b) < 0.07) {
    s.l = Math.max(0.04, s.l - 0.05);
    s.c = clamp(s.c * 0.9, 0.008, 0.22);
  }

  if (calculateDeltaE(b, h) < 0.07 && b.l < 0.97) {
    const maxL = b.l > 0.75 ? 0.995 : 0.97;
    h.l = Math.min(maxL, h.l + 0.03);
  }

  if (calculateDeltaE(b, a) < 0.10) {
    // Shift accent lightness away from base
    const lDir = b.l >= 0.5 ? -1 : 1;
    a.l = clamp(a.l + lDir * 0.12, 0.1, 0.95);
    if (b.c < 0.025) {
      a.c = clamp(a.c + 0.05, 0.1, 0.22);
    }
  }

  return {
    shadow: fitToSrgb(s),
    base: b,
    highlight: fitToSrgb(h),
    accent: fitToSrgb(a),
  };
}

/**
 * Main palette generator function.
 */
export function generatePalette(
  hexInput: string,
  harmony: HarmonyMode = 'splitComplementary',
  seed: number = 0
): Palette {
  const normHex = normalizeHex(hexInput) || '#5b21b6';
  const baseOklch = hexToOklch(normHex) || { l: 0.35, c: 0.18, h: 290 };

  const prng = createPrng(seed);

  // Seed offsets within limits:
  // Lightness: ±0.035
  // Chroma: ±0.02
  // Hue shift: 0 to 1
  const seedShadowL = (prng() - 0.5); // -0.5 to 0.5 -> ±0.035
  const seedShadowC = (prng() - 0.5);
  const seedShadowH = prng();

  const seedHighlightL = (prng() - 0.5);
  const seedHighlightC = (prng() - 0.5);
  const seedHighlightH = prng();

  const seedAccentOffset = prng();

  // Step 1: Generate initial colors
  const rawShadow = generateShadow(baseOklch, seedShadowL, seedShadowC, seedShadowH);
  const rawHighlight = generateHighlight(baseOklch, seedHighlightL, seedHighlightC, seedHighlightH);
  const rawAccent = generateAccentCandidate(baseOklch, rawShadow, rawHighlight, harmony, seedAccentOffset);

  // Step 2: Repair palette for hard guarantees
  const repaired = repairPalette(rawShadow, baseOklch, rawHighlight, rawAccent);

  const createPaletteColor = (
    role: 'shadow' | 'base' | 'highlight' | 'accent',
    rawOklch: OklchColor,
    overrideHex?: string
  ): PaletteColor => {
    // 1. Round values
    const rounded: OklchColor = {
      l: Number(rawOklch.l.toFixed(4)),
      c: Number(rawOklch.c.toFixed(4)),
      h: rawOklch.h !== null ? Number(rawOklch.h.toFixed(2)) : null,
    };

    // 2. Ensure fitted into sRGB after rounding
    const fitted = fitToSrgb(rounded);

    const hex = overrideHex || oklchToHex(fitted);
    return {
      role,
      hex,
      oklch: {
        l: Number(fitted.l.toFixed(4)),
        c: Number(fitted.c.toFixed(4)),
        h: fitted.h !== null ? Number(fitted.h.toFixed(2)) : null,
      },
    };
  };

  return {
    shadow: createPaletteColor('shadow', repaired.shadow),
    base: createPaletteColor('base', baseOklch, normHex),
    highlight: createPaletteColor('highlight', repaired.highlight),
    accent: createPaletteColor('accent', repaired.accent),
    harmony,
    seed,
  };
}
