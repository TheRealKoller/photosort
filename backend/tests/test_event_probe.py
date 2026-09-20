"""Tests fuer das rein lesende Messkommando der Event-Bildung
(specs/features/0506-cluster-als-anlass.md, decisions/0117-*.md).

Aufbau nach architecture/0002-testkonzept.md, Sektion "Ein rein lesendes Kommando im
Produktivpaket": die Zaehlbloecke rein und ohne DB gegen einen von Hand ausgerechneten
Projektgraphen, `main()` synchron gegen eine dateibasierte SQLite in `tmp_path`.
"""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Collection
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import events as events_module
from photosort import selection as selection_module
from photosort import worker
from photosort.db import Base, make_engine, make_session_factory
from photosort.event_inputs import EventInputs
from photosort.event_probe import (
    COHERENCE_TOP_EVENTS,
    DISTANCE_THRESHOLD_METERS,
    MOTIF_CONFIRMING_VARIANTS,
    MOTIF_STRENGTH_VARIANTS,
    CoherenceCounts,
    CoherenceRow,
    EventProbeError,
    EventProbeInput,
    _quota_lines,
    _tally,
    block_counts,
    cause_counts,
    coherence_counts,
    inheritance_counts,
    landmark_counts,
    main,
    match_distance_counts,
    motif_change_off_window,
    motif_sensitivity,
    quota_reach,
    read_event_probe_input,
    render_coherence_report,
    size_counts,
)
from photosort.events import (
    BOUNDARY_CAUSES,
    BOUNDARY_MOTIF_CHANGE,
    BOUNDARY_STEP,
    BOUNDARY_TIME_GAP,
    MERGE_BLOCK_EXTENT,
    MERGE_BLOCK_NO_NEIGHBOUR,
    MERGE_BLOCK_REASONS,
    MERGE_BLOCK_TIME_GAP,
    MERGE_BLOCK_UNBREAKABLE,
    BlockedSegment,
    BuiltEvent,
    EventCandidate,
    EventFormation,
    LocationEntry,
    build_events,
    explain_events,
    has_measured_coordinate,
)
from photosort.geonames import GEONAMES_MAX_DISTANCE_METERS, dataset_hash_path
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoLandmarkDetection,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
)
from photosort.place_dataset import write_extract
from photosort.selection import carried_motifs, effective_target
from tests.import_closure import import_closure, module_file
from tests.write_guard import write_statements

NOW = datetime(2026, 7, 20, 10, 0, 0)


def _candidate(minutes: float, *, gps: tuple[float, float] | None = None) -> EventCandidate:
    """Ein Kandidat OHNE Ort, sofern keiner genannt ist: die Zeitluecke allein gliedert dann."""
    return EventCandidate(
        photo_id=int(minutes * 60),
        taken_at=NOW + timedelta(minutes=minutes),
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )


def _candidate_of(entry: LocationEntry) -> EventCandidate:
    """Derselbe Eintrag als Kandidat - ohne `location`, weil Block C1 die Uebernahme selbst misst
    und nicht ihr Ergebnis."""
    return EventCandidate(
        photo_id=entry.photo_id,
        taken_at=entry.taken_at,
        gps_lat=entry.gps_lat,
        gps_lon=entry.gps_lon,
    )


def _named_candidate(
    photo_id: int, minutes: float, name: str, *, gps: tuple[float, float] | None = None
) -> EventCandidate:
    """Ein Kandidat mit bereits geprueftem Sehenswuerdigkeit-Namen - so, wie ihn `event_inputs`
    liefert (`usable_landmark_name` ist dort bereits gelaufen)."""
    return EventCandidate(
        photo_id=photo_id,
        taken_at=NOW + timedelta(minutes=minutes),
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
        landmark_name=name,
    )


async def _project(session: AsyncSession, name: str = "Reise") -> int:
    project = Project(name=name, opencloud_drive_id="drive", opencloud_path=f"/Fotos/{name}")
    session.add(project)
    await session.flush()
    return project.id


async def _photo(
    session: AsyncSession,
    project_id: int,
    *,
    minutes: float,
    gps: tuple[float, float] | None = None,
) -> int:
    photo = Photo(
        project_id=project_id,
        relative_path=f"img{int(minutes * 60):06d}.jpg",
        etag=f"etag-{project_id}-{minutes}",
        content_length=1000,
        taken_at=NOW + timedelta(minutes=minutes),
        taken_at_original=NOW + timedelta(minutes=minutes),
        last_modified=NOW,
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )
    session.add(photo)
    await session.flush()
    return photo.id


async def _successful_run(
    session: AsyncSession, project_id: int, photo_ids: list[int]
) -> CriterionScoringRun:
    """Ein erfolgreicher Kriterien-Lauf samt seiner Rangzeilen - die Kandidatenmenge des Laufs.

    Ein Event je Rangzeile: Block A rechnet die Gliederung ohnehin neu, die Event-Zeile traegt
    hier nur den Fremdschluessel."""
    scoring_run = ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project_id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    event = Event(
        criterion_scoring_run_id=run.id, position=1, started_at=NOW, ended_at=NOW, place_kind=None
    )
    session.add(event)
    await session.flush()
    session.add_all(
        [
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo_id,
                event_id=event.id,
                rank_score=0.5,
                rank_position=position,
            )
            for position, photo_id in enumerate(photo_ids, start=1)
        ]
    )
    await session.flush()
    return run


@pytest.mark.asyncio
class TestTheReadPath:
    """Der einzige Datenbankzugriff des Kommandos - und er liest ausschliesslich."""

    async def test_an_unknown_project_refuses_loudly(self, db_session: AsyncSession) -> None:
        with pytest.raises(EventProbeError):
            await read_event_probe_input(db_session, 4711)

    async def test_a_project_without_a_successful_run_is_marked_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """ "Kein erfolgreicher Lauf" ist etwas anderes als "ein Lauf ohne Kandidaten" - eine
        gemeinsame leere Menge verwischte beides."""
        project_id = await _project(db_session)
        await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))

        probe = await read_event_probe_input(db_session, project_id)

        assert probe.run_found is False
        assert probe.candidates == ()

    async def test_the_candidates_are_the_ranked_photos_of_the_run(
        self, db_session: AsyncSession
    ) -> None:
        """Die Kandidatenmenge des Laufs sind genau die Fotos seiner Rangzeilen - nicht die
        aktuellen Fotos des Projekts. Ein nach dem Lauf aussortiertes oder hinzugekommenes Foto
        speist die Inferenzbasis, wird aber nie Kandidat."""
        project_id = await _project(db_session)
        ranked = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        unranked = await _photo(db_session, project_id, minutes=5, gps=(43.52, 16.45))
        await _successful_run(db_session, project_id, [ranked])

        probe = await read_event_probe_input(db_session, project_id)

        assert probe.run_found is True
        assert [candidate.photo_id for candidate in probe.candidates] == [ranked]
        # Die Inferenzbasis bleibt das ganze Projekt: ein aussortiertes Foto traegt eine ebenso
        # gueltige Koordinate.
        assert {entry.photo_id for entry in probe.entries} == {ranked, unranked}

    async def test_the_configured_target_and_the_photo_count_of_the_project_are_read(
        self, db_session: AsyncSession
    ) -> None:
        """Beides speist den Album-Richtwert, und beides kommt aus DEM Projekt: `NULL` heisst
        "nicht selbst eingestellt", und die Bilderzahl ist jedes Foto des Projekts - dieselbe
        Menge, die auch `worker.py` zaehlt, nicht die Kandidatenmenge des Laufs."""
        project_id = await _project(db_session)
        ranked = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        await _photo(db_session, project_id, minutes=5, gps=(43.52, 16.45))
        await _successful_run(db_session, project_id, [ranked])

        probe = await read_event_probe_input(db_session, project_id)

        assert probe.selection_target is None
        assert probe.project_photos == 2
        assert len(probe.candidates) == 1

    async def test_a_configured_target_reaches_the_measurement(
        self, db_session: AsyncSession
    ) -> None:
        project_id = await _project(db_session)
        ranked = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        await _successful_run(db_session, project_id, [ranked])
        project = await db_session.get(Project, project_id)
        assert project is not None
        project.selection_target = 12
        await db_session.flush()

        probe = await read_event_probe_input(db_session, project_id)

        assert probe.selection_target == 12

    async def test_only_the_latest_successful_run_is_measured(
        self, db_session: AsyncSession
    ) -> None:
        project_id = await _project(db_session)
        older = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        newer = await _photo(db_session, project_id, minutes=5, gps=(43.52, 16.45))
        await _successful_run(db_session, project_id, [older])
        await _successful_run(db_session, project_id, [newer])

        probe = await read_event_probe_input(db_session, project_id)

        assert [candidate.photo_id for candidate in probe.candidates] == [newer]


class TestBlockASizes:
    """Wie sich die Bilder heute ueber die Cluster verteilen - der Ausgangswert, gegen den die
    Abnahme laeuft."""

    def test_the_hand_computed_graph(self) -> None:
        """Vier Events zu 3, 1, 2 und 1 Fotos, von Hand gestellt statt aus Zeitabstaenden gebaut:
        Eine Lage aus Abstaenden haenge an den Zahlwerten der Schwellen und waere nach der
        Kalibrierung eine Zeitbombe - Block A zaehlt ohnehin ueber die fertige Gliederung."""
        counts = size_counts(_sized_formation((3, 8), (1, 0), (2, 2), (1, 0)))

        assert counts.events_total == 4
        assert counts.photos_total == 7
        assert counts.events_by_photo_count == {1: 2, 2: 1, 3: 1}
        assert counts.single_photo_events == 2
        # Die vier Groessen sortiert: 1, 1, 2, 3 - der Median liegt zwischen 1 und 2.
        assert counts.median_photos == 1.5
        assert counts.largest_event_photos == 3
        # DAUERN, nie Anfang oder Ende (S2): laengste acht Minuten, kuerzeste null (Einzelfoto).
        assert counts.longest_seconds == 8 * 60
        assert counts.shortest_seconds == 0

    def test_a_run_without_a_single_event_is_a_valid_result(self) -> None:
        """Ein Lauf ohne Kandidaten ist ein gueltiges Messergebnis, kein Fehler - es gibt dann
        keine laengste und keine kuerzeste Dauer, und `None` ist etwas anderes als null."""
        counts = size_counts(explain_events([]))

        assert counts.events_total == 0
        assert counts.photos_total == 0
        assert counts.events_by_photo_count == {}
        assert counts.single_photo_events == 0
        assert counts.median_photos is None
        assert counts.largest_event_photos == 0
        assert counts.longest_seconds is None
        assert counts.shortest_seconds is None


class TestBlockAQuotaReach:
    """Ob die Kontingentvergabe ueberhaupt gewichten kann - das Mass, an dem die Zerstueckelung
    haengt. Der Anteil der Ein-Bild-Cluster ist nur ein Hilfsmass daneben.

    DIE LAGEN STEHEN UEBER EINEN EINGESTELLTEN RICHTWERT, nie ueber eine Bilderzahl, aus der er
    sich ergaebe: Eine Lage aus Fotozahlen haenge am Zahlwert von `DEFAULT_TARGET_DIVISOR` und
    ginge nur gegen den heutigen Wert auf. Die Ableitung selbst prueft der Fall darunter, und zwar
    gegen `effective_target` statt gegen eine Zahl."""

    def test_more_events_than_seats_leaves_nothing_to_weight(self) -> None:
        """Die gemessene Lage: deutlich mehr Events als Plaetze. "Abdeckung zuerst" vergibt jeden
        Platz, bevor die Gewichtung beginnt - kein Restplatz bleibt."""
        reach = quota_reach(_probe_input(selection_target=38, project_photos=373), events_total=81)

        assert reach.target == 38
        assert reach.target_is_configured is True
        assert reach.events_total == 81
        assert reach.free_seats == 0
        assert reach.weighting_is_effective is False

    def test_fewer_events_than_seats_leaves_seats_to_weight(self) -> None:
        reach = quota_reach(_probe_input(selection_target=38, project_photos=373), events_total=20)

        assert reach.free_seats == 18
        assert reach.weighting_is_effective is True

    def test_as_many_events_as_seats_already_exhausts_them(self) -> None:
        """Die Grenze liegt bei Gleichstand, nicht darueber: `_quotas` bricht ab, sobald nach der
        Abdeckung nichts mehr uebrig ist (`remaining <= 0`)."""
        reach = quota_reach(_probe_input(selection_target=38, project_photos=373), events_total=38)

        assert reach.free_seats == 0
        assert reach.weighting_is_effective is False

    def test_the_target_comes_from_selection_itself_not_from_a_second_formula(self) -> None:
        """Nicht nachgebildet: Eine zweite Fassung der Ableitung liefe beim naechsten Grenzfall
        auseinander. Geprueft ueber mehrere Bilderzahlen, damit nicht eine einzelne Zahl zufaellig
        uebereinstimmt."""
        for photo_count in (0, 1, 9, 10, 11, 373, 1000):
            reach = quota_reach(
                _probe_input(selection_target=None, project_photos=photo_count), events_total=5
            )

            assert reach.target == effective_target(None, photo_count)
            assert reach.target_is_configured is False

    def test_a_configured_target_is_reported_as_configured(self) -> None:
        """Eine eingestellte Zahl gilt absolut - und der Bericht sagt, dass sie eingestellt ist:
        "38 aus 373 Fotos abgeleitet" und "38 eingestellt" sind verschiedene Aussagen."""
        reach = quota_reach(_probe_input(selection_target=7, project_photos=373), events_total=5)

        assert reach.target == 7
        assert reach.target_is_configured is True

    def test_the_measured_sets_are_carried_side_by_side(self) -> None:
        """Die Auswertungsgrenze: Der Richtwert rechnet auf jedem Foto des Projekts, die gemessene
        Gliederung auf der Kandidatenmenge des Laufs. Beide Zahlen stehen nebeneinander, damit ein
        Auseinanderfallen sichtbar wird statt verrechnet zu werden."""
        probe = _probe_input(selection_target=None, project_photos=400, candidates=3)

        reach = quota_reach(probe, events_total=5)

        assert reach.project_photos == 400
        assert reach.candidates_total == 3
        assert reach.measured_on_the_same_set is False

    def test_the_same_set_is_reported_as_such(self) -> None:
        probe = _probe_input(selection_target=None, project_photos=3, candidates=3)

        assert quota_reach(probe, events_total=1).measured_on_the_same_set is True

    def test_the_verdict_is_written_out_as_a_sentence(self) -> None:
        """Ein Zahlenpaar liesse den Schluss beim Leser, und genau dieser Schluss ist das Mass -
        er gehoert ausgeschrieben."""
        lines = _quota_lines(quota_reach(_probe_input(selection_target=38), events_total=81))

        text = "\n".join(lines)
        assert "kann nicht gewichten" in text
        assert "jedes Event bekommt genau einen Platz" in text
        assert "kann gewichten:" not in text

    def test_the_other_direction_says_so_too(self) -> None:
        lines = _quota_lines(quota_reach(_probe_input(selection_target=38), events_total=20))

        text = "\n".join(lines)
        assert "kann gewichten" in text
        assert "kann nicht gewichten" not in text

    def test_the_diverging_sets_are_named_in_the_report(self) -> None:
        """Faellt die Bilderzahl mit der Kandidatenmenge auseinander, sagt der Bericht es - sonst
        laese sich der Richtwert fuer eine Aussage ueber die gemessene Menge halten."""
        diverging = _probe_input(selection_target=38, project_photos=400, candidates=3)
        same = _probe_input(selection_target=38, project_photos=3, candidates=3)

        assert "Auswertungsgrenze" in "\n".join(_quota_lines(quota_reach(diverging, 5)))
        assert "Auswertungsgrenze" not in "\n".join(_quota_lines(quota_reach(same, 5)))


