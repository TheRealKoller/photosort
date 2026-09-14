"""Das projektgebundene Namensregister der Sehenswuerdigkeiten - REIN und DB-FREI.

Dieses Modul beantwortet ausschliesslich "welcher Registereintrag meint diesen Rohnamen" und kennt
weder Sitzung noch Tabelle; der Datenbankzugriff liegt in `worker.py` (Muster `places.py`).

LOGGING-AUFLAGE fuer jede kuenftige Logzeile dieses Moduls: weder ein Ortsname noch ein
Sehenswuerdigkeitsname noch ein Einbettungsvektor gehoert je in ein Log. Der Vektor ist eine
verlustbehaftete Kodierung genau des Namens in derselben Zeile und erbt dessen Einstufung (S8).
"""

from __future__ import annotations

from dataclasses import dataclass

from photosort.label_embedding import LabelEmbedderLike, cosine_similarity, normalize_label_text

# Die Aehnlichkeitsschwelle des Namensregisters - eine EIGENE Konstante, nicht die der Feinlabels
# (ADR 0107 Punkt 4). Eigennamen verlangen einen strengeren Massstab als Sachbegriffe: "Hund" und
# "Hunde" duerfen zusammenfallen, "Kölner Dom" und "Ulmer Dom" nicht. Beide muessen sich unabhaengig
# bewegen koennen.
#
# Dokumentiert-unkalibriert, gleiche Klasse wie ihr Vorbild: Es gibt keinen Namenskorpus im
# Repository, gegen den sie kalibriert werden koennte. Erkennungsweg ist die Abnahme an einer
# echten Reise.
LANDMARK_NAME_SIMILARITY_THRESHOLD = 0.88


@dataclass
class LandmarkNameEntry:
    """Ein Eintrag des In-Memory-Schnappschusses der `landmark_names`-Tabelle.

    Bewusst NICHT frozen (Muster `FineLabelSnapshotEntry`): `worker.py` setzt nach dem
    Datenbank-Einfuegen die echte `id` auf genau dieser Instanz nach. `id is None` heisst "in
    diesem Lauf neu entstanden, noch nicht geschrieben".

    `locality` ist der aufgeloeste Ortsname, unter dem der Eintrag zuerst gesehen wurde, oder
    `None` - er wirkt als SPERRE und nie als Schluessel."""

    normalized_name: str
    display_name: str
    embedding: list[float]
    locality: str | None = None
    id: int | None = None


def _localities_are_known_and_different(a: str | None, b: str | None) -> bool:
    """Die Sperre: Nur wenn BEIDE Seiten einen aufgeloesten Ortsnamen tragen und dieser verschieden
    ist, gelten sie als verschiedene Sehenswuerdigkeiten.

    Traegt eine Seite keinen, entscheidet die Aehnlichkeit allein - das bewusst getragene
    Restrisiko dieser Entscheidung (siehe "Bekannte Luecken" der Spec)."""
    return a is not None and b is not None and a != b


def resolve_canonical_landmark(
    raw_name: str,
    locality: str | None,
    entries: list[LandmarkNameEntry],
    embedder: LabelEmbedderLike,
) -> LandmarkNameEntry:
    """Loest einen Rohnamen auf den Registereintrag auf, den er meint - rein und DB-frei.

    DREI SCHRITTE (ADR 0107 Punkt 4, Muster `remote_classification.py::resolve_canonical_label`):

    1. **Gleicher normalisierter Name** - trifft IMMER, ohne Ortspruefung und ohne Modellaufruf.
       Zwei zeichengleiche Namen gelten schon vor dieser Entscheidung als dieselbe
       Sehenswuerdigkeit. Dass die Sperre hier NICHT gilt, ist Absicht und kein Versehen: sonst
       zerfiele eine Sehenswuerdigkeit, die zwei benachbarte Gemeinden beruehrt, in zwei Eintraege.
    2. **Aehnlichkeit** oberhalb von `LANDMARK_NAME_SIMILARITY_THRESHOLD` (`>=`, inklusiv) - aber
       NUR gegen Eintraege, die die Sperre nicht ausschliesst. Ein gesperrter Eintrag wird
       uebersprungen und verdeckt damit keinen passenden dahinter.
    3. Sonst ein **neuer Eintrag**, der `entries` sofort (in-place) ergaenzt: Zwei sehr aehnliche
       neue Namen im selben Lauf ergeben sonst zwei Zeilen fuer dieselbe Sehenswuerdigkeit, und die
       zweite koennte am projektweiten Eindeutigkeits-Constraint scheitern.

    `entries` ist der Schnappschuss EINES Projekts - die Projektbindung liegt in der Abfrage, die
    ihn laedt (S8). Dieses Modul sieht nie mehr als ein Projekt."""
    normalized = normalize_label_text(raw_name)

    for entry in entries:
        if entry.normalized_name == normalized:
            return entry

    vector = embedder.embed(normalized)

    best_entry: LandmarkNameEntry | None = None
    best_similarity = -1.0
    for entry in entries:
        if _localities_are_known_and_different(locality, entry.locality):
            continue
        similarity = cosine_similarity(vector, entry.embedding)
        if similarity > best_similarity:
            best_similarity = similarity
            best_entry = entry

    if best_entry is not None and best_similarity >= LANDMARK_NAME_SIMILARITY_THRESHOLD:
        return best_entry

    new_entry = LandmarkNameEntry(
        normalized_name=normalized,
        display_name=raw_name,
        embedding=vector,
        locality=locality,
    )
    entries.append(new_entry)
    return new_entry
