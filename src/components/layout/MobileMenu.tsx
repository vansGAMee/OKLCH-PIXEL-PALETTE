'use client';
/**
 * src/components/layout/MobileMenu.tsx
 * Hamburger menu for mobile — works without knowing auth state.
 * Auth-aware version: shows login or dashboard based on what links are passed.
 */
import React, { useState } from 'react';
import Link from 'next/link';
import { Menu, X } from 'lucide-react';

interface MobileMenuProps {
  locale: 'en' | 'ru';
  isAuthenticated?: boolean;
}

export function MobileMenu({ locale, isAuthenticated = false }: MobileMenuProps) {
  const [open, setOpen] = useState(false);
  const isRu = locale === 'ru';

  const prefix = isRu ? '/ru' : '';

  const guestLinks = [
    { href: `${prefix}/explore`, label: isRu ? 'Галерея' : 'Explore' },
    { href: `${prefix}/login`, label: isRu ? 'Войти' : 'Sign in' },
    { href: `${prefix}/create`, label: isRu ? 'Редактор' : 'Studio' },
  ];

  const authLinks = [
    { href: `${prefix}/dashboard`, label: isRu ? 'Дашборд' : 'Dashboard' },
    { href: `${prefix}/explore`, label: isRu ? 'Галерея' : 'Explore' },
    { href: `${prefix}/create`, label: isRu ? 'Редактор' : 'Studio' },
    { href: `${prefix}/settings`, label: isRu ? 'Настройки' : 'Settings' },
  ];

  const links = isAuthenticated ? authLinks : guestLinks;

  return (
    <div className="sm:hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="p-2 text-gray-300 hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg"
        aria-label={open ? 'Close menu' : 'Open menu'}
      >
        {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {open && (
        <div className="absolute top-16 left-0 right-0 z-50 border-b border-white/10 bg-zinc-950/95 backdrop-blur-md shadow-xl">
          <nav className="max-w-7xl mx-auto px-4 py-4 flex flex-col gap-1">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="px-4 py-3 text-sm font-mono text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-all"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </div>
  );
}
