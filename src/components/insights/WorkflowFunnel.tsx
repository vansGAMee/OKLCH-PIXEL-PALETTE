'use client';
/**
 * src/components/insights/WorkflowFunnel.tsx
 * Lightweight SVG funnel chart for palette workflow stages.
 * 5 stages: Generated → Saved → Published → Remixed → Exported
 * Respects prefers-reduced-motion.
 */
import React from 'react';
import { useReducedMotion } from 'motion/react';

interface Stage {
  stage: string;
  label: string;
  count: number;
}

interface WorkflowFunnelProps {
  stages: Stage[];
  locale?: 'en' | 'ru';
}

const COLORS = [
  'oklch(0.55 0.22 290)',
  'oklch(0.50 0.20 290)',
  'oklch(0.45 0.18 290)',
  'oklch(0.40 0.16 290)',
  'oklch(0.35 0.14 290)',
];

export function WorkflowFunnel({ stages, locale = 'en' }: WorkflowFunnelProps) {
  const shouldReduceMotion = useReducedMotion();
  const maxCount = Math.max(...stages.map((s) => s.count), 1);

  const isRu = locale === 'ru';
  const dropLabel = (fromCount: number, toCount: number): string => {
    if (fromCount === 0) return '';
    const pct = Math.round(((fromCount - toCount) / fromCount) * 100);
    return pct > 0 ? `-${pct}%` : '';
  };

  return (
    <div className="space-y-2">
      {/* Legend */}
      <p className="text-xs font-mono text-gray-400 mb-4">
        {isRu ? 'Количество действий за всё время' : 'Lifetime action counts'}
      </p>

      {stages.map((stage, i) => {
        const widthPct = (stage.count / maxCount) * 100;
        const drop = i > 0 ? dropLabel(stages[i - 1].count, stage.count) : '';

        return (
          <div key={stage.stage} className="space-y-0.5">
            <div className="flex items-center justify-between text-[11px] font-mono text-gray-400">
              <span className="font-bold text-white">{stage.label}</span>
              <div className="flex items-center gap-3">
                {drop && (
                  <span className="text-amber-400">{drop}</span>
                )}
                <span className="text-purple-300 font-bold">{stage.count}</span>
              </div>
            </div>
            <div className="h-8 bg-zinc-900 rounded-lg overflow-hidden relative">
              <div
                className="h-full rounded-lg flex items-center px-3 transition-all"
                style={{
                  width: stage.count === 0 ? '4px' : `${Math.max(4, widthPct)}%`,
                  background: COLORS[i] ?? COLORS[4],
                  transitionProperty: shouldReduceMotion ? 'none' : 'width',
                  transitionDuration: '600ms',
                  transitionDelay: `${i * 100}ms`,
                }}
              />
              {stage.count === 0 && (
                <span className="absolute inset-0 flex items-center px-3 text-[10px] font-mono text-gray-600">
                  {isRu ? 'нет данных' : 'no data'}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
