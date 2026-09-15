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

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import DuplicateDecision, Photo, PhotoDuplicateDecision, PhotoScore


@dataclass(frozen=True)
class DuplicateLink:
    """Eine Kante des Sterns: ein Foto des Projekts, auf wen es zeigt und wann es aufgenommen
    wurde.

    `duplicate_of is None` heisst "kein Verlierer" - das Foto ist Repraesentant, sofern jemand auf
    es zeigt.

    DIE KANTE TRAEGT KEINE ENTSCHEIDUNGSAUSKUNFT (AK6). Die Gruppenreihenfolge haengt damit an
    keinem Wert, den eine Entscheidung aendert, und Zaehler wie Position koennen sich waehrend
    eines Durchgangs nicht verschieben. Ein wieder eingefuehrtes `decided` faellt in
    `tests/test_duplicates.py::test_the_group_order_cannot_depend_on_any_decision` auf."""

    photo_id: int
    duplicate_of: int | None
    taken_at: datetime


@dataclass(frozen=True)
class GroupStanding:
    """Die Stellung EINER Gruppe in der Gruppenreihenfolge: Platz, Gesamtzahl und die beiden
    Nachbarn als Repraesentanten-Id.

    `previous_id`/`next_id` sind `None` am jeweiligen Rand - die Ansicht schaltet die Schaltflaeche
    dort auf `disabled`, statt sie wegzulassen (AK5)."""

    position: int
    total: int
    previous_id: int | None
    next_id: int | None


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


def all_group_representative_ids(links: list[DuplicateLink]) -> list[int]:
    """ALLE Duplikat-Gruppen des Projekts in Anzeigereihenfolge: fruehester `taken_at` der
    Mitglieder, bei Gleichstand die Repraesentanten-Id.

    KEINE Auswahl nach offen/erledigt (AK6). Eine vollstaendig entschiedene Gruppe bleibt in der
    Liste, bleibt erreichbar und wird beim Durchgang nicht uebersprungen. Die Reihenfolge haengt
    damit an keinem Wert, den eine Entscheidung aendert; nur ein erneuter Ausschuss-Lauf kann sie
    bewegen."""
    return _ordered_representatives(_members_by_representative(links))


def group_standing(representative_id: int, links: list[DuplicateLink]) -> GroupStanding | None:
    """Platz, Gesamtzahl und die beiden Nachbarn der Gruppe - oder `None`, wenn es sie nicht gibt.

    EINE geordnete Liste fuer alle vier Werte, einmal berechnet: Zaehler und Nachbarn sind
    dieselbe Aussage. Getrennt gebildet koennten sie auseinanderlaufen, und ein Durchgang endete an
    einer Gruppe, die der Zaehler nicht kennt."""
    geordnet = all_group_representative_ids(links)
    if representative_id not in geordnet:
        return None
    index = geordnet.index(representative_id)
    return GroupStanding(
        position=index + 1,
        total=len(geordnet),
        previous_id=geordnet[index - 1] if index > 0 else None,
        next_id=geordnet[index + 1] if index + 1 < len(geordnet) else None,
    )


