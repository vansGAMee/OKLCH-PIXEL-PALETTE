<div align="center">
  <h1>🎨 OKLCH Pixel Palette Studio</h1>
  <h3>A color-theory-driven palette generator for pixel art</h3>

  <p>
    Generate expressive <strong>4-color pixel-art palettes</strong> in perceptually uniform
    <strong>OKLCH</strong> color space.
  </p>

  <p>
    <a href="https://oklchpalette.ru">
      <img src="https://img.shields.io/badge/LIVE_DEMO-OKLCHPALETTE.RU-111111?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Demo">
    </a>
    <img src="https://img.shields.io/badge/NEXT.JS-16-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js 16">
    <img src="https://img.shields.io/badge/TYPESCRIPT-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript 5">
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/LICENSE-MIT-F5C518?style=for-the-badge" alt="MIT License">
    </a>
  </p>

  <p><strong>Shadow · Base · Highlight · Accent</strong></p>

  <p>
    <a href="https://oklchpalette.ru"><strong>🌐 Open the app</strong></a>
    &nbsp;·&nbsp;
    <a href="https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE"><strong>⭐ Star the repo</strong></a>
  </p>
</div>

---

The generator keeps your selected **Base** color intact, builds the remaining colors with deterministic color-theory harmonies, and maps generated colors into the sRGB gamut.

## ✨ Features

### 🎨 OKLCH palette generation

Generate compact 4-color palettes designed for pixel art using OKLCH / OKLab color math.

The selected **Base** color is preserved exactly:

```ts
oklchToHex(palette.base.oklch) === inputHex
```

Generated Shadow, Highlight, and Accent colors are fitted into the sRGB gamut by reducing chroma while preserving lightness and hue as far as possible.

### 🌈 Color harmony modes

Choose between several deterministic harmony strategies:

- **Split Complementary** — accent hues at `+150°` and `+210°`
- **Complementary** — accent hue at `+180°`
- **Analogous** — neighboring hues around `±30°`

### ⚫ Dark-color handling

Very dark bases such as:

```text
#000000
#010101
#121212
```

use a dedicated boundary mode so the palette still produces visually distinct Highlight and Accent colors without requiring impossible negative lightness values.

### ⚪ Light-color handling

Very light bases such as:

```text
#ffffff
#fefefe
#f7f7f7
```

use a corresponding light boundary mode to produce useful Shadow and Accent colors without pushing highlight lightness beyond the valid OKLCH range.

### 📊 OKLCH metrics

The interface includes an interactive bar chart for comparing palette lightness values.

Tooltips display:

- palette role
- HEX
- OKLCH Lightness (`L`)
- Chroma (`C`)
- Hue (`H`)

Neutral colors are handled separately when a meaningful hue is unavailable.

### 📋 One-click color copying

Palette cards act as accessible copy controls with:

- mouse interaction
- keyboard `Enter`
- keyboard `Space`
- animated feedback
- `prefers-reduced-motion` support

### 💾 CSS and artist-file export

Export production-ready CSS custom properties with HEX fallbacks and native OKLCH overrides. The same menu also downloads PNG, GIMP GPL, JASC PAL, HEX, TXT, and structured JSON files.

### 💾 Persistent studio state

The app stores the current:

- HEX input
- harmony mode
- variation seed

in `localStorage`, so the editor restores your previous state after a reload.

---

## 🧰 Tech Stack

| Area | Technology |
| --- | --- |
| Framework | Next.js 16 |
| UI | React 19 |
| Language | TypeScript 5 |
| Color engine | OKLCH / OKLab with `culori` |
| Styling | Tailwind CSS v4 |
| Components | shadcn/ui, Bklit UI |
| Animation | Motion for React |
| Testing | Vitest |

---

## 🤖 PaletteBrain Candidate 11 — technical handoff and honest status

> **Status as of 2026-08-30: experimental; do not treat as production-ready.**
>
> The browser manifest currently says `productionReady: true`. That flag is stale
> and **must not** be used as evidence of semantic quality. The real frozen
> semantic report records a failing model. Candidate 11 may still be useful for
> engineering work (local inference, deterministic generation, locks, ONNX
> export, and runtime parity), but it is not reliable enough to promise that a
> text prompt produces an appropriate palette.

This section is deliberately more detailed than the product description above.
It is the handoff for a developer returning to the project or evaluating the
model work for the first time.

### What Candidate 11 is

Candidate 11 is an in-browser text-to-palette experiment. It is independent of
the deterministic 4-colour OKLCH generator described above:

