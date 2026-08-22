/**
 * embed_semantic_anchors.mjs
 * Computes anchor embeddings using the EXACT production encoder pipeline
 * (local q8 multilingual-e5-small + 'query:' prefix + masked mean pooling + L2 norm).
 * Each anchor: mean of EN and RU description embeddings.
 * Writes compact runtime asset: public/models/semantic-anchors.json
 * Model: multilingual-e5-small q8 (local), dim 384. Regenerate with: node scripts/embed_semantic_anchors.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { AutoTokenizer, AutoModel, env } from '@huggingface/transformers';

env.allowLocalModels = true;
env.allowRemoteModels = false;
env.localModelPath = './public/models/';

const tokenizer = await AutoTokenizer.from_pretrained('multilingual-e5-small');
const model = await AutoModel.from_pretrained('multilingual-e5-small', { dtype: 'q8' });

async function embed(text) {
  const inputs = await tokenizer(`query: ${text}`, { padding: true, truncation: true });
  const outputs = await model(inputs);
  const data = outputs.last_hidden_state.data;
  const [, seqLen, dim] = outputs.last_hidden_state.dims;
  const mask = inputs.attention_mask.data;
  const pooled = new Float64Array(dim);
  let w = 0;
  for (let s = 0; s < seqLen; s++) {
    const m = Number(mask[s]);
    if (m > 0) { w += m; for (let d = 0; d < dim; d++) pooled[d] += data[s * dim + d] * m; }
  }
  let norm = 0;
  for (let d = 0; d < dim; d++) { pooled[d] /= w; norm += pooled[d] * pooled[d]; }
  norm = Math.sqrt(Math.max(1e-12, norm));
  for (let d = 0; d < dim; d++) pooled[d] /= norm;
  return Array.from(pooled);
}

const anchors = JSON.parse(readFileSync('ml/semantic_anchor_definitions.json', 'utf8'));
const out = [];
const q = arr => arr.map(v => Math.round(v * 1e4) / 1e4); // 4-decimal quantization, ~0.1% error
for (const a of anchors) {
  // Split EN/RU entries: same-language similarity is far more discriminative than a blended vector
  out.push({ id: a.id, category: a.category, intent: a.intent, en: a.en, ru: a.ru, emb: q(await embed(a.en)) });
  out.push({ id: a.id + '_ru', category: a.category, intent: a.intent, en: a.en, ru: a.ru, emb: q(await embed(a.ru)) });
}

mkdirSync('public/models', { recursive: true });
const meta = {
  model: 'multilingual-e5-small (q8, local)',
  dim: 384,
  pooling: 'masked mean + L2 norm, query: prefix',
  anchorCount: out.length,
  quantization: '4 decimal places',
  source: 'ml/semantic_anchor_definitions.json',
  regenerate: 'node scripts/embed_semantic_anchors.mjs',
};
writeFileSync('public/models/semantic-anchors.json', JSON.stringify({ meta, anchors: out }));
const bytes = Buffer.byteLength(readFileSync('public/models/semantic-anchors.json'));
console.log(`wrote public/models/semantic-anchors.json: ${out.length} anchors, ${(bytes / 1024).toFixed(0)} KB`);
