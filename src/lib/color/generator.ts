import { HarmonyMode, OklchColor, Palette, PaletteColor } from '@/types/palette';
import { hexToOklch, normalizeHex, oklchToHex, shiftHueToward } from './conversions';
import { fitToSrgb } from './gamut';
import { generateAccentCandidate } from './harmony';
import { calculateDeltaE, SHADOW_BASE_MIN_DELTA, BASE_HIGHLIGHT_MIN_DELTA, BASE_ACCENT_MIN_DELTA } from './validation';
import { createPrng } from './seed';

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

/**
 * Generates the Shadow color given a Base OKLCH color and seed offset.
 */
export function generateShadow(base: OklchColor, seedL: number = 0, seedC: number = 0, seedH: number = 0): OklchColor {
  const isNeutral = base.c < 0.025;
  const isBlackBase = base.l <= 0.16;
  const isWhiteBase = base.l >= 0.97;

  if (isBlackBase) {
    // For black base, shadow is deep dark
    return { l: 0, c: 0, h: null };
  }

  if (isWhiteBase) {
    // For white base, shadow scales down to ~0.65
    const targetL = clamp(0.65 + seedL * 0.05, 0.40, 0.80);
    const targetC = 0.03 + Math.abs(seedC) * 0.02;
    const targetHue = shiftHueToward(base.h ?? 265, 265, 18);
    return fitToSrgb({ l: targetL, c: targetC, h: targetHue });
  }

  let targetL = clamp(base.l - 0.22 + seedL * 0.07, 0.04, 0.72);
  if (targetL >= base.l - 0.08) {
    targetL = Math.max(0.04, base.l - 0.12);
  }

  const targetC = isNeutral
    ? 0.008
    : clamp(base.c * 0.9 + seedC * 0.04, 0.025, 0.22);

  const maxHueShift = 12 + seedH * 12; // 12 deg to 24 deg
  const targetHue = isNeutral
    ? base.h
    : shiftHueToward(base.h, 265, maxHueShift);

  return fitToSrgb({ l: targetL, c: targetC, h: targetHue });
}

/**
 * Generates the Highlight color given a Base OKLCH color and seed offset.
 */
export function generateHighlight(base: OklchColor, seedL: number = 0, seedC: number = 0, seedH: number = 0): OklchColor {
  const isNeutral = base.c < 0.025;
  const isBlackBase = base.l <= 0.16;
  const isWhiteBase = base.l >= 0.97;

  if (isWhiteBase) {
    // For white base, highlight is pure white
    return { l: 1, c: 0, h: null };
  }

  if (isBlackBase) {
    // For black base, highlight scales up to ~0.35
    const targetL = clamp(0.35 + seedL * 0.05, 0.20, 0.50);
    const targetC = 0.03 + Math.abs(seedC) * 0.02;
    const targetHue = shiftHueToward(base.h ?? 90, 90, 18);
    return fitToSrgb({ l: targetL, c: targetC, h: targetHue });
  }

  let targetL = clamp(base.l + 0.22 + seedL * 0.07, 0.28, 0.98);
  if (targetL <= base.l + 0.02) {
    targetL = Math.min(0.98, base.l + 0.05);
  }

  const targetC = isNeutral
    ? 0.008
    : clamp(base.c * 0.72 + seedC * 0.04, 0.015, 0.18);

  const maxHueShift = 8 + seedH * 10; // 8 deg to 18 deg
  const targetHue = isNeutral
    ? base.h
    : shiftHueToward(base.h, 90, maxHueShift);

  return fitToSrgb({ l: targetL, c: targetC, h: targetHue });
}

/**
 * Repairs a generated palette if lightness order or minimum distinctions are violated.
 * Runs bounded iterations to adjust L, C, and slight Hue shift.
 * Base color remains 100% untouched.
 */
