"""
voice.session — Real-Time Voice Assistant Session (V21)

Coordinates speech streaming, state transitions, barge-in interruption,
unified Context Resolver & Agent pipeline execution, and TTS streaming.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable

import structlog

from voice.stt import GemmaSTTProvider, StreamingSTTBuffer
from voice.tts import VoiceSynthesizer
from voice.types import (
    AudioChunk,
    TranscriptionResult,
    VoiceSessionConfig,
    VoiceSessionMetrics,
    VoiceState,
)

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class VoiceAssistantSession:
    """
    Manages real-time conversational voice interaction for a client connection.
    """

    def __init__(
        self,
        session_id: str | None = None,
        config: VoiceSessionConfig | None = None,
        stt_buffer: StreamingSTTBuffer | None = None,
        tts_synthesizer: VoiceSynthesizer | None = None,
        agent_runner: Callable[[str], Awaitable[str]] | None = None,
        ws_send: WSSend | None = None,
    ) -> None:
        self.session_id = session_id or f"vsession_{uuid.uuid4().hex[:8]}"
        self.config = config or VoiceSessionConfig()
        self._stt = stt_buffer or StreamingSTTBuffer()
        self._tts = tts_synthesizer or VoiceSynthesizer()
        self._agent_runner = agent_runner
        self._ws_send = ws_send
        self._state: VoiceState = VoiceState.IDLE
        self._metrics = VoiceSessionMetrics(session_id=self.session_id)
        self._current_task: asyncio.Task[None] | None = None

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def metrics(self) -> VoiceSessionMetrics:
        return self._metrics

    async def _set_state(self, new_state: VoiceState) -> None:
        """Update voice state and emit notification frame."""
        old_state = self._state
        self._state = new_state
        logger.info("voice_state_changed", session_id=self.session_id, old=old_state.value, new=new_state.value)

        if self._ws_send:
            await self._ws_send({
                "type": "VOICE_STATE",
                "session_id": self.session_id,
                "payload": {
                    "state": new_state.value,
                    "previous_state": old_state.value,
                },
            })

    async def start_listening(self) -> None:
        """Begin listening for user speech."""
        self._stt.reset()
        await self._set_state(VoiceState.LISTENING)

    async def stop_listening(self) -> None:
        """Stop listening and return to idle."""
        self._stt.reset()
        await self._set_state(VoiceState.IDLE)

    async def interrupt(self) -> None:
        """
        Barge-in: Interrupt Kora's current speech synthesis and playback.
        """
        logger.info("voice_barge_in_triggered", session_id=self.session_id)
        self._metrics.interruptions_count += 1
        self._tts.cancel()

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        await self._set_state(VoiceState.INTERRUPTED)

        if self._ws_send:
            await self._ws_send({
                "type": "VOICE_INTERRUPTED",
                "session_id": self.session_id,
                "payload": {
                    "interruption_count": self._metrics.interruptions_count,
                },
            })

        # Immediately transition to listening for new speech
        await self.start_listening()

    async def feed_audio_chunk(
        self,
        chunk: AudioChunk,
        simulated_transcript: str | None = None,
        simulated_response: str | None = None,
    ) -> None:
        """
        Stream an incoming audio chunk into the session.
        Handles barge-in, VAD boundary detection, agent execution, and TTS.
        """
        # Barge-in: User spoke while Kora was speaking
        if self._state == VoiceState.SPEAKING and self.config.barge_in_enabled:
            await self.interrupt()

        if self._state != VoiceState.LISTENING:
            await self.start_listening()

        speech_ended = self._stt.feed_chunk(chunk)

        if speech_ended:
            # Process complete utterance
            await self._process_utterance(simulated_transcript, simulated_response)

    async def _process_utterance(
        self,
        simulated_transcript: str | None = None,
        simulated_response: str | None = None,
    ) -> None:
        """Transcribe audio, query agent, and stream TTS response."""
        # 1. Transcribe
        await self._set_state(VoiceState.TRANSCRIBING)
        stt_start = time.monotonic()
        transcription = await self._stt.finalize_transcription(mock_transcript=simulated_transcript)
        self._metrics.stt_latency_ms = (time.monotonic() - stt_start) * 1000

        if not transcription.text:
            await self._set_state(VoiceState.IDLE)
            return

        if self._ws_send:
            await self._ws_send({
                "type": "VOICE_TRANSCRIPT",
                "session_id": self.session_id,
                "payload": transcription.to_dict(),
            })

        # 2. Agent Execution (Unified Context + Pipeline)
        await self._set_state(VoiceState.THINKING)
        agent_start = time.monotonic()

        if self._agent_runner:
            response_text = await self._agent_runner(transcription.text)
        elif simulated_response:
            response_text = simulated_response
        else:
            response_text = f"I processed your request: '{transcription.text}'."

        self._metrics.agent_latency_ms = (time.monotonic() - agent_start) * 1000

        # 3. Speech Synthesis & Playback
        await self._set_state(VoiceState.SPEAKING)
        self._tts.reset()
        tts_start = time.monotonic()
        chunks = await self._tts.synthesize(response_text, voice_name=self.config.voice_name)
        self._metrics.tts_latency_ms = (time.monotonic() - tts_start) * 1000

        for chunk in chunks:
            if self._state != VoiceState.SPEAKING:
                # Interrupted mid-stream
                break

            if self._ws_send:
                await self._ws_send({
                    "type": "VOICE_AUDIO_CHUNK",
                    "session_id": self.session_id,
                    "payload": chunk.to_dict(),
                })
            # Small non-blocking yield
            await asyncio.sleep(0.01)

        # 4. Return to IDLE
        if self._state == VoiceState.SPEAKING:
            await self._set_state(VoiceState.IDLE)
