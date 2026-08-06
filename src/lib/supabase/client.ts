/**
 * src/lib/supabase/client.ts
 * Browser-side Supabase client.
 * Safe to import in Client Components.
 * Returns null when credentials are missing (safe demo mode).
 */
import { createBrowserClient } from '@supabase/ssr';
import type { Database } from './types';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export function createClient() {
  if (!supabaseUrl || !supabaseKey) return null;
  return createBrowserClient<Database>(supabaseUrl, supabaseKey);
}

/** Returns true when Supabase credentials are configured. */
export function isSupabaseAvailable(): boolean {
  return Boolean(supabaseUrl && supabaseKey);
}
