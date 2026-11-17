"""Der Ausschuss: die Uebersicht der abgelehnten Fotos und ihrer Begruendung."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as PathParam
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from photosort.api.deps import get_current_user, get_session
from photosort.api.persons import photo_person_outs
from photosort.api.photos._conversion import NO_PLACE, PhotoOut, _suggestion_reason, _to_photo_out
from photosort.api.photos._reads import (
    MAX_QUERY_POSITION,
    _album_level_source,
    _auto_decided_ids,
    _event_and_location_by_photo_id,
    _event_ids_from_rankings,
    _final_selection_decisions,
    _get_project_or_404,
    _latest_successful_criterion_scoring_run_id,
    _partition_sizes,
    _photos_by_id,
    _ranking_by_photo_id,
    _user_count,
)
from photosort.duplicates import (
    DuplicateLink,
    GroupSlot,
    SingleSlot,
    auto_decided_for,
    auto_decided_representatives,
    decision_effective_for,
    decision_without_suggestion_for,
    group_ausschuss_stock,
    has_ausschuss_entry,
    has_open_suggestion,
    keep_possible_for,
    load_duplicate_links,
    representative_of,
)
from photosort.models import (
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    User,
)
from photosort.motif_strengths import load_effective_strengths
from photosort.persons import load_effective_persons

router = APIRouter()


def _ausschuss_reason(photo: Photo) -> Literal["duplicate", "low_quality", "earlier_decision"]:
    """Der Grund der Markierung im Ausschuss - `_suggestion_reason` plus den dritten Fall.

    `earlier_decision`: Der Lauf hat `suggested_status` UND `duplicate_of` zurueckgesetzt, die
    Entscheidungszeile steht aber noch. Die Praesenzgrenze bleibt in `duplicates.py`
    (`decision_without_suggestion_for`); ohne eigenen Wert stuende die Aufnahme als "geringe
    Bildqualitaet" da, obwohl der Lauf sie gar nicht abgelehnt hat."""
    score = photo.score
    assert score is not None
    if decision_without_suggestion_for(photo):
        return "earlier_decision"
    return _suggestion_reason(score)


class AusschussPhotoEntryOut(BaseModel):
    """EIN Einzel-Eintrag der Ausschuss-Uebersicht (`kind = "photo"`).

    Im Listenzweig steht er fuer jede Bestandsaufnahme OHNE aufloesbare Duplikatgruppe; eine
    Aufnahme mit Gruppe liegt im Stapel ihrer Gruppe (`AusschussGroupEntryOut`). Am Detailfilter
    `?photo=<id>` steht er fuer jede Bestandsaufnahme, auch fuer ein Gruppenmitglied.

    `reason` ist der GRUND der Markierung und kommt vom Server, nicht aus einer TypeScript-Ableitung
    (Auflage S7): `duplicate` genau dann, wenn `PhotoScore.duplicate_of IS NOT NULL`,
    `earlier_decision`, wenn `suggested_status` UND `duplicate_of` leer sind, aber eine
    Entscheidungszeile existiert, sonst `low_quality` (`_ausschuss_reason`, dieselbe Ableitung wie
    `_suggestion_reason`). Der Grund ist damit unterscheidbar, statt ein Sammelzustand zu sein
    (AK4); `SuggestionOut.reason` bleibt zweiwertig.

    `decision` ist der GESPEICHERTE Zeilenwert aus `photo_duplicate_decisions`, ausdruecklich NICHT
    `duplicates.py::effective_decision_for` (ADR 0111 Punkt 1): Die Uebersicht zeigt den
    Sichtungsfortschritt, und ein unwirksames `keep` (Unschaerfe-Ablehnung ohne Gruppe) bleibt als
    gespeicherte Handlung sichtbar. Die Detailansicht zieht dieselbe Groesse, damit Uebersicht und
    Detail ueber denselben Bildzustand sprechen. Ein `null` heisst "noch nicht entschieden"; es gibt
    keinen Weg zurueck in diesen Zustand.

    `group_anchor_photo_id` ist der Repraesentant der Duplikatgruppe des Fotos oder `null`. Er
    entsteht ueber `duplicates.py::representative_of` aus der PROJEKTBEGRENZTEN Kantenliste (Auflage
    S6): `PhotoScore.duplicate_of` zeigt auf `photos.id` ohne Projektbedingung, eine eigene Abfrage
    darauf koennte den Gewinner eines fremden Projekts nennen. Eine Zugriffsmarke ist die Id nicht -
    die Folgeanfrage laeuft erneut ueber `project_id`.

    `keep_possible` ist die WIRKSAMKEIT des angebotenen "behalten" und kommt vom Server
    (`duplicates.py::keep_possible_for`, Auflage S7): Ein `keep` wirkt nur ueber eine Gruppe
    (`duplicate_of IS NOT NULL`), sonst hebt es eine Ablehnung nicht auf. Aus `reason` ist das
    AUSDRUECKLICH NICHT ableitbar - ein Eintrag aus einem frueheren Lauf traegt `earlier_decision`
    und trotzdem `true`. Eine zweite Ableitung im Client naehme dem Nutzer dort die einzige
    Handlung, die die Aufnahme zurueckholt.

    `decision_effective` ist die WIRKSAMKEIT der gespeicherten Zeile
    (`duplicates.py::decision_effective_for`, Auflage S7): `null` ohne Zeile, `true` fuer ein
    `discard`, fuer ein `keep` nur, solange `duplicate_of IS NOT NULL`. Ein veraltetes `keep` ist
    `false` - der Client markiert es dann als "wirkt nicht mehr", statt es abzuleiten."""

    kind: Literal["photo"]
    photo: PhotoOut
    reason: Literal["duplicate", "low_quality", "earlier_decision"]
    decision: DuplicateDecision | None
    group_anchor_photo_id: int | None
    keep_possible: bool
    decision_effective: bool | None
    # Spec 0639: Der Merker selbst (Verlierer) bzw. die Zugehoerigkeit zu einem automatisch
    # entschiedenen Stern (Repraesentant ueber die automatischen Kanten).
    auto_decided: bool


