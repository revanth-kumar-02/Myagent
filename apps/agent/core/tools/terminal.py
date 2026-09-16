import os
import re
import shlex
import time
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolResult
from core.filesystem.permission_manager import permission_manager, PermissionLevel, PermissionScope, sanitize_resource_log
from core.filesystem.path_validator import PathValidator
from api.websocket import ws_manager

logger = logging.getLogger(__name__)

# Max output capture limit (50 KB) to prevent memory exhaustion
MAX_OUTPUT_BYTES = 50 * 1024

class CommandRiskLevel(str, Enum):
    SAFE = "SAFE"
    REVIEW = "REVIEW"
    DANGEROUS = "DANGEROUS"
    BLOCKED = "BLOCKED"

class TerminalInput(BaseModel):
    command: str = Field(description="Command executable or full shell command string")
    arguments: Optional[List[str]] = Field(default=None, description="Optional list of command arguments")
    working_directory: Optional[str] = Field(default=None, description="Working directory path relative to workspace or absolute")
    timeout_seconds: float = Field(default=30.0, description="Execution timeout in seconds")
    task_id: Optional[str] = Field(default=None, description="Associated task ID")
    project_id: Optional[str] = Field(default=None, description="Associated project ID")

class CommandSafetyValidator:
    """Classifies commands into SAFE, REVIEW, DANGEROUS, or BLOCKED risk categories."""
    
    BLOCKED_PATTERNS = [
        r"\brm\s+-rf\s+(/|~|\$HOME|\.\.)",              # Destructive root/home wipe
        r"\bdd\s+if=",                                   # Low-level disk overwrite
        r"\bmkfs\.",                                     # Filesystem format
        r"\bsetenforce\s+0",                             # Disabling SELinux
        r"\buw\s+disable|\biptables\s+-F",              # Disabling firewall
        r"\bcat\s+.*(/etc/shadow|/etc/passwd|\.env)",    # Credential extraction
        r"\b(env|printenv|export)\b(?!\s*=[^|\&\n]+)",   # Dumping environment secrets
        r"gsk_[a-zA-Z0-9_-]{20,}",                       # API Key leak in command
        r"sk-[a-zA-Z0-9_-]{20,}",                        # API Key leak in command
        r"\b(nc|netcat|ncat)\s+.*-e",                    # Reverse shell creation
        r"\bchmod\s+777\s+/",                            # Root permission corruption
    ]

    DANGEROUS_COMMANDS = {
        "rm", "chmod", "chown", "sudo", "systemctl", "kill", "pkill", "mv",
        "mkfifo", "useradd", "usermod", "reboot", "shutdown"
    }

    REVIEW_COMMANDS = {
        "npm", "pip", "pip3", "cargo", "git", "python", "python3", "node",
        "make", "gcc", "g++", "rustc", "go", "yarn", "pnpm", "docker"
    }

    SAFE_COMMANDS = {
        "pwd", "ls", "find", "echo", "whoami", "cat", "grep", "head", "tail",
        "wc", "pytest", "uname", "which", "date"
    }

    @classmethod
    def classify(cls, command_str: str, working_dir: str, validator: PathValidator) -> CommandRiskLevel:
        """Evaluates command string and working directory for risk classification."""
        if not command_str or not command_str.strip():
            return CommandRiskLevel.BLOCKED

        cmd_lower = command_str.strip().lower()

        # 1. Check for blocked patterns
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, cmd_lower, re.IGNORECASE):
                logger.warning(f"[SECURITY BLOCKED] Command matching blocked pattern '{pattern}': {command_str}")
                return CommandRiskLevel.BLOCKED

        # 2. Check for path traversal or escaping authorized workspace boundary
        norm_cwd = os.path.abspath(working_dir)
        if not validator.is_path_authorized(norm_cwd):
            logger.warning(f"[SECURITY BLOCKED] Working directory '{norm_cwd}' is outside workspace boundary.")
            return CommandRiskLevel.BLOCKED

        # Check any explicit file path arguments in command for boundary escape
        try:
            tokens = shlex.split(command_str)
        except Exception:
            tokens = command_str.split()

        if not tokens:
            return CommandRiskLevel.BLOCKED

        base_bin = os.path.basename(tokens[0]).lower()

        # Check path argument boundary escape (e.g., cat /etc/shadow, ls /root)
        for token in tokens[1:]:
            if token.startswith("/") or token.startswith(".."):
                resolved = os.path.abspath(os.path.join(norm_cwd, token))
                # Allow reading system binaries / pythons if harmless
                if not validator.is_path_authorized(resolved) and not resolved.startswith("/usr") and not resolved.startswith("/lib"):
                    if base_bin in ("cat", "rm", "cp", "mv", "chmod", "chown"):
                        logger.warning(f"[SECURITY BLOCKED] Command target path '{resolved}' outside workspace boundary.")
                        return CommandRiskLevel.BLOCKED

        # 3. Classify base binary
        if base_bin in cls.DANGEROUS_COMMANDS:
            return CommandRiskLevel.DANGEROUS

        if base_bin in cls.REVIEW_COMMANDS:
            # Special check for git subcommands
            if base_bin == "git" and len(tokens) > 1:
                git_sub = tokens[1].lower()
                if git_sub in ("status", "diff", "log", "branch", "show", "remote"):
                    return CommandRiskLevel.SAFE
                elif git_sub in ("checkout", "reset", "stash"):
                    return CommandRiskLevel.REVIEW
                elif git_sub in ("clean", "push", "rebase"):
                    return CommandRiskLevel.DANGEROUS

            # Special check for npm / pytest
            if base_bin == "npm" and len(tokens) > 1 and tokens[1].lower() in ("test", "run"):
                return CommandRiskLevel.SAFE
            return CommandRiskLevel.REVIEW

        if base_bin in cls.SAFE_COMMANDS:
            return CommandRiskLevel.SAFE

        # Unknown binary defaults to REVIEW
        return CommandRiskLevel.REVIEW


