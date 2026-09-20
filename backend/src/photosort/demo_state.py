"""Schreibendes CLI: legt einen deterministischen Demo-Datenbestand fuer die browsergestuetzte
Oberflaechenpruefung an.

Aufruf::

    docker compose -f docker-compose.yml -f docker-compose.e2e.yml \\
        exec -T backend python -m photosort.demo_state

Fuenf Projekte mit dem festen Namenspraefix ``Demo — `` decken die prueflohnenden Zustaende ab
(leer, grosse Sammlung, bewertet, Fehlerzustand, Duplikate). Die Bilddateien entstehen mit Pillow
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

from photosort.album_suitability import (
    ALBUM_SUITABILITY_MAX_LEVEL,
    MAX_ALBUM_SUITABILITY_REASON_LENGTH,
)
from photosort.cameras import shifted
from photosort.cloud_vision import default_vision_model_for_provider
from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY
from photosort.db import make_engine, make_session_factory
from photosort.feedback_log import (
    FrozenContext,
    record_exchange,
    record_final_decision,
    record_motif_correction,
)
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    Event,
    FeedbackEventKind,
    FinalSelectionDecision,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    PhotoScore,
    Project,
    ProjectCamera,
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import upsert_assessment
from photosort.motifs import LOCAL_MOTIF_SIGNALS, MOTIF_REGISTRY
from photosort.places import place_cell
from photosort.project_deletion import collect_photo_cache_keys, delete_projects
from photosort.quality import compute_quality_score
from photosort.quality_weights import effective_weights, latest_weight_set
from photosort.scoring import SHARPNESS_REJECT_THRESHOLD
from photosort.thumbnails import (
    delete_cached_variants,
    generate_variants,
)
from photosort.worker import rebuild_run_selection

# --- Namen, Konstanten, Sperr-Literale -------------------------------------------------------

# Der Praefix ist der Anker der gesamten Sperre: exakt so, mit Geviertstrich und beidseitigem
# Leerzeichen. Eine lockere Pruefung ("startswith('Demo')") wuerde ein reales Projekt
# "Demolition Sommer 2019" freigeben und loeschen (Edge Case E9 der Spec).
DEMO_PROJECT_PREFIX = "Demo — "

EMPTY_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Leeres Projekt"
LARGE_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Große Sammlung"
RATED_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Bewertet"
ERROR_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Fehlerzustand"
DUPLICATE_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Duplikate"

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

# Die Groessen der beiden Duplikat-Gruppen des Vergleichs-Projekts, in dieser Reihenfolge. Das
# Projekt besteht ausschliesslich aus ihnen; seine Fotoanzahl ist ihre Summe.
#
# ZWEI Gruppen VERSCHIEDENER Groesse, und das ist keine Zugabe: Die Ansicht sagt zu, bei mehr
# Mitgliedern UMZUBRECHEN statt die Bilder zu verkleinern. Pruefbar ist das nur, wenn eine zweite
# Gruppe anderer Groesse dieselbe Kachelbreite zeigt - mit einer einzigen Gruppe bliebe die Zusage
# unbelegt, und genau dieser Fehler faellt in keinem Rendering-Test auf. Die sieben bringen dabei
# auf der breiten Pruefbreite (drei Spalten) eine angebrochene dritte Zeile, also den Umbruch
# selbst und nicht bloss eine volle Zeile.
_DEMO_DUPLICATE_GROUP_SIZES = (7, 3)

# Der Bestand ist ABSICHTLICH unentschieden: Die Sichtpruefung soll den Anfangszustand beider
# Gruppen sehen, und der Gruppenzaehler soll "1 von 2" nennen. Eine mitgelieferte Entscheidung
# naehme genau das weg.

# Hostnamen, die als "eindeutig lokal/Demo" gelten (M1c). Muster inklusive Port-Pflicht aus
# scripts/seed-opencloud-demo.py::validate_demo_base_url - dort als Copilot-Review-Fund ergaenzt,
# weil "http://localhost" (impliziter Port 80) sonst einen ganz anderen lokalen Dienst treffen
# koennte. Bewusst nachgebaut statt importiert: scripts/ ist ein eigenstaendiges Python-Paket und
# im Backend-Image nicht installiert.
_DEMO_HOSTS = frozenset({"opencloud-demo", "localhost", "127.0.0.1", "::1"})

# Bilderzeugung: fester Zufallskeim, fester Formatsatz, feste JPEG-Qualitaet - zwei Laeufe
# liefern byte-identische Dateien (per Test belegt, nicht behauptet).
_IMAGE_SEED = "photosort-demo-state-v1"
_IMAGE_JPEG_QUALITY = 90

# Vier Formate statt eines einzigen (ADR 0110, Konsequenzen): An lauter gleichen Verhaeltnissen
# ist ein justiertes Zeilenraster von einem Spaltenraster nicht zu unterscheiden - der
# E2E-Pruefstack pruefte die Zusage "kein Beschnitt, gemeinsame Zeilenhoehe" dann gar nicht.
# Hoch, quer, breit und quadratisch, alle innerhalb des Gueltigkeitsbands aus thumbnails.py.
_IMAGE_SIZES = (
    (960, 720),  # 4:3, quer
    (720, 960),  # 3:4, hoch
    (1200, 500),  # 12:5, breit
    (800, 800),  # 1:1, quadratisch
)

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

# Die vier Motiv-Fotozustaende (specs/features/0427-motive-mit-staerke.md). Bewusst VIER
# verschiedene Indizes, keiner davon derselbe: fielen zwei Sonderzustaende auf dasselbe Foto,
# zeigte die Sichtpruefung im Browser einen von beiden nie.
#
# Kein Index kollidiert mit `_OPEN_SUGGESTION_INDEX` (3) - das Foto mit offenem
# Ausschuss-Vorschlag soll seinen eigenen Zustand ungestoert zeigen. Alle vier liegen innerhalb
# der Fotoanzahl des bewerteten Projekts (der Groesse des Motivregisters); ein Waechtertest in
# tests/test_demo_state.py haelt das fest, sonst fiele ein Zustand bei einer Registry-Aenderung
# still aus dem Bestand.
_DEMO_UNASSESSED_INDEX = 5
_DEMO_LOCAL_BASIS_INDEX = 6
_DEMO_EXCLUDED_INDEX = 7
_DEMO_CORRECTED_INDEX = 1
_DEMO_CORRECTED_MOTIF_KEY = "menschen"

# Die Austausche im Ereignis-Log der Demo-Instanz: (gewaehltes Foto, ersetztes Foto, eingefrorene
# Stufe, eingefrorene Stufe des ersetzten). Die Foto-Indizes sind PAARE INNERHALB EINES EVENTS -
# bei acht Fotos und vier Events liegen 0/1, 2/3 und 4/5 jeweils zusammen, und ein Austausch ueber
# Eventgrenzen hinweg waere ein Zustand, den der Endpunkt selbst abweist.
#
# ALLE DREI TAUSCHARTEN, weil die Diagnose sie getrennt ausweist und nie summiert: gleichstufig
# (geht als einzige in die Gewichte ein), stufenuebergreifend, und unbestimmt. Die dritte entsteht
# aus dem gewoehnlichsten Hergang ueberhaupt - das Bild wurde ausgetauscht, BEVOR es eine
# Modellbewertung trug -, und ohne sie liesse sich der Zustand "keiner der beiden anderen Klassen
# zugeschlagen" in der Sichtpruefung nicht erkennen.
_DEMO_EXCHANGES: tuple[tuple[int, int, int | None, int | None], ...] = (
    (1, 0, 3, 3),
    (3, 2, 4, 2),
    (5, 4, None, 4),
)

# Das Foto und das Motiv, deren Korrektur die Demo als ZURUECKGENOMMEN zeigt: erst hinzugefuegt,
# dann zurueckgenommen. Es entsteht dabei bewusst KEINE Korrekturzeile - der Bestand zeigt eine
# zurueckgenommene Korrektur nicht mehr, und genau das ist der Grund fuer das Log. Der Index
# kollidiert mit keinem der uebrigen Sonderfaelle (0 Landmark, 1 korrigiert, 3 offener Vorschlag,
# 4 ohne Motiv-Kopfzeile, 6 lokale Grundlage, 7 ausgeschlossen).
_DEMO_WITHDRAWN_MOTIF_INDEX = 2
_DEMO_WITHDRAWN_MOTIF_KEY = "tiere"

# Die Motiv-Ereignisse der Demo: (Foto-Index, Motiv, Art). Der erste Eintrag gehoert zu der EINEN
# Korrekturzeile, die der Bestand traegt; die beiden folgenden bilden das Paar aus Korrektur und
# Ruecknahme, dem im Bestand nichts entspricht.
_DEMO_MOTIF_EVENTS: tuple[tuple[int, str, FeedbackEventKind], ...] = (
    (_DEMO_CORRECTED_INDEX, _DEMO_CORRECTED_MOTIF_KEY, FeedbackEventKind.MOTIF_DROPPED),
    (_DEMO_WITHDRAWN_MOTIF_INDEX, _DEMO_WITHDRAWN_MOTIF_KEY, FeedbackEventKind.MOTIF_ADDED),
    (
        _DEMO_WITHDRAWN_MOTIF_INDEX,
        _DEMO_WITHDRAWN_MOTIF_KEY,
        FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN,
    ),
)

# Die Spitzenstaerke, die das i-te Foto in seinem i-ten Motiv traegt. Literal und deutlich
# oberhalb der oberen Bandgrenze (2/3) statt aus dem deterministischen Generator: der Fall soll
# nicht kippen, wenn sich der Generator aendert.
_DEMO_PEAK_STRENGTH = 0.92

# Reihenfolge, in der die Albumentscheidungen auf die ersten Fotos des bewerteten Projekts
# verteilt werden - ueber das Enum gebildet, damit ein weiterer Status nicht stillschweigend
# unbewertet bliebe.
_RATED_STATUS_ORDER = tuple(RatingStatus)

# Die Bewertungszeilen der Demo-Instanz, je Eintrag ein Foto: (Albumentscheidung, Favorit).
#
# DREI Zustaende, und alle drei werden gebraucht: der erste traegt BEIDES - genau die Lage, die
# ADR 0098 neu ermoeglicht und die die Sichtpruefung sonst nirgends zu sehen bekaeme; der letzte
# traegt AUSSCHLIESSLICH das Kennzeichen und ist damit zugleich der Zustand "keine
# Albumentscheidung trotz vorhandener Zeile".
#
# Die Anzahl bleibt damit bei drei bewerteten Fotos (Index 0 bis 2) und kollidiert weiterhin
# nicht mit `_OPEN_SUGGESTION_INDEX` (3).
_DEMO_RATINGS: tuple[tuple[RatingStatus | None, bool], ...] = (
    *((status, index == 0) for index, status in enumerate(_RATED_STATUS_ORDER)),
    (None, True),
)

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

# Die Albumtauglichkeit des "bewertet"-Zustands. Zwei Fotos tragen einen Sonderfall der
# BEGRUENDUNG, damit die Sichtpruefung im Browser beide Extreme sieht - und damit die bestehenden
# Pruefstack-Spezifikationen (`no-horizontal-scroll`, `popover-position`) die Kuratierungsroute
# mit dem Extremfall besuchen, ohne dafuer einen eigenen Spec zu brauchen:
#
# * `_DEMO_MAX_REASON_INDEX` bekommt eine Begruendung in MAXIMALLAENGE - die einzige echte
#   Layoutfrage dieses Features (sprengt eine sehr lange Begruendung die 158px-Kachel?).
# * `_DEMO_NULL_REASON_INDEX` bekommt gar keine - die Zeile muss dort ersatzlos entfallen.
#
# Beide Indizes kollidieren mit keinem der Motiv-Sonderzustaende und nicht mit
# `_OPEN_SUGGESTION_INDEX`: fielen zwei Sonderfaelle auf dasselbe Foto, zeigte die Sichtpruefung
# einen von beiden nie.
_DEMO_MAX_REASON_INDEX = 2
_DEMO_NULL_REASON_INDEX = 4
# Frei erfundener Begruendungstext, auf die Zeichengrenze aufgefuellt - nie ein echter Modelltext.
_DEMO_ALBUM_SUITABILITY_REASON = (
    "Die Personen stehen mittig im Bild, der Moment ist getroffen und der Hintergrund bleibt "
    "ruhig genug, um nicht vom Motiv abzulenken."
)

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

# Abstand der Ein-Zellen-Lage von der Basis - groß genug für eine EIGENE gerundete Zelle (rund
# 1,1 km), klein genug, um in derselben Stadt zu bleiben. Ohne ihn läge das Koordinaten-Event in
# derselben Zelle wie das "Mehrere Orte"-Event, und zwei verschiedene Viertel in derselben Zelle
# wären ein Zustand, den die Anwendung nie schriebe: dieselbe Zelle ergibt dieselbe Auskunft.
_DEMO_SINGLE_CELL_OFFSET = 0.05

# DIE AUFGELÖSTEN ORTSNAMEN der Demo-Events, als LITERALE: `demo_state` ruft nie einen Auflöser
# und bezieht keinen Ortsdatensatz (S10).
#
# Die Kardinalität ist der Zweck: ZWEI Events teilen sich denselben Ortsnamen und tragen deshalb
# ihr Viertel. Ohne diesen Fall ist die Viertel-Regel im Browser unsichtbar, und `browse-app` kann
# sie nicht zeigen.
#
# NUR ZWEI Events tragen einen Namen, und mehr sind hier nicht zu haben: Von den vier Events des
# "bewertet"-Projekts trägt eines eine Sehenswürdigkeit (der Ortsname ersetzt sie nicht) und eines
# gar keine Ortsangabe (dort gibt es nichts aufzulösen). Ein fünftes Event wäre bei acht Fotos ein
# Event aus einem einzigen Foto - und das ausgeschlossene Dokument stünde dann allein in seinem
# Event, das damit Kandidaten, aber keinen Album-Entwurf trüge.
_DEMO_PLACE_NAMES = {
    _DEMO_SINGLE_COORDINATE_EVENT: "Paris, Montmartre",
    _DEMO_MULTIPLE_PLACES_EVENT: "Paris, Gros-Caillou",
}

# specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 8: der "bewertet"-Zustand muss
# ALLE Zustaende hergeben, die die Kameraliste und die Fotoansicht zeigen koennen - eine Kamera
# OHNE Versatz, eine MIT gesetztem Versatz und Fotos ohne bestimmbare Kamera. Sonst ist die
# Sichtpruefung ueber den `browse-app`-Skill fuer die Kennzeichnung "korrigiert" blind.
_DEMO_CAMERA_SLOT_COUNT = 3
_DEMO_CAMERA_WITHOUT_OFFSET = ("Apple", "iPhone 15")
_DEMO_CAMERA_WITH_OFFSET = ("Canon", "Canon EOS 5D")

# KLEINER als der Abstand zweier Demo-Fotos (17 Minuten, siehe `demo_taken_at`) und damit
# ordnungserhaltend: Die vier Demo-Events sind zusammenhaengende Bloecke ueber die nach `taken_at`
# aufsteigende Liste und ueberschneidungsfrei. Ein groesserer Versatz schoebe die Fotos der
# Kamera ueber ihre Nachbarn und erzeugte damit ueberlappende Events - denselben Zustand, den der
# Kommentar zu `_demo_event_index` oben als "von der Anwendung selbst nie geschrieben" ablehnt.
_DEMO_CAMERA_OFFSET_MINUTES = -13


def _demo_camera_slot(index: int) -> int | None:
    """Welcher Kamera das Demo-Foto `index` gehoert - `None` heisst "Kamera nicht bestimmbar".

    ZUSAMMENHAENGENDE Bloecke sind hier nicht noetig (die Kamera bestimmt keine Event-Grenze),
    ein Wechsel je Foto deckt die drei Zustaende dagegen schon bei wenigen Fotos ab."""
    slot = index % _DEMO_CAMERA_SLOT_COUNT
    return None if slot == _DEMO_CAMERA_SLOT_COUNT - 1 else slot


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
    Koordinate.

    Das Koordinaten-Event liegt um `_DEMO_SINGLE_CELL_OFFSET` versetzt und damit in einer EIGENEN
    Zelle: Es traegt ein anderes Viertel als das "Mehrere Orte"-Event, und zwei verschiedene
    Viertel in derselben Zelle waeren ein Zustand, den die Anwendung nie schriebe."""
    event_index = _demo_event_index(index, photo_count)
    if event_index == _DEMO_NO_LOCATION_EVENT:
        return None
    spread = (
        _DEMO_OTHER_CELL_STEP
        if event_index == _DEMO_MULTIPLE_PLACES_EVENT
        else _DEMO_SAME_CELL_STEP
    )
    offset = _DEMO_SINGLE_CELL_OFFSET if event_index == _DEMO_SINGLE_COORDINATE_EVENT else 0.0
    step = _demo_event_offset(index, photo_count)
    return (
        round(_DEMO_BASE_LAT + offset + spread * step, 6),
        round(_DEMO_BASE_LON + offset + spread * step, 6),
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
    """Die fuenf Zustaende in fester Reihenfolge.

    Die Fotoanzahl der grossen Sammlung ist ein Parameter mit der Produktionskonstante als Default
    (Edge Case E6): die Masse der Tests laeuft klein, genau ein Test faehrt die echte Groesse.
    Die Anzahl des bewerteten Projekts leitet sich dagegen aus dem festen MOTIVSET ab: acht
    Fotos, eines je Motiv, jedes mit einer Spitzenstaerke in genau einem Motiv - so ist jedes
    Motiv im Demo-Bestand mindestens einmal stark, ohne dass irgendwo eine abgeschriebene Liste
    gepflegt werden muesste."""
    return (
        DemoProjectSpec(name=EMPTY_PROJECT_NAME, slug="leeres-projekt", photo_count=0),
        DemoProjectSpec(
            name=LARGE_PROJECT_NAME,
            slug="grosse-sammlung",
            photo_count=large_collection_photo_count,
        ),
        DemoProjectSpec(name=RATED_PROJECT_NAME, slug="bewertet", photo_count=len(MOTIF_REGISTRY)),
        DemoProjectSpec(
            name=ERROR_PROJECT_NAME,
            slug="fehlerzustand",
            photo_count=ERROR_STATE_PHOTO_COUNT,
            uncached_photo_indices=(0,),
        ),
        # EIGENES Projekt statt zusaetzlicher Fotos im bewerteten: Dort haengt an jedem Index ein
        # benannter Sonderzustand, und die Event-/Ortsverteilung rechnet gegen die Fotoanzahl.
        # Zehn weitere Fotos verschoeben beides und nahmen der Sichtpruefung Zustaende weg, die sie
        # zeigen soll. Hier steht der Bestand fuer sich: nichts als die beiden Gruppen.
        DemoProjectSpec(
            name=DUPLICATE_PROJECT_NAME,
            slug="duplikate",
            photo_count=sum(_DEMO_DUPLICATE_GROUP_SIZES),
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


def demo_image_size(*, slug: str, index: int) -> tuple[int, int]:
    """Das Format des Demo-Fotos `index` - deterministisch aus `slug`/`index` gewaehlt.

    Reines Durchreihen ueber `index`, ohne den Zufallskeim: Der Satz hat vier Eintraege, und ein
    Zufallsgriff traefe bei kleinen Fotoanzahlen (die Masse der Tests laeuft mit drei oder vier
    Fotos) leicht viermal dasselbe Format. Das `slug` verschiebt den Startpunkt, damit zwei
    Projekte nicht Foto fuer Foto dieselbe Formfolge zeigen."""
    offset = sum(slug.encode()) % len(_IMAGE_SIZES)
    return _IMAGE_SIZES[(index + offset) % len(_IMAGE_SIZES)]


def render_demo_image(*, slug: str, index: int) -> bytes:
    """Erzeugt ein synthetisches, erkennbar durchnummeriertes JPEG.

    Deterministisch: der Zufallskeim haengt ausschliesslich an `slug`/`index`, die JPEG-Qualitaet
    ist eine Konstante, und das Format kommt aus `demo_image_size` - ebenfalls allein aus
    `slug`/`index`. Zwei Laeufe liefern byte-identische Dateien; ohne diese Zusage waere jeder
    darauf aufbauende E2E-Spec sprunghaft."""
    rng = random.Random(f"{_IMAGE_SEED}:{slug}:{index}")
    size = demo_image_size(slug=slug, index=index)
    width, height = size
    background = (rng.randrange(24, 96), rng.randrange(24, 96), rng.randrange(40, 120))
    image = Image.new("RGB", size, background)
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
    camera_of: Callable[[int], ProjectCamera | None] | None = None,
) -> list[Photo]:
    """Legt die Fotos eines Demo-Projekts an und schreibt ihre Bildvarianten ueber die ECHTE
    thumbnails.py-Logik in den Cache - kein nachgebauter Cache-Schluessel.

    `location_of` liefert je Foto-Index die Koordinate. Bewusst als Parameter statt fest
    verdrahtet: nur das "bewertet"-Projekt braucht
    Ortsdaten, und nur dort ist die Cluster-Zuordnung bekannt, aus der sich die vier
    Anzeigezustaende ergeben. Ohne den Parameter bleibt jedes Foto ohne Koordinate - der
    haeufigste reale Fall.

    `camera_of` liefert je Foto-Index die Kamerazeile, aus deren `offset_minutes` die WIRKSAME
    Zeit entsteht - gerechnet ueber `cameras.py::shifted`, dieselbe reine Funktion wie in den
    beiden produktiven Schreibstellen. Ohne den Parameter bleibt jedes Foto ohne Kamera, und
    beide Zeiten sind gleich."""
    photos: list[Photo] = []
    for index in range(spec.photo_count):
        image_bytes = render_demo_image(slug=spec.slug, index=index)
        gps = None if location_of is None else location_of(index)
        camera = None if camera_of is None else camera_of(index)
        recorded = demo_taken_at(index)
        # Ueber `shifted`, nicht ueber eine eigene Addition: der Demo-Zustand muss dieselbe
        # Invariante erfuellen wie produktive Daten.
        corrected = shifted(recorded, 0 if camera is None else camera.offset_minutes)
        if corrected is None:  # pragma: no cover - die Demo-Werte liegen weit im Bereich
            raise DemoStateError(
                "Der Demo-Versatz ergibt eine Aufnahmezeit ausserhalb des darstellbaren "
                "Bereichs. Abbruch."
            )
        photo = Photo(
            project_id=project.id,
            relative_path=demo_relative_path(spec.slug, index),
            etag=demo_etag(spec.slug, index),
            content_length=len(image_bytes),
            taken_at=corrected,
            taken_at_original=recorded,
            camera_id=None if camera is None else camera.id,
            # Der Merker steht AUCH fuer ein Foto ohne bestimmbare Kamera: die Demo bildet den
            # Zustand NACH dem Scan ab, und dort ist er gesetzt.
            camera_probed=True,
            # Beide Felder oder keines - nie eine halbe Koordinate (Paar-Invariante von
            # `extract_gps`; die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie
            # schriebe).
            gps_lat=None if gps is None else gps[0],
            gps_lon=None if gps is None else gps[1],
            last_modified=recorded,
        )
        session.add(photo)
        await session.flush()
        if index not in spec.uncached_photo_indices:
            # Das Seitenverhaeltnis kommt aus DERSELBEN Quelle wie produktiv - dem Rueckgabewert
            # von `generate_variants` -, nie aus einer zweiten Rechnung ueber `_IMAGE_SIZES`. Der
            # Demo-Bestand bildet den Zustand NACH dem Scan ab (wie `camera_probed`); ohne diesen
            # Wert fiele jedes Demo-Foto im Raster auf die 3:2-Ausfallrichtung zurueck.
            #
            # Ein Foto OHNE Cache-Dateien behaelt `None`: genau der Zustand, den ein echter Scan
            # hinterlaesst, wenn die Vorschau nicht geschrieben werden konnte.
            ratio = generate_variants(cache_dir, photo.id, photo.etag, image_bytes)
            if ratio is None:
                raise DemoStateError(
                    "Die Thumbnail-Erzeugung im Cache-Verzeichnis ist fehlgeschlagen (Pfad "
                    "nicht beschreibbar?). Abbruch."
                )
            photo.aspect_ratio = ratio
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


def _demo_album_suitability_reason(index: int) -> str | None:
    """Die Begruendung des i-ten Fotos: einmal in MAXIMALLAENGE, einmal gar keine, sonst der
    Regelfall.

    Die Maximallaenge entsteht aus der Kappungsgrenze selbst und nicht aus einem abgezaehlten
    Literal - waechst die Grenze, waechst dieser Text mit, und die Layoutfrage bleibt am
    tatsaechlichen Extremfall gestellt."""
    if index == _DEMO_NULL_REASON_INDEX:
        return None
    if index == _DEMO_MAX_REASON_INDEX:
        padded = _DEMO_ALBUM_SUITABILITY_REASON.ljust(MAX_ALBUM_SUITABILITY_REASON_LENGTH, "x")
        return padded[:MAX_ALBUM_SUITABILITY_REASON_LENGTH]
    return _DEMO_ALBUM_SUITABILITY_REASON


async def _seed_motif_assessments(
    session: AsyncSession, slug: str, photos: list[Photo], user_ids: Sequence[int]
) -> None:
    """Kopfzeilen, Staerkevektoren und GENAU EINE Korrektur - je Foto so, dass alle vier
    Fotozustaende im Demo-Bestand vorkommen (specs/features/0427-motive-mit-staerke.md).

    Ohne diese vier Zustaende sieht eine Sichtpruefung im Browser nur den Regelfall, und die drei
    Sonderdarstellungen (Satz statt Liste, lokale Grundlage mit nicht beurteilbaren Zeilen,
    Ausschluss ohne Korrekturschalter) bleiben ungesehen:

    * `_DEMO_UNASSESSED_INDEX` bekommt GAR KEINE Kopfzeile - "noch nicht klassifiziert".
    * `_DEMO_LOCAL_BASIS_INDEX` bekommt eine lokale Grundlage ohne Anbieter, und die beiden lokal
      nicht beurteilbaren Motive stehen dort auf 0.
    * `_DEMO_EXCLUDED_INDEX` ist als Dokument ausgeschlossen - mit erhaltenen Staerken daneben,
      denn der Ausschluss setzt sie nicht auf 0.
    * Alle uebrigen tragen eine Cloud-Grundlage.

    Die Staerken entstehen ueber dasselbe deterministische `_deterministic_unit_value`-Muster wie
    die uebrigen Demo-Werte und liegen damit in [0, 1] - die Demo darf keinen Zustand erzeugen,
    den die Anwendung selbst nie schriebe.

    Das i-te Foto bekommt zusaetzlich im i-ten Motiv der Registry eine SPITZENstaerke
    (`_DEMO_PEAK_STRENGTH`). Damit ist jedes Motiv im Demo-Bestand mindestens einmal im starken
    Band - sonst koennte die Statistiktabelle eine Zeile zeigen, die nie etwas anderes als
    Nullen enthaelt, und die Bandgrenzen blieben in der Sichtpruefung unsichtbar. Der Ueberhang
    bei mehr Fotos als Motiven laeuft ueber den Modulo zurueck auf den Anfang.

    Die Korrektur haengt an einem VORHANDENEN Nutzer; der Seeder legt selbst nie ein Konto an
    (ein Konto mit bekannten Zugangsdaten waere genau das Sicherheitsproblem, gegen das die Sperre
    antritt). Ohne Nutzer entsteht keine Korrektur, und der Seeder scheitert nicht daran."""
    registry_keys = list(MOTIF_REGISTRY)
    for index, photo in enumerate(photos):
        if index == _DEMO_UNASSESSED_INDEX:
            continue
        local = index == _DEMO_LOCAL_BASIS_INDEX
        peak_key = registry_keys[index % len(registry_keys)]
        strengths = {
            motif_key: (
                0.0
                if local and motif_key not in LOCAL_MOTIF_SIGNALS
                else _DEMO_PEAK_STRENGTH
                if motif_key == peak_key
                else _deterministic_unit_value(slug, index, f"motif:{motif_key}")
            )
            for motif_key in MOTIF_REGISTRY
        }
        await upsert_assessment(
            session,
            photo.id,
            source=MotifAssessmentSource.LOCAL if local else MotifAssessmentSource.CLOUD,
            strengths=strengths,
            excluded_document=index == _DEMO_EXCLUDED_INDEX,
            provider=None if local else "demo-state",
            computed_at=_BASE_SCORING_AT,
        )

    if user_ids and len(photos) > _DEMO_CORRECTED_INDEX:
        session.add(
            PhotoMotifCorrection(
                photo_id=photos[_DEMO_CORRECTED_INDEX].id,
                user_id=user_ids[0],
                motif_key=_DEMO_CORRECTED_MOTIF_KEY,
                applies=False,
                updated_at=_BASE_SCORING_AT,
            )
        )
    await session.flush()


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
            place_cell(photo.gps_lat, photo.gps_lon)
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
            # Ein Event OHNE Ortsangabe bekommt auch dann keinen Namen, wenn die Abbildung einen
            # traegt: Was es aufzuloesen gaebe, gibt es dort nicht.
            place_name=None if place_kind is None else _DEMO_PLACE_NAMES.get(event_index),
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
    # Dieses EINE Demo-Projekt traegt die Cloud-Freigabe - und zwar notwendigerweise: sein
    # Zustand enthaelt eine Cloud-Bilanz, eine Cloud-Motiv-Kopfzeile und eine Albumtauglichkeit,
    # und die kann die Anwendung ohne Freigabe gar nicht erzeugt haben. Ohne sie zeigte die
    # Kuratierung hier den Hinweis "Ohne Cloud-Freigabe entsteht kein Album-Entwurf" statt der
    # Kacheln, und die Pruefstack-Spezifikationen besuchten eine leere Ansicht.
    #
    # Es wird dadurch NICHTS ausgeloest: der Demo-Stapel hat keinen Worker-Lauf, und die Freigabe
    # allein ruft nirgends an. Der Fall "ohne Cloud" bleibt im Fehlerzustands-Projekt sichtbar,
    # das die Freigabe weiterhin nicht traegt.
    project.cloud_vision_detection_enabled = True
    project.cloud_vision_consent_at = _BASE_SCORING_AT
    # Die beiden Kamerazeilen entstehen VOR den Fotos - `Photo.camera_id` ist ein echter
    # Fremdschluessel, und die wirksame Zeit haengt am Versatz der Zeile.
    cameras = [
        ProjectCamera(
            project_id=project.id,
            make=_DEMO_CAMERA_WITHOUT_OFFSET[0],
            model=_DEMO_CAMERA_WITHOUT_OFFSET[1],
            offset_minutes=0,
        ),
        ProjectCamera(
            project_id=project.id,
            make=_DEMO_CAMERA_WITH_OFFSET[0],
            model=_DEMO_CAMERA_WITH_OFFSET[1],
            offset_minutes=_DEMO_CAMERA_OFFSET_MINUTES,
        ),
    ]
    session.add_all(cameras)
    await session.flush()

    def _camera_of(index: int) -> ProjectCamera | None:
        slot = _demo_camera_slot(index)
        return None if slot is None else cameras[slot]

    photos = await _create_photos(
        session,
        project,
        spec,
        cache_dir,
        location_of=lambda index: _demo_gps(index, spec.photo_count),
        camera_of=_camera_of,
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
        # KEIN `phase`: Der Lauf ist abgeschlossen (`status=SUCCESS`), und ein abgeschlossener
        # Lauf traegt keinen laufenden Teilschritt (ADR 0116 Punkt 1). Der frueher hier gesetzte
        # Wert widersprach der Invariante, auf die AK8 der Spec 0481 sich stuetzt - der eigene
        # Demo-Bestand war der einzige Ort, an dem sie falsch war.
        # Der Beginn `phase_started_at` faellt damit mit weg; beide Spalten gehoeren zusammen.
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

    # DIESELBE Herkunft der Gewichte wie im Lauf (`worker.py`), einmal gelesen und an der
    # Lauf-Zeile belegt: Eine hier stehengebliebene Modulkonstante zeigte auf der Demo-Instanz
    # Zahlen, die die Anwendung nach der naechsten Anpassung nie wieder erzeugte - und die Demo
    # darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe.
    weights = await effective_weights(session)
    used_weight_set = await latest_weight_set(session)
    criterion_run.quality_weight_set_id = None if used_weight_set is None else used_weight_set.id

    # Die Rangzeilen werden erst GESAMMELT und dann partitionsweise geschrieben: `rank_position`
    # ist innerhalb einer Partition lueckenlos 1..n (dieselbe Zusage wie im produktiven
    # Schreibpfad), und die Position steht erst fest, wenn die Partition vollstaendig ist.
    # ECHTE `events`-Zeilen, eine je Anzeigezustand. Die Ortsfelder werden nicht frei gesetzt,
    # sondern aus den GEMESSENEN Koordinaten der Mitglieder abgeleitet - die Demo darf keinen
    # Zustand erzeugen, den die Anwendung selbst nie schriebe (Feldkombination M7).
    event_by_index = await _create_demo_events(session, criterion_run.id, photos, spec.photo_count)

    rankings: list[tuple[int, Photo, float]] = []
    for index, photo in enumerate(photos):
        event_id = event_by_index[_demo_event_index(index, spec.photo_count)]
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
                computed_at=_BASE_SCORING_AT,
            )
        )
        # GENAU EIN erkannter Name im Landmark-Event. Genau einer, nicht mehrere: Ein zweiter Name
        # im selben Event bliebe zwar drin (er trennt seit ADR 0118 nichts mehr), waere aber ohne
        # Wirkung auf die Anzeige - das Event traegt den fruehesten. Der Demo-Zustand soll das
        # Event mit `kind="landmark"` zeigen, nicht einen unsichtbaren zweiten Namen. Die uebrigen Fotos
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
        criterion_values: dict[str, float] = {}
        for criterion_key, definition in CRITERIA_REGISTRY.items():
            value = _deterministic_unit_value(spec.slug, index, criterion_key)
            criterion_values[criterion_key] = value
            session.add(
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key=criterion_key,
                    value=value,
                    source=definition.source,
                    computed_at=_BASE_SCORING_AT,
                )
            )

        # Die Modellbewertung und der daraus GERECHNETE Qualitaetswert - nicht zwei unabhaengige
        # Zufallszahlen: die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie
        # schriebe, und `rank_score` ist seit Spec 0428 genau diese Rechnung.
        level = index % ALBUM_SUITABILITY_MAX_LEVEL + 1
        session.add(
            PhotoAlbumSuitability(
                photo_id=photo.id,
                level=level,
                reason=_demo_album_suitability_reason(index),
                provider="demo-state",
                computed_at=_BASE_SCORING_AT,
            )
        )
        rankings.append(
            (
                event_id,
                photo,
                compute_quality_score(level, criterion_values, weights),
            )
        )

    # Eine Partition je Event, ein Foto in genau einer davon.
    partitions: dict[int, list[tuple[Photo, float]]] = {}
    for event_id, photo, rank_score in rankings:
        partitions.setdefault(event_id, []).append((photo, rank_score))
    for partition_event_id, rows in partitions.items():
        # Absteigend nach Rang-Score, Tie-Break ueber die Foto-Id - dieselbe Ordnung wie
        # ranking.py::rank_photos.
        ordered = sorted(rows, key=lambda row: (-row[1], row[0].id))
        for position, (photo, rank_score) in enumerate(ordered, start=1):
            session.add(
                PhotoRanking(
                    criterion_scoring_run_id=criterion_run.id,
                    photo_id=photo.id,
                    event_id=partition_event_id,
                    rank_score=rank_score,
                    rank_position=position,
                )
            )

    # Bewertungen haengen an VORHANDENEN Nutzern; der Seeder legt selbst nie ein Konto an (ein
    # Konto mit bekannten Zugangsdaten waere genau das Sicherheitsproblem, gegen das die Sperre
    # antritt). Alle vorhandenen Nutzer bekommen dieselben Bewertungen, damit der Zustand
    # unabhaengig davon sichtbar ist, wer sich anmeldet.
    users = (await session.execute(select(User).order_by(User.id))).scalars().all()
    for user in users:
        for offset, (status, favorite) in enumerate(_DEMO_RATINGS):
            session.add(
                Rating(
                    photo_id=photos[offset].id,
                    user_id=user.id,
                    status=status,
                    favorite=favorite,
                    updated_at=_BASE_SCORING_AT,
                )
            )
    await session.flush()

    # NACH dem `flush` der Bewertungen und ueber denselben Nutzerbestand: die Korrektur haengt an
    # einem vorhandenen Konto, genau wie sie.
    await _seed_motif_assessments(session, spec.slug, photos, [user.id for user in users])

    # DER AUSWAHLVORSCHLAG ueber DIESELBE Worker-Funktion, nie ueber eine zweite Vergaberegel
    # hier: eine solche saehe im Ergebnis genauso aus und roetete keinen Test. Ohne diesen Aufruf
    # zeigt `/album` auf der Demo-Instanz eine leere Liste; der Albumseiten-Eintrag in
    # `no-horizontal-scroll` verlangt deshalb ausdruecklich mindestens EINE Kachel als
    # Vorbedingung, statt sich auf Ueberschrift und Scrollhoehe zu verlassen.
    #
    # Die Stelle ist NACH den Motivkopfzeilen: der Vorschlag liest die wirksamen Staerken, und
    # davor gaebe es keine.
    await rebuild_run_selection(session, project.id)
    await session.flush()

    # DER DISSENS-BLOCK, NACH dem Vorschlag und nicht davor: Vorher steht nicht fest, WELCHES Foto
    # vorgeschlagen ist, und ein geratenes traefe die gewuenschten Zustaende nicht.
    await _seed_final_selection_dissent(session, criterion_run.id, users)
    await session.flush()

    # DAS EREIGNIS-LOG ZULETZT: Es beschreibt Handgriffe an einem fertigen Entwurf, und die
    # gemeinsamen Entscheidungen, deren Ereignisse es traegt, entstehen erst im Block darueber.
    await _seed_feedback_events(
        session,
        project_id=project.id,
        criterion_scoring_run_id=criterion_run.id,
        photos=photos,
        user_ids=[user.id for user in users],
    )
    await session.flush()
    return photos, len(users)


