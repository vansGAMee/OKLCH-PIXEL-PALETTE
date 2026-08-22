import type { Metadata } from 'next';
import Link from 'next/link';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ArrowRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'OKLCH vs HSL: Why Modern Pixel Art Needs Perceptual Color | OKLCH Pixel Palette',
  description: 'An engineering comparison between HSL and OKLCH color spaces. Discover why HSL lightness causes muddy shading ramps and how OKLCH achieves true perceptual uniformity.',
  alternates: {
    canonical: 'https://oklchpalette.ru/research/oklch-vs-hsl',
    languages: { 'ru': 'https://oklchpalette.ru/ru/research/oklch-vs-hsl' },
  },
  openGraph: {
    title: 'OKLCH vs HSL: Why Modern Pixel Art Needs Perceptual Color',
    description: 'An engineering comparison between HSL and OKLCH color spaces for pixel art and digital design.',
    type: 'article',
    url: 'https://oklchpalette.ru/research/oklch-vs-hsl',
  },
};

export default function OklchVsHslPage() {
  const articleSchema = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: 'OKLCH vs HSL: Why Modern Pixel Art Needs Perceptual Color',
    description: 'An engineering comparison between HSL and OKLCH color spaces.',
    author: { '@type': 'Organization', name: 'OKLCH Pixel Palette' },
    publisher: { '@type': 'Organization', name: 'OKLCH Pixel Palette', url: 'https://oklchpalette.ru' },
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Research' },
        { label: 'OKLCH vs HSL' },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(articleSchema) }} />

      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-12">
        {/* Header */}
        <header className="space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
            Color Science &amp; Engineering
          </div>
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            OKLCH vs HSL:<br />Why Pixel Art Needs Perceptual Color
          </h1>
          <p className="text-base text-gray-300 font-sans leading-relaxed">
            For decades, digital art software relied on HSL and HSV for color pickers and ramp generation.
            While mathematically simple, HSL fails to account for human visual perception, creating
            unbalanced shading and inconsistent contrast.
          </p>
        </header>

        {/* The Core Problem: False Lightness */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">1. The Flaw in HSL Lightness</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            In HSL, pure yellow (<code className="font-mono text-purple-300">#FFFF00</code>) and pure blue (<code className="font-mono text-purple-300">#0000FF</code>)
            both have a lightness of exactly <strong className="text-white">L = 50%</strong>.
          </p>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            However, human eyes perceive yellow as drastically brighter than blue because our green and red cone receptors
            have peak sensitivity in that wavelength range. In OKLCH (developed by Björn Ottosson in 2020), this is corrected:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div className="glass-panel rounded-xl p-4 border border-white/10 space-y-2">
              <div className="h-12 rounded-lg bg-[#ffff00] flex items-center justify-center font-mono text-xs font-bold text-black shadow">
                #FFFF00 (Pure Yellow)
              </div>
              <div className="text-xs font-mono text-gray-400 space-y-1">
                <div>HSL Lightness: <strong className="text-white">50%</strong></div>
                <div>OKLCH Lightness: <strong className="text-yellow-400">96.8%</strong> (perceived)</div>
              </div>
            </div>

            <div className="glass-panel rounded-xl p-4 border border-white/10 space-y-2">
              <div className="h-12 rounded-lg bg-[#0000ff] flex items-center justify-center font-mono text-xs font-bold text-white shadow">
                #0000FF (Pure Blue)
              </div>
              <div className="text-xs font-mono text-gray-400 space-y-1">
                <div>HSL Lightness: <strong className="text-white">50%</strong></div>
                <div>OKLCH Lightness: <strong className="text-blue-400">45.2%</strong> (perceived)</div>
              </div>
            </div>
          </div>
        </section>

        {/* Shading Ramps in Pixel Art */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">2. Shading Ramps &amp; Muddy Transitions</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            When creating a color ramp in HSL by linearly stepping the Lightness channel from 20% to 80%,
            different hues produce wildly different visual contrast jumps. A blue ramp will look crushed and dark,
            while a yellow ramp will blow out into near-white instantly.
          </p>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            OKLCH solves this by modeling lightness (<code className="font-mono text-purple-300">L</code>) on a perceptually uniform curve.
            A step of +10% in OKLCH feels like the exact same brightness step whether you are working in teal, violet, or amber.
          </p>
        </section>

        {/* Independent Chroma vs Saturation */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">3. Chroma vs HSL Saturation</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            HSL saturation is normalized relative to lightness (100% saturation at L=50% is vivid, but at L=95% it is nearly white).
            In OKLCH, Chroma (<code className="font-mono text-purple-300">C</code>) is an absolute, physically grounded measurement of color purity.
          </p>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            This means you can adjust lightness without unintentionally changing the vividness of your palette anchors.
          </p>
        </section>

        {/* Gamut Fitting */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">4. Gamut Fitting</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            Because OKLCH is unbounded, some mathematical coordinates fall outside the standard sRGB display gamut.
            Our engine uses binary search chroma reduction to clip colors precisely to the sRGB boundary
            while strictly preserving hue and perceptual lightness.
          </p>
        </section>

        {/* CTA */}
        <section className="glass-panel rounded-2xl border border-purple-500/30 p-8 text-center space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">Try it in action</h2>
          <p className="text-sm text-gray-400 font-sans">
            Build your next pixel art palette with real OKLCH perceptual harmony.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link
              href="/tools/color-ramp-generator"
              className="px-6 py-2.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-md flex items-center gap-1.5"
            >
              Color Ramp Generator <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <Link
              href="/create"
              className="px-6 py-2.5 text-xs font-mono text-purple-300 hover:text-white rounded-xl border border-purple-500/30 hover:border-purple-500/60 transition-all"
            >
              Open Studio
            </Link>
          </div>
        </section>
      </article>
    </ToolPageLayout>
  );
}
