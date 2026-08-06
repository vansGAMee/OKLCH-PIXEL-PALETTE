import { OklchColor } from '@/types/palette';

/**
 * Returns a concise, professional human-readable English name for a color based on its OKLCH values.
 * Used for additional colors in palettes (5th color and beyond).
 */
export function getOklchColorName(oklch: OklchColor): string {
  const { l, c, h } = oklch;

  // Extremely dark or light
  if (l <= 0.06) return 'NEAR BLACK';
  if (l >= 0.97) return 'NEAR WHITE';

  // Low chroma (neutrals / grays)
  if (c < 0.025) {
    if (l < 0.25) return 'DEEP SLATE';
    if (l < 0.45) return 'DARK GRAY';
    if (l < 0.70) return 'SOFT GRAY';
    if (l < 0.88) return 'LIGHT GRAY';
    return 'PALE MIST';
  }

  // Determine Lightness / Intensity modifier
  let modifier = '';
  if (l < 0.25) modifier = 'DEEP';
  else if (l < 0.42) modifier = 'DARK';
  else if (l > 0.82) modifier = 'PALE';
  else if (l > 0.68) modifier = 'LIGHT';
  else if (c > 0.16) modifier = 'VIBRANT';
  else if (c < 0.06) modifier = 'MUTED';

  // Determine Hue Family (0 to 360 degrees)
  let hueName = 'COLOR';
  if (h === null) {
    hueName = 'GRAY';
  } else {
    const hue = ((h % 360) + 360) % 360;
    if (hue >= 345 || hue < 15) hueName = 'RED';
    else if (hue >= 15 && hue < 40) hueName = 'ORANGE';
    else if (hue >= 40 && hue < 70) hueName = 'AMBER';
    else if (hue >= 70 && hue < 100) hueName = 'YELLOW';
    else if (hue >= 100 && hue < 140) hueName = 'LIME';
    else if (hue >= 140 && hue < 170) hueName = 'GREEN';
    else if (hue >= 170 && hue < 200) hueName = 'TEAL';
    else if (hue >= 200 && hue < 235) hueName = 'CYAN';
    else if (hue >= 235 && hue < 265) hueName = 'BLUE';
    else if (hue >= 265 && hue < 290) hueName = 'INDIGO';
    else if (hue >= 290 && hue < 320) hueName = 'PURPLE';
    else if (hue >= 320 && hue < 345) hueName = 'PINK';
  }

  return modifier ? `${modifier} ${hueName}` : hueName;
}

/**
 * Returns user-facing color label based on index and palette total count.
 */
export function getPaletteColorLabel(role: string, index: number, numColors: number, oklch?: OklchColor): string {
  if (numColors === 2) {
    return index === 0 ? 'SHADOW' : 'BASE';
  }
  if (numColors === 3) {
    return index === 0 ? 'SHADOW' : index === 1 ? 'BASE' : 'HIGHLIGHT';
  }
  // For 4 to 9 colors: first 4 are ALWAYS SHADOW, BASE, HIGHLIGHT, ACCENT
  if (index === 0) return 'SHADOW';
  if (index === 1) return 'BASE';
  if (index === 2) return 'HIGHLIGHT';
  if (index === 3) return 'ACCENT';

  // For index >= 4 (5th color and beyond): generate human-readable OKLCH name
  if (oklch) {
    return getOklchColorName(oklch);
  }
  return role.startsWith('color') ? `COLOR ${index + 1}` : role.toUpperCase();
}
