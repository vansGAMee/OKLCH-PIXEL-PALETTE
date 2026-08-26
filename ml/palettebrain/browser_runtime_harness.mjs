#!/usr/bin/env node

/**
 * Local-only benchmark/parity harness for the production browser AI pipeline.
 *
 * It injects ONNX Runtime Web WASM sessions through inference.ts's loader seams,
 * so normalization, pooling, caching, seed noise, lock feeds, and palette decode
 * remain owned by the browser runtime rather than being reimplemented here.
 */

import { createHash, randomUUID } from 'node:crypto';
import { createReadStream } from 'node:fs';
import {
  mkdir,
  open,
  readFile,
  rename,
  stat,
  unlink,
} from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';
import { createJiti } from 'jiti';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, '..', '..');
const PUBLIC_DIR = path.join(PROJECT_ROOT, 'public');
const MODELS_DIR = path.join(PUBLIC_DIR, 'models');
const INPUT_LIMIT_BYTES = 2 * 1024 * 1024;
const REQUEST_LIMIT = 128;
const PROMPT_LIMIT_CODE_POINTS = 32_768;
const HARNESS_VERSION = 1;
const ENCODER_MODEL_ID = 'multilingual-e5-small';
const PARITY_CORPUS_NAME = 'parity-smoke-v1';

const HELP = `PaletteBrain browser runtime harness

Usage:
  node ml/palettebrain/browser_runtime_harness.mjs --input INPUT.json --output OUTPUT.json
  Get-Content INPUT.json | node ml/palettebrain/browser_runtime_harness.mjs --input - --output OUTPUT.json
  node ml/palettebrain/browser_runtime_harness.mjs --print-parity-input

Input schemas:
  {"schemaVersion":1,"mode":"embeddings","prompts":["winter forest",{"id":"ru","prompt":"зимний лес"}]}
  {"schemaVersion":1,"fixtureVersion":"...","prompts":[{"id":"long","text":"painted city","repeat":12}]}
  {"schemaVersion":1,"mode":"embeddings","corpus":"${PARITY_CORPUS_NAME}"}
  {"schemaVersion":1,"mode":"palettebrain","requests":[{"prompt":"winter forest","count":4,"seed":42,"lockedColors":[]}]}
  {"schemaVersion":1,"mode":"legacy","requests":[{"prompt":"winter forest","count":4,"seed":42}]}

Legacy mode uses the request seed for procedural palette generation. The seed
returned by inferPaletteIntent is recorded separately as intentSeed.
`;

function progress(message) {
  process.stderr.write(`[browser-runtime] ${message}\n`);
}

function parseCli(argv) {
  const options = { input: null, output: null, help: false, printParityInput: false };

  for (let index = 0; index < argv.length; index++) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      options.help = true;
    } else if (arg === '--print-parity-input') {
      options.printParityInput = true;
    } else if (arg === '--input' || arg === '-i') {
      options.input = argv[++index];
    } else if (arg.startsWith('--input=')) {
      options.input = arg.slice('--input='.length);
    } else if (arg === '--output' || arg === '-o') {
      options.output = argv[++index];
    } else if (arg.startsWith('--output=')) {
      options.output = arg.slice('--output='.length);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (options.help || options.printParityInput) return options;
  if (!options.input) throw new Error('Missing --input (use - for stdin)');
  if (!options.output) throw new Error('Missing --output');
  return options;
}

function parityCorpus() {
  const longPrompt = Array.from(
    { length: 24 },
    (_, index) => index % 2 === 0
      ? 'quiet winter forest beneath blue stars'
      : 'тихий зимний лес под синими звездами',
  ).join(', ');
  const nearContextLimitPrompt = Array.from(
    { length: 150 },
    (_, index) => index % 3 === 0
      ? 'weathered violet observatory'
      : index % 3 === 1
        ? 'заброшенная фиолетовая обсерватория'
        : 'under cold moonlight',
  ).join(' ');

  return [
    { id: 'english', prompt: 'winter forest under blue stars' },
    { id: 'russian', prompt: 'заброшенная больница ночью' },
    { id: 'punctuation', prompt: 'RED!!! blue??? — neon rain...' },
    { id: 'mixed-ru-en', prompt: 'тихий winter forest with синий moonlight' },
    { id: 'long-description', prompt: longPrompt },
    { id: 'near-context-limit', prompt: nearContextLimitPrompt },
  ].map((entry) => ({ ...entry, sourceText: entry.prompt, repeat: 1 }));
}

