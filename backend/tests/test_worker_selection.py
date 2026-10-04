"""Der DB-nahe Teil des Auswahlvorschlags: Kandidatenmenge, Schreiben der Spalte, Neuaufbau.

Genau das, was die reine Funktion (tests/test_selection.py) nicht kennt - die Bildung der
auswahlfaehigen Menge (letzter erfolgreicher Lauf, `rank_score IS NOT NULL`, kein
`excluded_document`, wirksame Staerken ueber `load_effective_strengths`, wirksame Personen ueber
`load_effective_persons`), das Schreiben von `selection_position` und die beiden Neuaufbauten
`rebuild_run_selection` und `rebuild_run_grouping`. Kein Fall hier wiederholt eine Aussage des
Verfahrens selbst.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    Event,
    MotifAssessmentSource,
    Person,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoMotifCorrection,
    PhotoPersonCorrection,
    PhotoPersonDetection,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import upsert_assessment
from photosort.persons import delete_person
from photosort.selection import DEFAULT_TARGET, MOTIF_PRESENCE_THRESHOLD, SIMILARITY_TIME_WINDOW
from photosort.worker import rebuild_run_grouping, rebuild_run_selection

_BASE = datetime(2026, 8, 12, 9, 0, 0)
_FULL = 1.0
_NONE = 0.0


async def _project(
    session: AsyncSession, name: str = "Reise", *, target: int | None = None
) -> Project:
    """`target` steht in jedem Fall ausgeschrieben, der eine bestimmte Platzzahl braucht: die
    Vorbelegung ist fest 150 (ADR 0131), und ein Testaufbau mit drei Fotos bekaeme sonst
    jedes Foto."""
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
        und eine spaetere Aenderung der Vorbelegung erreichte das Projekt nicht mehr. Mehr
        Kandidaten als die Vorbelegung, damit sie die Groesse tatsaechlich bestimmt."""
        project = await _project(db_session)
        run = await _successful_run(db_session, project)
        event = await _event_row(db_session, run, 1)
        for index in range(DEFAULT_TARGET + 10):
            photo = await _photo(db_session, project, index, offset=index * timedelta(hours=2))
            await _ranking(db_session, run, photo, event, rank_score=0.9 - index / 1000)
        await db_session.flush()

        await rebuild_run_selection(db_session, project.id)

        assert project.selection_target is None
        assert (
            len([p for p in (await _positions(db_session, run)).values() if p is not None])
            == DEFAULT_TARGET
        )

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


class TestTheDraftHasNoPhaseOfItsOwn:
    async def test_no_new_classification_phase_value_was_introduced(self) -> None:
        """Der Vorschlag ist kein eigener Teilschritt mit eigener Fortschrittsstufe in der
        Oberflaeche: Er rechnet unter der zuletzt gesetzten Phase. `persons` ist der Teilschritt
        der Personen-Erkennung, nicht der Vorschlag."""
        assert [phase.value for phase in ClassificationPhase] == [
            "remote_categories",
            "criteria",
            "landmark",
            "ranking",
            "persons",
        ]

    async def test_rebuilding_the_grouping_also_produces_the_draft(
        self, db_session: AsyncSession
    ) -> None:
        """`rebuild_run_grouping` loescht Events und Rangzeilen und baut sie ueber
        `_build_grouping_and_rankings` neu auf; den Vorschlag rechnet es danach ausdruecklich
        selbst. Ohne diesen Aufruf stuende die Spalte danach ueberall auf `NULL`."""
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


_Rebuild = Callable[[AsyncSession, int], Awaitable[None]]


async def _person(session: AsyncSession, slot: int, name: str) -> Person:
    person = Person(slot=slot, name=name, name_key=name.casefold())
    session.add(person)
    await session.flush()
    return person


async def _detect(session: AsyncSession, photo: Photo, person: Person) -> None:
    session.add(PhotoPersonDetection(photo_id=photo.id, person_id=person.id, computed_at=_BASE))
    await session.flush()


