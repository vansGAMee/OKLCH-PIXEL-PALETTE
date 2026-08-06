'use client';

/**
 * src/components/import/ImportModal.tsx
 * Modal for importing palettes from GPL, PAL, HEX/TXT, and JSON files.
 * Includes color swatches preview and cancel before applying to Studio state.
 */
import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Upload, X, Check, AlertCircle, FileText, Palette as PaletteIcon } from 'lucide-react';
import { parseGpl } from '@/lib/import/parsers/parseGpl';
import { parsePal } from '@/lib/import/parsers/parsePal';
import { parseHex } from '@/lib/import/parsers/parseHex';
import { parseJson } from '@/lib/import/parsers/parseJson';
import type { PaletteColor } from '@/types/palette';
import { Locale } from '@/i18n/messages';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImport: (colors: PaletteColor[], name?: string) => void;
  locale?: Locale;
}

export function ImportModal({ isOpen, onClose, onImport, locale = 'en' }: ImportModalProps) {
  const [parsedColors, setParsedColors] = useState<PaletteColor[] | null>(null);
  const [paletteName, setPaletteName] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isRu = locale === 'ru';

  const resetState = () => {
    setParsedColors(null);
    setPaletteName(undefined);
    setError(null);
    setFileName(null);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const processFileContent = (content: string, fname: string) => {
    resetState();
    setFileName(fname);
    const ext = fname.split('.').pop()?.toLowerCase() ?? '';

    let res: { colors: PaletteColor[]; name?: string; error?: string };

    if (ext === 'gpl') {
      res = parseGpl(content);
    } else if (ext === 'pal') {
      res = parsePal(content);
    } else if (ext === 'json') {
      res = parseJson(content);
    } else {
      // Fallback for .hex, .txt, or unknown text
      const hexRes = parseHex(content);
      if (hexRes.colors.length > 0) {
        res = hexRes;
      } else {
        // Try GPL then JSON then PAL
        const tryGpl = parseGpl(content);
        if (tryGpl.colors.length > 0) res = tryGpl;
        else {
          const tryJson = parseJson(content);
          if (tryJson.colors.length > 0) res = tryJson;
          else res = { colors: [], error: isRu ? 'Неизвестный формат палитры' : 'Unrecognized palette format' };
        }
      }
    }

    if (res.error) {
      setError(res.error);
    } else if (res.colors.length > 0) {
      setParsedColors(res.colors);
      setPaletteName(res.name);
    } else {
      setError(isRu ? 'Не удалось извлечь цвета из файла' : 'Could not extract colors from file');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      const content = evt.target?.result as string;
      if (content) processFileContent(content, file.name);
    };
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      const content = evt.target?.result as string;
      if (content) processFileContent(content, file.name);
    };
    reader.readAsText(file);
  };

  const handleConfirmImport = () => {
    if (parsedColors && parsedColors.length > 0) {
      onImport(parsedColors, paletteName);
      handleClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="w-full max-w-md bg-zinc-950 border border-white/15 rounded-2xl shadow-2xl p-6 space-y-5 glass-panel text-white font-mono"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg bg-purple-500/20 text-purple-400">
                  <Upload className="w-5 h-5" />
                </div>
                <h2 className="text-sm font-bold uppercase tracking-wider">
                  {isRu ? 'Импорт палитры' : 'Import Palette'}
                </h2>
              </div>
              <button
                onClick={handleClose}
                className="p-1 text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Dropzone & File Input */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-white/20 hover:border-purple-500/50 bg-zinc-900/50 rounded-xl p-6 text-center cursor-pointer transition-all space-y-2 group"
            >
              <FileText className="w-8 h-8 text-gray-400 group-hover:text-purple-400 mx-auto transition-colors" />
              <p className="text-xs font-bold text-gray-200">
                {isRu ? 'Перетащите файл палитры сюда' : 'Drop palette file here'}
              </p>
              <p className="text-[11px] text-gray-400">
                {isRu ? 'Поддерживается .gpl, .pal, .hex, .txt, .json' : 'Supports .gpl, .pal, .hex, .txt, .json'}
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".gpl,.pal,.hex,.txt,.json"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>

            {/* Error Display */}
            {error && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Preview Section */}
            {parsedColors && parsedColors.length > 0 && (
              <div className="space-y-3 bg-zinc-900/80 p-4 rounded-xl border border-white/10">
                <div className="flex items-center justify-between text-xs text-gray-300">
                  <span className="font-bold flex items-center gap-1">
                    <PaletteIcon className="w-3.5 h-3.5 text-purple-400" />
                    {paletteName || fileName || (isRu ? 'Импортированная палитра' : 'Imported Palette')}
                  </span>
                  <span className="text-purple-300 font-bold">{parsedColors.length} {isRu ? 'цветов' : 'colors'}</span>
                </div>

                {/* Color Strip */}
                <div className="flex h-12 rounded-lg overflow-hidden border border-white/10 shadow-inner">
                  {parsedColors.map((c, i) => (
                    <div
                      key={i}
                      className="flex-1"
                      style={{ backgroundColor: c.hex }}
                      title={`${c.role}: ${c.hex}`}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-xs font-bold text-gray-400 hover:text-white bg-zinc-900 border border-white/10 rounded-xl transition-all"
              >
                {isRu ? 'Отмена' : 'Cancel'}
              </button>
              <button
                disabled={!parsedColors || parsedColors.length === 0}
                onClick={handleConfirmImport}
                className="flex items-center gap-1.5 px-5 py-2 text-xs font-bold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-all shadow-lg shadow-purple-900/30"
              >
                <Check className="w-4 h-4" />
                {isRu ? 'Применить палитру' : 'Apply Palette'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
