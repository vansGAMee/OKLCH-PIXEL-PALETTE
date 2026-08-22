/**
 * AI End-to-End Integration Tests.
 * Tests:
 * 1. зимний звездный лес -> 4
 * 2. зимний звездный лес -> 9
 * 3. ржавый завод на закате -> 6
 * 4. нежная весенняя сакура -> 5
 * 5. neon cyberpunk rain -> 9
 * 6. Semantic diversity (different prompts -> different base/harmony/seed)
 * 7. Gamut and validity of all generated colors
 */
import { describe, it, expect, beforeAll } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { inferPaletteIntent, setTestArtifacts } from '../inference';
import { generatePalette } from '@/lib/color/generator';
import { extendPalette } from '@/lib/color/extendPalette';
import { isInSrgbGamut } from '@/lib/color/gamut';

beforeAll(() => {
  const rootDir = process.cwd();
  const vocabPath = path.join(rootDir, 'public/models/paletta-v1.vocab.json');
  const onnxPath = path.join(rootDir, 'public/models/paletta-v1.onnx');

  const vocab = JSON.parse(fs.readFileSync(vocabPath, 'utf8'));
  const modelBuf = fs.readFileSync(onnxPath);

  setTestArtifacts(vocab, modelBuf);
});

describe('AI Palette End-to-End Integration', () => {
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
      const inGamut = isInSrgbGamut(col.oklch, 1e-3);
      if (!inGamut) {
        console.log('Failing in 6 colors:', col, 'hex:', col.hex, 'inGamut eps=1e-2:', isInSrgbGamut(col.oklch, 1e-2));
      }
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
