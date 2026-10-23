from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_current_user
from database import get_supabase_admin
from models.schemas import ChatQueryRequest, ChatQueryResponse, TranslateRequest, TranslateResponse
from services.groq_summarizer import GroqSummarizer

router = APIRouter(prefix="/api/videos", tags=["chat"])

@router.post("/{video_id}/chat", response_model=ChatQueryResponse)
async def ask_question_about_video(
    video_id: str,
    body: ChatQueryRequest,
    user: dict = Depends(get_current_user)
):
    """
    Answers user questions with explicit timestamp citations using Groq Llama-3.3.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("id, user_id").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    t_res = supabase.table("transcripts").select("id, raw_text").eq("video_id", video_id).single().execute()
    if not t_res.data:
        raise HTTPException(status_code=404, detail="No transcript found for this video")

    seg_res = supabase.table("transcript_segments").select("*").eq("transcript_id", t_res.data["id"]).order("sequence_order").execute()
    segments = seg_res.data or []

    summarizer = GroqSummarizer()
    ans = summarizer.answer_question(
        transcript_text=t_res.data["raw_text"],
        segments=segments,
        question=body.question
    )

    return ans

@router.post("/{video_id}/translate", response_model=TranslateResponse)
async def translate_video_synopsis(
    video_id: str,
    body: TranslateRequest,
    user: dict = Depends(get_current_user)
):
    """
    Translates the video summary and key takeaways into the requested target language.
    """
    supabase = get_supabase_admin()
    v_res = supabase.table("videos").select("id, user_id").eq("id", video_id).single().execute()
    if not v_res.data or v_res.data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    s_res = supabase.table("summaries").select("executive_summary, detailed_synopsis").eq("video_id", video_id).single().execute()
    if not s_res.data:
        raise HTTPException(status_code=404, detail="Summary not found")

    content_to_translate = f"Executive Summary:\n{s_res.data['executive_summary']}\n\nDetailed Synopsis:\n{s_res.data['detailed_synopsis']}"

    summarizer = GroqSummarizer()
    translated = summarizer.translate_content(content_to_translate, body.target_language)

    return {
        "language": body.target_language,
        "translated_summary": translated
    }
