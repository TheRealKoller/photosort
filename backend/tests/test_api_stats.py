from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.stats import (
    _DATABASE_SIZE_SQL,
    _local_database_bytes_estimate,
    database_share_bytes,
)
from photosort.config import settings
from photosort.models import (
    ClassificationPhase,
    CloudVisionPhase,
    CriterionScoringRun,
    MotifAssessmentSource,
    Photo,
    PhotoCloudVisionError,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    PhotoScore,
    Project,
    ProjectCamera,
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motifs import (
    MOTIF_REGISTRY,
    MOTIF_STRENGTH_BAND_MEDIUM,
    MOTIF_STRENGTH_BAND_STRONG,
)
from photosort.security import hash_password
from photosort.thumbnails import display_path, thumbnail_path
from tests.event_rows import event_id_of_run

# specs/features/0207-projekt-statistikseite.md: ein einziger, aggregierender Nur-Lese-Endpunkt
# ueber Bestandsdaten. Schwerpunkt der Teststrategie ist die Integrationsebene (echte In-Memory-
# SQLite, httpx.ASGITransport) - die beiden reinen Bausteine (Anteilsrechnung, Dialekt-Weiche)
# stehen als Unit-Teil voran.


class TestDatabaseShareBytes:
    """Reine Funktion (Spec, Abschnitt 4 "Speicherbedarf"): der Datenbank-Anteil eines Projekts
    ist die Gesamtgroesse der Datenbank, anteilig nach seinem Anteil an allen Fotos - eine
    ausgewiesene SCHAETZUNG, keine Messung."""

    def test_zero_total_photos_does_not_divide_by_zero(self) -> None:
        assert database_share_bytes(1_000_000, project_photo_count=0, total_photo_count=0) == 0

    def test_a_project_without_photos_gets_no_share(self) -> None:
        assert database_share_bytes(1_000_000, project_photo_count=0, total_photo_count=50) == 0

    def test_the_only_project_gets_the_whole_database(self) -> None:
        assert database_share_bytes(1_000_000, project_photo_count=50, total_photo_count=50) == (
            1_000_000
        )

    def test_half_the_photos_get_half_the_database(self) -> None:
        assert database_share_bytes(1_000_000, project_photo_count=25, total_photo_count=50) == (
            500_000
        )

    def test_the_result_is_a_rounded_integer(self) -> None:
        result = database_share_bytes(10, project_photo_count=1, total_photo_count=3)

        assert isinstance(result, int)
        assert result == 3


class TestLocalDatabaseBytesEstimate:
    """Die Dialekt-Weiche laeuft ueber `dialect.name`, NICHT ueber ein try/except um
    fehlschlagendes SQL (Security-Muss-Kriterium: ein DBAPI-Fehlertext kann Datenbank-/Host-/
    Verbindungsangaben enthalten)."""

    def test_the_database_size_sql_is_a_static_literal_without_interpolation(self) -> None:
        rendered = str(_DATABASE_SIZE_SQL.compile(dialect=postgresql.dialect()))

        assert rendered == "SELECT pg_database_size(current_database())"

    async def test_a_non_postgres_bind_yields_none_without_running_any_sql(self) -> None:
        class _NeverExecutingSession:
            def get_bind(self) -> object:
                return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

            async def execute(self, *args: object, **kwargs: object) -> object:
                raise AssertionError("ausserhalb Postgres darf kein SQL abgesetzt werden")

        estimate = await _local_database_bytes_estimate(
            _NeverExecutingSession(),  # type: ignore[arg-type]
            project_photo_count=10,
        )

        assert estimate is None

    async def test_a_postgres_bind_scales_the_database_size_by_the_photo_share(self) -> None:
        executed: list[Any] = []

        class _StubResult:
            def __init__(self, value: int) -> None:
                self._value = value

            def scalar_one(self) -> int:
                return self._value

        class _FakePostgresSession:
            def get_bind(self) -> object:
                return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

            async def execute(self, statement: Any, *args: object, **kwargs: object) -> object:
                executed.append(statement)
                # Erste Abfrage: Datenbankgroesse, zweite: Gesamtzahl Fotos aller Projekte.
                return _StubResult(1_000_000 if len(executed) == 1 else 40)

        estimate = await _local_database_bytes_estimate(
            _FakePostgresSession(),  # type: ignore[arg-type]
            project_photo_count=10,
        )

        assert estimate == 250_000
        assert executed[0] is _DATABASE_SIZE_SQL


# --- Integrations-Ebene (Schwerpunkt) ------------------------------------------------------


async def _make_project(session: AsyncSession, name: str) -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=f"/{name}")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(
    session: AsyncSession,
    project: Project,
    path: str,
    *,
    content_length: int = 1_000,
    taken_at: datetime | None = None,
) -> Photo:
    moment = taken_at or datetime(2023, 6, 1, 12, 0)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{project.id}-{path}",
        content_length=content_length,
        taken_at=moment,
        taken_at_original=moment,
        last_modified=moment,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _add_score(
    session: AsyncSession,
    photo: Photo,
    *,
    duplicate_of: int | None = None,
) -> PhotoScore:
    score = PhotoScore(
        photo_id=photo.id,
        sharpness=1.0,
        exposure=0.5,
        computed_at=datetime(2023, 6, 2, 12, 0),
        duplicate_of=duplicate_of,
    )
    session.add(score)
    await session.commit()
    return score


async def _add_criterion_scoring_run(
    session: AsyncSession,
    project: Project,
    *,
    status_value: ScanStatus = ScanStatus.SUCCESS,
    started_at: datetime,
    finished_at: datetime | None = None,
    landmark_api_calls: int | None = 0,
    landmark_cost_usd: float | None = 0.0,
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=status_value,
        landmark_api_calls=landmark_api_calls,
        landmark_cost_usd=landmark_cost_usd,
    )
    # specs/features/0207, Edge Case 4: `started_at` in JEDEM Test mit mehr als einem Lauf
    # explizit setzen - sonst tragen alle Laeufe denselben Server-Default-Zeitstempel und die
    # "letzter erfolgreicher Lauf"-Sortierung waere ein Zufallsergebnis (sporadisch rotes CI).
    run.started_at = started_at
    run.finished_at = finished_at
    session.add(run)
    await session.commit()
    await _null_out_cost_columns(
        session,
        run,
        landmark_api_calls=landmark_api_calls,
        landmark_cost_usd=landmark_cost_usd,
    )
    await session.refresh(run)
    return run


async def _null_out_cost_columns(session: AsyncSession, run: object, **values: object) -> None:
    """Stellt einen ALTLAUF her (Kostenspalten `NULL`). Ein `None` im Konstruktor reicht dafuer
    NICHT: der Python-seitige Modell-Default `0` greift beim INSERT. Genau so sieht eine
    Bestandszeile nach `alembic upgrade` aus - und nur sie loest Befund (a) aus."""
    changed = False
    for column, value in values.items():
        if value is None:
            setattr(run, column, None)
            changed = True
    if changed:
        await session.commit()


