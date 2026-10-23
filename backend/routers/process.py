from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from dependencies import get_current_user
from database import get_supabase_admin
from services.pipeline import execute_video_pipeline

router = APIRouter(prefix="/api/videos", tags=["process"])

@router.get("/{video_id}/status")
async def get_processing_status(video_id: str, user: dict = Depends(get_current_user)):
    """
    Pollable status check endpoint for video analysis.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("id, status, progress_percent, error_message, updated_at").eq("id", video_id).single().execute()
    if not v_res.data:
        raise HTTPException(status_code=404, detail="Video not found")
    return v_res.data

@router.post("/{video_id}/process")
async def trigger_processing(
    video_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """
    Manually re-triggers processing for a video.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("id, user_id").eq("id", video_id).single().execute()
    if not v_res.data:
        raise HTTPException(status_code=404, detail="Video not found")
    if v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    background_tasks.add_task(execute_video_pipeline, video_id)
    return {"message": "Processing started", "video_id": video_id}
