import type { Metadata } from 'next';
import { HomePageContent } from '@/components/home/HomePageContent';
import { createClient } from '@/lib/supabase/server';
import { isSupabaseAvailable } from '@/lib/supabase/client';

export const metadata: Metadata = {
  title: 'AI OKLCH Palette Generator for Pixel Art & UI',
  description:
    'Generate balanced OKLCH color palettes from text descriptions or color harmonies with local in-browser AI and sprite previews.',
  alternates: {
    canonical: 'https://oklchpalette.ru/',
    languages: {
      en: 'https://oklchpalette.ru/',
      ru: 'https://oklchpalette.ru/ru',
      'x-default': 'https://oklchpalette.ru/',
    },
  },
  openGraph: {
    title: 'AI OKLCH Palette Generator for Pixel Art & UI',
    description:
      'Generate balanced OKLCH color palettes from text descriptions or color harmonies with local in-browser AI and sprite previews.',
    url: 'https://oklchpalette.ru/',
    siteName: 'OKLCH Pixel Palette',
    locale: 'en_US',
    alternateLocale: ['ru_RU'],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'AI OKLCH Palette Generator for Pixel Art & UI',
    description:
      'Generate balanced OKLCH color palettes from text descriptions or color harmonies with local in-browser AI and sprite previews.',
  },
};

export default async function Page() {
  let isAuthenticated = false;
  if (isSupabaseAvailable()) {
    const supabase = await createClient();
    if (supabase) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data: { user } } = await (supabase as any).auth.getUser();
      isAuthenticated = !!user;
    }
  }
  return <HomePageContent locale="en" isAuthenticated={isAuthenticated} />;
}
