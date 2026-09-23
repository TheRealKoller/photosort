"""`GET /projects/{project_id}/ausschuss` - der Lesepfad des Ausschuss-Schritts (Spec 0525).

Der Endpunkt traegt die UEBERSICHT: den projektweiten Bestand des Ausschusses (offener Vorschlag
ODER Entscheidungszeile, also offen, angenommen und aufgehoben zusammen) mit seinem Grund und dem
gespeicherten Entscheidungswert, dazu den Einstieg in die Detailansicht (`photo_id`-Filter).

ZWEI GROESSEN, DIE NICHT DASSELBE SIND und hier getrennt geprueft werden: `total` ist die Groesse
des GESAMTBESTANDS (paginierbar), `open_count` ist die projektweite Zahl der OFFENEN Vorschlaege -
unabhaengig von `limit`/`offset`. Der Bestaetigungsbutton nennt die zweite.

SICHERHEIT (S6): Der Bestand ist projektgebunden, auch der Gruppenanker. `PhotoScore.duplicate_of`
zeigt auf `photos.id` OHNE Projektbedingung; eine Aufnahme eines fremden Projekts darf weder als
Eintrag noch als Anker erscheinen.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.photos import MAX_QUERY_POSITION
from photosort.models import (
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)

_BASE = datetime(2023, 5, 1, 12, 0, 0, tzinfo=UTC)


async def _project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=f"/{name}")
    session.add(project)
    await session.flush()
    return project


async def _photo(
    session: AsyncSession,
    project: Project,
    path: str,
    *,
    seconds: int = 0,
    with_score: bool = True,
    suggested_status: RatingStatus | None = None,
    duplicate_of: int | None = None,
    decision: DuplicateDecision | None = None,
) -> Photo:
    moment = _BASE + timedelta(seconds=seconds)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=1,
        taken_at=moment,
        taken_at_original=moment,
        last_modified=moment,
    )
    session.add(photo)
    await session.flush()
    if with_score:
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=100.0,
                exposure=0.0,
                suggested_status=suggested_status,
                duplicate_of=duplicate_of,
                computed_at=moment,
            )
        )
    if decision is not None:
        session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=decision))
    await session.flush()
    return photo


async def _successful_run(session: AsyncSession, project: Project) -> ScoringRun:
    run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS, started_at=_BASE)
    session.add(run)
    await session.flush()
    return run


def _url(project_id: int, **params: int) -> str:
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"/projects/{project_id}/ausschuss" + (f"?{query}" if query else "")


def _ids(body: dict[str, object]) -> list[int]:
    items = body["items"]
    assert isinstance(items, list)
    return [entry["photo"]["id"] for entry in items]


def _entry(body: dict[str, object], photo_id: int) -> dict[str, object]:
    items = body["items"]
    assert isinstance(items, list)
    treffer = [entry for entry in items if entry["photo"]["id"] == photo_id]
    assert len(treffer) == 1, "Der Eintrag fehlt oder steht doppelt in der Antwort."
    return treffer[0]


# ------------------------------------------------------------------------------------------
# Auth und Eingabegrenzen (Auflage S5)
# ------------------------------------------------------------------------------------------


async def test_the_overview_requires_a_token(api_client: httpx.AsyncClient) -> None:
    """EIGENER, PFADBENANNTER 401-FALL. `photos.router` traegt bewusst keine router-weite
    `dependencies`-Liste und keinen Vollstaendigkeitstest - ein vergessener `current_user`-Parameter
    waere dort STILL OEFFENTLICH: keine 401, nur Daten."""
    response = await api_client.get(_url(1))

    assert response.status_code == 401


async def test_the_401_stands_before_any_statement_about_the_project(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die 401 steht VOR jeder Aussage ueber das Projekt: Ein unbekanntes Projekt ist ohne Token von
    einem bekannten nicht zu unterscheiden."""
    project = await _project(db_session)

    bekannt = await api_client.get(_url(project.id))
    unbekannt = await api_client.get(_url(999_999))

    assert bekannt.status_code == unbekannt.status_code == 401
    assert bekannt.json() == unbekannt.json()


