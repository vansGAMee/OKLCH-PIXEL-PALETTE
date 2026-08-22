import type { Metadata } from 'next';
import Link from 'next/link';
import { Palette, Terminal, ChevronRight, ArrowRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Free OKLCH Pixel Art & AI Palette Generator | CSS & Sprite Export',
  description: 'Build balanced 2–9 color pixel-art palettes in OKLCH using manual harmonies or local AI text descriptions. Preview sprites, analyze lightness and export CSS, PAL, GPL, PNG.',
  alternates: { canonical: 'https://oklchpalette.ru/tools/pixel-art-palette-generator' },
  openGraph: {
    title: 'Free OKLCH Pixel Art & AI Palette Generator | CSS & Sprite Export',
    description: 'Build balanced pixel-art palettes using local AI or manual OKLCH harmonies, preview sprites, and export CSS or artist palette files.',
    type: 'website',
  },
};

const FEATURES = [
  { title: 'AI Text-to-Palette', desc: 'Describe scenes or moods in natural language (EN & RU) to generate calibrated OKLCH starting palettes with local in-browser AI.' },
  { title: 'Perceptual Lightness', desc: 'OKLCH L-channel gives perfectly even light-to-dark steps — critical for shading in pixel art.' },
  { title: '6 Harmony Modes', desc: 'Complementary, Split-Complementary, Analogous, Triadic, Tetradic, Monochromatic.' },
  { title: 'sRGB Gamut Guard', desc: 'Every generated color is clamped to sRGB with Delta E verification — no out-of-gamut surprises.' },
  { title: 'Lightness Ladder', desc: 'Visual bar chart sorted by L-value so you can see lightness distribution instantly.' },
  { title: 'Live Pixel Preview', desc: 'See your palette on a potion, gem, shield, and hero sprite before exporting.' },
  { title: 'CSS & Artist Export', desc: 'CSS variables with HEX fallbacks, GPL (GIMP), JASC PAL (Aseprite), HEX, JSON, and branded PNG.' },
];

export default function PixelArtPaletteGeneratorPage() {
  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white">
      <header className="sticky top-0 z-40 border-b border-white/10 glass-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
              <Palette className="w-4 h-4" />
            </div>
            <span className="text-sm font-mono font-black text-white hidden sm:block">OKLCH PIXEL PALETTE</span>
          </Link>
          <Link href="/create" className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all">
            Open Generator <ChevronRight className="w-3 h-3" />
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-16 flex-1 w-full space-y-16">
        {/* Hero */}
        <section className="text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
            Free · No Account Required
          </div>
          <h1 className="text-4xl sm:text-5xl font-mono font-extrabold text-white leading-tight">
            Pixel Art Palette<br />Generator
          </h1>
          <p className="text-lg text-gray-300 font-sans max-w-2xl mx-auto">
            The only free palette generator built on <strong className="text-white">OKLCH</strong> — the perceptually uniform color space that gives pixel artists control over lightness without the HSL mudtone problem.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <Link
              href="/create"
              className="px-8 py-3.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/40 flex items-center gap-2"
            >
              Generate Palette Now <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>

        {/* Static Palette Demo */}
        <section aria-label="Palette example">
          <div className="flex rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
            {[
              '#1e1b4b', '#311b92', '#5b21b6', '#7c3aed', '#a855f7', '#c084fc', '#f43f5e',
            ].map((hex, i) => (
              <div key={i} className="flex-1 flex flex-col">
                <div className="h-24" style={{ backgroundColor: hex }} />
                <div className="bg-zinc-900/90 py-1.5 text-center">
                  <span className="text-[9px] font-mono text-gray-400">{hex}</span>
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs font-mono text-gray-500 text-center mt-2">7-color OKLCH split-complementary palette — generated in one click</p>
        </section>

        {/* Features Grid */}
        <section className="space-y-6">
          <h2 className="text-2xl font-mono font-bold text-white">What makes it different</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
                <h3 className="text-sm font-mono font-bold text-white">{f.title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* FAQ */}
        <section className="space-y-4">
          <h2 className="text-2xl font-mono font-bold text-white">FAQ</h2>
          <dl className="space-y-4">
            <div className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
              <dt className="text-sm font-mono font-bold text-white">Is it free?</dt>
              <dd className="text-xs text-gray-300 font-sans">Yes, 100% free. No account required to generate and export palettes.</dd>
            </div>
            <div className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
              <dt className="text-sm font-mono font-bold text-white">How many colors can I generate?</dt>
              <dd className="text-xs text-gray-300 font-sans">2 to 9 colors per palette. Optimized for pixel art constraints.</dd>
            </div>
            <div className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
              <dt className="text-sm font-mono font-bold text-white">Can I import existing palettes?</dt>
              <dd className="text-xs text-gray-300 font-sans">Yes — GPL, JASC PAL, HEX lists, and the site&apos;s own JSON format are all supported on import.</dd>
            </div>
            <div className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
              <dt className="text-sm font-mono font-bold text-white">How does AI palette generation work?</dt>
              <dd className="text-xs text-gray-300 font-sans">Type any scene, mood, or environment description (such as &ldquo;autumn forest&rdquo; or &ldquo;neon cyber rain&rdquo;). The local in-browser AI model maps the text to an OKLCH base color and harmony without calling external cloud APIs.</dd>
            </div>
            <div className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
              <dt className="text-sm font-mono font-bold text-white">What software accepts the export files?</dt>
              <dd className="text-xs text-gray-300 font-sans">CSS export works directly in web projects with HEX fallbacks and OKLCH overrides. GPL works in GIMP, Inkscape, and Krita; JASC PAL works in Aseprite, GraphicsGale, and GrafX2.</dd>
            </div>
          </dl>
        </section>

        {/* CTA */}
        <section className="glass-panel rounded-2xl border border-purple-500/30 p-10 text-center space-y-5">
          <h2 className="text-2xl font-mono font-bold text-white">Ready to build your palette?</h2>
          <Link
            href="/create"
            className="inline-flex items-center gap-2 px-8 py-3.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/40"
          >
            Open Pixel Art Palette Studio <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center flex flex-col sm:flex-row items-center justify-center gap-3">
        <div className="flex items-center gap-1">
          <Terminal className="w-3.5 h-3.5 text-purple-400 inline" />
          <span>OKLCH Pixel Palette &copy; {new Date().getFullYear()}</span>
        </div>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link
          href="/privacy"
          className="text-gray-400 hover:text-white transition-colors underline-offset-4 hover:underline"
        >
          Privacy Policy
        </Link>
      </footer>
    </div>
  );
}
