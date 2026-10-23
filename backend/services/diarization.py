import json
from typing import List, Dict, Any
from groq import Groq
from config import settings

class SpeakerDiarizer:
    def __init__(self):
        self.client = None
        if settings.GROQ_API_KEY:
            self.client = Groq(api_key=settings.GROQ_API_KEY)

    def assign_speaker_turns(self, segments: List[Dict[str, Any]], is_meeting_context: bool = True) -> List[Dict[str, Any]]:
        """
        Assigns speaker labels (Speaker 1, Speaker 2...) to chronological segments.
        Combines pause analysis and an LLM dialogue turn-taking classifier.
        """
        if not segments:
            return []

        # If not enough segments or single speaker monologue
        if len(segments) <= 2:
            for s in segments:
                s["speaker_label"] = "Speaker 1"
                s["display_name"] = "Speaker 1"
            return segments

        # If Groq is available, use LLM to analyze dialogue turns across the conversation
        if self.client and len(segments) > 2:
            try:
                # Prepare a sample of segments for dialogue context
                dialogue_snippet = []
                for idx, s in enumerate(segments[:60]): # Pass first 60 segments to detect conversation dynamic
                    dialogue_snippet.append({
                        "idx": idx,
                        "time": f"{int(s['start_time']//60):02d}:{int(s['start_time']%60):02d}",
                        "text": s["text"]
                    })

                system_prompt = (
                    "You are an expert speech and dialogue analyst. Analyze the provided chronological speech segments. "
                    "Identify conversational turns and assign speaker labels ('Speaker 1', 'Speaker 2', 'Speaker 3'). "
                    "Pay attention to questions, answers, affirmations, interruptions, and stylistic changes in voice. "
                    "Return ONLY a valid JSON array of objects with keys: 'idx' (integer matching input) and 'speaker' (string like 'Speaker 1')."
                )

                response = self.client.chat.completions.create(
                    model=settings.GROQ_CHAT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(dialogue_snippet)}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )

                content = response.choices[0].message.content
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    mapping_list = parsed
                elif isinstance(parsed, dict):
                    mapping_list = parsed.get("speakers") or parsed.get("segments") or parsed.get("dialogue") or []
                    if not isinstance(mapping_list, list):
                        for v in parsed.values():
                            if isinstance(v, list):
                                mapping_list = v
                                break
                else:
                    mapping_list = []


                speaker_map = {}
                for item in mapping_list:
                    if isinstance(item, dict) and "idx" in item and "speaker" in item:
                        speaker_map[item["idx"]] = item["speaker"]

                # Apply mapped speakers or propagate
                current_speaker = "Speaker 1"
                for idx, s in enumerate(segments):
                    if idx in speaker_map:
                        current_speaker = speaker_map[idx]
                    elif idx > 0:
                        # If a large pause between segments (> 1.8s), consider a speaker turn switch
                        pause = s["start_time"] - segments[idx - 1]["end_time"]
                        if pause > 2.0 and current_speaker == "Speaker 1":
                            current_speaker = "Speaker 2"
                        elif pause > 2.0 and current_speaker == "Speaker 2":
                            current_speaker = "Speaker 1"

                    s["speaker_label"] = current_speaker
                    s["display_name"] = current_speaker

                return segments
            except Exception as e:
                print(f"LLM Diarization fallback due to: {e}")

        # Heuristic fallback based on speech gaps and punctuation
        current_speaker = "Speaker 1"
        for idx, s in enumerate(segments):
            if idx > 0:
                gap = s["start_time"] - segments[idx - 1]["end_time"]
                # A pause > 2.2 seconds often indicates speaker alternation
                if gap > 2.2:
                    current_speaker = "Speaker 2" if current_speaker == "Speaker 1" else "Speaker 1"
            s["speaker_label"] = current_speaker
            s["display_name"] = current_speaker

        return segments
