import type { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: 'https://oklchpalette.ru/',
      changeFrequency: 'weekly',
      priority: 1.0,
    },
    {
      url: 'https://oklchpalette.ru/create',
      changeFrequency: 'daily',
      priority: 0.9,
    },
  ];
}
