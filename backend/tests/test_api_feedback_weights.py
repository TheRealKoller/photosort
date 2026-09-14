"""specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md, PR 3 Schritt 3 -
`POST /feedback/weights` und `POST /feedback/weights/revert`.

DIE BEIDEN WAECHTER SIND DER GEGENSTAND DIESER DATEI, und beide brechen ohne eigenen Fall still:

- Die Uebernahme prueft `based_on_event_id` auf STRIKTE GLEICHHEIT gegen die hoechste `id` des
  GESAMTEN Logs (S6). Gegen ein nach Projekt oder Art gefiltertes Maximum geprueft, gingen
  Ereignisse unbemerkt durch, und die Fassung entstuende gegen eine Lage, die niemand gesehen
  hat. Der Fall dazu braucht deshalb ein dazwischengekommenes Ereignis aus einem ANDEREN Projekt.
- Die Ruecknahme nennt die Fassung, die zurueckgenommen werden soll (S7). Ohne diesen Waechter
  legen zwei Aufrufe kurz hintereinander erst die Ruecknahme und dann deren Ruecknahme an: Das
  Ergebnis ist der Ausgangszustand, die Kette sieht lueckenlos aus, und keine Anzeige weist das
  als falsch aus.

Die TRAGENDE Haelfte jedes `409`-Falls ist die negative - "und keine neue Fassung geschrieben".
Ein blosser Statuscode-Vergleich bestuende auch gegen eine Umsetzung, die erst schreibt und dann
ablehnt.

DER SERVER RECHNET NEU. Der Body traegt keine Gewichte, und ein Aufruf mit zusaetzlichen Feldern
wird abgewiesen (G7): `weight` ist der einzige Wert, mit dem ein Aufrufer die eigene Korrektur in
der global wirkenden Ableitung ueberproportional zaehlen liesse.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_job_enqueuer
from photosort.main import app
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Event,
    FeedbackEvent,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoRanking,
    Project,
    QualityWeightSet,
    QualityWeightSetOrigin,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.quality import QUALITY_CRITERION_WEIGHTS
from photosort.quality_weights import effective_weights, store_weights
from photosort.worker import rebuild_run_grouping

_ADOPT = "/feedback/weights"
_REVERT = "/feedback/weights/revert"
_DIAGNOSIS = "/feedback/diagnosis"
_NOW = datetime(2026, 6, 1, tzinfo=UTC).replace(tzinfo=None)


class FakeEnqueuer:
    """Zaehlt Einreihungen, statt sie auszufuehren. Die Zusage ist hier eine ABWESENHEIT: Die
    Uebernahme reiht nichts ein (G9)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any) -> None:
        self.calls.append((function, args))


async def _user_id(session: AsyncSession, username: str = "daniel") -> int:
    user = User(username=username, password_hash="x")
    session.add(user)
    await session.flush()
    return user.id


async def _project_with_run(
    session: AsyncSession, name: str, *, photo_count: int = 2
) -> tuple[int, list[int], int, int]:
    """Projekt, Fotos DERSELBEN Modellstufe in EINEM Ereignis, erfolgreicher Kriterienlauf.

    Dieselbe Stufe, damit die Rangfolge allein an den lokalen Kriterien haengt - bei
    verschiedenen Stufen fuehrt die Modellstufe, und eine Gewichtsaenderung bliebe folgenlos."""
    project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
    session.add(project)
    await session.flush()
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    grouping_event = Event(
        criterion_scoring_run_id=run.id, position=1, started_at=_NOW, ended_at=_NOW
    )
    session.add(grouping_event)
    await session.flush()

    photo_ids: list[int] = []
    for index in range(photo_count):
        photo = Photo(
            project_id=project.id,
            relative_path=f"{name}-{index}.jpg",
            etag=f"etag-{name}-{index}",
            content_length=1,
            taken_at=_NOW,
            taken_at_original=_NOW,
            last_modified=_NOW,
        )
        session.add(photo)
        await session.flush()
        photo_ids.append(photo.id)
        session.add(
            PhotoAlbumSuitability(
                photo_id=photo.id,
                level=3,
                reason="Modellbegruendung",
                provider="anthropic",
                computed_at=_NOW,
            )
        )
        # Gegenlaeufige Werte auf zwei gewichteten Kriterien: Eine Verschiebung der Gewichte
        # zueinander veraendert dadurch jeden Qualitaetswert.
        for key, value in (
            ("sharpness", 0.1 + 0.8 * index),
            ("exposure", 0.9 - 0.8 * index),
        ):
            session.add(
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key=key,
                    value=value,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=_NOW,
                )
            )
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo.id,
                event_id=grouping_event.id,
                rank_score=0.5,
                rank_position=index + 1,
                selection_position=index + 1,
            )
        )
    await session.flush()
    return project.id, photo_ids, run.id, grouping_event.id


