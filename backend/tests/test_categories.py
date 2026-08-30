from __future__ import annotations

import itertools

import pytest

from photosort.categories import (
    CATEGORY_NOT_RECOGNIZED,
    CATEGORY_REGISTRY,
    LOCAL_CATEGORY_SIGNALS,
    MAX_FINE_LABELS_PER_PHOTO,
    MAX_REMOTE_CATEGORIES_PER_PHOTO,
    CategoryDefinition,
    build_classification_prompt,
    is_known_category,
    resolve_category,
)
from photosort.criteria import CRITERIA_REGISTRY

# specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 1-3: der fachliche Kern dieser
# Spec ist eine REINE FUNKTION ueber einer geschlossenen Datenstruktur - der Testschwerpunkt liegt
# deshalb hier auf Unit-Ebene, nicht auf der Worker-Integration.


# Die zwoelf echten Kategorien (ohne den Auffangwert) - Grundlage der parametrisierten Paartests.
_REAL_CATEGORY_KEYS = tuple(
    key for key, definition in CATEGORY_REGISTRY.items() if definition.precedence is not None
)


class TestResolveCategory:
    @pytest.mark.parametrize(
        ("first", "second"), list(itertools.permutations(_REAL_CATEGORY_KEYS, 2))
    )
    def test_the_smaller_precedence_wins_for_every_ordered_pair(
        self, first: str, second: str
    ) -> None:
        """Vorrang paarweise UND vollstaendig (Teststrategie 1): alle Paare in BEIDEN Richtungen,
        die Erwartung aus der Registry abgeleitet - der Test wandert bei einer kuenftigen
        Umsortierung mit, statt zu einer gepflegten zweiten Liste zu werden."""
        first_precedence = CATEGORY_REGISTRY[first].precedence
        second_precedence = CATEGORY_REGISTRY[second].precedence
        assert first_precedence is not None and second_precedence is not None
        expected = first if first_precedence < second_precedence else second

        assert resolve_category([first, second]) == expected
        assert resolve_category([second, first]) == expected

    def test_sport_aktivitaet_beats_menschen(self) -> None:
        """Die einzige kontraintuitive Regel des Sets ist eine PRODUKTENTSCHEIDUNG und bekommt
        deshalb einen eigenen, literalen Testfall (Teststrategie 1) - sie darf nicht stillschweigend
        mit einer Umsortierung der Registry kippen."""
        assert resolve_category({"menschen", "sport_aktivitaet"}) == "sport_aktivitaet"

    def test_resolves_three_candidates_by_the_smallest_precedence(self) -> None:
        assert (
            resolve_category({"landschaft", "menschen", "dokument_screenshot"})
            == "dokument_screenshot"
        )

    def test_empty_candidate_set_resolves_to_not_recognized(self) -> None:
        assert resolve_category([]) == CATEGORY_NOT_RECOGNIZED
        assert resolve_category(set()) == CATEGORY_NOT_RECOGNIZED

    def test_unknown_values_are_ignored_not_rejected(self) -> None:
        assert resolve_category({"einhorn"}) == CATEGORY_NOT_RECOGNIZED
        assert resolve_category({"einhorn", "tier"}) == "tier"

    def test_no_case_or_whitespace_fallback(self) -> None:
        """Abweichende Gross-/Kleinschreibung ist KEIN gueltiger Key (Teststrategie 1) - der Client
        schickt den Key exakt so zurueck, wie GET /categories ihn geliefert hat."""
        assert resolve_category({"", "  ", "TIER"}) == CATEGORY_NOT_RECOGNIZED

    def test_not_recognized_alone_is_the_result(self) -> None:
        assert resolve_category({CATEGORY_NOT_RECOGNIZED}) == CATEGORY_NOT_RECOGNIZED

    def test_a_real_category_displaces_the_catch_all_even_as_the_last_in_precedence(self) -> None:
        assert resolve_category({CATEGORY_NOT_RECOGNIZED, "gegenstand"}) == "gegenstand"

    def test_not_recognized_next_to_an_unknown_value_stays_not_recognized(self) -> None:
        assert resolve_category({CATEGORY_NOT_RECOGNIZED, "einhorn"}) == CATEGORY_NOT_RECOGNIZED

    def test_gegenstand_alone_is_gegenstand_never_not_recognized(self) -> None:
        """Regressionsschutz gegen eine Implementierung, die den letzten Platz der
        Vorrangreihenfolge mit dem Auffangwert verwechselt (Teststrategie 1)."""
        assert resolve_category({"gegenstand"}) == "gegenstand"

    def test_accepts_set_frozenset_list_and_tuple_alike(self) -> None:
        candidates = ["tier", "tier", "menschen"]
        assert resolve_category(candidates) == "menschen"
        assert resolve_category(tuple(candidates)) == "menschen"
        assert resolve_category(set(candidates)) == "menschen"
        assert resolve_category(frozenset(candidates)) == "menschen"

    def test_does_not_mutate_its_input(self) -> None:
        candidates = {"tier", "menschen"}
        resolve_category(candidates)
        assert candidates == {"tier", "menschen"}


