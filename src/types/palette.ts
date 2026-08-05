export type HarmonyMode = 'splitComplementary' | 'complementary' | 'analogous';

export type PaletteRole = 'shadow' | 'base' | 'highlight' | 'accent';

export type PaletteColor = {
  role: PaletteRole;
  hex: string;
  oklch: {
    l: number;
    c: number;
    h: number | null;
  };
};

export type Palette = {
  shadow: PaletteColor;
  base: PaletteColor;
  highlight: PaletteColor;
  accent: PaletteColor;
  harmony: HarmonyMode;
  seed: number;
};

export type OklchColor = {
  l: number;
  c: number;
  h: number | null;
};
