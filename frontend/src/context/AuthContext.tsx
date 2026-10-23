import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '../services/supabase';
import { api } from '../services/api';


export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'error';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  authStatus: AuthStatus;
  authError: string | null;
  isConfigured: boolean;
  clearAuthError: () => void;
  signInWithGoogle: () => Promise<void>;
  switchGoogleAccount: () => Promise<void>;
  signInWithEmail: (email: string, pass: string) => Promise<{ data?: any; error: any }>;
  signUpWithEmail: (email: string, pass: string, fullName?: string) => Promise<{ data?: any; error: any }>;
  resetPassword: (email: string) => Promise<{ data?: any; error: any }>;
  signOut: () => Promise<void>;
  useGuestMode: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const isConfigured = isSupabaseConfigured();

  useEffect(() => {
    let isMounted = true;

    // 1. Inspect URL parameters for OAuth errors from provider (e.g., access_denied)
    const hashParams = new URLSearchParams(window.location.hash.substring(1));
    const searchParams = new URLSearchParams(window.location.search);
    const errorDesc =
      hashParams.get('error_description') ||
      searchParams.get('error_description') ||
      hashParams.get('error') ||
      searchParams.get('error');

    if (errorDesc) {
      const decoded = decodeURIComponent(errorDesc.replace(/\+/g, ' '));
      console.error('Google OAuth callback error detected:', decoded);
      if (isMounted) setAuthError(decoded);
      if (window.history.replaceState) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    }

    if (!isConfigured) {
      if (isMounted) setLoading(false);
      return;
    }

    // 2. Verify initial session via getSession() & getUser()
    // Supabase client with detectSessionInUrl: true automatically processes
    // the PKCE ?code= parameter during initialization and emits SIGNED_IN or INITIAL_SESSION.
    // 2. Subscribe to auth state changes (INITIAL_SESSION, SIGNED_IN, SIGNED_OUT, TOKEN_REFRESHED, USER_UPDATED)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, currentSession) => {
      console.log('Supabase onAuthStateChange:', event, currentSession?.user?.email || 'No active session');
      if (!isMounted) return;

      if (currentSession?.user) {
        setSession(currentSession);
        setUser(currentSession.user);
        setAuthError(null);
        syncProfileToDatabase(currentSession.user);
        if (typeof window !== 'undefined' && window.location.search.includes('code=')) {
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      } else if (event === 'INITIAL_SESSION' || event === 'SIGNED_OUT' || !currentSession) {
        // Correctly handle missing initial session without treating as error or calling getUser()
        setUser(null);
        setSession(null);
      } else {
        setUser(null);
        setSession(null);
      }
      setLoading(false);
    });

    // Safeguard: in case onAuthStateChange is delayed, ensure loading is cleared via getSession()
    supabase.auth
      .getSession()
      .then(({ data: { session: fallbackSession }, error: sessionError }) => {
        if (!isMounted) return;
        if (sessionError) {
          console.warn('Supabase getSession note:', sessionError.message);
        }
        if (fallbackSession?.user) {
          setSession(fallbackSession);
          setUser(fallbackSession.user);
          setAuthError(null);
          syncProfileToDatabase(fallbackSession.user);
          if (typeof window !== 'undefined' && window.location.search.includes('code=')) {
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        }
        setLoading(false);
      })
      .catch((err) => {
        console.warn('Session check finished:', err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [isConfigured]);

  const syncProfileToDatabase = async (currentUser: User) => {
    if (!currentUser || !isConfigured) return;
    try {
      const fullName =
        currentUser.user_metadata?.full_name ||
        currentUser.user_metadata?.name ||
        (currentUser.email ? currentUser.email.split('@')[0] : 'Google User');
      const avatarUrl =
        currentUser.user_metadata?.avatar_url ||
        currentUser.user_metadata?.picture ||
        null;

      await supabase.from('profiles').upsert(
        {
          id: currentUser.id,
          email: currentUser.email || '',
          full_name: fullName,
          avatar_url: avatarUrl,
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'id' }
      );
    } catch (e) {
      console.debug('Client-side profile sync (non-critical):', e);
    }
  };

  const signInWithGoogle = async () => {
    setAuthError(null);
    if (!isConfigured) {
      const msg = 'Supabase is not configured yet. Please check your environment variables.';
      setAuthError(msg);
      alert(msg);
      return;
    }
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/`,
        queryParams: {
          prompt: 'select_account',
          access_type: 'offline',
        },
      },
    });
    if (error) {
      setAuthError(error.message);
      throw error;
    }
  };

  const switchGoogleAccount = async () => {
    setAuthError(null);
    try {
      if (isConfigured) {
        await supabase.auth.signOut();
      }
    } catch (e) {
      console.warn('Signout before switch account:', e);
    } finally {
      setUser(null);
      setSession(null);
    }
    await signInWithGoogle();
  };

  const signInWithEmail = async (email: string, pass: string) => {
    if (!isConfigured) return { error: new Error('Supabase not configured') };
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password: pass,
    });
    if (data?.session) {
      setSession(data.session);
      setUser(data.session.user);
      setAuthError(null);
      syncProfileToDatabase(data.session.user);
    }
    return { data, error };
  };

  const signUpWithEmail = async (email: string, pass: string, fullName?: string) => {
    if (!isConfigured) return { error: new Error('Supabase not configured') };
    
    // Existing Supabase registration flow
    const { data, error } = await supabase.auth.signUp({
      email,
      password: pass,
      options: {
        data: { full_name: fullName, name: fullName },
      },
    });

    if (error) {
      // Fallback via backend only if Supabase free-tier SMTP rate limit is reached
      if (error.message?.toLowerCase().includes('rate limit')) {
        try {
          await api.registerUser(email, pass, fullName);
          return { data: { user: { email } }, error: null };
        } catch (apiErr: any) {
          return { data: null, error: apiErr.response?.data?.detail ? new Error(apiErr.response.data.detail) : error };
        }
      }
      return { data, error };
    }

    // Ensure session is cleared locally so the user transitions to the Sign In page
    if (data?.session) {
      try {
        await supabase.auth.signOut({ scope: 'local' });
      } catch {}
    }
    return { data, error };
  };

  const resetPassword = async (email: string) => {
    if (!isConfigured) return { error: new Error('Supabase not configured') };
    const { data, error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/`,
    });
    return { data, error };
  };

  const signOut = async () => {
    try {
      if (isConfigured) {
        await supabase.auth.signOut();
      }
    } catch (err) {
      console.error('SignOut error:', err);
    } finally {
      setUser(null);
      setSession(null);
      setAuthError(null);
      if (typeof window !== 'undefined') {
        try {
          sessionStorage.clear();
          if (window.location.pathname !== '/sign-in') {
            window.history.pushState(null, '', '/sign-in');
          }
        } catch (e) {}
      }
    }
  };

  const useGuestMode = () => {
    // Demo placeholder details removed. Normal authentication must use genuine Google OAuth.
    console.info('Guest placeholder mode is disabled. Please use "Continue with Google" for authentication.');
  };

  const authStatus: AuthStatus = loading
    ? 'loading'
    : authError
    ? 'error'
    : user
    ? 'authenticated'
    : 'unauthenticated';

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        loading,
        authStatus,
        authError,
        isConfigured,
        clearAuthError: () => setAuthError(null),
        signInWithGoogle,
        switchGoogleAccount,
        signInWithEmail,
        signUpWithEmail,
        resetPassword,
        signOut,
        useGuestMode,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
