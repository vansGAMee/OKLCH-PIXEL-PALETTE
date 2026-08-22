import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { CURATED_PALETTES, getCuratedPalette } from '@/lib/tools/curatedPalettes';
import { CuratedPaletteDetail } from '@/components/palette/CuratedPaletteDetail';

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return CURATED_PALETTES.map(p => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const palette = getCuratedPalette(slug);
  if (!palette) return { title: 'Palette Not Found' };

  return {
    title: `${palette.title} — Pixel Art Palette | OKLCH Pixel Palette`,
    description: `${palette.description} Export to Aseprite, GIMP, CSS, or customize in Studio.`,
    alternates: {
      canonical: `https://oklchpalette.ru/palettes/${slug}`,
      languages: { 'ru': `https://oklchpalette.ru/ru/palettes/${slug}` },
    },
    openGraph: {
      title: `${palette.title} — Pixel Art Palette`,
      description: palette.description,
      type: 'website',
      url: `https://oklchpalette.ru/palettes/${slug}`,
    },
  };
}

export default async function CuratedPaletteDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const palette = getCuratedPalette(slug);
  if (!palette) notFound();

  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Curated Palettes', item: 'https://oklchpalette.ru/palettes' },
      { '@type': 'ListItem', position: 3, name: palette.title, item: `https://oklchpalette.ru/palettes/${slug}` },
    ],
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Curated Palettes', href: '/palettes' },
        { label: palette.title },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full">
        <CuratedPaletteDetail palette={palette} locale="en" />
      </main>
    </ToolPageLayout>
  );
}
