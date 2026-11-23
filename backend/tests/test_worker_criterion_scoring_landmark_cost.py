"""Kriterien-Lauf: Kosten und Modell der Sehenswuerdigkeits-Phase, Live-Zaehler, Buchfuehrung,
Ratenbegrenzung, Drosselungs-Zusammenfassung.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import pricing, worker
from photosort.cloud_vision import (
    VISION_MODELS_BY_PROVIDER,
    CloudRequestThrottle,
    ThrottleStats,
    TokenUsage,
    default_vision_model_for_provider,
)
from photosort.landmark import (
    AnthropicLandmarkClient,
    LandmarkApiError,
    LandmarkDetection,
    PlaceHint,
)
from photosort.models import (
    ClassificationPhase,
    CloudVisionPhase,
    CriterionScoringRun,
    Photo,
    PhotoCloudVisionError,
    PhotoLandmarkDetection,
    Project,
    ScanStatus,
    ScoringRun,
)
from photosort.pricing import compute_cost_usd
from photosort.worker import _runs as worker_runs
from photosort.worker import run_criterion_scoring
from photosort.worker._criterion import landmark as worker_landmark
from photosort.worker._criterion import ranking as worker_ranking
from tests.run_bookkeeping import assert_call_bookkeeping_invariant
from tests.support import make_project as _make_project
from tests.support import write_display_variant
from tests.support.criterion_scoring import (
    CancellingLandmarkClient,
    PerPhotoLandmarkClient,
    RecordingLandmarkClient,
    _add_photo,
    _add_score,
    _add_successful_scoring_run,
    _failing_landmark_client_builder,
    _flat_image,
    _landscape_scene_classifier,
    _no_aesthetics_model,
    _no_animal_detector,
    _no_face_detector,
    _no_face_landmarker,
    _no_scene_classifier,
    _run_with_landmark_client,
)


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md ab hier: die IST-Kostenerfassung der Landmark-Phase. Der Worker summiert Aufrufe und
# Tokens ueber die ERFOLGREICHEN Ergebnisse und schreibt sie zusammen mit dem einmal berechneten
# Betrag an die Lauf-Zeile - im `finally`-Block der Cloud-Phase, nicht erst vor `status=success`.
async def _landmark_cost_setup(
    db_session: AsyncSession, tmp_path: Path, *, photo_count: int, name: str = "Costa Rica"
) -> tuple[Project, ScoringRun, list[Photo]]:
    project = await _make_project(db_session, name=name)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photos = []
    for index in range(photo_count):
        photo = await _add_photo(
            db_session,
            project,
            f"{name}-{index}.jpg",
            f"etag-{name}-{index}",
            datetime(2023, 1, 1, tzinfo=UTC),
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())
        photos.append(photo)
    return project, scoring_run, photos


def _detection_with_usage(input_tokens: int, output_tokens: int) -> LandmarkDetection:
    return LandmarkDetection(
        name="Eiffelturm",
        confidence=0.9,
        usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _expected_cost(input_tokens: int, output_tokens: int) -> float:
    cost = compute_cost_usd(
        default_vision_model_for_provider("anthropic"),
        TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )
    assert cost is not None
    return cost


async def test_landmark_costs_are_summed_over_all_successful_calls(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=3)
    client = PerPhotoLandmarkClient(
        [
            _detection_with_usage(1_000, 10),
            _detection_with_usage(2_000, 20),
            _detection_with_usage(3_000, 30),
        ]
    )

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 3
    assert run.landmark_input_tokens == 6_000
    assert run.landmark_output_tokens == 60
    assert run.landmark_cost_usd == pytest.approx(_expected_cost(6_000, 60))


async def test_a_partially_failing_landmark_phase_only_counts_the_successful_calls(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ADR 0051 Punkt 6: ein fehlgeschlagener Aufruf liefert keinen auswertbaren `usage`-Block und
    traegt deshalb weder Tokens noch einen Aufruf bei - die dokumentierte, bewusst getragene
    Untererfassung. Die Fehler-Zeilen entstehen unabhaengig davon weiter (ADR 0035)."""
    project, scoring_run, photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=3)
    client = PerPhotoLandmarkClient(
        [
            LandmarkApiError("Fehler fuer a"),
            _detection_with_usage(2_000, 20),
            LandmarkApiError("Fehler fuer c"),
        ]
    )

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 1
    assert run.landmark_input_tokens == 2_000
    assert run.landmark_output_tokens == 20
    assert run.landmark_cost_usd == pytest.approx(_expected_cost(2_000, 20))

    errors = (
        (
            await db_session.execute(
                select(PhotoCloudVisionError).where(
                    PhotoCloudVisionError.phase == CloudVisionPhase.LANDMARK
                )
            )
        )
        .scalars()
        .all()
    )
    assert {error.photo_id for error in errors} == {photos[0].id, photos[2].id}


