import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearPromptEmbeddingCache,
  generateAiPalette,
  resetDecoderSession,
  resetEncoderSession,
  setTestDecoderLoader,
  setTestEncoderLoader,
  type PaletteDecoderFeeds,
} from '../inference';

function makePaletteOutput() {
  const data = new Float32Array(9 * 5);
  for (let slot = 0; slot < 9; slot++) {
    const offset = slot * 5;
    const hue = slot * 37 * Math.PI / 180;
    data[offset] = (slot - 4) / 3;
    data[offset + 1] = -0.5;
    data[offset + 2] = Math.sin(hue);
    data[offset + 3] = Math.cos(hue);
    data[offset + 4] = 1 - slot / 10;
  }
  return { data, dims: [1, 9, 5] as const };
}

function installEncoder() {
  const tokenizer = vi.fn().mockResolvedValue({
    attention_mask: { data: new Int32Array([1, 1, 1]) },
  });
  const model = vi.fn().mockResolvedValue({
    last_hidden_state: {
      data: new Float32Array(3 * 384).fill(0.25),
      dims: [1, 3, 384],
    },
  });
  const loader = vi.fn().mockResolvedValue({ tokenizer, model });
  setTestEncoderLoader(loader);
  return { loader, tokenizer, model };
}

function installDecoder(run = vi.fn().mockResolvedValue(makePaletteOutput())) {
  const loader = vi.fn().mockResolvedValue({
    modelVersion: 'palettebrain-v2-test',
    run,
  });
  setTestDecoderLoader(loader);
  return { loader, run };
}

