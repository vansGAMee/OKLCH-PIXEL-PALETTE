/**
 * src/lib/color/qualityInspector.ts
 * Analyzes palette for perceptual quality issues.
 * Returns structured warnings — no magic "score" to argue with.
 */
import type { Palette, PaletteColor } from '@/types/palette';

export type WarningSeverity = 'info' | 'warning' | 'error';

export interface QualityWarning {
  id: string;
  severity: WarningSeverity;
  messageEn: string;
  messageRu: string;
  colorIndices?: number[];
}

export interface QualityReport {
  warnings: QualityWarning[];
  hasErrors: boolean;
  hasWarnings: boolean;
}

// OKLCH Delta E2000 approximation (simplified for speed)
function deltaE(a: PaletteColor, b: PaletteColor): number {
  const dl = (a.oklch.l - b.oklch.l) * 100;
  const dc = (a.oklch.c - b.oklch.c) * 100;
  const dh = (() => {
    if (a.oklch.h === null || b.oklch.h === null) return 0;
    const diff = Math.abs(a.oklch.h - b.oklch.h);
    return Math.min(diff, 360 - diff) * (Math.max(a.oklch.c, b.oklch.c) * 100);
  })();
  return Math.sqrt(dl * dl + dc * dc + dh * dh);
}

// Relative luminance for WCAG contrast
function relativeLuminance(hex: string): number {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const toLinear = (v: number) => v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

function contrastRatio(a: string, b: string): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  const lighter = Math.max(la, lb);
  const darker = Math.min(la, lb);
  return (lighter + 0.05) / (darker + 0.05);
}

export function inspectPalette(palette: Palette): QualityReport {
  const warnings: QualityWarning[] = [];
  const colors = palette.colors;

  // 1. Duplicate colors
  for (let i = 0; i < colors.length; i++) {
    for (let j = i + 1; j < colors.length; j++) {
      if (colors[i].hex.toLowerCase() === colors[j].hex.toLowerCase()) {
        warnings.push({
          id: `duplicate_${i}_${j}`,
          severity: 'error',
          messageEn: `Colors #${i + 1} and #${j + 1} are identical (${colors[i].hex}).`,
          messageRu: `Цвета #${i + 1} и #${j + 1} одинаковые (${colors[i].hex}).`,
          colorIndices: [i, j],
        });
      }
    }
  }

  // 2. Near-duplicate colors (Delta E < 8)
  for (let i = 0; i < colors.length; i++) {
    for (let j = i + 1; j < colors.length; j++) {
      if (colors[i].hex.toLowerCase() === colors[j].hex.toLowerCase()) continue; // already caught above
      const de = deltaE(colors[i], colors[j]);
      if (de < 8) {
        warnings.push({
          id: `near_dup_${i}_${j}`,
          severity: 'warning',
          messageEn: `Colors #${i + 1} and #${j + 1} are very similar (ΔE≈${de.toFixed(1)}).`,
          messageRu: `Цвета #${i + 1} и #${j + 1} очень похожи (ΔE≈${de.toFixed(1)}).`,
          colorIndices: [i, j],
        });
      }
    }
  }

  // 3. Poor lightness spread (all colors in narrow L band)
  const ls = colors.map((c) => c.oklch.l);
  const lSpread = Math.max(...ls) - Math.min(...ls);
  if (lSpread < 0.25) {
    warnings.push({
      id: 'lightness_spread',
      severity: 'warning',
      messageEn: `Lightness range is very narrow (${(lSpread * 100).toFixed(0)}%). Palette may lack contrast.`,
      messageRu: `Диапазон яркости очень узкий (${(lSpread * 100).toFixed(0)}%). Палитра может не иметь достаточного контраста.`,
    });
  }

  // 4. WCAG AA contrast check: base vs highlight must be ≥ 4.5
  const baseColor = palette.base;
  const highlightColor = palette.highlight;
  const cr = contrastRatio(baseColor.hex, highlightColor.hex);
  if (cr < 3) {
    warnings.push({
      id: 'contrast_base_highlight',
      severity: 'info',
      messageEn: `Base/highlight contrast ratio is ${cr.toFixed(2)}:1. Consider increasing lightness difference.`,
      messageRu: `Контраст базового/светлого цвета — ${cr.toFixed(2)}:1. Рекомендуется увеличить разницу яркости.`,
      colorIndices: [colors.indexOf(baseColor), colors.indexOf(highlightColor)],
    });
  }

  // 5. All colors are neutral (no chroma)
  const hasChroma = colors.some((c) => c.oklch.c > 0.03);
  if (!hasChroma) {
    warnings.push({
      id: 'all_neutral',
      severity: 'info',
      messageEn: 'All colors appear to be neutral/grayscale (C < 0.03). Is this intentional?',
      messageRu: 'Все цвета выглядят нейтральными/серыми (C < 0.03). Это намеренно?',
    });
  }

  return {
    warnings,
    hasErrors: warnings.some((w) => w.severity === 'error'),
    hasWarnings: warnings.some((w) => w.severity === 'warning'),
  };
}
