"""Ereignis-Gruppierung: Ereignis zu einer Zeit, die Rundung an genau einer Stelle, Zellen eines
gebauten Ereignisses.
(Aufgeteilt aus test_events.py, Spec 0651.)
"""

from __future__ import annotations

import ast
from datetime import timedelta
from itertools import permutations
from pathlib import Path

from photosort.events import (
    EventSpan,
    event_for_time,
)
from tests.support.event_grouping import T0

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "photosort"


def _span(event_id: int, start_minutes: int, end_minutes: int) -> EventSpan:
    """Eine Eventspanne relativ zu `T0`, in Minuten. Zonenlos wie `Photo.taken_at`."""
    return EventSpan(
        event_id=event_id,
        started_at=T0 + timedelta(minutes=start_minutes),
        ended_at=T0 + timedelta(minutes=end_minutes),
    )


class TestEventForTime:
    """`event_for_time` ordnet eine Aufnahmezeit einem Event zu - fuer die Fotos, die der Nutzer
    aufgenommen hat, ohne dass der Lauf ihnen eine Rangzeile gegeben haette.

    REIN, ohne Session und ohne Uhr: dieselbe Eingabe liefert immer dieselbe Zuordnung."""

    def test_a_time_inside_a_span_belongs_to_that_event(self) -> None:
        spans = [_span(7, 0, 60), _span(8, 120, 180)]

        assert event_for_time(spans, T0 + timedelta(minutes=30)) == 7

    def test_containment_beats_proximity(self) -> None:
        """Zusicherung 10: Eine Zeit KURZ VOR dem Ende eines langen Events gehoert diesem Event -
        auch wenn der Abstand zum `started_at` des naechsten kleiner ist als der zum eigenen
        `started_at`. Genau diesen Fall beantwortet eine Abstandsmessung allein gegen `started_at`
        falsch."""
        long_event = _span(1, 0, 600)
        following = _span(2, 610, 640)
        # 599 Minuten vom eigenen Anfang entfernt, aber nur 11 vom Anfang des naechsten.
        moment = T0 + timedelta(minutes=599)

        assert event_for_time([long_event, following], moment) == 1

    def test_both_bounds_are_inclusive(self) -> None:
        spans = [_span(3, 0, 60)]

        assert event_for_time(spans, T0) == 3
        assert event_for_time(spans, T0 + timedelta(minutes=60)) == 3

    def test_touching_spans_go_to_the_earlier_event(self) -> None:
        """Zusicherung 11: `ended_at(A) == started_at(B)` ist ueber zwei Aufnahmen derselben
        Sekunde mit Ortssprung erreichbar. Ohne diesen Fall haengt das Ergebnis an der
        Aufzaehlungsreihenfolge."""
        earlier = _span(1, 0, 60)
        later = _span(2, 60, 120)
        touching_moment = T0 + timedelta(minutes=60)

        assert event_for_time([earlier, later], touching_moment) == 1
        assert event_for_time([later, earlier], touching_moment) == 1

    def test_an_equal_distance_goes_to_the_earlier_event(self) -> None:
        """Zusicherung 12: Die Luecke zwischen den beiden Events ist symmetrisch - die Zeit liegt
        genau in ihrer Mitte."""
        earlier = _span(1, 0, 60)
        later = _span(2, 80, 140)
        middle = T0 + timedelta(minutes=70)

        assert event_for_time([earlier, later], middle) == 1
        assert event_for_time([later, earlier], middle) == 1

    def test_a_time_between_two_events_goes_to_the_nearer_one(self) -> None:
        earlier = _span(1, 0, 60)
        later = _span(2, 100, 160)

        assert event_for_time([earlier, later], T0 + timedelta(minutes=95)) == 2
        assert event_for_time([earlier, later], T0 + timedelta(minutes=65)) == 1

    def test_a_single_event_takes_every_time(self) -> None:
        spans = [_span(5, 100, 200)]

        assert event_for_time(spans, T0) == 5
        assert event_for_time(spans, T0 + timedelta(minutes=150)) == 5
        assert event_for_time(spans, T0 + timedelta(days=30)) == 5

    def test_a_time_before_the_first_and_after_the_last_event(self) -> None:
        spans = [_span(1, 0, 60), _span(2, 120, 180)]

        assert event_for_time(spans, T0 - timedelta(days=1)) == 1
        assert event_for_time(spans, T0 + timedelta(days=1)) == 2

    def test_an_empty_span_list_answers_none(self) -> None:
        assert event_for_time([], T0) is None

    def test_the_result_does_not_depend_on_the_order_of_the_spans(self) -> None:
        """Die Spannenliste kommt aus einer Abfrage - ihre Reihenfolge ist ohne `ORDER BY` nicht
        zugesichert. Jede Permutation muss dieselbe Zuordnung liefern."""
        spans = [_span(1, 0, 60), _span(2, 120, 180), _span(3, 300, 360)]
        moment = T0 + timedelta(minutes=200)

        for permutation in permutations(spans):
            assert event_for_time(list(permutation), moment) == 2


