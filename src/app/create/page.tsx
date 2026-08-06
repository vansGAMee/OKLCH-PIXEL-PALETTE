import type { Metadata } from 'next';
import { PaletteStudio } from '@/components/editor/PaletteStudio';

export const metadata: Metadata = {
  title: 'Create an OKLCH Palette | OKLCH Pixel Palette',
  description:
    'Generate and inspect OKLCH palettes with adjustable harmony, 2–9 colors, pixel art previews, lightness analysis and PNG export.',
  alternates: {
    canonical: 'https://oklchpalette.ru/create',
  },
  openGraph: {
    title: 'Create an OKLCH Palette | OKLCH Pixel Palette',
    description:
      'Generate and inspect OKLCH palettes with adjustable harmony, 2–9 colors, pixel art previews, lightness analysis and PNG export.',
    url: 'https://oklchpalette.ru/create',
    siteName: 'OKLCH Pixel Palette',
    type: 'website',
    images: ['https://oklchpalette.ru/opengraph-image'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Create an OKLCH Palette | OKLCH Pixel Palette',
    description:
      'Generate and inspect OKLCH palettes with adjustable harmony, 2–9 colors, pixel art previews, lightness analysis and PNG export.',
    images: ['https://oklchpalette.ru/twitter-image'],
  },
};

export default function CreatePage() {
  return <PaletteStudio />;
}
