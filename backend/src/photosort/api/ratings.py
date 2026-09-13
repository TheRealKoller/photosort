from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.feedback_log import load_frozen_context, record_album_decision
from photosort.models import FeedbackEventKind, Photo, Rating, RatingStatus, User

# Siehe photos.py fuer die Begruendung: current_user als Depends()-Parameter statt Router-Level
# dependencies=[...], da jeder Endpunkt hier das User-Objekt selbst braucht (user_id fuer die
# eigene Bewertung), nicht nur eine reine Auth-Pruefung.
#
# SICHERHEIT (S1): Fuer diesen Router gibt es deshalb KEIN Vollstaendigkeitsnetz -
# `_protected_router_operations()` in tests/test_auth_guard.py fuehrt ihn nicht. Ein hier
# vergessener `current_user`-Parameter waere STILL OEFFENTLICH: kein Fehler, keine 401, nur ein
# unauthentifizierter Schreibzugriff auf eine fremde Bewertungszeile. Jeder Endpunkt bekommt
# deshalb seinen eigenen 401-Nachweis in tests/test_api_ratings.py.
router = APIRouter(tags=["ratings"])


class RatingUpdate(BaseModel):
    """Die Albumentscheidung, und nur sie.

    `status` ist NICHT nullable (Auflage S8): `null` ist kein zulaessiger Body-Wert, sondern
    ausschliesslich das Ergebnis von `DELETE`. Waere er zulaessig, entstuende die verbotene Zeile
    (`status IS NULL AND favorite IS FALSE`) ueber den regulaeren Schreibweg."""

    status: RatingStatus


class FavoriteUpdate(BaseModel):
    favorite: bool


class RatingWriteOut(BaseModel):
    """Der Zustand der eigenen Bewertungszeile NACH dem Schreibvorgang.

    NICHT `RatingOut` - dieser Name gehoert dem Element aus `PhotoOut.ratings[]`
    (`api/photos.py`) und ist eine ANDERE Form. Zwei gleichnamige Modelle in verschiedenen
    Modulen benennt FastAPI in der OpenAPI-Beschreibung auf beiden Seiten um
    (`photosort__api__photos__RatingOut`, `photosort__api__ratings__RatingOut`) - eine stille
    Aenderung an der Beschreibung eines Endpunkts, der gar nicht angefasst wurde.

    `updated_at` ist `None`, wenn die Zeile dabei geleert und damit geloescht wurde - ein dann
    ersatzweise gesetzter Zeitstempel behauptete eine Zeile, die es nicht mehr gibt.

    `user_id` stammt AUSSCHLIESSLICH aus `current_user` (Auflage S7) und benennt den Nutzer, fuer
    den geschrieben wurde. Es steht hier, weil die Entwurfsansicht den geschriebenen Zustand in
    ihre bereits geladene Liste einsetzt, statt sie neu zu laden (Spec 0430): Ein Eintrag von
    `PhotoOut.ratings[]` traegt `user_id`, und ohne dieses Feld muesste der Client eine Id
    ERFINDEN und in seiner zwischengespeicherten Antwort ablegen."""

    photo_id: int
    user_id: int
    status: RatingStatus | None
    favorite: bool
    updated_at: datetime | None


# Bildet den Bestandszustand (`status`, `favorite`) auf den gewuenschten ab. `None` als
# Bestandszustand heisst "noch keine Zeile".
_NextState = Callable[[RatingStatus | None, bool], tuple[RatingStatus | None, bool]]


async def _get_photo_or_404(photo_id: int, session: AsyncSession) -> Photo:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


async def _get_own_rating(session: AsyncSession, photo_id: int, user_id: int) -> Rating | None:
    result = await session.execute(
        select(Rating).where(Rating.photo_id == photo_id, Rating.user_id == user_id)
    )
    return result.scalar_one_or_none()


