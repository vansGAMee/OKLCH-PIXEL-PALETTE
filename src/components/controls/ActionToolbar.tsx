'use client';

import React from 'react';
import { motion } from 'motion/react';
import { RefreshCw, RotateCcw, Download } from 'lucide-react';
import { Palette } from '@/types/palette';
import { exportPalettePng } from '@/lib/color/exportPalettePng';

interface ActionToolbarProps {
  palette: Palette;
  onNewVariation: () => void;
  onReset: () => void;
}

export const ActionToolbar: React.FC<ActionToolbarProps> = ({
  palette,
  onNewVariation,
  onReset,
}) => {
  const handleExportPng = () => {
    exportPalettePng(palette, `pixel-palette-${palette.base.hex.replace('#', '')}.png`);
  };

  return (
    <div className="glass-panel rounded-xl p-4 border border-white/10 flex flex-wrap items-center justify-between gap-3">
      {/* Seed Badge */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-gray-400">Current Seed:</span>
        <span className="px-2.5 py-1 rounded bg-purple-500/10 text-purple-300 border border-purple-500/30 text-xs font-mono font-bold">
          #{palette.seed}
        </span>
      </div>

      {/* Buttons Row */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* New Variation Button */}
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={onNewVariation}
          className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-mono font-bold uppercase tracking-wider shadow-lg shadow-purple-900/30 border border-purple-400/40 flex items-center gap-2 transition-all cursor-pointer"
        >
          <RefreshCw className="w-4 h-4" />
          New Variation
        </motion.button>

        {/* Reset Button */}
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={onReset}
          className="px-4 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-gray-200 text-xs font-mono font-bold uppercase tracking-wider border border-white/10 flex items-center gap-2 transition-all cursor-pointer"
        >
          <RotateCcw className="w-4 h-4" />
          Reset
        </motion.button>

        {/* Export PNG Button */}
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={handleExportPng}
          className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold uppercase tracking-wider shadow-lg shadow-emerald-900/30 border border-emerald-400/40 flex items-center gap-2 transition-all cursor-pointer"
        >
          <Download className="w-4 h-4" />
          Export PNG
        </motion.button>
      </div>
    </div>
  );
};
