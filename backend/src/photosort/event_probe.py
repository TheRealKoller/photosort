"""REIN LESENDES Messkommando: misst an einem echten Projekt, wie die Event-Bildung heute gliedert.

Aufruf::

    docker compose exec -T backend python -m photosort.event_probe --project-id 3

Gemessen wird mit den Mitteln des Laufs: dieselbe Kandidatenmenge (``event_inputs.py``), derselbe
Durchlauf (``events.py::explain_events``), derselbe Auflöser. Eine zweite, nachbildende Fassung
maesse etwas anderes, als der Lauf tatsaechlich tut, waehrend beide fuer sich gruen blieben.

REIN LESEND, und das ist eine gepruefte Zusage, keine Absicht: kein ``INSERT``/``UPDATE``/
``DELETE``, kein Aufrufpfad aus ``main.py``/``worker.py``, kein Endpunkt, kein
Compose-``command``. Kein Lauf hinterlaesst eine geaenderte, geloeschte oder neue Zeile.
``tests/test_event_probe.py`` haelt das dreifach fest - Import-Graph, Syntaxbaum-Waechter gegen
jede Schreibform und ein echter ``main()``-Lauf mit Schnappschuss jeder Tabelle davor und danach.
Kein Teil traegt allein. Der Formwaechter laeuft JE MODUL und deckt ``event_inputs.py`` mit; der
Preis ist, dass beide Dateien auf ``set.add``/``dict.update`` als Sammlungs-Methoden verzichten.

SICHERHEIT:

* DIE AUSGABE TRAEGT KEINE KOORDINATE, KEINEN ORTS- ODER SEHENSWUERDIGKEIT-NAMEN, KEINEN
  OPENCLOUD-PFAD, KEINEN PROJEKTNAMEN UND KEINEN ZEITSTEMPEL (S2). Ein Projektname ist eine
  Ortsangabe, ein ``taken_at`` ist der Zeitpunkt; ausgewiesen wird die Projekt-**Id**. Das ist die
  Bedingung dafuer, dass die Zahlen als Ganzes in ein oeffentliches Repository duerfen.
* KEIN NAMENS-SCHALTER (S3): Messgegenstand ist hier die ZAHL der Widersprueche, nicht der Name.
  Pseudonymisierung waere kein Ausweg - die Menge der Sehenswuerdigkeitsnamen ist klein und
  oeffentlich, ein stabiler Hash per Woerterbuch rueckrechenbar.
* ZEITEN UND ENTFERNUNGEN STEHEN NUR IN VORAB FESTGELEGTEN KLASSEN (S5), nie als Einzelwert und
  nie in Reihenfolge: Ankerspannen und Zeitabstaende entstehen aus voller EXIF-Praezision, und
  eine geordnete Folge daraus waere ein Streckenabdruck. Eventdauern stehen als DAUER, nie als
  Anfang oder Ende.
* AUSFALLRICHTUNG (S7): Fehlt der Ortsdatensatz oder weicht er von seinem Hash ab, meldet Block C2
  "NICHT GEMESSEN", nie "0 %". Ein fehlendes Aggregat, das als gutes Messergebnis gelesen wird,
  truege hier die Entscheidung, an der Ortsbestimmung nichts zu aendern.
* LOGGING (S8): Dieses Modul schreibt kein Log. Eine kuenftige Logzeile traegt weder eine
  Koordinate noch einen Namen - nur ein festes Grund-Token und eine Id.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# `events_module` STEHT NEBEN DER NAMENSLISTE UNTEN, NICHT STATT IHRER, und traegt genau die
# aenderbaren Festlegungen: `MIN_EVENT_PHOTOS` wird bei jeder Nutzung frisch als MODULATTRIBUT
# gelesen. Ein `from ... import` baende den Wert beim Import - jede Fixture, die die Konstante
# verschiebt, liefe hier ins Leere, und der Bericht zaehlte still gegen eine andere Mindestgroesse
# als die, nach der gegliedert wurde. Die Namen in der Liste sind Typen, Funktionen und
# geschlossene Wortschaetze, keine Festlegungen.
from photosort import events as events_module
from photosort.config import settings
from photosort.db import make_engine, make_session_factory
from photosort.event_inputs import read_event_inputs
from photosort.events import (
    BOUNDARY_CAUSES,
    BOUNDARY_MOTIF_CHANGE,
    MERGE_BLOCK_REASONS,
    EventCandidate,
    EventFormation,
    LocationEntry,
    explain_events,
    has_measured_coordinate,
    inherited_locations,
)
from photosort.geonames import GeoNamesResolver, PlaceDatasetError, build_geonames_resolver
from photosort.landmark import place_hint_for
from photosort.models import (
    CriterionScoringRun,
    PhotoRanking,
    Project,
    ScanStatus,
)
from photosort.places import PlaceInfo, place_cell, usable_locality
from photosort.scoring import haversine_meters
from photosort.selection import carried_motifs, effective_target

Cell = tuple[float, float]

# DIE ENTFERNUNGSSCHWELLE, die "falsches Land" vertritt (Spec 0506, Block C). Der Laendercode steht
# nicht in den fuenf behaltenen Feldern des Ortsauszugs; eine Zuordnung, die um mehr als diese
# Entfernung von der Aufnahmeposition abweicht, ist falsch, ob sie eine Grenze ueberschreitet oder
# nicht.
#
# SIE MUSS UNTERHALB VON `geonames.GEONAMES_MAX_DISTANCE_METERS` (25 km) LIEGEN: Darueber koennte
# Block C2 sie strukturell nie ueberschreiten - der Auflöser verwirft solche Treffer bereits -, und
# ein Anteil von null waere dann kein Messergebnis, sondern eine Eigenschaft der Schwelle. Ein Test
# haelt diese Ungleichung fest.
#
# Sie ist zugleich die oberste Klassengrenze (S5), damit die Abnahme ohne Einzelwerte auskommt.
DISTANCE_THRESHOLD_METERS = 10_000.0

# DIE KLASSENRASTER, vorab festgelegt (S5). Genannt sind die INNEREN Grenzen; die unterste Klasse
# beginnt bei null, die oberste ist nach oben offen. Ein Wert GENAU auf einer Grenze faellt in die
# obere Klasse - damit ist die oberste Klasse genau "ab der Schwelle", und es gibt keinen zweiten
# Vergleich neben dem Raster.
DISTANCE_CLASS_BOUNDS = (250.0, 1000.0, 5000.0, DISTANCE_THRESHOLD_METERS)
DISTANCE_CLASS_LABELS = (
    "unter 250 m",
    "250 m bis unter 1 km",
    "1 km bis unter 5 km",
    "5 km bis unter 10 km",
    "10 km und mehr",
)

# DAS RASTER DER EMPFINDLICHKEITSMESSUNG (Block E). Beide Achsen sind Messparameter,
# keine Schwellen des Produkts: Sie legen fest, WO gemessen wird, und aendern an keinem Betriebswert
# etwas. `MOTIF_CHANGE_CONFIRMING_PHOTOS` (events.py) und die Motivstaerke-Grenze (selection.py)
# bleiben in diesem Schritt unveraendert und werden ausschliesslich variiert durchgerechnet.
#
# DER BETRIEBSWERT LAEUFT NICHT ALS RASTERZELLE MIT, sondern als eigene erste Zeile ohne jede
# Ueberschreibung - so traegt die Tabelle ihren eigenen Nullpunkt auch dann noch, wenn einer der
# beiden Werte spaeter wandert und in keiner Rasterzelle mehr steht.
MOTIF_CONFIRMING_VARIANTS = (2, 3, 4, 5, 6)
MOTIF_STRENGTH_VARIANTS = (0.3, 0.4, 0.5, 0.6, 0.7)

TIME_CLASS_BOUNDS = (60.0, 300.0, 1800.0, 7200.0, 43200.0)
TIME_CLASS_LABELS = (
    "unter 1 min",
    "1 bis unter 5 min",
    "5 bis unter 30 min",
    "30 min bis unter 2 h",
    "2 h bis unter 12 h",
    "12 h und mehr",
)


class EventProbeError(Exception):
    """Der Messlauf kann nicht stattfinden (unbekanntes Projekt, kein erfolgreicher Lauf).

    Meldungen nennen Bedingung und Status, nie einen Konfigurationswert und nie eine Koordinate."""


def _class_counts(values: Iterable[float], bounds: Sequence[float]) -> tuple[int, ...]:
    """Die Besetzung der Klassen zu `bounds` - die EINZIGE Form, in der eine Zeit oder eine
    Entfernung dieses Kommandos ausgegeben wird (S5).

    `bisect_right` ordnet einen Wert GENAU AUF einer Grenze der oberen Klasse zu. Dadurch ist die
    oberste Entfernungsklasse genau "ab `DISTANCE_THRESHOLD_METERS`", und der Anteil oberhalb der
    Schwelle wird aus ihr abgelesen statt ein zweites Mal gerechnet."""
    counts = [0] * (len(bounds) + 1)
    for value in values:
        counts[bisect_right(bounds, value)] += 1
    return tuple(counts)


def _tally(values: Iterable[int]) -> dict[int, int]:
    """Wie oft jeder Wert vorkommt - eine VERTEILUNG, keine Folge. Ein Aggregat ueber eine Menge
    sagt nichts ueber die Reihenfolge, in der ihre Werte entstanden sind."""
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _beyond_threshold(meters: float) -> bool:
    """Oberhalb der Entfernungsschwelle - DIE EINE Stelle, an der der Vergleich steht.

    Deckungsgleich mit der obersten Klasse von `DISTANCE_CLASS_BOUNDS`; ein zweiter, danebenstehen-
    der Vergleich liefe beim naechsten Grenzfall auseinander."""
    return meters >= DISTANCE_THRESHOLD_METERS


# --- Der gemessene Bestand ----------------------------------------------------------------------


@dataclass(frozen=True)
class EventProbeInput:
    """Der gemessene Bestand, bereits vollstaendig gelesen - ab hier rechnet alles rein.

    `candidates` ist die Kandidatenmenge des letzten erfolgreichen Kriterien-Laufs, `entries` die
    Inferenzbasis der Ortsherleitung (jedes Foto des Projekts). Beide kommen aus
    `event_inputs.py` - derselben Stelle, aus der sie auch der Lauf bezieht (ADR 0117 Punkt 5).

    `run_found` unterscheidet "Projekt ohne erfolgreichen Kriterien-Lauf" von "Lauf ohne
    Kandidaten".

    `selection_target` ist der EINGESTELLTE Richtwert des Projekts; `None` heisst "nicht selbst
    eingestellt" und ist etwas anderes als "kein Richtwert" (`models.py::Project`)."""

    project_id: int
    candidates: tuple[EventCandidate, ...]
    entries: tuple[LocationEntry, ...]
    run_found: bool
    selection_target: int | None = None

    @property
    def project_photos(self) -> int:
        """Die Bilderzahl, auf der der Album-Richtwert rechnet.

        DIESELBE MENGE, DIE AUCH DER LAUF ZAEHLT: `entries` ist jedes Foto dieses Projekts
        (`event_inputs.py`, Bindung an `Photo.project_id` ohne weitere Einschraenkung), also genau
        die Menge hinter `count(Photo where project_id)` in `worker.py`. Eine zweite Zaehlung
        daneben koennte mit ihr auseinanderlaufen."""
        return len(self.entries)


