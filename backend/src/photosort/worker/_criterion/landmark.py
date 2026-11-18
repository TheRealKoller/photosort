"""Die Sehenswuerdigkeits-Phase: Kandidaten, Ortshinweise, Cloud-Aufrufe, Erkennungszeilen."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker._runs as runs
from photosort.cloud_vision import TokenUsage
from photosort.cloud_vision_throttle import throttle_for_provider
from photosort.config import settings
from photosort.criteria import compute_landmark_score, is_landmark_candidate
from photosort.label_embedding import LabelEmbedderLike
from photosort.landmark import (
    LANDMARK_CONFIDENCE_THRESHOLD,
    LandmarkClientLike,
    LandmarkDetection,
    PlaceHint,
    place_hint_for,
)
from photosort.landmark_names import LandmarkNameEntry, resolve_canonical_landmark
from photosort.model_choice import provider_for_task_model
from photosort.models import (
    CloudVisionPhase,
    CriterionSource,
    LandmarkName,
    Photo,
    PhotoLandmarkDetection,
)
from photosort.places import PlaceInfo, place_cell, usable_locality
from photosort.pricing import compute_cost_usd
from photosort.run_cancel import RunCancelled
from photosort.thumbnails import variant_path
from photosort.worker._criterion import CriterionRunContext, upsert_criterion

if TYPE_CHECKING:
    from photosort.worker.criterion_scoring import ModelSet


def select_landmark_candidates(
    candidate_values: dict[int, dict[str, float]], already_scored_photo_ids: set[int]
) -> list[int]:
    """Vorfilterung + Skip-bereits-gescorter-Fotos für den landmark-Cloud-Aufruf - reine, DB-freie
    Funktion, isoliert unit-testbar (analog classify_scan_entries). Ein Foto wird nur dann
    Kandidat, wenn im selben Lauf content_landscape ODER gebaeude die jeweils registrierte
    presence_threshold erreicht (`>=`, inklusiv; die Registry-Schwellwerte werden
    wiederverwendet, es gibt hier KEINEN zweiten, doppelt gepflegten Grenzwert) UND noch keine
    landmark-Zeile aus einem frueheren Lauf existiert - die einzige, bewusst dokumentierte Ausnahme
    vom sonst projektweiten "jeder Lauf scort neu"-Prinzip. Gibt die photo_id-Reihenfolge von
    candidate_values zurueck, keine weitere Sortierung noetig.

    Die eigentliche Schwellenwert-Prüfung lebt in criteria.py::is_landmark_candidate, gemeinsam
    mit der API-seitigen Read-Time-Ableitung genutzt. Hier steht nur das
    Skip-bereits-gescorter-Fotos-Verhalten, das worker-spezifisch ist (keine API-Entsprechung)."""
    candidates: list[int] = []
    for photo_id, values in candidate_values.items():
        if photo_id in already_scored_photo_ids:
            continue
        if is_landmark_candidate(values):
            candidates.append(photo_id)
    return candidates


def landmark_place_hints(
    photos: Collection[Photo], info_by_cell: Mapping[tuple[float, float], PlaceInfo]
) -> dict[int, PlaceHint | None]:
    """Die Ortsangabe je Kandidatenfoto - rein, DB-frei und ohne Netzwerk.

    Ausschliesslich aus der EIGENEN gemessenen Koordinate des Fotos (S3, ADR 0106 Punkt 4): Die
    Inferenzbasis aus `events.py::infer_locations` wird hier nicht gelesen und diese Funktion
    bekommt sie gar nicht erst zu sehen. Ein Foto ohne eigene Koordinate bekommt `None`, und das
    ist kein Fehlerfall.

    Die Stufenwahl selbst liegt in `landmark.py::place_hint_for`; hier steht nur die Zuordnung von
    Foto zu abgelegter Auskunft."""
    hints: dict[int, PlaceHint | None] = {}
    for photo in photos:
        if photo.gps_lat is None or photo.gps_lon is None:
            hints[photo.id] = None
            continue
        info = info_by_cell.get(place_cell(photo.gps_lat, photo.gps_lon))
        hints[photo.id] = place_hint_for(usable_locality(info), photo.gps_lat, photo.gps_lon)
    return hints


def landmark_place_cells(photos: Collection[Photo]) -> set[tuple[float, float]]:
    """Die abgelegten Zellen der Kandidatenfotos, fuer die es ueberhaupt eine gibt.

    Die Zellen, nach denen gefragt und unter denen abgelegt wird, sind unveraendert die von
    `place_cell` (`PLACE_CELL_DIGITS`) - die Vergroeberung auf die ausgehende Koernung passiert
    erst in `place_hint_for`, am sendenden Rand. Eine eigene Zellsorte in `place_lookups` entstuende
    sonst, und die abgelegte Ortsspur waere nicht mehr die eine des Projekts."""
    return {
        place_cell(photo.gps_lat, photo.gps_lon)
        for photo in photos
        if photo.gps_lat is not None and photo.gps_lon is not None
    }


async def detect_landmark_for_photo(
    client: LandmarkClientLike, cache_dir: Path, photo: Photo, hint: PlaceHint | None
) -> LandmarkDetection:
    """Der reine I/O-/Netzwerk-Teil eines einzelnen Landmark-Kandidaten (analog
    _fetch_and_thumbnail) - bewusst OHNE Session-Zugriff, damit mehrere Aufrufe sicher parallel
    per asyncio.gather laufen koennen (siehe die Block-Schleife in run_criterion_scoring). Nutzt
    ausschliesslich die bereits vorhandene display-Cache-Variante, nie das
    Original - kein erneuter OpenCloud-Zugriff. Ein fehlender/nicht lesbarer Cache-Eintrag
    propagiert als gewoehnliche Exception (best-effort ueber return_exceptions=True in der
    aufrufenden Block-Schleife abgefangen), exakt wie ein LandmarkApiError des Clients selbst."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    image_bytes = path.read_bytes()
    return await client.detect(image_bytes, runs.CLOUD_VISION_IMAGE_MIME_TYPE, hint)