class TestIsKnownCategory:
    @pytest.mark.parametrize("key", list(CATEGORY_REGISTRY))
    def test_every_registry_key_is_known(self, key: str) -> None:
        assert is_known_category(key) is True

    def test_the_catch_all_is_known(self) -> None:
        assert is_known_category(CATEGORY_NOT_RECOGNIZED) is True

    @pytest.mark.parametrize("key", ["einhorn", "", "  ", "TIER", "Menschen", "unerkannt"])
    def test_unknown_or_differently_cased_values_are_not_known(self, key: str) -> None:
        assert is_known_category(key) is False


class TestRegistryInvariants:
    def test_the_registry_holds_exactly_these_thirteen_keys_in_this_order(self) -> None:
        """Bewusst redundanter, LITERALER Test (Teststrategie 2, Punkt 5) - eine rein aus der
        Registry abgeleitete Pruefung bliebe gruen, wenn eine Kategorie versehentlich geloescht
        oder umsortiert wuerde. Nachweis des Akzeptanzkriteriums, im Review nicht als "redundant
        zur Registry" zu streichen."""
        assert list(CATEGORY_REGISTRY) == [
            "menschen",
            "tier",
            "pflanze",
            "landschaft",
            "gebaeude_bauwerk",
            "innenraum",
            "essen_trinken",
            "fahrzeug",
            "gegenstand",
            "dokument_screenshot",
            "kunst_kreatives",
            "sport_aktivitaet",
            "nicht_erkannt",
        ]

    def test_keys_are_unique_and_match_their_dict_key(self) -> None:
        assert len(CATEGORY_REGISTRY) == len({d.key for d in CATEGORY_REGISTRY.values()})
        for dict_key, definition in CATEGORY_REGISTRY.items():
            assert dict_key == definition.key

    def test_precedence_values_form_a_gapless_one_to_twelve(self) -> None:
        precedences = sorted(
            definition.precedence
            for definition in CATEGORY_REGISTRY.values()
            if definition.precedence is not None
        )
        assert precedences == list(range(1, 13))

    def test_not_recognized_stands_outside_the_precedence_order(self) -> None:
        """Die Sonderrolle des Auffangwerts gilt STRUKTURELL (kein precedence-Wert), nicht nur per
        Konvention (Teststrategie 2, Punkt 3)."""
        assert CATEGORY_REGISTRY[CATEGORY_NOT_RECOGNIZED].precedence is None
        assert [
            key
            for key, definition in CATEGORY_REGISTRY.items()
            if definition.precedence is None
        ] == [CATEGORY_NOT_RECOGNIZED]

    def test_the_precedence_order_is_exactly_the_one_the_spec_fixes(self) -> None:
        ordered = [
            definition.key
            for definition in sorted(
                (d for d in CATEGORY_REGISTRY.values() if d.precedence is not None),
                key=lambda d: d.precedence or 0,
            )
        ]
        assert ordered == [
            "dokument_screenshot",
            "sport_aktivitaet",
            "menschen",
            "tier",
            "essen_trinken",
            "fahrzeug",
            "kunst_kreatives",
            "pflanze",
            "gebaeude_bauwerk",
            "landschaft",
            "innenraum",
            "gegenstand",
        ]

    @pytest.mark.parametrize("key", list(CATEGORY_REGISTRY))
    def test_every_entry_has_a_non_empty_definition_and_delimitation(self, key: str) -> None:
        definition = CATEGORY_REGISTRY[key]
        assert definition.definition.strip() != ""
        assert definition.delimitation.strip() != ""
        assert definition.display_name.strip() != ""

    def test_no_registry_entry_is_an_occasion_or_event_term(self) -> None:
        """Anlass-/Ereignisbegriffe bilden per Akzeptanzkriterium KEINE Kategorie - sie werden
        ausschliesslich als Feinlabel vergeben."""
        occasion_terms = {"geburtstag", "urlaub", "weihnachten", "hochzeit", "ostern", "feier"}
        for definition in CATEGORY_REGISTRY.values():
            assert definition.key.casefold() not in occasion_terms
            assert definition.display_name.casefold() not in occasion_terms


