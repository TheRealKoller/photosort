"""specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 7: Kameraliste,
Versatz-Endpunkt und Vorschlag.

Der Versatz-Endpunkt ist der HEBEL der Story: ein Aufruf ersetzt `taken_at` ALLER Fotos einer
Kamera und verwirft Events und Rangzeilen des letzten erfolgreichen Laufs. Deshalb steht hier je
Ablehnungsgrund ein Fall, der prueft, dass NICHTS geschrieben wurde - Zeiten, `offset_minutes`
UND Event-Zeilen.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

import photosort
from photosort.cameras import MAX_TIME_OFFSET_MINUTES
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoRanking,
    PhotoScore,
    Project,
    ProjectCamera,
    ScanRun,
    ScanStatus,
    ScoringRun,
)
from tests.time_offset_invariant import assert_time_offset_invariant

_BASE = datetime(2026, 8, 12, 14, 32, 0)


async def _make_project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_camera(
    session: AsyncSession,
    project: Project,
    make: str,
    model: str,
    *,
    offset_minutes: int = 0,
) -> ProjectCamera:
    camera = ProjectCamera(
        project_id=project.id, make=make, model=model, offset_minutes=offset_minutes
    )
    session.add(camera)
    await session.commit()
    await session.refresh(camera)
    return camera


async def _add_photo(
    session: AsyncSession,
    project: Project,
    path: str,
    taken_at_original: datetime,
    *,
    camera: ProjectCamera | None = None,
) -> Photo:
    offset = 0 if camera is None else camera.offset_minutes
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=taken_at_original + timedelta(minutes=offset),
        taken_at_original=taken_at_original,
        camera_id=None if camera is None else camera.id,
        camera_probed=True,
        last_modified=taken_at_original,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _add_successful_run(
    session: AsyncSession, project: Project, photos: list[Photo]
) -> CriterionScoringRun:
    """Ein erfolgreicher Kriterien-Lauf samt Event und je Foto einer Rangzeile - die Grundlage,
    auf der der Versatz-Endpunkt die Gliederung neu aufbaut."""
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    now = datetime.now(UTC).replace(tzinfo=None)
    grouping_event = Event(
        criterion_scoring_run_id=run.id, position=1, started_at=now, ended_at=now
    )
    session.add(grouping_event)
    await session.commit()
    for index, photo in enumerate(photos):
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=100.0,
                exposure=0.0,
                cluster_key="cluster-0",
                computed_at=now,
            )
        )
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo.id,
                event_id=grouping_event.id,
                category_key="nicht_erkannt",
                rank_score=0.5,
                rank_position=index + 1,
                is_primary=True,
            )
        )
    await session.commit()
    return run


async def _reloaded_photo(session: AsyncSession, photo_id: int) -> Photo:
    """Die Foto-Zeile frisch aus der Datenbank.

    Der Endpunkt benutzt DIESELBE Sitzung (Dependency-Override) und committet - danach sind alle
    ORM-Objekte des Tests expired, und schon der Zugriff auf `obj.id` loest einen Lazy-Load
    ausserhalb eines aktiven greenlet-Kontexts aus (`MissingGreenlet`). Deshalb halten die Tests
    unten ihre Ids als einfache `int` fest und laden die Zeile hier neu, statt Handles ueber den
    Aufruf hinweg zu benutzen."""
    photo = await session.get(Photo, photo_id)
    assert photo is not None
    await session.refresh(photo)
    return photo


async def _reloaded_camera(session: AsyncSession, camera_id: int) -> ProjectCamera:
    camera = await session.get(ProjectCamera, camera_id)
    assert camera is not None
    await session.refresh(camera)
    return camera


@contextmanager
def _recorded_select_statements() -> Iterator[list[str]]:
    """Die TATSAECHLICH abgesetzten SELECTs (Muster aus test_project_deletion.py) - eine daneben
    gepflegte Zahl driftete."""
    statements: list[str] = []

    def _listener(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(Engine, "before_cursor_execute", _listener)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", _listener)


class TestTheCameraList:
    async def test_it_lists_the_cameras_sorted_with_their_photo_count(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        nikon = await _add_camera(db_session, project, "Nikon", "Z6")
        canon = await _add_camera(db_session, project, "Canon", "EOS 5D", offset_minutes=-120)
        await _add_photo(db_session, project, "a.jpg", _BASE, camera=canon)
        await _add_photo(db_session, project, "b.jpg", _BASE, camera=canon)
        await _add_photo(db_session, project, "c.jpg", _BASE, camera=nikon)

        response = await authenticated_api_client.get(f"/projects/{project.id}/cameras")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": canon.id,
                "label": "Canon EOS 5D",
                "photo_count": 2,
                "offset_minutes": -120,
            },
            {"id": nikon.id, "label": "Nikon Z6", "photo_count": 1, "offset_minutes": 0},
        ]

    async def test_a_photo_without_a_camera_produces_no_entry_and_no_error(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _add_photo(db_session, project, "ohne.jpg", _BASE)

        response = await authenticated_api_client.get(f"/projects/{project.id}/cameras")

        assert response.status_code == 200
        assert response.json() == []

    async def test_a_camera_without_any_photo_is_listed_with_zero(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der `outerjoin` traegt genau das: eine Kamerazeile, deren Fotos inzwischen von
        OpenCloud verschwunden sind, faellt nicht aus der Liste."""
        project = await _make_project(db_session)
        await _add_camera(db_session, project, "Canon", "EOS 5D")

        response = await authenticated_api_client.get(f"/projects/{project.id}/cameras")

        assert [entry["photo_count"] for entry in response.json()] == [0]

    async def test_the_same_camera_in_two_projects_counts_separately(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """DER Fall, der ein fehlendes `Photo.project_id`-Praedikat im `outerjoin` roetet: ohne
        es zaehlte diese Kamera die Fotos des fremden Projekts mit."""
        first = await _make_project(db_session, "Costa Rica")
        second = await _make_project(db_session, "Norwegen")
        own = await _add_camera(db_session, first, "Canon", "EOS 5D")
        foreign = await _add_camera(db_session, second, "Canon", "EOS 5D")
        await _add_photo(db_session, first, "a.jpg", _BASE, camera=own)
        await _add_photo(db_session, second, "b.jpg", _BASE, camera=foreign)
        await _add_photo(db_session, second, "c.jpg", _BASE, camera=foreign)

        response = await authenticated_api_client.get(f"/projects/{first.id}/cameras")

        assert response.json() == [
            {"id": own.id, "label": "Canon EOS 5D", "photo_count": 1, "offset_minutes": 0}
        ]

    async def test_it_stays_at_one_query_regardless_of_the_camera_count(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        for index in range(5):
            camera = await _add_camera(db_session, project, "Canon", f"EOS {index}")
            await _add_photo(db_session, project, f"p{index}.jpg", _BASE, camera=camera)

        with _recorded_select_statements() as statements:
            response = await authenticated_api_client.get(f"/projects/{project.id}/cameras")

        assert response.status_code == 200
        camera_selects = [s for s in statements if "project_cameras" in s.lower()]
        assert len(camera_selects) == 1, camera_selects

    async def test_an_unknown_project_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        assert (await authenticated_api_client.get("/projects/999/cameras")).status_code == 404


class TestSettingTheTimeOffset:
    async def test_it_shifts_the_photos_of_this_camera_and_leaves_the_others_alone(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        canon = await _add_camera(db_session, project, "Canon", "EOS 5D")
        nikon = await _add_camera(db_session, project, "Nikon", "Z6")
        own_id = (await _add_photo(db_session, project, "a.jpg", _BASE, camera=canon)).id
        other_id = (await _add_photo(db_session, project, "b.jpg", _BASE, camera=nikon)).id
        without_id = (await _add_photo(db_session, project, "c.jpg", _BASE)).id
        project_id, canon_id = project.id, canon.id

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{canon_id}/time-offset",
            json={"offset_minutes": -120},
        )

        assert response.status_code == 200
        assert response.json()["offset_minutes"] == -120
        own = await _reloaded_photo(db_session, own_id)
        assert own.taken_at == _BASE - timedelta(minutes=120)
        assert own.taken_at_original == _BASE
        assert (await _reloaded_photo(db_session, other_id)).taken_at == _BASE
        assert (await _reloaded_photo(db_session, without_id)).taken_at == _BASE
        await assert_time_offset_invariant(db_session, project_id)

    async def test_it_recomputes_from_the_recorded_time_instead_of_accumulating(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """UNTERSAGT ist "Differenz auf den bestehenden Wert addieren" - das kumulierte bei jedem
        weiteren Aufruf und waere nicht zurueckrechenbar."""
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")
        photo_id = (await _add_photo(db_session, project, "a.jpg", _BASE, camera=camera)).id
        project_id, camera_id = project.id, camera.id

        for offset in (-120, -60, 30):
            response = await authenticated_api_client.put(
                f"/projects/{project_id}/cameras/{camera_id}/time-offset",
                json={"offset_minutes": offset},
            )
            assert response.status_code == 200

        stored = await _reloaded_photo(db_session, photo_id)
        assert stored.taken_at_original == _BASE
        assert stored.taken_at == _BASE + timedelta(minutes=30)
        await assert_time_offset_invariant(db_session, project_id)

    async def test_setting_zero_makes_both_times_equal_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D", offset_minutes=-120)
        photo_id = (await _add_photo(db_session, project, "a.jpg", _BASE, camera=camera)).id
        project_id, camera_id = project.id, camera.id

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{camera_id}/time-offset",
            json={"offset_minutes": 0},
        )

        assert response.status_code == 200
        stored = await _reloaded_photo(db_session, photo_id)
        assert stored.taken_at == stored.taken_at_original == _BASE

    async def test_the_same_value_twice_is_idempotent_and_still_rebuilds(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Kein frueher Ausstieg bei unveraendertem Wert: der Neuaufbau laeuft trotzdem und
        vergibt neue Event-Ids - ein Client, der Event-Ids zwischenspeichert, haelt sie nicht
        ueber die Aenderung hinweg."""
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")
        photo = await _add_photo(db_session, project, "a.jpg", _BASE, camera=camera)
        run = await _add_successful_run(db_session, project, [photo])
        project_id, camera_id, photo_id, run_id = project.id, camera.id, photo.id, run.id

        first = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{camera_id}/time-offset",
            json={"offset_minutes": -60},
        )
        events_after_first = await _event_ids(db_session, run_id)
        second = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{camera_id}/time-offset",
            json={"offset_minutes": -60},
        )
        events_after_second = await _event_ids(db_session, run_id)

        assert first.status_code == second.status_code == 200
        assert second.json()["offset_minutes"] == -60
        # Der Neuaufbau laeuft auch beim zweiten, unveraenderten Aufruf: es steht wieder genau
        # ein Event da. Auf DISJUNKTE Ids laesst sich hier nicht pruefen - SQLite vergibt nach
        # einem DELETE dieselben rowids erneut (siehe test_worker_rebuild_run_grouping.py).
        assert len(events_after_first) == len(events_after_second) == 1
        stored = await _reloaded_photo(db_session, photo_id)
        assert stored.taken_at == _BASE - timedelta(minutes=60)

    async def test_it_rebuilds_the_grouping_of_the_last_successful_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")
        photo = await _add_photo(db_session, project, "a.jpg", _BASE, camera=camera)
        run = await _add_successful_run(db_session, project, [photo])
        project_id, camera_id, run_id = project.id, camera.id, run.id

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{camera_id}/time-offset",
            json={"offset_minutes": -60},
        )

        assert response.status_code == 200
        events = (
            (
                await db_session.execute(
                    select(Event).where(Event.criterion_scoring_run_id == run_id)
                )
            )
            .scalars()
            .all()
        )
        # Die Event-Grenzen folgen der KORRIGIERTEN Zeit, ohne eine Zeile Korrekturlogik.
        assert [(e.started_at, e.ended_at) for e in events] == [
            (_BASE - timedelta(minutes=60), _BASE - timedelta(minutes=60))
        ]

    @pytest.mark.parametrize("offset", [MAX_TIME_OFFSET_MINUTES, -MAX_TIME_OFFSET_MINUTES])
    async def test_the_boundary_values_are_accepted(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, offset: int
    ) -> None:
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")

        response = await authenticated_api_client.put(
            f"/projects/{project.id}/cameras/{camera.id}/time-offset",
            json={"offset_minutes": offset},
        )

        assert response.status_code == 200

    @pytest.mark.parametrize("offset", [MAX_TIME_OFFSET_MINUTES + 1, -MAX_TIME_OFFSET_MINUTES - 1])
    async def test_one_minute_beyond_the_boundary_is_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, offset: int
    ) -> None:
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")
        project_id, camera_id = project.id, camera.id

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{camera_id}/time-offset",
            json={"offset_minutes": offset},
        )

        assert response.status_code == 422
        assert (await _reloaded_camera(db_session, camera_id)).offset_minutes == 0

    async def test_an_overflow_writes_absolutely_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`422` OHNE JEDES SCHREIBEN - Zeiten, `offset_minutes` UND Event-Zeilen unveraendert."""
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")
        photo = await _add_photo(
            db_session, project, "a.jpg", datetime(1, 1, 2, 0, 0), camera=camera
        )
        run = await _add_successful_run(db_session, project, [photo])
        project_id, camera_id, photo_id, run_id = project.id, camera.id, photo.id, run.id
        events_before = await _event_ids(db_session, run_id)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{camera_id}/time-offset",
            json={"offset_minutes": -MAX_TIME_OFFSET_MINUTES},
        )

        assert response.status_code == 422
        assert "nichts gespeichert" in response.json()["detail"]
        assert (await _reloaded_photo(db_session, photo_id)).taken_at == datetime(1, 1, 2, 0, 0)
        assert (await _reloaded_camera(db_session, camera_id)).offset_minutes == 0
        assert await _event_ids(db_session, run_id) == events_before

    @pytest.mark.parametrize("run_kind", ["scan", "criterion"])
    async def test_a_running_job_of_this_project_is_a_409_without_any_write(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        run_kind: str,
    ) -> None:
        """Der `409`-Waechter erfasst den Kriterien-Lauf UND DEN SCAN: der Scan schreibt
        `taken_at` ebenfalls und haelt den Versatz je Lauf zwischengespeichert - ohne ihn schriebe
        ein weiterlaufender Scan die Zeiten mit dem ALTEN Versatz zurueck und braeche die
        Invariante still."""
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")
        photo = await _add_photo(db_session, project, "a.jpg", _BASE, camera=camera)
        run = await _add_successful_run(db_session, project, [photo])
        project_id, camera_id, photo_id, run_id = project.id, camera.id, photo.id, run.id
        events_before = await _event_ids(db_session, run_id)
        if run_kind == "scan":
            db_session.add(ScanRun(project_id=project_id, status=ScanStatus.RUNNING))
        else:
            scoring_run = ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS)
            db_session.add(scoring_run)
            await db_session.commit()
            db_session.add(
                CriterionScoringRun(
                    project_id=project_id,
                    scoring_run_id=scoring_run.id,
                    status=ScanStatus.RUNNING,
                    started_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=1),
                )
            )
        await db_session.commit()

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{camera_id}/time-offset",
            json={"offset_minutes": -60},
        )

        assert response.status_code == 409
        assert (await _reloaded_photo(db_session, photo_id)).taken_at == _BASE
        assert (await _reloaded_camera(db_session, camera_id)).offset_minutes == 0
        assert await _event_ids(db_session, run_id) == events_before

    async def test_a_finished_run_does_not_block(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")
        db_session.add(ScanRun(project_id=project.id, status=ScanStatus.SUCCESS))
        await db_session.commit()

        response = await authenticated_api_client.put(
            f"/projects/{project.id}/cameras/{camera.id}/time-offset",
            json={"offset_minutes": -60},
        )

        assert response.status_code == 200

    async def test_a_running_job_of_another_project_does_not_block(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        other = await _make_project(db_session, "Norwegen")
        camera = await _add_camera(db_session, project, "Canon", "EOS 5D")
        db_session.add(ScanRun(project_id=other.id, status=ScanStatus.RUNNING))
        await db_session.commit()

        response = await authenticated_api_client.put(
            f"/projects/{project.id}/cameras/{camera.id}/time-offset",
            json={"offset_minutes": -60},
        )

        assert response.status_code == 200

    async def test_a_camera_of_another_project_is_a_404_without_reflecting_the_value(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Unbekannt und fremd sind DIESELBE Antwort - es entsteht keine Existenzauskunft ueber
        fremde Zeilen, und der Versatz landet nicht in einem fremden Projekt."""
        project = await _make_project(db_session, "Costa Rica")
        other = await _make_project(db_session, "Norwegen")
        foreign = await _add_camera(db_session, other, "Canon", "EOS 5D")
        foreign_photo = await _add_photo(db_session, other, "b.jpg", _BASE, camera=foreign)
        project_id, foreign_id, foreign_photo_id = project.id, foreign.id, foreign_photo.id

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/cameras/{foreign_id}/time-offset",
            json={"offset_minutes": -60},
        )

        assert response.status_code == 404
        assert str(foreign_id) not in response.text
        assert (await _reloaded_camera(db_session, foreign_id)).offset_minutes == 0
        assert (await _reloaded_photo(db_session, foreign_photo_id)).taken_at == _BASE

    async def test_an_unknown_camera_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)

        response = await authenticated_api_client.put(
            f"/projects/{project.id}/cameras/999/time-offset", json={"offset_minutes": -60}
        )

        assert response.status_code == 404


async def _event_ids(session: AsyncSession, run_id: int) -> set[int]:
    session.expire_all()
    return set(
        (await session.execute(select(Event.id).where(Event.criterion_scoring_run_id == run_id)))
        .scalars()
        .all()
    )


class TestTheOffsetSuggestion:
    async def test_it_computes_a_suggestion_without_saving_anything(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        canon = await _add_camera(db_session, project, "Canon", "EOS 5D")
        phone = await _add_camera(db_session, project, "Apple", "iPhone 15")
        camera_photo = await _add_photo(db_session, project, "a.jpg", _BASE, camera=canon)
        reference = await _add_photo(
            db_session, project, "b.jpg", _BASE + timedelta(minutes=120), camera=phone
        )
        project_id, canon_id = project.id, canon.id

        response = await authenticated_api_client.get(
            f"/projects/{project_id}/camera-time-offset-suggestion",
            params={"photo_id": camera_photo.id, "reference_photo_id": reference.id},
        )

        assert response.status_code == 200
        assert response.json() == {
            "camera_id": canon_id,
            "camera_label": "Canon EOS 5D",
            "offset_minutes": 120,
            "photo_taken_at_original": _BASE.isoformat(),
            "reference_taken_at": (_BASE + timedelta(minutes=120)).isoformat(),
        }
        assert (await _reloaded_camera(db_session, canon_id)).offset_minutes == 0

    async def test_the_same_pair_suggests_the_same_value_even_with_an_offset_in_place(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Gerechnet wird auf der AUFGEZEICHNETEN Zeit des Kamerafotos (ADR 0090, Punkt 6) -
        rechnete der Vorschlag auf ihrer korrigierten Zeit, haenge er vom bereits gesetzten
        Versatz ab und ein zweiter Aufruf schluege etwas anderes vor."""
        project = await _make_project(db_session)
        canon = await _add_camera(db_session, project, "Canon", "EOS 5D")
        phone = await _add_camera(db_session, project, "Apple", "iPhone 15")
        camera_photo = await _add_photo(db_session, project, "a.jpg", _BASE, camera=canon)
        reference = await _add_photo(
            db_session, project, "b.jpg", _BASE + timedelta(minutes=120), camera=phone
        )
        params = {"photo_id": camera_photo.id, "reference_photo_id": reference.id}
        project_id, canon_id = project.id, canon.id

        before = await authenticated_api_client.get(
            f"/projects/{project_id}/camera-time-offset-suggestion", params=params
        )
        assert (
            await authenticated_api_client.put(
                f"/projects/{project_id}/cameras/{canon_id}/time-offset",
                json={"offset_minutes": 120},
            )
        ).status_code == 200
        after = await authenticated_api_client.get(
            f"/projects/{project_id}/camera-time-offset-suggestion", params=params
        )

        assert before.json()["offset_minutes"] == after.json()["offset_minutes"] == 120

    async def test_a_camera_photo_without_a_camera_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        phone = await _add_camera(db_session, project, "Apple", "iPhone 15")
        without = await _add_photo(db_session, project, "a.jpg", _BASE)
        reference = await _add_photo(db_session, project, "b.jpg", _BASE, camera=phone)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/camera-time-offset-suggestion",
            params={"photo_id": without.id, "reference_photo_id": reference.id},
        )

        assert response.status_code == 422

    async def test_the_same_camera_on_both_sides_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Differenz zweier Fotos DERSELBEN Kamera ist keine Uhrenabweichung."""
        project = await _make_project(db_session)
        canon = await _add_camera(db_session, project, "Canon", "EOS 5D")
        first = await _add_photo(db_session, project, "a.jpg", _BASE, camera=canon)
        second = await _add_photo(db_session, project, "b.jpg", _BASE, camera=canon)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/camera-time-offset-suggestion",
            params={"photo_id": first.id, "reference_photo_id": second.id},
        )

        assert response.status_code == 422

    async def test_a_result_beyond_the_limits_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        canon = await _add_camera(db_session, project, "Canon", "EOS 5D")
        phone = await _add_camera(db_session, project, "Apple", "iPhone 15")
        camera_photo = await _add_photo(
            db_session, project, "a.jpg", datetime(1, 1, 1), camera=canon
        )
        reference = await _add_photo(
            db_session, project, "b.jpg", datetime(9999, 12, 31), camera=phone
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/camera-time-offset-suggestion",
            params={"photo_id": camera_photo.id, "reference_photo_id": reference.id},
        )

        assert response.status_code == 422

    async def test_a_photo_of_another_project_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        other = await _make_project(db_session, "Norwegen")
        canon = await _add_camera(db_session, project, "Canon", "EOS 5D")
        own = await _add_photo(db_session, project, "a.jpg", _BASE, camera=canon)
        foreign_camera = await _add_camera(db_session, other, "Apple", "iPhone 15")
        foreign = await _add_photo(db_session, other, "b.jpg", _BASE, camera=foreign_camera)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/camera-time-offset-suggestion",
            params={"photo_id": own.id, "reference_photo_id": foreign.id},
        )

        assert response.status_code == 404

    @pytest.mark.parametrize("photo_id", [0, -1, 2_000_000_000])
    async def test_an_out_of_range_photo_id_is_rejected_by_validation(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, photo_id: int
    ) -> None:
        """Die Obergrenze verhindert, dass ein Wert jenseits von 2^63 unter SQLite einen
        OverflowError und damit eine 500 statt einer 404 erzeugt."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/camera-time-offset-suggestion",
            params={"photo_id": photo_id, "reference_photo_id": 1},
        )

        assert response.status_code == 422

    async def test_it_writes_nothing_at_all(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein reiner LESEVORGANG ohne Zustand - kein "vorgeschlagen"-Feld, keine Zeile."""
        project = await _make_project(db_session)
        canon = await _add_camera(db_session, project, "Canon", "EOS 5D")
        phone = await _add_camera(db_session, project, "Apple", "iPhone 15")
        camera_photo = await _add_photo(db_session, project, "a.jpg", _BASE, camera=canon)
        reference = await _add_photo(
            db_session, project, "b.jpg", _BASE + timedelta(minutes=90), camera=phone
        )
        project_id, camera_photo_id = project.id, camera_photo.id

        await authenticated_api_client.get(
            f"/projects/{project_id}/camera-time-offset-suggestion",
            params={"photo_id": camera_photo_id, "reference_photo_id": reference.id},
        )

        assert (
            await db_session.execute(select(func.count()).select_from(Event.__table__))
        ).scalar_one() == 0
        assert (await _reloaded_photo(db_session, camera_photo_id)).taken_at == _BASE
        await assert_time_offset_invariant(db_session, project_id)


# Module, die einen OpenCloud- oder Cloud-Vision-Zugriff ueberhaupt erst moeglich machen.
_NETWORK_MODULES = ("opencloud", "cloud_vision", "landmark", "remote_classification")


def test_the_camera_module_reaches_neither_opencloud_nor_a_cloud_provider() -> None:
    """Akzeptanzkriterium 9: Ein gesetzter Versatz wirkt unmittelbar, OHNE dass die Fotos erneut
    eingelesen werden - ohne jeden OpenCloud-Zugriff und ohne jeden Cloud-Aufruf.

    STRUKTURELL geprueft statt ueber einen Aufrufzaehler: das Modul importiert nichts, womit ein
    solcher Zugriff moeglich waere, und ein Zaehler auf einem nie gebauten Client ist keine
    Zusage. Ein kuenftiger Import wuerde hier auffallen, bevor er einen Aufruf absetzt.

    `rebuild_run_grouping` bleibt erlaubt (und ist der einzige worker-Import): es rechnet
    ausschliesslich aus bereits persistierten Werten."""
    source = (Path(photosort.__file__).resolve().parent / "api" / "cameras.py").read_text(
        encoding="utf-8"
    )
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)

    offenders = sorted(
        name for name in imported for forbidden in _NETWORK_MODULES if f".{forbidden}" in f".{name}"
    )

    assert not offenders, (
        "api/cameras.py erreicht ueber diese Importe einen Netzwerk-/Cloud-Pfad, obwohl der "
        f"Versatz ohne jeden solchen Zugriff wirken muss: {offenders}"
    )
