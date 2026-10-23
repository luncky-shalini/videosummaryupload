import re
from urllib.parse import quote
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import Response
from dependencies import get_current_user
from database import get_supabase_admin
from services.pdf_generator import PDFReportGenerator
from services.docx_generator import DocxReportGenerator


router = APIRouter(prefix="/api/videos", tags=["export"])

def create_content_disposition(filename: str, disposition: str = "attachment") -> str:
    """
    Creates an RFC 6266 / RFC 5987 compliant Content-Disposition header value.
    Guarantees that the raw header value is strictly 7-bit ASCII (latin-1 safe for Starlette/FastAPI)
    while preserving the full Unicode filename (including emojis, CJK, Indic scripts)
    for modern web browsers via the filename*=UTF-8'' parameter.
    """
    clean_base = re.sub(r'[\r\n/\\:*?"<>|]', '_', filename).strip()
    if not clean_base:
        clean_base = "export_file"

    ascii_safe = re.sub(r'[^\x20-\x7E]', '_', clean_base)
    ascii_safe = ascii_safe.replace('"', '').replace('\\', '').replace(';', '')
    ascii_safe = re.sub(r'_+', '_', ascii_safe).strip('_')
    if not ascii_safe:
        ascii_safe = "export_file"

    encoded_utf8 = quote(clean_base, encoding='utf-8')
    return f"{disposition}; filename=\"{ascii_safe}\"; filename*=UTF-8''{encoded_utf8}"

def _format_srt_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def _format_vtt_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

@router.get("/{video_id}/export/pdf")
async def export_pdf(
    video_id: str,
    type: str = "full",
    lang: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    FR-08: Exports publication-ready PDF report of synopsis, meeting minutes, and transcript.
    Supports type='synopsis', type='transcript', or type='full'.
    Preserves original and translated Unicode text (Chinese, Telugu, Hindi, Spanish, English).
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    video = v_res.data

    s_res = supabase.table("summaries").select("*").eq("video_id", video_id).single().execute()
    summary = s_res.data or {}

    t_res = supabase.table("transcripts").select("id, language").eq("video_id", video_id).single().execute()
    segments = []
    if t_res.data:
        seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", t_res.data["id"]).order("sequence_order").execute()
        segments = seg_res.data or []

    # Use translated segments if requested and available in cache
    if lang:
        from routers.transcript import SUBTITLE_CACHE, normalize_language
        canonical_code, _ = normalize_language(lang)
        cache_key = f"{video_id}_{canonical_code}"
        if cache_key in SUBTITLE_CACHE:
            segments = SUBTITLE_CACHE[cache_key]

    raw_title = (video.get("title") or "Video Analysis").strip()
    pdf_bytes = PDFReportGenerator.generate_pdf(
        video_title=raw_title,
        video_metadata={"duration": video.get("duration_seconds", 0), "date": str(video.get("created_at", ""))[:10]},
        summary=summary,
        segments=segments,
        export_type=type
    )

    clean_filename = f"{raw_title.replace(' ', '_')}_{type}_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": create_content_disposition(clean_filename)}
    )

@router.get("/{video_id}/export/docx")
async def export_docx(
    video_id: str,
    type: str = "full",
    lang: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    FR-08: Exports Microsoft Word document (.docx).
    Supports type='synopsis', type='transcript', or type='full'.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    video = v_res.data

    s_res = supabase.table("summaries").select("*").eq("video_id", video_id).single().execute()
    summary = s_res.data or {}

    t_res = supabase.table("transcripts").select("id").eq("video_id", video_id).single().execute()
    segments = []
    if t_res.data:
        seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", t_res.data["id"]).order("sequence_order").execute()
        segments = seg_res.data or []

    if lang:
        from routers.transcript import SUBTITLE_CACHE
        cache_key = f"{video_id}_{lang.strip().lower()}"
        if cache_key in SUBTITLE_CACHE:
            segments = SUBTITLE_CACHE[cache_key]

    raw_title = (video.get("title") or "Video Analysis").strip()
    docx_bytes = DocxReportGenerator.generate_docx(
        video_title=raw_title,
        video_metadata={"duration": video.get("duration_seconds", 0), "date": str(video.get("created_at", ""))[:10]},
        summary=summary,
        segments=segments,
        export_type=type
    )

    clean_filename = f"{raw_title.replace(' ', '_')}_{type}_report.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": create_content_disposition(clean_filename)}
    )

