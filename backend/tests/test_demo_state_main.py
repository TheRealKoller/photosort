"""Demo-Zustands-Seeder: `main()` - Verdrahtung, Exit-Codes, Schutzabbruch ohne Vorzustandsaenderung;
kein Aufrufpfad aus der laufenden Anwendung.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from photosort.config import settings
from photosort.db import Base, make_engine, make_session_factory
from photosort.demo_state import (
    CONFIRM_ENV_VAR,
    CONFIRM_LITERAL,
    DEMO_PROJECT_PREFIX,
    DUPLICATE_PROJECT_NAME,
    EMPTY_PROJECT_NAME,
    ERROR_PROJECT_NAME,
    LARGE_PROJECT_NAME,
    LONG_AUSSCHUSS_PROJECT_NAME,
    OPERATIONS_PROJECT_NAME,
    RATED_PROJECT_NAME,
    main,
    render_demo_image,
)
from photosort.models import (
    Photo,
    PhotoScore,
    Project,
    Rating,
    ScanRun,
)
from photosort.thumbnails import (
    generate_variants,
)
from tests.import_closure import import_closure


# --- main(): Verdrahtung, Exit-Codes, Schutzabbruch ohne Vorzustandsaenderung -----------------
def _sqlite_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'demo_state.db'}"


def _prepare_database(database_url: str) -> None:
    async def _create() -> None:
        engine = make_engine(database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_create())


def _write_rows(database_url: str, cache_dir: Path, project_names: list[str]) -> None:
    """Legt je Projektnamen ein Projekt mit einem Foto und echten Cache-Dateien an - der
    Vorzustand, dessen Unveraendertheit jeder Abbruch-Testfall zusaetzlich assertiert."""

    async def _write() -> None:
        engine = make_engine(database_url)
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            for offset, name in enumerate(project_names):
                project = Project(
                    name=name, opencloud_drive_id="drive", opencloud_path=f"/pfad/{offset}"
                )
                session.add(project)
                await session.flush()
                image_bytes = render_demo_image(slug="vorzustand", index=offset)
                photo = Photo(
                    project_id=project.id,
                    relative_path=f"Vorzustand/{offset}.jpg",
                    etag=f"vorzustand-{offset}",
                    content_length=len(image_bytes),
                    taken_at=datetime(2020, 1, 1, 12, 0, 0),
                    taken_at_original=datetime(2020, 1, 1, 12, 0, 0),
                    last_modified=datetime(2020, 1, 1, 12, 0, 0),
                )
                session.add(photo)
                await session.flush()
                generate_variants(cache_dir, photo.id, photo.etag, image_bytes)
            await session.commit()
        await engine.dispose()

    asyncio.run(_write())


def _read_counts(database_url: str) -> dict[str, int]:
    async def _read() -> dict[str, int]:
        engine = make_engine(database_url)
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            counts = {
                "projects": len((await session.execute(select(Project))).scalars().all()),
                "photos": len((await session.execute(select(Photo))).scalars().all()),
                "scan_runs": len((await session.execute(select(ScanRun))).scalars().all()),
                "ratings": len((await session.execute(select(Rating))).scalars().all()),
                "scores": len((await session.execute(select(PhotoScore))).scalars().all()),
            }
        await engine.dispose()
        return counts

    return asyncio.run(_read())


def _state_fingerprint(database_url: str, cache_dir: Path) -> tuple[dict[str, int], list[str]]:
    return _read_counts(database_url), sorted(
        path.name for path in cache_dir.iterdir() if path.is_file()
    )


@pytest.fixture
def confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIRM_ENV_VAR, CONFIRM_LITERAL)
    monkeypatch.setattr(settings, "opencloud_base_url", "")


class TestMainSucceeds:
    """Bewusst SYNCHRONE Tests: main() ruft selbst asyncio.run auf (kein laufender Event-Loop
    erlaubt), `argv` und `database_url` sind injizierbar."""

    def test_seeds_all_four_projects_and_reports_them(
        self,
        tmp_path: Path,
        confirmed: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        url = _sqlite_url(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _prepare_database(url)

        exit_code = main(["--cache-dir", str(cache_dir)], database_url=url)

        assert exit_code == 0
        captured = capsys.readouterr()
        for name in (
            EMPTY_PROJECT_NAME,
            LARGE_PROJECT_NAME,
            RATED_PROJECT_NAME,
            ERROR_PROJECT_NAME,
            DUPLICATE_PROJECT_NAME,
            LONG_AUSSCHUSS_PROJECT_NAME,
            OPERATIONS_PROJECT_NAME,
        ):
            assert name in captured.out
        assert _read_counts(url)["projects"] == 7

    def test_second_run_leaves_the_same_number_of_projects(
        self,
        tmp_path: Path,
        confirmed: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        url = _sqlite_url(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _prepare_database(url)

        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 0
        first = _read_counts(url)
        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 0

        assert _read_counts(url) == first
        capsys.readouterr()

    def test_runs_against_a_database_holding_only_demo_projects(
        self,
        tmp_path: Path,
        confirmed: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        url = _sqlite_url(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _prepare_database(url)
        _write_rows(url, cache_dir, [f"{DEMO_PROJECT_PREFIX}Rest aus einem alten Lauf"])

        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 0
        assert _read_counts(url)["projects"] == 7
        capsys.readouterr()


class TestMainAbortsWithoutTouchingAnything:
    """Die eigentliche Testfrage ist nie "bricht es ab", sondern "bricht es ab, OHNE vorher etwas
    angefasst zu haben". Jeder Fall assertiert deshalb zusaetzlich den unveraenderten Vorzustand -
    ein Guard, der erst nach dem ersten DELETE greift, bestuende einen reinen Exit-Code-Test und
    waere trotzdem genau der Fehler, gegen den er antritt."""

    @pytest.fixture
    def prepared(self, tmp_path: Path) -> tuple[str, Path]:
        url = _sqlite_url(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _prepare_database(url)
        _write_rows(
            url,
            cache_dir,
            ["Familienfotos 2019", f"{DEMO_PROJECT_PREFIX}Rest aus einem alten Lauf"],
        )
        return url, cache_dir

    def test_the_prepared_state_is_not_empty(self, prepared: tuple[str, Path]) -> None:
        # Gegenprobe gegen einen leer bestehenden Vorzustands-Vergleich: waere der Vorzustand
        # leer, waere "unveraendert" in jedem Abbruch-Testfall trivial erfuellt.
        counts, cache_files = _state_fingerprint(*prepared)
        assert counts["projects"] == 2
        assert counts["photos"] == 2
        assert len(cache_files) == 4

    def test_missing_environment_variable_aborts(
        self,
        prepared: tuple[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        url, cache_dir = prepared
        monkeypatch.delenv(CONFIRM_ENV_VAR, raising=False)
        monkeypatch.setattr(settings, "opencloud_base_url", "")
        before = _state_fingerprint(url, cache_dir)

        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 1
        assert _state_fingerprint(url, cache_dir) == before
        assert capsys.readouterr().err.strip() != ""

    @pytest.mark.parametrize("value", ["", "0", "false", "1", "true"])
    def test_merely_truthy_environment_value_aborts(
        self,
        prepared: tuple[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        value: str,
    ) -> None:
        url, cache_dir = prepared
        monkeypatch.setenv(CONFIRM_ENV_VAR, value)
        monkeypatch.setattr(settings, "opencloud_base_url", "")
        before = _state_fingerprint(url, cache_dir)

        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 1
        assert _state_fingerprint(url, cache_dir) == before
        capsys.readouterr()

    def test_foreign_project_in_the_database_aborts(
        self,
        prepared: tuple[str, Path],
        confirmed: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        url, cache_dir = prepared
        before = _state_fingerprint(url, cache_dir)

        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 1
        assert _state_fingerprint(url, cache_dir) == before
        capsys.readouterr()

    @pytest.mark.parametrize("name", ["Demo", "Demonstration", "Demolition Sommer 2019"])
    def test_prefix_edge_cases_count_as_foreign_projects(
        self,
        tmp_path: Path,
        confirmed: None,
        capsys: pytest.CaptureFixture[str],
        name: str,
    ) -> None:
        # Belegt, dass die Pruefung nicht als lockeres startswith("Demo")/in implementiert ist -
        # ein reales Projekt "Demolition Sommer 2019" waere sonst freigegeben und geloescht.
        url = _sqlite_url(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _prepare_database(url)
        _write_rows(url, cache_dir, [name])
        before = _state_fingerprint(url, cache_dir)

        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 1
        assert _state_fingerprint(url, cache_dir) == before
        capsys.readouterr()

    def test_configured_real_opencloud_instance_aborts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Der Fall, den (b) NICHT abdeckt: eine frisch aufgesetzte Produktivinstanz hat eine
        # leere Datenbank, (b) ist dort leer erfuellt.
        url = _sqlite_url(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _prepare_database(url)
        monkeypatch.setenv(CONFIRM_ENV_VAR, CONFIRM_LITERAL)
        monkeypatch.setattr(settings, "opencloud_base_url", "https://cloud.example.org")
        before = _state_fingerprint(url, cache_dir)

        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 1
        assert _state_fingerprint(url, cache_dir) == before
        assert "cloud.example.org" not in capsys.readouterr().err

    def test_empty_database_is_not_treated_as_a_foreign_database(
        self,
        tmp_path: Path,
        confirmed: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Edge Case E8: der Erstlauf darf nicht am eigenen Schutz scheitern.
        url = _sqlite_url(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _prepare_database(url)

        assert main(["--cache-dir", str(cache_dir)], database_url=url) == 0
        capsys.readouterr()

    def test_unreachable_database_fails_without_leaking_the_url(
        self,
        tmp_path: Path,
        confirmed: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        unreachable = "sqlite+aiosqlite:////nicht/vorhandenes/verzeichnis/geheim.db"

        assert main(["--cache-dir", str(cache_dir)], database_url=unreachable) == 1
        captured = capsys.readouterr()
        assert "geheim.db" not in captured.err
        assert "sqlite" not in captured.err

    def test_unwritable_cache_directory_fails_loudly(
        self,
        tmp_path: Path,
        confirmed: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        url = _sqlite_url(tmp_path)
        _prepare_database(url)
        blocked = tmp_path / "cache-ist-eine-datei"
        blocked.write_text("keine Datei-Ablage")

        assert main(["--cache-dir", str(blocked)], database_url=url) == 1
        assert capsys.readouterr().err.strip() != ""


class TestNoCallPathFromTheRunningApplication:
    """M3: kein Import aus main.py/photosort.worker. Als Test festgehalten statt behauptet - geprueft
    ueber den statischen Import-Graphen des Quellbaums (kein Laufzeit-Import noetig)."""

    def test_import_graph_of_the_api_does_not_contain_the_seeder(self) -> None:
        closure = import_closure("photosort.main")
        assert "photosort.demo_state" not in closure

    def test_import_graph_of_the_worker_does_not_contain_the_seeder(self) -> None:
        closure = import_closure("photosort.worker")
        assert "photosort.demo_state" not in closure

    def test_the_import_graph_walker_actually_finds_something(self) -> None:
        # Gegenprobe: ohne sie bestuenden die beiden Tests oben auch dann, wenn der Walker gar
        # nichts findet (Tippfehler im Modulnamen, geaenderte Verzeichnisstruktur).
        assert {"photosort.models", "photosort.config"} <= import_closure("photosort.main")
        assert "photosort.models" in import_closure("photosort.demo_state")
        assert "photosort.thumbnails" in import_closure("photosort.demo_state")