class TestLocalCategorySignals:
    def test_exactly_the_six_locally_determinable_categories_are_wired(self) -> None:
        """Benannte Stichprobe (Teststrategie 2, Punkt 6) - ein versehentlich zusaetzlich
        verdrahtetes Signal faellt hier auf, nicht erst im produktiven Lauf."""
        assert set(LOCAL_CATEGORY_SIGNALS) == {
            "menschen",
            "tier",
            "essen_trinken",
            "fahrzeug",
            "gebaeude_bauwerk",
            "landschaft",
        }

    @pytest.mark.parametrize("category_key", list(LOCAL_CATEGORY_SIGNALS))
    def test_every_referenced_category_exists_and_is_not_the_catch_all(
        self, category_key: str
    ) -> None:
        assert category_key in CATEGORY_REGISTRY
        assert category_key != CATEGORY_NOT_RECOGNIZED

    def test_every_referenced_criterion_is_category_eligible_with_a_threshold(self) -> None:
        for criterion_keys in LOCAL_CATEGORY_SIGNALS.values():
            for criterion_key in criterion_keys:
                definition = CRITERIA_REGISTRY[criterion_key]
                assert definition.category_eligible is True
                assert definition.category_presence_threshold is not None

    def test_every_category_eligible_criterion_is_wired_except_the_named_exception(self) -> None:
        """Gegenrichtung (Teststrategie 2, Punkt 6): ohne sie entstuende unbemerkt genau der
        Zustand, den diese Spec fuer `landmark` BEWUSST herstellt - kategorie-faehig, aber ohne
        eigene Kategorie. `landmark` gehoert deshalb als benannte, kommentierte Ausnahme in den
        Test, statt die Gegenrichtung wegzulassen."""
        # Benannte, bewusste Ausnahme: `landmark` bleibt kategorie-faehig (der erkannte Name bleibt
        # am Foto sichtbar) und speist `gebaeude_bauwerk` mit, bildet aber keine eigene Kategorie
        # mehr - deshalb ist es Teil eines LOCAL_CATEGORY_SIGNALS-Eintrags, nicht dessen Schluessel.
        wired = {key for keys in LOCAL_CATEGORY_SIGNALS.values() for key in keys}
        eligible = {
            key
            for key, definition in CRITERIA_REGISTRY.items()
            if definition.category_eligible
        }
        assert eligible - wired == set()

    def test_landmark_feeds_gebaeude_bauwerk_and_has_no_category_of_its_own(self) -> None:
        assert "landmark" in LOCAL_CATEGORY_SIGNALS["gebaeude_bauwerk"]
        assert "landmark" not in LOCAL_CATEGORY_SIGNALS


class TestBuildClassificationPrompt:
    @pytest.mark.parametrize("key", list(CATEGORY_REGISTRY))
    def test_every_registry_entry_appears_with_all_three_texts(self, key: str) -> None:
        """Testnachweis fuer Entwurfsentscheidung 3 ("Prompt und Set koennen nicht auseinander-
        laufen") - keine Assertion auf den vollstaendigen Wortlaut."""
        prompt = build_classification_prompt()
        definition = CATEGORY_REGISTRY[key]
        assert definition.key in prompt
        assert definition.display_name in prompt
        assert definition.definition in prompt
        assert definition.delimitation in prompt

    def test_the_prompt_is_generated_from_the_registry_not_a_literal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = CategoryDefinition(
            key="testkategorie",
            display_name="Testkategorie",
            definition="Eine ausschliesslich im Test existierende Kategorie.",
            delimitation="Nicht in der produktiven Registry vorhanden.",
            precedence=99,
        )
        patched = dict(CATEGORY_REGISTRY)
        patched[fake.key] = fake
        monkeypatch.setattr("photosort.categories.CATEGORY_REGISTRY", patched)

        prompt = build_classification_prompt()

        assert fake.display_name in prompt
        assert fake.definition in prompt
        assert fake.delimitation in prompt

    def test_the_prompt_contains_the_guiding_question(self) -> None:
        assert "dominante Bildmotiv" in build_classification_prompt()

    def test_the_prompt_forbids_occasion_terms_as_categories(self) -> None:
        prompt = build_classification_prompt()
        assert "Geburtstag" in prompt
        assert "Urlaub" in prompt
        assert "Weihnachten" in prompt
        assert "Hochzeit" in prompt
        assert "Feinlabel" in prompt

    def test_the_prompt_states_the_limits_from_the_constants(self) -> None:
        prompt = build_classification_prompt()
        assert str(MAX_REMOTE_CATEGORIES_PER_PHOTO) in prompt
        assert str(MAX_FINE_LABELS_PER_PHOTO) in prompt

    def test_not_recognized_is_a_selectable_option_in_the_prompt(self) -> None:
        assert CATEGORY_NOT_RECOGNIZED in build_classification_prompt()
