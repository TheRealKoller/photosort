"""Das Auswahlverfahren, DB-frei geprueft: Kontingente je Event und motivgefuehrte Vergabe.

Ein Fehler in diesem Verfahren wirft keine Ausnahme und verletzt kein Schema - er liefert eine
andere, plausibel aussehende Auswahl. Jede Aussage hier hat deshalb einen Fall, der bei ihrer
Verletzung rot wird.

Die Startwerte stehen als Literale in genau EINEM Fall
(`test_the_starting_values_are_pinned_in_exactly_this_one_case`); alle uebrigen rechnen gegen die
Konstanten, damit eine spaetere Kalibrierung eine Zahl in `selection.py` aendert statt eine
Testwelle auszuloesen.
"""

from __future__ import annotations

import ast
import itertools
import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import photosort
from photosort.selection import (
    DEFAULT_TARGET_DIVISOR,
    EVENT_SHARE_CAP,
    MOTIF_PRESENCE_THRESHOLD,
    SIMILARITY_DECAY,
    SIMILARITY_TIME_WINDOW,
    AlternativeCandidate,
    SelectionCandidate,
    SelectionEvent,
    carried_motifs,
    effective_target,
    motif_is_present,
    order_alternatives,
    select_album_draft,
)

_BASE_TIME = datetime(2026, 7, 20, 10, 0)

# "Das Motiv ist voll da" - kein Kalibrierungswert, sondern der Rand der Skala. Der interessante
# Wert ist MOTIF_PRESENCE_THRESHOLD, und der wird als Konstante eingesetzt, nie als Zahl.
_FULL = 1.0
_BELOW = math.nextafter(MOTIF_PRESENCE_THRESHOLD, 0.0)


def _candidate(
    photo_id: int,
    quality: float,
    *,
    motifs: Mapping[str, float] | None = None,
    offset: timedelta = timedelta(),
) -> SelectionCandidate:
    return SelectionCandidate(
        photo_id=photo_id,
        taken_at=_BASE_TIME + offset,
        quality=quality,
        motif_strengths=dict(motifs or {}),
    )


def _event(
    event_id: int, position: int, candidates: Sequence[SelectionCandidate]
) -> SelectionEvent:
    return SelectionEvent(event_id=event_id, position=position, candidates=tuple(candidates))


def _plain_event(event_id: int, position: int, size: int, *, first_photo_id: int) -> SelectionEvent:
    """Ein Event mit `size` motivlosen Kandidaten absteigender Qualitaet - fuer alle Faelle, in
    denen ausschliesslich die Verteilung der Kontingente geprueft wird."""
    return _event(
        event_id,
        position,
        [_candidate(first_photo_id + index, 1.0 - index / (size + 1)) for index in range(size)],
    )


