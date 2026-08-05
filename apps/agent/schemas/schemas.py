from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any
from datetime import datetime

# ─── Project Schemas ──────────────────────────────────────────
class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    icon: Optional[str] = "folder_open"

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ─── Task Step Schemas ────────────────────────────────────────
class TaskStepBase(BaseModel):
    step_number: int
    label: str
    status: str = "pending"  # pending, active, done

class TaskStepCreate(TaskStepBase):
    pass

class TaskStepResponse(TaskStepBase):
    id: str
    task_id: str

    model_config = ConfigDict(from_attributes=True)

# ─── Activity Log Schemas ─────────────────────────────────────
class ActivityLogBase(BaseModel):
    timestamp: str
    message: str
    status: str = "done"
    details: Optional[List[str]] = None

class ActivityLogCreate(ActivityLogBase):
    task_id: Optional[str] = None

class ActivityLogResponse(ActivityLogBase):
    id: str
    task_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ─── Task Schemas ─────────────────────────────────────────────
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    icon: Optional[str] = "checklist"

class TaskCreate(TaskBase):
    pass

class TaskResponse(TaskBase):
    id: str
    status: str
    result: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    steps: List[TaskStepResponse] = []
    activity_logs: List[ActivityLogResponse] = []

    model_config = ConfigDict(from_attributes=True)

# ─── Research Session Schemas ────────────────────────────────
class ResearchSessionBase(BaseModel):
    title: str
    brief: str
    project_id: Optional[str] = None

class ResearchSessionCreate(ResearchSessionBase):
    pass

class ResearchSessionResponse(ResearchSessionBase):
    id: str
    session_code: str
    status: str
    confidence: int
    synthesis_markdown: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ─── Automation Schemas ───────────────────────────────────────
class AutomationBase(BaseModel):
    title: str
    description: Optional[str] = None
    trigger_type: str = "schedule"
    trigger_config: Optional[dict] = None
    nodes: Optional[list] = None
    is_active: bool = True

class AutomationCreate(AutomationBase):
    project_id: Optional[str] = None

class AutomationResponse(AutomationBase):
    id: str
    project_id: Optional[str] = None
    last_run_at: Optional[datetime] = None
    last_run_result: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ─── Setting Schemas ──────────────────────────────────────────
class SettingUpdate(BaseModel):
    key: str
    value: str

class SettingResponse(BaseModel):
    key: str
    value: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
