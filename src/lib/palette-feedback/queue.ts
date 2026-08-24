import {
  PALETTE_FEEDBACK_SCHEMA_VERSION,
  type FeedbackTransport,
  type PaletteFeedbackEvent,
  type PaletteFeedbackEventInput,
} from './types';

const ENABLED_KEY = 'palettebrain.feedback.enabled.v1';
const QUEUE_KEY = 'palettebrain.feedback.queue.v1';
const MAX_QUEUE_SIZE = 100;
const BATCH_SIZE = 20;

type FeedbackStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

type QueueOptions = {
  storage?: FeedbackStorage;
  transport?: FeedbackTransport;
  now?: () => Date;
};

function readQueue(storage?: FeedbackStorage): PaletteFeedbackEvent[] {
  if (!storage) return [];

  try {
    const value = storage.getItem(QUEUE_KEY);
    if (!value) return [];
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (event): event is PaletteFeedbackEvent =>
        typeof event === 'object' &&
        event !== null &&
        (event as PaletteFeedbackEvent).schemaVersion === PALETTE_FEEDBACK_SCHEMA_VERSION,
    );
  } catch {
    return [];
  }
}

function writeQueue(storage: FeedbackStorage | undefined, events: PaletteFeedbackEvent[]): void {
  if (!storage) return;
  try {
    storage.setItem(QUEUE_KEY, JSON.stringify(events.slice(-MAX_QUEUE_SIZE)));
  } catch {
    // Feedback is best-effort and must never interrupt palette work.
  }
}

export class PaletteFeedbackQueue {
  private readonly storage?: FeedbackStorage;
  private readonly transport?: FeedbackTransport;
  private readonly now: () => Date;
  private flushing?: Promise<void>;

  constructor(options: QueueOptions = {}) {
    this.storage = options.storage;
    this.transport = options.transport;
    this.now = options.now ?? (() => new Date());
  }

  isEnabled(): boolean {
    try {
      return this.storage?.getItem(ENABLED_KEY) === 'true';
    } catch {
      return false;
    }
  }

  setEnabled(enabled: boolean): void {
    try {
      if (enabled) {
        this.storage?.setItem(ENABLED_KEY, 'true');
      } else {
        this.storage?.removeItem(ENABLED_KEY);
        this.storage?.removeItem(QUEUE_KEY);
      }
    } catch {
      // Privacy setting remains opt-in if storage is unavailable.
    }
  }

  enqueue(input: PaletteFeedbackEventInput): boolean {
    if (!this.isEnabled()) return false;

    const event: PaletteFeedbackEvent = {
      ...input,
      schemaVersion: PALETTE_FEEDBACK_SCHEMA_VERSION,
      palette: input.palette.map((color) => ({ ...color })),
      createdAt: this.now().toISOString(),
    };
    const queued = [...readQueue(this.storage), event].slice(-MAX_QUEUE_SIZE);
    writeQueue(this.storage, queued);

    if (this.transport) {
      queueMicrotask(() => void this.flush());
    }
    return true;
  }

  snapshot(): PaletteFeedbackEvent[] {
    return readQueue(this.storage).map((event) => ({
      ...event,
      palette: event.palette.map((color) => ({ ...color })),
    }));
  }

  flush(): Promise<void> {
    if (!this.transport || !this.isEnabled()) return Promise.resolve();
    if (this.flushing) return this.flushing;

    this.flushing = this.flushBatches().finally(() => {
      this.flushing = undefined;
    });
    return this.flushing;
  }

  private async flushBatches(): Promise<void> {
    while (this.isEnabled()) {
      const queued = readQueue(this.storage);
      if (queued.length === 0) return;

      const batch = queued.slice(0, BATCH_SIZE);
      try {
        await this.transport!.send(batch);
      } catch {
        return;
      }

      const latest = readQueue(this.storage);
      const remaining = latest.slice(batch.length);
      writeQueue(this.storage, remaining);
    }
  }
}

export function createHttpFeedbackTransport(endpoint: string): FeedbackTransport {
  return {
    async send(events) {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ schemaVersion: PALETTE_FEEDBACK_SCHEMA_VERSION, events }),
        credentials: 'omit',
        keepalive: true,
      });
      if (!response.ok) throw new Error(`Feedback endpoint returned ${response.status}`);
    },
  };
}

let browserQueue: PaletteFeedbackQueue | undefined;

export function getPaletteFeedbackQueue(): PaletteFeedbackQueue {
  if (browserQueue) return browserQueue;

  const storage = typeof window === 'undefined' ? undefined : window.localStorage;
  const endpoint = process.env.NEXT_PUBLIC_PALETTE_FEEDBACK_ENDPOINT?.trim();
  browserQueue = new PaletteFeedbackQueue({
    storage,
    transport: endpoint ? createHttpFeedbackTransport(endpoint) : undefined,
  });
  return browserQueue;
}

export function resetPaletteFeedbackQueueForTests(): void {
  browserQueue = undefined;
}
