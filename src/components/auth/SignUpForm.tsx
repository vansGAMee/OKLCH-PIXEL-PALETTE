'use client';
/**
 * src/components/auth/SignUpForm.tsx
 * Displayed when user visits the signup route.
 * New registration is disabled to minimize personal data processing.
 */
import React from 'react';
import Link from 'next/link';
import { Palette, LogIn } from 'lucide-react';

export function SignUpForm({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const isRu = locale === 'ru';

  const content = {
    en: {
      message: 'Registration is temporarily unavailable',
      description: 'You can use all features of the color editor and explore public palettes without creating an account.',
      openStudio: 'Open Studio',
      signIn: 'Sign in with existing account',
    },
    ru: {
      message: 'Регистрация временно недоступна',
      description: 'Вы можете свободно использовать редактор палитр и просматривать галерею без создания аккаунта.',
      openStudio: 'Открыть редактор',
      signIn: 'Войти в существующий аккаунт',
    },
  }[locale];

  const studioHref = isRu ? '/ru/create' : '/create';
  const loginHref = isRu ? '/ru/login' : '/login';

  return (
    <div className="text-center py-4 space-y-5">
      <div className="w-12 h-12 rounded-2xl bg-purple-600/10 border border-purple-500/20 flex items-center justify-center mx-auto text-purple-400">
        <span className="text-xl font-mono">🔒</span>
      </div>

      <div className="space-y-2">
        <h2 className="text-base font-mono font-bold text-white">
          {content.message}
        </h2>
        <p className="text-xs text-gray-400 font-sans leading-relaxed max-w-sm mx-auto">
          {content.description}
        </p>
      </div>

      <div className="space-y-2.5 pt-2">
        <Link
          href={studioHref}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all shadow-md shadow-purple-900/30 focus:outline-none focus:ring-2 focus:ring-purple-400"
        >
          <Palette className="w-4 h-4" />
          {content.openStudio}
        </Link>

        <Link
          href={loginHref}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 text-xs font-mono text-gray-300 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-all"
        >
          <LogIn className="w-3.5 h-3.5" />
          {content.signIn}
        </Link>
      </div>
    </div>
  );
}
