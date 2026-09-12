"""specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 1 - Muster `test_categories.py`.

DB-frei und netzfrei wie das Modul selbst. Vier Nachweise tragen mehr als eine Werteprüfung:

* Die Registry trägt KEIN Ordnungsattribut - geprüft über die Felder des Eintrags, nicht über
  einen Namen: ein `rank` hieße sonst nur anders und die Vorrangreihenfolge wäre zurück.
* `LOCAL_MOTIF_SIGNALS` wird gegen `criteria.py`/`MOTIF_REGISTRY` ABGELEITET geprüft, nicht gegen
  eine zweite Liste in diesem Modul.
* Die Sättigungsgrenze ist ein PAAR (genau auf dem Anteil → 1.0, nächstkleinerer darstellbarer
  Wert → < 1.0). Einzeln bestünden beide Assertions auch bei einer verschobenen Grenze.
* Die Abbildungstabelle der dreizehn heutigen Kategorieschlüssel ist hier maschinell auf
  Vollständigkeit und Eindeutigkeit geprüft, statt nur in ADR 0091 zu stehen.
"""

from __future__ import annotations

import math
from dataclasses import fields

import pytest

from photosort.criteria import CRITERIA_REGISTRY
from photosort.motifs import (
    EXCLUSION_KEY,
    LOCAL_MOTIF_SIGNALS,
    MOTIF_REGISTRY,
    MOTIF_STRENGTH_BAND_MEDIUM,
    MOTIF_STRENGTH_BAND_STRONG,
    MotifDefinition,
    build_motif_prompt,
    is_motif_key,
    local_motif_strengths,
)

_EXPECTED_MOTIF_KEYS = (
    "menschen",
    "landschaft",
    "bauwerk_sehenswuerdigkeit",
    "stadt_strasse",
    "tiere",
    "essen_trinken",
    "aktivitaet",
    "detail_stimmung",
)

# Die beiden Motive, die ohne Cloud-Aussage strukturell nicht erreichbar sind (ADR 0091 Punkt 4) -
# bewusst akzeptierte Grenze, kein Fehlerfall.
_LOCALLY_UNASSESSABLE = ("aktivitaet", "detail_stimmung")

# Die dreizehn Schlüssel des abgelösten Kategorien-Sets, in seiner damaligen
# Anzeigereihenfolge. Eingefrorener historischer Stand: `categories.py` ist seit PR 3 gelöscht,
# und diese Liste wächst nie wieder.
_THIRTEEN_LEGACY_CATEGORY_KEYS: tuple[str, ...] = (
    "menschen",
    "tier",
    "landschaft",
    "gebaeude_bauwerk",
    "essen_trinken",
    "sport_aktivitaet",
    "fahrzeug",
    "pflanze",
    "gegenstand",
    "kunst_kreatives",
    "innenraum",
    "dokument_screenshot",
    "nicht_erkannt",
)

# Die Abbildung dieser dreizehn Kategorieschlüssel auf das Motivset (ADR 0091 Punkt 1).
# `None` heißt "entfällt"; die Begründung steht je Eintrag daneben. Dass jeder Schlüssel GENAU
# EINMAL vorkommt, ist eine Eigenschaft des Dicts; dass keiner fehlt, prüft der Test unten.
_LEGACY_CATEGORY_TO_MOTIF: dict[str, str | None] = {
    "menschen": "menschen",
    "tier": "tiere",
    "landschaft": "landschaft",
    "gebaeude_bauwerk": "bauwerk_sehenswuerdigkeit",
    "essen_trinken": "essen_trinken",
    "sport_aktivitaet": "aktivitaet",
    # Ein Fahrzeug ist Teil der Straßenszene und kein eigenes Motiv.
    "fahrzeug": "stadt_strasse",
    "pflanze": "detail_stimmung",
    "gegenstand": "detail_stimmung",
    "kunst_kreatives": "detail_stimmung",
    # Ein Innenraum ist ein Aufnahmeort, kein Motiv - das Foto trägt die Motive dessen, was darin
    # zu sehen ist.
    "innenraum": None,
    # Kein erkennbares Motiv heißt durchgehend niedrige Stärken, es gibt keine Auffangkategorie.
    "nicht_erkannt": None,
    # Kein Motiv mehr, sondern das Ausschluss-Signal (EXCLUSION_KEY).
    "dokument_screenshot": None,
}


