'use client';

import React from 'react';
import { useReducedMotion } from 'motion/react';
import { Palette } from '@/types/palette';
import { Activity, Info } from 'lucide-react';

import { BarChart } from '@/components/charts/bar-chart';
import { Bar } from '@/components/charts/bar';
import { Grid } from '@/components/charts/grid';
import { ChartTooltip } from '@/components/charts/tooltip';

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
  const normH = (h % 360 + 360) % 360;
  return `${Math.round(normH)}°`;
}

export const BklitLightnessChart: React.FC<BklitLightnessChartProps> = ({ palette }) => {
  const shouldReduceMotion = useReducedMotion();

  // Single grouped row for 4 roles with distinct palette color fills
  const chartData = [
    {
      name: 'Lightness',
      shadow: Math.round(palette.shadow.oklch.l * 100),
      base: Math.round(palette.base.oklch.l * 100),
      highlight: Math.round(palette.highlight.oklch.l * 100),
      accent: Math.round(palette.accent.oklch.l * 100),
    },
  ];

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
            <p className="text-[11px] text-gray-400 font-mono">Bklit UI BarChart Component</p>
          </div>
        </div>
        <div className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-gray-400 border border-white/5">
          OKLCH L-Scale
        </div>
      </div>

      {/* Real Bklit UI BarChart Component */}
      <div className="relative w-full py-2">
        <BarChart
          data={chartData}
          xDataKey="name"
          aspectRatio="2.4 / 1"
          barGap={0.3}
          animationDuration={shouldReduceMotion ? 0 : 600}
          margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
        >
          <Grid horizontal vertical={false} strokeDasharray="3 3" />
          
          <Bar dataKey="shadow" fill={palette.shadow.hex} lineCap="round" />
          <Bar dataKey="base" fill={palette.base.hex} lineCap="round" />
          <Bar dataKey="highlight" fill={palette.highlight.hex} lineCap="round" />
          <Bar dataKey="accent" fill={palette.accent.hex} lineCap="round" />

          <ChartTooltip
            showDatePill={false}
            showCrosshair={false}
            content={() => {
              return (
                <div className="p-3 rounded-xl border border-purple-500/30 shadow-2xl bg-zinc-950/95 text-left font-mono min-w-[220px]">
                  <div className="text-[10px] font-bold uppercase text-purple-400 mb-2 pb-1 border-b border-white/10 tracking-wider">
                    OKLCH Lightness Metrics
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    {(['shadow', 'base', 'highlight', 'accent'] as const).map((roleKey) => {
                      const col = palette[roleKey];
                      const hText = formatHue(col.oklch.h, col.oklch.c);
                      return (
                        <div key={roleKey} className="flex items-center justify-between gap-2 text-gray-300">
                          <div className="flex items-center gap-1.5">
                            <span
                              className="w-2.5 h-2.5 rounded-full border border-white/30 shrink-0"
                              style={{ backgroundColor: col.hex }}
                            />
                            <span className="capitalize font-bold text-white">{col.role}:</span>
                          </div>
                          <div className="font-mono text-right text-purple-300">
                            <span>{col.hex.toUpperCase()}</span>{' '}
                            <span className="text-gray-400">L:{col.oklch.l.toFixed(2)}</span>{' '}
                            <span className="text-gray-400">C:{col.oklch.c.toFixed(2)}</span>{' '}
                            <span className="text-purple-400 font-bold">H:{hText}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            }}
          />
        </BarChart>
      </div>

      {/* Footer Info */}
      <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between text-[10px] font-mono text-gray-400">
        <span className="flex items-center gap-1">
          <Info className="w-3 h-3 text-purple-400" /> Bklit UI BarChart Component
        </span>
        <span>sRGB Gamut Guarded</span>
      </div>
    </div>
  );
};
