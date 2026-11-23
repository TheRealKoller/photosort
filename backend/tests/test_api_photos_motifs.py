"""Foto-API: die zusaetzlichen Motiv-Felder, Vorhandensein, die vier Foto-Zustaende, Motivstaerken in
einer Abfrage.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    MotifAssessmentSource,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    User,
)
from photosort.motifs import MOTIF_REGISTRY
from photosort.selection import MOTIF_PRESENCE_THRESHOLD
from tests.support.api_photos import (
    _add_ranking,
    _assess_photo,
    _first_photo_out,
    _make_criterion_scoring_run,
    _make_photo,
    _make_project,
    _recorded_select_statements,
)


class TestTheAdditiveMotifFields:
    async def test_a_photo_with_an_assessment_carries_the_header(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, computed_at=datetime(2026, 9, 12, 10, 0, 0))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"] == {
            "source": "cloud",
            "provider": "anthropic",
            "excluded_document": False,
            "computed_at": "2026-09-12T10:00:00",
        }

    async def test_a_local_assessment_reports_its_basis_without_a_provider(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Dass eine Auswahl auf der schwaecheren Grundlage beruht, ist erkennbar: die Antwort
        nennt die Grundlage."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, source=MotifAssessmentSource.LOCAL, provider=None)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"]["source"] == "local"
        assert item["motif_assessment"]["provider"] is None

    async def test_the_list_carries_all_eight_motifs_in_registry_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo)

        item = await _first_photo_out(authenticated_api_client, project)

        assert [entry["key"] for entry in item["motifs"]] == list(MOTIF_REGISTRY)

    async def test_the_list_carries_eight_entries_even_with_incomplete_strength_rows(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein halb gefuellter Vektor darf die Liste nicht verkuerzen - sonst wechselten die
        Zeilen von Foto zu Foto ihre Position, und acht gleichnamige Korrekturschalter laden zum
        Fehlklick ein."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        db_session.add(
            PhotoMotifAssessment(
                photo_id=photo.id,
                source=MotifAssessmentSource.CLOUD,
                excluded_document=False,
                provider="anthropic",
                computed_at=datetime(2026, 9, 12, 10, 0, 0),
            )
        )
        await db_session.flush()
        db_session.add(PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.6))
        await db_session.commit()

        item = await _first_photo_out(authenticated_api_client, project)

        assert [entry["key"] for entry in item["motifs"]] == list(MOTIF_REGISTRY)
        by_key = {entry["key"]: entry for entry in item["motifs"]}
        assert by_key["menschen"]["strength"] == pytest.approx(0.6)
        assert by_key["tiere"]["strength"] == 0.0
        assert by_key["tiere"]["correction"] is None

    async def test_a_building_is_strong_and_people_are_weak_and_not_the_other_way_round(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Sichtbar im Ergebnis: ein Foto, auf dem das Modell ein Bauwerk deutlich und Menschen
        nur schwach erkennt, wird als Bauwerk stark und als Menschen schwach GEFUEHRT."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(
            db_session,
            photo,
            strengths={"bauwerk_sehenswuerdigkeit": 0.9, "menschen": 0.2},
        )

        by_key = {
            entry["key"]: entry["strength"]
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert by_key["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.9)
        assert by_key["menschen"] == pytest.approx(0.2)
        assert by_key["bauwerk_sehenswuerdigkeit"] > by_key["menschen"]

    async def test_a_correction_wins_over_the_model_number_in_the_response(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Antwort traegt die WIRKSAME Staerke - das Frontend rechnet nichts nach."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, strengths={"menschen": 0.9})
        user = (await db_session.execute(select(User))).scalars().first()
        assert user is not None
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        await db_session.commit()

        by_key = {
            entry["key"]: entry
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert by_key["menschen"]["strength"] == 0.0
        assert by_key["menschen"]["correction"] is False

    async def test_an_excluded_photo_keeps_its_strengths_in_the_response(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Ausschluss gewinnt, die Staerken bleiben gespeichert und werden nicht auf 0
        gesetzt - der Lesehelfer weist das Foto ueber `excluded_document` als ausgeschlossen
        aus."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, excluded_document=True, strengths={"menschen": 0.9})

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"]["excluded_document"] is True
        by_key = {entry["key"]: entry["strength"] for entry in item["motifs"]}
        assert by_key["menschen"] == pytest.approx(0.9)

    async def test_not_a_single_category_field_is_left_in_the_response(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die NEGATIVE Haelfte der Abloesung an der Antwort selbst (Spec 0427, PR 3 Schritt 4).

        Ein stehengebliebenes Feld waere fuer jeden Positivtest der Motivfelder unsichtbar: es
        traegt dann dauerhaft `null` bzw. `[]`, bricht keinen Test und lehrt das Frontend eine
        Aussage, die das Produkt nicht mehr macht."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo)

        item = await _first_photo_out(authenticated_api_client, project)

        for field in (
            "remote_category",
            "category_confidence",
            "category_override",
            "category_candidates",
            "rankings",
        ):
            assert field not in item, field
        assert "ranking" in item


class TestTheMotifPresenceFlag:
    """`MotifStrengthOut.present` - die Aussage des Servers, ob ein Foto ein Motiv TRAEGT.

    Die Grenze wohnt in `selection.py` und verlaesst das Backend nie als Zahl; die Motivmischung
    der Entwurfsansicht liest ausschliesslich dieses Ja/Nein."""

    async def test_the_threshold_is_inclusive_at_the_boundary(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 27, erste Haelfte: Die Staerke EXAKT an der Grenze traegt das Motiv, knapp
        darunter nicht. Der Zahlwert der Grenze steht in KEINEM Testfall - geprueft wird an der
        Grenze selbst, wie sie das Backend fuehrt."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(
            db_session,
            photo,
            strengths={
                "menschen": MOTIF_PRESENCE_THRESHOLD,
                "tiere": MOTIF_PRESENCE_THRESHOLD - 0.01,
            },
        )

        by_key = {
            entry["key"]: entry
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert by_key["menschen"]["present"] is True
        assert by_key["tiere"]["present"] is False

    async def test_a_correction_decides_the_flag_in_both_directions(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 27, zweite Haelfte: `present` entsteht aus DERSELBEN wirksamen Staerke wie
        `strength` - eine Korrektur nimmt ein starkes Motiv weg und holt ein schwaches herein.
        Beide Richtungen in einem Fall; eine Implementierung, die die MODELLzahl liest, faellt
        genau hier."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, strengths={"menschen": 0.9, "tiere": 0.1})
        user = (await db_session.execute(select(User))).scalars().first()
        assert user is not None
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="tiere", applies=True
            )
        )
        await db_session.commit()

        by_key = {
            entry["key"]: entry
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert (by_key["menschen"]["strength"], by_key["menschen"]["present"]) == (0.0, False)
        assert by_key["tiere"]["present"] is True
        assert by_key["tiere"]["strength"] > 0.0

    async def test_a_missing_strength_row_is_zero_and_absent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 27, dritte Haelfte: Eine fehlende Zeile ergibt `0.0` UND `false` - die
        beiden Felder entstehen aus derselben lokalen Groesse, auch im Ergaenzungszweig."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        db_session.add(
            PhotoMotifAssessment(
                photo_id=photo.id,
                source=MotifAssessmentSource.CLOUD,
                excluded_document=False,
                provider="anthropic",
                computed_at=datetime(2026, 9, 12, 10, 0, 0),
            )
        )
        await db_session.flush()
        db_session.add(PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.9))
        await db_session.commit()

        by_key = {
            entry["key"]: entry
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert (by_key["tiere"]["strength"], by_key["tiere"]["present"]) == (0.0, False)
        assert by_key["menschen"]["present"] is True

    async def test_a_photo_without_an_assessment_carries_no_entry_and_thus_no_flag(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Acht Eintraege mit `present: false` waeren wieder "nichts erkannt" statt "nicht
        klassifiziert" - die Liste bleibt LEER."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motifs"] == []

    async def test_present_is_identical_in_the_listing_and_in_the_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Feldgleichheit ueber die Lesepfade, wie bei `proposed`: Ein je Zweig getrennt gesetztes
        Feld liefe genau hier auseinander, und die Motivmischung naennte dann je nach Ansicht
        andere Motive."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        await _assess_photo(db_session, photo, strengths={"menschen": 0.9, "tiere": 0.1})

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        draft = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        assert listing.json()["items"][0]["motifs"] == draft.json()["items"][0]["motifs"]
        by_key = {entry["key"]: entry["present"] for entry in draft.json()["items"][0]["motifs"]}
        assert (by_key["menschen"], by_key["tiere"]) == (True, False)


class TestTheFourPhotoStates:
    async def test_a_photo_without_an_assessment_carries_no_motif_entry_at_all(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die KARDINALITAET Null, nicht eine Textsuche: der Hinweissatz kann ueber acht
        Nullzeilen stehen, und dann ist er gruen und falsch."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"] is None
        assert item["motifs"] == []

    async def test_not_yet_classified_and_nothing_recognised_are_different_responses(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """DAS PAAR. Derselbe Aufbau, einmal ohne Kopfzeile und einmal mit einer Kopfzeile, deren
        acht Staerken alle 0.0 sind - und die Assertion darauf, dass die beiden Antworten
        VERSCHIEDEN sind. Ohne sie machte ein `?? 0` im Lesepfad aus "noch nicht klassifiziert"
        acht Nullzeilen, und kein anderer Test brach."""
        unassessed_project = await _make_project(db_session, name="Ohne Kopfzeile")
        await _make_photo(db_session, unassessed_project, "a.jpg", datetime(2023, 1, 1))
        assessed_project = await _make_project(db_session, name="Mit Kopfzeile")
        assessed = await _make_photo(db_session, assessed_project, "b.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, assessed, source=MotifAssessmentSource.LOCAL, provider=None)

        unassessed_item = await _first_photo_out(authenticated_api_client, unassessed_project)
        assessed_item = await _first_photo_out(authenticated_api_client, assessed_project)

        assert unassessed_item["motif_assessment"] is None
        assert assessed_item["motif_assessment"] is not None
        assert len(unassessed_item["motifs"]) == 0
        assert len(assessed_item["motifs"]) == len(MOTIF_REGISTRY)
        assert {entry["strength"] for entry in assessed_item["motifs"]} == {0.0}
        assert unassessed_item["motifs"] != assessed_item["motifs"]

    async def test_a_correction_on_a_photo_without_an_assessment_stays_invisible_in_the_list(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Korrektur ist gespeichert, aber es gibt noch keine Zeile, an der sie haengen
        koennte - die Liste bleibt leer, statt eine einzelne Zeile zu erfinden."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        user = (await db_session.execute(select(User))).scalars().first()
        assert user is not None
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True
            )
        )
        await db_session.commit()

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motifs"] == []


class TestTheMotifStrengthsAreLoadedInOneQuery:
    async def test_one_strength_query_regardless_of_the_photo_count(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Kein Query je Foto: dieselbe Auflage wie bei `camera`/`criterion_scores`."""
        project = await _make_project(db_session)
        for index in range(6):
            photo = await _make_photo(
                db_session, project, f"p{index}.jpg", datetime(2023, 1, 1) + timedelta(hours=index)
            )
            await _assess_photo(db_session, photo)

        with _recorded_select_statements() as statements:
            response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        strength_selects = [s for s in statements if "photo_motif_strengths" in s.lower()]
        assert len(strength_selects) == 1, strength_selects