async def _seed_final_selection_dissent(
    session: AsyncSession, criterion_scoring_run_id: int, users: Sequence[User]
) -> None:
    """Die vier Zustaende der gemeinsamen Endauswahl auf der Demo-Instanz (Spec 0431).

    Ohne diesen Block bekommen ALLE Nutzer dieselben Bewertungen - die Nutzer sind dann per
    Definition einig, die Arbeitssicht zeigt dauerhaft "keine Unterschiede", und KEIN Test wuerde
    rot. Erzeugt werden:

    1. ein vorgeschlagenes Foto, vom ERSTEN Nutzer gestrichen -> strittig;
    2. ein nicht vorgeschlagenes Kandidatenfoto, vom ZWEITEN Nutzer aufgenommen -> strittig;
    3. ein strittiges Foto mit `included=true` -> "gemeinsam entschieden, drin";
    4. ein einig-drinnes Foto mit `included=false` -> "einig, aber herausgenommen".

    OHNE NUTZER UND MIT GENAU EINEM NUTZER SCHREIBT ER NICHTS: Bei `n = 1` ist Dissens
    arithmetisch unmoeglich (jedes vorgeschlagene, unangefasste Foto ist in der Endauswahl), und
    ein trotzdem geschriebener Zustand waere einer, den die Anwendung selbst nie herstellt.

    DETERMINISTISCH: Die Kandidaten kommen aus dem TATSAECHLICHEN Vorschlag, sortiert nach
    `photo_id` - genau hier wuerde eine Mengeniteration unbemerkt sprunghaft, und die
    Sichtpruefung zeigte von Lauf zu Lauf andere Bilder in anderen Rollen.

    Beruehrt werden ausschliesslich Fotos OHNE bestehende Bewertungszeile: Der Block darf den
    Zustandsvorrat des bestehenden Bewertungsblocks nicht verschieben, dessen Abdeckung ein
    eigener Testfall festhaelt."""
    if len(users) < 2:
        return

    rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.selection_position)
            .where(
                PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
                PhotoRanking.rank_score.is_not(None),
            )
            .order_by(PhotoRanking.photo_id)
        )
    ).all()
    already_rated = set(
        (
            await session.execute(
                select(Rating.photo_id).where(
                    Rating.photo_id.in_([photo_id for photo_id, _ in rows])
                )
            )
        )
        .scalars()
        .all()
    )
    proposed = [pid for pid, position in rows if position is not None and pid not in already_rated]
    unproposed = [pid for pid, position in rows if position is None and pid not in already_rated]

    # Drei vorgeschlagene und ein nicht vorgeschlagenes Foto. Reicht der Vorrat nicht, entstehen
    # die Zustaende, fuer die er reicht - der Seeder laeuft auch mit kleinen Fotozahlen (die
    # Testsuite faehrt ihn so) und darf dort nicht abbrechen.
    if len(proposed) >= 1:
        session.add(
            Rating(
                photo_id=proposed[0],
                user_id=users[0].id,
                status=RatingStatus.REJECTED,
                updated_at=_BASE_SCORING_AT,
            )
        )
    if len(unproposed) >= 1:
        session.add(
            Rating(
                photo_id=unproposed[0],
                user_id=users[1].id,
                status=RatingStatus.ALBUM_WORTHY,
                updated_at=_BASE_SCORING_AT,
            )
        )
    if len(proposed) >= 2:
        # Strittig UND entschieden: die Entscheidung ueberschreibt, das Foto verlaesst die
        # Arbeitssicht. Ohne die Streichung daneben zeigte die Demo die Ueberschreibung nicht.
        session.add(
            Rating(
                photo_id=proposed[1],
                user_id=users[0].id,
                status=RatingStatus.REJECTED,
                updated_at=_BASE_SCORING_AT,
            )
        )
        session.add(FinalSelectionDecision(photo_id=proposed[1], included=True))
    if len(proposed) >= 3:
        # Einig drin - und trotzdem herausgenommen. Einigkeit ist eine Vorbelegung, keine Sperre.
        session.add(FinalSelectionDecision(photo_id=proposed[2], included=False))


