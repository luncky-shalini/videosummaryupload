import logging
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import auth, videos, process, transcript, export, chat, worker

logger = logging.getLogger(__name__)

# Provision and ensure FFmpeg is available on PATH for serverless and container runtimes
try:
    from services.ffmpeg_resolver import ensure_ffmpeg
    ensure_ffmpeg()
except Exception as e:
    logger.warning(f"Initial FFmpeg provisioning notice: {e}")

app = FastAPI(
    title="AI Video Synopsis & Meeting Transcription Platform API",
    description="Production-grade API for speech recognition, diarization, and LLM-powered meeting intelligence.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Vercel Serverless Path Normalizer Middleware
# Ensures requests rewritten to /api/index.py or /main.py resolve to their intended route path
@app.middleware("http")
async def normalize_vercel_paths(request: Request, call_next):
    # 1. Check if path was forwarded via Vercel rewrite parameter (?path=:path*)
    path_param = request.query_params.get("path")
    if path_param is not None:
        clean_path = "/" + path_param.lstrip("/") if path_param else "/"
        request.scope["path"] = clean_path

        # Clean query string so endpoint query parameters are not polluted
        raw_qs = request.scope.get("query_string", b"").decode("utf-8")
        filtered = [p for p in raw_qs.split("&") if p and not p.startswith("path=")]
        request.scope["query_string"] = "&".join(filtered).encode("utf-8")
    else:
        # 2. Check if x-matched-path header is present from Vercel edge proxy
        matched = request.headers.get("x-matched-path")
        if matched and matched not in ("/main.py", "/api/index.py", "/api/index", "/index.py"):
            request.scope["path"] = matched
        else:
            # 3. Strip any serverless file prefixes injected into ASGI scope path
            path = request.scope.get("path", "")
            for prefix in ["/main.py", "/api/index.py", "/api/index", "/index.py"]:
                if path == prefix:
                    request.scope["path"] = "/"
                    break
                elif path.startswith(prefix + "/"):
                    request.scope["path"] = path[len(prefix):]
                    break

    return await call_next(request)

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
app.include_router(worker.router)

@app.get("/")
@app.get("/api")
def read_root():
    return {
        "status": "online",
        "service": "AI Video Synopsis & Meeting Transcription Platform API",
        "docs": "/docs"
    }

@app.get("/health")
@app.get("/api/health")
def healthcheck():
    ffmpeg_configured = False
    try:
        from services.ffmpeg_resolver import get_ffmpeg_path
        ffmpeg_configured = bool(get_ffmpeg_path())
    except Exception:
        ffmpeg_configured = False

    return {
        "status": "healthy",
        "groq_configured": bool(settings.GROQ_API_KEY),
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY),
        "ffmpeg_configured": ffmpeg_configured
    }

@app.get("/api/docs", include_in_schema=False)
def api_docs_redirect():
    return RedirectResponse(url="/docs")

# Expose both app and handler for Vercel Python runtime
handler = app

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
