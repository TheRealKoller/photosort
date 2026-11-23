"""Ereignis-Gruppierung: die Motivwechsel-Regel und ihre Sprecher-Fotos.
(Aufgeteilt aus test_events.py, Spec 0651.)
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime
from itertools import product

from photosort import events as events_module
from photosort.events import (
    EventCandidate,
    ExtentSignal,
    default_signals,
    motif_change_starts,
)
from photosort.selection import MOTIF_PRESENCE_THRESHOLD
from tests.support.event_grouping import (
    _ABOVE,
    _BELOW,
    EPSILON_METERS,
    EPSILON_TIME,
    T0,
    _at,
    _build,
    _extent_max,
    _measured_candidate,
    _motif_candidates,
    _north,
    _picture,
    _placeless_candidate,
    _SpySignal,
    _time_gap,
    _UnderEveryConfirmingWindow,
    _window,
)

_AT_THRESHOLD = MOTIF_PRESENCE_THRESHOLD


_JUST_BELOW = math.nextafter(MOTIF_PRESENCE_THRESHOLD, 0.0)


class TestTheMotifChangeRule(_UnderEveryConfirmingWindow):
    """Die REINE Regel, direkt an `motif_change_starts` gemessen.

    Sie ist keine paarweise Frage, sondern eine Segmentierung ueber die ganze Folge - ihr Ergebnis
    ist eine Indexmenge und damit direkt beobachtbar. Ein Nachweis allein durch `build_events`
    hindurch saehe die Rueckwirkung nicht."""

    def test_a_newly_carried_motif_starts_a_new_event(self) -> None:
        candidates = _motif_candidates([_picture("a")] + [_picture("a", "b")] * _window())

        assert motif_change_starts(candidates) == frozenset({1})

    def test_a_dropped_motif_starts_a_new_event(self) -> None:
        """Die symmetrische Differenz ist SYMMETRISCH: der Wegfall trennt wie das Hinzukommen."""
        candidates = _motif_candidates([_picture("a", "b")] + [_picture("a")] * _window())

        assert motif_change_starts(candidates) == frozenset({1})

    def test_a_changed_strongest_motif_within_the_same_carried_set_starts_nothing(self) -> None:
        """Untersagt ist der Wechsel des STAERKSTEN Motivs (er benennt eine Rangfolge zwischen
        Motiven) - entschieden wird ueber die getragene Menge, und die ist hier unveraendert."""
        candidates = _motif_candidates(
            [{"a": _ABOVE, "b": _AT_THRESHOLD}] + [{"a": _AT_THRESHOLD, "b": _ABOVE}] * _window()
        )

        assert motif_change_starts(candidates) == frozenset()

    def test_a_strength_change_below_the_threshold_starts_nothing(self) -> None:
        """Kein Gesamtabstand ueber die Staerken: unterhalb der Grenze ist jede Bewegung
        dasselbe leere Motivbild."""
        candidates = _motif_candidates([{"a": _BELOW}] + [{"a": _JUST_BELOW}] * _window())

        assert motif_change_starts(candidates) == frozenset()

    def test_the_presence_threshold_is_inclusive_and_not_rebuilt(self) -> None:
        """Beide Haelften in EINEM Fall - ein in `events.py` nachgebautes `>` liesse die erste
        leer und bliebe in der zweiten gruen.

        Genau auf der Grenze gilt ein Motiv als getragen, knapp darunter nicht."""
        exactly_at = _motif_candidates([{"a": _JUST_BELOW}] + [{"a": _AT_THRESHOLD}] * _window())
        just_below = _motif_candidates([{"a": _BELOW}] + [{"a": _JUST_BELOW}] * _window())

        assert motif_change_starts(exactly_at) == frozenset({1})
        assert motif_change_starts(just_below) == frozenset()

    def test_the_reference_is_the_opening_photo_and_not_the_predecessor(self) -> None:
        """Eine Folge, die sich Foto fuer Foto um je EIN Motiv weiterschiebt.

        Gegen den jeweiligen Vorgaenger gemessen traete nie eine Grenze ein: jedes Foto zeigt
        gegenueber seinem Vorgaenger ein ANDERES geaendertes Motiv, und kein Fenster kaeme je
        zustande. Gegen das eroeffnende Foto gemessen trennt das Abdriften."""
        candidates = _motif_candidates(
            [_picture(*(f"m{step}" for step in range(count + 1))) for count in range(_window() + 1)]
        )

        assert motif_change_starts(candidates) == frozenset({1})

    def test_the_start_is_the_first_photo_of_the_window_not_the_confirming_one(self) -> None:
        """DIE RUECKWIRKUNG. Geprueft wird der Index selbst, nicht nur, DASS getrennt wird."""
        candidates = _motif_candidates([_picture("a")] * 2 + [_picture("a", "b")] * _window())

        assert motif_change_starts(candidates) == frozenset({2})

    def test_confirmation_does_not_require_an_identical_picture(self) -> None:
        """Bestaetigt ist der Wechsel, wenn MINDESTENS EINES der zuerst geaenderten Motive
        weiterhin geaendert ist - ein zusaetzlich getragenes Motiv reisst ihn nicht ab."""
        candidates = _motif_candidates(
            [_picture("a"), _picture("a", "b"), _picture("a", "b", "c")]
            + [_picture("a", "b")] * (_window() - 2)
        )

        assert motif_change_starts(candidates) == frozenset({1})

    def test_a_window_one_photo_short_then_a_return_to_the_reference_starts_nothing(self) -> None:
        candidates = _motif_candidates(
            [_picture("a")] + [_picture("a", "b")] * (_window() - 1) + [_picture("a")]
        )

        assert motif_change_starts(candidates) == frozenset()

    def test_a_decayed_window_followed_by_a_full_one_starts_at_the_second_window(self) -> None:
        candidates = _motif_candidates(
            [_picture("a")]
            + [_picture("a", "b")] * (_window() - 1)
            + [_picture("a")]
            + [_picture("a", "b")] * _window()
        )

        assert motif_change_starts(candidates) == frozenset({_window() + 1})

    def test_a_single_deviating_photo_never_starts_an_event(self) -> None:
        """Der verhaltensnahe Zwilling der Ungleichung `MOTIF_CHANGE_CONFIRMING_PHOTOS >= 2`:
        beide werden bei `1` rot, und das ist die zugesagte Wirkung."""
        candidates = _motif_candidates(
            [_picture("a"), _picture("a", "b")] + [_picture("a")] * _window()
        )

        assert motif_change_starts(candidates) == frozenset()

    def test_the_window_length_is_at_least_two(self) -> None:
        """Die EINE Aussage ueber den Zahlwert, und sie ist eine Ungleichung."""
        assert events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS >= 2

    def test_zero_is_never_a_start_and_every_start_is_a_valid_index(self) -> None:
        """Ein Index `0` waere ein leeres fuehrendes Event - er setzt einen bereits gesetzten
        Bezug voraus und kann deshalb nicht entstehen."""
        candidates = _motif_candidates([_picture("a")] + [_picture("b")] * _window())

        starts = motif_change_starts(candidates)

        assert 0 not in starts
        assert starts <= set(range(len(candidates)))
        assert starts

    def test_candidates_without_any_motif_information_yield_no_start(self) -> None:
        """Die Vorgabewerte von `EventCandidate`: ohne Motivangabe liefert die erste Stufe die
        leere Menge und der Durchlauf ist der bisherige."""
        candidates = [_placeless_candidate(index, _at(minutes=index)) for index in range(1, 6)]

        assert motif_change_starts(candidates) == frozenset()


class TestWhichPhotosSpeakForTheMotifChange(_UnderEveryConfirmingWindow):
    """Die drei Zustaende: keine Kopfzeile, leeres Motivbild, ausgeschlossenes Dokument.

    Der erste und der dritte heissen "redet nicht mit", der zweite redet VOLL mit. Fielen zwei
    davon zusammen, waere genau einer der Zwillingsfaelle rot - in welche Richtung sie auch
    zusammenfallen."""

    def test_a_missing_header_is_not_an_empty_motif_picture(self) -> None:
        """DAS ZWILLINGSPAAR: identisch gebaute Folgen, die sich NUR in `None` gegen die
        vorhandene Kopfzeile ohne getragenes Motiv unterscheiden - mit entgegengesetzter
        Erwartung. Ein einzelner Fall bewiese hier nichts."""
        without_header = _motif_candidates([_picture("a")] + [None] * _window())
        empty_picture = _motif_candidates([_picture("a")] + [_picture()] * _window())

        assert motif_change_starts(without_header) == frozenset()
        assert motif_change_starts(empty_picture) == frozenset({1})

    def test_a_photo_without_a_header_never_starts_an_event(self) -> None:
        candidates = _motif_candidates([_picture("a")] + [None] * _window() + [_picture("a")])

        assert motif_change_starts(candidates) == frozenset()

    def test_a_photo_without_a_header_does_not_decay_a_running_window(self) -> None:
        candidates = _motif_candidates(
            [_picture("a")] + [_picture("a", "b")] * (_window() - 1) + [None] + [_picture("a", "b")]
        )

        assert motif_change_starts(candidates) == frozenset({1})

    def test_a_photo_without_a_header_counts_in_no_window(self) -> None:
        """Dieselbe Folge wie oben, nur ohne das bestaetigende Foto dahinter: zaehlte das
        unklassifizierte mit, waere das Fenster hier bereits voll."""
        candidates = _motif_candidates(
            [_picture("a")] + [_picture("a", "b")] * (_window() - 1) + [None]
        )

        assert motif_change_starts(candidates) == frozenset()

    def test_an_excluded_document_is_not_an_empty_motif_picture(self) -> None:
        """Das Zwillingspaar ein zweites Mal - dieselben Kopfzeilen, nur einmal ausgeschlossen."""
        deviating = [_picture("a")] + [_picture("a", "b")] * _window()
        excluded_indices = range(1, _window() + 1)

        assert motif_change_starts(_motif_candidates(deviating)) == frozenset({1})
        assert (
            motif_change_starts(_motif_candidates(deviating, excluded=excluded_indices))
            == frozenset()
        )

    def test_an_excluded_document_never_starts_an_event(self) -> None:
        pictures = [_picture("a")] + [_picture("b")] * _window() + [_picture("a")]
        excluded_indices = range(1, _window() + 1)

        assert motif_change_starts(_motif_candidates(pictures, excluded=excluded_indices)) == (
            frozenset()
        )

    def test_an_excluded_document_does_not_decay_a_running_window(self) -> None:
        pictures = (
            [_picture("a")]
            + [_picture("a", "b")] * (_window() - 1)
            + [_picture("a")]
            + [_picture("a", "b")]
        )

        starts = motif_change_starts(_motif_candidates(pictures, excluded={_window()}))

        assert starts == frozenset({1})

    def test_an_excluded_document_counts_in_no_window(self) -> None:
        pictures = [_picture("a")] + [_picture("a", "b")] * _window()

        starts = motif_change_starts(_motif_candidates(pictures, excluded={_window()}))

        assert starts == frozenset()


class TestTheMotifChangeOnlyMarksABoundaryAndNeverOpensOne(_UnderEveryConfirmingWindow):
    """Die zweite Stufe seit ADR 0119: Ein bestaetigter Motivwechsel EROEFFNET kein Event mehr. Er
    vermerkt `motivwechsel` an einer Grenze, die der Signal-Durchlauf an derselben Stelle ohnehin
    zieht; faellt er auf keine solche Grenze, bleibt er wirkungslos und wird verworfen.

    Die Faelle hier ERSETZEN die frueheren, die den erzwungenen Start durch `build_events` hindurch
    als Trennung geprueft haben: Angepasst haetten sie ihren Namen behalten und danach etwas
    anderes geprueft, als sie versprechen. Die Faelle an `motif_change_starts` SELBST gelten
    unveraendert weiter - der Begriff aendert sich nicht, nur seine Wirkung."""

    def test_two_photos_differing_only_in_their_motif_stay_in_one_event(self) -> None:
        """(a) Der umgekehrte Story-Fall: Ruinenbesuch, danach Mittagessen um die Ecke - EIN
        Anlass, und jetzt auch ein Event.

        Kein Signal trennt hier (Minutenabstand unter der Zeitluecke, 50 m je Schritt unter
        Schritt- und Ausdehnungsschwelle, kein Sehenswuerdigkeitsname), und der Motivwechsel allein
        trennt nicht mehr - gleich wie lange er bestaetigt bleibt."""
        ruins = _picture("ruine")
        lunch = _picture("essen")
        candidates = [
            _measured_candidate(
                index,
                _at(minutes=index),
                lat=_north(index * EPSILON_METERS),
                motif_strengths=picture,
            )
            for index, picture in enumerate([ruins, ruins] + [lunch] * _window())
        ]

        assert motif_change_starts(candidates) == frozenset({2}), "sonst misst der Fall nichts"
        assert [event.photo_ids for event in _build(candidates, default_signals())] == [
            tuple(range(len(candidates)))
        ]

    def test_an_atypical_opening_photo_no_longer_becomes_an_event_of_its_own(self) -> None:
        """Die Zusage der Spec 0477, die mit ADR 0119 faellt: Ein motivgetrenntes Einzelbild darf
        NICHT mehr allein bestehen. Ohne diesen Fall bliebe die aufgehobene Zusage ungeprueft."""
        candidates = _motif_candidates([_picture("a")] + [_picture("b")] * _window())

        assert motif_change_starts(candidates) == frozenset({1}), "sonst misst der Fall nichts"
        assert [event.photo_ids for event in _build(candidates, default_signals())] == [
            tuple(range(_window() + 1))
        ]

    def test_a_confirmed_change_advances_every_signal_instead_of_beginning_it(self) -> None:
        """DIE RUECKSETZUNG FAELLT MIT: Wo frueher `begin` auf allen Signalen lief, laeuft jetzt
        `advance`. Gefragt wird weiterhin jedes Signal an jedem Foto - sonst haengt seine
        Fortschreibung an der Listenposition."""
        spy = _SpySignal()
        candidates = _motif_candidates([_picture("a")] * 2 + [_picture("a", "b")] * _window())

        _build(candidates, [spy])

        assert motif_change_starts(candidates) == frozenset({2}), "sonst misst der Fall nichts"
        assert spy.asked == [candidate.photo_id for candidate in candidates]
        assert spy.begun == [0]
        assert spy.advanced == [candidate.photo_id for candidate in candidates[1:]]

    def test_without_the_reset_the_extent_runs_on_and_splits_later(self) -> None:
        """(e) DIE EINE RICHTUNG, IN DER DIESE AENDERUNG EINE GRENZE HINZUFUEGT. Ohne den
        erzwungenen Start bekommt `ExtentSignal` kein `begin` mehr und laeuft ueber den
        Motivwechsel hinweg weiter - es meldet an SPAETERER Stelle eine Grenze, die es mit der
        Ruecksetzung nie gebraucht haette.

        Die Lage in Metern, alle aus `EVENT_EXTENT_MAX_METERS` gebaut: Foto 0 am Bezugspunkt, Foto
        1 auf halber Schwelle, ab Foto 2 knapp darueber. Die Box ueber ALLE reisst die Schwelle bei
        Foto 2; die Box AB Foto 1 - so weit haette der erzwungene Start zurueckgesetzt - bleibt mit
        einer halben Schwelle darunter."""
        half = _extent_max() / 2
        beyond = _extent_max() + EPSILON_METERS
        metres = [0.0, half] + [beyond] * (_window() - 1)
        candidates = [
            _measured_candidate(
                index,
                T0 + index * EPSILON_TIME,
                lat=_north(north),
                motif_strengths=picture,
            )
            for index, (north, picture) in enumerate(
                zip(metres, [_picture("a")] + [_picture("a", "b")] * _window(), strict=True)
            )
        ]

        assert motif_change_starts(candidates) == frozenset({1}), "sonst misst der Fall nichts"
        # Wie der erzwungene Start gerechnet haette: ab Foto 1 neu - und dann meldet die
        # Ausdehnung nie wieder.
        assert [event.photo_ids for event in _build(candidates[1:], [ExtentSignal()])] == [
            tuple(range(1, len(candidates)))
        ]
        # Wie jetzt gerechnet wird: die Box laeuft weiter und trennt bei Foto 2 - SPAETER als der
        # erzwungene Start bei Foto 1 getrennt haette.
        assert [event.photo_ids for event in _build(candidates, [ExtentSignal()])] == [
            (0, 1),
            tuple(range(2, len(candidates))),
        ]

    def test_a_motif_boundary_on_an_index_that_already_splits_changes_nothing(self) -> None:
        """Faellt die Motivgrenze auf einen Index, an dem ohnehin getrennt wird, sind Anzahl,
        Mitgliedschaft und Positionen identisch zum motivfreien Lauf."""
        # Der Abstand zum Foto davor (das selbst bei `T0 + EPSILON_TIME` liegt) muss die Luecke
        # ECHT ueberschreiten - `TimeGapSignal` vergleicht mit `>`, nicht mit `>=`.
        after_the_gap = T0 + _time_gap() + 2 * EPSILON_TIME
        times = [T0, T0 + EPSILON_TIME] + [
            after_the_gap + index * EPSILON_TIME for index in range(_window())
        ]
        candidates = [_placeless_candidate(index, taken_at) for index, taken_at in enumerate(times)]
        candidates = [
            replace(candidate, motif_strengths=picture)
            for candidate, picture in zip(
                candidates,
                [_picture("a")] * 2 + [_picture("a", "b")] * _window(),
                strict=True,
            )
        ]
        without_motifs = [replace(candidate, motif_strengths=None) for candidate in candidates]

        events = _build(candidates, default_signals())
        reference = _build(without_motifs, default_signals())

        assert [(event.photo_ids, event.position) for event in events] == [
            (event.photo_ids, event.position) for event in reference
        ]

    def test_a_window_spanning_midnight_keeps_everything_in_one_event(self) -> None:
        """Der rueckwirkende Beginn liegt auf dem VORTAG, das bestaetigende Foto dahinter - und
        KEINE der beiden Stellen trennt noch: die Mitternachtsgrenze nicht (seit ADR 0117) und der
        Motivwechsel nicht mehr (seit ADR 0119). Braucht `default_signals()`, weil genau dieser
        Satz die Dauergrenze anstelle des Kalendertags fuehrt.

        Die Fotos liegen einen Sekundenschritt auseinander, der Wechsel faellt auf das erste nach
        Mitternacht. KEIN Abstand dieser Lage ist aus einer Uhrzeit gebaut: Ein Sprung von
        `23:30` auf `23:59:59` risse unter einer kleineren Zeitluecken-Schwelle eine Grenze auf,
        und der Fall maesse dann den Kalendertag gar nicht mehr."""
        midnight = datetime(2026, 7, 21, 0, 0, 0)
        candidates = [
            EventCandidate(
                photo_id=index,
                taken_at=midnight + (index - 2) * EPSILON_TIME,
                motif_strengths=picture,
            )
            for index, picture in enumerate([_picture("a")] * 2 + [_picture("a", "b")] * _window())
        ]

        events = _build(candidates, default_signals())

        assert candidates[1].taken_at.date() != candidates[2].taken_at.date(), (
            "sonst laeuft der Fall gar nicht ueber Mitternacht"
        )
        assert motif_change_starts(candidates) == frozenset({2}), "sonst misst der Fall nichts"
        assert [event.photo_ids for event in events] == [tuple(range(_window() + 2))]
        assert events[0].started_at.date() != events[0].ended_at.date()

    def test_a_run_without_any_carried_motif_groups_exactly_as_one_without_motif_fields(
        self,
    ) -> None:
        """Traegt kein Foto ein getragenes Motiv - weder als fehlende Kopfzeile noch als leeres
        Motivbild -, sind Anzahl, Mitgliedschaft und Positionen die bisherigen."""
        offsets = [0, 30, 61, 95, 400, 460, 461, 900, 1400, 1450]
        plain = [
            _placeless_candidate(index, _at(minutes=offset))
            for index, offset in enumerate(offsets, start=1)
        ]
        empty_pictures = [replace(candidate, motif_strengths=_picture()) for candidate in plain]

        reference = [
            (event.photo_ids, event.position) for event in _build(plain, default_signals())
        ]

        assert [
            (event.photo_ids, event.position) for event in _build(empty_pictures, default_signals())
        ] == reference


class TestEveryShortSequenceOverATinyMotifAlphabet(_UnderEveryConfirmingWindow):
    """Eine ERSCHOEPFENDE AUFZAEHLUNG an der Stelle, an der sonst Property-Testing staende -
    `hypothesis` waere eine ADR-pflichtige neue Abhaengigkeit, und hier braucht es keinen Zufall.

    Aufgezaehlt werden ALLE Folgen der Laenge `MOTIF_CHANGE_CONFIRMING_PHOTOS + 2` ueber vier
    Motivbildern: keine Kopfzeile, leeres Motivbild, ein Motiv, zwei Motive. Das deckt die Formen
    ab, die eine handverlesene Fallmenge nicht aufzaehlt (leeres fuehrendes Event, Index 0, ein
    Foto in zwei Events).

    ZULAESSIG ist die Form nur, solange Alphabet und Laenge winzig bleiben: die Zahl der Laeufe
    waechst exponentiell, und jeder einzelne muss linear und DB-frei sein."""

    def test_every_sequence_keeps_the_invariants_and_the_index_promises(self) -> None:
        alphabet = (None, _picture(), _picture("a"), _picture("a", "b"))
        found_a_start = False

        for combination in product(alphabet, repeat=_window() + 2):
            candidates = _motif_candidates(list(combination))
            starts = motif_change_starts(candidates)
            found_a_start = found_a_start or bool(starts)

            assert 0 not in starts, combination
            assert starts <= set(range(len(candidates))), combination
            # Kein anderes Signal spricht bei diesen Kandidaten mit (Sekundenabstand, kein Ort,
            # kein Name). Seit ADR 0119 eroeffnet ein bestaetigter Wechsel KEIN Event mehr - die
            # ganze Folge bleibt EIN Event, gleich wie viele Starts die erste Stufe liefert.
            events = _build(candidates, default_signals())
            assert [event.photo_ids for event in events] == [tuple(range(len(candidates)))], (
                combination
            )

        assert found_a_start, "sonst zaehlt die Aufzaehlung nur Folgen ohne jeden Wechsel"
