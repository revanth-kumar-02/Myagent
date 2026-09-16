import re
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from core.llm import LLMProviderGateway, BaseLLMProvider, ModelRole
from core.memory import memory_manager
from core.plan_validator import plan_validator, ValidationResult
from core.recovery import FailureCategory, RecoveryStrategy, ReplanDecision, FailureClassifier

logger = logging.getLogger(__name__)

class PlanStepSchema(BaseModel):
    id: str = Field(description="Unique step ID, e.g. step_1")
    title: str = Field(default="", description="Short human readable action step title")
    description: str = Field(default="", description="Detailed step execution instructions")
    tool: Optional[str] = Field(default="web_search", description="Tool name: web_search | list_directory | search_files | read_file | inspect_file | create_file | edit_file | move_file | delete_file | browser_open | browser_navigate | browser_extract | browser_click | browser_type | browser_scroll | browser_screenshot | browser_download | browser_close | browser | scheduler | terminal | git_status | git_diff | git_log | git_branch | git_show | git_remote")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Structured parameters dictionary for tool call")
    dependencies: List[str] = Field(default_factory=list, description="List of step IDs that must complete before this step can execute")
    expected_outcome: Optional[str] = Field(default=None, description="Expected outcome criteria for step verification")
    risk_level: str = Field(default="SAFE", description="Risk level: SAFE | REVIEW | DANGEROUS | BLOCKED")
    permission_level: str = Field(default="READ", description="Permission level: READ | WRITE | TERMINAL_EXECUTE | GIT_READ | GIT_WRITE | BROWSER_READ | BROWSER_INTERACT")
    timeout: float = Field(default=60.0, description="Step execution timeout in seconds")
    retry_policy: Dict[str, Any] = Field(default_factory=lambda: {"max_retries": 2}, description="Retry bounds configuration")
    status: str = Field(default="pending", description="Initial step status: pending")

class TaskPlan(BaseModel):
    goal: str = Field(description="Original user goal statement")
    steps: List[PlanStepSchema] = Field(description="List of executable steps with dependency graph annotations")

