import { afterEach, describe, expect, it } from 'vitest';
import { extendPalette } from '@/lib/color/extendPalette';
import { generatePalette } from '@/lib/color/generator';
import {
  generateAiPalette,
  setTestDecoderLoader,
  setTestEncoderLoader,
} from '../inference';

describe('deterministic OKLCH core isolation', () => {
  afterEach(() => {
    setTestEncoderLoader(null);
    setTestDecoderLoader(null);
  });

  it('works with AI disabled and is stable for every count', () => {
    const base = generatePalette('#3B82F6', 'splitComplementary', 42);
    for (let count = 2; count <= 9; count++) {
      const first = extendPalette(base, count);
      const second = extendPalette(generatePalette('#3B82F6', 'splitComplementary', 42), count);
      expect(first).toEqual(second);
      expect(first).toHaveLength(count);
    }
  });

  it('is unchanged after a neural runtime failure', async () => {
    const before = extendPalette(generatePalette('#A855F7', 'analogous', 137), 7);
    setTestEncoderLoader(async () => { throw new Error('AI disabled'); });
    setTestDecoderLoader(async () => { throw new Error('decoder disabled'); });
    await expect(generateAiPalette({ prompt: 'rain', count: 5, seed: 42 }))
      .rejects.toThrow('AI disabled');
    const after = extendPalette(generatePalette('#A855F7', 'analogous', 137), 7);
    expect(after).toEqual(before);
  });
});
