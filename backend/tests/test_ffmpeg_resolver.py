import os
import sys
import shutil
import subprocess
import pytest
from unittest.mock import patch, MagicMock

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ffmpeg_resolver import (
    ensure_ffmpeg,
    get_ffmpeg_path,
    get_ffprobe_path,
    get_ffmpeg_dir,
    get_target_bin_dir,
    parse_media_metadata_with_ffmpeg,
)
from services.media_processor import MediaProcessor
from services.youtube_downloader import YouTubeDownloader
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_ensure_ffmpeg_returns_working_binary():
    """Verifies that ensure_ffmpeg() returns an existing executable that responds to -version."""
    ffmpeg_exe = ensure_ffmpeg()
    assert os.path.exists(ffmpeg_exe), f"FFmpeg path {ffmpeg_exe} does not exist"
    
    res = subprocess.run([ffmpeg_exe, "-version"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "ffmpeg version" in res.stdout.lower()


def test_ffmpeg_dir_in_path():
    """Verifies get_ffmpeg_dir() returns directory and it is added to os.environ['PATH']."""
    bin_dir = get_ffmpeg_dir()
    assert os.path.isdir(bin_dir)
    paths = [os.path.normpath(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    assert os.path.normpath(bin_dir) in paths


def test_serverless_simulated_provisioning(tmp_path):
    """
    Simulates Vercel Serverless environment:
    - shutil.which('ffmpeg') returns None (no system ffmpeg)
    - VERCEL=1
    Ensures imageio-ffmpeg binary is staged in target bin dir and made executable.
    """
    import services.ffmpeg_resolver as resolver

    # Reset cached globals
    saved_ffmpeg = resolver._RESOLVED_FFMPEG_PATH
    saved_ffprobe = resolver._RESOLVED_FFPROBE_PATH
    saved_bin_dir = resolver._RESOLVED_BIN_DIR
    resolver._RESOLVED_FFMPEG_PATH = None
    resolver._RESOLVED_FFPROBE_PATH = None
    resolver._RESOLVED_BIN_DIR = None

    try:
        mock_bin_dir = str(tmp_path / "serverless_bin")
        os.makedirs(mock_bin_dir, exist_ok=True)
        with patch("services.ffmpeg_resolver.get_target_bin_dir", return_value=mock_bin_dir):
            with patch("shutil.which", return_value=None):
                with patch.dict(os.environ, {"VERCEL": "1"}):
                    exe = resolver.ensure_ffmpeg()
                    assert os.path.exists(exe)
                    assert os.path.normpath(mock_bin_dir) in os.path.normpath(exe) or os.path.basename(exe).startswith("ffmpeg")
                    # Check ffprobe shim was generated
                    shim = resolver.get_ffprobe_path()
                    assert shim is not None
                    assert os.path.exists(shim)
    finally:
        resolver._RESOLVED_FFMPEG_PATH = saved_ffmpeg
        resolver._RESOLVED_FFPROBE_PATH = saved_ffprobe
        resolver._RESOLVED_BIN_DIR = saved_bin_dir


def test_media_metadata_and_audio_extraction(tmp_path):
    """
    Creates a minimal valid audio file using ffmpeg test generator,
    verifies MediaProcessor.get_media_metadata() accurately extracts duration/audio streams,
    and tests MediaProcessor.extract_audio() converts it to 16kHz mono MP3.
    """
    ffmpeg_exe = get_ffmpeg_path()
    input_wav = str(tmp_path / "test_tone.wav")

    # Generate a 2-second sine wave audio file
    gen_cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=2",
        input_wav
    ]
    subprocess.run(gen_cmd, check=True, capture_output=True)
    assert os.path.exists(input_wav)

    # 1. Test get_media_metadata
    meta = MediaProcessor.get_media_metadata(input_wav)
    assert meta["has_audio"] is True
    assert meta["duration"] >= 1.9
    assert meta["size_bytes"] > 0

    # 2. Test direct FFmpeg stderr parsing fallback
    direct_meta = parse_media_metadata_with_ffmpeg(input_wav, ffmpeg_exe)
    assert direct_meta["has_audio"] is True
    assert direct_meta["duration"] >= 1.9

    # 3. Test extract_audio
    output_mp3 = str(tmp_path / "test_out.mp3")
    MediaProcessor.extract_audio(input_wav, output_mp3)
    assert os.path.exists(output_mp3)
    assert os.path.getsize(output_mp3) > 0

    # Verify extracted MP3 metadata
    mp3_meta = MediaProcessor.get_media_metadata(output_mp3)
    assert mp3_meta["has_audio"] is True
    assert mp3_meta["duration"] >= 1.9


def test_chunk_audio_if_needed(tmp_path):
    """Verifies that chunk_audio_if_needed splits audio when file size exceeds chunk threshold."""
    ffmpeg_exe = get_ffmpeg_path()
    audio_wav = str(tmp_path / "short_tone.wav")

    subprocess.run([
        ffmpeg_exe, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", audio_wav
    ], check=True, capture_output=True)

    file_size = os.path.getsize(audio_wav)

    # 1. If max_chunk_size is larger than file, returns single chunk
    chunks = MediaProcessor.chunk_audio_if_needed(audio_wav, max_chunk_size_bytes=file_size + 1000)
    assert len(chunks) == 1
    assert chunks[0][0] == audio_wav
    assert chunks[0][1] == 0.0

    # 2. If max_chunk_size is smaller, splits into multiple chunks
    small_chunk_limit = int(file_size / 2)
    split_chunks = MediaProcessor.chunk_audio_if_needed(audio_wav, max_chunk_size_bytes=small_chunk_limit)
    assert len(split_chunks) >= 2
    for chunk_file, offset in split_chunks:
        assert os.path.exists(chunk_file)
        assert os.path.getsize(chunk_file) > 0


def test_youtube_downloader_configures_ffmpeg_location(tmp_path):
    """Verifies YouTubeDownloader injects ffmpeg_location into yt-dlp options."""
    captured_opts = {}

    class MockYDLScope:
        def __init__(self, opts):
            nonlocal captured_opts
            captured_opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=True):
            out_file = tmp_path / "test_id.mp4"
            out_file.write_bytes(b"dummy_video_bytes")
            return {"id": "test_id", "title": "Test Video", "duration": 10.0}

        def prepare_filename(self, info):
            return str(tmp_path / "test_id.mp4")

    with patch("services.youtube_downloader.yt_dlp.YoutubeDL", side_effect=MockYDLScope):
        YouTubeDownloader.extract_and_download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", str(tmp_path))

    assert "ffmpeg_location" in captured_opts
    assert os.path.exists(captured_opts["ffmpeg_location"]) or os.path.isdir(captured_opts["ffmpeg_location"])
    assert "extractor_args" in captured_opts
    assert "youtube" in captured_opts["extractor_args"]
    assert "player_client" in captured_opts["extractor_args"]["youtube"]


def test_youtube_downloader_cookie_resolution(tmp_path):
    """Verifies that YouTubeDownloader supports inline cookies via YOUTUBE_COOKIES_CONTENT."""
    from config import settings
    mock_cookie_content = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1793214452\tSID\tdummy_val\n"
    
    with patch.object(settings, "YOUTUBE_COOKIES_CONTENT", mock_cookie_content):
        cookiefile = YouTubeDownloader._resolve_cookiefile()
        assert cookiefile is not None
        assert os.path.exists(cookiefile)
        with open(cookiefile, "r", encoding="utf-8") as f:
            assert "dummy_val" in f.read()


def test_requirements_contains_imageio_ffmpeg():
    """Verifies backend/requirements.txt contains imageio-ffmpeg for Vercel build dependency resolution."""
    req_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "requirements.txt"))
    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "imageio-ffmpeg" in content


def test_health_reports_ffmpeg_configured():
    """Verifies /health and /api/health report ffmpeg_configured: True."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["ffmpeg_configured"] is True

    api_resp = client.get("/api/health")
    assert api_resp.status_code == 200
    assert api_resp.json()["ffmpeg_configured"] is True
