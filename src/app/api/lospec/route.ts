import { NextRequest, NextResponse } from 'next/server';

/**
 * Server-side proxy for Lospec palette API.
 * Prevents CORS issues and adds attribution headers.
 * Only fetches from lospec.com/palette-list/*.json — no other URLs.
 */
export const runtime = 'nodejs';

const LOSPEC_SLUG_RE = /^[a-z0-9-]{1,80}$/;

export async function GET(req: NextRequest) {
  const slug = req.nextUrl.searchParams.get('slug')?.trim() ?? '';

  if (!slug || !LOSPEC_SLUG_RE.test(slug)) {
    return NextResponse.json(
      { error: 'Invalid slug. Slug must be 1–80 lowercase alphanumeric characters or hyphens.' },
      { status: 400 }
    );
  }

  const lospecUrl = `https://lospec.com/palette-list/${slug}.json`;

  try {
    const res = await fetch(lospecUrl, {
      headers: { 'User-Agent': 'oklchpalette.ru/1.0 (palette import tool; https://oklchpalette.ru)' },
      // 10-second timeout
      signal: AbortSignal.timeout(10_000),
    });

    if (res.status === 404) {
      return NextResponse.json({ error: 'Palette not found on Lospec.' }, { status: 404 });
    }

    if (!res.ok) {
      return NextResponse.json({ error: `Lospec returned HTTP ${res.status}.` }, { status: 502 });
    }

    const contentType = res.headers.get('content-type') ?? '';
    if (!contentType.includes('json')) {
      return NextResponse.json({ error: 'Unexpected response from Lospec.' }, { status: 502 });
    }

    const data = await res.json() as { name?: string; author?: string; colors?: string[] };

    if (!data.colors || !Array.isArray(data.colors)) {
      return NextResponse.json({ error: 'Lospec response missing colors field.' }, { status: 502 });
    }

    return NextResponse.json({
      name: data.name ?? slug,
      author: data.author ?? 'Unknown',
      colors: data.colors,
      lospecUrl: `https://lospec.com/palette-list/${slug}`,
      attribution: 'Unofficial import — palette by the author listed above. OKLCH Pixel Palette is not affiliated with Lospec.',
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes('timeout') || msg.includes('abort')) {
      return NextResponse.json({ error: 'Request to Lospec timed out.' }, { status: 504 });
    }
    return NextResponse.json({ error: 'Failed to fetch from Lospec.' }, { status: 502 });
  }
}
