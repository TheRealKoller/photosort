"""`POST /projects/{project_id}/draft/exchange/undo` - das Rueckgaengig nach einem Tausch als EIN
atomarer Schreibvorgang (Spec 0558, ADR 0130).

Der Client nennt dieselben beiden Ids wie beim Tausch und die beiden Vorzustaende. Der Endpunkt
bindet beide Ids wortgleich wie der Tausch (S5), prueft danach die Vorbedingung "aktuell
`photo_id` = `album_worthy`, `replaced_photo_id` = `rejected`" (S7) und schreibt beide Zeilen samt
EINEM Gegenereignis in einer Transaktion.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import FeedbackEventKind, PhotoRanking, RatingStatus
from tests.test_api_draft_exchange import _MAX_ALLOWED_ID, _build_draft, _Draft, _events, _ratings

_REFUSAL = (
    "Beide Bilder muessen zum selben Ereignis des juengsten Vorschlagslaufs dieses Projekts "
    "gehoeren."
)


def _undo_url(project_id: int | str) -> str:
    return f"/projects/{project_id}/draft/exchange/undo"


def _exchange_url(project_id: int) -> str:
    return f"/projects/{project_id}/draft/exchange"


def _body(
    photo_id: int,
    replaced_photo_id: int,
    photo_previous_status: str | None = None,
    replaced_previous_status: str | None = None,
) -> dict[str, Any]:
    return {
        "photo_id": photo_id,
        "replaced_photo_id": replaced_photo_id,
        "photo_previous_status": photo_previous_status,
        "replaced_previous_status": replaced_previous_status,
    }


async def _propose(session: AsyncSession, draft: _Draft, photo_id: int) -> None:
    await session.execute(
        update(PhotoRanking)
        .where(
            PhotoRanking.criterion_scoring_run_id == draft.run_id,
            PhotoRanking.photo_id == photo_id,
        )
        .values(selection_position=1)
    )
    await session.commit()


async def _exchanged(client: httpx.AsyncClient, session: AsyncSession) -> tuple[_Draft, int, int]:
    """Ein Projekt, in dem Foto 1 gegen das vorgeschlagene Foto 0 getauscht wurde."""
    draft = await _build_draft(session)
    alternative, replaced = draft.photo_ids[1], draft.photo_ids[0]
    await _propose(session, draft, replaced)
    response = await client.post(
        _exchange_url(draft.project_id),
        json={"photo_id": alternative, "replaced_photo_id": replaced},
    )
    assert response.status_code == 200
    return draft, alternative, replaced


class TestAuth:
    async def test_it_rejects_a_missing_token(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S1: Der eigene, pfadbenannte 401-Nachweis. Ein vergessener `current_user`-Parameter
        waere ein unauthentifizierter Schreibzugriff auf zwei Bewertungszeilen."""
        draft = await _build_draft(db_session)

        response = await api_client.post(
            _undo_url(draft.project_id), json=_body(draft.photo_ids[1], draft.photo_ids[0])
        )

        assert response.status_code == 401
        assert await _ratings(db_session) == {}
        assert await _events(db_session) == []


