from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from photosort.cloud_vision import _sanitize_label_text

# Die Albumtauglichkeit: eine fuenfstufige Modellaussage mit kurzer Begruendung, erhoben im
# bestehenden Klassifizierungsaufruf. Dieses Modul ist REIN - Stufenband, Ankertexte,
# Prompt-Block, Normierung und Parsing, kein Netz, keine Datenbank.

logger = logging.getLogger(__name__)

ALBUM_SUITABILITY_MIN_LEVEL: Final = 1
ALBUM_SUITABILITY_MAX_LEVEL: Final = 5

# Die vier Maengel, die keine lokale Messung sieht - sie stehen genau hier und gehen von hier aus
# in den Prompt, nicht als zweite Liste im Prompt-Literal daneben.
ALBUM_SUITABILITY_NAMED_FLAWS: Final = (
    "geschlossene Augen",
    "verdeckte Gesichter",
    "angeschnittene Personen",
    "langweilige Komposition",
)

# Ein Ankertext je Stufe. Bewusst ein veraenderbares dict und nicht als Tupel: der Prompt-Block
# entsteht daraus, und ein Test weist ueber eine ersetzte Zeile nach, dass er nicht aus einem
# Literal danebensteht.
ALBUM_SUITABILITY_ANCHORS: dict[int, str] = {
    1: (
        "Fuer ein Album unbrauchbar. Das Hauptmotiv ist verfehlt oder zerstoert - niemand wuerde "
        "dieses Bild aufheben."
    ),
    2: (
        "Schwach. Erkennbar, aber mit einem deutlichen Mangel, der beim Betrachten sofort "
        "auffaellt."
    ),
    3: (
        "Brauchbar. Ordentlich aufgenommen, ohne groben Mangel, aber ohne etwas, das es heraushebt."
    ),
    4: (
        "Gut. Ein Bild, das man ohne Zoegern ins Album nehmen wuerde - Motiv klar, Moment "
        "getroffen."
    ),
    5: (
        "Hervorragend. Das Bild, das man aus einer Serie auswaehlen wuerde: Moment, Ausdruck und "
        "Bildaufbau stimmen zusammen."
    ),
}

# Storage- und Degenerationsgrenze der Begruendung. GEKUERZT statt verworfen - bewusst anders als
# beim Feinlabel: `reason` wird nirgends verglichen, geschluesselt, dedupliziert oder
# slugifiziert, ein gekuerzter Wert fuehrt also keine zwei verschiedenen Dinge zusammen. Wird der
# Text spaeter Gegenstand eines Vergleichs, gilt ab dann die Verwerfensregel (S2).
MAX_ALBUM_SUITABILITY_REASON_LENGTH: Final = 160

# Sentinel fuer "das Antwort-Objekt nennt gar kein `album_suitability`" - unterscheidbar von einem
# gelieferten `null`. Ein FEHLENDES Feld wird still zu "keine Bewertung", ein geliefertes, aber
# unbrauchbares einmal protokolliert. Oeffentlich, weil der Aufrufer in `remote_classification.py`
# ihn als Default seines `.get()` einsetzt.
NO_VALUE: Final = object()

# Sicherheitsauflage S3: FESTE Grund-Tokens statt des Rohwerts. Der Diagnosewert einer verworfenen
# Stufe liegt vollstaendig in der Fehlerklasse; damit enthaelt die Zeile ueberhaupt keinen
# Fremdtext und die Log-Injection-Frage stellt sich nicht.
_REASON_NOT_AN_OBJECT: Final = "kein_objekt"
_REASON_LEVEL_MISSING: Final = "keine_stufe"
_REASON_LEVEL_NOT_INT: Final = "kein_ganzzahltyp"
_REASON_LEVEL_OUT_OF_RANGE: Final = "ausserhalb_stufenband"


@dataclass(frozen=True)
class AlbumSuitability:
    """Die validierte Albumtauglichkeits-Aussage fuer EIN Foto.

    `level` liegt immer im Band `1..5`; ein unbrauchbarer Wert erzeugt gar keine Instanz, nie eine
    geklemmte Stufe. `reason` ist der sanierte, laengenbegrenzte Fremdtext oder `None` - nie eine
    leere Zeichenkette."""

    level: int
    reason: str | None


def normalize_level(level: int) -> float:
    """Die Stufe auf `[0, 1]`: `(Stufe - 1) / 4`. Persistiert wird die STUFE, dieser Wert entsteht
    bei jeder Rechnung neu - eine zweite Spalte daneben waere ein zweiter Ort fuer dieselbe
    Aussage."""
    return (level - ALBUM_SUITABILITY_MIN_LEVEL) / (
        ALBUM_SUITABILITY_MAX_LEVEL - ALBUM_SUITABILITY_MIN_LEVEL
    )


def _log_discarded(photo_id: int, reason: str) -> None:
    """Eine Zeile, WARNING, kein exc_info - der Lauf bleibt erfolgreich, das Foto bekommt keine
    Albumtauglichkeitszeile und bleibt Kandidat des naechsten Laufs.

    Geloggt werden ausschliesslich `photo_id` und eines der festen Grund-Tokens. NIE der Rohwert,
    nie die vollstaendige Antwort, nie Bilddaten - und NIE `reason`, in keiner Laenge und in keiner
    Form: es ist genau der Fremdtext, der aus dem Log herauszuhalten ist (S3)."""
    logger.warning(
        "album_suitability: Stufe verworfen photo_id=%s grund=%s",
        photo_id,
        reason,
    )


