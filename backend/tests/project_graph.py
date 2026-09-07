"""Aufbau eines Projekts mit je einer Zeile in ALLEN am Projekt haengenden Tabellen.

Bewusst kein `test_*`-Modul (wird nicht eingesammelt): der Aufbau wird von
`test_project_deletion.py` (Modulebene) und `test_api_projects.py` (API-Ebene) gemeinsam
gebraucht - specs/features/0044-projekte-loeschen.md verlangt an beiden Stellen einen VOLLEN
Datengraphen und je Tabelle eine eigene Zeilenzaehlungs-Assertion.

Die Zaehlungen selbst stehen bewusst NICHT hier, sondern tabellenweise ausgeschrieben im
jeweiligen Test - nur so nennt die Fehlermeldung die vergessene Tabelle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.db import Base
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    FineLabel,
    Photo,
    PhotoCategoryClassification,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoLandmarkDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)


@dataclass(frozen=True)
class ProjectGraph:
    """Die Bezugspunkte eines aufgebauten Projekts, die ein Test danach braucht."""

    project_id: int
    project_name: str
    photo_id: int
    photo_etag: str
    scan_run_id: int
    scoring_run_id: int
    criterion_scoring_run_id: int
    remote_run_id: int
    fine_label_id: int


async def get_or_create_user(session: AsyncSession, username: str = "graph-user") -> User:
    existing = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    user = User(username=username, password_hash="hashed-value")
    session.add(user)
    await session.flush()
    return user


async def get_or_create_fine_label(
    session: AsyncSession, canonical_key: str = "strand"
) -> FineLabel:
    """Der projektuebergreifende Vokabular-Eintrag (ADR 0032) - bewusst wiederverwendbar, damit
    ein Test zwei Projekte auf DENSELBEN `fine_labels`-Eintrag zeigen lassen kann."""
    existing = (
        await session.execute(select(FineLabel).where(FineLabel.canonical_key == canonical_key))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    fine_label = FineLabel(
        canonical_key=canonical_key, display_name=canonical_key.capitalize(), embedding=[0.1, 0.2]
    )
    session.add(fine_label)
    await session.flush()
    return fine_label


async def build_project_graph(
    session: AsyncSession, name: str, *, fine_label_key: str = "strand"
) -> ProjectGraph:
    """Legt ein Projekt mit genau einer Zeile in jeder der dreizehn abhaengigen Tabellen an."""
    now = datetime.now(UTC).replace(tzinfo=None)
    user = await get_or_create_user(session)
    fine_label = await get_or_create_fine_label(session, fine_label_key)

    project = Project(
        name=name, opencloud_drive_id="drive-1", opencloud_path=f"/{name.replace(' ', '')}"
    )
    session.add(project)
    await session.flush()

    photo = Photo(
        project_id=project.id,
        relative_path=f"{name}/img001.jpg",
        etag=f"etag-{name}",
        content_length=1234,
        taken_at=now,
        last_modified=now,
    )
    scan_run = ScanRun(project_id=project.id, status=ScanStatus.SUCCESS)
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    remote_run = RemoteCategoryClassificationRun(
        project_id=project.id, status=ScanStatus.SUCCESS
    )
    session.add_all([photo, scan_run, scoring_run, remote_run])
    await session.flush()

    criterion_run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(criterion_run)
    await session.flush()

    session.add_all(
        [
            Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.FAVORITE),
            PhotoScore(
                photo_id=photo.id, sharpness=0.8, exposure=0.5, computed_at=now
            ),
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="sharpness",
                value=0.8,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=now,
            ),
            PhotoRanking(
                criterion_scoring_run_id=criterion_run.id,
                photo_id=photo.id,
                cluster_key="cluster-0",
                category_key="landschaft",
                rank_score=0.9,
                rank_position=1,
            ),
            PhotoLandmarkDetection(
                photo_id=photo.id, name="Eiffelturm", confidence=0.9, computed_at=now
            ),
            PhotoFineLabel(
                photo_id=photo.id,
                fine_label_id=fine_label.id,
                raw_label=fine_label.display_name,
                provider="anthropic",
                computed_at=now,
            ),
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="landschaft",
                detected_categories=["landschaft"],
                provider="anthropic",
                computed_at=now,
            ),
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="TimeoutError",
                error_message="zu langsam",
                attempted_at=now,
            ),
        ]
    )
    await session.flush()

    return ProjectGraph(
        project_id=project.id,
        project_name=name,
        photo_id=photo.id,
        photo_etag=photo.etag,
        scan_run_id=scan_run.id,
        scoring_run_id=scoring_run.id,
        criterion_scoring_run_id=criterion_run.id,
        remote_run_id=remote_run.id,
        fine_label_id=fine_label.id,
    )


async def count_rows(session: AsyncSession, table_name: str) -> int:
    """Zeilenzahl einer Tabelle ueber ihren Metadaten-Namen.

    Ueber `Base.metadata` statt ueber die Modellklasse, damit ein Test ueber die aus den
    Metadaten abgeleitete Tabellenmenge iterieren kann, ohne eine eigene Liste zu fuehren."""
    table = Base.metadata.tables[table_name]
    return (await session.execute(select(func.count()).select_from(table))).scalar_one()