async def upsert_landmark_detection(
    session: AsyncSession,
    photo_id: int,
    detection: LandmarkDetection,
    now: datetime,
    provider: str,
    canonical_name: str | None,
) -> None:
    """Legt eine photo_landmark_detections-Zeile nur an, wenn tatsaechlich ein Name identifiziert
    wurde (kein Platzhalter-"unbekannt") - wird nur aufgerufen, wenn detection.name is not None
    (siehe Aufrufer). `provider` wird atomar mit name/confidence gesetzt -dieser Aufruf feuert
    praktisch nie fuer ein bereits gescortes Foto (Skip ueber select_landmark_candidates anhand von
    PhotoCriterionScore, providerunabhaengig), ein
    Providerwechsel ueberschreibt das Feld bei bereits gescorten Fotos deshalb nicht.

    ZWEI VERSCHIEDENE ZUSAGEN in einer Zeile: `name` und `confidence` gehen UNGEFILTERT hinein -
    die Antwort ist bezahlt und bleibt vollstaendig erhalten, ob aus ihr ein verwendbarer Name wird,
    entscheidet die Lesestelle. `canonical_name` dagegen setzt der Aufrufer nur oberhalb von
    `LANDMARK_CONFIDENCE_THRESHOLD` und nur mit gebautem Einbetter; sonst bleibt er `None`, und die
    Zeile verhaelt sich exakt wie vor dem Register."""
    assert detection.name is not None
    existing = await session.get(PhotoLandmarkDetection, photo_id)
    if existing is None:
        existing = PhotoLandmarkDetection(photo_id=photo_id)
        session.add(existing)
    existing.name = detection.name
    existing.confidence = detection.confidence
    existing.computed_at = now
    existing.provider = provider
    existing.canonical_name = canonical_name


@dataclass
class _LandmarkTotals:
    """Fortschritt und Ist-Kosten-Buchfuehrung dieser Phase - streng getrennt (Invariante
    `landmark_photos_processed == api_calls + failed_calls`)."""

    attempts: int = 0
    processed: int = 0
    failures: int = 0
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


