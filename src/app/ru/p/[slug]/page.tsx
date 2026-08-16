/* eslint-disable @typescript-eslint/no-explicit-any */
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/server';
import { isSupabaseAvailable } from '@/lib/supabase/client';
import { deserializePaletteRow } from '@/lib/palette/deserialize';
import { BklitLightnessChart } from '@/components/charts/BklitLightnessChart';
import { PaletteActions } from '@/components/palette/PaletteActions';
import { CopyHexButton } from '@/components/palette/CopyHexButton';
import { Palette, Terminal, User } from 'lucide-react';

interface PaletteDetailPageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PaletteDetailPageProps): Promise<Metadata> {
  const { slug } = await params;
  const supabase = await createClient();
  if (!supabase) return { title: 'Палитра | OKLCH Pixel Palette' };

  const { data } = await (supabase as any)
    .from('palettes')
    .select('title, base_hex, harmony, color_count, visibility, profiles!owner_id(username)')
    .eq('slug', slug)
    .single();

  if (!data) return { title: 'Палитра | OKLCH Pixel Palette' };

  const isPublic = (data as any).visibility === 'public';
  const profiles = Array.isArray((data as any).profiles) ? (data as any).profiles[0] : (data as any).profiles as { username: string } | null;
  const title = (data as any).title ?? 'Палитра';
  const username = profiles?.username ?? 'unknown';
  const colorCount = (data as any).color_count ?? 0;
  const harmony = (data as any).harmony ?? '';

  return {
    title: `${title} – Пиксель-арт Палитра | OKLCH Pixel Palette`,
    description: `Палитра из ${colorCount} цветов (${harmony}) от @${username}. Экспорт в GPL, JASC PAL, HEX, JSON.`,
    robots: isPublic ? { index: true, follow: true } : { index: false, follow: false },
    alternates: {
      canonical: `https://oklchpalette.ru/ru/p/${slug}`,
    },
    openGraph: {
      title: `${title} | OKLCH Pixel Palette`,
      description: `Палитра из ${colorCount} цветов (${harmony}) от @${username}.`,
      url: `https://oklchpalette.ru/ru/p/${slug}`,
      type: 'website',
    },
  };
}