@router.get("/{video_id}/export/txt")
async def export_txt(
    video_id: str,
    type: str = "full",
    lang: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    FR-08: Exports valid UTF-8 plain text transcript & synopsis.
    Preserves original speech, speaker labels, timestamps, and line breaks.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    video = v_res.data

    s_res = supabase.table("summaries").select("*").eq("video_id", video_id).single().execute()
    summary = s_res.data or {}

    t_res = supabase.table("transcripts").select("id").eq("video_id", video_id).single().execute()
    segments = []
    if t_res.data:
        seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", t_res.data["id"]).order("sequence_order").execute()
        segments = seg_res.data or []

    if lang:
        from routers.transcript import SUBTITLE_CACHE
        cache_key = f"{video_id}_{lang.strip().lower()}"
        if cache_key in SUBTITLE_CACHE:
            segments = SUBTITLE_CACHE[cache_key]

    raw_title = (video.get("title") or "Video Analysis").strip()
    lines = [
        f"TITLE: {raw_title}",
        "=" * 60,
    ]

    if type in ("full", "synopsis") and summary:
        lines.extend([
            "\nEXECUTIVE SUMMARY:",
            summary.get("executive_summary", ""),
            "\nDETAILED SYNOPSIS:",
            summary.get("detailed_synopsis", ""),
        ])

        if summary.get("is_meeting"):
            lines.append("\nMEETING DECISIONS:")
            for d in summary.get("decisions", []):
                lines.append(f"- {d}")
            lines.append("\nACTION ITEMS:")
            for a in summary.get("action_items", []):
                lines.append(f"- [{a.get('owner', 'Unassigned')}] {a.get('item')} (Deadline: {a.get('deadline', 'None')})")

    if type in ("full", "transcript") and segments:
        lines.append("\n" + "=" * 60)
        lines.append("CHRONOLOGICAL DIALOGUE TRANSCRIPT:")
        lines.append("=" * 60)
        for s in segments:
            m, sec = divmod(int(s.get("start_time", 0)), 60)
            spk = s.get("display_name") or s.get("speaker_label", "Speaker")
            lines.append(f"[{m:02d}:{sec:02d}] {spk}: {s.get('text')}")

    txt_content = "\n".join(lines).encode("utf-8")
    clean_filename = f"{raw_title.replace(' ', '_')}_{type}.txt"
    return Response(
        content=txt_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": create_content_disposition(clean_filename)}
    )

@router.get("/{video_id}/export/srt")
async def export_srt(
    video_id: str,
    lang: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    FR-08: Exports SubRip subtitle format (.srt) with sequential numbers and accurate timestamps.
    Preserves currently active or requested subtitle language.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("id, title, user_id").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    t_res = supabase.table("transcripts").select("id").eq("video_id", video_id).single().execute()
    if not t_res.data:
        raise HTTPException(status_code=404, detail="No transcript found")

    seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", t_res.data["id"]).order("sequence_order").execute()
    segments = seg_res.data or []

    if lang:
        from routers.transcript import SUBTITLE_CACHE, normalize_language
        canonical_code, _ = normalize_language(lang)
        cache_key = f"{video_id}_{canonical_code}"
        if cache_key in SUBTITLE_CACHE:
            segments = SUBTITLE_CACHE[cache_key]

    srt_lines = []
    for idx, s in enumerate(segments, 1):
        start = _format_srt_time(s["start_time"])
        end = _format_srt_time(s["end_time"])
        spk = s.get("display_name") or s.get("speaker_label", "Speaker")
        srt_lines.append(str(idx))
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(f"{spk}: {s['text']}\n")

    srt_content = "\n".join(srt_lines).encode("utf-8")
    raw_title = (v_res.data.get("title") or "subtitles").strip()
    lang_suffix = f"_{lang}" if lang else ""
    clean_filename = f"{raw_title.replace(' ', '_')}{lang_suffix}.srt"
    return Response(
        content=srt_content,
        media_type="application/x-subrip; charset=utf-8",
        headers={"Content-Disposition": create_content_disposition(clean_filename)}
    )

@router.get("/{video_id}/export/vtt")
async def export_vtt(
    video_id: str,
    lang: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    FR-08: Exports WebVTT subtitle format (.vtt).
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("id, title, user_id").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    t_res = supabase.table("transcripts").select("id").eq("video_id", video_id).single().execute()
    if not t_res.data:
        raise HTTPException(status_code=404, detail="No transcript found")

    seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", t_res.data["id"]).order("sequence_order").execute()
    segments = seg_res.data or []

    if lang:
        from routers.transcript import SUBTITLE_CACHE, normalize_language
        canonical_code, _ = normalize_language(lang)
        cache_key = f"{video_id}_{canonical_code}"
        if cache_key in SUBTITLE_CACHE:
            segments = SUBTITLE_CACHE[cache_key]

    vtt_lines = ["WEBVTT\n"]
    for idx, s in enumerate(segments, 1):
        start = _format_vtt_time(s["start_time"])
        end = _format_vtt_time(s["end_time"])
        spk = s.get("display_name") or s.get("speaker_label", "Speaker")
        vtt_lines.append(f"{start} --> {end}")
        vtt_lines.append(f"<v {spk}>{s['text']}\n")

    vtt_content = "\n".join(vtt_lines).encode("utf-8")
    raw_title = (v_res.data.get("title") or "subtitles").strip()
    lang_suffix = f"_{lang}" if lang else ""
    clean_filename = f"{raw_title.replace(' ', '_')}{lang_suffix}.vtt"
    return Response(
        content=vtt_content,
        media_type="text/vtt; charset=utf-8",
        headers={"Content-Disposition": create_content_disposition(clean_filename)}
    )


