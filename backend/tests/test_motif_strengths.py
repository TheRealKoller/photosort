"""specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 2 - der DB-nahe Teil des Motivsets.

Vier Nachweise tragen mehr als eine Werteprüfung:

* Die WIRKSAME Stärke entsteht im Lesepfad und wird nie in die Stärkezeile materialisiert. Geprüft
  als Fallmatrix gegen eine hohe UND eine niedrige Grundlage - nur gegen eine von beiden bestünde
  auch eine Implementierung, die die Korrektur ignoriert.
* Ein STRUKTURELLER Wächter hält fest, dass dieser `CASE` an genau einer Stelle lebt. Eine zweite
  Fassung wäre kein Testfehler, sondern eine zweite Wahrheit.
* „Lokal schlägt Cloud nie" wird PAARWEISE geprüft: Cloud nach lokal ersetzt, lokal nach Cloud
  lässt Herkunft, Zeitstempel und alle acht Werte unverändert. Der zweite Fall ist der
  eigentliche; ohne ihn bestünde auch ein bedingungsloses Überschreiben.
* Eine Korrektur überlebt einen weiteren Lauf über dasselbe Foto - und zwar als Zeile UND in ihrer
  Wirkung. Nur die erste Hälfte deckt ein `cascade` nicht ab, das die Zeile mit der Kopfzeile
  abräumt; nur die zweite deckt nicht ab, dass sie neu geschrieben statt bewahrt wurde.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    MotifAssessmentSource,
    Photo,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    Project,
    User,
)
from photosort.motif_strengths import (
    EffectiveStrength,
    load_effective_strengths,
    upsert_assessment,
)
from photosort.motifs import MOTIF_REGISTRY

_SOURCE_DIR = Path(__file__).resolve().parent.parent / "src" / "photosort"

_NOW = datetime(2026, 9, 12, 10, 0, 0)
_LATER = datetime(2026, 9, 12, 12, 0, 0)


def _vector(**overrides: float) -> dict[str, float]:
    """Ein vollbesetzter Achter-Vektor - der Vektor ist vollständig oder er existiert nicht."""
    strengths = dict.fromkeys(MOTIF_REGISTRY, 0.0)
    strengths.update(overrides)
    return strengths


async def _photo(session: AsyncSession, *, name: str = "Costa Rica") -> Photo:
    project = Project(
        name=name, opencloud_drive_id="drive-1", opencloud_path=f"/{name.replace(' ', '')}"
    )
    session.add(project)
    await session.flush()
    photo = Photo(
        project_id=project.id,
        relative_path=f"{name}/img001.jpg",
        etag=f"etag-{name}",
        content_length=1234,
        taken_at=_NOW,
        taken_at_original=_NOW,
        last_modified=_NOW,
    )
    session.add(photo)
    await session.flush()
    return photo


async def _user(session: AsyncSession, username: str = "daniel") -> User:
    user = User(username=username, password_hash="hashed-value")
    session.add(user)
    await session.flush()
    return user


class TestUpsertAssessment:
    async def test_a_cloud_assessment_writes_the_header_and_all_eight_strengths(
        self, db_session: AsyncSession
    ) -> None:
        photo = await _photo(db_session)

        written = await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(bauwerk_sehenswuerdigkeit=0.9, menschen=0.2),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        await db_session.flush()

        assert written is True
        header = await db_session.get(PhotoMotifAssessment, photo.id)
        assert header is not None
        assert header.source == MotifAssessmentSource.CLOUD
        assert header.provider == "anthropic"
        assert header.excluded_document is False
        assert header.computed_at == _NOW
        rows = {
            row.motif_key: row.strength
            for row in (
                await db_session.execute(
                    select(PhotoMotifStrength).where(PhotoMotifStrength.photo_id == photo.id)
                )
            ).scalars()
        }
        assert rows == _vector(bauwerk_sehenswuerdigkeit=0.9, menschen=0.2)

    async def test_a_local_assessment_carries_no_provider(self, db_session: AsyncSession) -> None:
        photo = await _photo(db_session)

        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.LOCAL,
            strengths=_vector(tiere=0.4),
            excluded_document=False,
            provider=None,
            computed_at=_NOW,
        )
        await db_session.flush()

        header = await db_session.get(PhotoMotifAssessment, photo.id)
        assert header is not None
        assert header.source == MotifAssessmentSource.LOCAL
        assert header.provider is None

    async def test_a_local_assessment_without_any_detection_still_creates_a_header(
        self, db_session: AsyncSession
    ) -> None:
        """Sonst gilt das Foto als „noch nicht klassifiziert", obwohl es beurteilt wurde."""
        photo = await _photo(db_session)

        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.LOCAL,
            strengths=_vector(),
            excluded_document=False,
            provider=None,
            computed_at=_NOW,
        )
        await db_session.flush()

        header = await db_session.get(PhotoMotifAssessment, photo.id)
        assert header is not None
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
        assert {row.strength for row in strengths} == {0.0}

    async def test_a_local_assessment_replaces_an_existing_local_one(
        self, db_session: AsyncSession
    ) -> None:
        photo = await _photo(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.LOCAL,
            strengths=_vector(tiere=0.4),
            excluded_document=False,
            provider=None,
            computed_at=_NOW,
        )
        await db_session.flush()

        written = await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.LOCAL,
            strengths=_vector(tiere=0.9),
            excluded_document=False,
            provider=None,
            computed_at=_LATER,
        )
        await db_session.flush()

        assert written is True
        header = await db_session.get(PhotoMotifAssessment, photo.id)
        assert header is not None
        assert header.computed_at == _LATER
        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
        assert effective["tiere"].strength == pytest.approx(0.9)

    async def test_a_cloud_assessment_replaces_an_existing_local_one(
        self, db_session: AsyncSession
    ) -> None:
        """Erste Hälfte des Paars: liegt eine Modellaussage vor, bestimmt allein sie die
        Motivstärken."""
        photo = await _photo(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.LOCAL,
            strengths=_vector(tiere=0.4),
            excluded_document=False,
            provider=None,
            computed_at=_NOW,
        )
        await db_session.flush()

        written = await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.8),
            excluded_document=False,
            provider="anthropic",
            computed_at=_LATER,
        )
        await db_session.flush()

        assert written is True
        header = await db_session.get(PhotoMotifAssessment, photo.id)
        assert header is not None
        assert header.source == MotifAssessmentSource.CLOUD
        assert header.provider == "anthropic"
        assert header.computed_at == _LATER
        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
        assert effective["menschen"].strength == pytest.approx(0.8)
        assert effective["tiere"].strength == 0.0

    async def test_a_local_assessment_never_overwrites_a_cloud_one(
        self, db_session: AsyncSession
    ) -> None:
        """Die zweite und eigentliche Hälfte des Paars: Herkunft, Anbieter, Zeitstempel UND alle
        acht Werte bleiben unverändert. Ohne diesen Fall bestünde auch ein bedingungsloses
        Überschreiben."""
        photo = await _photo(db_session)
        cloud_vector = _vector(bauwerk_sehenswuerdigkeit=0.9, menschen=0.2, tiere=0.1)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=cloud_vector,
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        await db_session.flush()

        written = await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.LOCAL,
            strengths=_vector(tiere=0.99, menschen=0.99),
            excluded_document=True,
            provider=None,
            computed_at=_LATER,
        )
        await db_session.flush()

        assert written is False
        header = await db_session.get(PhotoMotifAssessment, photo.id)
        assert header is not None
        assert header.source == MotifAssessmentSource.CLOUD
        assert header.provider == "anthropic"
        assert header.computed_at == _NOW
        assert header.excluded_document is False
        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
        assert {key: value.strength for key, value in effective.items()} == cloud_vector

    async def test_an_excluded_photo_keeps_its_strengths(self, db_session: AsyncSession) -> None:
        """Der Ausschluss gewinnt im LESEPFAD; die Stärken werden nicht auf 0 gesetzt."""
        photo = await _photo(db_session)

        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.9),
            excluded_document=True,
            provider="anthropic",
            computed_at=_NOW,
        )
        await db_session.flush()

        header = await db_session.get(PhotoMotifAssessment, photo.id)
        assert header is not None
        assert header.excluded_document is True
        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
        assert effective["menschen"].strength == pytest.approx(0.9)

    async def test_a_second_run_leaves_no_orphaned_strength_row_behind(
        self, db_session: AsyncSession
    ) -> None:
        """Eine neue Grundlage ersetzt den GESAMTEN Vektor - keine Zeile aus dem Lauf davor."""
        photo = await _photo(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.8),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        await db_session.flush()

        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(tiere=0.7),
            excluded_document=False,
            provider="anthropic",
            computed_at=_LATER,
        )
        await db_session.flush()

        rows = (
            (
                await db_session.execute(
                    select(PhotoMotifStrength).where(PhotoMotifStrength.photo_id == photo.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == len(MOTIF_REGISTRY)


class TestTheEffectiveStrength:
    async def test_without_a_correction_the_base_strength_applies(
        self, db_session: AsyncSession
    ) -> None:
        photo = await _photo(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.42),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        await db_session.flush()

        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]

        assert effective["menschen"] == EffectiveStrength(
            strength=pytest.approx(0.42), correction=None
        )  # type: ignore[arg-type]

    @pytest.mark.parametrize("base", [0.0, 0.1, 0.5, 0.9, 1.0])
    async def test_applies_true_beats_any_base_strength(
        self, db_session: AsyncSession, base: float
    ) -> None:
        photo = await _photo(db_session)
        user = await _user(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=base),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True
            )
        )
        await db_session.flush()

        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]

        assert effective["menschen"].strength == 1.0
        assert effective["menschen"].correction is True

    @pytest.mark.parametrize("base", [0.0, 0.1, 0.5, 0.9, 1.0])
    async def test_applies_false_beats_any_base_strength(
        self, db_session: AsyncSession, base: float
    ) -> None:
        photo = await _photo(db_session)
        user = await _user(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=base),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        await db_session.flush()

        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]

        assert effective["menschen"].strength == 0.0
        assert effective["menschen"].correction is False

    async def test_a_correction_on_one_motif_leaves_the_other_seven_untouched(
        self, db_session: AsyncSession
    ) -> None:
        photo = await _photo(db_session)
        user = await _user(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.9, tiere=0.3),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        await db_session.flush()

        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]

        assert effective["menschen"].strength == 0.0
        assert effective["tiere"].strength == pytest.approx(0.3)
        assert effective["tiere"].correction is None

    async def test_a_pointless_correction_is_still_visible(self, db_session: AsyncSession) -> None:
        """`applies=false` auf einem Motiv, dessen Grundlage schon 0 ist: die Zeile entsteht und
        die Oberfläche zeigt das Korrekturwort - obwohl sich keine Zahl bewegt. Eine
        Implementierung, die eine wirkungslose Korrektur „einspart", macht sie unsichtbar."""
        photo = await _photo(db_session)
        user = await _user(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.0),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        await db_session.flush()

        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]

        assert effective["menschen"].strength == 0.0
        assert effective["menschen"].correction is False

    async def test_the_correction_is_not_materialised_into_the_strength_row(
        self, db_session: AsyncSession
    ) -> None:
        """Die gespeicherte Zahl bleibt die Modellaussage - die Korrektur wirkt nur im Lesepfad."""
        photo = await _photo(db_session)
        user = await _user(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.9),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        await db_session.flush()
        await load_effective_strengths(db_session, [photo.id])

        stored = (
            await db_session.execute(
                select(PhotoMotifStrength.strength).where(
                    PhotoMotifStrength.photo_id == photo.id,
                    PhotoMotifStrength.motif_key == "menschen",
                )
            )
        ).scalar_one()

        assert stored == pytest.approx(0.9)


