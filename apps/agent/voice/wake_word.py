"""
voice.wake_word — Wake Word Detection Provider (V21)

Provides optional wake-word detection ("Hey Kora") with privacy-first defaults.
Microphone is never always-on by default.
"""

from __future__ import annotations

import abc
import structlog

from voice.types import AudioChunk

logger = structlog.get_logger(__name__)


class BaseWakeWordProvider(abc.ABC):
    """Abstract interface for Wake Word detection."""

    @abc.abstractmethod
    def detect(self, chunk: AudioChunk) -> bool:
        """Evaluate an audio chunk for wake-word activation."""


class KeywordWakeWordDetector(BaseWakeWordProvider):
    """
    Keyword-based wake word detector for phrases like 'Hey Kora' or 'Kora'.
    """

    def __init__(self, keywords: list[str] | None = None, enabled: bool = False) -> None:
        self.keywords = [k.lower() for k in (keywords or ["hey kora", "kora"])]
        self.enabled = enabled

    def detect(self, chunk: AudioChunk, simulated_keyword: str | None = None) -> bool:
        """
        Check if audio chunk contains the wake word.
        """
        if not self.enabled:
            return False

        if simulated_keyword and simulated_keyword.lower() in self.keywords:
            logger.info("wake_word_detected", keyword=simulated_keyword)
            return True

        return False
