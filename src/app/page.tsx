import type { Metadata } from 'next';
import Link from 'next/link';
import { Palette, Sparkles, Sliders, Eye, BarChart2, ShieldCheck, Download, ChevronRight, Terminal } from 'lucide-react';

export const metadata: Metadata = {
  title: 'OKLCH Palette Generator for Pixel Art, Games and UI',
  description:
    'Create balanced OKLCH color palettes with 2–9 colors, pixel art previews, perceptual lightness analysis and polished PNG export.',
  alternates: {
    canonical: 'https://oklchpalette.ru/',
  },
  openGraph: {
    title: 'OKLCH Palette Generator for Pixel Art, Games and UI',
    description:
      'Create balanced OKLCH color palettes with 2–9 colors, pixel art previews, perceptual lightness analysis and polished PNG export.',
    url: 'https://oklchpalette.ru/',
    siteName: 'OKLCH Pixel Palette',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'OKLCH Palette Generator for Pixel Art, Games and UI',
    description:
      'Create balanced OKLCH color palettes with 2–9 colors, pixel art previews, perceptual lightness analysis and polished PNG export.',
  },
};

export default function HomePage() {
  const currentYear = new Date().getFullYear();

  const websiteJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'OKLCH Pixel Palette',
    alternateName: 'OKLCH Palette',
    url: 'https://oklchpalette.ru/',
  };

  const softwareJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'OKLCH Pixel Palette',
    url: 'https://oklchpalette.ru/',
    applicationCategory: 'DesignApplication',
    operatingSystem: 'Any',
    description:
      'Create balanced OKLCH color palettes with 2–9 colors, pixel art previews, perceptual lightness analysis and polished PNG export.',
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
  };

  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col justify-between selection:bg-purple-600 selection:text-white">
      {/* Structured Data (JSON-LD) */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
      />

      {/* Navigation Header */}
      <header className="sticky top-0 z-50 border-b border-white/10 glass-panel backdrop-blur-md bg-zinc-950/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-3 group focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg p-1"
          >
            <div className="w-9 h-9 rounded-xl bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 shadow-lg shadow-purple-900/20 group-hover:scale-105 transition-transform">
              <Palette className="w-5 h-5" />
            </div>
            <span className="text-sm sm:text-base font-mono font-black tracking-tight text-white">
              OKLCH PIXEL PALETTE
            </span>
          </Link>

          <nav aria-label="Main Navigation" className="flex items-center gap-4 sm:gap-6">
            <a
              href="#features"
              className="text-xs font-mono text-gray-300 hover:text-white transition-colors hidden sm:block focus:outline-none focus:ring-2 focus:ring-purple-500 rounded px-2 py-1"
            >
              Features
            </a>
            <a
              href="#why-oklch"
              className="text-xs font-mono text-gray-300 hover:text-white transition-colors hidden sm:block focus:outline-none focus:ring-2 focus:ring-purple-500 rounded px-2 py-1"
            >
              Why OKLCH
            </a>
            <Link
              href="/create"
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all shadow-md shadow-purple-900/30 focus:outline-none focus:ring-2 focus:ring-purple-400"
            >
              <span>Open Studio</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex-1 w-full space-y-20">
        {/* Hero Section */}
        <section aria-labelledby="hero-heading" className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              <span>Perceptual Color Engine for Creators</span>
            </div>

            <h1
              id="hero-heading"
              className="text-3xl sm:text-4xl lg:text-5xl font-mono font-extrabold tracking-tight text-white leading-tight"
            >
              Build better color palettes with OKLCH
            </h1>

            <p className="text-sm sm:text-base text-gray-300 font-sans leading-relaxed max-w-2xl">
              Create balanced palettes for pixel art, games and interfaces. Preview every color, inspect perceptual lightness and export a polished palette card.
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-2">
              <Link
                href="/create"
                className="px-6 py-3 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/40 flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-purple-400"
              >
                <span>Create a palette</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
              <a
                href="#features"
                className="px-6 py-3 text-sm font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-xl transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                Explore features
              </a>
            </div>
          </div>

          {/* Hero Static Showcase Card Grid (HTML/CSS, accessible to crawlers) */}
          <div className="lg:col-span-5">
            <div className="glass-panel p-6 rounded-2xl border border-white/10 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <span className="text-xs font-mono font-bold tracking-widest text-purple-400 uppercase">
                  OKLCH 7-Color Ramp Showcase
                </span>
                <span className="text-[10px] font-mono text-gray-400">sRGB Guarded</span>
              </div>

              {/* Static Palette Swatches Grid */}
              <div className="grid grid-cols-7 gap-2">
                {[
                  { hex: '#1e1b4b', role: 'SHADOW', l: '0.18' },
                  { hex: '#311b92', role: 'DARK', l: '0.30' },
                  { hex: '#5b21b6', role: 'BASE', l: '0.45' },
                  { hex: '#7c3aed', role: 'MID', l: '0.58' },
                  { hex: '#a855f7', role: 'HIGHLIGHT', l: '0.70' },
                  { hex: '#c084fc', role: 'LIGHT', l: '0.82' },
                  { hex: '#f43f5e', role: 'ACCENT', l: '0.65' },
                ].map((item, idx) => (
                  <div key={idx} className="flex flex-col gap-1.5">
                    <div
                      className="h-24 rounded-lg border border-white/15 shadow-inner"
                      style={{ backgroundColor: item.hex }}
                    />
                    <span className="text-[9px] font-mono text-gray-400 text-center font-bold">
                      {item.role}
                    </span>
                    <span className="text-[9px] font-mono text-purple-300 text-center">
                      {item.hex}
                    </span>
                  </div>
                ))}
              </div>

              <div className="pt-2 flex items-center justify-between text-[11px] font-mono text-gray-400">
                <span>Split Complementary Harmony</span>
                <span className="text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> Delta E &ge; 0.025
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" aria-labelledby="features-heading" className="space-y-8">
          <div className="space-y-2">
            <h2 id="features-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
              Features
            </h2>
            <p className="text-sm text-gray-400 font-sans">
              Everything you need to design perceptually uniform color schemes for digital media.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Sliders className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">2–9 color palettes</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Generate custom color ramps from 2 to 9 slots with automatic lightness scale balancing.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Palette className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">Perceptual OKLCH controls</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Harness uniform lightness perception to create predictable color relationships and smooth ramps.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Eye className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">Pixel art previews</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Instantly test color palettes on classic game sprites (potion, gem, shield, hero) and full mosaic grids.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <BarChart2 className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">Lightness analysis</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Inspect perceptual lightness distribution on an interactive ladder graph sorted from dark to light.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">sRGB gamut protection</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Guard against out-of-bounds screen colors using automated gamut fitting and Delta E deduplication.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Download className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">Polished PNG export</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Export crisp PNG palette cards complete with role labels, HEX codes, and OKLCH parameters.
              </p>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section aria-labelledby="how-it-works-heading" className="space-y-8">
          <div className="space-y-2">
            <h2 id="how-it-works-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
              How it works
            </h2>
            <p className="text-sm text-gray-400 font-sans">
              Three simple steps to craft balanced color palettes.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3 relative">
              <span className="text-xs font-mono font-bold text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-md inline-block">
                Step 1
              </span>
              <h3 className="text-base font-mono font-bold text-white">Choose a base color</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Pick any starting HEX color seed using the visual color picker or manual text input.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3 relative">
              <span className="text-xs font-mono font-bold text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-md inline-block">
                Step 2
              </span>
              <h3 className="text-base font-mono font-bold text-white">Select a harmony and size</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Choose complementary, split-complementary, or analogous rules with 2 to 9 color slots.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3 relative">
              <span className="text-xs font-mono font-bold text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-md inline-block">
                Step 3
              </span>
              <h3 className="text-base font-mono font-bold text-white">Preview, inspect and export</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Verify lightness steps on the ladder chart, test pixel art scenes, and download your PNG card.
              </p>
            </div>
          </div>
        </section>

        {/* Why OKLCH Section */}
        <section id="why-oklch" aria-labelledby="why-oklch-heading" className="glass-panel p-8 rounded-2xl border border-white/10 space-y-6">
          <div className="space-y-2 border-b border-white/10 pb-4">
            <h2 id="why-oklch-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
              Why OKLCH?
            </h2>
            <p className="text-xs font-mono text-purple-300">
              Perceptually uniform color theory for modern digital design
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed">
            <div className="space-y-3">
              <h3 className="font-mono font-bold text-white text-base">Perceptual Lightness vs. RGB/HSL</h3>
              <p>
                Traditional RGB and HSL color models do not reflect how human eyes perceive brightness. In HSL, yellow and blue at 50% lightness appear completely different in brightness. OKLCH explicitly separates perceived lightness (L) from chroma (C) and hue (H).
              </p>
              <p>
                When you modify hue in OKLCH, perceived brightness remains predictable. This allows game artists and UI designers to build harmonious color ramps without unintended contrast drops.
              </p>
            </div>

            <div className="space-y-3">
              <h3 className="font-mono font-bold text-white text-base">Lightness Ladder &amp; Gamut Protection</h3>
              <p>
                The Lightness Ladder analyzes palette entries along a single lightness scale from 0 (darkest) to 1 (lightest). It reveals colors that are too close in value before you start drawing.
              </p>
              <p>
                Because OKLCH can represent colors beyond standard monitor capabilities, our sRGB gamut protection algorithm automatically fits out-of-bounds values into sRGB display limits while preserving pairwise distinction.
              </p>
            </div>
          </div>
        </section>

        {/* Target Audience Section */}
        <section aria-labelledby="audience-heading" className="space-y-6">
          <h2 id="audience-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
            Built for creators
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="glass-panel p-5 rounded-xl border border-white/10 space-y-2">
              <h3 className="font-mono font-bold text-white text-sm">Pixel artists</h3>
              <p className="text-xs text-gray-400">
                Craft cohesive retro ramps and sprite palettes with uniform lightness steps.
              </p>
            </div>

            <div className="glass-panel p-5 rounded-xl border border-white/10 space-y-2">
              <h3 className="font-mono font-bold text-white text-sm">Game developers</h3>
              <p className="text-xs text-gray-400">
                Design distinct character, environment, and item color schemes for 2D/3D games.
              </p>
            </div>

            <div className="glass-panel p-5 rounded-xl border border-white/10 space-y-2">
              <h3 className="font-mono font-bold text-white text-sm">UI designers</h3>
              <p className="text-xs text-gray-400">
                Create accessible interface color systems with calibrated contrast levels.
              </p>
            </div>

            <div className="glass-panel p-5 rounded-xl border border-white/10 space-y-2">
              <h3 className="font-mono font-bold text-white text-sm">Frontend developers</h3>
              <p className="text-xs text-gray-400">
                Export clear HEX strings and OKLCH color parameters directly to CSS.
              </p>
            </div>
          </div>
        </section>

        {/* FAQ Section (Pure HTML details/summary, server-rendered in DOM) */}
        <section aria-labelledby="faq-heading" className="space-y-6">
          <div className="space-y-2">
            <h2 id="faq-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
              Frequently Asked Questions
            </h2>
            <p className="text-sm text-gray-400 font-sans">
              Learn more about OKLCH color theory and usage.
            </p>
          </div>

          <div className="space-y-4">
            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>What is OKLCH?</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                OKLCH is a perceptually uniform color space designed to align color values with human visual perception. Unlike HSL or RGB, equal changes in lightness values result in equal changes in perceived brightness.
              </div>
            </details>

            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>Is the palette generator free?</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                Yes, the OKLCH Pixel Palette Studio is 100% free to use directly in your browser without registration, subscriptions, or hidden limits.
              </div>
            </details>

            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>Can I use the palettes commercially?</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                Absolutely. All generated color palettes and exported PNG cards can be freely used in personal, open-source, and commercial games, artwork, or web projects.
              </div>
            </details>

            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>Why does the tool protect the sRGB gamut?</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                Monitors display colors within standard sRGB boundaries. Gamut protection automatically clamps out-of-bounds OKLCH values so exported colors match what you see on screen without clipping artifacts.
              </div>
            </details>
          </div>
        </section>

        {/* CTA Banner */}
        <section aria-label="Call to Action" className="glass-panel p-8 sm:p-12 rounded-2xl border border-purple-500/30 text-center space-y-6 relative overflow-hidden">
          <div className="max-w-2xl mx-auto space-y-3 relative z-10">
            <h2 className="text-2xl sm:text-3xl font-mono font-extrabold text-white">
              Ready to craft your pixel palette?
            </h2>
            <p className="text-xs sm:text-sm text-gray-300 font-sans">
              Launch the studio editor to build, test, and export your OKLCH color schemes.
            </p>
          </div>

          <div className="relative z-10">
            <Link
              href="/create"
              className="inline-flex items-center gap-2 px-8 py-3.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/50 focus:outline-none focus:ring-2 focus:ring-purple-400"
            >
              <span>Open Palette Studio</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 bg-zinc-950 py-8 text-xs font-mono text-gray-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-purple-400" />
              <span className="font-bold text-white">OKLCH Pixel Palette</span>
            </div>
            <span className="hidden sm:inline text-gray-600">|</span>
            <span className="text-gray-400">Perceptual color engine for games &amp; UI</span>
          </div>

          <div className="flex items-center gap-6">
            <Link href="/create" className="hover:text-white transition-colors">
              Studio
            </Link>
            <a href="https://oklchpalette.ru" className="hover:text-white transition-colors">
              https://oklchpalette.ru
            </a>
            <span>&copy; {currentYear}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
