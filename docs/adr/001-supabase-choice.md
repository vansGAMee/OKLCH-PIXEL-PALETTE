# ADR 001 — Backend: Supabase

**Date:** 2026-08  
**Status:** Accepted

## Context

OKLCH Pixel Palette needs cloud storage for user accounts, palettes, likes, and bookmarks. The stack is Next.js App Router on Vercel.

## Decision

Use Supabase: PostgreSQL + Auth + RLS + SSR integration.

## Rationale

- Vercel Integration available (auto-syncs env vars)
- `@supabase/ssr` provides secure cookie-based sessions for Next.js App Router
- Row Level Security at database level — not dependent on application code
- No Prisma: direct Supabase client keeps the stack minimal
- Free tier sufficient for launch traffic
- Migration files are plain SQL — no ORM lock-in

## Rejected Alternatives

- **PlanetScale + NextAuth:** Two separate services; RLS not built-in
- **Firebase:** NoSQL; harder to enforce relational constraints and limits
- **Neon + Lucia Auth:** More code to write; Supabase Auth is battle-tested

## Consequences

- Requires SUPABASE_SECRET_KEY server-side only — never in client bundle
- Application must handle missing credentials gracefully (demo mode)
- Migrations in `supabase/migrations/` — plain SQL, versioned
