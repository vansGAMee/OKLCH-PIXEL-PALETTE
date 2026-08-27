/**
 * Local browser inference for the legacy semantic baseline and PaletteBrain v2.
 * Neural runtimes and weights are loaded only when an AI function is called.
 */
'use client';

import type { OklchColor } from '@/types/palette';
import { isInSrgbGamut } from '@/lib/color/gamut';
import type { AiPaletteIntent, PaletteDecoderTensor } from './paletteAdapter';
import { decodePaletteOutput, semanticIntentToBase } from './paletteAdapter';
import { normalizeText, stablePromptHash } from './tokenizer';
import {
  blendAnchorIntent,
  applyColorConstraint,
  sanitizeSemanticIntent,
  getSemanticAnchors,
  setTestAnchors,
} from './semanticMapper';
import { matchColorConstraint } from './colorLexicon';

export interface EncoderSession {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tokenizer: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  model: any;
}

export interface GenerateAiPaletteRequest {
  prompt: string;
  count: number;
  seed: number;
  lockedColors?: Array<{
    index: number;
    oklch: {
      l: number;
      c: number;
      h: number | null;
    };
  }>;
}

export interface GenerateAiPaletteResult {
  colors: Array<{
    l: number;
    c: number;
    h: number | null;
  }>;
  seed: number;
  modelVersion: string;
  decoderSha256?: string;
  inference?: {
    encoderMs?: number;
    decoderMs?: number;
    criticMs?: number;
    totalMs?: number;
  };
  fallback?: boolean;
}

export interface PaletteDecoderInputTensor {
  data: Float32Array;
  dims: readonly number[];
}

export type PaletteDecoderFeeds = Record<string, PaletteDecoderInputTensor>;

export interface PaletteDecoderSession {
  modelVersion: string;
  decoderSha256?: string;
  run(feeds: PaletteDecoderFeeds): Promise<PaletteDecoderTensor>;
}

const ENCODER_MODEL_ID = 'multilingual-e5-small';
const ENCODER_EMBEDDING_SIZE = 384;
const MAX_PALETTE_SIZE = 9;
const PROMPT_EMBEDDING_CACHE_LIMIT = 16;
const DECODER_MANIFEST_PATH = '/models/palettebrain-v2.manifest.json';
const E5_UPSTREAM_MODEL_ID = 'intfloat/multilingual-e5-small';

let encoderPromise: Promise<EncoderSession> | null = null;
let customEncoderLoader: (() => Promise<EncoderSession>) | null = null;
let encoderRunQueue: Promise<void> = Promise.resolve();

let decoderPromise: Promise<PaletteDecoderSession> | null = null;
let customDecoderLoader: (() => Promise<PaletteDecoderSession>) | null = null;
let decoderRunQueue: Promise<void> = Promise.resolve();

const promptEmbeddingCache = new Map<string, Promise<Float32Array>>();

function errorDetail(err: unknown): string {
  return err instanceof Error ? `${err.name}: ${err.message}` : String(err);
}

function errorWithCause(message: string, cause: unknown): Error {
  const error = new Error(message);
  (error as { cause?: unknown }).cause = cause;
  return error;
}

function nowMs(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now();
}

export function clearPromptEmbeddingCache(): void {
  promptEmbeddingCache.clear();
}

export function setTestEncoderLoader(loader: (() => Promise<EncoderSession>) | null): void {
  customEncoderLoader = loader;
  resetEncoderSession();
}

export function resetEncoderSession(): void {
  encoderPromise = null;
  clearPromptEmbeddingCache();
}

export function setTestDecoderLoader(loader: (() => Promise<PaletteDecoderSession>) | null): void {
  customDecoderLoader = loader;
  resetDecoderSession();
}

