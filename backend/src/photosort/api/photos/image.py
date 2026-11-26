"""Das einzelne Foto: die Bilddatei und die Motiv-Korrektur."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import CursorResult, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.config import settings
from photosort.feedback_log import load_frozen_context, record_motif_correction
from photosort.models import (
    FeedbackEventKind,
    Photo,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    User,
)
from photosort.motifs import is_motif_key
from photosort.thumbnails import variant_path

router = APIRouter()


@router.get("/photos/{photo_id}/image")
async def get_photo_image(
    photo_id: int,
    # Literal["thumbnail", "display"] statt ein freier str-Parameter: FastAPI/Pydantic validiert
    # gegen genau diese Allowlist und liefert 422 fuer alles andere, BEVOR der Wert unten in eine
    # Datei-Pfadoperation einfließt - Muss-Kriterium gegen Path-Traversal über den
    # variant-Parameter.
    variant: Literal["thumbnail", "display"],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")

    path = variant_path(Path(settings.photo_cache_dir), photo.id, photo.etag, variant)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bild wird noch verarbeitet."
        )

    # SICHERHEIT: Content-Type explizit gesetzt (immer JPEG, siehe thumbnails.py), nicht vom
    # Dateisystem erraten; X-Content-Type-Options verhindert MIME-Sniffing-XSS bei falsch
    # benannten Dateien.
    return FileResponse(
        path, media_type="image/jpeg", headers={"X-Content-Type-Options": "nosniff"}
    )


async def _get_photo_or_404(photo_id: int, session: AsyncSession) -> Photo:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


class MotifCorrectionIn(BaseModel):
    """SICHERHEIT: der Body traegt AUSSCHLIESSLICH `applies`.

    Kein `user_id`, `photo_id`, `motif_key`, `strength` oder `updated_at` im Eingabeschema -
    Massenzuweisung ist strukturell ausgeschlossen statt im Handler herausgefiltert. Ein Feld,
    ueber das ein Client eine Staerke setzen koennte, hebt die Unterscheidung zwischen
    Modellaussage und Korrektur auf, und ein `user_id` im Body liesse Nutzer A unter dem Namen von
    B schreiben. Ein spaeter ergaenztes Feld bricht in
    tests/test_api_motif_corrections.py::TestTheRequestBody."""

    applies: bool


class MotifCorrectionOut(BaseModel):
    photo_id: int
    motif_key: str
    applies: bool


async def _stored_motif_strength(
    session: AsyncSession, photo_id: int, motif_key: str
) -> float | None:
    """Die GESPEICHERTE Modellstaerke dieses Paares, `None` ohne Staerkezeile.

    AUSDRUECKLICH NICHT `motif_strengths.py::effective_strength_expression`:
    Die wirksame Staerke traegt bereits eine fruehere Korrektur desselben Paares. Eingefroren
    zeigte die ZWEITE Korrektur eines Motivs nie einen Modellfehler an - sie beantwortete die
    Frage nach der Modellaussage mit der Korrektur.

    `None` ist ein gewoehnlicher, haeufiger Fall und kein Fehler: Die Korrektur eines nie
    erkannten Motivs ist ausdruecklich erlaubt und fuer die Diagnose der interessanteste Fall."""
    return (
        await session.execute(
            select(PhotoMotifStrength.strength).where(
                PhotoMotifStrength.photo_id == photo_id,
                PhotoMotifStrength.motif_key == motif_key,
            )
        )
    ).scalar_one_or_none()


def _validated_motif_key(motif_key: str) -> str:
    """SICHERHEIT: reine Mitgliedschaftspruefung im geschlossenen Achter-Schluesselraum, VOR
    jeder Schreib- und Loeschaktion, fuer `PUT` UND `DELETE`.

    Kein `startswith`, kein Regex, keine Normalisierung des Eingabewerts - der Client schickt den
    Schluessel exakt so zurueck, wie `GET /motifs` ihn geliefert hat. `EXCLUSION_KEY` ist kein
    gueltiger Wert und kann ueber diese Pruefung nicht hereinkommen: `is_motif_key` sieht
    ausschliesslich in `MOTIF_REGISTRY`, und dort steht er nicht.

    Angriffsmodell: ein erratener oder aus der Laufhistorie bekannter Schluessel. Untersagte
    Alternative ist eine auf die vorhandenen Staerkezeilen DIESES Fotos skopierte Existenzpruefung
    - sie haengt an Daten statt am Vokabular und wiese das Korrigieren eines nie erkannten Motivs
    zu Unrecht ab."""
    if not is_motif_key(motif_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="motif_key gehoert nicht zum festen Motivset.",
        )
    return motif_key


@router.put("/photos/{photo_id}/motif-corrections/{motif_key}", response_model=MotifCorrectionOut)
async def set_motif_correction(
    photo_id: int,
    motif_key: str,
    payload: MotifCorrectionIn,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT: ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # Router-weite `dependencies`-Liste und hat deshalb auch keinen Vollstaendigkeitstest - ein
    # hier vergessener Parameter waere STILL OEFFENTLICH: kein Fehler, keine 401, nur Daten.
    current_user: User = Depends(get_current_user),
) -> MotifCorrectionOut:
    """Markiert ein Motiv fuer dieses Foto als zutreffend oder als nicht zutreffend: `404` bei
    fehlendem Foto, `422` bei einem `motif_key` ausserhalb des festen Achter-Sets (auch fuer
    `dokument_screenshot` und fuer einen entfallenen Kategorieschluessel), `409` bei einem
    gleichzeitigen Schreibversuch auf dasselbe Paar.

    Die Korrektur traegt nie eine Zahl - der Nutzer schaetzt nichts ein, er waehlt ein Motiv ab
    oder zu. Die WIRKSAME Staerke entsteht erst im Lesepfad und wird nicht in die Staerkezeile
    materialisiert; sie ueberlebt damit jeden weiteren Klassifizierungslauf ohne Sonderfallcode.

    AUSDRUECKLICH ERLAUBT ist ein Motiv, das fuer dieses Foto nie erkannt wurde, und ein Foto ohne
    Kopfzeile: die Tabelle ist lauf-unabhaengig, und die Korrektur greift dann beim ersten Lauf.

    Eine Korrektur je Foto und Motiv, letzter Zugriff gewinnt: korrigiert der zweite Nutzer
    dasselbe Paar, UEBERSCHREIBT er die Aussage des ersten. `user_id` haelt fest, wer zuletzt
    geschrieben hat - es gibt keine Historie und keinen Hinweis an die erste Person. Eine
    wirkungslose Korrektur (`applies=false` auf einem Motiv, dessen Staerke schon 0 ist) wird
    trotzdem gespeichert; sie ist eine Nutzeraussage, keine Zwischenspeicherung."""
    # Die `project_id` VOR dem `flush` festhalten: Dessen `rollback`-Zweig laesst jedes geladene
    # Objekt expired zurueck, und ein danach angefasstes Attribut braeche unter `asyncio` mit
    # `MissingGreenlet`.
    project_id = (await _get_photo_or_404(photo_id, session)).project_id
    _validated_motif_key(motif_key)

    # SICHERHEIT: die Aufsuch-Bedingung lautet `(photo_id, motif_key)` und filtert BEWUSST
    # NICHT zusaetzlich auf `user_id`. Mit dem Nutzer im Filter entstuenden zwei widersprueckliche
    # Zeilen fuer dasselbe Paar, und welche gilt, entschiede die Sortierung.
    existing = (
        await session.execute(
            select(PhotoMotifCorrection).where(
                PhotoMotifCorrection.photo_id == photo_id,
                PhotoMotifCorrection.motif_key == motif_key,
            )
        )
    ).scalar_one_or_none()

    # NUR BEI TATSAECHLICHER AENDERUNG: Dieselbe Korrektur erneut geschrieben ist
    # keine Korrektur - auch dann nicht, wenn die Zeile dabei den Nutzer wechselt. Der
    # Bestandszustand des FOTOS bewegt sich nicht, und gemessen werden Korrekturen.
    changed = existing is None or existing.applies != payload.applies

    if existing is None:
        # SICHERHEIT: `user_id` stammt AUSSCHLIESSLICH aus `current_user.id` - nie aus Body
        # oder Query. Es ist ein Auditfeld und kein Zugriffsschluessel.
        session.add(
            PhotoMotifCorrection(
                photo_id=photo_id,
                user_id=current_user.id,
                motif_key=motif_key,
                applies=payload.applies,
            )
        )
    else:
        existing.applies = payload.applies
        existing.user_id = current_user.id
        # `updated_at` traegt `onupdate=func.now()` und wird nie von Hand gesetzt.

    # SICHERHEIT: der `flush` VOR dem `commit` bringt den Unique-Constraint hier zum Tragen,
    # damit ein gleichzeitiger Schreibversuch beider Nutzer als `409` herauskommt und nie als
    # `500`. Eine Sperre (`with_for_update()`) ist nicht noetig und ausdruecklich nicht
    # vorzusehen: die Korrektur schreibt eine Zeile und leitet nichts ab, sie hat keinen
    # Schreibzugriff auf die Rangfolge.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Die Korrektur dieses Motivs wurde gerade veraendert. Bitte erneut versuchen.",
        ) from exc

    if changed:
        await record_motif_correction(
            session,
            project_id=project_id,
            photo_id=photo_id,
            user_id=current_user.id,
            kind=(
                FeedbackEventKind.MOTIF_ADDED
                if payload.applies
                else FeedbackEventKind.MOTIF_DROPPED
            ),
            motif_key=motif_key,
            motif_strength=await _stored_motif_strength(session, photo_id, motif_key),
            context=await load_frozen_context(session, project_id=project_id, photo_id=photo_id),
        )
    # Der EINE Commit: Korrekturzeile und etwaiges Ereignis gehen gemeinsam oder gar nicht.
    await session.commit()

    return MotifCorrectionOut(photo_id=photo_id, motif_key=motif_key, applies=payload.applies)


@router.delete(
    "/photos/{photo_id}/motif-corrections/{motif_key}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_motif_correction(
    photo_id: int,
    motif_key: str,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT: siehe set_motif_correction - der 401-Nachweis ist fuer BEIDE Endpunkte
    # Pflicht, weil dieser Router keinen Vollstaendigkeitstest hat.
    current_user: User = Depends(get_current_user),
) -> None:
    """Nimmt die Korrektur eines Motivs zurueck - die wirksame Staerke ist danach wieder die der
    Grundlage. `404` bei fehlendem Foto, `422` bei einem `motif_key` ausserhalb des festen Sets.

    IDEMPOTENT (`204` auch ohne bestehende Zeile) und ohne Body. Auch die jeweils andere Person
    darf eine Korrektur zuruecknehmen: die Aussage gehoert zum Foto, nicht zu einem Geschmack.

    Ein Aufruf auf ein NIE korrigiertes Motiv erzeugt kein Ereignis der Nacharbeit: Er nimmt
    nichts zurueck. Die Ruecknahme einer bestehenden Korrektur dagegen erzeugt ein
    ZUSAETZLICHES Ereignis - das urspruengliche bleibt unveraendert stehen."""
    project_id = (await _get_photo_or_404(photo_id, session)).project_id
    _validated_motif_key(motif_key)

    # Die Staerke VOR der Loeschung lesen - danach ist die Korrekturzeile fort, und die
    # eingefrorene Modellaussage steht in einer anderen Tabelle, die den Zeitpunkt nicht kennt.
    motif_strength = await _stored_motif_strength(session, photo_id, motif_key)
    deleted = await session.execute(
        delete(PhotoMotifCorrection).where(
            PhotoMotifCorrection.photo_id == photo_id,
            PhotoMotifCorrection.motif_key == motif_key,
        )
    )
    if cast("CursorResult[Any]", deleted).rowcount:
        await record_motif_correction(
            session,
            project_id=project_id,
            photo_id=photo_id,
            user_id=current_user.id,
            kind=FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN,
            motif_key=motif_key,
            motif_strength=motif_strength,
            context=await load_frozen_context(session, project_id=project_id, photo_id=photo_id),
        )
    await session.commit()
