import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { LospecImporter } from '@/components/tools/LospecImporter';

export const metadata: Metadata = {
  title: 'Lospec Palette Import — View in OKLCH | OKLCH Pixel Palette',
  description: 'Import any Lospec palette by URL or slug, view it in OKLCH color space, and open it in the palette generator for editing. Unofficial import tool.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools/lospec-palette-editor',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools/lospec-palette-editor' },
  },
  openGraph: {
    title: 'Lospec Palette Import — View in OKLCH',
    description: 'Import any Lospec palette by URL and view it in OKLCH. Unofficial tool.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools/lospec-palette-editor',
  },
};

export default function LospecPaletteEditorPage() {
  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Tools', href: '/tools' },
        { label: 'Lospec Import' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Lospec Palette Import
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Enter a Lospec palette URL or slug to view the palette in OKLCH and open it
            in the generator. The import uses the public Lospec JSON API.
          </p>
          <div className="text-xs font-mono text-gray-600">
            Unofficial tool. Not affiliated with Lospec. Palettes belong to their authors.
          </div>
        </section>

        <LospecImporter locale="en" />

        <section className="space-y-3">
          <h2 className="text-base font-mono font-bold text-white">How it works</h2>
          <ul className="space-y-2 text-xs text-gray-400 font-sans">
            <li>• Enter a Lospec palette URL (<code className="font-mono text-gray-300">https://lospec.com/palette-list/db16</code>) or just the slug (<code className="font-mono text-gray-300">db16</code>).</li>
            <li>• The site fetches the palette data from Lospec&#39;s public JSON API via a server proxy (to avoid CORS).</li>
            <li>• Colors are converted to OKLCH for display and can be opened in the generator or exported.</li>
            <li>• The original palette page is always linked for attribution.</li>
          </ul>
        </section>
      </main>
    </ToolPageLayout>
  );
}
