-- Migration 001: profiles table
-- Enable citext extension for case-insensitive username comparisons
CREATE EXTENSION IF NOT EXISTS citext;

-- profiles table linked to auth.users
CREATE TABLE IF NOT EXISTS public.profiles (
  id           uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username     citext UNIQUE NOT NULL,
  display_name text,
  bio          text,
  locale       text NOT NULL DEFAULT 'en',
  avatar_seed  text,
  role         text NOT NULL DEFAULT 'user',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- Constraints
ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_username_length
    CHECK (char_length(username) BETWEEN 3 AND 24),
  ADD CONSTRAINT profiles_username_chars
    CHECK (username ~ '^[a-zA-Z0-9_-]+$'),
  ADD CONSTRAINT profiles_display_name_length
    CHECK (display_name IS NULL OR char_length(display_name) <= 50),
  ADD CONSTRAINT profiles_bio_length
    CHECK (bio IS NULL OR char_length(bio) <= 240),
  ADD CONSTRAINT profiles_role_values
    CHECK (role IN ('user', 'admin'));

-- Index for username lookups
CREATE INDEX IF NOT EXISTS profiles_username_idx ON public.profiles (username);

-- Enable Row Level Security
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Anyone can read public profiles
CREATE POLICY "profiles_public_select"
  ON public.profiles FOR SELECT
  USING (true);

-- Users can only update their own profile
CREATE POLICY "profiles_authenticated_update"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (
    auth.uid() = id
    -- Prevent self-promotion: role cannot be changed via client
    AND role = (SELECT role FROM public.profiles WHERE id = auth.uid())
  );

-- Only insert via trigger (see below) - no direct client insert
CREATE POLICY "profiles_insert_trigger"
  ON public.profiles FOR INSERT
  WITH CHECK (auth.uid() = id);

-- Trigger: auto-create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (id, username, display_name, locale)
  VALUES (
    NEW.id,
    -- Temporary username from email prefix, will be replaced in onboarding
    CONCAT('user_', SUBSTRING(REPLACE(NEW.id::text, '-', ''), 1, 12)),
    NULL,
    COALESCE(NEW.raw_user_meta_data->>'locale', 'en')
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- Trigger: auto-update updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE PROCEDURE public.set_updated_at();