1. The browser normalizes the prompt and obtains a 384-dimensional embedding
   with the local ONNX version of `intfloat/multilingual-e5-small`.
2. The browser derives a deterministic unsigned 32-bit seed from the prompt
   unless the caller supplies one. The Python training code and TypeScript
   runtime share the Mulberry32 + Box-Muller seed-noise contract.
3. A PyTorch `PaletteDecoder` predicts up to nine palette slots in an internal
   OKLCH-like representation. The selected count activates the requested
   prefix of slots; locked colours are passed as conditioning and restored by
   the runtime after decoding.
4. `paletteAdapter.ts` converts the decoder output to displayable sRGB/HEX and
   the UI applies it to the palette studio.

The deployed decoder is exported to ONNX. Its public contract is:

| Input/output | Shape | Meaning |
| --- | --- | --- |
| `text_embedding` | `[B, 384]` | L2-normalized multilingual E5 prompt embedding |
| `count_mask` | `[B, 9]` | Active palette slots (between 2 and 9) |
| `seed_noise` | `[B, 9, 4]` | Deterministic variation noise |
| `locked_mask` | `[B, 9]` | Which supplied colour slots are locked |
| `locked_colors` | `[B, 9, 4]` | Locked-colour conditioning values |
| `palette` | `[B, 9, 5]` | Predicted palette representation; inactive slots are zero |

The relevant runtime files are:

- `src/lib/ai-palette/inference.ts` — browser model/encoder loading, integrity
  checks, request validation, and ONNX invocation.
- `src/lib/ai-palette/paletteAdapter.ts` — conversion of model output to
  application colours.
- `src/components/controls/AiPaletteInput.tsx` — the UI entry point.
- `public/models/palettebrain-v2.manifest.json` — deployed artifact metadata.
- `ml/palettebrain/model.py` — the PyTorch decoder used for training/export.

### Model design

The decoder has two conditioning paths:

- **Inherited text path.** The E5 embedding is projected into each palette slot
  through the pre-existing decoder.
- **Candidate 11 visual bridge.** `VisualPaletteBridge` predicts a colour-histogram
  prior, latent style token, and four visual colour tokens from the same text
  embedding. `PaletteVisualCrossAttention` supplies slot-specific refinement.

Stage A trains the bridge and cross-attention while preserving the inherited
decoder. The intended optimizer contract is important: inherited `bridge.*`
parameters use the inherited learning rate and remain trainable; only
`visual_cross_attention.*` uses the new-parameter learning rate. Stage B uses
replay and BASE-prior/teacher distillation to reduce regressions.

This architecture has engineering advantages: it is compact (the deployed
manifest records 715,851 parameters), deterministic for a fixed request, and
works in the browser without a server inference API. Its central weakness is
that a learned visual prior is not, by itself, a hard semantic colour
constraint. The final decoder can still favour the inherited colour tendency.

### Data contract and artifacts

Candidate 11 uses full-photo palette supervision. For a semantically relevant
photograph, the **entire-image extracted palette** is a valid target; the
pipeline must not manufacture a hand-authored `concept → expected colour`
label or reject a relevant photo merely because its palette does not match a
stereotype. SigLIP/text-image relevance decides whether an image is accepted.
Palette statistics may be retained for diagnostic diversity analysis only.

The corrected, versioned artifacts are preserved alongside older artifacts:

| Artifact | Location | Known state |
| --- | --- | --- |
| Recovered full-photo source | `ml/palettebrain/data/palettebrain_c11_recovered_source_corrected_contract_v1.npz` | 2,811 images / 11,244 training rows |
| Training dataset | `ml/palettebrain/data/palettebrain_c11_corrected_contract_v1.npz` | 11,244 rows; recorded leakage audit: 0/0/0 |
| BASE checkpoint | `ml/palettebrain/checkpoints/candidate-11-base.pt` | Protected reference checkpoint |
| Stage A checkpoint | `ml/palettebrain/checkpoints/candidate-11-stage-a-corrected-contract-v2-best.pt` | Resumable training artifact, not proof of release quality |
| Stage B checkpoint | `ml/palettebrain/checkpoints/candidate-11-stage-b-corrected-contract-v2-best.pt` | Epoch 18 candidate used for the exported model |
| Exported ONNX decoder | `public/models/palettebrain-v4-candidate11-corrected-contract-v2.onnx` | Runtime/parity artifact, not semantic approval |

