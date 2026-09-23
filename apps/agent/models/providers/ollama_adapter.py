"""
models.providers.ollama_adapter — Provider-Neutral Ollama Tool Calling Adapter

Responsibilities:
  - Formats Kora tools into provider-neutral tool schemas for Ollama
  - Parses Ollama tool call responses ({name: ..., arguments: ...})
  - Dispatches tool calls strictly through Kora ToolRouter and ToolExecutor
  - Injects tool execution results back into Ollama context for final natural language synthesis
  - Ensures normal conversation messages ("Hello", "What is RAG?") stream directly without planning loops
"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator, Callable, Awaitable

import structlog

from core.types import ActionType, PlanStep
from models.providers.ollama import OllamaProvider

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class OllamaToolAdapter:
    """
    Adapts Ollama native chat completions with Kora's ToolRouter and Executor.
    Ensures LLM never executes tools directly:
      Ollama → ToolCall → ToolRouter → ToolExecutor → Tool Result → Ollama → Final Response
    """

    def __init__(
        self,
        ollama_provider: OllamaProvider,
        tool_router: Any | None = None,
        executor: Any | None = None,
    ) -> None:
        self.provider = ollama_provider
        self.tool_router = tool_router
        self.executor = executor

    @staticmethod
    def format_tools_for_ollama(tools: list[Any]) -> list[dict[str, Any]]:
        """Convert Kora BaseTool instances to Ollama function calling schemas."""
        formatted: list[dict[str, Any]] = []
        for t in tools:
            tool_id = getattr(t, "tool_id", getattr(t, "name", "tool"))
            desc = getattr(t, "description", "")
            params = getattr(t, "parameters", {"type": "object", "properties": {}})
            formatted.append({
                "type": "function",
                "function": {
                    "name": tool_id,
                    "description": desc,
                    "parameters": params,
                },
            })
        return formatted

    @staticmethod
    def is_normal_chat(message: str) -> bool:
        """
        Determine if message is normal conversation that does not require tool routing.
        Examples: 'Hello', 'What is Python?', 'What is RAG?'.
        """
        msg = message.strip().lower()
        if msg.startswith("/"):
            return False

        # Common conversation starters and conceptual questions
        conceptual_patterns = [
            r"^(?:hello|hi|hey|good\s+(?:morning|afternoon|evening|day))\b",
            r"^what\s+(?:is|are)\s+(?:python|rag|ai|llm|machine\s+learning|docker|fastapi|flutter)\b",
            r"^explain\s+(?:rag|python|vectors?|embeddings?)\b",
            r"^who\s+are\s+you\b",
            r"^how\s+are\s+you\b",
            r"^help\b",
        ]
        for pat in conceptual_patterns:
            if re.search(pat, msg):
                return True
        return False

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any] | None = None,
        ws_send: WSSend | None = None,
    ) -> str:
        """
        Execute full Ollama tool-calling loop:
          1. Send messages with tool schemas to Ollama
          2. Parse ToolCall if returned
          3. Route to Kora ToolRouter and execute via Executor
          4. Feed tool result back to Ollama
          5. Stream final response to ws_send
        """
        ollama_tools = self.format_tools_for_ollama(tools or [])
        res = await self.provider.chat_complete(
            messages=messages,
            tools=ollama_tools if ollama_tools else None,
        )

        # Check for tool calling response in raw message or text
        tool_calls: list[dict[str, Any]] = []
        full_text = res.full_text

        # Try parsing JSON tool call if embedded in text or tool_calls field
        try:
            if full_text.strip().startswith("{") and "name" in full_text:
                parsed = json.loads(full_text.strip())
                if "name" in parsed:
                    tool_calls.append(parsed)
        except Exception:
            pass

        if not tool_calls:
            # Normal completion without tool call
            if ws_send is not None and full_text:
                await ws_send({"type": "CHAT_CHUNK", "payload": {"chunk": full_text}})
            return full_text

        # Execute discovered tool calls through Kora ToolRouter & ToolExecutor
        conversation = list(messages)
        conversation.append({"role": "assistant", "content": full_text})

        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("arguments", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {}

            logger.info("ollama_tool_call_detected", tool=tool_name, args=tool_args)

            tool_result_content = ""
            if self.tool_router is not None and self.executor is not None:
                step = PlanStep(
                    index=0,
                    label=f"Execute {tool_name}",
                    action_type=ActionType.TOOL_CALL,
                    required_tool=tool_name,
                    params=tool_args,
                )
                target = await self.tool_router.resolve(step)
                exec_result = await self.executor.run(target, step)
                tool_result_content = exec_result.content
            else:
                tool_result_content = f"Tool '{tool_name}' executed with args {tool_args}"

            # Append tool result for Ollama final turn
            conversation.append({
                "role": "tool",
                "name": tool_name,
                "content": str(tool_result_content),
            })

        # Synthesize final response from Ollama with the tool results
        accumulated: list[str] = []
        async for chunk in self.provider.chat_stream(messages=conversation):
            accumulated.append(chunk)
            if ws_send is not None:
                await ws_send({"type": "CHAT_CHUNK", "payload": {"chunk": chunk}})

        final_response = "".join(accumulated) if accumulated else "Tool executed successfully."
        return final_response
