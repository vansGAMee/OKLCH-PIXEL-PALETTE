import type { Metadata } from 'next';
import Link from 'next/link';
import { Palette, Terminal, ChevronRight, ArrowRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'OKLCH for Pixel Art — Complete Guide | OKLCH Pixel Palette',
  description: 'Learn why OKLCH is the best color space for pixel art. Control lightness, chroma, and hue uniformly. Avoid muddy midtones forever.',
  alternates: {
    canonical: 'https://oklchpalette.ru/guides/oklch-for-pixel-art',
    languages: { 'ru': 'https://oklchpalette.ru/ru/guides/oklch-dlya-pikselnogo-arta' },
  },
  openGraph: {
    title: 'OKLCH for Pixel Art — Complete Guide',
    description: 'Control lightness perceptually. No more muddy midtones.',
    type: 'article',
  },
};

const EXAMPLES = [
  { hex: '#1e1b4b', l: 18, c: 12, h: 280, role: 'Deep Shadow' },
  { hex: '#5b21b6', l: 42, c: 22, h: 290, role: 'Dark Midtone' },
  { hex: '#a855f7', l: 65, c: 20, h: 295, role: 'Base' },
  { hex: '#d8b4fe', l: 82, c: 14, h: 298, role: 'Light Highlight' },
  { hex: '#f43f5e', l: 60, c: 22, h: 10, role: 'Accent' },
];

