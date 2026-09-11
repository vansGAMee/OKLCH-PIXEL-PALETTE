import { converter, parse } from 'culori';
import type { OklchColor } from '@/types/palette';
import { hexToOklch, oklchToHex } from '@/lib/color/conversions';
import { fitToSrgb } from '@/lib/color/gamut';

const toOklab = converter('oklab');
const TONE_SCALE = [0.25, 0.25, 0.25, 0.12, 0.12, 0.30, 0.15] as const;

export interface ToneLayerArtifacts {
  inFeatures: number;
  outFeatures: number;
  weights: number[];
  bias: number[];
  activation: 'relu' | 'linear';
}

export interface ToneArtifacts {
  layers: ToneLayerArtifacts[];
  targetMean: number[];
  targetStd: number[];
}

export interface RetrievalArtifacts {
  version: string;
  dimension: number;
  embeddings: Float32Array;
  palettes: string[][];
  tone: ToneArtifacts;
}

export interface PaletteScores {
  semantic: number;
  tone: number;
  harmony: number;
  diversity: number;
  structure: number;
  penalties: number;
  minDistance: number;
  total: number;
}

export interface RetrievedPaletteResult {
  colors: OklchColor[];
  scores: PaletteScores;
  sourceIndex: number;
  familyIndex: number;
  variantIndex: number;
}

interface Candidate {
  colors: OklchColor[];
  scores: PaletteScores;
  sourceIndex: number;
  familyIndex: number;
}

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

function quantile(values: number[], q: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return sorted[lower];
  return sorted[lower] * (upper - position) + sorted[upper] * (position - lower);
}

function hexToLab(hex: string): [number, number, number] {
  const value = parse(hex);
  const lab = value ? toOklab(value) : undefined;
  if (!lab) throw new Error(`Invalid palette color: ${hex}`);
  return [lab.l ?? 0, lab.a ?? 0, lab.b ?? 0];
}

function colorToLab(color: OklchColor): [number, number, number] {
  return hexToLab(oklchToHex(color));
}

function distance(a: readonly number[], b: readonly number[]): number {
  let sum = 0;
  for (let index = 0; index < a.length; index++) {
    const delta = a[index] - b[index];
    sum += delta * delta;
  }
  return Math.sqrt(sum);
}

function runToneHead(embedding: Float32Array, tone: ToneArtifacts): number[] {
  let values = Array.from(embedding);
  for (const layer of tone.layers) {
    if (
      values.length !== layer.inFeatures
      || layer.weights.length !== layer.inFeatures * layer.outFeatures
      || layer.bias.length !== layer.outFeatures
    ) {
      throw new Error('ToneHead artifact dimensions are invalid');
    }
    const next = new Array<number>(layer.outFeatures);
    for (let output = 0; output < layer.outFeatures; output++) {
      let value = layer.bias[output];
      const offset = output * layer.inFeatures;
      for (let input = 0; input < layer.inFeatures; input++) {
        value += layer.weights[offset + input] * values[input];
      }
      next[output] = layer.activation === 'relu' ? Math.max(0, value) : value;
    }
    values = next;
  }
  if (values.length !== 7 || tone.targetMean.length !== 7 || tone.targetStd.length !== 7) {
    throw new Error('ToneHead output contract must contain 7 values');
  }
  return values.map((value, index) => value * tone.targetStd[index] + tone.targetMean[index]);
}

