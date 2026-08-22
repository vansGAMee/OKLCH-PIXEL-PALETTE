import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ColorRampGenerator } from '@/components/tools/ColorRampGenerator';

export const metadata: Metadata = {
  title: 'Color Ramp Generator — OKLCH Pixel Art Shading | OKLCH Pixel Palette',
  description: 'Build perceptually even pixel art shading ramps in OKLCH. Control lightness steps, hue shift, and chroma to get smooth shadow-to-highlight transitions.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools/color-ramp-generator',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools/color-ramp-generator' },
  },
  openGraph: {
    title: 'Color Ramp Generator — OKLCH Pixel Art Shading',
    description: 'Build perceptually even pixel art shading ramps in OKLCH.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools/color-ramp-generator',
  },
};

export default function ColorRampGeneratorPage() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Tools', item: 'https://oklchpalette.ru/tools' },
      { '@type': 'ListItem', position: 3, name: 'Color Ramp Generator', item: 'https://oklchpalette.ru/tools/color-ramp-generator' },
    ],
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Tools', href: '/tools' },
        { label: 'Color Ramp Generator' },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        {/* Hero */}
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Color Ramp Generator
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Pick a base color and build a shading ramp with perceptually even lightness steps.
            Warm, cool, or neutral light presets — for pixel art and illustration.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">OKLCH even steps</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">3–9 colors</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">Hue shift control</span>
          </div>
        </section>

        {/* Tool */}
        <ColorRampGenerator locale="en" />

        {/* How to use */}
        <section className="space-y-4">
          <h2 className="text-lg font-mono font-bold text-white">How to use</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { title: 'Pick your base color', desc: 'This is the mid-tone of the ramp — the color you would use for the flat surface in neutral light.' },
              { title: 'Set step count', desc: 'Choose 3–9 steps. Pixel art typically uses 4–6 shades per surface.' },
              { title: 'Choose a light preset', desc: 'Warm light shifts shadows toward orange/amber. Cool light shifts them toward blue. Neutral keeps the hue.' },
              { title: 'Fine-tune hue shift', desc: 'The slider controls how many degrees the shadow hue drifts from the base hue. Common in classic pixel art.' },
            ].map(({ title, desc }) => (
              <div key={title} className="glass-panel rounded-xl border border-white/10 p-4 space-y-1">
                <h3 className="text-xs font-mono font-bold text-white">{title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Why OKLCH */}
        <section className="space-y-3">
          <h2 className="text-lg font-mono font-bold text-white">Why OKLCH for ramps?</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            HSL-based ramps often appear uneven because HSL&#39;s lightness is not perceptually uniform.
            OKLCH uses a perceptually linear lightness channel (L), so equal numeric steps produce
            equal perceived brightness jumps — which is critical for smooth sprite shading.
          </p>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            The chroma (C) channel independently controls colorfulness, so you can desaturate shadows
            and highlights without accidentally affecting their perceived brightness.
          </p>
        </section>
      </main>
    </ToolPageLayout>
  );
}
