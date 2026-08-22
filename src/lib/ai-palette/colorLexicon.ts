/**
 * colorLexicon.ts
 * Small canonical literal-color constraint table (RU + EN).
 * A strong deterministic constraint for explicit color words only —
 * NOT a semantic engine. Arbitrary concepts go through the semantic mapper.
 */
import { hexToOklch } from '@/lib/color/conversions';
import { maxSrgbChromaAt } from './paletteAdapter';

export interface LexiconIntent {
  l: number;
  relC: number;
  hue: number;
}

interface LexiconEntry {
  /** canonical sRGB target */
  hex: string;
  /** match aliases (normalized: lowercased, ё→е) */
  aliases: string[];
}

// Canonical sRGB targets (CSS conventions; burgundy/violet/lavender per documented common usage)
const ENTRIES: LexiconEntry[] = [
  { hex: '#000000', aliases: ['black', 'черный', 'черно'] },
  { hex: '#ffffff', aliases: ['white', 'белый', 'бело'] },
  { hex: '#808080', aliases: ['gray', 'grey', 'серый'] },
  { hex: '#c0c0c0', aliases: ['silver', 'серебряный', 'серебристый'] },
  { hex: '#ff0000', aliases: ['red', 'красный'] },
  { hex: '#ffa500', aliases: ['orange', 'оранжевый'] },
  { hex: '#ffff00', aliases: ['yellow', 'желтый'] },
  { hex: '#008000', aliases: ['green', 'зеленый'] },
  { hex: '#00ffff', aliases: ['cyan'] },
  { hex: '#40e0d0', aliases: ['turquoise', 'бирюзовый'] },
  { hex: '#0000ff', aliases: ['blue', 'синий'] },
  { hex: '#000080', aliases: ['navy', 'темно-синий'] },
  { hex: '#800080', aliases: ['purple', 'фиолетовый'] },
  { hex: '#8f00ff', aliases: ['violet'] },
  { hex: '#e6e6fa', aliases: ['lavender', 'лавандовый'] },
  { hex: '#ffc0cb', aliases: ['pink', 'розовый'] },
  { hex: '#ff00ff', aliases: ['magenta', 'пурпурный'] },
  { hex: '#a52a2a', aliases: ['brown', 'коричневый'] },
  { hex: '#f5f5dc', aliases: ['beige', 'бежевый'] },
  { hex: '#ffd700', aliases: ['gold', 'golden', 'золотой'] },
  { hex: '#800020', aliases: ['burgundy', 'бордовый'] },
];

function canonicalIntent(hex: string): LexiconIntent {
  const o = hexToOklch(hex);
  const l = o && Number.isFinite(o.l) ? Math.max(0, Math.min(1, o.l)) : 0.5;
  const hue = o && o.h !== null && Number.isFinite(o.h) ? ((o.h % 360) + 360) % 360 : 0;
  const cMax = Math.max(1e-4, maxSrgbChromaAt(l, hue));
  const relC = Math.max(0, Math.min(1, (o && Number.isFinite(o.c) ? o.c : 0) / cMax));
  return { l, hue, relC };
}

const LOOKUP = new Map<string, LexiconIntent>();
for (const e of ENTRIES) {
  const intent = canonicalIntent(e.hex);
  for (const a of e.aliases) LOOKUP.set(a, intent);
}
const MULTI_WORD = [...LOOKUP.keys()].filter(k => k.includes(' '));

function normalizeForLexicon(text: string): string {
  return text.normalize('NFKC').toLowerCase().replace(/ё/g, 'е');
}

export interface ColorConstraint {
  intent: LexiconIntent;
  /** blend weight of the canonical intent: 1 = fully deterministic */
  weight: number;
}

/**
 * Detects an explicit named color in the prompt.
 * Returns a strong constraint; the rest of the phrase still blends in
 * (lightness/chroma/harmony nuance) via the returned weight < 1.
 */
export function matchColorConstraint(normalizedText: string): ColorConstraint | null {
  const text = normalizeForLexicon(normalizedText);
  if (!text) return null;

  let intent: LexiconIntent | undefined;
  for (const mw of MULTI_WORD) {
    if (text.includes(mw)) { intent = LOOKUP.get(mw); break; }
  }
  if (!intent) {
    const words = text.replace(/[^\p{L}\p{N}]+/gu, ' ').trim().split(/\s+/).filter(Boolean);
    for (const w of words) {
      const hit = LOOKUP.get(w);
      if (hit) { intent = hit; break; }
    }
    if (!intent) return null;
    // Bare color word (or a trivial qualifier like "very"): near-deterministic.
    // Color inside a longer phrase: strong but leaves room for context nuance.
    const weight = words.length <= 2 ? 0.8 : 0.55;
    return { intent, weight };
  }
  return { intent, weight: 0.8 };
}
