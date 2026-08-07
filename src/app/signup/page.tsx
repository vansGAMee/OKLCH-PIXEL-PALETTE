import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { AuthForm } from '@/components/auth/AuthForm';
import { SignUpForm } from '@/components/auth/SignUpForm';
import { isSupabaseAvailable } from '@/lib/supabase/client';
import { createClient } from '@/lib/supabase/server';

export const metadata: Metadata = {
  title: 'Create Account | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default async function SignupPage() {
  const supabase = await createClient();
  const available = Boolean(supabase);

  if (supabase) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data: { user } } = await (supabase as any).auth.getUser();
    if (user) redirect('/dashboard');
  }

  return (
    <AuthForm
      locale="en"
      title="Create account"
      subtitle="Free forever. No credit card required."
      footerContent={
        <span>
          Already have an account?{' '}
          <Link href="/login" className="text-purple-400 hover:text-purple-300 transition-colors">
            Sign in
          </Link>
        </span>
      }
    >
      {available ? (
        <SignUpForm locale="en" />
      ) : (
        <div className="text-center py-6 space-y-3">
          <div className="text-3xl">🔒</div>
          <p className="text-xs font-mono text-gray-400">
            Account registration is not configured yet.
          </p>
          <p className="text-xs text-gray-500">
            The editor works without an account.{' '}
            <Link href="/create" className="text-purple-400 hover:text-purple-300">
              Open Studio →
            </Link>
          </p>
        </div>
      )}
    </AuthForm>
  );
}
