"""Demo-Zustands-Seeder: Schutzpruefung und `rebuild_demo_state` gegen die Datenbank - die sieben
Zustaende, Seitenverhaeltnis, Vorschaubilder, Idempotenz, Unberuehrtes, Personen,
Produktionsgroesse.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import demo_state
from photosort.criteria import CRITERIA_REGISTRY
from photosort.demo_state import (
    AUSSCHUSS_PAGE_SIZE,
    CONFIRM_LITERAL,
    DEMO_PERSON_NAMES,
    DEMO_PROJECT_PREFIX,
    DUPLICATE_PROJECT_NAME,
    EMPTY_PROJECT_NAME,
    ERROR_PROJECT_NAME,
    ERROR_STATE_PHOTO_COUNT,
    LARGE_COLLECTION_PHOTO_COUNT,
    LARGE_PROJECT_NAME,
    LONG_AUSSCHUSS_PROJECT_NAME,
    OPERATIONS_PROJECT_NAME,
    RATED_PROJECT_NAME,
    DemoStateError,
    assert_safe_to_seed,
    rebuild_demo_state,
    render_demo_image,
)
from photosort.face_analysis import MODEL_KEY
from photosort.models import (
    ClassificationPhase,
    ClassificationReview,
    CriterionScoringRun,
    Person,
    PersonReference,
    Photo,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoDuplicateDecision,
    PhotoMotifStrength,
    PhotoPersonCorrection,
    PhotoPersonDetection,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motifs import MOTIF_REGISTRY, MOTIF_STRENGTH_BAND_STRONG
from photosort.person_matching import validated_embedding
from photosort.persons import MAX_NAME_CODE_POINTS, load_effective_persons
from photosort.scoring import SHARPNESS_REJECT_THRESHOLD
from photosort.thumbnails import (
    display_path,
    generate_variants,
    thumbnail_path,
)
from tests.phase_binding import assert_phase_binding
from tests.support.demo_state_rows import _make_user, _photos_of, _project


async def _make_foreign_project(
    session: AsyncSession, cache_dir: Path, *, name: str = "Familienfotos 2019"
) -> tuple[Project, Photo]:
    """Ein Projekt, das der Seeder NIE anfassen darf - inklusive echter Cache-Dateien, damit ein
    versehentliches `glob`/`rmtree` im Cache auffiele (M2)."""
    project = Project(name=name, opencloud_drive_id="drive-echt", opencloud_path="/Familie")
    session.add(project)
    await session.flush()
    photo = Photo(
        project_id=project.id,
        relative_path="Familie/2019/echtes-foto.jpg",
        etag="echt-0001",
        content_length=1234,
        taken_at=datetime(2019, 7, 1, 12, 0, 0),
        taken_at_original=datetime(2019, 7, 1, 12, 0, 0),
        last_modified=datetime(2019, 7, 1, 12, 0, 0),
    )
    session.add(photo)
    await session.flush()
    generate_variants(cache_dir, photo.id, photo.etag, render_demo_image(slug="echt", index=0))
    return project, photo


def _cache_file_hashes(cache_dir: Path) -> list[str]:
    """Sortierte Inhalts-Hashes aller Cache-Dateien. Bewusst Inhalte statt Dateinamen: die Namen
    haengen an der von der Datenbank vergebenen photo_id, der Inhalt nicht."""
    if not cache_dir.exists():
        return []
    return sorted(
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in cache_dir.iterdir()
        if path.is_file()
    )


async def _snapshot(session: AsyncSession, cache_dir: Path) -> dict[str, object]:
    """Normalisierter Zustands-Schnappschuss fuer die Idempotenz-Pruefung (Testkonzept, Punkt 2).

    Bewusst unabhaengig vom Seeder gebaut - eine vom Modul selbst gelieferte Schnappschuss-
    Funktion pruefte sich selbst."""
    projects = (await session.execute(select(Project).order_by(Project.name))).scalars().all()
    photos_by_project: dict[str, int] = {}
    ratings: dict[str, int] = {}
    suggestions = 0
    for project in projects:
        photos = (
            (await session.execute(select(Photo).where(Photo.project_id == project.id)))
            .scalars()
            .all()
        )
        photos_by_project[project.name] = len(photos)
        for photo in photos:
            for rating in (
                (await session.execute(select(Rating).where(Rating.photo_id == photo.id)))
                .scalars()
                .all()
            ):
                # Beide Angaben im Schluessel: `status` allein liesse eine verlorene oder
                # zusaetzliche Favoriten-Auszeichnung durch den Schnappschuss fallen.
                key = (
                    f"{'-' if rating.status is None else rating.status.value}"
                    f"+{'favorit' if rating.favorite else 'kein-favorit'}"
                )
                ratings[key] = ratings.get(key, 0) + 1
            score = await session.get(PhotoScore, photo.id)
            if score is not None and score.suggested_status is not None:
                suggestions += 1
    scan_runs = (await session.execute(select(ScanRun))).scalars().all()
    return {
        "projects": sorted(project.name for project in projects),
        "photos_by_project": photos_by_project,
        "ratings": ratings,
        "suggestions": suggestions,
        "scan_run_status": sorted(run.status.value for run in scan_runs),
        "cache": _cache_file_hashes(cache_dir),
    }


class TestAssertSafeToSeed:
    """Die dreiteilige Sperre als Ganzes (M1) - inklusive Teil (b), der die Datenbank braucht."""

    async def test_empty_database_passes_the_guard(self, db_session: AsyncSession) -> None:
        # Edge Case E8: der Erstlauf darf nicht daran scheitern, dass "keine Demo-Projekte
        # vorhanden" als "nicht ausschliesslich Demo-Projekte" gewertet wird.
        await assert_safe_to_seed(db_session, confirmation=CONFIRM_LITERAL, opencloud_base_url="")

    async def test_database_with_only_demo_projects_passes_the_guard(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(
            Project(name=RATED_PROJECT_NAME, opencloud_drive_id="demo", opencloud_path="/demo")
        )
        await db_session.flush()
        await assert_safe_to_seed(db_session, confirmation=CONFIRM_LITERAL, opencloud_base_url="")

    @pytest.mark.parametrize("name", ["Familienfotos 2019", "Demo", "Demonstration"])
    async def test_any_foreign_project_aborts(self, db_session: AsyncSession, name: str) -> None:
        db_session.add(Project(name=name, opencloud_drive_id="drive", opencloud_path="/pfad"))
        await db_session.flush()
        with pytest.raises(DemoStateError):
            await assert_safe_to_seed(
                db_session, confirmation=CONFIRM_LITERAL, opencloud_base_url=""
            )

    async def test_wrong_confirmation_aborts(self, db_session: AsyncSession) -> None:
        with pytest.raises(DemoStateError):
            await assert_safe_to_seed(db_session, confirmation=None, opencloud_base_url="")

    async def test_real_looking_opencloud_target_aborts(self, db_session: AsyncSession) -> None:
        with pytest.raises(DemoStateError):
            await assert_safe_to_seed(
                db_session,
                confirmation=CONFIRM_LITERAL,
                opencloud_base_url="https://cloud.example.org",
            )


class TestRebuildDemoStateProducesTheSevenStates:
    """Die sieben Zustaende, geprueft ueber ihre pruefrelevante Eigenschaft - nie ueber die
    Implementierung."""

    async def test_creates_exactly_the_seven_demo_projects(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        names = (
            (await db_session.execute(select(Project.name).order_by(Project.id))).scalars().all()
        )
        assert names == [
            EMPTY_PROJECT_NAME,
            LARGE_PROJECT_NAME,
            RATED_PROJECT_NAME,
            ERROR_PROJECT_NAME,
            DUPLICATE_PROJECT_NAME,
            LONG_AUSSCHUSS_PROJECT_NAME,
            OPERATIONS_PROJECT_NAME,
        ]

    async def test_the_operations_project_shows_a_waiting_scan_as_its_latest_run(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Spec 0641, Architektur Punkt 8: Ohne einen wartenden Lauf sind „{Schritt} wartet",
        der Abbrechen-Knopf eines wartenden Vorgangs und „Alle abbrechen" im Pruefstack nicht
        erreichbar. Er muss der JUENGSTE Lauf seiner Art sein (die Anzeige liest nur ihn) und
        darf noch keinen Abbruchwunsch tragen - sonst waere „Alle abbrechen" gesperrt."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, OPERATIONS_PROJECT_NAME)
        latest = (
            (
                await db_session.execute(
                    select(ScanRun)
                    .where(ScanRun.project_id == project.id)
                    .order_by(ScanRun.started_at.desc())
                )
            )
            .scalars()
            .first()
        )

        assert latest is not None
        assert latest.status == ScanStatus.QUEUED
        assert latest.cancel_requested_at is None
        assert latest.finished_at is None
        assert latest.error_message is None

    async def test_the_operations_project_shows_a_cancelled_classification(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Spec 0641: Ein abgebrochener Lauf traegt Merker, Endzeit, seine letzte `phase` und
        einen eingefrorenen Teilstand - und KEINE Fehlermeldung (er ist kein Fehler). Erreichbar
        ist er nur hinter einem bestaetigten Ausschuss."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, OPERATIONS_PROJECT_NAME)
        runs = (
            (
                await db_session.execute(
                    select(CriterionScoringRun).where(CriterionScoringRun.project_id == project.id)
                )
            )
            .scalars()
            .all()
        )

        assert len(runs) == 1
        run = runs[0]
        assert run.status == ScanStatus.CANCELLED
        assert run.cancel_requested_at is not None
        assert run.finished_at is not None
        assert run.cancel_requested_at <= run.finished_at
        assert run.error_message is None
        assert run.phase is ClassificationPhase.CRITERIA
        assert_phase_binding(run)
        assert 0 < run.photos_processed < run.photos_total
        scoring_run = await db_session.get(ScoringRun, run.scoring_run_id)
        assert scoring_run is not None
        assert scoring_run.status == ScanStatus.SUCCESS
        assert scoring_run.gate_confirmed_at is not None

    async def test_no_other_demo_project_carries_a_waiting_or_cancelled_run(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Ein wartender Lauf sperrt die Ausloeser seines Schritts und blendet die
        Vorgangsleiste ein. Die uebrigen Projekte tragen die e2e-Faelle und muessen frei
        bleiben."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        operations = await _project(db_session, OPERATIONS_PROJECT_NAME)
        special = (ScanStatus.QUEUED, ScanStatus.CANCELLED)
        for model in (ScanRun, ScoringRun, CriterionScoringRun, ClassificationReview):
            rows = (
                await db_session.execute(
                    select(model.project_id).where(
                        model.status.in_(special), model.project_id != operations.id
                    )
                )
            ).all()
            assert rows == [], model.__name__

    async def test_the_long_ausschuss_fills_more_than_one_page_and_stays_unconfirmed(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Spec 0568: Der Browserfall „Mehr laden" der Aktionsleiste braucht eine unbestaetigte
        Ausschussliste ueber mehr als eine Seite der Uebersicht. Mit hoechstens einer Seite gaebe
        es den Knopf nicht, und der Fall bestuende leer.

        Gezaehlt werden EINZELEINTRAEGE (offener Vorschlag ohne Gruppe): Eine Gruppe ist in der
        Uebersicht EIN Eintrag, gleich wie viele Fotos sie hat."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, LONG_AUSSCHUSS_PROJECT_NAME)
        photos = await _photos_of(db_session, LONG_AUSSCHUSS_PROJECT_NAME)
        scores = [await db_session.get(PhotoScore, photo.id) for photo in photos]

        einzeln_offen = [
            score
            for score in scores
            if score is not None
            and score.suggested_status == RatingStatus.REJECTED
            and score.duplicate_of is None
        ]
        assert len(einzeln_offen) == len(photos)
        assert len(einzeln_offen) > AUSSCHUSS_PAGE_SIZE
        assert (
            await db_session.execute(
                select(PhotoDuplicateDecision).where(
                    PhotoDuplicateDecision.photo_id.in_([photo.id for photo in photos])
                )
            )
        ).first() is None

        run = (
            await db_session.execute(select(ScoringRun).where(ScoringRun.project_id == project.id))
        ).scalar_one()
        assert run.status == ScanStatus.SUCCESS
        assert run.gate_confirmed_at is None
        assert run.suggestions_found == len(photos)

    async def test_the_duplicate_project_holds_two_reachable_groups(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """specs/features/0374-duplikate-vergleichen.md: Ohne diesen Bestand ist die
        Vergleichsansicht weder vorfuehrbar noch im Browser pruefbar, und kein Test wuerde rot.

        Geprueft ueber den STERN, nicht ueber eine abgeschriebene Id-Liste: Jede Gruppe hat genau
        einen Repraesentanten ohne `duplicate_of`, alle uebrigen Mitglieder zeigen auf ihn und
        tragen einen Ausschuss-Vorschlag.

        DER REPRAESENTANT TRAEGT NICHT MEHR ZWINGEND "kein Vorschlag" (Spec 0486): Genau eine der
        beiden Gruppen bricht das bewusst - ihr Gewinner ist selbst wegen Unschaerfe abgelehnt und
        damit das unveraenderliche Mitglied, an dem AK3 vorfuehrbar wird. Was fuer JEDEN
        Repraesentanten gilt, ist allein `duplicate_of is None`."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, DUPLICATE_PROJECT_NAME)
        scores = {photo.id: await db_session.get(PhotoScore, photo.id) for photo in photos}

        assert all(score is not None for score in scores.values())
        gruppen: dict[int, list[int]] = {}
        for photo_id, score in scores.items():
            assert score is not None
            representative = score.duplicate_of if score.duplicate_of is not None else photo_id
            gruppen.setdefault(representative, []).append(photo_id)

        assert sorted(len(members) for members in gruppen.values()) == sorted(
            (*demo_state.DEMO_DUPLICATE_GROUP_SIZES, demo_state.DEMO_AUTO_DECIDED_GROUP_SIZE)
        )
        for representative, members in gruppen.items():
            repraesentant = scores[representative]
            assert repraesentant is not None
            assert repraesentant.duplicate_of is None
            for member_id in members:
                score = scores[member_id]
                assert score is not None
                if member_id == representative:
                    continue
                assert score.duplicate_of == representative
                assert score.suggested_status == RatingStatus.REJECTED

    async def test_exactly_one_representative_is_itself_rejected_without_a_duplicate(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """AK3 muss im Browser vorfuehrbar sein: Ohne ein Mitglied, dessen Ausschuss NICHT aus dem
        Duplikat folgt, zeigt die Demo die Kachel ohne Wahlschaltflaechen nie.

        GENAU EINER, nicht "mindestens einer": Der andere Repraesentant traegt weiter keinen
        Vorschlag und belegt damit den Regelfall daneben - ohne ihn bliebe unbelegt, dass die
        Ansicht beide Faelle unterscheidet. Der Gewinner liegt zugleich unterhalb
        `SHARPNESS_REJECT_THRESHOLD`, damit der Bestand genau so aussieht, wie ihn ein echter Lauf
        hinterliesse."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, DUPLICATE_PROJECT_NAME)
        scores = [await db_session.get(PhotoScore, photo.id) for photo in photos]

        repraesentanten = [
            score for score in scores if score is not None and score.duplicate_of is None
        ]
        abgelehnt = [
            score for score in repraesentanten if score.suggested_status == RatingStatus.REJECTED
        ]

        assert len(repraesentanten) == (len(demo_state.DEMO_DUPLICATE_GROUP_SIZES) + 1)
        assert len(abgelehnt) == 1
        assert abgelehnt[0].sharpness < SHARPNESS_REJECT_THRESHOLD
        # Der Zeit-/Ortscluster wird nur fuer die NICHT aussortierten Fotos gesetzt - dieselbe
        # Regel wie im Lauf.
        assert abgelehnt[0].cluster_key is None

    async def test_the_auto_decided_group_has_one_marked_loser_and_no_decision_row(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Spec 0639: Die dritte Gruppe ist VOM LAUF entschieden, nicht von Hand.

        Genau ein Merker (der Verlierer), keine Entscheidungszeile, ein Gewinner ueber der
        Schaerfeschwelle mit hoeherer Aufloesung als der Verlierer - so saehe der Bestand nach
        einem echten Lauf aus. Alle Demo-Fotos tragen die Aufloesung samt Merker (Scan-Zustand).
        """
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, DUPLICATE_PROJECT_NAME)
        scores = {photo.id: await db_session.get(PhotoScore, photo.id) for photo in photos}

        assert all(photo.pixel_count is not None for photo in photos)
        assert all(photo.pixel_count_probed for photo in photos)

        markiert = [score for score in scores.values() if score is not None and score.auto_decided]
        assert len(markiert) == 1
        verlierer = markiert[0]
        assert verlierer.duplicate_of is not None
        assert verlierer.suggested_status == RatingStatus.REJECTED
        gewinner = scores[verlierer.duplicate_of]
        assert gewinner is not None
        assert gewinner.auto_decided is False
        assert gewinner.duplicate_of is None
        assert gewinner.sharpness >= SHARPNESS_REJECT_THRESHOLD
        assert (gewinner_photo := await db_session.get(Photo, gewinner.photo_id)) is not None
        verlierer_photo = await db_session.get(Photo, verlierer.photo_id)
        assert verlierer_photo is not None
        assert gewinner_photo.pixel_count is not None
        assert verlierer_photo.pixel_count is not None
        assert gewinner_photo.pixel_count > verlierer_photo.pixel_count

        zeilen = (
            (
                await db_session.execute(
                    select(PhotoDuplicateDecision).where(
                        PhotoDuplicateDecision.photo_id.in_([gewinner.photo_id, verlierer.photo_id])
                    )
                )
            )
            .scalars()
            .all()
        )
        assert zeilen == []

    async def test_the_run_counts_the_rejected_representative_among_its_suggestions(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """`suggestions_found` ist die Zahl der Aufnahmen mit Vorschlag, nicht die Zahl der
        Duplikat-Verlierer. Der selbst abgelehnte Repraesentant zaehlt mit - sonst nennte der
        Ausschuss-Schritt eine andere Zahl, als die Fotoliste unter dem Filter `suggested`
        zeigt."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, DUPLICATE_PROJECT_NAME)
        scores = [await db_session.get(PhotoScore, photo.id) for photo in photos]
        mit_vorschlag = sum(
            1 for score in scores if score is not None and score.suggested_status is not None
        )

        run = (
            await db_session.execute(
                select(ScoringRun).where(ScoringRun.project_id == photos[0].project_id)
            )
        ).scalar_one()

        assert run.suggestions_found == mit_vorschlag

    async def test_the_duplicate_project_leaves_every_group_undecided(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Demo-Bestand zeigt die Ansicht in ihrem ANFANGSZUSTAND: keine gespeicherte
        Entscheidung, die beiden grossen Gruppen offen. Eine mitgelieferte Entscheidung naehme
        der Sichtpruefung genau den Zustand, den sie zeigen soll - und der Gruppenzaehler der
        offenen Gruppen stuende nicht auf "1 von 2". Die automatische Gruppe steht daneben und
        braucht dafuer keine Zeile."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, DUPLICATE_PROJECT_NAME)

        entscheidungen = (
            (
                await db_session.execute(
                    select(PhotoDuplicateDecision).where(
                        PhotoDuplicateDecision.photo_id.in_([photo.id for photo in photos])
                    )
                )
            )
            .scalars()
            .all()
        )

        assert entscheidungen == []

    async def test_empty_project_exists_but_has_no_photos(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert await _photos_of(db_session, EMPTY_PROJECT_NAME) == []

    async def test_large_collection_uses_the_injected_count(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert len(await _photos_of(db_session, LARGE_PROJECT_NAME)) == 3

    async def test_every_motif_is_strong_on_at_least_one_photo_of_the_rated_project(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Ueber `MOTIF_REGISTRY` iteriert, nie als abgeschriebene Achterliste: ein neuntes Motiv
        darf nicht ungeprueft durchrutschen.

        Geprueft wird die STAERKE ueber der oberen Bandgrenze, nicht das blosse Vorhandensein
        einer Zeile: acht Zeilen entstehen fuer jedes beurteilte Foto ohnehin, und eine
        Statistiktabelle, in der eine Zeile nie etwas anderes als Nullen zeigt, laesst die
        Bandgrenzen in der Sichtpruefung unsichtbar."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]
        strong_keys = set(
            (
                await db_session.execute(
                    select(PhotoMotifStrength.motif_key).where(
                        PhotoMotifStrength.photo_id.in_(photo_ids),
                        PhotoMotifStrength.strength >= MOTIF_STRENGTH_BAND_STRONG,
                    )
                )
            ).scalars()
        )

        assert strong_keys == set(MOTIF_REGISTRY)

    async def test_rated_project_covers_every_album_decision_and_the_favorite_marker(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Zusicherung 24: `tuple(RatingStatus)` ist mit dem Wegfall von `favorite` STILL
        geschrumpft. Ohne diesen Fall legte der Seeder danach nur noch Albumentscheidungen an,
        und die Demo-Instanz verloere den Favoriten - sichtbar erst im Browser, nirgends rot.

        Geprueft wird die neue Zerlegung, je Nutzer: JEDE Albumentscheidung des Enums kommt vor,
        UND es gibt eine Zeile mit dem Kennzeichen NEBEN einer Albumentscheidung (der Zustand,
        den ADR 0098 neu ermoeglicht) UND eine mit AUSSCHLIESSLICH dem Kennzeichen."""
        await _make_user(db_session, "daniel")
        await _make_user(db_session, "zweiter-nutzer")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]
        rows = (
            (await db_session.execute(select(Rating).where(Rating.photo_id.in_(photo_ids))))
            .scalars()
            .all()
        )
        by_user: dict[int, list[Rating]] = {}
        for rating in rows:
            by_user.setdefault(rating.user_id, []).append(rating)

        assert len(by_user) == 2
        expected_statuses = {status.value for status in RatingStatus}
        for ratings in by_user.values():
            assert {r.status.value for r in ratings if r.status is not None} == expected_statuses
            assert any(r.favorite and r.status is not None for r in ratings)
            assert any(r.favorite and r.status is None for r in ratings)

    async def test_rated_project_has_an_open_rejection_suggestion(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        open_suggestions = []
        for photo in await _photos_of(db_session, RATED_PROJECT_NAME):
            score = await db_session.get(PhotoScore, photo.id)
            assert score is not None
            ratings = (
                (await db_session.execute(select(Rating).where(Rating.photo_id == photo.id)))
                .scalars()
                .all()
            )
            if score.suggested_status == RatingStatus.REJECTED and not ratings:
                open_suggestions.append(photo.id)
        assert len(open_suggestions) >= 1

    async def test_rated_project_has_a_criterion_run_with_criterion_scores(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, RATED_PROJECT_NAME)
        runs = (
            (
                await db_session.execute(
                    select(CriterionScoringRun).where(CriterionScoringRun.project_id == project.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(runs) == 1
        assert runs[0].status == ScanStatus.SUCCESS
        photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]
        scores = (
            (
                await db_session.execute(
                    select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id.in_(photo_ids))
                )
            )
            .scalars()
            .all()
        )
        assert {score.criterion_key for score in scores} == set(CRITERIA_REGISTRY)

    async def test_error_project_has_a_failed_run_with_a_non_empty_error_message(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, ERROR_PROJECT_NAME)
        runs = (
            (await db_session.execute(select(ScanRun).where(ScanRun.project_id == project.id)))
            .scalars()
            .all()
        )
        failed = [run for run in runs if run.status == ScanStatus.FAILED]
        assert len(failed) == 1
        assert failed[0].error_message is not None
        assert failed[0].error_message.strip() != ""

    async def test_error_project_names_the_failed_step_classification(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die angezeigte Meldung des gescheiterten Laufs nennt den Schritt mit seinem
        Namen in der Oberflaeche."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, ERROR_PROJECT_NAME)
        messages = (
            await db_session.execute(
                select(CriterionScoringRun.error_message).where(
                    CriterionScoringRun.project_id == project.id,
                    CriterionScoringRun.status == ScanStatus.FAILED,
                )
            )
        ).scalars()

        assert list(messages) == [
            "Klassifizierung abgebrochen (Demo-Fehlerzustand, kein echter Vorfall)."
        ]

    async def test_error_project_has_at_least_one_photo_without_cache_files(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, ERROR_PROJECT_NAME)
        without_cache = [
            photo for photo in photos if not thumbnail_path(tmp_path, photo.id, photo.etag).exists()
        ]
        assert len(without_cache) >= 1
        assert len(without_cache) < len(photos)

    async def test_error_project_has_at_least_one_cloud_vision_error_row(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photo_ids = [photo.id for photo in await _photos_of(db_session, ERROR_PROJECT_NAME)]
        errors = (
            (
                await db_session.execute(
                    select(PhotoCloudVisionError).where(
                        PhotoCloudVisionError.photo_id.in_(photo_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(errors) >= 1
        assert all(error.error_message.strip() != "" for error in errors)


class TestTheDemoPhotosCarryTheirAspectRatio:
    """Der Demo-Bestand bildet den Zustand NACH dem Scan ab (wie `camera_probed`). Ohne
    gespeichertes Verhaeltnis fiele jedes Demo-Foto im Raster auf die 3:2-Ausfallrichtung
    zurueck, und der E2E-Pruefstack saehe wieder lauter gleiche Formen."""

    async def test_a_photo_with_cache_files_carries_the_ratio_of_its_image(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=4)

        photos = await _photos_of(db_session, LARGE_PROJECT_NAME)
        assert len(photos) == 4
        for index, photo in enumerate(sorted(photos, key=lambda p: p.relative_path)):
            with Image.open(
                io.BytesIO(render_demo_image(slug="grosse-sammlung", index=index))
            ) as image:
                expected = image.width / image.height
            assert photo.aspect_ratio == pytest.approx(expected)

    async def test_the_large_collection_holds_at_least_three_different_ratios(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=8)

        photos = await _photos_of(db_session, LARGE_PROJECT_NAME)
        ratios = {round(photo.aspect_ratio, 4) for photo in photos if photo.aspect_ratio}
        assert len(ratios) >= 3

    async def test_a_photo_without_cache_files_carries_no_ratio(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Genau der Zustand, den ein echter Scan hinterlaesst, wenn die Vorschau nicht
        geschrieben werden konnte: kein Bild im Cache UND kein Verhaeltnis. Die Oberflaeche
        zeigt dafuer ihren Platzhalter und plant das Feld mit 3:2 ein."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        photos = await _photos_of(db_session, ERROR_PROJECT_NAME)
        without_cache = [
            photo for photo in photos if not thumbnail_path(tmp_path, photo.id, photo.etag).exists()
        ]
        assert without_cache
        assert all(photo.aspect_ratio is None for photo in without_cache)
        assert all(photo.aspect_ratio is not None for photo in photos if photo not in without_cache)


class TestRebuildDemoStateWritesRealThumbnails:
    """Bindung an die ECHTE thumbnails.py-Logik, gegen Drift getestet statt vorausgesetzt."""

    async def test_cache_files_lie_at_the_independently_computed_paths(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        # Der Test fragt NICHT den Seeder, wohin er geschrieben hat, sondern berechnet den Pfad
        # selbst ueber thumbnails.thumbnail_path()/display_path(). Aendert sich die
        # Cache-Schluessel-Bildung, wird der Seeder rot statt still abzudriften.
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, LARGE_PROJECT_NAME)
        assert len(photos) == 3
        for photo in photos:
            assert thumbnail_path(tmp_path, photo.id, photo.etag).is_file()
            assert display_path(tmp_path, photo.id, photo.etag).is_file()

    async def test_two_runs_in_separate_directories_produce_byte_identical_images(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        first_dir = tmp_path / "erster-lauf"
        second_dir = tmp_path / "zweiter-lauf"
        await rebuild_demo_state(db_session, first_dir, large_collection_photo_count=3)
        await rebuild_demo_state(db_session, second_dir, large_collection_photo_count=3)
        assert _cache_file_hashes(first_dir) != []
        assert _cache_file_hashes(first_dir) == _cache_file_hashes(second_dir)


class TestRebuildDemoStateIsTargetStateIdempotent:
    """Zielzustands-Idempotenz als Zustandsgleichheit, nicht als Abwesenheit eines Absturzes."""

    async def test_deliberately_corrupted_state_is_restored_exactly(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        expected = await _snapshot(db_session, tmp_path)

        # Zustand mutwillig verfaelschen: ein Foto loeschen, eine Bewertung aendern, ein
        # fuenftes Demo-Projekt anlegen, eine Cache-Datei loeschen.
        doomed = (await _photos_of(db_session, LARGE_PROJECT_NAME))[0]
        await db_session.execute(delete(PhotoScore).where(PhotoScore.photo_id == doomed.id))
        await db_session.execute(delete(Rating).where(Rating.photo_id == doomed.id))
        await db_session.execute(delete(Photo).where(Photo.id == doomed.id))
        rated_photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]
        rating = (
            (await db_session.execute(select(Rating).where(Rating.photo_id.in_(rated_photo_ids))))
            .scalars()
            .first()
        )
        assert rating is not None
        rating.status = RatingStatus.REJECTED
        db_session.add(
            Project(
                name=f"{DEMO_PROJECT_PREFIX}Rest aus einem alten Lauf",
                opencloud_drive_id="demo",
                opencloud_path="/demo",
            )
        )
        await db_session.flush()
        sorted(tmp_path.iterdir())[0].unlink()

        assert await _snapshot(db_session, tmp_path) != expected

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert await _snapshot(db_session, tmp_path) == expected


class TestRebuildDemoStateTouchesNothingElse:
    """M2: geloescht wird nur, was der Seeder selbst angelegt hat."""

    async def test_foreign_project_rows_and_cache_files_survive_a_rebuild(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        foreign_project, foreign_photo = await _make_foreign_project(db_session, tmp_path)
        foreign_thumbnail = thumbnail_path(tmp_path, foreign_photo.id, foreign_photo.etag)
        foreign_display = display_path(tmp_path, foreign_photo.id, foreign_photo.etag)
        assert foreign_thumbnail.is_file()

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        assert await db_session.get(Project, foreign_project.id) is not None
        assert await db_session.get(Photo, foreign_photo.id) is not None
        assert foreign_thumbnail.is_file()
        assert foreign_display.is_file()

    async def test_users_are_never_created_or_removed(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        # Der Seeder haengt Bewertungen an VORHANDENE Nutzer, legt aber selbst keinen an: ein
        # angelegtes Konto mit bekannten Zugangsdaten waere genau das Sicherheitsproblem, das die
        # Sperre verhindern soll.
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        usernames = (await db_session.execute(select(User.username))).scalars().all()
        assert usernames == ["daniel"]

    async def test_runs_without_any_user_and_writes_no_ratings(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert (await db_session.execute(select(Rating))).scalars().all() == []
        assert len(await _photos_of(db_session, RATED_PROJECT_NAME)) == len(MOTIF_REGISTRY)


class TestTheDemoStateNamesTwoInventedPersons:
    """Zwei erfundene Personen mit synthetischen Referenzen, Fotos in allen drei
    Zuordnungszustaenden und ein Name an der Laengengrenze - Stoff fuer Detailansicht, `/persons`
    und die Personen-Filtergruppe im Pruefstack. S14: kein echtes Gesicht, kein echter Name."""

    async def test_two_persons_carry_synthetic_unit_references_of_the_current_model(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        persons = (await db_session.execute(select(Person).order_by(Person.slot))).scalars().all()
        assert [person.name for person in persons] == list(DEMO_PERSON_NAMES)
        assert max(len(person.name) for person in persons) == MAX_NAME_CODE_POINTS
        references = (await db_session.execute(select(PersonReference))).scalars().all()
        assert {reference.person_id for reference in references} == {p.id for p in persons}
        assert all(reference.model_key == MODEL_KEY for reference in references)
        assert all(validated_embedding(reference.embedding) is not None for reference in references)
        # Synthetisch statt aus einem Gesicht: hoechstens zwei Achsen sind belegt.
        assert all(
            sum(1 for value in reference.embedding if value != 0.0) <= 2 for reference in references
        )

    async def test_the_rated_project_shows_recognized_hand_assigned_and_hand_removed(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]

        effective = await load_effective_persons(db_session, photo_ids)
        origins = {assignment.origin for rows in effective.values() for assignment in rows}
        assert origins == {"recognized", "corrected"}
        assert any(len(rows) == 2 for rows in effective.values())

        removed = (
            await db_session.execute(
                select(PhotoPersonCorrection.photo_id, PhotoPersonCorrection.person_id)
                .join(
                    PhotoPersonDetection,
                    (PhotoPersonDetection.photo_id == PhotoPersonCorrection.photo_id)
                    & (PhotoPersonDetection.person_id == PhotoPersonCorrection.person_id),
                )
                .where(
                    PhotoPersonCorrection.applies.is_(False),
                    PhotoPersonCorrection.photo_id.in_(photo_ids),
                )
            )
        ).all()
        assert removed
        for photo_id, person_id in removed:
            assert person_id not in {row.person_id for row in effective.get(photo_id, [])}

    async def test_a_detection_and_a_shown_correction_carry_a_synthetic_box(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Spec 0551: Im Pruefstack ist "Gesicht gezeigt" zu sehen - eine Korrektur mit Box und
        einer Referenz des AKTUELLEN Modells (sonst stuende sie auf "gewaehlt, nicht gelernt") -
        und eine Erkennung mit Box, deren "Name entfernen" das Gesicht freigibt."""
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photo_ids = [photo.id for photo in await _photos_of(db_session, RATED_PROJECT_NAME)]

        boxed_detections = (
            await db_session.execute(
                select(PhotoPersonDetection.photo_id).where(
                    PhotoPersonDetection.face_box_x.is_not(None),
                    PhotoPersonDetection.photo_id.in_(photo_ids),
                )
            )
        ).all()
        shown_models = (
            (
                await db_session.execute(
                    select(PersonReference.model_key)
                    .join(
                        PhotoPersonCorrection,
                        PhotoPersonCorrection.reference_id == PersonReference.id,
                    )
                    .where(
                        PhotoPersonCorrection.face_box_x.is_not(None),
                        PhotoPersonCorrection.photo_id.in_(photo_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        effective = await load_effective_persons(db_session, photo_ids)

        assert boxed_detections
        assert shown_models and set(shown_models) == {MODEL_KEY}
        assert "shown" in {row.face for rows in effective.values() for row in rows}

    async def test_a_second_rebuild_replaces_the_demo_persons_instead_of_hitting_the_limit(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        first_references = len((await db_session.execute(select(PersonReference))).all())

        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        names = (await db_session.execute(select(Person.name).order_by(Person.slot))).scalars()
        assert list(names) == list(DEMO_PERSON_NAMES)
        assert len((await db_session.execute(select(PersonReference))).all()) == first_references

    async def test_without_any_user_no_person_is_created(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        # Eine Person entsteht nur zusammen mit der Korrektur ihres gezeigten Gesichts, und die
        # braucht ein vorhandenes Konto - der Seeder legt nie selbst eines an.
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert (await db_session.execute(select(Person))).scalars().all() == []

    async def test_a_foreign_person_survives_and_the_rebuild_aborts(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        # M2 gilt auch fuer die globalen Personen: entfernt wird nur, was den Demo-Namen traegt.
        # Belegt eine fremde Person einen Slot, ist der Demo-Bestand nicht herstellbar - Abbruch
        # mit fachlicher Meldung statt eines Tracebacks aus dem Personendienst.
        await _make_user(db_session, "daniel")
        foreign = Person(slot=1, name="Echte Person", name_key="echte person")
        db_session.add(foreign)
        await db_session.flush()

        with pytest.raises(DemoStateError):
            await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        assert await db_session.get(Person, foreign.id) is not None


class TestRebuildDemoStateAtProductionSize:
    """Genau EIN Testfall faehrt die echte Vorgabe (Edge Case E6) - alle uebrigen laufen klein."""

    async def test_large_collection_reaches_the_named_constant_with_full_cache(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        summary = await rebuild_demo_state(db_session, tmp_path)
        photos = await _photos_of(db_session, LARGE_PROJECT_NAME)
        assert len(photos) == LARGE_COLLECTION_PHOTO_COUNT
        for photo in photos:
            assert thumbnail_path(tmp_path, photo.id, photo.etag).is_file()
            assert display_path(tmp_path, photo.id, photo.etag).is_file()
        assert summary.photo_count == (
            LARGE_COLLECTION_PHOTO_COUNT
            + len(MOTIF_REGISTRY)
            + ERROR_STATE_PHOTO_COUNT
            + sum(demo_state.DEMO_DUPLICATE_GROUP_SIZES)
            + demo_state.DEMO_AUTO_DECIDED_GROUP_SIZE
            + demo_state.LONG_AUSSCHUSS_PHOTO_COUNT
            + demo_state.OPERATIONS_PHOTO_COUNT
        )
