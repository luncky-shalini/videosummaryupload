import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from routers.transcript import normalize_language, LANGUAGE_REGISTRY
from services.groq_summarizer import GroqSummarizer


def test_multilingual_registry_coverage():
    """Verify all requested languages are mapped accurately with valid ISO codes."""
    languages_to_test = [
        ("English", "en"),
        ("Telugu", "te"),
        ("Chinese", "zh"),
        ("Korean", "ko"),
        ("Hindi", "hi"),
        ("Italian", "it"),
        ("Bengali", "bn"),
        ("Tamil", "ta"),
        ("Kannada", "kn"),
    ]
    for lang_name, expected_code in languages_to_test:
        code, name = normalize_language(lang_name)
        assert code == expected_code, f"Failed for {lang_name}: got code {code}"
        assert name.lower() == lang_name.lower()

        # Reverse check with code
        code2, name2 = normalize_language(expected_code)
        assert code2 == expected_code
        assert name2.lower() == lang_name.lower()


def test_korean_source_not_misidentified_as_english():
    """Ensure Korean source video does not default or fall back to English."""
    code, name = normalize_language("korean")
    assert code == "ko"
    assert name == "Korean"

    code_ko, name_ko = normalize_language("ko")
    assert code_ko == "ko"
    assert name_ko == "Korean"


def test_segment_translation_preserves_structure_and_unicode():
    """Test translate_segments preserving timestamps, sequence and Unicode text."""
    summarizer = GroqSummarizer.__new__(GroqSummarizer)
    summarizer.client = MagicMock()

    sample_segments = [
        {
            "id": "seg-0",
            "start_time": 0.0,
            "end_time": 2.5,
            "speaker_label": "Speaker 1",
            "display_name": "Speaker 1",
            "text": "누구세요?",
            "sequence_order": 0,
        },
        {
            "id": "seg-1",
            "start_time": 2.5,
            "end_time": 5.0,
            "speaker_label": "Speaker 2",
            "display_name": "Speaker 2",
            "text": "안녕하세요",
            "sequence_order": 1,
        },
    ]

    # Mock Groq JSON response for Telugu translation
    telugu_json = '{"translations": [{"id": 0, "translated_text": "మీరు ఎవరు?"}, {"id": 1, "translated_text": "నమస్కారం"}]}'
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=telugu_json))]
    summarizer.client.chat.completions.create.return_value = mock_resp

    res = summarizer.translate_segments(sample_segments, "Telugu")
    assert len(res) == 2
    assert res[0]["text"] == "మీరు ఎవరు?"
    assert res[0]["start_time"] == 0.0
    assert res[0]["end_time"] == 2.5
    assert res[0]["speaker_label"] == "Speaker 1"
    assert res[0]["language"] == "Telugu"

    assert res[1]["text"] == "నమస్కారం"
    assert res[1]["start_time"] == 2.5
    assert res[1]["end_time"] == 5.0


def test_translation_failure_raises_exception():
    """Verify that translation API errors raise an exception instead of silently returning untranslated text."""
    summarizer = GroqSummarizer.__new__(GroqSummarizer)
    summarizer.client = MagicMock()
    summarizer.client.chat.completions.create.side_effect = Exception("Groq rate limit or API error")

    sample_segments = [{"id": "s1", "start_time": 0.0, "end_time": 2.0, "text": "누구세요?"}]

    with pytest.raises(RuntimeError) as exc_info:
        summarizer.translate_segments(sample_segments, "English")
    assert "Translation service failed" in str(exc_info.value)
