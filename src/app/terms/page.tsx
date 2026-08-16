import type { Metadata } from 'next';
import Link from 'next/link';
import { Palette, Terminal } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Terms of Use | OKLCH Pixel Palette',
  description: 'Terms of use for OKLCH Pixel Palette — a free color tool for pixel artists.',
  alternates: { canonical: 'https://oklchpalette.ru/terms' },
};

export default function TermsPage() {
  const year = new Date().getFullYear();
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
          <h1 className="text-3xl font-mono font-extrabold text-white mb-2">Terms of Use</h1>
          <p className="text-xs text-gray-400 font-mono">Last updated: August {year}</p>
        </div>

        <div className="space-y-6 text-gray-300 font-sans text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-mono font-bold text-white mb-2">Free to use</h2>
            <p>OKLCH Pixel Palette is free to use for any purpose — personal, commercial, or educational. No attribution required for palettes you create.</p>
          </section>

          <section>
            <h2 className="text-lg font-mono font-bold text-white mb-2">Your content</h2>
            <p>Palettes you create belong to you. When you publish a palette publicly, other users can view it, like it, and remix it (fork it into a new palette under their account). You keep ownership of your original.</p>
          </section>

          <section>
            <h2 className="text-lg font-mono font-bold text-white mb-2">What you must not do</h2>
            <ul className="list-disc list-inside space-y-1">
              <li>Publish content that is illegal, abusive, or violates third-party rights.</li>
              <li>Attempt to reverse-engineer, attack, or overload the service.</li>
              <li>Automate account creation or palette publishing.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-mono font-bold text-white mb-2">No warranty</h2>
            <p>This service is provided as-is. We make no guarantees about uptime or data retention. Back up important palettes locally using the export function.</p>
          </section>

          <section>
            <h2 className="text-lg font-mono font-bold text-white mb-2">Changes</h2>
            <p>We may update these terms. Continued use after updates constitutes acceptance. Material changes will be noted in our GitHub repository.</p>
          </section>
        </div>
      </main>

      <footer className="border-t border-white/10 py-6 text-xs font-mono text-gray-500 text-center flex flex-col sm:flex-row items-center justify-center gap-3">
        <div className="flex items-center gap-1">
          <Terminal className="w-3.5 h-3.5 text-purple-400 inline" />
          <span>OKLCH Pixel Palette &copy; {year}</span>
        </div>
        <span className="hidden sm:inline text-gray-700">·</span>
        <Link
          href="/privacy"
          className="text-gray-400 hover:text-white transition-colors underline-offset-4 hover:underline"
        >
          Privacy Policy
        </Link>
      </footer>
    </div>
  );
}