export default async function RuPaletteDetailPage({ params }: PaletteDetailPageProps) {
  const { slug } = await params;

  if (!isSupabaseAvailable()) notFound();

  const supabase = await createClient();
  if (!supabase) notFound();

  const { data: { user } } = await (supabase as any).auth.getUser();

  const { data: row } = await (supabase as any)
    .from('palettes')
    .select(`
      id, slug, title, description, colors, color_count, harmony, seed,
      base_hex, tags, visibility, published_at, owner_id,
      profiles!owner_id(username, display_name),
      source_palette_id
    `)
    .eq('slug', slug)
    .single();

  if (!row) notFound();

  const visibility = (row as any).visibility as string;
  const ownerId = (row as any).owner_id as string;
  const isOwner = user?.id === ownerId;

  if (visibility === 'private' && !isOwner) {
    notFound();
  }

  const palette = deserializePaletteRow(row as Parameters<typeof deserializePaletteRow>[0]);
  const profiles = Array.isArray((row as any).profiles) ? (row as any).profiles[0] ?? null : (row as any).profiles as { username: string; display_name: string | null } | null;

  const { data: likeCountData } = await (supabase as any)
    .rpc('get_palette_like_count', { target_palette_id: (row as any).id });
  const likeCount = Number(likeCountData ?? 0);

  let initialLiked = false;
  let initialBookmarked = false;
  if (user) {
    const [likeRes, bookmarkRes] = await Promise.all([
      (supabase as any)
        .from('palette_likes')
        .select('user_id')
        .eq('user_id', user.id)
        .eq('palette_id', (row as any).id)
        .maybeSingle(),
      (supabase as any)
        .from('palette_bookmarks')
        .select('user_id')
        .eq('user_id', user.id)
        .eq('palette_id', (row as any).id)
        .maybeSingle(),
    ]);
    initialLiked = !!likeRes.data;
    initialBookmarked = !!bookmarkRes.data;
  }

  let sourceTitle: string | null = null;
  let sourceSlug: string | null = null;
  const sourcePaletteId = (row as any).source_palette_id as string | null;
  if (sourcePaletteId) {
    const { data: sourceData } = await (supabase as any)
      .from('palettes')
      .select('title, slug, visibility')
      .eq('id', sourcePaletteId)
      .single();
    if (sourceData && (sourceData as any).visibility === 'public') {
      sourceTitle = (sourceData as any).title ?? null;
      sourceSlug = (sourceData as any).slug ?? null;
    }
  }

  const colors = Array.isArray(row.colors) ? row.colors as Array<{ hex: string; role: string; oklch: { l: number; c: number; h: number | null } }> : [];

  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white">
      <header className="sticky top-0 z-40 border-b border-white/10 glass-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <Link href="/ru" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
              <Palette className="w-4 h-4" />
            </div>
            <span className="text-sm font-mono font-black text-white hidden sm:block">OKLCH PIXEL PALETTE</span>
          </Link>
          <nav className="flex items-center gap-3">
            <Link href="/ru/explore" className="text-xs font-mono text-gray-300 hover:text-white transition-colors hidden sm:inline">Галерея</Link>
            {user ? (
              <Link href="/ru/dashboard" className="text-xs font-mono text-gray-300 hover:text-white transition-colors hidden sm:inline">Дашборд</Link>
            ) : (
              <Link href="/ru/login" className="text-xs font-mono text-gray-300 hover:text-white transition-colors">Войти</Link>
            )}
            <Link href="/ru/create" className="px-3 py-1.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all">Редактор</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          <div className="lg:col-span-7 space-y-6">
            {visibility !== 'public' && (
              <div className="inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400">
                {visibility === 'private' ? '🔒 Приватная' : '🔗 По ссылке'}
              </div>
            )}
            <div className="space-y-3">
              <h1 className="text-2xl sm:text-3xl font-mono font-extrabold text-white">{(row as any).title ?? 'Без названия'}</h1>
              {(row as any).description && (
                <p className="text-sm text-gray-300 font-sans">{(row as any).description}</p>
              )}
              <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-gray-400">
                {profiles?.username && (
                  <Link href={`/u/${profiles.username}`} className="flex items-center gap-1.5 hover:text-purple-300 transition-colors">
                    <User className="w-3.5 h-3.5" />
                    @{profiles.username}
                  </Link>
                )}
                <span>{(row as any).color_count} цветов</span>
                {(row as any).harmony && <span>{(row as any).harmony}</span>}
              </div>
            </div>

            <div className="space-y-2">
              {colors.map((c, i) => (
                <div key={i} className="flex items-center gap-3 glass-panel rounded-xl p-3 border border-white/10">
                  <div className="w-12 h-12 rounded-lg border border-white/20 flex-shrink-0" style={{ backgroundColor: c.hex }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-mono font-bold text-white">{c.role.toUpperCase()}</div>
                    <div className="text-[11px] font-mono text-gray-400">
                      {c.hex.toUpperCase()} · L:{(c.oklch.l * 100).toFixed(1)}% C:{c.oklch.c.toFixed(3)} H:{c.oklch.h !== null ? `${Math.round(c.oklch.h)}°` : 'neutral'}
                    </div>
                  </div>
                  <CopyHexButton hex={c.hex} locale="ru" />
                </div>
              ))}
            </div>

            {(row as any).tags && (row as any).tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {(row as any).tags.map((tag: string) => (
                  <span key={tag} className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">#{tag}</span>
                ))}
              </div>
            )}

            <PaletteActions
              paletteId={(row as any).id}
              paletteSlug={(row as any).slug}
              initialLiked={initialLiked}
              initialBookmarked={initialBookmarked}
              initialLikeCount={likeCount}
              isAuthenticated={!!user}
              isOwner={isOwner}
              locale="ru"
              sourcePaletteId={sourcePaletteId}
              sourceTitle={sourceTitle}
              sourceSlug={sourceSlug}
            />
          </div>

          <div className="lg:col-span-5">
            {palette && <BklitLightnessChart palette={palette} locale="ru" />}
          </div>
        </div>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center flex flex-col sm:flex-row items-center justify-center gap-3">
        <div className="flex items-center gap-1">
          <Terminal className="w-3.5 h-3.5 text-purple-400 inline" />
          <span>OKLCH Pixel Palette &copy; {new Date().getFullYear()}</span>
        </div>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link
          href="/ru/privacy"
          className="text-gray-400 hover:text-white transition-colors underline-offset-4 hover:underline"
        >
          Политика конфиденциальности
        </Link>
      </footer>
    </div>
  );
}
