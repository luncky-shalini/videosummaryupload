import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from routers.transcript import normalize_language, SUBTITLE_CACHE
from routers.export import _format_srt_time, _format_vtt_time


def test_language_normalization():
    # Primary languages
    assert normalize_language("English") == ("en", "English")
    assert normalize_language("en") == ("en", "English")
    assert normalize_language("en-US") == ("en", "English")
    
    assert normalize_language("Telugu") == ("te", "Telugu")
    assert normalize_language("te") == ("te", "Telugu")

    assert normalize_language("Hindi") == ("hi", "Hindi")
    assert normalize_language("hi") == ("hi", "Hindi")

    assert normalize_language("Spanish") == ("es", "Spanish")
    assert normalize_language("es") == ("es", "Spanish")
    assert normalize_language("español") == ("es", "Spanish")

    assert normalize_language("Japanese") == ("ja", "Japanese")
    assert normalize_language("ja") == ("ja", "Japanese")


def test_no_false_substring_collisions():
    """Ensure short codes like 'es' don't falsely match inside 'japanese' or 'hindi'"""
    ja_code, ja_name = normalize_language("japanese")
    es_code, es_name = normalize_language("spanish")
    hi_code, hi_name = normalize_language("hindi")
    en_code, en_name = normalize_language("english")

    assert ja_code != es_code
    assert hi_code != en_code
    assert ja_code == "ja"
    assert es_code == "es"


def test_subtitle_cache_behavior():
    video_id = "test-video-uuid-123"
    canonical_code, canonical_name = normalize_language("Telugu")
    cache_key = f"{video_id}_{canonical_code}"

    sample_segments = [
        {
            "id": "seg-1",
            "start_time": 0.0,
            "end_time": 4.5,
            "speaker_label": "Speaker 1",
            "display_name": "Speaker 1",
            "text": "నమస్కారం, ఇది వీడియో సారాంశం.",
            "sequence_order": 0
        },
        {
            "id": "seg-2",
            "start_time": 4.5,
            "end_time": 9.2,
            "speaker_label": "Speaker 2",
            "display_name": "Speaker 2",
            "text": "ప్రాజెక్ట్ సమీక్ష ప్రారంభమైంది.",
            "sequence_order": 1
        }
    ]

    SUBTITLE_CACHE[cache_key] = sample_segments
    assert cache_key in SUBTITLE_CACHE
    assert len(SUBTITLE_CACHE[cache_key]) == 2
    assert SUBTITLE_CACHE[cache_key][0]["text"] == "నమస్కారం, ఇది వీడియో సారాంశం."


def test_srt_and_vtt_timestamp_formatting():
    assert _format_srt_time(0.0) == "00:00:00,000"
    assert _format_srt_time(65.5) == "00:01:05,500"
    assert _format_srt_time(3661.125) == "01:01:01,125"

    assert _format_vtt_time(0.0) == "00:00:00.000"
    assert _format_vtt_time(65.5) == "00:01:05.500"
