import httpx
import logging
from typing import List, Dict
from config import settings
from core.research.providers.base import WebSearchProvider, SearchResultItem

logger = logging.getLogger(__name__)

class BraveProvider(WebSearchProvider):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(settings, "BRAVE_API_KEY", "") or ""

    @property
    def name(self) -> str:
        return "brave"

    async def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        if not self.api_key:
            raise ValueError("Brave API key not configured")

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        params = {
            "q": query,
            "count": max_results
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        web_results = data.get("web", {}).get("results", [])
        for item in web_results:
            results.append(
                SearchResultItem(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    score=0.8,
                    provider_name=self.name,
                    metadata={"extra_snippets": item.get("extra_snippets", [])}
                )
            )
        return results

    async def extract(self, urls: List[str]) -> Dict[str, str]:
        extracted_map = {}
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for u in urls:
                try:
                    resp = await client.get(u, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    if resp.status_code == 200:
                        extracted_map[u] = resp.text[:10000]
                except Exception as e:
                    logger.debug(f"Brave basic HTTP extract failed for {u}: {e}")
        return extracted_map
