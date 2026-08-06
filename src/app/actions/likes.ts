/* eslint-disable @typescript-eslint/no-explicit-any */
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

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  // Check if already liked
  const { data: existing } = await (supabase as any)
    .from('palette_likes')
    .select('user_id')
    .eq('user_id', user.id)
    .eq('palette_id', paletteId)
    .single();

  if (existing) {
    // Unlike
    const { error } = await (supabase as any)
      .from('palette_likes')
      .delete()
      .eq('user_id', user.id)
      .eq('palette_id', paletteId);
    if (error) return { error: 'Could not remove like.' };
    revalidatePath(`/p`);
    return { success: true, liked: false };
  } else {
    // Like
    const { error } = await (supabase as any)
      .from('palette_likes')
      .insert({ user_id: user.id, palette_id: paletteId });
    if (error) return { error: 'Could not add like.' };
    revalidatePath(`/p`);
    return { success: true, liked: true };
  }
}

export async function toggleBookmark(paletteId: string): Promise<ActionResult> {
  if (!/^[0-9a-f-]{36}$/.test(paletteId)) return { error: 'Invalid palette ID' };

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  const { data: existing } = await (supabase as any)
    .from('palette_bookmarks')
    .select('user_id')
    .eq('user_id', user.id)
    .eq('palette_id', paletteId)
    .single();

  if (existing) {
    const { error } = await (supabase as any)
      .from('palette_bookmarks')
      .delete()
      .eq('user_id', user.id)
      .eq('palette_id', paletteId);
    if (error) return { error: 'Could not remove bookmark.' };
    revalidatePath('/dashboard');
    return { success: true, bookmarked: false };
  } else {
    const { error } = await (supabase as any)
      .from('palette_bookmarks')
      .insert({ user_id: user.id, palette_id: paletteId });
    if (error) return { error: 'Could not add bookmark.' };
    revalidatePath('/dashboard');
    return { success: true, bookmarked: true };
  }
}
