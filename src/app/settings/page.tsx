import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { createClient } from '@/lib/supabase/server';
import { isSupabaseAvailable } from '@/lib/supabase/client';
import { SettingsContent } from '@/components/settings/SettingsContent';

export const metadata: Metadata = {
  title: 'Settings | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default async function SettingsPage() {
  if (!isSupabaseAvailable()) {
    redirect('/');
  }

  const supabase = await createClient();
  if (!supabase) redirect('/');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: { user }, error } = await (supabase as any).auth.getUser();
  if (error || !user) redirect('/login?redirect=/settings');

  const { data: profile } = await supabase.from('profiles').select('*').eq('id', user.id).single();

  return (
    <SettingsContent
      locale="en"
      profile={profile}
      email={user.email ?? ''}
    />
  );
}