class TestTheRegistry:
    def test_there_are_exactly_eight_motifs_in_display_order(self) -> None:
        assert tuple(MOTIF_REGISTRY) == _EXPECTED_MOTIF_KEYS

    def test_every_entry_is_keyed_by_its_own_key(self) -> None:
        for key, definition in MOTIF_REGISTRY.items():
            assert definition.key == key

    def test_every_entry_carries_a_display_name_a_definition_and_a_delimitation(self) -> None:
        for definition in MOTIF_REGISTRY.values():
            assert definition.display_name.strip()
            assert definition.definition.strip()
            assert definition.delimitation.strip()

    def test_the_registry_entry_has_no_ordering_attribute_at_all(self) -> None:
        """Über die FELDER des Eintrags geprüft, nicht über den Namen `precedence`: ein
        Ordnungsattribut unter anderem Namen wäre dieselbe Vorrangreihenfolge zurück, und die
        schafft dieses Motivset ab."""
        assert {field.name for field in fields(MotifDefinition)} == {
            "key",
            "display_name",
            "definition",
            "delimitation",
        }

    def test_no_field_of_an_entry_is_numeric(self) -> None:
        """Zweite Hälfte desselben Nachweises: kein Zahlenfeld, aus dem eine Ordnung entstehen
        könnte - unabhängig davon, wie es hieße."""
        for definition in MOTIF_REGISTRY.values():
            for field in fields(MotifDefinition):
                assert isinstance(getattr(definition, field.name), str), field.name


class TestTheExclusionKey:
    def test_the_exclusion_key_is_not_a_motif(self) -> None:
        assert EXCLUSION_KEY == "dokument_screenshot"
        assert EXCLUSION_KEY not in MOTIF_REGISTRY

    def test_the_exclusion_key_is_not_a_valid_correction_key(self) -> None:
        """Der tragende Fall: `dokument_screenshot` darf über keine Registry-Iteration in den
        Prüfraum der Korrektur-Endpunkte geraten - der Ausschluss ist nicht von Hand
        korrigierbar."""
        assert is_motif_key(EXCLUSION_KEY) is False


class TestIsMotifKey:
    @pytest.mark.parametrize("key", _EXPECTED_MOTIF_KEYS)
    def test_every_registry_key_is_accepted(self, key: str) -> None:
        assert is_motif_key(key) is True

    @pytest.mark.parametrize(
        "key",
        [
            "",
            "Menschen",
            "MENSCHEN",
            " menschen",
            "menschen ",
            "menschen\n",
            "mensch",
            "menschenX",
            # Entfallene Kategorieschlüssel - ein aus der Laufhistorie bekannter Wert.
            "pflanze",
            "innenraum",
            "nicht_erkannt",
            "tier",
            "gebaeude_bauwerk",
            "sport_aktivitaet",
        ],
    )
    def test_unknown_or_differently_written_values_are_rejected(self, key: str) -> None:
        """Keine Normalisierung, kein Präfixvergleich: ein anders geschriebener Schlüssel ist
        ungültig, nicht "fast richtig"."""
        assert is_motif_key(key) is False


class TestTheLegacyCategoryMapping:
    def test_the_table_lists_every_one_of_the_thirteen_category_keys_exactly_once(self) -> None:
        """Vollständigkeit gegen die dreizehn Schlüssel, die das abgelöste Set TATSÄCHLICH trug.

        Seit PR 3 ist `categories.py` gelöscht; die Liste steht deshalb hier als eingefrorener
        historischer Stand statt als Ableitung aus einer Registry, die es nicht mehr gibt. Sie
        wird nie wieder wachsen - die Abbildungstabelle ist die Buchführung eines einmaligen
        Übergangs (Akzeptanzkriterium "keine verschwindet unbemerkt"), kein lebendes Register."""
        assert set(_LEGACY_CATEGORY_TO_MOTIF) == set(_THIRTEEN_LEGACY_CATEGORY_KEYS)
        assert len(_LEGACY_CATEGORY_TO_MOTIF) == 13
        assert len(set(_THIRTEEN_LEGACY_CATEGORY_KEYS)) == 13

    def test_every_target_is_either_a_real_motif_or_an_explicit_omission(self) -> None:
        for category_key, motif_key in _LEGACY_CATEGORY_TO_MOTIF.items():
            assert motif_key is None or is_motif_key(motif_key), category_key

    def test_the_omitted_categories_are_exactly_the_three_named_ones(self) -> None:
        omitted = {key for key, value in _LEGACY_CATEGORY_TO_MOTIF.items() if value is None}

        assert omitted == {"innenraum", "nicht_erkannt", "dokument_screenshot"}

    def test_the_document_category_becomes_the_exclusion_signal(self) -> None:
        """Es entfällt nicht ersatzlos: derselbe Schlüssel ist ab hier das Ausschluss-Signal."""
        assert _LEGACY_CATEGORY_TO_MOTIF[EXCLUSION_KEY] is None
        assert EXCLUSION_KEY in _THIRTEEN_LEGACY_CATEGORY_KEYS