class TestTheRequestBody:
    """S6: genau vier Felder, die Vorzustaende ein geschlossener Vorrat ohne Vorgabewert."""

    @pytest.mark.parametrize(
        "extra",
        [
            pytest.param({"user_id": 2}, id="user_id"),
            pytest.param({"event_id": 1}, id="event_id"),
            pytest.param({"weight": 9.0}, id="weight"),
            pytest.param({"kind": "exchanged"}, id="kind"),
            pytest.param({"criterion_scoring_run_id": 1}, id="criterion_scoring_run_id"),
            pytest.param({"favorite": True}, id="favorite"),
        ],
    )
    async def test_an_additional_field_is_refused(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        extra: dict[str, object],
    ) -> None:
        draft, alternative, replaced = await _exchanged(authenticated_api_client, db_session)
        before = await _ratings(db_session)

        response = await authenticated_api_client.post(
            _undo_url(draft.project_id), json={**_body(alternative, replaced), **extra}
        )

        assert response.status_code == 422
        assert await _ratings(db_session) == before

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            pytest.param("photo_previous_status", "album_worthy", id="photo-album_worthy"),
            pytest.param("photo_previous_status", "favorite", id="photo-fremd"),
            pytest.param("replaced_previous_status", "rejected", id="replaced-rejected"),
            pytest.param("replaced_previous_status", "", id="replaced-leer"),
        ],
    )
    async def test_a_previous_status_outside_its_closed_set_is_refused(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        field: str,
        value: str,
    ) -> None:
        """Ein offener Vorrat liesse die Wiederherstellung Zustaende schreiben, die kein Tausch
        erzeugt hat."""
        draft, alternative, replaced = await _exchanged(authenticated_api_client, db_session)

        response = await authenticated_api_client.post(
            _undo_url(draft.project_id), json={**_body(alternative, replaced), field: value}
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("missing", ["photo_previous_status", "replaced_previous_status"])
    async def test_a_previous_status_has_no_default(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, missing: str
    ) -> None:
        """Ein Default `None` machte ein vergessenes Feld zu einer stillen Ruecknahme."""
        draft, alternative, replaced = await _exchanged(authenticated_api_client, db_session)
        body = _body(alternative, replaced)
        del body[missing]

        response = await authenticated_api_client.post(_undo_url(draft.project_id), json=body)

        assert response.status_code == 422

    @pytest.mark.parametrize("value", [0, -1, _MAX_ALLOWED_ID + 1, 2**63 + 1])
    async def test_an_id_outside_the_bounds_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, value: int
    ) -> None:
        draft, _alternative, replaced = await _exchanged(authenticated_api_client, db_session)

        response = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(value, replaced)
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("project_id", ["0", "-1", str(_MAX_ALLOWED_ID + 1)])
    async def test_the_project_id_is_bounded(
        self, authenticated_api_client: httpx.AsyncClient, project_id: str
    ) -> None:
        response = await authenticated_api_client.post(_undo_url(project_id), json=_body(1, 2))

        assert response.status_code == 422