class DecisionCountsOut(BaseModel):
    """Die GESPEICHERTEN Zeilen der Bestandsmitglieder eines Stapels - dieselbe Groesse wie
    `decision` am Einzel-Eintrag, nicht der angezeigte Zustand. Es gilt
    `undecided + keep + discard = member_count`."""

    undecided: int
    keep: int
    discard: int


class AusschussGroupEntryOut(BaseModel):
    """EIN Stapel der Ausschuss-Uebersicht: alle Bestandsaufnahmen EINER Duplikatgruppe.

    `group_anchor_photo_id` ist der Repraesentant - dieselbe Id, unter der die Gruppenantwort
    erreichbar ist. `cover` ist die erste Bestandsaufnahme der Gruppe nach (`taken_at`, `id`), nicht
    zwingend der Gewinner. `member_count` zaehlt die Bestandsaufnahmen der Gruppe, `group_size`
    alle ihre Mitglieder (dieselbe Zahl wie die Mitgliederzahl der Gruppenantwort);
    `1 <= member_count <= group_size`.

    SICHERHEIT (S8): Anker, `cover` und beide Zahlen stammen aus dem projektbegrenzten Bestand und
    `load_duplicate_links(session, project.id)`, gruppiert allein ueber `representative_of`
    (`duplicates.py::group_ausschuss_stock`). Eine eigene SQL-Fassung des Sterns ist untersagt:
    `duplicate_of` zeigt ohne Projektbedingung auf `photos.id`, der Stapel naehme sonst fremde
    Aufnahmen auf oder nennte eine fremde Id als Anker."""

    kind: Literal["group"]
    group_anchor_photo_id: int
    cover: PhotoOut
    member_count: int
    group_size: int
    decision_counts: DecisionCountsOut
    # Spec 0639: ganz automatisch entschieden oder gar nicht; `decision_counts` bleibt die Zahl
    # der GESPEICHERTEN Zeilen (dort null) und behaelt damit seine Bedeutung.
    auto_decided: bool


AusschussEntryOut = Annotated[
    AusschussPhotoEntryOut | AusschussGroupEntryOut, Field(discriminator="kind")
]