export function resetDecoderSession(): void {
  decoderPromise = null;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function setTestArtifacts(_vocab?: Record<string, number>, _model?: ArrayBuffer | Uint8Array | string): void {
  encoderPromise = null;
  customEncoderLoader = null;
  decoderPromise = null;
  customDecoderLoader = null;
  clearPromptEmbeddingCache();
  setTestAnchors(null);
}

export async function getEncoder(): Promise<EncoderSession> {
  if (encoderPromise) return encoderPromise;

  const loadPromise = (async () => {
    if (customEncoderLoader) {
      return await customEncoderLoader();
    }

    let transformersModule: typeof import('@huggingface/transformers');
    try {
      transformersModule = await import('@huggingface/transformers');
    } catch (err) {
      throw errorWithCause(
        `AI ONNX/WASM runtime load failed while importing @huggingface/transformers: ${errorDetail(err)}`,
        err,
      );
    }

    const { AutoTokenizer, AutoModel, env } = transformersModule;
    env.allowLocalModels = true;
    env.allowRemoteModels = false;
    env.localModelPath = typeof window !== 'undefined' ? '/models/' : './public/models/';

    if (typeof window !== 'undefined' && env.backends?.onnx?.wasm) {
      delete env.backends.onnx.wasm.wasmPaths;
      env.backends.onnx.wasm.numThreads = 1;
      env.backends.onnx.wasm.proxy = false;
    }

    let tokenizer;
    try {
      tokenizer = await AutoTokenizer.from_pretrained(ENCODER_MODEL_ID);
    } catch (err) {
      throw errorWithCause(
        `AI tokenizer load failed for ${ENCODER_MODEL_ID}: GET /models/${ENCODER_MODEL_ID}/tokenizer.json (${errorDetail(err)})`,
        err,
      );
    }

    let model;
    try {
      model = await AutoModel.from_pretrained(ENCODER_MODEL_ID, { dtype: 'q8' });
    } catch (err) {
      throw errorWithCause(
        `AI encoder load failed while loading E5 model: GET /models/${ENCODER_MODEL_ID}/onnx/model_quantized.onnx (${errorDetail(err)})`,
        err,
      );
    }

    return { tokenizer, model };
  })();

  encoderPromise = loadPromise.catch((err) => {
    encoderPromise = null;
    throw err;
  });

  return encoderPromise;
}

export interface DecoderManifestContract {
  schemaVersion?: number;
  model?: string;
  version?: string;
  modelVersion?: string;
  codename?: string | null;
  status?: string;
  trainedFromCandidate?: number;
  productionReady?: boolean;
  textEncoder?: {
    id?: string;
    browserId?: string;
    dimension?: number;
    prefix?: string;
    pooling?: string;
    l2Normalized?: boolean;
    sha256?: string;
    bytes?: number;
  };
  decoder?: {
    path?: string;
    url?: string;
    sha256?: string;
    sizeBytes?: number;
    bytes?: number;
    format?: string;
    opset?: number;
    parameters?: number;
  };
}

export interface ValidatedDecoderManifest {
  modelVersion: string;
  decoderPath: string;
  decoderSha256: string;
  decoderBytes: number;
  productionReady: boolean;
}

export function validateDecoderManifest(
  raw: unknown,
  options: { allowExperimental?: boolean } = {},
): ValidatedDecoderManifest {
  if (!raw || typeof raw !== 'object') {
    throw new Error('manifest must be a JSON object');
  }

  const manifest = raw as DecoderManifestContract;
  if (manifest.schemaVersion !== 2) {
    throw new Error('manifest schemaVersion must be 2');
  }
  const version = typeof manifest.modelVersion === 'string' && manifest.modelVersion.trim()
    ? manifest.modelVersion.trim()
    : (typeof manifest.version === 'string' && manifest.version.trim() ? manifest.version.trim() : null);

  if (!version) {
    throw new Error('manifest modelVersion must be a non-empty string');
  }

  const rawPath = manifest.decoder?.path ?? manifest.decoder?.url;
  const decoderPath = typeof rawPath === 'string' && rawPath.trim() ? rawPath.trim() : null;

  if (!decoderPath || !decoderPath.startsWith('/models/')) {
    throw new Error('manifest decoder path must be a valid path under /models/');
  }
  if (decoderPath.includes('..') || !decoderPath.endsWith('.onnx')) {
    throw new Error('manifest decoder path must identify an ONNX file under /models/');
  }
  const decoderSha256 = manifest.decoder?.sha256;
  if (typeof decoderSha256 !== 'string' || !/^[a-f0-9]{64}$/.test(decoderSha256)) {
    throw new Error('manifest decoder sha256 must be 64 lowercase hexadecimal characters');
  }
  const decoderBytes = manifest.decoder?.sizeBytes ?? manifest.decoder?.bytes;
  if (!Number.isSafeInteger(decoderBytes) || Number(decoderBytes) <= 0) {
    throw new Error('manifest decoder bytes must be a positive safe integer');
  }
  if (manifest.decoder?.format !== 'onnx' || !Number.isInteger(manifest.decoder?.opset)) {
    throw new Error('manifest decoder format/opset contract is invalid');
  }
  const encoder = manifest.textEncoder;
  if (
    encoder?.id !== E5_UPSTREAM_MODEL_ID
    || encoder.browserId !== ENCODER_MODEL_ID
    || encoder.dimension !== ENCODER_EMBEDDING_SIZE
    || encoder.prefix !== 'query: '
    || encoder.pooling !== 'mean'
    || encoder.l2Normalized !== true
    || typeof encoder.sha256 !== 'string'
    || !/^[a-f0-9]{64}$/.test(encoder.sha256)
    || !Number.isSafeInteger(encoder.bytes)
    || Number(encoder.bytes) <= 0
  ) {
    throw new Error('manifest textEncoder does not match the frozen production E5 contract');
  }
  if (typeof manifest.productionReady !== 'boolean') {
    throw new Error('manifest productionReady must be boolean');
  }
  if (!Number.isInteger(manifest.trainedFromCandidate) || manifest.trainedFromCandidate !== 11) {
    throw new Error('manifest trainedFromCandidate must identify Candidate 11');
  }
  if (!manifest.productionReady && manifest.codename !== null) {
    throw new Error('experimental Candidate 11 manifest codename must be null');
  }
  if (!manifest.productionReady && !options.allowExperimental) {
    throw new Error(
      'manifest marks this decoder experimental; set NEXT_PUBLIC_PALETTEBRAIN_ALLOW_EXPERIMENTAL=1 only for development qualification',
    );
  }

  return {
    modelVersion: version,
    decoderPath,
    decoderSha256,
    decoderBytes: Number(decoderBytes),
    productionReady: manifest.productionReady,
  };
}

async function loadDecoderManifest(): Promise<ValidatedDecoderManifest> {
  if (typeof fetch !== 'function') {
    throw new Error('fetch is unavailable');
  }

  const response = await fetch(DECODER_MANIFEST_PATH, {
    cache: 'no-cache',
    headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' },
  });
  if (!response.ok) {
    throw new Error(`GET ${DECODER_MANIFEST_PATH} returned ${response.status}`);
  }

  const raw = await response.json() as unknown;
  return validateDecoderManifest(raw, {
    allowExperimental: process.env.NEXT_PUBLIC_PALETTEBRAIN_ALLOW_EXPERIMENTAL === '1',
  });
}

async function sha256Hex(value: ArrayBuffer): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error('Web Crypto SHA-256 is unavailable');
  }
  const digest = await globalThis.crypto.subtle.digest('SHA-256', value);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function createDefaultDecoderSession(): Promise<PaletteDecoderSession> {
  let manifest: ValidatedDecoderManifest;
  try {
    manifest = await loadDecoderManifest();
  } catch (err) {
    throw errorWithCause(`AI palette decoder manifest load failed: ${errorDetail(err)}`, err);
  }

  let ort: typeof import('onnxruntime-web/webgpu');
  try {
    ort = await import('onnxruntime-web/webgpu');
  } catch (err) {
    throw errorWithCause(`AI palette decoder runtime load failed: ${errorDetail(err)}`, err);
  }

  delete ort.env.wasm.wasmPaths;
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.proxy = false;

  let decoderBytes: ArrayBuffer;
  try {
    const response = await fetch(manifest.decoderPath, { cache: 'no-cache' });
    if (!response.ok) {
      throw new Error(`GET ${manifest.decoderPath} returned ${response.status}`);
    }
    decoderBytes = await response.arrayBuffer();
    if (decoderBytes.byteLength !== manifest.decoderBytes) {
      throw new Error(
        `decoder byte size mismatch: manifest=${manifest.decoderBytes}, actual=${decoderBytes.byteLength}`,
      );
    }
    const actualSha256 = await sha256Hex(decoderBytes);
    if (actualSha256 !== manifest.decoderSha256) {
      throw new Error('decoder SHA-256 does not match the manifest');
    }
  } catch (err) {
    throw errorWithCause(`AI palette decoder integrity check failed: ${errorDetail(err)}`, err);
  }

  let session: import('onnxruntime-web/webgpu').InferenceSession;
  try {
    session = await ort.InferenceSession.create(decoderBytes, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all',
    });
  } catch (err) {
    throw errorWithCause(
      `AI palette decoder load failed for ${manifest.decoderPath}: ${errorDetail(err)}`,
      err,
    );
  }

  return {
    modelVersion: manifest.modelVersion,
    decoderSha256: manifest.decoderSha256,
    async run(feeds) {
      const ortFeeds: Record<string, import('onnxruntime-web/webgpu').Tensor> = {};
      for (const [name, tensor] of Object.entries(feeds)) {
        ortFeeds[name] = new ort.Tensor('float32', tensor.data, [...tensor.dims]);
      }

      const outputs = await session.run(ortFeeds);
      const palette = outputs.palette;
      if (!palette) {
        throw new Error('decoder did not return the required "palette" output');
      }
      if (palette.type !== 'float32') {
        throw new Error(`decoder palette output must be float32, got ${palette.type}`);
      }

      return {
        data: palette.data as Float32Array,
        dims: palette.dims,
      };
    },
  };
}