async def _correct(session: AsyncSession, photo: Photo, person: Person, *, applies: bool) -> None:
    user = (await session.execute(select(User))).scalars().first()
    if user is None:
        user = User(username="daniel", password_hash="egal")
        session.add(user)
        await session.flush()
    session.add(
        PhotoPersonCorrection(
            photo_id=photo.id,
            person_id=person.id,
            user_id=user.id,
            applies=applies,
            updated_at=_BASE,
        )
    )
    await session.flush()


class _PersonLay:
    """Ein Event, zwei Plaetze. `leader` und `runner_up` tragen Motiv `a`, `weak` nichts und hat
    den schwaechsten Rang. Ohne Person geht Platz 2 an `runner_up`; traegt `weak` eine wirksame
    Person, geht er an `weak`.

    Abstaende von 30 und 15 Minuten: ein Event auch nach einer Neugliederung, und `runner_up`
    liegt ausserhalb von `SIMILARITY_TIME_WINDOW` und wird nicht abgewertet. Modellstufe und
    Kriterienwert stehen dabei, damit auch `rebuild_run_grouping` dieselbe Rangfolge rechnet."""

    async def build(self, session: AsyncSession, name: str = "Reise") -> _PersonLay:
        self.session = session
        self.project = await _project(session, name, target=2)
        self.run = await _successful_run(session, self.project)
        self.event = await _event_row(session, self.run, 1)
        self.leader = await self._photo(1, timedelta(), level=5, strength=_FULL, rank=0.9)
        self.runner_up = await self._photo(
            2, 2 * SIMILARITY_TIME_WINDOW, level=4, strength=_FULL, rank=0.8
        )
        self.weak = await self._photo(
            3, 3 * SIMILARITY_TIME_WINDOW, level=1, strength=_NONE, rank=0.1
        )
        return self

    async def _photo(
        self, index: int, offset: timedelta, *, level: int, strength: float, rank: float
    ) -> Photo:
        photo = await _photo(self.session, self.project, index, offset=offset)
        await _motifs(self.session, photo, {"a": strength})
        self.session.add(
            PhotoAlbumSuitability(
                photo_id=photo.id,
                level=level,
                reason=None,
                provider="testanbieter",
                computed_at=_BASE,
            )
        )
        self.session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="sharpness",
                value=0.5,
                source="local_heuristic",
                computed_at=_BASE,
            )
        )
        await _ranking(self.session, self.run, photo, self.event, rank_score=rank)
        return photo

    async def draft(self) -> dict[str, int | None]:
        positions = await _positions(self.session, self.run)
        return {
            role: positions.get(photo.id)
            for role, photo in (
                ("leader", self.leader),
                ("runner_up", self.runner_up),
                ("weak", self.weak),
            )
        }


_WITHOUT_PERSON = {"leader": 1, "runner_up": 2, "weak": None}
_WITH_PERSON_ON_WEAK = {"leader": 1, "runner_up": None, "weak": 2}


