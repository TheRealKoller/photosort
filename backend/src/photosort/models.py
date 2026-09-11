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
    # Projektweiter Einwilligungs-Schalter für produktive Cloud-Vision-Datenflüsse. Es ist der
    # EINE Schalter für beide Cloud-Anteile (landmark und Remote-Kategorie-Klassifizierung), kein
    # zweiter daneben. Default AUS (anders als category_selection_enabled, ein rein lokales,
    # kostenloses Feature). Projektweit statt personenbezogen, konsistent mit dem "kein
    # Innentäter-Modell"-Grundsatz - kein user_id-Bezug.
    cloud_vision_detection_enabled: Mapped[bool] = mapped_column(default=False)
    # Zeitstempel, gesetzt beim Aktivieren, auf NULL zurückgesetzt beim Deaktivieren - bewusst
    # kein voller Audit-Log (konsistent mit ScoringRun.gate_confirmed_at).
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
    criterion_scoring_runs: Mapped[list[CriterionScoringRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    # Kein Cascade-Ziel für fine_labels selbst (projektübergreifend, siehe FineLabel-Docstring):
    # DELETE /projects/{id} löscht über die photos-Kaskade oben die projekteigenen
    # photo_fine_labels-Zeilen, lässt einen weiterhin von einem ANDEREN Projekt referenzierten
    # fine_labels-Eintrag unangetastet.
    remote_category_classification_runs: Mapped[list[RemoteCategoryClassificationRun]] = (
        relationship(back_populates="project", cascade="all, delete-orphan")
    )


class RatingStatus(enum.StrEnum):
    FAVORITE = "favorite"
    ALBUM_WORTHY = "album_worthy"
    REJECTED = "rejected"


class CriterionSource(enum.StrEnum):
    """Herkunft eines PhotoCriterionScore-Werts."""

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
    # Dezimalgrad aus dem EXIF-GPSInfo-IFD (opencloud/exif.py::extract_gps), beim Scan aus
    # demselben Range-Read-Fenster wie `taken_at` gelesen. `None` heißt "kein Ort bekannt" - es
    # gibt NIE eine halbe Koordinate: scheitert eine Komponente, sind beide Felder `None`
    # (Paar-Invariante von extract_gps). Volle EXIF-Präzision, keine Rundung beim Speichern; die
    # Anzeigerundung auf zwei Nachkommastellen liegt allein in api/photos.py::cluster_place.
    #
    # KEIN server_default und kein Backfill: `0.0` wäre eine gültige Koordinate (Golf von
    # Guinea), kein Abwesenheitswert. Bereits gescannte Fotos bleiben ohne Koordinate, bis sich
    # die Datei auf OpenCloud ändert.
    gps_lat: Mapped[float | None] = mapped_column(default=None)
    gps_lon: Mapped[float | None] = mapped_column(default=None)
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
    # 1:1 wie score oben, optional - nur angelegt, wenn tatsächlich ein Landmark-Name
    # identifiziert wurde.
    landmark_detection: Mapped[PhotoLandmarkDetection | None] = relationship(
        back_populates="photo", uselist=False, cascade="all, delete-orphan"
    )
    # 1:N (0-2 Zeilen pro Foto, ein freies Feinlabel je Zeile). Feinlabels sind reine
    # ZUSATZINFORMATION am Foto - sie bilden keine Kategorie (siehe category_classification).
    fine_labels: Mapped[list[PhotoFineLabel]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )
    # 1:1 wie score/landmark_detection, optional - nur angelegt, wenn ein
    # Remote-Klassifizierungslauf dieses Foto tatsächlich verarbeitet hat.
    category_classification: Mapped[PhotoCategoryClassification | None] = relationship(
        back_populates="photo", uselist=False, cascade="all, delete-orphan"
    )
    # Höchstens zwei Zeilen pro Foto (eine je CloudVisionPhase), ausschließlich der jeweils
    # LETZTE bekannte Fehlschlag, kein Verlauf.
    cloud_vision_errors: Mapped[list[PhotoCloudVisionError]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )
    # Die Foto-Seite derselben Kaskade wie bei CriterionScoringRun.rankings, und hier kein
    # Schönheitsfehler: worker.py::run_project_scan löscht beim Re-Scan die auf OpenCloud
    # verschwundenen Fotos (removed_paths); steht so ein Foto in einem photo_rankings-Eintrag,
    # scheitert der Scan unter echtem Postgres an der Fremdschlüsselverletzung.
    rankings: Mapped[list[PhotoRanking]] = relationship(cascade="all, delete-orphan")


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
    # Fortschritts-Watchdog: server-seitig defaultet (analog started_at), damit ein frisch
    # angelegter Lauf sofort einen last_progress_at-Wert hat und nicht bereits ab Zeile 1 als
    # Stillstand gilt. Wird an denselben Stellen wie files_found periodisch zwischen-committet
    # (worker.py::_maybe_commit_progress_checkpoint) und von worker.py::reap_stalled_runs gelesen.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # default=None (nicht 0) - unterscheidet bewusst "Enumerationsphase (Phase 1) noch nicht
    # abgeschlossen, Gesamtzahl unbekannt" von "Projekt enthält 0 Dateien". Überall mit
    # `is not None` statt truthy zu prüfen (0 ist ein gültiger, informativer Wert). Wird nach
    # Abschluss von Phase 1 (worker.py::run_project_scan) einmalig auf len(entries) gesetzt und
    # danach nicht mehr verändert.
    total_files: Mapped[int | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="scan_runs")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Rating(Base):
    """Bewertung eines Photos durch einen User.

    "Unbewertet" wird bewusst nicht als eigener Enum-Wert modelliert, sondern als Fehlen einer
    Zeile für (photo_id, user_id) - macht Toggle/Überschreiben zu einem einfachen Upsert über den
    Unique-Constraint, siehe api/ratings.py.
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
    """Ein Lauf des lokalen Scoring-Jobs, analog ScanRun. Nutzt bewusst denselben
    ScanStatus-Enum wie ScanRun statt eines eigenen ScoringStatus - beide haben identische
    Semantik (running/success/failed) für einen asynchron laufenden Worker-Job.

    photos_total/photos_processed liefern granularen Live-Fortschritt (periodisch
    zwischen-committet, siehe worker.py::run_project_scoring) - analog zu ScanRun.files_found.
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
    # (Duplikat-Verlierer + zu unscharfe Fotos, siehe worker.py::run_project_scoring, Variable
    # rejected_ids). Bleibt bei einem fehlgeschlagenen Lauf auf dem Default 0 - kein
    # irreführender Teilstand.
    suggestions_found: Mapped[int] = mapped_column(default=0, server_default="0")
    # Fortschritts-Watchdog, analog ScanRun.last_progress_at oben.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Ausschuss-Gate: projektweit, bewusst ohne user_id-Bezug wie alle Run-Tabellen - nur Rating
    # ist personenbezogen. None = Gate noch nicht bestätigt. Wird entweder über POST
    # /confirm-ausschuss-gate gesetzt oder automatisch von run_project_scoring, wenn
    # suggestions_found == 0 (kein Ausschuss zum Sichten vorhanden).
    gate_confirmed_at: Mapped[datetime | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="scoring_runs")


class PhotoScore(Base):
    """Automatisch berechnete Bewertungsgrundlage eines Fotos, 1:1 zu Photo.

    Bewusst KEINE Rating-Zeile und bewusst eine eigene Tabelle statt eines source-Felds an Rating:
    ein Vorschlag wird erst durch aktive Nutzerbestätigung über PUT /photos/{id}/rating zu einer
    echten Bewertung. `photo_id` ist Primary Key (kein separates id+Unique-Constraint-Paar wie bei
    Rating), weil es strukturell nie mehrere Zeilen pro Foto gibt.
    """

    __tablename__ = "photo_scores"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    sharpness: Mapped[float]
    exposure: Mapped[float]
    phash: Mapped[str | None] = mapped_column(default=None)
    # Selbstreferenzierender FK auf photos.id (nicht auf photo_scores.photo_id): zeigt auf das im
    # Duplikat-/Burst-Cluster behaltene FOTO, das nicht zwingend selbst schon eine PhotoScore-Zeile
    # braucht, um referenziert werden zu können.
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("photos.id"), default=None)
    cluster_key: Mapped[str | None] = mapped_column(default=None)
    # Wiederverwendet bewusst das bestehende RatingStatus-Enum: gesetzt wird darüber praktisch
    # nur REJECTED, offene Positivempfehlungen sind ohne erneute Migration möglich.
    suggested_status: Mapped[RatingStatus | None] = mapped_column(
        SQLEnum(RatingStatus, native_enum=False, length=20), default=None
    )
    computed_at: Mapped[datetime]
    # Dauerhafte manuelle Übersteuerung des sonst automatisch abgeleiteten category_key
    # (worker.py::run_criterion_scoring verwendet `score.category_override or
    # resolve_category(...)`) - überlebt damit auch künftige volle Re-Scoring-Läufe.
    #
    # Der zulässige Wertebereich ist das geschlossene Set aus categories.py::CATEGORY_REGISTRY,
    # trotzdem ein freier String ohne FK: die Whitelist-Prüfung (`is_known_category`) lebt am
    # Override-Endpunkt selbst, nicht hier. Der LESEPFAD bleibt bewusst tolerant gegenüber einem
    # Altwert außerhalb des Sets - Defense in Depth gegen einen unvollständig gelaufenen
    # Migrationsschritt.
    category_override: Mapped[str | None] = mapped_column(default=None)

    photo: Mapped[Photo] = relationship(back_populates="score", foreign_keys=[photo_id])


class PhotoCriterionScore(Base):
    """Ein normierter Kriterien-Wert für ein Foto - generische Tabelle statt weiterer fixer
    PhotoScore-Spalten, damit ein neues Kriterium nie eine Migration erzwingt (nur einen neuen
    Eintrag in criteria.py::CRITERIA_REGISTRY). `criterion_key` ist bewusst ein freier String
    (kein Enum) - genau das macht die Erweiterbarkeit aus. `value` ist immer bereits auf [0, 1]
    normiert, "höher = besser", zum Berechnungszeitpunkt und nicht erst beim Lesen.
    UniqueConstraint(photo_id, criterion_key): ein erneuter Kriterien-Lauf überschreibt (Upsert)
    den bestehenden Wert, keine Historie."""

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
    """Die VIER Teilschritte eines verketteten Klassifizierungslaufs, in genau dieser
    Reihenfolge, damit die Remote-Ergebnisse noch im selben Lauf in die Kategorieableitung
    einfließen.

    REMOTE_CATEGORIES und LANDMARK laufen nur bei angeforderter UND eingewilligter Cloud-Nutzung;
    CRITERIA und RANKING laufen immer. Getragen von CriterionScoringRun.phase, dort NULL sobald
    der Lauf beendet ist.

    RANKING (Kategorieableitung, rank_photos je Partition, Schreiben der PhotoRanking-Zeilen)
    gehört fachlich zur Kriterien-Phase, läuft aber NACH der Landmark-Phase. Ohne eigenen Namen
    müsste `phase` dort entweder auf LANDMARK stehenbleiben - die Anzeige behauptete dann
    Cloud-Aufrufe, die nicht mehr stattfinden, bei 100 % Fortschritt - oder auf CRITERIA
    zurückspringen. Ein vierter Wert macht die Abfolge monoton.

    Der Wertebereich ist eine Zeichenkette in einer VARCHAR(20)-Spalte OHNE DB-seitige
    Prüfeinschränkung (SQLEnum(..., native_enum=False), create_constraint aus) - ein weiterer Wert
    braucht deshalb keine Migration."""

    REMOTE_CATEGORIES = "remote_categories"
    CRITERIA = "criteria"
    LANDMARK = "landmark"
    RANKING = "ranking"


class CriterionScoringRun(Base):
    """Ein Lauf des Kriterien-/Rangfolgen-Jobs, analog ScoringRun/ScanRun (nutzt denselben
    ScanStatus-Enum). `scoring_run_id` bindet den Lauf explizit an den ScoringRun, dessen
    Ausschuss-Ergebnis (insb. cluster_key) er voraussetzt - Grundlage für den 409-Staleness-Guard
    bei einem zwischenzeitlichen Re-Scan/Re-Scoring.

    photos_total/photos_processed liefern granularen Live-Fortschritt (periodisch
    zwischen-committet, siehe worker.py::run_criterion_scoring). Bewusst kein Top-N-Parameter und
    kein suggestions_found: N ist beim Scoren nicht bekannt und wird erst beim Lesen angewendet -
    der Job berechnet immer den vollen Rangfolge-Pool je Partition (siehe PhotoRanking)."""

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
    # Fortschritts-Watchdog, analog ScanRun.last_progress_at oben.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Diese Zeile ist der Run-Datensatz des GESAMTEN Klassifizierungslaufs, nicht nur seiner
    # Kriterien-Phase - sie wird deshalb von worker.py::run_classification angelegt, bevor die
    # erste Phase startet, und nicht von run_criterion_scoring selbst. Ohne diesen frühen
    # Anlagezeitpunkt zeigte `last_criterion_scoring_run` während der Remote-Phase noch auf den
    # Lauf DAVOR, und die Oberfläche hätte keinen Anker für den laufenden Vorgang.
    #
    # `phase`: der gerade laufende Teilschritt; NULL heißt "läuft nicht mehr" (beendet, oder
    # Altzeile). Bewusst KEIN eigener Enum-Wert "done": der Abschluss steht bereits in `status`,
    # ein zweiter Ort dafür könnte auseinanderlaufen.
    phase: Mapped[ClassificationPhase | None] = mapped_column(
        SQLEnum(ClassificationPhase, native_enum=False, length=20), default=None
    )
    # War die Cloud-Nutzung für DIESEN Lauf angefordert (Checkbox am Auslöser)? Macht
    # nachträglich erkennbar, ob das Ergebnis überhaupt Cloud-Anreicherung enthalten kann. Sagt
    # NICHT, ob tatsächlich Cloud-Aufrufe stattgefunden haben - das Gate ist die Konjunktion mit
    # Project.cloud_vision_detection_enabled.
    cloud_requested: Mapped[bool] = mapped_column(default=False)
    # Menschenlesbare Zusammenfassung der Cloud-Probleme dieses Laufs, NULL = keine. Laufebene,
    # nicht Foto-Ebene: die Einzelfehler bleiben pro Foto in photo_cloud_vision_errors abrufbar.
    # Gesetzt zu werden heißt NICHT, dass der Lauf fehlgeschlagen ist - der lokale
    # Bewertungsanteil läuft trotzdem vollständig durch, der Lauf endet mit SUCCESS, das Ergebnis
    # ist nur nicht (vollständig) angereichert.
    cloud_error_message: Mapped[str | None] = mapped_column(default=None)

    # Die IST-Kosten-Buchführung des Landmark-Anteils dieses Laufs. Präfix `landmark_`, weil
    # diese Tabelle den GESAMTEN Klassifizierungslauf trägt und die Kriterien-Phase nichts kostet.
    #
    # Alle vier Spalten sind NULLABLE mit Python-seitigem Default `0` - exakt das
    # `ScanRun.total_files`-Idiom: `NULL` heißt "nicht erfasst" (Altzeile), `0` heißt "erfasst, es
    # sind keine Kosten angefallen". Ohne diese Unterscheidung wäre ein Altlauf nicht von einem
    # kostenlosen Lauf zu trennen; auf genau ihr beruht Befund (a) des
    # Unvollständigkeits-Hinweises der Statistikseite. Überall mit `is None` statt truthy zu
    # prüfen.
    #
    # `landmark_api_calls` zählt jeden STATTGEFUNDENEN Aufruf, auch wenn dessen `usage`-Block
    # fehlte (der Tokenbeitrag ist dann 0). Das ist zugleich der Auslöser für Befund (b): ein
    # Betrag von exakt 0 bei nachweislich abgesetzten Aufrufen ist bei Token-Preisen größer null
    # strukturell unmöglich und damit ein zuverlässiger Indikator für eine Erfassungslücke.
    #
    # `landmark_cost_usd` ist der beim Laufende EINGEFRORENE Betrag - eine spätere Preisänderung
    # verändert keinen historischen Betrag. `None` trotz erfasster Tokens heißt: das Modell war in
    # `pricing.py::MODEL_PRICING` nicht hinterlegt. `float` statt `Numeric`: Cent-Beträge, keine
    # Buchhaltung, gerundet wird erst bei der Ausgabe. Tokens und Aufrufzahl werden bewusst OHNE
    # eigenen Anzeigepfad mitgespeichert - ohne sie ist ein historischer Betrag nach einer
    # erkannten Preiskorrektur nicht mehr nachrechenbar, und der Verbrauch existiert nur im Moment
    # der API-Antwort.
    landmark_api_calls: Mapped[int | None] = mapped_column(default=0)
    landmark_input_tokens: Mapped[int | None] = mapped_column(default=0)
    landmark_output_tokens: Mapped[int | None] = mapped_column(default=0)
    landmark_cost_usd: Mapped[float | None] = mapped_column(default=0)

    # Die Modell-ID der Landmark-Phase dieses Laufs - die PREISGRUNDLAGE des eingefrorenen
    # `landmark_cost_usd` daneben. Da die Modellwahl eine Betriebseinstellung ist, sagt der
    # Provider allein nicht, womit ein Lauf gerechnet hat; ohne diese Spalte wäre ein historischer
    # Betrag nach einer Preiskorrektur nicht mehr nachrechenbar.
    #
    # Nullable mit Default `None` - `NULL` heißt "nicht erfasst" (Altzeile), NICHT "kein Modell";
    # dasselbe Idiom wie bei den vier Kostenspalten oben. Geschrieben an derselben Stelle und mit
    # demselben Commit wie der eingefrorene Betrag, aus demselben lokalen Wert.
    #
    # An der LAUF-Zeile und nicht an den `provider`-Spalten der Foto-Zeilen: eine Foto-Zeile
    # entsteht nur bei einem Treffer (_upsert_landmark_detection läuft nur bei erkanntem Namen) -
    # ein Lauf, der Aufrufe bezahlt und nichts erkennt, hinterließe dort keine Spur des Modells.
    # Bewusst ohne Lesepfad in der Oberfläche: Adressat ist der Betreiber, nicht der Anwender.
    landmark_model: Mapped[str | None] = mapped_column(default=None)

    # Die LIVE-Zähler der Landmark-Phase - je asyncio.gather-Block fortgeschrieben und
    # committet, gemeinsam mit `last_progress_at`.
    #
    # STRIKT GETRENNT von den vier Kosten-Buchführungsspalten oben: `landmark_api_calls` wird
    # EINMAL am Phasenende zusammen mit dem eingefrorenen Betrag geschrieben, und `api_calls > 0`
    # bei Betrag 0/NULL ist der Auslöser für Befund (b) des Unvollständigkeits-Hinweises der
    # Statistikseite. Ein laufend hochgezähltes `landmark_api_calls` erfüllte diese Bedingung bei
    # JEDEM laufenden Cloud-Lauf und färbte die Kostenseite mitten im Betrieb mit einem Fehlalarm
    # ein.
    #
    # Nullable mit Default `None`, dasselbe Idiom: `NULL` heißt "Phase nicht betreten" (oder
    # Altzeile), `0` heißt "betreten, nichts passiert". Gesetzt werden sie auf `0` beim BETRETEN
    # der Phase, nicht bei der Zeilenanlage.
    #
    # `landmark_photos_total` ist zugleich der MARKER, ob es diesen Teilschritt in diesem Lauf
    # überhaupt gab - die API leitet daraus ab, ob ein `cloud_phases`-Eintrag entsteht.
    # `landmark_photos_processed` zählt ABGESETZTE Aufrufe (Erfolge UND Fehlschläge), nicht
    # verwertete Antworten. Für Läufe ab der zugehörigen Migration gilt die per Test
    # festgeschriebene Invariante `landmark_photos_processed == landmark_api_calls +
    # landmark_failed_calls`.
    landmark_photos_total: Mapped[int | None] = mapped_column(default=None)
    landmark_photos_processed: Mapped[int | None] = mapped_column(default=None)
    landmark_failed_calls: Mapped[int | None] = mapped_column(default=None)

    # Die Kostenschätzung, mit der GENAU DIESER Lauf gestartet wurde - serverseitig im
    # Auslöse-Endpunkt berechnet und als Job-Argument durchgereicht. Sie muss festgehalten werden,
    # weil die Schätzung über den noch OFFENEN Kandidatenbestand rechnet, den genau dieser Lauf
    # abgearbeitet hat: unmittelbar danach schätzt derselbe Endpunkt nahe null.
    #
    # Ein BELEG, nie eine Eingabe: der Wert darf in keine spätere Rechnung, kein Budget-Gate und
    # keine Ableitung der Ist-Kosten eingehen - sonst würde eine Momentaufnahme autoritativ. Bei
    # `use_cloud=false` steht hier `NULL`, nicht `0.0`: ein Lauf ohne Cloud hat keine
    # Kostenschätzung, und `0.0` wäre eine Aussage, die niemand getroffen hat (dieselbe "null
    # heißt unbekannt, nie kostenlos"-Linie wie bei `price_per_image_usd`).
    estimated_cost_usd: Mapped[float | None] = mapped_column(default=None)

    # Der Remote-Lauf, der zu DIESEM Klassifizierungslauf gehört - gesetzt von
    # run_classification, BEVOR Phase 1 startet (die Oberfläche braucht den Anker schon während
    # der Remote-Phase). `NULL` = dieser Lauf hatte keine Remote-Phase, oder Altzeile.
    #
    # Der explizite Fremdschlüssel ist Pflicht, keine Bequemlichkeit: Die Heuristik "die jüngste
    # Remote-Zeile des Projekts" ist nachweislich falsch, sobald zwei Läufe hintereinander
    # unterschiedlich viel Cloud nutzen - ein Lauf ohne Cloud-Phase erbte die Zahlen des Laufs
    # davor und zeigte fremde Kosten als seine eigenen. Eine Bilanz nennt einen GELDBETRAG.
    #
    # Die Löschreihenfolge in project_deletion.py muss criterion_scoring_runs VOR
    # remote_category_classification_runs halten; ein Test hält das fest.
    remote_category_classification_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_category_classification_runs.id"), default=None
    )

    project: Mapped[Project] = relationship(back_populates="criterion_scoring_runs")
    # PhotoRanking hängt an ZWEI Elternteilen. Ohne diese Kaskade bleiben beim Löschen eines
    # Kuratierungslaufs verwaiste photo_rankings-Zeilen zurück.
    rankings: Mapped[list[PhotoRanking]] = relationship(cascade="all, delete-orphan")


