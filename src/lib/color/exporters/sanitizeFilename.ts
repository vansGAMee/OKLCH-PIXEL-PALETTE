/**
 * Sanitizes a string for use as a cross-platform safe filename.
 */
export function sanitizeFilename(name: string, fallback: string = 'oklch-palette'): string {
  if (!name || typeof name !== 'string') return fallback;
  const sanitized = name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9а-яё_-]/gi, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');

  return sanitized || fallback;
}
