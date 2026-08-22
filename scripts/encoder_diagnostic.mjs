/**
 * encoder_diagnostic.mjs
 * Measures semantic similarity of the EXACT production encoder pipeline
 * (local q8 multilingual-e5-small + 'query:' prefix + masked mean pooling + L2 norm).
 */
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
  return pooled;
}

function cos(a, b) {
  let s = 0;
  for (let d = 0; d < a.length; d++) s += a[d] * b[d];
  return s;
}

const related = [
  ['purple', 'фиолетовый'], ['purple', 'violet'], ['purple', 'amethyst'],
  ['winter', 'зима'], ['winter', 'snow'],
  ['hospital', 'больница'], ['hospital', 'clinic'],
  ['cemetery', 'кладбище'], ['ocean', 'море'], ['luxury', 'роскошный'],
  ['black', 'черный'], ['abandoned hospital', 'заброшенная больница'],
];
const unrelated = [
  ['black', 'white'], ['winter', 'tropical summer'], ['purple', 'lime'],
  ['hospital', 'beach'], ['cemetery', 'luxury'], ['fire', 'snow'],
];

const cache = new Map();
async function E(t) { if (!cache.has(t)) cache.set(t, await embed(t)); return cache.get(t); }

console.log('=== RELATED (expect high cosine) ===');
for (const [a, b] of related) console.log(cos(await E(a), await E(b)).toFixed(4), a, '↔', b);
console.log('=== UNRELATED (expect low cosine) ===');
for (const [a, b] of unrelated) console.log(cos(await E(a), await E(b)).toFixed(4), a, '↔', b);
