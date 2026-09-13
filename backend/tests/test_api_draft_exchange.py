"""`POST /projects/{project_id}/draft/exchange` - der Austausch als EIN atomarer Schreibvorgang
(Spec 0432, ADR 0100 Punkt 3).

"B statt A" ist die Aussage; die beiden Bilder fuer sich tragen sie nicht. Zwei getrennte Aufrufe
liessen sich nachtraeglich nur ueber eine Heuristik zu einem Paar zusammenfuegen, und die stille
Fehlpaarung zweier unabhaengiger Handgriffe waere an keinem Ergebnis erkennbar.

VIER AUSSAGEN BRECHEN OHNE EIGENEN FALL STILL:

* S1: `photos.router` traegt keine router-weite `dependencies`-Liste und hat deshalb KEIN
  Vollstaendigkeitsnetz. Ein hier vergessener `current_user`-Parameter waere still oeffentlich -
  ein unauthentifizierter Schreibzugriff, der ZWEI Bewertungszeilen aendert. Der 401-Fall ist
  Pflicht.
* S2: Die Projektbindung laeuft ueber die RANGZEILE des juengsten erfolgreichen Laufs, nie ueber
  `session.get(Photo, …)` mit nachgelagerter Projektpruefung. `PhotoRanking` traegt keine
  `project_id`, und ohne das Laufpraedikat identifiziert eine Id aus Projekt B unter
  `/projects/A/…` eindeutig fremde Zeilen: Der Endpunkt liefe nicht in eine erkennbar falsche
  Menge, sondern TAUSCHTE KOHAERENT ZWEI BILDER EINES FREMDEN PROJEKTS.
* S4: Das Eingabeschema traegt genau zwei Felder. `weight` waere der Wert, mit dem ein Aufrufer
  die eigene Korrektur in der global wirkenden Gewichtsableitung ueberproportional zaehlen liesse.
* S5: Ein Austausch ist EINE Transaktion. Zwei getrennte Commits liessen den halb ausgefuehrten
  Austausch bestehen - jetzt zusaetzlich mit einem Ereignis, das ihn als vollstaendig ausweist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    Event,
    FeedbackEvent,
    FeedbackEventKind,
    Photo,
    PhotoAlbumSuitability,
    PhotoRanking,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)

_MAX_ALLOWED_ID = 1_000_000_000


def _url(project_id: int) -> str:
    return f"/projects/{project_id}/draft/exchange"


@dataclass(frozen=True)
class _Draft:
    project_id: int
    run_id: int
    event_id: int
    other_event_id: int
    photo_ids: list[int]
    """Drei Fotos im ersten Event, eines im zweiten."""


async def _build_draft(session: AsyncSession, *, name: str = "Costa Rica") -> _Draft:
    """Ein Projekt mit erfolgreichem Lauf und ZWEI Events - das zweite traegt den Fall "beide
    Fotos im selben Event" (S3), der ohne ein zweites Event gar nicht pruefbar waere."""
    project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
    session.add(project)
    await session.flush()

    now = datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    photos = [
        Photo(
            project_id=project.id,
            relative_path=f"{name}-{index}.jpg",
            etag=f"etag-{name}-{index}",
            content_length=100,
            taken_at=now,
            taken_at_original=now,
            last_modified=now,
        )
        for index in range(4)
    ]
    session.add_all(photos)
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()

    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()

    events = [
        Event(criterion_scoring_run_id=run.id, position=position, started_at=now, ended_at=now)
        for position in (1, 2)
    ]
    session.add_all(events)
    await session.flush()

    for index, photo in enumerate(photos):
        session.add(
            PhotoAlbumSuitability(
                photo_id=photo.id, level=4 - index, provider="test", computed_at=now
            )
        )
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo.id,
                event_id=events[0].id if index < 3 else events[1].id,
                rank_score=0.9 - index * 0.1,
                rank_position=index + 1,
            )
        )
    await session.commit()

    return _Draft(
        project_id=project.id,
        run_id=run.id,
        event_id=events[0].id,
        other_event_id=events[1].id,
        photo_ids=[photo.id for photo in photos],
    )


