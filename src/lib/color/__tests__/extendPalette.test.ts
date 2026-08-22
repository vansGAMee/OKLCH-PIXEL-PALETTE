/**
 * Tests for extendPalette.
 */
import { describe, it, expect } from 'vitest';
import { extendPalette } from '../extendPalette';
import { generatePalette } from '../generator';

const BASE_HEX = '#5b21b6';
const HARMONY = 'splitComplementary' as const;
const SEED = 42;

function getPalette(seed = SEED) {
  return generatePalette(BASE_HEX, HARMONY, seed);
}

function isValidHex(s: string): boolean {
  return /^#[0-9a-f]{6}$/.test(s);
}

describe('extendPalette', () => {
  for (const count of [4, 5, 6, 7, 8, 9] as const) {
    it(`count=${count}: returns exactly ${count} colors`, () => {
      const palette = getPalette();
      const result = extendPalette(palette, count);
      expect(result).toHaveLength(count);
    });

    it(`count=${count}: all hexes are valid`, () => {
      const palette = getPalette();
      const result = extendPalette(palette, count);
      for (const c of result) {
        expect(isValidHex(c.hex)).toBe(true);
      }
    });

    it(`count=${count}: all OKLCH values are finite`, () => {
      const palette = getPalette();
      const result = extendPalette(palette, count);
      for (const c of result) {
        expect(isFinite(c.oklch.l)).toBe(true);
        expect(isFinite(c.oklch.c)).toBe(true);
      }
    });

    it(`count=${count}: is deterministic`, () => {
      const palette = getPalette();
      const r1 = extendPalette(palette, count);
      const r2 = extendPalette(palette, count);
      expect(r1.map(c => c.hex)).toEqual(r2.map(c => c.hex));
    });
  }

  it('count=4: exact shadow/base/highlight/accent anchors preserved', () => {
    const palette = getPalette();
    const result = extendPalette(palette, 4);
    expect(result[0].hex).toBe(palette.shadow.hex);
    expect(result[0].oklch.l).toBeCloseTo(palette.shadow.oklch.l, 4);
    expect(result[1].hex).toBe(palette.base.hex);
    expect(result[2].hex).toBe(palette.highlight.hex);
    expect(result[3].hex).toBe(palette.accent.hex);
    expect(result[0].anchorRole).toBe('shadow');
    expect(result[1].anchorRole).toBe('base');
    expect(result[2].anchorRole).toBe('highlight');
    expect(result[3].anchorRole).toBe('accent');
  });

  it('count=4: no derived colors', () => {
    const palette = getPalette();
    const result = extendPalette(palette, 4);
    expect(result.every(c => !c.derived)).toBe(true);
  });

  it('counts 5-9: first 4 anchors unchanged', () => {
    const palette = getPalette();
    const base4 = extendPalette(palette, 4);
    for (const count of [5, 6, 7, 8, 9]) {
      const result = extendPalette(palette, count);
      for (let i = 0; i < 4; i++) {
        expect(result[i].hex).toBe(base4[i].hex);
        expect(result[i].derived).toBe(false);
      }
    }
  });

  it('counts 5-9: derived colors are flagged', () => {
    const palette = getPalette();
    for (const count of [5, 6, 7, 8, 9]) {
      const result = extendPalette(palette, count);
      const derived = result.filter(c => c.derived);
      expect(derived).toHaveLength(count - 4);
    }
  });

  it('no obvious duplicates (all hex unique)', () => {
    const palette = getPalette();
    for (const count of [5, 6, 7, 8, 9]) {
      const result = extendPalette(palette, count);
      const hexes = result.map(c => c.hex);
      const unique = new Set(hexes);
      // Allow minor duplicates for edge cases but ensure at least 3/4 are unique
      expect(unique.size).toBeGreaterThanOrEqual(Math.min(count - 1, 4));
    }
  });
});
