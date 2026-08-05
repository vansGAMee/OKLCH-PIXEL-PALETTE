'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'motion/react';
import { Palette } from '@/types/palette';
import { Sparkles } from 'lucide-react';

interface PixelPreviewProps {
  palette: Palette;
}

type SceneType = 'potion' | 'gem' | 'shield' | 'hero';

// 16x16 Pixel Art Matrices
// Indices:
// 0: Shadow
// 1: Base
// 2: Highlight
// 3: Accent
// -1: Transparent

const PIXEL_SCENES: Record<SceneType, { title: string; grid: number[][] }> = {
  potion: {
    title: 'Magic Potion',
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
    title: 'Crystal Gem',
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
    title: 'Knight Shield',
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
    title: 'Retro Hero',
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

export const PixelPreview: React.FC<PixelPreviewProps> = ({ palette }) => {
  const [activeScene, setActiveScene] = useState<SceneType>('potion');
  const shouldReduceMotion = useReducedMotion();

  const colors = [
    palette.shadow.hex,
    palette.base.hex,
    palette.highlight.hex,
    palette.accent.hex,
  ];

  const scene = PIXEL_SCENES[activeScene];

  return (
    <div className="glass-panel rounded-xl p-5 border border-white/10 relative flex flex-col justify-between">
      {/* Header & Scene Switcher */}
      <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-widest text-gray-200 uppercase">
              Pixel Art Preview
            </h3>
            <p className="text-[11px] text-gray-400 font-mono">4-Color Dynamic Indexing</p>
          </div>
        </div>

        {/* Scene Selector Pills */}
        <div className="flex items-center gap-1 bg-zinc-900/80 p-1 rounded-lg border border-white/5">
          {(['potion', 'gem', 'shield', 'hero'] as SceneType[]).map((sceneKey) => (
            <button
              key={sceneKey}
              onClick={() => setActiveScene(sceneKey)}
              className={`px-2.5 py-1 text-[10px] font-mono rounded transition-all capitalize ${
                activeScene === sceneKey
                  ? 'bg-purple-600 text-white font-bold shadow-md'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`}
            >
              {sceneKey}
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
              {scene.grid.map((row, r) =>
                row.map((colorIdx, c) => {
                  if (colorIdx < 0 || colorIdx >= colors.length) return null;
                  return (
                    <rect
                      key={`${r}-${c}`}
                      x={c}
                      y={r}
                      width={1}
                      height={1}
                      fill={colors[colorIdx]}
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
            {scene.title}
          </span>
        </div>
      </div>

      {/* Index Legend Bar */}
      <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-4 gap-2">
        {[
          { label: '0: Shadow', role: palette.shadow },
          { label: '1: Base', role: palette.base },
          { label: '2: Highlight', role: palette.highlight },
          { label: '3: Accent', role: palette.accent },
        ].map((item, idx) => (
          <div
            key={idx}
            className="flex items-center gap-1.5 p-1.5 rounded-md bg-zinc-900/50 border border-white/5 text-[10px] font-mono text-gray-300"
          >
            <div
              className="w-3 h-3 rounded-xs border border-white/20 shrink-0 transition-colors duration-200"
              style={{ backgroundColor: item.role.hex }}
            />
            <span className="truncate">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