export function repairPalette(
  shadow: OklchColor,
  base: OklchColor,
  highlight: OklchColor,
  accent: OklchColor
): { shadow: OklchColor; base: OklchColor; highlight: OklchColor; accent: OklchColor } {
  let s = { ...shadow };
  const b = { ...base }; // Read-only base
  let h = { ...highlight };
  let a = { ...accent };

  const isBlackBase = b.l <= 0.16;
  const isWhiteBase = b.l >= 0.97;

  const MAX_ITERATIONS = 5;

  for (let iter = 0; iter < MAX_ITERATIONS; iter++) {
    let changed = false;

    if (!isBlackBase && !isWhiteBase) {
      // Normal Lightness hierarchy: s.l < b.l < h.l
      if (s.l >= b.l - 0.02) {
        s.l = Math.max(0.04, b.l - 0.12 - iter * 0.02);
        changed = true;
      }

      if (h.l <= b.l + 0.02) {
        h.l = Math.min(0.98, b.l + 0.12 + iter * 0.02);
        changed = true;
      }

      if (calculateDeltaE(s, b) < SHADOW_BASE_MIN_DELTA) {
        s.l = Math.max(0.04, s.l - 0.04);
        s.c = clamp(s.c * 0.9, 0.008, 0.22);
        changed = true;
      }

      if (calculateDeltaE(b, h) < BASE_HIGHLIGHT_MIN_DELTA) {
        h.l = Math.min(0.98, h.l + 0.04);
        h.c = clamp(h.c * 0.9, 0.008, 0.18);
        changed = true;
      }
    } else if (isBlackBase) {
      // Black boundary adjustments
      if (calculateDeltaE(b, h) < SHADOW_BASE_MIN_DELTA) {
        h.l = clamp(h.l + 0.05, 0.20, 0.60);
        changed = true;
      }
    } else if (isWhiteBase) {
      // White boundary adjustments
      if (calculateDeltaE(s, b) < SHADOW_BASE_MIN_DELTA) {
        s.l = clamp(s.l - 0.05, 0.40, 0.80);
        changed = true;
      }
    }

    // Accent distinction check for all modes
    if (calculateDeltaE(b, a) < BASE_ACCENT_MIN_DELTA) {
      const lDir = b.l >= 0.5 ? -1 : 1;
      a.l = clamp(a.l + lDir * (0.08 + iter * 0.02), 0.10, 0.90);
      if (b.c < 0.025) {
        a.c = clamp(a.c + 0.03, 0.10, 0.22);
      }
      changed = true;
    }

    // Re-fit adjusted colors to sRGB
    s = fitToSrgb(s);
    h = fitToSrgb(h);
    a = fitToSrgb(a);

    if (!changed) break;
  }

  return { shadow: s, base: b, highlight: h, accent: a };
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

  const seedShadowL = (prng() - 0.5);
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

  // Helper for Shadow, Highlight, Accent colors (fit & format)
  const createGeneratedColor = (
    role: 'shadow' | 'highlight' | 'accent',
    rawOklch: OklchColor
  ): PaletteColor => {
    const fitted = fitToSrgb(rawOklch);
    return {
      role,
      hex: oklchToHex(fitted),
      oklch: {
        l: Number(fitted.l.toFixed(4)),
        c: Number(fitted.c.toFixed(4)),
        h: fitted.h !== null ? Number(fitted.h.toFixed(2)) : null,
      },
    };
  };

  // Base color: EXACT untouched OKLCH and input HEX
  const basePaletteColor: PaletteColor = {
    role: 'base',
    hex: normHex,
    oklch: {
      l: baseOklch.l,
      c: baseOklch.c,
      h: baseOklch.h,
    },
  };

  return {
    shadow: createGeneratedColor('shadow', repaired.shadow),
    base: basePaletteColor,
    highlight: createGeneratedColor('highlight', repaired.highlight),
    accent: createGeneratedColor('accent', repaired.accent),
    harmony,
    seed,
  };
}
