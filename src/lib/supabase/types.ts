/**
 * src/lib/supabase/types.ts
 * TypeScript types matching the database schema.
 * Manually authored — regenerate with `supabase gen types typescript` after connecting CLI.
 */

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;
          username: string;
          display_name: string | null;
          bio: string | null;
          locale: string;
          avatar_seed: string | null;
          role: 'user' | 'admin';
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id: string;
          username: string;
          display_name?: string | null;
          bio?: string | null;
          locale?: string;
          avatar_seed?: string | null;
          role?: 'user' | 'admin';
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          username?: string;
          display_name?: string | null;
          bio?: string | null;
          locale?: string;
          avatar_seed?: string | null;
          updated_at?: string;
        };
      };
      palettes: {
        Row: {
          id: string;
          owner_id: string;
          slug: string;
          title: string;
          description: string | null;
          colors: Json;
          color_count: number;
          base_hex: string | null;
          harmony: string | null;
          seed: number | null;
          tags: string[] | null;
          visibility: 'private' | 'unlisted' | 'public';
          featured_position: 1 | 2 | 3 | null;
          source_palette_id: string | null;
          remix_settings: Json | null;
          created_at: string;
          updated_at: string;
          published_at: string | null;
        };
        Insert: {
          id?: string;
          owner_id: string;
          slug: string;
          title: string;
          description?: string | null;
          colors: Json;
          color_count: number;
          base_hex?: string | null;
          harmony?: string | null;
          seed?: number | null;
          tags?: string[] | null;
          visibility?: 'private' | 'unlisted' | 'public';
          featured_position?: 1 | 2 | 3 | null;
          source_palette_id?: string | null;
          remix_settings?: Json | null;
          created_at?: string;
          updated_at?: string;
          published_at?: string | null;
        };
        Update: {
          slug?: string;
          title?: string;
          description?: string | null;
          colors?: Json;
          color_count?: number;
          base_hex?: string | null;
          harmony?: string | null;
          seed?: number | null;
          tags?: string[] | null;
          visibility?: 'private' | 'unlisted' | 'public';
          featured_position?: 1 | 2 | 3 | null;
          source_palette_id?: string | null;
          remix_settings?: Json | null;
          updated_at?: string;
          published_at?: string | null;
        };
      };
      palette_likes: {
        Row: {
          user_id: string;
          palette_id: string;
          created_at: string;
        };
        Insert: {
          user_id: string;
          palette_id: string;
          created_at?: string;
        };
        Update: never;
      };
      palette_bookmarks: {
        Row: {
          user_id: string;
          palette_id: string;
          created_at: string;
        };
        Insert: {
          user_id: string;
          palette_id: string;
          created_at?: string;
        };
        Update: never;
      };
      palette_events: {
        Row: {
          id: number;
          user_id: string;
          palette_id: string | null;
          event_name: PaletteEventName;
          export_format: string | null;
          created_at: string;
        };
        Insert: {
          user_id: string;
          palette_id?: string | null;
          event_name: PaletteEventName;
          export_format?: string | null;
          created_at?: string;
        };
        Update: never;
      };
    };
    Views: Record<string, never>;
    Functions: {
      check_public_palette_limit: {
        Args: { uid: string };
        Returns: boolean;
      };
      check_saved_palette_limit: {
        Args: { uid: string };
        Returns: boolean;
      };
    };
    Enums: Record<string, never>;
  };
}

export type PaletteEventName =
  | 'palette_generated'
  | 'palette_saved'
  | 'palette_published'
  | 'palette_remixed'
  | 'palette_exported';

export type Profile = Database['public']['Tables']['profiles']['Row'];
export type PaletteRow = Database['public']['Tables']['palettes']['Row'];
export type PaletteLike = Database['public']['Tables']['palette_likes']['Row'];
export type PaletteBookmark = Database['public']['Tables']['palette_bookmarks']['Row'];
export type PaletteEvent = Database['public']['Tables']['palette_events']['Row'];
