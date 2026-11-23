"""Ereignis-Gruppierung: die Trennursache je Grenze (Spec 0506, ADR 0117 Punkt 4).
(Aufgeteilt aus test_events.py, Spec 0651.)
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from photosort import events as events_module
from photosort.events import (
    BOUNDARY_CAUSES,
    BOUNDARY_DURATION,
    BOUNDARY_EXTENT,
    BOUNDARY_LANDMARK,
    BOUNDARY_MOTIF_CHANGE,
    BOUNDARY_STEP,
    BOUNDARY_TIME_GAP,
    EventCandidate,
    EventSpanSignal,
    ExtentSignal,
    StepDistanceSignal,
    TimeGapSignal,
    build_events,
    default_signals,
    explain_events,
    motif_change_starts,
)
from photosort.selection import MOTIF_PRESENCE_THRESHOLD
from tests.support.event_grouping import (
    _NO_MERGING,
    EPSILON_METERS,
    EPSILON_TIME,
    T0,
    _AlwaysSignal,
    _at,
    _explain,
    _extent_max,
    _max_span,
    _measured_candidate,
    _motif_candidates,
    _north,
    _picture,
    _placeless_candidate,
    _step_max,
    _time_gap,
    _UnderEveryConfirmingWindow,
    _window,
)


class TestEverySignalCarriesAName:
    def test_the_default_set_uses_only_names_from_the_closed_stock(self) -> None:
        """Ein Signal ohne Namen aus dem Vorrat faellt in der Statistik unter den Tisch, ohne dass
        eine Summe kleiner wuerde - der Bericht waere dann still unvollstaendig."""
        names = [signal.name for signal in default_signals()]

        assert len(names) == len(set(names)), "zwei gleichnamige Signale sind eine Ursache"
        assert set(names) <= set(BOUNDARY_CAUSES)

    def test_the_motif_change_has_its_own_name_in_the_stock(self) -> None:
        """Der Motivwechsel ist kein Eintrag in `default_signals()` und eroeffnet seit ADR 0119
        auch kein Event mehr. Sein Name bleibt trotzdem im Vorrat: Er vermerkt eine Grenze mit, und
        "war beteiligt" ist die Zahl, an der eine spaetere Aenderung dieser Entscheidung gemessen
        wuerde."""
        assert BOUNDARY_MOTIF_CHANGE in BOUNDARY_CAUSES
        assert BOUNDARY_MOTIF_CHANGE not in {signal.name for signal in default_signals()}


class TestTheCauseSetPerBoundary:
    def test_the_first_segment_carries_no_cause_even_when_a_signal_reports_one(self) -> None:
        """DIE AUSNAHME HAENGT AN DER POSITION, nicht an `TimeGapSignal`: Das eingeschleuste,
        IMMER trennende Signal meldet auch am ersten Foto, und die Menge bleibt trotzdem leer.
        Ohne diese Verankerung braucht jedes kuenftige Signal seine eigene Ausnahme."""
        candidates = [_placeless_candidate(index, _at(minutes=index)) for index in range(3)]

        formation = _explain(candidates, [_AlwaysSignal()])

        assert len(formation.events) == 3
        assert formation.causes == (frozenset(), frozenset({"immer"}), frozenset({"immer"}))

    def test_the_twin_empty_at_the_start_and_zeitluecke_at_the_second_boundary(self) -> None:
        """Der Zwilling in IDENTISCHER Lage: Dieselbe Zeitluecke, die am Index 0 keine Ursache
        ergibt, ergibt an der zweiten Grenze `zeitluecke`. Ohne diesen Fall truege jeder Lauf eine
        erfundene Zeitluecke in der Statistik."""
        gap = _time_gap() + EPSILON_TIME
        candidates = [_placeless_candidate(1, T0), _placeless_candidate(2, T0 + gap)]

        formation = _explain(candidates, [TimeGapSignal()])

        assert len(formation.events) == 2
        assert formation.causes == (frozenset(), frozenset({BOUNDARY_TIME_GAP}))

    def test_two_signals_at_the_same_boundary_yield_a_set_of_two(self) -> None:
        """Die Grenze traegt die MENGE, nie ein einzelnes Signal: Der Durchlauf wertet alle aus,
        und ein Bericht mit einer Ursache je Grenze unterschluege die zweite."""
        gap = _time_gap() + EPSILON_TIME
        far = _step_max() + EPSILON_METERS
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, T0 + gap, lat=_north(far)),
        ]

        formation = _explain(candidates, [TimeGapSignal(), StepDistanceSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_TIME_GAP, BOUNDARY_STEP})

    def test_the_duration_reports_under_its_own_name(self) -> None:
        """Die Dauergrenze ist an die Stelle des Kalendertags getreten; ohne ihren Namen im Vorrat
        stuende in Block B eine Grenze ohne Ursache."""
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, T0 + _max_span() + EPSILON_TIME),
        ]

        formation = _explain(candidates, [EventSpanSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_DURATION})

    def test_the_landmark_keeps_its_name_in_the_supply_without_a_signal_behind_it(self) -> None:
        """Die EHRLICHE NULL (ADR 0118 Punkt 2): `sehenswuerdigkeit` bleibt im Wortschatz, damit die
        Nachmessung ihre Zeile behaelt und mit der Ausgangsmessung vergleichbar bleibt. Verschwaende
        das Symbol, koennte kein Leser unterscheiden, ob die Ursache weggefallen oder nie gemessen
        worden ist. Kein Signal traegt den Namen mehr - sonst waere die Null keine."""
        assert BOUNDARY_LANDMARK in BOUNDARY_CAUSES
        assert all(signal.name != BOUNDARY_LANDMARK for signal in default_signals())

    def test_the_extent_reports_under_its_own_name(self) -> None:
        far = _extent_max() + EPSILON_METERS
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(seconds=1), lat=_north(far)),
        ]

        formation = _explain(candidates, [ExtentSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_EXTENT})

    def test_a_run_without_any_candidate_has_neither_events_nor_causes(self) -> None:
        formation = _explain([])

        assert formation.events == ()
        assert formation.causes == ()

    def test_every_cause_of_a_full_signal_run_stays_inside_the_closed_stock(self) -> None:
        """Als Nachsatz ueber der ganzen Fallmenge, nicht als Einzelfall: Ein neues Signal ohne
        Eintrag im Vorrat wird hier rot, nicht erst im Bericht."""
        gap = _time_gap() + EPSILON_TIME
        far = _step_max() + EPSILON_METERS
        candidates = [
            _measured_candidate(1, T0, landmark_name="Zugspitze"),
            _measured_candidate(2, _at(seconds=1), landmark_name="Eibsee"),
            _measured_candidate(3, T0 + gap, lat=_north(far)),
            _placeless_candidate(4, T0 + gap + _max_span() + EPSILON_TIME),
        ]

        formation = _explain(candidates)

        for cause in formation.causes:
            assert cause <= set(BOUNDARY_CAUSES)


class TestTheGroupingNoLongerDependsOnTheFirstStage(_UnderEveryConfirmingWindow):
    """DIE EIGENTLICHE ZUSAGE von ADR 0119, in ihrer starken Form: `explain_events` liefert unter
    einem nie erreichbaren Bestaetigungsfenster DIESELBE Eventfolge wie am Betriebswert -
    verschieden sind allein die Ursachenmengen.

    Gerechnet wird mit den Mitteln des Laufs: dasselbe `explain_events`, nur mit einem Fenster
    groesser als die Zahl der Kandidatenfotos. Mehr aufeinanderfolgende mitredende Fotos als Fotos
    kann es nicht geben, also bestaetigt kein Wechsel - ohne einen Abschaltpfad im Produktivcode."""

    def _mixed_run(self) -> list[EventCandidate]:
        """Vier Abschnitte: ein Bezugsblock, ein zweiter hinter einer Zeitluecke, an der ZUGLEICH
        das Motiv wechselt, ein dritter mit einem Motivwechsel OHNE jedes meldende Signal, und ein
        vierter hinter einem Schritt ohne Motivwechsel.

        Ohne den Zusammenfall im zweiten Abschnitt waere der Vergleich unten vakuum-gleich: Die
        beiden Gliederungen truegen dann auch dieselben Ursachenmengen."""
        window = _window()
        gap = _time_gap() + EPSILON_TIME
        far = _step_max() + EPSILON_METERS
        first = [(T0 + index * EPSILON_TIME, 0.0, _picture("a")) for index in range(window)]
        behind_the_gap = [
            (first[-1][0] + gap + index * EPSILON_TIME, 0.0, _picture("a", "b"))
            for index in range(window)
        ]
        without_a_signal = [
            (behind_the_gap[-1][0] + (index + 1) * EPSILON_TIME, 0.0, _picture("a", "c"))
            for index in range(window)
        ]
        behind_the_step = [
            (without_a_signal[-1][0] + (index + 1) * EPSILON_TIME, far, _picture("a", "c"))
            for index in range(window)
        ]
        return [
            _measured_candidate(index, taken_at, lat=_north(north), motif_strengths=picture)
            for index, (taken_at, north, picture) in enumerate(
                [*first, *behind_the_gap, *without_a_signal, *behind_the_step]
            )
        ]

    def test_the_lay_carries_both_kinds_of_motif_change(self) -> None:
        """Der Waechter unter dieser Klasse: einer der beiden Wechsel faellt auf eine Signalgrenze,
        der andere auf keine. Faellt einer der beiden weg, messen die Faelle darunter die Haelfte
        der Zusage nicht mehr - und blieben gruen."""
        candidates = self._mixed_run()

        assert motif_change_starts(candidates) == frozenset({_window(), 2 * _window()})

    def test_the_unreachable_window_yields_the_very_same_events(self) -> None:
        """(b) Gleiche Fotomengen, gleiche Grenzen, gleiche Positionen - die Gliederung haengt
        nicht mehr an der ersten Stufe."""
        candidates = self._mixed_run()

        operating = _explain(candidates)
        switched_off = _explain(candidates, confirming_photos=len(candidates) + 1)

        assert [(event.photo_ids, event.position) for event in switched_off.events] == [
            (event.photo_ids, event.position) for event in operating.events
        ]

    def test_only_the_cause_sets_differ_and_only_by_the_motif_change(self) -> None:
        """Die Kehrseite des Falls darueber: Etwas UNTERSCHEIDET sich, sonst maesse er nichts - und
        es ist ausschliesslich der Vermerk."""
        candidates = self._mixed_run()

        operating = _explain(candidates)
        switched_off = _explain(candidates, confirming_photos=len(candidates) + 1)

        assert operating.causes != switched_off.causes
        assert tuple(cause - {BOUNDARY_MOTIF_CHANGE} for cause in operating.causes) == (
            switched_off.causes
        )

    def test_a_change_on_a_reported_boundary_joins_its_cause_set(self) -> None:
        """(c) Der Vermerk selbst: Der Motivwechsel faellt mit der Zeitluecke zusammen und steht
        NEBEN ihr in der Menge - nie an ihrer Stelle."""
        formation = _explain(self._mixed_run())

        assert formation.causes[1] == frozenset({BOUNDARY_TIME_GAP, BOUNDARY_MOTIF_CHANGE})

    def test_a_change_without_a_reporting_signal_reaches_no_later_boundary(self) -> None:
        """(d) DER VERMERK WIRD NICHT AUFGESCHOBEN: Der zweite Wechsel faellt auf einen Index, an
        dem kein Signal meldet. Er wird verworfen - die naechste Grenze, die der Schritt zieht,
        nennt nur den Schritt. Ein nachgetragener Vermerk behauptete eine Mitursache an einer
        Stelle, an der der Wechsel nicht stattgefunden hat."""
        formation = _explain(self._mixed_run())

        assert len(formation.events) == 3
        assert formation.causes[2] == frozenset({BOUNDARY_STEP})

    def test_no_cause_set_of_the_run_carries_the_motif_change_alone(self) -> None:
        """Die zweite maschinell gepruefte Zusage, hier an einer Lage mit beiden Arten von
        Wechsel. Als Nachsatz ueber JEDEM Fall dieser Sektion steht sie in `_explain`."""
        formation = _explain(self._mixed_run())

        assert any(BOUNDARY_MOTIF_CHANGE in cause for cause in formation.causes), (
            "sonst misst der Fall nichts"
        )
        for cause in formation.causes:
            assert cause != frozenset({BOUNDARY_MOTIF_CHANGE})


class TestBuildEventsAndTheExplainingFormAreTheSameRun:
    """Ein zweiter Rechenweg fuer dieselbe Gliederung liefe auseinander - und dann maesse Block B
    die Grenzen einer Gliederung, die so nie entstanden ist."""

    def test_the_same_candidates_yield_the_same_events(self) -> None:
        gap = _time_gap() + EPSILON_TIME
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(seconds=30)),
            _measured_candidate(3, T0 + gap),
        ]

        assert list(explain_events(candidates).events) == build_events(candidates)


class TestTheMotifRuleTakesItsTwoFestlegungenInjectably:
    """Fensterlaenge und Praesenzgrenze sind INJIZIERBAR - die Voraussetzung dafuer, dass die
    Empfindlichkeitsmessung (Spec 0506, Block E) den ECHTEN Rechenweg variiert statt eine
    Nachbildung zu messen.

    Ohne Angabe gilt weiterhin der Betriebswert, und zwar als MODULATTRIBUT gelesen: Ein
    Default-Parameterwert in der Signatur baende ihn beim Import, `monkeypatch.setattr` liefe ins
    Leere und die Variation waere wirkungslos - gruen, aber ohne Wirkung.

    Die Staerken dieser Faelle sind FREI GEWAEHLT und stehen zu `MOTIF_PRESENCE_THRESHOLD` in
    keinem Verhaeltnis: Jeder Fall gibt die Grenze, gegen die er misst, selbst mit."""

    _CARRIED = 1.0
    _MIDDLE = 0.8
    _ABSENT = 0.0

    def _sequence(self, length: int, *, strength: float | None = None) -> list[EventCandidate]:
        """Ein Bezugsfoto, dann `length` Fotos, in denen "b" mit mittlerer Staerke dazukommt.

        Ob daraus ein Wechsel wird, entscheidet allein die mitgegebene Grenze; wie viele Fotos ihn
        bestaetigen muessen, allein die mitgegebene Fensterlaenge.

        `strength` waehlt die Staerke von "b". Ein Fall, der KEINE Grenze mitgibt und trotzdem
        einen Wechsel braucht, gibt `_CARRIED` mit: Diese Staerke liegt am oberen Rand der Skala
        und wird unter JEDEM Betriebswert getragen. Mit der mittleren Staerke haenge er still am
        heutigen `MOTIF_PRESENCE_THRESHOLD` und bliebe nach einer Verschiebung vakuum-gruen."""
        reference = {"a": self._CARRIED, "b": self._ABSENT}
        deviating = {"a": self._CARRIED, "b": self._MIDDLE if strength is None else strength}
        return _motif_candidates([reference, *([deviating] * length)])

    def _sequence_behind_a_gap(self, length: int) -> list[EventCandidate]:
        """Dieselbe Folge, aber mit einer ZEITLUECKE genau am Index des Wechsels.

        Seit ADR 0119 wirkt sich die erste Stufe nur noch auf die Ursachenmenge einer Grenze aus,
        die ein Signal ohnehin meldet. Ohne diese Grenze waere an der Gliederung nicht mehr
        abzulesen, ob die beiden Festlegungen ueberhaupt durchgereicht werden."""
        return [
            replace(candidate, taken_at=candidate.taken_at + (_time_gap() + EPSILON_TIME))
            if candidate.photo_id >= 1
            else candidate
            for candidate in self._sequence(length)
        ]

    def test_the_window_length_comes_from_the_argument_not_from_the_constant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Modulkonstante steht auf einem Wert, unter dem die Folge NICHT bestaetigt - und das
        Argument setzt sich durch. Andersherum bliebe der Fall auch dann gruen, wenn das Argument
        gar nicht gelesen wird."""
        monkeypatch.setattr(events_module, "MOTIF_CHANGE_CONFIRMING_PHOTOS", 5)
        candidates = self._sequence(2)

        assert motif_change_starts(candidates, motif_presence_threshold=self._MIDDLE) == frozenset()
        assert motif_change_starts(
            candidates, confirming_photos=2, motif_presence_threshold=self._MIDDLE
        ) == frozenset({1})

    def test_the_presence_threshold_comes_from_the_argument_too(self) -> None:
        """Dieselbe Folge, dieselbe Fensterlaenge, nur die Grenze wandert: Ueber der mittleren
        Staerke traegt kein Foto "b", und es gibt gar keinen Wechsel."""
        candidates = self._sequence(2)

        assert motif_change_starts(
            candidates, confirming_photos=2, motif_presence_threshold=self._MIDDLE
        ) == frozenset({1})
        assert (
            motif_change_starts(
                candidates, confirming_photos=2, motif_presence_threshold=self._CARRIED
            )
            == frozenset()
        )

    def test_without_arguments_the_module_attributes_apply(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Der Zwilling gegen einen gebundenen Default: Das verschobene Modulattribut MUSS wirken,
        sonst ist die Konstante beim Import eingefroren."""
        candidates = self._sequence(4, strength=self._CARRIED)
        monkeypatch.setattr(events_module, "MOTIF_CHANGE_CONFIRMING_PHOTOS", 2)

        with_two = motif_change_starts(candidates)

        monkeypatch.setattr(events_module, "MOTIF_CHANGE_CONFIRMING_PHOTOS", 5)
        with_five = motif_change_starts(candidates)

        assert with_two != with_five
        assert with_five == motif_change_starts(candidates, confirming_photos=5)

    def test_the_operating_point_is_unchanged_by_the_new_parameters(self) -> None:
        """KEINE VERHALTENSAENDERUNG am unveraenderten Wert - die Zusage, unter der diese
        Injizierbarkeit ueberhaupt eingebaut werden durfte. Geprueft ueber eine Folge, die unter
        den Betriebswerten tatsaechlich trennt: eine Folge ohne jeden Start waere hier
        vakuum-gruen."""
        candidates = self._sequence(
            events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS, strength=self._CARRIED
        )
        threshold = MOTIF_PRESENCE_THRESHOLD

        assert motif_change_starts(candidates) == motif_change_starts(
            candidates,
            confirming_photos=events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS,
            motif_presence_threshold=threshold,
        )
        assert motif_change_starts(candidates) == frozenset({1})

    def test_the_explaining_form_hands_both_through(self) -> None:
        """`explain_events` reicht beide weiter - sonst kann die Messung den Vermerk nicht
        variieren und misst unter jeder Kombination dieselben Zahlen.

        Abgelesen wird seit ADR 0119 an der URSACHENMENGE, nicht mehr an der Gliederung: Die
        Zeitluecke zieht die Grenze in beiden Laeufen, und nur unter dem kurzen Fenster steht
        `motivwechsel` daneben."""
        candidates = self._sequence_behind_a_gap(2)

        # Stufe 3 bleibt draussen (`_NO_MERGING`): Der Fall misst den Durchlauf, und das
        # Zusammenlegen zoege das fuehrende Einzelfoto sonst wieder ein.
        narrow = explain_events(
            candidates,
            confirming_photos=2,
            motif_presence_threshold=self._MIDDLE,
            min_event_photos=_NO_MERGING,
        )
        wide = explain_events(
            candidates,
            confirming_photos=5,
            motif_presence_threshold=self._MIDDLE,
            min_event_photos=_NO_MERGING,
        )

        assert len(narrow.events) == len(wide.events) == 2
        assert narrow.causes[1] == frozenset({BOUNDARY_TIME_GAP, BOUNDARY_MOTIF_CHANGE})
        assert wide.causes[1] == frozenset({BOUNDARY_TIME_GAP})

    def test_the_explaining_form_without_arguments_is_the_run_itself(self) -> None:
        candidates = self._sequence(
            events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS, strength=self._CARRIED
        )

        assert explain_events(candidates) == explain_events(
            candidates,
            confirming_photos=events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS,
            motif_presence_threshold=MOTIF_PRESENCE_THRESHOLD,
        )


class TestTheFourAdmissibleStatementsAboutTheNumbers:
    """Die EINZIGEN vier Aussagen, die ein Test ueber die sieben Zahlwerte treffen darf - und alle
    vier sind Ungleichungen. Jede fuenfte waere eine Spiegelung des Codes und machte die naechste
    Kalibrierung zu einem Testumbau."""

    def test_a_segment_of_one_photo_is_below_the_minimum(self) -> None:
        """Bei `1` waere kein Segment je zu klein, Stufe 3 bliebe wirkungslos, und die Messung in
        Block B stuende dauerhaft auf null."""
        assert events_module.MIN_EVENT_PHOTOS >= 2

    def test_the_merge_gap_reaches_beyond_the_time_gap(self) -> None:
        """Waere sie nicht groesser, koennte Stufe 3 keine einzige Zeitluecken-Grenze aufloesen -
        die Stufe liefe, ohne je etwas zu tun."""
        assert events_module.MERGE_MAX_GAP > events_module.EVENT_TIME_GAP

    def test_the_maximum_span_stays_below_a_day(self) -> None:
        """Die Vorbedingung der Ueberschriftenform `23:40-01:15 Uhr`: Ab einem Tag waere die
        Spanne ohne Datumsangabe mehrdeutig."""
        assert events_module.EVENT_MAX_SPAN < timedelta(hours=24)

    def test_the_merge_extent_reaches_beyond_the_splitting_extent(self) -> None:
        """Waere sie nicht groesser, praefte Riegel (c) dieselbe Bedingung, deren Ueberschreitung
        die Trennung ausgeloest hat - fuer ausdehnungsgetrennte Segmente waere Stufe 3 damit
        strukturell unpassierbar. Eine Ungleichung, kein Zahlwert: WIE viel groesser, ist eine
        Kalibrierungsfrage und steht als Herleitung an der Konstante."""
        assert events_module.MERGE_EXTENT_MAX_METERS > events_module.EVENT_EXTENT_MAX_METERS
