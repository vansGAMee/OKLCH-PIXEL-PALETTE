/**
 * rampGenerator.ts
 *
 * Generates perceptually even OKLCH color ramps for pixel art shading.
 * Supports warm, cool, and neutral light presets, plus custom hue shift.
 */
import { hexToOklch, oklchToHex, normalizeHex } from '@/lib/color/conversions';
import { fitToSrgb } from '@/lib/color/gamut';
import type { OklchColor } from '@/types/palette';

export type RampPreset = 'neutral' | 'warm' | 'cool' | 'vivid';
export type HueShiftDirection = 'none' | 'warm-shadow' | 'cool-shadow' | 'custom';

export interface RampConfig {
  baseHex: string;
  count: number;        // 3–9
  /** Hue shift in degrees applied to shadow vs highlight (positive = warm, negative = cool) */
  hueShiftDeg: number;  // -30 to 30
  /** Chroma multiplier for shadows (< 1 = desaturate, > 1 = increase) */
  shadowChromaMult: number;  // 0.5–1.5
  /** Chroma multiplier for highlights */
  highlightChromaMult: number;
  preset?: RampPreset;
}

export interface RampColor {
  hex: string;
  oklch: OklchColor;
  /** 0 = darkest, count-1 = lightest */
  step: number;
  /** 0.0–1.0 normalized position */
  position: number;
  isMidpoint: boolean;
}

export interface GeneratedRamp {
  colors: RampColor[];
  config: RampConfig;
  baseOklch: OklchColor;
}

const PRESETS: Record<RampPreset, Partial<RampConfig>> = {
  neutral:  { hueShiftDeg: 0,   shadowChromaMult: 0.8,  highlightChromaMult: 0.75 },
  warm:     { hueShiftDeg: 20,  shadowChromaMult: 0.9,  highlightChromaMult: 0.65 },
  cool:     { hueShiftDeg: -18, shadowChromaMult: 0.75, highlightChromaMult: 0.8 },
  vivid:    { hueShiftDeg: 0,   shadowChromaMult: 1.1,  highlightChromaMult: 0.9 },
};

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v));
}

function hueShiftedAt(baseHue: number | null, position: number, hueShiftDeg: number): number | null {
  if (baseHue === null) return null;
  // Shift shadows in one direction, highlights in opposite
  // position 0 = darkest shadow, 0.5 = base, 1 = lightest highlight
  const shift = (0.5 - position) * hueShiftDeg * 2;
  return ((baseHue + shift) % 360 + 360) % 360;
}

export function applyPreset(config: RampConfig, preset: RampPreset): RampConfig {
  return { ...config, ...PRESETS[preset], preset };
}

export function generateDefaultConfig(baseHex?: string): RampConfig {
  return {
    baseHex: baseHex ?? '#5b21b6',
    count: 5,
    hueShiftDeg: 0,
    shadowChromaMult: 0.8,
    highlightChromaMult: 0.75,
    preset: 'neutral',
  };
}

export function generateRamp(config: RampConfig): GeneratedRamp | null {
  const normalized = normalizeHex(config.baseHex);
  if (!normalized) return null;

  const baseOklch = hexToOklch(normalized);
  if (!baseOklch) return null;

  const n = clamp(Math.round(config.count), 3, 9);

  // Determine lightness range
  // Base is at midpoint; shadows go lower, highlights go higher
  const midIdx = (n - 1) / 2;
  const lBase = baseOklch.l;

  // Calculate per-step lightness — attempt 10% above and below midpoint per step
  // The actual range depends on base L: darker base → less room below, more above
  const lStep = clamp(0.10, 0.05, 0.15);
  const lMin = clamp(lBase - midIdx * lStep, 0.04, lBase - 0.02);
  const lMax = clamp(lBase + midIdx * lStep, lBase + 0.02, 0.96);

  // Clamp step to fit
  const actualLStep = n > 1 ? (lMax - lMin) / (n - 1) : 0;

  const colors: RampColor[] = [];

  for (let i = 0; i < n; i++) {
    const position = n > 1 ? i / (n - 1) : 0.5;
    const l = clamp(lMin + i * actualLStep, 0.03, 0.97);

    // Chroma: shadows and highlights typically less chromatic than base
    const chromaMult = position <= 0.5
      ? config.shadowChromaMult + (1 - config.shadowChromaMult) * (position * 2)
      : 1 + (config.highlightChromaMult - 1) * ((position - 0.5) * 2);
    const c = clamp(baseOklch.c * chromaMult, 0.0, 0.3);

    const h = hueShiftedAt(baseOklch.h, position, config.hueShiftDeg);

    const fitted = fitToSrgb({ l, c, h });
    const hex = oklchToHex(fitted);
    const exactOklch = hexToOklch(hex) ?? fitted;

    colors.push({
      hex,
      oklch: exactOklch,
      step: i,
      position,
      isMidpoint: Math.round(i) === Math.round(midIdx),
    });
  }

  return { colors, config, baseOklch };
}

export function rampToHexList(ramp: GeneratedRamp): string {
  return ramp.colors.map(c => c.hex.toUpperCase()).join(' ');
}
