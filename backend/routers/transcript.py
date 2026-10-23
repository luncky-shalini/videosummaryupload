from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Tuple, Optional
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

# Registry of supported subtitle languages: alias/code -> (canonical_code, English Name)
LANGUAGE_REGISTRY: Dict[str, Tuple[str, str]] = {
    "en": ("en", "English"),
    "english": ("en", "English"),
    "te": ("te", "Telugu"),
    "telugu": ("te", "Telugu"),
    "hi": ("hi", "Hindi"),
    "hindi": ("hi", "Hindi"),
    "es": ("es", "Spanish"),
    "spanish": ("es", "Spanish"),
    "español": ("es", "Spanish"),
    "zh": ("zh", "Chinese"),
    "chinese": ("zh", "Chinese"),
    "mandarin": ("zh", "Chinese"),
    "it": ("it", "Italian"),
    "italian": ("it", "Italian"),
    "italiano": ("it", "Italian"),
    "bn": ("bn", "Bengali"),
    "bengali": ("bn", "Bengali"),
    "bangla": ("bn", "Bengali"),
    "fr": ("fr", "French"),
    "french": ("fr", "French"),
    "français": ("fr", "French"),
    "de": ("de", "German"),
    "german": ("de", "German"),
    "deutsch": ("de", "German"),
    "ja": ("ja", "Japanese"),
    "japanese": ("ja", "Japanese"),
    "pt": ("pt", "Portuguese"),
    "portuguese": ("pt", "Portuguese"),
    "português": ("pt", "Portuguese"),
    "ru": ("ru", "Russian"),
    "russian": ("ru", "Russian"),
    "ar": ("ar", "Arabic"),
    "arabic": ("ar", "Arabic"),
}

def normalize_language(lang_input: Optional[str]) -> Tuple[str, str]:
    """
    Normalizes language name or ISO code to (2-letter-code, Canonical English Name).
    e.g. 'te' -> ('te', 'Telugu'), 'Telugu' -> ('te', 'Telugu'), 'Hindi' -> ('hi', 'Hindi')
    """
    if not lang_input:
        return "en", "English"
    cleaned = str(lang_input).strip().lower()
    base = cleaned.split("-")[0].split("_")[0]
    if base in LANGUAGE_REGISTRY:
        return LANGUAGE_REGISTRY[base]
    if cleaned in LANGUAGE_REGISTRY:
        return LANGUAGE_REGISTRY[cleaned]
    return base, lang_input.strip().capitalize()

# Cache for translated subtitle tracks per video: {f"{video_id}_{canonical_code}": segments}
SUBTITLE_CACHE: Dict[str, List[Dict[str, Any]]] = {}

@router.post("/{video_id}/subtitles/translate")
async def translate_subtitles(
    video_id: str,
    body: dict,
    user: dict = Depends(get_current_user)
):
    """
    Translates transcript subtitle segments into requested target language.
    Preserves exact timing, sequence order, speaker labels, and Unicode characters.
    Reuses cached or original tracks without redundant API calls.
    """
    target_raw = (body.get("target_language") or body.get("target_language_code") or "English").strip()
    target_code, target_name = normalize_language(target_raw)
    supabase = get_supabase_admin()

    v_res = supabase.table("videos").select("id, user_id").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    t_res = supabase.table("transcripts").select("id, language").eq("video_id", video_id).single().execute()
    if not t_res.data:
        raise HTTPException(status_code=404, detail="Transcript not found")

    transcript_id = t_res.data["id"]
    detected_raw = t_res.data.get("language") or "en"
    orig_code, orig_name = normalize_language(detected_raw)

    # Fetch original segments
    seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", transcript_id).order("sequence_order").execute()
    original_segments = seg_res.data or []

    # Check if target matches detected original audio language
    is_original = (target_code == orig_code) or (target_raw.lower() in ("original", "source"))

    if is_original:
        return {
            "video_id": video_id,
            "target_language": orig_name,
            "target_language_code": orig_code,
            "is_original": True,
            "is_cached": True,
            "segments": original_segments
        }

    cache_key = f"{video_id}_{target_code}"
    if cache_key in SUBTITLE_CACHE:
        return {
            "video_id": video_id,
            "target_language": target_name,
            "target_language_code": target_code,
            "is_original": False,
            "is_cached": True,
            "segments": SUBTITLE_CACHE[cache_key]
        }

    from services.groq_summarizer import GroqSummarizer
    summarizer = GroqSummarizer()
    translated_segments = summarizer.translate_segments(original_segments, target_name)
    SUBTITLE_CACHE[cache_key] = translated_segments

    return {
        "video_id": video_id,
        "target_language": target_name,
        "target_language_code": target_code,
        "is_original": False,
        "is_cached": False,
        "segments": translated_segments
    }

