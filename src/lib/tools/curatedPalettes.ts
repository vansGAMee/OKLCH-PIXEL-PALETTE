import { hexToOklch } from '@/lib/color/conversions';
import type { Palette, PaletteColor } from '@/types/palette';

export interface CuratedPalette {
  slug: string;
  title: string;
  titleRu: string;
  description: string;
  descriptionRu: string;
  tags: string[];
  hexes: string[];
  baseHex: string;
  harmony: 'splitComplementary' | 'complementary' | 'analogous' | 'triadic' | 'tetradic' | 'monochromatic';
}

export const CURATED_PALETTES: CuratedPalette[] = [
  {
    slug: 'winter-forest',
    title: 'Winter Forest',
    titleRu: 'Зимний лес',
    description: 'Cold pine greens, muted slate shadows, and crisp frost highlights for snowy woodland landscapes.',
    descriptionRu: 'Холодная сосновая зелень, приглушённые сланцевые тени и морозные светлые тона для заснеженных пейзажей.',
    tags: ['winter', 'forest', 'nature', 'cold', 'snow'],
    hexes: ['#0f172a', '#1e293b', '#064e3b', '#047857', '#10b981', '#6ee7b7', '#e0f2fe'],
    baseHex: '#047857',
    harmony: 'splitComplementary',
  },
  {
    slug: 'deep-sea-horror',
    title: 'Deep Sea Horror',
    titleRu: 'Глубоководный ужас',
    description: 'Abyssal navy blues, bioluminescent cyan highlights, and eerie toxic accents.',
    descriptionRu: 'Бездные тёмно-синие тона, биолюминесцентный циан и зловещие токсичные акценты.',
    tags: ['ocean', 'horror', 'abyss', 'dark', 'cyan'],
    hexes: ['#030712', '#082f49', '#0c4a6e', '#0284c7', '#38bdf8', '#a5f3fc', '#f43f5e'],
    baseHex: '#0c4a6e',
    harmony: 'splitComplementary',
  },
  {
    slug: 'neon-cyberpunk-rain',
    title: 'Neon Cyberpunk Rain',
    titleRu: 'Неоновый киберпанк под дождём',
    description: 'Dark wet asphalt with high-contrast magenta, violet, and electric cyan neon reflections.',
    descriptionRu: 'Тёмный мокрый асфальт с контрастными неоновыми отражениями мадженты, фиолетового и циана.',
    tags: ['cyberpunk', 'neon', 'night', 'retro', 'synthwave'],
    hexes: ['#09090b', '#18181b', '#3b0764', '#701a75', '#d946ef', '#38bdf8', '#f43f5e'],
    baseHex: '#701a75',
    harmony: 'triadic',
  },
  {
    slug: 'purple-cave',
    title: 'Purple Cave',
    titleRu: 'Фиолетовая пещера',
    description: 'Amethyst crystal minerals, deep cavern violet shadows, and glowing lavender gems.',
    descriptionRu: 'Аметистовые кристаллы, глубокие пещерные тени и сияющие лавандовые самоцветы.',
    tags: ['cave', 'crystal', 'purple', 'gem', 'dungeon'],
    hexes: ['#1e1b4b', '#2e1065', '#581c87', '#7c3aed', '#a855f7', '#c084fc', '#fdf4ff'],
    baseHex: '#581c87',
    harmony: 'monochromatic',
  },
  {
    slug: 'rusty-factory-sunset',
    title: 'Rusty Factory at Sunset',
    titleRu: 'Ржавый завод на закате',
    description: 'Weathered industrial iron, oxidized rust orange, warm copper, and dusk amber skies.',
    descriptionRu: 'Индустриальное окисленное железо, ржаво-оранжевый, тёплая медь и закатное янтарное небо.',
    tags: ['industrial', 'rust', 'sunset', 'warm', 'copper'],
    hexes: ['#1c1917', '#451a03', '#78350f', '#b45309', '#d97706', '#f59e0b', '#fef3c7'],
    baseHex: '#b45309',
    harmony: 'analogous',
  },
  {
    slug: 'toxic-swamp',
    title: 'Toxic Swamp',
    titleRu: 'Токсичное болото',
    description: 'Murky swamp mud, murky dark olives, and radioactive acid-green neon bubbles.',
    descriptionRu: 'Глубокая болотная грязь, оливковые полутени и радиоактивно-зелёные ядовитые акценты.',
    tags: ['swamp', 'toxic', 'acid', 'nature', 'monster'],
    hexes: ['#141a0e', '#1c2813', '#365314', '#4d7c0f', '#65a30d', '#a3e635', '#facc15'],
    baseHex: '#4d7c0f',
    harmony: 'analogous',
  },
  {
    slug: 'cozy-autumn-cafe',
    title: 'Cozy Autumn Cafe',
    titleRu: 'Уютное осеннее кафе',
    description: 'Warm roasted espresso, cinnamon spice, fallen autumn maple leaves, and cream foam.',
    descriptionRu: 'Тёплый эспрессо, корица, осенние кленовые листья и нежная кофейная пенка.',
    tags: ['autumn', 'cozy', 'warm', 'cafe', 'coffee'],
    hexes: ['#271c19', '#451a03', '#7c2d12', '#9a3412', '#c2410c', '#ea580c', '#ffedd5'],
    baseHex: '#9a3412',
    harmony: 'analogous',
  },
  {
    slug: 'frozen-lake',
    title: 'Frozen Lake',
    titleRu: 'Замёрзшее озеро',
    description: 'Deep glacial sub-zero blues, polished reflective ice tones, and cold pale white.',
    descriptionRu: 'Глубокий ледниковый синий, отполированные льдистые оттенки и холодный снежный белый.',
    tags: ['ice', 'winter', 'cold', 'water', 'glacier'],
    hexes: ['#082f49', '#075985', '#0284c7', '#38bdf8', '#7dd3fc', '#bae6fd', '#f0f9ff'],
    baseHex: '#0284c7',
    harmony: 'monochromatic',
  },
  {
    slug: 'moonlit-castle',
    title: 'Moonlit Castle',
    titleRu: 'Замок под луной',
    description: 'Cold stone masonry, night sky indigo, slate battlements, and pale silver moonlight.',
    descriptionRu: 'Холодная каменная кладка, ночной индиго, сланцевые башни и серебристый лунный свет.',
    tags: ['castle', 'night', 'moonlight', 'gothic', 'slate'],
    hexes: ['#0f172a', '#1e1b4b', '#312e81', '#4338ca', '#6366f1', '#a5b4fc', '#e0e7ff'],
    baseHex: '#312e81',
    harmony: 'splitComplementary',
  },
  {
    slug: 'desert-ruins',
    title: 'Desert Ruins',
    titleRu: 'Руины в пустыне',
    description: 'Sun-bleached sandstone, terracotta pottery, baked canyon clay, and warm desert breeze.',
    descriptionRu: 'Обожжённый солнцем песчаник, терракота, каньонная глина и тёплый пустынный бриз.',
    tags: ['desert', 'sand', 'ruins', 'warm', 'ancient'],
    hexes: ['#292524', '#57534e', '#78716c', '#a8a29e', '#d6d3d1', '#f59e0b', '#fef3c7'],
    baseHex: '#78716c',
    harmony: 'splitComplementary',
  },
  {
    slug: 'lava-dungeon',
    title: 'Lava Dungeon',
    titleRu: 'Подземелье лавы',
    description: 'Obsidian basalt rocks, fiery incandescent magma, and glowing crimson embers.',
    descriptionRu: 'Базальтовый обсидиан, раскалённая магма и пылающие багровые угли.',
    tags: ['lava', 'fire', 'dungeon', 'volcano', 'magma'],
    hexes: ['#18181b', '#450a0a', '#7f1d1d', '#b91c1c', '#dc2626', '#f97316', '#fef08a'],
    baseHex: '#7f1d1d',
    harmony: 'analogous',
  },
  {
    slug: 'emerald-ruins',
    title: 'Emerald Ruins',
    titleRu: 'Изумрудные руины',
    description: 'Ancient overgrown temple stones, jade vines, and luminescent emerald crystals.',
    descriptionRu: 'Камни заросшего древнего храма, нефритовые лианы и люминесцентные изумруды.',
    tags: ['emerald', 'ruins', 'jungle', 'temple', 'green'],
    hexes: ['#022c22', '#064e3b', '#065f46', '#047857', '#059669', '#34d399', '#a7f3d0'],
    baseHex: '#047857',
    harmony: 'monochromatic',
  },
];

export function getCuratedPalette(slug: string): CuratedPalette | undefined {
  return CURATED_PALETTES.find(p => p.slug === slug);
}

export function toFullPalette(curated: CuratedPalette): Palette {
  const colors: PaletteColor[] = curated.hexes.map((hex, idx) => {
    const oklch = hexToOklch(hex) ?? { l: 0.5, c: 0, h: null };
    return {
      role: idx === 0 ? 'shadow' : idx === 1 ? 'base' : idx === 2 ? 'highlight' : idx === 3 ? 'accent' : `color${idx + 1}`,
      hex,
      oklch,
    };
  });

  return {
    colors,
    count: colors.length,
    shadow: colors[0] ?? { role: 'shadow', hex: '#000000', oklch: { l: 0, c: 0, h: null } },
    base: colors[1] ?? colors[0],
    highlight: colors[2] ?? colors[0],
    accent: colors[3] ?? colors[0],
    harmony: curated.harmony,
    seed: 0,
  };
}
