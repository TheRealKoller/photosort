"""Der Auswahlvorschlag: Kontingente je Event und motiv- und personengefuehrte Vergabe mit
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
from bisect import bisect_left
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


def motif_is_present(strength: float, threshold: float | None = None) -> bool:
    """Traegt ein Bild dieses Motiv? INKLUSIV verglichen, fuer alle Motive dieselbe Grenze.

    GETEILT WIRD DAS PRAEDIKAT, NIE DIE KONSTANTE: Jeder weitere Leser ruft diese Funktion, statt
    selbst gegen `MOTIF_PRESENCE_THRESHOLD` zu vergleichen. Sonst stuende die Zahl zwar an einer
    Stelle, der Vergleichsoperator aber an zweien - und ein spaeteres `>` an einer davon braeche
    nichts laut, obwohl gerade die Inklusivitaet die Zusage ist. Gehalten in
    `tests/test_selection.py::TestTheStructuralGuardAgainstReadingTheDisplayBands`.

    Zweiter Leser ausserhalb der Auswahl ist `api/photos.py::_motifs_out`
    (`MotifStrengthOut.present`) - die Grenze verlaesst das Backend ausschliesslich als dieses
    Ja/Nein, nie als Zahl.

    `threshold` ist DER MESSWEG UND NUR ER: Ein rein lesender Messlauf variiert die Grenze, ohne
    eine zweite Fassung des Vergleichs zu bauen - eine Nachbildung maesse etwas anderes, als der
    Lauf tut. Ohne Angabe gilt die Modulkonstante, das Verhalten ist dann unveraendert.
    KEIN AUSWAEHLENDER PFAD GIBT EINEN WERT MIT: Die Eindaemmung aus ADR 0091 Punkt 1 haengt
    daran, dass die Auswahl je Motiv gegen EINE fuer alle Motive gleiche Konstante prueft; eine
    eigene Grenze eines auswaehlenden Aufrufers waere eine zweite Auswahlgrenze im selben Produkt.
    Gehalten in `tests/test_selection.py::TestOnlyTheMeasuringPathPassesItsOwnThreshold`. Ein
    mitgegebener Wert ist ein SKALAR fuer alle Motive, nie eine Grenze je Motiv."""
    if threshold is None:
        return strength >= MOTIF_PRESENCE_THRESHOLD
    # Derselbe INKLUSIVE Vergleich, eine Zeile tiefer - ein `>` hier braeche die Zusage genauso.
    # Gepinnt durch den Zwilling, der beide Zweige am Betriebswert Wert fuer Wert gegeneinander
    # stellt, einschliesslich der Grenze selbst.
    return strength >= threshold


def carried_motifs(
    motif_strengths: Mapping[str, float], threshold: float | None = None
) -> frozenset[str]:
    """Die Motive, die ein Bild traegt - die EINE Herleitung fuer Auswahl und Alternativen.

    Sie nimmt die Staerkeabbildung und nicht einen Kandidaten entgegen, damit jeder Aufrufer mit
    eigenem Kandidatentyp dieselbe Herleitung nutzt: eine zweite Herleitung fuer einen zweiten Typ
    liefe an dem Tag auseinander, an dem die Grenze sich aendert. Ein hier fehlendes Motiv zaehlt
    als nicht getragen.

    `threshold` wird unveraendert an `motif_is_present` durchgereicht und gilt fuer JEDES Motiv
    dieser Abbildung gleich; die Auflage dort gilt hier mit."""
    return frozenset(
        key for key, strength in motif_strengths.items() if motif_is_present(strength, threshold)
    )


# Womit der Wert eines Bildes je bereits gewaehltem, vollstaendig aehnlichem Bild multipliziert
# wird.
SIMILARITY_DECAY = 0.5

# Jenseits dieser Spanne wertet nichts mehr ab; innerhalb laeuft die Zeitnaehe linear aus.
SIMILARITY_TIME_WINDOW = timedelta(minutes=15)

# Die Vorbelegung: ohne eingestellten Richtwert zielt der Vorschlag auf diese feste Zahl Bilder,
# unabhaengig von der Bilderzahl. Diese Zahl steht NUR hier.
DEFAULT_TARGET = 150

_SIMILARITY_TIME_WINDOW_SECONDS = SIMILARITY_TIME_WINDOW.total_seconds()


@dataclass(frozen=True)
class SelectionCandidate:
    """Ein auswahlfaehiges Bild eines Events.

    `taken_at` ist `datetime` und nicht `datetime | None`: `Photo.taken_at` ist NOT NULL, ein Bild
    ohne Aufnahmezeit gibt es nicht. Ein `| None` an dieser Stelle fuehrte einen Zweig ein, den
    kein Produktivzustand erreicht.

    `quality` ist der fertige `rank_score`; `motif_strengths` sind die WIRKSAMEN Staerken
    (Korrekturen inbegriffen), wie der Aufrufer sie geladen hat. Ein hier fehlendes Motiv zaehlt
    als nicht getragen.

    `person_ids` sind die wirksam zugeordneten Personen des Bildes, NUR als Id - ein Name erreicht
    dieses Modul nie. Pflichtfeld ohne Vorgabewert: ein Aufrufer, der es vergisst, scheitert an
    der Typpruefung, statt still "keine Personen" zu liefern. Der `repr` traegt die Ids; ein
    Kandidat gehoert deshalb in keine Logzeile und keinen Fehlertext."""

    photo_id: int
    taken_at: datetime
    quality: float
    motif_strengths: Mapping[str, float]
    person_ids: frozenset[int]


@dataclass(frozen=True)
class SelectionEvent:
    """Ein Event samt seinen auswahlfaehigen Kandidaten. `position` ist die 1-basierte,
    chronologische Nummer des Events im Lauf und zugleich der Stichentscheid der
    Restverteilung."""

    event_id: int
    position: int
    candidates: Sequence[SelectionCandidate]


@dataclass(frozen=True)
class TimedCandidate:
    """Ein Bild in der zeitlichen Reihe der Alternativen eines Austauschs - Bezugsbild wie
    Kandidat.

    Traegt bewusst NUR `photo_id` und `taken_at`: Motiv und Qualitaet gehen nicht in die Ordnung
    ein, und ohne die Felder ist das strukturell wahr statt bloss unbenutzt. `taken_at` ist die
    wirksame, um den Kamera-Versatz korrigierte Zeit und nie `None` (`Photo.taken_at`
    ist NOT NULL, Rueckfall `last_modified`)."""

    photo_id: int
    taken_at: datetime


@dataclass(frozen=True)
class QualityCandidate:
    """Ein Bild im Hinzufuegen-Feld des Album-Entwurfs (ohne Bezugsbild).

    `quality` ist `float | None`: ein Kandidat ohne Qualitaetsbewertung ist ein gueltiger,
    waehlbarer Zustand - er sortiert ans Ende."""

    photo_id: int
    quality: float | None


# Das Band unter einem Foto des Album-Entwurfs zeigt dessen Aufnahmeserie: Zwei
# zeitlich benachbarte Alternativen gehoeren zusammen, solange zwischen ihnen hoechstens
# `SERIES_GAP` liegt (INKLUSIV). Eine kuerzere Serie wird auf `BAND_MIN` aufgefuellt, eine
# laengere auf `BAND_MAX_SERIES` gekappt. SICHERHEIT: `BAND_MAX_SERIES`
# ist zugleich der Deckel der Hydratation und darf den `limit`-Deckel (200) nie uebersteigen.
SERIES_GAP = timedelta(minutes=2)
BAND_MIN = 4
BAND_MAX_SERIES = 12


@dataclass(frozen=True)
class SeriesWindow:
    """Das Fenster des Bands in der zeitlichen Reihe: `[offset, offset + size)`; `rest` ist
    die Zahl der Serienaufnahmen, die wegen `BAND_MAX_SERIES` draussen bleiben."""

    offset: int
    size: int
    rest: int


def order_alternatives_chronologically(
    reference: TimedCandidate, candidates: Iterable[TimedCandidate]
) -> tuple[list[int], int, list[datetime]]:
    """Die Alternativen zu EINEM Bild, zeitlich geordnet.

    Schluessel `(taken_at, photo_id)` aufsteigend - eine Totalordnung ohne Nutzer, Motiv oder
    Qualitaet; Gleichstand bricht ueber die kleinere `photo_id`, nie ueber die Eingabereihenfolge.

    Rueckgabe: die `photo_id`-Folge, `reference_index` - die Zahl der Kandidaten, die nach
    DEMSELBEN Schluessel STRIKT vor dem Bezugsbild liegen - und die `taken_at` in derselben
    Ordnung (Eingabe von `series_window`). Alles entsteht aus derselben Menge und Sortierung.
    Das Bezugsbild selbst faellt heraus: es ist der Ausgangspunkt des Austauschs, nicht sein
    Ziel."""
    reference_key = (reference.taken_at, reference.photo_id)
    ordered = sorted(
        (candidate.taken_at, candidate.photo_id)
        for candidate in candidates
        if candidate.photo_id != reference.photo_id
    )
    reference_index = bisect_left(ordered, reference_key)
    return (
        [photo_id for _, photo_id in ordered],
        reference_index,
        [taken_at for taken_at, _ in ordered],
    )


def series_window(
    times: Sequence[datetime], reference_taken_at: datetime, reference_index: int
) -> SeriesWindow:
    """Das Bandfenster ueber den nach `(taken_at, photo_id)` geordneten Zeiten der Alternativen.

    Die SERIE `[a, b)` waechst vom Bezugsbild nach beiden Seiten, solange der Abstand zum
    jeweils vorigen Nachbarn (zuerst dem Bezugsbild selbst) hoechstens `SERIES_GAP` ist.
    Das FENSTER ist immer zusammenhaengend: Serie mit `BAND_MIN`..`BAND_MAX_SERIES` Bildern
    genau; laenger -> die `BAND_MAX_SERIES` zeitlich naechsten INNERHALB der Serie; kuerzer ->
    die Serie, aufgefuellt mit den zeitlich naechsten des Events bis `BAND_MIN`. Beim Wachsen
    gewinnt der zeitlich naehere Nachbar, bei Gleichstand der fruehere."""
    total = len(times)
    start = reference_index
    previous = reference_taken_at
    while start > 0 and previous - times[start - 1] <= SERIES_GAP:
        start -= 1
        previous = times[start]
    end = reference_index
    previous = reference_taken_at
    while end < total and times[end] - previous <= SERIES_GAP:
        previous = times[end]
        end += 1
    series = end - start

    if BAND_MIN <= series <= BAND_MAX_SERIES:
        return SeriesWindow(offset=start, size=series, rest=0)
    if series > BAND_MAX_SERIES:
        low, high, bound_low, bound_high, target = (
            reference_index,
            reference_index,
            start,
            end,
            BAND_MAX_SERIES,
        )
    else:
        low, high, bound_low, bound_high, target = start, end, 0, total, BAND_MIN
    while high - low < target and (low > bound_low or high < bound_high):
        take_earlier = high >= bound_high or (
            low > bound_low
            and reference_taken_at - times[low - 1] <= times[high] - reference_taken_at
        )
        if take_earlier:
            low -= 1
        else:
            high += 1
    return SeriesWindow(offset=low, size=high - low, rest=max(0, series - BAND_MAX_SERIES))


def order_by_quality(candidates: Iterable[QualityCandidate]) -> list[int]:
    """Die Reihenfolge des Hinzufuegen-Felds (ohne Bezugsbild), als `photo_id`-Folge.

    Qualitaet absteigend, `None` zuletzt - als eigenes Schluesselglied, denn `quality or 0.0`
    machte aus einer `0.0` lautlos einen fehlenden Wert. Gleichstand ueber die kleinere
    `photo_id`. Ein Ersatz-Bezugsbild gibt es nicht."""

    def key(candidate: QualityCandidate) -> tuple[int, float, int]:
        quality = candidate.quality
        return (
            1 if quality is None else 0,
            0.0 if quality is None else -quality,
            candidate.photo_id,
        )

    return [candidate.photo_id for candidate in sorted(candidates, key=key)]


def effective_target(configured: int | None) -> int:
    """Der wirksame Richtwert eines Projekts.

    `None` heisst "nicht selbst eingestellt" und ergibt die feste Vorbelegung `DEFAULT_TARGET` -
    sie waechst mit dem Bestand NICHT mit. Eine eingestellte Zahl gilt absolut und unveraendert.

    DIE EINE Ableitungsstelle: die Vorbelegung wird nie in die Spalte geschrieben, ein
    eingeschriebener Vorgabewert waere von einer Nutzereingabe nicht mehr zu unterscheiden, und
    eine spaetere Aenderung der Vorbelegung erreichte das Projekt nicht mehr."""
    if configured is not None:
        return configured
    return DEFAULT_TARGET


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
    """Stufe 2 - die motiv- und personengefuehrte Vergabe innerhalb EINES Events, unabhaengig von
    den uebrigen.

    Der Wert eines noch nicht gewaehlten Bildes ist
    `rank_score · SIMILARITY_DECAY ^ Σ_{s gewählt} ähnlichkeit(p, s)`. Jeder Platz geht an das
    Bild mit dem hoechsten Wert - aber solange ein vorkommendes Motiv ODER eine vorkommende Person
    unvertreten ist, nur aus den Bildern, die etwas davon tragen. Das gewaehlte Bild vertritt dann
    ALLE unvertretenen Motive und Personen, die es traegt; wie viele das sind, geht nie in den Wert
    ein, und es wird nie ein Ziel gegen ein anderes abgewogen. Personen sind kein
    Aehnlichkeitsmerkmal.

    Motive und Personen bleiben zwei getrennte Mengen und nie ein gemeinsamer Schluesselraum: ein
    Motivschluessel und eine Personen-Id koennten sonst zusammenfallen. Die Personenmengen dienen
    nur Schnittmengen- und Leerheitspruefungen, nie einer Reihenfolge.

    Die Abwertung wird je Kandidat FORTGESCHRIEBEN und nie bei jeder Bewertung erneut ueber alle
    bereits Gewaehlten summiert (Sicherheitsauflage S5). Ergebnisgleich - die Aehnlichkeiten
    stehen additiv im Exponenten -, aber `O(n·k)` statt `O(n·k²)`: bei tausend Kandidaten und
    vollem Kontingent ist das der Unterschied zwischen rund 10⁶ und rund 10⁹ Bewertungen synchron
    im Request."""
    remaining = sorted(candidates, key=lambda candidate: candidate.photo_id)
    motifs_of = {
        candidate.photo_id: carried_motifs(candidate.motif_strengths) for candidate in remaining
    }
    present = frozenset().union(*motifs_of.values()) if motifs_of else frozenset()
    present_persons = frozenset().union(*(candidate.person_ids for candidate in remaining))
    decay: dict[int, float] = {candidate.photo_id: 0.0 for candidate in remaining}

    represented: set[str] = set()
    represented_persons: set[int] = set()
    places: dict[int, int] = {}

    for place in range(1, seats + 1):
        if not remaining:
            # Unerreichbar: `seats` ist durch die Obergrenze auf `n_i` begrenzt, es gibt also nie
            # mehr Plaetze als Kandidaten.
            break
        unrepresented = present - represented
        unrepresented_persons = present_persons - represented_persons
        restricted = bool(unrepresented or unrepresented_persons)

        best: SelectionCandidate | None = None
        best_key: tuple[float, int] | None = None
        for candidate in remaining:
            if restricted and not (
                motifs_of[candidate.photo_id] & unrepresented
                or candidate.person_ids & unrepresented_persons
            ):
                continue
            value = candidate.quality * SIMILARITY_DECAY ** decay[candidate.photo_id]
            # Gleichstand ueber die kleinere `photo_id` - ausgeschrieben als zweiter Schluessel
            # und nicht dem "erstes gesehenes Element gewinnt" von `max` ueberlassen.
            key = (-value, candidate.photo_id)
            if best_key is None or key < best_key:
                best_key = key
                best = candidate
        if best is None:
            # Unerreichbar, solange `present` und `present_persons` aus DIESEN Kandidaten
            # entstanden sind: ein vorkommendes Motiv und eine vorkommende Person haben per
            # Definition ein Traegerbild, und ist dieses gewaehlt, gelten sie als vertreten.
            break

        places[best.photo_id] = place
        chosen_motifs = motifs_of[best.photo_id]
        represented |= chosen_motifs
        represented_persons |= best.person_ids

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
