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
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import eye_comparison
from photosort.eye_comparison import (
    DEVIATION_SAMPLE_LIMIT,
    ComparisonReport,
    Deviation,
    PhotoComparison,
    PurposeCounts,
    compare_motifs,
    counts_only,
    full_report,
    load_comparisons,
    main,
    motif_present,
    summarize,
)
from photosort.models import (
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoEyeMotifStrength,
    PhotoEyeResult,
    PhotoMotifAssessment,
    PhotoMotifStrength,
    Project,
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
) -> PhotoComparison:
    return PhotoComparison(
        photo_id=photo_id,
        cloud_motifs=cloud_motifs if cloud_motifs is not None else {"menschen": 0.9},
        eye_motifs=eye_motifs if eye_motifs is not None else {"menschen": 0.9},
        cloud_excluded_document=cloud_excluded,
        eye_excluded_document=eye_excluded,
        cloud_album_level=cloud_album_level,
        eye_album_level=eye_album_level,
    )


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

        assert report.deviations == (Deviation(photo_id=7, purpose="excluded_document"),)

    def test_an_empty_project_reports_zeroes(self) -> None:
        report = summarize([], seed=0)

        assert report.photos_compared == 0
        assert report.motifs == PurposeCounts(0, 0, 0)
        assert report.deviations == ()


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

    def test_stdout_carries_only_counts(self) -> None:
        payload = counts_only(self._report())

        assert set(payload) == {
            "photos_compared",
            "motifs",
            "excluded_document",
            "album_level",
        }
        assert "deviations" not in payload

    def test_the_file_report_has_a_fixed_key_set_without_a_verdict_field(self) -> None:
        payload = full_report(self._report(), project_id=4)

        assert set(payload) == {
            "project_id",
            "photos_compared",
            "motifs",
            "excluded_document",
            "album_level",
            "deviations",
        }
        # Kein Feld traegt eine Empfehlung oder ein Gesamturteil - die Entscheidung bleibt bei
        # der lesenden Person.
        assert not {"verdict", "recommendation", "recommended", "score"} & set(payload)

    def test_deviations_carry_photo_id_and_app_path(self) -> None:
        payload = full_report(self._report(), project_id=4)

        assert payload["deviations"] == [
            {
                "photo_id": 9,
                "purpose": "excluded_document",
                "motif_key": None,
                "path": "/projects/4/photos/9",
            }
        ]


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
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["project_id"] == 1
        assert payload["deviations"] == [
            {
                "photo_id": 5,
                "purpose": "excluded_document",
                "motif_key": None,
                "path": "/projects/1/photos/5",
            }
        ]


async def _fake_run(project_id: int, *, seed: int) -> ComparisonReport:
    return summarize([_photo(5, eye_excluded=True)], seed=seed)
