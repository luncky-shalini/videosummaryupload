import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.schemas import VideoResponse, TranscriptSegmentBase, SummaryResponse, ActionItem
from services.pdf_generator import PDFReportGenerator
from services.docx_generator import DocxReportGenerator

def test_summary_schemas():
    summary_data = {
        "video_id": "test-vid-123",
        "executive_summary": "This was an executive meeting discussing Q3 roadmap and AI platform.",
        "detailed_synopsis": "The team aligned on the engineering deliverables and security audit.",
        "key_topics": ["AI Infrastructure", "Database Migrations", "Google OAuth"],
        "conclusions": ["Production release slated for next Friday."],
        "key_moments": [
            {
                "time": "01:30",
                "timestamp_seconds": 90.0,
                "title": "Roadmap Review",
                "description": "Reviewed Q3 targets"
            }
        ],
        "is_meeting": True,
        "meeting_overview": "Sprint alignment call",
        "decisions": ["Approved use of Groq Whisper and Llama-3.3."],
        "action_items": [
            {
                "item": "Deploy backend to production container",
                "owner": "DevOps Lead",
                "deadline": "Thursday 5 PM"
            }
        ],
        "open_questions": ["Will we add real-time streaming audio transcription in v2?"]
    }

    summary = SummaryResponse(**summary_data)
    assert summary.is_meeting is True
    assert len(summary.action_items) == 1
    assert summary.action_items[0].owner == "DevOps Lead"

def test_pdf_generation_bytes():
    metadata = {"duration": 180, "date": "2026-10-23"}
    summary = {
        "executive_summary": "High-level summary of the recording.",
        "detailed_synopsis": "Detailed narrative covering all segments.",
        "key_topics": ["Feature Planning", "Architecture"],
        "conclusions": ["Proceed with implementation"],
        "key_moments": [{"time": "00:45", "title": "Opening", "description": "Welcome"}],
        "is_meeting": True,
        "decisions": ["Adopt ReportLab for PDF export"],
        "action_items": [{"item": "Run test suite", "owner": "QA", "deadline": "Today"}]
    }
    segments = [
        {"start_time": 0.0, "end_time": 5.0, "speaker_label": "Speaker 1", "display_name": "Speaker 1", "text": "Hello everyone, welcome to the review."}
    ]

    pdf_bytes = PDFReportGenerator.generate_pdf("Test Meeting Title", metadata, summary, segments)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")

def test_docx_generation_bytes():
    metadata = {"duration": 180, "date": "2026-10-23"}
    summary = {
        "executive_summary": "High-level summary of the recording.",
        "detailed_synopsis": "Detailed narrative covering all segments.",
        "key_topics": ["Feature Planning"],
        "conclusions": ["Wrap up"],
        "key_moments": [],
        "is_meeting": False,
        "decisions": [],
        "action_items": []
    }
    segments = [
        {"start_time": 0.0, "end_time": 5.0, "speaker_label": "Speaker 1", "display_name": "Speaker 1", "text": "Testing word document generation."}
    ]

    docx_bytes = DocxReportGenerator.generate_docx("Test Meeting Title", metadata, summary, segments)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 1000
