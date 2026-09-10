from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any

from PIL import Image
from PIL.ExifTags import IFD

logger = logging.getLogger(__name__)

_DATETIME_ORIGINAL_TAG = 36867
_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"

# GPSInfo-IFD-Tags (EXIF-Standard) - bewusst als benannte Konstanten, die nackten Zahlen 1-4
# sagen an der Lesestelle nichts.
_GPS_LATITUDE_REF_TAG = 1
_GPS_LATITUDE_TAG = 2
_GPS_LONGITUDE_REF_TAG = 3
_GPS_LONGITUDE_TAG = 4

# Zeichen, die am Ref abgeschnitten werden, bevor er verglichen wird: reale Dateien schreiben ihn
# als NUL-terminierten ASCII-String, Pillow liefert ihn dann als `'S\x00'`. Ohne dieses Trimmen
# verloere eine voellig gewoehnliche Suedhalbkugel-Aufnahme ihren Ort.
_REF_STRIP_CHARS = " \t\r\n\x00"

# specs/features/0051-gps-landmark-cluster-bildung.md, Sicherheitskonzept "Standortdaten (GPS aus
# EXIF)": FESTE Grund-Tokens statt des Rohwerts, exakt nach dem Muster von
# remote_classification.py::_CONFIDENCE_REASON_*. Standortdaten sind seit ADR 0029 ein
# eigenstaendiges Asset; eine Logzeile ist eine schwaecher geschuetzte, laenger lebende Oberflaeche
# als die Datenbank. Weder ein akzeptierter noch ein verworfener Rohwert wird geloggt - die
# FEHLERKLASSE traegt den vollen Diagnosewert, der konkrete Wert nichts darueber hinaus.
#
# Vier Tokens statt der drei im Sicherheitskonzept ausdruecklich genannten: `extract_gps` hat vier
# Verwerfungsklassen. `nullinsel` unter `ausserhalb_intervall` zu fuehren waere schlicht falsch -
# das Paar LIEGT im gueltigen Intervall, es ist ein Geraete-Artefakt bei fehlgeschlagenem Fix.
# Die Auflage ("nur feste Grund-Tokens plus photo_id") ist damit unveraendert erfuellt: kein
# Fremdtext, keine Koordinate, keine Log-Injection-Flaeche.
_GPS_REASON_REF_MISSING = "ref_fehlt"
_GPS_REASON_NOT_NUMERIC = "nicht_numerisch"
_GPS_REASON_OUT_OF_RANGE = "ausserhalb_intervall"
_GPS_REASON_NULL_ISLAND = "nullinsel"


def extract_taken_at(content: bytes) -> datetime | None:
    """Best-effort EXIF DateTimeOriginal extraction.

    Runs on partial (range-fetched) file content from untrusted, possibly
    truncated downloads, so any parsing failure is treated as "no date
    available" rather than propagated — a single unreadable photo must
    never abort a project scan.
    """
    try:
        image = Image.open(io.BytesIO(content))
        exif = image.getexif()
        raw_value = exif.get(_DATETIME_ORIGINAL_TAG) or exif.get_ifd(IFD.Exif).get(
            _DATETIME_ORIGINAL_TAG
        )
    except Exception:
        return None

    if not raw_value:
        return None

    try:
        return datetime.strptime(raw_value, _DATETIME_FORMAT)
    except ValueError:
        return None


def _log_discarded_gps(photo_id: int | None, reason: str) -> None:
    """Eine WARNING-Zeile je verworfener Koordinate - mit FESTEM Grund-Token und `photo_id`, sonst
    nichts. Kein Log-Flooding moeglich: je Foto kann hoechstens EINE Koordinate verworfen werden,
    und der Normalfall "gar kein GPS-IFD" erzeugt ueberhaupt keine Zeile (ein Scan ueber tausende
    Fotos ohne Ortsangabe bleibt still)."""
    logger.warning("extract_gps: Koordinate verworfen photo_id=%s grund=%s", photo_id, reason)


def _normalized_ref(raw: object, allowed: tuple[str, str]) -> str | None:
    """Der Referenzbuchstabe nach Trimmen von Whitespace/NUL und Grossschreibung - `None`, wenn er
    fehlt oder nicht exakt einer der beiden fuer DIESE Komponente zulaessigen Werte ist.

    Je Komponente gegen ihr EIGENES Wertepaar, nicht gegen die Vereinigung aller vier Buchstaben:
    ein `E` als Breiten-Referenz ist ein kaputter Datensatz, kein Osten.

    Alles, was kein `str` ist, wird VERWORFEN statt umgedeutet - Pillow liefert den ASCII-Tag
    verifiziert als `str` (NUL-Terminierung inklusive, deshalb das Trimmen unten). Einen Rohwert
    anderen Typs zu dekodieren hiesse, aus einem kaputten Datensatz eine Himmelsrichtung zu raten;
    "kein Ort" ist der ueberall sauber behandelte Zustand."""
    if not isinstance(raw, str):
        return None
    normalized = raw.strip(_REF_STRIP_CHARS).upper()
    return normalized if normalized in allowed else None


