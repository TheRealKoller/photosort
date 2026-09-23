from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_job_enqueuer, get_opencloud_client
from photosort.config import settings
from photosort.main import app
from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from photosort.opencloud.client import Drive, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry


class FakeOpenCloudClient:
    def __init__(self, fail: OpenCloudError | None = None) -> None:
        self._fail = fail

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail:
            raise self._fail
        return Drive(
            id="drive-1",
            name="Family",
            drive_type="project",
            webdav_url="https://x/dav/spaces/drive-1",
        )

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[DavEntry]:
        if self._fail:
            raise self._fail
        return []


class FakeEnqueuer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any) -> None:
        self.calls.append((function, args))


async def _create_project(
    client: httpx.AsyncClient, name: str = "Costa Rica", path: str = "A"
) -> int:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await client.post("/projects", json={"name": name, "opencloud_path": path})
    result: int = created.json()["id"]
    return result


async def _add_successful_scoring_run(
    session: AsyncSession,
    project_id: int,
    *,
    suggestions_found: int = 1,
    started_at: datetime | None = None,
) -> ScoringRun:
    run = ScoringRun(
        project_id=project_id, status=ScanStatus.SUCCESS, suggestions_found=suggestions_found
    )
    if started_at is not None:
        run.started_at = started_at
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


_PHOTO_MOMENT = datetime(2023, 5, 1, 12, 0, 0, tzinfo=UTC)


async def _add_photo(
    session: AsyncSession,
    project_id: int,
    path: str,
    *,
    open_suggestion: bool = False,
    duplicate_of: int | None = None,
    decision: DuplicateDecision | None = None,
) -> int:
    """Ein Foto mit Bewertungszeile, wahlweise mit offenem Vorschlag und/oder Entscheidungszeile.

    Beide Ursachen sind EINZELN schaltbar, weil der Ausschuss-Bestand des Massenwegs (wie der
    Lesepfad) ihre VEREINIGUNG ist und `has_open_suggestion` nur die Aufnahmen OHNE Zeile trifft."""
    photo = Photo(
        project_id=project_id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=1,
        taken_at=_PHOTO_MOMENT,
        taken_at_original=_PHOTO_MOMENT,
        last_modified=_PHOTO_MOMENT,
    )
    session.add(photo)
    await session.flush()
    session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=100.0,
            exposure=0.0,
            suggested_status=RatingStatus.REJECTED if open_suggestion else None,
            duplicate_of=duplicate_of,
            computed_at=_PHOTO_MOMENT,
        )
    )
    if decision is not None:
        session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=decision))
    await session.flush()
    return photo.id


async def _stored_decision(session: AsyncSession, photo_id: int) -> DuplicateDecision | None:
    return (
        await session.execute(
            select(PhotoDuplicateDecision.decision).where(
                PhotoDuplicateDecision.photo_id == photo_id
            )
        )
    ).scalar_one_or_none()


async def _decision_count(session: AsyncSession) -> int:
    return (
        await session.execute(select(func.count()).select_from(PhotoDuplicateDecision))
    ).scalar_one()


