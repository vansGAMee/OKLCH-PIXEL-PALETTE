/**
 * src/lib/palette/activePalette.ts
 * Unified active palette sharing across Studio and Artist Tools.
 */

export interface ActivePaletteData {
  colors: string[];
  locks?: number[];
  prompt?: string;
  seed?: number;
  count?: number;
  source?: 'studio' | 'ai' | 'image' | 'lospec' | 'ramp' | 'recolor';
  modelVersion?: string;
  updatedAt?: number;
}

export const ACTIVE_PALETTE_STORAGE_KEY = 'pixel_palette_active_palette_v1';

export function saveActivePalette(
  colors: string[],
  meta?: Omit<ActivePaletteData, 'colors' | 'updatedAt'>
): void {
  if (typeof window === 'undefined') return;
  try {
    const data: ActivePaletteData = {
      colors: colors.filter((c) => /^#[0-9a-fA-F]{6}$/i.test(c)),
      ...meta,
      updatedAt: Date.now(),
    };
    localStorage.setItem(ACTIVE_PALETTE_STORAGE_KEY, JSON.stringify(data));
  } catch {
    // Ignore storage quota or disabled errors
  }
}

export function loadActivePalette(): ActivePaletteData | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(ACTIVE_PALETTE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ActivePaletteData;
    if (Array.isArray(parsed.colors) && parsed.colors.length >= 2) {
      return parsed;
    }
  } catch {
    // Ignore
  }
  return null;
}

export function buildStudioUrl(
  colors: string[],
  options?: {
    prompt?: string;
    name?: string;
    locale?: 'en' | 'ru';
    mode?: 'ai' | 'manual';
    seed?: number;
  }
): string {
  const isRu = options?.locale === 'ru';
  const prefix = isRu ? '/ru/create' : '/create';
  const params = new URLSearchParams();

  if (colors.length > 0) {
    params.set('import', colors.join(','));
    params.set('base', colors[0]);
    params.set('count', String(Math.min(9, Math.max(2, colors.length))));
  }
  if (options?.prompt) {
    params.set('prompt', options.prompt);
  }
  if (options?.name) {
    params.set('name', options.name);
  }
  if (options?.seed !== undefined) {
    params.set('seed', String(options.seed));
  }

  const query = params.toString();
  return query ? `${prefix}?${query}` : prefix;
}
