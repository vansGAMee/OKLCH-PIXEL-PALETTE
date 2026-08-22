import type { Metadata } from 'next';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { HomeAiPromptBox } from '@/components/home/HomeAiPromptBox';
import Link from 'next/link';

import { messages } from '@/i18n/messages';

export const metadata: Metadata = {
  title: 'AI Color Palette Generator | OKLCH Pixel Palette',
  description: 'Generate color palettes from a text prompt. Type a scene or mood in English or Russian — the local AI maps it to an OKLCH-based palette without using a remote AI API.',
  alternates: {
    canonical: 'https://oklchpalette.ru/tools/ai-color-palette-generator',
    languages: { 'ru': 'https://oklchpalette.ru/ru/tools/ai-color-palette-generator' },
  },
  openGraph: {
    title: 'AI Color Palette Generator | OKLCH Pixel Palette',
    description: 'Generate color palettes from a text prompt. Local AI, no OpenAI or Gemini.',
    type: 'website',
    url: 'https://oklchpalette.ru/tools/ai-color-palette-generator',
  },
};

const EXAMPLES = [
  { prompt: 'winter forest', label: 'winter forest' },
  { prompt: 'purple cave', label: 'purple cave' },
  { prompt: 'deep sea horror', label: 'deep sea horror' },
  { prompt: 'neon cyberpunk rain', label: 'neon cyberpunk rain' },
  { prompt: 'cozy autumn cafe', label: 'cozy autumn cafe' },
  { prompt: 'desert ruins at dusk', label: 'desert ruins at dusk' },
];

const FAQ = [
  {
    q: 'Does it use OpenAI or Gemini?',
    a: 'No. AI inference runs locally in the browser using a compact multilingual model and ONNX Runtime Web. Generation does not use a remote AI inference API.',
  },
  {
    q: 'Do I need an account?',
    a: 'No account is required to generate and export palettes.',
  },
  {
    q: 'Does it work with Russian prompts?',
    a: 'Yes. The model is multilingual and handles Russian and English prompts.',
  },
  {
    q: 'How does text-to-palette work?',
    a: 'Your text is embedded into a semantic vector using a local multilingual model. That vector is matched against a set of semantic color anchors, which maps it to an OKLCH base color. The palette is then generated from that base color using a perceptual color harmony.',
  },
  {
    q: 'Why does the first generation take longer?',
    a: 'Model assets (the ONNX model and tokenizer data) are downloaded on first use and cached by the browser. Subsequent generations are faster.',
  },
];

