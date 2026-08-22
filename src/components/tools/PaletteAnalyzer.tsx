'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { parseHexInput, analyzePalette, fixPalette, type PaletteDoctorReport, type AnalyzedColor } from '@/lib/tools/paletteDoctor';

const PLACEHOLDER = '#172033 #20283A #5F718A #C084FC #F43F5E';

const EXAMPLE_INPUTS = [
  { label: 'Forest (good)', value: '#0d1f0a #1a3d14 #3a7a30 #7cc46c #c8f0a4 #f2fad8' },
  { label: 'Flat grays (narrow L)', value: '#4a4a4a #5a5a5a #6a6a6a #7a7a7a' },
  { label: 'Near-dups warning', value: '#2d1b4e #2e1d50 #6b2fb4 #c084fc #f43f5e' },
];

function ColorSwatch({ hex, oklch }: { hex: string; oklch?: { l: number; c: number; h: number | null } }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(hex).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  };

  return (
    <button
      onClick={copy}
      className="flex flex-col items-center gap-1 group focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg p-1"
      title={`Copy ${hex}`}
      aria-label={`Copy color ${hex}`}
    >
      <div
        className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg border-2 border-white/10 group-hover:border-purple-500/50 transition-colors shadow-md"
        style={{ backgroundColor: hex }}
      />
      <span className="text-[9px] sm:text-[10px] font-mono text-gray-500 group-hover:text-gray-300 transition-colors">
        {copied ? '✓' : hex.toUpperCase()}
      </span>
      {oklch && (
        <span className="text-[8px] font-mono text-gray-600 hidden sm:block">
          L:{(oklch.l * 100).toFixed(0)} C:{oklch.c.toFixed(2)}
        </span>
      )}
    </button>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
    : score >= 60 ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
    : 'text-red-400 border-red-500/30 bg-red-500/10';

  const label = score >= 80 ? 'Healthy' : score >= 60 ? 'Fair' : 'Needs work';

  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border font-mono ${color}`}>
      <span className="text-2xl font-black">{score}</span>
      <div>
        <div className="text-xs font-bold">/100</div>
        <div className="text-[10px] opacity-80">{label}</div>
      </div>
    </div>
  );
}

function IssueLine({ severity, message, colorIndices, swatches }: {
  severity: string; message: string; colorIndices?: number[]; swatches?: AnalyzedColor[]
}) {
  const icon = severity === 'ok' ? '✓' : severity === 'warning' ? '⚠' : '✕';
  const cls = severity === 'ok' ? 'text-emerald-400' : severity === 'warning' ? 'text-amber-400' : 'text-red-400';

  return (
    <li className="flex items-start gap-2 py-1.5">
      <span className={`mt-0.5 font-mono text-sm shrink-0 ${cls}`}>{icon}</span>
      <div className="flex-1 min-w-0">
        <span className="text-xs text-gray-300 font-sans">{message}</span>
        {colorIndices && swatches && colorIndices.length > 0 && (
          <div className="flex gap-1 mt-1">
            {colorIndices.map(i => swatches[i] && (
              <div key={i} className="w-4 h-4 rounded border border-white/20" style={{ backgroundColor: swatches[i].hex }} title={swatches[i].hex} />
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

export function PaletteAnalyzer({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const router = useRouter();
  const [input, setInput] = useState('');
  const [report, setReport] = useState<PaletteDoctorReport | null>(null);
  const [fixedColors, setFixedColors] = useState<AnalyzedColor[] | null>(null);
  const [showFixed, setShowFixed] = useState(false);
  const [copyMsg, setCopyMsg] = useState('');

  const isRu = locale === 'ru';

  const analyze = useCallback(() => {
    const { colors, errors } = parseHexInput(input);
    if (colors.length === 0) return;
    const result = analyzePalette(colors);
    result.parseErrors.push(...errors);
    setReport(result);
    setFixedColors(null);
    setShowFixed(false);
  }, [input]);

  const applyFix = useCallback(() => {
    if (!report) return;
    const fixed = fixPalette(report);
    setFixedColors(fixed);
    setShowFixed(true);
  }, [report]);

  const copyHex = (colors: AnalyzedColor[]) => {
    navigator.clipboard.writeText(colors.map(c => c.hex.toUpperCase()).join(' ')).then(() => {
      setCopyMsg(isRu ? 'Скопировано!' : 'Copied!');
      setTimeout(() => setCopyMsg(''), 1500);
    });
  };

  const openInStudio = (colors: AnalyzedColor[]) => {
    const base = colors[0]?.hex ?? '#5b21b6';
    const allHex = colors.map(c => c.hex).join(',');
    const href = isRu
      ? `/ru/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(allHex)}`
      : `/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(allHex)}`;
    router.push(href);
  };

  return (
    <div className="space-y-8">
      {/* Input Area */}
      <section className="space-y-3">
        <label htmlFor="palette-input" className="text-sm font-mono font-bold text-white block">
          {isRu ? 'Введите цвета (HEX)' : 'Paste your palette (HEX colors)'}
        </label>
        <textarea
          id="palette-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={PLACEHOLDER}
          className="w-full h-24 glass-panel border border-white/15 rounded-xl px-4 py-3 text-sm font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-purple-500/60 focus:ring-1 focus:ring-purple-500/40 resize-y bg-transparent"
          aria-label={isRu ? 'Поле ввода цветов HEX для анализа' : 'HEX color input for palette analysis'}
          spellCheck={false}
        />
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={analyze}
            disabled={!input.trim()}
            className="px-5 py-2 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 shadow-md shadow-purple-900/30"
          >
            {isRu ? 'Анализировать' : 'Analyze'}
          </button>
          <span className="text-xs font-mono text-gray-500">
            {isRu ? 'Примеры:' : 'Examples:'}
          </span>
          {EXAMPLE_INPUTS.map(ex => (
            <button
              key={ex.label}
              onClick={() => setInput(ex.value)}
              className="text-xs font-mono px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 hover:border-purple-500/40 text-gray-400 hover:text-gray-200 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {ex.label}
            </button>
          ))}
        </div>
      </section>

      {/* Report */}
      {report && (
        <section className="space-y-6" aria-live="polite" aria-label={isRu ? 'Результат анализа палитры' : 'Palette analysis result'}>
          {/* Parse errors */}
          {report.parseErrors.length > 0 && (
            <div className="text-xs font-mono text-amber-400 glass-panel rounded-xl border border-amber-500/20 p-4 space-y-1">
              {report.parseErrors.map((e, i) => <div key={i}>⚠ {e}</div>)}
            </div>
          )}

          {/* Score + colors */}
          <div className="glass-panel rounded-2xl border border-white/10 p-6 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-mono font-bold text-white mb-1">
                  {isRu ? 'Здоровье палитры' : 'Palette Health'}
                </h3>
                <p className="text-xs text-gray-500 font-mono">
                  {isRu
                    ? 'Диагностическая оценка сайта, основанная на измеренных факторах.'
                    : "Site's own diagnostic score based on measured factors."}
                </p>
              </div>
              <ScoreBadge score={report.healthScore} />
            </div>

            {/* Color display */}
            <div>
              <div className="text-xs font-mono text-gray-500 mb-2">{isRu ? 'Цвета' : 'Colors'} ({report.colors.length})</div>
              <div className="flex flex-wrap gap-2">
                {report.colors.map((c, i) => (
                  <ColorSwatch key={i} hex={c.hex} oklch={c.oklch} />
                ))}
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: isRu ? 'Диапазон L' : 'L range', value: `${(report.lightnessRange * 100).toFixed(0)}%` },
                { label: isRu ? 'Диапазон C' : 'C range', value: report.chromaRange.toFixed(3) },
                { label: isRu ? 'Охват тона' : 'Hue span', value: report.hueSpan > 0 ? `${report.hueSpan.toFixed(0)}°` : 'neutral' },
              ].map(({ label, value }) => (
                <div key={label} className="glass-panel rounded-lg border border-white/10 p-3 text-center">
                  <div className="text-base font-mono font-bold text-white">{value}</div>
                  <div className="text-[10px] font-mono text-gray-500 mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Issues */}
          <div className="glass-panel rounded-2xl border border-white/10 p-6 space-y-3">
            <h3 className="text-sm font-mono font-bold text-white">
              {isRu ? 'Диагностика' : 'Diagnostics'}
            </h3>
            <ul className="space-y-0.5 divide-y divide-white/5">
              {report.issues.map(issue => (
                <IssueLine
                  key={issue.id}
                  severity={issue.severity}
                  message={issue.message}
                  colorIndices={issue.colorIndices}
                  swatches={report.colors}
                />
              ))}
            </ul>
          </div>

          {/* Fix / Before-After */}
          {report.healthScore < 100 && (
            <div className="space-y-4">
              {!showFixed ? (
                <button
                  onClick={applyFix}
                  className="px-5 py-2 text-sm font-mono font-bold text-white bg-emerald-700 hover:bg-emerald-600 rounded-xl transition-all focus:outline-none focus:ring-2 focus:ring-emerald-400 shadow-md"
                >
                  {isRu ? 'Исправить с OKLCH' : 'Fix with OKLCH'}
                </button>
              ) : fixedColors && (
                <div className="glass-panel rounded-2xl border border-emerald-500/20 p-6 space-y-4">
                  <h3 className="text-sm font-mono font-bold text-white">
                    {isRu ? 'До → После' : 'Before → After'}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <div className="text-xs font-mono text-gray-500">{isRu ? 'Оригинал' : 'Original'}</div>
                      <div className="flex flex-wrap gap-2">
                        {report.colors.map((c, i) => <ColorSwatch key={i} hex={c.hex} oklch={c.oklch} />)}
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="text-xs font-mono text-emerald-400">{isRu ? 'Исправлено' : 'Fixed'}</div>
                      <div className="flex flex-wrap gap-2">
                        {fixedColors.map((c, i) => <ColorSwatch key={i} hex={c.hex} oklch={c.oklch} />)}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 pt-2">
                    <button
                      onClick={() => copyHex(fixedColors)}
                      className="px-4 py-1.5 text-xs font-mono text-white bg-white/10 hover:bg-white/15 rounded-lg transition-all border border-white/15 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    >
                      {copyMsg || (isRu ? 'Копировать HEX' : 'Copy HEX')}
                    </button>
                    <button
                      onClick={() => openInStudio(fixedColors)}
                      className="px-4 py-1.5 text-xs font-mono text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-400"
                    >
                      {isRu ? 'Открыть в студии' : 'Open in Studio'}
                    </button>
                    <button
                      onClick={() => setShowFixed(false)}
                      className="text-xs font-mono text-gray-500 hover:text-gray-300 transition-colors underline underline-offset-2"
                    >
                      {isRu ? 'Сбросить' : 'Reset'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Export original */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => copyHex(report.colors)}
              className="px-4 py-1.5 text-xs font-mono text-white bg-white/8 hover:bg-white/12 rounded-lg transition-all border border-white/10 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {copyMsg || (isRu ? 'Копировать' : 'Copy HEX')}
            </button>
            <button
              onClick={() => openInStudio(report.colors)}
              className="px-4 py-1.5 text-xs font-mono text-purple-300 hover:text-purple-200 rounded-lg transition-all border border-purple-500/20 hover:border-purple-500/40 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {isRu ? 'Открыть в студии' : 'Open in Studio'}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
