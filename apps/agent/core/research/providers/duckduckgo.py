import re
import httpx
import logging
from html import unescape
from typing import List, Dict, Optional
from urllib.parse import unquote, parse_qs, urlparse

from core.research.providers.base import WebSearchProvider, SearchResultItem

logger = logging.getLogger(__name__)

class DuckDuckGoProvider(WebSearchProvider):
    """
    DuckDuckGo search provider.
    Serves as the locked fallback provider when Tavily is unavailable or fails.
    Uses real external web search without requiring API keys or third-party wrappers.
    """

    @property
    def name(self) -> str:
        return "duckduckgo"

    async def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        results: List[SearchResultItem] = []

        # Attempt 1: DuckDuckGo HTML Search
        try:
            results = await self._search_html(clean_query, max_results)
            if results:
                return results
        except Exception as e:
            logger.debug(f"DuckDuckGo HTML search attempt failed ({e}), falling back to Instant Answer API.")

        # Attempt 2: DuckDuckGo Instant Answer API
        try:
            results = await self._search_instant_api(clean_query, max_results)
            if results:
                return results
        except Exception as e:
            logger.warning(f"DuckDuckGo Instant Answer API failed: {e}")

        return results

    async def _search_html(self, query: str, max_results: int) -> List[SearchResultItem]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://html.duckduckgo.com/",
        }
        url = "https://html.duckduckgo.com/html/"
        data = {"q": query, "b": ""}

        async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
            resp = await client.post(url, data=data)
            if resp.status_code != 200:
                raise RuntimeError(f"DuckDuckGo HTML search returned status code {resp.status_code}")

            pattern = r'<a[^>]+class=[\"\']result__a[\"\'][^>]+href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>'
            matches = re.findall(pattern, resp.text, re.DOTALL)
            snippets = re.findall(r'<a[^>]+class=[\"\']result__snippet[\"\'][^>]*>(.*?)</a>', resp.text, re.DOTALL)

            results: List[SearchResultItem] = []
            for i, (href, raw_title) in enumerate(matches):
                if len(results) >= max_results:
                    break

                # Filter out advertising / click tracking URLs
                if "/y.js" in href or "ad_provider" in href or "ad_domain" in href:
                    continue

                actual_url = href
                if "uddg=" in href:
                    try:
                        parsed = parse_qs(urlparse(href).query)
                        if "uddg" in parsed:
                            actual_url = unquote(parsed["uddg"][0])
                    except Exception:
                        pass

                if not actual_url.startswith("http"):
                    continue

                clean_title = unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
                raw_snip = snippets[i] if i < len(snippets) else ""
                clean_snippet = unescape(re.sub(r"<[^>]+>", "", raw_snip)).strip()

                results.append(
                    SearchResultItem(
                        title=clean_title or "Web Result",
                        url=actual_url,
                        snippet=clean_snippet,
                        score=0.85,
                        provider_name=self.name,
                        metadata={"source": "duckduckgo_html"}
                    )
                )

            return results

    async def _search_instant_api(self, query: str, max_results: int) -> List[SearchResultItem]:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 0}

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()

        results: List[SearchResultItem] = []

        # Check primary Abstract
        if data.get("AbstractURL") and data.get("AbstractText"):
            results.append(
                SearchResultItem(
                    title=data.get("Heading") or query,
                    url=data["AbstractURL"],
                    snippet=data["AbstractText"],
                    score=0.9,
                    provider_name=self.name,
                    metadata={"source": "duckduckgo_instant_abstract"}
                )
            )

        # Check Related Topics
        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if isinstance(topic, dict) and topic.get("FirstURL") and topic.get("Text"):
                results.append(
                    SearchResultItem(
                        title=topic.get("Text", "").split(" - ")[0][:100],
                        url=topic["FirstURL"],
                        snippet=topic.get("Text", ""),
                        score=0.8,
                        provider_name=self.name,
                        metadata={"source": "duckduckgo_instant_related"}
                    )
                )

        return results

    async def extract(self, urls: List[str]) -> Dict[str, str]:
        extracted_map: Dict[str, str] = {}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            for u in urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code == 200:
                        clean_text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
                        clean_text = re.sub(r"<style[^>]*>.*?</style>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
                        clean_text = re.sub(r"<[^>]+>", " ", clean_text)
                        clean_text = re.sub(r"\s+", " ", clean_text).strip()
                        extracted_map[u] = clean_text[:12000]
                except Exception as e:
                    logger.debug(f"DuckDuckGo extraction failed for {u}: {e}")
        return extracted_map
