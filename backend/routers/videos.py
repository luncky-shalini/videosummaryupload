import os
import shutil
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from fastapi.responses import FileResponse
from config import settings, ensure_upload_dir
from dependencies import get_current_user, get_optional_user
from database import get_supabase_admin
from models.schemas import (
    VideoResponse,
    VideoDetailResponse,
    VideoCreateFromUrl,
    SummaryResponse,
    TranscriptResponse,
    UploadUrlRequest,
    UploadUrlResponse,
    CompleteUploadRequest,
)
from services.youtube_downloader import YouTubeDownloader
from services.pipeline import execute_video_pipeline
from services.storage import StorageService

router = APIRouter(prefix="/api/videos", tags=["videos"])

ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".mp3", ".wav", ".m4a"}

@router.post("/create-upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    req: UploadUrlRequest,
    user: dict = Depends(get_current_user)
):
    """
    Generates a short-lived signed upload URL for direct-to-object-storage upload,
    bypassing serverless request-body limits (e.g. Vercel 4.5MB limit).
    Validates file extension, size limit, and returns upload URL and token.
    """
    ext = os.path.splitext(req.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if req.file_size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be greater than 0 bytes."
        )
    if req.file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    video_id = str(uuid.uuid4())
    user_id = user["id"]

    res = StorageService.create_signed_upload_url(user_id=user_id, video_id=video_id, filename=req.filename)
    return res