def _probe_input(
    *, selection_target: int | None, project_photos: int = 0, candidates: int = 0
) -> EventProbeInput:
    """Ein gelesener Bestand ohne Datenbank - `quota_reach` rechnet rein ueber diese Felder."""
    return EventProbeInput(
        project_id=1,
        candidates=tuple(_candidate(index) for index in range(candidates)),
        entries=tuple(
            LocationEntry(
                photo_id=index, taken_at=NOW + timedelta(minutes=index), gps_lat=None, gps_lon=None
            )
            for index in range(project_photos)
        ),
        run_found=True,
        selection_target=selection_target,
    )


def _segment(position: int, photo_count: int, duration_minutes: int = 0) -> BuiltEvent:
    """Ein fertiges Segment fuer die Zaehlbloecke - Groesse, Position und Dauer."""
    return BuiltEvent(
        position=position,
        photo_ids=tuple(range(position * 100, position * 100 + photo_count)),
        started_at=NOW,
        ended_at=NOW + timedelta(minutes=duration_minutes),
    )


def _sized_formation(*segments: tuple[int, int]) -> EventFormation:
    """Eine Gliederung aus `(Fotozahl, Dauer in Minuten)` - ohne Ursachen, die Block A nicht liest."""
    events = tuple(
        _segment(position, photo_count, duration)
        for position, (photo_count, duration) in enumerate(segments, start=1)
    )
    return EventFormation(events=events, causes=tuple(frozenset() for _ in events))


def _formation(
    *segments: tuple[int, frozenset[str]],
    dissolved_boundaries: int = 0,
    moved_photos: int = 0,
) -> EventFormation:
    """Eine Gliederung SAMT Ursachen, von Hand gestellt: `(Fotozahl, Ursachenmenge)` je Segment.

    Von Hand statt ueber `explain_events`, weil Block B eine reine Zaehlung ueber die Ursachen ist
    - eine Testlage aus Zeitabstaenden haenge an den Zahlwerten der Schwellen und waere nach der
    Kalibrierung eine Zeitbombe."""
    return EventFormation(
        events=tuple(
            _segment(position, photo_count)
            for position, (photo_count, _) in enumerate(segments, start=1)
        ),
        causes=tuple(causes for _, causes in segments),
        dissolved_boundaries=dissolved_boundaries,
        moved_photos=moved_photos,
    )


