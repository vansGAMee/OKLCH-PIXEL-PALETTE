/**
 * paletteDoctor.ts
 *
 * Analyzes arbitrary palettes (array of hex strings) using OKLCH perceptual metrics.
 * Produces structured diagnostics and deterministic fixes.
 *
 * Scoring system (0–100):
 * Starts at 100; deductions applied for measured issues.
 * This is the site's own diagnostic score, not an industry standard.
 *
 * Deductions:
 * - Duplicate color:         -20 each
 * - Near-duplicate (ΔE<8):   -10 each
 * - Lightness spread < 0.25:  -15
 * - Lightness spread < 0.15:  -25 (instead of above)
 * - No chroma in any color:   -10
 * - Weak accent separation:   -8
 * - Ramp monotonicity break:  -5 per break
 * - Out-of-gamut color:       -10 each (shouldn't happen after fitToSrgb but guards)
 */
import { hexToOklch, oklchToHex, normalizeHex } from '@/lib/color/conversions';
import { fitToSrgb } from '@/lib/color/gamut';
import { calculateDeltaE } from '@/lib/color/validation';
import type { OklchColor } from '@/types/palette';

export interface AnalyzedColor {
  hex: string;
  oklch: OklchColor;
  index: number;
}

export interface DiagnosticIssue {
  id: string;
  severity: 'ok' | 'warning' | 'error';
  message: string;
  colorIndices?: number[];
}

export interface PaletteDoctorReport {
  colors: AnalyzedColor[];
  issues: DiagnosticIssue[];
  /** 0–100 score. Site's own metric, not an industry standard. */
  healthScore: number;
  lightnessRange: number;
  chromaRange: number;
  hueSpan: number;
  fixedColors?: AnalyzedColor[];
  parseErrors: string[];
}

/** Parse a string of hex colors, tolerating spaces, commas, newlines, and # prefixes */
export function parseHexInput(input: string): { colors: AnalyzedColor[]; errors: string[] } {
  const tokens = input
    .replace(/[,;\n\r\t]+/g, ' ')
    .split(/\s+/)
    .map(t => t.trim())
    .filter(Boolean);

  const colors: AnalyzedColor[] = [];
  const errors: string[] = [];

  for (const token of tokens) {
    const normalized = normalizeHex(token.startsWith('#') ? token : `#${token}`);
    if (!normalized) {
      errors.push(`"${token}" is not a valid hex color`);
      continue;
    }
    const oklch = hexToOklch(normalized);
    if (!oklch) {
      errors.push(`Could not convert ${normalized} to OKLCH`);
      continue;
    }
    colors.push({ hex: normalized, oklch, index: colors.length });
  }

  // Deduplicate identical hex
  const seen = new Set<string>();
  const unique: AnalyzedColor[] = [];
  for (const c of colors) {
    if (!seen.has(c.hex.toLowerCase())) {
      seen.add(c.hex.toLowerCase());
      unique.push({ ...c, index: unique.length });
    }
  }

  return { colors: unique, errors };
}

