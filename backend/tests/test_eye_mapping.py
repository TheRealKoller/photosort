"""Spec 0609 / ADR 0138 Punkt 3, Spec 0615 / ADR 0140 - die Abbildung Eye-SDK-Ausgabe auf das
Motivset, in beiden aufrufbaren Fassungen.

Drei Fallen werden hier festgehalten:

* Jede TABELLE deckt genau die Registry ab. Ein Test gleicht die Motivschluessel jeder Fassung
  gegen `MOTIF_REGISTRY` ab - ein Tippfehler dort erzeugte sonst ein neuntes Motiv, das die
  Registry nie anzeigt.
* Die GRENZEN sind inklusiv unten und exklusiv oben. Geprueft wird an den Grenzen selbst (0.2,
  0.4, 0.6, 0.8, 1.0) und nicht in der Mitte der Baender: nur so faellt eine um 0.01 verschobene
  Grenze auf.
* v1 bleibt WERTGLEICH aufrufbar. Was v2 nicht aendern soll (sechs Motive, Albumstufe,
  Feinlabels), wird gegen v1 verglichen und nicht gegen einen zweiten Satz Erwartungswerte.

Die Tag-Liste selbst ist gegen das ECHTE SDK-Vokabular geprueft: `tags.js` aus
`@desert-ant-labs/eye` fuehrt snake_case-Namen (`sky`), `eye_meta.json::labels.scenes` dagegen nur
Anzeigenamen (`Sky`). Der Abgleich gegen `tags.js` laeuft in `eye/test/tags.test.js`, der
Backend-Test haelt die Vereinigung aller Tabellen und `eye/src/pins.json::mappingTags`
deckungsgleich; der Ausschluss-Abgleich gegen `eye_meta.json` bleibt Heimserver-Schritt (Bekannte
Luecke in specs/features/0002-offene-punkte.md).
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any

import pytest

from photosort.eye_mapping import (
    DOCUMENT_TYPES,
    EYE_PURPOSE_MAPPING,
    MAPPING_V1,
    MAPPING_V2,
    MAPPING_VERSION,
    MAPPING_VERSION_V1,
    MAPPINGS,
    MODEL_REVISION,
    EyeMapping,
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

# Die sieben Fotoarten, die v1 ausschliesst und v2 nicht.
_ONLY_V1_EXCLUDES = (
    "map",
    "whiteboard",
    "chart_or_slide",
    "meme_or_graphic",
    "medical_reference",
    "repair_reference",
    "shopping_reference",
)
_V2_EXCLUDES = ("document", "screenshot", "receipt", "photo_of_screen", "id_card")


# Ein Payload in der Form, die der Sidecar unveraendert zurueckgibt - die gespeicherte JSON-Form
# des SDK (`Analysis.toJSON()`): Tag-Konfidenzen unter `tags`, dazu `scores`, `kind`, `faces`,
# `pets`. `confidences` ist nur der Name der JS-Eigenschaft und steht NICHT im JSON; ein Payload
# mit diesem Schluessel liesse jede Motivstaerke still auf 0 fallen. Alles, was die Abbildung nicht
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


def _pet(confidence: Any, label: str = "dog") -> dict[str, Any]:
    return {"label": label, "confidence": confidence, "box": {"x": 0, "y": 0, "w": 1, "h": 1}}


_BOTH = pytest.mark.parametrize("mapping", [MAPPING_V1, MAPPING_V2], ids=["v1", "v2"])


class TestTheMotifStrengths:
    @_BOTH
    def test_the_strength_is_the_highest_confidence_of_the_assigned_tags(
        self, mapping: EyeMapping
    ) -> None:
        strengths = motif_strengths(_payload(), mapping)

        assert strengths["landschaft"] == pytest.approx(0.91)
        # `people` mit 0.4 ist unter der Schwelle - aber die Staerke ist keine Trefferaussage,
        # sie traegt den Wert selbst (0.4), damit der Vergleich bei 0.5 beide Seiten gleich
        # liest.
        assert strengths["menschen"] == pytest.approx(0.4)

    @_BOTH
    def test_all_eight_motifs_are_always_present_and_unmentioned_ones_are_zero(
        self, mapping: EyeMapping
    ) -> None:
        strengths = motif_strengths(_payload(tags={"mountain": 0.9}), mapping)

        assert list(strengths) == list(MOTIF_REGISTRY)
        assert strengths["tiere"] == 0.0
        assert strengths["essen_trinken"] == 0.0

    @_BOTH
    def test_a_tag_that_two_motifs_share_counts_for_both(self, mapping: EyeMapping) -> None:
        """`building` und `people` stehen in mehreren Listen - eine erste Zuordnung, die den Tag
        "verbraucht", liesse eines der Motive grundlos auf 0 fallen."""
        strengths = motif_strengths(_payload(tags={"building": 0.8}), mapping)

        assert strengths["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.8)
        assert strengths["stadt_strasse"] == pytest.approx(0.8)

    @_BOTH
    def test_unknown_tags_and_non_numeric_values_do_not_leak_into_the_vector(
        self, mapping: EyeMapping
    ) -> None:
        strengths = motif_strengths(
            _payload(tags={"mountain": "hoch", "sky": True, "unbekannt": 0.99}), mapping
        )

        assert strengths["landschaft"] == 0.0

    @_BOTH
    def test_values_above_one_are_clamped_to_one(self, mapping: EyeMapping) -> None:
        strengths = motif_strengths(_payload(tags={"mountain": 1.4}), mapping)

        assert strengths["landschaft"] == pytest.approx(1.0)

    @_BOTH
    @pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), 10**400])
    def test_a_non_finite_tag_value_counts_as_zero(self, mapping: EyeMapping, value: Any) -> None:
        """S1: `json.loads` nimmt `Infinity`, `NaN` und beliebig grosse Ganzzahlen an. Ein
        nicht-endlicher Wert ist keine Aussage - er wird verworfen, nicht auf 1 geklemmt, und
        eine Ganzzahl jenseits des float-Bereichs wirft keinen `OverflowError`."""
        strengths = motif_strengths(_payload(tags={"mountain": value}), mapping)

        assert strengths["landschaft"] == 0.0

    @_BOTH
    def test_a_payload_without_tags_yields_eight_zeros(self, mapping: EyeMapping) -> None:
        strengths = motif_strengths({"kind": None}, mapping)

        assert set(strengths) == set(MOTIF_REGISTRY)
        assert set(strengths.values()) == {0.0}

    @pytest.mark.parametrize("version", list(MAPPINGS))
    def test_every_motif_in_every_table_is_a_registry_key(self, version: str) -> None:
        assert set(MAPPINGS[version].motif_tags) == set(MOTIF_REGISTRY)
        assert set(MAPPINGS[version].motif_detections) <= set(MOTIF_REGISTRY)

    @pytest.mark.parametrize("version", list(MAPPINGS))
    def test_no_motif_lists_the_same_tag_twice(self, version: str) -> None:
        for motif_key, tags in MAPPINGS[version].motif_tags.items():
            assert len(tags) == len(set(tags)), motif_key


class TestTheAnimalsInV2:
    @pytest.mark.parametrize("tag", ["animal", "insect", "wildlife", "marine_mammal", "dog"])
    def test_a_generic_or_class_tag_carries_the_strength(self, tag: str) -> None:
        strengths = motif_strengths(_payload(tags={tag: 0.8}), MAPPING_V2)

        assert strengths["tiere"] == pytest.approx(0.8)

    def test_eyes_pet_detection_carries_the_strength_without_an_animal_tag(self) -> None:
        strengths = motif_strengths(
            _payload(tags={}, pets=[_pet(0.3), _pet(0.7, "cat")]), MAPPING_V2
        )

        assert strengths["tiere"] == pytest.approx(0.7)

    def test_the_strength_is_the_maximum_of_tag_and_detection(self) -> None:
        low_detection = _payload(tags={"animal": 0.6}, pets=[_pet(0.4)])
        high_detection = _payload(tags={"animal": 0.6}, pets=[_pet(0.9)])

        assert motif_strengths(low_detection, MAPPING_V2)["tiere"] == pytest.approx(0.6)
        assert motif_strengths(high_detection, MAPPING_V2)["tiere"] == pytest.approx(0.9)

    def test_the_detection_feeds_no_other_motif(self) -> None:
        strengths = motif_strengths(_payload(tags={}, pets=[_pet(0.9)]), MAPPING_V2)

        assert {key for key, value in strengths.items() if value > 0} == {"tiere"}

    def test_v1_ignores_the_detection_and_the_new_animal_tags(self) -> None:
        strengths = motif_strengths(
            _payload(tags={"animal": 0.9, "insect": 0.9}, pets=[_pet(0.9)]), MAPPING_V1
        )

        assert strengths["tiere"] == 0.0

    @pytest.mark.parametrize(
        "pets",
        [
            None,
            {"confidence": 0.9},
            "dog",
            0.9,
            [0.9],
            ["dog"],
            [None],
            [_pet("0.9")],
            [_pet(True)],
            [_pet(None)],
            [_pet(float("nan"))],
            [_pet(float("inf"))],
            [_pet(float("-inf"))],
            [_pet(10**400)],
            [{"label": "dog"}],
        ],
    )
    def test_a_defective_detection_counts_as_zero(self, pets: Any) -> None:
        """S1: `pets` ist Fremdeingabe - kein JSON-Wert bricht die Abbildung ab."""
        strengths = motif_strengths(_payload(tags={}, pets=pets), MAPPING_V2)

        assert strengths["tiere"] == 0.0

    def test_a_missing_detection_list_counts_as_zero(self) -> None:
        payload = _payload(tags={})
        del payload["pets"]

        assert motif_strengths(payload, MAPPING_V2)["tiere"] == 0.0

    def test_a_defective_entry_does_not_hide_a_valid_one(self) -> None:
        strengths = motif_strengths(
            _payload(tags={}, pets=["dog", _pet(float("nan")), _pet(0.6)]), MAPPING_V2
        )

        assert strengths["tiere"] == pytest.approx(0.6)

    def test_detection_values_are_clamped(self) -> None:
        assert motif_strengths(_payload(tags={}, pets=[_pet(1.7)]), MAPPING_V2)[
            "tiere"
        ] == pytest.approx(1.0)
        assert motif_strengths(_payload(tags={}, pets=[_pet(-0.4)]), MAPPING_V2)["tiere"] == 0.0


class TestTheActivityInV2:
    @pytest.mark.parametrize(
        "tag", ["hiking", "walking", "cycle_sport", "playground", "dance", "skiing", "canoe"]
    )
    def test_a_tag_naming_an_activity_counts(self, tag: str) -> None:
        strengths = motif_strengths(_payload(tags={tag: 0.8}), MAPPING_V2)

        assert strengths["aktivitaet"] == pytest.approx(0.8)

    @pytest.mark.parametrize(
        "tag",
        [
            "surfboard",
            "stadium",
            "swimming_pool",
            "swimwear",
            "sailboat",
            "chess",
            "horse_racing",
            "motorsport",
        ],
    )
    def test_objects_places_clothing_and_spectator_sports_do_not_count(self, tag: str) -> None:
        strengths = motif_strengths(_payload(tags={tag: 0.9}), MAPPING_V2)

        assert strengths["aktivitaet"] == 0.0

    def test_v2_keeps_every_v1_activity_tag(self) -> None:
        assert set(MAPPING_V1.motif_tags["aktivitaet"]) <= set(MAPPING_V2.motif_tags["aktivitaet"])

    def test_v1_ignores_the_new_activity_tags(self) -> None:
        assert motif_strengths(_payload(tags={"hiking": 0.9}), MAPPING_V1)["aktivitaet"] == 0.0


class TestTheUnchangedPartsOfV2:
    """Die sechs uebrigen Motive, die Albumstufe und die Feinlabels sind in v1 und v2 gleich."""

    _UNCHANGED = (
        "menschen",
        "landschaft",
        "bauwerk_sehenswuerdigkeit",
        "stadt_strasse",
        "essen_trinken",
        "detail_stimmung",
    )

    def test_the_six_other_motif_tables_are_identical(self) -> None:
        for motif_key in self._UNCHANGED:
            assert MAPPING_V1.motif_tags[motif_key] == MAPPING_V2.motif_tags[motif_key], motif_key

    @pytest.mark.parametrize("aesthetic", [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 0.19, 0.79])
    def test_strengths_and_album_level_agree_on_every_table_tag(self, aesthetic: float) -> None:
        tags = {
            tag: 0.55 + index / 1000
            for index, tag in enumerate(
                sorted({tag for key in self._UNCHANGED for tag in MAPPING_V1.motif_tags[key]})
            )
        }
        payload = _payload(tags=tags, scores={"aesthetic": aesthetic})

        v1 = motif_strengths(payload, MAPPING_V1)
        v2 = motif_strengths(payload, MAPPING_V2)

        for motif_key in self._UNCHANGED:
            assert v1[motif_key] == v2[motif_key], motif_key
            assert v1[motif_key] > 0, motif_key
        assert album_level(payload, MAPPING_V1) == album_level(payload, MAPPING_V2)

    def test_the_fine_labels_are_identical_even_for_a_narrowed_exclusion_type(self) -> None:
        payload = _payload(tags={"map": 0.9, "document": 0.8, "mountain": 0.7, "dog": 0.6})

        assert fine_labels(payload, MAPPING_V1) == fine_labels(payload, MAPPING_V2)
        assert [label for label, _ in fine_labels(payload, MAPPING_V2)] == ["mountain", "dog"]

    def test_both_versions_filter_the_same_photo_types(self) -> None:
        assert MAPPING_V1.fine_label_excluded == MAPPING_V2.fine_label_excluded == DOCUMENT_TYPES
        assert len(DOCUMENT_TYPES) == 12


class TestTheDocumentExclusion:
    @pytest.mark.parametrize("kind", _V2_EXCLUDES)
    def test_every_type_of_the_v2_core_excludes(self, kind: str) -> None:
        assert is_excluded(_payload(kind=kind), MAPPING_V2) is True
        assert is_excluded(_payload(kind=kind), MAPPING_V1) is True

    @pytest.mark.parametrize("kind", _ONLY_V1_EXCLUDES)
    def test_the_other_photo_types_exclude_only_in_v1(self, kind: str) -> None:
        assert is_excluded(_payload(kind=kind), MAPPING_V2) is False
        assert is_excluded(_payload(kind=kind), MAPPING_V1) is True

    def test_the_v2_exclusion_is_exactly_the_core(self) -> None:
        assert MAPPING_V2.excluded_types == frozenset(_V2_EXCLUDES)

    def test_v1_excludes_the_twelve_photo_types(self) -> None:
        assert MAPPING_V1.excluded_types == DOCUMENT_TYPES

    @pytest.mark.parametrize("tag", ["map", "document", "screenshot"])
    def test_a_photo_with_a_strong_document_tag_stays_included(self, tag: str) -> None:
        """Ein Schild, eine Karte oder ein Bildschirm im Hintergrund ist ein Tag, keine Fotoart."""
        assert is_excluded(_payload(kind="photo", tags={tag: 0.95}), MAPPING_V2) is False

    @_BOTH
    def test_an_unknown_type_excludes_nothing(self, mapping: EyeMapping) -> None:
        assert is_excluded(_payload(kind="landscape"), mapping) is False

    @_BOTH
    def test_a_missing_type_excludes_nothing(self, mapping: EyeMapping) -> None:
        """Die Abwesenheit einer Typangabe ist keine Dokumentaussage."""
        payload = _payload()
        del payload["kind"]

        assert is_excluded(payload, mapping) is False

    @_BOTH
    @pytest.mark.parametrize("kind", [42, None, ["document"], {"document": 1}, True])
    def test_a_non_string_type_excludes_nothing(self, mapping: EyeMapping, kind: Any) -> None:
        assert is_excluded(_payload(kind=kind), mapping) is False

    def test_the_type_match_is_exact(self) -> None:
        assert is_excluded(_payload(kind="Document"), MAPPING_V2) is False
        assert is_excluded(_payload(kind="document "), MAPPING_V2) is False


class TestTheAlbumLevel:
    @_BOTH
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
        self, mapping: EyeMapping, note: float, level: int
    ) -> None:
        assert album_level(_payload(scores={"aesthetic": note}), mapping) == level

    def test_a_missing_aesthetic_score_is_an_error_not_a_default(self) -> None:
        """Eine erfundene Stufe waere eine Aussage, die das Modell nie getroffen hat."""
        with pytest.raises(EyeMappingError):
            album_level(_payload(scores={"keeper": 0.6}), MAPPING_V2)

    def test_a_missing_scores_object_is_an_error(self) -> None:
        payload = _payload()
        del payload["scores"]

        with pytest.raises(EyeMappingError):
            album_level(payload, MAPPING_V2)

    def test_a_non_numeric_aesthetic_score_is_an_error(self) -> None:
        with pytest.raises(EyeMappingError):
            album_level(_payload(scores={"aesthetic": "gut"}), MAPPING_V2)

    def test_a_score_outside_the_scale_is_clamped(self) -> None:
        assert album_level(_payload(scores={"aesthetic": 1.7}), MAPPING_V2) == 5
        assert album_level(_payload(scores={"aesthetic": -0.4}), MAPPING_V2) == 1


class TestTheFineLabels:
    def test_only_tags_from_the_threshold_on_appear(self) -> None:
        labels = fine_labels(_payload(), MAPPING_V2)

        assert [label for label, _ in labels] == ["mountain", "sky"]

    def test_the_threshold_is_inclusive(self) -> None:
        assert fine_labels(_payload(tags={"mountain": 0.5}), MAPPING_V2) == (("mountain", 0.5),)
        assert fine_labels(_payload(tags={"mountain": 0.4999}), MAPPING_V2) == ()

    def test_the_strongest_come_first_and_ties_are_alphabetical(self) -> None:
        labels = fine_labels(
            _payload(tags={"sky": 0.6, "mountain": 0.9, "beach": 0.6, "food": 0.7}), MAPPING_V2
        )

        assert [label for label, _ in labels] == ["mountain", "food", "beach", "sky"]

    @_BOTH
    def test_the_photo_types_are_not_fine_labels(self, mapping: EyeMapping) -> None:
        """Eine Fotoart ist keine Bildinhaltsaussage - als Feinlabel stuende sie neben dem
        Ausschluss ein zweites Mal."""
        labels = fine_labels(_payload(tags={"document": 0.9, "mountain": 0.7}), mapping)

        assert [label for label, _ in labels] == ["mountain"]

    def test_the_values_are_the_raw_confidences(self) -> None:
        labels = fine_labels(_payload(tags={"mountain": 0.73}), MAPPING_V2)

        assert labels == (("mountain", 0.73),)


class TestTheWholeMapping:
    def test_analyze_returns_all_four_answers(self) -> None:
        analysis = analyze(
            _payload(kind="document", scores={"aesthetic": 0.75}, pets=[_pet(0.66)]),
            MAPPING_VERSION,
        )

        assert analysis.excluded_document is True
        assert analysis.album_level == 4
        assert analysis.motif_strengths["landschaft"] == pytest.approx(0.91)
        assert analysis.motif_strengths["tiere"] == pytest.approx(0.66)
        assert analysis.fine_labels == (("mountain", 0.91), ("sky", 0.7))

    def test_the_run_version_is_v2_and_v1_stays_callable(self) -> None:
        assert MAPPING_VERSION == "eye-4.2.3/v2"
        assert MAPPING_VERSION_V1 == "eye-4.2.3/v1"
        assert list(MAPPINGS) == [MAPPING_VERSION_V1, MAPPING_VERSION]
        assert MAPPINGS[MAPPING_VERSION_V1] is MAPPING_V1
        assert MAPPINGS[MAPPING_VERSION] is MAPPING_V2
        assert MODEL_REVISION == "v1.0.0"

    def test_analyze_requires_the_version(self) -> None:
        """Ohne Default: wer `analyze` ruft, nennt die Fassung, mit der das Ergebnis entsteht."""
        with pytest.raises(TypeError):
            analyze(_payload())  # type: ignore[call-arg]

    def test_the_published_description_is_the_run_version(self) -> None:
        purposes = EYE_PURPOSE_MAPPING["purposes"]

        assert EYE_PURPOSE_MAPPING["version"] == MAPPING_VERSION
        assert EYE_PURPOSE_MAPPING["model_revision"] == MODEL_REVISION
        assert purposes["motivstaerken"]["motifs"] == MAPPING_V2.motif_tags
        assert purposes["motivstaerken"]["detections"] == MAPPING_V2.motif_detections
        assert set(purposes["motivstaerken"]["signals"]) == {"tags", "pets"}
        assert purposes["ausschluss"]["excluded_types"] == MAPPING_V2.excluded_types
        assert purposes["feinlabels"]["excluded_types"] == MAPPING_V2.fine_label_excluded


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
            if not name.startswith(
                ("collections", "dataclasses", "math", "types", "typing", "__future__")
            )
            and name != "photosort.motifs"
        }
        assert foreign == set()


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PINS_FILE = _REPO_ROOT / "eye" / "src" / "pins.json"


def _all_table_tags() -> set[str]:
    return {
        tag for mapping in MAPPINGS.values() for tags in mapping.motif_tags.values() for tag in tags
    }


class TestTheTagsAgainstTheSidecarPins:
    """Die Tag-Liste steht in DREI Fassungen, und alle drei muessen gleich sein: die Vereinigung
    der Tabellen ALLER aufrufbaren Fassungen, `mappingTags` in `eye/src/pins.json` und das
    SDK-Vokabular aus `tags.js`.

    Grund fuer die Pins-Fassung: das Modell ist gepinnt, das Vokabular ist es damit auch. Ein
    Pin-Wechsel, der einen Tag umbenennt, faellt dann hier auf und nicht als stille Null in jedem
    Eye-Ergebnis - auch fuer eine Fassung, mit der nur noch die Pruefung rechnet. Der Abgleich
    gegen `tags.js` selbst laeuft in `eye/test/tags.test.js`, wo die SDK ohnehin Abhaengigkeit
    ist; dieses Modul bleibt frei von Node.
    """

    def test_the_union_of_all_tables_equals_the_pins(self) -> None:
        pins = json.loads(_PINS_FILE.read_text(encoding="utf-8"))
        table = _all_table_tags()
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
        for tag in _all_table_tags():
            assert tag == tag.lower()
            assert " " not in tag


@pytest.mark.skipif(
    not Path(os.environ.get("EYE_META_PATH", "eye_model/eye_meta.json")).exists(),
    reason="eye_meta.json liegt ausserhalb des Repos - Heimserver-Schritt",
)
def test_every_photo_type_exists_in_eye_meta() -> None:
    """Heimserver-Schritt (0002): Ausschluss und Feinlabel-Filter haengen an `labels.type` des
    echten Modells. Die Motiv-Tags lassen sich dort NICHT abgleichen - `labels.scenes` fuehrt
    Anzeigenamen ("Sky"), die SDK-Antwort snake_case-Tags ("sky"); dieser Abgleich laeuft in
    eye/test/tags.test.js."""
    meta = json.loads(
        Path(os.environ.get("EYE_META_PATH", "eye_model/eye_meta.json")).read_text(encoding="utf-8")
    )
    known = set(meta["labels"]["type"])

    for mapping in MAPPINGS.values():
        assert mapping.excluded_types - known == set()
        assert mapping.fine_label_excluded - known == set()


class TestTheVersionedMappings:
    """Spec 0616, ADR 0139 Punkt 4: die Pruefseite speichert je Seite die Abbildungsfassung, mit
    der sie gerechnet wurde. Eine gespeicherte Fassung muss deshalb AUFRUFBAR bleiben - und eine
    unbekannte Fassung darf nicht still die Lauf-Fassung rechnen."""

    @pytest.mark.parametrize("version", list(MAPPINGS))
    def test_every_registered_version_produces_an_analysis(self, version: str) -> None:
        result = analyze(_payload(), version)

        assert set(result.motif_strengths) == set(MOTIF_REGISTRY)
        assert 1 <= result.album_level <= 5

    def test_the_versions_differ_where_v2_is_meant_to_differ(self) -> None:
        payload = _payload(kind="map", tags={"hiking": 0.8}, pets=[_pet(0.7)])

        v1 = analyze(payload, MAPPING_VERSION_V1)
        v2 = analyze(payload, MAPPING_VERSION)

        assert (v1.excluded_document, v2.excluded_document) == (True, False)
        assert (v1.motif_strengths["tiere"], v2.motif_strengths["tiere"]) == (0.0, 0.7)
        assert v1.motif_strengths["aktivitaet"] == 0.0
        assert v2.motif_strengths["aktivitaet"] == pytest.approx(0.8)

    @pytest.mark.parametrize("version", ["eye-0.0.0/v1", "", "EYE-4.2.3/V2"])
    def test_an_unknown_version_raises_instead_of_falling_back(self, version: str) -> None:
        with pytest.raises(EyeMappingError):
            analyze(_payload(), version)
