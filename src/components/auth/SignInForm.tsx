'use client';
/**
 * src/components/auth/SignInForm.tsx
 */
import React, { useActionState } from 'react';
import { signIn } from '@/app/actions/auth';
import { Loader2, LogIn } from 'lucide-react';

const initialState = { error: undefined as string | undefined };

export function SignInForm({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const [state, action, isPending] = useActionState(
    async (_prev: typeof initialState, formData: FormData) => {
      const result = await signIn(formData);
      if ('error' in result) return { error: result.error };
      return { error: undefined };
    },
    initialState
  );

  const labels = {
    en: { email: 'Email', password: 'Password', submit: 'Sign In', loading: 'Signing in…' },
    ru: { email: 'Email', password: 'Пароль', submit: 'Войти', loading: 'Вход…' },
  }[locale];

  return (
    <form action={action} className="space-y-4" noValidate>
      {state.error && (
        <div role="alert" className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 font-mono">
          {state.error}
        </div>
      )}

      <div className="space-y-1.5">
        <label htmlFor="signin-email" className="block text-xs font-mono text-gray-300 font-bold">
          {labels.email}
        </label>
        <input
          id="signin-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          disabled={isPending}
          className="w-full bg-zinc-900 border border-white/10 rounded-lg px-4 py-2.5 text-sm font-mono text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all disabled:opacity-50"
          placeholder="you@example.com"
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="signin-password" className="block text-xs font-mono text-gray-300 font-bold">
          {labels.password}
        </label>
        <input
          id="signin-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          disabled={isPending}
          className="w-full bg-zinc-900 border border-white/10 rounded-lg px-4 py-2.5 text-sm font-mono text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all disabled:opacity-50"
          placeholder="••••••••"
        />
      </div>

      <button
        type="submit"
        disabled={isPending}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all shadow-md shadow-purple-900/30 focus:outline-none focus:ring-2 focus:ring-purple-400 disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {isPending ? (
          <><Loader2 className="w-4 h-4 animate-spin" />{labels.loading}</>
        ) : (
          <><LogIn className="w-4 h-4" />{labels.submit}</>
        )}
      </button>
    </form>
  );
}
