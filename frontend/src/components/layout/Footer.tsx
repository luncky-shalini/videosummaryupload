import React from 'react';
import { Cpu, ShieldCheck, Zap } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer
      style={{
        marginTop: '5rem',
        borderTop: '1px solid var(--border-subtle)',
        padding: '2.5rem 1.5rem',
        textAlign: 'center',
        color: 'var(--text-faint)',
        fontSize: '0.85rem',
      }}
    >
      <div
        style={{
          maxWidth: '1200px',
          margin: '0 auto',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
        }}
      >
        <div>
          <p style={{ margin: 0, fontWeight: 500, color: 'var(--text-muted)' }}>
            AI Video Synopsis & Meeting Transcription Platform
          </p>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem' }}>
            Built with React, TypeScript, FastAPI, Groq AI, and Supabase
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Zap size={14} color="#6366f1" />
            <span>Groq Whisper & Llama 3.3</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <ShieldCheck size={14} color="#10b981" />
            <span>Supabase PostgreSQL & RLS</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Cpu size={14} color="#06b6d4" />
            <span>FFmpeg Media Engine</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
