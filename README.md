<div align="center">

# 🎨 OKLCH Pixel Palette Studio

**A deterministic color theory engine for generating expressively balanced 4-color pixel art palettes.**

[![Next.js](https://img.shields.io/badge/Next.js-16.3-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=for-the-badge&logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?style=for-the-badge&logo=typescript)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?style=for-the-badge&logo=tailwindcss)](https://tailwindcss.com/)
[![Motion](https://img.shields.io/badge/Motion-React-purple?style=for-the-badge&logo=framer)](https://motion.dev/)
[![Tests](https://img.shields.io/badge/Vitest-13%2F13_Passing-brightgreen?style=for-the-badge&logo=vitest)](https://vitest.dev/)

[**Live Demo**](http://localhost:3001) &bull; [**Deploy to Vercel**](https://vercel.com/new) &bull; [**Report Bug**](https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE/issues)

</div>
<img width="800" height="450" alt="pixel-palette-3f213a" src="https://github.com/user-attachments/assets/8d0d942f-e336-4502-9a9b-b3aa7337fe44" />

---

## 🌟 Overview

**OKLCH Pixel Palette Studio** is a specialized color generation workstation engineered specifically for **4-color pixel art**. 

Unlike random palette generators or basic RGB/HSL tweaks, this application uses **OKLCH perceived color space** and **OKLab Euclidean Distance ($\Delta E_{OK}$)** to construct expressively balanced 4-step color ramps containing:

1. **Shadow** — A cold-shifted, low-lightness base shadow.
2. **Base** — The user's exact, 100% preserved primary color.
3. **Highlight** — A warm-shifted, bright tint.
4. **Accent** — A harmoniously calculated contrast color derived through color theory scoring algorithms.

---

## ✨ Key Features

- **🎯 Perceived OKLCH Mathematics**: All computations executed in perceived lightness ($L$), chroma ($C$), and hue angle ($H^\circ$) space.
- **🛡️ sRGB Gamut Mapping**: Binary search gamut fitting algorithm guarantees zero channel clipping or dirty color artifacts in web browsers.
- **📊 Bklit UI Lightness Ladder**: Interactive 4-column chart demonstrating the lightness hierarchy step progression with rich metric tooltips.
- **👾 Dynamic Pixel Art Preview**: Crisp vector SVG rendering with 4-color index swapping across multiple selectable sprites (*Magic Potion, Crystal Gem, Knight Shield, Retro Hero*).
- **⚡ React 19 Concurrent Performance**: Powered by `useDeferredValue` for silky smooth 60–120 FPS dragging during live color selection.
- **🎲 Seeded Deterministic Variations**: Generates consistent variations within strict chromatic bounds based on a seed number.
- **📥 One-Click PNG Export**: Render high-resolution 800x450 PNG palette swatch cards directly from the browser.
- **💾 Auto-Save State**: Automatic `localStorage` persistence for color inputs, harmony choices, and seed states.

---

## 📐 Color Theory Engine Specification

```
                          ┌───────────────────────────┐
                          │    User Input Base Color  │ (Preserved 100%)
                          └─────────────┬─────────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             ▼                          ▼                          ▼
   ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
   │  Shadow Engine   │       │ Highlight Engine │       │  Accent Engine   │
   │  Cold Shift ~265°│       │ Warm Shift ~90°  │       │ Delta E OK Score │
   └─────────┬────────┘       └─────────┬────────┘       └─────────┬────────┘
             │                          │                          │
             └──────────────────────────┼──────────────────────────┘
                                        ▼
                          ┌───────────────────────────┐
                          │ sRGB Binary Gamut Mapping │
                          └─────────────┬─────────────┘
                                        ▼
                          ┌───────────────────────────┐
                          │ Verified 4-Color Palette  │
                          └───────────────────────────┘
```

### 1. Base Color
- **Rule**: $Base_{HEX}$ remains **100% exact and untouched**.

### 2. Shadow Generation
- **Lightness**: $L_{shadow} = \text{clamp}(L_{base} - 0.22, 0.04, 0.72)$
- **Chroma**: $C_{shadow} = \text{clamp}(C_{base} \cdot 0.9, 0.025, 0.22)$
- **Hue Shift**: Smooth 12–24° shift along the shortest path toward cold blue-violet (~265°).

### 3. Highlight Generation
- **Lightness**: $L_{highlight} = \text{clamp}(L_{base} + 0.22, 0.28, 0.995)$
- **Chroma**: $C_{highlight} = \text{clamp}(C_{base} \cdot 0.72, 0.015, 0.18)$
- **Hue Shift**: Smooth 8–18° shift along the shortest path toward warm yellow (~90°).

### 4. Accent Generation
Calculated using candidate evaluation across 3 harmony modes:
- **Split Complementary**: $H_{base} + 150^\circ$ or $H_{base} + 210^\circ$
- **Complementary**: $H_{base} + 180^\circ$
- **Analogous**: $H_{base} - 30^\circ$ or $H_{base} + 30^\circ$

**Scoring Function**: Evaluates candidates based on:
$$\text{Score} = 3.0 \cdot \Delta E_{min} + 2.0 \cdot |L_{accent} - L_{base}| + 1.5 \cdot \text{ChromaRetention}$$

---

## 🛠️ Project Structure

```
.
├── src/
│   ├── app/
│   │   ├── globals.css         # Styling system & dark aesthetic tokens
│   │   ├── layout.tsx          # Root layout
│   │   └── page.tsx            # Main Studio workstation
│   ├── components/
│   │   ├── charts/
│   │   │   └── BklitLightnessChart.tsx  # Bklit UI interactive chart
│   │   ├── controls/
│   │   │   ├── ActionToolbar.tsx        # Variations, Reset & PNG Export
│   │   │   ├── ColorPicker.tsx          # HEX input & native picker
│   │   │   └── HarmonySelector.tsx      # Harmony mode selector
│   │   ├── palette/
│   │   │   ├── ColorCard.tsx            # Swatch card with OKLCH metrics
│   │   │   └── PaletteGrid.tsx          # Motion layout container
│   │   └── preview/
│   │       └── PixelPreview.tsx         # Vector SVG pixel art scene renderer
│   ├── lib/
│   │   └── color/
│   │       ├── __tests__/      # Automated Vitest test suite
│   │       ├── conversions.ts   # HEX <-> OKLCH conversions
│   │       ├── exportPalettePng.ts # Canvas PNG export renderer
│   │       ├── gamut.ts         # sRGB binary search gamut mapping
│   │       ├── generator.ts     # Main 4-color palette engine
│   │       ├── harmony.ts       # Accent candidate scoring
│   │       ├── seed.ts          # Mulberry32 PRNG generator
│   │       └── validation.ts    # Delta E OK & rule verification
│   └── types/
│       └── palette.ts          # TypeScript type definitions
└── package.json
```

---

## 🚀 Getting Started

### Prerequisites

- Node.js 18.0 or higher
- npm 9.0 or higher

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE.git
   cd OKLCH-PIXEL-PALETTE
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start development server**:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🧪 Running Unit Tests

Automated tests cover all primary, secondary, grayscale, dark (`#121212`), bright (`#f7f7f7`), and seed determinism scenarios:

```bash
npx vitest run
```

```
 ✓ src/lib/color/__tests__/generator.test.ts (13 tests)
   ✓ Color Palette Generator Engine (13)
     ✓ generates valid palette for #ff0000 without throwing or NaN
     ✓ generates valid palette for #00ff00 without throwing or NaN
     ✓ generates valid palette for #0000ff without throwing or NaN
     ✓ generates valid palette for #f2c94c without throwing or NaN
     ✓ generates valid palette for #121212 without throwing or NaN
     ✓ generates valid palette for #f7f7f7 without throwing or NaN
     ✓ generates valid palette for #808080 without throwing or NaN
     ✓ generates valid palette for #5b21b6 without throwing or NaN
     ✓ guarantees deterministic output for identical seeds
     ✓ handles dark base #121212 without producing 4 almost black colors
     ✓ handles bright base #f7f7f7 without producing 4 almost white colors
     ✓ handles gray base #808080 properly with colorful accent
     ✓ provides different variations with different seeds
```

---

## 🚀 Deployment

### Deploy to Vercel

The application is fully static and zero-config ready for Vercel deployment:

1. Push your changes to GitHub.
2. Import the project into [Vercel](https://vercel.com/new).
3. Click **Deploy**.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