async def test_a_result_without_usage_still_counts_as_an_api_call(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Verbindliche Festlegung der Spec: `api_calls` zaehlt jeden stattgefundenen Aufruf, auch
    ohne `usage`-Block (Tokenbeitrag dann 0). Sonst entstuende die stille Kombination
    "api_calls == 0 bei real erfolgten Aufrufen" - und `api_calls > 0` ist zugleich der Ausloeser
    fuer Befund (b) des Unvollstaendigkeits-Hinweises."""
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=2)
    client = PerPhotoLandmarkClient(
        [
            LandmarkDetection(name="Eiffelturm", confidence=0.9),  # ohne usage
            _detection_with_usage(1_000, 10),
        ]
    )

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 2
    assert run.landmark_input_tokens == 1_000
    assert run.landmark_output_tokens == 10


async def test_an_unpriced_model_records_tokens_but_no_amount(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0051 Punkt 2: ein nicht bepreistes Modell liefert `None` statt eines stillen `0.0` -
    der Lauf faellt dadurch als Erfassungsluecke auf, statt sich als kostenlos zu tarnen. Der
    gemessene Verbrauch bleibt trotzdem erhalten und ist spaeter nachrechenbar."""
    monkeypatch.setattr(pricing, "MODEL_PRICING", {})
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 1
    assert run.landmark_input_tokens == 1_000
    assert run.landmark_output_tokens == 10
    assert run.landmark_cost_usd is None


async def test_a_run_without_any_cloud_usage_records_zero_not_null(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ "Erfasst, keine Kosten angefallen" - das ist etwas anderes als "nicht erfasst" (`NULL`),
    und nur diese Unterscheidung haelt den Unvollstaendigkeits-Hinweis fehlalarmfrei."""
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=False,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 0
    assert run.landmark_input_tokens == 0
    assert run.landmark_output_tokens == 0
    assert run.landmark_cost_usd == 0


async def test_costs_survive_a_run_that_fails_after_the_landmark_block(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DER Grund fuer das Schreiben im `finally`-Block: ein Lauf, der nach der Cloud-Phase
    scheitert, hat das Geld bereits ausgegeben. Wuerden die Summen erst vor `status=success`
    geschrieben, waere der Betrag `0` - und wegen `0` statt `NULL` nicht einmal als Luecke
    erkennbar."""
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])

    def _explode(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError("simulierter Fehlschlag nach der Cloud-Phase")

    monkeypatch.setattr(worker_ranking, "rank_photos", _explode)

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.FAILED
    assert run.landmark_api_calls == 1
    assert run.landmark_input_tokens == 1_000
    assert run.landmark_output_tokens == 10
    assert run.landmark_cost_usd == pytest.approx(_expected_cost(1_000, 10))


async def test_a_second_run_only_carries_its_own_costs(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Kosten haengen am LAUF, nicht am Projekt - die Projektsumme entsteht erst beim Lesen
    durch Aufsummieren der Laeufe (ADR 0051 Punkt 3/4)."""
    project, scoring_run, photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    first = await _run_with_landmark_client(
        db_session,
        project,
        scoring_run,
        tmp_path,
        PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)]),
    )
    assert first.landmark_api_calls == 1

    # Zweiter Lauf: das Foto hat bereits einen landmark-Kriterienwert und ist damit kein Kandidat
    # mehr - kein neuer Aufruf, keine neuen Kosten, aber ausdruecklich `0` statt `NULL`.
    second = await _run_with_landmark_client(
        db_session, project, scoring_run, tmp_path, PerPhotoLandmarkClient([])
    )

    assert second.id != first.id
    assert second.landmark_api_calls == 0
    assert second.landmark_input_tokens == 0
    assert second.landmark_output_tokens == 0
    assert second.landmark_cost_usd == 0
    assert first.landmark_api_calls == 1
    assert first.landmark_cost_usd == pytest.approx(_expected_cost(1_000, 10))


async def test_the_landmark_client_is_still_closed_exactly_once_when_costs_are_written(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = RecordingLandmarkClient(detection=_detection_with_usage(1_000, 10))

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.landmark_api_calls == 1
    assert client.aclose_calls == 1


async def test_landmark_costs_use_the_configured_provider_model(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Betrag haengt am tatsaechlich genutzten Modell - bei Mistral ist derselbe Verbrauch
    deutlich guenstiger als bei Anthropic."""
    monkeypatch.setattr(worker.settings, "landmark_provider", "mistral")
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000_000, 0)])

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    expected = compute_cost_usd(
        default_vision_model_for_provider("mistral"), TokenUsage(1_000_000, 0)
    )
    assert expected is not None
    assert run.landmark_cost_usd == pytest.approx(expected)
    assert run.landmark_cost_usd != pytest.approx(_expected_cost(1_000_000, 0))


# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-anbieter-
# und-modellgebundene-kostenschaetzung.md Punkt 6/7 ab hier: das eingestellte Modell wird
# durchgereicht, abgerechnet und je Lauf persistiert. Alle Faelle benutzen bewusst ein NICHT
# voreingestelltes Modell - bei der Voreinstellung stimmten alle drei Stellen auch dann ueberein,
# wenn drei getrennte Lesevorgaenge stattfaenden, und der Test haette keine Trennschaerfe.
_STRONGER_ANTHROPIC_MODEL = VISION_MODELS_BY_PROVIDER["anthropic"][1]


