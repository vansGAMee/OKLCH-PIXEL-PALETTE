'use client';

import { useState, useCallback, useRef } from 'react';
import { parseTargetPalette, recolorPixelBuffer } from '@/lib/tools/spriteRecolor';

const MAX_SPRITE_DIM = 256;
const MAX_FILE_MB = 2;

export function SpriteRecolor({ locale = 'en' }: { locale?: 'en' | 'ru' }) {
  const isRu = locale === 'ru';
  const spriteInputRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const outputCanvasRef = useRef<HTMLCanvasElement>(null);

  const [spritePreview, setSpritePreview] = useState<string | null>(null);
  const [outputPreview, setOutputPreview] = useState<string | null>(null);
  const [paletteInput, setPaletteInput] = useState('#172033 #20283A #5F718A #C084FC #F43F5E');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const processSprite = useCallback(async (file: File) => {
    setError(null);
    setOutputPreview(null);

    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setError(`File too large. Max ${MAX_FILE_MB} MB.`);
      return;
    }
    if (!file.type.startsWith('image/')) {
      setError('Please select an image file.');
      return;
    }

    const targets = parseTargetPalette(paletteInput);
    if (targets.length < 2) {
      setError(isRu ? 'Введите хотя бы 2 цвета палитры.' : 'Enter at least 2 palette colors.');
      return;
    }

    setLoading(true);
    try {
      const url = URL.createObjectURL(file);
      setSpritePreview(url);

      await new Promise<void>((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          const canvas = canvasRef.current;
          const outCanvas = outputCanvasRef.current;
          if (!canvas || !outCanvas) { reject(new Error('Canvas unavailable')); return; }

          let { width, height } = img;
          if (width > MAX_SPRITE_DIM || height > MAX_SPRITE_DIM) {
            const scale = MAX_SPRITE_DIM / Math.max(width, height);
            width = Math.round(width * scale);
            height = Math.round(height * scale);
          }

          canvas.width = width; canvas.height = height;
          outCanvas.width = width; outCanvas.height = height;

          const ctx = canvas.getContext('2d')!;
          ctx.drawImage(img, 0, 0, width, height);
          const imageData = ctx.getImageData(0, 0, width, height);
          const outCtx = outCanvas.getContext('2d')!;
          const outData = outCtx.createImageData(width, height);

          recolorPixelBuffer(imageData.data, outData.data, targets);

          outCtx.putImageData(outData, 0, 0);
          setOutputPreview(outCanvas.toDataURL('image/png'));
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
  }, [paletteInput, isRu]);

  const downloadOutput = () => {
    if (!outputPreview) return;
    const a = document.createElement('a');
    a.href = outputPreview;
    a.download = 'recolored.png';
    a.click();
  };

  return (
    <div className="space-y-8">
      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />
      <canvas ref={outputCanvasRef} className="hidden" aria-hidden="true" />

      {/* Palette input */}
      <section className="space-y-2">
        <label htmlFor="target-palette" className="text-xs font-mono font-bold text-gray-400 uppercase tracking-wider block">
          {isRu ? 'Целевая палитра (HEX)' : 'Target palette (HEX colors)'}
        </label>
        <input
          id="target-palette"
          type="text"
          value={paletteInput}
          onChange={e => setPaletteInput(e.target.value)}
          className="w-full glass-panel border border-white/15 rounded-xl px-4 py-2 text-sm font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-purple-500/60 bg-transparent"
          placeholder="#172033 #5F718A #C084FC #F43F5E"
          spellCheck={false}
        />
        <div className="flex flex-wrap gap-1.5 mt-1">
          {parseTargetPalette(paletteInput).map((c, i) => (
            <div key={i} className="w-5 h-5 rounded border border-white/10" style={{ backgroundColor: c.hex }} title={c.hex} />
          ))}
        </div>
      </section>

      {/* Sprite upload */}
      <section
        className="glass-panel rounded-2xl border-2 border-dashed border-white/15 hover:border-purple-500/40 p-8 text-center cursor-pointer transition-all group"
        onClick={() => spriteInputRef.current?.click()}
        onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) processSprite(f); }}
        onDragOver={e => e.preventDefault()}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && spriteInputRef.current?.click()}
        aria-label={isRu ? 'Загрузить спрайт' : 'Upload sprite'}
      >
        <input
          ref={spriteInputRef}
          type="file"
          accept="image/png,image/gif,image/webp"
          className="sr-only"
          onChange={e => { const f = e.target.files?.[0]; if (f) processSprite(f); }}
          aria-label={isRu ? 'Выбор файла спрайта' : 'Sprite file input'}
        />
        {spritePreview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={spritePreview} alt="Sprite" className="max-h-32 mx-auto border border-white/10 rounded-xl" style={{ imageRendering: 'pixelated' }} />
        ) : (
          <div className="space-y-2">
            <div className="text-3xl">🎮</div>
            <p className="text-sm font-mono text-gray-400 group-hover:text-gray-300 transition-colors">
              {isRu ? 'Перетащите спрайт или нажмите для выбора' : 'Drop a sprite or click to select'}
            </p>
            <p className="text-xs font-mono text-gray-600">PNG, GIF, WebP · max {MAX_FILE_MB} MB · max {MAX_SPRITE_DIM}×{MAX_SPRITE_DIM}px</p>
          </div>
        )}
        {loading && <div className="mt-4 text-xs font-mono text-purple-400 animate-pulse">{isRu ? 'Перекраска...' : 'Recoloring...'}</div>}
      </section>

      {error && <div className="text-xs font-mono text-red-400 glass-panel rounded-xl border border-red-500/20 p-4">✕ {error}</div>}

      {/* Output */}
      {outputPreview && (
        <section className="glass-panel rounded-2xl border border-white/10 p-6 space-y-4" aria-live="polite">
          <h3 className="text-sm font-mono font-bold text-white">{isRu ? 'Результат' : 'Result'}</h3>
          <div className="flex flex-wrap gap-6 items-start">
            {spritePreview && (
              <div className="space-y-1">
                <div className="text-[10px] font-mono text-gray-500">{isRu ? 'Оригинал' : 'Original'}</div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={spritePreview} alt="Original" className="max-h-24 border border-white/10 rounded-lg" style={{ imageRendering: 'pixelated' }} />
              </div>
            )}
            <div className="space-y-1">
              <div className="text-[10px] font-mono text-purple-400">{isRu ? 'Перекрашено' : 'Recolored'}</div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={outputPreview} alt="Recolored" className="max-h-24 border border-purple-500/30 rounded-lg" style={{ imageRendering: 'pixelated' }} />
            </div>
          </div>
          <button
            onClick={downloadOutput}
            className="px-4 py-1.5 text-xs font-mono text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 shadow-md"
          >
            {isRu ? 'Скачать PNG' : 'Download PNG'}
          </button>
        </section>
      )}

      <p className="text-xs font-mono text-gray-600">
        {isRu
          ? 'Обработка выполняется локально в браузере. Изображения не отправляются на сервер.'
          : 'Processing runs locally in the browser. Images are not sent to a server.'}
      </p>
    </div>
  );
}
