# Kora Real-Time Voice Assistant Architecture (V21)

## 1. Overview & Purpose
The **Real-Time Voice Assistant Layer (V21)** enables natural, full-duplex spoken conversation with Kora. It integrates microphone streaming, low-latency Speech-to-Text (STT), Text-to-Speech (TTS), and instant barge-in interruptions while executing directly through Kora's unified Context Resolver, Agent Planning, Safety Gates, Tools, RAG, Memory, Knowledge Graph, and Web Research.

```
+-----------------------------------------------------------------------------------+
|                                REAL-TIME AUDIO FLOW                               |
|                                                                                   |
|  User Microphone                                                                  |
|         |                                                                         |
|         v (WebSocket Audio Chunks)                                                |
|  [StreamingSTTBuffer & VAD] (Speech Boundary & Silence Detection)                 |
|         |                                                                         |
|         v                                                                         |
|  [GemmaSTTProvider] (Dynamic 'gemma-audio' routing, No Hardcoded IDs)             |
|         |                                                                         |
|         v                                                                         |
|  [Unified Context Resolver] (Conversation + RAG + Memory + Graph + Research)      |
|         |                                                                         |
|         v                                                                         |
|  [Agent Pipeline] (Planner -> Reasoning -> Tools / PermissionGate -> Verifier)    |
|         |                                                                         |
|         v                                                                         |
|  [VoiceSynthesizer] (Sentence Chunking + Streaming PCM/WAV TTS)                   |
|         |                                                                         |
|         v (Barge-In Interrupt: User speaks -> Immediately abort TTS & restart)   |
|  Client Audio Playback                                                            |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Components (`apps/agent/voice/`)

### 2.1 Domain Types (`types.py`)
- `VoiceState`: State machine (`IDLE`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `ACTING`, `SPEAKING`, `INTERRUPTED`, `ERROR`).
- `AudioChunk`: Raw audio binary frame container with sample rate, format (`PCM_16BIT`, `WAV`, `OPUS`), and finality flag.
- `TranscriptionResult`: Output containing transcript text, confidence score, language, duration, and model used.
- `TTSChunk`: Streaming audio payload with chunk index, sentence segment, and sample rate.
- `VoiceSessionConfig` & `VoiceSessionMetrics`: Session configuration parameters and latency performance metrics (STT latency, agent latency, TTS latency, interruption counts).

### 2.2 STT Provider & Streaming Buffer (`stt.py`)
- **Dynamic Model Resolution**: Uses `ModelRouter.select("audio")` or `ModelRegistry.get_by_capability("audio")` (`gemma-audio` / `google/gemma-3n-e4b-it`).
- **Streaming Buffer & VAD**: Buffers audio frames, computes silence thresholds, and determines speech boundary completion.
- **Credential Protection**: Masks passwords, tokens (`ghp_...`, `sk-...`), or secrets detected in speech transcripts before routing or logging.

### 2.3 TTS Provider & Voice Synthesizer (`tts.py`)
- **Conversational Chunking**: Automatically segments LLM responses into conversational sentence chunks.
- **Immediate Playback Abort**: Provides `cancel()` and `reset()` APIs to instantly halt TTS generation and audio streaming upon user barge-in.

### 2.4 Wake-Word Detector Provider (`wake_word.py`)
- `KeywordWakeWordDetector`: Optional keyword detection ("Hey Kora", "Kora").
- **Privacy-First**: Disabled by default; microphone is never always-on without user configuration.

### 2.5 Voice Session & Manager (`session.py` & `manager.py`)
- **VoiceAssistantSession**: Coordinates real-time state machine transitions, audio streaming, unified Agent execution, and WebSocket message framing (`VOICE_STATE`, `VOICE_TRANSCRIPT`, `VOICE_AUDIO_CHUNK`, `VOICE_INTERRUPTED`).
- **Barge-In Handling**: When user speech is detected during `SPEAKING` state, the session cancels active TTS, logs the interruption, and transitions to `LISTENING`.
- **VoiceSessionManager**: Manages active sessions per WebSocket connection.

---

## 3. Flutter Desktop UI Presentation (`apps/desktop/lib/features/voice/presentation/`)
1. `voice_assistant_view.dart`: Voice assistant dashboard and modal.
2. `voice_waveform_widget.dart`: Visual waveform animated according to real-time voice states (`LISTENING`, `THINKING`, `SPEAKING`, `INTERRUPTED`).
3. `voice_transcript_widget.dart`: Live speech bubbles displaying user utterances and Kora responses.
4. `voice_controls_widget.dart`: Microphone toggle, mute button, and manual barge-in interrupt action.

---

## 4. Privacy & Safety Guidelines
- **Microphone Disabled by Default**: Audio capture requires explicit activation by the user.
- **No Raw Audio Storage**: Audio buffers exist ephemerally in RAM and are never permanently persisted to disk or logged.
- **Secret Sanitization**: Transcripts are scanned and sanitized (`[REDACTED_SECRET]`) prior to context injection or logging.