export async function getPaletteDecoder(): Promise<PaletteDecoderSession> {
  if (decoderPromise) return decoderPromise;

  const loadPromise = customDecoderLoader
    ? customDecoderLoader()
    : createDefaultDecoderSession();

  decoderPromise = loadPromise.catch((err) => {
    decoderPromise = null;
    if (err instanceof Error && err.message.startsWith('AI palette decoder')) {
      throw err;
    }
    throw errorWithCause(`AI palette decoder load failed: ${errorDetail(err)}`, err);
  });

  return decoderPromise;
}

function enqueueEncoderRun<T>(run: () => Promise<T>): Promise<T> {
  const result = encoderRunQueue.then(run, run);
  encoderRunQueue = result.then(() => undefined, () => undefined);
  return result;
}

function enqueueDecoderRun<T>(run: () => Promise<T>): Promise<T> {
  const result = decoderRunQueue.then(run, run);
  decoderRunQueue = result.then(() => undefined, () => undefined);
  return result;
}

async function computePromptEmbedding(normalized: string): Promise<Float32Array> {
  const { tokenizer, model } = await getEncoder();

  let inputs;
  try {
    inputs = await tokenizer(`query: ${normalized}`, { padding: true, truncation: true });
  } catch (err) {
    throw errorWithCause(`AI tokenization failed for prompt "${normalized}": ${errorDetail(err)}`, err);
  }

  let outputs: {
    last_hidden_state?: {
      dims?: readonly number[];
      data?: ArrayLike<number>;
    };
  };
  try {
    outputs = await enqueueEncoderRun(() => model(inputs));
  } catch (err) {
    throw errorWithCause(`AI model inference failed: ${errorDetail(err)}`, err);
  }

  const lastHiddenState = outputs?.last_hidden_state;
  const dims = lastHiddenState?.dims as readonly number[] | undefined;
  const data = lastHiddenState?.data as ArrayLike<number> | undefined;
  const mask = inputs?.attention_mask?.data as ArrayLike<number | bigint> | undefined;

  if (
    !dims
    || dims.length !== 3
    || dims[0] !== 1
    || dims[2] !== ENCODER_EMBEDDING_SIZE
    || !Number.isInteger(dims[1])
    || dims[1] < 1
  ) {
    throw new Error(
      `AI encoder output invalid: expected [1,sequence,${ENCODER_EMBEDDING_SIZE}], got [${dims?.join(',') ?? ''}]`,
    );
  }

  const seqLen = dims[1];
  const hiddenDim = dims[2];
  if (!data || data.length < seqLen * hiddenDim) {
    throw new Error('AI encoder output invalid: last_hidden_state data is too short');
  }
  if (!mask || mask.length < seqLen) {
    throw new Error('AI encoder output invalid: attention mask is missing or too short');
  }

  const meanPooled = new Float32Array(hiddenDim);
  let totalWeight = 0;

  for (let s = 0; s < seqLen; s++) {
    const weight = Number(mask[s]);
    if (weight > 0) {
      totalWeight += weight;
      const offset = s * hiddenDim;
      for (let d = 0; d < hiddenDim; d++) {
        meanPooled[d] += Number(data[offset + d]) * weight;
      }
    }
  }

  if (!Number.isFinite(totalWeight) || totalWeight <= 0) {
    throw new Error('AI encoder output invalid: attention mask contains no active tokens');
  }

  let normSq = 0;
  for (let d = 0; d < hiddenDim; d++) {
    meanPooled[d] /= totalWeight;
    normSq += meanPooled[d] * meanPooled[d];
  }

  if (!Number.isFinite(normSq) || normSq <= 1e-12) {
    throw new Error('AI encoder output invalid: pooled embedding is not finite and non-zero');
  }

  const norm = Math.sqrt(normSq);
  for (let d = 0; d < hiddenDim; d++) {
    meanPooled[d] /= norm;
  }

  return meanPooled;
}

