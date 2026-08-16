/* eslint-disable @typescript-eslint/no-explicit-any */
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/server';
import { isSupabaseAvailable } from '@/lib/supabase/client';
import { PaletteGalleryCard } from '@/components/gallery/PaletteGalleryCard';
import { Palette, Terminal, User } from 'lucide-react';

interface ProfilePageProps {
  params: Promise<{ username: string }>;
}

export async function generateMetadata({ params }: ProfilePageProps): Promise<Metadata> {
  const { username } = await params;
  return {
    title: `@${username} | OKLCH Pixel Palette`,
    description: `Public palettes by @${username} on OKLCH Pixel Palette.`,
    alternates: {
      canonical: `https://oklchpalette.ru/u/${username}`,
    },
  };
}

export default async function ProfilePage({ params }: ProfilePageProps) {
  const { username } = await params;

  if (!isSupabaseAvailable()) {
    notFound();
  }

  const supabase = await createClient();
  if (!supabase) notFound();

  // Fetch profile
  const { data: profile } = await (supabase as any)
    .from('profiles')
    .select('id, username, display_name, bio, created_at')
    .eq('username', username.toLowerCase())
    .single();

  if (!profile) notFound();

  // Fetch public palettes by this user
  const { data: palettes } = await (supabase as any)
    .from('palettes')
    .select('id, slug, title, color_count, harmony, colors, published_at, owner_id, profiles!owner_id(username, display_name)')
    .eq('owner_id', (profile as any).id)
    .eq('visibility', 'public')
    .order('published_at', { ascending: false })
    .limit(24);

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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full space-y-8">
        {/* Profile Header */}
        <div className="glass-panel rounded-2xl border border-white/10 p-6 sm:p-8">
          <div className="flex items-start gap-5">
            {/* Avatar */}
            <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-purple-400 flex-shrink-0">
              <User className="w-8 h-8 sm:w-10 sm:h-10" />
            </div>
            <div className="space-y-1 min-w-0">
              <h1 className="text-xl sm:text-2xl font-mono font-extrabold text-white">
                {(profile as any).display_name ?? `@${(profile as any).username}`}
              </h1>
              <p className="text-xs font-mono text-purple-400">@{(profile as any).username}</p>
              {(profile as any).bio && (
                <p className="text-sm text-gray-300 font-sans mt-2">{(profile as any).bio}</p>
              )}
              <p className="text-xs font-mono text-gray-500 mt-2">
                {((palettes as any[]) ?? []).length} public palettes
              </p>
            </div>
          </div>
        </div>

        {/* Palettes Grid */}
        <section aria-label="Public palettes">
          <h2 className="text-sm font-mono font-bold text-white mb-4">Palettes</h2>
          {((palettes as any[]) ?? []).length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {((palettes as any[]) ?? []).map((p: any) => (
                <PaletteGalleryCard
                  key={p.id}
                  palette={{
                    ...p,
                    profiles: Array.isArray(p.profiles) ? p.profiles[0] ?? null : p.profiles as { username: string; display_name: string | null } | null,
                  }}
                  locale="en"
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-16 text-gray-400 font-mono text-sm">
              No public palettes yet.
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center flex flex-col sm:flex-row items-center justify-center gap-3">
        <div className="flex items-center gap-1">
          <Terminal className="w-3.5 h-3.5 text-purple-400 inline" />
          <span>OKLCH Pixel Palette &copy; {new Date().getFullYear()}</span>
        </div>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link
          href="/privacy"
          className="text-gray-400 hover:text-white transition-colors underline-offset-4 hover:underline"
        >
          Privacy Policy
        </Link>
      </footer>
    </div>
  );
}