class TestConfirmAusschussGate:
    async def test_requires_auth(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post("/projects/1/confirm-ausschuss-gate")
        assert response.status_code == 401

    async def test_returns_404_for_unknown_project(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.post("/projects/999/confirm-ausschuss-gate")
        assert response.status_code == 404

    async def test_returns_409_without_a_successful_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 409

    async def test_confirms_the_gate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 200
        detail = await authenticated_api_client.get(f"/projects/{project_id}")
        assert detail.json()["last_scoring_run"]["gate_confirmed_at"] is not None

    async def test_a_gate_with_nothing_open_still_confirms(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """AK13 (M1): Der Abschluss ist der EINZIGE Setzer des Zeitstempels - neben dem Autoset
        des Laufs, das nur bei null gefundenen Vorschlaegen greift. Sind alle Vorschlaege einzeln
        entschieden (`open_count == 0`, Zeitstempel noch leer), MUSS der Aufruf ihn setzen: Sonst
        bliebe der Schritt fuer jeden Nutzer unabschliessbar, der zuletzt jedes Bild einzeln
        entschieden hat (AK6), und der naechste Schritt laege dauerhaft hinter einer Wand."""
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)
        einzeln = await _add_photo(
            db_session,
            project_id,
            "einzeln.jpg",
            open_suggestion=True,
            decision=DuplicateDecision.KEEP,
        )
        await db_session.commit()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 200
        detail = await authenticated_api_client.get(f"/projects/{project_id}")
        assert detail.json()["last_scoring_run"]["gate_confirmed_at"] is not None
        # Und die bestehende Zeile bleibt die Handlung des Nutzers (S4).
        assert await _stored_decision(db_session, einzeln) is DuplicateDecision.KEEP

    async def test_is_idempotent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)

        first = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )
        first_detail = await authenticated_api_client.get(f"/projects/{project_id}")
        first_timestamp = first_detail.json()["last_scoring_run"]["gate_confirmed_at"]

        second = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )
        second_detail = await authenticated_api_client.get(f"/projects/{project_id}")

        assert first.status_code == 200
        assert second.status_code == 200
        assert second_detail.json()["last_scoring_run"]["gate_confirmed_at"] == first_timestamp

    async def test_writes_discard_for_every_open_suggestion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """AK9/AK10 (Spec 0525): Die Bestaetigung uebernimmt alle zu diesem Zeitpunkt OFFENEN
        Vorschlaege in einem Zug - die Menge bestimmt der Server aus `has_open_suggestion`.

        Geprueft wird die ZAHL DER ZEILEN, nicht nur der Antwortcode: Eine Umsetzung, die nur den
        Zeitstempel setzt (das Verhalten vor dieser Spec), antwortet ebenfalls `200`."""
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)
        offene = [
            await _add_photo(db_session, project_id, f"offen-{index}.jpg", open_suggestion=True)
            for index in range(3)
        ]
        await db_session.commit()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 200
        assert await _decision_count(db_session) == 3
        for photo_id in offene:
            assert await _stored_decision(db_session, photo_id) is DuplicateDecision.DISCARD

    async def test_leaves_an_already_decided_photo_untouched(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (S4): Eine bestehende Entscheidungszeile bleibt unveraendert - und zwar durch
        die AUSWAHLBEDINGUNG, nicht durch Nachfilterung. Ein `discard` auf eine manuell behaltene
        Aufnahme waere deren stille Ruecknahme; sie verschwaende aus Bewertung und Album, ohne dass
        jemand sie angeruehrt haette.

        Der Fall traegt Vorschlag UND Zeile (die Schnittmenge): Genau dort fiele eine Umsetzung auf,
        die ohne `has_open_suggestion` ueber den Bestand liefe."""
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)
        behalten = await _add_photo(
            db_session,
            project_id,
            "behalten.jpg",
            open_suggestion=True,
            decision=DuplicateDecision.KEEP,
        )
        aussortiert = await _add_photo(
            db_session,
            project_id,
            "aussortiert.jpg",
            open_suggestion=True,
            decision=DuplicateDecision.DISCARD,
        )
        offen = await _add_photo(db_session, project_id, "offen.jpg", open_suggestion=True)
        await db_session.commit()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 200
        assert await _stored_decision(db_session, behalten) is DuplicateDecision.KEEP
        assert await _stored_decision(db_session, aussortiert) is DuplicateDecision.DISCARD
        assert await _stored_decision(db_session, offen) is DuplicateDecision.DISCARD
        assert await _decision_count(db_session) == 3

    async def test_is_idempotent_on_the_decision_rows_too(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """AK11: Der zweite Aufruf ist auch in den ZEILEN idempotent. Ohne `has_open_suggestion`
        schriebe er denselben `discard` erneut - sichtbar waere das kaum, ausser an einem
        Primaerschluessel, der wirft (dann waere es eine `500`)."""
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)
        await _add_photo(db_session, project_id, "offen.jpg", open_suggestion=True)
        await db_session.commit()

        first = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )
        zweite = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert first.status_code == zweite.status_code == 200
        assert await _decision_count(db_session) == 1

    async def test_a_second_run_writes_only_the_then_open_ones(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """AK11 zweite Haelfte: Nach einem NEUEN Lauf sind genau die dann offenen dabei - die alten
        Zeilen ueberleben ihn unangetastet (die Entscheidungstabelle ist keine Lauf-Tabelle). Eine
        Umsetzung, die je Lauf ueberschreibt, holte die manuelle `keep`-Entscheidung hier zurueck auf
        `discard`."""
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)
        gewinner = await _add_photo(db_session, project_id, "gewinner.jpg")
        verlierer = await _add_photo(
            db_session, project_id, "verlierer.jpg", open_suggestion=True, duplicate_of=gewinner
        )
        await db_session.commit()
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        zurueckgenommen = await authenticated_api_client.put(
            f"/projects/{project_id}/photos/{verlierer}/duplicate-decision",
            json={"decision": "keep"},
        )
        assert zurueckgenommen.status_code == 200, "Vorbedingung des Falls: die Handlung greift"
        nachzuegler = await _add_photo(
            db_session, project_id, "nachzuegler.jpg", open_suggestion=True
        )
        await db_session.commit()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 200
        assert await _stored_decision(db_session, verlierer) is DuplicateDecision.KEEP
        assert await _stored_decision(db_session, nachzuegler) is DuplicateDecision.DISCARD
        assert await _decision_count(db_session) == 2

    async def test_never_touches_another_project(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (S1): `has_open_suggestion` traegt selbst KEINE Projektbedingung - sie kommt
        allein aus dem umgebenden Join auf `Photo`. Ohne ihn schriebe ein Aufruf ohne Body `discard`
        ueber ALLE Projekte der Instanz.

        Der stille Schaden waere der groessere: Die fremden Aufnahmen ueberlebten den Ausschuss
        nicht mehr, ohne dass in jenem Projekt je jemand bestaetigt haette."""
        other_id = await _create_project(authenticated_api_client, "Island", "B")
        home_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, home_id)
        await _add_successful_scoring_run(db_session, other_id)
        fremd = await _add_photo(db_session, other_id, "fremd.jpg", open_suggestion=True)
        await _add_photo(db_session, home_id, "eigen.jpg", open_suggestion=True)
        await db_session.commit()

        response = await authenticated_api_client.post(
            f"/projects/{home_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 200
        assert await _decision_count(db_session) == 1
        assert await _stored_decision(db_session, fremd) is None
        fremd_detail = await authenticated_api_client.get(f"/projects/{other_id}")
        assert fremd_detail.json()["last_scoring_run"]["gate_confirmed_at"] is None

    async def test_a_forced_abort_writes_neither_rows_nor_timestamp(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SICHERHEIT (S3): Massenweg und Zeitstempel liegen in EINER Transaktion.

        Ein halb geschriebener Bestand waere eine willkuerliche Teilmenge in der Menge, die den
        Homeserver verlaesst - und ein gesetzter Zeitstempel oeffnete den naechsten Schritt, ohne
        dass die Uebernahme je stattgefunden haette.

        Der Abbruch wird EINGESETZT statt nachgestellt (Muster
        `test_api_duplicate_decisions.py::test_a_concurrent_write_on_the_same_photo_is_a_409_and_never_a_500`):
        Das Fenster zwischen den Anweisungen einer Transaktion ist in einer Testsitzung mit
        derselben Verbindung nicht herstellbar, und der Testgegenstand ist der Zweig, nicht das
        Scheduling. `calls` belegt, dass er betreten wurde - ohne diese Zusicherung bestuende der
        Fall auch gegen eine Umsetzung, die den Schreibweg gar nicht erst betritt."""
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)
        offen = await _add_photo(db_session, project_id, "offen.jpg", open_suggestion=True)
        await db_session.commit()
        calls = {"count": 0}
        original_flush = AsyncSession.flush

        async def _always_failing(self: AsyncSession, *args: object, **kwargs: object) -> None:
            calls["count"] += 1
            raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

        monkeypatch.setattr(AsyncSession, "flush", _always_failing)
        try:
            response = await authenticated_api_client.post(
                f"/projects/{project_id}/confirm-ausschuss-gate"
            )
        finally:
            monkeypatch.setattr(AsyncSession, "flush", original_flush)

        assert calls["count"] >= 1, "der IntegrityError-Zweig wurde gar nicht betreten"
        assert response.status_code == 409
        # Der Rueckzug ist vollstaendig: keine Zeile, kein Zeitstempel.
        assert await _stored_decision(db_session, offen) is None
        assert await _decision_count(db_session) == 0
        detail = await authenticated_api_client.get(f"/projects/{project_id}")
        assert detail.json()["last_scoring_run"]["gate_confirmed_at"] is None

    async def test_a_body_of_ids_is_never_read(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (S2): Der Aufruf bleibt bodyfrei. Eine mitgeschickte Id-Liste wird NIE gelesen -
        die Menge bestimmt allein der Server aus `has_open_suggestion`. Waere sie eine Anweisung,
        waere das ein Massen-Schreibweg auf beliebige Fotos des Projekts."""
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)
        ausserhalb = await _add_photo(db_session, project_id, "ohne-vorschlag.jpg")
        await _add_photo(db_session, project_id, "offen.jpg", open_suggestion=True)
        await db_session.commit()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate", json={"photo_ids": [ausserhalb]}
        )

        assert response.status_code == 200
        assert await _stored_decision(db_session, ausserhalb) is None
        assert await _decision_count(db_session) == 1


