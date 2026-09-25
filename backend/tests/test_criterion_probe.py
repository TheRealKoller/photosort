"""Tests fuer das rein lesende Messkommando der Gebaeude-Allow-Liste
(specs/features/0283-gebaeude-allow-liste-gegen-modell-labels.md, Abschnitt 6/7).

Aufbau nach architecture/0002-testkonzept.md, Sektion "Ein rein lesendes Kommando im
Produktivpaket": die Zaehlbloecke rein und ohne DB, die duenne Leseschicht gegen die
`db_session`-Fixture, `main()` synchron gegen eine dateibasierte SQLite in `tmp_path`.

Der Lesepfad ist zugleich die Gegenprobe zur geteilten Quelle der Wahrheit: Er nimmt
`criteria.py::is_landmark_candidate` und `api/projects.py::_count_landmark_candidates` selbst,
statt die Schwellen in einer zweiten Fassung nachzubauen.
"""

from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.criteria import CRITERIA_REGISTRY, LANDMARK_CANDIDATE_CRITERION_KEYS
from photosort.criterion_probe import (
    NOT_MEASURED,
    CriterionCounts,
    CriterionProbeError,
    CriterionProbeInput,
    _number,
    _report_head,
    criterion_counts,
    landmark_candidates,
    main,
    read_criterion_probe_input,
    render_report,
)
from photosort.db import Base, make_engine, make_session_factory
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from tests.import_closure import import_closure, module_file
from tests.write_guard import write_statements

REPO_ROOT = Path(__file__).resolve().parents[2]

# Je Wert ein unterscheidbarer, in dieser Datei einmaliger Inhalt - so faellt im Bericht auf,
# was von hier aus durchgereicht wurde (S2).
MEASURED_TAKEN_AT = datetime(2029, 3, 4, 3, 47, 0)
MEASURED_PROJECT_NAME = "Familienurlaub"
MEASURED_OPENCLOUD_PATH = "/OpenCloud/Geheim/Familienurlaub"
MEASURED_PHOTO_FILE = "geheim-foto"
MEASURED_LAT = 43.51
MEASURED_LON = 16.44
MEASURED_LANDMARK = "Geheime Sehenswuerdigkeit"


# --- Die Zaehlbloecke, rein ------------------------------------------------------------------------


class TestCriterionCounts:
    """Die Verteilung eines Kriteriums ist eine reine Zaehlung ueber die gelesenen Zeilen."""

    def test_every_criterion_appears_even_without_a_single_row(self) -> None:
        """Ein Kriterium, das aus dem Bericht faellt, waere still unvollstaendig, ohne dass eine
        Summe kleiner wuerde."""
        counts = criterion_counts([])

        assert tuple(entry.criterion_key for entry in counts) == LANDMARK_CANDIDATE_CRITERION_KEYS
        assert all(entry.photos_with_a_value == 0 for entry in counts)
        assert all(entry.at_zero == 0 for entry in counts)
        assert all(entry.above_zero == 0 for entry in counts)

    def test_the_hand_computed_distribution(self) -> None:
        """Die Grenze ist `> 0.0`, nicht die Praesenzgrenze: die Frage ist "hat das Kriterium
        ueberhaupt gegriffen"."""
        rows = [
            (1, "gebaeude", 1.0),
            (1, "landschaft", 0.0),
            (2, "gebaeude", 0.0),
            (2, "landschaft", 0.5),
            (3, "gebaeude", 0.0),
            (3, "landschaft", 0.0),
            (4, "gebaeude", 0.4),
        ]

        counts = {entry.criterion_key: entry for entry in criterion_counts(rows)}

        assert counts["gebaeude"] == CriterionCounts(
            criterion_key="gebaeude", photos_with_a_value=4, at_zero=2, above_zero=2
        )
        assert counts["landschaft"] == CriterionCounts(
            criterion_key="landschaft", photos_with_a_value=3, at_zero=2, above_zero=1
        )

    def test_a_row_of_another_criterion_is_skipped(self) -> None:
        """Eine Zeile mehr darf keine Klasse verschieben - der Lesepfad fragt ohnehin nur die
        beiden Kandidaten-Kriterien."""
        counts = {entry.criterion_key: entry for entry in criterion_counts([(1, "sharpness", 0.9)])}

        assert set(counts) == set(LANDMARK_CANDIDATE_CRITERION_KEYS)
        assert all(entry.photos_with_a_value == 0 for entry in counts.values())