async def _landmark_register(
    context: CriterionRunContext, models: ModelSet, *, has_candidates: bool
) -> tuple[LabelEmbedderLike | None, list[LandmarkNameEntry]]:
    """DAS NAMENSREGISTER dieses Projekts, einmal je Lauf geladen und danach mutierbar
    durchgereicht (Muster `run_remote_category_classification`): Ein in diesem Lauf neu entstandener
    Eintrag ergaenzt den Schnappschuss sofort, sodass ein zweiter aehnlicher Name im selben Lauf auf
    ihn trifft statt eine zweite Zeile anzulegen.

    SICHERHEIT (S8): Die Bindung an `project.id` steht in der Abfrage ausgeschrieben, und es gibt
    keinen Rueckfall auf das Register eines anderen Projekts - ein solcher Rueckfall fuehrte die
    Reisen verschiedener Projekte zusammen.

    Der Einbetter ist BEST-EFFORT: Ohne ihn entsteht kein kanonischer Name und kein Registereintrag,
    der Lauf laeuft unveraendert durch, und jede Erkennungszeile verhaelt sich wie vor dem Register
    (sie faellt auf ihren Rohnamen zurueck). Gebaut wird er erst HIER, innerhalb der
    Landmark-Phase - `rebuild_run_grouping` erreicht diese Stelle nie und laedt deshalb kein
    113-MB-Modell in einen Anfragepfad (S10).

    UND NUR, WENN ES UEBERHAUPT KANDIDATEN GIBT: Die Phase wird auch dann betreten, wenn
    `select_landmark_candidates` alles herausgefiltert hat (ein zweiter Lauf ueber ein bereits
    vollstaendig gescortes Projekt) - dann laeuft die Blockschleife null Mal, und ein geladenes
    113-MB-Modell waere Arbeit ohne Gegenwert. Dieselbe Begruendung wie beim `place_infos` im
    Orchestrator."""
    embedder = runs.try_build(models.build_embedder) if has_candidates else None
    if embedder is None:
        # Der Schnappschuss haengt am Einbetter und nicht umgekehrt: Ohne ihn wird er nie gelesen,
        # und die Abfrage waere derselbe Leerlauf.
        return None, []
    register = [
        LandmarkNameEntry(
            normalized_name=row.normalized_name,
            display_name=row.display_name,
            embedding=list(row.embedding),
            locality=row.locality,
            id=row.id,
        )
        for row in (
            await context.session.execute(
                select(LandmarkName).where(LandmarkName.project_id == context.project_id)
            )
        )
        .scalars()
        .all()
    ]
    return embedder, register


async def _canonical_landmark_name(
    context: CriterionRunContext,
    detection: LandmarkDetection,
    hint: PlaceHint | None,
    register: list[LandmarkNameEntry],
    embedder: LabelEmbedderLike | None,
) -> str | None:
    """DIE KANONISIERUNG, und nur OBERHALB DER GRENZE: Ein unsicherer und wahrscheinlich falscher
    Name soll nicht die Anzeigeform eines Registereintrags besetzen, dem sich spaeter der richtige
    anschliesst (ADR 0107 Punkt 5). Ohne Einbetter entsteht kein kanonischer Name - kein
    Fehlerfall.

    `name` und `confidence` gehen dagegen UNGEFILTERT in die Zeile (siehe
    `upsert_landmark_detection`): Die Antwort ist bezahlt und bleibt vollstaendig erhalten."""
    assert detection.name is not None
    if embedder is None or detection.confidence < LANDMARK_CONFIDENCE_THRESHOLD:
        return None
    # Die SPERRE ist der aufgeloeste Ortsname dieses Fotos - genau die Namensstufe des Hinweises,
    # nie die Koordinatenstufe: Eine Zelle von rund 11 km ist als Unterscheidungsmerkmal zweier
    # Sehenswuerdigkeiten zu grob.
    entry = resolve_canonical_landmark(
        detection.name,
        hint.locality if hint is not None else None,
        register,
        embedder,
    )
    if entry.id is None:
        register_row = LandmarkName(
            project_id=context.project_id,
            normalized_name=entry.normalized_name,
            display_name=entry.display_name,
            embedding=entry.embedding,
            locality=entry.locality,
        )
        context.session.add(register_row)
        await context.session.flush()
        # Die `id` NACHSETZEN, auf genau der Instanz im Schnappschuss - sonst legte derselbe
        # Eintrag beim naechsten Treffer eine zweite Zeile an und verletzte
        # `UniqueConstraint(project_id, normalized_name)`.
        entry.id = register_row.id
    return entry.display_name


