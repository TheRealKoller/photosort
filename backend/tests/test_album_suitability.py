"""specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 1 - Muster `test_motifs.py`.

DB-frei und netzfrei wie das Modul selbst. Drei Nachweise tragen mehr als eine Werteprüfung:

* JEDE Verwerfungsform ergibt "keine Zeile", nie eine geklemmte Stufe (Sicherheitsauflage S1).
  Eine geklemmte Stufe wäre eine Aussage, die das Modell nie getroffen hat - bei Stufe 1 die
  schlechteste, die das Produkt kennt.
* Die Kappung der Begründung ist ein TRIPEL (`MAX-1`/`MAX`/`MAX+1`) und wird gegen die
  Feinlabel-Regel gestellt, die bei Überlänge VERWIRFT: `reason` wird gekürzt, weil er nirgends
  verglichen, geschlüsselt oder slugifiziert wird.
* Saniert wird VOR dem Messen und Kürzen (S2) - andernfalls bliebe ein halbierter Bidi-/
  Zero-Width-Kontext stehen, den die Sanitisierung danach nicht mehr sieht.
"""

from __future__ import annotations

import json

import pytest

from photosort.album_suitability import (
    ALBUM_SUITABILITY_ANCHORS,
    ALBUM_SUITABILITY_MAX_LEVEL,
    ALBUM_SUITABILITY_MIN_LEVEL,
    ALBUM_SUITABILITY_NAMED_FLAWS,
    MAX_ALBUM_SUITABILITY_REASON_LENGTH,
    NO_VALUE,
    AlbumSuitability,
    album_suitability_from_json,
    build_album_suitability_prompt_lines,
    normalize_level,
)
from photosort.cloud_vision import _sanitize_label_text


def _parse(raw_literal: str, photo_id: int = 1) -> AlbumSuitability | None:
    """Geht bewusst durch `json.loads`: `true`, `null`, `3.0` und `"3"` sollen genau als die
    Python-Objekte ankommen, die ein echter Anbieterpfad liefert."""
    return album_suitability_from_json(json.loads(raw_literal), photo_id)


class TestTheScale:
    def test_the_scale_runs_from_one_to_five(self) -> None:
        assert ALBUM_SUITABILITY_MIN_LEVEL == 1
        assert ALBUM_SUITABILITY_MAX_LEVEL == 5

    def test_every_level_carries_its_own_anchor_text(self) -> None:
        assert set(ALBUM_SUITABILITY_ANCHORS) == {1, 2, 3, 4, 5}
        assert len(set(ALBUM_SUITABILITY_ANCHORS.values())) == 5
        for text in ALBUM_SUITABILITY_ANCHORS.values():
            assert text.strip()

    @pytest.mark.parametrize(
        ("level", "expected"),
        [(1, 0.0), (2, 0.25), (3, 0.5), (4, 0.75), (5, 1.0)],
    )
    def test_normalize_level_maps_the_five_levels_onto_the_unit_interval(
        self, level: int, expected: float
    ) -> None:
        assert normalize_level(level) == expected

    def test_normalize_level_is_monotonic_over_the_whole_scale(self) -> None:
        values = [normalize_level(level) for level in range(1, 6)]

        assert values == sorted(values)
        assert values[0] == 0.0
        assert values[-1] == 1.0


class TestParsingAWellFormedAnswer:
    def test_a_well_formed_answer_yields_level_and_reason(self) -> None:
        result = _parse('{"level": 4, "reason": "Alle schauen in die Kamera."}')

        assert result == AlbumSuitability(level=4, reason="Alle schauen in die Kamera.")

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_every_level_of_the_scale_is_accepted(self, level: int) -> None:
        result = _parse(f'{{"level": {level}, "reason": "kurz"}}')

        assert result is not None
        assert result.level == level

    def test_a_missing_reason_is_no_reason_and_no_error(self) -> None:
        result = _parse('{"level": 3}')

        assert result == AlbumSuitability(level=3, reason=None)