async def _events(session: AsyncSession) -> list[FeedbackEvent]:
    session.expire_all()
    return list(
        (await session.execute(select(FeedbackEvent).order_by(FeedbackEvent.id))).scalars().all()
    )


async def _ratings(session: AsyncSession) -> dict[int, tuple[RatingStatus | None, bool]]:
    session.expire_all()
    rows = (await session.execute(select(Rating))).scalars().all()
    return {row.photo_id: (row.status, row.favorite) for row in rows}


class TestAuth:
    async def test_it_rejects_a_missing_token(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S1: Der eigene, pfadbenannte 401-Nachweis. Fuer `photos.router` gibt es kein
        Vollstaendigkeitsnetz - ein vergessener `current_user`-Parameter waere hier still
        oeffentlich, und der Endpunkt aendert ZWEI Bewertungszeilen."""
        draft = await _build_draft(db_session)

        response = await api_client.post(
            _url(draft.project_id),
            json={"photo_id": draft.photo_ids[1], "replaced_photo_id": draft.photo_ids[0]},
        )

        assert response.status_code == 401
        assert await _ratings(db_session) == {}
        assert await _events(db_session) == []


class TestTheRequestBody:
    """S4: Das Eingabeschema traegt GENAU zwei Felder. Massenzuweisung ist strukturell
    ausgeschlossen, nicht im Handler herausgefiltert."""

    @pytest.mark.parametrize(
        "extra",
        [
            pytest.param({"weight": 99.0}, id="weight"),
            pytest.param({"user_id": 2}, id="user_id"),
            pytest.param({"event_id": 1}, id="event_id"),
            pytest.param({"kind": "photo_included"}, id="kind"),
            pytest.param({"criterion_scoring_run_id": 1}, id="criterion_scoring_run_id"),
            pytest.param({"motif_strength": 0.5}, id="motif_strength"),
        ],
    )
    async def test_an_additional_field_is_refused(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        extra: dict[str, object],
    ) -> None:
        """`weight` wiegt am schwersten: Es ist der einzige Wert, mit dem ein Aufrufer die eigene
        Korrektur in der GLOBAL wirkenden Gewichtsableitung ueberproportional zaehlen liesse."""
        draft = await _build_draft(db_session)

        response = await authenticated_api_client.post(
            _url(draft.project_id),
            json={
                "photo_id": draft.photo_ids[1],
                "replaced_photo_id": draft.photo_ids[0],
                **extra,
            },
        )

        assert response.status_code == 422
        assert await _events(db_session) == []

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param(0, id="unter-der-untergrenze"),
            pytest.param(-1, id="negativ"),
            pytest.param(_MAX_ALLOWED_ID + 1, id="ueber-der-obergrenze"),
            pytest.param(2**63 + 1, id="jenseits-von-2-hoch-63"),
        ],
    )
    async def test_an_id_outside_the_declared_bounds_is_a_422_and_never_a_500(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, value: int
    ) -> None:
        """S4: Ein unbeschraenkter Pydantic-`int` erzeugt unter SQLite jenseits von 2^63 einen
        `OverflowError` und damit `500` statt `422`."""
        draft = await _build_draft(db_session)

        response = await authenticated_api_client.post(
            _url(draft.project_id),
            json={"photo_id": value, "replaced_photo_id": draft.photo_ids[0]},
        )

        assert response.status_code == 422

    async def test_a_missing_field_is_refused(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        draft = await _build_draft(db_session)

        response = await authenticated_api_client.post(
            _url(draft.project_id), json={"photo_id": draft.photo_ids[1]}
        )

        assert response.status_code == 422


class TestTheRefusals:
    """L3: Die drei Ablehnungsgruende, jeder mit seinem eigenen Fall."""

    async def test_an_unknown_project_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        draft = await _build_draft(db_session)

        response = await authenticated_api_client.post(
            _url(999999),
            json={"photo_id": draft.photo_ids[1], "replaced_photo_id": draft.photo_ids[0]},
        )

        assert response.status_code == 404

    async def test_the_same_photo_on_both_sides_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein Bild gegen sich selbst zu tauschen ist keine Aussage. Ohne diese Pruefung
        entstuende eine Ereigniszeile, deren beide Verweise dasselbe Foto benennen - in der
        Ableitung ein Paar, das auf jedem Kriterium Gleichstand zeigt und die Fallzahl
        verwaessert."""
        draft = await _build_draft(db_session)

        response = await authenticated_api_client.post(
            _url(draft.project_id),
            json={"photo_id": draft.photo_ids[0], "replaced_photo_id": draft.photo_ids[0]},
        )

        assert response.status_code == 422
        assert await _events(db_session) == []

    async def test_a_photo_of_another_project_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S2, DER tragende Fall: Die Id gehoert zu einem ANDEREN Projekt und ist dort voll
        gueltig - Rangzeile, Event, Modellstufe. Eine Umsetzung ueber `session.get(Photo, …)` mit
        nachgelagerter Projektpruefung faende sie und taeuschte Kohaerenz vor."""
        mine = await _build_draft(db_session)
        theirs = await _build_draft(db_session, name="Fremdes Projekt")

        response = await authenticated_api_client.post(
            _url(mine.project_id),
            json={"photo_id": theirs.photo_ids[1], "replaced_photo_id": mine.photo_ids[0]},
        )

        assert response.status_code == 422
        assert await _ratings(db_session) == {}
        assert await _events(db_session) == []

    async def test_the_refusal_of_an_unknown_and_of_a_foreign_id_is_indistinguishable(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S14: Verschiedene Antworten machten den Endpunkt zum EXISTENZ-ORAKEL ueber fremde
        Foto-Ids - geprueft wird deshalb Status UND Text."""
        mine = await _build_draft(db_session)
        theirs = await _build_draft(db_session, name="Fremdes Projekt")

        foreign = await authenticated_api_client.post(
            _url(mine.project_id),
            json={"photo_id": theirs.photo_ids[1], "replaced_photo_id": mine.photo_ids[0]},
        )
        unknown = await authenticated_api_client.post(
            _url(mine.project_id),
            json={"photo_id": 888888, "replaced_photo_id": mine.photo_ids[0]},
        )

        assert foreign.status_code == unknown.status_code == 422
        assert foreign.json()["detail"] == unknown.json()["detail"]

    async def test_two_photos_from_different_events_are_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S3: Ohne diese Bedingung paart ein Client zwei Bilder verschiedener Events. Die Zeile
        truege dann die `event_id` des ersetzten Fotos, und die Ableitung rechnete ueber eine
        Gegenueberstellung, die es nie gab - ohne Fehler und an keinem Ergebnis erkennbar."""
        draft = await _build_draft(db_session)

        response = await authenticated_api_client.post(
            _url(draft.project_id),
            json={"photo_id": draft.photo_ids[3], "replaced_photo_id": draft.photo_ids[0]},
        )

        assert response.status_code == 422
        assert await _ratings(db_session) == {}
        assert await _events(db_session) == []

    async def test_a_project_without_a_successful_run_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ohne erfolgreichen Lauf gibt es keine Rangzeile, ueber die die Projektbindung liefe -
        und damit keinen Entwurf, in dem etwas auszutauschen waere."""
        project = Project(name="Ohne Lauf", opencloud_drive_id="d", opencloud_path="/x")
        db_session.add(project)
        await db_session.flush()
        now = datetime(2023, 1, 1)
        photos = [
            Photo(
                project_id=project.id,
                relative_path=f"{index}.jpg",
                etag=f"e{index}",
                content_length=1,
                taken_at=now,
                taken_at_original=now,
                last_modified=now,
            )
            for index in range(2)
        ]
        db_session.add_all(photos)
        await db_session.commit()

        response = await authenticated_api_client.post(
            project_url := _url(project.id),
            json={"photo_id": photos[1].id, "replaced_photo_id": photos[0].id},
        )

        assert project_url
        assert response.status_code == 422
        assert await _events(db_session) == []


class TestTheSuccessfulExchange:
    async def test_it_writes_both_rating_rows_and_answers_with_both(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """L2: Der Aufruf antwortet mit dem GESCHRIEBENEN Zustand beider Bewertungszeilen, damit
        die Oberflaeche wie bisher fortschreibt statt neu zu laden."""
        draft = await _build_draft(db_session)
        taken_id, struck_id = draft.photo_ids[1], draft.photo_ids[0]

        response = await authenticated_api_client.post(
            _url(draft.project_id),
            json={"photo_id": taken_id, "replaced_photo_id": struck_id},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["taken"]["photo_id"] == taken_id
        assert body["taken"]["status"] == "album_worthy"
        assert body["struck"]["photo_id"] == struck_id
        assert body["struck"]["status"] == "rejected"
        own_user_id = (
            await db_session.execute(select(User.id).order_by(User.id).limit(1))
        ).scalar_one()
        assert body["taken"]["user_id"] == body["struck"]["user_id"] == own_user_id

        assert await _ratings(db_session) == {
            taken_id: (RatingStatus.ALBUM_WORTHY, False),
            struck_id: (RatingStatus.REJECTED, False),
        }

    async def test_it_records_exactly_one_event_with_both_photo_references(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """L2, und die Assertion ist `== 1` und nicht "es gibt ein `exchanged`": Sonst bliebe das
        ausgeschlossene zusaetzliche Streich-/Aufnahme-Paar unsichtbar und jeder Austausch zaehlte
        DREIFACH."""
        draft = await _build_draft(db_session)
        taken_id, struck_id = draft.photo_ids[1], draft.photo_ids[0]

        await authenticated_api_client.post(
            _url(draft.project_id),
            json={"photo_id": taken_id, "replaced_photo_id": struck_id},
        )

        rows = await _events(db_session)
        assert len(rows) == 1
        stored = rows[0]
        assert stored.kind is FeedbackEventKind.EXCHANGED
        assert stored.photo_id == taken_id
        assert stored.replaced_photo_id == struck_id
        assert stored.project_id == draft.project_id

    async def test_the_event_freezes_run_event_levels_and_qualities_of_both_photos(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """L4 und S3: `event_id` kommt aus der RANGZEILE, nie aus dem Body."""
        draft = await _build_draft(db_session)

        await authenticated_api_client.post(
            _url(draft.project_id),
            json={"photo_id": draft.photo_ids[1], "replaced_photo_id": draft.photo_ids[0]},
        )

        stored = (await _events(db_session))[0]
        assert stored.criterion_scoring_run_id == draft.run_id
        assert stored.event_id == draft.event_id
        assert (stored.level, stored.replaced_level) == (3, 4)
        assert stored.quality == pytest.approx(0.8)
        assert stored.replaced_quality == pytest.approx(0.9)

    async def test_a_photo_without_a_model_level_still_exchanges(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """L4: Die eingefrorenen Zahlen sind nullbar. Ein Foto ohne Modellbewertung haelt den
        Austausch nicht auf - das Paar ist in der Diagnose spaeter nur `unbestimmt`."""
        draft = await _build_draft(db_session)
        await db_session.execute(
            select(PhotoAlbumSuitability).where(
                PhotoAlbumSuitability.photo_id == draft.photo_ids[1]
            )
        )
        suitability = await db_session.get(PhotoAlbumSuitability, draft.photo_ids[1])
        assert suitability is not None
        await db_session.delete(suitability)
        await db_session.commit()

        response = await authenticated_api_client.post(
            _url(draft.project_id),
            json={"photo_id": draft.photo_ids[1], "replaced_photo_id": draft.photo_ids[0]},
        )

        assert response.status_code == 200
        stored = (await _events(db_session))[0]
        assert stored.level is None
        assert stored.replaced_level == 4

    async def test_the_exchange_leaves_the_favorite_markers_untouched(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Austausch laeuft durch DIESELBE Schreibstelle wie die drei Bestandsendpunkte und
        erbt damit deren Zusage: Er schreibt genau sein Feld."""
        draft = await _build_draft(db_session)
        taken_id, struck_id = draft.photo_ids[1], draft.photo_ids[0]
        await authenticated_api_client.put(f"/photos/{struck_id}/favorite", json={"favorite": True})

        await authenticated_api_client.post(
            _url(draft.project_id),
            json={"photo_id": taken_id, "replaced_photo_id": struck_id},
        )

        assert await _ratings(db_session) == {
            taken_id: (RatingStatus.ALBUM_WORTHY, False),
            struck_id: (RatingStatus.REJECTED, True),
        }

    async def test_the_reverse_exchange_adds_a_second_event_and_deletes_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ADR 0100 Punkt 3: Die Umkehr eines Austauschs ist ein WEITERER Austausch mit eigenem
        Ereignis. Sie loescht nichts - es zaehlt, DASS korrigiert wurde. Nur die Fallzahl trennt
        das von einer Umsetzung, die die Umkehr als Ruecknahme behandelt."""
        draft = await _build_draft(db_session)
        first, second = draft.photo_ids[0], draft.photo_ids[1]

        await authenticated_api_client.post(
            _url(draft.project_id), json={"photo_id": second, "replaced_photo_id": first}
        )
        await authenticated_api_client.post(
            _url(draft.project_id), json={"photo_id": first, "replaced_photo_id": second}
        )

        rows = await _events(db_session)
        assert len(rows) == 2
        assert [row.kind for row in rows] == [FeedbackEventKind.EXCHANGED] * 2
        assert [(row.photo_id, row.replaced_photo_id) for row in rows] == [
            (second, first),
            (first, second),
        ]


class TestTheAtomicity:
    async def test_a_failing_second_write_leaves_neither_row_nor_event_behind(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """S5 und L2, DER tragende Fall dieser Datei, mit drei Assertionen.

        Heute sind es zwei Aufrufe, von denen der zweite fehlschlagen kann und einen halb
        ausgefuehrten Austausch hinterlaesst. Committete die Schreibstelle weiterhin selbst, waere
        die erste Zeile nach ihrem Commit unwiderruflich geschrieben - und ein `record`-Parameter
        allein aenderte daran nichts."""
        draft = await _build_draft(db_session)
        taken_id, struck_id = draft.photo_ids[1], draft.photo_ids[0]

        original_flush = AsyncSession.flush
        calls = {"count": 0}

        async def _failing_on_the_second(
            self: AsyncSession, *args: object, **kwargs: object
        ) -> None:
            calls["count"] += 1
            if calls["count"] == 2:
                raise IntegrityError("UPDATE", {}, Exception("UNIQUE constraint failed"))
            await original_flush(self, *args, **kwargs)

        monkeypatch.setattr(AsyncSession, "flush", _failing_on_the_second)
        try:
            response = await authenticated_api_client.post(
                _url(draft.project_id),
                json={"photo_id": taken_id, "replaced_photo_id": struck_id},
            )
        finally:
            monkeypatch.setattr(AsyncSession, "flush", original_flush)

        assert calls["count"] >= 2, "der zweite Schreibvorgang wurde gar nicht erreicht"
        assert response.status_code != 200
        assert await _ratings(db_session) == {}
        assert await _events(db_session) == []