class TestBlockBCauses:
    """Welche Trennursache wie oft trennt. Nur "war alleinige Ursache" ist handlungsleitend - eine
    Schwelle anzuheben hilft dort, wo sie allein getrennt hat."""

    def test_the_hand_computed_graph(self) -> None:
        # "Gross genug" und "zu klein" kommen aus `MIN_EVENT_PHOTOS`, nie aus einer Zahl: Eine Lage
        # aus festen Fotozahlen geht nur gegen den heutigen Wert auf.
        big = events_module.MIN_EVENT_PHOTOS
        small = big - 1
        counts = cause_counts(
            _formation(
                # Das erste Segment traegt KEINE Ursache - die Ausnahme haengt an der Position.
                (big + 1, frozenset()),
                # Alleinige Ursache, und sie eroeffnet ein zu kleines Segment.
                (small, frozenset({BOUNDARY_TIME_GAP})),
                # ZWEI Ursachen gleichzeitig: beteiligt, aber keine allein.
                (big + 2, frozenset({BOUNDARY_TIME_GAP, BOUNDARY_STEP})),
                # Alleinige Ursache, aber das Segment ist gross genug.
                (big, frozenset({BOUNDARY_STEP})),
                (small, frozenset({BOUNDARY_MOTIF_CHANGE})),
            )
        )

        # Die Zahl der Grenzen MIT Ursache ist stets `Eventzahl - 1`.
        assert counts.boundaries_total == 4
        assert counts.involved[BOUNDARY_TIME_GAP] == 2
        assert counts.involved[BOUNDARY_STEP] == 2
        assert counts.involved[BOUNDARY_MOTIF_CHANGE] == 1
        # Die Doppelgrenze zaehlt bei KEINER der beiden als alleinige Ursache.
        assert counts.sole[BOUNDARY_TIME_GAP] == 1
        assert counts.sole[BOUNDARY_STEP] == 1
        assert counts.sole[BOUNDARY_MOTIF_CHANGE] == 1
        # Zu kleine Segmente: das hinter der Zeitluecke und das hinter dem Motivwechsel. Das
        # Segment hinter dem Schritt erreicht `MIN_EVENT_PHOTOS` und zaehlt nicht mit.
        assert counts.opening_a_small_segment[BOUNDARY_TIME_GAP] == 1
        assert counts.opening_a_small_segment[BOUNDARY_STEP] == 0
        assert counts.opening_a_small_segment[BOUNDARY_MOTIF_CHANGE] == 1

    def test_every_cause_of_the_closed_supply_appears_even_at_zero(self) -> None:
        """Eine Ursache, die im Lauf nie gemeldet hat, steht mit null da - sie faellt nicht aus dem
        Bericht. Sonst waere er still unvollstaendig, ohne dass eine Summe kleiner wuerde."""
        counts = cause_counts(_formation((2, frozenset()), (2, frozenset({BOUNDARY_TIME_GAP}))))

        assert set(counts.involved) == set(BOUNDARY_CAUSES)
        assert set(counts.sole) == set(BOUNDARY_CAUSES)
        assert set(counts.opening_a_small_segment) == set(BOUNDARY_CAUSES)

    def test_a_single_event_has_no_boundary_at_all(self) -> None:
        counts = cause_counts(_formation((5, frozenset())))

        assert counts.boundaries_total == 0
        assert sum(counts.involved.values()) == 0

    def test_a_run_without_events_does_not_report_a_negative_boundary_count(self) -> None:
        counts = cause_counts(explain_events([]))

        assert counts.boundaries_total == 0

    def test_the_minimum_size_is_read_as_a_module_attribute_not_bound_at_import(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`MIN_EVENT_PHOTOS` wird bei JEDER Zaehlung frisch aus `events.py` gelesen.

        Ein `from photosort.events import MIN_EVENT_PHOTOS` baende den Wert beim Import: Jede
        Fixture, die die Konstante verschiebt, liefe hier ins Leere, und die Spalte "eroeffnet ein
        zu kleines Segment" zaehlte still gegen eine andere Mindestgroesse als die, nach der
        gegliedert wurde. Aufgefallen beim Probelauf mit verschobenen Konstanten."""
        monkeypatch.setattr(events_module, "MIN_EVENT_PHOTOS", 3)

        counts = cause_counts(_formation((5, frozenset()), (2, frozenset({BOUNDARY_TIME_GAP}))))

        assert counts.opening_a_small_segment[BOUNDARY_TIME_GAP] == 1

    def test_a_cause_outside_the_closed_supply_refuses_loudly(self) -> None:
        """Nicht stillschweigend uebergehen: Ein kuenftiges Signal ohne Eintrag in
        `BOUNDARY_CAUSES` verschwaende sonst aus dem Bericht, ohne dass eine Summe kleiner wuerde."""
        with pytest.raises(EventProbeError):
            cause_counts(_formation((2, frozenset()), (2, frozenset({"erfunden"}))))


class TestBlockBCountsTheCounterIndicationOfTheThirdStage:
    """Die GEGENANZEIGE: Beide Abnahmezahlen dieser Spec - der Anteil der Ein-Bild-Cluster und die
    Eventzahl - wuerden von einer zu aggressiven Verschmelzung BESSER erfuellt. Ohne diese beiden
    Zahlen misst die Nachmessung nur die Unter-Zerstueckelung."""

    def test_the_dissolved_boundaries_are_counted_against_the_state_before_the_stage(self) -> None:
        """Bezugsgroesse ist die Zahl der Grenzen VOR Stufe 3 - gegen die Zahl danach gerechnet
        wuerde der Anteil mit jeder weiteren Aufloesung groesser statt aussagekraeftiger."""
        counts = cause_counts(
            _formation(
                (3, frozenset()),
                (2, frozenset({BOUNDARY_TIME_GAP})),
                (2, frozenset({BOUNDARY_STEP})),
                dissolved_boundaries=2,
                moved_photos=3,
            )
        )

        assert counts.boundaries_total == 2
        assert counts.dissolved_by_merge == 2
        assert counts.boundaries_before_merge == 4
        assert counts.photos_moved_by_merge == 3
        assert counts.photos_total == 7

    def test_a_run_that_merged_nothing_reports_zero_on_both(self) -> None:
        counts = cause_counts(_formation((2, frozenset()), (2, frozenset({BOUNDARY_TIME_GAP}))))

        assert counts.dissolved_by_merge == 0
        assert counts.photos_moved_by_merge == 0
        assert counts.boundaries_before_merge == counts.boundaries_total

    def test_the_counts_come_from_the_real_run_not_from_a_second_pass(self) -> None:
        """Gemessen wird die Gliederung, die auch entstanden ist. Eine zweite, nachbildende
        Zaehlung maesse die Grenzen einer Gliederung, die so nie existiert hat."""
        gap = events_module.EVENT_TIME_GAP + timedelta(seconds=1)
        candidates = [
            EventCandidate(photo_id=1, taken_at=NOW),
            EventCandidate(photo_id=2, taken_at=NOW + timedelta(seconds=1)),
            EventCandidate(photo_id=3, taken_at=NOW + timedelta(seconds=1) + gap),
        ]

        counts = cause_counts(explain_events(candidates))

        assert (counts.dissolved_by_merge, counts.photos_moved_by_merge) == (1, 1)
        assert counts.boundaries_before_merge == 1
        assert counts.boundaries_total == 0


def _blocked_formation(*blocked: tuple[frozenset[str], ...]) -> EventFormation:
    """Eine Gliederung samt der Beobachtung von Stufe 3, von Hand gestellt: je gesperrtem Segment
    seine Kanten, je Kante die Menge der Gruende.

    Von Hand statt ueber `merge_small_segments`, weil Block F eine reine Zaehlung ueber diese
    Mengen ist - eine Testlage aus Zeitabstaenden haenge an den Zahlwerten der Schwellen. Dass die
    Mengen entstehen, wie sie entstehen, haelt `test_events.py::TestWhyASegmentCouldNotBeMerged`
    fest."""
    return EventFormation(
        events=(_segment(1, 1),),
        causes=(frozenset(),),
        blocked_segments=tuple(BlockedSegment(edges=edges) for edges in blocked),
    )


def _edges(*reasons: Collection[str]) -> tuple[frozenset[str], ...]:
    """Die Kanten eines gesperrten Segments - je Kante die Menge ihrer Gruende."""
    return tuple(frozenset(reason) for reason in reasons)


def _one_big_segment_and_a_lone_photo_behind_the_merge_gap() -> list[EventCandidate]:
    """Ein Segment, das `MIN_EVENT_PHOTOS` erreicht, und ein einzelnes Foto jenseits von
    `MERGE_MAX_GAP` - also genau EIN gesperrtes Segment, und `zeitluecke` an seiner einen Kante.

    Die Groesse des ersten Segments kommt aus der Modulkonstante, nie aus einer Zahl: Mit einer
    festen Fotozahl waere auch das erste Segment zu klein, sobald `MIN_EVENT_PHOTOS` steigt, und
    der Fall zaehlte still zwei Blockaden statt einer."""
    filling = [
        EventCandidate(photo_id=index, taken_at=NOW + timedelta(seconds=index))
        for index in range(1, events_module.MIN_EVENT_PHOTOS + 1)
    ]
    behind_the_gap = filling[-1].taken_at + events_module.MERGE_MAX_GAP + timedelta(seconds=1)
    return [*filling, EventCandidate(photo_id=len(filling) + 1, taken_at=behind_the_gap)]


class TestBlockFWhyAMergeFailed:
    """Woran eine Zusammenlegung scheitert. ZWEI Zahlen je Grund, und nur die zweite ist
    handlungsleitend: Ein Segment mit zwei Nachbarn hat zwei Kanten, und ein Grund, der nur an
    einer stand, hat die Zusammenlegung nicht verhindert.

    "An allen Kanten DER Grund" heisst: an jeder Kante stand er, und an keiner stand etwas
    daneben. Nur dann loest seine Behebung dieses Segment tatsaechlich auf - dieselbe Bedeutung wie
    "alleinige Ursache" in Block B."""

    def test_the_hand_computed_graph(self) -> None:
        counts = block_counts(
            _blocked_formation(
                # An BEIDEN Kanten derselbe, einzige Grund - er hat fuer sich gesperrt.
                _edges({MERGE_BLOCK_UNBREAKABLE}, {MERGE_BLOCK_UNBREAKABLE}),
                # Zwei verschiedene Gruende: beide beteiligt, keiner an allen Kanten.
                _edges({MERGE_BLOCK_EXTENT}, {MERGE_BLOCK_TIME_GAP}),
                # Ein Randsegment: EINE Kante, dort zwei Gruende gleichzeitig. Beteiligt sind
                # beide; keiner stand allein, also traegt keiner die zweite Spalte.
                _edges({MERGE_BLOCK_EXTENT, MERGE_BLOCK_TIME_GAP}),
            )
        )

        assert counts.blocked_segments == 3
        assert counts.involved[MERGE_BLOCK_UNBREAKABLE] == 1
        assert counts.involved[MERGE_BLOCK_EXTENT] == 2
        assert counts.involved[MERGE_BLOCK_TIME_GAP] == 2
        assert counts.involved[MERGE_BLOCK_NO_NEIGHBOUR] == 0
        assert counts.at_every_edge[MERGE_BLOCK_UNBREAKABLE] == 1
        assert counts.at_every_edge[MERGE_BLOCK_EXTENT] == 0
        assert counts.at_every_edge[MERGE_BLOCK_TIME_GAP] == 0
        assert counts.at_every_edge[MERGE_BLOCK_NO_NEIGHBOUR] == 0

    def test_a_reason_beside_another_one_is_never_the_reason_at_that_edge(self) -> None:
        """Der Fall, der die zweite Spalte belastbar macht: `ausdehnung` steht an beiden Kanten,
        an einer aber neben `zeitluecke`. Seine Behebung loeste dieses Segment NICHT auf - die
        Spalte darf ihn deshalb nicht zaehlen, die erste sehr wohl."""
        counts = block_counts(
            _blocked_formation(
                _edges({MERGE_BLOCK_EXTENT}, {MERGE_BLOCK_EXTENT, MERGE_BLOCK_TIME_GAP})
            )
        )

        assert counts.involved[MERGE_BLOCK_EXTENT] == 1
        assert counts.involved[MERGE_BLOCK_TIME_GAP] == 1
        assert counts.at_every_edge[MERGE_BLOCK_EXTENT] == 0

    def test_a_reason_is_counted_once_per_segment_not_once_per_edge(self) -> None:
        """Gezaehlt werden SEGMENTE: Die Frage ist, wie viele Zusammenlegungen ein Grund verhindert
        hat, nicht wie oft er auftrat."""
        counts = block_counts(
            _blocked_formation(_edges({MERGE_BLOCK_TIME_GAP}, {MERGE_BLOCK_TIME_GAP}))
        )

        assert counts.involved[MERGE_BLOCK_TIME_GAP] == 1
        assert counts.at_every_edge[MERGE_BLOCK_TIME_GAP] == 1

    def test_every_reason_of_the_closed_supply_appears_even_at_zero(self) -> None:
        """Ein Grund, der nie an einer Kante stand, steht mit null da - er faellt nicht aus dem
        Bericht. Sonst waere er still unvollstaendig, ohne dass eine Summe kleiner wuerde."""
        counts = block_counts(_blocked_formation(_edges({MERGE_BLOCK_TIME_GAP})))

        assert set(counts.involved) == set(MERGE_BLOCK_REASONS)
        assert set(counts.at_every_edge) == set(MERGE_BLOCK_REASONS)

    def test_a_run_where_everything_could_be_merged_reports_no_blockade(self) -> None:
        counts = block_counts(_blocked_formation())

        assert counts.blocked_segments == 0
        assert sum(counts.involved.values()) == 0
        assert sum(counts.at_every_edge.values()) == 0

    def test_a_reason_outside_the_closed_supply_refuses_loudly(self) -> None:
        """Nicht stillschweigend uebergehen: Ein kuenftiger Riegel ohne Eintrag in
        `MERGE_BLOCK_REASONS` verschwaende sonst aus dem Bericht."""
        with pytest.raises(EventProbeError):
            block_counts(_blocked_formation(_edges({"erfunden"})))

    def test_the_counts_come_from_the_real_run_not_from_a_second_pass(self) -> None:
        """ADR 0117 Punkt 5: Gezaehlt wird, woran die Stufe TATSAECHLICH gescheitert ist. Eine
        nachbildende Pruefung im Messkommando maesse etwas anderes, als die Stufe tut, waehrend
        beide fuer sich gruen blieben."""
        candidates = _one_big_segment_and_a_lone_photo_behind_the_merge_gap()

        counts = block_counts(explain_events(candidates))

        assert counts.blocked_segments == 1
        assert counts.involved[MERGE_BLOCK_TIME_GAP] == 1
        assert counts.at_every_edge[MERGE_BLOCK_TIME_GAP] == 1
        assert counts.involved[MERGE_BLOCK_NO_NEIGHBOUR] == 0

    def test_the_grouping_is_the_one_build_events_would_have_produced(self) -> None:
        """Beobachten, nicht veraendern: Der Modus rechnet dieselbe Gliederung wie Block A und B.
        Bekaeme er einen eigenen Rechenweg, maesse er die Blockaden einer Gliederung, die so nie
        entstanden ist - und beides bliebe fuer sich gruen."""
        candidates = _one_big_segment_and_a_lone_photo_behind_the_merge_gap()

        formation = explain_events(candidates)

        assert formation.blocked_segments, "sonst misst der Fall die Beobachtung gar nicht"
        assert list(formation.events) == build_events(candidates)


# --- Block E: die Empfindlichkeit des Motivwechsels -----------------------------------------------
#
# Die Motivstaerken dieser Faelle sind FREI GEWAEHLT und stehen zur Praesenzgrenze in keinem
# Verhaeltnis: `_CARRIED` und `_ABSENT` liegen an den Raendern der Skala und fallen unter JEDEM Wert
# des Rasters gleich aus. Kein Fall hier pinnt den Zahlwert einer Schwelle.
_CARRIED = 1.0
_ABSENT = 0.0


def _motif_candidate(index: int, motifs: dict[str, float]) -> EventCandidate:
    """Ein Kandidat mit Motiv-Kopfzeile, ohne Ort und Namen und mit einem Sekundenabstand: Kein
    anderes Trennsignal spricht mit, gleich wie lang die Folge wird."""
    return EventCandidate(
        photo_id=index,
        taken_at=NOW + timedelta(seconds=index),
        motif_strengths=dict(motifs),
    )


def _motif_sequence(deviating: int) -> list[EventCandidate]:
    """Ein Bezugsfoto, dann `deviating` Fotos, die zusaetzlich das Motiv "b" tragen."""
    reference = {"a": _CARRIED, "b": _ABSENT}
    changed = {"a": _CARRIED, "b": _CARRIED}
    return [
        _motif_candidate(index, picture)
        for index, picture in enumerate([reference, *([changed] * deviating)])
    ]


class TestBlockEMotifSensitivity:
    """Wie Eventzahl und Ein-Bild-Anteil an den beiden Festlegungen des Motivwechsels haengen.

    Gemessen wird mit den Mitteln des Laufs: `explain_events` unter variierten Werten, nie eine
    Nachbildung - eine zweite Fassung maesse etwas anderes, als der Lauf tut."""

    def test_the_grid_is_the_cross_product_plus_two_reference_rows(self) -> None:
        candidates = _motif_sequence(2)

        rows = motif_sensitivity(candidates)

        assert len(rows) == 2 + len(MOTIF_CONFIRMING_VARIANTS) * len(MOTIF_STRENGTH_VARIANTS)
        # Die erste Zeile ist der Betriebswert - die Tabelle traegt ihren eigenen Nullpunkt.
        assert rows[0].confirming_photos is None
        assert rows[0].strength_threshold is None
        assert rows[0].motif_change_is_off is False
        # Die zweite ist der andere Rand: der Motivwechsel ganz aus.
        assert rows[1].motif_change_is_off is True
        assert {(row.confirming_photos, row.strength_threshold) for row in rows[2:]} == {
            (confirming, strength)
            for confirming in MOTIF_CONFIRMING_VARIANTS
            for strength in MOTIF_STRENGTH_VARIANTS
        }

    def test_the_operating_row_is_the_run_itself(self) -> None:
        """Der Nullpunkt entsteht OHNE Ueberschreibung: Er muss die Gliederung sein, die auch der
        Lauf gebildet haette - sonst haette die Tabelle keinen Bezug, gegen den sie liest."""
        candidates = _motif_sequence(6)
        formation = explain_events(candidates)

        [operating] = [
            row
            for row in motif_sensitivity(candidates)
            if row.confirming_photos is None and row.strength_threshold is None
        ]

        assert operating.events_total == len(formation.events)
        assert (
            operating.sole_motif_boundaries == cause_counts(formation).sole[BOUNDARY_MOTIF_CHANGE]
        )

    def test_a_shorter_window_splits_more_often_than_a_longer_one(self) -> None:
        """Die Aussage, um derentwillen der Block gebaut ist - und sie steht als Ungleichung
        zwischen zwei Zeilen, nie als Zahlwert."""
        rows = {
            row.confirming_photos: row
            for row in motif_sensitivity(_motif_sequence(4))
            if row.strength_threshold == MOTIF_STRENGTH_VARIANTS[0]
        }
        shortest = rows[min(MOTIF_CONFIRMING_VARIANTS)]
        longest = rows[max(MOTIF_CONFIRMING_VARIANTS)]

        assert shortest.events_total > longest.events_total
        assert shortest.sole_motif_boundaries > longest.sole_motif_boundaries

    def test_every_row_carries_the_counter_indication_against_coarse_grouping(self) -> None:
        """Beide Abnahmezahlen wuerden von einem zu groben Zusammenfassen BESSER erfuellt - die
        Gegenanzeige steht deshalb in derselben Zeile, nicht daneben."""
        candidates = _motif_sequence(4)

        for row in motif_sensitivity(candidates):
            assert row.largest_event_photos >= 1
            assert row.longest_seconds is not None
            assert row.events_total >= 1
            assert row.single_photo_events <= row.events_total

    def test_a_run_without_candidates_yields_rows_without_invented_zeroes(self) -> None:
        """Der entartete Fall: kein Kandidat, also kein Event - und dann gibt es keine laengste
        Dauer. Eine Null hiesse "das laengste Event dauert nichts"."""
        rows = motif_sensitivity([])

        for row in rows:
            assert row.events_total == 0
            assert row.longest_seconds is None
            assert row.largest_event_photos == 0
            assert row.sole_motif_boundaries == 0

    def test_the_switched_off_row_confirms_no_change_at_all(self) -> None:
        """ "Aus" entsteht OHNE Abschaltpfad im Produktivcode: Ein Bestaetigungsfenster groesser als
        die Zahl der Kandidatenfotos kann nie bestaetigt werden - `motif_change_starts` zaehlt
        hoechstens so viele aufeinanderfolgende Fotos, wie es Fotos gibt.

        Die Gegenprobe steht daneben: Am Betriebswert trennt dieselbe Folge sehr wohl, sonst
        bestuende der Fall auch gegen ein wirkungsloses Fenster."""
        candidates = _motif_sequence(6)

        assert events_module.motif_change_starts(candidates), "sonst misst der Fall nichts"
        assert (
            events_module.motif_change_starts(
                candidates, confirming_photos=motif_change_off_window(candidates)
            )
            == frozenset()
        )

    def test_the_switched_off_row_carries_the_window_it_used(self) -> None:
        """Die Zeile fuehrt den tatsaechlich gerechneten Wert mit - beschriftet wird sie als "aus",
        aber gemessen wurde mit einer Zahl, und die steht in den Daten."""
        candidates = _motif_sequence(6)

        [switched_off] = [row for row in motif_sensitivity(candidates) if row.motif_change_is_off]

        assert switched_off.confirming_photos == motif_change_off_window(candidates)
        assert switched_off.strength_threshold is None
        assert switched_off.sole_motif_boundaries == 0

    def test_the_switched_off_row_carries_the_same_columns_as_every_other(self) -> None:
        """Dieselben Spalten, auch die Gegenanzeige: Ein ausgeschalteter Motivwechsel fasst am
        groebsten zusammen, und genau dort muessen groesstes Event und laengste Dauer ablesbar
        sein."""
        candidates = _motif_sequence(6)

        [switched_off] = [row for row in motif_sensitivity(candidates) if row.motif_change_is_off]

        assert switched_off.events_total >= 1
        assert switched_off.largest_event_photos == len(candidates)
        assert switched_off.longest_seconds is not None

    def test_switching_the_motif_change_off_never_splits_more_than_the_operating_point(
        self,
    ) -> None:
        """Die Aussage, um derentwillen die Zeile existiert - als Ungleichung zwischen zwei Zeilen,
        nie als Zahlwert."""
        candidates = _motif_sequence(6)
        rows = motif_sensitivity(candidates)
        operating, switched_off = rows[0], rows[1]

        assert switched_off.events_total < operating.events_total
        assert switched_off.sole_motif_boundaries < operating.sole_motif_boundaries

    def test_a_run_without_candidates_switches_off_without_an_invented_row(self) -> None:
        """Der entartete Fall: Ohne Kandidat gibt es nichts zu bestaetigen - das Fenster bleibt
        wohldefiniert, und die Zeile entsteht trotzdem."""
        [switched_off] = [row for row in motif_sensitivity([]) if row.motif_change_is_off]

        assert switched_off.events_total == 0
        assert switched_off.longest_seconds is None

    def test_the_grid_varies_both_festlegungen_not_just_one(self) -> None:
        """Gegenprobe gegen eine wirkungslose Variation: Beide Achsen muessen mehr als einen Wert
        tragen, sonst misst die Tabelle eine Dimension gar nicht."""
        assert len(set(MOTIF_CONFIRMING_VARIANTS)) > 1
        assert len(set(MOTIF_STRENGTH_VARIANTS)) > 1


# --- Der Kohaerenz-Modus: vier Zahlen je Event ---------------------------------------------------
#
# DIE BEIDEN STAERKEN DER TESTLAGE SIND KEINE SCHWELLE, sondern die beiden Raender: 1,0 wird
# getragen, 0,0 nicht. Welche Zahl dazwischen getragen wird, entscheidet allein
# `selection.carried_motifs`; die Lage pinnt sie nirgends, und ein Waechterfall haelt die beiden
# Raender selbst gegen `carried_motifs` fest, statt sie zu behaupten.
CARRIED = 1.0
NOT_CARRIED = 0.0


def _coherent(
    position: int,
    photo_ids: tuple[int, ...],
    *,
    minutes: float = 0.0,
    cells: tuple[tuple[float, float], ...] = (),
) -> BuiltEvent:
    """Ein fertiges Event mit seinen Zellen - von Hand gestellt wie in Block B.

    `place_cells` traegt `_cells_of` bereits sortiert und dublettenfrei bei; hier steht die Menge
    deshalb so, wie das Event sie traegt, und der Zaehlblock liest sie, statt sie nachzubilden."""
    return BuiltEvent(
        position=position,
        photo_ids=photo_ids,
        started_at=NOW,
        ended_at=NOW + timedelta(minutes=minutes),
        place_cells=cells,
    )


def _with_motifs(
    photo_id: int, *, gps: tuple[float, float] | None = None, **strengths: float
) -> EventCandidate:
    """Ein Kandidat mit Motiv-Kopfzeile - OHNE gemessene Koordinate, sofern keine genannt ist: Er
    haette seinen Ort dann uebernommen und speist keine Zelle."""
    return EventCandidate(
        photo_id=photo_id,
        taken_at=NOW,
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
        motif_strengths=dict(strengths),
    )


class TestCoherenceOfTheEvents:
    """Vier Zahlen je Event - Fotozahl, Dauer, Zahl der verschiedenen Ortszellen, Zahl der
    verschiedenen getragenen Motive.

    NUR ANZAHLEN, das ist die tragende Auflage dieses Modus (S2/S3): keine Zelle, keine Koordinate,
    kein Orts- oder Motivname, kein Zeitstempel. Die Aussagekraft entsteht aus den Zahlen selbst -
    ein langes Event mit ZWEI Ortszellen ist ein Ausflug, eines mit sechs sind verschmolzene
    Anlaesse."""

    def test_the_lay_itself_rests_on_selection_not_on_a_number(self) -> None:
        """Der Waechter unter dieser Testklasse: Traegt 1,0 nicht mehr und 0,0 doch, geht die ganze
        Lage schief - und zwar hier, mit Ansage, statt verstreut in jedem Fall darunter."""
        assert carried_motifs({"getragen": CARRIED, "nicht": NOT_CARRIED}) == {"getragen"}

    def test_the_hand_computed_graph(self) -> None:
        formation = EventFormation(
            events=(
                _coherent(1, (1, 2, 3), minutes=90, cells=((43.51, 16.44), (43.52, 16.45))),
                _coherent(2, (4,), minutes=0, cells=((44.0, 15.0),)),
            ),
            causes=(frozenset(), frozenset({BOUNDARY_TIME_GAP})),
        )
        candidates = (
            _with_motifs(1, gps=(43.51, 16.44), strand=CARRIED),
            _with_motifs(2, gps=(43.52, 16.45), strand=CARRIED, essen=CARRIED),
            # Das dritte Foto hat den Ort UEBERNOMMEN - es speist keine Zelle und zaehlt nicht mit.
            _with_motifs(3, berge=CARRIED),
            _with_motifs(4, gps=(44.0, 15.0), essen=CARRIED),
        )

        counts = coherence_counts(formation, candidates)

        assert counts.events_total == 2
        first, second = counts.largest
        assert (first.photos, first.measured_photos, first.place_cells, first.motifs) == (
            3,
            2,
            2,
            3,
        )
        assert first.duration_seconds == 90 * 60
        assert (second.photos, second.measured_photos, second.place_cells, second.motifs) == (
            1,
            1,
            1,
            1,
        )
        assert second.duration_seconds == 0.0

    def test_only_photos_with_a_measured_coordinate_are_counted_as_measured(self) -> None:
        """OHNE DIESE FUENFTE ZAHL IST DIE ZELLZAHL NICHT DEUTBAR. `events.py::_cells_of` nimmt
        ausschliesslich Kandidaten mit GEMESSENER Koordinate; ein uebernommener Ort speist sie
        ausdruecklich nicht. Ein Event, dessen Fotos ueberwiegend geerbt haben, zeigt deshalb eine
        kleine Zellzahl - und die laese sich als "ein Ort, also ein Ausflug" lesen, obwohl schlicht
        nichts gemessen wurde. In der Ausgangsmessung dieser Spec trugen 30,0 % der Kandidatenfotos
        keine eigene Koordinate."""
        formation = EventFormation(
            events=(_coherent(1, (1, 2, 3, 4), cells=((43.51, 16.44),)),), causes=(frozenset(),)
        )
        candidates = (
            _with_motifs(1, gps=(43.51, 16.44)),
            _with_motifs(2),
            _with_motifs(3),
            _with_motifs(4),
        )

        [row] = coherence_counts(formation, candidates).largest

        assert (row.photos, row.measured_photos, row.place_cells) == (4, 1, 1)

    def test_an_event_without_a_single_measured_photo_says_zero_not_nothing(self) -> None:
        formation = EventFormation(events=(_coherent(1, (1, 2)),), causes=(frozenset(),))

        [row] = coherence_counts(formation, (_with_motifs(1), _with_motifs(2))).largest

        assert (row.measured_photos, row.place_cells) == (0, 0)

    def test_measured_and_cells_rest_on_the_same_one_predicate(self) -> None:
        """Gegen zwei Begriffe von "dieses Foto hat eine gemessene Koordinate" im selben Produkt:
        Beide Spalten fragen `events.py::has_measured_coordinate`, und `_cells_of` tut es auch.
        Liefen sie auseinander, stuende die Zahl der gemessenen Fotos neben einer Zellzahl, die
        nach einer anderen Regel entstanden ist."""
        measured = EventCandidate(photo_id=1, taken_at=NOW, gps_lat=43.51, gps_lon=16.44)
        inherited = EventCandidate(photo_id=2, taken_at=NOW)
        # Eine halbe Koordinate ist keine: `_cells_of` verlangt BEIDE Werte.
        half = EventCandidate(photo_id=3, taken_at=NOW, gps_lat=43.51)

        assert has_measured_coordinate(measured) is True
        assert has_measured_coordinate(inherited) is False
        assert has_measured_coordinate(half) is False

        formation = explain_events([measured, inherited, half])
        rows = coherence_counts(formation, (measured, inherited, half)).largest

        assert sum(row.measured_photos for row in rows) == 1
        assert sum(row.place_cells for row in rows) == 1

    def test_only_the_distinct_cells_are_counted(self) -> None:
        """Gezaehlt werden VERSCHIEDENE Zellen: Zwoelf Aufnahmen an einem Ort sind ein Ort, nicht
        zwoelf - sonst maesse die Spalte die Fotozahl ein zweites Mal."""
        formation = EventFormation(
            events=(_coherent(1, (1, 2), cells=((43.51, 16.44),)),), causes=(frozenset(),)
        )

        [row] = coherence_counts(formation, (_with_motifs(1), _with_motifs(2))).largest

        assert row.place_cells == 1

    def test_an_event_without_a_single_measured_coordinate_counts_no_cell(self) -> None:
        formation = EventFormation(events=(_coherent(1, (1,)),), causes=(frozenset(),))

        [row] = coherence_counts(formation, (_with_motifs(1),)).largest

        assert row.place_cells == 0

    def test_only_the_distinct_motifs_are_counted(self) -> None:
        formation = EventFormation(events=(_coherent(1, (1, 2)),), causes=(frozenset(),))
        candidates = (_with_motifs(1, strand=CARRIED), _with_motifs(2, strand=CARRIED))

        [row] = coherence_counts(formation, candidates).largest

        assert row.motifs == 1

    def test_a_motif_that_is_not_carried_is_not_counted(self) -> None:
        formation = EventFormation(events=(_coherent(1, (1,)),), causes=(frozenset(),))
        candidates = (_with_motifs(1, strand=CARRIED, essen=NOT_CARRIED),)

        [row] = coherence_counts(formation, candidates).largest

        assert row.motifs == 1

    def test_the_carried_motifs_come_from_selection_not_from_a_second_comparison(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die eine Stelle, die "dieses Foto zeigt X" beantwortet, ist
        `selection.py::carried_motifs`. Wandert ihre Grenze, wandert diese Spalte mit - eine eigene
        Fassung hier waere ein zweiter Begriff desselben im selben Produkt."""
        formation = EventFormation(events=(_coherent(1, (1,)),), causes=(frozenset(),))
        candidates = (_with_motifs(1, strand=CARRIED),)
        assert coherence_counts(formation, candidates).largest[0].motifs == 1

        monkeypatch.setattr(selection_module, "MOTIF_PRESENCE_THRESHOLD", CARRIED + 1.0)

        assert coherence_counts(formation, candidates).largest[0].motifs == 0

    def test_a_photo_without_a_motif_header_carries_nothing(self) -> None:
        """`motif_strengths is None` heisst "keine Motiv-Kopfzeile" und ist etwas anderes als eine
        leere Kopfzeile. Beide tragen hier null Motive bei, und keines von beiden ist ein Fehler."""
        formation = EventFormation(events=(_coherent(1, (1, 2, 3)),), causes=(frozenset(),))
        candidates = (
            EventCandidate(photo_id=1, taken_at=NOW),
            _with_motifs(2),
            _with_motifs(3, strand=CARRIED),
        )

        [row] = coherence_counts(formation, candidates).largest

        assert row.motifs == 1

    def test_the_list_shows_the_largest_events_not_all_of_them(self) -> None:
        """Eine Vollliste waere ueber die Zellzahlen eine Bewegungsspur. Die Liste beantwortet die
        Frage "ein langer Ausflug oder mehrere verschmolzene Anlaesse", ohne vollstaendig zu sein -
        und der Bericht sagt, wonach ausgewaehlt wurde."""
        events = tuple(
            _coherent(position, tuple(range(position * 100, position * 100 + position)))
            for position in range(1, COHERENCE_TOP_EVENTS + 4)
        )
        formation = EventFormation(events=events, causes=tuple(frozenset() for _ in events))

        counts = coherence_counts(formation, ())

        assert counts.events_total == len(events)
        assert len(counts.largest) == COHERENCE_TOP_EVENTS
        # Die groessten zuerst, absteigend - und das kleinste Event ist nicht dabei.
        assert [row.photos for row in counts.largest] == sorted(
            (len(event.photo_ids) for event in events), reverse=True
        )[:COHERENCE_TOP_EVENTS]

    def test_the_order_rests_on_the_measured_values_not_on_the_chronology(self) -> None:
        """Sortiert wird nach Fotozahl, dann Dauer, dann Zellzahl, dann Motivzahl - ausschliesslich
        ueber gemessene Werte. Die Position im Lauf geht NICHT ein und steht auch nicht im Bericht:
        eine nach Zeit geordnete Folge von Zellzahlen waere ein Bewegungsabdruck."""
        formation = EventFormation(
            events=(
                _coherent(1, (1, 2), minutes=10),
                _coherent(2, (3, 4), minutes=90),
                _coherent(3, (5, 6, 7), minutes=1),
            ),
            causes=(frozenset(), frozenset(), frozenset()),
        )

        counts = coherence_counts(formation, ())

        assert [(row.photos, row.duration_seconds) for row in counts.largest] == [
            (3, 60.0),
            (2, 90 * 60.0),
            (2, 10 * 60.0),
        ]

    def test_the_distributions_cover_every_event_not_only_the_listed_ones(self) -> None:
        """Die Verteilungszeile laeuft ueber ALLE Events - sonst behauptete der Bericht eine
        Verteilung, die nur fuer die groessten gilt."""
        events = tuple(
            _coherent(position, (position,), cells=((43.5, 16.4),) * min(position, 2))
            for position in range(1, COHERENCE_TOP_EVENTS + 3)
        )
        formation = EventFormation(events=events, causes=tuple(frozenset() for _ in events))

        counts = coherence_counts(formation, ())

        assert sum(counts.cells_per_event.values()) == len(events)
        assert sum(counts.motifs_per_event.values()) == len(events)
        assert counts.motifs_per_event == {0: len(events)}

    def test_a_run_without_events_yields_no_invented_row(self) -> None:
        counts = coherence_counts(explain_events([]), ())

        assert counts.events_total == 0
        assert counts.largest == ()
        assert counts.cells_per_event == {}
        assert counts.motifs_per_event == {}


def _coherence_counts(
    *rows: tuple[int, int, float, int, int], events_total: int = 0
) -> CoherenceCounts:
    """Ein fertig gezaehltes Ergebnis, von Hand gestellt - die Ausgabe rechnet nicht, sie
    schreibt. Je Zeile: Fotos, davon gemessen, Dauer, Ortszellen, Motive."""
    return CoherenceCounts(
        events_total=events_total or len(rows),
        largest=tuple(
            CoherenceRow(
                photos=photos,
                measured_photos=measured,
                duration_seconds=seconds,
                place_cells=cells,
                motifs=motifs,
            )
            for photos, measured, seconds, cells, motifs in rows
        ),
        cells_per_event=_tally(cells for _, _, _, cells, _ in rows),
        motifs_per_event=_tally(motifs for _, _, _, _, motifs in rows),
    )


class TestTheCoherenceReport:
    """Beide Gliederungen nebeneinander, und je Event fuenf ANZAHLEN - sonst nichts."""

    def test_both_groupings_stand_side_by_side(self) -> None:
        """Die Frage dieses Modus ist ein Vergleich: Traegt das grosse Event der Gliederung "aus"
        einen Anlass oder mehrere? Eine der beiden Gliederungen allein beantwortet sie nicht."""
        report = render_coherence_report(
            _probe_input(selection_target=None),
            _coherence_counts((3, 3, 60.0, 1, 1)),
            _coherence_counts((9, 9, 600.0, 4, 3)),
        )

        assert "Betriebswert" in report
        assert "Motivwechsel aus" in report

    def test_a_row_carries_the_five_numbers_and_nothing_else(self) -> None:
        report = render_coherence_report(
            _probe_input(selection_target=None),
            _coherence_counts((28, 26, 2 * 3600.0 + 8 * 60.0, 2, 3)),
            _coherence_counts((80, 5, 5 * 3600.0, 6, 7)),
        )

        assert "| 28 | 26 | 2 h 8 min | 2 | 3 |" in report
        assert "| 80 | 5 | 5 h | 6 | 7 |" in report
        # Fuenf Spalten je Zeile, nicht sechs: kein Rang, keine Position, keine Kennung.
        for line in report.splitlines():
            if line.startswith("| ") and not line.startswith("| Fotos"):
                assert line.count("|") == 6, line

    def test_the_reading_of_the_cell_count_is_bound_to_the_measured_photos(self) -> None:
        """DER DEUTUNGSSATZ GILT NUR SOWEIT GEMESSEN WURDE. "Zwei Ortszellen, also ein Ausflug" ist
        bei 80 Fotos, von denen fuenf eine Koordinate tragen, kein Befund, sondern eine Luecke -
        und sie sieht genauso aus wie ein Befund. Der Bericht muss das sagen, nicht der Leser."""
        report = render_coherence_report(
            _probe_input(selection_target=None),
            _coherence_counts((28, 26, 60.0, 2, 3)),
            _coherence_counts((80, 5, 5 * 3600.0, 2, 7)),
        )

        assert "davon gemessen" in report
        assert "uebernommen" in report
        assert "soweit" in report

    def test_the_selection_is_named_so_nobody_reads_the_list_as_complete(self) -> None:
        """Ohne diesen Satz waere eine Liste von acht Zeilen neben "26 Events" stumm daneben - und
        genau die Vollliste ist hier ausgeschlossen."""
        report = render_coherence_report(
            _probe_input(selection_target=None),
            _coherence_counts((3, 3, 60.0, 1, 1), events_total=81),
            _coherence_counts((9, 9, 600.0, 4, 3), events_total=26),
        )

        assert str(COHERENCE_TOP_EVENTS) in report
        assert "nicht vollstaendig" in report
        assert "Events: 81" in report
        assert "Events: 26" in report

    def test_the_distribution_over_all_events_stands_in_the_report(self) -> None:
        report = render_coherence_report(
            _probe_input(selection_target=None),
            _coherence_counts((3, 3, 60.0, 1, 1), (2, 2, 60.0, 1, 0), (1, 1, 0.0, 2, 1)),
            _coherence_counts((3, 3, 60.0, 1, 1)),
        )

        assert "Ortszellen je Event" in report
        assert "1 Zelle(n): 2, 2 Zelle(n): 1" in report
        assert "Motive je Event" in report
        assert "0 Motiv(e): 1, 1 Motiv(e): 2" in report

    def test_no_motif_name_can_reach_the_report(self) -> None:
        """DIE SIEBTE KLASSE, die erst dieser Modus beruehrt. Ein Motivname ist zwar keine der
        sechs aus S2, aber er beschreibt, was auf einem Familienfoto zu sehen ist - und dieser
        Modus ist der erste, der Motive ueberhaupt liest.

        Der Weg dorthin ist durch die Form verschlossen, nicht durch Sorgfalt: `CoherenceRow` traegt
        vier `int`/`float`, und zwischen `carried_motifs` und der Ausgabe steht nur noch `len`.
        Dieser Fall haelt genau das fest."""
        formation = EventFormation(events=(_coherent(1, (1,)),), causes=(frozenset(),))
        candidates = (_with_motifs(1, **{"geheimmotiv": CARRIED}),)

        counts = coherence_counts(formation, candidates)
        report = render_coherence_report(
            _probe_input(selection_target=None), counts, _coherence_counts()
        )

        assert counts.largest[0].motifs == 1
        assert "geheimmotiv" not in report

    def test_a_grouping_without_a_single_event_says_so_instead_of_an_empty_table(self) -> None:
        report = render_coherence_report(
            _probe_input(selection_target=None),
            _coherence_counts(),
            _coherence_counts(),
        )

        assert "Events: 0" in report
        assert "-" in report


# --- Block C: die Ortszuordnung, je Mechanismus getrennt -----------------------------------------
#
# Die Entfernungen der Messlage sind nachgerechnet: 0,002 Grad Breite sind rund 222 m, 0,01 Grad
# rund 1112 m, 0,2 Grad rund 22 239 m. Sie liegen damit klar in ihrer Klasse und nicht auf einer
# Grenze.
def _entry(photo_id: int, minutes: float, gps: tuple[float, float] | None = None) -> LocationEntry:
    return LocationEntry(
        photo_id=photo_id,
        taken_at=NOW + timedelta(minutes=minutes),
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )


class TestBlockC1InheritedLocations:
    """Der uebernommene Ort - er speist Schritt- und Ausdehnungssignal und damit die Grenzen.

    Beide Groessen stehen NUR in Klassen (S5): Sie entstehen aus voller EXIF-Praezision, und eine
    geordnete Folge daraus waere ein Streckenabdruck."""

    def test_the_hand_computed_graph(self) -> None:
        entries = [
            _entry(1, 0, (0.0, 0.0)),
            # Erbt vom frueheren Anker (30 s) - die Ankerspanne ist die Entfernung zwischen den
            # beiden Nachbarn, rund 22 km.
            _entry(2, 0.5),
            _entry(3, 10, (0.2, 0.0)),
            # NACH dem letzten Anker: es gibt nur einen Nachbarn, also KEINE Spanne - und `None`
            # ist ausdruecklich nicht null.
            _entry(4, 20),
        ]
        candidates = [_candidate_of(entry) for entry in entries]

        counts = inheritance_counts(entries, candidates)

        assert counts.candidates_total == 4
        assert counts.candidates_without_own_coordinate == 2
        assert counts.inheriting == 2
        # 30 s in der untersten Klasse, 600 s in "5 bis unter 30 min".
        assert counts.seconds_to_anchor_classes == (1, 0, 1, 0, 0, 0)
        # Die eine gemessene Spanne liegt ueber der Schwelle.
        assert counts.anchor_span_classes == (0, 0, 0, 0, 1)
        assert counts.without_anchor_span == 1

    def test_only_candidates_are_reported_though_the_whole_project_anchors(self) -> None:
        """Die Inferenzbasis ist das ganze Projekt - berichtet werden die KANDIDATEN. Ein nach dem
        Lauf aussortiertes Foto ohne Koordinate gehoert in keine der beiden Verteilungen; die
        Grenzen dieses Laufs haengen nicht an ihm."""
        entries = [
            _entry(1, 0, (0.0, 0.0)),
            _entry(2, 0.5),
            _entry(3, 3),
            _entry(4, 10, (0.2, 0.0)),
        ]
        candidates = [
            _candidate_of(entries[0]),
            _candidate_of(entries[1]),
            _candidate_of(entries[3]),
        ]

        counts = inheritance_counts(entries, candidates)

        assert counts.candidates_total == 3
        assert counts.candidates_without_own_coordinate == 1
        assert counts.inheriting == 1

    def test_without_a_single_anchor_nobody_inherits(self) -> None:
        """Der entartete Fall: Ohne jeden Anker erbt niemand. Die Zahl der Kandidaten ohne eigene
        Koordinate bleibt trotzdem stehen - sie ist etwas anderes als die Zahl der Uebernahmen."""
        entries = [_entry(1, 0), _entry(2, 5)]
        candidates = [_candidate_of(entry) for entry in entries]

        counts = inheritance_counts(entries, candidates)

        assert counts.candidates_without_own_coordinate == 2
        assert counts.inheriting == 0
        assert counts.seconds_to_anchor_classes == (0, 0, 0, 0, 0, 0)


class TestBlockC2MatchDistances:
    """Der aufgeloeste Ortsname: die Entfernung zwischen Aufnahmeposition und dem Eintrag, der den
    Namen geliefert hat. Ausgegeben in Klassen, nie je Zelle (S4)."""

    def test_the_hand_computed_graph(self) -> None:
        counts = match_distance_counts(
            {
                (0.0, 0.0): 120.0,
                (0.1, 0.0): 3000.0,
                (0.2, 0.0): 22239.0,
                # Eine Zelle, die gar keinen Ortsnamen bekaeme - sie traegt keine Entfernung und
                # darf keine Klasse besetzen.
                (0.3, 0.0): None,
            }
        )

        assert counts.cells_total == 4
        assert counts.cells_with_a_name == 3
        assert counts.distance_classes == (1, 0, 1, 0, 1)
        assert counts.cells_beyond_threshold == 1

    def test_the_threshold_is_the_topmost_class_boundary(self) -> None:
        """Der Anteil oberhalb der Schwelle wird aus der obersten Klasse ABGELESEN, nie ein zweites
        Mal gerechnet - ein zweiter Vergleich liefe beim naechsten Grenzfall auseinander."""
        counts = match_distance_counts(
            {(0.0, 0.0): DISTANCE_THRESHOLD_METERS, (0.1, 0.0): DISTANCE_THRESHOLD_METERS - 1}
        )

        assert counts.distance_classes[-1] == 1
        assert counts.cells_beyond_threshold == counts.distance_classes[-1]

    def test_the_threshold_lies_below_what_the_resolver_will_even_return(self) -> None:
        """Eine Ungleichung, kein Zahlwert: Laege die Schwelle ueber
        `GEONAMES_MAX_DISTANCE_METERS`, koennte Block C2 sie strukturell nie ueberschreiten - der
        Auflöser verwirft weiter entfernte Treffer bereits -, und ein Anteil von null waere dann
        eine Eigenschaft der Schwelle statt ein Messergebnis."""
        assert DISTANCE_THRESHOLD_METERS < GEONAMES_MAX_DISTANCE_METERS


class TestBlockC3LandmarkNames:
    """Der Sehenswuerdigkeitsname - der Weg, ueber den eine Ortsaussage am weitesten danebenliegen
    kann: Ein Name benennt das GANZE Event und verdraengt dessen Koordinatenstufe."""

    def test_a_detection_without_any_place_hint(self) -> None:
        """`landmark.py::place_hint_for` liefert fuer ein Foto ohne eigenes GPS `None` - die
        Erkennung entstand dann ohne jeden Ortshinweis. Ein uebernommener Ort erreicht diese
        Funktion nie."""
        with_gps = _named_candidate(1, 0, "Palast", gps=(0.0, 0.0))
        without_gps = _named_candidate(2, 1, "Palast")

        counts = landmark_counts([with_gps, without_gps], explain_events([]), {})

        assert counts.detections_total == 2
        assert counts.detections_without_place_hint == 1

    def test_a_name_whose_carriers_lie_further_apart_than_the_threshold(self) -> None:
        """Ein innerer Widerspruch, fuer den es keine aeussere Wahrheit braucht: Dieselbe
        Sehenswuerdigkeit kann nicht an zwei 22 km auseinanderliegenden Orten stehen."""
        candidates = [
            _named_candidate(1, 0, "Weit", gps=(0.0, 0.0)),
            _named_candidate(2, 1, "Weit", gps=(0.2, 0.0)),
            # Derselbe Ortsbesuch, rund 1,1 km auseinander - kein Widerspruch.
            _named_candidate(3, 2, "Nah", gps=(0.0, 0.0)),
            _named_candidate(4, 3, "Nah", gps=(0.01, 0.0)),
        ]

        counts = landmark_counts(candidates, explain_events([]), {})

        assert counts.names_total == 2
        assert counts.names_spread_beyond_threshold == 1

    def test_an_event_named_by_exactly_one_of_many_photos(self) -> None:
        """Ein einziges erkanntes Foto benennt hier zwoelf - der Name traegt dann eine Aussage
        ueber Fotos, zu denen er nie erhoben wurde."""
        named = _named_candidate(1, 0, "Palast", gps=(0.0, 0.0))
        others = [_candidate(minutes) for minutes in (1, 2)]
        formation = explain_events([named, *others])

        counts = landmark_counts([named, *others], formation, {})

        assert len(formation.events) == 1
        assert counts.events_named_by_a_single_photo == 1

    def test_an_event_whose_photos_all_carry_the_name_is_not_counted(self) -> None:
        candidates = [
            _named_candidate(1, 0, "Palast", gps=(0.0, 0.0)),
            _named_candidate(2, 1, "Palast", gps=(0.0, 0.0)),
        ]
        formation = explain_events(candidates)

        counts = landmark_counts(candidates, formation, {})

        assert len(formation.events) == 1
        assert counts.events_named_by_a_single_photo == 0

    def test_a_single_photo_event_is_not_counted_either(self) -> None:
        """ "Auf genau einem von VIELEN Fotos" - ein Event aus einem einzigen Foto ist kein
        Widerspruch, sondern der Normalfall."""
        named = _named_candidate(1, 0, "Palast", gps=(0.0, 0.0))
        formation = explain_events([named])

        counts = landmark_counts([named], formation, {})

        assert counts.events_named_by_a_single_photo == 0


# --- main() gegen eine echte, dateibasierte SQLite ------------------------------------------------
#
# DIE MESSLAGE TRAEGT JE EINEN UNTERSCHEIDBAREN WERT ALLER SECHS KLASSEN AUS S2, und keiner davon
# darf im Bericht stehen: Koordinate, Ortsname, Sehenswuerdigkeitsname, OpenCloud-Pfad,
# Projektname, Zeitstempel. Die gesuchten Zeichenfolgen stammen aus DIESER Lage, nie aus einem
# allgemeinen Muster.
MEASURED_PROJECT_NAME = "Zahnradbahnhausen"
MEASURED_OPENCLOUD_PATH = "/Fotos/Geheimpfad"
MEASURED_PHOTO_FILE = "geheimbild"
MEASURED_LANDMARK = "Wolkenpalast"
MEASURED_LOCALITY = "Nirgendwo"
MEASURED_TAKEN_AT = datetime(2029, 11, 17, 3, 47, 0)
MEASURED_LAT = 43.5081
MEASURED_LON = 16.4402


def _geonames_line(name: str, lat: float, lon: float, feature_class: str, feature_code: str) -> str:
    return "\t".join(
        ["1", name, name, "", str(lat), str(lon), feature_class, feature_code, "HR", ""]
    )


MEASURED_DATASET_LINES = [
    _geonames_line(MEASURED_LOCALITY, MEASURED_LAT, MEASURED_LON, "P", "PPL"),
]


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    """Der Auszug in genau der Form, die auch im Betrieb liegt - gepackt und mit seinem Hash
    daneben. Ueber `write_extract` statt von Hand geschrieben: das Messkommando liest ab hier
    dieselbe Datei wie ein Lauf."""
    path = tmp_path / "geonames-auszug.txt.gz"
    write_extract(MEASURED_DATASET_LINES, path)
    return path


async def _seed_measured_project(session: AsyncSession) -> int:
    """Baut die Messlage auf. SCHREIBT - aber im TEST, nie im Kommando.

    Vier Kandidaten: drei dicht beieinander (ein Event), einer DREI TAGE spaeter (zweites Event,
    ein einzelnes Foto). Eines traegt einen Sehenswuerdigkeit-Namen, eines gar keine Koordinate.

    Drei Tage, nicht drei Stunden: Die Trennung haengt damit an der gepinnten Ungleichung
    `EVENT_MAX_SPAN < 24 h` und nicht am Zahlwert einer Schwelle, die in Schritt 5 kalibriert
    wird."""
    project = Project(
        name=MEASURED_PROJECT_NAME,
        opencloud_drive_id="drive",
        opencloud_path=MEASURED_OPENCLOUD_PATH,
    )
    session.add(project)
    await session.flush()

    photos = []
    for index, minutes in enumerate((0, 2, 4, 3 * 24 * 60)):
        photos.append(
            Photo(
                project_id=project.id,
                relative_path=f"{MEASURED_PHOTO_FILE}{index:03d}.jpg",
                etag=f"etag-{index}",
                content_length=1000,
                taken_at=MEASURED_TAKEN_AT + timedelta(minutes=minutes),
                taken_at_original=MEASURED_TAKEN_AT + timedelta(minutes=minutes),
                last_modified=MEASURED_TAKEN_AT,
                # Das dritte Foto traegt KEINE Koordinate - es erbt und traegt damit Block C1.
                gps_lat=None if index == 2 else MEASURED_LAT,
                gps_lon=None if index == 2 else MEASURED_LON,
            )
        )
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add_all([*photos, scoring_run])
    await session.flush()

    session.add(
        PhotoLandmarkDetection(
            photo_id=photos[0].id,
            name=MEASURED_LANDMARK,
            confidence=0.9,
            computed_at=MEASURED_TAKEN_AT,
        )
    )
    criterion_run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(criterion_run)
    await session.flush()

    event = Event(
        criterion_scoring_run_id=criterion_run.id,
        position=1,
        started_at=MEASURED_TAKEN_AT,
        ended_at=MEASURED_TAKEN_AT,
        place_kind=None,
    )
    session.add(event)
    await session.flush()
    session.add_all(
        [
            PhotoRanking(
                criterion_scoring_run_id=criterion_run.id,
                photo_id=photo.id,
                event_id=event.id,
                rank_score=0.5,
                rank_position=position,
            )
            for position, photo in enumerate(photos, start=1)
        ]
    )
    await session.flush()
    return project.id


def _prepared(tmp_path: Path) -> tuple[str, int]:
    """Eine dateibasierte SQLite mit der Messlage darin - der Aufrufer bekommt URL und Projekt-Id."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

    async def prepare() -> int:
        engine = make_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = make_session_factory(engine)
        async with factory() as session:
            project_id = await _seed_measured_project(session)
            await session.commit()
        await engine.dispose()
        return project_id

    return url, asyncio.run(prepare())


class TestMainRefusesLoudly:
    """Nicht Traceback und nicht stille Null."""

    def test_an_unknown_project_id(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> None:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await engine.dispose()

        asyncio.run(prepare())

        exit_code = main(["--project-id", "999"], database_url=url)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "999" in captured.err
        assert captured.out == ""

    def test_a_project_without_a_successful_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project = Project(name="Ohne Lauf", opencloud_drive_id="d", opencloud_path="/p")
                session.add(project)
                await session.flush()
                project_id = project.id
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        exit_code = main(["--project-id", str(project_id)], database_url=url)

        assert exit_code == 1
        assert "Lauf" in capsys.readouterr().err

    def test_a_database_error_names_only_the_error_type(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """S8: NIE `str(exc)` und nie ein Traceback - die SQLAlchemy-Meldung kann die
        `DATABASE_URL` samt Zugangsdaten tragen. Die Lage ist eine Datenbank ohne Tabellen."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'ohne-tabellen.db'}"

        exit_code = main(["--project-id", "1"], database_url=url)

        assert exit_code == 1
        error = capsys.readouterr().err
        assert "OperationalError" in error
        assert url not in error

    def test_the_motif_mode_refuses_a_project_without_a_successful_run_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Dieselbe Vorbedingung, gleich welche Argumentform: Ohne Gliederung gibt es auch keine
        Empfindlichkeit zu messen - und das wird gesagt, nicht als leere Tabelle gezeigt."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _project(session, "Ohne Lauf")
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        exit_code = main(["--project-id", str(project_id), "--motiv"], database_url=url)

        assert exit_code == 1
        assert "Lauf" in capsys.readouterr().err

    def test_a_run_without_a_single_ranking_row_reports_dashes_not_zeroes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Der entartete Fall: ein erfolgreicher Lauf, dessen Rangzeilen fehlen. Es gibt dann
        keinen Median und keine Dauer - und "-" ist etwas anderes als null."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _project(session, "Leerer Lauf")
                await _successful_run(session, project_id, [])
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        exit_code = main(["--project-id", str(project_id)], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "Events: 0" in report
        assert "Median der Fotozahl: -" in report
        assert "laengste Eventdauer: -" in report

    def test_the_bolt_mode_refuses_a_project_without_a_successful_run_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JE ARGUMENTFORM: Ohne Gliederung gibt es auch keine Blockade zu messen."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _project(session, "Ohne Lauf")
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        exit_code = main(["--project-id", str(project_id), "--riegel"], database_url=url)

        assert exit_code == 1
        assert "Lauf" in capsys.readouterr().err

    def test_the_coherence_mode_refuses_a_project_without_a_successful_run_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JE ARGUMENTFORM: Ohne Gliederung gibt es auch keine Kohaerenz zu messen."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _project(session, "Ohne Lauf")
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        exit_code = main(["--project-id", str(project_id), "--kohaerenz"], database_url=url)

        assert exit_code == 1
        assert "Lauf" in capsys.readouterr().err

    def test_the_report_carries_the_counter_indication_of_the_third_stage(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ohne diese zwei Zeilen im BERICHT haette die Nachmessung die Zahlen zwar gerechnet, aber
        Daniel bekaeme sie nie zu sehen - und beurteilte die Aenderung allein an Zahlen, die eine
        Ueberverschmelzung verbessert."""
        url, project_id = _prepared(tmp_path)

        assert main(["--project-id", str(project_id)], database_url=url) == 0

        report = capsys.readouterr().out
        assert "Grenzen vor dem Zusammenlegen:" in report
        assert "durch Stufe 3 aufgeloest:" in report
        assert "Fotos, die dadurch ihr Event gewechselt haben:" in report


def _add_one_unranked_photo(url: str, project_id: int) -> None:
    """Ein Foto ohne Rangzeile - es zaehlt zum Bestand des Projekts, wird aber nie Kandidat.
    SCHREIBT, aber im TEST, nie im Kommando."""

    async def add() -> None:
        engine = make_engine(url)
        factory = make_session_factory(engine)
        async with factory() as session:
            await _photo(session, project_id, minutes=4711)
            await session.commit()
        await engine.dispose()

    asyncio.run(add())


class TestTheReportNamesWhetherTheQuotaCanWeigh:
    """Ohne diese Zeilen im BERICHT bliebe das eigentliche Mass ungemessen: Der Anteil der
    Ein-Bild-Cluster sagt nichts darueber, ob die Kontingentvergabe ueberhaupt gewichten kann."""

    def test_the_report_carries_the_target_and_the_verdict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Die Messlage traegt vier Fotos; der Richtwert kommt aus `effective_target` und wird
        deshalb auch hier von dort geholt statt als Zahl hingeschrieben. Der Wortlaut des Urteils
        steht in den reinen Faellen - hier geht es darum, dass der Block den Bericht ueberhaupt
        erreicht."""
        url, project_id = _prepared(tmp_path)

        assert main(["--project-id", str(project_id)], database_url=url) == 0

        report = capsys.readouterr().out
        assert f"Album-Richtwert: {effective_target(None, 4)}" in report
        assert "freie Plaetze" in report
        assert "Die Kontingentvergabe kann" in report

    def test_the_target_rests_on_the_photos_of_the_project_not_on_the_candidates(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Die Auswertungsgrenze am echten Lesepfad: Ein nach dem Lauf hinzugekommenes Foto zaehlt
        fuer den Richtwert mit - er rechnet auf dem Bestand, nicht auf der Kandidatenmenge - und
        der Bericht sagt, dass die beiden Mengen auseinanderfallen."""
        url, project_id = _prepared(tmp_path)
        _add_one_unranked_photo(url, project_id)

        assert main(["--project-id", str(project_id)], database_url=url) == 0

        report = capsys.readouterr().out
        assert f"Album-Richtwert: {effective_target(None, 5)}" in report
        assert "Auswertungsgrenze" in report


class TestTheOutputSeparatesNumbersFromPlaces:
    """S2 ueber ALLE SECHS KLASSEN. Die Messlage traegt je einen unterscheidbaren Wert, und keiner
    steht im Bericht - das ist die Bedingung dafuer, dass die Zahlen als Ganzes in ein
    oeffentliches Repository duerfen."""

    def test_the_motif_report_carries_none_of_the_six_classes_either(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JE ARGUMENTFORM: Der Bericht des Motiv-Modus entsteht an einer anderen Stelle und ist
        von der Zusage des Hauptberichts nicht mitgedeckt."""
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id), "--motiv"], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "43.5" not in report
        assert "16.44" not in report
        assert MEASURED_LOCALITY not in report
        assert MEASURED_LANDMARK not in report
        assert MEASURED_OPENCLOUD_PATH not in report
        assert MEASURED_PHOTO_FILE not in report
        assert MEASURED_PROJECT_NAME not in report
        assert "2029" not in report
        assert "03:47" not in report
        assert f"Projekt {project_id}" in report

    def test_the_bolt_report_carries_none_of_the_six_classes_either(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JE ARGUMENTFORM: Der Bericht von Block F entsteht an einer anderen Stelle und ist von
        der Zusage der beiden anderen nicht mitgedeckt. Die Gruende selbst sind interne Kennungen
        aus geschlossenem Vorrat, keine Ortsangaben - der S2-Fall laeuft trotzdem ueber ihn."""
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id), "--riegel"], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "43.5" not in report
        assert "16.44" not in report
        assert MEASURED_LOCALITY not in report
        assert MEASURED_LANDMARK not in report
        assert MEASURED_OPENCLOUD_PATH not in report
        assert MEASURED_PHOTO_FILE not in report
        assert MEASURED_PROJECT_NAME not in report
        assert "2029" not in report
        assert "03:47" not in report
        assert f"Projekt {project_id}" in report

    def test_the_bolt_report_carries_a_row_per_reason_of_the_closed_supply(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Jeder Grund steht da, auch der nie aufgetretene - sonst waere der Bericht still
        unvollstaendig, ohne dass eine Summe kleiner wuerde."""
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id), "--riegel"], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        for reason in MERGE_BLOCK_REASONS:
            assert f"| {reason} |" in report
        # Kopfzeile plus je eine Zeile je Grund (die Trennzeile beginnt mit `|---`).
        rows = [line for line in report.splitlines() if line.startswith("| ")]
        assert len(rows) == 1 + len(MERGE_BLOCK_REASONS)

    def test_the_bolt_report_names_the_measured_blockade(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Die Messlage traegt ein Einzelfoto DREI TAGE hinter den uebrigen: Seine eine Kante reisst
        die Ueberbrueckung UND die Dauergrenze zugleich.

        Damit haengt am Bericht zweierlei. Erstens stehen die Zahlen ueberhaupt darin - sonst
        haette der Lauf sie zwar gerechnet, aber Daniel bekaeme sie nie zu sehen. Zweitens steht
        `dauer` daneben: Kurzgeschlossen gaebe es nur `zeitluecke` zu sehen, und wer sie lockerte,
        staende danach vor der Dauergrenze. Und keiner der beiden traegt die zweite Spalte, weil
        keiner fuer sich sperrt."""
        url, project_id = _prepared(tmp_path)

        assert main(["--project-id", str(project_id), "--riegel"], database_url=url) == 0

        report = capsys.readouterr().out
        assert "zu kleine Segmente, die bestehen blieben: 1" in report
        assert "| zeitluecke | 1 (100.0 %) | 0 (0.0 %) |" in report
        assert "| dauer | 1 (100.0 %) | 0 (0.0 %) |" in report
        assert "| kein_nachbar | 0 (0.0 %) | 0 (0.0 %) |" in report

    def test_the_bolt_mode_measures_nothing_of_the_place_blocks(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Der Modus braucht den Ortsauszug gar nicht - er darf deshalb weder danach fragen noch
        sein Fehlen als Messergebnis melden."""
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id), "--riegel"], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "NICHT GEMESSEN" not in report
        assert "C1" not in report
        assert "C2" not in report

    def test_the_measuring_modes_exclude_each_other(self, tmp_path: Path) -> None:
        """Zwei Modi gleichzeitig ist keine Frage, die eine Antwort hat. Eine stille Vorrangregel
        gaebe einen Bericht aus, den niemand angefordert hat. Jede Paarung einzeln: Ein neuer Modus,
        der nur an EINEN der bestehenden gehaengt wird, liefe neben dem anderen still mit."""
        url, project_id = _prepared(tmp_path)

        for pair in (
            ("--motiv", "--riegel"),
            ("--motiv", "--kohaerenz"),
            ("--riegel", "--kohaerenz"),
        ):
            with pytest.raises(SystemExit):
                main(["--project-id", str(project_id), *pair], database_url=url)

    def test_the_coherence_report_carries_none_of_the_six_classes_either(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JE ARGUMENTFORM: Der Kohaerenz-Bericht entsteht an einer anderen Stelle und ist von der
        Zusage der uebrigen nicht mitgedeckt. Er ist zugleich der Modus, der einer Liste je Event am
        naechsten kommt - S2 ist hier strenger zu lesen, nicht lockerer."""
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id), "--kohaerenz"], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "43.5" not in report
        assert "16.44" not in report
        assert MEASURED_LOCALITY not in report
        assert MEASURED_LANDMARK not in report
        assert MEASURED_OPENCLOUD_PATH not in report
        assert MEASURED_PHOTO_FILE not in report
        assert MEASURED_PROJECT_NAME not in report
        assert "2029" not in report
        assert "03:47" not in report
        assert f"Projekt {project_id}" in report

    def test_the_coherence_report_carries_both_groupings_of_the_real_lay(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Die Messlage traegt vier Kandidaten in zwei Events (drei dicht beieinander, einer drei
        Tage spaeter) und kein einziges Motiv - ohne Motivgrenze bleibt es bei denselben zwei."""
        url, project_id = _prepared(tmp_path)

        assert main(["--project-id", str(project_id), "--kohaerenz"], database_url=url) == 0

        report = capsys.readouterr().out
        assert "## Betriebswert" in report
        assert "## Motivwechsel aus" in report
        assert report.count("- Events: 2") == 2
        # Drei Fotos an EINER Zelle, davon zwei gemessen - das dritte hat seinen Ort uebernommen
        # und speist keine Zelle. Genau diese Luecke macht die fuenfte Spalte sichtbar.
        assert "| 3 | 2 | 4 min | 1 | 0 |" in report
        assert "| 1 | 1 | 0 s | 1 | 0 |" in report

    def test_the_coherence_mode_measures_nothing_of_the_place_blocks(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Der Modus braucht den Ortsauszug gar nicht - er darf deshalb weder danach fragen noch
        sein Fehlen als Messergebnis melden."""
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id), "--kohaerenz"], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "NICHT GEMESSEN" not in report
        assert "C1" not in report
        assert "C2" not in report

    def test_the_two_groupings_come_from_the_same_means_as_the_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Die Gliederung "aus" entsteht ueber `motif_change_off_window`, nicht ueber einen
        Abschaltpfad - und beide ueber `explain_events`. Der Bericht sagt das, weil sonst offen
        bliebe, wie die zweite Spalte zustande kommt."""
        url, project_id = _prepared(tmp_path)

        assert main(["--project-id", str(project_id), "--kohaerenz"], database_url=url) == 0

        report = capsys.readouterr().out
        assert "Bestaetigungsfenster groesser als die Zahl der Kandidatenfotos" in report
        assert "keinen Abschalter" in report

    def test_the_motif_report_carries_a_row_per_combination_plus_both_reference_rows(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id), "--motiv"], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "Betriebswert" in report
        rows = [line for line in report.splitlines() if line.startswith("| ")]
        # Kopfzeile, die Zeile des Betriebswerts, die Zeile "aus" und je eine Zeile je Kombination
        # (die Trennzeile der Tabelle beginnt mit `|---` und zaehlt hier nicht mit).
        assert len(rows) == 3 + len(MOTIF_CONFIRMING_VARIANTS) * len(MOTIF_STRENGTH_VARIANTS)

    def test_the_switched_off_row_is_labelled_not_numbered(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """ "Aus" ist eine Aussage, keine Fensterlaenge: Die gerechnete Zahl (Kandidatenzahl plus
        eins) im Bericht laese sich als messbarer Betriebspunkt missverstehen."""
        url, project_id = _prepared(tmp_path)

        assert main(["--project-id", str(project_id), "--motiv"], database_url=url) == 0

        report = capsys.readouterr().out
        [switched_off] = [line for line in report.splitlines() if line.startswith("| aus |")]
        # Die Messlage traegt vier Kandidaten; das Fenster waere also 5.
        assert "| 5 |" not in switched_off
        assert "Bestaetigungsfenster groesser als die Zahl der Kandidatenfotos" in report

    def test_the_motif_mode_measures_nothing_of_the_place_blocks(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Der Modus braucht den Ortsauszug gar nicht - er darf deshalb weder danach fragen noch
        sein Fehlen als Messergebnis melden."""
        url, project_id = _prepared(tmp_path)

        exit_code = main(["--project-id", str(project_id), "--motiv"], database_url=url)

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "NICHT GEMESSEN" not in report
        assert "C1" not in report
        assert "C2" not in report

    def test_none_of_the_six_classes_reaches_the_report(
        self, tmp_path: Path, dataset: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url, project_id = _prepared(tmp_path)

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)], database_url=url
        )

        assert exit_code == 0
        report = capsys.readouterr().out
        # 1. Koordinate, 2. Ortsname, 3. Sehenswuerdigkeitsname, 4. OpenCloud-Pfad,
        # 5. Projektname, 6. Zeitstempel.
        assert "43.5" not in report
        assert "16.44" not in report
        assert MEASURED_LOCALITY not in report
        assert MEASURED_LANDMARK not in report
        assert MEASURED_OPENCLOUD_PATH not in report
        assert MEASURED_PHOTO_FILE not in report
        assert MEASURED_PROJECT_NAME not in report
        assert "2029" not in report
        assert "03:47" not in report
        # ... aber die Zahlen stehen da, samt der Projekt-Id.
        assert f"Projekt {project_id}" in report
        assert "Events: 2" in report

    def test_there_is_no_switch_that_would_add_the_names(self, tmp_path: Path) -> None:
        """S3: kein `--namen`-Aequivalent. Messgegenstand ist hier die ZAHL der Widersprueche;
        Pseudonymisierung waere kein Ausweg, weil die Menge der Sehenswuerdigkeitsnamen klein und
        oeffentlich ist."""
        url, project_id = _prepared(tmp_path)

        with pytest.raises(SystemExit):
            main(["--project-id", str(project_id), "--namen"], database_url=url)


class TestAnAbsentDatasetIsReportedNotShownAsZero:
    """S7 - die Ausfallrichtung von Block C2. Ein fehlendes Aggregat, das als gutes Messergebnis
    gelesen wird, truege hier die Entscheidung, an der Ortsbestimmung nichts zu aendern."""

    def test_a_missing_dataset_is_named_not_measured(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url, project_id = _prepared(tmp_path)

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(tmp_path / "fehlt.gz")],
            database_url=url,
        )

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "NICHT GEMESSEN" in report
        assert "sie sind nicht null" in report
        assert "python -m photosort.place_dataset" in report
        # Die uebrigen Bloecke stehen weiter da - nur C2 haengt am Ortsdatensatz.
        assert "Events: 2" in report

    def test_a_cell_without_any_resolvable_name_carries_no_distance(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """ "Diese Zelle bekaeme keinen Ortsnamen" ist etwas anderes als "die Entfernung ist null":
        Eine solche Zelle besetzt KEINE Entfernungsklasse. Die unterste zu besetzen behauptete
        einen perfekt getroffenen Namen, den es nicht gibt.

        Der Auszug dieser Lage traegt nur einen weit entfernten Eintrag - der Auflöser entsteht
        also, findet aber nichts."""
        url, project_id = _prepared(tmp_path)
        far_away = tmp_path / "nur-fern.txt.gz"
        write_extract([_geonames_line("Anderswo", 0.0, 0.0, "P", "PPL")], far_away)

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(far_away)], database_url=url
        )

        assert exit_code == 0
        report = capsys.readouterr().out
        assert "NICHT GEMESSEN" not in report
        assert "gefragte Zellen: 1" in report
        assert "davon mit Ortsnamen: 0" in report
        # Keine Klasse besetzt - und der Anteil ueber der Schwelle ist nicht messbar, nicht null.
        assert "ueber der Entfernungsschwelle: 0 (-)" in report

    def test_a_changed_dataset_is_not_measured_either(
        self, tmp_path: Path, dataset: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Kein stiller Ersatzweg: Ein Auszug, der von seinem Hash abweicht, wird nicht gelesen."""
        url, project_id = _prepared(tmp_path)
        dataset_hash_path(dataset).write_text("0" * 64 + "\n", encoding="utf-8")

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)], database_url=url
        )

        assert exit_code == 0
        assert "NICHT GEMESSEN" in capsys.readouterr().out


