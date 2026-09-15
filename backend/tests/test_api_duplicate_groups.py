"""`GET /projects/{project_id}/duplicate-groups/{photo_id}` - der Lesepfad der Vergleichsansicht.

Die Gruppe ist ABGELEITET (ADR 0104 Punkt 1): Jeder Aufruf bildet den Stern zur Lesezeit neu. Es
gibt keine Gruppen-Id, und dieselbe Gruppe ist deshalb ueber JEDES ihrer Mitglieder erreichbar -
das ist hier eine gepruefte Zusage, kein Nebeneffekt.

`404` DECKT VIER FAELLE UND UNTERSCHEIDET SIE NICHT: unbekannte Id, fremdes Projekt, Foto ohne
Gruppe und Vorschlag aus geringer Bildqualitaet (AK13). Ein Aufruf darf nicht ablesen koennen,
welcher davon vorliegt - sonst waere die Antwort ein Auskunftsmittel ueber fremde Bestaende.
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
    RatingStatus,
)

_BASE = datetime(2023, 5, 1, 12, 0, 0, tzinfo=UTC)


async def _project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=f"/{name}")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _photo(
    session: AsyncSession,
    project: Project,
    path: str,
    *,
    seconds: int = 0,
    taken_at: datetime | None = None,
    with_score: bool = True,
    suggested_status: RatingStatus | None = None,
    duplicate_of: int | None = None,
    decision: DuplicateDecision | None = None,
) -> Photo:
    moment = taken_at if taken_at is not None else _BASE + timedelta(seconds=seconds)
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
    await session.commit()
    await session.refresh(photo)
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
    await session.commit()
    return photo


async def _star(
    session: AsyncSession, project: Project, size: int, *, first_second: int = 0, prefix: str = "g"
) -> tuple[Photo, list[Photo]]:
    """Der Gewinner plus `size - 1` Verlierer, die auf ihn zeigen. Der Gewinner traegt bewusst
    KEINE Vorschlagszeile - er ist der Ausschuss-Ueberlebende der Serie."""
    winner = await _photo(session, project, f"{prefix}-gewinner.jpg", seconds=first_second)
    losers = [
        await _photo(
            session,
            project,
            f"{prefix}-verlierer-{offset}.jpg",
            seconds=first_second + offset,
            suggested_status=RatingStatus.REJECTED,
            duplicate_of=winner.id,
        )
        for offset in range(1, size)
    ]
    return winner, losers


def _url(project_id: int, photo_id: int) -> str:
    return f"/projects/{project_id}/duplicate-groups/{photo_id}"


# ------------------------------------------------------------------------------------------
# Erreichbarkeit und Gruppenbegriff (AK1)
# ------------------------------------------------------------------------------------------


async def test_the_endpoint_requires_a_token(api_client: httpx.AsyncClient) -> None:
    """Pfadbenannter 401-Fall: `photos.router` traegt bewusst KEINE router-weite
    `dependencies`-Liste, ein Endpunkt ohne ausgeschriebene Auth-Dependency waere dort still
    oeffentlich."""
    response = await api_client.get(_url(1, 1))

    assert response.status_code == 401


async def test_the_group_holds_the_representative_and_everyone_pointing_at_it(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)

    response = await authenticated_api_client.get(_url(project.id, losers[0].id))

    assert response.status_code == 200
    body = response.json()
    assert [item["photo"]["id"] for item in body["items"]] == [
        winner.id,
        losers[0].id,
        losers[1].id,
    ]


async def test_every_member_reaches_the_same_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die Gruppe hat keine eigene Id - sie ist ueber jedes Mitglied erreichbar, den Gewinner
    eingeschlossen. Der Gewinner traegt dabei selbst keine Vorschlagszeile (AK1)."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)

    antworten = [
        (await authenticated_api_client.get(_url(project.id, member.id))).json()
        for member in (winner, *losers)
    ]

    assert all(antwort == antworten[0] for antwort in antworten)


@pytest.mark.parametrize("size", [2, 3, 5])
async def test_a_star_of_any_size_returns_exactly_its_members(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, size: int
) -> None:
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, size)

    body = (await authenticated_api_client.get(_url(project.id, winner.id))).json()

    assert len(body["items"]) == size
    assert {item["photo"]["id"] for item in body["items"]} == {
        winner.id,
        *(loser.id for loser in losers),
    }


async def test_the_members_are_ordered_by_taken_at_then_id(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK2 als vollstaendige Id-Folge bei durchgehend gleichem `taken_at` - Serienaufnahmen tragen
    haeufig denselben Zeitstempel, und ohne den Zweitschluessel waere die Reihenfolge nicht
    reproduzierbar."""
    project = await _project(db_session)
    gleichzeitig = _BASE
    winner = await _photo(db_session, project, "w.jpg", taken_at=gleichzeitig)
    zweiter = await _photo(
        db_session,
        project,
        "b.jpg",
        taken_at=gleichzeitig,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )
    dritter = await _photo(
        db_session,
        project,
        "c.jpg",
        taken_at=gleichzeitig,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )

    body = (await authenticated_api_client.get(_url(project.id, winner.id))).json()

    assert [item["photo"]["id"] for item in body["items"]] == [winner.id, zweiter.id, dritter.id]


