"""Die Regel der Endauswahl - rein, ohne Session, ohne Modellimport (ADR 0099 Punkte 1 und 2).

Sie muss gruen sein, BEVOR Migration und Endpunkte ihren ersten Fall bekommen: Ein Endpunktfall
gegen das alte Schema ist nicht rot, sondern ein Importfehler.

Die Kardinalitaet ist hier ein PARAMETER und kein erfundener dritter Nutzer - die Regel gilt fuer
jedes `n`, waehrend das Produkt nur `n = 2` kennt. Bei `n = 1` ist `contested` fuer keine Belegung
erreichbar; das ist die Aussage, nicht ein Randfall.
"""

from __future__ import annotations

import dataclasses

import pytest

from photosort.album_selection import SelectionState, selection_state


class TestTheTruthTableOverProposedAndDecision:
    """Die vollstaendige Tafel ueber `proposed x decision`. Eine Entscheidung ueberschreibt in
    BEIDE Richtungen und unabhaengig von jeder Belegung der uebrigen Parameter (Zusicherungen 1
    und 2 auf reiner Ebene)."""

    @pytest.mark.parametrize("proposed", [True, False])
    @pytest.mark.parametrize("decision", [True, False])
    @pytest.mark.parametrize(
        ("taken", "rejected"),
        [(0, 0), (1, 0), (0, 1), (2, 0), (0, 2), (1, 1)],
        ids=["unangefasst", "einer-drin", "einer-raus", "beide-drin", "beide-raus", "uneins"],
    )
    def test_a_decision_wins_over_every_configuration_of_the_drafts(
        self, proposed: bool, decision: bool, taken: int, rejected: int
    ) -> None:
        state = selection_state(
            taken=taken, rejected=rejected, user_count=2, proposed=proposed, decision=decision
        )

        assert state.included is decision
        assert state.contested is False

    def test_consensus_is_a_default_and_not_a_lock(self) -> None:
        """Zusicherung 1: Ein einig-drinnes Foto ohne Entscheidungszeile laesst sich herausnehmen
        und danach wieder aufnehmen. Eine Umsetzung, die den Konsenszweig VOR die Entscheidung
        stellt, besteht jeden anderen Fall."""
        agreed = {"taken": 0, "rejected": 0, "user_count": 2, "proposed": True}

        assert selection_state(**agreed, decision=None).included is True
        assert selection_state(**agreed, decision=False).included is False
        assert selection_state(**agreed, decision=True).included is True


class TestTheTwoSeparatingCasesAreNotSymmetric:
    """Zusicherung 4: `drin_zahl` liest bei VORGESCHLAGENEN Fotos die Streichungen, bei nicht
    vorgeschlagenen die Aufnahmen. Jeder Fall allein laesst die andere Haelfte durch."""

    def test_a_proposed_photo_taken_by_one_and_untouched_by_the_other_stays_agreed(self) -> None:
        """Eine Umsetzung, die hier `taken` zaehlt, liest "strittig"."""
        state = selection_state(taken=1, rejected=0, user_count=2, proposed=True, decision=None)

        assert state.included is True
        assert state.contested is False

    def test_an_unproposed_photo_taken_by_one_is_contested(self) -> None:
        """Eine Umsetzung, die hier `user_count - rejected` zaehlt, liest "einig drin"."""
        state = selection_state(taken=1, rejected=0, user_count=2, proposed=False, decision=None)

        assert state.included is False
        assert state.contested is True

    def test_an_unproposed_photo_nobody_took_is_neither_included_nor_contested(self) -> None:
        state = selection_state(taken=0, rejected=0, user_count=2, proposed=False, decision=None)

        assert state.included is False
        assert state.contested is False

    def test_a_proposed_photo_struck_by_one_is_contested(self) -> None:
        state = selection_state(taken=0, rejected=1, user_count=2, proposed=True, decision=None)

        assert state.included is False
        assert state.contested is True

    def test_a_proposed_photo_struck_by_everyone_is_neither_included_nor_contested(self) -> None:
        """Der Fall, ueber den niemand entschieden hat und den beide gestrichen haben: er gehoert
        nicht zur Endauswahl UND ist nicht strittig."""
        state = selection_state(taken=0, rejected=2, user_count=2, proposed=True, decision=None)

        assert state.included is False
        assert state.contested is False


