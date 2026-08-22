'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { CuratedPalette, toFullPalette, CURATED_PALETTES } from '@/lib/tools/curatedPalettes';
import { PixelPreview } from '@/components/preview/PixelPreview';
import {
  generateGplString,
  generateJascPalString,
  generateCssString,
  generateJsonString,
  downloadTextFile,
  sanitizeFilename,
} from '@/lib/color/exporters';
import { ArrowRight, Download, Copy, Check } from 'lucide-react';

interface CuratedPaletteDetailProps {
  palette: CuratedPalette;
  locale?: 'en' | 'ru';
}

export function CuratedPaletteDetail({ palette, locale = 'en' }: CuratedPaletteDetailProps) {
  const isRu = locale === 'ru';
  const fullPalette = toFullPalette(palette);
  const [copied, setCopied] = useState(false);

  const title = isRu ? palette.titleRu : palette.title;
  const description = isRu ? palette.descriptionRu : palette.description;
  const studioHref = isRu
    ? `/ru/create?base=${encodeURIComponent(palette.baseHex)}&import=${encodeURIComponent(palette.hexes.join(','))}`
    : `/create?base=${encodeURIComponent(palette.baseHex)}&import=${encodeURIComponent(palette.hexes.join(','))}`;

  const related = CURATED_PALETTES.filter(p => p.slug !== palette.slug).slice(0, 4);

  const handleCopyHex = () => {
    navigator.clipboard.writeText(palette.hexes.map(h => h.toUpperCase()).join(' ')).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const downloadGpl = () => {
    downloadTextFile(`${sanitizeFilename(palette.slug)}.gpl`, generateGplString(fullPalette), 'text/plain');
  };

  const downloadPal = () => {
    downloadTextFile(`${sanitizeFilename(palette.slug)}.pal`, generateJascPalString(fullPalette), 'text/plain');
  };

  const downloadCss = () => {
    downloadTextFile(`${sanitizeFilename(palette.slug)}.css`, generateCssString(fullPalette), 'text/css');
  };

  const downloadJson = () => {
    downloadTextFile(`${sanitizeFilename(palette.slug)}.json`, generateJsonString(fullPalette, locale), 'application/json');
  };

  return (
    <div className="space-y-12">
      {/* Header Info */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {palette.tags.map(tag => (
            <span key={tag} className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">
              #{tag}
            </span>
          ))}
          <span className="text-xs font-mono text-gray-500">
            {palette.hexes.length} {isRu ? 'цветов' : 'colors'} · {palette.harmony}
          </span>
        </div>

        <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
          {title}
        </h1>
        <p className="text-base text-gray-300 font-sans max-w-2xl leading-relaxed">
          {description}
        </p>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <Link
            href={studioHref}
            className="px-6 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/30 flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-purple-400"
          >
            {isRu ? 'Открыть в Студии' : 'Open in Studio'} <ArrowRight className="w-4 h-4" />
          </Link>
          <button
            onClick={handleCopyHex}
            className="px-4 py-2.5 text-sm font-mono text-white bg-white/10 hover:bg-white/15 rounded-xl border border-white/15 transition-all flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-gray-400" />}
            {copied ? (isRu ? 'Скопировано!' : 'Copied!') : (isRu ? 'Копировать HEX' : 'Copy HEX')}
          </button>
        </div>
      </section>

      {/* Large Palette Display */}
      <section className="space-y-4">
        <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">
          {isRu ? 'Цвета палитры' : 'Palette Swatches'}
        </h2>
        <div className="flex rounded-2xl overflow-hidden border border-white/10 shadow-2xl h-24 sm:h-32">
          {palette.hexes.map((hex, i) => (
            <div key={i} className="flex-1 transition-all" style={{ backgroundColor: hex }} title={hex.toUpperCase()} />
          ))}
        </div>

        {/* Color breakdown */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {fullPalette.colors.map((c, i) => (
            <div key={i} className="glass-panel rounded-xl p-3 border border-white/10 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg border border-white/15 shrink-0" style={{ backgroundColor: c.hex }} />
              <div className="min-w-0 flex-1">
                <div className="text-xs font-mono font-bold text-white">{c.hex.toUpperCase()}</div>
                <div className="text-[10px] font-mono text-gray-400">
                  L:{(c.oklch.l * 100).toFixed(0)}% C:{c.oklch.c.toFixed(2)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Pixel Preview & Exports */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-7 space-y-4">
          <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">
            {isRu ? 'Пиксель-арт предпросмотр' : 'Pixel Art Preview'}
          </h2>
          <div className="glass-panel rounded-2xl border border-white/10 p-4">
            <PixelPreview palette={fullPalette} locale={locale} />
          </div>
        </div>

        <div className="lg:col-span-5 space-y-4">
          <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">
            {isRu ? 'Экспорт файлов' : 'Export Formats'}
          </h2>
          <div className="glass-panel rounded-2xl border border-white/10 p-5 space-y-3">
            <p className="text-xs text-gray-400 font-sans">
              {isRu
                ? 'Скачайте готовую палитру в формате для вашего графического редактора или проекта.'
                : 'Download this palette in your favorite pixel art editor or development format.'}
            </p>
            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                onClick={downloadPal}
                className="px-3 py-2 text-xs font-mono rounded-lg bg-white/5 border border-white/10 hover:border-purple-500/40 text-gray-200 hover:text-white transition-all text-left flex items-center justify-between"
              >
                <span>Aseprite (.pal)</span>
                <Download className="w-3.5 h-3.5 text-gray-500" />
              </button>
              <button
                onClick={downloadGpl}
                className="px-3 py-2 text-xs font-mono rounded-lg bg-white/5 border border-white/10 hover:border-purple-500/40 text-gray-200 hover:text-white transition-all text-left flex items-center justify-between"
              >
                <span>GIMP (.gpl)</span>
                <Download className="w-3.5 h-3.5 text-gray-500" />
              </button>
              <button
                onClick={downloadCss}
                className="px-3 py-2 text-xs font-mono rounded-lg bg-white/5 border border-white/10 hover:border-purple-500/40 text-gray-200 hover:text-white transition-all text-left flex items-center justify-between"
              >
                <span>CSS Variables</span>
                <Download className="w-3.5 h-3.5 text-gray-500" />
              </button>
              <button
                onClick={downloadJson}
                className="px-3 py-2 text-xs font-mono rounded-lg bg-white/5 border border-white/10 hover:border-purple-500/40 text-gray-200 hover:text-white transition-all text-left flex items-center justify-between"
              >
                <span>JSON Tokens</span>
                <Download className="w-3.5 h-3.5 text-gray-500" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Related Curated Palettes */}
      <section className="space-y-4 pt-6 border-t border-white/10">
        <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">
          {isRu ? 'Другие палитры' : 'Explore More Palettes'}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {related.map(p => {
            const relHref = isRu ? `/ru/palettes/${p.slug}` : `/palettes/${p.slug}`;
            return (
              <Link
                key={p.slug}
                href={relHref}
                className="glass-panel rounded-xl border border-white/10 hover:border-purple-500/40 p-4 group transition-all space-y-2 block"
              >
                <div className="text-xs font-mono font-bold text-white group-hover:text-purple-300 transition-colors truncate">
                  {isRu ? p.titleRu : p.title}
                </div>
                <div className="flex rounded overflow-hidden border border-white/10 h-5">
                  {p.hexes.map((hex, i) => (
                    <div key={i} className="flex-1" style={{ backgroundColor: hex }} />
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
