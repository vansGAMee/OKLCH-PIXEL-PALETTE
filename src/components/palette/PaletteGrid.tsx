'use client';

import React from 'react';
import { LayoutGroup } from 'motion/react';
import { Palette } from '@/types/palette';
import { ColorCard } from './ColorCard';

interface PaletteGridProps {
  palette: Palette;
}

export const PaletteGrid: React.FC<PaletteGridProps> = ({ palette }) => {
  const colors = [
    palette.shadow,
    palette.base,
    palette.highlight,
    palette.accent,
  ];

  return (
    <LayoutGroup>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {colors.map((color, idx) => (
          <ColorCard key={color.role} color={color} index={idx} />
        ))}
      </div>
    </LayoutGroup>
  );
};
