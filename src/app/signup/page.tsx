import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { AuthForm } from '@/components/auth/AuthForm';
import { SignUpForm } from '@/components/auth/SignUpForm';
import { createClient } from '@/lib/supabase/server';

export const metadata: Metadata = {
  title: 'Registration Unavailable | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default async function SignupPage() {
  const supabase = await createClient();

  if (supabase) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data: { user } } = await (supabase as any).auth.getUser();
    if (user) redirect('/dashboard');
  }

  return (
    <AuthForm
      locale="en"
      title="Registration"
      subtitle="Registration is temporarily unavailable."
      footerContent={
        <span>
          Already have an account?{' '}
          <Link href="/login" className="text-purple-400 hover:text-purple-300 transition-colors">
            Sign in
          </Link>
        </span>
      }
    >
      <SignUpForm locale="en" />
    </AuthForm>
  );
}
