"""Die Duplikat-Gruppen eines Projekts: der Einstieg in den Durchgang und die Gruppe selbst."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Path as PathParam
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.api.persons import photo_person_outs
from photosort.api.photos._conversion import NO_PLACE, PhotoOut, _to_photo_out
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
    all_group_representative_ids,
    auto_decided_representatives,
    effective_decision_for,
    group_span_seconds,
    group_standing,
    keep_possible_for,
    load_duplicate_links,
    member_ids_of,
    representative_of,
)
from photosort.models import DuplicateDecision, Photo, Project, User
from photosort.motif_strengths import load_effective_strengths
from photosort.persons import load_effective_persons

router = APIRouter()


class DuplicateGroupPhotoOut(BaseModel):
    """Ein Mitglied der Duplikat-Gruppe: das Foto, sein wirksamer Zustand und ob sich dieser
    ueberhaupt aendern laesst.

    DIE ANTWORT NENNT DIE AUSWERTUNG DES UEBERLEBENS-PRAEDIKATS, NICHT DIE ENTSCHEIDUNGSZEILE
    (ADR 0111). Die beiden fielen genau dort auseinander, wo keine Zeile steht: Ein unentschiedener
    Duplikat-Verlierer traegt `suggested_status = REJECTED` und scheidet aus, sah aber aus wie der
    Repraesentant, der bleibt. Es gibt deshalb keinen dritten Wert und kein `null`, und aus der
    Antwort geht nicht hervor, ob ein Zustand vom Automaten oder vom Nutzer stammt.

    `keep_possible = false` heisst: Kein Wert der Entscheidungszeile aendert diesen Zustand - die
    Ablehnung folgt nicht aus dem Duplikat. Der GRUND reist nicht als Feld, weil er aus der
    Bedingung selbst folgt; die Oberflaeche rendert dort einen festen Text. Entstuende ein dritter
    Ablehnungsgrund, gehoert er ab dann als eigenes Feld hierher (ADR 0111, Konsequenzen) -
    `tests/test_duplikat_anzeigezustand.py` laesst das laut auffallen.

    `sharpness`/`exposure` sind die Rohwerte aus `PhotoScore` (Laplace-Varianz, hoeher = schaerfer;
    Anteil geclippter Pixel, niedriger = besser), `null` ohne Zeile. Sie kommen NIE aus
    `PhotoOut.suggestion`: Das Feld faellt nach jeder Entscheidung und bei eigener Albumbewertung
    auf `null`, und die Bewertungszeile verloere ihre Werte mitten im Durchgang. Keines der
    Mitglieder ist als "bestes" ausgezeichnet - die Auszeichnung bildet die Oberflaeche ueber den
    angezeigten, gerundeten Werten."""

    photo: PhotoOut
    effective_decision: DuplicateDecision
    keep_possible: bool
    sharpness: float | None
    exposure: float | None


class DuplicateGroupOut(BaseModel):
    """Die Antwortform ALLER VIER Endpunkte der Vergleichsansicht - Lesepfad, beide Schreibwege und
    der Gruppenabschluss. Ein Schreibvorgang liefert damit denselben vollstaendigen Stand zurueck,
    den ein erneutes Laden liefern wuerde; die Oberflaeche braucht danach keine zweite Anfrage, um
    zu wissen, was gilt.

    `position`/`total` sind 1-basiert und beziehen sich auf ALLE Duplikat-Gruppen des Projekts.
    `previous_photo_id`/`next_photo_id` tragen die Repraesentanten-Id der jeweils benachbarten
    Gruppe, `null` am Rand - dort ist die Schaltflaeche `disabled`, nicht abwesend.

    SICHERHEIT (S6): Beide Nachbar-Ids stammen aus derselben projektbegrenzten Kantenliste wie die
    Gruppe selbst, nie aus einer eigenen Abfrage auf `photo_scores` - dessen `duplicate_of` zeigt
    auf `photos.id` ohne Projektbedingung. Zugriffsmarken sind sie nicht: Die Folgeanfrage laeuft
    erneut ueber `project_id` und loest eine fremde Id nicht auf.

    `span_seconds` ist der Abstand zwischen fruehestem und spaetestem korrigiertem `taken_at` der
    Mitglieder in ganzen Sekunden, abgerundet - aus derselben projektbegrenzten Kantenliste."""

    items: list[DuplicateGroupPhotoOut]
    position: int
    total: int
    previous_photo_id: int | None
    next_photo_id: int | None
    span_seconds: int
    # Spec 0639: Die Gruppe ist ganz automatisch entschieden oder gar nicht. Das Feld ist reine
    # Leseauskunft; die Entscheidungszeile bleibt unberuehrt und `decision` bleibt `null`."""
    auto_decided: bool


