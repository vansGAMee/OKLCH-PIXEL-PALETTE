import type { Metadata } from 'next';
import { Suspense } from 'react';
import { PaletteStudio } from '@/components/editor/PaletteStudio';

export const metadata: Metadata = {
  title: 'Создать палитру OKLCH | OKLCH Pixel Palette',
  description:
    'Настройте гармонию и размер палитры, проверьте светлоту и экспортируйте цвета для пиксель-арта, игр и графических редакторов.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/create',
    languages: {
      en: 'https://oklchpalette.ru/create',
      ru: 'https://oklchpalette.ru/ru/create',
      'x-default': 'https://oklchpalette.ru/create',
    },
  },
  openGraph: {
    title: 'Создать палитру OKLCH | OKLCH Pixel Palette',
    description:
      'Настройте гармонию и размер палитры, проверьте светлоту и экспортируйте цвета для пиксель-арта, игр и графических редакторов.',
    url: 'https://oklchpalette.ru/ru/create',
    siteName: 'OKLCH Pixel Palette',
    locale: 'ru_RU',
    alternateLocale: ['en_US'],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Создать палитру OKLCH | OKLCH Pixel Palette',
    description:
      'Настройте гармонию и размер палитры, проверьте светлоту и экспортируйте цвета для пиксель-арта, игр и графических редакторов.',
  },
};

export default function RuCreatePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#090909]" />}>
      <PaletteStudio locale="ru" />
    </Suspense>
  );
}
