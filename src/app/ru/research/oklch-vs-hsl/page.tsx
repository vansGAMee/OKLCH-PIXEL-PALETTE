import type { Metadata } from 'next';
import Link from 'next/link';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ArrowRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'OKLCH против HSL: почему пиксель-арту нужен перцептуальный цвет | OKLCH Pixel Palette',
  description: 'Инженерное сравнение цветовых пространств HSL и OKLCH. Почему светлота в HSL приводит к грязным теням и как OKLCH решает проблему контраста в пиксель-арте.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/research/oklch-vs-hsl',
    languages: { 'en': 'https://oklchpalette.ru/research/oklch-vs-hsl' },
  },
};

export default function OklchVsHslPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Исследования' },
        { label: 'OKLCH против HSL' },
      ]}
    >
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-12">
        <header className="space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
            Цветоведение и инженерия
          </div>
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            OKLCH против HSL:<br />почему пиксель-арту нужен перцептуальный цвет
          </h1>
          <p className="text-base text-gray-300 font-sans leading-relaxed">
            Десятилетиями программы для цифрового рисования использовали HSL и HSV.
            Несмотря на математическую простоту, HSL не учитывает особенности человеческого зрения,
            создавая несбалансированные тени и неравномерный контраст.
          </p>
        </header>

        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">1. Фундаментальный изъян светлоты в HSL</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            В пространстве HSL чистый жёлтый (<code className="font-mono text-purple-300">#FFFF00</code>) и чистый синий (<code className="font-mono text-purple-300">#0000FF</code>)
            имеют абсолютно одинаковое значение светлоты: <strong className="text-white">L = 50%</strong>.
          </p>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            Однако человеческий глаз воспринимает жёлтый значительно ярче синего.
            В пространстве OKLCH (разработанном Бьёрном Оттоссоном в 2020 году) это исправлено:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div className="glass-panel rounded-xl p-4 border border-white/10 space-y-2">
              <div className="h-12 rounded-lg bg-[#ffff00] flex items-center justify-center font-mono text-xs font-bold text-black shadow">
                #FFFF00 (Жёлтый)
              </div>
              <div className="text-xs font-mono text-gray-400 space-y-1">
                <div>Светлота HSL: <strong className="text-white">50%</strong></div>
                <div>Светлота OKLCH: <strong className="text-yellow-400">96.8%</strong> (воспринимаемая)</div>
              </div>
            </div>

            <div className="glass-panel rounded-xl p-4 border border-white/10 space-y-2">
              <div className="h-12 rounded-lg bg-[#0000ff] flex items-center justify-center font-mono text-xs font-bold text-white shadow">
                #0000FF (Синий)
              </div>
              <div className="text-xs font-mono text-gray-400 space-y-1">
                <div>Светлота HSL: <strong className="text-white">50%</strong></div>
                <div>Светлота OKLCH: <strong className="text-blue-400">45.2%</strong> (воспринимаемая)</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">2. Рампы затенения и грязные переходы</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            При создании цветового рампа в HSL линейный шаг светлоты даёт разный контраст для разных тонов.
            Синий рамп выглядит тёмным и сплюснутым, а жёлтый моментально выгорает в белый.
          </p>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            OKLCH моделирует светлоту (<code className="font-mono text-purple-300">L</code>) по перцептуально равномерной шкале.
            Шаг +10% ощущается глазом одинаково ярко в бирюзовом, фиолетовом или янтарном диапазоне.
          </p>
        </section>

        <section className="glass-panel rounded-2xl border border-purple-500/30 p-8 text-center space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">Попробуйте сами</h2>
          <p className="text-sm text-gray-400 font-sans">
            Создайте палитру с перцептуальным балансом в генераторе.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link
              href="/ru/tools/color-ramp-generator"
              className="px-6 py-2.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-md flex items-center gap-1.5"
            >
              Генератор рампов <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <Link
              href="/ru/create"
              className="px-6 py-2.5 text-xs font-mono text-purple-300 hover:text-white rounded-xl border border-purple-500/30 hover:border-purple-500/60 transition-all"
            >
              Открыть Студию
            </Link>
          </div>
        </section>
      </article>
    </ToolPageLayout>
  );
}
