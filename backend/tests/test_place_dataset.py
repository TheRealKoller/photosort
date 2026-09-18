"""Der lokale Ortsdatensatz: der Auflöser im Produktivpfad (`geonames.py`) und das getippte
Bezugskommando, das seinen Auszug bildet (`place_dataset.py`).

Grundlage: ADR 0105 (Wegwahl und Betriebsweg), Spec 0434 Abschnitt 8.

KEIN Test bezieht die echte Datei - die Rohzeilen stehen literal. Die beiden tragenden Nachweise
dieser Datei sind: die GLEICHHEIT von Rohzeilen und Auszug (ohne sie waere "der Auszug verhaelt
sich wie die Rohdatei" eine Behauptung) und das FERNHALTEN des Bezugskommandos von jedem
automatischen Pfad (ein 400-MB-Abruf tritt nur ein, wenn er getippt wird).
"""

from __future__ import annotations

import ast
import dataclasses
import gzip
import logging
from pathlib import Path

import pytest

from photosort.geonames import (
    DATASET_REASON_HASH_MISMATCH,
    DATASET_REASON_HASH_MISSING,
    DATASET_REASON_MISSING,
    GeoNamesResolver,
    PlaceDatasetError,
    build_place_resolver,
    dataset_hash_path,
    geonames_answer,
    geonames_level,
    geonames_match_distances,
    parse_geonames_line,
    sha256_of,
)
from photosort.models import PlaceLookup
from photosort.place_dataset import (
    GEONAMES_ARCHIVE_URL,
    extract_line,
    write_extract,
)
from photosort.places import PlaceAnswer, PlaceInfo, usable_locality
from photosort.scoring import haversine_meters
from tests.import_closure import import_closure, module_file

REPO_ROOT = Path(__file__).resolve().parents[2]

SPLIT = (43.51, 16.44)
BERLIN_KREUZBERG = (52.50, 13.40)
GARMISCH = (47.49, 11.09)


def _geonames_line(name: str, lat: float, lon: float, feature_class: str, feature_code: str) -> str:
    """Eine Rohzeile im echten Format: geonameid, name, asciiname, alternatenames, lat, lon,
    featureClass, featureCode, country, ... - die ungebrauchten Felder tragen hier Inhalt, damit
    der Auszug etwas zu leeren hat."""
    return "\t".join(
        [
            "2950159",
            name,
            name,
            "Berlino,Berlijn",
            str(lat),
            str(lon),
            feature_class,
            feature_code,
            "DE",
            "16",
            "00",
            "3663485",
            "Europe/Berlin",
            "2026-09-14",
        ]
    )


BERLIN_LINES = [
    _geonames_line("Berlin", 52.5200, 13.4050, "P", "PPLC"),
    _geonames_line("Kreuzberg", 52.4980, 13.4030, "P", "PPLX"),
    _geonames_line("Land Berlin", 52.5000, 13.4000, "A", "ADM1"),
    _geonames_line("Bundesrepublik Deutschland", 52.5000, 13.4000, "A", "PCLI"),
]

# Eine Zeile AUSSERHALB `P`/`A` - sie traegt in keiner der beiden Fassungen etwas bei und gehoert
# deshalb in den Gleichheitsnachweis: ohne sie belegte er nur, dass gleiche Zeilen gleich wirken.
BERG_LINE = _geonames_line("Kreuzberg (Berg)", 52.4985, 13.4035, "T", "MT")


def _info_of_answer(answer: object) -> PlaceInfo:
    assert answer is not None
    return PlaceInfo(
        neighbourhood=answer.neighbourhood,  # type: ignore[attr-defined]
        locality=answer.locality,  # type: ignore[attr-defined]
        matched_level=answer.matched_level,  # type: ignore[attr-defined]
    )


def _without_comments(compose: str) -> str:
    """Eine Compose-Datei ohne ihre reinen Kommentarzeilen."""
    return "\n".join(line for line in compose.splitlines() if not line.lstrip().startswith("#"))


def _entries(lines: list[str]) -> list[object]:
    return [entry for line in lines if (entry := parse_geonames_line(line)) is not None]


