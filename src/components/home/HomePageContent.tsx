import React from 'react';
import Link from 'next/link';
import { Palette, Sparkles, Sliders, Eye, BarChart2, ShieldCheck, Download, ChevronRight, Terminal } from 'lucide-react';
import { LanguageSwitcher } from '@/components/i18n/LanguageSwitcher';
import { MobileMenu } from '@/components/layout/MobileMenu';
import { Locale, messages } from '@/i18n/messages';

interface HomePageContentProps {
  locale?: Locale;
  isAuthenticated?: boolean;
}

export function HomePageContent({ locale = 'en', isAuthenticated = false }: HomePageContentProps) {
  const currentYear = new Date().getFullYear();
  const t = messages[locale];
  const createHref = locale === 'ru' ? '/ru/create' : '/create';
  const homeHref = locale === 'ru' ? '/ru' : '/';
  const canonicalUrl = locale === 'ru' ? 'https://oklchpalette.ru/ru' : 'https://oklchpalette.ru/';

  const websiteJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'OKLCH Pixel Palette',
    alternateName: locale === 'ru' ? 'Генератор палитр OKLCH' : 'OKLCH Palette',
    url: canonicalUrl,
  };

  const softwareJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'OKLCH Pixel Palette',
    url: canonicalUrl,
    applicationCategory: 'DesignApplication',
    operatingSystem: 'Any',
    description: t.hero.subtitle,
    featureList: [
      'OKLCH Perceptual Color Palette Generator',
      'Local In-Browser AI Text-to-Palette Generation',
      'Lightness Ladder & Perceptual Contrast Analysis',
      'Pixel Art Sprite Previews',
      'sRGB Gamut Protection',
      'PNG, CSS, GPL, JASC PAL & JSON Export',
    ],
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
  };

  return (
    <div
      lang={locale}
      className="min-h-screen bg-[#090909] text-[#f7f9fa] flex flex-col justify-between selection:bg-purple-600 selection:text-white"
    >
      {/* Structured Data (JSON-LD) */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
      />

      {/* Navigation Header */}
      <header className="sticky top-0 z-50 border-b border-white/10 glass-panel backdrop-blur-md bg-zinc-950/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link
            href={homeHref}
            className="flex items-center gap-3 group focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg p-1"
          >
            <div className="w-9 h-9 rounded-xl bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 shadow-lg shadow-purple-900/20 group-hover:scale-105 transition-transform">
              <Palette className="w-5 h-5" />
            </div>
            <span className="text-sm sm:text-base font-mono font-black tracking-tight text-white">
              {t.header.title}
            </span>
          </Link>

          <nav aria-label="Main Navigation" className="flex items-center gap-3 sm:gap-6">
            <LanguageSwitcher currentLocale={locale} />

            <a
              href="#features"
              className="text-xs font-mono text-gray-300 hover:text-white transition-colors hidden sm:block focus:outline-none focus:ring-2 focus:ring-purple-500 rounded px-2 py-1"
            >
              {t.header.features}
            </a>
            <Link
              href={locale === 'ru' ? '/ru/explore' : '/explore'}
              className="text-xs font-mono text-gray-300 hover:text-white transition-colors hidden sm:block focus:outline-none focus:ring-2 focus:ring-purple-500 rounded px-2 py-1"
            >
              {locale === 'ru' ? 'Галерея' : 'Explore'}
            </Link>
            {isAuthenticated ? (
              <Link
                href={locale === 'ru' ? '/ru/dashboard' : '/dashboard'}
                className="text-xs font-mono text-gray-300 hover:text-white transition-colors hidden sm:block focus:outline-none focus:ring-2 focus:ring-purple-500 rounded px-2 py-1"
              >
                {locale === 'ru' ? 'Дашборд' : 'Dashboard'}
              </Link>
            ) : (
              <Link
                href={locale === 'ru' ? '/ru/login' : '/login'}
                className="text-xs font-mono text-gray-300 hover:text-white transition-colors hidden sm:block focus:outline-none focus:ring-2 focus:ring-purple-500 rounded px-2 py-1"
              >
                {locale === 'ru' ? 'Войти' : 'Sign in'}
              </Link>
            )}
            <Link
              href={createHref}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all shadow-md shadow-purple-900/30 focus:outline-none focus:ring-2 focus:ring-purple-400"
            >
              <span className="hidden sm:inline">{t.header.openStudio}</span>
              <span className="sm:hidden">Studio</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
            <MobileMenu locale={locale} isAuthenticated={isAuthenticated} />
          </nav>

        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex-1 w-full space-y-20">
        {/* Hero Section */}
        <section aria-labelledby="hero-heading" className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              <span>{t.hero.badge}</span>
            </div>

            <h1
              id="hero-heading"
              className="text-3xl sm:text-4xl lg:text-5xl font-mono font-extrabold tracking-tight text-white leading-tight"
            >
              {t.hero.title}
            </h1>

            <p className="text-sm sm:text-base text-gray-300 font-sans leading-relaxed max-w-2xl">
              {t.hero.subtitle}
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-2">
              <Link
                href={createHref}
                className="px-6 py-3 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/40 flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-purple-400"
              >
                <span>{t.hero.primaryCta}</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
              <a
                href="#features"
                className="px-6 py-3 text-sm font-mono text-gray-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-white/10 rounded-xl transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {t.hero.secondaryCta}
              </a>
            </div>
          </div>

          {/* Hero Static Showcase Card Grid (HTML/CSS, accessible to crawlers) */}
          <div className="lg:col-span-5">
            <div className="glass-panel p-6 rounded-2xl border border-white/10 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <span className="text-xs font-mono font-bold tracking-widest text-purple-400 uppercase">
                  {t.hero.showcaseTitle}
                </span>
                <span className="text-[10px] font-mono text-gray-400">sRGB Guarded</span>
              </div>

              {/* Static Palette Swatches Grid */}
              <div className="grid grid-cols-7 gap-2">
                {[
                  { hex: '#1e1b4b', role: 'SHADOW', l: '0.18' },
                  { hex: '#311b92', role: 'DARK', l: '0.30' },
                  { hex: '#5b21b6', role: 'BASE', l: '0.45' },
                  { hex: '#7c3aed', role: 'MID', l: '0.58' },
                  { hex: '#a855f7', role: 'HIGHLIGHT', l: '0.70' },
                  { hex: '#c084fc', role: 'LIGHT', l: '0.82' },
                  { hex: '#f43f5e', role: 'ACCENT', l: '0.65' },
                ].map((item, idx) => (
                  <div key={idx} className="flex flex-col gap-1.5">
                    <div
                      className="h-24 rounded-lg border border-white/15 shadow-inner"
                      style={{ backgroundColor: item.hex }}
                    />
                    <span className="text-[9px] font-mono text-gray-400 text-center font-bold">
                      {item.role}
                    </span>
                    <span className="text-[9px] font-mono text-purple-300 text-center">
                      {item.hex}
                    </span>
                  </div>
                ))}
              </div>

              <div className="pt-2 flex items-center justify-between text-[11px] font-mono text-gray-400">
                <span>{t.hero.harmonyLabel}</span>
                <span className="text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> {t.hero.minDeltaE}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" aria-labelledby="features-heading" className="space-y-8">
          <div className="space-y-2">
            <h2 id="features-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
              {t.features.heading}
            </h2>
            <p className="text-sm text-gray-400 font-sans">
              {t.features.subtitle}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Sliders className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">{t.features.card1Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.features.card1Desc}
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Palette className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">{t.features.card2Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.features.card2Desc}
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Eye className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">{t.features.card3Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.features.card3Desc}
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <BarChart2 className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">{t.features.card4Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.features.card4Desc}
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">{t.features.card5Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.features.card5Desc}
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Download className="w-5 h-5" />
              </div>
              <h3 className="text-base font-mono font-bold text-white">{t.features.card6Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.features.card6Desc}
              </p>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section aria-labelledby="how-it-works-heading" className="space-y-8">
          <div className="space-y-2">
            <h2 id="how-it-works-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
              {t.howItWorks.heading}
            </h2>
            <p className="text-sm text-gray-400 font-sans">
              {t.howItWorks.subtitle}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3 relative">
              <span className="text-xs font-mono font-bold text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-md inline-block">
                {locale === 'ru' ? 'Шаг 1' : 'Step 1'}
              </span>
              <h3 className="text-base font-mono font-bold text-white">{t.howItWorks.step1Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.howItWorks.step1Desc}
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3 relative">
              <span className="text-xs font-mono font-bold text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-md inline-block">
                {locale === 'ru' ? 'Шаг 2' : 'Step 2'}
              </span>
              <h3 className="text-base font-mono font-bold text-white">{t.howItWorks.step2Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.howItWorks.step2Desc}
              </p>
            </div>

            <div className="glass-panel p-6 rounded-xl border border-white/10 space-y-3 relative">
              <span className="text-xs font-mono font-bold text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-md inline-block">
                {locale === 'ru' ? 'Шаг 3' : 'Step 3'}
              </span>
              <h3 className="text-base font-mono font-bold text-white">{t.howItWorks.step3Title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t.howItWorks.step3Desc}
              </p>
            </div>
          </div>
        </section>

        {/* AI Text-to-Palette Section */}
        <section id="ai-palette" aria-labelledby="ai-generator-heading" className="glass-panel p-8 sm:p-10 rounded-2xl border border-purple-500/20 bg-purple-950/10 space-y-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-white/10 pb-6">
            <div className="space-y-3 max-w-2xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-300 text-xs font-mono">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                <span>{t.aiSection.badge}</span>
              </div>
              <h2 id="ai-generator-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
                {t.aiSection.heading}
              </h2>
              <p className="text-sm text-gray-300 font-sans leading-relaxed">
                {t.aiSection.subtitle}
              </p>
            </div>
            <Link
              href={createHref}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-md shadow-purple-900/30 self-start md:self-auto shrink-0"
            >
              <span>{t.aiSection.cta}</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            <div className="lg:col-span-7 space-y-4 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed">
              <p>
                {t.aiSection.description}
              </p>
              <div className="space-y-2 pt-2">
                <span className="text-xs font-mono font-bold text-purple-300 block">
                  {t.aiSection.promptExamplesTitle}
                </span>
                <div className="flex flex-wrap gap-2">
                  {t.aiSection.prompts.map((promptText, idx) => (
                    <Link
                      key={idx}
                      href={createHref}
                      className="px-3 py-1.5 rounded-lg bg-zinc-900/90 hover:bg-purple-900/30 border border-white/10 hover:border-purple-500/40 text-xs font-mono text-gray-300 hover:text-purple-200 transition-colors"
                    >
                      &ldquo;{promptText}&rdquo;
                    </Link>
                  ))}
                </div>
              </div>
            </div>

            <div className="lg:col-span-5 glass-panel p-5 rounded-xl border border-white/10 space-y-3 bg-zinc-950/60">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-mono font-bold">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>{t.aiSection.privacyTitle}</span>
              </div>
              <p className="text-xs text-gray-400 font-sans leading-relaxed">
                {t.aiSection.privacyDesc}
              </p>
            </div>
          </div>
        </section>

        {/* Why OKLCH Section */}
        <section id="why-oklch" aria-labelledby="why-oklch-heading" className="glass-panel p-8 rounded-2xl border border-white/10 space-y-6">
          <div className="space-y-2 border-b border-white/10 pb-4">
            <h2 id="why-oklch-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
              {t.whyOklch.heading}
            </h2>
            <p className="text-xs font-mono text-purple-300">
              {t.whyOklch.tag}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed">
            <div className="space-y-3">
              <h3 className="font-mono font-bold text-white text-base">{t.whyOklch.col1Title}</h3>
              <p>{t.whyOklch.col1Text1}</p>
              <p>{t.whyOklch.col1Text2}</p>
            </div>

            <div className="space-y-3">
              <h3 className="font-mono font-bold text-white text-base">{t.whyOklch.col2Title}</h3>
              <p>{t.whyOklch.col2Text1}</p>
              <p>{t.whyOklch.col2Text2}</p>
            </div>
          </div>
        </section>

        {/* Target Audience Section */}
        <section aria-labelledby="audience-heading" className="space-y-6">
          <h2 id="audience-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
            {t.audience.heading}
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="glass-panel p-5 rounded-xl border border-white/10 space-y-2">
              <h3 className="font-mono font-bold text-white text-sm">{t.audience.item1Title}</h3>
              <p className="text-xs text-gray-400">{t.audience.item1Desc}</p>
            </div>

            <div className="glass-panel p-5 rounded-xl border border-white/10 space-y-2">
              <h3 className="font-mono font-bold text-white text-sm">{t.audience.item2Title}</h3>
              <p className="text-xs text-gray-400">{t.audience.item2Desc}</p>
            </div>

            <div className="glass-panel p-5 rounded-xl border border-white/10 space-y-2">
              <h3 className="font-mono font-bold text-white text-sm">{t.audience.item3Title}</h3>
              <p className="text-xs text-gray-400">{t.audience.item3Desc}</p>
            </div>

            <div className="glass-panel p-5 rounded-xl border border-white/10 space-y-2">
              <h3 className="font-mono font-bold text-white text-sm">{t.audience.item4Title}</h3>
              <p className="text-xs text-gray-400">{t.audience.item4Desc}</p>
            </div>
          </div>
        </section>

        {/* FAQ Section (Pure HTML details/summary, server-rendered in DOM) */}
        <section aria-labelledby="faq-heading" className="space-y-6">
          <div className="space-y-2">
            <h2 id="faq-heading" className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white">
              {t.faq.heading}
            </h2>
            <p className="text-sm text-gray-400 font-sans">
              {t.faq.subtitle}
            </p>
          </div>

          <div className="space-y-4">
            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>{t.faq.q1}</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                {t.faq.a1}
              </div>
            </details>

            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>{t.faq.q2}</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                {t.faq.a2}
              </div>
            </details>

            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>{t.faq.q3}</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                {t.faq.a3}
              </div>
            </details>

            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>{t.faq.q4}</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                {t.faq.a4}
              </div>
            </details>

            <details className="glass-panel p-5 rounded-xl border border-white/10 group cursor-pointer">
              <summary className="font-mono font-bold text-sm text-white flex items-center justify-between select-none">
                <span>{t.faq.q5}</span>
                <span className="text-purple-400 font-bold group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="pt-3 text-xs sm:text-sm text-gray-300 font-sans leading-relaxed border-t border-white/5 mt-3">
                {t.faq.a5}
              </div>
            </details>
          </div>
        </section>

        {/* CTA Banner */}
        <section aria-label="Call to Action" className="glass-panel p-8 sm:p-12 rounded-2xl border border-purple-500/30 text-center space-y-6 relative overflow-hidden">
          <div className="max-w-2xl mx-auto space-y-3 relative z-10">
            <h2 className="text-2xl sm:text-3xl font-mono font-extrabold text-white">
              {t.cta.heading}
            </h2>
            <p className="text-xs sm:text-sm text-gray-300 font-sans">
              {t.cta.subtitle}
            </p>
          </div>

          <div className="relative z-10">
            <Link
              href={createHref}
              className="inline-flex items-center gap-2 px-8 py-3.5 text-sm font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-lg shadow-purple-900/50 focus:outline-none focus:ring-2 focus:ring-purple-400"
            >
              <span>{t.cta.button}</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 bg-zinc-950 py-8 text-xs font-mono text-gray-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6 mb-6">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-purple-400" />
              <span className="font-bold text-white">{t.footer.brand}</span>
            </div>
            <span className="text-gray-400">{t.footer.text}</span>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 border-t border-white/5 pt-6">
            <Link href={createHref} className="hover:text-white transition-colors">
              {t.footer.studioLink}
            </Link>
            <Link href={locale === 'ru' ? '/ru/explore' : '/explore'} className="hover:text-white transition-colors">
              {locale === 'ru' ? 'Галерея' : 'Explore'}
            </Link>
            <Link href="/guides/oklch-for-pixel-art" className="hover:text-white transition-colors">
              {locale === 'ru' ? 'Гайды' : 'Guides'}
            </Link>
            <Link href="/tools/pixel-art-palette-generator" className="hover:text-white transition-colors">
              {locale === 'ru' ? 'Генератор' : 'Generator'}
            </Link>
            <Link href={locale === 'ru' ? '/ru/privacy' : '/privacy'} className="hover:text-white transition-colors">
              {locale === 'ru' ? 'Политика конфиденциальности' : 'Privacy Policy'}
            </Link>
            <Link href="/terms" className="hover:text-white transition-colors">
              {locale === 'ru' ? 'Условия' : 'Terms'}
            </Link>
            <a href="https://github.com/vansGAMee/OKLCH-PIXEL-PALETTE" className="hover:text-white transition-colors">
              GitHub
            </a>
            <span>&copy; {currentYear}</span>
          </div>
        </div>
      </footer>

    </div>
  );
}
