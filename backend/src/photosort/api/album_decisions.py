"""Der Schreibendpunkt der gemeinsamen Endauswahl - die Entscheidung des PROJEKTS ueber ein Foto.

EIGENES MODUL UND EIGENER ROUTER, weil die Entscheidung keinen Nutzer kennt: Der Endpunkt nimmt
KEIN `current_user` entgegen. Er gehoert ausdruecklich nicht nach `api/ratings.py` - dessen
Gegenstand ist die Aussage EINES Nutzers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.feedback_log import load_frozen_context, record_final_decision
from photosort.models import FeedbackEventKind, FinalSelectionDecision, Photo

# SICHERHEIT (S1): Der Torwaechter haengt am ROUTER, nicht am Endpunkt - und genau das ist hier
# moeglich, weil kein Endpunkt dieses Routers das `User`-Objekt selbst braucht.
#
# Dieser Endpunkt ist der einzige Schreibendpunkt des Projekts, dessen Authentifizierung an der
# Funktionssignatur NICHT sichtbar ist: Es gibt keinen `current_user`, dessen Fehlen auffiele. Er
# traegt deshalb DREI Sicherungen statt einer - die Router-Dependency hier, den Eintrag in
# `tests/test_auth_guard.py::_protected_router_operations()` und einen eigenen, pfadbenannten
# 401-Fall in `tests/test_api_album_decisions.py`. Die Doppelung traegt, weil der Listeneintrag
# weder sein eigenes Vergessen noch eine spaetere Verschiebung des Endpunkts in einen Router ohne
# `dependencies`-Liste (`photos.router`, `ratings.router`) ueberlebt. In beiden Faellen waere der
# Endpunkt STILL OEFFENTLICH: ein unauthentifizierter Schreibzugriff, der die Bildmenge des Albums
# aendert.
router = APIRouter(tags=["album"], dependencies=[Depends(get_current_user)])

# SICHERHEIT (S3): Obergrenze der fremdgesteuerten Pfad-Id, deklarativ VOR jeder Verwendung. Ein
# Pydantic-`int` ist unbeschraenkt und landet direkt in `session.get(Photo, photo_id)`; jenseits
# von 2^63 wirft SQLite einen `OverflowError` und der Endpunkt antwortete `500` statt `404`.
#
# Der Wert laesst die `1` zu, die `_protected_router_operations()` in seine Pfade einsetzt - waere
# die Grenze enger, antwortete der Vollstaendigkeitstest `422` statt `401` und pruefte die Auth
# gar nicht mehr. Die heute unbegrenzten Pfad-Ids der Bestandsendpunkte werden dabei bewusst
# NICHT mitgezogen.
_MAX_PHOTO_ID = 1_000_000_000


class AlbumDecisionIn(BaseModel):
    """SICHERHEIT (S4): der Body traegt AUSSCHLIESSLICH `included`, pflichtig und ohne `null`.

    Kein `photo_id`, kein `user_id`, kein `updated_at` im Eingabeschema - Massenzuweisung ist
    strukturell ausgeschlossen statt im Handler herausgefiltert.

    KEIN VORGABEWERT, aus demselben Grund, aus dem die Spalte keinen traegt: Die Abwesenheit der
    Zeile heisst "unentschieden". Ein aus Bequemlichkeit gesetztes `False` verlegte genau diese
    Entscheidung in die Auswertung einer fehlerhaften Anfrage - ein abgeschnittener oder leerer
    Body naehme das Foto aus dem Album, mit `200` als Antwort und ohne dass eine Anzeige das als
    falsch ausweist. Es gibt keinen Weg zurueck nach "unentschieden"; ein so entstandener Zustand
    ist nicht korrigierbar, nur ueberschreibbar."""

    included: bool


class AlbumDecisionOut(BaseModel):
    """Der PERSISTIERTE Zustand nach dem Schreibvorgang (Auflage S5).

    Er wird aus der Zeile gebildet, nie aus dem Body zurueckgespiegelt: Die Oberflaeche nimmt den
    eigenen Query-Schluessel von der Invalidierung aus und schreibt genau diesen Wert fort. Ein
    Echo des Bodys zeigte nach einem verlorenen Wettlauf dauerhaft eine Zugehoerigkeit an, die so
    nicht gespeichert ist - sichtbar erst nach einem vollstaendigen Neuladen, und bis dahin
    entscheiden die beiden anhand einer Anzeige, die etwas anderes behauptet als die Datenbank."""

    photo_id: int
    included: bool
    updated_at: datetime


async def _get_photo_or_404(photo_id: int, session: AsyncSession) -> Photo:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


async def _existing_decision(session: AsyncSession, photo_id: int) -> FinalSelectionDecision | None:
    return (
        await session.execute(
            select(FinalSelectionDecision).where(FinalSelectionDecision.photo_id == photo_id)
        )
    ).scalar_one_or_none()


@router.put("/photos/{photo_id}/album-decision", response_model=AlbumDecisionOut)
async def set_album_decision(
    photo_id: Annotated[int, Path(ge=1, le=_MAX_PHOTO_ID)],
    payload: AlbumDecisionIn,
    session: AsyncSession = Depends(get_session),
) -> AlbumDecisionOut:
    """Setzt die GEMEINSAME Entscheidung des Projekts ueber dieses Foto: gehoert es in die
    Endauswahl oder nicht.

    Sie ist KEINE Aussage eines Nutzers - anders als `PUT /photos/{id}/rating`. Wer angemeldet
    ist, spielt fuer ihre Wirkung keine Rolle, jeder kann jede Entscheidung aendern, und es wird
    weder bestaetigt noch abgestimmt noch auf jemanden gewartet: die beiden sitzen beim
    Entscheiden vor EINEM Geraet.

    Sie gilt sofort und UEBERSCHREIBT die Vorbelegung aus der Einigkeit beider Entwuerfe - in
    beide Richtungen. Ein einig-drinnes Bild laesst sich damit herausnehmen und danach wieder
    aufnehmen; Einigkeit ist eine Vorbelegung, keine Sperre. Sie ueberlebt umgekehrt jede spaetere
    Aenderung eines Einzelentwurfs und jeden neuen Vorschlagslauf, weil beide ausschliesslich in
    den Zweig OHNE Entscheidung hineinwirken.

    Die beiden Einzelentwuerfe bleiben unberuehrt: Diese Zeile liegt eine Ebene UEBER ihnen und
    traegt keinen Nutzerbezug.

    `404` fuer ein unbekanntes Foto, `422` fuer eine Pfad-Id ausserhalb der Grenzen oder einen
    Body ohne ausdrueckliches `included`, `409` bei einem gleichzeitigen Schreibversuch, der sich
    nicht aufloesen laesst. Wiederholte identische Aufrufe bleiben folgenlos.

    ES GIBT KEIN `DELETE`: "wieder strittig werden" ist kein Zustand, den die Story kennt; aendern
    heisst den anderen Wert schreiben.

    SICHERHEIT (S3): Die Bindung laeuft ausschliesslich ueber die globale `photo_id` - keine
    Projektaufloesung, keine Mitgliedschaftspruefung, Muster `PUT /photos/{id}/rating`. Beide
    Nutzer sehen alle Projekte; es gibt keine Grenze, die hier zu ziehen waere. Der uebergebene
    Wert wird nicht zurueckgespiegelt.

    Jede tatsaechliche AENDERUNG wird im Ereignis-Log der Nacharbeit festgehalten (Spec 0432) -
    OHNE Nutzer (S9), weil die Entscheidung dem Projekt gehoert, und mit hoeherem Gewicht, weil
    sie das Urteil beider Personen ist. Ein wiederholtes identisches `included` ist keine
    Korrektur und erzeugt nichts."""
    # Die `project_id` VOR dem `flush` festhalten: Dessen `rollback`-Zweig laesst jedes geladene
    # Objekt expired zurueck, und ein danach angefasstes Attribut braeche unter `asyncio` mit
    # `MissingGreenlet` - ausgerechnet im Zweig, der den Wettlauf-Fall behandelt.
    project_id = (await _get_photo_or_404(photo_id, session)).project_id

    decision = await _existing_decision(session, photo_id)
    # NUR BEI TATSAECHLICHER AENDERUNG (ADR 0100 Punkt 4). Die Abwesenheit der Zeile heisst
    # "unentschieden" und ist damit selbst ein Vorzustand, von dem aus jede Richtung ein Wechsel
    # ist.
    changed = decision is None or decision.included != payload.included
    if decision is None:
        decision = FinalSelectionDecision(photo_id=photo_id, included=payload.included)
        session.add(decision)
    else:
        decision.included = payload.included
        # `updated_at` traegt `onupdate=func.now()` und wird nie von Hand gesetzt.

    # SICHERHEIT (S6): der `flush` VOR dem `commit` bringt den Primaerschluessel auf `photo_id`
    # hier zum Tragen. Die Arbeitssicht laedt zum schnellen Durchklicken ein und jede Kachel
    # traegt zwei Schaltflaechen; zwei gleichzeitige Anfragen sehen beide "keine Zeile" und fuegen
    # beide ein. Ohne diese Behandlung waere das Ergebnis eine `500` auf einen alltaeglichen
    # Doppeldruck, und der Aufrufer wuesste nicht, welcher der beiden Werte gilt.
    #
    # Bewusst getragen bleibt "der letzte Schreibende gewinnt": Es gibt keine
    # Optimistic-Locking-Pruefung, weil die beiden ausdruecklich vor EINEM Geraet sitzen.
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        decision = await _existing_decision(session, photo_id)
        if decision is None:
            # Der Konflikt kam nicht aus dieser Zeile - es gibt nichts, worauf die Aenderung
            # anzuwenden waere. `409` statt `500`, und ausdruecklich statt eines stillen `200`
            # ohne geschriebene Zeile.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Die Entscheidung zu diesem Foto wurde gerade veraendert. "
                    "Bitte erneut versuchen."
                ),
            ) from None
        decision.included = payload.included
        await session.flush()

    if changed:
        # KEIN `user_id` (S9) - und der Endpunkt koennte gar keines liefern: Dieser Router nimmt
        # bewusst kein `current_user` entgegen, und ein struktureller Waechter haelt das fest.
        await record_final_decision(
            session,
            project_id=project_id,
            photo_id=photo_id,
            kind=(
                FeedbackEventKind.FINAL_DECISION_IN
                if payload.included
                else FeedbackEventKind.FINAL_DECISION_OUT
            ),
            context=await load_frozen_context(session, project_id=project_id, photo_id=photo_id),
        )
    await session.commit()
    await session.refresh(decision)
    return AlbumDecisionOut(
        photo_id=decision.photo_id, included=decision.included, updated_at=decision.updated_at
    )
