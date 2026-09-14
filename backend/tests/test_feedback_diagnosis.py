"""Die Ladeabfragen der laufenden Diagnose (`feedback_log.py::load_diagnosis`, Spec 0432).

KEINE ABFRAGE FILTERT NACH PROJEKT (D1). Der tragende Fall dafuer braucht ein Ereignis aus einem
ZWEITEN Projekt - mit nur einem Projekt ist eine projektskopierte Umsetzung von der globalen nicht
unterscheidbar, und beide lieferten dieselben Zahlen.

DIE EINGEFRORENEN WERTE KOMMEN AUS DEM EREIGNIS, die lokalen Kriterienwerte LIVE aus
`photo_criterion_scores`. Beide Richtungen stehen hier als eigener Fall: Ein spaeterer Lauf
aendert die Motivstaerke, ohne die Fehlerklasse zu bewegen; und ein geaenderter Kriterienwert
bewegt die Zustimmungsrate sehr wohl.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.feedback import (
    MOTIF_ABSENT_THRESHOLD,
    MOTIF_ADDED_KIND,
    MOTIF_DROPPED_KIND,
    CriterionAgreement,
    ExchangeKind,
    ExchangeStats,
    MotifErrorCase,
)
from photosort.feedback_log import (
    load_diagnosis,
    load_frozen_context,
    record_album_decision,
    record_exchange,
    record_final_decision,
    record_motif_correction,
)
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Event,
    FeedbackEvent,
    FeedbackEventKind,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoMotifAssessment,
    PhotoMotifStrength,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)

_KEYS = ("sharpness", "exposure")
_NOW = datetime(2023, 6, 1, tzinfo=UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class _Graph:
    project_id: int
    user_id: int
    run_id: int
    event_id: int
    photo_ids: list[int]


async def _user(session: AsyncSession) -> int:
    user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one_or_none()
    if user is None:
        user = User(username="anne", password_hash="x")
        session.add(user)
        await session.flush()
    return user.id


async def _build(
    session: AsyncSession, *, name: str = "Costa Rica", levels: tuple[int, ...] = (4, 4, 3)
) -> _Graph:
    """Ein Projekt mit erfolgreichem Kriterienlauf, einem Event und `len(levels)` eingeordneten
    Fotos - jedes mit Modellstufe, Rangwert und beiden Kriterienwerten."""
    project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
    session.add(project)
    user_id = await _user(session)
    await session.flush()

    photos = [
        Photo(
            project_id=project.id,
            relative_path=f"{name}-{index}.jpg",
            etag=f"etag-{name}-{index}",
            content_length=100,
            taken_at=_NOW,
            taken_at_original=_NOW,
            last_modified=_NOW,
        )
        for index in range(len(levels))
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
            PhotoAlbumSuitability(
                photo_id=photo.id, level=levels[index], provider="test", computed_at=_NOW
            )
        )
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo.id,
                event_id=event.id,
                rank_score=0.9 - index * 0.2,
                rank_position=index + 1,
            )
        )
        for key in _KEYS:
            session.add(
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key=key,
                    value=0.9 - index * 0.3,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=_NOW,
                )
            )
    await session.flush()
    return _Graph(
        project_id=project.id,
        user_id=user_id,
        run_id=run.id,
        event_id=event.id,
        photo_ids=[photo.id for photo in photos],
    )


async def _exchange(
    session: AsyncSession,
    graph: _Graph,
    *,
    taken: int = 0,
    replaced: int = 1,
    level: int | None = 4,
    replaced_level: int | None = 4,
    quality: float | None = 0.4,
    replaced_quality: float | None = 0.8,
) -> None:
    await record_exchange(
        session,
        project_id=graph.project_id,
        user_id=graph.user_id,
        photo_id=graph.photo_ids[taken],
        replaced_photo_id=graph.photo_ids[replaced],
        criterion_scoring_run_id=graph.run_id,
        event_id=graph.event_id,
        level=level,
        replaced_level=replaced_level,
        quality=quality,
        replaced_quality=replaced_quality,
    )
    await session.flush()


class TestTheEmptyLog:
    async def test_the_diagnosis_of_an_empty_log_counts_nothing(
        self, db_session: AsyncSession
    ) -> None:
        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.correction_count == 0
        assert diagnosis.motif_errors == dict.fromkeys(MotifErrorCase, 0)
        assert diagnosis.exchanges == dict.fromkeys(ExchangeKind, ExchangeStats())

    async def test_every_requested_criterion_appears_with_a_zero_bilance(
        self, db_session: AsyncSession
    ) -> None:
        """Der Leerzustand ist NICHT die leere Liste je Kriterium: Die Oberflaeche unterscheidet
        ihn an `correction_count`, nicht am Fehlen der Zeilen."""
        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.criteria == {key: CriterionAgreement(0, 0.0, 0.0) for key in _KEYS}


class TestTheCorrectionCount:
    async def test_it_counts_every_kind_of_event(self, db_session: AsyncSession) -> None:
        graph = await _build(db_session)
        context = await load_frozen_context(
            db_session, project_id=graph.project_id, photo_id=graph.photo_ids[0]
        )
        await record_album_decision(
            db_session,
            project_id=graph.project_id,
            photo_id=graph.photo_ids[0],
            user_id=graph.user_id,
            kind=FeedbackEventKind.PHOTO_INCLUDED,
            context=context,
        )
        await record_final_decision(
            db_session,
            project_id=graph.project_id,
            photo_id=graph.photo_ids[1],
            kind=FeedbackEventKind.FINAL_DECISION_OUT,
            context=context,
        )
        await _exchange(db_session, graph)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.correction_count == 3

    async def test_a_withdrawn_decision_adds_to_the_count_instead_of_shrinking_it(
        self, db_session: AsyncSession
    ) -> None:
        """Die beiden naheliegenden Fehler (das erste Ereignis loeschen; die Ruecknahme abziehen)
        liefern beide plausible Zahlen - hier waeren es 1 und 0 statt 2 (L6)."""
        graph = await _build(db_session)
        context = await load_frozen_context(
            db_session, project_id=graph.project_id, photo_id=graph.photo_ids[0]
        )
        for kind in (FeedbackEventKind.PHOTO_INCLUDED, FeedbackEventKind.DECISION_WITHDRAWN):
            await record_album_decision(
                db_session,
                project_id=graph.project_id,
                photo_id=graph.photo_ids[0],
                user_id=graph.user_id,
                kind=kind,
                context=context,
            )
        await db_session.flush()

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.correction_count == 2


class TestTheDiagnosisCountsAcrossProjects:
    """D1: Der Gewichtssatz gilt global; zaehlten die Fallzahlen nur ein Projekt, stuenden sie
    neben einem Vorschlag, den sie nicht belegen."""

    async def test_an_exchange_from_a_second_project_is_counted_too(
        self, db_session: AsyncSession
    ) -> None:
        first = await _build(db_session, name="Costa Rica")
        second = await _build(db_session, name="Norwegen")
        await _exchange(db_session, first)
        await _exchange(db_session, second)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.correction_count == 2
        assert diagnosis.exchanges[ExchangeKind.WITHIN_LEVEL].count == 2

    async def test_a_pair_from_a_second_project_moves_the_agreement(
        self, db_session: AsyncSession
    ) -> None:
        """Nicht nur die Fallzahl: Auch die RECHNUNG laeuft ueber beide Projekte."""
        first = await _build(db_session, name="Costa Rica")
        second = await _build(db_session, name="Norwegen")
        await _exchange(db_session, first, taken=0, replaced=1)
        await _exchange(db_session, second, taken=1, replaced=0, level=4, replaced_level=4)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.criteria["sharpness"].case_count == 2
        assert diagnosis.criteria["sharpness"].agreement == 0.0


class TestTheMotifErrors:
    async def _correction(
        self,
        session: AsyncSession,
        graph: _Graph,
        *,
        kind: FeedbackEventKind,
        strength: float | None,
    ) -> None:
        context = await load_frozen_context(
            session, project_id=graph.project_id, photo_id=graph.photo_ids[0]
        )
        await record_motif_correction(
            session,
            project_id=graph.project_id,
            photo_id=graph.photo_ids[0],
            user_id=graph.user_id,
            kind=kind,
            motif_key="sonnenuntergang",
            motif_strength=strength,
            context=context,
        )
        await session.flush()

    async def test_the_three_cases_are_told_apart(self, db_session: AsyncSession) -> None:
        graph = await _build(db_session)
        await self._correction(db_session, graph, kind=FeedbackEventKind.MOTIF_ADDED, strength=None)
        await self._correction(
            db_session, graph, kind=FeedbackEventKind.MOTIF_ADDED, strength=MOTIF_ABSENT_THRESHOLD
        )
        await self._correction(
            db_session, graph, kind=FeedbackEventKind.MOTIF_DROPPED, strength=0.95
        )

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.motif_errors == {
            MotifErrorCase.MISSING: 1,
            MotifErrorCase.TOO_WEAK: 1,
            MotifErrorCase.OVERCALLED: 1,
        }

    async def test_the_frozen_strength_survives_a_later_reclassification(
        self, db_session: AsyncSession
    ) -> None:
        """DER NACHWEIS IST DER EINGEFRORENE WERT, nicht das Vorhandensein der Zeile: Das Modell
        sieht das Motiv danach deutlich, die Fehlerklasse bleibt trotzdem `missing`. Ohne das
        Einfrieren zeigte die zweite Korrektur desselben Motivs nie einen Modellfehler an."""
        graph = await _build(db_session)
        db_session.add(
            PhotoMotifAssessment(
                photo_id=graph.photo_ids[0],
                source=MotifAssessmentSource.LOCAL,
                excluded_document=False,
                computed_at=_NOW,
            )
        )
        await db_session.flush()
        db_session.add(
            PhotoMotifStrength(
                photo_id=graph.photo_ids[0], motif_key="sonnenuntergang", strength=0.05
            )
        )
        await db_session.flush()
        await self._correction(db_session, graph, kind=FeedbackEventKind.MOTIF_ADDED, strength=0.05)

        await db_session.execute(
            update(PhotoMotifStrength)
            .where(PhotoMotifStrength.photo_id == graph.photo_ids[0])
            .values(strength=0.95)
        )
        await db_session.flush()

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.motif_errors[MotifErrorCase.MISSING] == 1
        assert diagnosis.motif_errors[MotifErrorCase.OVERCALLED] == 0

    async def test_a_correction_without_a_model_error_moves_no_number(
        self, db_session: AsyncSession
    ) -> None:
        graph = await _build(db_session)
        await self._correction(db_session, graph, kind=FeedbackEventKind.MOTIF_ADDED, strength=0.95)
        await self._correction(
            db_session, graph, kind=FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN, strength=0.95
        )

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.correction_count == 2
        assert diagnosis.motif_errors == dict.fromkeys(MotifErrorCase, 0)


class TestTheExchanges:
    async def test_the_three_classes_are_kept_apart(self, db_session: AsyncSession) -> None:
        graph = await _build(db_session)
        await _exchange(db_session, graph, level=4, replaced_level=4)
        await _exchange(db_session, graph, level=5, replaced_level=2)
        await _exchange(db_session, graph, level=None, replaced_level=3)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert [diagnosis.exchanges[kind].count for kind in ExchangeKind] == [1, 1, 1]

    async def test_the_frozen_quality_decides_the_preference(
        self, db_session: AsyncSession
    ) -> None:
        graph = await _build(db_session)
        await _exchange(db_session, graph, quality=0.2, replaced_quality=0.8)
        await _exchange(db_session, graph, quality=0.8, replaced_quality=0.2)
        await _exchange(db_session, graph, quality=0.5, replaced_quality=0.5)

        stats = (await load_diagnosis(db_session, criterion_keys=_KEYS)).exchanges

        assert stats[ExchangeKind.WITHIN_LEVEL] == ExchangeStats(
            count=3, preferred_lower_rated_count=1, quality_incomparable_count=1
        )


class TestThePairsBehindTheCriterionAgreement:
    async def test_a_within_level_exchange_reads_the_live_criterion_values(
        self, db_session: AsyncSession
    ) -> None:
        """Foto 0 traegt die hoeheren Werte und wurde vorgezogen - beide Kriterien stimmen zu."""
        graph = await _build(db_session)
        await _exchange(db_session, graph, taken=0, replaced=1)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.criteria["sharpness"] == CriterionAgreement(
            case_count=1, votes=1.0, agreement=1.0
        )

    async def test_a_changed_criterion_value_changes_the_agreement(
        self, db_session: AsyncSession
    ) -> None:
        """Die Gegenrichtung zum Einfrieren: Die Kriterienwerte werden zur AUSWERTUNGSZEIT
        gelesen - sie sind eine deterministische Messung an denselben Pixeln, keine je Lauf neu
        erfragte Fremdaussage."""
        graph = await _build(db_session)
        await _exchange(db_session, graph, taken=0, replaced=1)
        await db_session.execute(
            update(PhotoCriterionScore)
            .where(
                PhotoCriterionScore.photo_id == graph.photo_ids[0],
                PhotoCriterionScore.criterion_key == "sharpness",
            )
            .values(value=0.0)
        )
        await db_session.flush()

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.criteria["sharpness"].agreement == -1.0
        assert diagnosis.criteria["exposure"].agreement == 1.0

    async def test_an_across_level_exchange_forms_no_pair(self, db_session: AsyncSession) -> None:
        """Der Austausch zaehlt als Fall, geht in die Ableitung aber NICHT ein (G5) - sonst
        vermischte sich die Aussage ueber die lokalen Kriterien mit der ueber das Modell."""
        graph = await _build(db_session)
        await _exchange(db_session, graph, taken=0, replaced=2, level=4, replaced_level=3)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.exchanges[ExchangeKind.ACROSS_LEVEL].count == 1
        assert diagnosis.criteria["sharpness"].case_count == 0

    async def test_a_photo_without_criterion_values_forms_no_evaluable_pair(
        self, db_session: AsyncSession
    ) -> None:
        """D5: Die auswertbare Fallzahl kann KLEINER sein als die Zahl der gleichstufigen
        Austausche; beide stehen nebeneinander."""
        graph = await _build(db_session)
        await db_session.execute(
            PhotoCriterionScore.__table__.delete().where(
                PhotoCriterionScore.photo_id == graph.photo_ids[1]
            )
        )
        await _exchange(db_session, graph, taken=0, replaced=1)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.exchanges[ExchangeKind.WITHIN_LEVEL].count == 1
        assert all(entry.case_count == 0 for entry in diagnosis.criteria.values())

    async def test_the_joint_final_selection_forms_pairs_within_its_event(
        self, db_session: AsyncSession
    ) -> None:
        """Foto 0 und 1 stehen auf derselben Stufe, Foto 2 nicht - es bildet mit keinem ein
        Paar."""
        graph = await _build(db_session)
        for index, kind in (
            (0, FeedbackEventKind.FINAL_DECISION_IN),
            (1, FeedbackEventKind.FINAL_DECISION_OUT),
            (2, FeedbackEventKind.FINAL_DECISION_OUT),
        ):
            context = await load_frozen_context(
                db_session, project_id=graph.project_id, photo_id=graph.photo_ids[index]
            )
            await record_final_decision(
                db_session,
                project_id=graph.project_id,
                photo_id=graph.photo_ids[index],
                kind=kind,
                context=context,
            )
        await db_session.flush()

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.criteria["sharpness"] == CriterionAgreement(
            case_count=1, votes=2.0, agreement=1.0
        )

    async def test_the_joint_decision_weighs_more_than_a_single_handgrip(
        self, db_session: AsyncSession
    ) -> None:
        """L7: Das hoehere Gewicht wirkt in der STIMMENZAHL, die Fallzahl bleibt ungewichtet."""
        graph = await _build(db_session)
        await _exchange(db_session, graph, taken=0, replaced=1)
        for index, kind in (
            (0, FeedbackEventKind.FINAL_DECISION_IN),
            (1, FeedbackEventKind.FINAL_DECISION_OUT),
        ):
            context = await load_frozen_context(
                db_session, project_id=graph.project_id, photo_id=graph.photo_ids[index]
            )
            await record_final_decision(
                db_session,
                project_id=graph.project_id,
                photo_id=graph.photo_ids[index],
                kind=kind,
                context=context,
            )
        await db_session.flush()

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert diagnosis.criteria["sharpness"].case_count == 2
        assert diagnosis.criteria["sharpness"].votes == 3.0

    async def test_a_criterion_outside_the_requested_keys_never_appears(
        self, db_session: AsyncSession
    ) -> None:
        graph = await _build(db_session)
        db_session.add(
            PhotoCriterionScore(
                photo_id=graph.photo_ids[0],
                criterion_key="landschaft",
                value=0.9,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=_NOW,
            )
        )
        await _exchange(db_session, graph, taken=0, replaced=1)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert set(diagnosis.criteria) == set(_KEYS)


class TestTheKindStringsStayCoupledToTheEnum:
    """`feedback.py` importiert `photosort.models` nicht (Reinheit) und vergleicht deshalb gegen
    Zeichenketten. Ohne diesen Waechter liefe ein umbenannter Enum-Wert still ins Leere: Die
    Klassifizierung faende nichts mehr, die Diagnose zeigte null Motivfehler, und kein Fall der
    reinen Ebene wuerde rot."""

    @pytest.mark.parametrize(
        ("literal", "kind"),
        [
            (MOTIF_ADDED_KIND, FeedbackEventKind.MOTIF_ADDED),
            (MOTIF_DROPPED_KIND, FeedbackEventKind.MOTIF_DROPPED),
        ],
    )
    def test_the_literal_matches_its_enum_value(
        self, literal: str, kind: FeedbackEventKind
    ) -> None:
        assert literal == kind.value


class TestTheDiagnosisReadsNothingItDoesNotAggregate:
    """Auflage S8: Die Antwort liefert ausschliesslich Aggregate. Hier als Strukturaussage ueber
    den Rueckgabewert des Ladepfads - der Endpunkt kann nur weglassen, was dieser ihm gibt."""

    async def test_the_result_carries_no_event_user_or_photo_reference(
        self, db_session: AsyncSession
    ) -> None:
        graph = await _build(db_session)
        await _exchange(db_session, graph)

        diagnosis = await load_diagnosis(db_session, criterion_keys=_KEYS)

        assert [field for field in vars(diagnosis) if "photo" in field or "user" in field] == []
        assert (await db_session.execute(select(FeedbackEvent.user_id))).scalars().all() == [
            graph.user_id
        ]
