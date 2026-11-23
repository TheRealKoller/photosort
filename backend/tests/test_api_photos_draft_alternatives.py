"""Foto-API: Entwurfsalternativen und ihre Schluessel.
(Aufgeteilt aus test_api_photos.py, Spec 0651.)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    User,
)
from photosort.security import create_access_token
from photosort.selection import BAND_MAX_SERIES, SERIES_GAP
from tests.support.api_photos import (
    _add_ranking,
    _assess_photo,
    _default_event,
    _make_criterion_scoring_run,
    _make_event,
    _make_photo,
    _make_project,
    _make_second_user,
)

# Der EINE Leerkoerper des Alternativen-Endpunkts: jede gescheiterte
# Aufloesung, kein Lauf, fremdes Event - byte-gleich, ohne Rueckspiegelung eines Werts.
_NO_ALTERNATIVES = {
    "items": [],
    "total": 0,
    "offset": 0,
    "reference_index": None,
    "series_rest": 0,
}


class TestDraftAlternatives:
    """Die Alternativen zu EINEM Bild des Entwurfs (ADR 0098 Punkt 5):
    `GET /projects/{id}/draft-alternatives?event_id=…&photo_id=…` liefert die Fotos dieses Events
    im letzten erfolgreichen Lauf ABZUEGLICH des Entwurfs des anfragenden Nutzers - gestrichene
    sind also enthalten, denn genau daraus folgt die Umkehrbarkeit des Austauschs.

    Der Endpunkt ersetzt `GET /projects/{id}/curation-candidates` uebernehmend; dieser Block ist
    dessen umgeschriebener Testblock und behaelt jede seiner Sicherheitszusagen."""

    @staticmethod
    async def _rate(
        session: AsyncSession, photo: Photo, status: RatingStatus, user: User | None = None
    ) -> None:
        """Die eigene Albumentscheidung - ohne `user` die des Nutzers der Client-Fixture."""
        owner = (
            user
            if user is not None
            else (
                await session.execute(select(User).where(User.username == "testuser"))
            ).scalar_one()
        )
        session.add(Rating(photo_id=photo.id, user_id=owner.id, status=status))
        await session.commit()

    @staticmethod
    async def _candidates(
        session: AsyncSession,
        project: Project,
        run: CriterionScoringRun,
        size: int,
        *,
        event: Event | None = None,
        proposed: int = 0,
    ) -> list[Photo]:
        """`size` Fotos mit Rangzeile in EINEM Event, absteigender Qualitaet.

        Die ersten `proposed` gehoeren zum Vorschlag des Laufs (und damit zum Entwurf jedes
        Nutzers, der sie nicht gestrichen hat); die uebrigen sind Alternativen."""
        event_row = await _default_event(session, run) if event is None else event
        photos = []
        for index in range(size):
            photo = await _make_photo(
                session,
                project,
                f"p{index}-{project.id}.jpg",
                datetime(2023, 1, 1, 10, index, tzinfo=UTC),
            )
            await _add_ranking(
                session,
                run,
                photo,
                event=event_row,
                rank_score=1.0 - index / 100,
                rank_position=index + 1,
                selection_position=index + 1 if index < proposed else None,
            )
            photos.append(photo)
        return photos

    async def _get(
        self,
        client: httpx.AsyncClient,
        project: Project,
        **params: object,
    ) -> httpx.Response:
        return await client.get(f"/projects/{project.id}/draft-alternatives", params=params)

    async def test_returns_the_photos_of_the_event_that_are_not_in_the_own_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Regelfall und die Gegenprobe zu jedem Leerfall dieser Klasse: dasselbe Event, das
        unten nichts liefert, liefert hier Eintraege."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 5, proposed=2)

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[0].id,
        )

        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body["items"]] == [p.id for p in photos[2:]]
        assert body["total"] == 3

    async def _ranked(
        self,
        session: AsyncSession,
        project: Project,
        run: CriterionScoringRun,
        event_row: Event,
        name: str,
        quality: float | None,
        *,
        proposed: bool = False,
    ) -> Photo:
        photo = await _make_photo(
            session, project, f"{name}.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        await _add_ranking(
            session,
            run,
            photo,
            event=event_row,
            rank_score=quality,
            rank_position=None if quality is None else 1,
            selection_position=1 if proposed else None,
        )
        return photo

    async def test_without_a_reference_the_order_is_quality_none_last_then_smaller_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Das Hinzufuegen-Feld hat kein Bezugsbild: keine Motivstufe, Qualitaet absteigend,
        `None` zuletzt, Gleichstand ueber die kleinere Id."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        low = await self._ranked(db_session, project, run, event_row, "low", 0.2)
        unrated = await self._ranked(db_session, project, run, event_row, "unrated", None)
        tie_first = await self._ranked(db_session, project, run, event_row, "tie1", 0.5)
        high = await self._ranked(db_session, project, run, event_row, "high", 0.9)
        tie_second = await self._ranked(db_session, project, run, event_row, "tie2", 0.5)

        response = await self._get(authenticated_api_client, project, event_id=event_row.id)

        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [
            high.id,
            tie_first.id,
            tie_second.id,
            low.id,
            unrated.id,
        ]

    async def test_without_a_reference_the_set_is_the_event_minus_the_own_album(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Gestrichene sind enthalten (auch gestrichene vorgeschlagene), eigene Album-Fotos nicht -
        auch nicht unberuehrt vorgeschlagene. Aussortierte (ohne Rangzeile) und Fotos anderer
        Events fehlen; die Bewertung des ANDEREN Nutzers aendert nichts."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        other_event = await _make_event(db_session, run, position=2)
        other_user = await _make_second_user(db_session)

        proposed = await self._ranked(
            db_session, project, run, event_row, "proposed", 0.9, proposed=True
        )
        struck_proposed = await self._ranked(
            db_session, project, run, event_row, "struck-proposed", 0.8, proposed=True
        )
        taken = await self._ranked(db_session, project, run, event_row, "taken", 0.7)
        struck = await self._ranked(db_session, project, run, event_row, "struck", 0.6)
        untouched = await self._ranked(db_session, project, run, event_row, "untouched", 0.5)
        taken_by_other = await self._ranked(db_session, project, run, event_row, "other", 0.4)
        elsewhere = await self._ranked(db_session, project, run, other_event, "elsewhere", 0.95)
        discarded = await _make_photo(
            db_session, project, "discarded.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        await self._rate(db_session, struck_proposed, RatingStatus.REJECTED)
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)
        await self._rate(db_session, struck, RatingStatus.REJECTED)
        await self._rate(db_session, taken_by_other, RatingStatus.ALBUM_WORTHY, other_user)
        await self._rate(db_session, untouched, RatingStatus.REJECTED, other_user)

        response = await self._get(authenticated_api_client, project, event_id=event_row.id)

        body = response.json()
        ids = [item["id"] for item in body["items"]]
        assert ids == [struck_proposed.id, struck.id, untouched.id, taken_by_other.id]
        assert body["total"] == 4
        assert {proposed.id, taken.id, elsewhere.id, discarded.id}.isdisjoint(ids)

    async def test_without_a_reference_a_foreign_event_yields_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S8: Ohne Bezugsbild entfaellt die Sortierung, nie die Bindung - eine `event_id` aus
        einem fremden Projekt ergibt `200` mit leerer Liste UND `total == 0`."""
        project = await _make_project(db_session, name="eigen")
        foreign = await _make_project(db_session, name="fremd")
        await _make_criterion_scoring_run(db_session, project)
        foreign_run = await _make_criterion_scoring_run(db_session, foreign)
        foreign_event = await _default_event(db_session, foreign_run)
        await self._ranked(db_session, foreign, foreign_run, foreign_event, "x", 0.5)

        response = await self._get(authenticated_api_client, project, event_id=foreign_event.id)

        assert response.status_code == 200
        assert response.json() == _NO_ALTERNATIVES

    async def test_without_a_reference_the_second_page_continues_the_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 5)
        event_id = (await _default_event(db_session, run)).id

        first = await self._get(
            authenticated_api_client, project, event_id=event_id, limit=2, offset=0
        )
        second = await self._get(
            authenticated_api_client, project, event_id=event_id, limit=2, offset=2
        )

        assert [item["id"] for item in first.json()["items"]] == [photos[0].id, photos[1].id]
        assert [item["id"] for item in second.json()["items"]] == [photos[2].id, photos[3].id]
        assert second.json()["total"] == 5

    async def test_a_rejected_photo_is_in_the_draft_and_among_the_alternatives(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 2 - EIN Fall fuer beide Endpunkte, nicht zwei.

        Ein gestrichenes Foto des Vorschlags bleibt im Entwurfszweig stehen (mit `rejected` in
        `ratings[]`, Streichen ist ein Anzeigezustand) UND steht zugleich unter den Alternativen
        seines Events - erst daraus folgt, dass ein Austausch umkehrbar ist. Zwei getrennte Faelle
        waeren beide gruen, wenn ein gemeinsamer Helfer eine der beiden Seiten falsch bedient."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 3, proposed=2)
        rejected, kept = photos[0], photos[1]
        await self._rate(db_session, rejected, RatingStatus.REJECTED)

        draft = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")
        alternatives = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=kept.id,
        )

        draft_items = draft.json()["items"]
        assert [item["id"] for item in draft_items] == [rejected.id, kept.id]
        assert [
            r["status"]
            for item in draft_items
            if item["id"] == rejected.id
            for r in item["ratings"]
        ] == ["rejected"]
        assert [item["id"] for item in alternatives.json()["items"]] == [rejected.id, photos[2].id]

    async def test_an_own_taken_photo_is_no_alternative_but_one_taken_by_the_other_user_is(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Abgezogen wird der Entwurf DES ANFRAGENDEN Nutzers. Die Aufnahme des anderen Nutzers
        gehoert nicht dazu - sonst verschwaende sie aus der eigenen Auswahl, ohne dass eine
        Anzeige das benennt (Auflage S6)."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 4, proposed=1)
        other_user = await _make_second_user(db_session)
        await self._rate(db_session, photos[1], RatingStatus.ALBUM_WORTHY)
        await self._rate(db_session, photos[2], RatingStatus.ALBUM_WORTHY, other_user)

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[0].id,
        )

        assert [item["id"] for item in response.json()["items"]] == [photos[2].id, photos[3].id]

    async def test_a_photo_without_a_ranking_row_is_no_alternative(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein im Ausschuss-Schritt aussortiertes Foto hat keine Rangzeile und erscheint deshalb
        nicht unter den Alternativen - auch dann nicht, wenn seine Zeit mitten im Event liegt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 2, proposed=1)
        await _make_photo(
            db_session, project, "ausschuss.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[0].id,
        )

        assert [item["id"] for item in response.json()["items"]] == [photos[1].id]

    async def _timed(
        self,
        session: AsyncSession,
        project: Project,
        run: CriterionScoringRun,
        event_row: Event,
        name: str,
        minute: int,
        quality: float | None = 0.5,
    ) -> Photo:
        """Eine Alternative (nicht vorgeschlagen) zur Minute `minute` nach 10 Uhr."""
        photo = await _make_photo(
            session, project, f"{name}.jpg", datetime(2023, 1, 1, 10, minute, tzinfo=UTC)
        )
        await _add_ranking(
            session,
            run,
            photo,
            event=event_row,
            rank_score=quality,
            rank_position=None if quality is None else 1,
            selection_position=None,
        )
        return photo

    async def _row(
        self, session: AsyncSession, size: int, reference_minute: int
    ) -> tuple[Project, Event, Photo, list[Photo]]:
        """Ein Bezugsbild (vorgeschlagen) und `size` Alternativen, angelegt in UMGEKEHRTER
        Zeitfolge - die Id-Folge ist also nie die Sollreihenfolge. Rueckgabe zeitlich geordnet."""
        project = await _make_project(session)
        run = await _make_criterion_scoring_run(session, project)
        event_row = await _default_event(session, run)
        reference = await _make_photo(
            session, project, "ref.jpg", datetime(2023, 1, 1, 10, reference_minute, tzinfo=UTC)
        )
        await _add_ranking(
            session, run, reference, event=event_row, rank_score=1.0, rank_position=1
        )
        alternatives = [
            await self._timed(session, project, run, event_row, f"t{minute}", minute * 2 + 1)
            for minute in reversed(range(size))
        ]
        return project, event_row, reference, list(reversed(alternatives))

    async def test_with_a_reference_the_order_is_by_time_not_by_motif_or_quality(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Am Endpunkt: Das fruehere, schlechtere Bild ohne gemeinsames Motiv steht vor
        dem spaeteren, besseren mit gemeinsamem Motiv; ein Bild ohne Qualitaet steht zeitlich
        richtig und nicht am Ende. Die Gegenprobe: Die Soll-Folge ist weder die Id- noch die
        Qualitaetsfolge, sonst bestuende der Fall auch ohne jede Sortierung."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        reference = await self._timed(db_session, project, run, event_row, "ref", 30, 1.0)
        await _assess_photo(db_session, reference, strengths={"menschen": 1.0})
        shared_late = await self._timed(db_session, project, run, event_row, "late", 50, 0.9)
        await _assess_photo(db_session, shared_late, strengths={"menschen": 1.0})
        unrated = await self._timed(db_session, project, run, event_row, "unrated", 20, None)
        stranger_early = await self._timed(db_session, project, run, event_row, "early", 5, 0.1)
        await _assess_photo(db_session, stranger_early, strengths={"landschaft": 1.0})

        response = await self._get(
            authenticated_api_client, project, event_id=event_row.id, photo_id=reference.id
        )

        body = response.json()
        order = [item["id"] for item in body["items"]]
        assert order == [stranger_early.id, unrated.id, shared_late.id]
        assert order != sorted(order)
        assert body["reference_index"] == 2
        assert body["offset"] == 0

    async def test_temporal_proximity_now_is_the_sorting_criterion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die frueher geltende Aussage, ins Gegenteil gedreht: Der zeitlich benachbarte,
        schlechtere Kandidat steht VOR dem Stunden entfernten, besseren."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        reference = await self._timed(db_session, project, run, event_row, "ref", 0, 1.0)
        far = await _make_photo(
            db_session, project, "far.jpg", datetime(2023, 1, 1, 15, 0, tzinfo=UTC)
        )
        await _add_ranking(
            db_session,
            run,
            far,
            event=event_row,
            rank_score=0.9,
            rank_position=2,
            selection_position=None,
        )
        near = await self._timed(db_session, project, run, event_row, "near", 1, 0.1)

        response = await self._get(
            authenticated_api_client, project, event_id=event_row.id, photo_id=reference.id
        )

        assert [item["id"] for item in response.json()["items"]] == [near.id, far.id]

    async def test_the_pages_put_together_give_the_order_of_the_full_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ueber Seiten: Seite 1 und Seite 2 aneinandergehaengt ergeben die
        volle Reihe; `reference_index` und `total` sind auf jeder Seite dieselben, `offset` ist
        ohne `series` das angefragte; `series_rest` ist ohne `series` `0`."""
        project, event_row, reference, alternatives = await self._row(db_session, 5, 6)

        async def page(offset: int) -> dict[str, Any]:
            response = await self._get(
                authenticated_api_client,
                project,
                event_id=event_row.id,
                photo_id=reference.id,
                limit=3,
                offset=offset,
            )
            assert response.status_code == 200
            body: dict[str, Any] = response.json()
            return body

        first, second = await page(0), await page(3)

        ids = [item["id"] for item in [*first["items"], *second["items"]]]
        assert ids == [photo.id for photo in alternatives]
        # Minuten 1, 3, 5 liegen vor dem Bezugsbild (Minute 6), 7 und 9 danach.
        assert first["reference_index"] == second["reference_index"] == 3
        assert first["total"] == second["total"] == 5
        assert (first["offset"], second["offset"]) == (0, 3)
        assert first["series_rest"] == second["series_rest"] == 0

    async def test_the_reference_index_at_the_start_the_end_and_in_a_tie(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`reference_index` zaehlt STRIKT kleinere Schluessel - bei gleichem
        `taken_at` genau die kleineren Ids."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        before = await self._timed(db_session, project, run, event_row, "tie-before", 10)
        reference = await self._timed(db_session, project, run, event_row, "ref", 10, 1.0)
        after = await self._timed(db_session, project, run, event_row, "tie-after", 10)
        earliest = await self._timed(db_session, project, run, event_row, "earliest", 0)
        latest = await self._timed(db_session, project, run, event_row, "latest", 20)

        async def index_of(photo: Photo) -> tuple[list[int], int]:
            body = (
                await self._get(
                    authenticated_api_client, project, event_id=event_row.id, photo_id=photo.id
                )
            ).json()
            return [item["id"] for item in body["items"]], body["reference_index"]

        assert await index_of(reference) == ([earliest.id, before.id, after.id, latest.id], 2)
        assert (await index_of(earliest))[1] == 0
        assert (await index_of(latest))[1] == 4

    async def test_a_photo_without_exif_orders_by_its_file_time(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`taken_at` aus `last_modified` (keine EXIF-Zeit) - kein Sonderzweig, das Bild
        steht nach dieser Zeit in der Reihe und nicht am Ende."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        reference = await self._timed(db_session, project, run, event_row, "ref", 0, 1.0)
        later = await self._timed(db_session, project, run, event_row, "later", 30)
        file_time = datetime(2023, 1, 1, 10, 15, tzinfo=UTC)
        without_exif = Photo(
            project_id=project.id,
            relative_path="ohne-exif.jpg",
            etag="etag-1",
            content_length=100,
            taken_at=file_time,
            taken_at_original=file_time,
            last_modified=file_time,
        )
        db_session.add(without_exif)
        await db_session.commit()
        await _add_ranking(
            db_session,
            run,
            without_exif,
            event=event_row,
            rank_score=0.5,
            rank_position=2,
            selection_position=None,
        )

        response = await self._get(
            authenticated_api_client, project, event_id=event_row.id, photo_id=reference.id
        )

        assert [item["id"] for item in response.json()["items"]] == [without_exif.id, later.id]

    async def _series_row(
        self, session: AsyncSession, gaps_seconds: list[int], reference_position: int
    ) -> tuple[Project, Event, Photo, list[Photo]]:
        """Ein Bezugsbild (vorgeschlagen) und Alternativen mit den gegebenen Abstaenden in
        Sekunden; das Bezugsbild steht an `reference_position` der Gesamtfolge. Angelegt in
        umgekehrter Zeitfolge, Rueckgabe zeitlich geordnet (ohne Bezugsbild)."""
        project = await _make_project(session)
        run = await _make_criterion_scoring_run(session, project)
        event_row = await _default_event(session, run)
        start = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        moments = [start]
        for gap in gaps_seconds:
            moments.append(moments[-1] + timedelta(seconds=gap))
        reference: Photo | None = None
        alternatives: list[Photo] = []
        for index in reversed(range(len(moments))):
            photo = await _make_photo(session, project, f"s{index}.jpg", moments[index])
            if index == reference_position:
                await _add_ranking(
                    session, run, photo, event=event_row, rank_score=1.0, rank_position=1
                )
                reference = photo
            else:
                await _add_ranking(
                    session,
                    run,
                    photo,
                    event=event_row,
                    rank_score=0.5,
                    rank_position=1,
                    selection_position=None,
                )
                alternatives.append(photo)
        assert reference is not None
        return project, event_row, reference, list(reversed(alternatives))

    async def _series(
        self, client: httpx.AsyncClient, project: Project, event_row: Event, reference: Photo
    ) -> dict[str, Any]:
        response = await self._get(
            client, project, event_id=event_row.id, photo_id=reference.id, series="true"
        )
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        return body

    async def test_series_cuts_the_window_of_the_recording_series(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Serie endet an der ersten Pause `> SERIES_GAP`; eine Pause von genau `SERIES_GAP`
        gehoert dazu. Marke bei `reference_index - offset`."""
        gap = int(SERIES_GAP.total_seconds())
        # 0 | +gap+1 | 1 2 [ref] 3 4 (Abstand je genau gap) | +gap+1 | 5 6 7
        gaps = [gap + 1, gap, gap, gap, gap, gap + 1, 1, 1]
        project, event_row, reference, alternatives = await self._series_row(db_session, gaps, 3)

        body = await self._series(authenticated_api_client, project, event_row, reference)

        assert [item["id"] for item in body["items"]] == [p.id for p in alternatives[1:5]]
        assert (body["offset"], body["reference_index"], body["total"]) == (1, 3, 8)
        assert body["series_rest"] == 0

    async def test_with_series_the_window_comes_from_the_server_alone(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein mitgeschicktes `offset`/`limit` hat mit `series` keine
        Wirkung - gleiches Fenster, gleiches `offset`, gleiches `series_rest`."""
        project, event_row, reference, _ = await self._series_row(db_session, [1] * 20, 10)
        params = {"event_id": event_row.id, "photo_id": reference.id, "series": "true"}

        plain = await self._get(authenticated_api_client, project, **params)
        steered = await self._get(
            authenticated_api_client, project, **params, offset=999999, limit=200
        )

        assert steered.status_code == 200
        assert steered.json() == plain.json()
        assert len(plain.json()["items"]) == BAND_MAX_SERIES

    async def test_a_long_series_is_capped_with_its_rest(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Serie mit 20 Alternativen: genau `BAND_MAX_SERIES` Bilder, `series_rest` der Rest;
        die Hydratation laedt nur die Ids des Fensters."""
        project, event_row, reference, alternatives = await self._series_row(
            db_session, [1] * 20, 10
        )

        body = await self._series(authenticated_api_client, project, event_row, reference)

        assert len(body["items"]) == BAND_MAX_SERIES
        assert body["series_rest"] == 20 - BAND_MAX_SERIES
        assert body["total"] == 20
        assert 0 <= body["series_rest"] <= body["total"] - len(body["items"])
        assert 0 <= body["offset"] <= body["total"] - len(body["items"])
        offset = body["offset"]
        assert [item["id"] for item in body["items"]] == [
            p.id for p in alternatives[offset : offset + BAND_MAX_SERIES]
        ]

    async def test_a_short_series_is_filled_up_to_four(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        far = int(SERIES_GAP.total_seconds()) + 60
        project, event_row, reference, alternatives = await self._series_row(
            db_session, [far] * 6, 3
        )

        body = await self._series(authenticated_api_client, project, event_row, reference)

        assert [item["id"] for item in body["items"]] == [p.id for p in alternatives[1:5]]
        assert body["series_rest"] == 0

    async def test_a_short_row_is_shown_completely_by_series(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project, event_row, reference, alternatives = await self._row(db_session, 2, 10)

        body = await self._series(authenticated_api_client, project, event_row, reference)

        assert [item["id"] for item in body["items"]] == [photo.id for photo in alternatives]
        assert (body["offset"], body["reference_index"], body["total"]) == (0, 2, 2)
        assert body["series_rest"] == 0

    async def test_a_struck_alternative_counts_in_the_series(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein gestrichenes Foto des Vorschlags ist Alternative und schliesst die Serie."""
        gap = int(SERIES_GAP.total_seconds())
        project, event_row, reference, alternatives = await self._series_row(
            db_session, [1] * 14, 7
        )
        run = await db_session.get(CriterionScoringRun, event_row.criterion_scoring_run_id)
        assert run is not None
        struck = await _make_photo(
            db_session,
            project,
            "struck.jpg",
            alternatives[-1].taken_at + timedelta(seconds=gap),
        )
        await _add_ranking(
            db_session, run, struck, event=event_row, rank_score=0.9, rank_position=1
        )
        await self._rate(db_session, struck, RatingStatus.REJECTED)

        body = await self._series(authenticated_api_client, project, event_row, reference)

        assert body["total"] == 15
        assert body["series_rest"] == 15 - BAND_MAX_SERIES

    async def test_neither_a_draft_photo_nor_a_sorted_out_one_bridges_a_gap(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Datenlage: links und rechts je eine Serie mit mehr als `SERIES_GAP` Abstand, dazwischen
        ein Entwurfsfoto und ein aussortiertes Foto (ohne Rangzeile). Keines davon verbindet."""
        gap = int(SERIES_GAP.total_seconds())
        # Bezugsbild am Ende einer 13er-Serie, dann Luecke 2*gap, dann 5 dichte Bilder.
        gaps = [1] * 13 + [2 * gap] + [1] * 4
        project, event_row, reference, alternatives = await self._series_row(db_session, gaps, 13)
        run = await db_session.get(CriterionScoringRun, event_row.criterion_scoring_run_id)
        assert run is not None
        middle = reference.taken_at + timedelta(seconds=gap)
        in_draft = await _make_photo(db_session, project, "entwurf.jpg", middle)
        await _add_ranking(
            db_session, run, in_draft, event=event_row, rank_score=0.9, rank_position=1
        )
        await _make_photo(db_session, project, "aussortiert.jpg", middle)

        body = await self._series(authenticated_api_client, project, event_row, reference)

        assert body["series_rest"] == 13 - BAND_MAX_SERIES
        assert body["total"] == 18
        assert all(item["id"] != in_draft.id for item in body["items"])

    async def test_a_candidate_of_a_foreign_event_or_older_run_bridges_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Kandidaten eines fremden Events oder eines aelteren Laufs mit `taken_at` in der Luecke
        ueberbruecken nichts und zaehlen nicht in `series_rest` - sonst stuende dort eine
        plausible Zahl zu einer fremden Menge."""
        gap = int(SERIES_GAP.total_seconds())
        gaps = [1] * 13 + [2 * gap] + [1] * 4
        project, event_row, reference, _ = await self._series_row(db_session, gaps, 13)
        run = await db_session.get(CriterionScoringRun, event_row.criterion_scoring_run_id)
        assert run is not None
        middle = reference.taken_at + timedelta(seconds=gap)
        other_event = await _make_event(db_session, run, position=2)
        foreign = await _make_photo(db_session, project, "fremd-event.jpg", middle)
        await _add_ranking(
            db_session,
            run,
            foreign,
            event=other_event,
            rank_score=0.5,
            rank_position=1,
            selection_position=None,
        )
        older_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2000, 1, 1, tzinfo=UTC)
        )
        older = await _make_photo(db_session, project, "aelterer-lauf.jpg", middle)
        # Bewusst mit der Event-Id des AKTUELLEN Laufs: allein das Lauf-Praedikat haelt sie fern.
        await _add_ranking(
            db_session,
            older_run,
            older,
            event=event_row,
            rank_score=0.5,
            rank_position=1,
            selection_position=None,
        )
        before = await self._series(authenticated_api_client, project, event_row, reference)

        assert before["series_rest"] == 13 - BAND_MAX_SERIES
        assert before["total"] == 18

    async def test_another_users_decision_changes_nothing_of_the_own_series(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Eine `album_worthy`-
        oder `rejected`-Entscheidung des ANDEREN aendert keinen Wert der eigenen Antwort."""
        project, event_row, reference, alternatives = await self._series_row(
            db_session, [1] * 20, 10
        )
        other_user = await _make_second_user(db_session)
        await self._rate(db_session, alternatives[0], RatingStatus.ALBUM_WORTHY)
        own_before = await self._series(authenticated_api_client, project, event_row, reference)

        await self._rate(db_session, alternatives[9], RatingStatus.ALBUM_WORTHY, other_user)
        await self._rate(db_session, alternatives[12], RatingStatus.REJECTED, other_user)
        own_after = await self._series(authenticated_api_client, project, event_row, reference)

        assert own_after == own_before
        assert own_before["series_rest"] == 19 - BAND_MAX_SERIES

    async def test_a_resolved_reference_with_an_empty_remainder_stands_at_zero(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Aufgeloestes Bezugsbild, leere Restmenge ergibt
        `reference_index = 0` - zulaessig, denn das Bild sieht der Anfragende ohnehin."""
        project, event_row, reference, _ = await self._row(db_session, 0, 10)

        body = await self._series(authenticated_api_client, project, event_row, reference)

        assert body == {
            "items": [],
            "total": 0,
            "offset": 0,
            "reference_index": 0,
            "series_rest": 0,
        }

    async def test_series_without_a_reference_is_refused(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`series` ohne `photo_id` scheitert laut statt still."""
        project, event_row, _, _ = await self._row(db_session, 3, 10)

        response = await self._get(
            authenticated_api_client, project, event_id=event_row.id, series="true"
        )

        assert response.status_code == 422

    async def test_without_a_reference_there_is_no_reference_index(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ohne `photo_id` ist `reference_index` `null`, `offset` das
        angefragte."""
        project, event_row, _, _ = await self._row(db_session, 3, 10)

        body = (
            await self._get(
                authenticated_api_client, project, event_id=event_row.id, limit=1, offset=1
            )
        ).json()

        assert body["reference_index"] is None
        assert body["offset"] == 1
        assert body["total"] == 3

    async def test_every_failed_resolution_gives_the_same_bytes(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Fremde Id, nie vergebene Id und Foto eines anderen Events ergeben
        byte-gleiche Koerper - auch mit `series`, `offset` und `limit`."""
        project, event_row, reference, _ = await self._row(db_session, 3, 10)
        foreign = await _make_project(db_session, name="fremd")
        foreign_run = await _make_criterion_scoring_run(db_session, foreign)
        foreign_photo = await self._timed(
            db_session,
            foreign,
            foreign_run,
            await _default_event(db_session, foreign_run),
            "fremd",
            10,
        )
        run = await db_session.get(CriterionScoringRun, event_row.criterion_scoring_run_id)
        assert run is not None
        other_event = await _make_event(db_session, run, position=2)

        bodies = set()
        for event_id, photo_id in (
            (event_row.id, foreign_photo.id),
            (event_row.id, reference.id + 4200),
            (other_event.id, reference.id),
        ):
            for extra in ({}, {"series": "true", "offset": 7, "limit": 3}):
                response = await self._get(
                    authenticated_api_client,
                    project,
                    event_id=event_id,
                    photo_id=photo_id,
                    **extra,
                )
                assert response.status_code == 200
                bodies.add(response.content)

        assert len(bodies) == 1
        assert json.loads(bodies.pop()) == _NO_ALTERNATIVES

    async def test_both_users_see_the_same_order_and_their_own_set(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Schluessel enthaelt keinen Nutzer. Gleiche Restmenge ergibt
        dieselbe Folge; nimmt A ein Bild auf, fehlt es nur bei A, die uebrigen behalten ihre
        relative Ordnung. Die Entscheidung des ANDEREN aendert die eigene Antwort nicht."""
        project, event_row, reference, alternatives = await self._row(db_session, 4, 4)
        other_user = await _make_second_user(db_session)
        params = {"event_id": event_row.id, "photo_id": reference.id}

        async def as_other() -> dict[str, Any]:
            own_authorization = authenticated_api_client.headers["Authorization"]
            authenticated_api_client.headers["Authorization"] = (
                f"Bearer {create_access_token(other_user)}"
            )
            try:
                body: dict[str, Any] = (
                    await self._get(authenticated_api_client, project, **params)
                ).json()
            finally:
                authenticated_api_client.headers["Authorization"] = own_authorization
            return body

        def view(body: dict[str, Any]) -> tuple[list[int], int, int, int]:
            ids = [item["id"] for item in body["items"]]
            return ids, body["total"], body["offset"], body["reference_index"]

        own = (await self._get(authenticated_api_client, project, **params)).json()
        assert view(own) == view(await as_other())

        await self._rate(db_session, alternatives[0], RatingStatus.ALBUM_WORTHY)
        await self._rate(db_session, alternatives[3], RatingStatus.REJECTED, other_user)
        own_after = (await self._get(authenticated_api_client, project, **params)).json()
        other_after = await as_other()

        own_ids = [item["id"] for item in own_after["items"]]
        other_ids = [item["id"] for item in other_after["items"]]
        assert own_ids == [photo.id for photo in alternatives[1:]]
        assert other_ids == [photo.id for photo in alternatives]
        assert [i for i in other_ids if i in own_ids] == own_ids
        assert (own_after["reference_index"], other_after["reference_index"]) == (1, 2)
        assert own_after["total"] == 3

    async def test_a_candidate_without_a_quality_score_is_delivered_and_selectable(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein Kandidat ohne Modellbewertung ist ein gueltiger, waehlbarer Zustand: er steht in
        der Antwort und traegt `rank_score: null` statt herauszufallen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        photos = await self._candidates(db_session, project, run, 1, proposed=1)
        unrated = await _make_photo(
            db_session, project, "unrated.jpg", datetime(2023, 1, 1, 10, 9, tzinfo=UTC)
        )
        await _add_ranking(
            db_session,
            run,
            unrated,
            event=event_row,
            rank_score=None,
            rank_position=None,
            selection_position=None,
        )

        response = await self._get(
            authenticated_api_client, project, event_id=event_row.id, photo_id=photos[0].id
        )

        items = response.json()["items"]
        assert [item["id"] for item in items] == [unrated.id]
        assert items[0]["ranking"]["rank_score"] is None

    async def test_total_is_the_remaining_set_and_ignores_limit_and_offset(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`total` ist die RESTMENGE nach Abzug des eigenen Entwurfs und damit unabhaengig von
        `limit`/`offset` - ein aus `len(items)` gebildetes `total` waere auf der ersten Seite
        nicht davon zu unterscheiden. Die ZWEITE Seite ist der Pflichtfall."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 5, proposed=1)
        event_id = (await _default_event(db_session, run)).id

        async def page(limit: int, offset: int) -> tuple[list[int], int]:
            response = await self._get(
                authenticated_api_client,
                project,
                event_id=event_id,
                photo_id=photos[0].id,
                limit=limit,
                offset=offset,
            )
            assert response.status_code == 200
            body = response.json()
            return [item["id"] for item in body["items"]], body["total"]

        assert await page(limit=2, offset=0) == ([photos[1].id, photos[2].id], 4)
        assert await page(limit=2, offset=2) == ([photos[3].id, photos[4].id], 4)

    async def test_empty_without_a_successful_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Erster stiller Rand: 200 mit leerem `PhotoListOut`, kein Fehler."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project, status=ScanStatus.FAILED)
        photos = await self._candidates(db_session, project, run, 3, proposed=1)

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[0].id,
        )

        assert response.status_code == 200
        assert response.json() == _NO_ALTERNATIVES

    async def test_an_unresolvable_photo_id_yields_an_empty_list_without_reflecting_it(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S3: `photo_id` wird AUSSCHLIESSLICH ueber eine Rangzeile desselben Laufs UND
        desselben Events aufgeloest, nie ueber `session.get(Photo, …)`. Scheitert das, ist die
        Antwort 200 mit leerer Liste und `total: 0`, auf demselben Antwortpfad wie eine leere
        Trefferliste - ein abweichender Statuscode oder ein Fehlertext waere ein Existenz-Orakel
        ueber fremde Ids, und die Sortierung haengt allein an diesem Bild."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 3, proposed=1)
        other_event = await _make_event(db_session, run, position=2)

        unknown = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[-1].id + 4200,
        )
        # Dasselbe Foto, aber ein Event, in dem es keine Rangzeile hat: die Aufloesung traegt
        # BEIDE Praedikate, nicht nur das des Laufs.
        wrong_event = await self._get(
            authenticated_api_client,
            project,
            event_id=other_event.id,
            photo_id=photos[0].id,
        )

        for response in (unknown, wrong_event):
            assert response.status_code == 200
            assert response.json() == _NO_ALTERNATIVES
        assert str(photos[-1].id + 4200) not in unknown.text

    async def test_a_photo_of_the_project_without_a_ranking_row_does_not_resolve(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Gegenprobe zu `session.get(Photo, …)`: ein Foto DESSELBEN Projekts, das im Lauf
        keine Rangzeile hat, loest nicht auf - eine Aufloesung ueber die Fototabelle waere hier
        gruen und liesse ein fremdes Bild die eigene Antwort ordnen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        await self._candidates(db_session, project, run, 2, proposed=1)
        unranked = await _make_photo(
            db_session, project, "ohne-rang.jpg", datetime(2023, 1, 1, 10, 7, tzinfo=UTC)
        )

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=unranked.id,
        )

        assert response.status_code == 200
        assert response.json() == _NO_ALTERNATIVES

    async def test_unknown_project_returns_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.get(
            "/projects/9999/draft-alternatives", params={"event_id": 1, "photo_id": 1}
        )

        assert response.status_code == 404

    async def test_requires_authentication(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S1: `api/photos/` verzichtet bewusst auf eine Router-weite Auth-Dependency,
        und `_protected_router_operations()` in `test_auth_guard.py` fuehrt diesen Router nicht -
        fuer ihn gibt es KEIN Vollstaendigkeitsnetz. Ein neuer Endpunkt, der
        `Depends(get_current_user)` vergisst, ist STILL OEFFENTLICH: kein Fehler, keine 401, nur
        Daten. Genau dagegen steht dieser Testfall."""
        project = await _make_project(db_session)

        response = await api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": 1, "photo_id": 1, "series": "true"},
        )

        assert response.status_code == 401

    async def test_keys_of_another_project_return_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 21, erste Haelfte, und Auflage S2: `PhotoRanking` traegt keine
        `project_id`, und `event_id` ist ein globaler Surrogatschluessel - eine Id aus Projekt B
        identifiziert unter `/projects/A/…` eindeutig FREMDE Rangzeilen. Die einzige
        Projektbindung ist `criterion_scoring_run_id` aus dem PFADPARAMETER."""
        own = await _make_project(db_session, name="Eigenes")
        foreign = await _make_project(db_session, name="Fremdes")
        own_run = await _make_criterion_scoring_run(db_session, own)
        foreign_run = await _make_criterion_scoring_run(db_session, foreign)
        await self._candidates(db_session, own, own_run, 2, proposed=1)
        foreign_photos = await self._candidates(db_session, foreign, foreign_run, 4, proposed=1)

        response = await self._get(
            authenticated_api_client,
            own,
            event_id=(await _default_event(db_session, foreign_run)).id,
            photo_id=foreign_photos[0].id,
        )

        body = response.json()
        assert {item["id"] for item in body["items"]}.isdisjoint({p.id for p in foreign_photos})
        # `total` MITGEPRUEFT: eine Zaehlabfrage ohne Lauf-Praedikat lieferte eine plausible Zahl
        # zu einer leeren Liste, und nichts wuerde rot.
        assert body == _NO_ALTERNATIVES

    async def test_only_the_latest_successful_run_is_the_reference(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 21, zweite Haelfte: eine `event_id` aus einem AELTEREN Lauf desselben
        Projekts liefert 200 mit leerer Liste UND `total: 0`."""
        project = await _make_project(db_session)
        old_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC)
        )
        old_photos = await self._candidates(db_session, project, old_run, 3, proposed=1)
        new_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2024, 1, 1, tzinfo=UTC)
        )
        new_event = await _make_event(db_session, new_run, position=1)
        for position, photo in enumerate(old_photos[:2], start=1):
            await _add_ranking(
                db_session,
                new_run,
                photo,
                event=new_event,
                rank_score=1.0 - position / 10,
                rank_position=position,
                selection_position=1 if position == 1 else None,
            )

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, old_run)).id,
            photo_id=old_photos[0].id,
        )

        assert response.status_code == 200
        assert response.json() == _NO_ALTERNATIVES

    async def test_the_replaced_endpoint_is_gone(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`GET /projects/{id}/curation-candidates` entfaellt ERSATZLOS (ADR 0098 Punkt 5). Ohne
        diesen Fall waere sowohl ein vergessener Wegfall als auch ein stehengebliebener
        Uebergangsweg unsichtbar - und zwei Wege auf dieselbe Menge waeren zwei Reihenfolgen."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates", params={"event_id": 1}
        )

        assert response.status_code == 404


