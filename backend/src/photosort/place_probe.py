"""REIN LESENDES Messkommando: misst an einem echten Projekt, was eine Ortsauskunft ueberhaupt
hergaebe - BEVOR die Wegwahl faellt.

Aufruf::

    docker compose exec -T backend python -m photosort.place_probe --project-id 3

Die Wegwahl (lokaler Ortsdatensatz oder externer Dienst) ist eine Entscheidung Daniels und kann
nicht vorweggenommen werden. Beide Kandidaten stehen hier deshalb in bewusst WEGWERFBARER Form:
die Messung darf die Abhaengigkeit nicht vorwegnehmen, deren Anschaffung sie erst begruenden soll.
Faellt die Messung duerftig aus, ist das ein Ergebnis und keine Vorstufe.

REIN LESEND, und das ist eine gepruefte Zusage, keine Absicht: kein ``INSERT``/``UPDATE``/
``DELETE``, kein Aufrufpfad aus ``main.py``/``worker.py``, kein Endpunkt, kein
Compose-``command``. Kein Lauf hinterlaesst eine geaenderte, geloeschte oder neue Zeile.
``tests/test_place_probe.py`` haelt das dreifach fest - Import-Graph, Syntaxbaum-Waechter gegen
jede Schreibform und ein echter ``main()``-Lauf mit Schnappschuss jeder Tabelle davor und danach.
Kein Teil traegt allein.

WARUM DIESES MODUL TROTZDEM IM PRODUKTIV-PAKET LIEGT: Es braucht die echten SQLAlchemy-Modelle und
dieselbe Zellbildung wie die Anwendung (``places.place_cell``) - ein zweites Abbild davon
verfehlte genau die Frage, die gemessen werden soll.

SICHERHEIT - der Messlauf ist der ERSTE tatsaechliche Abfluss, nicht seine Vorstufe:

* Der externe Kandidat laeuft nur bei gesetztem ``EXTERNAL_PLACE_LOOKUP_ENABLED`` und MELDET SEIN
  AUSBLEIBEN in der Ausgabe, statt eine leere Spalte zu zeigen, die als schlechtes Messergebnis
  gelesen wuerde.
* Gefragt wird ueber die MENGE der verschiedenen Zellen, nie je Event - sonst ginge die
  Verweildauer je Ort mit hinaus - und ausschliesslich ueber die TATSAECHLICH BESUCHTEN Zellen aus
  dem Projektbestand. Dieses Kommando erzeugt keine Zelle und rastert kein Rechteck ab; eine
  flaechendeckende Sammlung risse die Grenze der OSM-Geocoding-Guideline ("systematic attempt to
  aggregate ... within a geographic area city-sized or larger").
* Die Vorgabe-Ausgabe traegt KEINE Koordinate, KEINEN aufgeloesten Ortsnamen und keinen
  OpenCloud-Pfad - nur Kennzahlen und die Projekt-Id. Namensbeispiele stehen ausschliesslich im
  abschaltbaren ``--namen``-Abschnitt.
* LOGGING: Dieses Modul schreibt kein Log. Eine kuenftige Logzeile traegt weder eine Koordinate
  noch einen Ortsnamen - weder einen angenommenen noch einen verworfenen.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.cloud_vision import CloudRequestThrottle
from photosort.config import settings
from photosort.db import make_engine, make_session_factory
from photosort.geonames import GeoNamesResolver, PlaceDatasetError
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoRanking,
    Project,
    ScanStatus,
)
from photosort.places import (
    PLACE_CELL_DIGITS,
    PlaceAnswer,
    PlaceInfo,
    PlaceResolver,
    place_cell,
    sanitize_place_name,
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

    `cells` sind die verschiedenen gerundeten GEMESSENEN Zellen seiner Fotos, sortiert und
    dublettenfrei - dieselbe Menge, aus der `events.py::_place_of` seine Stufenentscheidung
    bildet."""

    position: int
    landmark_name: str | None
    place_kind: str | None
    cells: tuple[Cell, ...]


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


