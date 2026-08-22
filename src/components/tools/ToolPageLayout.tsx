import Link from 'next/link';
import { Palette, Terminal, ChevronRight } from 'lucide-react';

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface ToolPageLayoutProps {
  locale?: 'en' | 'ru';
  breadcrumbs?: BreadcrumbItem[];
  children: React.ReactNode;
}

/** Shared layout for tool pages — header + footer matching site design */
export function ToolPageLayout({ locale = 'en', breadcrumbs, children }: ToolPageLayoutProps) {
  const homeHref = locale === 'ru' ? '/ru' : '/';
  const createHref = locale === 'ru' ? '/ru/create' : '/create';
  const toolsHref = locale === 'ru' ? '/ru/tools' : '/tools';
  const studioLabel = locale === 'ru' ? 'Студия' : 'Studio';
  const toolsLabel = locale === 'ru' ? 'Инструменты' : 'Tools';

  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white overflow-x-hidden">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-white/10 glass-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-2">
          <Link href={homeHref} className="flex items-center gap-2 group focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg p-1 shrink-0">
            <div className="w-8 h-8 rounded-xl bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
              <Palette className="w-4 h-4" />
            </div>
            <span className="text-xs sm:text-sm font-mono font-black text-white hidden sm:block">OKLCH PIXEL PALETTE</span>
          </Link>

          <nav className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            <Link
              href={toolsHref}
              className="text-xs font-mono text-gray-300 hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 rounded px-2 py-1"
            >
              {toolsLabel}
            </Link>
            <Link
              href={createHref}
              className="flex items-center gap-1 px-2.5 sm:px-3 py-1.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all shadow-md shadow-purple-900/30 focus:outline-none focus:ring-2 focus:ring-purple-400"
            >
              {studioLabel} <ChevronRight className="w-3 h-3" />
            </Link>
          </nav>
        </div>
      </header>

      {/* Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 w-full">
          <ol className="flex items-center gap-1.5 text-xs font-mono text-gray-500 flex-wrap">
            <li>
              <Link href={homeHref} className="hover:text-gray-300 transition-colors">
                {locale === 'ru' ? 'Главная' : 'Home'}
              </Link>
            </li>
            {breadcrumbs.map((crumb, i) => (
              <li key={i} className="flex items-center gap-1.5">
                <ChevronRight className="w-3 h-3" />
                {crumb.href ? (
                  <Link href={crumb.href} className="hover:text-gray-300 transition-colors">
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="text-gray-300">{crumb.label}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}

      {/* Content */}
      {children}

      {/* Footer */}
      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-1">
            <Terminal className="w-3.5 h-3.5 text-purple-400 inline" />
            <span>OKLCH Pixel Palette © {new Date().getFullYear()}</span>
          </div>
          <nav className="flex items-center gap-4">
            <Link href={toolsHref} className="hover:text-white transition-colors">
              {toolsLabel}
            </Link>
            <Link href={createHref} className="hover:text-white transition-colors">
              {locale === 'ru' ? 'Генератор' : 'Generator'}
            </Link>
            <Link href={locale === 'ru' ? '/ru/privacy' : '/privacy'} className="hover:text-white transition-colors">
              {locale === 'ru' ? 'Конфиденциальность' : 'Privacy'}
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
