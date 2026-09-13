"""Der DB-nahe Teil des Auswahlvorschlags: Kandidatenmenge, Schreiben der Spalte, Neuaufbau.

Genau das, was die reine Funktion (tests/test_selection.py) nicht kennt - die Bildung der
auswahlfaehigen Menge (letzter erfolgreicher Lauf, `rank_score IS NOT NULL`, kein
`excluded_document`, wirksame Staerken ueber `load_effective_strengths`), das Schreiben von
`selection_position`, die Einbettung in `_build_grouping_and_rankings` und
`rebuild_run_selection`. Kein Fall hier wiederholt eine Aussage des Verfahrens selbst.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    Event,
    MotifAssessmentSource,
    Photo,
    PhotoMotifCorrection,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import upsert_assessment
from photosort.selection import MOTIF_PRESENCE_THRESHOLD, SIMILARITY_TIME_WINDOW
from photosort.worker import rebuild_run_selection

_BASE = datetime(2026, 8, 12, 9, 0, 0)
_FULL = 1.0
_NONE = 0.0


async def _project(
    session: AsyncSession, name: str = "Reise", *, target: int | None = None
) -> Project:
    """`target` steht in jedem Fall ausgeschrieben, der mehr als einen Platz braucht: die
    Vorbelegung ist ein Zehntel der Bilderzahl, und ein Testaufbau mit drei Fotos haette sonst
    genau einen Platz."""
    project = Project(
        name=name,
        opencloud_drive_id=f"drive-{name}",
        opencloud_path=name,
        selection_target=target,
    )
    session.add(project)
    await session.flush()
    return project


async def _successful_run(session: AsyncSession, project: Project) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS, started_at=_BASE)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=ScanStatus.SUCCESS,
        started_at=_BASE,
        finished_at=_BASE + timedelta(minutes=5),
        last_progress_at=_BASE + timedelta(minutes=5),
    )
    session.add(run)
    await session.flush()
    return run


async def _event_row(session: AsyncSession, run: CriterionScoringRun, position: int) -> Event:
    event = Event(
        criterion_scoring_run_id=run.id,
        position=position,
        started_at=_BASE,
        ended_at=_BASE + timedelta(hours=1),
    )
    session.add(event)
    await session.flush()
    return event


async def _photo(
    session: AsyncSession, project: Project, index: int, *, offset: timedelta = timedelta()
) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=f"{project.name}/{index}.jpg",
        etag=f"etag-{project.name}-{index}",
        content_length=100,
        taken_at=_BASE + offset,
        taken_at_original=_BASE + offset,
        camera_probed=True,
        last_modified=_BASE,
    )
    session.add(photo)
    await session.flush()
    return photo


async def _motifs(
    session: AsyncSession,
    photo: Photo,
    strengths: Mapping[str, float],
    *,
    excluded: bool = False,
) -> None:
    await upsert_assessment(
        session,
        photo.id,
        source=MotifAssessmentSource.CLOUD,
        strengths=dict(strengths),
        excluded_document=excluded,
        provider="testanbieter",
        computed_at=_BASE,
    )
    await session.flush()


async def _ranking(
    session: AsyncSession,
    run: CriterionScoringRun,
    photo: Photo,
    event: Event,
    *,
    rank_score: float | None,
    rank_position: int | None = 1,
) -> PhotoRanking:
    row = PhotoRanking(
        criterion_scoring_run_id=run.id,
        photo_id=photo.id,
        event_id=event.id,
        rank_score=rank_score,
        rank_position=None if rank_score is None else rank_position,
    )
    session.add(row)
    await session.flush()
    return row


async def _positions(session: AsyncSession, run: CriterionScoringRun) -> dict[int, int | None]:
    rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.selection_position).where(
                PhotoRanking.criterion_scoring_run_id == run.id
            )
        )
    ).all()
    return {photo_id: position for photo_id, position in rows}


class TestTheEligibleCandidates:
    async def test_a_photo_without_a_quality_verdict_never_enters_the_draft(
        self, db_session: AsyncSession
    ) -> None:
        """Beide Haelften in EINEM Fall gegen ein bewertetes Foto, das den Platz bekommt: getrennt
        geschrieben bestuenden sie auch bei einem durchgehend leeren Vorschlag."""
        project = await _project(db_session)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        scored = await _photo(db_session, project, 1)
        unscored = await _photo(db_session, project, 2)
        without_row = await _photo(db_session, project, 3)
        await _ranking(db_session, run, scored, event, rank_score=0.9)
        await _ranking(db_session, run, unscored, event, rank_score=None)

        await rebuild_run_selection(db_session, project.id)

        positions = await _positions(db_session, run)
        assert positions[scored.id] == 1
        assert positions[unscored.id] is None
        assert without_row.id not in positions

    async def test_a_run_without_a_single_scored_candidate_yields_an_empty_draft(
        self, db_session: AsyncSession
    ) -> None:
        """Der dritte Weg zu `m = 0` - Events mit Kandidaten, aber keiner davon bewertet. Die
        beiden uebrigen Wege (gar keine Events, Events ohne Kandidaten) sind DB-frei geprueft."""
        project = await _project(db_session)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        for index in (1, 2, 3):
            photo = await _photo(db_session, project, index)
            await _ranking(db_session, run, photo, event, rank_score=None)

        await rebuild_run_selection(db_session, project.id)

        assert set((await _positions(db_session, run)).values()) == {None}

    async def test_an_excluded_document_never_enters_the_draft(
        self, db_session: AsyncSession
    ) -> None:
        """Das ausgeschlossene Foto traegt den HOECHSTEN `rank_score` des Events und bekommt
        trotzdem keinen Platz - waehrend dasselbe Foto ohne das Flag ihn bekommt. Das Paar steht in
        einem Fall, weil die erste Haelfte allein auch bei einem leeren Vorschlag bestuende."""
        project = await _project(db_session)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        best = await _photo(db_session, project, 1)
        other = await _photo(db_session, project, 2)
        await _motifs(db_session, best, {"a": _FULL}, excluded=True)
        await _motifs(db_session, other, {"a": _FULL})
        await _ranking(db_session, run, best, event, rank_score=0.99)
        await _ranking(db_session, run, other, event, rank_score=0.10)

        await rebuild_run_selection(db_session, project.id)
        with_flag = await _positions(db_session, run)

        await _motifs(db_session, best, {"a": _FULL}, excluded=False)
        await rebuild_run_selection(db_session, project.id)
        without_flag = await _positions(db_session, run)

        assert with_flag[best.id] is None
        assert with_flag[other.id] == 1
        assert without_flag[best.id] == 1

    async def test_an_excluded_document_does_not_make_a_motif_present(
        self, db_session: AsyncSession
    ) -> None:
        """Ein Motiv, das NUR von einem ausgeschlossenen Foto ueber der Grenze getragen wird, gilt
        nicht als vorkommend und darf die Vergabe nicht umlenken: Platz 2 geht an das qualitativ
        staerkere Bild, nicht an den schwachen `b`-Traeger."""
        project = await _project(db_session, target=2)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        excluded = await _photo(db_session, project, 1)
        strong = await _photo(db_session, project, 2, offset=4 * SIMILARITY_TIME_WINDOW)
        middle = await _photo(db_session, project, 3, offset=8 * SIMILARITY_TIME_WINDOW)
        weak_b = await _photo(db_session, project, 4)
        await _motifs(db_session, excluded, {"a": _NONE, "b": _FULL}, excluded=True)
        await _motifs(db_session, strong, {"a": _FULL, "b": _NONE})
        await _motifs(db_session, middle, {"a": _FULL, "b": _NONE})
        await _motifs(db_session, weak_b, {"a": _NONE, "b": _NONE})
        await _ranking(db_session, run, excluded, event, rank_score=0.99)
        await _ranking(db_session, run, strong, event, rank_score=0.90)
        await _ranking(db_session, run, middle, event, rank_score=0.80)
        await _ranking(db_session, run, weak_b, event, rank_score=0.10)

        await rebuild_run_selection(db_session, project.id)

        positions = await _positions(db_session, run)
        assert positions[strong.id] == 1
        assert positions[middle.id] == 2
        assert positions[weak_b.id] is None

    async def test_a_correction_is_part_of_the_effective_strength(
        self, db_session: AsyncSession
    ) -> None:
        """Die Staerken kommen ueber `load_effective_strengths`, nicht roh aus der Staerkezeile:
        eine Korrektur `applies=false` nimmt dem Foto sein Motiv und damit die Motivpflicht."""
        user = User(username="daniel", password_hash="egal")
        db_session.add(user)
        project = await _project(db_session, target=2)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        leader = await _photo(db_session, project, 1)
        runner_up = await _photo(db_session, project, 2, offset=4 * SIMILARITY_TIME_WINDOW)
        only_b = await _photo(db_session, project, 3)
        await _motifs(db_session, leader, {"a": _FULL, "b": _NONE})
        await _motifs(db_session, runner_up, {"a": _FULL, "b": _NONE})
        await _motifs(db_session, only_b, {"a": _NONE, "b": _FULL})
        await _ranking(db_session, run, leader, event, rank_score=0.9)
        await _ranking(db_session, run, runner_up, event, rank_score=0.8)
        await _ranking(db_session, run, only_b, event, rank_score=0.1)
        await db_session.flush()

        db_session.add(
            PhotoMotifCorrection(
                photo_id=only_b.id,
                user_id=user.id,
                motif_key="b",
                applies=False,
                updated_at=_BASE,
            )
        )
        await db_session.flush()

        await rebuild_run_selection(db_session, project.id)

        positions = await _positions(db_session, run)
        assert positions[runner_up.id] == 2
        assert positions[only_b.id] is None


class TestTheRunBinding:
    async def test_only_the_latest_successful_run_gets_a_draft(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project(db_session)
        older = await _successful_run(db_session, project)
        older.started_at = _BASE - timedelta(days=1)
        newer = await _successful_run(db_session, project)
        for run in (older, newer):
            event = await _event_row(db_session, run, 1)
            photo = await _photo(db_session, project, run.id)
            await _ranking(db_session, run, photo, event, rank_score=0.9)
        await db_session.flush()

        await rebuild_run_selection(db_session, project.id)

        assert set((await _positions(db_session, older)).values()) == {None}
        assert set((await _positions(db_session, newer)).values()) == {1}

    async def test_a_rebuild_of_one_project_leaves_the_other_untouched(
        self, db_session: AsyncSession
    ) -> None:
        """Sicherheitsauflage S2: `PhotoRanking` traegt keine `project_id`, die Lauf-Id ist die
        einzige Projektbindung. Fehlte das Praedikat in der Schreibanweisung, saehe die Antwort
        dem Ergebnis nichts an - der fremde Vorschlag waere in sich stimmig."""
        first = await _project(db_session, "Erstes")
        second = await _project(db_session, "Zweites")
        runs = {}
        for project in (first, second):
            run = await _successful_run(db_session, project)
            event = await _event_row(db_session, run, 1)
            photo = await _photo(db_session, project, 1)
            await _ranking(db_session, run, photo, event, rank_score=0.9)
            runs[project.name] = run
        await db_session.flush()

        await rebuild_run_selection(db_session, first.id)

        assert set((await _positions(db_session, runs["Erstes"])).values()) == {1}
        assert set((await _positions(db_session, runs["Zweites"])).values()) == {None}

    async def test_a_project_without_a_successful_run_is_a_no_op(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project(db_session)
        await db_session.flush()

        await rebuild_run_selection(db_session, project.id)


class TestTheRebuildOnlyRecomputesTheDraft:
    @staticmethod
    async def _snapshot(
        session: AsyncSession, run: CriterionScoringRun
    ) -> tuple[Sequence[object], Sequence[object]]:
        """Zustandsschnappschuss als Tupel OHNE Ids: eine Loeschung samt Neuanlage saehe sonst wie
        eine Aenderung aus, obwohl der Inhalt derselbe waere - und umgekehrt."""
        events = (
            await session.execute(
                select(Event.position, Event.started_at, Event.ended_at, Event.landmark_name)
                .where(Event.criterion_scoring_run_id == run.id)
                .order_by(Event.position)
            )
        ).all()
        rankings = (
            await session.execute(
                select(PhotoRanking.photo_id, PhotoRanking.rank_score, PhotoRanking.rank_position)
                .where(PhotoRanking.criterion_scoring_run_id == run.id)
                .order_by(PhotoRanking.photo_id)
            )
        ).all()
        return events, rankings

    async def test_events_and_ranking_rows_survive_the_rebuild_unchanged(
        self, db_session: AsyncSession
    ) -> None:
        """Dazu der Anti-Leerlauf-Nachweis: ein vorher von Hand verfaelschter Platz muss danach
        fort sein. Ohne ihn bestuende ein `return` am Funktionsanfang die Zusage."""
        project = await _project(db_session)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        rows = []
        for index in range(4):
            photo = await _photo(db_session, project, index, offset=index * timedelta(hours=2))
            rows.append(
                await _ranking(
                    db_session,
                    run,
                    photo,
                    event,
                    rank_score=0.9 - index / 10,
                    rank_position=index + 1,
                )
            )
        rows[3].selection_position = 99
        await db_session.flush()
        before = await self._snapshot(db_session, run)

        await rebuild_run_selection(db_session, project.id)

        assert await self._snapshot(db_session, run) == before
        positions = await _positions(db_session, run)
        assert positions[rows[3].photo_id] != 99
        assert set(positions.values()) != {None}

    async def test_the_rebuild_touches_neither_the_cloud_nor_image_processing(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Null Aufrufe am Cloud-/Bildverarbeitungs-Doppel: der Neuaufbau rechnet ausschliesslich
        aus persistierten Zeilen."""
        import photosort.worker as worker_module

        calls: list[str] = []
        for name in ("build_face_detector", "build_object_detector", "build_scene_classifier"):
            monkeypatch.setattr(
                worker_module,
                name,
                lambda *_args, _name=name, **_kwargs: calls.append(_name),
            )

        project = await _project(db_session)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        photo = await _photo(db_session, project, 1)
        await _ranking(db_session, run, photo, event, rank_score=0.9)
        await db_session.flush()

        await rebuild_run_selection(db_session, project.id)

        assert calls == []

    async def test_the_default_target_is_never_written_into_the_column(
        self, db_session: AsyncSession
    ) -> None:
        """Die eigentliche Zusage der Vorbelegung: sie wirkt, ohne je gespeichert zu werden. Ein
        eingeschriebener Vorgabewert waere von einer Nutzereingabe nicht mehr zu unterscheiden -
        und wuechse mit dem Bestand nicht mehr mit."""
        project = await _project(db_session)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        for index in range(30):
            photo = await _photo(db_session, project, index, offset=index * timedelta(hours=2))
            await _ranking(db_session, run, photo, event, rank_score=0.9 - index / 100)
        await db_session.flush()

        await rebuild_run_selection(db_session, project.id)

        assert project.selection_target is None
        assert len([p for p in (await _positions(db_session, run)).values() if p is not None]) == 3

    async def test_a_set_target_governs_the_size_of_the_draft(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project(db_session)
        project.selection_target = 5
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        for index in range(30):
            photo = await _photo(db_session, project, index, offset=index * timedelta(hours=2))
            await _ranking(db_session, run, photo, event, rank_score=0.9 - index / 100)
        await db_session.flush()

        await rebuild_run_selection(db_session, project.id)

        assert len([p for p in (await _positions(db_session, run)).values() if p is not None]) == 5


class TestADraftDoesNotMoveWhileTheViewIsUsed:
    async def test_a_motif_correction_moves_the_draft_only_at_the_next_rebuild(
        self, db_session: AsyncSession
    ) -> None:
        """Das Paar in EINEM Fall: die Korrektur allein aendert nichts, derselbe Neuaufbau danach
        sehr wohl. Getrennt geschrieben bestuende die erste Haelfte auch bei einem Vorschlag, der
        sich nie aendert."""
        user = User(username="daniel", password_hash="egal")
        db_session.add(user)
        project = await _project(db_session, target=2)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        leader = await _photo(db_session, project, 1)
        runner_up = await _photo(db_session, project, 2, offset=4 * SIMILARITY_TIME_WINDOW)
        only_b = await _photo(db_session, project, 3)
        await _motifs(db_session, leader, {"a": _FULL, "b": _NONE})
        await _motifs(db_session, runner_up, {"a": _FULL, "b": _NONE})
        await _motifs(db_session, only_b, {"a": _NONE, "b": _FULL})
        await _ranking(db_session, run, leader, event, rank_score=0.9)
        await _ranking(db_session, run, runner_up, event, rank_score=0.8)
        await _ranking(db_session, run, only_b, event, rank_score=0.1)
        await db_session.flush()
        await rebuild_run_selection(db_session, project.id)
        before = await _positions(db_session, run)

        db_session.add(
            PhotoMotifCorrection(
                photo_id=only_b.id,
                user_id=user.id,
                motif_key="b",
                applies=False,
                updated_at=_BASE,
            )
        )
        await db_session.flush()

        assert await _positions(db_session, run) == before
        assert before[only_b.id] == 2

        await rebuild_run_selection(db_session, project.id)

        after = await _positions(db_session, run)
        assert after[only_b.id] is None
        assert after[runner_up.id] == 2


class TestTheDraftIsPartOfTheRankingPhase:
    async def test_no_new_classification_phase_value_was_introduced(self) -> None:
        """Der Vorschlag ist die Fortsetzung der Phase `RANKING`, kein eigener Teilschritt mit
        eigener Fortschrittsstufe in der Oberflaeche."""
        assert [phase.value for phase in ClassificationPhase] == [
            "remote_categories",
            "criteria",
            "landmark",
            "ranking",
        ]

    async def test_rebuilding_the_grouping_also_produces_the_draft(
        self, db_session: AsyncSession
    ) -> None:
        """Die Einbettung am gemeinsamen Weg beider Auslöser: `rebuild_run_grouping` loescht
        Events und Rangzeilen und baut sie ueber `_build_grouping_and_rankings` neu auf - dort
        haengt der Vorschlag unmittelbar hinter den Rangzeilen. Ohne die Einbettung stuende die
        Spalte danach ueberall auf `NULL`."""
        from photosort.models import PhotoAlbumSuitability, PhotoCriterionScore
        from photosort.worker import rebuild_run_grouping

        project = await _project(db_session)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        for index in range(6):
            photo = await _photo(db_session, project, index, offset=index * timedelta(hours=3))
            db_session.add(
                PhotoAlbumSuitability(
                    photo_id=photo.id,
                    level=1 + index % 5,
                    reason=None,
                    provider="testanbieter",
                    computed_at=_BASE,
                )
            )
            db_session.add(
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key="sharpness",
                    value=0.5,
                    source="local_heuristic",
                    computed_at=_BASE,
                )
            )
            await _ranking(db_session, run, photo, event, rank_score=0.9 - index / 100)
        await db_session.flush()

        await rebuild_run_grouping(db_session, project.id)

        positions = (
            (
                await db_session.execute(
                    select(PhotoRanking.selection_position).where(
                        PhotoRanking.criterion_scoring_run_id == run.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert [position for position in positions if position is not None]


class TestTheThresholdComesFromTheSelectionModule:
    async def test_a_strength_exactly_at_the_threshold_carries_the_motif(
        self, db_session: AsyncSession
    ) -> None:
        """Die Grenze wirkt auch ueber den DB-nahen Weg: `b` gilt als vorkommend, und sein
        einziger Traeger bekommt Platz 2 trotz der niedrigsten Qualitaet."""
        project = await _project(db_session, target=2)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        leader = await _photo(db_session, project, 1)
        runner_up = await _photo(db_session, project, 2, offset=4 * SIMILARITY_TIME_WINDOW)
        at_threshold = await _photo(db_session, project, 3)
        await _motifs(db_session, leader, {"a": _FULL, "b": _NONE})
        await _motifs(db_session, runner_up, {"a": _FULL, "b": _NONE})
        await _motifs(db_session, at_threshold, {"a": _NONE, "b": MOTIF_PRESENCE_THRESHOLD})
        await _ranking(db_session, run, leader, event, rank_score=0.9)
        await _ranking(db_session, run, runner_up, event, rank_score=0.8)
        await _ranking(db_session, run, at_threshold, event, rank_score=0.1)
        await db_session.flush()

        await rebuild_run_selection(db_session, project.id)

        assert (await _positions(db_session, run))[at_threshold.id] == 2
