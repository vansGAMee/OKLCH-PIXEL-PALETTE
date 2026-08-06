-- Migration 003: likes and bookmarks
-- palette_likes
CREATE TABLE IF NOT EXISTS public.palette_likes (
  user_id    uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  palette_id uuid NOT NULL REFERENCES public.palettes(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, palette_id)
);

CREATE INDEX IF NOT EXISTS palette_likes_palette_idx ON public.palette_likes (palette_id);

ALTER TABLE public.palette_likes ENABLE ROW LEVEL SECURITY;

-- Users can read only their own like rows
CREATE POLICY "likes_own_select"
  ON public.palette_likes FOR SELECT
  USING (auth.uid() = user_id);

-- Public pages receive only the total number of likes, without user IDs
CREATE OR REPLACE FUNCTION public.get_palette_like_count(target_palette_id uuid)
RETURNS bigint
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT count(*)
  FROM public.palette_likes AS likes
  JOIN public.palettes AS palettes ON palettes.id = likes.palette_id
  WHERE likes.palette_id = target_palette_id
    AND palettes.visibility = 'public';
$$;

REVOKE ALL ON FUNCTION public.get_palette_like_count(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_palette_like_count(uuid) TO anon, authenticated;

-- Users manage only their own likes
CREATE POLICY "likes_authenticated_insert"
  ON public.palette_likes FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "likes_authenticated_delete"
  ON public.palette_likes FOR DELETE
  USING (auth.uid() = user_id);

-- palette_bookmarks (private — users see only their own)
CREATE TABLE IF NOT EXISTS public.palette_bookmarks (
  user_id    uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  palette_id uuid NOT NULL REFERENCES public.palettes(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, palette_id)
);

CREATE INDEX IF NOT EXISTS palette_bookmarks_user_idx ON public.palette_bookmarks (user_id);

ALTER TABLE public.palette_bookmarks ENABLE ROW LEVEL SECURITY;

-- Bookmarks are private — only owner sees their own
CREATE POLICY "bookmarks_own_select"
  ON public.palette_bookmarks FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "bookmarks_authenticated_insert"
  ON public.palette_bookmarks FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "bookmarks_authenticated_delete"
  ON public.palette_bookmarks FOR DELETE
  USING (auth.uid() = user_id);