class TestLandmarkCandidates:
    """Die obere, listenabhaengige Zahl - ueber dieselbe reine Funktion wie der Lauf."""

    def test_a_photo_counts_once_however_many_criteria_it_meets(self) -> None:
        """Gezaehlt werden FOTOS, nie Zeilen."""
        rows = [(1, "gebaeude", 1.0), (1, "landschaft", 1.0)]

        assert landmark_candidates(rows) == 1

    def test_a_missing_criterion_counts_as_zero(self) -> None:
        assert landmark_candidates([(1, "gebaeude", 1.0)]) == 1
        assert landmark_candidates([(1, "gebaeude", 0.0)]) == 0

    def test_the_threshold_comes_from_the_registry_inclusive(self) -> None:
        """Gegenprobe gegen eine zweite, nachgebaute Schwelle: `is_landmark_candidate` prueft
        `>=` gegen `presence_threshold`."""
        threshold = CRITERIA_REGISTRY["gebaeude"].presence_threshold
        assert threshold is not None

        assert landmark_candidates([(1, "gebaeude", threshold)]) == 1
        assert landmark_candidates([(1, "gebaeude", 0.0)]) == 0

    def test_a_row_of_another_criterion_cannot_make_a_candidate(self) -> None:
        assert landmark_candidates([(1, "sharpness", 1.0)]) == 0


# --- Der Lesepfad ----------------------------------------------------------------------------------


async def _project(session: AsyncSession, name: str = "Reise") -> int:
    project = Project(name=name, opencloud_drive_id="drive", opencloud_path=f"/Fotos/{name}")
    session.add(project)
    await session.flush()
    return project.id


async def _photo(session: AsyncSession, project_id: int, *, index: int) -> int:
    photo = Photo(
        project_id=project_id,
        relative_path=f"{MEASURED_PHOTO_FILE}-{index:03d}.jpg",
        etag=f"etag-{project_id}-{index}",
        content_length=1000,
        taken_at=MEASURED_TAKEN_AT + timedelta(minutes=index),
        taken_at_original=MEASURED_TAKEN_AT + timedelta(minutes=index),
        last_modified=MEASURED_TAKEN_AT,
        gps_lat=MEASURED_LAT,
        gps_lon=MEASURED_LON,
    )
    session.add(photo)
    await session.flush()
    return photo.id


async def _criterion_score(
    session: AsyncSession, photo_id: int, criterion_key: str, value: float
) -> None:
    session.add(
        PhotoCriterionScore(
            photo_id=photo_id,
            criterion_key=criterion_key,
            value=value,
            source=CriterionSource.LOCAL_ML,
            computed_at=MEASURED_TAKEN_AT,
        )
    )
    await session.flush()


async def _photo_score(
    session: AsyncSession,
    photo_id: int,
    *,
    suggested_status: RatingStatus | None = None,
) -> None:
    """Eine Bewertungszeile, die `duplicates.py::survives_ausschuss()` ueberlebt - sofern kein
    Ausschuss-Status gesetzt ist (dann faellt sie aus der Menge der Projekt-Antwort)."""
    session.add(
        PhotoScore(
            photo_id=photo_id,
            sharpness=0.5,
            exposure=0.5,
            suggested_status=suggested_status,
            computed_at=MEASURED_TAKEN_AT,
        )
    )
    await session.flush()


