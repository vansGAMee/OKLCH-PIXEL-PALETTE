import type { Metadata } from 'next';
import { HomePageContent } from '@/components/home/HomePageContent';
import { createClient } from '@/lib/supabase/server';
import { isSupabaseAvailable } from '@/lib/supabase/client';

export const metadata: Metadata = {
  title: 'OKLCH Palette Generator — AI & Perceptual Color Engine for Pixel Art, Games and UI',
  description:
    'Generate balanced OKLCH color palettes from text descriptions with local AI or manual harmonies. 2–9 colors, pixel art sprite previews, lightness ladder and CSS/PNG export.',
  alternates: {
    canonical: 'https://oklchpalette.ru/',
    languages: {
      en: 'https://oklchpalette.ru/',
      ru: 'https://oklchpalette.ru/ru',
      'x-default': 'https://oklchpalette.ru/',
    },
  },
  openGraph: {
    title: 'OKLCH Palette Generator — AI & Perceptual Color Engine for Pixel Art, Games and UI',
    description:
      'Generate balanced OKLCH color palettes from text descriptions with local AI or manual harmonies. 2–9 colors, pixel art sprite previews, lightness ladder and CSS/PNG export.',
    url: 'https://oklchpalette.ru/',
    siteName: 'OKLCH Pixel Palette',
    locale: 'en_US',
    alternateLocale: ['ru_RU'],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'OKLCH Palette Generator — AI & Perceptual Color Engine for Pixel Art, Games and UI',
    description:
      'Generate balanced OKLCH color palettes from text descriptions with local AI or manual harmonies. 2–9 colors, pixel art sprite previews, lightness ladder and CSS/PNG export.',
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