def album_decision_kind(
    previous: RatingStatus | None, new: RatingStatus | None
) -> FeedbackEventKind | None:
    """Die Uebergangsregel: welche Art von Ereignis aus welchem Zustandswechsel entsteht.

    REIN und DB-FREI, und sie liegt hier neben `_write_own_rating` statt in den Endpunkten: Drei
    Endpunkte durchlaufen dieselbe Schreibstelle, und eine je Endpunkt wiederholte Abbildung waere
    drei Stellen, die auseinanderlaufen koennen.

    `None` heisst AUSDRUECKLICH "kein Ereignis" und ist der Rueckgabewert fuer jeden
    Schreibvorgang, der den Status NICHT bewegt - dieselbe Entscheidung erneut gesetzt, eine nicht
    vorhandene zurueckgenommen (L1, ADR 0100 Punkt 4). Eine Wiederholung ist keine Korrektur, und
    die Story misst Korrekturen.

    Daraus faellt OHNE SONDERFALL heraus, dass `PUT /photos/{id}/favorite` kein Ereignis erzeugt:
    Der Endpunkt laesst `status` unberuehrt, also ist `previous == new`. Das entscheidende
    Praedikat ist der WECHSEL DES STATUS, nicht der Schreibvorgang an der Zeile - mit `record=True`
    als Vorgabewert zeichnete die Auszeichnung als Favorit sonst eine Korrektur auf, die niemand
    vorgenommen hat."""
    if previous == new:
        return None
    if new is None:
        return FeedbackEventKind.DECISION_WITHDRAWN
    if new is RatingStatus.ALBUM_WORTHY:
        return FeedbackEventKind.PHOTO_INCLUDED
    return FeedbackEventKind.PHOTO_REMOVED


async def _write_own_rating(
    session: AsyncSession,
    photo: Photo,
    user_id: int,
    next_state: _NextState,
    *,
    record: bool = True,
) -> RatingWriteOut:
    """DIE EINE Schreibstelle, die alle drei Endpunkte durchlaufen.

    Sie haelt zwei Zusagen, die sonst je Endpunkt neu getroffen werden muessten:

    INVARIANTE (Auflage S8): Es entsteht nie eine Zeile mit `status IS NULL AND favorite IS
    FALSE`, und eine dadurch leer gewordene wird geloescht. Die Loeschung steht hier und nur
    hier - je Endpunkt wiederholt waere sie drei Stellen, die auseinanderlaufen koennen.

    SICHERHEIT (S7): Die Aufsuchbedingung ist ueberall `(photo_id, user_id)`, und `user_id`
    stammt ausschliesslich aus `current_user` - nie aus Body oder Query. Ohne das koennte Nutzer
    A die Zeile von Nutzer B ueberschreiben (Broken Object-Level Authorization). Welches FELD ein
    Endpunkt aendert, entscheidet allein sein `next_state`; der jeweils andere Wert wird aus dem
    Bestand uebernommen und nie aus einem teilbefuellten Modell neu geschrieben.

    SIE COMMITTET NICHT (Auflage S5, Spec 0432): Die Transaktionsgrenze gehoert dem Aufrufer, der
    genau EINMAL committet. Ein `record`-Parameter allein machte den Austausch nicht atomar - der
    erste der beiden Aufrufe waere nach seinem eigenen Commit unwiderruflich geschrieben, und ein
    Fehlschlag des zweiten hinterliesse einen halb ausgefuehrten Austausch. Der `flush` bleibt
    hier, weil er den `409`-Fall traegt; sein `rollback` nimmt dann beide Schreibvorgaenge
    zurueck, und genau das ist die Zusage.

    `record=False` unterdrueckt die Aufzeichnung: Der Austausch ruft zweimal hierher und legt
    danach EIN `exchanged`-Ereignis ab. Ohne die Unterdrueckung zaehlte jeder Austausch
    dreifach."""
    rating = await _get_own_rating(session, photo.id, user_id)
    current = (None, False) if rating is None else (rating.status, rating.favorite)
    new_status, new_favorite = next_state(*current)
    kind = album_decision_kind(current[0], new_status) if record else None

    if new_status is None and not new_favorite:
        if rating is not None:
            await session.delete(rating)
        # VOR dem `return`: Dieser Zweig kehrt frueher zurueck als der gewoehnliche, und
        # ausgerechnet die Ruecknahme ist der Handgriff, den der Bestand danach nicht mehr zeigt.
        if kind is not None:
            await record_album_decision(
                session,
                photo=photo,
                user_id=user_id,
                kind=kind,
                context=await load_frozen_context(session, photo),
            )
        return RatingWriteOut(
            photo_id=photo.id, user_id=user_id, status=None, favorite=False, updated_at=None
        )

    if rating is None:
        rating = Rating(
            photo_id=photo.id, user_id=user_id, status=new_status, favorite=new_favorite
        )
        session.add(rating)
    else:
        rating.status = new_status
        rating.favorite = new_favorite

    # SICHERHEIT (S9): der `flush` bringt `uq_rating_photo_user` hier zum Tragen. Drei Endpunkte
    # schreiben auf dieselbe Zeile, und die Oberflaeche loest zwei davon aus derselben
    # Tastenbelegung aus; ohne diese Behandlung waere ein alltaeglicher Doppelklick eine `500`
    # statt einer `409`.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Die Bewertung dieses Fotos wurde gerade veraendert. Bitte erneut versuchen.",
        ) from exc
    await session.refresh(rating)
    if kind is not None:
        await record_album_decision(
            session,
            photo=photo,
            user_id=user_id,
            kind=kind,
            context=await load_frozen_context(session, photo),
        )
    return RatingWriteOut(
        photo_id=photo.id,
        user_id=user_id,
        status=rating.status,
        favorite=rating.favorite,
        updated_at=rating.updated_at,
    )


