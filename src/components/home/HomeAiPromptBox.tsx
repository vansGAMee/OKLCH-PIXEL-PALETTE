'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles, ArrowRight } from 'lucide-react';
import type { Locale } from '@/i18n/messages';

interface HomeAiPromptBoxProps {
  locale: Locale;
  prompts: readonly string[] | string[];
}

export function HomeAiPromptBox({ locale, prompts }: HomeAiPromptBoxProps) {
  const router = useRouter();
  const isRu = locale === 'ru';
  const createHref = isRu ? '/ru/create' : '/create';

  const [prompt, setPrompt] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed) {
      router.push(createHref);
      return;
    }
    router.push(`${createHref}?prompt=${encodeURIComponent(trimmed)}`);
  };

  const handleChipClick = (suggestion: string) => {
    setPrompt(suggestion);
    router.push(`${createHref}?prompt=${encodeURIComponent(suggestion)}`);
  };

  return (
    <div className="w-full space-y-4">
      {/* Interactive Form */}
      <form
        onSubmit={handleSubmit}
        action={createHref}
        method="GET"
        className="relative group"
      >
        <div className="relative flex flex-col sm:flex-row items-stretch sm:items-center gap-2 p-2 sm:p-2.5 rounded-2xl bg-zinc-900/90 border border-purple-500/30 hover:border-purple-400/60 focus-within:border-purple-400 focus-within:ring-2 focus-within:ring-purple-500/30 shadow-xl shadow-purple-950/20 backdrop-blur-sm transition-all">
          <div className="flex items-center flex-1 min-w-0 px-2">
            <Sparkles className="w-4 h-4 text-purple-400 flex-shrink-0 mr-2.5" />
            <input
              type="text"
              name="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={isRu ? 'Например: зимний звездный лес, фиолетовая пещера...' : 'e.g. winter starry forest, purple cave...'}
              maxLength={4096}
              aria-label={isRu ? 'Описание палитры для ИИ' : 'AI Palette prompt description'}
              className="w-full bg-transparent border-none text-sm sm:text-base font-mono text-white placeholder:text-gray-500 focus:outline-none focus:ring-0 py-1"
            />
          </div>

          <button
            type="submit"
            className="inline-flex items-center justify-center gap-2 px-5 py-3 sm:py-2.5 text-xs sm:text-sm font-mono font-bold text-white bg-gradient-to-r from-purple-600 via-purple-500 to-indigo-600 hover:from-purple-500 hover:via-purple-400 hover:to-indigo-500 active:scale-[0.98] rounded-xl transition-all shadow-md shadow-purple-900/40 hover:shadow-purple-700/50 shrink-0"
          >
            <span>{isRu ? 'Создать с ИИ' : 'Generate with AI'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>

      {/* Suggestion Chips */}
      {prompts && prompts.length > 0 && (
        <div className="space-y-2">
          <span className="text-[11px] font-mono font-medium text-gray-400 block">
            {isRu ? 'Или выберите готовый пример:' : 'Or try a prompt idea:'}
          </span>
          <div className="flex flex-wrap gap-2">
            {prompts.map((pText, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleChipClick(pText)}
                className="px-3 py-1.5 rounded-lg bg-zinc-900/80 hover:bg-purple-900/30 border border-white/10 hover:border-purple-400/40 text-xs font-mono text-gray-300 hover:text-purple-200 transition-all text-left flex items-center gap-1.5 group/chip"
              >
                <span className="text-purple-400/60 group-hover/chip:text-purple-300">#</span>
                <span>{pText}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
