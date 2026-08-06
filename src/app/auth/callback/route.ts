/**
 * src/app/auth/callback/route.ts
 * Handles Supabase Auth callbacks (email confirmation, OAuth, magic links).
 */
import { createClient } from '@/lib/supabase/server';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/dashboard';

  if (code) {
    const supabase = await createClient();
    if (supabase) {
      const { error } = await supabase.auth.exchangeCodeForSession(code);
      if (!error) {
        // Validate redirect to prevent open redirect
        const redirectUrl = next.startsWith('/') ? `${origin}${next}` : `${origin}/dashboard`;
        return NextResponse.redirect(redirectUrl);
      }
    }
  }

  // Return to error page if code exchange fails
  return NextResponse.redirect(`${origin}/login?error=auth_callback_failed`);
}
