import { describe, it, expect } from 'vitest';
import { parseHexInput, analyzePalette, fixPalette } from '../paletteDoctor';

describe('paletteDoctor', () => {
  it('parses diverse hex input formats correctly', () => {
    const raw = '#172033, 20283A\n#5F718A; C084FC';
    const { colors, errors } = parseHexInput(raw);
    expect(errors).toHaveLength(0);
    expect(colors).toHaveLength(4);
    expect(colors[0].hex).toBe('#172033');
    expect(colors[1].hex).toBe('#20283a');
    expect(colors[2].hex).toBe('#5f718a');
    expect(colors[3].hex).toBe('#c084fc');
  });

  it('detects duplicate and near-duplicate colors', () => {
    const input = parseHexInput('#5b21b6 #5b21b6 #5c22b7 #ffffff');
    const report = analyzePalette(input.colors);
    expect(report.healthScore).toBeLessThan(100);
    expect(report.issues.some(i => i.id.includes('dup') || i.id.includes('near_dup'))).toBe(true);
  });

  it('evaluates healthy palette with high score', () => {
    const input = parseHexInput('#0d1f0a #1a3d14 #3a7a30 #7cc46c #c8f0a4');
    const report = analyzePalette(input.colors);
    expect(report.healthScore).toBeGreaterThanOrEqual(80);
    expect(report.lightnessRange).toBeGreaterThan(0.3);
  });

  it('generates valid and improved fixed palette', () => {
    const input = parseHexInput('#4a4a4a #4b4b4b #4c4c4c #4d4d4d');
    const report = analyzePalette(input.colors);
    const fixed = fixPalette(report);
    expect(fixed).toHaveLength(4);
    const reReport = analyzePalette(fixed);
    expect(reReport.lightnessRange).toBeGreaterThan(report.lightnessRange);
  });
});
