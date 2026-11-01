"""Der Export-Worker (`run_export`): der erste Schreibpfad auf OpenCloud.

Der Fake ist AUFZEICHNEND - welche Schreiboperation mit welchem Zielpfad abgesetzt wurde. Das ist
das erste Mal, dass Tests pruefen, *was wohin* geschrieben wird, nicht nur *was* gelesen (Spec
0263, Teststrategie). Kein Test erreicht ein Netz (bestehende Socket-Sperre in conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    ExportPhoto,
    ExportRun,
    ExportRunStatus,
    FinalSelectionDecision,
    Photo,
    PhotoRanking,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.opencloud.client import Drive, OpenCloudError, _join
from photosort.worker import (
    build_export_folder_name,
    run_export,
    sanitize_project_name,
)
from tests.event_rows import event_id_of_run

DRIVE = Drive(
    id="drive-1",
    name="Family",
    drive_type="project",
    webdav_url="https://cloud.example.com/dav/spaces/drive-1",
)


class RecordingExportClient:
    def __init__(
        self,
        *,
        fail_mkcol: set[str] | None = None,
        fail_copy: set[str] | None = None,
        fail_drive: bool = False,
    ) -> None:
        self.mkcol_calls: list[str] = []
        self.copy_calls: list[tuple[str, str]] = []
        self._fail_mkcol = fail_mkcol or set()
        self._fail_copy = fail_copy or set()
        self._fail_drive = fail_drive

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail_drive:
            raise OpenCloudError("OpenCloud nicht erreichbar")
        return DRIVE

    async def mkcol(self, webdav_url: str, path: str) -> None:
        self.mkcol_calls.append(path)
        if path in self._fail_mkcol:
            raise OpenCloudError("MKCOL fehlgeschlagen")

    async def copy(self, webdav_url: str, source_path: str, dest_url: str) -> None:
        self.copy_calls.append((source_path, dest_url))
        if source_path in self._fail_copy:
            raise OpenCloudError("COPY fehlgeschlagen")


async def _user(session: AsyncSession, username: str) -> User:
    user = User(username=username, password_hash="irrelevant")
    session.add(user)
    await session.flush()
    return user


async def _project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id="drive-1", opencloud_path="/a")
    session.add(project)
    await session.flush()
    return project


async def _successful_run(session: AsyncSession, project: Project) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    return run


async def _photo(session: AsyncSession, project: Project, path: str) -> Photo:
    now = datetime.now(UTC).replace(tzinfo=None)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=now,
        taken_at_original=now,
        last_modified=now,
    )
    session.add(photo)
    await session.flush()
    return photo


async def _propose(session: AsyncSession, run: CriterionScoringRun, photo: Photo) -> None:
    session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=await event_id_of_run(session, run),
            rank_score=0.9,
            rank_position=1,
            selection_position=1,
        )
    )
    await session.flush()


async def _two_users(session: AsyncSession) -> None:
    await _user(session, "first")
    await _user(session, "second")


async def test_export_copies_each_included_photo_to_the_run_folder(db_session: AsyncSession) -> None:
    await _two_users(db_session)
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    a = await _photo(db_session, project, "a.jpg")
    b = await _photo(db_session, project, "b.jpg")
    await _propose(db_session, run, a)
    await _propose(db_session, run, b)
    await db_session.commit()

    client = RecordingExportClient()
    export_run = await run_export(db_session, client, project)

    assert export_run is not None
    assert export_run.status == ExportRunStatus.SUCCESS
    assert export_run.photo_count == 2
    assert export_run.exported_count == 2
    assert export_run.failed_count == 0
    # Wurzel + Lauf-Ordner, genau zweimal.
    assert client.mkcol_calls[0] == "PhotoSort-Export"
    assert client.mkcol_calls[1] == export_run.target_path
    assert client.mkcol_calls[1].startswith("PhotoSort-Export/Costa Rica ")
    # Je Foto ein COPY mit Ziel `Lauf-Ordner/relative_path` (ueber `_join` - Segmente werden
    # quotiert, Leerzeichen zu %20).
    assert {source for source, _ in client.copy_calls} == {"a.jpg", "b.jpg"}
    for source, dest in client.copy_calls:
        assert dest == _join(DRIVE.webdav_url, f"{export_run.target_path}/{source}")


async def test_subfolders_get_one_deduplicated_mkcol_each(db_session: AsyncSession) -> None:
    await _two_users(db_session)
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    # Zwei gleichnamige Basenamen in verschiedenen Unterordnern - kollisionsfrei, je Unterordner
    # genau ein MKCOL.
    one = await _photo(db_session, project, "Tag1/img.jpg")
    two = await _photo(db_session, project, "Tag2/img.jpg")
    nested = await _photo(db_session, project, "Tag1/Unter/img.jpg")
    await _propose(db_session, run, one)
    await _propose(db_session, run, two)
    await _propose(db_session, run, nested)
    await db_session.commit()

    client = RecordingExportClient()
    export_run = await run_export(db_session, client, project)

    assert export_run is not None
    subfolder_mkcols = client.mkcol_calls[2:]
    assert subfolder_mkcols == [
        f"{export_run.target_path}/Tag1",
        f"{export_run.target_path}/Tag2",
        f"{export_run.target_path}/Tag1/Unter",
    ]
    # Drei COPY, keiner ueberschreibt den anderen (Basename-Kollision strukturell ausgeschlossen).
    assert len(client.copy_calls) == 3
    assert len({dest for _, dest in client.copy_calls}) == 3


async def test_a_single_copy_failure_leaves_the_run_success_with_an_error_row(
    db_session: AsyncSession,
) -> None:
    await _two_users(db_session)
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    good = await _photo(db_session, project, "good.jpg")
    bad = await _photo(db_session, project, "bad.jpg")
    await _propose(db_session, run, good)
    await _propose(db_session, run, bad)
    await db_session.commit()

    client = RecordingExportClient(fail_copy={"bad.jpg"})
    export_run = await run_export(db_session, client, project)

    assert export_run is not None
    assert export_run.status == ExportRunStatus.SUCCESS
    assert export_run.exported_count == 1
    assert export_run.failed_count == 1

    rows = list(
        (
            await db_session.execute(
                select(ExportPhoto).where(ExportPhoto.export_run_id == export_run.id)
            )
        ).scalars()
    )
    by_path = {row.relative_path: row for row in rows}
    assert by_path["good.jpg"].error is None
    assert by_path["bad.jpg"].error == "COPY fehlgeschlagen"


async def test_a_fatal_mkcol_failure_fails_the_run(db_session: AsyncSession) -> None:
    await _two_users(db_session)
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    a = await _photo(db_session, project, "a.jpg")
    await _propose(db_session, run, a)
    await db_session.commit()

    client = RecordingExportClient(fail_mkcol={"PhotoSort-Export"})
    export_run = await run_export(db_session, client, project)

    assert export_run is not None
    assert export_run.status == ExportRunStatus.FAILED
    assert export_run.error_message == "MKCOL fehlgeschlagen"
    assert export_run.finished_at is not None


async def test_a_fatal_drive_failure_fails_the_run(db_session: AsyncSession) -> None:
    await _two_users(db_session)
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    a = await _photo(db_session, project, "a.jpg")
    await _propose(db_session, run, a)
    await db_session.commit()

    client = RecordingExportClient(fail_drive=True)
    export_run = await run_export(db_session, client, project)

    assert export_run is not None
    assert export_run.status == ExportRunStatus.FAILED


async def test_an_empty_selection_produces_no_run(db_session: AsyncSession) -> None:
    await _two_users(db_session)
    project = await _project(db_session)
    await _photo(db_session, project, "a.jpg")
    await db_session.commit()

    client = RecordingExportClient()
    export_run = await run_export(db_session, client, project)

    assert export_run is None
    assert client.mkcol_calls == []
    assert client.copy_calls == []
    assert (await db_session.execute(select(ExportRun))).scalars().all() == []


async def test_two_runs_create_two_distinct_folders(db_session: AsyncSession) -> None:
    await _two_users(db_session)
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    a = await _photo(db_session, project, "a.jpg")
    await _propose(db_session, run, a)
    await db_session.commit()

    first = await run_export(db_session, RecordingExportClient(), project)
    second = await run_export(db_session, RecordingExportClient(), project)

    assert first is not None and second is not None
    assert first.target_path != second.target_path
    assert first.target_path is not None and second.target_path is not None
    assert first.target_path.startswith("PhotoSort-Export/Costa Rica ")
    assert second.target_path.startswith("PhotoSort-Export/Costa Rica ")


async def test_the_snapshot_survives_a_source_change(db_session: AsyncSession) -> None:
    """`relative_path` ist beim Anlegen des Laufs eingefroren - eine spaetere Aenderung der Quelle
    laesst den Schnappschuss unveraendert (ADR 0136 Punkt 3)."""
    await _two_users(db_session)
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    a = await _photo(db_session, project, "original.jpg")
    await _propose(db_session, run, a)
    await db_session.commit()

    export_run = await run_export(db_session, RecordingExportClient(), project)
    assert export_run is not None

    a.relative_path = "renamed.jpg"
    await db_session.commit()

    row = (
        await db_session.execute(
            select(ExportPhoto).where(ExportPhoto.export_run_id == export_run.id)
        )
    ).scalar_one()
    assert row.relative_path == "original.jpg"


def test_sanitize_project_name_strips_control_chars_and_slashes() -> None:
    assert sanitize_project_name("Costa\u0007Rica/\u001bUrlaub\\2026") == "CostaRica Urlaub 2026"


def test_sanitize_project_name_empties_a_dot_segment() -> None:
    assert sanitize_project_name("..") == ""
    assert sanitize_project_name(".") == ""


def test_build_export_folder_name_has_no_colon_and_keeps_microseconds() -> None:
    name = build_export_folder_name("Costa Rica", datetime(2026, 11, 1, 12, 0, 0, 123456))

    assert name == "Costa Rica 2026-11-01 12-00-00.123456"
    assert ":" not in name
