"""Die gemeinsame Schicht aller Laeufe: Logger, Zeitquelle, Phasenwechsel, Lauf-Enden,
Abbruchpruefpunkte, Cloud-Fehler und -Kosten. Angesprochen wird sie ausschliesslich
qualifiziert (`import photosort.worker._runs as runs`): ein `from ... import` erzeugte je Modul
eine eigene Bindung und machte einen Patch still wirkungslos."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import clock
from photosort.cloud_vision import ThrottleStats
from photosort.models import (
    ClassificationPhase,
    ClassificationReview,
    CloudVisionPhase,
    CriterionScoringRun,
    ExportRun,
    ExportRunStatus,
    PhotoCloudVisionError,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
)
from photosort.run_cancel import RunCancelled, cancel_requested

# Kein Logger-Objekt wird injiziert oder durchgereicht: die gemeinsame Schicht ist die einzige
# Stelle mit Zugriff auf sowohl die Exception als auch den Foto-Kontext -
# landmark.py/remote_classification.py/cloud_vision.py bekommen deshalb keinen eigenen Logger.
#
# Der NAME ist der des Einstiegspunkts und nicht `__name__`: die Logger-Konfiguration haengt an
# "photosort", die Zusage an Betreiber und Tests lautet `photosort.worker` - und daran haengen die
# Meldungspfade, unabhaengig davon, in welcher Datei des Pakets eine Zeile entsteht.
logger = logging.getLogger("photosort.worker")


# Der Cloud-Aufruf nutzt ausschliesslich die bestehende display-Cache-Variante, die
# thumbnails.py::generate_variants immer als JPEG schreibt - fester Wert statt einer
# Format-Erkennung. Das Bildquellen-Muss-Kriterium gilt für BEIDE Cloud-Vision-Pfade.
CLOUD_VISION_IMAGE_MIME_TYPE = "image/jpeg"


def now_utc() -> datetime:
    """Die eine Zeitquelle aller Laeufe: gepatcht wird hier, nicht in `photosort.clock`."""
    return clock.now_utc()


def set_phase(run: CriterionScoringRun, phase: ClassificationPhase | None) -> None:
    """Die EINZIGE Stelle im Projekt, an der `phase` und `phase_started_at` gesetzt werden.

    Beide gemeinsam, nie einzeln: `phase = NULL` nimmt den Beginn mit, jeder andere Wert setzt ihn
    neu. Bliebe der alte Zeitstempel bei einem Wechsel stehen, rechnete die Restdauer den Beginn des
    VORIGEN Teilschritts gegen den Fortschritt des aktuellen - ohne Fehler und ohne roten
    Verhaltenstest.

    Kein `commit()` hier: Der Phasenwechsel wird an jeder Aufrufstelle zusammen mit dem uebrigen
    Zustand dieses Schritts committet, und ein zweiter Commit mitten in `fail_run` verschoebe dort
    die Reihenfolge aus Rollback, Zustand und Commit."""
    run.phase = phase
    run.phase_started_at = None if phase is None else now_utc()


async def fail_run(
    session: AsyncSession,
    run: (
        ScanRun
        | ScoringRun
        | CriterionScoringRun
        | RemoteCategoryClassificationRun
        | ClassificationReview
    ),
    error_message: str,
) -> None:
    """Gemeinsame "Lauf auf FAILED setzen"-Logik für die run_*-Funktionen. Kein raise hier drin -
    der Kontrollfluss des Laufs bleibt an jeder Call-Site sichtbar.

    Ist ein Abbruch angefordert, endet der Lauf stattdessen `CANCELLED`: der Wunsch des Nutzers
    schlaegt jeden Fehler, der danach auftritt, einschliesslich Timeout und Worker-Shutdown. Der
    Merker wird nach dem Rollback frisch gelesen, nie aus dem geladenen Objekt."""
    await session.rollback()
    await session.refresh(run)
    if run.cancel_requested_at is not None:
        await finish_cancelled(session, run)
        return
    run.status = ScanStatus.FAILED
    run.error_message = error_message
    run.finished_at = now_utc()
    if isinstance(run, CriterionScoringRun):
        # `phase = NULL` heisst "laeuft nicht mehr" - das gilt fuer einen fehlgeschlagenen Lauf
        # genauso wie fuer einen erfolgreichen. HIER statt in den run_*-Funktionen, weil fail_run
        # der einzige gemeinsame "auf FAILED setzen"-Pfad ist: er wird auch vom
        # Fortschritts-Watchdog benutzt, der einen haengenden Lauf abraeumt, ohne dass die
        # Job-Coroutine je zurueckkehrt. `phase` existiert nur auf CriterionScoringRun, deshalb die
        # isinstance-Pruefung statt eines gemeinsamen Basisklassen-Feldes.
        set_phase(run, None)
    elif isinstance(run, ClassificationReview):
        # Der Teilschritt einer Pruefung ist `NULL`, sobald der Lauf beendet ist - beim Fehlschlag
        # wie beim Erfolg. Die Pruefung hat kein `phase_started_at`, deshalb die direkte Zuweisung.
        run.phase = None
    await session.commit()
    # das vorangehende rollback() expired ORM-Objekte der Session - ohne dieses refresh() koennte
    # ein direkter Attributzugriff (z.B. `run.id` in scan_project/score_project/classify) einen
    # impliziten Lazy-Load ausserhalb eines aktiven greenlet-Kontexts ausloesen
    # (sqlalchemy.exc.MissingGreenlet) - siehe test_worker_fail_run.py.
    await session.refresh(run)


async def finish_cancelled(
    session: AsyncSession,
    run: (
        ScanRun
        | ScoringRun
        | CriterionScoringRun
        | RemoteCategoryClassificationRun
        | ClassificationReview
        | ExportRun
    ),
) -> None:
    """Der Abbruch-Endzustand eines Laufs. Nicht Committetes wird verworfen; was bis zum letzten
    Commit geschrieben wurde, bleibt - Zaehler, Teilergebnisse und `phase` (der Teilschritt, in dem
    der Lauf endete). Ein bereits beendeter Lauf bleibt unberuehrt: ein Endzustand wird nie
    ueberschrieben."""
    await session.rollback()
    await session.refresh(run)
    # EIN bedingtes UPDATE statt "lesen, pruefen, zuweisen". Der Watchdog schliesst dieselbe Zeile
    # ueber fail_run ab; mit einem ORM-Schreibvorgang entschiede die Commit-Reihenfolge, und ein
    # abgebrochener Lauf koennte nachtraeglich als `failed` erscheinen. Hier gewinnt, wer den
    # Endzustand zuerst schreibt: `cancelled` und `failed` sind beide keine aktiven Zustaende, die
    # Bedingung trifft nach dem ersten Abschluss keine Zeile mehr. `phase` bleibt ausgespart - der
    # Teilschritt gehoert dem abgebrochenen Lauf.
    if isinstance(run, ExportRun):
        model: type[
            ScanRun
            | ScoringRun
            | CriterionScoringRun
            | RemoteCategoryClassificationRun
            | ClassificationReview
            | ExportRun
        ] = ExportRun
        active: tuple[ExportRunStatus | ScanStatus, ...] = (
            ExportRunStatus.QUEUED,
            ExportRunStatus.RUNNING,
        )
        cancelled: ExportRunStatus | ScanStatus = ExportRunStatus.CANCELLED
    else:
        model = type(run)
        active = (ScanStatus.QUEUED, ScanStatus.RUNNING)
        cancelled = ScanStatus.CANCELLED
    await session.execute(
        update(model)
        .where(model.id == run.id, model.status.in_(active))
        .values(status=cancelled, error_message=None, finished_at=now_utc())
    )
    await session.commit()
    await session.refresh(run)


async def take_over_queued_run[
    RunT: (
        ScanRun,
        ScoringRun,
        CriterionScoringRun,
        ClassificationReview,
        ExportRun,
    )
](session: AsyncSession, model: type[RunT], run_id: int) -> RunT | None:
    """Uebernimmt einen von der API angelegten, wartenden Lauf: `QUEUED` -> `RUNNING` in EINER
    bedingten Anweisung. Wurde der Lauf in der Warteschlange abgebrochen (oder gibt es ihn nicht),
    trifft sie keine Zeile - dann `None`, und der Job endet ohne jede Arbeit. Die Bedingung macht
    das Rennen zwischen Abbruch und Jobstart atomar."""
    if model is ExportRun:
        queued: ExportRunStatus | ScanStatus = ExportRunStatus.QUEUED
        running: ExportRunStatus | ScanStatus = ExportRunStatus.RUNNING
    else:
        queued, running = ScanStatus.QUEUED, ScanStatus.RUNNING
    result = await session.execute(
        update(model)
        .where(model.id == run_id, model.status == queued, model.cancel_requested_at.is_(None))
        .values(status=running, last_progress_at=now_utc())
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    if cast("CursorResult[Any]", result).rowcount != 1:
        return None
    return await session.get(model, run_id, populate_existing=True)


async def raise_if_cancel_requested(
    session: AsyncSession,
    run: (
        ScanRun
        | ScoringRun
        | CriterionScoringRun
        | RemoteCategoryClassificationRun
        | ClassificationReview
    ),
) -> None:
    """Pruefpunkt eines Laufs: ist ein Abbruch angefordert, endet die Arbeit hier mit
    `RunCancelled`. Steht nur an Commit-Raendern - was davor committet wurde, bleibt erhalten."""
    if await cancel_requested(session, run):
        raise RunCancelled


async def finish_if_cancel_requested(session: AsyncSession, run: Any) -> bool:
    """Pruefpunkt an einer Phasengrenze: fordert der Lauf den Abbruch an, wird er hier beendet und
    die Phasenfolge endet. `True` heisst "der Lauf ist zu Ende"."""
    if not await cancel_requested(session, run):
        return False
    await finish_cancelled(session, run)
    return True


async def fail_export_run(session: AsyncSession, run: ExportRun, error_message: str) -> None:
    """ "ExportRun auf FAILED setzen" - das Pendant zu `fail_run` fuer den eigenen Status-Enum,
    mit demselben Vorrang eines angeforderten Abbruchs."""
    await session.rollback()
    await session.refresh(run)
    if run.cancel_requested_at is not None:
        await finish_cancelled(session, run)
        return
    run.status = ExportRunStatus.FAILED
    run.error_message = error_message
    run.finished_at = now_utc()
    await session.commit()
    await session.refresh(run)


def try_build[T](build: Callable[[], T]) -> T | None:
    """Best-effort Modell-/Detektor-Konstruktion: ein Fehlschlag GENAU EINES Builders (fehlendes
    oder defektes Asset, mediapipe-/tensorflow-Laufzeitproblem) darf weder den gesamten
    CriterionScoringRun noch die von den UEBRIGEN, erfolgreich gebauten Modellen abhaengigen
    Kriterien mit sich reissen."""
    try:
        return build()
    except Exception:
        return None


def log_cloud_vision_failure(
    phase: str, photo_id: int, relative_path: str, exc_type_name: str, exc_message: str
) -> None:
    """Strukturiertes WARNING-Logging fuer einen best-effort uebersprungenen Cloud-Vision-Aufruf -
    gemeinsam genutzt von der Landmark-Phase und der Remote-Kategorie-Phase. Level WARNING statt
    ERROR: der Skip ist erwartetes best-effort-Verhalten, der Lauf selbst bleibt SUCCESS. Kein
    exc_info/Traceback - eine Zeile pro fehlgeschlagenem Foto reicht fuer Fehlergrund und
    Foto-Kontext.

    Nimmt `exc_type_name`/`exc_message` statt der rohen Exception: der Aufrufer berechnet
    `type(exc).__name__`/`str(exc)` GENAU EINMAL an der Call-Site und reicht beide Werte auch an
    `record_cloud_vision_error` durch - keine zweite, potenziell abweichende Auswertung.

    SICHERHEIT: `exc_message` stammt ausschliesslich aus der bereits an der
    Exception-Konstruktionsstelle sanitierten Meldung (siehe
    cloud_vision.py::raise_for_vision_api_status/*_response_to_json) - hier NIE erneut auf
    `response.text`/`.json()`/`.headers` zugreifen."""
    logger.warning(
        "Cloud-Vision-Aufruf fehlgeschlagen (%s): photo_id=%s relative_path=%s %s: %s",
        phase,
        photo_id,
        relative_path,
        exc_type_name,
        exc_message,
    )


def _counted(count: int, singular: str, plural: str) -> str:
    """Zahlwort mit passendem Numerus - "1 Wiederholung", aber "0"/"2 Wiederholungen"."""
    return f"{count} {singular if count == 1 else plural}"


def log_cloud_vision_throttling(phase: str, provider: str, stats: ThrottleStats) -> None:
    """Strukturiertes WARNING-Logging der VERTEILUNG eines Cloud-Teilschritts, der Gegenpart zu
    log_cloud_vision_failure daneben.

    Hoechstens EINE Zeile je Teilschritt, und nur wenn tatsaechlich gewartet wurde: der Helfer
    kehrt wirkungslos zurueck, wenn weder eine Anfrage eingereiht noch eine Wiederholung noetig
    war. Das Logvolumen bleibt damit an den Ausnahmefall gebunden.

    Level WARNING statt INFO: das Root-Level des Projekts ist WARNING, eine INFO-Zeile erschiene in
    `docker compose logs` gar nicht erst.

    SICHERHEIT: `stats` sind ausschliesslich ZAHLEN - nie eine Antwort, nie ein Headerwert, nie
    `response.text`/`.headers`/`.json()`.

    Die Zeile benennt den Schrittmacher ausdruecklich als ANBIETERWEIT: `ThrottleStats.since()`
    liest prozessweite Zaehler, bei zwei gleichzeitigen Jobs enthaelt die Zusammenfassung des
    einen Laufs die Wartezeiten des anderen. Eine Zahl, die etwas anderes misst als ihr Label
    verspricht, schwaecht die Lauf-/Kostentransparenz, die als Erkennungsmechanismus dient."""
    if stats.delayed_requests == 0 and stats.retries == 0:
        return
    logger.warning(
        "Cloud-Vision-Anfragen gedrosselt (%s): %s eingereiht, %.1f s verteilt, "
        "%s nach 429 mit %.1f s Wartezeit - der Schrittmacher gilt anbieterweit "
        "(%s) und nicht nur fuer diesen Lauf.",
        phase,
        _counted(stats.delayed_requests, "Anfrage", "Anfragen"),
        stats.total_delay_seconds,
        _counted(stats.retries, "Wiederholung", "Wiederholungen"),
        stats.total_retry_wait_seconds,
        provider,
    )


# Defensive Obergrenze fuer eine entartete Fehlermeldung - die eigentliche Absicherung bleibt die
# str(exc)-Konstruktion (keine Secrets/Rohdaten), diese Kappung ist nur eine Storage-/
# Degenerationsgrenze.
#
# SICHERHEIT (die Zielgruppe reicht vom Server-Log-Leser bis zum App-Nutzer): Die persistierte
# Meldung darf keinen URL-Query-Parameter tragen. Betroffen ist der von httpx.HTTPError gewrappte
# Netzwerkfehler (photosort/landmark.py::LandmarkApiError bzw.
# remote_categories.py::RemoteCategoryClassificationApiError, jeweils "... API nicht erreichbar:
# {exc}"). Getragen wird die Zusage davon, dass beide Call-Sites ausschliesslich die fest codierten
# URL-Konstanten ANTHROPIC_MESSAGES_URL/MISTRAL_CHAT_COMPLETIONS_URL aufrufen (cloud_vision.py) -
# beide ohne Query-String. Jeglicher Payload (Bilddaten/API-Key) geht per POST-Body/-Header, NIE
# als Query-Parameter; eine URL mit Query-String gehoert an diesen Call-Sites nicht hin.
_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH = 500


async def commit_phase_costs(session: AsyncSession) -> None:
    """Committet die im `finally`-Block der Cloud-Phase gesetzten Ist-Kostenspalten - und wirft
    dabei NIE.

    Der Aufruf laeuft auch waehrend eine Exception nach oben laeuft. Scheitert genau dieses Commit,
    wuerde seine eigene Exception die urspruengliche ERSETZEN und der eigentliche Fehlergrund waere
    weder im Log noch in `run.error_message` erkennbar. Erreichbar ist das real: nach einem
    fehlgeschlagenen `flush()` (z.B. IntegrityError) wirft `commit()` einen PendingRollbackError.

    Im Fehlerfall gehen die Kostenwerte dieses Laufs verloren (das Rollback verwirft sie) - der
    kleinere Schaden: eine fehlende Kostenangabe faellt ueber den Unvollstaendigkeits-Hinweis der
    Statistikseite auf, eine verschluckte Fehlerursache nicht. Das anschliessende `rollback()`
    hinterlaesst eine benutzbare Session, damit `fail_run` den Lauf noch auf FAILED setzen kann.

    Auch dieses `rollback()` ist abgesichert - es laeuft in der Lage, in der schon das Commit
    gescheitert ist, und eine Exception von dort ersetzte die urspruengliche eine Ebene tiefer.
    Scheitert auch das Aufraeumen, scheitert fail_run mit SEINEM eigenen Fehler statt mit einem
    hier ausgeloesten; sichtbar bleibt beides ueber die zwei Logzeilen.

    Bewusst OHNE `run.id` in der Logzeile: nach einem gescheiterten Commit sind die ORM-Attribute
    expired, ein lesender Zugriff loeste einen Lazy-Load ausserhalb des greenlet-Kontexts aus
    (MissingGreenlet). Der Lauf ist ueber die von fail_run geschriebene `error_message`
    identifizierbar."""
    try:
        await session.commit()
    except SQLAlchemyError as exc:
        logger.warning(
            "Ist-Kosten des Laufs konnten nicht gespeichert werden: %s", type(exc).__name__
        )
        try:
            await session.rollback()
        except SQLAlchemyError as rollback_exc:
            logger.warning(
                "Session nach dem gescheiterten Kosten-Commit nicht aufraeumbar: %s",
                type(rollback_exc).__name__,
            )


async def record_cloud_vision_error(
    session: AsyncSession,
    photo_id: int,
    phase: CloudVisionPhase,
    exc_type_name: str,
    exc_message: str,
    now: datetime,
) -> None:
    """Upsert der letzten bekannten Fehler-Zeile fuer dieses Foto x CloudVisionPhase - getrennt von
    log_cloud_vision_failure (ephemeres Log gegen dauerhafte, per API abrufbare Persistenz mit
    Loesch-Pfad bei Erfolg). Nimmt `exc_type_name`/`exc_message` fertig berechnet entgegen - keine
    zweite Auswertung derselben Exception an zwei Stellen. Reines `session.add`/Attribut-Update,
    kein eigener Commit: die Persistierung laeuft ueber die periodischen Commit-Punkte der
    jeweiligen Schleife."""
    existing = await session.get(PhotoCloudVisionError, (photo_id, phase))
    if existing is None:
        existing = PhotoCloudVisionError(photo_id=photo_id, phase=phase)
        session.add(existing)
    existing.error_type = exc_type_name
    existing.error_message = exc_message[:_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH]
    existing.attempted_at = now


async def clear_cloud_vision_error(
    session: AsyncSession, photo_id: int, phase: CloudVisionPhase
) -> None:
    """Loescht eine ggf. vorhandene Fehler-Zeile nach einem erfolgreichen (Retry-)Versuch - haelt
    die Tabelle konsistent mit ihrer Bedeutung ("letzter bekannter Versuch ist fehlgeschlagen"),
    auch wenn die Prioritaets-Kaskade in api/photos/_conversion.py::_cloud_vision_status_out einen
    vergessenen Aufruf funktional abfangen wuerde (Erfolg schlaegt Fehler)."""
    existing = await session.get(PhotoCloudVisionError, (photo_id, phase))
    if existing is not None:
        await session.delete(existing)


# Defensive Obergrenze fuer die zusammengesetzte laufweite Cloud-Fehlermeldung. Die eigentliche
# Absicherung bleibt, dass jeder
# Baustein fest codiert ist oder aus einer bereits an der Konstruktionsstelle sanitierten Meldung
# stammt; diese Kappung ist nur eine Storage-/Degenerationsgrenze.
_MAX_RUN_CLOUD_ERROR_MESSAGE_LENGTH = 1000


def append_cloud_error(run: CriterionScoringRun, message: str) -> None:
    """Haengt einen Baustein an die laufweite Cloud-Fehlermeldung an, statt sie zu ueberschreiben:
    ein Lauf kann mehrere unabhaengige Cloud-Probleme haben, und keines davon darf ein anderes
    verdecken. Kein eigener Commit - der Aufrufer committet ohnehin an seinen bestehenden
    Punkten."""
    existing = run.cloud_error_message
    combined = message if existing is None else f"{existing} {message}"
    run.cloud_error_message = combined[:_MAX_RUN_CLOUD_ERROR_MESSAGE_LENGTH]
