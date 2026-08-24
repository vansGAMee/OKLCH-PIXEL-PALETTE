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

export interface PaletteDecoderTensor {
  data: ArrayLike<number>;
  dims: readonly number[];
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
 * Convert a semantic intent {l, relC, hue} into a gamut-safe base hex.
 * relC is relative to the maximum in-gamut chroma at (l, hue).
 */
export function semanticIntentToBase(intent: { l: number; relC: number; hue: number }): string {
  const L = Math.max(0, Math.min(1, intent.l));
  const H = (((intent.hue % 360) + 360) % 360);
  const relC = Math.max(0, Math.min(1, intent.relC));
  const cMax = maxSrgbChromaAt(L, H);
  const C = relC * cMax * INTERIOR_MARGIN;
  return oklchToHex(fitToSrgb({ l: L, c: C, h: H }));
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

/**
 * Decode the PaletteBrain v2 decoder tensor [1, 9, 5]. Each slot contains
 * [lightness logit, relative-chroma logit, hue sin, hue cos, importance].
 *
 * Locked slots bypass model decoding and gamut fitting. They are inputs to the
 * neural decoder as well; this replacement is the final immutability guard.
 */
export function decodePaletteOutput(
  output: PaletteDecoderTensor,
  count: number,
  lockedColors: ReadonlyMap<number, OklchColor> = new Map(),
): OklchColor[] {
  if (!Number.isInteger(count) || count < 2 || count > 9) {
    throw new Error(`Palette count must be an integer from 2 to 9, got ${count}`);
  }

  if (
    output.dims.length !== 3
    || output.dims[0] !== 1
    || output.dims[1] !== 9
    || output.dims[2] !== 5
  ) {
    throw new Error(`Expected palette output shape [1,9,5], got [${output.dims.join(',')}]`);
  }

  if (output.data.length !== 45) {
    throw new Error(`Expected 45 palette output values, got ${output.data.length}`);
  }

  for (let i = 0; i < output.data.length; i++) {
    if (!Number.isFinite(Number(output.data[i]))) {
      throw new Error(`Non-finite value at palette output[${i}]: ${String(output.data[i])}`);
    }
  }

  const colors: OklchColor[] = [];

  for (let slot = 0; slot < count; slot++) {
    const locked = lockedColors.get(slot);
    if (locked) {
      colors.push({ ...locked });
      continue;
    }

    const offset = slot * 5;
    const lightnessLogit = Number(output.data[offset]);
    const chromaLogit = Number(output.data[offset + 1]);
    const hueSinRaw = Number(output.data[offset + 2]);
    const hueCosRaw = Number(output.data[offset + 3]);

    const l = L_MIN + sigmoid(lightnessLogit) * (L_MAX - L_MIN);
    const hueNorm = Math.hypot(hueSinRaw, hueCosRaw);

    // A zero hue vector represents an achromatic slot.
    if (hueNorm < 1e-8) {
      colors.push({ l, c: 0, h: null });
      continue;
    }

    const h = (
      Math.atan2(hueSinRaw / hueNorm, hueCosRaw / hueNorm) * 180 / Math.PI
      + 360
    ) % 360;
    const relativeChroma = sigmoid(chromaLogit);
    const c = relativeChroma * maxSrgbChromaAt(l, h) * INTERIOR_MARGIN;

    colors.push(fitToSrgb({ l, c, h }));
  }

  return colors;
}

function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}
