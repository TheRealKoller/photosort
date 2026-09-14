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
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.feedback import ExchangeKind, MotifErrorCase
from photosort.feedback_log import FrozenContext, record_exchange, record_motif_correction
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Event,
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

        assert [key for key in self._keys(payload) if forbidden in key] == []
