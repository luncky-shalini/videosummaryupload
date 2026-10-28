import pytest
from fastapi.testclient import TestClient
import sys
import os

# Ensure backend root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_api_root():
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_docs_and_openapi():
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200

def test_vercel_rewrite_with_x_matched_path():
    # Simulates Vercel Edge proxy forwarding to /api/index.py with x-matched-path header
    resp = client.get("/api/index.py", headers={"x-matched-path": "/health"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

    docs_resp = client.get("/api/index.py", headers={"x-matched-path": "/docs"})
    assert docs_resp.status_code == 200

    root_resp = client.get("/api/index.py", headers={"x-matched-path": "/"})
    assert root_resp.status_code == 200
    assert root_resp.json()["status"] == "online"

def test_vercel_rewrite_with_path_prefix_injection():
    # Simulates Vercel Serverless Function receiving raw rewritten scope path
    resp = client.get("/api/index.py/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

    resp_main = client.get("/main.py/health")
    assert resp_main.status_code == 200
    assert resp_main.json()["status"] == "healthy"