export default function AiColorPaletteGeneratorPage() {
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://oklchpalette.ru/' },
      { '@type': 'ListItem', position: 2, name: 'Tools', item: 'https://oklchpalette.ru/tools' },
      { '@type': 'ListItem', position: 3, name: 'AI Color Palette Generator', item: 'https://oklchpalette.ru/tools/ai-color-palette-generator' },
    ],
  };

  const faqSchema = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQ.map(({ q, a }) => ({
      '@type': 'Question',
      name: q,
      acceptedAnswer: { '@type': 'Answer', text: a },
    })),
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Tools', href: '/tools' },
        { label: 'AI Color Palette Generator' },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }} />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-14">

        {/* Hero + Prompt Entry */}
        <section className="space-y-6">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
              Local AI · No external API
            </div>
            <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
              AI Color Palette Generator
            </h1>
            <p className="text-base text-gray-300 font-sans max-w-2xl">
              Type a scene, mood, or idea. A local in-browser AI model maps your text to a starting
              OKLCH color palette. Works in English and Russian.
            </p>
          </div>

          {/* Reuse existing HomeAiPromptBox — redirects to /create?prompt=... — does NOT load AI model */}
          <HomeAiPromptBox locale="en" prompts={messages['en'].aiSection.prompts} />
        </section>

        {/* Example Prompts */}
        <section className="space-y-4">
          <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">Example prompts</h2>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map(({ prompt, label }) => (
              <Link
                key={prompt}
                href={`/create?prompt=${encodeURIComponent(prompt)}`}
                className="text-xs font-mono px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 hover:border-purple-500/40 hover:text-purple-300 text-gray-400 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {label}
              </Link>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section className="space-y-5">
          <h2 className="text-xl font-mono font-bold text-white">How it works</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { step: '1', title: 'Describe', desc: 'Type any scene, mood, or idea in English or Russian.' },
              { step: '2', title: 'Embed → Match', desc: 'A local multilingual model converts your text to a semantic vector and matches it to an OKLCH color anchor.' },
              { step: '3', title: 'Generate palette', desc: 'The matched anchor becomes the base color. Shadow, highlight, and accent are derived by OKLCH perceptual harmony.' },
            ].map(({ step, title, desc }) => (
              <div key={step} className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
                <div className="text-2xl font-mono font-black text-purple-500/50">{step}</div>
                <h3 className="text-sm font-mono font-bold text-white">{title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Technical info */}
        <section className="glass-panel rounded-2xl border border-white/10 p-6 space-y-4">
          <h2 className="text-base font-mono font-bold text-white">Technical details</h2>
          <div className="space-y-2 text-sm text-gray-300 font-sans leading-relaxed">
            <p>
              AI inference runs locally in the browser using a compact multilingual text embedding model
              and ONNX Runtime Web. Required model assets are downloaded on first use and cached by the browser.
              Generation does not use a remote AI inference API — no OpenAI, Gemini, or Anthropic.
            </p>
            <p>
              The semantic matching layer uses a set of handcrafted color anchors that map semantic
              concepts (cold, warm, dark, vivid, organic, etc.) to OKLCH color targets. This gives
              predictable, art-direction-friendly results rather than statistically arbitrary colors.
            </p>
            <p>
              All generated colors are fitted to the sRGB gamut while preserving hue and perceptual
              lightness. The palette uses OKLCH Shadow, Base, Highlight, and Accent roles.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 pt-2">
            {['Multilingual E5 Small (ONNX)', 'OKLCH Color Space', 'Semantic Anchor Matching', 'sRGB Gamut Fitting'].map(tag => (
              <span key={tag} className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-500">{tag}</span>
            ))}
          </div>
        </section>

        {/* Use cases */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">What it&#39;s useful for</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { title: 'Pixel art', desc: 'Get a starting palette for a scene before hand-tweaking individual colors.' },
              { title: 'Illustration', desc: 'Explore color mood quickly without manually navigating color wheels.' },
              { title: 'Game jams', desc: 'Generate themed palettes fast when you need something coherent under time pressure.' },
              { title: 'UI/web design', desc: 'Start with a semantically grounded palette, then refine individual tokens.' },
            ].map(({ title, desc }) => (
              <div key={title} className="glass-panel rounded-xl border border-white/10 p-5 space-y-1.5">
                <h3 className="text-sm font-mono font-bold text-white">{title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Limitations */}
        <section className="space-y-3">
          <h2 className="text-base font-mono font-bold text-white">Limitations</h2>
          <ul className="space-y-2 text-xs text-gray-400 font-sans">
            <li>• The model interprets semantic meaning, not physical color names. &quot;Bright red&quot; will produce a red-range result, but exact output depends on semantic similarity to trained anchors.</li>
            <li>• Generated palettes are starting points. Pixel artists typically adjust colors manually after generation.</li>
            <li>• First generation requires downloading model assets (~20–30 MB). An active internet connection is needed on first use.</li>
            <li>• Generation on low-end mobile devices may be slower than on desktop.</li>
          </ul>
        </section>

        {/* FAQ */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">FAQ</h2>
          <dl className="space-y-3">
            {FAQ.map(({ q, a }) => (
              <div key={q} className="glass-panel rounded-xl border border-white/10 p-5 space-y-2">
                <dt className="text-sm font-mono font-bold text-white">{q}</dt>
                <dd className="text-xs text-gray-300 font-sans leading-relaxed">{a}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Related */}
        <section className="space-y-3">
          <h2 className="text-sm font-mono font-bold text-gray-400 uppercase tracking-wider">Related tools</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/tools/palette-analyzer" className="text-xs font-mono px-3 py-1.5 rounded-lg glass-panel border border-white/10 hover:border-purple-500/30 text-gray-300 hover:text-white transition-colors">
              Palette Analyzer →
            </Link>
            <Link href="/tools/color-ramp-generator" className="text-xs font-mono px-3 py-1.5 rounded-lg glass-panel border border-white/10 hover:border-purple-500/30 text-gray-300 hover:text-white transition-colors">
              Color Ramp Generator →
            </Link>
            <Link href="/research/text-to-color-benchmark" className="text-xs font-mono px-3 py-1.5 rounded-lg glass-panel border border-white/10 hover:border-purple-500/30 text-gray-300 hover:text-white transition-colors">
              Benchmark Results →
            </Link>
          </div>
        </section>
      </main>
    </ToolPageLayout>
  );
}
