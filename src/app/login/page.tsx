import type { Metadata } from 'next';
import Link from 'next/link';
import { AuthForm } from '@/components/auth/AuthForm';
import { SignInForm } from '@/components/auth/SignInForm';
import { redirect } from 'next/navigation';
import { createClient } from '@/lib/supabase/server';

export const metadata: Metadata = {
  title: 'Sign In | OKLCH Pixel Palette',
  robots: { index: false, follow: false },
};

export default async function LoginPage() {
  const supabase = await createClient();
  const available = Boolean(supabase);

  if (supabase) {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) redirect('/dashboard');
  }

return (
    <AuthForm
      locale="en"
      title="Sign in"
      subtitle="Access your saved palettes and dashboard."
      footerContent={
        <span>
          No account?{' '}
          <Link href="/signup" className="text-purple-400 hover:text-purple-300 transition-colors">
            Create one free
          </Link>
        </span>
      }
    >
      {available ? (
        <SignInForm locale="en" />
      ) : (
        <div className="text-center py-6 space-y-3">
          <div className="text-3xl">🔒</div>
          <p className="text-xs font-mono text-gray-400">
            Account features are not configured yet.
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
