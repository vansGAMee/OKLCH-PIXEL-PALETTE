import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { createClient } from '@/lib/supabase/server';
import { DashboardContent } from '@/components/dashboard/DashboardContent';
import { isSupabaseAvailable } from '@/lib/supabase/client';

export const metadata: Metadata = {
  title: 'Панель управления | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default async function RuDashboardPage() {
  if (!isSupabaseAvailable()) {
    redirect('/dashboard');
  }

  const supabase = await createClient();
  if (!supabase) redirect('/ru/login?redirect=/ru/dashboard');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: { user } } = await (supabase as any).auth.getUser();
  if (!user) redirect('/ru/login?redirect=/ru/dashboard');

  const [profileRes, palettesRes, savedCountRes, publicCountRes, bookmarksRes] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).single(),
    supabase
      .from('palettes')
      .select('id, slug, title, color_count, visibility, featured_position, created_at, updated_at, colors, harmony, seed, base_hex')
      .eq('owner_id', user.id)
      .order('updated_at', { ascending: false })
      .limit(30),
    supabase.from('palettes').select('id', { count: 'exact', head: true }).eq('owner_id', user.id),
    supabase.from('palettes').select('id', { count: 'exact', head: true }).eq('owner_id', user.id).eq('visibility', 'public'),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (supabase as any)
      .from('palette_bookmarks')
      .select('palette_id, palettes!palette_id(id, slug, title, color_count, harmony, colors, profiles!owner_id(username, display_name))')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .limit(48),
  ]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rawBookmarks = (bookmarksRes.data ?? []) as any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const bookmarks = rawBookmarks.map((b: any) => {
    const p = b.palettes;
    if (!p) return null;
    return {
      id: p.id, slug: p.slug, title: p.title,
      color_count: p.color_count, harmony: p.harmony, colors: p.colors,
      profiles: Array.isArray(p.profiles) ? p.profiles[0] ?? null : p.profiles,
    };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  }).filter(Boolean) as any[];

  return (
    <DashboardContent
      locale="ru"
      profile={profileRes.data}
      palettes={palettesRes.data ?? []}
      savedCount={savedCountRes.count ?? 0}
      publicCount={publicCountRes.count ?? 0}
      bookmarks={bookmarks}
    />
  );
}