# --- Block A: wie sich die Bilder ueber die Cluster verteilen ------------------------------------


@dataclass(frozen=True)
class SizeCounts:
    """Block A. Dauern stehen als DAUER in Sekunden, nie als Anfang oder Ende (S2).

    `median_photos`, `longest_seconds` und `shortest_seconds` sind `None`, wenn es kein Event gibt:
    Eine Null hiesse "der Median ist null" bzw. "das kuerzeste Event dauert nichts" und waere eine
    Aussage, die niemand gemessen hat."""

    events_total: int
    photos_total: int
    events_by_photo_count: dict[int, int]
    single_photo_events: int
    median_photos: float | None
    largest_event_photos: int
    longest_seconds: float | None
    shortest_seconds: float | None


@dataclass(frozen=True)
class QuotaReach:
    """Ob die Kontingentvergabe der Albumauswahl ueberhaupt gewichten kann - Block A.

    DIE EIGENTLICHE ABNAHMEZAHL dieser Messung. `selection.py::_quotas` vergibt nach "Abdeckung
    zuerst" jedem Event zuerst einen Platz und verteilt erst den REST nach Groesse. Ist die
    Eventzahl mindestens so gross wie der Richtwert, ist nach diesem ersten Schritt kein Platz mehr
    uebrig (`remaining <= 0`, `selection.py`): Jedes Event bekommt genau einen, und die Gewichtung
    kommt nie zum Zug. Der Anteil der Ein-Bild-Cluster sagt darueber nichts - er faellt auch dann,
    wenn die Grundmenge mitschrumpft.

    `target` kommt aus `selection.effective_target`, NICHT aus einer zweiten Fassung der
    Ableitung: Zwei Formeln liefen beim naechsten Grenzfall auseinander, und der Bericht behauptete
    dann einen Richtwert, nach dem die Auswahl gar nicht arbeitet.

    `project_photos` und `candidates_total` stehen NEBENEINANDER, weil sie verschiedene Mengen sind
    (Auswertungsgrenze): Der Richtwert rechnet auf jedem Foto des Projekts, die gemessene
    Gliederung auf der Kandidatenmenge des letzten erfolgreichen Laufs. Fallen sie auseinander,
    gehoert das in den Bericht statt verrechnet zu werden."""

    target: int
    target_is_configured: bool
    project_photos: int
    candidates_total: int
    events_total: int

    @property
    def free_seats(self) -> int:
        """Die Plaetze, die nach "Abdeckung zuerst" noch zu verteilen sind - nie negativ: `_quotas`
        vergibt keine Plaetze zurueck, es bleibt bei einem je Event."""
        return max(self.target - self.events_total, 0)

    @property
    def weighting_is_effective(self) -> bool:
        """Gleichstand zaehlt schon als "wirkungslos": `_quotas` bricht ab, sobald nach der
        Abdeckung nichts mehr uebrig ist."""
        return self.events_total < self.target

    @property
    def measured_on_the_same_set(self) -> bool:
        return self.project_photos == self.candidates_total


def quota_reach(probe: EventProbeInput, events_total: int) -> QuotaReach:
    """Der Album-Richtwert dieses Projekts und die Eventzahl gegen ihn - rein.

    Rein lesend wie der ganze Bericht: `effective_target` rechnet, es schreibt nichts, und an
    `selection.py` aendert dieser Lauf nichts."""
    return QuotaReach(
        target=effective_target(probe.selection_target, probe.project_photos),
        target_is_configured=probe.selection_target is not None,
        project_photos=probe.project_photos,
        candidates_total=len(probe.candidates),
        events_total=events_total,
    )


