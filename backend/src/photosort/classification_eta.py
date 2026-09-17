"""Die geschätzte Restdauer des laufenden Teilschritts eines Klassifizierungslaufs.

Reine Funktion: keine Datenbank, keine Uhr, `now` als Parameter. Die Zuordnung "welcher Zähler
gehört zu welchem Teilschritt" steht beim Aufrufer (`api/projects.py`), nicht hier.

Gerechnet wird der Durchsatz **seit Beginn des Teilschritts**, nicht der eines gleitenden
Fensters (ADR 0116 Punkt 2): Ein Fenster bildete jede kurze Schwankung ab, und genau die soll die
Anzeige nicht zeigen.
"""

from __future__ import annotations

from datetime import datetime

# Die beiden Schwellen der Belastbarkeit (ADR 0116 Punkt 3). Unterhalb einer von beiden ist das
# Ergebnis `None` - "noch nicht abschätzbar", nie "keine Restdauer" und nie "sofort fertig".
#
# Drei Einheiten, weil die erste Einheit einen Modellaufbau mitträgt und der daraus gerechnete
# Durchsatz für den gesamten Rest gälte. Fünfzehn Sekunden, weil der erste Poll zwei Sekunden nach
# dem Auslösen kommt und eine dort gerechnete Zahl im selben Takt wieder anders aussähe.
MIN_PROCESSED_UNITS = 3
MIN_ELAPSED_SECONDS = 15.0


def remaining_seconds(
    *,
    phase_started_at: datetime | None,
    now: datetime,
    processed: int | None,
    total: int | None,
) -> float | None:
    """Die geschätzte Restdauer des Teilschritts in Sekunden, oder `None`.

    `None` heißt ausschließlich "noch nicht abschätzbar" und entsteht an genau vier Stellen:
    kein gespeicherter Phasenbeginn, kein bekannter Nenner größer null, weniger als
    `MIN_PROCESSED_UNITS` verarbeitete Einheiten, weniger als `MIN_ELAPSED_SECONDS` seit
    Phasenbeginn. Dazu der Sonderfall `now < phase_started_at`.

    **Jede Schwellenprüfung steht VOR der Division, nicht daneben.** Diese Funktion läuft im
    Lesepfad JEDER Projektantwort (`GET /projects`, `GET /projects/{id}`), im Zwei-Sekunden-Takt
    des Pollings. Ein unbehandelter `ZeroDivisionError` nähme dort nicht das Feld, sondern die
    gesamte Projektübersicht mit (HTTP 500). Ein umschließendes `except Exception: return None`
    ist ausdrücklich **kein** zulässiger Ersatz für diese Reihenfolge: Es deckte jeden anderen
    Rechenfehler mit zu, die Anzeige stünde dauerhaft auf "wird noch ermittelt", und die Ursache
    wäre aus der Antwort nicht mehr zu erkennen. Eine unerwartete Eingabe scheitert deshalb laut
    (tests/test_classification_eta.py).

    Zwei Randfälle mit festgelegtem Ergebnis:

    - `processed >= total` ergibt `0.0`. "Wird noch ermittelt", wenn die Arbeit faktisch fertig
      ist, wäre die falschere Aussage - ein negativer Betrag erst recht.
    - `now < phase_started_at` (Uhr-Rückschritt) ergibt `None`, nicht einen Betrag: Die
      Messgrundlage ist ungültig, nicht die Restdauer kurz.
    """
    if phase_started_at is None:
        return None
    if total is None or total <= 0:
        return None
    if processed is None or processed < MIN_PROCESSED_UNITS:
        return None

    elapsed = (now - phase_started_at).total_seconds()
    if elapsed < 0:
        return None
    if elapsed < MIN_ELAPSED_SECONDS:
        return None

    if processed >= total:
        return 0.0
    return (total - processed) * elapsed / processed
