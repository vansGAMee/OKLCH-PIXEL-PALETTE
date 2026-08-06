'use client';

import React from 'react';
import { HarmonyMode } from '@/types/palette';
import { Locale, messages } from '@/i18n/messages';
import { Compass, Sparkles, Spline, Orbit } from 'lucide-react';

interface HarmonySelectorProps {
  harmony: HarmonyMode;
  onChange: (mode: HarmonyMode) => void;
  locale?: Locale;
}

const HARMONY_ICONS: Record<HarmonyMode, React.ReactNode> = {
  splitComplementary: <Sparkles className="w-4 h-4" />,
  complementary: <Orbit className="w-4 h-4" />,
  analogous: <Spline className="w-4 h-4" />,
  triadic: <Compass className="w-4 h-4" />,
  tetradic: <Orbit className="w-4 h-4" />,
  monochromatic: <Spline className="w-4 h-4" />,
};

export const HarmonySelector: React.FC<HarmonySelectorProps> = ({
  harmony,
  onChange,
  locale = 'en',
}) => {
  const t = messages[locale].controls;

  const options: { id: HarmonyMode; title: string; desc: string }[] = [
    {
      id: 'splitComplementary',
      title: t.harmonies.splitComplementary,
      desc: locale === 'ru' ? 'Сбалансированный контраст' : 'Dynamic & Balanced',
    },
    {
      id: 'complementary',
      title: t.harmonies.complementary,
      desc: locale === 'ru' ? 'Высокий контраст' : 'High Contrast Accent',
    },
    {
      id: 'analogous',
      title: t.harmonies.analogous,
      desc: locale === 'ru' ? 'Плавные переходы' : 'Smooth & Harmonious',
    },
  ];

  return (
    <div className="glass-panel rounded-xl p-5 border border-white/10 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-widest text-gray-200 uppercase">
              {t.harmonyTitle}
            </h3>
            <p className="text-[11px] text-gray-400 font-mono">Accent Generation Mode</p>
          </div>
        </div>
      </div>

      {/* Segmented Control Options */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {options.map((opt) => {
          const isActive = harmony === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onChange(opt.id)}
              className={`p-3 rounded-xl border text-left transition-all relative overflow-hidden flex flex-col justify-between cursor-pointer ${
                isActive
                  ? 'bg-purple-600/20 border-purple-500 shadow-lg shadow-purple-900/30 text-white'
                  : 'bg-zinc-900/60 border-white/10 text-gray-400 hover:text-gray-200 hover:border-white/25'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono font-bold uppercase truncate">{opt.title}</span>
                <span className={isActive ? 'text-purple-300' : 'text-gray-500'}>
                  {HARMONY_ICONS[opt.id]}
                </span>
              </div>
              <span className="text-[10px] font-mono text-gray-400 block truncate">{opt.desc}</span>

              {isActive && (
                <div className="absolute bottom-0 inset-x-0 h-0.5 bg-purple-400 shadow-sm" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
