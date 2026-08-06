-- Migration 002: palettes table
CREATE TABLE IF NOT EXISTS public.palettes (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id          uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  slug              text UNIQUE NOT NULL,
  title             text NOT NULL,
  description       text,
  colors            jsonb NOT NULL,
  color_count       smallint NOT NULL,
  base_hex          text,
  harmony           text,
  seed              integer,
  tags              text[],
  visibility        text NOT NULL DEFAULT 'private',
  featured_position smallint,
  source_palette_id uuid REFERENCES public.palettes(id) ON DELETE SET NULL,
  remix_settings    jsonb,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  published_at      timestamptz
);

-- Constraints
ALTER TABLE public.palettes
  ADD CONSTRAINT palettes_title_length
    CHECK (char_length(title) BETWEEN 1 AND 80),
  ADD CONSTRAINT palettes_description_length
    CHECK (description IS NULL OR char_length(description) <= 500),
  ADD CONSTRAINT palettes_color_count_range
    CHECK (color_count BETWEEN 2 AND 9),
  ADD CONSTRAINT palettes_visibility_values
    CHECK (visibility IN ('private', 'unlisted', 'public')),
  ADD CONSTRAINT palettes_featured_position_values
    CHECK (featured_position IS NULL OR featured_position IN (1, 2, 3)),
  ADD CONSTRAINT palettes_tags_max
    CHECK (tags IS NULL OR array_length(tags, 1) <= 8),
  ADD CONSTRAINT palettes_slug_chars
    CHECK (slug ~ '^[a-z0-9-]+$' AND char_length(slug) BETWEEN 3 AND 80),
  -- Enforce color_count matches actual colors array length
  ADD CONSTRAINT palettes_color_count_matches
    CHECK (jsonb_array_length(colors) = color_count);

-- One featured_position per user (unique partial index)
CREATE UNIQUE INDEX IF NOT EXISTS palettes_featured_unique
  ON public.palettes (owner_id, featured_position)
  WHERE featured_position IS NOT NULL;

-- Performance indexes
CREATE INDEX IF NOT EXISTS palettes_owner_idx ON public.palettes (owner_id);
CREATE INDEX IF NOT EXISTS palettes_visibility_idx ON public.palettes (visibility);
CREATE INDEX IF NOT EXISTS palettes_published_at_idx ON public.palettes (published_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS palettes_slug_idx ON public.palettes (slug);

-- Enable RLS
ALTER TABLE public.palettes ENABLE ROW LEVEL SECURITY;

-- RLS: public can see only public palettes
CREATE POLICY "palettes_public_select"
  ON public.palettes FOR SELECT
  USING (visibility = 'public');

-- RLS: authenticated users see their own palettes (any visibility)
CREATE POLICY "palettes_own_select"
  ON public.palettes FOR SELECT
  USING (auth.uid() = owner_id);

-- RLS: authenticated insert — owner_id must match session user
CREATE POLICY "palettes_authenticated_insert"
  ON public.palettes FOR INSERT
  WITH CHECK (
    auth.uid() = owner_id
    AND auth.uid() IS NOT NULL
  );

-- RLS: authenticated update — only own palettes, cannot change owner_id
CREATE POLICY "palettes_authenticated_update"
  ON public.palettes FOR UPDATE
  USING (auth.uid() = owner_id)
  WITH CHECK (auth.uid() = owner_id);

-- RLS: authenticated delete — only own palettes
CREATE POLICY "palettes_authenticated_delete"
  ON public.palettes FOR DELETE
  USING (auth.uid() = owner_id);

-- updated_at trigger
CREATE TRIGGER palettes_updated_at
  BEFORE UPDATE ON public.palettes
  FOR EACH ROW EXECUTE PROCEDURE public.set_updated_at();
