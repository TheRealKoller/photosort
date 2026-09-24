"""Der Sehenswürdigkeits-Auszug: Faltung, Parser, Namensverzeichnis und die Prüfung vor Gebrauch.

Grundlage: ADR 0123, Spec 0529 Abschnitte 1 bis 3 und die Sicherheitsauflagen S5 bis S7.

KEIN Test bezieht die echte Datei - die Rohzeilen stehen literal, das Verzeichnis liest eine
Mini-Auszugsdatei aus `tmp_path`. Die beiden tragenden Nachweise: die Faltung ist diesseits und
jenseits dieselbe (zwei Fassungen liefen auseinander und die Suche schlüge still fehl), und die
drei Zustände der Auskunft fallen nicht zusammen.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from photosort.geonames import (
    DATASET_REASON_HASH_MISMATCH,
    DATASET_REASON_HASH_MISSING,
    DATASET_REASON_MISSING,
    GEONAMES_MAX_DISTANCE_METERS,
    LANDMARK_DATASET_REASON_HASH_MISMATCH,
    LANDMARK_DATASET_REASON_HASH_MISSING,
    LANDMARK_DATASET_REASON_MISSING,
    LANDMARK_PLAUSIBILITY_RADIUS_METERS,
    LandmarkGazetteer,
    PlaceDatasetError,
    build_landmark_gazetteer,
    dataset_hash_path,
    fold_landmark_name,
    landmark_dataset_path,
    parse_geonames_line,
    parse_landmark_line,
    sha256_of,
)

SPLIT = (43.51, 16.44)
BERLIN_KREUZBERG = (52.50, 13.40)


def _raw_line(
    name: str,
    lat: float | str,
    lon: float | str,
    feature_class: str,
    feature_code: str,
    alternates: str = "",
) -> str:
    """Eine Rohzeile im echten Format (geonamesid, name, asciiname, alternatenames, lat, lon,
    featureClass, featureCode, ...) - ungebrauchte Felder tragen Inhalt wie in der Rohdatei."""
    return "\t".join(
        [
            "2950159",
            name,
            name,
            alternates,
            str(lat),
            str(lon),
            feature_class,
            feature_code,
        ]
    )


def _landmark_line(name: str, lat: float | str, lon: float | str, alternates: str = "") -> str:
    return _raw_line(name, lat, lon, "S", "CH", alternates)


class TestTheFoldingIsOneFunction:
    """S5(d): Kleinschreibung, getrennte Diakritika, Trennzeichen zu Leerzeichen - eine Funktion,
    diesseits und jenseits dieselbe. Sie darf nur angleichen, nie Zeichen ersatzlos entfernen."""

    @pytest.mark.parametrize(
        ("raw", "folded"),
        [
            ("Brandenburger Tor", "brandenburger tor"),
            ("Kölner Dom", "kolner dom"),
            ("Karlsbrücke", "karlsbrucke"),
            ("Trevi-Brunnen", "trevi brunnen"),
            ("  Eiffelturm  ", "eiffelturm"),
        ],
    )
    def test_case_diacritics_and_separators_are_equalised(self, raw: str, folded: str) -> None:
        assert fold_landmark_name(raw) == folded

    def test_folding_twice_changes_nothing(self) -> None:
        assert fold_landmark_name(fold_landmark_name("Kölner Dom")) == fold_landmark_name(
            "Kölner Dom"
        )

    def test_two_different_landmarks_do_not_collapse(self) -> None:
        """Eine zu aggressive Faltung zöge verschiedene Sehenswürdigkeiten zusammen und
        BESTÄTIGTE dann einen falschen Namen."""
        assert fold_landmark_name("Ben Nevis") != fold_landmark_name("Ben Nevis Range")

    def test_the_comma_is_not_a_separator(self) -> None:
        """S5(c): Sonst verschmölzen alle Alternativnamen einer Zeile zu einem Riesenschlüssel -
        zerlegt wird vorher, und dieses Zeichen bleibt dabei außen vor."""
        assert fold_landmark_name("A,B") != fold_landmark_name("A B")
        assert "," in fold_landmark_name("A,B")

    def test_a_separator_becomes_a_space_and_is_never_dropped(self) -> None:
        """„Nie Zeichen ersatzlos entfernen": aus `A/B` wird `A B`, nicht `AB`."""
        assert fold_landmark_name("A/B") == "a b"

    def test_the_radius_is_its_own_constant(self) -> None:
        """ADR 0123 Punkt 5: Dort geht es darum, ab wann eine Entfernung eine Verwechslung
        beweist; `GEONAMES_MAX_DISTANCE_METERS` darum, ab wann ein Ortsname keiner mehr ist."""
        assert isinstance(LANDMARK_PLAUSIBILITY_RADIUS_METERS, float)
        assert LANDMARK_PLAUSIBILITY_RADIUS_METERS > GEONAMES_MAX_DISTANCE_METERS


