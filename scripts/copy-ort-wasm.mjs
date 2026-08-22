/**
 * Copy required ORT WASM files to public/ort/
 * Run before dev/build.
 */
import { existsSync, mkdirSync, readdirSync, copyFileSync } from 'fs';
import { join, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const rootDir = resolve(__dirname, '..');
const destDir = join(rootDir, 'public', 'ort');

// Find ort package wasm files
const candidateDirs = [
  join(rootDir, 'node_modules', 'onnxruntime-web', 'dist'),
  join(rootDir, 'node_modules', 'onnxruntime-web', 'dist', 'esm'),
  join(rootDir, 'node_modules', 'onnxruntime-web'),
];

function findWasmFiles(dir) {
  if (!existsSync(dir)) return [];
  try {
    return readdirSync(dir).filter(f => f.endsWith('.wasm') || f.endsWith('.mjs') || f.endsWith('.js'));
  } catch {
    return [];
  }
}

mkdirSync(destDir, { recursive: true });

let copied = 0;
for (const candidate of candidateDirs) {
  const files = findWasmFiles(candidate);
  // Copy WASM files and the main WASM-backend JS
  const relevant = files.filter(f =>
    f.includes('wasm') ||
    f.includes('ort-wasm') ||
    f === 'ort.all.min.js' ||
    f.endsWith('.wasm')
  );
  for (const file of relevant) {
    const src = join(candidate, file);
    const dst = join(destDir, file);
    try {
      copyFileSync(src, dst);
      copied++;
    } catch {
      // skip
    }
  }
}

if (copied === 0) {
  console.warn('WARNING: No ORT WASM files found. Run npm install first.');
} else {
  console.log(`Copied ${copied} ORT asset(s) to public/ort/`);
}