async def build_duplicate_group_out(
    session: AsyncSession, project: Project, photo_id: int, current_user_id: int
) -> DuplicateGroupOut:
    """Bildet den Stern um `photo_id` und hydratisiert seine Mitglieder zur vollen Antwort.

    VON ALLEN VIER ENDPUNKTEN GENUTZT, auch von den drei Schreibwegen im eigenen Router - genau
    deshalb steht der Aufbau hier und nicht im Endpunkt: Die Hydratation (`_photos_by_id`,
    `_to_photo_out` samt Event-, Orts- und Rang-Kontext) haengt an dieser Datei, und eine zweite
    Fassung davon liefe auseinander.

    `404` (als `HTTPException`), wenn es keine Gruppe gibt. Der Fall deckt unbekannte Id, fremdes
    Projekt (die Kantenliste ist bereits projektbegrenzt, S7) und "Foto in keinem Stern" - und
    unterscheidet sie ausdruecklich nicht.

    SICHERHEIT (S10): Die Antwort traegt `PhotoOut` und damit `suggestion`/`ratings`; sie ist
    damit eine Funktion des ANFRAGENDEN Nutzers. Bekaeme sie je eine Zwischenspeicherung, ein
    `ETag` oder ein `Cache-Control` ueber `no-store` hinaus, muss der Schluessel den Nutzer
    enthalten."""
    links = await load_duplicate_links(session, project.id)
    representative_id = representative_of(photo_id, links)
    if representative_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Keine Duplikat-Gruppe zu diesem Foto."
        )
    auto_ids = await _auto_decided_ids(session, project.id)
    auto_representatives = auto_decided_representatives(links, auto_ids)
    stellung = group_standing(representative_id, links)
    # `representative_of` hat die Gruppe soeben aufgeloest - `group_standing` kann sie nicht mehr
    # verfehlen. Der Zweig steht trotzdem, weil `mypy --strict` sonst das `None` durchliesse.
    assert stellung is not None

    ids = member_ids_of(representative_id, links)
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
    final_decisions = await _final_selection_decisions(session, ids)
    user_count = await _user_count(session)
    album_level_source = await _album_level_source(session, project)
    return DuplicateGroupOut(
        items=[
            DuplicateGroupPhotoOut(
                photo=_to_photo_out(
                    photos_by_id[member_id],
                    current_user_id,
                    project,
                    rankings_by_id.get(member_id),
                    partition_sizes,
                    # Keine `curation_position`: Die Gruppe ist keine numerierte Auswahl.
                    None,
                    place_by_id.get(member_id, NO_PLACE),
                    motifs_by_id.get(member_id),
                    decisions=final_decisions,
                    user_count=user_count,
                    persons=photo_person_outs(persons_by_id.get(member_id, [])),
                    album_level_source=album_level_source,
                ),
                # BEIDE WERTE KOMMEN AUS `duplicates.py`, nie als ausgeschriebene Bedingung hier
                # (Auflage S2): Sie ziehen dasselbe Praedikat, das bestimmt, welche Bilder den
                # Homeserver Richtung Cloud-Anbieter verlassen. Eine zweite Fassung liefe von der
                # ersten weg, ohne Fehler und ohne Meldung -
                # `tests/test_ausschuss_ueberlebende.py` schlaegt fuer jede hier ausgeschriebene
                # Fassung an.
                effective_decision=effective_decision_for(photos_by_id[member_id]),
                keep_possible=keep_possible_for(photos_by_id[member_id]),
                # SICHERHEIT (S10): ueber `_score_metrics`, das die fehlende Zeile kennt - ein
                # blosser Attributzugriff wuerfe fuer den Repraesentanten ohne `PhotoScore` und
                # machte die ganze Gruppenantwort zur `500`.
                sharpness=_score_metrics(photos_by_id[member_id])[0],
                exposure=_score_metrics(photos_by_id[member_id])[1],
            )
            for member_id in ids
        ],
        position=stellung.position,
        total=stellung.total,
        previous_photo_id=stellung.previous_id,
        next_photo_id=stellung.next_id,
        span_seconds=group_span_seconds(representative_id, links),
        auto_decided=representative_id in auto_representatives,
    )


