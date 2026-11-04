"""Spec 0609, Akzeptanzkriterium "Vergleich": das CLI `photosort.eye_comparison`.

Der Test traegt drei Zusagen:

1. die REINE Vergleichslogik (Schwelle, Zaehlungen, seeded Auswahl) - ohne Datenbank;
2. den LESEPFAD gegen eine In-Memory-Datenbank - nur Eye-, Cloud-, Motiv- und Albumspalten;
3. den FORMWAECHTER (S10): genau eine Schreibstelle, kein Logging, keine Namen, keine
   Einbindung in `main.py`/`worker.py`.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import null, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import eye_comparison
from photosort.eye_comparison import (
    DEVIATION_SAMPLE_LIMIT,
    CloudRunFacts,
    ComparisonReport,
    Deviation,
    EyeRunFacts,
    PhotoComparison,
    PurposeCounts,
    RunFacts,
    compare_motifs,
    counts_only,
    full_report,
    load_comparisons,
    load_run_facts,
    main,
    motif_present,
    summarize,
)
from photosort.models import (
    ClassificationMode,
    CriterionScoringRun,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoEyeMotifStrength,
    PhotoEyeResult,
    PhotoMotifAssessment,
    PhotoMotifStrength,
    Project,
    RemoteCategoryClassificationRun,
    ScanStatus,
    ScoringRun,
)
from photosort.selection import MOTIF_PRESENCE_THRESHOLD, motif_is_present

_MODULE_PATH = Path(eye_comparison.__file__)


def _photo(
    photo_id: int,
    *,
    cloud_motifs: dict[str, float] | None = None,
    eye_motifs: dict[str, float] | None = None,
    cloud_excluded: bool = False,
    eye_excluded: bool = False,
    cloud_album_level: int | None = 3,
    eye_album_level: int = 3,
    cloud_provider: str | None = "anthropic",
    eye_model_revision: str | None = "v1.0.0",
) -> PhotoComparison:
    return PhotoComparison(
        photo_id=photo_id,
        cloud_motifs=cloud_motifs if cloud_motifs is not None else {"menschen": 0.9},
        eye_motifs=eye_motifs if eye_motifs is not None else {"menschen": 0.9},
        cloud_excluded_document=cloud_excluded,
        eye_excluded_document=eye_excluded,
        cloud_album_level=cloud_album_level,
        eye_album_level=eye_album_level,
        cloud_provider=cloud_provider,
        eye_model_revision=eye_model_revision,
    )


def _runs(
    *,
    cloud_models: tuple[str, ...] = ("cloud-model",),
    cloud_run: CloudRunFacts | None = None,
    eye_run: EyeRunFacts | None = None,
    remote_api_calls_total: int | None = None,
) -> RunFacts:
    """Die Laufdaten einer `--out`-Datei, fest gesetzt - der Leser hat einen eigenen Test."""
    return RunFacts(
        cloud_models=cloud_models,
        cloud_run=cloud_run,
        eye_run=eye_run,
        remote_api_calls_total=remote_api_calls_total,
    )


async def _project_row(session: AsyncSession, name: str) -> Project:
    project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _photo_row(session: AsyncSession, project: Project, path: str) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=datetime(2023, 1, 1),
        taken_at_original=datetime(2023, 1, 1),
        last_modified=datetime(2023, 1, 1),
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _eye_row(
    session: AsyncSession,
    photo: Photo,
    *,
    revision: str = "v1.0.0",
    album_level: int = 4,
    excluded: bool = False,
    motifs: dict[str, float] | None = None,
) -> None:
    session.add(
        PhotoEyeResult(
            photo_id=photo.id,
            excluded_document=excluded,
            album_level=album_level,
            model_revision=revision,
            computed_at=datetime(2026, 9, 14, 9, 0, 0),
        )
    )
    await session.flush()
    for key, strength in (motifs or {"menschen": 0.8}).items():
        session.add(PhotoEyeMotifStrength(photo_id=photo.id, motif_key=key, strength=strength))
    await session.commit()


async def _cloud_row(
    session: AsyncSession,
    photo: Photo,
    *,
    provider: str | None = "anthropic",
    excluded: bool = False,
    album_level: int | None = 4,
    motifs: dict[str, float] | None = None,
) -> None:
    session.add(
        PhotoMotifAssessment(
            photo_id=photo.id,
            source=MotifAssessmentSource.CLOUD,
            excluded_document=excluded,
            provider=provider,
            computed_at=datetime(2026, 9, 14, 9, 0, 0),
        )
    )
    await session.flush()
    for key, strength in (motifs or {"menschen": 0.9}).items():
        session.add(PhotoMotifStrength(photo_id=photo.id, motif_key=key, strength=strength))
    if album_level is not None:
        session.add(
            PhotoAlbumSuitability(
                photo_id=photo.id,
                level=album_level,
                reason=None,
                provider=provider,
                computed_at=datetime(2026, 9, 14, 9, 0, 0),
            )
        )
    await session.commit()


async def _remote_row(
    session: AsyncSession,
    project: Project,
    *,
    status: ScanStatus = ScanStatus.SUCCESS,
    photos_total: int = 0,
    api_calls: int | None = 0,
    model: str | None = None,
) -> RemoteCategoryClassificationRun:
    run = RemoteCategoryClassificationRun(
        project_id=project.id,
        status=status,
        photos_total=photos_total,
        # `null()` statt `None`: die Spalte hat einen Python-Default 0, den ein explizites `None`
        # nicht ueberschreibt - eine "nicht erfasste" Zeile braucht das SQL-Literal.
        api_calls=null() if api_calls is None else api_calls,
        model=model,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _criterion_row(
    session: AsyncSession,
    project: Project,
    *,
    status: ScanStatus = ScanStatus.SUCCESS,
    started_at: datetime = datetime(2026, 9, 14, 9, 0, 0),
    finished_at: datetime | None = datetime(2026, 9, 14, 10, 0, 0),
    mode: ClassificationMode | None = None,
    remote_run_id: int | None = None,
    eye_photos_total: int | None = None,
    eye_photos_processed: int | None = None,
    landmark_api_calls: int | None = 0,
) -> CriterionScoringRun:
    scoring = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring.id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        mode=mode,
        remote_category_classification_run_id=remote_run_id,
        eye_photos_total=eye_photos_total,
        eye_photos_processed=eye_photos_processed,
        landmark_api_calls=landmark_api_calls,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


class TestTheThreshold:
    """Der Vergleich entscheidet die Grenze NICHT selbst: er ruft das geteilte Praedikat aus
    `selection.py`. Ein Test gegen die dortige Konstante haelt fest, dass die Zuordnung
    Schluessel -> Staerke nichts Eigenes dazwischenschiebt."""

    def test_the_shared_threshold_is_inclusive(self) -> None:
        assert motif_present({"menschen": MOTIF_PRESENCE_THRESHOLD}, "menschen")
        assert not motif_present({"menschen": MOTIF_PRESENCE_THRESHOLD - 0.01}, "menschen")

    def test_the_helper_delegates_to_the_shared_predicate(self) -> None:
        for strength in (0.0, 0.49, 0.5, 0.51, 1.0):
            assert motif_present({"menschen": strength}, "menschen") is motif_is_present(strength)

    def test_a_missing_strength_means_not_present(self) -> None:
        # Dieselbe Regel wie im Lesepfad: eine fehlende Zeile ist "nicht vorhanden", nie
        # "unbekannt". Zwei unbekannte Seiten als Abweichung zu zaehlen waere eine Aussage ueber
        # Daten, die es nicht gibt.
        assert not motif_present({}, "menschen")


class TestTheMotifComparison:
    def test_counts_matching_and_deviating_presence_decisions(self) -> None:
        cloud = {"menschen": 0.9, "natur": 0.2, "wasser": 0.61}
        eye = {"menschen": 0.9, "natur": 0.8, "wasser": 0.59}

        # menschen: beide vorhanden (Uebereinstimmung). natur: nur Eye (Abweichung).
        # wasser: Cloud 0.61 vorhanden, Eye 0.59 vorhanden (Uebereinstimmung).
        assert compare_motifs(cloud, eye) == (2, 1)

    def test_compares_over_the_union_of_keys(self) -> None:
        # Eine auf einer Seite fehlende Zeile ist "nicht vorhanden" - der Schnitt uebersaehe
        # genau die Faelle, in denen eine Seite das Motiv gar nicht beurteilt hat.
        assert compare_motifs({"menschen": 0.9}, {}) == (0, 1)
        assert compare_motifs({}, {"menschen": 0.9}) == (0, 1)


class TestTheSummary:
    def test_counts_each_purpose_separately(self) -> None:
        report = summarize(
            [
                _photo(1),
                _photo(2, cloud_excluded=True),
                _photo(3, cloud_album_level=2, eye_album_level=4),
                _photo(4, cloud_album_level=None),
            ],
            seed=0,
        )

        assert report.photos_compared == 4
        assert report.motifs == PurposeCounts(compared=4, matching=4, deviating=0)
        assert report.excluded_document == PurposeCounts(compared=4, matching=3, deviating=1)
        # Foto 4 hat KEINE Albumtauglichkeitszeile - es faellt aus dem Vergleich, statt als
        # Abweichung gezaehlt zu werden.
        assert report.album_level == PurposeCounts(compared=3, matching=2, deviating=1)

    def test_names_deviation_rows_by_photo_and_purpose(self) -> None:
        report = summarize([_photo(7, eye_excluded=True)], seed=0)

        # Die Frage dieses Tests ist "welche Zeile wird benannt", nicht das Wertepaar - die Form
        # ueberlebt damit auch die naechste Feld-Erweiterung von `Deviation`.
        assert [(row.photo_id, row.purpose) for row in report.deviations] == [
            (7, "excluded_document")
        ]

    def test_an_empty_project_reports_zeroes(self) -> None:
        report = summarize([], seed=0)

        assert report.photos_compared == 0
        assert report.motifs == PurposeCounts(0, 0, 0)
        assert report.deviations == ()


class TestTheDeviationValues:
    """Jede Abweichungszeile traegt BEIDE Werte ihres Zwecks, roh und ungerundet.

    Gezaehlt wird weiter ausschliesslich ueber `motif_is_present`; die Grenze bleibt an einer
    Stelle. `null` steht dort, wo der Zweck das Paar nicht fuehrt ODER die Seite den Schluessel
    nicht beurteilt hat - "nicht beurteilt" ist nicht "als 0.0 beurteilt"."""

    def test_a_motif_row_carries_both_raw_strengths_unrounded(self) -> None:
        report = summarize(
            [_photo(1, cloud_motifs={"menschen": 0.123456789}, eye_motifs={"menschen": 0.9})],
            seed=0,
        )

        assert report.deviations[0].cloud_strength == 0.123456789
        assert report.deviations[0].eye_strength == 0.9
        assert full_report(report, _runs(), project_id=1)["deviations"] == [
            {
                "photo_id": 1,
                "purpose": "motifs",
                "motif_key": "menschen",
                "cloud_strength": 0.123456789,
                "eye_strength": 0.9,
                "cloud_excluded_document": None,
                "eye_excluded_document": None,
                "cloud_album_level": None,
                "eye_album_level": None,
                "path": "/projects/1/photos/1",
            }
        ]

    def test_exactly_the_threshold_on_both_sides_is_a_match(self) -> None:
        report = summarize(
            [
                _photo(
                    1,
                    cloud_motifs={"menschen": MOTIF_PRESENCE_THRESHOLD},
                    eye_motifs={"menschen": MOTIF_PRESENCE_THRESHOLD},
                )
            ],
            seed=0,
        )

        assert report.deviations == ()
        assert report.motifs == PurposeCounts(compared=1, matching=1, deviating=0)

    def test_just_below_the_threshold_is_a_row_with_both_raw_values(self) -> None:
        report = summarize(
            [_photo(2, cloud_motifs={"menschen": 0.5}, eye_motifs={"menschen": 0.4999999})],
            seed=0,
        )

        assert [(row.cloud_strength, row.eye_strength) for row in report.deviations] == [
            (0.5, 0.4999999)
        ]

    def test_a_missing_side_is_null_never_zero(self) -> None:
        report = summarize(
            [_photo(3, cloud_motifs={"menschen": 0.9}, eye_motifs={"natur": 0.9})],
            seed=0,
        )

        [row] = [row for row in report.deviations if row.motif_key == "natur"]
        assert row.cloud_strength is None
        assert row.eye_strength == 0.9

    def test_an_excluded_row_carries_both_bools_and_nulls_elsewhere(self) -> None:
        report = summarize([_photo(4, cloud_excluded=False, eye_excluded=True)], seed=0)

        assert full_report(report, _runs(), project_id=1)["deviations"] == [
            {
                "photo_id": 4,
                "purpose": "excluded_document",
                "motif_key": None,
                "cloud_strength": None,
                "eye_strength": None,
                "cloud_excluded_document": False,
                "eye_excluded_document": True,
                "cloud_album_level": None,
                "eye_album_level": None,
                "path": "/projects/1/photos/4",
            }
        ]

    def test_an_album_row_carries_both_levels_as_int(self) -> None:
        report = summarize([_photo(5, cloud_album_level=2, eye_album_level=4)], seed=0)

        [row] = report.deviations
        assert (row.cloud_album_level, row.eye_album_level) == (2, 4)
        assert (row.cloud_strength, row.eye_strength) == (None, None)
        assert (row.cloud_excluded_document, row.eye_excluded_document) == (None, None)

    def test_a_photo_without_a_cloud_album_level_stays_out_of_the_album_comparison(self) -> None:
        report = summarize([_photo(6, cloud_album_level=None, eye_album_level=4)], seed=0)

        assert report.album_level == PurposeCounts(compared=0, matching=0, deviating=0)
        assert report.deviations == ()

    def test_a_forgotten_value_field_fails_at_construction(self) -> None:
        # Kein Vorgabewert: ein in `summarize` vergessenes Setzen scheitert beim BAU, statt als
        # stilles `null` in die Datei zu gehen.
        with pytest.raises(TypeError):
            Deviation(  # type: ignore[call-arg]
                photo_id=1,
                purpose="motifs",
                motif_key="menschen",
            )


class TestTheSeededSelection:
    def _many_deviations(self, count: int) -> list[PhotoComparison]:
        return [_photo(photo_id, eye_excluded=True) for photo_id in range(1, count + 1)]

    def test_the_same_seed_selects_the_same_rows(self) -> None:
        photos = self._many_deviations(100)

        first = summarize(photos, seed=17)
        second = summarize(photos, seed=17)

        assert first.deviations == second.deviations
        assert len(first.deviations) == DEVIATION_SAMPLE_LIMIT

    def test_different_seeds_select_different_rows(self) -> None:
        photos = self._many_deviations(100)

        assert summarize(photos, seed=1).deviations != summarize(photos, seed=2).deviations

    def test_never_more_rows_than_there_are_deviations(self) -> None:
        report = summarize(self._many_deviations(3), seed=5)

        assert len(report.deviations) == 3

    def test_the_selection_is_sorted_for_stable_files(self) -> None:
        report = summarize(self._many_deviations(50), seed=3)

        keys = [(row.photo_id, row.purpose, row.motif_key or "") for row in report.deviations]
        assert keys == sorted(keys)

    def test_the_selection_of_the_previous_stand_is_unchanged(self) -> None:
        # Pin, aufgenommen VOR der Felderweiterung: dieselbe Seed waehlt dieselben Zeilen. Die
        # neuen Wertepaare haengen an der Zeile, nicht am Zufallsstrom.
        report = summarize(self._many_deviations(100), seed=17)

        assert [row.photo_id for row in report.deviations] == [
            4,
            8,
            15,
            18,
            20,
            23,
            26,
            27,
            32,
            33,
            36,
            38,
            39,
            41,
            43,
            47,
            50,
            52,
            54,
            65,
            67,
            69,
            70,
            71,
            72,
            80,
            85,
            91,
            94,
            99,
        ]


class TestThePerPurposeLimit:
    """ADR 0138 Punkt 8: die Auswahl ist JE ZWECK gedeckelt. Eine Gesamtgrenze liesse dreissig
    Motiv-Abweichungen den Platz von Ausschluss und Albumstufe fressen - genau der Zwecke, fuer
    die das Werkzeug existiert."""

    @staticmethod
    def _motif_deviations(count: int, *, offset: int = 0) -> list[PhotoComparison]:
        return [
            _photo(offset + index, eye_motifs={"menschen": 0.1}) for index in range(1, count + 1)
        ]

    @staticmethod
    def _album_deviations(count: int, *, offset: int = 0) -> list[PhotoComparison]:
        return [
            _photo(offset + index, cloud_album_level=2, eye_album_level=4)
            for index in range(1, count + 1)
        ]

    def test_every_purpose_keeps_its_own_thirty_rows(self) -> None:
        photos = (
            self._motif_deviations(40)
            + self._album_deviations(5, offset=100)
            + [_photo(200 + index, eye_excluded=True) for index in range(1, 4)]
        )

        report = summarize(photos, seed=0)

        purposes = [row.purpose for row in report.deviations]
        assert purposes.count("motifs") == DEVIATION_SAMPLE_LIMIT
        assert purposes.count("album_level") == 5
        assert purposes.count("excluded_document") == 3
        assert set(purposes) == {"motifs", "album_level", "excluded_document"}

    def test_a_purpose_below_the_limit_contributes_all_its_rows(self) -> None:
        report = summarize(self._album_deviations(4), seed=0)

        assert len(report.deviations) == 4
        assert {row.purpose for row in report.deviations} == {"album_level"}

    def test_the_per_purpose_selection_is_seed_deterministic(self) -> None:
        photos = self._motif_deviations(90) + self._album_deviations(40, offset=100)

        first = summarize(photos, seed=7)
        second = summarize(photos, seed=7)

        assert first.deviations == second.deviations
        assert summarize(photos, seed=8).deviations != first.deviations


class TestTheOutputShape:
    def _report(self) -> ComparisonReport:
        return summarize([_photo(9, cloud_excluded=True)], seed=0)

    def _runs(self) -> RunFacts:
        return _runs(
            cloud_run=CloudRunFacts(
                duration_seconds=90, remote_photos_total=12, remote_api_calls=7
            ),
            eye_run=EyeRunFacts(duration_seconds=42, eye_photos_total=12, eye_photos_processed=11),
            remote_api_calls_total=7,
        )

    def test_stdout_carries_only_counts(self) -> None:
        payload = counts_only(self._report())

        assert set(payload) == {
            "photos_compared",
            "motifs",
            "excluded_document",
            "album_level",
        }
        assert "deviations" not in payload
        # Die Laufdaten bleiben der Datei vorbehalten - eine Konsole ist fluechtig.
        assert "origin" not in payload
        assert "runtime" not in payload

    def test_the_file_report_has_a_fixed_key_set_without_a_verdict_field(self) -> None:
        payload = full_report(self._report(), self._runs(), project_id=4)

        assert set(payload) == {
            "project_id",
            "photos_compared",
            "motifs",
            "excluded_document",
            "album_level",
            "origin",
            "runtime",
            "deviations",
        }
        # Kein Feld traegt eine Empfehlung oder ein Gesamturteil - die Entscheidung bleibt bei
        # der lesenden Person.
        assert not {"verdict", "recommendation", "recommended", "score"} & set(payload)

    def test_the_file_report_carries_no_timestamp(self) -> None:
        payload = full_report(self._report(), self._runs(), project_id=4)

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | {inner for item in value.values() for inner in keys(item)}
            if isinstance(value, list):
                return {inner for item in value for inner in keys(item)}
            return set()

        # Nur Dauern, keine Zeitpunkte: ein Zeitpunkt waere das Muster, wann der Haushalt nicht
        # zu Hause war. `finished_at`/`started_at` werden zum AUSWAEHLEN gelesen, nie ausgegeben.
        assert not [key for key in keys(payload) if key.endswith("_at") or key == "timestamp"]
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", json.dumps(payload))

    def test_deviations_carry_photo_id_and_app_path(self) -> None:
        payload = full_report(self._report(), self._runs(), project_id=4)

        assert payload["deviations"] == [
            {
                "photo_id": 9,
                "purpose": "excluded_document",
                "motif_key": None,
                "cloud_strength": None,
                "eye_strength": None,
                "cloud_excluded_document": True,
                "eye_excluded_document": False,
                "cloud_album_level": None,
                "eye_album_level": None,
                "path": "/projects/4/photos/9",
            }
        ]


class TestTheOrigin:
    """`origin` nennt drei Listen, nie `null` - und die Bezugsmengen sind getrennt: Anbieter und
    Revisionen stammen aus den VERGLICHENEN Fotos, Modelle aus allen erfolgreichen Remote-Laeufen
    des Projekts.

    `NULL` faellt weg, statt als Leerstring zu erscheinen: eine nicht erfasste Kennung ist keine
    Aussage. `[]` heisst "kein Wert erfasst", nicht "fand nicht statt"."""

    def test_providers_come_from_the_compared_photos_sorted_and_deduplicated(self) -> None:
        report = summarize(
            [
                _photo(1, cloud_provider="openai"),
                _photo(2, cloud_provider="anthropic"),
                _photo(3, cloud_provider="openai"),
                _photo(4, cloud_provider=None),
            ],
            seed=0,
        )

        assert full_report(report, _runs(), project_id=1)["origin"] == {
            "cloud_providers": ["anthropic", "openai"],
            "cloud_models": ["cloud-model"],
            "eye_model_revisions": ["v1.0.0"],
        }

    def test_revisions_come_from_the_compared_eye_rows(self) -> None:
        report = summarize(
            [
                _photo(1, eye_model_revision="v2.0.0"),
                _photo(2, eye_model_revision="v1.0.0"),
                _photo(3, eye_model_revision="v2.0.0"),
            ],
            seed=0,
        )

        assert full_report(report, _runs(), project_id=1)["origin"]["eye_model_revisions"] == [
            "v1.0.0",
            "v2.0.0",
        ]

    def test_nothing_to_collect_is_three_empty_lists_never_null(self) -> None:
        origin = full_report(summarize([], seed=0), _runs(cloud_models=()), project_id=1)["origin"]

        assert origin == {
            "cloud_providers": [],
            "cloud_models": [],
            "eye_model_revisions": [],
        }

    async def test_the_compared_photos_name_their_provider_and_revision(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Anbieter")
        both = await _photo_row(db_session, project, "beide.jpg")
        await _eye_row(db_session, both, revision="v1.0.0")
        await _cloud_row(db_session, both, provider="anthropic")
        # Kopfzeile ohne Eye-Zeile: das Foto wird NICHT verglichen und traegt nichts bei.
        cloud_only = await _photo_row(db_session, project, "nur-cloud.jpg")
        await _cloud_row(db_session, cloud_only, provider="unbeteiligt")

        report = summarize(await load_comparisons(db_session, project.id), seed=0)
        facts = await load_run_facts(db_session, project.id)

        assert full_report(report, facts, project_id=project.id)["origin"] == {
            "cloud_providers": ["anthropic"],
            "cloud_models": [],
            "eye_model_revisions": ["v1.0.0"],
        }

    async def test_models_come_from_every_successful_remote_run(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Modelle")
        await _remote_row(db_session, project, model="gpt-4o")
        await _remote_row(db_session, project, model="claude-3")
        await _remote_row(db_session, project, model="gpt-4o")
        await _remote_row(db_session, project, model=None)
        # Ein fehlgeschlagener Lauf traegt kein Modell bei: er hat keines belegt.
        await _remote_row(db_session, project, status=ScanStatus.FAILED, model="fehlschlag")

        facts = await load_run_facts(db_session, project.id)

        assert facts.cloud_models == ("claude-3", "gpt-4o")

    async def test_a_successful_remote_run_without_a_compared_photo_still_names_its_model(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Ohne Fotos")
        await _remote_row(db_session, project, model="claude-3")

        report = summarize(await load_comparisons(db_session, project.id), seed=0)
        facts = await load_run_facts(db_session, project.id)

        assert full_report(report, facts, project_id=project.id)["origin"] == {
            "cloud_providers": [],
            "cloud_models": ["claude-3"],
            "eye_model_revisions": [],
        }

    async def test_a_second_project_contributes_nothing(self, db_session: AsyncSession) -> None:
        mine = await _project_row(db_session, "Meins")
        other = await _project_row(db_session, "Fremd")
        photo = await _photo_row(db_session, other, "fremd.jpg")
        await _eye_row(db_session, photo, revision="v9.9.9")
        await _cloud_row(db_session, photo, provider="fremd-anbieter")
        await _remote_row(db_session, other, model="fremd-modell")

        facts = await load_run_facts(db_session, mine.id)

        assert facts.cloud_models == ()
        assert facts.cloud_run is None
        assert facts.eye_run is None
        assert facts.remote_api_calls_total is None


class TestTheRuntime:
    """Die Form der beiden Laufbloecke: fehlt ein Lauf, ist das Objekt `null`.

    Kein Zeitpunkt in der Ausgabe - nur `duration_seconds`."""

    def test_a_missing_run_is_null_not_an_empty_object(self) -> None:
        runtime = full_report(summarize([], seed=0), _runs(cloud_models=()), project_id=1)[
            "runtime"
        ]

        assert runtime == {
            "cloud_run": None,
            "eye_run": None,
            "remote_api_calls_total": None,
        }

    def test_the_cloud_block_names_its_three_fields(self) -> None:
        runs = _runs(
            cloud_run=CloudRunFacts(
                duration_seconds=3600, remote_photos_total=40, remote_api_calls=None
            ),
        )

        assert full_report(summarize([], seed=0), runs, project_id=1)["runtime"]["cloud_run"] == {
            "duration_seconds": 3600,
            "remote_photos_total": 40,
            "remote_api_calls": None,
        }

    def test_the_eye_block_names_its_three_fields_and_keeps_null(self) -> None:
        runs = _runs(
            eye_run=EyeRunFacts(
                duration_seconds=42, eye_photos_total=None, eye_photos_processed=None
            ),
        )

        # `NULL` heisst "Phase nicht betreten" - eine 0 waere eine erfundene Messung.
        assert full_report(summarize([], seed=0), runs, project_id=1)["runtime"]["eye_run"] == {
            "duration_seconds": 42,
            "eye_photos_total": None,
            "eye_photos_processed": None,
        }


class TestTheOutFileGuard:
    def test_an_out_path_inside_the_repository_is_rejected_without_writing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Ein Pfad INNERHALB des Repos: genau der Fall, in dem Eye-Ergebnisse versehentlich in die
        # Versionsverwaltung wandern wuerden.
        repository_root = Path(__file__).resolve().parents[2]
        target = repository_root / "eye-vergleich-nie-angelegt.json"
        assert not target.exists()

        exit_code = main(["--project-id", "1", "--out", str(target)])

        assert exit_code != 0
        assert not target.exists()

    def test_an_out_path_outside_the_repository_is_accepted(self, tmp_path: Path) -> None:
        target = tmp_path / "vergleich.json"

        assert eye_comparison._resolve_out(target) == target.resolve()

    def test_any_worktree_above_the_target_is_rejected(self, tmp_path: Path) -> None:
        # Nicht nur DIESES Repository: jedes `.git` ueber dem Ziel ist ein Arbeitsbaum, dessen
        # Inhalt sonst in die Versionsverwaltung wanderte.
        (tmp_path / ".git").mkdir()
        target = tmp_path / "unterordner" / "vergleich.json"

        with pytest.raises(ValueError, match="AUSSERHALB"):
            eye_comparison._resolve_out(target)

    def test_the_package_location_does_not_decide_about_the_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Der Container-Fall: das Paket liegt installiert unter `site-packages` ohne Arbeitsbaum
        # darueber, das Ziel unter /tmp. Wird die Grenze ab dem Paket gemessen, gilt `/` als
        # Repo-Wurzel und JEDES Ziel wird abgelehnt - auch das dokumentierte `/tmp/...`.
        paket = tmp_path / "site-packages" / "photosort" / "eye_comparison.py"
        monkeypatch.setattr(eye_comparison, "__file__", str(paket))
        ziel = tmp_path / "ausgabe" / "vergleich.json"

        assert eye_comparison._resolve_out(ziel) == ziel.resolve()


class TestTheReadPath:
    async def _project(self, session: AsyncSession) -> Project:
        project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project

    async def _photo(self, session: AsyncSession, project: Project, path: str) -> Photo:
        photo = Photo(
            project_id=project.id,
            relative_path=path,
            etag=f"etag-{path}",
            content_length=100,
            taken_at=datetime(2023, 1, 1),
            taken_at_original=datetime(2023, 1, 1),
            last_modified=datetime(2023, 1, 1),
        )
        session.add(photo)
        await session.commit()
        await session.refresh(photo)
        return photo

    async def test_compares_only_photos_with_both_bases(self, db_session: AsyncSession) -> None:
        project = await self._project(db_session)
        both = await self._photo(db_session, project, "beide.jpg")
        eye_only = await self._photo(db_session, project, "nur-eye.jpg")

        for photo, with_cloud in ((both, True), (eye_only, False)):
            db_session.add(
                PhotoEyeResult(
                    photo_id=photo.id,
                    excluded_document=False,
                    album_level=4,
                    model_revision="v1.0.0",
                    computed_at=datetime(2026, 9, 14, 9, 0, 0),
                )
            )
            await db_session.flush()
            db_session.add(
                PhotoEyeMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.8)
            )
            if with_cloud:
                db_session.add(
                    PhotoMotifAssessment(
                        photo_id=photo.id,
                        source=MotifAssessmentSource.CLOUD,
                        excluded_document=False,
                        provider="anthropic",
                        computed_at=datetime(2026, 9, 14, 9, 0, 0),
                    )
                )
                await db_session.flush()
                db_session.add(
                    PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.9)
                )
                db_session.add(
                    PhotoAlbumSuitability(
                        photo_id=photo.id,
                        level=4,
                        reason=None,
                        provider="anthropic",
                        computed_at=datetime(2026, 9, 14, 9, 0, 0),
                    )
                )
        await db_session.commit()

        comparisons = await load_comparisons(db_session, project.id)

        assert [item.photo_id for item in comparisons] == [both.id]
        assert comparisons[0].cloud_motifs == {"menschen": 0.9}
        assert comparisons[0].eye_motifs == {"menschen": 0.8}
        assert comparisons[0].cloud_album_level == 4
        assert comparisons[0].eye_album_level == 4

    async def test_ignores_an_eye_header_without_cloud_header(
        self, db_session: AsyncSession
    ) -> None:
        project = await self._project(db_session)
        photo = await self._photo(db_session, project, "a.jpg")
        db_session.add(
            PhotoEyeResult(
                photo_id=photo.id,
                excluded_document=False,
                album_level=2,
                model_revision="v1.0.0",
                computed_at=datetime(2026, 9, 14, 9, 0, 0),
            )
        )
        await db_session.commit()

        assert await load_comparisons(db_session, project.id) == []

    async def test_does_not_touch_the_write_path(self, db_session: AsyncSession) -> None:
        project = await self._project(db_session)
        photo = await self._photo(db_session, project, "a.jpg")
        db_session.add(
            PhotoEyeResult(
                photo_id=photo.id,
                excluded_document=False,
                album_level=2,
                model_revision="v1.0.0",
                computed_at=datetime(2026, 9, 14, 9, 0, 0),
            )
        )
        await db_session.commit()

        await load_comparisons(db_session, project.id)

        # Der Vergleich liest: die Zeile steht unveraendert, und nichts wurde geloescht.
        stored = (
            await db_session.execute(
                select(PhotoEyeResult).where(PhotoEyeResult.photo_id == photo.id)
            )
        ).scalar_one()
        assert stored.album_level == 2


class TestTheRunSelection:
    """Welcher Lauf zaehlt: gefiltert wird VOR der Ordnung, sonst verdraengte ein neuerer
    unpassender Lauf den aelteren gueltigen."""

    async def test_a_newer_run_without_a_successful_remote_run_does_not_displace_the_valid_one(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Verdraengung")
        failed_remote = await _remote_row(db_session, project, status=ScanStatus.FAILED)
        valid_remote = await _remote_row(db_session, project, photos_total=40, api_calls=9)
        await _criterion_row(
            db_session,
            project,
            finished_at=datetime(2026, 9, 14, 10, 0, 0),
            remote_run_id=valid_remote.id,
        )
        await _criterion_row(
            db_session,
            project,
            finished_at=datetime(2026, 9, 14, 12, 0, 0),
            remote_run_id=failed_remote.id,
        )

        facts = await load_run_facts(db_session, project.id)

        assert facts.cloud_run == CloudRunFacts(
            duration_seconds=3600, remote_photos_total=40, remote_api_calls=9
        )

    async def test_a_run_without_finished_at_is_never_chosen(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Ohne Ende")
        remote = await _remote_row(db_session, project)
        await _criterion_row(db_session, project, finished_at=None, remote_run_id=remote.id)

        facts = await load_run_facts(db_session, project.id)

        assert facts.cloud_run is None

    async def test_a_failed_run_is_never_chosen(self, db_session: AsyncSession) -> None:
        project = await _project_row(db_session, "Fehlschlag")
        remote = await _remote_row(db_session, project)
        await _criterion_row(db_session, project, status=ScanStatus.FAILED, remote_run_id=remote.id)

        assert (await load_run_facts(db_session, project.id)).cloud_run is None

    async def test_a_run_without_a_remote_run_is_never_chosen(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Ohne Remote")
        await _criterion_row(db_session, project, remote_run_id=None)

        assert (await load_run_facts(db_session, project.id)).cloud_run is None

    async def test_the_numbers_come_from_the_linked_remote_run_not_the_newest_one(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Verknuepft")
        linked = await _remote_row(db_session, project, photos_total=5, api_calls=3)
        # Ein juengerer Remote-Lauf desselben Projekts, aber nicht der verknuepfte.
        await _remote_row(db_session, project, photos_total=100, api_calls=99)
        await _criterion_row(db_session, project, remote_run_id=linked.id)

        facts = await load_run_facts(db_session, project.id)

        assert facts.cloud_run == CloudRunFacts(
            duration_seconds=3600, remote_photos_total=5, remote_api_calls=3
        )

    async def test_a_tie_on_finished_at_is_broken_by_the_higher_id(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Gleichstand")
        first_remote = await _remote_row(db_session, project, api_calls=1)
        second_remote = await _remote_row(db_session, project, api_calls=2)
        tie = datetime(2026, 9, 14, 10, 0, 0)
        await _criterion_row(db_session, project, finished_at=tie, remote_run_id=first_remote.id)
        await _criterion_row(db_session, project, finished_at=tie, remote_run_id=second_remote.id)

        facts = await load_run_facts(db_session, project.id)

        assert facts.cloud_run is not None
        assert facts.cloud_run.remote_api_calls == 2

    async def test_a_legacy_row_without_a_mode_counts_as_a_cloud_run(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Altzeile")
        remote = await _remote_row(db_session, project, api_calls=4)
        await _criterion_row(db_session, project, mode=None, remote_run_id=remote.id)

        facts = await load_run_facts(db_session, project.id)

        assert facts.cloud_run is not None
        assert facts.cloud_run.remote_api_calls == 4

    async def test_the_newest_successful_eye_run_is_chosen(self, db_session: AsyncSession) -> None:
        project = await _project_row(db_session, "Eye")
        await _criterion_row(
            db_session,
            project,
            mode=ClassificationMode.EYE,
            finished_at=datetime(2026, 9, 14, 10, 0, 0),
            eye_photos_total=3,
            eye_photos_processed=3,
        )
        await _criterion_row(
            db_session,
            project,
            mode=ClassificationMode.EYE,
            started_at=datetime(2026, 9, 15, 8, 30, 0),
            finished_at=datetime(2026, 9, 15, 8, 31, 30, 500000),
            eye_photos_total=120,
            eye_photos_processed=118,
        )

        facts = await load_run_facts(db_session, project.id)

        assert facts.eye_run == EyeRunFacts(
            duration_seconds=90, eye_photos_total=120, eye_photos_processed=118
        )

    async def test_a_non_eye_mode_is_never_the_eye_run(self, db_session: AsyncSession) -> None:
        project = await _project_row(db_session, "Nicht-Eye")
        await _criterion_row(
            db_session,
            project,
            mode=ClassificationMode.LOCAL,
            eye_photos_total=40,
            eye_photos_processed=40,
        )

        assert (await load_run_facts(db_session, project.id)).eye_run is None

    async def test_a_legacy_row_is_never_an_eye_run(self, db_session: AsyncSession) -> None:
        # `mode IS NULL` heisst "vor der Laufwahl" - die gefuellten `eye_photos_*` machen daraus
        # keinen Eye-Lauf.
        project = await _project_row(db_session, "Alt ohne Modus")
        await _criterion_row(
            db_session, project, mode=None, eye_photos_total=40, eye_photos_processed=40
        )

        assert (await load_run_facts(db_session, project.id)).eye_run is None

    async def test_the_duration_is_a_whole_truncated_second(self, db_session: AsyncSession) -> None:
        project = await _project_row(db_session, "Dauer")
        remote = await _remote_row(db_session, project)
        await _criterion_row(
            db_session,
            project,
            started_at=datetime(2026, 9, 14, 10, 0, 0),
            finished_at=datetime(2026, 9, 14, 10, 1, 30, 700000),
            remote_run_id=remote.id,
        )

        facts = await load_run_facts(db_session, project.id)

        assert facts.cloud_run is not None
        assert isinstance(facts.cloud_run.duration_seconds, int)
        # Abgeschnitten, nicht gerundet - 90,7 s sind 90 s, keine 91.
        assert facts.cloud_run.duration_seconds == 90

    async def test_a_negative_duration_stays_visible(self, db_session: AsyncSession) -> None:
        # Ein Uhrensprung ist ein Befund; eine 0 waere eine erfundene Messung.
        project = await _project_row(db_session, "Uhrsprung")
        remote = await _remote_row(db_session, project)
        await _criterion_row(
            db_session,
            project,
            started_at=datetime(2026, 9, 14, 10, 0, 0),
            finished_at=datetime(2026, 9, 14, 9, 59, 58, 500000),
            remote_run_id=remote.id,
        )

        facts = await load_run_facts(db_session, project.id)

        assert facts.cloud_run is not None
        assert facts.cloud_run.duration_seconds == -1

    async def test_another_project_does_not_leak_in(self, db_session: AsyncSession) -> None:
        mine = await _project_row(db_session, "Meins")
        other = await _project_row(db_session, "Fremd")
        remote = await _remote_row(db_session, other, api_calls=5)
        await _criterion_row(
            db_session, other, mode=ClassificationMode.EYE, remote_run_id=remote.id
        )

        facts = await load_run_facts(db_session, mine.id)

        assert facts.cloud_run is None
        assert facts.eye_run is None
        assert facts.remote_api_calls_total is None


class TestTheApiCallsTotal:
    """Die Summe ist vollstaendig oder `null` - eine Teilsumme traegt die Ausbauentscheidung."""

    async def test_all_zero_is_zero(self, db_session: AsyncSession) -> None:
        project = await _project_row(db_session, "Nullaufrufe")
        await _remote_row(db_session, project, api_calls=0)
        await _remote_row(db_session, project, api_calls=0)

        assert (await load_run_facts(db_session, project.id)).remote_api_calls_total == 0

    async def test_a_single_null_makes_the_total_null(self, db_session: AsyncSession) -> None:
        project = await _project_row(db_session, "Luecke")
        await _remote_row(db_session, project, api_calls=7)
        await _remote_row(db_session, project, api_calls=None)

        # Nie eine Teilsumme ueber die erfassten Zeilen.
        assert (await load_run_facts(db_session, project.id)).remote_api_calls_total is None

    async def test_a_failed_remote_run_does_not_count(self, db_session: AsyncSession) -> None:
        project = await _project_row(db_session, "Teilfehler")
        await _remote_row(db_session, project, api_calls=2)
        await _remote_row(db_session, project, status=ScanStatus.FAILED, api_calls=999)

        assert (await load_run_facts(db_session, project.id)).remote_api_calls_total == 2

    async def test_without_a_successful_remote_run_the_total_is_null(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Ohne Erfolg")
        await _remote_row(db_session, project, status=ScanStatus.FAILED, api_calls=3)

        assert (await load_run_facts(db_session, project.id)).remote_api_calls_total is None

    async def test_landmark_calls_never_count(self, db_session: AsyncSession) -> None:
        project = await _project_row(db_session, "Landmark")
        remote = await _remote_row(db_session, project, photos_total=5, api_calls=2)
        await _criterion_row(db_session, project, remote_run_id=remote.id, landmark_api_calls=77)

        facts = await load_run_facts(db_session, project.id)

        assert facts.remote_api_calls_total == 2
        assert facts.cloud_run is not None
        assert facts.cloud_run.remote_api_calls == 2


class TestTheFormGuard:
    """S10 als Syntaxbaumwaechter: die Zusage haengt am CODE, nicht an der Prosa dieses Moduls."""

    def _tree(self) -> ast.Module:
        return ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))

    def test_has_exactly_one_write_site(self) -> None:
        writes = [
            node
            for node in ast.walk(self._tree())
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"write_text", "write_bytes", "write"}
        ]

        # Genau die `--out`-Datei. Eine zweite Schreibstelle machte den Vergleich zu einem
        # Werkzeug, das den Bestand veraendert.
        assert len(writes) == 1

    def test_does_not_import_logging(self) -> None:
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(self._tree())
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(self._tree())
            if isinstance(node, ast.ImportFrom)
        }

        assert "logging" not in imported

    def test_is_not_wired_into_the_service(self) -> None:
        imported = {
            (node.module or "")
            for node in ast.walk(self._tree())
            if isinstance(node, ast.ImportFrom)
        }
        assert "photosort.main" not in imported
        assert "photosort.worker" not in imported
        # Kein Einstiegspunkt importiert das Werkzeug - es laeuft ausschliesslich von Hand.
        for wiring in ("main.py", "worker.py", "api/projects.py", "api/photos.py"):
            assert "eye_comparison" not in (_MODULE_PATH.parent / wiring).read_text(
                encoding="utf-8"
            )
        # Kein Dateiname, keine Bilddaten: keine Attribut-Lesung auf `relative_path` (die Prosa
        # des Modulkopfs nennt die Spalte - der Waechter liest den Syntaxbaum, nicht den Text).
        assert not [
            node
            for node in ast.walk(self._tree())
            if isinstance(node, ast.Attribute) and node.attr == "relative_path"
        ]

    @staticmethod
    def _error_message_reads(tree: ast.Module) -> list[str]:
        return [
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr.endswith("error_message")
        ]

    def test_does_not_read_any_error_message_attribute(self) -> None:
        # Dort steht `str(exc)` eines fremden Systems - der einzige Fremdtext, den dieses
        # Werkzeug uebernehmen koennte.
        assert self._error_message_reads(self._tree()) == []

    def test_the_error_message_guard_reacts_and_stays_narrow(self) -> None:
        # Gegenprobe: der Waechter trifft die Endung `error_message` UND laesst die Zahlen-
        # spalten durch. Ohne diese Probe waere ein spaeter zu breit gebauter Waechter still.
        probe = ast.parse(
            "run.error_message, run.cloud_error_message, run.api_calls, run.photos_total"
        )

        assert self._error_message_reads(probe) == ["error_message", "cloud_error_message"]

    def test_imports_no_network_or_client_module(self) -> None:
        tree = self._tree()
        imported = (
            {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
            | {
                f"{node.module}.{alias.name}"
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            }
        )
        verboten = {
            "httpx",
            "photosort.opencloud",
            "photosort.eye_client",
            "photosort.remote_classification",
            "photosort.landmark",
        }

        # Kein Egress, kein Kostenpfad: das Werkzeug LIEST `api_calls`, es ruft nichts auf.
        assert not {name for name in imported if name in verboten}

    @staticmethod
    def _session_calls(tree: ast.Module) -> set[str]:
        return {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "session"
        }

    def test_calls_no_write_or_session_method(self) -> None:
        # Der Leser liest. `session.add` waere bereits ein Schreibpfad in den Bestand - eng auf
        # den Aufrufempfaenger `session` geprueft, damit `set.add` beim Sammeln der Herkunft
        # nicht als Fehlalarm steht.
        assert not {
            "add",
            "add_all",
            "merge",
            "delete",
            "commit",
            "flush",
        } & self._session_calls(self._tree())

    def test_the_session_call_guard_reacts(self) -> None:
        probe = ast.parse("session.add(photo); session.commit(); session.flush()")

        assert {"add", "commit", "flush"} <= self._session_calls(probe)

    def test_a_real_run_writes_counts_to_stdout(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = tmp_path / "vergleich.json"
        monkeypatch.setattr(eye_comparison, "_run", _fake_run)

        exit_code = main(["--project-id", "1", "--seed", "3", "--out", str(out)])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert '"photos_compared"' in captured.out
        assert '"deviations"' not in captured.out
        # stdout bleibt unveraendert: die Laufdaten gehoeren in die Datei.
        assert '"origin"' not in captured.out
        assert '"runtime"' not in captured.out
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["project_id"] == 1
        assert payload["origin"] == {
            "cloud_providers": ["anthropic"],
            "cloud_models": ["cloud-model"],
            "eye_model_revisions": ["v1.0.0"],
        }
        assert payload["runtime"] == {
            "cloud_run": {
                "duration_seconds": 90,
                "remote_photos_total": 12,
                "remote_api_calls": 7,
            },
            "eye_run": {
                "duration_seconds": 42,
                "eye_photos_total": 12,
                "eye_photos_processed": 11,
            },
            "remote_api_calls_total": 7,
        }
        assert payload["deviations"] == [
            {
                "photo_id": 5,
                "purpose": "excluded_document",
                "motif_key": None,
                "cloud_strength": None,
                "eye_strength": None,
                "cloud_excluded_document": False,
                "eye_excluded_document": True,
                "cloud_album_level": None,
                "eye_album_level": None,
                "path": "/projects/1/photos/5",
            }
        ]

    async def test_the_file_carries_no_message_text_and_no_timestamp(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project_row(db_session, "Meldungen")
        remote = await _remote_row(db_session, project, photos_total=5, api_calls=3)
        remote.error_message = "MARKER-REMOTE-FREMDTEXT"
        run = await _criterion_row(db_session, project, remote_run_id=remote.id)
        run.error_message = "MARKER-KRITERIUM-FREMDTEXT"
        run.cloud_error_message = "MARKER-CLOUD-FREMDTEXT"
        await db_session.commit()

        facts = await load_run_facts(db_session, project.id)
        text = json.dumps(full_report(summarize([], seed=0), facts, project_id=project.id))

        assert "MARKER" not in text
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text)


async def _fake_run(project_id: int, *, seed: int) -> tuple[ComparisonReport, RunFacts]:
    return (
        summarize([_photo(5, eye_excluded=True)], seed=seed),
        _runs(
            cloud_run=CloudRunFacts(
                duration_seconds=90, remote_photos_total=12, remote_api_calls=7
            ),
            eye_run=EyeRunFacts(duration_seconds=42, eye_photos_total=12, eye_photos_processed=11),
            remote_api_calls_total=7,
        ),
    )
