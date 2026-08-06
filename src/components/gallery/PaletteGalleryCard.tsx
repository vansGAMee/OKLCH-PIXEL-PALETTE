/**
 * src/components/gallery/PaletteGalleryCard.tsx
 * Public gallery card — shows color strip, title, author, like count.
 */
import React from 'react';
import Link from 'next/link';

interface GalleryPalette {
  id: string;
  slug: string;
  title: string;
  color_count: number;
  harmony: string | null;
  colors: unknown;
  profiles: { username: string; display_name: string | null } | null;
}

interface Props {
  palette: GalleryPalette;
  locale: 'en' | 'ru';
}

export function PaletteGalleryCard({ palette, locale }: Props) {
  const colors = Array.isArray(palette.colors) ? palette.colors as Array<{ hex: string }> : [];
  const href = locale === 'ru' ? `/ru/p/${palette.slug}` : `/p/${palette.slug}`;

  return (
    <Link
      href={href}
      className="glass-panel rounded-xl border border-white/10 overflow-hidden group transition-all hover:border-purple-500/40 hover:shadow-lg hover:shadow-purple-900/20 focus:outline-none focus:ring-2 focus:ring-purple-500"
    >
      {/* Color Strip */}
      <div className="flex h-14">
        {colors.slice(0, 9).map((c, i) => (
          <div
            key={i}
            className="flex-1 group-hover:brightness-110 transition-all"
            style={{ backgroundColor: c.hex }}
          />
        ))}
      </div>

      {/* Card Body */}
      <div className="p-3 space-y-1.5">
        <h3 className="text-sm font-mono font-bold text-white truncate group-hover:text-purple-300 transition-colors">
          {palette.title}
        </h3>
        <div className="flex items-center justify-between text-[11px] font-mono text-gray-400">
          <span>@{palette.profiles?.username ?? '?'}</span>
          <span>{palette.color_count} {locale === 'ru' ? 'цветов' : 'colors'}</span>
        </div>
      </div>
    </Link>
  );
}