class TestTheLandmarkParser:
    """S5 und S6: jeder Name läuft einzeln durch `sanitize_landmark_name`, die Faltung läuft
    danach, und die Koordinaten werden am Parser-Rand auf ihr Band geprüft."""

    def test_it_reads_name_and_coordinates(self) -> None:
        entry = parse_landmark_line(_landmark_line("Eiffelturm", 48.8584, 2.2945))

        assert entry is not None
        assert entry.folded_names == ("eiffelturm",)
        assert (entry.lat, entry.lon) == (48.8584, 2.2945)

    def test_the_alternates_are_split_at_the_comma(self) -> None:
        """S5(c): `alternatenames` wird VOR der Faltung am Komma zerlegt."""
        entry = parse_landmark_line(
            _landmark_line("Tour Eiffel", 48.8584, 2.2945, alternates="Eiffelturm,Eiffel Tower")
        )

        assert entry is not None
        assert entry.folded_names == ("tour eiffel", "eiffelturm", "eiffel tower")

    def test_an_alternate_that_fails_sanitisation_drops_only_itself(self) -> None:
        """S5(a): Ein Element, das die Sanitisierung nicht übersteht, fällt für sich weg - nie
        die ganze Zeile."""
        entry = parse_landmark_line(
            _landmark_line("Eiffelturm", 48.8584, 2.2945, alternates="\u200b\u202e,Eiffel Tower")
        )

        assert entry is not None
        assert entry.folded_names == ("eiffelturm", "eiffel tower")

    def test_a_line_without_any_usable_name_is_dropped(self) -> None:
        assert parse_landmark_line(_landmark_line("\u200b", 48.8584, 2.2945)) is None

    @pytest.mark.parametrize(
        ("lat", "lon"),
        [(91.0, 2.2945), (-91.0, 2.2945), (48.8584, 181.0), (48.8584, -181.0), ("nan", 2.2945)],
    )
    def test_coordinates_outside_the_band_drop_the_line(
        self, lat: float | str, lon: float | str
    ) -> None:
        """S6: Bereichsvergleich, nie Klemmen - ein geklemmter Wert stünde als Fundort in der
        JSON-Spalte."""
        assert parse_landmark_line(_landmark_line("Eiffelturm", lat, lon)) is None

    @pytest.mark.parametrize(
        ("lat", "lon"),
        [(91.0, 2.2945), (-91.0, 2.2945), (48.8584, 181.0), (48.8584, -181.0), ("nan", 2.2945)],
    )
    def test_the_band_check_lives_at_one_place_for_both_extracts(
        self, lat: float | str, lon: float | str
    ) -> None:
        """S6: Die Prüfung steht an EINER Stelle im Parser und wirkt für beide Auszüge."""
        assert parse_geonames_line(_raw_line("Eiffelturm", lat, lon, "P", "PPL")) is None


