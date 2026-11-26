"""Die Remote-Kategorie-Phase samt Kandidatenmenge und Album-Eignung."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker._runs as runs
from photosort.album_suitability import AlbumSuitability
from photosort.cloud_vision import TokenUsage
from photosort.cloud_vision_throttle import throttle_for_provider
from photosort.config import settings
from photosort.duplicates import survives_ausschuss
from photosort.label_embedding import LabelEmbedderLike, build_label_embedder
from photosort.model_choice import provider_for_task_model
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    FineLabel,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoFineLabel,
    PhotoMotifAssessment,
    PhotoScore,
    Project,
    RemoteCategoryClassificationRun,
    ScanStatus,
)
from photosort.motif_strengths import upsert_assessment
from photosort.pricing import compute_cost_usd
from photosort.remote_classification import (
    CategoryDetectionClientLike,
    FineLabelSnapshotEntry,
    RemoteClassification,
    build_category_classification_client,
    resolve_canonical_label,
)
from photosort.run_cancel import RunCancelled
from photosort.thumbnails import variant_path


async def _upsert_album_suitability(
    session: AsyncSession,
    photo_id: int,
    suitability: AlbumSuitability,
    now: datetime,
    provider: str,
) -> None:
    """Schreibt bzw. ersetzt die Albumtauglichkeitszeile eines Fotos - GENAU EINE je Foto, auch
    nach beliebig vielen Laeufen.

    Stufe, Begruendung, Anbieter und Zeitstempel werden gemeinsam gesetzt: die Zeile stammt
    immer vollstaendig aus EINER Antwort, ein gemischter Zustand aus zwei Aufrufen entsteht nicht.
    Aufgerufen wird sie nur mit einer bereits validierten Aussage (`album_suitability.py`) - ohne
    brauchbare Stufe entsteht gar keine Zeile, und das Foto bleibt Kandidat des naechsten Laufs.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer."""
    existing = await session.get(PhotoAlbumSuitability, photo_id)
    if existing is None:
        existing = PhotoAlbumSuitability(photo_id=photo_id)
        session.add(existing)
    existing.level = suitability.level
    existing.reason = suitability.reason
    existing.provider = provider
    existing.computed_at = now


async def _classify_photo_for_remote_category(
    client: CategoryDetectionClientLike, cache_dir: Path, photo: Photo
) -> RemoteClassification:
    """Der reine I/O-/Netzwerk-Teil eines einzelnen Remote-Kategorie-Kandidaten - bewusst OHNE
    Session-Zugriff, damit mehrere Aufrufe sicher parallel per asyncio.gather laufen koennen. Nutzt
    ausschliesslich die bereits vorhandene, auf 2048 px begrenzte display-Cache-Variante - nie das
    OpenCloud-Original, kein EXIF/GPS, kein Dateiname und kein Pfad im Request - SICHERHEIT,
    Muss-Kriterium."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    image_bytes = path.read_bytes()
    return await client.classify(image_bytes, runs.CLOUD_VISION_IMAGE_MIME_TYPE, photo.id)


async def select_remote_category_candidates(session: AsyncSession, project_id: int) -> list[Photo]:
    """Kandidatenmenge fuer die Remote-Kategorie-Klassifizierung: der KOMPLETTE
    Ausschuss-Ueberlebender-Bestand (`duplicates.py::survives_ausschuss`) OHNE Vorfilter,
    abzueglich der bereits VOLLSTAENDIG von der Cloud beurteilten Fotos.

    DAS SKIP-KRITERIUM IST ZUSAMMENGESETZT: eine Kopfzeile mit `source='cloud'` UND eine
    Albumtauglichkeitszeile. Beide Haelften tragen je einen eigenen Fehler:

    - Ein reiner Existenztest auf die Kopfzeile (statt auf `source='cloud'`) machte jedes lokal
      beurteilte Foto dauerhaft zum Nicht-Kandidaten - der Kriterien-Lauf schreibt fuer JEDES
      beurteilte Foto eine LOKALE Kopfzeile. Die Cloud-Klassifizierung waere ein stilles No-op.
    - Eine Lockerung auf nur EINES der beiden Merkmale schickt fertig bewertete Fotos erneut an
      den Anbieter: Kosten und wiederholte Datenexposition.

    Die zweite Haelfte ist zugleich die NACHBEWERTUNG: ein Foto aus einem frueheren Lauf, das eine
    Cloud-Kopfzeile, aber noch keine Albumtauglichkeit traegt, wird wieder Kandidat - ohne Re-Scan
    und ohne zweiten Ausloeser.

    Das lokale Ausschuss-Gate bleibt unberuehrt und steht ausgeschrieben in DERSELBEN Anweisung wie
    der Skip-Term: `join(PhotoScore)` plus `survives_ausschuss()` begrenzen weiterhin, welche Fotos
    den Homeserver ueberhaupt verlassen duerfen. Das Praedikat tritt als weiterer
    Konjunktionsteil in DIESE Anweisung ein, nie als nachgelagerter Filter ueber einer bereits
    gebildeten Menge.

    Von `run_remote_category_classification` UND `GET .../classify/estimate` (api/projects.py)
    genutzt - "ermittelt ueber dieselbe Kandidaten-Selektion wie der tatsaechliche Lauf"."""
    rows = (
        (
            await session.execute(
                select(Photo)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project_id, survives_ausschuss())
            )
        )
        .scalars()
        .all()
    )

    if not rows:
        return []

    photo_ids = [photo.id for photo in rows]
    cloud_assessed_ids = set(
        (
            await session.execute(
                select(PhotoMotifAssessment.photo_id).where(
                    PhotoMotifAssessment.photo_id.in_(photo_ids),
                    PhotoMotifAssessment.source == MotifAssessmentSource.CLOUD,
                )
            )
        ).scalars()
    )
    suitability_ids = set(
        (
            await session.execute(
                select(PhotoAlbumSuitability.photo_id).where(
                    PhotoAlbumSuitability.photo_id.in_(photo_ids)
                )
            )
        ).scalars()
    )
    return [
        photo
        for photo in rows
        if not (photo.id in cloud_assessed_ids and photo.id in suitability_ids)
    ]