# Der geschlossene Vorrat der Ausfallgruende. FESTE TOKEN, nie ein Fremdtext: weder ein
# Statuswert noch eine Fehlermeldung des Dienstes und erst recht keine Zelle geraet darueber in
# die Ausgabe (S5/S11).
FAILURE_HTTP_STATUS = "http-status"
FAILURE_TRANSPORT = "transport"
FAILURE_TOO_LARGE = "zu-gross"
FAILURE_UNREADABLE = "unlesbar"
FAILURE_REASONS = (
    FAILURE_HTTP_STATUS,
    FAILURE_TRANSPORT,
    FAILURE_TOO_LARGE,
    FAILURE_UNREADABLE,
)


@dataclass(frozen=True)
class ProbeTally:
    """Die Nebenbefunde EINES Kandidaten-Durchgangs, die in der Antwort selbst nicht stehen.

    `seen_levels` sind die roh gesehenen Ebenenangaben der Quelle, `failures` die Ausfaelle je
    Grund aus `FAILURE_REASONS`.

    Frozen, aber die beiden Abbildungen darin sind veraenderlich: der Aufrufer legt sie an, der
    Auflöser fuellt sie waehrend des Durchgangs. Ein Rueckkanal neben dem Rueckgabewert ist noetig,
    weil `PlaceResolver.resolve` bewusst nur "Antwort oder nichts" kennt - diese Schmalheit ist
    eine Sicherheitszusage (S2) und wird hier nicht aufgeweicht."""

    seen_levels: dict[str, int]
    failures: dict[str, int]

    @property
    def failed_requests(self) -> int:
        return sum(self.failures.values())

    def record_failure(self, reason: str) -> None:
        self.failures[reason] = self.failures.get(reason, 0) + 1