# --- Die Zusage "rein lesend", in drei Teilen ------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestTheWriteGuardIsNotVacuous:
    """Zwei Referenzfaelle gegen Vakuum-Gruen: Ein Waechter, der nichts erkennt, ist immer gruen.
    Die Mikrotests je Schreibform und die Positiv-Gegenproben stehen bei ihm selbst
    (`test_place_probe.py::TestTheWriteGuardItself`) - er hat nur EINE Definition."""

    def test_a_writing_form_is_still_recognised(self) -> None:
        assert "add()" in write_statements(ast.parse("session.add(row)"))

    def test_a_reading_form_is_still_not_flagged(self) -> None:
        assert (
            write_statements(ast.parse("rows = (await session.execute(select(Photo))).all()")) == []
        )


class TestTheProbeIsReadOnly:
    """Die Zusage "kein Lauf hinterlaesst eine geaenderte, geloeschte oder neue Zeile", in drei
    Teilen - KEIN Teil traegt allein."""

    def test_the_command_is_in_no_import_graph_of_the_application(self) -> None:
        assert "photosort.event_probe" not in import_closure("photosort.main")
        assert "photosort.event_probe" not in import_closure("photosort.worker")

    def test_the_import_graph_walker_actually_finds_something(self) -> None:
        # Gegenprobe: ohne sie bestuenden die beiden Zusagen oben auch bei einem Walker, der gar
        # nichts findet - Tippfehler im Modulnamen, geaenderte Verzeichnisstruktur.
        assert {"photosort.models", "photosort.config"} <= import_closure("photosort.main")
        assert "photosort.events" in import_closure("photosort.event_probe")

    def test_the_inputs_module_lies_in_the_graph_of_the_run(self) -> None:
        """DIE GEGENPROBE ZUR IMPORT-GRAPH-ZUSAGE: `event_inputs.py` MUSS im Graphen von
        `worker.py` liegen - sonst waere aus dem gemeinsamen Modul still wieder eine Kopie
        geworden, und das Messkommando maesse etwas anderes als der Lauf (ADR 0117 Punkt 5)."""
        assert "photosort.event_inputs" in import_closure("photosort.worker")
        assert "photosort.event_inputs" in import_closure("photosort.event_probe")

    def test_no_compose_file_runs_either_module(self) -> None:
        """Der Abfluss tritt nur ein, wenn Daniel ihn TIPPT - nicht, weil ein Container startet.
        Ueber BEIDE Modulnamen: nur mit dem alten Namen kopiert waere dieser Waechter still
        vakuum-gruen."""
        for compose in sorted(REPO_ROOT.glob("docker-compose*.yml")):
            content = compose.read_text(encoding="utf-8")

            assert "event_probe" not in content, compose.name
            assert "event_inputs" not in content, compose.name

    @pytest.mark.parametrize("module", ["photosort.event_probe", "photosort.event_inputs"])
    def test_the_module_defines_no_endpoint(self, module: str) -> None:
        path = module_file(module)
        assert path is not None
        source = path.read_text(encoding="utf-8")

        assert "APIRouter" not in source
        assert "fastapi" not in source

    @pytest.mark.parametrize("module", ["photosort.event_probe", "photosort.event_inputs"])
    def test_the_module_contains_no_writing_statement_at_all(self, module: str) -> None:
        """JE MODUL, nicht ueber den Import-Graphen: Ueber die Import-Huelle angewandt schluege der
        Waechter auf `events.py`, `selection.py` und `geonames.py` an (gleichnamige
        Sammlungs-Methoden, falsch positiv) und wuerde dann entschaerft."""
        path = module_file(module)
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))

        assert write_statements(tree) == []