class AusschussOut(BaseModel):
    """Die Antwort des Ausschuss-Lesepfads: der Bestand, seine Groesse und die Zahl der offenen
    Vorschlaege.

    `total` zaehlt die EINTRAEGE des Gesamtbestands (Einzel-Eintraege und Stapel, paginierbar),
    `open_count` die projektweite Zahl der AUFNAHMEN mit offenem Vorschlag - unabhaengig von
    `limit`/`offset`. Die beiden Einheiten fallen auseinander, sobald ein Stapel mehr als eine
    offene Aufnahme traegt. Der Bestaetigungsbutton nennt genau `open_count` (AK9), weil der
    Abschluss je Aufnahme schreibt; aus `len(items)` gebildet nennte er auf der zweiten Seite eine
    andere Zahl, und ein bereits entschiedenes Bild zaehlte mit.

    SICHERHEIT (S8 der Spec 0525, S9 der Spec 0533): Die Antwort traegt `PhotoOut` samt
    `suggestion`/`ratings` - am Einzel-Eintrag als `photo`, am Stapel als `cover` - und ist damit in
    BEIDEN Eintragsarten eine Funktion des ANFRAGENDEN Nutzers. Bekaeme sie je eine
    Zwischenspeicherung, ein `ETag`, ein `Cache-Control` ueber `no-store` hinaus oder einen
    clientseitigen Laufzeit-Cache, muss der Schluessel den Nutzer enthalten - sonst saehe der eine
    Nutzer Vorschlagsanzeige und Bewertungen aus der Sicht des anderen. Dass `decision_counts`,
    `total` und `open_count` nutzerunabhaengig sind, erlaubt nichts anderes."""

    items: list[AusschussEntryOut]
    total: int
    open_count: int
    # Spec 0639: Zahl der automatisch entschiedenen GRUPPEN, projektweit und unabhaengig von
    # `limit`/`offset`/Filter - wie `open_count` eine Aussage ueber den ganzen Bestand.
    auto_decided_group_count: int


