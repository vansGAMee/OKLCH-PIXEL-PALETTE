/* eslint-disable @typescript-eslint/no-explicit-any */
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/server';
import { isSupabaseAvailable } from '@/lib/supabase/client';
import { deserializePaletteRow } from '@/lib/palette/deserialize';
import { BklitLightnessChart } from '@/components/charts/BklitLightnessChart';
import { Palette, Terminal, User, Copy, Download, Heart, Bookmark, Shuffle } from 'lucide-react';

interface PaletteDetailPageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PaletteDetailPageProps): Promise<Metadata> {
  const { slug } = await params;
  const supabase = await createClient();
  if (!supabase) return { title: 'Palette | OKLCH Pixel Palette' };

  const { data } = await (supabase as any)
    .from('palettes')
    .select('title, base_hex, profiles!owner_id(username)')
    .eq('slug', slug)
    .eq('visibility', 'public')
    .single();

  if (!data) return { title: 'Palette Not Found' };

  const profiles = Array.isArray((data as any).profiles) ? (data as any).profiles[0] : (data as any).profiles as { username: string } | null;

  return {
    title: `${(data as any).title} | OKLCH Pixel Palette`,
    description: `OKLCH pixel art palette by @${profiles?.username ?? 'unknown'}. Export to GPL, JASC PAL, HEX, JSON.`,
    alternates: {
      canonical: `https://oklchpalette.ru/p/${slug}`,
    },
  };
}

export default async function PaletteDetailPage({ params }: PaletteDetailPageProps) {
  const { slug } = await params;

  if (!isSupabaseAvailable()) notFound();

  const supabase = await createClient();
  if (!supabase) notFound();

  const { data: row } = await (supabase as any)
    .from('palettes')
    .select(`
      id, slug, title, description, colors, color_count, harmony, seed,
      base_hex, tags, visibility, published_at, owner_id,
      profiles!owner_id(username, display_name),
      source_palette_id
    `)
    .eq('slug', slug)
    .eq('visibility', 'public')
    .single();

  if (!row) notFound();

  const palette = deserializePaletteRow(row as Parameters<typeof deserializePaletteRow>[0]);
  const profiles = Array.isArray((row as any).profiles) ? (row as any).profiles[0] ?? null : (row as any).profiles as { username: string; display_name: string | null } | null;

  // Like count
  const { data: likeCountData } = await (supabase as any)
    .rpc('get_palette_like_count', {
      target_palette_id: (row as any).id,
    });

  const likeCount = Number(likeCountData ?? 0);

  const colors = Array.isArray(row.colors) ? row.colors as Array<{ hex: string; role: string; oklch: { l: number; c: number; h: number | null } }> : [];

  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-white/10 glass-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
              <Palette className="w-4 h-4" />
            </div>
            <span className="text-sm font-mono font-black text-white hidden sm:block">OKLCH PIXEL PALETTE</span>
          </Link>
          <nav className="flex items-center gap-3">
            <Link href="/explore" className="text-xs font-mono text-gray-300 hover:text-white transition-colors">Explore</Link>
            <Link href="/create" className="px-3 py-1.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all">Studio</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left: main info */}
          <div className="lg:col-span-7 space-y-6">
            {/* Title + Meta */}
            <div className="space-y-3">
              <h1 className="text-2xl sm:text-3xl font-mono font-extrabold text-white">{(row as any).title}</h1>
              {(row as any).description && (
                <p className="text-sm text-gray-300 font-sans">{(row as any).description}</p>
              )}
              <div className="flex items-center gap-4 text-xs font-mono text-gray-400">
                <Link href={`/u/${profiles?.username}`} className="flex items-center gap-1.5 hover:text-purple-300 transition-colors">
                  <User className="w-3.5 h-3.5" />
                  @{profiles?.username}
                </Link>
                <span>{(row as any).color_count} colors</span>
                <span>{(row as any).harmony}</span>
                {likeCount !== null && likeCount !== undefined && (
                  <span className="flex items-center gap-1">
                    <Heart className="w-3.5 h-3.5 text-rose-400" />
                    {likeCount}
                  </span>
                )}
              </div>
            </div>

            {/* Color Swatches */}
            <div className="space-y-2">
              {colors.map((c, i) => (
                <div key={i} className="flex items-center gap-3 glass-panel rounded-xl p-3 border border-white/10">
                  <div
                    className="w-12 h-12 rounded-lg border border-white/20 flex-shrink-0"
                    style={{ backgroundColor: c.hex }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-mono font-bold text-white">{c.role.toUpperCase()}</div>
                    <div className="text-[11px] font-mono text-gray-400">
                      {c.hex.toUpperCase()} · L:{(c.oklch.l * 100).toFixed(1)}% C:{c.oklch.c.toFixed(3)} H:{c.oklch.h !== null ? `${Math.round(c.oklch.h)}°` : 'neutral'}
                    </div>
                  </div>
                  <button
                    onClick={undefined}
                    className="p-2 text-gray-400 hover:text-purple-400 transition-colors"
                    title="Copy HEX"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>

            {/* Tags */}
            {(row as any).tags && (row as any).tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {(row as any).tags.map((tag: string) => (
                  <span key={tag} className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">
                    #{tag}
                  </span>
                ))}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex flex-wrap gap-3">
              <Link
                href={`/create?seed=${(row as any).seed ?? 0}&harmony=${(row as any).harmony ?? 'splitComplementary'}`}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all"
              >
                <Shuffle className="w-4 h-4" />
                Remix in Studio
              </Link>
              <button className="flex items-center gap-1.5 px-4 py-2 text-sm font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-lg transition-all">
                <Heart className="w-4 h-4 text-rose-400" />
                Like
              </button>
              <button className="flex items-center gap-1.5 px-4 py-2 text-sm font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-lg transition-all">
                <Bookmark className="w-4 h-4 text-amber-400" />
                Save
              </button>
              <button className="flex items-center gap-1.5 px-4 py-2 text-sm font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-lg transition-all">
                <Download className="w-4 h-4" />
                Export
              </button>
            </div>
          </div>

          {/* Right: Lightness Chart */}
          <div className="lg:col-span-5">
            {palette && (
              <BklitLightnessChart palette={palette} locale="en" />
            )}
          </div>
        </div>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center">
        <Terminal className="w-3.5 h-3.5 text-purple-400 inline mr-1" />
        OKLCH Pixel Palette &copy; {new Date().getFullYear()}
      </footer>
    </div>
  );
}
