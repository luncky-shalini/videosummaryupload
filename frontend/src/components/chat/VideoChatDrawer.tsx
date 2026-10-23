import React, { useState } from 'react';
import { MessageSquare, Send, X, Bot, User, Sparkles, Clock } from 'lucide-react';
import { api } from '../../services/api';
import { ChatMessage } from '../../types';

interface VideoChatDrawerProps {
  videoId: string;
  isOpen: boolean;
  onClose: () => void;
  onSeek: (seconds: number) => void;
}

export const VideoChatDrawer: React.FC<VideoChatDrawerProps> = ({
  videoId,
  isOpen,
  onClose,
  onSeek,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hello! I have analyzed the entire transcript and meeting context. Ask me anything, like "What did the team decide?" or "Who is responsible for the API?"',
      created_at: new Date().toISOString(),
    },
  ]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuestion.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: 'user',
      content: inputQuestion.trim(),
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuestion('');
    setLoading(true);

    try {
      const response = await api.askQuestion(videoId, userMsg.content);
      const botMsg: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: 'Sorry, I encountered an error searching the recording. Please verify your connection.',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: '100%',
        maxWidth: '420px',
        background: 'var(--bg-secondary)',
        borderLeft: '1px solid var(--border-subtle)',
        boxShadow: '-8px 0 32px rgba(0,0,0,0.5)',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
      }}
      className="animate-fade-in"
    >
      {/* Header */}
      <div
        style={{
          padding: '1.25rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Sparkles size={16} color="white" />
          </div>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Ask SynopAI</h3>
            <p style={{ margin: 0, fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              Chat with Video Intelligence
            </p>
          </div>
        </div>

        <button
          onClick={onClose}
          style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
        >
          <X size={20} />
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {messages.map((m) => {
          const isBot = m.role === 'assistant';
          return (
            <div
              key={m.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: isBot ? 'flex-start' : 'flex-end',
              }}
            >
              <div
                style={{
                  maxWidth: '85%',
                  padding: '0.85rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  background: isBot ? 'rgba(255, 255, 255, 0.04)' : 'var(--primary)',
                  color: 'white',
                  border: isBot ? '1px solid var(--border-subtle)' : 'none',
                  fontSize: '0.88rem',
                  lineHeight: 1.5,
                }}
              >
                {m.content}

                {/* Citations */}
                {m.citations && m.citations.length > 0 && (
                  <div style={{ marginTop: '0.65rem', paddingTop: '0.5rem', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                    <p style={{ fontSize: '0.75rem', color: '#818cf8', margin: '0 0 0.35rem', fontWeight: 600 }}>
                      Referenced Timestamps:
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                      {m.citations.map((c, i) => (
                        <button
                          key={i}
                          onClick={() => onSeek(c.timestamp_seconds)}
                          className="badge badge-speaker"
                          style={{ cursor: 'pointer', padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                        >
                          <Clock size={11} /> {c.timecode} ({c.speaker})
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            <Sparkles size={16} className="animate-spin" color="#6366f1" />
            <span>Analyzing video context...</span>
          </div>
        )}
      </div>

      {/* Input Form */}
      <form
        onSubmit={handleSendMessage}
        style={{
          padding: '1rem',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          gap: '0.5rem',
        }}
      >
        <input
          type="text"
          value={inputQuestion}
          onChange={(e) => setInputQuestion(e.target.value)}
          placeholder="Ask a question about this video..."
          className="input-field"
          style={{ fontSize: '0.85rem' }}
        />
        <button type="submit" disabled={loading} className="gradient-btn" style={{ padding: '0.65rem 1rem' }}>
          <Send size={16} />
        </button>
      </form>
    </div>
  );
};
