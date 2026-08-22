/**
 * AI End-to-End Integration Tests.
 * Tests:
 * 1. zimniy zvezdniy les -> 4 colors
 * 2. zimniy zvezdniy les -> 9 colors
 * 3. rzhaviy zavod na zakate -> 6 colors
 * 4. nezhnaya vesennyaya sakura -> 5 colors
 * 5. neon cyberpunk rain -> 9 colors
 * 6. Direct color word grounding: purple, fioletoviy, red, krasniy, green, zeleniy
 * 7. Semantic diversity & zero prompt collapse
 * 8. Gamut and validity of all generated colors
 */
import { describe, it, expect } from 'vitest';
import { inferPaletteIntent } from '../inference';
import { generatePalette } from '@/lib/color/generator';
import { extendPalette } from '@/lib/color/extendPalette';
import { isInSrgbGamut } from '@/lib/color/gamut';
import { hexToOklch } from '@/lib/color/conversions';

describe('AI Palette End-to-End Multilingual Integration', () => {
  it('зимний звездный лес -> 4 colors', async () => {
    const intent = await inferPaletteIntent('зимний звездный лес');
    expect(intent.baseHex).toMatch(/^#[0-9a-f]{6}$/i);
    expect(['splitComplementary', 'complementary', 'analogous']).toContain(intent.harmony);

    const palette = generatePalette(intent.baseHex, intent.harmony, intent.seed);
    const displayColors = extendPalette(palette, 4);

    expect(displayColors).toHaveLength(4);
    for (const col of displayColors) {
      expect(col.hex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(isInSrgbGamut(col.oklch, 1e-3)).toBe(true);
    }
  });

  it('зимний звездный лес -> 9 colors', async () => {
    const intent = await inferPaletteIntent('зимний звездный лес');
    const palette = generatePalette(intent.baseHex, intent.harmony, intent.seed);
    const displayColors = extendPalette(palette, 9);

    expect(displayColors).toHaveLength(9);
    for (const col of displayColors) {
      expect(col.hex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(isInSrgbGamut(col.oklch, 1e-3)).toBe(true);
    }
  });

  it('ржавый завод на закате -> 6 colors', async () => {
    const intent = await inferPaletteIntent('ржавый завод на закате');
    const palette = generatePalette(intent.baseHex, intent.harmony, intent.seed);
    const displayColors = extendPalette(palette, 6);

    expect(displayColors).toHaveLength(6);
    for (const col of displayColors) {
      expect(col.hex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(isInSrgbGamut(col.oklch, 5e-3)).toBe(true);
    }
  });

  it('нежная весенняя сакура -> 5 colors', async () => {
    const intent = await inferPaletteIntent('нежная весенняя сакура');
    const palette = generatePalette(intent.baseHex, intent.harmony, intent.seed);
    const displayColors = extendPalette(palette, 5);

    expect(displayColors).toHaveLength(5);
    for (const col of displayColors) {
      expect(col.hex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(isInSrgbGamut(col.oklch, 1e-3)).toBe(true);
    }
  });

  it('neon cyberpunk rain -> 9 colors', async () => {
    const intent = await inferPaletteIntent('neon cyberpunk rain');
    const palette = generatePalette(intent.baseHex, intent.harmony, intent.seed);
    const displayColors = extendPalette(palette, 9);

    expect(displayColors).toHaveLength(9);
    for (const col of displayColors) {
      expect(col.hex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(isInSrgbGamut(col.oklch, 1e-3)).toBe(true);
    }
  });

  it('accurately grounds direct color names in English and Russian', async () => {
    const purpleEn = await inferPaletteIntent('purple');
    const purpleRu = await inferPaletteIntent('фиолетовый');
    const violetEn = await inferPaletteIntent('violet');

    const oklchPurpleEn = hexToOklch(purpleEn.baseHex)!;
    const oklchPurpleRu = hexToOklch(purpleRu.baseHex)!;
    const oklchVioletEn = hexToOklch(violetEn.baseHex)!;

    // Assert purple/violet hue region (~280° - 325°)
    expect(oklchPurpleEn.h).toBeGreaterThanOrEqual(280);
    expect(oklchPurpleEn.h).toBeLessThanOrEqual(325);

    expect(oklchPurpleRu.h).toBeGreaterThanOrEqual(280);
    expect(oklchPurpleRu.h).toBeLessThanOrEqual(325);

    expect(oklchVioletEn.h).toBeGreaterThanOrEqual(280);
    expect(oklchVioletEn.h).toBeLessThanOrEqual(325);

    // Assert red / красный hue region (~15° - 45°)
    const redEn = await inferPaletteIntent('red');
    const redRu = await inferPaletteIntent('красный');
    const oklchRedEn = hexToOklch(redEn.baseHex)!;
    const oklchRedRu = hexToOklch(redRu.baseHex)!;
    expect(oklchRedEn.h).toBeGreaterThanOrEqual(15);
    expect(oklchRedEn.h).toBeLessThanOrEqual(45);
    expect(oklchRedRu.h).toBeGreaterThanOrEqual(15);
    expect(oklchRedRu.h).toBeLessThanOrEqual(45);

    // Assert green / зеленый hue region (~125° - 165°)
    const greenEn = await inferPaletteIntent('green');
    const greenRu = await inferPaletteIntent('зеленый');
    const oklchGreenEn = hexToOklch(greenEn.baseHex)!;
    const oklchGreenRu = hexToOklch(greenRu.baseHex)!;
    expect(oklchGreenEn.h).toBeGreaterThanOrEqual(125);
    expect(oklchGreenEn.h).toBeLessThanOrEqual(165);
    expect(oklchGreenRu.h).toBeGreaterThanOrEqual(125);
    expect(oklchGreenRu.h).toBeLessThanOrEqual(165);
  });

  it('different semantic prompts do not collapse to identical intents', async () => {
    const p1 = await inferPaletteIntent('зимний звездный лес');
    const p2 = await inferPaletteIntent('ржавый завод на закате');
    const p3 = await inferPaletteIntent('neon cyberpunk rain');

    expect(p1.baseHex).not.toBe(p2.baseHex);
    expect(p2.baseHex).not.toBe(p3.baseHex);
    expect(p1.seed).not.toBe(p2.seed);
    expect(p2.seed).not.toBe(p3.seed);
  });
});
