"""REIN LESENDES Messkommando: misst an einem echten Projekt, was die Ortsauskunft hergibt.

Aufruf::

    docker compose exec -T backend python -m photosort.place_probe --project-id 3

Gemessen wird der Weg, der auch im Betrieb laeuft: der lokale Ortsdatensatz (ADR 0105). Dasselbe
Modul, derselbe Auflöser, dieselbe Vergabelogik wie im Kriterien-Lauf - eine zweite, nachbildende
Fassung driftete, und dann maesse dieses Kommando etwas anderes, als der Lauf tatsaechlich tut,
waehrend beide fuer sich gruen blieben.

REIN LESEND, und das ist eine gepruefte Zusage, keine Absicht: kein ``INSERT``/``UPDATE``/
``DELETE``, kein Aufrufpfad aus ``main.py``/``worker.py``, kein Endpunkt, kein
Compose-``command``. Kein Lauf hinterlaesst eine geaenderte, geloeschte oder neue Zeile.
``tests/test_place_probe.py`` haelt das dreifach fest - Import-Graph, Syntaxbaum-Waechter gegen
jede Schreibform und ein echter ``main()``-Lauf mit Schnappschuss jeder Tabelle davor und danach.
Kein Teil traegt allein.

WARUM DIESES MODUL IM PRODUKTIV-PAKET LIEGT: Es braucht die echten SQLAlchemy-Modelle und dieselbe
Zellbildung wie die Anwendung (``places.place_cell``) - ein zweites Abbild davon verfehlte genau
die Frage, die gemessen werden soll.

SICHERHEIT:

* MIT DEM EXTERNEN KANDIDATEN IST DER ABFLUSSPFAD DIESES KOMMANDOS VOLLSTAENDIG ENTFALLEN (ADR
  0105 Punkt 2): Es liest nur noch eine lokale Datei; keine Ortsangabe verlaesst das System.
* Gefragt wird ueber die MENGE der verschiedenen Zellen, nie je Event - sonst ginge die
  Verweildauer je Ort mit ein - und ausschliesslich ueber die TATSAECHLICH BESUCHTEN Zellen aus
  dem Projektbestand. Dieses Kommando erzeugt keine Zelle und rastert kein Rechteck ab.
* Die Vorgabe-Ausgabe traegt KEINE Koordinate, KEINEN aufgeloesten Ortsnamen und keinen
  OpenCloud-Pfad - nur Kennzahlen und die Projekt-Id. Namensbeispiele stehen ausschliesslich im
  abschaltbaren ``--namen``-Abschnitt.
* LOGGING: Dieses Modul schreibt kein Log. Eine kuenftige Logzeile traegt weder eine Koordinate
  noch einen Ortsnamen - weder einen angenommenen noch einen verworfenen.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.config import settings
from photosort.db import make_engine, make_session_factory
from photosort.events import assign_place_names, locality_of_event
from photosort.geonames import PlaceDatasetError, build_place_resolver
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoRanking,
    Project,
    ScanStatus,
)
from photosort.places import (
    PlaceAnswer,
    PlaceInfo,
    PlaceResolver,
    place_cell,
    usable_locality,
)

# Die vergroeberte Ortszelle, wie `places.place_cell` sie bildet. Eigener Name, weil sie in diesem
# Modul durchgaengig der Schluessel ist.
Cell = tuple[float, float]


class PlaceProbeError(Exception):
    """Der Messlauf kann nicht stattfinden (unbekanntes Projekt, fehlender Ortsdatensatz).

    Meldungen nennen Bedingung und Status, nie einen Konfigurationswert und nie eine Koordinate."""


@dataclass(frozen=True)
class ProbeEvent:
    """Ein Event des gemessenen Laufs, auf das reduziert, was die Bloecke brauchen.

    `place_cells` sind die verschiedenen gerundeten GEMESSENEN Zellen seiner Fotos, sortiert und
    dublettenfrei - dieselbe Menge, die `events.py::BuiltEvent` traegt. Der Feldname ist derselbe,
    weil `assign_place_names` beide ueber dasselbe Protokoll liest: die Vergabelogik steht genau
    EINMAL im Projekt."""

    position: int
    landmark_name: str | None
    place_kind: str | None
    place_cells: tuple[Cell, ...]


@dataclass(frozen=True)
class ProbeInput:
    """Der gemessene Bestand, bereits vollstaendig gelesen - ab hier rechnet alles rein.

    `photo_cells` traegt EINEN Eintrag JE FOTO mit gemessener Koordinate; Dubletten sind der
    Normalfall und genau das, was Block E zaehlt. `run_found` unterscheidet "Projekt ohne
    erfolgreichen Kriterien-Lauf" von "Lauf ohne Events"."""

    project_id: int
    photos_total: int
    photo_cells: tuple[Cell, ...]
    events: tuple[ProbeEvent, ...]
    run_found: bool


