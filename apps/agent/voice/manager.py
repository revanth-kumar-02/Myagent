"""
voice.manager — Voice Session Manager (V21)

Registers, manages, and routes WebSocket audio events to active voice sessions.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable
import structlog

from voice.session import VoiceAssistantSession
from voice.types import AudioChunk, VoiceSessionConfig

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class VoiceSessionManager:
    """
    Manages active voice sessions across WebSocket connections.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, VoiceAssistantSession] = {}

    def get_session(self, session_id: str) -> VoiceAssistantSession | None:
        """Retrieve an active voice session."""
        return self._sessions.get(session_id)

    def create_session(
        self,
        session_id: str,
        config: VoiceSessionConfig | None = None,
        agent_runner: Callable[[str], Awaitable[str]] | None = None,
        ws_send: WSSend | None = None,
    ) -> VoiceAssistantSession:
        """Create and register a new voice session."""
        session = VoiceAssistantSession(
            session_id=session_id,
            config=config,
            agent_runner=agent_runner,
            ws_send=ws_send,
        )
        self._sessions[session_id] = session
        logger.info("voice_session_registered", session_id=session_id)
        return session

    def remove_session(self, session_id: str) -> bool:
        """Unregister a voice session."""
        session = self._sessions.pop(session_id, None)
        if session:
            logger.info("voice_session_unregistered", session_id=session_id)
            return True
        return False
