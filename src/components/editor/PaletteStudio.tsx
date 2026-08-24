'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { HarmonyMode, Palette, PaletteColor, PaletteGenerationMode } from '@/types/palette';
import { generatePalette } from '@/lib/color/generator';
import {
  canonicalizeGeneratedPalette,
  clampPaletteColorCount,
  createCanonicalPaletteFromOklch,
  mergeLockedPalette,
} from '@/lib/color/extendPalette';
import { ColorPicker } from '@/components/controls/ColorPicker';
import { HarmonySelector } from '@/components/controls/HarmonySelector';
import {
  AiPaletteInput,
  type AiApplyResult,
  type AiLockedColor,
  type AiPaletteInputHandle,
} from '@/components/controls/AiPaletteInput';
import { AiFeedbackControls } from '@/components/controls/AiFeedbackControls';
import { ActionToolbar } from '@/components/controls/ActionToolbar';
import { PaletteGrid } from '@/components/palette/PaletteGrid';
import { BklitLightnessChart } from '@/components/charts/BklitLightnessChart';
import { PixelPreview } from '@/components/preview/PixelPreview';
import { QualityInspector } from '@/components/quality/QualityInspector';
import { ImportModal } from '@/components/import/ImportModal';
import { inspectPalette } from '@/lib/color/qualityInspector';
import { savePalette } from '@/app/actions/palettes';
import { isSupabaseAvailable } from '@/lib/supabase/client';
import { LanguageSwitcher } from '@/components/i18n/LanguageSwitcher';
import { Locale, messages } from '@/i18n/messages';
import { Sparkles, Palette as PaletteIcon, ShieldCheck, Terminal, Home, Bot, SlidersHorizontal } from 'lucide-react';
import {
  getPaletteFeedbackQueue,
  type PaletteFeedbackEventName,
} from '@/lib/palette-feedback';

const STORAGE_KEY = 'pixel_palette_studio_state_v1';

const DEFAULT_HEX = '#5b21b6';
const DEFAULT_HARMONY: HarmonyMode = 'splitComplementary';
const DEFAULT_SEED = 0;
const DEFAULT_COLOR_COUNT = 4;
const AI_ENCODER_VERSION = 'multilingual-e5-small-q8';

function buildManualPalette(
  baseHex: string,
  harmony: HarmonyMode,
  seed: number,
  count: number,
): Palette {
  return canonicalizeGeneratedPalette(generatePalette(baseHex, harmony, seed), count);
}

interface PaletteStudioProps {
  locale?: Locale;
}

