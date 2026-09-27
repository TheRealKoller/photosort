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
    """Die Foto-Id je Eintrag: das Foto des Einzel-Eintrags, das Titelbild des Stapels."""
    items = body["items"]
    assert isinstance(items, list)
    return [
        entry["photo"]["id"] if entry["kind"] == "photo" else entry["cover"]["id"]
        for entry in items
    ]


def _entry(body: dict[str, object], photo_id: int) -> dict[str, object]:
    """Der EINZEL-Eintrag dieser Aufnahme."""
    items = body["items"]
    assert isinstance(items, list)
    treffer = [
        entry for entry in items if entry["kind"] == "photo" and entry["photo"]["id"] == photo_id
    ]
    assert len(treffer) == 1, "Der Eintrag fehlt oder steht doppelt in der Antwort."
    return treffer[0]


def _groups(body: dict[str, object]) -> list[dict[str, object]]:
    items = body["items"]
    assert isinstance(items, list)
    return [entry for entry in items if entry["kind"] == "group"]


def _group(body: dict[str, object], anchor_id: int) -> dict[str, object]:
    treffer = [entry for entry in _groups(body) if entry["group_anchor_photo_id"] == anchor_id]
    assert len(treffer) == 1, "Der Stapel fehlt oder steht doppelt in der Antwort."
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
    """SICHERHEIT (S6/S8): `has_open_suggestion` traegt selbst KEINE Projektbedingung - sie kommt
    allein aus dem umgebenden Join auf `Photo`. Ohne ihn liefert die Uebersicht jeden offenen
    Vorschlag der ganzen Instanz aus - als Einzel-Eintrag wie als Stapel."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    eigene = await _photo(db_session, home, "eigene.jpg", suggested_status=RatingStatus.REJECTED)
    fremde = await _photo(db_session, other, "fremde.jpg", suggested_status=RatingStatus.REJECTED)
    fremder_gewinner = await _photo(db_session, other, "fremder-gewinner.jpg", seconds=1)
    fremder_verlierer = await _photo(
        db_session,
        other,
        "fremder-verlierer.jpg",
        seconds=2,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=fremder_gewinner.id,
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(home.id))).json()

    assert _ids(body) == [eigene.id]
    assert body["total"] == 1
    assert _groups(body) == []
    assert {fremde.id, fremder_verlierer.id}.isdisjoint(_ids(body))


# ------------------------------------------------------------------------------------------
# Grund, Entscheidung, Anker (AK4, AK6, AK8)
# ------------------------------------------------------------------------------------------


async def test_the_reason_matches_the_suggestion_reason_of_the_score(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK4: `reason` ist eine ZWEITE Fassung derselben Ableitung - `duplicate` genau dann, wenn
    `duplicate_of IS NOT NULL`, sonst `low_quality`. Beide Gruende stehen nebeneinander, damit eine
    Umsetzung auffaellt, die alle Eintraege gleich kennzeichnet. Das Duplikat ist in der Liste
    Teil seines Stapels und traegt seinen Grund deshalb am Detailfilter (Spec 0533, B6)."""
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
    detail = (await authenticated_api_client.get(_url(project.id, photo_id=duplikat.id))).json()

    assert _entry(detail, duplikat.id)["reason"] == "duplicate"
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
    """Der Anker ist die Repraesentanten-Id - dieselbe, unter der die Gruppenantwort erreichbar
    ist. In der Liste traegt ihn der Stapel, am Detailfilter der Einzel-Eintrag des Mitglieds
    (Spec 0533, B6/B8); die Unschaerfe-Ablehnung ohne Gruppe traegt keinen."""
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
    detail = (await authenticated_api_client.get(_url(project.id, photo_id=verlierer.id))).json()
    gruppe = (
        await authenticated_api_client.get(
            f"/projects/{project.id}/duplicate-groups/{verlierer.id}"
        )
    ).json()

    assert _group(body, gewinner.id)["cover"]["id"] == verlierer.id
    assert _entry(detail, verlierer.id)["group_anchor_photo_id"] == gewinner.id
    assert gruppe["items"][0]["photo"]["id"] == gewinner.id
    assert _entry(body, unscharf.id)["group_anchor_photo_id"] is None