class TestTheGazetteer:
    """S7: Namensgeschlüsselt, mit den gesuchten Namen im Konstruktor, ein Durchgang durch den
    zweiten Auszug."""

    def _prepared(self, tmp_path: Path, lines: list[str]) -> Path:
        target = tmp_path / "sehenswuerdigkeiten.txt"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

    def test_a_name_in_the_name_field_is_found(self, tmp_path: Path) -> None:
        path = self._prepared(tmp_path, [_landmark_line("Eiffelturm", 48.8584, 2.2945)])

        gazetteer = LandmarkGazetteer(path, [fold_landmark_name("Eiffelturm")])

        assert gazetteer.points(fold_landmark_name("Eiffelturm")) == ((48.8584, 2.2945),)

    def test_a_name_only_reachable_over_an_alternate_is_found(self, tmp_path: Path) -> None:
        """33 von 50 gemessenen Namen waren nur über `alternatenames` auffindbar (ADR 0123)."""
        path = self._prepared(
            tmp_path,
            [_landmark_line("Tour Eiffel", 48.8584, 2.2945, alternates="Eiffelturm")],
        )

        gazetteer = LandmarkGazetteer(path, [fold_landmark_name("Eiffelturm")])

        assert gazetteer.points(fold_landmark_name("Eiffelturm")) == ((48.8584, 2.2945),)

    def test_several_findspots_of_one_name_are_all_kept(self, tmp_path: Path) -> None:
        """Homonyme sind häufig (ADR 0123): geprüft wird Name UND Umkreis."""
        path = self._prepared(
            tmp_path,
            [
                _landmark_line("Eiffelturm", 48.8584, 2.2945),
                _landmark_line("Eiffelturm", 43.51, 16.44),
            ],
        )

        gazetteer = LandmarkGazetteer(path, [fold_landmark_name("Eiffelturm")])

        assert gazetteer.points(fold_landmark_name("Eiffelturm")) == (
            (48.8584, 2.2945),
            (43.51, 16.44),
        )

    def test_an_unknown_name_is_a_key_with_an_empty_point_set(self, tmp_path: Path) -> None:
        """Zustand (2): nachgeschlagen, ohne Fund - die leere Punktmenge ist kein fehlender
        Eintrag."""
        path = self._prepared(tmp_path, [_landmark_line("Eiffelturm", 48.8584, 2.2945)])

        gazetteer = LandmarkGazetteer(path, [fold_landmark_name("Stonehenge")])

        assert gazetteer.points(fold_landmark_name("Stonehenge")) == ()

    def test_only_the_asked_names_are_kept(self, tmp_path: Path) -> None:
        """S7: Ein Gazetteer, der den vollen Auszug hält, erschöpft den Worker-Prozess."""
        path = self._prepared(
            tmp_path,
            [
                _landmark_line("Eiffelturm", 48.8584, 2.2945),
                _landmark_line("Stonehenge", 51.1789, -1.8262),
            ],
        )

        gazetteer = LandmarkGazetteer(path, [fold_landmark_name("Eiffelturm")])

        assert gazetteer.points(fold_landmark_name("Stonehenge")) == ()

    def test_an_empty_candidate_set_does_not_read_the_file(self, tmp_path: Path) -> None:
        """S7: Der Durchgang läuft nur, wenn es offene Namen gibt."""
        missing = tmp_path / "gibt-es-nicht.txt"

        gazetteer = LandmarkGazetteer(missing, [])

        assert gazetteer.points("eiffelturm") == ()

    def test_a_missing_file_breaks_loudly(self, tmp_path: Path) -> None:
        with pytest.raises(PlaceDatasetError):
            LandmarkGazetteer(tmp_path / "gibt-es-nicht.txt", ["eiffelturm"])


