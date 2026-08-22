import { describe, it, expect } from 'vitest';
import { generatePalette } from '../generator';
import { extendPalette } from '../extendPalette';
import { validatePalette, calculateDeltaE } from '../validation';
import { hexToOklch, oklchToHex, normalizeHex } from '../conversions';
import { fitToSrgb } from '../gamut';
import { exportPalettePng } from '../exportPalettePng';
import { getOklchColorName, getPaletteColorLabel } from '../colorNaming';
import { HarmonyMode } from '@/types/palette';

describe('OKLCH Pixel Palette Engine', () => {
  describe('Gamut and Conversions', () => {
    it('preserves L in [0, 1] for fitToSrgb', () => {
      const black = fitToSrgb({ l: 0, c: 0, h: null });
      expect(black.l).toBe(0);
      expect(black.c).toBe(0);

      const white = fitToSrgb({ l: 1, c: 0, h: null });
      expect(white.l).toBe(1);
      expect(white.c).toBe(0);
    });

    it('correctly normalizes HEX strings', () => {
      expect(normalizeHex('#5b21b6')).toBe('#5b21b6');
      expect(normalizeHex('ff0000')).toBe('#ff0000');
      expect(normalizeHex('#FFF')).toBe('#ffffff');
      expect(normalizeHex('invalid')).toBeNull();
    });

    it('converts HEX <-> OKLCH accurately', () => {
      const oklch = hexToOklch('#ff0000');
      expect(oklch).not.toBeNull();
      if (oklch) {
        const hex = oklchToHex(oklch);
        expect(hex.toLowerCase()).toBe('#ff0000');
      }
    });
  });

  describe('Base Preservation & Reverse Conversion', () => {
    it('preserves Base HEX and OKLCH exactly', () => {
      const inputHex = '#5b21b6';
      const palette = generatePalette(inputHex, 'splitComplementary', 0);
      
      expect(palette.base.hex.toLowerCase()).toBe('#5b21b6');
      const recomputedHex = oklchToHex(palette.base.oklch);
      expect(recomputedHex.toLowerCase()).toBe('#5b21b6');
    });
  });

  describe('Mandatory Test Colors Suite', () => {
    const mandatoryColors = [
      '#000000',
      '#010101',
      '#121212',
      '#808080',
      '#f7f7f7',
      '#fefefe',
      '#ffffff',
      '#ff0000',
      '#00ff00',
      '#0000ff',
      '#f2c94c',
      '#5b21b6',
    ];

    const harmonies: HarmonyMode[] = ['splitComplementary', 'complementary', 'analogous'];

    for (const colorHex of mandatoryColors) {
      for (const harmony of harmonies) {
        it(`generates valid palette for mandatory color ${colorHex} with ${harmony} harmony`, () => {
          const palette = generatePalette(colorHex, harmony, 0);
          
          // 1. Base preservation
          expect(palette.base.hex.toLowerCase()).toBe(colorHex.toLowerCase());
          expect(oklchToHex(palette.base.oklch).toLowerCase()).toBe(colorHex.toLowerCase());

          // 2. Palette validation
          const validation = validatePalette(palette);
          expect(validation.isValid).toBe(true);

          // 3. Boundary mode assertions
          if (palette.base.oklch.l <= 0.02) {
            expect(validation.boundaryMode).toBe('black-base');
          } else if (palette.base.oklch.l >= 0.98) {
            expect(validation.boundaryMode).toBe('white-base');
          }
        });
      }
    }
  });

  describe('Deterministic Mass Test (1000+ Palettes)', () => {
    it('passes validation for > 300 deterministic color combinations without Math.random()', () => {
      const hues = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330];
      const lightnesses = [0.1, 0.3, 0.5, 0.7, 0.9];
      const chromas = [0.05, 0.15];
      const harmonies: HarmonyMode[] = ['splitComplementary', 'complementary', 'analogous'];
      const seeds = [0, 1, 42];

      let count = 0;

      for (const h of hues) {
        for (const l of lightnesses) {
          for (const c of chromas) {
            for (const harmony of harmonies) {
              for (const seed of seeds) {
                const hex = oklchToHex({ l, c, h });
                const palette = generatePalette(hex, harmony, seed);

                const validation = validatePalette(palette);
                expect(validation.isValid).toBe(true);

                const reverseHex = oklchToHex(palette.base.oklch);
                expect(reverseHex.toLowerCase()).toBe(palette.base.hex.toLowerCase());

                count++;
              }
            }
          }
        }
      }

      expect(count).toBeGreaterThanOrEqual(300);
    });
  });

  describe('Flexible Palette Sizes (4 to 9 Colors via extendPalette)', () => {
    it('generates exact 4 core anchors for generatePalette', () => {
      const p4 = generatePalette('#5b21b6', 'splitComplementary', 0);
      expect(p4.count).toBe(4);
      expect(p4.colors.length).toBe(4);
      expect(p4.shadow).toBe(p4.colors[0]);
      expect(p4.base).toBe(p4.colors[1]);
      expect(p4.highlight).toBe(p4.colors[2]);
      expect(p4.accent).toBe(p4.colors[3]);
    });

    it('extendPalette produces exact requested counts 4 to 9', () => {
      const p = generatePalette('#5b21b6', 'splitComplementary', 0);
      for (const count of [4, 5, 6, 7, 8, 9]) {
        const ext = extendPalette(p, count);
        expect(ext.length).toBe(count);
      }
    });

    it('guarantees unique React keys for palette grid cards across all sizes', () => {
      const palette = generatePalette('#5b21b6', 'splitComplementary', 0);
      for (let size = 4; size <= 9; size++) {
        const ext = extendPalette(palette, size);
        const keys = ext.map((c, idx) => `${c.role}-${idx}`);
        const uniqueKeys = new Set(keys);
        expect(uniqueKeys.size).toBe(ext.length);
      }
    });

    it('runs exportPalettePng for 4, 6, and 9 colors without error in node environment', () => {
      const palette = generatePalette('#5b21b6', 'splitComplementary', 0);
      for (const count of [4, 6, 9]) {
        const ext = extendPalette(palette, count);
        const extendedPalette = { ...palette, count, colors: ext };
        expect(() => exportPalettePng(extendedPalette)).not.toThrow();
      }
    });
  });

  describe('Deduplication & Minimum Distance (100+ 9-Color Palettes)', () => {
    it('guarantees no duplicate HEX codes and Delta E >= 0.025 across 100+ 9-color palettes', () => {
      const testHexes = ['#5b21b6', '#ff0000', '#00ff00', '#0000ff', '#f2c94c', '#808080', '#121212', '#f7f7f7'];
      const harmonies: HarmonyMode[] = ['splitComplementary', 'complementary', 'analogous'];
      const seeds = [0, 1, 2, 3, 4, 5];

      let totalPalettes = 0;

      for (const hex of testHexes) {
        for (const harmony of harmonies) {
          for (const seed of seeds) {
            const palette = generatePalette(hex, harmony, seed);
            const ext = extendPalette(palette, 9);
            totalPalettes++;

            // 1. Assert exact count
            expect(ext.length).toBe(9);

            // 2. Assert no duplicate HEX strings
            const hexes = ext.map((c) => c.hex.toLowerCase());
            const uniqueHexes = new Set(hexes);
            expect(uniqueHexes.size).toBe(9);

            // 3. Assert pairwise Delta E >= MIN_PALETTE_DELTA_E (0.025)
            for (let i = 0; i < 9; i++) {
              for (let j = i + 1; j < 9; j++) {
                const delta = calculateDeltaE(ext[i].oklch, ext[j].oklch);
                if (delta < 0.025) {
                  console.log('Failing pair:', hex, harmony, seed, 'i=', i, ext[i].role, ext[i].hex, 'j=', j, ext[j].role, ext[j].hex, 'delta=', delta);
                }
                expect(delta).toBeGreaterThanOrEqual(0.025);
              }
            }
          }
        }
      }

      expect(totalPalettes).toBeGreaterThanOrEqual(100);
    });
  });

  describe('Human-Readable OKLCH Color Naming', () => {
    it('generates descriptive names for extra colors based on OKLCH parameters', () => {
      expect(getOklchColorName({ l: 0.02, c: 0, h: null })).toBe('NEAR BLACK');
      expect(getOklchColorName({ l: 0.98, c: 0, h: null })).toBe('NEAR WHITE');
      expect(getOklchColorName({ l: 0.50, c: 0.01, h: 200 })).toBe('SOFT GRAY');
      expect(getOklchColorName({ l: 0.20, c: 0.15, h: 290 })).toBe('DEEP PURPLE');
      expect(getOklchColorName({ l: 0.75, c: 0.12, h: 150 })).toBe('LIGHT GREEN');
      expect(getOklchColorName({ l: 0.35, c: 0.18, h: 240 })).toBe('DARK BLUE');
    });

    it('preserves SHADOW, BASE, HIGHLIGHT, ACCENT for indices 0..3 in 4..9 color palettes', () => {
      const p4 = generatePalette('#5b21b6', 'splitComplementary', 0);
      const ext9 = extendPalette(p4, 9);
      expect(getPaletteColorLabel(ext9[0].role, 0, 9, ext9[0].oklch)).toBe('SHADOW');
      expect(getPaletteColorLabel(ext9[1].role, 1, 9, ext9[1].oklch)).toBe('BASE');
      expect(getPaletteColorLabel(ext9[2].role, 2, 9, ext9[2].oklch)).toBe('HIGHLIGHT');
      expect(getPaletteColorLabel(ext9[3].role, 3, 9, ext9[3].oklch)).toBe('ACCENT');
      // 5th color and beyond get human-readable OKLCH name
      const label5 = getPaletteColorLabel(ext9[4].role, 4, 9, ext9[4].oklch);
      expect(label5).toBeTruthy();
    });
  });
});

