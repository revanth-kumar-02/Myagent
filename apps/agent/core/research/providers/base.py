from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str = ""
    content: Optional[str] = None
    score: float = 0.0
    provider_name: str = "unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WebSearchProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Returns provider identifier (e.g. 'tavily', 'brave')"""
        pass

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        """Perform web search for query and return list of search result items."""
        pass

    @abstractmethod
    async def extract(self, urls: List[str]) -> Dict[str, str]:
        """Extract full text content from given list of URLs. Returns mapping {url: text}."""
        pass