@router.put("/photos/{photo_id}/rating", response_model=RatingWriteOut)
async def set_rating(
    photo_id: int,
    payload: RatingUpdate,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency, siehe Router-Kommentar oben.
    current_user: User = Depends(get_current_user),
) -> RatingWriteOut:
    """Setzt die ALBUMENTSCHEIDUNG dieses Nutzers: gehoert das Bild ins Album (`album_worthy`)
    oder nicht (`rejected`).

    Sie ist KEINE Aussage ueber die Bildguete - ein bewusst aufgenommener schlechter
    Schnappschuss und ein gestrichenes gutes Bild sind gewollte, widerspruchsfreie Zustaende.

    `favorite` bleibt UNBERUEHRT (Auflage S7)."""
    photo = await _get_photo_or_404(photo_id, session)

    written = await _write_own_rating(
        session,
        photo,
        current_user.id,
        lambda _status, favorite: (payload.status, favorite),
    )
    # Der EINE Commit dieses Endpunkts: Bewertungszeile und etwaiges Ereignis gehen gemeinsam
    # oder gar nicht (Auflage S5).
    await session.commit()
    return written


@router.delete("/photos/{photo_id}/rating", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rating(
    photo_id: int,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency, siehe Router-Kommentar oben.
    current_user: User = Depends(get_current_user),
) -> None:
    """Nimmt NUR die Albumentscheidung zurueck (`status = NULL`).

    Die Zeile BLEIBT stehen, solange `favorite` gesetzt ist; sonst wird sie geloescht. Eine
    pauschale Zeilenloeschung verloere die Auszeichnung mit der Ruecknahme der Albumentscheidung,
    ohne jede Meldung (Auflage S7). Idempotent: `204`, ob eine Zeile bestand oder nicht - und
    ohne bestehende Albumentscheidung entsteht dabei KEIN Ereignis, weil nichts zurueckgenommen
    wurde."""
    photo = await _get_photo_or_404(photo_id, session)

    await _write_own_rating(
        session,
        photo,
        current_user.id,
        lambda _status, favorite: (None, favorite),
    )
    await session.commit()


@router.put("/photos/{photo_id}/favorite", response_model=RatingWriteOut)
async def set_favorite(
    photo_id: int,
    payload: FavoriteUpdate,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency, siehe Router-Kommentar oben.
    current_user: User = Depends(get_current_user),
) -> RatingWriteOut:
    """Setzt oder entfernt die Auszeichnung als Favorit - eine eigene, von der Albumentscheidung
    UNABHAENGIGE Angabe (ADR 0098 Punkt 2). Sie wirkt nicht auf den Album-Entwurf.

    Legt die Zeile bei Bedarf an und loescht sie, wenn danach beides leer ist. `status` bleibt
    unberuehrt (Auflage S7).

    ES ENTSTEHT KEIN EREIGNIS DER NACHARBEIT: Der Favorit wirkt nicht auf den Album-Entwurf und
    ist damit keine Aussage ueber einen Modellfehler. Das faellt ohne Sonderfall daraus heraus,
    dass dieser Endpunkt `status` unberuehrt laesst (Spec 0432, L1)."""
    photo = await _get_photo_or_404(photo_id, session)

    written = await _write_own_rating(
        session,
        photo,
        current_user.id,
        lambda status_value, _favorite: (status_value, payload.favorite),
    )
    await session.commit()
    return written
