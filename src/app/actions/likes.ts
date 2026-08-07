'use server';
/**
 * src/app/actions/likes.ts
 * Server Actions for likes and bookmarks.
 */
import { revalidatePath } from 'next/cache';
import { createClient } from '@/lib/supabase/server';

type ActionResult = { error: string } | { success: true; liked?: boolean; bookmarked?: boolean };

export async function toggleLike(paletteId: string): Promise<ActionResult> {
  if (!/^[0-9a-f-]{36}$/.test(paletteId)) return { error: 'Invalid palette ID' };

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: { user } } = await (supabase as any).auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  // Check if already liked
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: existing } = await (supabase as any)
    .from('palette_likes')
    .select('user_id')
    .eq('user_id', user.id)
    .eq('palette_id', paletteId)
    .maybeSingle();

  if (existing) {
    // Unlike
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error } = await (supabase as any)
      .from('palette_likes')
      .delete()
      .eq('user_id', user.id)
      .eq('palette_id', paletteId);
    if (error) return { error: 'Could not remove like.' };
    revalidatePath('/p', 'page');
    return { success: true, liked: false };
  } else {
    // Like
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error } = await (supabase as any)
      .from('palette_likes')
      .insert({ user_id: user.id, palette_id: paletteId });
    if (error) return { error: 'Could not add like.' };
    revalidatePath('/p', 'page');
    return { success: true, liked: true };
  }
}

export async function toggleBookmark(paletteId: string): Promise<ActionResult> {
  if (!/^[0-9a-f-]{36}$/.test(paletteId)) return { error: 'Invalid palette ID' };

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: { user } } = await (supabase as any).auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: existing } = await (supabase as any)
    .from('palette_bookmarks')
    .select('user_id')
    .eq('user_id', user.id)
    .eq('palette_id', paletteId)
    .maybeSingle();

  if (existing) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error } = await (supabase as any)
      .from('palette_bookmarks')
      .delete()
      .eq('user_id', user.id)
      .eq('palette_id', paletteId);
    if (error) return { error: 'Could not remove bookmark.' };
    revalidatePath('/dashboard');
    revalidatePath('/ru/dashboard');
    return { success: true, bookmarked: false };
  } else {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error } = await (supabase as any)
      .from('palette_bookmarks')
      .insert({ user_id: user.id, palette_id: paletteId });
    if (error) return { error: 'Could not add bookmark.' };
    revalidatePath('/dashboard');
    revalidatePath('/ru/dashboard');
    return { success: true, bookmarked: true };
  }
}
