import type { Metadata } from 'next';
import Link from 'next/link';
import { Palette, Terminal, Globe } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Политика конфиденциальности | OKLCH Pixel Palette',
  description: 'Политика конфиденциальности сервиса OKLCH Pixel Palette — информация об обработке данных и защите приватности.',
  alternates: { canonical: 'https://oklchpalette.ru/ru/privacy' },
};

export default function RuPrivacyPage() {
  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white">
      <header className="border-b border-white/10 bg-zinc-950/80 h-14 flex items-center justify-between px-6">
        <Link href="/ru" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
            <Palette className="w-4 h-4" />
          </div>
          <span className="text-sm font-mono font-black text-white">OKLCH PIXEL PALETTE</span>
        </Link>
        <Link
          href="/privacy"
          className="flex items-center gap-1.5 text-xs font-mono text-gray-400 hover:text-white transition-colors bg-white/5 hover:bg-white/10 px-2.5 py-1 rounded-md border border-white/10"
        >
          <Globe className="w-3.5 h-3.5" />
          <span>English version</span>
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 space-y-8">
        <div>
          <h1 className="text-3xl font-mono font-extrabold text-white mb-2">Политика конфиденциальности</h1>
          <p className="text-xs text-gray-400 font-mono">Дата обновления: август 2026 г.</p>
        </div>

        <div className="prose prose-invert prose-sm max-w-none space-y-6 text-gray-300 font-sans text-sm leading-relaxed">
          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">1. Общие положения и минимизация данных</h2>
            <p>
              Сервис OKLCH Pixel Palette предоставляет инструменты для генерации, анализа и экспорта гармоничных цветовых палитр для пиксель-арта, игр и интерфейсов.
              Сайт функционирует в режиме максимальной минимизации сбора и обработки данных.
            </p>
            <p>
              <strong>Новая регистрация пользователей отключена.</strong> Все основные функциональные возможности сайта — включая создание и редактирование палитр, проверку шкалы светлоты, предпросмотр пиксель-арт спрайтов, экспорт карточек в формате PNG и файлов палитр (GPL, PAL, JSON, TXT, HEX), а также просмотр публичной галереи — доступны любому посетителю без необходимости регистрации или авторизации.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">2. Категории и порядок обработки данных</h2>
            <p>
              <strong>Обычные посетители (без учетной записи):</strong> Для использования сервиса не требуется указывать адрес электронной почты, пароль, имя или другие идентификационные данные. Рабочее состояние редактора палитр сохраняется исключительно на стороне вашего устройства в локальном хранилище браузера (<code className="text-purple-300 font-mono text-xs">localStorage</code>, ключ <code className="text-purple-300 font-mono text-xs">oklch_studio_state_v1</code>). Эти данные не передаются на наши серверы.
            </p>
            <p>
              <strong>Ранее зарегистрированные аккаунты:</strong> Учетные записи и публичные/сохраненные палитры, созданные до закрытия регистрации, сохраняются в базе данных Supabase. Владельцы существующих аккаунтов могут входить в систему, управлять ранее опубликованным контентом, обновлять профиль или полностью удалить свой аккаунт через раздел настроек (Settings).
            </p>
            <p>
              <strong>Статистика посещаемости:</strong> Сайт использует сервис <code className="text-purple-300 font-mono text-xs">@vercel/analytics</code> (Vercel Analytics) для сбора обобщённых показателей посещаемости (количество просмотров, уникальные посетители, популярные страницы, источники переходов, страна и тип устройства). Vercel Analytics не использует файлы cookie для отслеживания, не сохраняет персональные профили посетителей и не осуществляет трекинг между сторонними сайтами.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">3. Чего мы не делаем</h2>
            <ul className="list-disc list-inside space-y-1.5">
              <li>Мы не продаём и не передаём пользовательские данные третьим лицам.</li>
              <li>Мы не размещаем коммерческую рекламу и рекламные баннеры.</li>
              <li>Мы не используем рекламные трекеры и маркетинговые скрипты (Google Analytics, Яндекс Метрика, Facebook Pixel, PostHog, Sentry и др.).</li>
              <li>Мы не требуем регистрации для доступа к базовому функционалу сайта.</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">4. Сторонние инфраструктурные сервисы</h2>
            <p>Для обеспечения работы сайта задействованы следующие сервисы:</p>
            <ul className="list-disc list-inside space-y-1.5">
              <li><strong>Supabase:</strong> Облачная база данных (PostgreSQL) для хранения существующих профилей и опубликованных палитр.</li>
              <li><strong>Vercel:</strong> Хостинг веб-приложения и сбор обобщённой статистики посещений.</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">5. Сведения об операторе и контакты</h2>
            <p>
              <strong>Оператор сайта:</strong> Кулькин Иван Андреевич
            </p>
            <p>
              <strong>Электронная почта для обращений:</strong>{' '}
              <a href="mailto:ytivanioi510@gmail.com" className="text-purple-400 hover:text-purple-300 underline">
                ytivanioi510@gmail.com
              </a>
            </p>
            <p>
              По техническим вопросам и предложениям по работе сервиса вы также можете создать обращение в{' '}
              <a
                href="https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE"
                target="_blank"
                rel="noopener noreferrer"
                className="text-purple-400 hover:text-purple-300 underline"
              >
                GitHub-репозитории проекта
              </a>.
            </p>
          </section>
        </div>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center flex flex-col sm:flex-row items-center justify-center gap-3">
        <div className="flex items-center gap-1">
          <Terminal className="w-3.5 h-3.5 text-purple-400 inline" />
          <span>OKLCH Pixel Palette &copy; {new Date().getFullYear()}</span>
        </div>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link href="/ru/privacy" className="text-gray-400 hover:text-white transition-colors">
          Политика конфиденциальности
        </Link>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link href="/terms" className="text-gray-400 hover:text-white transition-colors">
          Условия
        </Link>
      </footer>
    </div>
  );
}