class PhotoRanking(Base):
    """Der volle, sortierte Kandidatenpool einer Partition (cluster_key x category_key) für einen
    CriterionScoringRun - NICHT nur die Top-N. Macht "zeig die besten X pro Kategorie" zu einer
    reinen Lese-Query (GET /projects/{id}/photos?top_n_per_category=N) statt eines Job-Parameters,
    und Backfill zu einem Nebeneffekt eines erneuten Abrufs nach einer Rating-Änderung, ohne dass
    irgendein Server-Code aktiv "nachrückt". `category_key` ist wie `criterion_key` ein freier
    String, `rank_position` ist 1-basiert innerhalb der Partition.

    MEHRFACHZUGEHÖRIGKEIT: ein Foto hat pro Lauf EINE ZEILE JE KATEGORIE, zu der es gehört - genau
    eine davon trägt `is_primary=True`. Daher der Unique-Constraint über
    `(run, photo, category_key)`: ein Foto steht pro Lauf höchstens einmal JE KATEGORIE, nicht
    höchstens einmal überhaupt.

    `rank_score` ist über alle Zugehörigkeitszeilen eines Fotos IDENTISCH (der ungedämpfte
    gewichtete Kriterien-Mittelwert). `rank_position` ist es NICHT und innerhalb einer Partition
    auch nicht monoton in `rank_score` - die Modellkonfidenz zum Schlüssel DIESER Partition dämpft
    den Sortierschlüssel (ranking.py::confidence_ordering_score). Gewollt, kein Defekt.

    Die zweite Invariante - GENAU EINE Zeile mit `is_primary=True` je (Lauf, Foto) - ist bewusst
    nicht als Datenbankbedingung ausdrückbar und wird stattdessen im Schreibpfad gehalten
    (worker.py::run_criterion_scoring/reassign_photo_category, dort mit `with_for_update()` gegen
    überlappende Overrides) und in den Tests nach jeder Schreiboperation geprüft."""

    __tablename__ = "photo_rankings"
    __table_args__ = (
        UniqueConstraint(
            "criterion_scoring_run_id",
            "photo_id",
            "category_key",
            name="uq_photo_ranking_run_photo_category",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    criterion_scoring_run_id: Mapped[int] = mapped_column(ForeignKey("criterion_scoring_runs.id"))
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))
    cluster_key: Mapped[str]
    category_key: Mapped[str]
    rank_score: Mapped[float]
    rank_position: Mapped[int]
    # BEWUSST OHNE Default, weder Python- noch Server-seitig: ein Schreibpfad, der die Spalte
    # vergisst, soll auffallen statt still eine zweite Hauptkategorie zu erzeugen. Die Spalte
    # trägt genau die Invariante, die sonst niemand hält.
    is_primary: Mapped[bool]