async def _run_landmark_block(
    context: CriterionRunContext,
    client: LandmarkClientLike,
    block_photos: Sequence[Photo],
    hints: Mapping[int, PlaceHint | None],
    register: list[LandmarkNameEntry],
    embedder: LabelEmbedderLike | None,
    provider: str,
    totals: _LandmarkTotals,
) -> None:
    """EIN Block der Landmark-Phase: parallele Aufrufe, Auswertung je Ergebnis, Fortschritts-Commit.
    Ein Abbruch mitten im Block wird NACH dem Commit als `RunCancelled` weitergereicht."""
    session = context.session
    run = context.run
    results = await asyncio.gather(
        *[
            detect_landmark_for_photo(client, context.cache_dir, photo, hints[photo.id])
            for photo in block_photos
        ],
        return_exceptions=True,
    )
    # Derselbe Async-Fallstrick wie in _process_scan_block: ein CancelledError einer einzelnen
    # Kind-Coroutine wird von return_exceptions=True sonst als gewoehnliches Ergebniselement
    # durchgereicht statt propagiert.
    for result in results:
        if isinstance(result, asyncio.CancelledError):
            raise result
    handled = 0
    cancelled = False
    for photo, result in zip(block_photos, results, strict=True):
        if isinstance(result, RunCancelled):
            # Der Abbruch hat die Wartezeit dieses Aufrufs beendet: weder Aufruf noch Fehlschlag,
            # und der Block beginnt nichts Neues mehr.
            cancelled = True
            break
        handled += 1
        if isinstance(result, BaseException):
            # Best-effort: ein einzelner fehlgeschlagener Cloud-Aufruf (Timeout, 4xx/5xx,
            # fehlender Cache-Eintrag) laesst fuer dieses Foto keine landmark-Zeile entstehen, alle
            # anderen Kriterien dieses Fotos bleiben unberuehrt, kein Laufabbruch. Dennoch sichtbar
            # ueber docker compose logs. type(exc).__name__/str(exc) GENAU EINMAL berechnet, an
            # beide Senken (Logger, DB) weitergereicht - keine zweite Auswertung.
            totals.failures += 1
            exc_type_name = type(result).__name__
            exc_message = str(result)
            runs.log_cloud_vision_failure(
                "landmark",
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
                CloudVisionPhase.LANDMARK,
                exc_type_name,
                exc_message,
                context.now,
            )
            continue
        detection = result
        # Verbindlich: jeder STATTGEFUNDENE Aufruf wird gezaehlt, auch wenn sein `usage`-Block
        # fehlte - der Tokenbeitrag ist dann 0. Sonst entstuende die stille Kombination
        # "api_calls == 0 bei real erfolgten Aufrufen", und `api_calls > 0` ist zugleich der
        # Ausloeser fuer Befund (b) des Unvollstaendigkeits-Hinweises.
        totals.api_calls += 1
        if detection.usage is not None:
            totals.input_tokens += detection.usage.input_tokens
            totals.output_tokens += detection.usage.output_tokens
        landmark_value = compute_landmark_score(detection)
        upsert_criterion(context, photo.id, "landmark", landmark_value, CriterionSource.CLOUD)
        context.candidate_values[photo.id]["landmark"] = landmark_value
        # "Aufraeumen bei Erfolg": ein erfolgreicher (Retry-)Versuch loescht eine ggf. vorhandene
        # Fehler-Zeile.
        await runs.clear_cloud_vision_error(session, photo.id, CloudVisionPhase.LANDMARK)
        if detection.name is not None:
            canonical_name = await _canonical_landmark_name(
                context, detection, hints[photo.id], register, embedder
            )
            await upsert_landmark_detection(
                session,
                photo.id,
                detection,
                context.now,
                provider,
                canonical_name,
            )

    # Fortgeschrieben wird AM BLOCKENDE, nie beim Betreten des Blocks: sonst stuende nach einem
    # Abbruch mitten im Block ein `processed` da, dem weder ein Aufruf noch ein Fehlschlag
    # gegenuebersteht (Invariante `landmark_photos_processed == api_calls + failed_calls`).
    #
    # `last_progress_at` gehoert VERBINDLICH dazu. Bleibt der Zeitstempel in dieser Phase
    # unberuehrt, setzt `reap_stalled_runs` einen Lauf mit mehr als STALL_THRESHOLD (15 min)
    # Landmark-Arbeit auf FAILED - OHNE die Coroutine abzubrechen. Der Lauf ruft danach unveraendert
    # weiter kostenpflichtig beim Anbieter an, waehrend die Oberflaeche "fehlgeschlagen" sagt, und
    # die Kostenerfassung des `finally` schreibt ihren Betrag auf eine bereits als gescheitert
    # ausgewiesene Zeile.
    totals.processed += handled
    run.landmark_photos_processed = totals.processed
    run.landmark_failed_calls = totals.failures
    run.last_progress_at = runs.now_utc()
    await session.commit()
    if cancelled:
        raise RunCancelled


