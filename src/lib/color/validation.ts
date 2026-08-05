import { OklchColor, PaletteColor } from '@/types/palette';
import { isInSrgbGamut } from './gamut';
import { oklchToHex } from './conversions';

export const SHADOW_BASE_MIN_DELTA = 0.08;
export const BASE_HIGHLIGHT_MIN_DELTA = 0.08;
export const BASE_ACCENT_MIN_DELTA = 0.12;

/**
 * Helper to unwrap OklchColor from either raw OklchColor or PaletteColor.
 */
function toOklchColor(input: OklchColor | PaletteColor): OklchColor {
  if ('oklch' in input && input.oklch) {
    return input.oklch;
  }
  return input as OklchColor;
}

/**
 * Converts OKLCH to OKLab (L, a, b) components.
 */
export function oklchToOklab(color: OklchColor): { l: number; a: number; b: number } {
  const l = color.l;
  if (color.h === null || color.c < 0.0001) {
    return { l, a: 0, b: 0 };
  }
  const rad = (color.h * Math.PI) / 180;
  const a = color.c * Math.cos(rad);
  const b = color.c * Math.sin(rad);
  return { l, a, b };
}

/**
 * Calculates Delta E OK (Euclidean distance in OKLab space).
 */
export function calculateDeltaE(c1: OklchColor | PaletteColor, c2: OklchColor | PaletteColor): number {
  const o1 = toOklchColor(c1);
  const o2 = toOklchColor(c2);

  const lab1 = oklchToOklab(o1);
  const lab2 = oklchToOklab(o2);

  const dl = lab1.l - lab2.l;
  const da = lab1.a - lab2.a;
  const db = lab1.b - lab2.b;

  return Math.sqrt(dl * dl + da * da + db * db);
}

export type ValidationResult = {
  isValid: boolean;
  issues: string[];
  boundaryMode?: 'black-base' | 'white-base';
};

/**
 * Validates a generated palette against color theory rules and boundary modes.
 */
export function validatePalette(palette: {
  shadow: OklchColor | PaletteColor;
  base: OklchColor | PaletteColor;
  highlight: OklchColor | PaletteColor;
  accent: OklchColor | PaletteColor;
}): ValidationResult {
  const issues: string[] = [];
  let boundaryMode: 'black-base' | 'white-base' | undefined;

  const shadow = toOklchColor(palette.shadow);
  const base = toOklchColor(palette.base);
  const highlight = toOklchColor(palette.highlight);
  const accent = toOklchColor(palette.accent);

  // Check NaN
  const allColors = [shadow, base, highlight, accent];
  for (const [idx, col] of allColors.entries()) {
    if (isNaN(col.l) || isNaN(col.c) || (col.h !== null && isNaN(col.h))) {
      issues.push(`Color at index ${idx} contains NaN values`);
    }
  }

  const baseL = base.l;
  const baseHex = ('hex' in palette.base ? palette.base.hex : oklchToHex(base)).toLowerCase();

  const isBlackBase = baseL <= 0.16 || baseHex === '#000000' || baseHex === '#010101';
  const isWhiteBase = baseL >= 0.97 || baseHex === '#ffffff' || baseHex === '#fefefe' || baseHex === '#f7f7f7';

  if (isBlackBase) {
    boundaryMode = 'black-base';

    // Black boundary rules:
    // Highlight and Accent must be distinct from Base
    const deltaBaseHighlight = calculateDeltaE(base, highlight);
    if (deltaBaseHighlight < SHADOW_BASE_MIN_DELTA) {
      issues.push(`Base and Highlight Delta E OK (${deltaBaseHighlight.toFixed(3)}) is below threshold ${SHADOW_BASE_MIN_DELTA}`);
    }

    const deltaBaseAccent = calculateDeltaE(base, accent);
    if (deltaBaseAccent < BASE_ACCENT_MIN_DELTA) {
      issues.push(`Base and Accent Delta E OK (${deltaBaseAccent.toFixed(3)}) is below threshold ${BASE_ACCENT_MIN_DELTA}`);
    }

    if (highlight.l < 0.15) {
      issues.push(`Highlight lightness (${highlight.l.toFixed(3)}) is too dark for black base boundary`);
    }
  } else if (isWhiteBase) {
    boundaryMode = 'white-base';

    // White boundary rules:
    // Shadow and Accent must be distinct from Base
    const deltaShadowBase = calculateDeltaE(shadow, base);
    if (deltaShadowBase < SHADOW_BASE_MIN_DELTA) {
      issues.push(`Shadow and Base Delta E OK (${deltaShadowBase.toFixed(3)}) is below threshold ${SHADOW_BASE_MIN_DELTA}`);
    }

    const deltaBaseAccent = calculateDeltaE(base, accent);
    if (deltaBaseAccent < BASE_ACCENT_MIN_DELTA) {
      issues.push(`Base and Accent Delta E OK (${deltaBaseAccent.toFixed(3)}) is below threshold ${BASE_ACCENT_MIN_DELTA}`);
    }

    if (shadow.l > 0.85) {
      issues.push(`Shadow lightness (${shadow.l.toFixed(3)}) is too light for white base boundary`);
    }
  } else {
    // Normal base rules:
    if (shadow.l >= base.l) {
      issues.push(`Shadow lightness (${shadow.l.toFixed(3)}) is not less than Base lightness (${base.l.toFixed(3)})`);
    }

    if (base.l >= highlight.l) {
      issues.push(`Base lightness (${base.l.toFixed(3)}) is not less than Highlight lightness (${highlight.l.toFixed(3)})`);
    }

    const deltaShadowBase = calculateDeltaE(shadow, base);
    if (deltaShadowBase < SHADOW_BASE_MIN_DELTA) {
      issues.push(`Shadow and Base Delta E OK (${deltaShadowBase.toFixed(3)}) is below threshold ${SHADOW_BASE_MIN_DELTA}`);
    }

    const deltaBaseHighlight = calculateDeltaE(base, highlight);
    if (deltaBaseHighlight < BASE_HIGHLIGHT_MIN_DELTA) {
      issues.push(`Base and Highlight Delta E OK (${deltaBaseHighlight.toFixed(3)}) is below threshold ${BASE_HIGHLIGHT_MIN_DELTA}`);
    }

    const deltaBaseAccent = calculateDeltaE(base, accent);
    if (deltaBaseAccent < BASE_ACCENT_MIN_DELTA) {
      issues.push(`Base and Accent Delta E OK (${deltaBaseAccent.toFixed(3)}) is below threshold ${BASE_ACCENT_MIN_DELTA}`);
    }
  }

  // Gamut check for all colors
  const colorMap = { shadow, base, highlight, accent };
  for (const [name, col] of Object.entries(colorMap)) {
    if (!isInSrgbGamut(col, 0.01)) {
      issues.push(`Color ${name} is out of sRGB gamut`);
    }
    const hex = oklchToHex(col);
    if (!/^#[0-9a-f]{6}$/i.test(hex)) {
      issues.push(`Color ${name} generated invalid HEX string (${hex})`);
    }
  }

  return {
    isValid: issues.length === 0,
    issues,
    boundaryMode,
  };
}
