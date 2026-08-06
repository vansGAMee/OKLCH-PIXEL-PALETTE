/* eslint-disable @typescript-eslint/no-explicit-any */
'use server';
/**
 * src/app/actions/events.ts
 * Server Action for tracking user events (funnel analytics).
 * Only logged-in users. Never logs IP or sensitive data.
 */
import { createClient } from '@/lib/supabase/server';
import { PaletteEventName } from '@/lib/supabase/types';

const ALLOWED_EVENTS: PaletteEventName[] = [
  'palette_generated',
  'palette_saved',
  'palette_published',
  'palette_remixed',
  'palette_exported',
];

export async function trackEvent(
  eventName: PaletteEventName,
  opts?: { paletteId?: string; exportFormat?: string }
): Promise<void> {
  // Validate event name against whitelist
  if (!ALLOWED_EVENTS.includes(eventName)) return;

  const supabase = await createClient();
  if (!supabase) return;

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return; // Only track authenticated users

  try {
    await (supabase as any).from('palette_events').insert({
      user_id: user.id,
      palette_id: opts?.paletteId ?? null,
      event_name: eventName,
      export_format: opts?.exportFormat ?? null,
    });
  } catch {
    // Silent fail — analytics should never break user flow
  }
}
