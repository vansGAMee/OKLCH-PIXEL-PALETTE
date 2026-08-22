import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { AsepriteConverter } from '@/components/tools/AsepriteConverter';

export const metadata: Metadata = {
  title: 'Конвертер палитры для Aseprite (PAL, GPL, CSS, JSON) | OKLCH Pixel Palette',
  description: 'Конвертируйте палитры в форматы для Aseprite, GIMP, Krita и веб-разработки: JASC PAL (.pal), GIMP Palette (.gpl), CSS-переменные, Tailwind и токены дизайна.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools/aseprite-palette-converter',
    languages: { 'en': 'https://oklchpalette.ru/tools/aseprite-palette-converter' },
  },
};

export default function AsepritePaletteConverterPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Инструменты', href: '/ru/tools' },
        { label: 'Конвертер Aseprite' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Конвертер палитр для Aseprite
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Конвертируйте цветовую палитру в форматы пиксель-арт редакторов (Aseprite, GIMP)
            и веб-разработки (CSS Variables, Tailwind Config, JSON Design Tokens).
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">JASC PAL (.pal)</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">GPL (.gpl)</span>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400">CSS &amp; Tailwind</span>
          </div>
        </section>

        <AsepriteConverter locale="ru" />

        <section className="space-y-4">
          <h2 className="text-lg font-mono font-bold text-white">Как импортировать в Aseprite</h2>
          <div className="glass-panel rounded-xl border border-white/10 p-5 space-y-3 text-xs text-gray-300 font-sans">
            <ol className="space-y-2 list-decimal list-inside">
              <li>Скачайте палитру в формате <code className="font-mono text-purple-300">.pal</code> или <code className="font-mono text-purple-300">.gpl</code>.</li>
              <li>Откройте <strong>Aseprite</strong>.</li>
              <li>На панели палитры нажмите кнопку <strong>Options</strong> (значок меню).</li>
              <li>Выберите <strong>Load Palette</strong> и выберите скачанный файл.</li>
            </ol>
          </div>
        </section>
      </main>
    </ToolPageLayout>
  );
}
