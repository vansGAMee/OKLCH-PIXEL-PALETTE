import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { HomeAiPromptBox } from '@/components/home/HomeAiPromptBox';
import { messages } from '@/i18n/messages';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'ИИ-генератор цветовой палитры | OKLCH Pixel Palette',
  description: 'Генерируйте цветовые палитры из текстового описания. Напишите сцену или настроение на русском или английском языке — локальный ИИ создаст OKLCH-палитру без внешнего API.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools/ai-color-palette-generator',
    languages: { 'en': 'https://oklchpalette.ru/tools/ai-color-palette-generator' },
  },
  openGraph: {
    title: 'ИИ-генератор цветовой палитры | OKLCH Pixel Palette',
    description: 'Генерируйте цветовые палитры из текстового описания. Локальный ИИ, без OpenAI и Gemini.',
    type: 'website',
    url: 'https://oklchpalette.ru/ru/tools/ai-color-palette-generator',
  },
};

const EXAMPLES = [
  { prompt: 'зимний лес', label: 'зимний лес' },
  { prompt: 'фиолетовая пещера', label: 'фиолетовая пещера' },
  { prompt: 'бледно-розовый рассвет', label: 'бледно-розовый рассвет' },
  { prompt: 'неоновый киберпанк под дождём', label: 'неоновый киберпанк под дождём' },
  { prompt: 'уютное осеннее кафе', label: 'уютное осеннее кафе' },
  { prompt: 'заброшенная шахта', label: 'заброшенная шахта' },
];

const FAQ = [
  {
    q: 'Используется ли OpenAI или Gemini?',
    a: 'Нет. Инференс ИИ выполняется локально в браузере с помощью компактной многоязычной модели и ONNX Runtime Web. Генерация не использует удалённый API.',
  },
  {
    q: 'Нужна ли регистрация?',
    a: 'Нет. Для генерации и экспорта палитр аккаунт не нужен.',
  },
  {
    q: 'Почему первая генерация дольше?',
    a: 'Файлы модели загружаются при первом использовании и кэшируются браузером. Последующие генерации выполняются быстрее.',
  },
  {
    q: 'Как работает перевод текста в палитру?',
    a: 'Текст преобразуется в семантический вектор с помощью локальной многоязычной модели. Вектор сопоставляется с набором семантических цветовых якорей, что даёт базовый цвет в OKLCH. Затем из него строится палитра на основе цветовой гармонии.',
  },
];

export default function AiColorPaletteGeneratorPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Инструменты', href: '/ru/tools' },
        { label: 'ИИ-генератор палитры' },
      ]}
    >
      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-14">

        <section className="space-y-6">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
              Локальный ИИ · Без внешнего API
            </div>
            <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
              ИИ-генератор цветовой палитры
            </h1>
            <p className="text-base text-gray-300 font-sans max-w-2xl">
              Напишите сцену, настроение или идею. Локальная ИИ-модель в браузере переводит текст
              в стартовую OKLCH-палитру. Работает на русском и английском.
            </p>
          </div>
          <HomeAiPromptBox locale="ru" prompts={messages['ru'].aiSection.prompts} />
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">Примеры запросов</h2>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map(({ prompt, label }) => (
              <Link
                key={prompt}
                href={`/ru/create?prompt=${encodeURIComponent(prompt)}`}
                className="text-xs font-mono px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 hover:border-purple-500/40 hover:text-purple-300 text-gray-400 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {label}
              </Link>
            ))}
          </div>
        </section>

        <section className="space-y-5">
          <h2 className="text-xl font-mono font-bold text-white">Как это работает</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { step: '1', title: 'Описываете', desc: 'Вводите любую сцену, настроение или идею на русском или английском.' },
              { step: '2', title: 'Сопоставление', desc: 'Локальная многоязычная модель преобразует текст в вектор и находит ближайший семантический якорь цвета.' },
              { step: '3', title: 'Генерация', desc: 'Якорный цвет становится базовым. Тень, светлое и акцент создаются через OKLCH-гармонию.' },
            ].map(({ step, title, desc }) => (
              <div key={step} className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
                <div className="text-2xl font-mono font-black text-purple-500/50">{step}</div>
                <h3 className="text-sm font-mono font-bold text-white">{title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="glass-panel rounded-2xl border border-white/10 p-6 space-y-4">
          <h2 className="text-base font-mono font-bold text-white">Технические детали</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            Инференс ИИ выполняется локально в браузере с помощью компактной многоязычной модели
            и ONNX Runtime Web. Файлы модели загружаются при первом использовании и кэшируются браузером.
            Генерация не использует удалённый API — OpenAI, Gemini и Anthropic не задействованы.
          </p>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            Все сгенерированные цвета адаптируются к гамуту sRGB с сохранением тона и перцептуальной
            светлоты. Палитра содержит роли OKLCH: тень, базовый, светлый и акцент.
          </p>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">FAQ</h2>
          <dl className="space-y-3">
            {FAQ.map(({ q, a }) => (
              <div key={q} className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
                <dt className="text-sm font-mono font-bold text-white">{q}</dt>
                <dd className="text-xs text-gray-300 font-sans leading-relaxed">{a}</dd>
              </div>
            ))}
          </dl>
        </section>
      </main>
    </ToolPageLayout>
  );
}
