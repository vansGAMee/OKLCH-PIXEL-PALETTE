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
  if (!palette) return { title: 'Палитра не найдена' };

  return {
    title: `${palette.titleRu} — Пиксель-арт палитра | OKLCH Pixel Palette`,
    description: `${palette.descriptionRu} Экспорт в Aseprite, GIMP, CSS или кастомизация в Студии.`,
    alternates: {
      canonical: `https://oklchpalette.ru/ru/palettes/${slug}`,
      languages: { 'en': `https://oklchpalette.ru/palettes/${slug}` },
    },
  };
}

export default async function CuratedPaletteDetailPageRu({ params }: PageProps) {
  const { slug } = await params;
  const palette = getCuratedPalette(slug);
  if (!palette) notFound();

  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Палитры', href: '/ru/palettes' },
        { label: palette.titleRu },
      ]}
    >
      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full">
        <CuratedPaletteDetail palette={palette} locale="ru" />
      </main>
    </ToolPageLayout>
  );
}
