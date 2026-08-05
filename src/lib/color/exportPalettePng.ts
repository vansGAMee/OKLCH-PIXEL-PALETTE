import { Palette } from '@/types/palette';

/**
 * Renders the 4-color palette onto a canvas and triggers PNG download.
 */
export function exportPalettePng(palette: Palette, filename: string = 'pixel-palette.png') {
  const canvas = document.createElement('canvas');
  const width = 800;
  const height = 450;
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
  ctx.fillText(`Harmony: ${palette.harmony.toUpperCase()} | Seed: ${palette.seed}`, 30, 72);

  // Swatches
  const swatches = [
    { label: 'SHADOW', color: palette.shadow },
    { label: 'BASE', color: palette.base },
    { label: 'HIGHLIGHT', color: palette.highlight },
    { label: 'ACCENT', color: palette.accent },
  ];

  const swatchWidth = 175;
  const swatchHeight = 240;
  const startX = 30;
  const startY = 100;
  const gap = 15;

  swatches.forEach((swatch, i) => {
    const x = startX + i * (swatchWidth + gap);
    const y = startY;

    // Swatch fill
    ctx.fillStyle = swatch.color.hex;
    ctx.fillRect(x, y, swatchWidth, swatchHeight);

    // Inner shadow border
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, swatchWidth, swatchHeight);

    // Text box at bottom of swatch
    ctx.fillStyle = 'rgba(9, 9, 9, 0.85)';
    ctx.fillRect(x, y + swatchHeight - 65, swatchWidth, 65);

    ctx.fillStyle = '#f7f9fa';
    ctx.font = 'bold 13px monospace';
    ctx.fillText(swatch.label, x + 12, y + swatchHeight - 42);

    ctx.fillStyle = '#af50ff';
    ctx.font = '14px monospace';
    ctx.fillText(swatch.color.hex.toUpperCase(), x + 12, y + swatchHeight - 20);

    ctx.fillStyle = '#828384';
    ctx.font = '10px monospace';
    ctx.fillText(`L:${swatch.color.oklch.l.toFixed(2)} C:${swatch.color.oklch.c.toFixed(2)}`, x + 12, y + swatchHeight - 6);
  });

  // Footer stamp
  ctx.fillStyle = '#474747';
  ctx.font = '11px monospace';
  ctx.fillText('GENERATED WITH OKLCH COLOR THEORY ENGINE', 30, 415);

  // Trigger download
  const dataUrl = canvas.toDataURL('image/png');
  const link = document.createElement('a');
  link.download = filename;
  link.href = dataUrl;
  link.click();
}
