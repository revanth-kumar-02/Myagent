"""
tests.agent.test_tools_v8 — Comprehensive Test Suite for Kora's Tool System & Computer Control (V8)
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from permissions.gate import PermissionDeniedError, PermissionGate
from permissions.types import PermissionGrant
from tools.audit import ToolAuditLogger, sanitize_audit_payload
from tools.base import BaseTool, ToolValidationError
from tools.platforms.factory import get_platform_adapter
from tools.platforms.linux import LinuxAdapter
from tools.platforms.macos import MacOSAdapter
from tools.platforms.windows import WindowsAdapter
from tools.registry import ToolNotFoundError, ToolRegistry, build_default_registry
from tools.types import PermissionLevel, PlatformOS, ToolCategory, ToolResult, ToolStatus


# ── 1. Tool Registry & Schemas ────────────────────────────────────────────────


class TestToolRegistry:

    def test_default_registry_contains_all_core_tools(self) -> None:
        reg = build_default_registry()
        tools = reg.all()
        assert len(tools) >= 20

        # Check all 5 categories are populated
        sys_tools = reg.get_by_category(ToolCategory.SYSTEM)
        assert len(sys_tools) >= 4

        file_tools = reg.get_by_category(ToolCategory.FILES)
        assert len(file_tools) >= 7

        comp_tools = reg.get_by_category(ToolCategory.COMPUTER)
        assert len(comp_tools) >= 4

        web_tools = reg.get_by_category(ToolCategory.WEB)
        assert len(web_tools) >= 4

        dev_tools = reg.get_by_category(ToolCategory.DEVELOPMENT)
        assert len(dev_tools) >= 3

    def test_lookup_by_tool_id(self) -> None:
        reg = build_default_registry()
        read_tool = reg.get("file_read")
        assert read_tool.name == "file_read"
        assert read_tool.category == ToolCategory.FILES

    def test_lookup_unknown_raises_not_found(self) -> None:
        reg = build_default_registry()
        with pytest.raises(ToolNotFoundError, match="Tool not found"):
            reg.get("nonexistent_tool_id")

    def test_to_schema_exports_valid_function_calling_schemas(self) -> None:
        reg = build_default_registry()
        schemas = reg.to_schema()
        assert len(schemas) >= 20
        for s in schemas:
            assert "name" in s
            assert "description" in s
            assert "parameters" in s
            assert s["parameters"]["type"] == "object"


# ── 2. Input Validation & Timeout Handling ────────────────────────────────────


@pytest.mark.asyncio
class TestInputValidationAndTimeout:

    async def test_missing_required_parameter_fails_gracefully(self) -> None:
        reg = build_default_registry()
        read_tool = reg.get("file_read")
        # Missing 'path' parameter
        res = await read_tool.run({})
        assert res.success is False
        assert "Missing required parameter" in (res.error or "")

    async def test_timeout_enforcement(self) -> None:
        class SlowTool(BaseTool):
            @property
            def tool_id(self) -> str: return "slow_tool"
            @property
            def category(self) -> ToolCategory: return ToolCategory.SYSTEM
            @property
            def description(self) -> str: return "Simulates slow operation"
            @property
            def parameters(self) -> dict[str, Any]: return {"type": "object"}
            @property
            def timeout(self) -> float: return 0.1  # 100ms timeout

            async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
                await asyncio.sleep(0.5)
                return self._make_result(output="Done")

        slow = SlowTool()
        res = await slow.run({})
        assert res.status == ToolStatus.TIMEOUT
        assert "timed out after 0.1s" in (res.error or "")


# ── 3. Platform Abstraction ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestPlatformAdapters:

    async def test_linux_adapter(self) -> None:
        adapter = LinuxAdapter()
        assert adapter.platform_os == PlatformOS.LINUX
        info = await adapter.get_system_info()
        assert info["os"] == "Linux"
        assert "cpu_count" in info

        # Clipboard buffer
        await adapter.write_clipboard("Linux test buffer")
        clip = await adapter.read_clipboard()
        assert "Linux test buffer" in clip

    async def test_windows_adapter(self) -> None:
        adapter = WindowsAdapter()
        assert adapter.platform_os == PlatformOS.WINDOWS
        info = await adapter.get_system_info()
        assert info["os"] == "Windows"

        await adapter.write_clipboard("Windows test buffer")
        clip = await adapter.read_clipboard()
        assert "Windows test buffer" in clip

    async def test_macos_adapter(self) -> None:
        adapter = MacOSAdapter()
        assert adapter.platform_os == PlatformOS.MACOS
        info = await adapter.get_system_info()
        assert info["os"] == "macOS"

        await adapter.write_clipboard("macOS test buffer")
        clip = await adapter.read_clipboard()
        assert "macOS test buffer" in clip

    async def test_platform_factory_resolution(self) -> None:
        lin = get_platform_adapter(force_platform="linux")
        assert lin.platform_os == PlatformOS.LINUX

        win = get_platform_adapter(force_platform="win32")
        assert win.platform_os == PlatformOS.WINDOWS

        mac = get_platform_adapter(force_platform="darwin")
        assert mac.platform_os == PlatformOS.MACOS


# ── 4. Core Tools Execution ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCoreToolsExecution:

    async def test_file_tools_lifecycle(self, tmp_path: Path) -> None:
        reg = build_default_registry()
        create_tool = reg.get("file_create")
        read_tool = reg.get("file_read")
        write_tool = reg.get("file_write")
        rename_tool = reg.get("file_rename")
        delete_tool = reg.get("file_delete")

        target_file = str(tmp_path / "kora_sample.txt")
        renamed_file = str(tmp_path / "kora_renamed.txt")

        # Create
        res = await create_tool.run({"path": target_file})
        assert res.success is True
        assert Path(target_file).exists()

        # Write
        res = await write_tool.run({"path": target_file, "content": "Hello Kora V8"})
        assert res.success is True

        # Read
        res = await read_tool.run({"path": target_file})
        assert res.success is True
        assert res.output["content"] == "Hello Kora V8"

        # Write / Append
        res = await write_tool.run({"path": target_file, "content": "\nSecond Line", "append": True})
        assert res.success is True
        assert "Second Line" in Path(target_file).read_text()

        # Rename
        res = await rename_tool.run({"path": target_file, "new_name": "kora_renamed.txt"})
        assert res.success is True
        assert not Path(target_file).exists()
        assert Path(renamed_file).exists()

        # Delete
        res = await delete_tool.run({"path": renamed_file})
        assert res.success is True
        assert not Path(renamed_file).exists()

    async def test_system_info_tool(self) -> None:
        reg = build_default_registry()
        sys_tool = reg.get("system_info")
        res = await sys_tool.run({})
        assert res.success is True
        assert "os" in res.output
        assert "cpu_count" in res.output

    async def test_clipboard_tool(self) -> None:
        reg = build_default_registry()
        clip_tool = reg.get("clipboard")

        # Write
        res = await clip_tool.run({"action": "write", "text": "Kora Clipboard V8"})
        assert res.success is True

        # Read
        res = await clip_tool.run({"action": "read"})
        assert res.success is True
        assert "Kora Clipboard V8" in res.output["content"]

    async def test_computer_tools(self) -> None:
        reg = build_default_registry()
        win_tool = reg.get("window_manager")
        mouse_tool = reg.get("mouse_control")
        kb_tool = reg.get("keyboard_control")
        screen_tool = reg.get("screen_capture")

        # Window Manager
        res = await win_tool.run({"action": "list"})
        assert res.success is True

        # Mouse
        res = await mouse_tool.run({"action": "position"})
        assert res.success is True

        # Keyboard
        res = await kb_tool.run({"action": "type", "text": "echo ok"})
        assert res.success is True

        # Screen Capture
        res = await screen_tool.run({"full_screen": True})
        assert res.success is True

    async def test_web_tools(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        reg = build_default_registry()
        browser_tool = reg.get("browser_control")
        nav_tool = reg.get("page_navigation")
        interact_tool = reg.get("page_interaction")
        dl_tool = reg.get("download_manager")

        # Browser
        res = await browser_tool.run({"action": "launch"})
        assert res.success is True

        # Nav
        res = await nav_tool.run({"url": "https://example.com"})
        assert res.success is True

        # Interact
        res = await interact_tool.run({"action": "click", "selector": "#btn"})
        assert res.success is True

        # Download (with hermetic mocked response)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<html>mock download</html>"

        async def mock_get(self, url, **kwargs):
            return mock_resp

        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

        dest_file = str(tmp_path / "mock_download.html")
        res = await dl_tool.run({"action": "download", "url": "https://example.com/file.zip", "destination_path": dest_file})
        assert res.success is True
        assert res.output["downloaded"] is True
        assert Path(dest_file).exists()

    async def test_dev_terminal_tool(self) -> None:
        reg = build_default_registry()
        term_tool = reg.get("terminal_exec")
        res = await term_tool.run({"command": "echo 'Kora Terminal Test'"})
        assert res.success is True
        assert "Kora Terminal Test" in res.output["stdout"]


# ── 5. Permission Gate Enforcement ────────────────────────────────────────────


@pytest.mark.asyncio
class TestPermissionSystem:

    async def test_permission_levels_defined_on_all_tools(self) -> None:
        reg = build_default_registry()
        for tool in reg.all():
            assert isinstance(tool.permission_level, PermissionLevel)

    async def test_high_impact_tool_without_ws_is_denied(self) -> None:
        gate = PermissionGate(ws_send=None)
        reg = build_default_registry()
        del_tool = reg.get("file_delete")
        assert del_tool.permission_level == PermissionLevel.HIGH_IMPACT_ACTION

        with pytest.raises(PermissionDeniedError, match="requires approval but no interactive client connected"):
            await gate.check(del_tool)

    async def test_high_impact_tool_interactive_approval(self) -> None:
        last_frame: dict[str, Any] = {}

        async def mock_ws(frame: dict[str, Any]) -> None:
            nonlocal last_frame
            last_frame = frame
            # Simulate async approval response
            req_id = UUID(frame["payload"]["request_id"])
            gate.receive_grant(PermissionGrant(request_id=req_id, granted=True))

        gate = PermissionGate(ws_send=mock_ws)
        reg = build_default_registry()
        del_tool = reg.get("file_delete")

        # Should prompt, get granted=True, and complete cleanly
        await gate.check(del_tool)
        assert last_frame.get("type") == "PERMISSION_REQUEST"
        assert last_frame["payload"]["tool_name"] == "file_delete"

    async def test_high_impact_tool_interactive_rejection(self) -> None:
        async def mock_ws(frame: dict[str, Any]) -> None:
            req_id = UUID(frame["payload"]["request_id"])
            gate.receive_grant(PermissionGrant(request_id=req_id, granted=False))

        gate = PermissionGate(ws_send=mock_ws)
        reg = build_default_registry()
        del_tool = reg.get("file_delete")

        with pytest.raises(PermissionDeniedError, match="User rejected permission request"):
            await gate.check(del_tool)

    async def test_session_grant_bypasses_future_checks(self) -> None:
        gate = PermissionGate(ws_send=None)
        reg = build_default_registry()
        del_tool = reg.get("file_delete")

        gate.grant_for_session(del_tool.name)
        # Should now pass without raising
        await gate.check(del_tool)


# ── 6. Audit Logging & Secret Masking ─────────────────────────────────────────


class TestAuditLoggingAndSanitization:

    def test_audit_logger_records_duration_and_status(self) -> None:
        logger = ToolAuditLogger()
        rec = logger.record(
            tool_id="file_read",
            action="execute",
            permission_level=PermissionLevel.READ,
            status=ToolStatus.SUCCESS,
            execution_duration_ms=45,
            metadata={"path": "/var/log/syslog"},
        )
        assert rec.tool_id == "file_read"
        assert rec.status == ToolStatus.SUCCESS
        assert rec.execution_duration_ms == 45
        assert len(logger.get_records()) == 1

    def test_audit_sanitizer_masks_passwords_and_tokens(self) -> None:
        payload = {
            "user": "alice",
            "password": "supersecretpassword123",
            "api_key": "sk-1234567890abcdef1234567890abcdef",
            "normal_data": "public info",
        }
        sanitized = sanitize_audit_payload(payload)
        assert "****** [REDACTED SECRET]" in sanitized["password"]
        assert "****** [REDACTED SECRET]" in sanitized["api_key"]


# ── 7. Projects Scan & Workspace Tooling ──────────────────────────────────────


class TestProjectsScanAndWorkspaceTool:

    def test_projects_scan_tool_registered(self) -> None:
        reg = build_default_registry()
        tool = reg.get("projects_scan")
        assert tool.tool_id == "projects_scan"
        assert tool.permission_level == PermissionLevel.READ

    @pytest.mark.asyncio
    async def test_projects_scan_executes_on_real_workspace(self) -> None:
        from tools.projects import ProjectsScanTool
        tool = ProjectsScanTool()
        result = await tool.execute({})
        assert result.success is True
        assert "unfinished_projects" in result.output
        assert "finished_projects" in result.output
        assert result.output["total_count"] > 0
        assert "summary" in result.output

    @pytest.mark.asyncio
    async def test_planner_routes_project_and_directory_queries(self) -> None:
        from core.planner import Planner
        from core.types import ActionType, ChatRequest

        planner = Planner()
        queries = [
            "check about my projects and tell me what are the projects i havenot finished",
            "check my dictoraries i created a folder for unfinished projects to store",
            "Unfinished",
            "what are my projects",
        ]
        for q in queries:
            plan = await planner.plan(ChatRequest(message=q))
            assert len(plan.steps) >= 2
            assert plan.steps[0].action_type == ActionType.TOOL_CALL
            assert plan.steps[0].required_tool == "projects_scan"
            assert plan.steps[1].action_type == ActionType.MODEL_GENERATE
            assert plan.steps[1].dependencies == [0]

    @pytest.mark.asyncio
    async def test_directory_ops_handles_dictoraries_and_projects(self) -> None:
        from tools.files import DirectoryOpsTool
        tool = DirectoryOpsTool()
        result = await tool.execute({"path": "dictoraries", "action": "list"})
        assert result.success is True
        assert result.output["count"] > 0
        assert "items" in result.output
        assert "summary" in result.output

    @pytest.mark.asyncio
    async def test_app_launcher_falls_back_to_browser_for_web_services(self) -> None:
        from tools.system import AppLauncherTool
        tool = AppLauncherTool()
        result = await tool.execute({"app_name": "youtube"})
        assert result.success is True
        assert result.output.get("launched") is True
        assert result.output.get("mode") == "browser"
        assert "youtube.com" in result.output.get("url", "")
