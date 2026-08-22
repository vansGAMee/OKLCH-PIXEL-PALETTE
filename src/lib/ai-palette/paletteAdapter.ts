/**
 * paletteAdapter.ts
 * Converts raw CNN output [7] → { baseHex, harmony }.
 * Uses existing OKLCH engine for gamut safety.
 */
import type { HarmonyMode, OklchColor } from '@/types/palette';
import { fitToSrgb, isInSrgbGamut } from '@/lib/color/gamut';
import { oklchToHex } from '@/lib/color/conversions';

const L_MIN = 0.07;
const L_MAX = 0.93;
const INTERIOR_MARGIN = 0.92;

export interface AiPaletteIntent {
  baseHex: string;
  harmony: HarmonyMode;
}

const HARMONY_CLASSES: HarmonyMode[] = [
  'splitComplementary',
  'complementary',
  'analogous',
];

/** True sRGB gamut boundary search using existing isInSrgbGamut. */
export function maxSrgbChromaAt(l: number, h: number): number {
  // Normalize hue, validate lightness
  const hNorm = ((h % 360) + 360) % 360;
  const lClamped = Math.max(0, Math.min(1, l));

  let low = 0;
  let high = 0.05;

  while (high < 1 && isInSrgbGamut({ l: lClamped, c: high, h: hNorm })) {
    low = high;
    high *= 2;
  }
  high = Math.min(high, 1);

  for (let i = 0; i < 20; i++) {
    const mid = (low + high) / 2;
    if (isInSrgbGamut({ l: lClamped, c: mid, h: hNorm })) {
      low = mid;
    } else {
      high = mid;
    }
  }

  return low;
}

/**
 * Decode CNN output [7] into palette intent.
 * Throws on NaN / Infinity / shape error.
 */
export function decodeCnnOutput(output: Float32Array | number[]): AiPaletteIntent {
  if (output.length < 7) {
    throw new Error(`Expected 7 outputs, got ${output.length}`);
  }

  for (let i = 0; i < 7; i++) {
    if (!isFinite(output[i])) {
      throw new Error(`Non-finite value at output[${i}]: ${output[i]}`);
    }
  }

  const lightness_logit       = output[0];
  const hue_sin_raw            = output[1];
  const hue_cos_raw            = output[2];
  const relative_chroma_logit  = output[3];
  const h0                     = output[4]; // splitComplementary
  const h1                     = output[5]; // complementary
  const h2                     = output[6]; // analogous

  // Decode lightness
  const L = L_MIN + sigmoid(lightness_logit) * (L_MAX - L_MIN);

  // Normalize hue vector
  const norm = Math.sqrt(hue_sin_raw * hue_sin_raw + hue_cos_raw * hue_cos_raw);
  let hueSin: number;
  let hueCos: number;
  if (norm < 1e-8) {
    // Fallback: use 0°
    hueSin = 0;
    hueCos = 1;
  } else {
    hueSin = hue_sin_raw / norm;
    hueCos = hue_cos_raw / norm;
  }

  // Reconstruct hue — atan2(SIN, COS)
  const H = (Math.atan2(hueSin, hueCos) * 180 / Math.PI + 360) % 360;

  // Decode relative chroma
  const relativeChroma = sigmoid(relative_chroma_logit);

  // Compute true sRGB Cmax
  const cMax = maxSrgbChromaAt(L, H);
  const C = relativeChroma * cMax * INTERIOR_MARGIN;

  // Final gamut safety via existing fitToSrgb
  const oklch: OklchColor = fitToSrgb({ l: L, c: C, h: H });

  const baseHex = oklchToHex(oklch);

  // Argmax harmony
  const maxH = Math.max(h0, h1, h2);
  let harmonyIdx = 0;
  if (h1 === maxH) harmonyIdx = 1;
  else if (h2 === maxH) harmonyIdx = 2;

  const harmony = HARMONY_CLASSES[harmonyIdx];

  return { baseHex, harmony };
}

function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}
