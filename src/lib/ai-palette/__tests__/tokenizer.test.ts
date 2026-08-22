/**
 * Tokenizer tests — verifies RU/EN/normalization/parity.
 */
import { describe, it, expect } from 'vitest';
import { PalettaTokenizer, normalizeText, stablePromptHash } from '../tokenizer';

// Minimal vocab for testing — built with same logic as Python build_vocab()
const BASE_CHARS =
  'abcdefghijklmnopqrstuvwxyz' +
  'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' +
  '0123456789' +
  ' -_.,!?\'\"()';

function buildVocab(): Record<string, number> {
  const vocab: Record<string, number> = {};
  let idx = 2;
  for (const ch of BASE_CHARS) {
    if (!(ch in vocab)) {
      vocab[ch] = idx++;
    }
  }
  return vocab;
}

const VOCAB = buildVocab();
const tokenizer = new PalettaTokenizer(VOCAB, 96);

describe('normalizeText', () => {
  it('lowercases English', () => {
    expect(normalizeText('Winter Forest')).toBe('winter forest');
  });

  it('NFKC normalizes', () => {
    // Full-width character → ASCII
    const fw = '\uFF57\uFF49\uFF4E\uFF54\uFF45\uFF52'; // 'ｗｉｎｔｅｒ'
    expect(normalizeText(fw)).toBe('winter');
  });

  it('collapses multiple spaces', () => {
    expect(normalizeText('NEON   CYBERPUNK   RAIN')).toBe('neon cyberpunk rain');
  });

  it('trims leading/trailing whitespace', () => {
    expect(normalizeText('  forest  ')).toBe('forest');
  });

  it('lowercases Russian', () => {
    expect(normalizeText('Зимний лес')).toBe('зимний лес');
  });
});

describe('PalettaTokenizer', () => {
  it('pads to maxLength=96', () => {
    const ids = tokenizer.tokenize('hi');
    expect(ids).toHaveLength(96);
    // Last elements should be PAD=0
    expect(ids[95]).toBe(0);
    expect(ids[2]).toBe(0); // 'h','i' then pad
  });

  it('truncates to 96 code points', () => {
    const long = 'a'.repeat(200);
    const ids = tokenizer.tokenize(long);
    expect(ids).toHaveLength(96);
    expect(ids.every(id => id > 0)).toBe(true); // no padding needed
  });

  it('unknown characters map to UNK=1', () => {
    // Emoji not in vocab
    const ids = tokenizer.tokenize('🌲');
    expect(ids[0]).toBe(1); // UNK
  });

  it('English: consistent IDs for known chars', () => {
    const ids = tokenizer.tokenize('winter');
    // 'w', 'i', 'n', 't', 'e', 'r' all in vocab
    expect(ids.slice(0, 6).every(id => id > 1)).toBe(true);
  });

  it('Russian: consistent IDs for known chars', () => {
    const ids = tokenizer.tokenize('зима');
    // з, и, м, а all in vocab
    expect(ids.slice(0, 4).every(id => id > 1)).toBe(true);
  });

  it('parity fixture: "winter" normalized correctly', () => {
    const norm = normalizeText('winter starry forest');
    expect(norm).toBe('winter starry forest');
  });

  it('parity fixture: "зимний звездный лес" normalized correctly', () => {
    const norm = normalizeText('зимний звездный лес');
    expect(norm).toBe('зимний звездный лес');
  });

  it('parity fixture: NEON CYBERPUNK RAIN collapses to single spaces', () => {
    const norm = normalizeText('NEON   CYBERPUNK   RAIN');
    expect(norm).toBe('neon cyberpunk rain');
  });

  it('PAD_ID is 0, UNK_ID is 1', () => {
    expect(PalettaTokenizer.PAD_ID).toBe(0);
    expect(PalettaTokenizer.UNK_ID).toBe(1);
  });
});

describe('stablePromptHash', () => {
  it('is deterministic', () => {
    const h1 = stablePromptHash('winter starry forest');
    const h2 = stablePromptHash('winter starry forest');
    expect(h1).toBe(h2);
  });

  it('different prompts produce different hashes', () => {
    const h1 = stablePromptHash('winter starry forest');
    const h2 = stablePromptHash('neon cyberpunk rain');
    expect(h1).not.toBe(h2);
  });

  it('produces a non-negative integer', () => {
    const h = stablePromptHash('test');
    expect(h).toBeGreaterThanOrEqual(0);
    expect(Number.isInteger(h)).toBe(true);
  });
});
