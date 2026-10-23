import React, { useState } from 'react';
import {
  FileText,
  CheckCircle2,
  ListTodo,
  HelpCircle,
  Clock,
  Download,
  Languages,
  Sparkles,
  ChevronRight,
  UserCheck,
  Calendar,
  Loader2,
  AlertCircle,
  Check,
  FileCheck,
} from 'lucide-react';
import { Summary, Video, TranscriptSegment } from '../../types';
import { api } from '../../services/api';

interface SummaryDashboardProps {
  summary: Summary;
  video: Video;
  onSeek: (seconds: number) => void;
  detectedLanguage?: string;
  segments?: TranscriptSegment[];
}

const SUPPORTED_LANGUAGES = [
  { name: 'English', native: 'English' },
  { name: 'Telugu', native: 'తెలుగు' },
  { name: 'Hindi', native: 'हिन्दी' },
  { name: 'Spanish', native: 'Español' },
  { name: 'Chinese', native: '中文' },
  { name: 'Italian', native: 'Italiano' },
  { name: 'Bengali', native: 'বাংলা' },
  { name: 'French', native: 'Français' },
  { name: 'German', native: 'Deutsch' },
  { name: 'Japanese', native: '日本語' },
  { name: 'Portuguese', native: 'Português' },
  { name: 'Russian', native: 'Русский' },
  { name: 'Arabic', native: 'العربية' },
];

