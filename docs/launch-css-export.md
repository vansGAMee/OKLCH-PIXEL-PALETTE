# DTF

## Заголовок

Я добавил экспорт палитр OKLCH прямо в CSS — с HEX-фолбэком для старых браузеров

## Лид

Бесплатный генератор OKLCH Pixel Palette теперь выдаёт готовый `.css`, который можно сразу положить в проект. Внутри — обычные HEX-цвета для совместимости и нативные OKLCH-значения для современных браузеров.

## Текст

Когда я делал OKLCH Pixel Palette, инструмент сначала был ориентирован на пиксель-арт: выбрал базовый цвет, получил от двух до девяти оттенков, проверил светлоту на графике и выгрузил палитру в Aseprite или GIMP. Но часть людей использовала генератор для интерфейсов. Им всё равно приходилось вручную переносить цвета в CSS.

Теперь это отдельный пункт в меню Export.

Генератор скачивает обычный `.css` с предсказуемыми именами переменных:

```css
:root {
  --palette-1-shadow: #160067;
  --palette-2-base: #5B21B6;
  --palette-3-highlight: #AB7CE1;
  --palette-4-accent: #4DCD49;
}

@supports (color: oklch(50% 0 0)) {
  :root {
    --palette-1-shadow: oklch(25.12% 0.1510 280.34);
    --palette-2-base: oklch(43.22% 0.1960 293.54);
    --palette-3-highlight: oklch(67.40% 0.1180 301.12);
    --palette-4-accent: oklch(74.82% 0.1880 142.28);
  }
}
```

Почему не оставить только OKLCH? Значение внутри CSS custom property может сохраниться даже в браузере, который ещё не умеет отображать такой цвет. Ошибка проявится позже, когда переменная попадёт в `color` или `background`. Поэтому сначала записывается безопасный HEX, а OKLCH переопределяет его только внутри `@supports`.

Так файл можно использовать сразу:

```css
.button {
  color: var(--palette-3-highlight);
  background: var(--palette-2-base);
  border-color: var(--palette-4-accent);
}
```

### Что ещё умеет генератор

- создаёт палитры из 2–9 цветов;
- поддерживает complementary, split-complementary, analogous, triadic, tetradic и monochromatic гармонии;
- подгоняет цвета под sRGB, чтобы экспорт не отличался от предпросмотра;
- показывает ступени светлоты OKLCH и предупреждает о слабом контрасте;
- примеряет цвета к небольшим пиксельным сценам;
- экспортирует PNG, GIMP GPL, JASC PAL для Aseprite, HEX, TXT и JSON;
- работает без аккаунта, а текущая палитра хранится в браузере.

Заодно я поправил страницу форматов и sitemap: из карты сайта удалён несуществующий URL, а CSS получил отдельное описание с примером. Это небольшая правка, но поисковику больше не предлагают индексировать 404.

Попробовать: https://oklchpalette.ru/create

Руководство по форматам: https://oklchpalette.ru/guides/palette-file-formats

Исходный код: https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE

Интересно, какой экспорт добавить следующим: Tailwind theme, Sass map или Godot resource?

# Product Hunt launch update

## Tagline

Perceptual pixel palettes, now exported as production CSS

## Description

OKLCH Pixel Palette is a free, browser-local palette generator for pixel artists and UI developers. Build 2–9 color ramps, inspect perceptual lightness, preview sprites, and export production-ready CSS variables with universal HEX fallbacks and native OKLCH overrides. Artist workflows are covered too: Aseprite PAL, GIMP GPL, HEX, JSON, TXT, and PNG. No account required.

## Maker comment

I built OKLCH Pixel Palette because ordinary RGB interpolation often gives pixel-art ramps muddy midtones and uneven jumps in perceived brightness.

The newest release closes the gap between palette exploration and real web code. Export now downloads a ready-to-use `.css` file: HEX custom properties first, then native OKLCH overrides inside `@supports`. That detail matters because putting an unsupported color function directly inside a custom property does not create a reliable fallback.

The rest stays intentionally local and free: 2–9 colors, six harmony modes, sRGB gamut fitting, lightness inspection, sprite previews, plus PAL, GPL, HEX, JSON, TXT, and PNG exports. I would especially value feedback from pixel artists and design-system developers about the next format to support.

# DEV Community

## Title

Why OKLCH CSS variables need `@supports` for a real fallback

## Body

I added CSS export to an OKLCH palette generator this week. The obvious output looked like this:

```css
:root {
  --brand: #5b21b6;
  --brand: oklch(43.22% 0.196 293.54);
}
```

It looks like ordinary progressive enhancement: older browsers ignore the second declaration and keep the HEX value. That assumption is unreliable for custom properties.

## The failure happens when the variable is used

A custom property accepts almost any token sequence. A browser can preserve `oklch(...)` as the value of `--brand` even if it cannot use that function as a color. The second declaration therefore replaces the first one.

The browser only discovers the unsupported color when the variable reaches a typed property:

```css
.button {
  background: var(--brand);
}
```

At that point the declaration can become invalid. The HEX line did not survive as a fallback because both declarations set the same untyped custom property.

## Put the override behind a feature query

The exported file now separates the universal values from the modern override:

```css
:root {
  --palette-1-shadow: #160067;
  --palette-2-base: #5b21b6;
  --palette-3-highlight: #ab7ce1;
  --palette-4-accent: #4dcd49;
}

@supports (color: oklch(50% 0 0)) {
  :root {
    --palette-1-shadow: oklch(25.12% 0.151 280.34);
    --palette-2-base: oklch(43.22% 0.196 293.54);
    --palette-3-highlight: oklch(67.4% 0.118 301.12);
    --palette-4-accent: oklch(74.82% 0.188 142.28);
  }
}
```

Browsers without OKLCH support keep the sRGB values. Browsers that pass the feature query receive the perceptual values. Consumers do not need to know which path was selected:

```css
.button {
  color: var(--palette-3-highlight);
  background: var(--palette-2-base);
  border-color: var(--palette-4-accent);
}
```

The variable names include both order and role. The numeric prefix keeps them unique when a larger generated palette contains two colors with similar human-readable names.

## Why export both formats?

OKLCH is useful when a palette needs controlled lightness steps. That matters in UI states and in small sprites where two colors with different RGB values can still look almost identical. HEX remains the practical compatibility layer and accurately represents the generator's sRGB-fitted output.

The generator handles the rest of the workflow in the browser: 2–9 colors, six harmony modes, sRGB gamut fitting, lightness inspection, sprite previews, and exports for Aseprite PAL, GIMP GPL, HEX, JSON, TXT, PNG, and now CSS. It requires no account.

Try the CSS export: https://oklchpalette.ru/create

Source: https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE

The next candidates are Tailwind theme output, a Sass map, and a Godot resource. I would be interested to know which one would remove the most manual work from your workflow.
