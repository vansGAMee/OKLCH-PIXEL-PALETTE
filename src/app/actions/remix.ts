'use server';
/**
 * src/app/actions/remix.ts
 * Server Action for remixing a public palette.
 */
import { redirect } from 'next/navigation';
import { createClient } from '@/lib/supabase/server';
import { generateSlug } from '@/lib/palette/serialize';

type ActionResult = { error: string } | { success: true; slug: string };

export async function remixPalette(sourcePaletteId: string): Promise<ActionResult> {
  if (!/^[0-9a-f-]{36}$/.test(sourcePaletteId)) return { error: 'Invalid palette ID' };

  const supabase = await createClient();
  if (!supabase) return { error: 'Service unavailable' };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: { user } } = await (supabase as any).auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  // Fetch source palette (must be public)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: source, error: fetchError } = await (supabase as any)
    .from('palettes')
    .select('id, slug, title, colors, color_count, base_hex, harmony, seed, tags, visibility')
    .eq('id', sourcePaletteId)
    .eq('visibility', 'public')
    .single();

  if (fetchError || !source) return { error: 'Palette not found or not public' };

  // Generate unique slug for remix
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const slugBase = generateSlug(`remix-${(source as any).title}`);
  const newSlug = `${slugBase}-${Date.now().toString(36)}`;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: newPalette, error: insertError } = await (supabase as any)
    .from('palettes')
    .insert({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      owner_id: user.id,
      slug: newSlug,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      title: `Remix of ${(source as any).title}`,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      colors: (source as any).colors,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      color_count: (source as any).color_count,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      base_hex: (source as any).base_hex,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      harmony: (source as any).harmony,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      seed: (source as any).seed,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      tags: (source as any).tags,
      visibility: 'private',
      source_palette_id: sourcePaletteId,
    })
    .select('slug')
    .single();

  if (insertError) {
    if (insertError.message?.includes('Palette limit')) {
      return { error: 'You have reached the maximum of 30 saved palettes.' };
    }
    return { error: 'Could not remix palette. Please try again.' };
  }

  redirect(`/dashboard`);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return { success: true, slug: (newPalette as any).slug };
}
