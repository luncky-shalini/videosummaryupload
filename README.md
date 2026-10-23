# SynopAI: AI Video Synopsis & Meeting Transcription Platform

A practical, production-grade web application in video processing, speech recognition, and generative AI.

---

## 🌟 Overview & Key Capabilities

- **Video & Audio Ingestion**: Upload MP4, MOV, MKV, WebM, MP3, WAV or import from supported video URLs (including YouTube) with real-time upload and processing feedback.
- **Audio Extraction & Optimization**: High-performance audio conversion to 16kHz mono MP3 via FFmpeg, with automatic chunking for arbitrary recording lengths.
- **Speech-to-Text with Timestamps**: Transcribes spoken dialogue with start and end timestamps via Groq Whisper (`whisper-large-v3`).
- **Speaker Diarization & Global Renaming**: Identifies conversational turns (`Speaker 1`, `Speaker 2`) and allows users to rename speakers across the entire recording.
- **Structured Meeting Intelligence**: Extracts meeting overviews, agreed decisions (without hallucinations), action items with assigned owners and deadlines, and open questions via Groq Llama 3.3 (`llama-3.3-70b-versatile`).
- **Interactive Synchronized Player**: Click any transcript line, speaker turn, or key moment to instantly seek the video to that timestamp. Real-time transcript auto-highlighting as video plays.
- **Multi-Format Export Engine**: Download publication-grade **PDF** reports (ReportLab with Unicode formatting), Microsoft Word **DOCX** files, plain **TXT** files, and standard **SRT** / **WebVTT** subtitles.
- **Interactive "Ask AI" Drawer**: Chat with video intelligence to ask questions about the recording with exact timestamp citations.
- **Multilingual Support**: Automatic spoken language detection and instant translation into Spanish, French, German, Japanese, Hindi, and Portuguese.
- **Security & Data Ownership**: Strict user-level isolation using Supabase Auth (Google OAuth & Email/Password) and PostgreSQL Row Level Security (RLS).

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│             Client SPA (Vercel Deployed)               │
│        React 18 + TypeScript + Vite + Glassmorphism    │
└───────────────────────────┬────────────────────────────┘
                            │ Bearer Token / REST API
                            ▼
┌────────────────────────────────────────────────────────┐
│            FastAPI Server (Python 3.12)                │
│    Auth Guard • FFmpeg Audio Engine • ReportLab Export │
└───────┬───────────────────┬────────────────────┬───────┘
        │                   │                    │
        ▼                   ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Supabase   │     │ Groq Whisper │     │  Groq Llama  │
│  PostgreSQL  │     │  (large-v3)  │     │   3.3 70B    │
│  Auth + RLS  │     │ Transcription│     │ Synopsis/Q&A │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## 📋 Prerequisites (Windows & Mac/Linux)

1. **Python 3.10+**: Verify via `python --version`
2. **Node.js 18+ & npm**: Verify via `node -v` and `npm -v`
3. **FFmpeg**: 
   - Windows: Run `winget install Gyan.FFmpeg` or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add `bin` to PATH. Verify via `ffmpeg -version`.
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
4. **Groq API Key**: Free tier or paid key from [Groq Console](https://console.groq.com/keys)
5. **Supabase Account**: Free project from [Supabase](https://supabase.com)

---

## ⚙️ Quickstart: Local Setup (Windows)

### 1. Database Setup (Supabase)
1. Open your Supabase project dashboard -> **SQL Editor**.
2. Open `supabase/migrations/20240101_initial_schema.sql` in this repo, copy its contents, and run it.
3. In Supabase Dashboard -> **Project Settings** -> **API**, note:
   - `Project URL`
   - `anon public key`
   - `service_role secret key`

### 2. Google OAuth Configuration
1. Go to [Google Cloud Console](https://console.cloud.google.com/) -> **APIs & Services** -> **Credentials**.
2. Create an **OAuth 2.0 Client ID** (Application type: **Web Application**).
3. Set **Authorized JavaScript origins**:
   - `http://localhost:5173`
   - `https://<your-vercel-domain>.vercel.app`
4. Set **Authorized redirect URIs**:
   - `https://<your-supabase-project-id>.supabase.co/auth/v1/callback`
5. In Supabase Dashboard -> **Authentication** -> **Providers** -> **Google**:
   - Toggle **Enable Google provider**.
   - Paste your **Client ID** and **Client Secret**.

### 3. Environment Variables
Copy `.env.example` to `.env` in the root (or `backend/.env` and `frontend/.env`):

```bash
# In backend/.env:
GROQ_API_KEY=gsk_your_groq_api_key_here
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# In frontend/.env:
VITE_SUPABASE_URL=https://your-project-id.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGci...
VITE_BACKEND_URL=http://localhost:8000
```

### 4. Running the Backend
In PowerShell or Command Prompt:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1    # or .\venv\Scripts\activate.bat for CMD
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Backend API will be running at `http://localhost:8000` (Docs at `http://localhost:8000/docs`).

### 5. Running the Frontend
In a new terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Testing

To run the automated backend test suite:
```powershell
cd backend
.\venv\Scripts\pytest -v
```

---

## 🚀 Cloud Deployment

### Frontend (Vercel)
1. Push your repository to GitHub.
2. In [Vercel](https://vercel.com), import your repository.
3. Configure the following environment variables in Vercel:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
   - `VITE_BACKEND_URL` (Points to your deployed backend URL)
4. Click **Deploy**. Vercel will build using `vercel.json`.

### Backend (Render / Railway / Fly.io / VPS)
Because long-running FFmpeg media extraction requires a persistent Linux container rather than a short-lived Vercel serverless function:
1. Deploy the `backend/Dockerfile` to **Render** (Web Service), **Railway**, or **Fly.io**.
2. Supply `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `CORS_ORIGINS`.

---

## 📄 License
MIT License.
