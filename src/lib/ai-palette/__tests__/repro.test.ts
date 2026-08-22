import { describe, it, expect } from 'vitest';
import { inferPaletteIntent } from '../inference';
import { hexToOklch } from '@/lib/color/conversions';

describe('Critical Semantic Quality & Regression Suite', () => {
  const criticalPrompts = [
    'black',
    'white',
    'purple',
    'фиолетовый',
    'winter',
    'зима',
    'amethyst',
    'obsidian cave',
    'snowy forest under stars',
    'rusty factory at sunset',
    'toxic green swamp',
    'abandoned hospital at night',
    'cozy autumn cafe',
    'deep sea horror',
    'neon cyberpunk rain',
    'loneliness',
    'хуй',
  ];

  it('evaluates critical semantic prompts with valid OKLCH output', async () => {
    for (const p of criticalPrompts) {
      const intent = await inferPaletteIntent(p);
      expect(intent.baseHex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(['splitComplementary', 'complementary', 'analogous']).toContain(intent.harmony);

      const ok = hexToOklch(intent.baseHex)!;
      expect(ok).toBeDefined();
      const hueStr = ok.h !== null ? ok.h.toFixed(0) + '°' : 'neutral';
      console.log(
        p.padEnd(30),
        intent.baseHex,
        'L=' + ok.l.toFixed(2),
        'C=' + ok.c.toFixed(3),
        'H=' + hueStr.padEnd(8),
        intent.harmony
      );
    }
  }, 300000);

  it('enforces literal color release gates (black is never brown, white is high lightness)', async () => {
    // 1. Black must be near-black / low-chroma (never brown)
    const blackEn = await inferPaletteIntent('black');
    const blackRu = await inferPaletteIntent('черный');
    const okBlackEn = hexToOklch(blackEn.baseHex)!;
    const okBlackRu = hexToOklch(blackRu.baseHex)!;

    expect(okBlackEn.l).toBeLessThanOrEqual(0.25);
    expect(okBlackEn.c).toBeLessThanOrEqual(0.05);

    expect(okBlackRu.l).toBeLessThanOrEqual(0.25);
    expect(okBlackRu.c).toBeLessThanOrEqual(0.05);

    // 2. White must be high lightness, neutral
    const whiteEn = await inferPaletteIntent('white');
    const whiteRu = await inferPaletteIntent('белый');
    const okWhiteEn = hexToOklch(whiteEn.baseHex)!;
    const okWhiteRu = hexToOklch(whiteRu.baseHex)!;

    expect(okWhiteEn.l).toBeGreaterThanOrEqual(0.85);
    expect(okWhiteEn.c).toBeLessThanOrEqual(0.05);
    expect(okWhiteRu.l).toBeGreaterThanOrEqual(0.85);
    expect(okWhiteRu.c).toBeLessThanOrEqual(0.05);

    // 3. Purple & фиолетовый must ground in purple/violet hue range (280°-325°)
    const purpleEn = await inferPaletteIntent('purple');
    const purpleRu = await inferPaletteIntent('фиолетовый');
    const okPurpleEn = hexToOklch(purpleEn.baseHex)!;
    const okPurpleRu = hexToOklch(purpleRu.baseHex)!;

    expect(okPurpleEn.h).toBeGreaterThanOrEqual(280);
    expect(okPurpleEn.h).toBeLessThanOrEqual(325);
    expect(okPurpleRu.h).toBeGreaterThanOrEqual(280);
    expect(okPurpleRu.h).toBeLessThanOrEqual(325);
  });

  it('preserves semantic context in longer phrases with color words', async () => {
    const castle = await inferPaletteIntent('purple castle at night');
    const forest = await inferPaletteIntent('black winter forest');
    const alley = await inferPaletteIntent('red neon alley');

    expect(castle.baseHex).toMatch(/^#[0-9a-f]{6}$/i);
    expect(forest.baseHex).toMatch(/^#[0-9a-f]{6}$/i);
    expect(alley.baseHex).toMatch(/^#[0-9a-f]{6}$/i);

    // They must not all collapse to bare static color targets
    const okForest = hexToOklch(forest.baseHex)!;
    expect(okForest.l).toBeLessThan(0.6);
  });
});
