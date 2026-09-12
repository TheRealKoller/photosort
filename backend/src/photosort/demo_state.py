"""Schreibendes CLI: legt einen deterministischen Demo-Datenbestand fuer die browsergestuetzte
Oberflaechenpruefung an.

Aufruf::

    docker compose -f docker-compose.yml -f docker-compose.e2e.yml \\
        exec -T backend python -m photosort.demo_state

Vier Projekte mit dem festen Namenspraefix ``Demo — `` decken die vier prueflohnenden Zustaende ab
(leer, grosse Sammlung, bewertet, Fehlerzustand). Die Bilddateien entstehen synthetisch mit Pillow
und werden ueber die ECHTE ``thumbnails.py``-Logik in den lokalen Cache geschrieben - kein zweites
Abbild von Datenmodell oder Cache-Schluessel, das bei einer Modelaenderung still abdriften
koennte.

WARUM DIESES MODUL IM PRODUKTIV-PAKET LIEGT UND TROTZDEM UNGEFAEHRLICH IST: Es braucht die echten
SQLAlchemy-Modelle und die echte Cache-Schluessel-Bildung, liegt damit im Produktiv-Image - und ist
bewusst destruktiv (es loescht seine eigenen Demo-Projekte, bevor es sie neu anlegt). Drei
Eigenschaften halten das zusammen:

* **Dreiteilige, fail-closed Sperre (M1)**, vollstaendig ausgewertet VOR dem ersten Schreibzugriff:
  eine Umgebungsvariable mit exaktem Literalwert, kein Projekt ohne Demo-Praefix in der Datenbank,
  und eine OpenCloud-Basis-URL, die leer ist oder auf einen bekannten Demo-Host zeigt. Die dritte
  Bedingung ist die einzige, die auf einer frisch aufgesetzten Produktivinstanz mit LEERER
  Datenbank noch greift - dort ist die zweite leer erfuellt.
* **Geloescht wird nur, was dieses Modul selbst angelegt hat (M2):** zeilenweise entlang der
  eigenen Demo-Projekte, im Thumbnail-Cache ausschliesslich ueber die aus den eigenen
  ``(photo_id, etag)``-Paaren BERECHNETEN Pfade. Kein ``glob``, kein ``rmtree`` - die
  Cache-Dateinamen sind flache Hash-Schluessel ohne Projektzuordnung, bei einem geteilten Volume
  traefe ein Glob echte Familien-Thumbnails.
* **Kein Aufrufpfad aus der laufenden Anwendung (M3):** kein Import aus ``main.py``/``worker.py``,
  kein Endpunkt, kein Compose-``command``. Ein Test haelt das ueber den Import-Graphen fest.

Fehlermeldungen nennen nur Bedingung und Status, nie Konfigurationswerte (M2).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import random
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.categories import CATEGORY_REGISTRY, secondary_categories
from photosort.cloud_vision import default_vision_model_for_provider
from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY
from photosort.db import make_engine, make_session_factory
from photosort.models import (
    ClassificationPhase,
    CloudVisionPhase,
    CriterionScoringRun,
    Event,
    Photo,
    PhotoCategoryClassification,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.project_deletion import collect_photo_cache_keys, delete_projects
from photosort.thumbnails import (
    delete_cached_variants,
    generate_variants,
)

# --- Namen, Konstanten, Sperr-Literale -------------------------------------------------------

# Der Praefix ist der Anker der gesamten Sperre: exakt so, mit Geviertstrich und beidseitigem
# Leerzeichen. Eine lockere Pruefung ("startswith('Demo')") wuerde ein reales Projekt
# "Demolition Sommer 2019" freigeben und loeschen (Edge Case E9 der Spec).
DEMO_PROJECT_PREFIX = "Demo — "

EMPTY_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Leeres Projekt"
LARGE_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Große Sammlung"
RATED_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Bewertet"
ERROR_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Fehlerzustand"

# Umgebungsvariable + exakter Satz-Literal (M1a). Bewusst KEIN "gesetzt"/truthy-Test: `1`/`true`
# setzt man versehentlich, einen Satz wie diesen nicht.
CONFIRM_ENV_VAR = "PHOTOSORT_DEMO_STATE_CONFIRM"
CONFIRM_LITERAL = "yes-wipe-and-seed-demo-data"

# Fotoanzahl der grossen Sammlung. Vorgabe der Spec: Band 60-80 - genug fuer Scrollen und
# Listendichte, bewusst keine Performance-Groessenordnung. Die Tests fahren diese Groesse genau
# EINMAL; alle uebrigen Testfaelle uebergeben eine kleine Anzahl (Edge Case E6).
LARGE_COLLECTION_PHOTO_COUNT = 72

# Fotoanzahl des Fehlerzustands-Projekts - klein, aber gross genug, dass ein Foto ohne
# Cache-Datei ("wird noch verarbeitet"-Platzhalter) neben normal dargestellten Fotos auffaellt.
ERROR_STATE_PHOTO_COUNT = 6

# Hostnamen, die als "eindeutig lokal/Demo" gelten (M1c). Muster inklusive Port-Pflicht aus
# scripts/seed-opencloud-demo.py::validate_demo_base_url - dort als Copilot-Review-Fund ergaenzt,
# weil "http://localhost" (impliziter Port 80) sonst einen ganz anderen lokalen Dienst treffen
# koennte. Bewusst nachgebaut statt importiert: scripts/ ist ein eigenstaendiges Python-Paket und
# im Backend-Image nicht installiert.
_DEMO_HOSTS = frozenset({"opencloud-demo", "localhost", "127.0.0.1", "::1"})

# Bilderzeugung: fester Zufallskeim, feste Groesse, feste JPEG-Qualitaet - zwei Laeufe liefern
# byte-identische Dateien (per Test belegt, nicht behauptet).
_IMAGE_SEED = "photosort-demo-state-v1"
_IMAGE_SIZE = (960, 720)
_IMAGE_JPEG_QUALITY = 90

# Feste Zeit-Anker: alle Zeitstempel sind deterministisch daraus abgeleitet, damit Sortierung,
# Zeit-Cluster und angezeigte Daten zwischen zwei Laeufen identisch bleiben. Naiv/UTC wie im
# uebrigen Backend (worker.py: `datetime.now(UTC).replace(tzinfo=None)`).
_BASE_TAKEN_AT = datetime(2024, 5, 1, 9, 0, 0)
_BASE_SCAN_AT = datetime(2024, 6, 1, 10, 0, 0)
_BASE_SCORING_AT = datetime(2024, 6, 1, 11, 0, 0)

# Das Foto des bewerteten Projekts, das einen OFFENEN Ausschuss-Vorschlag traegt: bewusst hinter
# den drei bewerteten Fotos, damit es garantiert keine Bewertung hat (ein bewerteter Vorschlag
# waere bereits entschieden und zeigte den Zustand nicht mehr).
_OPEN_SUGGESTION_INDEX = 3

# Zwei Fotos des bewerteten Projekts tragen eine ABSICHTLICH gesetzte Konfidenz-Sonderform, damit
# beide leicht falsch gebauten Faelle im Browser tatsaechlich sichtbar sind.
#
#   _CONFIDENCE_GAP_INDEX  - gar keine Angabe (beide Spalten `NULL`): die Luecke IST die
#                            Darstellung, es darf dort kein Platzhalter und kein "0 %" stehen.
#   _LOW_CONFIDENCE_INDEX  - eine Angabe ECHT unter der Kuratierungsschwelle von 60 %, damit der
#                            Filter "Nur unsichere Zuordnungen" in der Demo nicht leer laeuft.
#
# Bewusst zwei VERSCHIEDENE Fotos und beide ausserhalb von `_OPEN_SUGGESTION_INDEX`, damit sich
# die Sonderfaelle nicht gegenseitig verdecken.
_CONFIDENCE_GAP_INDEX = 0
_LOW_CONFIDENCE_INDEX = 1

# Faktor, mit dem der deterministische Basiswert fuer `_LOW_CONFIDENCE_INDEX` in die untere
# Bandhaelfte gezogen wird: `_deterministic_unit_value` liefert [0.05, 0.98], halbiert also
# hoechstens 0.49 - garantiert unter 0.6, ohne den Wert fest zu verdrahten.
_LOW_CONFIDENCE_FACTOR = 0.5

# FESTE Zusatzkonfidenzen fuer drei Fotos des bewerteten Projekts, damit die Mehrfachzugehoerigkeit
# in `browse-app` und im e2e-Prueflauf tatsaechlich zu sehen ist. Bewusst literale Zahlen statt des
# deterministischen Zufallswerts: die Faelle sollen an der Schwelle nicht kippen, wenn sich der
# Generator aendert.
#
#   Index 4  - ein Foto mit ZWEI Zugehoerigkeiten (Haupt + eine Nebenkategorie); `tier` gehoert
#              Foto 1, das im selben Cluster liegt - die Partition zeigt damit zwei Fotos.
#   Index 5  - ein Foto mit DREI Zugehoerigkeiten (Haupt + zwei Nebenkategorien).
#   Index 6  - das Foto mit Override UND Nebenkategorien: hier stehen beide Ecken-Marker
#              nebeneinander auf derselben Kachel (Marker-Kollision, UI/UX-Abschnitt der Spec).
#              Seine automatische Kategorie (`essen_trinken`) traegt eine Zahl ueber der Schwelle
#              und wird nach dem Uebersteuern zur Nebenkategorie - das Foto verschwindet also
#              nicht aus der Kategorie, aus der es umgehaengt wurde.
#
# Alle uebrigen Fotos behalten GENAU EINE Zugehoerigkeit - der haeufigste Fall muss in der Demo
# der haeufigste bleiben. Index 0 (`_CONFIDENCE_GAP_INDEX`) traegt weiterhin gar keine Angabe und
# bekommt daher auch keine Nebenkategorie.
_DEMO_EXTRA_CONFIDENCES: dict[int, dict[str, float]] = {
    4: {"tier": 0.86},
    5: {"menschen": 0.91, "essen_trinken": 0.74},
    6: {"menschen": 0.88, "essen_trinken": 0.93},
}

# Das Foto mit dem manuellen Override (Index 6, automatisch `essen_trinken`).
_DEMO_OVERRIDE_INDEX = 6
_DEMO_OVERRIDE_CATEGORY_KEY = "kunst_kreatives"

# Reihenfolge, in der die drei Bewertungsstatus auf die ersten Fotos des bewerteten Projekts
# verteilt werden - ueber das Enum gebildet, damit ein vierter Status nicht stillschweigend
# unbewertet bliebe.
_RATED_STATUS_ORDER = tuple(RatingStatus)

# Das Foto des Fehlerzustands-Projekts, das eine Cloud-Vision-Fehlerzeile traegt (nicht dasselbe
# wie das Foto ohne Cache-Datei - die Oberflaeche soll beide Fehlerbilder nebeneinander zeigen).
_CLOUD_VISION_ERROR_INDEX = 1

# Die Cloud-Bilanz des "bewertet"-Zustands.
#
# SAEMTLICHE Werte hier sind FREI ERFUNDEN und stammen aus keinem echten Lauf (nur synthetische
# Demo-Daten). Das ist keine Formalie: die Bilanz zeigt einen GELDBETRAG an der Ausloese-Stelle, und
# Screenshots aus dem Pruefstack landen als PR-Anhaenge in einem oeffentlichen Repository. Ein
# echter Betrag waere damit Ausgabeninformation der Familie in der Oeffentlichkeit.
#
# Gewaehlt so, dass die Oberflaeche etwas Sinnvolles zu zeigen hat: beide Cloud-Teilschritte mit
# Betraegen deutlich ueber der "< 0,01 USD"-Schwelle, ein Fehlschlag in der Remote-Phase (damit
# die Fehlschlag-Zeile der Bilanz nicht leer bleibt) und eine Startschaetzung, die von der Summe
# der Ist-Betraege ABWEICHT - sonst waere die geforderte Einordnung "Ist gegen Schaetzung" im
# Demo-Zustand gar nicht ablesbar.
_DEMO_REMOTE_INPUT_TOKENS = 21_400
_DEMO_REMOTE_OUTPUT_TOKENS = 1_820
_DEMO_REMOTE_COST_USD = 0.34
_DEMO_LANDMARK_PHOTOS_TOTAL = 4
_DEMO_LANDMARK_INPUT_TOKENS = 6_200
_DEMO_LANDMARK_OUTPUT_TOKENS = 540
_DEMO_LANDMARK_COST_USD = 0.11
_DEMO_ESTIMATED_COST_USD = 0.52

# Der "bewertet"-Zustand muss ALLE VIER Anzeigezustaende der Event-Ueberschrift hergeben -
# Sehenswuerdigkeit, eine Koordinate, mehrere Orte und gar kein Ort. Sonst ist die Sichtpruefung
# ueber den `browse-app`-Skill fuer drei davon blind, und sie ist die einzige nicht automatisierte
# Kontrollinstanz dieses Features. Genau eines der vier traegt einen Namen, drei tragen keinen.
#
# Die Fotos fallen in ZUSAMMENHAENGENDE Bloecke statt im Wechsel (`index % 4`): Events eines Laufs
# sind ueberschneidungsfrei, und `demo_taken_at` waechst streng mit dem Index. Ein Reissverschluss
# erzeugte einen Zustand, den die Anwendung selbst nie schriebe.
_DEMO_EVENT_COUNT = 4
_DEMO_LANDMARK_EVENT = 0
_DEMO_SINGLE_COORDINATE_EVENT = 1
_DEMO_MULTIPLE_PLACES_EVENT = 2
_DEMO_NO_LOCATION_EVENT = 3
# Das Foto, an dem die eine Sehenswuerdigkeit-Zeile haengt - das erste des Landmark-Events.
_DEMO_LANDMARK_PHOTO_INDEX = 0

# Frei erfundene, aber plausible Koordinaten rund um den Eiffelturm (ausschliesslich synthetische
# Demo-Daten - das Repository ist oeffentlich, und Standortdaten der Familie duerfen es nie
# erreichen).
_DEMO_BASE_LAT = 48.8583
_DEMO_BASE_LON = 2.2945
# Streuung INNERHALB einer 2-Nachkommastellen-Zelle (~1,1 km): alle Fotos eines Clusters fallen auf
# dieselbe gerundete Stelle -> `kind="coordinate"`.
_DEMO_SAME_CELL_STEP = 0.0001
# Streuung ueber Zellgrenzen hinweg -> `kind="multiple"`.
_DEMO_OTHER_CELL_STEP = 0.02

_DEMO_LANDMARK_NAME = "Eiffelturm"
_DEMO_LANDMARK_CONFIDENCE = 0.91


def _demo_event_index(index: int, photo_count: int) -> int:
    """Das Event des Demo-Fotos `index` - zusammenhaengende Bloecke ueber die nach `taken_at`
    aufsteigende Fotoliste, damit die vier Events ueberschneidungsfrei aufeinanderfolgen."""
    return min(index * _DEMO_EVENT_COUNT // photo_count, _DEMO_EVENT_COUNT - 1)


def _demo_event_offset(index: int, photo_count: int) -> int:
    """Der Platz des Fotos INNERHALB seines Events, 0-basiert.

    Die Streuung rechnet gegen diesen Offset, nicht gegen den Gesamtindex: sonst waechst der
    Abstand zur Basiskoordinate ueber die Events hinweg weiter, und das "eine Zelle"-Event faellt
    ab einem bestimmten Index still ueber eine Zellgrenze."""
    own_event = _demo_event_index(index, photo_count)
    first = next(i for i in range(photo_count) if _demo_event_index(i, photo_count) == own_event)
    return index - first


def _demo_gps(index: int, photo_count: int) -> tuple[float, float] | None:
    """Die Koordinate des Demo-Fotos `index` - deterministisch, ohne Zufall, damit zwei
    Seeder-Laeufe byte-gleiche Werte liefern.

    Die Zuordnung folgt dem Event: das Landmark- und das Koordinaten-Event streuen INNERHALB einer
    gerundeten Zelle, das "Mehrere Orte"-Event ueber Zellgrenzen hinweg, und das vierte Event
    bekommt gar keine Koordinate. `None` heisst hier wie ueberall "kein Ort" - nie eine halbe
    Koordinate."""
    event_index = _demo_event_index(index, photo_count)
    if event_index == _DEMO_NO_LOCATION_EVENT:
        return None
    spread = (
        _DEMO_OTHER_CELL_STEP
        if event_index == _DEMO_MULTIPLE_PLACES_EVENT
        else _DEMO_SAME_CELL_STEP
    )
    step = _demo_event_offset(index, photo_count)
    return (
        round(_DEMO_BASE_LAT + spread * step, 6),
        round(_DEMO_BASE_LON + spread * step, 6),
    )


class DemoStateError(Exception):
    """Erwarteter, benutzerseitig behebbarer Abbruch (Sperre nicht erfuellt, DB nicht erreichbar).

    Wird in main() zu einer kurzen Meldung auf stderr und einem Exit-Code != 0. Der Text nennt nur
    Bedingung und Status, nie einen Konfigurationswert (M2) - ein durchgereichter Wert waere genau
    der Pfad, ueber den eine echte OPENCLOUD_BASE_URL oder ein Token in ein CI-Log geriete.
    """


# --- Reine Praedikate der dreiteiligen Sperre (M1) --------------------------------------------


def is_demo_project_name(name: str) -> bool:
    """Traegt der Projektname exakt den Demo-Praefix? Bewusst `startswith` auf dem VOLLSTAENDIGEN
    Praefix inklusive Geviertstrich und Leerzeichen, case-sensitiv."""
    return name.startswith(DEMO_PROJECT_PREFIX)


def check_confirmation(value: str | None) -> None:
    """Teil (a) der Sperre: die Umgebungsvariable traegt den exakten Literalwert.

    Kein `strip()`, kein Case-Insensitive-Vergleich, kein Truthy-Test - jede Aufweichung machte
    aus einer bewussten Freigabe wieder ein Versehen."""
    if value != CONFIRM_LITERAL:
        raise DemoStateError(
            f"Freigabe fehlt: {CONFIRM_ENV_VAR} muss exakt auf den vorgesehenen Freigabe-Satz "
            "gesetzt sein (siehe docs/setup.md). Abbruch, ohne etwas zu veraendern."
        )


def check_opencloud_target(base_url: str) -> None:
    """Teil (c) der Sperre: die konfigurierte OpenCloud-Basis-URL ist leer oder zeigt auf einen
    bekannten lokalen Demo-Host (mit explizit angegebenem Port).

    Diese Bedingung ist die einzige, die auf einer frisch aufgesetzten Produktivinstanz noch
    greift: dort ist die Datenbank leer, Teil (b) also leer erfuellt."""
    if base_url == "":
        return
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in _DEMO_HOSTS or parsed.port is None:
        raise DemoStateError(
            "Die konfigurierte OpenCloud-Basis-URL zeigt nicht auf eine lokale Demo-Instanz "
            "(erwartet: leer oder http://<lokaler Demo-Host>:<port>). Abbruch, ohne etwas zu "
            "veraendern - der Demo-Seeder darf nie neben einer echten OpenCloud-Anbindung laufen."
        )


# --- Reine Zustandsbeschreibung ---------------------------------------------------------------


@dataclass(frozen=True)
class DemoProjectSpec:
    """Beschreibung EINES Demo-Projekts, unabhaengig von Datenbank und Dateisystem.

    `uncached_photo_indices` sind die Fotos, fuer die bewusst KEINE Cache-Datei erzeugt wird - sie
    loesen im Frontend den "wird noch verarbeitet"-Platzhalter aus und sind Teil des
    Fehlerzustands, kein Versehen."""

    name: str
    slug: str
    photo_count: int
    uncached_photo_indices: tuple[int, ...] = ()


def demo_project_specs(
    *, large_collection_photo_count: int = LARGE_COLLECTION_PHOTO_COUNT
) -> tuple[DemoProjectSpec, ...]:
    """Die vier Zustaende in fester Reihenfolge.

    Die Fotoanzahl der grossen Sammlung ist ein Parameter mit der Produktionskonstante als Default
    (Edge Case E6): die Masse der Tests laeuft klein, genau ein Test faehrt die echte Groesse.
    Die Anzahl des bewerteten Projekts leitet sich dagegen aus dem festen Kategorien-Set ab - jedes
    Foto traegt genau einen Kategorie-Schluessel, damit ALLE Schluessel belegt sind, ohne dass
    irgendwo eine abgeschriebene Liste gepflegt werden muesste."""
    return (
        DemoProjectSpec(name=EMPTY_PROJECT_NAME, slug="leeres-projekt", photo_count=0),
        DemoProjectSpec(
            name=LARGE_PROJECT_NAME,
            slug="grosse-sammlung",
            photo_count=large_collection_photo_count,
        ),
        DemoProjectSpec(
            name=RATED_PROJECT_NAME, slug="bewertet", photo_count=len(CATEGORY_REGISTRY)
        ),
        DemoProjectSpec(
            name=ERROR_PROJECT_NAME,
            slug="fehlerzustand",
            photo_count=ERROR_STATE_PHOTO_COUNT,
            uncached_photo_indices=(0,),
        ),
    )


# --- Reine Erzeuger je Foto -------------------------------------------------------------------


def demo_etag(slug: str, index: int) -> str:
    """Deterministischer etag. Geht ueber `thumbnails.cache_key` in den Cache-Dateinamen ein."""
    return f"demo-{slug}-{index:04d}"


def demo_relative_path(slug: str, index: int) -> str:
    """Deterministischer, im Frontend sichtbarer Dateipfad innerhalb des Demo-Projekts."""
    return f"Demo/{slug}/foto-{index:04d}.jpg"


def demo_taken_at(index: int) -> datetime:
    """Aufnahmezeitpunkt, streng monoton mit dem Index. Naiv/UTC wie im uebrigen Backend
    (worker.py: `datetime.now(UTC).replace(tzinfo=None)`)."""
    return _BASE_TAKEN_AT + timedelta(minutes=17 * index)


def render_demo_image(*, slug: str, index: int) -> bytes:
    """Erzeugt ein synthetisches, erkennbar durchnummeriertes JPEG.

    Deterministisch: der Zufallskeim haengt ausschliesslich an `slug`/`index`, JPEG-Qualitaet und
    Bildgroesse sind Konstanten. Zwei Laeufe liefern byte-identische Dateien - ohne diese Zusage
    waere jeder darauf aufbauende E2E-Spec sprunghaft."""
    rng = random.Random(f"{_IMAGE_SEED}:{slug}:{index}")
    width, height = _IMAGE_SIZE
    background = (rng.randrange(24, 96), rng.randrange(24, 96), rng.randrange(40, 120))
    image = Image.new("RGB", _IMAGE_SIZE, background)
    draw = ImageDraw.Draw(image)

    # Ein paar grobe Formen, damit die Bilder im Grid unterscheidbar sind und die
    # Thumbnail-Skalierung etwas zu tun hat.
    for _ in range(6):
        x0 = rng.randrange(0, width)
        y0 = rng.randrange(0, height)
        x1 = min(width, x0 + rng.randrange(80, 360))
        y1 = min(height, y0 + rng.randrange(80, 360))
        fill = (rng.randrange(60, 240), rng.randrange(60, 240), rng.randrange(60, 240))
        draw.rectangle((x0, y0, x1, y1), fill=fill)

    label = f"{slug} #{index:04d}"
    font = ImageFont.load_default(size=64)
    draw.text((40, height - 120), label, fill=(255, 255, 255), font=font)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=_IMAGE_JPEG_QUALITY)
    return buffer.getvalue()


# --- Duenne DB-Schreibschicht -----------------------------------------------------------------


@dataclass(frozen=True)
class DemoStateSummary:
    """Ergebnis EINES Laufs - Grundlage der CLI-Ausgabe. Enthaelt nur Zaehlwerte und die eigenen
    Projektnamen, keine Konfigurationswerte."""

    project_names: tuple[str, ...]
    photo_count: int
    cache_file_count: int
    rated_user_count: int


async def load_demo_projects(session: AsyncSession) -> list[Project]:
    """Die eigenen Projekte, ausschliesslich ueber den exakten Praefix bestimmt."""
    projects = (await session.execute(select(Project).order_by(Project.id))).scalars().all()
    return [project for project in projects if is_demo_project_name(project.name)]


async def check_only_demo_projects(session: AsyncSession) -> None:
    """Teil (b) der Sperre: kein einziges Projekt ohne Demo-Praefix in der Datenbank.

    Eine LEERE Datenbank erfuellt die Bedingung (Edge Case E8) - der Erstlauf darf nicht daran
    scheitern, dass noch keine Demo-Projekte existieren. Gemeldet wird nur die Anzahl, nie ein
    Projektname: Projektnamen sind Familiendaten."""
    projects = (await session.execute(select(Project.name))).scalars().all()
    foreign = [name for name in projects if not is_demo_project_name(name)]
    if foreign:
        raise DemoStateError(
            f"Die Datenbank enthaelt {len(foreign)} Projekt(e) ohne den Demo-Praefix. Abbruch, "
            "ohne etwas zu veraendern - der Demo-Seeder laeuft nur gegen eine Datenbank, die "
            "ausschliesslich seine eigenen Demo-Projekte enthaelt."
        )


async def assert_safe_to_seed(
    session: AsyncSession, *, confirmation: str | None, opencloud_base_url: str
) -> None:
    """Die dreiteilige, fail-closed Sperre (M1), vollstaendig ausgewertet VOR dem ersten
    Schreibzugriff. Reihenfolge: die beiden reinen Bedingungen zuerst, danach die Datenbankfrage -
    ein fehlgeleiteter Aufruf soll gar nicht erst lesend auf eine fremde Datenbank gehen."""
    check_confirmation(confirmation)
    check_opencloud_target(opencloud_base_url)
    await check_only_demo_projects(session)


async def purge_demo_state(session: AsyncSession, cache_dir: Path) -> int:
    """Entfernt die eigenen Demo-Projekte samt aller abhaengigen Zeilen und Cache-Dateien.

    M2: zeilenweise entlang der eigenen Projekt-IDs, im Cache ausschliesslich ueber die aus den
    eigenen `(photo_id, etag)`-Paaren BERECHNETEN Pfade. Kein `glob`, kein `rmtree` - die
    Cache-Dateinamen sind flache Hash-Schluessel ohne Projektzuordnung, bei einem geteilten Volume
    traefe ein Glob echte Familien-Thumbnails.

    Die Aufzaehlung der abhaengigen Tabellen und die Cache-Loeschung stehen NICHT hier, sondern in
    `project_deletion.py`/`thumbnails.py` - dieselbe Loeschung existierte sonst ein zweites Mal
    neben `DELETE /projects/{id}`, und zwei Aufzaehlungen driften. Die Import-Richtung ist dabei
    verbindlich: dieses Modul importiert `project_deletion`, nie umgekehrt (M3, siehe
    Modul-Docstring dort).

    EINE bewusste Verhaltensaenderung gegenueber der frueheren Fassung: der Cache wird jetzt NACH
    der Zeilenloeschung geraeumt statt davor (die Reihenfolge des gemeinsamen Moduls). Die
    `(photo_id, etag)`-Paare werden weiterhin VORHER gelesen - danach gaebe es die Zeilen nicht
    mehr, aus denen sich die Pfade berechnen liessen.

    Rueckgabe: Anzahl entfernter Projekte."""
    projects = await load_demo_projects(session)
    project_ids = [project.id for project in projects]
    if not project_ids:
        return 0

    cache_keys = await collect_photo_cache_keys(session, project_ids)
    await delete_projects(session, project_ids)
    await session.flush()
    # Ueber to_thread, wie es der Docstring von delete_cached_variants zusagt: die Funktion ist rein
    # synchron und setzt bis zu zwei unlink-Aufrufe je Foto ab - ein direkter Aufruf aus dieser
    # Koroutine heraus blockierte die Event-Loop. Der Endpunkt nebenan macht es richtig; eine
    # Zusage, an die sich nur einer der beiden Aufrufer haelt, ist keine.
    await asyncio.to_thread(delete_cached_variants, cache_dir, cache_keys)
    return len(project_ids)


async def _create_project(session: AsyncSession, spec: DemoProjectSpec) -> Project:
    project = Project(
        name=spec.name,
        opencloud_drive_id="demo-drive",
        opencloud_path=f"/Demo/{spec.slug}",
    )
    session.add(project)
    await session.flush()
    return project


async def _create_photos(
    session: AsyncSession,
    project: Project,
    spec: DemoProjectSpec,
    cache_dir: Path,
    location_of: Callable[[int], tuple[float, float] | None] | None = None,
) -> list[Photo]:
    """Legt die Fotos eines Demo-Projekts an und schreibt ihre Bildvarianten ueber die ECHTE
    thumbnails.py-Logik in den Cache - kein nachgebauter Cache-Schluessel.

    `location_of` liefert je Foto-Index die Koordinate. Bewusst als Parameter statt fest
    verdrahtet: nur das "bewertet"-Projekt braucht
    Ortsdaten, und nur dort ist die Cluster-Zuordnung bekannt, aus der sich die vier
    Anzeigezustaende ergeben. Ohne den Parameter bleibt jedes Foto ohne Koordinate - der
    haeufigste reale Fall."""
    photos: list[Photo] = []
    for index in range(spec.photo_count):
        image_bytes = render_demo_image(slug=spec.slug, index=index)
        gps = None if location_of is None else location_of(index)
        photo = Photo(
            project_id=project.id,
            relative_path=demo_relative_path(spec.slug, index),
            etag=demo_etag(spec.slug, index),
            content_length=len(image_bytes),
            taken_at=demo_taken_at(index),
            taken_at_original=demo_taken_at(index),
            # Beide Felder oder keines - nie eine halbe Koordinate (Paar-Invariante von
            # `extract_gps`; die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie
            # schriebe).
            gps_lat=None if gps is None else gps[0],
            gps_lon=None if gps is None else gps[1],
            last_modified=demo_taken_at(index),
        )
        session.add(photo)
        await session.flush()
        if index not in spec.uncached_photo_indices:
            if not generate_variants(cache_dir, photo.id, photo.etag, image_bytes):
                raise DemoStateError(
                    "Die Thumbnail-Erzeugung im Cache-Verzeichnis ist fehlgeschlagen (Pfad "
                    "nicht beschreibbar?). Abbruch."
                )
        photos.append(photo)
    return photos


def _scan_run(
    project: Project,
    *,
    status: ScanStatus,
    photo_count: int,
    started_at: datetime,
    error_message: str | None = None,
) -> ScanRun:
    return ScanRun(
        project_id=project.id,
        status=status,
        started_at=started_at,
        finished_at=started_at + timedelta(minutes=2),
        last_progress_at=started_at + timedelta(minutes=2),
        files_found=photo_count,
        photos_added=photo_count if status == ScanStatus.SUCCESS else 0,
        photos_updated=0,
        photos_removed=0,
        files_skipped=0,
        total_files=photo_count,
        error_message=error_message,
    )


def _deterministic_unit_value(slug: str, index: int, salt: str) -> float:
    """Reproduzierbarer Wert in [0, 1] fuer Score-/Kriterienwerte - gerundet, damit zwei Laeufe
    exakt gleiche Zahlen liefern."""
    rng = random.Random(f"{_IMAGE_SEED}:{slug}:{index}:{salt}")
    return round(rng.uniform(0.05, 0.98), 3)


def _demo_category_confidences(slug: str, index: int, category_key: str) -> dict[str, float] | None:
    """Die Konfidenz-Abbildung EINES Demo-Fotos - `None` heisst "nicht erhoben" und ist genau der
    Fall, den die Oberflaeche als Luecke darstellen muss.

    Reine Funktion ueber demselben deterministischen Zufallsgenerator wie die uebrigen Demo-Werte:
    zwei Laeufe liefern identische Zahlen, ein Screenshot bleibt vergleichbar.

    Drei Fotos bekommen zusaetzlich feste Zahlen zu WEITEREN Schluesseln
    (`_DEMO_EXTRA_CONFIDENCES`) - daraus entstehen die Nebenkategorien, und
    zwar ueber dieselbe Ableitung wie im produktiven Schreibpfad (`secondary_categories`), damit
    die Demo keinen Zustand erzeugt, den die Anwendung selbst nie schriebe."""
    if index == _CONFIDENCE_GAP_INDEX:
        return None
    base = _deterministic_unit_value(slug, index, "category_confidence")
    if index == _LOW_CONFIDENCE_INDEX:
        confidences = {category_key: round(base * _LOW_CONFIDENCE_FACTOR, 3)}
    else:
        confidences = {category_key: base}
    return confidences | _DEMO_EXTRA_CONFIDENCES.get(index, {})


async def _create_demo_events(
    session: AsyncSession, criterion_scoring_run_id: int, photos: list[Photo], photo_count: int
) -> dict[int, int]:
    """Die vier Events des "bewertet"-Laufs - Rueckgabe `Event-Index -> events.id`.

    Zeitspanne und Ortsfelder entstehen aus den MITGLIEDERN, nicht aus freien Werten: `place_kind`
    folgt derselben Rangfolge wie `events.py::_place_of` (Name -> genau eine gerundete Zelle ->
    mehrere Orte -> kein Ortsbezug), und `'multiple'` traegt strukturell keine Koordinate. Der
    Seeder darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe."""
    members: dict[int, list[Photo]] = {}
    for index, photo in enumerate(photos):
        members.setdefault(_demo_event_index(index, photo_count), []).append(photo)

    event_by_index: dict[int, int] = {}
    for position, event_index in enumerate(sorted(members), start=1):
        group = members[event_index]
        cells = {
            (round(photo.gps_lat, 2) + 0.0, round(photo.gps_lon, 2) + 0.0)
            for photo in group
            if photo.gps_lat is not None and photo.gps_lon is not None
        }
        is_landmark = event_index == _DEMO_LANDMARK_EVENT
        if is_landmark:
            place_kind, place_lat, place_lon = "landmark", None, None
        elif not cells:
            place_kind, place_lat, place_lon = None, None, None
        elif len(cells) > 1:
            place_kind, place_lat, place_lon = "multiple", None, None
        else:
            [(lat, lon)] = cells
            place_kind, place_lat, place_lon = "coordinate", lat, lon
        event = Event(
            criterion_scoring_run_id=criterion_scoring_run_id,
            position=position,
            started_at=group[0].taken_at,
            ended_at=group[-1].taken_at,
            landmark_name=_DEMO_LANDMARK_NAME if is_landmark else None,
            place_kind=place_kind,
            place_lat=place_lat,
            place_lon=place_lon,
        )
        session.add(event)
        await session.flush()
        event_by_index[event_index] = event.id
    return event_by_index


async def _seed_empty_project(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> list[Photo]:
    """Zustand 1: ein Projekt, das es wirklich gibt, aber ohne ein einziges Foto - der leere
    Zustand der Oberflaeche."""
    project = await _create_project(session, spec)
    session.add(
        _scan_run(
            project,
            status=ScanStatus.SUCCESS,
            photo_count=0,
            started_at=_BASE_SCAN_AT,
        )
    )
    await session.flush()
    return await _create_photos(session, project, spec, cache_dir)


async def _seed_large_collection(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> list[Photo]:
    """Zustand 2: genug Fotos fuer Grid-Dichte und Scrollen (Band 60-80), bewusst keine
    Performance-Groessenordnung."""
    project = await _create_project(session, spec)
    photos = await _create_photos(session, project, spec, cache_dir)
    session.add(
        _scan_run(
            project,
            status=ScanStatus.SUCCESS,
            photo_count=len(photos),
            started_at=_BASE_SCAN_AT,
        )
    )
    await session.flush()
    return photos


async def _seed_rated_project(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> tuple[list[Photo], int]:
    """Zustand 3: alle drei Bewertungsstatus, ein offener Ausschuss-Vorschlag, ein
    Kriterien-Lauf samt Kriterien-Bewertungen und alle Kategorie-Schluessel des festen Sets.

    Rueckgabe: die Fotos und die Anzahl der Nutzer, fuer die Bewertungen geschrieben wurden."""
    project = await _create_project(session, spec)
    photos = await _create_photos(
        session,
        project,
        spec,
        cache_dir,
        location_of=lambda index: _demo_gps(index, spec.photo_count),
    )
    session.add(
        _scan_run(
            project,
            status=ScanStatus.SUCCESS,
            photo_count=len(photos),
            started_at=_BASE_SCAN_AT,
        )
    )

    scoring_run = ScoringRun(
        project_id=project.id,
        status=ScanStatus.SUCCESS,
        started_at=_BASE_SCORING_AT,
        finished_at=_BASE_SCORING_AT + timedelta(minutes=5),
        last_progress_at=_BASE_SCORING_AT + timedelta(minutes=5),
        photos_total=len(photos),
        photos_processed=len(photos),
        suggestions_found=1,
        gate_confirmed_at=_BASE_SCORING_AT + timedelta(minutes=6),
    )
    session.add(scoring_run)
    await session.flush()

    # Der Remote-Lauf DIESES Durchlaufs. Er entsteht vor dem Klassifizierungslauf, damit dessen
    # Fremdschluessel ihn treffen kann - dieselbe Reihenfolge wie im produktiven Pfad
    # (worker.py::run_classification).
    #
    # SAEMTLICHE Zahlen hier sind frei erfunden (nur synthetische Demo-Daten - das Repository ist
    # oeffentlich, PR-Anhaenge liegen oeffentlich auf GitHub). Sie stammen aus keinem echten Lauf
    # und beschreiben keine tatsaechlichen Ausgaben der Familie.
    remote_run = RemoteCategoryClassificationRun(
        project_id=project.id,
        status=ScanStatus.SUCCESS,
        started_at=_BASE_SCORING_AT + timedelta(minutes=7),
        finished_at=_BASE_SCORING_AT + timedelta(minutes=9),
        last_progress_at=_BASE_SCORING_AT + timedelta(minutes=9),
        photos_total=len(photos),
        photos_processed=len(photos),
        failed_calls=1,
        api_calls=len(photos) - 1,
        input_tokens=_DEMO_REMOTE_INPUT_TOKENS,
        output_tokens=_DEMO_REMOTE_OUTPUT_TOKENS,
        cost_usd=_DEMO_REMOTE_COST_USD,
        model=default_vision_model_for_provider("anthropic"),
    )
    session.add(remote_run)
    await session.flush()

    criterion_run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=ScanStatus.SUCCESS,
        started_at=_BASE_SCORING_AT + timedelta(minutes=10),
        finished_at=_BASE_SCORING_AT + timedelta(minutes=15),
        last_progress_at=_BASE_SCORING_AT + timedelta(minutes=15),
        photos_total=len(photos),
        photos_processed=len(photos),
        phase=ClassificationPhase.CRITERIA,
        # Der "bewertet"-Zustand traegt die vollstaendige Lauf-Bilanz: beide Cloud-Teilschritte,
        # verknuepfter Remote-Lauf und eingefrorene Startschaetzung - sonst waere der Block im
        # Pruefstack/`browse-app` gar nicht sichtbar. Der Fall "ohne Cloud" bleibt im
        # Fehlerzustands-Projekt erhalten.
        cloud_requested=True,
        remote_category_classification_run_id=remote_run.id,
        landmark_photos_total=_DEMO_LANDMARK_PHOTOS_TOTAL,
        landmark_photos_processed=_DEMO_LANDMARK_PHOTOS_TOTAL,
        landmark_failed_calls=0,
        landmark_api_calls=_DEMO_LANDMARK_PHOTOS_TOTAL,
        landmark_input_tokens=_DEMO_LANDMARK_INPUT_TOKENS,
        landmark_output_tokens=_DEMO_LANDMARK_OUTPUT_TOKENS,
        landmark_cost_usd=_DEMO_LANDMARK_COST_USD,
        landmark_model=default_vision_model_for_provider("anthropic"),
        estimated_cost_usd=_DEMO_ESTIMATED_COST_USD,
    )
    session.add(criterion_run)
    await session.flush()

    # Ein Foto je Kategorie-Schluessel des FESTEN Sets - ueber die Registry iteriert, damit eine
    # vierzehnte Kategorie automatisch mit abgedeckt ist statt durchzurutschen.
    #
    # Die Zugehoerigkeiten werden erst GESAMMELT und dann partitionsweise geschrieben - ein Foto
    # kann in mehreren Partitionen stehen, und `rank_position` ist innerhalb einer Partition
    # lueckenlos 1..n (dieselbe Zusage wie im produktiven Schreibpfad).
    # ECHTE `events`-Zeilen, eine je Anzeigezustand. Die Ortsfelder werden nicht frei gesetzt,
    # sondern aus den GEMESSENEN Koordinaten der Mitglieder abgeleitet - die Demo darf keinen
    # Zustand erzeugen, den die Anwendung selbst nie schriebe (Feldkombination M7).
    event_by_index = await _create_demo_events(session, criterion_run.id, photos, spec.photo_count)

    memberships: list[tuple[tuple[int, str], Photo, float, bool]] = []
    for index, (photo, category_key) in enumerate(zip(photos, CATEGORY_REGISTRY, strict=True)):
        event_id = event_by_index[_demo_event_index(index, spec.photo_count)]
        category_override = _DEMO_OVERRIDE_CATEGORY_KEY if index == _DEMO_OVERRIDE_INDEX else None
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=_deterministic_unit_value(spec.slug, index, "sharpness"),
                exposure=_deterministic_unit_value(spec.slug, index, "exposure"),
                # Phase A, unberuehrt von der Event-Bildung - die Divergenz zu
                # `PhotoRanking.event_id` ist gewollt.
                cluster_key=f"{spec.slug}-cluster-{index % _DEMO_EVENT_COUNT}",
                # Genau ein offener Ausschuss-Vorschlag: ein Foto mit Vorschlag "Ausschuss", das
                # bewusst KEINE Bewertung traegt - sonst waere der Vorschlag bereits entschieden.
                suggested_status=(
                    RatingStatus.REJECTED if index == _OPEN_SUGGESTION_INDEX else None
                ),
                # Genau ein uebersteuertes Foto - und zwar dasjenige, das zugleich
                # Nebenkategorien hat: nur so ist die Marker-Kollision (zwei Ecken-Marker
                # nebeneinander) im Browser ueberhaupt sichtbar.
                category_override=category_override,
                computed_at=_BASE_SCORING_AT,
            )
        )
        # Deterministische Konfidenz je Foto ueber dasselbe `_deterministic_unit_value`-Muster wie
        # die uebrigen Demo-Werte - zwei Fotos tragen die Sonderformen (keine Angabe / unterhalb der
        # Kuratierungsschwelle), siehe die Konstanten oben. Der Skalar entsteht wie im produktiven
        # Schreibpfad per LOOKUP aus der Abbildung, damit die Demo keinen Zustand erzeugt, den die
        # Anwendung selbst nie schriebe (Invariante des Schreibpfads).
        confidences = _demo_category_confidences(spec.slug, index, category_key)
        session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key=category_key,
                # Die Kandidatenliste enthaelt genau die Schluessel der Konfidenz-Abbildung -
                # `set(detected_category_confidences) <= set(detected_categories)` ist die am Parser
                # erzwungene Invariante, und die Demo darf keinen Zustand erzeugen, den die
                # Anwendung selbst nie schriebe.
                detected_categories=([category_key] if confidences is None else list(confidences)),
                detected_category_confidences=confidences,
                category_confidence=(
                    None if confidences is None else confidences.get(category_key)
                ),
                provider="demo-state",
                computed_at=_BASE_SCORING_AT,
            )
        )
        # GENAU EIN erkannter Name im Landmark-Event. Genau einer, nicht mehrere: ein zweiter
        # Name im selben Event traennte es (LandmarkChangeSignal), und der Demo-Zustand soll das
        # ungeteilte Event mit `kind="landmark"` zeigen, nicht seine Trennung. Die uebrigen Fotos
        # des Events tragen den Namen ueber `PhotoOut.event.place` mit - genau das ist der Zustand,
        # den die Sichtpruefung sehen soll.
        if index == _DEMO_LANDMARK_PHOTO_INDEX:
            session.add(
                PhotoLandmarkDetection(
                    photo_id=photo.id,
                    name=_DEMO_LANDMARK_NAME,
                    confidence=_DEMO_LANDMARK_CONFIDENCE,
                    provider="demo-state",
                    computed_at=_BASE_SCORING_AT,
                )
            )
        rank_score = _deterministic_unit_value(spec.slug, index, "rank")
        primary_key = category_override or category_key
        memberships.append(((event_id, primary_key), photo, rank_score, True))
        for secondary_key in secondary_categories(confidences or {}, primary_key):
            memberships.append(((event_id, secondary_key), photo, rank_score, False))
        for criterion_key, definition in CRITERIA_REGISTRY.items():
            session.add(
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key=criterion_key,
                    value=_deterministic_unit_value(spec.slug, index, criterion_key),
                    source=definition.source,
                    computed_at=_BASE_SCORING_AT,
                )
            )

    partitions: dict[tuple[int, str], list[tuple[Photo, float, bool]]] = {}
    for partition_key, photo, rank_score, is_primary in memberships:
        partitions.setdefault(partition_key, []).append((photo, rank_score, is_primary))
    for (partition_event_id, partition_category_key), rows in partitions.items():
        # Absteigend nach Rang-Score, Tie-Break ueber die Foto-Id - dieselbe Ordnung wie
        # ranking.py::rank_photos. Die Konfidenz-Daempfung wird hier bewusst NICHT nachgebaut: die
        # Demo soll einen plausiblen Zustand zeigen, nicht den Algorithmus ein zweites Mal
        # implementieren.
        ordered = sorted(rows, key=lambda row: (-row[1], row[0].id))
        for position, (photo, rank_score, is_primary) in enumerate(ordered, start=1):
            session.add(
                PhotoRanking(
                    criterion_scoring_run_id=criterion_run.id,
                    photo_id=photo.id,
                    event_id=partition_event_id,
                    category_key=partition_category_key,
                    rank_score=rank_score,
                    rank_position=position,
                    is_primary=is_primary,
                )
            )

    # Bewertungen haengen an VORHANDENEN Nutzern; der Seeder legt selbst nie ein Konto an (ein
    # Konto mit bekannten Zugangsdaten waere genau das Sicherheitsproblem, gegen das die Sperre
    # antritt). Alle vorhandenen Nutzer bekommen dieselben Bewertungen, damit der Zustand
    # unabhaengig davon sichtbar ist, wer sich anmeldet.
    users = (await session.execute(select(User).order_by(User.id))).scalars().all()
    for user in users:
        for offset, status in enumerate(_RATED_STATUS_ORDER):
            session.add(
                Rating(
                    photo_id=photos[offset].id,
                    user_id=user.id,
                    status=status,
                    updated_at=_BASE_SCORING_AT,
                )
            )
    await session.flush()
    return photos, len(users)


async def _seed_error_project(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> list[Photo]:
    """Zustand 4: fehlgeschlagener Lauf mit nicht-leerem Fehlertext, mindestens ein Foto ohne
    Cache-Datei ("wird noch verarbeitet"-Platzhalter) und mindestens eine Cloud-Vision-Fehlerzeile
    - die drei Fehlerdarstellungen des Frontends haengen daran."""
    project = await _create_project(session, spec)
    photos = await _create_photos(session, project, spec, cache_dir)
    session.add(
        _scan_run(
            project,
            status=ScanStatus.SUCCESS,
            photo_count=len(photos),
            started_at=_BASE_SCAN_AT,
        )
    )
    session.add(
        _scan_run(
            project,
            status=ScanStatus.FAILED,
            photo_count=len(photos),
            started_at=_BASE_SCAN_AT + timedelta(days=1),
            error_message=(
                "OpenCloud nicht erreichbar: Verbindung zum Space abgelehnt "
                "(Demo-Fehlerzustand, kein echter Vorfall)."
            ),
        )
    )
    # Der Fall "Lauf OHNE Cloud-Nutzung" der Bilanz - er lebt hier, weil im "bewertet"-Projekt jetzt
    # die vollstaendige Cloud-Bilanz steht. Ohne ihn haette die Bilanz-Variante "Ohne
    # Cloud-Anreicherung durchgefuehrt - es wurden keine Fotos an einen Anbieter gesendet." im
    # Pruefstack/`browse-app` keinen Fall mehr.
    #
    # `status = FAILED` passt zum Zweck dieses Projekts (die Bilanz erscheint auch bei einem
    # gescheiterten Lauf - das Geld waere ausgegeben gewesen) und deckt zugleich den Fehler-Alert
    # des Klassifizierungs-Abschnitts ab. Alle Cloud-Spalten bleiben `NULL`: keine Phase betreten.
    error_scoring_run = ScoringRun(
        project_id=project.id,
        status=ScanStatus.SUCCESS,
        started_at=_BASE_SCORING_AT,
        finished_at=_BASE_SCORING_AT + timedelta(minutes=3),
        last_progress_at=_BASE_SCORING_AT + timedelta(minutes=3),
        photos_total=len(photos),
        photos_processed=len(photos),
        suggestions_found=0,
        gate_confirmed_at=_BASE_SCORING_AT + timedelta(minutes=4),
    )
    session.add(error_scoring_run)
    await session.flush()
    session.add(
        CriterionScoringRun(
            project_id=project.id,
            scoring_run_id=error_scoring_run.id,
            status=ScanStatus.FAILED,
            started_at=_BASE_SCORING_AT + timedelta(minutes=5),
            finished_at=_BASE_SCORING_AT + timedelta(minutes=6),
            last_progress_at=_BASE_SCORING_AT + timedelta(minutes=6),
            photos_total=len(photos),
            photos_processed=2,
            error_message=(
                "Kriterien-Bewertung abgebrochen (Demo-Fehlerzustand, kein echter Vorfall)."
            ),
            cloud_requested=False,
        )
    )
    session.add(
        PhotoCloudVisionError(
            photo_id=photos[_CLOUD_VISION_ERROR_INDEX].id,
            phase=CloudVisionPhase.LANDMARK,
            error_type="upstream_error",
            error_message=(
                "Cloud-Vision-Anbieter antwortete mit 503 (Demo-Fehlerzustand, kein echter "
                "Vorfall)."
            ),
            attempted_at=_BASE_SCORING_AT,
        )
    )
    await session.flush()
    return photos


async def rebuild_demo_state(
    session: AsyncSession,
    cache_dir: Path,
    *,
    large_collection_photo_count: int = LARGE_COLLECTION_PHOTO_COUNT,
) -> DemoStateSummary:
    """Zielzustands-idempotent: entfernt zuerst ALLE eigenen Demo-Projekte (auch Reste eines
    frueheren Laufs mit anderen Namen) und legt die vier Zustaende danach neu an. Das Ergebnis
    haengt nicht vom Vorzustand ab.

    Enthaelt selbst KEINE Sperre - der Aufrufer (main()) wertet `assert_safe_to_seed` vor dem
    ersten Schreibzugriff vollstaendig aus."""
    await purge_demo_state(session, cache_dir)
    empty_spec, large_spec, rated_spec, error_spec = demo_project_specs(
        large_collection_photo_count=large_collection_photo_count
    )
    photos = list(await _seed_empty_project(session, empty_spec, cache_dir))
    photos += await _seed_large_collection(session, large_spec, cache_dir)
    rated_photos, rated_user_count = await _seed_rated_project(session, rated_spec, cache_dir)
    photos += rated_photos
    photos += await _seed_error_project(session, error_spec, cache_dir)
    await session.flush()

    cache_file_count = (
        sum(1 for path in cache_dir.iterdir() if path.is_file()) if cache_dir.exists() else 0
    )
    return DemoStateSummary(
        project_names=(
            empty_spec.name,
            large_spec.name,
            rated_spec.name,
            error_spec.name,
        ),
        photo_count=len(photos),
        cache_file_count=cache_file_count,
        rated_user_count=rated_user_count,
    )


# --- CLI-Verdrahtung ---------------------------------------------------------------------------


async def _rebuild_with_own_session(
    database_url: str,
    cache_dir: Path,
    *,
    confirmation: str | None,
    opencloud_base_url: str,
) -> DemoStateSummary:
    engine = make_engine(database_url)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            # Die vollstaendige Sperre laeuft VOR dem ersten Schreibzugriff (M1).
            await assert_safe_to_seed(
                session, confirmation=confirmation, opencloud_base_url=opencloud_base_url
            )
            summary = await rebuild_demo_state(session, cache_dir)
            await session.commit()
            return summary
    finally:
        await engine.dispose()


def render_summary(summary: DemoStateSummary) -> str:
    """Reine Formatierung der Ausgabe - Zaehlwerte und die eigenen Projektnamen, sonst nichts.
    Kein Konfigurationswert, kein Pfad, kein Nutzername (M2)."""
    lines = [
        "Demo-Datenbestand neu aufgebaut.",
        f"Projekte: {len(summary.project_names)}",
    ]
    lines.extend(f"  - {name}" for name in summary.project_names)
    lines.append(f"Fotos: {summary.photo_count}")
    lines.append(f"Cache-Dateien: {summary.cache_file_count}")
    lines.append(f"Bewertungen geschrieben fuer {summary.rated_user_count} vorhandene(n) Nutzer.")
    if summary.rated_user_count == 0:
        lines.append(
            "  Hinweis: kein Benutzerkonto in der Datenbank - das bewertete Projekt bleibt "
            "deshalb ohne Bewertungen. Der Seeder legt bewusst nie selbst ein Konto an."
        )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.demo_state",
        description=(
            "Baut den deterministischen Demo-Datenbestand fuer die browsergestuetzte "
            "Oberflaechenpruefung auf. Loescht dabei die EIGENEN Demo-Projekte und legt sie neu "
            "an - laeuft nur mit ausdruecklicher Freigabe ueber eine Umgebungsvariable, nur gegen "
            "eine Datenbank ohne Fremdprojekte und nur ohne echte OpenCloud-Anbindung."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default=settings.photo_cache_dir,
        help="Ziel-Verzeichnis des Thumbnail-Caches (Default: die konfigurierte Anwendung).",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, database_url: str | None = None) -> int:
    """Verdrahtung + Exit-Code. `argv` und `database_url` sind injizierbar (kein sys.argv-Zugriff
    im Testpfad, kein unbeabsichtigter Zugriff auf die konfigurierte Anwendungs-Datenbank).
    `asyncio.run` laeuft INNERHALB von main(): eine Async-Engine ueberlebt keinen Loop-Wechsel."""
    args = _build_parser().parse_args(argv)
    try:
        summary = asyncio.run(
            _rebuild_with_own_session(
                database_url or settings.database_url,
                Path(args.cache_dir),
                confirmation=os.environ.get(CONFIRM_ENV_VAR),
                opencloud_base_url=settings.opencloud_base_url,
            )
        )
    except DemoStateError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        # Nur der Fehlertyp, NIE str(exc)/Traceback - die SQLAlchemy-Meldung kann die
        # DATABASE_URL inklusive Zugangsdaten enthalten (Muster aus category_diff.py).
        print(f"Fehler: Datenbankzugriff fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(render_summary(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
