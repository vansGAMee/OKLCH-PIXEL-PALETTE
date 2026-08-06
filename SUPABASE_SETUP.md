# Пошаговое руководство: Подключение Supabase и Vercel к OKLCH Pixel Palette

Это подробная инструкция для человека без опыта. Следуйте шагам по очереди, чтобы запустить облачные функции (сохранение палитр, профили, лайки, аналитика) на localhost и на боевом домене.

---

## Часть 1. Создание проекта в Supabase

1. Перейдите на сайт **[https://supabase.com](https://supabase.com)**.
2. Нажмите **"Start your project"** или **"Sign In"** (можно войти через GitHub).
3. На главной панели нажмите **"New Project"**.
4. Заполните форму:
   - **Organization**: выберите свою личную организацию.
   - **Name**: введите `oklch-pixel-palette` (или любое понятное имя).
   - **Database Password**: придумайте надёжный пароль (или нажмите *Generate a password*). **Обязательно сохраните его в надежном месте!**
   - **Region**: выберите ближайший к вам регион (например, `Central Europe (Frankfurt)`).
   - **Pricing Plan**: выберите `Free Tier` ($0/mo).
5. Нажмите кнопку **"Create new project"**.
6. Подождите 1–2 минуты, пока подготовятся базы данных и сервисы авторизации.

---

## Часть 2. Применение SQL-миграций БД

### Вариант A — Через Supabase SQL Editor (Самый простой способ)

1. В левом меню Supabase нажмите на иконку **SQL Editor** (`>/`).
2. Нажмите **"New query"**.
3. По очереди откройте 5 SQL-файлов из папки проекта `supabase/migrations/`:
   - `001_profiles.sql`
   - `002_palettes.sql`
   - `003_likes_bookmarks.sql`
   - `004_events.sql`
   - `005_functions.sql`
4. Скопируйте содержимое файла `001_profiles.sql`, вставьте в SQL Editor и нажмите **"Run"** (или `Ctrl+Enter`).
5. Убедитесь, что внизу появилось сообщение `Success. No rows returned`.
6. Повторите шаг 4 для всех остальных файлов **строго по порядку**: `002`, `003`, `004`, `005`.

### Вариант B — Через Supabase CLI (Для разработчиков)

1. Установите Supabase CLI:
   ```bash
   npm install -g supabase
   ```
2. Авторизуйтесь в CLI:
   ```bash
   supabase login
   ```
3. Найдите ваш **Reference ID** проекта (в URL Supabase Dashboard: `https://supabase.com/dashboard/project/ВАШ_PROJECT_REF`).
4. Свяжите локальный проект с Supabase:
   ```bash
   supabase link --project-ref ВАШ_PROJECT_REF
   ```
5. Примените миграции:
   ```bash
   supabase db push
   ```
6. Сгенерируйте актуальные типы TypeScript:
   ```bash
   supabase gen types typescript --linked > src/lib/supabase/types.ts
   ```

---

## Часть 3. Настройка авторизации (Auth)

1. В левом меню Supabase перейдите в **Authentication** -> **URL Configuration**.
2. В поле **Site URL** укажите ваш локальный адрес (или боевой, если уже запустили на Vercel):
   ```text
   http://localhost:3000
   ```
3. В разделе **Redirect URLs** нажмите **"Add URL"** и добавьте следующие ссылки:
   - `http://localhost:3000/auth/callback`
   - `http://localhost:3000/ru/auth/callback`
   - `https://oklchpalette.ru/auth/callback`
   - `https://oklchpalette.ru/ru/auth/callback`
4. Перейдите в **Authentication** -> **Providers** -> **Email**:
   - Убедитесь, что **Enable Email provider** включен.
   - Для удобства разработки можно временно выключить **Confirm email** (чтобы входить сразу без подтверждения по почте).

---

## Часть 4. Переменные окружения для localhost (`.env.local`)

1. В Supabase перейдите в **Project Settings** (иконка шестеренки внизу) -> **API Keys**.
2. Найдите 3 значения:
   - **Project URL** (начинается с `https://...supabase.co`)
   - **Publishable Key / anon key** (начинается с `eyJ...`)
   - **Secret Key / service_role key** (начинается с `eyJ...`)
3. В корне вашего локального репозитория создайте файл `.env.local` и вставьте данные по шаблону:

```env
# Supabase URL & Public Anon Key (доступны на клиенте)
NEXT_PUBLIC_SUPABASE_URL=https://ВАШ_PROJECT_ID.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=eyJhbGciOiJIUzI1NiIsIn...

# Supabase Service Role Key (СТРОГО СЕКРЕТНО — только для сервера!)
SUPABASE_SECRET_KEY=eyJhbGciOiJIUzI1NiIsIn...
```

> ⚠️ **ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ О БЕЗОПАСНОСТИ:**
> - Ни в коем случае **не публикуйте** `SUPABASE_SECRET_KEY` в репозитории Git!
> - Файл `.env.local` автоматически внесен в `.gitignore`.
> - Не добавляйте префикс `NEXT_PUBLIC_` к `SUPABASE_SECRET_KEY`, иначе ключ утекёт в браузер пользователей.

---

## Часть 5. Проверка работы на localhost

1. Запустите проект локально:
   ```bash
   npm run dev
   ```
2. Откройте в браузере: `http://localhost:3000`.
3. Сценарий проверки:
   - Перейдите на `/signup` и создайте тестовый аккаунт.
   - Убедитесь, что система перенаправила вас на шаг установки username (`/onboarding`).
   - Задайте имя пользователя (например, `pixelartist`).
   - Перейдите на `/create`, измените палитру и нажмите **"В облако"** / **"Cloud Save"**.
   - Перейдите в `/dashboard` — ваша палитра должна отобразиться в списке "Сохранённые".
   - Переключите видимость палитры на `public`.
   - Перейдите в `/explore` — палитра должна быть видна в галерее.
   - Выйдите из аккаунта (`Log Out`) и проверьте, что приватные страницы направляют на форму входа.

---

## Часть 6. Подключение Vercel

1. Перейдите в **[Vercel Dashboard](https://vercel.com/dashboard)**.
2. Выберите ваш проект `oklch-pixel-palette`.
3. Перейдите в **Settings** -> **Environment Variables**.
4. Добавьте по очереди 3 переменные:
   - `NEXT_PUBLIC_SUPABASE_URL` = `https://ВАШ_PROJECT_ID.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` = `eyJ...`
   - `SUPABASE_SECRET_KEY` = `eyJ...`
   *(Установите галочки для Production, Preview и Development)*.
5. Перейдите во вкладку **Deployments** и нажмите **"Redeploy"** на последнем коммите, чтобы Vercel подтянул новые переменные.

### Альтернатива: Интеграция Vercel + Supabase
В Vercel Dashboard перейдите в **Integrations** -> найдите **Supabase** и нажмите **Connect**. Переменные свяжутся автоматически.

---

## Часть 7. Боевые URL для авторизации (Production)

Убедитесь, что в Supabase -> **Authentication** -> **URL Configuration** добавлены:
- **Site URL**: `https://oklchpalette.ru`
- **Redirect URLs**:
  - `https://oklchpalette.ru/auth/callback`
  - `https://oklchpalette.ru/ru/auth/callback`

---

## Часть 8. Финальный чеклист готовности

- [ ] Все 5 SQL-миграций выполнены без ошибок.
- [ ] Таблицы `profiles`, `palettes`, `palette_likes`, `palette_bookmarks`, `palette_events` созданы.
- [ ] Row Level Security (RLS) включен на всех таблицах.
- [ ] Переменные окружения добавлены в `.env.local` локально.
- [ ] Регистрация и вход работают на `http://localhost:3000`.
- [ ] Палитра сохраняется в облако и показывается в `/dashboard`.
- [ ] Публичные палитры видны в `/explore` и на `/p/[slug]`.
- [ ] Переменные добавлены в Vercel Dashboard.
- [ ] `SUPABASE_SECRET_KEY` не имеет префикса `NEXT_PUBLIC_`.

---

## Часть 9. Частые ошибки и их решения

### 1. `Invalid API key` или `Supabase client error`
- **Причина:** Неверно скопирован `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` или утеряны символы.
- **Решение:** Скопируйте ключ заново из Project Settings -> API Keys.

### 2. `Redirect mismatch` при входе или подтверждении почты
- **Причина:** Ссылка редиректа отсутствует в **Redirect URLs** в панеле Supabase Auth.
- **Решение:** Добавьте точный URL (с портом `3000` для localhost) в Authentication -> URL Configuration.

### 3. Пользователь создан, но профиль отсутствует (`relation profiles does not exist` / `profile missing`)
- **Причина:** Не была выполнена миграция `001_profiles.sql` или триггер `on_auth_user_created` не сработал.
- **Решение:** Выполните скрипт `001_profiles.sql` в SQL Editor заново.

### 4. Ошибка `row-level security policy violation`
- **Причина:** Пользователь пытается изменить чужую палитру или записать данные без авторизованной сессии.
- **Решение:** Проверьте, авторизован ли пользователь через `supabase.auth.getUser()`.

### 5. `Build works locally, but fails on Vercel`
- **Причина:** Забыли добавить переменные окружения в Vercel Settings -> Environment Variables.
- **Решение:** Добавьте ключи в Vercel и сделайте `Redeploy`.

### 6. Переменные добавлены в Vercel, но сайт их не видит
- **Причина:** Vercel считывает переменные только во время сборки (`build time`).
- **Решение:** Нажмите **Redeploy** во вкладке Deployments.

### 7. Бесконечный редирект на `/login`
- **Причина:** В браузер куки сессии блокируются или не передается заголовок Cookie в Server Actions.
- **Решение:** Очистите куки браузера для домена и войдите заново.