# ------------------------------------------------------------------------------------------
# Die vier 404-Faelle
# ------------------------------------------------------------------------------------------


async def test_an_unknown_photo_is_a_404(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)

    response = await authenticated_api_client.get(_url(project.id, 999_999))

    assert response.status_code == 404


async def test_a_photo_without_a_group_is_a_404(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der entartete Fall `n = 1`: kein `duplicate_of`, niemand zeigt darauf. Zugleich die
    Durchsetzung von "nur fuer als Duplikat erkannte Aufnahmen"."""
    project = await _project(db_session)
    einzeln = await _photo(db_session, project, "einzeln.jpg")

    response = await authenticated_api_client.get(_url(project.id, einzeln.id))

    assert response.status_code == 404


async def test_a_low_quality_suggestion_is_a_404(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK13: Fuer Vorschlaege wegen geringer Bildqualitaet aendert sich nichts. Eine solche
    Aufnahme traegt `suggested_status = REJECTED` OHNE `duplicate_of` - sie hat keine Gruppe, und
    der Vergleich hat ihr nichts zu zeigen."""
    project = await _project(db_session)
    unscharf = await _photo(
        db_session, project, "unscharf.jpg", suggested_status=RatingStatus.REJECTED
    )

    response = await authenticated_api_client.get(_url(project.id, unscharf.id))

    assert response.status_code == 404


async def test_a_photo_of_another_project_is_a_404_that_reveals_nothing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S7): Die Antwort spiegelt den Wert nicht und ist von der eines unbekannten
    Fotos nicht zu unterscheiden."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    _fremder_gewinner, fremde_verlierer = await _star(db_session, other, 3, prefix="f")

    fremd = await authenticated_api_client.get(_url(home.id, fremde_verlierer[0].id))
    unbekannt = await authenticated_api_client.get(_url(home.id, 999_999))

    assert fremd.status_code == 404
    assert fremd.json() == unbekannt.json()


async def test_a_foreign_photo_pointing_into_this_project_never_joins_the_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S7) in der SCHARFEN Form: Nur diese Datenlage deckt ein fehlendes
    `Photo.project_id`-Praedikat auf - der blosse 404-Fall bestuende auch ohne es.
    `photo_scores.duplicate_of` zeigt auf `photos.id` ohne Projektbedingung."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    winner, losers = await _star(db_session, home, 2)
    fremder_verlierer = await _photo(
        db_session,
        other,
        "fremd.jpg",
        seconds=5,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )

    body = (await authenticated_api_client.get(_url(home.id, winner.id))).json()

    assert [item["photo"]["id"] for item in body["items"]] == [winner.id, losers[0].id]
    assert fremder_verlierer.id not in {item["photo"]["id"] for item in body["items"]}