class TestTheRefusals:
    """S5: dieselbe Bindung wie der Tausch, VOR der Vorbedingung."""

    async def test_an_unknown_project_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        response = await authenticated_api_client.post(_undo_url(999999), json=_body(1, 2))

        assert response.status_code == 404

    async def test_the_same_photo_on_both_sides_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        draft, alternative, _replaced = await _exchanged(authenticated_api_client, db_session)

        response = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(alternative, alternative)
        )

        assert response.status_code == 422
        assert response.json()["detail"] == _REFUSAL

    async def test_two_photos_from_different_events_are_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        draft, alternative, _replaced = await _exchanged(authenticated_api_client, db_session)

        response = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(alternative, draft.photo_ids[3])
        )

        assert response.status_code == 422
        assert response.json()["detail"] == _REFUSAL

    async def test_a_project_without_a_successful_run_is_a_422(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        from photosort.models import CriterionScoringRun, ScanStatus

        draft, alternative, replaced = await _exchanged(authenticated_api_client, db_session)
        await db_session.execute(
            update(CriterionScoringRun)
            .where(CriterionScoringRun.id == draft.run_id)
            .values(status=ScanStatus.FAILED)
        )
        await db_session.commit()

        response = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(alternative, replaced)
        )

        assert response.status_code == 422
        assert response.json()["detail"] == _REFUSAL

    async def test_a_foreign_and_an_unknown_id_are_indistinguishable_and_precede_the_check(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Stuende die Vorbedingung vorn, unterschiede die Antwort eine unbekannte Id (`409`, keine
        eigene Zeile) von einer projektfremden - das Existenz-Orakel, das S14 der Spec 0432
        ausschliesst. Die fremde Id traegt deshalb eine eigene `album_worthy`-Zeile, die die
        Vorbedingung erfuellte."""
        draft, _alternative, replaced = await _exchanged(authenticated_api_client, db_session)
        theirs = await _build_draft(db_session, name="Fremdes Projekt")
        response = await authenticated_api_client.put(
            f"/photos/{theirs.photo_ids[1]}/rating", json={"status": "album_worthy"}
        )
        assert response.status_code == 200
        before_ratings = await _ratings(db_session)
        before_events = len(await _events(db_session))

        foreign = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(theirs.photo_ids[1], replaced)
        )
        unknown = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(888888, replaced)
        )

        assert foreign.status_code == unknown.status_code == 422
        assert foreign.json()["detail"] == unknown.json()["detail"] == _REFUSAL
        assert await _ratings(db_session) == before_ratings
        assert len(await _events(db_session)) == before_events


class TestThePrecondition:
    """S7: Hat sich der Zustand eines der beiden Fotos seit dem Tausch geaendert, lehnt der Server
    mit `409` ab und schreibt nichts - je Seite einzeln."""

    @pytest.mark.parametrize("side", ["photo", "replaced"])
    async def test_a_changed_side_is_a_409_without_any_write(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, side: str
    ) -> None:
        draft, alternative, replaced = await _exchanged(authenticated_api_client, db_session)
        if side == "photo":
            changed = await authenticated_api_client.delete(f"/photos/{alternative}/rating")
        else:
            changed = await authenticated_api_client.put(
                f"/photos/{replaced}/rating", json={"status": "album_worthy"}
            )
        assert changed.status_code == 200
        before_ratings = await _ratings(db_session)
        before_events = len(await _events(db_session))

        response = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(alternative, replaced)
        )

        assert response.status_code == 409
        assert "album_worthy" not in response.text and "rejected" not in response.text
        assert await _ratings(db_session) == before_ratings
        assert len(await _events(db_session)) == before_events

    async def test_a_repeated_undo_is_a_409(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Doppelklick, zweiter Tab: Die Vorbedingung faengt die Wiederholung nach Abschluss ab."""
        draft, alternative, replaced = await _exchanged(authenticated_api_client, db_session)

        first = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(alternative, replaced)
        )
        second = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(alternative, replaced)
        )

        assert (first.status_code, second.status_code) == (200, 409)

    async def test_the_other_users_rows_do_not_decide(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Vorbedingung liest ausschliesslich die eigenen Zeilen: Der andere Nutzer hat die
        Lage umgekehrt bewertet, das Rueckgaengig gelingt trotzdem und laesst seine Zeilen
        stehen."""
        from photosort.models import Rating, User
        from photosort.security import hash_password

        draft, alternative, replaced = await _exchanged(authenticated_api_client, db_session)
        other = User(username="other-user", password_hash=hash_password("x"))
        db_session.add(other)
        await db_session.flush()
        db_session.add_all(
            [
                Rating(photo_id=alternative, user_id=other.id, status=RatingStatus.REJECTED),
                Rating(photo_id=replaced, user_id=other.id, status=RatingStatus.ALBUM_WORTHY),
            ]
        )
        await db_session.commit()
        other_id = other.id

        response = await authenticated_api_client.post(
            _undo_url(draft.project_id), json=_body(alternative, replaced)
        )

        assert response.status_code == 200
        db_session.expire_all()
        rows = (
            (await db_session.execute(Rating.__table__.select().where(Rating.user_id == other_id)))
            .mappings()
            .all()
        )
        assert {(row["photo_id"], row["status"]) for row in rows} == {
            (alternative, RatingStatus.REJECTED),
            (replaced, RatingStatus.ALBUM_WORTHY),
        }


class TestTheRestoration:
    @pytest.mark.parametrize("favorite", [False, True], ids=["ohne-favorit", "mit-favorit"])
    @pytest.mark.parametrize(
        ("photo_previous", "replaced_previous"),
        [
            pytest.param(None, None, id="unberuehrt-gegen-vorschlag"),
            pytest.param(None, "album_worthy", id="unberuehrt-gegen-aufgenommen"),
            pytest.param("rejected", None, id="gestrichen-gegen-vorschlag"),
            pytest.param("rejected", "album_worthy", id="gestrichen-gegen-aufgenommen"),
        ],
    )
    async def test_undo_restores_the_snapshot_before_the_exchange(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        photo_previous: str | None,
        replaced_previous: str | None,
        favorite: bool,
    ) -> None:
        """Schnappschussgleichheit von `GET /album-draft` und den eigenen Zeilen samt `favorite`
        vor dem Tausch und nach dem Rueckgaengig - dazu genau EIN zusaetzliches Tauschereignis in
        Gegenrichtung, und die Antwort traegt beide geschriebenen Zeilen."""
        client = authenticated_api_client
        draft = await _build_draft(db_session)
        alternative, replaced = draft.photo_ids[1], draft.photo_ids[0]
        await _propose(db_session, draft, replaced)
        if replaced_previous is not None:
            await client.put(f"/photos/{replaced}/rating", json={"status": replaced_previous})
        if photo_previous is not None:
            await client.put(f"/photos/{alternative}/rating", json={"status": photo_previous})
        if favorite:
            for photo_id in (alternative, replaced):
                await client.put(f"/photos/{photo_id}/favorite", json={"favorite": True})

        snapshot = (await client.get(f"/projects/{draft.project_id}/album-draft")).json()
        rows_before = await _ratings(db_session)
        events_before = len(await _events(db_session))

        exchange = await client.post(
            _exchange_url(draft.project_id),
            json={"photo_id": alternative, "replaced_photo_id": replaced},
        )
        assert exchange.status_code == 200
        response = await client.post(
            _undo_url(draft.project_id),
            json=_body(alternative, replaced, photo_previous, replaced_previous),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["photo"]["photo_id"] == alternative
        assert body["photo"]["status"] == photo_previous
        assert body["photo"]["favorite"] is favorite
        assert body["replaced"]["photo_id"] == replaced
        assert body["replaced"]["status"] == replaced_previous
        assert body["replaced"]["favorite"] is favorite
        assert await _ratings(db_session) == rows_before
        assert (await client.get(f"/projects/{draft.project_id}/album-draft")).json() == snapshot

        events = await _events(db_session)
        assert len(events) == events_before + 2
        assert [event.kind for event in events[-2:]] == [FeedbackEventKind.EXCHANGED] * 2
        assert (events[-1].photo_id, events[-1].replaced_photo_id) == (replaced, alternative)
        assert events[-1].event_id == draft.event_id


class TestTheAtomicity:
    async def test_a_failing_second_write_leaves_the_exchanged_state_untouched(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """S7: beide Zeilen und das Gegenereignis oder gar nichts. Beide Vorzustaende fuehren hier
        zu einem `flush`, der zweite scheitert."""
        client = authenticated_api_client
        draft = await _build_draft(db_session)
        alternative, replaced = draft.photo_ids[1], draft.photo_ids[0]
        await client.put(f"/photos/{replaced}/rating", json={"status": "album_worthy"})
        await client.put(f"/photos/{alternative}/rating", json={"status": "rejected"})
        await client.post(
            _exchange_url(draft.project_id),
            json={"photo_id": alternative, "replaced_photo_id": replaced},
        )
        rows_before = await _ratings(db_session)
        events_before = len(await _events(db_session))

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
            response = await client.post(
                _undo_url(draft.project_id),
                json=_body(alternative, replaced, "rejected", "album_worthy"),
            )
        finally:
            monkeypatch.setattr(AsyncSession, "flush", original_flush)

        assert calls["count"] >= 2, "der zweite Schreibvorgang wurde gar nicht erreicht"
        assert response.status_code != 200
        assert await _ratings(db_session) == rows_before
        assert len(await _events(db_session)) == events_before
