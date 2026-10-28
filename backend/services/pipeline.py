import os
import traceback
from typing import Optional
from config import settings
from database import get_supabase_admin
from services.media_processor import MediaProcessor
from services.groq_transcription import GroqTranscriptionService
from services.groq_summarizer import GroqSummarizer
from services.diarization import SpeakerDiarizer

def execute_video_pipeline(video_id: str):
    """
    Synchronous / Background execution worker for the video analysis pipeline:
    Extraction -> Transcription -> Diarization -> Summarization -> Supabase Persist.
    """
    supabase = get_supabase_admin()
    
    # 1. Fetch Video Record
    try:
        video_res = supabase.table("videos").select("*").eq("id", video_id).single().execute()
        video = video_res.data
        if not video:
            print(f"Pipeline error: Video {video_id} not found.")
            return
    except Exception as e:
        print(f"Failed to fetch video {video_id}: {e}")
        return

    try:
        # Update status: extracting
        supabase.table("videos").update({
            "status": "extracting",
            "progress_percent": 15
        }).eq("id", video_id).execute()

        # Ensure video media is available locally on disk (downloads from Supabase Storage if needed)
        from services.storage import StorageService
        raw_storage_path = video.get("storage_path")
        try:
            video_path = StorageService.ensure_local_file(raw_storage_path, video.get("user_id"))
        except Exception as e:
            raise FileNotFoundError(f"Media file not found at {raw_storage_path}: {e}")

        # Metadata extraction
        meta = MediaProcessor.get_media_metadata(video_path)
        duration = meta.get("duration", 0.0)
        file_size = meta.get("size_bytes", os.path.getsize(video_path))
        
        supabase.table("videos").update({
            "duration_seconds": duration,
            "file_size_bytes": file_size,
            "progress_percent": 25
        }).eq("id", video_id).execute()

        # 2. Extract Audio
        audio_output_path = os.path.splitext(video_path)[0] + "_audio.mp3"
        MediaProcessor.extract_audio(video_path, audio_output_path)

        # 3. Chunk audio if necessary
        audio_chunks = MediaProcessor.chunk_audio_if_needed(audio_output_path)

        # Update status: transcribing
        supabase.table("videos").update({
            "status": "transcribing",
            "progress_percent": 45
        }).eq("id", video_id).execute()

        # 4. Transcribe using Groq Whisper API
        transcription_service = GroqTranscriptionService()
        stt_result = transcription_service.transcribe_chunks(audio_chunks)
        raw_text = stt_result["raw_text"]
        detected_lang = stt_result["language"]
        segments = stt_result["segments"]

        # Update status: analyzing & diarizing
        supabase.table("videos").update({
            "status": "analyzing",
            "progress_percent": 70
        }).eq("id", video_id).execute()

        # 5. Diarization: Speaker identification & Turn assignment
        diarizer = SpeakerDiarizer()
        diarized_segments = diarizer.assign_speaker_turns(segments)

        # 6. Groq Llama 3.3 Summarization & Meeting Insights
        summarizer = GroqSummarizer()
        summary_result = summarizer.generate_synopsis_and_meeting_insights(
            transcript_text=raw_text,
            segments=diarized_segments,
            video_title=video.get("title", "Video Recording")
        )

        # 7. Persist to Database
        # Save Transcript
        tr_insert = supabase.table("transcripts").insert({
            "video_id": video_id,
            "language": detected_lang,
            "raw_text": raw_text
        }).execute()
        transcript_id = tr_insert.data[0]["id"]

        # Save Transcript Segments (batch insert)
        segment_records = []
        for s in diarized_segments:
            segment_records.append({
                "transcript_id": transcript_id,
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "speaker_label": s.get("speaker_label", "Speaker 1"),
                "display_name": s.get("display_name", "Speaker 1"),
                "text": s["text"],
                "is_unclear": s.get("is_unclear", False),
                "sequence_order": s.get("sequence_order", 0)
            })

        if segment_records:
            # Batch in chunks of 100 for database limits
            for i in range(0, len(segment_records), 100):
                supabase.table("transcript_segments").insert(segment_records[i:i+100]).execute()

        # Save Summary & Meeting Insights
        supabase.table("summaries").insert({
            "video_id": video_id,
            "executive_summary": summary_result.get("executive_summary", ""),
            "detailed_synopsis": summary_result.get("detailed_synopsis", ""),
            "key_topics": summary_result.get("key_topics", []),
            "conclusions": summary_result.get("conclusions", []),
            "key_moments": summary_result.get("key_moments", []),
            "is_meeting": summary_result.get("is_meeting", False),
            "meeting_overview": summary_result.get("meeting_overview"),
            "decisions": summary_result.get("decisions", []),
            "action_items": summary_result.get("action_items", []),
            "open_questions": summary_result.get("open_questions", [])
        }).execute()

        # 8. Mark Video Completed
        supabase.table("videos").update({
            "status": "completed",
            "progress_percent": 100,
            "error_message": None
        }).eq("id", video_id).execute()

        # Cleanup extracted audio
        if os.path.exists(audio_output_path):
            try:
                os.remove(audio_output_path)
            except Exception:
                pass

        print(f"Pipeline successfully completed for video {video_id}")

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"Pipeline error for video {video_id}: {error_msg}")
        try:
            supabase.table("videos").update({
                "status": "failed",
                "progress_percent": 0,
                "error_message": str(e)
            }).eq("id", video_id).execute()
        except Exception:
            pass
