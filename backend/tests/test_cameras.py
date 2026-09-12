"""Unit-Tests des reinen Kamera-Moduls - DB-frei, Schwerpunkt der Teststrategie von Spec 0426."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from photosort.cameras import (
    MAX_CAMERA_FIELD_LENGTH,
    MAX_TIME_OFFSET_MINUTES,
    CameraIdentity,
    camera_identity,
    camera_label,
    shifted,
    suggested_offset_minutes,
)

# Jedes gepruefte unsichtbare Zeichen steht als CODEPUNKT da, nie als literales Zeichen im
# Quelltext: ein literales U+200B in dieser Datei ist fuer keinen Prueferblick von einem fehlenden
# Zeichen zu unterscheiden, und zwei Faelle einer Parametrisierung saehen identisch aus. Diese
# Datei enthaelt deshalb bewusst KEIN unsichtbares Zeichen.
LEFT_TO_RIGHT_EMBEDDING = chr(0x202A)
RIGHT_TO_LEFT_OVERRIDE = chr(0x202E)
LEFT_TO_RIGHT_ISOLATE = chr(0x2066)
POP_DIRECTIONAL_ISOLATE = chr(0x2069)
ZERO_WIDTH_SPACE = chr(0x200B)
ZERO_WIDTH_JOINER = chr(0x200D)
ZERO_WIDTH_NO_BREAK_SPACE = chr(0xFEFF)
NEXT_LINE = chr(0x85)
LINE_SEPARATOR = chr(0x2028)
PARAGRAPH_SEPARATOR = chr(0x2029)
NUL = chr(0x00)
TAB = chr(0x09)
LINE_FEED = chr(0x0A)
CARRIAGE_RETURN = chr(0x0D)


class TestCameraIdentity:
    def test_make_and_model_become_an_identity(self) -> None:
        assert camera_identity("Canon", "EOS 5D") == CameraIdentity(make="Canon", model="EOS 5D")

    @pytest.mark.parametrize("raw", [1, b"Canon", None, ["Canon"], 3.5, {"make": "Canon"}])
    def test_a_non_string_field_is_discarded(self, raw: object) -> None:
        """Alles, was kein `str` ist, wird verworfen statt umgedeutet - der Wert kommt aus einer
        fremden, moeglicherweise entarteten Datei."""
        assert camera_identity(raw, "EOS 5D") == CameraIdentity(make="", model="EOS 5D")

    @pytest.mark.parametrize("raw", ["", "   ", NUL, NUL + NUL + " " + TAB])
    def test_an_empty_whitespace_or_nul_field_counts_as_absent(self, raw: str) -> None:
        assert camera_identity(raw, "EOS 5D") == CameraIdentity(make="", model="EOS 5D")

    def test_both_fields_absent_gives_no_identity(self) -> None:
        assert camera_identity("  ", "") is None
        assert camera_identity(None, None) is None

    def test_only_make_is_enough(self) -> None:
        assert camera_identity("Canon", "") == CameraIdentity(make="Canon", model="")

    def test_only_model_is_enough(self) -> None:
        assert camera_identity("", "EOS 5D") == CameraIdentity(make="", model="EOS 5D")

    @pytest.mark.parametrize(
        "invisible",
        [
            LEFT_TO_RIGHT_EMBEDDING,
            RIGHT_TO_LEFT_OVERRIDE,
            LEFT_TO_RIGHT_ISOLATE,
            POP_DIRECTIONAL_ISOLATE,
            ZERO_WIDTH_SPACE,
            ZERO_WIDTH_JOINER,
            ZERO_WIDTH_NO_BREAK_SPACE,
            NEXT_LINE,
        ],
    )
    def test_invisible_characters_are_removed(self, invisible: str) -> None:
        identity = camera_identity(f"Ca{invisible}non", f"{invisible}EOS 5D")

        assert identity == CameraIdentity(make="Canon", model="EOS 5D")

    @pytest.mark.parametrize(
        "invisible",
        [
            RIGHT_TO_LEFT_OVERRIDE,
            ZERO_WIDTH_SPACE + ZERO_WIDTH_JOINER,
            ZERO_WIDTH_NO_BREAK_SPACE + NEXT_LINE,
        ],
    )
    def test_a_field_made_only_of_invisible_characters_counts_as_absent(
        self, invisible: str
    ) -> None:
        assert camera_identity(invisible, "EOS 5D") == CameraIdentity(make="", model="EOS 5D")

    def test_two_values_differing_only_in_invisible_characters_are_one_camera(self) -> None:
        """Die tragende Sicherheitszusage: zwei optisch identische Listenzeilen fuehren den Versatz
        auf die falsche Kamera."""
        first = camera_identity("Canon", f"EOS{ZERO_WIDTH_SPACE} 5D")
        second = camera_identity("Canon", "EOS 5D")

        assert first == second

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("EOS   5D", "EOS 5D"),
            ("  EOS 5D  ", "EOS 5D"),
            (f"EOS{LINE_SEPARATOR}5D", "EOS 5D"),
            (f"EOS{PARAGRAPH_SEPARATOR}5D", "EOS 5D"),
        ],
    )
    def test_inner_whitespace_runs_collapse_to_one_space(self, raw: str, expected: str) -> None:
        """U+2028/U+2029 sind Leerraum (`Zl`/`Zp`) und fallen hierunter, nicht unter das Entfernen
        der unsichtbaren Zeichen."""
        identity = camera_identity("Canon", raw)

        assert identity == CameraIdentity(make="Canon", model=expected)

    @pytest.mark.parametrize("control", [TAB, LINE_FEED, CARRIAGE_RETURN, NEXT_LINE])
    def test_a_whitespace_control_character_is_removed_not_turned_into_a_space(
        self, control: str
    ) -> None:
        """Die REIHENFOLGE, festgenagelt: entfernen, DANN Leerraumfolgen zusammenziehen. Tabulator,
        Zeilenumbruch und U+0085 sind `Cc` und fallen deshalb unter das Entfernen - sie werden
        nicht zu einem Leerzeichen. Beide Richtungen fuehren dieselben Werte zusammen; die hier
        gewaehlte deckt sich mit der Aufzaehlung im Sicherheitsabschnitt der Spec, die U+0085
        ausdruecklich unter den ENTFERNTEN Zeichen nennt."""
        identity = camera_identity("Canon", f"EOS{control}5D")

        assert identity == CameraIdentity(make="Canon", model="EOS5D")

    def test_a_field_of_maximum_length_is_valid(self) -> None:
        model = "M" * MAX_CAMERA_FIELD_LENGTH

        assert camera_identity("Canon", model) == CameraIdentity(make="Canon", model=model)

    def test_one_character_more_is_discarded_not_truncated(self) -> None:
        """VERWORFEN, nie abgeschnitten - ein gekuerztes Modell waere eine andere Kamera."""
        identity = camera_identity("Canon", "M" * (MAX_CAMERA_FIELD_LENGTH + 1))

        assert identity == CameraIdentity(make="Canon", model="")

    def test_the_length_check_applies_per_field_not_to_the_joined_label(self) -> None:
        make = "M" * MAX_CAMERA_FIELD_LENGTH
        model = "X" * MAX_CAMERA_FIELD_LENGTH

        assert camera_identity(make, model) == CameraIdentity(make=make, model=model)

    def test_the_length_check_runs_after_removing_invisible_characters(self) -> None:
        model = "M" * MAX_CAMERA_FIELD_LENGTH
        padded = ZERO_WIDTH_SPACE.join(model)

        assert camera_identity("Canon", padded) == CameraIdentity(make="Canon", model=model)


class TestCameraLabel:
    def test_a_model_starting_with_the_make_stands_alone(self) -> None:
        label = camera_label(CameraIdentity(make="Canon", model="Canon EOS 5D"))

        assert label == "Canon EOS 5D"

    def test_the_prefix_check_ignores_the_letter_case(self) -> None:
        label = camera_label(CameraIdentity(make="CANON", model="canon EOS 5D"))

        assert label == "canon EOS 5D"

    def test_a_model_containing_the_make_elsewhere_keeps_both(self) -> None:
        label = camera_label(CameraIdentity(make="Canon", model="EOS Canon 5D"))

        assert label == "Canon EOS Canon 5D"

    def test_make_and_model_are_joined_with_one_space(self) -> None:
        assert camera_label(CameraIdentity(make="Canon", model="EOS 5D")) == "Canon EOS 5D"

    def test_only_make_gives_the_make(self) -> None:
        assert camera_label(CameraIdentity(make="Canon", model="")) == "Canon"

    def test_only_model_gives_the_model(self) -> None:
        assert camera_label(CameraIdentity(make="", model="EOS 5D")) == "EOS 5D"


class TestShifted:
    def test_a_positive_offset_moves_the_timestamp_forward(self) -> None:
        assert shifted(datetime(2026, 8, 12, 14, 32), 60) == datetime(2026, 8, 12, 15, 32)

    def test_a_negative_offset_moves_the_timestamp_back(self) -> None:
        assert shifted(datetime(2026, 8, 12, 14, 32), -60) == datetime(2026, 8, 12, 13, 32)

    def test_an_offset_of_zero_returns_the_same_timestamp(self) -> None:
        original = datetime(2026, 8, 12, 14, 32)

        assert shifted(original, 0) == original

    def test_the_minimum_below_the_representable_range_gives_no_result(self) -> None:
        assert shifted(datetime.min, -1) is None

    def test_the_maximum_above_the_representable_range_gives_no_result(self) -> None:
        assert shifted(datetime.max, 1) is None

    @pytest.mark.parametrize("border", [datetime.min, datetime.max])
    def test_an_offset_of_zero_on_a_border_returns_the_border_itself(
        self, border: datetime
    ) -> None:
        """NICHT `None` - `0` ist kein Ueberlauf, und ein `None` hier wuerde am Endpunkt einen
        voellig gewoehnlichen Datensatz zurueckweisen."""
        assert shifted(border, 0) == border

    def test_microseconds_survive_the_shift(self) -> None:
        original = datetime(2026, 8, 12, 14, 32, 5, 123456)

        assert shifted(original, 1) == original + timedelta(minutes=1)

    @pytest.mark.parametrize("offset", [MAX_TIME_OFFSET_MINUTES, -MAX_TIME_OFFSET_MINUTES])
    def test_the_maximum_offset_on_a_middle_date_computes_through(self, offset: int) -> None:
        result = shifted(datetime(2026, 8, 12, 14, 32), offset)

        assert result == datetime(2026, 8, 12, 14, 32) + timedelta(minutes=offset)


class TestSuggestedOffsetMinutes:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0, 0),
            (29, 0),
            (30, 1),
            (31, 1),
            (150, 3),
            (-29, 0),
            (-30, -1),
            (-31, -1),
            (-150, -3),
        ],
    )
    def test_it_rounds_halves_away_from_zero(self, seconds: int, expected: int) -> None:
        """`30 s` und `150 s` sind die beiden Faelle, die "Haelften vom Null weg" von `round()`
        trennen - `round` liefert dort `0` bzw. `2`. Ein Satz aus 60/120/180 s bestuende mit jeder
        Implementierung."""
        camera_original = datetime(2026, 8, 12, 14, 0, 0)
        reference_effective = camera_original + timedelta(seconds=seconds)

        assert suggested_offset_minutes(camera_original, reference_effective) == expected

    def test_a_result_beyond_the_limits_is_not_clamped(self) -> None:
        """Das Zurueckweisen liegt am Endpunkt, nicht in der reinen Funktion."""
        camera_original = datetime(1, 1, 1, 0, 0)
        reference_effective = datetime(9999, 12, 31, 0, 0)

        assert suggested_offset_minutes(camera_original, reference_effective) > (
            MAX_TIME_OFFSET_MINUTES
        )
