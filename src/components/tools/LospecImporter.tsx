'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { hexToOklch, normalizeHex } from '@/lib/color/conversions';

interface LospecResult {
  name: string;
  author: string;
  colors: string[];
  lospecUrl: string;
  attribution: string;
}

function slugFromUrl(input: string): string | null {
  try {
    const url = new URL(input);
    if (url.hostname === 'lospec.com') {
      const parts = url.pathname.split('/').filter(Boolean);
      return parts[parts.length - 1] ?? null;
    }
  } catch {
    const cleaned = input.trim().toLowerCase().replace(/\.json$/, '');
    if (/^[a-z0-9-]{1,80}$/.test(cleaned)) return cleaned;
  }
  return null;
}

export function LospecImporter({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const isRu = locale === 'ru';
  const router = useRouter();

  const [input, setInput] = useState('');
  const [result, setResult] = useState<LospecResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copyMsg, setCopyMsg] = useState('');

  const EXAMPLES = ['db16', 'apollo', 'aap-64', 'nyx8', 'lospec500'];

  const fetchPalette = useCallback(async () => {
    const slug = slugFromUrl(input.trim());
    if (!slug) {
      setError(isRu ? 'Введите корректный URL Lospec или название палитры (например: db16 или apollo).' : 'Enter a valid Lospec URL or palette slug (e.g. db16 or apollo).');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`/api/lospec?slug=${encodeURIComponent(slug)}`);
      const data = await res.json() as LospecResult & { error?: string };
      if (!res.ok || data.error) {
        setError(data.error ?? `HTTP ${res.status}`);
        return;
      }
      setResult(data);
    } catch {
      setError(isRu ? 'Ошибка сети.' : 'Network error.');
    } finally {
      setLoading(false);
    }
  }, [input, isRu]);

  const copyHex = () => {
    if (!result) return;
    const hexes = result.colors.map(c => `#${c.toUpperCase()}`).join(' ');
    navigator.clipboard.writeText(hexes).then(() => {
      setCopyMsg(isRu ? 'Скопировано!' : 'Copied!');
      setTimeout(() => setCopyMsg(''), 1500);
    });
  };

  const openInStudio = () => {
    if (!result) return;
    const hexes = result.colors.map(c => `#${c}`);
    const base = hexes[Math.floor(hexes.length / 2)] ?? hexes[0] ?? '#5b21b6';
    const all = hexes.join(',');
    const href = isRu
      ? `/ru/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(all)}`
      : `/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(all)}`;
    router.push(href);
  };

  return (
    <div className="space-y-8">
      {/* Notice */}
      <div className="text-xs font-mono text-amber-400/80 glass-panel rounded-xl border border-amber-500/20 p-4 leading-relaxed">
        {isRu
          ? 'Неофициальный импорт. OKLCH Pixel Palette не аффилирован с Lospec. Все палитры принадлежат их авторам.'
          : 'Unofficial import. OKLCH Pixel Palette is not affiliated with Lospec. All palettes belong to their authors.'}
      </div>

      {/* Input */}
      <div className="space-y-3">
        <label htmlFor="lospec-input" className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
          {isRu ? 'URL Lospec или название (slug)' : 'Lospec URL or palette slug'}
        </label>
        <div className="flex gap-2">
          <input
            id="lospec-input"
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && fetchPalette()}
            placeholder="https://lospec.com/palette-list/db16 or db16"
            className="flex-1 glass-panel border border-white/15 rounded-xl px-4 py-2 text-sm font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-purple-500/60 bg-transparent"
            spellCheck={false}
          />
          <button
            onClick={fetchPalette}
            disabled={loading || !input.trim()}
            className="px-4 py-2 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 shadow-md whitespace-nowrap"
          >
            {loading ? (isRu ? 'Загрузка...' : 'Loading...') : (isRu ? 'Загрузить' : 'Load')}
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <span className="text-[10px] font-mono text-gray-600">{isRu ? 'Примеры:' : 'Examples:'}</span>
          {EXAMPLES.map(ex => (
            <button
              key={ex}
              onClick={() => setInput(ex)}
              className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 border border-white/10 hover:border-purple-500/30 text-gray-500 hover:text-gray-300 transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="text-xs font-mono text-red-400 glass-panel rounded-xl border border-red-500/20 p-4">
          ✕ {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="glass-panel rounded-2xl border border-white/10 p-6 space-y-5">
          <div className="space-y-1">
            <h3 className="text-base font-mono font-bold text-white">{result.name}</h3>
            <p className="text-xs font-mono text-gray-500">
              {isRu ? 'Автор:' : 'Author:'}{' '}
              <a href={result.lospecUrl} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline underline-offset-2">
                {result.author}
              </a>
              {' '}({result.colors.length} {isRu ? 'цветов' : 'colors'})
            </p>
          </div>

          {/* Palette bar */}
          <div className="flex rounded-xl overflow-hidden border border-white/10 h-14">
            {result.colors.map((c, i) => (
              <div key={i} className="flex-1" style={{ backgroundColor: `#${c}` }} title={`#${c.toUpperCase()}`} />
            ))}
          </div>

          {/* Swatches + OKLCH */}
          <div className="flex flex-wrap gap-2">
            {result.colors.map((c, i) => {
              const hex = normalizeHex(`#${c}`) ?? `#${c}`;
              const oklch = hexToOklch(hex);
              return (
                <div key={i} className="flex flex-col items-center gap-0.5">
                  <div className="w-9 h-9 rounded-lg border border-white/15" style={{ backgroundColor: hex }} title={hex} />
                  <span className="text-[8px] font-mono text-gray-600">{hex.toUpperCase()}</span>
                  {oklch && <span className="text-[7px] font-mono text-gray-700">L:{(oklch.l * 100).toFixed(0)}%</span>}
                </div>
              );
            })}
          </div>

          {/* Attribution notice */}
          <p className="text-[10px] font-mono text-gray-600 border-t border-white/5 pt-3">
            {result.attribution}
          </p>

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={copyHex}
              className="px-4 py-1.5 text-xs font-mono text-white bg-white/10 hover:bg-white/15 rounded-lg border border-white/15 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {copyMsg || (isRu ? 'Копировать HEX' : 'Copy HEX')}
            </button>
            <button
              onClick={openInStudio}
              className="px-4 py-1.5 text-xs font-mono text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 shadow-md"
            >
              {isRu ? 'Открыть в студии' : 'Open in Studio'}
            </button>
            <a
              href={result.lospecUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-1.5 text-xs font-mono text-gray-400 hover:text-gray-200 rounded-lg border border-white/10 hover:border-white/20 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {isRu ? 'На Lospec →' : 'View on Lospec →'}
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
