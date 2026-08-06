'use client';

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { RefreshCw, RotateCcw, Download, ChevronDown, Image as ImageIcon, FileCode, FileText, Code, Palette as PaletteIcon } from 'lucide-react';
import { Palette } from '@/types/palette';
import { exportPalettePng } from '@/lib/color/exportPalettePng';
import { Locale, messages } from '@/i18n/messages';
import {
  sanitizeFilename,
  downloadTextFile,
  generateGplString,
  generateJascPalString,
  generateHexListString,
  generateTxtString,
  generateJsonString,
} from '@/lib/color/exporters';

interface ActionToolbarProps {
  palette: Palette;
  colorCount: number;
  onColorCountChange: (count: number) => void;
  onNewVariation: () => void;
  onReset: () => void;
  locale?: Locale;
}

export const ActionToolbar: React.FC<ActionToolbarProps> = ({
  palette,
  colorCount,
  onColorCountChange,
  onNewVariation,
  onReset,
  locale = 'en',
}) => {
  const [isExportOpen, setIsExportOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const t = messages[locale].controls;
  const exp = messages[locale].export;

  const baseFilename = sanitizeFilename(`pixel-palette-${palette.base.hex.replace('#', '')}`);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsExportOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleExportPng = () => {
    exportPalettePng(palette, `${baseFilename}.png`);
    setIsExportOpen(false);
  };

  const handleExportGpl = () => {
    const content = generateGplString(palette, locale);
    downloadTextFile(content, `${baseFilename}.gpl`, 'text/plain;charset=utf-8');
    setIsExportOpen(false);
  };

  const handleExportJasc = () => {
    const content = generateJascPalString(palette);
    downloadTextFile(content, `${baseFilename}.pal`, 'text/plain;charset=utf-8');
    setIsExportOpen(false);
  };

  const handleExportHex = () => {
    const content = generateHexListString(palette);
    downloadTextFile(content, `${baseFilename}.hex`, 'text/plain;charset=utf-8');
    setIsExportOpen(false);
  };

  const handleExportTxt = () => {
    const content = generateTxtString(palette, locale);
    downloadTextFile(content, `${baseFilename}.txt`, 'text/plain;charset=utf-8');
    setIsExportOpen(false);
  };

  const handleExportJson = () => {
    const content = generateJsonString(palette, locale);
    downloadTextFile(content, `${baseFilename}.json`, 'application/json;charset=utf-8');
    setIsExportOpen(false);
  };

  return (
    <div className="glass-panel rounded-xl p-4 border border-white/10 flex flex-wrap items-center justify-between gap-4">
      {/* Left side: Seed & Color Count Selector */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Seed Badge */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-gray-400">Seed:</span>
          <span className="px-2.5 py-1 rounded bg-purple-500/10 text-purple-300 border border-purple-500/30 text-xs font-mono font-bold">
            #{palette.seed}
          </span>
        </div>

        {/* Color Count Selector (2 to 9) */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-gray-400">{t.countTitle}:</span>
          <div className="flex items-center bg-zinc-900 p-1 rounded-xl border border-white/10 gap-0.5 overflow-x-auto">
            {[2, 3, 4, 5, 6, 7, 8, 9].map((cnt) => (
              <button
                key={cnt}
                onClick={() => onColorCountChange(cnt)}
                aria-label={`Select ${cnt} colors`}
                className={`w-7 h-7 text-xs font-mono rounded-lg transition-all flex items-center justify-center font-bold cursor-pointer ${
                  colorCount === cnt
                    ? 'bg-purple-600 text-white shadow-md'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
                }`}
              >
                {cnt}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Buttons Row */}
      <div className="flex items-center gap-2 flex-wrap relative" ref={menuRef}>
        {/* New Variation Button */}
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={onNewVariation}
          className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-mono font-bold tracking-wider shadow-lg shadow-purple-900/30 border border-purple-400/40 flex items-center gap-2 transition-all cursor-pointer"
        >
          <RefreshCw className="w-4 h-4" />
          <span>{t.newVariation}</span>
        </motion.button>

        {/* Reset Button */}
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={onReset}
          className="px-4 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-gray-200 text-xs font-mono font-bold tracking-wider border border-white/10 flex items-center gap-2 transition-all cursor-pointer"
        >
          <RotateCcw className="w-4 h-4" />
          <span>{t.reset}</span>
        </motion.button>

        {/* Export Dropdown Trigger Button */}
        <div className="relative">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setIsExportOpen((prev) => !prev)}
            aria-expanded={isExportOpen}
            aria-haspopup="true"
            className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold tracking-wider shadow-lg shadow-emerald-900/30 border border-emerald-400/40 flex items-center gap-2 transition-all cursor-pointer"
          >
            <Download className="w-4 h-4" />
            <span>{t.exportBtn}</span>
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isExportOpen ? 'rotate-180' : ''}`} />
          </motion.button>

          {/* Export Formats Menu */}
          <AnimatePresence>
            {isExportOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 mt-2 w-72 bg-zinc-950/95 border border-white/15 rounded-xl shadow-2xl z-50 p-2 backdrop-blur-lg space-y-1 font-mono"
              >
                <div className="px-3 py-1.5 text-[10px] text-gray-400 uppercase tracking-widest border-b border-white/5 font-bold flex items-center gap-1.5">
                  <PaletteIcon className="w-3 h-3 text-purple-400" />
                  <span>{exp.menuTitle}</span>
                </div>

                {/* Polished PNG (Primary) */}
                <button
                  onClick={handleExportPng}
                  className="w-full text-left px-3 py-2 rounded-lg bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-500/30 text-white transition-all flex items-center gap-2.5 cursor-pointer group"
                >
                  <div className="p-1.5 rounded bg-emerald-500/20 text-emerald-400">
                    <ImageIcon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-emerald-300 flex items-center gap-1.5">
                      <span>{exp.polishedPng}</span>
                      <span className="text-[9px] bg-emerald-500/30 text-emerald-200 px-1.5 py-0.2 rounded">PNG</span>
                    </div>
                    <div className="text-[10px] text-gray-400">{exp.polishedPngDesc}</div>
                  </div>
                </button>

                {/* GIMP GPL */}
                <button
                  onClick={handleExportGpl}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-white/5 text-gray-200 transition-all flex items-center gap-2.5 cursor-pointer"
                >
                  <div className="p-1.5 rounded bg-purple-500/10 text-purple-400">
                    <PaletteIcon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold">{exp.gimpGpl}</div>
                    <div className="text-[10px] text-gray-400">{exp.gimpGplDesc}</div>
                  </div>
                </button>

                {/* JASC PAL */}
                <button
                  onClick={handleExportJasc}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-white/5 text-gray-200 transition-all flex items-center gap-2.5 cursor-pointer"
                >
                  <div className="p-1.5 rounded bg-blue-500/10 text-blue-400">
                    <FileCode className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold">{exp.jascPal}</div>
                    <div className="text-[10px] text-gray-400">{exp.jascPalDesc}</div>
                  </div>
                </button>

                {/* HEX List */}
                <button
                  onClick={handleExportHex}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-white/5 text-gray-200 transition-all flex items-center gap-2.5 cursor-pointer"
                >
                  <div className="p-1.5 rounded bg-amber-500/10 text-amber-400">
                    <Code className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold">{exp.hexList}</div>
                    <div className="text-[10px] text-gray-400">{exp.hexListDesc}</div>
                  </div>
                </button>

                {/* Text Breakdown */}
                <button
                  onClick={handleExportTxt}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-white/5 text-gray-200 transition-all flex items-center gap-2.5 cursor-pointer"
                >
                  <div className="p-1.5 rounded bg-zinc-800 text-gray-300">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold">{exp.plainText}</div>
                    <div className="text-[10px] text-gray-400">{exp.plainTextDesc}</div>
                  </div>
                </button>

                {/* JSON */}
                <button
                  onClick={handleExportJson}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-white/5 text-gray-200 transition-all flex items-center gap-2.5 cursor-pointer"
                >
                  <div className="p-1.5 rounded bg-indigo-500/10 text-indigo-400">
                    <FileCode className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold">{exp.jsonFormat}</div>
                    <div className="text-[10px] text-gray-400">{exp.jsonFormatDesc}</div>
                  </div>
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};
