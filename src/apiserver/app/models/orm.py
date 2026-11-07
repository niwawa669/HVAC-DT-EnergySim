"""ORM 模型（D3/D5/D9/D11）。

时间戳统一存本地时间（D9），与既有接口序列化格式保持一致。
JSON 列使用 sqlalchemy.JSON：SQLite 落 TEXT，MySQL 落 JSON。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now()


class Base(DeclarativeBase):
    pass


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="engineer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_owner", "owner_id", "updated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    building_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)


class Dataset(Base):
    __tablename__ = "datasets"

    # id 就是内容 sha256，天然去重（D4）
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_column: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    headers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class SimulationTask(Base):
    __tablename__ = "simulation_tasks"
    __table_args__ = (
        Index("ix_tasks_user_updated", "user_id", "updated_at"),
        Index("ix_tasks_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_week: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=52)
    project_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    building_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    data_meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_tasks.id", ondelete="CASCADE"), primary_key=True
    )
    caliber_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    total_energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_cooling_load: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eui: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carbon_emission: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peak_load: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class Report(Base):
    __tablename__ = "reports"
    # task_id 不设外键：历史报告的 task 早已不存在（D5）
    __table_args__ = (Index("ix_reports_task", "task_id", "generated_at"),)

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    report_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    caliber_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    generated_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    meta_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    chapters: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    chapter_titles: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    html_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    result_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    meta_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    html_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    html_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    artifact_state: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
