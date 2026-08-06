import type { Metadata } from 'next';
import Link from 'next/link';
import { AuthForm } from '@/components/auth/AuthForm';
import { SignInForm } from '@/components/auth/SignInForm';
import { isSupabaseAvailable } from '@/lib/supabase/client';

export const metadata: Metadata = {
  title: 'Войти | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default function RuLoginPage() {
  const available = isSupabaseAvailable();

  return (
    <AuthForm
      locale="ru"
      title="Войти"
      subtitle="Доступ к сохранённым палитрам и панели управления."
      footerContent={
        <span>
          Нет аккаунта?{' '}
          <Link href="/ru/signup" className="text-purple-400 hover:text-purple-300 transition-colors">
            Создать бесплатно
          </Link>
        </span>
      }
    >
      {available ? (
        <SignInForm locale="ru" />
      ) : (
        <div className="text-center py-6 space-y-3">
          <div className="text-3xl">🔒</div>
          <p className="text-xs font-mono text-gray-400">
            Аккаунты пока не настроены.
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
