import pytest
from pathlib import Path
from fastapi.testclient import TestClient


def test_serve_existing_file(tmp_path, monkeypatch):
    """Returns 200 + file content for a file that exists."""
    fake_raw = tmp_path / "raw"
    fake_raw.mkdir()
    pdf = fake_raw / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr("server.main.UPLOAD_DIR", fake_raw)

    from server.main import app
    client = TestClient(app)
    resp = client.get("/api/files/report.pdf")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 fake"


def test_serve_missing_file(tmp_path, monkeypatch):
    """Returns 404 for a filename that doesn't exist."""
    fake_raw = tmp_path / "raw"
    fake_raw.mkdir()

    monkeypatch.setattr("server.main.UPLOAD_DIR", fake_raw)

    from server.main import app
    client = TestClient(app)
    resp = client.get("/api/files/does_not_exist.pdf")
    assert resp.status_code == 404


def test_serve_blocks_path_traversal(tmp_path, monkeypatch):
    """Path traversal attempts are blocked (by Starlette routing or by is_relative_to handler check)."""
    fake_raw = tmp_path / "raw"
    fake_raw.mkdir()

    monkeypatch.setattr("server.main.UPLOAD_DIR", fake_raw)

    from server.main import app
    client = TestClient(app)

    # Bare ".." — normalized by Starlette routing layer before handler sees it; 404 result
    resp = client.get("/api/files/..")
    assert resp.status_code in (400, 404), f"Expected 400 or 404, got {resp.status_code}"

    # URL-encoded slash — rejected by Starlette routing before handler; 404 result
    resp2 = client.get("/api/files/..%2F..%2Fetc%2Fpasswd")
    assert resp2.status_code in (400, 404), f"Expected 400 or 404, got {resp2.status_code}"
