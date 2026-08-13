import logging
from urllib.parse import urlparse
from typing import List, Dict, Optional, Set
from datetime import datetime

from core.research.providers.base import SearchResultItem
from core.research.providers.router import SearchProviderRouter
from core.tools.registry import tool_registry

logger = logging.getLogger(__name__)

class ProcessedSource:
    def __init__(self, title: str, url: str, domain: str, provider: str, content_excerpt: str = "", relevance: float = 1.0):
        self.title = title
        self.url = url
        self.domain = domain
        self.provider = provider
        self.content_excerpt = content_excerpt
        self.relevance = relevance

class SourceManager:
    def __init__(self, search_router: SearchProviderRouter = None):
        self.search_router = search_router or SearchProviderRouter()
        self.seen_urls: Set[str] = set()

    def normalize_url(self, url: str) -> str:
        """Strips query fragments and trailing slashes for clean deduplication."""
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        return normalized.lower()

    def extract_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    def filter_and_deduplicate(self, search_items: List[SearchResultItem]) -> List[SearchResultItem]:
        unique_items = []
        for item in search_items:
            norm_url = self.normalize_url(item.url)
            if norm_url not in self.seen_urls:
                self.seen_urls.add(norm_url)
                unique_items.append(item)
            else:
                logger.info(f"Filtered duplicate URL: {item.url}")
        return unique_items

    async def collect_and_extract(self, search_items: List[SearchResultItem], provider_name: str) -> List[ProcessedSource]:
        """
        Deduplicates search items, attempts API extraction, and falls back to Playwright if content is missing.
        """
        deduped_items = self.filter_and_deduplicate(search_items)
        if not deduped_items:
            return []

        urls_to_extract = [item.url for item in deduped_items]
        
        # 1. API Extraction via SearchProviderRouter
        extracted_content = await self.search_router.extract(urls_to_extract, preferred_provider=provider_name)

        processed_sources = []
        for item in deduped_items:
            content = extracted_content.get(item.url) or item.snippet
            
            # 2. Playwright Fallback if snippet/content is too brief (< 100 chars) and Playwright tool is registered
            if len(content.strip()) < 100 and tool_registry.has_tool("browser"):
                try:
                    logger.info(f"Triggering Playwright browser extraction for dynamic page: {item.url}")
                    pw_res = await tool_registry.execute_tool("browser", {"action": "fetch_content", "url": item.url})
                    if pw_res.success and pw_res.data and isinstance(pw_res.data, str):
                        content = pw_res.data[:5000]
                except Exception as e:
                    logger.debug(f"Playwright extraction attempt skipped for {item.url}: {e}")

            domain = self.extract_domain(item.url)
            processed_sources.append(
                ProcessedSource(
                    title=item.title or f"Source ({domain})",
                    url=item.url,
                    domain=domain,
                    provider=item.provider_name or provider_name,
                    content_excerpt=content[:2000],
                    relevance=item.score
                )
            )

        return processed_sources
