from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any
from datetime import datetime

# ─── Workspace Schemas ────────────────────────────────────────
class WorkspaceBase(BaseModel):
    name: str
    path: str

class WorkspaceCreate(WorkspaceBase):
    pass

class WorkspaceResponse(WorkspaceBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ─── Project Schemas ──────────────────────────────────────────
class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    icon: Optional[str] = "folder_open"
    path: Optional[str] = None
    languages: Optional[List[str]] = Field(default_factory=list)
    frameworks: Optional[List[str]] = Field(default_factory=list)
    git_repository: bool = False
    detection_confidence: Optional[str] = "high"
    last_scanned: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    metadata_info: Optional[dict] = None

class ProjectCreate(ProjectBase):
    workspace_id: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: str
    workspace_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ScanWorkspaceResponse(BaseModel):
    workspace: WorkspaceResponse
    projects: List[ProjectResponse]

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

# ─── Research Engine Schemas ─────────────────────────────────
class ResearchRunRequest(BaseModel):
    query: str = Field(..., description="Natural language research query or goal")
    project_id: Optional[str] = None

class ResearchPlanStep(BaseModel):
    id: str
    objective: str
    queries: List[str] = Field(default_factory=list)
    status: str = "pending"

class ResearchPlan(BaseModel):
    goal: str
    steps: List[ResearchPlanStep] = Field(default_factory=list)

class ResearchSourceResponse(BaseModel):
    id: str
    research_session_id: str
    title: str
    url: str
    domain: str
    provider: str
    retrieved_at: datetime
    content_excerpt: Optional[str] = None
    relevance: float = 1.0

    model_config = ConfigDict(from_attributes=True)

class ResearchEvidenceResponse(BaseModel):
    id: str
    research_session_id: str
    source_id: Optional[str] = None
    claim: str
    supporting_text: str
    confidence: str = "high"

    model_config = ConfigDict(from_attributes=True)

class ResearchFindingResponse(BaseModel):
    id: str
    research_session_id: str
    finding_text: str
    is_verified: bool = True
    verification_confidence: str = "high"
    supporting_sources: Optional[List[str]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class ResearchSessionBase(BaseModel):
    title: str
    brief: str
    project_id: Optional[str] = None

class ResearchSessionCreate(ResearchSessionBase):
    pass

class ResearchSessionResponse(ResearchSessionBase):
    id: str
    session_code: str
    query: Optional[str] = None
    status: str
    confidence: int
    synthesis_markdown: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    sources: List[ResearchSourceResponse] = Field(default_factory=list)
    evidence: List[ResearchEvidenceResponse] = Field(default_factory=list)
    findings: List[ResearchFindingResponse] = Field(default_factory=list)

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
