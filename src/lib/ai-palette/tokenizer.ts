/**
 * Text normalizer — must match Python normalize_text exactly.
 * NFKC → lowercase → trim → collapse whitespace
 */
export function normalizeText(text: string): string {
  return text
    .normalize('NFKC')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ');
}

/**
 * Paletta v1 tokenizer.
 * 0 = PAD, 1 = UNK
 * Uses Unicode code-point iteration (Array.from).
 * Vocab loaded from public/models/paletta-v1.vocab.json
 */
export class PalettaTokenizer {
  private vocab: Map<string, number>;
  readonly maxLength: number;
  static readonly PAD_ID = 0;
  static readonly UNK_ID = 1;

  constructor(vocab: Record<string, number>, maxLength = 96) {
    this.vocab = new Map(Object.entries(vocab));
    this.maxLength = maxLength;
  }

  tokenize(text: string): number[] {
    const normalized = normalizeText(text);
    const chars = Array.from(normalized).slice(0, this.maxLength);
    const ids = chars.map(ch => this.vocab.get(ch) ?? PalettaTokenizer.UNK_ID);
    // Pad
    while (ids.length < this.maxLength) {
      ids.push(PalettaTokenizer.PAD_ID);
    }
    return ids;
  }
}

/**
 * FNV-1a 32-bit hash for deterministic seed from prompt.
 * No external dependency.
 */
export function stablePromptHash(normalizedText: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < normalizedText.length; i++) {
    hash ^= normalizedText.charCodeAt(i);
    hash = (Math.imul(hash, 0x01000193) >>> 0);
  }
  // Map to non-negative 32-bit integer safe for seed use
  return hash >>> 0;
}