async def _add_ranking(
    session: AsyncSession,
    run: CriterionScoringRun,
    photo: Photo,
    *,
    rank_position: int = 1,
) -> None:
    """Ein Foto steht je Lauf in genau EINER Rangzeile - die Partition ist allein das Event
    (Spec 0427, PR 3)."""
    session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=await event_id_of_run(session, run),
            rank_score=0.5,
            rank_position=rank_position,
        )
    )
    await session.commit()


async def _add_assessment(
    session: AsyncSession,
    photo: Photo,
    *,
    source: MotifAssessmentSource = MotifAssessmentSource.CLOUD,
    strengths: dict[str, float] | None = None,
    excluded_document: bool = False,
) -> None:
    """Kopfzeile plus Staerkevektor eines Fotos. Ohne `strengths` entstehen ACHT Nullen - so wie
    der Schreibpfad sie anlegt; ein unvollstaendiger Vektor ist kein Zustand, den das Produkt
    erzeugt."""
    values = {key: 0.0 for key in MOTIF_REGISTRY}
    values.update(strengths or {})
    session.add(
        PhotoMotifAssessment(
            photo_id=photo.id,
            source=source,
            excluded_document=excluded_document,
            provider="anthropic" if source == MotifAssessmentSource.CLOUD else None,
            computed_at=datetime(2023, 6, 3, 12, 0),
        )
    )
    await session.flush()
    session.add_all(
        [
            PhotoMotifStrength(photo_id=photo.id, motif_key=key, strength=strength)
            for key, strength in values.items()
        ]
    )
    await session.commit()


async def _add_correction(
    session: AsyncSession, photo: Photo, motif_key: str, *, applies: bool, user: User
) -> None:
    session.add(
        PhotoMotifCorrection(
            photo_id=photo.id, motif_key=motif_key, applies=applies, user_id=user.id
        )
    )
    await session.commit()


async def _add_second_user(session: AsyncSession, username: str = "zweitnutzer") -> User:
    user = User(username=username, password_hash=hash_password("irrelevant"))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _add_rating(
    session: AsyncSession,
    photo: Photo,
    user: User,
    status_value: RatingStatus | None = None,
    *,
    favorite: bool = False,
) -> None:
    session.add(Rating(photo_id=photo.id, user_id=user.id, status=status_value, favorite=favorite))
    await session.commit()


async def _current_user(session: AsyncSession) -> User:
    """Der von `authenticated_api_client` angelegte Testnutzer."""
    user = (await session.execute(select(User).where(User.username == "testuser"))).scalar_one()
    return user


@pytest.fixture(autouse=True)
def _cache_dir_in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Endpunkt misst den echten Cache unter `settings.photo_cache_dir` - in Tests zeigt der
    auf ein leeres tmp_path-Verzeichnis, damit kein Zustand der Entwicklungsmaschine einfliesst."""
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path / "cache"))


async def _noise_project(session: AsyncSession, tmp_path: Path) -> Project:
    """Edge Case 9: ein ZWEITES Projekt mit Daten in JEDER aggregierten Tabelle - kein Wert der
    Antwort darf projektuebergreifend lecken."""
    other = await _make_project(session, "Nachbarprojekt")
    other.cloud_vision_detection_enabled = True
    await session.commit()
    photo_a = await _add_photo(session, other, "n1.jpg", content_length=99_999)
    photo_b = await _add_photo(session, other, "n2.jpg", content_length=99_999)
    await _add_score(session, photo_a)
    await _add_score(session, photo_b, duplicate_of=photo_a.id)
    run = await _add_criterion_scoring_run(
        session,
        other,
        started_at=datetime(2024, 1, 1),
        finished_at=datetime(2024, 1, 2),
        landmark_api_calls=99,
        landmark_cost_usd=99.0,
    )
    await _add_ranking(session, run, photo_a)
    await _add_ranking(session, run, photo_b, rank_position=2)
    await _add_assessment(session, photo_a, strengths={"tier": 0.9})
    await _add_assessment(session, photo_b, excluded_document=True)
    user_for_correction = await _current_user(session)
    await _add_correction(session, photo_a, "menschen", applies=True, user=user_for_correction)
    session.add(
        PhotoLandmarkDetection(
            photo_id=photo_a.id,
            name="Fremder Turm",
            confidence=0.9,
            computed_at=datetime(2024, 1, 1),
        )
    )
    session.add(
        PhotoCloudVisionError(
            photo_id=photo_b.id,
            phase=CloudVisionPhase.LANDMARK,
            error_type="LandmarkApiError",
            error_message="fremd",
            attempted_at=datetime(2024, 1, 1),
        )
    )
    session.add(
        RemoteCategoryClassificationRun(
            project_id=other.id,
            status=ScanStatus.SUCCESS,
            finished_at=datetime(2024, 1, 3),
            api_calls=99,
            cost_usd=99.0,
        )
    )
    session.add(
        ScanRun(
            project_id=other.id,
            status=ScanStatus.SUCCESS,
            finished_at=datetime(2024, 1, 1),
            files_skipped=77,
        )
    )
    user = await _current_user(session)
    await _add_rating(session, photo_a, user, RatingStatus.ALBUM_WORTHY)
    await session.commit()
    return other


class TestAccess:
    async def test_without_a_token_the_endpoint_answers_401(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")

        response = await api_client.get(f"/projects/{project.id}/stats")

        assert response.status_code == 401

    async def test_an_unknown_project_id_without_a_token_answers_401_not_404(
        self, api_client: httpx.AsyncClient
    ) -> None:
        """Sonst waere die Existenz von Projekt-IDs unauthentifiziert abfragbar."""
        response = await api_client.get("/projects/999999/stats")

        assert response.status_code == 401

    async def test_an_unknown_project_id_answers_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.get("/projects/999999/stats")

        assert response.status_code == 404
        assert response.json()["detail"] == "Projekt nicht gefunden."


class TestEmptyProject:
    """Akzeptanzkriterium A1: ein Projekt ohne Fotos antwortet mit 200, alles auf 0 bzw. leer -
    weder Fehlermeldung noch leerer Bereich noch NaN."""

    @pytest.fixture
    async def payload(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, tmp_path: Path
    ) -> dict[str, Any]:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Leeres Projekt")

        response = await authenticated_api_client.get(f"/projects/{project.id}/stats")

        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        return body

    async def test_all_counters_are_zero(self, payload: dict[str, Any]) -> None:
        assert payload["photo_count"] == 0
        assert payload["motif_correction_count"] == 0
        assert payload["unassessed_photo_count"] == 0
        assert payload["excluded_photo_count"] == 0
        assert payload["progress"] == {
            "scanned": 0,
            "thumbnails_ready": 0,
            "ausschuss_scored": 0,
            "ranked": 0,
            "remote_classified": 0,
        }
        assert payload["ratings"] == {
            "favorite": 0,
            "album_worthy": 0,
            "rejected": 0,
            "unrated": 0,
        }
        assert payload["diagnostics"]["duplicate_photo_count"] == 0

    async def test_storage_is_zero_and_the_database_share_is_not_determinable(
        self, payload: dict[str, Any]
    ) -> None:
        """Edge Case 2: `SUM(content_length)` liefert bei 0 Fotos NULL - serverseitig auf 0
        normalisiert. Edge Case 17: unter SQLite ist der Datenbank-Anteil `None`."""
        assert payload["storage"]["opencloud_bytes"] == 0
        assert payload["storage"]["local_cache_bytes"] == 0
        assert payload["storage"]["local_database_bytes_estimate"] is None

    async def test_the_taken_at_range_is_empty(self, payload: dict[str, Any]) -> None:
        assert payload["taken_at_earliest"] is None
        assert payload["taken_at_latest"] is None

    async def test_every_motif_is_listed_with_three_zeros_and_no_average(
        self, payload: dict[str, Any]
    ) -> None:
        """Bei null beurteilten Fotos existieren die Eintraege trotzdem (sonst waere die Tabelle
        leer statt vollstaendig), tragen drei Nullen und den Mittelwert `None` - keine Division.

        Nachsatz wie in jedem Statistikfall: die drei Baender sind disjunkt und erschoepfend."""
        entries = payload["motifs"]

        assert [entry["motif_key"] for entry in entries] == list(MOTIF_REGISTRY)
        assert all(entry["strong_photo_count"] == 0 for entry in entries)
        assert all(entry["medium_photo_count"] == 0 for entry in entries)
        assert all(entry["weak_photo_count"] == 0 for entry in entries)
        assert all(entry["average_strength"] is None for entry in entries)

    async def test_costs_are_zero_without_an_incompleteness_hint(
        self, payload: dict[str, Any]
    ) -> None:
        assert payload["cost"]["currency"] == "USD"
        assert payload["cost"]["total_usd"] == 0
        assert payload["cost"]["by_purpose"] == [
            {"purpose": "landmark", "cost_usd": 0.0, "has_unrecorded_runs": False},
            {"purpose": "remote_category", "cost_usd": 0.0, "has_unrecorded_runs": False},
        ]

    async def test_no_run_has_ever_finished(self, payload: dict[str, Any]) -> None:
        assert payload["last_successful_runs"] == {
            "scan": None,
            "scoring": None,
            "classification": None,
            "remote_category_classification": None,
        }

    async def test_files_skipped_is_null_not_zero_without_a_scan_run(
        self, payload: dict[str, Any]
    ) -> None:
        """Edge Case 20: ohne Scan-Lauf `null` - "noch nie gescannt" ist etwas anderes als "0
        Dateien uebersprungen"."""
        assert payload["diagnostics"]["last_scan_files_skipped"] is None

    async def test_both_purposes_are_listed_in_remote_failures(
        self, payload: dict[str, Any]
    ) -> None:
        assert payload["diagnostics"]["remote_failures"] == [
            {"purpose": "landmark", "photo_count": 0},
            {"purpose": "remote_category", "photo_count": 0},
        ]


