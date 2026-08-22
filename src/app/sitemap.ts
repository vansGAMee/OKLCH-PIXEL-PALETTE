import type { MetadataRoute } from 'next';
import { createClient } from '@/lib/supabase/server';
import { CURATED_PALETTES } from '@/lib/tools/curatedPalettes';

/**
 * Stable build-date for pages whose content does not change between builds.
 * This date reflects the last time these particular pages had significant content changes.
 * Update this when genuinely updating a page's content.
 */
const PAGE_DATES: Record<string, string> = {
  '/':                                     '2026-08-22',
  '/create':                               '2026-08-22',
  '/ru':                                   '2026-08-22',
  '/ru/create':                            '2026-08-22',
  '/explore':                              '2026-07-01',
  '/ru/explore':                           '2026-07-01',
  '/guides/oklch-for-pixel-art':           '2026-06-01',
  '/guides/palette-file-formats':          '2026-06-01',
  '/tools':                                '2026-08-22',
  '/ru/tools':                             '2026-08-22',
  '/tools/pixel-art-palette-generator':    '2026-08-22',
  '/tools/ai-color-palette-generator':     '2026-08-22',
  '/ru/tools/ai-color-palette-generator':  '2026-08-22',
  '/tools/palette-analyzer':               '2026-08-22',
  '/ru/tools/palette-analyzer':            '2026-08-22',
  '/tools/color-ramp-generator':           '2026-08-22',
  '/ru/tools/color-ramp-generator':        '2026-08-22',
  '/tools/image-to-palette':               '2026-08-22',
  '/ru/tools/image-to-palette':            '2026-08-22',
  '/tools/palette-compare':                '2026-08-22',
  '/ru/tools/palette-compare':             '2026-08-22',
  '/tools/lospec-palette-editor':          '2026-08-22',
  '/ru/tools/lospec-palette-editor':       '2026-08-22',
  '/tools/sprite-recolor':                 '2026-08-22',
  '/ru/tools/sprite-recolor':              '2026-08-22',
  '/tools/aseprite-palette-converter':     '2026-08-22',
  '/ru/tools/aseprite-palette-converter':  '2026-08-22',
  '/palettes':                             '2026-08-22',
  '/ru/palettes':                          '2026-08-22',
  '/research/oklch-vs-hsl':                '2026-08-22',
  '/ru/research/oklch-vs-hsl':             '2026-08-22',
  '/research/text-to-color-benchmark':     '2026-08-22',
  '/ru/research/text-to-color-benchmark':  '2026-08-22',
  '/privacy':                              '2026-01-01',
  '/ru/privacy':                           '2026-01-01',
  '/terms':                                '2026-01-01',
};