def _adjustable_constants_of_events() -> frozenset[str]:
    """Die Stellschrauben von `events.py` - AUS DEM MODUL GELESEN, nie von Hand gefuehrt.

    Zwei Achsen, beide gemessen: der NAME muss in `events.py` auf Modulebene zugewiesen sein (die
    Syntaxbaum-Seite - ein von anderswo importierter Name wie `MAX_PLACE_NAME_LENGTH` ist keine
    Stellschraube dieses Moduls), und der WERT muss eine Zahl oder ein `timedelta` sein (die
    Laufzeit-Seite). Die geschlossenen Wortschaetze (`BOUNDARY_*`, `BOUNDARY_CAUSES`,
    `MERGE_BLOCK_REASONS`, `PLACE_KINDS`, `UNBREAKABLE_CAUSES`) fallen dadurch heraus und duerfen
    weiter importiert werden - sie aendern sich nicht unter der Hand, und ein Test verschiebt sie
    nicht.

    Ein handgefuehrter Namensvorrat waere beim naechsten Zuwachs still vakuum-gruen: Genau die neue
    Stellschraube waere die ungeprueфte."""
    path = module_file("photosort.events")
    assert path is not None
    assigned = {
        target.id
        # NUR `.body`, also Modulebene: eine Zuweisung in einer Funktion ist keine Modulkonstante.
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, ast.Assign | ast.AnnAssign)
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and target.id.isupper()
    }
    return frozenset(
        name
        for name in assigned
        if isinstance(getattr(events_module, name), int | float | timedelta)
    )


