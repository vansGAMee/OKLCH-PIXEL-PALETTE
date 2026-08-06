/**
 * src/app/ru/auth/callback/route.ts
 * Russian locale auth callback — same logic as EN version.
 */
import { createClient } from '@/lib/supabase/server';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/ru/dashboard';

  if (code) {
    const supabase = await createClient();
    if (supabase) {
      const { error } = await supabase.auth.exchangeCodeForSession(code);
      if (!error) {
        const redirectUrl = next.startsWith('/') ? `${origin}${next}` : `${origin}/ru/dashboard`;
        return NextResponse.redirect(redirectUrl);
      }
    }
  }

  return NextResponse.redirect(`${origin}/ru/login?error=auth_callback_failed`);
}
