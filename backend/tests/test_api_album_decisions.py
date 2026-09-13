"""specs/features/0431-endauswahl-gemeinsam.md, PR 1 Schritt 3 - der Schreibendpunkt der
gemeinsamen Entscheidung.

Er ist der ERSTE Schreibendpunkt des Projekts OHNE `current_user`, und genau das macht ihn
besonders: Seine Authentifizierung ist an der Funktionssignatur nicht sichtbar - es gibt keinen
`current_user`, dessen Fehlen auffiele. Der Torwaechter haengt deshalb am ROUTER, der Router steht
in `test_auth_guard.py::_protected_router_operations()`, UND es gibt zusaetzlich den eigenen,
pfadbenannten 401-Fall hier (Auflage S1). Die Doppelung traegt, weil der Listeneintrag weder sein
eigenes Vergessen noch eine spaetere Verschiebung des Endpunkts nach `api/photos.py` ueberlebt.

Vier Aussagen brechen ohne eigenen Fall still:

* S4: Der Body erzwingt dieselbe Ausdruecklichkeit wie die Spalte. Ein aus Bequemlichkeit
  gesetzter Vorgabewert `False` naehme bei einem leeren Body das Foto aus dem Album - mit `200`
  und ohne dass eine Anzeige das als falsch ausweist.
* S5: Die Antwort ist der PERSISTIERTE Zustand, nie die Rueckspiegelung des Bodys. Die Oberflaeche
  schreibt genau diesen Wert fort und laedt nicht neu.
* S6: Ein gleichzeitiger Doppeldruck laeuft in den Primaerschluessel und darf keine `500` werden.
* Es gibt KEIN `DELETE`: "wieder strittig werden" ist kein Zustand, den die Story kennt.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.feedback_log import FINAL_DECISION_WEIGHT
from photosort.models import (
    FeedbackEvent,
    FeedbackEventKind,
    FinalSelectionDecision,
    Photo,
    Project,
    User,
)
from photosort.security import create_access_token, hash_password


def _url(photo_id: int | str) -> str:
    return f"/photos/{photo_id}/album-decision"


async def _make_photo(session: AsyncSession, name: str = "Costa Rica") -> Photo:
    project = Project(
        name=name, opencloud_drive_id="drive-1", opencloud_path=f"/{name.replace(' ', '')}"
    )
    session.add(project)
    await session.flush()
    now = datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    photo = Photo(
        project_id=project.id,
        relative_path=f"{name}/img001.jpg",
        etag=f"etag-{name}",
        content_length=1,
        taken_at=now,
        taken_at_original=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _second_user_token(session: AsyncSession, username: str = "partnerin") -> str:
    user = User(username=username, password_hash=hash_password("irrelevant"))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return create_access_token(user)


async def _decisions(session: AsyncSession) -> list[FinalSelectionDecision]:
    return list((await session.execute(select(FinalSelectionDecision))).scalars().all())


class TestAuth:
    async def test_the_put_rejects_a_missing_token(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S1, der EIGENE pfadbenannte Nachweis. Er ist die einzige Pruefung, die eine
        Verschiebung des Endpunkts in einen Router ohne `dependencies`-Liste ueberlebt - dort
        waere er still oeffentlich: ein unauthentifizierter Schreibzugriff, der die Bildmenge des
        Albums aendert."""
        photo = await _make_photo(db_session)

        response = await api_client.put(_url(photo.id), json={"included": True})

        assert response.status_code == 401
        assert await _decisions(db_session) == []

    async def test_the_gate_closes_before_the_body_is_validated(
        self, api_client: httpx.AsyncClient
    ) -> None:
        """Die Router-Dependency greift VOR der Body-Validierung - sonst antwortete der
        Vollstaendigkeitstest, der ohne Token UND ohne Body anfragt, mit `422` statt `401`."""
        response = await api_client.put(_url(1))

        assert response.status_code == 401

    async def test_the_path_id_bounds_still_let_the_completeness_test_through(
        self, api_client: httpx.AsyncClient
    ) -> None:
        """Auflage S3: Die gewaehlten Grenzen muessen den Wert `1` zulassen, den
        `_protected_router_operations()` einsetzt - sonst antwortet er `422` statt `401`, und der
        Vollstaendigkeitstest prueft die Auth gar nicht mehr."""
        response = await api_client.put(_url(1), json={"included": True})

        assert response.status_code == 401


