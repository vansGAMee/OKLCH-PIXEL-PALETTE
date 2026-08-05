import { describe, expect, it } from 'vitest';
import { generatePalette } from '../generator';
import { HarmonyMode } from '@/types/palette';
import { calculateDeltaE, validatePalette } from '../validation';
import { isValidHex } from '../conversions';

const TEST_INPUT_COLORS = [
  '#ff0000',
  '#00ff00',
  '#0000ff',
  '#f2c94c',
  '#121212',
  '#f7f7f7',
  '#808080',
  '#5b21b6',
];

const HARMONY_MODES: HarmonyMode[] = ['splitComplementary', 'complementary', 'analogous'];

describe('Color Palette Generator Engine', () => {
  it.each(TEST_INPUT_COLORS)('generates valid palette for %s without throwing or NaN', (hex) => {
    for (const harmony of HARMONY_MODES) {
      const palette = generatePalette(hex, harmony, 42);

      // Verify no exceptions and valid structure
      expect(palette).toBeDefined();
      expect(palette.shadow).toBeDefined();
      expect(palette.base).toBeDefined();
      expect(palette.highlight).toBeDefined();
      expect(palette.accent).toBeDefined();

      // Verify HEX validity
      expect(isValidHex(palette.shadow.hex)).toBe(true);
      expect(isValidHex(palette.base.hex)).toBe(true);
      expect(isValidHex(palette.highlight.hex)).toBe(true);
      expect(isValidHex(palette.accent.hex)).toBe(true);

      // Verify Base Preservation
      expect(palette.base.hex.toLowerCase()).toBe(hex.toLowerCase());

      // Verify NaN absence
      for (const col of [palette.shadow, palette.base, palette.highlight, palette.accent]) {
        expect(isNaN(col.oklch.l)).toBe(false);
        expect(isNaN(col.oklch.c)).toBe(false);
        if (col.oklch.h !== null) {
          expect(isNaN(col.oklch.h)).toBe(false);
        }
      }

      // Verify lightness hierarchy
      expect(palette.shadow.oklch.l).toBeLessThan(palette.base.oklch.l);
      expect(palette.base.oklch.l).toBeLessThan(palette.highlight.oklch.l);

      // Verify full validation rules
      const val = validatePalette({
        shadow: palette.shadow.oklch,
        base: palette.base.oklch,
        highlight: palette.highlight.oklch,
        accent: palette.accent.oklch,
      });

      expect(val.issues).toEqual([]);
      expect(val.isValid).toBe(true);
    }
  });

  it('guarantees deterministic output for identical seeds', () => {
    const hex = '#5b21b6';
    const seed = 1337;

    const p1 = generatePalette(hex, 'splitComplementary', seed);
    const p2 = generatePalette(hex, 'splitComplementary', seed);

    expect(p1.shadow.hex).toBe(p2.shadow.hex);
    expect(p1.base.hex).toBe(p2.base.hex);
    expect(p1.highlight.hex).toBe(p2.highlight.hex);
    expect(p1.accent.hex).toBe(p2.accent.hex);
  });

  it('handles dark base #121212 without producing 4 almost black colors', () => {
    const palette = generatePalette('#121212', 'splitComplementary', 0);
    // Base is dark, but highlight and accent should have clear visual separation
    expect(palette.highlight.oklch.l).toBeGreaterThan(palette.base.oklch.l + 0.15);
    expect(palette.accent.oklch.l).toBeGreaterThan(0.30);
    expect(palette.accent.oklch.c).toBeGreaterThan(0.08); // Accent must be colorful
  });

  it('handles bright base #f7f7f7 without producing 4 almost white colors', () => {
    const palette = generatePalette('#f7f7f7', 'splitComplementary', 0);
    // Base is very light, shadow and accent must step down in lightness
    expect(palette.shadow.oklch.l).toBeLessThan(palette.base.oklch.l - 0.15);
    expect(palette.accent.oklch.l).toBeLessThan(0.70);
    expect(palette.accent.oklch.c).toBeGreaterThan(0.08); // Accent must be colorful
  });

  it('handles gray base #808080 properly with colorful accent', () => {
    const palette = generatePalette('#808080', 'splitComplementary', 0);
    expect(palette.shadow.oklch.l).toBeLessThan(palette.base.oklch.l);
    expect(palette.highlight.oklch.l).toBeGreaterThan(palette.base.oklch.l);
    expect(palette.accent.oklch.c).toBeGreaterThan(0.08);
  });

  it('provides different variations with different seeds', () => {
    const hex = '#f2c94c';
    const p1 = generatePalette(hex, 'splitComplementary', 10);
    const p2 = generatePalette(hex, 'splitComplementary', 99);

    // Either shadow, highlight, or accent will vary within constraints
    const isDifferent =
      p1.shadow.hex !== p2.shadow.hex ||
      p1.highlight.hex !== p2.highlight.hex ||
      p1.accent.hex !== p2.accent.hex;

    expect(isDifferent).toBe(true);
    // Base remains exact
    expect(p1.base.hex).toBe(p2.base.hex);
  });
});