class TestTheFactoryChecksTheSecondExtractBeforeEveryUse:
    """S3 und S4: eigener Bauweg samt eigener Prüfung, eigene Grund-Token, fail-open - ein
    fehlender Sehenswürdigkeits-Auszug verwirft keinen Namen."""

    def _prepared(self, tmp_path: Path) -> Path:
        target = tmp_path / "sehenswuerdigkeiten.txt"
        target.write_text(_landmark_line("Eiffelturm", 48.8584, 2.2945) + "\n", encoding="utf-8")
        dataset_hash_path(target).write_text(sha256_of(target) + "\n", encoding="utf-8")
        return target

    def test_a_matching_hash_yields_a_working_gazetteer(self, tmp_path: Path) -> None:
        gazetteer = build_landmark_gazetteer(["eiffelturm"], path=self._prepared(tmp_path))

        assert gazetteer is not None
        assert gazetteer.points("eiffelturm") == ((48.8584, 2.2945),)

    def test_no_open_name_means_no_gazetteer_at_all(self, tmp_path: Path) -> None:
        target = self._prepared(tmp_path)

        assert build_landmark_gazetteer([], path=target) is None

    def test_a_missing_file_yields_no_gazetteer_and_a_loud_line(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR, logger="photosort.geonames"):
            gazetteer = build_landmark_gazetteer(["eiffelturm"], path=tmp_path / "fehlt.txt")

        assert gazetteer is None
        assert any(
            LANDMARK_DATASET_REASON_MISSING in record.getMessage() for record in caplog.records
        )

    def test_a_missing_hash_file_yields_no_gazetteer(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        target = self._prepared(tmp_path)
        dataset_hash_path(target).unlink()

        with caplog.at_level(logging.ERROR, logger="photosort.geonames"):
            gazetteer = build_landmark_gazetteer(["eiffelturm"], path=target)

        assert gazetteer is None
        assert any(
            LANDMARK_DATASET_REASON_HASH_MISSING in record.getMessage() for record in caplog.records
        )

    def test_a_changed_extract_yields_no_gazetteer(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        target = self._prepared(tmp_path)
        dataset_hash_path(target).write_text("0" * 64 + "\n", encoding="utf-8")

        with caplog.at_level(logging.ERROR, logger="photosort.geonames"):
            gazetteer = build_landmark_gazetteer(["eiffelturm"], path=target)

        assert gazetteer is None
        assert any(
            LANDMARK_DATASET_REASON_HASH_MISMATCH in record.getMessage()
            for record in caplog.records
        )

    def test_the_two_extracts_have_their_own_reason_tokens(self) -> None:
        """S3: Sonst wäre „der Sehenswürdigkeitsauszug fehlt" von „der Ortsauszug fehlt" nicht zu
        unterscheiden - und daran hängt die fail-open-Ausfallrichtung."""
        own = {
            LANDMARK_DATASET_REASON_MISSING,
            LANDMARK_DATASET_REASON_HASH_MISSING,
            LANDMARK_DATASET_REASON_HASH_MISMATCH,
        }
        place = {DATASET_REASON_MISSING, DATASET_REASON_HASH_MISSING, DATASET_REASON_HASH_MISMATCH}

        assert not own & place

    def test_no_log_line_carries_a_name_or_a_coordinate(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """S10: weder ein Name noch eine Koordinate gehört in eine Logzeile - geprüft über die
        fertige Meldung UND über die Argumente."""
        target = self._prepared(tmp_path)
        dataset_hash_path(target).write_text("0" * 64 + "\n", encoding="utf-8")

        with caplog.at_level(logging.DEBUG, logger="photosort.geonames"):
            build_landmark_gazetteer(["eiffelturm"], path=target)

        for record in caplog.records:
            rendered = record.getMessage() + repr(record.args)
            assert "Eiffelturm" not in rendered
            assert "48.85" not in rendered
            assert "2.29" not in rendered


class TestTheSecondPathIsDerivedNotConfigured:
    """Spec 0529: keine neue Betriebseinstellung, sondern eine abgeleitete Funktion - Muster
    `dataset_hash_path`."""

    def test_it_is_a_sibling_of_the_place_extract(self) -> None:
        place = Path("/data/place-dataset/geonames-auszug.txt.gz")

        derived = landmark_dataset_path(place)

        assert derived.parent == place.parent
        assert derived != place

    def test_it_is_a_pure_function_of_its_argument(self) -> None:
        assert landmark_dataset_path(Path("/a/b.txt.gz")) == landmark_dataset_path(
            Path("/a/b.txt.gz")
        )