@dataclass(frozen=True)
class CoverageCounts:
    """Block A - die Obergrenze dessen, was ueberhaupt benannt werden kann."""

    photos_total: int
    photos_with_coordinate: int
    events_total: int
    events_with_landmark: int
    events_coordinate: int
    events_multiple: int
    events_without_place: int


@dataclass(frozen=True)
class CellCounts:
    """Block B - zugleich die Zahl der Anfragen, die ein Lauf je Weg tatsaechlich stellte."""

    distinct_cells: int
    cells_per_event: dict[int, int]
    max_cells_in_one_event: int


@dataclass(frozen=True)
class LevelCounts:
    """Block C - AGGREGIERT. Eine Zeile je Zelle traegt die Zelle nie als Kennung (S5).

    `cells_without_answer` und `cells_with_a_failed_request` sind ZWEI VERSCHIEDENE DINGE und
    duerfen nie zu einem werden: das eine heisst "der Dienst hat geantwortet und nichts
    gefunden" - ein Messergebnis -, das andere "es kam gar keine verwertbare Antwort" - ein
    Ausfall. Beides als "ohne Treffer" auszuweisen machte aus einer Drosselung ein schlechtes
    Messergebnis, und darauf faellt eine NICHT RUECKNEHMBARE Wegwahl. Dieselbe Unterscheidung
    trifft ADR 0102 Punkt 5 fuer den spaeteren Betrieb."""

    cells_total: int
    cells_without_answer: int
    cells_with_a_failed_request: int
    cells_with_locality: int
    cells_with_neighbourhood: int
    cells_region_or_country_only: int


@dataclass(frozen=True)
class HeadingCounts:
    """Block D - Verwendung "Ueberschrift". ZAEHLT EVENTS."""

    events_with_landmark: int
    events_named: int
    events_keeping_position: int
    events_sharing_a_name: int
    events_distinguishable_by_district: int


@dataclass(frozen=True)
class PhotoCounts:
    """Block E - Verwendung #469. ZAEHLT FOTOS, nicht Events: #469 fragt VOR der Event-Bildung."""

    photos_with_coordinate: int
    photos_with_a_resolved_locality: int


def coverage_counts(probe: ProbeInput) -> CoverageCounts:
    """Block A. Ein Projekt ohne Koordinaten und ohne erfolgreichen Lauf ist ein gueltiges
    Ergebnis, kein Fehler - die Obergrenze ist dann eben null."""
    return CoverageCounts(
        photos_total=probe.photos_total,
        photos_with_coordinate=len(probe.photo_cells),
        events_total=len(probe.events),
        events_with_landmark=sum(1 for e in probe.events if e.place_kind == "landmark"),
        events_coordinate=sum(1 for e in probe.events if e.place_kind == "coordinate"),
        events_multiple=sum(1 for e in probe.events if e.place_kind == "multiple"),
        events_without_place=sum(1 for e in probe.events if e.place_kind is None),
    )


def cell_counts(probe: ProbeInput) -> CellCounts:
    """Block B. Die Verteilung "wie viele Events haben n Zellen" statt eines Mittelwerts: ein
    Mittelwert verbirgt genau den Fall, der die Viertel-Regel traegt."""
    per_event: dict[int, int] = {}
    for event in probe.events:
        size = len(event.place_cells)
        per_event[size] = per_event.get(size, 0) + 1
    return CellCounts(
        distinct_cells=len(set(probe.photo_cells)),
        cells_per_event=per_event,
        max_cells_in_one_event=max((len(e.place_cells) for e in probe.events), default=0),
    )


