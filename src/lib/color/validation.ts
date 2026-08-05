import { converter } from 'culori';
import { OklchColor } from '@/types/palette';
import { isInSrgbGamut } from './gamut';
import { oklchToHex } from './conversions';

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
export function calculateDeltaE(c1: OklchColor, c2: OklchColor): number {
  const lab1 = oklchToOklab(c1);
  const lab2 = oklchToOklab(c2);

  const dl = lab1.l - lab2.l;
  const da = lab1.a - lab2.a;
  const db = lab1.b - lab2.b;

  return Math.sqrt(dl * dl + da * da + db * db);
}

export type ValidationResult = {
  isValid: boolean;
  issues: string[];
};

/**
 * Validates a generated palette against rules.
 */
export function validatePalette(palette: {
  shadow: OklchColor;
  base: OklchColor;
  highlight: OklchColor;
  accent: OklchColor;
}): ValidationResult {
  const issues: string[] = [];

  // Check NaN
  const allColors = [palette.shadow, palette.base, palette.highlight, palette.accent];
  for (const [idx, col] of allColors.entries()) {
    if (isNaN(col.l) || isNaN(col.c) || (col.h !== null && isNaN(col.h))) {
      issues.push(`Color at index ${idx} contains NaN values`);
    }
  }

  // Lightness hierarchy
  if (palette.shadow.l >= palette.base.l) {
    issues.push(`Shadow lightness (${palette.shadow.l.toFixed(3)}) is not less than Base lightness (${palette.base.l.toFixed(3)})`);
  }

  if (palette.base.l >= palette.highlight.l) {
    issues.push(`Base lightness (${palette.base.l.toFixed(3)}) is not less than Highlight lightness (${palette.highlight.l.toFixed(3)})`);
  }

  // Delta E distinctions
  const deltaShadowBase = calculateDeltaE(palette.shadow, palette.base);
  if (deltaShadowBase < 0.07) {
    issues.push(`Shadow and Base Delta E OK (${deltaShadowBase.toFixed(3)}) is below threshold 0.07`);
  }

  const deltaBaseHighlight = calculateDeltaE(palette.base, palette.highlight);
  const minHighlightDelta = palette.base.l > 0.90 ? 0.015 : 0.07;
  if (deltaBaseHighlight < minHighlightDelta) {
    issues.push(`Base and Highlight Delta E OK (${deltaBaseHighlight.toFixed(3)}) is below threshold ${minHighlightDelta}`);
  }

  const deltaBaseAccent = calculateDeltaE(palette.base, palette.accent);
  if (deltaBaseAccent < 0.10) {
    issues.push(`Base and Accent Delta E OK (${deltaBaseAccent.toFixed(3)}) is below threshold 0.10`);
  }

  // Gamut check
  for (const [name, col] of Object.entries(palette)) {
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
  };
}
