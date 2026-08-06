/* eslint-disable @typescript-eslint/no-explicit-any */
'use server';
/**
 * src/app/actions/palettes.ts
 * Server Actions for cloud palette management.
 */
import { revalidatePath } from 'next/cache';
import { z } from 'zod';
import { createClient } from '@/lib/supabase/server';
import { SavePaletteInputSchema } from '@/lib/palette/schema';
import { serializePaletteColors, generateSlug } from '@/lib/palette/serialize';

type ActionResult<T = void> = { error: string } | { success: true; data?: T };

// ---------- Save Palette ----------
export async function savePalette(input: unknown): Promise<ActionResult<{ id: string; slug: string }>> {
  const parsed = SavePaletteInputSchema.safeParse(input);
  if (!parsed.success) {
    return { error: parsed.error.issues[0].message };
  }

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  const { title, description, tags, visibility, palette } = parsed.data;

  // Generate unique slug
  const slugBase = generateSlug(title);
  const slug = `${slugBase}-${Date.now().toString(36)}`;

  const { data, error } = await (supabase as any)
    .from('palettes')
    .insert({
      owner_id: user.id,
      slug,
      title,
      description: description ?? null,
      colors: serializePaletteColors(palette),
      color_count: palette.count,
      base_hex: palette.base.hex,
      harmony: palette.harmony,
      seed: palette.seed,
      tags: tags?.map((t) => t.toLowerCase().trim()) ?? null,
      visibility,
      published_at: visibility === 'public' ? new Date().toISOString() : null,
    })
    .select('id, slug')
    .single();

  if (error) {
    if (error.message?.includes('Palette limit reached') || error.message?.includes('maximum 30')) {
      return { error: 'You have reached the maximum of 30 saved palettes.' };
    }
    if (error.message?.includes('Public palette limit') || error.message?.includes('maximum 3')) {
      return { error: 'You have reached the maximum of 3 public palettes.' };
    }
    console.error('[palettes] savePalette error:', error.code);
    return { error: 'Could not save palette. Please try again.' };
  }

  revalidatePath('/dashboard');
  revalidatePath('/explore');
  return { success: true, data: { id: (data as any).id, slug: (data as any).slug } };
}

// ---------- Update Palette ----------
export async function updatePalette(
  paletteId: string,
  input: Partial<{ title: string; description: string; visibility: 'private' | 'unlisted' | 'public'; tags: string[] }>
): Promise<ActionResult> {
  const updateSchema = z.object({
    title: z.string().min(1).max(80).optional(),
    description: z.string().max(500).optional(),
    visibility: z.enum(['private', 'unlisted', 'public']).optional(),
    tags: z.array(z.string().max(32)).max(8).optional(),
  });

  const parsed = updateSchema.safeParse(input);
  if (!parsed.success) return { error: parsed.error.issues[0].message };

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  // Validate ID format
  if (!/^[0-9a-f-]{36}$/.test(paletteId)) return { error: 'Invalid palette ID' };

  const updateData: Record<string, unknown> = { ...parsed.data, updated_at: new Date().toISOString() };
  if (parsed.data.visibility === 'public') {
    updateData.published_at = new Date().toISOString();
  }

  const { error } = await (supabase as any)
    .from('palettes')
    .update(updateData)
    .eq('id', paletteId)
    .eq('owner_id', user.id); // RLS double-check at app level

  if (error) {
    if (error.message?.includes('Public palette limit')) {
      return { error: 'You have reached the maximum of 3 public palettes.' };
    }
    return { error: 'Could not update palette.' };
  }

  revalidatePath('/dashboard');
  revalidatePath('/explore');
  return { success: true };
}

// ---------- Delete Palette ----------
export async function deletePalette(paletteId: string): Promise<ActionResult> {
  if (!/^[0-9a-f-]{36}$/.test(paletteId)) return { error: 'Invalid palette ID' };

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  const { error } = await (supabase as any)
    .from('palettes')
    .delete()
    .eq('id', paletteId)
    .eq('owner_id', user.id);

  if (error) return { error: 'Could not delete palette.' };

  revalidatePath('/dashboard');
  return { success: true };
}

// ---------- Feature Palette (set/clear featured slot) ----------
export async function featurePalette(
  paletteId: string,
  position: 1 | 2 | 3 | null
): Promise<ActionResult> {
  if (paletteId && !/^[0-9a-f-]{36}$/.test(paletteId)) return { error: 'Invalid palette ID' };

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  // Clear any existing palette in the same position first
  if (position !== null) {
    await (supabase as any)
      .from('palettes')
      .update({ featured_position: null })
      .eq('owner_id', user.id)
      .eq('featured_position', position);
  }

  const { error } = await (supabase as any)
    .from('palettes')
    .update({ featured_position: position })
    .eq('id', paletteId)
    .eq('owner_id', user.id);

  if (error) return { error: 'Could not update featured position.' };

  revalidatePath('/dashboard');
  revalidatePath(`/u`);
  return { success: true };
}
