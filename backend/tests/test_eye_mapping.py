"""Spec 0609 / ADR 0138 Punkt 3 - die Abbildung Eye-SDK-Ausgabe auf das Motivset.

Der Port aus `tools/eye-eval/src/mapping.js` hat zwei Fallen, und beide werden hier festgehalten:

* Die TABELLE ist die einzige Zuordnung. Ein Test gleicht die Motivschluessel gegen
  `MOTIF_REGISTRY` ab - ein Tippfehler dort erzeugte sonst ein neuntes Motiv, das die Registry nie
  anzeigt.
* Die GRENZEN sind inklusiv unten und exklusiv oben. Geprueft wird an den Grenzen selbst (0.2,
  0.4, 0.6, 0.8, 1.0) und nicht in der Mitte der Baender: nur so faellt eine um 0.01 verschobene
  Grenze auf.

Die Tag-Liste selbst ist gegen das ECHTE SDK-Vokabular geprueft: `tags.js` aus
`@desert-ant-labs/eye` fuehrt snake_case-Namen (`sky`), `eye_meta.json::labels.scenes` dagegen nur
Anzeigenamen (`Sky`). Der Abgleich gegen `tags.js` laeuft in `eye/test/tags.test.js`, der
Backend-Test haelt diese Tabelle und `eye/src/pins.json::mappingTags` deckungsgleich; der
Ausschluss-Abgleich gegen `eye_meta.json` bleibt Heimserver-Schritt (Bekannte Luecke in
specs/features/0002-offene-punkte.md).
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any

import pytest

from photosort.eye_mapping import (
    EXCLUDED_TYPES,
    EYE_PURPOSE_MAPPING,
    MAPPING_VERSION,
    MODEL_REVISION,
    EyeMappingError,
    album_level,
    analyze,
    fine_labels,
    is_excluded,
    motif_strengths,
)
from photosort.motifs import MOTIF_REGISTRY
from photosort.selection import MOTIF_PRESENCE_THRESHOLD

_SOURCE_DIR = Path(__file__).resolve().parent.parent / "src" / "photosort"


# Ein Payload in der Form, die der Sidecar unveraendert zurueckgibt - die gespeicherte JSON-Form
# des SDK (`Analysis.toJSON()`): Tag-Konfidenzen unter `tags`, dazu `scores`, `kind`, `faces`.
# `confidences` ist nur der Name der JS-Eigenschaft und steht NICHT im JSON; ein Payload mit
# diesem Schluessel liesse jede Motivstaerke still auf 0 fallen. Alles, was die Abbildung nicht
# liest, steht bewusst mit drin.
def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": "eye-4.2.3",
        "kind": "landscape",
        "tags": {
            "mountain": 0.91,
            "sky": 0.7,
            "people": 0.4,
            "document": 0.2,
        },
        "scores": {"aesthetic": 0.5, "keeper": 0.6, "cover": 0.3},
        "faces": [],
        "pets": [],
        "details": {"layout": {"shot": {"wide": 0.8, "close_up": 0.2}}},
    }
    payload.update(overrides)
    return payload


class TestTheMotifStrengths:
    def test_the_strength_is_the_highest_confidence_of_the_assigned_tags(self) -> None:
        strengths = motif_strengths(_payload())

        assert strengths["landschaft"] == pytest.approx(0.91)
        # `people` mit 0.4 ist unter der Schwelle - aber die Staerke ist keine Trefferaussage,
        # sie traegt den Wert selbst (0.4), damit der Vergleich bei 0.5 beide Seiten gleich
        # liest.
        assert strengths["menschen"] == pytest.approx(0.4)

    def test_all_eight_motifs_are_always_present_and_unmentioned_ones_are_zero(self) -> None:
        strengths = motif_strengths(_payload(tags={"mountain": 0.9}))

        assert list(strengths) == list(MOTIF_REGISTRY)
        assert strengths["tiere"] == 0.0
        assert strengths["essen_trinken"] == 0.0

    def test_a_tag_that_two_motifs_share_counts_for_both(self) -> None:
        """`building` und `people` stehen in mehreren Listen - eine erste Zuordnung, die den Tag
        "verbraucht", liesse eines der Motive grundlos auf 0 fallen."""
        strengths = motif_strengths(_payload(tags={"building": 0.8}))

        assert strengths["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.8)
        assert strengths["stadt_strasse"] == pytest.approx(0.8)

    def test_unknown_tags_and_non_numeric_values_do_not_leak_into_the_vector(self) -> None:
        strengths = motif_strengths(
            _payload(tags={"mountain": "hoch", "sky": True, "unbekannt": 0.99})
        )

        assert strengths["landschaft"] == 0.0

    def test_values_above_one_are_clamped_to_one(self) -> None:
        strengths = motif_strengths(_payload(tags={"mountain": 1.4}))

        assert strengths["landschaft"] == pytest.approx(1.0)

    def test_a_payload_without_tags_yields_eight_zeros(self) -> None:
        strengths = motif_strengths({"kind": None})

        assert set(strengths) == set(MOTIF_REGISTRY)
        assert set(strengths.values()) == {0.0}

    def test_every_motif_in_the_table_is_a_registry_key(self) -> None:
        motifs = EYE_PURPOSE_MAPPING["purposes"]["motivstaerken"]["motifs"]

        assert set(motifs) == set(MOTIF_REGISTRY)

    def test_no_motif_lists_the_same_tag_twice(self) -> None:
        motifs = EYE_PURPOSE_MAPPING["purposes"]["motivstaerken"]["motifs"]

        for motif_key, tags in motifs.items():
            assert len(tags) == len(set(tags)), motif_key


class TestTheDocumentExclusion:
    def test_a_known_type_excludes(self) -> None:
        assert is_excluded(_payload(kind="screenshot")) is True

    def test_every_type_of_the_binding_list_excludes(self) -> None:
        purposes = EYE_PURPOSE_MAPPING["purposes"]["ausschluss"]

        assert len(purposes["excluded_types"]) == 12
        for kind in purposes["excluded_types"]:
            assert is_excluded(_payload(kind=kind)) is True

    def test_an_unknown_type_excludes_nothing(self) -> None:
        assert is_excluded(_payload(kind="landscape")) is False

    def test_a_missing_type_excludes_nothing(self) -> None:
        """Die Abwesenheit einer Typangabe ist keine Dokumentaussage."""
        payload = _payload()
        del payload["kind"]

        assert is_excluded(payload) is False

    def test_a_non_string_type_excludes_nothing(self) -> None:
        assert is_excluded(_payload(kind=42)) is False


class TestTheAlbumLevel:
    @pytest.mark.parametrize(
        ("note", "level"),
        [
            (0.0, 1),
            (0.19, 1),
            (0.2, 2),
            (0.39, 2),
            (0.4, 3),
            (0.59, 3),
            (0.6, 4),
            (0.79, 4),
            (0.8, 5),
            (0.99, 5),
            (1.0, 5),
        ],
    )
    def test_the_bands_are_lower_inclusive_and_upper_exclusive(
        self, note: float, level: int
    ) -> None:
        assert album_level(_payload(scores={"aesthetic": note})) == level

    def test_a_missing_aesthetic_score_is_an_error_not_a_default(self) -> None:
        """Eine erfundene Stufe waere eine Aussage, die das Modell nie getroffen hat."""
        with pytest.raises(EyeMappingError):
            album_level(_payload(scores={"keeper": 0.6}))

    def test_a_missing_scores_object_is_an_error(self) -> None:
        payload = _payload()
        del payload["scores"]

        with pytest.raises(EyeMappingError):
            album_level(payload)

    def test_a_non_numeric_aesthetic_score_is_an_error(self) -> None:
        with pytest.raises(EyeMappingError):
            album_level(_payload(scores={"aesthetic": "gut"}))

    def test_a_score_outside_the_scale_is_clamped(self) -> None:
        assert album_level(_payload(scores={"aesthetic": 1.7})) == 5
        assert album_level(_payload(scores={"aesthetic": -0.4})) == 1


class TestTheFineLabels:
    def test_only_tags_from_the_threshold_on_appear(self) -> None:
        labels = fine_labels(_payload())

        assert [label for label, _ in labels] == ["mountain", "sky"]

    def test_the_threshold_is_inclusive(self) -> None:
        assert fine_labels(_payload(tags={"mountain": 0.5})) == (("mountain", 0.5),)
        assert fine_labels(_payload(tags={"mountain": 0.4999})) == ()

    def test_the_strongest_come_first_and_ties_are_alphabetical(self) -> None:
        labels = fine_labels(
            _payload(tags={"sky": 0.6, "mountain": 0.9, "beach": 0.6, "food": 0.7})
        )

        assert [label for label, _ in labels] == ["mountain", "food", "beach", "sky"]

    def test_the_excluded_types_are_not_fine_labels(self) -> None:
        """Der Typ ist bereits die Aussage `excluded_document` - als Feinlabel waere er ein
        zweites Mal gezaehlt."""
        labels = fine_labels(_payload(tags={"document": 0.9, "mountain": 0.7}))

        assert [label for label, _ in labels] == ["mountain"]

    def test_the_values_are_the_raw_confidences(self) -> None:
        labels = fine_labels(_payload(tags={"mountain": 0.73}))

        assert labels == (("mountain", 0.73),)


class TestTheWholeMapping:
    def test_analyze_returns_all_four_answers(self) -> None:
        analysis = analyze(_payload(kind="document", scores={"aesthetic": 0.75}))

        assert analysis.excluded_document is True
        assert analysis.album_level == 4
        assert analysis.motif_strengths["landschaft"] == pytest.approx(0.91)
        assert analysis.fine_labels == (("mountain", 0.91), ("sky", 0.7))

    def test_the_published_version_and_revision_are_named(self) -> None:
        assert MAPPING_VERSION == "eye-4.2.3/v1"
        assert MODEL_REVISION == "v1.0.0"
        assert EYE_PURPOSE_MAPPING["version"] == MAPPING_VERSION
        assert EYE_PURPOSE_MAPPING["model_revision"] == MODEL_REVISION


class TestThePublishedThresholdAgainstTheSelectionPredicate:
    """`EYE_PURPOSE_MAPPING` beschreibt die Praesenzgrenze, entschieden wird sie in
    `selection.py`. Zwei Zahlen fuer dieselbe Grenze driften sonst still auseinander - hier
    bricht die Drift laut."""

    def test_the_published_motif_present_threshold_is_the_selection_threshold(self) -> None:
        assert EYE_PURPOSE_MAPPING["thresholds"]["motif_present"] == MOTIF_PRESENCE_THRESHOLD


class TestTheStructuralGuards:
    def test_the_module_imports_nothing_but_the_standard_library_and_the_motif_registry(
        self,
    ) -> None:
        """ADR 0138 Punkt 3: das Modul steht neben `motifs.py` und bleibt frei von Session,
        Modell und Sidecar."""
        tree = ast.parse((_SOURCE_DIR / "eye_mapping.py").read_text(encoding="utf-8"))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported |= {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }

        foreign = {
            name
            for name in imported
            if not name.startswith(("collections", "dataclasses", "types", "typing", "__future__"))
            and name != "photosort.motifs"
        }
        assert foreign == set()


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PINS_FILE = _REPO_ROOT / "eye" / "src" / "pins.json"


class TestTheTagsAgainstTheSidecarPins:
    """Die Tag-Liste steht in DREI Fassungen, und alle drei muessen gleich sein: diese Tabelle,
    `mappingTags` in `eye/src/pins.json` und das SDK-Vokabular aus `tags.js`.

    Grund fuer die Pins-Fassung: das Modell ist gepinnt, das Vokabular ist es damit auch. Ein
    Pin-Wechsel, der einen Tag umbenennt, faellt dann hier auf und nicht als stille Null in jedem
    Eye-Ergebnis. Der Abgleich gegen `tags.js` selbst laeuft in `eye/test/tags.test.js`, wo die SDK
    ohnehin Abhaengigkeit ist; dieses Modul bleibt frei von Node.
    """

    def test_the_binding_table_equals_the_pins(self) -> None:
        pins = json.loads(_PINS_FILE.read_text(encoding="utf-8"))
        table = {
            tag
            for tags in EYE_PURPOSE_MAPPING["purposes"]["motivstaerken"]["motifs"].values()
            for tag in tags
        }
        pinned = set(pins["mappingTags"])

        assert table - pinned == set()
        assert pinned - table == set()

    def test_the_pins_name_the_pinned_revision_and_commit(self) -> None:
        pins = json.loads(_PINS_FILE.read_text(encoding="utf-8"))

        assert pins["revision"] == MODEL_REVISION
        assert len(pins["commit"]) == 40
        assert set(pins["files"]) == {"eye.tflite", "eye_meta.json"}
        for digest in pins["files"].values():
            assert len(digest) == 64

    def test_every_motif_tag_is_lowercase_snake_case(self) -> None:
        """Das SDK-Vokabular ist snake_case; ein Anzeigename wie "Human face" wuerde nie treffen."""
        table = {
            tag
            for tags in EYE_PURPOSE_MAPPING["purposes"]["motivstaerken"]["motifs"].values()
            for tag in tags
        }

        for tag in table:
            assert tag == tag.lower()
            assert " " not in tag


@pytest.mark.skipif(
    not Path(os.environ.get("EYE_META_PATH", "eye_model/eye_meta.json")).exists(),
    reason="eye_meta.json liegt ausserhalb des Repos - Heimserver-Schritt",
)
def test_every_excluded_type_exists_in_eye_meta() -> None:
    """Heimserver-Schritt (0002): der Ausschluss haengt an `labels.type` des echten Modells. Die
    Motiv-Tags lassen sich dort NICHT abgleichen - `labels.scenes` fuehrt Anzeigenamen ("Sky"),
    die SDK-Antwort snake_case-Tags ("sky"); dieser Abgleich laeuft in eye/test/tags.test.js."""
    meta = json.loads(
        Path(os.environ.get("EYE_META_PATH", "eye_model/eye_meta.json")).read_text(encoding="utf-8")
    )
    known = set(meta["labels"]["type"])

    assert EXCLUDED_TYPES - known == set()