class TestDraftAlternativesKeys:
    """Die beiden fremdgesteuerten Id-Parameter des Alternativen-Endpunkts, deklarativ begrenzt
    (Auflage S4) - `event_id` adressiert das Event, `photo_id` das Bezugsbild.

    Umgeschriebener Nachfolger des Blocks, der dieselbe Zusage am Vorgaenger-Endpunkt hielt: dort
    war `event_id` gerade vom Freitextschluessel zur Objekt-Id geworden. Die Mengen- und
    Bindungszusagen stehen in `TestDraftAlternatives`; hier stehen ausschliesslich die Parameter
    selbst."""

    async def _setup(
        self, db_session: AsyncSession, *, photos: int = 3
    ) -> tuple[Project, CriterionScoringRun, Event, list[Photo]]:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1)
        created = []
        for index in range(photos):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1, 10, index, tzinfo=UTC)
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=1.0 - index / 10,
                rank_position=index + 1,
                selection_position=1 if index == 0 else None,
            )
            created.append(photo)
        return project, run, event_row, created

    async def test_the_event_and_the_reference_are_addressed_by_their_ids(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Gegenprobe zu jedem 422 dieser Klasse: mit gueltigen Werten liefert derselbe
        Aufbau Eintraege."""
        project, _run, event_row, photos = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event_row.id, "photo_id": photos[0].id},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    async def test_the_series_cap_stays_below_the_page_cap(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`BAND_MAX_SERIES` deckelt die Hydratation des Bands und bleibt
        unter dem Deckel von `limit` (200); `series=true` ist mit Bezugsbild gueltig."""
        project, _run, event_row, photos = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event_row.id, "photo_id": photos[0].id, "series": "true"},
        )

        assert response.status_code == 200
        assert BAND_MAX_SERIES <= 200

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("2", id="series-zwei"),
            pytest.param("abc", id="series-nicht-bool"),
            pytest.param("", id="series-leer"),
            pytest.param("1.0", id="series-kommazahl"),
        ],
    )
    async def test_series_is_a_strictly_parsed_boolean(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        value: str,
    ) -> None:
        """Ein nicht als Wahrheitswert lesbarer Wert fuer `series` ergibt `422`."""
        project, _run, event_row, photos = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event_row.id, "photo_id": photos[0].id, "series": value},
        )

        assert response.status_code == 422

    async def test_series_false_behaves_like_a_missing_parameter(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project, _run, event_row, photos = await self._setup(db_session)
        params = {"event_id": event_row.id, "photo_id": photos[0].id}

        plain = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives", params=params
        )
        off = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives", params={**params, "series": "false"}
        )

        assert off.status_code == 200
        assert off.json() == plain.json()

    @pytest.mark.parametrize("with_reference", [True, False])
    @pytest.mark.parametrize("value", ["4", "0", "abc", ""])
    async def test_the_retired_nearest_parameter_is_refused(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        with_reference: bool,
        value: str,
    ) -> None:
        """Ein noch nicht aktualisierter Client mit `nearest` scheitert
        laut, statt still die erste Seite der vollen Reihe als Band zu bekommen."""
        project, _run, event_row, photos = await self._setup(db_session)
        params: dict[str, object] = {"event_id": event_row.id, "nearest": value}
        if with_reference:
            params["photo_id"] = photos[0].id

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives", params=params
        )

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "params",
        [
            pytest.param({"event_id": 0}, id="event_id-null"),
            pytest.param({"event_id": -1}, id="event_id-negativ"),
            pytest.param({"event_id": 2**63 + 1}, id="event_id-jenseits-der-obergrenze"),
            pytest.param({"event_id": "cluster-0"}, id="event_id-nicht-numerisch"),
            pytest.param({"photo_id": 0}, id="photo_id-null"),
            pytest.param({"photo_id": -1}, id="photo_id-negativ"),
            pytest.param({"photo_id": 2**63 + 1}, id="photo_id-jenseits-der-obergrenze"),
            pytest.param({"photo_id": "erstes"}, id="photo_id-nicht-numerisch"),
            pytest.param({"offset": -1}, id="negatives-offset"),
            pytest.param({"offset": 2**63}, id="offset-jenseits-der-obergrenze"),
            pytest.param({"limit": 0}, id="limit-unter-der-untergrenze"),
            pytest.param({"limit": 201}, id="limit-ueber-der-obergrenze"),
            pytest.param({"series": "abc"}, id="series-nicht-bool"),
        ],
    )
    async def test_rejects_query_parameters_outside_their_bounds(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        params: dict[str, object],
    ) -> None:
        """Auflage S4: Grenzen an ALLEN vier Parametern, deklarativ und VOR jeder Verwendung.

        `ge=1` plus Typpruefung ist enger als jede `max_length`; ohne Obergrenze erzeugte ein Wert
        jenseits von 2^63 unter SQLite einen `OverflowError` und damit eine 500 statt einer leeren
        Liste. `limit <= 200` deckelt zugleich die schwere Hydratation ueber `photos_by_id` mit
        ihren `selectinload`s. Der bei 422 von FastAPI zurueckgespiegelte Rohwert wird
        ausschliesslich als React-Textknoten gerendert, nie geloggt."""
        project, _run, event_row, photos = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event_row.id, "photo_id": photos[0].id, **params},
        )

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "keys",
        [
            pytest.param((), id="beide-fehlen"),
            pytest.param(("photo_id",), id="event_id-fehlt"),
        ],
    )
    async def test_the_event_key_is_required(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        keys: tuple[str, ...],
    ) -> None:
        """`event_id` ist pflichtig: ohne ihn ist gar kein Event adressiert, und ein Vorgabewert
        waere die stille Wahl irgendeines. `photo_id` ist optional (das Hinzufuegen-Feld hat kein
        Bezugsbild) - siehe `TestDraftAlternatives`."""
        project, _run, event_row, photos = await self._setup(db_session)
        available = {"event_id": event_row.id, "photo_id": photos[0].id}

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={key: available[key] for key in keys},
        )

        assert response.status_code == 422
