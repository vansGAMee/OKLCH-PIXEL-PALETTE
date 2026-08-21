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