function printParityInput() {
  process.stdout.write(`${JSON.stringify({
    schemaVersion: 1,
    mode: 'embeddings',
    corpus: PARITY_CORPUS_NAME,
  }, null, 2)}\n`);
}

async function readInput(source, invocationCwd) {
  if (source === '-') {
    const chunks = [];
    let totalBytes = 0;
    for await (const chunk of process.stdin) {
      const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      totalBytes += buffer.length;
      if (totalBytes > INPUT_LIMIT_BYTES) {
        throw new Error(`stdin JSON exceeds ${INPUT_LIMIT_BYTES} bytes`);
      }
      chunks.push(buffer);
    }
    if (totalBytes === 0) throw new Error('stdin JSON is empty');
    return { raw: Buffer.concat(chunks).toString('utf8'), sourceLabel: 'stdin' };
  }

  const inputPath = path.resolve(invocationCwd, source);
  const inputStat = await stat(inputPath);
  if (!inputStat.isFile()) throw new Error(`Input is not a file: ${inputPath}`);
  if (inputStat.size > INPUT_LIMIT_BYTES) {
    throw new Error(`Input JSON exceeds ${INPUT_LIMIT_BYTES} bytes: ${inputPath}`);
  }
  return { raw: await readFile(inputPath, 'utf8'), sourceLabel: inputPath };
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function parseId(value, fallback, label) {
  if (value === undefined) return fallback;
  if (typeof value !== 'string' && typeof value !== 'number') {
    throw new Error(`${label}.id must be a string or number`);
  }
  if (typeof value === 'number' && !Number.isSafeInteger(value)) {
    throw new Error(`${label}.id number must be a safe integer`);
  }
  return value;
}

function parsePrompt(value, label) {
  if (typeof value !== 'string') throw new Error(`${label} must be a string`);
  if (!value.trim()) throw new Error(`${label} must not be empty`);
  if (Array.from(value).length > PROMPT_LIMIT_CODE_POINTS) {
    throw new Error(`${label} exceeds ${PROMPT_LIMIT_CODE_POINTS} Unicode code points`);
  }
  return value;
}

function parseRepeatedPrompt(entry, label) {
  if (entry.prompt !== undefined && entry.text !== undefined) {
    throw new Error(`${label} must use either prompt or text, not both`);
  }
  const sourceText = parsePrompt(entry.prompt ?? entry.text, `${label}.prompt/text`);
  const repeat = entry.repeat ?? 1;
  if (!Number.isInteger(repeat) || repeat < 1 || repeat > 1024) {
    throw new Error(`${label}.repeat must be an integer from 1 to 1024`);
  }
  const expandedCodePoints = Array.from(sourceText).length * repeat + repeat - 1;
  if (expandedCodePoints > PROMPT_LIMIT_CODE_POINTS) {
    throw new Error(
      `${label} expanded prompt exceeds ${PROMPT_LIMIT_CODE_POINTS} Unicode code points`,
    );
  }
  return {
    prompt: repeat === 1 ? sourceText : new Array(repeat).fill(sourceText).join(' '),
    sourceText,
    repeat,
  };
}

function parseCount(value, label) {
  if (!Number.isInteger(value) || value < 2 || value > 9) {
    throw new Error(`${label} must be an integer from 2 to 9`);
  }
  return value;
}

function parseSeed(value, label) {
  if (!Number.isSafeInteger(value) || value < 0 || value > 0xffff_ffff) {
    throw new Error(`${label} must be an unsigned 32-bit integer`);
  }
  return value;
}

function parseLockedColors(value, count, label) {
  if (value === undefined) return [];
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  if (value.length > 9) throw new Error(`${label} must contain at most 9 entries`);

  const seen = new Set();
  return value.map((entry, index) => {
    const entryLabel = `${label}[${index}]`;
    if (!isRecord(entry)) throw new Error(`${entryLabel} must be an object`);
    if (!Number.isInteger(entry.index) || entry.index < 0 || entry.index >= count) {
      throw new Error(`${entryLabel}.index must be an integer from 0 to ${count - 1}`);
    }
    if (seen.has(entry.index)) throw new Error(`${label} has duplicate index ${entry.index}`);
    seen.add(entry.index);

    if (!isRecord(entry.oklch)) throw new Error(`${entryLabel}.oklch must be an object`);
    const { l, c, h } = entry.oklch;
    if (!Number.isFinite(l) || l < 0 || l > 1) {
      throw new Error(`${entryLabel}.oklch.l must be finite and in [0,1]`);
    }
    if (!Number.isFinite(c) || c < 0) {
      throw new Error(`${entryLabel}.oklch.c must be finite and non-negative`);
    }
    if (h !== null && !Number.isFinite(h)) {
      throw new Error(`${entryLabel}.oklch.h must be finite or null`);
    }
    return { index: entry.index, oklch: { l, c, h } };
  });
}

function parseInputSpec(raw) {
  let value;
  try {
    value = JSON.parse(raw);
  } catch (error) {
    throw new Error(`Input is not valid JSON: ${error instanceof Error ? error.message : error}`);
  }
  if (!isRecord(value)) throw new Error('Input JSON must be an object');
  if (value.schemaVersion !== undefined && value.schemaVersion !== 1) {
    throw new Error('Input schemaVersion must be 1 when provided');
  }

  const mode = value.mode ?? (
    typeof value.fixtureVersion === 'string' && Array.isArray(value.prompts)
      ? 'embeddings'
      : undefined
  );
  if (!['embeddings', 'palettebrain', 'legacy'].includes(mode)) {
    throw new Error('mode must be one of: embeddings, palettebrain, legacy');
  }

  if (mode === 'embeddings') {
    if (value.corpus !== undefined && value.prompts !== undefined) {
      throw new Error('embeddings input must use either corpus or prompts, not both');
    }
    let prompts;
    if (value.corpus !== undefined) {
      if (value.corpus !== PARITY_CORPUS_NAME) {
        throw new Error(`Unknown corpus: ${value.corpus}`);
      }
      prompts = parityCorpus();
    } else {
      if (!Array.isArray(value.prompts)) throw new Error('embeddings.prompts must be an array');
      prompts = value.prompts.map((entry, index) => {
        const label = `prompts[${index}]`;
        if (typeof entry === 'string') {
          const prompt = parsePrompt(entry, label);
          return { id: index, prompt, sourceText: prompt, repeat: 1 };
        }
        if (!isRecord(entry)) throw new Error(`${label} must be a string or object`);
        const repeated = parseRepeatedPrompt(entry, label);
        return {
          id: parseId(entry.id, index, label),
          ...repeated,
        };
      });
    }
    if (prompts.length < 1 || prompts.length > REQUEST_LIMIT) {
      throw new Error(`embeddings requires 1 to ${REQUEST_LIMIT} prompts`);
    }
    return {
      mode,
      corpus: value.corpus ?? null,
      fixture: value.fixtureVersion
        ? {
            fixtureVersion: value.fixtureVersion,
            frozenAt: value.frozenAt ?? null,
            releaseThresholds: value.releaseThresholds ?? null,
          }
        : null,
      requests: prompts,
    };
  }

  if (!Array.isArray(value.requests)) throw new Error(`${mode}.requests must be an array`);
  if (value.requests.length < 1 || value.requests.length > REQUEST_LIMIT) {
    throw new Error(`${mode} requires 1 to ${REQUEST_LIMIT} requests`);
  }
  const requests = value.requests.map((entry, index) => {
    const label = `requests[${index}]`;
    if (!isRecord(entry)) throw new Error(`${label} must be an object`);
    const count = parseCount(entry.count, `${label}.count`);
    const request = {
      id: parseId(entry.id, index, label),
      prompt: parsePrompt(entry.prompt, `${label}.prompt`),
      count,
      seed: parseSeed(entry.seed, `${label}.seed`),
    };
    if (mode === 'palettebrain') {
      request.lockedColors = parseLockedColors(entry.lockedColors, count, `${label}.lockedColors`);
    } else if (entry.lockedColors !== undefined) {
      throw new Error(`${label}.lockedColors is unsupported in legacy mode`);
    }
    return request;
  });
  return { mode, corpus: null, fixture: null, requests };
}

async function sha256File(filePath) {
  return await new Promise((resolvePromise, rejectPromise) => {
    const hash = createHash('sha256');
    const stream = createReadStream(filePath);
    stream.on('error', rejectPromise);
    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('end', () => resolvePromise(hash.digest('hex')));
  });
}

function repoRelative(filePath) {
  return path.relative(PROJECT_ROOT, filePath).split(path.sep).join('/');
}

async function fileMetadata(filePath) {
  const info = await stat(filePath);
  if (!info.isFile()) throw new Error(`Required artifact is not a file: ${filePath}`);
  return {
    path: repoRelative(filePath),
    sizeBytes: info.size,
    sha256: await sha256File(filePath),
  };
}

async function readJsonFile(filePath, label) {
  try {
    return JSON.parse(await readFile(filePath, 'utf8'));
  } catch (error) {
    throw new Error(`Cannot read ${label}: ${error instanceof Error ? error.message : error}`);
  }
}

async function packageVersion(...segments) {
  const packageJsonPath = path.join(PROJECT_ROOT, 'node_modules', ...segments, 'package.json');
  try {
    return (await readJsonFile(packageJsonPath, packageJsonPath)).version ?? null;
  } catch {
    return null;
  }
}

function resolvePublicArtifact(publicUrl) {
  if (typeof publicUrl !== 'string' || !publicUrl.startsWith('/')) {
    throw new Error('Manifest decoder.path must be a root-relative public URL');
  }
  const resolved = path.resolve(PUBLIC_DIR, publicUrl.replace(/^\/+/, ''));
  const relativePath = path.relative(PUBLIC_DIR, resolved);
  if (relativePath.startsWith('..') || path.isAbsolute(relativePath)) {
    throw new Error(`Manifest decoder.path escapes public/: ${publicUrl}`);
  }
  return resolved;
}

async function collectRuntimeMetadata() {
  const manifestPath = path.join(MODELS_DIR, 'palettebrain-v2.manifest.json');
  const manifest = await readJsonFile(manifestPath, 'PaletteBrain manifest');
  const transformersPackage = await readJsonFile(
    path.join(PROJECT_ROOT, 'node_modules', '@huggingface', 'transformers', 'package.json'),
    '@huggingface/transformers package metadata',
  );
  const declaredTransformersOrtVersion = transformersPackage?.dependencies?.['onnxruntime-web'];
  const decoderUrl = manifest?.decoder?.path ?? manifest?.decoder?.url;
  const decoderPath = resolvePublicArtifact(decoderUrl);
  const encoderModelPath = path.join(MODELS_DIR, ENCODER_MODEL_ID, 'onnx', 'model_quantized.onnx');
  const tokenizerPath = path.join(MODELS_DIR, ENCODER_MODEL_ID, 'tokenizer.json');
  const encoderConfigPath = path.join(MODELS_DIR, ENCODER_MODEL_ID, 'config.json');
  const tokenizerConfigPath = path.join(MODELS_DIR, ENCODER_MODEL_ID, 'tokenizer_config.json');
  const semanticAnchorsPath = path.join(MODELS_DIR, 'semantic-anchors.json');
  const [
    manifestMeta,
    decoderMeta,
    encoderMeta,
    tokenizerMeta,
    encoderConfigMeta,
    tokenizerConfigMeta,
    semanticAnchorsMeta,
    transformersVersion,
    ortWebVersion,
    jitiVersion,
    transformersOrtWebVersion,
    transformersOrtNodeVersion,
  ] = await Promise.all([
    fileMetadata(manifestPath),
    fileMetadata(decoderPath),
    fileMetadata(encoderModelPath),
    fileMetadata(tokenizerPath),
    fileMetadata(encoderConfigPath),
    fileMetadata(tokenizerConfigPath),
    fileMetadata(semanticAnchorsPath),
    packageVersion('@huggingface', 'transformers'),
    packageVersion('onnxruntime-web'),
    packageVersion('jiti'),
    packageVersion('@huggingface', 'transformers', 'node_modules', 'onnxruntime-web'),
    packageVersion('@huggingface', 'transformers', 'node_modules', 'onnxruntime-node'),
  ]);

  const declaredEncoderId = manifest?.textEncoder?.browserId
    ?? (typeof manifest.encoder === 'string' ? manifest.encoder : manifest?.encoder?.modelId);
  if (declaredEncoderId !== ENCODER_MODEL_ID) {
    throw new Error(
      `Manifest encoder ${String(declaredEncoderId)} does not match runtime ${ENCODER_MODEL_ID}`,
    );
  }

  const declaredDecoderSha = manifest?.decoder?.sha256 ?? manifest.decoderSha256;
  const declaredDecoderBytes = manifest?.decoder?.sizeBytes
    ?? manifest?.decoder?.bytes
    ?? manifest.decoderBytes;
  if (declaredDecoderSha && declaredDecoderSha !== decoderMeta.sha256) {
    throw new Error('Decoder SHA-256 does not match the manifest');
  }
  if (declaredDecoderBytes !== undefined && declaredDecoderBytes !== decoderMeta.sizeBytes) {
    throw new Error('Decoder byte size does not match the manifest');
  }
  if (typeof declaredTransformersOrtVersion !== 'string' || !declaredTransformersOrtVersion) {
    throw new Error('@huggingface/transformers must declare an onnxruntime-web dependency');
  }
  if (ortWebVersion !== declaredTransformersOrtVersion) {
    throw new Error(
      `Root onnxruntime-web ${String(ortWebVersion)} must exactly match `
      + `@huggingface/transformers requirement ${declaredTransformersOrtVersion}`,
    );
  }
  if (transformersOrtWebVersion && transformersOrtWebVersion !== ortWebVersion) {
    throw new Error('Nested Transformers onnxruntime-web does not match the shared root runtime');
  }

  const modelVersion = manifest.modelVersion ?? manifest.version;
  if (typeof modelVersion !== 'string' || !modelVersion.trim()) {
    throw new Error('Manifest must contain a non-empty modelVersion or version');
  }

  return {
    manifest,
    modelVersion,
    paths: { decoderPath, encoderModelPath },
    record: {
      node: {
        version: process.version,
        platform: process.platform,
        arch: process.arch,
      },
      packages: {
        '@huggingface/transformers': transformersVersion,
        'onnxruntime-web': ortWebVersion,
        'transformers-declared-onnxruntime-web': declaredTransformersOrtVersion,
        jiti: jitiVersion,
        'transformers>onnxruntime-web': transformersOrtWebVersion,
        'transformers>onnxruntime-node': transformersOrtNodeVersion,
      },
      backend: {
        host: 'node',
        runtime: 'onnxruntime-web/webgpu',
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all',
        numThreads: 1,
        proxy: false,
        localOnly: true,
        bundledContentHashedWasm: true,
        sharedOrtVersion: true,
      },
      artifacts: {
        encoder: {
          modelId: ENCODER_MODEL_ID,
          embeddingSize: 384,
          model: encoderMeta,
          tokenizer: tokenizerMeta,
          config: encoderConfigMeta,
          tokenizerConfig: tokenizerConfigMeta,
        },
        decoder: {
          modelVersion,
          status: manifest.status ?? null,
          productionReady: manifest.productionReady ?? null,
          manifest: manifestMeta,
          model: decoderMeta,
          manifestSha256Matches: !declaredDecoderSha || declaredDecoderSha === decoderMeta.sha256,
          manifestSizeMatches: declaredDecoderBytes === undefined || declaredDecoderBytes === decoderMeta.sizeBytes,
        },
        semanticAnchors: semanticAnchorsMeta,
        wasm: {
          delivery: 'bundled_content_hashed',
          runtimePackageVersion: ortWebVersion,
        },
      },
    },
  };
}

function ensureBigInt64(data, label) {
  if (data instanceof BigInt64Array) return data;
  if (!data || typeof data.length !== 'number') {
    throw new Error(`${label} is missing int64 tensor data`);
  }
  return BigInt64Array.from(data, (value) => BigInt(value));
}

function assertSessionInputs(session, required, label) {
  const missing = required.filter((name) => !session.inputNames.includes(name));
  if (missing.length > 0) throw new Error(`${label} is missing inputs: ${missing.join(', ')}`);
}

async function createRuntime(mode, runtimeMetadata) {
  let lastDecoderOutput = null;
  const [{ AutoTokenizer, env: transformersEnv }, ort] = await Promise.all([
    import('@huggingface/transformers'),
    import('onnxruntime-web/webgpu'),
  ]);

  transformersEnv.allowLocalModels = true;
  transformersEnv.allowRemoteModels = false;
  transformersEnv.localModelPath = './public/models/';
  transformersEnv.fetch = async (resource) => {
    throw new Error(`Network access is disabled by the harness: ${String(resource)}`);
  };

  ort.env.wasm.numThreads = 1;
  ort.env.wasm.proxy = false;

  const jiti = createJiti(import.meta.url, {
    tsconfigPaths: path.join(PROJECT_ROOT, 'tsconfig.json'),
  });
  const inference = await jiti.import(path.join(PROJECT_ROOT, 'src', 'lib', 'ai-palette', 'inference.ts'));
  const tokenizerModule = await jiti.import(path.join(PROJECT_ROOT, 'src', 'lib', 'ai-palette', 'tokenizer.ts'));

  inference.setTestEncoderLoader(async () => {
    progress('loading local q8 E5 with ONNX Runtime Web WASM');
    const tokenizer = await AutoTokenizer.from_pretrained(ENCODER_MODEL_ID, {
      local_files_only: true,
    });
    const encoderBytes = await readFile(runtimeMetadata.paths.encoderModelPath);
    const session = await ort.InferenceSession.create(encoderBytes, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all',
    });
    assertSessionInputs(
      session,
      ['input_ids', 'attention_mask', 'token_type_ids'],
      'E5 ONNX model',
    );

    return {
      tokenizer,
      model: async (inputs) => {
        const inputIds = inputs?.input_ids;
        const attentionMask = inputs?.attention_mask;
        if (!inputIds?.dims || !attentionMask?.dims) {
          throw new Error('Tokenizer did not return input_ids and attention_mask tensors');
        }
        const dims = [...inputIds.dims];
        const ids = ensureBigInt64(inputIds.data, 'input_ids');
        const mask = ensureBigInt64(attentionMask.data, 'attention_mask');
        const tokenTypes = inputs?.token_type_ids?.data
          ? ensureBigInt64(inputs.token_type_ids.data, 'token_type_ids')
          : new BigInt64Array(ids.length);

        const outputs = await session.run({
          input_ids: new ort.Tensor('int64', ids, dims),
          attention_mask: new ort.Tensor('int64', mask, dims),
          token_type_ids: new ort.Tensor('int64', tokenTypes, dims),
        });
        const hidden = outputs.last_hidden_state;
        if (!hidden || hidden.type !== 'float32') {
          throw new Error('E5 ONNX model did not return float32 last_hidden_state');
        }
        return {
          last_hidden_state: {
            data: hidden.data,
            dims: hidden.dims,
          },
        };
      },
    };
  });

  if (mode === 'palettebrain') {
    inference.setTestDecoderLoader(async () => {
      progress('loading current PaletteBrain decoder with ONNX Runtime Web WASM');
      const decoderBytes = await readFile(runtimeMetadata.paths.decoderPath);
      const session = await ort.InferenceSession.create(decoderBytes, {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all',
      });
      assertSessionInputs(
        session,
        ['text_embedding', 'count_mask', 'seed_noise', 'locked_mask', 'locked_colors'],
        'PaletteBrain ONNX model',
      );

      return {
        modelVersion: runtimeMetadata.modelVersion,
        run: async (feeds) => {
          const ortFeeds = Object.fromEntries(
            Object.entries(feeds).map(([name, tensor]) => [
              name,
              new ort.Tensor('float32', tensor.data, [...tensor.dims]),
            ]),
          );
          const outputs = await session.run(ortFeeds);
          const palette = outputs.palette;
          if (!palette || palette.type !== 'float32') {
            throw new Error('PaletteBrain ONNX model did not return float32 palette');
          }
          lastDecoderOutput = {
            dims: [...palette.dims],
            data: Array.from(palette.data),
          };
          return { data: palette.data, dims: palette.dims };
        },
      };
    });
  }

  let legacy = null;
  if (mode === 'legacy') {
    const generator = await jiti.import(path.join(PROJECT_ROOT, 'src', 'lib', 'color', 'generator.ts'));
    const extender = await jiti.import(path.join(PROJECT_ROOT, 'src', 'lib', 'color', 'extendPalette.ts'));
    legacy = {
      generatePalette: generator.generatePalette,
      extendPalette: extender.extendPalette,
    };
  }

  return {
    inference,
    normalizeText: tokenizerModule.normalizeText,
    legacy,
    getLastDecoderOutput: () => lastDecoderOutput,
  };
}

