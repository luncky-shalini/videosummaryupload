from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import auth, videos, process, transcript, export, chat

app = FastAPI(
    title="AI Video Synopsis & Meeting Transcription Platform API",
    description="Production-grade API for speech recognition, diarization, and LLM-powered meeting intelligence.",
    version="1.0.0"
)

# CORS configuration
origins = settings.cors_origins_list
if "*" not in origins and "http://localhost:5173" not in origins:
    origins.extend(["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(process.router)
app.include_router(transcript.router)
app.include_router(export.router)
app.include_router(chat.router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "AI Video Synopsis & Meeting Transcription Platform API",
        "docs": "/docs"
    }

@app.get("/health")
def healthcheck():
    return {
        "status": "healthy",
        "groq_configured": bool(settings.GROQ_API_KEY),
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY)
    }

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
