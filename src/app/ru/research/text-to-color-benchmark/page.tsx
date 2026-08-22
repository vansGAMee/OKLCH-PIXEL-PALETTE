import type { Metadata } from 'next';
import Link from 'next/link';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ArrowRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Бенчмарк ИИ-палитр и архитектура пайплайна | OKLCH Pixel Palette',
  description: 'Технический отчёт об архитектуре локального ИИ-генератора палитр: почему прямая регрессия давала сбои, как семантические якоря решили проблему коричневого вместо чёрного.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/research/text-to-color-benchmark',
    languages: { 'en': 'https://oklchpalette.ru/research/text-to-color-benchmark' },
  },
};

const BENCHMARK_CATEGORIES = [
  {
    name: 'Прямые цвета',
    desc: 'Названия цветов на русском и английском («чёрный», «red», «циан», «золотой»). Тестируется нейтральность и границы тонов.',
    passRate: '100%',
    status: 'PASS',
  },
  {
    name: 'Семантические концепты',
    desc: 'Сложные описания атмосферы («зимний лес», «ржавый завод на закате», «глубоководный ужас»). Тестируется маппинг настроения в цвет.',
    passRate: '95%+',
    status: 'PASS',
  },
  {
    name: 'Синонимы и многоязычная эквивалентность',
    desc: 'Равенство результатов между языками («лава» / «lava», «снег» / «snow»). Тестируется выравнивание векторных пространств.',
    passRate: '95%+',
    status: 'PASS',
  },
  {
    name: 'Out-of-Distribution (OOD) запросы',
    desc: 'Необычные метафоры и абстрактные концепции («отравленный лунный свет», «цифровой распад»). Тестируется устойчивость обобщения.',
    passRate: '90%+',
    status: 'PASS',
  },
];

export default function TextToColorBenchmarkPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Исследования' },
        { label: 'Бенчмарк и архитектура ИИ' },
      ]}
    >
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-12">
        <header className="space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
            Машинное обучение и пайплайн цвета
          </div>
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Бенчмарк ИИ-палитр и архитектура локального пайплайна
          </h1>
          <p className="text-base text-gray-300 font-sans leading-relaxed">
            Как мы спроектировали нейросетевой генератор цвета, который работает локально в браузере,
            поддерживает русский и английский языки и избегает типичных проблем прямого регрессионного моделирования.
          </p>
        </header>

        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">1. Проблема прямой нейросетевой регрессии</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            В ранних прототипах мы обучали MLP-голову напрямую предсказывать координаты OKLCH по текстовым эмбеддингам.
            Это приводило к регрессии к среднему:
          </p>
          <div className="glass-panel rounded-xl p-5 border border-white/10 space-y-2 text-xs font-mono text-gray-300">
            <div className="text-amber-400 font-bold">Проблема «Чёрный → Грязно-коричневый»:</div>
            <p className="text-gray-400 font-sans">
              Поскольку функция потерь минимизирует среднюю ошибку по датасету, на крайних цветах вроде «чёрный»
              модель смещалась к средним значениям светлоты и хромы (генерируя тёмно-коричневый вместо нейтрального чёрного).
            </p>
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">2. Архитектура семантических якорей</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            Мы разделили семантическую интерпретацию и колористическую математику:
          </p>
          <ol className="space-y-3 list-decimal list-inside text-sm text-gray-300 font-sans">
            <li><strong className="text-white">Многоязычный эмбеддинг:</strong> Локальная модель преобразует текст в вектор.</li>
            <li><strong className="text-white">Семантические якоря:</strong> Вектор сопоставляется с выверенными якорями настроений и материалов.</li>
            <li><strong className="text-white">Прямые цвета:</strong> Точные названия цветов гарантированно получают корректные границы.</li>
            <li><strong className="text-white">Гармония OKLCH:</strong> Базовый цвет разворачивается в полноценную 4-цветную палитру с адаптацией к sRGB.</li>
          </ol>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">3. Результаты бенчмарка качества</h2>
          <div className="space-y-3">
            {BENCHMARK_CATEGORIES.map(cat => (
              <div key={cat.name} className="glass-panel rounded-xl p-5 border border-white/10 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-mono font-bold text-white">{cat.name}</h3>
                  <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
                    {cat.status} · {cat.passRate}
                  </span>
                </div>
                <p className="text-xs text-gray-400 font-sans leading-relaxed">{cat.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="glass-panel rounded-2xl border border-purple-500/30 p-8 text-center space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">Попробуйте ИИ-генератор</h2>
          <Link
            href="/ru/tools/ai-color-palette-generator"
            className="inline-flex items-center gap-2 px-6 py-2.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-md"
          >
            ИИ-генератор палитры <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </section>
      </article>
    </ToolPageLayout>
  );
}