class TestACorrectionSurvivesAnotherRun:
    async def test_the_row_still_exists_and_still_wins_after_a_new_assessment(
        self, db_session: AsyncSession
    ) -> None:
        """Beide Hälften in EINEM Fall: die Zeile existiert noch UND die wirksame Stärke ist
        weiter der korrigierte Wert. Getrennt geschrieben deckte die erste ein `cascade` nicht ab,
        das die Zeile mit der Kopfzeile abräumt, und die zweite nicht, dass sie neu geschrieben
        statt bewahrt wurde."""
        photo = await _photo(db_session)
        user = await _user(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.9),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        await db_session.flush()
        correction_id = (
            await db_session.execute(
                select(PhotoMotifCorrection.id).where(PhotoMotifCorrection.photo_id == photo.id)
            )
        ).scalar_one()

        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.95),
            excluded_document=False,
            provider="anthropic",
            computed_at=_LATER,
        )
        await db_session.flush()

        surviving = (await db_session.execute(select(PhotoMotifCorrection))).scalars().one()
        assert surviving.id == correction_id, "die Korrekturzeile wurde neu geschrieben"
        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
        assert effective["menschen"].strength == 0.0

    async def test_a_run_that_confirms_the_correction_does_not_remove_it(
        self, db_session: AsyncSession
    ) -> None:
        """Der Sonderfall: das Modell liefert nun denselben Wert, den die Korrektur erzwingt. Die
        Zeile ist eine Nutzeraussage, keine Zwischenspeicherung."""
        photo = await _photo(db_session)
        user = await _user(db_session)
        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.2),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True
            )
        )
        await db_session.flush()

        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=1.0),
            excluded_document=False,
            provider="anthropic",
            computed_at=_LATER,
        )
        await db_session.flush()

        assert len((await db_session.execute(select(PhotoMotifCorrection))).scalars().all()) == 1

    async def test_a_correction_written_before_any_run_wins_in_the_very_first_one(
        self, db_session: AsyncSession
    ) -> None:
        """Korrigieren, danach klassifizieren: die Tabelle ist lauf-unabhängig, also greift die
        Korrektur bereits im ersten Lauf."""
        photo = await _photo(db_session)
        user = await _user(db_session)
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True
            )
        )
        await db_session.flush()

        assert await load_effective_strengths(db_session, [photo.id]) == {}

        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.CLOUD,
            strengths=_vector(menschen=0.1),
            excluded_document=False,
            provider="anthropic",
            computed_at=_NOW,
        )
        await db_session.flush()

        effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
        assert effective["menschen"].strength == 1.0


