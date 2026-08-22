import { describe, it, expect } from 'vitest';
import { comparePalettes } from '../paletteCompare';

describe('paletteCompare', () => {
  it('computes comparison metrics between two palettes', () => {
    const palA = '#172033 #20283A #5F718A #C084FC #F43F5E';
    const palB = '#0d1f0a #1a3d14 #3a7a30 #7cc46c #c8f0a4';

    const result = comparePalettes(palA, palB);
    expect(result.paletteA.uniqueColors).toBe(5);
    expect(result.paletteB.uniqueColors).toBe(5);
    expect(result.paletteA.lightnessRange).toBeGreaterThan(0);
    expect(result.paletteB.lightnessRange).toBeGreaterThan(0);
    expect(result.avgNearestDE).toBeGreaterThan(0);
  });
});
