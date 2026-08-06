'use client';

import React, { useState } from 'react';
import { isValidHex, normalizeHex } from '@/lib/color/conversions';
import { Locale, messages } from '@/i18n/messages';
import { Pipette, AlertCircle } from 'lucide-react';

interface ColorPickerProps {
  value: string;
  onChange: (hex: string) => void;
  locale?: Locale;
}

const PRESET_COLORS = [
  { name: 'Deep Purple', hex: '#5b21b6' },
  { name: 'Cyber Yellow', hex: '#f2c94c' },
  { name: 'Ruby Red', hex: '#ff0000' },
  { name: 'Emerald Green', hex: '#00ff00' },
  { name: 'Pure Blue', hex: '#0000ff' },
  { name: 'Midnight', hex: '#121212' },
  { name: 'Slate Gray', hex: '#808080' },
  { name: 'Pearl White', hex: '#f7f7f7' },
];

export const ColorPicker: React.FC<ColorPickerProps> = ({ value, onChange, locale = 'en' }) => {
  const [inputVal, setInputVal] = useState(value);
  const [prevValue, setPrevValue] = useState(value);
  const [error, setError] = useState(false);
  const t = messages[locale].controls;

  // Sync internal input string during render when external prop value changes
  if (value !== prevValue) {
    setPrevValue(value);
    setInputVal(value);
    setError(false);
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    setInputVal(raw);

    const norm = normalizeHex(raw);
    if (norm) {
      setError(false);
      onChange(norm);
    } else {
      setError(true);
    }
  };

  const handleNativePicker = (e: React.ChangeEvent<HTMLInputElement>) => {
    const hex = e.target.value;
    const norm = normalizeHex(hex) || hex;
    setInputVal(norm);
    setError(false);
    onChange(norm);
  };

  return (
    <div className="glass-panel rounded-xl p-5 border border-white/10 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Pipette className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-widest text-gray-200 uppercase">
              {t.colorPickerTitle}
            </h3>
            <p className="text-[11px] text-gray-400 font-mono">User Primary Color (Base)</p>
          </div>
        </div>
      </div>

      {/* Input Row */}
      <div className="space-y-2">
        <label className="text-xs font-mono text-gray-300 block">{t.hexLabel}</label>
        <div className="flex items-center gap-3">
          {/* Swatch & Native Color Picker Trigger */}
          <div className="relative w-12 h-12 rounded-xl overflow-hidden border border-white/20 shadow-md cursor-pointer shrink-0 group">
            <div
              className="w-full h-full"
              style={{ backgroundColor: isValidHex(inputVal) ? inputVal : value }}
            />
            <input
              type="color"
              value={isValidHex(inputVal) ? inputVal : value}
              onChange={handleNativePicker}
              aria-label="Pick color using browser picker"
              className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
            />
          </div>

          {/* Text Input */}
          <div className="relative flex-1">
            <input
              type="text"
              value={inputVal}
              onChange={handleInputChange}
              placeholder="#5B21B6"
              aria-label="Enter HEX color code"
              className={`w-full bg-zinc-900/90 border rounded-xl px-4 py-3 text-base sm:text-lg font-mono font-bold tracking-wider uppercase text-white placeholder-gray-600 focus:outline-none transition-all ${
                error
                  ? 'border-red-500 focus:ring-2 focus:ring-red-500/50'
                  : 'border-white/10 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/30'
              }`}
            />
            {error && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-red-400 flex items-center gap-1 text-xs font-mono">
                <AlertCircle className="w-4 h-4" /> Invalid HEX
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Preset Swatches */}
      <div>
        <span className="text-[11px] font-mono text-gray-400 block mb-2">Presets</span>
        <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
          {PRESET_COLORS.map((preset) => (
            <button
              key={preset.hex}
              onClick={() => {
                setInputVal(preset.hex);
                setError(false);
                onChange(preset.hex);
              }}
              title={`${preset.name} (${preset.hex})`}
              aria-label={`Select preset ${preset.name}`}
              className={`h-8 rounded-lg border transition-all hover:scale-105 ${
                value.toLowerCase() === preset.hex.toLowerCase()
                  ? 'border-purple-400 ring-2 ring-purple-500/50 scale-105'
                  : 'border-white/15 hover:border-white/40'
              }`}
              style={{ backgroundColor: preset.hex }}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
