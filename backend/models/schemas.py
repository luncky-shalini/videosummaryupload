from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

class VideoCreateFromUrl(BaseModel):
    url: str
    title: Optional[str] = None

class UploadUrlRequest(BaseModel):
    filename: str
    file_size: int
    content_type: Optional[str] = None
    title: Optional[str] = None

class UploadUrlResponse(BaseModel):
    video_id: str
    upload_url: Optional[str] = None
    token: Optional[str] = None
    bucket: Optional[str] = None
    path: Optional[str] = None
    storage_path: Optional[str] = None
    direct_upload: bool = False

class CompleteUploadRequest(BaseModel):
    video_id: str
    storage_path: str
    title: str
    original_filename: str
    file_size_bytes: int

class WorkerDownloadRequest(BaseModel):
    url: str
    user_id: str
    title: Optional[str] = None

class WorkerDownloadResponse(BaseModel):
    status: str = "success"
    title: str
    duration: float
    storage_path: str
    file_size_bytes: int
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    description: Optional[str] = ""

class WorkerHealthResponse(BaseModel):
    status: str
    yt_dlp_version: str
    ffmpeg_available: bool
    js_runtime: Optional[str] = None
    pot_provider_configured: bool = False

class VideoResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    title: str
    original_filename: Optional[str] = None
    file_type: str = "upload"
    storage_path: Optional[str] = None
    source_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    status: str
    progress_percent: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class TranscriptSegmentBase(BaseModel):
    id: Optional[str] = None
    start_time: float
    end_time: float
    speaker_label: str = "Speaker 1"
    display_name: str = "Speaker 1"
    text: str
    is_unclear: bool = False
    sequence_order: int = 0

class TranscriptSegmentUpdate(BaseModel):
    display_name: str

class SpeakerRenameRequest(BaseModel):
    speaker_label: str # e.g. "Speaker 1"
    new_display_name: str # e.g. "Alice Smith"

class TranscriptResponse(BaseModel):
    id: str
    video_id: str
    language: str = "en"
    raw_text: str
    segments: List[TranscriptSegmentBase] = []

class KeyMoment(BaseModel):
    time: str # e.g. "04:15"
    timestamp_seconds: float
    title: str
    description: str

class ActionItem(BaseModel):
    item: str
    owner: str = "Unassigned"
    deadline: str = "Not specified"

class SummaryResponse(BaseModel):
    id: Optional[str] = None
    video_id: str
    executive_summary: str
    detailed_synopsis: str
    key_topics: List[str] = []
    conclusions: List[str] = []
    key_moments: List[KeyMoment] = []
    is_meeting: bool = False
    meeting_overview: Optional[str] = None
    decisions: List[str] = []
    action_items: List[ActionItem] = []
    open_questions: List[str] = []

class VideoDetailResponse(BaseModel):
    video: VideoResponse
    transcript: Optional[TranscriptResponse] = None
    summary: Optional[SummaryResponse] = None

class ChatQueryRequest(BaseModel):
    video_id: str
    question: str

class ChatCitation(BaseModel):
    timestamp_seconds: float
    timecode: str
    speaker: str
    snippet: str

class ChatQueryResponse(BaseModel):
    answer: str
    citations: List[ChatCitation] = []

class TranslateRequest(BaseModel):
    target_language: str # e.g. "Spanish", "French", "German", "Hindi", "Japanese"

class TranslateResponse(BaseModel):
    language: str
    translated_summary: str
    translated_transcript_preview: Optional[str] = None
