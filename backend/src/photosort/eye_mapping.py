"""Die Abbildung Eye-SDK-Ausgabe -> Motivstaerken, Dokumentausschluss, Albumstufe, Feinlabels.

Spec 0609 / ADR 0138 Punkt 3. Reines Modul, nur Standardbibliothek: es steht neben `motifs.py`
und braucht weder eine Session noch ein Modell.

GENAU EINE ZUORDNUNGSTABELLE. Sie ist der Port von `tools/eye-eval/src/mapping.js` und
`signals.js` des entfallenen Auswertungswerkzeugs; das Werkzeug ist geloescht, damit Lauf und
Vergleich nicht zwei Tabellen fuehren, die auseinanderlaufen. Der Node-Teil des Sidecars bleibt
dumm: er gibt die SDK-Analyse unveraendert zurueck und rechnet keine Motive.

WAS HIER NICHT PASSIERT, und warum:

* Keine Sanierung der Feinlabel-Texte. Der Text ist fremder Modelltext und wird am Parser mit
  `cloud_vision._sanitize_label_text` saniert und laengenbegrenzt (Spec 0609, S12) - dieses Modul
  importiert aber bewusst nichts aus dem Anwendungscode.
* Kein Vergleich und kein Urteil. Ob Eye oder Cloud "recht hat", ist Story #610; hier entstehen
  nur Eyes eigene Aussagen.
* Kein Nachladen der Pin-Dateien. Die Modellrevision steht als Konstante in `MODEL_REVISION` und
  wird in `photo_eye_results.model_revision` mitgeschrieben; der Pin-Abgleich selbst gehoert zum
  Sidecar (`eye/src/pins.json`) und zum Heimserver-Schritt (`eye_meta.json`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from photosort.motifs import MOTIF_REGISTRY

# Die Fassung der Zuordnung, wie sie das entfallene Werkzeug in seinen Arbeitsbereich schrieb.
MAPPING_VERSION: Final = "eye-4.2.3/v1"

# Die Revision des gepinnten Modells (`eye/src/pins.json`). Sie steht in jeder
# `photo_eye_results`-Zeile, damit ein Pin-Wechsel nicht still unter bestehenden Ergebnissen
# laeuft (ADR 0138 Punkt 2).
MODEL_REVISION: Final = "v1.0.0"

# Die Schwellen der Zuordnung. `tag_confidence` ist die Grenze, ab der ein Tag als Motivbeleg
# zaehlt UND als Feinlabel erscheint; `motif_present` BESCHREIBT die Grenze, ab der eine Staerke
# als "trifft zu" gilt - entschieden wird sie in `selection.py::motif_is_present`, und ein Test
# haelt beide Zahlen zusammen. Diese Tabelle fliesst in die veroeffentlichte
# `EYE_PURPOSE_MAPPING`; sie ist eine Beschreibung, keine zweite Auswahlregel.
TAG_CONFIDENCE: Final = 0.5
MOTIF_PRESENT: Final = 0.5

# Die Eye-Typen, die als Dokument oder Bildschirmabbildung gelten. `kind` in dieser Liste heisst
# "Eye schliesst aus"; die Liste ist geschlossen und wird beim Pin-Wechsel nachgeprueft (der
# Abgleich gegen `eye_meta.json` ist Heimserver-Schritt, siehe tests/test_eye_mapping.py).
EXCLUDED_TYPES: Final[frozenset[str]] = frozenset(
    {
        "document",
        "screenshot",
        "receipt",
        "id_card",
        "whiteboard",
        "chart_or_slide",
        "map",
        "photo_of_screen",
        "medical_reference",
        "repair_reference",
        "shopping_reference",
        "meme_or_graphic",
    }
)

# Je Motiv die Eye-Tags, die es belegen - WOERTLICH aus dem SDK-Vokabular
# (`@desert-ant-labs/eye/tags.js`, erzeugt aus `eye_meta.json`). Die Reihenfolge ist die des
# entfallenen Werkzeugs und hat keine Bedeutung fuer das Ergebnis (die Staerke ist ein Maximum).
#
# Die Tabelle des Werkzeugs fuehrte 15 Namen, die im SDK-Vokabular NICHT vorkommen und deshalb nie
# gefeuert haetten: `arch`, `bridge`, `basketball`, `coffee`, `dancing`, `desert`, `dish`,
# `interior`, `mosque`, `museum`, `palace`, `restaurant`, `sunrise`, `tableware`, `valley`. Fuenf
# davon sind auf den SDK-Namen derselben Sache umgestellt (`architecture`, `bridge_structure`,
# `basketball_sport`, `coffee_cup`, `coffee_drink`); die uebrigen elf sind gestrichen, weil das
# Vokabular - und auch das Anzeigevokabular unter `labels.scenes` - keine Entsprechung fuehrt.
# Beides haelt `eye/test/tags.test.js` gegen `tags.js` und `tests/test_eye_mapping.py` gegen
# `eye/src/pins.json::mappingTags` fest.
MOTIF_TAGS: Final[dict[str, tuple[str, ...]]] = {
    "menschen": ("people", "portrait", "group_shot", "selfie"),
    "landschaft": (
        "beach",
        "mountain",
        "sky",
        "forest",
        "lake",
        "river",
        "coast",
        "cloud",
        "sunset",
        "water",
        "sea",
        "field",
    ),
    "bauwerk_sehenswuerdigkeit": (
        "building",
        "tower",
        "skyscraper",
        "bridge_structure",
        "castle",
        "church",
        "temple",
        "monument",
        "fountain",
        "architecture",
        "lighthouse",
        "ruins",
        "stadium",
    ),
    "stadt_strasse": (
        "street",
        "road",
        "city",
        "town",
        "sidewalk",
        "traffic_light",
        "car",
        "bus",
        "building",
    ),
    "tiere": ("dog", "cat", "bird", "horse"),
    "essen_trinken": (
        "food",
        "drink",
        "coffee_cup",
        "coffee_drink",
        "cake",
        "bread",
        "fruit",
        "plate",
        "cocktail",
    ),
    "aktivitaet": (
        "bicycle",
        "football",
        "soccer",
        "swimming",
        "ski",
        "surfing",
        "skateboard",
        "basketball_sport",
        "tennis",
    ),
    "detail_stimmung": ("flower", "leaf", "furniture"),
}

# Feste Albumbaender: untere Grenze inklusiv, obere exklusiv, die letzte Stufe nimmt 1.0 mit. Die
# Grenzen stehen hier EINMAL - der Vergleich (Story #610) liest dieselbe Stufe ueber
# `album_level()`.
ALBUM_LEVELS: Final[tuple[tuple[int, float, float], ...]] = (
    (1, 0.0, 0.2),
    (2, 0.2, 0.4),
    (3, 0.4, 0.6),
    (4, 0.6, 0.8),
    (5, 0.8, 1.0),
)

EYE_PURPOSE_MAPPING: Final[Mapping[str, Any]] = MappingProxyType(
    {
        "version": MAPPING_VERSION,
        "model_revision": MODEL_REVISION,
        "thresholds": MappingProxyType(
            {
                "tag_confidence": TAG_CONFIDENCE,
                "motif_present": MOTIF_PRESENT,
            }
        ),
        "purposes": MappingProxyType(
            {
                "motivstaerken": MappingProxyType({"signals": ("tags",), "motifs": MOTIF_TAGS}),
                "ausschluss": MappingProxyType(
                    {"signals": ("kind",), "excluded_types": EXCLUDED_TYPES}
                ),
                "albumtauglichkeit": MappingProxyType(
                    {"signals": ("scores.aesthetic",), "levels": ALBUM_LEVELS}
                ),
                "feinlabels": MappingProxyType({"signals": ("tags",)}),
            }
        ),
    }
)


class EyeMappingError(ValueError):
    """Die SDK-Antwort traegt eine Aussage nicht, die eine Pflichtspalte braucht.

    Bewusst ein Fehler und kein Ersatzwert: eine erfundene Albumstufe oder ein erfundenes
    `excluded_document` waere eine Aussage, die das Modell nie getroffen hat. Der Aufrufer
    behandelt das wie einen Transportfehler (Phase bricht ab, keine Promotion)."""


@dataclass(frozen=True)
class EyeAnalysis:
    """Eyes Aussagen zu EINEM Foto - die Eingabe des Schreibpfads.

    `motif_strengths` ist IMMER vollstaendig: alle acht Registry-Schluessel, was Eye nicht nennt
    steht mit `0.0` darin. `fine_labels` ist die absteigend sortierte Liste der Tags ab
    `TAG_CONFIDENCE` als `(roher Tag, Konfidenz)` - ungekuerzt, ungefiltert, unsaniert."""

    motif_strengths: dict[str, float]
    excluded_document: bool
    album_level: int
    fine_labels: tuple[tuple[str, float], ...]


def _confidence(tags: Mapping[str, Any], tag: str) -> float:
    value = tags.get(tag)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    if number != number:  # NaN
        return 0.0
    return min(1.0, max(0.0, number))


def _tags(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Die Tag-Konfidenzen stehen in der JSON-Form des SDK (`Analysis.toJSON()`) unter `tags`.

    `confidences` ist nur der Name der JS-Eigenschaft und kommt im JSON nie vor; wer ihn liest,
    bekommt still acht Nullen und keine Feinlabels."""
    tags = payload.get("tags")
    return tags if isinstance(tags, Mapping) else {}


