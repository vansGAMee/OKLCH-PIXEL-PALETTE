/**
 * prepare-models.mjs
 * Reassembles model chunks if needed before build/dev.
 */
import fs from 'fs';
import path from 'path';
import { createHash } from 'crypto';

const modelDir = path.join(process.cwd(), 'public/models/multilingual-e5-small/onnx');
const chunkDir = path.join(process.cwd(), 'model-parts/multilingual-e5-small/onnx');
const targetFile = path.join(modelDir, 'model_quantized.onnx');
const partA = path.join(chunkDir, 'model_quantized.onnx.part_aa');
const partB = path.join(chunkDir, 'model_quantized.onnx.part_ab');
const expectedSha256 = 'f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193';

function sha256(data) {
  return createHash('sha256').update(data).digest('hex');
}

if (fs.existsSync(partA) && fs.existsSync(partB)) {
  const statA = fs.statSync(partA);
  const statB = fs.statSync(partB);
  const expectedSize = statA.size + statB.size;

  let needsAssembly = true;
  if (fs.existsSync(targetFile)) {
    const curStat = fs.statSync(targetFile);
    if (curStat.size === expectedSize) {
      needsAssembly = sha256(fs.readFileSync(targetFile)) !== expectedSha256;
    }
  }

  if (needsAssembly) {
    console.log('Assembling multilingual-e5-small model from chunks...');
    const dataA = fs.readFileSync(partA);
    const dataB = fs.readFileSync(partB);
    const combined = Buffer.concat([dataA, dataB]);
    const assembledSha256 = sha256(combined);
    if (assembledSha256 !== expectedSha256) {
      throw new Error(`Assembled E5 artifact SHA-256 mismatch: ${assembledSha256}`);
    }
    const temporaryFile = `${targetFile}.tmp-${process.pid}`;
    fs.writeFileSync(temporaryFile, combined);
    fs.renameSync(temporaryFile, targetFile);
    console.log(`Assembled model (${combined.length} bytes) successfully!`);
  }
}