class PhotoLandmarkDetection(Base):
    """Der vom Vision-LLM identifizierte Sehenswürdigkeit-Name, 1:1 zu Photo, analog PhotoScore.

    `photo_id` ist Primary Key (kein separates id+Unique-Constraint-Paar wie bei
    PhotoCriterionScore), weil dies eine optionale Detail-Zeile pro Foto ist, kein
    Mehrfach-Kriterien-Fact. Nur angelegt, wenn tatsächlich ein Name identifiziert wurde (kein
    Platzhalter-"unbekannt"). `confidence` dupliziert bewusst den zugehörigen
    PhotoCriterionScore(criterion_key="landmark").value - hält diese Tabelle für eine Abfrage ohne
    Join selbsttragend, beide Werte stammen atomar aus derselben API-Antwort.

    `provider` hält fest, welcher Cloud-Provider diese Zeile erzeugt hat - sonst würde die
    Herkunft bereits gescorter Fotos bei einem Umschalten von Settings.landmark_provider
    stillschweigend unklar. Atomar im selben Upsert wie name/confidence gesetzt
    (worker.py::_upsert_landmark_detection). Der Default "anthropic" deckt Zeilen aus der Zeit vor
    dieser Spalte ab; worker.py setzt den Wert im produktiven Pfad trotzdem immer explizit."""

    __tablename__ = "photo_landmark_detections"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    name: Mapped[str]
    confidence: Mapped[float]
    computed_at: Mapped[datetime]
    provider: Mapped[str] = mapped_column(default="anthropic")

    photo: Mapped[Photo] = relationship(back_populates="landmark_detection")


