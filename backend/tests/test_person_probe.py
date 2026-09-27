"""Das rein lesende Messkommando der Personen-Erkennung (Spec 0292, S12) - dieselben
Waechterklassen wie `test_criterion_probe.py`."""

from __future__ import annotations

import ast
import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.db import Base, make_engine, make_session_factory
from photosort.models import (
    Person,
    Photo,
    PhotoPersonCorrection,
    PhotoPersonDetection,
    Project,
    User,
)
from photosort.person_probe import (
    NOT_DETERMINABLE,
    PersonCounts,
    count_trail,
    main,
    read_counts,
    render_report,
)
from tests.import_closure import import_closure, imported_root_packages, module_file
from tests.write_guard import write_statements

REPO_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2029, 3, 4, 3, 47, 0)
SECRET_NAME = "Geheimname-Annabell"
SECRET_PATH = "Geheim/Familienurlaub"


async def _seed(session: AsyncSession) -> tuple[int, int]:
    """Alle fuenf Zustaende fuer Person 1, dazu ein fremdes Projekt mit Zeilen."""
    user = User(username="u", password_hash="h")
    anna = Person(slot=1, name=SECRET_NAME, name_key=SECRET_NAME.casefold())
    berta = Person(slot=2, name="Berta-Geheim", name_key="berta-geheim")
    mine = Project(name="Familienurlaub", opencloud_drive_id="d", opencloud_path=SECRET_PATH)
    other = Project(name="Fremd", opencloud_drive_id="d", opencloud_path="/fremd")
    session.add_all([user, anna, berta, mine, other])
    await session.flush()

    def photo(project: Project, index: int) -> Photo:
        return Photo(
            project_id=project.id,
            relative_path=f"{SECRET_PATH}/{index}.jpg",
            etag=f"{project.id}-{index}",
            content_length=1,
            taken_at=NOW,
            taken_at_original=NOW,
            last_modified=NOW,
        )

    photos = [photo(mine, index) for index in range(5)]
    foreign = photo(other, 9)
    session.add_all([*photos, foreign])
    await session.flush()
    # 0: Erkennung ohne Korrektur, 1: Erkennung + true, 2: Erkennung + false,
    # 3: true ohne Erkennung, 4: false ohne Erkennung.
    for index in (0, 1, 2):
        session.add(
            PhotoPersonDetection(photo_id=photos[index].id, person_id=anna.id, computed_at=NOW)
        )
    for index, applies in ((1, True), (2, False), (3, True), (4, False)):
        session.add(
            PhotoPersonCorrection(
                photo_id=photos[index].id, person_id=anna.id, user_id=user.id, applies=applies
            )
        )
    session.add(PhotoPersonDetection(photo_id=foreign.id, person_id=anna.id, computed_at=NOW))
    session.add(
        PhotoPersonCorrection(
            photo_id=foreign.id, person_id=anna.id, user_id=user.id, applies=False
        )
    )
    await session.flush()
    return mine.id, anna.id


class TestTheCounting:
    async def test_all_five_states_from_the_raw_trail(self, db_session: AsyncSession) -> None:
        project_id, _ = await _seed(db_session)

        [anna, berta] = await read_counts(db_session, project_id)

        assert anna == PersonCounts(
            label="Person 1", recognised=3, correct=2, wrong=1, added=1, removed_not_recognised=1
        )
        assert anna.rate == pytest.approx(2 / 3)
        assert berta == PersonCounts(
            label="Person 2", recognised=0, correct=0, wrong=0, added=0, removed_not_recognised=0
        )
        assert berta.rate is None

    def test_counting_the_effective_assignment_would_see_no_wrong_one(self) -> None:
        """Rot-Anker: ueber die wirksame Zuordnung waere die entfernte Erkennung verschwunden -
        die rohe Spur zaehlt sie."""
        [counts] = count_trail([7], [(1, 7)], {(1, 7): False})

        assert counts.wrong == 1
        assert counts.correct == 0

    def test_without_denominator_a_placeholder_not_an_error(self) -> None:
        report = render_report(1, count_trail([7], [], {}))

        assert NOT_DETERMINABLE in report


@pytest.fixture
def prepared(tmp_path: Path) -> tuple[str, int]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

    async def prepare() -> int:
        engine = make_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with make_session_factory(engine)() as session:
            project_id, _ = await _seed(session)
            await session.commit()
        await engine.dispose()
        return project_id

    return url, asyncio.run(prepare())


async def _snapshot(url: str) -> dict[str, list[tuple[object, ...]]]:
    engine = make_engine(url)
    async with make_session_factory(engine)() as session:
        taken = {
            table.name: [tuple(row) for row in (await session.execute(select(table))).all()]
            for table in Base.metadata.sorted_tables
        }
    await engine.dispose()
    return taken


class TestTheOutput:
    def test_only_counts_and_person_labels(
        self, prepared: tuple[str, int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        url, project_id = prepared

        assert main(["--project-id", str(project_id)], database_url=url) == 0

        report = capsys.readouterr().out
        for forbidden in (
            SECRET_NAME,
            "Berta-Geheim",
            SECRET_PATH,
            "Familienurlaub",
            ".jpg",
            "2029",
        ):
            assert forbidden not in report
        assert "## Person 1" in report and "## Person 2" in report
        assert "- falsch erkannt (erkannt und von Hand entfernt): 1" in report
        assert "66.7 %" in report

    def test_there_is_no_switch_adding_names(self, prepared: tuple[str, int]) -> None:
        url, _ = prepared
        with pytest.raises(SystemExit):
            main(["--project-id", "1", "--namen"], database_url=url)

    def test_an_unknown_project_and_a_broken_database(
        self, tmp_path: Path, prepared: tuple[str, int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        url, _ = prepared
        assert main(["--project-id", "999"], database_url=url) == 1
        broken = f"sqlite+aiosqlite:///{tmp_path / 'leer.db'}"
        assert main(["--project-id", "1"], database_url=broken) == 1
        error = capsys.readouterr().err
        assert "OperationalError" in error
        assert broken not in error


class TestTheProbeIsReadOnly:
    def test_not_in_the_graph_of_the_application_nor_in_compose(self) -> None:
        assert "photosort.person_probe" not in import_closure("photosort.main")
        assert "photosort.person_probe" not in import_closure("photosort.worker")
        assert "photosort.persons" in import_closure("photosort.main"), "Gegenprobe Walker"
        for compose in sorted(REPO_ROOT.glob("docker-compose*.yml")):
            assert "person_probe" not in compose.read_text(encoding="utf-8"), compose.name

    def test_no_model_no_endpoint_no_writing_form_no_file_no_log(self) -> None:
        path = module_file("photosort.person_probe")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots = imported_root_packages("photosort.person_probe")

        assert "photosort.face_analysis" not in import_closure("photosort.person_probe")
        assert "cv2" not in roots and "fastapi" not in roots and "logging" not in roots
        assert write_statements(tree) == []
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "open" not in called and "Path" not in called

    def test_the_write_guard_is_not_vacuous(self) -> None:
        assert "add()" in write_statements(ast.parse("session.add(row)"))

    def test_a_real_run_changes_not_a_single_row(self, prepared: tuple[str, int]) -> None:
        url, project_id = prepared
        before = asyncio.run(_snapshot(url))

        assert main(["--project-id", str(project_id)], database_url=url) == 0

        after = asyncio.run(_snapshot(url))
        assert after == before
        assert len(after["photo_person_corrections"]) == 5, (
            "Gegenprobe: der Schnappschuss prueft etwas"
        )