async def _ausschuss_photo_outs(
    session: AsyncSession,
    project: Project,
    ids: list[int],
    current_user_id: int,
) -> tuple[dict[int, Photo], dict[int, PhotoOut]]:
    """Hydratisiert die Aufnahmen EINER Seite - Einzel-Eintraege und Titelbilder - mit derselben
    Kontextbeschaffung wie die Fotoliste (Rang, Partition, Ort/Event, Motive, Endauswahl), damit
    jede dieselben `PhotoOut`-Felder traegt wie jedes andere Foto. Nur die Seite, nie der ganze
    Bestand."""
    if not ids:
        return {}, {}
    photos_by_id = await _photos_by_id(session, ids)
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project.id)
    rankings_by_id = (
        await _ranking_by_photo_id(session, latest_run_id, ids) if latest_run_id is not None else {}
    )
    partition_sizes = (
        await _partition_sizes(session, latest_run_id) if latest_run_id is not None else {}
    )
    place_by_id = await _event_and_location_by_photo_id(
        session, project.id, latest_run_id, photos_by_id, _event_ids_from_rankings(rankings_by_id)
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    persons_by_id = await load_effective_persons(session, ids)
    decisions = await _final_selection_decisions(session, ids)
    user_count = await _user_count(session)
    album_level_source = await _album_level_source(session, project)
    return photos_by_id, {
        photo_id: _to_photo_out(
            photos_by_id[photo_id],
            current_user_id,
            project,
            rankings_by_id.get(photo_id),
            partition_sizes,
            # Keine `curation_position`: Der Ausschuss ist keine numerierte Auswahl.
            None,
            place_by_id.get(photo_id, NO_PLACE),
            motifs_by_id.get(photo_id),
            decisions=decisions,
            user_count=user_count,
            persons=photo_person_outs(persons_by_id.get(photo_id, [])),
            album_level_source=album_level_source,
        )
        for photo_id in ids
    }


def _ausschuss_photo_entry_out(
    photo: Photo,
    photo_out: PhotoOut,
    links: list[DuplicateLink],
    auto_links: list[DuplicateLink],
) -> AusschussPhotoEntryOut:
    score = photo.score
    # Der Bestand ist ueber den inneren Join auf `PhotoScore` gebildet - hier kann die Zeile
    # nicht fehlen. Der Zweig steht trotzdem, weil `mypy --strict` sonst das `None` durchliesse.
    assert score is not None
    entscheidung = photo.duplicate_decision
    return AusschussPhotoEntryOut(
        kind="photo",
        photo=photo_out,
        # SICHERHEIT (S7): die vorhandene Ableitung plus den dritten Fall, nicht eine zweite
        # Fassung davon.
        reason=_ausschuss_reason(photo),
        decision=None if entscheidung is None else entscheidung.decision,
        group_anchor_photo_id=representative_of(photo.id, links),
        # SICHERHEIT (S7), zwei Unabhaengige Aussagen: die Wirksamkeit des angebotenen "behalten"
        # und die der gespeicherten Zeile. Beide stammen aus `duplicates.py`, keine Ableitung im
        # Client (siehe `AusschussPhotoEntryOut`).
        keep_possible=keep_possible_for(photo),
        decision_effective=decision_effective_for(photo),
        auto_decided=auto_decided_for(photo, auto_links),
    )


def _ausschuss_group_entry_out(
    slot: GroupSlot, cover: PhotoOut, auto_representatives: set[int]
) -> AusschussGroupEntryOut:
    return AusschussGroupEntryOut(
        kind="group",
        group_anchor_photo_id=slot.anchor_id,
        cover=cover,
        member_count=len(slot.member_ids),
        group_size=slot.group_size,
        decision_counts=DecisionCountsOut(
            undecided=slot.decision_counts.undecided,
            keep=slot.decision_counts.keep,
            discard=slot.decision_counts.discard,
        ),
        auto_decided=slot.anchor_id in auto_representatives,
    )


@router.get("/projects/{project_id}/ausschuss", response_model=AusschussOut)
async def list_ausschuss(
    # SICHERHEIT (S5): deklarativ begrenzt wie der Gruppen-Index daneben - ein unbeschraenkter
    # Pydantic-`int` erreicht die Datenbank und wird jenseits von 2^63 zu `500` statt `404`.
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    # Die Detailansicht der Schritt-Route ist derselbe Endpunkt mit gesetztem Filter (AK5, AK8):
    # `items` traegt dann GENAU den passenden Eintrag oder eine leere Liste, `total`/`open_count`
    # bleiben projektweit, und `limit`/`offset` sind in diesem Zweig ohne Wirkung - das Muster des
    # Alternativ-Zweigs der Fotoliste. Damit ist der Deep-Link `?photo=<id>` auch fuer eine Aufnahme
    # ausserhalb der geladenen Seite definiert.
    #
    # SICHERHEIT (S5): deklarativ begrenzt, BEVOR der Wert die Datenbank erreicht - ein
    # unbeschraenkter Pydantic-`int` wird jenseits von 2^63 zu `500` statt einer leeren Liste.
    photo_id: int | None = Query(None, ge=1, le=MAX_QUERY_POSITION),
    # Spec 0639: Der Filter liegt nur in der Adresse (`?auto_decided=true`); `false` wirkt wie
    # weggelassen. Zusammen mit `photo_id` ist er widerspruechlich und wird VOR jeder Abfrage
    # abgewiesen (422) - der Detailzweig liefert immer genau einen Eintrag.
    auto_decided: bool = Query(False),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S5): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste (siehe Kopfkommentar der Datei), und
    # `_protected_router_operations()` in `test_auth_guard.py` fuehrt ihn nicht - fuer ihn gibt es
    # KEIN Vollstaendigkeitsnetz. Ein Endpunkt, der diesen Parameter vergisst, waere STILL
    # OEFFENTLICH: kein Fehler, keine 401, nur Daten. Der eigene, pfadbenannte 401-Fall steht in
    # `tests/test_api_ausschuss.py`.
    current_user: User = Depends(get_current_user),
) -> AusschussOut:
    """Der Ausschuss-BESTAND dieses Projekts: offene Vorschlaege und getroffene Entscheidungen,
    mit Grund, gespeicherter Entscheidung und Gruppenanker.

    Der Bestand ist die VEREINIGUNG beider Ursachen - "offener Vorschlag" UND
    "Entscheidungszeile", also offen, angenommen und aufgehoben zusammen (AK1, AK3). Er ist
    ausdruecklich NICHT `NOT ueberlebt`: Eine mit `Ausschuss` entschiedene Aufnahme ist weder
    Ueberlebende noch offener Vorschlag.

    SICHERHEIT (S1/S6): Projektbindung und Bestandsbedingung stehen als UND-Glieder in DERSELBEN
    Anweisung, nie als nachgelagerter Filter ueber einer bereits gebildeten Menge.
    `duplicates.py::has_open_suggestion` traegt selbst keine Projektbedingung - ohne
    `Photo.project_id == project_id` daneben lieferte der Endpunkt jeden offenen Vorschlag der
    ganzen Instanz aus. `PhotoScore.duplicate_of` zeigt auf `photos.id` ohne Projektbedingung; der
    Gruppenanker stammt deshalb aus der bereits projektbegrenzten Kantenliste. Eine unbekannte oder
    fremde `photo_id` liefert eine leere Liste, ununterscheidbar von einer unbekannten.

    KEIN `404`/`409` fuer "nichts gefunden": Der leere Ausschuss ist ein regulaerer Zustand (AK14) -
    auch ohne erfolgreichen `ScoringRun` und bei einem Projekt ganz ohne Fotos. `404` gibt es allein
    fuer ein unbekanntes Projekt, ohne den uebergebenen Wert zu spiegeln; `422` fuer eine Id
    ausserhalb der Grenzen.

    Reihenfolge und Paginierung nach EINTRAEGEN: Jeder Eintrag steht an der
    Stelle seiner ersten Bestandsaufnahme (`Photo.taken_at, Photo.id`), `limit`/`offset`/`total`
    zaehlen Einzel-Eintraege und Stapel. Geschnitten wird erst NACH dem Gruppieren - ein
    SQL-`LIMIT` davor zerlegte eine Gruppe ueber zwei Seiten in zwei Stapel. `open_count` ist
    davon unabhaengig und nennt die Zahl der Aufnahmen, die der Bestaetigungsbutton traegt
    (AK9)."""
    if auto_decided and photo_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("auto_decided=true ist nicht mit photo_id kombinierbar."),
        )

    project = await _get_project_or_404(project_id, session)

    # Eine Anweisung, zwei UND-Glieder: die Projektbindung und der Bestand. `has_ausschuss_entry`
    # zieht dieselbe Praesenzgrenze wie das Ueberlebenden-Praedikat und steht NICHT ausgeschrieben
    # hier (Auflage S9 - eine zweite Fassung daneben liefe ohne Fehler und ohne Meldung weg). Die
    # gespeicherte Entscheidung kommt ueber einen ALIAS: `has_ausschuss_entry` korreliert seine
    # Unterabfrage auf `photo_duplicate_decisions`, und dieselbe Tabelle unaliasiert im FROM
    # zoege die Korrelation an sich.
    entscheidung = aliased(PhotoDuplicateDecision)
    bestand = (
        (
            await session.execute(
                select(Photo.id, Photo.taken_at, entscheidung.decision)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .outerjoin(entscheidung, entscheidung.photo_id == Photo.id)
                .where(Photo.project_id == project_id, has_ausschuss_entry())
                .order_by(Photo.taken_at, Photo.id)
            )
        )
        .tuples()
        .all()
    )
    # SICHERHEIT (S8): Gruppenschluessel, Anker, Titelbild und Mitglieder stammen allein aus dem
    # projektbegrenzten Bestand und diesen Kanten - nie aus einem eigenen SQL-Stern.
    links = await load_duplicate_links(session, project.id)
    slots = group_ausschuss_stock(bestand, links)
    auto_ids = await _auto_decided_ids(session, project.id)
    auto_representatives = auto_decided_representatives(links, auto_ids)
    auto_links = [link for link in links if link.photo_id in auto_ids]
    auto_decided_group_count = len(auto_representatives)

    # SICHERHEIT (S1): dieselbe ausgeschriebene Projektbindung wie der Bestand - eine Zaehlung ohne
    # sie gaebe dem Button eine Zahl, die auf dieser Seite niemand einloesen kann.
    open_count = (
        await session.execute(
            select(func.count())
            .select_from(Photo)
            .join(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(Photo.project_id == project_id, has_open_suggestion())
        )
    ).scalar_one()

    if photo_id is not None:
        # Der Detail-Zweig: GENAU der passende Einzel-Eintrag oder gar keiner, auch fuer ein
        # Gruppenmitglied (dann mit Anker). `limit`/`offset` sind hier bewusst ohne Wirkung - die
        # Antwort ist der eine Eintrag, nicht eine Seite. Eine fremde oder unbekannte Id steht nicht
        # im projektbegrenzten Bestand und ergibt die leere Liste.
        ids = [photo_id] if any(row[0] == photo_id for row in bestand) else []
        photos_by_id, outs = await _ausschuss_photo_outs(session, project, ids, current_user.id)
        detail: list[AusschussEntryOut] = [
            _ausschuss_photo_entry_out(photos_by_id[pid], outs[pid], links, auto_links)
            for pid in ids
        ]
        return AusschussOut(
            items=detail,
            total=len(slots),
            open_count=open_count,
            auto_decided_group_count=auto_decided_group_count,
        )

    if auto_decided:
        slots = [
            slot
            for slot in slots
            if isinstance(slot, GroupSlot) and slot.anchor_id in auto_representatives
        ]
    seite = slots[offset : offset + limit]
    ids = [slot.photo_id if isinstance(slot, SingleSlot) else slot.cover_id for slot in seite]
    photos_by_id, outs = await _ausschuss_photo_outs(session, project, ids, current_user.id)
    items: list[AusschussEntryOut] = [
        _ausschuss_photo_entry_out(
            photos_by_id[slot.photo_id], outs[slot.photo_id], links, auto_links
        )
        if isinstance(slot, SingleSlot)
        else _ausschuss_group_entry_out(slot, outs[slot.cover_id], auto_representatives)
        for slot in seite
    ]
    return AusschussOut(
        items=items,
        total=len(slots),
        open_count=open_count,
        auto_decided_group_count=auto_decided_group_count,
    )
