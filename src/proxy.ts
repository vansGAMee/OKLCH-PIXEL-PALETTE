/**
 * src/middleware.ts
 * Supabase session refresh middleware for Next.js App Router.
 * Refreshes auth tokens on every request to prevent session expiry.
 * Passes through gracefully when Supabase credentials are missing.
 */
import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export async function proxy(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  // Skip session refresh if credentials are missing (safe demo mode)
  if (!supabaseUrl || !supabaseKey) {
    return supabaseResponse;
  }

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) =>
          request.cookies.set(name, value)
        );
        supabaseResponse = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options)
        );
      },
    },
  });

  // Refresh session — do NOT remove this line
  const { data: { user } } = await supabase.auth.getUser();

  // Protected routes — redirect to login if not authenticated
  const protectedPaths = ['/dashboard', '/ru/dashboard', '/settings', '/ru/settings', '/onboarding', '/ru/onboarding'];
  const pathname = request.nextUrl.pathname;

  const isProtected = protectedPaths.some((p) => pathname === p || pathname.startsWith(p + '/'));

  if (isProtected && !user) {
    const loginUrl = pathname.startsWith('/ru') ? '/ru/login' : '/login';
    const redirectUrl = new URL(loginUrl, request.url);
    redirectUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(redirectUrl);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico, manifest, robots, sitemap
     * - public folder
     */
    '/((?!_next/static|_next/image|favicon|manifest|robots|sitemap|icon|opengraph|twitter|apple).*)',
  ],
};