describe('PaletteBrain v2 browser runtime', () => {
  beforeEach(() => {
    setTestEncoderLoader(null);
    setTestDecoderLoader(null);
    resetEncoderSession();
    resetDecoderSession();
    clearPromptEmbeddingCache();
  });

  it.each([2, 3, 4, 9])('returns exactly %i native decoder colors', async (count) => {
    const encoder = installEncoder();
    const decoder = installDecoder();

    const result = await generateAiPalette({
      prompt: 'ночная больница во время грозы',
      count,
      seed: 42,
    });

    expect(result.colors).toHaveLength(count);
    expect(result.seed).toBe(42);
    expect(result.modelVersion).toBe('palettebrain-v2-test');
    expect(result.fallback).toBe(false);
    expect(result.inference?.encoderMs).toBeGreaterThanOrEqual(0);
    expect(result.inference?.decoderMs).toBeGreaterThanOrEqual(0);
    expect(result.inference?.totalMs).toBeGreaterThanOrEqual(0);
    expect(encoder.loader).toHaveBeenCalledOnce();
    expect(decoder.loader).toHaveBeenCalledOnce();

    const feeds = decoder.run.mock.calls[0][0] as PaletteDecoderFeeds;
    expect(feeds.text_embedding.dims).toEqual([1, 384]);
    expect(feeds.count_mask.dims).toEqual([1, 9]);
    expect(Array.from(feeds.count_mask.data)).toEqual([
      ...new Array(count).fill(1),
      ...new Array(9 - count).fill(0),
    ]);
  });

  it('reuses one normalized prompt embedding across count, seed, and lock changes', async () => {
    const encoder = installEncoder();
    const decoder = installDecoder();

    await generateAiPalette({ prompt: '  Hospital AT night  ', count: 4, seed: 1 });
    await generateAiPalette({
      prompt: 'hospital at night',
      count: 7,
      seed: 2,
      lockedColors: [{ index: 0, oklch: { l: 0.5, c: 0, h: null } }],
    });

    expect(encoder.tokenizer).toHaveBeenCalledOnce();
    expect(encoder.model).toHaveBeenCalledOnce();
    expect(decoder.run).toHaveBeenCalledTimes(2);
  });

  it('evicts a failed embedding promise so the same prompt can retry', async () => {
    const tokenizer = vi.fn().mockResolvedValue({
      attention_mask: { data: new Int32Array([1]) },
    });
    const model = vi.fn()
      .mockRejectedValueOnce(new Error('transient encoder failure'))
      .mockResolvedValue({
        last_hidden_state: {
          data: new Float32Array(384).fill(0.25),
          dims: [1, 1, 384],
        },
      });
    setTestEncoderLoader(async () => ({ tokenizer, model }));
    installDecoder();

    const request = { prompt: 'rainy laundromat', count: 3, seed: 9 };
    await expect(generateAiPalette(request)).rejects.toThrow('AI model inference failed');
    await expect(generateAiPalette(request)).resolves.toMatchObject({
      seed: 9,
      modelVersion: 'palettebrain-v2-test',
      fallback: false,
    });
    expect(model).toHaveBeenCalledTimes(2);
  });

  it('uses deterministic seed noise for the same seed', async () => {
    installEncoder();
    const seenNoise: Float32Array[] = [];
    installDecoder(vi.fn(async (feeds: PaletteDecoderFeeds) => {
      seenNoise.push(feeds.seed_noise.data.slice());
      return makePaletteOutput();
    }));

    await generateAiPalette({ prompt: 'melancholic anime sunset', count: 5, seed: 1234 });
    await generateAiPalette({ prompt: 'melancholic anime sunset', count: 5, seed: 1234 });
    await generateAiPalette({ prompt: 'melancholic anime sunset', count: 5, seed: 1235 });

    expect(Array.from(seenNoise[0])).toEqual(Array.from(seenNoise[1]));
    expect(Array.from(seenNoise[0])).not.toEqual(Array.from(seenNoise[2]));
    expect(Array.from(seenNoise[0].slice(0, 8))).toEqual([
      -0.6596911549568176,
      -2.1889116764068604,
      0.44437092542648315,
      -0.08317964524030685,
      1.8668758869171143,
      1.7043763399124146,
      0.6211627721786499,
      -1.8047523498535156,
    ]);
  });

  it('passes lock tensors to the decoder and preserves locked colors exactly', async () => {
    installEncoder();
    const decoder = installDecoder();
    const firstLock = { l: 0.52, c: 0.08, h: 120 };
    const secondLock = { l: 0.2, c: 0, h: null };

    const result = await generateAiPalette({
      prompt: 'abandoned greenhouse in space',
      count: 5,
      seed: 77,
      lockedColors: [
        { index: 1, oklch: firstLock },
        { index: 4, oklch: secondLock },
      ],
    });

    expect(result.colors[1]).toEqual(firstLock);
    expect(result.colors[4]).toEqual(secondLock);

    const feeds = decoder.run.mock.calls[0][0] as PaletteDecoderFeeds;
    expect(Array.from(feeds.locked_mask.data)).toEqual([0, 1, 0, 0, 1, 0, 0, 0, 0]);
    expect(feeds.locked_colors.data[4]).toBeCloseTo(firstLock.l);
    expect(feeds.locked_colors.data[5]).toBeCloseTo(firstLock.c);
    expect(feeds.locked_colors.data[6]).toBeCloseTo(Math.sin(120 * Math.PI / 180));
    expect(feeds.locked_colors.data[7]).toBeCloseTo(Math.cos(120 * Math.PI / 180));
    expect(feeds.locked_colors.data[16]).toBeCloseTo(secondLock.l);
    expect(Array.from(feeds.locked_colors.data.slice(17, 20))).toEqual([0, 0, 0]);
  });

  it('serializes overlapping decoder runs instead of rejecting them', async () => {
    const encoder = installEncoder();
    let activeRuns = 0;
    let maxActiveRuns = 0;
    installDecoder(vi.fn(async () => {
      activeRuns++;
      maxActiveRuns = Math.max(maxActiveRuns, activeRuns);
      await new Promise((resolve) => setTimeout(resolve, 10));
      activeRuns--;
      return makePaletteOutput();
    }));

    const [first, second] = await Promise.all([
      generateAiPalette({ prompt: 'airport loneliness', count: 4, seed: 1 }),
      generateAiPalette({ prompt: 'airport loneliness', count: 4, seed: 2 }),
    ]);

    expect(first.colors).toHaveLength(4);
    expect(second.colors).toHaveLength(4);
    expect(maxActiveRuns).toBe(1);
    expect(encoder.model).toHaveBeenCalledOnce();
  });

  it('throws concise validation errors before loading either model', async () => {
    const encoderLoader = vi.fn();
    const decoderLoader = vi.fn();
    setTestEncoderLoader(encoderLoader);
    setTestDecoderLoader(decoderLoader);

    await expect(generateAiPalette({ prompt: '   ', count: 4, seed: 1 }))
      .rejects.toThrow('AI prompt must not be empty');
    await expect(generateAiPalette({ prompt: 'forest', count: 1, seed: 1 }))
      .rejects.toThrow('AI palette count must be an integer from 2 to 9');
    await expect(generateAiPalette({
      prompt: 'forest',
      count: 4,
      seed: 1,
      lockedColors: [
        { index: 2, oklch: { l: 0.5, c: 0, h: null } },
        { index: 2, oklch: { l: 0.6, c: 0, h: null } },
      ],
    })).rejects.toThrow('Duplicate locked color index: 2');

    expect(encoderLoader).not.toHaveBeenCalled();
    expect(decoderLoader).not.toHaveBeenCalled();
  });

  it('does not return a procedural fallback when the decoder is unavailable and can retry', async () => {
    const encoder = installEncoder();
    let attempts = 0;
    setTestDecoderLoader(async () => {
      attempts++;
      if (attempts === 1) {
        throw new Error('decoder artifact unavailable');
      }
      return {
        modelVersion: 'palettebrain-v2-test',
        run: async () => makePaletteOutput(),
      };
    });

    const request = { prompt: 'blackout hospital', count: 4, seed: 88 };
    await expect(generateAiPalette(request)).rejects.toThrow('AI palette decoder load failed');
    const recovered = await generateAiPalette(request);

    expect(recovered.fallback).toBe(false);
    expect(recovered.colors).toHaveLength(4);
    expect(attempts).toBe(2);
    expect(encoder.model).toHaveBeenCalledOnce();
  });

  describe('Production Manifest Contract Validation', () => {
    it('validates the actual production manifest file on disk', async () => {
      const fs = await import('fs');
      const path = await import('path');
      const manifestPath = path.resolve(process.cwd(), 'public/models/palettebrain-v2.manifest.json');
      expect(fs.existsSync(manifestPath)).toBe(true);

      const raw = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      const { validateDecoderManifest } = await import('../inference');
      const validated = validateDecoderManifest(raw, { allowExperimental: true });

      expect(validated.modelVersion).toBeTruthy();
      expect(typeof validated.modelVersion).toBe('string');
      expect(validated.decoderPath).toMatch(/^\/models\/palettebrain-.*\.onnx$/);

      // Verify decoder ONNX artifact actually exists on disk
      const decoderFilePath = path.resolve(process.cwd(), `public${validated.decoderPath}`);
      expect(fs.existsSync(decoderFilePath)).toBe(true);
      const stat = fs.statSync(decoderFilePath);
      expect(stat.size).toBeGreaterThan(100_000);
    });

    it('rejects invalid manifests with missing or empty version', async () => {
      const { validateDecoderManifest } = await import('../inference');
      expect(() => validateDecoderManifest(null)).toThrow('manifest must be a JSON object');
      expect(() => validateDecoderManifest({})).toThrow('manifest schemaVersion must be 2');
      expect(() => validateDecoderManifest({ schemaVersion: 2, modelVersion: '   ' })).toThrow('manifest modelVersion must be a non-empty string');
      expect(() => validateDecoderManifest({ schemaVersion: 2, modelVersion: 'valid-v1', decoder: { path: 'invalid/path' } })).toThrow('manifest decoder path must be a valid path under /models/');
    });

    it('refuses an experimental decoder unless the qualification override is explicit', async () => {
      const fs = await import('fs');
      const path = await import('path');
      const raw = JSON.parse(fs.readFileSync(
        path.resolve(process.cwd(), 'public/models/palettebrain-v2.manifest.json'),
        'utf-8',
      ));
      const { validateDecoderManifest } = await import('../inference');
      expect(() => validateDecoderManifest(raw)).toThrow('manifest marks this decoder experimental');
      expect(validateDecoderManifest(raw, { allowExperimental: true }).productionReady).toBe(false);
    });
  });
});
