"""Tests fuer die reine, DB-freie Ortsauskunft (specs/features/0434-ortsnamen-fuer-events.md,
decisions/0102-ortsauskunft-je-zelle-projektgebunden-eventname-als-laufartefakt.md).

Ohne DB, ohne Netz, ohne Auflöser: `places.py` beantwortet ausschliesslich "was liegt an dieser
Zelle" und kennt die unspezifische Stufe. Die Gleichnamigkeitspruefung ueber einen Lauf und die
zusammengesetzte Form "Ort, Viertel" liegen in `events.py` (ADR 0102 Punkt 4) und sind von hier
aus strukturell nicht erreichbar.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError

import pytest

from photosort.landmark import MAX_LANDMARK_NAME_LENGTH, sanitize_landmark_name
from photosort.places import (
    MAX_PLACE_NAME_LENGTH,
    NAME_BEARING_LEVELS,
    PLACE_CELL_DIGITS,
    PLACE_LEVELS,
    PlaceAnswer,
    PlaceInfo,
    place_cell,
    sanitize_place_name,
    usable_locality,
)
from photosort.scoring import haversine_meters
from tests.import_closure import import_closure, imported_root_packages, module_file


class TestTheCellIsTheOneRounding:
    """`place_cell` ist die EINE Rundung des Projekts - `events.py::_rounded` ist darin
    aufgegangen. Die Koernung traegt eine Datenschutzentscheidung (Spec 0434, S3)."""

    def test_the_digit_count_is_pinned_as_a_literal(self) -> None:
        """Als Literal und nicht abgeleitet: zwei Nachkommastellen sind rund 1,1 km. Drei traefen
        Wohnadress-Aufloesung, eine machte die Viertel-Regel strukturell unerfuellbar. Eine
        Aenderung dieses Werts ist eine Datenschutzaenderung, kein Refactoring."""
        assert PLACE_CELL_DIGITS == 2

    def test_two_points_forty_metres_apart_share_a_cell(self) -> None:
        # Rund 40 m in Nord-Sued-Richtung - die Streuung eines einzelnen Ortsbesuchs.
        near = (48.1372, 11.5756)
        also_near = (48.13756, 11.5756)
        assert haversine_meters(*near, *also_near) < 50.0

        assert place_cell(*near) == place_cell(*also_near)

    def test_two_points_across_the_cell_boundary_differ(self) -> None:
        assert place_cell(48.1372, 11.5756) != place_cell(48.1472, 11.5756)

    def test_negative_zero_is_normalised_for_the_latitude(self) -> None:
        """`-0.0` waere im JSON `-0.0` und in der Anzeige `"-0.00"` - eine Himmelsrichtung, die
        es nicht gibt. Breite und Laenge werden GETRENNT geprueft: ein Normalisieren nur einer
        von beiden faellt sonst nicht auf."""
        lat, _ = place_cell(-0.001, 11.5756)

        assert lat == 0.0
        assert str(lat) == "0.0"

    def test_negative_zero_is_normalised_for_the_longitude(self) -> None:
        _, lon = place_cell(48.1372, -0.001)

        assert lon == 0.0
        assert str(lon) == "0.0"

    def test_a_value_on_the_rounding_boundary_is_deterministic(self) -> None:
        """Auf der Rundungsgrenze entscheidet Pythons Bankiers-Rundung. Der Fall steht hier, weil
        die Zelle ein SCHLUESSEL ist: welche Seite gewinnt, ist gleichgueltig - dass immer
        dieselbe gewinnt, ist es nicht."""
        assert place_cell(48.125, 11.125) == place_cell(48.125, 11.125)
        assert place_cell(48.125, 11.125) == (round(48.125, 2) + 0.0, round(11.125, 2) + 0.0)


class TestPlaceNameSanitisation:
    """Im Schnitt der acht Faelle von test_landmark.py::TestLandmarkNameSanitisation - ein
    Ortsdatensatz ist ebenso von Dritten geschrieben wie eine Dienstantwort (Spec 0434, S7)."""

    def test_a_non_string_is_no_name(self) -> None:
        assert sanitize_place_name(42) is None
        assert sanitize_place_name(None) is None

    def test_an_empty_string_is_no_name(self) -> None:
        assert sanitize_place_name("") is None

    def test_blanks_only_are_no_name(self) -> None:
        assert sanitize_place_name("   ") is None

    def test_a_null_byte_is_stripped(self) -> None:
        assert sanitize_place_name("Split\x00") == "Split"

    def test_a_zero_width_character_is_stripped(self) -> None:
        assert sanitize_place_name("Spl​it") == "Split"

    def test_a_bidi_override_is_stripped(self) -> None:
        assert sanitize_place_name("Spl‮it") == "Split"

    def test_a_line_break_between_two_words_becomes_a_blank(self) -> None:
        # Ersatzlos entfernt verschmoelzen die beiden Woerter zu einem.
        assert sanitize_place_name("Garmisch\nPartenkirchen") == "Garmisch Partenkirchen"

    def test_a_name_exactly_at_the_length_limit_is_kept(self) -> None:
        exactly = "A" * MAX_PLACE_NAME_LENGTH

        assert sanitize_place_name(exactly) == exactly

    def test_one_character_more_is_discarded_never_truncated(self) -> None:
        """VERWERFEN, nie Abschneiden - hier Korrektheit, nicht Hygiene: `assign_place_names`
        VERGLEICHT Ortsnamen ueber die Events eines Laufs. Zwei verschiedene, auf dieselbe Laenge
        gekappte Namen waeren ein Name, und die Viertel-Regel griffe fuer Events an
        verschiedenen Orten."""
        too_long = "A" * (MAX_PLACE_NAME_LENGTH + 1)

        assert sanitize_place_name(too_long) is None

    def test_an_ordinary_name_passes_through_unchanged(self) -> None:
        assert sanitize_place_name("Garmisch-Partenkirchen") == "Garmisch-Partenkirchen"


_SHARED_SANITISATION_CASES = [
    42,
    None,
    "",
    "   ",
    "Split\x00",
    "Spl​it",
    "Spl‮it",
    "Garmisch\nPartenkirchen",
    "  Santiago   de  Compostela ",
    "A" * 80,
    "A" * 81,
    "Garmisch-Partenkirchen",
]


class TestBothSanitisersAreTheSameFunction:
    """Die Auflage lautet DIESELBE Funktion, nicht eine zweite Fassung davon (Spec 0434, S7).
    Beide Grenzen liegen bei 80, beide Wege durchlaufen `cloud_vision.py::_sanitize_label_text`."""

    def test_the_two_length_limits_agree(self) -> None:
        assert MAX_PLACE_NAME_LENGTH == MAX_LANDMARK_NAME_LENGTH

    @pytest.mark.parametrize("raw", _SHARED_SANITISATION_CASES)
    def test_both_sanitisers_agree_on_every_case(self, raw: object) -> None:
        """Bricht, sobald jemand eine zweite Sanitisierungsfassung einfuehrt."""
        assert sanitize_place_name(raw) == sanitize_landmark_name(raw)


def _info(
    *, matched_level: str | None, locality: str | None, neighbourhood: str | None = None
) -> PlaceInfo:
    return PlaceInfo(neighbourhood=neighbourhood, locality=locality, matched_level=matched_level)


class TestUsableLocality:
    """Die Stufenpruefung an EINER Stelle: ein Name gilt als aufgeloest, wenn
    `matched_level in {"neighbourhood", "locality"}` UND `locality` gesetzt ist (ADR 0102
    Punkt 3)."""

    def test_the_level_vocabulary_is_pinned_in_length_and_order(self) -> None:
        """Als Literal: sonst liefe eine fuenfte Ebene ungeprueft durch die Matrix unten."""
        assert PLACE_LEVELS == ("neighbourhood", "locality", "region", "country")

    def test_the_name_bearing_levels_are_the_two_finest_ones(self) -> None:
        """Abgeleitet und nicht ein zweites Mal ausgeschrieben - hier als Literal festgehalten,
        damit eine Umordnung von `PLACE_LEVELS` nicht still die Stufenpruefung verschiebt."""
        assert NAME_BEARING_LEVELS == ("neighbourhood", "locality")

    @pytest.mark.parametrize("level", PLACE_LEVELS)
    @pytest.mark.parametrize("locality", ["Split", None])
    def test_the_matrix_over_levels_and_locality(self, level: str, locality: str | None) -> None:
        resolved = usable_locality(_info(matched_level=level, locality=locality))

        if level in ("neighbourhood", "locality") and locality is not None:
            assert resolved == locality
        else:
            assert resolved is None

    @pytest.mark.parametrize("level", ["region", "country"])
    def test_a_region_level_hit_with_a_locality_set_is_no_name(self, level: str) -> None:
        """DIE ANBIETERANGABE GEWINNT, nicht die gefuellte Spalte: eine Antwort auf Regionsebene
        nennt oft trotzdem eine Stadt, und die liegt dann womoeglich Dutzende Kilometer
        entfernt."""
        assert usable_locality(_info(matched_level=level, locality="Split")) is None

    def test_a_level_outside_the_vocabulary_is_no_name_not_an_exception(self) -> None:
        """Mitgliedschaftspruefung statt Cast (Muster `place_kind`) - nie eine 500."""
        assert usable_locality(_info(matched_level="bezirk", locality="Split")) is None

    def test_an_absent_level_is_no_name(self) -> None:
        assert usable_locality(_info(matched_level=None, locality="Split")) is None

    def test_no_info_at_all_is_no_name(self) -> None:
        assert usable_locality(None) is None


class TestTheModuleBoundaryFromAdr0102:
    """ADR 0102 Punkt 4: `places.py` ist rein und DB-frei, und die zusammengesetzte Form
    "Ort, Viertel" entsteht ausschliesslich in `events.py`. Story #469 fragt vor der
    Event-Bildung und kann "Berlin, Kreuzberg" strukturell nicht erreichen."""

    def test_the_module_imports_neither_sqlalchemy_nor_the_models(self) -> None:
        assert "photosort.models" not in import_closure("photosort.places")
        assert "sqlalchemy" not in imported_root_packages("photosort.places")

    def test_the_import_graph_walker_actually_finds_something(self) -> None:
        # Gegenprobe: ohne sie bestuende der Fall oben auch dann, wenn der Walker nichts findet.
        assert "photosort.cloud_vision" in import_closure("photosort.places")
        assert "photosort" in imported_root_packages("photosort.places")

    def test_no_string_literal_in_the_module_composes_a_place_and_a_district(self) -> None:
        """Die Modulgrenze ist die Zusage. Gesucht wird die Zusammensetzung selbst - ein
        Trennzeichen-Literal, aus dem "Ort, Viertel" entstuende, und jede Formatzeichenkette mit
        zwei Platzhaltern."""
        path = module_file("photosort.places")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))

        composing: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                if sum(isinstance(part, ast.FormattedValue) for part in node.values) >= 2:
                    composing.append(ast.unparse(node))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in (", ", "{}, {}", "%s, %s"):
                    composing.append(node.value)

        assert composing == []


class TestTheAnswerStandsInStages:
    """Vier benannte Stufen, kein zusammengesetzter Anzeigename und kein offener Beutel fuer
    alles, was eine Antwort sonst noch traegt (ADR 0102 Punkt 3). Strasse und Hausnummer werden
    am Parser-Rand verworfen und erreichen kein Feld."""

    def test_the_answer_carries_exactly_the_four_stages_and_the_level(self) -> None:
        assert [field for field in PlaceAnswer.__dataclass_fields__] == [
            *PLACE_LEVELS,
            "matched_level",
        ]

    def test_the_info_carries_only_what_a_name_needs(self) -> None:
        """`PlaceInfo` ist die LESESICHT: Region und Land tragen zu keinem Namen bei und stehen
        deshalb nicht darin."""
        assert [field for field in PlaceInfo.__dataclass_fields__] == [
            "neighbourhood",
            "locality",
            "matched_level",
        ]

    @pytest.mark.parametrize("cls", [PlaceAnswer, PlaceInfo])
    def test_both_are_frozen(self, cls: type) -> None:
        instance = cls(**dict.fromkeys(cls.__dataclass_fields__, None))

        with pytest.raises(FrozenInstanceError):
            instance.matched_level = "locality"
