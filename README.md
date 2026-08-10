# OKLCH Pixel Palette Studio 🎨

[![Live Demo](https://img.shields.io/badge/Live%20Demo-oklch--pixel--palette.vercel.app-7c3aed?style=for-the-badge&logo=vercel)](https://oklch-pixel-palette.vercel.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?style=for-the-badge&logo=typescript)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-v4-38bdf8?style=for-the-badge&logo=tailwindcss)](https://tailwindcss.com/)

A professional, color-theory-driven web application for generating expressive **4-color pixel art palettes** (Shadow, Base, Highlight, Accent) in perceived-uniform **OKLCH** color space with sRGB gamut enforcement.

🔗 **Live Production Demo**: [](oklchpalette.ru)

---

## 🌟 Highlights & Features

- **Exact Base Preservation**: The chosen Base color is preserved **100% untouched** (never forced through lossy gamut fitting). `oklchToHex(palette.base.oklch)` is strictly equal to the input HEX.
- **Physical OKLCH Gamut Mapping**: Fits generated Shadow, Highlight, and Accent colors into sRGB space via binary search on Chroma ($C$) while preserving Lightness ($L \in [0, 1]$) and Hue ($H$).
- **Color Theory Harmonies**:
  - **Split-Complementary**: Base hue + two adjacent accent hues offset by 150° and 210°.
  - **Complementary**: High-contrast accent hue offset by 180°.
  - **Analogous**: Smooth harmonious accent hues offset by ±30°.
- **Deterministic Boundary Modes**:
  - **Black Base Mode** ($base.l \le 0.16$, `#000000`, `#010101`): Preserves exact dark base. Enforces distinct, vibrant Highlight ($L \ge 0.20$) and Accent ($L \ge 0.35$) colors without requiring negative shadow lightness.
  - **White Base Mode** ($base.l \ge 0.97$, `#ffffff`, `#fefefe`, `#f7f7f7`): Preserves exact light base. Enforces deep Shadow ($L \le 0.80$) and Accent ($L \le 0.65$) colors without requiring highlight lightness $> 1.0$.
- **Real Bklit UI BarChart Component**: Directly integrates the official `@bklit/bar-chart` registry component (`visx` + `motion/react`) for displaying OKLCH Lightness metrics with interactive tooltips displaying Role, HEX, L, C, and H (`neutral` for grays).
- **Interactive Motion & Accessibility**: Powered by `motion/react` with full `prefers-reduced-motion` compliance. Color cards double as accessible copy buttons (`role="button"`, `tabIndex={0}`, keyboard `Enter`/`Space` handlers) with animated feedback.
- **PNG Export & State Persistence**: Instantly export downloadable 4-color palette PNG swatches; studio state (HEX input, harmony mode, seed variation) automatically persists to `localStorage`.

---

## 🏗 Tech Stack

- **Framework**: Next.js 16 (App Router, React 19)
- **Language**: TypeScript 5
- **Color Engine**: OKLCH / OKLab via `culori`
- **Styling**: Tailwind CSS v4 & Glassmorphism design tokens
- **Components**: shadcn/ui & Bklit UI (`@bklit/bar-chart`)
- **Animation**: Motion for React (`motion/react`)
- **Testing**: Vitest (Automated unit & mass integration test suite)

---

## 🚀 Quick Start & Installation

```bash
# Clone the repository
git clone https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE.git
cd OKLCH-PIXEL-PALETTE

# Install dependencies
npm install

# Start local development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the application.

---

## 🛠 Available Scripts

In the project directory, you can run:

| Command | Description |
| :--- | :--- |
| `npm run dev` | Runs the Next.js development server on `http://localhost:3000` |
| `npm run lint` | Runs ESLint checks across project source files |
| `npm run typecheck` | Runs TypeScript compiler diagnostics (`tsc --noEmit`) |
| `npm run test` | Runs the Vitest test suite (`Run npm test to see the current test count.`) |
| `npm run build` | Builds the production bundle for deployment |
| `npm run check` | Runs full quality control chain: `lint` + `typecheck` + `test` + `build` |

---

## 🧪 Testing

Run `npm test` to see the current test count. The test suite includes:
- Base preservation & reverse conversion checks (`oklchToHex(palette.base.oklch) === base.hex`)
- Mandatory color test suite (`#000000`, `#010101`, `#121212`, `#808080`, `#f7f7f7`, `#fefefe`, `#ffffff`, `#ff0000`, `#00ff00`, `#0000ff`, `#f2c94c`, `#5b21b6`)
- Deterministic mass test across 1,000+ palette combinations without `Math.random()`

---

## 📂 Project Structure

```
.
├── src/
│   ├── app/                  # Next.js 16 App Router pages & globals
│   ├── components/
│   │   ├── charts/           # Bklit UI BarChart registry components & adapter
│   │   ├── controls/         # ColorPicker, HarmonySelector, ActionToolbar
│   │   ├── palette/          # ColorCard, PaletteGrid
│   │   ├── preview/          # PixelPreview interactive SVG scene
│   │   └── ui/               # shadcn/ui primitive components
│   ├── lib/
│   │   └── color/            # OKLCH math engine (conversions, gamut, generator, validation)
│   │       └── __tests__/    # Vitest automated test suite
│   └── types/                # Palette & color TypeScript interface definitions
├── docs/
│   └── ui-ux-audit.md        # Detailed UI/UX Pro Max compliance report
├── LICENSE                   # MIT License
├── package.json
└── README.md
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
