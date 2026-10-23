import os
from typing import Dict, Any, List, Tuple
from groq import Groq
from config import settings
from models.schemas import TranscriptSegmentBase

class GroqTranscriptionService:
    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def transcribe_audio_file(self, audio_path: str, time_offset: float = 0.0) -> Dict[str, Any]:
        """
        Transcribes a single audio file via Groq Whisper API (whisper-large-v3).
        Returns verbose json with detected language, text, and segment timecodes.
        """
        with open(audio_path, "rb") as f:
            transcription = self.client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                temperature=0.0
            )

        # Groq returns an object or dict with .segments, .language, .text
        data = transcription if isinstance(transcription, dict) else transcription.model_dump()
        
        language = data.get("language", "en")
        full_text = data.get("text", "")
        raw_segments = data.get("segments", [])

        processed_segments = []
        for idx, seg in enumerate(raw_segments):
            start = round(float(seg.get("start", 0.0)) + time_offset, 2)
            end = round(float(seg.get("end", 0.0)) + time_offset, 2)
            text = seg.get("text", "").strip()

            # Mark unclear speech if confidence is low
            avg_logprob = seg.get("avg_logprob", 0.0)
            no_speech = seg.get("no_speech_prob", 0.0)
            is_unclear = False
            if avg_logprob < -1.5 or no_speech > 0.6:
                is_unclear = True
                if not text:
                    text = "[unclear speech]"

            if text:
                processed_segments.append({
                    "start_time": start,
                    "end_time": end,
                    "text": text,
                    "is_unclear": is_unclear,
                    "sequence_order": idx
                })

        return {
            "language": language,
            "raw_text": full_text,
            "segments": processed_segments
        }

    def transcribe_chunks(self, audio_chunks: List[Tuple[str, float]]) -> Dict[str, Any]:
        """
        Transcribes multiple audio chunks and stitches them chronologically.
        """
        all_segments = []
        full_text_parts = []
        detected_language = "en"
        current_seq = 0

        for chunk_path, offset in audio_chunks:
            res = self.transcribe_audio_file(chunk_path, time_offset=offset)
            detected_language = res.get("language", detected_language)
            full_text_parts.append(res.get("raw_text", ""))

            for seg in res.get("segments", []):
                seg["sequence_order"] = current_seq
                all_segments.append(seg)
                current_seq += 1

            # Cleanup temp chunk if it's a split chunk
            if "_chunk_" in chunk_path and os.path.exists(chunk_path):
                try:
                    os.remove(chunk_path)
                except Exception:
                    pass

        return {
            "language": detected_language,
            "raw_text": " ".join(full_text_parts).strip(),
            "segments": all_segments
        }
