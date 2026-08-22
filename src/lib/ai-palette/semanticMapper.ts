/**
 * semanticMapper.ts
 * Semantic anchor projection: prompt embedding → cosine similarity against
 * precomputed anchor embeddings → top-k confidence-weighted intent blending.
 * Hue blends via circular vectors (never linear degree averaging).
 */
import type { HarmonyMode } from '@/types/palette';
import type { LexiconIntent } from './colorLexicon';

export interface SemanticIntent {
  l: number;
  relC: number;
  hue: number;
  harmony: HarmonyMode;
}

export interface SemanticAnchor {
  id: string;
  category: string;
  intent: { hue: number; l: number; relC: number; harmony: HarmonyMode };
  en: string;
  ru: string;
  emb: number[];
}

export interface AnchorsPackage {
  meta: Record<string, unknown>;
  anchors: SemanticAnchor[];
}

export const TEMPERATURE = 0.02;
export const TOP_K = 4;

let anchorsPromise: Promise<SemanticAnchor[]> | null = null;
let customAnchors: SemanticAnchor[] | null = null;

export function setTestAnchors(anchors: SemanticAnchor[] | null) {
  customAnchors = anchors;
  anchorsPromise = null;
}

export async function getSemanticAnchors(): Promise<SemanticAnchor[]> {
  if (customAnchors) return customAnchors;
  if (anchorsPromise) return anchorsPromise;

  anchorsPromise = (async () => {
    if (typeof window !== 'undefined') {
      const res = await fetch('/models/semantic-anchors.json');
      if (!res.ok) {
        throw new Error(`Failed to load semantic anchors: ${res.statusText}`);
      }
      const pkg: AnchorsPackage = await res.json();
      return pkg.anchors;
    } else {
      const fs = await import('node:fs/promises');
      const path = await import('node:path');
      const raw = await fs.readFile(
        path.join(process.cwd(), 'public/models/semantic-anchors.json'),
        'utf8'
      );
      const pkg: AnchorsPackage = JSON.parse(raw);
      return pkg.anchors;
    }
  })();

  return anchorsPromise;
}

function dot(a: ArrayLike<number>, b: ArrayLike<number>): number {
  let s = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) s += a[i] * b[i];
  return s;
}

function softmax(xs: number[]): number[] {
  const m = Math.max(...xs);
  const es = xs.map(x => Math.exp(x - m));
  const sum = es.reduce((p, c) => p + c, 0);
  return es.map(e => e / sum);
}

/** Top-k softmax-weighted blend of anchor intents. Circular hue, linear L / relC. */
export function blendAnchorIntent(embedding: ArrayLike<number>, anchors: SemanticAnchor[]): SemanticIntent {
  if (anchors.length === 0) throw new Error('No semantic anchors loaded');

  const scored = anchors.map((a, i) => ({ sim: dot(embedding, a.emb), i }));
  scored.sort((x, y) => y.sim - x.sim);
  const top = scored.slice(0, Math.min(TOP_K, scored.length));

  const weights = softmax(top.map(t => t.sim / TEMPERATURE));

  let l = 0;
  let relC = 0;
  let x = 0;
  let y = 0;
  const harmonyVotes: Partial<Record<HarmonyMode, number>> = {
    analogous: 0,
    complementary: 0,
    splitComplementary: 0,
  };
  for (let j = 0; j < top.length; j++) {
    const it = anchors[top[j].i].intent;
    const w = weights[j];
    l += w * it.l;
    relC += w * it.relC;
    const rad = (it.hue * Math.PI) / 180;
    x += w * Math.cos(rad);
    y += w * Math.sin(rad);
    harmonyVotes[it.harmony] = (harmonyVotes[it.harmony] ?? 0) + w;
  }

  let hue: number;
  if (x * x + y * y < 1e-12) {
    hue = 0;
  } else {
    hue = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  }
  const harmony = ((Object.keys(harmonyVotes) as HarmonyMode[]).sort(
    (a, b) => (harmonyVotes[b] ?? 0) - (harmonyVotes[a] ?? 0)
  )[0] || 'analogous') as HarmonyMode;

  return {
    l: Math.max(0, Math.min(1, l)),
    relC: Math.max(0, Math.min(1, relC)),
    hue,
    harmony,
  };
}

/** Blends a canonical lexicon intent with the semantic blend (circular hue). */
export function applyColorConstraint(lex: LexiconIntent, base: SemanticIntent, weight: number): SemanticIntent {
  const w = Math.max(0, Math.min(1, weight));
  const wb = 1 - w;
  const xr = w * Math.cos((lex.hue * Math.PI) / 180) + wb * Math.cos((base.hue * Math.PI) / 180);
  const yr = w * Math.sin((lex.hue * Math.PI) / 180) + wb * Math.sin((base.hue * Math.PI) / 180);
  return {
    l: w * lex.l + wb * base.l,
    relC: w * lex.relC + wb * base.relC,
    hue: ((Math.atan2(yr, xr) * 180) / Math.PI + 360) % 360,
    harmony: base.harmony,
  };
}

/** Final sanity gate: rejects/repairs non-finite or out-of-range values. */
export function sanitizeSemanticIntent(intent: SemanticIntent): SemanticIntent {
  const finite = (v: number, fallback: number) => (Number.isFinite(v) ? v : fallback);
  return {
    l: Math.max(0.01, Math.min(0.99, finite(intent.l, 0.5))),
    relC: Math.max(0, Math.min(1, finite(intent.relC, 0.4))),
    hue: (((finite(intent.hue, 0) % 360) + 360) % 360),
    harmony: ['analogous', 'complementary', 'splitComplementary'].includes(intent.harmony)
      ? intent.harmony
      : 'analogous',
  };
}