function getCachedPromptEmbedding(normalized: string): Promise<Float32Array> {
  const key = `${ENCODER_MODEL_ID}\u0000${normalized}`;
  const cached = promptEmbeddingCache.get(key);
  if (cached) {
    // Refresh insertion order so the Map acts as a small LRU.
    promptEmbeddingCache.delete(key);
    promptEmbeddingCache.set(key, cached);
    return cached;
  }

  const embeddingPromise = computePromptEmbedding(normalized).catch((err) => {
    if (promptEmbeddingCache.get(key) === embeddingPromise) {
      promptEmbeddingCache.delete(key);
    }
    throw err;
  });
  promptEmbeddingCache.set(key, embeddingPromise);

  while (promptEmbeddingCache.size > PROMPT_EMBEDDING_CACHE_LIMIT) {
    const oldestKey = promptEmbeddingCache.keys().next().value as string | undefined;
    if (oldestKey === undefined) break;
    promptEmbeddingCache.delete(oldestKey);
  }

  return embeddingPromise;
}

export async function encodePrompt(prompt: string): Promise<Float32Array> {
  const normalized = normalizeText(prompt);
  if (!normalized) {
    throw new Error('Empty prompt');
  }
  return (await getCachedPromptEmbedding(normalized)).slice();
}

/**
 * Explicit legacy baseline retained for offline CURRENT-vs-NEW comparison.
 * It intentionally returns one base color and a procedural harmony intent.
 */
