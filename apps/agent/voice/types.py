"""
voice.types — Domain Types for Real-Time Voice Assistant (V21)

Defines voice states, audio chunk containers, transcription models,
TTS audio buffers, session configs, and audio performance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class VoiceState(str, Enum):
    """Real-time conversational voice assistant states."""
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    ACTING = "acting"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class AudioFormat(str, Enum):
    """Supported audio encodings."""
    PCM_16BIT = "pcm_16bit"
    WAV = "wav"
    OPUS = "opus"
    AAC = "aac"


@dataclass
class AudioChunk:
    """Represents a chunk of binary audio data streamed from microphone or server."""
    chunk_id: str
    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    format: AudioFormat = AudioFormat.PCM_16BIT
    is_final: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "format": self.format.value,
            "is_final": self.is_final,
            "size_bytes": len(self.data),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TranscriptionResult:
    """Output from the speech-to-text (STT) pipeline."""
    text: str
    is_final: bool = True
    confidence: float = 1.0
    language: str = "en"
    duration_seconds: float = 0.0
    model_used: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "is_final": self.is_final,
            "confidence": self.confidence,
            "language": self.language,
            "duration_seconds": round(self.duration_seconds, 3),
            "model_used": self.model_used,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TTSChunk:
    """Output audio segment from the text-to-speech (TTS) engine."""
    chunk_index: int
    audio_data: bytes
    text_segment: str
    is_final: bool = False
    sample_rate: int = 24000
    format: AudioFormat = AudioFormat.PCM_16BIT
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "text_segment": self.text_segment,
            "is_final": self.is_final,
            "sample_rate": self.sample_rate,
            "size_bytes": len(self.audio_data),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VoiceSessionConfig:
    """Configuration options for a live voice session."""
    voice_name: str = "kora_neutral"
    sample_rate: int = 16000
    enable_wake_word: bool = False
    barge_in_enabled: bool = True
    auto_stop_silence_seconds: float = 1.5
    language: str = "en"


@dataclass
class VoiceSessionMetrics:
    """Latency and interaction metrics for a voice session."""
    session_id: str
    stt_latency_ms: float = 0.0
    agent_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    interruptions_count: int = 0
    total_audio_duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "stt_latency_ms": round(self.stt_latency_ms, 2),
            "agent_latency_ms": round(self.agent_latency_ms, 2),
            "tts_latency_ms": round(self.tts_latency_ms, 2),
            "interruptions_count": self.interruptions_count,
            "total_audio_duration_seconds": round(self.total_audio_duration_seconds, 2),
        }
