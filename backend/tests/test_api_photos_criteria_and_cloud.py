"""Foto-API: Kriterienwerte und Cloud-Vision-Status.
(Aufgeteilt aus test_api_photos.py, Spec 0651.)
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.criteria import CRITERIA_REGISTRY
from photosort.models import (
    CriterionSource,
    MotifAssessmentSource,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoScore,
    RatingStatus,
)
from tests.support.api_photos import (
    _assess_photo,
    _make_photo,
    _make_project,
    _rate_album_suitability,
)


class TestCriterionScores:
    """Bewertungsdetails-Info-Popover (specs/features/0040-bewertungsdetails-info-popover.md):
    `PhotoOut.criterion_scores` exponiert die bereits vorhandenen `PhotoCriterionScore`-Zeilen."""

    async def test_includes_criterion_scores_in_registry_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        computed_at = datetime(2023, 1, 1, tzinfo=UTC)
        # Bewusst NICHT in Registry-Reihenfolge (sharpness, exposure, content_people,
        # content_landscape) eingefuegt - die Response muss trotzdem in Registry-Reihenfolge
        # sortieren (Akzeptanzkriterium 7 der Spec).
        db_session.add_all(
            [
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key="content_people",
                    value=1.0,
                    source=CriterionSource.LOCAL_ML,
                    computed_at=computed_at,
                ),
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key="sharpness",
                    value=0.734,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=computed_at,
                ),
            ]
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        criterion_scores = response.json()["items"][0]["criterion_scores"]
        assert criterion_scores == [
            {
                "criterion_key": "sharpness",
                "display_name": "Schärfe",
                "value": 0.734,
                "source": "local_heuristic",
                "has_presence_threshold": False,
            },
            {
                "criterion_key": "content_people",
                "display_name": "Menschen erkannt",
                "value": 1.0,
                "source": "local_ml",
                "has_presence_threshold": True,
            },
        ]

    async def test_content_landscape_is_exposed_as_a_non_category_quality_criterion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0217, ADR 0047 Punkt 1: content_landscape heisst in den
        # Bewertungsdetails "Flächigkeit" und ist nicht mehr kategorie-faehig - dadurch wandert es
        # im Frontend automatisch vom Block "Kategorien" in den Block "Qualität" (Spec 0209
        # partitioniert allein nach diesem Flag, kein Frontend-Sonderfall).
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_landscape",
                value=0.8,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["criterion_scores"] == [
            {
                "criterion_key": "content_landscape",
                "display_name": "Flächigkeit",
                "value": 0.8,
                "source": "local_heuristic",
                "has_presence_threshold": False,
            }
        ]

    async def test_criterion_scores_is_empty_list_when_none_exist(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["criterion_scores"] == []

    async def test_missing_criterion_is_omitted_not_filled_with_placeholder(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Best-effort-Luecke (Akzeptanzkriterium 8): nur `sharpness` wurde berechnet, `exposure`
        # fehlt - die Antwort darf `exposure` weder mit 0 noch einem Platzhalter auffuellen.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
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

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        criterion_scores = response.json()["items"][0]["criterion_scores"]
        assert [c["criterion_key"] for c in criterion_scores] == ["sharpness"]

    async def test_unknown_criterion_key_falls_back_to_key_as_display_name(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Defensiv gegen Registry-/Daten-Drift (Architektur-Abschnitt der Spec): ein
        # criterion_key, der (nicht mehr) in CRITERIA_REGISTRY steht, wird trotzdem angezeigt,
        # mit dem rohen Key als display_name. `category_eligible` faellt dabei auf False zurueck
        # (Registry-Default) - im Frontend landet die Zeile damit im Qualitaets-Block
        # (specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
        # Akzeptanzkriterium 9).
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="future_criterion",
                value=0.3,
                source=CriterionSource.CLOUD,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        criterion_scores = response.json()["items"][0]["criterion_scores"]
        assert criterion_scores == [
            {
                "criterion_key": "future_criterion",
                "display_name": "future_criterion",
                "value": 0.3,
                "source": "cloud",
                "has_presence_threshold": False,
            }
        ]

    async def test_has_presence_threshold_matches_the_registry_for_every_criterion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
        # Architektur-Entscheidung 1: das ausgelieferte Flag ist keine zweite Wahrheit, sondern
        # exakt `presence_threshold is not None`. Ein einziger Registry-weiter Test statt einer
        # Parametrisierung pro Key - WELCHE Kriterien eine Schwelle tragen, nagelt bereits
        # test_criteria.py::test_exactly_these_seven_content_criteria_carry_a_presence_threshold
        # fest.
        #
        # Die SCHWELLE selbst geht ausdruecklich nicht in die Antwort: sie ist die
        # Vorfilter-Grenze des Cloud-Aufrufs, keine Anzeigehilfe.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        computed_at = datetime(2023, 1, 1, tzinfo=UTC)
        db_session.add_all(
            [
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key=key,
                    value=0.5,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=computed_at,
                )
                for key in CRITERIA_REGISTRY
            ]
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        criterion_scores = response.json()["items"][0]["criterion_scores"]
        assert {c["criterion_key"]: c["has_presence_threshold"] for c in criterion_scores} == {
            key: definition.presence_threshold is not None
            for key, definition in CRITERIA_REGISTRY.items()
        }
        assert all("presence_threshold" not in c for c in criterion_scores)


class TestCloudVisionStatus:
    """specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-
    attempt-fehler-persistierung.md: `PhotoOut.cloud_vision_status` - immer genau 2 Eintraege in
    fester Reihenfolge [landmark, remote_category], Prioritaets-Kaskade ueber 5 Raenge je Phase.
    """

    async def test_always_returns_exactly_two_entries_in_fixed_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        status_list = response.json()["items"][0]["cloud_vision_status"]
        assert [entry["phase"] for entry in status_list] == ["landmark", "remote_category"]

    async def test_photo_without_any_score_row_is_not_candidate_for_both_phases_with_consent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # ADR 0035/Spec 0058, Akzeptanzkriterium: ein Foto ganz ohne PhotoScore-Zeile ->
        # not_candidate (NICHT not_run) fuer beide Phasen, sobald Consent aktiv ist.
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        status_list = response.json()["items"][0]["cloud_vision_status"]
        assert {entry["phase"]: entry["status"] for entry in status_list} == {
            "landmark": "not_candidate",
            "remote_category": "not_candidate",
        }

    async def test_default_consent_disabled_wins_over_not_candidate_for_both_phases(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Explizit bindender Ueberschneidungsfall der Spec: consent_disabled UND not_candidate
        # gleichzeitig zutreffend -> consent_disabled gewinnt.
        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        status_list = response.json()["items"][0]["cloud_vision_status"]
        assert {entry["phase"]: entry["status"] for entry in status_list} == {
            "landmark": "consent_disabled",
            "remote_category": "consent_disabled",
        }

    async def test_landmark_result_when_a_landmark_detection_row_exists(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoLandmarkDetection(
                photo_id=photo.id,
                name="Eiffelturm",
                confidence=0.9,
                computed_at=datetime(2023, 6, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "result"
        assert entry["attempted_at"] is not None
        assert entry["error_message"] is None

    async def test_landmark_no_result_when_criterion_score_exists_without_detection_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Datenanomalie-Regressionstest (Teststrategie-Abschnitt der Spec): ein POSITIVER Wert
        # (nicht nur 0.0) ohne PhotoLandmarkDetection-Zeile muss trotzdem no_result liefern - die
        # Kaskade prueft die PRAESENZ der Score-Zeile, nicht den konkreten Wert.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="landmark",
                value=0.7,
                source=CriterionSource.CLOUD,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "no_result"
        assert entry["attempted_at"] is not None

    async def test_landmark_error_status_includes_message_and_timestamp(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        from photosort.models import CloudVisionPhase, PhotoCloudVisionError

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="LandmarkApiError",
                error_message="Anthropic Vision API nicht erreichbar: timeout",
                attempted_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "error"
        assert entry["error_message"] == "Anthropic Vision API nicht erreichbar: timeout"
        assert entry["attempted_at"] is not None

    async def test_landmark_error_persists_even_after_consent_is_disabled_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Explizit bindender Ueberschneidungsfall der Spec: error UND Consent inzwischen
        # deaktiviert -> error bleibt bestehen (Consent ist bereits Default False hier).
        from photosort.models import CloudVisionPhase, PhotoCloudVisionError

        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="LandmarkApiError",
                error_message="Fehler",
                attempted_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "error"

    async def test_landmark_result_persists_even_after_consent_is_disabled_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/architecture/0002-testkonzept.md ("Read-Time-Prioritaets-Kaskade..." fuer ADR
        # 0035): "Erfolgssignal vorhanden UND Consent nachtraeglich deaktiviert -> weiterhin
        # result/no_result (Rang 1 vor Rang 3)" - explizit bindender Ueberschneidungsfall,
        # spiegelbildlich zu test_landmark_error_persists_even_after_consent_is_disabled_again
        # oben (dort Rang 2 vor Rang 3).

        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoLandmarkDetection(
                photo_id=photo.id,
                name="Eiffelturm",
                confidence=0.9,
                computed_at=datetime(2023, 6, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "result"

    async def test_landmark_success_wins_over_an_orphaned_error_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Edge Case der Teststrategie: verwaiste Fehler-Zeile trotz vorhandenem Erfolgssignal -
        # die Kaskade muss trotzdem korrekt "result" liefern (Erfolg schlaegt Fehler, ADR 0035
        # Punkt 1).
        from photosort.models import CloudVisionPhase, PhotoCloudVisionError

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoLandmarkDetection(
                photo_id=photo.id,
                name="Eiffelturm",
                confidence=0.9,
                computed_at=datetime(2023, 6, 1, tzinfo=UTC),
            )
        )
        db_session.add(
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="LandmarkApiError",
                error_message="veraltete Fehler-Zeile",
                attempted_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "result"

    async def test_landmark_not_candidate_when_no_local_criterion_reaches_the_threshold(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_landscape",
                value=0.0,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "not_candidate"

    async def test_landmark_not_candidate_for_an_old_run_with_only_a_content_landscape_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0217, ADR 0047 Punkt 5: die Read-Time-Ableitung folgt derselben
        # umgestellten Vorfilterung wie der Lauf - eine Zeile aus einem ALTEN Lauf (nur
        # content_landscape, hoher Wert) macht ein Foto nicht mehr zum Kandidaten.
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_landscape",
                value=1.0,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "not_candidate"

    async def test_landmark_not_run_when_the_landschaft_criterion_reaches_the_threshold(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        threshold = CRITERIA_REGISTRY["landschaft"].presence_threshold
        assert threshold is not None
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="landschaft",
                value=threshold,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "not_run"

    async def test_landmark_not_run_when_a_local_criterion_reaches_the_threshold(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        threshold = CRITERIA_REGISTRY["gebaeude"].presence_threshold
        assert threshold is not None
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="gebaeude",
                value=threshold,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "not_run"

    async def test_remote_category_result_comes_from_the_cloud_header(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Spec 0427, PR 2 Schritt 2: das Erfolgssignal der Remote-Phase ist ab hier die
        # Kopfzeile mit `source='cloud'` - der Marker ist mit dem Schreibpfad umgezogen.
        # `attempted_at` bleibt eindeutig, ohne Aggregation ueber mehrere Zeilen.
        # Spec 0428, S6: dazu gehoert ab hier die Albumtauglichkeitszeile - dieselbe Bedingung wie
        # in Auswahl und Schaetzung.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _assess_photo(
            db_session, photo, computed_at=datetime(2023, 6, 1, 12, 0, 0), strengths={"tiere": 0.8}
        )
        await _rate_album_suitability(db_session, photo)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "result"
        assert entry["attempted_at"].startswith("2023-06-01")

    async def test_remote_category_result_also_for_a_photo_where_nothing_was_recognized(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Ein Foto, auf dem das Modell nichts deutlich erkannt hat, ist trotzdem erfolgreich
        # verarbeitet - es darf nicht weiterhin als "noch nicht gelaufen" erscheinen. Acht Nullen
        # sind eine BEURTEILUNG und nicht die Abwesenheit einer.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _assess_photo(db_session, photo)
        await _rate_album_suitability(db_session, photo)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "result"

    async def test_a_cloud_header_without_a_level_stays_an_open_candidate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Sicherheitsauflage S6 auf dem LESEpfad: das Skip-Kriterium ist zusammengesetzt, und
        dieser Status macht es sichtbar. Meldete er hier `result`, waere ein Foto, das seine Stufe
        wiederholt unbrauchbar liefert und deshalb bei JEDEM Lauf erneut gesendet wird, in der
        Oberflaeche als erledigt ausgewiesen - waehrend dasselbe Foto in Auswahl und Schaetzung
        wieder Kandidat ist."""
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=100.0,
                exposure=0.0,
                cluster_key="c",
                suggested_status=None,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()
        await _assess_photo(db_session, photo)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "not_run"

    async def test_a_local_header_alone_is_not_a_remote_category_result(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Sicherheitsauflage S14 auf dem LESEpfad: der Kriterien-Lauf schreibt lokale
        Kopfzeilen. Sie sind kein Erfolgssignal der Cloud-Phase - ein Foto mit lokaler Grundlage
        hat noch keinen Cloud-Aufruf gesehen und ist weiterhin Kandidat."""
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=100.0,
                exposure=0.0,
                cluster_key="c",
                suggested_status=None,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()
        await _assess_photo(db_session, photo, source=MotifAssessmentSource.LOCAL, provider=None)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "not_run"

    async def test_remote_category_result_persists_even_after_consent_is_disabled_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/architecture/0002-testkonzept.md ("Read-Time-Prioritaets-Kaskade..." fuer ADR
        # 0035): "Erfolgssignal vorhanden UND Consent nachtraeglich deaktiviert -> weiterhin
        # result/no_result (Rang 1 vor Rang 3)" - Remote-Kategorie-Pendant zu
        # test_landmark_result_persists_even_after_consent_is_disabled_again oben.
        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _assess_photo(db_session, photo, strengths={"tiere": 0.8})
        await _rate_album_suitability(db_session, photo)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "result"

    async def test_remote_category_error_status_includes_message_and_timestamp(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        from photosort.models import CloudVisionPhase, PhotoCloudVisionError

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.REMOTE_CATEGORY,
                error_type="RemoteCategoryClassificationApiError",
                error_message="Fehler beim Klassifizieren",
                attempted_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "error"
        assert entry["error_message"] == "Fehler beim Klassifizieren"

    async def test_remote_category_not_candidate_when_photo_was_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=1.0,
                exposure=0.0,
                suggested_status=RatingStatus.REJECTED,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "not_candidate"

    async def test_remote_category_not_run_when_photo_is_an_ausschuss_survivor(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=1.0,
                exposure=0.0,
                suggested_status=None,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "not_run"
