import { describe, it, expect } from 'vitest';
import { generatePalette } from '../generator';
import {
  sanitizeFilename,
  generateGplString,
  generateJascPalString,
  generateHexListString,
  generateTxtString,
  generateJsonString,
  generateCssString,
} from '../exporters';

describe('Artist Palette Exporters Unit Tests', () => {
  const p2 = generatePalette('#5b21b6', 'splitComplementary', 0, 2);
  const p9 = generatePalette('#5b21b6', 'splitComplementary', 0, 9);

  describe('Sanitize Filename', () => {
    it('produces cross-platform safe filenames', () => {
      expect(sanitizeFilename('My Palette #1!')).toBe('my-palette-1');
      expect(sanitizeFilename('Палитра 9000!')).toBe('палитра-9000');
      expect(sanitizeFilename('', 'fallback')).toBe('fallback');
    });
  });

  describe('GIMP Palette (.gpl)', () => {
    it('generates valid GPL structure for 2 colors', () => {
      const gpl = generateGplString(p2);
      expect(gpl).toContain('GIMP Palette');
      expect(gpl).toContain('Name: OKLCH Palette (2 Colors)');
      expect(gpl).toContain('Columns: 2');

      const lines = gpl.trim().split('\n');
      expect(lines.length).toBe(6); // 4 header lines + 2 color lines
    });

    it('generates valid GPL structure for 9 colors without losing colors', () => {
      const gpl = generateGplString(p9, 'ru');
      expect(gpl).toContain('GIMP Palette');
      expect(gpl).toContain('Columns: 9');

      const lines = gpl.trim().split('\n');
      expect(lines.length).toBe(13); // 4 header lines + 9 color lines
    });
  });

  describe('JASC Palette (.pal)', () => {
    it('generates valid JASC-PAL header and exact color count N', () => {
      const pal2 = generateJascPalString(p2);
      const lines2 = pal2.trim().split('\n');
      expect(lines2[0]).toBe('JASC-PAL');
      expect(lines2[1]).toBe('0100');
      expect(lines2[2]).toBe('2');
      expect(lines2.length).toBe(5);

      const pal9 = generateJascPalString(p9);
      const lines9 = pal9.trim().split('\n');
      expect(lines9[2]).toBe('9');
      expect(lines9.length).toBe(12);
    });

    it('outputs valid RGB integers between 0 and 255', () => {
      const pal = generateJascPalString(p9);
      const colorLines = pal.trim().split('\n').slice(3);

      colorLines.forEach((line) => {
        const parts = line.split(' ').map(Number);
        expect(parts.length).toBe(3);
        parts.forEach((val) => {
          expect(val).toBeGreaterThanOrEqual(0);
          expect(val).toBeLessThanOrEqual(255);
          expect(Number.isInteger(val)).toBe(true);
        });
      });
    });
  });

  describe('HEX Code List (.hex)', () => {
    it('formats uppercase HEX strings one per line', () => {
      const hexList = generateHexListString(p9);
      const lines = hexList.trim().split('\n');
      expect(lines.length).toBe(9);

      lines.forEach((hex, idx) => {
        expect(hex).toMatch(/^#[0-9A-F]{6}$/);
        expect(hex).toBe(p9.colors[idx].hex.toUpperCase());
      });
    });
  });

  describe('Plain Text Breakdown (.txt)', () => {
    it('includes all colors and metrics in English and Russian', () => {
      const txtEn = generateTxtString(p9, 'en');
      expect(txtEn).toContain('OKLCH Pixel Palette Breakdown');
      expect(txtEn).toContain('Total Colors: 9');
      expect(txtEn).toContain('HEX:');
      expect(txtEn).toContain('OKLCH:');

      const txtRu = generateTxtString(p9, 'ru');
      expect(txtRu).toContain('Палитра OKLCH Pixel Palette');
      expect(txtRu).toContain('Количество цветов: 9');
    });
  });

  describe('Structured JSON (.json)', () => {
    it('parses valid JSON with numeric OKLCH metrics matching palette order', () => {
      const jsonStr = generateJsonString(p9);
      interface JsonExportColor {
        name: string;
        role: string;
        hex: string;
        oklch: { l: number; c: number; h: number | null };
      }
      interface JsonExportFormat {
        colorSpace: string;
        colors: JsonExportColor[];
      }

      const parsed = JSON.parse(jsonStr) as JsonExportFormat;

      expect(parsed.colorSpace).toBe('OKLCH');
      expect(parsed.colors.length).toBe(9);

      parsed.colors.forEach((col, idx) => {
        expect(col.hex).toBe(p9.colors[idx].hex.toUpperCase());
        expect(typeof col.oklch.l).toBe('number');
        expect(typeof col.oklch.c).toBe('number');
      });
    });
  });

  describe('CSS Custom Properties (.css)', () => {
    it('exports every color with an sRGB fallback and OKLCH override', () => {
      const css = generateCssString(p9);

      expect(css).toContain(':root {');
      expect(css).toContain('@supports (color: oklch(50% 0 0))');
      expect(css.match(/--palette-\d+-/g)).toHaveLength(18);
      expect(css).toContain(p9.colors[0].hex.toUpperCase());
      expect(css).toContain('oklch(');
    });
  });

  describe('Graceful Fallback for Invalid Palettes', () => {
    it('handles empty or malformed palette objects without throwing', () => {
      const invalid = {} as unknown as Parameters<typeof generateGplString>[0];
      expect(() => generateGplString(invalid)).not.toThrow();
      expect(() => generateJascPalString(invalid)).not.toThrow();
      expect(() => generateHexListString(invalid)).not.toThrow();
      expect(() => generateTxtString(invalid)).not.toThrow();
      expect(() => generateJsonString(invalid)).not.toThrow();
      expect(() => generateCssString(invalid)).not.toThrow();
    });
  });
});
