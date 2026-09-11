import { describe, expect, it } from 'vitest';
import { hexToOklch, oklchToHex } from '@/lib/color/conversions';
import {
  generateRetrievedPalette,
  type RetrievalArtifacts,
} from '../retrievalEngine';

function makeArtifacts(): RetrievalArtifacts {
  return {
    version: 'retrieval-test-v1',
    dimension: 3,
    embeddings: new Float32Array([
      1, 0, 0,
      0.99, 0.1, 0,
      0.97, 0.2, 0,
      0.95, 0.3, 0,
    ]),
    palettes: [
      ['#222222', '#222222', '#232323', '#242424', '#252525'],
      ['#10243a', '#315b68', '#6d9293', '#a8b8b5', '#d6d2c4'],
      ['#2a183a', '#52345e', '#8a6382', '#bd9b9b', '#ead8c6'],
      ['#172b25', '#35584a', '#73836b', '#a8a886', '#d4c9a5'],
    ],
    tone: {
      layers: [
        {
          inFeatures: 3,
          outFeatures: 7,
          weights: new Array(21).fill(0),
          bias: [0.2, 0.42, 0.72, 0.07, 0.1, 0.28, 0.08],
          activation: 'linear',
        },
      ],
      targetMean: new Array(7).fill(0),
      targetStd: new Array(7).fill(1),
    },
  };
}

describe('retrieval whole-palette engine', () => {
  it('rejects a collapsed nearest palette in favor of a coherent candidate', () => {
    const result = generateRetrievedPalette({
      embedding: new Float32Array([1, 0, 0]),
      count: 5,
      seed: 0,
      artifacts: makeArtifacts(),
    });

    expect(result.colors.map(oklchToHex)).not.toEqual([
      '#222222', '#222222', '#232323', '#242424', '#252525',
    ]);
    expect(result.scores.minDistance).toBeGreaterThan(0.035);
    expect(result.scores.penalties).toBeLessThan(0.15);
  });

  it('is deterministic, exposes ranked variants, and returns exactly 2-9 colors', () => {
    const artifacts = makeArtifacts();
    const request = {
      embedding: new Float32Array([1, 0, 0]),
      count: 4,
      artifacts,
    };

    const first = generateRetrievedPalette({ ...request, seed: 0 });
    const repeated = generateRetrievedPalette({ ...request, seed: 0 });
    const variation = generateRetrievedPalette({ ...request, seed: 1 });

    expect(first.colors).toEqual(repeated.colors);
    expect(variation.colors).not.toEqual(first.colors);
    expect(first.familyIndex).toBeTypeOf('number');
    expect(variation.familyIndex).toBe(first.familyIndex);
    expect(first.colors).toHaveLength(4);
    expect(generateRetrievedPalette({ ...request, count: 2, seed: 0 }).colors).toHaveLength(2);
    expect(generateRetrievedPalette({ ...request, count: 9, seed: 0 }).colors).toHaveLength(9);
  });

  it('preserves locked colors exactly while ranking the remaining palette', () => {
    const locked = hexToOklch('#ff00aa')!;
    const result = generateRetrievedPalette({
      embedding: new Float32Array([1, 0, 0]),
      count: 5,
      seed: 0,
      artifacts: makeArtifacts(),
      lockedColors: new Map([[2, locked]]),
    });

    expect(result.colors[2]).toEqual(locked);
    expect(oklchToHex(result.colors[2])).toBe('#ff00aa');
  });

  it('validates artifact and request dimensions', () => {
    const artifacts = makeArtifacts();
    expect(() => generateRetrievedPalette({
      embedding: new Float32Array([1, 0]),
      count: 5,
      seed: 0,
      artifacts,
    })).toThrow('embedding dimension');
    expect(() => generateRetrievedPalette({
      embedding: new Float32Array([1, 0, 0]),
      count: 10,
      seed: 0,
      artifacts,
    })).toThrow('2 to 9');
  });
});
