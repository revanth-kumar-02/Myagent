import re
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ContextRoutingMode(str, Enum):
    NONE = "NONE"
    PROJECT_RAG = "PROJECT_RAG"
    WEB_RESEARCH = "WEB_RESEARCH"
    BOTH = "BOTH"

class RoutingDecision(BaseModel):
    mode: ContextRoutingMode
    reason: str
    needs_rag: bool
    needs_web: bool
    project_query: Optional[str] = None
    web_query: Optional[str] = None

    @property
    def reasoning(self) -> str:
        return self.reason

ContextRoutingDecision = RoutingDecision

# Patterns for simple computations, direct tool tasks, or math requiring NEITHER
NONE_PATTERNS = [
    re.compile(r"^\s*(?:calculate|compute|eval|what is\s+\d+[\s\+\-\*\/\^%]+\d+)", re.IGNORECASE),
    re.compile(r"^\s*(?:echo|print|count\s+(?:from|to)|generate\s+a\s+random)", re.IGNORECASE),
    re.compile(r"^\s*(?:hello|hi|hey|ping|test)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:create|touch|mkdir|delete|remove)\s+[a-zA-Z0-9_\-\.\/]+\s*$", re.IGNORECASE),
]

# Patterns explicitly referencing local codebase, files, functions, project architecture
PROJECT_PATTERNS = [
    re.compile(r"\b(?:in this project|in our codebase|in the project|in our project|our project|this project|local repository|in our repo)\b", re.IGNORECASE),
    re.compile(r"\b(?:our (?:project|codebase|code|schema|database|models|routes|auth|api|backend|frontend|repo|app|implementation))\b", re.IGNORECASE),
    re.compile(r"\b(?:where is|how does|find the|show the|explain the)\s+(?:function|class|method|component|table|file|symbol)\b", re.IGNORECASE),
    re.compile(r"\b(?:loginUser|PaymentService|ProjectChunk|AgentMemory|UserSession|TaskStep|AuthHandler)\b"),
    re.compile(r"\b[a-zA-Z0-9_\-]+\.(?:py|ts|js|jsx|tsx|sql|html|css|json|yaml|dart|kt|java)\b", re.IGNORECASE),
]

# Patterns explicitly referencing external information, live web, latest releases, documentation
WEB_PATTERNS = [
    re.compile(r"\b(?:latest|current|newest|recent|today|2025|2026|release notes|changelog)\b", re.IGNORECASE),
    re.compile(r"\b(?:who won|weather|price of|market cap|news about|stock price)\b", re.IGNORECASE),
    re.compile(r"\b(?:official (?:docs|documentation|guide)|rfc|pep|spec)\b", re.IGNORECASE),
    re.compile(r"\b(?:search the web|google|look up online|external api|browse)\b", re.IGNORECASE),
    re.compile(r"\b(?:owasp|stripe api|github api|openai api|fastapi docs|react 19)\b", re.IGNORECASE),
]

class ContextIntentRouter:
    """
    Intelligently routes agent tasks to:
    1. PROJECT_RAG: Local codebase questions
    2. WEB_RESEARCH: Current / external web knowledge
    3. BOTH: Local project context + external web documentation
    4. NONE: Simple local computation or direct commands
    """

    async def route(self, goal: str, project_id: Optional[str] = None) -> RoutingDecision:
        clean_goal = goal.strip()
        if not clean_goal:
            return RoutingDecision(
                mode=ContextRoutingMode.NONE,
                reason="Empty goal statement",
                needs_rag=False,
                needs_web=False
            )

        # 1. Check for pure computation or simple direct command (NONE)
        for pat in NONE_PATTERNS:
            if pat.search(clean_goal):
                # Ensure it does not mention project or external libraries
                if not any(wp.search(clean_goal) for wp in WEB_PATTERNS) and not any(pp.search(clean_goal) for pp in PROJECT_PATTERNS):
                    return RoutingDecision(
                        mode=ContextRoutingMode.NONE,
                        reason="Simple computation or direct command requiring no external or project context",
                        needs_rag=False,
                        needs_web=False
                    )

        has_project_intent = False
        has_web_intent = False

        # 2. Check project pattern matches
        if any(pp.search(clean_goal) for pp in PROJECT_PATTERNS):
            has_project_intent = True
        elif project_id and re.search(r"\b(?:code|function|class|method|module|file|bug|error|test|refactor|implement|route|endpoint|auth)\b", clean_goal, re.IGNORECASE):
            has_project_intent = True

        # 3. Check web pattern matches
        if any(wp.search(clean_goal) for wp in WEB_PATTERNS):
            has_web_intent = True
        elif not project_id and re.search(r"\b(?:what is|how to|why is|explain|compare|versus|vs|best practice)\b", clean_goal, re.IGNORECASE):
            has_web_intent = True

        # 4. Synthesize decision
        if has_project_intent and has_web_intent:
            return RoutingDecision(
                mode=ContextRoutingMode.BOTH,
                reason="Task requires both local project codebase context and live external web documentation",
                needs_rag=True,
                needs_web=True,
                project_query=clean_goal,
                web_query=clean_goal
            )
        elif has_project_intent:
            return RoutingDecision(
                mode=ContextRoutingMode.PROJECT_RAG,
                reason="Task focuses on local project code, files, or architecture",
                needs_rag=True,
                needs_web=False,
                project_query=clean_goal
            )
        elif has_web_intent:
            return RoutingDecision(
                mode=ContextRoutingMode.WEB_RESEARCH,
                reason="Task requests current or external world information",
                needs_rag=False,
                needs_web=True,
                web_query=clean_goal
            )
        else:
            # Default to direct execution if neither project nor web query is indicated
            return RoutingDecision(
                mode=ContextRoutingMode.NONE,
                reason="Standard task requiring normal direct agent execution",
                needs_rag=False,
                needs_web=False
            )

context_intent_router = ContextIntentRouter()