export default function OklchForPixelArtGuide() {
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
            Try Studio <ChevronRight className="w-3 h-3" />
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 space-y-10">
        {/* Breadcrumb */}
        <nav className="text-xs font-mono text-gray-500 flex items-center gap-1.5">
          <Link href="/" className="hover:text-purple-400 transition-colors">Home</Link>
          <span>/</span>
          <Link href="/guides" className="hover:text-purple-400 transition-colors">Guides</Link>
          <span>/</span>
          <span className="text-gray-300">OKLCH for Pixel Art</span>
        </nav>

        {/* Title */}
        <article className="space-y-8">
          <header className="space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
              Guide · 5 min read
            </div>
            <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
              OKLCH for Pixel Art
            </h1>
            <p className="text-base text-gray-300 font-sans leading-relaxed">
              Pixel art lives and dies by its palette. A 7-color palette with perceptually even lightness steps looks polished. A palette mixed in HSL with muddy midtones looks amateur — even with great sprites.
              OKLCH fixes this at the math level.
            </p>
          </header>

          {/* Section 1 */}
          <section className="space-y-4">
            <h2 className="text-xl font-mono font-bold text-white">What makes OKLCH different?</h2>
            <p className="text-sm text-gray-300 font-sans leading-relaxed">
              RGB and HSL were designed for screens, not for human perception. In HSL, a yellow at 60° hue and L=50% is <em>perceptually much brighter</em> than a blue at 240° with the same L. Your eye notices the difference — your code doesn&apos;t.
            </p>
            <p className="text-sm text-gray-300 font-sans leading-relaxed">
              OKLCH stands for <strong>OK Lightness Chroma Hue</strong>. The &quot;OK&quot; comes from the Björn Ottosson model that achieves near-perfect perceptual uniformity. When you step L from 0.4 to 0.5, the brightness change is the same regardless of hue.
            </p>
            <div className="glass-panel rounded-xl border border-white/10 p-4 font-mono text-xs space-y-1">
              <p className="text-gray-400">{`// HSL — same "lightness" value, very different perceived brightness`}</p>
              <p><span className="text-amber-400">hsl(60, 100%, 50%)</span> <span className="text-gray-500">&larr; blinding yellow</span></p>
              <p><span className="text-blue-400">hsl(240, 100%, 50%)</span> <span className="text-gray-500">&larr; dark navy</span></p>
              <br />
              <p className="text-gray-400">{`// OKLCH — L=0.65 means the same perceived brightness for both`}</p>
              <p><span className="text-amber-400">oklch(0.65 0.18 90)</span> <span className="text-gray-500">&larr; warm yellow</span></p>
              <p><span className="text-blue-400">oklch(0.65 0.18 250)</span> <span className="text-gray-500">&larr; cool blue, same lightness</span></p>
            </div>
          </section>

          {/* Live Example */}
          <section className="space-y-4">
            <h2 className="text-xl font-mono font-bold text-white">Pixel art palette example</h2>
            <p className="text-sm text-gray-300 font-sans">A 5-color OKLCH palette with predictable lightness steps. Each step is deliberate — no guessing.</p>
            <div className="glass-panel rounded-xl border border-white/10 overflow-hidden">
              <div className="flex">
                {EXAMPLES.map((e) => (
                  <div key={e.hex} className="flex-1 group relative">
                    <div className="h-20" style={{ backgroundColor: e.hex }} />
                    <div className="p-2 text-center space-y-0.5 bg-zinc-900/80">
                      <p className="text-[10px] font-mono text-gray-300 font-bold truncate">{e.role}</p>
                      <p className="text-[9px] font-mono text-purple-300">L:{e.l}%</p>
                      <p className="text-[9px] font-mono text-gray-500">C:{e.c}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <p className="text-xs font-mono text-gray-500">Lightness progression: 18% &rarr; 42% &rarr; 65% &rarr; 82%. Even steps. Clean shading.</p>
          </section>

          {/* Section 2 */}
          <section className="space-y-4">
            <h2 className="text-xl font-mono font-bold text-white">The three controls that matter</h2>
            <dl className="space-y-4">
              <div className="glass-panel rounded-xl border border-white/10 p-4 space-y-1">
                <dt className="text-sm font-mono font-bold text-purple-300">L — Lightness (0–1)</dt>
                <dd className="text-xs text-gray-300 font-sans">Controls how bright a color appears to the human eye. Step from 0.15 (shadow) to 0.85 (highlight) in even increments for clean shading. This is the most important axis for pixel art.</dd>
              </div>
              <div className="glass-panel rounded-xl border border-white/10 p-4 space-y-1">
                <dt className="text-sm font-mono font-bold text-purple-300">C — Chroma (0–0.37+)</dt>
                <dd className="text-xs text-gray-300 font-sans">Controls color saturation. Low C (&asymp;0.05) gives neutral grays. High C (&asymp;0.2+) gives vibrant hues. For pixel art, shadows typically use lower chroma than highlights — it matches how light works physically.</dd>
              </div>
              <div className="glass-panel rounded-xl border border-white/10 p-4 space-y-1">
                <dt className="text-sm font-mono font-bold text-purple-300">H — Hue (0–360°)</dt>
                <dd className="text-xs text-gray-300 font-sans">The color wheel direction. Shifting hue slightly toward warm (orange/yellow) as you increase L creates the &quot;fantasy lighting&quot; look popular in game palettes.</dd>
              </div>
            </dl>
          </section>

          {/* Section 3 */}
          <section className="space-y-4">
            <h2 className="text-xl font-mono font-bold text-white">Starting from text: AI palette generation</h2>
            <p className="text-sm text-gray-300 font-sans leading-relaxed">
              When creating sprites or environments, you often have a scene in mind (such as <em>&quot;deep sea horror&quot;</em>, <em>&quot;autumn forest&quot;</em>, or <em>&quot;неоновый киберпанк&quot;</em>) before picking exact HEX values.
            </p>
            <p className="text-sm text-gray-300 font-sans leading-relaxed">
              In the <Link href="/create" className="text-purple-400 hover:text-purple-300 underline underline-offset-2">OKLCH Studio</Link>, you can describe your scene in English or Russian. A local in-browser model turns the prompt into a starting OKLCH palette with balanced lightness steps that you can edit and export.
            </p>
          </section>

          {/* CTA */}
          <section className="glass-panel rounded-2xl border border-purple-500/30 p-8 text-center space-y-4">
            <h2 className="text-xl font-mono font-bold text-white">Try it in the Studio</h2>
            <p className="text-sm text-gray-300">Generate OKLCH palettes from text descriptions or color harmony rules with real-time lightness analysis.</p>
            <Link
              href="/create"
              className="inline-flex items-center gap-2 px-6 py-3 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/40"
            >
              Open Pixel Palette Studio <ArrowRight className="w-4 h-4" />
            </Link>
          </section>

          {/* See also */}
          <nav aria-label="Related guides" className="space-y-3">
            <h2 className="text-sm font-mono font-bold text-white">Related guides</h2>
            <div className="flex flex-col gap-2">
              <Link href="/guides/palette-file-formats" className="text-xs font-mono text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1">
                <ChevronRight className="w-3.5 h-3.5" /> Palette file formats: GPL, PAL, HEX, JSON
              </Link>
              <Link href="/guides/pixel-art-lightness" className="text-xs font-mono text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1">
                <ChevronRight className="w-3.5 h-3.5" /> Why lightness matters in pixel art
              </Link>
            </div>
          </nav>
        </article>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center">
        <Terminal className="w-3.5 h-3.5 text-purple-400 inline mr-1" />
        OKLCH Pixel Palette &copy; {new Date().getFullYear()} ·{' '}
        <Link href="/privacy" className="hover:text-gray-400 transition-colors">Privacy Policy</Link>
        {' · '}
        <Link href="/terms" className="hover:text-gray-400 transition-colors">Terms</Link>
      </footer>
    </div>
  );
}
