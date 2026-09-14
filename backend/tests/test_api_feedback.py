"""specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md, PR 2 Schritt 2 -
`GET /feedback/diagnosis`.

OHNE PROJEKTPARAMETER, und das ist die Aussage des Endpunkts: Er rechnet projektuebergreifend,
steht aber auf der Projekt-Statistikseite. Der Fall dazu braucht ein Ereignis aus einem ZWEITEN
Projekt - mit nur einem ist eine projektskopierte Umsetzung von der globalen nicht
unterscheidbar.

AUFLAGE S1: Der Router traegt `dependencies=[Depends(get_current_user)]`, steht in
`test_auth_guard.py::_protected_router_operations()` UND hat hier seinen eigenen, pfadbenannten
401-Fall. Die Doppelung traegt, weil der Listeneintrag weder sein eigenes Vergessen noch eine
spaetere Verschiebung des Endpunkts in einen Router ohne `dependencies`-Liste ueberlebt.

AUFLAGE S8: Die Antwort liefert AUSSCHLIESSLICH Aggregate - kein Einzelereignis, kein `user_id`,
keine Foto-Id-Liste, keine Aufschluesselung je Nutzer. Hier als Strukturaussage ueber die
vollstaendige Antwort und nicht als Aufzaehlung der heute vorhandenen Felder: Ein spaeter
ergaenztes Feld faellt sonst durch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.feedback import FEEDBACK_WEIGHT_SPAN, ExchangeKind, MotifErrorCase
from photosort.feedback_log import FrozenContext, record_exchange, record_motif_correction
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Event,
    FeedbackEvent,
    FeedbackEventKind,
    Photo,
    PhotoCriterionScore,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.quality import QUALITY_CRITERION_WEIGHTS
from photosort.quality_weights import store_weights

_URL = "/feedback/diagnosis"
_NOW = datetime(2023, 6, 1, tzinfo=UTC).replace(tzinfo=None)


async def _project_with_two_photos(
    session: AsyncSession, name: str
) -> tuple[int, list[int], int, int]:
    """Projekt, zwei eingeordnete Fotos, erfolgreicher Kriterienlauf mit einem Event."""
    project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
    session.add(project)
    await session.flush()
    photos = [
        Photo(
            project_id=project.id,
            relative_path=f"{name}-{index}.jpg",
            etag=f"etag-{name}-{index}",
            content_length=1,
            taken_at=_NOW,
            taken_at_original=_NOW,
            last_modified=_NOW,
        )
        for index in range(2)
    ]
    session.add_all(photos)
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    event = Event(criterion_scoring_run_id=run.id, position=1, started_at=_NOW, ended_at=_NOW)
    session.add(event)
    await session.flush()
    for index, photo in enumerate(photos):
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo.id,
                event_id=event.id,
                rank_score=0.8 - index * 0.3,
                rank_position=index + 1,
            )
        )
        for key in QUALITY_CRITERION_WEIGHTS:
            session.add(
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key=key,
                    value=0.9 - index * 0.4,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=_NOW,
                )
            )
    await session.flush()
    return project.id, [photo.id for photo in photos], run.id, event.id


async def _user_id(session: AsyncSession) -> int:
    user = User(username=f"nutzer-{datetime.now(UTC).timestamp()}", password_hash="x")
    session.add(user)
    await session.flush()
    return user.id


async def _seed_exchange(session: AsyncSession, name: str, *, level: int = 4) -> None:
    project_id, photo_ids, run_id, event_id = await _project_with_two_photos(session, name)
    await record_exchange(
        session,
        project_id=project_id,
        user_id=await _user_id(session),
        photo_id=photo_ids[0],
        replaced_photo_id=photo_ids[1],
        criterion_scoring_run_id=run_id,
        event_id=event_id,
        level=level,
        replaced_level=4,
        quality=0.5,
        replaced_quality=0.8,
    )
    await session.commit()


def _by(entries: list[dict[str, Any]], field: str, value: str) -> dict[str, Any]:
    return next(entry for entry in entries if entry[field] == value)


class TestTheDiagnosisIsProtected:
    async def test_the_diagnosis_rejects_a_missing_token(
        self, api_client: httpx.AsyncClient
    ) -> None:
        """Auflage S1, pfadbenannt: Ohne Torwaechter waere dies ein unauthentifizierter Lesepfad
        auf Aussagen ueber ALLE Projekte."""
        response = await api_client.get(_URL)

        assert response.status_code == 401


class TestTheEmptyDiagnosis:
    async def test_it_answers_with_zero_corrections(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.get(_URL)

        assert response.status_code == 200
        assert response.json()["correction_count"] == 0

    async def test_every_motif_error_case_and_exchange_kind_is_present(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        """Der Leerzustand ist eine Zahl, keine fehlende Liste: Die Oberflaeche unterscheidet ihn
        an `correction_count` und stellt daraufhin KEINE einzige Zeile dar (D6). Fehlten die
        Eintraege hier, muesste sie ihre Abwesenheit als Null deuten."""
        payload = (await authenticated_api_client.get(_URL)).json()

        assert [entry["case"] for entry in payload["motif_errors"]] == [
            case.value for case in MotifErrorCase
        ]
        assert [entry["kind"] for entry in payload["exchanges"]] == [
            kind.value for kind in ExchangeKind
        ]

    async def test_the_criteria_are_exactly_the_baseline_keys(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        """G2 an der Aussenkante: Der Schluesselsatz ist der der Startwerte - insbesondere steht
        kein Kriterium mit Inhaltsaussage darin."""
        payload = (await authenticated_api_client.get(_URL)).json()

        assert [entry["criterion_key"] for entry in payload["criteria"]] == list(
            QUALITY_CRITERION_WEIGHTS
        )


class TestTheDiagnosisCountsAcrossProjects:
    async def test_events_of_two_projects_are_added_up(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_exchange(db_session, "Costa Rica")
        await _seed_exchange(db_session, "Norwegen")

        payload = (await authenticated_api_client.get(_URL)).json()

        assert payload["correction_count"] == 2
        assert _by(payload["exchanges"], "kind", ExchangeKind.WITHIN_LEVEL.value)["count"] == 2

    async def test_the_endpoint_takes_no_project_parameter(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein Projektparameter waere der Weg, auf dem die Zahlen doch wieder projektweise
        wuerden - ohne dass eine Zahl sich sichtbar aenderte, solange nur ein Projekt Ereignisse
        traegt."""
        await _seed_exchange(db_session, "Costa Rica")

        filtered = await authenticated_api_client.get(_URL, params={"project_id": 999999})

        assert filtered.status_code == 200
        assert filtered.json()["correction_count"] == 1


