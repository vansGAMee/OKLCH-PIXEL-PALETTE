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
 * Supports palette sizes from 2 to 9 colors.
 */
export function generatePalette(
  hexInput: string,
  harmony: HarmonyMode = 'splitComplementary',
  seed: number = 0,
  colorCount: number = 4
): Palette {
  const count = clamp(Math.round(colorCount), 2, 9);
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

  // Step 1: Generate initial core colors
  const rawShadow = generateShadow(baseOklch, seedShadowL, seedShadowC, seedShadowH);
  const rawHighlight = generateHighlight(baseOklch, seedHighlightL, seedHighlightC, seedHighlightH);
  const rawAccent = generateAccentCandidate(baseOklch, rawShadow, rawHighlight, harmony, seedAccentOffset);

  // Step 2: Repair core palette for hard guarantees
  const repaired = repairPalette(rawShadow, baseOklch, rawHighlight, rawAccent);

  // Helper for formatting PaletteColor objects
  const createGeneratedColor = (
    role: string,
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

  const shadowColor = createGeneratedColor('shadow', repaired.shadow);
  const highlightColor = createGeneratedColor('highlight', repaired.highlight);
  const accentColor = createGeneratedColor('accent', repaired.accent);

  // Build the colors array (Single Source of Truth) based on count
  const colors: PaletteColor[] = [];

  if (count === 2) {
    colors.push(shadowColor);
    colors.push(basePaletteColor);
  } else if (count === 3) {
    colors.push(shadowColor);
    colors.push(basePaletteColor);
    colors.push(highlightColor);
  } else {
    // 4 to 9 colors: start with standard 4 core colors
    colors.push(shadowColor);
    colors.push(basePaletteColor);
    colors.push(highlightColor);
    colors.push(accentColor);

    // Extra colors (5 to 9)
    const extraSpecs: { l: number; c: number; hShift: number }[] = [
      // color 5: mid shadow
      { l: (repaired.shadow.l + baseOklch.l) / 2, c: (repaired.shadow.l > 0.01 ? (repaired.shadow.c + baseOklch.c) / 2 : baseOklch.c * 0.5), hShift: -15 },
      // color 6: mid highlight
      { l: (baseOklch.l + repaired.highlight.l) / 2, c: (baseOklch.c + repaired.highlight.c) / 2, hShift: 15 },
      // color 7: deep shadow
      { l: Math.max(0.03, repaired.shadow.l * 0.6), c: repaired.shadow.c * 0.7, hShift: -30 },
      // color 8: vibrant accent variation
      { l: clamp(repaired.accent.l + 0.08, 0.15, 0.88), c: clamp(repaired.accent.c * 1.1, 0.05, 0.22), hShift: 45 },
      // color 9: bright highlight
      { l: Math.min(0.98, repaired.highlight.l + (1 - repaired.highlight.l) * 0.5), c: repaired.highlight.c * 0.6, hShift: 30 },
    ];

    for (let i = 4; i < count; i++) {
      const spec = extraSpecs[i - 4];
      const baseH = baseOklch.h ?? 0;
      const targetH = (baseH + spec.hShift + 360) % 360;
      const rawOklch: OklchColor = {
        l: clamp(spec.l, 0.02, 0.98),
        c: clamp(spec.c, 0.005, 0.25),
        h: targetH,
      };
      colors.push(createGeneratedColor(`color${i + 1}`, rawOklch));
    }
  }

  // Deduplication pass: ensure no duplicate HEX or visually indistinguishable colors (DeltaE < 0.035)
  const deduplicatedColors = deduplicateColors(colors);

  // Find or fallback core roles directly from deduplicated colors array (Single Source of Truth)
  const shadow = deduplicatedColors.find((c) => c.role === 'shadow') || deduplicatedColors[0];
  const base = deduplicatedColors.find((c) => c.role === 'base') || deduplicatedColors[1] || deduplicatedColors[0];
  const highlight = deduplicatedColors.find((c) => c.role === 'highlight') || deduplicatedColors[deduplicatedColors.length - 1] || base;
  const accent = deduplicatedColors.find((c) => c.role === 'accent') || highlight || base;

  return {
    colors: deduplicatedColors,
    count,
    shadow,
    base,
    highlight,
    accent,
    harmony,
    seed,
  };
}

export const MIN_PALETTE_DELTA_E = 0.025;

/**
 * Deduplicates and ensures minimum perceptual distinction (OKLab Delta E >= 0.025) between all colors.
 * Lightness is adjusted first, then chroma, then hue. Base color remains 100% untouched.
 */
export function deduplicateColors(colors: PaletteColor[]): PaletteColor[] {
  const result = colors.map((c) => ({ ...c, oklch: { ...c.oklch } }));
  const count = result.length;
  if (count <= 1) return result;

  const MAX_OUTER_PASSES = 4;
  const MAX_ITER = 8;

  for (let pass = 0; pass < MAX_OUTER_PASSES; pass++) {
    let anyChanged = false;

    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        let iter = 0;
        while (iter < MAX_ITER) {
          const delta = calculateDeltaE(result[i].oklch, result[j].oklch);
          const hex1 = result[i].hex.toLowerCase();
          const hex2 = result[j].hex.toLowerCase();
          const hexSame = hex1 === hex2;

          if (delta >= MIN_PALETTE_DELTA_E && !hexSame) {
            break; // Distinct enough
          }

          anyChanged = true;

          // Adjust result[j] (unless it's base, in which case adjust result[i])
          const targetIdx = result[j].role === 'base' ? i : j;
          const compareIdx = targetIdx === j ? i : j;
          const target = result[targetIdx];
          const compare = result[compareIdx];

          const step = iter + 1;
          let lDir = target.oklch.l >= compare.oklch.l ? 1 : -1;
          if (target.oklch.l >= 0.94) lDir = -1;
          if (target.oklch.l <= 0.06) lDir = 1;

          // Step 1: Lightness adjustment first
          const newL = clamp(target.oklch.l + lDir * 0.04 * step, 0.03, 0.97);
          let newC = target.oklch.c;
          let newH = target.oklch.h;

          let fitted = fitToSrgb({ l: newL, c: newC, h: newH });
          let newHex = oklchToHex(fitted).toLowerCase();
          let newDelta = calculateDeltaE(compare.oklch, fitted);

          // Step 2: Chroma adjustment if lightness shift wasn't enough or HEX identical
          if (newDelta < MIN_PALETTE_DELTA_E || newHex === compare.hex.toLowerCase()) {
            const cDir = target.oklch.c >= compare.oklch.c ? 1 : -1;
            newC = clamp(target.oklch.c + cDir * 0.035 * step, 0.005, 0.25);
            fitted = fitToSrgb({ l: newL, c: newC, h: newH });
            newHex = oklchToHex(fitted).toLowerCase();
            newDelta = calculateDeltaE(compare.oklch, fitted);
          }

          // Step 3: Hue adjustment if still too close or HEX identical
          if (newDelta < MIN_PALETTE_DELTA_E || newHex === compare.hex.toLowerCase()) {
            const baseH = newH !== null ? newH : 180;
            newH = (baseH + 25 * step) % 360;
            fitted = fitToSrgb({ l: newL, c: newC, h: newH });
            newHex = oklchToHex(fitted).toLowerCase();
          }

          result[targetIdx] = {
            role: target.role,
            hex: newHex,
            oklch: {
              l: Number(fitted.l.toFixed(4)),
              c: Number(fitted.c.toFixed(4)),
              h: fitted.h !== null ? Number(fitted.h.toFixed(2)) : null,
            },
          };

          iter++;
        }
      }
    }

    if (!anyChanged) break;
  }

  return result;
}