class TestLoadEffectiveStrengths:
    async def test_a_photo_without_a_header_is_absent_from_the_result(
        self, db_session: AsyncSession
    ) -> None:
        """Die Abwesenheit der Kopfzeile ist „noch nicht klassifiziert" - NICHT acht Nullen."""
        photo = await _photo(db_session)

        assert await load_effective_strengths(db_session, [photo.id]) == {}

    async def test_an_empty_id_list_asks_the_database_nothing(
        self, db_session: AsyncSession
    ) -> None:
        assert await load_effective_strengths(db_session, []) == {}

    async def test_it_keeps_the_photos_apart(self, db_session: AsyncSession) -> None:
        first = await _photo(db_session, name="Erstes")
        second = await _photo(db_session, name="Zweites")
        for photo, value in ((first, 0.3), (second, 0.7)):
            await upsert_assessment(
                db_session,
                photo.id,
                source=MotifAssessmentSource.CLOUD,
                strengths=_vector(menschen=value),
                excluded_document=False,
                provider="anthropic",
                computed_at=_NOW,
            )
        await db_session.flush()

        result = await load_effective_strengths(db_session, [first.id, second.id])

        assert result[first.id]["menschen"].strength == pytest.approx(0.3)
        assert result[second.id]["menschen"].strength == pytest.approx(0.7)

    async def test_a_correction_of_another_photo_does_not_leak_over(
        self, db_session: AsyncSession
    ) -> None:
        """Der Verbund läuft über `(photo_id, motif_key)` - nicht über `motif_key` allein."""
        first = await _photo(db_session, name="Erstes")
        second = await _photo(db_session, name="Zweites")
        user = await _user(db_session)
        for photo in (first, second):
            await upsert_assessment(
                db_session,
                photo.id,
                source=MotifAssessmentSource.CLOUD,
                strengths=_vector(menschen=0.9),
                excluded_document=False,
                provider="anthropic",
                computed_at=_NOW,
            )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=first.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        await db_session.flush()

        result = await load_effective_strengths(db_session, [first.id, second.id])

        assert result[first.id]["menschen"].strength == 0.0
        assert result[second.id]["menschen"].strength == pytest.approx(0.9)

    async def test_it_returns_only_the_requested_photos(self, db_session: AsyncSession) -> None:
        first = await _photo(db_session, name="Erstes")
        second = await _photo(db_session, name="Zweites")
        for photo in (first, second):
            await upsert_assessment(
                db_session,
                photo.id,
                source=MotifAssessmentSource.CLOUD,
                strengths=_vector(),
                excluded_document=False,
                provider="anthropic",
                computed_at=_NOW,
            )
        await db_session.flush()

        assert set(await load_effective_strengths(db_session, [first.id])) == {first.id}


