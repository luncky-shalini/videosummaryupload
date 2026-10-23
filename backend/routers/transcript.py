from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any
from dependencies import get_current_user
from database import get_supabase_admin
from models.schemas import SpeakerRenameRequest, TranscriptSegmentBase

router = APIRouter(prefix="/api/videos", tags=["transcripts"])

@router.get("/{video_id}/transcript/search")
async def search_transcript(
    video_id: str,
    q: str = Query(..., min_length=1),
    user: dict = Depends(get_current_user)
):
    """
    FR-07: Searches transcript text for matching query and returns matching segments.
    """
    supabase = get_supabase_admin()
    
    # Verify ownership
    v_res = supabase.table("videos").select("id, user_id").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    t_res = supabase.table("transcripts").select("id").eq("video_id", video_id).single().execute()
    if not t_res.data:
        return []

    transcript_id = t_res.data["id"]
    # Case-insensitive search on segment text
    seg_res = supabase.table("transcript_segments") \
        .select("*") \
        .eq("transcript_id", transcript_id) \
        .ilike("text", f"%{q}%") \
        .order("start_time") \
        .execute()

    return seg_res.data or []

@router.patch("/{video_id}/speakers")
async def rename_speaker(
    video_id: str,
    body: SpeakerRenameRequest,
    user: dict = Depends(get_current_user)
):
    """
    FR-05: Allows users to rename speaker labels across the entire video.
    e.g. rename all 'Speaker 1' to 'Sarah Connor'.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("id, user_id").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    t_res = supabase.table("transcripts").select("id").eq("video_id", video_id).single().execute()
    if not t_res.data:
        raise HTTPException(status_code=404, detail="Transcript not found")

    transcript_id = t_res.data["id"]

    # Update all segments where speaker_label matches
    supabase.table("transcript_segments").update({
        "display_name": body.new_display_name
    }).eq("transcript_id", transcript_id).eq("speaker_label", body.speaker_label).execute()

    return {
        "message": f"Successfully updated speaker '{body.speaker_label}' to '{body.new_display_name}'",
        "speaker_label": body.speaker_label,
        "new_display_name": body.new_display_name
    }

# Cache for translated subtitle tracks per video: {f"{video_id}_{target_lang.lower()}": segments}
SUBTITLE_CACHE: Dict[str, List[Dict[str, Any]]] = {}

@router.post("/{video_id}/subtitles/translate")
async def translate_subtitles(
    video_id: str,
    body: dict,
    user: dict = Depends(get_current_user)
):
    """
    Translates transcript subtitle segments into requested target language.
    Preserves exact timing, sequence order, and speaker labels.
    Reuses cached or original tracks without redundant API calls.
    """
    target_language = (body.get("target_language") or "English").strip()
    supabase = get_supabase_admin()

    v_res = supabase.table("videos").select("id, user_id").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    t_res = supabase.table("transcripts").select("id, language").eq("video_id", video_id).single().execute()
    if not t_res.data:
        raise HTTPException(status_code=404, detail="Transcript not found")

    transcript_id = t_res.data["id"]
    detected_lang = (t_res.data.get("language") or "en").lower()

    # Fetch original segments
    seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", transcript_id).order("sequence_order").execute()
    original_segments = seg_res.data or []

    # Map language aliases to check if target is the source audio language
    lang_map = {
        "english": ["en", "english"],
        "telugu": ["te", "telugu"],
        "hindi": ["hi", "hindi"],
        "spanish": ["es", "spanish", "español"],
        "chinese": ["zh", "chinese", "mandarin", "中文"],
        "italian": ["it", "italian", "italiano"],
        "bengali": ["bn", "bengali", "bangla", "বাংলা"],
        "french": ["fr", "french", "français"],
        "german": ["de", "german", "deutsch"],
        "japanese": ["ja", "japanese", "日本語"],
        "portuguese": ["pt", "portuguese", "português"],
        "russian": ["ru", "russian"],
        "arabic": ["ar", "arabic"]
    }

    target_lower = target_language.lower()
    is_original = False
    for std_name, aliases in lang_map.items():
        if any(a in target_lower for a in aliases) and any(a in detected_lang for a in aliases):
            is_original = True
            break
    if target_lower in (detected_lang, "original"):
        is_original = True

    if is_original:
        return {
            "video_id": video_id,
            "target_language": target_language,
            "is_original": True,
            "segments": original_segments
        }

    cache_key = f"{video_id}_{target_lower}"
    if cache_key in SUBTITLE_CACHE:
        return {
            "video_id": video_id,
            "target_language": target_language,
            "is_original": False,
            "is_cached": True,
            "segments": SUBTITLE_CACHE[cache_key]
        }

    from services.groq_summarizer import GroqSummarizer
    summarizer = GroqSummarizer()
    translated_segments = summarizer.translate_segments(original_segments, target_language)
    SUBTITLE_CACHE[cache_key] = translated_segments

    return {
        "video_id": video_id,
        "target_language": target_language,
        "is_original": False,
        "segments": translated_segments
    }

