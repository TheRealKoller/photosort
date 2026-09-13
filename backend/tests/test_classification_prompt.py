"""specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 2.

Der Prompt-Bau zieht als Ganzes aus `motifs.py` hierher um - `motifs.py` bleibt reines
Registermodul und weiss nichts ueber die Antwortform des Anbieters. Der Umzug ist
VERHALTENSERHALTEND: die Faelle von `TestBuildMotifPrompt` stehen unveraendert in
`TestBuildClassificationPrompt` darunter, mit denselben Namen und denselben Assertions, nur gegen
den neuen Funktionsnamen. Neu geprueft wird allein der Albumtauglichkeits-Block.
"""

from __future__ import annotations

import pytest

from photosort.album_suitability import (
    ALBUM_SUITABILITY_ANCHORS,
    ALBUM_SUITABILITY_MAX_LEVEL,
    ALBUM_SUITABILITY_MIN_LEVEL,
    ALBUM_SUITABILITY_NAMED_FLAWS,
)
from photosort.classification_prompt import build_classification_prompt
from photosort.motifs import EXCLUSION_KEY, MOTIF_REGISTRY, MotifDefinition


class TestBuildClassificationPrompt:
    def test_the_prompt_names_every_motif_with_key_definition_and_delimitation(self) -> None:
        prompt = build_classification_prompt(max_fine_labels=2)

        for definition in MOTIF_REGISTRY.values():
            assert f'"{definition.key}"' in prompt
            assert definition.display_name in prompt
            assert definition.definition in prompt
            assert definition.delimitation in prompt

    def test_the_prompt_is_generated_from_the_registry_not_a_literal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SICHERHEIT (S8): eine veränderte Registry MUSS den Prompt verändern - sonst steht das
        Motivset ein zweites Mal in einem Literal."""
        monkeypatch.setitem(
            MOTIF_REGISTRY,
            "menschen",
            MotifDefinition(
                key="menschen",
                display_name="Voelklein",
                definition="Testdefinition.",
                delimitation="Testabgrenzung.",
            ),
        )

        prompt = build_classification_prompt(max_fine_labels=2)

        assert "Voelklein" in prompt
        assert "Testdefinition." in prompt
        assert "Testabgrenzung." in prompt

    def test_the_prompt_asks_for_a_number_for_every_motif(self) -> None:
        prompt = build_classification_prompt(max_fine_labels=2)

        assert '"motifs"' in prompt
        assert "zwischen 0 und 1" in prompt

    def test_the_prompt_asks_for_the_exclusion_flag_as_a_real_boolean(self) -> None:
        prompt = build_classification_prompt(max_fine_labels=2)

        assert '"excluded"' in prompt
        assert "true oder false" in prompt

    def test_the_prompt_carries_the_fine_label_limit_it_was_given(self) -> None:
        assert "hoechstens 2 kurze" in build_classification_prompt(max_fine_labels=2)
        assert "hoechstens 5 kurze" in build_classification_prompt(max_fine_labels=5)

    def test_the_prompt_never_names_a_main_category_or_a_precedence(self) -> None:
        """Die abgeschaffte Mechanik darf nicht über den Prompt zurückkommen."""
        prompt = build_classification_prompt(max_fine_labels=2).lower()

        assert "hauptkategorie" not in prompt
        assert "vorrang" not in prompt
        assert "nicht_erkannt" not in prompt

    def test_the_prompt_does_not_offer_the_exclusion_key_as_a_motif(self) -> None:
        prompt = build_classification_prompt(max_fine_labels=2)

        assert f'"{EXCLUSION_KEY}"' not in prompt


class TestTheAlbumSuitabilityPart:
    def test_the_prompt_carries_all_five_anchor_texts(self) -> None:
        prompt = build_classification_prompt(max_fine_labels=2)

        for text in ALBUM_SUITABILITY_ANCHORS.values():
            assert text in prompt

    def test_the_prompt_names_the_four_flaws_local_measurements_cannot_see(self) -> None:
        prompt = build_classification_prompt(max_fine_labels=2).lower()

        for flaw in ALBUM_SUITABILITY_NAMED_FLAWS:
            assert flaw.lower() in prompt

    def test_the_prompt_names_the_limits_of_the_scale(self) -> None:
        prompt = build_classification_prompt(max_fine_labels=2)

        assert str(ALBUM_SUITABILITY_MIN_LEVEL) in prompt
        assert str(ALBUM_SUITABILITY_MAX_LEVEL) in prompt

    def test_the_album_block_is_generated_from_the_anchors_not_from_a_literal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SICHERHEIT (S4): der Prompt entsteht ausschliesslich aus dem Code - aus der Registry
        und den fuenf festen Stufenankern, nie aus einem Literal daneben."""
        monkeypatch.setitem(ALBUM_SUITABILITY_ANCHORS, 5, "Testanker fuenf.")

        assert "Testanker fuenf." in build_classification_prompt(max_fine_labels=2)

    def test_the_json_form_names_the_album_suitability_object_with_both_fields(self) -> None:
        """Die Formzeile ist die EINE Stelle, an der das Modell die Antwortform abliest - fehlt
        das Feld dort, liefert es keines, und die Nachbewertung liefe kostenpflichtig ins Leere."""
        prompt = build_classification_prompt(max_fine_labels=2)
        form_line = prompt.rsplit("\n", maxsplit=1)[-1]

        assert '"album_suitability"' in form_line
        assert '"level"' in form_line
        assert '"reason"' in form_line

    def test_the_album_block_is_not_a_second_motif(self) -> None:
        """Die Albumtauglichkeit ist eine Aussage ueber die Bildguete, keine Motivstaerke (ADR
        0091 bleibt unberuehrt) - sie darf im Motivblock nicht als Schluessel auftauchen."""
        prompt = build_classification_prompt(max_fine_labels=2)
        motif_block = prompt.split("Die Motive")[1].split("Nenne zu JEDEM")[0]

        assert "album_suitability" not in motif_block