async def _seed_feedback_events(
    session: AsyncSession,
    *,
    project_id: int,
    criterion_scoring_run_id: int,
    photos: Sequence[Photo],
    user_ids: Sequence[int],
) -> None:
    """Das Ereignis-Log der Nacharbeit auf der Demo-Instanz (Spec 0432).

    OHNE DIESEN BLOCK zeigt der Diagnoseabschnitt dort dauerhaft seinen Nullzustand, und KEIN Test
    wuerde rot: Die Pruefstack-Spezifikation misst die Statistik-Route bereits und maesse dann
    dauerhaft den Leerzustand.

    ALLE DREI TAUSCHARTEN entstehen hier, weil die Diagnose sie getrennt ausweist und nie
    summiert - und die unbestimmte ist ohne eigenen Eintrag nicht darstellbar. Die eingefrorenen
    Stufen stehen dafuer in `_DEMO_EXCHANGES` und werden NICHT aus der heutigen Modellbewertung
    gelesen: Ein Ereignis haelt die Lage zum Zeitpunkt der Korrektur fest, und ein spaeterer Lauf
    ueberschreibt sie - genau das ist der Gegenstand des Einfrierens (ADR 0100 Punkt 2). Die
    unbestimmte Tauschart entsteht so aus dem gewoehnlichsten Hergang ueberhaupt: Das Bild wurde
    ausgetauscht, BEVOR es eine Modellbewertung trug.

    Lauf, Ereignis-Gruppierung, Projekt und Qualitaetswerte kommen dagegen aus dem TATSAECHLICHEN
    Bestand - die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe.

    Geschrieben wird ausschliesslich ueber `feedback_log` - die eine Schreibstelle, an der die
    Feldmatrix je `kind` haengt. Ein zweiter Schreibweg hier saehe im Ergebnis genauso aus und
    roetete keinen Test.

    OHNE NUTZER ENTSTEHT NICHTS ausser den gemeinsamen Entscheidungen: Die tragen bewusst keinen
    Nutzerbezug (S9), alles andere haengt an einem vorhandenen Konto."""
    rankings = {
        photo_id: (event_id, rank_score)
        for photo_id, event_id, rank_score in (
            await session.execute(
                select(PhotoRanking.photo_id, PhotoRanking.event_id, PhotoRanking.rank_score).where(
                    PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id
                )
            )
        ).all()
    }
    # Die HEUTIGE Modellstufe - richtig fuer jedes Ereignis, dessen Lage sich seither nicht
    # bewegt hat. Nur die Tauschereignisse tragen bewusst andere, aeltere Stufen (siehe oben).
    levels = {
        photo_id: level
        for photo_id, level in (
            await session.execute(
                select(PhotoAlbumSuitability.photo_id, PhotoAlbumSuitability.level).where(
                    PhotoAlbumSuitability.photo_id.in_([photo.id for photo in photos])
                )
            )
        ).all()
    }

    def _context(photo_id: int) -> FrozenContext:
        event_id, quality = rankings.get(photo_id, (None, None))
        return FrozenContext(
            criterion_scoring_run_id=criterion_scoring_run_id if event_id is not None else None,
            event_id=event_id,
            level=levels.get(photo_id),
            quality=quality,
        )

    if user_ids:
        for taken_index, replaced_index, level, replaced_level in _DEMO_EXCHANGES:
            if max(taken_index, replaced_index) >= len(photos):
                continue
            taken, replaced = photos[taken_index], photos[replaced_index]
            if taken.id not in rankings or replaced.id not in rankings:
                continue
            event_id, quality = rankings[taken.id]
            _, replaced_quality = rankings[replaced.id]
            await record_exchange(
                session,
                project_id=project_id,
                user_id=user_ids[0],
                photo_id=taken.id,
                replaced_photo_id=replaced.id,
                criterion_scoring_run_id=criterion_scoring_run_id,
                event_id=event_id,
                level=level,
                replaced_level=replaced_level,
                quality=quality,
                replaced_quality=replaced_quality,
            )

        strengths = {
            (photo_id, motif_key): strength
            for photo_id, motif_key, strength in (
                await session.execute(
                    select(
                        PhotoMotifStrength.photo_id,
                        PhotoMotifStrength.motif_key,
                        PhotoMotifStrength.strength,
                    ).where(PhotoMotifStrength.photo_id.in_([photo.id for photo in photos]))
                )
            ).all()
        }
        for photo_index, motif_key, kind in _DEMO_MOTIF_EVENTS:
            if photo_index >= len(photos):
                continue
            photo = photos[photo_index]
            await record_motif_correction(
                session,
                project_id=project_id,
                photo_id=photo.id,
                user_id=user_ids[0],
                kind=kind,
                motif_key=motif_key,
                motif_strength=strengths.get((photo.id, motif_key)),
                context=_context(photo.id),
            )

    # Die gemeinsamen Entscheidungen - OHNE Nutzer, und der Aufruf koennte auch gar keinen
    # anbieten. Gelesen aus dem tatsaechlich geschriebenen Bestand statt aus einer zweiten
    # Indexliste daneben: Welche Fotos der Dissens-Block entschieden hat, haengt am Vorschlag.
    decisions = (
        await session.execute(
            select(FinalSelectionDecision.photo_id, FinalSelectionDecision.included)
            .where(FinalSelectionDecision.photo_id.in_(list(rankings)))
            .order_by(FinalSelectionDecision.photo_id)
        )
    ).all()
    for photo_id, included in decisions:
        await record_final_decision(
            session,
            project_id=project_id,
            photo_id=photo_id,
            kind=(
                FeedbackEventKind.FINAL_DECISION_IN
                if included
                else FeedbackEventKind.FINAL_DECISION_OUT
            ),
            context=_context(photo_id),
        )


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


