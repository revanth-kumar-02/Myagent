"""
tests.agent.test_voice_v21 — Test Suite for Real-Time Voice Assistant (V21)

Verifies:
- Voice state transitions and audio chunk representations
- Dynamic audio model resolution via ModelRouter / ModelRegistry
- Streaming STT buffering, silence/VAD boundary detection, and partial transcripts
- TTS sentence synthesis, streaming audio generation, and cancellation
- Optional Wake-Word detection provider abstraction
- Full conversational voice turn through unified Agent pipeline
- Barge-in interruption when user speaks during playback
- Privacy protections and transcript secret masking
- VoiceSessionManager lifecycle
"""

import pathlib
import pytest
from unittest.mock import AsyncMock

from core.model_router import ModelRouter
from models.registry import ModelRegistry
from voice import (
    AudioChunk,
    AudioFormat,
    BaseSTTProvider,
    BaseTTSProvider,
    BaseWakeWordProvider,
    GemmaSTTProvider,
    KeywordWakeWordDetector,
    StreamingSTTBuffer,
    TTSChunk,
    TranscriptionResult,
    VoiceAssistantSession,
    VoiceSessionConfig,
    VoiceSessionManager,
    VoiceSessionMetrics,
    VoiceState,
    VoiceSynthesizer,
)


@pytest.fixture
def mock_audio_registry(tmp_path: pathlib.Path) -> ModelRegistry:
    yaml_content = """
models:
  gemma-audio:
    provider: huggingface
    model_id: "google/gemma-3n-e4b-it"
    capabilities:
      - audio
    context_window: 32768
"""
    reg_file = tmp_path / "registry.yaml"
    reg_file.write_text(yaml_content)
    return ModelRegistry.load(reg_file)


def test_voice_domain_types_and_state_enums():
    """Verify all domain models and voice state enums."""
    chunk = AudioChunk(
        chunk_id="chk_01",
        data=b"\x00\x01\x02\x03",
        sample_rate=16000,
        channels=1,
        format=AudioFormat.PCM_16BIT,
        is_final=False,
    )
    assert chunk.to_dict()["size_bytes"] == 4
    assert chunk.format == AudioFormat.PCM_16BIT

    trans = TranscriptionResult(
        text="Hello Kora",
        is_final=True,
        confidence=0.98,
        language="en",
        duration_seconds=1.2,
        model_used="gemma-audio",
    )
    assert trans.to_dict()["text"] == "Hello Kora"

    tts = TTSChunk(
        chunk_index=0,
        audio_data=b"\x00" * 100,
        text_segment="Hello there.",
        is_final=True,
        sample_rate=24000,
    )
    assert tts.to_dict()["size_bytes"] == 100

    states = [
        VoiceState.IDLE,
        VoiceState.LISTENING,
        VoiceState.TRANSCRIBING,
        VoiceState.THINKING,
        VoiceState.ACTING,
        VoiceState.SPEAKING,
        VoiceState.INTERRUPTED,
        VoiceState.ERROR,
    ]
    assert len(states) == 8


@pytest.mark.asyncio
async def test_gemma_stt_provider_dynamic_model_resolution(mock_audio_registry: ModelRegistry):
    """Ensure STT provider dynamically resolves the registered audio model."""
    router = ModelRouter(mock_audio_registry)
    stt = GemmaSTTProvider(router=router)

    info = await stt.get_model_info()
    assert info["name"] == "gemma-audio"
    assert info["model_id"] == "google/gemma-3n-e4b-it"

    res = await stt.transcribe(b"\x00" * 32000, sample_rate=16000, mock_transcript="List my project goals")
    assert res.text == "List my project goals"
    assert res.model_used == "gemma-audio"


@pytest.mark.asyncio
async def test_streaming_stt_buffer_and_vad():
    """Test feeding audio frames into StreamingSTTBuffer and detecting utterance boundaries."""
    buffer = StreamingSTTBuffer(silence_threshold_bytes=1000)

    # 1. Feed partial non-final chunk
    chunk1 = AudioChunk(chunk_id="c1", data=b"\x00" * 400, is_final=False)
    assert buffer.feed_chunk(chunk1) is False

    # 2. Feed final chunk -> triggers speech end
    chunk2 = AudioChunk(chunk_id="c2", data=b"\x00" * 200, is_final=True)
    assert buffer.feed_chunk(chunk2) is True

    # 3. Finalize transcription
    res = await buffer.finalize_transcription(mock_transcript="Create a new task")
    assert res.text == "Create a new task"

    # 4. Cancellation
    buffer.feed_chunk(chunk1)
    buffer.cancel()
    assert buffer.get_audio_bytes() == b""


