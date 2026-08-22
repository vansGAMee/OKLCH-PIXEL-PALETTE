/**
 * evaluate-ai-semantic-quality.mjs
 * Independent semantic release benchmark harness. Evaluation only — no production mappings.
 * Usage: node scripts/evaluate-ai-semantic-quality.mjs [candidate]
 *   candidate: "A" (current palette-head) | "C" (semantic anchors + color lexicon) | "all"
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { oklch, clampChroma } from 'culori';

const CAND = process.argv[2] || 'all';

const bench = JSON.parse(readFileSync('ml/semantic_quality_benchmark.json', 'utf8'));
const FAMILIES = bench.hueFamilies;

// ---------- embedding cache (production encoder, exact pipeline) ----------
const embCachePath = 'ml/cache/benchmark_embeddings.json';
const embCache = existsSync(embCachePath) ? JSON.parse(readFileSync(embCachePath, 'utf8')) : {};

function collectPrompts() {
  const set = new Set();
  bench.directColors.forEach(e => set.add(e.prompt));
  bench.translations.flat().forEach(p => set.add(p));
  bench.synonyms.flat().forEach(p => set.add(p));
  bench.visualAttributes.forEach(e => set.add(e.prompt));
  bench.ood.forEach(e => set.add(e.prompt));
  bench.robustness.forEach(p => set.add(p));
  return [...set];
}

async function ensureEmbeddings() {
  const missing = collectPrompts().filter(p => !(p in embCache));
  if (missing.length) {
    const { AutoTokenizer, AutoModel, env } = await import('@huggingface/transformers');
    env.allowLocalModels = true; env.allowRemoteModels = false; env.localModelPath = './public/models/';
    const tokenizer = await AutoTokenizer.from_pretrained('multilingual-e5-small');
    const model = await AutoModel.from_pretrained('multilingual-e5-small', { dtype: 'q8' });
    for (const t of missing) {
      const norm = t.trim().toLowerCase();
      if (!norm) continue;
      const inputs = await tokenizer(`query: ${norm}`, { padding: true, truncation: true });
      const outputs = await model(inputs);
      const data = outputs.last_hidden_state.data;
      const [, seqLen, dim] = outputs.last_hidden_state.dims;
      const mask = inputs.attention_mask.data;
      const pooled = new Float64Array(dim); let w = 0;
      for (let s = 0; s < seqLen; s++) { const m = Number(mask[s]); if (m > 0) { w += m; for (let d = 0; d < dim; d++) pooled[d] += data[s * dim + d] * m; } }
      let n = 0; for (let d = 0; d < dim; d++) { pooled[d] /= w; n += pooled[d] * pooled[d]; }
      n = Math.sqrt(Math.max(1e-12, n));
      embCache[t] = Array.from(pooled, v => v / n);
    }
    mkdirSync('ml/cache', { recursive: true });
    writeFileSync(embCachePath, JSON.stringify(embCache));
    console.error(`embedded ${missing.length} new prompts -> ${embCachePath}`);
  }
}
await ensureEmbeddings();

// ---------- intent helpers ----------
const hueDist = (a, b) => { const d = Math.abs(((a - b) % 360 + 360) % 360); return d > 180 ? 360 - d : d; };
function maxChroma(l, h) { return clampChroma({ mode: 'oklch', l, c: 0.4, h }, 'rgb').c; }

function dot(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }
function softmax(xs) { const m = Math.max(...xs); const es = xs.map(x => Math.exp(x - m)); const s = es.reduce((p, c) => p + c, 0); return es.map(e => e / s); }

// ---------- Candidate A: current palette-head.onnx ----------
let headRun = null;
async function getCandidateA() {
  if (!headRun) {
    const ort = await import('onnxruntime-web');
    const buf = readFileSync('./public/models/palette-head.onnx');
    const session = await ort.InferenceSession.create(buf, { executionProviders: ['wasm'] });
    const sigmoid = x => 1 / (1 + Math.exp(-x));
    headRun = async prompt => {
      const emb = embCache[prompt];
      const res = await session.run({ embedding: new ort.Tensor('float32', Float32Array.from(emb), [1, 384]) });
      const o = res.logits.data;
      const l = 0.07 + sigmoid(o[0]) * 0.86;
      const n = Math.hypot(o[1], o[2]);
      const hue = (Math.atan2(o[1] / (n || 1), o[2] / (n || 1)) * 180 / Math.PI + 360) % 360;
      const relC = sigmoid(o[3]);
      const harms = ['splitComplementary', 'complementary', 'analogous'];
      const harmony = harms[[o[4], o[5], o[6]].indexOf(Math.max(o[4], o[5], o[6]))];
      return { l, hue, relC, harmony };
    };
  }
  return headRun;
}

// ---------- Candidate C: semantic anchors + explicit color lexicon ----------
const anchorsPkg = JSON.parse(readFileSync('public/models/semantic-anchors.json', 'utf8'));
const ANCHORS = anchorsPkg.anchors;
const TEMP = Number(process.env.TEMP || 0.045), TOPK = Number(process.env.TOPK || 8);

// canonical literal color lexicon (production spec §14): word -> canonical sRGB hex
const LEXICON = {
  'black': '#000000', 'чёрный': '#000000', 'черный': '#000000', 'черно': '#000000',
  'white': '#ffffff', 'белый': '#ffffff', 'бело': '#ffffff',
  'gray': '#808080', 'grey': '#808080', 'серый': '#808080',
  'silver': '#c0c0c0', 'серебряный': '#c0c0c0', 'серебристый': '#c0c0c0',
  'red': '#ff0000', 'красный': '#ff0000',
  'orange': '#ffa500', 'оранжевый': '#ffa500',
  'yellow': '#ffff00', 'жёлтый': '#ffff00', 'желтый': '#ffff00',
  'green': '#008000', 'зелёный': '#008000', 'зеленый': '#008000',
  'cyan': '#00ffff', 'бирюзовый': '#40e0d0', 'turquoise': '#40e0d0',
  'blue': '#0000ff', 'синий': '#0000ff',
  'navy': '#000080', 'тёмно-синий': '#000080', 'темно-синий': '#000080',
  'purple': '#800080', 'violet': '#8f00ff', 'фиолетовый': '#800080',
  'lavender': '#e6e6fa', 'лавандовый': '#e6e6fa',
  'pink': '#ffc0cb', 'розовый': '#ffc0cb',
  'magenta': '#ff00ff', 'пурпурный': '#ff00ff',
  'brown': '#a52a2a', 'коричневый': '#a52a2a',
  'beige': '#f5f5dc', 'бежевый': '#f5f5dc',
  'gold': '#ffd700', 'golden': '#ffd700', 'золотой': '#ffd700',
  'burgundy': '#800020', 'бордовый': '#800020',
};
const lexiconIntents = new Map();
for (const [w, hex] of Object.entries(LEXICON)) {
  const o = oklch(hex);
  const h = Number.isFinite(o.h) ? o.h : 0;
  lexiconIntents.set(w, { l: o.l, hue: h, relC: Math.min(1, o.c / Math.max(0.01, maxChroma(o.l, h))), harmony: 'analogous' });
}
function canonIntent(hex) {
  const o = oklch(hex);
  const h = Number.isFinite(o.h) ? o.h : 0;
  return { l: o.l, hue: h, relC: Math.min(1, o.c / Math.max(0.01, maxChroma(o.l, h))) };
}

function anchorBlend(emb) {
  const sims = ANCHORS.map(a => dot(emb, a.emb));
  const idx = sims.map((s, i) => [s, i]).sort((x, y) => y[0] - x[0]).slice(0, TOPK);
  const w = softmax(idx.map(([s]) => s / TEMP));
  let l = 0, relC = 0, x = 0, y = 0;
  const harm = { analogous: 0, complementary: 0, splitComplementary: 0 };
  idx.forEach(([, i], j) => {
    const it = ANCHORS[i].intent;
    l += w[j] * it.l; relC += w[j] * it.relC;
    x += w[j] * Math.cos(it.hue * Math.PI / 180); y += w[j] * Math.sin(it.hue * Math.PI / 180);
    harm[it.harmony] += w[j];
  });
  return { l, relC, hue: (Math.atan2(y, x) * 180 / Math.PI + 360) % 360, harmony: Object.entries(harm).sort((a, b) => b[1] - a[1])[0][0] };
}

function blendIntents(a, b, wa) {
  const wb = 1 - wa;
  const x = wa * Math.cos(a.hue * Math.PI / 180) + wb * Math.cos(b.hue * Math.PI / 180);
  const y = wa * Math.sin(a.hue * Math.PI / 180) + wb * Math.sin(b.hue * Math.PI / 180);
  return {
    l: wa * a.l + wb * b.l,
    relC: wa * a.relC + wb * b.relC,
    hue: (Math.atan2(y, x) * 180 / Math.PI + 360) % 360,
    harmony: wa >= 0.5 ? a.harmony : b.harmony,
  };
}

function normalizeWords(p) {
  return p.toLowerCase().replace(/ё/g, 'е').replace(/[^\p{L}\p{N}]+/gu, ' ').trim().split(/\s+/).filter(Boolean);
}

function candidateC(prompt) {
  const norm = prompt.trim().toLowerCase();
  if (!norm) throw new Error('Empty prompt');
  const words = normalizeWords(prompt);
  // explicit color lexicon: multi-word names first
  let lexHit = null;
  for (const [w, intent] of lexiconIntents) {
    if (w.includes(' ')) {
      if (norm.includes(w.replace('ё', 'е'))) { lexHit = intent; break; }
    }
  }
  if (!lexHit) {
    for (const w of words) if (lexiconIntents.has(w)) { lexHit = lexiconIntents.get(w); break; }
  }
  const emb = embCache[prompt];
  const base = anchorBlend(emb);
  if (!lexHit) return base;
  const isBareColor = words.length <= 2; // "black", "тёмно-синий", "very black"
  const wa = isBareColor ? 0.8 : 0.55;
  return blendIntents(lexHit, base, wa);
}

// ---------- checks ----------
const failures = [];
function inFamily(hue, fams) { return fams.some(f => { const [lo, hi] = FAMILIES[f]; return hue >= lo && hue <= hi; }); }

function checkEntry(entry, intent) {
  if (![intent.l, intent.relC, intent.hue].every(Number.isFinite)) return 'non-finite';
  const e = entry.expect || {};
  if (e.hueFamilies && intent.relC >= 0.2 && !inFamily(intent.hue, e.hueFamilies)) return `hue ${intent.hue.toFixed(0)} not in [${e.hueFamilies}]`;
  if (e.minL !== undefined && intent.l < e.minL) return `L ${intent.l.toFixed(2)} < ${e.minL}`;
  if (e.maxL !== undefined && intent.l > e.maxL) return `L ${intent.l.toFixed(2)} > ${e.maxL}`;
  if (e.minRelC !== undefined && intent.relC < e.minRelC) return `relC ${intent.relC.toFixed(2)} < ${e.minRelC}`;
  if (e.maxRelC !== undefined && intent.relC > e.maxRelC) return `relC ${intent.relC.toFixed(2)} > ${e.maxRelC}`;
  return null;
}

const emptyGuard = fn => async p => {
  if (!p.trim()) throw new Error('Empty prompt');
  return fn(p);
};

async function evaluate(name, intentOf_) {
  const intentOf = emptyGuard(intentOf_);
  const res = { name, direct: [0, 0], trans: [0, 0], syn: [0, 0], visual: [0, 0], ood: [0, 0], robust: [0, 0], failures: [] };
  const log = (cat, ok, prompt, reason) => {
    res[cat][0]++; if (ok) res[cat][1]++;
    else { res.failures.push(`${cat} FAIL [${prompt}]: ${reason}`); failures.push(`${name} ${cat} [${prompt}]: ${reason}`); }
  };

  for (const e of bench.directColors) {
    let intent; try { intent = await intentOf(e.prompt); } catch (err) { log('direct', false, e.prompt, 'threw ' + err.message); continue; }
    const canon = oklch(e.hex);
    if (e.kind === 'neutral') {
      const r = checkEntry({ expect: { minL: e.minL, maxL: e.maxL, maxRelC: e.maxRelC } }, intent);
      log('direct', !r, e.prompt, r);
    } else {
      const ci = canonIntent(e.hex);
      const hd = hueDist(intent.hue, ci.hue);
      const ok = hd <= 35 && Math.abs(intent.l - ci.l) <= 0.2 && intent.relC >= Math.max(0.2, ci.relC * 0.55);
      log('direct', ok, e.prompt, `hueDist=${hd.toFixed(0)} dL=${Math.abs(intent.l - ci.l).toFixed(2)} relC=${intent.relC.toFixed(2)} (canon ${e.hex} h=${ci.hue.toFixed(0)} L=${ci.l.toFixed(2)} relC=${ci.relC.toFixed(2)})`);
    }
  }

  const pairClose = (a, b) => hueDist(a.hue, b.hue) <= 45 && Math.abs(a.l - b.l) <= 0.2 && Math.abs(a.relC - b.relC) <= 0.35;
  const bothNeutral = (a, b) => a.relC < 0.2 && b.relC < 0.2;
  for (const [pa, pb] of bench.translations) {
    const ia = await intentOf(pa), ib = await intentOf(pb);
    const ok = pairClose(ia, ib) || bothNeutral(ia, ib);
    log('trans', ok, `${pa} / ${pb}`, `hue ${ia.hue.toFixed(0)} vs ${ib.hue.toFixed(0)}, L ${ia.l.toFixed(2)} vs ${ib.l.toFixed(2)}`);
  }
  for (const group of bench.synonyms) {
    const ints = [];
    for (const p of group) { try { ints.push(await intentOf(p)); } catch { ints.push(null); } }
    let ok = true, worst = '';
    for (let i = 0; i < ints.length && ok; i++) for (let j = i + 1; j < ints.length; j++) {
      if (!ints[i] || !ints[j]) { ok = false; worst = 'threw'; break; }
      if (!(pairClose(ints[i], ints[j]) || bothNeutral(ints[i], ints[j]))) { ok = false; worst = `${group[i]}(${ints[i].hue.toFixed(0)}°) vs ${group[j]}(${ints[j].hue.toFixed(0)}°)`; break; }
    }
    log('syn', ok, group.join('/'), worst);
  }
  for (const e of bench.visualAttributes) {
    let intent; try { intent = await intentOf(e.prompt); } catch (err) { log('visual', false, e.prompt, 'threw ' + err.message); continue; }
    const r = checkEntry(e, intent);
    log('visual', !r, e.prompt, r);
  }
  for (const e of bench.ood) {
    let intent; try { intent = await intentOf(e.prompt); } catch (err) { log('ood', false, e.prompt, 'threw ' + err.message); continue; }
    const r = checkEntry(e, intent);
    log('ood', !r, e.prompt, r);
  }
  for (const p of bench.robustness) {
    try { const it = await intentOf(p); log('robust', [it.l, it.relC, it.hue].every(Number.isFinite), JSON.stringify(p), 'non-finite'); }
    catch (err) { log('robust', /empty/i.test(err.message), JSON.stringify(p), 'threw ' + err.message); }
  }

  // collapse diagnostics over all semantic prompts
  const all = [...bench.visualAttributes.map(e => e.prompt), ...bench.ood.map(e => e.prompt)];
  const ints = all.map(p => ({ p, ...candidateC(p) })).filter(i => i.relC >= 0.25);
  const famCount = {};
  for (const i of ints) { const f = Object.entries(FAMILIES).find(([, [lo, hi]]) => i.hue >= lo && i.hue <= hi); if (f) famCount[f[0]] = (famCount[f[0]] || 0) + 1; }
  const total = ints.length;
  const topFam = Object.entries(famCount).sort((a, b) => b[1] - a[1])[0];
  let dupPairs = 0;
  for (let i = 0; i < ints.length; i++) for (let j = i + 1; j < ints.length; j++)
    if (hueDist(ints[i].hue, ints[j].hue) < 6 && Math.abs(ints[i].l - ints[j].l) < 0.03 && Math.abs(ints[i].relC - ints[j].relC) < 0.03) dupPairs++;
  const pairTotal = ints.length * (ints.length - 1) / 2;
  res.collapse = { chromaticN: total, topFamily: topFam, topFamilyShare: +(topFam[1] / total).toFixed(2), nearDuplicateShare: +(dupPairs / pairTotal).toFixed(3) };
  return res;
}

function report(r) {
  const pct = (a) => a[1] + '/' + a[0] + (a[0] ? ' (' + (100 * a[1] / a[0]).toFixed(0) + '%)' : '');
  console.log(`\n===== ${r.name} =====`);
  console.log('direct colors :', pct(r.direct));
  console.log('translations  :', pct(r.trans));
  console.log('synonyms      :', pct(r.syn));
  console.log('visual attrs  :', pct(r.visual));
  console.log('ood           :', pct(r.ood));
  console.log('robustness    :', pct(r.robust));
  console.log('collapse      :', JSON.stringify(r.collapse));
  r.failures.forEach(f => console.log('  ' + f));
}

const results = [];
if (CAND === 'A' || CAND === 'all') results.push(await evaluate('A: current palette-head', await getCandidateA()));
if (CAND === 'C' || CAND === 'all') results.push(await evaluate('C: semantic anchors + lexicon', p => candidateC(p)));
results.forEach(report);
