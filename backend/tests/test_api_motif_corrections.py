"""specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 5 - die beiden Korrektur-Endpunkte.

Die Auflagen S2 bis S7 sind hier einzeln abgehakt. Drei Aussagen brechen ohne eigenen Fall
stillschweigend:

* S2: Fuer diesen Router gibt es KEINEN Vollstaendigkeitstest (die Auth liegt je Endpunkt am
  Parameter, nicht am Router) - ein dort vergessener Parameter ist still oeffentlich: keine 401,
  nur Daten. Der 401-Fall ist deshalb fuer `PUT` UND `DELETE` Pflicht.
* S6: `user_id` ist ein AUDITFELD. Beide Richtungen brauchen je einen Test - der Schreibweg nimmt
  `user_id` nie aus Body oder Query, und der Aufsuchpfad filtert nie zusaetzlich auf `user_id`.
  Tragender Fall: der `PUT` des zweiten Nutzers UEBERSCHREIBT die Zeile des ersten und legt keine
  zweite an.
* S7: Ein gleichzeitiger `PUT` beider Nutzer laeuft in den Unique-Constraint; der `IntegrityError`
  wird auf `409` abgebildet, nie auf eine `500`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    MotifAssessmentSource,
    Photo,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    Project,
    User,
)
from photosort.motif_strengths import load_effective_strengths, upsert_assessment
from photosort.motifs import MOTIF_REGISTRY
from photosort.security import create_access_token, hash_password

_SOURCE_DIR = Path(__file__).resolve().parent.parent / "src" / "photosort"

_MISSING_PHOTO_ID = 987654


def _url(photo_id: int, motif_key: str) -> str:
    return f"/photos/{photo_id}/motif-corrections/{motif_key}"


async def _make_photo(session: AsyncSession, *, name: str = "Costa Rica") -> Photo:
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


async def _assess(session: AsyncSession, photo: Photo, **overrides: float) -> None:
    strengths = dict.fromkeys(MOTIF_REGISTRY, 0.0)
    strengths.update(overrides)
    await upsert_assessment(
        session,
        photo.id,
        source=MotifAssessmentSource.CLOUD,
        strengths=strengths,
        excluded_document=False,
        provider="anthropic",
        computed_at=datetime(2026, 9, 12, 10, 0, 0),
    )
    await session.commit()


async def _second_user_token(session: AsyncSession, username: str = "partnerin") -> str:
    user = User(username=username, password_hash=hash_password("irrelevant"))
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return create_access_token(user)


async def _corrections(session: AsyncSession) -> list[PhotoMotifCorrection]:
    return list((await session.execute(select(PhotoMotifCorrection))).scalars().all())


class TestAuth:
    async def test_the_put_rejects_a_missing_token(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S2: ein vergessener `current_user`-Parameter ist still oeffentlich - keine 401, nur
        Daten."""
        photo = await _make_photo(db_session)

        response = await api_client.put(_url(photo.id, "menschen"), json={"applies": True})

        assert response.status_code == 401
        assert await _corrections(db_session) == []

    async def test_the_delete_rejects_a_missing_token(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)

        response = await api_client.delete(_url(photo.id, "menschen"))

        assert response.status_code == 401