@dataclass
class _RemoteTotals:
    """Ist-Kosten-Buchfuehrung und Fehlzaehler EINES Remote-Kategorie-Laufs - getrennt, weil
    `api_calls` die Kosten sind und einmal am Phasenende geschrieben wird, `failed_calls` dagegen
    live mitlaeuft."""

    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    failed_calls: int = 0


def _open_remote_models(
    build_client: Callable[[str], CategoryDetectionClientLike],
    build_embedder: Callable[[], LabelEmbedderLike],
    model: str | None,
) -> tuple[str, str, CategoryDetectionClientLike | None, LabelEmbedderLike | None]:
    """Loest Modell, Anbieter und die beiden Bausteine EINMAL je Cloud-Phase auf.

    Fehlt der Parameter (Altjob), gilt die Installationsvorgabe. Client, Schrittmacher, Preis und die
    `provider`-Spalten je Foto lesen denselben Wert."""
    model = model or settings.resolved_landmark_model()
    provider = provider_for_task_model(model)
    client = runs.try_build(lambda: build_client(model))
    embedder = runs.try_build(build_embedder)
    return model, provider, client, embedder


async def _load_fine_label_snapshot(session: AsyncSession) -> list[FineLabelSnapshotEntry]:
    """Das Feinlabel-Vokabular, einmal je Lauf geladen und danach mutierbar durchgereicht: ein in
    diesem Lauf neu entstandener Eintrag ergaenzt den Schnappschuss sofort."""
    return [
        FineLabelSnapshotEntry(
            canonical_key=row.canonical_key,
            display_name=row.display_name,
            embedding=list(row.embedding),
            id=row.id,
        )
        for row in (await session.execute(select(FineLabel))).scalars().all()
    ]


