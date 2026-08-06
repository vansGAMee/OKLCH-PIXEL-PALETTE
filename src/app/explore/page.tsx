/* eslint-disable @typescript-eslint/no-explicit-any */
import type { Metadata } from 'next';
import { createClient } from '@/lib/supabase/server';
import { ExploreContent } from '@/components/gallery/ExploreContent';

export const metadata: Metadata = {
  title: 'Explore Palettes | OKLCH Pixel Palette',
  description: 'Browse community OKLCH pixel art palettes — sorted by newest and most liked. Export to GPL, JASC PAL, HEX, JSON.',
  alternates: {
    canonical: 'https://oklchpalette.ru/explore',
    languages: { 'ru': 'https://oklchpalette.ru/ru/explore' },
  },
};

interface ExplorePageProps {
  searchParams: Promise<{ sort?: string; q?: string; page?: string }>;
}

export default async function ExplorePage({ searchParams }: ExplorePageProps) {
  const params = await searchParams;
  const sort = params.sort === 'liked' ? 'liked' : 'newest';
  const page = Math.max(1, parseInt(params.page ?? '1', 10));
  const limit = 24;
  const offset = (page - 1) * limit;

  const supabase = await createClient();

  let palettes: Array<{
    id: string;
    slug: string;
    title: string;
    color_count: number;
    harmony: string | null;
    colors: unknown;
    published_at: string | null;
    owner_id: string;
    profiles: { username: string; display_name: string | null } | null;
    like_count?: number;
  }> = [];

  let totalCount = 0;

  if (supabase) {
    const { data, count } = await (supabase as any)
      .from('palettes')
      .select(`
        id, slug, title, color_count, harmony, colors, published_at, owner_id,
        profiles!owner_id(username, display_name)
      `, { count: 'exact' })
      .eq('visibility', 'public')
      .order('published_at', { ascending: false })
      .range(offset, offset + limit - 1);

    palettes = (data ?? []).map((p: any) => ({
      ...p,
      profiles: Array.isArray(p.profiles) ? p.profiles[0] ?? null : p.profiles as { username: string; display_name: string | null } | null,
    }));
    totalCount = count ?? 0;
  }

  return (
    <ExploreContent
      locale="en"
      palettes={palettes}
      totalCount={totalCount}
      page={page}
      limit={limit}
      sort={sort}
      isSupabaseAvailable={Boolean(supabase)}
    />
  );
}