class TestTheParserReadsTheLevelFromClassAndCode:
    """Die Ebene kommt aus `featureClass`/`featureCode`, NIE aus der Bevoelkerungszahl: viele
    `PPLX`-Eintraege (die Viertel-Ebene) tragen `population = 0`."""

    def test_a_populated_place_gives_the_locality_level(self) -> None:
        entry = parse_geonames_line(_geonames_line("Split", 43.5081, 16.4402, "P", "PPL"))
        assert entry is not None

        assert geonames_level(entry) == "locality"

    def test_a_section_of_a_populated_place_gives_the_district_level(self) -> None:
        entry = parse_geonames_line(_geonames_line("Kreuzberg", 52.4980, 13.4030, "P", "PPLX"))
        assert entry is not None

        assert geonames_level(entry) == "neighbourhood"

    @pytest.mark.parametrize("code", ["ADM1", "ADM2", "ADM3", "ADM4", "ADM5"])
    def test_an_administrative_division_carries_no_usable_level(self, code: str) -> None:
        """Klasse `A` ist genau der als wertlos eingestufte Fall: `region` traegt keinen Namen."""
        entry = parse_geonames_line(_geonames_line("Bayern", *GARMISCH, "A", code))
        assert entry is not None
        answer = geonames_answer([entry], GARMISCH)
        assert answer is not None

        assert geonames_level(entry) == "region"
        assert answer.matched_level == "region"
        assert usable_locality(_info_of_answer(answer)) is None

    def test_a_line_with_too_few_fields_is_skipped_not_crashing(self) -> None:
        assert parse_geonames_line("1\tBerlin\n") is None

    def test_a_line_with_an_unparsable_coordinate_is_skipped(self) -> None:
        broken = _geonames_line("Berlin", 0.0, 0.0, "P", "PPL").replace("\t0.0\t0.0\t", "\tN\tO\t")

        assert parse_geonames_line(broken) is None

    def test_a_name_that_does_not_survive_sanitisation_drops_the_whole_line(self) -> None:
        """Ein Ortsdatensatz ist ebenso von Dritten geschrieben wie eine Dienstantwort (S7)."""
        assert parse_geonames_line(_geonames_line("​‮", 52.52, 13.40, "P", "PPL")) is None

    def test_the_nearest_entry_per_level_wins(self) -> None:
        answer = geonames_answer(_entries(BERLIN_LINES), BERLIN_KREUZBERG)

        assert answer is not None
        assert answer.matched_level == "neighbourhood"
        assert answer.neighbourhood == "Kreuzberg"
        assert answer.locality == "Berlin"
        assert answer.country == "Bundesrepublik Deutschland"

    def test_no_nearby_entry_at_all_means_no_answer(self) -> None:
        """KEINE ANTWORT, ausdruecklich nicht "Antwort ohne brauchbare Ebene" - die beiden sind
        verschieden: die eine hinterlaesst keine Auskunft, die andere eine."""
        assert geonames_answer([], SPLIT) is None


