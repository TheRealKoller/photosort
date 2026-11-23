"""Foto-API: Ort, Cluster-Ort, Ereignis, Laufbindung des Orts, Abfragezahl."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    Photo,
    Project,
)
from tests.support.api_photos import (
    _add_ranking,
    _default_event,
    _make_camera,
    _make_criterion_scoring_run,
    _make_event,
    _make_photo,
    _make_photo_of_camera,
    _make_project,
    _recorded_select_statements,
)


async def _make_photo_at(
    session: AsyncSession,
    project: Project,
    path: str,
    taken_at: datetime,
    *,
    gps: tuple[float, float] | None = None,
) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=taken_at,
        taken_at_original=taken_at,
        last_modified=taken_at,
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


_EIFFEL = (48.858093, 2.294694)


# Trocadero, rund 700 m entfernt - ein anderer ORT, aber (verifiziert) dieselbe gerundete Stelle
# wie der Eiffelturm: 500 m Trennabstand und ~1,1 km Rundungsraster sind bewusst verschieden grob.
# Fuer die Nachbarschaftstests der Herleitung ist genau das richtig; fuer "Mehrere Orte" nicht.
_TROCADERO = (48.862000, 2.288500)


# Ein Ort auf einem ANDEREN Kontinent (Sydney). Fuer den Nachweis der Ortsuebernahme unter einem
# gesetzten Versatz ist genau diese Weite richtig: erbt ein Kamerafoto den falschen Anker, ist das
# Ergebnis unuebersehbar falsch und nicht bloss um ein paar Meter verschoben - dieselbe Deutlichkeit,
# die der Zielabsatz der Spec beschreibt ("der Ort eines ganz anderen Moments").
_SYDNEY = (-33.856800, 151.215300)


# Louvre - eine tatsaechlich ANDERE gerundete Stelle (48.86, 2.34 statt 48.86, 2.29). Der
# Unterschied zu _TROCADERO ist der eigentliche Testgegenstand des "multiple"-Falls: dort wird die
# GERUNDETE Stelle verglichen, nicht der Rohwert.
_LOUVRE = (48.860611, 2.337644)


class TestPhotoLocationAndClusterPlace:
    async def test_a_photo_with_its_own_coordinate_reports_source_exif_in_full_precision(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """VOLLE EXIF-Praezision, keine serverseitige Rundung (Daniels Entscheidung) - die
        Rundung auf zwei Nachkommastellen liegt allein in `cluster_place`, weil dort dieselbe Zahl
        ueber "coordinate" vs. "multiple" entscheidet."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC), gps=_EIFFEL
        )
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        [item] = response.json()["items"]
        assert item["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "exif",
        }

    async def test_a_photo_without_a_coordinate_inherits_the_nearest_one_in_its_cluster(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        anchor = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
        )
        await _add_ranking(db_session, run, anchor, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, blind, rank_score=0.5, rank_position=2)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[anchor.id]["location"]["source"] == "exif"
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }

    async def test_the_derived_coordinate_comes_from_the_temporally_nearest_neighbour(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        far = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 50, tzinfo=UTC)
        )
        near = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 10, 55, tzinfo=UTC), gps=_TROCADERO
        )
        for index, photo in enumerate((far, blind, near), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"]["lat"] == _TROCADERO[0]
        assert items[blind.id]["location"]["source"] == "derived"

    # specs/features/0426-zeitversatz-je-kamera.md, Akzeptanzkriterium 5: die ORTSUEBERNAHME ist
    # die vierte Lesestelle der Aufnahmezeit und braucht ihren eigenen Nachweis an einem
    # Datensatz, dessen Ergebnis mit gesetztem Versatz ANDERS ausfaellt als mit der
    # aufgezeichneten Zeit.
    #
    # Gefuehrt wird der Nachweis am AUFRUFER, nicht an `infer_locations`: die reine Funktion
    # kennt den Versatz nicht: sie bekommt `taken_at` uebergeben. Die Entscheidung, WELCHE
    # Spalte die Inferenzbasis speist, liegt hier (`_event_and_location_by_photo_id`) und in
    # `worker/_criterion/ranking.py::build_grouping_and_rankings` - genau dort waere ein Umbau auf
    # `taken_at_original` plausibel formuliert und fachlich falsch.
    async def _inheritance_fixture(
        self, db_session: AsyncSession, *, offset_minutes: int
    ) -> tuple[Project, Photo]:
        """Zwei Anker mit VERSCHIEDENEN Koordinaten und ein Kamerafoto ohne eigene Koordinate,
        dessen zeitlich naechster Anker vom Versatz abhaengt.

        Aufgezeichnet 10:00 - naechster Anker ist der um 09:00 (eine Stunde gegen vier). Mit
        +180 Minuten liegt die wirksame Zeit auf 13:00 - naechster Anker ist der um 13:00."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        camera = await _make_camera(
            db_session, project, "Canon", "EOS 5D", offset_minutes=offset_minutes
        )
        early = await _make_photo_at(
            db_session, project, "frueh.jpg", datetime(2023, 1, 1, 9, 0), gps=_EIFFEL
        )
        late = await _make_photo_at(
            db_session, project, "spaet.jpg", datetime(2023, 1, 1, 13, 0), gps=_SYDNEY
        )
        blind = await _make_photo_of_camera(
            db_session, project, "kamera.jpg", datetime(2023, 1, 1, 10, 0), camera
        )
        for index, photo in enumerate((early, blind, late), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)
        return project, blind

    async def test_without_an_offset_the_camera_photo_inherits_the_earlier_anchor(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project, blind = await self._inheritance_fixture(db_session, offset_minutes=0)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"]["lat"] == _EIFFEL[0]
        assert items[blind.id]["location"]["source"] == "derived"

    async def test_an_offset_switches_the_inherited_place_to_the_other_anchor(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """DER Defekt, den die Story behebt (Zielabsatz): ein Kamerafoto ohne eigenen Ort erbt bei
        falsch gehender Uhr den Ort eines ganz anderen Moments. Faellt dieser Fall weg, kann ein
        Umbau die Inferenzbasis auf `taken_at_original` umstellen, ohne dass ein Test roetet."""
        project, blind = await self._inheritance_fixture(db_session, offset_minutes=180)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        # Mit der AUFGEZEICHNETEN Zeit (10:00) waere es der Eiffelturm-Anker - der Unterschied
        # zwischen beiden Faellen ist ausschliesslich der Versatz.
        assert items[blind.id]["location"]["lat"] == _SYDNEY[0]
        assert items[blind.id]["location"]["lon"] == _SYDNEY[1]
        assert items[blind.id]["location"]["source"] == "derived"

    async def test_an_exactly_equidistant_neighbour_is_resolved_towards_the_earlier_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Deterministischer Tie-Break: bei zwei gleich weit entfernten Nachbarn gewinnt der
        FRUEHERE Zeitpunkt. Ohne feste Regel haengt die angezeigte Koordinate an der
        Zeilenreihenfolge der Datenbank."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        earlier = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 10, tzinfo=UTC)
        )
        later = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 10, 20, tzinfo=UTC), gps=_TROCADERO
        )
        for index, photo in enumerate((earlier, blind, later), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"]["lat"] == _EIFFEL[0]

    async def test_an_identical_timestamp_is_resolved_towards_the_smaller_photo_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        same_moment = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        first = await _make_photo_at(db_session, project, "a.jpg", same_moment, gps=_EIFFEL)
        second = await _make_photo_at(db_session, project, "b.jpg", same_moment, gps=_TROCADERO)
        blind = await _make_photo_at(db_session, project, "c.jpg", same_moment)
        for index, photo in enumerate((first, second, blind), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert min(first.id, second.id) == first.id
        assert items[blind.id]["location"]["lat"] == _EIFFEL[0]

    async def test_a_photo_earlier_than_every_anchor_inherits_the_first_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Randfall "vor allen Ankern" - die Einfuegestelle ist 0, und es gibt keinen frueheren
        Nachbarn, gegen den abgewogen werden koennte. Ohne eigenen Fall bliebe genau der Zweig
        ungeprueft, der bei einer Umstellung der Suche als erstes bricht."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        blind = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        nearest = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 5, tzinfo=UTC), gps=_EIFFEL
        )
        farther = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 11, 0, tzinfo=UTC), gps=_LOUVRE
        )
        for index, photo in enumerate((blind, nearest, farther), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }

    async def test_a_photo_later_than_every_anchor_inherits_the_last_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der gespiegelte Randfall: die Einfuegestelle liegt hinter dem letzten Anker."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        farther = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_LOUVRE
        )
        nearest = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 55, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 11, 0, tzinfo=UTC)
        )
        for index, photo in enumerate((farther, nearest, blind), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }

    async def test_duplicate_anchor_timestamps_still_resolve_to_the_smaller_photo_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zwei Anker auf DEMSELBEN Zeitpunkt plus ein spaeterer dritter - der Fall, der die
        Sortier-Voraussetzung der Suche tatsaechlich beansprucht: die Ankerliste ist nach
        `(taken_at, photo_id)` sortiert, und die Suche darf nur den ERSTEN der beiden gleichen
        Zeitstempel treffen. Der bestehende Gleichstand-Test kommt ohne einen dritten, spaeteren
        Anker aus und wuerde eine falsche Einfuegestelle deshalb nicht bemerken."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        same_moment = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        first = await _make_photo_at(db_session, project, "a.jpg", same_moment, gps=_EIFFEL)
        second = await _make_photo_at(db_session, project, "b.jpg", same_moment, gps=_TROCADERO)
        later = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 10, 30, tzinfo=UTC), gps=_LOUVRE
        )
        blind = await _make_photo_at(db_session, project, "d.jpg", same_moment)
        for index, photo in enumerate((first, second, later, blind), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert first.id < second.id < later.id
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }

    async def test_both_fields_are_null_when_nothing_carries_a_location_at_all(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """KEIN Objekt aus lauter `null`-Feldern - `null` heisst "kein Ort"."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo_at(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        [item] = response.json()["items"]
        assert item["location"] is None
        assert item["event"]["place"] is None

    async def test_location_is_null_while_the_event_place_is_set_for_a_name_only_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die `null`-Abgrenzung getrennt fuer BEIDE Felder: ein Event mit einem Namen, aber ohne
        jede Koordinate, hat einen Ort - kein Foto hat trotzdem einen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session, run, position=1, landmark_name="Eiffelturm", place_kind="landmark"
        )
        photo = await _make_photo_at(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        [item] = response.json()["items"]
        assert item["location"] is None
        assert item["event"]["place"] == {
            "kind": "landmark",
            "landmark_name": "Eiffelturm",
            "lat": None,
            "lon": None,
        }

    async def test_the_only_anchor_may_be_a_rejected_photo_without_a_ranking_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """VERSCHAERFTER ROT-ANKER: die Bezugsmenge der Ortsherleitung ist das GANZE PROJEKT, nicht
        die Kandidatenmenge. Der einzige Anker ist hier ein am Ausschuss-Gate haengengebliebenes
        Foto ohne jede Rangzeile - unter der frueheren, clusterweiten Herleitung blieb das
        koordinatenlose Foto `null`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        gated = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
        )
        await _add_ranking(db_session, run, blind, rank_score=0.5, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[gated.id]["location"]["source"] == "exif"
        # Das aussortierte Foto hat keine Rangzeile und damit kein Event - seinen ORT vererbt es
        # trotzdem.
        assert items[gated.id]["event"] is None
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }


# Die Stufenentscheidung selbst (Name -> eine gerundete Zelle -> mehrere Orte -> kein Ortsbezug),
# die Rundung und die `-0.0`-Normalisierung leben seit Spec 0425 in `events.py` und werden dort
# DB-frei geprueft (tests/test_events_place_names.py::TestEventPlace). Die Namenshaertung liegt an
# der Schreibstelle (tests/test_worker_criterion_scoring_landmark_names.py, unsanierter und zu
# langer Altname). Hier bleibt, was nur der Endpunkt zeigen kann.
class TestEventIsNotAnAnswerStatement:
    async def _seed_event_with_a_deep_anchor(
        self,
        db_session: AsyncSession,
        *,
        anchor_gps: tuple[float, float] | None = None,
        shallow_gps: tuple[float, float] | None = None,
        landmark_name: str | None = None,
    ) -> tuple[Project, CriterionScoringRun, Photo]:
        """Ein Event mit 11 Fotos, dessen tragendes Foto auf `rank_position` 11 liegt und NICHT
        zum Vorschlag gehoert - also ausserhalb der Auswahl-Antwort. Der Vorschlag umfasst die
        drei bestplatzierten Fotos."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            position=1,
            landmark_name=landmark_name,
            place_kind=None if landmark_name is None else "landmark",
        )
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for index in range(1, 11):
            shallow = await _make_photo_at(
                db_session,
                project,
                f"shallow-{index}.jpg",
                base + timedelta(minutes=index),
                gps=shallow_gps,
            )
            await _add_ranking(
                db_session,
                run,
                shallow,
                event=event_row,
                rank_score=1.0 / index,
                rank_position=index,
                selection_position=index if index <= 3 else None,
            )
        anchor = await _make_photo_at(
            db_session, project, "anchor.jpg", base + timedelta(minutes=11), gps=anchor_gps
        )
        await _add_ranking(
            db_session,
            run,
            anchor,
            event=event_row,
            rank_score=0.01,
            rank_position=11,
            selection_position=None,
        )
        return project, run, anchor

    async def test_the_only_coordinate_reaches_photos_that_outrank_it(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ROT-ANKER: das EINZIGE koordinatentragende Foto liegt auf Rang 11 und steht nicht im
        Vorschlag. Eine Herleitung ueber die Fotos der Antwort lieferte hier `null`."""
        project, _run, _anchor = await self._seed_event_with_a_deep_anchor(
            db_session, anchor_gps=_EIFFEL
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        items = response.json()["items"]
        assert len(items) == 3
        for item in items:
            assert item["location"] == {
                "lat": _EIFFEL[0],
                "lon": _EIFFEL[1],
                "source": "derived",
            }

    async def test_the_event_does_not_change_between_limit_one_and_sixty(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project, _run, _anchor = await self._seed_event_with_a_deep_anchor(
            db_session, anchor_gps=_LOUVRE, shallow_gps=_EIFFEL, landmark_name="Eiffelturm"
        )

        narrow = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"limit": 1}
        )
        wide = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"limit": 60}
        )

        assert narrow.json()["items"][0]["event"] == wide.json()["items"][0]["event"]

    async def test_both_fields_are_field_equal_across_photos_and_draft_alternatives(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der direkte "springt nicht"-Nachweis: dasselbe Foto einmal ueber das Standard-Listing
        und einmal ueber den Alternativen-Endpunkt. Das tragende Foto liegt ausserhalb des
        Vorschlags und ist damit genau dort eine Alternative."""
        project, run, anchor = await self._seed_event_with_a_deep_anchor(
            db_session, anchor_gps=_LOUVRE, shallow_gps=_EIFFEL
        )
        event_row = await _default_event(db_session, run)

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        from_listing = {item["id"]: item for item in listing.json()["items"]}
        # Bezugsbild ist ein vorgeschlagenes Foto desselben Events - der Regelfall des Austauschs.
        reference_id = next(
            item["id"] for item in from_listing.values() if item["ranking"]["proposed"]
        )

        alternatives = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event_row.id, "photo_id": reference_id},
        )

        assert alternatives.status_code == 200
        by_id = {item["id"]: item for item in alternatives.json()["items"]}
        assert by_id[anchor.id]["location"] == from_listing[anchor.id]["location"]
        assert by_id[anchor.id]["event"] == from_listing[anchor.id]["event"]

    async def test_the_event_is_identical_on_every_photo_of_an_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nach `event_id` gruppiert geprueft, nicht stichprobenweise an einem Foto: das ist die
        Zusicherung, aus der die Frontend-Seite ihre Berechtigung zieht, den Wert aus einem
        BELIEBIGEN Foto des Events zu lesen. `location` DARF je Foto verschieden sein, `event`
        nicht."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(db_session, run, position=1, place_kind="multiple")
        second_event = await _make_event(
            db_session, run, position=2, landmark_name="Trocadero", place_kind="landmark"
        )
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for index in range(1, 4):
            photo = await _make_photo_at(
                db_session,
                project,
                f"a-{index}.jpg",
                base + timedelta(minutes=index),
                gps=_EIFFEL if index == 1 else None,
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=first_event,
                rank_score=1.0 / index,
                rank_position=index,
            )
        for index in range(1, 3):
            photo = await _make_photo_at(
                db_session,
                project,
                f"b-{index}.jpg",
                base + timedelta(hours=5, minutes=index),
                gps=_TROCADERO,
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=second_event,
                rank_score=1.0 / index,
                rank_position=index,
            )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        events_by_id: dict[int, list[object]] = {}
        for item in response.json()["items"]:
            events_by_id.setdefault(item["ranking"]["event_id"], []).append(item["event"])
        assert set(events_by_id) == {first_event.id, second_event.id}
        for event_id, seen in events_by_id.items():
            assert len(seen) > 1, event_id
            assert all(entry == seen[0] for entry in seen), event_id


