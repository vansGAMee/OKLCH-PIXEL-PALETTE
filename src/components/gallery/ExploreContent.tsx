'use client';
/**
 * src/components/gallery/ExploreContent.tsx
 * Explore page layout with palette gallery.
 */
import React from 'react';
import Link from 'next/link';
import { Palette, Compass, Terminal, ChevronLeft, ChevronRight } from 'lucide-react';
import { PaletteGalleryCard } from './PaletteGalleryCard';
import { LanguageSwitcher } from '@/components/i18n/LanguageSwitcher';

interface PaletteItem {
  id: string;
  slug: string;
  title: string;
  color_count: number;
  harmony: string | null;
  colors: unknown;
  published_at: string | null;
  owner_id: string;
  profiles: { username: string; display_name: string | null } | null;
}

interface ExploreContentProps {
  locale: 'en' | 'ru';
  palettes: PaletteItem[];
  totalCount: number;
  page: number;
  limit: number;
  sort: string;
  isSupabaseAvailable: boolean;
}

export function ExploreContent({
  locale,
  palettes,
  totalCount,
  page,
  limit,
  isSupabaseAvailable,
}: ExploreContentProps) {
  const isRu = locale === 'ru';
  const totalPages = Math.ceil(totalCount / limit);
  const homeHref = isRu ? '/ru' : '/';
  const createHref = isRu ? '/ru/create' : '/create';
  const exploreBase = isRu ? '/ru/explore' : '/explore';

  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-white/10 glass-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <Link href={homeHref} className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
              <Palette className="w-4 h-4" />
            </div>
            <span className="text-sm font-mono font-black text-white hidden sm:block">OKLCH PIXEL PALETTE</span>
          </Link>
          <nav className="flex items-center gap-3">
            <LanguageSwitcher currentLocale={locale} />
            <Link
              href={createHref}
              className="px-3 py-1.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all"
            >
              {isRu ? 'Редактор' : 'Studio'}
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full">
        {/* Page header */}
        <div className="flex items-center gap-3 mb-8">
          <Compass className="w-6 h-6 text-purple-400" />
          <div>
            <h1 className="text-2xl font-mono font-extrabold text-white">
              {isRu ? 'Галерея палитр' : 'Explore Palettes'}
            </h1>
            <p className="text-xs font-mono text-gray-400">
              {isSupabaseAvailable
                ? `${totalCount} ${isRu ? 'публичных палитр' : 'public palettes'}`
                : (isRu ? 'Облако не подключено — галерея пуста' : 'Cloud not connected — gallery is empty')}
            </p>
          </div>
        </div>

        {/* Gallery Grid */}
        {palettes.length > 0 ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
              {palettes.map((p) => (
                <PaletteGalleryCard key={p.id} palette={p} locale={locale} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3">
                {page > 1 && (
                  <Link
                    href={`${exploreBase}?page=${page - 1}`}
                    className="flex items-center gap-1 px-4 py-2 text-xs font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-lg transition-all"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                    {isRu ? 'Назад' : 'Previous'}
                  </Link>
                )}
                <span className="text-xs font-mono text-gray-400">
                  {page} / {totalPages}
                </span>
                {page < totalPages && (
                  <Link
                    href={`${exploreBase}?page=${page + 1}`}
                    className="flex items-center gap-1 px-4 py-2 text-xs font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-lg transition-all"
                  >
                    {isRu ? 'Вперёд' : 'Next'}
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Link>
                )}
              </div>
            )}
          </>
        ) : (
          <EmptyGallery locale={locale} createHref={createHref} isSupabaseAvailable={isSupabaseAvailable} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center flex flex-col sm:flex-row items-center justify-center gap-3">
        <div className="flex items-center gap-1">
          <Terminal className="w-3.5 h-3.5 text-purple-400 inline" />
          <span>OKLCH Pixel Palette &copy; {new Date().getFullYear()}</span>
        </div>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link
          href={isRu ? '/ru/privacy' : '/privacy'}
          className="text-gray-400 hover:text-white transition-colors underline-offset-4 hover:underline"
        >
          {isRu ? 'Политика конфиденциальности' : 'Privacy Policy'}
        </Link>
      </footer>
    </div>
  );
}

function EmptyGallery({ locale, createHref, isSupabaseAvailable }: { locale: 'en' | 'ru'; createHref: string; isSupabaseAvailable: boolean }) {
  const isRu = locale === 'ru';
  return (
    <div className="text-center py-20 space-y-4">
      <div className="text-5xl">🎨</div>
      <p className="text-sm font-mono font-bold text-white">
        {isSupabaseAvailable
          ? (isRu ? 'Пока нет публичных палитр' : 'No public palettes yet')
          : (isRu ? 'Галерея требует подключения к облаку' : 'Gallery requires cloud connection')}
      </p>
      <p className="text-xs text-gray-400">
        {isRu ? 'Создайте и опубликуйте первую палитру!' : 'Create and publish the first one!'}
      </p>
      <Link
        href={createHref}
        className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all"
      >
        <Palette className="w-4 h-4" />
        {isRu ? 'Открыть редактор' : 'Open Studio'}
      </Link>
    </div>
  );
}
