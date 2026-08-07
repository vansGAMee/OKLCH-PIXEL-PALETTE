import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { AuthForm } from '@/components/auth/AuthForm';
import { SignUpForm } from '@/components/auth/SignUpForm';
import { isSupabaseAvailable } from '@/lib/supabase/client';
import { createClient } from '@/lib/supabase/server';

export const metadata: Metadata = {
  title: 'Создать аккаунт | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default async function RuSignupPage() {
  const supabase = await createClient();
  const available = Boolean(supabase);

  if (supabase) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data: { user } } = await (supabase as any).auth.getUser();
    if (user) redirect('/ru/dashboard');
  }

  return (
    <AuthForm
      locale="ru"
      title="Создать аккаунт"
      subtitle="Бесплатно. Без кредитной карты."
      footerContent={
        <span>
          Уже есть аккаунт?{' '}
          <Link href="/ru/login" className="text-purple-400 hover:text-purple-300 transition-colors">
            Войти
          </Link>
        </span>
      }
    >
      {available ? (
        <SignUpForm locale="ru" />
      ) : (
        <div className="text-center py-6 space-y-3">
          <div className="text-3xl">🔒</div>
          <p className="text-xs font-mono text-gray-400">
            Регистрация пока не настроена.
          </p>
          <p className="text-xs text-gray-500">
            Редактор работает без аккаунта.{' '}
            <Link href="/ru/create" className="text-purple-400 hover:text-purple-300">
              Открыть редактор →
            </Link>
          </p>
        </div>
      )}
    </AuthForm>
  );
}
