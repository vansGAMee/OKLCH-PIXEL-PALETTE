import type { Metadata } from 'next';
import Link from 'next/link';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { CURATED_PALETTES } from '@/lib/tools/curatedPalettes';
import { ChevronRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Коллекция пиксель-арт палитр | OKLCH Pixel Palette',
  description: 'Подборка сбалансированных цветовых палитр для пиксель-арта, игр и интерфейсов. Экспорт в Aseprite, GIMP, CSS и открытие в генераторе.',
  alternates: {
    canonical: 'https://oklchpalette.ru/ru/palettes',
    languages: { 'en': 'https://oklchpalette.ru/palettes' },
  },
};

export default function CuratedPalettesIndexPageRu() {
  return (
    <ToolPageLayout
      locale="ru"
      breadcrumbs={[{ label: 'Палитры' }]}
    >
      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-12">
        <section className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Коллекция пиксель-арт палитр
          </h1>
          <p className="text-base text-gray-300 font-sans max-w-2xl">
            Тематические палитры с выверенным балансом светлоты в пространстве OKLCH.
            Готовы к экспорту для Aseprite, GIMP, CSS или кастомизации в студии.
          </p>
        </section>

        <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {CURATED_PALETTES.map(p => (
            <Link
              key={p.slug}
              href={`/ru/palettes/${p.slug}`}
              className="glass-panel rounded-2xl border border-white/10 hover:border-purple-500/40 p-5 group transition-all space-y-3 flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-sm font-mono font-bold text-white group-hover:text-purple-300 transition-colors">
                    {p.titleRu}
                  </h2>
                  <ChevronRight className="w-4 h-4 text-gray-500 group-hover:text-purple-400 group-hover:translate-x-0.5 transition-all shrink-0" />
                </div>
                <p className="text-xs text-gray-400 font-sans leading-relaxed line-clamp-2">
                  {p.descriptionRu}
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex rounded-lg overflow-hidden border border-white/10 h-8">
                  {p.hexes.map((hex, i) => (
                    <div key={i} className="flex-1" style={{ backgroundColor: hex }} />
                  ))}
                </div>
                <div className="flex flex-wrap gap-1">
                  {p.tags.slice(0, 3).map(tag => (
                    <span key={tag} className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 text-gray-400">
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>
            </Link>
          ))}
        </section>
      </main>
    </ToolPageLayout>
  );
}
