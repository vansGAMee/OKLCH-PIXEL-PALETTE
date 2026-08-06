import type { Metadata } from 'next';
import { PaletteStudio } from '@/components/editor/PaletteStudio';

export const metadata: Metadata = {
  title: 'Create an OKLCH Palette | OKLCH Pixel Palette',
  description:
    'Generate and inspect OKLCH palettes with adjustable harmony, 2–9 colors, pixel art previews, lightness analysis and artist-friendly export formats.',
  alternates: {
    canonical: 'https://oklchpalette.ru/create',
    languages: {
      en: 'https://oklchpalette.ru/create',
      ru: 'https://oklchpalette.ru/ru/create',
      'x-default': 'https://oklchpalette.ru/create',
    },
  },
  openGraph: {
    title: 'Create an OKLCH Palette | OKLCH Pixel Palette',
    description:
      'Generate and inspect OKLCH palettes with adjustable harmony, 2–9 colors, pixel art previews, lightness analysis and artist-friendly export formats.',
    url: 'https://oklchpalette.ru/create',
    siteName: 'OKLCH Pixel Palette',
    locale: 'en_US',
    alternateLocale: ['ru_RU'],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Create an OKLCH Palette | OKLCH Pixel Palette',
    description:
      'Generate and inspect OKLCH palettes with adjustable harmony, 2–9 colors, pixel art previews, lightness analysis and artist-friendly export formats.',
  },
};

export default function CreatePage() {
  return <PaletteStudio locale="en" />;
}