async def test_the_landmark_phase_builds_its_client_with_the_configured_model(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_model", _STRONGER_ANTHROPIC_MODEL)
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])
    received: list[str] = []

    def build(model: str) -> object:
        received.append(model)
        return client

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=build,
        use_cloud=True,
    )

    assert received == [_STRONGER_ANTHROPIC_MODEL]


async def test_the_client_the_billing_and_the_persisted_model_are_one_and_the_same_value(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Identitaetsaussage von ADR 0059 Punkt 7 in einem Test: der Wert, mit dem der Client
    gebaut wurde, ist derselbe, mit dem gerechnet und den die Laufzeile festhaelt. Sie ersetzt den
    mit den Modell-Aliasen entfallenen Waechtertest aus test_pricing.py - geprueft wird jetzt das
    tatsaechliche Laufzeitverhalten statt der Gleichheit zweier Literale."""
    monkeypatch.setattr(worker.settings, "landmark_model", _STRONGER_ANTHROPIC_MODEL)
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000_000, 0)])
    received: list[str] = []

    def build(model: str) -> object:
        received.append(model)
        return client

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=build,
        use_cloud=True,
    )

    expected_cost = compute_cost_usd(_STRONGER_ANTHROPIC_MODEL, TokenUsage(1_000_000, 0))
    assert expected_cost is not None
    assert received == [_STRONGER_ANTHROPIC_MODEL]
    assert run.landmark_model == _STRONGER_ANTHROPIC_MODEL
    assert run.landmark_cost_usd == pytest.approx(expected_cost)
    # Gegenprobe: mit dem Voreinstellungs-Modell waere der Betrag ein anderer - der Test haette
    # sonst nicht gezeigt, dass wirklich das EINGESTELLTE Modell gerechnet wurde.
    assert run.landmark_cost_usd != pytest.approx(_expected_cost(1_000_000, 0))


async def test_a_run_without_a_cloud_phase_leaves_the_model_column_null(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """`NULL` heisst "nicht erfasst" - ein eingetragenes Modell behauptete Cloud-Nutzung, wo keine
    stattfand (dieselbe Semantik wie bei `landmark_cost_usd`)."""
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])

    run = await _run_with_landmark_client(
        db_session, project, scoring_run, tmp_path, client, use_cloud=False
    )

    assert run.landmark_model is None


async def test_the_model_column_survives_a_run_that_fails_after_the_landmark_block(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Spalte wird im selben `finally` und Commit geschrieben wie der eingefrorene Betrag -
    ein Lauf, der spaeter scheitert, hat das Geld bereits ausgegeben und muss erklaerbar bleiben."""
    monkeypatch.setattr(worker.settings, "landmark_model", _STRONGER_ANTHROPIC_MODEL)
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])
    monkeypatch.setattr(worker_ranking, "rank_photos", _raise_after_landmark_phase, raising=True)

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.FAILED
    assert run.landmark_model == _STRONGER_ANTHROPIC_MODEL


def _raise_after_landmark_phase(*args: object, **kwargs: object) -> NoReturn:
    raise RuntimeError("Kriterien-Phase scheitert nach dem Cloud-Anteil")


# --------------------------------------------------------------------------------------------
# specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
# teilschritte-und-laufeigene-cloud-bilanz.md Punkt 2: die LIVE-Zaehler der Landmark-Phase.
#
# Grundmuster aller Tests hier: der Landmark-Client schnappschuesst bei JEDEM Aufruf den Zustand
# der Lauf-Zeile. Assertiert wird ueber die Schnappschussliste, nicht ueber den Endzustand - "der
# Fortschritt bewegt sich waehrend des Laufs mit" ist am Endzustand grundsaetzlich nicht
# nachweisbar.
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _LandmarkSnapshot:
    phase: ClassificationPhase | None
    photos_total: int | None
    photos_processed: int | None
    failed_calls: int | None
    api_calls: int | None
    model: str | None
    cost_usd: float | None
    last_progress_at: datetime


def _snapshot(run: CriterionScoringRun) -> _LandmarkSnapshot:
    return _LandmarkSnapshot(
        phase=run.phase,
        photos_total=run.landmark_photos_total,
        photos_processed=run.landmark_photos_processed,
        failed_calls=run.landmark_failed_calls,
        api_calls=run.landmark_api_calls,
        model=run.landmark_model,
        cost_usd=run.landmark_cost_usd,
        last_progress_at=run.last_progress_at,
    )


