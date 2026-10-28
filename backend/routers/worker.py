import os
import secrets
import logging
import tempfile
import yt_dlp
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Request, status
from config import settings, ensure_upload_dir
from models.schemas import WorkerDownloadRequest, WorkerDownloadResponse, WorkerHealthResponse
from services.youtube_downloader import YouTubeDownloader
from services.storage import StorageService
from services.ffmpeg_resolver import get_ffmpeg_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/worker", tags=["worker"])


def verify_worker_auth(
    x_worker_key: Optional[str] = Header(None, alias="X-Worker-Key"),
    authorization: Optional[str] = Header(None)
):
    """
    Verifies server-to-server authentication between the main API and the external worker.
    Requires matching YOUTUBE_WORKER_SECRET using constant-time string comparison.
    """
    expected_secret = settings.YOUTUBE_WORKER_SECRET
    if not expected_secret or not expected_secret.strip():
        # If no secret is configured, reject in all non-local setups
        logger.warning("Worker received request but YOUTUBE_WORKER_SECRET is not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Worker secret is not configured on this service."
        )

    token = None
    if x_worker_key:
        token = x_worker_key.strip()
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not token or not secrets.compare_digest(token, expected_secret.strip()):
        logger.warning("Unauthorized access attempt to worker endpoint.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing worker authentication credentials."
        )


@router.get("/health", response_model=WorkerHealthResponse)
def worker_health():
    """
    Health check endpoint reporting yt-dlp version, FFmpeg status,
    discovered JavaScript challenge solving runtime, and PO Token provider configuration.
    """
    js_runtime_info = YouTubeDownloader._resolve_js_runtime()
    js_desc = None
    if js_runtime_info:
        # e.g. "node: C:\Program Files\nodejs\node.exe"
        engine = next(iter(js_runtime_info))
        js_desc = f"{engine}: {js_runtime_info[engine].get('path')}"

    ffmpeg_path = get_ffmpeg_path()

    return {
        "status": "healthy",
        "yt_dlp_version": yt_dlp.version.__version__,
        "ffmpeg_available": bool(ffmpeg_path),
        "js_runtime": js_desc,
        "pot_provider_configured": bool(settings.YOUTUBE_POT_PROVIDER_URL)
    }


@router.post("/download", response_model=WorkerDownloadResponse)
async def execute_worker_download(
    req: WorkerDownloadRequest,
    request: Request
):
    """
    Authenticated worker endpoint that processes YouTube URLs using local PO token
    capabilities, stores the media in cloud storage, and returns metadata.
    """
    x_key = request.headers.get("x-worker-key")
    auth_header = request.headers.get("authorization")
    verify_worker_auth(x_worker_key=x_key, authorization=auth_header)

    user_id = req.user_id or "shared"
    worker_temp_dir = ensure_upload_dir(os.path.join(tempfile.gettempdir(), "worker_dl", user_id))

    try:
        # Force in-process download on the worker itself (bypassing any worker delegation recursion)
        meta = YouTubeDownloader._extract_and_download_in_process(req.url, worker_temp_dir)
    except Exception as exc:
        logger.error(f"Worker YouTube download failed for {req.url}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    filepath = meta["filepath"]
    filename = os.path.basename(filepath)
    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

    # Upload downloaded media to persistent Supabase Storage
    try:
        storage_path = StorageService.upload_file(filepath, user_id, filename)
    except Exception as e:
        logger.error(f"Worker failed to upload to storage: {e}")
        storage_path = filepath

    # Clean up local temporary file if uploaded to cloud storage
    if storage_path.startswith("supabase://") and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass

    return {
        "status": "success",
        "title": req.title if req.title and req.title.strip() else meta.get("title", "Imported Video"),
        "duration": meta.get("duration", 0.0),
        "storage_path": storage_path,
        "file_size_bytes": file_size,
        "thumbnail": meta.get("thumbnail"),
        "uploader": meta.get("uploader", "Unknown"),
        "description": meta.get("description", "")
    }
