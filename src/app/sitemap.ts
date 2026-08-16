import type { MetadataRoute } from 'next';
import { createClient } from '@/lib/supabase/server';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = 'https://oklchpalette.ru';
  const now = new Date().toISOString();

  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    { url: `${base}/`, changeFrequency: 'weekly', priority: 1.0, lastModified: now },
    { url: `${base}/create`, changeFrequency: 'daily', priority: 0.95, lastModified: now },
    { url: `${base}/explore`, changeFrequency: 'daily', priority: 0.85, lastModified: now },
    { url: `${base}/ru`, changeFrequency: 'weekly', priority: 0.95, lastModified: now },
    { url: `${base}/ru/create`, changeFrequency: 'daily', priority: 0.90, lastModified: now },
    { url: `${base}/ru/explore`, changeFrequency: 'daily', priority: 0.80, lastModified: now },
    // Guides (EN)
    { url: `${base}/guides/oklch-for-pixel-art`, changeFrequency: 'monthly', priority: 0.75 },
    { url: `${base}/guides/palette-file-formats`, changeFrequency: 'monthly', priority: 0.70 },
    { url: `${base}/guides/pixel-art-lightness`, changeFrequency: 'monthly', priority: 0.70 },
    // Tools
    { url: `${base}/tools/pixel-art-palette-generator`, changeFrequency: 'monthly', priority: 0.80 },
    // Legal
    { url: `${base}/privacy`, changeFrequency: 'yearly', priority: 0.20 },
    { url: `${base}/ru/privacy`, changeFrequency: 'yearly', priority: 0.20 },
    { url: `${base}/terms`, changeFrequency: 'yearly', priority: 0.20 },
  ];

  /* eslint-disable @typescript-eslint/no-explicit-any */
  // Dynamic: public palettes and profiles
  const dynamicPages: MetadataRoute.Sitemap = [];

  try {
    const supabase = await createClient();
    if (supabase) {
      // Public palettes
      const { data: palettes } = await (supabase as any)
        .from('palettes')
        .select('slug, updated_at')
        .eq('visibility', 'public')
        .order('updated_at', { ascending: false })
        .limit(500);

      if (palettes) {
        for (const p of (palettes as any[])) {
          dynamicPages.push({
            url: `${base}/p/${p.slug}`,
            changeFrequency: 'monthly',
            priority: 0.60,
            lastModified: p.updated_at,
          });
        }
      }

      // Public profiles
      const { data: profiles } = await (supabase as any)
        .from('profiles')
        .select('username, updated_at')
        .limit(500);

      if (profiles) {
        for (const p of (profiles as any[])) {
          dynamicPages.push({
            url: `${base}/u/${p.username}`,
            changeFrequency: 'weekly',
            priority: 0.50,
            lastModified: p.updated_at,
          });
        }
      }
    }
  } catch {
    // Sitemap builds without dynamic pages if Supabase is unavailable
  }

  return [...staticPages, ...dynamicPages];
}
