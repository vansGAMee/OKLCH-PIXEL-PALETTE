import type { Metadata } from 'next';
import { HomePageContent } from '@/components/home/HomePageContent';

export const metadata: Metadata = {
  title: 'OKLCH Palette Generator for Pixel Art, Games and UI',
  description:
    'Create balanced OKLCH color palettes with 2–9 colors, pixel art previews, perceptual lightness analysis and polished PNG export.',
  alternates: {
    canonical: 'https://oklchpalette.ru/',
    languages: {
      en: 'https://oklchpalette.ru/',
      ru: 'https://oklchpalette.ru/ru',
      'x-default': 'https://oklchpalette.ru/',
    },
  },
  openGraph: {
    title: 'OKLCH Palette Generator for Pixel Art, Games and UI',
    description:
      'Create balanced OKLCH color palettes with 2–9 colors, pixel art previews, perceptual lightness analysis and polished PNG export.',
    url: 'https://oklchpalette.ru/',
    siteName: 'OKLCH Pixel Palette',
    locale: 'en_US',
    alternateLocale: ['ru_RU'],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'OKLCH Palette Generator for Pixel Art, Games and UI',
    description:
      'Create balanced OKLCH color palettes with 2–9 colors, pixel art previews, perceptual lightness analysis and polished PNG export.',
  },
};

export default function Page() {
  return <HomePageContent locale="en" />;
}
