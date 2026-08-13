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
    scoring_runs: Mapped[list[ScoringRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    top_selection_runs: Mapped[list[TopSelectionRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class RatingStatus(enum.StrEnum):
    FAVORITE = "favorite"
    ALBUM_WORTHY = "album_worthy"
    REJECTED = "rejected"


class PhotoCategory(enum.StrEnum):
    """Lokal (kein Cloud-Aufruf) klassifizierte Motiv-Kategorie eines Fotos
    (specs/features/0024-top-photo-selection-category-mix.md, decisions/0015-lokale-kategorie-
    klassifikation.md). Nur 3 statt urspruenglich 4 geplanter Kategorien - "Sehenswuerdigkeit"
    wurde fuer v1 gestrichen (ohne GPS oder ein schweres Landmark-Modell lokal nicht sinnvoll
    erkennbar, siehe Entscheidungen-Abschnitt der Spec)."""

    LANDSCAPE = "landscape"
    DETAIL = "detail"
    PEOPLE = "people"


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
    ratings: Mapped[list[Rating]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )
    score: Mapped[PhotoScore | None] = relationship(
        back_populates="photo",
        foreign_keys="PhotoScore.photo_id",
        uselist=False,
        cascade="all, delete-orphan",
    )


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
    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR 0019):
    # server-seitig defaultet (analog started_at), damit ein frisch angelegter Lauf sofort einen
    # last_progress_at-Wert hat und nicht bereits ab Zeile 1 als Stillstand gilt. Wird an denselben
    # Stellen wie files_found periodisch zwischen-committet (worker.py::_commit_progress_checkpoint)
    # und von worker.py::reap_stalled_runs gelesen.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020: additiv, default=None
    # (nicht 0) - unterscheidet bewusst "Enumerationsphase (Phase 1) noch nicht abgeschlossen,
    # Gesamtzahl unbekannt" von "Projekt enthaelt 0 Dateien". Ueberall mit `is not None` statt
    # truthy zu pruefen (0 ist ein gueltiger, informativer Wert). Wird nach Abschluss von Phase 1
    # (worker.py::run_project_scan) einmalig auf len(entries) gesetzt und danach nicht mehr
    # veraendert.
    total_files: Mapped[int | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="scan_runs")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Rating(Base):
    """Bewertung eines Photos durch einen User (specs/features/0002-manual-categorization.md).

    "Unbewertet" wird bewusst nicht als eigener Enum-Wert modelliert, sondern als Fehlen einer
    Zeile fuer (photo_id, user_id) - macht Toggle/Ueberschreiben zu einem einfachen Upsert ueber
    den Unique-Constraint, siehe api/ratings.py.
    """

    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("photo_id", "user_id", name="uq_rating_photo_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[RatingStatus] = mapped_column(
        SQLEnum(RatingStatus, native_enum=False, length=20)
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    photo: Mapped[Photo] = relationship(back_populates="ratings")
    user: Mapped[User] = relationship()


class ScoringRun(Base):
    """Ein Lauf des lokalen Scoring-Jobs (specs/features/0003-automatic-best-photo-selection.md,
    decisions/0006-local-scoring-datamodel.md), analog ScanRun. Nutzt bewusst denselben
    ScanStatus-Enum wie ScanRun statt eines eigenen ScoringStatus - beide Enums haben identische
    Semantik (running/success/failed) fuer einen asynchron laufenden Worker-Job.

    photos_total/photos_processed liefern granularen Live-Fortschritt (periodisch
    zwischen-committet, siehe worker.py::run_project_scoring) - analog zu ScanRun.files_found, das
    seit specs/features/0022-scan-live-fortschrittszaehler.md ebenfalls periodisch statt nur am
    Ende committet wird (siehe worker.py::run_project_scan, SCAN_COMMIT_BATCH_SIZE).
    """

    __tablename__ = "scoring_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    photos_total: Mapped[int] = mapped_column(default=0)
    photos_processed: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(default=None)
    # Anzahl der Fotos, deren PhotoScore.suggested_status in diesem Lauf gesetzt wurde
    # (Duplikat-Verlierer + zu unscharfe Fotos, siehe worker.py::run_project_scoring,
    # Variable rejected_ids). Bleibt bei einem fehlgeschlagenen Lauf auf dem Default 0 - kein
    # irrefuehrender Teilstand (specs/features/0021-scoring-run-vorschlagszaehler.md).
    suggestions_found: Mapped[int] = mapped_column(default=0, server_default="0")
    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md), analog
    # ScanRun.last_progress_at oben.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="scoring_runs")


class PhotoScore(Base):
    """Automatisch berechnete Bewertungsgrundlage eines Fotos, 1:1 zu Photo
    (specs/features/0003-automatic-best-photo-selection.md, decisions/0006-local-scoring-
    datamodel.md). Bewusst KEINE Rating-Zeile und bewusst eine eigene Tabelle statt eines
    source-Felds an Rating (siehe ADR 0006) - ein Vorschlag wird erst durch aktive
    Nutzerbestaetigung ueber den bestehenden PUT /photos/{id}/rating-Endpunkt zu einer echten
    Bewertung. `photo_id` ist Primary Key (kein separates id+Unique-Constraint-Paar wie bei
    Rating), weil es strukturell nie mehrere Zeilen pro Foto gibt.
    """

    __tablename__ = "photo_scores"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    sharpness: Mapped[float]
    exposure: Mapped[float]
    phash: Mapped[str | None] = mapped_column(default=None)
    # Selbstreferenzierender FK auf photos.id (nicht auf photo_scores.photo_id): zeigt auf das im
    # Duplikat-/Burst-Cluster behaltene FOTO, das nicht zwingend selbst schon eine PhotoScore-Zeile
    # braucht, um referenziert werden zu koennen.
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("photos.id"), default=None)
    cluster_key: Mapped[str | None] = mapped_column(default=None)
    local_quality_score: Mapped[float | None] = mapped_column(default=None)
    # Wiederverwendet das bestehende RatingStatus-Enum (Akzeptanzkriterium der Spec) - Phase A
    # setzt darueber praktisch nur REJECTED, offene Positivempfehlungen bleiben Phase B
    # vorbehalten, ohne dass das Feld dafuer erneut migriert werden muesste.
    suggested_status: Mapped[RatingStatus | None] = mapped_column(
        SQLEnum(RatingStatus, native_enum=False, length=20), default=None
    )
    computed_at: Mapped[datetime]
    # Additiv, specs/features/0024-top-photo-selection-category-mix.md: NICHT in Phase A
    # (run_project_scoring) mitberechnet, sondern erst im neuen select_top_photos-Job, nur fuer den
    # dort bereits begrenzten Kandidatenpool pro Cluster - sonst wuerde mediapipe fuer jedes
    # gescannte Foto laufen (auch fuer nie betrachtete Duplikat-Verlierer). Bei jedem
    # select-top-Lauf neu berechnet (kein Reuse-Tracking, da lokal/kostenlos), siehe
    # worker.py::select_top_photos.
    category: Mapped[PhotoCategory | None] = mapped_column(
        SQLEnum(PhotoCategory, native_enum=False, length=20), default=None
    )

    photo: Mapped[Photo] = relationship(back_populates="score", foreign_keys=[photo_id])


class TopSelectionRun(Base):
    """Ein Lauf des lokalen Top-Auswahl-Jobs (specs/features/0024-top-photo-selection-category-
    mix.md), analog ScoringRun/ScanRun. Nutzt wie ScoringRun den bestehenden ScanStatus-Enum
    (running/success/failed) statt eines eigenen Status-Enums - identische Semantik fuer einen
    asynchron laufenden Worker-Job.

    candidates_total/candidates_processed liefern granularen Live-Fortschritt (periodisch
    zwischen-committet, siehe worker.py::select_top_photos) - mediapipe-Inferenz hat pro Foto eine
    spuerbare Laufzeit, deshalb ein eigener asynchroner Job statt synchroner Verarbeitung, analog
    zu ScoringRun.photos_total/photos_processed (decisions/0006-local-scoring-datamodel.md).
    """

    __tablename__ = "top_selection_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    top_n_per_cluster: Mapped[int] = mapped_column(default=0)
    candidates_total: Mapped[int] = mapped_column(default=0)
    candidates_processed: Mapped[int] = mapped_column(default=0)
    suggestions_found: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(default=None)
    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md), analog
    # ScanRun.last_progress_at oben.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="top_selection_runs")