def _names_bound_from_events(source: str) -> frozenset[str]:
    """Die Namen, die `source` per `from photosort.events import ...` BEIM IMPORT BINDET.

    `import photosort.events as ...` bindet nichts davon - der Zugriff laeuft dann bei jeder
    Nutzung ueber das Modul und folgt einer Verschiebung."""
    return frozenset(
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module == "photosort.events"
        for alias in node.names
    )


class TestNoAdjustableConstantIsBoundAtImport:
    """Die Fehlerklasse hinter einem Befund, der fuenf PRs und zwei veroeffentlichte Messungen lang
    still eine falsche Spalte gezaehlt hat: `event_probe.py` band `MIN_EVENT_PHOTOS` per
    `from photosort.events import ...` und las damit den Wert vom Importzeitpunkt.

    Ein Kommentar ist dagegen kein Waechter, und ein einzelner Verhaltensfall deckt nur die eine
    Konstante ab, die er benutzt. Dieser Fall deckt ALLE - auch die, die es noch nicht gibt."""

    def test_the_adjustable_constants_are_actually_found(self) -> None:
        """Gegenprobe gegen einen Detektor, der nichts findet: Ein leerer Vorrat machte jede
        Zusage unten vakuum-gruen. Geprueft wird eine TEILMENGE, kein Gleichstand - eine neue
        Stellschraube soll den Waechter erweitern, nicht diesen Fall rot machen."""
        found = _adjustable_constants_of_events()

        assert {
            "EVENT_TIME_GAP",
            "EVENT_STEP_MAX_METERS",
            "EVENT_EXTENT_MAX_METERS",
            "EVENT_MAX_SPAN",
            "MERGE_MAX_GAP",
            "MERGE_EXTENT_MAX_METERS",
            "MIN_EVENT_PHOTOS",
            "MOTIF_CHANGE_CONFIRMING_PHOTOS",
        } <= found

    def test_the_closed_vocabularies_are_not_mistaken_for_adjustable(self) -> None:
        """Die Gegenrichtung: Waeren sie mit drin, muesste der Waechter entschaerft werden - und
        entschaerft faengt er die Stellschrauben auch nicht mehr."""
        found = _adjustable_constants_of_events()

        assert found.isdisjoint(
            {
                "PLACE_KINDS",
                "BOUNDARY_CAUSES",
                "BOUNDARY_TIME_GAP",
                "MERGE_BLOCK_REASONS",
                "MERGE_BLOCK_UNBREAKABLE",
                "UNBREAKABLE_CAUSES",
                # Von `places.py` importiert, nicht hier zugewiesen: keine Stellschraube DIESES
                # Moduls, und die Namensseite des Kriteriums haelt sie heraus.
                "MAX_PLACE_NAME_LENGTH",
            }
        )

    def test_the_guard_recognises_a_bound_constant(self) -> None:
        """Gegenprobe gegen einen Waechter, der die Importliste gar nicht liest."""
        bound = _names_bound_from_events(
            "from photosort.events import EventCandidate, MIN_EVENT_PHOTOS\n"
        )

        assert bound & _adjustable_constants_of_events() == {"MIN_EVENT_PHOTOS"}

    def test_the_module_alias_form_binds_nothing(self) -> None:
        """Die zulaessige Form muss zulaessig BLEIBEN, sonst ist der Waechter unerfuellbar."""
        bound = _names_bound_from_events("from photosort import events as events_module\n")

        assert bound == frozenset()

    @pytest.mark.parametrize("module", ["photosort.event_probe", "photosort.event_inputs"])
    def test_the_module_binds_no_adjustable_constant(self, module: str) -> None:
        """JE MODUL, wie der Formwaechter: Eine Stellschraube gehoert bei jeder Nutzung frisch als
        Modulattribut gelesen. Gebunden zaehlte der Bericht still gegen einen Wert, nach dem gar
        nicht gegliedert wurde, und jede Fixture, die sie verschiebt, liefe ins Leere."""
        path = module_file(module)
        assert path is not None

        bound = _names_bound_from_events(path.read_text(encoding="utf-8"))

        assert bound & _adjustable_constants_of_events() == frozenset()


