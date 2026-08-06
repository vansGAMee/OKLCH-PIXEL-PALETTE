'use client';

import React from 'react';
import { useReducedMotion } from 'motion/react';
import { Palette } from '@/types/palette';
import { Activity, Info } from 'lucide-react';
import { getPaletteColorLabel } from '@/lib/color/colorNaming';

interface BklitLightnessChartProps {
  palette: Palette;
}

/**
 * Formats Hue cleanly, returning 'neutral' for neutral/gray colors or null hues.
 */
function formatHue(h: number | null | undefined, c: number): string {
  if (h === null || h === undefined || isNaN(h) || c < 0.025) {
    return 'neutral';
  }
  const normH = ((h % 360) + 360) % 360;
  return `${Math.round(normH)}°`;
}

export const BklitLightnessChart: React.FC<BklitLightnessChartProps> = ({ palette }) => {
  const shouldReduceMotion = useReducedMotion();
  const [hoveredIdx, setHoveredIdx] = React.useState<number | null>(null);

  // Sort colors for visual display ONLY from darkest (L=0) to lightest (L=1)
  const sortedColors = React.useMemo(() => {
    const rawColors = palette.colors && palette.colors.length > 0
      ? palette.colors
      : [palette.shadow, palette.base, palette.highlight, palette.accent];

    return rawColors
      .map((col) => {
        const originalIndex = rawColors.findIndex((c) => c === col);
        const label = getPaletteColorLabel(col.role, originalIndex, rawColors.length, col.oklch);
        return {
          ...col,
          originalIndex,
          label,
        };
      })
      .sort((a, b) => a.oklch.l - b.oklch.l);
  }, [palette]);

  const activeColor = hoveredIdx !== null ? sortedColors[hoveredIdx] : null;

  return (
    <div className="glass-panel rounded-xl p-5 border border-white/10 relative flex flex-col justify-between">
      {/* Chart Header */}
      <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-widest text-gray-200 uppercase">
              Lightness Ladder
            </h3>
            <p className="text-[11px] text-gray-400 font-mono">
              OKLCH L-Scale ({sortedColors.length} Colors Sorted L&rarr;H)
            </p>
          </div>
        </div>
        <div className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-purple-300 border border-purple-500/20">
          Sorted L0 &rarr; L1
        </div>
      </div>

      {/* Interactive Lightness Ladder Bar Visualizer */}
      <div className="relative w-full py-4 min-h-[220px] flex flex-col justify-end">
        {/* Hover Tooltip Card */}
        {activeColor ? (
          <div className="mb-3 p-2.5 rounded-xl border border-purple-500/30 shadow-2xl bg-zinc-950/95 text-left font-mono text-[11px] flex items-center justify-between gap-2 animate-in fade-in duration-150">
            <div className="flex items-center gap-2">
              <span
                className="w-3.5 h-3.5 rounded-md border border-white/30 shrink-0"
                style={{ backgroundColor: activeColor.hex }}
              />
              <span className="font-bold text-white uppercase truncate max-w-[120px]">
                {activeColor.label}
              </span>
            </div>
            <div className="flex items-center gap-3 text-purple-300 text-[10px]">
              <span className="font-bold">{activeColor.hex.toUpperCase()}</span>
              <span className="text-gray-400">L:{(activeColor.oklch.l * 100).toFixed(1)}%</span>
              <span className="text-gray-400">C:{activeColor.oklch.c.toFixed(3)}</span>
              <span className="text-purple-400">H:{formatHue(activeColor.oklch.h, activeColor.oklch.c)}</span>
            </div>
          </div>
        ) : (
          <div className="mb-3 p-2.5 rounded-xl border border-white/5 bg-zinc-900/40 text-gray-400 text-center font-mono text-[11px]">
            Hover over any bar to inspect OKLCH metrics
          </div>
        )}

        {/* Dynamic Bars Row */}
        <div className="h-44 w-full flex items-end justify-between gap-1.5 sm:gap-2 px-1 bg-zinc-950/60 rounded-xl border border-white/5 p-3 relative">
          {/* Subtle horizontal grid lines */}
          <div className="absolute inset-x-3 top-1/4 border-b border-white/5 pointer-events-none" />
          <div className="absolute inset-x-3 top-2/4 border-b border-white/5 pointer-events-none" />
          <div className="absolute inset-x-3 top-3/4 border-b border-white/5 pointer-events-none" />

          {sortedColors.map((col, idx) => {
            const heightPercent = Math.max(8, Math.round(col.oklch.l * 100));
            const isHovered = hoveredIdx === idx;

            return (
              <div
                key={`${col.role}-${col.originalIndex}`}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                className="flex-1 flex flex-col items-center h-full justify-end group cursor-pointer relative z-10"
              >
                {/* L% Badge top */}
                <span className="text-[9px] font-mono text-gray-400 mb-1 opacity-80 group-hover:opacity-100 group-hover:text-purple-300 group-hover:font-bold">
                  {(col.oklch.l * 100).toFixed(0)}%
                </span>

                {/* Animated Color Bar */}
                <div
                  className={`w-full rounded-t-lg transition-all duration-200 border border-white/10 ${
                    isHovered ? 'ring-2 ring-purple-400 scale-y-[1.02] shadow-lg' : 'hover:brightness-110'
                  }`}
                  style={{
                    height: `${heightPercent}%`,
                    backgroundColor: col.hex,
                    transitionProperty: shouldReduceMotion ? 'none' : 'height, transform',
                  }}
                />

                {/* Compact Bar Label (360px overflow safe) */}
                <div className="mt-1 text-center w-full overflow-hidden">
                  <span className="text-[9px] font-mono font-bold text-gray-300 truncate block uppercase">
                    {col.label.length > 5 ? col.label.substring(0, 5) : col.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between text-[10px] font-mono text-gray-400">
        <span className="flex items-center gap-1">
          <Info className="w-3 h-3 text-purple-400" /> Sorted L0 &rarr; L1 (Array Order Preserved)
        </span>
        <span>sRGB Gamut Guarded</span>
      </div>
    </div>
  );
};