Do not delete raw images, caches, old source archives, or checkpoints while
working on this model. Version a new source/dataset/checkpoint instead. The
intended release runner is resumable and should reuse valid artifacts:

```powershell
ml\.venv\Scripts\python.exe -u ml\palettebrain\run_candidate11_release.py --device cuda --resume
```

It deliberately refuses to run on the production branch. It records phase
state under `ml/palettebrain/reports/`, checks reusable artifacts, and is
supposed to avoid accepting known-bad Stage A checkpoints as valid resume
points. Treat the runner as orchestration, not as the semantic authority: read
the generated frozen evaluation report before publishing a model.

### What was fixed in the pipeline

These changes improve correctness, reproducibility, or resumability. They do
**not** prove that Candidate 11 understands arbitrary colour-language prompts.

- The full-photo data contract was corrected: retrieval accepts relevant images
  through text-image semantics rather than palette-family pass/fail. Retrieval
  no longer ranks providers, routes, images, or queries toward hand-authored
  expected colours.
- Existing raw/cache entries are reused; targeted acquisition is intended only
  for demonstrated coverage deficits. Old artifacts are versioned rather than
  overwritten.
- The Stage A optimizer grouping was corrected so inherited `bridge.*` no
  longer receives the new-module learning rate. `bridge.*` remains trainable;
  near-zero initialization of `visual_cross_attention.*` was preserved.
- Checkpoint saving was made safer on Windows: resumable `save_last` retries
  bounded transient `PermissionError` / WinError 5 around atomic replacement,
  without deleting the valid destination checkpoint first.
- Python/ONNX/browser parity, inactive-slot behaviour, deterministic seed
  behaviour, and browser runtime loading were exercised. These are engineering
  checks, not semantic-success checks.

### Known semantic failures (reproducible, unresolved)

The following are actual observed failures of the current Stage B/browser model,
not hypothetical risks:

| Prompt | Observed behaviour |
| --- | --- |
| `фисташковый` | pink/red/orange palette instead of a pistachio-like result |
| `лед` | first/dominant colour may be brown/red/orange rather than ice-like |
| `водичка` | pink/purple palette |
| `красный и синий` | mostly red/purple, with almost no blue |
| `киберпанк` | brown/pink/tan instead of a recognizably cyberpunk palette |

For the exact browser-compatible seeds, examples included:

```text
фисташковый       #DB8479 #CD535C #BB485D #E0647E #E2B7A7
красный и синий   #F98885 #DA294C #701A7C #96239B #C826A2
киберпанк         #6D4E49 #775148 #805448 #BB8E75 #B99A80
```

The frozen real-PyTorch report at
`ml/palettebrain/reports/candidate-11-semantic-v3.json` confirms the issue:

| Metric | Current recorded value | Interpretation |
| --- | ---: | --- |
| `semanticFamilyWin` | `0.06` | Failing; semantic family matching is very weak |
| `directEn` | `0.5714` | Partial English direct-control performance only |
| `directRu` | `1.0` | Not sufficient evidence of broad Russian semantics |
| `cleanMultiColor` | `0.2980` | Poor multi-colour generalization |
| `nearDuplicateRate` | `0.7020` | Excessively similar outputs |
| `basicConcepts` | `0.15` | Failing basic concept coverage |
| `weatherScenes` | `0.0` | Failing |
| `stylesMedia` | `0.0` | Failing |
| `compositions` | `0.0` | Failing |
| `realBrowserSemanticSmoke` | `false` | Browser semantic smoke fails |
| PyTorch/ONNX parity | `true` | Export agrees with native model; it does not make semantics correct |

The nearest examples in the recovered training dataset expose the main cause:
there is no direct supervision for `фисташковый`, `киберпанк`, or a red-and-blue
composition. E5 therefore retrieves unrelated photo concepts for those prompts.
For ice and water, the bridge prior changes with the prompt, but the final
decoder does not consistently turn that signal into a colour constraint. Stage B
distillation stabilizes the inherited decoder, which also preserves its weak
behaviour on these unseen/under-covered requests.

### Strengths and limitations

| Works reasonably as designed | Does not currently work reliably |
| --- | --- |
| Local/offline browser inference | General semantic text-to-palette generation |
| Deterministic result for prompt + seed | Direct named-colour control and colour combinations |
| Requested count and locked-colour plumbing | Styles and abstract concepts outside data coverage |
| PyTorch → ONNX → browser numerical parity | High palette diversity (`nearDuplicateRate` is high) |
| Full-photo palette targets without colour stereotypes | Treating `productionReady` or loss reduction as proof of quality |

