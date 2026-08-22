/**
 * prepare-models.mjs
 * Reassembles model chunks if needed before build/dev.
 */
import fs from 'fs';
import path from 'path';

const modelDir = path.join(process.cwd(), 'public/models/multilingual-e5-small/onnx');
const targetFile = path.join(modelDir, 'model_quantized.onnx');
const partA = path.join(modelDir, 'model_quantized.onnx.part_aa');
const partB = path.join(modelDir, 'model_quantized.onnx.part_ab');

if (fs.existsSync(partA) && fs.existsSync(partB)) {
  const statA = fs.statSync(partA);
  const statB = fs.statSync(partB);
  const expectedSize = statA.size + statB.size;

  let needsAssembly = true;
  if (fs.existsSync(targetFile)) {
    const curStat = fs.statSync(targetFile);
    if (curStat.size === expectedSize) {
      needsAssembly = false;
    }
  }

  if (needsAssembly) {
    console.log('Assembling multilingual-e5-small model from chunks...');
    const dataA = fs.readFileSync(partA);
    const dataB = fs.readFileSync(partB);
    const combined = Buffer.concat([dataA, dataB]);
    fs.writeFileSync(targetFile, combined);
    console.log(`Assembled model (${combined.length} bytes) successfully!`);
  }
}
