/* eslint-disable @typescript-eslint/no-explicit-any */
'use server';
/**
 * src/app/actions/auth.ts
 * Server Actions for authentication.
 * All validation is server-side. Passwords are never logged.
 */
import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';
import { z } from 'zod';
import { createClient } from '@/lib/supabase/server';
import { createAdminClient } from '@/lib/supabase/admin';

// ---------- Schemas ----------
const signUpSchema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

const signInSchema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(1, 'Password is required'),
});

const usernameSchema = z.object({
  username: z
    .string()
    .min(3, 'Username must be at least 3 characters')
    .max(24, 'Username must be at most 24 characters')
    .regex(/^[a-zA-Z0-9_-]+$/, 'Username can only contain letters, numbers, _ and -'),
});

export type AuthResult = { error: string } | { success: true };

// ---------- Sign Up ----------
export async function signUp(formData: FormData): Promise<AuthResult> {
  const raw = {
    email: formData.get('email'),
    password: formData.get('password'),
  };

  const parsed = signUpSchema.safeParse(raw);
  if (!parsed.success) {
    return { error: parsed.error.issues[0].message };
  }

  const supabase = await createClient();
  if (!supabase) {
    return { error: 'Account features are currently unavailable. Try again later.' };
  }

  const { error } = await supabase.auth.signUp({
    email: parsed.data.email,
    password: parsed.data.password,
    options: {
      // Disable email confirmation for launch mode (no SMTP configured)
      // emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback?type=signup`,
    },
  });

  if (error) {
    // No account enumeration — return generic message
    console.error('[auth] signUp error (code):', error.code);
    return { error: 'Could not create account. Please try again.' };
  }

  return { success: true };
}

// ---------- Sign In ----------
export async function signIn(formData: FormData): Promise<AuthResult> {
  const raw = {
    email: formData.get('email'),
    password: formData.get('password'),
  };

  const parsed = signInSchema.safeParse(raw);
  if (!parsed.success) {
    return { error: parsed.error.issues[0].message };
  }

  const supabase = await createClient();
  if (!supabase) {
    return { error: 'Account features are currently unavailable.' };
  }

  const { error } = await supabase.auth.signInWithPassword({
    email: parsed.data.email,
    password: parsed.data.password,
  });

  if (error) {
    // Intentionally vague to prevent account enumeration
    return { error: 'Invalid email or password.' };
  }

  revalidatePath('/', 'layout');
  redirect('/dashboard');
}

// ---------- Sign Out ----------
export async function signOut(): Promise<void> {
  const supabase = await createClient();
  if (supabase) {
    await supabase.auth.signOut();
  }
  revalidatePath('/', 'layout');
  redirect('/');
}

// ---------- Check Username Availability ----------
export async function checkUsername(username: string): Promise<{ available: boolean; error?: string }> {
  const parsed = usernameSchema.safeParse({ username });
  if (!parsed.success) {
    return { available: false, error: parsed.error.issues[0].message };
  }

  const supabase = await createClient();
  if (!supabase) return { available: false, error: 'Service unavailable' };

  const { data } = await (supabase as any)
    .from('profiles')
    .select('username')
    .eq('username', username.toLowerCase())
    .single();

  return { available: !data };
}

// ---------- Set Username (Onboarding) ----------
export async function setUsername(formData: FormData): Promise<AuthResult> {
  const raw = { username: formData.get('username') };
  const parsed = usernameSchema.safeParse(raw);
  if (!parsed.success) {
    return { error: parsed.error.issues[0].message };
  }

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) return { error: 'Not authenticated' };

  const { error } = await (supabase as any)
    .from('profiles')
    .update({ username: parsed.data.username.toLowerCase() })
    .eq('id', user.id);

  if (error) {
    if (error.code === '23505') {
      return { error: 'This username is already taken.' };
    }
    return { error: 'Could not set username. Please try again.' };
  }

  revalidatePath('/dashboard');
  redirect('/dashboard');
}

// ---------- Delete Account ----------
export async function deleteAccount(formData: FormData): Promise<AuthResult> {
  const confirmPhrase = formData.get('confirm_phrase');
  if (confirmPhrase !== 'delete my account') {
    return { error: 'Please type the exact confirmation phrase.' };
  }

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) return { error: 'Not authenticated' };

  const adminClient = createAdminClient();
  if (!adminClient) {
    return { error: 'Account deletion is currently unavailable. Contact support.' };
  }

  // Delete auth user — cascades to public.profiles and all user data via ON DELETE CASCADE
  const { error } = await adminClient.auth.admin.deleteUser(user.id);
  if (error) {
    console.error('[auth] deleteUser error:', error.message);
    return { error: 'Could not delete account. Please try again or contact support.' };
  }

  await supabase.auth.signOut();
  revalidatePath('/', 'layout');
  redirect('/');
}
