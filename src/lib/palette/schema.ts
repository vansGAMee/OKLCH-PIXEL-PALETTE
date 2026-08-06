/**
 * src/lib/palette/schema.ts
 * Zod schema for palette validation — shared client and server.
 */
import { z } from 'zod';

export const PaletteColorSchema = z.object({
  role: z.string().min(1).max(32),
  hex: z.string().regex(/^#[0-9a-fA-F]{6}$/, 'Invalid HEX color'),
  oklch: z.object({
    l: z.number().min(0).max(1),
    c: z.number().min(0).max(0.4),
    h: z.number().min(0).max(360).nullable(),
  }),
});

export const PaletteSchema = z.object({
  colors: z.array(PaletteColorSchema).min(2).max(9),
  count: z.number().int().min(2).max(9),
  shadow: PaletteColorSchema,
  base: PaletteColorSchema,
  highlight: PaletteColorSchema,
  accent: PaletteColorSchema,
  harmony: z.enum(['splitComplementary', 'complementary', 'analogous', 'triadic', 'tetradic', 'monochromatic']),
  seed: z.number().int().min(0),
});

export const SavePaletteInputSchema = z.object({
  title: z.string().min(1, 'Title is required').max(80, 'Title too long'),
  description: z.string().max(500, 'Description too long').optional(),
  tags: z.array(z.string().min(1).max(32)).max(8).optional(),
  visibility: z.enum(['private', 'unlisted', 'public']).default('private'),
  palette: PaletteSchema,
});

export type SavePaletteInput = z.infer<typeof SavePaletteInputSchema>;
export type PaletteColorData = z.infer<typeof PaletteColorSchema>;
export type PaletteData = z.infer<typeof PaletteSchema>;
