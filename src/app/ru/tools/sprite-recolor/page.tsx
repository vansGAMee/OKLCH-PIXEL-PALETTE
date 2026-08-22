import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { SpriteRecolor } from '@/components/tools/SpriteRecolor';

export const metadata: Metadata = {
  title: 'Перекраска спрайта — Маппинг палитры | OKLCH Pixel Palette',
  description: 'Загрузите пиксель-арт спрайт и перекрасьте его в цвета целевой палитры с помощью перцептуального расстояния OKLCH прямо в браузере.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools/sprite-recolor',
    languages: { 'en': 'https://oklchpalette.ru/tools/sprite-recolor' },
  },
};

export default function SpriteRecolorPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Инструменты', href: '/ru/tools' },
        { label: 'Перекраска спрайта' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Перекраска спрайта
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Перенесите цвета пиксель-арт спрайта на целевую палитру с использованием перцептуального
            OKLCH-маппинга. Альфа-прозрачность сохраняется, изображения никуда не отправляются.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">OKLCH расстояние</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">Сохранение прозрачности</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">Локально</span>
          </div>
        </section>

        <SpriteRecolor locale="ru" />
      </main>
    </ToolPageLayout>
  );
}
