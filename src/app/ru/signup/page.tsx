import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { AuthForm } from '@/components/auth/AuthForm';
import { SignUpForm } from '@/components/auth/SignUpForm';
import { createClient } from '@/lib/supabase/server';

export const metadata: Metadata = {
  title: 'Регистрация временно недоступна | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default async function RuSignupPage() {
  const supabase = await createClient();

  if (supabase) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data: { user } } = await (supabase as any).auth.getUser();
    if (user) redirect('/ru/dashboard');
  }

  return (
    <AuthForm
      locale="ru"
      title="Регистрация"
      subtitle="Регистрация временно недоступна."
      footerContent={
        <span>
          Уже есть аккаунт?{' '}
          <Link href="/ru/login" className="text-purple-400 hover:text-purple-300 transition-colors">
            Войти
          </Link>
        </span>
      }
    >
      <SignUpForm locale="ru" />
    </AuthForm>
  );
}