async def _store_remote_classification(
    session: AsyncSession,
    photo: Photo,
    classification: RemoteClassification,
    snapshot: list[FineLabelSnapshotEntry],
    embedder: LabelEmbedderLike,
    provider: str,
    now: datetime,
) -> None:
    """Schreibt die Antwort EINES Fotos: Kopfzeile, Albumtauglichkeit, Feinlabels - und raeumt eine
    ggf. vorhandene Fehler-Zeile ab.

    Pro Foto genau EINE Kopfzeile (`source='cloud'`) samt vollstaendigem Achter-Staerkevektor. Der
    Vektor kommt VALIDIERT aus dem Parser - SICHERHEIT: nie die Rohabbildung des Modells, sonst
    wanderte unvalidierter Fremdtext ueber einen zweiten Kanal in API-Antwort und UI, und ein
    entarteter Zahlenwert legte ueber Starlettes `allow_nan=False` die gesamte Fotoliste des
    Projekts auf 500."""
    # `upsert_assessment` setzt die Regel durch, die beide Grundlagen auseinanderhaelt: eine
    # Cloud-Grundlage schreibt immer und ersetzt eine vorhandene lokale VOLLSTAENDIG. Die
    # Korrekturzeilen bleiben unangetastet - sie haengen am Foto und nicht an der Kopfzeile.
    await upsert_assessment(
        session,
        photo.id,
        source=MotifAssessmentSource.CLOUD,
        strengths=classification.motif_strengths,
        excluded_document=classification.excluded,
        provider=provider,
        computed_at=now,
    )

    # Die Albumtauglichkeit derselben Antwort, im SELBEN Schleifendurchlauf und mit demselben `now` -
    # und nach derselben Best-effort-Regel: ohne brauchbare Stufe entsteht keine Zeile, kein Fehler,
    # kein Laufabbruch. Das Foto bleibt dann Kandidat des naechsten Laufs (die Auswahl verlangt BEIDE
    # Zeilen).
    if classification.album_suitability is not None:
        await _upsert_album_suitability(
            session,
            photo.id,
            classification.album_suitability,
            now,
            provider,
        )

    # Feinlabels sind reine Zusatzinformation und werden AUCH DANN geschrieben, wenn das Modell kein
    # Motiv deutlich erkennt. Loesen beide Labels auf denselben canonical_key auf, entsteht nur eine
    # Zeile - kein IntegrityError durch UniqueConstraint(photo_id, fine_label_id). Ein
    # Konfidenz-Vergleich ist dafür nicht nötig, es gewinnt die Erstnennung.
    entries_by_canonical: dict[str, tuple[FineLabelSnapshotEntry, str]] = {}
    for raw_label in classification.fine_labels:
        entry = resolve_canonical_label(raw_label, snapshot, embedder)
        entries_by_canonical.setdefault(entry.canonical_key, (entry, raw_label))

    # Die Feinlabel-Zeilen der VORHERIGEN Antwort fallen VOLLSTAENDIG, bevor die neuen entstehen -
    # eine Antwort ist vollstaendig oder sie existiert nicht, ein Gemisch aus zwei Antworten gibt es
    # nicht. Ein erneut gesendetes Foto traegt seine alten Zeilen noch, und ein zweiter INSERT
    # desselben Labels verletzte `UniqueConstraint(photo_id, fine_label_id)` - die IntegrityError
    # rollt die Transaktion zurueck und laesst den GESAMTEN Lauf scheitern, nicht nur dieses eine
    # Foto. Die `fine_labels`-Registry selbst bleibt unberuehrt (projektuebergreifendes Vokabular).
    await session.execute(delete(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id))

    for entry, raw_label in entries_by_canonical.values():
        if entry.id is None:
            label_row = FineLabel(
                canonical_key=entry.canonical_key,
                display_name=entry.display_name,
                embedding=entry.embedding,
            )
            session.add(label_row)
            await session.flush()
            entry.id = label_row.id
        session.add(
            PhotoFineLabel(
                photo_id=photo.id,
                fine_label_id=entry.id,
                raw_label=raw_label,
                provider=provider,
                computed_at=now,
            )
        )
    # "Aufräumen bei Erfolg": ein erfolgreicher (Retry-)Versuch loescht eine ggf. vorhandene
    # Fehler-Zeile - einmal pro Foto, nicht pro Label.
    await runs.clear_cloud_vision_error(session, photo.id, CloudVisionPhase.REMOTE_CATEGORY)


