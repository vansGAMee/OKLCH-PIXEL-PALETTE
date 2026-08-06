# SUPABASE_SETUP.md — 5 Actions to Activate Cloud Features

The OKLCH Pixel Palette editor works without Supabase.  
Complete these 5 steps to enable accounts, cloud saves, and gallery.

---

## Action 1 — Create a Supabase Project

1. Go to https://supabase.com/dashboard
2. Click **New Project**
3. Name: `oklch-pixel-palette` (or any name)
4. Region: closest to `Frankfurt` (EU West) for oklchpalette.ru
5. Save your password somewhere safe

---

## Action 2 — Run Migrations

In the Supabase Dashboard → **SQL Editor**, run these files **in order**:

```
supabase/migrations/001_profiles.sql
supabase/migrations/002_palettes.sql
supabase/migrations/003_likes_bookmarks.sql
supabase/migrations/004_events.sql
supabase/migrations/005_functions.sql
```

Copy each file's contents and click **Run**.

---

## Action 3 — Configure Auth

In **Authentication → URL Configuration**:

- **Site URL:** `https://oklchpalette.ru`
- **Redirect URLs** (add all three):
  ```
  https://oklchpalette.ru/auth/callback
  https://oklchpalette.ru/ru/auth/callback
  http://localhost:3000/auth/callback
  ```

In **Authentication → Email Templates**:
- Set `Confirm signup` redirect to: `{{ .SiteURL }}/auth/callback?type=signup`
- Set `Recovery` redirect to: `{{ .SiteURL }}/auth/callback?type=recovery`

---

## Action 4 — Add Environment Variables to Vercel

In Vercel project → **Settings → Environment Variables**, add:

| Variable | Value | Where to find |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxxx.supabase.co` | Project Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `eyJhb...` (anon key) | Project Settings → API → anon/public |
| `SUPABASE_SECRET_KEY` | `eyJhb...` (service_role key) | Project Settings → API → service_role |

⚠️ **Never commit SUPABASE_SECRET_KEY to Git. It is server-side only.**

For local development, copy `.env.example` to `.env.local` and fill in values.

---

## Action 5 — Redeploy

After adding env vars:
```
git commit --allow-empty -m "chore: trigger redeploy after supabase setup"
git push origin main
```

Vercel will auto-deploy. Verify at:
- https://oklchpalette.ru/login (should show auth form)
- https://oklchpalette.ru/dashboard (should require login)

---

## Verification

After setup, test:
1. Sign up at `/signup`
2. Complete onboarding (choose username)
3. Open `/create` → save palette → check `/dashboard`
4. Publish palette → verify it appears on `/explore`

---

## Optional: SMTP for Email Delivery

By default, Supabase uses its own email service (limited to 2 emails/hour).

For production email: **Authentication → SMTP Settings** → add your SMTP provider.

Without custom SMTP:
- Email confirmation is disabled (configured in code)
- Password reset will work but may be slow

Supabase recommends: Resend, SendGrid, Postmark.