function selectSeparatedColors(palettes: readonly string[][], count: number): string[] {
  const pool = [...new Set(palettes.flat().map((color) => color.toLowerCase()))];
  if (pool.length < count) throw new Error(`Only ${pool.length} unique retrieved colors are available`);

  const primary = [...new Set(palettes[0].map((color) => color.toLowerCase()))];
  if (count <= primary.length) {
    const labs = primary.map(hexToLab);
    const selected = [labs.reduce((best, lab, index) => lab[0] < labs[best][0] ? index : best, 0)];
    if (count > 1) {
      selected.push(labs.reduce((best, lab, index) => lab[0] > labs[best][0] ? index : best, 0));
    }
    while (selected.length < count) {
      let bestIndex = -1;
      let bestDistance = -1;
      for (let index = 0; index < primary.length; index++) {
        if (selected.includes(index)) continue;
        const nearest = Math.min(...selected.map((chosen) => distance(labs[index], labs[chosen])));
        if (nearest > bestDistance) {
          bestDistance = nearest;
          bestIndex = index;
        }
      }
      selected.push(bestIndex);
    }
    return selected.sort((a, b) => a - b).map((index) => primary[index]);
  }

  const selected = [...primary];
  const selectedLabs = selected.map(hexToLab);
  for (const color of pool) {
    if (selected.length >= count) break;
    if (!selected.includes(color)) {
      let bestColor = color;
      let bestDistance = -1;
      for (const candidate of pool.filter((item) => !selected.includes(item))) {
        const candidateLab = hexToLab(candidate);
        const nearest = Math.min(...selectedLabs.map((lab) => distance(candidateLab, lab)));
        if (nearest > bestDistance) {
          bestDistance = nearest;
          bestColor = candidate;
        }
      }
      selected.push(bestColor);
      selectedLabs.push(hexToLab(bestColor));
    }
  }
  return selected;
}

function transformTone(palette: readonly string[], target: readonly number[], strength: number): OklchColor[] {
  const colors = palette.map((hex) => {
    const color = hexToOklch(hex);
    if (!color) throw new Error(`Invalid palette color: ${hex}`);
    return color;
  });
  const order = colors.map((_, index) => index).sort((a, b) => colors[a].l - colors[b].l);
  const lower = clamp(target[0] - 0.45 * (target[1] - target[0]), 0.03, 0.97);
  const upper = clamp(target[2] + 0.45 * (target[2] - target[1]), 0.03, 0.97);
  const curveX = [0, 0.2, 0.5, 0.8, 1];
  const curveY = [lower, target[0], target[1], target[2], upper];
  const desired = new Array<number>(colors.length);
  for (let rank = 0; rank < colors.length; rank++) {
    const x = colors.length === 1 ? 0 : rank / (colors.length - 1);
    let segment = curveX.findIndex((value) => value >= x);
    if (segment <= 0) desired[order[rank]] = curveY[0];
    else {
      segment = Math.min(segment, curveX.length - 1);
      const ratio = (x - curveX[segment - 1]) / (curveX[segment] - curveX[segment - 1]);
      desired[order[rank]] = curveY[segment - 1] * (1 - ratio) + curveY[segment] * ratio;
    }
  }
  const meanChroma = colors.reduce((sum, color) => sum + color.c, 0) / colors.length;
  const chromaScale = clamp(Math.max(0, target[3]) / Math.max(meanChroma, 0.015), 0.25, 2.5);
  return colors.map((color, index) => fitToSrgb({
    l: (1 - strength) * color.l + strength * desired[index],
    c: color.c * ((1 - strength) + strength * chromaScale),
    h: color.h,
  }));
}

function paletteStats(colors: readonly OklchColor[]): number[] {
  const labs = colors.map(colorToLab);
  const lightness = colors.map((color) => color.l);
  const chroma = colors.map((color) => color.c);
  const pairwise: number[] = [];
  for (let left = 0; left < labs.length; left++) {
    for (let right = left + 1; right < labs.length; right++) pairwise.push(distance(labs[left], labs[right]));
  }
  return [
    quantile(lightness, 0.2),
    quantile(lightness, 0.5),
    quantile(lightness, 0.8),
    chroma.reduce((sum, value) => sum + value, 0) / chroma.length,
    quantile(chroma, 0.8),
    pairwise.reduce((sum, value) => sum + value, 0) / pairwise.length,
    Math.min(...pairwise),
  ];
}

