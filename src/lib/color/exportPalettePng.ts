import { Palette } from '@/types/palette';
import { getPaletteColorLabel } from './colorNaming';

/**
 * Renders the 4-color palette onto a canvas and triggers PNG download.
 */
export function exportPalettePng(palette: Palette, filename: string = 'pixel-palette.png') {
  if (typeof document === 'undefined') return;

  const colors = palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent];

  const numColors = colors.length;

  const width = 800;
  // Increase canvas height for 5-9 colors (2-row grid)
  const height = numColors <= 4 ? 450 : 580;

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // Background
  ctx.fillStyle = '#090909';
  ctx.fillRect(0, 0, width, height);

  // Border & Header
  ctx.strokeStyle = '#262626';
  ctx.lineWidth = 2;
  ctx.strokeRect(10, 10, width - 20, height - 20);

  // Title text
  ctx.fillStyle = '#f7f9fa';
  ctx.font = 'bold 22px monospace';
  ctx.fillText('PIXEL ART PALETTE', 30, 48);

  ctx.fillStyle = '#828384';
  ctx.font = '14px monospace';
  ctx.fillText(`Harmony: ${palette.harmony.toUpperCase()} | Seed: ${palette.seed} | Colors: ${numColors}`, 30, 72);

  const getLabel = (color: typeof colors[0], index: number): string => {
    return getPaletteColorLabel(color.role, index, numColors, color.oklch);
  };

  // Swatch Layout Calculations
  if (numColors <= 4) {
    // 1-Row Layout (Exact match for 4 colors: w=175, h=240, startX=30, startY=100, gap=15)
    let swatchWidth = 175;
    const swatchHeight = 240;
    let gap = 15;
    let startX = 30;
    const startY = 100;

    if (numColors === 2) {
      swatchWidth = 240;
      gap = 20;
      startX = (width - (2 * swatchWidth + gap)) / 2; // 150
    } else if (numColors === 3) {
      swatchWidth = 225;
      gap = 15;
      startX = (width - (3 * swatchWidth + 2 * gap)) / 2; // 47.5
    }

    colors.forEach((col, i) => {
      const x = startX + i * (swatchWidth + gap);
      const y = startY;
      drawSwatch(ctx, col, getLabel(col, i), x, y, swatchWidth, swatchHeight);
    });
  } else {
    // 2-Row Adaptive Grid Layout for 5-9 Colors
    const topCount = Math.ceil(numColors / 2);
    const botCount = numColors - topCount;

    let swatchWidth = 175;
    let gap = 15;
    if (topCount === 3) {
      swatchWidth = 225;
      gap = 15;
    } else if (topCount === 5) {
      swatchWidth = 136;
      gap = 12;
    }

    const swatchHeight = 180;
    const topStartX = (width - (topCount * swatchWidth + (topCount - 1) * gap)) / 2;
    const botStartX = (width - (botCount * swatchWidth + (botCount - 1) * gap)) / 2;

    colors.forEach((col, i) => {
      const isTop = i < topCount;
      const rowIdx = isTop ? i : i - topCount;
      const startX = isTop ? topStartX : botStartX;
      const startY = isTop ? 100 : 300;

      const x = startX + rowIdx * (swatchWidth + gap);
      const y = startY;
      drawSwatch(ctx, col, getLabel(col, i), x, y, swatchWidth, swatchHeight);
    });
  }

  // Footer stamp
  ctx.fillStyle = '#474747';
  ctx.font = '11px monospace';
  ctx.fillText('GENERATED WITH OKLCH COLOR THEORY ENGINE', 30, height - 35);

  // Trigger download if element attached
  const dataUrl = canvas.toDataURL('image/png');
  const link = document.createElement('a');
  link.download = filename;
  link.href = dataUrl;
  link.click();
}

/**
 * Helper to render individual swatch on canvas
 */
function drawSwatch(
  ctx: CanvasRenderingContext2D,
  color: { hex: string; oklch: { l: number; c: number; h: number | null } },
  label: string,
  x: number,
  y: number,
  w: number,
  h: number
) {
  // Swatch fill
  ctx.fillStyle = color.hex;
  ctx.fillRect(x, y, w, h);

  // Inner shadow border
  ctx.strokeStyle = 'rgba(255,255,255,0.15)';
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);

  // Text box at bottom of swatch
  const boxHeight = 65;
  ctx.fillStyle = 'rgba(9, 9, 9, 0.85)';
  ctx.fillRect(x, y + h - boxHeight, w, boxHeight);

  ctx.fillStyle = '#f7f9fa';
  ctx.font = 'bold 13px monospace';
  ctx.fillText(label, x + 10, y + h - 42);

  ctx.fillStyle = '#af50ff';
  ctx.font = '14px monospace';
  ctx.fillText(color.hex.toUpperCase(), x + 10, y + h - 20);

  ctx.fillStyle = '#828384';
  ctx.font = '10px monospace';
  ctx.fillText(
    `L:${color.oklch.l.toFixed(2)} C:${color.oklch.c.toFixed(2)}`,
    x + 10,
    y + h - 6
  );
}
