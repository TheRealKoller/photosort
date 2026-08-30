from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.category_diff import (
    MISSING_CATEGORY,
    CategoryDiffError,
    collect_assignments,
    collect_photo_paths,
    diff_category_assignments,
    main,
    render_report,
    resolve_run_ids,
)
from photosort.db import Base, make_engine, make_session_factory
from photosort.models import (
    CriterionScoringRun,
    Photo,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
)


class TestDiffCategoryAssignments:
    """Reine, DB-freie Vergleichsfunktion (ADR 0046 Punkt 7: Logik rein, I/O aussen)."""

    def test_unchanged_assignment_is_reported_as_unchanged(self) -> None:
        diff = diff_category_assignments({1: "people"}, {1: "people"})
        assert diff.transitions[0].changed is False
        assert diff.matrix == {("people", "people"): 1}

    def test_changed_assignment_is_reported_with_both_keys(self) -> None:
        diff = diff_category_assignments({1: "landscape"}, {1: "unerkannt"})
        transition = diff.transitions[0]
        assert (transition.before, transition.after) == ("landscape", "unerkannt")
        assert transition.changed is True

    def test_photo_only_in_the_before_run_keeps_a_visible_marker(self) -> None:
        diff = diff_category_assignments({1: "people"}, {})
        assert diff.transitions[0].after == MISSING_CATEGORY

    def test_photo_only_in_the_after_run_keeps_a_visible_marker(self) -> None:
        diff = diff_category_assignments({}, {1: "people"})
        assert diff.transitions[0].before == MISSING_CATEGORY

    def test_empty_input_yields_an_empty_diff(self) -> None:
        diff = diff_category_assignments({}, {})
        assert diff.transitions == ()
        assert diff.matrix == {}

    def test_matrix_counts_identical_transitions_together(self) -> None:
        before = {1: "landscape", 2: "landscape", 3: "people"}
        after = {1: "unerkannt", 2: "unerkannt", 3: "people"}
        diff = diff_category_assignments(before, after)
        assert diff.matrix == {("landscape", "unerkannt"): 2, ("people", "people"): 1}

    def test_transitions_are_sorted_by_photo_id_regardless_of_input_order(self) -> None:
        diff = diff_category_assignments({3: "a", 1: "b"}, {1: "b", 3: "a"})
        assert [t.photo_id for t in diff.transitions] == [1, 3]


class TestRenderReport:
    def test_report_contains_matrix_and_photo_list(self) -> None:
        diff = diff_category_assignments(
            {1: "landscape", 2: "people"}, {1: "unerkannt", 2: "people"}
        )
        report = render_report(
            diff, {1: "a/berg.jpg", 2: "a/oma.jpg"}, before_run_id=7, after_run_id=8
        )
        assert "landscape -> unerkannt: 1" in report
        assert "people -> people: 1" in report
        assert "a/berg.jpg: landscape -> unerkannt" in report
        assert "a/oma.jpg: people -> people" in report
        assert "Lauf 7" in report
        assert "Lauf 8" in report

    def test_photo_list_is_sorted_by_relative_path(self) -> None:
        diff = diff_category_assignments({1: "a", 2: "b"}, {1: "a", 2: "b"})
        report = render_report(diff, {1: "z.jpg", 2: "a.jpg"}, before_run_id=1, after_run_id=2)
        assert report.index("a.jpg") < report.index("z.jpg")

    def test_rendering_is_deterministic(self) -> None:
        before = {2: "b", 1: "a", 3: "c"}
        after = {3: "c", 1: "x", 2: "b"}
        paths = {1: "1.jpg", 2: "2.jpg", 3: "3.jpg"}
        first = render_report(
            diff_category_assignments(before, after), paths, before_run_id=1, after_run_id=2
        )
        second = render_report(
            diff_category_assignments(before, after), paths, before_run_id=1, after_run_id=2
        )
        assert first == second

    def test_empty_diff_renders_without_crashing(self) -> None:
        report = render_report(
            diff_category_assignments({}, {}), {}, before_run_id=1, after_run_id=2
        )
        assert "Fotos gesamt: 0" in report


async def _make_project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _make_photo(session: AsyncSession, project: Project, path: str) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=datetime(2023, 1, 1, tzinfo=UTC),
        last_modified=datetime(2023, 1, 1, tzinfo=UTC),
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _make_run(
    session: AsyncSession,
    project: Project,
    *,
    status: ScanStatus = ScanStatus.SUCCESS,
    started_at: datetime | None = None,
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=status,
        started_at=started_at or datetime(2023, 1, 1, tzinfo=UTC),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _add_ranking(
    session: AsyncSession, run: CriterionScoringRun, photo: Photo, category_key: str
) -> None:
    session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            cluster_key="cluster-0",
            category_key=category_key,
            rank_score=0.5,
            rank_position=1,
        )
    )
    await session.commit()


