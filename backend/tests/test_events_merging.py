"""Ereignis-Gruppierung: Stufe 3, das Zusammenlegen zu kleiner Segmente (Spec 0506, ADR 0117 Punkt
3).
(Aufgeteilt aus test_events.py, Spec 0651.)
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import timedelta

import pytest

from photosort import events as events_module
from photosort.events import (
    BOUNDARY_CAUSES,
    BOUNDARY_EXTENT,
    BOUNDARY_LANDMARK,
    BOUNDARY_MOTIF_CHANGE,
    BOUNDARY_TIME_GAP,
    MERGE_BLOCK_EXTENT,
    MERGE_BLOCK_NO_NEIGHBOUR,
    MERGE_BLOCK_REASONS,
    MERGE_BLOCK_SPAN,
    MERGE_BLOCK_TIME_GAP,
    MERGE_BLOCK_UNBREAKABLE,
    EventCandidate,
    EventMergeError,
    MergeOutcome,
    Segment,
    build_events,
    explain_events,
    merge_small_segments,
)
from tests.support.event_grouping import (
    EPSILON_METERS,
    EPSILON_TIME,
    T0,
    _confirming,
    _extent_max,
    _max_span,
    _measured_candidate,
    _merge_extent_max,
    _north,
    _placeless_candidate,
    _UnderShiftedEventConstants,
)


def _merge_gap() -> timedelta:
    """Die geltende Ueberbrueckungsgrenze von Stufe 3 - als Modulattribut gelesen."""
    return events_module.MERGE_MAX_GAP


# --- Stufe 3: das Zusammenlegen zu kleiner Segmente (Spec 0506, ADR 0117 Punkt 3) ----------------
def _members(
    first_id: int, offsets: Sequence[timedelta], meters_north: float | None
) -> tuple[EventCandidate, ...]:
    """`meters_north=None` heisst "ganz ohne Ort" - die Lage, in der die Entfernung ueber eine
    Kante unbestimmbar ist."""
    if meters_north is None:
        return tuple(
            _placeless_candidate(first_id + index, T0 + offset)
            for index, offset in enumerate(offsets)
        )
    return tuple(
        _measured_candidate(first_id + index, T0 + offset, lat=_north(meters_north))
        for index, offset in enumerate(offsets)
    )


def _tiny(
    offset: timedelta,
    *,
    first_id: int,
    causes: Collection[str] = (),
    meters_north: float | None = 0.0,
) -> Segment:
    """Ein Segment aus EINEM Foto - unter jeder zulaessigen Mindestgroesse (`>= 2`)."""
    return Segment(members=_members(first_id, [offset], meters_north), causes=frozenset(causes))


def _normal_from(
    start: timedelta,
    *,
    first_id: int,
    causes: Collection[str] = (),
    meters_north: float | None = 0.0,
) -> Segment:
    """Genau `MIN_EVENT_PHOTOS` Fotos ab `start`, dicht beieinander.

    Die GROESSE kommt aus dem Symbol, nicht aus einer Zahl: Unter einer anderen Mindestgroesse
    waere ein fest zweielementiges Nachbarsegment selbst zu klein und zoege sich in den Fall
    hinein, den der Fall gar nicht misst."""
    offsets = [start + index * EPSILON_TIME for index in range(events_module.MIN_EVENT_PHOTOS)]
    return Segment(members=_members(first_id, offsets, meters_north), causes=frozenset(causes))


def _normal_until(
    end: timedelta,
    *,
    first_id: int,
    causes: Collection[str] = (),
    meters_north: float | None = 0.0,
) -> Segment:
    """Genau `MIN_EVENT_PHOTOS` Fotos, das LETZTE bei `end`, die uebrigen dicht davor."""
    minimum = events_module.MIN_EVENT_PHOTOS
    offsets = [end - (minimum - 1 - index) * EPSILON_TIME for index in range(minimum)]
    return Segment(members=_members(first_id, offsets, meters_north), causes=frozenset(causes))


def _normal_spanning_the_maximum(first_id: int) -> Segment:
    """Genau `MIN_EVENT_PHOTOS` Fotos, die zusammen GENAU `EVENT_MAX_SPAN` ueberspannen - das
    Segment, neben dem jeder weitere Zuwachs die Dauergrenze reisst."""
    minimum = events_module.MIN_EVENT_PHOTOS
    offsets = [_max_span() * index / (minimum - 1) for index in range(minimum)]
    return Segment(members=_members(first_id, offsets, 0.0), causes=frozenset())


def _ids(outcome: MergeOutcome) -> list[tuple[int, ...]]:
    return [tuple(member.photo_id for member in segment.members) for segment in outcome.segments]


def _block(first_id: int) -> tuple[int, ...]:
    """Die Foto-Ids eines Segments aus `_normal_from`/`_normal_until`."""
    return tuple(range(first_id, first_id + events_module.MIN_EVENT_PHOTOS))


class TestTheThirdStageChoosesItsNeighbour(_UnderShiftedEventConstants):
    """Die drei Tie-Break-Stufen, je an einem eigens GEBAUTEN Gleichstand: kleinere Zeitluecke,
    bei Gleichstand kleinere Entfernung, danach der fruehere. Nur angrenzende Segmente."""

    def _three(
        self,
        *,
        gap_before: timedelta,
        gap_after: timedelta,
        meters_before: float = 0.0,
        meters_after: float = 0.0,
    ) -> list[Segment]:
        """Zwei normal grosse Segmente und dazwischen eines aus EINEM Foto."""
        middle = _merge_gap()
        return [
            _normal_until(middle - gap_before, first_id=1, meters_north=meters_before),
            _tiny(middle, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(
                middle + gap_after,
                first_id=20,
                causes={BOUNDARY_TIME_GAP},
                meters_north=meters_after,
            ),
        ]

    def test_the_smaller_time_gap_wins(self) -> None:
        outcome = merge_small_segments(
            self._three(gap_before=EPSILON_TIME, gap_after=2 * EPSILON_TIME)
        )

        assert _ids(outcome) == [(*_block(1), 10), _block(20)]

    def test_the_smaller_time_gap_wins_the_other_way_round_too(self) -> None:
        """Der Spiegelfall - ohne ihn bliebe offen, ob die Wahl die Zeitluecke liest oder nur
        immer den frueheren nimmt."""
        outcome = merge_small_segments(
            self._three(gap_before=2 * EPSILON_TIME, gap_after=EPSILON_TIME)
        )

        assert _ids(outcome) == [_block(1), (10, *_block(20))]

    def test_at_an_equal_gap_the_smaller_distance_wins(self) -> None:
        near = _extent_max() / 4
        outcome = merge_small_segments(
            self._three(
                gap_before=EPSILON_TIME,
                gap_after=EPSILON_TIME,
                meters_before=near,
                meters_after=2 * near,
            )
        )

        assert _ids(outcome) == [(*_block(1), 10), _block(20)]

    def test_at_an_equal_gap_the_smaller_distance_wins_the_other_way_round_too(self) -> None:
        near = _extent_max() / 4
        outcome = merge_small_segments(
            self._three(
                gap_before=EPSILON_TIME,
                gap_after=EPSILON_TIME,
                meters_before=2 * near,
                meters_after=near,
            )
        )

        assert _ids(outcome) == [_block(1), (10, *_block(20))]

    def test_at_an_equal_gap_and_an_equal_distance_the_earlier_wins(self) -> None:
        """Die dritte Stufe macht die Regel TOTAL - ohne sie haenge das Ergebnis an der
        Iterationsreihenfolge."""
        outcome = merge_small_segments(self._three(gap_before=EPSILON_TIME, gap_after=EPSILON_TIME))

        assert _ids(outcome) == [(*_block(1), 10), _block(20)]

    def test_a_neighbour_without_a_coordinate_wins_no_tie(self) -> None:
        """Eine unbestimmbare Entfernung zaehlt als groesstmoegliche: Ein Nachbar, ueber den nichts
        bekannt ist, gewinnt keinen Gleichstand. Er bleibt zulaessig - nur eben nicht bevorzugt."""
        middle = _merge_gap()
        segments = [
            _normal_until(middle - EPSILON_TIME, first_id=1, meters_north=None),
            _tiny(middle, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(middle + EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert _ids(outcome) == [_block(1), (10, *_block(20))]


class TestTheFourBoltsAgainstOverMerging(_UnderShiftedEventConstants):
    """Vier Riegel, JE EINZELN: In jedem Fall greift genau einer, die anderen drei halten. Nur so
    steht fest, dass jeder von ihnen fuer sich traegt."""

    def test_all_four_holding_is_the_control_case(self) -> None:
        """Der ROT-ANKER: Dieselbe Lage ohne Verletzung wird tatsaechlich zusammengelegt. Ohne ihn
        bestuenden die vier Faelle darunter auch dann, wenn nie etwas zusammengelegt wuerde."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        assert _ids(merge_small_segments(segments)) == [(*_block(1), 10)]

    def test_bolt_a_the_gap_to_the_neighbour_exceeds_the_merge_gap(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(_merge_gap() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        assert _ids(merge_small_segments(segments)) == [_block(1), (10,)]

    def test_bolt_b_the_duration_of_the_result_exceeds_the_maximum_span(self) -> None:
        """Die Zeitluecke zum Nachbarn bleibt dabei UNTER `MERGE_MAX_GAP` - Riegel (a) haelt, und
        allein die Dauer des Ergebnisses sperrt."""
        segments = [
            _normal_spanning_the_maximum(first_id=1),
            _tiny(_max_span() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        assert _ids(merge_small_segments(segments)) == [_block(1), (10,)]

    def test_bolt_c_the_extent_of_the_result_exceeds_the_merge_extent(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        assert _ids(merge_small_segments(segments)) == [_block(1), (10,)]

    def test_bolt_c_reads_its_own_limit_not_the_splitting_threshold(self) -> None:
        """DER TRAGENDE FALL von ADR 0118 Punkt 4: Genau die Lage, die die Ausdehnung GETRENNT hat
        - das Ergebnis liegt ueber `EVENT_EXTENT_MAX_METERS` - wird zusammengelegt, weil Riegel (c)
        seine eigene, groessere Grenze prueft. Praefte er weiter die Trennschwelle, waere die Stufe
        fuer ausdehnungsgetrennte Segmente strukturell unpassierbar, und dieser Fall bliebe rot."""
        between = (_extent_max() + _merge_extent_max()) / 2
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_EXTENT},
                meters_north=between,
            ),
        ]

        assert between > _extent_max(), "sonst misst der Fall die neue Grenze gar nicht"
        assert _ids(merge_small_segments(segments)) == [(*_block(1), 10)]

    def test_bolt_d_a_segment_at_the_minimum_is_never_absorbed(self) -> None:
        """Ein normal grosses Event wird NIE zugeschlagen, auch wenn Zeit, Dauer und Ausdehnung es
        zuliessen - die uebrigen drei Riegel halten hier alle."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _normal_from(EPSILON_TIME, first_id=100, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert _ids(outcome) == [_block(1), _block(100)]
        assert outcome.dissolved_boundaries == 0


class TestNoBoundaryIsUntouchableAnyMore(_UnderShiftedEventConstants):
    """Seit ADR 0119 liest die dritte Stufe ueberhaupt keine Ursachenmenge mehr: `motivwechsel`
    haelt eine Grenze nicht mehr fest, und `UNBREAKABLE_CAUSES` ist ersatzlos entfallen.

    Die Faelle hier ERSETZEN die frueheren zur unantastbaren Grenze - sie sind deren woertliche
    Umkehrung. Der Berichtsgrund `MERGE_BLOCK_UNBREAKABLE` bleibt im Vorrat und steht dauerhaft auf
    0; ohne die Zeile waere eine Riegel-Diagnose nicht mehr gegen die frueheren zu halten, in denen
    `unantastbar` der groesste Blocker war."""

    def _enclosed(self, causes: Collection[str]) -> list[Segment]:
        return [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes=causes),
            _normal_from(2 * EPSILON_TIME, first_id=20, causes=causes),
        ]

    def test_a_segment_opened_by_a_motif_change_is_absorbed_like_any_other(self) -> None:
        """DIE UMKEHRUNG: Genau die Lage, die den Motivwechsel frueher festgehalten hat - ein
        einzelnes Foto zwischen zwei Grenzen mit `motivwechsel`, beide Nachbarn erfuellen alle drei
        Riegel - wird jetzt zugeschlagen."""
        outcome = merge_small_segments(self._enclosed({BOUNDARY_MOTIF_CHANGE}))

        assert _ids(outcome) == [(*_block(1), 10), _block(20)]
        assert outcome.dissolved_boundaries == 1
        assert outcome.moved_photo_ids == frozenset({10})

    def test_the_lage_is_decided_by_the_bolts_alone_not_by_the_cause(self) -> None:
        """Dieselbe Lage unter JEDER Ursachenmenge des Vorrats - das Ergebnis ist immer dasselbe.
        Ein einzelner Eintrag, der die Stufe doch noch liest, wird hier rot, nicht erst im
        Bericht."""
        reference = _ids(merge_small_segments(self._enclosed({BOUNDARY_TIME_GAP})))

        for cause in BOUNDARY_CAUSES:
            assert _ids(merge_small_segments(self._enclosed({cause}))) == reference, cause

    def test_a_motif_change_inside_a_set_of_two_dissolves_too(self) -> None:
        """Die Grenze traegt eine MENGE - und keine Teilmenge davon haelt sie mehr fest."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP, BOUNDARY_MOTIF_CHANGE}),
        ]

        assert _ids(merge_small_segments(segments)) == [(*_block(1), 10)]

    def test_the_block_reason_stays_in_the_supply_with_an_honest_zero(self) -> None:
        """Der Berichtswortschatz behaelt seinen Eintrag, und die Stufe liefert ihn unter KEINER
        Lage - auch nicht an einer Kante, an der alle drei Riegel zugleich sperren."""
        assert MERGE_BLOCK_UNBREAKABLE in MERGE_BLOCK_REASONS

        for cause in BOUNDARY_CAUSES:
            segments = [
                _normal_spanning_the_maximum(first_id=1),
                _tiny(
                    _max_span() + _merge_gap() + EPSILON_TIME,
                    first_id=10,
                    causes={cause},
                    meters_north=_merge_extent_max() + EPSILON_METERS,
                ),
            ]

            [blocked] = merge_small_segments(segments).blocked_segments

            for edge in blocked.edges:
                assert MERGE_BLOCK_UNBREAKABLE not in edge, cause

    def test_the_landmark_keeps_its_place_in_the_cause_vocabulary(self) -> None:
        """Was von der Ungleichbehandlung aus ADR 0118 Punkt 2 bleibt: Der Berichtswortschatz der
        URSACHEN fuehrt weiter beide Namen mit ehrlicher Null bzw. beweglicher Zahl, waehrend die
        an jeder Kante gelesene Regel ganz entfallen ist."""
        assert {BOUNDARY_LANDMARK, BOUNDARY_MOTIF_CHANGE} <= set(BOUNDARY_CAUSES)
        assert not hasattr(events_module, "UNBREAKABLE_CAUSES")


class TestTheThirdStageComesToAStandstill(_UnderShiftedEventConstants):
    """Der Stillstand, maschinenpruefbar - nicht als Behauptung ueber den Ablauf."""

    def _a_blocked_and_a_mergeable_segment(self) -> list[Segment]:
        """Ein Einzelfoto, dessen EINZIGE Kante die Ueberbrueckungsgrenze reisst (es bleibt
        gesperrt), und dahinter ein zweites Einzelfoto, das zugeschlagen werden darf.

        Gesperrt wird hier ueber einen RIEGEL, nicht mehr ueber eine Ursache: Seit ADR 0119 haelt
        keine Ursachenmenge eine Kante mehr fest."""
        return [
            _tiny(timedelta(0), first_id=1),
            _tiny(_merge_gap() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(_merge_gap() + 2 * EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}),
        ]

    def test_a_blocked_segment_does_not_stall_the_rest(self) -> None:
        """Ohne den Zusatz "nicht bereits gesperrt" waehlte jede Runde dasselbe gescheiterte
        Segment erneut, und das zusammenlegbare daneben bliebe unbehandelt."""
        outcome = merge_small_segments(self._a_blocked_and_a_mergeable_segment())

        assert _ids(outcome) == [(1,), (10, *_block(20))]

    def test_the_outcome_is_idempotent(self) -> None:
        """Die maschinenpruefbare Form des Stillstands: Ein zweiter Durchgang aendert nichts
        mehr."""
        once = merge_small_segments(self._a_blocked_and_a_mergeable_segment())
        twice = merge_small_segments(once.segments)

        assert twice.segments == once.segments
        assert twice.dissolved_boundaries == 0
        assert twice.moved_photo_ids == frozenset()

    def test_each_dissolved_boundary_costs_exactly_one_segment(self) -> None:
        """Die je Zusammenlegung strikt fallende Segmentzahl, als Bilanz statt als Behauptung."""
        segments = self._a_blocked_and_a_mergeable_segment()

        outcome = merge_small_segments(segments)

        assert len(outcome.segments) == len(segments) - outcome.dissolved_boundaries
        assert outcome.dissolved_boundaries >= 1

    def test_a_chain_of_tiny_segments_collapses_completely(self) -> None:
        """Ein zusammengelegtes Ergebnis, das noch immer zu klein ist, wird weiter zugeschlagen -
        und ein Foto zaehlt dabei trotzdem nur EINMAL als bewegt."""
        count = 2 * events_module.MIN_EVENT_PHOTOS + 1
        segments = [
            _tiny(
                index * EPSILON_TIME,
                first_id=index,
                causes=() if index == 0 else {BOUNDARY_TIME_GAP},
            )
            for index in range(count)
        ]

        outcome = merge_small_segments(segments)

        assert _ids(outcome) == [tuple(range(count))]
        assert outcome.dissolved_boundaries == count - 1
        assert len(outcome.moved_photo_ids) < count, "ein Foto wechselt hoechstens einmal"

    def test_an_empty_run_is_no_special_case(self) -> None:
        outcome = merge_small_segments([])

        assert outcome == MergeOutcome(
            segments=(), dissolved_boundaries=0, moved_photo_ids=frozenset()
        )

    def test_the_round_limit_raises_instead_of_breaking_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Rundenobergrenze greift im Betrieb nie; pruefbar ist sie nur, indem man sie
        unterschreitet. Ein stiller Frueabbruch liesse eine halb zusammengelegte Gliederung
        zurueck, die niemandem auffiele - deshalb WIRFT sie."""
        monkeypatch.setattr(events_module, "round_limit", lambda _: 0)
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        with pytest.raises(EventMergeError):
            merge_small_segments(segments)


class TestTheThirdStageKeepsTheOpeningCause(_UnderShiftedEventConstants):
    """Aufgeloest wird die Grenze ZWISCHEN den beiden; die eroeffnende des FRUEHEREN bleibt."""

    def test_the_result_carries_the_cause_of_the_earlier_segment(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1, causes={BOUNDARY_EXTENT}),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        [merged] = merge_small_segments(segments).segments

        assert merged.causes == frozenset({BOUNDARY_EXTENT})

    def test_the_first_segment_keeps_its_empty_cause_when_it_is_absorbed(self) -> None:
        """Index 0 traegt die leere Menge, und das muss auch NACH Stufe 3 gelten - sonst truege
        der erste Abschnitt eines Laufs ploetzlich eine Ursache."""
        segments = [
            _tiny(timedelta(0), first_id=1),
            _normal_from(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        [merged] = merge_small_segments(segments).segments

        assert merged.causes == frozenset()


class TestTheCounterIndicationOfTheThirdStage(_UnderShiftedEventConstants):
    """Die Gegenanzeige: Beide Abnahmezahlen dieser Spec wuerden von einer zu aggressiven
    Verschmelzung BESSER erfuellt. Ohne diese beiden Zahlen misst eine Nachmessung nur die
    Unter-Zerstueckelung."""

    def test_nothing_merged_reports_nothing_moved(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _normal_from(_merge_gap() + EPSILON_TIME, first_id=100, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert outcome.dissolved_boundaries == 0
        assert outcome.moved_photo_ids == frozenset()

    def test_only_the_absorbed_segment_counts_as_moved(self) -> None:
        """Die Fotos des AUFNEHMENDEN Nachbarn sind geblieben, wo sie waren - sie mitzuzaehlen
        machte aus jeder einzelnen Zusammenlegung eine grosse Bewegung."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert outcome.dissolved_boundaries == 1
        assert outcome.moved_photo_ids == frozenset({10})


class TestWhyASegmentCouldNotBeMerged(_UnderShiftedEventConstants):
    """Block F: Je zu kleinem Segment, das NICHT zugeschlagen werden konnte, steht fest, welche
    Gruende an seinen Kanten standen.

    JE KANTE EINE MENGE, nie ein einzelner Grund: Mehrere Riegel duerfen gleichzeitig zutreffen,
    und eine Meldung mit einem Grund je Kante unterschluege die spaeter geprueften - `ausdehnung`
    steht als letzter und ist genau die Zahl, an der die Frage dieses Blocks haengt.

    EIN SEGMENT HAT SO VIELE KANTEN, WIE ES NACHBARN HAT. Eine nicht vorhandene Seite ist kein
    Hindernis; sie als Kante zu fuehren verfaelschte "an allen Kanten der Grund" - die einzige
    handlungsleitende Spalte - bei jedem Randsegment. `kein_nachbar` greift nur, wenn es
    ueberhaupt keinen Nachbarn gibt."""

    def _tiny_between(
        self,
        *,
        gap_after: timedelta = EPSILON_TIME,
        meters_before: float = 0.0,
        causes: Collection[str] = (BOUNDARY_TIME_GAP,),
    ) -> list[Segment]:
        return [
            _normal_until(timedelta(0), first_id=1, meters_north=meters_before),
            _tiny(EPSILON_TIME, first_id=10, causes=causes),
            _normal_from(EPSILON_TIME + gap_after, first_id=20, causes={BOUNDARY_TIME_GAP}),
        ]

    def test_nothing_is_reported_when_everything_could_be_merged(self) -> None:
        """Der ROT-ANKER: Ohne ihn bestuenden die Faelle darunter auch dann, wenn jede beliebige
        Lage als gesperrt gemeldet wuerde."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert outcome.dissolved_boundaries == 1
        assert outcome.blocked_segments == ()

    def test_a_segment_at_the_minimum_is_no_case_of_this_block(self) -> None:
        """Riegel (d) haengt an der AUSWAHL, nicht an einer Kante: Ein Segment, das nicht zu klein
        ist, wird gar nicht erst betrachtet - und taucht deshalb mit keinem Grund auf."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _normal_from(_merge_gap() + EPSILON_TIME, first_id=100, causes={BOUNDARY_TIME_GAP}),
        ]

        assert merge_small_segments(segments).blocked_segments == ()

    def test_the_gap_to_the_neighbour(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(_merge_gap() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_TIME_GAP}),)

    def test_the_duration_of_the_result(self) -> None:
        segments = [
            _normal_spanning_the_maximum(first_id=1),
            _tiny(_max_span() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_SPAN}),)

    def test_the_extent_of_the_result(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_EXTENT}),)

    def test_a_segment_without_any_neighbour_at_all(self) -> None:
        """`kein_nachbar` greift NUR hier - ein einziges Segment im ganzen Lauf. Eine bloss
        fehlende SEITE eines Randsegments ist kein Hindernis und zaehlt nicht als Kante."""
        [blocked] = merge_small_segments([_tiny(timedelta(0), first_id=1)]).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_NO_NEIGHBOUR}),)

    def test_a_segment_at_the_edge_of_the_run_has_exactly_one_edge(self) -> None:
        """Die fehlende Seite taucht NICHT auf. Als eigene Kante gefuehrt, faende sich dieses
        Segment in "an allen Kanten der Grund" bei keinem einzigen Grund wieder - obwohl die
        Ausdehnung dort der Grund war."""
        segments = [
            _tiny(timedelta(0), first_id=1, meters_north=0.0),
            _normal_from(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_EXTENT}),)

    def test_two_neighbours_can_stand_for_two_different_reasons(self) -> None:
        """Genau die Lage, fuer die es zwei Zahlen braucht: Keiner der beiden Gruende stand an
        allen Kanten, und eine Zaehlung nur ueber "beteiligt" legte beide Behebungen nahe."""
        segments = [
            _normal_until(
                timedelta(0), first_id=1, meters_north=_merge_extent_max() + EPSILON_METERS
            ),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(_merge_gap() + 2 * EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (
            frozenset({MERGE_BLOCK_EXTENT}),
            frozenset({MERGE_BLOCK_TIME_GAP}),
        )

    def test_an_edge_that_violates_several_bolts_reports_them_all(self) -> None:
        """NICHT KURZGESCHLOSSEN, dieselbe Zusage wie fuer die Signale des Durchlaufs
        (`TestSignalsAreNeverShortCircuited`): Alle drei werden ausgewertet. Sonst verschwaende
        `ausdehnung` als zuletzt geprueftes hinter jedem frueheren Grund - und das ist genau die
        Zahl, an der die Frage dieses Blocks haengt. Eine Lage, die ALLE DREI zugleich verletzt."""
        segments = [
            _normal_spanning_the_maximum(first_id=1),
            _tiny(
                _max_span() + _merge_gap() + EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (
            frozenset({MERGE_BLOCK_TIME_GAP, MERGE_BLOCK_SPAN, MERGE_BLOCK_EXTENT}),
        )

    def test_the_extent_is_reported_next_to_an_earlier_bolt(self) -> None:
        """Der Fall, den der Kurzschluss verschluckte: Zeitluecke UND Ausdehnung an derselben
        Kante. Wer nur die Zeitluecke lockert, steht danach vor der Ausdehnung."""
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                _merge_gap() + EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_TIME_GAP, MERGE_BLOCK_EXTENT}),)

    def test_every_reported_reason_comes_from_the_closed_supply(self) -> None:
        """Der Vorrat ist geschlossen: Ein Grund ausserhalb stuende in keiner Zeile des Berichts,
        ohne dass eine Summe kleiner wuerde. Und keine Kante ist leer - eine offene Kante waere
        ein zulaessiger Nachbar, dann waere das Segment gar nicht gesperrt."""
        for segments in (
            self._tiny_between(gap_after=_merge_gap()),
            [_tiny(timedelta(0), first_id=1)],
            [
                _normal_spanning_the_maximum(first_id=1),
                _tiny(_max_span() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
            ],
        ):
            for blocked in merge_small_segments(segments).blocked_segments:
                for edge in blocked.edges:
                    assert edge, "eine leere Kante waere ein zulaessiger Nachbar"
                    assert edge <= set(MERGE_BLOCK_REASONS)
                assert 1 <= len(blocked.edges) <= 2, "so viele Kanten, wie es Nachbarn gibt"

    def test_the_supply_is_exactly_these_five(self) -> None:
        assert MERGE_BLOCK_REASONS == (
            MERGE_BLOCK_UNBREAKABLE,
            MERGE_BLOCK_TIME_GAP,
            MERGE_BLOCK_SPAN,
            MERGE_BLOCK_EXTENT,
            MERGE_BLOCK_NO_NEIGHBOUR,
        )

    def test_exactly_the_segments_that_stayed_too_small_are_reported(self) -> None:
        """Die Bilanz statt einer Behauptung ueber den Ablauf: Beobachtet wird, was tatsaechlich
        stehen geblieben ist - nicht mehr und nicht weniger."""
        segments = [
            _tiny(timedelta(0), first_id=1, causes=()),
            _tiny(_merge_gap() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(
                2 * _merge_gap() + 2 * EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}
            ),
        ]

        outcome = merge_small_segments(segments)

        still_small = [
            segment
            for segment in outcome.segments
            if len(segment.members) < events_module.MIN_EVENT_PHOTOS
        ]
        assert len(outcome.blocked_segments) == len(still_small) == 2

    def test_the_observation_reaches_the_explaining_form(self) -> None:
        """Ohne diesen Weg bliebe die Diagnose in der Stufe stehen, und das Messkommando muesste
        sie nachbilden - es maesse dann etwas anderes, als die Stufe tut."""
        minimum = events_module.MIN_EVENT_PHOTOS
        gap = _merge_gap() + EPSILON_TIME
        # Das erste Segment traegt GENAU die Mindestgroesse - unter einer anderen waere es selbst
        # zu klein und zoege sich in den Fall hinein, den der Fall nicht misst.
        candidates = [
            _placeless_candidate(index, T0 + index * EPSILON_TIME) for index in range(minimum)
        ]
        candidates.append(_placeless_candidate(minimum, T0 + (minimum - 1) * EPSILON_TIME + gap))

        formation = explain_events(candidates)

        assert [event.photo_ids for event in formation.events] == [
            tuple(range(minimum)),
            (minimum,),
        ]
        [blocked] = formation.blocked_segments
        assert blocked.edges == (frozenset({MERGE_BLOCK_TIME_GAP}),)


class TestBuildEventsRunsTheThirdStage:
    """Stufe 3 laeuft INNERHALB der Event-Bildung - und ihre beiden Festlegungen sind injizierbar,
    sonst liefen die Faelle der Signale still durch sie hindurch."""

    def _a_lonely_photo_behind_a_time_gap(self) -> list[EventCandidate]:
        """Zwei Fotos, dann - hinter einer Zeitluecke, aber innerhalb von `MERGE_MAX_GAP` - ein
        einzelnes. Der Durchlauf trennt, Stufe 3 legt wieder zusammen."""
        gap = events_module.EVENT_TIME_GAP + EPSILON_TIME
        return [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, T0 + EPSILON_TIME),
            _placeless_candidate(3, T0 + EPSILON_TIME + gap),
        ]

    def test_the_operating_values_apply_without_any_argument(self) -> None:
        events = build_events(self._a_lonely_photo_behind_a_time_gap())

        assert [event.photo_ids for event in events] == [(1, 2, 3)]

    def test_the_minimum_is_injectable_and_switches_the_stage_off(self) -> None:
        events = build_events(self._a_lonely_photo_behind_a_time_gap(), min_event_photos=1)

        assert [event.photo_ids for event in events] == [(1, 2), (3,)]

    def test_the_merge_gap_is_injectable(self) -> None:
        """Eine Ueberbrueckung unterhalb der Zeitluecke kann keine Zeitluecken-Grenze mehr
        aufloesen - die Stufe laeuft dann, ohne etwas zu tun."""
        events = build_events(self._a_lonely_photo_behind_a_time_gap(), merge_max_gap=timedelta(0))

        assert [event.photo_ids for event in events] == [(1, 2), (3,)]

    def test_the_constants_are_read_as_module_attributes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ein Default-Parameterwert in der Signatur baende sie beim Import; `monkeypatch.setattr`
        liefe ins Leere und jede Variation waere wirkungslos - gruen, aber ohne Wirkung."""
        monkeypatch.setattr(events_module, "MIN_EVENT_PHOTOS", 1)

        events = build_events(self._a_lonely_photo_behind_a_time_gap())

        assert [event.photo_ids for event in events] == [(1, 2), (3,)]

    def test_the_explaining_form_reports_the_counter_indication(self) -> None:
        formation = explain_events(self._a_lonely_photo_behind_a_time_gap())

        assert formation.dissolved_boundaries == 1
        assert formation.moved_photos == 1
        assert formation.causes == (frozenset(),)

    def test_a_run_without_any_merging_reports_a_counter_indication_of_zero(self) -> None:
        formation = explain_events(self._a_lonely_photo_behind_a_time_gap(), min_event_photos=1)

        assert (formation.dissolved_boundaries, formation.moved_photos) == (0, 0)

    def test_a_merged_event_goes_through_the_one_place_that_builds_them(self) -> None:
        """Ein zusammengelegtes Event durchlaeuft dieselbe Bildung wie jedes andere - es gibt
        keinen zweiten Zweig fuer Name, Zellen, `place_kind` und `position`."""
        gap = events_module.EVENT_TIME_GAP + EPSILON_TIME
        candidates = [
            _measured_candidate(1, T0, landmark_name="Zugspitze"),
            _measured_candidate(2, T0 + EPSILON_TIME),
            _measured_candidate(3, T0 + EPSILON_TIME + gap),
        ]

        [event] = build_events(candidates, landmark_points_by_name=_confirming("Zugspitze"))

        assert (event.position, event.photo_ids) == (1, (1, 2, 3))
        assert (event.landmark_name, event.place_kind) == ("Zugspitze", "landmark")
        assert len(event.place_cells) == 1
        assert (event.started_at, event.ended_at) == (T0, candidates[-1].taken_at)
