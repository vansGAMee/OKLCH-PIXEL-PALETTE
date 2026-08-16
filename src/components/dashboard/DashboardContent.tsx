'use client';
/**
 * src/components/dashboard/DashboardContent.tsx
 * Dashboard main client component with tabs including Bookmarks.
 */
import React, { useState } from 'react';
import Link from 'next/link';
import { Palette, BarChart2, User, Settings, Terminal, LogOut, Plus, ExternalLink, Bookmark } from 'lucide-react';
import { signOut } from '@/app/actions/auth';
import { LimitBar } from './LimitBar';
import { PaletteCard } from './PaletteCard';
import { InsightsTab } from './InsightsTab';
import { Profile } from '@/lib/supabase/types';

interface BookmarkedPalette {
  id: string;
  slug: string;
  title: string;
  color_count: number;
  harmony: string | null;
  colors: unknown;
  profiles: { username: string; display_name: string | null } | null;
}

interface DashboardContentProps {
  locale: 'en' | 'ru';
  profile: Profile | null;
  palettes: Array<{
    id: string;
    slug: string;
    title: string;
    color_count: number;
    visibility: string;
    featured_position: number | null;
    created_at: string;
    updated_at: string;
    colors: unknown;
    harmony: string | null;
    seed: number | null;
    base_hex: string | null;
  }>;
  savedCount: number;
  publicCount: number;
  bookmarks?: BookmarkedPalette[];
}

type Tab = 'saved' | 'published' | 'bookmarks' | 'insights' | 'profile';