function roundedMs(startedAt) {
  return Math.round((performance.now() - startedAt) * 1000) / 1000;
}

function hashFloat32(values) {
  const bytes = Buffer.from(values.buffer, values.byteOffset, values.byteLength);
  return createHash('sha256').update(bytes).digest('hex');
}

async function runEmbeddings(requests, runtime) {
  const results = [];
  for (const request of requests) {
    const startedAt = performance.now();
    const embedding = await runtime.inference.encodePrompt(request.prompt);
    results.push({
      id: request.id,
      prompt: request.prompt,
      sourceText: request.sourceText ?? request.prompt,
      repeat: request.repeat ?? 1,
      normalizedPrompt: runtime.normalizeText(request.prompt),
      dimensions: embedding.length,
      dtype: 'float32',
      embeddingSha256: hashFloat32(embedding),
      embedding: Array.from(embedding),
      elapsedMs: roundedMs(startedAt),
    });
  }
  return results;
}

async function runPaletteBrain(requests, runtime) {
  const results = [];
  for (const request of requests) {
    const startedAt = performance.now();
    const result = await runtime.inference.generateAiPalette({
      prompt: request.prompt,
      count: request.count,
      seed: request.seed,
      lockedColors: request.lockedColors,
    });
    results.push({
      id: request.id,
      request: {
        prompt: request.prompt,
        count: request.count,
        seed: request.seed,
        lockedColors: request.lockedColors,
      },
      result,
      rawDecoderOutput: runtime.getLastDecoderOutput(),
      elapsedMs: roundedMs(startedAt),
    });
  }
  return results;
}

