from unittest.mock import patch, MagicMock
import pytest
from server.url_loader import load_url


def _mock_response(html: str, status: int = 200):
    mock = MagicMock()
    mock.status_code = status
    mock.text = html
    mock.raise_for_status = MagicMock(
        side_effect=None if status == 200 else Exception(f"HTTP {status}")
    )
    return mock


SAMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
  <nav>Skip this nav text</nav>
  <h1>Main Title</h1>
  <p>First paragraph with enough text to be included in extraction.</p>
  <p>Second paragraph also has enough content here.</p>
  <script>var x = 1;</script>
  <footer>Skip footer text</footer>
</body>
</html>
"""


def test_load_url_returns_document():
    with patch("httpx.get", return_value=_mock_response(SAMPLE_HTML)):
        docs = load_url("https://example.com/article")
    assert len(docs) == 1


def test_load_url_extracts_text():
    with patch("httpx.get", return_value=_mock_response(SAMPLE_HTML)):
        docs = load_url("https://example.com/article")
    content = docs[0].page_content
    assert "Main Title" in content
    assert "First paragraph" in content
    assert "Second paragraph" in content


def test_load_url_excludes_nav_and_footer():
    with patch("httpx.get", return_value=_mock_response(SAMPLE_HTML)):
        docs = load_url("https://example.com/article")
    content = docs[0].page_content
    assert "Skip this nav text" not in content
    assert "Skip footer text" not in content
    assert "var x = 1" not in content


def test_load_url_metadata():
    with patch("httpx.get", return_value=_mock_response(SAMPLE_HTML)):
        docs = load_url("https://example.com/article")
    meta = docs[0].metadata
    assert meta["source"] == "https://example.com/article"
    assert meta["type"] == "web"
    assert "fetched_at" in meta


def test_load_url_raises_on_http_error():
    mock = MagicMock()
    mock.raise_for_status = MagicMock(side_effect=Exception("HTTP 404"))
    with patch("httpx.get", return_value=mock):
        with pytest.raises(Exception):
            load_url("https://example.com/missing")


def test_load_url_raises_on_empty_content():
    empty_html = "<html><body><nav>Only nav</nav><footer>Only footer</footer></body></html>"
    with patch("httpx.get", return_value=_mock_response(empty_html)):
        with pytest.raises(ValueError, match="No extractable text"):
            load_url("https://example.com/empty")