export function DashboardContent({ locale, profile, palettes, savedCount, publicCount, bookmarks = [] }: DashboardContentProps) {
  const [activeTab, setActiveTab] = useState<Tab>('saved');
  const isRu = locale === 'ru';

  const homeHref = isRu ? '/ru' : '/';
  const createHref = isRu ? '/ru/create' : '/create';
  const settingsHref = isRu ? '/ru/settings' : '/settings';

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: 'saved', label: isRu ? 'Сохранённые' : 'Saved', icon: Palette },
    { id: 'published', label: isRu ? 'Публичные' : 'Published', icon: ExternalLink },
    { id: 'bookmarks', label: isRu ? 'Закладки' : 'Bookmarks', icon: Bookmark },
    { id: 'insights', label: isRu ? 'Аналитика' : 'Insights', icon: BarChart2 },
    { id: 'profile', label: isRu ? 'Профиль' : 'Profile', icon: User },
  ];

  const savedPalettes = palettes;
  const publishedPalettes = palettes.filter((p) => p.visibility === 'public');

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

          <div className="flex items-center gap-2 sm:gap-3">
            <Link
              href={createHref}
              className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-mono text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{isRu ? 'Новая палитра' : 'New Palette'}</span>
            </Link>
            <Link href={settingsHref} className="p-2 text-gray-400 hover:text-white transition-colors" title={isRu ? 'Настройки' : 'Settings'}>
              <Settings className="w-4 h-4" />
            </Link>
            <form action={signOut}>
              <button type="submit" className="p-2 text-gray-400 hover:text-white transition-colors" title={isRu ? 'Выйти' : 'Sign out'}>
                <LogOut className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex-1">
        {/* Page title */}
        <div className="flex items-center gap-3 mb-6">
          <Terminal className="w-5 h-5 text-purple-400" />
          <div>
            <h1 className="text-xl font-mono font-extrabold text-white">
              {isRu ? 'Панель управления' : 'Dashboard'}
            </h1>
            {profile && (
              <p className="text-xs font-mono text-gray-400">@{profile.username}</p>
            )}
          </div>
        </div>

        {/* Limits */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <LimitBar label={isRu ? 'Сохранено' : 'Saved'} current={savedCount} max={30} />
          <LimitBar label={isRu ? 'Публичных' : 'Public'} current={publicCount} max={3} />
        </div>

        {/* Tabs */}
        <div className="border-b border-white/10 mb-6">
          <nav className="flex gap-1 overflow-x-auto" aria-label="Dashboard tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 sm:px-4 py-2.5 text-xs font-mono font-bold whitespace-nowrap border-b-2 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-t-lg ${
                  activeTab === tab.id
                    ? 'border-purple-500 text-purple-400'
                    : 'border-transparent text-gray-400 hover:text-white hover:border-white/20'
                }`}
              >
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === 'saved' && (
          <section aria-label={isRu ? 'Сохранённые палитры' : 'Saved palettes'}>
            {savedPalettes.length === 0 ? (
              <EmptyState
                locale={locale}
                title={isRu ? 'Нет сохранённых палитр' : 'No saved palettes'}
                desc={isRu ? 'Откройте редактор и сохраните первую палитру.' : 'Open the studio and save your first palette.'}
                createHref={createHref}
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {savedPalettes.map((p) => (
                  <PaletteCard key={p.id} palette={p} locale={locale} />
                ))}
              </div>
            )}
          </section>
        )}

        {activeTab === 'published' && (
          <section aria-label={isRu ? 'Публичные палитры' : 'Published palettes'}>
            {publishedPalettes.length === 0 ? (
              <EmptyState
                locale={locale}
                title={isRu ? 'Нет публичных палитр' : 'No public palettes'}
                desc={isRu ? 'Откройте палитру и опубликуйте её.' : 'Open a palette and publish it to share.'}
                createHref={createHref}
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {publishedPalettes.map((p) => (
                  <PaletteCard key={p.id} palette={p} locale={locale} showPublicLink />
                ))}
              </div>
            )}
          </section>
        )}

        {activeTab === 'bookmarks' && (
          <section aria-label={isRu ? 'Закладки' : 'Bookmarks'}>
            {bookmarks.length === 0 ? (
              <div className="text-center py-16 space-y-4">
                <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mx-auto">
                  <Bookmark className="w-8 h-8 text-amber-400" />
                </div>
                <p className="text-sm font-mono font-bold text-white">
                  {isRu ? 'Нет закладок' : 'No bookmarks'}
                </p>
                <p className="text-xs text-gray-400">
                  {isRu
                    ? 'Открывайте публичные палитры и сохраняйте их в закладки.'
                    : 'Browse public palettes and bookmark ones you like.'}
                </p>
                <Link
                  href={isRu ? '/ru/explore' : '/explore'}
                  className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all"
                >
                  {isRu ? 'Галерея' : 'Explore'}
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {bookmarks.map((p) => (
                  <Link
                    key={p.id}
                    href={`${locale === 'ru' ? '/ru' : ''}/p/${p.slug}`}
                    className="glass-panel rounded-xl border border-white/10 overflow-hidden group transition-all hover:border-amber-500/40 hover:shadow-lg hover:shadow-amber-900/20"
                  >
                    <div className="flex h-14">
                      {(Array.isArray(p.colors) ? p.colors as Array<{ hex: string }> : []).slice(0, 9).map((c, i) => (
                        <div key={i} className="flex-1 group-hover:brightness-110 transition-all" style={{ backgroundColor: c.hex }} />
                      ))}
                    </div>
                    <div className="p-3 space-y-1">
                      <h3 className="text-sm font-mono font-bold text-white truncate group-hover:text-amber-300 transition-colors">
                        {p.title}
                      </h3>
                      <div className="flex items-center justify-between text-[11px] font-mono text-gray-400">
                        <span>@{p.profiles?.username ?? '?'}</span>
                        <span>{p.color_count} {isRu ? 'цветов' : 'colors'}</span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>
        )}

        {activeTab === 'insights' && (
          <InsightsTab locale={locale} />
        )}

        {activeTab === 'profile' && (
          <section aria-label={isRu ? 'Профиль' : 'Profile'}>
            <div className="glass-panel rounded-xl border border-white/10 p-6 max-w-lg space-y-4">
              <h2 className="text-sm font-mono font-bold text-white">{isRu ? 'Ваш профиль' : 'Your Profile'}</h2>
              {profile ? (
                <dl className="space-y-3 text-xs font-mono">
                  <div className="flex justify-between">
                    <dt className="text-gray-400">{isRu ? 'Имя пользователя' : 'Username'}</dt>
                    <dd className="text-white">@{profile.username}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-400">{isRu ? 'Отображаемое имя' : 'Display name'}</dt>
                    <dd className="text-white">{profile.display_name ?? '—'}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Bio</dt>
                    <dd className="text-white max-w-xs text-right">{profile.bio ?? '—'}</dd>
                  </div>
                  {profile.username && (
                    <Link
                      href={isRu ? `/ru/u/${profile.username}` : `/u/${profile.username}`}
                      className="flex items-center gap-1 text-purple-400 hover:text-purple-300 transition-colors"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      {isRu ? 'Публичный профиль' : 'View public profile'}
                    </Link>
                  )}
                </dl>
              ) : null}
              <Link
                href={settingsHref}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-mono text-white bg-zinc-800 hover:bg-zinc-700 border border-white/10 rounded-lg transition-all"
              >
                <Settings className="w-3.5 h-3.5" />
                {isRu ? 'Настройки' : 'Settings'}
              </Link>
            </div>
          </section>
        )}
      </div>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center flex flex-col sm:flex-row items-center justify-center gap-3 mt-12">
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

function EmptyState({ locale, title, desc, createHref }: { locale: 'en' | 'ru'; title: string; desc: string; createHref: string }) {
  return (
    <div className="text-center py-16 space-y-4">
      <div className="w-16 h-16 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mx-auto">
        <Palette className="w-8 h-8 text-purple-400" />
      </div>
      <p className="text-sm font-mono font-bold text-white">{title}</p>
      <p className="text-xs text-gray-400">{desc}</p>
      <Link
        href={createHref}
        className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all"
      >
        <Plus className="w-4 h-4" />
        {locale === 'ru' ? 'Создать палитру' : 'Create palette'}
      </Link>
    </div>
  );
}
