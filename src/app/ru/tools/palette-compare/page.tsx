import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { PaletteCompareTool } from '@/components/tools/PaletteCompareTool';

export const metadata: Metadata = {
  title: 'Сравнение палитр — OKLCH | OKLCH Pixel Palette',
  description: 'Сравните две цветовые палитры по OKLCH-метрикам: диапазон светлоты, хрома, охват тона и перцептуальное расстояние между палитрами.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools/palette-compare',
    languages: { 'en': 'https://oklchpalette.ru/tools/palette-compare' },
  },
};

export default function PaletteComparePageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Инструменты', href: '/ru/tools' },
        { label: 'Сравнение палитр' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Сравнение палитр
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Вставьте две палитры и сравните их OKLCH-метрики: диапазон светлоты, баланс хромы,
            охват тона и перцептуальное расстояние.
          </p>
        </section>

        <PaletteCompareTool locale="ru" />
      </main>
    </ToolPageLayout>
  );
}
