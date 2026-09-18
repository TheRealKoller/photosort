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

import statistics
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.event_inputs import read_event_inputs
from photosort.events import (
    EventCandidate,
    EventFormation,
    LocationEntry,
)
from photosort.models import (
    CriterionScoringRun,
    PhotoRanking,
    Project,
    ScanStatus,
)

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
    Kandidaten"."""

    project_id: int
    candidates: tuple[EventCandidate, ...]
    entries: tuple[LocationEntry, ...]
    run_found: bool


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
    project_id_found = (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project_id_found is None:
        raise EventProbeError(f"Es gibt kein Projekt mit der Id {project_id}.")

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
    )


# --- Die Zaehlbloecke, rein ---------------------------------------------------------------------


def size_counts(formation: EventFormation) -> SizeCounts:
    """Block A ueber genau die Gliederung, die auch der Lauf gebildet haette.

    Die VERTEILUNG statt eines Mittelwerts: Der Anteil der Ein-Bild-Cluster ist die Abnahmezahl
    dieser Spec, und ein Mittelwert verbirgt ihn."""
    sizes = [len(event.photo_ids) for event in formation.events]
    durations = [(event.ended_at - event.started_at).total_seconds() for event in formation.events]
    by_size: dict[int, int] = {}
    for size in sizes:
        by_size[size] = by_size.get(size, 0) + 1
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
