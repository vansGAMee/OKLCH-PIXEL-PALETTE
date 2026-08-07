'use client';
/**
 * src/components/palette/PaletteActions.tsx
 * Like, Bookmark, Remix interactive buttons for the public palette page.
 */
import React, { useState, useTransition } from 'react';
import { Heart, Bookmark, Shuffle, Loader2 } from 'lucide-react';
import { toggleLike, toggleBookmark } from '@/app/actions/likes';
import { remixPalette } from '@/app/actions/remix';

interface PaletteActionsProps {
  paletteId: string;
  paletteSlug: string;
  initialLiked: boolean;
  initialBookmarked: boolean;
  initialLikeCount: number;
  isAuthenticated: boolean;
  isOwner: boolean;
  locale: 'en' | 'ru';
  /** source_palette_id - exists if this is already a remix */
  sourcePaletteId?: string | null;
  sourceTitle?: string | null;
  sourceSlug?: string | null;
}

export function PaletteActions({
  paletteId,
  paletteSlug,
  initialLiked,
  initialBookmarked,
  initialLikeCount,
  isAuthenticated,
  isOwner,
  locale,
  sourcePaletteId,
  sourceTitle,
  sourceSlug,
}: PaletteActionsProps) {
  const isRu = locale === 'ru';
  const [liked, setLiked] = useState(initialLiked);
  const [bookmarked, setBookmarked] = useState(initialBookmarked);
  const [likeCount, setLikeCount] = useState(initialLikeCount);
  const [likeError, setLikeError] = useState<string | null>(null);
  const [bookmarkError, setBookmarkError] = useState<string | null>(null);
  const [remixError, setRemixError] = useState<string | null>(null);
  const [likePending, startLikeTransition] = useTransition();
  const [bookmarkPending, startBookmarkTransition] = useTransition();
  const [remixPending, startRemixTransition] = useTransition();

  const loginHref = `${locale === 'ru' ? '/ru' : ''}/login?redirect=${locale === 'ru' ? '/ru' : ''}/p/${paletteSlug}`;

  const handleLike = () => {
    if (!isAuthenticated) {
      window.location.href = loginHref;
      return;
    }
    setLikeError(null);
    // Optimistic
    setLiked((prev) => !prev);
    setLikeCount((prev) => (liked ? prev - 1 : prev + 1));

    startLikeTransition(async () => {
      const result = await toggleLike(paletteId);
      if ('error' in result) {
        // Revert optimistic
        setLiked((prev) => !prev);
        setLikeCount((prev) => (liked ? prev + 1 : prev - 1));
        setLikeError(result.error);
      }
    });
  };

  const handleBookmark = () => {
    if (!isAuthenticated) {
      window.location.href = loginHref;
      return;
    }
    setBookmarkError(null);
    setBookmarked((prev) => !prev);

    startBookmarkTransition(async () => {
      const result = await toggleBookmark(paletteId);
      if ('error' in result) {
        setBookmarked((prev) => !prev);
        setBookmarkError(result.error);
      }
    });
  };

  const handleRemix = () => {
    if (!isAuthenticated) {
      window.location.href = loginHref;
      return;
    }
    setRemixError(null);
    startRemixTransition(async () => {
      const result = await remixPalette(paletteId);
      if (result && 'error' in result) {
        setRemixError(result.error);
      }
    });
  };

  return (
    <div className="space-y-3">
      {/* Source palette reference */}
      {sourcePaletteId && sourceSlug && (
        <p className="text-xs font-mono text-gray-400">
          {isRu ? 'Ремикс' : 'Remix of'}{' '}
          <a
            href={`${locale === 'ru' ? '/ru' : ''}/p/${sourceSlug}`}
            className="text-purple-400 hover:text-purple-300 transition-colors underline"
          >
            {sourceTitle ?? sourceSlug}
          </a>
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        {/* Remix / Duplicate */}
        <button
          onClick={handleRemix}
          disabled={remixPending}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-60 rounded-lg transition-all"
        >
          {remixPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Shuffle className="w-4 h-4" />
          )}
          {isOwner
            ? (isRu ? 'Дублировать' : 'Duplicate')
            : (isRu ? 'Ремикс' : 'Remix')}
        </button>

        {/* Like */}
        <button
          onClick={handleLike}
          disabled={likePending}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm font-mono rounded-lg border transition-all disabled:opacity-60 ${
            liked
              ? 'bg-rose-600/20 border-rose-500/40 text-rose-300 hover:bg-rose-600/30'
              : 'bg-zinc-900 hover:bg-zinc-800 border-white/10 text-gray-300 hover:text-white'
          }`}
          title={isAuthenticated ? '' : (isRu ? 'Войдите, чтобы поставить лайк' : 'Sign in to like')}
        >
          <Heart className={`w-4 h-4 ${liked ? 'fill-rose-400 text-rose-400' : 'text-rose-400'}`} />
          {likeCount > 0 ? likeCount : (isRu ? 'Нравится' : 'Like')}
        </button>

        {/* Bookmark */}
        <button
          onClick={handleBookmark}
          disabled={bookmarkPending}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm font-mono rounded-lg border transition-all disabled:opacity-60 ${
            bookmarked
              ? 'bg-amber-600/20 border-amber-500/40 text-amber-300 hover:bg-amber-600/30'
              : 'bg-zinc-900 hover:bg-zinc-800 border-white/10 text-gray-300 hover:text-white'
          }`}
          title={isAuthenticated ? '' : (isRu ? 'Войдите, чтобы сохранить' : 'Sign in to bookmark')}
        >
          <Bookmark className={`w-4 h-4 ${bookmarked ? 'fill-amber-400 text-amber-400' : 'text-amber-400'}`} />
          {isRu ? (bookmarked ? 'Сохранено' : 'Сохранить') : (bookmarked ? 'Saved' : 'Save')}
        </button>
      </div>

      {/* Error messages */}
      {likeError && <p className="text-xs text-red-400 font-mono">{likeError}</p>}
      {bookmarkError && <p className="text-xs text-red-400 font-mono">{bookmarkError}</p>}
      {remixError && <p className="text-xs text-red-400 font-mono">{remixError}</p>}
    </div>
  );
}
