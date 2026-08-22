import { describe, it, expect } from 'vitest';
import { parseTargetPalette, findNearestColorHex, recolorPixelBuffer } from '../spriteRecolor';
import { hexToOklch } from '@/lib/color/conversions';

describe('spriteRecolor', () => {
  it('parses target palette correctly', () => {
    const targets = parseTargetPalette('#ff0000, #00ff00; #0000ff');
    expect(targets).toHaveLength(3);
    expect(targets[0].hex).toBe('#ff0000');
  });

  it('maps colors accurately based on OKLCH distance', () => {
    const targets = parseTargetPalette('#ff0000 #0000ff');
    const darkRedOklch = hexToOklch('#880000')!;
    const darkBlueOklch = hexToOklch('#000088')!;

    expect(findNearestColorHex(darkRedOklch, targets)).toBe('#ff0000');
    expect(findNearestColorHex(darkBlueOklch, targets)).toBe('#0000ff');
  });

  it('recolors buffer while preserving alpha channel', () => {
    const targets = parseTargetPalette('#ff0000 #0000ff');
    const src = new Uint8ClampedArray([
      250, 10, 10, 255,   // red-ish, opaque
      10, 10, 250, 180,   // blue-ish, semi-transparent
      0, 0, 0, 0,         // fully transparent
    ]);
    const target = new Uint8ClampedArray(12);

    recolorPixelBuffer(src, target, targets);

    // Red pixel -> #ff0000
    expect(target[0]).toBe(255);
    expect(target[1]).toBe(0);
    expect(target[2]).toBe(0);
    expect(target[3]).toBe(255);

    // Blue pixel -> #0000ff, alpha = 180 preserved
    expect(target[4]).toBe(0);
    expect(target[5]).toBe(0);
    expect(target[6]).toBe(255);
    expect(target[7]).toBe(180);

    // Transparent pixel -> alpha = 0 preserved
    expect(target[11]).toBe(0);
  });
});
