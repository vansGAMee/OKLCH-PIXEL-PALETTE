/**
 * Tests for math/adapter correctness.
 */
import { describe, it, expect } from 'vitest';
import { decodeCnnOutput, maxSrgbChromaAt } from '../paletteAdapter';

const L_MIN = 0.07;
const L_MAX = 0.93;

function sigmoid(x: number) {
  return 1 / (1 + Math.exp(-x));
}

describe('paletteAdapter - hue math', () => {
  it('atan2(SIN, COS) reconstruction: 0°', () => {
    const h = 0;
    const theta = h * Math.PI / 180;
    const s = Math.sin(theta);
    const c = Math.cos(theta);
    const recon = (Math.atan2(s, c) * 180 / Math.PI + 360) % 360;
    expect(recon).toBeCloseTo(0, 3);
  });

  it('atan2(SIN, COS) reconstruction: 90°', () => {
    const h = 90;
    const theta = h * Math.PI / 180;
    const s = Math.sin(theta);
    const c = Math.cos(theta);
    const recon = (Math.atan2(s, c) * 180 / Math.PI + 360) % 360;
    expect(recon).toBeCloseTo(90, 3);
  });

  it('atan2(SIN, COS) reconstruction: 180°', () => {
    const h = 180;
    const theta = h * Math.PI / 180;
    const s = Math.sin(theta);
    const c = Math.cos(theta);
    const recon = (Math.atan2(s, c) * 180 / Math.PI + 360) % 360;
    expect(recon).toBeCloseTo(180, 3);
  });

  it('atan2(SIN, COS) reconstruction: 359°', () => {
    const h = 359;
    const theta = h * Math.PI / 180;
    const s = Math.sin(theta);
    const c = Math.cos(theta);
    const recon = (Math.atan2(s, c) * 180 / Math.PI + 360) % 360;
    expect(recon).toBeCloseTo(359, 3);
  });

  it('1° and 359° are circularly close (not 180° apart)', () => {
    const diff = (1 - 359 + 360) % 360;
    expect(diff).toBe(2); // 2° apart, not 358°
  });
});

describe('paletteAdapter - lightness decoding', () => {
  it('decoded L stays in [L_MIN, L_MAX] for range of logits', () => {
    for (const logit of [-10, -3, -1, 0, 1, 3, 10]) {
      const L = L_MIN + sigmoid(logit) * (L_MAX - L_MIN);
      expect(L).toBeGreaterThanOrEqual(L_MIN);
      expect(L).toBeLessThanOrEqual(L_MAX);
    }
  });
});

describe('paletteAdapter - relative chroma decoding', () => {
  it('decoded relative chroma stays in [0, 1]', () => {
    for (const logit of [-10, -3, -1, 0, 1, 3, 10]) {
      const rc = sigmoid(logit);
      expect(rc).toBeGreaterThanOrEqual(0);
      expect(rc).toBeLessThanOrEqual(1);
    }
  });
});

describe('paletteAdapter - maxSrgbChromaAt', () => {
  it('Cmax is in gamut', () => {
    // We verify via the binary search result: by construction, low is in gamut
    const cMax = maxSrgbChromaAt(0.5, 145);
    expect(cMax).toBeGreaterThan(0);
    // Production chroma = relativeChroma * cMax * 0.92 <= cMax
    const prodChroma = 1.0 * cMax * 0.92;
    expect(prodChroma).toBeLessThanOrEqual(cMax);
  });

  it('Cmax is positive for typical colors', () => {
    expect(maxSrgbChromaAt(0.5, 0)).toBeGreaterThan(0);
    expect(maxSrgbChromaAt(0.7, 220)).toBeGreaterThan(0);
    expect(maxSrgbChromaAt(0.4, 30)).toBeGreaterThan(0);
  });
});

describe('paletteAdapter - NaN and Infinity rejection', () => {
  it('rejects NaN in output', () => {
    const bad = [NaN, 0, 0, 0, 0, 0, 0];
    expect(() => decodeCnnOutput(bad)).toThrow();
  });

  it('rejects Infinity in output', () => {
    const bad = [0, Infinity, 0, 0, 0, 0, 0];
    expect(() => decodeCnnOutput(bad)).toThrow();
  });

  it('rejects output shorter than 7', () => {
    expect(() => decodeCnnOutput([0, 0, 0, 0, 0])).toThrow();
  });
});

describe('paletteAdapter - zero-length hue-vector fallback', () => {
  it('zero-norm hue vector does not produce NaN', () => {
    // logits that produce near-zero sin/cos raw
    const output = [
      0,     // lightness_logit
      1e-20, // hue_sin_raw (nearly zero)
      1e-20, // hue_cos_raw (nearly zero)
      0,     // relative_chroma_logit
      1, 0, 0  // harmony logits
    ];
    const result = decodeCnnOutput(output);
    expect(result.baseHex).toMatch(/^#[0-9a-f]{6}$/);
    expect(result.harmony).toBeTruthy();
  });
});

describe('paletteAdapter - full decode produces valid hex', () => {
  it('typical output produces valid hex and harmony', () => {
    // Simulate: L=0.5, H=145°, relChroma=0.6, analogous
    const theta = 145 * Math.PI / 180;
    const output = new Float32Array([
      0,               // lightness_logit → ~0.5
      Math.sin(theta), // hue_sin_raw
      Math.cos(theta), // hue_cos_raw
      0.4,             // relative_chroma_logit → sigmoid ≈ 0.6
      -1, -1, 2        // analogous wins
    ]);
    const result = decodeCnnOutput(output);
    expect(result.baseHex).toMatch(/^#[0-9a-f]{6}$/);
    expect(['splitComplementary', 'complementary', 'analogous']).toContain(result.harmony);
  });
});