def _score_metrics(photo: Photo) -> tuple[float | None, float | None]:
    """`(sharpness, exposure)` aus der `PhotoScore`-Zeile, `(None, None)` ohne Zeile."""
    score = photo.score
    return (None, None) if score is None else (score.sharpness, score.exposure)


def empty_duplicate_group_out() -> DuplicateGroupOut:
    """Der leere Gruppenstand fuer eine Aufnahme OHNE Gruppe (Spec 0525, AK6).

    Der Einzel-Schreibweg nimmt seit Spec 0525 auch die Unschaerfe-Ablehnung an, die in keinem
    Stern liegt: Dort ist die Entscheidung selbst das Ergebnis und es gibt keine Gruppe, die man
    zurueckgeben koennte. Die Antwortform bleibt trotzdem dieselbe `DuplicateGroupOut` - die
    Oberflaeche schreibt den Rueckgabewert der Entscheidung unmittelbar fort und braucht eine
    zweite Anfrage sonst nur, um zu erfahren, dass es nichts zu zeigen gibt.

    `position = 0` ist der eine Wert, der NICHT der 1-basierten Zaehlung der gefuellten Antwort
    folgt, und er ist genau dafuer da: Ein Platz in einer Reihenfolge, die es nicht gibt, waere
    eine erfundene Auskunft. `total = 0` sagt dasselbe ueber die Gesamtzahl."""
    return DuplicateGroupOut(
        items=[],
        position=0,
        total=0,
        previous_photo_id=None,
        next_photo_id=None,
        span_seconds=0,
        auto_decided=False,
    )


class DuplicateGroupIndexOut(BaseModel):
    """Die Auskunft fuer den EINSTIEG: wie viele Duplikat-Gruppen es gibt und wo der Durchgang
    beginnt.

    `first_photo_id` ist `null`, wenn es keine Gruppe gibt - die Oberflaeche rendert den Einstieg
    dann gar nicht, statt auf eine leere Ansicht zu fuehren (AK8).

    KEINE LISTE ALLER GRUPPEN (ADR 0111 Punkt 3): Sie waere eine zweite Quelle derselben
    Reihenfolge neben `position`/`total`, deren Momentaufnahmen auseinanderlaufen koennen. Die
    Nachbarn reisen in der Gruppenantwort selbst."""

    total: int
    first_photo_id: int | None


