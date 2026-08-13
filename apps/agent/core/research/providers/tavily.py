import httpx
import logging
from typing import List, Dict, Any
from config import settings
from core.research.providers.base import WebSearchProvider, SearchResultItem

logger = logging.getLogger(__name__)

class TavilyProvider(WebSearchProvider):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(settings, "TAVILY_API_KEY", "") or ""

    @property
    def name(self) -> str:
        return "tavily"

    async def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        if not self.api_key:
            raise ValueError("Tavily API key not configured")

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", []):
            results.append(
                SearchResultItem(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", "") or item.get("content", ""),
                    score=item.get("score", 0.0),
                    provider_name=self.name,
                    metadata={"raw": item}
                )
            )
        return results

    async def extract(self, urls: List[str]) -> Dict[str, str]:
        if not self.api_key or not urls:
            return {}

        url = "https://api.tavily.com/extract"
        payload = {
            "api_key": self.api_key,
            "urls": urls
        }

        extracted_map = {}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            for item in data.get("results", []):
                u = item.get("url")
                raw_c = item.get("raw_content") or item.get("content", "")
                if u and raw_c:
                    extracted_map[u] = raw_c
        except Exception as e:
            logger.warning(f"Tavily extract failed: {e}")

        return extracted_map
