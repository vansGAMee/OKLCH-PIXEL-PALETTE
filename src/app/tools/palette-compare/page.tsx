import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { PaletteCompareTool } from '@/components/tools/PaletteCompareTool';

export const metadata: Metadata = {
  title: 'Palette Compare — OKLCH Side-by-Side | OKLCH Pixel Palette',
  description: 'Compare two color palettes side by side using OKLCH perceptual metrics: lightness spread, chroma, hue span, and perceptual distance between palettes.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools/palette-compare',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools/palette-compare' },
  },
  openGraph: {
    title: 'Palette Compare — OKLCH Side-by-Side',
    description: 'Compare two color palettes side by side using OKLCH metrics.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools/palette-compare',
  },
};

export default function PaletteComparePage() {
  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Tools', href: '/tools' },
        { label: 'Palette Compare' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Palette Compare
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Paste two palettes and compare their OKLCH perceptual properties side by side.
            Lightness spread, chroma balance, hue span, and perceptual distance.
          </p>
        </section>

        <PaletteCompareTool locale="en" />

        <section className="space-y-3">
          <h2 className="text-base font-mono font-bold text-white">About the metrics</h2>
          <ul className="space-y-2 text-xs text-gray-400 font-sans">
            <li><strong className="text-gray-300">L range</strong> — Lightness spread between the darkest and lightest color. Higher = more contrast potential.</li>
            <li><strong className="text-gray-300">C range</strong> — Spread in colorfulness. Higher = palette contains both muted and saturated colors.</li>
            <li><strong className="text-gray-300">Hue span</strong> — Degrees of hue wheel covered. 0 = monochromatic, 180+ = complementary.</li>
            <li><strong className="text-gray-300">Avg nearest ΔE</strong> — How similar the two palettes are overall. Lower = more similar.</li>
          </ul>
        </section>
      </main>
    </ToolPageLayout>
  );
}