class TestTheRequestBody:
    """Auflage S4: genau EIN Feld, pflichtig, ohne Vorgabewert und ohne `null`."""

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({}, id="leerer-body"),
            pytest.param({"included": None}, id="null"),
            pytest.param({"included": "ja"}, id="kein-boolean"),
        ],
    )
    async def test_a_body_without_an_explicit_decision_is_rejected(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        body: dict[str, object],
    ) -> None:
        """Sonst hat die Spalte keinen Vorgabewert und die API schon - und es gibt keinen Weg
        zurueck nach "unentschieden"."""
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(_url(photo.id), json=body)

        assert response.status_code == 422
        assert await _decisions(db_session) == []

    async def test_an_extra_field_does_not_reach_the_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Massenzuweisung ist strukturell ausgeschlossen: das Eingabemodell kennt kein
        `photo_id`, kein `user_id` und kein `updated_at`."""
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(
            _url(photo.id), json={"included": True, "photo_id": 999, "user_id": 42}
        )

        assert response.status_code == 200
        rows = await _decisions(db_session)
        assert [(row.photo_id, row.included) for row in rows] == [(photo.id, True)]


class TestTheUnknownPhoto:
    async def test_an_unknown_photo_id_is_a_404_without_echoing_the_value(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await _make_photo(db_session)

        response = await authenticated_api_client.put(_url(999_999), json={"included": True})

        assert response.status_code == 404
        assert "999999" not in response.text
        assert await _decisions(db_session) == []

    @pytest.mark.parametrize("photo_id", [0, -1, 10**19])
    async def test_a_path_id_outside_the_bounds_is_a_422_and_never_a_500(
        self, authenticated_api_client: httpx.AsyncClient, photo_id: int
    ) -> None:
        """Auflage S3: Ein Pydantic-`int` ist unbeschraenkt und landet direkt in
        `session.get(Photo, photo_id)`; jenseits von 2^63 wirft SQLite einen `OverflowError` und
        der Endpunkt antwortete `500` statt `404`."""
        response = await authenticated_api_client.put(_url(photo_id), json={"included": True})

        assert response.status_code == 422


class TestTheWrite:
    async def test_the_first_write_creates_exactly_one_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(_url(photo.id), json={"included": True})

        assert response.status_code == 200
        body = response.json()
        assert body["photo_id"] == photo.id
        assert body["included"] is True
        assert body["updated_at"]
        rows = await _decisions(db_session)
        assert [(row.photo_id, row.included) for row in rows] == [(photo.id, True)]

    async def test_the_response_is_the_persisted_state_and_not_an_echo_of_the_body(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S5: Ein Echo des Bodys zeigte nach einem verlorenen Wettlauf dauerhaft eine
        Zugehoerigkeit an, die so nicht gespeichert ist - sichtbar erst nach einem vollstaendigen
        Neuladen, und bis dahin entscheiden die beiden anhand einer Anzeige, die etwas anderes
        behauptet als die Datenbank."""
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(_url(photo.id), json={"included": False})

        stored = (await _decisions(db_session))[0]
        assert response.json()["included"] is stored.included
        assert response.json()["updated_at"] == stored.updated_at.isoformat()

    async def test_writing_the_opposite_value_flips_the_same_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 19: Aendern heisst den anderen Wert schreiben - es entsteht keine zweite
        Zeile und kein Verlauf."""
        photo = await _make_photo(db_session)

        await authenticated_api_client.put(_url(photo.id), json={"included": True})
        response = await authenticated_api_client.put(_url(photo.id), json={"included": False})

        assert response.status_code == 200
        assert response.json()["included"] is False
        rows = await _decisions(db_session)
        assert [(row.photo_id, row.included) for row in rows] == [(photo.id, False)]

    async def test_writing_the_same_value_twice_stays_without_consequence(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 19: Wiederholte identische Aufrufe bleiben folgenlos - `200`, weiterhin
        genau eine Zeile, derselbe Wert. Die Arbeitssicht laedt zum schnellen Durchklicken ein."""
        photo = await _make_photo(db_session)

        first = await authenticated_api_client.put(_url(photo.id), json={"included": True})
        second = await authenticated_api_client.put(_url(photo.id), json={"included": True})

        assert (first.status_code, second.status_code) == (200, 200)
        rows = await _decisions(db_session)
        assert [(row.photo_id, row.included) for row in rows] == [(photo.id, True)]

    async def test_there_is_no_delete_on_this_path(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Wieder strittig werden" ist kein Zustand, den die Story kennt. Ohne diesen Fall
        koennte ein spaeter ergaenztes `DELETE` den Zustand "unentschieden" wiederherstellen -
        und damit eine getroffene Entscheidung spurlos entfernen."""
        photo = await _make_photo(db_session)
        await authenticated_api_client.put(_url(photo.id), json={"included": True})

        response = await authenticated_api_client.delete(_url(photo.id))

        assert response.status_code == 405
        assert len(await _decisions(db_session)) == 1


class TestTheDecisionBelongsToTheProjectAndNotToAUser:
    async def test_a_write_by_one_user_reads_identically_for_the_other(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Wer angemeldet ist, spielt fuer die Wirkung der Entscheidung keine Rolle." Die Zeile
        traegt keinen Nutzerbezug, an dem sich das unterscheiden liesse."""
        photo = await _make_photo(db_session)
        other_token = await _second_user_token(db_session)

        await authenticated_api_client.put(_url(photo.id), json={"included": True})
        response = await authenticated_api_client.put(
            _url(photo.id),
            json={"included": False},
            headers={"Authorization": f"Bearer {other_token}"},
        )

        assert response.status_code == 200
        rows = await _decisions(db_session)
        assert [(row.photo_id, row.included) for row in rows] == [(photo.id, False)]

    async def test_everyone_may_change_every_decision(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)
        other_token = await _second_user_token(db_session)

        await authenticated_api_client.put(
            _url(photo.id),
            json={"included": False},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        response = await authenticated_api_client.put(_url(photo.id), json={"included": True})

        assert response.status_code == 200
        assert response.json()["included"] is True


class TestTheConcurrencyMapping:
    async def test_a_losing_race_is_resolved_on_the_existing_row_and_never_becomes_a_500(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Zusicherung 20 / Auflage S6: Zwei gleichzeitige Anfragen sehen beide "keine Zeile" und
        fuegen beide ein. Der `flush` VOR dem `commit` bringt den Primaerschluessel zum Tragen;
        danach wird die Zeile erneut gelesen und die Aenderung darauf angewandt.

        Simuliert ueber einen EINMALIG scheiternden `flush` - ein echtes Wettrennen ist in einer
        In-Memory-SQLite-Sitzung nicht herstellbar, und der Abbildungspfad ist das, was hier
        geprueft gehoert. Die Zeile ist vorher committet, damit der `rollback` des Handlers sie
        stehen laesst - genau die Lage nach einem verlorenen Wettlauf."""
        photo = await _make_photo(db_session)
        # Die Id VOR dem Aufruf festgehalten: der `rollback` des Handlers laeuft auf derselben
        # Sitzung und laesst jedes geladene Objekt expired zurueck - ein spaeterer `photo.id`
        # loeste dann einen synchronen Nachladeversuch aus (`MissingGreenlet`), der nichts ueber
        # den Endpunkt aussagte.
        photo_id = photo.id
        db_session.add(FinalSelectionDecision(photo_id=photo_id, included=False))
        await db_session.commit()

        original_flush = AsyncSession.flush
        calls = {"count": 0}

        async def _failing_once(self: AsyncSession, *args: object, **kwargs: object) -> None:
            calls["count"] += 1
            if calls["count"] == 1:
                raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))
            await original_flush(self, *args, **kwargs)

        monkeypatch.setattr(AsyncSession, "flush", _failing_once)
        try:
            response = await authenticated_api_client.put(_url(photo_id), json={"included": True})
        finally:
            monkeypatch.setattr(AsyncSession, "flush", original_flush)

        assert calls["count"] >= 2, "der IntegrityError-Zweig wurde gar nicht betreten"
        assert response.status_code == 200
        assert response.json()["included"] is True
        rows = await _decisions(db_session)
        assert [(row.photo_id, row.included) for row in rows] == [(photo_id, True)]

    async def test_an_unresolvable_integrity_error_becomes_a_409_and_never_a_500(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Die Gegenprobe: Ist nach dem `rollback` KEINE Zeile da, auf die die Aenderung
        anzuwenden waere, endet die Anfrage als `409` - nie als `500` und nie stillschweigend
        erfolgreich, ohne dass etwas geschrieben wurde."""
        photo = await _make_photo(db_session)
        original_flush = AsyncSession.flush

        async def _always_failing(self: AsyncSession, *args: object, **kwargs: object) -> None:
            raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

        monkeypatch.setattr(AsyncSession, "flush", _always_failing)
        try:
            response = await authenticated_api_client.put(_url(photo.id), json={"included": True})
        finally:
            monkeypatch.setattr(AsyncSession, "flush", original_flush)

        assert response.status_code == 409
        assert response.json()["detail"]


class TestTheRecordedJointDecision:
    """Spec 0432: Auch die gemeinsame Entscheidung ist eine Korrektur am Vorschlag - und die
    einzige, deren Ereignis KEINEN Nutzer traegt (S9)."""

    async def test_each_change_records_one_event_without_a_user(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Das Ereignis traegt `user_id IS NULL`, und das ist strukturell getragen: Dieser Router
        kennt kein `current_user`. Sich fuer das Log eines zu besorgen, fuehrte das in ADR 0099
        verworfene `decided_by` durch die Hintertuer ein - und das Log waere der Ort, an dem man
        nachsieht, wer wollte, was das Projekt entschieden hat."""
        photo = await _make_photo(db_session)
        photo_id, project_id = photo.id, photo.project_id

        await authenticated_api_client.put(_url(photo_id), json={"included": True})
        await authenticated_api_client.put(_url(photo_id), json={"included": False})

        db_session.expire_all()
        rows = (
            (await db_session.execute(select(FeedbackEvent).order_by(FeedbackEvent.id)))
            .scalars()
            .all()
        )
        assert [row.kind for row in rows] == [
            FeedbackEventKind.FINAL_DECISION_IN,
            FeedbackEventKind.FINAL_DECISION_OUT,
        ]
        assert [row.user_id for row in rows] == [None, None]
        assert [row.project_id for row in rows] == [project_id, project_id]
        assert [row.weight for row in rows] == [FINAL_DECISION_WEIGHT, FINAL_DECISION_WEIGHT]

    async def test_the_same_decision_written_again_records_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Endpunkt ist ein Upsert, und ein wiederholtes identisches `included` ist keine
        Korrektur (ADR 0100 Punkt 4). Die Arbeitssicht laedt zum schnellen Durchklicken ein - ohne
        diese Bedingung fuellte sich das Log mit Handgriffen, die nichts bewegt haben."""
        photo = await _make_photo(db_session)
        photo_id = photo.id
        await authenticated_api_client.put(_url(photo_id), json={"included": True})

        await authenticated_api_client.put(_url(photo_id), json={"included": True})
        await authenticated_api_client.put(_url(photo_id), json={"included": True})

        db_session.expire_all()
        kinds = [
            kind
            for kind in (
                await db_session.execute(select(FeedbackEvent.kind).order_by(FeedbackEvent.id))
            ).scalars()
        ]
        assert kinds == [FeedbackEventKind.FINAL_DECISION_IN]

    async def test_a_rejected_write_leaves_no_event_behind(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein unbekanntes Foto und ein Body ohne `included` erzeugen kein Ereignis. Der Eintrag
        steht hinter beiden Pruefungen - ein davor geschriebenes Ereignis behauptete eine
        Entscheidung, die es nie gab, und waere append-only nicht mehr zu entfernen."""
        photo = await _make_photo(db_session)
        photo_id = photo.id

        unknown = await authenticated_api_client.put(_url(999999), json={"included": True})
        empty_body = await authenticated_api_client.put(_url(photo_id), json={})

        assert (unknown.status_code, empty_body.status_code) == (404, 422)
        db_session.expire_all()
        assert (await db_session.execute(select(FeedbackEvent))).scalars().all() == []
