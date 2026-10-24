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
    res = client.post("/api/auth/check-method", json={"email": "nonexistent_user_999@test.com"})
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is False
    assert data["has_google"] is False
    assert data["has_email"] is False


def test_auth_check_method_existing_user():
    """Verify check-method correctly detects existing accounts."""
    res = client.post("/api/auth/check-method", json={"email": "anikita123@gmail.com"})
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is True
    assert data["has_email"] is True
    assert data["is_confirmed"] is True


def test_auth_check_method_google_user():
    """Verify check-method correctly detects Google accounts."""
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
    res = client.post("/api/auth/confirm-account", json={"email": "anikita123@gmail.com"})
    assert res.status_code == 200
    assert res.json()["success"] is True