@router.post("/complete-upload", response_model=VideoResponse)
async def complete_upload(
    req: CompleteUploadRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """
    Finalizes a direct-to-storage upload: verifies user ownership of storage path,
    records video metadata in Supabase, and dispatches the background processing pipeline.
    """
    user_id = user["id"]
    expected_prefix = f"supabase://{settings.STORAGE_BUCKET_NAME}/{user_id}/"

    # Enforce strict user ownership and storage bucket isolation
    if not req.storage_path.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Storage path does not belong to authenticated user."
        )

    ext = os.path.splitext(req.original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if req.file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    supabase = get_supabase_admin()

    # Idempotency check: if record already exists, return it
    existing = supabase.table("videos").select("*").eq("id", req.video_id).execute()
    if existing.data:
        record = existing.data[0]
        if record.get("user_id") != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return record

    insert_res = supabase.table("videos").insert({
        "id": req.video_id,
        "user_id": user_id,
        "title": req.title.strip() or os.path.splitext(req.original_filename)[0],
        "original_filename": req.original_filename,
        "file_type": "upload",
        "storage_path": req.storage_path,
        "file_size_bytes": req.file_size_bytes,
        "status": "pending",
        "progress_percent": 0
    }).execute()

    record = insert_res.data[0]
    background_tasks.add_task(execute_video_pipeline, req.video_id)
    return record


@router.post("/upload", response_model=VideoResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    user: dict = Depends(get_current_user)
):
    """
    Accepts video or audio upload, validates format, stores media, creates record,
    and enqueues background processing.
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    user_id = user["id"]
    video_id = str(uuid.uuid4())
    video_title = title.strip() if title and title.strip() else os.path.splitext(file.filename)[0]

    # Local user directory (ensures /tmp/uploads on serverless)
    user_upload_dir = ensure_upload_dir(os.path.join(settings.UPLOAD_DIR, user_id))
    saved_filename = f"{video_id}_{file.filename}"
    saved_filepath = os.path.join(user_upload_dir, saved_filename)

    # Stream write to disk
    try:
        with open(saved_filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    file_size = os.path.getsize(saved_filepath)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        try:
            os.remove(saved_filepath)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    # Persist in storage (Supabase Storage if configured/serverless, else local disk)
    persistent_storage_path = StorageService.upload_file(saved_filepath, user_id, saved_filename)

    # Persist in Supabase
    supabase = get_supabase_admin()
    insert_res = supabase.table("videos").insert({
        "id": video_id,
        "user_id": user_id,
        "title": video_title,
        "original_filename": file.filename,
        "file_type": "upload",
        "storage_path": persistent_storage_path,
        "file_size_bytes": file_size,
        "status": "pending",
        "progress_percent": 0
    }).execute()

    record = insert_res.data[0]

    # Launch background processing pipeline
    background_tasks.add_task(execute_video_pipeline, video_id)

    return record

@router.post("/import-url", response_model=VideoResponse)
async def import_video_url(
    data: VideoCreateFromUrl,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """
    Downloads media from supported video URLs (including YouTube) using yt-dlp,
    creates DB record, and queues analysis pipeline.
    """
    user_id = user["id"]
    video_id = str(uuid.uuid4())
    user_upload_dir = ensure_upload_dir(os.path.join(settings.UPLOAD_DIR, user_id))

    try:
        download_meta = YouTubeDownloader.extract_and_download(data.url, user_upload_dir)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to import URL with yt-dlp: {str(e)}"
        )

    filepath = download_meta["filepath"]
    title = data.title if data.title else download_meta.get("title", "Imported Video")
    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

    # Persist in storage (Supabase Storage if configured/serverless, else local disk)
    persistent_storage_path = StorageService.upload_file(filepath, user_id, os.path.basename(filepath))

    supabase = get_supabase_admin()
    insert_res = supabase.table("videos").insert({
        "id": video_id,
        "user_id": user_id,
        "title": title,
        "original_filename": os.path.basename(filepath),
        "file_type": "youtube",
        "storage_path": persistent_storage_path,
        "source_url": data.url,
        "duration_seconds": download_meta.get("duration", 0),
        "file_size_bytes": file_size,
        "status": "pending",
        "progress_percent": 0
    }).execute()

    record = insert_res.data[0]
    background_tasks.add_task(execute_video_pipeline, video_id)

    return record

@router.get("", response_model=List[VideoResponse])
async def list_videos(user: dict = Depends(get_current_user)):
    """
    Retrieves all video projects for the signed-in user.
    """
    supabase = get_supabase_admin()
    res = supabase.table("videos").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return res.data

@router.get("/{video_id}", response_model=VideoDetailResponse)
async def get_video_detail(video_id: str, user: dict = Depends(get_current_user)):
    """
    Returns full video details including transcripts, dialogue segments, and AI summaries.
    """
    supabase = get_supabase_admin()
    
    # Check ownership
    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    video = v_res.data
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this video")

    # Fetch transcript
    transcript_obj = None
    t_res = supabase.table("transcripts").select("*").eq("video_id", video_id).execute()
    if t_res.data:
        t_data = t_res.data[0]
        # Fetch segments
        seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", t_data["id"]).order("sequence_order").execute()
        t_data["segments"] = seg_res.data or []
        transcript_obj = t_data

    # Fetch summary
    summary_obj = None
    s_res = supabase.table("summaries").select("*").eq("video_id", video_id).execute()
    if s_res.data:
        summary_obj = s_res.data[0]

    return {
        "video": video,
        "transcript": transcript_obj,
        "summary": summary_obj
    }

@router.get("/{video_id}/stream")
async def stream_video_file(
    video_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Streams the local video file for browser playback.
    Requires an authenticated user session/token (via Bearer header or ?token= query parameter).
    Supports HTTP Range requests for seamless video scrubbing and playback.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    video = v_res.data
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.get("user_id") and video["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this video")

    try:
        return StorageService.get_stream_response(video, user["id"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Media file not found on server or storage")


@router.delete("/{video_id}")
async def delete_video(video_id: str, user: dict = Depends(get_current_user)):
    """
    Deletes the video, related transcripts, summaries, and local/cloud storage.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    video = v_res.data
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Delete local or Supabase Storage file
    filepath = video.get("storage_path")
    if filepath:
        StorageService.delete_file(filepath)

    # Delete DB records (Cascading deletes handles transcripts, segments, summaries)
    supabase.table("videos").delete().eq("id", video_id).execute()

    return {"message": "Video project deleted successfully", "id": video_id}
