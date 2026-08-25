import { describe, expect, it, vi } from 'vitest';
import { PaletteFeedbackQueue } from '../queue';
import type { FeedbackTransport, PaletteFeedbackEventInput } from '../types';

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }
}

const sample: PaletteFeedbackEventInput = {
  event: 'like',
  modelVersion: 'palettebrain-v2-test',
  encoderVersion: 'multilingual-e5-small-q8',
  palette: [{ l: 0.5, c: 0.1, h: 220 }],
  requestedCount: 2,
  seed: 42,
};

describe('PaletteFeedbackQueue', () => {
  it('collects nothing before explicit opt-in', () => {
    const queue = new PaletteFeedbackQueue({ storage: new MemoryStorage() });
    expect(queue.enqueue(sample)).toBe(false);
    expect(queue.snapshot()).toEqual([]);
  });

  it('stores a versioned anonymous event after opt-in and clears on opt-out', () => {
    const queue = new PaletteFeedbackQueue({
      storage: new MemoryStorage(),
      now: () => new Date('2026-08-24T00:00:00.000Z'),
    });
    queue.setEnabled(true);

    expect(queue.enqueue(sample)).toBe(true);
    expect(queue.snapshot()).toEqual([
      expect.objectContaining({
        schemaVersion: 1,
        event: 'like',
        createdAt: '2026-08-24T00:00:00.000Z',
      }),
    ]);

    queue.setEnabled(false);
    expect(queue.snapshot()).toEqual([]);
  });

  it('keeps failed batches queued and never throws from enqueue', async () => {
    const storage = new MemoryStorage();
    const send = vi.fn(async () => {
      throw new Error('offline');
    });
    const transport: FeedbackTransport = { send };
    const queue = new PaletteFeedbackQueue({ storage, transport });
    queue.setEnabled(true);
    queue.enqueue(sample);

    await queue.flush();

    expect(send).toHaveBeenCalledOnce();
    expect(queue.snapshot()).toHaveLength(1);
  });

  it('stores and validates a full 384-d embedding for future Bobby Fischer training', () => {
    const queue = new PaletteFeedbackQueue({
      storage: new MemoryStorage(),
      now: () => new Date('2026-08-25T12:00:00.000Z'),
    });
    queue.setEnabled(true);

    const fullEmbedding = Array.from({ length: 384 }, (_, i) => Math.sin(i) * 0.1);
    const richInput: PaletteFeedbackEventInput = {
      event: 'export',
      modelVersion: 'palettebrain-v3-candidate7',
      modelHash: 'bb52e9d9cde2bd2c80b3b8407f83f3400141e713022e0ddd5efbc684f7b63083',
      encoderVersion: 'multilingual-e5-small',
      encoderHash: 'f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193',
      palette: [{ l: 0.6, c: 0.2, h: 25 }],
      editedPalette: [{ l: 0.55, c: 0.22, h: 28 }],
      requestedCount: 5,
      seed: 42,
      locks: [0],
      groupId: 'session-group-123',
      rating: 5,
      promptRepresentation: {
        kind: 'embedding',
        value: fullEmbedding,
      },
    };

    expect(queue.enqueue(richInput)).toBe(true);
    const snapshot = queue.snapshot();
    expect(snapshot).toHaveLength(1);
    expect(snapshot[0].promptRepresentation).toEqual({
      kind: 'embedding',
      value: fullEmbedding,
    });
    expect(snapshot[0].editedPalette).toEqual([{ l: 0.55, c: 0.22, h: 28 }]);
    expect(snapshot[0].locks).toEqual([0]);
    expect(snapshot[0].groupId).toBe('session-group-123');

    // Rejects invalid embedding dimensions
    const badInput: PaletteFeedbackEventInput = {
      ...richInput,
      promptRepresentation: {
        kind: 'embedding',
        value: [0.1, 0.2], // only 2 elements instead of 384
      },
    };
    expect(queue.enqueue(badInput)).toBe(false);
  });
});
