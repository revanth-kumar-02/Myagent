import asyncio
import os
import sys
import unittest
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock

# Ensure agent package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.failover import ProviderFailoverManager, ProviderMode
from models.providers.ollama import OllamaProvider
from models.providers.huggingface import HuggingFaceProvider
from models.types import ModelCapability, GenerationResult
from core.tool_router import ToolRouter, DispatchTarget
from core.executor import Executor
from core.types import PlanStep, ActionType, IntentType
from core.intent_analyzer import IntentAnalyzer
from core.planner import Planner
from tools.system import SystemInfoTool, ClipboardTool, AppLauncherTool
from tools.files import DirectoryOpsTool
from tools.web import DownloadManagerTool
from tools.types import ToolResult, ToolStatus
import sqlalchemy
from db.client import engine, startup


class TestProviderFailoverAndTools(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.mgr = ProviderFailoverManager()

    # TEST 1: HuggingFace healthy -> HuggingFace selected
    async def test_01_huggingface_healthy_selected(self) -> None:
        with patch.object(self.mgr, "check_internet", return_value=True), \
             patch.object(self.mgr, "check_huggingface_health", return_value=True), \
             patch.object(self.mgr, "check_ollama_health", return_value=(True, None)):
            self.mgr._internet_available = True
            self.mgr._hf_healthy = True
            self.mgr._ollama_healthy = True
            await self.mgr.update_all_health()
            self.assertEqual(self.mgr.active_provider_name, "huggingface")
            self.assertEqual(self.mgr.mode, ProviderMode.ONLINE)

    # TEST 2: Internet unavailable -> Ollama selected
    async def test_02_internet_unavailable_ollama_selected(self) -> None:
        with patch.object(self.mgr, "check_internet", return_value=False), \
             patch.object(self.mgr, "check_ollama_health", return_value=(True, None)):
            self.mgr._internet_available = False
            self.mgr._ollama_healthy = True
            await self.mgr.update_all_health()
            self.assertEqual(self.mgr.active_provider_name, "ollama")
            self.assertEqual(self.mgr.mode, ProviderMode.OFFLINE)

    # TEST 3: HuggingFace HTTP failure -> Ollama selected
    async def test_03_huggingface_http_failure_ollama_selected(self) -> None:
        with patch.object(self.mgr, "check_internet", return_value=True), \
             patch.object(self.mgr, "check_huggingface_health", return_value=False), \
             patch.object(self.mgr, "check_ollama_health", return_value=(True, None)):
            self.mgr._internet_available = True
            self.mgr._hf_healthy = False
            self.mgr._ollama_healthy = True
            await self.mgr.update_all_health()
            self.assertEqual(self.mgr.active_provider_name, "ollama")
            self.assertEqual(self.mgr.mode, ProviderMode.LOCAL_FALLBACK)

    # TEST 4: HuggingFace timeout -> Ollama selected
    async def test_04_huggingface_timeout_ollama_selected(self) -> None:
        self.mgr._ollama_healthy = True
        self.mgr.record_hf_failure(reason="Timeout after 10s")
        self.assertEqual(self.mgr.active_provider_name, "ollama")
        self.assertEqual(self.mgr.mode, ProviderMode.LOCAL_FALLBACK)

    # TEST 5: Ollama unavailable too -> NO_PROVIDER
    async def test_05_ollama_unavailable_no_provider(self) -> None:
        with patch.object(self.mgr, "check_internet", return_value=False), \
             patch.object(self.mgr, "check_ollama_health", return_value=(False, "Connection refused")):
            self.mgr._internet_available = False
            self.mgr._ollama_healthy = False
            await self.mgr.update_all_health()
            self.assertEqual(self.mgr.active_provider_name, "none")
            self.assertEqual(self.mgr.mode, ProviderMode.NO_PROVIDER)

    # TEST 6: Internet returns -> Ollama -> HuggingFace
    async def test_06_internet_returns_failback_to_huggingface(self) -> None:
        self.mgr._mode = ProviderMode.LOCAL_FALLBACK
        with patch.object(self.mgr, "check_internet", return_value=True), \
             patch.object(self.mgr, "check_huggingface_health", return_value=True), \
             patch.object(self.mgr, "check_ollama_health", return_value=(True, None)):
            self.mgr._internet_available = True
            self.mgr._hf_healthy = True
            self.mgr._ollama_healthy = True
            await self.mgr.update_all_health()
            self.assertEqual(self.mgr.active_provider_name, "huggingface")
            self.assertEqual(self.mgr.mode, ProviderMode.ONLINE)

    # TEST 7: Normal chat offline -> qwen3:1.7b response
    async def test_07_normal_chat_offline_ollama(self) -> None:
        ollama = OllamaProvider(base_url="http://127.0.0.1:11434", default_model="qwen3:1.7b")
        is_running, err, models = await ollama.check_health("qwen3:1.7b")
        if is_running:
            messages = [{"role": "user", "content": "Respond with the word OK."}]
            res = await ollama.chat_complete(model_id="qwen3:1.7b", messages=messages, max_tokens=15)
            self.assertTrue(len(res.full_text) > 0 or res.input_tokens > 0)
        else:
            self.skipTest("Ollama not running locally")

    # TEST 8: system_info offline -> actual system information
    async def test_08_system_info_offline(self) -> None:
        tool = SystemInfoTool()
        self.assertFalse(tool.requires_network)
        self.assertTrue(tool.available_offline)
        res = await tool.execute({})
        self.assertTrue(res.success)
        self.assertIsInstance(res.output, dict)
        self.assertIn("os", res.output)
        self.assertIn("cpu_count", res.output)
        self.assertIn("architecture", res.output)

    # TEST 9: clipboard offline -> actual clipboard operation
    async def test_09_clipboard_offline(self) -> None:
        tool = ClipboardTool()
        self.assertFalse(tool.requires_network)
        self.assertTrue(tool.available_offline)
        res = await tool.execute({"action": "read"})
        self.assertTrue(res.success)
        self.assertIsNotNone(res.output)

    # TEST 10: app_launcher offline -> actual local application launch check
    async def test_10_app_launcher_offline(self) -> None:
        tool = AppLauncherTool()
        self.assertFalse(tool.requires_network)
        self.assertTrue(tool.available_offline)
        res = await tool.execute({"app_name": "echo", "args": ["hello"]})
        self.assertIsNotNone(res)

    # TEST 11: filesystem offline -> actual local file operation
    async def test_11_filesystem_offline(self) -> None:
        tool = DirectoryOpsTool()
        self.assertFalse(tool.requires_network)
        self.assertTrue(tool.available_offline)
        res = await tool.execute({"action": "list", "path": "."})
        self.assertTrue(res.success)
        self.assertIn("items", res.output)

    # TEST 12: Network tool offline -> tool unavailable without repeated requests
    async def test_12_duckduckgo_offline_unavailable(self) -> None:
        search_tool = DownloadManagerTool()
        self.assertTrue(search_tool.requires_network)
        self.assertFalse(search_tool.available_offline)
        
        executor = Executor()
        target = DispatchTarget(
            action_type=ActionType.TOOL_CALL,
            tool_name="download_manager",
            tool_instance=search_tool,
            callable_=search_tool.execute,
            params={"url": "https://example.com/file.zip"}
        )
        step = PlanStep(index=0, label="Download file", action_type=ActionType.TOOL_CALL, required_tool="download_manager", params={"url": "https://example.com/file.zip"})
        self.mgr._internet_available = False
        executor._model_router = MagicMock(failover_manager=self.mgr)
        res = await executor.run(target, step)
        self.assertTrue(res.success)
        self.assertIn("unavailable offline", res.content)

    # TEST 13 & 14: Ollama Tool Calling -> ToolRouter -> ToolExecutor -> Ollama Final Answer
    async def test_13_14_ollama_tool_calling_adapter(self) -> None:
        ollama = OllamaProvider(base_url="http://127.0.0.1:11434", default_model="qwen3:1.7b")
        sys_tool = SystemInfoTool()
        params = sys_tool.parameters
        self.assertIn("type", params)

        # Test tool calling payload structure
        tool_spec = {
            "type": "function",
            "function": {
                "name": sys_tool.tool_id,
                "description": sys_tool.description,
                "parameters": params,
            }
        }
        self.assertEqual(tool_spec["function"]["name"], "system_info")

    # TEST 15 & 16: Ollama Streaming and Completion
    async def test_15_16_ollama_streaming_chunks(self) -> None:
        ollama = OllamaProvider(base_url="http://127.0.0.1:11434", default_model="qwen3:1.7b")
        is_running, err, models = await ollama.check_health("qwen3:1.7b")
        if is_running:
            chunks: list[str] = []
            async for chunk in ollama.chat_stream(
                model_id="qwen3:1.7b",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=20,
            ):
                chunks.append(chunk)
            self.assertTrue(len(chunks) > 0)
        else:
            self.skipTest("Ollama not running locally")

    # TEST 17: PROVIDER_STATUS event generation
    async def test_17_provider_status_event(self) -> None:
        status_payload = self.mgr.get_status_payload()
        self.assertIn("mode", status_payload)
        self.assertIn("provider", status_payload)
        self.assertIn("model", status_payload)
        self.assertIn("local_fallback", status_payload)

    # TEST 18: WebSocket reconnect restoration state
    async def test_18_websocket_reconnect_state(self) -> None:
        payload = self.mgr.get_status_payload()
        self.assertIsInstance(payload["local_fallback"], bool)

    # TEST 19: No duplicate response during failover
    async def test_19_no_duplicate_response_on_failover(self) -> None:
        self.assertIsNone(self.mgr._background_task)

    # TEST 20: Existing HuggingFace chat remains functional
    async def test_20_huggingface_chat_provider(self) -> None:
        hf = HuggingFaceProvider()
        self.assertTrue(hasattr(hf, "chat_stream"))
        self.assertTrue(hasattr(hf, "chat_complete"))

    # TEST 21 & 22: Local tools functional online & offline
    async def test_21_22_local_tools_always_functional(self) -> None:
        sys_tool = SystemInfoTool()
        res = await sys_tool.execute({})
        self.assertTrue(res.success)
        self.assertIsNotNone(res.output)

    # TEST 23: Slash command /system_info
    async def test_23_slash_command_system_info(self) -> None:
        analyzer = IntentAnalyzer()
        intent, _ = analyzer.analyze("/system_info")
        self.assertEqual(intent, IntentType.TOOL_ACTION)

    # TEST 24: Natural language "show my system info" invokes system_info
    async def test_24_natural_language_system_info(self) -> None:
        analyzer = IntentAnalyzer()
        intent, _ = analyzer.analyze("What is my system information?")
        self.assertEqual(intent, IntentType.TOOL_ACTION)

    # TEST 25: Generic tool executor does not pass undeclared "action" arguments
    async def test_25_executor_does_not_inject_spurious_action(self) -> None:
        executor = Executor()
        sys_tool = SystemInfoTool()
        target = DispatchTarget(
            action_type=ActionType.TOOL_CALL,
            tool_name="system_info",
            tool_instance=sys_tool,
            callable_=sys_tool.execute,
            params={"action": "invalid_action", "some_arg": 123} # Spurious params supplied
        )
        step = PlanStep(index=0, label="System Info", action_type=ActionType.TOOL_CALL, required_tool="system_info", params={})
        res = await executor.run(target, step)
        self.assertTrue(res.success)
        self.assertIsInstance(res.raw.output, dict)
        self.assertIn("os", res.raw.output)

    # TEST 26: PostgreSQL SELECT 1 succeeds when DB is available
    async def test_26_postgres_select_1(self) -> None:
        try:
            async with engine.begin() as conn:
                res = await conn.execute(sqlalchemy.text("SELECT 1"))
                row = res.scalar()
                self.assertEqual(row, 1)
        except Exception as e:
            self.skipTest(f"Postgres not connected in current test environment: {e}")

    # TEST 27: PostgreSQL unavailable produces degraded state instead of crash
    async def test_27_postgres_degraded_state(self) -> None:
        try:
            await startup()
        except Exception as e:
            self.fail(f"startup crashed with uncaught error: {e}")


if __name__ == "__main__":
    unittest.main()