class TestClassify:
    async def test_requires_auth(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(
            "/projects/1/classify", json={"scoring_run_id": 1, "use_cloud": False}
        )
        assert response.status_code == 401

    async def test_returns_404_for_unknown_project(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            "/projects/999/classify", json={"scoring_run_id": 1, "use_cloud": False}
        )

        assert response.status_code == 404

    async def test_returns_403_when_feature_flag_disabled(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "category_selection_enabled", False)
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify", json={"scoring_run_id": run.id, "use_cloud": False}
        )

        assert response.status_code == 403

    async def test_returns_409_without_a_successful_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify", json={"scoring_run_id": 1, "use_cloud": False}
        )

        assert response.status_code == 409

    async def test_returns_409_without_a_confirmed_gate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=1)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify", json={"scoring_run_id": run.id, "use_cloud": False}
        )

        assert response.status_code == 409

    async def test_returns_409_for_a_stale_scoring_run_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        stale_run = await _add_successful_scoring_run(
            db_session,
            project_id,
            suggestions_found=0,
            started_at=datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None),
        )
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        # Re-Scan/Re-Scoring waehrend der Kuratierung -> neuer erfolgreicher ScoringRun.
        await _add_successful_scoring_run(
            db_session,
            project_id,
            suggestions_found=0,
            started_at=datetime(2023, 1, 2, tzinfo=UTC).replace(tzinfo=None),
        )
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify",
            json={"scoring_run_id": stale_run.id, "use_cloud": False},
        )

        assert response.status_code == 409

    async def test_enqueues_job_when_gate_confirmed(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify", json={"scoring_run_id": run.id, "use_cloud": False}
        )

        assert response.status_code == 202
        # specs/features/0348-klassifizierungs-transparenz.md, ADR 0068 Punkt 5: das vierte
        # Argument ist die serverseitig berechnete Start-Schaetzung. Ohne Cloud-Nutzung ist sie
        # `None` - nicht `0.0`: ein Lauf ohne Cloud hat keine Kostenschaetzung.
        assert fake_enqueuer.calls == [("classify", (project_id, run.id, False, None))]

    async def test_auto_confirmed_gate_allows_the_request(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Leerer Ausschuss (suggestions_found=0) -> Gate laut Worker automatisch bestaetigt, kein
        # expliziter confirm-ausschuss-gate-Aufruf noetig, um die Klassifizierung zu starten.
        project_id = await _create_project(authenticated_api_client)
        scoring_run = ScoringRun(
            project_id=project_id,
            status=ScanStatus.SUCCESS,
            suggestions_found=0,
        )
        db_session.add(scoring_run)
        await db_session.flush()
        scoring_run.gate_confirmed_at = datetime.now(UTC).replace(tzinfo=None)
        await db_session.commit()
        await db_session.refresh(scoring_run)
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify",
            json={"scoring_run_id": scoring_run.id, "use_cloud": False},
        )

        assert response.status_code == 202

    async def test_enqueues_the_job_with_use_cloud_true(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md: die laufbezogene
        Checkbox wird unveraendert an den Job durchgereicht - sie ist eine Laufeigenschaft, kein
        Projektzustand."""
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        await authenticated_api_client.put(
            f"/projects/{project_id}/cloud-vision-consent", json={"enabled": True}
        )
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify",
            json={"scoring_run_id": run.id, "use_cloud": True},
        )

        assert response.status_code == 202
        # Mit Cloud-Nutzung reicht der Endpunkt die Schaetzung durch. Das Projekt hat hier keine
        # Kandidaten, die Schaetzung ist deshalb `0.0` - "es faellt nichts an", eine BEKANNTE
        # Aussage, im Unterschied zum `None` des lokalen Laufs darueber.
        assert fake_enqueuer.calls == [("classify", (project_id, run.id, True, 0.0))]

    async def test_returns_403_when_cloud_is_requested_without_consent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEITS-MUSS-KRITERIUM (Spec 0296, Security-Abschnitt Bedrohung 1): die Checkbox
        erteilt selbst KEINE Freigabe - ohne projektweite Einwilligung wird ein Cloud-Lauf
        abgewiesen, statt still auf "lokal" herunterzufallen."""
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify",
            json={"scoring_run_id": run.id, "use_cloud": True},
        )

        assert response.status_code == 403
        assert fake_enqueuer.calls == []

    async def test_local_run_is_allowed_without_consent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify",
            json={"scoring_run_id": run.id, "use_cloud": False},
        )

        assert response.status_code == 202

    async def test_use_cloud_is_required(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Kein Default fuer `use_cloud` (api/projects.py::ClassifyRequest): der Client soll sich
        sichtbar entscheiden muessen, statt in eine Voreinstellung zu laufen, die Kosten
        verursacht."""
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify", json={"scoring_run_id": run.id}
        )

        assert response.status_code == 422

    async def test_the_replaced_endpoints_are_gone(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """AC "Ein Ausloeser": die bisherige getrennte Ausloesung entfaellt ersatzlos - es gibt
        keinen zweiten Weg mehr, einen Teil der Klassifizierung zu starten."""
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        score_criteria = await authenticated_api_client.post(
            f"/projects/{project_id}/score-criteria", json={"scoring_run_id": run.id}
        )
        classify_remote = await authenticated_api_client.post(
            f"/projects/{project_id}/classify-categories-remote"
        )
        old_estimate = await authenticated_api_client.get(
            f"/projects/{project_id}/classify-categories-remote/estimate"
        )

        assert score_criteria.status_code == 404
        assert classify_remote.status_code == 404
        assert old_estimate.status_code == 404


class TestProjectOutCriterionScoringRun:
    async def test_has_no_last_criterion_scoring_run_before_any_classify_call(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        detail = await authenticated_api_client.get(f"/projects/{project_id}")

        assert detail.json()["last_criterion_scoring_run"] is None

    async def test_reports_last_criterion_scoring_run_progress(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        scoring_run = await _add_successful_scoring_run(db_session, project_id)
        run = CriterionScoringRun(
            project_id=project_id,
            scoring_run_id=scoring_run.id,
            status=ScanStatus.RUNNING,
            photos_total=10,
            photos_processed=4,
        )
        db_session.add(run)
        await db_session.commit()

        detail = await authenticated_api_client.get(f"/projects/{project_id}")

        last_run = detail.json()["last_criterion_scoring_run"]
        assert last_run["status"] == "running"
        assert last_run["photos_total"] == 10
        assert last_run["photos_processed"] == 4
        # specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md: die drei neuen
        # Felder sind Teil derselben Zusammenfassung - das Frontend braucht sie fuer die
        # Teilschritt-Anzeige und den "ohne Cloud-Anreicherung"-Hinweis.
        assert last_run["phase"] is None
        assert last_run["cloud_requested"] is False
        assert last_run["cloud_error_message"] is None

    async def test_reports_phase_and_cloud_fields_of_a_running_classification(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        scoring_run = await _add_successful_scoring_run(db_session, project_id)
        db_session.add(
            CriterionScoringRun(
                project_id=project_id,
                scoring_run_id=scoring_run.id,
                status=ScanStatus.RUNNING,
                phase=ClassificationPhase.REMOTE_CATEGORIES,
                cloud_requested=True,
            )
        )
        await db_session.commit()

        detail = await authenticated_api_client.get(f"/projects/{project_id}")

        last_run = detail.json()["last_criterion_scoring_run"]
        assert last_run["phase"] == "remote_categories"
        assert last_run["cloud_requested"] is True