def level_counts(
    answers_by_cell: Mapping[Cell, PlaceAnswer | None],
    failures: Mapping[str, int] | None = None,
) -> LevelCounts:
    """Block C. Gezaehlt wird nach `matched_level`, NICHT nach gefuellter Stufe: eine Antwort auf
    Regionsebene nennt oft trotzdem eine Stadt, und wer die mitzaehlt, misst systematisch zu
    guenstig - und traegt damit eine nicht ruecknehmbare Wegwahl.

    `failures` sind die Zellen, fuer die gar keine verwertbare Antwort kam. Sie werden aus
    `cells_without_answer` HERAUSGERECHNET, statt zusaetzlich danebenzustehen - sonst waere
    dieselbe Zelle zweimal gezaehlt. Ein Kandidat ohne Ausfallbegriff (der lokale Datensatz)
    laesst den Parameter weg."""
    failed = sum(failures.values()) if failures is not None else 0
    without = 0
    with_locality = 0
    with_neighbourhood = 0
    coarse_only = 0
    for answer in answers_by_cell.values():
        if answer is None:
            without += 1
            continue
        info = PlaceInfo(
            neighbourhood=answer.neighbourhood,
            locality=answer.locality,
            matched_level=answer.matched_level,
        )
        if usable_locality(info) is not None:
            with_locality += 1
            if answer.neighbourhood is not None:
                with_neighbourhood += 1
        elif answer.matched_level in ("region", "country"):
            coarse_only += 1
    return LevelCounts(
        cells_total=len(answers_by_cell),
        cells_without_answer=without - failed,
        cells_with_a_failed_request=failed,
        cells_with_locality=with_locality,
        cells_with_neighbourhood=with_neighbourhood,
        cells_region_or_country_only=coarse_only,
    )


def heading_counts(probe: ProbeInput, info_by_cell: Mapping[Cell, PlaceInfo]) -> HeadingCounts:
    """Block D. Zaehlt ueber die ECHTE Vergabe (`events.py::assign_place_names`), nie ueber eine
    Nachbildung davon: Was dieses Kommando misst, ist damit genau das, was ein Lauf schreibt.

    `locality_of_event` liefert den Namen OHNE Viertel - die Gleichnamigkeit ist eine Aussage
    ueber ihn, nicht ueber die fertige Ueberschrift. Ein Event, dessen fertiger Name von seinem
    Ortsnamen abweicht, hat sein Viertel bekommen und ist damit unterscheidbar.

    DIE PARTITION WIRD AUS DER VEREINIGUNG GEZAEHLT, nie durch Subtraktion: `events_named` zaehlt
    ALLE Events mit einem Ortsnamen, und `events_keeping_position` ist die Restmenge darueber.
    `events_with_landmark` ist eine TEILMENGE von `events_named` - ein benanntes Event traegt
    seinen Ortsnamen seit ADR 0120 ebenfalls und wuerde beim Abziehen doppelt fehlen."""
    localities = [locality_of_event(event, info_by_cell) for event in probe.events]
    names = assign_place_names(probe.events, info_by_cell)

    occurrences: dict[str, int] = {}
    for locality in localities:
        if locality is not None:
            occurrences[locality] = occurrences.get(locality, 0) + 1

    shared = 0
    distinguishable = 0
    for locality, name in zip(localities, names, strict=True):
        if locality is None or occurrences[locality] < 2:
            continue
        shared += 1
        if name != locality:
            distinguishable += 1

    with_landmark = sum(1 for event in probe.events if event.landmark_name is not None)
    named = sum(1 for name in names if name is not None)
    return HeadingCounts(
        events_with_landmark=with_landmark,
        events_named=named,
        events_keeping_position=len(probe.events) - named,
        events_sharing_a_name=shared,
        events_distinguishable_by_district=distinguishable,
    )


def photo_counts(probe: ProbeInput, info_by_cell: Mapping[Cell, PlaceInfo]) -> PhotoCounts:
    """Block E. Zaehlt ueber `photo_cells` - EINEN Eintrag JE FOTO -, nie ueber die Events.

    Eine Umsetzung, die diese Zahl aus Block D ableitet, zaehlt ein Event statt seiner Fotos und
    misst damit den halben Nutzen von #469."""
    resolved = sum(
        1 for cell in probe.photo_cells if usable_locality(info_by_cell.get(cell)) is not None
    )
    return PhotoCounts(
        photos_with_coordinate=len(probe.photo_cells),
        photos_with_a_resolved_locality=resolved,
    )


# --- Der Lesepfad ------------------------------------------------------------------------------