class TestCollectAssignments:
    async def test_reads_exactly_the_rows_of_the_given_run(
        self, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg")
        old_run = await _make_run(db_session, project)
        new_run = await _make_run(db_session, project)
        await _add_ranking(db_session, old_run, photo, "landscape")
        await _add_ranking(db_session, new_run, photo, "unerkannt")

        assert await collect_assignments(db_session, old_run.id) == {photo.id: "landscape"}
        assert await collect_assignments(db_session, new_run.id) == {photo.id: "unerkannt"}

    async def test_unknown_run_yields_an_empty_mapping(self, db_session: AsyncSession) -> None:
        assert await collect_assignments(db_session, 999) == {}

    async def test_reading_does_not_modify_any_row(self, db_session: AsyncSession) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg")
        run = await _make_run(db_session, project)
        await _add_ranking(db_session, run, photo, "landscape")

        await collect_assignments(db_session, run.id)

        assert await collect_assignments(db_session, run.id) == {photo.id: "landscape"}

    async def test_collect_photo_paths_returns_relative_paths(
        self, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "urlaub/a.jpg")

        assert await collect_photo_paths(db_session, [photo.id]) == {photo.id: "urlaub/a.jpg"}
        assert await collect_photo_paths(db_session, []) == {}


class TestResolveRunIds:
    async def test_defaults_to_the_two_most_recent_successful_runs(
        self, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        oldest = await _make_run(db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC))
        middle = await _make_run(db_session, project, started_at=datetime(2023, 2, 1, tzinfo=UTC))
        newest = await _make_run(db_session, project, started_at=datetime(2023, 3, 1, tzinfo=UTC))

        assert await resolve_run_ids(db_session, project.id, None, None) == (
            middle.id,
            newest.id,
        )
        assert oldest.id not in (middle.id, newest.id)

    async def test_failed_runs_are_ignored_for_the_default(
        self, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        first = await _make_run(db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_run(db_session, project, started_at=datetime(2023, 2, 1, tzinfo=UTC))
        await _make_run(
            db_session,
            project,
            status=ScanStatus.FAILED,
            started_at=datetime(2023, 3, 1, tzinfo=UTC),
        )

        assert await resolve_run_ids(db_session, project.id, None, None) == (
            first.id,
            second.id,
        )

    async def test_unknown_project_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(CategoryDiffError):
            await resolve_run_ids(db_session, 999, None, None)

    async def test_fewer_than_two_successful_runs_raises(
        self, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_run(db_session, project)

        with pytest.raises(CategoryDiffError):
            await resolve_run_ids(db_session, project.id, None, None)

    async def test_explicit_run_ids_are_used_as_given(self, db_session: AsyncSession) -> None:
        project = await _make_project(db_session)
        first = await _make_run(db_session, project)
        second = await _make_run(db_session, project)

        assert await resolve_run_ids(db_session, project.id, first.id, second.id) == (
            first.id,
            second.id,
        )

    async def test_a_run_of_a_different_project_is_rejected(
        self, db_session: AsyncSession
    ) -> None:
        # Konsistenz-Guard (Security-Abschnitt der Spec 0217, Punkt 3): lieber Abbruch als still
        # die Daten zweier Projekte vermischen.
        project = await _make_project(db_session)
        other = await _make_project(db_session, name="Norwegen")
        own_run = await _make_run(db_session, project)
        foreign_run = await _make_run(db_session, other)

        with pytest.raises(CategoryDiffError):
            await resolve_run_ids(db_session, project.id, own_run.id, foreign_run.id)

    async def test_two_identical_run_ids_are_rejected(self, db_session: AsyncSession) -> None:
        project = await _make_project(db_session)
        run = await _make_run(db_session, project)

        with pytest.raises(CategoryDiffError):
            await resolve_run_ids(db_session, project.id, run.id, run.id)

    async def test_only_one_explicit_run_id_is_rejected(self, db_session: AsyncSession) -> None:
        project = await _make_project(db_session)
        run = await _make_run(db_session, project)

        with pytest.raises(CategoryDiffError):
            await resolve_run_ids(db_session, project.id, run.id, None)


def _seed_database(database_url: str) -> dict[str, int]:
    """Legt ein Projekt mit zwei erfolgreichen Laeufen in einer DATEIBASIERTEN SQLite-DB an -
    main() baut seine eigene Engine/Session (wie im echten Container), deshalb reicht die
    In-Memory-`db_session`-Fixture hier nicht."""

    async def _seed() -> dict[str, int]:
        engine = make_engine(database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            project = await _make_project(session)
            photo = await _make_photo(session, project, "urlaub/berg.jpg")
            before = await _make_run(
                session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC)
            )
            after = await _make_run(
                session, project, started_at=datetime(2023, 2, 1, tzinfo=UTC)
            )
            await _add_ranking(session, before, photo, "landscape")
            await _add_ranking(session, after, photo, "unerkannt")
            ids = {
                "project": project.id,
                "before": before.id,
                "after": after.id,
                "photo": photo.id,
            }
        await engine.dispose()
        return ids

    return asyncio.run(_seed())


def _sqlite_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'category_diff.db'}"


class TestMain:
    """Verdrahtung + Exit-Codes. Bewusst SYNCHRONE Tests: main() ruft selbst asyncio.run auf (kein
    laufender Event-Loop erlaubt), `argv` und `database_url` sind injizierbar."""

    def test_default_compares_the_two_most_recent_runs(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = _sqlite_url(tmp_path)
        ids = _seed_database(url)

        exit_code = main(["--project-id", str(ids["project"])], database_url=url)

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "urlaub/berg.jpg: landscape -> unerkannt" in output

    def test_explicit_run_ids_are_accepted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = _sqlite_url(tmp_path)
        ids = _seed_database(url)

        exit_code = main(
            [
                "--project-id",
                str(ids["project"]),
                "--before-run-id",
                str(ids["before"]),
                "--after-run-id",
                str(ids["after"]),
            ],
            database_url=url,
        )

        assert exit_code == 0
        assert "landscape -> unerkannt" in capsys.readouterr().out

    def test_unknown_project_exits_non_zero_with_a_short_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = _sqlite_url(tmp_path)
        _seed_database(url)

        exit_code = main(["--project-id", "999"], database_url=url)

        assert exit_code != 0
        captured = capsys.readouterr()
        # Fehlertexte auf stderr, damit ein umgeleiteter Report (stdout) frei davon bleibt.
        assert "Fehler:" in captured.err
        assert captured.out == ""
        # Kein durchgereichter Traceback/keine DATABASE_URL in der Meldung.
        assert "Traceback" not in captured.err
        assert "sqlite" not in captured.err

    def test_project_with_too_few_runs_exits_non_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = _sqlite_url(tmp_path)

        async def _seed_single_run() -> int:
            engine = make_engine(url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session_factory = make_session_factory(engine)
            async with session_factory() as session:
                project = await _make_project(session)
                await _make_run(session, project)
                project_id = project.id
            await engine.dispose()
            return project_id

        project_id = asyncio.run(_seed_single_run())

        exit_code = main(["--project-id", str(project_id)], database_url=url)

        assert exit_code != 0
        assert "Fehler:" in capsys.readouterr().err

    def test_a_run_id_of_another_project_exits_non_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = _sqlite_url(tmp_path)
        ids = _seed_database(url)

        exit_code = main(
            [
                "--project-id",
                str(ids["project"]),
                "--before-run-id",
                str(ids["before"]),
                "--after-run-id",
                "9999",
            ],
            database_url=url,
        )

        assert exit_code != 0
        assert "Fehler:" in capsys.readouterr().err

    def test_identical_run_ids_are_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Review-Fund: zwei identische Run-IDs ergaeben einen Report, in dem definitionsgemaess
        # alles unveraendert aussieht - irrefuehrend bei einem Werkzeug, das eine Veraenderung
        # nachweisen soll.
        url = _sqlite_url(tmp_path)
        ids = _seed_database(url)

        exit_code = main(
            [
                "--project-id",
                str(ids["project"]),
                "--before-run-id",
                str(ids["before"]),
                "--after-run-id",
                str(ids["before"]),
            ],
            database_url=url,
        )

        assert exit_code != 0
        assert "Fehler:" in capsys.readouterr().err

    def test_a_database_error_yields_a_short_message_without_credentials(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Security-Abschnitt der Spec 0217, Punkt 3: kein durchgereichter SQLAlchemy-Traceback -
        # der koennte die DATABASE_URL inklusive Zugangsdaten in die Ausgabe schreiben.
        unreachable = "sqlite+aiosqlite:////nicht/vorhandenes/verzeichnis/geheim.db"

        exit_code = main(["--project-id", "1"], database_url=unreachable)

        assert exit_code != 0
        captured = capsys.readouterr()
        assert "Fehler: Datenbankzugriff fehlgeschlagen" in captured.err
        assert captured.out == ""
        assert "Traceback" not in captured.err
        assert "geheim" not in captured.err

    def test_project_id_must_be_an_integer(self, tmp_path: Path) -> None:
        # argparse type=int (Security-Abschnitt der Spec 0217, Punkt 3): ein freier String wird
        # gar nicht erst bis zur Datenbank durchgereicht.
        with pytest.raises(SystemExit):
            main(["--project-id", "1 OR 1=1"], database_url=_sqlite_url(tmp_path))
