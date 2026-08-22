import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { AsepriteConverter } from '@/components/tools/AsepriteConverter';

export const metadata: Metadata = {
  title: 'Aseprite Palette Converter (PAL, GPL, CSS, JSON) | OKLCH Pixel Palette',
  description: 'Convert color palettes to formats supported by Aseprite, GIMP, Krita, and web projects: JASC PAL (.pal), GIMP Palette (.gpl), CSS variables, Tailwind, and JSON tokens.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools/aseprite-palette-converter',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools/aseprite-palette-converter' },
  },
  openGraph: {
    title: 'Aseprite Palette Converter (PAL, GPL, CSS, JSON)',
    description: 'Convert color palettes to formats supported by Aseprite, GIMP, Krita, and web projects.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools/aseprite-palette-converter',
  },
};

export default function AsepritePaletteConverterPage() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Tools', item: 'https://oklchpalette.ru/tools' },
      { '@type': 'ListItem', position: 3, name: 'Aseprite Palette Converter', item: 'https://oklchpalette.ru/tools/aseprite-palette-converter' },
    ],
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Tools', href: '/tools' },
        { label: 'Aseprite Converter' },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Aseprite Palette Converter
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Convert color palettes between formats used by pixel art software (Aseprite, GIMP, GraphicsGale)
            and modern frontend development (CSS Variables, Tailwind Config, W3C Design Tokens).
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">JASC PAL (.pal)</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">GPL (.gpl)</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">CSS &amp; Tailwind</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">Design Tokens</span>
          </div>
        </section>

        <AsepriteConverter locale="en" />

        <section className="space-y-4">
          <h2 className="text-lg font-mono font-bold text-white">How to import into Aseprite</h2>
          <div className="glass-panel rounded-xl border border-white/10 p-5 space-y-3 text-xs text-gray-300 font-sans">
            <ol className="space-y-2 list-decimal list-inside">
              <li>Download the palette as <code className="font-mono text-purple-300">.pal</code> (JASC-PAL) or <code className="font-mono text-purple-300">.gpl</code> (GIMP Palette).</li>
              <li>Open <strong>Aseprite</strong>.</li>
              <li>In the Palette panel (left or top), click the <strong>Options menu</strong> (hamburger icon / hamburger button on palette bar).</li>
              <li>Select <strong>Load Palette</strong> and choose the downloaded file.</li>
            </ol>
          </div>
        </section>
      </main>
    </ToolPageLayout>
  );
}
