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
    "ko": ("ko", "Korean"),
    "korean": ("ko", "Korean"),
    "한국어": ("ko", "Korean"),
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
    "ta": ("ta", "Tamil"),
    "tamil": ("ta", "Tamil"),
    "kn": ("kn", "Kannada"),
    "kannada": ("kn", "Kannada"),
    "ml": ("ml", "Malayalam"),
    "malayalam": ("ml", "Malayalam"),
    "mr": ("mr", "Marathi"),
    "marathi": ("mr", "Marathi"),
    "gu": ("gu", "Gujarati"),
    "gujarati": ("gu", "Gujarati"),
    "pa": ("pa", "Punjabi"),
    "punjabi": ("pa", "Punjabi"),
    "tr": ("tr", "Turkish"),
    "turkish": ("tr", "Turkish"),
    "vi": ("vi", "Vietnamese"),
    "vietnamese": ("vi", "Vietnamese"),
    "ur": ("ur", "Urdu"),
    "urdu": ("ur", "Urdu"),
    "nl": ("nl", "Dutch"),
    "dutch": ("nl", "Dutch"),
    "pl": ("pl", "Polish"),
    "polish": ("pl", "Polish"),
    "id": ("id", "Indonesian"),
    "indonesian": ("id", "Indonesian"),
}

def normalize_language(lang_input: Optional[str]) -> Tuple[str, str]:
    """
    Normalizes language name or ISO code to (2-letter-code, Canonical English Name).
    e.g. 'te' -> ('te', 'Telugu'), 'Telugu' -> ('te', 'Telugu'), 'ko' -> ('ko', 'Korean')
    """
    if not lang_input:
        return "en", "English"
    cleaned = str(lang_input).strip().lower()
    base = cleaned.split("-")[0].split("_")[0]
    if cleaned in LANGUAGE_REGISTRY:
        return LANGUAGE_REGISTRY[cleaned]
    if base in LANGUAGE_REGISTRY:
        return LANGUAGE_REGISTRY[base]
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
    Generates transcript from video audio on the fly if subtitles are not yet available.
    """
    target_raw = (body.get("target_language") or body.get("target_language_code") or "").strip()
    if not target_raw:
        raise HTTPException(status_code=400, detail="Target language is required.")

    target_code, target_name = normalize_language(target_raw)
    supabase = get_supabase_admin()

    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    if not v_res.data:
        raise HTTPException(status_code=404, detail="Video not found.")
    if v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    video = v_res.data

    # Fetch transcript and segments
    t_res = supabase.table("transcripts").select("*").eq("video_id", video_id).execute()
    transcript_id = None
    detected_raw = "en"
    original_segments: List[Dict[str, Any]] = []

    if t_res.data:
        t_data = t_res.data[0]
        transcript_id = t_data["id"]
        detected_raw = t_data.get("language") or "en"
        seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", transcript_id).order("sequence_order").execute()
        original_segments = seg_res.data or []

    # If transcript segments are not found in DB, attempt audio transcription fallback
    if not original_segments:
        import os
        video_path = video.get("storage_path")
        if video_path and os.path.exists(video_path):
            try:
                from services.media_processor import MediaProcessor
                from services.groq_transcription import GroqTranscriptionService
                from services.diarization import SpeakerDiarizer

                audio_output_path = os.path.splitext(video_path)[0] + "_audio.mp3"
                MediaProcessor.extract_audio(video_path, audio_output_path)
                chunks = MediaProcessor.chunk_audio_if_needed(audio_output_path)
                transcription_service = GroqTranscriptionService()
                stt_result = transcription_service.transcribe_chunks(chunks)
                detected_raw = stt_result.get("language") or "en"
                diarizer = SpeakerDiarizer()
                diarized = diarizer.assign_speaker_turns(stt_result.get("segments", []))

                # Save transcript
                if not transcript_id:
                    tr_ins = supabase.table("transcripts").insert({
                        "video_id": video_id,
                        "language": detected_raw,
                        "raw_text": stt_result.get("raw_text", "")
                    }).execute()
                    transcript_id = tr_ins.data[0]["id"]

                # Save segments
                for s in diarized:
                    s["transcript_id"] = transcript_id
                if diarized:
                    supabase.table("transcript_segments").insert(diarized).execute()
                original_segments = diarized
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to extract and transcribe audio for subtitles: {str(e)}"
                )

    if not original_segments:
        raise HTTPException(
            status_code=404,
            detail="Source subtitles or audio transcript unavailable for this video."
        )

    orig_code, orig_name = normalize_language(detected_raw)

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

    try:
        from services.groq_summarizer import GroqSummarizer
        summarizer = GroqSummarizer()
        translated_segments = summarizer.translate_segments(original_segments, target_name)
        if not translated_segments:
            raise ValueError(f"No translated segments produced for {target_name}.")
        SUBTITLE_CACHE[cache_key] = translated_segments
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Subtitle translation failed: {str(e)}"
        )

    return {
        "video_id": video_id,
        "target_language": target_name,
        "target_language_code": target_code,
        "is_original": False,
        "is_cached": False,
        "segments": translated_segments
    }

