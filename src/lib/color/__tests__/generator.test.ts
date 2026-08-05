import { describe, it, expect } from 'vitest';
import { generatePalette } from '../generator';
import { validatePalette } from '../validation';
import { hexToOklch, oklchToHex, normalizeHex } from '../conversions';
import { fitToSrgb } from '../gamut';
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
});
