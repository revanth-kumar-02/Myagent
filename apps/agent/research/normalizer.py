"""
research.normalizer — Result Normalizer and URL Sanitizer (V6)

Responsibilities:
  - Canonicalize and sanitize search URLs (strip tracking query params & anchors)
  - Extract root domains
  - Unescape HTML entities and normalize whitespace in titles and snippets
  - Compute content hash for deduplication
"""

from __future__ import annotations

import hashlib
import html
import re
import urllib.parse
from typing import Any

from research.types import WebResult, WebSource

# Tracking parameters to strip from URLs
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "msclkid",
    "ref",
    "source",
}


def sanitize_url(raw_url: str) -> str:
    """
    Strips tracking query parameters and anchor fragments from a URL.
    """
    if not raw_url:
        return ""

    # Decode if it's a DuckDuckGo redirect link e.g. //duckduckgo.com/l/?uddg=http%3A%2F%2F...
    if "duckduckgo.com/l/?" in raw_url or "uddg=" in raw_url:
        parsed_ddg = urllib.parse.urlparse(raw_url)
        params = urllib.parse.parse_qs(parsed_ddg.query)
        if "uddg" in params and params["uddg"]:
            raw_url = urllib.parse.unquote(params["uddg"][0])

    try:
        parsed = urllib.parse.urlparse(raw_url)
        if not parsed.scheme or not parsed.netloc:
            # Add scheme if missing
            if raw_url.startswith("//"):
                parsed = urllib.parse.urlparse("https:" + raw_url)
            elif not raw_url.startswith("http"):
                parsed = urllib.parse.urlparse("https://" + raw_url)

        query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        filtered_params = [
            (k, v) for k, v in query_params if k.lower() not in _TRACKING_PARAMS
        ]
        new_query = urllib.parse.urlencode(filtered_params)

        clean_url = urllib.parse.urlunparse((
            parsed.scheme.lower() or "https",
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            new_query,
            "",  # Strip fragment/anchor
        ))
        return clean_url
    except Exception:
        return raw_url.strip()


def extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def clean_text(text: str) -> str:
    """Strip HTML tags, unescape entities, and normalize whitespace."""
    if not text:
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities
    clean = html.unescape(clean)
    # Normalize whitespace
    clean = " ".join(clean.split())
    return clean.strip()


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized text."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ResultNormalizer:
    """
    Transforms raw search provider output into standardized WebResult & WebSource objects.
    """

    def normalize_result(
        self,
        raw_result: dict[str, Any] | WebResult,
        source_provider: str = "duckduckgo",
    ) -> WebResult:
        """
        Normalize a raw result into a standardized WebResult.
        """
        if isinstance(raw_result, WebResult):
            raw_url = raw_result.url
            raw_title = raw_result.title
            raw_snippet = raw_result.snippet
            raw_score = raw_result.score
            raw_content = raw_result.raw_content
        else:
            raw_url = raw_result.get("url") or raw_result.get("link") or raw_result.get("href") or ""
            raw_title = raw_result.get("title") or ""
            raw_snippet = raw_result.get("snippet") or raw_result.get("body") or raw_result.get("content") or ""
            raw_score = float(raw_result.get("score", 0.0))
            raw_content = raw_result.get("raw_content")

        clean_url_str = sanitize_url(raw_url)
        domain = extract_domain(clean_url_str)
        clean_title_str = clean_text(raw_title)
        clean_snippet_str = clean_text(raw_snippet)

        return WebResult(
            url=clean_url_str,
            title=clean_title_str,
            snippet=clean_snippet_str,
            score=raw_score,
            source=source_provider,
            domain=domain,
            raw_content=raw_content,
        )

    def to_web_source(self, result: WebResult) -> WebSource:
        """Convert WebResult into a tracked WebSource."""
        c_hash = compute_text_hash(f"{result.title} {result.snippet}")
        return WebSource(
            url=result.url,
            title=result.title,
            snippet=result.snippet,
            domain=result.domain or extract_domain(result.url),
            source_type="web_search",
            content_hash=c_hash,
            raw_content=result.raw_content,
            score=result.score,
        )