class TestEveryRejectionYieldsNoRow:
    @pytest.mark.parametrize(
        "raw_literal",
        [
            '{"reason": "ohne Stufe"}',
            '{"level": 0}',
            '{"level": 6}',
            '{"level": -1}',
            '{"level": "3"}',
            '{"level": 3.5}',
            '{"level": 4.0}',
            '{"level": null}',
            '{"level": true}',
            '{"level": false}',
            '{"level": [4]}',
            "[]",
            '"4"',
            "4",
            "null",
        ],
    )
    def test_an_unusable_level_yields_no_row_at_all(self, raw_literal: str) -> None:
        """VERWORFEN, nie geklemmt (S1): ohne brauchbare Stufe entsteht keine Zeile, und das Foto
        bleibt Kandidat des naechsten Laufs."""
        assert _parse(raw_literal) is None

    def test_a_boolean_level_is_never_read_as_level_one(self) -> None:
        """`isinstance(True, int)` ist `True` - ohne den expliziten bool-Ausschluss erschiene
        `"level": true` als Stufe 1, die schlechteste Aussage, die das Produkt kennt, erfunden aus
        einem Nicht-Wert."""
        assert _parse('{"level": true}') is None

    def test_a_float_level_is_rejected_even_when_it_is_whole(self) -> None:
        """Die Stufe ist ein Anker, kein Messwert. Die Zurueckweisung ALLER Gleitkommawerte
        schliesst `NaN`/`+-Infinity` mit aus, die `json.loads` klaglos parst - ein durchgelassener
        entarteter Wert legte ueber `allow_nan=False` die gesamte Fotoliste auf 500."""
        assert _parse('{"level": 4.0}') is None
        assert album_suitability_from_json({"level": float("nan")}, 1) is None
        assert album_suitability_from_json({"level": float("inf")}, 1) is None

    def test_an_out_of_range_level_is_not_clamped_to_the_band(self) -> None:
        assert _parse('{"level": 9, "reason": "sehr gut"}') is None
        assert _parse('{"level": 0, "reason": "sehr schlecht"}') is None

    def test_a_completely_absent_field_yields_no_row_either(self) -> None:
        assert album_suitability_from_json(NO_VALUE, 1) is None