class AgentPlanner:
    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or LLMProviderGateway.get_provider(role=ModelRole.REASONING)

    async def generate_plan(
        self,
        goal: str,
        project_id: Optional[str] = None,
        context: Optional[Any] = None
    ) -> TaskPlan:
        # 1. Retrieve bounded project knowledge and relevant memories
        bounded_ctx = {}
        try:
            bounded_ctx = await memory_manager.build_bounded_context(project_id=project_id, task_description=goal)
        except Exception as e:
            logger.debug(f"Context builder note: {e}")

        memory_context_lines = []
        if bounded_ctx.get("technologies"):
            memory_context_lines.append(f"- Technologies: {', '.join(bounded_ctx['technologies'])}")
        if bounded_ctx.get("git_branch"):
            memory_context_lines.append(f"- Git Branch: {bounded_ctx['git_branch']}")
        if bounded_ctx.get("relevant_memories"):
            for m_text in bounded_ctx["relevant_memories"]:
                memory_context_lines.append(f"- Retained Knowledge: {m_text}")

        memory_context = ""
        if memory_context_lines:
            memory_context = "\n\nProject Knowledge Context:\n" + "\n".join(memory_context_lines)

        # 2. Extract unified or RAG context
        retrieved_context_text = ""
        if context is not None:
            if hasattr(context, "formatted_prompt_context") and context.formatted_prompt_context:
                retrieved_context_text = "\n\n" + context.formatted_prompt_context
            elif isinstance(context, str) and context.strip():
                retrieved_context_text = "\n\n" + context.strip()
        elif project_id:
            try:
                from core.rag.context_builder import project_context_builder
                rag_res = await project_context_builder.build_project_context(project_id=project_id, query=goal, max_chars=4000)
                if rag_res.formatted_context:
                    retrieved_context_text = "\n\nRelevant Project Code Chunks (RAG):\n" + rag_res.formatted_context
            except Exception as rag_err:
                logger.debug(f"RAG context note: {rag_err}")

        system_prompt = (
            "You are an autonomous AI Agent Planner for Cocoa Agent. "
            "Decompose high-level user goals into a structured, dependency-annotated execution plan. "
            "Assign valid tools from [web_search, list_directory, search_files, read_file, inspect_file, create_file, edit_file, move_file, delete_file, browser_open, browser_navigate, browser_extract, browser_click, browser_type, browser_scroll, browser_screenshot, browser_download, browser_close, browser, scheduler, terminal, git_status, git_diff, git_log, git_branch, git_show, git_remote]. "
            "For independent tasks (e.g., git status + directory scan), specify dependencies = []. "
            "For sequential tasks (e.g., run tests -> read failure -> edit file -> rerun tests), specify dependencies = ['step_1']."
            f"{memory_context}"
            f"{retrieved_context_text}"
        )
        user_prompt = f"Goal to accomplish: '{goal}'"
        
        try:
            plan = await self.llm.generate_structured(user_prompt, TaskPlan, system_prompt)
            # Validate generated plan
            val = plan_validator.validate_plan(plan, project_id=project_id)
            if not val.valid:
                logger.warning(f"LLM plan failed validation ({val.errors}). Falling back to deterministic planner.")
                return self._build_fallback_plan(goal, context=context)
            return plan
        except Exception as e:
            logger.info(f"Using deterministic fallback plan for goal '{goal}': {e}")
            return self._build_fallback_plan(goal, context=context)

    def _build_fallback_plan(self, goal: str, context: Optional[Any] = None) -> TaskPlan:
        lower_goal = goal.lower()

        # Check if context has web research or goal is research/search oriented
        has_web_context = False
        if context is not None and hasattr(context, "web_items") and context.web_items:
            has_web_context = True

        if has_web_context or any(k in lower_goal for k in ["search", "research", "latest", "recent", "who is", "what is the current", "news"]):
            return TaskPlan(
                goal=goal,
                steps=[
                    PlanStepSchema(
                        id="step_1",
                        title=f"Conduct web research on: '{goal}'",
                        description=f"Query search provider and extract relevant web sources",
                        tool="web_search",
                        arguments={"query": goal},
                        dependencies=[],
                        permission_level="READ",
                        risk_level="SAFE"
                    ),
                    PlanStepSchema(
                        id="step_2",
                        title="Synthesize research findings and prepare response",
                        description="Analyze gathered information and summarize resolution",
                        tool="inspect_file",
                        dependencies=["step_1"],
                        permission_level="READ",
                        risk_level="SAFE"
                    )
                ]
            )

        # Check if goal is test failure / debugging related
        if "test" in lower_goal or "fail" in lower_goal or "debug" in lower_goal or "analyze" in lower_goal or "fix" in lower_goal:
            return TaskPlan(
                goal=goal,
                steps=[
                    PlanStepSchema(
                        id="step_1",
                        title="Inspect repository Git status",
                        description="Inspect working directory status and branch state",
                        tool="git_status",
                        dependencies=[],
                        permission_level="GIT_READ",
                        risk_level="SAFE"
                    ),
                    PlanStepSchema(
                        id="step_2",
                        title="Inspect project structure",
                        description="Scan project directory layout",
                        tool="list_directory",
                        dependencies=[],
                        permission_level="READ",
                        risk_level="SAFE"
                    ),
                    PlanStepSchema(
                        id="step_3",
                        title="Run automated test suite",
                        description="Execute test suite in workspace via terminal",
                        tool="terminal",
                        dependencies=[],
                        permission_level="TERMINAL_EXECUTE",
                        risk_level="SAFE"
                    ),
                    PlanStepSchema(
                        id="step_4",
                        title="Inspect failing source and test files",
                        description="Read source file contents for context",
                        tool="read_file",
                        dependencies=["step_3"],
                        permission_level="READ",
                        risk_level="SAFE"
                    ),
                    PlanStepSchema(
                        id="step_5",
                        title="Diagnose and apply code fix",
                        description="Modify project files to resolve failing test",
                        tool="edit_file",
                        dependencies=["step_4"],
                        permission_level="WRITE",
                        risk_level="REVIEW"
                    ),
                    PlanStepSchema(
                        id="step_6",
                        title="Re-run automated test suite",
                        description="Verify test suite passes after code fix",
                        tool="terminal",
                        dependencies=["step_5"],
                        permission_level="TERMINAL_EXECUTE",
                        risk_level="SAFE"
                    ),
                    PlanStepSchema(
                        id="step_7",
                        title="Verify outcome and summarize changes",
                        description="Confirm issue resolution and report final status",
                        tool="inspect_file",
                        dependencies=["step_6"],
                        permission_level="READ",
                        risk_level="SAFE"
                    )
                ]
            )

        # Check if goal is browser related
        url_match = re.search(r'https?://[^\s]+', goal)
        if "open" in lower_goal and ("http" in lower_goal or "fastapi" in lower_goal or "doc" in lower_goal or "website" in lower_goal or "page" in lower_goal or "site" in lower_goal):
            target_url = url_match.group(0) if url_match else "https://fastapi.tiangolo.com/"
            return TaskPlan(
                goal=goal,
                steps=[
                    PlanStepSchema(
                        id="step_1",
                        title=f"Open target web page: '{target_url}'",
                        description=f"Launch isolated browser session and open {target_url}",
                        tool="browser_open",
                        dependencies=[],
                        permission_level="BROWSER_READ"
                    ),
                    PlanStepSchema(
                        id="step_2",
                        title="Extract page content & navigation links",
                        description="Extract structured headings, text, and interactive elements",
                        tool="browser_extract",
                        dependencies=["step_1"],
                        permission_level="BROWSER_READ"
                    ),
                    PlanStepSchema(
                        id="step_3",
                        title="Navigate to requested section & extract details",
                        description="Perform click navigation or section extraction for target topic",
                        tool="browser_extract",
                        dependencies=["step_2"],
                        permission_level="BROWSER_READ"
                    ),
                    PlanStepSchema(
                        id="step_4",
                        title="Close browser session & report findings",
                        description="Close browser session and format summary report",
                        tool="browser_close",
                        dependencies=["step_3"],
                        permission_level="BROWSER_READ"
                    )
                ]
            )

        # Generic default plan
        return TaskPlan(
            goal=goal,
            steps=[
                PlanStepSchema(
                    id="step_1",
                    title=f"Explore workspace context for '{goal}'",
                    description="Perform search across workspace files",
                    tool="search_files",
                    dependencies=[],
                    permission_level="READ"
                ),
                PlanStepSchema(
                    id="step_2",
                    title="Inspect file contents",
                    description="Read relevant file contents",
                    tool="read_file",
                    dependencies=["step_1"],
                    permission_level="READ"
                ),
                PlanStepSchema(
                    id="step_3",
                    title="Execute goal resolution step",
                    description="Execute action or report findings for goal",
                    tool="inspect_file",
                    dependencies=["step_2"],
                    permission_level="READ"
                )
            ]
        )

    async def replan(
        self,
        goal: str,
        completed_steps: List[PlanStepSchema],
        failed_step: PlanStepSchema,
        failure_category: FailureCategory,
        error_message: str,
        tool_output: Any,
        project_id: Optional[str] = None,
        retry_count: int = 0
    ) -> ReplanDecision:
        """
        Generates a structured recovery strategy and updated steps when a step fails.
        """
        logger.info(f"Replanning for task step '{failed_step.id}' (Category: {failure_category.value}, Retries: {retry_count})")

        # 1. PERMISSION failure -> Escalate to user
        if failure_category == FailureCategory.PERMISSION:
            return ReplanDecision(
                strategy=RecoveryStrategy.ASK_USER,
                reasoning_metadata=f"Permission for operation '{failed_step.permission_level}' on tool '{failed_step.tool}' was denied. Escalating to human user.",
                user_prompt=f"Permission required: Operation '{failed_step.title}' requires approval for {failed_step.permission_level}."
            )

        # 2. Exceeded Retry Bounds -> Prevent infinite loop, attempt alternative or escalate
        max_retries = failed_step.retry_policy.get("max_retries", 2)
        if retry_count >= max_retries:
            # If terminal failed, try alternative tool or escalate
            if failed_step.tool in ("terminal", "edit_file"):
                return ReplanDecision(
                    strategy=RecoveryStrategy.ASK_USER,
                    reasoning_metadata=f"Step '{failed_step.id}' failed {retry_count} times ({error_message}). Reached maximum retry boundary. Escalating to human user.",
                    user_prompt=f"Task recovery limit reached for step '{failed_step.title}': {error_message}. How would you like to proceed?"
                )
            else:
                return ReplanDecision(
                    strategy=RecoveryStrategy.ABORT,
                    reasoning_metadata=f"Step '{failed_step.id}' failed repeatedly ({error_message}). Aborting execution.",
                    user_prompt=f"Task aborted after exceeding retry bounds: {error_message}"
                )

        # 3. TRANSIENT or TIMEOUT failure -> Retry once
        if failure_category in (FailureCategory.TRANSIENT, FailureCategory.TIMEOUT):
            return ReplanDecision(
                strategy=RecoveryStrategy.RETRY,
                reasoning_metadata=f"Failure categorized as {failure_category.value}. Initiating transient retry (Attempt {retry_count + 1}).",
                new_steps=[failed_step.model_dump()]
            )

        # 4. TOOL_FAILURE / LOGICAL_FAILURE -> Modify plan or attempt diagnostic inspection
        if failure_category in (FailureCategory.TOOL_FAILURE, FailureCategory.LOGICAL_FAILURE, FailureCategory.ENVIRONMENT):
            # Check if failed step was running tests: add diagnostic inspection step before retry
            if failed_step.tool == "terminal" and ("pytest" in str(failed_step.arguments) or "test" in failed_step.description.lower()):
                diag_step = PlanStepSchema(
                    id=f"{failed_step.id}_diag",
                    title="Inspect failure output and source files",
                    description="Read failing test output and associated source file",
                    tool="read_file",
                    dependencies=[],
                    permission_level="READ",
                    risk_level="SAFE"
                )
                fix_step = PlanStepSchema(
                    id=f"{failed_step.id}_fix",
                    title="Apply code correction",
                    description="Modify source file to fix failing assertion",
                    tool="edit_file",
                    dependencies=[diag_step.id],
                    permission_level="WRITE",
                    risk_level="REVIEW"
                )
                rerun_step = PlanStepSchema(
                    id=f"{failed_step.id}_rerun",
                    title="Re-run automated test suite",
                    description="Verify fix passes tests",
                    tool="terminal",
                    dependencies=[fix_step.id],
                    permission_level="TERMINAL_EXECUTE",
                    risk_level="SAFE"
                )
                return ReplanDecision(
                    strategy=RecoveryStrategy.MODIFY_PLAN,
                    reasoning_metadata=f"Test run failed with error '{error_message}'. Inserting diagnostic inspection, code correction, and re-test steps into plan.",
                    new_steps=[diag_step.model_dump(), fix_step.model_dump(), rerun_step.model_dump()]
                )

        # Default: Retry with updated reasoning metadata
        return ReplanDecision(
            strategy=RecoveryStrategy.RETRY,
            reasoning_metadata=f"Standard failure recovery for category {failure_category.value}. Retrying step.",
            new_steps=[failed_step.model_dump()]
        )

agent_planner = AgentPlanner()