export function PaletteStudio({ locale = 'en' }: PaletteStudioProps) {
  const t = messages[locale].header;
  const c = messages[locale].controls;
  const isRu = locale === 'ru';
  const searchParams = useSearchParams();
  const urlPrompt = searchParams?.get('prompt') || searchParams?.get('q') || '';
  const initialUrlPromptRef = useRef(urlPrompt);

  const [paletteName, setPaletteName] = useState<string>('');
  const [mode, setMode] = useState<PaletteGenerationMode>(() => initialUrlPromptRef.current ? 'ai' : 'manual');
  const [baseHex, setBaseHex] = useState<string>(DEFAULT_HEX);
  const [harmony, setHarmony] = useState<HarmonyMode>(DEFAULT_HARMONY);
  const [seed, setSeed] = useState<number>(DEFAULT_SEED);
  const [colorCount, setColorCount] = useState<number>(DEFAULT_COLOR_COUNT);
  const [palette, setPalette] = useState<Palette>(() =>
    buildManualPalette(DEFAULT_HEX, DEFAULT_HARMONY, DEFAULT_SEED, DEFAULT_COLOR_COUNT)
  );
  const [lockedIndices, setLockedIndices] = useState<Set<number>>(() => new Set());
  const [aiModelVersion, setAiModelVersion] = useState<string | undefined>();
  const lockedIndicesRef = useRef<Set<number>>(new Set());
  const aiInputRef = useRef<AiPaletteInputHandle>(null);

  // Modal and cloud notification state
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [cloudNotice, setCloudNotice] = useState<string | null>(null);

  // Restore saved state from localStorage safely after hydration
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.baseHex && /^#[0-9a-fA-F]{6}$/.test(parsed.baseHex)) setBaseHex(parsed.baseHex);
        if (parsed.harmony) setHarmony(parsed.harmony as HarmonyMode);
        if (typeof parsed.seed === 'number') setSeed(parsed.seed);
        if (typeof parsed.colorCount === 'number' && parsed.colorCount >= 2 && parsed.colorCount <= 9) {
          setColorCount(clampPaletteColorCount(parsed.colorCount));
        }
        if (!initialUrlPromptRef.current && (parsed.mode === 'manual' || parsed.mode === 'ai')) {
          setMode(parsed.mode);
        }
      }
    } catch {
      // Ignore
    }
  }, []);

  // Read URL search parameters on load if present
  useEffect(() => {
    if (!searchParams) return;
    const pBase = searchParams.get('baseHex') || searchParams.get('base');
    const pHarmony = searchParams.get('harmony');
    const pSeed = searchParams.get('seed');
    const pCount = searchParams.get('count');
    const pTitle = searchParams.get('title') || searchParams.get('name');
    const pPrompt = searchParams.get('prompt') || searchParams.get('q');

    if (pBase && /^#[0-9a-fA-F]{6}$/.test(pBase)) setBaseHex(pBase);
    if (pHarmony) setHarmony(pHarmony as HarmonyMode);
    if (pSeed && !isNaN(Number(pSeed))) setSeed(Number(pSeed));
    if (pCount && !isNaN(Number(pCount))) setColorCount(clampPaletteColorCount(Number(pCount)));
    if (pTitle) setPaletteName(pTitle);
    if (pPrompt) setMode('ai');
  }, [searchParams]);

  // Debounced sync to localStorage (400ms delay to eliminate synchronous disk I/O during drag)
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ baseHex, harmony, seed, colorCount, mode })
        );
      } catch {
        // Ignore
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [baseHex, harmony, seed, colorCount, mode]);

  // Manual mode is a strictly procedural path: generator + OKLCH extension only.
  useEffect(() => {
    if (mode !== 'manual') return;
    const candidate = buildManualPalette(baseHex, harmony, seed, colorCount);
    setPalette((current) => mergeLockedPalette(current, candidate, lockedIndicesRef.current));
  }, [baseHex, colorCount, harmony, mode, seed]);

  // Quality Report calculated with useMemo
  const qualityReport = useMemo(() => {
    return inspectPalette(palette);
  }, [palette]);

  const recordAiFeedback = useCallback((event: PaletteFeedbackEventName) => {
    if (mode !== 'ai' || !aiModelVersion) return;
    getPaletteFeedbackQueue().enqueue({
      event,
      modelVersion: aiModelVersion,
      encoderVersion: AI_ENCODER_VERSION,
      palette: palette.colors.map((color) => ({ ...color.oklch })),
      requestedCount: palette.count,
      seed,
    });
  }, [aiModelVersion, mode, palette, seed]);

  const dropOutOfRangeLocks = useCallback((count: number) => {
    setLockedIndices((current) => {
      const next = new Set([...current].filter((index) => index < count));
      lockedIndicesRef.current = next;
      return next;
    });
  }, []);

  const handleColorCountChange = useCallback((nextCount: number) => {
    const safeCount = clampPaletteColorCount(nextCount);
    setColorCount(safeCount);
    dropOutOfRangeLocks(safeCount);
  }, [dropOutOfRangeLocks]);

  const handleToggleLock = useCallback((index: number) => {
    const wasLocked = lockedIndicesRef.current.has(index);
    setLockedIndices((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      lockedIndicesRef.current = next;
      return next;
    });
    recordAiFeedback(wasLocked ? 'unlock' : 'lock');
  }, [recordAiFeedback]);

  const handleNewVariation = useCallback(() => {
    const nextSeed = seed + 1;
    if (mode === 'manual') {
      setSeed(nextSeed);
      return;
    }
    recordAiFeedback('regenerate');
    void aiInputRef.current?.generate({ seed: nextSeed, count: colorCount });
  }, [colorCount, mode, recordAiFeedback, seed]);

  const handleReset = useCallback(() => {
    setBaseHex(DEFAULT_HEX);
    setHarmony(DEFAULT_HARMONY);
    setSeed(DEFAULT_SEED);
    setColorCount(DEFAULT_COLOR_COUNT);
    setPaletteName('');
    setAiModelVersion(undefined);
    setMode('manual');
    const noLocks = new Set<number>();
    lockedIndicesRef.current = noLocks;
    setLockedIndices(noLocks);
    setPalette(buildManualPalette(DEFAULT_HEX, DEFAULT_HARMONY, DEFAULT_SEED, DEFAULT_COLOR_COUNT));
  }, []);

  const handleAiApply = useCallback((result: AiApplyResult) => {
    const candidate = createCanonicalPaletteFromOklch(result.colors, harmony, result.seed);
    setPalette((current) => mergeLockedPalette(current, candidate, lockedIndicesRef.current));
    setSeed(result.seed);
    setAiModelVersion(result.modelVersion);
    setColorCount(candidate.count);
    dropOutOfRangeLocks(candidate.count);
  }, [dropOutOfRangeLocks, harmony]);

  const handleImportColors = useCallback((colors: PaletteColor[]) => {
    if (!colors || colors.length === 0) return;
    const baseCol = colors.find((col) => col.role === 'base') || colors[0];
    const nextCount = clampPaletteColorCount(colors.length);
    const noLocks = new Set<number>();
    lockedIndicesRef.current = noLocks;
    setLockedIndices(noLocks);
    setMode('manual');
    setAiModelVersion(undefined);
    setBaseHex(baseCol.hex);
    setColorCount(nextCount);
  }, []);

  const aiLockedColors = useMemo<AiLockedColor[]>(() =>
    [...lockedIndices]
      .filter((index) => index >= 0 && index < colorCount && Boolean(palette.colors[index]))
      .sort((a, b) => a - b)
      .map((index) => ({ index, oklch: { ...palette.colors[index].oklch } })),
  [colorCount, lockedIndices, palette.colors]);

  const handleCloudSave = useCallback(async () => {
    if (!isSupabaseAvailable()) {
      setCloudNotice(
        isRu
          ? 'Облачное сохранение требует подключения Supabase. Настройте переменные в SUPABASE_SETUP.md.'
          : 'Cloud save requires Supabase setup. Check SUPABASE_SETUP.md for instructions.'
      );
      setTimeout(() => setCloudNotice(null), 5000);
      return;
    }

    const title = paletteName.trim() || (isRu ? `Палитра ${palette.base.hex}` : `Palette ${palette.base.hex}`);
    const result = await savePalette({
      title,
      visibility: 'private',
      palette,
    });

    if ('error' in result) {
      setCloudNotice(result.error);
    } else {
      setCloudNotice(
        isRu
          ? 'Палитра успешно сохранена в облаке!'
          : 'Palette saved to cloud successfully!'
      );
    }
    setTimeout(() => setCloudNotice(null), 4000);
  }, [isRu, palette, paletteName]);

  const homeHref = locale === 'ru' ? '/ru' : '/';

  return (
    <div
      lang={locale}
      className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col justify-between selection:bg-purple-600 selection:text-white overflow-x-hidden"
    >
      {/* Top Header Navigation */}
      <header className="sticky top-0 z-40 border-b border-white/10 glass-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-2">
          {/* Logo & Brand Title */}
          <Link href={homeHref} className="flex items-center gap-2 sm:gap-3 group focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg p-1 transition-all min-w-0">
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 shadow-lg shadow-purple-900/20 group-hover:scale-105 transition-transform shrink-0">
              <PaletteIcon className="w-4 h-4 sm:w-5 sm:h-5" />
            </div>
            <div className="min-w-0">
              <h1 className="text-xs sm:text-base font-mono font-black tracking-tight text-white flex items-center gap-1.5 truncate">
                OKLCH PIXEL PALETTE <span className="text-purple-400 font-normal text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20">{t.studioBadge}</span>
              </h1>
              <p className="text-[11px] text-gray-400 font-mono hidden sm:block">
                {t.subtitle}
              </p>
            </div>
          </Link>

          {/* Right Header Navigation & Status Stamp */}
          <div className="flex items-center gap-1.5 sm:gap-4 shrink-0">
            <LanguageSwitcher currentLocale={locale} />

            <Link
              href={homeHref}
              className="flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <Home className="w-3.5 h-3.5" />
              <span className="hidden xs:inline">{t.homepage}</span>
            </Link>

            <div className="hidden md:flex items-center gap-2 text-xs font-mono text-gray-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>{t.gamutGuarded}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Studio Workstation */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Cloud Notice Alert */}
        {cloudNotice && (
          <div className="p-4 rounded-xl bg-purple-950/80 border border-purple-500/40 text-purple-200 text-xs font-mono flex items-center justify-between shadow-xl">
            <span>{cloudNotice}</span>
            <button onClick={() => setCloudNotice(null)} className="text-gray-400 hover:text-white">✕</button>
          </div>
        )}

        {/* Explicit generation mode */}
        <section aria-label={isRu ? 'Режим генерации' : 'Generation mode'} className="glass-panel p-2 rounded-xl border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-1 p-1 bg-zinc-950 rounded-lg border border-white/5" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'manual'}
              onClick={() => {
                setMode('manual');
                setAiModelVersion(undefined);
              }}
              className={`flex items-center justify-center gap-2 px-4 py-2 rounded-md text-xs font-mono font-bold transition-all ${
                mode === 'manual' ? 'bg-purple-600 text-white shadow-md' : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              {isRu ? 'Вручную' : 'Manual'}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'ai'}
              onClick={() => setMode('ai')}
              className={`flex items-center justify-center gap-2 px-4 py-2 rounded-md text-xs font-mono font-bold transition-all ${
                mode === 'ai' ? 'bg-purple-600 text-white shadow-md' : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <Bot className="w-3.5 h-3.5" />
              AI
            </button>
          </div>
          <p className="px-2 text-[10px] font-mono text-gray-500">
            {mode === 'manual'
              ? (isRu ? 'Локальная OKLCH-генерация без AI' : 'Deterministic local OKLCH generation • no AI')
              : (isRu ? 'Локальная нейросеть в браузере' : 'Local in-browser model generation')}
          </p>
        </section>

        {mode === 'manual' ? (
          <section aria-label="Palette Controls" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ColorPicker value={baseHex} onChange={setBaseHex} locale={locale} />
            <HarmonySelector harmony={harmony} onChange={setHarmony} locale={locale} />
          </section>
        ) : (
          <section aria-label={isRu ? 'AI генерация' : 'AI generation'}>
            <AiPaletteInput
              ref={aiInputRef}
              onApply={handleAiApply}
              count={colorCount}
              onCountChange={handleColorCountChange}
              seed={seed}
              lockedColors={aiLockedColors}
              locale={locale}
              initialPrompt={urlPrompt}
            />
            <div className="mt-3">
              <AiFeedbackControls
                palette={palette}
                modelVersion={aiModelVersion}
                encoderVersion={AI_ENCODER_VERSION}
                seed={seed}
                locale={locale}
              />
            </div>
          </section>
        )}

        {/* Palette Name Section */}
        <section aria-label="Palette Name" className="glass-panel p-4 rounded-xl border border-white/10">
          <label htmlFor="studio-palette-title" className="block text-xs font-mono font-bold text-gray-300 mb-1.5">
            {isRu ? 'Название палитры' : 'Palette Name'}
          </label>
          <input
            id="studio-palette-title"
            type="text"
            value={paletteName}
            onChange={(e) => setPaletteName(e.target.value)}
            maxLength={80}
            placeholder={isRu ? `Палитра ${baseHex}` : `Palette ${baseHex}`}
            className="w-full px-3.5 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm font-mono text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </section>

        {/* Global Action Toolbar */}
        <section aria-label="Action Toolbar">
          <ActionToolbar
            palette={palette}
            colorCount={palette.count}
            onColorCountChange={mode === 'manual' ? handleColorCountChange : undefined}
            onNewVariation={handleNewVariation}
            onReset={handleReset}
            onOpenImport={() => setIsImportOpen(true)}
            onCloudSave={handleCloudSave}
            onExport={() => recordAiFeedback('export')}
            locale={locale}
          />
        </section>

        {/* Color Cards Display Grid */}
        <section aria-label="Generated Color Palette Cards">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-mono font-bold tracking-widest text-gray-300 uppercase flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              {c.generatedPaletteTitle} ({palette.count})
            </h2>
            <span className="text-[11px] font-mono text-gray-400">{c.clickToCopy}</span>
          </div>

          <PaletteGrid
            palette={palette}
            lockedIndices={lockedIndices}
            onToggleLock={handleToggleLock}
            locale={locale}
          />
        </section>

        {/* Quality Inspector Panel */}
        <section aria-label="Quality Inspection">
          <QualityInspector report={qualityReport} locale={locale} />
        </section>

        {/* Visualizations and Pixel Preview Dual Column Section */}
        <section aria-label="Visualizations and Pixel Preview" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BklitLightnessChart palette={palette} locale={locale} />
          <PixelPreview palette={palette} locale={locale} />
        </section>
      </main>

      {/* Import Modal */}
      <ImportModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onImport={handleImportColors}
        locale={locale}
      />

      {/* Minimal Footer */}
      <footer className="border-t border-white/10 bg-zinc-950 py-6 text-xs font-mono text-gray-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Terminal className="w-4 h-4 text-purple-400" />
            <span>OKLCH Pixel Palette Studio &copy; {new Date().getFullYear()}</span>
            <span className="text-gray-700">|</span>
            <Link
              href={isRu ? '/ru/privacy' : '/privacy'}
              className="text-gray-400 hover:text-white transition-colors underline-offset-4 hover:underline"
            >
              {isRu ? 'Политика конфиденциальности' : 'Privacy Policy'}
            </Link>
          </div>

          <div className="flex items-center gap-4 text-gray-400">
            <span className="flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Delta E OK Validated
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
