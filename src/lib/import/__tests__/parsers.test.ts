/**
 * src/lib/import/__tests__/parsers.test.ts
 * Tests for all 5 palette parsers.
 */
import { describe, test, expect } from 'vitest';
import { parseGpl } from '../parsers/parseGpl';
import { parsePal } from '../parsers/parsePal';
import { parseHex } from '../parsers/parseHex';
import { parseJson } from '../parsers/parseJson';

// ---------- GPL Parser Tests ----------
describe('parseGpl', () => {
  test('parses valid GPL file', () => {
    const content = `GIMP Palette
Name: Test
Columns: 4
# comment
155  89 182 purple
  52 152 219 blue
231  76  60 red
`;
    const result = parseGpl(content);
    expect(result.error).toBeUndefined();
    expect(result.colors).toHaveLength(3);
    expect(result.colors[0].hex).toBe('#9b59b6');
    expect(result.colors[0].role).toBe('purple');
    expect(result.name).toBe('Test');
  });

  test('returns error for missing header', () => {
    const result = parseGpl('Not a GIMP Palette\n255 0 0 red\n');
    expect(result.error).toMatch(/GIMP Palette/);
    expect(result.colors).toHaveLength(0);
  });

  test('ignores comment lines', () => {
    const content = `GIMP Palette\nName: X\n# this is a comment\n100 100 100 gray\n`;
    const result = parseGpl(content);
    expect(result.colors).toHaveLength(1);
  });

  test('truncates to max 9 colors', () => {
    const lines = ['GIMP Palette'];
    for (let i = 0; i < 12; i++) lines.push(`${i * 20} 0 0 color${i}`);
    const result = parseGpl(lines.join('\n'));
    expect(result.colors).toHaveLength(9);
  });

  test('parses hex values correctly', () => {
    const content = `GIMP Palette\n255 255 255 white\n0 0 0 black\n`;
    const result = parseGpl(content);
    expect(result.colors[0].hex).toBe('#ffffff');
    expect(result.colors[1].hex).toBe('#000000');
  });
});

// ---------- PAL Parser Tests ----------
describe('parsePal', () => {
  test('parses valid JASC PAL file', () => {
    const content = `JASC-PAL\n0100\n3\n255 0 0\n0 255 0\n0 0 255\n`;
    const result = parsePal(content);
    expect(result.error).toBeUndefined();
    expect(result.colors).toHaveLength(3);
    expect(result.colors[0].hex).toBe('#ff0000');
  });

  test('returns error for invalid header', () => {
    const result = parsePal('NOT-A-PAL\n0100\n1\n255 0 0\n');
    expect(result.error).toBeTruthy();
    expect(result.colors).toHaveLength(0);
  });

  test('returns error for wrong version', () => {
    const result = parsePal('JASC-PAL\n0200\n1\n255 0 0\n');
    expect(result.error).toMatch(/0100/);
  });

  test('truncates to max 9 colors', () => {
    const lines = ['JASC-PAL', '0100', '15'];
    for (let i = 0; i < 15; i++) lines.push(`${i * 15} 0 0`);
    const result = parsePal(lines.join('\n'));
    expect(result.colors).toHaveLength(9);
  });
});

// ---------- HEX Parser Tests ----------
describe('parseHex', () => {
  test('parses hex colors with # prefix', () => {
    const content = `#ff0000\n#00ff00\n#0000ff\n`;
    const result = parseHex(content);
    expect(result.error).toBeUndefined();
    expect(result.colors).toHaveLength(3);
    expect(result.colors[0].hex).toBe('#ff0000');
  });

  test('parses hex colors without # prefix', () => {
    const content = `ff0000\n00ff00\n`;
    const result = parseHex(content);
    expect(result.colors).toHaveLength(2);
    expect(result.colors[0].hex).toBe('#ff0000');
  });

  test('skips invalid lines', () => {
    const content = `#ff0000\nnot-a-color\n#00ff00\n`;
    const result = parseHex(content);
    expect(result.colors).toHaveLength(2);
  });

  test('returns error when no valid colors', () => {
    const result = parseHex('not a color\nstill not\n');
    expect(result.error).toBeTruthy();
    expect(result.colors).toHaveLength(0);
  });

  test('truncates to 9 colors', () => {
    const lines = Array.from({ length: 15 }, (_, i) => `#${i.toString(16).padStart(2, '0')}0000`);
    const result = parseHex(lines.join('\n'));
    expect(result.colors).toHaveLength(9);
  });
});

// ---------- JSON Parser Tests ----------
describe('parseJson', () => {
  test('parses valid palette JSON', () => {
    const data = {
      name: 'My Palette',
      harmony: 'analogous',
      seed: 42,
      colors: [
        { role: 'shadow', hex: '#1e1b4b', oklch: { l: 0.18, c: 0.12, h: 280 } },
        { role: 'base', hex: '#7c3aed', oklch: { l: 0.45, c: 0.22, h: 290 } },
        { role: 'highlight', hex: '#c084fc', oklch: { l: 0.70, c: 0.18, h: 295 } },
      ],
    };
    const result = parseJson(JSON.stringify(data));
    expect(result.error).toBeUndefined();
    expect(result.colors).toHaveLength(3);
    expect(result.name).toBe('My Palette');
    expect(result.harmony).toBe('analogous');
    expect(result.seed).toBe(42);
  });

  test('returns error for invalid JSON', () => {
    const result = parseJson('{ not valid json }');
    expect(result.error).toBe('Invalid JSON');
  });

  test('returns error when colors array is missing', () => {
    const result = parseJson(JSON.stringify({ name: 'test' }));
    expect(result.error).toBeTruthy();
  });

  test('returns error when fewer than 2 valid colors', () => {
    const data = { colors: [{ hex: '#ff0000', role: 'base', oklch: { l: 0.5, c: 0.2, h: 30 } }] };
    const result = parseJson(JSON.stringify(data));
    expect(result.error).toBeTruthy();
  });

  test('skips items with invalid hex', () => {
    const data = {
      colors: [
        { role: 'a', hex: '#ff0000', oklch: { l: 0.5, c: 0.2, h: 30 } },
        { role: 'b', hex: 'not-hex', oklch: { l: 0.5, c: 0.2, h: 30 } },
        { role: 'c', hex: '#00ff00', oklch: { l: 0.7, c: 0.1, h: 120 } },
      ],
    };
    const result = parseJson(JSON.stringify(data));
    expect(result.colors).toHaveLength(2);
  });
});