export async function inferPaletteIntent(prompt: string): Promise<AiPaletteIntent & { seed: number }> {
  const normalized = normalizeText(prompt);
  if (!normalized) {
    throw new Error('Empty prompt');
  }

  const [meanPooled, anchors] = await Promise.all([
    getCachedPromptEmbedding(normalized),
    getSemanticAnchors(),
  ]);

  let intent = blendAnchorIntent(meanPooled, anchors);
  const colorConstraint = matchColorConstraint(normalized);
  if (colorConstraint) {
    intent = applyColorConstraint(colorConstraint.intent, intent, colorConstraint.weight);
  }

  const sanitized = sanitizeSemanticIntent(intent);
  const baseHex = semanticIntentToBase(sanitized);
  const seed = stablePromptHash(normalized);

  return {
    baseHex,
    harmony: sanitized.harmony,
    seed,
  };
}

function validateGenerateRequest(request: GenerateAiPaletteRequest): {
  normalized: string;
  lockedByIndex: Map<number, OklchColor>;
} {
  if (!request || typeof request.prompt !== 'string') {
    throw new Error('AI prompt must be a string');
  }

  const normalized = normalizeText(request.prompt);
  if (!normalized) {
    throw new Error('AI prompt must not be empty');
  }

  if (!Number.isInteger(request.count) || request.count < 2 || request.count > MAX_PALETTE_SIZE) {
    throw new Error(`AI palette count must be an integer from 2 to ${MAX_PALETTE_SIZE}`);
  }

  if (
    !Number.isSafeInteger(request.seed)
    || request.seed < 0
    || request.seed > 0xffffffff
  ) {
    throw new Error('AI palette seed must be an unsigned 32-bit integer');
  }

  if (request.lockedColors !== undefined && !Array.isArray(request.lockedColors)) {
    throw new Error('AI palette lockedColors must be an array');
  }

  const lockedByIndex = new Map<number, OklchColor>();
  for (const locked of request.lockedColors ?? []) {
    if (!locked || !Number.isInteger(locked.index) || locked.index < 0 || locked.index >= request.count) {
      throw new Error(`Locked color index must be an integer from 0 to ${request.count - 1}`);
    }
    if (lockedByIndex.has(locked.index)) {
      throw new Error(`Duplicate locked color index: ${locked.index}`);
    }

    const color = locked.oklch;
    if (
      !color
      || !Number.isFinite(color.l)
      || color.l < 0
      || color.l > 1
      || !Number.isFinite(color.c)
      || color.c < 0
      || (color.h !== null && !Number.isFinite(color.h))
    ) {
      throw new Error(`Locked color at index ${locked.index} is not valid OKLCH`);
    }
    if (!isInSrgbGamut(color)) {
      throw new Error(`Locked color at index ${locked.index} must already be in the sRGB gamut`);
    }

    lockedByIndex.set(locked.index, { ...color });
  }

  return { normalized, lockedByIndex };
}