class TestThePhotoLookup:
    async def test_a_missing_photo_is_a_404_on_the_put(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.put(
            _url(_MISSING_PHOTO_ID, "menschen"), json={"applies": True}
        )

        assert response.status_code == 404

    async def test_a_missing_photo_is_a_404_on_the_delete(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.delete(_url(_MISSING_PHOTO_ID, "menschen"))

        assert response.status_code == 404

    async def test_the_404_does_not_mirror_the_input_value(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.put(
            _url(_MISSING_PHOTO_ID, "menschen"), json={"applies": True}
        )

        assert str(_MISSING_PHOTO_ID) not in response.text

    async def test_a_photo_of_another_project_is_reachable(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S3: die Aufloesung laeuft AUSDRUECKLICH ohne Projektbedingung - das Auth-Modell kennt
        keine Eigentuemer, beide Nutzer sehen dieselben Projekte, `photo_id` ist global eindeutig.
        Untersagt ist der umgekehrte Fehler, aus dem Kamera-Muster eine Projektbedingung zu
        uebernehmen, die als Filter ueber einer fremden Projekt-Id eine Zugriffsentscheidung nur
        vortaeuschte."""
        first = await _make_photo(db_session, name="Erstes")
        second = await _make_photo(db_session, name="Zweites")

        for photo in (first, second):
            response = await authenticated_api_client.put(
                _url(photo.id, "menschen"), json={"applies": True}
            )
            assert response.status_code == 200, photo.relative_path


class TestTheMotifKeyValidation:
    @pytest.mark.parametrize("motif_key", list(MOTIF_REGISTRY))
    async def test_every_registry_key_is_accepted(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        motif_key: str,
    ) -> None:
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(
            _url(photo.id, motif_key), json={"applies": True}
        )

        assert response.status_code == 200

    @pytest.mark.parametrize(
        "motif_key",
        [
            # Der Ausschluss-Schluessel ist NICHT korrigierbar und darf nicht ueber eine
            # Registry-Iteration in den Pruefraum geraten.
            "dokument_screenshot",
            # Anders geschrieben ist ungueltig, nicht "fast richtig" - keine Normalisierung.
            "Menschen",
            "MENSCHEN",
            "menschen%20",
            "mensch",
            "menschenX",
            # Entfallene Kategorieschluessel - ein aus der Laufhistorie bekannter Wert.
            "pflanze",
            "innenraum",
            "nicht_erkannt",
            "tier",
            "gebaeude_bauwerk",
        ],
    )
    async def test_an_invalid_key_is_a_422_on_the_put(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        motif_key: str,
    ) -> None:
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(
            _url(photo.id, motif_key), json={"applies": True}
        )

        assert response.status_code == 422
        assert await _corrections(db_session) == []

    @pytest.mark.parametrize("motif_key", ["dokument_screenshot", "Menschen", "pflanze"])
    async def test_an_invalid_key_is_a_422_on_the_delete_too(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        motif_key: str,
    ) -> None:
        """S4 gilt fuer `PUT` UND `DELETE`: ein `DELETE` ohne Pruefung nimmt einen beliebigen
        Pfadwert an und setzt eine Loeschbedingung darauf ab."""
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.delete(_url(photo.id, motif_key))

        assert response.status_code == 422

    async def test_the_key_is_checked_before_any_write(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """VOR jeder Schreibaktion, nicht erst beim Bauen der Antwort."""
        photo = await _make_photo(db_session)
        await _assess(db_session, photo, menschen=0.9)

        await authenticated_api_client.put(_url(photo.id, "pflanze"), json={"applies": False})

        assert await _corrections(db_session) == []
        strengths = (
            (
                await db_session.execute(
                    select(PhotoMotifStrength).where(PhotoMotifStrength.photo_id == photo.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(strengths) == len(MOTIF_REGISTRY)

    async def test_the_check_is_a_membership_test_and_not_a_prefix_comparison(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)

        assert (
            await authenticated_api_client.put(
                _url(photo.id, "menschen_extra"), json={"applies": True}
            )
        ).status_code == 422

    async def test_a_never_recognised_motif_is_still_correctable(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die untersagte Alternative waere eine auf die vorhandenen Staerkezeilen dieses Fotos
        skopierte Existenzpruefung - sie haengt an Daten statt am Vokabular und wiese das
        Korrigieren eines nie erkannten Motivs zu Unrecht ab."""
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(
            _url(photo.id, "aktivitaet"), json={"applies": True}
        )

        assert response.status_code == 200


class TestTheRequestBody:
    async def test_the_body_carries_the_statement(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(
            _url(photo.id, "menschen"), json={"applies": False}
        )

        assert response.status_code == 200
        assert response.json() == {
            "photo_id": photo.id,
            "motif_key": "menschen",
            "applies": False,
        }

    @pytest.mark.parametrize("body", [{}, {"applies": None}, {"applies": "ja"}, {"applies": 2}])
    async def test_a_body_without_a_usable_truth_value_is_a_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        body: dict[str, object],
    ) -> None:
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(_url(photo.id, "menschen"), json=body)

        assert response.status_code == 422
        assert await _corrections(db_session) == []

    async def test_the_delete_needs_no_body(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.delete(_url(photo.id, "menschen"))

        assert response.status_code == 204

    async def test_a_smuggled_user_id_in_the_body_is_ignored(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S5/S6: `user_id` stammt AUSSCHLIESSLICH aus `current_user.id` - sonst schreibt Nutzer A
        eine Korrektur unter dem Namen von B."""
        photo = await _make_photo(db_session)
        own = (await db_session.execute(select(User))).scalars().one()

        response = await authenticated_api_client.put(
            _url(photo.id, "menschen"), json={"applies": True, "user_id": 999999}
        )

        assert response.status_code == 200
        assert [row.user_id for row in await _corrections(db_session)] == [own.id]

    async def test_a_smuggled_strength_in_the_body_is_ignored(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S5: Massenzuweisung ist strukturell ausgeschlossen statt im Handler herausgefiltert. Ein
        Feld, ueber das ein Client eine Staerke setzen koennte, hebt die Unterscheidung zwischen
        Modellaussage und Korrektur auf."""
        photo = await _make_photo(db_session)
        await _assess(db_session, photo, menschen=0.42)

        response = await authenticated_api_client.put(
            _url(photo.id, "menschen"),
            json={"applies": False, "strength": 1.0, "motif_key": "tiere", "photo_id": 1},
        )

        assert response.status_code == 200
        stored = (
            await db_session.execute(
                select(PhotoMotifStrength.strength).where(
                    PhotoMotifStrength.photo_id == photo.id,
                    PhotoMotifStrength.motif_key == "menschen",
                )
            )
        ).scalar_one()
        assert stored == pytest.approx(0.42)
        assert [row.motif_key for row in await _corrections(db_session)] == ["menschen"]

    def test_the_input_schema_carries_exactly_one_field(self) -> None:
        """Die strukturelle Haelfte von S5: ein spaeter ergaenztes Feld machte die
        Verhaltensfaelle oben gruen, waehrend die Massenzuweisung wieder offen stuende."""
        from photosort.api.photos import MotifCorrectionIn

        assert set(MotifCorrectionIn.model_fields) == {"applies"}


class TestTheSharedCorrectionRow:
    async def test_a_put_creates_a_row_with_the_user_from_the_token(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)
        own = (await db_session.execute(select(User))).scalars().one()

        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": True})

        rows = await _corrections(db_session)
        assert len(rows) == 1
        assert (rows[0].photo_id, rows[0].motif_key, rows[0].applies) == (
            photo.id,
            "menschen",
            True,
        )
        assert rows[0].user_id == own.id

    async def test_a_second_put_of_the_same_user_updates_in_place(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)
        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": True})
        first_id = (await _corrections(db_session))[0].id

        response = await authenticated_api_client.put(
            _url(photo.id, "menschen"), json={"applies": False}
        )

        assert response.status_code == 200
        rows = await _corrections(db_session)
        assert len(rows) == 1
        assert rows[0].id == first_id
        assert rows[0].applies is False

    async def test_the_put_of_the_second_user_overwrites_the_row_of_the_first(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """DER tragende Fall von S6: kein `IntegrityError`, keine zweite Zeile - ein Update, und
        `user_id` wandert mit. Bleibt das Feld stehen, schreibt die Feedback-Story das Signal der
        falschen Person zu."""
        photo = await _make_photo(db_session)
        first_user = (await db_session.execute(select(User))).scalars().one()
        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": True})
        row_id = (await _corrections(db_session))[0].id
        token = await _second_user_token(db_session)

        response = await authenticated_api_client.put(
            _url(photo.id, "menschen"),
            json={"applies": False},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        rows = await _corrections(db_session)
        assert len(rows) == 1, "es darf keine zweite Zeile fuer dasselbe (Foto, Motiv) entstehen"
        assert rows[0].id == row_id
        assert rows[0].applies is False
        assert rows[0].user_id != first_user.id

    async def test_the_lookup_does_not_filter_on_the_user(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die zweite Richtung von S6: filterte der Aufsuchpfad zusaetzlich auf `user_id`,
        entstuenden zwei widersprueckliche Zeilen fuer dasselbe Paar - und welche gilt, entschiede
        die Sortierung. Geprueft ueber die WIRKSAME Staerke, nicht nur ueber die Zeilenzahl."""
        photo = await _make_photo(db_session)
        await _assess(db_session, photo, menschen=0.9)
        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": False})
        token = await _second_user_token(db_session)

        await authenticated_api_client.put(
            _url(photo.id, "menschen"),
            json={"applies": True},
            headers={"Authorization": f"Bearer {token}"},
        )

        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
        assert effective["menschen"].strength == 1.0
        assert effective["menschen"].correction is True

    async def test_the_other_person_may_delete_the_correction(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)
        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": True})
        token = await _second_user_token(db_session)

        response = await authenticated_api_client.delete(
            _url(photo.id, "menschen"), headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 204
        assert await _corrections(db_session) == []

    async def test_two_motifs_of_the_same_photo_are_two_rows(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)

        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": True})
        await authenticated_api_client.put(_url(photo.id, "tiere"), json={"applies": False})

        assert {row.motif_key for row in await _corrections(db_session)} == {"menschen", "tiere"}


class TestTheDelete:
    async def test_it_removes_an_existing_correction(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)
        await _assess(db_session, photo, menschen=0.9)
        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": False})

        response = await authenticated_api_client.delete(_url(photo.id, "menschen"))

        assert response.status_code == 204
        assert await _corrections(db_session) == []
        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
        assert effective["menschen"].strength == pytest.approx(0.9)
        assert effective["menschen"].correction is None

    async def test_it_is_idempotent_without_a_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)

        first = await authenticated_api_client.delete(_url(photo.id, "menschen"))
        second = await authenticated_api_client.delete(_url(photo.id, "menschen"))

        assert (first.status_code, second.status_code) == (204, 204)

    async def test_it_only_removes_the_named_motif(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)
        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": True})
        await authenticated_api_client.put(_url(photo.id, "tiere"), json={"applies": True})

        await authenticated_api_client.delete(_url(photo.id, "menschen"))

        assert {row.motif_key for row in await _corrections(db_session)} == {"tiere"}

    async def test_it_only_removes_the_correction_of_the_named_photo(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        first = await _make_photo(db_session, name="Erstes")
        second = await _make_photo(db_session, name="Zweites")
        for photo in (first, second):
            await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": True})

        await authenticated_api_client.delete(_url(first.id, "menschen"))

        assert [row.photo_id for row in await _corrections(db_session)] == [second.id]


class TestAPhotoWithoutAnAssessment:
    async def test_the_correction_is_accepted_and_stored(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Tabelle ist lauf-unabhaengig: korrigieren geht auch vor dem ersten Lauf."""
        photo = await _make_photo(db_session)

        response = await authenticated_api_client.put(
            _url(photo.id, "menschen"), json={"applies": True}
        )

        assert response.status_code == 200
        assert len(await _corrections(db_session)) == 1

    async def test_the_effective_strengths_stay_empty_until_the_first_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        photo = await _make_photo(db_session)
        await authenticated_api_client.put(_url(photo.id, "menschen"), json={"applies": True})

        assert await load_effective_strengths(db_session, [photo.id]) == {}


class TestTheConcurrencyMapping:
    async def test_an_integrity_error_becomes_a_409_and_never_a_500(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """S7: ein gleichzeitiger `PUT` beider Nutzer auf dasselbe Paar laeuft in den
        Unique-Constraint. Simuliert ueber einen scheiternden `flush` - ein echtes Wettrennen ist
        in einer In-Memory-SQLite-Sitzung nicht herstellbar, und der Abbildungspfad ist das, was
        hier geprueft gehoert."""
        photo = await _make_photo(db_session)
        original_flush = AsyncSession.flush

        async def _failing_flush(self: AsyncSession, *args: object, **kwargs: object) -> None:
            raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

        monkeypatch.setattr(AsyncSession, "flush", _failing_flush)
        try:
            response = await authenticated_api_client.put(
                _url(photo.id, "menschen"), json={"applies": True}
            )
        finally:
            monkeypatch.setattr(AsyncSession, "flush", original_flush)

        assert response.status_code == 409
        assert response.json()["detail"]

    def test_the_handlers_take_no_row_lock(self) -> None:
        """Eine Sperre ist nicht noetig und ausdruecklich nicht vorzusehen: die Korrektur schreibt
        eine Zeile und leitet nichts ab, sie hat keinen Schreibzugriff auf die Rangfolge. Der
        Grund, aus dem `reassign_photo_category` mit `with_for_update()` arbeiten musste, gilt
        hier nicht."""
        source = (_SOURCE_DIR / "api" / "photos.py").read_text(encoding="utf-8")
        handlers = source[source.index("async def set_motif_correction") :]

        # Der AUFRUF, nicht das Wort: der Kommentar an der Stelle nennt die untersagte Sperre
        # ausdruecklich, und ein Wortverbot wuerde genau diese Begruendung verbieten.
        assert ".with_for_update(" not in handlers
        assert "_lock_photo_score" not in handlers

    def test_the_guard_would_see_an_actual_lock(self) -> None:
        """Selbstschutz: der Waechter oben prueft auf den Methodenaufruf - dieser Fall haelt fest,
        dass er die Form trifft, in der eine Sperre tatsaechlich geschrieben waere."""
        assert ".with_for_update(" in "select(X).where(Y).with_for_update()"