class FineLabel(Base):
    """Kanonische Registry der frei formulierten Feinlabels.

    Die Einträge bilden keine Kategorien (das tut das feste Set in categories.py), sondern dienen
    der Feinlabel-Häufigkeitsauswertung (`GET /projects/{id}/fine-labels`) - dort macht die
    Kanonisierung über Embeddings sie erst belastbar ("Hund"/"Hunde"/"dog" als ein Eintrag).

    Bewusst PROJEKTÜBERGREIFEND (kein project_id-Bezug): reine Vokabular-Einträge ("hund" ist kein
    personenbezogenes Datum), keine Fotoinhalte. Eine projektgebundene Registry würde identische
    Label wiederholt neu anlegen und die Cluster-Qualität verschlechtern - für dieses
    Zwei-Personen-Familienprojekt ohne Mandantentrennung eine bewusste Vereinfachung. Die
    HÄUFIGKEITSABFRAGE ist deshalb zwingend über `photo_fine_labels -> photos.project_id` zu
    skopieren: ein globales SELECT auf diese Tabelle würde Label-Häufigkeiten ANDERER Projekte
    ausliefern.

    `canonical_key` ist ein URL-/Key-sicherer Slug (remote_classification.py::_slugify),
    `display_name` der zuerst gesehene Roh-Label-Text in Originalschreibweise (reine Anzeigehilfe,
    keine kuratierte Übersetzung). `embedding` ist der 384-dimensionale Text-Embedding-Vektor
    (label_embedding.py) als JSON-Liste von float - kein pgvector/Vektor-Index nötig, die Menge
    ist klein und wächst langsam, ein voller Scan pro Auflösung ist unproblematisch.
    """

    __tablename__ = "fine_labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_key: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(SQLJSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    photo_fine_labels: Mapped[list[PhotoFineLabel]] = relationship(back_populates="fine_label")


