# Competitive Audit — OKLCH Pixel Palette

Date: 2026-08

---

## 1. Lospec Palette List

**URL:** https://lospec.com/palette-list

**Audience:** Pixel artists, retro game developers

**Strengths:**
- Largest curated pixel art palette database
- Community-driven with tags, likes, downloads
- GPL and PNG download for every palette
- Filter by color count, tag, palette type

**Weaknesses:**
- No palette generator — browse only
- No perceptual color analysis
- No lightness ladder or gamut check
- No OKLCH support
- Limited export formats (PNG, GPL, HEX)

**Save/Publish:** User-uploaded palettes, public by default
**Export:** PNG, GPL, HEX list, PAINT.NET
**Pixel Art Support:** ✅ strong (purpose-built)
**Perceptual Color:** ❌ none
**SEO:** Strong — individual palette pages indexed, good keyword density
**Mobile UX:** Good — responsive grid, filters work on touch

---

## 2. Coolors

**URL:** https://coolors.co

**Audience:** UI designers, branding, general creators

**Strengths:**
- Beautiful, polished product
- Fast palette generation with spacebar
- Wide export formats (CSS, SVG, PDF, PNG, URL share)
- Image color extraction
- Accessibility contrast checker
- Large community gallery

**Weaknesses:**
- HSL/HEX based — no OKLCH or perceptual lightness
- No pixel art preview or game-specific workflow
- Palette files (GPL, PAL) behind paywall
- Free tier has limits on saves
- No lightness analysis beyond generic gradient display

**Save/Publish:** Account required for cloud save; public gallery available
**Export:** URL, PNG, SVG, PDF, CSS, SCSS, HEX (GPL/PAL are Pro)
**Pixel Art Support:** ❌ none
**Perceptual Color:** ❌ none (uses HSL)
**SEO:** Excellent — thousands of indexed palette pages
**Mobile UX:** Good

---

## 3. Adobe Color

**URL:** https://color.adobe.com

**Audience:** Adobe ecosystem users, graphic designers

**Strengths:**
- HSL/LAB color harmony rules
- Accessibility checker with WCAG contrast
- Integration with Adobe apps
- Trend exploration from community

**Weaknesses:**
- Requires Adobe account
- No OKLCH or perceptual lightness
- No pixel art workflow
- No GPL/PAL export
- Heavy, slow, Adobe-ecosystem-locked

**Save/Publish:** Adobe account required
**Export:** ASE, ACO, CSS (basic)
**Pixel Art Support:** ❌ none
**Perceptual Color:** Partial (LAB available but not highlighted)
**SEO:** Moderate — blocked by auth wall
**Mobile UX:** Poor

---

## 4. Color Hunt

**URL:** https://colorhunt.co

**Audience:** Designers, general audience

**Strengths:**
- Extremely simple — 4-color palettes only
- Fast browsing, likes, curation
- Large volume

**Weaknesses:**
- Fixed 4 colors only
- No generator
- No analysis, no export formats
- No pixel art workflow
- Minimal SEO per page

**Save/Publish:** Community upload, always public
**Export:** PNG strip, code copy
**Pixel Art Support:** ❌ none
**Perceptual Color:** ❌ none
**SEO:** Weak per-palette pages
**Mobile UX:** Good

---

## 5. Huemint

**URL:** https://huemint.com

**Audience:** UI designers, branding

**Strengths:**
- Machine learning palette generation
- Context-aware (website, logo, illustration)
- Unique visual output

**Weaknesses:**
- Black box ML — no control over individual colors
- Slow, requires API call for each generation
- No pixel art workflow
- No gamut protection
- No file export (GPL, PAL, etc.)
- No lightness analysis

**Save/Publish:** URL share only
**Export:** HEX codes copy
**Pixel Art Support:** ❌ none
**Perceptual Color:** ❌ none (outputs HEX)
**SEO:** Minimal
**Mobile UX:** Limited

---

## 6. Paletton

**URL:** https://paletton.com

**Audience:** Web designers, traditional color theory users

**Strengths:**
- Fine-grained color harmony wheel
- Multiple harmony modes
- Long-established, trusted

**Weaknesses:**
- HSV/RGB based — no OKLCH or perceptual lightness
- Outdated UI
- No pixel art preview
- No file export (GPL, PAL)
- No cloud save or community

**Save/Publish:** URL parameter share
**Export:** XML, tables (no pixel art formats)
**Pixel Art Support:** ❌ none
**Perceptual Color:** ❌ none
**SEO:** Low
**Mobile UX:** Poor (desktop-first design from ~2010)

---

## 3 Provable Differentiators of OKLCH Pixel Palette

### 1. OKLCH Perceptual Lightness Analysis
No competitor offers a Lightness Ladder — a sorted visualization of palette entries by perceptual OKLCH lightness (L 0→1). Competitors use HSL or RGB, where perceived brightness is uneven. OKLCH Pixel Palette exposes lightness values numerically and visually, letting pixel artists verify contrast before drawing.

### 2. Native Pixel Art Workflow
Only Lospec serves pixel artists — and it's a browse-only catalog with no generator. OKLCH Pixel Palette uniquely combines: OKLCH generator → perceptual analysis → live pixel art preview (Potion, Gem, Shield, Hero, Full Palette) → artist-format export (GPL, JASC PAL, HEX, PNG card) in one tool.

### 3. Artist Export + Gamut Protection in One Tool
Coolors locks GPL/PAL behind a paywall. Adobe Color has no pixel art exports. OKLCH Pixel Palette provides all major pixel art file formats free, with sRGB gamut protection and Delta E deduplication guaranteeing the colors are valid before export — a combination no competitor offers.
