import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'OKLCH Pixel Palette',
    short_name: 'OKLCH Palette',
    description:
      'Create, remix and export OKLCH color palettes for pixel art, games and interfaces.',
    start_url: '/',
    display: 'standalone',
    background_color: '#090909',
    theme_color: '#8b5cf6',
  };
}
