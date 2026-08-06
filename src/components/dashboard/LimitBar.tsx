'use client';
/**
 * src/components/dashboard/LimitBar.tsx
 * Shows X/max usage bar with color coding.
 */
import React from 'react';

interface LimitBarProps {
  label: string;
  current: number;
  max: number;
}

export function LimitBar({ label, current, max }: LimitBarProps) {
  const pct = Math.min(100, (current / max) * 100);
  const isWarning = pct >= 80;
  const isFull = pct >= 100;

  return (
    <div className="glass-panel rounded-xl border border-white/10 p-4 space-y-2">
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="text-gray-400 font-bold uppercase tracking-widest">{label}</span>
        <span className={`font-bold ${isFull ? 'text-red-400' : isWarning ? 'text-amber-400' : 'text-white'}`}>
          {current} / {max}
        </span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isFull ? 'bg-red-500' : isWarning ? 'bg-amber-500' : 'bg-purple-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