def _modules_building_a_cell(*, with_a_digit_literal: bool) -> dict[str, int]:
    """Je Quelldatei die Zahl der Stellen darin, die eine ORTSZELLE bilden.

    `with_a_digit_literal` trennt die beiden Faelle, um die es geht: `round(wert, 2) + 0.0` ist
    eine eigene Stellschraube und darf nirgends stehen, `round(wert, PLACE_CELL_DIGITS) + 0.0`
    ist die eine benannte.

    Gesucht wird die Signatur `round(<etwas>, <Zahlliteral>) + 0.0` - gezaehlt wird die FORM, nicht
    der Wert. Die Addition von `0.0` normalisiert `-0.0` und ist genau das, was aus einer beliebigen
    Rundung eine Zelle macht; ein blosses `round(wert, 3)` auf einen Qualitaetswert faellt dadurch
    nicht mit herein und soll es auch nicht.

    Eine Stelle, die heute zufaellig ebenfalls auf zwei Stellen rundet, ist genau der Fall, der bei
    der naechsten Aenderung der Koernung zurueckbleibt."""
    found: dict[str, int] = {}
    for path in sorted(SRC_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)):
                continue
            if not (isinstance(node.right, ast.Constant) and node.right.value == 0.0):
                continue
            call = node.left
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
                continue
            if call.func.id != "round" or len(call.args) < 2:
                continue
            digits = call.args[1]
            literal = isinstance(digits, ast.Constant) and isinstance(digits.value, int)
            if literal is with_a_digit_literal:
                name = path.relative_to(SRC_DIR).as_posix()
                found[name] = found.get(name, 0) + 1
    return found


class TestTheRoundingStandsAtExactlyOnePlace:
    """ADR 0102 Punkt 2: die Koernung der Ortszelle ist EINE benannte Konstante, nicht ueber den
    Code verteilt. Sie ist die Stellschraube der Sicherheitsentscheidung - wie grob gefragt und
    abgelegt wird, gehoert dorthin und nicht in die Bequemlichkeit einer Aufrufstelle.

    Ein Verhaltenstest roetete hier nichts: eine zweite, zufaellig gleich rundende Stelle liefert
    heute dieselben Werte und driftet erst bei der naechsten Aenderung ab. Die Zusage ist eine
    Aussage ueber eine ANZAHL und braucht deshalb einen strukturellen Waechter."""

    def test_the_old_constant_name_is_gone_from_the_source_tree(self) -> None:
        """`events.py::_EVENT_PLACE_COORDINATE_DIGITS` ist in `places.PLACE_CELL_DIGITS`
        aufgegangen. Bliebe der alte Name irgendwo stehen, gaebe es wieder zwei Stellschrauben."""
        hits = [
            path.relative_to(SRC_DIR).as_posix()
            for path in sorted(SRC_DIR.rglob("*.py"))
            if "_EVENT_PLACE_COORDINATE_DIGITS" in path.read_text(encoding="utf-8")
        ]

        assert hits == []

    def test_no_module_builds_a_cell_with_a_digit_literal_of_its_own(self) -> None:
        """Die Zusage aus ADR 0102 Punkt 2 in ihrer pruefbaren Form: nirgends im Quellbaum steht
        eine zweite Rundung mit STELLENLITERAL. Eine solche Stelle liefert heute dieselben Werte
        wie `place_cell` und bleibt bei der naechsten Aenderung der Koernung zurueck - lautlos."""
        assert _modules_building_a_cell(with_a_digit_literal=True) == {}

    def test_every_named_cell_rounding_lives_in_places(self) -> None:
        """Die Gegenprobe zum Fall darueber: ohne sie bestuende er auch dann, wenn der Walker gar
        nichts faende - etwa nach einer Umbenennung von `round`, einem Wegfall der
        `-0.0`-Normalisierung oder einem Umbau des Quellverzeichnisses.

        VIER Stellen in EINER Datei: zwei Zellrundungen mit je getrennter Breite und Laenge.
        `place_cell` ist die Koernung, mit der gefragt und abgelegt wird, `landmark_place_cell` die
        groebere, mit der eine Koordinate das System verlaesst (Spec 0469, S1). Beide tragen eine
        eigene benannte Konstante und stehen nebeneinander; die Zusage aus ADR 0102 Punkt 2 ist
        nicht "genau eine Rundung", sondern "keine mit Stellenliteral und keine ausserhalb dieses
        Moduls"."""
        assert _modules_building_a_cell(with_a_digit_literal=False) == {"places.py": 4}

    def test_the_guard_would_catch_a_second_rounding(self) -> None:
        """Mikrotest auf den Walker selbst, gegen einen ausgeschriebenen Verstoss - sonst belegt
        keiner der beiden Faelle oben, dass die Form ueberhaupt erkannt wird."""
        offender = ast.parse("cell = (round(lat, 2) + 0.0, round(lon, 2) + 0.0)")
        matches = [
            node
            for node in ast.walk(offender)
            if isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Add)
            and isinstance(node.right, ast.Constant)
            and node.right.value == 0.0
        ]

        assert len(matches) == 2
