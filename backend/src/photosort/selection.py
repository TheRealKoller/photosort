"""Der Auswahlvorschlag: Kontingente je Event und motivgefuehrte Vergabe mit
Aehnlichkeitsabwertung.

REIN und DB-FREI - dasselbe Muster wie `ranking.py`/`quality.py`/`events.py`: keine Session, kein
Modell, kein SQL-Ausdruck. Die Kandidatenmenge kommt fertig herein; wer auswahlfaehig ist,
entscheidet der Aufrufer (`worker.py`).

DETERMINISMUS IST STRUKTURELL, nicht zugesichert: Kandidaten werden beim Eintritt nach `photo_id`
sortiert, Events nach `position` durchlaufen, und jede Wahl des groessten Werts bricht Gleichstand
ueber die kleinere `photo_id` (Konvention aus `ranking.py`). Kein Schritt liest eine
Datenbankreihenfolge, eine Mengeniteration oder eine Uhr.

Die Grenze, ab der ein Motiv als getragen gilt, wohnt HIER und ist fuer alle Motive dieselbe. Sie
ist ausdruecklich keines der Anzeigebaender des Motiv-Vokabulars - ein auswaehlender Codepfad
liest jene nicht (ADR 0091 Punkt 8), sonst entstuende ueber die Bandgrenzen eine Rangfolge
zwischen Motiven. Ein struktureller Waechter in tests/test_selection.py haelt das fest.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

# Die drei Stellschrauben des Verfahrens plus die Vorbelegung des Richtwerts - dokumentiert
# UNKALIBRIERTE Startwerte in der Klasse von `TIME_CLUSTER_GAP` und `LOCAL_CORRECTION_SPAN`. Es
# gibt keinen Fotokorpus im Repository, gegen den ein anderer Wert zu belegen waere; sie zu
# aendern ist eine Zahl hier plus ein Neuaufbau, keine Migration.

# Kein Event bekommt mehr als ein Viertel aller Plaetze - und nie weniger als den gleichen Anteil
# (`max(⌈T/m⌉, ⌈EVENT_SHARE_CAP·T⌉)`), sonst griffe die Kappe bei wenigen Events zwangslaeufig
# immer.
EVENT_SHARE_CAP = 0.25

# Ab dieser wirksamen Staerke gilt ein Motiv als von einem Bild getragen - INKLUSIV und fuer alle
# Motive gleich.
MOTIF_PRESENCE_THRESHOLD = 0.5

# Womit der Wert eines Bildes je bereits gewaehltem, vollstaendig aehnlichem Bild multipliziert
# wird.
SIMILARITY_DECAY = 0.5

# Jenseits dieser Spanne wertet nichts mehr ab; innerhalb laeuft die Zeitnaehe linear aus.
SIMILARITY_TIME_WINDOW = timedelta(minutes=15)

# Der Nenner der Vorbelegung: ohne eingestellten Richtwert umfasst der Vorschlag ein Zehntel der
# Bilderzahl. Diese Zahl steht NUR hier.
DEFAULT_TARGET_DIVISOR = 10

_SIMILARITY_TIME_WINDOW_SECONDS = SIMILARITY_TIME_WINDOW.total_seconds()


@dataclass(frozen=True)
class SelectionCandidate:
    """Ein auswahlfaehiges Bild eines Events.

    `taken_at` ist `datetime` und nicht `datetime | None`: `Photo.taken_at` ist NOT NULL, ein Bild
    ohne Aufnahmezeit gibt es nicht. Ein `| None` an dieser Stelle fuehrte einen Zweig ein, den
    kein Produktivzustand erreicht.

    `quality` ist der fertige `rank_score`; `motif_strengths` sind die WIRKSAMEN Staerken
    (Korrekturen inbegriffen), wie der Aufrufer sie geladen hat. Ein hier fehlendes Motiv zaehlt
    als nicht getragen."""

    photo_id: int
    taken_at: datetime
    quality: float
    motif_strengths: Mapping[str, float]


@dataclass(frozen=True)
class SelectionEvent:
    """Ein Event samt seinen auswahlfaehigen Kandidaten. `position` ist die 1-basierte,
    chronologische Nummer des Events im Lauf und zugleich der Stichentscheid der
    Restverteilung."""

    event_id: int
    position: int
    candidates: Sequence[SelectionCandidate]


def effective_target(configured: int | None, photo_count: int) -> int:
    """Der wirksame Richtwert eines Projekts.

    `None` heisst "nicht selbst eingestellt" und ergibt ein Zehntel der Bilderzahl, aufgerundet
    und mindestens 1 - im Moment der Auswahl berechnet und deshalb mit dem Bestand mitwachsend.
    Eine eingestellte Zahl gilt absolut und unveraendert.

    DIE EINE Ableitungsstelle: die Vorbelegung wird nie in die Spalte geschrieben, ein
    eingeschriebener Vorgabewert waere von einer Nutzereingabe nicht mehr zu unterscheiden."""
    if configured is not None:
        return configured
    return max(1, -(-photo_count // DEFAULT_TARGET_DIVISOR))


def _carried_motifs(candidate: SelectionCandidate) -> frozenset[str]:
    return frozenset(
        key
        for key, strength in candidate.motif_strengths.items()
        if strength >= MOTIF_PRESENCE_THRESHOLD
    )


def _similarity(
    left: SelectionCandidate,
    right: SelectionCandidate,
    left_motifs: frozenset[str],
    right_motifs: frozenset[str],
) -> float:
    """`geteiltes_motiv · zeitnähe` mit `zeitnähe = max(0, 1 − |Δt| / SIMILARITY_TIME_WINDOW)`.

    Das `max(0, …)` ist nicht Kosmetik: ohne es ergaebe der Exponent jenseits des Fensters einen
    negativen Wert und damit einen Faktor GROESSER als 1 - eine Aufwertung gerade der weit
    entfernten Bilder, ohne auffaelliges Fehlerbild.

    Ein eigenes Mass fuer visuelle Aehnlichkeit gibt es nicht; Duplikate und Serien faengt der
    Ausschuss-Schritt ab."""
    if not (left_motifs & right_motifs):
        return 0.0
    gap = abs((left.taken_at - right.taken_at).total_seconds())
    return max(0.0, 1.0 - gap / _SIMILARITY_TIME_WINDOW_SECONDS)


def _largest_remainder(
    ids: Sequence[int], weights: Mapping[int, float], positions: Mapping[int, int], seats: int
) -> dict[int, int]:
    """Groesste-Reste-Verfahren ueber `seats` Plaetze. Der Stichentscheid bei gleichem Rest laeuft
    ueber `position`, nie ueber die Iterationsreihenfolge."""
    total_weight = sum(weights[event_id] for event_id in ids)
    exact = {event_id: seats * weights[event_id] / total_weight for event_id in ids}
    assigned = {event_id: int(exact[event_id]) for event_id in ids}
    leftover = seats - sum(assigned.values())
    by_remainder = sorted(
        ids, key=lambda event_id: (-(exact[event_id] - assigned[event_id]), positions[event_id])
    )
    for event_id in by_remainder[:leftover]:
        assigned[event_id] += 1
    return assigned


def _quotas(events: Sequence[SelectionEvent], target: int) -> dict[int, int]:
    """Stufe 1 - die Kontingente je Event.

    Vier Schritte: Abdeckung zuerst (jedes Event einen Platz, auch wenn der Vorschlag dadurch
    groesser wird als `T`), der Rest nach `√n_i`, Obergrenze `min(n_i, max(⌈T/m⌉, ⌈0,25·T⌉))` mit
    Umverteilung der gekappten Plaetze, und danach uebrige Plaetze verfallen."""
    sizes = {event.event_id: len(event.candidates) for event in events if event.candidates}
    event_count = len(sizes)
    if event_count == 0:
        return {}

    seats = max(0, target)
    positions = {event.event_id: event.position for event in events}
    order = [event.event_id for event in events if event.candidates]

    ceiling = max(1, -(-seats // event_count), math.ceil(EVENT_SHARE_CAP * seats))
    caps = {event_id: min(sizes[event_id], ceiling) for event_id in order}

    # Abdeckung zuerst. `caps` ist ueberall mindestens 1 (jedes Event hier hat einen Kandidaten),
    # die Zuteilung verletzt die Obergrenze also nicht.
    allocation = {event_id: 1 for event_id in order}
    remaining = seats - event_count

    weights = {event_id: math.sqrt(sizes[event_id]) for event_id in order}
    # FESTE Rundenobergrenze statt einer Zeitgrenze: jede Runde vergibt entweder alle
    # verbliebenen Plaetze oder drueckt mindestens ein Event an seine Kappe, aus der es nicht
    # zurueckkehrt. Mehr Runden als Events plus eine kann es deshalb nicht geben.
    for _ in range(event_count + 1):
        if remaining <= 0:
            break
        open_ids = [event_id for event_id in order if allocation[event_id] < caps[event_id]]
        if not open_ids:
            break
        assigned = _largest_remainder(open_ids, weights, positions, remaining)
        placed = 0
        for event_id in open_ids:
            give = min(assigned[event_id], caps[event_id] - allocation[event_id])
            allocation[event_id] += give
            placed += give
        if placed == 0:
            # Unerreichbar: das Groesste-Reste-Verfahren vergibt alle `remaining` Plaetze auf die
            # offenen Events, und ein offenes Event nimmt mindestens einen an. Die Bremse steht
            # trotzdem hier, weil die Alternative eine Endlosschleife in einem synchronen Endpunkt
            # waere.
            break
        remaining -= placed

    return allocation


def _assign_event(candidates: Sequence[SelectionCandidate], seats: int) -> dict[int, int]:
    """Stufe 2 - die motivgefuehrte Vergabe innerhalb EINES Events, unabhaengig von den uebrigen.

    Der Wert eines noch nicht gewaehlten Bildes ist
    `rank_score · SIMILARITY_DECAY ^ Σ_{s gewählt} ähnlichkeit(p, s)`. Jeder Platz geht an das
    Bild mit dem hoechsten Wert - aber solange ein vorkommendes Motiv unvertreten ist, nur aus den
    Bildern, die ein solches Motiv tragen. Das gewaehlte Bild vertritt dann ALLE unvertretenen
    Motive, die es traegt; es wird nie ein Motiv gegen ein anderes abgewogen und keine Staerke mit
    einer anderen verglichen.

    Die Abwertung wird je Kandidat FORTGESCHRIEBEN und nie bei jeder Bewertung erneut ueber alle
    bereits Gewaehlten summiert (Sicherheitsauflage S5). Ergebnisgleich - die Aehnlichkeiten
    stehen additiv im Exponenten -, aber `O(n·k)` statt `O(n·k²)`: bei tausend Kandidaten und
    vollem Kontingent ist das der Unterschied zwischen rund 10⁶ und rund 10⁹ Bewertungen synchron
    im Request."""
    remaining = sorted(candidates, key=lambda candidate: candidate.photo_id)
    motifs_of = {candidate.photo_id: _carried_motifs(candidate) for candidate in remaining}
    present = frozenset().union(*motifs_of.values()) if motifs_of else frozenset()
    decay: dict[int, float] = {candidate.photo_id: 0.0 for candidate in remaining}

    represented: set[str] = set()
    places: dict[int, int] = {}

    for place in range(1, seats + 1):
        if not remaining:
            # Unerreichbar: `seats` ist durch die Obergrenze auf `n_i` begrenzt, es gibt also nie
            # mehr Plaetze als Kandidaten.
            break
        unrepresented = present - represented

        best: SelectionCandidate | None = None
        best_key: tuple[float, int] | None = None
        for candidate in remaining:
            if unrepresented and not (motifs_of[candidate.photo_id] & unrepresented):
                continue
            value = candidate.quality * SIMILARITY_DECAY ** decay[candidate.photo_id]
            # Gleichstand ueber die kleinere `photo_id` - ausgeschrieben als zweiter Schluessel
            # und nicht dem "erstes gesehenes Element gewinnt" von `max` ueberlassen.
            key = (-value, candidate.photo_id)
            if best_key is None or key < best_key:
                best_key = key
                best = candidate
        if best is None:
            # Unerreichbar, solange `present` aus DIESEN Kandidaten entstanden ist: ein
            # vorkommendes Motiv hat per Definition ein Traegerbild, und ist dieses gewaehlt, gilt
            # das Motiv als vertreten.
            break

        places[best.photo_id] = place
        chosen_motifs = motifs_of[best.photo_id]
        represented |= chosen_motifs

        still_open: list[SelectionCandidate] = []
        for candidate in remaining:
            if candidate.photo_id == best.photo_id:
                continue
            similarity = _similarity(candidate, best, motifs_of[candidate.photo_id], chosen_motifs)
            if similarity:
                decay[candidate.photo_id] += similarity
            still_open.append(candidate)
        remaining = still_open

    return places


def select_album_draft(events: Iterable[SelectionEvent], target: int) -> dict[int, int]:
    """Der Auswahlvorschlag als Abbildung `photo_id -> Platz innerhalb seines Events`.

    Der Richtwert ist ein ZIEL, keine Obergrenze: reicht der Bestand nicht, umfasst der Vorschlag
    weniger; damit jedes Event vertreten ist, kann er auch mehr umfassen."""
    ordered = sorted(events, key=lambda event: (event.position, event.event_id))
    allocation = _quotas(ordered, target)

    result: dict[int, int] = {}
    for event in ordered:
        seats = allocation.get(event.event_id, 0)
        if seats > 0:
            result.update(_assign_event(event.candidates, seats))
    return result
