import { User } from '@supabase/supabase-js';

/**
 * Extracts the user's authentic display name from Supabase user metadata.
 * Prioritizes full_name, name, display_name, and falls back to email username.
 */
export const getUserDisplayName = (user: User | null): string => {
  if (!user) return '';
  return (
    user.user_metadata?.full_name ||
    user.user_metadata?.name ||
    user.user_metadata?.display_name ||
    (user.email ? user.email.split('@')[0] : 'User')
  );
};

/**
 * Extracts the user's authentic avatar URL from Supabase user metadata (Google picture or custom avatar).
 */
export const getUserAvatarUrl = (user: User | null): string | null => {
  if (!user) return null;
  return user.user_metadata?.avatar_url || user.user_metadata?.picture || null;
};
