-- Migration 004: palette_events (user analytics funnel)
CREATE TABLE IF NOT EXISTS public.palette_events (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id       uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  palette_id    uuid REFERENCES public.palettes(id) ON DELETE SET NULL,
  event_name    text NOT NULL,
  export_format text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Whitelist allowed event names
ALTER TABLE public.palette_events
  ADD CONSTRAINT events_event_name_whitelist
    CHECK (event_name IN (
      'palette_generated',
      'palette_saved',
      'palette_published',
      'palette_remixed',
      'palette_exported'
    ));

-- Index for dashboard queries
CREATE INDEX IF NOT EXISTS palette_events_user_idx ON public.palette_events (user_id, created_at DESC);

-- Enable RLS
ALTER TABLE public.palette_events ENABLE ROW LEVEL SECURITY;

-- Users insert and read only their own events
-- Cannot forge user_id — WITH CHECK enforces auth.uid()
CREATE POLICY "events_own_insert"
  ON public.palette_events FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "events_own_select"
  ON public.palette_events FOR SELECT
  USING (auth.uid() = user_id);

-- Retention: events older than 1 year can be deleted
-- (Cron job or manual cleanup — documented, not automated here)
-- COMMENT: retention_days = 365