async def _classify_remote_block(
    session: AsyncSession,
    client: CategoryDetectionClientLike,
    cache_dir: Path,
    block: list[Photo],
    snapshot: list[FineLabelSnapshotEntry],
    embedder: LabelEmbedderLike,
    provider: str,
    now: datetime,
    totals: _RemoteTotals,
) -> tuple[bool, int]:
    """EIN Block der Remote-Phase - liefert `(abgebrochen, bearbeitet)`.

    Best-effort: ein einzelner fehlgeschlagener Cloud-Aufruf laesst fuer dieses Foto keine Zeile
    entstehen, das Foto bleibt beim naechsten Lauf erneut Kandidat."""
    results = await asyncio.gather(
        *[_classify_photo_for_remote_category(client, cache_dir, photo) for photo in block],
        return_exceptions=True,
    )
    # Async-Fallstrick - siehe run_criterion_scoring.
    for result in results:
        if isinstance(result, asyncio.CancelledError):
            raise result

    handled = 0
    cancelled = False
    for photo, result in zip(block, results, strict=True):
        if isinstance(result, RunCancelled):
            # Der Abbruch hat die Wartezeit dieses Aufrufs beendet: das Element ist weder Ergebnis
            # noch Fehlschlag, und der Block beginnt nichts Neues mehr. Was vor ihm fertig wurde,
            # wird vom Aufrufer noch committet.
            cancelled = True
            break
        handled += 1
        if isinstance(result, BaseException):
            # type(exc).__name__/str(exc) GENAU EINMAL berechnet, an beide Senken (Logger, DB)
            # weitergereicht - keine zweite Auswertung.
            #
            # Das Zählen führt AUSDRÜCKLICH keine weitere Logzeile ein - der Fehlergrund bleibt, wo
            # er liegt (Logzeile unten mit fester Meldung, photo_cloud_vision_errors, laufweite
            # cloud_error_message). Der Zaehler ist eine Anzahl, kein Fremdtext.
            totals.failed_calls += 1
            exc_type_name = type(result).__name__
            exc_message = str(result)
            runs.log_cloud_vision_failure(
                "remote_category",
                photo.id,
                photo.relative_path,
                exc_type_name,
                exc_message,
            )
            # Dauerhafte, per API abrufbare Persistenz desselben Fehlschlags (getrennt vom Log
            # oben).
            await runs.record_cloud_vision_error(
                session,
                photo.id,
                CloudVisionPhase.REMOTE_CATEGORY,
                exc_type_name,
                exc_message,
                now,
            )
            continue
        classification = result
        # Verbindlich: jeder stattgefundene Aufruf zaehlt, auch ohne `usage`-Block (Tokenbeitrag
        # dann 0) - `api_calls > 0` bei Betrag 0/NULL ist der Ausloeser fuer Befund (b) des
        # Unvollstaendigkeits-Hinweises.
        totals.api_calls += 1
        if classification.usage is not None:
            totals.input_tokens += classification.usage.input_tokens
            totals.output_tokens += classification.usage.output_tokens
        await _store_remote_classification(
            session, photo, classification, snapshot, embedder, provider, now
        )
    return cancelled, handled


