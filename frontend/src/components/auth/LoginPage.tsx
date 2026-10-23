import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import {
  Sparkles,
  Eye,
  EyeOff,
  Mail,
  Lock,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  KeyRound,
} from 'lucide-react';

interface LoginPageProps {
  onNavigateToRegister: () => void;
  initialEmail?: string;
  initialMessage?: string;
}

export const LoginPage: React.FC<LoginPageProps> = ({
  onNavigateToRegister,
  initialEmail,
  initialMessage,
}) => {
  const {
    signInWithGoogle,
    signInWithEmail,
    resetPassword,
    authError,
    clearAuthError,
  } = useAuth();

  const [email, setEmail] = useState(initialEmail || '');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(initialMessage || null);
  const [showConfirmOption, setShowConfirmOption] = useState(false);
  const [confirming, setConfirming] = useState(false);

  // Sync initialEmail and initialMessage if they change
  React.useEffect(() => {
    if (initialEmail) setEmail(initialEmail);
    if (initialMessage) setSuccessMessage(initialMessage);
  }, [initialEmail, initialMessage]);

  // Forgot password sub-state
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetLoading, setResetLoading] = useState(false);

  const validateEmail = (val: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
  };

  const handleGoogleSignIn = async () => {
    setFormError(null);
    setSuccessMessage(null);
    clearAuthError();
    setGoogleLoading(true);
    try {
      await signInWithGoogle();
    } catch (err: any) {
      console.error('Google Sign In failed:', err);
      setFormError(err.message || 'Failed to initialize Google Sign In');
      setGoogleLoading(false);
    }
  };

  const handleConfirmAccount = async () => {
    if (!email.trim()) return;
    setConfirming(true);
    setFormError(null);
    try {
      const res = await api.confirmAccount(email.trim());
      setSuccessMessage(res.message || 'Email verified successfully! You can now sign in.');
      setShowConfirmOption(false);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Unable to verify account automatically.');
    } finally {
      setConfirming(false);
    }
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessMessage(null);
    setShowConfirmOption(false);
    clearAuthError();

    if (!email.trim() || !password) {
      setFormError('Please enter both your email and password.');
      return;
    }

    if (!validateEmail(email)) {
      setFormError('Please enter a valid email address (e.g., name@example.com).');
      return;
    }

    setLoading(true);
    try {
      const { data, error } = await signInWithEmail(email.trim(), password);
      if (error) {
        const errorMsg = error.message || '';
        const lowerMsg = errorMsg.toLowerCase();

        if (lowerMsg.includes('email not confirmed')) {
          setFormError('Your email address has not been confirmed yet. Click below to verify and activate your account.');
          setShowConfirmOption(true);
        } else if (lowerMsg.includes('invalid') || lowerMsg.includes('credentials')) {
          try {
            const methodInfo = await api.checkAuthMethod(email.trim());
            if (methodInfo.exists && methodInfo.has_google && !methodInfo.has_email) {
              setFormError('This account was created with Google Sign-In. You can click "Continue with Google" above to sign in directly.');
            } else if (!methodInfo.exists) {
              setFormError('No account found with this email. Please check for typos or click "Create New Account" below.');
            } else if (!methodInfo.is_confirmed) {
              setFormError('Your email address has not been confirmed yet. Click below to activate your account.');
              setShowConfirmOption(true);
            } else {
              setFormError('Incorrect email or password. Please verify your credentials or click "Forgot password?".');
            }
          } catch {
            setFormError('Incorrect email or password. Please verify your credentials or click "Forgot password?".');
          }
        } else if (lowerMsg.includes('network') || lowerMsg.includes('fetch')) {
          setFormError('Network connection error. Please verify your internet connection and try again.');
        } else {
          setFormError(errorMsg || 'Sign in failed. Please try again.');
        }
      } else if (data?.session) {
        setSuccessMessage('Authenticated successfully! Redirecting to dashboard...');
      }
    } catch (err: any) {
      setFormError(err.message || 'An unexpected error occurred during sign in.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessMessage(null);

    if (!resetEmail.trim() || !validateEmail(resetEmail)) {
      setFormError('Please enter a valid email address to receive password reset instructions.');
      return;
    }

    setResetLoading(true);
    try {
      const { error } = await resetPassword(resetEmail.trim());
      if (error) {
        setFormError(error.message || 'Unable to send password reset email.');
      } else {
        setSuccessMessage(`Password reset link sent to ${resetEmail.trim()}. Please check your inbox.`);
        setShowForgotPassword(false);
        setResetEmail('');
      }
    } catch (err: any) {
      setFormError(err.message || 'Error requesting password reset.');
    } finally {
      setResetLoading(false);
    }
  };

  const displayError = formError || authError;

  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem 1rem',
        background: 'radial-gradient(ellipse at top, rgba(99, 102, 241, 0.16), transparent 70%), var(--bg-main)',
      }}
    >
      <div
        className="glass-panel animate-fade-in"
        style={{
          width: '100%',
          maxWidth: '470px',
          padding: '2.5rem 2.25rem',
          borderRadius: 'var(--radius-lg, 18px)',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.45)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
          <div
            style={{
              width: '54px',
              height: '54px',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1rem',
              boxShadow: '0 8px 24px rgba(99, 102, 241, 0.35)',
            }}
          >
            <Sparkles size={26} color="white" />
          </div>

          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, margin: '0 0 0.35rem', lineHeight: 1.2 }}>
            Sign In to Synop<span className="gradient-text">AI</span>
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', margin: 0 }}>
            AI Video Synopsis & Meeting Transcription Platform
          </p>
        </div>

        {/* View Switcher Tabs: Sign In / Create New Account */}
        <div
          style={{
            display: 'flex',
            background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: '10px',
            padding: '4px',
            marginBottom: '1.75rem',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <button
            type="button"
            className="tab-btn active"
            style={{
              flex: 1,
              padding: '0.6rem 0.5rem',
              fontSize: '0.9rem',
              fontWeight: 700,
              borderRadius: '7px',
              background: 'var(--primary)',
              color: '#ffffff',
              border: 'none',
              cursor: 'default',
              boxShadow: '0 2px 8px rgba(99, 102, 241, 0.35)',
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={onNavigateToRegister}
            style={{
              flex: 1,
              padding: '0.6rem 0.5rem',
              fontSize: '0.9rem',
              fontWeight: 600,
              borderRadius: '7px',
              background: 'transparent',
              color: 'var(--text-muted)',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            Create New Account
          </button>
        </div>

        {/* Error / Alert Banner */}
        {displayError && (
          <div
            className="animate-fade-in"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.6rem',
              padding: '0.85rem 1rem',
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              borderRadius: 'var(--radius-sm, 8px)',
              color: '#fca5a5',
              fontSize: '0.85rem',
              marginBottom: '1.25rem',
              lineHeight: 1.4,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem' }}>
              <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} color="#ef4444" />
              <span style={{ flex: 1 }}>{displayError}</span>
            </div>

            {showConfirmOption && (
              <button
                type="button"
                onClick={handleConfirmAccount}
                disabled={confirming}
                style={{
                  alignSelf: 'flex-start',
                  marginTop: '0.2rem',
                  padding: '0.4rem 0.85rem',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  borderRadius: '6px',
                  background: '#ef4444',
                  color: '#ffffff',
                  border: 'none',
                  cursor: confirming ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  boxShadow: '0 2px 6px rgba(239, 68, 68, 0.4)',
                }}
              >
                <ShieldCheck size={14} />
                <span>{confirming ? 'Activating Account...' : 'Verify Email & Activate Account'}</span>
              </button>
            )}
          </div>
        )}

        {/* Success Alert */}
        {successMessage && (
          <div
            className="animate-fade-in"
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.65rem',
              padding: '0.85rem 1rem',
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.35)',
              borderRadius: 'var(--radius-sm, 8px)',
              color: '#6ee7b7',
              fontSize: '0.85rem',
              marginBottom: '1.25rem',
              lineHeight: 1.4,
            }}
          >
            <CheckCircle2 size={18} style={{ flexShrink: 0, marginTop: '2px' }} color="#10b981" />
            <span style={{ flex: 1 }}>{successMessage}</span>
          </div>
        )}

        {/* 1. Continue with Google */}
        <button
          onClick={handleGoogleSignIn}
          disabled={googleLoading || loading}
          type="button"
          style={{
            width: '100%',
            padding: '0.85rem 1.25rem',
            borderRadius: 'var(--radius-md, 10px)',
            background: '#ffffff',
            color: '#1f2937',
            border: 'none',
            fontWeight: 600,
            fontSize: '0.95rem',
            cursor: googleLoading || loading ? 'not-allowed' : 'pointer',
            opacity: googleLoading || loading ? 0.75 : 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.75rem',
            boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
            transition: 'all 0.2s ease',
            marginBottom: '1.5rem',
          }}
        >
          {googleLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div
                style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid #cbd5e1',
                  borderTopColor: '#4f46e5',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                }}
              />
              <span>Connecting to Google...</span>
            </div>
          ) : (
            <>
              <svg width="20" height="20" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>Continue with Google</span>
            </>
          )}
        </button>

        {/* Divider */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
            margin: '0 0 1.5rem',
            color: 'var(--text-muted)',
            fontSize: '0.8rem',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          <div style={{ flex: 1, height: '1px', background: 'var(--border-subtle)' }} />
          <span>Or sign in with email</span>
          <div style={{ flex: 1, height: '1px', background: 'var(--border-subtle)' }} />
        </div>

        {/* 2. Normal Email/Password Form */}
        {!showForgotPassword ? (
          <form onSubmit={handleSignIn} style={{ display: 'flex', flexDirection: 'column', gap: '1.15rem' }}>
            {/* Email Field */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  marginBottom: '0.4rem',
                  color: 'var(--text-main)',
                }}
              >
                Email Address
              </label>
              <div style={{ position: 'relative' }}>
                <Mail
                  size={18}
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                  }}
                />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                  required
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem 0.75rem 2.5rem',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md, 10px)',
                    color: 'var(--text-main)',
                    fontSize: '0.9rem',
                    outline: 'none',
                    transition: 'all 0.2s',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = 'var(--primary)')}
                  onBlur={(e) => (e.target.style.borderColor = 'var(--border-subtle)')}
                />
              </div>
            </div>

            {/* Password Field with Show/Hide toggle */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                <label
                  style={{
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-main)',
                  }}
                >
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowForgotPassword(true)}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    fontSize: '0.8rem',
                    color: 'var(--primary)',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  Forgot Password?
                </button>
              </div>
              <div style={{ position: 'relative' }}>
                <Lock
                  size={18}
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                  }}
                />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                  style={{
                    width: '100%',
                    padding: '0.75rem 2.75rem 0.75rem 2.5rem',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md, 10px)',
                    color: 'var(--text-main)',
                    fontSize: '0.9rem',
                    outline: 'none',
                    transition: 'all 0.2s',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = 'var(--primary)')}
                  onBlur={(e) => (e.target.style.borderColor = 'var(--border-subtle)')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    display: 'flex',
                  }}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || googleLoading}
              className="gradient-btn"
              style={{
                width: '100%',
                padding: '0.85rem',
                fontSize: '0.95rem',
                fontWeight: 700,
                borderRadius: 'var(--radius-md, 10px)',
                marginTop: '0.5rem',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.75 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
              }}
            >
              {loading ? (
                <span>Signing in...</span>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={17} />
                </>
              )}
            </button>
          </form>
        ) : (
          /* Forgot Password Box */
          <form onSubmit={handleResetPassword} style={{ display: 'flex', flexDirection: 'column', gap: '1.15rem' }}>
            <div style={{ textAlign: 'left' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: '0 0 0.35rem', color: 'var(--text-main)' }}>
                Reset Password
              </h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0 }}>
                Enter your email address and we'll send you instructions to reset your password.
              </p>
            </div>

            <div>
              <div style={{ position: 'relative' }}>
                <Mail
                  size={18}
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                  }}
                />
                <input
                  type="email"
                  value={resetEmail}
                  onChange={(e) => setResetEmail(e.target.value)}
                  placeholder="name@example.com"
                  required
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem 0.75rem 2.5rem',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md, 10px)',
                    color: 'var(--text-main)',
                    fontSize: '0.9rem',
                    outline: 'none',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                type="button"
                onClick={() => {
                  setShowForgotPassword(false);
                  setFormError(null);
                }}
                className="btn-secondary"
                style={{ flex: 1, padding: '0.75rem', fontSize: '0.85rem' }}
              >
                Back to Sign In
              </button>
              <button
                type="submit"
                disabled={resetLoading}
                className="gradient-btn"
                style={{ flex: 1, padding: '0.75rem', fontSize: '0.85rem', fontWeight: 600 }}
              >
                {resetLoading ? 'Sending...' : 'Send Reset Link'}
              </button>
            </div>
          </form>
        )}

        {/* Footer Navigation Link: Create New Account */}
        <div style={{ textAlign: 'center', marginTop: '1.75rem', fontSize: '0.88rem', color: 'var(--text-muted)' }}>
          Don't have an account yet?{' '}
          <button
            type="button"
            onClick={onNavigateToRegister}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              color: 'var(--primary)',
              fontWeight: 700,
              cursor: 'pointer',
              textDecoration: 'underline',
              marginLeft: '0.25rem',
            }}
          >
            Create New Account
          </button>
        </div>

        {/* Security Badges */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            marginTop: '1.5rem',
            color: 'var(--text-muted)',
            fontSize: '0.75rem',
          }}
        >
          <ShieldCheck size={14} color="#10b981" />
          <span>OAuth 2.0 PKCE Protected  •  256-bit SSL Encrypted</span>
        </div>
      </div>
    </div>
  );
};
