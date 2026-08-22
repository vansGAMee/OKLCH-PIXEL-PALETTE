import { describe, it, expect } from 'vitest';
import { extractPalette } from '../imageQuantize';

describe('imageQuantize', () => {
  it('extracts colors from synthetic ImageData buffer', () => {
    // 4x4 image: 8 pixels red, 8 pixels blue
    const data = new Uint8ClampedArray(4 * 4 * 4);
    for (let i = 0; i < 8; i++) {
      data[i * 4] = 255;     // R
      data[i * 4 + 1] = 0;   // G
      data[i * 4 + 2] = 0;   // B
      data[i * 4 + 3] = 255; // A
    }
    for (let i = 8; i < 16; i++) {
      data[i * 4] = 0;       // R
      data[i * 4 + 1] = 0;   // G
      data[i * 4 + 2] = 255; // B
      data[i * 4 + 3] = 255; // A
    }

    const mockImageData = {
      data,
      width: 4,
      height: 4,
      colorSpace: 'srgb' as PredefinedColorSpace,
    };

    const res = extractPalette(mockImageData, 4);
    expect(res.colors.length).toBeGreaterThanOrEqual(2);
    expect(res.totalPixels).toBe(16);
  });

  it('ignores fully transparent pixels', () => {
    const data = new Uint8ClampedArray(4 * 4 * 4);
    // All transparent except 1 pixel green
    data[0] = 0;
    data[1] = 255;
    data[2] = 0;
    data[3] = 255; // green

    const mockImageData = {
      data,
      width: 4,
      height: 4,
      colorSpace: 'srgb' as PredefinedColorSpace,
    };

    const res = extractPalette(mockImageData, 3);
    expect(res.colors.length).toBeGreaterThanOrEqual(1);
  });
});
