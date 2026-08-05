'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'motion/react';
import { Palette, PaletteColor } from '@/types/palette';
import { Activity, Info } from 'lucide-react';

interface BklitLightnessChartProps {
  palette: Palette;
}

export const BklitLightnessChart: React.FC<BklitLightnessChartProps> = ({ palette }) => {
  const [hoveredRole, setHoveredRole] = useState<string | null>(null);
  const shouldReduceMotion = useReducedMotion();

  const columns: { label: string; role: keyof Omit<Palette, 'harmony' | 'seed'>; data: PaletteColor }[] = [
    { label: 'Shadow', role: 'shadow', data: palette.shadow },
    { label: 'Base', role: 'base', data: palette.base },
    { label: 'Highlight', role: 'highlight', data: palette.highlight },
    { label: 'Accent', role: 'accent', data: palette.accent },
  ];

  const hoveredData = hoveredRole
    ? columns.find((c) => c.role === hoveredRole)?.data
    : null;

  return (
    <div className="glass-panel rounded-xl p-5 border border-white/10 relative overflow-hidden flex flex-col justify-between">
      {/* Chart Header */}
      <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-widest text-gray-200 uppercase">
              Bklit UI Lightness Ladder
            </h3>
            <p className="text-[11px] text-gray-400 font-mono">OKLCH Perceived Lightness (L)</p>
          </div>
        </div>
        <div className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-gray-400 border border-white/5">
          OKLCH L-Scale
        </div>
      </div>

      {/* Interactive Chart Container */}
      <div className="relative h-44 w-full flex items-end justify-between gap-3 px-2 pt-6 pb-2">
        {/* Horizontal Guide Lines */}
        <div className="absolute inset-x-0 top-6 bottom-2 flex flex-col justify-between pointer-events-none opacity-25">
          <div className="border-b border-dashed border-white/20 w-full relative">
            <span className="absolute -top-3 right-0 text-[9px] font-mono text-gray-400">1.0</span>
          </div>
          <div className="border-b border-dashed border-white/20 w-full relative">
            <span className="absolute -top-3 right-0 text-[9px] font-mono text-gray-400">0.75</span>
          </div>
          <div className="border-b border-dashed border-white/20 w-full relative">
            <span className="absolute -top-3 right-0 text-[9px] font-mono text-gray-400">0.50</span>
          </div>
          <div className="border-b border-dashed border-white/20 w-full relative">
            <span className="absolute -top-3 right-0 text-[9px] font-mono text-gray-400">0.25</span>
          </div>
          <div className="border-b border-white/30 w-full relative">
            <span className="absolute -top-3 right-0 text-[9px] font-mono text-gray-400">0.0</span>
          </div>
        </div>

        {/* Bklit Columns */}
        {columns.map(({ label, role, data }) => {
          const lightnessPct = Math.min(100, Math.max(4, Math.round(data.oklch.l * 100)));
          const isHovered = hoveredRole === role;

          return (
            <div
              key={role}
              className="relative flex-1 h-full flex flex-col items-center justify-end group cursor-pointer z-10"
              onMouseEnter={() => setHoveredRole(role)}
              onMouseLeave={() => setHoveredRole(null)}
            >
              {/* Column Bar Container */}
              <div className="w-full max-w-[56px] h-full flex items-end justify-center relative">
                {/* Bar Motion Container */}
                <motion.div
                  className="w-full rounded-t-lg relative transition-all duration-200"
                  style={{
                    backgroundColor: data.hex,
                    boxShadow: isHovered
                      ? `0 0 20px ${data.hex}80, 0 0 2px #ffffff80 inset`
                      : `0 0 10px ${data.hex}30`,
                    border: '1px solid rgba(255, 255, 255, 0.25)',
                    borderBottom: 'none',
                  }}
                  initial={shouldReduceMotion ? { height: `${lightnessPct}%` } : { height: '0%' }}
                  animate={{ height: `${lightnessPct}%` }}
                  transition={{
                    type: 'spring',
                    stiffness: 180,
                    damping: 20,
                  }}
                >
                  {/* Top Highlight Shine */}
                  <div className="absolute top-0 inset-x-0 h-1 bg-white/40 rounded-t-lg" />
                  
                  {/* Lightness Label Badge Inside Column if Tall */}
                  {lightnessPct > 25 && (
                    <span
                      className="absolute top-2 inset-x-0 text-center text-[10px] font-mono font-bold"
                      style={{
                        color: data.oklch.l > 0.6 ? '#000000' : '#ffffff',
                      }}
                    >
                      {(data.oklch.l * 100).toFixed(0)}%
                    </span>
                  )}
                </motion.div>
              </div>

              {/* Column Label */}
              <div className="mt-2 text-center">
                <span
                  className={`text-[11px] font-mono font-semibold transition-colors ${
                    isHovered ? 'text-purple-300' : 'text-gray-400'
                  }`}
                >
                  {label}
                </span>
              </div>
            </div>
          );
        })}

        {/* Bklit UI Animated Floating Tooltip */}
        <AnimatePresence>
          {hoveredData && (
            <motion.div
              initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: 5, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 3, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute top-2 left-1/2 -translate-x-1/2 z-30 pointer-events-none"
            >
              <div className="glass-panel px-3 py-2 rounded-lg border border-purple-500/30 shadow-2xl bg-zinc-950/90 text-left min-w-[160px]">
                <div className="flex items-center gap-2 mb-1">
                  <div
                    className="w-3 h-3 rounded-full border border-white/30"
                    style={{ backgroundColor: hoveredData.hex }}
                  />
                  <span className="text-xs font-mono font-bold uppercase text-white">
                    {hoveredData.role}
                  </span>
                  <span className="text-[10px] font-mono text-purple-400 ml-auto font-bold">
                    {hoveredData.hex.toUpperCase()}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1 text-[10px] font-mono text-gray-300 pt-1 border-t border-white/10">
                  <div>
                    <span className="text-gray-500 block">L</span>
                    {(hoveredData.oklch.l * 100).toFixed(1)}%
                  </div>
                  <div>
                    <span className="text-gray-500 block">C</span>
                    {hoveredData.oklch.c.toFixed(3)}
                  </div>
                  <div>
                    <span className="text-gray-500 block">H</span>
                    {hoveredData.oklch.h !== null ? `${hoveredData.oklch.h.toFixed(0)}°` : 'None'}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer Info */}
      <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between text-[10px] font-mono text-gray-400">
        <span className="flex items-center gap-1">
          <Info className="w-3 h-3 text-purple-400" /> Smooth L-Step progression
        </span>
        <span>sRGB Gamut OK</span>
      </div>
    </div>
  );
};
