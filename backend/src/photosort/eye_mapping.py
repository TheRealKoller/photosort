"""Die Abbildung Eye-SDK-Ausgabe -> Motivstaerken, Dokumentausschluss, Albumstufe, Feinlabels.

Reines Modul, nur Standardbibliothek: es steht neben `motifs.py` und braucht weder eine Session
noch ein Modell.

MEHRERE FASSUNGEN, EINE LAUF-FASSUNG. `MAPPINGS` fuehrt jede aufrufbare Fassung der Zuordnung;
der Eye-Lauf rechnet `MAPPING_VERSION`, die Klassifizierungspruefung die Fassung, die ihre Seite
gespeichert hat. Eine Fassung wird nie geaendert, nur um eine weitere ergaenzt - ein gespeichertes
Ergebnis traegt seine Fassung, und eine still veraenderte Tabelle machte diese Angabe falsch. Der
Node-Teil des Sidecars bleibt dumm: er gibt die SDK-Analyse unveraendert zurueck und rechnet
keine Motive.

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

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from photosort.motifs import MOTIF_REGISTRY

# Die erste Fassung - aufrufbar, damit gespeicherte Pruefseiten und Altergebnisse lesbar bleiben.
MAPPING_VERSION_V1: Final = "eye-4.2.3/v1"

# Die zweite Fassung - seit v3 nicht mehr die Lauf-Fassung, aber unveraendert aufrufbar.
MAPPING_VERSION_V2: Final = "eye-4.2.3/v2"

# Die Lauf-Fassung: mit ihr rechnet der Eye-Lauf, und sie steht in jeder neuen
# `photo_eye_results`-Zeile. Nur der Server setzt sie - nie ein Wert aus Request, Sidecar-Antwort
# oder Umgebung. Ein Wert von dort liesse eine Zeile eine Fassung behaupten, mit der sie nicht
# entstand.
MAPPING_VERSION: Final = "eye-4.2.3/v3"

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

# Die zwoelf Eye-Fotoarten (`kind`), die ein Dokument, eine Bildschirm- oder Grafikabbildung
# benennen. In v1 schliessen sie alle aus; in jeder Fassung fehlen sie als Feinlabel, weil eine
# Fotoart keine Bildinhaltsaussage ist. Die Liste ist geschlossen und wird beim Pin-Wechsel
# nachgeprueft (der Abgleich gegen `eye_meta.json` ist Heimserver-Schritt, siehe
# tests/test_eye_mapping.py).
DOCUMENT_TYPES: Final[frozenset[str]] = frozenset(
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

# Der Ausschluss von v2: nur die Fotoarten, die das Foto SELBST zum Dokument oder Bildschirmbild
# machen. Karte, Whiteboard, Folie, Grafik und die Referenzfotos bleiben eingeschlossen. Exakte
# Mitgliedschaft von `kind`, kein Tag - ein Schild oder Bildschirm im Hintergrund ist ein Tag und
# schliesst deshalb nie aus.
EXCLUDED_TYPES_V2: Final[frozenset[str]] = frozenset(
    {"document", "screenshot", "receipt", "photo_of_screen", "id_card"}
)

# Je Motiv die Eye-Tags, die es in v1 belegen - WOERTLICH aus dem SDK-Vokabular
# (`@desert-ant-labs/eye/tags.js`, erzeugt aus `eye_meta.json`). Die Reihenfolge hat keine
# Bedeutung fuer das Ergebnis (die Staerke ist ein Maximum). Ein Name ausserhalb des Vokabulars
# feuerte nie und liefert still Nullen: `eye/test/tags.test.js` prueft
# `eye/src/pins.json::mappingTags` gegen `tags.js`, `tests/test_eye_mapping.py` die Vereinigung
# aller Tabellen gegen `mappingTags`.
MOTIF_TAGS_V1: Final[Mapping[str, tuple[str, ...]]] = {
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

# v2 aendert gegenueber v1 genau zwei Motive; die uebrigen sechs Listen sind dieselben Objekte.
# Tiere: die vier Arten plus die Oberbegriffe und Tierklassen des Vokabulars (dazu
# `motif_detections`). Aktivitaet: Taetigkeiten - keine Gegenstaende, Orte oder Kleidung
# (`surfboard`, `stadium`, `swimming_pool`, `swimwear`), kein Zuschauersport (`horse_racing`,
# `motorsport`), kein `sailboat`, kein `chess`.
MOTIF_TAGS_V2: Final[Mapping[str, tuple[str, ...]]] = {
    **MOTIF_TAGS_V1,
    "tiere": (
        "dog",
        "cat",
        "bird",
        "horse",
        "animal",
        "pet",
        "wildlife",
        "insect",
        "reptile",
        "fish",
        "marine_mammal",
    ),
    "aktivitaet": (
        *MOTIF_TAGS_V1["aktivitaet"],
        "hiking",
        "walking",
        "running",
        "cross_country_running",
        "ultramarathon",
        "track_and_field_athletics",
        "skiing",
        "snowboarding",
        "ice_skating",
        "water_skiing",
        "cycle_sport",
        "racing_bicycle",
        "dance",
        "playground",
        "sports",
        "volleyball_sport",
        "baseball_sport",
        "american_football",
        "golf",
        "hockey",
        "bowling",
        "canoe",
    ),
}

# v3 zaehlt nur DEFINIERENDE Signale: ein Tag belegt ein Motiv nur, wenn er das Motiv selbst
# benennt. Gegenstaende (`car`, `bus`, `building`, `furniture`, `bicycle`, `football`), reine
# Umgebungsbedingungen (`sky`, `cloud`, `sunset`, `water`) und Oberbegriffe ohne Art
# (`animal`, `pet`, `wildlife`) entfallen; benannte Arten und Klassen kommen hinzu. `menschen`,
# `bauwerk_sehenswuerdigkeit` und `essen_trinken` bleiben dieselben Objekte wie in v2.
MOTIF_TAGS_V3: Final[Mapping[str, tuple[str, ...]]] = {
    **MOTIF_TAGS_V2,
    "landschaft": (
        "beach",
        "field",
        "forest",
        "grassland",
        "hill",
        "lake",
        "landscape",
        "mountain",
        "mountain_range",
        "ocean",
        "river",
        "sea",
        "shore",
        "coast",
    ),
    "stadt_strasse": (
        "street",
        "road",
        "city",
        "town",
        "sidewalk",
        "traffic_light",
        "street_light",
        "traffic_sign",
        "pedestrian",
        "cityscape",
        "metropolis",
        "metropolitan_area",
        "urban_area",
        "neighbourhood",
        "skyline",
    ),
    "detail_stimmung": ("flower", "leaf", "blossom"),
    "tiere": (
        "antelope",
        "bear",
        "bee",
        "beetle",
        "bird",
        "black_cat",
        "border_collie",
        "bulldog",
        "butterfly",
        "cat",
        "cattle",
        "deer",
        "dog",
        "dolphin",
        "dragonfly",
        "duck",
        "eagle",
        "elephant",
        "english_cocker_spaniel",
        "falcon",
        "fish",
        "frog",
        "giraffe",
        "goat",
        "golden_retriever",
        "goose",
        "harbor_seal",
        "horse",
        "insect",
        "labrador_retriever",
        "lion",
        "lizard",
        "maine_coon",
        "marine_mammal",
        "monkey",
        "norwegian_forest_cat",
        "owl",
        "parrot",
        "penguin",
        "pig",
        "poodle",
        "pug",
        "rabbit",
        "reptile",
        "sea_lion",
        "sheep",
        "siamese",
        "snake",
        "spider",
        "squirrel",
        "swan",
        "tiger",
        "turtle",
    ),
    "aktivitaet": (
        "swimming",
        "ski",
        "surfing",
        "basketball_sport",
        "tennis",
        "hiking",
        "walking",
        "running",
        "cross_country_running",
        "ultramarathon",
        "track_and_field_athletics",
        "skiing",
        "snowboarding",
        "ice_skating",
        "water_skiing",
        "cycle_sport",
        "racing_bicycle",
        "dance",
        "playground",
        "sports",
        "volleyball_sport",
        "baseball_sport",
        "american_football",
        "golf",
        "hockey",
        "bowling",
        "canoe",
    ),
}

# Die Support-Bedingung je Motiv: hat ein Motiv hier einen Eintrag, zaehlt es nur, wenn mindestens
# einer dieser Tags `tag_confidence` erreicht; sonst ist seine Staerke 0.0. Die Staerke selbst
# bleibt das Maximum der Motivsignale - der Support hebt sie nicht an. Ein leerer Eintrag ist
# unzulaessig, weil er das Motiv dauerhaft auf 0.0 schloesse.
MOTIF_SUPPORT_V3: Final[Mapping[str, tuple[str, ...]]] = {
    "aktivitaet": (
        "people",
        "person",
        "man",
        "woman",
        "boy",
        "girl",
        "child",
        "crowd",
        "human_face",
        "portrait",
        "group_shot",
        "selfie",
        "adolescent",
        "baby",
        "toddler",
        "senior_citizen",
    ),
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


@dataclass(frozen=True)
class EyeMapping:
    """EINE Fassung der Zuordnung - die Tabelle, gegen die ein gespeichertes Ergebnis gelesen
    wird.

    Die Fassung ist eine Zusage ueber das Ergebnis, nicht nur eine Versionsnummer: eine spaetere
    Tabelle bekommt einen eigenen Schluessel, und die alte bleibt unveraendert aufrufbar
    (`MAPPINGS`). Deshalb stehen die Tabellen hier als Feld und nicht als Modulglobale, die eine
    kuenftige Fassung ueberschreiben muesste.

    `motif_detections` nennt je Motiv eine Detektionsliste der SDK-Antwort (`pets`), deren
    groesste `confidence` neben den Tags in das Maximum eingeht. `excluded_types` entscheidet den
    Ausschluss, `fine_label_excluded` die Tags, die nie Feinlabel werden - getrennt, damit ein
    schmalerer Ausschluss die Feinlabels nicht veraendert. `motif_support` ist die Support-
    Bedingung: hat ein Motiv dort einen Eintrag, gilt es nur, wenn mindestens einer dieser Tags
    `tag_confidence` erreicht - sonst ist seine Staerke 0.0. Leer ist die Abbildung, wo es keine
    Bedingung gibt.
    """

    motif_tags: Mapping[str, tuple[str, ...]]
    motif_detections: Mapping[str, str]
    excluded_types: frozenset[str]
    fine_label_excluded: frozenset[str]
    album_levels: tuple[tuple[int, float, float], ...]
    tag_confidence: float
    motif_support: Mapping[str, tuple[str, ...]]


MAPPING_V1: Final[EyeMapping] = EyeMapping(
    motif_tags=MappingProxyType(MOTIF_TAGS_V1),
    motif_detections=MappingProxyType({}),
    excluded_types=DOCUMENT_TYPES,
    fine_label_excluded=DOCUMENT_TYPES,
    album_levels=ALBUM_LEVELS,
    tag_confidence=TAG_CONFIDENCE,
    motif_support=MappingProxyType({}),
)

MAPPING_V2: Final[EyeMapping] = EyeMapping(
    motif_tags=MappingProxyType(MOTIF_TAGS_V2),
    motif_detections=MappingProxyType({"tiere": "pets"}),
    excluded_types=EXCLUDED_TYPES_V2,
    fine_label_excluded=DOCUMENT_TYPES,
    album_levels=ALBUM_LEVELS,
    tag_confidence=TAG_CONFIDENCE,
    motif_support=MappingProxyType({}),
)

MAPPING_V3: Final[EyeMapping] = EyeMapping(
    motif_tags=MappingProxyType(MOTIF_TAGS_V3),
    motif_detections=MappingProxyType({"tiere": "pets"}),
    excluded_types=EXCLUDED_TYPES_V2,
    fine_label_excluded=DOCUMENT_TYPES,
    album_levels=ALBUM_LEVELS,
    tag_confidence=TAG_CONFIDENCE,
    motif_support=MappingProxyType(MOTIF_SUPPORT_V3),
)

# Die aufrufbaren Fassungen. Eine neue Tabelle kommt als zusaetzlicher Eintrag hinzu, nie als
# Ersatz; die Klassifizierungspruefung bietet jede davon an und nimmt nur diese Schluessel an.
MAPPINGS: Final[Mapping[str, EyeMapping]] = MappingProxyType(
    {MAPPING_VERSION_V1: MAPPING_V1, MAPPING_VERSION_V2: MAPPING_V2, MAPPING_VERSION: MAPPING_V3}
)

_RUN_MAPPING: Final = MAPPINGS[MAPPING_VERSION]

# Die Beschreibung der LAUF-Fassung.
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
                "motivstaerken": MappingProxyType(
                    {
                        "signals": ("tags", "pets"),
                        "motifs": _RUN_MAPPING.motif_tags,
                        "detections": _RUN_MAPPING.motif_detections,
                        "support": _RUN_MAPPING.motif_support,
                        "support_threshold": _RUN_MAPPING.tag_confidence,
                    }
                ),
                "ausschluss": MappingProxyType(
                    {"signals": ("kind",), "excluded_types": _RUN_MAPPING.excluded_types}
                ),
                "albumtauglichkeit": MappingProxyType(
                    {"signals": ("scores.aesthetic",), "levels": _RUN_MAPPING.album_levels}
                ),
                "feinlabels": MappingProxyType(
                    {"signals": ("tags",), "excluded_types": _RUN_MAPPING.fine_label_excluded}
                ),
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


def _confidence(value: Any) -> float:
    """Ein Fremdwert aus der SDK-Antwort als Konfidenz in [0, 1] - fuer Tag-Werte UND die
    `confidence` eines `pets`-Eintrags dieselbe Regel.

    Nur `int`/`float` zaehlen (`bool` nicht). Ein NICHT-ENDLICHER Wert - NaN, ±Unendlich, eine
    Ganzzahl jenseits des float-Bereichs, die `json.loads` alle annimmt - wird verworfen (0),
    nicht geklemmt: er ist keine Aussage, und aus einem Defekt entstuende sonst eine Hoechststaerke
    oder ein `OverflowError`, der die Eye-Phase abbricht. Endliche Werte werden geklemmt."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        number = float(value)
    except OverflowError:
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return min(1.0, max(0.0, number))


