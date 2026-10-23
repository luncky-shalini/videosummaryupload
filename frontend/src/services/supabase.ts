import { createClient } from '@supabase/supabase-js';

const rawUrl = (import.meta.env.VITE_SUPABASE_URL || '').trim();
const rawKey = (
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  import.meta.env.SUPABASE_ANON_KEY ||
  ''
).trim();

const supabaseUrl = rawUrl ? rawUrl.replace(/\/+$/, '') : 'https://placeholder.supabase.co';
const supabaseAnonKey = rawKey || 'placeholder-anon-key';

if (supabaseAnonKey.startsWith('sb_secret_')) {
  console.error(
    '[Supabase Config Alert] VITE_SUPABASE_ANON_KEY is configured with a secret key (sb_secret_...). ' +
    'Browser PKCE flow requires the public "anon" key from Supabase Dashboard -> Project Settings -> API -> anon (public).'
  );
}

export const isSupabaseConfigured = () => {
  return (
    Boolean(rawUrl) &&
    rawUrl !== 'https://placeholder.supabase.co' &&
    Boolean(rawKey) &&
    rawKey !== 'placeholder-anon-key'
  );
};

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storage: typeof window !== 'undefined' ? window.localStorage : undefined,
    flowType: 'pkce',
  },
});

