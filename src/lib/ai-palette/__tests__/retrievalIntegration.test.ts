import { beforeEach, describe, expect, it, vi } from 'vitest';
import { hexToOklch } from '@/lib/color/conversions';
import {
  generateAiPalette,
  resetEncoderSession,
  setTestDecoderLoader,
  setTestEncoderLoader,
  setTestRetrievalLoader,
} from '../inference';
import type { RetrievalArtifacts } from '../retrievalEngine';

function unitEmbedding(first: number, second = 0): number[] {
  const values = new Array<number>(384).fill(0);
  values[0] = first;
  values[1] = second;
  return values;
}

const artifacts: RetrievalArtifacts = {
  version: 'pat-tone-scorer-test',
  dimension: 384,
  embeddings: new Float32Array([
    ...unitEmbedding(1),
    ...unitEmbedding(0.9, 0.3),
    ...unitEmbedding(0.8, 0.5),
    ...unitEmbedding(0.7, 0.7),
  ]),
  palettes: [
    ['#10243a', '#315b68', '#6d9293', '#a8b8b5', '#d6d2c4'],
    ['#2a183a', '#52345e', '#8a6382', '#bd9b9b', '#ead8c6'],
    ['#172b25', '#35584a', '#73836b', '#a8a886', '#d4c9a5'],
    ['#261c18', '#593b2a', '#91633e', '#c69a68', '#e8d5ad'],
  ],
  tone: {
    layers: [{
      inFeatures: 384,
      outFeatures: 7,
      weights: new Array(384 * 7).fill(0),
      bias: [0.2, 0.42, 0.72, 0.07, 0.1, 0.28, 0.08],
      activation: 'linear',
    }],
    targetMean: new Array(7).fill(0),
    targetStd: new Array(7).fill(1),
  },
};

describe('retrieval production integration', () => {
  beforeEach(() => {
    setTestDecoderLoader(null);
    setTestRetrievalLoader(null);
    resetEncoderSession();
  });

  it('uses E5 retrieval and whole-palette scoring without loading the legacy decoder', async () => {
    const decoderLoader = vi.fn();
    const locked = hexToOklch('#ff00aa')!;
    setTestEncoderLoader(async () => ({
      tokenizer: vi.fn().mockResolvedValue({ attention_mask: { data: new Int32Array([1]) } }),
      model: vi.fn().mockResolvedValue({
        last_hidden_state: { data: new Float32Array(unitEmbedding(1)), dims: [1, 1, 384] },
      }),
    }));
    setTestDecoderLoader(decoderLoader);
    setTestRetrievalLoader(async () => artifacts);

    const result = await generateAiPalette({
      prompt: 'dark rain',
      count: 5,
      seed: 0,
      lockedColors: [{ index: 2, oklch: locked }],
    });

    expect(result.modelVersion).toBe('pat-tone-scorer-test');
    expect(result.colors).toHaveLength(5);
    expect(result.colors[2]).toEqual(locked);
    expect(result.fallback).toBe(false);
    expect(result.inference?.criticMs).toBeGreaterThanOrEqual(0);
    expect(decoderLoader).not.toHaveBeenCalled();
  });
});
