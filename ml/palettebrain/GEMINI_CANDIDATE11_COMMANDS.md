# Candidate 11 repaired training commands

These commands continue Candidate 11. They never create Candidate 12 and never
set `productionReady=true` or assign a codename.

The current compact C11 archive fails provenance audit. Recover/build a
metadata-rich source archive first; do not silently treat the current archive
as licensed, source-group-safe image supervision.

## Preflight

```powershell
& 'ml\.venv\Scripts\python.exe' ml/palettebrain/validate_benchmarks.py
& 'ml\.venv\Scripts\python.exe' ml/palettebrain/build_c11_dataset.py --input ml/palettebrain/data/palettebrain_c11_recovered_source.npz --output ml/palettebrain/data/palettebrain_c11_repaired_v2.npz --report ml/palettebrain/reports/candidate-11-repaired-dataset-audit.json
```

## Stage A

```powershell
& 'ml\.venv\Scripts\python.exe' ml/palettebrain/train_candidate11.py --stage a --data ml/palettebrain/data/palettebrain_c11_repaired_v2.npz --initialize-from ml/palettebrain/checkpoints/candidate-11-best.pt --output ml/palettebrain/checkpoints/candidate-11-stage-a-best.pt --epochs 30 --batch-size 32 --new-lr 3e-4 --inherited-lr 2e-5 --seed 20260826 --device auto
```

## Stage A evaluation (must report `semanticFamilyWin >= 0.80`)

```powershell
& 'ml\.venv\Scripts\python.exe' ml/palettebrain/evaluate_semantic_v3.py --checkpoint ml/palettebrain/checkpoints/candidate-11-stage-a-best.pt --output ml/palettebrain/reports/candidate-11-stage-a-semantic-v3.json --device auto
```

If the gate fails, repair the same Candidate 11. Do not start Stage B.

## Stage B

```powershell
& 'ml\.venv\Scripts\python.exe' ml/palettebrain/train_candidate11.py --stage b --data ml/palettebrain/data/palettebrain_c11_repaired_v2.npz --replay-data ml/palettebrain/data/palettebrain_candidate3_direct8_v1.npz --initialize-from ml/palettebrain/checkpoints/candidate-11-stage-a-best.pt --stage-a-eval-report ml/palettebrain/reports/candidate-11-stage-a-semantic-v3.json --output ml/palettebrain/checkpoints/candidate-11-stage-b-best.pt --epochs 20 --batch-size 32 --new-lr 1e-4 --inherited-lr 2e-5 --seed 20260826 --device auto
```

## Export and full qualification

```powershell
& 'ml\.venv\Scripts\python.exe' ml/palettebrain/export_c11_onnx.py --checkpoint ml/palettebrain/checkpoints/candidate-11-stage-b-best.pt --output public/models/palettebrain-v4-candidate11-repaired.onnx --manifest public/models/palettebrain-v2.manifest.json
& 'ml\.venv\Scripts\python.exe' ml/palettebrain/evaluate_semantic_v3.py --checkpoint ml/palettebrain/checkpoints/candidate-11-stage-b-best.pt --output ml/palettebrain/reports/candidate-11-stage-b-semantic-v3.json --device auto
& 'ml\.venv\Scripts\python.exe' ml/palettebrain/qualify_candidate.py --evidence ml/palettebrain/reports/candidate-11-stage-b-semantic-v3.json --parity-report ml/palettebrain/reports/candidate-11-parity.json --manifest public/models/palettebrain-v2.manifest.json --output ml/palettebrain/reports/candidate-11-stage-b-qualification.json
```

The final qualification remains failed until the real Chromium semantic smoke
and raw ORT-Web parity evidence are regenerated for the repaired ONNX artifact.