async function runLegacy(requests, runtime) {
  const results = [];
  for (const request of requests) {
    const startedAt = performance.now();
    const intent = await runtime.inference.inferPaletteIntent(request.prompt);
    const generated = runtime.legacy.generatePalette(
      intent.baseHex,
      intent.harmony,
      request.seed,
    );
    const colors = runtime.legacy.extendPalette(generated, request.count).map((color) => ({
      role: color.role,
      hex: color.hex,
      oklch: color.oklch,
    }));
    results.push({
      id: request.id,
      request: {
        prompt: request.prompt,
        count: request.count,
        benchmarkSeed: request.seed,
      },
      intent: {
        baseHex: intent.baseHex,
        harmony: intent.harmony,
        intentSeed: intent.seed,
      },
      palette: {
        seed: request.seed,
        count: request.count,
        colors,
      },
      elapsedMs: roundedMs(startedAt),
    });
  }
  return results;
}

async function atomicWriteJson(outputPath, value) {
  const outputDir = path.dirname(outputPath);
  await mkdir(outputDir, { recursive: true });
  const tempPath = path.join(
    outputDir,
    `.${path.basename(outputPath)}.${process.pid}.${randomUUID()}.tmp`,
  );
  let handle;
  try {
    handle = await open(tempPath, 'wx');
    await handle.writeFile(`${JSON.stringify(value, null, 2)}\n`, 'utf8');
    await handle.sync();
    await handle.close();
    handle = null;
    await rename(tempPath, outputPath);
  } finally {
    if (handle) await handle.close().catch(() => {});
    await unlink(tempPath).catch(() => {});
  }
}