function pageDate(path: string): string | undefined {
  return PAGE_DATES[path] ?? '2026-08-22';
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = 'https://oklchpalette.ru';

  // Static pages — lastModified reflects actual content update date, not build time
  const staticPages: MetadataRoute.Sitemap = [
    { url: `${base}/`,       priority: 1.0, lastModified: pageDate('/') },
    { url: `${base}/create`, priority: 0.95, lastModified: pageDate('/create') },
    { url: `${base}/explore`, priority: 0.85, lastModified: pageDate('/explore') },
    { url: `${base}/ru`,      priority: 0.95, lastModified: pageDate('/ru') },
    { url: `${base}/ru/create`, priority: 0.90, lastModified: pageDate('/ru/create') },
    { url: `${base}/ru/explore`, priority: 0.80, lastModified: pageDate('/ru/explore') },

    // Tools hub
    { url: `${base}/tools`, priority: 0.85, lastModified: pageDate('/tools') },
    { url: `${base}/ru/tools`, priority: 0.85, lastModified: pageDate('/ru/tools') },

    // Tool pages (EN)
    { url: `${base}/tools/pixel-art-palette-generator`, priority: 0.80, lastModified: pageDate('/tools/pixel-art-palette-generator') },
    { url: `${base}/tools/ai-color-palette-generator`, priority: 0.85, lastModified: pageDate('/tools/ai-color-palette-generator') },
    { url: `${base}/tools/palette-analyzer`, priority: 0.80, lastModified: pageDate('/tools/palette-analyzer') },
    { url: `${base}/tools/color-ramp-generator`, priority: 0.80, lastModified: pageDate('/tools/color-ramp-generator') },
    { url: `${base}/tools/image-to-palette`, priority: 0.80, lastModified: pageDate('/tools/image-to-palette') },
    { url: `${base}/tools/palette-compare`, priority: 0.75, lastModified: pageDate('/tools/palette-compare') },
    { url: `${base}/tools/lospec-palette-editor`, priority: 0.75, lastModified: pageDate('/tools/lospec-palette-editor') },
    { url: `${base}/tools/sprite-recolor`, priority: 0.80, lastModified: pageDate('/tools/sprite-recolor') },
    { url: `${base}/tools/aseprite-palette-converter`, priority: 0.80, lastModified: pageDate('/tools/aseprite-palette-converter') },

    // Tool pages (RU)
    { url: `${base}/ru/tools/ai-color-palette-generator`, priority: 0.85, lastModified: pageDate('/ru/tools/ai-color-palette-generator') },
    { url: `${base}/ru/tools/palette-analyzer`, priority: 0.80, lastModified: pageDate('/ru/tools/palette-analyzer') },
    { url: `${base}/ru/tools/color-ramp-generator`, priority: 0.80, lastModified: pageDate('/ru/tools/color-ramp-generator') },
    { url: `${base}/ru/tools/image-to-palette`, priority: 0.80, lastModified: pageDate('/ru/tools/image-to-palette') },
    { url: `${base}/ru/tools/palette-compare`, priority: 0.75, lastModified: pageDate('/ru/tools/palette-compare') },
    { url: `${base}/ru/tools/lospec-palette-editor`, priority: 0.75, lastModified: pageDate('/ru/tools/lospec-palette-editor') },
    { url: `${base}/ru/tools/sprite-recolor`, priority: 0.80, lastModified: pageDate('/ru/tools/sprite-recolor') },
    { url: `${base}/ru/tools/aseprite-palette-converter`, priority: 0.80, lastModified: pageDate('/ru/tools/aseprite-palette-converter') },

    // Curated palettes index
    { url: `${base}/palettes`, priority: 0.85, lastModified: pageDate('/palettes') },
    { url: `${base}/ru/palettes`, priority: 0.85, lastModified: pageDate('/ru/palettes') },

    // Curated individual palettes (EN & RU)
    ...CURATED_PALETTES.flatMap(p => [
      { url: `${base}/palettes/${p.slug}`, priority: 0.75, lastModified: '2026-08-22' },
      { url: `${base}/ru/palettes/${p.slug}`, priority: 0.75, lastModified: '2026-08-22' },
    ]),

    // Research pages
    { url: `${base}/research/oklch-vs-hsl`, priority: 0.75, lastModified: pageDate('/research/oklch-vs-hsl') },
    { url: `${base}/ru/research/oklch-vs-hsl`, priority: 0.75, lastModified: pageDate('/ru/research/oklch-vs-hsl') },
    { url: `${base}/research/text-to-color-benchmark`, priority: 0.75, lastModified: pageDate('/research/text-to-color-benchmark') },
    { url: `${base}/ru/research/text-to-color-benchmark`, priority: 0.75, lastModified: pageDate('/ru/research/text-to-color-benchmark') },

    // Guides (EN)
    { url: `${base}/guides/oklch-for-pixel-art`,  priority: 0.75, lastModified: pageDate('/guides/oklch-for-pixel-art') },
    { url: `${base}/guides/palette-file-formats`, priority: 0.70, lastModified: pageDate('/guides/palette-file-formats') },

    // Legal
    { url: `${base}/privacy`,    priority: 0.20, lastModified: pageDate('/privacy') },
    { url: `${base}/ru/privacy`, priority: 0.20, lastModified: pageDate('/ru/privacy') },
    { url: `${base}/terms`,      priority: 0.20, lastModified: pageDate('/terms') },
  ];

  /* eslint-disable @typescript-eslint/no-explicit-any */
  // Dynamic: public palettes and active profiles
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
            priority: 0.60,
            lastModified: p.updated_at,
          });
        }
      }

      // Profiles: only include users who have at least 1 public palette
      // This avoids indexing empty user pages as thin content
      const { data: profilesWithPalettes } = await (supabase as any)
        .from('palettes')
        .select('owner_id, profiles!owner_id(username, updated_at)')
        .eq('visibility', 'public')
        .limit(500);

      if (profilesWithPalettes) {
        const seen = new Set<string>();
        for (const row of (profilesWithPalettes as any[])) {
          const profile = Array.isArray(row.profiles) ? row.profiles[0] : row.profiles;
          if (!profile?.username || seen.has(profile.username)) continue;
          seen.add(profile.username);
          dynamicPages.push({
            url: `${base}/u/${profile.username}`,
            priority: 0.50,
            lastModified: profile.updated_at,
          });
        }
      }
    }
  } catch {
    // Sitemap builds without dynamic pages if Supabase is unavailable
  }

  return [...staticPages, ...dynamicPages];
}