### How to continue safely

Do not solve the failures with a hidden frontend dictionary or by changing the
frozen benchmark’s expected answers. That would make a few demonstrations look
better while violating the full-photo supervision contract and leaking test
knowledge into training.

The next legitimate experiment is substantial rather than a one-line fix:

1. Define data coverage targets for missing semantic regions (named colours,
   colour compositions, styles) without copying frozen benchmark prompts or
   answers into the training set.
2. Acquire/curate only genuinely relevant, licensed images for those proven
   gaps; preserve current raw data and write a new versioned source and dataset.
3. Improve the decoder/bridge objective so the predicted colour prior has a
   measurable, non-destructive effect on the final palette.
4. Add a regression suite containing independently authored prompts for this
   failure class, then run a one-epoch probe. The probe must improve semantic
   results without regressing BASE direct EN/RU controls.
5. Only if that probe passes, run Stage A, Stage B, frozen semantic evaluation,
   ONNX export, native/ONNX parity, browser validation, and final qualification.

On the recorded hardware, a full Stage A run took about 15.2 minutes and Stage
B about 10.1 minutes (roughly 25 minutes of training after a real fix), before
data preparation and release checks. Do not launch that work merely because
training loss falls or the manifest says `productionReady`.

### Planned next experiment: semantic and compositional supervision

This is the intended research direction, not a claim that it has already been
implemented or validated. The working hypothesis is that Candidate 11 can keep
its E5 → bridge → decoder → ONNX → browser architecture and its existing
full-photo source, but needs a second, more direct training signal.

The current supervision is predominantly:

```text
text → semantically relevant photograph → palette of the whole photograph
```

That is valuable for natural variation: a storm, water, or sunset should not
collapse to one fixed palette. It is insufficient on its own for direct colour
terms and compositions. A photograph of ice can contain sky, earth, reflections
and people; a cyberpunk photograph can contain skin, asphalt and interiors; and
`red and blue` requires that both conditions survive rather than being averaged
into purple or pink.

The proposed training mixture is therefore:

```text
full-photo palette supervision
        +
direct text ↔ palette supervision
        +
compositional text ↔ palette supervision
        +
contrastive / hard-negative palette loss
```

The first term keeps the natural diversity supplied by relevant photos. The
second should teach that a direct colour term has a dependable colour relation.
The third should preserve multiple requirements in a phrase. The fourth should
make an answer such as “red plus purple” demonstrably worse than “red plus
blue” when the prompt requires red and blue, rather than allowing a visually
safe average to minimize a broad reconstruction loss.

This is informed by, rather than copied from, two useful research directions:

