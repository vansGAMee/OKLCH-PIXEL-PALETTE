/**
 * Mulberry32 PRNG for deterministic variations based on seed.
 */
export function createPrng(seed: number): () => number {
  let s = Math.floor(seed) || 12345;
  return function () {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
