import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { PaletteAnalyzer } from '@/components/tools/PaletteAnalyzer';

export const metadata: Metadata = {
  title: 'Анализатор палитры — OKLCH диагностика | OKLCH Pixel Palette',
  description: 'Вставьте любую цветовую палитру и получите OKLCH-диагностику: распределение светлоты, похожие цвета, баланс хромы и автоматическое перцептуальное исправление.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools/palette-analyzer',
    languages: { 'en': 'https://oklchpalette.ru/tools/palette-analyzer' },
  },
  openGraph: {
    title: 'Анализатор палитры — OKLCH диагностика',
    description: 'Вставьте любую цветовую палитру и получите OKLCH-диагностику.',
    type: 'website',
    url: 'https://oklchpalette.ru/ru/tools/palette-analyzer',
  },
};

export default function PaletteAnalyzerPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Инструменты', href: '/ru/tools' },
        { label: 'Анализатор палитры' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Анализатор палитры
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Вставьте любой набор HEX-цветов и получите OKLCH-диагностику: диапазон светлоты,
            похожие цвета, баланс хромы и охват тона. Доступно автоматическое перцептуальное исправление.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">OKLCH</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">В браузере</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">2–16 цветов</span>
          </div>
        </section>

        <PaletteAnalyzer locale="ru" />

        <section className="space-y-4">
          <h2 className="text-lg font-mono font-bold text-white">Что означают метрики</h2>
          <dl className="space-y-3">
            {[
              {
                term: 'Диапазон L (светлота)',
                def: 'Разница значений OKLCH L между самым светлым и самым тёмным цветом. Диапазон менее 25% означает, что палитра будет выглядеть плоской в пиксель-арте.',
              },
              {
                term: 'ΔE (Дельта E)',
                def: 'Перцептуальное расстояние между двумя цветами в OKLCH. Значения ниже ~0.08 означают цвета, которые сложно различить в пиксель-арте.',
              },
              {
                term: 'Оценка здоровья',
                def: 'Диагностическая оценка сайта (0–100) на основе измеренных OKLCH-факторов. Это не отраслевой стандарт. Начинается с 90; баллы снимаются за обнаруженные проблемы.',
              },
            ].map(({ term, def }) => (
              <div key={term} className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
                <dt className="text-sm font-mono font-bold text-white">{term}</dt>
                <dd className="text-xs text-gray-400 font-sans leading-relaxed">{def}</dd>
              </div>
            ))}
          </dl>
        </section>
      </main>
    </ToolPageLayout>
  );
}