function createSeedNoise(seed: number): Float32Array {
  let state = seed >>> 0;
  const random = (): number => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 0x100000000;
  };

  const noise = new Float32Array(MAX_PALETTE_SIZE * 4);
  for (let i = 0; i < noise.length; i += 2) {
    const u1 = Math.max(random(), Number.EPSILON);
    const u2 = random();
    const radius = Math.sqrt(-2 * Math.log(u1));
    const angle = 2 * Math.PI * u2;
    noise[i] = radius * Math.cos(angle);
    noise[i + 1] = radius * Math.sin(angle);
  }
  return noise;
}

function createDecoderFeeds(
  embedding: Float32Array,
  count: number,
  seed: number,
  lockedByIndex: ReadonlyMap<number, OklchColor>,
): PaletteDecoderFeeds {
  if (embedding.length !== ENCODER_EMBEDDING_SIZE) {
    throw new Error(`Expected a ${ENCODER_EMBEDDING_SIZE}-value text embedding, got ${embedding.length}`);
  }

  const countMask = new Float32Array(MAX_PALETTE_SIZE);
  countMask.fill(1, 0, count);

  const lockedMask = new Float32Array(MAX_PALETTE_SIZE);
  const lockedColors = new Float32Array(MAX_PALETTE_SIZE * 4);
  for (const [index, color] of lockedByIndex) {
    lockedMask[index] = 1;
    const offset = index * 4;
    lockedColors[offset] = color.l;
    lockedColors[offset + 1] = color.c;
    if (color.h !== null) {
      const radians = color.h * Math.PI / 180;
      lockedColors[offset + 2] = Math.sin(radians);
      lockedColors[offset + 3] = Math.cos(radians);
    }
  }

  return {
    text_embedding: { data: embedding, dims: [1, ENCODER_EMBEDDING_SIZE] },
    count_mask: { data: countMask, dims: [1, MAX_PALETTE_SIZE] },
    seed_noise: { data: createSeedNoise(seed), dims: [1, MAX_PALETTE_SIZE, 4] },
    locked_mask: { data: lockedMask, dims: [1, MAX_PALETTE_SIZE] },
    locked_colors: { data: lockedColors, dims: [1, MAX_PALETTE_SIZE, 4] },
  };
}

export async function generateAiPalette(
  request: GenerateAiPaletteRequest,
): Promise<GenerateAiPaletteResult> {
  const totalStartedAt = nowMs();
  const { normalized, lockedByIndex } = validateGenerateRequest(request);

  const encoderStartedAt = nowMs();
  const embedding = await getCachedPromptEmbedding(normalized);
  const encoderMs = nowMs() - encoderStartedAt;

  const decoderStartedAt = nowMs();
  const decoder = await getPaletteDecoder();
  const feeds = createDecoderFeeds(embedding, request.count, request.seed, lockedByIndex);

  let output: PaletteDecoderTensor;
  try {
    output = await enqueueDecoderRun(() => decoder.run(feeds));
  } catch (err) {
    throw errorWithCause(`AI palette decoder inference failed: ${errorDetail(err)}`, err);
  }
  const decoderMs = nowMs() - decoderStartedAt;

  let colors: OklchColor[];
  try {
    colors = decodePaletteOutput(output, request.count, lockedByIndex);
  } catch (err) {
    throw errorWithCause(`AI palette decoder output invalid: ${errorDetail(err)}`, err);
  }

  // Defense in depth: model and post-processing must never alter locked colors.
  for (const [index, color] of lockedByIndex) {
    colors[index] = { ...color };
  }
  if (colors.length !== request.count) {
    throw new Error(`AI palette decoder returned ${colors.length} colors; expected ${request.count}`);
  }

  return {
    colors,
    seed: request.seed,
    modelVersion: decoder.modelVersion,
    decoderSha256: decoder.decoderSha256,
    inference: {
      encoderMs,
      decoderMs,
      totalMs: nowMs() - totalStartedAt,
    },
    fallback: false,
  };
}
