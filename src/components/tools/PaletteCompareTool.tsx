'use client';

import { useState, useCallback } from 'react';
import { comparePalettes, type PaletteComparison } from '@/lib/tools/paletteCompare';

const EXAMPLE_A = '#172033 #20283A #5F718A #C084FC #F43F5E';
const EXAMPLE_B = '#0d1f0a #1a3d14 #3a7a30 #7cc46c #c8f0a4';

function MetricRow({ label, a, b }: { label: string; a: string; b: string }) {
  return (
    <div className="grid grid-cols-3 gap-2 py-2 border-b border-white/5 last:border-0 text-xs font-mono">
      <span className="text-gray-500">{label}</span>
      <span className="text-blue-300 text-right">{a}</span>
      <span className="text-emerald-300 text-right">{b}</span>
    </div>
  );
}

function SwatchRow({ colors, accent }: { colors: { hex: string }[]; accent: 'blue' | 'green' }) {
  const ring = accent === 'blue' ? 'ring-blue-500/40' : 'ring-emerald-500/40';
  return (
    <div className={`flex flex-wrap gap-1.5 p-2 rounded-xl bg-black/20 ring-1 ${ring}`}>
      {colors.map((c, i) => (
        <div
          key={i}
          className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg border border-white/10"
          style={{ backgroundColor: c.hex }}
          title={c.hex.toUpperCase()}
        />
      ))}
    </div>
  );
}

export function PaletteCompareTool({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const isRu = locale === 'ru';
  const [inputA, setInputA] = useState('');
  const [inputB, setInputB] = useState('');
  const [comparison, setComparison] = useState<PaletteComparison | null>(null);

  const analyze = useCallback(() => {
    if (!inputA.trim() || !inputB.trim()) return;
    setComparison(comparePalettes(inputA, inputB));
  }, [inputA, inputB]);

  const loadExample = () => {
    setInputA(EXAMPLE_A);
    setInputB(EXAMPLE_B);
  };

  const pct = (n: number) => `${(n * 100).toFixed(0)}%`;
  const fmt = (n: number) => n.toFixed(3);

  return (
    <div className="space-y-8">
      {/* Inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label htmlFor="palette-a" className="text-xs font-mono font-bold text-blue-300 block">
            {isRu ? 'Палитра A' : 'Palette A'}
          </label>
          <textarea
            id="palette-a"
            value={inputA}
            onChange={e => setInputA(e.target.value)}
            placeholder={EXAMPLE_A}
            className="w-full h-20 glass-panel border border-blue-500/20 rounded-xl px-4 py-3 text-xs font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 resize-none bg-transparent"
            spellCheck={false}
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="palette-b" className="text-xs font-mono font-bold text-emerald-300 block">
            {isRu ? 'Палитра B' : 'Palette B'}
          </label>
          <textarea
            id="palette-b"
            value={inputB}
            onChange={e => setInputB(e.target.value)}
            placeholder={EXAMPLE_B}
            className="w-full h-20 glass-panel border border-emerald-500/20 rounded-xl px-4 py-3 text-xs font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 resize-none bg-transparent"
            spellCheck={false}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={analyze}
          disabled={!inputA.trim() || !inputB.trim()}
          className="px-5 py-2 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 shadow-md"
        >
          {isRu ? 'Сравнить' : 'Compare'}
        </button>
        <button
          onClick={loadExample}
          className="px-4 py-2 text-xs font-mono text-gray-400 hover:text-gray-200 rounded-xl border border-white/10 hover:border-white/20 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          {isRu ? 'Загрузить пример' : 'Load example'}
        </button>
      </div>

      {/* Comparison result */}
      {comparison && (
        <section className="space-y-6" aria-live="polite" aria-label={isRu ? 'Результат сравнения' : 'Comparison result'}>
          {/* Swatches */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="text-xs font-mono text-blue-300">{isRu ? 'Палитра A' : 'Palette A'} ({comparison.paletteA.uniqueColors})</div>
              <SwatchRow colors={comparison.paletteA.colors} accent="blue" />
            </div>
            <div className="space-y-2">
              <div className="text-xs font-mono text-emerald-300">{isRu ? 'Палитра B' : 'Palette B'} ({comparison.paletteB.uniqueColors})</div>
              <SwatchRow colors={comparison.paletteB.colors} accent="green" />
            </div>
          </div>

          {/* Metric table */}
          <div className="glass-panel rounded-2xl border border-white/10 p-5 space-y-1">
            <div className="grid grid-cols-3 gap-2 py-1.5 text-[10px] font-mono text-gray-600 uppercase tracking-wider">
              <span>{isRu ? 'Метрика' : 'Metric'}</span>
              <span className="text-right">{isRu ? 'Палитра A' : 'Palette A'}</span>
              <span className="text-right">{isRu ? 'Палитра B' : 'Palette B'}</span>
            </div>
            <MetricRow
              label={isRu ? 'Диапазон L' : 'L range'}
              a={pct(comparison.paletteA.lightnessRange)}
              b={pct(comparison.paletteB.lightnessRange)}
            />
            <MetricRow
              label={isRu ? 'Средняя L' : 'Avg L'}
              a={pct(comparison.paletteA.avgLightness)}
              b={pct(comparison.paletteB.avgLightness)}
            />
            <MetricRow
              label={isRu ? 'Диапазон C' : 'C range'}
              a={fmt(comparison.paletteA.chromaRange)}
              b={fmt(comparison.paletteB.chromaRange)}
            />
            <MetricRow
              label={isRu ? 'Средняя C' : 'Avg C'}
              a={fmt(comparison.paletteA.avgChroma)}
              b={fmt(comparison.paletteB.avgChroma)}
            />
            <MetricRow
              label={isRu ? 'Охват тона' : 'Hue span'}
              a={comparison.paletteA.hueSpan > 0 ? `${comparison.paletteA.hueSpan.toFixed(0)}°` : 'neutral'}
              b={comparison.paletteB.hueSpan > 0 ? `${comparison.paletteB.hueSpan.toFixed(0)}°` : 'neutral'}
            />
            <MetricRow
              label={isRu ? 'Кол-во цветов' : 'Color count'}
              a={String(comparison.paletteA.uniqueColors)}
              b={String(comparison.paletteB.uniqueColors)}
            />
          </div>

          {/* ΔE between palettes */}
          <div className="glass-panel rounded-xl border border-white/10 p-4 space-y-1">
            <div className="text-xs font-mono text-gray-400">
              {isRu ? 'Среднее ближайшее ΔE (A→B)' : 'Avg nearest ΔE (A→B)'}
            </div>
            <div className="text-lg font-mono font-bold text-white">
              {(comparison.avgNearestDE * 100).toFixed(2)}
            </div>
            <div className="text-[10px] font-mono text-gray-600">
              {isRu
                ? 'Среднее перцептуальное расстояние от каждого цвета A до ближайшего цвета B.'
                : 'Average perceptual distance from each color in A to its nearest color in B.'}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
