'use client';

import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface CopyHexButtonProps {
  hex: string;
  locale?: 'en' | 'ru';
}

export function CopyHexButton({ hex, locale = 'en' }: CopyHexButtonProps) {
  const [copied, setCopied] = useState(false);
  const isRu = locale === 'ru';

  const handleCopy = () => {
    if (typeof window !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(hex.toUpperCase());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="p-2 text-gray-400 hover:text-purple-400 transition-colors rounded-lg focus:outline-none focus:ring-1 focus:ring-purple-500"
      title={copied ? (isRu ? 'Скопировано!' : 'Copied!') : (isRu ? 'Скопировать HEX' : 'Copy HEX')}
    >
      {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
    </button>
  );
}