async def test_keep_possible_comes_from_the_server_and_not_from_the_reason(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """D1: Grund und Wirksamkeit sind zwei verschiedene Aussagen ueber dieselbe Aufnahme.

    `reason` ist `low_quality` genau dann, wenn `duplicate_of IS NULL`. `keep_possible` ist die
    Wirksamkeit eines hypothetischen `keep` (`duplicates.py::keep_possible_for`). Beides faellt
    auseinander, wenn eine Entscheidungszeile einen Lauf ueberlebt, in dem `suggested_status` UND
    `duplicate_of` zurueckgesetzt wurden: Der Eintrag traegt dann `low_quality` und trotzdem
    `keep_possible`. Wer das Feld aus dem Grund ableitet, naehme dem Nutzer dort die einzige
    Handlung, die die Aufnahme zurueckholt - und die Ansicht widerspraeche dem Schreibweg."""
    project = await _project(db_session)
    zeile_ohne_vorschlag = await _photo(
        db_session,
        project,
        "zeile.jpg",
        seconds=0,
        suggested_status=None,
        duplicate_of=None,
        decision=DuplicateDecision.DISCARD,
    )
    unscharf = await _photo(
        db_session, project, "unscharf.jpg", seconds=1, suggested_status=RatingStatus.REJECTED
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert _entry(body, zeile_ohne_vorschlag.id)["reason"] == "low_quality"
    assert _entry(body, zeile_ohne_vorschlag.id)["keep_possible"] is True
    assert _entry(body, unscharf.id)["reason"] == "low_quality"
    assert _entry(body, unscharf.id)["keep_possible"] is False


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
    """SICHERHEIT (S6/S8): `duplicate_of` zeigt auf `photos.id` ohne Projektbedingung. Zeigt ein
    eigener Verlierer auf den Gewinner eines FREMDEN Projekts, bleibt er ein Einzel-Eintrag mit
    leerem Anker, und kein Stapel nennt die fremde Id - Anker und Gruppe stammen aus der
    projektbegrenzten Kantenliste, nie aus einer eigenen Abfrage auf `photo_scores`."""
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

    assert _entry(body, verlierer.id)["kind"] == "photo"
    assert _entry(body, verlierer.id)["group_anchor_photo_id"] is None
    assert _groups(body) == []
    assert fremder_gewinner.id not in [entry["group_anchor_photo_id"] for entry in body["items"]]


# ------------------------------------------------------------------------------------------
# Stapel je Duplikatgruppe (Spec 0533, B6/B7)
# ------------------------------------------------------------------------------------------


async def _group_with_losers(
    session: AsyncSession, project: Project, count: int, *, first_second: int = 0
) -> tuple[Photo, list[Photo]]:
    """Ein Gewinner ohne Vorschlag, zeitlich zuerst, und `count` offene Verlierer."""
    gewinner = await _photo(session, project, f"gewinner-{first_second}.jpg", seconds=first_second)
    verlierer = [
        await _photo(
            session,
            project,
            f"verlierer-{first_second}-{index}.jpg",
            seconds=first_second + 1 + index,
            suggested_status=RatingStatus.REJECTED,
            duplicate_of=gewinner.id,
        )
        for index in range(count)
    ]
    return gewinner, verlierer


async def test_photos_without_a_resolvable_group_stay_single_entries(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S8): `None` ist nie ein Gruppenschluessel. Zwei Unschaerfe-Ablehnungen ohne
    Gruppe bleiben zwei Einzel-Eintraege, statt zu einem Stapel zu verschmelzen, dessen Link ins
    Leere fuehrt - auch neben einer echten Gruppe desselben Projekts."""
    project = await _project(db_session)
    erste = await _photo(
        db_session, project, "unscharf-1.jpg", seconds=0, suggested_status=RatingStatus.REJECTED
    )
    zweite = await _photo(
        db_session, project, "unscharf-2.jpg", seconds=1, suggested_status=RatingStatus.REJECTED
    )
    gewinner, _ = await _group_with_losers(db_session, project, 2, first_second=10)
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert [entry["kind"] for entry in body["items"]] == ["photo", "photo", "group"]
    assert _ids(body)[:2] == [erste.id, zweite.id]
    assert [entry["group_anchor_photo_id"] for entry in _groups(body)] == [gewinner.id]


async def test_the_stack_counts_the_whole_group_and_the_stock_members_separately(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """B7: `group_size` zaehlt ALLE Mitglieder und ist dieselbe Zahl wie die Mitgliederzahl der
    Gruppenantwort; `member_count` zaehlt nur die Bestandsaufnahmen. Der Gewinner ohne Vorschlag
    liegt nicht im Bestand und ist zeitlich zuerst - er ist deshalb auch nicht das Titelbild."""
    project = await _project(db_session)
    gewinner, verlierer = await _group_with_losers(db_session, project, 2)
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()
    gruppe = (
        await authenticated_api_client.get(f"/projects/{project.id}/duplicate-groups/{gewinner.id}")
    ).json()

    stapel = _group(body, gewinner.id)
    assert stapel["group_size"] == len(gruppe["items"]) == 3
    assert stapel["member_count"] == 2
    assert stapel["cover"]["id"] == verlierer[0].id != gewinner.id
    counts = stapel["decision_counts"]
    assert counts == {"undecided": 2, "keep": 0, "discard": 0}
    assert counts["undecided"] + counts["keep"] + counts["discard"] == stapel["member_count"]


async def test_the_sharpness_rejected_winner_lies_in_the_stack_of_its_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """B6: Gruppiert wird nach Mitgliedschaft, nicht nach `reason`. Der Gewinner mit
    Schaerfe-Ablehnung erscheint nicht als Einzelkachel "Geringe Bildqualitaet", sondern zaehlt in
    `member_count` seines Stapels. Traegt er dazu eine `keep`-Zeile, zaehlt sie als gespeichertes
    `keep`, obwohl sein angezeigter Zustand "Ausschuss" bleibt."""
    project = await _project(db_session)
    gewinner = await _photo(
        db_session,
        project,
        "gewinner.jpg",
        seconds=0,
        suggested_status=RatingStatus.REJECTED,
        decision=DuplicateDecision.KEEP,
    )
    await _photo(
        db_session,
        project,
        "verlierer.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=gewinner.id,
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()
    gruppe = (
        await authenticated_api_client.get(f"/projects/{project.id}/duplicate-groups/{gewinner.id}")
    ).json()

    assert [entry["kind"] for entry in body["items"]] == ["group"]
    stapel = _group(body, gewinner.id)
    assert stapel["member_count"] == stapel["group_size"] == 2
    assert stapel["cover"]["id"] == gewinner.id
    assert stapel["decision_counts"] == {"undecided": 1, "keep": 1, "discard": 0}
    angezeigt = {item["photo"]["id"]: item["effective_decision"] for item in gruppe["items"]}
    assert angezeigt[gewinner.id] == "discard"


async def test_a_winner_carried_only_by_a_keep_row_lies_in_the_stack(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """B6, ueber den Schreibweg des Produkts: Nach "Alle behalten" traegt auch der Gewinner ohne
    Vorschlag eine `keep`-Zeile und kommt so in den Bestand - er liegt dann im Stapel, nicht als
    Einzelkachel daneben."""
    project = await _project(db_session)
    gewinner, _ = await _group_with_losers(db_session, project, 2)
    await db_session.commit()

    antwort = await authenticated_api_client.put(
        f"/projects/{project.id}/duplicate-groups/{gewinner.id}/decision",
        json={"decision": "keep"},
    )
    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert antwort.status_code == 200
    assert [entry["kind"] for entry in body["items"]] == ["group"]
    stapel = _group(body, gewinner.id)
    assert stapel["member_count"] == stapel["group_size"] == 3
    assert stapel["decision_counts"]["keep"] == stapel["group_size"]
    assert stapel["cover"]["id"] == gewinner.id


async def test_a_foreign_photo_pointing_into_the_own_group_never_enlarges_the_stack(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S8): Eine fremde Aufnahme mit `duplicate_of` auf den eigenen Gewinner zaehlt
    weder in `group_size` noch in `member_count`."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    gewinner, _ = await _group_with_losers(db_session, home, 1)
    await _photo(
        db_session,
        other,
        "fremd.jpg",
        seconds=5,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=gewinner.id,
    )
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(home.id))).json()

    stapel = _group(body, gewinner.id)
    assert stapel["group_size"] == 2
    assert stapel["member_count"] == 1


async def test_the_list_branch_never_carries_an_anchor_on_a_photo_entry(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """B6: Im Listenzweig traegt kein Einzel-Eintrag einen Gruppenanker - jede Aufnahme mit
    aufloesbarer Gruppe liegt in deren Stapel. Ueber mehrere Gruppen und Einzelaufnahmen, auf
    jeder Seite."""
    project = await _project(db_session)
    await _group_with_losers(db_session, project, 2, first_second=0)
    await _photo(
        db_session, project, "unscharf.jpg", seconds=5, suggested_status=RatingStatus.REJECTED
    )
    await _group_with_losers(db_session, project, 3, first_second=10)
    await db_session.commit()

    for offset in range(3):
        seite = (
            await authenticated_api_client.get(_url(project.id, limit=1, offset=offset))
        ).json()
        for entry in seite["items"]:
            if entry["kind"] == "photo":
                assert entry["group_anchor_photo_id"] is None


# ------------------------------------------------------------------------------------------
# Paginierung nach Eintraegen (Spec 0533, B8)
# ------------------------------------------------------------------------------------------


async def test_a_group_never_falls_apart_over_a_page_boundary(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Gruppe mit drei Bestandsaufnahmen (t = 1, 2, 3) und eine Einzelaufnahme (t = 4), `limit=2`:
    Seite 1 ist [Stapel, Einzelaufnahme], und der Stapel zaehlt DREI Mitglieder. Ein SQL-Schnitt
    vor dem Gruppieren ergaebe einen Stapel mit zwei - die Ids allein bestuenden auch dagegen."""
    project = await _project(db_session)
    gewinner, _ = await _group_with_losers(db_session, project, 3)
    einzeln = await _photo(
        db_session, project, "unscharf.jpg", seconds=4, suggested_status=RatingStatus.REJECTED
    )
    await db_session.commit()

    erste = (await authenticated_api_client.get(_url(project.id, limit=2))).json()

    assert [entry["kind"] for entry in erste["items"]] == ["group", "photo"]
    assert _group(erste, gewinner.id)["member_count"] == 3
    assert _entry(erste, einzeln.id)["kind"] == "photo"
    assert erste["total"] == 2


async def test_an_interleaved_group_stands_at_its_first_stock_photo(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Verschraenkte Lage: Gruppe bei t = 0 und t = 5, Einzelaufnahme bei t = 3. Die Reihenfolge
    ist [Stapel, Einzelaufnahme]; die Folgeseite traegt keinen zweiten Eintrag derselben Gruppe."""
    project = await _project(db_session)
    gewinner = await _photo(
        db_session, project, "gewinner.jpg", seconds=0, suggested_status=RatingStatus.REJECTED
    )
    einzeln = await _photo(
        db_session, project, "unscharf.jpg", seconds=3, suggested_status=RatingStatus.REJECTED
    )
    await _photo(
        db_session,
        project,
        "verlierer.jpg",
        seconds=5,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=gewinner.id,
    )
    await db_session.commit()

    alle = (await authenticated_api_client.get(_url(project.id))).json()
    zweite = (await authenticated_api_client.get(_url(project.id, limit=1, offset=1))).json()

    assert [entry["kind"] for entry in alle["items"]] == ["group", "photo"]
    assert _ids(zweite) == [einzeln.id]
    assert _groups(zweite) == []


async def test_walking_all_pages_names_every_anchor_exactly_once(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Seitendurchlauf mit `limit=1`: Jeder Anker kommt genau einmal vor, jede Bestandsaufnahme
    steht genau einmal (als Einzel-Eintrag oder in `member_count`), und die Zahl der Eintraege ist
    `total`."""
    project = await _project(db_session)
    erste_gruppe, _ = await _group_with_losers(db_session, project, 2, first_second=0)
    await _photo(
        db_session, project, "unscharf.jpg", seconds=5, suggested_status=RatingStatus.REJECTED
    )
    zweite_gruppe, _ = await _group_with_losers(db_session, project, 3, first_second=10)
    await db_session.commit()

    total = (await authenticated_api_client.get(_url(project.id))).json()["total"]
    eintraege: list[dict[str, object]] = []
    for offset in range(total + 1):
        seite = (
            await authenticated_api_client.get(_url(project.id, limit=1, offset=offset))
        ).json()
        eintraege.extend(seite["items"])

    anker = [entry["group_anchor_photo_id"] for entry in eintraege if entry["kind"] == "group"]
    assert anker == [erste_gruppe.id, zweite_gruppe.id]
    assert len(eintraege) == total == 3
    aufnahmen = sum(
        1 if entry["kind"] == "photo" else int(str(entry["member_count"])) for entry in eintraege
    )
    assert aufnahmen == 6


async def test_entries_and_open_suggestions_are_two_different_counts(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Drei offene Verlierer in einer Gruppe: `total = 1` (Eintraege), `open_count = 3`
    (Aufnahmen). Das ist die Lage, in der die beiden Einheiten auseinanderfallen."""
    project = await _project(db_session)
    await _group_with_losers(db_session, project, 3)
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()

    assert body["total"] == 1
    assert body["open_count"] == 3


async def test_the_photo_filter_on_a_group_member_answers_a_photo_entry_with_its_anchor(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """B8: Der Detailfilter liefert fuer ein Gruppenmitglied genau einen Einzel-Eintrag mit
    gesetztem Anker; `total` und `open_count` sind dieselben wie im Listenzweig."""
    project = await _project(db_session)
    gewinner, verlierer = await _group_with_losers(db_session, project, 2)
    await _photo(
        db_session, project, "unscharf.jpg", seconds=9, suggested_status=RatingStatus.REJECTED
    )
    await db_session.commit()

    liste = (await authenticated_api_client.get(_url(project.id))).json()
    detail = (await authenticated_api_client.get(_url(project.id, photo_id=verlierer[1].id))).json()

    assert _ids(detail) == [verlierer[1].id]
    assert _entry(detail, verlierer[1].id)["group_anchor_photo_id"] == gewinner.id
    assert detail["total"] == liste["total"] == 2
    assert detail["open_count"] == liste["open_count"] == 3


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
    """Reihenfolge `Photo.taken_at, Photo.id` und ein `total` ueber den GANZEN Bestand - kein aus
    `len(items)` gebildetes, das auf der ersten Seite nicht davon zu unterscheiden waere. `total`
    zaehlt Eintraege; hier der Spezialfall nur mit Einzelaufnahmen, in dem Eintraege und
    Aufnahmen zusammenfallen."""
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


async def test_the_answer_carries_exactly_the_agreed_fields(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Als Gleichheit der Feldmenge je Eintragsart, damit ein spaeter angehaengtes Feld auffaellt,
    bevor es stillschweigend mitreist. `cover` traegt dieselbe Feldmenge wie ein Eintrag der
    Fotoliste - ein `PhotoOut`, weder erweitert noch gekuerzt."""
    project = await _project(db_session)
    await _photo(db_session, project, "foto.jpg", suggested_status=RatingStatus.REJECTED)
    await _group_with_losers(db_session, project, 1, first_second=10)
    await db_session.commit()

    body = (await authenticated_api_client.get(_url(project.id))).json()
    liste = (await authenticated_api_client.get(f"/projects/{project.id}/photos")).json()

    assert set(body) == {"items", "total", "open_count"}
    einzel, stapel = body["items"]
    assert set(einzel) == {
        "kind",
        "photo",
        "reason",
        "decision",
        "group_anchor_photo_id",
        "keep_possible",
    }
    assert set(stapel) == {
        "kind",
        "group_anchor_photo_id",
        "cover",
        "member_count",
        "group_size",
        "decision_counts",
    }
    assert set(stapel["decision_counts"]) == {"undecided", "keep", "discard"}
    assert set(stapel["cover"]) == set(liste["items"][0])
