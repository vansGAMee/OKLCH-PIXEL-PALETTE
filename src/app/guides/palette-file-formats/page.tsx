import type { Metadata } from 'next';
import Link from 'next/link';
import { Palette, Terminal, ChevronRight, ArrowRight, Download } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Pixel Art Palette File Formats: GPL, PAL, HEX, JSON | OKLCH Pixel Palette',
  description: 'Complete guide to pixel art palette file formats — GIMP GPL, JASC PAL, HEX list, JSON. What each format is for and which software reads them.',
  alternates: {
    canonical: 'https://oklchpalette.ru/guides/palette-file-formats',
  },
};

const FORMATS = [
  {
    name: 'GIMP Palette (.gpl)',
    badge: 'Universal',
    badgeColor: 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10',
    apps: ['GIMP', 'Inkscape', 'Aseprite (import)', 'Krita'],
    desc: 'The most universally supported pixel art palette format. A plain text file with "GIMP Palette" header, followed by RGB values and optional color names.',
    sample: `GIMP Palette
Name: My Palette
Columns: 4
#
155  89 182 purple
 52 152 219 blue
231  76  60 red`,
  },
  {
    name: 'JASC PAL (.pal)',
    badge: 'Paint Shop Pro',
    badgeColor: 'text-blue-400 border-blue-500/20 bg-blue-500/10',
    apps: ['Paint Shop Pro', 'Aseprite', 'GraphicsGale', 'GrafX2'],
    desc: 'The native palette format for Paint Shop Pro and many retro-era pixel art tools. Supported by most dedicated pixel art apps.',
    sample: `JASC-PAL
0100
4
155 89 182
52 152 219
231 76 60
52 73 94`,
  },
  {
    name: 'HEX List (.txt)',
    badge: 'Web / Dev',
    badgeColor: 'text-purple-400 border-purple-500/20 bg-purple-500/10',
    apps: ['Lospec', 'Coolors', 'Web code', 'Figma', 'CSS'],
    desc: 'One HEX color per line, with or without the # prefix. Easiest format to paste into CSS, JavaScript, or any web tool.',
    sample: `#9b59b6
#3498db
#e74c3c
#34495e`,
  },
  {
    name: 'JSON (.json)',
    badge: 'OKLCH Native',
    badgeColor: 'text-amber-400 border-amber-500/20 bg-amber-500/10',
    apps: ['OKLCH Pixel Palette', 'Custom apps', 'JavaScript'],
    desc: 'Our own export format — includes full OKLCH values (L, C, H), color roles, harmony mode, and seed. Preserves all the perceptual data. Use this for round-tripping palettes in the Studio.',
    sample: `{
  "name": "My Palette",
  "harmony": "analogous",
  "colors": [
    { "role": "shadow", "hex": "#1e1b4b",
      "oklch": { "l": 0.18, "c": 0.12, "h": 280 } }
  ]
}`,
  },
];

export default function PaletteFileFormatsGuide() {
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
        <nav className="text-xs font-mono text-gray-500 flex items-center gap-1.5">
          <Link href="/" className="hover:text-purple-400 transition-colors">Home</Link>
          <span>/</span>
          <Link href="/guides" className="hover:text-purple-400 transition-colors">Guides</Link>
          <span>/</span>
          <span className="text-gray-300">Palette File Formats</span>
        </nav>

        <article className="space-y-8">
          <header className="space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
              Guide · 4 min read
            </div>
            <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
              Palette File Formats
            </h1>
            <p className="text-base text-gray-300 font-sans leading-relaxed">
              The right palette format depends on your workflow. GIMP GPL works everywhere. JASC PAL is native to pixel art apps. HEX is for web. JSON preserves OKLCH data. Here&apos;s what you need to know.
            </p>
          </header>

          {/* Format Comparison Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-gray-400">
                  <th className="text-left py-2 pr-4">Format</th>
                  <th className="text-left py-2 pr-4">Extension</th>
                  <th className="text-left py-2 pr-4">Color Data</th>
                  <th className="text-left py-2">Best For</th>
                </tr>
              </thead>
              <tbody className="text-gray-300">
                <tr className="border-b border-white/5">
                  <td className="py-2 pr-4 text-white font-bold">GIMP GPL</td>
                  <td className="py-2 pr-4">.gpl</td>
                  <td className="py-2 pr-4">RGB 0–255 + name</td>
                  <td className="py-2">Universal pixel art</td>
                </tr>
                <tr className="border-b border-white/5">
                  <td className="py-2 pr-4 text-white font-bold">JASC PAL</td>
                  <td className="py-2 pr-4">.pal</td>
                  <td className="py-2 pr-4">RGB 0–255</td>
                  <td className="py-2">PSP, Aseprite, retro tools</td>
                </tr>
                <tr className="border-b border-white/5">
                  <td className="py-2 pr-4 text-white font-bold">HEX List</td>
                  <td className="py-2 pr-4">.txt</td>
                  <td className="py-2 pr-4">6-digit hex</td>
                  <td className="py-2">Web, CSS, Lospec, Figma</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 text-white font-bold">JSON</td>
                  <td className="py-2 pr-4">.json</td>
                  <td className="py-2 pr-4">HEX + OKLCH + roles</td>
                  <td className="py-2">OKLCH Studio, custom code</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Format Details */}
          {FORMATS.map((f) => (
            <section key={f.name} className="space-y-4">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-mono font-bold text-white">{f.name}</h2>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${f.badgeColor}`}>{f.badge}</span>
              </div>
              <p className="text-sm text-gray-300 font-sans">{f.desc}</p>
              <div className="text-xs font-mono text-gray-400">
                <span className="font-bold text-gray-300">Supported in: </span>
                {f.apps.join(', ')}
              </div>
              <pre className="bg-zinc-900 border border-white/10 rounded-xl p-4 text-xs font-mono text-gray-300 overflow-x-auto">
                {f.sample}
              </pre>
            </section>
          ))}

          {/* CTA */}
          <section className="glass-panel rounded-2xl border border-purple-500/30 p-8 text-center space-y-4">
            <Download className="w-8 h-8 text-purple-400 mx-auto" />
            <h2 className="text-xl font-mono font-bold text-white">Export in all formats, free</h2>
            <p className="text-sm text-gray-300">OKLCH Pixel Palette exports GPL, PAL, HEX, JSON, and PNG in one click. No account required.</p>
            <Link
              href="/create"
              className="inline-flex items-center gap-2 px-6 py-3 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all"
            >
              Open Studio <ArrowRight className="w-4 h-4" />
            </Link>
          </section>
        </article>
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