def motif_strengths(payload: Mapping[str, Any]) -> dict[str, float]:
    """Je Motiv die GROESSTE Konfidenz seiner zugeordneten Tags, alle acht Registry-Schluessel.

    Nur Tags, keine Gesichter, keine Tiere, kein Bildausschnitt: die Staerke ist eine Aussage
    ueber den Bildinhalt, und `MOTIF_TAGS` ist die einzige Stelle, an der festgelegt ist, welcher
    Tag welches Motiv belegt. Eine zweite Regel daneben (etwa "ein Gesicht genuegt") liefe beim
    naechsten Pin-Wechsel auseinander."""
    tags = _tags(payload)
    return {
        motif_key: max(
            (_confidence(tags, tag) for tag in MOTIF_TAGS.get(motif_key, ())), default=0.0
        )
        for motif_key in MOTIF_REGISTRY
    }


def is_excluded(payload: Mapping[str, Any]) -> bool:
    """`kind` in der Ausschlussliste heisst "Eye schliesst aus". Ein fehlendes `kind` schliesst
    NICHTS aus - die Abwesenheit einer Typangabe ist keine Dokumentaussage."""
    kind = payload.get("kind")
    return isinstance(kind, str) and kind in EXCLUDED_TYPES


def album_level(payload: Mapping[str, Any]) -> int:
    """Die Albumstufe 1..5 aus `scores.aesthetic` in festen Baendern.

    Fehlt der Wert, gibt es KEINE Stufe - und weil die Ergebnistabelle NOT NULL fuehrt, ist das
    ein `EyeMappingError` und kein erfundenes `1`."""
    scores = payload.get("scores")
    aesthetic = scores.get("aesthetic") if isinstance(scores, Mapping) else None
    if isinstance(aesthetic, bool) or not isinstance(aesthetic, (int, float)):
        raise EyeMappingError("Die Eye-Antwort enthaelt keine Albumstufe.")
    note = min(1.0, max(0.0, float(aesthetic)))
    for level, lower, upper in ALBUM_LEVELS:
        if lower <= note < upper or (upper == 1.0 and note == 1.0):
            return level
    raise EyeMappingError("Die Eye-Antwort enthaelt keine gueltige Albumstufe.")