async def run_remote_category_classification(
    session: AsyncSession,
    project: Project,
    cache_dir: Path,
    build_client: Callable[
        [str], CategoryDetectionClientLike
    ] = build_category_classification_client,
    build_embedder: Callable[[], LabelEmbedderLike] = build_label_embedder,
    *,
    run: RemoteCategoryClassificationRun | None = None,
    parent_run: CriterionScoringRun | None = None,
    model: str | None = None,
) -> RemoteCategoryClassificationRun:
    """Eigenstaendiger, expliziter Job - KEIN Teil von run_criterion_scoring, eigene Run-Tabelle,
    eigenes Concurrency-Setting. Best-effort ohne Retry: ein einzelner Fehlschlag bricht den Lauf
    nicht ab, das Foto bleibt beim naechsten Lauf erneut Kandidat.
    `project.cloud_vision_detection_enabled` wird hier EINMALIG gelesen (kein Live-Reread,
    dokumentierte Vereinfachung) - ist der Schalter aus (Default) ODER der Kandidatenpool leer,
    wird `build_client` GAR NICHT ERST aufgerufen (Security-Muss-Kriterium, geteiltes
    Consent-Gate mit `landmark`).

    `run` ist der bereits von run_classification angelegte Lauf-Datensatz. Der uebergeordnete
    Klassifizierungslauf setzt seinen Fremdschluessel darauf, BEVOR Phase 1 startet; ohne diesen
    frueheren Anlagezeitpunkt haette die Oberflaeche waehrend der Remote-Phase keinen Anker fuer
    den laufenden Vorgang. Fehlt er (Direktaufruf, Tests), legt diese Funktion die Zeile selbst an.

    `parent_run` ist der uebergeordnete Klassifizierungslauf; er wird an jedem Block-Commit
    mitgestempelt. Ohne ihn stempelt die Funktion nur ihre eigene Zeile.

    `model` ist das Modell der Kategorisierung, im Ausloeser aus der Projektwahl aufgeloest. Fehlt
    es (Direktaufruf, Altjob), gilt die Installationsvorgabe. Aus DIESEM Wert folgen Anbieter,
    Client, Schrittmacher, Preis und die `provider`-Spalten je Foto."""
    if run is None:
        run = RemoteCategoryClassificationRun(project_id=project.id, status=ScanStatus.RUNNING)
        session.add(run)
        await session.commit()
        await session.refresh(run)

    try:
        candidates = await select_remote_category_candidates(session, project.id)

        run.photos_total = len(candidates)
        run.photos_processed = 0
        await session.commit()

        if not project.cloud_vision_detection_enabled or not candidates:
            run.status = ScanStatus.SUCCESS
            run.finished_at = runs.now_utc()
            await session.commit()
            return run

        model, provider, client, embedder = _open_remote_models(build_client, build_embedder, model)
        if client is None or embedder is None:
            # Best-effort auf Job-Ebene: ein Ladefehler eines der beiden noetigen Bausteine laesst
            # den Lauf erfolgreich, aber wirkungslos enden - kein Crash, kein FAILED-Zustand fuer
            # ein Infrastrukturproblem, das der naechste Lauf ggf. von selbst behebt.
            run.status = ScanStatus.SUCCESS
            run.finished_at = runs.now_utc()
            await session.commit()
            return run

        # Das Zaehlerwerk steht VOR dem `try` fest: der `finally`-Block liest seine Felder. Wuerde
        # eine Anweisung INNERHALB des `try` vor ihrer Initialisierung werfen - realistisch ein
        # DB-Fehler beim Laden des Feinlabel-Snapshots -, ersetzte ein UnboundLocalError die
        # urspruengliche Exception, und der eigentliche Fehlergrund waere weder im Log noch in
        # `run.error_message` erkennbar.
        #
        # Modell und Zaehler stehen beim BETRETEN der Phase da, nicht erst im `finally` -
        # `failed_calls = 0` heisst "erfasst, noch nichts fehlgeschlagen" und unterscheidet sich
        # damit von `NULL` = "diese Phase fand nicht statt". Der BETRAG bleibt am Phasenende
        # eingefroren.
        totals = _RemoteTotals()
        run.model = model
        run.failed_calls = 0
        await session.commit()

        # Zählerstand des ANBIETERWEITEN Schrittmachers beim Betreten des Teilschritts. Die
        # Zusammenfassung unten entsteht ausschliesslich aus der DIFFERENZ zu diesem Schnappschuss.
        throttle = throttle_for_provider(provider)
        throttle_before = throttle.stats()

        try:
            snapshot = await _load_fine_label_snapshot(session)
            now = runs.now_utc()
            concurrency = settings.remote_category_classification_concurrency
            processed = 0
            for start in range(0, len(candidates), concurrency):
                await runs.raise_if_cancel_requested(session, run)
                cancelled, handled = await _classify_remote_block(
                    session,
                    client,
                    cache_dir,
                    candidates[start : start + concurrency],
                    snapshot,
                    embedder,
                    provider,
                    now,
                    totals,
                )
                processed += handled
                run.photos_processed = processed
                # Der Live-Zähler wird am Block-Commit-Punkt mitgeschrieben - am Blockende, nie
                # beim Betreten des Blocks (sonst stuende nach einem Abbruch mitten im Block ein
                # `processed` da, dem weder ein Aufruf noch ein Fehlschlag gegenuebersteht).
                run.failed_calls = totals.failed_calls
                # Der uebergeordnete Klassifizierungslauf bekommt denselben Stempel im
                # selben Commit - reap_stalled_runs liest nur `last_progress_at` der eigenen Zeile
                # und setzte den Elternlauf sonst nach STALL_THRESHOLD auf FAILED, waehrend diese
                # Coroutine kostenpflichtig weiter Cloud-Aufrufe absetzt.
                progress_at = runs.now_utc()
                run.last_progress_at = progress_at
                if parent_run is not None:
                    parent_run.last_progress_at = progress_at
                await session.commit()
                if cancelled:
                    raise RunCancelled
        finally:
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                await aclose()
            # Wie in der Landmark-Phase VERBINDLICH im finally und mit eigenem Commit: ein nach
            # begonnener Cloud-Nutzung scheiternder Lauf hat das Geld bereits ausgegeben, und der
            # Fehlerpfad laeuft ueber fail_run, das mit einem rollback() beginnt. Der Betrag wird
            # einmal berechnet und eingefroren.
            run.api_calls = totals.api_calls
            run.input_tokens = totals.input_tokens
            run.output_tokens = totals.output_tokens
            run.cost_usd = compute_cost_usd(
                model,
                TokenUsage(input_tokens=totals.input_tokens, output_tokens=totals.output_tokens),
            )
            # Wie in der Landmark-Phase: `run.model` steht bereits vom Phasenanfang her da
            # (derselbe lokale `model`, aus dem hier der Betrag entsteht) - KEINE zweite Zuweisung.
            await runs.commit_phase_costs(session)

        # Höchstens eine Zeile, und nur wenn in DIESEM Teilschritt tatsächlich gewartet wurde.
        runs.log_cloud_vision_throttling(
            "remote_category",
            provider,
            throttle.stats().since(throttle_before),
        )

        run.status = ScanStatus.SUCCESS
        run.finished_at = runs.now_utc()
        await session.commit()
        return run
    except RunCancelled:
        await runs.finish_cancelled(session, run)
        return run
    except asyncio.CancelledError:
        await runs.fail_run(session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
        raise
    except Exception as exc:
        await runs.fail_run(session, run, str(exc))
        return run
