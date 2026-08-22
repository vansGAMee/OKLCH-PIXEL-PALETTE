'use client';

import React, { useState, useCallback, useRef } from 'react';
import { Sparkles, Loader2, AlertCircle } from 'lucide-react';
import type { HarmonyMode } from '@/types/palette';

export interface AiApplyResult {
  baseHex: string;
  harmony: HarmonyMode;
  seed: number;
  count: number;
}

interface AiPaletteInputProps {
  onApply: (result: AiApplyResult) => void;
  locale?: 'en' | 'ru';
  className?: string;
}

type State = 'idle' | 'loading' | 'error';

const PLACEHOLDER_EN = 'winter starry forest';
const PLACEHOLDER_RU = 'зимний звездный лес';

const COUNT_OPTIONS = [4, 5, 6, 7, 8, 9] as const;

export function AiPaletteInput({ onApply, locale = 'en', className = '' }: AiPaletteInputProps) {
  const isRu = locale === 'ru';

  const [prompt, setPrompt] = useState('');
  const [count, setCount] = useState<number>(4);
  const [state, setState] = useState<State>('idle');
  const [error, setError] = useState<string | null>(null);
  const isGenerating = state === 'loading';
  const inputRef = useRef<HTMLInputElement>(null);

  const handleGenerate = useCallback(async () => {
    const trimmed = (inputRef.current?.value || prompt).trim();
    if (!trimmed || isGenerating) return;

    setState('loading');
    setError(null);

    try {
      // Lazy load inference module — only on first use
      const { inferPaletteIntent } = await import('@/lib/ai-palette/inference');
      const intent = await inferPaletteIntent(trimmed);

      onApply({
        baseHex: intent.baseHex,
        harmony: intent.harmony,
        seed: intent.seed,
        count,
      });

      setState('idle');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setState('error');
    }
  }, [prompt, count, isGenerating, onApply]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleGenerate();
      }
    },
    [handleGenerate],
  );

  const handleRetry = useCallback(() => {
    setState('idle');
    setError(null);
    inputRef.current?.focus();
  }, []);

  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as unknown as { __generateAiPalette?: (text: string) => Promise<void> }).__generateAiPalette = async (text: string) => {
        setPrompt(text);
        if (inputRef.current) inputRef.current.value = text;
        const { inferPaletteIntent } = await import('@/lib/ai-palette/inference');
        const intent = await inferPaletteIntent(text);
        onApply({
          baseHex: intent.baseHex,
          harmony: intent.harmony,
          seed: intent.seed,
          count,
        });
      };
    }
  }, [count, onApply]);

  return (
    <section
      className={`rounded-xl border border-purple-500/20 bg-purple-950/20 p-4 space-y-3 ${className}`}
      aria-label={isRu ? 'AI генерация палитры' : 'AI palette generation'}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-purple-400 flex-shrink-0" />
        <span className="text-xs font-mono font-bold tracking-widest text-purple-300 uppercase">
          {isRu ? 'Создать с помощью AI' : 'Try with AI'}
        </span>
      </div>

      {/* Prompt input */}
      <div className="space-y-1.5">
        <label
          htmlFor="ai-palette-prompt"
          className="text-[11px] font-mono text-gray-400"
        >
          {isRu ? 'Опишите палитру' : 'Describe a palette'}
        </label>
        <input
          id="ai-palette-prompt"
          ref={inputRef}
          type="text"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isRu ? PLACEHOLDER_RU : PLACEHOLDER_EN}
          maxLength={160}
          disabled={isGenerating}
          aria-busy={isGenerating}
          aria-label={isRu ? 'Текстовое описание палитры' : 'Palette description'}
          className="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm font-mono text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      {/* Color count selector */}
      <div className="space-y-1.5">
        <span className="text-[11px] font-mono text-gray-400">
          {isRu ? 'Количество цветов' : 'Colors'}
        </span>
        <div className="flex gap-1.5 flex-wrap" role="group" aria-label={isRu ? 'Количество цветов' : 'Color count'}>
          {COUNT_OPTIONS.map(n => (
            <button
              key={n}
              type="button"
              onClick={() => setCount(n)}
              aria-pressed={count === n}
              className={`w-8 h-8 rounded-lg text-xs font-mono font-bold transition-all ${
                count === n
                  ? 'bg-purple-600 text-white border border-purple-400'
                  : 'bg-zinc-900 text-gray-400 border border-white/10 hover:border-purple-500/50 hover:text-white'
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* Error display */}
      {state === 'error' && error && (
        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-950/40 border border-red-500/30">
          <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-mono text-red-300 break-words">{error}</p>
            <button
              type="button"
              onClick={handleRetry}
              className="mt-1 text-[11px] font-mono text-red-400 hover:text-white underline"
            >
              {isRu ? 'Попробовать снова' : 'Retry'}
            </button>
          </div>
        </div>
      )}

      {/* Generate button */}
      <button
        type="button"
        onClick={handleGenerate}
        disabled={!prompt.trim() || isGenerating}
        aria-disabled={!prompt.trim() || isGenerating}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-mono font-bold transition-all bg-purple-600 hover:bg-purple-500 text-white disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {isGenerating ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            {isRu ? 'Генерация...' : 'Generating...'}
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            {isRu ? 'Создать с AI' : 'Generate with AI'}
          </>
        )}
      </button>

      {/* Disclaimer */}
      <p className="text-[10px] font-mono text-gray-600 text-center">
        {isRu
          ? 'Нейросеть работает локально на вашем устройстве'
          : 'Runs locally on your device'}
      </p>
    </section>
  );
}