class TestPlaceRunBinding:
    async def test_a_foreign_project_contributes_neither_location_nor_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT, Pflichtfall (M1 und M5 in EINEM Aufbau): die Ortsherleitung haengt an
        `Photo.project_id`, die Event-Abfrage am Lauf-Praedikat. Faellt eine der beiden Bindungen
        weg, erbt das Foto eine fremde Koordinate bzw. bekommt ein fremdes Event."""
        project_a = await _make_project(db_session, name="A")
        project_b = await _make_project(db_session, name="B")
        run_a = await _make_criterion_scoring_run(db_session, project_a)
        run_b = await _make_criterion_scoring_run(db_session, project_b)
        event_a = await _make_event(db_session, run_a, position=1)
        event_b = await _make_event(
            db_session, run_b, position=1, landmark_name="Eiffelturm", place_kind="landmark"
        )
        blind = await _make_photo_at(
            db_session, project_a, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        await _add_ranking(db_session, run_a, blind, event=event_a, rank_score=0.9, rank_position=1)
        foreign = await _make_photo_at(
            db_session, project_b, "b.jpg", datetime(2023, 1, 1, 10, 1, tzinfo=UTC), gps=_EIFFEL
        )
        await _add_ranking(
            db_session, run_b, foreign, event=event_b, rank_score=0.9, rank_position=1
        )

        response = await authenticated_api_client.get(f"/projects/{project_a.id}/photos")

        [item] = response.json()["items"]
        assert item["location"] is None
        assert item["event"]["place"] is None
        assert item["event"]["id"] == event_a.id

    async def test_an_older_run_of_the_same_project_contributes_no_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Dieselbe Bindung greift auch INNERHALB eines Projekts: Rangzeilen eines aelteren Laufs
        beschreiben eine andere Gliederung."""
        project = await _make_project(db_session)
        old_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC)
        )
        new_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 6, 1, tzinfo=UTC)
        )
        old_event = await _make_event(
            db_session, old_run, position=1, landmark_name="Eiffelturm", place_kind="landmark"
        )
        new_event = await _make_event(db_session, new_run, position=1)
        photo = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, old_run, photo, event=old_event, rank_score=0.5, rank_position=1
        )
        await _add_ranking(
            db_session, new_run, photo, event=new_event, rank_score=0.5, rank_position=1
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        [item] = response.json()["items"]
        assert item["event"]["id"] == new_event.id
        assert item["event"]["place"] is None

    async def test_without_a_successful_run_only_the_own_coordinate_remains(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ausfallrichtung "nichts anzeigen", nie "aus irgendeinem Lauf herleiten": ohne Bezugslauf
        gibt es kein Event. Der ORT bleibt - er haengt am Projekt, nicht am Lauf."""
        project = await _make_project(db_session)
        photo = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC), gps=_EIFFEL
        )
        await _make_photo_at(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[photo.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "exif",
        }
        assert items[photo.id]["event"] is None


class TestPlaceQueryCount:
    async def test_the_place_derivation_costs_a_fixed_number_of_queries(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Eine FESTE Zahl Abfragen pro Anfrage, nicht eine pro Foto: die Abfrageanzahl muss
        zwischen 2 und 20 Fotos GLEICH bleiben."""
        small = await _make_project(db_session, name="klein")
        large = await _make_project(db_session, name="gross")
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for project, count in ((small, 2), (large, 20)):
            run = await _make_criterion_scoring_run(db_session, project)
            for index in range(1, count + 1):
                photo = await _make_photo_at(
                    db_session,
                    project,
                    f"{project.name}-{index}.jpg",
                    base + timedelta(minutes=index),
                    gps=_EIFFEL if index == 1 else None,
                )
                await _add_ranking(
                    db_session, run, photo, rank_score=1.0 / index, rank_position=index
                )

        with _recorded_select_statements() as small_statements:
            small_response = await authenticated_api_client.get(f"/projects/{small.id}/photos")
        with _recorded_select_statements() as large_statements:
            large_response = await authenticated_api_client.get(f"/projects/{large.id}/photos")

        assert small_response.status_code == large_response.status_code == 200
        assert len(small_response.json()["items"]) == 2
        assert len(large_response.json()["items"]) == 20
        assert len(small_statements) == len(large_statements)


# ---------------------------------------------------------------------------------------------
# specs/features/0425-events-statt-zeitcluster.md, ADR 0087 Entscheidung 6: `PhotoOut.event`
# ersetzt `cluster_place`, `RankingOut.event_id` ersetzt `cluster_key`, und der Query-Parameter
# der Kuratierung wird von einem Freitextschluessel zu einer Objekt-Id.
class TestPhotoEvent:
    """Das Event in der Antwort - auf jedem Foto desselben Events FELDGLEICH."""

    async def test_every_photo_of_one_event_carries_the_identical_event_object(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            position=3,
            started_at=datetime(2023, 1, 1, 10, 30),
            ended_at=datetime(2023, 1, 1, 11, 45),
            landmark_name="Eiffelturm",
            place_kind="landmark",
            place_name="Paris",
        )
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1, 10, index, tzinfo=UTC)
            )
            await _add_ranking(
                db_session, run, photo, event=event_row, rank_score=0.9, rank_position=index + 1
            )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        events = [item["event"] for item in response.json()["items"]]
        assert len(events) == 3
        assert all(event == events[0] for event in events)
        assert events[0] == {
            "id": event_row.id,
            "position": 3,
            "started_at": "2023-01-01T10:30:00",
            "ended_at": "2023-01-01T11:45:00",
            "place": {"kind": "landmark", "landmark_name": "Eiffelturm", "lat": None, "lon": None},
            # Ein Event MIT Sehenswuerdigkeit darf daneben einen Ortsnamen tragen (Spec 0514,
            # ADR 0120): er verdeckt ihn nicht mehr. Beide Felder stehen NEBENEINANDER, die
            # Ueberschrift "Name, Ort" setzt erst das Frontend zusammen.
            "place_name": "Paris",
        }

    async def test_the_event_is_identical_across_both_read_paths(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein je Query-Modus divergierendes `PhotoOut` waere die zweite, driftende Abbildung."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        draft = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        assert listing.json()["items"][0]["event"] == draft.json()["items"][0]["event"]

    async def test_the_event_is_the_same_with_and_without_the_draft_mode(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Nachfolger von `test_the_event_does_not_depend_on_the_requested_top_n`: den
        Leseparameter, dessen Einfluss jener Fall ausschloss, gibt es nicht mehr. Nummer und
        Zeitspanne stehen weiterhin im Event, nicht in einer Aggregation ueber die sichtbaren
        Fotos - und der Aufbau sorgt dafuer, dass die beiden Antworten VERSCHIEDEN viele Fotos
        enthalten."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 18, 0),
        )
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1, 10, index, tzinfo=UTC)
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=0.9,
                rank_position=index + 1,
                selection_position=1 if index == 0 else None,
            )

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        draft = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        assert len(listing.json()["items"]) == 3
        assert len(draft.json()["items"]) == 1
        assert listing.json()["items"][0]["event"] == draft.json()["items"][0]["event"]

    async def test_a_photo_without_a_ranking_row_has_no_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["event"] is None

    async def test_the_ranking_carries_the_event_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        ranking = response.json()["items"][0]["ranking"]
        assert ranking["event_id"] == event_row.id
        assert "cluster_key" not in ranking

    @pytest.mark.parametrize(
        ("place_kind", "landmark_name", "lat", "lon", "expected"),
        [
            pytest.param(
                "coordinate",
                None,
                48.86,
                2.29,
                {"kind": "coordinate", "landmark_name": None, "lat": 48.86, "lon": 2.29},
                id="koordinate",
            ),
            pytest.param(
                "multiple",
                None,
                None,
                None,
                {"kind": "multiple", "landmark_name": None, "lat": None, "lon": None},
                id="mehrere-orte",
            ),
            pytest.param(None, None, None, None, None, id="kein-ortsbezug"),
        ],
    )
    async def test_the_place_mirrors_the_stored_kind(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        place_kind: str | None,
        landmark_name: str | None,
        lat: float | None,
        lon: float | None,
        expected: dict[str, Any] | None,
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            position=1,
            landmark_name=landmark_name,
            place_kind=place_kind,
            place_lat=lat,
            place_lon=lon,
        )
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["event"]["place"] == expected

    async def test_the_place_name_stands_beside_the_place_not_inside_it(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """DER TRAGENDE FALL: ein Event MIT Namen und UNBEKANNTEM `place_kind`. `place` ist dann
        `null` - der Name steht trotzdem da.

        Bei einer Unterbringung in `EventPlaceOut` fiele er still mit: `_event_place_out` liefert
        bei unbekanntem `place_kind` `None`, und die Ueberschrift des Events verschwaende."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session, run, position=1, place_kind="unbekannt", place_name="Split"
        )
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        event = response.json()["items"][0]["event"]
        assert event["place"] is None
        assert event["place_name"] == "Split"

    async def test_a_named_event_over_several_places_still_carries_no_coordinate(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Eine Koordinate erscheint weiterhin nie als Name - und ein Name macht aus "mehrere
        Orte" keinen einen Ort."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session, run, position=1, place_kind="multiple", place_name="Berlin, Mitte"
        )
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        event = response.json()["items"][0]["event"]
        assert event["place"] == {
            "kind": "multiple",
            "landmark_name": None,
            "lat": None,
            "lon": None,
        }
        assert event["place_name"] == "Berlin, Mitte"

    async def test_an_old_run_without_a_name_answers_null_not_an_empty_string(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """`NULL` heisst "kein aufgeloester Ortsname"; ein leerer String saehe in der Oberflaeche
        aus wie ein Name, den es gibt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1, place_kind="coordinate")
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["event"]["place_name"] is None

    async def test_an_unknown_place_kind_does_not_break_the_answer(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (M8): Mitgliedschaftspruefung statt blindem Cast - sonst legt ein einzelner
        Datenfehler die gesamte Listenantwort auf 500."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1, place_kind="galaxie")
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        assert response.json()["items"][0]["event"]["place"] is None

    async def test_the_event_of_a_foreign_run_is_never_attached(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (M1): `event_id` ist ein GLOBALER Surrogatschluessel; die Event-Abfrage
        traegt das Lauf-Praedikat ausgeschrieben."""
        foreign_project = await _make_project(db_session, name="Fremd")
        foreign_run = await _make_criterion_scoring_run(db_session, foreign_project)
        foreign_event = await _make_event(
            db_session, foreign_run, position=1, landmark_name="Geheim", place_kind="landmark"
        )

        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session, run, photo, event=foreign_event, rank_score=0.9, rank_position=1
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        assert response.json()["items"][0]["event"] is None