async def _table_snapshot(session: AsyncSession) -> dict[str, list[tuple[object, ...]]]:
    """JEDE Tabelle aus `Base.metadata.sorted_tables` - GEMESSEN, nie als handgeschriebene Liste.

    Eine von Hand gepflegte Tabellenliste veraltet still, sobald eine Tabelle hinzukommt; genau
    die neue waere dann die ungepruefte."""
    return {
        table.name: [tuple(row) for row in (await session.execute(select(table))).all()]
        for table in Base.metadata.sorted_tables
    }


class TestARealRunChangesNothing:
    """Teil 3 der Zusage: ein ECHTER `main()`-Lauf gegen eine dateibasierte SQLite, mit
    Schnappschuss jeder Tabelle davor und danach.

    Der Formwaechter allein bestuende gegen ein Modul, das ueber eine Hilfsfunktion schreibt;
    dieser Vergleich allein bestuende gegen einen Schreibpfad, den die Testlage nicht betritt."""

    def test_not_a_single_row_changes(self, tmp_path: Path, dataset: Path) -> None:
        url, project_id = _prepared(tmp_path)

        async def snapshot() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            factory = make_session_factory(engine)
            async with factory() as session:
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        before = asyncio.run(snapshot())

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)], database_url=url
        )

        assert exit_code == 0
        assert asyncio.run(snapshot()) == before

    def test_not_a_single_row_changes_in_the_motif_mode_either(self, tmp_path: Path) -> None:
        """JE ARGUMENTFORM einmal: Der Motiv-Modus nimmt einen anderen Weg durch das Modul, und
        die Zusage des anderen Wegs deckt ihn nicht mit."""
        url, project_id = _prepared(tmp_path)

        async def snapshot() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            factory = make_session_factory(engine)
            async with factory() as session:
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        before = asyncio.run(snapshot())

        exit_code = main(["--project-id", str(project_id), "--motiv"], database_url=url)

        assert exit_code == 0
        assert asyncio.run(snapshot()) == before

    def test_not_a_single_row_changes_in_the_bolt_mode_either(self, tmp_path: Path) -> None:
        """JE ARGUMENTFORM einmal: Block F beobachtet eine Stufe, die im Lauf schreibt - hier
        nicht, und das steht nicht von selbst fest."""
        url, project_id = _prepared(tmp_path)

        async def snapshot() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            factory = make_session_factory(engine)
            async with factory() as session:
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        before = asyncio.run(snapshot())

        exit_code = main(["--project-id", str(project_id), "--riegel"], database_url=url)

        assert exit_code == 0
        assert asyncio.run(snapshot()) == before

    def test_not_a_single_row_changes_in_the_coherence_mode_either(self, tmp_path: Path) -> None:
        """JE ARGUMENTFORM einmal: Der Kohaerenz-Modus rechnet ZWEI Gliederungen statt einer und
        nimmt damit einen eigenen Weg durch das Modul, den die Zusage der uebrigen nicht mitdeckt."""
        url, project_id = _prepared(tmp_path)

        async def snapshot() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            factory = make_session_factory(engine)
            async with factory() as session:
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        before = asyncio.run(snapshot())

        exit_code = main(["--project-id", str(project_id), "--kohaerenz"], database_url=url)

        assert exit_code == 0
        assert asyncio.run(snapshot()) == before

    def test_the_snapshot_actually_covers_something(self, tmp_path: Path) -> None:
        """Gegenprobe: ohne sie bestuende der Vergleich oben auch gegen einen leeren
        Schnappschuss - etwa nach einem Umbau von `Base.metadata`."""
        url, _ = _prepared(tmp_path)

        async def snapshot() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            factory = make_session_factory(engine)
            async with factory() as session:
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        taken = asyncio.run(snapshot())

        assert {"projects", "photos", "events", "photo_rankings"} <= set(taken)
        assert len(taken["photos"]) == 4
        assert len(taken["photo_rankings"]) == 4