# ----------------------------------------------------------------------------------------------
# Der Ausschuss-Ueberlebender-Bestand - eine Bedingung statt sechs ausgeschriebener Vorkommen
# ----------------------------------------------------------------------------------------------
#
#     DISCARD ueberlebt nie · KEEP ueberlebt, solange duplicate_of IS NOT NULL ·
#     sonst entscheidet suggested_status
#
# ZWEI ZAEHLWEISEN, DIE NICHT DIESELBE ZAHL ERGEBEN - und das ist kein Versehen:
#
# * ERSETZTE VORKOMMEN: SECHS. So zaehlen Spec 0374, ADR 0104 Punkt 3 und das Sicherheitskonzept,
#   und so stand `PhotoScore.suggested_status IS NULL` vorher ausgeschrieben da.
# * NEUE AUFRUFSTELLEN: SIEBEN. Die eine Bedingung zerfaellt in ZWEI Funktionen ("ueberlebt" und
#   "offener Vorschlag", die seit ADR 0104 nicht mehr komplementaer sind), und "der Vorschlags-
#   Zweig" war schon vorher zwei Codeformen - eine SQL- und eine Objektfassung, die der
#   Paritaetstest aneinander band. Vier Aufrufe von `survives_ausschuss`, einer von
#   `survives_ausschuss_for`, je einer von `has_open_suggestion`/`_for`.
#
# Die Sollgroesse des Waechters ist die ZWEITE Zahl (`tests/test_ausschuss_ueberlebende.py`); die
# erste steht in den Dokumenten und wird dort nicht nachgezogen. Wer beide verwechselt, "korrigiert"
# das Waechter-Dictionary auf sechs und haelt den dann roten Test fuer einen Fund.
#
# SICHERHEITSAUFLAGE (S1) - DASSELBE PRAEDIKAT IST DIE GRENZE DES HOMESERVERS. Es begrenzt, welche
# Fotos den Homeserver Richtung Cloud-Anbieter verlassen duerfen, und gilt fuer JEDE Abfrage, die
# Cloud-Kandidaten bestimmt. Das sind VIER, nicht eine: die beiden Laeufe
# (`worker.py::run_criterion_scoring`, das zugleich den Sehenswuerdigkeits-Teilschritt speist, und
# `worker.py::select_remote_category_candidates`) und die beiden vorgelagerten Kostenschaetzungen
# (`api/projects.py::_count_remote_category_candidates`, `_count_landmark_candidates`). Die
# Schaetzungen folgen der Auswahl nicht von selbst, sondern sind eigene Anweisungen; sie zaehlen
# dieselbe Menge, die der Lauf sendet. Untersagte Alternative ist die naheliegende Teilumsetzung -
# das Praedikat in die Lesepfade der Oberflaeche zu legen und eine der vier Stellen beim alten
# `suggested_status IS NULL` zu belassen. Bei Verletzung verlassen ausdruecklich verworfene
# Aufnahmen den Homeserver, behaltene fehlen in der Bewertung, und die Schaetzung nennt eine andere
# Zahl als der Lauf sendet - ohne Fehler, ohne Meldung, sichtbar erst an der Abrechnung des
# Anbieters. Der fuenfte Ort (`api/photos.py::_cloud_vision_status_out`) traegt dieselbe Bedingung,
# ist aber Anzeige und keine Grenze.
#
# DIE ASYMMETRIE ZWISCHEN DEN BEIDEN WERTEN IST DIE ENTSCHEIDUNG, NICHT EIN DETAIL (S3).
# `suggested_status = REJECTED` traegt zwei Gruende - Duplikat-Verlierer UND Unschaerfe unterhalb
# `SHARPNESS_REJECT_THRESHOLD`, wobei `duplicate_of` im zweiten Fall `NULL` bleibt. Ein
# unbedingtes `keep` hoebe damit eine Ablehnung auf, zu der der Nutzer nie befragt wurde: Er hat
# die Duplikatfrage beantwortet, nicht die Schaerfefrage. `discard` bleibt unbedingt, weil es den
# abfliessenden Bestand verkleinert.


def _decision_subquery() -> ColumnElement[DuplicateDecision | None]:
    """Die Entscheidung zu DIESEM `PhotoScore`, als korrelierte Skalar-Unterabfrage.

    Skalar und nicht als Join, damit keine Aufrufstelle eine Join-Buchfuehrung erbt: Die
    SQL-Fassungen treten an jeder ihrer FUENF Aufrufstellen als weiterer Konjunktionsteil in die
    BESTEHENDE Anweisung. Die beiden Objektfassungen in `api/photos.py` tun das gerade nicht - sie
    lesen ein bereits geladenes Foto und kommen hier nie vorbei."""
    return (
        select(PhotoDuplicateDecision.decision)
        .where(PhotoDuplicateDecision.photo_id == PhotoScore.photo_id)
        .scalar_subquery()
    )


