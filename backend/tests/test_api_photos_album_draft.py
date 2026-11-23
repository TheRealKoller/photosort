"""Foto-API: der Albumentwurf und das Vorschlags-Flag."""

from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionSource,
    Photo,
    PhotoCriterionScore,
    Rating,
    RatingStatus,
    User,
)
from photosort.security import create_access_token
from tests.support.api_photos import (
    _add_ranking,
    _album_draft,
    _default_event,
    _make_criterion_scoring_run,
    _make_event,
    _make_photo,
    _make_project,
    _make_second_user,
    _own_status,
    _own_user_id,
    _recorded_select_statements,
)

_MEMBERSHIP_TABLE: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "data" / "album_draft_membership.json").read_text(encoding="utf-8")
)["rows"]


class TestTheAlbumDraft:
    """`GET /projects/{id}/album-draft` (ADR 0098, ADR 0130): der Entwurf DES ANFRAGENDEN
    NUTZERS samt Eventliste - `Vorschlag ∪ eigene album_worthy ∪ (eigene rejected ∩ Rangzeile)`.

    Er ist ABGELEITET und nirgends gespeichert; die Auswahlregel selbst ist ein LAUF-ARTEFAKT und
    wird hier nicht wiederholt (tests/test_selection.py)."""

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

    def test_the_case_table_covers_the_full_cross_product(self) -> None:
        """Erst die Vollstaendigkeit, dann die Faelle: Fehlt eine Zeile, prueft niemand sie."""
        keys = [(row["ranking"], row["own"]) for row in _MEMBERSHIP_TABLE]
        assert len(keys) == len(set(keys)) == 9
        assert set(keys) == set(
            itertools.product(
                ("none", "not_proposed", "proposed"), (None, "album_worthy", "rejected")
            )
        )
        for row in _MEMBERSHIP_TABLE:
            assert row["other"] in ("album_worthy", "rejected")
            assert row["membership"] in ("out", "album", "struck")

    @pytest.mark.parametrize(
        "row", _MEMBERSHIP_TABLE, ids=lambda row: f"{row['ranking']}-{row['own']}"
    )
    async def test_each_row_of_the_case_table(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        row: dict[str, Any],
    ) -> None:
        """Je Zeile die Lage samt Gegenbewertung des ANDEREN Nutzers: Eine Umsetzung ohne
        Nutzerbedingung im neuen Zweig (S2) liesse dessen Streichung als eigene erscheinen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 10, 0),
        )
        photo = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 9, 0, tzinfo=UTC)
        )
        if row["ranking"] != "none":
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=0.5,
                rank_position=1,
                selection_position=1 if row["ranking"] == "proposed" else None,
            )
        if row["own"] is not None:
            await self._rate(db_session, photo, RatingStatus(row["own"]))
        await self._rate(
            db_session, photo, RatingStatus(row["other"]), await _make_second_user(db_session)
        )

        body = await _album_draft(authenticated_api_client, project)

        items = {item["id"]: item for item in body["items"]}
        own_id = _own_user_id(authenticated_api_client)
        if row["membership"] == "out":
            assert photo.id not in items
        else:
            assert photo.id in items
            assert (_own_status(items[photo.id], own_id) == "rejected") == (
                row["membership"] == "struck"
            )

    async def test_a_run_with_events_but_no_proposal_lists_every_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Eventliste ist die des Laufs, nicht die der Fotos: Events ohne Vorschlag stehen
        darin, in der Reihenfolge ihrer `position` - auch wenn sie anders angelegt wurden."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        third = await _make_event(db_session, run, position=3, place_name="Drei")
        first = await _make_event(db_session, run, position=1)
        second = await _make_event(db_session, run, position=2)

        body = await _album_draft(authenticated_api_client, project)

        assert body["items"] == []
        assert [event_row["id"] for event_row in body["events"]] == [first.id, second.id, third.id]
        assert body["events"][2]["place_name"] == "Drei"
        assert set(body["events"][0]) == {
            "id",
            "position",
            "started_at",
            "ended_at",
            "place",
            "place_name",
        }

    async def test_the_number_of_selects_does_not_depend_on_the_number_of_events(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S14: die Events werden EINMAL geladen - eine Abfrage je Event fiele hier auf."""
        few = await _make_project(db_session, name="wenige")
        many = await _make_project(db_session, name="viele")
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for project, count in ((few, 1), (many, 8)):
            run = await _make_criterion_scoring_run(db_session, project)
            for position in range(1, count + 1):
                event_row = await _make_event(db_session, run, position=position)
                photo = await _make_photo(
                    db_session, project, f"{project.name}-{position}.jpg", base
                )
                await _add_ranking(
                    db_session, run, photo, event=event_row, rank_score=0.5, rank_position=1
                )

        with _recorded_select_statements() as few_statements:
            few_body = await _album_draft(authenticated_api_client, few)
        with _recorded_select_statements() as many_statements:
            many_body = await _album_draft(authenticated_api_client, many)

        assert (len(few_body["events"]), len(many_body["events"])) == (1, 8)
        assert len(many_body["items"]) == 8
        assert len(few_statements) == len(many_statements)

    async def test_a_rejection_in_the_photo_grid_shows_as_struck_only_with_a_ranking_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Verwerfung aus dem Bildbestand (`PUT /photos/{id}/rating`) ist dieselbe Zeile wie
        das Streichen: Mit Rangzeile im Lauf steht das Foto als gestrichen in der Antwort, ein
        aussortiertes Foto ohne Rangzeile bleibt draussen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 10, 0),
        )
        ranked = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 8, 30, tzinfo=UTC)
        )
        discarded = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 9, 30, tzinfo=UTC)
        )
        await _add_ranking(
            db_session,
            run,
            ranked,
            event=event_row,
            rank_score=0.5,
            rank_position=1,
            selection_position=None,
        )
        for photo in (ranked, discarded):
            response = await authenticated_api_client.put(
                f"/photos/{photo.id}/rating", json={"status": "rejected"}
            )
            assert response.status_code == 200

        body = await _album_draft(authenticated_api_client, project)

        assert [item["id"] for item in body["items"]] == [ranked.id]
        assert _own_status(body["items"][0], _own_user_id(authenticated_api_client)) == "rejected"

    async def test_a_struck_photo_of_another_project_never_enters(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S2: Die Projektbindung steht AUSSERHALB der Vereinigung, die Rangzeile am Lauf DIESES
        Projekts. Ein im fremden Projekt gestrichenes Foto mit Rangzeile im fremden Lauf erfuellt
        den dritten Zweig dort - hier darf es nicht erscheinen."""
        project = await _make_project(db_session, name="eigen")
        foreign = await _make_project(db_session, name="fremd")
        own_run = await _make_criterion_scoring_run(db_session, project)
        foreign_run = await _make_criterion_scoring_run(db_session, foreign)
        await _make_event(db_session, own_run)
        foreign_photo = await _make_photo(
            db_session, foreign, "x.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        await _add_ranking(db_session, foreign_run, foreign_photo, rank_score=0.5, rank_position=1)
        await self._rate(db_session, foreign_photo, RatingStatus.REJECTED)

        body = await _album_draft(authenticated_api_client, project)

        assert body["items"] == []

    @pytest.mark.parametrize("value", ["true", "false"])
    async def test_the_old_draft_mode_fails_loudly_in_both_settings(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, value: str
    ) -> None:
        """S3: Ein noch nicht ersetzter Client fiele mit `draft=true` sonst still in den
        Listing-Zweig und zeigte den vollen Bestand als Entwurf."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": value}
        )

        assert response.status_code == 422

    async def test_the_order_holds_with_struck_photos_in_between(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`(events.position, taken_at, id)` gilt fuer die ganze Antwort - ein gestrichenes Foto
        steht an seiner zeitlichen Stelle, nicht am Ende seines Events."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        later_event = await _make_event(db_session, run, position=2)
        earlier_event = await _make_event(db_session, run, position=1)
        same_moment = datetime(2023, 1, 2, 9, 0, tzinfo=UTC)
        struck_late = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 3, tzinfo=UTC)
        )
        tie_struck = await _make_photo(db_session, project, "b.jpg", same_moment)
        early = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        tie_kept = await _make_photo(db_session, project, "d.jpg", same_moment)
        in_later = await _make_photo(db_session, project, "e.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        for photo, event_row, position, proposed in (
            (struck_late, earlier_event, 1, False),
            (tie_struck, earlier_event, 2, True),
            (early, earlier_event, 3, True),
            (tie_kept, earlier_event, 4, True),
            (in_later, later_event, 1, True),
        ):
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=0.5,
                rank_position=position,
                selection_position=position if proposed else None,
            )
        await self._rate(db_session, struck_late, RatingStatus.REJECTED)
        await self._rate(db_session, tie_struck, RatingStatus.REJECTED)

        body = await _album_draft(authenticated_api_client, project)

        assert tie_struck.id < tie_kept.id
        assert [item["id"] for item in body["items"]] == [
            early.id,
            tie_struck.id,
            tie_kept.id,
            struck_late.id,
            in_later.id,
        ]

    async def test_requires_authentication(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S1: `api/photos/` hat kein Vollstaendigkeitsnetz - ein vergessenes
        `Depends(get_current_user)` machte den Entwurf still oeffentlich."""
        project = await _make_project(db_session)

        response = await api_client.get(f"/projects/{project.id}/album-draft")

        assert response.status_code == 401

    async def test_unknown_project_returns_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.get("/projects/9999/album-draft")

        assert response.status_code == 404

    @pytest.mark.parametrize("project_id", ["0", "-1", "1000000001"])
    async def test_the_project_id_is_bounded(
        self, authenticated_api_client: httpx.AsyncClient, project_id: str
    ) -> None:
        response = await authenticated_api_client.get(f"/projects/{project_id}/album-draft")

        assert response.status_code == 422

    async def test_returns_the_drafted_photos_with_ranking_details(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        third = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 3, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, second, rank_score=0.5, rank_position=2)
        # Bewertet, im einsehbaren Vorrat - aber nicht im Vorschlag und nicht aufgenommen.
        await _add_ranking(
            db_session, run, third, rank_score=0.1, rank_position=3, selection_position=None
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body["items"]] == [first.id, second.id]
        ranking = body["items"][0]["ranking"]
        # partition_size ist die GROESSE DER GESAMTEN Partition (hier 3 Fotos), nicht die des
        # Entwurfs - "Rang M von N" soll immer den vollen Pool zeigen (Spec 0040).
        assert ranking == {
            "event_id": (await _default_event(db_session, run)).id,
            "rank_score": 0.9,
            "rank_position": 1,
            "proposed": True,
            "partition_size": 3,
            # Im Entwurfsmodus traegt jedes gelieferte Foto seinen Platz in der ANGEZEIGTEN
            # Auswahl seines Events - lueckenlos ab 1 ueber die gelieferte Reihenfolge.
            "curation_position": 1,
        }

    async def test_a_proposed_and_taken_photo_appears_exactly_once(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 1: Der Entwurf ist eine VEREINIGUNG, keine Verkettung. Ein Foto, das der
        Lauf vorschlaegt UND das der Nutzer aufgenommen hat, erfuellt beide Bedingungen - eine
        Implementierung, die zwei Mengen aneinanderhaengt, liefert es zweimal, und die Ansicht
        zeigte dieselbe Kachel doppelt, ohne dass irgendetwas rot wuerde."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        both = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, both, rank_score=0.9, rank_position=1)
        await self._rate(db_session, both, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        body = response.json()
        assert [item["id"] for item in body["items"]] == [both.id]

    async def test_a_taken_photo_without_a_proposal_joins_the_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        proposed = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        taken = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, proposed, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, taken, rank_score=0.1, rank_position=2, selection_position=None
        )
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        items = {item["id"]: item for item in response.json()["items"]}
        assert set(items) == {proposed.id, taken.id}
        # Zwei Herkuenfte, EIN Anzeigezustand - unterscheidbar allein ueber `proposed`.
        assert items[proposed.id]["ranking"]["proposed"] is True
        assert items[taken.id]["ranking"]["proposed"] is False

    async def test_a_rejected_photo_that_was_never_proposed_stands_as_struck_only_with_ranking(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der fehlende Ablehnungsfilter darf nicht zum fehlenden Filter werden: Ein gestrichenes
        Foto mit Rangzeile im Lauf steht als gestrichen in der Antwort, auch wenn es nie
        vorgeschlagen war; eines ohne Rangzeile bleibt draussen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        proposed = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        rejected = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        unranked = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, proposed, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, rejected, rank_score=0.1, rank_position=2, selection_position=None
        )
        await self._rate(db_session, rejected, RatingStatus.REJECTED)
        await self._rate(db_session, unranked, RatingStatus.REJECTED)

        body = await _album_draft(authenticated_api_client, project)

        assert [item["id"] for item in body["items"]] == [proposed.id, rejected.id]
        assert [r["status"] for r in body["items"][1]["ratings"]] == ["rejected"]

    async def test_only_untouched_places_follow_the_new_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 3: „Nur unangefasste Plaetze werden neu befuellt" ist erst ueber ZWEI Laeufe
        sichtbar, und die drei Fotos gehoeren in EINEN Fall - getrennt geschrieben bestuenden die
        Haelften auch bei einer Implementierung, die immer oder nie den neuen Lauf gewinnen
        laesst.

        Lauf 1 schlaegt `dropped` vor, sonst nichts. Der Nutzer streicht `dropped` und nimmt
        `taken` auf. Lauf 2 schlaegt danach `untouched` NEU vor und `dropped` ERNEUT - und genau
        das ist der Pruefstein: Der unangefasste Platz folgt dem neuen Lauf, die beiden
        angefassten behalten ihre Entscheidung, statt sich vom neuen Vorschlag zurueckstellen zu
        lassen."""
        project = await _make_project(db_session)
        first_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 5, 1, 10, 0)
        )
        untouched = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC)
        )
        dropped = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        taken = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 3, tzinfo=UTC))
        await _add_ranking(db_session, first_run, dropped, rank_score=0.9, rank_position=1)
        for photo, position in ((untouched, 2), (taken, 3)):
            await _add_ranking(
                db_session,
                first_run,
                photo,
                rank_score=1.0 - position / 10,
                rank_position=position,
                selection_position=None,
            )

        await self._rate(db_session, dropped, RatingStatus.REJECTED)
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)

        before = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")
        # Nach Lauf 1: das Vorgeschlagene (gestrichen, als Anzeigezustand) und das Aufgenommene.
        assert [item["id"] for item in before.json()["items"]] == [dropped.id, taken.id]

        second_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 5, 2, 10, 0)
        )
        second_event = await _make_event(db_session, second_run, position=1)
        for photo, position in ((untouched, 1), (dropped, 2)):
            await _add_ranking(
                db_session,
                second_run,
                photo,
                event=second_event,
                rank_score=1.0 - position / 10,
                rank_position=position,
                selection_position=position,
            )
        # Lauf 2 fuehrt das Aufgenommene nur noch als Kandidaten - es bleibt trotzdem im Entwurf.
        await _add_ranking(
            db_session,
            second_run,
            taken,
            event=second_event,
            rank_score=0.1,
            rank_position=3,
            selection_position=None,
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        items = {item["id"]: item for item in response.json()["items"]}
        assert set(items) == {untouched.id, dropped.id, taken.id}
        # Der unangefasste Platz folgt Lauf 2 - vorher war er nicht dabei.
        assert untouched.id not in {item["id"] for item in before.json()["items"]}
        assert items[untouched.id]["ranking"]["proposed"] is True
        assert items[untouched.id]["ratings"] == []
        # Das Gestrichene bleibt gestrichen, obwohl Lauf 2 es erneut vorschlaegt - der neue
        # Vorschlag setzt keine getroffene Entscheidung zurueck.
        assert items[dropped.id]["ranking"]["proposed"] is True
        assert [r["status"] for r in items[dropped.id]["ratings"]] == ["rejected"]
        # Das Aufgenommene bleibt, obwohl Lauf 2 es nicht mehr vortraegt.
        assert items[taken.id]["ranking"]["proposed"] is False
        assert [r["status"] for r in items[taken.id]["ratings"]] == ["album_worthy"]

    async def test_the_order_is_event_position_then_taken_at_then_photo_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 4: Der Sortierschluessel muss TOTAL sein - ein unvollstaendiges `ORDER BY`
        ist unter SQLite zufaellig stabil und unter Postgres nicht.

        Die Zeilen werden in GESCHUETTELTER Reihenfolge eingefuegt, das spaeter angelegte Event
        steht chronologisch VOR dem frueher angelegten, und zwei Fotos teilen sich dieselbe
        Aufnahmezeit (der Gleichstand, den erst die `photo_id` bricht). Geprueft wird die
        VOLLSTAENDIGE Id-Folge, nicht bloss die Mitgliedschaft."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        later_event = await _make_event(db_session, run, position=2)
        earlier_event = await _make_event(db_session, run, position=1)

        same_moment = datetime(2023, 1, 2, 9, 0, tzinfo=UTC)
        # Anlagereihenfolge: absichtlich weder die Soll- noch die Zeitreihenfolge.
        late_in_later = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 5, tzinfo=UTC)
        )
        tie_second = await _make_photo(db_session, project, "b.jpg", same_moment)
        early_in_earlier = await _make_photo(
            db_session, project, "c.jpg", datetime(2023, 1, 1, tzinfo=UTC)
        )
        tie_first = await _make_photo(db_session, project, "d.jpg", same_moment)
        early_in_later = await _make_photo(
            db_session, project, "e.jpg", datetime(2023, 1, 4, tzinfo=UTC)
        )

        for photo, event_row, position in (
            (late_in_later, later_event, 1),
            (tie_second, earlier_event, 2),
            (early_in_earlier, earlier_event, 3),
            (tie_first, earlier_event, 4),
            (early_in_later, later_event, 5),
        ):
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=1.0 - position / 10,
                rank_position=position,
                selection_position=position,
            )

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        # Der Gleichstand bricht ueber die kleinere `photo_id` - `tie_first` wurde VOR
        # `tie_second` angelegt und traegt deshalb die kleinere Id.
        assert tie_first.id > tie_second.id
        assert [item["id"] for item in response.json()["items"]] == [
            early_in_earlier.id,
            tie_second.id,
            tie_first.id,
            early_in_later.id,
            late_in_later.id,
        ]

    async def test_the_order_inside_an_event_is_chronological_not_the_selection_position(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Aufbau laesst Vorschlagsplatz und Aufnahmezeit AUSEINANDERFALLEN: das zeitlich
        fruehere Foto steht auf Platz 2 des Vorschlags. Nach `selection_position` sortiert stuende
        die Liste umgekehrt - und ein aufgenommenes Bild ohne Platz stets am Gruppenende, statt
        an seiner Stelle."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        early = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        late = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(
            db_session, run, late, rank_score=0.9, rank_position=1, selection_position=1
        )
        await _add_ranking(
            db_session, run, early, rank_score=0.2, rank_position=2, selection_position=2
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        items = response.json()["items"]
        assert [item["id"] for item in items] == [early.id, late.id]
        # `curation_position` numeriert die GELIEFERTE Reihenfolge des Events, lueckenlos ab 1 -
        # nicht die `selection_position` und nicht die `rank_position`.
        assert [item["ranking"]["curation_position"] for item in items] == [1, 2]
        assert [item["ranking"]["rank_position"] for item in items] == [2, 1]

    async def test_a_taken_photo_without_a_ranking_row_is_placed_by_its_time(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein im Ausschuss-Schritt aussortiertes Foto hat NIE eine Rangzeile bekommen. Nimmt der
        Nutzer es im Raster auf, erscheint es trotzdem im Entwurf - eingeordnet ueber
        `events.py::event_for_time`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 9, 0),
        )
        second_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 1, 14, 0),
            ended_at=datetime(2023, 1, 1, 15, 0),
        )
        anchor = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 8, 30, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, anchor, event=first_event, rank_score=0.9, rank_position=1
        )
        # Nie bewertet, nie eingeordnet - aber vom Nutzer aufgenommen.
        discarded = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 14, 30, tzinfo=UTC)
        )
        await self._rate(db_session, discarded, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        items = {item["id"]: item for item in response.json()["items"]}
        assert set(items) == {anchor.id, discarded.id}
        assert items[discarded.id]["event"]["id"] == second_event.id
        # Ohne Rangzeile gibt es keine Rangaussage - und ausdruecklich keinen erfundenen Platz.
        assert items[discarded.id]["ranking"] is None

    async def test_the_time_assignment_reads_the_corrected_taken_at(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 13: Ein gesetzter Kameraversatz ist der einzige Fall, der `taken_at` von
        `taken_at_original` trennt. Die Zuordnung liest die KORRIGIERTE Zeit - die aufgezeichnete
        zeigte hier auf das erste Event."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 9, 0),
        )
        second_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 1, 14, 0),
            ended_at=datetime(2023, 1, 1, 15, 0),
        )
        anchor = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 8, 30, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, anchor, event=first_event, rank_score=0.9, rank_position=1
        )
        shifted = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 8, 40, tzinfo=UTC)
        )
        # Zonenlos wie die Spalte selbst - `taken_at_original` bleibt bei 8:40 stehen.
        shifted.taken_at = datetime(2023, 1, 1, 14, 40)
        await db_session.commit()
        await self._rate(db_session, shifted, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[shifted.id]["event"]["id"] == second_event.id

    async def test_the_ranking_row_beats_the_time_assignment(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 14: Ordnet der neue Lauf ein aufgenommenes Foto einem ANDEREN Event zu,
        steht es dort - nicht dort, wohin seine Zeit zeigte."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 9, 0),
        )
        second_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 1, 14, 0),
            ended_at=datetime(2023, 1, 1, 15, 0),
        )
        # Die Zeit zeigt mitten in das ZWEITE Event, die Rangzeile sagt das ERSTE.
        moved = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 14, 30, tzinfo=UTC)
        )
        await _add_ranking(
            db_session,
            run,
            moved,
            event=first_event,
            rank_score=0.9,
            rank_position=1,
            selection_position=None,
        )
        await self._rate(db_session, moved, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        [item] = response.json()["items"]
        assert item["event"]["id"] == first_event.id
        assert item["event"]["id"] != second_event.id

    async def test_the_time_assignment_costs_no_query_per_photo(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S14: Die Zuordnung der rangzeilenlosen Fotos laeuft in EINEM Durchgang ueber die
        einmal geladene Eventliste. Ein N+1-Muster erzeugte hier eine Abfrage je aufgenommenem
        Foto oder je Event - der Unterschied zwischen einer Handvoll Abfragen und mehreren
        tausend, ausgeloest durch normale Benutzung, ohne dass ein Parameter das begrenzte. Das
        grosse Projekt hat deshalb auch mehr Events."""
        small = await _make_project(db_session, name="klein")
        large = await _make_project(db_session, name="gross")
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for project, count in ((small, 2), (large, 20)):
            run = await _make_criterion_scoring_run(db_session, project)
            anchor = await _make_photo(db_session, project, f"{project.name}-anchor.jpg", base)
            await _add_ranking(db_session, run, anchor, rank_score=0.9, rank_position=1)
            if project is large:
                for position in range(2, 8):
                    await _make_event(
                        db_session,
                        run,
                        position=position,
                        started_at=datetime(2024, 1, position, 10, 0),
                        ended_at=datetime(2024, 1, position, 11, 0),
                    )
            for index in range(count):
                photo = await _make_photo(
                    db_session,
                    project,
                    f"{project.name}-{index}.jpg",
                    base + timedelta(minutes=index + 1),
                )
                await self._rate(db_session, photo, RatingStatus.ALBUM_WORTHY)

        with _recorded_select_statements() as small_statements:
            small_response = await authenticated_api_client.get(f"/projects/{small.id}/album-draft")
        with _recorded_select_statements() as large_statements:
            large_response = await authenticated_api_client.get(f"/projects/{large.id}/album-draft")

        assert len(small_response.json()["items"]) == 3
        assert len(large_response.json()["items"]) == 21
        assert len(small_statements) == len(large_statements)

    async def test_every_event_of_the_draft_is_represented(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Entwurf spannt ueber die Events: zwei Events mit je einem Platz liefern zwei
        Fotos, nicht eines."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(db_session, run, position=1)
        second_event = await _make_event(db_session, run, position=2)
        first_photo = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC)
        )
        second_photo = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, first_photo, event=first_event, rank_score=0.9, rank_position=1
        )
        await _add_ranking(
            db_session, run, second_photo, event=second_event, rank_score=0.1, rank_position=1
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        assert {item["id"] for item in response.json()["items"]} == {
            first_photo.id,
            second_photo.id,
        }

    async def test_a_small_draft_returns_fewer_without_error(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        only = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, only, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        assert response.status_code == 200
        body = response.json()
        assert body["items"][0]["id"] == only.id

    async def test_a_run_without_a_draft_answers_empty(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Bestandslauf: seine Rangzeilen tragen ueberall `NULL`, es gibt keine Migration, die
        den Vorschlag rueckwirkend berechnet. Ohne eigene Aufnahme bleibt der Entwurf leer."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session, run, photo, rank_score=0.9, rank_position=1, selection_position=None
        )

        body = await _album_draft(authenticated_api_client, project)

        assert body["items"] == []
        assert [event_row["id"] for event_row in body["events"]] == [
            (await _default_event(db_session, run)).id
        ]

    async def test_limit_and_offset_stay_without_effect(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 19 (Sicherheitsauflage S4/S14): `limit`/`offset` wirken hier nicht, auch
        nicht HALB. Ein abgeschnittener Entwurf, den die Ansicht als vollstaendig ausweist, ist ein
        Zustand, den keine Anzeige als fehlerhaft erkennt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        for index in range(4):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1 + index, tzinfo=UTC)
            )
            await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=index + 1)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/album-draft", params={"limit": 1, "offset": 2}
        )

        assert response.status_code == 200
        assert len(response.json()["items"]) == 4

    @pytest.mark.parametrize("value", ["true", "false"])
    async def test_the_old_selection_parameter_fails_loudly_in_both_settings(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, value: str
    ) -> None:
        """Zusicherung 20: Der abgeschaffte Parameter scheitert LAUT, in BEIDEN Belegungen. Der
        zweite ist der gefaehrlichere - `selection=false` ist heute ein gueltiger Aufruf und fiele
        sonst still in den Listing-Zweig, ohne dass irgendwo ein Fehler sichtbar wuerde."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"selection": value}
        )

        assert response.status_code == 422

    async def test_rejecting_a_photo_does_not_change_the_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nach dem Streichen des Top-Fotos rueckt in der ANTWORT nichts nach - das gestrichene
        Foto bleibt an seiner Position und traegt seinen Zustand; die Ansicht blendet es aus.

        Geprueft als vollstaendiger Listenvergleich (Ids in Reihenfolge), nicht als blosses
        "das Foto ist noch da": ein Vorhandensein-Test bliebe auch dann gruen, wenn hinter dem
        Foto die Liste umsortiert wuerde."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        # Im Vorrat, aber nicht im Vorschlag - das ist das Foto, das frueher nachgerueckt waere.
        await _add_ranking(
            db_session, run, second, rank_score=0.5, rank_position=2, selection_position=None
        )

        before = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")
        assert [item["id"] for item in before.json()["items"]] == [first.id]

        await authenticated_api_client.put(
            f"/photos/{first.id}/rating", json={"status": "rejected"}
        )

        after = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")
        assert [item["id"] for item in after.json()["items"]] == [first.id]
        [item] = after.json()["items"]
        ranking = item["ranking"]
        assert (ranking["rank_position"], ranking["curation_position"]) == (1, 1)

    async def test_a_rejected_photo_stays_in_the_draft_with_its_rating(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Das gestrichene Foto verschwindet nicht aus der ANTWORT, sondern traegt seinen Zustand
        dort, wo er im Produkt immer steht - in `ratings[]`. Die Entwurfsansicht leitet Ausblenden
        und Gestrichen-Zeile ausschliesslich daraus ab (`utils/ownRating.ts::ownRatingStatus`), es
        gibt kein eigenes Antwortfeld dafuer."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        await authenticated_api_client.put(
            f"/photos/{photo.id}/rating", json={"status": "rejected"}
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        [item] = response.json()["items"]
        assert item["id"] == photo.id
        assert [r["status"] for r in item["ratings"]] == ["rejected"]

    async def test_the_response_depends_on_the_asking_user(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die UMGEKEHRTE Zusage des frueheren `test_response_is_independent_of_the_asking_user`
        (ADR 0071 Entscheidung 1, mit ADR 0098 abgeloest): Seit der Entwurf je Nutzer entsteht,
        haengt die ANTWORTMENGE am anfragenden Nutzer - derselbe Aufbau, umgekehrte Erwartung.

        Beide Richtungen in EINEM Fall: Das von B aufgenommene Foto erscheint nicht im Entwurf von
        A, und das von B gestrichene bleibt in A's Entwurf. Ein Ein-Nutzer-Test sieht keine von
        beiden."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        proposed = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        other_choice = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC)
        )
        await _add_ranking(db_session, run, proposed, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, other_choice, rank_score=0.5, rank_position=2, selection_position=None
        )

        other_user = await _make_second_user(db_session)
        # B nimmt ein Foto auf, das der Lauf nicht vorschlaegt, und streicht das vorgeschlagene.
        await self._rate(db_session, other_choice, RatingStatus.ALBUM_WORTHY, other_user)
        await self._rate(db_session, proposed, RatingStatus.REJECTED, other_user)

        async def draft(client: httpx.AsyncClient) -> list[int]:
            response = await client.get(f"/projects/{project.id}/album-draft")
            assert response.status_code == 200
            return [item["id"] for item in response.json()["items"]]

        own_view = await draft(authenticated_api_client)

        # DIESELBE Anfrage, anderer Nutzer. Nur der Bearer-Token wechselt (und wird danach
        # zurueckgesetzt), damit derselbe ASGI-Transport und dieselbe Sitzung benutzt werden.
        own_authorization = authenticated_api_client.headers["Authorization"]
        authenticated_api_client.headers["Authorization"] = (
            f"Bearer {create_access_token(other_user)}"
        )
        try:
            other_view = await draft(authenticated_api_client)
        finally:
            authenticated_api_client.headers["Authorization"] = own_authorization

        assert own_view != other_view
        assert own_view == [proposed.id]
        assert other_view == [proposed.id, other_choice.id]

    async def test_empty_before_any_successful_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ohne erfolgreichen Lauf ist der Entwurf leer - AUCH dann, wenn der Nutzer bereits
        Fotos aufgenommen hat. Der Entwurf ist Vorschlag ∪ Aufnahmen, und ohne Lauf gibt es weder
        Vorschlag noch Events, in die etwas einzuordnen waere."""
        project = await _make_project(db_session)
        taken = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)

        assert await _album_draft(authenticated_api_client, project) == {
            "events": [],
            "items": [],
            "eligible_candidate_count": 0,
        }

    async def test_a_run_without_events_keeps_the_draft_empty(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein erfolgreicher Lauf OHNE Events: es gibt keine Spanne, in die ein aufgenommenes Foto
        einzuordnen waere. Die Ausfallrichtung ist "nicht zeigen", nie eine erfundene Gruppe."""
        project = await _make_project(db_session)
        await _make_criterion_scoring_run(db_session, project)
        taken = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)

        assert await _album_draft(authenticated_api_client, project) == {
            "events": [],
            "items": [],
            "eligible_candidate_count": 0,
        }

    @pytest.mark.parametrize("value", [2, 11])
    async def test_the_old_top_n_parameter_does_not_exist_any_more(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, value: int
    ) -> None:
        """Der Nachfolger von `test_rejects_top_n_per_event_outside_valid_range`, und bewusst
        keine blosse Umbenennung: geprueft wird, dass der Parameter GAR NICHT MEHR existiert -
        auch ein frueher gueltiger Wert endet in `422`. Ein Uebergangsweg mit beiden Parametern
        waere eine zweite Auswahlregel."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_event": value}
        )

        assert response.status_code == 422

    async def test_includes_criterion_scores_alongside_ranking(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Test-Review-Fund: criterion_scores und ranking wurden bisher nur je einzeln getestet,
        # nie im selben Entwurfszweig kombiniert - to_photo_out setzt aber beide in
        # derselben Funktion.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="sharpness",
                value=0.5,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        item = response.json()["items"][0]
        assert item["ranking"] is not None
        assert [c["criterion_key"] for c in item["criterion_scores"]] == ["sharpness"]


class TestTheProposedFlag:
    """`RankingOut.proposed` ist `selection_position IS NOT NULL` des letzten erfolgreichen Laufs:
    LAUF-GLOBAL (kein Nutzerbezug) und auf ALLEN Lesepfaden befuellt, nicht nur im Entwurfsmodus.

    Es ist die einzige Auskunft darueber, ob der Lauf ein Foto vortraegt - ohne sie muesste die
    Oberflaeche sie aus `curation_position` nachbauen, und die gibt es nur im Entwurfszweig."""

    async def test_the_listing_carries_proposed_for_both_states(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        proposed = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        candidate = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC)
        )
        await _add_ranking(db_session, run, proposed, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, candidate, rank_score=0.5, rank_position=2, selection_position=None
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[proposed.id]["ranking"]["proposed"] is True
        assert items[candidate.id]["ranking"]["proposed"] is False

    async def test_the_alternatives_endpoint_carries_the_same_field(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Feldgleichheit ueber die Lesepfade: derselbe Wert desselben Fotos, einmal ueber das
        Listing und einmal ueber den Alternativen-Endpunkt. Ein je Zweig getrennt gesetztes Feld
        liefe genau hier auseinander."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, second, rank_score=0.5, rank_position=2, selection_position=None
        )

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        alternatives = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={
                "event_id": (await _default_event(db_session, run)).id,
                "photo_id": first.id,
            },
        )

        from_listing = {item["id"]: item["ranking"]["proposed"] for item in listing.json()["items"]}
        [alternative_item] = alternatives.json()["items"]
        assert alternative_item["id"] == second.id
        assert alternative_item["ranking"]["proposed"] == from_listing[second.id] is False

    async def test_proposed_is_run_global_and_not_user_dependent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die MENGE der Antwort haengt im Entwurfszweig am anfragenden Nutzer, dieses Feld
        ausdruecklich NICHT: es sagt, was der LAUF vortraegt. Der zweite Nutzer bewertet das Foto
        gegenlaeufig - beide Sichten tragen trotzdem denselben Wert."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other_user = await _make_second_user(db_session)
        db_session.add(
            Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.REJECTED)
        )
        await db_session.commit()

        own = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        own_authorization = authenticated_api_client.headers["Authorization"]
        authenticated_api_client.headers["Authorization"] = (
            f"Bearer {create_access_token(other_user)}"
        )
        try:
            other = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        finally:
            authenticated_api_client.headers["Authorization"] = own_authorization

        assert own.json()["items"][0]["ranking"]["proposed"] is True
        assert other.json()["items"][0]["ranking"]["proposed"] is True
