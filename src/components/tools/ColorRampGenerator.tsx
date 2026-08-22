'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { generateRamp, applyPreset, generateDefaultConfig, rampToHexList, type GeneratedRamp, type RampConfig, type RampPreset } from '@/lib/tools/rampGenerator';
import { normalizeHex } from '@/lib/color/conversions';

const PRESETS: { id: RampPreset; label: string; labelRu: string }[] = [
  { id: 'neutral', label: 'Neutral', labelRu: 'Нейтральный' },
  { id: 'warm',    label: 'Warm light', labelRu: 'Тёплый свет' },
  { id: 'cool',    label: 'Cool light', labelRu: 'Холодный свет' },
  { id: 'vivid',   label: 'Vivid', labelRu: 'Насыщенный' },
];

const STEP_OPTIONS = [3, 4, 5, 6, 7, 8, 9];

const EXAMPLE_BASES = [
  { hex: '#5b21b6', label: 'Purple' },
  { hex: '#b45309', label: 'Amber' },
  { hex: '#0f766e', label: 'Teal' },
  { hex: '#be185d', label: 'Rose' },
  { hex: '#1d4ed8', label: 'Blue' },
  { hex: '#15803d', label: 'Green' },
];

export function ColorRampGenerator({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const isRu = locale === 'ru';
  const router = useRouter();

  const [config, setConfig] = useState<RampConfig>(() => generateDefaultConfig());
  const [ramp, setRamp] = useState<GeneratedRamp | null>(() => generateRamp(generateDefaultConfig()));
  const [hexInput, setHexInput] = useState('#5b21b6');
  const [copyMsg, setCopyMsg] = useState('');

  const update = useCallback((next: Partial<RampConfig>) => {
    setConfig(prev => {
      const merged = { ...prev, ...next };
      const result = generateRamp(merged);
      setRamp(result);
      return merged;
    });
  }, []);

  const handleBaseInput = (raw: string) => {
    setHexInput(raw);
    const norm = normalizeHex(raw.startsWith('#') ? raw : `#${raw}`);
    if (norm) update({ baseHex: norm });
  };

  const handlePreset = (id: RampPreset) => {
    const next = applyPreset(config, id);
    setConfig(next);
    setRamp(generateRamp(next));
  };

  const copyHex = () => {
    if (!ramp) return;
    navigator.clipboard.writeText(rampToHexList(ramp)).then(() => {
      setCopyMsg(isRu ? 'Скопировано!' : 'Copied!');
      setTimeout(() => setCopyMsg(''), 1500);
    });
  };

  const openInStudio = () => {
    if (!ramp) return;
    const base = ramp.colors[Math.floor(ramp.colors.length / 2)]?.hex ?? config.baseHex;
    const all = ramp.colors.map(c => c.hex).join(',');
    const href = isRu
      ? `/ru/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(all)}`
      : `/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(all)}`;
    router.push(href);
  };

  return (
    <div className="space-y-8">
      {/* Controls */}
      <section className="glass-panel rounded-2xl border border-white/10 p-6 space-y-6">
        {/* Base color */}
        <div className="space-y-2">
          <label className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
            {isRu ? 'Базовый цвет' : 'Base color'}
          </label>
          <div className="flex items-center gap-3">
            <input
              type="color"
              value={normalizeHex(config.baseHex) ?? '#5b21b6'}
              onChange={e => { setHexInput(e.target.value); update({ baseHex: e.target.value }); }}
              className="w-10 h-10 rounded-lg border border-white/20 bg-transparent cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-500"
              aria-label={isRu ? 'Выбор базового цвета' : 'Base color picker'}
            />
            <input
              type="text"
              value={hexInput}
              onChange={e => handleBaseInput(e.target.value)}
              className="w-36 glass-panel border border-white/15 rounded-lg px-3 py-1.5 text-sm font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-purple-500/60"
              placeholder="#5b21b6"
              aria-label={isRu ? 'Ввод HEX базового цвета' : 'Base color hex input'}
              spellCheck={false}
            />
          </div>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {EXAMPLE_BASES.map(ex => (
              <button
                key={ex.hex}
                onClick={() => { setHexInput(ex.hex); update({ baseHex: ex.hex }); }}
                className="flex items-center gap-1.5 px-2 py-1 text-xs font-mono rounded-lg bg-white/5 border border-white/10 hover:border-purple-500/30 text-gray-400 hover:text-gray-200 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                <span className="w-3 h-3 rounded-full border border-white/20" style={{ backgroundColor: ex.hex }} />
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        {/* Steps */}
        <div className="space-y-2">
          <label className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
            {isRu ? 'Количество шагов' : 'Steps'} ({config.count})
          </label>
          <div className="flex flex-wrap gap-2">
            {STEP_OPTIONS.map(n => (
              <button
                key={n}
                onClick={() => update({ count: n })}
                className={`w-9 h-9 rounded-lg text-sm font-mono font-bold transition-all focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                  config.count === n
                    ? 'bg-purple-600 text-white shadow-md shadow-purple-900/30'
                    : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:border-purple-500/30'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        {/* Presets */}
        <div className="space-y-2">
          <label className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
            {isRu ? 'Пресет' : 'Preset'}
          </label>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map(p => (
              <button
                key={p.id}
                onClick={() => handlePreset(p.id)}
                className={`px-3 py-1.5 text-xs font-mono rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                  config.preset === p.id
                    ? 'bg-purple-600 text-white'
                    : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:border-purple-500/30'
                }`}
              >
                {isRu ? p.labelRu : p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Hue shift slider */}
        <div className="space-y-2">
          <label htmlFor="hue-shift" className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
            {isRu ? 'Сдвиг тона теней' : 'Shadow hue shift'} ({config.hueShiftDeg > 0 ? '+' : ''}{config.hueShiftDeg}°)
          </label>
          <input
            id="hue-shift"
            type="range"
            min={-30}
            max={30}
            step={2}
            value={config.hueShiftDeg}
            onChange={e => update({ hueShiftDeg: Number(e.target.value) })}
            className="w-full accent-purple-500"
            aria-label={isRu ? 'Сдвиг тона для теней' : 'Hue shift for shadows'}
          />
          <div className="flex justify-between text-[10px] font-mono text-gray-600">
            <span>{isRu ? '← холоднее' : '← cooler'}</span>
            <span>0</span>
            <span>{isRu ? 'теплее →' : 'warmer →'}</span>
          </div>
        </div>
      </section>

      {/* Ramp output */}
      {ramp && (
        <section className="space-y-4" aria-live="polite" aria-label={isRu ? 'Сгенерированный рамп' : 'Generated ramp'}>
          {/* Horizontal ramp bar */}
          <div className="rounded-2xl overflow-hidden border border-white/10 shadow-2xl flex" style={{ height: '72px' }}>
            {ramp.colors.map((c, i) => (
              <div
                key={i}
                className="flex-1"
                style={{ backgroundColor: c.hex }}
                title={`Step ${i + 1}: ${c.hex.toUpperCase()} — L:${(c.oklch.l * 100).toFixed(1)}%`}
              />
            ))}
          </div>

          {/* Swatch grid with details */}
          <div className="flex flex-wrap gap-3 justify-center sm:justify-start">
            {ramp.colors.map((c, i) => (
              <div key={i} className="flex flex-col items-center gap-1 text-center">
                <div
                  className={`w-12 h-12 rounded-xl border-2 shadow-md transition-all ${c.isMidpoint ? 'border-purple-500/60 ring-1 ring-purple-500/30' : 'border-white/10'}`}
                  style={{ backgroundColor: c.hex }}
                  title={c.hex.toUpperCase()}
                />
                <span className="text-[9px] font-mono text-gray-500">{c.hex.toUpperCase()}</span>
                <span className="text-[8px] font-mono text-gray-700">L:{(c.oklch.l * 100).toFixed(0)}%</span>
                {c.isMidpoint && (
                  <span className="text-[8px] font-mono text-purple-400">base</span>
                )}
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={copyHex}
              className="px-4 py-1.5 text-xs font-mono text-white bg-white/10 hover:bg-white/15 rounded-lg border border-white/15 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {copyMsg || (isRu ? 'Копировать HEX' : 'Copy HEX')}
            </button>
            <button
              onClick={openInStudio}
              className="px-4 py-1.5 text-xs font-mono text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 shadow-md shadow-purple-900/30"
            >
              {isRu ? 'Открыть в студии' : 'Open in Studio'}
            </button>
          </div>

          {/* Hex list */}
          <div className="text-xs font-mono text-gray-600 break-all">
            {rampToHexList(ramp)}
          </div>
        </section>
      )}
    </div>
  );
}
