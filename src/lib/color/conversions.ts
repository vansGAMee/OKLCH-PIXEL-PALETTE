import { converter, formatHex, parse } from 'culori';
import { OklchColor } from '@/types/palette';

const toOklch = converter('oklch');

/**
 * Normalizes input string into a standard 6-digit hex string (#rrggbb)
 */
export function normalizeHex(input: string): string | null {
  if (!input) return null;
  let clean = input.trim().replace(/^#/, '');

  if (clean.length === 3) {
    clean = clean.split('').map((char) => char + char).join('');
  }

  if (!/^[0-9a-fA-F]{6}$/.test(clean)) {
    return null;
  }

  return `#${clean.toLowerCase()}`;
}

/**
 * Validates whether string is a valid HEX color.
 */
export function isValidHex(hex: string): boolean {
  return normalizeHex(hex) !== null;
}

/**
 * Converts a HEX string or culori color object into OKLCH object { l, c, h }
 */
export function hexToOklch(hex: string): OklchColor | null {
  const normHex = normalizeHex(hex);
  if (!normHex) return null;

  const parsed = parse(normHex);
  if (!parsed) return null;

  const oklch = toOklch(parsed);
  if (!oklch) return null;

  const l = Math.max(0, Math.min(1, oklch.l ?? 0));
  const c = Math.max(0, oklch.c ?? 0);
  let h: number | null = oklch.h !== undefined && !isNaN(oklch.h) ? oklch.h : null;

  // Handle neutral colors (chroma < 0.001 or undefined hue)
  if (c < 0.001 || h === null) {
    h = null;
  } else {
    h = (h % 360 + 360) % 360;
  }

  return { l, c, h };
}

/**
 * Converts an OKLCH color object to HEX string using culori.
 */
export function oklchToHex(color: OklchColor): string {
  const modeObj = {
    mode: 'oklch' as const,
    l: Math.max(0, Math.min(1, color.l)),
    c: Math.max(0, color.c),
    h: color.h === null ? 0 : (color.h % 360 + 360) % 360,
  };

  const formatted = formatHex(modeObj);
  return formatted || '#000000';
}

/**
 * Calculates shortest angle distance on hue circle (0..360)
 */
export function angleDiff(a: number, b: number): number {
  const diff = Math.abs(a - b) % 360;
  return diff > 180 ? 360 - diff : diff;
}

/**
 * Shifts hue along the shortest path toward targetHue by maxDeg degrees.
 */
export function shiftHueToward(currentHue: number | null, targetHue: number, maxDeg: number): number {
  if (currentHue === null) return targetHue;

  const cur = (currentHue % 360 + 360) % 360;
  const target = (targetHue % 360 + 360) % 360;

  let diff = target - cur;
  if (diff > 180) diff -= 360;
  if (diff < -180) diff += 360;

  const actualShift = Math.sign(diff) * Math.min(Math.abs(diff), maxDeg);
  return (cur + actualShift + 360) % 360;
}
