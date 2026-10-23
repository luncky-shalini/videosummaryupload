import React, { useState, useEffect } from 'react';
import { Navbar } from './components/layout/Navbar';
import { Footer } from './components/layout/Footer';
import { AuthModal } from './components/auth/AuthModal';
import { LoginPage } from './components/auth/LoginPage';
import { RegisterPage } from './components/auth/RegisterPage';
import { UploadSection } from './components/upload/UploadSection';
import { VideoPlayer } from './components/player/VideoPlayer';
import { TranscriptViewer } from './components/transcript/TranscriptViewer';
import { SummaryDashboard } from './components/summary/SummaryDashboard';
import { VideoChatDrawer } from './components/chat/VideoChatDrawer';
import { ProjectHistory } from './components/history/ProjectHistory';
import { useAuth } from './context/AuthContext';
import { api } from './services/api';
import { Video, VideoDetail } from './types';
import { Loader2, MessageSquare, AlertCircle, RefreshCw, CheckCircle2, Sparkles } from 'lucide-react';

type AuthView = 'login' | 'register';

export const App: React.FC = () => {
  const { user, loading, authError, clearAuthError } = useAuth();
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showChatDrawer, setShowChatDrawer] = useState(false);

  // Auth Routing: 'login' (Sign In) | 'register' (Create Account)
  const [authView, setAuthView] = useState<AuthView>(() => {
    if (typeof window !== 'undefined' && (window.location.pathname === '/register' || window.location.pathname === '/signup')) {
      return 'register';
    }
    return 'login';
  });

  // Active Analysis State
  const [activeVideoId, setActiveVideoId] = useState<string | null>(null);
  const [videoDetail, setVideoDetail] = useState<VideoDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Synchronized Playback State
  const [currentTime, setCurrentTime] = useState(0);
  const [seekTime, setSeekTime] = useState<number | null>(null);

  // Theme effect
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      if (window.location.pathname === '/register' || window.location.pathname === '/signup') {
        setAuthView('register');
      } else {
        setAuthView('login');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // When user is authenticated, ensure clean URL path to dashboard
  useEffect(() => {
    if (user && (
      window.location.pathname === '/login' ||
      window.location.pathname === '/signin' ||
      window.location.pathname === '/sign-in' ||
      window.location.pathname === '/register' ||
      window.location.pathname === '/signup'
    )) {
      window.history.replaceState(null, '', '/');
    }
  }, [user]);

  // Normalize legacy /login or /signin URLs to /sign-in
  useEffect(() => {
    if (!user && (window.location.pathname === '/login' || window.location.pathname === '/signin')) {
      window.history.replaceState(null, '', '/sign-in');
    }
  }, [user]);

  const [loginPrefill, setLoginPrefill] = useState<{ email?: string; message?: string } | null>(null);

  const navigateToLogin = (prefillEmail?: string, message?: string) => {
    if (prefillEmail || message) {
      setLoginPrefill({ email: prefillEmail, message });
    }
    setAuthView('login');
    if (window.location.pathname !== '/sign-in') {
      window.history.pushState(null, '', '/sign-in');
    }
  };


  const navigateToRegister = () => {
    setAuthView('register');
    if (window.location.pathname !== '/register') {
      window.history.pushState(null, '', '/register');
    }
  };

  // Polling for processing status
  useEffect(() => {
    if (!activeVideoId) return;

    let intervalId: any = null;

    const checkStatus = async () => {
      try {
        const detail = await api.getVideoDetail(activeVideoId);
        setVideoDetail(detail);

        if (detail.video.status === 'completed' || detail.video.status === 'failed') {
          clearInterval(intervalId);
        }
      } catch (err) {
        console.error('Status check error:', err);
      }
    };

    // Load initial
    checkStatus();

    // Poll every 3 seconds if not completed
    intervalId = setInterval(checkStatus, 3000);
    return () => clearInterval(intervalId);
  }, [activeVideoId]);

  const handleVideoCreated = (video: Video) => {
    setActiveVideoId(video.id);
  };

  const handleSeek = (time: number) => {
    setSeekTime(time);
    setCurrentTime(time);
  };

  const handleSpeakerRenamed = async () => {
    if (activeVideoId) {
      const detail = await api.getVideoDetail(activeVideoId);
      setVideoDetail(detail);
    }
  };

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // 1. Session Restoration Loading Splash (Prevents login form from flashing on reload)
  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'radial-gradient(ellipse at top, rgba(99, 102, 241, 0.15), transparent 70%), var(--bg-main)',
          gap: '1.25rem',
        }}
      >
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 8px 24px rgba(99, 102, 241, 0.4)',
          }}
        >
          <Sparkles size={28} color="white" />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <Loader2 size={20} color="#6366f1" className="animate-spin" />
          <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-muted)' }}>
            Restoring secure session...
          </span>
        </div>
      </div>
    );
  }

  // 2. Unauthenticated: Display separate Login or Registration Page
  if (!user) {
    if (authView === 'register') {
      return <RegisterPage onNavigateToLogin={navigateToLogin} />;
    }
    return (
      <LoginPage
        onNavigateToRegister={navigateToRegister}
        initialEmail={loginPrefill?.email}
        initialMessage={loginPrefill?.message}
      />
    );
  }

  // 3. Authenticated: Render Main Application Dashboard

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        onOpenAuth={() => setShowAuthModal(true)}
        onOpenHistory={() => setShowHistoryModal(true)}
        onNewAnalysis={() => {
          setActiveVideoId(null);
          setVideoDetail(null);
        }}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <main style={{ flex: 1, maxWidth: '1400px', width: '100%', margin: '0 auto', padding: '0 1rem' }}>
        {authError && (
          <div
            className="animate-fade-in"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
              padding: '0.85rem 1.25rem',
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              borderRadius: 'var(--radius-md)',
              color: '#fca5a5',
              marginBottom: '1.5rem',
              fontSize: '0.9rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <AlertCircle size={18} color="#ef4444" />
              <span><strong>Google Sign-In Alert:</strong> {authError}</span>
            </div>
            <button
              onClick={clearAuthError}
              className="btn-secondary"
              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', borderColor: 'rgba(239, 68, 68, 0.4)' }}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* VIEW 1: No active video -> Upload Section */}
        {!activeVideoId && (
          <UploadSection
            onVideoCreated={handleVideoCreated}
            onOpenAuth={() => setShowAuthModal(true)}
            isAuthenticated={Boolean(user)}
          />
        )}

        {/* VIEW 2: Active video loading / processing */}
        {activeVideoId && videoDetail && videoDetail.video.status !== 'completed' && (
          <div style={{ maxWidth: '640px', margin: '4rem auto', textAlign: 'center' }}>
            <div className="glass-panel" style={{ padding: '3rem 2rem' }}>
              {videoDetail.video.status === 'failed' ? (
                <div>
                  <div
                    style={{
                      width: '64px',
                      height: '64px',
                      borderRadius: '50%',
                      background: 'rgba(239, 68, 68, 0.15)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      marginBottom: '1rem',
                    }}
                  >
                    <AlertCircle size={32} color="#ef4444" />
                  </div>
                  <h3 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                    Analysis Failed
                  </h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    {videoDetail.video.error_message || 'An unexpected error occurred during audio processing.'}
                  </p>
                  <button
                    onClick={() => setActiveVideoId(null)}
                    className="gradient-btn"
                    style={{ margin: '0 auto' }}
                  >
                    Try Another File
                  </button>
                </div>
              ) : (
                <div>
                  <div
                    style={{
                      width: '64px',
                      height: '64px',
                      borderRadius: '50%',
                      background: 'rgba(99, 102, 241, 0.15)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      marginBottom: '1rem',
                    }}
                  >
                    <Loader2 size={32} color="#6366f1" className="animate-spin" />
                  </div>
                  <h3 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                    Analyzing Your Recording
                  </h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    {videoDetail.video.status === 'extracting' && 'Extracting and optimizing audio streams...'}
                    {videoDetail.video.status === 'transcribing' && 'Transcribing spoken dialogue via Groq Whisper API...'}
                    {videoDetail.video.status === 'analyzing' && 'Identifying speakers, key topics, decisions, and synopses...'}
                    {videoDetail.video.status === 'pending' && 'Queued in background worker...'}
                  </p>

                  <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden', marginBottom: '0.75rem' }}>
                    <div
                      style={{
                        width: `${videoDetail.video.progress_percent || 20}%`,
                        height: '100%',
                        background: 'linear-gradient(90deg, #6366f1, #06b6d4)',
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-faint)' }}>
                    {videoDetail.video.progress_percent}% completed • You can safely close or navigate away
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* VIEW 3: Analysis Completed -> Full Synchronized Dashboard */}
        {activeVideoId && videoDetail && videoDetail.video.status === 'completed' && (
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Project Header */}
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.75rem', fontWeight: 800, margin: '0 0 0.25rem' }}>
                  {videoDetail.video.title}
                </h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  <span className="badge badge-success">
                    <CheckCircle2 size={12} /> Analysis Ready
                  </span>
                  <span>{videoDetail.video.file_type.toUpperCase()}</span>
                  <span>•</span>
                  <span>
                    Duration: {Math.floor((videoDetail.video.duration_seconds || 0) / 60)}m{' '}
                    {Math.floor((videoDetail.video.duration_seconds || 0) % 60)}s
                  </span>
                </div>
              </div>

              {/* Chat with AI Button */}
              <button onClick={() => setShowChatDrawer(true)} className="gradient-btn">
                <MessageSquare size={16} />
                <span>Ask AI Video Assistant</span>
              </button>
            </div>

            {/* Main Split Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
                gap: '1.5rem',
                alignItems: 'start',
              }}
            >
              {/* Left Column: Player & Transcript */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <VideoPlayer
                  videoId={videoDetail.video.id}
                  currentTime={currentTime}
                  seekTime={seekTime}
                  onTimeUpdate={setCurrentTime}
                  videoTitle={videoDetail.video.title}
                  initialSegments={videoDetail.transcript?.segments || []}
                  detectedLanguage={videoDetail.transcript?.language || 'en'}
                  sourceUrl={videoDetail.video.source_url}
                  fileType={videoDetail.video.file_type}
                />

                {videoDetail.transcript && (
                  <TranscriptViewer
                    videoId={videoDetail.video.id}
                    segments={videoDetail.transcript.segments || []}
                    language={videoDetail.transcript.language || 'en'}
                    currentTime={currentTime}
                    onSeek={handleSeek}
                    onSpeakerRenamed={handleSpeakerRenamed}
                  />
                )}
              </div>

              {/* Right Column: AI Synopses, Decisions & Tasks */}
              <div>
                {videoDetail.summary && (
                  <SummaryDashboard
                    summary={videoDetail.summary}
                    video={videoDetail.video}
                    onSeek={handleSeek}
                  />
                )}
              </div>

            </div>
          </div>
        )}
      </main>

      {/* Floating Chat Drawer */}
      {activeVideoId && (
        <VideoChatDrawer
          videoId={activeVideoId}
          isOpen={showChatDrawer}
          onClose={() => setShowChatDrawer(false)}
          onSeek={handleSeek}
        />
      )}

      {/* Modals */}
      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />

      {showHistoryModal && (
        <ProjectHistory
          onSelectVideo={(id) => setActiveVideoId(id)}
          onClose={() => setShowHistoryModal(false)}
        />
      )}

      <Footer />
    </div>
  );
};
