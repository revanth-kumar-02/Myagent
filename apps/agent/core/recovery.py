import logging
import re
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from core.state import StepExecutionState

logger = logging.getLogger(__name__)

class FailureCategory(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMISSION = "PERMISSION"
    INVALID_INPUT = "INVALID_INPUT"
    TOOL_FAILURE = "TOOL_FAILURE"
    ENVIRONMENT = "ENVIRONMENT"
    LOGICAL_FAILURE = "LOGICAL_FAILURE"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"

class RecoveryStrategy(str, Enum):
    RETRY = "RETRY"
    ALTERNATIVE_TOOL = "ALTERNATIVE_TOOL"
    MODIFY_PLAN = "MODIFY_PLAN"
    ASK_USER = "ASK_USER"
    ABORT = "ABORT"

class ReplanDecision(BaseModel):
    strategy: RecoveryStrategy
    reasoning_metadata: str = Field(description="Internal reasoning explanation for selected recovery strategy")
    new_steps: List[Dict[str, Any]] = Field(default_factory=list, description="Replacement or additional steps if strategy modifies plan")
    user_prompt: Optional[str] = Field(default=None, description="Escalation question for user if strategy is ASK_USER or ABORT")

class FailureClassifier:
    """Classifies tool & execution failures into discrete categories for deterministic recovery routing."""

    @staticmethod
    def classify(
        error_message: str,
        tool_name: str,
        tool_output: Optional[Any] = None,
        exit_code: Optional[int] = None
    ) -> FailureCategory:
        if not error_message and not tool_output:
            return FailureCategory.UNKNOWN

        err_lower = (str(error_message) + " " + str(tool_output)).lower()

        # Timeout check
        if "timed out" in err_lower or "timeout" in err_lower or "asyncio.timeouterror" in err_lower:
            return FailureCategory.TIMEOUT

        # Permission check
        if "permission denied" in err_lower or "security rejection" in err_lower or "access denied" in err_lower or "outside project" in err_lower:
            return FailureCategory.PERMISSION

        # Invalid Input check
        if "invalid argument" in err_lower or "missing required" in err_lower or "malformed" in err_lower or "valueerror" in err_lower:
            return FailureCategory.INVALID_INPUT

        # Environment check
        if "connection refused" in err_lower or "modulenotfounderror" in err_lower or "module not found" in err_lower or "command not found" in err_lower or "no such file" in err_lower:
            return FailureCategory.ENVIRONMENT

        # Tool failure / exit code
        if exit_code is not None and exit_code != 0:
            return FailureCategory.TOOL_FAILURE
        if "failed" in err_lower or "error" in err_lower:
            return FailureCategory.TOOL_FAILURE

        # Logical failure (from verification)
        if "verification failed" in err_lower or "outcome mismatch" in err_lower:
            return FailureCategory.LOGICAL_FAILURE

        # Transient
        if "temporary" in err_lower or "503" in err_lower or "rate limit" in err_lower:
            return FailureCategory.TRANSIENT

        return FailureCategory.UNKNOWN