export const SummaryDashboard: React.FC<SummaryDashboardProps> = ({
  summary,
  video,
  onSeek,
  detectedLanguage = 'en',
  segments = [],
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'meeting' | 'topics' | 'timeline'>('overview');
  const [targetLang, setTargetLang] = useState('Spanish');
  const [isTranslating, setIsTranslating] = useState(false);
  const [translatedText, setTranslatedText] = useState<string | null>(null);

  // Export state
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [pdfMenuOpen, setPdfMenuOpen] = useState(false);

  const handleTranslate = async () => {
    setIsTranslating(true);
    setExportMessage(null);
    try {
      const res = await api.translateContent(video.id, targetLang);
      setTranslatedText(res.translated_summary);
    } catch (err: any) {
      console.error('Translation error:', err);
      setExportMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Translation failed. Please try again.',
      });
    } finally {
      setIsTranslating(false);
    }
  };

  const handleDownload = async (
    format: 'pdf' | 'docx' | 'txt' | 'srt' | 'vtt',
    type: 'full' | 'synopsis' | 'transcript' = 'full'
  ) => {
    setExportingFormat(`${format}-${type}`);
    setExportMessage(null);
    setPdfMenuOpen(false);

    try {
      const safeTitle = (video.title || 'video_analysis')
        .trim()
        .replace(/[^a-zA-Z0-9_\u00A0-\uFFFF-]/g, '_')
        .substring(0, 50);
      const filename = `${safeTitle}_${type}.${format}`;

      await api.downloadExport(video.id, format, filename, {
        type,
        lang: targetLang,
      });

      setExportMessage({
        type: 'success',
        text: `Successfully downloaded ${filename}!`,
      });
      setTimeout(() => setExportMessage(null), 4000);
    } catch (err: any) {
      console.error('Download export failed:', err);
      let errorMsg = `Failed to generate ${format.toUpperCase()} export.`;
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const json = JSON.parse(text);
          if (json.detail) errorMsg = json.detail;
        } catch (_) {}
      } else if (err.response?.data?.detail) {
        errorMsg = err.response.data.detail;
      }

      setExportMessage({
        type: 'error',
        text: errorMsg,
      });
      setTimeout(() => setExportMessage(null), 5000);
    } finally {
      setExportingFormat(null);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Controls: Tabs & Export */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setActiveTab('overview')}
            className={activeTab === 'overview' ? 'gradient-btn' : 'btn-secondary'}
            style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
          >
            <FileText size={15} />
            <span>Executive Synopsis</span>
          </button>

          {summary.is_meeting && (
            <button
              onClick={() => setActiveTab('meeting')}
              className={activeTab === 'meeting' ? 'gradient-btn' : 'btn-secondary'}
              style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
            >
              <CheckCircle2 size={15} />
              <span>Decisions & Tasks</span>
            </button>
          )}

          <button
            onClick={() => setActiveTab('topics')}
            className={activeTab === 'topics' ? 'gradient-btn' : 'btn-secondary'}
            style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
          >
            <ListTodo size={15} />
            <span>Topics & Takeaways</span>
          </button>

          <button
            onClick={() => setActiveTab('timeline')}
            className={activeTab === 'timeline' ? 'gradient-btn' : 'btn-secondary'}
            style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
          >
            <Clock size={15} />
            <span>Key Moments</span>
          </button>
        </div>

        {/* Export Button Group */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          {/* PDF Dropdown Button */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setPdfMenuOpen((prev) => !prev)}
              disabled={Boolean(exportingFormat)}
              className="btn-secondary"
              style={{ padding: '0.45rem 0.75rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
              title="Download PDF Report"
            >
              {exportingFormat?.startsWith('pdf') ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Download size={14} />
              )}
              <span>PDF</span>
            </button>

            {pdfMenuOpen && (
              <div
                className="glass-panel"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 6px)',
                  right: 0,
                  zIndex: 50,
                  padding: '0.5rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.3rem',
                  minWidth: '180px',
                  boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <button
                  onClick={() => handleDownload('pdf', 'full')}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '0.45rem 0.75rem',
                    color: 'var(--text-main)',
                    fontSize: '0.82rem',
                    textAlign: 'left',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <FileCheck size={14} color="#818cf8" />
                  <span>Full Report (PDF)</span>
                </button>
                <button
                  onClick={() => handleDownload('pdf', 'synopsis')}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '0.45rem 0.75rem',
                    color: 'var(--text-main)',
                    fontSize: '0.82rem',
                    textAlign: 'left',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <FileText size={14} color="#06b6d4" />
                  <span>Synopsis Only (PDF)</span>
                </button>
                <button
                  onClick={() => handleDownload('pdf', 'transcript')}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '0.45rem 0.75rem',
                    color: 'var(--text-main)',
                    fontSize: '0.82rem',
                    textAlign: 'left',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <ListTodo size={14} color="#10b981" />
                  <span>Transcript Only (PDF)</span>
                </button>
              </div>
            )}
          </div>

          {/* DOCX Download */}
          <button
            onClick={() => handleDownload('docx', 'full')}
            disabled={Boolean(exportingFormat)}
            className="btn-secondary"
            style={{ padding: '0.45rem 0.75rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
            title="Download Word Document (.docx)"
          >
            {exportingFormat?.startsWith('docx') ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Download size={14} />
            )}
            <span>DOCX</span>
          </button>

          {/* TXT Download */}
          <button
            onClick={() => handleDownload('txt', 'full')}
            disabled={Boolean(exportingFormat)}
            className="btn-secondary"
            style={{ padding: '0.45rem 0.75rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
            title="Download Plain Text (.txt)"
          >
            {exportingFormat?.startsWith('txt') ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Download size={14} />
            )}
            <span>TXT</span>
          </button>

          {/* SRT Download */}
          <button
            onClick={() => handleDownload('srt')}
            disabled={Boolean(exportingFormat)}
            className="btn-secondary"
            style={{ padding: '0.45rem 0.75rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
            title="Download SubRip Subtitles (.srt)"
          >
            {exportingFormat?.startsWith('srt') ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Download size={14} />
            )}
            <span>SRT</span>
          </button>
        </div>
      </div>

      {/* Export Status Banner */}
      {exportMessage && (
        <div
          className="animate-fade-in"
          style={{
            padding: '0.5rem 1rem',
            borderRadius: 'var(--radius-sm, 8px)',
            background: exportMessage.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${exportMessage.type === 'success' ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)'}`,
            color: exportMessage.type === 'success' ? '#34d399' : '#f87171',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          {exportMessage.type === 'success' ? <Check size={16} /> : <AlertCircle size={16} />}
          <span>{exportMessage.text}</span>
        </div>
      )}

      {/* Tab 1: Executive Overview & Detailed Synopsis */}
      {activeTab === 'overview' && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Executive Summary Box */}
          <div className="glass-card" style={{ borderLeft: '4px solid var(--primary)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <Sparkles size={18} color="#818cf8" />
              <h4 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Executive Summary</h4>
            </div>
            <div style={{ color: 'var(--text-main)', fontSize: '0.95rem', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
              {summary.executive_summary}
            </div>
          </div>

          {/* Detailed Synopsis */}
          <div>
            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem' }}>Detailed Synopsis</h4>
            <div className="glass-card" style={{ color: 'var(--text-main)', fontSize: '0.92rem', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
              {summary.detailed_synopsis}
            </div>
          </div>

          {/* Multilingual Translation Section */}
          <div className="glass-card" style={{ marginTop: '1rem', background: 'rgba(99, 102, 241, 0.05)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Languages size={18} color="#06b6d4" />
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Translate Synopsis</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <select
                  value={targetLang}
                  onChange={(e) => setTargetLang(e.target.value)}
                  className="input-field"
                  style={{ width: 'auto', padding: '0.35rem 0.75rem', fontSize: '0.85rem' }}
                >
                  {SUPPORTED_LANGUAGES.map((l) => (
                    <option key={l.name} value={l.name}>
                      {l.name} ({l.native})
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleTranslate}
                  disabled={isTranslating}
                  className="gradient-btn"
                  style={{ padding: '0.4rem 0.9rem', fontSize: '0.8rem' }}
                >
                  {isTranslating ? 'Translating...' : 'Translate'}
                </button>
              </div>
            </div>

            {translatedText && (
              <div style={{ marginTop: '0.75rem', padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-sm)', fontSize: '0.9rem', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '0.5rem' }}>
                  Translation ({targetLang}):
                </div>
                {translatedText}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Meeting Minutes & Action Items */}
      {activeTab === 'meeting' && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {summary.meeting_overview && (
            <div className="glass-card">
              <h4 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.4rem' }}>Meeting Context</h4>
              <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-muted)' }}>{summary.meeting_overview}</p>
            </div>
          )}

          {/* Decisions */}
          <div>
            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle2 size={18} color="#10b981" />
              <span>Decisions Agreed</span>
            </h4>
            {summary.decisions && summary.decisions.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {summary.decisions.map((dec, i) => (
                  <div key={i} className="glass-card" style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', padding: '0.85rem 1rem' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', marginTop: '6px' }} />
                    <span style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>{dec}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No explicit decisions recorded.</p>
            )}
          </div>

          {/* Action Items Table */}
          <div>
            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ListTodo size={18} color="#6366f1" />
              <span>Action Items & Deliverables</span>
            </h4>
            {summary.action_items && summary.action_items.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '0.75rem 1rem' }}>Task / Action Item</th>
                      <th style={{ padding: '0.75rem 1rem', width: '180px' }}>Owner</th>
                      <th style={{ padding: '0.75rem 1rem', width: '160px' }}>Deadline</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.action_items.map((item, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '0.75rem 1rem', fontWeight: 500 }}>{item.item}</td>
                        <td style={{ padding: '0.75rem 1rem', color: '#818cf8' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <UserCheck size={14} />
                            <span>{item.owner || 'Unassigned'}</span>
                          </div>
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <Calendar size={14} />
                            <span>{item.deadline || 'Not specified'}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No structured action items detected.</p>
            )}
          </div>

          {/* Open Questions */}
          {summary.open_questions && summary.open_questions.length > 0 && (
            <div>
              <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <HelpCircle size={18} color="#f59e0b" />
                <span>Open Questions & Follow-ups</span>
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {summary.open_questions.map((q, i) => (
                  <div key={i} className="glass-card" style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', padding: '0.85rem 1rem' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f59e0b', marginTop: '6px' }} />
                    <span style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>{q}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Key Topics & Conclusions */}
      {activeTab === 'topics' && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem' }}>Key Topics & Themes</h4>
            {summary.key_topics && summary.key_topics.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {summary.key_topics.map((topic, i) => (
                  <div key={i} className="badge badge-primary" style={{ padding: '0.5rem 0.85rem', fontSize: '0.85rem' }}>
                    #{topic}
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No topics extracted.</p>
            )}
          </div>

          <div>
            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem' }}>Key Takeaways & Conclusions</h4>
            {summary.conclusions && summary.conclusions.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {summary.conclusions.map((c, i) => (
                  <div key={i} className="glass-card" style={{ padding: '0.85rem 1rem' }}>
                    <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.5 }}>{c}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No conclusions recorded.</p>
            )}
          </div>
        </div>
      )}

      {/* Tab 4: Interactive Timeline Moments */}
      {activeTab === 'timeline' && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {summary.key_moments && summary.key_moments.length > 0 ? (
            summary.key_moments.map((km, i) => (
              <div
                key={i}
                onClick={() => onSeek(km.timestamp_seconds)}
                className="glass-card"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  padding: '1rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div
                    style={{
                      background: 'rgba(99, 102, 241, 0.2)',
                      color: '#818cf8',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.85rem',
                      fontWeight: 700,
                      padding: '0.35rem 0.65rem',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    {km.time}
                  </div>
                  <div>
                    <h5 style={{ margin: '0 0 0.2rem', fontSize: '0.95rem', fontWeight: 600 }}>{km.title}</h5>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>{km.description}</p>
                  </div>
                </div>
                <ChevronRight size={18} color="var(--text-faint)" />
              </div>
            ))
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No key timeline moments extracted.</p>
          )}
        </div>
      )}
    </div>
  );
};