def fine_labels(payload: Mapping[str, Any]) -> tuple[tuple[str, float], ...]:
    """Die Tags ab `TAG_CONFIDENCE`, absteigend nach Konfidenz, bei Gleichstand alphabetisch.

    Die Reihenfolge ist eine Zusage DIESER Funktion, nicht der SDK-Antwort: die Anzeige kuerzt am
    Ende, und ohne feste Ordnung fiele die Auswahl bei gleichem Wert von Lauf zu Lauf anders aus.
    Die Ausschlusstypen fehlen hier - sie sind bereits die Aussage `excluded_document`, kein
    Feinlabel."""
    tags = _tags(payload)
    labeled = [
        (tag, confidence)
        for tag in tags
        if isinstance(tag, str) and tag not in EXCLUDED_TYPES
        for confidence in (_confidence(tags, tag),)
        if confidence >= TAG_CONFIDENCE
    ]
    labeled.sort(key=lambda entry: (-entry[1], entry[0]))
    return tuple(labeled)


def analyze(payload: Mapping[str, Any]) -> EyeAnalysis:
    """Die ganze Abbildung in einem Aufruf - die Form, die der Schreibpfad braucht."""
    return EyeAnalysis(
        motif_strengths=motif_strengths(payload),
        excluded_document=is_excluded(payload),
        album_level=album_level(payload),
        fine_labels=fine_labels(payload),
    )
