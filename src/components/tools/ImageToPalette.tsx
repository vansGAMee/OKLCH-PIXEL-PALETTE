'use client';

import { useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { extractPalette, MAX_FILE_SIZE_MB, type ExtractionResult } from '@/lib/tools/imageQuantize';

const TARGET_OPTIONS = [4, 5, 6, 7, 8, 10, 12, 16];

const MERGE_LEVEL_TO_THRESHOLD: Record<'low' | 'medium' | 'high', number> = {
  low: 0.025,
  medium: 0.04,
  high: 0.06,
};

function FrequencyBar({ freq }: { freq: number }) {
  return (
    <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
      <div className="h-full bg-purple-500/60 rounded-full" style={{ width: `${(freq * 100).toFixed(0)}%` }} />
    </div>
  );
}

export function ImageToPalette({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const isRu = locale === 'ru';
  const router = useRouter();

  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [targetCount, setTargetCount] = useState(6);
  const [mergeLevel, setMergeLevel] = useState<'low' | 'medium' | 'high'>('medium');
  const [copyMsg, setCopyMsg] = useState('');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback(async (file: File) => {
    setError(null);
    setResult(null);

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setError(`File is too large. Maximum: ${MAX_FILE_SIZE_MB} MB.`);
      return;
    }

    if (!file.type.startsWith('image/')) {
      setError('Please select an image file (PNG, JPEG, GIF, WebP).');
      return;
    }

    setLoading(true);

    try {
      const url = URL.createObjectURL(file);
      setPreview(url);

      await new Promise<void>((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          const canvas = canvasRef.current;
          if (!canvas) { reject(new Error('Canvas not available')); return; }

          let { width, height } = img;
          const MAX_DIM = 512;
          if (width > MAX_DIM || height > MAX_DIM) {
            const scale = MAX_DIM / Math.max(width, height);
            width = Math.round(width * scale);
            height = Math.round(height * scale);
          }

          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          if (!ctx) { reject(new Error('Canvas context not available')); return; }
          ctx.drawImage(img, 0, 0, width, height);

          const imageData = ctx.getImageData(0, 0, width, height);
          const threshold = MERGE_LEVEL_TO_THRESHOLD[mergeLevel];
          const extracted = extractPalette(imageData, targetCount, threshold);
          setResult(extracted);
          URL.revokeObjectURL(url);
          resolve();
        };
        img.onerror = () => reject(new Error('Failed to load image'));
        img.src = url;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Processing failed');
    } finally {
      setLoading(false);
    }
  }, [targetCount, mergeLevel]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  }, [processFile]);

  const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  }, [processFile]);

  const copyHex = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.colors.map(c => c.hex.toUpperCase()).join(' ')).then(() => {
      setCopyMsg(isRu ? 'Скопировано!' : 'Copied!');
      setTimeout(() => setCopyMsg(''), 1500);
    });
  };

  const openInStudio = () => {
    if (!result) return;
    const base = result.dominantHex;
    const all = result.colors.map(c => c.hex).join(',');
    const href = isRu
      ? `/ru/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(all)}`
      : `/create?base=${encodeURIComponent(base)}&import=${encodeURIComponent(all)}`;
    router.push(href);
  };

  return (
    <div className="space-y-8">
      {/* Hidden canvas for processing */}
      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

      {/* Controls: count + merge level */}
      <section className="glass-panel rounded-2xl border border-white/10 p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
              {isRu ? 'Количество цветов' : 'Color count'} ({targetCount})
            </label>
            <div className="flex flex-wrap gap-1.5">
              {TARGET_OPTIONS.map(n => (
                <button
                  key={n}
                  onClick={() => setTargetCount(n)}
                  className={`w-8 h-8 text-xs font-mono font-bold rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                    targetCount === n
                      ? 'bg-purple-600 text-white'
                      : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
              {isRu ? 'Объединение похожих' : 'Merge similar'}
            </label>
            <div className="flex flex-wrap gap-1.5">
              {(['low', 'medium', 'high'] as const).map(lv => (
                <button
                  key={lv}
                  onClick={() => setMergeLevel(lv)}
                  className={`px-2 py-1 text-xs font-mono rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                    mergeLevel === lv
                      ? 'bg-purple-600 text-white'
                      : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white'
                  }`}
                >
                  {isRu ? { low: 'слабо', medium: 'средне', high: 'сильно' }[lv] : lv}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Drop zone */}
      <section
        onDrop={handleDrop}
        onDragOver={e => e.preventDefault()}
        onClick={() => inputRef.current?.click()}
        className="glass-panel rounded-2xl border-2 border-dashed border-white/15 hover:border-purple-500/40 p-10 text-center cursor-pointer transition-all group focus-within:border-purple-500/40"
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
        aria-label={isRu ? 'Перетащите изображение или нажмите для выбора' : 'Drop image or click to select'}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="sr-only"
          onChange={handleInput}
          aria-label={isRu ? 'Выбор файла изображения' : 'Image file input'}
        />
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt={isRu ? 'Предпросмотр изображения' : 'Image preview'} className="max-h-48 mx-auto rounded-xl object-contain border border-white/10" />
        ) : (
          <div className="space-y-3">
            <div className="text-4xl">🖼</div>
            <p className="text-sm font-mono text-gray-400 group-hover:text-gray-300 transition-colors">
              {isRu ? 'Перетащите изображение или нажмите для выбора' : 'Drop an image or click to select'}
            </p>
            <p className="text-xs font-mono text-gray-600">PNG, JPEG, GIF, WebP · max {MAX_FILE_SIZE_MB} MB</p>
          </div>
        )}
        {loading && (
          <div className="mt-4 text-xs font-mono text-purple-400 animate-pulse">
            {isRu ? 'Обработка...' : 'Processing...'}
          </div>
        )}
      </section>

      {/* Error */}
      {error && (
        <div className="text-xs font-mono text-red-400 glass-panel rounded-xl border border-red-500/20 p-4">
          ✕ {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <section className="space-y-5" aria-live="polite" aria-label={isRu ? 'Результат извлечения палитры' : 'Extracted palette'}>
          <div className="glass-panel rounded-2xl border border-white/10 p-6 space-y-4">
            <h3 className="text-sm font-mono font-bold text-white">
              {isRu ? `Палитра — ${result.colors.length} цветов` : `Palette — ${result.colors.length} colors`}
            </h3>

            {/* Palette bar */}
            <div className="rounded-xl overflow-hidden border border-white/10 flex h-16">
              {result.colors.map((c, i) => (
                <div
                  key={i}
                  className="flex-shrink-0"
                  style={{ backgroundColor: c.hex, flexGrow: c.frequency }}
                  title={`${c.hex.toUpperCase()} — ${(c.frequency * 100).toFixed(0)}%`}
                />
              ))}
            </div>

            {/* Color list */}
            <div className="space-y-2">
              {result.colors.map((c, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg border border-white/15 shrink-0" style={{ backgroundColor: c.hex }} />
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <div className="text-xs font-mono text-white">{c.hex.toUpperCase()}</div>
                    <FrequencyBar freq={c.frequency} />
                  </div>
                  <div className="text-[10px] font-mono text-gray-600 shrink-0 text-right">
                    <div>L:{(c.oklch.l * 100).toFixed(0)}%</div>
                    <div>{(c.frequency * 100).toFixed(0)}%</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-2 pt-2">
              <button
                onClick={copyHex}
                className="px-4 py-1.5 text-xs font-mono text-white bg-white/10 hover:bg-white/15 rounded-lg border border-white/15 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {copyMsg || (isRu ? 'Копировать HEX' : 'Copy HEX')}
              </button>
              <button
                onClick={openInStudio}
                className="px-4 py-1.5 text-xs font-mono text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 shadow-md shadow-purple-900/30"
              >
                {isRu ? 'Открыть в студии' : 'Open in Studio'}
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Privacy notice */}
      <p className="text-xs font-mono text-gray-600">
        {isRu
          ? 'Изображение обрабатывается локально в браузере. На сервер ничего не отправляется.'
          : 'Image processing runs locally in the browser. Nothing is uploaded to a server.'}
      </p>
    </div>
  );
}
