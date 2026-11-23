"""Der Kriterien-Lauf: Orchestrierung der Phasen, Run-Kontext, Modellsatz, Rangfolge und
Auswahl. Die Phasen selbst liegen in `_criterion/`."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Row, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker._runs as runs
from photosort.aesthetics import AestheticsModelLike, build_aesthetics_model
from photosort.classification import (
    FaceDetectorLike,
    FaceLandmarkerLike,
    ObjectDetectorLike,
    SceneClassifierLike,
    build_face_detector,
    build_face_landmarker,
    build_object_detector,
    build_scene_classifier,
)
from photosort.duplicates import survives_ausschuss
from photosort.face_analysis import FaceAnalyzerLike, build_face_analyzer
from photosort.geonames import build_landmark_gazetteer, build_place_resolver
from photosort.label_embedding import LabelEmbedderLike, build_label_embedder
from photosort.landmark import LandmarkClientLike, build_landmark_client
from photosort.models import (
    ClassificationMode,
    ClassificationPhase,
    CriterionScoringRun,
    Event,
    Photo,
    PhotoCriterionScore,
    PhotoRanking,
    PhotoScore,
    Project,
    ScanStatus,
    ScoringRun,
)
from photosort.run_cancel import RunCancelled
from photosort.worker._criterion import CriterionRunContext
from photosort.worker._criterion.landmark import (
    landmark_place_cells,
    landmark_place_hints,
    run_landmark_phase,
    select_landmark_candidates,
)
from photosort.worker._criterion.local import run_local_phase, write_local_motif_header
from photosort.worker._criterion.persons import recognize_persons
from photosort.worker._criterion.ranking import (
    LandmarkGazetteerFactory,
    PlaceResolverFactory,
    apply_run_selection,
    build_grouping_and_rankings,
    place_infos,
)


class CriterionScoringGuardError(Exception):
    """Fachliche Vorbedingung fuer run_criterion_scoring nicht erfuellt (die uebergebene
    scoring_run_id ist nicht mehr der aktuell neueste erfolgreiche ScoringRun, z.B. wegen eines
    zwischenzeitlichen Re-Scan/Re-Scoring) - wird wie jede andere Exception im umgebenden
    try/except als FAILED-Lauf mit error_message behandelt. Der Guard sitzt im Worker-Job,
    zusaetzlich zum eigenen 409 der API-Schicht."""


class CriterionScoringReferenceError(Exception):
    """Der in `scoring_run_id` referenzierte Bewertungslauf existiert nicht (mehr).

    Der andere Fall als `CriterionScoringGuardError`: hier gibt es NICHTS anzulegen und nichts als
    FAILED zu markieren. Dieses INSERT haette keine Zeile, auf die sein Fremdschluessel zeigen
    koennte, und risse auf der Zieldatenbank die Transaktion ab - der bisher gepruefte "saubere
    Fehlschlag" mit FAILED-Lauf ist dort kein erreichbarer Zustand. Die Ausnahme verlaesst die
    Funktion deshalb, statt als FAILED-Lauf verschluckt zu werden (Spec 0350, ADR 0122 Punkt 4)."""


async def _latest_successful_criterion_run(
    session: AsyncSession, project_id: int
) -> CriterionScoringRun | None:
    return (
        await session.execute(
            select(CriterionScoringRun)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def rebuild_run_selection(session: AsyncSession, project_id: int) -> None:
    """Rechnet NUR den Auswahlvorschlag des letzten erfolgreichen Kriterien-Laufs neu - aus
    persistierten Zeilen, ohne Cloud-Aufruf und ohne Bildverarbeitung.

    Aufgerufen vom Richtwert-Endpunkt. Events und Rangzeilen bleiben dabei unangetastet: der
    Richtwert aendert, wie viele Plaetze wohin gehen, nicht die Gliederung und nicht die
    Rangfolge.

    Kein erfolgreicher Lauf: nichts zu tun. Weder `commit` noch eigene Transaktionsgrenze - die
    gehoert dem Aufrufer (Muster `rebuild_run_grouping`)."""
    run = await _latest_successful_criterion_run(session, project_id)
    if run is None:
        return
    await apply_run_selection(session, run, project_id)


async def rebuild_run_grouping(session: AsyncSession, project_id: int) -> None:
    """Baut Gliederung und Rangzeilen des LETZTEN ERFOLGREICHEN Kriterien-Laufs neu auf -
    ausschliesslich aus bereits persistierten Werten, ohne Cloud-Aufruf und ohne Bildverarbeitung.

    Aufgerufen vom Versatz-Endpunkt: Reihenfolge, Anzeige und Ortsherleitung sind mit der
    Bedeutungsumkehr von `taken_at` sofort richtig, die EVENTS sind dagegen persistierte
    Lauf-Artefakte (ADR 0087) und waeren es nicht.

    LOESCHEN UND NEUSCHREIBEN statt Umhaengen: `UniqueConstraint(criterion_scoring_run_id,
    position)` laesst alte und neue Events desselben Laufs nicht gleichzeitig zu.

    Kein erfolgreicher Lauf oder keine einzige Rangzeile: nichts zu tun. Weder `commit` noch
    eigene Transaktionsgrenze - die gehoert dem Aufrufer, der genau EINMAL committet (Muster
    `project_deletion`)."""
    run = await _latest_successful_criterion_run(session, project_id)
    if run is None:
        return

    # Die Kandidatenmenge des Laufs sind genau die Fotos seiner Rangzeilen - nicht die aktuellen
    # Ausschuss-Ueberlebenden: ein zwischenzeitliches Re-Scoring darf die Zusammensetzung dieses
    # Laufs nicht nachtraeglich veraendern.
    candidate_ids = set(
        (
            await session.execute(
                select(PhotoRanking.photo_id).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    if not candidate_ids:
        return

    values_by_photo_id: dict[int, dict[str, float]] = {}
    criterion_rows = (
        await session.execute(
            select(
                PhotoCriterionScore.photo_id,
                PhotoCriterionScore.criterion_key,
                PhotoCriterionScore.value,
            ).where(PhotoCriterionScore.photo_id.in_(candidate_ids))
        )
    ).all()
    for photo_id, criterion_key, value in criterion_rows:
        values_by_photo_id.setdefault(photo_id, {})[criterion_key] = value
    # Ein Kandidat ohne einen einzigen Kriterien-Wert bleibt Kandidat: er stand in einer Rangzeile
    # des Laufs und muss auch danach in einer stehen.
    for photo_id in sorted(candidate_ids):
        values_by_photo_id.setdefault(photo_id, {})

    await session.execute(
        delete(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
    )
    await session.execute(delete(Event).where(Event.criterion_scoring_run_id == run.id))
    # Das `flush` VOR dem Neuaufbau: sonst kollidieren die neuen Events mit den alten am
    # Unique-Constraint ueber `(Lauf, position)`.
    await session.flush()

    # `None` STATT EINES AUFLOESERS (S10): Dieser Pfad laeuft in einem Request (Versatz-Endpunkt).
    # Er baut die Namen ausschliesslich aus bereits abgelegten Auskuenften neu und fragt niemanden;
    # eine noch nie gefragte Zelle bleibt hier ohne Namen, bis der naechste Kriterien-Lauf sie
    # beschafft. Ohne diese Grenze koennte ein Request-Pfad nach aussen wirken.
    #
    # `None` STATT EINES VERZEICHNISSES (S8): dasselbe Argument fuer die Ortsplausibilitaet des
    # Sehenswuerdigkeitsnamens - ein Durchgang ueber den zweiten Auszug dauerte gemessen 43 s und
    # waere ueber eine authentifizierte Anfrage beliebig oft wiederholbar. Der Neuaufbau liest die
    # abgelegte Auskunft; unbekannte Namen behalten ihre Namen (Zustand 1).
    await build_grouping_and_rankings(session, run, project_id, values_by_photo_id, None, None)
    # Der Vorschlag gehoert zur neuen Gliederung: ohne ihn stuende `selection_position` nach dem
    # Loeschen der Rangzeilen ueberall auf `NULL`.
    await apply_run_selection(session, run, project_id)


async def start_criterion_scoring_run(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    *,
    cloud_requested: bool,
    estimated_cost_usd: float | None = None,
    mode: ClassificationMode | None = None,
) -> CriterionScoringRun:
    """Legt die Lauf-Zeile an - fuer BEIDE Aufrufer, und erst nach der Existenzpruefung des
    referenzierten Bewertungslaufs.

    Die Pruefung ist GLOBAL (`session.get(ScoringRun, ...)`), nicht projektgebunden: ein ScoringRun
    existiert projektunabhaengig, und eine vorhandene, aber projektfremde oder veraltete id
    "existiert" - sie gehoert damit in den Aktualitaets-Guard hinter dem INSERT (FAILED-Lauf) und
    nicht in den ReferenceError (Spec 0350, ADR 0122 Punkt 4).

    Das INSERT selbst bleibt ungeschuetzt: das Restfenster, in dem der Bewertungslauf zwischen
    Pruefung und INSERT verschwindet, wird benannt und nicht zugedeckt (ADR 0122 Punkt 5)."""
    if await session.get(ScoringRun, scoring_run_id) is None:
        raise CriterionScoringReferenceError(
            f"Der referenzierte Bewertungslauf {scoring_run_id} existiert nicht (mehr); es wird "
            "keine Lauf-Zeile angelegt."
        )

    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run_id,
        status=ScanStatus.RUNNING,
        cloud_requested=cloud_requested,
        estimated_cost_usd=estimated_cost_usd,
        # Der gewaehlte Weg wird EINGEFROREN (Spec 0609): die Anzeige liest ihn nie zurueck, aber
        # eine Auswertung muss spaeter wissen, welcher Weg zu einem Ergebnis gefuehrt hat. Altzeilen
        # bleiben `NULL` - "unbekannt" ist die wahre Aussage ueber sie.
        mode=mode,
        # Die einzige Schreibstelle der Stufenquelle (ADR 0144 Punkt 1) - fuer jeden Weg, auch
        # `local`: Auch ein Lauf ohne Eye und ohne Cloud bildet Rangwerte aus einer Stufe.
        album_level_source=project.category_method,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


@dataclass(frozen=True)
class ModelSet:
    """Die einmal gebundenen Modell-Builder EINES Kriterien-Laufs.

    Jede Phase bekommt genau diesen einen Parameter; keine Phasensignatur nennt einen einzelnen
    Builder. Damit ist "welche Modelle ein Lauf baut" eine einzige, an der Orchestrierung ablesbare
    Zusage, und die Vorgabewerte (die teure, echte Konstruktion) binden hier beim `def` - nicht in
    einer Phase. Ein Patch am Aufrufer erreicht damit genau die Stelle, die den Builder tatsaechlich
    benutzt."""

    build_detector: Callable[[], FaceDetectorLike]
    build_animal_detector: Callable[[], ObjectDetectorLike]
    build_classifier: Callable[[], SceneClassifierLike]
    build_aesthetics: Callable[[], AestheticsModelLike]
    build_landmarker: Callable[[], FaceLandmarkerLike]
    build_landmark_client: Callable[[str], LandmarkClientLike]
    build_place_resolver: PlaceResolverFactory
    build_landmark_gazetteer: LandmarkGazetteerFactory
    build_embedder: Callable[[], LabelEmbedderLike]
    build_face_analyzer: Callable[[], FaceAnalyzerLike]


async def _assert_current_scoring_run(
    session: AsyncSession, project: Project, scoring_run_id: int
) -> None:
    """Der Guard des Laufs: `scoring_run_id` muss der aktuell neueste erfolgreiche `ScoringRun` des
    Projekts sein. Ein Re-Scan/Re-Scoring waehrend der Kuratierung macht den Lauf gegenstandslos -
    er wuerde sonst Kriterien auf einen veralteten Score-Bestand schreiben."""
    latest_scoring_run = (
        (
            await session.execute(
                select(ScoringRun)
                .where(ScoringRun.project_id == project.id)
                .order_by(ScoringRun.started_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if (
        latest_scoring_run is None
        or latest_scoring_run.status != ScanStatus.SUCCESS
        or latest_scoring_run.id != scoring_run_id
    ):
        raise CriterionScoringGuardError(
            "scoring_run_id entspricht nicht mehr dem aktuell neuesten erfolgreichen "
            "Scoring-Lauf (Re-Scan/Re-Scoring waehrend der Kuratierung)."
        )


async def _surviving_rows(
    session: AsyncSession, project_id: int
) -> Sequence[Row[tuple[Photo, PhotoScore]]]:
    """Die Ausschuss-Ueberlebenden des Projekts mit ihrem Score - die Arbeitsmenge des Laufs.

    Bekannter, akzeptierter Performance-Trade-off: HIER gibt es bewusst KEINEN
    Kandidatenpool-Vorfilter pro Cluster - N ist beim Scoren nicht bekannt (es wird erst beim Lesen
    ueber top_n_per_event angewendet), also werden ALLE Ausschuss-Ueberlebenden verarbeitet, nicht
    nur die aussichtsreichsten. Fuer sehr grosse Projekte potenziell spuerbar, siehe
    docs/architecture.md."""
    return (
        await session.execute(
            select(Photo, PhotoScore)
            .join(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(Photo.project_id == project_id, survives_ausschuss())
        )
    ).all()


async def _build_run_context(
    session: AsyncSession,
    run: CriterionScoringRun,
    project_id: int,
    cache_dir: Path,
    rows: Sequence[Row[tuple[Photo, PhotoScore]]],
) -> CriterionRunContext:
    """Der EINE Run-Kontext des Laufs: Zeitpunkt, Arbeitsmenge und die drei reinen In-Memory-
    Grundlagen der Phasen (siehe `CriterionRunContext`)."""
    existing_criterion_scores: dict[tuple[int, str], PhotoCriterionScore] = {}
    if rows:
        photo_ids = [photo.id for photo, _score in rows]
        existing_criterion_scores = {
            (row.photo_id, row.criterion_key): row
            for row in (
                await session.execute(
                    select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id.in_(photo_ids))
                )
            ).scalars()
        }
    return CriterionRunContext(
        session=session,
        run=run,
        project_id=project_id,
        cache_dir=cache_dir,
        now=runs.now_utc(),
        rows=rows,
        candidate_values={},
        area_fractions_by_photo_id={},
        existing_criterion_scores=existing_criterion_scores,
    )


async def run_criterion_scoring(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    cache_dir: Path,
    build_detector: Callable[[], FaceDetectorLike] = build_face_detector,
    build_animal_detector: Callable[[], ObjectDetectorLike] = build_object_detector,
    build_classifier: Callable[[], SceneClassifierLike] = build_scene_classifier,
    build_aesthetics: Callable[[], AestheticsModelLike] = build_aesthetics_model,
    build_landmarker: Callable[[], FaceLandmarkerLike] = build_face_landmarker,
    build_landmark_client: Callable[[str], LandmarkClientLike] = build_landmark_client,
    build_place_resolver: PlaceResolverFactory = build_place_resolver,
    build_landmark_gazetteer: LandmarkGazetteerFactory = build_landmark_gazetteer,
    build_embedder: Callable[[], LabelEmbedderLike] = build_label_embedder,
    *,
    run: CriterionScoringRun | None = None,
    use_cloud: bool = False,
    landmark_model: str | None = None,
    build_face_analyzer: Callable[[], FaceAnalyzerLike] = build_face_analyzer,
) -> CriterionScoringRun:
    """Berechnet Kriterien-Werte fuer alle Ausschuss-Ueberlebenden eines Projekts und die daraus
    abgeleitete Rangfolge je Partition (event_id). Ablauf:
    CriterionScoringRun anlegen -> Guard (scoring_run_id muss der aktuell neueste erfolgreiche
    ScoringRun sein) -> Run-Kontext und Modellsatz bauen -> lokale Kriterienphase ->
    Sehenswuerdigkeits-Phase (nur mit Cloud-Freigabe) -> lokale Motiv-Kopfzeile -> Rangfolge
    (rank_photos je Partition, reine In-Memory-Aggregation ueber die in diesem Lauf berechneten
    Werte, PhotoRanking-Zeilen) -> Personenangabe -> Auswahlvorschlag -> CriterionScoringRun auf
    success/failed setzen. Die Phasen selbst liegen in `_criterion/` und bekommen den Modellsatz als
    einen Parameter. `build_detector`/`build_animal_detector`/`build_classifier`/
    `build_aesthetics`/`build_landmarker` sind injizierbar (Default: die echte, teure
    Modellkonstruktion) - Tests uebergeben stattdessen Fakes ohne echtes Modell
    (build_object_detector/build_scene_classifier/build_aesthetics_model/
    build_face_landmarker dürfen wie build_face_detector NIE in einem automatisierten Test
    aufgerufen werden).

    Dies ist die ZWEITE Phase eines verketteten Klassifizierungslaufs, kein eigenständig
    ausgelöster Lauf. Drei keyword-only Parameter:

    - `run`: der bereits von run_classification angelegte Lauf-Datensatz. Wird keiner uebergeben,
      legt diese Funktion ihn selbst an (Direktaufruf, z.B. in Tests).
    - `use_cloud`: laufbezogene Cloud-Freigabe (die Checkbox am Ausloeser). Das Gate fuer die
      Landmark-Phase ist ab hier die KONJUNKTION `use_cloud and
      project.cloud_vision_detection_enabled` - `use_cloud` kann eine fehlende Einwilligung nie
      ersetzen, nur eine vorhandene fuer diesen einen Lauf ungenutzt lassen.
      Default `False` und damit FAIL-CLOSED: ein Aufrufer, der den Parameter vergisst, verliert
      die Cloud-Anreicherung, statt ungewollte Kosten und einen ungewollten Datenabfluss
      auszuloesen.
    - `landmark_model`: das im Projekt aufgeloeste Modell der Sehenswuerdigkeits-Erkennung.
      Fehlt es (Job aus der Zeit vor dem Update), loest diese Funktion die
      Installationsvorgabe auf. Client, Schrittmacher, Kosten und `provider`-Spalte lesen
      denselben Wert."""
    if run is None:
        run = await start_criterion_scoring_run(
            session, project, scoring_run_id, cloud_requested=use_cloud
        )
    runs.set_phase(run, ClassificationPhase.CRITERIA)
    await session.commit()

    try:
        await _assert_current_scoring_run(session, project, scoring_run_id)
        rows = await _surviving_rows(session, project.id)

        run.photos_total = len(rows)
        run.photos_processed = 0
        await session.commit()

        context = await _build_run_context(session, run, project.id, cache_dir, rows)
        models = ModelSet(
            build_detector=build_detector,
            build_animal_detector=build_animal_detector,
            build_classifier=build_classifier,
            build_aesthetics=build_aesthetics,
            build_landmarker=build_landmarker,
            build_landmark_client=build_landmark_client,
            build_place_resolver=build_place_resolver,
            build_landmark_gazetteer=build_landmark_gazetteer,
            build_embedder=build_embedder,
            build_face_analyzer=build_face_analyzer,
        )

        await run_local_phase(context, models)

        # Die Cloud-Phase laeuft NACH der obigen (rein lokalen/synchronen) Foto-Schleife und VOR
        # der Kategorieableitung/rank_photos, damit landmark-Werte noch in die
        # Kategorie-/Rangfolgenbildung einfliessen können. `project.cloud_vision_detection_enabled`
        # wird hier EINMALIG gelesen (kein Live-Reread während des Laufs, dokumentierte
        # Vereinfachung).
        #
        # SICHERHEIT - das Gate ist die KONJUNKTION aus projektweiter Einwilligung UND
        # laufbezogener `use_cloud`-Freigabe: fehlt eine der beiden, wird
        # build_landmark_client GAR NICHT ERST aufgerufen - keine Netzwerkverbindung, kein
        # API-Key nötig, kein Byte verlässt den Server, kein einziger Cloud-Aufruf im
        # gesamten Durchlauf.
        if use_cloud and project.cloud_vision_detection_enabled and rows:
            # Die Sehenswuerdigkeits-Erkennung ist ein EIGENER, benannter Teilschritt, kein
            # unsichtbarer Teil der Kriterien-Phase: bliebe `phase` hier auf `criteria`, waehrend
            # `photos_processed` bereits auf `photos_total` steht, waere ein langer Durchlauf von
            # einem haengengebliebenen nicht zu unterscheiden.
            runs.set_phase(run, ClassificationPhase.LANDMARK)
            await session.commit()
            already_scored_photo_ids = {
                photo_id
                for photo_id, criterion_key in context.existing_criterion_scores
                if criterion_key == "landmark"
            }
            landmark_candidate_ids = select_landmark_candidates(
                context.candidate_values, already_scored_photo_ids
            )
            photos_by_id = {photo.id: photo for photo, _score in rows}
            landmark_candidate_photos = [
                photos_by_id[photo_id] for photo_id in landmark_candidate_ids
            ]
            # DIE ORTSAUSKUNFT, VOR der Blockschleife und in EINEM Zug fuer alle Kandidaten -
            # nicht je Foto: derselbe Auflöser, dieselbe Tabelle, ein Durchgang durch den
            # Ortsdatensatz statt einem je Aufnahme. Die Event-Phase findet ihre Zellen danach
            # ueberwiegend bereits abgelegt vor und baut dann gar keinen Auflöser mehr (ADR 0106,
            # Konsequenzen).
            #
            # Ausschliesslich die EIGENE gemessene Koordinate des Fotos (S3): `infer_locations`
            # wird hier nicht aufgerufen, und ein Syntaxbaum-Waechter in
            # tests/test_worker_criterion_scoring_landmark_names.py haelt das fest - ein hinzugefuegter Aufruf
            # roetet sonst keinen Verhaltenstest, solange die Messlage echte Koordinaten traegt.
            landmark_place_infos = await place_infos(
                session,
                project.id,
                landmark_place_cells(landmark_candidate_photos),
                models.build_place_resolver,
            )
            landmark_hints = landmark_place_hints(landmark_candidate_photos, landmark_place_infos)
            await session.commit()
            await run_landmark_phase(
                context,
                models,
                candidate_photos=landmark_candidate_photos,
                hints=landmark_hints,
                landmark_model=landmark_model,
            )

        await write_local_motif_header(context)

        # Der RANKING-Teilschritt (Kategorieableitung + rank_photos je Partition + Schreiben der
        # PhotoRanking-Zeilen). Er gehoert fachlich zur Kriterien-Phase, laeuft aber NACH der
        # Landmark-Phase und braucht deshalb einen eigenen Namen: sonst bliebe `phase` hier auf
        # `landmark` bei 100 % Fortschritt stehen ("haengt oder laeuft?") oder muesste auf
        # `criteria` zurueckspringen. Der vierte Wert macht die Abfolge monoton.
        # Pruefpunkt vor der Rangfolge: ein Abbruch nach dem letzten Kriterium ueberspringt
        # Rangfolge, Personenangabe und Auswahlvorschlag - der Lauf bleibt ein Teilstand.
        await runs.raise_if_cancel_requested(session, run)
        runs.set_phase(run, ClassificationPhase.RANKING)
        await session.commit()

        await build_grouping_and_rankings(
            session,
            run,
            project.id,
            context.candidate_values,
            models.build_place_resolver,
            models.build_landmark_gazetteer,
        )

        # Die Id VOR der Phase: Ein verworfener Block rollt die Session zurueck und expired dabei
        # jedes Objekt, auch `project` - ein `project.id` danach liefe in ein Nachladen ausserhalb
        # des Async-Kontexts.
        project_id = project.id

        # Die LETZTE Phase, nach der Rangfolge: Die Personenangabe ist kein Motiv und geht in
        # keine Motivstaerke und keine Rangfolge ein.
        await recognize_persons(session, run, project_id, cache_dir, models.build_face_analyzer)

        # DER AUSWAHLVORSCHLAG hinter der Phase `persons` und AUSSERHALB von
        # `recognize_persons`: Er liest die Namen, die dieser Lauf ergeben hat - auch beim ersten
        # Lauf eines Projekts -, und entsteht auch dann, wenn die Phase entfaellt. Kein eigener
        # `ClassificationPhase`-Wert: er rechnet unter der zuletzt gesetzten Phase und landet
        # im selben Commit wie der Erfolgsvermerk.
        await apply_run_selection(session, run, project_id)

        run.status = ScanStatus.SUCCESS
        runs.set_phase(run, None)
        run.finished_at = runs.now_utc()
        await session.commit()
        return run
    except RunCancelled:
        await runs.finish_cancelled(session, run)
        return run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs - analog run_project_scan/run_project_scoring.
        await runs.fail_run(session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
        raise
    except Exception as exc:
        # Kein Rollback bereits committeter Fortschritts-/Kriterien-Zwischenstaende - identisches
        # Muster wie run_project_scoring.
        await runs.fail_run(session, run, str(exc))
        return run
