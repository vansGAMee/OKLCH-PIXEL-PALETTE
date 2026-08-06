'use client';

import React from 'react';
import { LayoutGroup } from 'motion/react';
import { Palette } from '@/types/palette';
import { Locale } from '@/i18n/messages';
import { ColorCard } from './ColorCard';

interface PaletteGridProps {
  palette: Palette;
  locale?: Locale;
}

export const PaletteGrid: React.FC<PaletteGridProps> = ({ palette, locale = 'en' }) => {
  const colors = palette.colors && palette.colors.length > 0
    ? palette.colors
    : [palette.shadow, palette.base, palette.highlight, palette.accent];

  const getGridColsClass = (count: number) => {
    switch (count) {
      case 2:
        return 'grid-cols-1 sm:grid-cols-2';
      case 3:
        return 'grid-cols-1 sm:grid-cols-3';
      case 4:
        return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';
      default:
        return 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5';
    }
  };

  return (
    <LayoutGroup>
      <div className={`grid ${getGridColsClass(colors.length)} gap-4 sm:gap-6`}>
        {colors.map((color, idx) => (
          <ColorCard
            key={`${color.role}-${idx}`}
            color={color}
            index={idx}
            totalColors={colors.length}
            locale={locale}
          />
        ))}
      </div>
    </LayoutGroup>
  );
};
