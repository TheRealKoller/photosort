from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from photosort.db import Base


class ScanStatus(enum.StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    opencloud_drive_id: Mapped[str]
    opencloud_path: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    photos: Mapped[list[Photo]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scan_runs: Mapped[list[ScanRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (
        UniqueConstraint("project_id", "relative_path", name="uq_photo_project_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    relative_path: Mapped[str]
    etag: Mapped[str]
    content_length: Mapped[int]
    taken_at: Mapped[datetime]
    last_modified: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    project: Mapped[Project] = relationship(back_populates="photos")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    files_found: Mapped[int] = mapped_column(default=0)
    photos_added: Mapped[int] = mapped_column(default=0)
    photos_updated: Mapped[int] = mapped_column(default=0)
    photos_removed: Mapped[int] = mapped_column(default=0)
    files_skipped: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="scan_runs")
