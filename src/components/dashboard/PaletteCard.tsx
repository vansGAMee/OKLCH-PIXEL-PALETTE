'use client';
/**
 * src/components/dashboard/PaletteCard.tsx
 * Dashboard palette card with actions.
 */
import React, { useState, useTransition } from 'react';
import Link from 'next/link';
import { Trash2, EyeOff, Globe, Loader2, ExternalLink } from 'lucide-react';
import { deletePalette, updatePalette } from '@/app/actions/palettes';

interface PaletteCardProps {
  palette: {
    id: string;
    slug: string;
    title: string;
    color_count: number;
    visibility: string;
    featured_position: number | null;
    colors: unknown;
    harmony: string | null;
  };
  locale: 'en' | 'ru';
  showPublicLink?: boolean;
}

export function PaletteCard({ palette, locale, showPublicLink }: PaletteCardProps) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string>();
  const isRu = locale === 'ru';

  const colors = Array.isArray(palette.colors) ? palette.colors as Array<{ hex: string }> : [];

  const handleDelete = () => {
    if (!confirm(isRu ? 'Удалить эту палитру?' : 'Delete this palette?')) return;
    startTransition(async () => {
      const result = await deletePalette(palette.id);
      if ('error' in result) setError(result.error);
    });
  };

  const handleTogglePublic = () => {
    const newVisibility = palette.visibility === 'public' ? 'private' : 'public';
    startTransition(async () => {
      const result = await updatePalette(palette.id, { visibility: newVisibility });
      if ('error' in result) setError(result.error);
    });
  };

  return (
    <div className="glass-panel rounded-xl border border-white/10 overflow-hidden group">
      {/* Color Strip */}
      <div className="flex h-16">
        {colors.slice(0, 9).map((c, i) => (
          <div
            key={i}
            className="flex-1"
            style={{ backgroundColor: c.hex }}
            title={c.hex}
          />
        ))}
      </div>

      {/* Card Body */}
      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-sm font-mono font-bold text-white truncate">{palette.title}</h3>
            <p className="text-[11px] font-mono text-gray-400">
              {palette.color_count} colors · {palette.harmony ?? 'custom'}
            </p>
          </div>
          <div className={`flex-shrink-0 text-[10px] font-mono px-2 py-0.5 rounded border ${
            palette.visibility === 'public'
              ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
              : palette.visibility === 'unlisted'
                ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
                : 'text-gray-400 border-white/10 bg-white/5'
          }`}>
            {palette.visibility}
          </div>
        </div>

        {error && (
          <p className="text-xs text-red-400 font-mono">{error}</p>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2">
          {showPublicLink && palette.visibility === 'public' && (
            <Link
              href={`/p/${palette.slug}`}
              className="flex items-center gap-1 text-xs font-mono text-purple-400 hover:text-purple-300 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {isRu ? 'Смотреть' : 'View'}
            </Link>
          )}

          <div className="ml-auto flex items-center gap-1.5">
            {isPending ? (
              <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
            ) : (
              <>
                <button
                  onClick={handleTogglePublic}
                  className="p-1.5 text-gray-400 hover:text-white transition-colors rounded"
                  title={palette.visibility === 'public'
                    ? (isRu ? 'Сделать приватной' : 'Make private')
                    : (isRu ? 'Опубликовать' : 'Publish')}
                >
                  {palette.visibility === 'public' ? <EyeOff className="w-4 h-4" /> : <Globe className="w-4 h-4" />}
                </button>
                <button
                  onClick={handleDelete}
                  className="p-1.5 text-gray-400 hover:text-red-400 transition-colors rounded"
                  title={isRu ? 'Удалить' : 'Delete'}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
