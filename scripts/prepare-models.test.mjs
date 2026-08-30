import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const scriptPath = path.join(path.dirname(fileURLToPath(import.meta.url)), 'prepare-models.mjs');

test('assembles the model when the clean checkout lacks the ONNX parent directory', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'prepare-models-'));
  const onnxDir = path.join(root, 'public/models/multilingual-e5-small/onnx');
  const chunkDir = path.join(root, 'model-parts/multilingual-e5-small/onnx');
  const model = Buffer.from('a complete test model');

  try {
    fs.mkdirSync(path.join(root, 'scripts'), { recursive: true });
    fs.mkdirSync(path.join(root, 'public/models'), { recursive: true });
    fs.mkdirSync(chunkDir, { recursive: true });
    fs.copyFileSync(scriptPath, path.join(root, 'scripts/prepare-models.mjs'));
    fs.writeFileSync(path.join(chunkDir, 'model_quantized.onnx.part_aa'), model.subarray(0, 7));
    fs.writeFileSync(path.join(chunkDir, 'model_quantized.onnx.part_ab'), model.subarray(7));
    fs.writeFileSync(
      path.join(root, 'public/models/palettebrain-v2.manifest.json'),
      JSON.stringify({
        textEncoder: {
          sha256: createHash('sha256').update(model).digest('hex'),
          bytes: model.length,
        },
      }),
    );

    execFileSync(process.execPath, ['scripts/prepare-models.mjs'], {
      cwd: root,
      stdio: 'pipe',
    });

    assert.deepEqual(fs.readFileSync(path.join(onnxDir, 'model_quantized.onnx')), model);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