class TestScopeAndStorage:
    async def test_counts_bytes_and_range_only_of_this_project(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        await _add_photo(
            db_session, project, "a.jpg", content_length=1_000, taken_at=datetime(2019, 4, 2, 10)
        )
        await _add_photo(
            db_session, project, "b.jpg", content_length=2_500, taken_at=datetime(2019, 4, 19, 18)
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["photo_count"] == 2
        assert payload["storage"]["opencloud_bytes"] == 3_500
        assert payload["taken_at_earliest"] == "2019-04-02T10:00:00"
        assert payload["taken_at_latest"] == "2019-04-19T18:00:00"

    async def test_a_single_photo_yields_an_identical_start_and_end(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        await _add_photo(db_session, project, "a.jpg", taken_at=datetime(2020, 1, 1, 8))

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["taken_at_earliest"] == payload["taken_at_latest"] == "2020-01-01T08:00:00"

    async def test_the_range_follows_a_camera_offset_without_a_code_change(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """specs/features/0426-zeitversatz-je-kamera.md: `min`/`max` laufen in SQL ueber
        `Photo.taken_at`, und das traegt seit ADR 0090 die KORRIGIERTE Zeit - der
        Aufnahmezeitraum folgt dem Versatz ohne eine Zeile Codeaenderung. Der Datensatz ist so
        gewaehlt, dass das Ergebnis mit der aufgezeichneten Zeit ANDERS ausfaellt: ohne Versatz
        begaenne der Zeitraum um 10:00, mit ihm um 08:00."""
        project = await _make_project(db_session, "Costa Rica")
        camera = ProjectCamera(
            project_id=project.id, make="Canon", model="EOS 5D", offset_minutes=-120
        )
        db_session.add(camera)
        await db_session.commit()
        await db_session.refresh(camera)
        recorded = datetime(2019, 4, 2, 10)
        shifted_photo = await _add_photo(db_session, project, "a.jpg", taken_at=recorded)
        shifted_photo.camera_id = camera.id
        shifted_photo.taken_at = recorded - timedelta(minutes=120)
        await _add_photo(db_session, project, "b.jpg", taken_at=datetime(2019, 4, 19, 18))
        await db_session.commit()

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["taken_at_earliest"] == "2019-04-02T08:00:00"
        assert payload["taken_at_latest"] == "2019-04-19T18:00:00"

    async def test_the_cache_measurement_feeds_storage_and_thumbnails_ready(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        complete = await _add_photo(db_session, project, "a.jpg")
        partial = await _add_photo(db_session, project, "b.jpg")
        await _add_photo(db_session, project, "c.jpg")
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        thumbnail_path(cache_dir, complete.id, complete.etag).write_bytes(b"x" * 100)
        display_path(cache_dir, complete.id, complete.etag).write_bytes(b"x" * 400)
        thumbnail_path(cache_dir, partial.id, partial.etag).write_bytes(b"x" * 50)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["storage"]["local_cache_bytes"] == 550
        assert payload["progress"]["thumbnails_ready"] == 1
        assert payload["progress"]["scanned"] == 3


class TestTheMotifDistribution:
    """specs/features/0427-motive-mit-staerke.md, PR 3 Schritt 4/6: EIN Abschnitt "Motivverteilung"
    statt "Kategorienverteilung" und "Konfidenz der Kategorie-Erkennung".

    Zwei Zusagen tragen hier mehr als eine Werteprüfung, und beide stehen als NACHSATZ JEDES
    Falls (nicht als eigener Test, sonst deckten sie genau den einen Aufbau ab):

    * die drei Bänder je Motiv sind disjunkt und erschöpfend - ihre Summe je Motiv ist die Zahl
      der beurteilten Fotos;
    * die Summe der starken Bandzahlen über alle Motive darf die Fotozahl übersteigen. Genau das
      ist der Grund für den dauerhaft sichtbaren Erklärsatz der Oberfläche.
    """

    @staticmethod
    def _assert_bands_are_disjoint_and_exhaustive(
        payload: dict[str, Any], assessed_photo_count: int
    ) -> None:
        for entry in payload["motifs"]:
            total = (
                entry["strong_photo_count"]
                + entry["medium_photo_count"]
                + entry["weak_photo_count"]
            )
            assert total == assessed_photo_count, entry

    async def test_every_motif_is_listed_in_registry_order_with_its_display_name(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert [entry["motif_key"] for entry in payload["motifs"]] == list(MOTIF_REGISTRY)
        assert [entry["display_name"] for entry in payload["motifs"]] == [
            definition.display_name for definition in MOTIF_REGISTRY.values()
        ]
        self._assert_bands_are_disjoint_and_exhaustive(payload, 0)

    async def test_a_photo_strong_in_three_motifs_makes_the_band_sums_exceed_the_photo_count(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """DER tragende Aufbau der neuen Zählweise: ein Foto zählt in mehreren Zeilen, die Summe
        über alle Motive ist deshalb größer als die Zahl der Fotos."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(
            db_session,
            photo,
            strengths={"menschen": 0.9, "landschaft": 0.8, "stadt_strasse": 0.95},
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        strong_total = sum(entry["strong_photo_count"] for entry in payload["motifs"])
        assert strong_total == 3
        assert strong_total > payload["photo_count"]
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    async def test_the_three_bands_split_by_the_registry_boundaries(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(
            db_session,
            photo,
            strengths={"menschen": 0.9, "landschaft": 0.5, "tiere": 0.1},
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_key = {entry["motif_key"]: entry for entry in payload["motifs"]}
        assert by_key["menschen"]["strong_photo_count"] == 1
        assert by_key["landschaft"]["medium_photo_count"] == 1
        assert by_key["tiere"]["weak_photo_count"] == 1
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    @pytest.mark.parametrize(
        ("strength", "expected_band"),
        [
            (MOTIF_STRENGTH_BAND_STRONG, "strong_photo_count"),
            (math.nextafter(MOTIF_STRENGTH_BAND_STRONG, 0.0), "medium_photo_count"),
            (MOTIF_STRENGTH_BAND_MEDIUM, "medium_photo_count"),
            (math.nextafter(MOTIF_STRENGTH_BAND_MEDIUM, 0.0), "weak_photo_count"),
        ],
    )
    async def test_both_boundaries_are_inclusive(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        strength: float,
        expected_band: str,
    ) -> None:
        """Inklusivität als PAAR je Grenze (`>=`), mit dem nächstkleineren darstellbaren Wert als
        Gegenprobe - einzeln bestünde die Assertion auch bei einer verschobenen Grenze."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(db_session, photo, strengths={"menschen": strength})

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_key = {entry["motif_key"]: entry for entry in payload["motifs"]}
        assert by_key["menschen"][expected_band] == 1
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    async def test_the_bands_count_the_effective_strength_not_the_stored_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die eine Zusage, die nur dieser Aufbau von der falschen Implementierung unterscheidet:
        ein Foto mit gespeicherter Stärke 0.9 und `applies=false` zählt ins SCHWACHE Band. Eine
        Aggregation direkt auf `photo_motif_strengths` liefert überall sonst dieselben Zahlen."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(db_session, photo, strengths={"menschen": 0.9})
        await _add_correction(
            db_session, photo, "menschen", applies=False, user=await _current_user(db_session)
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_key = {entry["motif_key"]: entry for entry in payload["motifs"]}
        assert by_key["menschen"]["strong_photo_count"] == 0
        assert by_key["menschen"]["weak_photo_count"] == 1
        assert by_key["menschen"]["average_strength"] == pytest.approx(0.0)
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    async def test_a_positive_correction_lifts_a_weak_strength_into_the_strong_band(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Gegenrichtung desselben Paares."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(db_session, photo, strengths={"menschen": 0.05})
        await _add_correction(
            db_session, photo, "menschen", applies=True, user=await _current_user(db_session)
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_key = {entry["motif_key"]: entry for entry in payload["motifs"]}
        assert by_key["menschen"]["strong_photo_count"] == 1
        assert by_key["menschen"]["average_strength"] == pytest.approx(1.0)
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    async def test_the_average_is_the_arithmetic_mean_of_the_effective_strengths(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo_a = await _add_photo(db_session, project, "a.jpg")
        photo_b = await _add_photo(db_session, project, "b.jpg")
        await _add_assessment(db_session, photo_a, strengths={"menschen": 0.8})
        await _add_assessment(db_session, photo_b, strengths={"menschen": 0.2})

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_key = {entry["motif_key"]: entry for entry in payload["motifs"]}
        assert by_key["menschen"]["average_strength"] == pytest.approx(0.5)
        self._assert_bands_are_disjoint_and_exhaustive(payload, 2)

    async def test_without_a_single_assessed_photo_the_average_is_none_and_never_zero(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Nicht erhoben" ist keine Null: ein `0.0` behauptete, das Modell habe sich zu 0 %
        geäußert. Keine Division bei null Fotos."""
        project = await _make_project(db_session, "Costa Rica")
        await _add_photo(db_session, project, "a.jpg")

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert len(payload["motifs"]) == len(MOTIF_REGISTRY)
        assert all(entry["average_strength"] is None for entry in payload["motifs"])
        assert all(entry["strong_photo_count"] == 0 for entry in payload["motifs"])
        self._assert_bands_are_disjoint_and_exhaustive(payload, 0)

    async def test_the_strength_bands_come_from_the_registry(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Grenzen gehen mit, damit das Frontend sie nicht hinterlegt - `0.67` dort und `2/3`
        hier verschöben die Grenze um einen Betrag, den kein Fall trifft."""
        project = await _make_project(db_session, "Costa Rica")

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["strength_bands"] == {
            "strong": MOTIF_STRENGTH_BAND_STRONG,
            "medium": MOTIF_STRENGTH_BAND_MEDIUM,
        }

    async def test_a_photo_without_a_header_is_unassessed_and_counted_in_no_band(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Noch nicht klassifiziert" ist etwas anderes als "nichts erkannt" - das Foto fehlt in
        JEDER Zahl der Tabelle und steht als eigene Kennzahl daneben."""
        project = await _make_project(db_session, "Costa Rica")
        assessed = await _add_photo(db_session, project, "a.jpg")
        await _add_photo(db_session, project, "b.jpg")
        await _add_assessment(db_session, assessed, strengths={"menschen": 0.9})

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["unassessed_photo_count"] == 1
        assert payload["photo_count"] == 2
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    async def test_an_excluded_photo_is_counted_in_no_band_but_in_its_own_number(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium: die Statistik zählt ein als Dokument/Screenshot ausgeschlossenes
        Foto in keinem Band. Seine Stärken bleiben gespeichert und werden nicht auf 0 gesetzt -
        sie dürfen hier trotzdem in keiner Bandzahl auftauchen."""
        project = await _make_project(db_session, "Costa Rica")
        regular = await _add_photo(db_session, project, "a.jpg")
        excluded = await _add_photo(db_session, project, "b.jpg")
        await _add_assessment(db_session, regular, strengths={"menschen": 0.9})
        await _add_assessment(
            db_session, excluded, strengths={"menschen": 0.95}, excluded_document=True
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_key = {entry["motif_key"]: entry for entry in payload["motifs"]}
        assert by_key["menschen"]["strong_photo_count"] == 1
        assert payload["excluded_photo_count"] == 1
        assert payload["unassessed_photo_count"] == 0
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    async def test_the_correction_count_counts_rows_not_photos(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(db_session, photo, strengths={"menschen": 0.9})
        user = await _current_user(db_session)
        await _add_correction(db_session, photo, "menschen", applies=False, user=user)
        await _add_correction(db_session, photo, "tiere", applies=True, user=user)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["motif_correction_count"] == 2
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    async def test_a_correction_on_a_photo_without_a_header_is_still_counted(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Korrekturtabelle ist lauf-UNABHÄNGIG: eine Korrektur auf einem noch nicht
        klassifizierten Foto ist gespeichert und zählt, auch wenn keine Bandzahl sie zeigt."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_correction(
            db_session, photo, "menschen", applies=True, user=await _current_user(db_session)
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["motif_correction_count"] == 1
        assert payload["unassessed_photo_count"] == 1
        self._assert_bands_are_disjoint_and_exhaustive(payload, 0)

    async def test_no_number_of_the_block_leaks_across_projects(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Projekt-Skopierung als Muss-Kriterium: keine der drei Motiv-Tabellen trägt eine eigene
        `project_id`, die Einschränkung über `photos` ist die einzige Trennung zwischen zwei
        Projekten."""
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(db_session, photo, strengths={"menschen": 0.9})

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_key = {entry["motif_key"]: entry for entry in payload["motifs"]}
        assert by_key["menschen"]["strong_photo_count"] == 1
        assert by_key["tiere"]["strong_photo_count"] == 0
        assert payload["motif_correction_count"] == 0
        assert payload["excluded_photo_count"] == 0
        assert payload["unassessed_photo_count"] == 0
        self._assert_bands_are_disjoint_and_exhaustive(payload, 1)

    async def test_assessed_plus_unassessed_plus_excluded_always_equals_the_photo_count(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        assessed = await _add_photo(db_session, project, "a.jpg")
        excluded = await _add_photo(db_session, project, "b.jpg")
        await _add_photo(db_session, project, "c.jpg")
        await _add_assessment(db_session, assessed, strengths={"menschen": 0.9})
        await _add_assessment(db_session, excluded, excluded_document=True)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assessed_count = sum(
            payload["motifs"][0][band]
            for band in ("strong_photo_count", "medium_photo_count", "weak_photo_count")
        )
        assert (
            assessed_count + payload["unassessed_photo_count"] + payload["excluded_photo_count"]
            == payload["photo_count"]
        )


class TestTheRanking:
    async def test_the_processing_state_counts_the_rows_of_the_latest_successful_run(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        photo_a = await _add_photo(db_session, project, "a.jpg")
        photo_b = await _add_photo(db_session, project, "b.jpg")
        old_run = await _add_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1)
        )
        await _add_ranking(db_session, old_run, photo_a)
        new_run = await _add_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 2, 1)
        )
        await _add_ranking(db_session, new_run, photo_a)
        await _add_ranking(db_session, new_run, photo_b, rank_position=2)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["progress"]["ranked"] == 2

    async def test_a_newer_failed_run_does_not_displace_the_older_successful_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Edge Case 4: nur ERFOLGREICHE Laeufe zaehlen - ein spaeter fehlgeschlagener Lauf hat
        keine (oder eine unvollstaendige) Rangfolge und wuerde den Bearbeitungsstand leeren."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        good_run = await _add_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1)
        )
        await _add_ranking(db_session, good_run, photo)
        await _add_criterion_scoring_run(
            db_session,
            project,
            status_value=ScanStatus.FAILED,
            started_at=datetime(2023, 3, 1),
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["progress"]["ranked"] == 1

    async def test_the_partition_size_of_a_photo_is_the_size_of_its_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Partition ist allein das Event - ein Foto steht je Lauf in genau einer Zeile, und
        "Rang M von N" bezieht sich auf den Foto-Moment."""
        project = await _make_project(db_session, "Costa Rica")
        photo_a = await _add_photo(db_session, project, "a.jpg")
        photo_b = await _add_photo(db_session, project, "b.jpg")
        run = await _add_criterion_scoring_run(db_session, project, started_at=datetime(2023, 2, 1))
        await _add_ranking(db_session, run, photo_a)
        await _add_ranking(db_session, run, photo_b, rank_position=2)

        photos = (await authenticated_api_client.get(f"/projects/{project.id}/photos")).json()

        assert [item["ranking"]["partition_size"] for item in photos["items"]] == [2, 2]


async def _add_landmark_detection(session: AsyncSession, photo: Photo) -> None:
    session.add(
        PhotoLandmarkDetection(
            photo_id=photo.id,
            name="Eiffelturm",
            confidence=0.9,
            computed_at=datetime(2023, 6, 3, 12, 0),
        )
    )
    await session.commit()


async def _add_remote_category_run(
    session: AsyncSession,
    project: Project,
    *,
    status_value: ScanStatus = ScanStatus.SUCCESS,
    started_at: datetime,
    finished_at: datetime | None = None,
    api_calls: int | None = 0,
    cost_usd: float | None = 0.0,
) -> RemoteCategoryClassificationRun:
    run = RemoteCategoryClassificationRun(
        project_id=project.id, status=status_value, api_calls=api_calls, cost_usd=cost_usd
    )
    run.started_at = started_at
    run.finished_at = finished_at
    session.add(run)
    await session.commit()
    await _null_out_cost_columns(session, run, api_calls=api_calls, cost_usd=cost_usd)
    await session.refresh(run)
    return run


class TestCosts:
    """Akzeptanzkriterien K3-K5, ADR 0051 Punkt 5 - die Vierfeldertafel des
    Unvollstaendigkeits-Hinweises plus Befund (b)."""

    async def test_amounts_are_summed_per_purpose_over_all_runs(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 1, 1),
            landmark_api_calls=5,
            landmark_cost_usd=1.5,
        )
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 2, 1),
            landmark_api_calls=3,
            landmark_cost_usd=0.75,
        )
        await _add_remote_category_run(
            db_session, project, started_at=datetime(2023, 1, 5), api_calls=10, cost_usd=2.0
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["landmark"]["cost_usd"] == pytest.approx(2.25)
        assert by_purpose["remote_category"]["cost_usd"] == pytest.approx(2.0)
        assert payload["cost"]["total_usd"] == pytest.approx(4.25)

    async def test_a_failed_run_still_contributes_its_amount(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein Lauf, der nach der Cloud-Phase gescheitert ist, hat das Geld trotzdem ausgegeben."""
        project = await _make_project(db_session, "Costa Rica")
        await _add_criterion_scoring_run(
            db_session,
            project,
            status_value=ScanStatus.FAILED,
            started_at=datetime(2023, 1, 1),
            landmark_api_calls=5,
            landmark_cost_usd=1.5,
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["landmark"]["cost_usd"] == pytest.approx(1.5)

    async def test_the_total_is_exactly_the_sum_of_both_entries(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Edge Case 15: serverseitig ungerundet - sonst koennte die angezeigte Summe von der
        Summe der angezeigten Einzelposten abweichen."""
        project = await _make_project(db_session, "Costa Rica")
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 1, 1),
            landmark_api_calls=1,
            landmark_cost_usd=0.005,
        )
        await _add_remote_category_run(
            db_session, project, started_at=datetime(2023, 1, 5), api_calls=1, cost_usd=0.007
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["cost"]["total_usd"] == sum(
            entry["cost_usd"] for entry in payload["cost"]["by_purpose"]
        )

    async def test_a_only_recorded_runs_show_an_amount_without_a_hint(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_landmark_detection(db_session, photo)
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 1, 1),
            landmark_api_calls=2,
            landmark_cost_usd=1.0,
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["landmark"]["cost_usd"] == pytest.approx(1.0)
        assert by_purpose["landmark"]["has_unrecorded_runs"] is False

    async def test_b_a_recorded_and_an_old_run_with_results_show_amount_plus_hint(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_landmark_detection(db_session, photo)
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 1, 1),
            landmark_api_calls=2,
            landmark_cost_usd=1.0,
        )
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2022, 1, 1),
            landmark_api_calls=None,
            landmark_cost_usd=None,
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["landmark"]["cost_usd"] == pytest.approx(1.0)
        assert by_purpose["landmark"]["has_unrecorded_runs"] is True

    async def test_c_only_old_runs_with_results_show_zero_plus_hint(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(db_session, photo)
        await _add_remote_category_run(
            db_session,
            project,
            started_at=datetime(2022, 1, 1),
            api_calls=None,
            cost_usd=None,
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["remote_category"]["cost_usd"] == 0.0
        assert by_purpose["remote_category"]["has_unrecorded_runs"] is True

    async def test_d_old_runs_without_results_show_zero_without_a_hint(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der haeufigste Fehlalarm: ein Projekt, das die Cloud-Nutzung nie aktiviert hatte, hat
        zwar Altlaeufe, aber nachweislich nichts ausgegeben."""
        project = await _make_project(db_session, "Costa Rica")
        await _add_photo(db_session, project, "a.jpg")
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2022, 1, 1),
            landmark_api_calls=None,
            landmark_cost_usd=None,
        )
        await _add_remote_category_run(
            db_session, project, started_at=datetime(2022, 1, 1), api_calls=None, cost_usd=None
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["cost"]["total_usd"] == 0.0
        assert all(entry["has_unrecorded_runs"] is False for entry in payload["cost"]["by_purpose"])

    async def test_e_calls_without_an_amount_trigger_the_hint_even_without_results(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Befund (b): `api_calls > 0` bei Betrag `0` ist bei Token-Preisen groesser null
        strukturell unmoeglich - hier greift der Hinweis auch ohne Ergebniszeile."""
        project = await _make_project(db_session, "Costa Rica")
        await _add_photo(db_session, project, "a.jpg")
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 1, 1),
            landmark_api_calls=4,
            landmark_cost_usd=0.0,
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["landmark"]["has_unrecorded_runs"] is True

    async def test_e_calls_with_a_null_amount_trigger_the_hint_too(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        await _add_remote_category_run(
            db_session, project, started_at=datetime(2023, 1, 1), api_calls=4, cost_usd=None
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["remote_category"]["has_unrecorded_runs"] is True

    async def test_the_landmark_blind_spot_of_finding_a_is_documented_behaviour(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Bewusst getragene Grenze (ADR 0051 Punkt 5, "Bekannte Grenzen" der Spec): ein ALTLAUF,
        der Aufrufe abgesetzt, aber keine Sehenswuerdigkeit gefunden hat, hinterlaesst keine
        `photo_landmark_detections`-Zeile - Befund (a) greift dann nicht, und die Aufrufzahl von
        damals existiert nirgends. Hier per Test festgeschrieben, damit die Luecke nicht
        unbemerkt zur vermeintlich korrekten Aussage wird."""
        project = await _make_project(db_session, "Costa Rica")
        await _add_photo(db_session, project, "a.jpg")
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2022, 1, 1),
            landmark_api_calls=None,
            landmark_cost_usd=None,
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["landmark"]["has_unrecorded_runs"] is False

    async def test_the_hint_of_one_purpose_does_not_bleed_into_the_other(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 1, 1),
            landmark_api_calls=4,
            landmark_cost_usd=0.0,
        )
        await _add_remote_category_run(
            db_session, project, started_at=datetime(2023, 1, 5), api_calls=2, cost_usd=0.5
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["landmark"]["has_unrecorded_runs"] is True
        assert by_purpose["remote_category"]["has_unrecorded_runs"] is False

    async def test_costs_of_another_project_never_leak(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["cost"]["total_usd"] == 0.0


class TestProgress:
    async def test_each_stage_counts_only_photos_of_this_project(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        photo_a = await _add_photo(db_session, project, "a.jpg")
        photo_b = await _add_photo(db_session, project, "b.jpg")
        await _add_photo(db_session, project, "c.jpg")
        await _add_score(db_session, photo_a)
        await _add_score(db_session, photo_b)
        await _add_assessment(db_session, photo_a)
        run = await _add_criterion_scoring_run(db_session, project, started_at=datetime(2023, 1, 1))
        await _add_ranking(db_session, run, photo_a)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["progress"] == {
            "scanned": 3,
            "thumbnails_ready": 0,
            "ausschuss_scored": 2,
            "ranked": 1,
            "remote_classified": 1,
        }

    async def test_only_the_latest_successful_run_contributes_to_ranked(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        old_run = await _add_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1)
        )
        await _add_ranking(db_session, old_run, photo)
        new_run = await _add_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 2, 1)
        )
        await _add_ranking(db_session, new_run, photo)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["progress"]["ranked"] == 1


class TestRatings:
    """Akzeptanzkriterium F2 und Security-Abschnitt Punkt 2: ausschliesslich die Bewertungen des
    ANGEMELDETEN Nutzers.

    Seit ADR 0098 zerlegen die vier Zahlen den Bestand NICHT mehr ueberschneidungsfrei:
    `favorite` kommt aus einer eigenen Spalte und steht neben der Albumentscheidung, `unrated`
    zaehlt die Abwesenheit einer Albumentscheidung."""

    async def test_only_the_own_ratings_are_counted(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo_a = await _add_photo(db_session, project, "a.jpg")
        photo_b = await _add_photo(db_session, project, "b.jpg")
        photo_c = await _add_photo(db_session, project, "c.jpg")
        await _add_photo(db_session, project, "d.jpg")
        me = await _current_user(db_session)
        await _add_rating(db_session, photo_a, me, favorite=True)
        await _add_rating(db_session, photo_b, me, RatingStatus.ALBUM_WORTHY)
        await _add_rating(db_session, photo_c, me, RatingStatus.REJECTED)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["ratings"] == {
            "favorite": 1,
            "album_worthy": 1,
            "rejected": 1,
            # Das nur als Favorit markierte Foto UND das voellig unberuehrte: beide tragen keine
            # Albumentscheidung.
            "unrated": 2,
        }

    async def test_the_favorite_count_comes_from_the_column_not_from_the_status(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 17, dritte der drei Lesestellen, und Auflage S11: Diese Zahl bricht
        NICHT laut, wenn sie den entfallenen Statuswert weiterzaehlt - sie liest still `0` und
        behauptet damit, es gebe keine Favoriten.

        Das Foto mit BEIDEM ist der tragende Teil des Aufbaus: Es zaehlt in `favorite` UND in
        `album_worthy`, was eine Umsetzung ueber sich ausschliessende Statuswerte nicht kann."""
        project = await _make_project(db_session, "Costa Rica")
        only_favorite = await _add_photo(db_session, project, "a.jpg")
        both = await _add_photo(db_session, project, "b.jpg")
        me = await _current_user(db_session)
        await _add_rating(db_session, only_favorite, me, favorite=True)
        await _add_rating(db_session, both, me, RatingStatus.ALBUM_WORTHY, favorite=True)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["ratings"] == {
            "favorite": 2,
            "album_worthy": 1,
            "rejected": 0,
            "unrated": 1,
        }

    async def test_a_row_without_an_album_decision_still_counts_as_unrated(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 18: `group_by(Rating.status)` haette jetzt eine `NULL`-Gruppe, und ein
        `sum(counts.values())` zaehlte sie als "bewertet" mit - `unrated` waere zu klein, ohne
        dass irgendetwas rot wuerde. Der Aufbau hat GENAU EIN Foto, damit die Zahl nicht
        zufaellig stimmt."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        me = await _current_user(db_session)
        await _add_rating(db_session, photo, me, favorite=True)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["ratings"]["unrated"] == 1
        assert payload["ratings"]["favorite"] == 1

    async def test_ratings_of_the_second_user_alone_leave_everything_unrated(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Edge Case 10: haette nur die andere Person bewertet, waere ihr Fortschritt sonst aus
        der Differenz rekonstruierbar."""
        project = await _make_project(db_session, "Costa Rica")
        photo_a = await _add_photo(db_session, project, "a.jpg")
        photo_b = await _add_photo(db_session, project, "b.jpg")
        other = await _add_second_user(db_session)
        await _add_rating(db_session, photo_a, other, RatingStatus.ALBUM_WORTHY, favorite=True)
        await _add_rating(db_session, photo_b, other, RatingStatus.REJECTED)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["ratings"] == {
            "favorite": 0,
            "album_worthy": 0,
            "rejected": 0,
            "unrated": 2,
        }

    async def test_a_photo_rated_differently_by_both_counts_once_under_the_own_status(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        me = await _current_user(db_session)
        other = await _add_second_user(db_session)
        await _add_rating(db_session, photo, me, RatingStatus.ALBUM_WORTHY)
        await _add_rating(db_session, photo, other, RatingStatus.REJECTED)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["ratings"] == {
            "favorite": 0,
            "album_worthy": 1,
            "rejected": 0,
            "unrated": 0,
        }

    async def test_the_album_decisions_and_unrated_partition_the_photo_count(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Was von der alten Zusage "die vier Werte summieren sich zu `photo_count`" bleibt:
        Die ALBUMENTSCHEIDUNG ist dreiwertig und erschoepfend (`album_worthy`, `rejected`,
        keine). `favorite` steht daneben und darf in dieser Summe nicht vorkommen - hier traegt
        ein Foto es zusaetzlich zu seiner Albumentscheidung."""
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        photo_a = await _add_photo(db_session, project, "a.jpg")
        await _add_photo(db_session, project, "b.jpg")
        me = await _current_user(db_session)
        other = await _add_second_user(db_session)
        await _add_rating(db_session, photo_a, me, RatingStatus.ALBUM_WORTHY, favorite=True)
        await _add_rating(db_session, photo_a, other, RatingStatus.REJECTED)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        ratings = payload["ratings"]
        assert (
            ratings["album_worthy"] + ratings["rejected"] + ratings["unrated"]
            == payload["photo_count"]
        )
        assert ratings["favorite"] == 1

    async def test_the_answer_never_names_another_user(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Muss (negativ): keine Kennzahl wird nach Nutzer aufgeschluesselt, und weder `user_id`
        noch `username` einer anderen Person taucht auf."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        other = await _add_second_user(db_session, username="ehefrau")
        await _add_rating(db_session, photo, other, RatingStatus.ALBUM_WORTHY, favorite=True)

        raw = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).text

        assert "ehefrau" not in raw
        assert "user_id" not in raw
        assert "username" not in raw


class TestLastSuccessfulRuns:
    async def test_each_kind_reports_its_latest_successful_finish(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        db_session.add(
            ScanRun(
                project_id=project.id,
                status=ScanStatus.SUCCESS,
                finished_at=datetime(2023, 5, 1, 9),
                files_skipped=0,
            )
        )
        scoring_run = ScoringRun(
            project_id=project.id,
            status=ScanStatus.SUCCESS,
            finished_at=datetime(2023, 5, 2, 9),
        )
        db_session.add(scoring_run)
        await db_session.commit()
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 5, 3),
            finished_at=datetime(2023, 5, 3, 9),
        )
        await _add_remote_category_run(
            db_session,
            project,
            started_at=datetime(2023, 5, 4),
            finished_at=datetime(2023, 5, 4, 9),
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["last_successful_runs"] == {
            "scan": "2023-05-01T09:00:00",
            "scoring": "2023-05-02T09:00:00",
            "classification": "2023-05-03T09:00:00",
            "remote_category_classification": "2023-05-04T09:00:00",
        }

    async def test_a_running_or_failed_run_does_not_change_the_reported_moment(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        await _add_criterion_scoring_run(
            db_session,
            project,
            started_at=datetime(2023, 5, 1),
            finished_at=datetime(2023, 5, 1, 9),
        )
        await _add_criterion_scoring_run(
            db_session,
            project,
            status_value=ScanStatus.FAILED,
            started_at=datetime(2023, 6, 1),
            finished_at=datetime(2023, 6, 1, 9),
        )
        await _add_criterion_scoring_run(
            db_session, project, status_value=ScanStatus.RUNNING, started_at=datetime(2023, 7, 1)
        )

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["last_successful_runs"]["classification"] == "2023-05-01T09:00:00"


class TestDiagnostics:
    async def test_files_skipped_comes_from_the_last_started_scan_run_whatever_its_status(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Edge Case 20 / Akzeptanzkriterium D2: der zuletzt GESTARTETE Lauf, unabhaengig von
        seinem Status - nicht der letzte erfolgreiche."""
        project = await _make_project(db_session, "Costa Rica")
        older = ScanRun(
            project_id=project.id,
            status=ScanStatus.SUCCESS,
            finished_at=datetime(2023, 1, 2),
            files_skipped=3,
        )
        older.started_at = datetime(2023, 1, 1)
        newer = ScanRun(project_id=project.id, status=ScanStatus.FAILED, files_skipped=12)
        newer.started_at = datetime(2023, 2, 1)
        db_session.add_all([older, newer])
        await db_session.commit()

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["diagnostics"]["last_scan_files_skipped"] == 12

    async def test_duplicates_count_photos_not_clusters(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Edge Case 19: ein Cluster aus drei Fotos ergibt ZWEI Duplikate - das Originalfoto
        zaehlt nicht mit."""
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        original = await _add_photo(db_session, project, "a.jpg")
        duplicate_one = await _add_photo(db_session, project, "b.jpg")
        duplicate_two = await _add_photo(db_session, project, "c.jpg")
        await _add_score(db_session, original)
        await _add_score(db_session, duplicate_one, duplicate_of=original.id)
        await _add_score(db_session, duplicate_two, duplicate_of=original.id)

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["diagnostics"]["duplicate_photo_count"] == 2

    async def test_remote_failures_are_reported_per_purpose(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        await _noise_project(db_session, tmp_path)
        project = await _make_project(db_session, "Costa Rica")
        photo_a = await _add_photo(db_session, project, "a.jpg")
        photo_b = await _add_photo(db_session, project, "b.jpg")
        for photo, phase in (
            (photo_a, CloudVisionPhase.LANDMARK),
            (photo_b, CloudVisionPhase.LANDMARK),
            (photo_a, CloudVisionPhase.REMOTE_CATEGORY),
        ):
            db_session.add(
                PhotoCloudVisionError(
                    photo_id=photo.id,
                    phase=phase,
                    error_type="LandmarkApiError",
                    error_message="Zeitueberschreitung",
                    attempted_at=datetime(2023, 6, 1),
                )
            )
        await db_session.commit()

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        assert payload["diagnostics"]["remote_failures"] == [
            {"purpose": "landmark", "photo_count": 2},
            {"purpose": "remote_category", "photo_count": 1},
        ]

    async def test_a_successful_retry_lowers_the_failure_count_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Edge Case 18 / Akzeptanzkriterium D1: die Zahl ist ein IST-Zustand, keine Historie -
        ADR 0035 loescht die Fehler-Zeile beim erfolgreichen Retry."""
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        error = PhotoCloudVisionError(
            photo_id=photo.id,
            phase=CloudVisionPhase.LANDMARK,
            error_type="LandmarkApiError",
            error_message="Zeitueberschreitung",
            attempted_at=datetime(2023, 6, 1),
        )
        db_session.add(error)
        await db_session.commit()

        before = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()
        assert before["diagnostics"]["remote_failures"][0]["photo_count"] == 1

        await db_session.delete(error)
        await db_session.commit()

        after = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()
        assert after["diagnostics"]["remote_failures"][0]["photo_count"] == 0


# --- specs/features/0299-kategorie-konfidenz-anzeigen.md, Umsetzungsschritt 5 -----------------


class TestTheLiveCountersNeverTriggerTheIncompletenessHint:
    """specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-
    vier-teilschritte-und-laufeigene-cloud-bilanz.md Punkt 2/8.

    DER Test, der rot wird, falls jemand die neuen Live-Zaehler doch in die Buchfuehrungsspalten
    legt. Naheliegend waere, `api_calls`/`landmark_api_calls` waehrend des Laufs hochzuzaehlen -
    das erfuellte Befund (b) (`api_calls > 0` bei Betrag `0`/`NULL`) bei JEDEM laufenden Cloud-Lauf
    und faerbte die Statistikseite mitten im Betrieb mit einem Fehlalarm ein. Auf einer Seite,
    deren einziger Zweck Kostenkontrolle ist, ist ein Fehlalarm so schaedlich wie eine Fehlzahl.

    Die Zeilen werden direkt konstruiert (ein laufender Lauf laesst sich nicht abwarten), samt
    mindestens einem vorhandenen Ergebnis im Projekt - sonst waere schon die zweite Teilbedingung
    von Befund (a) unerfuellt und der Test bestuende aus dem falschen Grund."""

    async def test_a_running_landmark_phase_does_not_trigger_the_hint(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_landmark_detection(db_session, photo)
        run = await _add_criterion_scoring_run(
            db_session,
            project,
            status_value=ScanStatus.RUNNING,
            started_at=datetime(2023, 1, 1),
            landmark_api_calls=0,
            landmark_cost_usd=0.0,
        )
        run.phase = ClassificationPhase.LANDMARK
        run.landmark_photos_total = 10
        run.landmark_photos_processed = 4
        run.landmark_failed_calls = 1
        await db_session.commit()

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["landmark"]["has_unrecorded_runs"] is False
        assert by_purpose["remote_category"]["has_unrecorded_runs"] is False

    async def test_a_running_remote_phase_does_not_trigger_the_hint(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, "Costa Rica")
        photo = await _add_photo(db_session, project, "a.jpg")
        await _add_assessment(db_session, photo)
        run = await _add_remote_category_run(
            db_session,
            project,
            status_value=ScanStatus.RUNNING,
            started_at=datetime(2023, 1, 1),
            api_calls=0,
            cost_usd=0.0,
        )
        run.photos_total = 10
        run.photos_processed = 4
        run.failed_calls = 1
        await db_session.commit()

        payload = (await authenticated_api_client.get(f"/projects/{project.id}/stats")).json()

        by_purpose = {entry["purpose"]: entry for entry in payload["cost"]["by_purpose"]}
        assert by_purpose["remote_category"]["has_unrecorded_runs"] is False
        assert by_purpose["landmark"]["has_unrecorded_runs"] is False
