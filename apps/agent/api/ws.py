"""
api.ws — WebSocket handler

Manages persistent WebSocket connections and dispatches typed messages
to the appropriate handlers (agent session, indexer, etc.).

One AgentSession per WebSocket connection. Sessions are keyed by session_id.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from api.deps import get_agent_dependencies
from core.session import AgentSession
from core.types import ChatRequest
from permissions.types import PermissionGrant
from rag.indexer import Indexer
from pathlib import Path

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, deps: dict = Depends(get_agent_dependencies)) -> None:
    """
    Primary WebSocket endpoint.
    All client-server communication flows through this single connection.
    """
    await ws.accept()
    session_id = uuid.uuid4()
    logger.info("ws_connected", session_id=str(session_id))

    # Bound send function for this connection
    async def ws_send(payload: dict) -> None:
        try:
            await ws.send_json(payload)
        except Exception:
            pass

    session: AgentSession | None = None

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")
            payload = msg.get("payload", {})
            project_id_str = msg.get("project_id")
            project_id = uuid.UUID(project_id_str) if project_id_str else None

            match msg_type:
                case "CHAT_REQUEST":
                    if session is None:
                        session = AgentSession(
                            session_id=session_id,
                            project_id=project_id,
                            ws_send=ws_send,
                            **deps,
                        )
                        await session.start()

                    request = ChatRequest(
                        message=payload["message"],
                        session_id=session_id,
                        project_id=project_id,
                        attachments=payload.get("attachments", []),
                    )
                    response = await session.run(request)
                    await ws_send({
                        "type": "CHAT_DONE",
                        "session_id": str(session_id),
                        "payload": {
                            "full_text": response.full_text,
                            "sources": [
                                {"chunk_id": str(s.chunk_id), "file_path": s.file_path,
                                 "start_line": s.start_line, "end_line": s.end_line}
                                for s in response.sources
                            ],
                            "web_sources": [
                                {"url": w.url, "title": w.title, "snippet": w.snippet}
                                for w in response.web_sources
                            ],
                            "model_used": response.model_used,
                            "input_tokens": response.input_tokens,
                            "output_tokens": response.output_tokens,
                            "latency_ms": response.latency_ms,
                        },
                    })

                case "INDEX_REQUEST":
                    # Spawn indexing as a background task
                    indexer = Indexer(
                        project_id=uuid.UUID(payload["project_id"]),
                        root_path=Path(payload["root_path"]),
                        db=deps["db"],
                        model_router=deps["model_router"],
                        ws_send=ws_send,
                    )
                    # TODO: run as background task in feature phase
                    stats = await indexer.run(incremental=payload.get("incremental", True))
                    await ws_send({
                        "type": "INDEX_DONE",
                        "payload": {
                            "project_id": payload["project_id"],
                            "files_added": stats.files_added,
                            "files_changed": stats.files_changed,
                            "files_deleted": stats.files_deleted,
                            "chunks_total": stats.chunks_total,
                            "duration_ms": stats.duration_ms,
                        },
                    })

                case "PERMISSION_RESPONSE":
                    if session:
                        grant = PermissionGrant(
                            request_id=uuid.UUID(payload["request_id"]),
                            granted=payload["granted"],
                        )
                        # TODO: forward to session's PermissionGate in feature phase

                case "HEARTBEAT":
                    await ws_send({"type": "HEARTBEAT", "payload": {}})

                case _:
                    logger.warning("ws_unknown_message_type", type=msg_type)

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=str(session_id))
        if session:
            await session.stop()
    except Exception as e:
        logger.exception("ws_error", session_id=str(session_id), error=str(e))
        await ws_send({"type": "ERROR", "payload": {"code": "INTERNAL_ERROR", "message": str(e)}})