class SnapshottingLandmarkClient:
    """Wie PerPhotoLandmarkClient, zeichnet zusaetzlich vor JEDEM Aufruf den Zustand der
    Lauf-Zeile auf. Die Zeile wird dem Test vorab uebergeben (`run=`-Parameter von
    run_criterion_scoring) - sonst haette der Client waehrend des Laufs keinen Zugriff auf sie."""

    def __init__(
        self, run: CriterionScoringRun, results: list[LandmarkDetection | Exception]
    ) -> None:
        self._run = run
        self._results = results
        self.snapshots: list[_LandmarkSnapshot] = []

    async def detect(
        self, image_bytes: bytes, mime_type: str, hint: PlaceHint | None
    ) -> LandmarkDetection:
        self.snapshots.append(_snapshot(self._run))
        result = self._results[len(self.snapshots) - 1]
        if isinstance(result, Exception):
            raise result
        return result


async def _prepared_run(
    session: AsyncSession, project: Project, scoring_run: ScoringRun
) -> CriterionScoringRun:
    """Legt die Lauf-Zeile VOR dem Aufruf an und reicht sie ueber `run=` hinein - dasselbe, was
    run_classification produktiv tut (ADR 0050 Punkt 3). Der Test bekommt damit eine Referenz auf
    genau die Zeile, die der Lauf fortschreibt."""
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=ScanStatus.RUNNING,
        cloud_requested=True,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


def _unbuildable_landmark_client_builder(model: str) -> NoReturn:
    raise RuntimeError("simulierter Modell-Ladefehler")


