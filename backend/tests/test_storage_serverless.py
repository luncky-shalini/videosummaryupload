import os
import pytest
from unittest.mock import patch, MagicMock
from config import is_serverless, ensure_upload_dir, settings
from services.storage import StorageService

def test_serverless_detection():
    with patch.dict(os.environ, {"VERCEL": "1"}):
        assert is_serverless() is True

    with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "fastapi-handler"}, clear=False):
        assert is_serverless() is True

    with patch.dict(os.environ, {}, clear=True):
        assert is_serverless() is False

def test_ensure_upload_dir_safe_on_readonly():
    # Simulate read-only filesystem where os.makedirs raises OSError
    with patch("os.makedirs", side_effect=OSError(30, "Read-only file system: './uploads'")):
        # Must not raise an unhandled exception
        result = ensure_upload_dir("./uploads")
        assert os.path.normpath(result) == os.path.normpath("/tmp/uploads")

def test_storage_service_local_fallback(tmp_path):
    # Test local storage behavior
    local_file = tmp_path / "test_video.mp4"
    local_file.write_bytes(b"dummy video data")

    with patch.object(settings, "MEDIA_STORAGE_TYPE", "local"):
        saved_path = StorageService.upload_file(str(local_file), "user123", "test_video.mp4")
        assert saved_path == str(local_file)

        # File exists locally
        ensured = StorageService.ensure_local_file(saved_path, "user123")
        assert ensured == str(local_file)

def test_storage_service_supabase_signed_url():
    video = {
        "id": "vid-123",
        "user_id": "usr-456",
        "storage_path": "supabase://media-vault/usr-456/vid-123_test.mp4",
        "original_filename": "test.mp4"
    }

    mock_supabase = MagicMock()
    mock_supabase.storage.from_().create_signed_url.return_value = {
        "signedURL": "https://storage.example.com/signed/video.mp4"
    }

    with patch("services.storage.get_supabase_admin", return_value=mock_supabase):
        resp = StorageService.get_stream_response(video, "usr-456")
        assert resp.status_code == 307
        assert resp.headers["location"] == "https://storage.example.com/signed/video.mp4"
