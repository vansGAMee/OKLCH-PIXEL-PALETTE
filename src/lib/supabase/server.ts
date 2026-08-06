/**
 * src/lib/supabase/server.ts
 * Server-side Supabase client for App Router (Server Components, Route Handlers, Server Actions).
 * Uses cookie-based session storage via next/headers.
 * Returns null when credentials are missing (safe demo mode).
 */
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';
import type { Database } from './types';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export async function createClient() {
  if (!supabaseUrl || !supabaseKey) return null;

  const cookieStore = await cookies();

  return createServerClient<Database>(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          );
        } catch {
          // setAll is called from Server Components — cookies can't be set there.
          // The middleware handles cookie refresh.
        }
      },
    },
  });
}
