'use client';
/**
 * src/components/settings/SettingsContent.tsx
 * Profile settings form: username, display name, bio.
 */
import React, { useActionState } from 'react';
import Link from 'next/link';
import { updateProfile } from '@/app/actions/auth';
import { Profile } from '@/lib/supabase/types';
import { Palette, ArrowLeft, Check, Loader2, Terminal } from 'lucide-react';

interface SettingsContentProps {
  locale: 'en' | 'ru';
  profile: Profile | null;
  email: string;
}

const initialState = { error: undefined as string | undefined, success: false };

type State = { error?: string; success?: boolean };

function settingsReducer(_prev: State, result: { error: string } | { success: true }): State {
  if ('error' in result) return { error: result.error, success: false };
  return { success: true };
}

export function SettingsContent({ locale, profile, email }: SettingsContentProps) {
  const isRu = locale === 'ru';
  const [state, formAction, isPending] = useActionState(
    async (_prev: State, formData: FormData) => {
      const result = await updateProfile(formData);
      return settingsReducer(_prev, result);
    },
    initialState
  );

  const dashboardHref = isRu ? '/ru/dashboard' : '/dashboard';

  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white">
      <header className="sticky top-0 z-40 border-b border-white/10 glass-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <Link href={isRu ? '/ru' : '/'} className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
              <Palette className="w-4 h-4" />
            </div>
            <span className="text-sm font-mono font-black text-white hidden sm:block">OKLCH PIXEL PALETTE</span>
          </Link>
          <Link href={dashboardHref} className="flex items-center gap-1.5 text-xs font-mono text-gray-400 hover:text-white transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" />
            {isRu ? 'Дашборд' : 'Dashboard'}
          </Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-10 w-full flex-1">
        <h1 className="text-2xl font-mono font-extrabold text-white mb-2">
          {isRu ? 'Настройки профиля' : 'Profile Settings'}
        </h1>
        <p className="text-sm text-gray-400 mb-8 font-sans">
          {isRu ? 'Управляйте своим именем пользователя и публичным профилем.' : 'Manage your username and public profile.'}
        </p>

        <div className="glass-panel rounded-2xl border border-white/10 p-6 space-y-6">
          <form action={formAction} className="space-y-5">
            {/* Username */}
            <div className="space-y-1.5">
              <label htmlFor="settings-username" className="block text-xs font-mono font-bold text-gray-300">
                {isRu ? 'Имя пользователя' : 'Username'} <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-3 flex items-center text-gray-500 text-sm font-mono">@</span>
                <input
                  id="settings-username"
                  name="username"
                  type="text"
                  defaultValue={profile?.username ?? ''}
                  required
                  minLength={3}
                  maxLength={24}
                  pattern="[a-zA-Z0-9_\-]+"
                  className="w-full pl-8 pr-4 py-2.5 bg-zinc-900 border border-white/10 rounded-lg text-sm font-mono text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  placeholder={isRu ? 'имя_пользователя' : 'username'}
                />
              </div>
              <p className="text-[11px] font-mono text-gray-500">
                {isRu ? '3–24 символа: буквы, цифры, _ и -' : '3–24 chars: letters, numbers, _ and -'}
              </p>
            </div>

            {/* Display Name */}
            <div className="space-y-1.5">
              <label htmlFor="settings-display-name" className="block text-xs font-mono font-bold text-gray-300">
                {isRu ? 'Отображаемое имя' : 'Display Name'}
              </label>
              <input
                id="settings-display-name"
                name="display_name"
                type="text"
                defaultValue={profile?.display_name ?? ''}
                maxLength={64}
                className="w-full px-4 py-2.5 bg-zinc-900 border border-white/10 rounded-lg text-sm font-mono text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                placeholder={isRu ? 'Ваше имя' : 'Your name'}
              />
            </div>

            {/* Bio */}
            <div className="space-y-1.5">
              <label htmlFor="settings-bio" className="block text-xs font-mono font-bold text-gray-300">
                Bio
              </label>
              <textarea
                id="settings-bio"
                name="bio"
                defaultValue={profile?.bio ?? ''}
                maxLength={200}
                rows={3}
                className="w-full px-4 py-2.5 bg-zinc-900 border border-white/10 rounded-lg text-sm font-mono text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                placeholder={isRu ? 'Расскажите о себе...' : 'Tell us about yourself...'}
              />
              <p className="text-[11px] font-mono text-gray-500">{isRu ? 'Максимум 200 символов' : 'Up to 200 characters'}</p>
            </div>

            {/* Email (read-only) */}
            <div className="space-y-1.5">
              <label htmlFor="settings-email" className="block text-xs font-mono font-bold text-gray-300">
                Email
              </label>
              <input
                id="settings-email"
                type="email"
                value={email}
                readOnly
                disabled
                className="w-full px-4 py-2.5 bg-zinc-800/50 border border-white/5 rounded-lg text-sm font-mono text-gray-400 cursor-not-allowed"
              />
            </div>

            {/* Error / Success */}
            {state.error && (
              <div className="p-3 rounded-lg bg-red-900/20 border border-red-500/30 text-red-400 text-xs font-mono">
                {state.error}
              </div>
            )}
            {state.success && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-900/20 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
                <Check className="w-4 h-4" />
                {isRu ? 'Профиль обновлён!' : 'Profile updated!'}
              </div>
            )}

            <button
              type="submit"
              disabled={isPending}
              className="flex items-center gap-2 px-6 py-2.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-60 rounded-lg transition-all"
            >
              {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              {isRu ? 'Сохранить' : 'Save changes'}
            </button>
          </form>
        </div>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center flex flex-col sm:flex-row items-center justify-center gap-3">
        <div className="flex items-center gap-1">
          <Terminal className="w-3.5 h-3.5 text-purple-400 inline" />
          <span>OKLCH Pixel Palette &copy; {new Date().getFullYear()}</span>
        </div>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link
          href={isRu ? '/ru/privacy' : '/privacy'}
          className="text-gray-400 hover:text-white transition-colors underline-offset-4 hover:underline"
        >
          {isRu ? 'Политика конфиденциальности' : 'Privacy Policy'}
        </Link>
      </footer>
    </div>
  );
}