def _by_photo_id(candidates: Collection[EventCandidate]) -> list[EventCandidate]:
    """Dieselbe Menge in derselben Ordnung - verglichen wird danach FELD FUER FELD (`EventCandidate`
    ist ein frozen dataclass)."""
    return sorted(candidates, key=lambda candidate: candidate.photo_id)


@pytest.mark.asyncio
class TestBothPathsSeeTheSameCandidates:
    """ADR 0117 Punkt 5 - ein eigener Fall, den "rein lesend" NICHT mitdeckt: Der Lauf und das
    Messkommando beziehen die Kandidatenmenge aus derselben Stelle. Eine nachbildende zweite
    Fassung maesse etwas anderes, als der Lauf tut, waehrend beide fuer sich gruen blieben."""

    async def test_the_worker_path_and_the_probe_path_agree_field_by_field(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_id = await _seed_measured_project(db_session)
        captured: list[tuple[EventCandidate, ...]] = []
        through_the_run = worker.read_event_inputs

        async def recording(
            session: AsyncSession, seen_project_id: int, photo_ids: Collection[int]
        ) -> EventInputs:
            inputs = await through_the_run(session, seen_project_id, photo_ids)
            captured.append(inputs.candidates)
            return inputs

        monkeypatch.setattr(worker, "read_event_inputs", recording)

        # Der Neuaufbau ist der Lauf-Pfad: er ermittelt die Kandidatenmenge selbst und ruft
        # `_build_grouping_and_rankings` - genau wie der Kriterien-Lauf.
        await worker.rebuild_run_grouping(db_session, project_id)
        probe = await read_event_probe_input(db_session, project_id)

        [from_the_run] = captured
        assert _by_photo_id(from_the_run) == _by_photo_id(probe.candidates)
        assert len(from_the_run) == 4
