import type { Metadata } from 'next';
import { HomePageContent } from '@/components/home/HomePageContent';
import { createClient } from '@/lib/supabase/server';
import { isSupabaseAvailable } from '@/lib/supabase/client';

export const metadata: Metadata = {
  title: 'Генератор палитр OKLCH для пиксель-арта, игр и интерфейсов',
  description:
    'Собирайте палитры OKLCH из 2–9 цветов, проверяйте светлоту, смотрите результат на пиксель-арте и экспортируйте палитру в PNG, GPL и PAL.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru',
    languages: {
      en: 'https://oklchpalette.ru/',
      ru: 'https://oklchpalette.ru/ru',
      'x-default': 'https://oklchpalette.ru/',
    },
  },
  openGraph: {
    title: 'Генератор палитр OKLCH для пиксель-арта, игр и интерфейсов',
    description:
      'Собирайте палитры OKLCH из 2–9 цветов, проверяйте светлоту, смотрите результат на пиксель-арте и экспортируйте палитру в PNG, GPL и PAL.',
    url: 'https://oklchpalette.ru/ru',
    siteName: 'OKLCH Pixel Palette',
    locale: 'ru_RU',
    alternateLocale: ['en_US'],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Генератор палитр OKLCH для пиксель-арта, игр и интерфейсов',
    description:
      'Собирайте палитры OKLCH из 2–9 цветов, проверяйте светлоту, смотрите результат на пиксель-арте и экспортируйте палитру в PNG, GPL и PAL.',
  },
};

export default async function RuHomePage() {
  let isAuthenticated = false;
  if (isSupabaseAvailable()) {
    const supabase = await createClient();
    if (supabase) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data: { user } } = await (supabase as any).auth.getUser();
      isAuthenticated = !!user;
    }
  }
  return <HomePageContent locale="ru" isAuthenticated={isAuthenticated} />;
}