async def read_event_probe_input(session: AsyncSession, project_id: int) -> EventProbeInput:
    """Der EINZIGE Datenbankzugriff dieses Moduls, und er liest ausschliesslich.

    SICHERHEIT: Die Bindung an `project_id` steht in jeder Abfrage ausgeschrieben - gemessen wird
    genau ein Projekt, nie ein Bestand ueber Projektgrenzen hinweg.

    DIE KANDIDATENMENGE SIND DIE FOTOS DER RANGZEILEN des letzten erfolgreichen Kriterien-Laufs,
    nicht die aktuellen Ausschuss-Ueberlebenden: Ein zwischenzeitliches Re-Scoring darf die
    Zusammensetzung dieses Laufs nicht nachtraeglich veraendern (dieselbe Wahl wie
    `worker.py::rebuild_run_grouping`).

    Alles Weitere kommt aus `event_inputs.py` - derselben Stelle, aus der auch der Lauf es bezieht
    (ADR 0117 Punkt 5)."""
    project_row = (
        await session.execute(
            select(Project.id, Project.selection_target).where(Project.id == project_id)
        )
    ).one_or_none()
    if project_row is None:
        raise EventProbeError(f"Es gibt kein Projekt mit der Id {project_id}.")
    selection_target = project_row.selection_target

    run_id = (
        await session.execute(
            select(CriterionScoringRun.id)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run_id is None:
        inputs = await read_event_inputs(session, project_id, [])
        return EventProbeInput(
            project_id=project_id,
            candidates=(),
            entries=inputs.entries,
            run_found=False,
            selection_target=selection_target,
        )

    photo_ids = list(
        (
            await session.execute(
                select(PhotoRanking.photo_id)
                .where(PhotoRanking.criterion_scoring_run_id == run_id)
                .order_by(PhotoRanking.photo_id)
            )
        )
        .scalars()
        .all()
    )
    inputs = await read_event_inputs(session, project_id, photo_ids)
    return EventProbeInput(
        project_id=project_id,
        candidates=inputs.candidates,
        entries=inputs.entries,
        run_found=True,
        selection_target=selection_target,
    )


# --- Die Zaehlbloecke, rein ---------------------------------------------------------------------


def size_counts(formation: EventFormation) -> SizeCounts:
    """Block A ueber genau die Gliederung, die auch der Lauf gebildet haette.

    Die VERTEILUNG statt eines Mittelwerts: Der Anteil der Ein-Bild-Cluster ist die Abnahmezahl
    dieser Spec, und ein Mittelwert verbirgt ihn."""
    sizes = [len(event.photo_ids) for event in formation.events]
    durations = [(event.ended_at - event.started_at).total_seconds() for event in formation.events]
    by_size = _tally(sizes)
    return SizeCounts(
        events_total=len(sizes),
        photos_total=sum(sizes),
        events_by_photo_count=by_size,
        single_photo_events=by_size.get(1, 0),
        median_photos=statistics.median(sizes) if sizes else None,
        largest_event_photos=max(sizes, default=0),
        longest_seconds=max(durations) if durations else None,
        shortest_seconds=min(durations) if durations else None,
    )


# --- Block B: welche Trennursache wie oft trennt -------------------------------------------------


@dataclass(frozen=True)
class CauseCounts:
    """Block B. ZWEI Zahlen je Ursache, und nur die zweite ist handlungsleitend: Eine Schwelle
    anzuheben hilft dort, wo sie ALLEIN getrennt hat - an einer Doppelgrenze traegt die andere
    Ursache weiter.

    Alle drei Abbildungen fuehren JEDE Ursache aus `BOUNDARY_CAUSES`, auch die nie gemeldete. Eine
    fehlende Zeile waere ein still unvollstaendiger Bericht, ohne dass eine Summe kleiner wuerde.

    `boundaries_total` ist `Eventzahl - 1`: Das erste Segment eines Laufs traegt keine Ursache.

    DIE GEGENANZEIGE steht daneben, und sie gehoert zu Block B: Beide Abnahmezahlen dieser Spec -
    der Anteil der Ein-Bild-Cluster und die Eventzahl - wuerden von einer zu aggressiven
    Verschmelzung BESSER erfuellt. Ohne `dissolved_by_merge` und `photos_moved_by_merge` misst eine
    Nachmessung nur die Unter-Zerstueckelung und bemerkte die Ueberverschmelzung nicht.

    `boundaries_before_merge` ist die Bezugsgroesse der Aufloesungen - die Zahl der Grenzen, die
    der Durchlauf erzeugt hat. Gegen `boundaries_total` gerechnet wuerde der Anteil mit jeder
    weiteren Aufloesung groesser statt aussagekraeftiger."""

    boundaries_total: int
    involved: dict[str, int]
    sole: dict[str, int]
    opening_a_small_segment: dict[str, int]
    photos_total: int
    boundaries_before_merge: int
    dissolved_by_merge: int
    photos_moved_by_merge: int


def cause_counts(formation: EventFormation) -> CauseCounts:
    """Block B ueber die Ursachenmengen desselben Durchlaufs, der auch die Gliederung gebildet hat.

    Der Index 0 bleibt AUSGESPART - seine Menge ist leer, und eine Zaehlung ueber ihn truege eine
    erfundene Zeitluecke in die Statistik.

    Eine Ursache ausserhalb des geschlossenen Vorrats laesst diese Zaehlung LAUT scheitern statt
    sie zu uebergehen: ein kuenftiges Signal ohne Eintrag in `BOUNDARY_CAUSES` verschwaende sonst
    aus dem Bericht, ohne dass eine Summe kleiner wuerde."""
    known = set(BOUNDARY_CAUSES)
    unknown = sorted({cause for causes in formation.causes for cause in causes} - known)
    if unknown:
        raise EventProbeError(
            "Trennursache ausserhalb des geschlossenen Vorrats: "
            f"{', '.join(unknown)}. Der Bericht waere still unvollstaendig - erst "
            "BOUNDARY_CAUSES ergaenzen."
        )

    involved = {cause: 0 for cause in BOUNDARY_CAUSES}
    sole = {cause: 0 for cause in BOUNDARY_CAUSES}
    opening_small = {cause: 0 for cause in BOUNDARY_CAUSES}
    for event, causes in zip(formation.events[1:], formation.causes[1:], strict=True):
        small = len(event.photo_ids) < events_module.MIN_EVENT_PHOTOS
        for cause in causes:
            involved[cause] += 1
            if len(causes) == 1:
                sole[cause] += 1
            if small:
                opening_small[cause] += 1
    # `max(..., 0)`: Ein Lauf ohne ein einziges Event hat null Grenzen, nicht minus eine.
    boundaries_total = max(len(formation.events) - 1, 0)
    return CauseCounts(
        boundaries_total=boundaries_total,
        involved=involved,
        sole=sole,
        opening_a_small_segment=opening_small,
        photos_total=sum(len(event.photo_ids) for event in formation.events),
        boundaries_before_merge=boundaries_total + formation.dissolved_boundaries,
        dissolved_by_merge=formation.dissolved_boundaries,
        photos_moved_by_merge=formation.moved_photos,
    )


# --- Block F: woran eine Zusammenlegung scheitert ------------------------------------------------


@dataclass(frozen=True)
class BlockCounts:
    """Block F. ZWEI Zahlen je Grund, und nur die zweite ist handlungsleitend.

    `involved` - der Grund stand an mindestens einer Kante des Segments.

    `at_every_edge` - er stand an JEDER Kante, und an keiner stand etwas daneben. Nur dann loest
    seine Behebung dieses Segment tatsaechlich auf: Bleibt an einer Kante ein zweiter Grund
    stehen, bleibt die Kante gesperrt; und ein Grund, der nur an einer von zwei Kanten stand, hat
    die Zusammenlegung nicht fuer sich verhindert. Das ist dieselbe Bedeutung wie "alleinige
    Ursache" in Block B, eine Ebene tiefer angewandt.

    Beide Abbildungen fuehren JEDEN Grund aus `MERGE_BLOCK_REASONS`, auch den nie aufgetretenen.
    Eine fehlende Zeile waere ein still unvollstaendiger Bericht, ohne dass eine Summe kleiner
    wuerde.

    Gezaehlt werden SEGMENTE, nie Kanten: Die Frage ist, wie viele Zusammenlegungen ein Grund
    verhindert hat, nicht wie oft er auftrat."""

    blocked_segments: int
    involved: dict[str, int]
    at_every_edge: dict[str, int]


def block_counts(formation: EventFormation) -> BlockCounts:
    """Block F ueber die Beobachtung DESSELBEN Durchlaufs, der auch die Gliederung gebildet hat.

    Ein Grund ausserhalb des geschlossenen Vorrats laesst diese Zaehlung LAUT scheitern statt sie
    zu uebergehen: ein kuenftiger Riegel ohne Eintrag in `MERGE_BLOCK_REASONS` verschwaende sonst
    aus dem Bericht, ohne dass eine Summe kleiner wuerde."""
    known = set(MERGE_BLOCK_REASONS)
    unknown = sorted(
        {
            reason
            for blocked in formation.blocked_segments
            for edge in blocked.edges
            for reason in edge
        }
        - known
    )
    if unknown:
        raise EventProbeError(
            "Grund ausserhalb des geschlossenen Vorrats: "
            f"{', '.join(unknown)}. Der Bericht waere still unvollstaendig - erst "
            "MERGE_BLOCK_REASONS ergaenzen."
        )

    involved = {reason: 0 for reason in MERGE_BLOCK_REASONS}
    at_every_edge = {reason: 0 for reason in MERGE_BLOCK_REASONS}
    for blocked in formation.blocked_segments:
        for reason in {reason for edge in blocked.edges for reason in edge}:
            involved[reason] += 1
        # "An allen Kanten DER Grund": jede Kante traegt genau einen Grund, und ueberall denselben.
        alone = {next(iter(edge)) for edge in blocked.edges if len(edge) == 1}
        if len(alone) == 1 and all(len(edge) == 1 for edge in blocked.edges):
            [only] = alone
            at_every_edge[only] += 1
    return BlockCounts(
        blocked_segments=len(formation.blocked_segments),
        involved=involved,
        at_every_edge=at_every_edge,
    )


# --- Block E: die Empfindlichkeit des Motivwechsels ----------------------------------------------


@dataclass(frozen=True)
class MotifSensitivityRow:
    """Eine Zeile des Rasters: dieselbe Kandidatenmenge unter einer Kombination durchgerechnet.

    `confirming_photos` und `strength_threshold` sind `None` in der Zeile des BETRIEBSWERTS - sie
    entsteht ohne jede Ueberschreibung und ist damit die Gliederung, die auch der Lauf bildete.

    `motif_change_is_off` kennzeichnet die andere Randzeile: den Motivwechsel ganz ohne Wirkung.
    Sie fuehrt in `confirming_photos` das tatsaechlich gerechnete Fenster mit, wird aber als "aus"
    beschriftet - die Zahl ist ein Rechenmittel, kein messbarer Betriebspunkt.

    DIE LETZTEN BEIDEN FELDER SIND DIE GEGENANZEIGE: Eventzahl und Ein-Bild-Anteil wuerden von
    einem zu groben Zusammenfassen BESSER erfuellt; groesstes Event und laengste Dauer stehen
    deshalb in derselben Zeile, nicht daneben. `longest_seconds` ist `None`, wenn es kein Event
    gibt - eine Null hiesse "das laengste Event dauert nichts"."""

    confirming_photos: int | None
    strength_threshold: float | None
    events_total: int
    single_photo_events: int
    sole_motif_boundaries: int
    largest_event_photos: int
    longest_seconds: float | None
    motif_change_is_off: bool = False


def motif_change_off_window(candidates: Sequence[EventCandidate]) -> int:
    """Ein Bestaetigungsfenster, das diese Kandidatenmenge NIE bestaetigen kann - der Motivwechsel
    damit aus, OHNE einen Abschaltpfad im Produktivcode.

    `motif_change_starts` bestaetigt einen Wechsel erst, wenn so viele aufeinanderfolgende
    mitredende Fotos ihn zeigen, wie das Fenster lang ist; mehr als alle Kandidatenfotos koennen
    das nie sein. Ein Fenster von "Kandidatenzahl plus eins" ist deshalb unerreichbar, und es
    entsteht keine einzige Motivgrenze.

    Bewusst kein Schalter an `motif_change_starts` und kein weiterer Parameter: Ein Abschaltpfad im
    Produktivcode waere ein Zweig, den nur die Messung betritt und den ab dann jeder Aufrufer
    setzen koennte."""
    return len(candidates) + 1


def _sensitivity_row(
    candidates: Sequence[EventCandidate],
    confirming_photos: int | None,
    strength_threshold: float | None,
    *,
    motif_change_is_off: bool = False,
) -> MotifSensitivityRow:
    """Eine Kombination, gerechnet mit den MITTELN DES LAUFS.

    `explain_events` ist derselbe Durchlauf, den auch der Lauf nimmt - die beiden Festlegungen
    gehen als Parameter hinein, statt dass hier eine zweite Fassung der Motivregel entstuende. Eine
    Nachbildung maesse etwas anderes, als der Lauf tut, waehrend beide fuer sich gruen blieben."""
    formation = explain_events(
        candidates,
        confirming_photos=confirming_photos,
        motif_presence_threshold=strength_threshold,
    )
    sizes = size_counts(formation)
    causes = cause_counts(formation)
    return MotifSensitivityRow(
        confirming_photos=confirming_photos,
        strength_threshold=strength_threshold,
        events_total=sizes.events_total,
        single_photo_events=sizes.single_photo_events,
        sole_motif_boundaries=causes.sole[BOUNDARY_MOTIF_CHANGE],
        largest_event_photos=sizes.largest_event_photos,
        longest_seconds=sizes.longest_seconds,
        motif_change_is_off=motif_change_is_off,
    )


def motif_sensitivity(candidates: Sequence[EventCandidate]) -> tuple[MotifSensitivityRow, ...]:
    """Das ganze Raster, die beiden Randzeilen voran: der Betriebswert, dann der Motivwechsel aus.

    ZWEI BEZUGSZEILEN STATT EINER: Das Raster zeigt, wie empfindlich der Motivwechsel ist; erst die
    Zeile "aus" zeigt, wie viel er insgesamt traegt. Ohne sie bliebe offen, wie die Gliederung ganz
    ohne ihn aussaehe, und die Antwort waere aus keiner Rasterzeile zu erschliessen.

    NUR DIE ALLEINIGE URSACHE ist handlungsleitend (wie in Block B): Eine Motivgrenze zu lockern
    loest dort eine Grenze auf, wo der Motivwechsel ALLEIN getrennt hat - an einer Doppelgrenze
    traegt die andere Ursache weiter.

    Rein: Kein Aufruf dieser Funktion aendert eine Konstante, eine Zeile oder einen Zustand."""
    return (
        _sensitivity_row(candidates, None, None),
        _sensitivity_row(
            candidates, motif_change_off_window(candidates), None, motif_change_is_off=True
        ),
        *(
            _sensitivity_row(candidates, confirming, strength)
            for confirming in MOTIF_CONFIRMING_VARIANTS
            for strength in MOTIF_STRENGTH_VARIANTS
        ),
    )


# --- Der Kohaerenz-Modus: vier Zahlen je Event ---------------------------------------------------

# WIE VIELE EVENTS DIE LISTE ZEIGT - die groessten, und bewusst keine Vollliste.
#
# EINE ZEILE JE EVENT WAERE UEBER DIE ZELLZAHLEN EINE BEWEGUNGSSPUR: Wie viele verschiedene Orte ein
# Anlass beruehrt hat, ist je Event eine Anzahl; ueber den ganzen Lauf gelesen ist es das Profil
# einer Reise. Die Frage dieses Modus - ein langer Ausflug oder mehrere verschmolzene Anlaesse -
# haengt an den GROESSTEN Events und ist mit wenigen Zeilen beantwortet. Der Bericht schreibt
# ausdruecklich hin, wonach ausgewaehlt wurde, damit niemand die Liste fuer vollstaendig haelt.
COHERENCE_TOP_EVENTS = 8


@dataclass(frozen=True)
class CoherenceRow:
    """Ein Event in FUENF ANZAHLEN, und in nichts sonst.

    Keine Zelle, keine Koordinate, kein Orts- oder Motivname, kein Zeitstempel, keine Position im
    Lauf (S2/S3). Die Aussagekraft entsteht aus den Zahlen selbst: Ein Event ueber fuenf Stunden mit
    ZWEI Ortszellen ist ein Ausflug, eines mit sechs sind verschmolzene Anlaesse.

    `measured_photos` TRAEGT GENAU DIESE DEUTUNG, und ohne sie ist `place_cells` nicht lesbar:
    `events.py::_cells_of` nimmt ausschliesslich Fotos mit GEMESSENER Koordinate, ein uebernommener
    Ort speist die Zellen nie. Ein Event, dessen Fotos ueberwiegend geerbt haben, zeigt deshalb eine
    kleine Zellzahl oder null - und die sieht aus wie "ein Ort, also ein Ausflug", waehrend
    tatsaechlich nichts gemessen wurde. In der Ausgangsmessung dieser Spec trugen 30,0 % der
    Kandidatenfotos keine eigene Koordinate, und sie koennen sich in einem einzigen Event ballen;
    eine Gesamtzahl je Gliederung finge genau diesen Fall nicht. Sie ist selbst eine Anzahl und
    damit S2-konform.

    `duration_seconds` steht als DAUER, nie als Anfang oder Ende (S2)."""

    photos: int
    measured_photos: int
    duration_seconds: float
    place_cells: int
    motifs: int


@dataclass(frozen=True)
class CoherenceCounts:
    """Die groessten Events einer Gliederung, dazu die Verteilung ueber ALLE.

    `largest` ist ausdruecklich ein Ausschnitt (`COHERENCE_TOP_EVENTS`); `cells_per_event` und
    `motifs_per_event` laufen dagegen ueber jedes Event - sonst behauptete der Bericht eine
    Verteilung, die nur fuer die groessten gilt. Beide sind Abbildungen "Anzahl -> Zahl der Events",
    also selbst Aggregate und keine Folge je Event."""

    events_total: int
    largest: tuple[CoherenceRow, ...]
    cells_per_event: dict[int, int]
    motifs_per_event: dict[int, int]


def coherence_counts(
    formation: EventFormation, candidates: Sequence[EventCandidate]
) -> CoherenceCounts:
    """Die Kohaerenz der Events einer Gliederung - rein, und ausschliesslich in Anzahlen.

    DIE ZELLEN LIEST DIESE FUNKTION, SIE BILDET SIE NICHT: `BuiltEvent.place_cells` traegt die
    verschiedenen gerundeten GEMESSENEN Zellen bereits sortiert und dublettenfrei
    (`events.py::_cells_of`); `len` darauf ist damit genau die Zahl der VERSCHIEDENEN Zellen. Eine
    zweite Bildung hier maesse die Zellen einer Gliederung, die so nie entstanden ist.

    WIE VIELE FOTOS DIESE ZELLEN UEBERHAUPT TRAGEN, steht daneben und entscheidet
    `events.py::has_measured_coordinate` - dieselbe eine Stelle, die auch `_cells_of` fragt. Ohne
    diese Zahl liesse sich eine kleine Zellzahl nicht von einer ungemessenen unterscheiden.

    WAS EIN FOTO TRAEGT, BEANTWORTET `selection.py::carried_motifs`, nicht diese Funktion - dieselbe
    eine Stelle und dieselbe eine Grenze wie im Lauf. `motif_strengths is None` heisst "keine
    Motiv-Kopfzeile" und traegt nichts bei; das ist etwas anderes als eine leere Kopfzeile, und
    beides ist hier gleich folgenlos.

    GEORDNET WIRD UEBER DIE GEMESSENEN WERTE, NIE UEBER DIE POSITION IM LAUF: Fotozahl, dann Dauer,
    dann Zellzahl, dann Motivzahl, jeweils absteigend. Eine nach Zeit geordnete Folge von Zellzahlen
    waere ein Bewegungsabdruck; eine nach Groesse geordnete ist es nicht, und die Position steht
    deshalb weder im Schluessel noch im Bericht."""
    motifs_by_photo = {
        candidate.photo_id: carried_motifs(candidate.motif_strengths)
        for candidate in candidates
        if candidate.motif_strengths is not None
    }
    measured_photo_ids = {
        candidate.photo_id for candidate in candidates if has_measured_coordinate(candidate)
    }

    rows = []
    for event in formation.events:
        carried: frozenset[str] = frozenset()
        for photo_id in event.photo_ids:
            carried |= motifs_by_photo.get(photo_id, frozenset())
        rows.append(
            CoherenceRow(
                photos=len(event.photo_ids),
                measured_photos=sum(
                    1 for photo_id in event.photo_ids if photo_id in measured_photo_ids
                ),
                duration_seconds=(event.ended_at - event.started_at).total_seconds(),
                place_cells=len(event.place_cells),
                motifs=len(carried),
            )
        )

    ordered = sorted(
        rows,
        key=lambda row: (
            row.photos,
            row.duration_seconds,
            row.place_cells,
            row.motifs,
            # ZULETZT, damit die oben beschriebene Rangfolge unveraendert bleibt - aber ueberhaupt
            # im Schluessel, weil die Ordnung sonst bei sonst gleichen Zeilen auf die stabile
            # Eingabefolge zurueckfiele, und die ist die des Laufs.
            row.measured_photos,
        ),
        reverse=True,
    )
    return CoherenceCounts(
        events_total=len(rows),
        largest=tuple(ordered[:COHERENCE_TOP_EVENTS]),
        cells_per_event=_tally(row.place_cells for row in rows),
        motifs_per_event=_tally(row.motifs for row in rows),
    )


# --- Block C1: der uebernommene Ort --------------------------------------------------------------


@dataclass(frozen=True)
class InheritanceCounts:
    """Block C1. BEIDE VERTEILUNGEN STEHEN NUR IN KLASSEN (S5) - sie entstehen aus voller
    EXIF-Praezision, und eine geordnete Folge aus Spannen und Zeitluecken waere ein Streckenabdruck.

    `candidates_without_own_coordinate` und `inheriting` sind ZWEI VERSCHIEDENE ZAHLEN: Ohne jeden
    Anker erbt niemand, und dann steht die erste hoch, waehrend die zweite null ist.

    `without_anchor_span` sind die Uebernahmen mit nur EINEM Nachbarn - dort gibt es keine Spanne.
    Eine Null hiesse "beide Nachbarn liegen am selben Ort" und waere die guenstigste aller Aussagen
    ueber eine Uebernahme."""

    candidates_total: int
    candidates_without_own_coordinate: int
    inheriting: int
    seconds_to_anchor_classes: tuple[int, ...]
    anchor_span_classes: tuple[int, ...]
    without_anchor_span: int


def inheritance_counts(
    entries: Sequence[LocationEntry], candidates: Sequence[EventCandidate]
) -> InheritanceCounts:
    """Block C1 ueber genau die Ankerwahl, die auch `infer_locations` trifft
    (`events.py::inherited_locations`) - eine zweite Fassung maesse den Abstand zu einem Anker, den
    das Foto gar nicht geerbt hat.

    DIE INFERENZBASIS IST DAS GANZE PROJEKT, BERICHTET WERDEN DIE KANDIDATEN: Ein aussortiertes
    Foto traegt eine ebenso gueltige Koordinate und darf die Ankerwahl mitbestimmen, aber die
    Grenzen dieses Laufs haengen an den Kandidaten, und nur ueber sie sagt die Verteilung etwas."""
    candidate_ids = {candidate.photo_id for candidate in candidates}
    reports = [
        report for report in inherited_locations(entries) if report.photo_id in candidate_ids
    ]
    spans = [
        report.anchor_span_meters for report in reports if report.anchor_span_meters is not None
    ]
    return InheritanceCounts(
        candidates_total=len(candidates),
        candidates_without_own_coordinate=sum(
            1 for candidate in candidates if candidate.gps_lat is None or candidate.gps_lon is None
        ),
        inheriting=len(reports),
        seconds_to_anchor_classes=_class_counts(
            (report.seconds_to_anchor for report in reports), TIME_CLASS_BOUNDS
        ),
        anchor_span_classes=_class_counts(spans, DISTANCE_CLASS_BOUNDS),
        without_anchor_span=len(reports) - len(spans),
    )


# --- Block C2: der aufgeloeste Ortsname ----------------------------------------------------------


@dataclass(frozen=True)
class MatchDistanceCounts:
    """Block C2. Die Entfernung steht in KLASSEN, nie je Zelle und nie neben Name oder Ebene (S4):
    Die Entfernung zu einem benannten, oeffentlich enumerierbaren GeoNames-Eintrag ist ein
    Trilaterationsmittel - `locality` und `neighbourhood` derselben Zelle schneiden sich zu rund
    zwei Punkten und unterliefen die 1,1-km-Koernung, die `PLACE_CELL_DIGITS = 2` zusichert."""

    cells_total: int
    cells_with_a_name: int
    distance_classes: tuple[int, ...]
    cells_beyond_threshold: int


def match_distance_counts(name_distances: Mapping[Cell, float | None]) -> MatchDistanceCounts:
    """Block C2 ueber die Zellen der Kandidatenfotos.

    `None` heisst "diese Zelle bekaeme gar keinen Ortsnamen" - sie besetzt dann keine Klasse. Eine
    Null besetzte die unterste und behauptete einen perfekt getroffenen Namen, den es nicht gibt."""
    distances = [distance for distance in name_distances.values() if distance is not None]
    classes = _class_counts(distances, DISTANCE_CLASS_BOUNDS)
    return MatchDistanceCounts(
        cells_total=len(name_distances),
        cells_with_a_name=len(distances),
        distance_classes=classes,
        # ABGELESEN, nicht ein zweites Mal gerechnet: Die Schwelle IST die oberste Klassengrenze.
        cells_beyond_threshold=classes[-1],
    )


# --- Block C3: der Sehenswuerdigkeitsname --------------------------------------------------------


@dataclass(frozen=True)
class LandmarkCounts:
    """Block C3. Der Weg, ueber den eine Ortsaussage am weitesten danebenliegen kann: Ein Name
    benennt das GANZE Event und verdraengt dessen Koordinatenstufe.

    Gezaehlt werden WIDERSPRUECHE, nie Namen (S3): Ein in sich stimmiger Name ist ohne Rueckfrage
    bei einem bezahlten Dienst nicht ueberpruefbar. Dieser Block BELEGT diesen Weg, wo Widersprueche
    auftreten, und kann ihn nicht widerlegen."""

    detections_total: int
    detections_without_place_hint: int
    names_total: int
    names_spread_beyond_threshold: int
    events_named_by_a_single_photo: int


def _max_pairwise_meters(cells: Sequence[Cell]) -> float:
    """Die groesste Entfernung zwischen zwei Zellen einer Menge.

    Gerechnet wird ueber die GERUNDETEN Zellen, nicht die Rohwerte: Das haelt den Aufwand klein
    (die Zahl verschiedener Zellen je Name ist klein, die der Fotos nicht) und gibt ausserdem
    keine volle EXIF-Praezision in die Rechnung, die den Bericht speist. Der Preis ist eine
    Unschaerfe von rund 1,1 km gegen eine Schwelle von 10 km."""
    return max(
        (
            haversine_meters(first[0], first[1], second[0], second[1])
            for index, first in enumerate(cells)
            for second in cells[index + 1 :]
        ),
        default=0.0,
    )


def landmark_counts(
    candidates: Sequence[EventCandidate],
    formation: EventFormation,
    locality_by_cell: Mapping[Cell, str],
) -> LandmarkCounts:
    """Block C3 ueber die Kandidaten des Laufs und die Gliederung, die aus ihnen entstand.

    "Ohne jeden Ortshinweis" entscheidet `landmark.py::place_hint_for` - dieselbe eine Stelle, die
    auch im Betrieb entscheidet, was einer Erkennung beigelegt wird. Ein Foto ohne eigene
    Koordinate bekommt dort `None`; ein uebernommener Ort erreicht die Funktion nie."""
    named = [candidate for candidate in candidates if candidate.landmark_name is not None]

    without_hint = 0
    cells_by_name: dict[str, list[Cell]] = {}
    for candidate in named:
        assert candidate.landmark_name is not None
        cell: Cell | None = None
        if candidate.gps_lat is not None and candidate.gps_lon is not None:
            cell = place_cell(candidate.gps_lat, candidate.gps_lon)
        locality = None if cell is None else locality_by_cell.get(cell)
        if place_hint_for(locality, candidate.gps_lat, candidate.gps_lon) is None:
            without_hint += 1
        if cell is not None:
            cells_by_name.setdefault(candidate.landmark_name, []).append(cell)

    spread = sum(
        1
        for cells in cells_by_name.values()
        if _beyond_threshold(_max_pairwise_meters(sorted(set(cells))))
    )

    name_by_photo = {candidate.photo_id: candidate.landmark_name for candidate in named}
    single_photo_named = 0
    for event in formation.events:
        if event.landmark_name is None or len(event.photo_ids) < 2:
            continue
        carriers = sum(
            1 for photo_id in event.photo_ids if name_by_photo.get(photo_id) == event.landmark_name
        )
        if carriers == 1:
            single_photo_named += 1

    return LandmarkCounts(
        detections_total=len(named),
        detections_without_place_hint=without_hint,
        names_total=len({candidate.landmark_name for candidate in named}),
        names_spread_beyond_threshold=spread,
        events_named_by_a_single_photo=single_photo_named,
    )


# --- Der Durchgang ueber die gefragten Zellen ----------------------------------------------------


@dataclass(frozen=True)
class PlaceMeasurement:
    """Block C2 - oder der Grund seines Ausbleibens (S7).

    Ein ausgebliebener Ortsdatensatz MELDET SICH: "0 %" waere hier ein gutes Messergebnis und
    truege die Entscheidung, an der Ortsbestimmung nichts zu aendern."""

    absent_reason: str | None = None
    distances: MatchDistanceCounts | None = None


async def name_distances_by_cell(
    resolver: GeoNamesResolver, cells: Sequence[Cell]
) -> tuple[dict[Cell, float | None], dict[Cell, str]]:
    """Je Zelle die Entfernung zu dem Eintrag, der ihren Namen geliefert haette - und der Name.

    Der NAME bleibt hier und erreicht den Bericht nie (S2/S4); er wird gebraucht, weil "diese
    Zelle bekaeme einen Ortsnamen" ausschliesslich `places.usable_locality` entscheidet - es gibt
    keine zweite Fassung dieser Regel. `None` heisst "kein Name", und eine solche Zelle besetzt
    keine Entfernungsklasse.

    Eine Anfrage JE VERSCHIEDENER ZELLE, nie je Foto und nie je Event - sonst ginge die
    Verweildauer je Ort mit in die Verteilung ein."""
    distances: dict[Cell, float | None] = {}
    localities: dict[Cell, str] = {}
    for cell in cells:
        answer = await resolver.resolve(cell)
        locality = (
            None
            if answer is None
            else usable_locality(
                PlaceInfo(
                    neighbourhood=answer.neighbourhood,
                    locality=answer.locality,
                    matched_level=answer.matched_level,
                )
            )
        )
        if locality is None:
            distances[cell] = None
            continue
        localities[cell] = locality
        # Name und Entfernung kommen aus DERSELBEN Nachbarschaftssuche - es gibt die eine nicht
        # ohne die andere.
        distance = resolver.match_distances(cell).get("locality")
        assert distance is not None
        distances[cell] = distance
    return distances, localities


# --- Die Ausgabe ---------------------------------------------------------------------------------


def _percent(part: int, whole: int) -> str:
    if whole == 0:
        return "-"
    return f"{100.0 * part / whole:.1f} %"


def _duration(seconds: float | None) -> str:
    """Eine DAUER, nie ein Anfang und nie ein Ende (S2). `None` heisst "nicht gemessen"."""
    if seconds is None:
        return "-"
    hours, rest = divmod(int(seconds), 3600)
    minutes, remaining = divmod(rest, 60)
    parts = [f"{hours} h"] if hours else []
    if minutes:
        parts.append(f"{minutes} min")
    if remaining or not parts:
        parts.append(f"{remaining} s")
    return " ".join(parts)


def _class_lines(counts: Sequence[int], labels: Sequence[str]) -> list[str]:
    """Die Klassenbesetzung als Liste - die EINZIGE Form, in der Zeiten und Entfernungen dieses
    Kommandos erscheinen (S5)."""
    total = sum(counts)
    return [
        f"  - {label}: {count} ({_percent(count, total)})"
        for label, count in zip(labels, counts, strict=True)
    ]


def _quota_lines(reach: QuotaReach) -> list[str]:
    """Der Album-Richtwert und die Eventzahl gegen ihn - AUSGESCHRIEBEN ALS AUSSAGE.

    Ein Zahlenpaar allein liesse den Schluss beim Leser, und genau dieser Schluss ist das Mass:
    Sind es mindestens so viele Events wie Plaetze, ist die Gewichtung der Albumauswahl
    wirkungslos."""
    origin = (
        "eingestellt"
        if reach.target_is_configured
        else f"abgeleitet aus {reach.project_photos} Fotos des Projekts, ein Zehntel aufgerundet"
    )
    verdict = (
        (
            f"Die Kontingentvergabe kann gewichten: {reach.events_total} Events auf "
            f'{reach.target} Plaetze - nach "Abdeckung zuerst" bleiben {reach.free_seats} '
            "Plaetze, die nach Groesse verteilt werden."
        )
        if reach.weighting_is_effective
        else (
            f"Die Kontingentvergabe kann nicht gewichten: {reach.events_total} Events auf "
            f"{reach.target} Plaetze - jedes Event bekommt genau einen Platz, und kein Restplatz "
            "bleibt uebrig, bevor die Gewichtung nach Groesse ueberhaupt beginnt."
        )
    )
    lines = [
        "",
        "### Reicht der Album-Richtwert fuer eine Gewichtung?",
        "",
        f"- Album-Richtwert: {reach.target} Bild(er) ({origin})",
        f"- Events: {reach.events_total}",
        f'- freie Plaetze nach "Abdeckung zuerst": {reach.free_seats}',
        "",
        verdict,
    ]
    if not reach.measured_on_the_same_set:
        lines += [
            "",
            f"Auswertungsgrenze: Der Richtwert rechnet auf den {reach.project_photos} Fotos des "
            f"Projekts, die gemessene Gliederung auf den {reach.candidates_total} Kandidaten des "
            "letzten erfolgreichen Kriterien-Laufs. Die beiden Mengen fallen hier auseinander.",
        ]
    return lines + [
        "",
        "Die Kontingentvergabe sieht ausserdem nur Events mit mindestens einem auswaehlbaren Foto",
        "(Ausschuss und Rangzeilen ohne Wert fallen dort weg); die Eventzahl hier ist ihre",
        "Obergrenze, nie eine kleinere Zahl.",
    ]


def render_motif_report(probe: EventProbeInput, rows: Sequence[MotifSensitivityRow]) -> str:
    """Block E als Markdown nach stdout - ZAHLEN OHNE ORTE UND OHNE ZEITPUNKTE (S2).

    Derselbe Bericht-Rand wie der Hauptbericht: keine Koordinate, kein Orts- oder
    Sehenswuerdigkeit-Name, kein OpenCloud-Pfad, kein Projektname, kein Zeitstempel; ausgewiesen
    wird die Projekt-Id. Dauern stehen als DAUER, nie als Anfang oder Ende.

    Die Zeile des Betriebswerts nennt ihre beiden Werte NICHT: Sie entsteht ohne Ueberschreibung,
    und eine ausgeschriebene Zahl daneben behauptete, gemessen zu haben, welcher Wert gerade gilt.
    Die Zeile "aus" nennt ihr Fenster aus demselben Grund nicht: Es ist ein Rechenmittel, und als
    Zahl gelesen sieht es aus wie ein weiterer messbarer Betriebspunkt."""
    lines = [
        f"# Empfindlichkeit des Motivwechsels, Projekt {probe.project_id}",
        "",
        "Dieselbe Kandidatenmenge, durchgerechnet unter mehreren Kombinationen aus der Zahl der",
        "bestaetigenden Fotos und der Motivstaerke-Grenze. BEIDE KONSTANTEN BLEIBEN UNVERAENDERT -",
        "dieser Lauf misst, er aendert nichts.",
        "",
        "Die letzten beiden Spalten sind die GEGENANZEIGE gegen zu grobes Zusammenfassen: Eventzahl",
        "und Ein-Bild-Anteil wuerden von einer zu groben Gliederung besser erfuellt.",
        "",
        "| bestaetigende Fotos | Motivstaerke-Grenze | Events | Ein-Bild-Cluster | "
        "motivwechsel allein | groesstes Event | laengste Dauer |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        operating = row.confirming_photos is None and row.strength_threshold is None
        if row.motif_change_is_off:
            # "aus" statt der gerechneten Fensterlaenge - und die Staerke-Grenze steht dort
            # unveraendert, wie in der Zeile des Betriebswerts.
            confirming, strength = "aus", "Betriebswert"
        elif operating:
            confirming, strength = "Betriebswert", "Betriebswert"
        else:
            confirming, strength = str(row.confirming_photos), f"{row.strength_threshold}"
        lines.append(
            f"| {confirming} | {strength} | {row.events_total} "
            f"| {row.single_photo_events} "
            f"({_percent(row.single_photo_events, row.events_total)}) "
            f"| {row.sole_motif_boundaries} "
            f"({_percent(row.sole_motif_boundaries, max(row.events_total - 1, 0))}) "
            f"| {row.largest_event_photos} Foto(s) | {_duration(row.longest_seconds)} |"
        )

    lines += [
        "",
        'Der Anteil bezieht sich auf die Grenzen MIT Ursache (Eventzahl - 1); "motivwechsel '
        'allein" zaehlt',
        "nur die Grenzen, an denen keine andere Ursache mitgemeldet hat - nur dort loest eine",
        "gelockerte Motivgrenze ueberhaupt etwas auf.",
        "",
        'Die Zeile "aus" ist keine Rasterzelle und kein Betriebspunkt, sondern der andere Rand: ein',
        "Bestaetigungsfenster groesser als die Zahl der Kandidatenfotos, nie bestaetigbar. Der",
        "Produktivcode bekommt dafuer keinen Abschalter und keinen weiteren Parameter; die",
        "Motivstaerke-Grenze steht dort unveraendert - ohne Wechsel wirkt sie ohnehin nicht.",
    ]
    return "\n".join(lines) + "\n"


def _distribution(counts: Mapping[int, int], unit: str) -> str:
    """Eine Verteilung "Anzahl -> Zahl der Events", aufsteigend nach der Anzahl.

    Die Ordnung ist die der ANZAHL, nie die des Laufs: Eine Verteilung sagt nichts darueber, in
    welcher Reihenfolge ihre Werte entstanden sind."""
    return ", ".join(f"{value} {unit}: {events}" for value, events in sorted(counts.items())) or "-"


def _coherence_block(title: str, counts: CoherenceCounts) -> list[str]:
    """Eine Gliederung: ihre Eventzahl, die groessten Events und die Verteilung ueber ALLE.

    Die beiden Verteilungszeilen laufen ueber JEDES Event, die Tabelle ist ein Ausschnitt. Ohne sie
    liesse sich an der Tabelle nicht ablesen, ob sie den Regelfall zeigt oder die Ausnahme."""
    lines = [
        f"## {title}",
        "",
        f"- Events: {counts.events_total}",
        f"- Ortszellen je Event: {_distribution(counts.cells_per_event, 'Zelle(n)')}",
        f"- Motive je Event: {_distribution(counts.motifs_per_event, 'Motiv(e)')}",
        "",
        "| Fotos | davon gemessen | Dauer | Ortszellen | Motive |",
        "|---|---|---|---|---|",
    ]
    if not counts.largest:
        return [*lines, "| - | - | - | - | - |"]
    return lines + [
        f"| {row.photos} | {row.measured_photos} | {_duration(row.duration_seconds)} "
        f"| {row.place_cells} | {row.motifs} |"
        for row in counts.largest
    ]


def render_coherence_report(
    probe: EventProbeInput, operating: CoherenceCounts, switched_off: CoherenceCounts
) -> str:
    """Der Kohaerenz-Modus als Markdown nach stdout - ZAHLEN OHNE ORTE UND OHNE ZEITPUNKTE (S2).

    Derselbe Bericht-Rand wie die uebrigen Modi: keine Koordinate, kein Orts-, Sehenswuerdigkeit-
    oder Motivname, kein OpenCloud-Pfad, kein Projektname, kein Zeitstempel; ausgewiesen wird die
    Projekt-Id. Dauern stehen als DAUER, nie als Anfang oder Ende.

    BEIDE GLIEDERUNGEN NEBENEINANDER, weil die Frage ein Vergleich ist: Das grosse Event der
    Gliederung "aus" ist nur gegen den Betriebswert zu beurteilen.

    DASS DIE TABELLE EIN AUSSCHNITT IST, STEHT AUSGESCHRIEBEN DARIN. Eine Liste ueber alle Events
    waere ueber die Zellzahlen eine Bewegungsspur; eine Liste ueber die groessten ohne diesen Satz
    laese sich fuer die vollstaendige halten und die uebrigen Events fuer nicht vorhanden."""
    return (
        "\n".join(
            [
                f"# Kohaerenz der Events, Projekt {probe.project_id}",
                "",
                "Je Event fuenf ANZAHLEN: Fotozahl, davon mit gemessener Koordinate, Dauer, Zahl",
                "der verschiedenen Ortszellen und Zahl der verschiedenen getragenen Motive. Weder",
                "Zelle noch Koordinate, weder Orts- noch Motivname, kein Zeitpunkt - die Aussage",
                "entsteht aus den Zahlen selbst: Ein langes Event mit ZWEI Ortszellen ist ein",
                "Ausflug, eines mit sechs sind mehrere verschmolzene Anlaesse.",
                "",
                'Diese Lesart gilt nur soweit gemessen wurde, und die Spalte "davon gemessen" ist',
                "deshalb keine Beigabe: In die Ortszellen gehen AUSSCHLIESSLICH Fotos mit eigener",
                "Koordinate ein - ein uebernommener Ort speist sie nie. Liegt sie weit unter der",
                "Fotozahl, ist eine kleine Zellzahl keine Aussage ueber den Anlass, sondern eine",
                "Luecke in der Messung - und sie sieht genauso aus wie ein Befund.",
                "",
                f"Die Tabelle zeigt je Gliederung hoechstens die {COHERENCE_TOP_EVENTS} groessten",
                "Events nach FOTOZAHL, absteigend; bei gleicher Fotozahl entscheiden Dauer,",
                "Zellzahl und Motivzahl. Sie ist damit bewusst nicht vollstaendig, sobald die",
                "Gliederung mehr Events traegt - eine Zeile je Event waere ueber die Zellzahlen",
                "eine Bewegungsspur. Die beiden Verteilungszeilen ueber der Tabelle laufen dagegen",
                "immer ueber JEDES Event.",
                "",
                "Die Reihenfolge der Zeilen ist die der Groesse, nie die des Laufs; eine Position",
                "oder Kennung des Events steht nirgends.",
                "",
                *_coherence_block("Betriebswert", operating),
                "",
                *_coherence_block("Motivwechsel aus", switched_off),
                "",
                'Die zweite Gliederung entsteht wie die Zeile "aus" der Empfindlichkeitsmessung:',
                "ueber ein Bestaetigungsfenster groesser als die Zahl der Kandidatenfotos, das nie",
                "bestaetigt werden kann. Der Produktivcode bekommt dafuer keinen Abschalter und",
                "keinen weiteren Parameter, und an der Gliederung aendert dieser Lauf nichts - er",
                "misst.",
            ]
        )
        + "\n"
    )


def render_bolt_report(probe: EventProbeInput, formation: EventFormation) -> str:
    """Block F als Markdown nach stdout - ZAHLEN OHNE ORTE UND OHNE ZEITPUNKTE (S2).

    Derselbe Bericht-Rand wie die uebrigen Modi: keine Koordinate, kein Orts- oder
    Sehenswuerdigkeit-Name, kein OpenCloud-Pfad, kein Projektname, kein Zeitstempel; ausgewiesen
    wird die Projekt-Id. Die Gruende selbst sind interne Kennungen aus geschlossenem Vorrat.

    Die beiden Bezugszeilen oben (Events, Ein-Bild-Cluster) stehen dabei, weil der Bericht sonst
    nicht fuer sich stuende: "vier gesperrte Segmente" heisst etwas anderes bei 91 Events als bei
    10."""
    sizes = size_counts(formation)
    blocks = block_counts(formation)

    lines = [
        f"# Woran eine Zusammenlegung scheitert, Projekt {probe.project_id}",
        "",
        f"- Events: {sizes.events_total}",
        f"- Ein-Bild-Cluster: {sizes.single_photo_events} "
        f"({_percent(sizes.single_photo_events, sizes.events_total)})",
        f"- durch Stufe 3 aufgeloeste Grenzen: {formation.dissolved_boundaries}",
        f"- zu kleine Segmente, die bestehen blieben: {blocks.blocked_segments}",
        f"- Mindestgroesse eines Segments: {events_module.MIN_EVENT_PHOTOS} Fotos",
        "",
        "| Grund | an einer Kante beteiligt | an allen Kanten der Grund |",
        "|---|---|---|",
    ]
    for reason in MERGE_BLOCK_REASONS:
        involved = blocks.involved[reason]
        at_every_edge = blocks.at_every_edge[reason]
        lines.append(
            f"| {reason} | {involved} ({_percent(involved, blocks.blocked_segments)}) "
            f"| {at_every_edge} ({_percent(at_every_edge, blocks.blocked_segments)}) |"
        )

    lines += [
        "",
        "Gezaehlt werden SEGMENTE, nie Kanten, und ein Segment hat so viele Kanten, wie es Nachbarn",
        "hat. An einer Kante duerfen mehrere Gruende gleichzeitig stehen; ausgewiesen werden alle.",
        "",
        "Nur die zweite Spalte ist handlungsleitend: Sie zaehlt die Segmente, an deren JEDER Kante",
        "dieser Grund stand und sonst keiner - allein dort loest seine Behebung die Zusammenlegung",
        "aus. Steht daneben ein zweiter Grund, bleibt die Kante auch ohne diesen gesperrt; stand er",
        "nur an einer von zwei Kanten, hat er die Zusammenlegung nicht fuer sich verhindert.",
        "",
        "`kein_nachbar` greift nur, wenn es UEBERHAUPT keinen Nachbarn gibt. Eine fehlende Seite am",
        "Rand ist kein Hindernis und zaehlt nicht als Kante.",
        "",
        "`unantastbar` ist kein Riegel, sondern die Zusage, dass eine Grenze mit der Ursache",
        "`motivwechsel` nie aufgeloest wird. Ihre Behebung waere eine andere Entscheidung als die",
        "Aenderung einer Zahl.",
        "",
        "Dieser Lauf beobachtet nur: An der Gliederung und an den Riegeln aendert er nichts.",
    ]
    return "\n".join(lines) + "\n"


def render_report(
    probe: EventProbeInput,
    formation: EventFormation,
    place: PlaceMeasurement,
    locality_by_cell: Mapping[Cell, str],
) -> str:
    """Markdown nach stdout - ZAHLEN OHNE ORTE UND OHNE ZEITPUNKTE.

    Der Bericht traegt keine Koordinate, keinen Orts- oder Sehenswuerdigkeit-Namen, keinen
    OpenCloud-Pfad, keinen Projektnamen und keinen Zeitstempel (S2); ausgewiesen wird die
    Projekt-Id. Damit sind die Zahlen als Ganzes weitergebbar, ohne Einzelfallpruefung."""
    sizes = size_counts(formation)
    causes = cause_counts(formation)
    reach = quota_reach(probe, sizes.events_total)
    inheritance = inheritance_counts(probe.entries, probe.candidates)
    landmarks = landmark_counts(probe.candidates, formation, locality_by_cell)

    lines = [
        f"# Event-Messung, Projekt {probe.project_id}",
        "",
        "## A - Verteilung der Events nach Fotozahl",
        "",
        f"- Events: {sizes.events_total}",
        f"- Fotos in Events: {sizes.photos_total}",
        f"- Ein-Bild-Cluster: {sizes.single_photo_events} "
        f"({_percent(sizes.single_photo_events, sizes.events_total)})",
        f"- Median der Fotozahl: {sizes.median_photos if sizes.median_photos is not None else '-'}",
        f"- groesstes Event: {sizes.largest_event_photos} Foto(s)",
        f"- laengste Eventdauer: {_duration(sizes.longest_seconds)}",
        f"- kuerzeste Eventdauer: {_duration(sizes.shortest_seconds)}",
        "- Events nach Fotozahl: "
        + (
            ", ".join(
                f"{size} Foto(s): {count}"
                for size, count in sorted(sizes.events_by_photo_count.items())
            )
            or "-"
        ),
        *_quota_lines(reach),
        "",
        "## B - Trennursachen",
        "",
        f"- Grenzen mit Ursache: {causes.boundaries_total} (Eventzahl - 1; das erste Segment "
        "eines Laufs traegt keine)",
        f"- Mindestgroesse eines Segments: {events_module.MIN_EVENT_PHOTOS} Fotos",
        "",
        "| Ursache | beteiligt | alleinige Ursache | eroeffnet ein zu kleines Segment |",
        "|---|---|---|---|",
    ]
    for cause in BOUNDARY_CAUSES:
        involved = causes.involved[cause]
        lines.append(
            f"| {cause} | {involved} ({_percent(involved, causes.boundaries_total)}) "
            f"| {causes.sole[cause]} ({_percent(causes.sole[cause], causes.boundaries_total)}) "
            f"| {causes.opening_a_small_segment[cause]} "
            f"({_percent(causes.opening_a_small_segment[cause], involved)}) |"
        )

    lines += [
        "",
        "### Gegenanzeige: was Stufe 3 wieder zusammengelegt hat",
        "",
        f"- Grenzen vor dem Zusammenlegen: {causes.boundaries_before_merge}",
        f"- davon durch Stufe 3 aufgeloest: {causes.dissolved_by_merge} "
        f"({_percent(causes.dissolved_by_merge, causes.boundaries_before_merge)})",
        f"- Fotos, die dadurch ihr Event gewechselt haben: {causes.photos_moved_by_merge} "
        f"von {causes.photos_total} "
        f"({_percent(causes.photos_moved_by_merge, causes.photos_total)})",
        "",
        "Beide Abnahmezahlen dieser Messung - der Anteil der Ein-Bild-Cluster und die Eventzahl -",
        "wuerden von einer zu aggressiven Verschmelzung besser erfuellt. Diese zwei Zahlen sind die",
        "Gegenprobe dazu.",
        "",
        "## C1 - uebernommener Ort",
        "",
        f"- Kandidatenfotos: {inheritance.candidates_total}",
        f"- davon ohne eigene Koordinate: {inheritance.candidates_without_own_coordinate} "
        f"({_percent(inheritance.candidates_without_own_coordinate, inheritance.candidates_total)})",
        f"- davon mit tatsaechlicher Uebernahme: {inheritance.inheriting}",
        "- Zeitabstand zum uebernommenen Anker:",
        *_class_lines(inheritance.seconds_to_anchor_classes, TIME_CLASS_LABELS),
        "- Ankerspanne (Entfernung zwischen vorherigem und naechstem Anker):",
        *_class_lines(inheritance.anchor_span_classes, DISTANCE_CLASS_LABELS),
        f"  - ohne Spanne (nur ein Nachbar): {inheritance.without_anchor_span}",
        "",
        "## C2 - aufgeloester Ortsname",
        "",
    ]
    if place.absent_reason is not None:
        lines += [f"NICHT GEMESSEN - {place.absent_reason}"]
    else:
        distances = place.distances
        assert distances is not None
        lines += [
            f"- gefragte Zellen: {distances.cells_total}",
            f"- davon mit Ortsnamen: {distances.cells_with_a_name} "
            f"({_percent(distances.cells_with_a_name, distances.cells_total)})",
            "- Entfernung zum namengebenden Eintrag:",
            *_class_lines(distances.distance_classes, DISTANCE_CLASS_LABELS),
            f"- ueber der Entfernungsschwelle: {distances.cells_beyond_threshold} "
            f"({_percent(distances.cells_beyond_threshold, distances.cells_with_a_name)})",
        ]

    lines += [
        "",
        "## C3 - Sehenswuerdigkeitsname",
        "",
        f"- Erkennungen unter den Kandidaten: {landmarks.detections_total}",
        f"- davon ohne jeden Ortshinweis: {landmarks.detections_without_place_hint} "
        f"({_percent(landmarks.detections_without_place_hint, landmarks.detections_total)})",
        f"- verschiedene Namen: {landmarks.names_total}",
        "- davon mit Traegerfotos ueber der Entfernungsschwelle auseinander: "
        f"{landmarks.names_spread_beyond_threshold}",
        f"- Events, deren Name auf genau einem von vielen Fotos beruht: "
        f"{landmarks.events_named_by_a_single_photo}",
        "",
        'Die Entfernungsschwelle vertritt "falsches Land": Der Laendercode steht nicht in den '
        "behaltenen",
        "Feldern des Ortsauszugs. Ein in sich stimmiger Sehenswuerdigkeitsname ist hier nicht "
        "widerlegbar -",
        "dieser Block belegt Widersprueche, er schliesst sie nicht aus.",
    ]
    return "\n".join(lines) + "\n"


# --- Verdrahtung ---------------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.event_probe",
        description=(
            "Misst an einem echten Projekt, wie die Event-Bildung heute gliedert. REIN LESEND - "
            "kein Lauf veraendert eine Zeile."
        ),
    )
    parser.add_argument("--project-id", type=int, required=True)
    # EINANDER AUSSCHLIESSEND: Zwei Modi gleichzeitig ist keine Frage, die eine Antwort hat, und
    # eine stille Vorrangregel gaebe einen Bericht aus, den niemand angefordert hat.
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--motiv",
        action="store_true",
        help=(
            "Statt der Bloecke A-C: die Empfindlichkeit des Motivwechsels. Dieselbe "
            "Kandidatenmenge unter mehreren Kombinationen aus der Zahl der bestaetigenden Fotos "
            "und der Motivstaerke-Grenze. Beide Konstanten bleiben dabei unveraendert."
        ),
    )
    modes.add_argument(
        "--riegel",
        action="store_true",
        help=(
            "Statt der Bloecke A-C: woran eine Zusammenlegung scheitert. Je zu kleinem Segment, "
            "das nicht zugeschlagen werden konnte, der Grund an seinen Kanten. Dieselbe "
            "Gliederung wie ohne Schalter - der Modus beobachtet, er aendert nichts."
        ),
    )
    modes.add_argument(
        "--kohaerenz",
        action="store_true",
        help=(
            "Statt der Bloecke A-C: die Kohaerenz der groessten Events, fuer den Betriebswert und "
            "fuer den Motivwechsel 'aus' nebeneinander. Je Event vier Anzahlen - Fotozahl, Dauer, "
            "Zahl der verschiedenen Ortszellen, Zahl der verschiedenen getragenen Motive. Rein "
            "lesend wie die uebrigen Modi."
        ),
    )
    parser.add_argument(
        "--ortsdatensatz",
        default=None,
        help=(
            "Pfad auf den GeoNames-Auszug. Ohne Angabe gilt die Betriebseinstellung "
            "PLACE_DATASET_PATH - also genau die Datei, aus der auch ein Lauf liest."
        ),
    )
    return parser


async def _probe_with_own_session(
    database_url: str,
    *,
    project_id: int,
    dataset_path: Path,
    motif: bool = False,
    bolts: bool = False,
    coherence: bool = False,
) -> str:
    engine = make_engine(database_url)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            probe = await read_event_probe_input(session, project_id)
    finally:
        await engine.dispose()

    if not probe.run_found:
        raise EventProbeError(
            f"Projekt {project_id} hat keinen erfolgreichen Kriterien-Lauf. Ohne Events gibt es "
            "nichts zu messen - erst einen Lauf durchfuehren."
        )

    if motif:
        # Block E fragt den Ortsauszug GAR NICHT: Die Empfindlichkeit des Motivwechsels haengt an
        # keiner Ortsangabe, und ein hier gebauter Auflöser laese Daten, die in diesen Bericht
        # ohnehin nie eingehen.
        return render_motif_report(probe, motif_sensitivity(probe.candidates))

    # DERSELBE Durchlauf, den auch der Lauf nimmt - nur zusaetzlich mit den Ursachen.
    formation = explain_events(probe.candidates)

    if bolts:
        # DIESELBE Gliederung wie ohne Schalter, aus demselben Aufruf: Ein eigener Rechenweg
        # maesse die Blockaden einer Gliederung, die so nie entstanden ist. Den Ortsauszug fragt
        # Block F ebensowenig wie Block E - keine seiner Zahlen haengt an einer Ortsangabe.
        return render_bolt_report(probe, formation)

    if coherence:
        # ZWEI Gliederungen, beide ueber `explain_events`: die des Betriebswerts (dieselbe wie
        # oben) und die ohne wirksamen Motivwechsel. Die zweite entsteht ueber dasselbe
        # unerreichbare Bestaetigungsfenster wie die Zeile "aus" in Block E - kein Abschaltpfad im
        # Produktivcode, kein weiterer Parameter. Den Ortsauszug fragt auch dieser Modus nicht:
        # Gezaehlt wird die ZAHL der Zellen, und die traegt das Event bereits.
        without_motif_change = explain_events(
            probe.candidates, confirming_photos=motif_change_off_window(probe.candidates)
        )
        return render_coherence_report(
            probe,
            coherence_counts(formation, probe.candidates),
            coherence_counts(without_motif_change, probe.candidates),
        )

    cells = sorted(
        {
            place_cell(candidate.gps_lat, candidate.gps_lon)
            for candidate in probe.candidates
            if candidate.gps_lat is not None and candidate.gps_lon is not None
        }
    )

    # DERSELBE Auflöser und DIESELBE Pruefung wie im Lauf: Fehlt der Auszug oder weicht er von
    # seinem Hash ab, wird auch hier keiner gebaut - und Block C2 MELDET sein Ausbleiben (S7).
    resolver = build_geonames_resolver(cells, path=dataset_path)
    if resolver is None:
        return render_report(
            probe,
            formation,
            PlaceMeasurement(
                absent_reason=(
                    "Der Ortsdatensatz fehlt oder weicht von seinem Hash ab - es wurde kein "
                    "Auflöser gebaut. Erst 'python -m photosort.place_dataset' laufen lassen. Die "
                    "Zahlen dieses Blocks fehlen, sie sind nicht null."
                )
            ),
            {},
        )

    distances, localities = await name_distances_by_cell(resolver, cells)
    return render_report(
        probe, formation, PlaceMeasurement(distances=match_distance_counts(distances)), localities
    )


def main(argv: Sequence[str] | None = None, *, database_url: str | None = None) -> int:
    """Verdrahtung + Exit-Code. `argv` und `database_url` sind injizierbar - kein
    `sys.argv`-Zugriff im Testpfad und kein unbeabsichtigter Zugriff auf die konfigurierte
    Anwendungs-Datenbank.

    `asyncio.run` laeuft INNERHALB von main(): eine Async-Engine ueberlebt keinen Loop-Wechsel."""
    args = _build_parser().parse_args(argv)
    try:
        report = asyncio.run(
            _probe_with_own_session(
                database_url or settings.database_url,
                project_id=args.project_id,
                dataset_path=Path(args.ortsdatensatz or settings.place_dataset_path),
                motif=args.motiv,
                bolts=args.riegel,
                coherence=args.kohaerenz,
            )
        )
    except (EventProbeError, PlaceDatasetError) as exc:
        # BEIDE Abbruchgruende sehen fuer den Aufrufer gleich aus: der Messlauf hat nicht
        # stattgefunden, und warum, steht in der Meldung.
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        # Nur der Fehlertyp, NIE str(exc)/Traceback - die SQLAlchemy-Meldung kann die
        # DATABASE_URL inklusive Zugangsdaten enthalten (Muster demo_state.py).
        print(f"Fehler: Datenbankzugriff fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