@router.get("/projects/{project_id}/duplicate-groups", response_model=DuplicateGroupIndexOut)
async def duplicate_group_index(
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste und keinen Vollstaendigkeitstest - ein Endpunkt, der
    # diesen Parameter vergisst, waere STILL OEFFENTLICH (keine 401, nur Daten). Der eigene
    # 401-Fall steht in `tests/test_api_duplicate_group_index.py`.
    current_user: User = Depends(get_current_user),
) -> DuplicateGroupIndexOut:
    """Wie viele Duplikat-Gruppen dieses Projekt hat und ueber welche Aufnahme die erste beginnt.

    Grundlage der beiden Einstiege in die Vergleichsansicht - aus dem Ausschuss-Schritt und aus der
    nach Vorschlaegen gefilterten Fotoliste. Ohne Foto-Hydratation: Die Antwort traegt kein
    `PhotoOut` und ist damit keine Funktion des anfragenden Nutzers.

    `total` ist DIESELBE Zahl wie in `DuplicateGroupOut` und zaehlt alle Gruppen des Projekts,
    entschiedene eingeschlossen.

    SICHERHEIT (S6): `first_photo_id` stammt aus derselben projektbegrenzten Kantenliste wie die
    Gruppe selbst, nie aus einer eigenen Abfrage auf `photo_scores` - dessen `duplicate_of` zeigt
    auf `photos.id` ohne Projektbedingung. Eine Zugriffsmarke ist die Id nicht: Die Folgeanfrage
    laeuft erneut ueber `project_id`.

    `404` fuer ein unbekanntes Projekt, ohne den uebergebenen Wert zu spiegeln. `422` fuer eine
    Pfad-Id ausserhalb der Grenzen - ein unbeschraenkter Pydantic-`int` erreicht die Datenbank und
    wird jenseits von 2^63 zu `500` statt `404`."""
    project = await _get_project_or_404(project_id, session)
    representatives = all_group_representative_ids(await load_duplicate_links(session, project.id))
    return DuplicateGroupIndexOut(
        total=len(representatives),
        first_photo_id=representatives[0] if representatives else None,
    )


@router.get("/projects/{project_id}/duplicate-groups/{photo_id}", response_model=DuplicateGroupOut)
async def duplicate_group(
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    photo_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT: ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE router-weite
    # `dependencies`-Liste (siehe Kopfkommentar der Datei) - ein Endpunkt, der diesen Parameter
    # vergisst, waere STILL OEFFENTLICH.
    current_user: User = Depends(get_current_user),
) -> DuplicateGroupOut:
    """Alle Aufnahmen EINER Duplikat-Gruppe samt ihrem wirksamen Zustand und ihren Nachbargruppen.

    Die Gruppe ist ABGELEITET und nirgends gespeichert (ADR 0104 Punkt 1): Sie ist der Stern ueber
    `PhotoScore.duplicate_of` - der Gewinner und alle, die auf ihn zeigen -, zur Lesezeit gebildet.
    Sie hat deshalb keine eigene Id und ist ueber JEDES ihrer Mitglieder unter derselben Antwort
    erreichbar, den Gewinner eingeschlossen.

    KEIN MITGLIED IST AUSGEZEICHNET. Die Antwort nennt weder Gewinner noch Original noch
    Vorgeschlagenen - die Reihenfolge ist `taken_at`, bei Gleichstand `id`, und sonst nichts.
    Jedes Mitglied traegt aber seinen wirksamen Zustand (`effective_decision`), also das, was ohne
    weiteres Zutun eintritt.

    `position`/`total` beziehen sich auf ALLE Duplikat-Gruppen des Projekts. Eine vollstaendig
    entschiedene Gruppe zaehlt weiter mit und bleibt erreichbar; die Gesamtzahl aendert sich
    waehrend eines Durchgangs nicht, und die Position einer Gruppe verschiebt sich nicht dadurch,
    dass eine andere entschieden wird.

    `404`, wenn es zu dieser Id keine Gruppe gibt - unbekanntes Foto, fremdes Projekt, Foto ohne
    Duplikat, oder ein Vorschlag wegen geringer Bildqualitaet (der traegt kein `duplicate_of`).
    Die vier Faelle sind voneinander nicht unterscheidbar, und die Antwort spiegelt den
    uebergebenen Wert nicht.

    `422` fuer eine Pfad-Id ausserhalb der Grenzen: Ein unbeschraenkter Pydantic-`int` erreicht die
    Datenbank und wird jenseits von 2^63 zu `500` statt `404`."""
    project = await _get_project_or_404(project_id, session)
    return await build_duplicate_group_out(session, project, photo_id, current_user.id)