async def _seed_duplicate_project(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> list[Photo]:
    """Zustand 5: zwei Duplikat-Gruppen verschiedener Groesse, beide unentschieden.

    Ohne diesen Bestand ist die Vergleichsansicht weder vorfuehrbar noch im Browser pruefbar, und
    kein Test wuerde rot (ADR 0104).

    Der Bestand entsteht GENAU SO, wie ihn ein echter Ausschuss-Lauf hinterliesse: Je Gruppe
    traegt das erste Foto kein `duplicate_of` (der Gewinner), alle uebrigen
    `suggested_status = REJECTED` und `duplicate_of` auf den Gewinner. Ketten gibt es nicht; der
    Gewinner zeigt nirgendwohin. `suggestions_found` ist die Zahl der Aufnahmen mit Vorschlag.

    DER GEWINNER DER ZWEITEN GRUPPE IST SELBST ABGELEHNT - eine Serie unterhalb der
    Schaerfeschwelle, deren Gewinner trotzdem herausfaellt. Sein Ausschuss folgt nicht aus dem
    Duplikat (`duplicate_of` bleibt `None`), und kein Wert der Entscheidungszeile aendert ihn: Er
    ist das UNVERAENDERLICHE Mitglied, an dem die Kachel ohne Wahlschaltflaechen vorfuehrbar wird.
    Ohne ihn ist AK3 der Spec 0486 im Browser nicht pruefbar.

    KEINE Entscheidungszeile: Die Ansicht soll ihren Anfangszustand zeigen."""
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

    mit_vorschlag = 0
    erste = 0
    for gruppen_index, size in enumerate(_DEMO_DUPLICATE_GROUP_SIZES):
        gruppe = photos[erste : erste + size]
        gewinner = gruppe[0]
        # GENAU EINE der beiden Gruppen traegt einen selbst abgelehnten Gewinner. Die andere zeigt
        # den Regelfall daneben - ohne sie bliebe unbelegt, dass die Ansicht beide unterscheidet.
        gewinner_abgelehnt = gruppen_index == 1
        for offset, photo in enumerate(gruppe):
            ist_gewinner = offset == 0
            abgelehnt = not ist_gewinner or gewinner_abgelehnt
            session.add(
                PhotoScore(
                    photo_id=photo.id,
                    # Der abgelehnte Gewinner liegt unterhalb der Schaerfeschwelle - ein Wert
                    # darueber waere ein Bestand, den kein Lauf hinterliesse.
                    sharpness=(
                        SHARPNESS_REJECT_THRESHOLD / 2
                        if ist_gewinner and gewinner_abgelehnt
                        else _deterministic_unit_value(spec.slug, erste + offset, "sharpness")
                    ),
                    exposure=_deterministic_unit_value(spec.slug, erste + offset, "exposure"),
                    # Der Zeit-/Ortscluster wird nur fuer die NICHT aussortierten Fotos gesetzt -
                    # dieselbe Regel wie im Lauf. Er ist ausdruecklich nicht die Duplikat-Gruppe.
                    cluster_key=None if abgelehnt else f"{spec.slug}-cluster-0",
                    # Der abgelehnte Gewinner traegt trotzdem KEIN `duplicate_of` - genau daran
                    # haengt, dass sein Ausschuss nicht aus dem Duplikat folgt.
                    duplicate_of=None if ist_gewinner else gewinner.id,
                    suggested_status=RatingStatus.REJECTED if abgelehnt else None,
                    computed_at=_BASE_SCORING_AT,
                )
            )
            if abgelehnt:
                mit_vorschlag += 1
        erste += size

    session.add(
        ScoringRun(
            project_id=project.id,
            status=ScanStatus.SUCCESS,
            started_at=_BASE_SCORING_AT,
            finished_at=_BASE_SCORING_AT + timedelta(minutes=2),
            last_progress_at=_BASE_SCORING_AT + timedelta(minutes=2),
            photos_total=len(photos),
            photos_processed=len(photos),
            suggestions_found=mit_vorschlag,
            # Das Gate bleibt UNBESTAETIGT: Die Vergleichsansicht ist der Weg durch die Sichtung,
            # und ein bereits bestaetigtes Gate zeigte den Einstieg in sie nie.
            gate_confirmed_at=None,
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
    frueheren Laufs mit anderen Namen) und legt die fuenf Zustaende danach neu an. Das Ergebnis
    haengt nicht vom Vorzustand ab.

    Enthaelt selbst KEINE Sperre - der Aufrufer (main()) wertet `assert_safe_to_seed` vor dem
    ersten Schreibzugriff vollstaendig aus."""
    await purge_demo_state(session, cache_dir)
    empty_spec, large_spec, rated_spec, error_spec, duplicate_spec = demo_project_specs(
        large_collection_photo_count=large_collection_photo_count
    )
    photos = list(await _seed_empty_project(session, empty_spec, cache_dir))
    photos += await _seed_large_collection(session, large_spec, cache_dir)
    rated_photos, rated_user_count = await _seed_rated_project(session, rated_spec, cache_dir)
    photos += rated_photos
    photos += await _seed_error_project(session, error_spec, cache_dir)
    photos += await _seed_duplicate_project(session, duplicate_spec, cache_dir)
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
            duplicate_spec.name,
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
        # DATABASE_URL inklusive Zugangsdaten enthalten (Muster analog OpenCloudError).
        print(f"Fehler: Datenbankzugriff fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(render_summary(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
