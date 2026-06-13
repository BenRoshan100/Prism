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
    resp = httpx.get(url, follow_redirects=True, timeout=timeout)
    resp.raise_for_status()

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
                "type": "web",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    ]
