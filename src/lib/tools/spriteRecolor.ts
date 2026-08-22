import { hexToOklch, normalizeHex } from '@/lib/color/conversions';
import { calculateDeltaE } from '@/lib/color/validation';
import type { OklchColor } from '@/types/palette';

export interface TargetColor {
  hex: string;
  oklch: OklchColor;
}

export function parseTargetPalette(input: string): TargetColor[] {
  return input
    .replace(/[,;\n\r\t]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .flatMap(t => {
      const hex = normalizeHex(t.startsWith('#') ? t : `#${t}`);
      if (!hex) return [];
      const oklch = hexToOklch(hex);
      if (!oklch) return [];
      return [{ hex, oklch }];
    });
}

export function findNearestColorHex(src: OklchColor, targets: TargetColor[]): string {
  if (targets.length === 0) return '#000000';
  let best = targets[0]!;
  let bestDe = Infinity;
  for (const t of targets) {
    const de = calculateDeltaE(src, t.oklch);
    if (de < bestDe) {
      bestDe = de;
      best = t;
    }
  }
  return best.hex;
}

export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

/**
 * Recolors raw RGBA image data array using the target palette in-place.
 */
export function recolorPixelBuffer(
  srcData: Uint8ClampedArray,
  targetData: Uint8ClampedArray,
  targets: TargetColor[]
): void {
  if (targets.length === 0) return;

  // Cache RGB to nearest mapped RGB for performance
  const cache = new Map<number, [number, number, number]>();

  for (let i = 0; i < srcData.length; i += 4) {
    const a = srcData[i + 3];
    if (a < 10) {
      targetData[i] = 0;
      targetData[i + 1] = 0;
      targetData[i + 2] = 0;
      targetData[i + 3] = 0;
      continue;
    }

    const r = srcData[i];
    const g = srcData[i + 1];
    const b = srcData[i + 2];
    const key = (r << 16) | (g << 8) | b;

    let mappedRgb = cache.get(key);
    if (!mappedRgb) {
      const srcHex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
      const srcOklch = hexToOklch(srcHex) ?? { l: 0.5, c: 0, h: null };
      const nearest = findNearestColorHex(srcOklch, targets);
      mappedRgb = hexToRgb(nearest);
      cache.set(key, mappedRgb);
    }

    targetData[i] = mappedRgb[0];
    targetData[i + 1] = mappedRgb[1];
    targetData[i + 2] = mappedRgb[2];
    targetData[i + 3] = a;
  }
}
