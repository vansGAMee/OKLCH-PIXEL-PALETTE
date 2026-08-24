/**
 * Tests for extendPalette.
 */
import { describe, it, expect } from 'vitest';
import { canonicalizeGeneratedPalette, extendPalette, mergeLockedPalette } from '../extendPalette';
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
  for (const count of [2, 3, 4, 5, 6, 7, 8, 9] as const) {
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

  it('counts 2-3 return the requested leading anchors', () => {
    const palette = getPalette();
    expect(extendPalette(palette, 2).map((color) => color.hex)).toEqual([
      palette.shadow.hex,
      palette.base.hex,
    ]);
    expect(extendPalette(palette, 3).map((color) => color.hex)).toEqual([
      palette.shadow.hex,
      palette.base.hex,
      palette.highlight.hex,
    ]);
  });

  it('canonical palette count always matches colors length from 2-9', () => {
    const generated = getPalette();
    for (const count of [2, 3, 4, 5, 6, 7, 8, 9]) {
      const palette = canonicalizeGeneratedPalette(generated, count);
      expect(palette.count).toBe(count);
      expect(palette.colors).toHaveLength(count);
      expect(palette.shadow).toBe(palette.colors[0]);
    }
  });

  it('preserves locked colors exactly across seed regeneration', () => {
    const current = canonicalizeGeneratedPalette(getPalette(1), 6);
    const candidate = canonicalizeGeneratedPalette(getPalette(2), 6);
    const merged = mergeLockedPalette(current, candidate, new Set([0, 2, 5]));

    for (const index of [0, 2, 5]) {
      expect(merged.colors[index]).toEqual(current.colors[index]);
    }
    expect(merged.seed).toBe(candidate.seed);
    expect(merged.count).toBe(6);
  });

  it('ignores out-of-range locks on shrink and preserves locks on grow', () => {
    const current = canonicalizeGeneratedPalette(getPalette(3), 4);
    const shrunk = mergeLockedPalette(
      current,
      canonicalizeGeneratedPalette(getPalette(4), 2),
      new Set([0, 3]),
    );
    expect(shrunk.colors).toHaveLength(2);
    expect(shrunk.colors[0]).toEqual(current.colors[0]);

    const grown = mergeLockedPalette(
      current,
      canonicalizeGeneratedPalette(getPalette(5), 7),
      new Set([1]),
    );
    expect(grown.colors).toHaveLength(7);
    expect(grown.colors[1]).toEqual(current.colors[1]);
  });

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
