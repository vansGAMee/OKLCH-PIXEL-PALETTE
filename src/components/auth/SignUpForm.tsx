'use client';
/**
 * src/components/auth/SignUpForm.tsx
 */
import React, { useActionState } from 'react';
import { signUp } from '@/app/actions/auth';
import { Loader2, UserPlus } from 'lucide-react';

const initialState = { error: undefined as string | undefined, success: false };

export function SignUpForm({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const [state, action, isPending] = useActionState(
    async (_prev: typeof initialState, formData: FormData) => {
      const result = await signUp(formData);
      if ('error' in result) return { error: result.error, success: false };
      return { error: undefined, success: true };
    },
    initialState
  );

  const labels = {
    en: {
      email: 'Email',
      password: 'Password (min 8 chars)',
      submit: 'Create Account',
      loading: 'Creating account…',
      success: 'Account created! Check your email or sign in directly.',
    },
    ru: {
      email: 'Email',
      password: 'Пароль (минимум 8 символов)',
      submit: 'Создать аккаунт',
      loading: 'Создание аккаунта…',
      success: 'Аккаунт создан! Проверьте почту или войдите сразу.',
    },
  }[locale];

  if (state.success) {
    return (
      <div className="text-center space-y-3 py-4">
        <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto">
          <span className="text-2xl">✓</span>
        </div>
        <p className="text-sm font-mono text-emerald-400">{labels.success}</p>
      </div>
    );
  }

  return (
    <form action={action} className="space-y-4" noValidate>
      {state.error && (
        <div role="alert" className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 font-mono">
          {state.error}
        </div>
      )}

      <div className="space-y-1.5">
        <label htmlFor="signup-email" className="block text-xs font-mono text-gray-300 font-bold">
          {labels.email}
        </label>
        <input
          id="signup-email"
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
        <label htmlFor="signup-password" className="block text-xs font-mono text-gray-300 font-bold">
          {labels.password}
        </label>
        <input
          id="signup-password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
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
          <><UserPlus className="w-4 h-4" />{labels.submit}</>
        )}
      </button>
    </form>
  );
}
