import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from config import settings
from services.youtube_downloader import YouTubeDownloader
from main import app

client = TestClient(app)


def test_youtube_downloader_success_with_mock(tmp_path):
    """Test successful download and metadata extraction."""
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
            out_file = tmp_path / "vid123.mp4"
            out_file.write_bytes(b"dummy_video_stream")
            return {
                "id": "vid123",
                "title": "Sample Title",
                "duration": 42.0,
                "thumbnail": "https://img.youtube.com/vi/vid123/0.jpg",
                "uploader": "Sample Channel",
                "description": "Sample Description",
            }

        def prepare_filename(self, info):
            return str(tmp_path / "vid123.mp4")

    with patch.object(settings, "YOUTUBE_WORKER_URL", None):
        with patch("services.youtube_downloader.yt_dlp.YoutubeDL", side_effect=MockYDLScope):
            res = YouTubeDownloader.extract_and_download("https://www.youtube.com/watch?v=vid123", str(tmp_path))

    assert res["title"] == "Sample Title"
    assert res["duration"] == 42.0
    assert res["uploader"] == "Sample Channel"
    assert os.path.exists(res["filepath"])


def test_youtube_downloader_client_fallback_on_bot_check(tmp_path):
    """Verifies that downloader rotates client profiles when bot check error is raised."""
    attempts = []

    class MockFailingYDLScope:
        def __init__(self, opts):
            clients = opts.get("extractor_args", {}).get("youtube", {}).get("player_client", [])
            attempts.append(clients)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=True):
            if len(attempts) == 1:
                # First attempt fails with bot check error
                raise Exception("Sign in to confirm you’re not a bot. This helps protect our community.")
            # Second attempt succeeds
            out_file = tmp_path / "fallback_vid.mp4"
            out_file.write_bytes(b"fallback_stream")
            return {
                "id": "fallback_vid",
                "title": "Fallback Video",
                "duration": 30.0,
            }

        def prepare_filename(self, info):
            return str(tmp_path / "fallback_vid.mp4")

    with patch.object(settings, "YOUTUBE_WORKER_URL", None):
        with patch("services.youtube_downloader.yt_dlp.YoutubeDL", side_effect=MockFailingYDLScope):
            res = YouTubeDownloader.extract_and_download("https://www.youtube.com/watch?v=fallback_vid", str(tmp_path))

    assert len(attempts) >= 2
    assert res["title"] == "Fallback Video"
    assert os.path.exists(res["filepath"])


def test_youtube_downloader_po_token_configuration(tmp_path):
    """Verifies PO Token and Visitor Data are passed into extractor args."""
    captured_opts = {}

    class MockScope:
        def __init__(self, opts):
            nonlocal captured_opts
            captured_opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=True):
            out_file = tmp_path / "token_vid.mp4"
            out_file.write_bytes(b"dummy")
            return {"id": "token_vid", "title": "Token Vid", "duration": 15.0}

        def prepare_filename(self, info):
            return str(tmp_path / "token_vid.mp4")

    with patch.object(settings, "YOUTUBE_WORKER_URL", None):
        with patch.object(settings, "YOUTUBE_PO_TOKEN", "web.gvs+abc123xyz"):
            with patch.object(settings, "YOUTUBE_VISITOR_DATA", "visit_token_456"):
                with patch("services.youtube_downloader.yt_dlp.YoutubeDL", side_effect=MockScope):
                    YouTubeDownloader.extract_and_download("https://www.youtube.com/watch?v=token_vid", str(tmp_path))

    yt_args = captured_opts["extractor_args"]["youtube"]
    assert "po_token" in yt_args
    assert yt_args["po_token"] == ["web.gvs+abc123xyz"]
    assert "visitor_data" in yt_args
    assert yt_args["visitor_data"] == ["visit_token_456"]


def test_youtube_downloader_pot_provider_opts(tmp_path):
    """Verifies youtubepot-bgutilhttp is configured when YOUTUBE_POT_PROVIDER_URL is set."""
    opts = YouTubeDownloader._build_ydl_opts(str(tmp_path))
    assert "youtubepot-bgutilhttp" not in opts.get("extractor_args", {})

    with patch.object(settings, "YOUTUBE_POT_PROVIDER_URL", "http://127.0.0.1:4416"):
        opts = YouTubeDownloader._build_ydl_opts(str(tmp_path))
        assert "youtubepot-bgutilhttp" in opts["extractor_args"]
        assert opts["extractor_args"]["youtubepot-bgutilhttp"]["base_url"] == ["http://127.0.0.1:4416"]


def test_youtube_downloader_bot_verification_actionable_error(tmp_path):
    """Verifies that persistent bot checks raise clear actionable error with upload fallback."""
    class MockPermanentBotFail:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=True):
            raise Exception("ERROR: [youtube] AFVexpKO3UM: Sign in to confirm you’re not a bot.")

        def prepare_filename(self, info):
            return str(tmp_path / "bot_vid.mp4")

    with patch.object(settings, "YOUTUBE_WORKER_URL", None):
        with patch("services.youtube_downloader.yt_dlp.YoutubeDL", side_effect=MockPermanentBotFail):
            with pytest.raises(RuntimeError) as exc_info:
                YouTubeDownloader.extract_and_download("https://www.youtube.com/watch?v=AFVexpKO3UM", str(tmp_path))

    error_msg = str(exc_info.value)
    assert "YouTube requires additional verification" in error_msg
    assert "upload the video file directly" in error_msg.lower()
    assert "YOUTUBE_WORKER_URL" in error_msg


