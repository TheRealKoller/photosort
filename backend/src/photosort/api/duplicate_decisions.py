"""Die beiden Schreibwege der Duplikat-Vergleichsansicht - je Aufnahme und je Gruppe.

EIGENES MODUL UND EIGENER ROUTER, weil die geschriebene Entscheidung keinen Nutzer kennt: Wer sie
trifft, geht in keine Zeile ein (ADR 0104 Punkt 2). Sie gehoeren ausdruecklich nicht nach
`api/photos.py` - siehe die Sicherungen unten.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.api.photos import (
    MAX_QUERY_POSITION,
    DuplicateGroupOut,
    build_duplicate_group_out,
)
from photosort.duplicates import load_duplicate_links, member_ids_of, representative_of
from photosort.models import DuplicateDecision, PhotoDuplicateDecision, Project, User

# SICHERHEIT (S8): Der Torwaechter haengt am ROUTER. Beide Endpunkte tragen damit DREI Sicherungen
# statt einer: die Router-Dependency hier, den Eintrag in
# `tests/test_auth_guard.py::_protected_router_operations()` und je einen eigenen, pfadbenannten
# 401-Fall in `tests/test_api_duplicate_decisions.py`. Laege einer von ihnen stattdessen in
# `photos.router`, griffe von den dreien nur der 401-Fall: Jener Router traegt keine
# `dependencies`-Liste und keinen Vollstaendigkeitstest, ein vergessener Torwaechter waere dort
# STILL OEFFENTLICH - ein unauthentifizierter Schreibzugriff, der bestimmt, welche Bilder den
# Homeserver verlassen. Die Router-Dependency gilt zudem fuer jeden kuenftigen Endpunkt dieses
# Routers, auch fuer einen, der den Nutzer nicht selbst braucht.
#
# ABWEICHUNG ZUM MUSTER `api/album_decisions.py`, benannt statt stillschweigend: Dort nimmt der
# Endpunkt KEIN `current_user` entgegen. Hier tut er es zusaetzlich zur Router-Dependency, weil
# beide Schreibwege mit derselben `DuplicateGroupOut` antworten wie der Lesepfad - und die traegt
# `PhotoOut` samt `suggestion`/`ratings`, die eine Funktion des ANFRAGENDEN Nutzers sind (S10).
# Ohne den Nutzer waere die Antwort entweder eine andere Form als der Lesepfad oder eine, die die
# Vorschlags- und Bewertungsanzeige einer fremden Person zeigt. Die ENTSCHEIDUNG selbst bleibt
# nutzerlos: Wer schreibt, geht in keine Zeile ein (ADR 0104 Punkt 2).
router = APIRouter(tags=["duplicates"], dependencies=[Depends(get_current_user)])


class DuplicateDecisionIn(BaseModel):
    """SICHERHEIT (S6): der Koerper traegt AUSSCHLIESSLICH `decision`, pflichtig und ohne `null`.

    Kein `photo_id`, kein `user_id`, KEINE Id-Liste - und `extra="forbid"`, damit eine
    mitgeschickte Menge nicht still ignoriert, sondern zurueckgewiesen wird. Welche Fotos die
    Gruppe umfasst, bestimmt der Server aus dem Stern; eine vom Aufrufer gelieferte Menge waere ein
    Massen-Schreibweg auf beliebige Fotos des Projekts.

    KEIN VORGABEWERT, aus demselben Grund, aus dem die Spalte keinen traegt: Die Abwesenheit der
    Zeile heisst "noch nicht entschieden". Ein aus Bequemlichkeit gesetzter Wert verlegte genau
    diese Entscheidung in die Auswertung einer fehlerhaften Anfrage - und es gibt keinen Weg
    zurueck nach "unentschieden", ein so entstandener Zustand ist nicht korrigierbar, nur
    ueberschreibbar."""

    model_config = ConfigDict(extra="forbid")

    decision: DuplicateDecision


async def _project_or_404(project_id: int, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


async def _write(session: AsyncSession, photo_ids: list[int], decision: DuplicateDecision) -> None:
    """Setzt die Entscheidung fuer genau diese Fotos - OHNE `commit`, die Transaktionsgrenze
    gehoert dem Endpunkt (S9).

    Loeschen und neu einfuegen statt Zeile-fuer-Zeile-Abgleich: Der Primaerschluessel ist
    `photo_id`, ein naives `INSERT` liefe bei einer bestehenden Zeile in einen `IntegrityError`
    und damit in eine 500 auf einem alltaeglichen zweiten Druck. Beide Anweisungen liegen in
    DERSELBEN Transaktion; ein Zwischenzustand ohne Zeile ist von aussen nie beobachtbar.

    SICHERHEIT (S9), zweite Haelfte: Das deckt den WIEDERHOLTEN Druck ab, nicht den
    NEBENLAEUFIGEN. Committet die andere Sitzung zwischen unserem `DELETE` und unserem `INSERT`,
    trifft das `INSERT` eine Zeile, die es beim `DELETE` noch nicht gab - und der
    Primaerschluessel wirft. Der `flush` VOR dem `commit` des Endpunkts holt diesen Fehler an eine
    Stelle, an der er sich in `409` uebersetzen laesst; ohne ihn faende ihn erst der `commit`, und
    der Aufrufer bekaeme eine `500` auf einen alltaeglichen Doppeldruck zu zweit.

    Bewusst getragen bleibt "der letzte Schreibende gewinnt": Es gibt keine
    Optimistic-Locking-Pruefung, und im Regelfall - die andere Sitzung committet VOR unserem
    `DELETE` - raeumt dieses die fremde Zeile weg und der zweite Schreibende setzt sich durch. Der
    `409` gilt allein fuer das schmale Fenster dazwischen, und die Wiederholung loest ihn auf."""
    await session.execute(
        delete(PhotoDuplicateDecision).where(PhotoDuplicateDecision.photo_id.in_(photo_ids))
    )
    session.add_all(
        [PhotoDuplicateDecision(photo_id=photo_id, decision=decision) for photo_id in photo_ids]
    )
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Die Entscheidung zu dieser Duplikat-Gruppe wurde gerade veraendert. "
                "Bitte erneut versuchen."
            ),
        ) from None


@router.put(
    "/projects/{project_id}/photos/{photo_id}/duplicate-decision",
    response_model=DuplicateGroupOut,
)
async def set_duplicate_decision(
    project_id: Annotated[int, Path(ge=1, le=MAX_QUERY_POSITION)],
    photo_id: Annotated[int, Path(ge=1, le=MAX_QUERY_POSITION)],
    payload: DuplicateDecisionIn,
    session: AsyncSession = Depends(get_session),
    # Ausschliesslich fuer die ANTWORT (S10) - siehe den Kopfkommentar dieser Datei. In die
    # geschriebene Zeile geht der Nutzer nicht ein.
    current_user: User = Depends(get_current_user),
) -> DuplicateGroupOut:
    """Entscheidet ueber EINE Aufnahme des Ausschusses: bleibt sie, oder geht sie.

    Sie ist KEINE Albumentscheidung. Dieser Weg schreibt ausdruecklich KEINE `Rating`-Zeile und
    KEIN Nacharbeits-Ereignis (ADR 0104 Punkt 2): Die Nacharbeit misst Korrekturen am Album, nicht
    am Ausschuss, und ueber `write_own_rating` geschrieben zoege jedes "behalten" das Foto zugleich
    in den Album-Entwurf des Anfragenden - eine Aussage, die niemand getroffen hat.

    DIE WIRKUNG IST ASYMMETRISCH. `discard` wirkt unbedingt: Die Aufnahme ueberlebt den
    Ausschuss-Schritt nie, auch wenn gar kein Vorschlag vorlag. `behalten` wirkt nur, SOLANGE die
    Aufnahme Duplikat-Verlierer ist - es uebersteuert die Duplikatablehnung und ausdruecklich keine
    Ablehnung aus einem anderen Grund. Eine wegen Unschaerfe abgelehnte Aufnahme bleibt abgelehnt.

    Eine entschiedene Aufnahme ist kein offener Vorschlag mehr: Sie verschwindet aus dem Filter
    `suggested`, aus der Vorschlagsanzeige am Foto und aus der Zaehlung des Ausschuss-Gates.

    Ein wiederholter Aufruf UEBERSCHREIBT; der Wechsel behalten -> Ausschuss -> behalten ist
    moeglich, und danach steht genau eine Zeile. ES GIBT KEIN `DELETE`: Eine Ruecknahme nach "noch
    nicht entschieden" kennt die Story nicht, aendern heisst den anderen Wert schreiben.

    Die Antwort ist dieselbe `DuplicateGroupOut` wie auf dem Lesepfad - der vollstaendige Stand der
    Gruppe, nicht ein Echo des Koerpers.

    `404` fuer ein Foto ohne Duplikat-Gruppe, ein unbekanntes Foto oder eines aus einem fremden
    Projekt (die drei sind nicht unterscheidbar), `422` fuer eine Pfad-Id ausserhalb der Grenzen
    oder einen Koerper mit einem anderen Feld als `decision`, `409` bei einem gleichzeitigen
    Schreibversuch, der sich nicht aufloesen laesst - nie eine `500`."""
    project = await _project_or_404(project_id, session)
    # SICHERHEIT (S7): Die Projektbindung steht ausgeschrieben, hier ueber die bereits
    # projektbegrenzte Kantenliste. Ein Foto eines fremden Projekts loest sich nicht auf und wird
    # deshalb auch nicht geschrieben.
    links = await load_duplicate_links(session, project.id)
    if representative_of(photo_id, links) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Keine Duplikat-Gruppe zu diesem Foto."
        )

    await _write(session, [photo_id], payload.decision)
    await session.commit()
    return await build_duplicate_group_out(session, project, photo_id, current_user.id)


@router.put(
    "/projects/{project_id}/duplicate-groups/{photo_id}/decision",
    response_model=DuplicateGroupOut,
)
async def set_duplicate_group_decision(
    project_id: Annotated[int, Path(ge=1, le=MAX_QUERY_POSITION)],
    photo_id: Annotated[int, Path(ge=1, le=MAX_QUERY_POSITION)],
    payload: DuplicateDecisionIn,
    session: AsyncSession = Depends(get_session),
    # Wie beim Einzelweg: ausschliesslich fuer die Antwort (S10).
    current_user: User = Depends(get_current_user),
) -> DuplicateGroupOut:
    """Entscheidet ueber ALLE Aufnahmen einer Duplikat-Gruppe in EINEM Aufruf.

    DIE MENGE BESTIMMT DER SERVER aus dem Stern; der Koerper traegt ausschliesslich die
    Entscheidung. Eine vom Aufrufer gelieferte Id-Liste waere ein Massen-Schreibweg auf beliebige
    Fotos des Projekts und wird deshalb nicht bloss ignoriert, sondern zurueckgewiesen.

    Danach traegt jedes Mitglied denselben Zustand, auch jene, die vorher einzeln anders
    entschieden waren; ein anschliessender Einzelaufruf uebersteuert nur dieses eine Mitglied.

    SICHERHEIT (S5): Der Repraesentant wird ZUERST aufgeloest; gibt es keine Gruppe, ist die
    Antwort `404`, BEVOR geschrieben wird. Ein `None` als Vergleichswert des Gruppenpraedikats wird
    in SQLAlchemy zu `duplicate_of IS NULL` und traefe damit jede nicht aussortierte Aufnahme des
    Projekts: Ein Klick schriebe `discard` oder `keep` auf den gesamten Bestand - im einen Fall
    verschwindet das Projekt aus Bewertung und Album, im anderen geht es vollstaendig an den
    Cloud-Anbieter. Die Gruppengroesse ist die Verstaerkung dieses einen Schreibwegs und der Grund,
    warum er schaerfer ist als der einzelne.

    SICHERHEIT (S9): EINE Transaktion, ein `commit` ueber alle Zeilen. Eine halb entschiedene
    Gruppe waere eine willkuerliche Teilmenge im abfliessenden Bestand, ohne dass ein Lesepfad den
    Zwischenzustand als solchen erkennt. Ein gleichzeitiger Schreibzugriff beider Nutzer auf
    dieselbe Aufnahme wird `409`, nie `500` - und weil die Transaktion die GANZE Gruppe umfasst,
    bleibt dann keine einzige ihrer Zeilen geschrieben.

    Antwortform und Fehlercodes wie beim Einzelweg."""
    project = await _project_or_404(project_id, session)
    links = await load_duplicate_links(session, project.id)
    representative_id = representative_of(photo_id, links)
    if representative_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Keine Duplikat-Gruppe zu diesem Foto."
        )

    await _write(session, member_ids_of(representative_id, links), payload.decision)
    await session.commit()
    return await build_duplicate_group_out(session, project, photo_id, current_user.id)
