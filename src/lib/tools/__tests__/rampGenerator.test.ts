import { describe, it, expect } from 'vitest';
import { generateRamp, applyPreset, generateDefaultConfig } from '../rampGenerator';

describe('rampGenerator', () => {
  it('generates exact requested color count', () => {
    for (const count of [3, 5, 7, 9]) {
      const config = { ...generateDefaultConfig('#5b21b6'), count };
      const ramp = generateRamp(config);
      expect(ramp).not.toBeNull();
      expect(ramp!.colors).toHaveLength(count);
    }
  });

  it('produces monotonically increasing lightness progression', () => {
    const config = generateDefaultConfig('#047857');
    const ramp = generateRamp(config)!;
    for (let i = 1; i < ramp.colors.length; i++) {
      expect(ramp.colors[i].oklch.l).toBeGreaterThan(ramp.colors[i - 1].oklch.l);
    }
  });

  it('applies presets correctly', () => {
    const base = generateDefaultConfig('#b45309');
    const warm = applyPreset(base, 'warm');
    const cool = applyPreset(base, 'cool');
    expect(warm.hueShiftDeg).toBeGreaterThan(0);
    expect(cool.hueShiftDeg).toBeLessThan(0);
  });
});
