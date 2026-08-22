/**
 * imageQuantize.ts — client-side only
 *
 * Extracts a reduced pixel palette from an ImageData using median-cut quantization.
 * Merges perceptually near-duplicate colors using OKLCH ΔE.
 * No external uploads. All processing is in the browser.
 */
import { hexToOklch, oklchToHex } from '@/lib/color/conversions';
import { calculateDeltaE } from '@/lib/color/validation';
import { fitToSrgb } from '@/lib/color/gamut';
import type { OklchColor } from '@/types/palette';

export const MAX_IMAGE_PIXELS = 1_048_576; // 1MP limit for performance
export const MAX_FILE_SIZE_MB = 10;

export interface ExtractedColor {
  hex: string;
  oklch: OklchColor;
  frequency: number; // 0–1 proportion of pixels
}

export interface ExtractionResult {
  colors: ExtractedColor[];
  totalPixels: number;
  dominantHex: string;
}

/** Clamp to [0, 255] and convert to hex byte */
function byteHex(n: number): string {
  return Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, '0');
}

function rgbToHex(r: number, g: number, b: number): string {
  return `#${byteHex(r)}${byteHex(g)}${byteHex(b)}`;
}

interface RGBColor {
  r: number; g: number; b: number; count: number;
}

/** Median-cut quantizer — returns N dominant RGB buckets */
function medianCut(pixels: Uint8ClampedArray, targetCount: number): RGBColor[] {
  // Sample every 4th pixel for speed
  const stride = 4;
  const colors: [number, number, number][] = [];
  for (let i = 0; i < pixels.length; i += stride * stride) {
    const r = pixels[i];
    const g = pixels[i + 1];
    const b = pixels[i + 2];
    const a = pixels[i + 3];
    if (a < 128) continue; // skip transparent
    colors.push([r, g, b]);
  }

  if (colors.length === 0) return [];

  // Recursive bucket splitting
  function split(bucket: [number, number, number][], depth: number): RGBColor[] {
    if (depth === 0 || bucket.length <= 1) {
      if (bucket.length === 0) return [];
      const r = bucket.reduce((s, c) => s + c[0], 0) / bucket.length;
      const g = bucket.reduce((s, c) => s + c[1], 0) / bucket.length;
      const b = bucket.reduce((s, c) => s + c[2], 0) / bucket.length;
      return [{ r, g, b, count: bucket.length }];
    }

    // Find widest range channel
    const rRange = Math.max(...bucket.map(c => c[0])) - Math.min(...bucket.map(c => c[0]));
    const gRange = Math.max(...bucket.map(c => c[1])) - Math.min(...bucket.map(c => c[1]));
    const bRange = Math.max(...bucket.map(c => c[2])) - Math.min(...bucket.map(c => c[2]));
    const ch = rRange >= gRange && rRange >= bRange ? 0 : gRange >= bRange ? 1 : 2;

    bucket.sort((a, b) => a[ch] - b[ch]);
    const mid = Math.floor(bucket.length / 2);
    return [
      ...split(bucket.slice(0, mid), depth - 1),
      ...split(bucket.slice(mid), depth - 1),
    ];
  }

  const depth = Math.ceil(Math.log2(targetCount));
  return split(colors, depth).slice(0, targetCount);
}

/** Merge OKLCH near-duplicates (ΔE < threshold) */
function mergeNearDuplicates(colors: ExtractedColor[], threshold = 0.04): ExtractedColor[] {
  const result: ExtractedColor[] = [...colors];
  let merged = true;

  while (merged) {
    merged = false;
    for (let i = 0; i < result.length; i++) {
      for (let j = i + 1; j < result.length; j++) {
        const de = calculateDeltaE(result[i].oklch, result[j].oklch);
        if (de < threshold) {
          // Merge j into i (frequency-weighted average)
          const totalFreq = result[i].frequency + result[j].frequency;
          const wi = result[i].frequency / totalFreq;
          const wj = result[j].frequency / totalFreq;
          const mergedOklch = fitToSrgb({
            l: result[i].oklch.l * wi + result[j].oklch.l * wj,
            c: result[i].oklch.c * wi + result[j].oklch.c * wj,
            h: (() => {
              const hi = result[i].oklch.h;
              const hj = result[j].oklch.h;
              if (hi === null) return hj;
              if (hj === null) return hi;
              let diff = hj - hi;
              if (diff > 180) diff -= 360;
              if (diff < -180) diff += 360;
              return ((hi + diff * wj) + 360) % 360;
            })(),
          });
          const mergedHex = oklchToHex(mergedOklch);
          result[i] = { hex: mergedHex, oklch: mergedOklch, frequency: totalFreq };
          result.splice(j, 1);
          merged = true;
          break;
        }
      }
      if (merged) break;
    }
  }

  return result;
}

/**
 * Extract a pixel art palette from ImageData.
 * @param imageData - raw ImageData from canvas
 * @param targetCount - desired number of colors (3–16)
 * @param mergeThreshold - ΔE below which colors are merged (0.04 = moderate, 0.06 = aggressive)
 */
export function extractPalette(
  imageData: ImageData,
  targetCount: number,
  mergeThreshold = 0.04,
): ExtractionResult {
  const n = Math.max(3, Math.min(16, targetCount));
  const totalPixels = imageData.width * imageData.height;

  // Run median cut with more buckets than needed, then merge
  const buckets = medianCut(imageData.data, n * 3);
  const totalBucketCount = buckets.reduce((s, b) => s + b.count, 0);

  const rawColors: ExtractedColor[] = buckets
    .map(b => {
      const hex = rgbToHex(b.r, b.g, b.b);
      const oklch = hexToOklch(hex) ?? { l: 0.5, c: 0, h: null };
      return { hex, oklch, frequency: b.count / Math.max(1, totalBucketCount) };
    })
    .sort((a, b) => b.frequency - a.frequency);

  // Merge near-dupes
  const merged = mergeNearDuplicates(rawColors, mergeThreshold);

  // Take top N
  const colors = merged
    .sort((a, b) => b.frequency - a.frequency)
    .slice(0, n);

  // Re-normalize frequencies
  const totalFreq = colors.reduce((s, c) => s + c.frequency, 0);
  const normalized = colors.map(c => ({ ...c, frequency: c.frequency / Math.max(0.001, totalFreq) }));

  return {
    colors: normalized,
    totalPixels,
    dominantHex: normalized[0]?.hex ?? '#000000',
  };
}
