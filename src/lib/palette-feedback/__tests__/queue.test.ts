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
});
