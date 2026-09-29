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
        request: "ChatRequest | str | None" = None,
        context: "ContextWindow | str | None" = None,
        goal: str | None = None,
        available_tools: list[str] | None = None,
    ) -> Plan:
        """
        Produce an ordered Plan with explicit goals, dependencies, and verification criteria.
        """
        if request is None and goal is not None:
            request = goal
        if isinstance(request, str):
            from core.types import ChatRequest
            request = ChatRequest(message=request)
        elif request is None:
            from core.types import ChatRequest
            request = ChatRequest(message="")

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
            elif tool_name in ("projects", "projects_scan", "scan_projects", "list_projects"):
                tool_name = "projects_scan"
                params = {"category": args_str if args_str in ("unfinished", "finished") else "all"}
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

        # 1. System Info & Diagnostics
        if re.search(r"\b(?:system\s+(?:info|information)|show\s+(?:my\s+)?system|check\s+(?:my\s+)?system|what\s+is\s+my\s+os|what\s+os|system\s+hardware|cpu|ram|memory\s+usage|hardware\s+info|disk\s+space|hostname|specs?|specifications?)\b", msg_lower):
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

        # 2. Screen Capture / Screenshot
        if re.search(r"\b(?:screenshot|screen\s*capture|capture\s+(?:the\s+)?screen|take\s+(?:a\s+)?screenshot)\b", msg_lower):
            return PlanStep(
                index=index,
                label="Execute tool: screen_capture",
                action_type=ActionType.TOOL_CALL,
                required_tool="screen_capture",
                goal="Capture desktop screenshot",
                expected_result="Screenshot image file path",
                verification_method="tool_output_check",
                params={},
            )

        # 3. Clipboard
        if re.search(r"\b(?:read\s+clipboard|check\s+clipboard|show\s+clipboard|what(?:'s|\s+is)\s+(?:in\s+)?(?:my\s+)?clipboard|clipboard)\b", msg_lower):
            if re.search(r"\b(?:copy|write|set|save\s+to)\b", msg_lower):
                clip_text = re.sub(r"^.*?(?:copy|write|set|save\s+to\s+clipboard)\s+", "", msg_clean, flags=re.IGNORECASE)
                params = {"action": "write", "text": clip_text}
            else:
                params = {"action": "read"}
            return PlanStep(
                index=index,
                label="Execute tool: clipboard",
                action_type=ActionType.TOOL_CALL,
                required_tool="clipboard",
                goal="Access system clipboard",
                expected_result="Clipboard content",
                verification_method="tool_output_check",
                params=params,
            )

        # 4. App Launcher
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

        # General App or Web Service launcher (e.g. open youtube, launch chrome, open spotify, open github)
        open_app_match = re.search(r"\b(?:open|launch)\s+(?:the\s+)?([a-z0-9_\-\.]+)(?:\s+(?:app|application|in\s+browser))?\b", msg_lower)
        if open_app_match:
            target_app = open_app_match.group(1).strip()
            if target_app not in (
                "a", "an", "the", "my", "this", "file", "files", "directory", "directories",
                "dictoraries", "dictaries", "folder", "folders", "project", "projects",
                "browser", "terminal", "code", "system", "clipboard", "processes",
            ):
                return PlanStep(
                    index=index,
                    label=f"Execute tool: app_launcher ({target_app})",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="app_launcher",
                    goal=f"Launch application or web service '{target_app}'",
                    expected_result="Application or web browser launch confirmation",
                    verification_method="tool_output_check",
                    params={"app_name": target_app, "args": []},
                )

        if re.search(r"\b(?:what\s+processes\s+are\s+running|list\s+processes|running\s+processes|check\s+processes|task\s+manager)\b", msg_lower):
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

        # 5. Projects & Workspace Inspection (including unfinished projects, dictoraries/directories)
        if re.search(r"\b(?:projects?\s+(?:i\s+)?(?:have\s+not|havenot|haven't|not|did\s+not|didn't)\s+finish(?:ed)?|unfinished\s+projects?|folder\s+for\s+(?:unfinished\s+)?projects?|^unfinished$)\b", msg_lower):
            return PlanStep(
                index=index,
                label="Execute tool: projects_scan",
                action_type=ActionType.TOOL_CALL,
                required_tool="projects_scan",
                goal="Scan and inspect unfinished project directories and git repositories",
                expected_result="List of unfinished project directories and details",
                verification_method="tool_output_check",
                params={"category": "unfinished"},
            )

        if (re.search(r"\b(?:projects?|project\s+folders?|dictoraries|dictaries|directories|my\s+folders?)\b", msg_lower)
                and re.search(r"\b(?:check|list|show|find|scan|what\s+are|tell\s+me|access)\b", msg_lower)):
            category = "unfinished" if "unfinished" in msg_lower else ("finished" if "finished" in msg_lower else "all")
            return PlanStep(
                index=index,
                label="Execute tool: projects_scan",
                action_type=ActionType.TOOL_CALL,
                required_tool="projects_scan",
                goal="Scan and inspect project directories in workspace",
                expected_result="Project directory scan results",
                verification_method="tool_output_check",
                params={"category": category},
            )

        # 6. Local Files & Directory Ops
        if re.search(r"\b(?:find\s+(?:this\s+)?file|search\s+for\s+file|list\s+(?:my\s+)?files|show\s+(?:my\s+)?files|files\s+in\s+workspace|list\s+directory|directory\s+contents)\b", msg_lower):
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

        # 6. Google Gmail (Search, Read, Draft, Send)
        if re.search(r"\b(?:emails?|gmail|inbox)\b", msg_lower):
            if re.search(r"\b(?:draft|compose)\b", msg_lower):
                body_text = re.sub(r"^.*?(?:draft|compose)\s+(?:an?\s+)?email\s*(?:about|saying|that)?\s*", "", msg_clean, flags=re.IGNORECASE) or msg_clean
                return PlanStep(
                    index=index,
                    label="Execute tool: google_gmail_draft",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_gmail_draft",
                    goal="Draft email in Gmail",
                    expected_result="Draft creation confirmation",
                    verification_method="tool_output_check",
                    params={"to": "", "subject": "Draft", "body": body_text},
                )
            if re.search(r"\b(?:send\s+(?:an?\s+)?email)\b", msg_lower):
                return PlanStep(
                    index=index,
                    label="Execute tool: google_gmail_send",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_gmail_send",
                    goal="Send email via Gmail",
                    expected_result="Sent confirmation",
                    verification_method="tool_output_check",
                    params={"to": "", "subject": "", "body": msg_clean},
                )
            # Search / List emails
            q = ""
            if "unread" in msg_lower:
                q = "is:unread"
            elif re.search(r"\b(?:from|about|containing|for)\s+", msg_lower):
                q = re.sub(r"^.*?(?:from|about|containing|for)\s+", "", msg_clean, flags=re.IGNORECASE).strip()

            return PlanStep(
                index=index,
                label="Execute tool: google_gmail_search",
                action_type=ActionType.TOOL_CALL,
                required_tool="google_gmail_search",
                goal="Search and list emails in Gmail",
                expected_result="List of matching emails",
                verification_method="tool_output_check",
                params={"query": q, "max_results": 10},
            )

        # 7. Google Calendar (List, Create, Update, Delete)
        if re.search(r"\b(?:calendar|events?|meetings?|appointments?|schedule)\b", msg_lower):
            if re.search(r"\b(?:create|schedule|set\s+up|add)\b", msg_lower):
                meeting_summary = re.sub(r"^.*?(?:create|schedule|set\s+up|add)\s+(?:a\s+|an\s+)?(?:meeting|event|appointment)\s*(?:called|named|for|about)?\s*", "", msg_clean, flags=re.IGNORECASE).strip() or "New Meeting"
                return PlanStep(
                    index=index,
                    label="Execute tool: google_calendar_create_event",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_calendar_create_event",
                    goal="Create Google Calendar event",
                    expected_result="Calendar event creation confirmation",
                    verification_method="tool_output_check",
                    params={"summary": meeting_summary, "start_time": ""},
                )
            if re.search(r"\b(?:delete|cancel|remove)\b", msg_lower):
                return PlanStep(
                    index=index,
                    label="Execute tool: google_calendar_delete_event",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_calendar_delete_event",
                    goal="Delete Google Calendar event",
                    expected_result="Calendar event deletion confirmation",
                    verification_method="tool_output_check",
                    params={"calendar_id": "primary", "event_id": ""},
                )
            # Default to listing calendar events
            return PlanStep(
                index=index,
                label="Execute tool: google_calendar_list_events",
                action_type=ActionType.TOOL_CALL,
                required_tool="google_calendar_list_events",
                goal="Query upcoming schedule from Google Calendar",
                expected_result="List of calendar events",
                verification_method="tool_output_check",
                params={"calendar_id": "primary", "max_results": 15},
            )

        # 8. Google Tasks (Create, List, Complete)
        if re.search(r"\b(?:tasks?|to-?do)\b", msg_lower):
            if re.search(r"\b(?:create|add|new)\b", msg_lower):
                task_title = re.sub(r"^.*?(?:create|add|new)\s+(?:a\s+|an\s+)?(?:task|to-?do)\s*(?:called|named|to)?\s*", "", msg_clean, flags=re.IGNORECASE)
                task_title = re.sub(r"\s+to\s+(?:my\s+)?tasks.*$", "", task_title, flags=re.IGNORECASE).strip().strip("\"'") or "New Task"
                return PlanStep(
                    index=index,
                    label="Execute tool: google_tasks_create",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_tasks_create",
                    goal=f"Create Google task: {task_title}",
                    expected_result="Task creation confirmation",
                    verification_method="tool_output_check",
                    params={"title": task_title},
                )
            if re.search(r"\b(?:complete|mark|finish|done)\b", msg_lower):
                return PlanStep(
                    index=index,
                    label="Execute tool: google_tasks_complete",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_tasks_complete",
                    goal="Complete Google task",
                    expected_result="Task completion confirmation",
                    verification_method="tool_output_check",
                    params={"task_id": ""},
                )
            return PlanStep(
                index=index,
                label="Execute tool: google_tasks_list",
                action_type=ActionType.TOOL_CALL,
                required_tool="google_tasks_list",
                goal="List Google tasks",
                expected_result="Active tasks listing",
                verification_method="tool_output_check",
                params={"show_completed": False},
            )

        # 9. Google Drive (Search, Read, Create Folder)
        if re.search(r"\b(?:drive|google\s+drive)\b", msg_lower):
            if re.search(r"\b(?:create\s+a?\s*folder|new\s+folder)\b", msg_lower):
                folder_name = re.sub(r"^.*?(?:create|new)\s+(?:a\s+)?folder\s*(?:called|named)?\s*", "", msg_clean, flags=re.IGNORECASE).strip().strip("\"'") or "New Folder"
                return PlanStep(
                    index=index,
                    label="Execute tool: google_drive_create_folder",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_drive_create_folder",
                    goal=f"Create Drive folder: {folder_name}",
                    expected_result="Folder creation confirmation",
                    verification_method="tool_output_check",
                    params={"name": folder_name},
                )
            q_name = re.sub(r"^.*?(?:find|search(?:\s+drive)?\s+for|files?\s+in|for)\s+", "", msg_clean, flags=re.IGNORECASE)
            q_name = re.sub(r"\s+(?:in\s+drive|google\s+drive|drive).*$", "", q_name, flags=re.IGNORECASE).strip()
            return PlanStep(
                index=index,
                label="Execute tool: google_drive_search",
                action_type=ActionType.TOOL_CALL,
                required_tool="google_drive_search",
                goal="Search files in Google Drive",
                expected_result="Matching drive files",
                verification_method="tool_output_check",
                params={"name_contains": q_name},
            )

        # 10. Google Docs
        if re.search(r"\b(?:google\s+doc(?:s|ument)?|documents?)\b", msg_lower):
            if re.search(r"\b(?:create|new|write)\b", msg_lower):
                doc_name = re.sub(r"^.*?(?:create|new|write)\s+(?:a\s+)?(?:google\s+)?doc(?:s|ument)?\s*(?:called|named)?\s*", "", msg_clean, flags=re.IGNORECASE).strip().strip("\"'") or "New Document"
                return PlanStep(
                    index=index,
                    label="Execute tool: google_docs_create",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_docs_create",
                    goal=f"Create Google Doc: {doc_name}",
                    expected_result="Document creation confirmation",
                    verification_method="tool_output_check",
                    params={"title": doc_name},
                )
            return PlanStep(
                index=index,
                label="Execute tool: google_docs_read",
                action_type=ActionType.TOOL_CALL,
                required_tool="google_docs_read",
                goal="Read Google Doc text",
                expected_result="Document text",
                verification_method="tool_output_check",
                params={"document_id": ""},
            )

        # 11. Google Sheets
        if re.search(r"\b(?:spreadsheet|google\s+sheets?|sheets?|read\s+rows?|cells?)\b", msg_lower):
            if re.search(r"\b(?:append|add\s+row)\b", msg_lower):
                return PlanStep(
                    index=index,
                    label="Execute tool: google_sheets_append",
                    action_type=ActionType.TOOL_CALL,
                    required_tool="google_sheets_append",
                    goal="Append row to Google Sheet",
                    expected_result="Row append confirmation",
                    verification_method="tool_output_check",
                    params={"spreadsheet_id": "", "values": []},
                )
            range_match = re.search(r"\b[A-Za-z0-9]+![A-Za-z0-9:]+|\b[A-Za-z]+[0-9]+:[A-Za-z]+[0-9]+", msg_clean)
            range_val = range_match.group(0) if range_match else "A1:Z50"
            return PlanStep(
                index=index,
                label="Execute tool: google_sheets_read",
                action_type=ActionType.TOOL_CALL,
                required_tool="google_sheets_read",
                goal=f"Read spreadsheet range {range_val}",
                expected_result="Cell range data",
                verification_method="tool_output_check",
                params={"spreadsheet_id": "", "range_notation": range_val},
            )

        # 12. Automated Testing / Dev
        if "pytest" in msg_lower or "run test" in msg_lower:
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

        # Default fallback
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