class TestTheHitDistanceIsAZahlOhneNamen:
    """Spec 0506 Block C2 / Security S4. Die Entfernung zwischen Aufnahmeposition und dem Eintrag,
    der den Namen geliefert hat, wird bereits gerechnet und heute weggeworfen. Sie kommt auf einen
    EIGENEN Rueckgabeweg - nicht auf `PlaceAnswer` und damit nicht an den Schreibrand.

    GRUND: Die Entfernung zu einem benannten, oeffentlich enumerierbaren GeoNames-Eintrag ist ein
    Trilaterationsmittel - `locality` und `neighbourhood` derselben Zelle schneiden sich zu rund
    zwei Punkten und unterliefen die 1,1-km-Koernung, die `PLACE_CELL_DIGITS = 2` zusichert."""

    def test_the_distance_is_reported_per_level_without_any_name(self) -> None:
        distances = geonames_match_distances(_entries(BERLIN_LINES), BERLIN_KREUZBERG)

        assert set(distances) == {"neighbourhood", "locality", "region", "country"}
        for value in distances.values():
            assert isinstance(value, float)

    def test_it_measures_the_same_entry_the_answer_names(self) -> None:
        """Die beiden duerfen nicht auseinanderlaufen: Eine zweite Fassung der Nachbarschaftssuche
        maesse die Entfernung zu einem Eintrag, dessen Name gar nicht vergeben wurde."""
        far = _geonames_line("Beelin", 52.5800, 13.4050, "P", "PPL")
        entries = _entries([*BERLIN_LINES, far])

        answer = geonames_answer(entries, BERLIN_KREUZBERG)
        distances = geonames_match_distances(entries, BERLIN_KREUZBERG)
        assert answer is not None

        # "Berlin" liegt naeher als "Beelin" und gewinnt die Ebene; die gemeldete Entfernung ist
        # die des Gewinners, nicht die des letzten gelesenen Eintrags.
        assert answer.locality == "Berlin"
        assert distances["locality"] < haversine_meters(*BERLIN_KREUZBERG, 52.5800, 13.4050)

    def test_the_levels_of_both_forms_are_always_the_same_set(self) -> None:
        entries = _entries(BERLIN_LINES)
        answer = geonames_answer(entries, BERLIN_KREUZBERG)
        assert answer is not None

        named = {
            level
            for level, value in (
                ("neighbourhood", answer.neighbourhood),
                ("locality", answer.locality),
                ("region", answer.region),
                ("country", answer.country),
            )
            if value is not None
        }

        assert named == set(geonames_match_distances(entries, BERLIN_KREUZBERG))

    def test_an_entry_beyond_the_cap_is_absent_here_too(self) -> None:
        """Dieselbe Obergrenze wie bei der Antwort. Eine Entfernung ohne diese Kappung waere die
        Entfernung zum naechsten Eintrag IRGENDWO - und ihr Anteil oberhalb der Schwelle waere
        eine Aussage ueber die Kappung, nicht ueber die Ortszuordnung."""
        assert geonames_match_distances([], SPLIT) == {}

    def test_the_answer_itself_never_carries_a_distance(self) -> None:
        """S4, strukturell: `PlaceAnswer` ist ein geschlossener Stufenvorrat und bleibt es. Ein
        Feld hier waere der Weg an den `PlaceLookup`-Schreibrand in `worker.py`."""
        fields = {field.name for field in dataclasses.fields(PlaceAnswer)}

        assert fields == {"neighbourhood", "locality", "region", "country", "matched_level"}

    def test_no_column_of_the_place_lookup_holds_a_distance(self) -> None:
        """S4, zweite Haelfte: Sie wird nicht persistiert. Ohne diesen Waechter faellt eine
        spaetere Spalte niemandem auf."""
        columns = {column.name for column in PlaceLookup.__table__.columns}

        assert not {name for name in columns if "distance" in name or "entfernung" in name}


