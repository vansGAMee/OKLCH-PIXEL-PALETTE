import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { PaletteAnalyzer } from '@/components/tools/PaletteAnalyzer';

export const metadata: Metadata = {
  title: 'Palette Analyzer — OKLCH Diagnostic Tool | OKLCH Pixel Palette',
  description: 'Paste any color palette and get a detailed OKLCH diagnostic: lightness spread, near-duplicate detection, chroma balance, and optional perceptual fix.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools/palette-analyzer',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools/palette-analyzer' },
  },
  openGraph: {
    title: 'Palette Analyzer — OKLCH Diagnostic Tool',
    description: 'Paste any color palette and get a detailed OKLCH diagnostic.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools/palette-analyzer',
  },
};

export default function PaletteAnalyzerPage() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Tools', item: 'https://oklchpalette.ru/tools' },
      { '@type': 'ListItem', position: 3, name: 'Palette Analyzer', item: 'https://oklchpalette.ru/tools/palette-analyzer' },
    ],
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Tools', href: '/tools' },
        { label: 'Palette Analyzer' },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        {/* Hero */}
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Palette Analyzer
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Paste any set of hex colors and get an OKLCH-based diagnostic: lightness spread, near-duplicate detection,
            chroma balance, and hue span. Includes a perceptual fix for common issues.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">OKLCH</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">Browser-local</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">2–16 colors</span>
          </div>
        </section>

        {/* Tool */}
        <PaletteAnalyzer locale="en" />

        {/* What each metric means */}
        <section className="space-y-4">
          <h2 className="text-lg font-mono font-bold text-white">What each metric means</h2>
          <dl className="space-y-4">
            {[
              {
                term: 'L range (Lightness spread)',
                def: 'Difference in OKLCH L-value between the lightest and darkest color in the palette. A range of less than 25% usually means the palette will appear flat when used in pixel art.',
              },
              {
                term: 'ΔE (Delta E)',
                def: 'Perceptual distance between two colors in OKLCH space. Values below ~0.08 indicate colors that are visually very difficult to distinguish in pixel art context.',
              },
              {
                term: 'C range (Chroma spread)',
                def: 'Spread in colorfulness/saturation across the palette. High C range means the palette includes both muted and saturated colors.',
              },
              {
                term: 'Hue span',
                def: 'The range of hue degrees covered by chromatic colors. Larger span = more varied hue relationships (analogous is narrow, complementary or triadic is wider).',
              },
              {
                term: 'Health score',
                def: "This site's own diagnostic score (0–100) based on measured OKLCH factors. Not an industry standard. Starts at 100; deductions applied for detected issues.",
              },
            ].map(({ term, def }) => (
              <div key={term} className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
                <dt className="text-sm font-mono font-bold text-white">{term}</dt>
                <dd className="text-xs text-gray-400 font-sans leading-relaxed">{def}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Limitations */}
        <section className="space-y-3">
          <h2 className="text-base font-mono font-bold text-white">Limitations</h2>
          <ul className="space-y-1 text-xs text-gray-400 font-sans">
            <li>• The automatic fix is a heuristic — it prioritizes lightness separation and may change colors more than expected.</li>
            <li>• The health score is this site&#39;s own metric, not an industry-standard measurement.</li>
            <li>• All computation runs in the browser. No colors are sent to a server.</li>
          </ul>
        </section>
      </main>
    </ToolPageLayout>
  );
}
