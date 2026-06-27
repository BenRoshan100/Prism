from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from server.utils import setup_logger

logger = setup_logger(__name__)

_STRIP_TAGS = ["script", "style", "nav", "footer", "header", "aside", "noscript"]
_CONTENT_TAGS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "blockquote"]
_MIN_BLOCK_LEN = 3


def load_url(url: str, timeout: float = 15.0) -> list[Document]:
    """Fetch URL and extract readable text as a LangChain Document.

    Raises ValueError if no extractable text found.
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    resp = httpx.get(
        url,
        follow_redirects=True,
        timeout=timeout,
        headers={"Accept": "text/html,text/plain,*/*"},
    )
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "text" not in content_type and "html" not in content_type:
        raise ValueError(f"URL does not return text content (got {content_type}): {url}")

    # Guard against huge pages (> 5MB) to prevent OOM on constrained deployments
    _MAX_BYTES = 5 * 1024 * 1024  # 5MB
    if len(resp.content) > _MAX_BYTES:
        raise ValueError(f"URL response too large ({len(resp.content) // 1024}KB > 5MB limit): {url}")

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    blocks = []
    for tag in soup.find_all(_CONTENT_TAGS):
        text = tag.get_text(separator=" ", strip=True)
        if len(text) >= _MIN_BLOCK_LEN:
            blocks.append(text)

    full_text = "\n\n".join(blocks)
    if not full_text.strip():
        raise ValueError(f"No extractable text found at {url}")

    logger.info("Loaded URL: %s (%d chars extracted)", url, len(full_text))

    return [
        Document(
            page_content=full_text,
            metadata={
                "source": url,
                "source_type": "url",
                "type": "web",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    ]
