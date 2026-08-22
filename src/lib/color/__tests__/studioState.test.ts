/**
 * src/lib/color/__tests__/studioState.test.ts
 * Regression tests for studio state updates, palette generation bounds, and performance.
 */
import { describe, test, expect } from 'vitest';
import { generatePalette } from '../generator';
import { extendPalette } from '../extendPalette';
import { inspectPalette } from '../qualityInspector';
import { parseGpl } from '../../import/parsers/parseGpl';
import { parseJson } from '../../import/parsers/parseJson';

describe('Studio State & Performance Integration', () => {
  test('generatePalette executes under 2ms for fast dragging', () => {
    const start = performance.now();
    for (let i = 0; i < 50; i++) {
      const hueHex = `#${((i * 5) % 255).toString(16).padStart(2, '0')}21b6`;
      generatePalette(hueHex, 'splitComplementary', 0);
    }
    const elapsed = performance.now() - start;
    const avgPerCall = elapsed / 50;
    expect(avgPerCall).toBeLessThan(2); // Avg call must be < 2ms for 60fps interaction
  });

  test('qualityInspector inspects generated palette under 1ms', () => {
    const palette = generatePalette('#5b21b6', 'splitComplementary', 0);
    const start = performance.now();
    for (let i = 0; i < 50; i++) {
      inspectPalette(palette);
    }
    const elapsed = performance.now() - start;
    expect(elapsed / 50).toBeLessThan(1);
  });

  test('importing exported GPL format roundtrips cleanly', () => {
    const gplText = `GIMP Palette
Name: Studio Export
Columns: 4
#
 91  33 182 base
 30  27  75 shadow
216 180 254 highlight
244  63  94 accent
`;
    const parsed = parseGpl(gplText);
    expect(parsed.error).toBeUndefined();
    expect(parsed.colors).toHaveLength(4);
    expect(parsed.colors[0].hex).toBe('#5b21b6');
  });

  test('importing exported JSON format roundtrips cleanly', () => {
    const palette = generatePalette('#7c3aed', 'analogous', 2);
    const displayColors = extendPalette(palette, 5);
    const jsonStr = JSON.stringify({
      name: 'Import Test',
      colors: displayColors,
    });
    const parsed = parseJson(jsonStr);
    expect(parsed.error).toBeUndefined();
    expect(parsed.colors).toHaveLength(5);
  });
});
