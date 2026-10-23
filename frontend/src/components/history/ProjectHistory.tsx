import React, { useEffect, useState } from 'react';
import { Video as VideoIcon, Trash2, Clock, CheckCircle2, AlertTriangle, Loader2, ArrowRight } from 'lucide-react';
import { Video } from '../../types';
import { api } from '../../services/api';

interface ProjectHistoryProps {
  onSelectVideo: (videoId: string) => void;
  onClose: () => void;
}

export const ProjectHistory: React.FC<ProjectHistoryProps> = ({ onSelectVideo, onClose }) => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    loadVideos();
  }, []);

  const loadVideos = async () => {
    setLoading(true);
    try {
      const data = await api.listVideos();
      setVideos(data);
    } catch (err) {
      console.error('Failed to load videos:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (videoId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this video and its generated summaries?')) return;

    setDeletingId(videoId);
    try {
      await api.deleteVideo(videoId);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
    } catch (err) {
      alert('Failed to delete video');
    } finally {
      setDeletingId(null);
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="glass-panel animate-fade-in"
        style={{ width: '100%', maxWidth: '720px', maxHeight: '80vh', display: 'flex', flexDirection: 'column', padding: '1.75rem' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 700, margin: 0 }}>My Video Analyses</h3>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Previous transcripts and generated executive synopses
            </p>
          </div>
          <button onClick={onClose} className="btn-secondary" style={{ padding: '0.4rem 0.8rem' }}>
            Close
          </button>
        </div>

        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Loader2 size={28} className="animate-spin" style={{ margin: '0 auto 0.5rem' }} />
            <p>Loading projects...</p>
          </div>
        ) : videos.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <VideoIcon size={36} color="var(--text-faint)" style={{ margin: '0 auto 0.5rem' }} />
            <p>No uploaded videos yet. Start your first analysis!</p>
          </div>
        ) : (
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {videos.map((v) => (
              <div
                key={v.id}
                onClick={() => {
                  onSelectVideo(v.id);
                  onClose();
                }}
                className="glass-card"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '1rem',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div
                    style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '10px',
                      background: 'rgba(99, 102, 241, 0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <VideoIcon size={20} color="#818cf8" />
                  </div>

                  <div>
                    <h4 style={{ margin: '0 0 0.25rem', fontSize: '0.95rem', fontWeight: 600 }}>{v.title}</h4>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      <span>{v.file_type.toUpperCase()}</span>
                      <span>•</span>
                      <span>{formatDuration(v.duration_seconds)}</span>
                      <span>•</span>
                      <span>{v.created_at ? new Date(v.created_at).toLocaleDateString() : 'Recent'}</span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  {v.status === 'completed' && (
                    <span className="badge badge-success">
                      <CheckCircle2 size={12} /> Ready
                    </span>
                  )}
                  {v.status === 'failed' && (
                    <span className="badge badge-warning">
                      <AlertTriangle size={12} /> Failed
                    </span>
                  )}
                  {v.status !== 'completed' && v.status !== 'failed' && (
                    <span className="badge badge-primary">
                      <Loader2 size={12} className="animate-spin" /> {v.status} ({v.progress_percent}%)
                    </span>
                  )}

                  <button
                    onClick={(e) => handleDelete(v.id, e)}
                    disabled={deletingId === v.id}
                    className="btn-secondary"
                    style={{ padding: '0.45rem', color: '#f87171' }}
                    title="Delete recording and results"
                  >
                    <Trash2 size={15} />
                  </button>

                  <ArrowRight size={16} color="var(--text-faint)" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
