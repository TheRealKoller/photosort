"""Kamera-Identitaet und Zeitversatz: die reinen Rechnungen hinter dem projekteigenen
Zeitversatz je Kamera.

REIN und DB-FREI, Muster `events.py`. Die eine Stelle, die `taken_at` aus `taken_at_original`
errechnet: `shifted` ist die Funktion, ueber die BEIDE Schreibstellen (`worker.py`-Scan und
`api/cameras.py`) laufen - eine dritte Schreibstelle auf `Photo.taken_at` gibt es nicht
(ADR 0090, Punkt 1).

LOGGING-AUFLAGE: `make`/`model` sind Fremdtext aus einer Kamera-Firmware und gehoeren NIE in eine
Logzeile - nur ein festes Grund-Token plus `photo_id`.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

# Laengengrenze je Feld, nicht an der zusammengesetzten Beschriftung: ein laengerer Wert gilt als
# nicht vorhanden. VERWORFEN, nie abgeschnitten - ein gekuerztes Modell waere eine andere Kamera
# (ADR 0090, Punkt 3).
MAX_CAMERA_FIELD_LENGTH = 80

# +/-100 Jahre in Minuten. Die Grenze wird am Endpunkt durchgesetzt (`api/cameras.py`), nicht
# hier: `shifted` und `suggested_offset_minutes` rechnen unbeschraenkt und klemmen nie.
MAX_TIME_OFFSET_MINUTES = 52_560_000

# Die Unicode-Kategorien, deren Zeichen VOR der Leer-/Laengenpruefung entfernt werden: `Cc`
# (Steuerzeichen, darunter NUL und U+0085) und `Cf` (Format, darunter die Bidi-Overrides
# U+202A-U+202E und U+2066-U+2069, Zero-Width U+200B-U+200D sowie U+FEFF).
#
# SICHERHEIT: Der Angriff ist NICHT XSS, sondern die VERWECHSLUNG ZWEIER LISTENZEILEN - die
# Bezeichnung ist das einzige Merkmal, an dem der Nutzer die Kamera auswaehlt, deren Fotos er
# gleich umschreiben laesst. Bei Verletzung: zwei optisch identische Zeilen in der Kameraliste und
# ein Versatz, der auf der falschen Kamera landet, ohne dass etwas es anzeigt. Deshalb ist
# "escapen und anzeigen genuegt" fuer diesen Wert untersagt, obwohl es beim OpenCloud-Dateinamen
# zulaessig ist: dort haengt keine Handlung am angezeigten Text.
_INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf"})


@dataclass(frozen=True)
class CameraIdentity:
    """Hersteller und Modell einer Kamera, beide bereits normalisiert.

    Ein LEERER String heisst "dieses Feld ist nicht vorhanden"; beide leer gibt es nicht - dann
    liefert `camera_identity` `None`. Ohne Seriennummer (ADR 0090, Punkt 3): zwei baugleiche
    Gehaeuse im selben Projekt sind EINE Kamera und teilen einen Versatz."""

    make: str
    model: str


def _normalized_field(raw: object) -> str:
    """Ein einzelnes EXIF-Textfeld nach Normalisierung - `""` heisst "nicht vorhanden".

    Alles, was kein `str` ist, wird VERWORFEN statt umgedeutet: der Wert kommt roh aus einer
    fremden, moeglicherweise entarteten Datei.

    Reihenfolge: unsichtbare Zeichen entfernen, dann Leerraumfolgen zusammenziehen, dann auf leer
    und Laenge pruefen. Das Entfernen steht VOR der Pruefung, weil es eine Normalisierung wie das
    Leerraum-Zusammenziehen ist - bleibt danach nichts Druckbares, gilt das Feld als nicht
    vorhanden."""
    if not isinstance(raw, str):
        return ""
    visible = "".join(
        character
        for character in raw
        if unicodedata.category(character) not in _INVISIBLE_CATEGORIES
    )
    # `split()` ohne Argument zieht jede Leerraumfolge zusammen und trimmt zugleich die Raender.
    # U+2028/U+2029 sind Leerraum (`Zl`/`Zp`) und fallen genau hier, nicht unter das Entfernen.
    collapsed = " ".join(visible.split())
    if len(collapsed) > MAX_CAMERA_FIELD_LENGTH:
        return ""
    return collapsed


def camera_identity(make: object, model: object) -> CameraIdentity | None:
    """Die Identitaet einer Kamera aus den EXIF-Rohwerten `Make` und `Model`.

    `None`, wenn BEIDE Felder nicht vorhanden sind - das heisst "Kamera nicht bestimmbar" und ist
    ein regulaerer Zustand ohne Versatz, kein Fehler."""
    normalized_make = _normalized_field(make)
    normalized_model = _normalized_field(model)
    if not normalized_make and not normalized_model:
        return None
    return CameraIdentity(make=normalized_make, model=normalized_model)


def camera_label(identity: CameraIdentity) -> str:
    """Die Bezeichnung, unter der eine Kamera in Liste, Dialog und Fotodetail erscheint.

    Die Beschriftung entsteht im BACKEND - eine Stelle entscheidet, wie eine Kamera heisst.

    Beginnt `model` (ohne Beachtung der Schreibweise) mit `make`, gilt `model` allein, sonst
    `"make model"`; fehlt eines, gilt das andere."""
    if not identity.make:
        return identity.model
    if not identity.model:
        return identity.make
    if identity.model.lower().startswith(identity.make.lower()):
        return identity.model
    return f"{identity.make} {identity.model}"


def shifted(original: datetime, offset_minutes: int) -> datetime | None:
    """Die wirksame Aufnahmezeit: aufgezeichnete Zeit plus Versatz.

    DIE EINE Stelle, die `taken_at` aus `taken_at_original` errechnet (ADR 0090, Punkt 1).

    `None` statt einer Ausnahme, wenn das Ergebnis ausserhalb des darstellbaren Bereichs liegt:
    der Versatz-Endpunkt weist den Versatz dann zurueck (kein Teilschreiben), der Scan schreibt
    fuer dieses eine Foto die unkorrigierte Zeit und protokolliert das mit festem Grund-Token.
    Ein Versatz von `0` auf einem Rand ist KEIN Ueberlauf und liefert den Rand selbst."""
    try:
        return original + timedelta(minutes=offset_minutes)
    except (OverflowError, OSError, ValueError):
        return None


def suggested_offset_minutes(camera_original: datetime, reference_effective: datetime) -> int:
    """Der aus einem Fotopaar errechnete Versatzvorschlag in ganzen Minuten.

    Bezug ist die AUFGEZEICHNETE Zeit des Kamerafotos und die KORRIGIERTE des Referenzfotos
    (ADR 0090, Punkt 6): rechnete der Vorschlag auf der korrigierten Zeit des Kamerafotos, haenge
    er vom bereits gesetzten Versatz ab und ein zweiter Aufruf schluege etwas anderes vor.

    Gerundet wird auf die naechste Minute, HAELFTEN VOM NULL WEG, ueber ganzzahlige
    Sekundenarithmetik - nicht ueber `round()`: das rundet kaufmaennisch-symmetrisch zur geraden
    Zahl (`round(0.5) == 0`, `round(2.5) == 2`) und lieferte fuer 30 s und 150 s die falschen
    Werte. Das Ergebnis wird NICHT geklemmt; das Zurueckweisen liegt am Endpunkt."""
    total_seconds = round((reference_effective - camera_original).total_seconds())
    sign = -1 if total_seconds < 0 else 1
    return sign * ((abs(total_seconds) + 30) // 60)