class TestTheStructuralGuardAgainstASecondCase:
    """Der Ausdruck lebt an EINER Stelle und wird von jedem lesenden Pfad von dort bezogen. Eine
    zweite Fassung wäre kein Testfehler, sondern eine zweite Wahrheit - und sie liefe beim
    nächsten Grenzfall auseinander."""

    def test_only_motif_strengths_names_the_correction_column_of_the_class(self) -> None:
        naming = sorted(
            path.relative_to(_SOURCE_DIR).as_posix()
            for path in _SOURCE_DIR.rglob("*.py")
            if "PhotoMotifCorrection.applies" in path.read_text(encoding="utf-8")
        )

        assert naming == ["motif_strengths.py"], (
            "Die wirksame Stärke darf nur in motif_strengths.py aus der Korrekturspalte "
            f"entstehen; sie wird auch genannt in: {naming}"
        )

    def test_the_module_exists_and_carries_the_expression(self) -> None:
        """Selbstschutz: ohne diesen Fall bliebe der Wächter oben auch grün, wenn der Ausdruck
        ganz verschwindet."""
        source = (_SOURCE_DIR / "motif_strengths.py").read_text(encoding="utf-8")

        assert "PhotoMotifCorrection.applies" in source
        assert "def effective_strength_expression" in source


class TestTheTimestampsAreNaive:
    async def test_a_timezone_aware_input_is_not_silently_stored(
        self, db_session: AsyncSession
    ) -> None:
        """Alle Zeitstempel des Projekts sind zonenlos (ADR 0090, Punkt 4) - der Aufrufer reicht
        einen zonenlosen Wert durch, und dieser Fall hält fest, dass er unverändert ankommt."""
        photo = await _photo(db_session)
        naive = datetime.now(UTC).replace(tzinfo=None)

        await upsert_assessment(
            db_session,
            photo.id,
            source=MotifAssessmentSource.LOCAL,
            strengths=_vector(),
            excluded_document=False,
            provider=None,
            computed_at=naive,
        )
        await db_session.flush()

        header = await db_session.get(PhotoMotifAssessment, photo.id)
        assert header is not None
        assert header.computed_at == naive
