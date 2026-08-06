# HANDOFF.md — OKLCH Pixel Palette 2.0 State & Transition Document

**Date:** 2026-08-07  
**Status:** Phase 0–9 Core Implementation Complete (Build & Tests Passing)

---

## 1. Что реализовано

### Phase 0 — Baseline & Documentation
- `docs/competitive-audit.md`: Сравнительный аудит (Lospec, Coolors, Adobe Color, Color Hunt, Huemint, Paletton) + 3 уникальных дифференциатора.
- `docs/adr/001-supabase-choice.md`: ADR решения по выбору Supabase (PostgreSQL + RLS + SSR).
- `docs/adr/002-local-first.md`: ADR локал-ферст архитектуры (localStorage приоритет, облако как опция).
- `src/types/palette.ts`: Расширен `HarmonyMode` (добавлены `triadic`, `tetradic`, `monochromatic`).
- `src/lib/color/harmony.ts`: Реализованы функции расчета кандидатных оттенков для новых гармоний.
- `src/components/controls/HarmonySelector.tsx`: Обновлена иконная карта гармоний.

### Phase 1 — Supabase Foundation & Database Schema
- `.env.example`: Шаблон переменных окружения (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`).
- `scripts/check-env.mjs`: Скрипт проверки переменных с безопасным фолбэком в демо-режим.
- `src/lib/supabase/client.ts`: Клиент браузера (`@supabase/ssr`).
- `src/lib/supabase/server.ts`: Клиент сервера (`cookies()`).
- `src/lib/supabase/admin.ts`: Service-role клиент для критичных операций (удаление аккаунта).
- `src/lib/supabase/types.ts`: TypeScript типы БД.
- `supabase/migrations/`:
  - `001_profiles.sql`: Таблица профилей пользователей, триггеры создания профиля и `updated_at`.
  - `002_palettes.sql`: Таблица палитр с JSONB, ограничениями длины и цвета, уникальным слотом `featured_position`.
  - `003_likes_bookmarks.sql`: Лайки и закладки.
  - `004_events.sql`: События пользовательского воркфлоу с вайтлистом событий.
  - `005_functions.sql`: SQL-функции и триггеры лимитов (макс. 30 сохранённых, макс. 3 публичных палитры).
- `SUPABASE_SETUP.md`: Подробное пошаговое руководство из 5 шагов для подключения Supabase.

### Phase 2 — Auth & Middleware
- `src/middleware.ts`: Обновление сессий Supabase SSR + защита маршрутов (`/dashboard`, `/settings`, `/onboarding`).
- `src/app/actions/auth.ts`: Server Actions (`signUp`, `signIn`, `signOut`, `checkUsername`, `setUsername`, `deleteAccount`).
- `src/app/login/page.tsx` + `/ru/login/page.tsx`: Формы входа с проверкой доступности Supabase.
- `src/app/signup/page.tsx` + `/ru/signup/page.tsx`: Формы регистрации.
- `src/app/auth/callback/route.ts` + `/ru/auth/callback/route.ts`: Callback-обработчики авторизации.

### Phase 3 — Cloud Saves & Dashboard
- `src/lib/palette/schema.ts`: Zod-схема валидации палитры (сервер + клиент).
- `src/lib/palette/serialize.ts` / `deserialize.ts`: Сериализация/десериализация палитр.
- `src/app/actions/palettes.ts`: Server Actions (`savePalette`, `updatePalette`, `deletePalette`, `featurePalette`).
- `src/app/dashboard/page.tsx` + `/ru/dashboard/page.tsx`: SSR дашборд пользователя.
- `src/components/dashboard/DashboardContent.tsx`, `LimitBar.tsx`, `PaletteCard.tsx`, `InsightsTab.tsx`.

### Phase 4 — Profiles & Publishing
- `src/app/u/[username]/page.tsx`: Публичный профиль автора с гридом палитр.
- `src/app/p/[slug]/page.tsx`: Детальная страница публичной палитры с OKLCH-свойствами, плашками цветов, BklitLightnessChart и кнопками действий.

### Phase 5 — Explore Gallery & Engagement
- `src/app/explore/page.tsx` + `/ru/explore/page.tsx`: Публичная галерея с пагинацией.
- `src/app/actions/likes.ts`: Server Actions для лайков и закладок.
- `src/components/gallery/ExploreContent.tsx`, `PaletteGalleryCard.tsx`.

### Phase 6 — Parsers & Quality Inspector
- `src/lib/import/parsers/`:
  - `parseGpl.ts`: Парсер GIMP Palette (`.gpl`).
  - `parsePal.ts`: Парсер JASC Paint Shop Pro (`.pal`).
  - `parseHex.ts`: Парсер списков HEX-кодов (`.txt`).
  - `parseJson.ts`: Парсер собственного JSON-формата палитр.
- `src/lib/color/qualityInspector.ts`: Инспектор качества палитр (дубликаты, близкие цвета по Delta E, узкий диапазон яркости, контраст WCAG, нейтральность).
- `src/components/quality/QualityInspector.tsx`: UI-панель инспектора качества.
- `src/lib/import/__tests__/parsers.test.ts`: 19 юнит-тестов для парсеров.
- `src/lib/color/__tests__/qualityInspector.test.ts`: 6 юнит-тестов инспектора качества.

### Phase 7 & 8 — Homepage & Insights
- `src/components/home/HomePageContent.tsx`: Обновлены ссылки в шапке и подвале (Explore, Guides, Generator, Privacy, Terms, GitHub).
- `src/app/actions/events.ts`: Функция трекинга воркфлоу-событий.
- `src/components/insights/WorkflowFunnel.tsx`: Легковесный SVG-воронка воркфлоу для Insights дашборда.

### Phase 9 — SEO & Content Pages
- `src/app/sitemap.ts`: Динамическая генерация sitemap (включает статьи, инструменты, публичные профили и палитры).
- `src/app/guides/oklch-for-pixel-art/page.tsx`: Гайд "OKLCH for Pixel Art".
- `src/app/guides/palette-file-formats/page.tsx`: Гайд по форматам файлов (.gpl, .pal, .txt, .json).
- `src/app/tools/pixel-art-palette-generator/page.tsx`: SEO-посадочная страница для ключевого запроса "pixel art palette generator".
- `src/app/privacy/page.tsx`: Политика конфиденциальности.
- `src/app/terms/page.tsx`: Условия использования.
- `.github/workflows/ci.yml`: GitHub Actions CI pipeline (lint, typecheck, test, build).

---

## 2. Что не завершено

1. **Кнопка Cloud Save в PaletteStudio.tsx**: Редактор `PaletteStudio.tsx` работает с `localStorage`. Для добавления интерактивной кнопки "Save to Cloud" прямо из редактора нужно интегрировать вызов `savePalette` из `src/app/actions/palettes.ts` в панели `ActionToolbar.tsx`.
2. **Экспорт данных и смена пароля в `/settings`**: Создать страницу `/settings` (и `/ru/settings`) с UI для смены пароля, редактирования профиля и вызова `deleteAccount`.
3. **Модальное окно импорта в PaletteStudio**: Подключить созданные парсеры (`parseGpl`, `parsePal`, `parseHex`, `parseJson`) к модальному окну загрузки файлов в редакторе.

---

## 3. Известные ошибки / предупреждения

- **Ошибок сборки нет** (`npm run build` проходит за ~1.6с, 29/29 страниц скомпилированы).
- **Тесты проходят на 100%** (83/83 тестов в 4 тест-файлах проходят).
- **TypeScript clean** (`npx tsc --noEmit` — 0 ошибок).
- **ESLint clean** (`npm run lint` — 0 ошибок, 6 варнингов на сторонних визуал-компонентах visx).
- **Next.js 16 Deprecation Warning**: `The "middleware" file convention is deprecated. Please use "proxy" instead.` (Стандартное предупреждение Next.js 16 Canary/RC).

---

## 4. Запускавшиеся команды

```bash
npm install @supabase/supabase-js @supabase/ssr zod
npx tsc --noEmit
npm run lint
npm run test
npm run build
```

---

## 5. Точный следующий шаг

1. **Подключить Supabase**: Следуйте 5 шагам из `SUPABASE_SETUP.md`:
   - Создать проект на https://supabase.com
   - Выполнить 5 SQL-миграций из `supabase/migrations/`
   - Добавить переменные в Vercel / `.env.local`
2. **Интегрировать Cloud Save в PaletteStudio**:
   - В `src/components/controls/ActionToolbar.tsx` добавить кнопку "Save to Cloud" (видимую при авторизованном сеансе), вызывающую `savePalette`.

---

## 6. Миграции и переменные Supabase

### Необходимые переменные окружения:
```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=eyJhb...
SUPABASE_SECRET_KEY=eyJhb...
```

### Порядок выполнения миграций в SQL Editor:
1. `supabase/migrations/001_profiles.sql`
2. `supabase/migrations/002_palettes.sql`
3. `supabase/migrations/003_likes_bookmarks.sql`
4. `supabase/migrations/004_events.sql`
5. `supabase/migrations/005_functions.sql`

---

## 7. Файлы, требующие проверки при следующем сеансе

- `SUPABASE_SETUP.md`
- `src/components/editor/PaletteStudio.tsx`
- `src/components/controls/ActionToolbar.tsx`
- `src/app/actions/palettes.ts`
- `src/app/actions/auth.ts`
- `src/lib/color/qualityInspector.ts`
