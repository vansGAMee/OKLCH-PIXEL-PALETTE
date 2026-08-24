export type HarmonyMode =
  | 'splitComplementary'
  | 'complementary'
  | 'analogous'
  | 'triadic'
  | 'tetradic'
  | 'monochromatic';

export type PaletteGenerationMode = 'manual' | 'ai';

export type PaletteRole = 'shadow' | 'base' | 'highlight' | 'accent' | string;

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
  colors: PaletteColor[];
  count: number;
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
