-- Migration 005: helper functions for palette limits
-- Returns TRUE if user has NOT reached the 30 saved palette limit
CREATE OR REPLACE FUNCTION public.check_saved_palette_limit(uid uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COUNT(*) < 30
  FROM public.palettes
  WHERE owner_id = uid;
$$;

-- Returns TRUE if user has NOT reached the 3 public palette limit
CREATE OR REPLACE FUNCTION public.check_public_palette_limit(uid uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COUNT(*) < 3
  FROM public.palettes
  WHERE owner_id = uid AND visibility = 'public';
$$;

-- Database-level limit enforcement via trigger
CREATE OR REPLACE FUNCTION public.enforce_palette_limits()
RETURNS trigger AS $$
BEGIN
  -- Check total saved limit (30 per user)
  IF NOT public.check_saved_palette_limit(NEW.owner_id) THEN
    RAISE EXCEPTION 'Palette limit reached: maximum 30 saved palettes per account.';
  END IF;

  -- Check public limit on insert or visibility change to 'public'
  IF NEW.visibility = 'public' THEN
    IF NOT public.check_public_palette_limit(NEW.owner_id) THEN
      RAISE EXCEPTION 'Public palette limit reached: maximum 3 public palettes per account.';
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Trigger for INSERT
CREATE TRIGGER palettes_enforce_limits_insert
  BEFORE INSERT ON public.palettes
  FOR EACH ROW EXECUTE PROCEDURE public.enforce_palette_limits();

-- Trigger for UPDATE (catches visibility changes to 'public')
CREATE OR REPLACE FUNCTION public.enforce_public_limit_on_update()
RETURNS trigger AS $$
BEGIN
  -- Only check if visibility is being changed TO 'public'
  IF NEW.visibility = 'public' AND OLD.visibility != 'public' THEN
    IF NOT public.check_public_palette_limit(NEW.owner_id) THEN
      RAISE EXCEPTION 'Public palette limit reached: maximum 3 public palettes per account.';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE TRIGGER palettes_enforce_limits_update
  BEFORE UPDATE ON public.palettes
  FOR EACH ROW EXECUTE PROCEDURE public.enforce_public_limit_on_update();
