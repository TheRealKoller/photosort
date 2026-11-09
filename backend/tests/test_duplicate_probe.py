"""Tests fuer das rein lesende Messkommando der Duplikaterkennung (Spec 0637).

Aufbau wie beim Event-Probe: die Zaehl- und Gruppierungsfunktionen rein gegen von Hand gebaute
Fingerprints, `main()` synchron gegen eine dateibasierte SQLite mit echtem `display`-Cache.
"""

from __future__ import annotations

import ast
import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from photosort.config import settings
from photosort.db import Base, make_engine, make_session_factory
from photosort.duplicate_probe import (
    OLD_REFERENCE_HAMMING,
    ProbePhoto,
    _distribution,
    _groups_of,
    _summarise,
    largest_similar_span,
    main,
    old_transitive_groups,
    pair_counts,
)
from photosort.models import Photo, PhotoScore, Project, ScanStatus, ScoringRun
from photosort.scoring import (
    PhotoFingerprint,
    assign_duplicate_groups,
    compute_dhash,
    compute_sharpness,
)
from photosort.thumbnails import display_path
from tests.import_closure import import_closure, module_file
from tests.write_guard import write_statements

BASE = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _mask(bits: int) -> int:
    return (1 << bits) - 1


def _probe_photo(photo_id: int, phash: int, moment: datetime, trusted: bool = True) -> ProbePhoto:
    return ProbePhoto(
        photo_id=photo_id,
        phash=phash,
        taken_at=moment,
        taken_at_trusted=trusted,
    )


def _fingerprint(
    photo_id: int,
    *,
    phash: int,
    fine_phash: int,
    moment: datetime,
    trusted: bool = True,
    sharpness: float = 10.0,
) -> PhotoFingerprint:
    return PhotoFingerprint(
        photo_id=photo_id,
        phash=phash,
        fine_phash=fine_phash,
        gray_grid=bytes(1024),
        sharpness=sharpness,
        taken_at=moment,
        taken_at_trusted=trusted,
    )


class TestTheOldReference:
    def test_transitive_chain_is_one_group_under_the_frozen_threshold(self) -> None:
        # Die alte Gruppierung kannte keine Zeit: A~B~C ueber je 6 Bit wurde EINE Gruppe.
        photos = [
            _probe_photo(1, 0, BASE),
            _probe_photo(2, _mask(6), BASE),
            _probe_photo(3, _mask(12), BASE + 20 * MINUTE),
        ]

        groups = old_transitive_groups(photos)

        assert sorted(sorted(group) for group in groups) == [[1, 2, 3]]

    def test_a_pair_above_the_frozen_threshold_is_not_connected(self) -> None:
        photos = [
            _probe_photo(1, 0, BASE),
            _probe_photo(2, _mask(OLD_REFERENCE_HAMMING + 1), BASE),
        ]

        assert sorted(sorted(group) for group in old_transitive_groups(photos)) == [[1], [2]]


class TestTheNewGroupingSplitsTheChain:
    def test_the_same_chain_is_two_members_under_one_winner_not_one_group(self) -> None:
        """A~B und B~C, aber A und C liegen 20 Minuten auseinander. Der Stern nimmt C nicht auf,
        obwohl die alte transitive Gruppe alle drei enthielt."""
        photos = [
            _probe_photo(1, 0, BASE - 10 * MINUTE),
            _probe_photo(2, _mask(6), BASE),
            _probe_photo(3, _mask(12), BASE + 10 * MINUTE),
        ]
        fingerprints = [
            _fingerprint(1, phash=0, fine_phash=0, moment=BASE - 10 * MINUTE),
            _fingerprint(2, phash=_mask(6), fine_phash=_mask(20), moment=BASE, sharpness=30.0),
            _fingerprint(3, phash=_mask(12), fine_phash=_mask(40), moment=BASE + 10 * MINUTE),
        ]

        old = _summarise(old_transitive_groups(photos), {p.photo_id: p.taken_at for p in photos})
        mapping = assign_duplicate_groups(fingerprints)
        new = _summarise(_groups_of(mapping), {p.photo_id: p.taken_at for p in photos})

        assert old.groups == 1
        assert old.largest == 3
        assert mapping == {1: 2}
        assert new.groups == 1
        assert new.largest == 2


class TestGroupSummary:
    def test_sizes_losers_and_the_largest_group(self) -> None:
        moments = {photo_id: BASE for photo_id in (1, 2, 3, 4, 5)}

        summary = _summarise([[1, 2, 3], [4, 5], [6]], moments)

        assert summary.groups == 2
        assert summary.losers == 3
        assert summary.largest == 3
        assert summary.sizes == (3, 2)

    def test_the_span_uses_only_similar_edges(self) -> None:
        by_id = {
            1: _fingerprint(1, phash=0, fine_phash=0, moment=BASE),
            2: _fingerprint(2, phash=0, fine_phash=0, moment=BASE + 400 * MINUTE),
            3: _fingerprint(3, phash=_mask(6), fine_phash=_mask(20), moment=BASE + 5 * MINUTE),
        }

        span = largest_similar_span({2: 1, 3: 1}, by_id)

        assert span == 5 * MINUTE

    def test_a_flat_distribution_is_named_keine(self) -> None:
        assert _distribution(()) == "keine"
        assert _distribution((2, 2, 3)) == "2:2, 3:1"


class TestPairCounts:
    def test_candidates_identical_and_similar_are_counted_once(self) -> None:
        fingerprints = [
            _fingerprint(1, phash=0, fine_phash=0, moment=BASE),
            _fingerprint(2, phash=0, fine_phash=0, moment=BASE),
            _fingerprint(3, phash=_mask(6), fine_phash=_mask(20), moment=BASE + MINUTE),
            _fingerprint(4, phash=_mask(20), fine_phash=_mask(40), moment=BASE),
        ]

        candidates, identical, similar = pair_counts(fingerprints)

        assert candidates == 3
        assert identical == 1
        assert similar == 2


