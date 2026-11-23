"""Demo-Zustands-Seeder: Endauswahl, Nacharbeitsprotokoll, Gewichtssatz, Albumentwurf-Zustaende,
abgeschlossene Klassifizierungspruefung.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.album_selection import SelectionState, selection_state
from photosort.classification_comparison import PhotoComparison, compare_review
from photosort.demo_state import (
    RATED_PROJECT_NAME,
    purge_demo_state,
    rebuild_demo_state,
)
from photosort.duplicates import survives_ausschuss
from photosort.feedback_log import load_diagnosis
from photosort.models import (
    ClassificationReview,
    ClassificationReviewCase,
    ClassificationReviewPurpose,
    ClassificationReviewResult,
    ClassificationReviewResultStrength,
    ClassificationReviewSide,
    ClassificationReviewSideKind,
    ClassificationReviewVerdict,
    CriterionScoringRun,
    FeedbackEvent,
    FeedbackEventKind,
    FinalSelectionDecision,
    Photo,
    PhotoMotifCorrection,
    PhotoRanking,
    PhotoScore,
    Rating,
    RatingStatus,
    ScanStatus,
    User,
)
from photosort.motifs import MOTIF_REGISTRY
from photosort.quality import QUALITY_CRITERION_WEIGHTS
from photosort.quality_weights import store_weights
from photosort.security import create_access_token
from tests.support.demo_state_rows import _make_user, _photos_of, _project


class TestTheDemoStateCarriesTheFinalSelection:
    """specs/features/0431-endauswahl-gemeinsam.md, Zusicherung 21.

    Der Seeder legt fuer den bestehenden Block ALLEN Nutzern DIESELBEN Bewertungen an - eine
    Eigenschaft, die bleibt. Ohne einen benannten Dissens daneben zeigte die Arbeitssicht der
    Endauswahl auf der Demo-Instanz dauerhaft "keine Unterschiede", und KEIN Test wuerde rot: die
    Sichtpruefung besuchte eine Seite, die nichts zu tun hat, und haette keinen Anhaltspunkt,
    dass das falsch ist."""

    @staticmethod
    async def _state_of_the_rated_project(
        session: AsyncSession,
    ) -> tuple[dict[int, SelectionState], dict[int, bool]]:
        """Der Zustand jedes Fotos des bewerteten Projekts - ueber DIESELBE reine Funktion, die
        auch der Lesepfad benutzt, nie ueber eine zweite Nachbildung hier."""
        photos = await _photos_of(session, RATED_PROJECT_NAME)
        photo_ids = [photo.id for photo in photos]
        rankings = {
            row.photo_id: row
            for row in (
                await session.execute(
                    select(PhotoRanking).where(PhotoRanking.photo_id.in_(photo_ids))
                )
            )
            .scalars()
            .all()
        }
        decisions = {
            row.photo_id: row.included
            for row in (
                await session.execute(
                    select(FinalSelectionDecision).where(
                        FinalSelectionDecision.photo_id.in_(photo_ids)
                    )
                )
            )
            .scalars()
            .all()
        }
        ratings: dict[int, list[Rating]] = {}
        for rating in (
            (await session.execute(select(Rating).where(Rating.photo_id.in_(photo_ids))))
            .scalars()
            .all()
        ):
            ratings.setdefault(rating.photo_id, []).append(rating)
        user_count = len((await session.execute(select(User))).scalars().all())

        states = {}
        for photo_id in photo_ids:
            rows = ratings.get(photo_id, [])
            ranking = rankings.get(photo_id)
            states[photo_id] = selection_state(
                taken=sum(1 for r in rows if r.status is RatingStatus.ALBUM_WORTHY),
                rejected=sum(1 for r in rows if r.status is RatingStatus.REJECTED),
                user_count=user_count,
                proposed=ranking is not None and ranking.selection_position is not None,
                decision=decisions.get(photo_id),
            )
        return states, decisions

    async def test_all_four_states_of_the_final_selection_occur(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """KARDINALITAETSFALL ueber die vier benannten Zustaende: strittig, gemeinsam entschieden
        und drin, einig aber herausgenommen, und einig drin ohne Zutun. Fehlt einer, ist die
        Sichtpruefung blind fuer genau die Darstellung, die es fuer ihn gibt."""
        await _make_user(db_session, "daniel")
        await _make_user(db_session, "zweiter-nutzer")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        states, decisions = await self._state_of_the_rated_project(db_session)

        contested = [pid for pid, state in states.items() if state.contested]
        decided_in = [pid for pid, included in decisions.items() if included]
        decided_out = [pid for pid, included in decisions.items() if not included]
        agreed_in = [
            pid for pid, state in states.items() if state.included and pid not in decisions
        ]

        assert contested, "kein strittiges Foto - die Arbeitssicht bliebe dauerhaft leer"
        assert decided_in, "kein gemeinsam entschiedenes Foto mit `included=true`"
        assert decided_out, "kein ausdruecklich herausgenommenes Foto"
        assert agreed_in, "kein einig-drinnes Foto ohne Entscheidung"

    async def test_a_decided_photo_is_no_longer_contested(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Zustand "gemeinsam entschieden, drin" entsteht auf einem Foto, das OHNE die
        Entscheidung strittig waere - sonst zeigte die Demo die Ueberschreibung gar nicht."""
        await _make_user(db_session, "daniel")
        await _make_user(db_session, "zweiter-nutzer")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        states, decisions = await self._state_of_the_rated_project(db_session)

        for photo_id in decisions:
            assert not states[photo_id].contested, photo_id
            assert states[photo_id].included is decisions[photo_id], photo_id

    async def test_two_rebuilds_put_the_same_photo_ids_into_the_same_roles(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Zusicherung 21, zweite Haelfte: Die Auswahl stammt aus dem TATSAECHLICHEN Vorschlag -
        genau dort wird eine `set`-Iteration unbemerkt sprunghaft, und die Sichtpruefung zeigte
        von Lauf zu Lauf andere Bilder in anderen Rollen."""
        await _make_user(db_session, "daniel")
        await _make_user(db_session, "zweiter-nutzer")

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        first_states, first_decisions = await self._state_of_the_rated_project(db_session)
        first = (
            sorted(pid for pid, s in first_states.items() if s.contested),
            sorted(first_decisions.items()),
        )

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        second_states, second_decisions = await self._state_of_the_rated_project(db_session)
        second = (
            sorted(pid for pid, s in second_states.items() if s.contested),
            sorted(second_decisions.items()),
        )

        assert first[0], "ohne strittiges Foto prueft der Determinismusfall nichts"
        # Die Foto-Ids selbst wandern beim Neuaufbau (die Zeilen werden geloescht und neu
        # angelegt); verglichen wird deshalb die STRUKTUR: gleich viele Fotos in gleichen Rollen,
        # an gleicher Stelle der nach Id sortierten Fotoliste.
        photos = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]
        second_offsets = (
            [photos.index(pid) for pid in second[0]],
            [(photos.index(pid), included) for pid, included in second[1]],
        )
        assert second_offsets[0] == sorted(second_offsets[0])
        assert len(second[0]) == len(first[0])
        assert len(second[1]) == len(first[1])

    async def test_the_block_writes_nothing_without_any_user(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Seeder legt selbst nie ein Konto an. Ohne Nutzer gibt es keine Entwuerfe, ueber die
        man uneins sein koennte."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        assert (await db_session.execute(select(FinalSelectionDecision))).scalars().all() == []

    async def test_the_block_writes_nothing_with_exactly_one_user(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Bei `n = 1` ist Dissens ARITHMETISCH unmoeglich: jedes vorgeschlagene, unangefasste
        Foto ist in der Endauswahl, und nichts ist strittig. Ein Block, der hier trotzdem
        schriebe, erzeugte einen Zustand, den die Anwendung selbst nie herstellt."""
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        states, decisions = await self._state_of_the_rated_project(db_session)

        assert decisions == {}
        assert not any(state.contested for state in states.values())

    async def test_the_project_deletion_removes_the_decisions_too(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Seeder raeumt ueber `project_deletion` auf - hier am Demo-Bestand. Ohne diese
        Anweisung ueberlebten die gemeinsamen Entscheidungen ueber geloeschte Familienfotos die
        Projektloeschung."""
        await _make_user(db_session, "daniel")
        await _make_user(db_session, "zweiter-nutzer")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert (await db_session.execute(select(FinalSelectionDecision))).scalars().all() != []

        await purge_demo_state(db_session, tmp_path)
        await db_session.commit()

        assert (await db_session.execute(select(FinalSelectionDecision))).scalars().all() == []
        assert (await db_session.execute(select(User))).scalars().all() != []


class TestTheDemoStateCarriesTheReworkLog:
    """specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md: das Ereignis-Log.

    OHNE SUBSTANZ zeigt der Diagnoseabschnitt auf der Demo-Instanz dauerhaft seinen Nullzustand,
    und KEIN Test wuerde rot - die Pruefstack-Spezifikation misst die Statistik-Route bereits und
    maesse dann dauerhaft den Leerzustand. Das ist keine Kosmetik, sondern die einzige Stelle, an
    der die Abwesenheit auffaellt."""

    async def _events(self, session: AsyncSession) -> list[FeedbackEvent]:
        return list(
            (await session.execute(select(FeedbackEvent).order_by(FeedbackEvent.id)))
            .scalars()
            .all()
        )

    async def _seed_two_users(self, session: AsyncSession, tmp_path: Path) -> None:
        await _make_user(session, "daniel")
        await _make_user(session, "zweiter-nutzer")
        await rebuild_demo_state(session, tmp_path, large_collection_photo_count=3)

    async def test_all_three_exchange_classes_are_present(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Diagnose weist die drei Tauscharten GETRENNT aus und summiert sie nie. Geprueft
        wird ueber die eingefrorenen Stufenpaare und nicht ueber eine abgezaehlte Anzahl: Die
        unbestimmte Klasse entsteht allein daraus, dass eine der beiden Stufen fehlt, und genau
        das ist die Eigenschaft, die still verschwinden koennte."""
        await self._seed_two_users(db_session, tmp_path)

        exchanges = [
            row for row in await self._events(db_session) if row.kind is FeedbackEventKind.EXCHANGED
        ]

        assert len(exchanges) == 3
        assert any(
            row.level is not None and row.level == row.replaced_level for row in exchanges
        ), "keine gleichstufige Tauschart im Demo-Bestand"
        assert any(
            row.level is not None
            and row.replaced_level is not None
            and row.level != row.replaced_level
            for row in exchanges
        ), "keine stufenuebergreifende Tauschart im Demo-Bestand"
        assert any(row.level is None or row.replaced_level is None for row in exchanges), (
            "keine unbestimmte Tauschart im Demo-Bestand"
        )

    async def test_every_exchange_names_two_different_photos_of_the_same_event(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe: Der
        Endpunkt weist ein Paar aus verschiedenen Ereignissen und ein Bild gegen sich selbst
        ausdruecklich ab."""
        await self._seed_two_users(db_session, tmp_path)
        events_by_photo = {
            photo_id: event_id
            for photo_id, event_id in (
                await db_session.execute(select(PhotoRanking.photo_id, PhotoRanking.event_id))
            ).all()
        }

        for row in await self._events(db_session):
            if row.kind is not FeedbackEventKind.EXCHANGED:
                continue
            assert row.replaced_photo_id is not None
            assert row.photo_id != row.replaced_photo_id
            assert row.event_id == events_by_photo[row.photo_id]
            assert row.event_id == events_by_photo[row.replaced_photo_id]

    async def test_a_motif_error_case_is_present_with_its_frozen_model_strength(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Ein `motif_dropped` auf ein Motiv, das das Modell mit Staerke genannt hat, ist der
        Fehlerfall "vom Modell genannt und von uns weggenommen". Ohne eingefrorene Staerke waere
        er nach dem naechsten Lauf nicht mehr von "zu schwach" zu unterscheiden."""
        await self._seed_two_users(db_session, tmp_path)

        dropped = [
            row
            for row in await self._events(db_session)
            if row.kind is FeedbackEventKind.MOTIF_DROPPED
        ]

        assert dropped
        assert all(row.motif_key in MOTIF_REGISTRY for row in dropped)
        assert any(row.motif_strength is not None for row in dropped)

    async def test_a_withdrawn_correction_leaves_its_two_events_and_no_state_row(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """DIE Aussage, fuer die es das Log ueberhaupt gibt: Der Bestand zeigt eine
        zurueckgenommene Korrektur nicht mehr - das Log schon, und beide Ereignisse stehen
        nebeneinander."""
        await self._seed_two_users(db_session, tmp_path)

        rows = await self._events(db_session)
        added = [row for row in rows if row.kind is FeedbackEventKind.MOTIF_ADDED]
        withdrawn = [
            row for row in rows if row.kind is FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN
        ]

        assert len(added) == len(withdrawn) == 1
        assert (added[0].photo_id, added[0].motif_key) == (
            withdrawn[0].photo_id,
            withdrawn[0].motif_key,
        )
        assert added[0].id < withdrawn[0].id
        corrections = (
            (
                await db_session.execute(
                    select(PhotoMotifCorrection).where(
                        PhotoMotifCorrection.photo_id == added[0].photo_id,
                        PhotoMotifCorrection.motif_key == added[0].motif_key,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert corrections == []

    async def test_the_seeded_log_fills_every_number_of_the_diagnosis(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Nachweis am ERGEBNIS statt an den geschriebenen Zeilen: Die Ereignisse koennen
        vollzaehlig dastehen und die Diagnose trotzdem ihren Nullzustand zeigen - etwa weil kein
        `motif_dropped` auf ein tatsaechlich getragenes Motiv faellt (dann ist es kein
        Modellfehler) oder weil dem gleichstufigen Austausch die Kriterienwerte fehlen (dann
        bildet er kein auswertbares Paar). Genau das saehe auf der Demo-Instanz aus wie "noch nie
        korrigiert", und die Pruefstack-Spezifikation maesse es, ohne rot zu werden."""
        await self._seed_two_users(db_session, tmp_path)

        diagnosis = await load_diagnosis(
            db_session, criterion_keys=tuple(QUALITY_CRITERION_WEIGHTS)
        )

        assert diagnosis.correction_count > 0
        assert sum(diagnosis.motif_errors.values()) > 0
        assert all(stats.count > 0 for stats in diagnosis.exchanges.values())
        assert any(entry.case_count > 0 for entry in diagnosis.criteria.values())

    async def test_every_joint_decision_has_its_event_and_none_of_them_names_a_user(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """S9 am Demo-Bestand, beide Richtungen in einem Fall: Die Ereignisse der gemeinsamen
        Entscheidung tragen keinen Nutzer, alle uebrigen tragen einen."""
        await self._seed_two_users(db_session, tmp_path)
        decisions = (await db_session.execute(select(FinalSelectionDecision))).scalars().all()
        assert decisions

        rows = await self._events(db_session)
        final = [
            row
            for row in rows
            if row.kind
            in {FeedbackEventKind.FINAL_DECISION_IN, FeedbackEventKind.FINAL_DECISION_OUT}
        ]

        assert len(final) == len(decisions)
        assert all(row.user_id is None for row in final)
        assert all(row.user_id is not None for row in rows if row not in final)

    async def test_the_log_stays_empty_without_a_user_except_for_the_joint_decisions(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Ohne Nutzerkonto legt der Seeder keines an (ein Konto mit bekannten Zugangsdaten waere
        genau das Sicherheitsproblem, gegen das die Sperre antritt) - und ohne Nutzer gibt es
        weder Austausche noch Motivkorrekturen. Der Dissens-Block schreibt bei `n < 2` ebenfalls
        nichts, also bleibt das Log hier vollstaendig leer."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        assert await self._events(db_session) == []

    async def test_the_project_deletion_removes_the_log_too(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """S13: Ohne die Anweisung ueberleben Aussagen ueber geloeschte Familienfotos ihr
        Projekt."""
        await self._seed_two_users(db_session, tmp_path)
        assert await self._events(db_session) != []

        await purge_demo_state(db_session, tmp_path)
        await db_session.commit()

        assert await self._events(db_session) == []


class TestTheDemoStateRespectsAStoredWeightSet:
    """specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md, PR 3 Schritt 2.

    Der Seeder rechnet den Qualitaetswert selbst, statt ihn zu wuerfeln - er muss deshalb
    DIESELBE Herkunft der Gewichte benutzen wie der Lauf. Eine hier stehengebliebene
    Modulkonstante zeigte auf der Demo-Instanz Zahlen, die die Anwendung nach der naechsten
    Anpassung nie wieder erzeugte, und kein Verhaltensfall des Bestands wuerde rot: Ohne
    gespeicherte Fassung sind beide Wege identisch.

    Die gewaehlten Gewichte sind ausdruecklich keine gleichmaessige Streckung - die ist
    nachweislich wirkungslos (`test_quality.py::TestTheRenormalizationInvariance`)."""

    _TILTED = {"sharpness": 1.9, "exposure": 0.1}

    async def _rank_scores(self, session: AsyncSession) -> dict[int, float | None]:
        rows = (await session.execute(select(PhotoRanking))).scalars().all()
        return {row.photo_id: row.rank_score for row in rows}

    async def test_the_seeded_scores_follow_the_stored_set(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        before = await self._rank_scores(db_session)
        user = await _make_user(db_session, "gewichts-nutzer")
        await store_weights(db_session, weights=self._TILTED, user_id=user.id, based_on_event_id=0)
        await db_session.flush()

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        after = await self._rank_scores(db_session)
        assert sorted(before.values(), key=lambda value: (value is None, value)) != sorted(
            after.values(), key=lambda value: (value is None, value)
        )

    async def test_the_seeded_run_records_the_set_it_used(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Lauf-Zeile der Demo traegt denselben Beleg wie die eines echten Laufs - sonst
        erzeugte der Seeder einen Zustand, den die Anwendung selbst nie schriebe.

        Geprueft am Lauf des BEWERTETEN Projekts: Nur er rechnet Qualitaetswerte. Die Laeufe der
        uebrigen Demo-Zustaende (leer, gross, fehlgeschlagen) tragen folgerichtig `NULL` - sie
        haben keine Gewichte benutzt."""
        user = await _make_user(db_session, "gewichts-nutzer")
        written = await store_weights(
            db_session, weights=self._TILTED, user_id=user.id, based_on_event_id=0
        )
        await db_session.flush()

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        rated = await _project(db_session, RATED_PROJECT_NAME)
        run = (
            await db_session.execute(
                select(CriterionScoringRun).where(CriterionScoringRun.project_id == rated.id)
            )
        ).scalar_one()
        assert run.quality_weight_set_id == written.id


class TestTheDemoStateShowsEveryStateOfTheAlbumDraft:
    """specs/features/0558-album-entwurf-verstaendlich.md: Gestrichen-Zeile, Eingriffszaehler und
    Hinzufuegen im leeren Event sind in E2E und `browse-app` nur sichtbar, wenn der Bestand sie
    traegt. Geprueft ueber den LESEPFAD als erster Nutzer - genau die Sicht, die die Pruefstacks
    anmelden -, nie ueber eine Nachbildung des Praedikats hier."""

    @staticmethod
    async def _views(
        session: AsyncSession, client: httpx.AsyncClient, tmp_path: Path
    ) -> tuple[dict[str, Any], dict[str, Any], int, int]:
        first = await _make_user(session, "daniel")
        second = await _make_user(session, "zweiter-nutzer")
        await rebuild_demo_state(session, tmp_path, large_collection_photo_count=3)
        await session.commit()
        project = await _project(session, RATED_PROJECT_NAME)
        client.headers["Authorization"] = f"Bearer {create_access_token(first)}"
        draft = await client.get(f"/projects/{project.id}/album-draft")
        selection = await client.get(f"/projects/{project.id}/album-selection")
        assert draft.status_code == selection.status_code == 200
        return draft.json(), selection.json(), first.id, second.id

    @staticmethod
    def _own(item: dict[str, Any], user_id: int) -> str | None:
        return next((r["status"] for r in item["ratings"] if r["user_id"] == user_id), None)

    async def test_the_draft_of_the_first_user_carries_all_four_cases(
        self, db_session: AsyncSession, api_client: httpx.AsyncClient, tmp_path: Path
    ) -> None:
        draft, _selection, me, _other = await self._views(db_session, api_client, tmp_path)

        def proposed(item: dict[str, Any]) -> bool:
            return bool(item["ranking"] and item["ranking"]["proposed"])

        items = draft["items"]
        struck_proposed = [i for i in items if self._own(i, me) == "rejected" and proposed(i)]
        taken_unproposed = [
            i for i in items if self._own(i, me) == "album_worthy" and not proposed(i)
        ]
        struck_unproposed = [
            i
            for i in items
            if self._own(i, me) == "rejected" and not proposed(i) and i["ranking"] is not None
        ]
        events_with_proposal = {i["event"]["id"] for i in items if proposed(i)}
        events_without_proposal = [
            event for event in draft["events"] if event["id"] not in events_with_proposal
        ]

        assert struck_proposed, "kein gestrichenes vorgeschlagenes Foto"
        assert taken_unproposed, "kein aufgenommenes nicht vorgeschlagenes Foto"
        assert struck_unproposed, "kein gestrichenes nicht vorgeschlagenes Foto mit Rangzeile"
        assert events_without_proposal, "kein Event ohne Vorschlag"

    async def test_the_final_selection_shows_a_proposal_stance_and_a_not_in_draft_stance(
        self, db_session: AsyncSession, api_client: httpx.AsyncClient, tmp_path: Path
    ) -> None:
        """Die Haltungszeilen "Vorschlag" (unberuehrt, vorgeschlagen) und "Nicht im Entwurf"
        (unberuehrt, nicht vorgeschlagen) - je Teilnehmer abgeleitet wie in der Ansicht."""
        _draft, selection, me, other = await self._views(db_session, api_client, tmp_path)

        stances = [
            (bool(item["ranking"] and item["ranking"]["proposed"]), self._own(item, user_id))
            for item in selection["items"]
            for user_id in (me, other)
        ]

        assert (True, None) in stances, "keine Haltung 'Vorschlag'"
        assert (False, None) in stances, "keine Haltung 'Nicht im Entwurf'"


class TestTheDemoStateCarriesACompletedClassificationReview:
    """specs/features/0616-klassifizierungsverfahren-vergleichen.md, Stufe 7: Liste, Fallansicht
    und Urteil sind im Pruefstack und in `browse-app` nur pruefbar, wenn der Bestand eine
    ABGESCHLOSSENE Pruefung traegt - als gespeichertes Ergebnis, nie durch einen ausgeloesten Lauf.
    """

    @staticmethod
    async def _review(session: AsyncSession, tmp_path: Path) -> tuple[ClassificationReview, User]:
        user = await _make_user(session, "daniel")
        await rebuild_demo_state(session, tmp_path, large_collection_photo_count=3)
        project = await _project(session, RATED_PROJECT_NAME)
        reviews = (
            (
                await session.execute(
                    select(ClassificationReview).where(
                        ClassificationReview.project_id == project.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(reviews) == 1
        return reviews[0], user

    @staticmethod
    async def _cases(session: AsyncSession, review_id: int) -> list[ClassificationReviewCase]:
        return list(
            (
                await session.execute(
                    select(ClassificationReviewCase)
                    .where(ClassificationReviewCase.review_id == review_id)
                    .order_by(ClassificationReviewCase.id)
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def _review_photo_ids(session: AsyncSession, project_id: int) -> list[int]:
        """Die Pruefmenge so, wie der Pruefjob sie einfriert - unabhaengig nachgebaut."""
        return list(
            (
                await session.execute(
                    select(Photo.id)
                    .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                    .where(Photo.project_id == project_id, survives_ausschuss())
                    .order_by(Photo.id)
                )
            )
            .scalars()
            .all()
        )

    async def test_the_review_is_finished_and_compares_eye_with_cloud(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        review, user = await self._review(db_session, tmp_path)
        sides = {
            row.side: row
            for row in (
                await db_session.execute(
                    select(ClassificationReviewSide).where(
                        ClassificationReviewSide.review_id == review.id
                    )
                )
            )
            .scalars()
            .all()
        }

        assert review.status is ScanStatus.SUCCESS
        assert review.phase is None
        assert review.finished_at is not None
        assert review.error_message is None
        assert review.created_by_user_id == user.id
        assert (
            review.photos_processed
            == review.photo_count
            == len(await self._review_photo_ids(db_session, review.project_id))
        )
        assert set(sides) == {"a", "b"}
        assert sides["a"].kind is ClassificationReviewSideKind.EYE
        assert sides["a"].eye_model_revision is not None
        assert sides["a"].eye_mapping_version is not None
        assert sides["b"].kind is ClassificationReviewSideKind.CLOUD
        assert sides["b"].provider is not None and sides["b"].model is not None
        assert sides["b"].cost_usd is not None and sides["b"].cost_usd > 0

    async def test_the_stored_cases_are_exactly_what_the_comparison_draws(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Uebersicht rechnet die Zaehlungen beim Lesen mit `compare_review` neu. Gespeicherte
        Faelle, die diese Funktion nicht zoege, waeren ein Zustand, den die App selbst nie
        schriebe - die Zahl "vorgelegt" laege dann neben "abweichend" falsch."""
        review, _user = await self._review(db_session, tmp_path)
        results = {
            (row.side, row.photo_id): row
            for row in (
                await db_session.execute(
                    select(ClassificationReviewResult).where(
                        ClassificationReviewResult.review_id == review.id
                    )
                )
            )
            .scalars()
            .all()
        }
        strengths: dict[tuple[str, int], dict[str, float]] = {}
        for row in (
            (
                await db_session.execute(
                    select(ClassificationReviewResultStrength).where(
                        ClassificationReviewResultStrength.review_id == review.id
                    )
                )
            )
            .scalars()
            .all()
        ):
            strengths.setdefault((row.side, row.photo_id), {})[row.motif_key] = row.strength
        photo_ids = await self._review_photo_ids(db_session, review.project_id)
        comparison = compare_review(
            [
                PhotoComparison(
                    photo_id=photo_id,
                    a_motifs=strengths.get(("a", photo_id)),
                    b_motifs=strengths.get(("b", photo_id)),
                    a_excluded_document=results[("a", photo_id)].excluded_document,
                    b_excluded_document=results[("b", photo_id)].excluded_document,
                    a_album_level=results[("a", photo_id)].album_level,
                    b_album_level=results[("b", photo_id)].album_level,
                )
                for photo_id in photo_ids
            ],
            seed=review.seed,
            limit=review.sample_size,
        )
        stored = await self._cases(db_session, review.id)

        assert {photo_id for _side, photo_id in results} == set(photo_ids)
        assert all((side, photo_id) in results for side in "ab" for photo_id in photo_ids)
        assert sorted((c.photo_id, c.purpose.value, c.motif_key or "") for c in stored) == sorted(
            (c.photo_id, c.purpose, c.motif_key or "") for c in comparison.cases
        )
        assert {c.purpose for c in stored} == set(ClassificationReviewPurpose), (
            "nicht jeder Zweck hat Faelle"
        )

    async def test_photo_position_counts_from_one_in_the_order_of_the_review_set(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        review, _user = await self._review(db_session, tmp_path)
        position = {
            photo_id: index
            for index, photo_id in enumerate(
                await self._review_photo_ids(db_session, review.project_id), start=1
            )
        }

        for case in await self._cases(db_session, review.id):
            assert case.photo_position == position[case.photo_id]

    async def test_some_cases_are_judged_by_an_existing_account_and_some_stay_open(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Offene Faelle sind Stoff fuer das Urteil per Klick und per Taste im Pruefstack,
        beurteilte fuer die Urteilszahlen der Uebersicht."""
        review, user = await self._review(db_session, tmp_path)
        cases = await self._cases(db_session, review.id)
        verdicts = (
            (
                await db_session.execute(
                    select(ClassificationReviewVerdict).where(
                        ClassificationReviewVerdict.case_id.in_([c.id for c in cases])
                    )
                )
            )
            .scalars()
            .all()
        )

        assert 0 < len(verdicts) < len(cases)
        assert {v.updated_by_user_id for v in verdicts} == {user.id}
        assert len({v.verdict for v in verdicts}) > 1

    async def test_without_an_account_there_is_no_review_and_the_seeder_does_not_fail(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Pruefung braucht einen Anleger; der Seeder legt nie selbst ein Konto an."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        assert (await db_session.execute(select(ClassificationReview))).scalars().all() == []

    async def test_a_rebuild_leaves_exactly_one_review(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        assert len((await db_session.execute(select(ClassificationReview))).scalars().all()) == 1
