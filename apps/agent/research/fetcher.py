"""
research.fetcher — Asynchronous Source Page Fetcher and Content Extractor (V6)

Responsibilities:
  - Asynchronously fetch full HTML source pages for high-priority search results
  - Strip navigation, footer, scripts, ads, and boilerplate elements
  - Extract structured, bounded textual content
  - Gracefully handle timeouts, 4xx/5xx HTTP errors, and SSL failures
"""

from __future__ import annotations

import asyncio
from typing import Sequence

import bs4
import httpx
import structlog

from research.normalizer import clean_text

logger = structlog.get_logger(__name__)

# Elements to strip completely from web pages
_BOILERPLATE_TAGS = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "iframe",
    "noscript",
    "svg",
    "button",
    "form",
]

_DEFAULT_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_MAX_PAGE_CHARS = 4000


class PageFetcher:
    """
    Fetches source web pages asynchronously with content cleaning and bounded limits.
    """

    def __init__(
        self,
        timeout_seconds: float = 8.0,
        max_chars_per_page: int = DEFAULT_MAX_PAGE_CHARS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_chars_per_page = max_chars_per_page

    async def fetch_page(self, url: str) -> str | None:
        """
        Fetch a single URL and return clean text content, or None on failure.
        """
        if not url or not url.startswith("http"):
            return None

        try:
            async with httpx.AsyncClient(
                headers=_DEFAULT_FETCH_HEADERS,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.debug("page_fetch_non_200", url=url, status=resp.status_code)
                    return None

                return self.extract_clean_text(resp.text)
        except (httpx.HTTPError, httpx.TimeoutException, Exception) as e:
            logger.debug("page_fetch_failed", url=url, error=str(e))
            return None

    async def fetch_pages_batch(self, urls: Sequence[str]) -> dict[str, str | None]:
        """
        Fetch a list of URLs concurrently.
        """
        tasks = [self.fetch_page(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        page_map: dict[str, str | None] = {}
        for url, res in zip(urls, results):
            if isinstance(res, str):
                page_map[url] = res
            else:
                page_map[url] = None
        return page_map

    def extract_clean_text(self, html_content: str) -> str:
        """
        Parse HTML and extract clean text up to max_chars_per_page.
        """
        if not html_content:
            return ""

        soup = bs4.BeautifulSoup(html_content, "html.parser")

        # Strip boilerplate tags
        for tag in soup(_BOILERPLATE_TAGS):
            tag.decompose()

        # Extract text from main / article if present, else body
        container = soup.find("article") or soup.find("main") or soup.body or soup

        # Extract paragraphs and headings
        blocks: list[str] = []
        for elem in container.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            txt = clean_text(elem.get_text())
            if len(txt) > 20:  # Skip tiny fragments
                blocks.append(txt)

        full_text = "\n\n".join(blocks)
        if len(full_text) > self.max_chars_per_page:
            full_text = full_text[: self.max_chars_per_page] + " ... [truncated]"

        return full_text