class TestTheCardinalityIsAParameter:
    """Zusicherung 6: `n` ist der Nutzerbestand, und der Beweis dafuer ist `n = 1`. Ein
    hartkodiertes `== 2` liefert dort flaechendeckend `included: False`.

    Die Achse laeuft ueber `user_count in {1, 2, 3, 4}` mit je den drei Belegungen "alle drin",
    "keiner drin" und "einer fehlt" - in BEIDEN Herkuenften (vorgeschlagen und nicht
    vorgeschlagen), weil die beiden verschiedene Eingaenge lesen."""

    @pytest.mark.parametrize("user_count", [1, 2, 3, 4])
    def test_everyone_in_means_included_and_uncontested(self, user_count: int) -> None:
        proposed_state = selection_state(
            taken=0, rejected=0, user_count=user_count, proposed=True, decision=None
        )
        taken_state = selection_state(
            taken=user_count, rejected=0, user_count=user_count, proposed=False, decision=None
        )

        assert (proposed_state.included, proposed_state.contested) == (True, False)
        assert (taken_state.included, taken_state.contested) == (True, False)

    @pytest.mark.parametrize("user_count", [1, 2, 3, 4])
    def test_nobody_in_means_neither_included_nor_contested(self, user_count: int) -> None:
        proposed_state = selection_state(
            taken=0, rejected=user_count, user_count=user_count, proposed=True, decision=None
        )
        taken_state = selection_state(
            taken=0, rejected=0, user_count=user_count, proposed=False, decision=None
        )

        assert (proposed_state.included, proposed_state.contested) == (False, False)
        assert (taken_state.included, taken_state.contested) == (False, False)

    @pytest.mark.parametrize("user_count", [1, 2, 3, 4])
    def test_one_missing_is_contested_for_every_cardinality_above_one(
        self, user_count: int
    ) -> None:
        """Bei `n = 1` ist "einer fehlt" gleichbedeutend mit "keiner drin" - `contested` ist dort
        fuer KEINE Belegung erreichbar."""
        state = selection_state(
            taken=0, rejected=1, user_count=user_count, proposed=True, decision=None
        )

        assert state.included is False
        assert state.contested is (user_count > 1)

    def test_a_single_user_can_never_reach_contested(self) -> None:
        """Die Aussage hinter der Achse, ausgeschrieben: bei genau einem Nutzer ist Dissens
        arithmetisch unmoeglich."""
        for taken in range(3):
            for rejected in range(3):
                for proposed in (True, False):
                    state = selection_state(
                        taken=taken,
                        rejected=rejected,
                        user_count=1,
                        proposed=proposed,
                        decision=None,
                    )

                    assert state.contested is False, (taken, rejected, proposed)


class TestTheDegenerateInputs:
    def test_zero_users_is_no_consensus(self) -> None:
        """Zusicherung 7: Ohne den `user_count > 0`-Waechter waere `0 == 0` wahr und jedes
        vorgeschlagene Foto Teil der Endauswahl einer nutzerlosen Instanz."""
        state = selection_state(taken=0, rejected=0, user_count=0, proposed=True, decision=None)

        assert state.included is False
        assert state.contested is False

    def test_zero_users_with_an_explicit_decision_still_follows_the_decision(self) -> None:
        assert (
            selection_state(
                taken=0, rejected=0, user_count=0, proposed=True, decision=True
            ).included
            is True
        )

    def test_more_rejections_than_users_is_not_clamped(self) -> None:
        """Zusicherung 8: `taken + rejected <= user_count` gilt strukturell
        (`uq_rating_photo_user` plus Fremdschluessel auf `users`). Ein Clamp verbaerge den Bruch
        dieser Invariante, statt ihn zu zeigen - der Fall haelt seine ABWESENHEIT fest."""
        state = selection_state(taken=0, rejected=3, user_count=2, proposed=True, decision=None)

        assert state.included is False
        assert state.contested is False

    def test_more_takes_than_users_is_not_clamped_either(self) -> None:
        state = selection_state(taken=3, rejected=0, user_count=2, proposed=False, decision=None)

        assert state.included is False
        assert state.contested is False


class TestTheResultIsImmutable:
    def test_the_state_is_frozen(self) -> None:
        """Die drei abgeleiteten Werte gehen aus dieser Funktion in den Lesepfad und werden dort
        nie nachgerechnet - eine Zuweisung daran waere eine zweite Herleitung."""
        state = selection_state(taken=0, rejected=0, user_count=2, proposed=True, decision=None)

        with pytest.raises(dataclasses.FrozenInstanceError):
            state.included = False  # type: ignore[misc]

    def test_two_equal_states_compare_equal(self) -> None:
        arguments = {
            "taken": 1,
            "rejected": 0,
            "user_count": 2,
            "proposed": False,
            "decision": None,
        }

        assert selection_state(**arguments) == SelectionState(included=False, contested=True)


class TestTheInvariantsHoldForEveryInput:
    """Zusicherung 3 auf reiner Ebene: nie `contested` und `included` zugleich; `contested`
    impliziert keine Entscheidung; eine Entscheidung bestimmt `included`."""

    @pytest.mark.parametrize("decision", [None, True, False])
    @pytest.mark.parametrize("proposed", [True, False])
    @pytest.mark.parametrize("user_count", [0, 1, 2, 3])
    def test_the_three_invariants_hold(
        self, decision: bool | None, proposed: bool, user_count: int
    ) -> None:
        for taken in range(user_count + 1):
            for rejected in range(user_count + 1 - taken):
                state = selection_state(
                    taken=taken,
                    rejected=rejected,
                    user_count=user_count,
                    proposed=proposed,
                    decision=decision,
                )

                assert not (state.included and state.contested)
                if state.contested:
                    assert decision is None
                if decision is not None:
                    assert state.included is decision
