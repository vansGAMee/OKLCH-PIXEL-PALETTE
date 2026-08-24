'use client';

import { useEffect, useState } from 'react';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import type { Palette } from '@/types/palette';
import { getPaletteFeedbackQueue } from '@/lib/palette-feedback';

interface AiFeedbackControlsProps {
  palette: Palette;
  modelVersion?: string;
  encoderVersion: string;
  seed: number;
  locale?: 'en' | 'ru';
}

export function AiFeedbackControls({
  palette,
  modelVersion,
  encoderVersion,
  seed,
  locale = 'en',
}: AiFeedbackControlsProps) {
  const isRu = locale === 'ru';
  const [enabled, setEnabled] = useState(false);
  const [sentiment, setSentiment] = useState<{
    generationKey: string;
    event: 'like' | 'dislike';
  } | null>(null);
  const generationKey = `${modelVersion ?? 'none'}:${palette.seed}:${palette.colors.map((color) => color.hex).join(',')}`;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setEnabled(getPaletteFeedbackQueue().isEnabled());
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleOptIn = (nextEnabled: boolean) => {
    getPaletteFeedbackQueue().setEnabled(nextEnabled);
    setEnabled(nextEnabled);
    if (!nextEnabled) setSentiment(null);
  };

  const submit = (event: 'like' | 'dislike') => {
    if (!enabled || !modelVersion) return;
    const accepted = getPaletteFeedbackQueue().enqueue({
      event,
      modelVersion,
      encoderVersion,
      palette: palette.colors.map((color) => ({ ...color.oklch })),
      requestedCount: palette.count,
      seed,
    });
    if (accepted) setSentiment({ generationKey, event });
  };

  return (
    <section className="glass-panel rounded-xl border border-white/10 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <label className="flex items-start gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => handleOptIn(event.target.checked)}
          className="mt-0.5 accent-purple-500"
        />
        <span>
          <span className="block text-[11px] font-mono text-gray-300">
            {isRu
              ? 'Помочь улучшить AI анонимными отзывами о палитрах'
              : 'Help improve AI with anonymous palette feedback'}
          </span>
          <span className="block mt-0.5 text-[9px] font-mono text-gray-500">
            {isRu
              ? 'Генерация остаётся локальной. Текст запроса не отправляется.'
              : 'Generation stays local. Your prompt text is not uploaded.'}
          </span>
        </span>
      </label>

      {enabled && modelVersion && (
        <div className="flex items-center gap-2" aria-label={isRu ? 'Оценка палитры' : 'Rate palette'}>
          <span className="text-[10px] font-mono text-gray-500">
            {isRu ? 'Полезно?' : 'Useful?'}
          </span>
          <button
            type="button"
            onClick={() => submit('like')}
            aria-pressed={sentiment?.generationKey === generationKey && sentiment.event === 'like'}
            aria-label={isRu ? 'Нравится' : 'Like palette'}
            className={`p-2 rounded-lg border transition-colors ${
              sentiment?.generationKey === generationKey && sentiment.event === 'like'
                ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300'
                : 'border-white/10 text-gray-400 hover:text-emerald-300 hover:border-emerald-400/50'
            }`}
          >
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => submit('dislike')}
            aria-pressed={sentiment?.generationKey === generationKey && sentiment.event === 'dislike'}
            aria-label={isRu ? 'Не нравится' : 'Dislike palette'}
            className={`p-2 rounded-lg border transition-colors ${
              sentiment?.generationKey === generationKey && sentiment.event === 'dislike'
                ? 'bg-rose-500/20 border-rose-400 text-rose-300'
                : 'border-white/10 text-gray-400 hover:text-rose-300 hover:border-rose-400/50'
            }`}
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </section>
  );
}
