import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ImageToPalette } from '@/components/tools/ImageToPalette';

export const metadata: Metadata = {
  title: 'Image to Palette — Extract Pixel Art Colors | OKLCH Pixel Palette',
  description: 'Drop any image to extract a pixel art palette. Browser-local median-cut quantization with OKLCH perceptual color merging. No image is uploaded to a server.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools/image-to-palette',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools/image-to-palette' },
  },
  openGraph: {
    title: 'Image to Palette — Extract Pixel Art Colors',
    description: 'Drop any image to extract a pixel art palette. Browser-local, no uploads.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools/image-to-palette',
  },
};

export default function ImageToPalettePage() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Tools', item: 'https://oklchpalette.ru/tools' },
      { '@type': 'ListItem', position: 3, name: 'Image to Palette', item: 'https://oklchpalette.ru/tools/image-to-palette' },
    ],
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Tools', href: '/tools' },
        { label: 'Image → Palette' },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Image → Pixel Palette
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Drop any image to extract a reduced palette suitable for pixel art.
            Perceptual OKLCH color merging removes near-identical colors.
            Everything runs locally — your image is never uploaded.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">Browser-local</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">No uploads</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">OKLCH merging</span>
          </div>
        </section>

        <ImageToPalette locale="en" />

        <section className="space-y-4">
          <h2 className="text-lg font-mono font-bold text-white">How it works</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { title: 'Median-cut quantization', desc: 'Recursively splits the color space into buckets, averaging each bucket into a representative color.' },
              { title: 'OKLCH perceptual merging', desc: 'Near-identical colors (low ΔE in OKLCH space) are merged into a single weighted-average color.' },
              { title: 'Frequency display', desc: 'Each color shows what proportion of pixels it represents — useful for identifying dominant and accent tones.' },
              { title: 'Open in Studio', desc: 'The extracted palette is passed to the generator so you can fine-tune colors, change harmony, and export.' },
            ].map(({ title, desc }) => (
              <div key={title} className="glass-panel rounded-xl border border-white/10 p-4 space-y-1">
                <h3 className="text-xs font-mono font-bold text-white">{title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-mono font-bold text-white">Privacy</h2>
          <p className="text-sm text-gray-400 font-sans leading-relaxed">
            All image processing runs entirely in your browser using the Canvas API.
            No pixel data leaves your device. No analytics are collected on images you process.
          </p>
        </section>
      </main>
    </ToolPageLayout>
  );
}