def _decimal_degrees(raw: Any, ref: str, negative_ref: str) -> float:
    """Grad/Minute/Sekunde -> Dezimalgrad, mit Vorzeichenumkehr bei `S`/`W`.

    Wirft bei allem, was nicht GENAU drei in `float` konvertierbare Komponenten sind (fehlender
    Tag, zwei statt drei Werte, nicht numerischer Inhalt) - der Aufrufer faengt das. Die
    Konvertierung MUSS innerhalb seines geschuetzten Blocks liegen: ein absurder Zaehler wirft
    `OverflowError`, und der ist nur dort gedeckt.

    `raw` ist bewusst `Any`: der Wert kommt roh aus einer fremden, moeglicherweise entarteten
    Datei - jede engere Typannahme waere hier eine Behauptung ueber Eingabedaten, die die Funktion
    gerade nicht treffen darf."""
    degrees, minutes, seconds = (float(component) for component in raw)
    value = degrees + minutes / 60.0 + seconds / 3600.0
    return -value if ref == negative_ref else value


def extract_gps(content: bytes, photo_id: int | None = None) -> tuple[float, float] | None:
    """Best-effort EXIF-GPS-Extraktion als Pendant zu `extract_taken_at` (specs/features/0051-gps-
    landmark-cluster-bildung.md, ADR 0029/0072) - liefert `(lat, lon)` in Dezimalgrad oder `None`.

    Liest aus demselben bereits per Range-Read geladenen Byte-Fenster wie `extract_taken_at`
    (`worker.py::_EXIF_RANGE_BYTES`), also ohne einen einzigen zusaetzlichen Netzwerkzugriff.

    PAAR-INVARIANTE: BEIDE Werte oder KEINER. Scheitert eine Komponente, sind beide verworfen -
    sonst stuende in der Datenbank ein halbes Koordinatenpaar und jede spaetere `is not None`-
    Pruefung muesste beide Spalten einzeln kennen.

    Der `try` umfasst Arithmetik UND Bereichspruefung, nicht nur `Image.open`/`get_ifd` - anders
    als bei `extract_taken_at`, wo die riskante Stelle tatsaechlich nur das Oeffnen/Parsen ist.

    DREI Verwerfungsregeln, die KEIN Parserfehler sind und die ein `except Exception` deshalb
    strukturell nicht sehen kann (Sicherheitskonzept, Abschnitt "Standortdaten"):

    1. **Bereichspruefung als VERGLEICH, nie als Klemmen.** Verifiziert am Projektstand (Pillow
       12.3.0): `IFDRational(x, 0)` ergibt `nan` OHNE jede Exception, und `nan` propagiert durch
       die DMS-Arithmetik. Ein Klemmen liesse es durch, weil JEDER Vergleich mit `nan` `False`
       ergibt. Landete `nan` in `Photo.gps_lat`, naehme PostgreSQL es an und SQLite im Testlauf
       ebenfalls - aber Starlettes `JSONResponse.render` serialisiert mit `allow_nan=False`: ein
       einziges betroffenes Foto legte die GESAMTE Listenantwort des Projekts dauerhaft auf 500.
       Dieselbe Falle deckt auch den zweiten Ausgang eines abgeschnittenen Range-Read-Fensters -
       daraus folgt naemlich NICHT verlaesslich "gar kein Wert", sondern je nach Abbruchpunkt eine
       Ausnahme ODER ein teilgelesener Unsinnswert.
    2. **Fehlender/abweichender `GPSLatitudeRef`/`GPSLongitudeRef` verwirft die Koordinate**, kein
       stiller Default auf `N`/`E`. Die Referenz zu raten spiegelte eine Suedhalbkugel-Aufnahme
       wortlos auf die Nordhalbkugel - "kein Ort" ist ueberall sauber behandelt, "falscher Ort"
       nirgends.
    3. **Das exakte Paar `(0.0, 0.0)` wird verworfen.** Geraete schreiben es bei fehlgeschlagenem
       Fix; es liegt im gueltigen Bereich und risse sein Cluster bei 500 m Trennabstand gleich
       ZWEIMAL auf (beim Hinein- und beim Hinauslaufen). Der reale Punkt im Golf von Guinea ist
       der bewusst in Kauf genommene, dokumentierte Verlust.

    `photo_id` dient AUSSCHLIESSLICH der Logzeile (siehe `_log_discarded_gps`) und hat keinen
    Einfluss auf das Ergebnis - deshalb optional, damit die Funktion ohne Kontext testbar bleibt.
    """
    try:
        image = Image.open(io.BytesIO(content))
        gps_ifd = image.getexif().get_ifd(IFD.GPSInfo)
    except Exception:
        return None

    if not gps_ifd:
        # Der Normalfall (kein GPS im EXIF) ist kein Befund und erzeugt keine Logzeile.
        return None

    try:
        lat_ref = _normalized_ref(gps_ifd.get(_GPS_LATITUDE_REF_TAG), ("N", "S"))
        lon_ref = _normalized_ref(gps_ifd.get(_GPS_LONGITUDE_REF_TAG), ("E", "W"))
        if lat_ref is None or lon_ref is None:
            _log_discarded_gps(photo_id, _GPS_REASON_REF_MISSING)
            return None

        latitude = _decimal_degrees(gps_ifd.get(_GPS_LATITUDE_TAG), lat_ref, "S")
        longitude = _decimal_degrees(gps_ifd.get(_GPS_LONGITUDE_TAG), lon_ref, "W")
    except Exception:
        _log_discarded_gps(photo_id, _GPS_REASON_NOT_NUMERIC)
        return None

    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        _log_discarded_gps(photo_id, _GPS_REASON_OUT_OF_RANGE)
        return None

    if latitude == 0.0 and longitude == 0.0:
        _log_discarded_gps(photo_id, _GPS_REASON_NULL_ISLAND)
        return None

    return latitude, longitude
