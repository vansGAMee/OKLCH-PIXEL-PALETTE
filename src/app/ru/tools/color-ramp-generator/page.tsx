import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ColorRampGenerator } from '@/components/tools/ColorRampGenerator';

export const metadata: Metadata = {
  title: 'Генератор цветовых рампов — OKLCH для пиксель-арта | OKLCH Pixel Palette',
  description: 'Создавайте рампы теней для пиксель-арта с перцептуально равномерными шагами светлоты в OKLCH. Тёплый, холодный и нейтральный свет, управление сдвигом тона.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools/color-ramp-generator',
    languages: { 'en': 'https://oklchpalette.ru/tools/color-ramp-generator' },
  },
};

export default function ColorRampGeneratorPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Инструменты', href: '/ru/tools' },
        { label: 'Генератор рампов' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Генератор цветовых рампов
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Выберите базовый цвет и постройте рамп теней с перцептуально равномерными шагами светлоты.
            Пресеты тёплого, холодного и нейтрального света — для пиксель-арта и иллюстраций.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">OKLCH равномерные шаги</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">3–9 цветов</span>
          </div>
        </section>

        <ColorRampGenerator locale="ru" />

        <section className="space-y-3">
          <h2 className="text-lg font-mono font-bold text-white">Почему OKLCH для рампов?</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            Рампы на основе HSL часто выглядят неравномерно, потому что канал светлоты HSL
            не является перцептуально линейным. OKLCH использует перцептуально линейный канал L,
            поэтому равные числовые шаги дают равные воспринимаемые перепады яркости — что
            критично для плавного затенения спрайтов.
          </p>
        </section>
      </main>
    </ToolPageLayout>
  );
}