class TestTheWarningLine:
    @pytest.mark.parametrize(
        "raw_literal",
        ['{"level": "3"}', '{"level": 3.5}', '{"level": null}', '{"level": 0}', "[]"],
    )
    def test_a_discarded_level_logs_exactly_one_warning_with_photo_id(
        self, caplog: pytest.LogCaptureFixture, raw_literal: str
    ) -> None:
        with caplog.at_level("WARNING", logger="photosort.album_suitability"):
            _parse(raw_literal, photo_id=42)

        assert len(caplog.records) == 1
        assert "photo_id=42" in caplog.records[0].getMessage()

    def test_the_warning_carries_a_fixed_reason_token_and_never_the_raw_value(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="photosort.album_suitability"):
            album_suitability_from_json({"level": "SEHR-GUT-42"}, 1)

        message = caplog.records[0].getMessage()
        assert "SEHR-GUT-42" not in message
        assert "grund=" in message

    def test_the_reason_text_is_never_logged_in_any_form(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """S3: `reason` ist genau der Fremdtext, der aus dem Log herauszuhalten ist - eine
        mehrzeilige Antwort erzeugte gefaelschte Logzeilen."""
        with caplog.at_level("WARNING", logger="photosort.album_suitability"):
            album_suitability_from_json({"level": "x", "reason": "GEHEIMER-FREMDTEXT"}, photo_id=1)

        assert "GEHEIMER-FREMDTEXT" not in caplog.records[0].getMessage()

    def test_a_missing_field_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Ein FEHLENDES Feld ist keine entartete Aussage, sondern gar keine - dieselbe Regel wie
        beim `excluded`-Feld der Motivantwort."""
        with caplog.at_level("WARNING", logger="photosort.album_suitability"):
            album_suitability_from_json(NO_VALUE, 1)

        assert caplog.records == []

    def test_a_well_formed_answer_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING", logger="photosort.album_suitability"):
            _parse('{"level": 2, "reason": "Augen geschlossen."}')

        assert caplog.records == []

    def test_an_unusable_reason_next_to_a_usable_level_logs_nothing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Eine leere Begruendung ist kein Fehler, sie ist `NULL` - und die Stufe steht."""
        with caplog.at_level("WARNING", logger="photosort.album_suitability"):
            result = _parse('{"level": 5, "reason": "   "}')

        assert result == AlbumSuitability(level=5, reason=None)
        assert caplog.records == []


class TestTheReasonText:
    def test_control_characters_and_line_breaks_are_sanitized_away(self) -> None:
        result = album_suitability_from_json({"level": 3, "reason": "Zwei\nZeilen‮mit​Tricks"}, 1)

        assert result is not None
        assert result.reason is not None
        assert "\n" not in result.reason
        assert "‮" not in result.reason
        assert "​" not in result.reason

    def test_the_sanitizer_is_the_shared_one_and_not_a_second_copy(self) -> None:
        """S2: DIESELBE Funktion wie der Feinlabel- und der Sehenswuerdigkeit-Pfad."""
        raw = "Ein\tText​mit  Zeichen"

        result = album_suitability_from_json({"level": 3, "reason": raw}, 1)

        assert result is not None
        assert result.reason == _sanitize_label_text(raw)

    @pytest.mark.parametrize("length", [1, MAX_ALBUM_SUITABILITY_REASON_LENGTH - 1])
    def test_a_reason_below_the_limit_survives_unchanged(self, length: int) -> None:
        raw = "a" * length

        result = album_suitability_from_json({"level": 3, "reason": raw}, 1)

        assert result is not None
        assert result.reason == raw

    def test_a_reason_exactly_at_the_limit_survives_unchanged(self) -> None:
        raw = "a" * MAX_ALBUM_SUITABILITY_REASON_LENGTH

        result = album_suitability_from_json({"level": 3, "reason": raw}, 1)

        assert result is not None
        assert result.reason == raw

    def test_a_reason_one_over_the_limit_is_truncated_and_not_discarded(self) -> None:
        """Das Gegenstueck zur Feinlabel-Regel, die VERWIRFT: `reason` wird nirgends verglichen,
        geschluesselt, dedupliziert oder slugifiziert - die Kappung ist eine Storage- und
        Degenerationsgrenze, keine Identitaetsfrage."""
        raw = "a" * (MAX_ALBUM_SUITABILITY_REASON_LENGTH + 1)

        result = album_suitability_from_json({"level": 3, "reason": raw}, 1)

        assert result is not None
        assert result.reason == "a" * MAX_ALBUM_SUITABILITY_REASON_LENGTH
        assert result.level == 3

    def test_the_text_is_sanitized_before_it_is_measured_and_truncated(self) -> None:
        """Die REIHENFOLGE ist die Auflage (S2): vor der Sanitisierung zu kuerzen liesse einen
        halbierten Bidi-/Zero-Width-Kontext stehen. Der Rohtext liegt hier ueber der Grenze, der
        sanitisierte darunter - wer zuerst kuerzt, verliert echte Zeichen."""
        raw = "​" * 40 + "b" * (MAX_ALBUM_SUITABILITY_REASON_LENGTH - 20)

        result = album_suitability_from_json({"level": 3, "reason": raw}, 1)

        assert result is not None
        assert result.reason == "b" * (MAX_ALBUM_SUITABILITY_REASON_LENGTH - 20)

    @pytest.mark.parametrize("raw", ["", "   ", "\n\t", "​​", "‮"])
    def test_an_empty_or_whitespace_only_reason_becomes_null_never_an_empty_string(
        self, raw: str
    ) -> None:
        result = album_suitability_from_json({"level": 3, "reason": raw}, 1)

        assert result is not None
        assert result.reason is None

    @pytest.mark.parametrize("raw_literal", ["4", "null", "true", "[]", "{}"])
    def test_a_reason_that_is_not_a_string_becomes_null_and_keeps_the_level(
        self, raw_literal: str
    ) -> None:
        result = _parse(f'{{"level": 3, "reason": {raw_literal}}}')

        assert result == AlbumSuitability(level=3, reason=None)


class TestThePromptBlock:
    def test_the_block_carries_all_five_anchor_texts(self) -> None:
        block = "\n".join(build_album_suitability_prompt_lines())

        for text in ALBUM_SUITABILITY_ANCHORS.values():
            assert text in block

    def test_the_block_is_generated_from_the_anchors_not_from_a_literal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(ALBUM_SUITABILITY_ANCHORS, 3, "Testanker drei.")

        assert "Testanker drei." in "\n".join(build_album_suitability_prompt_lines())

    def test_the_block_names_the_four_flaws_local_measurements_cannot_see(self) -> None:
        """Akzeptanzkriterium: geschlossene Augen, verdeckte Gesichter, angeschnittene Personen,
        langweilige Komposition - woertlich."""
        block = "\n".join(build_album_suitability_prompt_lines()).lower()

        assert len(ALBUM_SUITABILITY_NAMED_FLAWS) == 4
        for flaw in ALBUM_SUITABILITY_NAMED_FLAWS:
            assert flaw.lower() in block

    def test_the_block_names_the_limits_of_the_scale(self) -> None:
        block = "\n".join(build_album_suitability_prompt_lines())

        assert str(ALBUM_SUITABILITY_MIN_LEVEL) in block
        assert str(ALBUM_SUITABILITY_MAX_LEVEL) in block
        assert "album_suitability" in block
        assert '"level"' in block
        assert '"reason"' in block

    def test_the_block_names_the_reason_length_limit_it_enforces(self) -> None:
        """Prompt und Kappung duerfen nicht auseinanderlaufen - die Zahl steht nicht als zweites
        Literal im Prompt."""
        block = "\n".join(build_album_suitability_prompt_lines())

        assert str(MAX_ALBUM_SUITABILITY_REASON_LENGTH) in block