async def run_landmark_phase(
    context: CriterionRunContext,
    models: ModelSet,
    *,
    candidate_photos: Sequence[Photo],
    hints: Mapping[int, PlaceHint | None],
    landmark_model: str | None,
) -> None:
    """DIE Sehenswuerdigkeits-Phase eines Kriterien-Laufs - eine Einheit, die ohne die uebrigen
    Phasen laeuft (die Kandidaten und ihre Ortshinweise kommen fertig herein).

    Das Modell kommt als Parameter herein (im Ausloeser aus der Projektwahl aufgeloest) und wird
    EINMAL je Cloud-Phase gebunden: derselbe lokale Wert baut den Client, bestimmt den
    Schrittmacher, rechnet die Ist-Kosten und landet in der Modellspalte des Laufs. "Angezeigt =
    abgerechnet = tatsaechlich aufgerufen" ist damit strukturell wahr, nicht das Ergebnis dreier
    zufaellig gleicher Lesevorgaenge. Fehlt der Parameter (Job aus der Zeit vor dem Update), gilt
    die Installationsvorgabe."""
    session = context.session
    run = context.run
    landmark_model = landmark_model or settings.resolved_landmark_model()
    landmark_provider = provider_for_task_model(landmark_model)
    landmark_client = runs.try_build(lambda: models.build_landmark_client(landmark_model or ""))
    if landmark_client is None:
        # Ein nicht konstruierbarer Client laesst die Sehenswuerdigkeits-Erkennung aus - das
        # gehoert VERBINDLICH in die laufweite Cloud-Fehlermeldung, sonst bliebe der Fall stumm.
        runs.append_cloud_error(
            run,
            "Sehenswuerdigkeits-Erkennung nicht verfuegbar (Initialisierung fehlgeschlagen).",
        )
        return
    # Die Modellspalte wird am PHASENANFANG committet, nicht erst im `finally` - es ist derselbe
    # lokale Wert, der den Client gebaut hat und gleich die Kosten rechnen wird, nur frueher
    # sichtbar, damit die Oberflaeche schon WAEHREND des Teilschritts sagen kann, wohin die Aufrufe
    # gehen. Der BETRAG bleibt im `finally` und am Phasenende eingefroren.
    run.landmark_model = landmark_model
    await session.commit()
    totals = _LandmarkTotals(attempts=len(candidate_photos))
    # Die Live-Zaehler werden beim BETRETEN der Phase auf `0` gesetzt, nicht bei der Zeilenanlage -
    # `NULL` bleibt damit die Aussage "diesen Teilschritt gab es in diesem Lauf nicht", `0` heisst
    # "gab es, nichts zu tun". `landmark_photos_total` ist zugleich der Marker, an dem die API
    # entscheidet, ob dieser Lauf einen Landmark-Eintrag in `cloud_phases` bekommt - er muss
    # deshalb schon VOR dem ersten Aufruf dastehen, sonst saehe die Oberflaeche den Teilschritt
    # genau dann nicht, wenn er laeuft.
    run.landmark_photos_total = totals.attempts
    run.landmark_photos_processed = 0
    run.landmark_failed_calls = 0
    await session.commit()
    # Zaehlerstand des ANBIETERWEITEN Schrittmachers beim Betreten des Teilschritts. Die
    # Zusammenfassung unten entsteht ausschliesslich aus der DIFFERENZ zu diesem Schnappschuss -
    # die Zaehler selbst sind prozessweit und enthalten auch die Wartezeiten des jeweils anderen
    # Cloud-Teilschritts und paralleler Laeufe.
    landmark_throttle = throttle_for_provider(landmark_provider)
    landmark_throttle_before = landmark_throttle.stats()
    try:
        embedder, register = await _landmark_register(
            context, models, has_candidates=bool(candidate_photos)
        )
        landmark_concurrency = settings.landmark_api_concurrency
        for start in range(0, len(candidate_photos), landmark_concurrency):
            await runs.raise_if_cancel_requested(session, run)
            await _run_landmark_block(
                context,
                landmark_client,
                candidate_photos[start : start + landmark_concurrency],
                hints,
                register,
                embedder,
                landmark_provider,
                totals,
            )
    finally:
        aclose = getattr(landmark_client, "aclose", None)
        if aclose is not None:
            await aclose()
        # VERBINDLICH im finally, nicht erst vor `status = SUCCESS`: ein Lauf, der nach der
        # Cloud-Phase in der Kriterien-Phase scheitert, hat das Geld bereits ausgegeben. Ohne das
        # Schreiben hier verloere er den real angefallenen Betrag - und waere wegen `0` statt
        # `NULL` nicht einmal als Luecke erkennbar. Das Commit ist ebenfalls noetig: der Fehlerpfad
        # laeuft ueber fail_run, das mit einem rollback() beginnt.
        run.landmark_api_calls = totals.api_calls
        run.landmark_input_tokens = totals.input_tokens
        run.landmark_output_tokens = totals.output_tokens
        # Der Betrag wird EINMAL am Phasenende berechnet und eingefroren - eine spaetere
        # Preisaenderung schreibt die Vergangenheit nicht um.
        run.landmark_cost_usd = compute_cost_usd(
            landmark_model,
            TokenUsage(
                input_tokens=totals.input_tokens,
                output_tokens=totals.output_tokens,
            ),
        )
        # `run.landmark_model` - die Preisgrundlage des eben eingefrorenen Betrags - steht bereits
        # vom PHASENANFANG her da und ist derselbe lokale `landmark_model`, aus dem hier der Betrag
        # entsteht. Deshalb KEINE zweite Zuweisung an dieser Stelle.
        await runs.commit_phase_costs(session)
    # Hoechstens eine Zeile, und nur wenn in DIESEM Teilschritt tatsaechlich gewartet wurde.
    runs.log_cloud_vision_throttling(
        "landmark",
        landmark_provider,
        landmark_throttle.stats().since(landmark_throttle_before),
    )
    # Zaehl-Zusammenfassung statt N Einzelmeldungen - die Einzelfehler bleiben pro Foto ueber
    # photo_cloud_vision_errors abrufbar, das hier ist die Laufebene.
    if totals.failures > 0:
        runs.append_cloud_error(
            run,
            f"Sehenswuerdigkeits-Erkennung: {totals.failures} von "
            f"{totals.attempts} Fotos fehlgeschlagen.",
        )
