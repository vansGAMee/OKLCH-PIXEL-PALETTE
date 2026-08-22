/**
 * inference.ts
 * Multilingual semantic palette generation using local multilingual-e5-small encoder
 * + precomputed semantic anchors + literal color lexicon.
 * Runs completely locally in browser/Node via ONNX WASM & @huggingface/transformers.
 */
'use client';

import type { AiPaletteIntent } from './paletteAdapter';
import { semanticIntentToBase } from './paletteAdapter';
import { normalizeText, stablePromptHash } from './tokenizer';
import {
  blendAnchorIntent,
  applyColorConstraint,
  sanitizeSemanticIntent,
  getSemanticAnchors,
  setTestAnchors,
} from './semanticMapper';
import { matchColorConstraint } from './colorLexicon';

let encoderPromise: Promise<{
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tokenizer: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  model: any;
}> | null = null;

const ENCODER_MODEL_ID = 'multilingual-e5-small';

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function setTestArtifacts(_vocab?: Record<string, number>, _model?: ArrayBuffer | Uint8Array | string) {
  encoderPromise = null;
  setTestAnchors(null);
}

async function getEncoder() {
  if (encoderPromise) return encoderPromise;

  encoderPromise = (async () => {
    const { AutoTokenizer, AutoModel, env } = await import('@huggingface/transformers');
    env.allowLocalModels = true;
    env.allowRemoteModels = false;
    env.localModelPath = typeof window !== 'undefined' ? '/models/' : './public/models/';

    if (typeof window !== 'undefined') {
      if (env.backends?.onnx?.wasm) {
        env.backends.onnx.wasm.wasmPaths = '/ort/';
        env.backends.onnx.wasm.numThreads = 1;
        env.backends.onnx.wasm.proxy = false;
      }
    }

    const tokenizer = await AutoTokenizer.from_pretrained(ENCODER_MODEL_ID);
    const model = await AutoModel.from_pretrained(ENCODER_MODEL_ID, {
      dtype: 'q8',
    });

    return { tokenizer, model };
  })();

  return encoderPromise;
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
    const [{ tokenizer, model }, anchors] = await Promise.all([
      getEncoder(),
      getSemanticAnchors(),
    ]);

    // Tokenize text prompt with query: prefix
    const inputs = await tokenizer(`query: ${normalized}`, { padding: true, truncation: true });
    const outputs = await model(inputs);

    // Mean pooling over tokens using attention mask
    const lastHiddenState = outputs.last_hidden_state;
    const data = lastHiddenState.data as Float32Array;
    const [, seqLen, hiddenDim] = lastHiddenState.dims;
    const mask = inputs.attention_mask.data as BigInt64Array | Int32Array | number[];

    const meanPooled = new Float32Array(hiddenDim);
    let totalWeight = 0;

    for (let s = 0; s < seqLen; s++) {
      const m = Number(mask[s]);
      if (m > 0) {
        totalWeight += m;
        const offset = s * hiddenDim;
        for (let d = 0; d < hiddenDim; d++) {
          meanPooled[d] += data[offset + d] * m;
        }
      }
    }

    if (totalWeight > 0) {
      for (let d = 0; d < hiddenDim; d++) {
        meanPooled[d] /= totalWeight;
      }
    }

    // L2 normalization
    let normSq = 0;
    for (let d = 0; d < hiddenDim; d++) {
      normSq += meanPooled[d] * meanPooled[d];
    }
    const norm = Math.sqrt(Math.max(1e-12, normSq));
    for (let d = 0; d < hiddenDim; d++) {
      meanPooled[d] /= norm;
    }

    // 1. Semantic anchor projection (top-k softmax blend)
    let intent = blendAnchorIntent(meanPooled, anchors);

    // 2. Named color constraint (if prompt contains a genuine color word)
    const colorConstraint = matchColorConstraint(normalized);
    if (colorConstraint) {
      intent = applyColorConstraint(colorConstraint.intent, intent, colorConstraint.weight);
    }

    // 3. Sanitize intent (bounds, NaN/Inf protection)
    const sanitized = sanitizeSemanticIntent(intent);

    // 4. Gamut-safe baseHex conversion via OKLCH engine
    const baseHex = semanticIntentToBase(sanitized);

    // 5. Stable prompt seed
    const seed = stablePromptHash(normalized);

    return {
      baseHex,
      harmony: sanitized.harmony,
      seed,
    };
  } finally {
    inferenceInProgress = false;
  }
}
