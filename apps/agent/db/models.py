import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Boolean, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="folder_open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    research_sessions: Mapped[List["ResearchSession"]] = relationship("ResearchSession", back_populates="project", cascade="all, delete-orphan")
    automations: Mapped[List["Automation"]] = relationship("Automation", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="idle")  # idle, running, error, done
    icon: Mapped[str] = mapped_column(String(50), default="checklist")
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="tasks")
    steps: Mapped[List["TaskStep"]] = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan")
    activity_logs: Mapped[List["ActivityLog"]] = relationship("ActivityLog", back_populates="task", cascade="all, delete-orphan")


class TaskStep(Base):
    __tablename__ = "task_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, active, done
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship("Task", back_populates="steps")


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    session_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="running")
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    synthesis_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="research_sessions")


class Automation(Base):
    __tablename__ = "automations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default="schedule")
    trigger_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_result: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nodes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="automations")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    timestamp: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="done")  # done, active, info, error
    details: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped[Optional["Task"]] = relationship("Task", back_populates="activity_logs")


class SettingModel(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
