from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from photosort.db import Base


class ScanStatus(enum.StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    opencloud_drive_id: Mapped[str]
    opencloud_path: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Projektweiter Einwilligungs-Schalter fuer produktive Cloud-Vision-Datenfluesse
    # (urspruenglich nur die Cloud-Sehenswuerdigkeit-Erkennung, specs/features/0047-
    # sehenswuerdigkeit-erkennung-cloud-vision-api.md, decisions/0025-cloud-landmark-erkennung.md
    # Punkt 5) - Default AUS (anders als category_selection_enabled, ein rein lokales/kostenloses
    # Feature). Projektweit statt personenbezogen (konsistent mit dem "kein Innentaeter-Modell"-
    # Grundsatz, siehe Security-Abschnitt der Spec) - kein user_id-Bezug.
    #
    # Umbenannt von cloud_landmark_detection_enabled/cloud_landmark_consent_at
    # (specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
    # decisions/0032, Punkt 2 Migration a): wertsicheres RENAME COLUMN, kein neuer, zweiter
    # Consent-Schalter - dieselbe Einwilligung gated seitdem sowohl `landmark` als auch die neue
    # Remote-Kategorie-Klassifizierung. Ein Projekt, das die Cloud-Erkennung bereits aktiviert
    # hatte, bleibt nach der Migration technisch identisch aktiv.
    cloud_vision_detection_enabled: Mapped[bool] = mapped_column(default=False)
    # Zeitstempel, gesetzt beim Aktivieren, auf NULL zurueckgesetzt beim Deaktivieren - kein
    # voller Audit-Log (konsistent mit ScoringRun.gate_confirmed_at, ADR 0025 Punkt 5).
    cloud_vision_consent_at: Mapped[datetime | None] = mapped_column(default=None)

    photos: Mapped[list[Photo]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scan_runs: Mapped[list[ScanRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scoring_runs: Mapped[list[ScoringRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    # Ersetzt top_selection_runs (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
    # backfill.md, decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md, Punkt 5).
    criterion_scoring_runs: Mapped[list[CriterionScoringRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    # specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt
    # 2 Migration d - kein Cascade-Ziel fuer fine_labels selbst (projektuebergreifend, siehe
    # FineLabel-Docstring): DELETE /projects/{id} loescht ueber die photos-Kaskade oben die
    # projekteigenen photo_fine_labels-Zeilen, laesst einen weiterhin von einem ANDEREN
    # Projekt referenzierten fine_labels-Eintrag unangetastet.
    remote_category_classification_runs: Mapped[list[RemoteCategoryClassificationRun]] = (
        relationship(back_populates="project", cascade="all, delete-orphan")
    )


class RatingStatus(enum.StrEnum):
    FAVORITE = "favorite"
    ALBUM_WORTHY = "album_worthy"
    REJECTED = "rejected"


class CriterionSource(enum.StrEnum):
    """Herkunft eines PhotoCriterionScore-Werts (specs/features/0037-gatefuehrte-bewertungs-
    pipeline-mit-backfill.md, decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md, Punkt
    1). `CLOUD` ist ein reiner Registry-Wert in dieser Spec - kein source=cloud-Compute-Pfad wird
    hier implementiert (siehe Security-Abschnitt der Spec)."""

    LOCAL_HEURISTIC = "local_heuristic"
    LOCAL_ML = "local_ml"
    CLOUD = "cloud"


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (
        UniqueConstraint("project_id", "relative_path", name="uq_photo_project_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    relative_path: Mapped[str]
    etag: Mapped[str]
    content_length: Mapped[int]
    taken_at: Mapped[datetime]
    last_modified: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    project: Mapped[Project] = relationship(back_populates="photos")
    ratings: Mapped[list[Rating]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )
    score: Mapped[PhotoScore | None] = relationship(
        back_populates="photo",
        foreign_keys="PhotoScore.photo_id",
        uselist=False,
        cascade="all, delete-orphan",
    )
    criterion_scores: Mapped[list[PhotoCriterionScore]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )
    # specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: 1:1 wie score oben,
    # optional (nur angelegt, wenn tatsaechlich ein Landmark-Name identifiziert wurde).
    landmark_detection: Mapped[PhotoLandmarkDetection | None] = relationship(
        back_populates="photo", uselist=False, cascade="all, delete-orphan"
    )
    # specs/features/0055, ADR 0032 Punkt 2 Migration c2, umbenannt in
    # specs/features/0289-feste-kategorien.md: 1:N (0-2 Zeilen pro Foto, ein freies Feinlabel je
    # Zeile). Feinlabels sind seit Spec 0289 reine ZUSATZINFORMATION am Foto - sie bilden keine
    # Kategorie mehr (siehe category_classification unten).
    fine_labels: Mapped[list[PhotoFineLabel]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )
    # specs/features/0289-feste-kategorien.md, Umsetzungsschritt 3a: 1:1 wie score/
    # landmark_detection, optional (nur angelegt, wenn ein Remote-Klassifizierungslauf dieses Foto
    # tatsaechlich verarbeitet hat).
    category_classification: Mapped[PhotoCategoryClassification | None] = relationship(
        back_populates="photo", uselist=False, cascade="all, delete-orphan"
    )
    # specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
    # fehler-persistierung.md Punkt 2: hoechstens zwei Zeilen pro Foto (eine je CloudVisionPhase),
    # ausschliesslich der jeweils LETZTE bekannte Fehlschlag, kein Verlauf.
    cloud_vision_errors: Mapped[list[PhotoCloudVisionError]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    files_found: Mapped[int] = mapped_column(default=0)
    photos_added: Mapped[int] = mapped_column(default=0)
    photos_updated: Mapped[int] = mapped_column(default=0)
    photos_removed: Mapped[int] = mapped_column(default=0)
    files_skipped: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(default=None)
    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR 0019):
    # server-seitig defaultet (analog started_at), damit ein frisch angelegter Lauf sofort einen
    # last_progress_at-Wert hat und nicht bereits ab Zeile 1 als Stillstand gilt. Wird an denselben
    # Stellen wie files_found periodisch zwischen-committet (worker.py::
    # _maybe_commit_progress_checkpoint, seit specs/features/0036-scan-performance-zweiphasig-
    # parallel.md aus Phase 1/Phase 2a von run_project_scan aufgerufen) und von
    # worker.py::reap_stalled_runs gelesen.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020: additiv, default=None
    # (nicht 0) - unterscheidet bewusst "Enumerationsphase (Phase 1) noch nicht abgeschlossen,
    # Gesamtzahl unbekannt" von "Projekt enthaelt 0 Dateien". Ueberall mit `is not None` statt
    # truthy zu pruefen (0 ist ein gueltiger, informativer Wert). Wird nach Abschluss von Phase 1
    # (worker.py::run_project_scan) einmalig auf len(entries) gesetzt und danach nicht mehr
    # veraendert.
    total_files: Mapped[int | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="scan_runs")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Rating(Base):
    """Bewertung eines Photos durch einen User (specs/features/0002-manual-categorization.md).

    "Unbewertet" wird bewusst nicht als eigener Enum-Wert modelliert, sondern als Fehlen einer
    Zeile fuer (photo_id, user_id) - macht Toggle/Ueberschreiben zu einem einfachen Upsert ueber
    den Unique-Constraint, siehe api/ratings.py.
    """

    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("photo_id", "user_id", name="uq_rating_photo_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[RatingStatus] = mapped_column(
        SQLEnum(RatingStatus, native_enum=False, length=20)
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    photo: Mapped[Photo] = relationship(back_populates="ratings")
    user: Mapped[User] = relationship()


class ScoringRun(Base):
    """Ein Lauf des lokalen Scoring-Jobs (specs/features/0003-automatic-best-photo-selection.md,
    decisions/0006-local-scoring-datamodel.md), analog ScanRun. Nutzt bewusst denselben
    ScanStatus-Enum wie ScanRun statt eines eigenen ScoringStatus - beide Enums haben identische
    Semantik (running/success/failed) fuer einen asynchron laufenden Worker-Job.

    photos_total/photos_processed liefern granularen Live-Fortschritt (periodisch
    zwischen-committet, siehe worker.py::run_project_scoring) - analog zu ScanRun.files_found, das
    seit specs/features/0022-scan-live-fortschrittszaehler.md ebenfalls periodisch statt nur am
    Ende committet wird (siehe worker.py::run_project_scan, SCAN_COMMIT_BATCH_SIZE).
    """

    __tablename__ = "scoring_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    photos_total: Mapped[int] = mapped_column(default=0)
    photos_processed: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(default=None)
    # Anzahl der Fotos, deren PhotoScore.suggested_status in diesem Lauf gesetzt wurde
    # (Duplikat-Verlierer + zu unscharfe Fotos, siehe worker.py::run_project_scoring,
    # Variable rejected_ids). Bleibt bei einem fehlgeschlagenen Lauf auf dem Default 0 - kein
    # irrefuehrender Teilstand (specs/features/0021-scoring-run-vorschlagszaehler.md).
    suggestions_found: Mapped[int] = mapped_column(default=0, server_default="0")
    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md), analog
    # ScanRun.last_progress_at oben.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Ausschuss-Gate (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md,
    # decisions/0021, Punkt 6): additiv, projektweit (kein user_id-Bezug, bewusst konsistent mit
    # allen anderen Run-Tabellen - nur Rating ist personenbezogen, siehe Security-Abschnitt der
    # Spec). None = Gate noch nicht bestaetigt. Wird entweder ueber POST /confirm-ausschuss-gate
    # gesetzt oder automatisch von run_project_scoring, wenn suggestions_found == 0 (kein
    # Ausschuss zum Sichten vorhanden).
    gate_confirmed_at: Mapped[datetime | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="scoring_runs")


class PhotoScore(Base):
    """Automatisch berechnete Bewertungsgrundlage eines Fotos, 1:1 zu Photo
    (specs/features/0003-automatic-best-photo-selection.md, decisions/0006-local-scoring-
    datamodel.md). Bewusst KEINE Rating-Zeile und bewusst eine eigene Tabelle statt eines
    source-Felds an Rating (siehe ADR 0006) - ein Vorschlag wird erst durch aktive
    Nutzerbestaetigung ueber den bestehenden PUT /photos/{id}/rating-Endpunkt zu einer echten
    Bewertung. `photo_id` ist Primary Key (kein separates id+Unique-Constraint-Paar wie bei
    Rating), weil es strukturell nie mehrere Zeilen pro Foto gibt.
    """

    __tablename__ = "photo_scores"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    sharpness: Mapped[float]
    exposure: Mapped[float]
    phash: Mapped[str | None] = mapped_column(default=None)
    # Selbstreferenzierender FK auf photos.id (nicht auf photo_scores.photo_id): zeigt auf das im
    # Duplikat-/Burst-Cluster behaltene FOTO, das nicht zwingend selbst schon eine PhotoScore-Zeile
    # braucht, um referenziert werden zu koennen.
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("photos.id"), default=None)
    cluster_key: Mapped[str | None] = mapped_column(default=None)
    # Wiederverwendet das bestehende RatingStatus-Enum (Akzeptanzkriterium der Spec) - Phase A
    # setzt darueber praktisch nur REJECTED, offene Positivempfehlungen bleiben Phase B
    # vorbehalten, ohne dass das Feld dafuer erneut migriert werden muesste.
    suggested_status: Mapped[RatingStatus | None] = mapped_column(
        SQLEnum(RatingStatus, native_enum=False, length=20), default=None
    )
    computed_at: Mapped[datetime]
    # `category`/`local_quality_score` (specs/features/0024) entfallen ersatzlos
    # (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md, decisions/0021, Punkt
    # 2) - reiner, nie manuell editierter Ableitungszustand, dessen Nachfolge jetzt strukturell
    # durch PhotoCriterionScore+PhotoRanking (Kriterien-/Rangfolgen-Schicht) uebernommen wird statt
    # in eigenen PhotoScore-Spalten.
    #
    # specs/features/0055, ADR 0032 Punkt 2 Migration b: additiv, dauerhafte manuelle
    # Uebersteuerung des sonst automatisch abgeleiteten category_key
    # (worker.py::run_criterion_scoring verwendet `score.category_override or
    # resolve_category(...)`) - ueberlebt damit auch kuenftige volle Re-Scoring-Laeufe.
    #
    # specs/features/0289-feste-kategorien.md: der zulaessige Wertebereich ist seit dieser Spec das
    # geschlossene 13er-Set (categories.py::CATEGORY_REGISTRY), nicht mehr ein beliebiger
    # `canonical_key`. Weiterhin freier String ohne FK - die Whitelist-Pruefung
    # (`is_known_category`) lebt am Override-Endpunkt selbst, nicht hier; der LESEPFAD bleibt
    # bewusst tolerant gegenueber einem Altwert ausserhalb des Sets (Defense in Depth gegen einen
    # unvollstaendig gelaufenen Migrationsschritt, Security-Abschnitt der Spec Punkt 2).
    category_override: Mapped[str | None] = mapped_column(default=None)

    photo: Mapped[Photo] = relationship(back_populates="score", foreign_keys=[photo_id])


class PhotoCriterionScore(Base):
    """Ein normierter Kriterien-Wert fuer ein Foto (specs/features/0037-gatefuehrte-bewertungs-
    pipeline-mit-backfill.md, decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md, Punkt
    1) - generische Tabelle statt weiterer fixer PhotoScore-Spalten, damit neue Kriterien nie eine
    neue Migration erzwingen (nur einen neuen Eintrag in criteria.py::CRITERIA_REGISTRY).
    `criterion_key` ist bewusst ein freier String (kein Enum) - genau das macht die Erweiterbarkeit
    aus. `value` ist immer bereits auf [0, 1] normiert, "hoeher = besser", zum
    Berechnungszeitpunkt (nicht erst beim Lesen). UniqueConstraint(photo_id, criterion_key): ein
    erneuter Kriterien-Lauf ueberschreibt (Upsert) den bestehenden Wert, keine Historie."""

    __tablename__ = "photo_criterion_scores"
    __table_args__ = (
        UniqueConstraint("photo_id", "criterion_key", name="uq_criterion_score_photo_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))
    criterion_key: Mapped[str]
    value: Mapped[float]
    source: Mapped[CriterionSource] = mapped_column(
        SQLEnum(CriterionSource, native_enum=False, length=20)
    )
    computed_at: Mapped[datetime]

    photo: Mapped[Photo] = relationship(back_populates="criterion_scores")


class ClassificationPhase(enum.StrEnum):
    """Die beiden Teilschritte eines verketteten Klassifizierungslaufs (specs/features/0296-
    klassifizierung-ein-ausloeser-cloud-checkbox.md, decisions/0050-verketteter-klassifizierungs-
    lauf-mit-laufbezogener-cloud-freigabe.md Punkt 1) - in genau dieser Reihenfolge, damit die
    Remote-Ergebnisse noch im selben Lauf in die Kategorieableitung einfliessen.

    REMOTE_CATEGORIES laeuft nur bei angeforderter UND eingewilligter Cloud-Nutzung; CRITERIA
    laeuft immer. Getragen von CriterionScoringRun.phase, dort NULL sobald der Lauf beendet ist."""

    REMOTE_CATEGORIES = "remote_categories"
    CRITERIA = "criteria"


class CriterionScoringRun(Base):
    """Ein Lauf des Kriterien-/Rangfolgen-Jobs (specs/features/0037-gatefuehrte-bewertungs-
    pipeline-mit-backfill.md, decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md, Punkt
    5) - ersetzt TopSelectionRun/select_top_photos vollstaendig. Analog ScoringRun/ScanRun (nutzt
    denselben ScanStatus-Enum). `scoring_run_id` bindet den Lauf explizit an den ScoringRun, dessen
    Ausschuss-Ergebnis (insb. cluster_key) er voraussetzt - Grundlage fuer den 409-Staleness-Guard
    bei einem zwischenzeitlichen Re-Scan/Re-Scoring (ADR 0021, Punkt 7).

    photos_total/photos_processed liefern granularen Live-Fortschritt (periodisch zwischen-
    committet, siehe worker.py::run_criterion_scoring) - analog ScoringRun.photos_total/
    photos_processed. Kein top_n_per_cluster/candidates_total mehr (anders als das fruehere
    TopSelectionRun): N ist beim Scoren nicht mehr bekannt, wird erst beim Lesen angewendet (ADR
    0021, Punkt 4) - der Job verarbeitet immer alle Ausschuss-Ueberlebenden. Kein suggestions_found
    mehr: der Job waehlt keine Top-N mehr aus, sondern berechnet immer den vollen Rangfolge-Pool je
    Partition (siehe PhotoRanking)."""

    __tablename__ = "criterion_scoring_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    scoring_run_id: Mapped[int] = mapped_column(ForeignKey("scoring_runs.id"))
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    photos_total: Mapped[int] = mapped_column(default=0)
    photos_processed: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(default=None)
    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md), analog
    # ScanRun.last_progress_at oben.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, decisions/0050-
    # verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md Punkt 3: diese Zeile
    # ist seit Spec 0296 der Run-Datensatz des GESAMTEN Klassifizierungslaufs, nicht mehr nur
    # seiner Kriterien-Phase - sie wird deshalb von worker.py::run_classification angelegt, bevor
    # die erste Phase startet, und nicht mehr von run_criterion_scoring selbst. Ohne diesen
    # frueheren Anlagezeitpunkt zeigte `last_criterion_scoring_run` waehrend der Remote-Phase noch
    # auf den Lauf DAVOR, und die Oberflaeche haette keinen Anker fuer den laufenden Vorgang.
    #
    # `phase`: der gerade laufende Teilschritt; NULL heisst "laeuft nicht mehr" (beendet - oder
    # Altzeile aus der Zeit der getrennten Ausloesung). Bewusst KEIN eigener Enum-Wert "done":
    # der Abschluss steht bereits in `status`, ein zweiter Ort dafuer koennte auseinanderlaufen.
    phase: Mapped[ClassificationPhase | None] = mapped_column(
        SQLEnum(ClassificationPhase, native_enum=False, length=20), default=None
    )
    # War die Cloud-Nutzung fuer DIESEN Lauf angefordert (Checkbox am Ausloeser)? Macht
    # nachtraeglich erkennbar, ob das Ergebnis ueberhaupt Cloud-Anreicherung enthalten kann.
    # Sagt NICHT, ob tatsaechlich Cloud-Aufrufe stattgefunden haben - das Gate ist die Konjunktion
    # mit Project.cloud_vision_detection_enabled (ADR 0050 Punkt 2).
    cloud_requested: Mapped[bool] = mapped_column(default=False)
    # Menschenlesbare Zusammenfassung der Cloud-Probleme dieses Laufs (ADR 0050 Punkt 4), NULL =
    # keine. Laufebene, nicht Foto-Ebene: die Einzelfehler bleiben pro Foto in
    # photo_cloud_vision_errors abrufbar (ADR 0035). Gesetzt zu werden heisst NICHT, dass der Lauf
    # fehlgeschlagen ist - der lokale Bewertungsanteil laeuft trotzdem vollstaendig durch, der
    # Lauf endet mit SUCCESS, das Ergebnis ist nur nicht (vollstaendig) angereichert.
    cloud_error_message: Mapped[str | None] = mapped_column(default=None)

    # specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-
    # remote-laeufe.md Punkt 3: die IST-Kosten-Buchfuehrung des Landmark-Anteils dieses
    # Laufs.
    # Praefix `landmark_`, weil diese Tabelle seit ADR 0050 den GESAMTEN
    # Klassifizierungslauf traegt und die Kriterien-Phase selbst nichts kostet.
    #
    # Alle vier Spalten sind NULLABLE mit Python-seitigem Default `0` - exakt das
    # `ScanRun.total_files`-Idiom: `NULL` heisst "nicht erfasst" (Zeile aus der Zeit vor
    # der zugehoerigen Migration), `0` heisst "erfasst, es sind keine Kosten angefallen".
    # Ohne diese Unterscheidung waere ein Altlauf nicht von einem kostenlosen Lauf zu
    # trennen; auf genau ihr beruht Befund (a) des Unvollstaendigkeits-Hinweises der
    # Statistikseite (ADR 0051 Punkt 5). Ueberall mit `is None` statt truthy zu pruefen.
    #
    # `landmark_api_calls` zaehlt jeden STATTGEFUNDENEN Aufruf, auch wenn dessen `usage`-Block
    # fehlte (der Tokenbeitrag ist dann 0). Das ist zugleich der Ausloeser fuer Befund (b):
    # ein Betrag von exakt 0 bei nachweislich abgesetzten Aufrufen ist bei Token-Preisen
    # groesser null strukturell unmoeglich und damit ein zuverlaessiger Indikator fuer eine
    # Erfassungsluecke.
    #
    # `landmark_cost_usd` ist der beim Laufende EINGEFRORENE Betrag (ADR 0051 Punkt 4) - eine
    # spaetere Preisaenderung veraendert keinen historischen Betrag. `None` trotz erfasster
    # Tokens heisst: das Modell war in `pricing.py::MODEL_PRICING` nicht hinterlegt.
    # `float` statt `Numeric` (ADR 0051 Punkt 3): Cent-Betraege, keine Buchhaltung,
    # gerundet wird erst bei der Ausgabe. Tokens und Aufrufzahl werden bewusst OHNE
    # eigenen Anzeigepfad mitgespeichert (eng begrenzte Ausnahme, ADR 0051 Punkt 3): ohne
    # sie ist ein historischer Betrag nach einer erkannten Preiskorrektur nicht mehr
    # nachrechenbar, und der Verbrauch existiert nur im Moment der API-Antwort.
    landmark_api_calls: Mapped[int | None] = mapped_column(default=0)
    landmark_input_tokens: Mapped[int | None] = mapped_column(default=0)
    landmark_output_tokens: Mapped[int | None] = mapped_column(default=0)
    landmark_cost_usd: Mapped[float | None] = mapped_column(default=0)

    project: Mapped[Project] = relationship(back_populates="criterion_scoring_runs")


class PhotoRanking(Base):
    """Der volle, sortierte Kandidatenpool einer Partition (cluster_key x category_key) fuer einen
    CriterionScoringRun (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md,
    decisions/0021, Punkt 4) - NICHT nur die Top-N. Macht "zeig die besten X pro Kategorie" zu
    einer reinen Lese-Query (GET /projects/{id}/photos?top_n_per_category=N) statt eines
    Job-Parameters, und macht Backfill zu einem reinen Nebeneffekt eines erneuten Abrufs nach einer
    Rating-Aenderung, ohne dass irgendein Server-Code aktiv "nachrueckt".
    `category_key` ist wie `criterion_key` ein freier String (kein PhotoCategory-Enum mehr) -
    dieselbe Erweiterbarkeits-Begruendung. `rank_position` ist 1-basiert innerhalb der Partition.
    UniqueConstraint(criterion_scoring_run_id, photo_id): jedes Foto taucht pro Lauf hoechstens
    einmal auf (es gehoert zu genau einer Partition)."""

    __tablename__ = "photo_rankings"
    __table_args__ = (
        UniqueConstraint(
            "criterion_scoring_run_id", "photo_id", name="uq_photo_ranking_run_photo"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    criterion_scoring_run_id: Mapped[int] = mapped_column(ForeignKey("criterion_scoring_runs.id"))
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))
    cluster_key: Mapped[str]
    category_key: Mapped[str]
    rank_score: Mapped[float]
    rank_position: Mapped[int]


class PhotoLandmarkDetection(Base):
    """Der vom Vision-LLM identifizierte Sehenswuerdigkeit-Name, 1:1 zu Photo
    (specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, decisions/0025-cloud-
    landmark-erkennung.md Punkt 6) - analog PhotoScore. `photo_id` ist Primary Key (kein
    separates id+Unique-Constraint-Paar wie bei PhotoCriterionScore), weil dies eine optionale
    Detail-Zeile pro Foto ist, kein Mehrfach-Kriterien-Fact. Nur angelegt, wenn tatsaechlich ein
    Name identifiziert wurde (kein Platzhalter-"unbekannt"). `confidence` dupliziert bewusst den
    zugehoerigen PhotoCriterionScore(criterion_key="landmark").value (ADR 0025 Punkt 6) - haelt
    diese Tabelle fuer eine spaetere UI-Abfrage ohne Join selbsttragend, beide Werte stammen
    atomar aus derselben API-Antwort (kein Divergenzrisiko). Kein UI-Verweis in v1 - reine
    Persistenz-Vorbereitung, vermeidet einen spaeteren, erneut kostenpflichtigen Cloud-Durchlauf
    aller bereits gescorten Fotos, falls der Name doch einmal angezeigt werden soll.

    `provider` (specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-
    mistral-provider-option-cloud-landmark.md Punkt 5) haelt fest, welcher Cloud-Provider diese
    Zeile erzeugt hat - verhindert, dass die Herkunft bereits gescorter Fotos bei einem spaeteren
    Umschalten von Settings.landmark_provider stillschweigend unklar wird. Atomar im selben
    Upsert wie name/confidence gesetzt (worker.py::_upsert_landmark_detection). Python-seitiger
    Default "anthropic" (analog Project.cloud_vision_detection_enabled oben) deckt bereits
    bestehende Zeilen aus der Zeit vor dieser Spalte ab, in der Anthropic der einzige Provider
    war - worker.py setzt den Wert im produktiven Pfad trotzdem immer explizit."""

    __tablename__ = "photo_landmark_detections"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    name: Mapped[str]
    confidence: Mapped[float]
    computed_at: Mapped[datetime]
    provider: Mapped[str] = mapped_column(default="anthropic")

    photo: Mapped[Photo] = relationship(back_populates="landmark_detection")


class FineLabel(Base):
    """Kanonische Registry der frei formulierten Feinlabels (specs/features/0055, ADR 0032 Punkt 2
    Migration c1; in specs/features/0289-feste-kategorien.md von `CategoryLabel` umbenannt).

    Der ZWECK hat sich mit Spec 0289 verschoben, die Struktur nicht: die Eintraege bilden keine
    Kategorien mehr (das tut das feste Set in categories.py), sondern dienen der
    Feinlabel-Haeufigkeitsauswertung (`GET /projects/{id}/fine-labels`) - dort macht die
    Kanonisierung ueber Embeddings sie erst belastbar ("Hund"/"Hunde"/"dog" als ein Eintrag).

    Bewusst PROJEKTUEBERGREIFEND (kein project_id-Bezug, ADR 0032 Begruendung): reine
    Vokabular-Eintraege ("hund" ist kein personenbezogenes/projektspezifisches Datum), keine
    Fotoinhalte. Eine projektgebundene Registry wuerde bei mehreren Projekten identische Label
    wiederholt neu anlegen und die Cluster-Qualitaet unnoetig verschlechtern (weniger Beispiele
    pro Cluster) - fuer dieses Zwei-Personen-Familienprojekt (keine Mandantentrennung zwischen
    Projekten noetig) eine bewusste, dokumentierte Vereinfachung. Die HAEUFIGKEITSABFRAGE ist
    deshalb zwingend ueber `photo_fine_labels -> photos.project_id` zu skopieren (Security-
    Abschnitt der Spec 0289, Punkt 1) - ein globales SELECT auf diese Tabelle wuerde
    Label-Haeufigkeiten anderer Projekte ausliefern.

    `canonical_key` ist ein URL-/Key-sicherer Slug (remote_classification.py::_slugify),
    `display_name` der zuerst gesehene Roh-Label-Text in Originalschreibweise (reine Anzeige-
    Hilfe, keine kuratierte Uebersetzung). `embedding` ist der 384-dimensionale Text-Embedding-
    Vektor (label_embedding.py) als JSON-Liste von float - kein pgvector/Vektor-Index noetig
    (ADR 0032: kleine, langsam wachsende Menge, ein voller Scan pro Aufloesung ist unproblematisch).
    """

    __tablename__ = "fine_labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_key: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(SQLJSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    photo_fine_labels: Mapped[list[PhotoFineLabel]] = relationship(back_populates="fine_label")


class PhotoFineLabel(Base):
    """Ein vom Vision-LLM frei formuliertes, auf einen kanonischen Eintrag aufgeloestes Feinlabel
    (specs/features/0055, decisions/0032 Punkt 2 Migration c2; in
    specs/features/0289-feste-kategorien.md von `PhotoCategoryDetection` umbenannt) - 1:N zu Photo,
    0 bis MAX_FINE_LABELS_PER_PHOTO Zeilen pro Foto. Anders als bis Spec 0289 ist die Zeilenzahl
    ausdruecklich auch 0 zulaessig: der Prompt erzwingt kein Feinlabel mehr, die Pflichtaussage je
    Foto ist die Kategorie (PhotoCategoryClassification), nicht das Label.

    `raw_label` ist der - bereits zeichensanierte (remote_classification.py::_sanitize_label_text)
    - vom Vision-LLM gelieferte Text (Audit-/Debug-Spur, welche konkrete Formulierung auf welchen
    canonical_key gemappt wurde). `confidence` ist mit Spec 0289 ERSATZLOS entfallen (ADR 0049
    Entwurfsentscheidung 7: die Zahl diente ausschliesslich der abgeloesten Score-Auswahl, eine
    persistierte Zahl ohne Codepfad waere irrefuehrender Ballast).

    UniqueConstraint(photo_id, fine_label_id): verhindert zwei Zeilen fuer dasselbe
    Foto x kanonisches-Label-Paar (relevant, falls beide Feinlabels eines Fotos auf denselben
    canonical_key clustern - dann wird nur eine Zeile geschrieben, siehe
    worker.py::run_remote_category_classification)."""

    __tablename__ = "photo_fine_labels"
    __table_args__ = (
        UniqueConstraint("photo_id", "fine_label_id", name="uq_fine_label_photo_label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))
    fine_label_id: Mapped[int] = mapped_column(ForeignKey("fine_labels.id"))
    raw_label: Mapped[str]
    provider: Mapped[str]
    computed_at: Mapped[datetime]

    photo: Mapped[Photo] = relationship(back_populates="fine_labels")
    fine_label: Mapped[FineLabel] = relationship(back_populates="photo_fine_labels")


class PhotoCategoryClassification(Base):
    """Das Ergebnis der Remote-Kategorie-Klassifizierung eines Fotos (specs/features/0289-feste-
    kategorien.md, Umsetzungsschritt 3a) - 1:1 zu Photo, `photo_id` ist Primary Key (strukturell
    nie mehrere Zeilen pro Foto, gleiche Begruendung wie bei PhotoScore/PhotoLandmarkDetection).

    `category_key` ist das bereits ueber `categories.py::resolve_category` aufgeloeste Ergebnis der
    remote genannten Kandidaten - also immer ein Wert aus dem festen Set, nie ein Rohwert des
    Modells. `detected_categories` haelt die VALIDIERTE Kandidatenliste (ausschliesslich bekannte
    Set-Keys, unbekannte Rohwerte sind bereits verworfen) als JSON-Liste; sie wird ueber
    `PhotoOut.category_candidates` ausgeliefert. Security-Muss-Kriterium (Spec 0289, Abschnitt 5):
    hier landet NIE die Rohliste des Modells - sonst wanderte unvalidierter Fremdtext ueber einen
    zweiten Kanal in API-Antwort und UI.

    Die PRAESENZ dieser Zeile ist zugleich das Erfolgssignal der Remote-Phase (Skip-Kriterium in
    worker.py::select_remote_category_candidates und Statusableitung in
    api/photos.py::_cloud_vision_status_out) - sie entsteht auch dann, wenn `category_key`
    `nicht_erkannt` lautet (kein "nichts gefunden"-Sonderfall)."""

    __tablename__ = "photo_category_classifications"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    category_key: Mapped[str]
    detected_categories: Mapped[list[str]] = mapped_column(SQLJSON)
    provider: Mapped[str]
    computed_at: Mapped[datetime]

    photo: Mapped[Photo] = relationship(back_populates="category_classification")


class RemoteCategoryClassificationRun(Base):
    """Ein Lauf des Remote-Kategorie-Klassifizierungs-Jobs (specs/features/0055-remote-kategorie-
    klassifizierung-mit-kostenschaetzung.md, decisions/0032, Punkt 2 Migration d) - Run-Tracking
    analog CriterionScoringRun/ScoringRun/ScanRun, aber bewusst OHNE scoring_run_id-FK: dieser Job
    schreibt ausschliesslich in photo_category_classifications/photo_fine_labels/fine_labels,
    beruehrt weder cluster_key noch PhotoRanking direkt - kein 409-Staleness-Guard, kein
    Ausschuss-Gate-
    Erfordernis (anders als run_criterion_scoring)."""

    __tablename__ = "remote_category_classification_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    photos_total: Mapped[int] = mapped_column(default=0)
    photos_processed: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(default=None)
    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md), analog
    # ScanRun.last_progress_at/ScoringRun.last_progress_at/CriterionScoringRun.last_progress_at.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-
    # remote-laeufe.md Punkt 3: die IST-Kosten-Buchfuehrung des Remote-Kategorie-Anteils dieses
    # Laufs.
    # Kein Praefix - dieser Lauf hat genau einen Zweck.
    #
    # Alle vier Spalten sind NULLABLE mit Python-seitigem Default `0` - exakt das
    # `ScanRun.total_files`-Idiom: `NULL` heisst "nicht erfasst" (Zeile aus der Zeit vor
    # der zugehoerigen Migration), `0` heisst "erfasst, es sind keine Kosten angefallen".
    # Ohne diese Unterscheidung waere ein Altlauf nicht von einem kostenlosen Lauf zu
    # trennen; auf genau ihr beruht Befund (a) des Unvollstaendigkeits-Hinweises der
    # Statistikseite (ADR 0051 Punkt 5). Ueberall mit `is None` statt truthy zu pruefen.
    #
    # `api_calls` zaehlt jeden STATTGEFUNDENEN Aufruf, auch wenn dessen `usage`-Block
    # fehlte (der Tokenbeitrag ist dann 0). Das ist zugleich der Ausloeser fuer Befund (b):
    # ein Betrag von exakt 0 bei nachweislich abgesetzten Aufrufen ist bei Token-Preisen
    # groesser null strukturell unmoeglich und damit ein zuverlaessiger Indikator fuer eine
    # Erfassungsluecke.
    #
    # `cost_usd` ist der beim Laufende EINGEFRORENE Betrag (ADR 0051 Punkt 4) - eine
    # spaetere Preisaenderung veraendert keinen historischen Betrag. `None` trotz erfasster
    # Tokens heisst: das Modell war in `pricing.py::MODEL_PRICING` nicht hinterlegt.
    # `float` statt `Numeric` (ADR 0051 Punkt 3): Cent-Betraege, keine Buchhaltung,
    # gerundet wird erst bei der Ausgabe. Tokens und Aufrufzahl werden bewusst OHNE
    # eigenen Anzeigepfad mitgespeichert (eng begrenzte Ausnahme, ADR 0051 Punkt 3): ohne
    # sie ist ein historischer Betrag nach einer erkannten Preiskorrektur nicht mehr
    # nachrechenbar, und der Verbrauch existiert nur im Moment der API-Antwort.
    api_calls: Mapped[int | None] = mapped_column(default=0)
    input_tokens: Mapped[int | None] = mapped_column(default=0)
    output_tokens: Mapped[int | None] = mapped_column(default=0)
    cost_usd: Mapped[float | None] = mapped_column(default=0)

    project: Mapped[Project] = relationship(back_populates="remote_category_classification_runs")


class CloudVisionPhase(enum.StrEnum):
    """Die beiden unabhaengigen Cloud-Vision-Laeufe, fuer die specs/features/0058-cloud-vision-
    status-transparenz.md/decisions/0035-cloud-vision-attempt-fehler-persistierung.md pro Foto
    einen von sechs Zustaenden ableitet - LANDMARK (ADR 0025) und REMOTE_CATEGORY (ADR 0032)."""

    LANDMARK = "landmark"
    REMOTE_CATEGORY = "remote_category"


class PhotoCloudVisionError(Base):
    """Der letzte bekannte Fehlschlag eines Cloud-Vision-Laufs fuer ein Foto
    (specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
    fehler-persistierung.md Punkt 2) - bewusst KEIN Verlauf: ein erneuter Fehlschlag ueberschreibt
    (Upsert, worker.py::_record_cloud_vision_error) die bestehende Zeile, ein erfolgreicher Retry
    LOESCHT sie (worker.py::_clear_cloud_vision_error). Composite PK (photo_id, phase) statt eines
    separaten id+UniqueConstraint-Paars (wie PhotoScore/PhotoLandmarkDetection): es gibt
    strukturell hoechstens eine sinnvolle "letzter Fehlschlag"-Zeile je Foto x CloudVisionPhase.

    `error_type`/`error_message` sind identischer Inhalt wie der WARNING-Log-Eintrag aus
    specs/features/0056-structured-logging-cloud-vision-errors.md/ADR 0034 (`type(exc).__name__`,
    `str(exc)`) - an der jeweiligen worker.py-Call-Site EINMAL berechnet, an beide Senken (Logger,
    hier) weitergereicht, keine zweite Auswertung. `error_message` wird beim Schreiben auf
    worker.py::_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH (500 Zeichen) gekappt - defensiver
    Schutz gegen eine entartete Fehlermeldung, analog remote_classification.py::
    MAX_REMOTE_LABEL_LENGTH. Die bereits in ADR 0034 verifizierte Sanitisierung von `str(exc)`
    (keine Secrets/Rohdaten) bleibt die eigentliche Absicherung, die Kappung ist nur eine
    Storage-/Degenerationsgrenze (Security-Abschnitt der Spec 0058).

    `attempted_at`: Zeitpunkt des letzten Fehlschlags - keine weiteren Metadaten (kein HTTP-
    Statuscode, kein Provider-Feld, siehe ADR 0035 Punkt 2)."""

    __tablename__ = "photo_cloud_vision_errors"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    phase: Mapped[CloudVisionPhase] = mapped_column(
        SQLEnum(CloudVisionPhase, native_enum=False, length=20), primary_key=True
    )
    error_type: Mapped[str]
    error_message: Mapped[str]
    attempted_at: Mapped[datetime]

    photo: Mapped[Photo] = relationship(back_populates="cloud_vision_errors")
