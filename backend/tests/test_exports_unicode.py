import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from services.pdf_generator import PDFReportGenerator
from services.docx_generator import DocxReportGenerator


def test_multilingual_pdf_generation():
    video_title = "Multilingual Video Analysis (Telugu, Hindi, Chinese, English)"
    video_metadata = {"duration": 180.0, "date": "2026-10-23"}
    summary = {
        "executive_summary": "English summary.\n\nChinese: 你好 谢谢!\nHindi: नमस्ते और स्वागत है!\nTelugu: నమస్కారం, ప్రాజెక్ట్ సమీక్ష ప్రారంభమైంది.",
        "detailed_synopsis": "Full synopsis with Spanish: ¡Hola a todos!",
        "key_topics": ["Introduction", "బహుభాషా సంభాషణ (Telugu)", "बहुभाषी वार्तालाप (Hindi)", "中文对话 (Chinese)"],
        "conclusions": ["All language transcripts and summaries rendered faithfully."],
        "key_moments": [
            {"time": "00:10", "timestamp_seconds": 10.0, "title": "Greetings", "description": "Telugu and Chinese opening."}
        ],
        "is_meeting": True,
        "meeting_overview": "Cross-cultural sync",
        "decisions": ["Deploy multilingual video synopsis"],
        "action_items": [{"item": "Verify PDF rendering", "owner": "Team", "deadline": "Today"}],
    }
    segments = [
        {"start_time": 0.0, "end_time": 5.0, "speaker_label": "Speaker 1", "display_name": "Speaker 1", "text": "你好"},
        {"start_time": 5.0, "end_time": 10.0, "speaker_label": "Speaker 2", "display_name": "Speaker 2", "text": "నమస్కారం"},
        {"start_time": 10.0, "end_time": 15.0, "speaker_label": "Speaker 3", "display_name": "Speaker 3", "text": "नमस्ते"},
        {"start_time": 15.0, "end_time": 20.0, "speaker_label": "Speaker 1", "display_name": "Speaker 1", "text": "Hello and welcome"}
    ]

    # Test full PDF
    pdf_bytes = PDFReportGenerator.generate_pdf(video_title, video_metadata, summary, segments, export_type="full")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

    # Test synopsis only PDF
    synopsis_pdf = PDFReportGenerator.generate_pdf(video_title, video_metadata, summary, segments, export_type="synopsis")
    assert len(synopsis_pdf) > 500
    assert synopsis_pdf.startswith(b"%PDF")

    # Test transcript only PDF
    transcript_pdf = PDFReportGenerator.generate_pdf(video_title, video_metadata, summary, segments, export_type="transcript")
    assert len(transcript_pdf) > 500
    assert transcript_pdf.startswith(b"%PDF")

def test_multilingual_docx_generation():
    video_title = "Multilingual Video Analysis"
    video_metadata = {"duration": 60.0, "date": "2026-10-23"}
    summary = {
        "executive_summary": "Chinese: 你好, Hindi: नमस्ते, Telugu: నమస్కారం",
        "detailed_synopsis": "Detailed synopsis in Word",
        "is_meeting": False
    }
    segments = [
        {"start_time": 0.0, "end_time": 4.0, "speaker_label": "Speaker 1", "text": "你好 谢谢"}
    ]
    docx_bytes = DocxReportGenerator.generate_docx(video_title, video_metadata, summary, segments)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 1000
    # DOCX is a zip archive starting with PK\x03\x04
    assert docx_bytes.startswith(b"PK\x03\x04")
