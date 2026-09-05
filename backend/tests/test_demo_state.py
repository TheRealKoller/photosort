"""Tests fuer den Demo-Zustands-Seeder (specs/features/0174-browser-zugang-fuer-claude.md,
decisions/0057-browsergestuetzte-oberflaechenpruefung.md).

Aufbau nach architecture/0002-testkonzept.md, Sektion "Ein schreibender Demo-Zustands-Seeder im
Produktivpaket": reine Erzeuger ohne DB, duenne DB-Schreibschicht gegen die `db_session`-Fixture,
`main()` synchron gegen eine dateibasierte SQLite in `tmp_path`. Kein Testfall dieses Moduls setzt
einen laufenden Container voraus.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import io
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.categories import CATEGORY_REGISTRY
from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY
from photosort.db import Base, make_engine, make_session_factory
from photosort.demo_state import (
    CONFIRM_ENV_VAR,
    CONFIRM_LITERAL,
    DEMO_PROJECT_PREFIX,
    EMPTY_PROJECT_NAME,
    ERROR_PROJECT_NAME,
    ERROR_STATE_PHOTO_COUNT,
    LARGE_COLLECTION_PHOTO_COUNT,
    LARGE_PROJECT_NAME,
    RATED_PROJECT_NAME,
    DemoStateError,
    assert_safe_to_seed,
    check_confirmation,
    check_opencloud_target,
    demo_etag,
    demo_project_specs,
    demo_relative_path,
    is_demo_project_name,
    main,
    rebuild_demo_state,
    render_demo_image,
)
from photosort.models import (
    CriterionScoringRun,
    Photo,
    PhotoCategoryClassification,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanRun,
    ScanStatus,
    User,
)
from photosort.thumbnails import display_path, generate_variants, thumbnail_path

_SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def _module_file(module: str) -> Path | None:
    relative = module.replace(".", "/")
    for candidate in (_SRC_DIR / f"{relative}.py", _SRC_DIR / relative / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _import_closure(entry_module: str) -> set[str]:
    """Statischer Import-Graph des Quellbaums ab `entry_module`, auf `photosort.*` beschraenkt.

    Bewusst per AST statt per echtem Import: der Laufzeit-Import von `photosort.main` zieht
    mediapipe/onnxruntime mit und waere nur in einem Subprozess aussagekraeftig (`sys.modules` ist
    im Testprozess bereits durch die Testdatei selbst verunreinigt)."""
    seen: set[str] = set()
    pending = [entry_module]
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        path = _module_file(module)
        if path is None:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                pending.extend(
                    alias.name for alias in node.names if alias.name.startswith("photosort")
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith("photosort"):
                    pending.append(node.module)
                    # "from photosort.api import projects" - der Name kann ein Untermodul sein.
                    pending.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return seen


class TestIsDemoProjectName:
    """Praefix-Praedikat des Schutzabbruchs. Der interessante Teil ist, was NICHT als Demo-Projekt
    durchgeht - eine lockere `startswith("Demo")`-Pruefung wuerde ein reales Projekt
    "Demolition Sommer 2019" freigeben und loeschen (Edge Case E9 der Spec)."""

    @pytest.mark.parametrize(
        "name",
        [
            EMPTY_PROJECT_NAME,
            LARGE_PROJECT_NAME,
            RATED_PROJECT_NAME,
            ERROR_PROJECT_NAME,
            f"{DEMO_PROJECT_PREFIX}Irgendein Rest aus einem frueheren Lauf",
        ],
    )
    def test_exact_prefix_counts_as_demo_project(self, name: str) -> None:
        assert is_demo_project_name(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "Demo",
            "Demonstration",
            "Demolition Sommer 2019",
            "Demo -- Bewertet",
            "Demo—Bewertet",
            "Demo - Bewertet",
            "demo — bewertet",
            "Ein Demo — Projekt",
            "Familienfotos 2019",
            "",
        ],
    )
    def test_anything_but_the_exact_prefix_counts_as_a_foreign_project(self, name: str) -> None:
        assert is_demo_project_name(name) is False


class TestCheckConfirmation:
    """Teil (a) der dreiteiligen Sperre (M1): ein exakter Satz-Literal, nicht "gesetzt"/truthy."""

    def test_exact_literal_passes(self) -> None:
        check_confirmation(CONFIRM_LITERAL)

    @pytest.mark.parametrize(
        "value",
        [None, "", "0", "false", "1", "true", "yes", "YES-WIPE-AND-SEED-DEMO-DATA"],
    )
    def test_missing_or_merely_truthy_value_aborts(self, value: str | None) -> None:
        with pytest.raises(DemoStateError):
            check_confirmation(value)

    def test_surrounding_whitespace_is_not_accepted(self) -> None:
        with pytest.raises(DemoStateError):
            check_confirmation(f" {CONFIRM_LITERAL} ")

    def test_error_message_names_the_variable_but_not_the_rejected_value(self) -> None:
        with pytest.raises(DemoStateError) as excinfo:
            check_confirmation("geheimer-falscher-wert")
        assert CONFIRM_ENV_VAR in str(excinfo.value)
        assert "geheimer-falscher-wert" not in str(excinfo.value)


class TestCheckOpencloudTarget:
    """Teil (c) der dreiteiligen Sperre (M1) - die einzige Bedingung, die auf einer frisch
    aufgesetzten Produktivinstanz mit leerer Datenbank noch greift. Muster (inkl. Port-Pflicht)
    aus scripts/seed-opencloud-demo.py::validate_demo_base_url."""

    @pytest.mark.parametrize(
        "base_url",
        [
            "",
            "http://opencloud-demo:9200",
            "http://localhost:9200",
            "http://127.0.0.1:9200",
            "http://localhost:8080/",
        ],
    )
    def test_empty_or_known_demo_host_passes(self, base_url: str) -> None:
        check_opencloud_target(base_url)

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://cloud.example.org",
            "http://cloud.example.org:9200",
            "http://localhost",
            "https://localhost:9200",
            "http://192.168.1.10:9200",
            "opencloud-demo:9200",
        ],
    )
    def test_anything_else_aborts(self, base_url: str) -> None:
        with pytest.raises(DemoStateError):
            check_opencloud_target(base_url)

    def test_error_message_does_not_leak_the_configured_url(self) -> None:
        with pytest.raises(DemoStateError) as excinfo:
            check_opencloud_target("https://cloud.familie-koller.example:8443")
        message = str(excinfo.value)
        assert "familie-koller" not in message
        assert "8443" not in message


class TestDemoProjectSpecs:
    """Reine Zustandsbeschreibung - ohne DB, ohne Dateisystem."""

    def test_all_four_states_are_described_and_carry_the_demo_prefix(self) -> None:
        specs = demo_project_specs()
        assert [spec.name for spec in specs] == [
            EMPTY_PROJECT_NAME,
            LARGE_PROJECT_NAME,
            RATED_PROJECT_NAME,
            ERROR_PROJECT_NAME,
        ]
        assert all(is_demo_project_name(spec.name) for spec in specs)

    def test_slugs_are_unique(self) -> None:
        slugs = [spec.slug for spec in demo_project_specs()]
        assert len(set(slugs)) == len(slugs)

    def test_empty_project_has_no_photos(self) -> None:
        empty = demo_project_specs()[0]
        assert empty.photo_count == 0
        assert empty.uncached_photo_indices == ()

    def test_large_collection_defaults_to_the_named_constant(self) -> None:
        large = demo_project_specs()[1]
        assert large.photo_count == LARGE_COLLECTION_PHOTO_COUNT

    def test_large_collection_photo_count_stays_inside_the_specified_band(self) -> None:
        # Kardinalitaets-Assertion gegen die KONSTANTE, nicht gegen einen Testparameter: eine
        # spaetere "Optimierung" auf fuenf Fotos wuerde das Grid-/Scroll-Verhalten unbemerkt
        # entwerten und muss rot werden.
        assert 60 <= LARGE_COLLECTION_PHOTO_COUNT <= 80

    def test_large_collection_photo_count_is_injectable_for_fast_tests(self) -> None:
        large = demo_project_specs(large_collection_photo_count=3)[1]
        assert large.photo_count == 3

    def test_rated_project_has_one_photo_per_category_key_of_the_fixed_set(self) -> None:
        rated = demo_project_specs()[2]
        assert rated.photo_count == len(CATEGORY_REGISTRY)

    def test_error_state_has_at_least_one_photo_without_cache_files(self) -> None:
        error = demo_project_specs()[3]
        assert error.photo_count > 0
        assert len(error.uncached_photo_indices) >= 1
        assert all(0 <= index < error.photo_count for index in error.uncached_photo_indices)
        assert len(error.uncached_photo_indices) < error.photo_count


class TestRenderDemoImage:
    """Synthetische Bilderzeugung - deterministisch, ohne Netzwerk, ohne echte Fotos."""

    def test_produces_a_decodable_jpeg(self) -> None:
        image = Image.open(io.BytesIO(render_demo_image(slug="bewertet", index=0)))
        image.load()
        assert image.format == "JPEG"
        assert image.width > 0
        assert image.height > 0

    def test_same_arguments_produce_byte_identical_output(self) -> None:
        first = render_demo_image(slug="bewertet", index=7)
        second = render_demo_image(slug="bewertet", index=7)
        assert first == second

    def test_different_index_produces_different_output(self) -> None:
        assert render_demo_image(slug="bewertet", index=1) != render_demo_image(
            slug="bewertet", index=2
        )

    def test_different_slug_produces_different_output(self) -> None:
        assert render_demo_image(slug="bewertet", index=1) != render_demo_image(
            slug="fehlerzustand", index=1
        )


class TestDemoPhotoIdentity:
    """etag und relativer Pfad sind deterministisch und je Foto eindeutig - der etag geht in den
    Cache-Schluessel ein (thumbnails.cache_key), der Pfad ist die Anzeige im Frontend."""

    def test_etag_is_deterministic(self) -> None:
        assert demo_etag("bewertet", 3) == demo_etag("bewertet", 3)

    def test_etag_is_unique_per_photo(self) -> None:
        etags = {
            demo_etag(slug, index)
            for slug in ("bewertet", "grosse-sammlung")
            for index in range(5)
        }
        assert len(etags) == 10

    def test_relative_path_is_deterministic_and_unique(self) -> None:
        assert demo_relative_path("bewertet", 3) == demo_relative_path("bewertet", 3)
        paths = {demo_relative_path("bewertet", index) for index in range(5)}
        assert len(paths) == 5

    def test_relative_path_looks_like_an_image_file(self) -> None:
        assert Path(demo_relative_path("bewertet", 3)).suffix == ".jpg"


# --- Duenne DB-Schreibschicht -----------------------------------------------------------------


async def _make_user(session: AsyncSession, username: str) -> User:
    user = User(username=username, password_hash="argon2-platzhalter")
    session.add(user)
    await session.flush()
    return user


async def _project(session: AsyncSession, name: str) -> Project:
    project = (
        (await session.execute(select(Project).where(Project.name == name))).scalars().first()
    )
    assert project is not None, f"Projekt {name!r} fehlt"
    return project


async def _photos_of(session: AsyncSession, project_name: str) -> list[Photo]:
    project = await _project(session, project_name)
    return list(
        (
            await session.execute(
                select(Photo).where(Photo.project_id == project.id).order_by(Photo.id)
            )
        )
        .scalars()
        .all()
    )


async def _make_foreign_project(
    session: AsyncSession, cache_dir: Path, *, name: str = "Familienfotos 2019"
) -> tuple[Project, Photo]:
    """Ein Projekt, das der Seeder NIE anfassen darf - inklusive echter Cache-Dateien, damit ein
    versehentliches `glob`/`rmtree` im Cache auffiele (M2)."""
    project = Project(name=name, opencloud_drive_id="drive-echt", opencloud_path="/Familie")
    session.add(project)
    await session.flush()
    photo = Photo(
        project_id=project.id,
        relative_path="Familie/2019/echtes-foto.jpg",
        etag="echt-0001",
        content_length=1234,
        taken_at=datetime(2019, 7, 1, 12, 0, 0),
        last_modified=datetime(2019, 7, 1, 12, 0, 0),
    )
    session.add(photo)
    await session.flush()
    generate_variants(cache_dir, photo.id, photo.etag, render_demo_image(slug="echt", index=0))
    return project, photo


def _cache_file_hashes(cache_dir: Path) -> list[str]:
    """Sortierte Inhalts-Hashes aller Cache-Dateien. Bewusst Inhalte statt Dateinamen: die Namen
    haengen an der von der Datenbank vergebenen photo_id, der Inhalt nicht."""
    if not cache_dir.exists():
        return []
    return sorted(
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in cache_dir.iterdir()
        if path.is_file()
    )


async def _snapshot(session: AsyncSession, cache_dir: Path) -> dict[str, object]:
    """Normalisierter Zustands-Schnappschuss fuer die Idempotenz-Pruefung (Testkonzept, Punkt 2).

    Bewusst unabhaengig vom Seeder gebaut - eine vom Modul selbst gelieferte Schnappschuss-
    Funktion pruefte sich selbst."""
    projects = (await session.execute(select(Project).order_by(Project.name))).scalars().all()
    photos_by_project: dict[str, int] = {}
    ratings: dict[str, int] = {}
    suggestions = 0
    for project in projects:
        photos = (
            (await session.execute(select(Photo).where(Photo.project_id == project.id)))
            .scalars()
            .all()
        )
        photos_by_project[project.name] = len(photos)
        for photo in photos:
            for rating in (
                (await session.execute(select(Rating).where(Rating.photo_id == photo.id)))
                .scalars()
                .all()
            ):
                ratings[rating.status.value] = ratings.get(rating.status.value, 0) + 1
            score = await session.get(PhotoScore, photo.id)
            if score is not None and score.suggested_status is not None:
                suggestions += 1
    scan_runs = (await session.execute(select(ScanRun))).scalars().all()
    return {
        "projects": sorted(project.name for project in projects),
        "photos_by_project": photos_by_project,
        "ratings": ratings,
        "suggestions": suggestions,
        "scan_run_status": sorted(run.status.value for run in scan_runs),
        "cache": _cache_file_hashes(cache_dir),
    }


class TestAssertSafeToSeed:
    """Die dreiteilige Sperre als Ganzes (M1) - inklusive Teil (b), der die Datenbank braucht."""

    async def test_empty_database_passes_the_guard(self, db_session: AsyncSession) -> None:
        # Edge Case E8: der Erstlauf darf nicht daran scheitern, dass "keine Demo-Projekte
        # vorhanden" als "nicht ausschliesslich Demo-Projekte" gewertet wird.
        await assert_safe_to_seed(db_session, confirmation=CONFIRM_LITERAL, opencloud_base_url="")

    async def test_database_with_only_demo_projects_passes_the_guard(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(
            Project(name=RATED_PROJECT_NAME, opencloud_drive_id="demo", opencloud_path="/demo")
        )
        await db_session.flush()
        await assert_safe_to_seed(db_session, confirmation=CONFIRM_LITERAL, opencloud_base_url="")

    @pytest.mark.parametrize("name", ["Familienfotos 2019", "Demo", "Demonstration"])
    async def test_any_foreign_project_aborts(self, db_session: AsyncSession, name: str) -> None:
        db_session.add(Project(name=name, opencloud_drive_id="drive", opencloud_path="/pfad"))
        await db_session.flush()
        with pytest.raises(DemoStateError):
            await assert_safe_to_seed(
                db_session, confirmation=CONFIRM_LITERAL, opencloud_base_url=""
            )

    async def test_wrong_confirmation_aborts(self, db_session: AsyncSession) -> None:
        with pytest.raises(DemoStateError):
            await assert_safe_to_seed(db_session, confirmation=None, opencloud_base_url="")

    async def test_real_looking_opencloud_target_aborts(self, db_session: AsyncSession) -> None:
        with pytest.raises(DemoStateError):
            await assert_safe_to_seed(
                db_session,
                confirmation=CONFIRM_LITERAL,
                opencloud_base_url="https://cloud.example.org",
            )


class TestRebuildDemoStateProducesTheFourStates:
    """Die vier Zustaende, geprueft ueber ihre pruefrelevante Eigenschaft - nie ueber die
    Implementierung."""

    async def test_creates_exactly_the_four_demo_projects(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        names = (
            (await db_session.execute(select(Project.name).order_by(Project.id))).scalars().all()
        )
        assert names == [
            EMPTY_PROJECT_NAME,
            LARGE_PROJECT_NAME,
            RATED_PROJECT_NAME,
            ERROR_PROJECT_NAME,
        ]

    async def test_empty_project_exists_but_has_no_photos(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert await _photos_of(db_session, EMPTY_PROJECT_NAME) == []

    async def test_large_collection_uses_the_injected_count(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert len(await _photos_of(db_session, LARGE_PROJECT_NAME)) == 3

    async def test_rated_project_covers_every_category_key_of_the_fixed_set(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        # Ueber das Set aus categories.py iteriert, nie als abgeschriebene 13er-Liste: eine
        # vierzehnte Kategorie darf nicht ungeprueft durchrutschen.
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        keys = set()
        for photo in await _photos_of(db_session, RATED_PROJECT_NAME):
            classification = await db_session.get(PhotoCategoryClassification, photo.id)
            assert classification is not None
            keys.add(classification.category_key)
        assert keys == set(CATEGORY_REGISTRY)

    async def test_rated_project_has_all_three_rating_statuses_for_every_user(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await _make_user(db_session, "zweiter-nutzer")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]
        rows = (
            (await db_session.execute(select(Rating).where(Rating.photo_id.in_(photo_ids))))
            .scalars()
            .all()
        )
        by_user: dict[int, set[str]] = {}
        for rating in rows:
            by_user.setdefault(rating.user_id, set()).add(rating.status.value)
        assert len(by_user) == 2
        expected_statuses = {status.value for status in RatingStatus}
        assert all(statuses == expected_statuses for statuses in by_user.values())

    async def test_rated_project_has_an_open_rejection_suggestion(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        open_suggestions = []
        for photo in await _photos_of(db_session, RATED_PROJECT_NAME):
            score = await db_session.get(PhotoScore, photo.id)
            assert score is not None
            ratings = (
                (await db_session.execute(select(Rating).where(Rating.photo_id == photo.id)))
                .scalars()
                .all()
            )
            if score.suggested_status == RatingStatus.REJECTED and not ratings:
                open_suggestions.append(photo.id)
        assert len(open_suggestions) >= 1

    async def test_rated_project_has_a_criterion_run_with_criterion_scores(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, RATED_PROJECT_NAME)
        runs = (
            (
                await db_session.execute(
                    select(CriterionScoringRun).where(
                        CriterionScoringRun.project_id == project.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(runs) == 1
        assert runs[0].status == ScanStatus.SUCCESS
        photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]
        scores = (
            (
                await db_session.execute(
                    select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id.in_(photo_ids))
                )
            )
            .scalars()
            .all()
        )
        assert {score.criterion_key for score in scores} == set(CRITERIA_REGISTRY)

    async def test_error_project_has_a_failed_run_with_a_non_empty_error_message(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, ERROR_PROJECT_NAME)
        runs = (
            (await db_session.execute(select(ScanRun).where(ScanRun.project_id == project.id)))
            .scalars()
            .all()
        )
        failed = [run for run in runs if run.status == ScanStatus.FAILED]
        assert len(failed) == 1
        assert failed[0].error_message is not None
        assert failed[0].error_message.strip() != ""

    async def test_error_project_has_at_least_one_photo_without_cache_files(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, ERROR_PROJECT_NAME)
        without_cache = [
            photo for photo in photos if not thumbnail_path(tmp_path, photo.id, photo.etag).exists()
        ]
        assert len(without_cache) >= 1
        assert len(without_cache) < len(photos)

    async def test_error_project_has_at_least_one_cloud_vision_error_row(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photo_ids = [photo.id for photo in await _photos_of(db_session, ERROR_PROJECT_NAME)]
        errors = (
            (
                await db_session.execute(
                    select(PhotoCloudVisionError).where(
                        PhotoCloudVisionError.photo_id.in_(photo_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(errors) >= 1
        assert all(error.error_message.strip() != "" for error in errors)


class TestRebuildDemoStateWritesRealThumbnails:
    """Bindung an die ECHTE thumbnails.py-Logik, gegen Drift getestet statt vorausgesetzt."""

    async def test_cache_files_lie_at_the_independently_computed_paths(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        # Der Test fragt NICHT den Seeder, wohin er geschrieben hat, sondern berechnet den Pfad
        # selbst ueber thumbnails.thumbnail_path()/display_path(). Aendert sich die
        # Cache-Schluessel-Bildung, wird der Seeder rot statt still abzudriften.
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, LARGE_PROJECT_NAME)
        assert len(photos) == 3
        for photo in photos:
            assert thumbnail_path(tmp_path, photo.id, photo.etag).is_file()
            assert display_path(tmp_path, photo.id, photo.etag).is_file()

    async def test_two_runs_in_separate_directories_produce_byte_identical_images(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        first_dir = tmp_path / "erster-lauf"
        second_dir = tmp_path / "zweiter-lauf"
        await rebuild_demo_state(db_session, first_dir, large_collection_photo_count=3)
        await rebuild_demo_state(db_session, second_dir, large_collection_photo_count=3)
        assert _cache_file_hashes(first_dir) != []
        assert _cache_file_hashes(first_dir) == _cache_file_hashes(second_dir)


class TestRebuildDemoStateIsTargetStateIdempotent:
    """Zielzustands-Idempotenz als Zustandsgleichheit, nicht als Abwesenheit eines Absturzes."""

    async def test_deliberately_corrupted_state_is_restored_exactly(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        expected = await _snapshot(db_session, tmp_path)

        # Zustand mutwillig verfaelschen: ein Foto loeschen, eine Bewertung aendern, ein
        # fuenftes Demo-Projekt anlegen, eine Cache-Datei loeschen.
        doomed = (await _photos_of(db_session, LARGE_PROJECT_NAME))[0]
        await db_session.execute(delete(PhotoScore).where(PhotoScore.photo_id == doomed.id))
        await db_session.execute(delete(Rating).where(Rating.photo_id == doomed.id))
        await db_session.execute(delete(Photo).where(Photo.id == doomed.id))
        rated_photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]
        rating = (
            (
                await db_session.execute(
                    select(Rating).where(Rating.photo_id.in_(rated_photo_ids))
                )
            )
            .scalars()
            .first()
        )
        assert rating is not None
        rating.status = RatingStatus.REJECTED
        db_session.add(
            Project(
                name=f"{DEMO_PROJECT_PREFIX}Rest aus einem alten Lauf",
                opencloud_drive_id="demo",
                opencloud_path="/demo",
            )
        )
        await db_session.flush()
        sorted(tmp_path.iterdir())[0].unlink()

        assert await _snapshot(db_session, tmp_path) != expected

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert await _snapshot(db_session, tmp_path) == expected


class TestRebuildDemoStateTouchesNothingElse:
    """M2: geloescht wird nur, was der Seeder selbst angelegt hat."""

    async def test_foreign_project_rows_and_cache_files_survive_a_rebuild(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        foreign_project, foreign_photo = await _make_foreign_project(db_session, tmp_path)
        foreign_thumbnail = thumbnail_path(tmp_path, foreign_photo.id, foreign_photo.etag)
        foreign_display = display_path(tmp_path, foreign_photo.id, foreign_photo.etag)
        assert foreign_thumbnail.is_file()

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        assert await db_session.get(Project, foreign_project.id) is not None
        assert await db_session.get(Photo, foreign_photo.id) is not None
        assert foreign_thumbnail.is_file()
        assert foreign_display.is_file()

    async def test_users_are_never_created_or_removed(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        # Der Seeder haengt Bewertungen an VORHANDENE Nutzer, legt aber selbst keinen an: ein
        # angelegtes Konto mit bekannten Zugangsdaten waere genau das Sicherheitsproblem, das die
        # Sperre verhindern soll.
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        usernames = (await db_session.execute(select(User.username))).scalars().all()
        assert usernames == ["daniel"]

    async def test_runs_without_any_user_and_writes_no_ratings(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert (await db_session.execute(select(Rating))).scalars().all() == []
        assert len(await _photos_of(db_session, RATED_PROJECT_NAME)) == len(CATEGORY_REGISTRY)


class TestRebuildDemoStateAtProductionSize:
    """Genau EIN Testfall faehrt die echte Vorgabe (Edge Case E6) - alle uebrigen laufen klein."""

    async def test_large_collection_reaches_the_named_constant_with_full_cache(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        summary = await rebuild_demo_state(db_session, tmp_path)
        photos = await _photos_of(db_session, LARGE_PROJECT_NAME)
        assert len(photos) == LARGE_COLLECTION_PHOTO_COUNT
        for photo in photos:
            assert thumbnail_path(tmp_path, photo.id, photo.etag).is_file()
            assert display_path(tmp_path, photo.id, photo.etag).is_file()
        assert summary.photo_count == (
            LARGE_COLLECTION_PHOTO_COUNT + len(CATEGORY_REGISTRY) + ERROR_STATE_PHOTO_COUNT
        )


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
        ):
            assert name in captured.out
        assert _read_counts(url)["projects"] == 4

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
        assert _read_counts(url)["projects"] == 4
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
    """M3: kein Import aus main.py/worker.py. Als Test festgehalten statt behauptet - geprueft
    ueber den statischen Import-Graphen des Quellbaums (kein Laufzeit-Import noetig)."""

    def test_import_graph_of_the_api_does_not_contain_the_seeder(self) -> None:
        closure = _import_closure("photosort.main")
        assert "photosort.demo_state" not in closure

    def test_import_graph_of_the_worker_does_not_contain_the_seeder(self) -> None:
        closure = _import_closure("photosort.worker")
        assert "photosort.demo_state" not in closure

    def test_the_import_graph_walker_actually_finds_something(self) -> None:
        # Gegenprobe: ohne sie bestuenden die beiden Tests oben auch dann, wenn der Walker gar
        # nichts findet (Tippfehler im Modulnamen, geaenderte Verzeichnisstruktur).
        assert {"photosort.models", "photosort.config"} <= _import_closure("photosort.main")
        assert "photosort.models" in _import_closure("photosort.demo_state")
        assert "photosort.thumbnails" in _import_closure("photosort.demo_state")
