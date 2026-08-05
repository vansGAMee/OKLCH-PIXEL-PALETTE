import { converter } from 'culori';
import { OklchColor } from '@/types/palette';

const toRgb = converter('rgb');

/**
 * Checks if an OKLCH color falls inside sRGB gamut [0, 1] for all channels.
 */
export function isInSrgbGamut(color: OklchColor, eps: number = 1e-4): boolean {
  const modeObj = {
    mode: 'oklch' as const,
    l: color.l,
    c: color.c,
    h: color.h === null ? 0 : color.h,
  };

  const rgb = toRgb(modeObj);
  if (!rgb) return false;

  const r = rgb.r ?? 0;
  const g = rgb.g ?? 0;
  const b = rgb.b ?? 0;

  return r >= -eps && r <= 1 + eps &&
         g >= -eps && g <= 1 + eps &&
         b >= -eps && b <= 1 + eps;
}

/**
 * Fits an OKLCH color into the sRGB gamut by preserving Lightness (L) and Hue (H),
 * and performing a binary search for maximum allowable Chroma (C).
 * Preserves L in physical range [0, 1] without forced clamping.
 */
export function fitToSrgb(color: OklchColor): OklchColor {
  const targetL = Math.max(0, Math.min(1, color.l));
  const baseColor: OklchColor = { l: targetL, c: color.c, h: color.h };

  if (isInSrgbGamut(baseColor, 1e-4)) {
    return baseColor;
  }

  let lowC = 0;
  let highC = color.c;
  let bestC = 0;

  for (let i = 0; i < 24; i++) {
    const midC = (lowC + highC) / 2;
    const testColor: OklchColor = { l: targetL, c: midC, h: color.h };

    if (isInSrgbGamut(testColor, 1e-4)) {
      bestC = midC;
      lowC = midC;
    } else {
      highC = midC;
    }
  }

  return {
    l: targetL,
    c: bestC,
    h: color.h,
  };
}
