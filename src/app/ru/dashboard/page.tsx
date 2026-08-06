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
    redirect('/dashboard'); // Reuse EN unavailable state
  }

  const supabase = await createClient();
  if (!supabase) redirect('/ru/login?redirect=/ru/dashboard');

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect('/ru/login?redirect=/ru/dashboard');

  const [profileRes, palettesRes, savedCountRes, publicCountRes] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).single(),
    supabase
      .from('palettes')
      .select('id, slug, title, color_count, visibility, featured_position, created_at, updated_at, colors, harmony, seed, base_hex')
      .eq('owner_id', user.id)
      .order('updated_at', { ascending: false })
      .limit(30),
    supabase.from('palettes').select('id', { count: 'exact', head: true }).eq('owner_id', user.id),
    supabase.from('palettes').select('id', { count: 'exact', head: true }).eq('owner_id', user.id).eq('visibility', 'public'),
  ]);

  return (
    <DashboardContent
      locale="ru"
      profile={profileRes.data}
      palettes={palettesRes.data ?? []}
      savedCount={savedCountRes.count ?? 0}
      publicCount={publicCountRes.count ?? 0}
    />
  );
}
