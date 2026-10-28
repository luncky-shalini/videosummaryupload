import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from config import is_serverless, ensure_upload_dir, settings
from services.storage import StorageService
from main import app
from dependencies import get_current_user

client = TestClient(app)


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


def test_storage_service_ensure_bucket():
    mock_supabase = MagicMock()
    # Bucket does not exist, triggers create_bucket
    mock_supabase.storage.get_bucket.side_effect = Exception("Not found")

    with patch("services.storage.get_supabase_admin", return_value=mock_supabase):
        res = StorageService.ensure_bucket("media-vault")
        assert res is True
        mock_supabase.storage.create_bucket.assert_called_once()


def test_create_signed_upload_url_supabase():
    mock_supabase = MagicMock()
    mock_supabase.storage.from_().create_signed_upload_url.return_value = {
        "signedURL": "https://storage.example.com/upload/sign?token=xyz",
        "token": "xyz",
        "path": "usr-123/vid_test.mp4"
    }

    with patch.object(settings, "MEDIA_STORAGE_TYPE", "supabase"):
        with patch("services.storage.get_supabase_admin", return_value=mock_supabase):
            res = StorageService.create_signed_upload_url("usr-123", "vid-789", "test.mp4")
            assert res["direct_upload"] is True
            assert res["upload_url"] == "https://storage.example.com/upload/sign?token=xyz"
            assert res["token"] == "xyz"
            assert res["storage_path"] == "supabase://media-vault/usr-123/vid-789_test.mp4"


def test_create_upload_url_endpoint_success():
    app.dependency_overrides[get_current_user] = lambda: {"id": "usr-test-1", "email": "test@example.com"}

    mock_supabase = MagicMock()
    mock_supabase.storage.from_().create_signed_upload_url.return_value = {
        "signedURL": "https://storage.example.com/upload/signed?token=tok123",
        "token": "tok123",
        "path": "usr-test-1/vid.mp4"
    }

    with patch.object(settings, "MEDIA_STORAGE_TYPE", "supabase"):
        with patch("services.storage.get_supabase_admin", return_value=mock_supabase):
            resp = client.post("/api/videos/create-upload-url", json={
                "filename": "team_meeting.mp4",
                "file_size": 15000000,
                "content_type": "video/mp4",
                "title": "Team Meeting"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["direct_upload"] is True
            assert "upload_url" in data
            assert data["storage_path"].startswith("supabase://media-vault/usr-test-1/")

    app.dependency_overrides.clear()


def test_create_upload_url_unsupported_format():
    app.dependency_overrides[get_current_user] = lambda: {"id": "usr-test-1", "email": "test@example.com"}
    resp = client.post("/api/videos/create-upload-url", json={
        "filename": "malicious.exe",
        "file_size": 1000
    })
    assert resp.status_code == 400
    assert "Unsupported file format" in resp.json()["detail"]
    app.dependency_overrides.clear()


def test_create_upload_url_oversized_file():
    app.dependency_overrides[get_current_user] = lambda: {"id": "usr-test-1", "email": "test@example.com"}
    resp = client.post("/api/videos/create-upload-url", json={
        "filename": "huge_video.mp4",
        "file_size": 600 * 1024 * 1024  # 600MB > 500MB limit
    })
    assert resp.status_code == 400
    assert "exceeds maximum allowed limit" in resp.json()["detail"]
    app.dependency_overrides.clear()


def test_complete_upload_ownership_enforcement():
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-alice", "email": "alice@example.com"}

    # Attempt to complete upload for user-bob's storage path
    resp = client.post("/api/videos/complete-upload", json={
        "video_id": "vid-steal",
        "storage_path": "supabase://media-vault/user-bob/vid-steal_secret.mp4",
        "title": "Stolen Video",
        "original_filename": "secret.mp4",
        "file_size_bytes": 10000
    })

    assert resp.status_code == 403
    assert "does not belong to authenticated user" in resp.json()["detail"]
    app.dependency_overrides.clear()


def test_complete_upload_success():
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-alice", "email": "alice@example.com"}

    mock_supabase = MagicMock()
    # Idempotency check: not found
    mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[])
    # Insert record
    mock_record = {
        "id": "vid-1234",
        "user_id": "user-alice",
        "title": "Alice Video",
        "original_filename": "meeting.mp4",
        "file_type": "upload",
        "storage_path": "supabase://media-vault/user-alice/vid-1234_meeting.mp4",
        "file_size_bytes": 25000000,
        "status": "pending",
        "progress_percent": 0
    }
    mock_supabase.table().insert().execute.return_value = MagicMock(data=[mock_record])

    with patch("routers.videos.get_supabase_admin", return_value=mock_supabase):
        with patch("routers.videos.execute_video_pipeline"):
            resp = client.post("/api/videos/complete-upload", json={
                "video_id": "vid-1234",
                "storage_path": "supabase://media-vault/user-alice/vid-1234_meeting.mp4",
                "title": "Alice Video",
                "original_filename": "meeting.mp4",
                "file_size_bytes": 25000000
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "vid-1234"
            assert data["user_id"] == "user-alice"
            assert data["status"] == "pending"

    app.dependency_overrides.clear()
