import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { SpriteRecolor } from '@/components/tools/SpriteRecolor';

export const metadata: Metadata = {
  title: 'Sprite Recolor — Palette Mapping for Pixel Art | OKLCH Pixel Palette',
  description: 'Upload a pixel art sprite and remap its colors to a target palette using perceptual OKLCH color distance. Runs entirely in your browser.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools/sprite-recolor',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools/sprite-recolor' },
  },
  openGraph: {
    title: 'Sprite Recolor — Palette Mapping for Pixel Art',
    description: 'Upload a pixel art sprite and remap its colors to a target palette in your browser.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools/sprite-recolor',
  },
};

export default function SpriteRecolorPage() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Tools', item: 'https://oklchpalette.ru/tools' },
      { '@type': 'ListItem', position: 3, name: 'Sprite Recolor', item: 'https://oklchpalette.ru/tools/sprite-recolor' },
    ],
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Tools', href: '/tools' },
        { label: 'Sprite Recolor' },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Sprite Recolor
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Remap small pixel art sprites to a target palette using perceptual OKLCH color matching.
            Alpha transparency is preserved and no images leave your device.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">OKLCH perceptual distance</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">Alpha preserved</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">Browser-local</span>
          </div>
        </section>

        <SpriteRecolor locale="en" />

        <section className="space-y-4">
          <h2 className="text-lg font-mono font-bold text-white">How it works</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { title: 'Perceptual matching', desc: 'Each non-transparent pixel is mapped to the closest target color using OKLCH ΔE distance rather than simple RGB.' },
              { title: 'Exact alpha preservation', desc: 'Transparent and semi-transparent pixels maintain their exact alpha channel values.' },
              { title: 'Pixel art safe', desc: 'No resampling or bilinear blur is introduced — pixel boundaries remain razor sharp.' },
              { title: 'Local performance', desc: 'Processes directly on HTML5 Canvas without network uploads.' },
            ].map(({ title, desc }) => (
              <div key={title} className="glass-panel rounded-xl border border-white/10 p-4 space-y-1">
                <h3 className="text-xs font-mono font-bold text-white">{title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </ToolPageLayout>
  );
}
