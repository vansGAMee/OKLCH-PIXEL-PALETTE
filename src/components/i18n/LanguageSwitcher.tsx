'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Locale } from '@/i18n/messages';

interface LanguageSwitcherProps {
  currentLocale: Locale;
}

export const LanguageSwitcher: React.FC<LanguageSwitcherProps> = ({ currentLocale }) => {
  const pathname = usePathname() || '/';

  // Compute target path for switching locales
  const getLocalePath = (targetLocale: Locale): string => {
    const isRuPath = pathname === '/ru' || pathname.startsWith('/ru/');

    if (targetLocale === 'ru') {
      if (isRuPath) return pathname;
      return pathname === '/' ? '/ru' : `/ru${pathname}`;
    } else {
      // targetLocale === 'en'
      if (!isRuPath) return pathname;
      if (pathname === '/ru') return '/';
      return pathname.replace(/^\/ru/, '') || '/';
    }
  };

  return (
    <div className="flex items-center bg-zinc-900/90 p-0.5 rounded-lg border border-white/10 text-xs font-mono select-none">
      <Link
        href={getLocalePath('en')}
        className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
          currentLocale === 'en'
            ? 'bg-purple-600 text-white font-bold shadow-sm'
            : 'text-gray-400 hover:text-gray-200'
        }`}
        aria-label="Switch to English"
      >
        EN
      </Link>
      <span className="text-gray-600 px-0.5">/</span>
      <Link
        href={getLocalePath('ru')}
        className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
          currentLocale === 'ru'
            ? 'bg-purple-600 text-white font-bold shadow-sm'
            : 'text-gray-400 hover:text-gray-200'
        }`}
        aria-label="Переключить на Русский"
      >
        RU
      </Link>
    </div>
  );
};
