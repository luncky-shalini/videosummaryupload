import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_supabase_admin

client = TestClient(app)


def test_auth_check_method_nonexistent():
    """Verify check-method returns exists=False for unknown emails."""
    mock_supabase = MagicMock()
    mock_supabase.auth.admin.list_users.return_value = []

    with patch("routers.auth.get_supabase_admin", return_value=mock_supabase):
        res = client.post("/api/auth/check-method", json={"email": "nonexistent_user_999@test.com"})
        assert res.status_code == 200
        data = res.json()
        assert data["exists"] is False
        assert data["has_google"] is False
        assert data["has_email"] is False


def test_auth_check_method_existing_user():
    """Verify check-method correctly detects existing accounts."""
    mock_supabase = MagicMock()
    mock_user = MagicMock()
    mock_user.email = "anikita123@gmail.com"
    mock_user.email_confirmed_at = "2024-01-01T00:00:00Z"
    mock_user.app_metadata = {"provider": "email", "providers": ["email"]}
    mock_supabase.auth.admin.list_users.return_value = [mock_user]

    with patch("routers.auth.get_supabase_admin", return_value=mock_supabase):
        res = client.post("/api/auth/check-method", json={"email": "anikita123@gmail.com"})
        assert res.status_code == 200
        data = res.json()
        assert data["exists"] is True
        assert data["has_email"] is True
        assert data["is_confirmed"] is True


def test_auth_check_method_google_user():
    """Verify check-method correctly detects Google accounts."""
    mock_supabase = MagicMock()
    mock_user = MagicMock()
    mock_user.email = "luckyshalu000@gmail.com"
    mock_user.email_confirmed_at = "2024-01-01T00:00:00Z"
    mock_user.app_metadata = {"provider": "google", "providers": ["google"]}
    mock_supabase.auth.admin.list_users.return_value = [mock_user]

    with patch("routers.auth.get_supabase_admin", return_value=mock_supabase):
        res = client.post("/api/auth/check-method", json={"email": "luckyshalu000@gmail.com"})
        assert res.status_code == 200
        data = res.json()
        assert data["exists"] is True
        assert data["has_google"] is True


def test_register_validation():
    """Ensure invalid email and short passwords are rejected with 400."""
    res1 = client.post("/api/auth/register", json={"email": "notanemail", "password": "validpassword123"})
    assert res1.status_code == 400
    assert "valid email address" in res1.json()["detail"]

    res2 = client.post("/api/auth/register", json={"email": "test@example.com", "password": "123"})
    assert res2.status_code == 400
    assert "at least 6 characters" in res2.json()["detail"]


def test_confirm_account_endpoint():
    """Ensure confirm-account endpoint successfully confirms email without errors."""
    mock_supabase = MagicMock()
    mock_user = MagicMock()
    mock_user.email = "anikita123@gmail.com"
    mock_user.email_confirmed_at = "2024-01-01T00:00:00Z"
    mock_supabase.auth.admin.list_users.return_value = [mock_user]

    with patch("routers.auth.get_supabase_admin", return_value=mock_supabase):
        res = client.post("/api/auth/confirm-account", json={"email": "anikita123@gmail.com"})
        assert res.status_code == 200
        assert res.json()["success"] is True


def test_unauthenticated_protected_endpoints():
    """Requirement 5: Ensure protected endpoints reject unauthenticated requests with 401."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    
    # 1. Videos listing
    assert client.get("/api/videos").status_code == 401

    # 2. Upload video
    assert client.post("/api/videos/upload").status_code == 401

    # 3. Import URL
    assert client.post("/api/videos/import-url", json={"url": "https://youtu.be/test"}).status_code == 401

    # 4. Video detail
    assert client.get(f"/api/videos/{fake_id}").status_code == 401

    # 5. Media stream
    assert client.get(f"/api/videos/{fake_id}/stream").status_code == 401

    # 6. Status polling
    assert client.get(f"/api/videos/{fake_id}/status").status_code == 401

    # 7. PDF export
    assert client.get(f"/api/videos/{fake_id}/export/pdf").status_code == 401

    # 8. AI Chat
    assert client.post(f"/api/videos/{fake_id}/chat", json={"question": "summarize"}).status_code == 401

    # 9. Subtitle translation
    assert client.post(f"/api/videos/{fake_id}/subtitles/translate", json={"target_language": "Telugu"}).status_code == 401

    # 10. Delete video
    assert client.delete(f"/api/videos/{fake_id}").status_code == 401