async def test_an_unknown_project_is_a_404(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get(_url(999_999, 1))

    assert response.status_code == 404


@pytest.mark.parametrize("photo_id", [0, -1, MAX_QUERY_POSITION + 1])
async def test_a_photo_id_outside_the_declared_bounds_is_a_422(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, photo_id: int
) -> None:
    """SICHERHEIT (S6): Ein unbeschraenkter Pydantic-`int` erreicht die Datenbank und wird
    jenseits von 2^63 zu `500` statt `404`."""
    project = await _project(db_session)

    response = await authenticated_api_client.get(_url(project.id, photo_id))

    assert response.status_code == 422


# ------------------------------------------------------------------------------------------
# Entscheidung und Gruppenzaehler
# ------------------------------------------------------------------------------------------


async def test_each_item_carries_the_state_that_applies_without_further_action(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """DER KERN VON AK1. Das dritte Mitglied traegt KEINE Entscheidungszeile und stand bis zu
    dieser Story deshalb als `null` da - es scheidet aber ohne weiteres Zutun aus. Die Ansicht
    zeigt seit ADR 0111 die Auswertung des Praedikats, nicht die Zeile: Es gibt kein `null` mehr,
    und der unentschiedene Verlierer steht von Anfang an als `discard` da."""
    project = await _project(db_session)
    winner = await _photo(db_session, project, "w.jpg", decision=DuplicateDecision.KEEP)
    verworfen = await _photo(
        db_session,
        project,
        "b.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
        decision=DuplicateDecision.DISCARD,
    )
    ohne_zeile = await _photo(
        db_session,
        project,
        "c.jpg",
        seconds=2,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )

    body = (await authenticated_api_client.get(_url(project.id, winner.id))).json()

    assert {item["photo"]["id"]: item["effective_decision"] for item in body["items"]} == {
        winner.id: "keep",
        verworfen.id: "discard",
        ohne_zeile.id: "discard",
    }


async def test_the_answer_never_says_whether_a_state_came_from_the_automaton_or_the_user(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK2: Es gibt keinen Zustand "noch nicht entschieden" mehr, und die Herkunft wird nicht
    unterschieden. Geprueft als Ununterscheidbarkeit zweier Bestaende, die sich NUR in der
    Anwesenheit der Entscheidungszeile unterscheiden - ein zusaetzliches Herkunftsfeld oder ein
    drittes `effective_decision` faellt hier auf."""
    project = await _project(db_session)
    winner = await _photo(db_session, project, "w.jpg")
    ohne_zeile = await _photo(
        db_session,
        project,
        "b.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )
    mit_zeile = await _photo(
        db_session,
        project,
        "c.jpg",
        seconds=2,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
        decision=DuplicateDecision.DISCARD,
    )

    body = (await authenticated_api_client.get(_url(project.id, winner.id))).json()
    eintraege = {item["photo"]["id"]: item for item in body["items"]}

    ohne = {schluessel: wert for schluessel, wert in eintraege[ohne_zeile.id].items()}
    mit = {schluessel: wert for schluessel, wert in eintraege[mit_zeile.id].items()}
    del ohne["photo"], mit["photo"]
    assert ohne == mit


async def test_the_counter_is_one_based_over_all_groups(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    erste, _ = await _star(db_session, project, 2, first_second=0, prefix="a")
    zweite, _ = await _star(db_session, project, 2, first_second=100, prefix="b")
    dritte, _ = await _star(db_session, project, 2, first_second=200, prefix="c")

    zaehler = {}
    for stern in (erste, zweite, dritte):
        body = (await authenticated_api_client.get(_url(project.id, stern.id))).json()
        zaehler[stern.id] = (body["position"], body["total"])

    assert zaehler == {erste.id: (1, 3), zweite.id: (2, 3), dritte.id: (3, 3)}


async def test_the_neighbours_are_the_representative_ids_of_the_adjacent_groups(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK5: Ziel des Blaetterns ist jeweils die REPRAESENTANTEN-Id der Nachbargruppe, `null` am
    Rand ("nicht bedienbar", nicht "fehlt"). Geprueft ueber alle drei Gruppen zugleich - eine
    Umsetzung, die die Nachbarn je Gruppe plausibel, aber nicht kettenbildend besetzt, faellt nur
    so auf."""
    project = await _project(db_session)
    erste, _ = await _star(db_session, project, 2, first_second=0, prefix="a")
    zweite, _ = await _star(db_session, project, 2, first_second=100, prefix="b")
    dritte, _ = await _star(db_session, project, 2, first_second=200, prefix="c")

    nachbarn = {}
    for stern in (erste, zweite, dritte):
        body = (await authenticated_api_client.get(_url(project.id, stern.id))).json()
        nachbarn[stern.id] = (body["previous_photo_id"], body["next_photo_id"])

    assert nachbarn == {
        erste.id: (None, zweite.id),
        zweite.id: (erste.id, dritte.id),
        dritte.id: (zweite.id, None),
    }


async def test_a_finished_group_keeps_its_place_and_stays_reachable(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """HEBT AK10 DER SPEC 0374 AUF (AK6): Eine vollstaendig entschiedene Gruppe faellt NICHT mehr
    aus der Bezugsmenge. Sie behaelt ihren Platz, die offene Gruppe hinter ihr steht auf `(2, 2)`
    statt auf `(1, 1)`, und der Weg zurueck zu ihr fuehrt ueber `previous_photo_id`."""
    project = await _project(db_session)
    fertig_winner = await _photo(db_session, project, "a-w.jpg", decision=DuplicateDecision.KEEP)
    await _photo(
        db_session,
        project,
        "a-v.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=fertig_winner.id,
        decision=DuplicateDecision.DISCARD,
    )
    offen_winner, _ = await _star(db_session, project, 2, first_second=100, prefix="b")

    offen_body = (await authenticated_api_client.get(_url(project.id, offen_winner.id))).json()
    fertig_body = (await authenticated_api_client.get(_url(project.id, fertig_winner.id))).json()

    assert (offen_body["position"], offen_body["total"]) == (2, 2)
    assert (fertig_body["position"], fertig_body["total"]) == (1, 2)
    assert offen_body["previous_photo_id"] == fertig_winner.id


async def test_the_counter_stays_constant_while_another_group_is_decided(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK6, zugesichert gegen den SCHREIBWEG DES PRODUKTS und nicht bloss gegen zwei
    aufeinanderfolgende Lesevorgaenge: Zwischen den beiden Beobachtungen wird eine ANDERE Gruppe
    ueber den gruppenweiten Schreibweg vollstaendig entschieden.

    `(position, total)` steht als Gleichheit ZWEIER BEOBACHTUNGEN, nicht gegen ein Literal - ein
    Literal bestuende auch dann, wenn beide Lesevorgaenge dieselbe falsche Zahl lieferten."""
    project = await _project(db_session)
    erste, _ = await _star(db_session, project, 2, first_second=0, prefix="a")
    zweite, _ = await _star(db_session, project, 2, first_second=100, prefix="b")
    await _star(db_session, project, 2, first_second=200, prefix="c")

    vorher = (await authenticated_api_client.get(_url(project.id, zweite.id))).json()

    entschieden = await authenticated_api_client.put(
        f"/projects/{project.id}/duplicate-groups/{erste.id}/decision", json={"decision": "discard"}
    )
    assert entschieden.status_code == 200

    nachher = (await authenticated_api_client.get(_url(project.id, zweite.id))).json()

    assert (nachher["position"], nachher["total"]) == (vorher["position"], vorher["total"])
    assert nachher["previous_photo_id"] == erste.id


# ------------------------------------------------------------------------------------------
# Die Form der Antwort
# ------------------------------------------------------------------------------------------


async def test_the_item_carries_an_unextended_photo_out(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`PhotoOut` wird WIEDERVERWENDET und nicht erweitert (ADR 0104): Die Entscheidung hat
    ausserhalb dieser Ansicht keine Rolle und stuende sonst als Feld auf jedem Lesepfad. Geprueft
    als Gleichheit der Feldmenge gegen die Fotoliste - ein zusaetzliches Feld faellt hier auf."""
    project = await _project(db_session)
    winner, _ = await _star(db_session, project, 2)

    gruppe = (await authenticated_api_client.get(_url(project.id, winner.id))).json()
    liste = (await authenticated_api_client.get(f"/projects/{project.id}/photos")).json()

    vom_vergleich = next(
        item["photo"] for item in gruppe["items"] if item["photo"]["id"] == winner.id
    )
    aus_der_liste = next(item for item in liste["items"] if item["id"] == winner.id)
    assert set(vom_vergleich) == set(aus_der_liste)
    # Als GLEICHHEIT, nicht als Teilmenge: zugleich der Waechter dagegen, dass der Rohwert
    # `decision` spaeter als Zusatzfeld wieder mitreist.
    assert set(gruppe["items"][0]) == {"photo", "effective_decision", "keep_possible"}
    assert set(gruppe) == {
        "items",
        "position",
        "total",
        "previous_photo_id",
        "next_photo_id",
    }


# ------------------------------------------------------------------------------------------
# Die Unveraenderlichkeit (AK3) und ihr Verhaeltnis zum gruppenweiten Schreibweg (S4, S5)
# ------------------------------------------------------------------------------------------


async def _gruppe_mit_unveraenderlichem_mitglied(
    session: AsyncSession, project: Project
) -> tuple[Photo, Photo, Photo]:
    """Eine Serie, deren GEWINNER selbst wegen Unschaerfe abgelehnt ist: `suggested_status =
    REJECTED` bei `duplicate_of = None`. Sein Ausschuss folgt nicht aus dem Duplikat, und kein
    Wert der Entscheidungszeile aendert ihn."""
    unveraenderlich = await _photo(
        session, project, "u-w.jpg", suggested_status=RatingStatus.REJECTED
    )
    verlierer = await _photo(
        session,
        project,
        "u-v.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=unveraenderlich.id,
    )
    return unveraenderlich, verlierer, unveraenderlich


async def test_keep_possible_is_false_exactly_where_the_rejection_does_not_follow_from_the_duplicate(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK3: Eine wegen Unschaerfe abgelehnte Aufnahme laesst sich hier nicht auf "behalten" drehen
    und sagt das, statt einen Klick anzunehmen, der still wirkungslos bleibt."""
    project = await _project(db_session)
    unveraenderlich, verlierer, _ = await _gruppe_mit_unveraenderlichem_mitglied(
        db_session, project
    )

    body = (await authenticated_api_client.get(_url(project.id, unveraenderlich.id))).json()

    assert {item["photo"]["id"]: item["keep_possible"] for item in body["items"]} == {
        unveraenderlich.id: False,
        verlierer.id: True,
    }


async def test_keep_all_writes_on_every_member_and_the_immutable_one_still_reads_as_discard(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AUFLAGE S5 x AK3. Die Unterdrueckung der Wahlschaltflaechen ist eine ANZEIGE-, keine
    Durchsetzungsmassnahme: Der gruppenweite Schreibweg bestimmt die Menge unveraendert aus dem
    Stern und schreibt auf ALLE Mitglieder, das unveraenderliche eingeschlossen. Die dort
    geschriebene Zeile bleibt ohne Wirkung.

    Ohne diesen Fall waere ein Schreibweg, der das Mitglied auslaesst, von einem, der es
    einschliesst, nicht zu unterscheiden."""
    project = await _project(db_session)
    unveraenderlich, verlierer, _ = await _gruppe_mit_unveraenderlichem_mitglied(
        db_session, project
    )

    antwort = await authenticated_api_client.put(
        f"/projects/{project.id}/duplicate-groups/{unveraenderlich.id}/decision",
        json={"decision": "keep"},
    )

    assert antwort.status_code == 200
    geschrieben = (
        await db_session.execute(
            select(PhotoDuplicateDecision.photo_id, PhotoDuplicateDecision.decision)
        )
    ).all()
    assert dict(geschrieben) == {
        unveraenderlich.id: DuplicateDecision.KEEP,
        verlierer.id: DuplicateDecision.KEEP,
    }

    eintraege = {item["photo"]["id"]: item for item in antwort.json()["items"]}
    assert eintraege[unveraenderlich.id]["effective_decision"] == "discard"
    assert eintraege[unveraenderlich.id]["keep_possible"] is False
    assert eintraege[verlierer.id]["effective_decision"] == "keep"


async def test_a_member_without_a_score_row_reads_as_keep_instead_of_tearing_the_whole_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S3) auf dem Lesepfad: Der Repraesentant braucht strukturell keine eigene
    `PhotoScore`-Zeile. Ein `photo.score.suggested_status` an der Aufrufstelle traefe nicht eine
    Kachel, sondern die gesamte Gruppenantwort und damit den einzigen Zugang zur Ansicht (`500`)."""
    project = await _project(db_session)
    winner = await _photo(db_session, project, "w.jpg", with_score=False)
    verlierer = await _photo(
        db_session,
        project,
        "b.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )

    response = await authenticated_api_client.get(_url(project.id, winner.id))

    assert response.status_code == 200
    eintraege = {item["photo"]["id"]: item for item in response.json()["items"]}
    assert eintraege[winner.id]["effective_decision"] == "keep"
    assert eintraege[winner.id]["keep_possible"] is True
    assert eintraege[verlierer.id]["effective_decision"] == "discard"


# ------------------------------------------------------------------------------------------
# Das Seitenverhaeltnis auf dem fuenften Lesepfad (ADR 0110)
# ------------------------------------------------------------------------------------------


async def test_the_item_carries_the_aspect_ratio_like_every_other_read_path(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der fuenfte Lesepfad (ADR 0110 Punkt 1). `aspect_ratio` steht auf ALLEN, nicht nur auf dem
    der Rasteransicht - ein je Abfragemodus verschiedenes `PhotoOut` waere eine zweite,
    driftende Abbildung desselben Fotos."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 2)
    winner.aspect_ratio = 1.5
    await db_session.commit()

    gruppe = (await authenticated_api_client.get(_url(project.id, winner.id))).json()

    nach_id = {item["photo"]["id"]: item["photo"] for item in gruppe["items"]}
    assert nach_id[winner.id]["aspect_ratio"] == 1.5
    # `null` ist ein regulaerer Zustand und erzeugt auch hier keinen Fehler.
    assert nach_id[losers[0].id]["aspect_ratio"] is None
