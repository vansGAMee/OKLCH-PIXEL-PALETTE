import type { OklchColor } from '@/types/palette';

export const PALETTE_FEEDBACK_SCHEMA_VERSION = 1 as const;

export type PaletteFeedbackEventName =
  | 'like'
  | 'dislike'
  | 'export'
  | 'regenerate'
  | 'lock'
  | 'unlock'
  | 'candidate_selected';

export type PaletteFeedbackEvent = {
  schemaVersion: typeof PALETTE_FEEDBACK_SCHEMA_VERSION;
  event: PaletteFeedbackEventName;
  modelVersion: string;
  encoderVersion: string;
  palette: OklchColor[];
  requestedCount: number;
  seed?: number;
  candidateId?: string;
  promptRepresentation?: {
    kind: 'embedding_hash';
    value: string;
  };
  createdAt: string;
};

export type PaletteFeedbackEventInput = Omit<
  PaletteFeedbackEvent,
  'schemaVersion' | 'createdAt'
>;

export interface FeedbackTransport {
  send(events: readonly PaletteFeedbackEvent[]): Promise<void>;
}