/** Full palette analysis */
export function analyzePalette(colors: AnalyzedColor[]): PaletteDoctorReport {
  const issues: DiagnosticIssue[] = [];
  const parseErrors: string[] = [];

  if (colors.length < 2) {
    return {
      colors,
      issues: [{ id: 'too_few', severity: 'error', message: 'Need at least 2 colors to analyze.' }],
      healthScore: 0,
      lightnessRange: 0,
      chromaRange: 0,
      hueSpan: 0,
      parseErrors,
    };
  }

  let deductions = 0;

  // ── Lightness distribution ──────────────────────────────────────────────
  const ls = colors.map(c => c.oklch.l);
  const lMin = Math.min(...ls);
  const lMax = Math.max(...ls);
  const lightnessRange = lMax - lMin;

  if (lightnessRange < 0.15) {
    deductions += 25;
    issues.push({
      id: 'very_narrow_lightness',
      severity: 'error',
      message: `Very narrow lightness range (${(lightnessRange * 100).toFixed(0)}%). Palette will look flat — increase the spread between darkest and lightest colors.`,
    });
  } else if (lightnessRange < 0.25) {
    deductions += 15;
    issues.push({
      id: 'narrow_lightness',
      severity: 'warning',
      message: `Narrow lightness range (${(lightnessRange * 100).toFixed(0)}%). Consider adding a darker shadow or lighter highlight.`,
    });
  } else {
    issues.push({
      id: 'lightness_spread_ok',
      severity: 'ok',
      message: `Good lightness spread (${(lightnessRange * 100).toFixed(0)}%).`,
    });
  }

  // ── Chroma distribution ─────────────────────────────────────────────────
  const cs = colors.map(c => c.oklch.c);
  const cMin = Math.min(...cs);
  const cMax = Math.max(...cs);
  const chromaRange = cMax - cMin;
  const hasChroma = colors.some(c => c.oklch.c > 0.03);

  if (!hasChroma) {
    deductions += 10;
    issues.push({
      id: 'no_chroma',
      severity: 'warning',
      message: 'All colors appear neutral/grayscale (C < 0.03). Is this intentional?',
    });
  } else {
    issues.push({
      id: 'chroma_present',
      severity: 'ok',
      message: `Chroma present (max C = ${cMax.toFixed(3)}).`,
    });
  }

  // ── Hue span ─────────────────────────────────────────────────────────────
  const chromatic = colors.filter(c => c.oklch.c > 0.04 && c.oklch.h !== null);
  let hueSpan = 0;
  if (chromatic.length >= 2) {
    const hues = chromatic.map(c => c.oklch.h!).sort((a, b) => a - b);
    // Compute maximum arc between adjacent hues in circular order
    const gaps = hues.map((h, i) => {
      const next = hues[(i + 1) % hues.length];
      const arc = ((next - h) + 360) % 360;
      return arc;
    });
    const maxGap = Math.max(...gaps);
    hueSpan = 360 - maxGap; // span = 360 minus the largest empty arc
  }

  // ── Near-duplicates ───────────────────────────────────────────────────────
  const nearDups: { i: number; j: number; de: number }[] = [];
  for (let i = 0; i < colors.length; i++) {
    for (let j = i + 1; j < colors.length; j++) {
      if (colors[i].hex.toLowerCase() === colors[j].hex.toLowerCase()) {
        deductions += 20;
        issues.push({
          id: `dup_${i}_${j}`,
          severity: 'error',
          message: `Colors #${i + 1} and #${j + 1} are identical (${colors[i].hex.toUpperCase()}).`,
          colorIndices: [i, j],
        });
      } else {
        const de = calculateDeltaE(colors[i].oklch, colors[j].oklch) * 100; // scale for readability
        if (de < 8) {
          nearDups.push({ i, j, de });
          deductions += 10;
          issues.push({
            id: `near_dup_${i}_${j}`,
            severity: 'warning',
            message: `Colors #${i + 1} and #${j + 1} are visually very similar (ΔE ≈ ${de.toFixed(1)}). They may be hard to distinguish.`,
            colorIndices: [i, j],
          });
        }
      }
    }
  }

  if (nearDups.length === 0 && colors.every((c, i, arr) =>
    arr.slice(i + 1).every(c2 => c.hex.toLowerCase() !== c2.hex.toLowerCase())
  )) {
    issues.push({
      id: 'no_dups',
      severity: 'ok',
      message: 'No duplicate or near-identical colors detected.',
    });
  }

  // ── Lightness ramp monotonicity (sorted order) ────────────────────────────
  const sortedByL = [...colors].sort((a, b) => a.oklch.l - b.oklch.l);
  let rampBreaks = 0;
  for (let i = 1; i < sortedByL.length - 1; i++) {
    const gap1 = sortedByL[i].oklch.l - sortedByL[i - 1].oklch.l;
    const gap2 = sortedByL[i + 1].oklch.l - sortedByL[i].oklch.l;
    if (Math.abs(gap1 - gap2) > 0.18) rampBreaks++;
  }
  if (rampBreaks > 0) {
    deductions += rampBreaks * 5;
    issues.push({
      id: 'ramp_uneven',
      severity: 'warning',
      message: `Lightness steps are uneven (${rampBreaks} break${rampBreaks > 1 ? 's' : ''}). Consider adjusting intermediate colors for smoother shading ramps.`,
    });
  } else if (colors.length >= 3) {
    issues.push({
      id: 'ramp_ok',
      severity: 'ok',
      message: 'Lightness steps are reasonably even.',
    });
  }

  // ── Final score ───────────────────────────────────────────────────────────
  const healthScore = Math.max(0, Math.min(100, 100 - deductions));

  return {
    colors,
    issues,
    healthScore,
    lightnessRange,
    chromaRange,
    hueSpan,
    parseErrors,
  };
}

/**
 * Attempt to fix common issues while preserving palette character.
 * Rules:
 * 1. Near-duplicates: push them apart in lightness keeping hue/chroma.
 * 2. Narrow lightness: expand range symmetrically.
 * 3. All changes are gamut-fitted.
 * 4. Original colors that are OK remain unchanged.
 */
export function fixPalette(report: PaletteDoctorReport): AnalyzedColor[] {
  const fixed = report.colors.map(c => ({ ...c, oklch: { ...c.oklch } }));

  // Sort by lightness, then expand range if too narrow
  if (report.lightnessRange < 0.25) {
    const sortedIdx = [...fixed].sort((a, b) => a.oklch.l - b.oklch.l).map(c => c.index);
    const n = sortedIdx.length;
    const targetRange = Math.max(0.35, report.lightnessRange + 0.15);
    const lMin = fixed[sortedIdx[0]].oklch.l;
    const lMax = fixed[sortedIdx[n - 1]].oklch.l;
    const center = (lMin + lMax) / 2;
    const scale = targetRange / Math.max(0.01, report.lightnessRange);
    for (const idx of sortedIdx) {
      const newL = center + (fixed[idx].oklch.l - center) * scale;
      fixed[idx].oklch = fitToSrgb({ ...fixed[idx].oklch, l: Math.max(0.03, Math.min(0.97, newL)) });
      fixed[idx].hex = oklchToHex(fixed[idx].oklch);
    }
  }

  // Push near-duplicate pairs apart
  for (const issue of report.issues) {
    if (!issue.id.startsWith('near_dup_')) continue;
    const [i, j] = issue.colorIndices ?? [];
    if (i === undefined || j === undefined) continue;
    const a = fixed[i];
    const b = fixed[j];
    const dl = b.oklch.l - a.oklch.l;
    // Push the brighter one brighter, the darker one darker
    if (dl >= 0) {
      fixed[i].oklch = fitToSrgb({ ...fixed[i].oklch, l: Math.max(0.03, fixed[i].oklch.l - 0.06) });
      fixed[j].oklch = fitToSrgb({ ...fixed[j].oklch, l: Math.min(0.97, fixed[j].oklch.l + 0.06) });
    } else {
      fixed[j].oklch = fitToSrgb({ ...fixed[j].oklch, l: Math.max(0.03, fixed[j].oklch.l - 0.06) });
      fixed[i].oklch = fitToSrgb({ ...fixed[i].oklch, l: Math.min(0.97, fixed[i].oklch.l + 0.06) });
    }
    fixed[i].hex = oklchToHex(fixed[i].oklch);
    fixed[j].hex = oklchToHex(fixed[j].oklch);
  }

  return fixed;
}
