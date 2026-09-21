"""
voice.tts — Text-to-Speech Provider & Speech Synthesizer (V21)

Synthesizes conversational responses into streaming audio chunks with
support for immediate cancellation and barge-in interruption.
"""

from __future__ import annotations

import abc
import asyncio
import re
import structlog
from typing import AsyncIterator

from voice.types import AudioFormat, TTSChunk

logger = structlog.get_logger(__name__)


class BaseTTSProvider(abc.ABC):
    """Abstract interface for Text-to-Speech synthesis."""

    @abc.abstractmethod
    async def synthesize(self, text: str, voice_name: str = "kora_neutral") -> list[TTSChunk]:
        """Synthesize text into audio chunks."""


class VoiceSynthesizer(BaseTTSProvider):
    """
    Synthesizes text into streaming PCM audio chunks with playback cancellation support.
    """

    def __init__(self, sample_rate: int = 24000) -> None:
        self._sample_rate = sample_rate
        self._is_cancelled = False

    def cancel(self) -> None:
        """Immediately abort active synthesis and playback for barge-in."""
        self._is_cancelled = True
        logger.info("tts_synthesis_cancelled_barge_in")

    def reset(self) -> None:
        """Reset cancellation state for new synthesis."""
        self._is_cancelled = False

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into conversational sentence units for streaming TTS."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in sentences if s.strip()]

    async def synthesize(self, text: str, voice_name: str = "kora_neutral") -> list[TTSChunk]:
        """
        Synthesize text into a sequence of audio chunks.
        """
        if self._is_cancelled:
            return []

        sentences = self._split_sentences(text)
        if not sentences:
            sentences = [text]

        chunks: list[TTSChunk] = []
        for idx, sentence in enumerate(sentences):
            if self._is_cancelled:
                logger.info("tts_stream_aborted_early", completed_chunks=idx)
                break

            # Generate synthetic PCM audio data proportional to sentence length
            # ~200ms per character at 24kHz 16-bit mono
            num_samples = max(2400, len(sentence) * 240)
            mock_pcm_bytes = b"\x00" * (num_samples * 2)

            is_last = (idx == len(sentences) - 1)
            chunk = TTSChunk(
                chunk_index=idx,
                audio_data=mock_pcm_bytes,
                text_segment=sentence,
                is_final=is_last,
                sample_rate=self._sample_rate,
                format=AudioFormat.PCM_16BIT,
            )
            chunks.append(chunk)

        return chunks

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice_name: str = "kora_neutral",
    ) -> AsyncIterator[TTSChunk]:
        """
        Stream audio chunks as text arrives.
        """
        self._is_cancelled = False
        chunk_idx = 0

        async for text_segment in text_stream:
            if self._is_cancelled:
                break
            if not text_segment.strip():
                continue

            num_samples = max(2400, len(text_segment) * 240)
            mock_pcm = b"\x00" * (num_samples * 2)

            yield TTSChunk(
                chunk_index=chunk_idx,
                audio_data=mock_pcm,
                text_segment=text_segment,
                is_final=False,
                sample_rate=self._sample_rate,
                format=AudioFormat.PCM_16BIT,
            )
            chunk_idx += 1