function scorePalette(colors: readonly OklchColor[], target: readonly number[], semantic: number): PaletteScores {
  const stats = paletteStats(colors);
  const labs = colors.map(colorToLab);
  const pairwise: number[] = [];
  const chromaDistances: number[][] = colors.map(() => []);
  for (let left = 0; left < labs.length; left++) {
    for (let right = left + 1; right < labs.length; right++) {
      pairwise.push(distance(labs[left], labs[right]));
      const chromaDistance = distance(labs[left].slice(1), labs[right].slice(1));
      chromaDistances[left].push(chromaDistance);
      chromaDistances[right].push(chromaDistance);
    }
  }
  const nearestChroma = chromaDistances.map((items) => Math.min(...items));
  const minDistance = Math.min(...pairwise);
  const meanDistance = pairwise.reduce((sum, value) => sum + value, 0) / pairwise.length;
  const minSeparation = clamp(minDistance / 0.075, 0, 1);
  const meanMatch = Math.exp(-Math.pow((meanDistance - target[5]) / 0.26, 2));
  const diversity = 0.68 * minSeparation + 0.32 * meanMatch;

  const medianNearest = quantile(nearestChroma, 0.5);
  const neighborRatio = Math.max(...nearestChroma) / Math.max(medianNearest, 0.035);
  const medianChroma = quantile(colors.map((color) => color.c), 0.5);
  const chromaRatio = Math.max(...colors.map((color) => color.c)) / Math.max(medianChroma, 0.04);
  const chromatic = colors.filter((color) => color.c > 0.025 && color.h !== null);
  const totalChroma = chromatic.reduce((sum, color) => sum + Math.max(color.c, 0.01), 0);
  const temperature = totalChroma > 0
    ? Math.abs(chromatic.reduce((sum, color) => sum + Math.cos(((color.h ?? 0) - 50) * Math.PI / 180) * Math.max(color.c, 0.01), 0) / totalChroma)
    : 1;
  const harmony = clamp(
    Math.exp(-1.2 * Math.max(0, neighborRatio - 1.75))
      * Math.exp(-0.65 * Math.max(0, chromaRatio - 2.5))
      * (0.88 + 0.12 * temperature),
    0,
    1,
  );

  const lightness = colors.map((color) => color.l);
  const lightnessRange = stats[2] - stats[0];
  const fullRange = Math.max(...lightness) - Math.min(...lightness);
  const targetRange = Math.max(0.1, target[2] - target[0]);
  const rangeMatch = Math.exp(-Math.pow((lightnessRange - targetRange) / 0.24, 2));
  const hierarchy = clamp(fullRange / 0.16, 0, 1);
  const structure = 0.48 * rangeMatch + 0.34 * hierarchy + 0.18 * Math.exp(-0.45 * Math.max(0, chromaRatio - 3));

  const unique = new Set(colors.map(oklchToHex)).size;
  const nearFraction = pairwise.filter((value) => value < 0.035).length / pairwise.length;
  const extremeFraction = colors.filter((color) => color.l < 0.025 || color.l > 0.985).length / colors.length;
  const penalties = 0.15 * (colors.length - unique)
    + 0.22 * nearFraction
    + 0.10 * extremeFraction
    + 0.045 * Math.max(0, neighborRatio - 2)
    + 0.035 * Math.max(0, chromaRatio - 3);

  const toneError = stats.reduce((sum, value, index) => sum + Math.pow((value - target[index]) / TONE_SCALE[index], 2), 0) / 7;
  const tone = Math.exp(-toneError);
  const total = 0.52 * semantic + 0.23 * tone + 0.10 * harmony + 0.07 * diversity + 0.08 * structure - penalties;
  return { semantic, tone, harmony, diversity, structure, penalties, minDistance, total };
}

