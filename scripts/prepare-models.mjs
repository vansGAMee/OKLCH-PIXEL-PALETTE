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
const manifestPath = path.join(process.cwd(), 'public/models/palettebrain-v2.manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const expectedSha256 = manifest?.textEncoder?.sha256;
const declaredBytes = manifest?.textEncoder?.bytes;
if (!/^[a-f0-9]{64}$/.test(expectedSha256) || !Number.isSafeInteger(declaredBytes) || declaredBytes <= 0) {
  throw new Error('PaletteBrain manifest has an invalid textEncoder hash/size contract');
}

function sha256(data) {
  return createHash('sha256').update(data).digest('hex');
}

if (fs.existsSync(partA) && fs.existsSync(partB)) {
  const statA = fs.statSync(partA);
  const statB = fs.statSync(partB);
  const expectedSize = statA.size + statB.size;
  if (expectedSize !== declaredBytes) {
    throw new Error(`E5 chunk size ${expectedSize} does not match manifest ${declaredBytes}`);
  }

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

if (!fs.existsSync(targetFile)) {
  throw new Error('Assembled E5 model is missing after prepare:models');
}
const finalData = fs.readFileSync(targetFile);
if (finalData.length !== declaredBytes || sha256(finalData) !== expectedSha256) {
  throw new Error('Assembled E5 artifact does not match the PaletteBrain manifest');
}