@pytest.mark.asyncio
async def test_voice_synthesizer_streaming_chunks_and_cancellation():
    """Test TTS synthesis sentence splitting, chunk streaming, and barge-in abort."""
    synthesizer = VoiceSynthesizer(sample_rate=24000)

    # 1. Synthesize multi-sentence response
    text = "First sentence completed. Second sentence following! Third sentence done."
    chunks = await synthesizer.synthesize(text)
    assert len(chunks) == 3
    assert chunks[0].text_segment == "First sentence completed."
    assert chunks[2].is_final is True

    # 2. Cancellation
    synthesizer.cancel()
    aborted_chunks = await synthesizer.synthesize("This should abort immediately.")
    assert len(aborted_chunks) == 0


def test_wake_word_detector_provider():
    """Test optional wake-word detection behavior."""
    detector = KeywordWakeWordDetector(keywords=["hey kora", "kora"], enabled=False)

    chunk = AudioChunk(chunk_id="chk", data=b"\x00" * 100)
    # When disabled -> never activates
    assert detector.detect(chunk, simulated_keyword="hey kora") is False

    # When enabled -> activates on keyword
    detector.enabled = True
    assert detector.detect(chunk, simulated_keyword="hey kora") is True
    assert detector.detect(chunk, simulated_keyword="alexa") is False


@pytest.mark.asyncio
async def test_voice_assistant_session_full_flow():
    """Test full conversational voice turn: Audio in -> STT -> Agent -> TTS -> State IDLE."""
    ws_mock = AsyncMock()

    async def mock_agent(query: str) -> str:
        return f"Agent response for: {query}"

    session = VoiceAssistantSession(
        session_id="v_session_test",
        agent_runner=mock_agent,
        ws_send=ws_mock,
    )

    assert session.state == VoiceState.IDLE

    # Stream final audio chunk
    chunk = AudioChunk(chunk_id="chk_final", data=b"\x00" * 1000, is_final=True)
    await session.feed_audio_chunk(
        chunk=chunk,
        simulated_transcript="Show my recent activity",
    )

    assert session.state == VoiceState.IDLE
    assert session.metrics.stt_latency_ms >= 0.0
    assert session.metrics.agent_latency_ms >= 0.0
    assert session.metrics.tts_latency_ms >= 0.0

    # Verify WS messages were dispatched
    msg_types = [call.args[0]["type"] for call in ws_mock.call_args_list]
    assert "VOICE_STATE" in msg_types
    assert "VOICE_TRANSCRIPT" in msg_types
    assert "VOICE_AUDIO_CHUNK" in msg_types


@pytest.mark.asyncio
async def test_barge_in_interruption():
    """Test that barge-in during SPEAKING immediately stops speech and transitions state."""
    ws_mock = AsyncMock()
    session = VoiceAssistantSession(
        session_id="v_session_barge_in",
        ws_send=ws_mock,
    )

    # Force session state to SPEAKING
    await session._set_state(VoiceState.SPEAKING)
    assert session.state == VoiceState.SPEAKING

    # Trigger interrupt
    await session.interrupt()
    assert session.state == VoiceState.LISTENING
    assert session.metrics.interruptions_count == 1

    msg_types = [call.args[0]["type"] for call in ws_mock.call_args_list]
    assert "VOICE_INTERRUPTED" in msg_types


@pytest.mark.asyncio
async def test_voice_privacy_and_secret_masking():
    """Verify secrets and passwords in transcribed audio are masked before processing."""
    stt = GemmaSTTProvider()

    res = await stt.transcribe(
        audio_data=b"\x00" * 1000,
        mock_transcript="Please connect with password: mysecretpassword999 to database",
    )
    assert "mysecretpassword999" not in res.text
    assert "[REDACTED_SECRET]" in res.text


def test_voice_session_manager_registration():
    """Test VoiceSessionManager registration and lookup."""
    mgr = VoiceSessionManager()

    s = mgr.create_session("sess_01")
    assert s.session_id == "sess_01"
    assert mgr.get_session("sess_01") is not None

    removed = mgr.remove_session("sess_01")
    assert removed is True
    assert mgr.get_session("sess_01") is None
