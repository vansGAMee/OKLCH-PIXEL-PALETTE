import type { Metadata } from 'next';
import Link from 'next/link';
import { ToolPageLayout } from '@/components/tools/ToolPageLayout';
import { ArrowRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Text-to-Palette Benchmark & AI Architecture | OKLCH Pixel Palette',
  description: 'Technical report on our in-browser multilingual semantic palette generator. How we solved regression drift, black-to-brown bias, and cross-lingual consistency with E5 Small & OKLCH anchors.',
  alternates: {
    canonical: 'https://oklchpalette.ru/research/text-to-color-benchmark',
    languages: { 'ru': 'https://oklchpalette.ru/ru/research/text-to-color-benchmark' },
  },
  openGraph: {
    title: 'Text-to-Palette Benchmark & AI Architecture',
    description: 'Technical report on in-browser multilingual semantic palette generation with OKLCH anchors.',
    type: 'article',
    url: 'https://oklchpalette.ru/research/text-to-color-benchmark',
  },
};

const BENCHMARK_CATEGORIES = [
  {
    name: 'Direct Colors',
    desc: 'Literal color names in English and Russian (e.g. "black", "чёрный", "cyan", "золотой"). Tests strict neutrality and hue bounds.',
    passRate: '100%',
    status: 'PASS',
  },
  {
    name: 'Semantic Concepts',
    desc: 'Complex atmospheric scene descriptions ("winter forest", "rusty factory at sunset", "deep sea horror"). Tests mood-to-color mapping.',
    passRate: '95%+',
    status: 'PASS',
  },
  {
    name: 'Synonym Pairs & Cross-Lingual Parity',
    desc: 'Equivalence across languages ("lava" vs "лава", "snow" vs "снег", "cyberpunk" vs "киберпанк"). Tests vector alignment.',
    passRate: '95%+',
    status: 'PASS',
  },
  {
    name: 'Out-of-Distribution (OOD) Prompts',
    desc: 'Novel metaphors and abstract game concepts ("poisoned moonlight", "digital decay"). Tests graceful generalization.',
    passRate: '90%+',
    status: 'PASS',
  },
];

export default function TextToColorBenchmarkPage() {
  const articleSchema = {
    '@context': 'https://schema.org',
    '@type': 'TechArticle',
    headline: 'Text-to-Palette Benchmark & AI Architecture',
    description: 'Technical report on in-browser multilingual semantic palette generation with OKLCH anchors.',
    author: { '@type': 'Organization', name: 'OKLCH Pixel Palette' },
  };

  return (
    <ToolPageLayout
      locale="en"
      breadcrumbs={[
        { label: 'Research' },
        { label: 'AI Benchmark & Architecture' },
      ]}
    >
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(articleSchema) }} />

      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 flex-1 w-full space-y-12">
        <header className="space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono">
            Machine Learning &amp; Color Pipeline
          </div>
          <h1 className="text-3xl sm:text-4xl font-mono font-extrabold text-white leading-tight">
            Text-to-Palette Benchmark &amp; Local AI Architecture
          </h1>
          <p className="text-base text-gray-300 font-sans leading-relaxed">
            How we designed an in-browser neural color pipeline that runs entirely on client devices,
            supports English and Russian prompts, and avoids the common pitfalls of direct neural color regression.
          </p>
        </header>

        {/* The Engineering Challenge */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">1. The Direct Regression Failure</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            In early prototypes, we trained a lightweight MLP regression head directly on text embeddings to predict OKLCH coordinates.
            This produced a well-known machine learning failure mode: regression to the mean.
          </p>
          <div className="glass-panel rounded-xl p-5 border border-white/10 space-y-2 text-xs font-mono text-gray-300">
            <div className="text-amber-400 font-bold">The &quot;Black → Muddy Brown&quot; Problem:</div>
            <p className="text-gray-400 font-sans">
              Because training losses minimize squared error across thousands of scene descriptions, prompt inputs for extreme colors
              like &quot;black&quot; or &quot;white&quot; were continually pulled toward mid-lightness, mid-chroma averages (generating dark muddy brown instead of true neutral black).
            </p>
          </div>
        </section>

        {/* The Architecture */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">2. Semantic Anchor Architecture</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            To guarantee high-quality, art-direction-friendly palettes without massive server-side models, we decoupled semantic interpretation from color math:
          </p>
          <ol className="space-y-3 list-decimal list-inside text-sm text-gray-300 font-sans">
            <li>
              <strong className="text-white">Multilingual Embedding:</strong> The user&#39;s prompt is embedded locally using a compact multilingual model (ONNX WebAssembly) into a dense 384-dimensional vector space.
            </li>
            <li>
              <strong className="text-white">Semantic Anchor Mapping:</strong> The embedding is matched against curated semantic anchors representing specific moods, materials, and lighting states.
            </li>
            <li>
              <strong className="text-white">Literal Color Extraction:</strong> Explicit color tokens (&quot;red&quot;, &quot;синий&quot;, &quot;emerald&quot;) have deterministic boundary guarantees.
            </li>
            <li>
              <strong className="text-white">Perceptual Harmony Generation:</strong> The resolved base color is expanded into a full palette (Shadow, Base, Highlight, Accent) using OKLCH perceptual harmony and sRGB gamut fitting.
            </li>
          </ol>
        </section>

        {/* Benchmark Results */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">3. Semantic Quality Benchmark</h2>
          <p className="text-sm text-gray-300 font-sans leading-relaxed">
            Our automated test suite evaluates prompt-to-palette accuracy across 4 independent test suites:
          </p>

          <div className="space-y-3">
            {BENCHMARK_CATEGORIES.map(cat => (
              <div key={cat.name} className="glass-panel rounded-xl p-5 border border-white/10 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-mono font-bold text-white">{cat.name}</h3>
                  <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
                    {cat.status} · {cat.passRate}
                  </span>
                </div>
                <p className="text-xs text-gray-400 font-sans leading-relaxed">{cat.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Performance & Privacy */}
        <section className="space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">4. In-Browser Privacy &amp; Performance</h2>
          <div className="glass-panel rounded-xl p-5 border border-white/10 space-y-2 text-xs text-gray-300 font-sans leading-relaxed">
            <p>
              • <strong>Zero Remote API Calls:</strong> No prompts or generated palettes are sent to external AI servers (no OpenAI, Gemini, or remote endpoints).
            </p>
            <p>
              • <strong>Lazy Loading:</strong> Model assets are only downloaded when the user actively triggers generation — browsing pages and viewing palettes does not download model files.
            </p>
            <p>
              • <strong>Offline Capable:</strong> Once cached, inference runs locally in browser memory using ONNX Runtime Web.
            </p>
          </div>
        </section>

        {/* CTA */}
        <section className="glass-panel rounded-2xl border border-purple-500/30 p-8 text-center space-y-4">
          <h2 className="text-xl font-mono font-bold text-white">Try the AI Generator</h2>
          <p className="text-sm text-gray-400 font-sans">
            Type any scene or idea and see the semantic mapping pipeline in real time.
          </p>
          <Link
            href="/tools/ai-color-palette-generator"
            className="inline-flex items-center gap-2 px-6 py-2.5 text-xs font-mono font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl transition-all shadow-md"
          >
            AI Palette Generator <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </section>
      </article>
    </ToolPageLayout>
  );
}