export function generateRetrievedPalette(input: {
  embedding: Float32Array;
  count: number;
  seed: number;
  artifacts: RetrievalArtifacts;
  lockedColors?: ReadonlyMap<number, OklchColor>;
}): RetrievedPaletteResult {
  const { embedding, count, seed, artifacts } = input;
  if (!Number.isInteger(count) || count < 2 || count > 9) throw new Error('Color count must be from 2 to 9');
  if (embedding.length !== artifacts.dimension) throw new Error(`Query embedding dimension must be ${artifacts.dimension}`);
  if (artifacts.embeddings.length !== artifacts.palettes.length * artifacts.dimension) {
    throw new Error('Retrieval embedding artifact dimensions are invalid');
  }

  let queryNorm = 0;
  for (const value of embedding) queryNorm += value * value;
  queryNorm = Math.sqrt(queryNorm);
  if (!Number.isFinite(queryNorm) || queryNorm < 1e-8) throw new Error('Query embedding must be finite and non-zero');

  const similarities = artifacts.palettes.map((_, row) => {
    let dot = 0;
    let norm = 0;
    const offset = row * artifacts.dimension;
    for (let column = 0; column < artifacts.dimension; column++) {
      const value = artifacts.embeddings[offset + column];
      dot += value * embedding[column];
      norm += value * value;
    }
    return dot / (queryNorm * Math.max(Math.sqrt(norm), 1e-8));
  });
  const nearest = similarities
    .map((similarity, index) => ({ similarity, index }))
    .sort((a, b) => b.similarity - a.similarity || a.index - b.index)
    .slice(0, Math.min(24, artifacts.palettes.length));
  const target = runToneHead(embedding, artifacts.tone);
  const candidates: Candidate[] = [];
  const seen = new Set<string>();

  nearest.forEach((neighbor, position) => {
    const sources = [artifacts.palettes[neighbor.index]];
    for (let offset = 1; offset < Math.min(4, count); offset++) {
      sources.push(artifacts.palettes[nearest[(position + offset) % nearest.length].index]);
    }
    const bases: Array<{ palette: string[]; semantic: number; familyIndex: number }> = [{
      palette: selectSeparatedColors(sources, count),
      semantic: clamp((neighbor.similarity + 1) / 2, 0, 1),
      familyIndex: 0,
    }];
    if (count >= 3 && nearest.length > 1) {
      const other = nearest[position > 0 ? position - 1 : 1];
      const retain = Math.min(5, count - 1);
      const core = selectSeparatedColors([artifacts.palettes[neighbor.index], artifacts.palettes[other.index]], retain);
      bases.push({
        palette: selectSeparatedColors([core, artifacts.palettes[other.index], ...sources.slice(1)], count),
        semantic: clamp(((neighbor.similarity + other.similarity) / 2 + 1) / 2, 0, 1),
        familyIndex: 1,
      });
    }
    for (const base of bases) {
      for (const strength of [0.3, 0.6, 0.9]) {
        const colors = transformTone(base.palette, target, strength);
        for (const [index, locked] of input.lockedColors ?? []) colors[index] = { ...locked };
        const key = colors.map(oklchToHex).join(',');
        if (seen.has(key)) continue;
        seen.add(key);
        candidates.push({
          colors,
          scores: scorePalette(colors, target, base.semantic),
          sourceIndex: neighbor.index,
          familyIndex: base.familyIndex,
        });
      }
    }
  });
  if (!candidates.length) throw new Error('No palette candidates could be generated');
  candidates.sort((a, b) => b.scores.total - a.scores.total || a.sourceIndex - b.sourceIndex);
  // Variations must stay inside the winning semantic memory and composition.
  // Cycling through the global ranking can jump from e.g. "rain" to "rainbow".
  const bestSourceIndex = candidates[0].sourceIndex;
  const bestFamilyIndex = candidates[0].familyIndex;
  const variants = candidates.filter((candidate) => (
    candidate.sourceIndex === bestSourceIndex && candidate.familyIndex === bestFamilyIndex
  ));
  const variantCount = variants.length;
  const variantIndex = seed % variantCount;
  return { ...variants[variantIndex], variantIndex };
}