def _level_from_raw(raw: object, photo_id: int) -> int | None:
    """Die Stufe aus dem Rohwert - `None` heisst "keine brauchbare Stufe" (Sicherheitsauflage S1).

    Uebernommen wird ausschliesslich ein echter `int` im Band `1 <= level <= 5`:

    - `bool` wird EXPLIZIT vor der `int`-Pruefung ausgeschlossen: `isinstance(True, int)` ist
      `True`, `"level": true` erschiene sonst als Stufe 1 - die schlechteste Aussage, die das
      Produkt kennt, erfunden aus einem Nicht-Wert.
    - `float` faellt durch, auch `4.0`: die Stufe ist ein Anker, kein Messwert. Damit sind
      `NaN`/`+-Infinity` mit ausgeschlossen, die `json.loads` klaglos parst - ein durchgelassener
      entarteter Wert legte ueber Starlettes `allow_nan=False` die gesamte Fotoliste des Projekts
      auf `500`, nicht nur den einen Eintrag.
    - Keine Umdeutung von `"4"`.
    - Ein Wert ausserhalb des Bandes wird VERWORFEN, nie geklemmt - `9 -> 5` waere eine Aussage,
      die das Modell nie getroffen hat."""
    if raw is NO_VALUE:
        _log_discarded(photo_id, _REASON_LEVEL_MISSING)
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        _log_discarded(photo_id, _REASON_LEVEL_NOT_INT)
        return None
    if not ALBUM_SUITABILITY_MIN_LEVEL <= raw <= ALBUM_SUITABILITY_MAX_LEVEL:
        _log_discarded(photo_id, _REASON_LEVEL_OUT_OF_RANGE)
        return None
    return raw


def _reason_from_raw(raw: object) -> str | None:
    """Die Begruendung: sanieren -> messen -> kuerzen, in genau dieser Reihenfolge (S2).

    Die Reihenfolge ist die Auflage: vor der Sanitisierung zu kuerzen liesse einen halbierten
    Bidi-/Zero-Width-Kontext stehen, den die Sanitisierung danach nicht mehr sieht. Saniert wird
    mit `cloud_vision.py::_sanitize_label_text` - DERSELBEN Funktion wie im Feinlabel- und im
    Sehenswuerdigkeit-Pfad, nie einer zweiten Fassung davon.

    Kein String, oder leer nach der Sanitisierung: `None`, nie `""`."""
    if not isinstance(raw, str):
        return None
    sanitized = _sanitize_label_text(raw)
    if not sanitized:
        return None
    return sanitized[:MAX_ALBUM_SUITABILITY_REASON_LENGTH]


def album_suitability_from_json(raw: object, photo_id: int) -> AlbumSuitability | None:
    """Der Parser des `album_suitability`-Feldes - inhaltlich tolerant: ein fehlendes oder
    entartetes Feld ergibt KEINE Bewertung und KEINEN Fehler.

    Ohne brauchbare Stufe entsteht gar keine Zeile, und das Foto bleibt Kandidat des naechsten
    Laufs. Eine unbrauchbare Begruendung neben einer brauchbaren Stufe kostet die Stufe nicht -
    sie wird zu `None`."""
    if raw is NO_VALUE:
        return None
    if not isinstance(raw, dict):
        _log_discarded(photo_id, _REASON_NOT_AN_OBJECT)
        return None

    level = _level_from_raw(raw.get("level", NO_VALUE), photo_id)
    if level is None:
        return None
    return AlbumSuitability(level=level, reason=_reason_from_raw(raw.get("reason")))


def build_album_suitability_prompt_lines() -> list[str]:
    """Der Albumtauglichkeits-Block des Klassifizierungs-Prompts, als Zeilen.

    SICHERHEIT (S4): der Block entsteht ausschliesslich aus dem Code - den fuenf festen
    Stufenankern und der Maengelliste oben. Nie aus Datenbankinhalten und nie aus einer frueheren
    Modellantwort; jeder Rueckkopplungspfad bleibt untersagt."""
    lines = [
        "Beurteile dieses Foto zusaetzlich danach, wie gut es sich fuer ein Fotoalbum eignet.",
        "",
        "Achte dabei ausdruecklich auf das, was eine Messung von Schaerfe und Belichtung NICHT "
        "sieht: " + ", ".join(ALBUM_SUITABILITY_NAMED_FLAWS) + ".",
        "",
        "Die Stufen:",
    ]
    lines.extend(
        f"- {level}: {ALBUM_SUITABILITY_ANCHORS[level]}"
        for level in sorted(ALBUM_SUITABILITY_ANCHORS)
    )
    lines.extend(
        [
            "",
            'Gib das Ergebnis im Feld "album_suitability" an: "level" als ganze Zahl von '
            f"{ALBUM_SUITABILITY_MIN_LEVEL} bis {ALBUM_SUITABILITY_MAX_LEVEL} (nicht als Text, "
            'nicht als Kommazahl) und "reason" als einen kurzen deutschen Satz von hoechstens '
            f"{MAX_ALBUM_SUITABILITY_REASON_LENGTH} Zeichen ohne Zeilenumbruch, der die Stufe "
            "begruendet.",
        ]
    )
    return lines
