import type { Metadata } from 'next';
import Link from 'next/link';
import { Palette, Terminal } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Privacy Policy | OKLCH Pixel Palette',
  description: 'Privacy policy for OKLCH Pixel Palette — a free color tool for pixel artists.',
  alternates: { canonical: 'https://oklchpalette.ru/privacy' },
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col">
      <header className="border-b border-white/10 bg-zinc-950/80 h-14 flex items-center px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400">
            <Palette className="w-4 h-4" />
          </div>
          <span className="text-sm font-mono font-black text-white">OKLCH PIXEL PALETTE</span>
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 space-y-8">
        <div>
          <h1 className="text-3xl font-mono font-extrabold text-white mb-2">Privacy Policy</h1>
          <p className="text-xs text-gray-400 font-mono">Last updated: August 2026</p>
        </div>

        <div className="prose prose-invert prose-sm max-w-none space-y-6 text-gray-300 font-sans text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-mono font-bold text-white">What we collect</h2>
            <p>
              <strong>Without an account:</strong> We collect no personal data. Your palette state is stored in your browser&apos;s localStorage and never sent to our servers.
            </p>
            <p>
              <strong>With an account (optional):</strong> We collect your email address and the username you choose during onboarding. Saved palettes are stored in our database.
            </p>
            <p>
              <strong>Analytics:</strong> We use Vercel Analytics, which collects anonymized page view data (no cookies, no fingerprinting, GDPR-compliant).
            </p>
          </section>

          <section>
            <h2 className="text-lg font-mono font-bold text-white">What we do not do</h2>
            <ul className="list-disc list-inside space-y-1">
              <li>We do not sell your data to anyone.</li>
              <li>We do not serve advertising.</li>
              <li>We do not use third-party tracking scripts (no Google Analytics, no Facebook Pixel).</li>
              <li>We do not collect your IP address or build behavioral profiles.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-mono font-bold text-white">Your data rights</h2>
            <p>If you have an account, you can export or permanently delete all your data from the Settings page. Deletion cascades — your account, palettes, likes, bookmarks, and all event logs are removed permanently.</p>
          </section>

          <section>
            <h2 className="text-lg font-mono font-bold text-white">Third-party services</h2>
            <p>We use Supabase (PostgreSQL) to store account data. Supabase is GDPR-compliant. Our servers are hosted in EU-West (Frankfurt) on Vercel&apos;s infrastructure.</p>
          </section>

          <section>
            <h2 className="text-lg font-mono font-bold text-white">Contact</h2>
            <p>Questions? Open an issue on our <a href="https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE" className="text-purple-400 hover:underline">GitHub repository</a>.</p>
          </section>
        </div>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center">
        <Terminal className="w-3.5 h-3.5 text-purple-400 inline mr-1" />
        OKLCH Pixel Palette &copy; {new Date().getFullYear()}
      </footer>
    </div>
  );
}
