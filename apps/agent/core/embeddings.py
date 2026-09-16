import logging
import hashlib
import asyncio
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_VECTOR_DIMENSION = 384

class BaseEmbeddingProvider:
    """Abstract Base Class for Memory Vector Embedding Providers."""
    
    def __init__(self, dimension: int = DEFAULT_VECTOR_DIMENSION):
        self.dimension = dimension

    async def get_embedding(self, text: str) -> List[float]:
        raise NotImplementedError

class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock embedding provider for testing without external API calls or costs."""
    
    def __init__(self, dimension: int = DEFAULT_VECTOR_DIMENSION):
        super().__init__(dimension=dimension)

    async def get_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.dimension
            
        words = [w.strip(".,!?()[]{}'\"") for w in text.lower().split() if w.strip(".,!?()[]{}'\"")]
        if not words:
            return [0.0] * self.dimension
            
        combined = [0.0] * self.dimension
        for word in words:
            word_bytes = word.encode("utf-8")
            for i in range(self.dimension):
                h = hashlib.sha256(word_bytes + str(i).encode("utf-8")).digest()
                val = (int.from_bytes(h[:4], "big") / 4294967295.0) * 2.0 - 1.0
                combined[i] += val
            
        # Normalize vector
        magnitude = (sum(x * x for x in combined)) ** 0.5
        if magnitude > 0:
            combined = [round(x / magnitude, 6) for x in combined]
            
        return combined

class ConfiguredEmbeddingProvider(BaseEmbeddingProvider):
    """Handles embedding generation with safety guards, timeouts, and fallback to mock if unconfigured."""
    
    def __init__(
        self,
        provider_name: str = "mock",
        api_key: Optional[str] = None,
        dimension: int = DEFAULT_VECTOR_DIMENSION,
        timeout_seconds: float = 5.0
    ):
        super().__init__(dimension=dimension)
        self.provider_name = provider_name.lower() if provider_name else "mock"
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.fallback_provider = MockEmbeddingProvider(dimension=dimension)

    async def get_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.dimension

        if self.provider_name == "mock" or not self.api_key:
            return await self.fallback_provider.get_embedding(text)

        try:
            # Wrap API call with timeout protection
            return await asyncio.wait_for(
                self._fetch_remote_embedding(text),
                timeout=self.timeout_seconds
            )
        except Exception as e:
            logger.warning(f"Embedding API call failed ({e}). Falling back to deterministic embedding.")
            return await self.fallback_provider.get_embedding(text)

    async def _fetch_remote_embedding(self, text: str) -> List[float]:
        # Remote vendor integrations (OpenAI / Cohere / Ollama) can be plugged here
        # Defaults to fallback if external provider is not actively active
        return await self.fallback_provider.get_embedding(text)

default_embedding_provider = ConfiguredEmbeddingProvider()
