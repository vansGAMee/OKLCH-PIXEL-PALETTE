import { it } from 'vitest';
import { inferPaletteIntent } from '../inference';
import { hexToOklch } from '@/lib/color/conversions';

it('repro', async () => {
  const prompts = ['black', 'white', 'winter', 'зима', 'purple', 'фиолетовый', 'ocean', 'fire', 'amethyst'];
  for (const p of prompts) {
    const intent = await inferPaletteIntent(p);
    const ok = hexToOklch(intent.baseHex);
    // eslint-disable-next-line no-console
    console.log(p.padEnd(14), intent.baseHex, 'L=' + ok.l.toFixed(2), 'C=' + ok.c.toFixed(3), 'H=' + ok.h.toFixed(0), intent.harmony);
  }
}, 300000);