async def _record_exchange(session: AsyncSession, name: str) -> None:
    """EIN gleichstufiger Austausch in einem eigenen Projekt - eine Paarquelle der Ableitung."""
    from photosort.feedback_log import record_exchange

    project_id, photo_ids, run_id, event_id = await _project_with_run(session, name)
    await record_exchange(
        session,
        project_id=project_id,
        user_id=await _user_id(session, f"nutzer-{name}"),
        photo_id=photo_ids[0],
        replaced_photo_id=photo_ids[1],
        criterion_scoring_run_id=run_id,
        event_id=event_id,
        level=4,
        replaced_level=4,
        quality=0.5,
        replaced_quality=0.8,
    )
    await session.commit()


async def _set_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(QualityWeightSet))).scalar_one()


async def _anchor(client: httpx.AsyncClient) -> int:
    payload = (await client.get(_DIAGNOSIS)).json()
    anchor: int = payload["weights"]["based_on_event_id"]
    return anchor


async def _chain(session: AsyncSession) -> list[QualityWeightSet]:
    return list(
        (await session.execute(select(QualityWeightSet).order_by(QualityWeightSet.id)))
        .scalars()
        .all()
    )


class TestBothWriteEndpointsAreProtected:
    """Auflage S1, pfadbenannt je Endpunkt. Der Listeneintrag in `test_auth_guard.py` traegt die
    Vollstaendigkeit, ueberlebt aber weder sein eigenes Vergessen noch eine spaetere Verschiebung
    des Endpunkts in einen Router ohne `dependencies`-Liste."""

    async def test_the_adoption_rejects_a_missing_token(
        self, api_client: httpx.AsyncClient
    ) -> None:
        response = await api_client.post(_ADOPT, json={"based_on_event_id": 0})

        assert response.status_code == 401

    async def test_the_revert_rejects_a_missing_token(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(_REVERT, json={"reverts_set_id": 1})

        assert response.status_code == 401


class TestTheAdoptionBodyCarriesNothingButTheAnchor:
    """G7/S4: Massenzuweisung ist STRUKTURELL ausgeschlossen, nicht im Handler herausgefiltert."""

    @pytest.mark.parametrize(
        "extra",
        [
            {"weights": {"sharpness": 99.0}},
            {"criterion_key": "sharpness", "weight": 99.0},
            {"user_id": 1},
        ],
        ids=["weights", "single-weight", "user"],
    )
    async def test_an_additional_field_is_refused(
        self, authenticated_api_client: httpx.AsyncClient, extra: dict[str, Any]
    ) -> None:
        response = await authenticated_api_client.post(
            _ADOPT, json={"based_on_event_id": 0, **extra}
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("anchor", [-1, 10**12], ids=["negative", "beyond-the-limit"])
    async def test_an_anchor_outside_the_declared_bounds_is_refused(
        self, authenticated_api_client: httpx.AsyncClient, anchor: int
    ) -> None:
        """Deklarative Grenzen wie in S4: Ein unbeschraenkter Pydantic-`int` erzeugt unter SQLite
        jenseits von 2^63 einen `OverflowError` und damit `500` statt `422`."""
        response = await authenticated_api_client.post(_ADOPT, json={"based_on_event_id": anchor})

        assert response.status_code == 422


class TestTheAnchorIsCheckedAgainstTheWholeLog:
    async def test_a_stale_anchor_is_refused_and_a_current_one_succeeds(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """PAARWEISE in einem Fall. Die TRAGENDE Haelfte ist die negative: "und keine neue
        Fassung geschrieben" - ein blosser Statuscode-Vergleich bestuende auch gegen eine
        Umsetzung, die erst schreibt und dann ablehnt."""
        await _record_exchange(db_session, "Costa Rica")
        stale = await _anchor(authenticated_api_client)
        await _record_exchange(db_session, "Norwegen")

        refused = await authenticated_api_client.post(_ADOPT, json={"based_on_event_id": stale})

        assert refused.status_code == 409
        assert await _set_count(db_session) == 0

        accepted = await authenticated_api_client.post(
            _ADOPT, json={"based_on_event_id": await _anchor(authenticated_api_client)}
        )

        assert accepted.status_code == 200
        assert await _set_count(db_session) == 1

    async def test_an_event_from_another_project_invalidates_the_anchor_too(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Sonst ist eine projektskopierte Konflikterkennung von der globalen nicht zu
        unterscheiden - und der Gewichtssatz gilt global."""
        await _record_exchange(db_session, "Costa Rica")
        stale = await _anchor(authenticated_api_client)
        await _record_exchange(db_session, "Ein ganz anderes Projekt")

        refused = await authenticated_api_client.post(_ADOPT, json={"based_on_event_id": stale})

        assert refused.status_code == 409
        assert await _set_count(db_session) == 0

    async def test_an_empty_log_adopts_with_the_anchor_zero(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S6: Ohne definierten Wert waere ausgerechnet der erste Schreibvorgang ungeprueft."""
        response = await authenticated_api_client.post(_ADOPT, json={"based_on_event_id": 0})

        assert response.status_code == 200
        assert await _set_count(db_session) == 1
        # Bei leerem Log ist der Vorschlag exakt der Startwertsatz - die Fassung ist dieselbe
        # Zahlenreihe, aber sie EXISTIERT nun, und "zuruecksetzen" wird dadurch anbietbar.
        assert await effective_weights(db_session) == QUALITY_CRITERION_WEIGHTS
        assert response.json()["can_revert"] is True


class TestTheServerRecomputesTheProposal:
    async def test_the_written_weights_are_exactly_the_previewed_ones(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """G6: Wird die Anpassung ohne zwischenzeitliche Aenderung uebernommen, sind die
        gespeicherten Werte EXAKT die zuvor angezeigten - Gleichheit, kein `approx`."""
        await _record_exchange(db_session, "Costa Rica")
        preview = (await authenticated_api_client.get(_DIAGNOSIS)).json()["weights"]
        previewed = {entry["criterion_key"]: entry["weight"] for entry in preview["proposed"]}

        response = await authenticated_api_client.post(
            _ADOPT, json={"based_on_event_id": preview["based_on_event_id"]}
        )

        assert response.status_code == 200
        assert await effective_weights(db_session) == previewed

    async def test_the_new_set_records_the_anchor_it_was_adopted_against(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await _record_exchange(db_session, "Costa Rica")
        anchor = await _anchor(authenticated_api_client)

        await authenticated_api_client.post(_ADOPT, json={"based_on_event_id": anchor})

        stored = (await _chain(db_session))[0]
        assert stored.based_on_event_id == anchor
        assert stored.origin is QualityWeightSetOrigin.FEEDBACK
        assert stored.reverts_set_id is None

    async def test_a_criterion_added_after_a_stored_set_keeps_its_starting_value(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """PAARWEISE in einem Fall (G2): Ein der Fassung unbekannter Startwertschluessel behaelt
        seinen Startwert, UND ein den Startwerten unbekannter Schluessel der Fassung erscheint
        nicht im wirksamen Satz. Die erste Haelfte allein bestuende auch gegen
        `{**startwerte, **fassung}` - und genau das ist der Weg, auf dem ein entfallenes
        Kriterium ein Gewicht behaelt."""
        await store_weights(
            db_session,
            weights={"sharpness": 1.25, "ein_entfallenes_kriterium": 9.0},
            user_id=await _user_id(db_session),
            based_on_event_id=0,
        )
        await db_session.commit()

        weights = (await authenticated_api_client.get(_DIAGNOSIS)).json()["weights"]

        current = {entry["criterion_key"]: entry["weight"] for entry in weights["current"]}
        assert current["sharpness"] == 1.25
        assert current["exposure"] == QUALITY_CRITERION_WEIGHTS["exposure"]
        assert "ein_entfallenes_kriterium" not in current


class TestTheRevertIsAToggle:
    async def test_it_writes_a_new_set_and_deletes_none(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        first = await store_weights(
            db_session,
            weights={**QUALITY_CRITERION_WEIGHTS, "sharpness": 1.2},
            user_id=await _user_id(db_session),
            based_on_event_id=0,
        )
        await db_session.commit()

        response = await authenticated_api_client.post(_REVERT, json={"reverts_set_id": first.id})

        assert response.status_code == 200
        chain = await _chain(db_session)
        assert [entry.origin for entry in chain] == [
            QualityWeightSetOrigin.FEEDBACK,
            QualityWeightSetOrigin.REVERT,
        ]
        assert chain[1].reverts_set_id == first.id
        assert await effective_weights(db_session) == QUALITY_CRITERION_WEIGHTS

    async def test_reverting_twice_walks_the_full_value_sequence_without_deleting_anything(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """G10, die vollstaendige Wertefolge: Der zweite Druck fuehrt auf die Werte zurueck, von
        denen der erste zurueckgesetzt hat - er geht NICHT eine weitere Fassung rueckwaerts. Fuenf
        Fassungen bleiben in der Kette stehen; geloescht wird keine."""
        user_id = await _user_id(db_session)
        for value in (1.1, 1.2, 1.3):
            await store_weights(
                db_session,
                weights={**QUALITY_CRITERION_WEIGHTS, "sharpness": value},
                user_id=user_id,
                based_on_event_id=0,
            )
        await db_session.commit()

        third = (await _chain(db_session))[2]
        first_revert = await authenticated_api_client.post(
            _REVERT, json={"reverts_set_id": third.id}
        )
        assert first_revert.status_code == 200
        assert (await effective_weights(db_session))["sharpness"] == 1.2

        fourth = (await _chain(db_session))[3]
        second_revert = await authenticated_api_client.post(
            _REVERT, json={"reverts_set_id": fourth.id}
        )

        assert second_revert.status_code == 200
        assert (await effective_weights(db_session))["sharpness"] == 1.3
        chain = await _chain(db_session)
        assert len(chain) == 5
        assert [entry.origin for entry in chain] == [
            QualityWeightSetOrigin.FEEDBACK,
            QualityWeightSetOrigin.FEEDBACK,
            QualityWeightSetOrigin.FEEDBACK,
            QualityWeightSetOrigin.REVERT,
            QualityWeightSetOrigin.REVERT,
        ]

    async def test_a_revert_without_any_stored_set_is_refused(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """G10: Ohne Fassung gibt es nichts zurueckzunehmen. Die Oberflaeche bietet es nicht an
        (`can_revert`), und der Aufruf wird trotzdem abgewiesen - eine Schaltflaeche, die nicht
        erscheint, ist keine Zugangskontrolle."""
        response = await authenticated_api_client.post(_REVERT, json={"reverts_set_id": 1})

        assert response.status_code == 409
        assert await _set_count(db_session) == 0

    async def test_a_revert_naming_a_set_that_is_no_longer_current_is_refused(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """AUFLAGE S7, paarweise: Ohne diesen Waechter legen zwei Aufrufe kurz hintereinander
        (Doppelklick, zweites Geraet, Wiederholung nach Zeitueberschreitung) erst die Ruecknahme
        und dann deren Ruecknahme an - das Ergebnis ist der Ausgangszustand, die Kette sieht
        lueckenlos aus, und keine Anzeige weist das als falsch aus."""
        user_id = await _user_id(db_session)
        outdated = await store_weights(
            db_session,
            weights={**QUALITY_CRITERION_WEIGHTS, "sharpness": 1.1},
            user_id=user_id,
            based_on_event_id=0,
        )
        await store_weights(
            db_session,
            weights={**QUALITY_CRITERION_WEIGHTS, "sharpness": 1.2},
            user_id=user_id,
            based_on_event_id=0,
        )
        await db_session.commit()

        refused = await authenticated_api_client.post(_REVERT, json={"reverts_set_id": outdated.id})

        assert refused.status_code == 409
        assert await _set_count(db_session) == 2
        assert (await effective_weights(db_session))["sharpness"] == 1.2

    @pytest.mark.parametrize(
        "extra",
        [{"weights": {"sharpness": 99.0}}, {"origin": "feedback"}],
        ids=["weights", "origin"],
    )
    async def test_an_additional_field_is_refused(
        self, authenticated_api_client: httpx.AsyncClient, extra: dict[str, Any]
    ) -> None:
        response = await authenticated_api_client.post(_REVERT, json={"reverts_set_id": 1, **extra})

        assert response.status_code == 422


class TestTheAdoptionWritesNothingButTheNewSet:
    """G9, ZWEISEITIG. Die erste Haelfte allein bestuende auch gegen eine Umsetzung, die Gewichte
    speichert, die nie jemand liest - bei einem neu eingefuehrten Persistenzweg der
    wahrscheinlichste Fehler."""

    async def _ranking_map(
        self, session: AsyncSession
    ) -> dict[int, tuple[float | None, int | None, int | None, int]]:
        rows = (await session.execute(select(PhotoRanking))).scalars().all()
        return {
            row.photo_id: (row.rank_score, row.rank_position, row.selection_position, row.event_id)
            for row in rows
        }

    async def test_no_ranking_moves_no_run_appears_and_nothing_is_enqueued(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: enqueuer
        try:
            await _record_exchange(db_session, "Costa Rica")
            before = await self._ranking_map(db_session)
            runs_before = (
                await db_session.execute(select(func.count()).select_from(CriterionScoringRun))
            ).scalar_one()

            response = await authenticated_api_client.post(
                _ADOPT, json={"based_on_event_id": await _anchor(authenticated_api_client)}
            )

            assert response.status_code == 200
            assert await self._ranking_map(db_session) == before
            assert (
                await db_session.execute(select(func.count()).select_from(CriterionScoringRun))
            ).scalar_one() == runs_before
            assert enqueuer.calls == []
        finally:
            app.dependency_overrides.pop(get_job_enqueuer, None)

    async def test_the_next_run_actually_computes_with_the_new_weights(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """DIE ZWEITE HAELFTE: "wirkt erst beim naechsten Durchlauf" ist nur dann eine Aussage,
        wenn es beim naechsten Durchlauf auch tatsaechlich wirkt.

        Die Gewichte stammen hier aus einem echten Austausch-Ereignis und sind deshalb KEINE
        gleichmaessige Streckung - die waere nachweislich wirkungslos
        (`test_quality.py::TestTheRenormalizationInvariance`)."""
        project_id, _, run_id, _ = await _project_with_run(db_session, "Costa Rica")
        await _record_exchange(db_session, "Norwegen")
        await rebuild_run_grouping(db_session, project_id)
        await db_session.commit()
        before = await self._ranking_map(db_session)

        adopted = await authenticated_api_client.post(
            _ADOPT, json={"based_on_event_id": await _anchor(authenticated_api_client)}
        )
        assert adopted.status_code == 200
        assert await self._ranking_map(db_session) == before

        await rebuild_run_grouping(db_session, project_id)
        await db_session.commit()

        after = await self._ranking_map(db_session)
        assert set(after) == set(before)
        assert any(before[photo_id][0] != after[photo_id][0] for photo_id in before), (
            "kein einziger rank_score hat sich bewegt - die gespeicherte Fassung liest niemand"
        )
        run = await db_session.get(CriterionScoringRun, run_id)
        assert run is not None
        assert run.quality_weight_set_id == (await _chain(db_session))[-1].id


class TestTheLogItselfIsNeverTouched:
    async def test_neither_endpoint_writes_or_removes_a_feedback_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Das Log ist append-only und gehoert der Nacharbeit - eine Gewichtsanpassung ist keine
        Korrektur an einem Bild und darf in keiner Fallzahl auftauchen."""
        await _record_exchange(db_session, "Costa Rica")
        before = (
            await db_session.execute(select(func.count()).select_from(FeedbackEvent))
        ).scalar_one()

        adopted = await authenticated_api_client.post(
            _ADOPT, json={"based_on_event_id": await _anchor(authenticated_api_client)}
        )
        await authenticated_api_client.post(
            _REVERT, json={"reverts_set_id": (await _chain(db_session))[-1].id}
        )

        assert adopted.status_code == 200
        assert (
            await db_session.execute(select(func.count()).select_from(FeedbackEvent))
        ).scalar_one() == before
