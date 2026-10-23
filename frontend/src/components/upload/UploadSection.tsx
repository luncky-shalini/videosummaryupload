import React, { useState, useRef } from 'react';
import { UploadCloud, Link as LinkIcon, FileVideo, AlertTriangle, CheckCircle, Loader2, Sparkles } from 'lucide-react';
import { api } from '../../services/api';
import { Video } from '../../types';

interface UploadSectionProps {
  onVideoCreated: (video: Video) => void;
  onOpenAuth: () => void;
  isAuthenticated: boolean;
}

export const UploadSection: React.FC<UploadSectionProps> = ({
  onVideoCreated,
  onOpenAuth,
  isAuthenticated,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [customTitle, setCustomTitle] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [showUrlModal, setShowUrlModal] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const allowedExtensions = ['.mp4', '.mkv', '.mov', '.avi', '.webm', '.mp3', '.wav', '.m4a'];

  const validateFile = (file: File): boolean => {
    setError(null);
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      setError(`Unsupported file format '${ext}'. Please upload an MP4, MOV, MKV, WebM, or audio file.`);
      return false;
    }
    if (file.size > 500 * 1024 * 1024) {
      setError('File size exceeds the 500MB maximum limit.');
      return false;
    }
    return true;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
        setCustomTitle(file.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
        setCustomTitle(file.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const startUpload = async () => {
    if (!selectedFile) return;
    if (!isAuthenticated) {
      onOpenAuth();
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const video = await api.uploadVideo(selectedFile, customTitle, (percent) => {
        setUploadProgress(percent);
      });
      onVideoCreated(video);
      setSelectedFile(null);
      setCustomTitle('');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Upload failed. Please verify server connection.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    if (!isAuthenticated) {
      onOpenAuth();
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const video = await api.importVideoUrl(urlInput.trim(), customTitle.trim() || undefined);
      setShowUrlModal(false);
      setUrlInput('');
      setCustomTitle('');
      onVideoCreated(video);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to import video from URL.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '1rem' }}>
      {/* Hero Header */}
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <div className="badge badge-primary" style={{ marginBottom: '0.75rem' }}>
          <Sparkles size={13} />
          <span>Next-Gen Audio & Video AI</span>
        </div>
        <h2 style={{ fontSize: '2.5rem', fontWeight: 800, lineHeight: 1.2, marginBottom: '0.75rem' }}>
          Understand Any Video or Meeting <span className="gradient-text">in Seconds</span>
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.05rem', maxWidth: '600px', margin: '0 auto' }}>
          Upload Teams, Zoom, or Google Meet recordings for verbatim speaker diarization,
          action items, decisions, and executive synopses.
        </p>

        {/* Authentication Status Tag */}
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '0.85rem' }}>
          {isAuthenticated ? (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.35rem 0.85rem',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: '9999px',
                fontSize: '0.8rem',
                color: '#34d399',
              }}
            >
              <CheckCircle size={14} color="#10b981" />
              <span>Signed in & ready to process</span>
            </div>
          ) : (
            <div
              onClick={onOpenAuth}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.35rem 0.85rem',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '9999px',
                fontSize: '0.8rem',
                color: 'var(--text-muted)',
                cursor: 'pointer',
              }}
              title="Click to sign in"
            >
              <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#94a3b8' }} />
              <span>Not signed in — Click to sign in</span>
            </div>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '1rem',
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 'var(--radius-md)',
            color: '#fca5a5',
            marginBottom: '1.5rem',
          }}
        >
          <AlertTriangle size={20} />
          <span style={{ fontSize: '0.9rem' }}>{error}</span>
        </div>
      )}

      {/* Upload Box */}
      <div
        className="glass-panel"
        style={{
          padding: '2.5rem 2rem',
          border: isDragging ? '2px dashed var(--primary)' : '2px dashed var(--border-subtle)',
          backgroundColor: isDragging ? 'rgba(99, 102, 241, 0.08)' : 'var(--bg-card)',
          cursor: 'pointer',
          textAlign: 'center',
          transition: 'var(--transition-smooth)',
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          accept={allowedExtensions.join(',')}
          onChange={handleFileChange}
        />

        <div
          style={{
            width: '64px',
            height: '64px',
            borderRadius: '16px',
            background: 'rgba(99, 102, 241, 0.12)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '1rem',
          }}
        >
          <UploadCloud size={32} color="#818cf8" />
        </div>

        <h3 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem' }}>
          Drag and drop your recording here
        </h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
          Supports MP4, MOV, MKV, WebM, MP3, WAV (up to 500MB)
        </p>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }} onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            className="gradient-btn"
            onClick={() => fileInputRef.current?.click()}
          >
            <FileVideo size={16} />
            <span>Browse Local Files</span>
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setShowUrlModal(true)}
          >
            <LinkIcon size={16} />
            <span>Import from YouTube / URL</span>
          </button>
        </div>
      </div>

      {/* Selected File Details & Upload Progress */}
      {selectedFile && (
        <div className="glass-card animate-fade-in" style={{ marginTop: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <FileVideo size={24} color="#6366f1" />
              <div>
                <p style={{ fontWeight: 600, margin: 0, fontSize: '0.95rem' }}>{selectedFile.name}</p>
                <p style={{ color: 'var(--text-muted)', margin: 0, fontSize: '0.75rem' }}>
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
            </div>
            <button
              onClick={() => setSelectedFile(null)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-faint)', cursor: 'pointer' }}
            >
              Cancel
            </button>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
              Project / Meeting Title (Optional)
            </label>
            <input
              type="text"
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              placeholder="e.g. Q3 Sprint Planning Meeting"
              className="input-field"
            />
          </div>

          {isUploading ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.25rem' }}>
                <span>Uploading media to secure backend...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${uploadProgress}%`,
                    height: '100%',
                    background: 'linear-gradient(90deg, #6366f1, #06b6d4)',
                    transition: 'width 0.2s ease',
                  }}
                />
              </div>
            </div>
          ) : (
            <button
              onClick={startUpload}
              className="gradient-btn"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              <Sparkles size={16} />
              <span>Analyze & Transcribe Video</span>
            </button>
          )}
        </div>
      )}

      {/* URL Import Modal */}
      {showUrlModal && (
        <div className="modal-overlay" onClick={() => setShowUrlModal(false)}>
          <div
            className="glass-panel animate-fade-in"
            style={{ width: '100%', maxWidth: '480px', padding: '1.75rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>
              Import Video from URL
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
              Enter a public YouTube URL or direct video stream link to extract and transcribe.
            </p>

            <form onSubmit={handleUrlSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                  Video URL
                </label>
                <input
                  type="url"
                  required
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="input-field"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                  Custom Title (Optional)
                </label>
                <input
                  type="text"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="Custom name for this recording"
                  className="input-field"
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowUrlModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading}
                  className="gradient-btn"
                >
                  {isUploading ? <Loader2 size={16} className="animate-spin" /> : <LinkIcon size={16} />}
                  <span>{isUploading ? 'Extracting...' : 'Import & Analyze'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
