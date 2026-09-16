import logging
from typing import List, Tuple, Dict, Optional
from core.research.providers.base import WebSearchProvider, SearchResultItem
from core.research.providers.tavily import TavilyProvider
from core.research.providers.duckduckgo import DuckDuckGoProvider
from core.observability import record_fallback_event

logger = logging.getLogger(__name__)

class SearchProviderRouter:
    """
    Locked Search Provider Router:
    Tavily = PRIMARY
    DuckDuckGo = FALLBACK
    Real external search results only — zero synthetic or mock search items.
    """

    def __init__(
        self,
        tavily: Optional[WebSearchProvider] = None,
        duckduckgo: Optional[WebSearchProvider] = None,
        brave: Optional[WebSearchProvider] = None
    ):
        self.primary = tavily or TavilyProvider()
        self.fallback = duckduckgo or brave or DuckDuckGoProvider()

    async def search(self, query: str, max_results: int = 5) -> Tuple[List[SearchResultItem], str]:
        """
        Attempts search via Tavily (primary).
        If Tavily fails or is unavailable, falls back strictly to DuckDuckGo.
        Returns (results, provider_used).
        """
        clean_query = query.strip()
        if not clean_query:
            return [], "none"

        # 1. Try Primary: Tavily
        try:
            results = await self.primary.search(clean_query, max_results=max_results)
            if results:
                logger.info(f"Web search successful using primary provider ({self.primary.name})")
                return results, self.primary.name
        except Exception as e:
            record_fallback_event(
                provider=self.primary.name,
                reason=str(e),
                fallback_provider=self.fallback.name
            )
            logger.warning(
                f"Primary provider ({self.primary.name}) search failed: {e}. Falling back to ({self.fallback.name})."
            )

        # 2. Try Fallback: DuckDuckGo
        try:
            results = await self.fallback.search(clean_query, max_results=max_results)
            if results:
                logger.info(f"Web search successful using fallback provider ({self.fallback.name})")
                return results, self.fallback.name
            else:
                logger.warning(f"Fallback provider ({self.fallback.name}) returned 0 results for '{clean_query}'")
        except Exception as e:
            record_fallback_event(
                provider=self.fallback.name,
                reason=str(e),
                fallback_provider="none"
            )
            logger.error(f"Fallback provider ({self.fallback.name}) search failed: {e}")

        # Both real providers failed or returned no results — return empty without fabricating results
        logger.error(f"All web search providers exhausted for query: '{clean_query}'")
        return [], "none"

    async def extract(self, urls: List[str], preferred_provider: str = "tavily") -> Dict[str, str]:
        if not urls:
            return {}

        provider = self.primary if preferred_provider == self.primary.name else self.fallback
        try:
            extracted = await provider.extract(urls)
            if extracted:
                return extracted
        except Exception as e:
            logger.warning(f"Extraction with {preferred_provider} failed: {e}")

        # Fallback extraction attempt
        alt_provider = self.fallback if provider == self.primary else self.primary
        try:
            return await alt_provider.extract(urls)
        except Exception as e:
            logger.warning(f"Fallback extraction with {alt_provider.name} failed: {e}")
            return {}

search_provider_router = SearchProviderRouter()
search_router = search_provider_router