class TestLandmarkPhaseLiveCounters:
    """ADR 0068 Punkt 2 - die drei Zahlen, die die Story WAEHREND eines Cloud-Teilschritts
    verlangt: Fortschritt, abgesetzte Aufrufe, Fehlschlaege."""

    async def test_the_counters_are_set_to_zero_when_the_phase_is_entered(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`0` und nicht `None`: `NULL` heisst "Phase nicht betreten", `0` heisst "betreten,
        noch nichts passiert". Ohne das Setzen beim Betreten waere der Marker
        `landmark_photos_total` erst am Phasenende da - die Oberflaeche saehe den Teilschritt
        genau dann nicht, wenn er laeuft."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(run, [_detection_with_usage(10, 1)] * 3)

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        first = client.snapshots[0]
        assert first.photos_total == 3
        assert first.photos_processed == 0
        assert first.failed_calls == 0
        assert first.phase is ClassificationPhase.LANDMARK

    async def test_the_processed_counter_grows_block_by_block(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DER Nachweis "der Fortschritt bewegt sich mit" (geschaerftes Akzeptanzkriterium:
        Fortschreibung mindestens einmal je parallel abgearbeitetem Aufruf-Block)."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(run, [_detection_with_usage(10, 1)] * 3)

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        assert [snapshot.photos_processed for snapshot in client.snapshots] == [0, 1, 2]
        assert run.landmark_photos_processed == 3

    async def test_the_live_counters_are_committed_at_every_block_end_not_only_at_the_end(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Eine Attributaenderung ist noch keine Sichtbarkeit: die Oberflaeche pollt ueber eine
        ANDERE Verbindung und sieht ausschliesslich Committetes. Ohne diesen Test bliebe "die
        pollende Oberflaeche sieht den Fortschritt" unbelegt."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        run = await _prepared_run(db_session, project, scoring_run)
        committed: list[tuple[int | None, int | None]] = []
        real_commit = db_session.commit

        async def _recording_commit() -> None:
            await real_commit()
            committed.append((run.landmark_photos_processed, run.landmark_failed_calls))

        monkeypatch.setattr(db_session, "commit", _recording_commit)
        client = SnapshottingLandmarkClient(
            run,
            [
                _detection_with_usage(10, 1),
                LandmarkApiError("simulierter Cloud-Fehler"),
                _detection_with_usage(10, 1),
            ],
        )

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        assert (1, 0) in committed
        assert (2, 1) in committed
        assert (3, 1) in committed

    async def test_last_progress_at_advances_during_the_landmark_phase(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DER geschlossene Watchdog-Defekt: bis hierher hatte die Landmark-Phase keinen einzigen
        Commit-Punkt vor dem `finally`, und `reap_stalled_runs` setzte einen Lauf mit mehr als
        STALL_THRESHOLD (15 min) Landmark-Arbeit auf FAILED - OHNE die Coroutine abzubrechen. Der
        Lauf rief danach unveraendert weiter kostenpflichtig beim Anbieter an, waehrend die
        Oberflaeche "fehlgeschlagen" sagte.

        Bewusst KEIN zweiter Testfall in test_worker_reap_stalled_runs.py: `reap_stalled_runs`
        liest ausschliesslich `last_progress_at`, ein Test dort verdoppelte diese Zusage."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        ticks = iter(datetime(2030, 1, 1, 12, 0, second) for second in range(0, 60))
        monkeypatch.setattr(worker_runs, "now_utc", lambda: next(ticks))

        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(run, [_detection_with_usage(10, 1)] * 3)

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        stamps = [snapshot.last_progress_at for snapshot in client.snapshots]
        assert stamps == sorted(stamps)
        assert stamps[-1] > stamps[0], (
            "last_progress_at hat sich waehrend der Landmark-Phase nicht bewegt - ein "
            "arbeitender Lauf sieht damit fuer reap_stalled_runs aus wie ein stehender."
        )

    async def test_failed_single_calls_are_counted_while_the_run_is_still_going(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Eigenes Akzeptanzkriterium: "Fehlgeschlagene Einzelaufrufe sind BEREITS WAEHREND des
        Laufs erkennbar, nicht erst nach seinem Abschluss"."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=4
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(
            run,
            [
                _detection_with_usage(10, 1),
                LandmarkApiError("simulierter Cloud-Fehler"),
                _detection_with_usage(10, 1),
                _detection_with_usage(10, 1),
            ],
        )

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        assert [snapshot.failed_calls for snapshot in client.snapshots] == [0, 0, 1, 1]

    async def test_the_model_is_written_at_the_phase_start_while_the_amount_is_not(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Beide Haelften der ADR-Zusage in EINEM Test (ADR 0068 Punkt 6): Modell/Anbieter stehen
        schon WAEHREND des Teilschritts da (sonst koennte die laufende Anzeige nicht sagen, wohin
        die Aufrufe gehen), der BETRAG bleibt am Phasenende eingefroren (ADR 0051 Punkt 4).

        Der Sentinel-Modellwert kommt aus einer NICHT voreingestellten Einstellung - mit dem
        Default waere die Assertion tautologisch (der Wert stuende dann auch bei einem falsch
        gelesenen `settings` da)."""
        stronger = VISION_MODELS_BY_PROVIDER["anthropic"][1]
        monkeypatch.setattr(worker.settings, "landmark_model", stronger)
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(run, [_detection_with_usage(1_000, 10)] * 2)

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        first = client.snapshots[0]
        assert first.model == stronger
        assert first.api_calls == 0
        assert first.cost_usd == 0
        assert run.landmark_api_calls == 2
        assert run.landmark_cost_usd is not None and run.landmark_cost_usd > 0

    @pytest.mark.parametrize(
        "use_cloud,consent,photo_count",
        [
            pytest.param(False, True, 1, id="cloud-checkbox-aus"),
            pytest.param(True, False, 1, id="einwilligung-aus"),
            pytest.param(True, True, 0, id="keine-fotos"),
        ],
    )
    async def test_an_untouched_landmark_phase_leaves_null_not_zero(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        use_cloud: bool,
        consent: bool,
        photo_count: int,
    ) -> None:
        """Die Vierfeldertafel additiver Lauf-Spalten (ADR 0051 Punkt 3): `NULL` heisst "Phase
        nicht betreten", `0` heisst "betreten, nichts passiert". Ohne die Unterscheidung koennte
        die Bilanz einen Lauf ohne Cloud-Teilschritt nicht von einem mit leerer Kandidatenmenge
        trennen und zeigte fuer beide dieselben Nullzeilen."""
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=photo_count
        )
        project.cloud_vision_detection_enabled = consent
        await db_session.commit()

        run = await _run_with_landmark_client(
            db_session,
            project,
            scoring_run,
            tmp_path,
            RecordingLandmarkClient(),
            use_cloud=use_cloud,
        )

        assert run.landmark_photos_total is None
        assert run.landmark_photos_processed is None
        assert run.landmark_failed_calls is None
        assert_call_bookkeeping_invariant(run)

    async def test_an_unbuildable_client_leaves_the_counters_null_too(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der vierte NULL-Fall: die Phase wird betreten, der Client ist aber nicht
        konstruierbar - es findet kein einziger Aufruf statt, also gibt es auch nichts zu
        zaehlen."""
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=1
        )

        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=_unbuildable_landmark_client_builder,
            use_cloud=True,
        )

        assert run.landmark_photos_total is None
        assert run.landmark_failed_calls is None
        assert_call_bookkeeping_invariant(run)

    async def test_an_entered_phase_without_candidates_counts_zero_not_null(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die ANDERE Haelfte der Vierfeldertafel, und der Fall, der sich am leichtesten mit den
        vier NULL-Faellen darueber verwechseln laesst: Fotos sind da, die Einwilligung liegt vor,
        der Client ist gebaut - nur ist unter den bewerteten Fotos kein Landmark-Kandidat (hier:
        kein Landschaftslabel, also greift `is_landmark_candidate` nicht).

        Die Phase HAT stattgefunden. `0` ist deshalb die richtige Aussage und `NULL` waere
        falsch: die Bilanz zeigt den Teilschritt als durchlaufen, mit null gesendeten Fotos,
        statt ihn zu verschweigen. Ohne diesen Testfall waere die Grenze zwischen "gab es nicht"
        und "gab es, nichts zu tun" genau an der Stelle unbelegt, an der die API entscheidet, ob
        der Lauf ueberhaupt einen Landmark-Eintrag bekommt (`landmark_photos_total is not None`).
        """
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=1
        )
        client = RecordingLandmarkClient()

        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            # Kein Landschaftslabel -> leere Kandidatenmenge, OBWOHL die Phase betreten wurde.
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: client,
            use_cloud=True,
        )

        assert client.calls == []
        assert run.landmark_photos_total == 0
        assert run.landmark_photos_processed == 0
        assert run.landmark_failed_calls == 0
        assert_call_bookkeeping_invariant(run)


class TestLandmarkCallBookkeepingInvariant:
    """ADR 0068 Punkt 2: `photos_processed == api_calls + failed_calls` - die Klammer, die den
    laufend fortgeschriebenen Zaehler und die eingefrorene Kosten-Buchfuehrung zusammenhaelt."""

    async def test_all_calls_successful(self, db_session: AsyncSession, tmp_path: Path) -> None:
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        client = PerPhotoLandmarkClient([_detection_with_usage(10, 1)] * 3)

        run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

        assert run.landmark_photos_processed == 3
        assert run.landmark_failed_calls == 0
        assert_call_bookkeeping_invariant(run)

    async def test_mixed_success_and_failure(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        client = PerPhotoLandmarkClient(
            [
                _detection_with_usage(10, 1),
                LandmarkApiError("simulierter Cloud-Fehler"),
                _detection_with_usage(10, 1),
            ]
        )

        run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

        assert run.landmark_photos_processed == 3
        assert run.landmark_api_calls == 2
        assert run.landmark_failed_calls == 1
        assert_call_bookkeeping_invariant(run)

    async def test_every_call_failed(self, db_session: AsyncSession, tmp_path: Path) -> None:
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        client = PerPhotoLandmarkClient([LandmarkApiError("a"), LandmarkApiError("b")])

        run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

        assert run.landmark_photos_processed == 2
        assert run.landmark_api_calls == 0
        assert run.landmark_failed_calls == 2
        assert_call_bookkeeping_invariant(run)

    async def test_a_run_that_fails_after_the_cloud_phase_keeps_the_invariant(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Erweiterung von test_costs_survive_a_run_that_fails_after_the_landmark_block: das Geld
        war ausgegeben, also muss auch die Zaehler-Bilanz stimmen."""
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        client = PerPhotoLandmarkClient(
            [_detection_with_usage(1_000, 10), LandmarkApiError("simulierter Cloud-Fehler")]
        )

        def _explode(*args: object, **kwargs: object) -> NoReturn:
            raise RuntimeError("simulierter Fehlschlag nach der Cloud-Phase")

        monkeypatch.setattr(worker_ranking, "rank_photos", _explode)

        run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

        assert run.status == ScanStatus.FAILED
        assert_call_bookkeeping_invariant(run)

    async def test_a_cancelled_block_counts_neither_as_processed_nor_as_an_api_call(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Implementierungsvorgabe, die aus der Invariante folgt: der Live-Zaehler wird AM
        BLOCKENDE fortgeschrieben, nie beim Betreten. Wuerde er beim Betreten hochgezaehlt,
        stuende nach einem Abbruch mitten im Block ein `processed` da, dem weder ein Aufruf noch
        ein Fehlschlag gegenuebersteht."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        run = await _prepared_run(db_session, project, scoring_run)

        with pytest.raises(asyncio.CancelledError):
            await _run_with_landmark_client(
                db_session,
                project,
                scoring_run,
                tmp_path,
                CancellingLandmarkClient(),
                run=run,
            )

        assert run.landmark_photos_processed == 0
        assert run.landmark_api_calls == 0

    async def test_the_invariant_is_not_claimed_for_a_run_cancelled_inside_a_block(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Ausnahme wird ausdruecklich festgehalten statt beim ersten Abbruch-Testfall
        stillschweigend gestrichen zu werden: die Invariante gilt fuer VOLLSTAENDIG abgearbeitete
        Bloecke. Nach einem Abbruch mitten im ersten Block ist sie hier trivialerweise erfuellt,
        weil gar kein Block fertig wurde - der Testfall haelt genau das fest, statt die
        Erwartung spaeter kommentarlos zu streichen."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        run = await _prepared_run(db_session, project, scoring_run)

        with pytest.raises(asyncio.CancelledError):
            await _run_with_landmark_client(
                db_session,
                project,
                scoring_run,
                tmp_path,
                CancellingLandmarkClient(),
                run=run,
            )

        assert run.landmark_failed_calls == 0
        assert_call_bookkeeping_invariant(run)


def _throttle_recording_waits(waits: list[float]) -> CloudRequestThrottle:
    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    return CloudRequestThrottle(min_interval_seconds=0.0, clock=lambda: 0.0, sleep=sleep)


def _landmark_success_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[index]

    return httpx.MockTransport(handler)


def _landmark_ok(name: str, confidence: float) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "content": [
                {"type": "text", "text": json.dumps({"name": name, "confidence": confidence})}
            ]
        },
    )


class TestTheLandmarkPhaseSitsOutARateLimit:
    """K9: ein Lauf, dessen Fotos heute wegen der Drosselung ohne Ergebnis blieben, liefert danach
    fuer dieselben Fotos ein Ergebnis - und bei einem dauerhaft drosselnden Anbieter bleibt es
    beim heutigen Verhalten. Erst der Kontrast belegt die Zusage."""

    async def _run(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        transport: httpx.MockTransport,
        throttle: CloudRequestThrottle,
    ) -> tuple[CriterionScoringRun, Photo]:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await db_session.commit()
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())

        client = AnthropicLandmarkClient(
            api_key="sk-test-not-a-real-secret",
            model=default_vision_model_for_provider("anthropic"),
            transport=transport,
            throttle=throttle,
        )
        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: client,
            use_cloud=True,
        )
        return run, photo

    async def test_a_429_followed_by_a_200_still_produces_the_result_row(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        waits: list[float] = []
        run, photo = await self._run(
            db_session,
            tmp_path,
            _landmark_success_transport([httpx.Response(429), _landmark_ok("Eiffelturm", 0.87)]),
            _throttle_recording_waits(waits),
        )

        assert run.status == ScanStatus.SUCCESS
        assert run.landmark_failed_calls == 0
        detection_row = (
            await db_session.execute(
                select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
            )
        ).scalar_one()
        assert detection_row.name == "Eiffelturm"
        errors = (
            (
                await db_session.execute(
                    select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
                )
            )
            .scalars()
            .all()
        )
        assert errors == []
        assert waits == [2.0]

    async def test_a_permanent_429_keeps_todays_behaviour(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        waits: list[float] = []
        run, photo = await self._run(
            db_session,
            tmp_path,
            _landmark_success_transport([httpx.Response(429)]),
            _throttle_recording_waits(waits),
        )

        assert run.status == ScanStatus.SUCCESS
        assert run.landmark_failed_calls == 1
        rows = (
            (
                await db_session.execute(
                    select(PhotoLandmarkDetection).where(
                        PhotoLandmarkDetection.photo_id == photo.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert rows == []
        error_row = (
            await db_session.execute(
                select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
            )
        ).scalar_one()
        assert "429" in error_row.error_message
        assert waits == [2.0, 4.0, 8.0, 16.0]


class TestTheLandmarkPhaseSummarisesItsThrottling:
    """K8: je Cloud-Teilschritt HOECHSTENS EINE WARNING-Zusammenfassung, und nur, wenn in DIESEM
    Teilschritt tatsaechlich gewartet wurde."""

    async def _run(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        throttle: CloudRequestThrottle,
        monkeypatch: pytest.MonkeyPatch,
    ) -> CriterionScoringRun:
        # Etablierte Konvention (vgl. test_worker_reap_stalled_runs.py): Worker und injizierter
        # Client muessen DENSELBEN Schrittmacher sehen, sonst misst die Zusammenfassung nichts.
        monkeypatch.setattr(worker_landmark, "throttle_for_provider", lambda _provider: throttle)
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await db_session.commit()
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())

        client = AnthropicLandmarkClient(
            api_key="sk-test-not-a-real-secret",
            model=default_vision_model_for_provider("anthropic"),
            transport=_landmark_success_transport(
                [httpx.Response(429), _landmark_ok("Eiffelturm", 0.87)]
            ),
            throttle=throttle,
        )
        return await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: client,
            use_cloud=True,
        )

    async def test_without_any_waiting_no_line_is_written(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Zugleich der Grund, warum alle BESTEHENDEN Worker-Tests still bleiben: sie arbeiten mit
        Test-Doubles und beruehren den Schrittmacher nie."""
        throttle = _throttle_recording_waits([])
        monkeypatch.setattr(worker_landmark, "throttle_for_provider", lambda _provider: throttle)
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await db_session.commit()
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())
        client = RecordingLandmarkClient(
            detection=LandmarkDetection(name="Eiffelturm", confidence=0.87)
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            run = await run_criterion_scoring(
                db_session,
                project,
                scoring_run.id,
                cache_dir=tmp_path,
                build_detector=_no_face_detector,
                build_animal_detector=_no_animal_detector,
                build_classifier=_landscape_scene_classifier,
                build_aesthetics=_no_aesthetics_model,
                build_landmarker=_no_face_landmarker,
                build_landmark_client=lambda _model: client,
                use_cloud=True,
            )

        assert run.status == ScanStatus.SUCCESS
        assert [record for record in caplog.records if record.name == "photosort.worker"] == []

    async def test_after_waiting_exactly_one_summary_line_is_written(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        throttle = _throttle_recording_waits([])

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            run = await self._run(db_session, tmp_path, throttle, monkeypatch)

        assert run.status == ScanStatus.SUCCESS
        # Gefiltert auf den Worker-Logger: der Client-Logger (photosort.cloud_vision) schreibt im
        # selben Lauf seine eigene Zeile JE WIEDERHOLUNG - das ist K8s andere Haelfte und hier
        # nicht der Gegenstand.
        records = [record for record in caplog.records if record.name == "photosort.worker"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        message = records[0].getMessage()
        assert "landmark" in message
        assert "anthropic" in message
        # Genau EINE Wiederholung - Singular. Bewusst mit dem Folgewort assertiert:
        # `"1 Wiederholung" in "1 Wiederholungen"` waere sonst auch beim Plural wahr.
        assert "1 Wiederholung nach 429" in message
        assert "2.0" in message  # summierte Wiederholungs-Wartezeit

    async def test_the_summary_reports_only_the_difference_of_this_phase(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Die Zaehler sind PROZESSWEIT. Ohne diesen Fall schriebe der zweite Cloud-Teilschritt
        sich die Wartezeit des ersten zu und waere bei einem einzelnen Teilschritt trotzdem
        gruen."""
        throttle = _throttle_recording_waits([])
        # Zaehlerstand VOR dem Teilschritt kuenstlich ungleich null.
        throttle.record_retry_wait(41.0)
        throttle.record_retry_wait(1.0)

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            await self._run(db_session, tmp_path, throttle, monkeypatch)

        records = [record for record in caplog.records if record.name == "photosort.worker"]
        assert len(records) == 1
        message = records[0].getMessage()
        # Die Zeile meldet die EINE Wiederholung dieses Teilschritts, nicht alle drei des
        # Prozesses - und nicht die 42.0 s, die vor dem Teilschritt bereits auf dem prozessweiten
        # Zaehler standen.
        assert "42.0" not in message
        # Genau EINE Wiederholung - Singular. Bewusst mit dem Folgewort assertiert:
        # `"1 Wiederholung" in "1 Wiederholungen"` waere sonst auch beim Plural wahr.
        assert "1 Wiederholung nach 429" in message
        assert "2.0 s Wartezeit" in message


class TestLogCloudVisionThrottling:
    """Reine Unit-Faelle des Helfers mit handgebauten ThrottleStats."""

    def test_it_stays_silent_without_any_waiting(self, caplog: pytest.LogCaptureFixture) -> None:
        stats = ThrottleStats(
            delayed_requests=0, total_delay_seconds=0.0, retries=0, total_retry_wait_seconds=0.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker_runs.log_cloud_vision_throttling("landmark", "anthropic", stats)

        assert caplog.records == []

    def test_a_queued_request_alone_already_yields_a_line(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        stats = ThrottleStats(
            delayed_requests=3, total_delay_seconds=4.5, retries=0, total_retry_wait_seconds=0.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker_runs.log_cloud_vision_throttling("remote_category", "mistral", stats)

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "remote_category" in message
        assert "mistral" in message
        assert "3 Anfragen eingereiht" in message
        assert "4.5" in message
        # Null Wiederholungen ist im Deutschen ebenfalls Plural.
        assert "0 Wiederholungen nach 429" in message

    def test_both_counts_are_singular_for_exactly_one(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Copilot-Review-Fund (PR #385), auf BEIDE Zahlwoerter erweitert: "1 Anfragen"/"1
        Wiederholungen" laesen sich falsch. Diese Zeile ist der einzige Traeger der Zusage "eine
        ungewoehnlich lange Laufzeit ist im Lauf-Protokoll erklaerbar" - und genau EINE
        Wiederholung ist der haeufigste Fall, den man dort antrifft."""
        stats = ThrottleStats(
            delayed_requests=1, total_delay_seconds=1.5, retries=1, total_retry_wait_seconds=2.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker_runs.log_cloud_vision_throttling("landmark", "anthropic", stats)

        message = caplog.records[0].getMessage()
        assert "1 Anfrage eingereiht" in message
        assert "1 Wiederholung nach 429" in message
        assert "Anfragen eingereiht" not in message
        assert "Wiederholungen" not in message

    def test_both_counts_are_plural_for_more_than_one(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        stats = ThrottleStats(
            delayed_requests=2, total_delay_seconds=3.0, retries=4, total_retry_wait_seconds=30.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker_runs.log_cloud_vision_throttling("landmark", "anthropic", stats)

        message = caplog.records[0].getMessage()
        assert "2 Anfragen eingereiht" in message
        assert "4 Wiederholungen nach 429" in message

    def test_the_line_names_the_throttle_as_provider_wide(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Restrisiko (b) der Spec: `ThrottleStats.since()` liest prozessweite Zaehler - bei zwei
        gleichzeitigen Jobs enthaelt die Zusammenfassung des einen Laufs die Wartezeiten des
        anderen. Eine Zahl, die etwas anderes misst als ihr Label verspricht, schwaecht die
        Lauf-/Kostentransparenz, der das Sicherheitskonzept die Rolle eines
        Erkennungsmechanismus zuschreibt."""
        stats = ThrottleStats(
            delayed_requests=1, total_delay_seconds=1.0, retries=1, total_retry_wait_seconds=2.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker_runs.log_cloud_vision_throttling("landmark", "anthropic", stats)

        assert "anbieterweit" in caplog.records[0].getMessage()
