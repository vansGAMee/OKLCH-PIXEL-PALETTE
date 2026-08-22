import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { LospecImporter } from '@/components/tools/LospecImporter';

export const metadata: Metadata = {
  title: 'Импорт палитры Lospec | OKLCH Pixel Palette',
  description: 'Импортируйте любую палитру с Lospec по URL или slug, просматривайте в OKLCH и открывайте в генераторе. Неофициальный инструмент.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/tools/lospec-palette-editor',
    languages: { 'en': 'https://oklchpalette.ru/tools/lospec-palette-editor' },
  },
};

export default function LospecPaletteEditorPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[
        { label: 'Инструменты', href: '/ru/tools' },
        { label: 'Импорт Lospec' },
      ]}
    >
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-10">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Импорт палитры с Lospec
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Введите URL палитры Lospec или slug, чтобы просмотреть её в OKLCH и открыть в генераторе.
            Импорт использует публичный JSON API Lospec.
          </p>
          <div className="text-xs font-mono text-gray-600">
            Неофициальный инструмент. Не аффилирован с Lospec. Палитры принадлежат их авторам.
          </div>
        </section>

        <LospecImporter locale="ru" />
      </main>
    </ToolPageLayout>
  );
}