def survives_ausschuss() -> ColumnElement[bool]:
    """Die SQL-Fassung. Setzt einen inneren Join auf `PhotoScore` in derselben Anweisung voraus.

    SICHERHEIT (S2), drei Festlegungen, jede einzeln tragend:

    1. Ueberleben wird POSITIV auf `KEEP` geprueft, nie negativ auf `DISCARD`. Die Spalte ist eine
       Zeichenkette, der Wertevorrat wird von der Datenbank nicht erzwungen, und ein unerwarteter
       Wert muss zur zurueckhaltenden Seite fallen - nicht zum Abfluss.
    2. Der Fall "keine Zeile" ist ein ausdrueckliches `IS NULL` auf die Unterabfrage, nie ein
       Ungleichheitsvergleich: `<Unterabfrage> != 'discard'` ergibt bei fehlender Zeile `NULL`,
       und die Auswahl lieferte dann den LEEREN Bestand.
    3. Der innere Join auf `PhotoScore` bleibt ein innerer Join, und das Praedikat tritt als
       weiterer Konjunktionsteil in DIESELBE Anweisung. Ein Umbau auf einen Outer Join oder auf
       eine vorgeschaltete Aufloesung machte das Gate zu einem nachgelagerten Filter ueber einer
       bereits gebildeten Menge und ist untersagt."""
    decision = _decision_subquery()
    wirksames_keep = and_(decision == DuplicateDecision.KEEP, PhotoScore.duplicate_of.is_not(None))
    # "Ohne Wirkung" deckt zwei Faelle: keine Zeile, und ein `keep`, dessen Gruppe zerfallen ist
    # (AK12). Beide fallen auf `suggested_status` zurueck - ein `keep` macht eine Aufnahme nie
    # schlechter, als sie ohne Entscheidung staende.
    ohne_wirkung = or_(
        decision.is_(None),
        and_(decision == DuplicateDecision.KEEP, PhotoScore.duplicate_of.is_(None)),
    )
    return or_(wirksames_keep, and_(ohne_wirkung, PhotoScore.suggested_status.is_(None)))


def has_open_suggestion() -> ColumnElement[bool]:
    """Die SQL-Fassung von "offener Vorschlag": gestellt und noch nicht beantwortet.

    AUSDRUECKLICH NICHT die Negation von `survives_ausschuss()` (AK5): Eine mit `Ausschuss`
    entschiedene Aufnahme ist weder Ueberlebende noch offener Vorschlag. Eine Umsetzung, die die
    eine Menge als Verneinung der anderen bildet, liefert plausible, falsche Listen."""
    return and_(PhotoScore.suggested_status.is_not(None), _decision_subquery().is_(None))


def _survives(
    suggested_status: object, duplicate_of: int | None, decision: DuplicateDecision | None
) -> bool:
    if decision is DuplicateDecision.KEEP and duplicate_of is not None:
        return True
    if decision is None or (decision is DuplicateDecision.KEEP and duplicate_of is None):
        return suggested_status is None
    return False


def survives_ausschuss_for(photo: Photo) -> bool:
    """Die Objektfassung, ueber einem Foto mit geladenem `score` und `duplicate_decision`.

    Ein Foto OHNE `PhotoScore` ueberlebt nicht - das entspricht dem inneren Join der SQL-Fassung.
    Beide werden ueber demselben Datenbestand gegeneinander gemessen
    (`tests/test_ausschuss_ueberlebende.py`)."""
    score = photo.score
    if score is None:
        return False
    entscheidung = photo.duplicate_decision
    return _survives(
        score.suggested_status,
        score.duplicate_of,
        entscheidung.decision if entscheidung is not None else None,
    )


