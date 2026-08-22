import { readFileSync } from 'node:fs';
const pkg = JSON.parse(readFileSync('public/models/semantic-anchors.json', 'utf8'));
const embCache = JSON.parse(readFileSync('ml/cache/benchmark_embeddings.json', 'utf8'));
const prompts = process.argv.slice(2);
function dot(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }
for (const p of prompts) {
  const e = embCache[p];
  if (!e) { console.log(p, 'NO EMB'); continue; }
  const top = pkg.anchors.map(a => [dot(e, a.emb), a]).sort((x, y) => y[0] - x[0]).slice(0, 8);
  console.log('\n' + p);
  for (const [s, a] of top) console.log(' ', s.toFixed(3), a.id, `h=${a.intent.hue} l=${a.intent.l} rc=${a.intent.relC}`);
}
