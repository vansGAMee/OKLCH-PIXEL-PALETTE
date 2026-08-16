import type { Metadata } from 'next';
import Link from 'next/link';
import { Palette, Terminal, Globe } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Privacy Policy | OKLCH Pixel Palette',
  description: 'Privacy policy for OKLCH Pixel Palette — transparent details on data handling and privacy.',
  alternates: { canonical: 'https://oklchpalette.ru/privacy' },
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white">
      <header className="border-b border-white/10 bg-zinc-950/80 h-14 flex items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
            <Palette className="w-4 h-4" />
          </div>
          <span className="text-sm font-mono font-black text-white">OKLCH PIXEL PALETTE</span>
        </Link>
        <Link
          href="/ru/privacy"
          className="flex items-center gap-1.5 text-xs font-mono text-gray-400 hover:text-white transition-colors bg-white/5 hover:bg-white/10 px-2.5 py-1 rounded-md border border-white/10"
        >
          <Globe className="w-3.5 h-3.5" />
          <span>Русская версия</span>
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 space-y-8">
        <div>
          <h1 className="text-3xl font-mono font-extrabold text-white mb-2">Privacy Policy</h1>
          <p className="text-xs text-gray-400 font-mono">Last updated: August 2026</p>
        </div>

        <div className="prose prose-invert prose-sm max-w-none space-y-6 text-gray-300 font-sans text-sm leading-relaxed">
          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">1. Data Minimization & Service Overview</h2>
            <p>
              OKLCH Pixel Palette is a web application for creating, inspecting, and exporting color palettes for pixel art, games, and user interfaces.
              Our platform operates on a data-minimization principle.
            </p>
            <p>
              <strong>New user registration is permanently disabled.</strong> The core features of the website — including palette generation, lightness analysis, pixel art sprite previews, export to PNG cards and palette formats (GPL, PAL, JSON, TXT, HEX), and exploring public palettes — are available to all visitors without any registration or account creation.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">2. What Data Is Processed</h2>
            <p>
              <strong>Website Visitors:</strong> We do not collect or request your name, email address, password, or any other identifying personal details. When you use the OKLCH Palette Studio editor, your working parameters (e.g., base color, harmony, color count) are stored locally on your device in your browser&apos;s <code className="text-purple-300 font-mono text-xs">localStorage</code> (<code className="text-purple-300 font-mono text-xs">oklch_studio_state_v1</code>). This data remains on your computer and is not transmitted to our servers.
            </p>
            <p>
              <strong>Public Palettes:</strong> Supabase database infrastructure is used solely to store publicly available palettes and color schemes.
            </p>
            <p>
              <strong>Aggregated Traffic Analytics:</strong> We use <code className="text-purple-300 font-mono text-xs">@vercel/analytics</code> (Vercel Analytics) to collect anonymous, aggregated website traffic statistics (such as total page views, visitor counts, popular pages, referring sources, country of origin, and device types). Vercel Web Analytics operates without cookies; visitor identification relies on a temporary one-way hash that is not stored longer than 24 hours, does not collect personal identifiers, and does not track users across external websites.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">3. What We Do Not Do</h2>
            <ul className="list-disc list-inside space-y-1.5">
              <li>We do not sell user data. Data may be processed by third-party infrastructure providers necessary for the operation of the website, including Supabase and Vercel.</li>
              <li>We do not display commercial advertising or banners.</li>
              <li>We do not use advertising trackers or cross-site behavioral tracking scripts (no Google Analytics, no Yandex Metrika, no Facebook Pixel, no PostHog, no Sentry).</li>
              <li>We do not require visitors to provide personal information to access public palettes and color tools.</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">4. Third-Party Services</h2>
            <p>The platform relies on the following infrastructure providers:</p>
            <ul className="list-disc list-inside space-y-1.5">
              <li><strong>Supabase:</strong> Cloud database infrastructure used for storing public palette records.</li>
              <li><strong>Vercel:</strong> Web hosting and aggregated traffic analytics.</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-mono font-bold text-white">5. Operator Information & Inquiries</h2>
            <p>
              <strong>Website Operator:</strong> Kulkin Ivan Andreevich
            </p>
            <p>
              <strong>Email:</strong>{' '}
              <a href="mailto:ytivanioi510@gmail.com" className="text-purple-400 hover:text-purple-300 underline">
                ytivanioi510@gmail.com
              </a>
            </p>
            <p>
              If you have any technical questions or inquiries regarding the service, you can also open an issue on our{' '}
              <a
                href="https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE"
                target="_blank"
                rel="noopener noreferrer"
                className="text-purple-400 hover:text-purple-300 underline"
              >
                GitHub repository
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
        <Link href="/privacy" className="text-gray-400 hover:text-white transition-colors">
          Privacy Policy
        </Link>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link href="/terms" className="text-gray-400 hover:text-white transition-colors">
          Terms
        </Link>
      </footer>
    </div>
  );
}