class TestTheDiagnosisNumbers:
    async def test_an_exchange_reports_its_class_and_the_preferred_lower_rating(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_exchange(db_session, "Costa Rica")

        payload = (await authenticated_api_client.get(_URL)).json()

        assert _by(payload["exchanges"], "kind", ExchangeKind.WITHIN_LEVEL.value) == {
            "kind": ExchangeKind.WITHIN_LEVEL.value,
            "count": 1,
            "preferred_lower_rated_count": 1,
            "quality_incomparable_count": 0,
        }

    async def test_an_across_level_exchange_is_never_added_to_another_class(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_exchange(db_session, "Costa Rica", level=2)

        exchanges = (await authenticated_api_client.get(_URL)).json()["exchanges"]

        assert [entry["count"] for entry in exchanges] == [0, 1, 0]

    async def test_a_within_level_exchange_feeds_the_criterion_agreement(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """D5: die Zahl der tatsaechlich auswertbaren Paare UND die Zustimmungsrate, je
        Kriterium."""
        await _seed_exchange(db_session, "Costa Rica")

        criteria = (await authenticated_api_client.get(_URL)).json()["criteria"]

        assert all(entry["case_count"] == 1 for entry in criteria)
        assert all(entry["agreement"] == 1.0 for entry in criteria)

    async def test_a_motif_correction_reports_its_error_case(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id, photo_ids, _, _ = await _project_with_two_photos(db_session, "Costa Rica")
        await record_motif_correction(
            db_session,
            project_id=project_id,
            photo_id=photo_ids[0],
            user_id=await _user_id(db_session),
            kind=FeedbackEventKind.MOTIF_ADDED,
            motif_key="sonnenuntergang",
            motif_strength=None,
            context=FrozenContext(),
        )
        await db_session.commit()

        payload = (await authenticated_api_client.get(_URL)).json()

        assert payload["correction_count"] == 1
        assert _by(payload["motif_errors"], "case", MotifErrorCase.MISSING.value)["count"] == 1


class TestTheAnswerCarriesAggregatesOnly:
    """Auflage S8. Geprueft wird die VOLLSTAENDIGE Antwort rekursiv und gegen eine Menge
    verbotener Schluessel-Bestandteile, nicht die heutige Feldliste: Ein spaeter ergaenztes
    `user_id` oder eine Foto-Id-Liste faellt sonst nicht auf."""

    _FORBIDDEN = ("user", "photo", "occurred", "event_id")

    # DIE EINE erlaubte Ausnahme, namentlich und abschliessend: `based_on_event_id` ist das
    # Zustimmungs-Token auf den zuletzt beruecksichtigten Ereignisstand (S6) - eine Hochwassermarke
    # ueber das GESAMTE Log, kein lesbares Einzelereignis. Es steht hier als exakter Name und nicht
    # als gelockertes Muster: Ein spaeter ergaenztes `event_id` faellt weiterhin durch.
    _ALLOWED = frozenset({"based_on_event_id"})

    def _keys(self, node: Any) -> list[str]:
        if isinstance(node, dict):
            return [key for key in node] + [
                found for value in node.values() for found in self._keys(value)
            ]
        if isinstance(node, list):
            return [found for item in node for found in self._keys(item)]
        return []

    @pytest.mark.parametrize("forbidden", _FORBIDDEN)
    async def test_no_key_of_the_answer_names_a_user_photo_or_single_event(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        forbidden: str,
    ) -> None:
        await _seed_exchange(db_session, "Costa Rica")

        payload = (await authenticated_api_client.get(_URL)).json()

        assert [
            key for key in self._keys(payload) if forbidden in key and key not in self._ALLOWED
        ] == []


class TestTheDiagnosisCarriesTheWeightPreview:
    """G6 an der Aussenkante: Vor dem Ausloesen ist je Kriterium erkennbar, was gilt, was
    vorgeschlagen wird und wie weit beides auseinanderliegt."""

    async def test_without_any_correction_the_proposal_equals_the_starting_values(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        """G4 an der Aussenkante: Bei null auswertbaren Paaren ist jedes abgeleitete Gewicht EXAKT
        sein Startwert - Gleichheit, kein `approx`."""
        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        assert {entry["criterion_key"]: entry["weight"] for entry in weights["current"]} == (
            QUALITY_CRITERION_WEIGHTS
        )
        assert {entry["criterion_key"]: entry["weight"] for entry in weights["proposed"]} == (
            QUALITY_CRITERION_WEIGHTS
        )
        assert all(entry["delta"] == 0.0 for entry in weights["proposed"])

    async def test_the_key_set_of_both_lists_is_exactly_the_baseline_key_set(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """G2 an der Aussenkante, fuer BEIDE Listen: Insbesondere steht in keiner ein Kriterium
        mit Inhaltsaussage."""
        await _seed_exchange(db_session, "Costa Rica")

        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        for name in ("current", "proposed"):
            assert [entry["criterion_key"] for entry in weights[name]] == list(
                QUALITY_CRITERION_WEIGHTS
            ), name

    async def test_a_within_level_exchange_moves_the_proposal_away_from_the_current_weights(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Das gleichstufige Paar stimmt auf allen sieben Kriterien zu - der Vorschlag liegt
        danach ueber dem geltenden Gewicht, und die Abweichung traegt ihr Vorzeichen."""
        await _seed_exchange(db_session, "Costa Rica")

        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        current = {entry["criterion_key"]: entry["weight"] for entry in weights["current"]}
        for entry in weights["proposed"]:
            assert entry["weight"] > current[entry["criterion_key"]], entry
            assert entry["delta"] == pytest.approx(
                entry["weight"] - current[entry["criterion_key"]]
            )

    async def test_every_proposed_weight_stays_strictly_positive_and_inside_the_band(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """G3: abgewertet, nie invertiert und nie auf null gesetzt - ein Gewicht null liesse das
        Kriterium aus der Renormierung ganz herausfallen."""
        await _seed_exchange(db_session, "Costa Rica")

        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        for entry in weights["proposed"]:
            start = QUALITY_CRITERION_WEIGHTS[entry["criterion_key"]]
            assert entry["weight"] > 0.0
            assert abs(entry["weight"] - start) < FEEDBACK_WEIGHT_SPAN * start


class TestTheAnchorAndTheRevertFlag:
    async def test_an_empty_log_reports_the_anchor_zero(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        """S6: Ohne definierten Wert waere der erste Schreibvorgang ungeprueft."""
        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        assert weights["based_on_event_id"] == 0

    async def test_the_anchor_is_the_highest_id_of_the_whole_log(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """UEBER DAS GESAMTE LOG, nie ueber ein nach Projekt oder Art gefiltertes Maximum: sonst
        gehen Ereignisse unbemerkt durch, und die Fassung entstuende gegen eine Lage, die niemand
        gesehen hat."""
        await _seed_exchange(db_session, "Costa Rica")
        await _seed_exchange(db_session, "Norwegen")
        highest = (await db_session.execute(select(func.max(FeedbackEvent.id)))).scalar_one()

        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        assert weights["based_on_event_id"] == highest

    async def test_without_a_stored_set_the_revert_is_not_offered(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        """G10: Ohne Fassung gibt es nichts zurueckzunehmen - die Schaltflaeche erscheint nicht,
        und der Aufruf wird abgewiesen."""
        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        assert weights["can_revert"] is False

    async def test_with_a_stored_set_the_revert_is_offered(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await store_weights(
            db_session,
            weights=QUALITY_CRITERION_WEIGHTS,
            user_id=await _user_id(db_session),
            based_on_event_id=0,
        )
        await db_session.commit()

        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        assert weights["can_revert"] is True

    async def test_the_current_weights_follow_the_stored_set(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Geltend" heisst die gespeicherte Fassung, nicht der Startwert - sonst zeigte die
        Tabelle nach der ersten Anpassung dauerhaft dieselbe linke Spalte."""
        adjusted = dict(QUALITY_CRITERION_WEIGHTS)
        adjusted["sharpness"] = 1.15
        await store_weights(
            db_session,
            weights=adjusted,
            user_id=await _user_id(db_session),
            based_on_event_id=0,
        )
        await db_session.commit()

        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        current = {entry["criterion_key"]: entry["weight"] for entry in weights["current"]}
        assert current == adjusted

    async def test_the_proposal_is_derived_from_the_starting_values_and_not_from_the_current_ones(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SONST DRIFTETE DER SATZ: Jede Uebernahme verschoebe die Grundlage der naechsten, und
        die Bandbreite aus G3 waere nach wenigen Runden verlassen, ohne dass eine einzelne
        Uebernahme sie je verletzte."""
        adjusted = dict(QUALITY_CRITERION_WEIGHTS)
        adjusted["sharpness"] = 1.15
        await store_weights(
            db_session,
            weights=adjusted,
            user_id=await _user_id(db_session),
            based_on_event_id=0,
        )
        await db_session.commit()

        weights = (await authenticated_api_client.get(_URL)).json()["weights"]

        proposed = {entry["criterion_key"]: entry["weight"] for entry in weights["proposed"]}
        assert proposed == QUALITY_CRITERION_WEIGHTS