class TestTheLocalSignalRegistry:
    def test_it_references_only_existing_motif_keys(self) -> None:
        for motif_key in LOCAL_MOTIF_SIGNALS:
            assert is_motif_key(motif_key), motif_key

    def test_it_references_only_existing_criterion_keys(self) -> None:
        """ABGELEITET gegen `criteria.py::CRITERIA_REGISTRY` geprüft statt gegen eine zweite Liste
        hier - das Modul importiert `criteria.py` bewusst nicht."""
        for motif_key, signal in LOCAL_MOTIF_SIGNALS.items():
            for criterion_key in signal.criterion_keys:
                assert criterion_key in CRITERIA_REGISTRY, (motif_key, criterion_key)

    def test_every_signal_names_at_least_one_criterion(self) -> None:
        for motif_key, signal in LOCAL_MOTIF_SIGNALS.items():
            assert signal.criterion_keys, motif_key

    def test_a_saturation_fraction_exists_exactly_for_the_area_weighted_signals(self) -> None:
        for motif_key, signal in LOCAL_MOTIF_SIGNALS.items():
            assert (signal.saturation_fraction is not None) == (signal.kind == "area"), motif_key

    def test_every_saturation_fraction_is_strictly_greater_than_zero(self) -> None:
        """Invariante, nicht Kosmetik: eine 0 wäre eine Division durch Null im Schreibpfad des
        Stärkevektors."""
        for motif_key, signal in LOCAL_MOTIF_SIGNALS.items():
            if signal.saturation_fraction is not None:
                assert signal.saturation_fraction > 0, motif_key
                assert math.isfinite(signal.saturation_fraction), motif_key

    def test_the_two_locally_unassessable_motifs_are_absent(self) -> None:
        for motif_key in _LOCALLY_UNASSESSABLE:
            assert motif_key not in LOCAL_MOTIF_SIGNALS

    def test_the_landmark_signal_only_strengthens_the_building_motif(self) -> None:
        """Eine erkannte Sehenswürdigkeit ist kein eigenes Motiv."""
        carrying = {
            motif_key
            for motif_key, signal in LOCAL_MOTIF_SIGNALS.items()
            if "landmark" in signal.criterion_keys
        }

        assert carrying == {"bauwerk_sehenswuerdigkeit"}