@pytest.mark.parametrize("project_id", [0, -1, MAX_QUERY_POSITION + 1])
async def test_a_project_id_outside_the_declared_bounds_is_a_422(
    authenticated_api_client: httpx.AsyncClient, project_id: int
) -> None:
    """SICHERHEIT (S5): Ein unbeschraenkter Pydantic-`int` erreicht die Datenbank und wird jenseits
    von 2^63 zu `500` statt `404`."""
    response = await authenticated_api_client.get(_url(project_id))

    assert response.status_code == 422


@pytest.mark.parametrize("photo_id", [0, -1, MAX_QUERY_POSITION + 1])
async def test_a_photo_id_outside_the_declared_bounds_is_a_422(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, photo_id: int
) -> None:
    project = await _project(db_session)

    response = await authenticated_api_client.get(_url(project.id, photo_id=photo_id))

    assert response.status_code == 422


async def test_an_unknown_project_is_a_404_that_does_not_mirror_the_value(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get(_url(999_999))

    assert response.status_code == 404
    assert "999999" not in response.text


# ------------------------------------------------------------------------------------------
# Der Bestand: zwei Ursachen, mit dem Fall in der Schnittmenge (AK1, AK3, AK4)
# ------------------------------------------------------------------------------------------


async def test_the_stock_is_the_union_of_open_suggestion_and_decision_row(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """DIE Zusage des Bestands, ueber die Wahrheitstabelle beider Ursachen (Muster (1)).

    Vier Faelle, und der Fall in der SCHNITTMENGE ist der tragende: Ein Test je Ursache bestuende
    auch gegen eine Umsetzung, die nur eine der beiden liest - hier steht ein Foto, das BEIDE
    traegt, neben einem, das NUR die Entscheidungszeile traegt, und neben einem, das NUR den
    offenen Vorschlag traegt. Das vierte traegt weder noch und fehlt.
    """
    project = await _project(db_session)
    nur_offen = await _photo(
        db_session, project, "nur-offen.jpg", seconds=0, suggested_status=RatingStatus.REJECTED
    )
    schnittmenge = await _photo(
        db_session,
        project,
        "schnittmenge.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        decision=DuplicateDecision.DISCARD,
    )
    nur_entschieden = await _photo(
        db_session, project, "nur-entschieden.jpg", seconds=2, decision=DuplicateDecision.KEEP
    )
    await _photo(db_session, project, "ohne-alles.jpg", seconds=3)
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert set(_ids(body)) == {nur_offen.id, schnittmenge.id, nur_entschieden.id}
    assert body["total"] == 3


async def test_a_photo_without_a_score_is_never_an_entry(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT: Der innere Join auf `PhotoScore` bleibt ein innerer Join. Ein Foto ohne
    Bewertungsgrundlage traegt weder Vorschlag noch Grund und gehoert nicht in den Bestand - ein
    outer Join zoege es hinein."""
    project = await _project(db_session)
    foto = await _photo(db_session, project, "ohne-score.jpg", with_score=False)
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert body == {"items": [], "total": 0, "open_count": 0}
    assert foto.id not in _ids(body)


async def test_the_stock_of_another_project_never_shows_up(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S6): `has_open_suggestion` traegt selbst KEINE Projektbedingung - sie kommt
    allein aus dem umgebenden Join auf `Photo`. Ohne ihn liefert die Uebersicht jeden offenen
    Vorschlag der ganzen Instanz aus."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    eigene = await _photo(db_session, home, "eigene.jpg", suggested_status=RatingStatus.REJECTED)
    fremde = await _photo(db_session, other, "fremde.jpg", suggested_status=RatingStatus.REJECTED)
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(home.id))).json()

    assert _ids(body) == [eigene.id]
    assert body["total"] == 1
    assert fremde.id not in _ids(body)


# ------------------------------------------------------------------------------------------
# Grund, Entscheidung, Anker (AK4, AK6, AK8)
# ------------------------------------------------------------------------------------------


async def test_the_reason_matches_the_suggestion_reason_of_the_score(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK4: `reason` ist eine ZWEITE Fassung derselben Ableitung - `duplicate` genau dann, wenn
    `duplicate_of IS NOT NULL`, sonst `low_quality`. Beide Gruende stehen nebeneinander, damit eine
    Umsetzung auffaellt, die alle Eintraege gleich kennzeichnet."""
    project = await _project(db_session)
    gewinner = await _photo(db_session, project, "gewinner.jpg", seconds=0)
    duplikat = await _photo(
        db_session,
        project,
        "duplikat.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=gewinner.id,
    )
    unscharf = await _photo(
        db_session,
        project,
        "unscharf.jpg",
        seconds=2,
        suggested_status=RatingStatus.REJECTED,
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert _entry(body, duplikat.id)["reason"] == "duplicate"
    assert _entry(body, unscharf.id)["reason"] == "low_quality"


async def test_the_decision_is_the_stored_row_and_not_the_effective_state(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK6/AK10: `decision` ist der GESPEICHERTE Zeilenwert, ausdruecklich nicht
    `effective_decision_for`. Ein unwirksames `keep` (Unschaerfe-Ablehnung ohne Gruppe) bleibt als
    gespeicherte Handlung sichtbar - genau das unterscheidet die Uebersicht von der
    Vergleichsansicht (ADR 0111 Punkt 1)."""
    project = await _project(db_session)
    offen = await _photo(
        db_session, project, "offen.jpg", seconds=0, suggested_status=RatingStatus.REJECTED
    )
    unwirksam_behalten = await _photo(
        db_session,
        project,
        "unwirksam.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        decision=DuplicateDecision.KEEP,
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert _entry(body, offen.id)["decision"] is None
    assert _entry(body, unwirksam_behalten.id)["decision"] == "keep"


async def test_a_foreign_rating_of_the_requester_never_changes_the_decision(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`decision` ist eine PROJEKTAUSSAGE. Eine eigene Albumbewertung des Anfragenden aendert den
    gespeicherten Wert nicht - waere er aus `effective_decision_for` oder aus `PhotoOut.suggestion`
    gebildet, kippte er hier."""
    project = await _project(db_session)
    foto = await _photo(
        db_session,
        project,
        "foto.jpg",
        suggested_status=RatingStatus.REJECTED,
        decision=DuplicateDecision.DISCARD,
    )
    user = (await db_session.execute(select(User).where(User.username == "testuser"))).scalar_one()
    db_session.add(Rating(photo_id=foto.id, user_id=user.id, status=RatingStatus.ALBUM_WORTHY))
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert _entry(body, foto.id)["decision"] == "discard"


async def test_the_group_anchor_names_the_representative_of_the_duplicate_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK8: Ist ein Bild wegen eines Duplikats im Ausschuss, zeigt die Detailansicht seine Gruppe.
    Der Anker ist die Repraesentanten-Id - dieselbe, unter der die Gruppenantwort erreichbar ist."""
    project = await _project(db_session)
    gewinner = await _photo(db_session, project, "gewinner.jpg", seconds=0)
    verlierer = await _photo(
        db_session,
        project,
        "verlierer.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=gewinner.id,
    )
    unscharf = await _photo(
        db_session, project, "unscharf.jpg", seconds=2, suggested_status=RatingStatus.REJECTED
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()
    gruppe = (
        await authenticated_api_client.get(
            f"/projects/{project.id}/duplicate-groups/{verlierer.id}"
        )
    ).json()

    assert _entry(body, verlierer.id)["group_anchor_photo_id"] == gewinner.id
    assert gruppe["items"][0]["photo"]["id"] == gewinner.id
    assert _entry(body, unscharf.id)["group_anchor_photo_id"] is None


async def test_a_vanished_group_leaves_the_entry_with_a_null_anchor(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK8, dritter Fall: Die Gruppe kann zwischen zwei Laeufen verschwinden. Die
    Entscheidungszeile bleibt, der Bestand bleibt - aber es gibt keinen Anker mehr. Eine
    Umsetzung, die den Anker aus der eigenen Zeile bildet statt aus der Gruppenaufloesung, nennte
    hier eine Id, zu der die Detailansicht `404` antwortet."""
    project = await _project(db_session)
    ehemaliger_verlierer = await _photo(
        db_session,
        project,
        "ehemals.jpg",
        seconds=0,
        suggested_status=RatingStatus.REJECTED,
        decision=DuplicateDecision.DISCARD,
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert _entry(body, ehemaliger_verlierer.id)["group_anchor_photo_id"] is None


async def test_a_group_of_another_project_is_never_named_as_the_anchor(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S6): `duplicate_of` zeigt auf `photos.id` ohne Projektbedingung. Zeigt ein
    eigener Verlierer auf den Gewinner eines FREMDEN Projekts, bleibt der Anker leer - er stammt aus
    der projektbegrenzten Kantenliste, nie aus einer eigenen Abfrage auf `photo_scores`."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    fremder_gewinner = await _photo(db_session, other, "fremd.jpg", seconds=0)
    verlierer = await _photo(
        db_session,
        home,
        "verlierer.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=fremder_gewinner.id,
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(home.id))).json()

    assert _entry(body, verlierer.id)["group_anchor_photo_id"] is None


# ------------------------------------------------------------------------------------------
# open_count, Paginierung, Leerfaelle (AK9, AK14)
# ------------------------------------------------------------------------------------------


async def test_the_open_count_is_project_wide_and_independent_of_the_page(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK9: Der Bestaetigungsbutton nennt die projektweite Zahl der OFFENEN Vorschlaege. Sie haengt
    nicht an `limit`/`offset` - waere sie `len(items)`, nennte der Button auf der zweiten Seite eine
    andere Zahl, und ein bereits entschiedenes Bild zaehlte mit."""
    project = await _project(db_session)
    for index in range(3):
        await _photo(
            db_session,
            project,
            f"offen-{index}.jpg",
            seconds=index,
            suggested_status=RatingStatus.REJECTED,
        )
    await _photo(
        db_session,
        project,
        "entschieden.jpg",
        seconds=10,
        suggested_status=RatingStatus.REJECTED,
        decision=DuplicateDecision.DISCARD,
    )
    await db_session.commit()

    erste = (await authenticated_api_client.get(_url(project.id, limit=1))).json()
    zweite = (await authenticated_api_client.get(_url(project.id, limit=1, offset=1))).json()

    assert erste["open_count"] == zweite["open_count"] == 3
    assert erste["total"] == zweite["total"] == 4
    assert len(erste["items"]) == 1


async def test_the_open_count_of_another_project_is_never_counted_in(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S1): Dieselbe Projektbindung wie der Bestand - eine Zaehlung ueber alle Projekte
    gaebe dem Button eine Zahl, die auf dieser Seite niemand einloesen kann."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    await _photo(db_session, home, "eigene.jpg", suggested_status=RatingStatus.REJECTED)
    await _photo(
        db_session, other, "fremd-1.jpg", seconds=0, suggested_status=RatingStatus.REJECTED
    )
    await _photo(
        db_session, other, "fremd-2.jpg", seconds=1, suggested_status=RatingStatus.REJECTED
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(home.id))).json()

    assert body["open_count"] == 1


async def test_two_pages_do_not_overlap_and_the_total_counts_everything(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK3: Reihenfolge `Photo.taken_at, Photo.id` und ein `total` ueber den GANZEN Bestand - kein
    aus `len(items)` gebildetes, das auf der ersten Seite nicht davon zu unterscheiden waere."""
    project = await _project(db_session)
    fotos = [
        await _photo(
            db_session,
            project,
            f"foto-{index}.jpg",
            seconds=index,
            suggested_status=RatingStatus.REJECTED,
        )
        for index in range(5)
    ]
    await db_session.commit()

    erste = (await authenticated_api_client.get(_url(project.id, limit=2))).json()
    zweite = (await authenticated_api_client.get(_url(project.id, limit=2, offset=2))).json()

    assert _ids(erste) == [foto.id for foto in fotos[:2]]
    assert _ids(zweite) == [foto.id for foto in fotos[2:4]]
    assert set(_ids(erste)).isdisjoint(_ids(zweite))
    assert erste["total"] == 5


async def test_an_empty_project_answers_200_with_empty_lists(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK14: "leer" ist ein regulaerer Zustand, kein Fehler - auch ohne erfolgreichen `ScoringRun`
    und bei einem Projekt ganz ohne Fotos. Kein `404`, kein `409`: Beide Codes truegen eine Aussage
    ueber einen Vorgang, den es nicht gibt."""
    project = await _project(db_session)
    await db_session.commit()

    ohne_lauf = (await authenticated_api_client.get(_url(project.id))).json()

    await _successful_run(db_session, project)
    await db_session.commit()
    mit_lauf = (await authenticated_api_client.get(_url(project.id))).json()

    leer = {"items": [], "total": 0, "open_count": 0}
    assert ohne_lauf == mit_lauf == leer


async def test_the_photo_filter_returns_exactly_that_entry(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die Detailansicht zieht genau einen Eintrag - und dieselbe Groesse wie die Uebersicht, damit
    beide ueber denselben Bildzustand sprechen. `total`/`open_count` bleiben die projektweiten
    Zahlen, sonst truege der Bestaetigungsbutton in der Detailansicht eine andere Zahl."""
    project = await _project(db_session)
    gesucht = await _photo(
        db_session,
        project,
        "gesucht.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        decision=DuplicateDecision.DISCARD,
    )
    await _photo(
        db_session, project, "anderes.jpg", seconds=2, suggested_status=RatingStatus.REJECTED
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id, photo_id=gesucht.id))).json()

    assert _ids(body) == [gesucht.id]
    assert body["total"] == 2
    assert body["open_count"] == 1
    assert _entry(body, gesucht.id)["reason"] == "low_quality"
    assert _entry(body, gesucht.id)["decision"] == "discard"


async def test_a_photo_filter_outside_the_stock_answers_an_empty_list(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S6): Eine unbekannte oder fremde `photo_id` liefert eine LEERE Liste,
    ununterscheidbar von einer unbekannten - nicht `404`, das ein Existenz-Orakel ueber fremde Ids
    waere. Die Uebersicht selbst bleibt gefuellt."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    await _photo(db_session, home, "eigene.jpg", suggested_status=RatingStatus.REJECTED)
    fremde = await _photo(db_session, other, "fremde.jpg", suggested_status=RatingStatus.REJECTED)
    await db_session.commit()

    unbekannt = (await authenticated_api_client.get(_url(home.id, photo_id=999_999))).json()
    fremd = (await authenticated_api_client.get(_url(home.id, photo_id=fremde.id))).json()

    assert _ids(unbekannt) == []
    assert _ids(fremd) == []
    assert unbekannt["total"] == fremd["total"] == 1


async def test_the_answer_carries_exactly_the_three_agreed_fields(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Als Gleichheit der Feldmenge, damit ein spaeter angehaengtes Feld auffaellt, bevor es
    stillschweigend mitreist."""
    project = await _project(db_session)
    await _photo(db_session, project, "foto.jpg", suggested_status=RatingStatus.REJECTED)
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert set(body) == {"items", "total", "open_count"}
    assert set(_entry(body, _ids(body)[0])) == {
        "photo",
        "reason",
        "decision",
        "group_anchor_photo_id",
    }
