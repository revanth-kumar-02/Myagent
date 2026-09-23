"""
core.planner — Context-Aware Task Planner & Dynamic Replanner (V7)

Responsibilities:
  - Decompose user requests into structured, dependency-aware PlanStep items
  - Attach goals, required context, required tools, expected results, and verification methods to each step
  - Generate concise plans for simple requests (1 step) and ordered multi-step plans for complex tasks
  - Provide dynamic replanning upon execution failure or escalation
  - Stream PLAN_UPDATE frames over WebSocket
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import structlog

from core.intent_analyzer import IntentAnalyzer
from core.types import ActionType, ContextNeed, IntentType, Plan, PlanStep, SourceType, StepStatus

if TYPE_CHECKING:
    from core.types import ChatRequest, ContextWindow, ExecutionReport

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class Planner:
    """
    Translates user requests into structured execution plans and performs dynamic replanning.
    """

    def __init__(
        self,
        model_router: object | None = None,
        intent_analyzer: IntentAnalyzer | None = None,
        learning_manager: Any | None = None,
    ) -> None:
        self._model_router = model_router
        self._analyzer = intent_analyzer or IntentAnalyzer()
        self._learning_manager = learning_manager

    async def plan(
        self,
        request: "ChatRequest",
        context: "ContextWindow | None" = None,
    ) -> Plan:
        """
        Produce an ordered Plan with explicit goals, dependencies, and verification criteria.
        """
        # 0. Check Adaptive Learnings for prior workflow advice or constraints
        relevant_learnings: list[Any] = []
        if self._learning_manager is not None:
            try:
                relevant_learnings = await self._learning_manager.get_relevant_learnings(
                    request.message,
                    project_id=request.project_id,
                )
            except Exception as exc:
                logger.debug("planner_learning_retrieval_skipped", error=str(exc))


        intent, context_need = self._analyzer.analyze(
            message=request.message,
            project_id=request.project_id,
            has_active_project=request.project_id is not None,
        )

        steps: list[PlanStep] = []
        step_idx = 0

        # 1. Handle Tool / Multi-Step Actions
        if intent == IntentType.TOOL_ACTION:
            tool_step = self._plan_tool_action(step_idx, request.message)
            steps.append(tool_step)
            step_idx += 1
            # Follow-up with model generation / summary
            steps.append(
                PlanStep(
                    index=step_idx,
                    label="Summarize action results",
                    action_type=ActionType.MODEL_GENERATE,
                    goal="Report tool execution results to user",
                    dependencies=[step_idx - 1],
                    expected_result="Clear confirmation and output report",
                    verification_method="non_empty_check",
                    params={"prompt": request.message},
                )
            )
            return Plan(steps=steps, trace_id=request.trace_id)

        # 2. Context Retrieval Steps (RAG, Memory, Web)
        context_dep_indices: list[int] = []
        raw_msg = request.message.strip()

        # Clean query if slash prefix is used
        query_text = raw_msg
        if re.match(r"^/(?:search|web|research|rag|memory)\s+", raw_msg, re.IGNORECASE):
            parts = raw_msg.split(maxsplit=1)
            if len(parts) > 1:
                query_text = parts[1].strip()

        if context_need in (ContextNeed.RAG, ContextNeed.RAG_AND_MEMORY, ContextNeed.RAG_AND_WEB, ContextNeed.ALL):
            steps.append(
                PlanStep(
                    index=step_idx,
                    label="Retrieve project knowledge",
                    action_type=ActionType.RAG_QUERY,
                    goal="Fetch relevant code and document chunks from RAG",
                    required_context=[SourceType.RAG],
                    expected_result="Non-empty relevant chunks matching query",
                    verification_method="rag_score_check",
                    params={"query": query_text, "project_id": str(request.project_id) if request.project_id else None},
                )
            )
            context_dep_indices.append(step_idx)
            step_idx += 1

        if context_need in (ContextNeed.MEMORY, ContextNeed.RAG_AND_MEMORY, ContextNeed.MEMORY_AND_WEB, ContextNeed.ALL):
            steps.append(
                PlanStep(
                    index=step_idx,
                    label="Retrieve persistent memory",
                    action_type=ActionType.MEMORY_QUERY,
                    goal="Retrieve user preferences, profile, or past decisions",
                    required_context=[SourceType.MEMORY],
                    expected_result="Matching active memory records",
                    verification_method="memory_check",
                    params={"query": query_text, "project_id": str(request.project_id) if request.project_id else None},
                )
            )
            context_dep_indices.append(step_idx)
            step_idx += 1

        if context_need in (ContextNeed.WEB, ContextNeed.RAG_AND_WEB, ContextNeed.MEMORY_AND_WEB, ContextNeed.ALL):
            steps.append(
                PlanStep(
                    index=step_idx,
                    label="Search external web sources",
                    action_type=ActionType.WEB_RESEARCH,
                    goal="Query DuckDuckGo for live external evidence",
                    required_context=[SourceType.WEB],
                    expected_result="Normalized web search results and snippets",
                    verification_method="web_results_check",
                    params={"query": query_text},
                )
            )
            context_dep_indices.append(step_idx)
            step_idx += 1

        # 3. Model Generation Step (Reasoning / Response)
        steps.append(
            PlanStep(
                index=step_idx,
                label="Generate grounded response",
                action_type=ActionType.MODEL_GENERATE,
                goal="Synthesize retrieved context and answer user request accurately",
                dependencies=context_dep_indices,
                expected_result="Cohesive, factually grounded final response",
                verification_method="grounding_check",
                params={"prompt": query_text},
            )
        )

        return Plan(steps=steps, trace_id=request.trace_id)

    async def replan(
        self,
        failed_step: PlanStep,
        report: "ExecutionReport",
        original_plan: Plan,
    ) -> Plan:
        """
        Dynamically adjust plan when a step fails verification or execution.
        """
        logger.info(
            "replanning_triggered",
            failed_step=failed_step.label,
            verdict=report.verdict.value,
            error=report.error_message,
        )

        new_steps: list[PlanStep] = []
        new_idx = 0

        # Preserve already completed steps
        for step in original_plan.steps:
            if step.status == StepStatus.DONE:
                new_steps.append(step)
                new_idx += 1

        # Insert corrective / fallback step
        if failed_step.action_type == ActionType.RAG_QUERY:
            # Fallback to broader query or web search if RAG returned empty
            corrective_step = PlanStep(
                index=new_idx,
                label="Broader knowledge search (Replan)",
                action_type=ActionType.WEB_RESEARCH,
                goal="Search web for query terms since local RAG was insufficient",
                params={"query": failed_step.params.get("query", "")},
                expected_result="External web evidence",
                verification_method="web_results_check",
            )
            new_steps.append(corrective_step)
            new_idx += 1

        elif failed_step.action_type == ActionType.TOOL_CALL:
            # Retry tool with relaxed or alternate parameters
            corrective_step = PlanStep(
                index=new_idx,
                label=f"Retry {failed_step.label} with sanitized parameters",
                action_type=ActionType.TOOL_CALL,
                goal=f"Recover from failure: {report.error_message or 'Unknown error'}",
                required_tool=failed_step.required_tool,
                params=dict(failed_step.params),
                expected_result="Successful tool execution",
                verification_method="tool_output_check",
            )
            new_steps.append(corrective_step)
            new_idx += 1

        # Final generation step
        new_steps.append(
            PlanStep(
                index=new_idx,
                label="Generate response explaining replan / result",
                action_type=ActionType.MODEL_GENERATE,
                goal="Synthesize results including recovery explanation",
                dependencies=[new_idx - 1] if new_idx > 0 else [],
                expected_result="Clear user-facing explanation",
                verification_method="non_empty_check",
                params={"prompt": "Explain the outcome of the replanned execution"},
            )
        )

        return Plan(
            steps=new_steps,
            trace_id=original_plan.trace_id,
            is_replan=True,
            replan_reason=f"Step '{failed_step.label}' failed: {report.error_message}",
        )

    async def update_step_status(
        self,
        plan: Plan,
        step_index: int,
        status: StepStatus,
        ws_send: WSSend | None = None,
    ) -> None:
        """Update step status and optionally push WebSocket notification."""
        if 0 <= step_index < len(plan.steps):
            plan.steps[step_index].status = status
            if ws_send is not None:
                await ws_send({
                    "type": "PLAN_UPDATE",
                    "payload": {
                        "trace_id": str(plan.trace_id),
                        "step_index": step_index,
                        "status": status.value,
                        "label": plan.steps[step_index].label,
                    },
                })

    def _plan_tool_action(self, index: int, message: str) -> PlanStep:
        """Heuristically configure a PlanStep for detected tool actions."""
        msg_clean = message.strip()
        if msg_clean.startswith("/"):
            parts = msg_clean[1:].split(maxsplit=1)
            tool_name = parts[0].lower().replace("-", "_")
            args_str = parts[1].strip() if len(parts) > 1 else ""

            params: dict[str, Any] = {}
            if tool_name in ("system_info", "sysinfo"):
                tool_name = "system_info"
                params = {}
            elif tool_name == "clipboard":
                if args_str:
                    params = {"action": "write", "text": args_str}
                else:
                    params = {"action": "read"}
            elif tool_name in ("app_launcher", "launch"):
                tool_name = "app_launcher"
                app_parts = args_str.split()
                params = {
                    "app_name": app_parts[0] if app_parts else "bash",
                    "args": app_parts[1:] if len(app_parts) > 1 else [],
                }
            elif tool_name in ("page_navigation", "browser", "browser_control"):
                tool_name = "page_navigation" if tool_name == "page_navigation" else "browser_control"
                params = {"url": args_str or "https://google.com"}
            elif tool_name in ("download_manager", "download"):
                tool_name = "download_manager"
                subparts = args_str.split(maxsplit=1)
                if len(subparts) == 2:
                    params = {"url": subparts[0], "destination_path": subparts[1]}
                elif len(subparts) == 1 and subparts[0]:
                    params = {"url": subparts[0], "destination_path": "downloaded_file"}
                else:
                    params = {"url": "https://example.com", "destination_path": "downloaded_file"}
            elif tool_name in ("notification", "notify"):
                tool_name = "notification"
                params = {"title": "Kora Notification", "message": args_str or "Action completed"}
            elif tool_name in ("shell_command", "shell", "bash"):
                tool_name = "shell_command"
                params = {"command": args_str or "echo 'Kora Shell'"}
            elif tool_name in ("read_file", "write_file", "list_files", "delete_file"):
                params = {"path": args_str, "content": args_str}
            else:
                params = {"query": args_str, "command": args_str, "text": args_str}

            return PlanStep(
                index=index,
                label=f"Execute tool: {tool_name}",
                action_type=ActionType.TOOL_CALL,
                required_tool=tool_name,
                goal=f"Execute {tool_name} with parameters: {args_str}",
                expected_result="Successful tool execution output",
                verification_method="tool_output_check",
                params=params,
            )

        # Natural language mapping
        msg_lower = msg_clean.lower()
        if re.search(r"\b(?:system\s+(?:info|information)|show\s+(?:my\s+)?system|check\s+(?:my\s+)?system|what\s+is\s+my\s+os|what\s+os|system\s+hardware|cpu\s+info|os\s+version|hardware\s+info)\b", msg_lower):
            return PlanStep(
                index=index,
                label="Execute tool: system_info",
                action_type=ActionType.TOOL_CALL,
                required_tool="system_info",
                goal="Query hardware and OS details from local machine",
                expected_result="Accurate OS and hardware summary",
                verification_method="tool_output_check",
                params={},
            )

        if re.search(r"\b(?:read\s+clipboard|check\s+clipboard|what(?:'s|\s+is)\s+(?:in\s+)?(?:my\s+)?clipboard)\b", msg_lower):
            return PlanStep(
                index=index,
                label="Execute tool: clipboard",
                action_type=ActionType.TOOL_CALL,
                required_tool="clipboard",
                goal="Read current clipboard content",
                expected_result="Clipboard text",
                verification_method="tool_output_check",
                params={"action": "read"},
            )

        if re.search(r"\b(?:open\s+(?:vs\s*code|vscode|code)|launch\s+(?:vs\s*code|vscode|code))\b", msg_lower):
            return PlanStep(
                index=index,
                label="Execute tool: app_launcher",
                action_type=ActionType.TOOL_CALL,
                required_tool="app_launcher",
                goal="Launch VS Code application",
                expected_result="Process launch confirmation",
                verification_method="tool_output_check",
                params={"app_name": "code", "args": []},
            )

        if re.search(r"\b(?:open\s+terminal|launch\s+terminal)\b", msg_lower):
            return PlanStep(
                index=index,
                label="Execute tool: app_launcher",
                action_type=ActionType.TOOL_CALL,
                required_tool="app_launcher",
                goal="Launch terminal application",
                expected_result="Process launch confirmation",
                verification_method="tool_output_check",
                params={"app_name": "bash", "args": []},
            )

        if re.search(r"\b(?:what\s+processes\s+are\s+running|list\s+processes|running\s+processes|check\s+processes)\b", msg_lower):
            return PlanStep(
                index=index,
                label="Execute tool: system_info",
                action_type=ActionType.TOOL_CALL,
                required_tool="system_info",
                goal="List running system processes",
                expected_result="Active process listing",
                verification_method="tool_output_check",
                params={},
            )

        if re.search(r"\b(?:find\s+(?:this\s+)?file|search\s+for\s+file|list\s+files\s+in|show\s+files\s+in)\b", msg_lower):
            return PlanStep(
                index=index,
                label="Execute tool: directory_ops",
                action_type=ActionType.TOOL_CALL,
                required_tool="directory_ops",
                goal="List workspace directory contents",
                expected_result="Directory contents listing",
                verification_method="tool_output_check",
                params={"path": ".", "operation": "list"},
            )

        if "pytest" in message.lower() or "test" in message.lower():
            return PlanStep(
                index=index,
                label="Execute automated tests",
                action_type=ActionType.TOOL_CALL,
                required_tool="terminal_exec",
                goal="Run test command in workspace",
                expected_result="Test execution exit code 0",
                verification_method="exit_code_zero",
                params={"command": "pytest"},
            )

        return PlanStep(
            index=index,
            label="Execute tool action",
            action_type=ActionType.TOOL_CALL,
            required_tool="system_info",
            goal="Perform requested system action",
            expected_result="Successful tool output",
            verification_method="tool_output_check",
            params={},
        )