async def read_probe_input(session: AsyncSession, project_id: int) -> ProbeInput:
    """Der EINZIGE Datenbankzugriff dieses Moduls, und er liest ausschliesslich.

    SICHERHEIT: Die Bindung an `project_id` steht in jeder Abfrage ausgeschrieben - gemessen wird
    genau ein Projekt, nie ein Bestand ueber Projektgrenzen hinweg.

    Die Zellen eines Events entstehen ueber `PhotoRanking` (die Kandidatenfotos DIESES Laufs) und
    ueber dieselbe `places.place_cell`, die auch die Anwendung benutzt."""
    project_id_found = (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project_id_found is None:
        raise PlaceProbeError(f"Es gibt kein Projekt mit der Id {project_id}.")

    photo_rows = (
        await session.execute(
            select(Photo.id, Photo.gps_lat, Photo.gps_lon).where(Photo.project_id == project_id)
        )
    ).all()
    # AUSSCHLIESSLICH GEMESSENE Koordinaten: ein uebernommener Ort speist den Ortsbezug eines
    # Events nie und darf deshalb auch die Messung nicht aufhuebschen.
    cell_by_photo = {
        photo_id: place_cell(lat, lon)
        for photo_id, lat, lon in photo_rows
        if lat is not None and lon is not None
    }
    photo_cells = tuple(sorted(cell_by_photo.values()))

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
        return ProbeInput(
            project_id=project_id,
            photos_total=len(photo_rows),
            photo_cells=photo_cells,
            events=(),
            run_found=False,
        )

    event_rows = (
        await session.execute(
            select(Event.id, Event.position, Event.landmark_name, Event.place_kind)
            .where(Event.criterion_scoring_run_id == run_id)
            .order_by(Event.position)
        )
    ).all()
    ranking_rows = (
        await session.execute(
            select(PhotoRanking.event_id, PhotoRanking.photo_id).where(
                PhotoRanking.criterion_scoring_run_id == run_id
            )
        )
    ).all()

    grouped: dict[int, list[Cell]] = {}
    for event_id, photo_id in ranking_rows:
        cell = cell_by_photo.get(photo_id)
        if cell is not None:
            grouped.setdefault(event_id, []).append(cell)

    events = tuple(
        ProbeEvent(
            position=position,
            landmark_name=landmark_name,
            place_kind=place_kind,
            place_cells=tuple(sorted(set(grouped.get(event_id, ())))),
        )
        for event_id, position, landmark_name, place_kind in event_rows
    )
    return ProbeInput(
        project_id=project_id,
        photos_total=len(photo_rows),
        photo_cells=photo_cells,
        events=events,
        run_found=True,
    )


# --- Der Durchgang ueber die gefragten Zellen ---------------------------------------------------


async def resolve_all(
    resolver: PlaceResolver, cells: Sequence[Cell]
) -> dict[Cell, PlaceAnswer | None]:
    """Eine Anfrage JE VERSCHIEDENER ZELLE, nie je Event - sonst ginge die Verweildauer je Ort
    mit hinaus. Nacheinander, damit der Mindestabstand des Schrittmachers auch greift."""
    answers: dict[Cell, PlaceAnswer | None] = {}
    for cell in cells:
        answers[cell] = await resolver.resolve(cell)
    return answers


# --- Die Ausgabe -------------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateResult:
    """Das Messergebnis EINES Kandidaten, oder der Grund seines Ausbleibens.

    Ein ausgebliebener Kandidat MELDET SICH (S4): eine leere Spalte wuerde als schlechtes
    Messergebnis gelesen, und darauf faellt dann eine nicht ruecknehmbare Wegwahl."""

    name: str
    absent_reason: str | None = None
    levels: LevelCounts | None = None
    headings: HeadingCounts | None = None
    photos: PhotoCounts | None = None
    examples: tuple[str, ...] = ()


def _info_by_cell(answers: Mapping[Cell, PlaceAnswer | None]) -> dict[Cell, PlaceInfo]:
    return {
        cell: PlaceInfo(
            neighbourhood=answer.neighbourhood,
            locality=answer.locality,
            matched_level=answer.matched_level,
        )
        for cell, answer in answers.items()
        if answer is not None
    }


def measure_candidate(
    name: str,
    probe: ProbeInput,
    answers: Mapping[Cell, PlaceAnswer | None],
    failures: Mapping[str, int] | None = None,
) -> CandidateResult:
    """Die Bloecke C, D und E fuer einen Kandidaten.

    `examples` traegt die aufgeloesten Namen - sie erscheinen NUR im `--namen`-Abschnitt.
    `failures` bleibt bei einer Quelle ohne Ausfallbegriff leer: der lokale Datensatz antwortet
    entweder oder es gibt ihn nicht, und dann entsteht gar kein Auflöser."""
    infos = _info_by_cell(answers)
    resolved = sorted(
        {locality for info in infos.values() if (locality := usable_locality(info)) is not None}
    )
    return CandidateResult(
        name=name,
        levels=level_counts(answers, failures),
        headings=heading_counts(probe, infos),
        photos=photo_counts(probe, infos),
        examples=tuple(resolved),
    )


def _percent(part: int, whole: int) -> str:
    if whole == 0:
        return "-"
    return f"{100.0 * part / whole:.1f} %"


def render_report(
    probe: ProbeInput, candidates: Sequence[CandidateResult], *, show_names: bool
) -> str:
    """Markdown nach stdout - ZAHLEN OHNE KOORDINATEN.

    Die Vorgabe-Ausgabe traegt keine Koordinate, keinen aufgeloesten Ortsnamen und keinen
    OpenCloud-Pfad; damit sind die Zahlen als Ganzes weitergebbar, ohne Einzelfallpruefung. Block
    C steht aggregiert - eine Zeile je Zelle traegt die Zelle nie als Kennung."""
    coverage = coverage_counts(probe)
    cells = cell_counts(probe)
    lines = [
        f"# Ortsauskunft-Messung, Projekt {probe.project_id}",
        "",
        "## A - Abdeckung",
        "",
        f"- Fotos gesamt: {coverage.photos_total}",
        f"- davon mit gemessener Koordinate: {coverage.photos_with_coordinate} "
        f"({_percent(coverage.photos_with_coordinate, coverage.photos_total)})",
        f"- Events des letzten erfolgreichen Kriterien-Laufs: {coverage.events_total}",
        f"  - mit Sehenswuerdigkeit (bereits benannt): {coverage.events_with_landmark}",
        f"  - place_kind='coordinate': {coverage.events_coordinate}",
        f"  - place_kind='multiple': {coverage.events_multiple}",
        f"  - ohne Ortsbezug: {coverage.events_without_place}",
        "",
        "## B - Zellen",
        "",
        f"- verschiedene Zellen im Projekt: {cells.distinct_cells}",
        "  (zugleich die Zahl der Anfragen, die ein Lauf je Weg stellte)",
        f"- groesste Zellzahl in einem Event: {cells.max_cells_in_one_event}",
        "- Events nach Zellzahl: "
        + (
            ", ".join(
                f"{size} Zelle(n): {count}" for size, count in sorted(cells.cells_per_event.items())
            )
            or "-"
        ),
    ]

    for candidate in candidates:
        lines += ["", f"## Kandidat: {candidate.name}", ""]
        if candidate.absent_reason is not None:
            lines += [f"NICHT GEMESSEN - {candidate.absent_reason}", ""]
            continue
        levels = candidate.levels
        headings = candidate.headings
        photos = candidate.photos
        assert levels is not None and headings is not None and photos is not None
        lines += [
            "### C - getroffene Ebenen (aggregiert)",
            "",
            f"- gefragte Zellen: {levels.cells_total}",
            f"- ohne Treffer (Quelle antwortete, fand nichts): {levels.cells_without_answer}",
            f"- mit Ortsnamen: {levels.cells_with_locality} "
            f"({_percent(levels.cells_with_locality, levels.cells_total)})",
            f"- davon zusaetzlich mit Viertel: {levels.cells_with_neighbourhood}",
            f"- nur Region/Land (gilt als kein Name): {levels.cells_region_or_country_only}",
        ]
        # AUSFALL und NICHTTREFFER bleiben getrennt (ADR 0102 Punkt 5). Die Zeile erscheint nur,
        # wenn es tatsaechlich einen Ausfall gab: Der lokale Datensatz kennt keinen - er liegt
        # vor und antwortet, oder es entsteht gar kein Auflöser. Eine dauerhaft auf null stehende
        # Zeile behauptete eine Messung, die niemand vornimmt.
        if levels.cells_with_a_failed_request:
            lines += [
                f"- AUSFALL (gar keine verwertbare Antwort): {levels.cells_with_a_failed_request} "
                f"({_percent(levels.cells_with_a_failed_request, levels.cells_total)})",
                "  ACHTUNG: Diese Zellen sind NICHT gemessen - sie sagen nichts ueber die",
                "  Quelle aus. Ein nennenswerter Ausfall macht die Zahlen dieses Kandidaten",
                "  unbrauchbar; dann erst die Ursache beheben und neu messen, nicht auf dieser",
                "  Grundlage entscheiden.",
            ]
        lines += [
            "",
            "### D - Verwendung Ueberschrift (zaehlt EVENTS)",
            "",
            f"- Events mit Sehenswuerdigkeit (Teilmenge der benannten): "
            f"{headings.events_with_landmark}",
            f"- Events, die einen Ortsnamen bekaemen: {headings.events_named}",
            f"- Events, die bei Nummer und Zeitspanne blieben: {headings.events_keeping_position}",
            f"- davon gleichnamig im selben Lauf: {headings.events_sharing_a_name}",
            f"- davon per Viertel unterscheidbar: {headings.events_distinguishable_by_district}",
            "",
            "### E - Verwendung #469 (zaehlt FOTOS)",
            "",
            f"- Fotos mit Koordinate: {photos.photos_with_coordinate}",
            f"- davon in einer Zelle mit Ortsnamen: {photos.photos_with_a_resolved_locality} "
            f"({_percent(photos.photos_with_a_resolved_locality, photos.photos_with_coordinate)})",
        ]

    if show_names:
        lines += [
            "",
            "## Aufgeloeste Namen",
            "",
            "ACHTUNG: Ein Ortsname IST die Ortsangabe - ihn wegzugeben ist dasselbe wie die Zelle",
            "wegzugeben. Dieser Abschnitt gehoert nicht in eine Weitergabe der Zahlen.",
            "",
        ]
        for candidate in candidates:
            if candidate.absent_reason is not None:
                continue
            lines.append(f"- {candidate.name}: " + (", ".join(candidate.examples) or "-"))

    return "\n".join(lines) + "\n"


# --- Verdrahtung -------------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.place_probe",
        description=(
            "Misst an einem echten Projekt, was eine Ortsauskunft hergaebe. REIN LESEND - kein "
            "Lauf veraendert eine Zeile."
        ),
    )
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument(
        "--ortsdatensatz",
        default=None,
        help=(
            "Pfad auf den GeoNames-Auszug. Ohne Angabe gilt die Betriebseinstellung "
            "PLACE_DATASET_PATH - also genau die Datei, aus der auch ein Lauf liest."
        ),
    )
    parser.add_argument(
        "--namen",
        action="store_true",
        help=(
            "Haengt die aufgeloesten Ortsnamen an. STANDARDMAESSIG AUS, damit die Zahlen fuer "
            "sich weitergegeben werden koennen."
        ),
    )
    return parser