class PhotoFineLabel(Base):
    """Ein vom Vision-LLM frei formuliertes, auf einen kanonischen Eintrag aufgelöstes Feinlabel
    - 1:N zu Photo, 0 bis MAX_FINE_LABELS_PER_PHOTO Zeilen pro Foto. 0 Zeilen sind ausdrücklich
    zulässig: der Prompt erzwingt kein Feinlabel, die Pflichtaussage je Foto ist die Kategorie
    (PhotoCategoryClassification), nicht das Label.

    `raw_label` ist der - bereits zeichensanierte (cloud_vision.py::_sanitize_label_text) - vom
    Vision-LLM gelieferte Text, als Audit-/Debug-Spur, welche Formulierung auf welchen
    canonical_key gemappt wurde.

    UniqueConstraint(photo_id, fine_label_id): verhindert zwei Zeilen für dasselbe
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
    """Das Ergebnis der Remote-Kategorie-Klassifizierung eines Fotos - 1:1 zu Photo, `photo_id`
    ist Primary Key (strukturell nie mehrere Zeilen pro Foto, gleiche Begründung wie bei
    PhotoScore/PhotoLandmarkDetection).

    `category_key` ist das bereits über `categories.py::resolve_category` aufgelöste Ergebnis der
    remote genannten Kandidaten - also immer ein Wert aus dem festen Set, nie ein Rohwert des
    Modells. `detected_categories` hält die VALIDIERTE Kandidatenliste (ausschließlich bekannte
    Set-Keys, unbekannte Rohwerte sind bereits verworfen) als JSON-Liste; sie wird über
    `PhotoOut.category_candidates` ausgeliefert. SICHERHEIT: hier landet NIE die Rohliste des
    Modells - sonst wanderte unvalidierter Fremdtext über einen zweiten Kanal in API-Antwort und
    UI.

    Die PRÄSENZ dieser Zeile ist zugleich das Erfolgssignal der Remote-Phase (Skip-Kriterium in
    worker.py::select_remote_category_candidates und Statusableitung in
    api/photos.py::_cloud_vision_status_out) - sie entsteht auch dann, wenn `category_key`
    `nicht_erkannt` lautet (kein "nichts gefunden"-Sonderfall)."""

    __tablename__ = "photo_category_classifications"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    category_key: Mapped[str]
    detected_categories: Mapped[list[str]] = mapped_column(SQLJSON)
    # Die Selbsteinschätzung des Modells je Kandidat als ABBILDUNG `category_key -> Wert in
    # [0, 1]`, ausschließlich mit Schlüsseln aus `detected_categories` (Invariante, am Parser
    # erzwungen). Kein positionsparalleles Array und keine Paarliste - der Wert hängt am Schlüssel
    # und überlebt jede Umsortierung.
    #
    # `category_confidence` ist die Konfidenz zur AUFGELÖSTEN Kategorie DIESER Zeile, also
    # `detected_category_confidences.get(category_key)`. Bewusst redundant: die
    # Statistik-Aggregation muss in SQL laufen (ein `AVG` über einen aus JSON extrahierten Wert
    # ist in SQLite und PostgreSQL unterschiedlich zu schreiben, und alle Klassifizierungszeilen
    # eines Projekts nach Python zu laden verträgt sich nicht mit der Größenannahme "mehrere
    # tausend Fotos"). Tragbar, weil es genau EINE schreibende Stelle gibt
    # (worker.py::run_remote_category_classification) und beide Werte dort aus derselben Quelle in
    # derselben Transaktion entstehen; die Invariante wird getestet.
    #
    # BEIDE nullable, ohne server_default und ohne Backfill - das Muster der Kostenspalten:
    #     NULL = "nicht erhoben" (Altzeile, oder Modell ohne Angabe)
    #     0.0  = "das Modell war sich zu 0 % sicher"
    # Ein `{}` in `detected_category_confidences` heißt wiederum "erhoben, aber keine brauchbare
    # Zahl geliefert". Überall mit `is None` statt truthy zu prüfen.
    #
    # KEIN Codepfad, der eine Kategorie BESTIMMT, liest diese beiden Spalten - sie werden
    # ausschließlich von der API-Ausgabe, der Statistik-Aggregation und dem Frontend gelesen.
    detected_category_confidences: Mapped[dict[str, float] | None] = mapped_column(
        SQLJSON, default=None
    )
    category_confidence: Mapped[float | None] = mapped_column(default=None)
    provider: Mapped[str]
    computed_at: Mapped[datetime]

    photo: Mapped[Photo] = relationship(back_populates="category_classification")


class RemoteCategoryClassificationRun(Base):
    """Ein Lauf des Remote-Kategorie-Klassifizierungs-Jobs - Run-Tracking analog
    CriterionScoringRun/ScoringRun/ScanRun, aber bewusst OHNE scoring_run_id-FK: dieser Job
    schreibt ausschließlich in photo_category_classifications/photo_fine_labels/fine_labels,
    berührt weder cluster_key noch PhotoRanking direkt - kein 409-Staleness-Guard, kein
    Ausschuss-Gate-Erfordernis (anders als run_criterion_scoring)."""

    __tablename__ = "remote_category_classification_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    photos_total: Mapped[int] = mapped_column(default=0)
    photos_processed: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(default=None)
    # Fortschritts-Watchdog, analog ScanRun.last_progress_at.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Die IST-Kosten-Buchführung des Remote-Kategorie-Anteils dieses Laufs. Kein Präfix - dieser
    # Lauf hat genau einen Zweck. Nullable-Semantik, Zählweise von `api_calls`, das Einfrieren von
    # `cost_usd` und die Begründung für das Mitspeichern von Tokens/Aufrufzahl sind wortgleich die
    # der vier `landmark_*`-Kostenspalten an CriterionScoringRun.
    api_calls: Mapped[int | None] = mapped_column(default=0)
    input_tokens: Mapped[int | None] = mapped_column(default=0)
    output_tokens: Mapped[int | None] = mapped_column(default=0)
    cost_usd: Mapped[float | None] = mapped_column(default=0)

    # Die Modell-ID dieses Laufs, Gegenstück zu `CriterionScoringRun.landmark_model` -
    # Begründung, Nullable-Semantik ("NULL = nicht erfasst") und Schreibzeitpunkt wortgleich dort.
    model: Mapped[str | None] = mapped_column(default=None)

    # Der LIVE-Zähler der fehlgeschlagenen Einzelaufrufe dieser Phase - Gegenstück zu
    # `CriterionScoringRun.landmark_failed_calls`, Begründung und Nullable-Semantik wortgleich
    # dort. Geschrieben am Block-Commit-Punkt (`photos_processed`/`last_progress_at`), NICHT im
    # `finally`: die Zahl muss WÄHREND des Laufs stimmen.
    failed_calls: Mapped[int | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="remote_category_classification_runs")


class CloudVisionPhase(enum.StrEnum):
    """Die beiden unabhängigen Cloud-Vision-Läufe, aus denen pro Foto einer von sechs Zuständen
    abgeleitet wird."""

    LANDMARK = "landmark"
    REMOTE_CATEGORY = "remote_category"


class PhotoCloudVisionError(Base):
    """Der letzte bekannte Fehlschlag eines Cloud-Vision-Laufs für ein Foto - bewusst KEIN
    Verlauf: ein erneuter Fehlschlag überschreibt (Upsert, worker.py::_record_cloud_vision_error)
    die bestehende Zeile, ein erfolgreicher Retry LÖSCHT sie
    (worker.py::_clear_cloud_vision_error). Composite PK (photo_id, phase) statt eines separaten
    id+UniqueConstraint-Paars: es gibt strukturell höchstens eine sinnvolle "letzter
    Fehlschlag"-Zeile je Foto x CloudVisionPhase.

    `error_type`/`error_message` sind identischer Inhalt wie der WARNING-Log-Eintrag
    (`type(exc).__name__`, `str(exc)`) - an der jeweiligen worker.py-Call-Site EINMAL berechnet,
    an beide Senken (Logger, hier) weitergereicht, keine zweite Auswertung. `error_message` wird
    beim Schreiben auf worker.py::_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH (500 Zeichen)
    gekappt - defensiver Schutz gegen eine entartete Fehlermeldung. Die eigentliche Absicherung
    ist und bleibt die Sanitisierung von `str(exc)` (keine Secrets, keine Rohdaten); die Kappung
    ist nur eine Storage-/Degenerationsgrenze.

    `attempted_at`: Zeitpunkt des letzten Fehlschlags - bewusst keine weiteren Metadaten, kein
    HTTP-Statuscode und kein Provider-Feld."""

    __tablename__ = "photo_cloud_vision_errors"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    phase: Mapped[CloudVisionPhase] = mapped_column(
        SQLEnum(CloudVisionPhase, native_enum=False, length=20), primary_key=True
    )
    error_type: Mapped[str]
    error_message: Mapped[str]
    attempted_at: Mapped[datetime]

    photo: Mapped[Photo] = relationship(back_populates="cloud_vision_errors")
