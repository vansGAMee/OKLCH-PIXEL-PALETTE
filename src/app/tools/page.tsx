import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ToolCard } from '@/components/tools/ToolCard';

export const metadata: Metadata = {
  title: 'Color Palette Tools | OKLCH Pixel Palette',
  description: 'Free browser-based tools for pixel art and illustration: AI palette generator, palette analyzer, color ramp builder, image palette extractor, and more.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools' },
  },
  openGraph: {
    title: 'Color Palette Tools | OKLCH Pixel Palette',
    description: 'Free browser-based tools for pixel art and illustration: AI palette generator, palette analyzer, color ramp builder, image palette extractor, and more.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools',
  },
};

const TOOLS = [
  {
    title: 'AI Color Palette Generator',
    description: 'Describe a scene, mood, or idea in English or Russian. The site maps your text to an OKLCH-based color palette locally in the browser.',
    href: '/tools/ai-color-palette-generator',
    badge: 'AI',
    available: true,
  },
  {
    title: 'Pixel Art Palette Generator',
    description: 'Generate perceptually balanced palettes using OKLCH color harmonies. Export to CSS, GPL, JASC PAL, HEX, and JSON.',
    href: '/tools/pixel-art-palette-generator',
    available: true,
  },
  {
    title: 'Palette Analyzer',
    description: 'Paste any palette and get a detailed diagnostic: lightness spread, near-duplicate detection, chroma balance, and an optional OKLCH fix.',
    href: '/tools/palette-analyzer',
    available: true,
  },
  {
    title: 'Color Ramp Generator',
    description: 'Build pixel-art shading ramps with perceptually even lightness steps. Control hue shift, chroma, and range with presets for warm, cool, and neutral light.',
    href: '/tools/color-ramp-generator',
    available: true,
  },
  {
    title: 'Image → Pixel Palette',
    description: 'Drop any image. Extract a reduced palette suitable for pixel art, with perceptual merging of near-duplicate colors.',
    href: '/tools/image-to-palette',
    available: true,
  },
  {
    title: 'Palette Compare',
    description: 'Supply two palettes side by side. Compare lightness, chroma, and hue distribution across both.',
    href: '/tools/palette-compare',
    available: true,
  },
  {
    title: 'Lospec Palette Import',
    description: 'Import a palette from a Lospec URL, view it in OKLCH, and open it in the generator for editing.',
    href: '/tools/lospec-palette-editor',
    available: true,
  },
  {
    title: 'Sprite Recolor',
    description: 'Upload a small pixel-art sprite and remap its colors to a target palette using perceptual color distance.',
    href: '/tools/sprite-recolor',
    available: true,
  },
  {
    title: 'Aseprite Palette Converter',
    description: 'Convert any palette to the formats used by Aseprite, GIMP, and other pixel-art software: GPL, JASC PAL, HEX, CSS, and JSON.',
    href: '/tools/aseprite-palette-converter',
    available: true,
  },
];

export default function ToolsPage() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Tools', item: 'https://oklchpalette.ru/tools' },
    ],
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[{ label: 'Tools' }]}
    >
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-12">
        {/* Hero */}
        <section className="space-y-4">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Palette Tools
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            A set of free browser-based tools for building, analyzing, and converting color palettes.
            All computation runs locally — no files are uploaded to a server.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">
              OKLCH color space
            </span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">
              Browser-local processing
            </span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">
              No account required
            </span>
          </div>
        </section>

        {/* Tool Grid */}
        <section className="space-y-4">
          <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">Available tools</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {TOOLS.map((tool) => (
              <ToolCard
                key={tool.href}
                title={tool.title}
                description={tool.description}
                href={tool.href}
                badge={tool.badge}
                available={tool.available}
              />
            ))}
          </div>
        </section>

        {/* Studio CTA */}
        <section className="glass-panel rounded-2xl border border-purple-500/20 p-8 text-center space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">Just need to create a palette?</h2>
          <p className="text-sm text-gray-400 font-sans">
            Open the generator directly to pick colors, choose harmonies, preview sprites, and export.
          </p>
          <a
            href="/create"
            className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/30 focus:outline-none focus:ring-2 focus:ring-purple-400"
          >
            Open Palette Studio
          </a>
        </section>
      </main>
    </ToolPageLayout>
  );
}