async def _probe_with_own_session(
    database_url: str,
    *,
    project_id: int,
    dataset_path: Path,
    show_names: bool,
) -> str:
    engine = make_engine(database_url)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            probe = await read_probe_input(session, project_id)
    finally:
        await engine.dispose()

    if not probe.run_found:
        raise PlaceProbeError(
            f"Projekt {project_id} hat keinen erfolgreichen Kriterien-Lauf. Ohne Events gibt es "
            "nichts zu messen - erst einen Lauf durchfuehren."
        )

    cells = sorted(set(probe.photo_cells))

    # DERSELBE Auflöser und DIESELBE Pruefung wie im Lauf: Fehlt der Auszug oder weicht er von
    # seinem Hash ab, wird auch hier keiner gebaut. Der Kandidat MELDET dann sein Ausbleiben -
    # eine leere Spalte wuerde als schlechtes Messergebnis gelesen.
    resolver = build_place_resolver(cells, path=dataset_path)
    if resolver is None:
        candidate = CandidateResult(
            name="Lokaler Ortsdatensatz (GeoNames)",
            absent_reason=(
                "Der Ortsdatensatz fehlt oder weicht von seinem Hash ab - es wurde kein Auflöser "
                "gebaut. Erst 'python -m photosort.place_dataset' laufen lassen. Die Zahlen "
                "dieses Kandidaten fehlen, sie sind nicht null."
            ),
        )
    else:
        candidate = measure_candidate(
            "Lokaler Ortsdatensatz (GeoNames)", probe, await resolve_all(resolver, cells)
        )

    return render_report(probe, [candidate], show_names=show_names)


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
                show_names=args.namen,
            )
        )
    except (PlaceProbeError, PlaceDatasetError) as exc:
        # BEIDE Abbruchgruende sehen fuer den Aufrufer gleich aus: der Messlauf hat nicht
        # stattgefunden, und warum, steht in der Meldung. Ein fehlender Ortsdatensatz ist hier
        # ausdruecklich KEIN leeres Messergebnis.
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
