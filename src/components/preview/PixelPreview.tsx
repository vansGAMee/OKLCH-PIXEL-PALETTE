'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'motion/react';
import { Palette } from '@/types/palette';
import { Locale, messages } from '@/i18n/messages';
import { Sparkles } from 'lucide-react';
import { getPaletteColorLabel } from '@/lib/color/colorNaming';

interface PixelPreviewProps {
  palette: Palette;
  locale?: Locale;
}

type SceneType = 'potion' | 'gem' | 'shield' | 'hero' | 'full';

// 16x16 Pixel Art Matrices
// Indices: 0: Shadow, 1: Base, 2: Highlight, 3: Accent, -1: Transparent

const PIXEL_SCENES: Record<Exclude<SceneType, 'full'>, { titleKey: 'potion' | 'gem' | 'shield' | 'hero'; grid: number[][] }> = {
  potion: {
    titleKey: 'potion',
    grid: [
      [-1, -1, -1, -1, -1, -1,  0,  0,  0,  0, -1, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1,  0,  2,  2,  0, -1, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1,  0,  1,  1,  0, -1, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1,  0,  0,  1,  1,  0,  0, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1,  0,  2,  2,  1,  1,  1,  1,  0, -1, -1, -1, -1],
      [-1, -1, -1,  0,  2,  2,  1,  1,  1,  1,  0,  0,  0, -1, -1, -1],
      [-1, -1,  0,  2,  2,  1,  1,  3,  3,  1,  1,  0,  0,  0, -1, -1],
      [-1,  0,  2,  2,  1,  1,  3,  3,  3,  3,  1,  1,  0,  0,  0, -1],
      [-1,  0,  2,  1,  1,  3,  3,  3,  3,  3,  3,  1,  1,  0,  0, -1],
      [-1,  0,  2,  1,  3,  3,  3,  3,  3,  3,  3,  3,  1,  0,  0, -1],
      [-1,  0,  2,  1,  3,  3,  3,  3,  3,  3,  3,  3,  1,  0,  0, -1],
      [-1,  0,  2,  1,  1,  3,  3,  3,  3,  3,  3,  1,  0,  0,  0, -1],
      [-1,  0,  2,  2,  1,  1,  3,  3,  3,  3,  1,  0,  0,  0,  0, -1],
      [-1, -1,  0,  2,  2,  1,  1,  1,  1,  1,  0,  0,  0,  0, -1, -1],
      [-1, -1, -1,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    ],
  },
  gem: {
    titleKey: 'gem',
    grid: [
      [-1, -1, -1, -1, -1, -1,  2,  2,  2,  2, -1, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1,  2,  2,  2,  2,  2,  2,  2,  2, -1, -1, -1, -1],
      [-1, -1, -1,  2,  2,  2,  1,  1,  1,  1,  2,  2,  2, -1, -1, -1],
      [-1, -1,  2,  2,  1,  1,  1,  1,  1,  1,  1,  1,  2,  2, -1, -1],
      [-1,  2,  2,  1,  1,  1,  3,  3,  3,  3,  1,  1,  1,  0,  0, -1],
      [ 0,  2,  1,  1,  3,  3,  3,  3,  3,  3,  3,  3,  1,  1,  0,  0],
      [ 0,  2,  1,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  1,  0,  0],
      [ 0,  2,  1,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  1,  0,  0],
      [-1,  0,  1,  1,  3,  3,  3,  3,  3,  3,  3,  3,  1,  0,  0, -1],
      [-1, -1,  0,  1,  1,  3,  3,  3,  3,  3,  3,  1,  0,  0, -1, -1],
      [-1, -1, -1,  0,  1,  1,  3,  3,  3,  3,  1,  0,  0, -1, -1, -1],
      [-1, -1, -1, -1,  0,  0,  1,  3,  3,  1,  0,  0, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1,  0,  0,  1,  1,  0,  0, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1,  0,  0,  0,  0, -1, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1, -1,  0,  0, -1, -1, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    ],
  },
  shield: {
    titleKey: 'shield',
    grid: [
      [-1, -1,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, -1, -1],
      [-1,  0,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  0, -1],
      [-1,  0,  2,  1,  1,  1,  1,  0,  0,  1,  1,  1,  1,  2,  0, -1],
      [-1,  0,  2,  1,  3,  3,  1,  0,  0,  1,  3,  3,  1,  2,  0, -1],
      [-1,  0,  2,  1,  3,  3,  1,  0,  0,  1,  3,  3,  1,  2,  0, -1],
      [-1,  0,  2,  1,  1,  1,  1,  0,  0,  1,  1,  1,  1,  2,  0, -1],
      [-1,  0,  2,  0,  0,  0,  0,  3,  3,  0,  0,  0,  0,  2,  0, -1],
      [-1,  0,  2,  0,  0,  0,  0,  3,  3,  0,  0,  0,  0,  2,  0, -1],
      [-1,  0,  2,  1,  1,  1,  1,  0,  0,  1,  1,  1,  1,  2,  0, -1],
      [-1, -1,  0,  2,  1,  3,  1,  0,  0,  1,  3,  1,  2,  0, -1, -1],
      [-1, -1,  0,  2,  2,  1,  1,  0,  0,  1,  1,  2,  2,  0, -1, -1],
      [-1, -1, -1,  0,  2,  2,  1,  0,  0,  1,  2,  2,  0, -1, -1, -1],
      [-1, -1, -1, -1,  0,  2,  2,  0,  0,  2,  2,  0, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1,  0,  2,  0,  0,  2,  0, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1,  0,  0,  0,  0, -1, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1, -1,  0,  0, -1, -1, -1, -1, -1, -1, -1],
    ],
  },
  hero: {
    titleKey: 'hero',
    grid: [
      [-1, -1, -1, -1, -1,  0,  0,  0,  0,  0,  0, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1,  0,  2,  2,  2,  2,  2,  2,  0, -1, -1, -1, -1],
      [-1, -1, -1, -1,  0,  2,  1,  1,  1,  1,  2,  0, -1, -1, -1, -1],
      [-1, -1, -1, -1,  0,  1,  0,  1,  1,  0,  1,  0, -1, -1, -1, -1],
      [-1, -1, -1, -1,  0,  1,  1,  1,  1,  1,  1,  0, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1,  0,  1,  1,  1,  1,  0, -1, -1, -1, -1, -1],
      [-1, -1, -1,  0,  0,  3,  3,  3,  3,  3,  3,  0,  0, -1, -1, -1],
      [-1, -1,  0,  2,  0,  3,  3,  3,  3,  3,  3,  0,  2,  0, -1, -1],
      [-1, -1,  0,  2,  0,  3,  1,  3,  3,  1,  3,  0,  2,  0, -1, -1],
      [-1, -1,  0,  2,  0,  3,  3,  3,  3,  3,  3,  0,  2,  0, -1, -1],
      [-1, -1, -1,  0,  0,  3,  3,  3,  3,  3,  3,  0,  0, -1, -1, -1],
      [-1, -1, -1, -1, -1,  0,  0,  0,  0,  0,  0, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1,  0,  1,  0,  0,  1,  0, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1,  0,  1,  0,  0,  1,  0, -1, -1, -1, -1, -1],
      [-1, -1, -1, -1,  0,  0,  0, -1, -1,  0,  0,  0, -1, -1, -1, -1],
      [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    ],
  },
};

/**
 * Creates a pixel art mosaic grid that utilizes every color index 0..numColors-1 at least once.
 */
function createFullPaletteGrid(numColors: number): number[][] {
  const grid: number[][] = [];
  for (let r = 0; r < 16; r++) {
    const row: number[] = [];
    for (let c = 0; c < 16; c++) {
      const idx = (r + c) % numColors;
      row.push(idx);
    }
    grid.push(row);
  }
  return grid;
}

export const PixelPreview: React.FC<PixelPreviewProps> = React.memo(function PixelPreviewComponent({ palette, locale = 'en' }: PixelPreviewProps) {
  const [activeScene, setActiveScene] = useState<SceneType>('potion');
  const shouldReduceMotion = useReducedMotion();
  const t = messages[locale].preview;

  const paletteColors = palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent];

  const colors = paletteColors.map((c) => c.hex);

  // Active Grid & Title
  const isFullMode = activeScene === 'full';
  const activeGrid = isFullMode
    ? createFullPaletteGrid(paletteColors.length)
    : PIXEL_SCENES[activeScene].grid;

  const sceneTitle = isFullMode ? t.scenes.full : t.scenes[PIXEL_SCENES[activeScene].titleKey];

  // Calculate used color indices in active scene
  const usedIndices = React.useMemo(() => {
    const set = new Set<number>();
    activeGrid.forEach((row) => {
      row.forEach((idx) => {
        if (idx >= 0 && idx < paletteColors.length) {
          set.add(idx);
        }
      });
    });
    return set;
  }, [activeGrid, paletteColors.length]);

  const usesCaption = t.usesCaption
    .replace('{used}', String(usedIndices.size))
    .replace('{total}', String(paletteColors.length));

  return (
    <div className="glass-panel rounded-xl p-5 border border-white/10 relative flex flex-col justify-between">
      {/* Header & Scene Switcher */}
      <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-widest text-gray-200 uppercase">
              {t.title}
            </h3>
            <p className="text-[11px] text-gray-400 font-mono flex items-center gap-1.5">
              <span>{usesCaption}</span>
            </p>
          </div>
        </div>

        {/* Scene Selector Pills */}
        <div className="flex items-center gap-1 bg-zinc-900/80 p-1 rounded-lg border border-white/5 overflow-x-auto">
          {(['potion', 'gem', 'shield', 'hero', 'full'] as SceneType[]).map((sceneKey) => (
            <button
              key={sceneKey}
              onClick={() => setActiveScene(sceneKey)}
              className={`px-2.5 py-1 text-[10px] font-mono rounded transition-all capitalize cursor-pointer ${
                activeScene === sceneKey
                  ? 'bg-purple-600 text-white font-bold shadow-md'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`}
            >
              {t.scenes[sceneKey]}
            </button>
          ))}
        </div>
      </div>

      {/* Pixel Display Container */}
      <div className="relative flex flex-col items-center justify-center p-6 bg-zinc-950/90 rounded-lg border border-white/5 shadow-inner">
        {/* Subtle grid pattern background */}
        <div
          className="absolute inset-0 opacity-10 pointer-events-none rounded-lg"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.4) 1px, transparent 0)',
            backgroundSize: '16px 16px',
          }}
        />

        {/* SVG Pixel Renderer with Motion Entrance */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeScene}
            initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="relative z-10 p-3 bg-zinc-900/80 rounded-xl border border-white/10 shadow-2xl flex items-center justify-center"
          >
            <svg
              viewBox="0 0 16 16"
              className="w-48 h-48 sm:w-56 sm:h-56 image-pixelated drop-shadow-xl"
              shapeRendering="crispEdges"
            >
              {activeGrid.map((row, r) =>
                row.map((colorIdx, c) => {
                  if (colorIdx < 0) return null;
                  const safeIdx = colorIdx % colors.length;
                  return (
                    <rect
                      key={`${r}-${c}`}
                      x={c}
                      y={r}
                      width={1}
                      height={1}
                      fill={colors[safeIdx]}
                    />
                  );
                })
              )}
            </svg>
          </motion.div>
        </AnimatePresence>

        {/* Active Scene Title */}
        <div className="mt-3 text-center z-10">
          <span className="text-xs font-mono text-purple-300 font-bold uppercase tracking-wider">
            {sceneTitle}
          </span>
        </div>
      </div>

      {/* Index Legend Bar */}
      <div className="mt-4 pt-3 border-t border-white/5 flex flex-wrap gap-2">
        {paletteColors.map((col, idx) => {
          const isUsed = usedIndices.has(idx);
          const label = getPaletteColorLabel(col.role, idx, paletteColors.length, col.oklch);

          return (
            <div
              key={`${col.role}-${idx}`}
              className={`flex items-center gap-1.5 p-1.5 rounded-md border text-[10px] font-mono transition-all flex-1 min-w-[80px] ${
                isUsed
                  ? 'bg-zinc-900/80 border-purple-500/30 text-gray-200 opacity-100 shadow-sm'
                  : 'bg-zinc-950/40 border-white/5 text-gray-500 opacity-40 grayscale-[40%]'
              }`}
            >
              <div
                className="w-3 h-3 rounded-xs border border-white/20 shrink-0"
                style={{ backgroundColor: col.hex }}
              />
              <span className="truncate uppercase font-bold">{label}</span>
              <span
                className={`w-1.5 h-1.5 rounded-full ml-auto shrink-0 ${
                  isUsed ? 'bg-emerald-400' : 'bg-zinc-600'
                }`}
                title={isUsed ? 'Used in scene' : 'Unused in scene'}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
});
