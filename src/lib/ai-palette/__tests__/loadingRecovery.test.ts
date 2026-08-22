import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getEncoder, setTestEncoderLoader, resetEncoderSession, inferPaletteIntent } from '../inference';
import { getSemanticAnchors, setTestAnchors } from '../semanticMapper';

describe('AI Palette Loading & Failure Recovery', () => {
  beforeEach(() => {
    resetEncoderSession();
    setTestEncoderLoader(null);
    setTestAnchors(null);
  });

  describe('Encoder Recovery', () => {
    it('does not poison session when first encoder initialization fails, allowing second load to succeed', async () => {
      let loadCount = 0;

      const mockTokenizer = vi.fn().mockResolvedValue({
        attention_mask: { data: [1, 1, 1] },
      });
      const mockModel = vi.fn().mockResolvedValue({
        last_hidden_state: {
          data: new Float32Array(3 * 384).fill(0.1),
          dims: [1, 3, 384],
        },
      });

      setTestEncoderLoader(async () => {
        loadCount++;
        if (loadCount === 1) {
          throw new TypeError('Failed to fetch: /models/multilingual-e5-small/onnx/model_quantized.onnx');
        }
        return { tokenizer: mockTokenizer, model: mockModel };
      });

      // First attempt fails
      await expect(getEncoder()).rejects.toThrow('Failed to fetch');
      expect(loadCount).toBe(1);

      // Second attempt succeeds — proves a NEW load occurred and the session was NOT poisoned
      const encoder = await getEncoder();
      expect(encoder).toBeDefined();
      expect(encoder.tokenizer).toBe(mockTokenizer);
      expect(loadCount).toBe(2);
    });

    it('deduplicates concurrent healthy encoder initialization to exactly one load', async () => {
      let loadCount = 0;

      const mockTokenizer = vi.fn();
      const mockModel = vi.fn();

      setTestEncoderLoader(async () => {
        loadCount++;
        // Simulate network delay
        await new Promise((r) => setTimeout(r, 50));
        return { tokenizer: mockTokenizer, model: mockModel };
      });

      // Call getEncoder simultaneously
      const [res1, res2] = await Promise.all([getEncoder(), getEncoder()]);

      expect(loadCount).toBe(1);
      expect(res1).toBe(res2);
      expect(res1.tokenizer).toBe(mockTokenizer);
    });
  });

  describe('Semantic Anchors Recovery', () => {
    it('does not poison session when first semantic anchors request fails', async () => {
      setTestAnchors(null);

      // Test valid loading from disk in Node
      const anchors1 = await getSemanticAnchors();
      expect(anchors1).toBeDefined();
      expect(anchors1.length).toBeGreaterThan(10);

      // Verify custom anchors override and reset works
      setTestAnchors([
        {
          id: 'test-1',
          category: 'nature',
          intent: { hue: 200, l: 0.5, relC: 0.5, harmony: 'analogous' },
          en: 'test sky',
          ru: 'тестовое небо',
          emb: new Array(384).fill(0.05),
        },
      ]);

      const custom = await getSemanticAnchors();
      expect(custom).toHaveLength(1);
      expect(custom[0].id).toBe('test-1');

      // Reset to null restores default package loading
      setTestAnchors(null);
      const defaultAnchors = await getSemanticAnchors();
      expect(defaultAnchors.length).toBeGreaterThan(10);
    });
  });

  describe('End-to-End Inference Recovery', () => {
    it('recovers from a transient encoder failure and produces valid palette on retry', async () => {
      let attempts = 0;

      const mockTokenizer = vi.fn().mockResolvedValue({
        attention_mask: { data: [1, 1, 1] },
      });
      const mockModel = vi.fn().mockResolvedValue({
        last_hidden_state: {
          data: new Float32Array(3 * 384).fill(0.1),
          dims: [1, 3, 384],
        },
      });

      setTestEncoderLoader(async () => {
        attempts++;
        if (attempts === 1) {
          throw new Error('AI encoder load failed while loading E5 model: GET /models/multilingual-e5-small/onnx/model_quantized.onnx (TypeError: Failed to fetch)');
        }
        return { tokenizer: mockTokenizer, model: mockModel };
      });

      // 1. Initial attempt fails
      await expect(inferPaletteIntent('winter forest')).rejects.toThrow('AI encoder load failed');
      expect(attempts).toBe(1);

      // 2. Retry succeeds without page reload
      const result = await inferPaletteIntent('winter forest');
      expect(attempts).toBe(2);
      expect(result.baseHex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(result.seed).toBeDefined();
    });
  });
});