class ProcessExecutor:
    """Executes child processes with timeout, output truncation, secret sanitization, and cleanup."""

    @staticmethod
    def sanitize_output(raw_output: str) -> str:
        if not raw_output:
            return ""
        return sanitize_resource_log(raw_output)

    @staticmethod
    def truncate_output(output_bytes: bytes, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
        if len(output_bytes) <= max_bytes:
            return output_bytes.decode("utf-8", errors="replace")
        
        half = max_bytes // 2
        head = output_bytes[:half].decode("utf-8", errors="replace")
        tail = output_bytes[-half:].decode("utf-8", errors="replace")
        truncated_msg = f"\n\n[... Output Truncated ({len(output_bytes) - max_bytes} bytes omitted) ...]\n\n"
        return head + truncated_msg + tail

    @classmethod
    async def execute(
        cls,
        command_str: str,
        working_dir: str,
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        start_time = time.time()
        norm_cwd = os.path.abspath(working_dir)

        try:
            # Prefer argv token execution over shell if no pipe/redirection
            has_shell_operators = any(op in command_str for op in ["|", "&&", ";", "||", ">", "<"])
            
            if has_shell_operators:
                proc = await asyncio.create_subprocess_shell(
                    command_str,
                    cwd=norm_cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:
                try:
                    args = shlex.split(command_str)
                except Exception:
                    args = command_str.split()
                proc = await asyncio.create_subprocess_exec(
                    args[0],
                    *args[1:],
                    cwd=norm_cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds
            )
            duration = time.time() - start_time

            stdout_str = cls.sanitize_output(cls.truncate_output(stdout_bytes))
            stderr_str = cls.sanitize_output(cls.truncate_output(stderr_bytes))

            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "working_directory": norm_cwd,
                "duration_seconds": round(duration, 3),
                "command": command_str
            }

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.warning(f"[TERMINAL TIMEOUT] Command '{command_str}' timed out after {timeout_seconds}s. Killing process.")
            try:
                proc.kill()
                await proc.wait()
            except Exception as kill_err:
                logger.error(f"Error killing timed-out process: {kill_err}")

            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                "working_directory": norm_cwd,
                "duration_seconds": round(duration, 3),
                "command": command_str
            }

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[TERMINAL ERROR] Failed to execute process '{command_str}': {e}")
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Process execution error: {str(e)}",
                "working_directory": norm_cwd,
                "duration_seconds": round(duration, 3),
                "command": command_str
            }


