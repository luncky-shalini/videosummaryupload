import os
import shutil
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from fastapi.responses import FileResponse
from config import settings
from dependencies import get_current_user, get_optional_user
from database import get_supabase_admin
from models.schemas import VideoResponse, VideoDetailResponse, VideoCreateFromUrl, SummaryResponse, TranscriptResponse
from services.youtube_downloader import YouTubeDownloader
from services.pipeline import execute_video_pipeline

router = APIRouter(prefix="/api/videos", tags=["videos"])

ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".mp3", ".wav", ".m4a"}

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

    # Local user directory
    user_upload_dir = os.path.join(settings.UPLOAD_DIR, user_id)
    os.makedirs(user_upload_dir, exist_ok=True)
    saved_filename = f"{video_id}_{file.filename}"
    saved_filepath = os.path.join(user_upload_dir, saved_filename)

    # Stream write to disk
    try:
        with open(saved_filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    file_size = os.path.getsize(saved_filepath)

    # Persist in Supabase
    supabase = get_supabase_admin()
    insert_res = supabase.table("videos").insert({
        "id": video_id,
        "user_id": user_id,
        "title": video_title,
        "original_filename": file.filename,
        "file_type": "upload",
        "storage_path": saved_filepath,
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
    user_upload_dir = os.path.join(settings.UPLOAD_DIR, user_id)

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

    supabase = get_supabase_admin()
    insert_res = supabase.table("videos").insert({
        "id": video_id,
        "user_id": user_id,
        "title": title,
        "original_filename": os.path.basename(filepath),
        "file_type": "youtube",
        "storage_path": filepath,
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
    user: Optional[dict] = Depends(get_optional_user)
):
    """
    Streams the local video file for browser playback.
    Supports HTTP Range requests for seamless video scrubbing and playback.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    video = v_res.data
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if user and video.get("user_id") and video["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    filepath = video.get("storage_path")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Media file not found on server")

    import mimetypes
    media_type, _ = mimetypes.guess_type(filepath)
    if not media_type:
        media_type = "video/mp4" if filepath.endswith((".mp4", ".m4v")) else "application/octet-stream"

    return FileResponse(
        filepath,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{os.path.basename(filepath)}"'
        }
    )


@router.delete("/{video_id}")
async def delete_video(video_id: str, user: dict = Depends(get_current_user)):
    """
    Deletes the video, related transcripts, summaries, and local file storage.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    video = v_res.data
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Delete local file
    filepath = video.get("storage_path")
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass

    # Delete DB records (Cascading deletes handles transcripts, segments, summaries)
    supabase.table("videos").delete().eq("id", video_id).execute()

    return {"message": "Video project deleted successfully", "id": video_id}