def new_tally() -> ProbeTally:
    return ProbeTally(seen_levels={}, failures={})


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
        size = len(event.cells)
        per_event[size] = per_event.get(size, 0) + 1
    return CellCounts(
        distinct_cells=len(set(probe.photo_cells)),
        cells_per_event=per_event,
        max_cells_in_one_event=max((len(e.cells) for e in probe.events), default=0),
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


def _the_one_of(values: Iterable[str | None]) -> str | None:
    """Der EINE verschiedene Wert einer Menge, oder `None` bei null oder mehreren.

    Werte `None` zaehlen ausdruecklich nicht mit: ein Event aus zwei Zellen, von denen nur eine
    einen Namen liefert, traegt diesen Namen."""
    distinct = {value for value in values if value is not None}
    if len(distinct) != 1:
        return None
    return distinct.pop()


def _place_name_of(event: ProbeEvent, info_by_cell: Mapping[Cell, PlaceInfo]) -> str | None:
    """Der Ortsname, den DIESES Event bekaeme - ohne Viertel, das entscheidet erst der Lauf.

    Ein Event mit Sehenswuerdigkeit bekommt KEINEN: der Ortsname ersetzt sie nicht und tritt
    nicht daneben."""
    if event.landmark_name is not None:
        return None
    return _the_one_of(usable_locality(info_by_cell.get(cell)) for cell in event.cells)


def _district_of(event: ProbeEvent, info_by_cell: Mapping[Cell, PlaceInfo]) -> str | None:
    """Das eine Viertel ueber die Zellen dieses Events. Liefern sie zwei verschiedene, keines."""
    return _the_one_of(
        info.neighbourhood
        for cell in event.cells
        if (info := info_by_cell.get(cell)) is not None and usable_locality(info) is not None
    )


def heading_counts(probe: ProbeInput, info_by_cell: Mapping[Cell, PlaceInfo]) -> HeadingCounts:
    """Block D. Bildet die Vergabe aus Spec 0434 nach, ZAEHLEND statt schreibend.

    Ein Event mit Sehenswuerdigkeit zaehlt bei der Gleichnamigkeitspruefung NICHT mit: es traegt
    keinen Ortsnamen und loest deshalb auch bei keinem anderen Event die Viertel-Ergaenzung aus."""
    names = [_place_name_of(event, info_by_cell) for event in probe.events]
    occurrences: dict[str, int] = {}
    for name in names:
        if name is not None:
            occurrences[name] = occurrences.get(name, 0) + 1

    shared = 0
    distinguishable = 0
    for event, name in zip(probe.events, names, strict=True):
        if name is None or occurrences[name] < 2:
            continue
        shared += 1
        if _district_of(event, info_by_cell) is not None:
            distinguishable += 1

    with_landmark = sum(1 for event in probe.events if event.landmark_name is not None)
    named = sum(1 for name in names if name is not None)
    return HeadingCounts(
        events_with_landmark=with_landmark,
        events_named=named,
        events_keeping_position=len(probe.events) - with_landmark - named,
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
            cells=tuple(sorted(set(grouped.get(event_id, ())))),
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


# --- Kandidat 2: der externe Dienst (Photon), bewusst WEGWERFBAR --------------------------------

# Der Ziel-Host ist eine KONSTANTE, nie ein Wert aus Datenbank, Parameter oder Request - kein
# SSRF-Pfad. Photon laeuft auf OSM-Daten (Apache-2.0, Selbst-Hosting als Ausweg).
PHOTON_REVERSE_URL = "https://photon.komoot.io/reverse"

# Zeitgrenze je Anfrage: eine haengende Fremdantwort haelt sonst den ganzen Messlauf an.
PHOTON_REQUEST_TIMEOUT_SECONDS = 10.0

# Mindestabstand zwischen zwei Anfragen. BEGRUENDETE SELBSTAUFLAGE, aus keiner Quelle ableitbar:
# Photon nennt keine Ratenzahl, nur "please be fair, extensive usage will be throttled". Eine
# Sekunde ist die vorsichtige Setzung fuer eine erklaerte Demo-Instanz.
PHOTON_MIN_REQUEST_INTERVAL_SECONDS = 1.0

# Die Antwort wird BEGRENZT gelesen: eine unerwartet grosse Fremdantwort soll den Messlauf nicht
# in den Speicher laufen lassen. Eine Reverse-Antwort mit einem Treffer misst wenige Kilobyte.
PHOTON_MAX_RESPONSE_BYTES = 256 * 1024

# Photons Ebenenangabe steht in der Antwort im Feld `type` (nicht in `layer` - das ist
# ausschliesslich ein Filter-Parameter der ANFRAGE und kommt in der Antwort nicht vor).
#
# ACHTUNG, NAMENSKOLLISION: Photons `locality` ist NICHT unser `locality`. Photon staffelt
# `locality` ⊂ `district` ⊂ `city` ("Ritterkiez" ⊂ "Kreuzberg" ⊂ "Berlin"); unser `locality` ist
# der ORT und entspricht Photons `city`, unser `neighbourhood` entspricht Photons `district`.
# Wer Photons `locality` direkt uebernimmt, setzt systematisch die falsche Ebene als Ueberschrift.
#
# `house`/`street`/`locality` sind FEINER als jede Ebene, die dieses Projekt fuehrt, und werden
# deshalb auf `neighbourhood` abgebildet - nicht auf "keine Ebene". Die Begruendung des
# Regions-Ausschlusses traegt hier ausdruecklich NICHT: ein Regionstreffer nennt oft eine Stadt,
# die Dutzende Kilometer entfernt liegt, ein Haustreffer nennt genau die richtige. Ein Abbilden
# auf "keine Ebene" wiese die Messung systematisch zu duerftig aus und traege damit eine nicht
# ruecknehmbare Wegwahl. Die tatsaechlich gesehenen `type`-Werte weist Block C zusaetzlich roh
# aus, damit diese Zuordnung am Messergebnis nachprüfbar bleibt statt geglaubt werden zu muessen.
_PHOTON_TYPE_TO_LEVEL = {
    "house": "neighbourhood",
    "street": "neighbourhood",
    "locality": "neighbourhood",
    "district": "neighbourhood",
    "city": "locality",
    "county": "region",
    "state": "region",
    "country": "country",
}


def photon_answer(payload: object, seen_levels: dict[str, int] | None = None) -> PlaceAnswer | None:
    """Der Parser-Rand des externen Wegs - rein, ohne Netz, gegen eine FREMDE Struktur.

    Gelesen werden ausschliesslich die vier Stufen und die Ebenenangabe. Strasse, Hausnummer,
    Postleitzahl und Photons `locality` werden HIER verworfen und erreichen kein Feld: es gibt
    keinen offenen Beutel, in dem sie doch ankaemen."""
    if not isinstance(payload, dict):
        return None
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        return None
    first = features[0]
    if not isinstance(first, dict):
        return None
    properties = first.get("properties")
    if not isinstance(properties, dict):
        return None

    raw_level = properties.get("type")
    if seen_levels is not None and isinstance(raw_level, str):
        seen_levels[raw_level] = seen_levels.get(raw_level, 0) + 1
    level = _PHOTON_TYPE_TO_LEVEL.get(raw_level) if isinstance(raw_level, str) else None

    return PlaceAnswer(
        neighbourhood=sanitize_place_name(properties.get("district")),
        locality=sanitize_place_name(properties.get("city")),
        region=sanitize_place_name(properties.get("state")),
        country=sanitize_place_name(properties.get("country")),
        matched_level=level,
    )


class PhotonResolver:
    """Der externe Kandidat. Gebaut wird er NUR bei gesetztem `EXTERNAL_PLACE_LOOKUP_ENABLED`."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        throttle: CloudRequestThrottle,
        tally: ProbeTally,
    ) -> None:
        self._client = client
        self._throttle = throttle
        self._tally = tally

    async def resolve(self, cell: Cell) -> PlaceAnswer | None:
        await self._throttle.acquire()
        lat, lon = cell
        # ZWEITE, UNABHAENGIGE SCHRANKE AM AUSGEHENDEN RAND (S2): beide Zahlen werden mit genau
        # `PLACE_CELL_DIGITS` Nachkommastellen formatiert. Eine ungerundete Zahl ist in der
        # abgesetzten Zeichenkette damit nicht darstellbar, selbst wenn sie hierher gelangte -
        # das Akzeptanzkriterium haengt an diesem Rand, nicht an einer Aufrufstelle.
        params = {
            "lat": f"{lat:.{PLACE_CELL_DIGITS}f}",
            "lon": f"{lon:.{PLACE_CELL_DIGITS}f}",
            "limit": "1",
        }
        body = bytearray()
        try:
            async with self._client.stream(
                "GET",
                PHOTON_REVERSE_URL,
                params=params,
                timeout=PHOTON_REQUEST_TIMEOUT_SECONDS,
            ) as response:
                # JEDER dieser vier Ausgaenge heisst "es kam keine verwertbare Antwort" und wird
                # als AUSFALL vermerkt - ausdruecklich nicht als "nichts gefunden". Eine
                # Drosselung der Dienst-Instanz (sie nennt keine Ratenzahl) saehe sonst in der
                # Messung aus wie ein schlechter Anbieter.
                if response.status_code != httpx.codes.OK:
                    self._tally.record_failure(FAILURE_HTTP_STATUS)
                    return None
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > PHOTON_MAX_RESPONSE_BYTES:
                        self._tally.record_failure(FAILURE_TOO_LARGE)
                        return None
        except httpx.HTTPError:
            # KEINE ANTWORT ist etwas anderes als eine Antwort ohne brauchbare Ebene: eine
            # voruebergehende Stoerung darf die Zelle nicht dauerhaft vergiften.
            self._tally.record_failure(FAILURE_TRANSPORT)
            return None
        try:
            payload = json.loads(bytes(body))
        except ValueError:
            self._tally.record_failure(FAILURE_UNREADABLE)
            return None
        # Ab hier HAT der Dienst geantwortet: ein `None` von `photon_answer` ist ein Nichttreffer
        # und damit ein Messergebnis, kein Ausfall.
        return photon_answer(payload, self._tally.seen_levels)


def build_photon_resolver(tally: ProbeTally) -> PlaceResolver:
    """Die echte Fabrik - baut einen Client gegen das echte Netz.

    Sie wird NUR bei gesetztem Schalter aufgerufen; kein automatisierter Test ruft sie je auf
    (die Netzsperre in `tests/conftest.py` machte das laut)."""
    return PhotonResolver(
        httpx.AsyncClient(),
        CloudRequestThrottle(min_interval_seconds=PHOTON_MIN_REQUEST_INTERVAL_SECONDS),
        tally,
    )


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
    tally: ProbeTally | None = None
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
    tally: ProbeTally | None = None,
) -> CandidateResult:
    """Die Bloecke C, D und E fuer einen Kandidaten.

    `examples` traegt die aufgeloesten Namen - sie erscheinen NUR im `--namen`-Abschnitt. `tally`
    fehlt bei einem Kandidaten, der keinen Ausfallbegriff kennt (der lokale Datensatz)."""
    infos = _info_by_cell(answers)
    resolved = sorted(
        {locality for info in infos.values() if (locality := usable_locality(info)) is not None}
    )
    return CandidateResult(
        name=name,
        levels=level_counts(answers, tally.failures if tally is not None else None),
        headings=heading_counts(probe, infos),
        photos=photo_counts(probe, infos),
        tally=tally,
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
        if candidate.tally is not None:
            failed = candidate.tally.failed_requests
            lines.append(
                f"- AUSFALL (gar keine verwertbare Antwort): {failed} "
                f"({_percent(failed, levels.cells_total)})"
            )
            if failed:
                lines += [
                    "  - "
                    + ", ".join(
                        f"{reason}: {count}"
                        for reason, count in sorted(candidate.tally.failures.items())
                    ),
                    "  ACHTUNG: Diese Zellen sind NICHT gemessen - sie sagen nichts ueber die",
                    "  Quelle aus. Ein nennenswerter Ausfall (Drosselung, Stoerung) macht die",
                    "  Zahlen dieses Kandidaten unbrauchbar; dann erst die Ursache beheben und",
                    "  neu messen, nicht auf dieser Grundlage entscheiden.",
                ]
            if candidate.tally.seen_levels:
                lines.append(
                    "- rohe Ebenenangaben der Quelle: "
                    + ", ".join(
                        f"{key}: {count}"
                        for key, count in sorted(candidate.tally.seen_levels.items())
                    )
                )
        lines += [
            "",
            "### D - Verwendung Ueberschrift (zaehlt EVENTS)",
            "",
            f"- Events mit Sehenswuerdigkeit (unveraendert): {headings.events_with_landmark}",
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
            "Pfad auf die entpackte GeoNames-Datei (scripts/fetch-ortsdatensatz.sh). Ohne diese "
            "Angabe bleibt der lokale Kandidat ungemessen und sagt das in der Ausgabe."
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
    dataset_path: Path | None,
    show_names: bool,
    external_enabled: bool,
    build_external_resolver: Callable[[ProbeTally], PlaceResolver],
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
    candidates: list[CandidateResult] = []

    if dataset_path is None:
        candidates.append(
            CandidateResult(
                name="Lokaler Ortsdatensatz (GeoNames)",
                absent_reason=(
                    "kein --ortsdatensatz angegeben. Die Zahlen dieses Kandidaten fehlen, sie "
                    "sind nicht null."
                ),
            )
        )
    else:
        local = GeoNamesResolver(dataset_path, cells)
        candidates.append(
            measure_candidate(
                "Lokaler Ortsdatensatz (GeoNames)", probe, await resolve_all(local, cells)
            )
        )

    if not external_enabled:
        candidates.append(
            CandidateResult(
                name="Externer Dienst (Photon)",
                absent_reason=(
                    "EXTERNAL_PLACE_LOOKUP_ENABLED steht auf false - es wurde kein Auflöser "
                    "gebaut und keine Anfrage abgesetzt. Die Zahlen dieses Kandidaten fehlen, "
                    "sie sind nicht null."
                ),
            )
        )
    else:
        tally = new_tally()
        external = build_external_resolver(tally)
        candidates.append(
            measure_candidate(
                "Externer Dienst (Photon)",
                probe,
                await resolve_all(external, cells),
                tally,
            )
        )

    return render_report(probe, candidates, show_names=show_names)


def main(
    argv: Sequence[str] | None = None,
    *,
    database_url: str | None = None,
    external_lookup_enabled: bool | None = None,
    build_external_resolver: Callable[[ProbeTally], PlaceResolver] = build_photon_resolver,
) -> int:
    """Verdrahtung + Exit-Code. `argv`, `database_url`, der Schalter und die externe Fabrik sind
    injizierbar - kein `sys.argv`-Zugriff im Testpfad, kein unbeabsichtigter Zugriff auf die
    konfigurierte Anwendungs-Datenbank und kein Client-Bau im Test.

    `asyncio.run` laeuft INNERHALB von main(): eine Async-Engine ueberlebt keinen Loop-Wechsel."""
    args = _build_parser().parse_args(argv)
    enabled = (
        settings.external_place_lookup_enabled
        if external_lookup_enabled is None
        else external_lookup_enabled
    )
    try:
        report = asyncio.run(
            _probe_with_own_session(
                database_url or settings.database_url,
                project_id=args.project_id,
                dataset_path=Path(args.ortsdatensatz) if args.ortsdatensatz else None,
                show_names=args.namen,
                external_enabled=enabled,
                build_external_resolver=build_external_resolver,
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