- [Text2Colors (ECCV 2018)](https://openaccess.thecvf.com/content_ECCV_2018/html/Hyojin_Bahng_Coloring_with_Words_ECCV_2018_paper.html)
  studies text-to-palette learning with the PAT text/palette dataset, including
  direct colours and abstract concepts.
- [Generating Compositional Color Representations from Text (Adobe Research)](https://research.adobe.com/publication/generating-compositional-color-representations-from-text/)
  investigates compositional colour representations and contrastive ranking
  objectives for correct, near-miss, and incorrect colour combinations.

The PAT/Text2Colors dataset or other public data must **not** be incorporated
until its licence, provenance, redistribution terms, and fit for this product
have been independently checked. It may initially be useful only as an external
benchmark or format reference. Frozen release-benchmark prompts, answers, and
derived labels remain prohibited from training data.

#### Scope deliberately kept unchanged

The plan does **not** call for replacing E5, rebuilding the browser runtime,
switching to diffusion/GANs, deleting the 2,811 recovered photos, or replacing
the ONNX pipeline. It also explicitly rejects a hidden runtime rule such as:

```python
if "ice" in prompt:
    make_blue()
```

Such a rule would make a demo look better but would neither generalize nor
measure the model’s conditioning ability.

#### Data to add (versioned, separate from the recovered photos)

Build a small licensed semantic/compositional dataset rather than rebuilding
the existing 11,244 rows. Its initial size is an experiment, not a target:
roughly 1,000–5,000 rows may be enough for a probe if they are balanced and
well-provenanced. Candidate groups include:

```text
direct colours:       red, blue, green, cyan, …
colour variants:      pistachio, olive, mint, burgundy, …
nature/materials:     ice, water, blood, grass, sand, …
atmosphere/styles:    storm, sunset, fog, cyberpunk, …
compositions:         red and blue; black and gold; pink and cyan; …
```

For compositions, training should include known elements in combinations and
reserve different combinations for held-out evaluation. The purpose is to test
composition, not memorize a lookup table.

#### Objective to test

Keep the existing reconstruction/distribution objectives and BASE-prior
distillation, but add a weighted contrastive palette term with genuine hard
negatives. For a `red and blue` training item, examples such as red-only,
blue-only, red-plus-purple, and an unrelated pink/brown palette are candidate
near-misses. The exact sampling strategy, margin, and weights must be chosen
using a held-out set; they must not be tuned against frozen release answers.

The distillation weight also needs a controlled sweep. A teacher that is weak
on direct/compositional semantics should stabilize general behaviour, not veto a
stronger, independently sourced semantic target.

#### Evidence-first execution plan

```text
1. Create a small held-out semantic/compositional development benchmark.
   It must not overlap with training prompts or the frozen release benchmark.

2. Record the current C11 failure on that benchmark and the existing frozen
   semantic report, including semantic score, composition score and duplicates.

3. Build a new versioned supplemental dataset with provenance and licence audit.
   Preserve all existing sources, caches, and datasets unchanged.

4. Add the semantic/compositional and hard-negative loss behind an explicit
   training configuration; add focused regression tests for loss behaviour.

5. Run a 1–3 epoch probe. It passes only if semantic/compositional behaviour
   improves, near-duplicate rate decreases, and BASE direct EN/RU controls and
   engineering invariants do not regress.

6. If the probe fails, diagnose the first failing contract and iterate on that
   same focused test. Do not launch a 30-epoch run.

7. If the probe passes, run Stage A → Stage B → frozen evaluation → ONNX export
   → native/ONNX parity → browser validation → final qualification.
```

Only a successful final qualification can change the public readiness claim.
Until then, Candidate 11 remains an experimental local model with known semantic
failure modes.

---

## 🚀 Quick Start

Clone the repository:

```bash
git clone https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE.git
cd OKLCH-PIXEL-PALETTE
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Then open:

```text
http://localhost:3000
```

---

## 🛠 Available Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the local Next.js development server |
| `npm run lint` | Run ESLint |
| `npm run typecheck` | Run TypeScript diagnostics with `tsc --noEmit` |
| `npm run test` | Run the Vitest test suite |
| `npm run build` | Build the production bundle |
| `npm run check` | Run lint, typecheck, tests, and production build |

---

## 🧪 Testing

Run:

```bash
npm test
```

The test suite covers:

- exact base-color preservation
- OKLCH → HEX reverse-conversion checks
- dark and light boundary cases
- common RGB primaries
- neutral colors
- deterministic generation across 1,000+ palette combinations
- generation without `Math.random()`

Representative test colors include:

```text
#000000
#010101
#121212
#808080
#f7f7f7
#fefefe
#ffffff
#ff0000
#00ff00
#0000ff
#f2c94c
#5b21b6
```

---

## 📂 Project Structure

```text
.
├── src/
│   ├── app/
│   │   └── Next.js App Router pages and global styles
│   ├── components/
│   │   ├── charts/
│   │   │   └── OKLCH metric charts
│   │   ├── controls/
│   │   │   └── Color picker, harmony selector, toolbar
│   │   ├── palette/
│   │   │   └── Palette cards and palette grid
│   │   ├── preview/
│   │   │   └── Interactive pixel-art preview
│   │   └── ui/
│   │       └── UI primitives
│   ├── lib/
│   │   └── color/
│   │       ├── Color conversion and gamut logic
│   │       ├── Palette generator
│   │       ├── Validation
│   │       └── __tests__/
│   └── types/
│       └── Palette and color TypeScript types
├── docs/
├── public/
├── scripts/
├── supabase/
├── LICENSE
├── package.json
└── README.md
```

---

## 🎯 Why OKLCH?

Traditional RGB and HSL operations do not correspond well to how humans perceive differences in brightness and saturation.

OKLCH gives the palette generator separate controls for:

- **Lightness**
- **Chroma**
- **Hue**

This makes palette relationships more predictable while still exporting ordinary sRGB colors for the web and pixel-art tools.

---

## 👾 Use Cases

OKLCH Pixel Palette Studio is useful for:

- pixel artists
- game developers
- UI designers
- sprite artists
- palette exploration
- color-theory experiments
- Aseprite workflows

---

## 📄 License

Licensed under the [MIT License](LICENSE).