class TestThePersonsOfTheDraft:
    @pytest.mark.parametrize(
        ("detected", "correction", "counts"),
        [
            pytest.param(True, None, True, id="erkannt"),
            pytest.param(False, True, True, id="von-hand-ergaenzt"),
            pytest.param(True, False, False, id="von-hand-entfernt"),
        ],
    )
    async def test_exactly_the_effective_names_count(
        self,
        db_session: AsyncSession,
        detected: bool,
        correction: bool | None,
        counts: bool,
    ) -> None:
        """Dieselben Namen, nach denen der Personenfilter filtert: Die Korrektur geht der
        Erkennung vor, ein entfernter Name zaehlt nicht."""
        lay = await _PersonLay().build(db_session)
        anna = await _person(db_session, 1, "Anna")
        if detected:
            await _detect(db_session, lay.weak, anna)
        if correction is not None:
            await _correct(db_session, lay.weak, anna, applies=correction)

        await rebuild_run_selection(db_session, lay.project.id)

        assert await lay.draft() == (_WITH_PERSON_ON_WEAK if counts else _WITHOUT_PERSON)

    @pytest.mark.parametrize("lage", ["ausgeschlossenes-dokument", "ohne-rank-score"])
    async def test_a_person_only_on_an_ineligible_photo_is_not_present(
        self, db_session: AsyncSession, lage: str
    ) -> None:
        """Anna steht nur auf einem Foto, das nicht auswahlfaehig ist: sie kommt nicht vor und
        lenkt Platz 2 nicht um. Dasselbe Foto auswahlfaehig gemacht bekommt ihn - das Paar steht
        in einem Fall, weil die erste Haelfte allein auch ohne jede Personenwirkung bestuende."""
        lay = await _PersonLay().build(db_session)
        anna = await _person(db_session, 1, "Anna")
        carrier = await _photo(db_session, lay.project, 4, offset=SIMILARITY_TIME_WINDOW)
        await _motifs(
            db_session, carrier, {"a": _NONE}, excluded=lage == "ausgeschlossenes-dokument"
        )
        await _ranking(
            db_session,
            lay.run,
            carrier,
            lay.event,
            rank_score=None if lage == "ohne-rank-score" else 0.05,
        )
        await _detect(db_session, carrier, anna)

        await rebuild_run_selection(db_session, lay.project.id)
        ineligible = await _positions(db_session, lay.run)

        if lage == "ausgeschlossenes-dokument":
            await _motifs(db_session, carrier, {"a": _NONE})
        else:
            await db_session.execute(
                update(PhotoRanking)
                .where(PhotoRanking.photo_id == carrier.id)
                .values(rank_score=0.05, rank_position=4)
            )
        await rebuild_run_selection(db_session, lay.project.id)
        eligible = await _positions(db_session, lay.run)

        assert ineligible[carrier.id] is None
        assert ineligible[lay.runner_up.id] == 2
        assert eligible[carrier.id] == 2

    async def test_a_deleted_person_leaves_the_draft_of_a_project_without_her(
        self, db_session: AsyncSession
    ) -> None:
        """Zwilling: dasselbe Projekt ohne Person. Vor dem Loeschen lenkt Anna Platz 2 um, nach
        `delete_person` und einem Neuaufbau nicht mehr."""
        with_anna = await _PersonLay().build(db_session, "Mit")
        twin = await _PersonLay().build(db_session, "Ohne")
        anna = await _person(db_session, 1, "Anna")
        await _detect(db_session, with_anna.weak, anna)
        await _correct(db_session, with_anna.weak, anna, applies=True)
        await rebuild_run_selection(db_session, with_anna.project.id)
        await rebuild_run_selection(db_session, twin.project.id)
        assert await with_anna.draft() != await twin.draft()

        assert await delete_person(db_session, anna.id)
        await db_session.flush()
        await rebuild_run_selection(db_session, with_anna.project.id)

        assert await with_anna.draft() == await twin.draft() == _WITHOUT_PERSON

    @pytest.mark.parametrize(
        "rebuild",
        [
            pytest.param(rebuild_run_selection, id="richtwert"),
            pytest.param(rebuild_run_grouping, id="versatz"),
        ],
    )
    async def test_both_rebuilds_read_the_persons_live(
        self, db_session: AsyncSession, rebuild: _Rebuild
    ) -> None:
        """Eine nach dem Lauf eingefuegte Erkennung wirkt beim naechsten Neuaufbau - es gibt
        keinen Schnappschuss der Personen je Lauf."""
        lay = await _PersonLay().build(db_session)
        anna = await _person(db_session, 1, "Anna")
        await rebuild(db_session, lay.project.id)
        assert await lay.draft() == _WITHOUT_PERSON

        await _detect(db_session, lay.weak, anna)
        await rebuild(db_session, lay.project.id)

        assert await lay.draft() == _WITH_PERSON_ON_WEAK
