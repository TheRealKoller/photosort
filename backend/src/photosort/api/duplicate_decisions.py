"""Die drei Schreibwege der Duplikat-Vergleichsansicht - je Aufnahme, je Gruppe und der
Gruppenabschluss.

EIGENES MODUL UND EIGENER ROUTER, weil die geschriebene Entscheidung keinen Nutzer kennt: Wer sie
trifft, geht in keine Zeile ein (ADR 0104 Punkt 2). Sie gehoeren ausdruecklich nicht nach
`api/photos.py` - siehe die Sicherungen unten.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.api.photos import (
    MAX_QUERY_POSITION,
    DuplicateGroupOut,
    build_duplicate_group_out,
    empty_duplicate_group_out,
)
from photosort.duplicates import (
    has_open_suggestion,
    load_duplicate_links,
    member_ids_of,
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

# SICHERHEIT (S8): Der Torwaechter haengt am ROUTER. Alle Endpunkte tragen damit DREI Sicherungen
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
# alle Schreibwege mit derselben `DuplicateGroupOut` antworten wie der Lesepfad - und die traegt
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


async def _has_open_suggestion(session: AsyncSession, project_id: int, photo_id: int) -> bool:
    """Ob DIESES Foto DIESES Projekts einen offenen Vorschlag traegt (Spec 0525, Auflage S10).

    Die zweite Haelfte der erweiterten Vorbedingung des Einzelwegs - und die Stelle, an der die
    Projektbindung sitzt: Das Praedikat `has_open_suggestion()` traegt selbst keine
    Projektbedingung, sie kommt allein aus dem Join auf `Photo`. Die Bedingung wird pro FOTO
    beantwortet; ein Sammelweg entsteht daraus nicht."""
    treffer = await session.execute(
        select(Photo.id)
        .join(PhotoScore, PhotoScore.photo_id == Photo.id)
        .where(Photo.project_id == project_id, Photo.id == photo_id, has_open_suggestion())
    )
    return treffer.first() is not None


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

    SEIT SPEC 0525 IST DAS EINE ANGENOMMENE, ABER UNWIRKSAME HANDLUNG (Auflage S10). Die
    Vorbedingung heisst "hat eine Duplikat-Gruppe ODER einen offenen Vorschlag": Die
    Unschaerfe-Ablehnung ohne Gruppe darf entschieden werden, und `keep` bleibt dort wirkungslos -
    die Anzeige bietet es gar nicht erst an. Der Server weist es NICHT ab (Auflage S4 der Spec 0486
    gilt unveraendert): Eine solche Abweisung waere eine zweite Regel neben ADR 0104 Punkt 3 und
    liefe dem gruppenweiten Schreibweg entgegen.

    Eine entschiedene Aufnahme ist kein offener Vorschlag mehr: Sie verschwindet aus dem Filter
    `suggested`, aus der Vorschlagsanzeige am Foto und aus der Zaehlung des Ausschuss-Gates.

    Ein wiederholter Aufruf UEBERSCHREIBT; der Wechsel behalten -> Ausschuss -> behalten ist
    moeglich, und danach steht genau eine Zeile. ES GIBT KEIN `DELETE`: Eine Ruecknahme nach "noch
    nicht entschieden" kennt die Story nicht, aendern heisst den anderen Wert schreiben.

    Die Antwort ist dieselbe `DuplicateGroupOut` wie auf dem Lesepfad - der vollstaendige Stand der
    Gruppe, nicht ein Echo des Koerpers. Ohne Gruppe ist der Stand leer (AK6): Ein Aufruf, der eine
    Entscheidung getragen hat, darf nicht wie ein Fehlschlag aussehen.

    `404` fuer ein Foto, das WEDER in einer Duplikat-Gruppe liegt NOCH einen offenen Vorschlag
    traegt - das deckt das unbekannte Foto und das fremde Projekt mit ab (die drei sind nicht
    unterscheidbar; die Meldung nennt deshalb weiterhin nur die Gruppe und gibt nicht preis, welche
    der beiden Bedingungen gefehlt hat), `422` fuer eine Pfad-Id ausserhalb der Grenzen oder einen
    Koerper mit einem anderen Feld als `decision`, `409` bei einem gleichzeitigen Schreibversuch, der
    sich nicht aufloesen laesst - nie eine `500`."""
    project = await _project_or_404(project_id, session)
    # SICHERHEIT (S7): Die Projektbindung steht ausgeschrieben, hier ueber die bereits
    # projektbegrenzte Kantenliste. Ein Foto eines fremden Projekts loest sich nicht auf und wird
    # deshalb auch nicht geschrieben.
    links = await load_duplicate_links(session, project.id)
    representative_id = representative_of(photo_id, links)
    # SICHERHEIT (S10): Die zweite Haelfte der Vorbedingung ist ebenfalls projektgebunden und wird
    # pro FOTO beantwortet - ein Sammelweg entsteht daraus nicht.
    if representative_id is None and not await _has_open_suggestion(session, project.id, photo_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Keine Duplikat-Gruppe zu diesem Foto."
        )

    await _write(session, [photo_id], payload.decision)
    await session.commit()
    if representative_id is None:
        return empty_duplicate_group_out()
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


