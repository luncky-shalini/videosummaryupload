import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Search, Edit2, Check, User, Globe, FileText, Volume2 } from 'lucide-react';
import { TranscriptSegment } from '../../types';
import { api } from '../../services/api';

interface TranscriptViewerProps {
  videoId: string;
  segments: TranscriptSegment[];
  language: string;
  currentTime: number;
  onSeek: (time: number) => void;
  onSpeakerRenamed: () => void;
}

export const TranscriptViewer: React.FC<TranscriptViewerProps> = ({
  videoId,
  segments,
  language,
  currentTime,
  onSeek,
  onSpeakerRenamed,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);
  const activeSegmentRef = useRef<HTMLDivElement>(null);

  // Filter segments based on search
  const filteredSegments = useMemo(() => {
    if (!searchQuery.trim()) return segments;
    const q = searchQuery.toLowerCase();
    return segments.filter(
      (s) =>
        s.text.toLowerCase().includes(q) ||
        s.display_name.toLowerCase().includes(q)
    );
  }, [segments, searchQuery]);

  const handleStartRename = (speakerLabel: string, currentName: string) => {
    setEditingSpeaker(speakerLabel);
    setRenameValue(currentName);
  };

  const handleSaveRename = async (speakerLabel: string) => {
    if (!renameValue.trim()) return;
    setIsRenaming(true);
    try {
      await api.renameSpeaker(videoId, speakerLabel, renameValue.trim());
      setEditingSpeaker(null);
      onSpeakerRenamed();
    } catch (err) {
      alert('Failed to rename speaker');
    } finally {
      setIsRenaming(false);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Helper to highlight matching text
  const highlightMatch = (text: string, query: string) => {
    if (!query.trim()) return text;
    const parts = text.split(new RegExp(`(${query})`, 'gi'));
    return (
      <span>
        {parts.map((part, i) =>
          part.toLowerCase() === query.toLowerCase() ? (
            <mark
              key={i}
              style={{
                background: 'rgba(234, 179, 8, 0.35)',
                color: '#fef08a',
                padding: '0 2px',
                borderRadius: '2px',
              }}
            >
              {part}
            </mark>
          ) : (
            part
          )
        )}
      </span>
    );
  };

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '620px' }}>
      {/* Header & Search */}
      <div style={{ padding: '1.25rem', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText size={18} color="#6366f1" />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, margin: 0 }}>Dialogue Transcript</h3>
          </div>
          <div className="badge badge-primary">
            <Globe size={12} />
            <span>{language.toUpperCase()}</span>
          </div>
        </div>

        {/* Search Bar */}
        <div style={{ position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-faint)' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search transcript dialog, names, topics..."
            className="input-field"
            style={{ paddingLeft: '36px', fontSize: '0.85rem' }}
          />
          {searchQuery && (
            <span
              style={{
                position: 'absolute',
                right: '12px',
                top: '11px',
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
              }}
            >
              {filteredSegments.length} match{filteredSegments.length === 1 ? '' : 'es'}
            </span>
          )}
        </div>
      </div>

      {/* Segments List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {filteredSegments.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem 1rem' }}>
            No transcript segments found matching your search.
          </div>
        ) : (
          filteredSegments.map((segment) => {
            const isActive = currentTime >= segment.start_time && currentTime <= segment.end_time;
            const isEditing = editingSpeaker === segment.speaker_label;

            return (
              <div
                key={segment.id || segment.sequence_order}
                ref={isActive ? activeSegmentRef : null}
                onClick={() => onSeek(segment.start_time)}
                style={{
                  padding: '0.85rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                  border: isActive ? '1px solid var(--primary)' : '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  transition: 'var(--transition-smooth)',
                }}
              >
                {/* Speaker & Timestamp Bar */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {isEditing ? (
                      <div
                        style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="text"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          className="input-field"
                          style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem', width: '130px' }}
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveRename(segment.speaker_label)}
                          disabled={isRenaming}
                          style={{ background: '#10b981', border: 'none', borderRadius: '4px', padding: '0.3rem', cursor: 'pointer', color: 'white' }}
                        >
                          <Check size={14} />
                        </button>
                      </div>
                    ) : (
                      <div
                        className="badge badge-speaker"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartRename(segment.speaker_label, segment.display_name);
                        }}
                        title="Click to rename this speaker across the entire recording"
                      >
                        <User size={12} />
                        <span>{segment.display_name}</span>
                        <Edit2 size={10} style={{ opacity: 0.6 }} />
                      </div>
                    )}

                    {segment.is_unclear && (
                      <span className="badge badge-warning" style={{ fontSize: '0.65rem' }}>
                        Low Confidence
                      </span>
                    )}
                  </div>

                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      color: isActive ? '#818cf8' : 'var(--text-faint)',
                      fontWeight: isActive ? 600 : 400,
                    }}
                  >
                    {formatTime(segment.start_time)} - {formatTime(segment.end_time)}
                  </span>
                </div>

                {/* Spoken Dialogue Text */}
                <p
                  style={{
                    margin: 0,
                    fontSize: '0.9rem',
                    color: isActive ? 'white' : 'var(--text-main)',
                    lineHeight: 1.5,
                  }}
                >
                  {highlightMatch(segment.text, searchQuery)}
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
