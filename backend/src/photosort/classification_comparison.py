"""Die reine A/B-Vergleichslogik der Klassifizierungspruefung (Spec 0616, ADR 0139 Punkt 2/3).

Zwei Verfahren, zwei Aussagen je Foto - daraus werden Zaehlungen, Faelle und eine seeded
Stichprobe. Hier steht KEINE Datenbank und kein Lauf: der Job liefert die Aussagen je Foto, die
Uebersicht ruft dieselbe Funktion fuer ihre Zaehlungen. Damit koennen Zaehlungen und Faelle nicht
auseinanderlaufen.

Vier Zwecke mit unterschiedlicher Zaehleinheit:

* `motifs` zaehlt FOTOS: ein Foto mit drei abweichenden Motiven ist EIN Fall.
* `motif_feature` zaehlt PAARE aus Foto und Motiv: dasselbe Foto ist DREI Faelle.
* `excluded_document` und `album_level` zaehlen Fotos und nur, wenn beide Seiten eine Aussage
  haben - `NULL` heisst "dieses Verfahren sagt dazu nichts", nicht "nein".
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, NamedTuple

from photosort.motifs import MOTIF_REGISTRY
from photosort.selection import motif_is_present

# Die Zwecke in Anzeige- und Sortierreihenfolge. `motifs` steht fuer die Fotoentscheidung,
# `motif_feature` fuer das einzelne Merkmal dahinter - beide werden gezeigt, weil "das Foto passt
# nicht" ohne das abweichende Merkmal nicht pruefbar ist.
PURPOSES: Final[tuple[str, ...]] = ("motifs", "motif_feature", "excluded_document", "album_level")

_PURPOSE_ORDER: Final[dict[str, int]] = {purpose: index for index, purpose in enumerate(PURPOSES)}
_MOTIF_ORDER: Final[dict[str, int]] = {
    motif_key: index for index, motif_key in enumerate(MOTIF_REGISTRY)
}

# Ein Deckel JE ZWECK: dreissig Motivfaelle duerfen nicht den Platz von Ausschluss und Albumstufe
# fressen. Der Job setzt ihn auf die Pruefgraesse der Pruefung.
DEFAULT_SAMPLE_SIZE: Final = 30


@dataclass(frozen=True)
class PhotoComparison:
    """Die Aussagen beider Seiten zu EINEM Foto.

    `None` heisst "diese Seite hat zu diesem Zweck nichts gesagt" - fuer Motive eine fehlende
    Vektorseite, fuer Ausschluss und Albumstufe das `NULL` der Ergebnistabelle. Ein Vergleich
    entsteht nur, wenn BEIDE Seiten etwas sagen.
    """

    photo_id: int
    a_motifs: Mapping[str, float] | None
    b_motifs: Mapping[str, float] | None
    a_excluded_document: bool | None
    b_excluded_document: bool | None
    a_album_level: int | None
    b_album_level: int | None


@dataclass(frozen=True)
class Case:
    """Ein vorzulegender Fall - Traeger beider Rohwerte seines Zwecks.

    `a_strength`/`b_strength` gelten fuer `motifs` und `motif_feature`, die drei uebrigen
    Wertepaare fuer ihren eigenen Zweck. `None` steht dort, wo der Zweck das Paar nicht fuehrt
    oder eine Seite den Schluessel nicht beurteilt hat - "nicht beurteilt" ist nicht "als 0.0
    beurteilt".
    """

    photo_id: int
    purpose: str
    motif_key: str | None
    a_strength: float | None
    b_strength: float | None
    a_excluded_document: bool | None
    b_excluded_document: bool | None
    a_album_level: int | None
    b_album_level: int | None


class PurposeCounts(NamedTuple):
    """Verglichene Einheiten eines Zwecks. `matching + deviating == compared` gilt immer."""

    compared: int
    matching: int
    deviating: int


@dataclass(frozen=True)
class Comparison:
    """Zaehlungen je Zweck, je Merkmal und die vorzulegenden Faelle (seeded, gedeckelt,
    sortiert).

    `motif_counts` schluesselt den Zweck `motif_feature` nach Merkmal auf - je Motiv ein
    (Foto, Motiv)-Paar-Zaehler in Registry-Ordnung, alle acht auch ohne Vergleich. Die Uebersicht
    der App bleibt bei einer Zeilengruppe; der Export traegt die Aufschluesselung (AK 10).
    """

    photos_compared: int
    counts: Mapping[str, PurposeCounts]
    motif_counts: Mapping[str, PurposeCounts]
    cases: tuple[Case, ...]


def motif_present(strengths: Mapping[str, float], motif_key: str) -> bool:
    """Gilt das Motiv als vorhanden? Entschieden von `selection.py::motif_is_present` - dieselbe
    Grenze wie im Lesepfad. Eine fehlende Zeile ist "nicht vorhanden"."""
    return motif_is_present(strengths.get(motif_key, 0.0))


def _motif_keys(a: Mapping[str, float], b: Mapping[str, float]) -> tuple[str, ...]:
    """Die VEREINIGUNG der Schluessel: eine auf einer Seite fehlende Zeile ist "nicht
    vorhanden", und genau so liest der Lesepfad sie. Ein Schnitt uebersaehe gerade die Faelle, in
    denen eine Seite ein Motiv gar nicht beurteilt hat."""
    return tuple(sorted(set(a) | set(b)))


def compare_motifs(a: Mapping[str, float], b: Mapping[str, float]) -> tuple[int, int]:
    """(uebereinstimmende, abweichende) Motiv-Entscheidungen der gemeinsamen Praesenzregel."""
    matching = 0
    deviating = 0
    for key in _motif_keys(a, b):
        if motif_present(a, key) == motif_present(b, key):
            matching += 1
        else:
            deviating += 1
    return matching, deviating


def _case(photo: PhotoComparison, purpose: str, motif_key: str | None) -> Case:
    """Ein Fall mit ausschliesslich den Werten SEINES Zwecks - der Export traegt je Fall genau
    diese beiden Seitenobjekte."""
    if purpose in ("motifs", "motif_feature"):
        assert photo.a_motifs is not None and photo.b_motifs is not None
        return Case(
            photo_id=photo.photo_id,
            purpose=purpose,
            motif_key=motif_key,
            a_strength=photo.a_motifs.get(motif_key) if motif_key is not None else None,
            b_strength=photo.b_motifs.get(motif_key) if motif_key is not None else None,
            a_excluded_document=None,
            b_excluded_document=None,
            a_album_level=None,
            b_album_level=None,
        )
    if purpose == "excluded_document":
        return Case(
            photo_id=photo.photo_id,
            purpose=purpose,
            motif_key=None,
            a_strength=None,
            b_strength=None,
            a_excluded_document=photo.a_excluded_document,
            b_excluded_document=photo.b_excluded_document,
            a_album_level=None,
            b_album_level=None,
        )
    assert purpose == "album_level"
    return Case(
        photo_id=photo.photo_id,
        purpose=purpose,
        motif_key=None,
        a_strength=None,
        b_strength=None,
        a_excluded_document=None,
        b_excluded_document=None,
        a_album_level=photo.a_album_level,
        b_album_level=photo.b_album_level,
    )


def _sort_key(case: Case) -> tuple[int, int, int]:
    return (
        case.photo_id,
        _PURPOSE_ORDER[case.purpose],
        _MOTIF_ORDER[case.motif_key] if case.motif_key is not None else -1,
    )


def _sample(cases: Sequence[Case], *, seed: int, limit: int) -> tuple[Case, ...]:
    """Hoechstens `limit` Faelle JE ZWECK, seeded ausgewaehlt und anschliessend sortiert.

    Ein gemeinsamer Generator ueber die Zwecke in fester Reihenfolge: der Strom haengt damit nur
    an der Seed und den Zaehlungen, nicht an der Reihenfolge der Faelle im Bestand. `rng.sample`
    zieht POSITIONEN, deshalb steht die Kandidatenliste je Zweck vorher in `_sort_key`-Ordnung -
    sonst waere die Zusage an die Eingabereihenfolge gebunden. Die Sortierung danach macht den
    gespeicherten Bestand unabhaengig von der Zufallsreihenfolge lesbar.
    """
    if limit <= 0:
        return ()
    by_purpose: dict[str, list[Case]] = {purpose: [] for purpose in PURPOSES}
    for case in cases:
        by_purpose[case.purpose].append(case)
    rng = random.Random(seed)
    chosen: list[Case] = []
    for purpose in PURPOSES:
        rows = sorted(by_purpose[purpose], key=_sort_key)
        if rows:
            chosen.extend(rng.sample(rows, min(limit, len(rows))))
    return tuple(sorted(chosen, key=_sort_key))


def compare_review(
    photos: Iterable[PhotoComparison],
    *,
    seed: int,
    limit: int = DEFAULT_SAMPLE_SIZE,
) -> Comparison:
    """Zaehlungen je Zweck plus die vorzulegenden Faelle.

    Jede Abweichung erzeugt einen Fall; die Staerken werden durchgereicht, wie sie in der
    Datenbank stehen - kein `round`, keine Formatierung, damit die inklusive Grenze pruefbar
    bleibt. `limit` deckelt JEDEN Zweck einzeln.
    """
    photos_compared = 0
    motif_photos = [0, 0]  # matching, deviating
    motif_pairs = [0, 0]
    motif_units: dict[str, list[int]] = {motif_key: [0, 0] for motif_key in MOTIF_REGISTRY}
    excluded = [0, 0]
    album = [0, 0]
    cases: list[Case] = []

    for photo in photos:
        photos_compared += 1

        if photo.a_motifs is not None and photo.b_motifs is not None:
            matching, deviating = compare_motifs(photo.a_motifs, photo.b_motifs)
            motif_pairs[0] += matching
            motif_pairs[1] += deviating
            deviating_keys: list[str] = []
            for key in _motif_keys(photo.a_motifs, photo.b_motifs):
                if motif_present(photo.a_motifs, key) == motif_present(photo.b_motifs, key):
                    motif_units[key][0] += 1
                else:
                    motif_units[key][1] += 1
                    deviating_keys.append(key)
            if deviating_keys:
                motif_photos[1] += 1
                cases.append(_case(photo, "motifs", None))
                cases.extend(_case(photo, "motif_feature", key) for key in deviating_keys)
            else:
                motif_photos[0] += 1

        if photo.a_excluded_document is not None and photo.b_excluded_document is not None:
            if photo.a_excluded_document == photo.b_excluded_document:
                excluded[0] += 1
            else:
                excluded[1] += 1
                cases.append(_case(photo, "excluded_document", None))

        if photo.a_album_level is not None and photo.b_album_level is not None:
            if photo.a_album_level == photo.b_album_level:
                album[0] += 1
            else:
                album[1] += 1
                cases.append(_case(photo, "album_level", None))

    counts = {
        "motifs": PurposeCounts(
            compared=motif_photos[0] + motif_photos[1],
            matching=motif_photos[0],
            deviating=motif_photos[1],
        ),
        "motif_feature": PurposeCounts(
            compared=motif_pairs[0] + motif_pairs[1],
            matching=motif_pairs[0],
            deviating=motif_pairs[1],
        ),
        "excluded_document": PurposeCounts(
            compared=excluded[0] + excluded[1], matching=excluded[0], deviating=excluded[1]
        ),
        "album_level": PurposeCounts(
            compared=album[0] + album[1], matching=album[0], deviating=album[1]
        ),
    }
    motif_counts = {
        motif_key: PurposeCounts(
            compared=matching + deviating, matching=matching, deviating=deviating
        )
        for motif_key, (matching, deviating) in motif_units.items()
    }
    return Comparison(
        photos_compared=photos_compared,
        counts=counts,
        motif_counts=motif_counts,
        cases=_sample(cases, seed=seed, limit=limit),
    )
