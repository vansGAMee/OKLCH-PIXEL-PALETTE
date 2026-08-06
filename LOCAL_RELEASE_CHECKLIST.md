# LOCAL_RELEASE_CHECKLIST.md — OKLCH Pixel Palette 2.0

Финальный чеклист локальной готовности продукта перед подключением Supabase и деплоем на Vercel.

---

## 1. Что уже готово и полностью реализовано локально

- [x] **Оптимизация производительности редактора (Editor Lag Fix):**
  - Удален тяжелый prop `layout` из `ColorCard.tsx`, устраняющий layout thrashing при движении курсора.
  - Все ключевые UI-компоненты (`ColorCard`, `PaletteGrid`, `BklitLightnessChart`, `PixelPreview`, `HarmonySelector`, `ActionToolbar`, `ColorPicker`, `QualityInspector`) обернуты в `React.memo`.
  - Запись в `localStorage` задебауншена на 400 мс (больше нет блокирующего дискового ввода-вывода на каждый кадр движения мыши).
  - События цвета сгруппированы через `requestAnimationFrame`.
- [x] **Встроенные модули в Palette Studio:**
  - Импорт палитр в форматах `.gpl` (GIMP), `.pal` (JASC), `.hex` / `.txt` и `.json` с предварительным просмотром плашек и отменой в модальном окне `ImportModal.tsx`.
  - Встроенный инспектор качества палитры `QualityInspector.tsx` (проверка дубликатов, близости цветов по Delta E, узкого диапазона яркости и WCAG контраста).
  - Кнопка "В облако" / "Cloud Save" со встроенным безопасным оповещением в гостевом демо-режиме.
- [x] **Страницы продукта и SEO:**
  - Маршруты `/`, `/create`, `/dashboard`, `/explore`, `/u/[username]`, `/p/[slug]`, `/privacy`, `/terms`, `/guides/...`, `/tools/...` полностью работоспособны.
  - Русская локализация для всех маршрутов (`/ru/...`).
  - Гарантированный честный демо-режим при отсутствии ключей Supabase.
- [x] **Автоматическое тестирование и сборка:**
  - `npm run test`: 83 из 83 тестов проходят.
  - `npx tsc --noEmit`: 0 ошибок типов.
  - `npm run lint`: 0 ошибок линтера.
  - `npm run build`: 29 страниц скомпилированы успешно.

---

## 2. Что проверено локально (Local Verification)

| Маршрут | Описание | Результат |
| :--- | :--- | :--- |
| `/` & `/ru` | Главная страница с промо OKLCH, особенностями и ссылками | 🟢 OK |
| `/create` & `/ru/create` | Студия редактора (выбор цвета, гармонии, seed, импорт, инспектор, экспорт) | 🟢 OK (без лагов) |
| `/dashboard` & `/ru/dashboard` | Панель управления (Сохранённые, Публичные, Профиль, Аналитика) | 🟢 OK (демо-режим) |
| `/explore` & `/ru/explore` | Галерея публичных палитр с пагинацией | 🟢 OK (демо-режим) |
| `/login` & `/signup` | Формы входа и регистрации | 🟢 OK (демо-режим) |
| `/privacy` & `/terms` | Страницы политики и условий | 🟢 OK |
| `/guides/...` | Обучающие статьи и SEO-посадочная | 🟢 OK |

---

## 3. Что требует подключения Supabase

1. Создание реальных учетных записей пользователей (Email/Password Auth).
2. Облачное сохранение до 30 приватных палитр на аккаунт.
3. Публикация до 3 палитр в общую галерею `/explore`.
4. Лайки и закладки палитр.
5. Персональная воронка воркфлоу на вкладке "Аналитика".

---

## 4. Что требует подключения Vercel

1. Деплой Next.js App Router с поддержкой SSR и Edge Middleware.
2. Автоматическая сборка при коммитах в ветку `main`.
3. Привязка домена `oklchpalette.ru`.

---

## 5. Точный порядок подключения (Инструкция к действию)

### Шаг 1: Подключение Supabase
1. Создайте проект на https://supabase.com.
2. Примените 5 SQL-файлов из `supabase/migrations/` в SQL Editor Supabase.
3. В **Authentication -> URL Configuration** задайте Site URL `http://localhost:3000` и добавьте Redirect URLs.
4. Скопируйте ключи API и создайте файл `.env.local` в корне проекта (см. [SUPABASE_SETUP.md](file:///home/ivan/ssss/SUPABASE_SETUP.md)).

### Шаг 2: Проверка с базой на Localhost
```bash
npm run dev
```
- Откройте `http://localhost:3000/signup`, зарегистрируйтесь, сохраните палитру в облако.

### Шаг 3: Деплой на Vercel
1. В Vercel Dashboard перейдите в **Settings -> Environment Variables**.
2. Добавьте:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SECRET_KEY`
3. Нажмите **Redeploy**.

---

## 6. Команды для финальной проверки перед запуском

```bash
# 1. Запуск тестов
npm run test

# 2. Проверка типов TypeScript
npx tsc --noEmit

# 3. Проверка правил ESLint
npm run lint

# 4. Продакшн сборка Next.js
npm run build

# 5. Запуск продакшн сервера локально
npm run start
```