def _event_cap(size: int, target: int, event_count: int) -> int:
    """`min(n_i, max(⌈T/m⌉, ⌈0,25·T⌉))` - die Obergrenze eines Events, gegen die Konstante
    gerechnet. Das `max(1, …)` haelt die Abdeckungszusage auch bei `T = 0` aufrecht."""
    return min(
        size,
        max(1, -(-target // event_count), math.ceil(EVENT_SHARE_CAP * target)),
    )


def assert_selection_invariants(
    events: Sequence[SelectionEvent], target: int, result: Mapping[int, int]
) -> None:
    """Vier Zusicherungen, die als Nachsatz JEDES Falls laufen - im Muster von
    `assert_event_invariants`:

    (a) jedes Event mit `n_i > 0` hat mindestens einen Platz;
    (b) kein Event hat mehr als `min(n_i, max(⌈T/m⌉, ⌈0,25·T⌉))`;
    (c) die Plaetze eines Events sind exakt `{1 … k}`, 1-basiert und lueckenlos;
    (d) kein Foto erscheint zweimal."""
    eligible = [event for event in events if event.candidates]
    event_count = len(eligible)

    seen: list[int] = []
    for event in eligible:
        places = sorted(
            result[candidate.photo_id]
            for candidate in event.candidates
            if candidate.photo_id in result
        )
        seen.extend(
            candidate.photo_id for candidate in event.candidates if candidate.photo_id in result
        )
        assert places, f"Event {event.event_id} mit {len(event.candidates)} Kandidaten ohne Platz"
        cap = _event_cap(len(event.candidates), target, event_count)
        assert len(places) <= cap, f"Event {event.event_id}: {len(places)} > Kappe {cap}"
        assert places == list(range(1, len(places) + 1)), (
            f"Event {event.event_id}: Plaetze {places} sind nicht lueckenlos ab 1"
        )

    assert len(seen) == len(set(seen)), "ein Foto steht zweimal im Vorschlag"
    assert set(seen) == set(result), "der Vorschlag enthaelt ein Foto ausserhalb der Events"


def _draft(events: Sequence[SelectionEvent], target: int) -> dict[int, int]:
    """Ein Aufruf samt Invariantenpruefung - der Regelweg dieser Datei.

    GENAU EINE benannte Ausnahme: `TestTheOverloadBoundary` ruft `select_album_draft` direkt. Die
    Invariantenpruefung laeuft ueber alle Kandidaten jedes Events und waere bei 2000 Kandidaten
    selbst der teuerste Teil des Falls - sie machte die Laufzeitaussage unlesbar, die dort die
    eigentliche Zusage ist."""
    result = select_album_draft(events, target)
    assert_selection_invariants(events, target, result)
    return result


def _places_per_event(
    events: Sequence[SelectionEvent], result: Mapping[int, int]
) -> dict[int, int]:
    return {
        event.event_id: sum(1 for c in event.candidates if c.photo_id in result) for event in events
    }


class TestTheStartingValues:
    def test_the_starting_values_are_pinned_in_exactly_this_one_case(self) -> None:
        """Der EINE Fall mit Literalen. Aendert eine Kalibrierung eine dieser Zahlen, wird genau
        dieser Fall rot - und kein zweiter."""
        assert EVENT_SHARE_CAP == 0.25
        assert MOTIF_PRESENCE_THRESHOLD == 0.5
        assert SIMILARITY_DECAY == 0.5
        assert SIMILARITY_TIME_WINDOW == timedelta(minutes=15)
        assert DEFAULT_TARGET_DIVISOR == 10


class TestTheEffectiveTarget:
    def test_without_an_own_setting_it_is_a_tenth_of_the_photo_count(self) -> None:
        assert effective_target(None, 100) == 100 // DEFAULT_TARGET_DIVISOR

    @pytest.mark.parametrize(
        ("photo_count", "expected"),
        [
            pytest.param(DEFAULT_TARGET_DIVISOR, 1, id="glatt-aufgehend"),
            pytest.param(DEFAULT_TARGET_DIVISOR + 1, 2, id="aufgerundet"),
        ],
    )
    def test_the_default_rounds_up(self, photo_count: int, expected: int) -> None:
        """Das Paar trennt `⌈·⌉` von `//`: eine ganzzahlige Division ergaebe hier zweimal 1."""
        assert effective_target(None, photo_count) == expected

    def test_an_empty_project_still_has_a_target_of_one(self) -> None:
        assert effective_target(None, 0) == 1

    def test_a_configured_number_is_taken_absolutely(self) -> None:
        assert effective_target(7, 100_000) == 7

    def test_the_default_grows_with_the_stock_while_a_set_number_stays(self) -> None:
        """Die eigentliche Zusage der Vorbelegung, als Paar in EINEM Fall: derselbe Bestand
        waechst, der wirksame Wert waechst bei `NULL` mit und bleibt bei einer eingestellten Zahl
        stehen. Dass die Vorbelegung dabei nie in die Spalte geschrieben wird, ist die DB-nahe
        Haelfte davon (test_worker_selection.py)."""
        small, large = 50, 500

        assert effective_target(None, small) < effective_target(None, large)
        assert effective_target(20, small) == effective_target(20, large) == 20


class TestTheQuotasPerEvent:
    @pytest.mark.parametrize("event_count", [1, 2, 3, 4, 5, 8, 13])
    @pytest.mark.parametrize("target", [1, 2, 7, 10, 100])
    def test_the_share_cap_never_shrinks_the_draft(self, event_count: int, target: int) -> None:
        """Die Anteilskappe verkleinert den Vorschlag nie - nur fehlende Kandidaten tun das. Als
        Eigenschaft ueber eine Matrix statt an Beispielen; sie deckt zugleich "der Vorschlag wird
        groesser als der Richtwert" (`m > T`) und den Normalfall ab."""
        events = [
            _plain_event(index + 1, index + 1, 100, first_photo_id=1000 * (index + 1))
            for index in range(event_count)
        ]

        result = _draft(events, target)

        assert len(result) == max(target, event_count)

    def test_the_draft_gets_smaller_only_when_candidates_run_out(self) -> None:
        """Exakte Kardinalitaet, nicht `<= T`: die uebrigen Plaetze verfallen."""
        events = [
            _plain_event(1, 1, 2, first_photo_id=100),
            _plain_event(2, 2, 3, first_photo_id=200),
        ]

        result = _draft(events, target=100)

        assert len(result) == 5

    def test_the_cap_binds_where_the_equal_share_is_the_larger_half(self) -> None:
        """`max(⌈T/m⌉, ⌈0,25·T⌉)` ist von jeder seiner Haelften allein ununterscheidbar - dies ist
        der Aufbau, in dem `⌈T/m⌉` gewinnt (m = 3, T = 12 → 4 gegen 3)."""
        target = 12
        events = [
            _plain_event(1, 1, 100, first_photo_id=1000),
            _plain_event(2, 2, 10, first_photo_id=2000),
            _plain_event(3, 3, 10, first_photo_id=3000),
        ]

        result = _draft(events, target)
        per_event = _places_per_event(events, result)

        assert per_event[1] == _event_cap(100, target, 3) == 4
        assert len(result) == target

    def test_the_cap_binds_where_the_quarter_is_the_larger_half(self) -> None:
        """Der zweite Aufbau: m = 8, T = 20 → `⌈0,25·T⌉ = 5` gewinnt gegen `⌈T/m⌉ = 3`."""
        target = 20
        events = [_plain_event(1, 1, 100, first_photo_id=1000)] + [
            _plain_event(index, index, 10, first_photo_id=1000 * index) for index in range(2, 9)
        ]

        result = _draft(events, target)
        per_event = _places_per_event(events, result)

        assert per_event[1] == _event_cap(100, target, 8) == 5
        assert len(result) == target

    def test_the_redistribution_pushes_a_second_event_to_its_cap(self) -> None:
        """Ohne die WIEDERHOLUNG der Verteilung blieben hier drei Plaetze liegen: nach der ersten
        Runde steht nur das grosse Event an seiner Kappe, die drei kleinen haben je einen Platz
        frei. Eine Implementierung mit nur einer Runde liefert 13 statt 16."""
        target = 16
        events = [_plain_event(1, 1, 100, first_photo_id=1000)] + [
            _plain_event(index, index, 8, first_photo_id=1000 * index) for index in range(2, 5)
        ]

        result = _draft(events, target)
        per_event = _places_per_event(events, result)

        assert per_event == {1: 4, 2: 4, 3: 4, 4: 4}
        assert len(result) == target

    def test_the_redistribution_terminates_when_no_event_can_take_more(self) -> None:
        """Nach der Umverteilung bleiben Plaetze frei, und KEIN Event kann sie aufnehmen: das
        grosse steht an seiner Kappe, das kleine an seiner Kandidatenzahl. Das muss enden - und
        zwar ueber den Rundenzaehler in der Funktion, nicht ueber eine Zeitgrenze."""
        events = [
            _plain_event(1, 1, 100, first_photo_id=1000),
            _plain_event(2, 2, 3, first_photo_id=2000),
        ]

        result = _draft(events, target=10)

        assert _places_per_event(events, result) == {1: 5, 2: 3}
        assert len(result) == 8


class TestTheEdgesOfTheDistribution:
    @pytest.mark.parametrize(
        "events",
        [
            pytest.param((), id="gar-keine-events"),
            pytest.param(
                (_event(1, 1, ()), _event(2, 2, ())), id="events-ohne-auswahlfaehige-kandidaten"
            ),
        ],
    )
    def test_no_eligible_candidate_at_all_yields_an_empty_draft(
        self, events: tuple[SelectionEvent, ...]
    ) -> None:
        """`m = 0` macht `⌈T/m⌉` zu einer Division durch Null. Das Ergebnis muss ein leeres Dict
        sein, ohne Ausnahme. Der dritte Weg zu demselben Ausgang - Kandidaten ohne `rank_score` -
        ist DB-nah und steht in test_worker_selection.py."""
        assert _draft(events, target=10) == {}

    def test_an_event_without_candidates_does_not_count_in_the_event_number(self) -> None:
        """Zaehlte es mit, verschoebe sich die gesamte Verteilung."""
        events = [
            _event(1, 1, ()),
            _plain_event(2, 2, 10, first_photo_id=2000),
            _plain_event(3, 3, 10, first_photo_id=3000),
        ]

        result = _draft(events, target=4)

        assert _places_per_event(events, result) == {1: 0, 2: 2, 3: 2}

    def test_more_events_than_the_target_make_the_draft_larger(self) -> None:
        """`T - m` ist hier negativ - eine Restverteilung, die damit rechnet, zoege Plaetze ab."""
        events = [
            _plain_event(index, index, 3, first_photo_id=1000 * index) for index in range(1, 6)
        ]

        result = _draft(events, target=2)

        assert len(result) == 5
        assert set(_places_per_event(events, result).values()) == {1}

    @pytest.mark.parametrize(
        ("event_count", "expected"),
        [pytest.param(1, 1, id="ein-event"), pytest.param(3, 3, id="drei-events")],
    )
    def test_a_target_of_one_still_covers_every_event(
        self, event_count: int, expected: int
    ) -> None:
        events = [
            _plain_event(index, index, 5, first_photo_id=1000 * index)
            for index in range(1, event_count + 1)
        ]

        assert len(_draft(events, target=1)) == expected

    def test_a_single_event_gets_the_whole_target(self) -> None:
        """Die Kappe ist `min(n_1, max(T, ⌈0,25·T⌉)) = min(n_1, T)`. Eine Implementierung ohne das
        `max` kappte hier auf ein Viertel."""
        events = [_plain_event(1, 1, 100, first_photo_id=1000)]

        assert len(_draft(events, target=8)) == 8

    def test_a_very_large_target_places_every_candidate(self) -> None:
        events = [
            _plain_event(1, 1, 4, first_photo_id=1000),
            _plain_event(2, 2, 6, first_photo_id=2000),
        ]

        result = _draft(events, target=1_000)

        assert _places_per_event(events, result) == {1: 4, 2: 6}

    def test_the_last_remaining_seat_goes_by_position_not_by_iteration_order(self) -> None:
        """Zwei Events mit identischem `n_i` und damit identischem Rest, ein einziger Restplatz.
        Die Eingabe steht bewusst in umgekehrter Reihenfolge."""
        first = _plain_event(7, 1, 10, first_photo_id=7000)
        second = _plain_event(3, 2, 10, first_photo_id=3000)
        events = [second, first]

        result = _draft(events, target=3)

        assert _places_per_event(events, result) == {7: 2, 3: 1}

    def test_a_remainder_free_distribution_stays_exact(self) -> None:
        """Alle Anteile gehen glatt auf - es gibt keinen Rest zu vergeben."""
        events = [
            _plain_event(1, 1, 4, first_photo_id=1000),
            _plain_event(2, 2, 4, first_photo_id=2000),
        ]

        result = _draft(events, target=4)

        assert _places_per_event(events, result) == {1: 2, 2: 2}

    def test_a_target_equal_to_the_event_number_distributes_nothing(self) -> None:
        """`T - m == 0`: die Abdeckung fuellt den Richtwert bereits vollstaendig, und die
        Restverteilung laeuft gar nicht erst an."""
        events = [
            _plain_event(index, index, 5, first_photo_id=1000 * index) for index in range(1, 4)
        ]

        result = _draft(events, target=3)

        assert _places_per_event(events, result) == {1: 1, 2: 1, 3: 1}


class TestTheMotifGuidedAssignment:
    def test_without_any_present_motif_the_order_is_the_pure_quality_order(self) -> None:
        """Kein Motiv ueber der Grenze: die Einschraenkung greift nie, es gibt keine Abwertung."""
        candidates = [
            _candidate(1, 0.9, motifs={"a": _BELOW}),
            _candidate(2, 0.7, motifs={"a": _BELOW}),
            _candidate(3, 0.5, motifs={"a": _BELOW}),
            _candidate(4, 0.3, motifs={"a": _BELOW}),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=3)

        assert result == {1: 1, 2: 2, 3: 3}

    def test_with_motifs_the_same_stock_comes_out_differently(self) -> None:
        """Gegenprobe zum Fall darueber: derselbe Bestand, dieselben Qualitaeten - nur tragen die
        Bilder jetzt Motive."""
        candidates = [
            _candidate(1, 0.9, motifs={"a": _FULL}),
            _candidate(2, 0.7, motifs={"a": _FULL}),
            _candidate(3, 0.5, motifs={"b": _FULL}),
            _candidate(4, 0.3, motifs={"a": _BELOW}),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=3)

        assert result[3] == 2

    def test_the_chosen_photo_represents_every_unrepresented_motif_it_carries(self) -> None:
        """Drei vorkommende Motive; ein Bild traegt A UND B. Bei zwei Plaetzen muss Platz 2 an den
        C-Traeger gehen, auch wenn der reine B-Traeger den hoeheren Wert haette. Mit nur zwei
        Motiven waere diese Aussage von "vertritt eines davon" nicht zu unterscheiden."""
        candidates = [
            _candidate(1, 0.99, motifs={"a": _FULL, "b": _FULL}),
            _candidate(2, 0.95, motifs={"b": _FULL}, offset=4 * SIMILARITY_TIME_WINDOW),
            _candidate(3, 0.50, motifs={"c": _FULL}),
            _candidate(4, 0.30, motifs={"a": _FULL}),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=2)

        assert result == {1: 1, 3: 2}

    def test_with_fewer_seats_than_motifs_the_value_decides_which_are_represented(self) -> None:
        """Hat ein Event WENIGER Plaetze als vorkommende Motive, entscheidet der Wert, welche
        Motive vertreten sind - und zwar OHNE dass irgendwo eine Rangfolge zwischen Motiven
        entstuende.

        Der Aufbau ist der einzige der Datei, in dem ein vorkommendes Motiv am Ende UNVERTRETEN
        bleibt: drei Motive, je ein eigener Traeger, klar getrennte Qualitaeten, zwei Plaetze. Die
        beiden Faelle darueber und darunter enden mit allen bzw. beiden Motiven vertreten und
        koennten diese Aussage deshalb nicht tragen.

        Qualitaet und `photo_id` laufen dabei GEGENLAEUFIG, und die Eingabereihenfolge folgt
        keiner von beiden: eine Implementierung, die bei Motivknappheit den zuerst gesehenen oder
        den kleinstnummerierten Traeger nimmt statt den wertvollsten, faellt hier auf. Die
        Permutationsinvarianz ueber die Motivschluessel faengt nur eine Rangfolge ueber die
        SCHLUESSEL, nicht eine ueber die Reihenfolge der Kandidaten."""
        candidates = [
            _candidate(2, 0.7, motifs={"b": _FULL}),
            _candidate(1, 0.5, motifs={"c": _FULL}),
            _candidate(3, 0.9, motifs={"a": _FULL}),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=2)

        assert result == {3: 1, 2: 2}
        represented = {
            motif_key
            for candidate in candidates
            if candidate.photo_id in result
            for motif_key, strength in candidate.motif_strengths.items()
            if strength >= MOTIF_PRESENCE_THRESHOLD
        }
        assert represented == {"a", "b"}

    def test_the_motif_obligation_beats_the_higher_value(self) -> None:
        """Das wertvollste verbliebene Bild traegt ausschliesslich ein bereits vertretenes Motiv
        und wird uebergangen."""
        candidates = [
            _candidate(1, 0.9, motifs={"a": _FULL}, offset=4 * SIMILARITY_TIME_WINDOW),
            _candidate(2, 0.8, motifs={"a": _FULL}, offset=8 * SIMILARITY_TIME_WINDOW),
            _candidate(3, 0.4, motifs={"b": _FULL}),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=2)

        assert result == {1: 1, 3: 2}

    def test_the_decay_also_works_inside_the_restricted_set(self) -> None:
        """Das gewaehlte Bild traegt A und B, unvertreten ist C. Von zwei C-Traegern liegt einer
        zeitnah beim gewaehlten Bild und teilt mit ihm A - er faellt zurueck, obwohl seine
        Qualitaet die hoehere ist."""
        candidates = [
            _candidate(1, 0.99, motifs={"a": _FULL, "b": _FULL}),
            _candidate(2, 0.60, motifs={"a": _FULL, "c": _FULL}),
            _candidate(3, 0.50, motifs={"c": _FULL}, offset=4 * SIMILARITY_TIME_WINDOW),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=2)

        assert result == {1: 1, 3: 2}

    def test_equal_quality_is_broken_by_the_lower_photo_id(self) -> None:
        """Eingegeben in ABSTEIGENDER `photo_id`-Reihenfolge: eine Implementierung, die die
        Kandidaten beim Eintritt nicht sortiert, nimmt hier das zuerst gesehene Element."""
        candidates = [
            _candidate(5, 0.5, motifs={"a": _BELOW}),
            _candidate(4, 0.5, motifs={"a": _BELOW}),
            _candidate(3, 0.5, motifs={"a": _BELOW}),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=2)

        assert result == {3: 1, 4: 2}

    def test_equal_decayed_values_are_broken_by_the_lower_photo_id(self) -> None:
        """Der schaerfere Fall: erst die ABGEWERTETEN Werte sind gleich. Ein `max(…, key=…)` ohne
        expliziten zweiten Schluessel nimmt dort das zuerst gesehene Element - und das ist bei
        dieser Eingabereihenfolge das mit der groesseren Id."""
        candidates = [
            _candidate(3, 0.8, motifs={"a": _FULL}),
            _candidate(2, 0.8 * SIMILARITY_DECAY, motifs={"a": _BELOW}),
            _candidate(1, 1.0, motifs={"a": _FULL}),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=2)

        assert result == {1: 1, 2: 2}


def _second_place_winner(
    decayed_quality: float,
    neutral_quality: float,
    *,
    offset: timedelta = timedelta(),
    shared_strength: float = _FULL,
) -> int:
    """Ein Event, drei Kandidaten, zwei Plaetze: der Anfuehrer (Platz 1), ein Kandidat, der mit
    ihm ein Motiv teilt und deshalb abgewertet wird, und ein motivloser Kandidat ohne Abwertung.
    Rueckgabe ist die `photo_id` auf Platz 2 - und damit die pruefbare Aussage darueber, wie stark
    abgewertet wurde."""
    events = [
        _event(
            1,
            1,
            [
                _candidate(1, 1.0, motifs={"a": _FULL}),
                _candidate(2, decayed_quality, motifs={"a": shared_strength}, offset=offset),
                _candidate(3, neutral_quality, motifs={"a": _BELOW}),
            ],
        )
    ]
    result = _draft(events, target=2)
    assert result[1] == 1
    return next(photo_id for photo_id, place in result.items() if place == 2)


class TestTheSimilarityFormula:
    def test_a_simultaneous_photo_of_the_same_motif_is_halved(self) -> None:
        """(a) Zeitgleich, geteiltes Motiv → Faktor exakt `SIMILARITY_DECAY`. Die beiden
        Nachbarwerte klemmen den Faktor ein: ein milderer oder staerkerer Faktor kippt einen der
        beiden Ausgaenge."""
        halved = 0.8 * SIMILARITY_DECAY

        assert _second_place_winner(0.8, math.nextafter(halved, 0.0)) == 2
        assert _second_place_winner(0.8, math.nextafter(halved, 1.0)) == 3

    def test_two_similar_photos_sum_up_in_the_exponent(self) -> None:
        """(b) Summation: zwei bereits gewaehlte zeitgleiche Bilder desselben Motivs werten ein
        drittes auf `SIMILARITY_DECAY ** 2` ab."""
        quartered = 0.8 * SIMILARITY_DECAY**2

        def winner_of_third_place(neutral_quality: float) -> int:
            events = [
                _event(
                    1,
                    1,
                    [
                        _candidate(1, 1.0, motifs={"a": _FULL}),
                        _candidate(2, 0.9, motifs={"a": _FULL}),
                        _candidate(3, 0.8, motifs={"a": _FULL}),
                        _candidate(4, neutral_quality, motifs={"a": _BELOW}),
                    ],
                )
            ]
            result = _draft(events, target=3)
            assert result[1] == 1 and result[2] == 2
            return next(photo_id for photo_id, place in result.items() if place == 3)

        assert winner_of_third_place(math.nextafter(quartered, 0.0)) == 3
        assert winner_of_third_place(math.nextafter(quartered, 1.0)) == 4

    def test_without_a_shared_motif_nothing_is_devalued(self) -> None:
        """(c) Kein geteiltes Motiv → KEINE Abwertung, egal wie klein `Δt`. Beide Kandidaten
        liegen hier zeitgleich beim Anfuehrer; wuerde der motivlose mit abgewertet, gewaenne der
        qualitativ staerkere Motivtraeger."""
        candidates = [
            _candidate(1, 1.0, motifs={"a": _FULL}),
            _candidate(2, 0.5, motifs={"a": _BELOW}),
            _candidate(3, 0.9, motifs={"a": _FULL}),
        ]
        events = [_event(1, 1, candidates)]

        result = _draft(events, target=2)

        assert result == {1: 1, 2: 2}

    @pytest.mark.parametrize(
        "offset",
        [
            pytest.param(SIMILARITY_TIME_WINDOW, id="genau-am-fensterrand"),
            pytest.param(2 * SIMILARITY_TIME_WINDOW, id="weit-jenseits-des-fensters"),
        ],
    )
    def test_beyond_the_time_window_the_factor_is_one_and_never_larger(
        self, offset: timedelta
    ) -> None:
        """(d) Der gefaehrlichste Fall des Verfahrens: `1 − |Δt|/15min` OHNE `max(0, …)` ergibt
        jenseits des Fensters einen negativen Exponenten und damit eine AUFWERTUNG gerade der
        weit entfernten Bilder (`0,5^−1 = 2`) - ohne auffaelliges Fehlerbild. Die beiden
        Nachbarwerte klemmen den Faktor auf exakt 1 ein: ein groesserer kippt den zweiten
        Ausgang."""
        assert _second_place_winner(0.6, math.nextafter(0.6, 0.0), offset=offset) == 2
        assert _second_place_winner(0.6, math.nextafter(0.6, 1.0), offset=offset) == 3


class TestTheMotifThresholdIsInclusive:
    def test_a_motif_carried_at_exactly_the_threshold_counts_as_present(self) -> None:
        """Erste Haelfte: "Motiv kommt vor". Gilt `b` als vorkommend, muss Platz 2 an seinen
        einzigen Traeger gehen, obwohl dessen Qualitaet die niedrigste ist."""

        def second_place(strength: float) -> int:
            events = [
                _event(
                    1,
                    1,
                    [
                        _candidate(1, 0.9, motifs={"a": _FULL}),
                        _candidate(2, 0.8, motifs={"a": _FULL}, offset=4 * SIMILARITY_TIME_WINDOW),
                        _candidate(3, 0.1, motifs={"b": strength}),
                    ],
                )
            ]
            result = _draft(events, target=2)
            assert result[1] == 1
            return next(photo_id for photo_id, place in result.items() if place == 2)

        assert second_place(MOTIF_PRESENCE_THRESHOLD) == 3
        assert second_place(_BELOW) == 2

    def test_a_shared_motif_at_exactly_the_threshold_devalues(self) -> None:
        """Zweite Haelfte: "geteiltes Motiv". Bei genau der Grenze wird abgewertet (0,8 → 0,4) und
        der motivlose Kandidat mit 0,5 gewinnt; knapp darunter bleibt die 0,8 stehen."""
        assert _second_place_winner(0.8, 0.5, shared_strength=MOTIF_PRESENCE_THRESHOLD) == 3
        assert _second_place_winner(0.8, 0.5, shared_strength=_BELOW) == 2


class TestTheMotifsAreEqualInRank:
    def test_swapping_two_motif_keys_leaves_the_result_identical(self) -> None:
        """Der pruefbare Ausdruck von "keine Rangfolge zwischen Motiven": werden zwei
        Motivschluessel in der GESAMTEN Eingabe konsistent vertauscht, ist das Ergebnis
        identisch. Ein Fall, der nur "beide Motive sind vertreten" prueft, bestuende auch bei
        einer festen Vorrangliste."""
        swap = {"a": "b", "b": "a"}
        originals = [
            _candidate(1, 0.90, motifs={"a": _FULL}),
            _candidate(2, 0.85, motifs={"a": _FULL, "b": _FULL}),
            _candidate(3, 0.70, motifs={"b": _FULL}),
            _candidate(4, 0.60, motifs={"a": _FULL, "c": _FULL}),
            _candidate(5, 0.55, motifs={"b": _FULL, "c": _FULL}),
        ]
        swapped = [
            _candidate(
                candidate.photo_id,
                candidate.quality,
                motifs={
                    swap.get(key, key): value for key, value in candidate.motif_strengths.items()
                },
                offset=candidate.taken_at - _BASE_TIME,
            )
            for candidate in originals
        ]

        assert _draft([_event(1, 1, originals)], target=3) == _draft(
            [_event(1, 1, swapped)], target=3
        )


def _alternative(
    photo_id: int, quality: float | None, *, motifs: Mapping[str, float] | None = None
) -> AlternativeCandidate:
    return AlternativeCandidate(
        photo_id=photo_id, quality=quality, motif_strengths=dict(motifs or {})
    )


class TestTheCarriedMotifsArePublic:
    """`carried_motifs` ist die eine Stelle, an der "dieses Bild traegt dieses Motiv" entsteht -
    fuer die Auswahl wie fuer die Alternativen. Sie ruft `motif_is_present` und vergleicht nie
    selbst."""

    def test_exactly_the_motifs_at_or_above_the_threshold_are_carried(self) -> None:
        carried = carried_motifs({"a": _FULL, "b": MOTIF_PRESENCE_THRESHOLD, "c": _BELOW})

        assert carried == frozenset({"a", "b"})

    def test_a_candidate_without_strengths_carries_nothing(self) -> None:
        assert carried_motifs({}) == frozenset()


class TestTheThresholdCanBeVariedForAMeasurementWithoutMovingTheOperatingPoint:
    """Die Praesenzgrenze ist DURCHREICHBAR, damit ein rein lesender Messlauf sie variieren kann,
    ohne eine zweite Fassung des Vergleichs zu bauen (Spec 0506, Block E).

    DIE EINDAEMMUNG BLEIBT (Sicherheitskonzept, "Standortdaten"): Es ist EIN Skalar fuer ALLE
    Motive, nie eine Grenze je Motiv - zwei Motive treten damit weiterhin nie ueber ihre Zahlen
    gegeneinander an. Ohne Angabe gilt unveraendert die Modulkonstante, und der Vergleich bleibt
    INKLUSIV."""

    def test_without_an_argument_nothing_changes_at_all(self) -> None:
        """Der Zwilling gegen das Auseinanderlaufen der beiden Vergleiche in `motif_is_present`:
        Am Betriebswert muessen beide Zweige Foto fuer Foto dasselbe sagen - EINSCHLIESSLICH des
        Werts genau auf der Grenze und seines naechsten Nachbarn darunter."""
        for strength in (0.0, _BELOW, MOTIF_PRESENCE_THRESHOLD, _FULL):
            assert motif_is_present(strength) is motif_is_present(
                strength, MOTIF_PRESENCE_THRESHOLD
            ), strength

    def test_a_stricter_threshold_carries_less_and_a_looser_one_carries_more(self) -> None:
        strengths = {"a": _FULL, "b": MOTIF_PRESENCE_THRESHOLD, "c": _BELOW}

        assert carried_motifs(strengths, _FULL) == frozenset({"a"})
        assert carried_motifs(strengths, _BELOW) == frozenset({"a", "b", "c"})

    def test_the_passed_threshold_is_read_inclusively_too(self) -> None:
        """Nicht nur die Konstante wird inklusiv gelesen: Ein `>` im durchgereichten Zweig waere
        gruen gegen jeden Wert abseits der Grenze und liefe genau am Grenzfall auseinander."""
        assert motif_is_present(_FULL, _FULL) is True
        assert motif_is_present(math.nextafter(_FULL, 0.0), _FULL) is False

    def test_the_same_threshold_applies_to_every_motif_of_a_picture(self) -> None:
        """Ein Skalar, keine Abbildung je Motiv: Zwei gleich starke Motive fallen unter jedem Wert
        gemeinsam heraus oder gemeinsam hinein."""
        strengths = {"a": MOTIF_PRESENCE_THRESHOLD, "b": MOTIF_PRESENCE_THRESHOLD}

        assert carried_motifs(strengths, _FULL) == frozenset()
        assert carried_motifs(strengths, _BELOW) == frozenset({"a", "b"})


class TestTheOrderOfTheAlternatives:
    """Der Sortierschluessel `(0 wenn geteiltes Motiv sonst 1, -quality, photo_id)`.

    Ein Fehler hier wirft nichts - er liefert eine andere, plausibel aussehende Reihenfolge. Jede
    Aussage des ADR 0098 Punkt 5 hat deshalb einen Fall."""

    def test_a_shared_motif_comes_before_a_better_picture_without_one(self) -> None:
        reference = _alternative(1, 0.5, motifs={"a": _FULL})

        assert order_alternatives(
            reference,
            [_alternative(2, 0.1, motifs={"a": _FULL}), _alternative(3, 0.9, motifs={"b": _FULL})],
        ) == [2, 3]

    def test_a_candidate_without_quality_and_with_a_shared_motif_beats_every_stranger(self) -> None:
        """Zusicherung 5: `None` sortiert INNERHALB seiner Gruppe ans Ende, nie global. Eine
        Implementierung, die alle `None` global ans Ende schiebt, besteht jeden Aufbau ohne einen
        Kandidaten dieser Art."""
        reference = _alternative(1, 0.5, motifs={"a": _FULL})

        assert order_alternatives(
            reference,
            [
                _alternative(2, 0.9, motifs={"b": _FULL}),
                _alternative(3, None, motifs={"a": _FULL}),
                _alternative(4, 0.8, motifs={"a": _FULL}),
                _alternative(5, None, motifs={"b": _FULL}),
            ],
        ) == [4, 3, 2, 5]

    def test_a_quality_of_zero_is_not_a_missing_quality(self) -> None:
        """Zusicherung 6: `0.0` steht vor jedem `None` derselben Gruppe. `quality or 0` verliert
        die Unterscheidung lautlos - und zwar in beiden Gruppen."""
        reference = _alternative(1, 0.5, motifs={"a": _FULL})

        assert order_alternatives(
            reference,
            [
                _alternative(2, None, motifs={"a": _FULL}),
                _alternative(3, 0.0, motifs={"a": _FULL}),
                _alternative(4, None, motifs={"b": _FULL}),
                _alternative(5, 0.0, motifs={"b": _FULL}),
            ],
        ) == [3, 2, 5, 4]

    def test_three_shared_motifs_do_not_beat_one(self) -> None:
        """Zusicherung 7, erste Haelfte: die Motivgruppe ist BINAER. Entschieden wird allein
        "mindestens eines"; innerhalb der Gruppe ordnet die Qualitaet."""
        reference = _alternative(1, 0.5, motifs={"a": _FULL, "b": _FULL, "c": _FULL})

        assert order_alternatives(
            reference,
            [
                _alternative(2, 0.2, motifs={"a": _FULL, "b": _FULL, "c": _FULL}),
                _alternative(3, 0.9, motifs={"a": _FULL}),
            ],
        ) == [3, 2]

    def test_the_motif_boundary_of_the_grouping_is_inclusive(self) -> None:
        """Zusicherung 7, zweite Haelfte: die Grenze ist INKLUSIV und fuer alle Motive dieselbe -
        auf BEIDEN Seiten, Bezugsbild wie Kandidat. Genau an der Grenze teilt das Paar ein Motiv,
        einen Gleitkommaschritt darunter nicht mehr."""

        def order(reference_strength: float, candidate_strength: float) -> list[int]:
            return order_alternatives(
                _alternative(1, 0.5, motifs={"a": reference_strength}),
                [
                    _alternative(2, 0.1, motifs={"a": candidate_strength}),
                    _alternative(3, 0.9, motifs={"b": _FULL}),
                ],
            )

        assert order(MOTIF_PRESENCE_THRESHOLD, MOTIF_PRESENCE_THRESHOLD) == [2, 3]
        assert order(MOTIF_PRESENCE_THRESHOLD, _BELOW) == [3, 2]
        assert order(_BELOW, MOTIF_PRESENCE_THRESHOLD) == [3, 2]

    def test_the_input_carries_no_time_at_all(self) -> None:
        """Zusicherung 8: zeitliche Naehe ist KEIN Sortierkriterium - hier strukturell, nicht bloss
        unbenutzt. `AlternativeCandidate` traegt anders als `SelectionCandidate` kein `taken_at`;
        eine spaetere Sortierung nach Zeit muesste erst das Eingabeformat aendern. Der Gegenprobe
        am Endpunkt (zeitlich benachbart, schlechter) steht das nicht entgegen - sie liegt in
        `test_api_photos.py`."""
        assert "taken_at" not in AlternativeCandidate.__dataclass_fields__
        assert "taken_at" in SelectionCandidate.__dataclass_fields__

    def test_a_tie_breaks_over_the_smaller_photo_id_in_every_permutation(self) -> None:
        """Zusicherung 9: der Aufbau traegt ECHTEN Gleichstand (gleiche Gruppe, gleiche Qualitaet;
        einmal mit Wert, einmal ohne), sonst ist der Fall leer. Geprueft ueber ALLE Permutationen
        der Eingabe - eine Implementierung, die die Eingabereihenfolge durchreicht, faellt erst
        dadurch auf."""
        reference = _alternative(1, 0.5, motifs={"a": _FULL})
        candidates = [
            _alternative(5, 0.7, motifs={"a": _FULL}),
            _alternative(3, 0.7, motifs={"a": _FULL}),
            _alternative(4, None, motifs={"a": _FULL}),
            _alternative(2, None, motifs={"a": _FULL}),
        ]

        for permutation in itertools.permutations(candidates):
            assert order_alternatives(reference, permutation) == [3, 5, 2, 4]

    def test_an_empty_candidate_list_stays_empty(self) -> None:
        assert order_alternatives(_alternative(1, 0.5, motifs={"a": _FULL}), []) == []

    def test_a_reference_without_a_carried_motif_leaves_a_plain_quality_order(self) -> None:
        """Traegt das Bezugsbild kein Motiv, teilt niemand eines mit ihm: alle Kandidaten stehen in
        derselben Gruppe, und es bleibt bei Qualitaet absteigend, `None` zuletzt."""
        reference = _alternative(1, 0.5, motifs={"a": _BELOW})

        assert order_alternatives(
            reference,
            [
                _alternative(2, 0.3, motifs={"a": _FULL}),
                _alternative(3, None, motifs={"a": _FULL}),
                _alternative(4, 0.8, motifs={"b": _FULL}),
            ],
        ) == [4, 2, 3]

    def test_the_reference_is_never_among_its_own_alternatives(self) -> None:
        """Das Bezugsbild ist der Ausgangspunkt des Austauschs, nicht sein Ziel - es faellt hier
        heraus und nicht erst in der Anzeige."""
        reference = _alternative(1, 0.5, motifs={"a": _FULL})

        assert order_alternatives(
            reference, [_alternative(1, 0.5, motifs={"a": _FULL}), _alternative(2, 0.1)]
        ) == [2]


class TestTheStructuralGuardAgainstReadingTheDisplayBands:
    """ADR 0091 Punkt 8: kein auswaehlender Codepfad liest die Anzeigebaender aus `motifs.py`.
    Die Grenze der Auswahl ist eine eigene Konstante in `selection.py`, fuer alle Motive gleich -
    ein Band waere eine Rangfolge zwischen Motiven durch die Hintertuer."""

    _SOURCE_DIR = Path(photosort.__file__).resolve().parent
    # `api/photos.py` steht seit Spec 0430 dabei: der Lesepfad liefert `MotifStrengthOut.present`
    # und liest damit erstmals eine AUSWAHLGRENZE - die Datei faellt ab hier unter denselben
    # Waechter wie die auswaehlenden Module. Der Eintrag ist ein PFAD relativ zu `_SOURCE_DIR`,
    # kein flacher Dateiname.
    # `events.py` steht seit Spec 0477 dabei: der Motivwechsel als Trennsignal liest ueber
    # `carried_motifs` erstmals eine AUSWAHLGRENZE und faellt ab hier unter denselben Waechter.
    _SELECTING_MODULES = (
        "selection.py",
        "ranking.py",
        "quality.py",
        "worker.py",
        "api/photos.py",
        "events.py",
    )
    _DISPLAY_BANDS = ("MOTIF_STRENGTH_BAND_STRONG", "MOTIF_STRENGTH_BAND_MEDIUM")

    @pytest.mark.parametrize("module", _SELECTING_MODULES)
    def test_no_selecting_module_reads_a_display_band(self, module: str) -> None:
        source = (self._SOURCE_DIR / module).read_text(encoding="utf-8")

        for band in self._DISPLAY_BANDS:
            assert band not in source, f"{module} liest das Anzeigeband {band}"

    def test_the_presence_threshold_is_named_exactly_once_in_the_source_tree(self) -> None:
        """Zusicherung 26: Die Praesenzgrenze wird als PRAEDIKAT geteilt, nie als Zahl.

        `MOTIF_PRESENCE_THRESHOLD` kommt unter `backend/src/photosort/` an genau EINER Stelle vor
        (ihrer Definition in `selection.py`); jede andere Stelle ruft `motif_is_present`. Ein
        zweites `>=` gegen dieselbe Konstante waere gruen und liefe beim ersten Wechsel auf `>`
        auseinander - und genau die INKLUSIVITAET ist die Zusage (Zusicherung 7)."""
        sources = {
            path.relative_to(self._SOURCE_DIR).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self._SOURCE_DIR.rglob("*.py"))
        }
        naming = sorted(
            name for name, source in sources.items() if "MOTIF_PRESENCE_THRESHOLD" in source
        )

        # Kein anderes Modul nennt die Konstante ueberhaupt.
        assert naming == ["selection.py"], (
            f"Die Praesenzgrenze gehoert ausschliesslich nach selection.py; gefunden in: {naming}"
        )
        # Und innerhalb von `selection.py` wird genau EINMAL gegen sie verglichen - in
        # `motif_is_present`. Ein zweiter Vergleich waere die Stelle, an der die Inklusivitaet
        # spaeter still auseinanderlaeuft.
        selection_source = sources["selection.py"]
        operators = [
            operator
            for operator in (">=", ">", "<=", "<", "==")
            if f"{operator} MOTIF_PRESENCE_THRESHOLD" in selection_source
        ]
        assert operators == [">="], f"Die Grenze wird INKLUSIV gelesen; gefunden: {operators}"
        assert selection_source.count(">= MOTIF_PRESENCE_THRESHOLD") == 1, (
            "Genau ein Vergleich gegen die Praesenzgrenze, und der steht in motif_is_present"
        )

    def test_selection_does_not_name_the_motif_vocabulary_at_all(self) -> None:
        """`selection.py` nennt `motifs.py` ueberhaupt nicht: es kennt nur Schluessel und eine
        Grenze, kein Vokabular."""
        source = (self._SOURCE_DIR / "selection.py").read_text(encoding="utf-8")

        assert "photosort.motifs" not in source
        assert "motifs.py" not in source

    def test_the_display_bands_still_exist(self) -> None:
        """Selbstschutz: ohne diesen Fall bliebe der Waechter oben auch gruen, wenn die Konstanten
        umbenannt werden oder ganz verschwinden."""
        source = (self._SOURCE_DIR / "motifs.py").read_text(encoding="utf-8")

        for band in self._DISPLAY_BANDS:
            assert band in source


class TestOnlyTheMeasuringPathPassesItsOwnThreshold:
    """Die durchreichbare Praesenzgrenze steht AUSSCHLIESSLICH dem Messweg offen.

    Sie ist seit Spec 0506 Block E durchreichbar, damit ein rein lesender Messlauf sie variieren
    kann. Die Eindaemmung des Sicherheitskonzepts (Abschnitt "Standortdaten") haengt daran, dass
    JEDER AUSWAEHLENDE Pfad gegen die eine, fuer alle Motive gleiche Konstante prueft: Ein
    Aufrufer, der selbst eine Grenze mitgibt, stellte eine zweite Auswahlgrenze im selben Produkt
    auf, und zwei Motive traeten dann ueber ihre Zahlen gegeneinander an. Zulaessig ist genau eine
    Stelle - die Weitergabe in `events.py::_motif_picture`, deren Wert seinerseits nur aus dem
    injizierbaren Parameter von `motif_change_starts` stammt."""

    _SOURCE_DIR = Path(photosort.__file__).resolve().parent
    _PREDICATES = ("motif_is_present", "carried_motifs")
    _ALLOWED = {"selection.py", "events.py"}

    def _modules_passing_a_threshold(self) -> set[str]:
        passing: set[str] = set()
        for path in sorted(self._SOURCE_DIR.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                called = node.func.id if isinstance(node.func, ast.Name) else None
                if called in self._PREDICATES and len(node.args) + len(node.keywords) > 1:
                    passing.add(path.relative_to(self._SOURCE_DIR).as_posix())
        return passing

    def test_only_the_measuring_path_ever_passes_a_threshold_of_its_own(self) -> None:
        assert self._modules_passing_a_threshold() <= self._ALLOWED, (
            "Ein auswaehlender Pfad gibt eine eigene Praesenzgrenze mit - die Eindaemmung "
            "'eine Grenze fuer alle Motive' haengt daran, dass er es nicht tut"
        )

    def test_the_walker_actually_finds_the_two_allowed_call_sites(self) -> None:
        """Gegenprobe: Ohne sie bestuende der Waechter oben auch dann, wenn der Aufruf-Sucher gar
        nichts findet - umbenannte Funktion, geaenderte Verzeichnisstruktur."""
        assert self._modules_passing_a_threshold() == self._ALLOWED


class TestTheResultIsDeterministic:
    @staticmethod
    def _events() -> list[SelectionEvent]:
        """NICHT-TRIVIAL, sonst bestuende der Fall auch bei einer Implementierung, die ueber ein
        `set` iteriert: mehr Kandidaten als Plaetze, ein echter Qualitaets-Gleichstand (Fotos 103
        und 104) und zwei Events mit gleichem `n_i`."""
        return [
            _event(
                10,
                1,
                [
                    _candidate(101, 0.90, motifs={"a": _FULL}),
                    _candidate(102, 0.80, motifs={"b": _FULL}),
                    _candidate(103, 0.70, motifs={"a": _FULL}),
                    _candidate(104, 0.70, motifs={"a": _FULL}),
                    _candidate(105, 0.60, motifs={"c": _FULL}),
                ],
            ),
            _event(
                20,
                2,
                [
                    _candidate(201, 0.95, motifs={"a": _FULL}),
                    _candidate(202, 0.85, motifs={"a": _FULL}),
                    _candidate(203, 0.75, motifs={"b": _FULL}),
                    _candidate(204, 0.65, motifs={"b": _FULL}),
                    _candidate(205, 0.55, motifs={"a": _FULL, "c": _FULL}),
                ],
            ),
            _event(
                30,
                3,
                [
                    _candidate(300 + index, 0.9 - index / 20, motifs={"a": _FULL})
                    for index in range(8)
                ],
            ),
        ]

    @pytest.mark.parametrize(
        ("event_order", "candidate_order"),
        [
            pytest.param((0, 1, 2), "wie-eingegeben", id="unveraendert"),
            pytest.param((2, 1, 0), "umgekehrt", id="events-und-kandidaten-umgekehrt"),
            pytest.param((1, 2, 0), "rotiert", id="events-rotiert-kandidaten-rotiert"),
            pytest.param((2, 0, 1), "umgekehrt", id="zweite-mischung"),
        ],
    )
    def test_the_full_mapping_is_the_same_under_any_input_order(
        self, event_order: tuple[int, ...], candidate_order: str
    ) -> None:
        """Verglichen wird die VOLLSTAENDIGE Abbildung samt Plaetzen, nicht die Fotomenge."""
        expected = _draft(self._events(), target=9)

        source = self._events()
        permuted = []
        for index in event_order:
            event = source[index]
            candidates = list(event.candidates)
            if candidate_order == "umgekehrt":
                candidates.reverse()
            elif candidate_order == "rotiert":
                candidates = candidates[2:] + candidates[:2]
            permuted.append(_event(event.event_id, event.position, candidates))

        assert _draft(permuted, target=9) == expected


class TestTheOverloadBoundary:
    def test_a_large_event_at_full_quota_stays_within_the_test_runtime(self) -> None:
        """Die Ueberlastschranke des synchronen Endpunkts (Sicherheitsauflage S5): die
        Aehnlichkeitsabwertung wird je Kandidat FORTGESCHRIEBEN, nicht bei jeder Bewertung erneut
        ueber alle bereits Gewaehlten summiert. Ergebnisgleich, aber `O(n·k)` statt `O(n·k²)`; in
        der quadratischen Form kostete dieser Aufbau rund 10⁹ Bewertungen synchron im Request."""
        size = 2_000
        candidates = [
            _candidate(
                index + 1,
                1.0 - index / (size + 1),
                motifs={"a": _FULL if index % 2 else _BELOW},
                offset=index * SIMILARITY_TIME_WINDOW / 10,
            )
            for index in range(size)
        ]

        result = select_album_draft([_event(1, 1, candidates)], target=size)

        # Der eine Fall ohne `_draft`: die Invariantenpruefung ueber 2000 Kandidaten waere selbst
        # der teuerste Teil und verdeckte die Laufzeitaussage (siehe `_draft`).
        assert len(result) == size
