"""research package."""
from research.types import WebResult, ResearchResponse
from research.router import ResearchRouter
from research.normalizer import ResultNormalizer
__all__ = ["WebResult", "ResearchResponse", "ResearchRouter", "ResultNormalizer"]
