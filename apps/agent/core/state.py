from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class AgentState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepExecutionState(BaseModel):
    step_id: str
    step_number: int
    title: str
    description: str
    tool: Optional[str] = None
    status: AgentState = AgentState.IDLE
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0

class ExecutionContext(BaseModel):
    task_id: str
    goal: str
    project_id: Optional[str] = None
    active_page_id: Optional[str] = None
    current_state: AgentState = AgentState.IDLE
    steps: List[StepExecutionState] = []
    current_step_index: int = 0
    observations: List[Dict[str, Any]] = []
    final_result: Optional[str] = None
    error_message: Optional[str] = None
