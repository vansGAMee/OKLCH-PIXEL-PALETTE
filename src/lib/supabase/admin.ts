/**
 * src/lib/supabase/admin.ts
 * Service-role Supabase client.
 * SERVER-ONLY — never import in client components or pages.
 * Used for: account deletion (cascades auth.users), admin operations.
 */
import 'server-only';
import { createClient as createSupabaseClient } from '@supabase/supabase-js';
import type { Database } from './types';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SECRET_KEY;

export function createAdminClient() {
  if (!supabaseUrl || !supabaseServiceKey) {
    return null;
  }
  return createSupabaseClient<Database>(supabaseUrl, supabaseServiceKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

export function isAdminAvailable(): boolean {
  return Boolean(supabaseUrl && supabaseServiceKey);
}
