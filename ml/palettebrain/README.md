# PaletteBrain 2 decoder pipeline

This directory contains an experimental custom neural **complete-palette
decoder**. It is deliberately separate from the existing `ml/train.py`,
`ml/evaluate.py`, and `ml/export_onnx.py` intent baseline.

## Honest status

- The model architecture, deterministic data preparation, training,
  evaluation, export, latency benchmark, and feedback-pair conversion are
  implemented.
- A full 20-epoch synthetic-baseline export is committed at
  `public/models/palettebrain-v2-decoder.onnx`. It is a real trained artifact,
  not random or smoke weights, but its manifest deliberately marks it
  `productionReady: false` and `synthetic_baseline_only`.
- The scripts refuse to export when a checkpoint is absent; random weights are
  never shipped.
- The prepared targets are a **deterministic synthetic baseline** expanded from
  the scalar labels in `ml/dataset_embeddings.npz`. They validate tensor shapes,
  native counts, seed variation, locking, loss, and export plumbing. They are
  not human-authored full palettes and are not evidence of production quality.
- There is no critic. A critic should be added only after a human/full-palette
  dataset makes the base decoder useful and a measured ranking experiment
  shows a quality gain worth its latency.
- `benchmark_prompts.v1.json` is a versioned prompt/coverage specification. It
  has no human ratings or reference palettes yet, so it cannot support a claim
  of semantic quality or superiority over another palette source.

## Decoder contract

`PaletteDecoder` has nine learned palette query slots and two small
self-attention blocks. Every slot is conditioned on:

- cached `text_embedding`: `[B, 384]`
- native `count_mask`: `[B, 9]`
- deterministic `seed_noise`: `[B, 9, 4]`
- `locked_mask`: `[B, 9]`
- physical `locked_colors`: `[B, 9, 4]` as `[L, C, sin(hue), cos(hue)]`

The output `palette` is `[B, 9, 5]`:

```text
[L_logit, C_logit, sin(hue), cos(hue), importance]
```

Decode with `L = 0.07 + 0.86 * sigmoid(L_logit)` and
`C = sigmoid(C_logit) * maxSrgbChromaAt(L, H) * 0.92`. Data preparation mirrors
the runtime's Culori-derived OKLCH conversion, gamut tolerance, and 20-iteration
chroma search. Active slots are the first requested 2..9 mask entries; inactive
slots are exactly zero. Physical locked colors condition the self-attention so
free slots can adapt around them. Because inputs and outputs use different L/C
representations, the browser runtime restores original locked OKLCH objects after
decode as the exact immutability guard; training also teaches locked-slot
reconstruction as an auxiliary objective.

The encoder is intentionally outside this package. The decoder API accepts the
cached 384-d representation so count changes, seed regeneration, and lock
changes do not require re-encoding text.

## Commands

From the repository root, install the isolated ML requirements and prepare the
synthetic plumbing dataset:

```powershell
python -m pip install -r ml/palettebrain/requirements.txt
python ml/palettebrain/prepare_data.py
```

A small shape/loss/checkpoint smoke training run is explicit and remains marked
non-production:

```powershell
python ml/palettebrain/train_decoder.py --smoke
python ml/palettebrain/evaluate.py --split val --max-samples 64
```

For a real synthetic-baseline training run:

```powershell
python ml/palettebrain/train_decoder.py --epochs 20
python ml/palettebrain/evaluate.py --split test --output ml/palettebrain/checkpoints/test-metrics.json
```

Export only a trained checkpoint; export performs ONNX validation, PyTorch/ORT
  parity, finite/inactive output checks, SHA-256, and size checks:

```powershell
python ml/palettebrain/export_onnx.py
```

Measure the decoder-only cached-embedding path. Results are written only when
the command really runs; there are no fabricated numbers in the repository:

```powershell
python ml/palettebrain/benchmark.py --onnx ml/palettebrain/artifacts/palettebrain-decoder-v1.onnx --output ml/palettebrain/artifacts/decoder-benchmark.json
```

Validate the prompt benchmark without Torch:

```powershell
python ml/palettebrain/evaluate.py --validate-benchmark-only
```

Convert explicit candidate selections or explicit `goodPalette`/`badPalette`
events into critic-ready JSONL pairs:

```powershell
python ml/palettebrain/prepare_feedback.py feedback.jsonl good-bad-pairs.jsonl
```

Single likes/dislikes without a compared palette are skipped because they do
not define an honest pair. Raw prompts remain excluded unless the command uses
`--include-raw-prompts` **and** the individual event has
`rawPromptConsent: true`.

## Metrics

Evaluation reports native exact-count behavior, inactive-slot zeroing,
near-duplicate rate, decoded L/C and hue error, sRGB gamut validity using the
same conversion/search as the browser runtime, and learned lock reconstruction.
The browser remains the authority for exact immutable locks because it restores
the original physical values after model-aware completion.

`benchmark.py` separately measures warm generation, cached-embedding seed
regeneration, count changes, and locked regeneration. It excludes encoder load,
text encoding, worker messaging, and color post-processing and records those
exclusions beside every real result.

Version-controlled results from the shipped synthetic baseline are in
`reports/palettebrain-v2-synthetic-evaluation.json` and
`reports/palettebrain-v2-synthetic-benchmark.json`.

## Data and license note

`ml/dataset_embeddings.npz` is generated by the repository's
`generate_semantic_dataset.py` from the repository-owned `concepts_v2.json` and
the local MIT-licensed multilingual E5 encoder. The committed decoder contains
no PAT/Text2Colors, scraped LoSpec data, image-generated palettes, or other new
third-party dataset. Before production training, add appropriately licensed
human text-to-complete-palette data for counts 2..9, RU/EN contextual contrasts,
abstractions, and lock-completion examples, then record its license and human
evaluation methodology.