class TestLocalMotifStrengths:
    def test_it_returns_all_eight_motifs_in_registry_order(self) -> None:
        result = local_motif_strengths({}, {})

        assert tuple(result) == _EXPECTED_MOTIF_KEYS

    def test_without_any_detection_all_eight_strengths_are_zero(self) -> None:
        """Eine lokale Beurteilung ohne Fund ist acht Nullen - und damit etwas anderes als eine
        fehlende Beurteilung."""
        assert set(local_motif_strengths({}, {}).values()) == {0.0}

    @pytest.mark.parametrize("motif_key", _LOCALLY_UNASSESSABLE)
    def test_a_locally_unassessable_motif_is_zero_in_every_conceivable_input(
        self, motif_key: str
    ) -> None:
        """In KEINEM Aufbau > 0: alle Kriterien auf 1.0, alle Flächenanteile auf 1.0."""
        criterion_values = dict.fromkeys(CRITERIA_REGISTRY, 1.0)
        area_fractions = dict.fromkeys(CRITERIA_REGISTRY, 1.0)

        result = local_motif_strengths(criterion_values, area_fractions)

        assert result[motif_key] == 0.0

    def test_every_value_stays_within_zero_and_one(self) -> None:
        result = local_motif_strengths(
            dict.fromkeys(CRITERIA_REGISTRY, 1.0),
            # Überlappende Boxen summieren über 1 hinaus - das Ergebnis bleibt geklemmt.
            dict.fromkeys(CRITERIA_REGISTRY, 1.0),
        )

        for motif_key, value in result.items():
            assert 0.0 <= value <= 1.0, motif_key

    def test_a_scene_signal_is_taken_as_the_whole_image_confidence(self) -> None:
        result = local_motif_strengths({"landschaft": 0.42}, {})

        assert result["landschaft"] == pytest.approx(0.42)

    def test_a_scene_signal_is_not_area_weighted(self) -> None:
        """Gegenprobe: ein Flächenanteil desselben Kriterien-Schlüssels ändert einen
        Szenen-Wert nicht."""
        without = local_motif_strengths({"landschaft": 0.42}, {})
        with_area = local_motif_strengths({"landschaft": 0.42}, {"landschaft": 0.9})

        assert without == with_area

    def test_the_building_motif_is_the_maximum_of_scene_and_landmark_confidence(self) -> None:
        assert local_motif_strengths({"gebaeude": 0.8, "landmark": 0.3}, {})[
            "bauwerk_sehenswuerdigkeit"
        ] == pytest.approx(0.8)
        assert local_motif_strengths({"gebaeude": 0.3, "landmark": 0.8}, {})[
            "bauwerk_sehenswuerdigkeit"
        ] == pytest.approx(0.8)

    def test_the_building_motif_does_not_add_the_two_confidences_up(self) -> None:
        """Kein erfundenes Summenmaß: zwei mittlere Konfidenzen ergeben nicht eine hohe."""
        result = local_motif_strengths({"gebaeude": 0.5, "landmark": 0.5}, {})

        assert result["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.5)

    def test_an_area_weighted_motif_grows_monotonically_with_the_covered_area(self) -> None:
        """Der Kern der Story: ein bildfüllender Hund ergibt eine hohe Tier-Stärke, ein Hund am
        Bildrand eine niedrige."""
        small = local_motif_strengths({}, {"tier": 0.01})["tiere"]
        medium = local_motif_strengths({}, {"tier": 0.1})["tiere"]
        large = local_motif_strengths({}, {"tier": 0.2})["tiere"]

        assert 0.0 < small < medium < large

    def test_an_area_weighted_motif_ignores_the_plain_criterion_confidence(self) -> None:
        """Gegenprobe zur Monotonie: die bloße Anwesenheit (Konfidenz ohne Fläche) wirkt nicht."""
        result = local_motif_strengths({"tier": 0.99}, {})

        assert result["tiere"] == 0.0

    def test_the_saturation_fraction_is_reached_inclusively(self) -> None:
        saturation = LOCAL_MOTIF_SIGNALS["tiere"].saturation_fraction
        assert saturation is not None

        assert local_motif_strengths({}, {"tier": saturation})["tiere"] == pytest.approx(1.0)

    def test_just_below_the_saturation_fraction_the_strength_stays_below_one(self) -> None:
        """Die zweite Hälfte des Paars - ohne sie bestünde die Assertion oben auch bei einer
        verschobenen Grenze."""
        saturation = LOCAL_MOTIF_SIGNALS["tiere"].saturation_fraction
        assert saturation is not None

        just_below = math.nextafter(saturation, 0.0)

        assert local_motif_strengths({}, {"tier": just_below})["tiere"] < 1.0

    def test_beyond_the_saturation_fraction_the_strength_is_clamped(self) -> None:
        assert local_motif_strengths({}, {"tier": 1.0})["tiere"] == 1.0

    def test_area_fractions_of_one_allow_list_are_summed_not_maximised(self) -> None:
        """Der Aufrufer liefert je Allow-Liste EINEN, bereits summierten Anteil - fünf kleine
        Personen sind ein Personenbild. Geprüft über zwei Kriterien desselben Motivs gibt es hier
        nicht; geprüft wird, dass der gelieferte Summenanteil unverändert wirkt."""
        saturation = LOCAL_MOTIF_SIGNALS["menschen"].saturation_fraction
        assert saturation is not None

        result = local_motif_strengths({}, {"content_people": saturation / 2})

        assert result["menschen"] == pytest.approx(0.5)

    @pytest.mark.parametrize("degenerate", [None, "0.7", float("nan"), float("inf"), True, -0.5])
    def test_a_degenerate_area_fraction_is_discarded_not_clamped(self, degenerate: object) -> None:
        """`NaN` würde jeden Vergleich zu `False` machen, in die `double precision`-Spalte
        wandern und die gesamte Fotoliste des Projekts auf `500` legen (Starlette rendert mit
        `allow_nan=False`). `True` erschiene als die stärkste Aussage, die das Produkt kennt."""
        result = local_motif_strengths({}, {"tier": degenerate})  # type: ignore[dict-item]

        assert result["tiere"] == 0.0

    @pytest.mark.parametrize("degenerate", [None, "0.7", float("nan"), float("inf"), True, -0.5])
    def test_a_degenerate_scene_confidence_is_discarded_too(self, degenerate: object) -> None:
        result = local_motif_strengths({"landschaft": degenerate}, {})  # type: ignore[dict-item]

        assert result["landschaft"] == 0.0

    def test_a_value_above_one_is_clamped_before_it_reaches_the_scene_motif(self) -> None:
        result = local_motif_strengths({"landschaft": 1.5}, {})

        assert result["landschaft"] == 1.0

    def test_the_input_mappings_are_not_mutated(self) -> None:
        criterion_values = {"landschaft": 0.4}
        area_fractions = {"tier": 0.1}

        local_motif_strengths(criterion_values, area_fractions)

        assert criterion_values == {"landschaft": 0.4}
        assert area_fractions == {"tier": 0.1}


class TestTheStrengthBands:
    def test_the_two_band_limits_are_two_thirds_and_one_third(self) -> None:
        assert MOTIF_STRENGTH_BAND_STRONG == 2 / 3
        assert MOTIF_STRENGTH_BAND_MEDIUM == 1 / 3

    def test_the_strong_limit_lies_above_the_medium_limit(self) -> None:
        assert MOTIF_STRENGTH_BAND_STRONG > MOTIF_STRENGTH_BAND_MEDIUM

    def test_both_limits_lie_inside_the_strength_range(self) -> None:
        assert 0.0 < MOTIF_STRENGTH_BAND_MEDIUM < MOTIF_STRENGTH_BAND_STRONG < 1.0


class TestBuildMotifPrompt:
    def test_the_prompt_names_every_motif_with_key_definition_and_delimitation(self) -> None:
        prompt = build_motif_prompt(max_fine_labels=2)

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

        prompt = build_motif_prompt(max_fine_labels=2)

        assert "Voelklein" in prompt
        assert "Testdefinition." in prompt
        assert "Testabgrenzung." in prompt

    def test_the_prompt_asks_for_a_number_for_every_motif(self) -> None:
        prompt = build_motif_prompt(max_fine_labels=2)

        assert '"motifs"' in prompt
        assert "zwischen 0 und 1" in prompt

    def test_the_prompt_asks_for_the_exclusion_flag_as_a_real_boolean(self) -> None:
        prompt = build_motif_prompt(max_fine_labels=2)

        assert '"excluded"' in prompt
        assert "true oder false" in prompt

    def test_the_prompt_carries_the_fine_label_limit_it_was_given(self) -> None:
        assert "hoechstens 2 kurze" in build_motif_prompt(max_fine_labels=2)
        assert "hoechstens 5 kurze" in build_motif_prompt(max_fine_labels=5)

    def test_the_prompt_never_names_a_main_category_or_a_precedence(self) -> None:
        """Die abgeschaffte Mechanik darf nicht über den Prompt zurückkommen."""
        prompt = build_motif_prompt(max_fine_labels=2).lower()

        assert "hauptkategorie" not in prompt
        assert "vorrang" not in prompt
        assert "nicht_erkannt" not in prompt

    def test_the_prompt_does_not_offer_the_exclusion_key_as_a_motif(self) -> None:
        prompt = build_motif_prompt(max_fine_labels=2)

        assert f'"{EXCLUSION_KEY}"' not in prompt