def _image(seed: int, size: int = 160) -> Image.Image:
    image = Image.new("RGB", (size, size), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    for index in range(6):
        x0 = (seed * 37 + index * 23) % size
        y0 = (seed * 53 + index * 31) % size
        draw.ellipse(
            (x0, y0, x0 + 40 + index * 3, y0 + 30 + index * 2),
            fill=((seed * 40 + index * 30) % 256, (index * 50) % 256, (seed * 20) % 256),
        )
    return image


def _shifted_crop(image: Image.Image, fraction: float = 0.02) -> Image.Image:
    shift = max(1, int(image.width * fraction))
    return image.crop((shift, shift, image.width - shift, image.height - shift)).resize(
        image.size, Image.Resampling.LANCZOS
    )


class TestMainAgainstARealSQLite:
    @pytest.fixture
    def prepared(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, int, str]:
        cache = tmp_path / "cache"
        cache.mkdir()
        monkeypatch.setattr(settings, "photo_cache_dir", str(cache))
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"
        moment = datetime(2029, 11, 17, 3, 47, tzinfo=UTC)
        images = [
            _image(1),
            _image(1),
            _image(2),
            _shifted_crop(_image(2)),
            _image(3),
            _image(4),
        ]
        moments = [
            moment,
            moment + timedelta(days=900),
            moment,
            moment + 5 * MINUTE,
            moment,
            moment,
        ]
        trusted = [True, True, True, True, True, False]

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project = Project(
                    name="GEHEIMPROJEKT",
                    opencloud_drive_id="GEHEIMDRIVE",
                    opencloud_path="/GEHEIMPAD",
                )
                session.add(project)
                await session.flush()
                session.add(
                    ScoringRun(
                        project_id=project.id,
                        status=ScanStatus.SUCCESS,
                        photos_total=len(images),
                        photos_processed=len(images),
                    )
                )
                for index, (image, taken, is_trusted) in enumerate(
                    zip(images, moments, trusted, strict=True), start=1
                ):
                    photo = Photo(
                        id=index,
                        project_id=project.id,
                        relative_path=f"GEHEIMBILD{index}.jpg",
                        etag=f"etag-{index}",
                        content_length=1000,
                        taken_at=taken,
                        taken_at_original=taken,
                        last_modified=taken if not is_trusted else moment + timedelta(hours=1),
                        aspect_ratio=1.0,
                    )
                    session.add(photo)
                    session.add(
                        PhotoScore(
                            photo_id=index,
                            sharpness=compute_sharpness(image),
                            exposure=0.0,
                            phash=compute_dhash(image),
                            computed_at=moment,
                        )
                    )
                    if index != len(images):
                        image.save(
                            display_path(cache, index, f"etag-{index}"),
                            format="JPEG",
                            quality=88,
                        )
                await session.commit()
                project_id = project.id
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())
        return url, project_id, str(tmp_path / "probe.db")

    def test_the_report_names_project_and_run_but_no_image_data(
        self,
        prepared: tuple[str, int, str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        url, project_id, _ = prepared

        assert main(["--project-id", str(project_id)], database_url=url) == 0

        report = capsys.readouterr().out
        assert f"Projekt {project_id}, Lauf 1" in report
        assert "gemessen: 5" in report
        assert "uebersprungen (kein Cache / nicht dekodierbar): 1" in report
        for secret in ("GEHEIM", "geheim", "source-", "2029", "/GEHEIMPAD"):
            assert secret not in report

    def test_a_missing_cache_is_skipped_never_zero(
        self, prepared: tuple[str, int, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        url, project_id, _ = prepared

        assert main(["--project-id", str(project_id)], database_url=url) == 0

        report = capsys.readouterr().out
        assert "uebersprungen (kein Cache / nicht dekodierbar): 1" in report
        assert "NICHT GEMESSEN" not in report

    def test_main_leaves_every_table_byte_identical(self, prepared: tuple[str, int, str]) -> None:
        url, project_id, path = prepared

        def dump() -> str:
            with sqlite3.connect(path) as connection:
                return "\n".join(connection.iterdump())

        before = dump()
        assert main(["--project-id", str(project_id)], database_url=url) == 0
        assert dump() == before

    def test_an_unknown_project_is_a_loud_error(
        self, prepared: tuple[str, int, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        url, _project_id, _ = prepared

        assert main(["--project-id", "999"], database_url=url) == 1
        assert "existiert nicht" in capsys.readouterr().err


class TestTheProbeIsReadOnly:
    """Dieselbe Dreiteilung wie beim Event-Probe - KEIN Teil traegt allein."""

    def test_the_command_is_in_no_import_graph_of_the_application(self) -> None:
        assert "photosort.duplicate_probe" not in import_closure("photosort.main")
        assert "photosort.duplicate_probe" not in import_closure("photosort.worker")

    def test_the_module_lies_in_the_graph_of_the_production_signatures(self) -> None:
        assert "photosort.scoring" in import_closure("photosort.duplicate_probe")
        assert "photosort.scoring" in import_closure("photosort.worker")

    def test_no_compose_file_runs_the_module(self) -> None:
        for compose in sorted(REPO_ROOT.glob("docker-compose*.yml")):
            assert "duplicate_probe" not in compose.read_text(encoding="utf-8"), compose.name

    def test_the_module_contains_no_writing_statement_at_all(self) -> None:
        path = module_file("photosort.duplicate_probe")
        assert path is not None
        assert write_statements(ast.parse(path.read_text(encoding="utf-8"))) == []
