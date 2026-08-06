import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/server';
import { DashboardContent } from '@/components/dashboard/DashboardContent';
import { isSupabaseAvailable } from '@/lib/supabase/client';
import { Palette, Terminal } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Dashboard | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default async function DashboardPage() {
  if (!isSupabaseAvailable()) {
    return <DashboardUnavailable locale="en" />;
  }

  const supabase = await createClient();
  if (!supabase) return <DashboardUnavailable locale="en" />;

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect('/login?redirect=/dashboard');

  // Fetch user data in parallel
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

  const profile = profileRes.data;
  const palettes = palettesRes.data ?? [];
  const savedCount = savedCountRes.count ?? 0;
  const publicCount = publicCountRes.count ?? 0;

  return (
    <DashboardContent
      locale="en"
      profile={profile}
      palettes={palettes}
      savedCount={savedCount}
      publicCount={publicCount}
    />
  );
}

function DashboardUnavailable({ locale }: { locale: 'en' | 'ru' }) {
  const isRu = locale === 'ru';
  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col">
      <header className="border-b border-white/10 bg-zinc-950/80 h-14 flex items-center px-6">
        <Link href={isRu ? '/ru' : '/'} className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400">
            <Palette className="w-4 h-4" />
          </div>
          <span className="text-sm font-mono font-black text-white">OKLCH PIXEL PALETTE</span>
        </Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="text-center space-y-4 max-w-md">
          <Terminal className="w-12 h-12 text-purple-400 mx-auto" />
          <h1 className="text-2xl font-mono font-bold text-white">
            {isRu ? 'Аккаунты не настроены' : 'Accounts not configured'}
          </h1>
          <p className="text-sm text-gray-400 font-sans">
            {isRu
              ? 'Облачные функции требуют настройки Supabase. Редактор работает без аккаунта.'
              : 'Cloud features require Supabase setup. The editor works without an account.'}
          </p>
          <Link
            href={isRu ? '/ru/create' : '/create'}
            className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all"
          >
            {isRu ? 'Открыть редактор' : 'Open Studio'}
          </Link>
        </div>
      </main>
    </div>
  );
}
