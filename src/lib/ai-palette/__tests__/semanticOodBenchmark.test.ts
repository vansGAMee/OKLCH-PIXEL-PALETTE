/**
 * semanticOodBenchmark.test.ts
 * Rigorous semantic validation across 80+ out-of-distribution Russian & English prompts.
 */
import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { inferPaletteIntent } from '../inference';
import { generatePalette } from '@/lib/color/generator';
import { extendPalette } from '@/lib/color/extendPalette';
import { isInSrgbGamut } from '@/lib/color/gamut';
import { hexToOklch } from '@/lib/color/conversions';

describe('80+ Semantic OOD Benchmark Suite', () => {
  const rootDir = process.cwd();
  const promptsPath = path.join(rootDir, 'ml/semantic_ood_prompts.json');
  const prompts: string[] = JSON.parse(fs.readFileSync(promptsPath, 'utf8'));

  it('contains at least 80 diverse benchmark prompts', () => {
    expect(prompts.length).toBeGreaterThanOrEqual(80);
  });

  it('generates valid, gamut-safe 4-9 color palettes for all 80+ prompts', async () => {
    const uniqueBaseHexes = new Set<string>();
    const hues: number[] = [];

    for (const prompt of prompts) {
      const intent = await inferPaletteIntent(prompt);

      // 1. Valid hex and harmony
      expect(intent.baseHex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(['splitComplementary', 'complementary', 'analogous']).toContain(intent.harmony);
      expect(typeof intent.seed).toBe('number');

      uniqueBaseHexes.add(intent.baseHex.toLowerCase());

      const oklch = hexToOklch(intent.baseHex);
      expect(oklch).toBeDefined();
      if (oklch && oklch.h !== null) {
        hues.push(oklch.h);
      }

      // 2. Generate 4 core colors and extend to 7 colors
      const palette = generatePalette(intent.baseHex, intent.harmony, intent.seed);
      const displayColors = extendPalette(palette, 7);
      expect(displayColors).toHaveLength(7);

      for (const col of displayColors) {
        expect(col.hex).toMatch(/^#[0-9a-f]{6}$/i);
        expect(isInSrgbGamut(col.oklch, 5e-3)).toBe(true);
      }
    }

    // 3. Assert high diversity (no collapse across 80+ prompts)
    expect(uniqueBaseHexes.size).toBeGreaterThanOrEqual(40);

    // 4. Assert hue coverage across entire 360 degree circle
    const minHue = Math.min(...hues);
    const maxHue = Math.max(...hues);
    expect(minHue).toBeLessThan(60);
    expect(maxHue).toBeGreaterThan(270);
  }, 60000);
});
