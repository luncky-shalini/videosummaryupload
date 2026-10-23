import React, { useRef, useEffect, useState, useMemo } from 'react';
import {
  RotateCcw,
  RotateCw,
  Subtitles,
  Languages,
  Check,
  AlertCircle,
  Loader2,
  RefreshCw,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Gauge,
} from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { TranscriptSegment } from '../../types';

interface VideoPlayerProps {
  videoId: string;
  currentTime: number;
  seekTime: number | null;
  onTimeUpdate: (time: number) => void;
  videoTitle: string;
  initialSegments?: TranscriptSegment[];
  detectedLanguage?: string;
  sourceUrl?: string;
  fileType?: string;
}

interface LanguageOption {
  code: string;
  name: string;
  nativeName: string;
}

const SUPPORTED_LANGUAGES: LanguageOption[] = [
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు' },
  { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी' },
  { code: 'es', name: 'Spanish', nativeName: 'Español' },
  { code: 'zh', name: 'Chinese', nativeName: '中文' },
  { code: 'it', name: 'Italian', nativeName: 'Italiano' },
  { code: 'bn', name: 'Bengali', nativeName: 'বাংলা' },
  { code: 'fr', name: 'French', nativeName: 'Français' },
  { code: 'de', name: 'German', nativeName: 'Deutsch' },
  { code: 'ja', name: 'Japanese', nativeName: '日本語' },
  { code: 'pt', name: 'Portuguese', nativeName: 'Português' },
  { code: 'ru', name: 'Russian', nativeName: 'Русский' },
  { code: 'ar', name: 'Arabic', nativeName: 'العربية' },
];

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  videoId,
  currentTime,
  seekTime,
  onTimeUpdate,
  videoTitle,
  initialSegments = [],
  detectedLanguage = 'en',
  sourceUrl,
  fileType,
}) => {
  const { session } = useAuth();
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Stream URL with auth token query param so browser native media engine authenticates cleanly
  const token = session?.access_token;
  const streamUrl = useMemo(() => api.getVideoStreamUrl(videoId, token), [videoId, token]);

  // CC & Subtitles State
  const [ccEnabled, setCcEnabled] = useState(true);
  const [selectedLanguage, setSelectedLanguage] = useState<string>('English');
  const [activeLanguage, setActiveLanguage] = useState<string>('English');
  const [subtitleTracks, setSubtitleTracks] = useState<Record<string, TranscriptSegment[]>>({});
  const [isTranslating, setIsTranslating] = useState(false);
  const [translationMessage, setTranslationMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Video Player States
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [playbackRateOpen, setPlaybackRateOpen] = useState(false);

  // Extract YouTube ID if video is imported from YouTube
  const youtubeId = useMemo(() => {
    if (!sourceUrl) return null;
    const match = sourceUrl.match(
      /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([^"&?\/\s]{11})/i
    );
    return match ? match[1] : null;
  }, [sourceUrl]);
  const [useYouTubeEmbed, setUseYouTubeEmbed] = useState(false);

  // Map detected original language code to name
  const { originalLanguageName, originalLanguageCode } = useMemo(() => {
    const code = (detectedLanguage || 'en').toLowerCase().split('-')[0].split('_')[0];
    const found = SUPPORTED_LANGUAGES.find(
      (l) => l.code === code || l.name.toLowerCase() === code
    );
    return {
      originalLanguageName: found ? found.name : 'English',
      originalLanguageCode: found ? found.code : 'en',
    };
  }, [detectedLanguage]);

  // Seed original subtitle track on mount or when initialSegments / videoId change
  useEffect(() => {
    // Reset tracks when switching to a different video project
    const newTracks: Record<string, TranscriptSegment[]> = {};
    if (initialSegments && initialSegments.length > 0) {
      newTracks[originalLanguageName] = initialSegments;
      newTracks[originalLanguageCode] = initialSegments;
    }
    setSubtitleTracks(newTracks);
    // Default to original language initially
    setActiveLanguage(originalLanguageName);
    setSelectedLanguage(originalLanguageName);
    setPlaybackError(null);
    setTranslationMessage(null);
    setUseYouTubeEmbed(false);
  }, [videoId, initialSegments, originalLanguageName, originalLanguageCode]);

  // Jump to seek timestamp when requested by external components (transcript, moments)
  useEffect(() => {
    if (seekTime !== null && videoRef.current) {
      videoRef.current.currentTime = seekTime;
      videoRef.current.play().catch(() => {});
    }
  }, [seekTime]);

  // Time update handler
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  const skipSeconds = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime + seconds);
    }
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
    if (videoRef.current) {
      videoRef.current.playbackRate = speed;
    }
    setPlaybackRateOpen(false);
  };

  // Find active subtitle segment matching current time (safely parsing numeric timestamps)
  const currentSubtitles = subtitleTracks[activeLanguage] || subtitleTracks[selectedLanguage] || initialSegments;
  const activeSubtitle = useMemo(() => {
    if (!ccEnabled || !currentSubtitles || currentSubtitles.length === 0) return null;
    return currentSubtitles.find((s) => {
      const start = Number(s.start_time);
      const end = Number(s.end_time);
      if (isNaN(start) || isNaN(end)) return false;
      return currentTime >= start && currentTime <= end + 0.25;
    });
  }, [ccEnabled, currentSubtitles, currentTime]);

  // Switch subtitle track immediately when an existing or original language is selected
  const handleLanguageSelect = (newLanguage: string) => {
    setSelectedLanguage(newLanguage);
    const isOrig = newLanguage.toLowerCase() === originalLanguageName.toLowerCase();
    const existingTrack = subtitleTracks[newLanguage] || (isOrig ? initialSegments : undefined);

    if (existingTrack && existingTrack.length > 0) {
      if (!subtitleTracks[newLanguage] && isOrig) {
        setSubtitleTracks((prev) => ({
          ...prev,
          [originalLanguageName]: initialSegments,
          [originalLanguageCode]: initialSegments,
        }));
      }
      setActiveLanguage(newLanguage);
      if (!ccEnabled) setCcEnabled(true);
      setTranslationMessage({
        type: 'success',
        text: isOrig ? `Active subtitles: ${originalLanguageName} (Original)` : `Switched to ${newLanguage} subtitles`,
      });
      setTimeout(() => setTranslationMessage(null), 2500);
    }
  };

  // Handle subtitle translation request
  const handleTranslateSubtitles = async () => {
    setTranslationMessage(null);
    if (!selectedLanguage) return;

    // Ensure CC is enabled so user sees the subtitles
    if (!ccEnabled) {
      setCcEnabled(true);
    }

    // 1. If target language is already cached, apply immediately without re-translating
    if (subtitleTracks[selectedLanguage] && subtitleTracks[selectedLanguage].length > 0) {
      setActiveLanguage(selectedLanguage);
      setTranslationMessage({
        type: 'success',
        text: `Switched to ${selectedLanguage} subtitles`,
      });
      setTimeout(() => setTranslationMessage(null), 3000);
      return;
    }

    // 2. If target language matches detected original language, use initialSegments
    if (selectedLanguage.toLowerCase() === originalLanguageName.toLowerCase()) {
      setSubtitleTracks((prev) => ({
        ...prev,
        [originalLanguageName]: initialSegments,
        [originalLanguageCode]: initialSegments,
      }));
      setActiveLanguage(originalLanguageName);
      setTranslationMessage({
        type: 'success',
        text: `Active subtitles: ${originalLanguageName} (Original)`,
      });
      setTimeout(() => setTranslationMessage(null), 3000);
      return;
    }

    // 3. Call backend subtitle translation
    setIsTranslating(true);
    try {
      const res = await api.translateSubtitles(videoId, selectedLanguage);
      if (res && res.segments && res.segments.length > 0) {
        const canonicalName = res.target_language || selectedLanguage;
        const canonicalCode = res.target_language_code;

        setSubtitleTracks((prev) => {
          const updated = {
            ...prev,
            [selectedLanguage]: res.segments,
            [canonicalName]: res.segments,
          };
          if (canonicalCode) {
            updated[canonicalCode] = res.segments;
          }
          return updated;
        });
        setActiveLanguage(canonicalName);
        setTranslationMessage({
          type: 'success',
          text: `Subtitles translated to ${canonicalName}!`,
        });
      } else {
        setTranslationMessage({
          type: 'error',
          text: `No subtitle segments returned for ${selectedLanguage}.`,
        });
      }
    } catch (err: any) {
      console.error('Subtitle translation error:', err);
      let errorDetail = err.response?.data?.detail;
      if (!errorDetail) {
        if (typeof err.response?.data === 'string' && err.response.data.includes('<!DOCTYPE')) {
          errorDetail = 'Backend API is not reachable on Vercel. Please set VITE_BACKEND_URL in Vercel Environment Variables to your deployed backend URL.';
        } else if (err.message === 'Network Error' || !err.response) {
          errorDetail = import.meta.env.PROD
            ? 'Cannot connect to production backend. Check VITE_BACKEND_URL and CORS settings.'
            : 'Cannot connect to local backend at http://localhost:8000. Ensure the FastAPI server is running.';
        } else {
          errorDetail = err.message || `Failed to translate subtitles into ${selectedLanguage}.`;
        }
      }
      setTranslationMessage({
        type: 'error',
        text: errorDetail,
      });
    } finally {
      setIsTranslating(false);
      setTimeout(() => setTranslationMessage(null), 4000);
    }
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <div
      ref={containerRef}
      className="glass-panel"
      style={{
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        borderRadius: 'var(--radius-lg, 16px)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      {/* 1. Main Video Container */}
      <div
        style={{
          position: 'relative',
          background: '#090d16',
          aspectRatio: '16/9',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        {playbackError ? (
          <div
            style={{
              padding: '2rem',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '0.75rem',
              color: '#f87171',
            }}
          >
            <AlertCircle size={36} color="#ef4444" />
            <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem' }}>
              Media stream unavailable or processing
            </p>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.8rem', maxWidth: '380px' }}>
              {playbackError}
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center', marginTop: '0.5rem' }}>
              <button
                onClick={() => {
                  setPlaybackError(null);
                  if (videoRef.current) {
                    videoRef.current.load();
                  }
                }}
                className="btn-secondary"
                style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
              >
                <RefreshCw size={14} /> Retry Playback
              </button>
              {youtubeId && (
                <button
                  onClick={() => {
                    setPlaybackError(null);
                    setUseYouTubeEmbed(true);
                  }}
                  className="gradient-btn"
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                >
                  <Play size={14} /> Play via YouTube
                </button>
              )}
            </div>
          </div>
        ) : useYouTubeEmbed && youtubeId ? (
          <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${youtubeId}?autoplay=1&enablejsapi=1`}
              title={videoTitle || 'YouTube player'}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              style={{ width: '100%', height: '100%', border: 'none' }}
            />
            <button
              onClick={() => setUseYouTubeEmbed(false)}
              className="btn-secondary"
              style={{
                position: 'absolute',
                top: '12px',
                right: '12px',
                zIndex: 20,
                fontSize: '0.72rem',
                padding: '0.3rem 0.6rem',
                background: 'rgba(15, 23, 42, 0.85)',
              }}
              title="Switch back to synchronized native player"
            >
              <RotateCcw size={12} /> Native Stream
            </button>
          </div>
        ) : (
          <video
            ref={videoRef}
            src={streamUrl}
            controls
            playsInline
            crossOrigin="anonymous"
            onTimeUpdate={handleTimeUpdate}
            onError={(e) => {
              console.warn('Video element playback notification:', e);
              // Only report error if duration is 0 and source was attempted
              if (videoRef.current && videoRef.current.networkState === 3) {
                setPlaybackError(
                  'The media file could not be loaded. Please ensure the backend is running and the video was extracted successfully.'
                );
              }
            }}
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        )}

        {/* 2. Synchronized Subtitle Overlay (CC ON) */}
        {ccEnabled && activeSubtitle && !playbackError && (
          <div
            style={{
              position: 'absolute',
              bottom: '12%',
              left: '5%',
              right: '5%',
              display: 'flex',
              justifyContent: 'center',
              pointerEvents: 'none',
              zIndex: 10,
              transition: 'opacity 0.15s ease',
            }}
          >
            <div
              style={{
                background: 'rgba(0, 0, 0, 0.82)',
                color: '#ffffff',
                padding: '0.45rem 1rem',
                borderRadius: '8px',
                fontSize: 'clamp(0.85rem, 2vw, 1.15rem)',
                fontWeight: 600,
                textAlign: 'center',
                lineHeight: 1.35,
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.6)',
                backdropFilter: 'blur(4px)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                maxWidth: '85%',
                letterSpacing: '0.01em',
              }}
            >
              {activeSubtitle.display_name && (
                <span style={{ color: '#818cf8', marginRight: '0.4rem', fontWeight: 700 }}>
                  {activeSubtitle.display_name}:
                </span>
              )}
              {activeSubtitle.text}
            </div>
          </div>
        )}
      </div>

      {/* 3. Subtitle Language Bar & Controls */}
      <div
        style={{
          padding: '0.75rem 1rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.75rem',
          background: 'rgba(15, 23, 42, 0.65)',
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
        {/* Left: Quick Seek & Playback Speed */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => skipSeconds(-5)}
            className="btn-secondary"
            style={{ padding: '0.35rem 0.6rem', fontSize: '0.78rem' }}
            title="Rewind 5 seconds"
          >
            <RotateCcw size={13} />
            <span>-5s</span>
          </button>
          <button
            onClick={() => skipSeconds(10)}
            className="btn-secondary"
            style={{ padding: '0.35rem 0.6rem', fontSize: '0.78rem' }}
            title="Forward 10 seconds"
          >
            <RotateCw size={13} />
            <span>+10s</span>
          </button>

          {/* Speed Selector */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setPlaybackRateOpen((prev) => !prev)}
              className="btn-secondary"
              style={{
                padding: '0.35rem 0.65rem',
                fontSize: '0.78rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
              }}
              title="Change playback speed"
            >
              <Gauge size={13} />
              <span>{playbackSpeed}x</span>
            </button>
            {playbackRateOpen && (
              <div
                className="glass-panel"
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 6px)',
                  left: 0,
                  zIndex: 40,
                  padding: '0.35rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.2rem',
                  minWidth: '80px',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                }}
              >
                {[0.75, 1, 1.25, 1.5, 2].map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSpeedChange(s)}
                    style={{
                      background: playbackSpeed === s ? 'rgba(99, 102, 241, 0.25)' : 'transparent',
                      color: playbackSpeed === s ? 'var(--primary, #6366f1)' : 'var(--text-main)',
                      border: 'none',
                      borderRadius: '4px',
                      padding: '0.3rem 0.5rem',
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontWeight: playbackSpeed === s ? 700 : 500,
                    }}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: CC Toggle & Subtitle Language Workflow */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          {/* CC Toggle Button */}
          <button
            onClick={() => setCcEnabled((prev) => !prev)}
            className="btn-secondary"
            style={{
              padding: '0.35rem 0.75rem',
              fontSize: '0.78rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              background: ccEnabled ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255,255,255,0.04)',
              borderColor: ccEnabled ? 'rgba(16, 185, 129, 0.45)' : 'var(--border-subtle)',
              color: ccEnabled ? '#34d399' : 'var(--text-muted)',
              fontWeight: 700,
            }}
            title={ccEnabled ? 'Closed Captions ON (Click to hide)' : 'Closed Captions OFF (Click to show)'}
          >
            <Subtitles size={14} color={ccEnabled ? '#10b981' : 'currentColor'} />
            <span>CC {ccEnabled ? 'ON' : 'OFF'}</span>
          </button>

          {/* Subtitle Language Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Languages size={14} color="var(--text-muted)" />
            <select
              value={selectedLanguage}
              onChange={(e) => handleLanguageSelect(e.target.value)}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-main)',
                padding: '0.35rem 0.6rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                cursor: 'pointer',
                outline: 'none',
              }}
              title="Select subtitle language"
            >
              {SUPPORTED_LANGUAGES.map((lang) => {
                const isOrig = lang.name.toLowerCase() === originalLanguageName.toLowerCase();
                const isCached = Boolean(subtitleTracks[lang.name] || subtitleTracks[lang.code]);
                const isActive = lang.name.toLowerCase() === activeLanguage.toLowerCase();
                return (
                  <option key={lang.code} value={lang.name} style={{ background: '#1e293b', color: '#fff' }}>
                    {lang.name} ({lang.nativeName}) {isOrig ? '• Original' : isCached ? '✓ Ready' : ''} {isActive ? '★ Active' : ''}
                  </option>
                );
              })}
            </select>

            {/* Translate / Apply Button */}
            <button
              onClick={handleTranslateSubtitles}
              disabled={isTranslating}
              className="gradient-btn"
              style={{
                padding: '0.35rem 0.75rem',
                fontSize: '0.78rem',
                opacity: isTranslating ? 0.7 : 1,
              }}
              title={
                selectedLanguage.toLowerCase() === activeLanguage.toLowerCase()
                  ? `${selectedLanguage} subtitles are currently active on video`
                  : subtitleTracks[selectedLanguage] || selectedLanguage.toLowerCase() === originalLanguageName.toLowerCase()
                  ? `Apply cached ${selectedLanguage} subtitles to video`
                  : `Translate subtitles into ${selectedLanguage}`
              }
            >
              {isTranslating ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  <span>Translating...</span>
                </>
              ) : selectedLanguage.toLowerCase() === activeLanguage.toLowerCase() ? (
                <>
                  <Check size={13} />
                  <span>Active</span>
                </>
              ) : subtitleTracks[selectedLanguage] || selectedLanguage.toLowerCase() === originalLanguageName.toLowerCase() ? (
                <>
                  <Check size={13} />
                  <span>Apply</span>
                </>
              ) : (
                <>
                  <Check size={13} />
                  <span>Translate</span>
                </>
              )}
            </button>
          </div>

          {/* Fullscreen Button */}
          <button
            onClick={toggleFullscreen}
            className="btn-secondary"
            style={{ padding: '0.35rem 0.5rem' }}
            title="Toggle fullscreen"
          >
            <Maximize size={13} />
          </button>
        </div>
      </div>

      {/* 4. Feedback & Status Notification */}
      {translationMessage && (
        <div
          style={{
            padding: '0.4rem 1rem',
            fontSize: '0.78rem',
            background:
              translationMessage.type === 'success'
                ? 'rgba(16, 185, 129, 0.12)'
                : 'rgba(239, 68, 68, 0.12)',
            color: translationMessage.type === 'success' ? '#34d399' : '#f87171',
            borderTop: '1px solid rgba(255, 255, 255, 0.05)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{translationMessage.text}</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Active: <strong>{activeLanguage}</strong>
          </span>
        </div>
      )}
    </div>
  );
};
