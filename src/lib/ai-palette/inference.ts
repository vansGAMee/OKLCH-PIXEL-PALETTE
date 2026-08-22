/**
 * inference.ts
 * Lazy-loads ONNX model + WASM runtime.
 * One session, one inference at a time.
 * No React logic; no ontology rules; pure neural inference.
 */
'use client';

import type { AiPaletteIntent } from './paletteAdapter';
import { PalettaTokenizer, normalizeText, stablePromptHash } from './tokenizer';
import { decodeCnnOutput } from './paletteAdapter';

// ONNX runtime is loaded lazily
let sessionPromise: Promise<import('onnxruntime-web').InferenceSession> | null = null;
let tokenizerInstance: PalettaTokenizer | null = null;

const MODEL_PATH = '/models/paletta-v1.onnx';
const VOCAB_PATH = '/models/paletta-v1.vocab.json';

let customVocabData: Record<string, number> | null = null;
let customModelData: ArrayBuffer | Uint8Array | string | null = null;

export function setTestArtifacts(vocab: Record<string, number>, model: ArrayBuffer | Uint8Array | string) {
  customVocabData = vocab;
  customModelData = model;
  sessionPromise = null;
  tokenizerInstance = null;
}

async function getTokenizer(): Promise<PalettaTokenizer> {
  if (tokenizerInstance) return tokenizerInstance;
  let vocab: Record<string, number>;
  if (customVocabData) {
    vocab = customVocabData;
  } else {
    const res = await fetch(VOCAB_PATH);
    if (!res.ok) throw new Error(`Failed to load vocab: ${res.status}`);
    vocab = await res.json();
  }
  tokenizerInstance = new PalettaTokenizer(vocab, 96);
  return tokenizerInstance;
}

async function getSession(): Promise<import('onnxruntime-web').InferenceSession> {
  if (sessionPromise) return sessionPromise;

  sessionPromise = (async () => {
    // Dynamic import to keep ORT off the critical path
    const ort = await import('onnxruntime-web');

    // WASM config: single thread, browser vs Node paths
    ort.env.wasm.numThreads = 1;
    ort.env.wasm.proxy = false;
    if (typeof window !== 'undefined') {
      ort.env.wasm.wasmPaths = '/ort/';
    } else {
      // In Node/Vitest test environment, point to local directory
      try {
        const path = await import('path');
        ort.env.wasm.wasmPaths = path.join(process.cwd(), 'public/ort/') + path.sep;
      } catch {
        // fallback
      }
    }

    const modelSource = customModelData || MODEL_PATH;
    // Cast to any to satisfy overloaded create signature across browser (path string) & node (buffer)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const session = await (ort.InferenceSession.create as any)(modelSource, {
      executionProviders: ['wasm'],
    });
    return session;
  })();

  return sessionPromise;
}

let inferenceInProgress = false;

export async function inferPaletteIntent(prompt: string): Promise<AiPaletteIntent & { seed: number }> {
  if (inferenceInProgress) {
    throw new Error('Inference already in progress');
  }

  const normalized = normalizeText(prompt);
  if (!normalized) {
    throw new Error('Empty prompt');
  }

  inferenceInProgress = true;
  try {
    const [tokenizer, session] = await Promise.all([getTokenizer(), getSession()]);
    const ort = await import('onnxruntime-web');

    const ids = tokenizer.tokenize(normalized);

    // Build int64 tensor [1, 96]
    const inputData = new BigInt64Array(ids.map(id => BigInt(id)));
    const inputTensor = new ort.Tensor('int64', inputData, [1, 96]);

    const feeds: Record<string, import('onnxruntime-web').Tensor> = { token_ids: inputTensor };
    const results = await session.run(feeds);

    const output = results['output'];
    if (!output) throw new Error('No output from model');

    const rawData = output.data as Float32Array;
    const intent = decodeCnnOutput(rawData);
    const seed = stablePromptHash(normalized);

    return { ...intent, seed };
  } finally {
    inferenceInProgress = false;
  }
}