async function main() {
  const cli = parseCli(process.argv.slice(2));
  if (cli.help) {
    process.stdout.write(HELP);
    return;
  }
  if (cli.printParityInput) {
    printParityInput();
    return;
  }

  const invocationCwd = process.cwd();
  const outputPath = path.resolve(invocationCwd, cli.output);
  const { raw, sourceLabel } = await readInput(cli.input, invocationCwd);
  const spec = parseInputSpec(raw);
  if (cli.input !== '-' && path.resolve(invocationCwd, cli.input) === outputPath) {
    throw new Error('Input and output paths must be different');
  }

  process.chdir(PROJECT_ROOT);
  progress(`mode=${spec.mode} requests=${spec.requests.length}`);
  const metadata = await collectRuntimeMetadata();
  const runtime = await createRuntime(spec.mode, metadata);

  let results;
  if (spec.mode === 'embeddings') {
    results = await runEmbeddings(spec.requests, runtime);
  } else if (spec.mode === 'palettebrain') {
    results = await runPaletteBrain(spec.requests, runtime);
  } else {
    results = await runLegacy(spec.requests, runtime);
  }

  const output = {
    schemaVersion: 1,
    harnessVersion: HARNESS_VERSION,
    mode: spec.mode,
    corpus: spec.corpus,
    fixture: spec.fixture,
    generatedAt: new Date().toISOString(),
    input: {
      source: sourceLabel,
      requestCount: spec.requests.length,
    },
    runtime: metadata.record,
    results,
  };
  await atomicWriteJson(outputPath, output);
  progress(`wrote ${results.length} result(s) to ${outputPath}`);
}

main().catch((error) => {
  const detail = error instanceof Error ? error.message : String(error);
  process.stderr.write(`[browser-runtime] ERROR: ${detail}\n`);
  process.exitCode = 1;
});