@router.post(
    "/projects/{project_id}/duplicate-groups/{photo_id}/confirm",
    response_model=DuplicateGroupOut,
)
async def confirm_duplicate_group(
    project_id: Annotated[int, Path(ge=1, le=MAX_QUERY_POSITION)],
    photo_id: Annotated[int, Path(ge=1, le=MAX_QUERY_POSITION)],
    session: AsyncSession = Depends(get_session),
    # Wie beim Einzelweg: ausschliesslich fuer die Antwort (S10).
    current_user: User = Depends(get_current_user),
) -> DuplicateGroupOut:
    """Schliesst EINE Duplikat-Gruppe ab: Jedes Mitglied mit offenem Vorschlag bekommt `discard`.

    Das ist der Abschluss des Ausschuss-Schritts, auf eine Gruppe begrenzt. Ein
    offener Vorschlag zeigt bereits "Ausschuss"; der angezeigte Zustand aendert sich nicht, er wird
    festgeschrieben - mit derselben Wirkung, die der spaetere Abschluss des Ausschuss-Schritts
    gehabt haette. Mitglieder mit Entscheidungszeile oder ohne Vorschlag bleiben ungeschrieben: Ihr
    angezeigter Zustand gilt schon ohne Zeile. Es entsteht kein Gruppenzustand "erledigt".

    SICHERHEIT (S1): Der Stern wird ZUERST aufgeloest; ohne Gruppe ist die Antwort `404`, bevor
    irgendetwas geschrieben wird - auch fuer ein Foto mit offenem Vorschlag. Die erweiterte
    Vorbedingung des Einzelwegs gilt hier nicht: `member_ids_of(None, ...)` liefert jedes Foto ohne
    `duplicate_of`, und ein Aufruf auf ein einzelnes unscharfes Foto schriebe sonst `discard` auf
    jede Unschaerfe-Ablehnung des Projekts - der projektweite Massenabschluss ohne dessen
    Bestaetigung.

    SICHERHEIT (S2): Projektbindung, Mitgliedschaft und `has_open_suggestion()` stehen als
    UND-Glieder in EINER Anweisung mit innerem Join auf `PhotoScore`. `has_open_suggestion` traegt
    keine eigene Projektbedingung und setzt den Join voraus; ohne ihn wuerde die Bedingung fuer
    jedes Mitglied wahr, sobald irgendein Foto der Instanz einen offenen Vorschlag traegt, und der
    Gewinner, der "Behalten" zeigt, verloere still seinen Platz in Bewertung und Album.

    SICHERHEIT (S3): Nur einfuegen, nur `discard`, eine Transaktion; der `flush` liegt vor dem
    `commit`, ein `IntegrityError` wird `409` mit vollstaendigem Rueckzug. KEIN `DELETE` und nie
    `_write`: Zwischen Auswahl und Schreiben kann der andere Nutzer eine `keep`-Zeile committen,
    und ein vorangestelltes `DELETE` ersetzte seine Handlung still durch `discard`. Ein zweiter
    Aufruf findet keine offene Aufnahme mehr und antwortet `200` mit derselben Gruppe.

    SICHERHEIT (S4): Weder Menge noch Wert kommen vom Aufrufer - der Endpunkt nimmt kein
    Eingabeschema entgegen, ein mitgeschickter Koerper wird nie gelesen. Eine Id-Liste waere ein
    Massen-Schreibweg auf beliebige Fotos, ein Wert ein Massen-`keep`.

    SICHERHEIT (S5): `gate_confirmed_at` bleibt unberuehrt. Der Zeitstempel oeffnet den
    Cloud-Teilschritt; ihn setzt allein der projektweite Abschluss, der auch die
    Unschaerfe-Ablehnungen ausserhalb jeder Gruppe uebernimmt.

    Antwort ist dieselbe `DuplicateGroupOut` wie auf dem Lesepfad. `404` fuer unbekanntes Projekt
    und fuer ein Foto ohne Gruppe (unbekannt, fremdes Projekt und "keine Gruppe" sind nicht
    unterscheidbar), `422` fuer eine Pfad-Id ausserhalb der Grenzen, `409` bei einem
    gleichzeitigen Schreibversuch - nie eine `500`."""
    project = await _project_or_404(project_id, session)
    links = await load_duplicate_links(session, project.id)
    representative_id = representative_of(photo_id, links)
    if representative_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Keine Duplikat-Gruppe zu diesem Foto."
        )

    offene_ids = list(
        (
            await session.execute(
                select(Photo.id)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(
                    Photo.project_id == project.id,
                    Photo.id.in_(member_ids_of(representative_id, links)),
                    has_open_suggestion(),
                )
            )
        ).scalars()
    )
    if offene_ids:
        session.add_all(
            [
                PhotoDuplicateDecision(photo_id=offen, decision=DuplicateDecision.DISCARD)
                for offen in offene_ids
            ]
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
        await session.commit()
    return await build_duplicate_group_out(session, project, photo_id, current_user.id)
