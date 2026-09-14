"""Die Duplikat-Gruppe als STERN ueber `PhotoScore.duplicate_of` - und der eine Ort, an dem steht,
wer den Ausschuss-Schritt ueberlebt (ADR 0104).

Die Gruppe ist ABGELEITET und wird zur Lesezeit gebildet; es gibt keine Gruppen-Id und keine
Gruppentabelle. `scoring.py::assign_duplicate_clusters` schreibt `duplicate_of` nur fuer die
Verlierer, jeweils auf den Gewinner; der Gewinner traegt `NULL`, Ketten sind damit bauartbedingt
ausgeschlossen. Zu einem Foto `P` des Projekts ist der Repraesentant `P.duplicate_of`, sonst `P`
selbst - aber nur, wenn mindestens ein Foto auf ihn zeigt. Zeigt niemand auf `P` und traegt `P`
selbst nichts, gibt es KEINE Gruppe; das ist zugleich die Durchsetzung von "nur fuer als Duplikat
erkannte Aufnahmen".

`PhotoScore.cluster_key` ist NICHT die Duplikat-Gruppe (er traegt den Zeit-/Ortscluster der
Ausschuss-Ueberlebenden) und wird hier nirgends gelesen.

Die Auswertung steht als REINE Funktion ueber den geladenen Kanten; nur `load_duplicate_links`
fragt die Datenbank. Das Laden ist dabei die Stelle, an der die PROJEKTGRENZE gezogen wird - jede
weitere Funktion arbeitet auf einer bereits begrenzten Kantenliste, und ein `duplicate_of`, das
aus ihr herauszeigt, loest sich nicht auf.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import Photo, PhotoDuplicateDecision, PhotoScore


@dataclass(frozen=True)
class DuplicateLink:
    """Eine Kante des Sterns: ein Foto des Projekts, auf wen es zeigt, wann es aufgenommen wurde
    und ob darueber bereits entschieden ist.

    `duplicate_of is None` heisst "kein Verlierer" - das Foto ist Repraesentant, sofern jemand auf
    es zeigt. `decided` traegt ausschliesslich die ANWESENHEIT einer Entscheidungszeile, nie ihren
    Wert: Fuer den Gruppenzaehler ist `keep` von `discard` nicht zu unterscheiden, beides ist
    erledigte Arbeit."""

    photo_id: int
    duplicate_of: int | None
    taken_at: datetime
    decided: bool


def representative_of(photo_id: int, links: list[DuplicateLink]) -> int | None:
    """Der Repraesentant der Gruppe, in der `photo_id` liegt - oder `None`, wenn es keine gibt.

    `None` deckt DREI Faelle, und alle drei muenden in dieselbe Antwort `404`, ohne voneinander
    unterscheidbar zu sein: das Foto gibt es nicht, das Foto gehoert einem anderen Projekt (es
    steht dann nicht in der bereits begrenzten Kantenliste), oder es liegt in keinem Stern."""
    by_id = {link.photo_id: link for link in links}
    link = by_id.get(photo_id)
    if link is None:
        return None
    if link.duplicate_of is not None:
        # SICHERHEIT (S7): Ein Zeiger, der aus der projektbegrenzten Kantenliste herausfuehrt, wird
        # NICHT aufgeloest. `photo_scores.duplicate_of` zeigt auf `photos.id` ohne
        # Projektbedingung; ohne diese Pruefung entschiede eine Aufnahme des einen Projekts ueber
        # den abfliessenden Bestand eines anderen.
        return link.duplicate_of if link.duplicate_of in by_id else None
    # Der entartete Fall: Ein Foto ohne `duplicate_of`, auf das niemand zeigt, ist keine Gruppe der
    # Groesse eins - es ist gar keine.
    return photo_id if any(other.duplicate_of == photo_id for other in links) else None


def member_ids_of(representative_id: int, links: list[DuplicateLink]) -> list[int]:
    """Die Mitglieder der Gruppe in Anzeigereihenfolge: `taken_at`, bei Gleichstand `id` (AK2).

    Serienaufnahmen tragen haeufig denselben Zeitstempel; ohne den Zweitschluessel waere die
    Reihenfolge nicht reproduzierbar."""
    members = [
        link
        for link in links
        if link.photo_id == representative_id or link.duplicate_of == representative_id
    ]
    return [
        link.photo_id for link in sorted(members, key=lambda link: (link.taken_at, link.photo_id))
    ]


def _members_by_representative(links: list[DuplicateLink]) -> dict[int, list[DuplicateLink]]:
    by_id = {link.photo_id: link for link in links}
    groups: dict[int, list[DuplicateLink]] = {}
    for link in links:
        representative = link.duplicate_of if link.duplicate_of is not None else link.photo_id
        if representative not in by_id:
            continue
        groups.setdefault(representative, []).append(link)
    # Ein Repraesentant, auf den niemand zeigt, ist keine Gruppe (derselbe entartete Fall wie in
    # `representative_of`).
    return {
        representative: members
        for representative, members in groups.items()
        if any(member.photo_id != representative for member in members)
    }


def _ordered_representatives(groups: dict[int, list[DuplicateLink]]) -> list[int]:
    return sorted(
        groups,
        key=lambda representative: (
            min(member.taken_at for member in groups[representative]),
            representative,
        ),
    )


def open_group_representative_ids(links: list[DuplicateLink]) -> list[int]:
    """Die noch OFFENEN Gruppen in Anzeigereihenfolge: fruehester `taken_at` der Mitglieder, bei
    Gleichstand die Repraesentanten-Id (AK10).

    Eine Gruppe, in der jedes Mitglied entschieden ist, faellt heraus - der Zaehler beschreibt die
    verbleibende Arbeit und laeuft auf null zu. Dass sich `position` dadurch verschiebt, sobald
    eine Gruppe abgeschlossen wird, ist die bewusst getragene Folge."""
    groups = _members_by_representative(links)
    offen = {
        representative: members
        for representative, members in groups.items()
        if any(not member.decided for member in members)
    }
    return _ordered_representatives(offen)


def group_position(representative_id: int, links: list[DuplicateLink]) -> tuple[int, int] | None:
    """`(position, total)` der Gruppe, 1-basiert - oder `None`, wenn es sie nicht gibt.

    Bezugsmenge sind die offenen Gruppen VEREINIGT mit der gerade angesehenen. Die Vereinigung ist
    nicht Bequemlichkeit: AK10 sichert `1 <= position <= total` zu, und wer die letzte offene
    Gruppe fertig entscheidet, laedt genau sie danach neu. Ohne sie stuende dort `position = 1` bei
    `total = 0`. Fremde abgeschlossene Gruppen fallen unveraendert heraus."""
    groups = _members_by_representative(links)
    if representative_id not in groups:
        return None
    bezugsmenge = {
        representative: groups[representative]
        for representative in [*open_group_representative_ids(links), representative_id]
    }
    geordnet = _ordered_representatives(bezugsmenge)
    return geordnet.index(representative_id) + 1, len(geordnet)


def _project_member_condition(project_id: int) -> ColumnElement[bool]:
    """Wer gehoert ueberhaupt zu einem Stern dieses Projekts: wer selbst auf jemanden zeigt, oder
    auf wen gezeigt wird.

    BEIDE Haelften tragen `Photo.project_id == project_id` ausgeschrieben (S7). Ohne die Bedingung
    in der Unterabfrage zoege ein Foto eines FREMDEN Projekts, dessen `duplicate_of` hierher zeigt,
    den hiesigen Gewinner in eine Gruppe, die es nicht gibt."""
    zeigt_hierher = (
        select(PhotoScore.duplicate_of)
        .join(Photo, Photo.id == PhotoScore.photo_id)
        .where(Photo.project_id == project_id, PhotoScore.duplicate_of.is_not(None))
    )
    return or_(PhotoScore.duplicate_of.is_not(None), Photo.id.in_(zeigt_hierher))


async def load_duplicate_links(session: AsyncSession, project_id: int) -> list[DuplicateLink]:
    """Alle Kanten aller Sterne DIESES Projekts - die einzige Abfrage dieses Moduls.

    Der Join auf `PhotoScore` ist ein AEUSSERER: `photo_scores.duplicate_of` zeigt auf `photos.id`
    und nicht auf `photo_scores.photo_id`, ein Gewinner braucht also strukturell keine eigene
    Zeile, um referenziert zu werden. Ein innerer Join liesse ihn aus seiner eigenen Gruppe fallen,
    und die Ansicht zeigte den Vergleich ohne das Bild, gegen das verglichen wird.

    Geladen werden AUSSCHLIESSLICH Sternmitglieder, nicht alle Fotos des Projekts: Die Menge ist
    damit durch die Zahl der erkannten Duplikate begrenzt und nicht durch die Projektgroesse."""
    rows = (
        await session.execute(
            select(
                Photo.id,
                PhotoScore.duplicate_of,
                Photo.taken_at,
                PhotoDuplicateDecision.photo_id,
            )
            .outerjoin(PhotoScore, PhotoScore.photo_id == Photo.id)
            .outerjoin(PhotoDuplicateDecision, PhotoDuplicateDecision.photo_id == Photo.id)
            .where(Photo.project_id == project_id, _project_member_condition(project_id))
        )
    ).all()
    return [
        DuplicateLink(
            photo_id=photo_id,
            duplicate_of=duplicate_of,
            taken_at=taken_at,
            decided=decided_photo_id is not None,
        )
        for photo_id, duplicate_of, taken_at, decided_photo_id in rows
    ]
