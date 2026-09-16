from enum import Enum
from typing import Optional, Dict, Any, List, Set
from pydantic import BaseModel, Field

class AgentState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskStepState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    WAITING_DEPENDENCY = "waiting_dependency"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLANNING = "replanning"
    CANCELLED = "cancelled"

VALID_TRANSITIONS: Dict[TaskStepState, Set[TaskStepState]] = {
    TaskStepState.PENDING: {TaskStepState.READY, TaskStepState.WAITING_DEPENDENCY, TaskStepState.RUNNING, TaskStepState.CANCELLED, TaskStepState.FAILED},
    TaskStepState.WAITING_DEPENDENCY: {TaskStepState.READY, TaskStepState.CANCELLED, TaskStepState.FAILED},
    TaskStepState.READY: {TaskStepState.RUNNING, TaskStepState.WAITING_PERMISSION, TaskStepState.CANCELLED, TaskStepState.FAILED},
    TaskStepState.WAITING_PERMISSION: {TaskStepState.RUNNING, TaskStepState.CANCELLED, TaskStepState.FAILED},
    TaskStepState.RUNNING: {TaskStepState.VERIFYING, TaskStepState.WAITING_PERMISSION, TaskStepState.FAILED, TaskStepState.COMPLETED, TaskStepState.CANCELLED},
    TaskStepState.VERIFYING: {TaskStepState.COMPLETED, TaskStepState.FAILED, TaskStepState.REPLANNING, TaskStepState.CANCELLED},
    TaskStepState.FAILED: {TaskStepState.REPLANNING, TaskStepState.CANCELLED},
    TaskStepState.REPLANNING: {TaskStepState.READY, TaskStepState.PENDING, TaskStepState.RUNNING, TaskStepState.FAILED, TaskStepState.CANCELLED},
    TaskStepState.COMPLETED: {TaskStepState.COMPLETED},
    TaskStepState.CANCELLED: {TaskStepState.CANCELLED},
}

def validate_state_transition(current: TaskStepState, target: TaskStepState) -> bool:
    """Validates state transitions according to the explicit task state machine."""
    if current == target:
        return True
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Invalid state transition: '{current.value}' -> '{target.value}' is not allowed.")
    return True

class StepExecutionState(BaseModel):
    step_id: str
    step_number: int
    title: str
    description: str
    tool: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    expected_outcome: Optional[str] = None
    risk_level: str = "SAFE"
    permission_level: str = "READ"
    timeout: float = 60.0
    retry_policy: Dict[str, Any] = Field(default_factory=lambda: {"max_retries": 2})
    status: TaskStepState = TaskStepState.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0

class ExecutionContext(BaseModel):
    task_id: str
    goal: str
    project_id: Optional[str] = None
    active_page_id: Optional[str] = None
    current_state: AgentState = AgentState.IDLE
    steps: List[StepExecutionState] = Field(default_factory=list)
    current_step_index: int = 0
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    final_result: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float = 0.0
