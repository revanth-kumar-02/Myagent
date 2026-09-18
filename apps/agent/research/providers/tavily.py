"""
research.providers.tavily — Disabled Provider (DuckDuckGo is Exclusive)
"""

from __future__ import annotations


class TavilyError(Exception):
    """Raised if Tavily is invoked."""


class TavilyProvider:
    """
    Deprecated / Disabled provider. Kora uses DuckDuckGo exclusively.
    """

    def __init__(self) -> None:
        raise NotImplementedError("Tavily is disabled — DuckDuckGo is the exclusive search provider for Kora.")
