import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ImageToPalette } from '@/components/tools/ImageToPalette';

export const metadata: Metadata = {
  title: 'Извлечение палитры из изображения | OKLCH Pixel Palette',
  description: 'Перетащите любое изображение для извлечения палитры пиксель-арта. Обработка происходит локально в браузере без загрузки на сервер.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools/image-to-palette',
    languages: { 'en': 'https://oklchpalette.ru/tools/image-to-palette' },
  },
};

export default function ImageToPalettePageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Инструменты', href: '/ru/tools' },
        { label: 'Изображение → Палитра' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Изображение → Палитра пиксель-арта
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Перетащите любое изображение для извлечения уменьшенной палитры, пригодной для пиксель-арта.
            Перцептуальное объединение OKLCH удаляет почти одинаковые цвета.
            Всё работает локально — изображение никуда не отправляется.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">В браузере</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">Без загрузки</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">OKLCH объединение</span>
          </div>
        </section>

        <ImageToPalette locale="ru" />

        <section className="space-y-2">
          <h2 className="text-base font-mono font-bold text-white">Конфиденциальность</h2>
          <p className="text-sm text-gray-400 font-sans leading-relaxed">
            Вся обработка изображений выполняется в вашем браузере с помощью Canvas API.
            Никакие данные пикселей не покидают ваше устройство.
          </p>
        </section>
      </main>
    </ToolPageLayout>
  );
}
