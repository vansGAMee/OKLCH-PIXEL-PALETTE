'use client';

import React, { useState, useEffect, useMemo, useDeferredValue } from 'react';
import Link from 'next/link';
import { HarmonyMode, Palette } from '@/types/palette';
import { generatePalette } from '@/lib/color/generator';
import { ColorPicker } from '@/components/controls/ColorPicker';
import { HarmonySelector } from '@/components/controls/HarmonySelector';
import { ActionToolbar } from '@/components/controls/ActionToolbar';
import { PaletteGrid } from '@/components/palette/PaletteGrid';
import { BklitLightnessChart } from '@/components/charts/BklitLightnessChart';
import { PixelPreview } from '@/components/preview/PixelPreview';
import { Sparkles, Palette as PaletteIcon, ShieldCheck, Terminal, Home } from 'lucide-react';

const STORAGE_KEY = 'pixel_palette_studio_state_v1';

const DEFAULT_HEX = '#5b21b6';
const DEFAULT_HARMONY: HarmonyMode = 'splitComplementary';
const DEFAULT_SEED = 0;
const DEFAULT_COLOR_COUNT = 4;

export function PaletteStudio() {
  // Initialize state directly from localStorage synchronously without cascading effect renders
  const [baseHex, setBaseHex] = useState<string>(() => {
    if (typeof window === 'undefined') return DEFAULT_HEX;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.baseHex) return parsed.baseHex;
      }
    } catch {
      // Ignore
    }
    return DEFAULT_HEX;
  });

  const [harmony, setHarmony] = useState<HarmonyMode>(() => {
    if (typeof window === 'undefined') return DEFAULT_HARMONY;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.harmony) return parsed.harmony;
      }
    } catch {
      // Ignore
    }
    return DEFAULT_HARMONY;
  });

  const [seed, setSeed] = useState<number>(() => {
    if (typeof window === 'undefined') return DEFAULT_SEED;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (typeof parsed.seed === 'number') return parsed.seed;
      }
    } catch {
      // Ignore
    }
    return DEFAULT_SEED;
  });

  const [colorCount, setColorCount] = useState<number>(() => {
    if (typeof window === 'undefined') return DEFAULT_COLOR_COUNT;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (typeof parsed.colorCount === 'number' && parsed.colorCount >= 2 && parsed.colorCount <= 9) {
          return parsed.colorCount;
        }
      }
    } catch {
      // Ignore
    }
    return DEFAULT_COLOR_COUNT;
  });

  // Save state changes to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ baseHex, harmony, seed, colorCount })
      );
    } catch {
      // Ignore errors
    }
  }, [baseHex, harmony, seed, colorCount]);

  const deferredHex = useDeferredValue(baseHex);

  // Deferred palette calculation for ultra-smooth dragging performance
  const palette: Palette = useMemo(() => {
    return generatePalette(deferredHex, harmony, seed, colorCount);
  }, [deferredHex, harmony, seed, colorCount]);

  const handleNewVariation = () => {
    setSeed((prev) => prev + 1);
  };

  const handleReset = () => {
    setBaseHex(DEFAULT_HEX);
    setHarmony(DEFAULT_HARMONY);
    setSeed(DEFAULT_SEED);
    setColorCount(DEFAULT_COLOR_COUNT);
  };

  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col justify-between selection:bg-purple-600 selection:text-white">
      {/* Top Header Navigation */}
      <header className="sticky top-0 z-40 border-b border-white/10 glass-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Brand Title */}
          <Link href="/" className="flex items-center gap-3 group focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg p-1 transition-all">
            <div className="w-9 h-9 rounded-xl bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 shadow-lg shadow-purple-900/20 group-hover:scale-105 transition-transform">
              <PaletteIcon className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm sm:text-base font-mono font-black tracking-tight text-white flex items-center gap-2">
                OKLCH PIXEL PALETTE <span className="text-purple-400 font-normal text-xs px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20">STUDIO</span>
              </h1>
              <p className="text-[11px] text-gray-400 font-mono hidden sm:block">
                Color Theory Engine tailored for Pixel Art &amp; UI
              </p>
            </div>
          </Link>

          {/* Right Header Navigation & Status Stamp */}
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <Home className="w-3.5 h-3.5" />
              <span>Homepage</span>
            </Link>

            <div className="hidden md:flex items-center gap-2 text-xs font-mono text-gray-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>sRGB Gamut Guarded</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Studio Workstation */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Top Control Section */}
        <section aria-label="Palette Controls" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ColorPicker value={baseHex} onChange={setBaseHex} />
          <HarmonySelector harmony={harmony} onChange={setHarmony} />
        </section>

        {/* Global Action Toolbar */}
        <section aria-label="Action Toolbar">
          <ActionToolbar
            palette={palette}
            colorCount={colorCount}
            onColorCountChange={setColorCount}
            onNewVariation={handleNewVariation}
            onReset={handleReset}
          />
        </section>

        {/* Color Cards Display Grid */}
        <section aria-label="Generated Color Palette Cards">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-mono font-bold tracking-widest text-gray-300 uppercase flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              Generated {colorCount}-Color Palette
            </h2>
            <span className="text-[11px] font-mono text-gray-400">Click any card to copy HEX</span>
          </div>

          <PaletteGrid palette={palette} />
        </section>

        {/* Visualizations and Pixel Preview Dual Column Section */}
        <section aria-label="Visualizations and Pixel Preview" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BklitLightnessChart palette={palette} />
          <PixelPreview palette={palette} />
        </section>
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-white/10 bg-zinc-950 py-6 text-xs font-mono text-gray-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-purple-400" />
            <span>OKLCH Pixel Palette Studio &copy; {new Date().getFullYear()}</span>
            <span className="text-gray-700">|</span>
            <span className="text-gray-400">Next.js &bull; Tailwind CSS &bull; Motion &bull; Bklit UI</span>
          </div>

          <div className="flex items-center gap-4 text-gray-400">
            <span className="flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Delta E OK Validated
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
