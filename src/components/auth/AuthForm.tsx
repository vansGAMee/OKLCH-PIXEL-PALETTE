'use client';
/**
 * src/components/auth/AuthForm.tsx
 * Reusable auth form wrapper with dark pixel-tech aesthetic.
 */
import React from 'react';
import Link from 'next/link';
import { Palette, Terminal } from 'lucide-react';

interface AuthFormProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footerContent?: React.ReactNode;
  locale?: 'en' | 'ru';
}

export function AuthForm({ title, subtitle, children, footerContent, locale = 'en' }: AuthFormProps) {
  const homeHref = locale === 'ru' ? '/ru' : '/';

  return (
    <div className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col selection:bg-purple-600 selection:text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-zinc-950/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center">
          <Link
            href={homeHref}
            className="flex items-center gap-2.5 group focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg p-1"
          >
            <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400">
              <Palette className="w-4 h-4" />
            </div>
            <span className="text-sm font-mono font-black tracking-tight text-white">
              OKLCH PIXEL PALETTE
            </span>
          </Link>
        </div>
      </header>

      {/* Form Area */}
      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md space-y-6">
          {/* Card */}
          <div className="glass-panel rounded-2xl border border-white/10 p-8 space-y-6">
            {/* Title */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 mb-3">
                <Terminal className="w-4 h-4 text-purple-400" />
                <span className="text-[10px] font-mono text-purple-400 tracking-widest uppercase">
                  OKLCH Pixel Palette
                </span>
              </div>
              <h1 className="text-2xl font-mono font-extrabold text-white tracking-tight">
                {title}
              </h1>
              {subtitle && (
                <p className="text-xs text-gray-400 font-sans">
                  {subtitle}
                </p>
              )}
            </div>

            {/* Form Content */}
            {children}
          </div>

          {/* Footer Links */}
          {footerContent && (
            <div className="text-center text-xs font-mono text-gray-400">
              {footerContent}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