class TerminalTool(BaseTool):
    """Controlled Terminal & Subprocess Execution Tool for Cocoa Agent."""
    name = "terminal"
    description = "Executes command line processes inside authorized workspace boundaries with strict permission checks, risk safety validation, and output sanitization."

    def __init__(self, validator: Optional[PathValidator] = None):
        default_roots = [os.getcwd(), "/home/rev/My Personal Space/Projects"]
        self.validator = validator or PathValidator(default_roots)

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        inp = TerminalInput(**params)
        
        # Build full command string
        full_cmd = inp.command
        if inp.arguments:
            full_cmd = f"{inp.command} " + " ".join(inp.arguments)

        # Working directory resolution
        working_dir = inp.working_directory or os.getcwd()
        norm_cwd = os.path.abspath(working_dir)

        # 1. Safety Classification
        risk_level = CommandSafetyValidator.classify(full_cmd, norm_cwd, self.validator)

        # Broadcast tool.requested
        await ws_manager.broadcast({
            "event": "tool.requested",
            "data": {
                "tool": self.name,
                "operation": full_cmd,
                "working_directory": norm_cwd,
                "risk_level": risk_level.value,
                "task_id": inp.task_id,
                "project_id": inp.project_id
            }
        })

        # 2. Blocked Command Rejection
        if risk_level == CommandRiskLevel.BLOCKED:
            await ws_manager.broadcast({
                "event": "tool.blocked",
                "data": {
                    "tool": self.name,
                    "operation": full_cmd,
                    "reason": "Command violates security boundary policies or blocked pattern rules",
                    "task_id": inp.task_id
                }
            })
            return ToolResult(
                success=False,
                data={"risk_level": risk_level.value, "exit_code": -1},
                error=f"SECURITY BLOCKED: Terminal command '{full_cmd}' is prohibited by security policy."
            )

        # 3. Permission Manager Check
        # Safe commands pass auto-approval; Review / Dangerous require explicit check
        is_granted = await permission_manager.check_permission(
            tool_name=self.name,
            path=norm_cwd,
            operation=full_cmd,
            permission_level=PermissionLevel.TERMINAL_EXECUTE,
            task_id=inp.task_id,
            project_id=inp.project_id,
            scope=PermissionScope.ONCE
        )

        if not is_granted:
            await ws_manager.broadcast({
                "event": "tool.blocked",
                "data": {
                    "tool": self.name,
                    "operation": full_cmd,
                    "reason": "Permission denied by user or policy",
                    "task_id": inp.task_id
                }
            })
            return ToolResult(
                success=False,
                data={"risk_level": risk_level.value, "permission_denied": True},
                error=f"PERMISSION DENIED: Execution of terminal command '{full_cmd}' was denied."
            )

        # 4. Broadcast tool.started
        await ws_manager.broadcast({
            "event": "tool.started",
            "data": {
                "tool": self.name,
                "operation": full_cmd,
                "working_directory": norm_cwd,
                "task_id": inp.task_id
            }
        })

        # 5. Process Execution
        result = await ProcessExecutor.execute(
            command_str=full_cmd,
            working_dir=norm_cwd,
            timeout_seconds=inp.timeout_seconds
        )
        result["risk_level"] = risk_level.value

        # 6. Telemetry Event Emission
        if result["success"]:
            await ws_manager.broadcast({
                "event": "tool.completed",
                "data": {
                    "tool": self.name,
                    "operation": full_cmd,
                    "duration": result["duration_seconds"],
                    "success": True,
                    "exit_code": result["exit_code"],
                    "task_id": inp.task_id
                }
            })
            return ToolResult(success=True, data=result, error="")
        else:
            await ws_manager.broadcast({
                "event": "tool.failed",
                "data": {
                    "tool": self.name,
                    "operation": full_cmd,
                    "duration": result["duration_seconds"],
                    "success": False,
                    "exit_code": result["exit_code"],
                    "error_category": "process_failure" if result["exit_code"] != -1 else "timeout",
                    "task_id": inp.task_id
                }
            })
            return ToolResult(
                success=False,
                data=result,
                error=f"Terminal process failed with exit code {result['exit_code']}: {result['stderr']}"
            )
