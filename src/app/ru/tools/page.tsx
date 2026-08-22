import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ToolCard } from '@/components/tools/ToolCard';

export const metadata: Metadata = {
  title: 'Инструменты для палитр | OKLCH Pixel Palette',
  description: 'Бесплатные инструменты для работы с палитрами прямо в браузере: ИИ-генератор, анализатор, построитель рампов, извлечение палитры из изображения.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools',
    languages: { 'en': 'https://oklchpalette.ru/tools' },
  },
  openGraph: {
    title: 'Инструменты для палитр | OKLCH Pixel Palette',
    description: 'Бесплатные инструменты для работы с палитрами прямо в браузере: ИИ-генератор, анализатор, построитель рампов, извлечение палитры из изображения.',
    type: 'website',
    url: 'https://oklchpalette.ru/ru/tools',
  },
};

const TOOLS = [
  {
    title: 'ИИ-генератор цветовой палитры',
    description: 'Опишите сцену, настроение или идею на русском или английском языке. Сайт переводит текст в OKLCH-палитру прямо в браузере.',
    href: '/ru/tools/ai-color-palette-generator',
    badge: 'ИИ',
    available: true,
  },
  {
    title: 'Генератор пиксель-арт палитр',
    description: 'Создавайте перцептуально сбалансированные палитры на основе цветовых гармоний OKLCH. Экспорт в CSS, GPL, JASC PAL, HEX и JSON.',
    href: '/ru/create',
    available: true,
  },
  {
    title: 'Анализатор палитры',
    description: 'Вставьте любую палитру и получите детальную диагностику: распределение светлоты, похожие цвета, баланс хромы и предложение исправлений.',
    href: '/ru/tools/palette-analyzer',
    available: true,
  },
  {
    title: 'Генератор цветовых рампов',
    description: 'Постройте рампы теней для пиксель-арта с перцептуально равномерными шагами светлоты. Тёплый, холодный и нейтральный свет.',
    href: '/ru/tools/color-ramp-generator',
    available: true,
  },
  {
    title: 'Изображение → палитра',
    description: 'Перетащите любое изображение. Извлеките палитру для пиксель-арта с перцептуальным объединением похожих цветов.',
    href: '/ru/tools/image-to-palette',
    available: true,
  },
  {
    title: 'Сравнение палитр',
    description: 'Загрузите две палитры рядом. Сравните распределение светлоты, хромы и тона.',
    href: '/ru/tools/palette-compare',
    available: true,
  },
  {
    title: 'Импорт Lospec',
    description: 'Импортируйте палитру по URL из Lospec, просматривайте её в OKLCH и открывайте в генераторе.',
    href: '/ru/tools/lospec-palette-editor',
    available: true,
  },
  {
    title: 'Перекраска спрайта',
    description: 'Загрузите небольшой пиксель-арт спрайт и перекрасьте его цвета в цвета целевой палитры.',
    href: '/ru/tools/sprite-recolor',
    available: true,
  },
  {
    title: 'Конвертер палитры Aseprite',
    description: 'Конвертируйте любую палитру в форматы для Aseprite, GIMP и других программ: GPL, JASC PAL, HEX, CSS, JSON.',
    href: '/ru/tools/aseprite-palette-converter',
    available: true,
  },
];

export default function ToolsPageRu() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Главная', item: 'https://oklchpalette.ru/ru' },
      { '@type': 'ListItem', position: 2, name: 'Инструменты', item: 'https://oklchpalette.ru/ru/tools' },
    ],
  };

  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[{ label: 'Инструменты' }]}
    >
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-12">
        <section className="space-y-4">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Инструменты для палитр
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Бесплатные инструменты для создания, анализа и конвертации цветовых палитр.
            Всё работает локально в браузере — файлы на сервер не отправляются.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">
              Цветовое пространство OKLCH
            </span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">
              Локальная обработка
            </span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">
              Без регистрации
            </span>
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">Доступные инструменты</h2>
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

        <section className="glass-panel rounded-2xl border border-purple-500/20 p-8 text-center space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">Просто хотите создать палитру?</h2>
          <p className="text-sm text-gray-400 font-sans">
            Откройте генератор напрямую: выбирайте цвета, гармонии, предпросматривайте спрайты и экспортируйте.
          </p>
          <a
            href="/ru/create"
            className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/30 focus:outline-none focus:ring-2 focus:ring-purple-400"
          >
            Открыть генератор палитр
          </a>
        </section>
      </main>
    </ToolPageLayout>
  );
}
