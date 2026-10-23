import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  User as UserIcon,
  LogOut,
  Moon,
  Sun,
  PlusCircle,
  History,
  RefreshCw,
  ChevronDown,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getUserDisplayName, getUserAvatarUrl } from '../../utils/user';

interface NavbarProps {
  onOpenAuth: () => void;
  onOpenHistory: () => void;
  onNewAnalysis: () => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  onOpenAuth,
  onOpenHistory,
  onNewAnalysis,
  theme,
  onToggleTheme,
}) => {
  const { user, signOut, switchGoogleAccount } = useAuth();
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowProfileMenu(false);
      }
    };
    if (showProfileMenu) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [showProfileMenu]);

  const handleLogout = async () => {
    setShowProfileMenu(false);
    await signOut();
  };

  const displayName = getUserDisplayName(user);
  const avatarUrl = getUserAvatarUrl(user);
  const isGoogleProvider =
    user?.app_metadata?.provider === 'google' ||
    Boolean(user?.user_metadata?.avatar_url || user?.user_metadata?.picture);

  return (
    <header className="glass-panel sticky top-4 z-50 mx-4 lg:mx-auto max-w-7xl px-5 py-3 mb-8">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        {/* Top-Left: Brand Logo & User Profile Area */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
          {/* Brand Logo */}
          <div
            onClick={onNewAnalysis}
            style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', cursor: 'pointer' }}
            title="SynopAI Home"
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 12px rgba(99, 102, 241, 0.4)',
              }}
            >
              <Sparkles size={19} color="white" />
            </div>
            <div>
              <h1 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, lineHeight: 1.1 }}>
                Synop<span className="gradient-text">AI</span>
              </h1>
              <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: 0 }}>
                Video & Meeting Intelligence
              </p>
            </div>
          </div>

          {/* Mandatory Top-Left Profile Section (Displays Actual Logged-in Name and Gmail) */}
          {user && (
            <div ref={menuRef} style={{ position: 'relative' }}>
              <div
                onClick={() => setShowProfileMenu((prev) => !prev)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '0.35rem 0.85rem 0.35rem 0.5rem',
                  background: 'rgba(16, 185, 129, 0.08)',
                  borderRadius: '9999px',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  userSelect: 'none',
                }}
                title="Click to open profile options"
              >
                {/* Profile Picture or Initials */}
                {avatarUrl ? (
                  <img
                    src={avatarUrl}
                    alt={displayName}
                    referrerPolicy="no-referrer"
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '50%',
                      objectFit: 'cover',
                      border: '2px solid #10b981',
                      flexShrink: 0,
                    }}
                  />
                ) : (
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #10b981, #06b6d4)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      color: 'white',
                      flexShrink: 0,
                    }}
                  >
                    {(displayName || user.email || 'U')[0].toUpperCase()}
                  </div>
                )}

                {/* Actual Logged-in Account Details */}
                <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', lineHeight: 1.15 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <span
                      style={{
                        width: '7px',
                        height: '7px',
                        borderRadius: '50%',
                        background: '#10b981',
                        display: 'inline-block',
                      }}
                    />
                    <span
                      style={{
                        fontSize: '0.85rem',
                        fontWeight: 700,
                        color: 'var(--text-main)',
                        letterSpacing: '-0.01em',
                      }}
                    >
                      {displayName}
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      color: '#10b981',
                      fontWeight: 500,
                    }}
                  >
                    {user.email}
                  </span>
                </div>

                <ChevronDown
                  size={15}
                  color="var(--text-muted)"
                  style={{
                    transform: showProfileMenu ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s ease',
                  }}
                />
              </div>

              {/* Top-Left Profile Dropdown Menu */}
              {showProfileMenu && (
                <div
                  className="glass-panel animate-fade-in"
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 8px)',
                    left: 0,
                    width: '280px',
                    padding: '1rem',
                    borderRadius: 'var(--radius-md, 12px)',
                    boxShadow: '0 12px 32px rgba(0,0,0,0.4)',
                    border: '1px solid var(--border-subtle)',
                    zIndex: 100,
                  }}
                >
                  <div style={{ marginBottom: '0.75rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-subtle)' }}>
                    <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '0 0 0.35rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Signed In As
                    </p>
                    <p style={{ fontSize: '0.92rem', fontWeight: 700, margin: '0 0 0.2rem', color: 'var(--text-main)' }}>
                      {displayName}
                    </p>
                    <p style={{ fontSize: '0.78rem', color: '#10b981', margin: '0 0 0.4rem', wordBreak: 'break-all' }}>
                      {user.email}
                    </p>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.7rem', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.06)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                      <ShieldCheck size={12} color="#10b981" />
                      <span>{isGoogleProvider ? 'Google OAuth Account' : 'Verified Email Account'}</span>
                    </div>
                  </div>

                  {isGoogleProvider && (
                    <button
                      type="button"
                      onClick={() => {
                        setShowProfileMenu(false);
                        switchGoogleAccount();
                      }}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.65rem',
                        padding: '0.6rem 0.75rem',
                        background: 'transparent',
                        border: 'none',
                        borderRadius: 'var(--radius-sm, 6px)',
                        color: 'var(--text-main)',
                        fontSize: '0.84rem',
                        fontWeight: 500,
                        cursor: 'pointer',
                        textAlign: 'left',
                        marginBottom: '0.35rem',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <RefreshCw size={15} color="var(--primary, #6366f1)" />
                      <span>Switch Google Account</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={handleLogout}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.65rem',
                      padding: '0.6rem 0.75rem',
                      background: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.25)',
                      borderRadius: 'var(--radius-sm, 6px)',
                      color: '#f87171',
                      fontSize: '0.84rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)')}
                  >
                    <LogOut size={15} color="#ef4444" />
                    <span>Log Out</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Top-Right: Navigation & Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            onClick={onNewAnalysis}
            className="btn-secondary"
            title="Start new video analysis"
          >
            <PlusCircle size={16} />
            <span className="hidden-mobile">New Analysis</span>
          </button>

          {user && (
            <button
              onClick={onOpenHistory}
              className="btn-secondary"
              title="View previous analyses"
            >
              <History size={16} />
              <span className="hidden-mobile">My Videos</span>
            </button>
          )}

          <button
            onClick={onToggleTheme}
            className="btn-secondary"
            style={{ padding: '0.65rem' }}
            title="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>

          {user ? (
            <button
              onClick={handleLogout}
              className="btn-secondary"
              style={{
                padding: '0.55rem 0.85rem',
                fontSize: '0.82rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                borderColor: 'rgba(239, 68, 68, 0.3)',
                color: '#fca5a5',
              }}
              title="Sign out of your account"
            >
              <LogOut size={15} />
              <span>Sign Out</span>
            </button>
          ) : (
            <button onClick={onOpenAuth} className="gradient-btn" title="Sign in to SynopAI">
              <UserIcon size={16} />
              <span>Sign In</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

