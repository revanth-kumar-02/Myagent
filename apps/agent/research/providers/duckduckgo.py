"""
research.providers.duckduckgo — Exclusive DuckDuckGo Web Search Provider (V6)

Features:
  - DuckDuckGo HTML / Lite endpoint search via async httpx
  - Zero API keys required
  - Resilient retry handling with exponential backoff
  - Parsing of titles, URLs, and snippets using BeautifulSoup
  - Unwrapping of DuckDuckGo redirect URLs (uddg parameter)
  - Rate-limit and network timeout protection
"""

from __future__ import annotations

import asyncio
import random
import urllib.parse
from typing import Any

import bs4
import httpx
import structlog

from config import settings
from research.normalizer import ResultNormalizer, sanitize_url
from research.types import WebResult

logger = structlog.get_logger(__name__)

# Realistic browser headers for reliable scraping
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://html.duckduckgo.com/",
}

DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/"


class DuckDuckGoSearchError(Exception):
    """Raised when DuckDuckGo search fails."""


class DuckDuckGoProvider:
    """
    Exclusive DuckDuckGo search provider for Kora Web Research.
    """

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        initial_retry_delay: float = 0.5,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self._normalizer = ResultNormalizer()

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[WebResult]:
        """
        Execute an asynchronous search on DuckDuckGo and return normalized WebResults.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                results = await self._fetch_duckduckgo_html(clean_query, max_results)
                if results:
                    return results

                # If primary endpoint returned empty, try Lite endpoint as fallback
                results = await self._fetch_duckduckgo_lite(clean_query, max_results)
                return results

            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    "ddg_search_attempt_failed",
                    attempt=attempt,
                    query=clean_query,
                    error=str(e),
                )
                if attempt < self.max_retries:
                    delay = self.initial_retry_delay * (2 ** (attempt - 1)) + random.uniform(0.1, 0.3)
                    await asyncio.sleep(delay)
            except Exception as e:
                last_error = e
                logger.warning("ddg_unexpected_search_error", error=str(e))
                break

        logger.error("ddg_search_all_retries_failed", query=clean_query, error=str(last_error))
        return []

    async def _fetch_duckduckgo_html(self, query: str, max_results: int) -> list[WebResult]:
        """Fetch results from https://html.duckduckgo.com/html/."""
        async with httpx.AsyncClient(
            headers=_DEFAULT_HEADERS,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as client:
            resp = await client.post(
                DUCKDUCKGO_HTML_URL,
                data={"q": query, "b": ""},
            )

            if resp.status_code != 200:
                logger.warning("ddg_html_non_200", status=resp.status_code)
                return []

            return self._parse_html_results(resp.text, max_results)

    async def _fetch_duckduckgo_lite(self, query: str, max_results: int) -> list[WebResult]:
        """Fetch results from https://lite.duckduckgo.com/lite/."""
        async with httpx.AsyncClient(
            headers=_DEFAULT_HEADERS,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as client:
            resp = await client.post(
                DUCKDUCKGO_LITE_URL,
                data={"q": query},
            )

            if resp.status_code != 200:
                return []

            return self._parse_lite_results(resp.text, max_results)

    def _parse_html_results(self, html_content: str, max_results: int) -> list[WebResult]:
        """Parse standard HTML DuckDuckGo page."""
        soup = bs4.BeautifulSoup(html_content, "html.parser")
        results: list[WebResult] = []

        result_divs = [
            div for div in soup.find_all("div")
            if any("result" in str(cls) and "results_links" in str(cls) for cls in (div.get("class") or []))
        ]
        if not result_divs:
            result_divs = soup.find_all("div", class_="result")

        for div in result_divs:
            if len(results) >= max_results:
                break

            # Title & URL
            a_tag = div.find("a", class_="result__a") or div.find("a", class_="result__url")
            if not a_tag or not a_tag.get("href"):
                continue

            raw_url = str(a_tag.get("href") or "")
            title = a_tag.get_text(strip=True)

            # Snippet
            snippet_tag = div.find("a", class_="result__snippet") or div.find("div", class_="result__snippet")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

            clean_url = sanitize_url(raw_url)
            if not clean_url or not clean_url.startswith("http"):
                continue

            web_res = self._normalizer.normalize_result({
                "url": clean_url,
                "title": title,
                "snippet": snippet,
                "score": 1.0 - (len(results) * 0.05),  # Position decay
            })
            results.append(web_res)

        return results

    def _parse_lite_results(self, html_content: str, max_results: int) -> list[WebResult]:
        """Parse DuckDuckGo Lite HTML page."""
        soup = bs4.BeautifulSoup(html_content, "html.parser")
        results: list[WebResult] = []

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            i = 0
            while i < len(rows) and len(results) < max_results:
                link_tag = rows[i].find("a", class_="result-link")
                if link_tag and link_tag.get("href"):
                    raw_url = str(link_tag.get("href") or "")
                    title = link_tag.get_text(strip=True)
                    snippet = ""
                    if i + 1 < len(rows):
                        snip_td = rows[i + 1].find("td", class_="result-snippet")
                        if snip_td:
                            snippet = snip_td.get_text(strip=True)
                    clean_url = sanitize_url(raw_url)
                    if clean_url and clean_url.startswith("http"):
                        web_res = self._normalizer.normalize_result({
                            "url": clean_url,
                            "title": title,
                            "snippet": snippet,
                            "score": 1.0 - (len(results) * 0.05),
                        })
                        results.append(web_res)
                    i += 2
                else:
                    i += 1

        return results
