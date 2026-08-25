'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'motion/react';
import { PaletteColor } from '@/types/palette';
import { Locale, messages } from '@/i18n/messages';
import { getPaletteColorLabel } from '@/lib/color/colorNaming';
import { Copy, Check, ChevronDown, ChevronUp, Lock, LockOpen } from 'lucide-react';

interface ColorCardProps {
  color: PaletteColor;
  index: number;
  totalColors?: number;
  isLocked?: boolean;
  onToggleLock?: () => void;
  onColorChange?: (newHex: string) => void;
  locale?: Locale;
}

export const ColorCard = React.memo(function ColorCardComponent({
  color,
  index,
  totalColors = 4,
  isLocked = false,
  onToggleLock,
  onColorChange,
  locale = 'en',
}: ColorCardProps) {
  const [copied, setCopied] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const shouldReduceMotion = useReducedMotion();
  const c = messages[locale].controls;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(color.hex);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleCopy();
    }
  };

  const isLightColor = color.oklch.l > 0.6;
  const textColor = isLightColor ? 'text-zinc-950' : 'text-zinc-50';
  const subTextColor = isLightColor ? 'text-zinc-700' : 'text-zinc-300';
  const badgeBg = isLightColor ? 'bg-black/10 border-black/20' : 'bg-white/10 border-white/20';

  const label = getPaletteColorLabel(color.role, index, totalColors, color.oklch);

  return (
    <motion.div
      initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className={`group relative flex flex-col rounded-2xl overflow-hidden shadow-xl border transition-all focus-visible:ring-2 focus-visible:ring-purple-400 focus-visible:outline-none cursor-pointer ${
        isLocked ? 'border-amber-400/70 ring-1 ring-amber-400/30' : 'border-white/10 hover:border-purple-500/40'
      }`}
      style={{
        backgroundColor: color.hex,
      }}
      role="button"
      tabIndex={0}
      onClick={handleCopy}
      onKeyDown={handleKeyDown}
      aria-label={`Copy ${label} color HEX code ${color.hex}`}
    >
      {/* Top Swatch Section */}
      <div className="p-5 flex flex-col justify-between min-h-[200px] relative">
        {/* Header Badges */}
        <div className="flex items-center justify-between">
          <span
            className={`px-3 py-1 rounded-full text-xs font-mono font-bold tracking-wider uppercase border backdrop-blur-xs ${textColor} ${badgeBg}`}
          >
            {label}
          </span>
          <div className="flex items-center gap-1.5">
            {onColorChange && (
              <label
                onClick={(e) => e.stopPropagation()}
                title={locale === 'ru' ? 'Изменить цвет' : 'Edit color'}
                className={`p-2 rounded-lg border backdrop-blur-md cursor-pointer transition-all hover:scale-105 ${badgeBg} ${textColor}`}
              >
                <input
                  type="color"
                  value={color.hex}
                  onChange={(e) => onColorChange(e.target.value)}
                  className="sr-only"
                  aria-label={locale === 'ru' ? `Изменить цвет ${label}` : `Edit ${label} color`}
                />
                <span className="text-[10px] font-mono font-bold">HEX</span>
              </label>
            )}
            {color.role === 'base' && (
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-purple-600 text-white font-bold shadow-md">
                {locale === 'ru' ? 'Базовый' : 'Primary Base'}
              </span>
            )}
            {onToggleLock && (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleLock();
                }}
                onKeyDown={(event) => event.stopPropagation()}
                aria-pressed={isLocked}
                aria-label={isLocked
                  ? (locale === 'ru' ? 'Открепить цвет' : `Unlock ${label}`)
                  : (locale === 'ru' ? 'Закрепить цвет' : `Lock ${label}`)}
                title={isLocked
                  ? (locale === 'ru' ? 'Открепить' : 'Unlock color')
                  : (locale === 'ru' ? 'Закрепить' : 'Lock color')}
                className={`p-2 rounded-lg border backdrop-blur-md transition-all ${
                  isLocked
                    ? 'bg-amber-400 text-zinc-950 border-amber-200 shadow-md'
                    : `${badgeBg} ${textColor} hover:scale-105`
                }`}
              >
                {isLocked ? <Lock className="w-3.5 h-3.5" /> : <LockOpen className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>
        </div>

        {/* Footer / Hex Display */}
        <div className="flex items-end justify-between mt-auto">
          <div>
            <p className={`text-xs font-mono font-semibold ${subTextColor} uppercase tracking-wider`}>
              HEX CODE
            </p>
            <h3 className={`text-2xl sm:text-3xl font-mono font-black ${textColor} tracking-tight`}>
              {color.hex.toUpperCase()}
            </h3>
          </div>

          {/* Copy Icon Visual Indicator */}
          <div
            className={`p-3 rounded-xl border backdrop-blur-md transition-all shadow-lg flex items-center justify-center ${
              isLightColor
                ? 'bg-black/15 group-hover:bg-black/25 text-black border-black/20'
                : 'bg-white/15 group-hover:bg-white/25 text-white border-white/20'
            }`}
          >
            <AnimatePresence mode="wait">
              {copied ? (
                <motion.div
                  key="check"
                  initial={{ scale: 0, rotate: -45 }}
                  animate={{ scale: 1, rotate: 0 }}
                  exit={{ scale: 0 }}
                  className="flex items-center gap-1 font-mono font-bold text-xs"
                >
                  <Check className="w-4 h-4 text-emerald-400" />
                </motion.div>
              ) : (
                <motion.div key="copy" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                  <Copy className="w-4 h-4" />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Copy Feedback Badge Overlay */}
        <AnimatePresence>
          {copied && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute inset-x-4 top-1/2 -translate-y-1/2 p-3 rounded-xl bg-zinc-950/95 border border-emerald-500/50 shadow-2xl flex items-center justify-center gap-2 pointer-events-none z-20"
            >
              <Check className="w-5 h-5 text-emerald-400" />
              <span className="text-xs font-mono font-bold text-emerald-300">
                {c.copied} {color.hex.toUpperCase()}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Expandable OKLCH Details Drawer */}
      <div
        className="bg-zinc-950/90 border-t border-white/10 p-3 text-white"
        onClick={(e) => e.stopPropagation()} // Stop copy trigger when toggling details
        onKeyDown={(e) => e.stopPropagation()}
      >
        <div
          role="button"
          tabIndex={0}
          onClick={() => setShowDetails(!showDetails)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setShowDetails(!showDetails);
            }
          }}
          className="w-full flex items-center justify-between text-xs font-mono text-gray-400 hover:text-purple-300 transition-colors py-1 cursor-pointer focus-visible:outline-none focus-visible:text-purple-300"
        >
          <span>OKLCH Data &amp; Metrics</span>
          {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>

        <AnimatePresence>
          {showDetails && (
            <motion.div
              initial={shouldReduceMotion ? { height: 'auto' } : { height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden pt-2 border-t border-white/5"
            >
              <div className="grid grid-cols-3 gap-2 text-[11px] font-mono text-gray-300">
                <div className="p-2 rounded bg-zinc-900/60 border border-white/5">
                  <span className="text-gray-500 block text-[10px]">LIGHTNESS (L)</span>
                  <span className="font-bold text-purple-300">
                    {(color.oklch.l * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="p-2 rounded bg-zinc-900/60 border border-white/5">
                  <span className="text-gray-500 block text-[10px]">CHROMA (C)</span>
                  <span className="font-bold text-purple-300">{color.oklch.c.toFixed(3)}</span>
                </div>
                <div className="p-2 rounded bg-zinc-900/60 border border-white/5">
                  <span className="text-gray-500 block text-[10px]">HUE (H)</span>
                  <span className="font-bold text-purple-300">
                    {color.oklch.h !== null ? `${color.oklch.h.toFixed(0)}°` : 'None'}
                  </span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
});
