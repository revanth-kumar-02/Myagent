import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Float, Boolean, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    projects: Mapped[List["Project"]] = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="folder_open")
    languages: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    frameworks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    git_repository: Mapped[bool] = mapped_column(Boolean, default=False)
    detection_confidence: Mapped[Optional[str]] = mapped_column(String(20), default="high")
    last_scanned: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace: Mapped[Optional["Workspace"]] = relationship("Workspace", back_populates="projects")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    research_sessions: Mapped[List["ResearchSession"]] = relationship("ResearchSession", back_populates="project", cascade="all, delete-orphan")
    automations: Mapped[List["Automation"]] = relationship("Automation", back_populates="project", cascade="all, delete-orphan")
    files: Mapped[List["ProjectFile"]] = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    technologies: Mapped[List["ProjectTechnology"]] = relationship("ProjectTechnology", back_populates="project", cascade="all, delete-orphan")
    dependencies: Mapped[List["ProjectDependency"]] = relationship("ProjectDependency", back_populates="project", cascade="all, delete-orphan")
    git_metadata: Mapped[Optional["GitMetadata"]] = relationship("GitMetadata", back_populates="project", cascade="all, delete-orphan", uselist=False)
    chunks: Mapped[List["ProjectChunk"]] = relationship("ProjectChunk", back_populates="project", cascade="all, delete-orphan")


class TaskStep(Base):
    __tablename__ = "task_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"))
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    arguments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dependencies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, active, done, failed, etc.
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    task: Mapped["Task"] = relationship("Task", back_populates="steps")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    timestamp: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="done")
    details: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    task: Mapped[Optional["Task"]] = relationship("Task", back_populates="activity_logs")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="idle")
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="checklist")
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    plan_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="tasks")
    steps: Mapped[List["TaskStep"]] = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan")
    activity_logs: Mapped[List["ActivityLog"]] = relationship("ActivityLog", back_populates="task", cascade="all, delete-orphan")


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="idle")  # idle, planning, researching, verifying, synthesizing, completed, failed, cancelled
    confidence: Mapped[int] = mapped_column(Integer, default=95)
    synthesis_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="research_sessions")
    sources: Mapped[List["ResearchSource"]] = relationship("ResearchSource", back_populates="research_session", cascade="all, delete-orphan")
    evidence: Mapped[List["ResearchEvidence"]] = relationship("ResearchEvidence", back_populates="research_session", cascade="all, delete-orphan")
    findings: Mapped[List["ResearchFinding"]] = relationship("ResearchFinding", back_populates="research_session", cascade="all, delete-orphan")


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="tavily")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    content_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relevance: Mapped[float] = mapped_column(Float, default=1.0)

    research_session: Mapped["ResearchSession"] = relationship("ResearchSession", back_populates="sources")
    evidence_items: Mapped[List["ResearchEvidence"]] = relationship("ResearchEvidence", back_populates="source", cascade="all, delete-orphan")


class ResearchEvidence(Base):
    __tablename__ = "research_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("research_sources.id", ondelete="SET NULL"), nullable=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), default="high")

    research_session: Mapped["ResearchSession"] = relationship("ResearchSession", back_populates="evidence")
    source: Mapped[Optional["ResearchSource"]] = relationship("ResearchSource", back_populates="evidence_items")


class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    finding_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_confidence: Mapped[str] = mapped_column(String(20), default="high")
    supporting_sources: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    research_session: Mapped["ResearchSession"] = relationship("ResearchSession", back_populates="findings")


class Automation(Base):
    __tablename__ = "automations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default="schedule")  # CRON | INTERVAL | ONE_TIME | MANUAL | TASK_COMPLETION | FILE_CHANGE | GIT_CHANGE | CONDITION
    trigger_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    workflow_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # steps, condition logic, safety bounds
    nodes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_run_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="automations")
    runs: Mapped[list["AutomationRun"]] = relationship("AutomationRun", back_populates="automation", cascade="all, delete-orphan")


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    automation_id: Mapped[str] = mapped_column(String(36), ForeignKey("automations.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="QUEUED")  # QUEUED | RUNNING | WAITING_PERMISSION | RETRYING | REPLANNING | COMPLETED | FAILED | CANCELLED | SKIPPED
    trigger_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    llm_call_count: Mapped[int] = mapped_column(Integer, default=0)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_logs: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    automation: Mapped["Automation"] = relationship("Automation", back_populates="runs")



class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


from pgvector.sqlalchemy import Vector
from sqlalchemy.types import TypeDecorator

class JSONOrVector(TypeDecorator):
    """
    TypeDecorator that uses pgvector Vector(384) when pgvector extension is active,
    or falls back gracefully to JSON without breaking when reading/writing Python lists.
    """
    impl = JSON
    cache_ok = True

    class comparator_factory(Vector.comparator_factory):
        pass

    def load_dialect_impl(self, dialect):
        try:
            from db.session import IS_PGVECTOR_AVAILABLE
            if dialect.name == "postgresql" and IS_PGVECTOR_AVAILABLE:
                return dialect.type_descriptor(Vector(384))
        except Exception:
            pass
        return dialect.type_descriptor(JSON())

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return [float(x) for x in value.strip("[]").split(",") if x.strip()]
            except Exception:
                return value
        return value

class ProjectFile(Base):
    __tablename__ = "project_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), default="source")  # source, config, documentation, build
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="files")


class ProjectChunk(Base):
    __tablename__ = "project_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(JSONOrVector, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="chunks")


class ProjectTechnology(Base):
    __tablename__ = "project_technologies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="framework")  # language, framework, database, tool, package_manager
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    evidence_source: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. package.json, requirements.txt, Cargo.toml
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="technologies")


class ProjectDependency(Base):
    __tablename__ = "project_dependencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version_spec: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ecosystem: Mapped[str] = mapped_column(String(50), default="npm")  # npm, pip, cargo, maven, gradle, pub
    is_dev: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="dependencies")


class GitMetadata(Base):
    __tablename__ = "git_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    branch: Mapped[str] = mapped_column(String(100), default="main")
    latest_commit_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    latest_commit_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latest_commit_author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latest_commit_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    modified_files_count: Mapped[int] = mapped_column(Integer, default=0)
    status_clean: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="git_metadata")


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)  # FACT, DECISION, PREFERENCE, PROJECT_KNOWLEDGE, RESEARCH_FINDING, TASK_OUTCOME, TECHNICAL_CONTEXT, USER_PREFERENCE
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="user")
    source_reliability: Mapped[str] = mapped_column(String(50), default="USER_CONFIRMED")  # USER_CONFIRMED, VERIFIED_TASK, VERIFIED_RESEARCH, PROJECT_FILE, GIT_METADATA, AGENT_INFERENCE
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    importance: Mapped[int] = mapped_column(Integer, default=5)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    verification_status: Mapped[str] = mapped_column(String(50), default="ACTIVE")  # CANDIDATE, VERIFIED, ACTIVE, SUPERSEDED, ARCHIVED, CONFLICT_DETECTED
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("agent_memories.id", ondelete="SET NULL"), nullable=True)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[Optional[List[float]]] = mapped_column(JSONOrVector, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PermissionAuditLog(Base):
    __tablename__ = "permission_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    permission_level: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)  # granted, denied, blocked
    scope: Mapped[str] = mapped_column(String(50), default="ONCE")  # ONCE, TASK, SESSION
    task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Aliases for compatibility
SettingModel = Setting