def _score_und_entscheidung(photo: Photo) -> tuple[object, int | None, DuplicateDecision | None]:
    """`(suggested_status, duplicate_of, decision)` eines geladenen Fotos.

    EINE FEHLENDE `PhotoScore`-ZEILE WIRD WIE `NULL, NULL` GELESEN (Auflage S3) - anders als beim
    inneren Join der beiden Ueberlebens-Fassungen. Der Repraesentant braucht strukturell keine
    eigene Zeile, um referenziert zu werden (`photo_scores.duplicate_of` zeigt auf `photos.id`),
    und `load_duplicate_links` joint genau deshalb aeusser."""
    score = photo.score
    entscheidung = photo.duplicate_decision
    return (
        score.suggested_status if score is not None else None,
        score.duplicate_of if score is not None else None,
        entscheidung.decision if entscheidung is not None else None,
    )


def effective_decision_for(photo: Photo) -> DuplicateDecision:
    """Der Zustand, den die Vergleichsansicht zeigt: `KEEP`, wenn das Foto den Ausschuss-Schritt
    ueberlebt, sonst `DISCARD` (ADR 0111 Punkt 1).

    KEIN DRITTER WERT. Aus der Antwort geht nicht hervor, ob der Zustand vom Automaten oder vom
    Nutzer stammt - der unentschiedene Duplikat-Verlierer traegt `suggested_status = REJECTED` und
    steht damit von Anfang an als "Ausschuss" da.

    KEINE DELEGATION AN `survives_ausschuss_for`, obwohl die Aussage dieselbe ist: Jenes bildet den
    INNEREN Join nach und antwortet fuer ein Mitglied ohne `PhotoScore`-Zeile `False` - der
    Gruppengewinner staende dann als unumkehrbarer Ausschuss da."""
    suggested_status, duplicate_of, decision = _score_und_entscheidung(photo)
    return (
        DuplicateDecision.KEEP
        if _survives(suggested_status, duplicate_of, decision)
        else DuplicateDecision.DISCARD
    )


def keep_possible_for(photo: Photo) -> bool:
    """Ob "behalten" fuer dieses Mitglied ueberhaupt etwas bewirken kann (ADR 0111 Punkt 2).

    AUSDRUECKLICH KEINE NEUE REGEL, sondern dasselbe Praedikat an einer HYPOTHETISCHEN
    Entscheidung: Die tatsaechlich gespeicherte Zeile wird nicht gelesen. `false` ist es genau
    dann, wenn `duplicate_of IS NULL AND suggested_status IS NOT NULL` - der Ausschuss folgt dann
    nicht aus dem Duplikat, und `keep` wirkt laut ADR 0104 Punkt 3 nicht. Ein solches Mitglied
    steht unveraenderlich auf `discard`; die Ansicht bietet dort keine Wahl an, statt einen Klick
    anzunehmen, der still wirkungslos bleibt."""
    suggested_status, duplicate_of, _decision = _score_und_entscheidung(photo)
    return _survives(suggested_status, duplicate_of, DuplicateDecision.KEEP)


def has_open_suggestion_for(photo: Photo) -> bool:
    """Die Objektfassung von "offener Vorschlag" - siehe `has_open_suggestion()`."""
    score = photo.score
    if score is None:
        return False
    return score.suggested_status is not None and photo.duplicate_decision is None


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
    damit durch die Zahl der erkannten Duplikate begrenzt und nicht durch die Projektgroesse.

    `photo_duplicate_decisions` wird NICHT mitgelesen (AK6): Die Gruppenreihenfolge kennt keinen
    Unterschied zwischen offen und erledigt, und eine mitgeladene Auskunft darueber waere eine
    Einladung, den Zaehler wieder daran zu haengen."""
    rows = (
        await session.execute(
            select(Photo.id, PhotoScore.duplicate_of, Photo.taken_at)
            .outerjoin(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(Photo.project_id == project_id, _project_member_condition(project_id))
        )
    ).all()
    return [
        DuplicateLink(photo_id=photo_id, duplicate_of=duplicate_of, taken_at=taken_at)
        for photo_id, duplicate_of, taken_at in rows
    ]
