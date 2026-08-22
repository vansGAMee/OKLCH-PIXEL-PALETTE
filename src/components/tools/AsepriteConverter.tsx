'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { hexToOklch, normalizeHex } from '@/lib/color/conversions';
import {
  generateGplString,
  generateJascPalString,
  generateHexListString,
  generateCssString,
  generateJsonString,
  generateTailwindConfigString,
  generateDesignTokensJson,
  downloadTextFile,
  sanitizeFilename,
} from '@/lib/color/exporters';
import type { Palette, PaletteColor } from '@/types/palette';

const DEFAULT_HEXES = '#1e1b4b #311b92 #5b21b6 #7c3aed #a855f7 #c084fc #f43f5e';

export function AsepriteConverter({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const isRu = locale === 'ru';
  const router = useRouter();

  const [input, setInput] = useState(DEFAULT_HEXES);
  const [paletteName, setPaletteName] = useState('aseprite-palette');
  const [activeTab, setActiveTab] = useState<'pal' | 'gpl' | 'hex' | 'css' | 'tailwind' | 'tokens' | 'json'>('pal');
  const [copied, setCopied] = useState(false);

  const parsedColors: PaletteColor[] = input
    .replace(/[,;\n\r\t]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .flatMap((t, idx) => {
      const hex = normalizeHex(t.startsWith('#') ? t : `#${t}`);
      if (!hex) return [];
      const oklch = hexToOklch(hex) ?? { l: 0.5, c: 0, h: null };
      return [{
        role: idx === 0 ? 'shadow' : idx === 1 ? 'base' : idx === 2 ? 'highlight' : idx === 3 ? 'accent' : `color${idx + 1}`,
        hex,
        oklch,
      }];
    });

  const paletteLike: Palette = {
    colors: parsedColors,
    count: parsedColors.length,
    shadow: parsedColors[0] ?? { role: 'shadow', hex: '#000000', oklch: { l: 0, c: 0, h: null } },
    base: parsedColors[1] ?? parsedColors[0],
    highlight: parsedColors[2] ?? parsedColors[0],
    accent: parsedColors[3] ?? parsedColors[0],
    harmony: 'splitComplementary',
    seed: 0,
  };

  let outputText = '';
  let outputExt = 'pal';
  let outputMime = 'text/plain';

  switch (activeTab) {
    case 'pal':
      outputText = generateJascPalString(paletteLike);
      outputExt = 'pal';
      outputMime = 'text/plain';
      break;
    case 'gpl':
      outputText = generateGplString(paletteLike);
      outputExt = 'gpl';
      outputMime = 'text/plain';
      break;
    case 'hex':
      outputText = generateHexListString(paletteLike);
      outputExt = 'hex';
      outputMime = 'text/plain';
      break;
    case 'css':
      outputText = generateCssString(paletteLike);
      outputExt = 'css';
      outputMime = 'text/css';
      break;
    case 'tailwind':
      outputText = generateTailwindConfigString(paletteLike);
      outputExt = 'json';
      outputMime = 'application/json';
      break;
    case 'tokens':
      outputText = generateDesignTokensJson(paletteLike);
      outputExt = 'json';
      outputMime = 'application/json';
      break;
    case 'json':
      outputText = generateJsonString(paletteLike, locale);
      outputExt = 'json';
      outputMime = 'application/json';
      break;
  }

  const handleDownload = () => {
    const filename = `${sanitizeFilename(paletteName)}.${outputExt}`;
    downloadTextFile(filename, outputText, outputMime);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(outputText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const openInStudio = () => {
    if (parsedColors.length === 0) return;
    const base = parsedColors[0].hex;
    const all = parsedColors.map(c => c.hex).join(',');
    const href = isRu
      ? `/ru/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(all)}`
      : `/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(all)}`;
    router.push(href);
  };

  return (
    <div className="space-y-8">
      {/* Input */}
      <section className="glass-panel rounded-2xl border border-white/10 p-6 space-y-4">
        <div className="space-y-2">
          <label htmlFor="aseprite-colors" className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
            {isRu ? 'Цвета палитры (HEX)' : 'Palette colors (HEX)'}
          </label>
          <textarea
            id="aseprite-colors"
            value={input}
            onChange={e => setInput(e.target.value)}
            className="w-full h-24 glass-panel border border-white/15 rounded-xl px-4 py-3 text-sm font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-purple-500/60 bg-transparent resize-y"
            placeholder="#1e1b4b #311b92 #5b21b6..."
            spellCheck={false}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <label htmlFor="palette-name" className="text-xs font-mono text-gray-400">
              {isRu ? 'Имя файла:' : 'File name:'}
            </label>
            <input
              id="palette-name"
              type="text"
              value={paletteName}
              onChange={e => setPaletteName(e.target.value)}
              className="glass-panel border border-white/15 rounded-lg px-3 py-1 text-xs font-mono text-gray-200 focus:outline-none focus:border-purple-500/60 bg-transparent"
              spellCheck={false}
            />
          </div>
          <div className="text-xs font-mono text-purple-400">
            {parsedColors.length} {isRu ? 'цветов' : 'colors parsed'}
          </div>
        </div>

        {/* Swatches preview */}
        {parsedColors.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t border-white/5">
            {parsedColors.map((c, i) => (
              <div key={i} className="flex flex-col items-center gap-1">
                <div className="w-8 h-8 rounded-lg border border-white/10" style={{ backgroundColor: c.hex }} title={c.hex} />
                <span className="text-[9px] font-mono text-gray-500">{c.hex.toUpperCase()}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Exporter Tabs */}
      <section className="glass-panel rounded-2xl border border-white/10 p-6 space-y-4">
        <div className="flex flex-wrap gap-2 border-b border-white/10 pb-3">
          {[
            { id: 'pal', label: 'JASC PAL (.pal)', desc: 'Aseprite, GraphicsGale' },
            { id: 'gpl', label: 'GIMP (.gpl)', desc: 'Aseprite, GIMP, Krita' },
            { id: 'hex', label: 'HEX (.hex)', desc: 'Raw hex list' },
            { id: 'css', label: 'CSS Variables', desc: 'Web design' },
            { id: 'tailwind', label: 'Tailwind Config', desc: 'tailwind.config.js' },
            { id: 'tokens', label: 'Design Tokens', desc: 'W3C Community JSON' },
            { id: 'json', label: 'JSON', desc: 'OKLCH structured data' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                activeTab === tab.id
                  ? 'bg-purple-600 text-white font-bold'
                  : 'bg-white/5 text-gray-400 hover:text-white border border-white/10 hover:border-purple-500/30'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="relative">
          <pre className="p-4 rounded-xl bg-black/40 border border-white/10 text-xs font-mono text-gray-300 max-h-60 overflow-y-auto whitespace-pre">
            {outputText}
          </pre>
        </div>

        <div className="flex flex-wrap gap-3 pt-2">
          <button
            onClick={handleDownload}
            disabled={parsedColors.length === 0}
            className="px-5 py-2 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 shadow-md"
          >
            {isRu ? `Скачать .${outputExt}` : `Download .${outputExt}`}
          </button>
          <button
            onClick={handleCopy}
            disabled={parsedColors.length === 0}
            className="px-4 py-2 text-xs font-mono text-white bg-white/10 hover:bg-white/15 rounded-xl border border-white/15 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            {copied ? (isRu ? 'Скопировано!' : 'Copied!') : (isRu ? 'Копировать' : 'Copy')}
          </button>
          <button
            onClick={openInStudio}
            disabled={parsedColors.length === 0}
            className="px-4 py-2 text-xs font-mono text-purple-300 hover:text-purple-200 rounded-xl border border-purple-500/20 hover:border-purple-500/40 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            {isRu ? 'Открыть в студии' : 'Open in Studio'}
          </button>
        </div>
      </section>

      {/* Compatibility Notice */}
      <section className="text-xs font-mono text-gray-500 space-y-1">
        <p>• <strong>Aseprite Compatibility:</strong> Aseprite imports <code>.pal</code> (JASC-PAL) and <code>.gpl</code> (GIMP Palette) formats natively via Preset Palette Options &gt; Load Palette.</p>
        <p>• Binary <code>.ase</code> sprite format is not generated directly; standard palette files are fully compatible.</p>
      </section>
    </div>
  );
}
