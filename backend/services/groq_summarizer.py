import json
from typing import Dict, Any, List
from groq import Groq
from config import settings

class GroqSummarizer:
    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def generate_synopsis_and_meeting_insights(
        self,
        transcript_text: str,
        segments: List[Dict[str, Any]],
        video_title: str = "Video"
    ) -> Dict[str, Any]:
        """
        Uses Groq Llama 3.3 70B to generate structured synopsis and meeting minutes
        strictly following instructions without hallucinating facts.
        """
        # Format a condensed timestamped transcript representation
        timestamped_lines = []
        for s in segments:
            mins = int(s["start_time"] // 60)
            secs = int(s["start_time"] % 60)
            speaker = s.get("display_name") or s.get("speaker_label", "Speaker")
            timestamped_lines.append(f"[{mins:02d}:{secs:02d}] {speaker}: {s['text']}")

        condensed_transcript = "\n".join(timestamped_lines)
        # Limit transcript context if extraordinarily large (Groq llama-3.3-70b-versatile has 128k context)
        if len(condensed_transcript) > 100000:
            condensed_transcript = condensed_transcript[:100000] + "\n...[Transcript truncated]..."

        system_prompt = """
You are an expert executive intelligence analyst and meeting recorder.
Analyze the provided transcript and generate a comprehensive, accurate analysis in JSON format.

CRITICAL INSTRUCTIONS:
1. Do NOT invent facts, decisions, commitments, owners, or deadlines that are not explicitly stated in the recording.
2. If speech is marked [unclear] or ambiguous, do not guess what was said.
3. Determine whether the recording is a collaborative meeting/discussion (is_meeting: true) or a general video/presentation/monologue (is_meeting: false).
4. Output MUST be a valid JSON object matching the exact schema specified below.

JSON SCHEMA:
{
  "executive_summary": "Concise 2-3 paragraph high-level overview summarizing the core substance.",
  "detailed_synopsis": "In-depth chronological breakdown and narrative synthesis of the entire video content.",
  "key_topics": ["List of primary themes and subjects covered"],
  "conclusions": ["List of key takeaways, outcomes, and final conclusions"],
  "key_moments": [
    {
      "time": "MM:SS",
      "timestamp_seconds": 123.45,
      "title": "Short title of notable event or turning point",
      "description": "What occurred or was discussed at this exact moment"
    }
  ],
  "is_meeting": true,
  "meeting_overview": "Structured meeting context, participants, and goals (or null if not a meeting)",
  "decisions": ["List of explicit decisions agreed upon (empty list if no explicit decisions or not a meeting)"],
  "action_items": [
    {
      "item": "Task or deliverable description",
      "owner": "Specific person named, or 'Unassigned' if none mentioned",
      "deadline": "Specific date/time mentioned, or 'Not specified'"
    }
  ],
  "open_questions": ["List of unresolved inquiries, blockers, or topics flagged for follow-up"]
}
"""

        user_prompt = f"Video Title: {video_title}\n\nTimestamped Transcript:\n{condensed_transcript}"

        response = self.client.chat.completions.create(
            model=settings.GROQ_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=4000
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        return data

    def answer_question(
        self,
        transcript_text: str,
        segments: List[Dict[str, Any]],
        question: str
    ) -> Dict[str, Any]:
        """
        Answers a user question about the video transcript with exact timestamp citations.
        """
        timestamped_lines = []
        for s in segments:
            mins = int(s["start_time"] // 60)
            secs = int(s["start_time"] % 60)
            speaker = s.get("display_name") or s.get("speaker_label", "Speaker")
            timestamped_lines.append(f"[{mins:02d}:{secs:02d}] {speaker}: {s['text']}")

        condensed_transcript = "\n".join(timestamped_lines[:300]) # Cap for fast latency

        system_prompt = """
You are a video intelligence assistant. Answer the user's question directly using only the provided transcript.
Cite specific timestamps in [MM:SS] format wherever applicable.
If the transcript does not contain the answer, state honestly that the recording does not mention it.
Respond with a JSON object:
{
  "answer": "Detailed answer citing [MM:SS] timecodes.",
  "citations": [
    {
      "timestamp_seconds": 120.0,
      "timecode": "02:00",
      "speaker": "Speaker Name",
      "snippet": "Relevant phrase from transcript"
    }
  ]
}
"""
        response = self.client.chat.completions.create(
            model=settings.GROQ_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Transcript:\n{condensed_transcript}\n\nQuestion: {question}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        return json.loads(response.choices[0].message.content)

    def translate_content(self, text_to_translate: str, target_language: str) -> str:
        """
        Translates text or summary to a target language.
        """
        prompt = f"Translate the following text faithfully into {target_language}. Maintain formatting and bullet points:\n\n{text_to_translate}"
        response = self.client.chat.completions.create(
            model=settings.GROQ_CHAT_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional multilingual translator. Output only the translation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()

    def translate_segments(
        self,
        segments: List[Dict[str, Any]],
        target_language: str
    ) -> List[Dict[str, Any]]:
        """
        Translates a list of speech segments into target_language while preserving
        exact start_time, end_time, and speaker labels.
        """
        if not segments:
            return []

        indexed = [{"id": idx, "text": s.get("text", "")} for idx, s in enumerate(segments)]
        translated_map = {}
        chunk_size = 40

        for i in range(0, len(indexed), chunk_size):
            chunk = indexed[i:i + chunk_size]
            prompt = (
                f"You are a professional audiovisual subtitler and translator. "
                f"Translate the following speech subtitle lines faithfully into {target_language}. "
                f"Preserve conversational nuances, colloquialisms, and tone. "
                f"Output ONLY a valid JSON object with key 'translations', containing an array of objects with keys 'id' and 'translated_text':\n\n"
                f"{json.dumps(chunk, ensure_ascii=False)}"
            )
            try:
                res = self.client.chat.completions.create(
                    model=settings.GROQ_CHAT_MODEL,
                    messages=[
                        {"role": "system", "content": f"You are a professional translator into {target_language}. Output JSON with 'translations' list."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                parsed = json.loads(res.choices[0].message.content)
                items = parsed.get("translations") or parsed.get("segments") or parsed.get("items") or []
                if not items and isinstance(parsed, list):
                    items = parsed
                for it in items:
                    if isinstance(it, dict) and "id" in it:
                        text_val = it.get("translated_text") or it.get("text") or it.get("translation") or ""
                        try:
                            int_id = int(it["id"])
                            translated_map[int_id] = text_val
                        except (ValueError, TypeError):
                            pass
                        translated_map[str(it["id"])] = text_val
            except Exception as e:
                raise RuntimeError(f"Translation service failed: {str(e)}")

        if segments and not translated_map:
            raise RuntimeError(f"Translation service returned empty response for {target_language}.")

        result = []
        for idx, s in enumerate(segments):
            new_seg = dict(s)
            translated_text = translated_map.get(idx) or translated_map.get(str(idx)) or s.get("text", "")
            new_seg["text"] = translated_text
            new_seg["language"] = target_language
            try:
                new_seg["start_time"] = float(s.get("start_time", 0.0))
                new_seg["end_time"] = float(s.get("end_time", 0.0))
            except (ValueError, TypeError):
                pass
            result.append(new_seg)

        return result