def _tags(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Die Tag-Konfidenzen stehen in der JSON-Form des SDK (`Analysis.toJSON()`) unter `tags`.

    `confidences` ist nur der Name der JS-Eigenschaft und kommt im JSON nie vor; wer ihn liest,
    bekommt still acht Nullen und keine Feinlabels."""
    tags = payload.get("tags")
    return tags if isinstance(tags, Mapping) else {}


def _detection_confidence(payload: Mapping[str, Any], field: str) -> float:
    """Die groesste `confidence` einer Detektionsliste (`pets`), sonst 0.

    Fremdeingabe: gelesen nur, wenn das Feld eine Liste ist; ein Eintrag zaehlt nur als Objekt,
    seine `confidence` laeuft durch `_confidence`. Nur die oberste Listenebene, keine Rekursion;
    Label, Box und uebrige Felder werden nie gelesen und verlassen diese Funktion nicht - sonst
    stuende ungesaeuberter Fremdtext in Datenbank oder Oberflaeche.
    """
    detections = payload.get(field)
    if not isinstance(detections, list):
        return 0.0
    return max(
        (
            _confidence(entry.get("confidence"))
            for entry in detections
            if isinstance(entry, Mapping)
        ),
        default=0.0,
    )


def motif_strengths(payload: Mapping[str, Any], mapping: EyeMapping) -> dict[str, float]:
    """Je Motiv die GROESSTE Konfidenz seiner Signale, alle acht Registry-Schluessel.

    Signale sind die zugeordneten Tags (`mapping.motif_tags`) und, wo die Fassung es nennt, eine
    Detektionsliste (`mapping.motif_detections`, in v2 `pets` fuer Tiere). Keine Gesichter, kein
    Bildausschnitt: diese beiden Felder sind die einzige Stelle, an der festgelegt ist, was ein
    Motiv belegt. Eine zweite Regel daneben (etwa "ein Gesicht genuegt") liefe beim naechsten
    Pin-Wechsel auseinander.

    `mapping.motif_support` gatet ein Motiv danach: hat es einen Eintrag, zaehlt es nur, wenn
    mindestens einer dieser Tags `tag_confidence` erreicht - sonst 0.0. Die Schwelle ist
    dieselbe, inklusiv wie bei den Feinlabels; eine eigene Support-Schwelle gibt es nicht."""
    tags = _tags(payload)
    strengths: dict[str, float] = {}
    for motif_key in MOTIF_REGISTRY:
        strength = max(
            (_confidence(tags.get(tag)) for tag in mapping.motif_tags.get(motif_key, ())),
            default=0.0,
        )
        field = mapping.motif_detections.get(motif_key)
        if field is not None:
            strength = max(strength, _detection_confidence(payload, field))
        support = mapping.motif_support.get(motif_key)
        if support is not None and not any(
            _confidence(tags.get(tag)) >= mapping.tag_confidence for tag in support
        ):
            strength = 0.0
        strengths[motif_key] = strength
    return strengths


def is_excluded(payload: Mapping[str, Any], mapping: EyeMapping) -> bool:
    """`kind` in der Ausschlussmenge der Fassung heisst "Eye schliesst aus" - exakte
    Mitgliedschaft eines Textes, Tags spielen keine Rolle. Ein fehlendes, unbekanntes oder
    nicht-textuelles `kind` schliesst NICHTS aus - die Abwesenheit einer Typangabe ist keine
    Dokumentaussage."""
    kind = payload.get("kind")
    return isinstance(kind, str) and kind in mapping.excluded_types


def album_level(payload: Mapping[str, Any], mapping: EyeMapping) -> int:
    """Die Albumstufe 1..5 aus `scores.aesthetic` in festen Baendern.

    Fehlt der Wert, gibt es KEINE Stufe - und weil die Ergebnistabelle NOT NULL fuehrt, ist das
    ein `EyeMappingError` und kein erfundenes `1`."""
    scores = payload.get("scores")
    aesthetic = scores.get("aesthetic") if isinstance(scores, Mapping) else None
    if isinstance(aesthetic, bool) or not isinstance(aesthetic, (int, float)):
        raise EyeMappingError("Die Eye-Antwort enthaelt keine Albumstufe.")
    note = min(1.0, max(0.0, float(aesthetic)))
    for level, lower, upper in mapping.album_levels:
        if lower <= note < upper or (upper == 1.0 and note == 1.0):
            return level
    raise EyeMappingError("Die Eye-Antwort enthaelt keine gueltige Albumstufe.")


def fine_labels(payload: Mapping[str, Any], mapping: EyeMapping) -> tuple[tuple[str, float], ...]:
    """Die Tags ab `mapping.tag_confidence`, absteigend nach Konfidenz, bei Gleichstand
    alphabetisch.

    Die Reihenfolge ist eine Zusage DIESER Funktion, nicht der SDK-Antwort: die Anzeige kuerzt am
    Ende, und ohne feste Ordnung fiele die Auswahl bei gleichem Wert von Lauf zu Lauf anders aus.
    Die Fotoarten (`mapping.fine_label_excluded`) fehlen hier - sie sind keine
    Bildinhaltsaussage."""
    tags = _tags(payload)
    labeled = [
        (tag, confidence)
        for tag in tags
        if isinstance(tag, str) and tag not in mapping.fine_label_excluded
        for confidence in (_confidence(tags.get(tag)),)
        if confidence >= mapping.tag_confidence
    ]
    labeled.sort(key=lambda entry: (-entry[1], entry[0]))
    return tuple(labeled)


def analyze(payload: Mapping[str, Any], version: str) -> EyeAnalysis:
    """Die ganze Abbildung in einem Aufruf - die Form, die der Schreibpfad braucht.

    `version` waehlt die Fassung (`MAPPINGS`) und hat KEINEN Default: der Eye-Lauf uebergibt
    `MAPPING_VERSION`, die Pruefung die gespeicherte Fassung ihrer Seite. Eine unbekannte Fassung
    ist ein `EyeMappingError` und kein Rueckfall: das Ergebnis traegt die Fassung in seiner Zeile,
    und ein still gerechneter Ersatz machte diese Angabe falsch."""
    mapping = MAPPINGS.get(version)
    if mapping is None:
        raise EyeMappingError(f"Unbekannte Fassung der Eye-Zuordnung: {version!r}")
    return EyeAnalysis(
        motif_strengths=motif_strengths(payload, mapping),
        excluded_document=is_excluded(payload, mapping),
        album_level=album_level(payload, mapping),
        fine_labels=fine_labels(payload, mapping),
    )
