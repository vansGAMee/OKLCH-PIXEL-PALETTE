# ADR 002 — Architecture: Local-First, Cloud as Optional Layer

**Date:** 2026-08  
**Status:** Accepted

## Context

OKLCH Pixel Palette is a free tool. Requiring sign-in to use it would destroy conversion. But cloud features (save, publish, share) add value.

## Decision

Local-first: the editor works 100% with localStorage, no account needed. Cloud is an optional additive layer.

## Rationale

- Guest can create, preview, export, share (via URL params) without auth
- After sign-in, user is offered (not forced) to import local palette to cloud
- localStorage key `pixel_palette_studio_state_v1` is permanent — never renamed without migration
- Cloud save requires explicit user action (Save button), with optional debounced autosave only after first cloud save

## Consequences

- Editor must not break if Supabase credentials are absent
- Account UI shows "unavailable" state gracefully, not broken buttons
- No localStorage data is deleted without confirmed cloud save
- Conflict resolution: `updated_at` timestamp wins; user is shown a diff dialog if needed
