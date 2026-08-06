/**
 * Triggers a browser download of a text string as a UTF-8 file.
 */
export function downloadTextFile(content: string, filename: string, mimeType: string = 'text/plain;charset=utf-8'): void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return;

  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
