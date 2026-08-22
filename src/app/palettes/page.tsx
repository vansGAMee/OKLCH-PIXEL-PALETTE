import type { Metadata } from 'next';
import Link from 'next/link';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { CURATED_PALETTES } from '@/lib/tools/curatedPalettes';
import { ChevronRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Curated Pixel Art Palettes | OKLCH Pixel Palette',
  description: 'Hand-crafted, perceptually balanced color palettes for pixel art, games, and UI design. Export to Aseprite, GIMP, CSS, and open in studio.',
  alternates: {
    canonical: 'https://oklchpalette.ru/palettes',
    languages: { 'ru': 'https://oklchpalette.ru/ru/palettes' },
  },
  openGraph: {
    title: 'Curated Pixel Art Palettes | OKLCH Pixel Palette',
    description: 'Hand-crafted, perceptually balanced color palettes for pixel art.',
    type: 'website',
    url: 'https://oklchpalette.ru/palettes',
  },
};

export default function CuratedPalettesIndexPage() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Curated Palettes', item: 'https://oklchpalette.ru/palettes' },
    ],
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[{ label: 'Curated Palettes' }]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-12">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Curated Pixel Art Palettes
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            A hand-crafted collection of theme-focused palettes designed with OKLCH lightness balance.
            Ready to export for Aseprite, GIMP, CSS, or customize in the studio.
          </p>
        </section>

        <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {CURATED_PALETTES.map(p => (
            <Link
              key={p.slug}
              href={`/palettes/${p.slug}`}
              className="glass-panel rounded-2xl border border-white/10 hover:border-purple-500/40 p-5 group transition-all space-y-3 flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-sm font-mono font-bold text-white group-hover:text-purple-300 transition-colors">
                    {p.title}
                  </h2>
                  <ChevronRight className="w-4 h-4 text-gray-500 group-hover:text-purple-400 group-hover:translate-x-0.5 transition-all shrink-0" />
                </div>
                <p className="text-xs text-gray-400 font-sans leading-relaxed line-clamp-2">
                  {p.description}
                </p>
              </div>

              <div className="space-y-2">
                {/* Palette bar preview */}
                <div className="flex rounded-lg overflow-hidden border border-white/10 h-8">
                  {p.hexes.map((hex, i) => (
                    <div key={i} className="flex-1" style={{ backgroundColor: hex }} />
                  ))}
                </div>
                <div className="flex flex-wrap gap-1">
                  {p.tags.slice(0, 3).map(tag => (
                    <span key={tag} className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 text-gray-400">
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>
            </Link>
          ))}
        </section>
      </main>
    </ToolPageLayout>
  );
}