class TestTheExtractBehavesLikeTheRawFile:
    """DER GLEICHHEITSNACHWEIS. Der Auszug ist eine GeoNames-Datei mit geleerten ungebrauchten
    Spalten, kein eigenes Format - dieselben Zeilen, dieselben Felder, derselbe Parser."""

    def test_the_same_cell_gets_the_same_answer_from_both_versions(self) -> None:
        raw = [*BERLIN_LINES, BERG_LINE]
        extracted = [line for line in (extract_line(line) for line in raw) if line is not None]

        assert geonames_answer(_entries(raw), BERLIN_KREUZBERG) == geonames_answer(
            _entries(extracted), BERLIN_KREUZBERG
        )

    def test_a_line_outside_p_and_a_is_dropped_from_the_extract(self) -> None:
        """Sie traegt in beiden Fassungen nichts bei - und ohne diesen Fall belegte der
        Gleichheitsnachweis nur, dass gleiche Zeilen gleich wirken."""
        assert extract_line(BERG_LINE) is None

    def test_the_kept_fields_stay_at_their_original_column_positions(self) -> None:
        line = extract_line(BERLIN_LINES[1])
        assert line is not None
        raw_fields = BERLIN_LINES[1].split("\t")
        fields = line.split("\t")

        assert len(fields) == len(raw_fields)
        for index in (1, 4, 5, 6, 7):
            assert fields[index] == raw_fields[index], index

    def test_every_unused_column_is_emptied(self) -> None:
        """Datensparsamkeit, KEINE Injektionsabwehr (S9): gegen Injektion tragen Sanitisierung und
        Laengengrenze."""
        line = extract_line(BERLIN_LINES[0])
        assert line is not None
        fields = line.split("\t")

        assert [index for index, value in enumerate(fields) if value] == [1, 4, 5, 6, 7]

    def test_the_written_extract_is_gzip_packed_and_carries_only_kept_lines(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "auszug.txt.gz"

        kept = write_extract([*BERLIN_LINES, BERG_LINE], target)

        assert kept == len(BERLIN_LINES)
        with gzip.open(target, "rt", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        assert len(lines) == len(BERLIN_LINES)
        assert all("Kreuzberg (Berg)" not in line for line in lines)

    def test_the_hash_is_written_next_to_the_extract(self, tmp_path: Path) -> None:
        """Geprueft wird der AUSZUG selbst, also genau die Datei, die gelesen wird."""
        target = tmp_path / "auszug.txt.gz"

        write_extract(BERLIN_LINES, target)

        assert dataset_hash_path(target).read_text(encoding="utf-8").strip() == sha256_of(target)


class TestTheResolverReadsTheExtract:
    async def test_it_answers_from_a_gzip_packed_extract(self, tmp_path: Path) -> None:
        target = tmp_path / "auszug.txt.gz"
        write_extract(BERLIN_LINES, target)

        resolver = GeoNamesResolver(target, [BERLIN_KREUZBERG])
        answer = await resolver.resolve(BERLIN_KREUZBERG)

        assert answer is not None
        assert (answer.locality, answer.neighbourhood) == ("Berlin", "Kreuzberg")

    async def test_it_reads_an_unpacked_file_too(self, tmp_path: Path) -> None:
        """Die gepackte Form ist die abgelegte; eine entpackte Datei daneben bleibt lesbar, damit
        der Auszug zur Untersuchung nicht erst umkopiert werden muss."""
        plain = tmp_path / "auszug.txt"
        plain.write_text("\n".join(BERLIN_LINES) + "\n", encoding="utf-8")

        resolver = GeoNamesResolver(plain, [BERLIN_KREUZBERG])

        answer = await resolver.resolve(BERLIN_KREUZBERG)
        assert answer is not None
        assert answer.locality == "Berlin"

    async def test_a_cell_nobody_asked_for_gets_no_answer(self, tmp_path: Path) -> None:
        """Der Auflöser behaelt nur die Nachbarschaft der GEFRAGTEN Zellen - er erzeugt keine."""
        target = tmp_path / "auszug.txt.gz"
        write_extract(BERLIN_LINES, target)

        resolver = GeoNamesResolver(target, [BERLIN_KREUZBERG])

        assert await resolver.resolve(SPLIT) is None

    def test_a_missing_file_breaks_loudly(self, tmp_path: Path) -> None:
        with pytest.raises(PlaceDatasetError):
            GeoNamesResolver(tmp_path / "gibt-es-nicht.txt.gz", [SPLIT])


class TestTheFactoryChecksTheExtractBeforeEveryUse:
    """Fehlt der Auszug oder weicht er von seinem Hash ab, wird KEIN Auflöser gebaut (Muster
    `build_landmark_client` ohne Einwilligung): kein stiller Ersatzweg, eine laute Zeile mit
    festem Grund-Token. Der Lauf laeuft durch, die Events behalten Nummer und Zeitspanne."""

    def _prepared(self, tmp_path: Path) -> Path:
        target = tmp_path / "auszug.txt.gz"
        write_extract(BERLIN_LINES, target)
        return target

    async def test_a_matching_hash_yields_a_working_resolver(self, tmp_path: Path) -> None:
        resolver = build_place_resolver([BERLIN_KREUZBERG], path=self._prepared(tmp_path))

        assert resolver is not None
        answer = await resolver.resolve(BERLIN_KREUZBERG)
        assert answer is not None
        assert answer.locality == "Berlin"

    def test_a_missing_file_yields_no_resolver_and_a_loud_line(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR, logger="photosort.geonames"):
            resolver = build_place_resolver([SPLIT], path=tmp_path / "fehlt.txt.gz")

        assert resolver is None
        assert any(DATASET_REASON_MISSING in record.getMessage() for record in caplog.records)

    def test_a_missing_hash_file_yields_no_resolver(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ein Auszug ohne seinen Hash ist nicht pruefbar - und "nicht pruefbar" ist hier
        dasselbe wie "nicht verwendbar"."""
        target = self._prepared(tmp_path)
        dataset_hash_path(target).unlink()

        with caplog.at_level(logging.ERROR, logger="photosort.geonames"):
            resolver = build_place_resolver([BERLIN_KREUZBERG], path=target)

        assert resolver is None
        assert any(DATASET_REASON_HASH_MISSING in record.getMessage() for record in caplog.records)

    def test_a_changed_extract_yields_no_resolver(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Eine Beschaedigung NACH dem Bezug faellt an der Datei auf, die tatsaechlich gelesen
        wird - das ist genau die Luecke, die der Bezug in Teil 1 offen liess."""
        target = self._prepared(tmp_path)
        write_extract([_geonames_line("Anderswo", 52.50, 13.40, "P", "PPL")], target)
        dataset_hash_path(target).write_text("0" * 64 + "\n", encoding="utf-8")

        with caplog.at_level(logging.ERROR, logger="photosort.geonames"):
            resolver = build_place_resolver([BERLIN_KREUZBERG], path=target)

        assert resolver is None
        assert any(DATASET_REASON_HASH_MISMATCH in record.getMessage() for record in caplog.records)

    def test_no_log_line_carries_a_coordinate_or_a_place_name(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """S11: Koordinaten und Ortsnamen gehoeren in kein Log - geprueft ueber die fertige
        Meldung UND ueber die Argumente, sonst rutscht ein `%s`-Argument durch."""
        target = self._prepared(tmp_path)
        dataset_hash_path(target).write_text("0" * 64 + "\n", encoding="utf-8")

        with caplog.at_level(logging.DEBUG, logger="photosort.geonames"):
            build_place_resolver([BERLIN_KREUZBERG], path=target)

        for record in caplog.records:
            rendered = record.getMessage() + repr(record.args)
            assert "52.5" not in rendered
            assert "13.4" not in rendered
            assert "Berlin" not in rendered


class TestTheFetchCommandStaysAwayFromEveryAutomaticPath:
    """Dieselbe Auflage und derselbe Nachweis wie bei `place_probe`: ein 400-MB-Abruf tritt nur
    ein, wenn er getippt wird. Kein Teil traegt allein."""

    def test_the_command_is_in_no_import_graph_of_the_application(self) -> None:
        assert "photosort.place_dataset" not in import_closure("photosort.main")
        assert "photosort.place_dataset" not in import_closure("photosort.worker")

    def test_the_import_graph_walker_actually_finds_something(self) -> None:
        """Gegenprobe: ohne sie bestuenden die beiden Zusagen oben auch bei einem Walker, der gar
        nichts findet. Der LESENDE Teil ist ausdruecklich erreichbar - er ist der Produktivpfad."""
        assert {"photosort.models", "photosort.config"} <= import_closure("photosort.main")
        assert "photosort.geonames" in import_closure("photosort.worker")
        assert "photosort.geonames" in import_closure("photosort.place_dataset")

    def test_no_compose_file_runs_the_command(self) -> None:
        """Gesucht wird der MODULPFAD, unter dem das Kommando aufgerufen wuerde - der blosse Name
        `place_dataset` steht dort als Volume und traegt nichts aus. Ein `command:` oder ein
        `entrypoint:` auf dieses Modul enthielte den Modulpfad zwangslaeufig.

        KOMMENTARZEILEN ZAEHLEN NICHT: Der Volume-Eintrag nennt den getippten Aufruf erklaerend,
        und ein Wortverbot verboete genau diese Erklaerung. Dass die Trennung die echte Form noch
        faengt, steht als eigener Fall darunter."""
        for compose in sorted(REPO_ROOT.glob("docker-compose*.yml")):
            assert "photosort.place_dataset" not in _without_comments(
                compose.read_text(encoding="utf-8")
            ), compose.name

    def test_the_comment_stripping_still_sees_a_real_command(self) -> None:
        """Gegenprobe zur Zeile darueber: ohne sie bestuende der Waechter auch dann, wenn das
        Ausklammern der Kommentare versehentlich die ganze Datei verschluckte."""
        compose = (
            "services:\n"
            "  worker:\n"
            "    # docker compose exec backend python -m photosort.place_dataset\n"
            '    command: ["python", "-m", "photosort.place_dataset"]\n'
        )

        assert "photosort.place_dataset" in _without_comments(compose)

    def test_the_module_defines_no_endpoint(self) -> None:
        path = module_file("photosort.place_dataset")
        assert path is not None
        source = path.read_text(encoding="utf-8")

        assert "APIRouter" not in source
        assert "fastapi" not in source

    def test_the_source_address_is_a_constant_not_a_value_from_anywhere(self) -> None:
        """Kein SSRF-Pfad: die Quell-Adresse ist eine Konstante, nie ein Wert aus Datenbank,
        Request oder Parameter (S9)."""
        path = module_file("photosort.place_dataset")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assignments = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "GEONAMES_ARCHIVE_URL"
                for target in node.targets
            )
        ]

        assert len(assignments) == 1
        assert isinstance(assignments[0].value, ast.Constant)
        assert GEONAMES_ARCHIVE_URL.startswith("https://")
