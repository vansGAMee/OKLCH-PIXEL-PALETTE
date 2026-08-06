/* eslint-disable @typescript-eslint/no-explicit-any */
import type { Metadata } from 'next';
import { createClient } from '@/lib/supabase/server';
import { ExploreContent } from '@/components/gallery/ExploreContent';

export const metadata: Metadata = {
  title: 'Галерея палитр | OKLCH Pixel Palette',
  description: 'Просматривайте OKLCH пиксельные палитры сообщества. Экспорт в GPL, JASC PAL, HEX, JSON.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/explore',
    languages: { 'en': 'https://oklchpalette.ru/explore' },
  },
};

interface ExplorePageProps {
  searchParams: Promise<{ sort?: string; page?: string }>;
}

export default async function RuExplorePage({ searchParams }: ExplorePageProps) {
  const params = await searchParams;
  const page = Math.max(1, parseInt(params.page ?? '1', 10));
  const limit = 24;
  const offset = (page - 1) * limit;

  const supabase = await createClient();
  let palettes: Array<{
    id: string; slug: string; title: string; color_count: number;
    harmony: string | null; colors: unknown; published_at: string | null;
    owner_id: string;
    profiles: { username: string; display_name: string | null } | null;
  }> = [];
  let totalCount = 0;

  if (supabase) {
    const { data, count } = await (supabase as any)
      .from('palettes')
      .select('id, slug, title, color_count, harmony, colors, published_at, owner_id, profiles!owner_id(username, display_name)', { count: 'exact' })
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
      locale="ru"
      palettes={palettes}
      totalCount={totalCount}
      page={page}
      limit={limit}
      sort="newest"
      isSupabaseAvailable={Boolean(supabase)}
    />
  );
}