async def _successful_run(
    session: AsyncSession, project_id: int, *, status: ScanStatus = ScanStatus.SUCCESS
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(project_id=project_id, scoring_run_id=scoring_run.id, status=status)
    session.add(run)
    await session.flush()
    return run


# Die gemessene Lage, in beiden Aufbauten dieselbe: fuenf Fotos, drei Kandidaten, davon zwei
# ausschuss- und landmark-bereinigt.
#
# Foto 4 traegt einen Ausschuss-Vorschlag, Foto 5 eine `landmark`-Zeile. Beide sind damit
# GESPEICHERTE Landmark-Kandidaten, aber KEINE Kandidaten der Projekt-Antwort - genau die
# Auseinanderfall-Lage, an der die beiden Zahlen ihren verschiedenen Bezug zeigen.
_MEASURED_LAY: tuple[tuple[str, dict[str, float], RatingStatus | None, bool], ...] = (
    ("bauwerk", {"gebaeude": 1.0, "landschaft": 0.0}, None, False),
    ("kueste", {"gebaeude": 0.0, "landschaft": 1.0}, None, False),
    ("innenhof", {"gebaeude": 0.0, "landschaft": 0.0}, None, False),
    ("aussortiert", {"gebaeude": 1.0, "landschaft": 0.0}, RatingStatus.REJECTED, False),
    ("schon-gescort", {"gebaeude": 1.0, "landschaft": 0.0}, None, True),
)


async def _seed_measured_project(session: AsyncSession) -> int:
    """Baut die Messlage auf. SCHREIBT - aber im TEST, nie im Kommando."""
    project_id = await _project(session, MEASURED_PROJECT_NAME)
    first_photo_id: int | None = None
    for index, (_, values, status, already_scored) in enumerate(_MEASURED_LAY, start=1):
        photo_id = await _photo(session, project_id, index=index)
        if first_photo_id is None:
            first_photo_id = photo_id
        for criterion_key, value in values.items():
            await _criterion_score(session, photo_id, criterion_key, value)
        await _photo_score(session, photo_id, suggested_status=status)
        if already_scored:
            await _criterion_score(session, photo_id, "landmark", 1.0)
    assert first_photo_id is not None
    # Eine Erkenntnis des bezahlten Dienstes - sie liegt vor und darf den Bericht nicht erreichen.
    session.add(
        PhotoLandmarkDetection(
            photo_id=first_photo_id,
            name=MEASURED_LANDMARK,
            confidence=0.9,
            computed_at=MEASURED_TAKEN_AT,
        )
    )
    await _successful_run(session, project_id)
    return project_id


def _prepared(tmp_path: Path) -> tuple[str, int]:
    """Eine dateibasierte SQLite mit der Messlage darin - der Aufrufer bekommt URL und Projekt-Id."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

    async def prepare() -> int:
        engine = make_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = make_session_factory(engine)
        async with factory() as session:
            project_id = await _seed_measured_project(session)
            await session.commit()
        await engine.dispose()
        return project_id

    return url, asyncio.run(prepare())


@pytest.mark.asyncio
class TestTheReadPath:
    """Der einzige Datenbankzugriff des Kommandos - und er liest ausschliesslich."""

    async def test_an_unknown_project_refuses_loudly(self, db_session: AsyncSession) -> None:
        with pytest.raises(CriterionProbeError):
            await read_criterion_probe_input(db_session, 4711)

    async def test_a_project_without_a_successful_run_counts_nothing(
        self, db_session: AsyncSession
    ) -> None:
        """Ohne erfolgreichen Lauf wird GAR NICHT ERST gezaehlt: Eine Zahl aus einem frueheren,
        gescheiterten Zustand saehe aus wie eine Messung."""
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, index=1)
        await _criterion_score(db_session, photo_id, "gebaeude", 1.0)
        await _photo_score(db_session, photo_id)

        probe = await read_criterion_probe_input(db_session, project_id)

        assert probe.run_found is False
        assert probe.run_id is None
        assert probe.counts == ()
        assert probe.landmark_candidates is None
        assert probe.landmark_candidate_count is None
        # Die Fotozahl des Projekts steht daneben - sie haengt nicht am Lauf.
        assert probe.photos_total == 1

    async def test_a_failed_run_is_not_a_measured_run(self, db_session: AsyncSession) -> None:
        project_id = await _project(db_session)
        await _photo(db_session, project_id, index=1)
        await _successful_run(db_session, project_id, status=ScanStatus.FAILED)

        probe = await read_criterion_probe_input(db_session, project_id)

        assert probe.run_found is False

    async def test_only_the_latest_successful_run_is_measured(
        self, db_session: AsyncSession
    ) -> None:
        project_id = await _project(db_session)
        await _photo(db_session, project_id, index=1)
        older = await _successful_run(db_session, project_id)
        newer = await _successful_run(db_session, project_id)

        probe = await read_criterion_probe_input(db_session, project_id)

        assert probe.run_id == newer.id
        assert probe.run_id != older.id

    async def test_the_measured_lay_reaches_the_counts(self, db_session: AsyncSession) -> None:
        project_id = await _seed_measured_project(db_session)

        probe = await read_criterion_probe_input(db_session, project_id)

        counts = {entry.criterion_key: entry for entry in probe.counts}
        assert counts["gebaeude"] == CriterionCounts(
            criterion_key="gebaeude", photos_with_a_value=5, at_zero=2, above_zero=3
        )
        assert counts["landschaft"] == CriterionCounts(
            criterion_key="landschaft", photos_with_a_value=5, at_zero=4, above_zero=1
        )

    async def test_the_photo_count_of_the_project_is_not_the_count_of_photos_with_a_row(
        self, db_session: AsyncSession
    ) -> None:
        """Ein Foto ohne Zeile zu einem Kriterium ist NICHT dasselbe wie ein Foto mit dem Wert
        null. Sonst fiele ein Lauf, der ein Kriterium gar nicht geschrieben hat, mit einem
        zusammen, der es ueberall auf null gesetzt hat."""
        project_id = await _project(db_session)
        with_row = await _photo(db_session, project_id, index=1)
        await _photo(db_session, project_id, index=2)
        await _criterion_score(db_session, with_row, "gebaeude", 1.0)
        await _successful_run(db_session, project_id)

        probe = await read_criterion_probe_input(db_session, project_id)

        assert probe.photos_total == 2
        counts = {entry.criterion_key: entry for entry in probe.counts}
        assert counts["gebaeude"].photos_with_a_value == 1

    async def test_a_row_of_another_project_is_never_read(self, db_session: AsyncSession) -> None:
        """S1 gilt auch fuer den Messpfad: gemessen wird genau ein Projekt."""
        mine = await _project(db_session)
        await _photo(db_session, mine, index=1)
        await _successful_run(db_session, mine)
        other = await _project(db_session, "Fremd")
        other_photo = await _photo(db_session, other, index=1)
        await _criterion_score(db_session, other_photo, "gebaeude", 1.0)
        await _successful_run(db_session, other)

        probe = await read_criterion_probe_input(db_session, mine)

        counts = {entry.criterion_key: entry for entry in probe.counts}
        assert counts["gebaeude"].photos_with_a_value == 0
        assert probe.landmark_candidates == 0

    async def test_only_the_two_candidate_criteria_reach_the_counts(
        self, db_session: AsyncSession
    ) -> None:
        """Ein `sharpness`-Wert von 1.0 ist kein Kandidat und verschiebt keine Klasse."""
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, index=1)
        await _criterion_score(db_session, photo_id, "sharpness", 1.0)
        await _successful_run(db_session, project_id)

        probe = await read_criterion_probe_input(db_session, project_id)

        assert {entry.criterion_key for entry in probe.counts} == set(
            LANDMARK_CANDIDATE_CRITERION_KEYS
        )
        assert probe.landmark_candidates == 0

    async def test_the_two_landmark_numbers_have_different_predicates(
        self, db_session: AsyncSession
    ) -> None:
        """DIE MESSLAGE, an der die beiden Zahlen auseinanderfallen: Vier Fotos tragen einen
        gespeicherten Kandidatenwert, aber nur zwei ueberleben den Ausschuss OHNE `landmark`-Zeile.
        Sie werden nicht verrechnet, sie stehen nebeneinander."""
        project_id = await _seed_measured_project(db_session)

        probe = await read_criterion_probe_input(db_session, project_id)

        assert probe.landmark_candidates == 4
        assert probe.landmark_candidate_count == 2

    async def test_the_project_answer_leaves_out_the_ausschuss_and_the_already_scored(
        self, db_session: AsyncSession
    ) -> None:
        """Die Zahl der Projekt-Antwort kommt aus ihrer eigenen Funktion: Ausschuss faellt weg, ein
        Foto mit `landmark`-Zeile ebenfalls - und die gespeicherte Zaehlung sieht beide trotzdem."""
        project_id = await _project(db_session)
        ausschuss = await _photo(db_session, project_id, index=1)
        await _criterion_score(db_session, ausschuss, "gebaeude", 1.0)
        await _photo_score(db_session, ausschuss, suggested_status=RatingStatus.REJECTED)
        scored = await _photo(db_session, project_id, index=2)
        await _criterion_score(db_session, scored, "gebaeude", 1.0)
        await _criterion_score(db_session, scored, "landmark", 1.0)
        await _photo_score(db_session, scored)
        await _successful_run(db_session, project_id)

        probe = await read_criterion_probe_input(db_session, project_id)

        assert probe.landmark_candidates == 2
        assert probe.landmark_candidate_count == 0


# --- Kopf und Bericht --------------------------------------------------------------------------


def _probe(
    *,
    run_id: int | None = 7,
    photos_total: int = 0,
    counts: tuple[CriterionCounts, ...] = (),
    landmark_candidate_count: int | None = None,
    landmark_value: int | None = None,
) -> CriterionProbeInput:
    """Ein gelesener Bestand ohne Datenbank - `render_report` rechnet rein ueber diese Felder."""
    return CriterionProbeInput(
        project_id=1,
        photos_total=photos_total,
        run_id=run_id,
        counts=counts,
        landmark_candidates=landmark_value,
        landmark_candidate_count=landmark_candidate_count,
    )


class TestTheReportHead:
    """Titel, Projekt-Id, Laufkennung - an genau einer Stelle gebaut."""

    def test_the_head_carries_the_title_the_project_and_the_run(self) -> None:
        assert _report_head(_probe(run_id=7)) == "# Kriterien-Messung, Projekt 1, Lauf 7"

    def test_a_project_without_a_run_gets_no_invented_identifier(self) -> None:
        """ "Lauf 0" oder "Lauf None" waere eine Kennung, die es nicht gibt - der Kopf sagt
        stattdessen, dass kein erfolgreicher Lauf vorliegt."""
        head = _report_head(_probe(run_id=None))

        assert head == "# Kriterien-Messung, Projekt 1, ohne erfolgreichen Lauf"
        assert "Lauf 0" not in head
        assert "Lauf None" not in head


class TestTheRunMarkerCannotDivergeFromTheIdentifier:
    """EIN Feld, nicht zwei."""

    def test_the_marker_is_derived_from_the_identifier_not_stored_beside_it(self) -> None:
        assert _probe(run_id=7).run_found is True
        assert _probe(run_id=None).run_found is False

    def test_the_marker_cannot_be_set_against_the_identifier(self) -> None:
        with pytest.raises(TypeError):
            CriterionProbeInput(
                project_id=1,
                photos_total=0,
                run_id=None,
                run_found=True,  # type: ignore[call-arg]
            )


class TestTheReportWithoutARunReportsNotMeasured:
    """AUSFALLRICHTUNG: "NICHT GEMESSEN" IST NICHT "0"."""

    def test_the_number_is_not_measured_instead_of_zero(self) -> None:
        assert _number(None) == NOT_MEASURED
        assert _number(0) == "0"

    def test_the_report_carries_no_numeric_section(self) -> None:
        """Die guenstigste aller Aussagen ("der Zuwachs ist klein") waere eine Null - sie steht
        hier nirgends, es fehlt stattdessen die ganze Zahlenabteilung."""
        report = render_report(_probe(run_id=None, photos_total=373))

        assert NOT_MEASURED in report
        assert "## Kriterium" not in report
        assert "## Landmark-Kandidaten" not in report
        assert "Fotos im Projekt: 373" in report

    def test_the_report_for_a_measured_run_carries_the_numbers(self) -> None:
        counts = (
            CriterionCounts(
                criterion_key="gebaeude", photos_with_a_value=4, at_zero=1, above_zero=3
            ),
            CriterionCounts(
                criterion_key="landschaft", photos_with_a_value=3, at_zero=2, above_zero=1
            ),
        )
        report = render_report(
            _probe(run_id=7, counts=counts, landmark_value=4, landmark_candidate_count=2)
        )

        assert "## Kriterium gebaeude" in report
        assert "## Kriterium landschaft" in report
        assert "- Fotos mit einem gespeicherten Wert: 4" in report
        assert "- davon mit Wert 0: 1 (25.0 %)" in report
        assert "- davon mit Wert > 0: 3 (75.0 %)" in report
        assert "- nach is_landmark_candidate ueber die gespeicherten Werte: 4" in report
        assert "- landmark_candidate_count der Projekt-Antwort: 2" in report


# --- main() --------------------------------------------------------------------------------------


async def _prepared_project_without_a_run(url: str) -> int:
    engine = make_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = make_session_factory(engine)
    async with factory() as session:
        project_id = await _project(session, "Ohne Lauf")
        await _photo(session, project_id, index=1)
        await session.commit()
    await engine.dispose()
    return project_id


class TestMainRefusesLoudly:
    """Nicht Traceback und nicht stille Null."""

    def test_an_unknown_project_id(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> None:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await engine.dispose()

        asyncio.run(prepare())

        exit_code = main(["--project-id", "999"], database_url=url)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "999" in captured.err
        assert captured.out == ""

    def test_a_project_without_a_successful_run_is_a_measurement_not_an_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"
        project_id = asyncio.run(_prepared_project_without_a_run(url))

        exit_code = main(["--project-id", str(project_id)], database_url=url)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert NOT_MEASURED in captured.out
        assert captured.err == ""

    def test_a_database_error_names_only_the_error_type(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """NIE `str(exc)` und nie ein Traceback - die SQLAlchemy-Meldung kann die `DATABASE_URL`
        samt Zugangsdaten tragen. Die Lage ist eine Datenbank ohne Tabellen."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'ohne-tabellen.db'}"

        exit_code = main(["--project-id", "1"], database_url=url)

        assert exit_code == 1
        error = capsys.readouterr().err
        assert "OperationalError" in error
        assert url not in error

    def test_the_project_id_is_an_integer_argument(self, tmp_path: Path) -> None:
        """S2: `--project-id` ist `argparse type=int`. Eine Zeichenkette wird abgewiesen, bevor
        irgendein Datenbankzugriff entsteht."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        with pytest.raises(SystemExit):
            main(["--project-id", "nicht-ganzzahlig"], database_url=url)

    def test_the_project_id_is_required(self, tmp_path: Path) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        with pytest.raises(SystemExit):
            main([], database_url=url)

    def test_there_is_no_switch_that_would_add_the_names(self, tmp_path: Path) -> None:
        """S2: kein `--namen`-Aequivalent. Verboten ist die Verbindung Klassenname <-> einzelnes
        Foto in jeder Form, auch hinter einem standardmaessig ausgeschalteten Schalter."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        with pytest.raises(SystemExit):
            main(["--project-id", "1", "--namen"], database_url=url)


# --- Ausgabe-Hygiene (S2) ------------------------------------------------------------------------


class TestTheOutputSeparatesNumbersFromPlaces:
    """S2: Der Bericht traegt ausschliesslich Zahlen. Die Messlage traegt je einen unterscheidbaren
    Wert aller verbotenen Klassen, und keiner steht im Bericht - das ist die Bedingung dafuer, dass
    die Zahlen als Ganzes in ein oeffentliches Repository duerfen."""

    def test_the_report_carries_none_of_the_forbidden_classes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id)], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        # 1. Koordinate, 2. Dateiname/OpenCloud-Pfad, 3. Projektname, 4. Sehenswuerdigkeit-Name,
        # 5. Zeitstempel.
        assert str(MEASURED_LAT) not in report
        assert str(MEASURED_LON) not in report
        assert MEASURED_PHOTO_FILE not in report
        assert MEASURED_OPENCLOUD_PATH not in report
        assert MEASURED_PROJECT_NAME not in report
        assert MEASURED_LANDMARK not in report
        assert "2029" not in report
        assert "03:47" not in report
        # ... aber die Zahlen stehen da, samt der Projekt-Id.
        assert f"Projekt {project_id}" in report
        assert "## Kriterium gebaeude" in report
        assert "## Kriterium landschaft" in report
        assert "- nach is_landmark_candidate ueber die gespeicherten Werte: 4" in report
        assert "- landmark_candidate_count der Projekt-Antwort: 2" in report

    def test_no_line_speaks_about_a_single_photo(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Keine Zeile je Foto, auch nicht mit Foto-Id statt Pfad - der Bericht hat keine Tabelle
        ueber Einzelfaelle."""
        url, project_id = _prepared(tmp_path)

        assert main(["--project-id", str(project_id)], database_url=url) == 0

        report = capsys.readouterr().out
        assert ".jpg" not in report
        assert "- Foto " not in report
        assert "Foto 1" not in report


# --- Die Rein-lesend-Zusage, dreifach -----------------------------------------------------------


class TestTheWriteGuardIsNotVacuous:
    """Zwei Referenzfaelle gegen Vakuum-Gruen: Ein Waechter, der nichts erkennt, ist immer gruen.
    Die Mikrotests je Schreibform und die Positiv-Gegenproben stehen bei ihm selbst
    (`test_place_probe.py::TestTheWriteGuardItself`) - er hat nur EINE Definition."""

    def test_a_writing_form_is_still_recognised(self) -> None:
        assert "add()" in write_statements(ast.parse("session.add(row)"))

    def test_a_reading_form_is_still_not_flagged(self) -> None:
        assert (
            write_statements(ast.parse("rows = (await session.execute(select(Photo))).all()")) == []
        )


class TestTheProbeIsReadOnly:
    """Die Zusage "kein Lauf hinterlaesst eine geaenderte, geloeschte oder neue Zeile", in drei
    Teilen - KEIN Teil traegt allein."""

    def test_the_command_is_in_no_import_graph_of_the_application(self) -> None:
        assert "photosort.criterion_probe" not in import_closure("photosort.main")
        assert "photosort.criterion_probe" not in import_closure("photosort.worker")

    def test_the_import_graph_walker_actually_finds_something(self) -> None:
        # Gegenprobe: ohne sie bestuenden die beiden Zusagen oben auch bei einem Walker, der gar
        # nichts findet - Tippfehler im Modulnamen, geaenderte Verzeichnisstruktur.
        assert {"photosort.models", "photosort.config"} <= import_closure("photosort.main")
        assert "photosort.criteria" in import_closure("photosort.criterion_probe")

    def test_the_shared_means_lie_in_the_graph_of_the_run(self) -> None:
        """DIE GEGENPROBE ZUR NACHBAU-GEFAHR: `is_landmark_candidate` und
        `_count_landmark_candidates` MUESSEN im Graphen des Kommandos liegen - sonst waeren aus
        den geteilten Mitteln still Kopien geworden, und das Messkommando maesse etwas anderes als
        der Lauf, waehrend beide fuer sich gruen blieben."""
        in_probe = import_closure("photosort.criterion_probe")

        assert "photosort.criteria" in in_probe
        assert "photosort.api.projects" in in_probe
        # Der Lauf selbst nimmt dieselbe Schwellenwert-Pruefung.
        assert "photosort.criteria" in import_closure("photosort.worker")

    def test_no_compose_file_runs_the_command(self) -> None:
        """Der Abfluss tritt nur ein, wenn Daniel ihn TIPPT - nicht, weil ein Container startet."""
        for compose in sorted(REPO_ROOT.glob("docker-compose*.yml")):
            content = compose.read_text(encoding="utf-8")

            assert "criterion_probe" not in content, compose.name

    def test_the_module_defines_no_endpoint(self) -> None:
        path = module_file("photosort.criterion_probe")
        assert path is not None
        source = path.read_text(encoding="utf-8")

        assert "APIRouter" not in source
        assert "fastapi" not in source

    def test_the_module_contains_no_writing_statement_at_all(self) -> None:
        path = module_file("photosort.criterion_probe")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))

        assert write_statements(tree) == []

    def test_the_module_writes_no_file_and_no_log(self) -> None:
        """S2: Ausgabe ausschliesslich auf stdout. Kein Dateischreiben, nichts ueber den
        strukturierten Anwendungs-Logger und damit nichts in persistente Container-Logs."""
        path = module_file("photosort.criterion_probe")
        assert path is not None
        source = path.read_text(encoding="utf-8")

        assert "logging" not in source
        assert "open(" not in source
        assert "write_text" not in source
        assert "Path(" not in source


async def _table_snapshot(session: AsyncSession) -> dict[str, list[tuple[object, ...]]]:
    """JEDE Tabelle aus `Base.metadata.sorted_tables` - GEMESSEN, nie als handgeschriebene Liste.

    Eine von Hand gepflegte Tabellenliste veraltet still, sobald eine Tabelle hinzukommt; genau
    die neue waere dann die ungepruefte."""
    return {
        table.name: [tuple(row) for row in (await session.execute(select(table))).all()]
        for table in Base.metadata.sorted_tables
    }


class TestARealRunChangesNothing:
    """Teil 3 der Zusage: ein ECHTER `main()`-Lauf gegen eine dateibasierte SQLite, mit
    Schnappschuss jeder Tabelle davor und danach.

    Der Formwaechter allein bestuende gegen ein Modul, das ueber eine Hilfsfunktion schreibt;
    dieser Vergleich allein bestuende gegen einen Schreibpfad, den die Testlage nicht betritt."""

    def test_not_a_single_row_changes(self, tmp_path: Path) -> None:
        url, project_id = _prepared(tmp_path)

        async def snapshot() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            factory = make_session_factory(engine)
            async with factory() as session:
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        before = asyncio.run(snapshot())

        exit_code = main(["--project-id", str(project_id)], database_url=url)

        assert exit_code == 0
        assert asyncio.run(snapshot()) == before

    def test_the_snapshot_actually_covers_something(self, tmp_path: Path) -> None:
        """Gegenprobe: ohne sie bestuende der Vergleich oben auch gegen einen leeren
        Schnappschuss - etwa nach einem Umbau von `Base.metadata`."""
        url, _ = _prepared(tmp_path)

        async def snapshot() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            factory = make_session_factory(engine)
            async with factory() as session:
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        taken = asyncio.run(snapshot())

        assert {
            "projects",
            "photos",
            "photo_scores",
            "photo_criterion_scores",
            "criterion_scoring_runs",
        } <= set(taken)
        assert len(taken["photos"]) == 5
        assert len(taken["photo_criterion_scores"]) == 2 * 5 + 1
