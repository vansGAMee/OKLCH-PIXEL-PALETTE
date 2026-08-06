/**
 * src/lib/color/__tests__/qualityInspector.test.ts
 */
import { describe, test, expect } from 'vitest';
import { inspectPalette } from '../qualityInspector';
import type { Palette, PaletteColor } from '@/types/palette';

function makeColor(hex: string, l: number, c: number, h: number | null, role = 'base'): PaletteColor {
  return { role, hex, oklch: { l, c, h } };
}

function makePalette(colors: PaletteColor[]): Palette {
  return {
    colors,
    count: colors.length,
    shadow: colors[0],
    base: colors[Math.floor(colors.length / 2)],
    highlight: colors[colors.length - 1],
    accent: colors[colors.length - 1],
    harmony: 'analogous',
    seed: 1,
  };
}

describe('qualityInspector', () => {
  test('returns no warnings for a good palette', () => {
    const colors = [
      makeColor('#1e1b4b', 0.18, 0.12, 280, 'shadow'),
      makeColor('#5b21b6', 0.42, 0.22, 290, 'base'),
      makeColor('#a855f7', 0.65, 0.20, 295, 'highlight'),
      makeColor('#f43f5e', 0.60, 0.22, 10, 'accent'),
    ];
    const report = inspectPalette(makePalette(colors));
    const errorOrWarning = report.warnings.filter((w) => w.severity !== 'info');
    expect(errorOrWarning).toHaveLength(0);
    expect(report.hasErrors).toBe(false);
  });

  test('detects duplicate colors', () => {
    const hex = '#a855f7';
    const colors = [
      makeColor(hex, 0.65, 0.20, 295, 'shadow'),
      makeColor(hex, 0.65, 0.20, 295, 'base'),
      makeColor('#1e1b4b', 0.18, 0.12, 280, 'highlight'),
    ];
    const report = inspectPalette(makePalette(colors));
    const dupe = report.warnings.find((w) => w.id.startsWith('duplicate'));
    expect(dupe).toBeDefined();
    expect(dupe!.severity).toBe('error');
    expect(report.hasErrors).toBe(true);
  });

  test('detects near-duplicate colors', () => {
    const colors = [
      makeColor('#a855f7', 0.65, 0.20, 295, 'shadow'),
      makeColor('#a856f7', 0.65, 0.20, 295.1, 'base'), // Very close (deltaE < 8)
      makeColor('#1e1b4b', 0.18, 0.12, 280, 'highlight'),
    ];
    const report = inspectPalette(makePalette(colors));
    const nearDupe = report.warnings.find((w) => w.id.startsWith('near_dup'));
    expect(nearDupe).toBeDefined();
    expect(nearDupe!.severity).toBe('warning');
  });

  test('detects narrow lightness range', () => {
    const colors = [
      makeColor('#6d28d9', 0.42, 0.22, 290, 'shadow'),
      makeColor('#7c3aed', 0.44, 0.22, 290, 'base'),
      makeColor('#8b5cf6', 0.58, 0.20, 292, 'highlight'),
    ];
    const report = inspectPalette(makePalette(colors));
    const spread = report.warnings.find((w) => w.id === 'lightness_spread');
    expect(spread).toBeDefined();
  });

  test('does not flag good lightness range', () => {
    const colors = [
      makeColor('#1e1b4b', 0.18, 0.12, 280, 'shadow'),
      makeColor('#7c3aed', 0.50, 0.22, 290, 'base'),
      makeColor('#e9d5ff', 0.88, 0.08, 298, 'highlight'),
    ];
    const report = inspectPalette(makePalette(colors));
    const spread = report.warnings.find((w) => w.id === 'lightness_spread');
    expect(spread).toBeUndefined();
  });

  test('detects all-neutral palette', () => {
    const colors = [
      makeColor('#1a1a1a', 0.15, 0.005, null, 'shadow'),
      makeColor('#808080', 0.50, 0.005, null, 'base'),
      makeColor('#e0e0e0', 0.88, 0.005, null, 'highlight'),
    ];
    const report = inspectPalette(makePalette(colors));
    const neutral = report.warnings.find((w) => w.id === 'all_neutral');
    expect(neutral).toBeDefined();
    expect(neutral!.severity).toBe('info');
  });
});