def test_youtube_downloader_http_403_error(tmp_path):
    """Verifies HTTP 403 error returns clear user-friendly explanation."""
    class Mock403Fail:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=True):
            raise Exception("HTTP Error 403: Forbidden")

        def prepare_filename(self, info):
            return str(tmp_path / "vid.mp4")

    with patch.object(settings, "YOUTUBE_WORKER_URL", None):
        with patch("services.youtube_downloader.yt_dlp.YoutubeDL", side_effect=Mock403Fail):
            with pytest.raises(RuntimeError) as exc_info:
                YouTubeDownloader.extract_and_download("https://www.youtube.com/watch?v=403vid", str(tmp_path))

    assert "HTTP 403 Forbidden" in str(exc_info.value)
    assert "upload the video file directly" in str(exc_info.value)


def test_youtube_downloader_unavailable_video(tmp_path):
    """Verifies private or unavailable video returns clear message."""
    class MockUnavailableFail:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=True):
            raise Exception("Video unavailable. This video is private.")

        def prepare_filename(self, info):
            return str(tmp_path / "priv.mp4")

    with patch.object(settings, "YOUTUBE_WORKER_URL", None):
        with patch("services.youtube_downloader.yt_dlp.YoutubeDL", side_effect=MockUnavailableFail):
            with pytest.raises(RuntimeError) as exc_info:
                YouTubeDownloader.extract_and_download("https://www.youtube.com/watch?v=priv", str(tmp_path))

    assert "restricted or unavailable" in str(exc_info.value)


def test_youtube_downloader_js_runtime_detection():
    """Verifies JavaScript challenge solver discovery."""
    with patch("shutil.which", return_value="/usr/bin/node"):
        runtimes = YouTubeDownloader._resolve_js_runtime()
        assert runtimes is not None
        assert "node" in runtimes
        assert runtimes["node"]["path"] == "/usr/bin/node"


def test_youtube_downloader_delegation_to_worker():
    """Verifies that extract_and_download delegates to YOUTUBE_WORKER_URL when configured."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "title": "Worker Downloaded Video",
        "duration": 120.0,
        "storage_path": "supabase://media-vault/usr-worker/vid-worker.mp4",
        "file_size_bytes": 10485760,
        "thumbnail": "https://img.youtube.com/vi/vid-worker/0.jpg",
        "uploader": "Worker Channel",
        "description": "Worker Desc"
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch.object(settings, "YOUTUBE_WORKER_URL", "https://worker.example.com"):
        with patch.object(settings, "YOUTUBE_WORKER_SECRET", "super_secret_worker_key"):
            with patch("httpx.Client", return_value=mock_client):
                res = YouTubeDownloader.extract_and_download(
                    "https://www.youtube.com/watch?v=test_worker_url",
                    "/tmp/dummy",
                    user_id="usr-worker",
                    title="Custom Worker Video"
                )

                assert res["title"] == "Worker Downloaded Video"
                assert res["storage_path"] == "supabase://media-vault/usr-worker/vid-worker.mp4"
                assert res["duration"] == 120.0

                # Verify authenticated headers and payload sent to worker
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "https://worker.example.com/api/worker/download"
                headers = call_args[1]["headers"]
                assert headers["X-Worker-Key"] == "super_secret_worker_key"
                assert headers["Authorization"] == "Bearer super_secret_worker_key"


def test_youtube_downloader_worker_auth_error():
    """Verifies clear error when worker rejects secret key."""
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch.object(settings, "YOUTUBE_WORKER_URL", "https://worker.example.com"):
        with patch.object(settings, "YOUTUBE_WORKER_SECRET", "wrong_secret"):
            with patch("httpx.Client", return_value=mock_client):
                with pytest.raises(RuntimeError) as exc_info:
                    YouTubeDownloader.extract_and_download("https://www.youtube.com/watch?v=test", "/tmp")

                assert "External YouTube worker authentication failed" in str(exc_info.value)


def test_worker_endpoints_health_and_auth():
    """Verifies /api/worker/health and /api/worker/download authentication rules."""
    # 1. Health endpoint (public)
    res = client.get("/api/worker/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "yt_dlp_version" in data
    assert "ffmpeg_available" in data

    # 2. Download endpoint without key -> 401
    with patch.object(settings, "YOUTUBE_WORKER_SECRET", "test_secret_123"):
        res = client.post("/api/worker/download", json={
            "url": "https://www.youtube.com/watch?v=test",
            "user_id": "usr-1"
        })
        assert res.status_code == 401

        # 3. Download endpoint with invalid key -> 401
        res = client.post("/api/worker/download", json={
            "url": "https://www.youtube.com/watch?v=test",
            "user_id": "usr-1"
        }, headers={"X-Worker-Key": "wrong_key"})
        assert res.status_code == 401

        # 4. Download endpoint with valid key -> 200 (mocking downloader)
        mock_meta = {
            "title": "Downloaded Clip",
            "duration": 45.0,
            "filepath": "C:/dummy/test.mp4",
            "thumbnail": None,
            "uploader": "Channel",
            "description": ""
        }
        with patch.object(YouTubeDownloader, "_extract_and_download_in_process", return_value=mock_meta):
            with patch("routers.worker.StorageService.upload_file", return_value="supabase://media-vault/usr-1/test.mp4"):
                with patch("os.path.exists", return_value=False):
                    res = client.post("/api/worker/download", json={
                        "url": "https://www.youtube.com/watch?v=test",
                        "user_id": "usr-1",
                        "title": "Custom Title"
                    }, headers={"X-Worker-Key": "test_secret_123"})
                    assert res.status_code == 200
                    resp_data = res.json()
                    assert resp_data["status"] == "success"
                    assert resp_data["storage_path"] == "supabase://media-vault/usr-1/test.mp4"
                    assert resp_data["title"] == "Custom Title"
