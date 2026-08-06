import { HarmonyMode, OklchColor } from '@/types/palette';
import { fitToSrgb } from './gamut';
import { calculateDeltaE } from './validation';

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

/**
 * Gets candidate hues based on base hue and selected harmony mode.
 */
export function getHarmonyCandidateHues(baseHue: number | null, harmony: HarmonyMode): number[] {
  if (baseHue === null) {
    switch (harmony) {
      case 'splitComplementary':
        return [260, 280];
      case 'complementary':
        return [240];
      case 'analogous':
        return [210, 310];
      case 'triadic':
        return [120, 240];
      case 'tetradic':
        return [90, 180, 270];
      case 'monochromatic':
        return [260];
    }
  }

  const h = (baseHue % 360 + 360) % 360;

  switch (harmony) {
    case 'splitComplementary':
      return [(h + 150) % 360, (h + 210) % 360];
    case 'complementary':
      return [(h + 180) % 360];
    case 'analogous':
      return [(h - 30 + 360) % 360, (h + 30) % 360];
    case 'triadic':
      return [(h + 120) % 360, (h + 240) % 360];
    case 'tetradic':
      return [(h + 90) % 360, (h + 180) % 360, (h + 270) % 360];
    case 'monochromatic':
      return [h];
  }
}

/**
 * Evaluates candidate accent colors and selects the best candidate.
 */
export function generateAccentCandidate(
  base: OklchColor,
  shadow: OklchColor,
  highlight: OklchColor,
  harmony: HarmonyMode,
  seedOffset: number = 0
): OklchColor {
  const isNeutralBase = base.c < 0.025;

  // Initial parameters
  let targetL = base.l >= 0.62 ? 0.38 : 0.76;
  targetL = clamp(targetL + (seedOffset * 0.02 - 0.01), 0.2, 0.85);

  let targetC = isNeutralBase
    ? 0.13
    : clamp(Math.max(base.c, 0.14), 0.1, 0.22);
  targetC = clamp(targetC + (seedOffset * 0.01 - 0.005), 0.08, 0.24);

  const candidateHues = getHarmonyCandidateHues(base.h, harmony);

  let bestCandidate: OklchColor | null = null;
  let bestScore = -Infinity;

  for (const hue of candidateHues) {
    const rawCandidate: OklchColor = {
      l: targetL,
      c: targetC,
      h: (hue + 360) % 360,
    };

    const srgbCandidate = fitToSrgb(rawCandidate);

    // Scoring metrics:
    // 1. Delta E from Base (higher is better, want >= 0.12)
    const deltaBase = calculateDeltaE(srgbCandidate, base);
    // 2. Delta E from Shadow & Highlight
    const deltaShadow = calculateDeltaE(srgbCandidate, shadow);
    const deltaHighlight = calculateDeltaE(srgbCandidate, highlight);
    const minDelta = Math.min(deltaBase, deltaShadow, deltaHighlight);

    // 3. Chroma retention (avoid washed out colors)
    const chromaRatio = targetC > 0 ? srgbCandidate.c / targetC : 1;

    // 4. Lightness separation from Base
    const lDiff = Math.abs(srgbCandidate.l - base.l);

    const score = minDelta * 3.0 + lDiff * 2.0 + chromaRatio * 1.5;

    if (score > bestScore) {
      bestScore = score;
      bestCandidate = srgbCandidate;
    }
  }

  return bestCandidate ?? fitToSrgb({ l: targetL, c: targetC, h: candidateHues[0] ?? 260 });
}
