import { describe, it, expect } from 'vitest';
import { generatePalette } from '../generator';
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

  describe('Flexible Palette Sizes (2 to 9 Colors)', () => {
    it('generates exact number of colors for 2, 4, and 9 colors', () => {
      const p2 = generatePalette('#5b21b6', 'splitComplementary', 0, 2);
      expect(p2.count).toBe(2);
      expect(p2.colors.length).toBe(2);
      expect(p2.shadow).toBe(p2.colors[0]);
      expect(p2.base).toBe(p2.colors[1]);

      const p4 = generatePalette('#5b21b6', 'splitComplementary', 0, 4);
      expect(p4.count).toBe(4);
      expect(p4.colors.length).toBe(4);
      expect(p4.shadow).toBe(p4.colors[0]);
      expect(p4.base).toBe(p4.colors[1]);
      expect(p4.highlight).toBe(p4.colors[2]);
      expect(p4.accent).toBe(p4.colors[3]);

      const p9 = generatePalette('#5b21b6', 'splitComplementary', 0, 9);
      expect(p9.count).toBe(9);
      expect(p9.colors.length).toBe(9);
      expect(p9.colors[4].role).toBe('color5');
      expect(p9.colors[8].role).toBe('color9');
    });

    it('clamps color count strictly below 2 to 2 and above 9 to 9', () => {
      const pMin = generatePalette('#5b21b6', 'splitComplementary', 0, 1);
      expect(pMin.count).toBe(2);
      expect(pMin.colors.length).toBe(2);

      const pMax = generatePalette('#5b21b6', 'splitComplementary', 0, 15);
      expect(pMax.count).toBe(9);
      expect(pMax.colors.length).toBe(9);
    });

    it('uses 4 colors by default when colorCount is omitted', () => {
      const pDefault = generatePalette('#5b21b6');
      expect(pDefault.count).toBe(4);
      expect(pDefault.colors.length).toBe(4);
    });

    it('guarantees unique React keys for palette grid cards across all sizes', () => {
      for (let size = 2; size <= 9; size++) {
        const palette = generatePalette('#5b21b6', 'splitComplementary', 0, size);
        const keys = palette.colors.map((c, idx) => `${c.role}-${idx}`);
        const uniqueKeys = new Set(keys);
        expect(uniqueKeys.size).toBe(palette.colors.length);
      }
    });

    it('runs exportPalettePng for 2, 4, 6, and 9 colors without error in node environment', () => {
      for (const count of [2, 4, 6, 9]) {
        const palette = generatePalette('#5b21b6', 'splitComplementary', 0, count);
        expect(() => exportPalettePng(palette)).not.toThrow();
      }
    });
  });

  describe('Deduplication & Minimum Distance (100+ 9-Color Palettes)', () => {
    it('guarantees no duplicate HEX codes and Delta E >= 0.025 across 100+ 9-color palettes', () => {
      const testHexes = ['#5b21b6', '#ff0000', '#00ff00', '#0000ff', '#f2c94c', '#808080', '#121212', '#f7f7f7'];
      const harmonies: HarmonyMode[] = ['splitComplementary', 'complementary', 'analogous'];
      const seeds = [0, 1, 2, 3, 4, 5];

      let totalPalettes = 0;
      let globalMinDeltaE = 999;

      for (const hex of testHexes) {
        for (const harmony of harmonies) {
          for (const seed of seeds) {
            const palette = generatePalette(hex, harmony, seed, 9);
            totalPalettes++;

            // 1. Assert exact count
            expect(palette.colors.length).toBe(9);

            // 2. Assert no duplicate HEX strings
            const hexes = palette.colors.map((c) => c.hex.toLowerCase());
            const uniqueHexes = new Set(hexes);
            expect(uniqueHexes.size).toBe(9);

            // 3. Assert pairwise Delta E >= MIN_PALETTE_DELTA_E (0.025)
            for (let i = 0; i < 9; i++) {
              for (let j = i + 1; j < 9; j++) {
                const delta = calculateDeltaE(palette.colors[i].oklch, palette.colors[j].oklch);
                if (delta < globalMinDeltaE) {
                  globalMinDeltaE = delta;
                }
                expect(delta).toBeGreaterThanOrEqual(0.025);
              }
            }
          }
        }
      }

      expect(totalPalettes).toBeGreaterThanOrEqual(100);
      expect(globalMinDeltaE).toBeGreaterThanOrEqual(0.025);
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
      const p9 = generatePalette('#5b21b6', 'splitComplementary', 0, 9);
      expect(getPaletteColorLabel(p9.colors[0].role, 0, 9, p9.colors[0].oklch)).toBe('SHADOW');
      expect(getPaletteColorLabel(p9.colors[1].role, 1, 9, p9.colors[1].oklch)).toBe('BASE');
      expect(getPaletteColorLabel(p9.colors[2].role, 2, 9, p9.colors[2].oklch)).toBe('HIGHLIGHT');
      expect(getPaletteColorLabel(p9.colors[3].role, 3, 9, p9.colors[3].oklch)).toBe('ACCENT');
      // 5th color and beyond get human-readable OKLCH name
      const label5 = getPaletteColorLabel(p9.colors[4].role, 4, 9, p9.colors[4].oklch);
      expect(label5).not.toContain('COLOR 5');
    });
  });
});

