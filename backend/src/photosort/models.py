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
    # Projektweiter Einwilligungs-Schalter für produktive Cloud-Vision-Datenflüsse: der EINE
    # Schalter für beide Cloud-Anteile (landmark und Remote-Kategorie-Klassifizierung), nie ein
    # zweiter daneben. Default AUS. Projektweit, ohne user_id-Bezug.
    cloud_vision_detection_enabled: Mapped[bool] = mapped_column(default=False)
    # Zeitstempel, gesetzt beim Aktivieren, auf NULL zurückgesetzt beim Deaktivieren - kein
    # voller Audit-Log.
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
    # Kein Cascade-Ziel für fine_labels selbst (projektübergreifend): DELETE /projects/{id}
    # löscht über die photos-Kaskade oben die projekteigenen photo_fine_labels-Zeilen, lässt
    # einen weiterhin von einem ANDEREN Projekt referenzierten fine_labels-Eintrag unangetastet.
    remote_category_classification_runs: Mapped[list[RemoteCategoryClassificationRun]] = (
        relationship(back_populates="project", cascade="all, delete-orphan")
    )
    cameras: Mapped[list[ProjectCamera]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
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


class ProjectCamera(Base):
    """Eine Kamera, wie sie in GENAU DIESEM Projekt vorkommt, samt ihrem Zeitversatz.

    PROJEKTEIGEN, nicht projektuebergreifend (ADR 0088, Punkt 2): "der Versatz gilt nur in diesem
    Projekt" ist damit STRUKTURELL wahr - es gibt keine Zeile, die zwei Projekte sehen koennten,
    und kein Prädikat, das in jeder Abfrage ausgeschrieben stehen muesste. Dieselbe Kamera in zwei
    Projekten sind zwei Zeilen mit getrennten Versaetzen.

    Die Zeilen entstehen ausschliesslich beim Scan aus den Fotos selbst; der Nutzer traegt keine
    Kamera ein. Identitaet ist Hersteller UND Modell, zeichengenau und OHNE Seriennummer - zwei
    baugleiche Gehaeuse im selben Projekt sind eine Kamera und teilen einen Versatz.

    `offset_minutes` ist eine vorzeichenbehaftete Ganzzahl Minuten, kein `timedelta` und keine
    Zeitzonenzugehoerigkeit: abgebildet wird eine feste Zeitspanne, keine Regel mit Sommer-/
    Winterzeit. Ober- und Untergrenze werden am Endpunkt durchgesetzt
    (`cameras.py::MAX_TIME_OFFSET_MINUTES`), nicht hier.

    KEHRSEITE, die der eine Schreibpfad haelt und ein Test prueft: `Photo.camera_id` muss auf eine
    Zeile DESSELBEN Projekts zeigen - der Scan loest die Kamera innerhalb des Projekts des Fotos
    auf."""

    __tablename__ = "project_cameras"
    __table_args__ = (
        UniqueConstraint("project_id", "make", "model", name="uq_project_camera_make_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    # Beide bereits normalisiert (cameras.py::camera_identity): getrimmt, innere Leerraumfolgen
    # zusammengezogen, ohne Zeichen der Unicode-Kategorien Cc/Cf. Ein LEERER String heisst "dieses
    # Feld war nicht vorhanden"; beide leer gibt es nicht - dann bleibt `Photo.camera_id` NULL.
    make: Mapped[str]
    model: Mapped[str]
    offset_minutes: Mapped[int] = mapped_column(default=0, server_default="0")

    project: Mapped[Project] = relationship(back_populates="cameras")


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
    # DIE KORRIGIERTE ZEIT - "die Zeit, mit der die Anwendung arbeitet" (ADR 0088, Punkt 1). Der
    # Name und die Rolle sind unveraendert, der INHALT hat sich mit Spec 0426 gedreht: hier steht
    # seither die um den Kamera-Versatz verschobene Zeit, nicht mehr die aufgezeichnete.
    #
    # INVARIANTE, im Schreibpfad gehalten: `taken_at == taken_at_original + offset_minutes` der
    # Kamera dieses Fotos in genau diesem Projekt; ohne Kamera oder bei `offset_minutes = 0` sind
    # beide Werte gleich. Es gibt GENAU ZWEI Schreibstellen - `worker.py::_process_scan_block` und
    # `api/cameras.py` -, beide ueber die eine reine Funktion `cameras.py::shifted`. Eine dritte
    # gibt es nicht; ein struktureller Waechtertest in test_models.py haelt das fest, weil eine
    # dritte Schreibstelle keinen Verhaltenstest roeten wuerde, solange sie den Wert irgendwie
    # setzt.
    #
    # Deshalb aendert sich an KEINER Lesestelle etwas: `assign_clusters`, `build_events`,
    # `infer_locations`, die SQL-Sortierung der Fotoliste und `min`/`max` der Statistik rechnen
    # ohne eine Zeile Aenderung mit dem korrigierten Wert. Gruppierung, Reihenfolge und
    # Ortsuebernahme haben KEINE eigene Korrekturlogik.
    taken_at: Mapped[datetime]
    # Die AUFGEZEICHNETE Zeit: EXIF `DateTimeOriginal`, sonst der Rueckfall auf `last_modified`.
    #
    # NOT NULL und BEWUSST OHNE jeden Default, weder Python- noch server-seitig: dies ist die
    # einzige Kopie der aufgezeichneten Zeit, und ein unveraendertes, bereits geprueftes Foto wird
    # nie wieder aus EXIF gelesen - ein Schreibpfad, der die Spalte vergisst, soll LAUT an der
    # NOT-NULL-Bedingung scheitern statt still einen falschen Wert zu erben. Geschrieben wird
    # ausschliesslich aus der QUELLE, NIE aus `taken_at`, und nach dem Setzen nie verschoben.
    taken_at_original: Mapped[datetime]
    # Die Kamera dieses Fotos innerhalb DIESES Projekts. `NULL` heisst "Kamera nicht bestimmbar"
    # und ist ein regulaerer Zustand ohne Versatz, kein Fehler: die wirksame Zeit ist dann gleich
    # der aufgezeichneten, das Foto erscheint in keiner Kameraliste, und jeder Lesepfad antwortet
    # fuer es fehlerfrei.
    #
    # Der Fremdschluessel ist EXPLIZIT BENANNT: ein per `batch_alter_table` unbenannt angelegter
    # Fremdschluessel ist im `downgrade()` unter SQLite nicht droppbar, und `Base.metadata` traegt
    # keine `naming_convention`, aus der ein Name entstuende.
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_cameras.id", name="fk_photos_camera_id"), default=None
    )
    # Der Merker "EXIF dieses Fotos wurde auf die Kamera-Angabe geprueft". Ein Foto ohne ihn wird
    # beim naechsten Scan trotz unveraenderten Etags erneut gelesen - nur das EXIF-Fenster, ohne
    # Voll-Download und ohne Thumbnail-Neuerzeugung. Das ist die einmalige Nachhol-Runde fuer
    # Bestandsfotos; ohne sie bliebe die Kameraliste in bestehenden Projekten leer.
    #
    # Gesetzt wird er AUCH OHNE FUND (die Datei nennt keine Kamera) - sonst laese jeder weitere
    # Scan den gesamten Bestand erneut.
    #
    # `server_default` in Migration UND Modell, damit beide dieselbe DDL lesen: fehlt die
    # Modellseite, bleibt alles gruen und der erste Schreibpfad, der die Spalte nicht nennt,
    # bricht produktiv.
    camera_probed: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Dezimalgrad aus dem EXIF-GPSInfo-IFD (opencloud/exif.py::extract_gps). `None` heißt "kein
    # Ort bekannt" - es gibt NIE eine halbe Koordinate: scheitert eine Komponente, sind beide
    # Felder `None` (Paar-Invariante von extract_gps). Volle EXIF-Präzision, keine Rundung beim
    # Speichern; die Anzeigerundung auf zwei Nachkommastellen liegt allein in
    # events.py::_rounded (`_EVENT_PLACE_COORDINATE_DIGITS`) und trifft ausschließlich
    # `events.place_lat`/`place_lon`, nie diese Spalten hier.
    #
    # KEIN server_default und kein Backfill: `0.0` ist eine gültige Koordinate, kein
    # Abwesenheitswert. Bereits gescannte Fotos bleiben ohne Koordinate, bis sich die Datei auf
    # OpenCloud ändert.
    gps_lat: Mapped[float | None] = mapped_column(default=None)
    gps_lon: Mapped[float | None] = mapped_column(default=None)
    last_modified: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    project: Mapped[Project] = relationship(back_populates="photos")
    # Ohne `back_populates`: die Gegenrichtung (alle Fotos einer Kamera) wird nirgends gebraucht,
    # und eine Sammlung an `ProjectCamera` verleitete dazu, die Fotoanzahl im Python zu zaehlen
    # statt in der einen `group_by`-Abfrage der Kameraliste.
    camera: Mapped[ProjectCamera | None] = relationship()
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
    # ZUSATZINFORMATION am Foto und bilden keine Kategorie.
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
    # Die Foto-Seite derselben Kaskade wie bei CriterionScoringRun.rankings. Ohne sie scheitert
    # der Re-Scan unter echtem Postgres an einer Fremdschlüsselverletzung, sobald
    # worker.py::run_project_scan ein auf OpenCloud verschwundenes Foto löscht, das noch in einem
    # photo_rankings-Eintrag steht.
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
    # Fortschritts-Watchdog: server-seitig defaultet, sonst gälte ein frisch angelegter Lauf
    # sofort als Stillstand. Periodisch zwischen-committet
    # (worker.py::_maybe_commit_progress_checkpoint), gelesen von worker.py::reap_stalled_runs.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # default=None (nicht 0) - unterscheidet "Enumerationsphase noch nicht abgeschlossen,
    # Gesamtzahl unbekannt" von "Projekt enthält 0 Dateien". Überall mit `is not None` statt
    # truthy zu prüfen. Wird nach Abschluss von Phase 1 (worker.py::run_project_scan) einmalig
    # gesetzt und danach nicht mehr verändert.
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

    "Unbewertet" ist kein Enum-Wert, sondern das Fehlen einer Zeile für (photo_id, user_id);
    Toggle und Überschreiben laufen als Upsert über den Unique-Constraint (api/ratings.py).
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
    """Ein Lauf des lokalen Scoring-Jobs, analog ScanRun.

    photos_total/photos_processed liefern granularen Live-Fortschritt, periodisch
    zwischen-committet (worker.py::run_project_scoring).
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
    # (Duplikat-Verlierer und zu unscharfe Fotos). Bleibt bei einem fehlgeschlagenen Lauf auf
    # dem Default 0 - kein irreführender Teilstand.
    suggestions_found: Mapped[int] = mapped_column(default=0, server_default="0")
    # Fortschritts-Watchdog, analog ScanRun.last_progress_at oben.
    last_progress_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Ausschuss-Gate: projektweit, ohne user_id-Bezug wie alle Run-Tabellen - nur Rating ist
    # personenbezogen. None = Gate noch nicht bestätigt. Gesetzt über POST
    # /confirm-ausschuss-gate oder automatisch von run_project_scoring, wenn
    # suggestions_found == 0.
    gate_confirmed_at: Mapped[datetime | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="scoring_runs")


class PhotoScore(Base):
    """Automatisch berechnete Bewertungsgrundlage eines Fotos, 1:1 zu Photo.

    Nie eine Rating-Zeile und nie ein source-Feld an Rating: ein Vorschlag wird erst durch aktive
    Nutzerbestätigung über PUT /photos/{id}/rating zu einer echten Bewertung. `photo_id` ist
    Primary Key, weil es strukturell nie mehrere Zeilen pro Foto gibt.
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
    # Gesetzt wird praktisch nur REJECTED; Positivempfehlungen sind über dasselbe Enum ohne
    # erneute Migration möglich.
    suggested_status: Mapped[RatingStatus | None] = mapped_column(
        SQLEnum(RatingStatus, native_enum=False, length=20), default=None
    )
    computed_at: Mapped[datetime]
    # Dauerhafte manuelle Übersteuerung des sonst automatisch abgeleiteten category_key
    # (worker.py::run_criterion_scoring) - überlebt auch künftige volle Re-Scoring-Läufe.
    #
    # Der zulässige Wertebereich ist das geschlossene Set aus categories.py::CATEGORY_REGISTRY,
    # trotzdem ein freier String ohne FK: die Whitelist-Prüfung (`is_known_category`) lebt am
    # Override-Endpunkt, nicht hier. Der LESEPFAD bleibt tolerant gegenüber einem Altwert
    # außerhalb des Sets - Defense in Depth gegen einen unvollständig gelaufenen
    # Migrationsschritt.
    category_override: Mapped[str | None] = mapped_column(default=None)

    photo: Mapped[Photo] = relationship(back_populates="score", foreign_keys=[photo_id])


class PhotoCriterionScore(Base):
    """Ein normierter Kriterien-Wert für ein Foto - generische Tabelle statt weiterer fixer
    PhotoScore-Spalten, damit ein neues Kriterium nie eine Migration erzwingt, sondern nur einen
    neuen Eintrag in criteria.py::CRITERIA_REGISTRY. `criterion_key` ist ein freier String, kein
    Enum. `value` ist immer bereits auf [0, 1] normiert, "höher = besser", zum
    Berechnungszeitpunkt und nicht erst beim Lesen. UniqueConstraint(photo_id, criterion_key):
    ein erneuter Kriterien-Lauf überschreibt den bestehenden Wert, keine Historie."""

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
    gehört fachlich zur Kriterien-Phase, läuft aber NACH der Landmark-Phase und trägt deshalb
    einen eigenen Wert: die Abfolge bleibt monoton, `phase` springt nie zurück und behauptet nie
    Cloud-Aufrufe, die nicht mehr stattfinden.

    Der Wertebereich ist eine Zeichenkette in einer VARCHAR(20)-Spalte OHNE DB-seitige
    Prüfeinschränkung (SQLEnum(..., native_enum=False), create_constraint aus) - ein weiterer Wert
    braucht deshalb keine Migration."""

    REMOTE_CATEGORIES = "remote_categories"
    CRITERIA = "criteria"
    LANDMARK = "landmark"
    RANKING = "ranking"


class CriterionScoringRun(Base):
    """Ein Lauf des Kriterien-/Rangfolgen-Jobs, analog ScoringRun/ScanRun. `scoring_run_id`
    bindet den Lauf explizit an den ScoringRun, dessen Ausschuss-Ergebnis (insb. cluster_key) er
    voraussetzt - Grundlage für den 409-Staleness-Guard bei einem zwischenzeitlichen
    Re-Scan/Re-Scoring.

    photos_total/photos_processed liefern granularen Live-Fortschritt, periodisch
    zwischen-committet (worker.py::run_criterion_scoring). Kein Top-N-Parameter und kein
    suggestions_found: N ist beim Scoren nicht bekannt und wird erst beim Lesen angewendet - der
    Job berechnet immer den vollen Rangfolge-Pool je Partition."""

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
    # Kriterien-Phase: angelegt von worker.py::run_classification, bevor die erste Phase startet,
    # nie von run_criterion_scoring selbst. Sonst zeigte `last_criterion_scoring_run` während der
    # Remote-Phase noch auf den Lauf DAVOR.
    #
    # `phase`: der gerade laufende Teilschritt; NULL heißt "läuft nicht mehr" (beendet, oder
    # Altzeile). KEIN eigener Enum-Wert "done" - der Abschluss steht in `status`, ein zweiter Ort
    # dafür liefe auseinander.
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
    # Alle vier Spalten sind NULLABLE mit Python-seitigem Default `0`, dasselbe Idiom wie
    # `ScanRun.total_files`: `NULL` heißt "nicht erfasst" (Altzeile), `0` heißt "erfasst, es sind
    # keine Kosten angefallen". Überall mit `is None` statt truthy zu prüfen. Auf dieser
    # Unterscheidung beruht Befund (a) des Unvollständigkeits-Hinweises der Statistikseite.
    #
    # `landmark_api_calls` zählt jeden STATTGEFUNDENEN Aufruf, auch wenn dessen `usage`-Block
    # fehlte (der Tokenbeitrag ist dann 0). Ein Betrag von exakt 0 bei abgesetzten Aufrufen ist
    # deshalb Befund (b): eine Erfassungslücke.
    #
    # `landmark_cost_usd` ist der beim Laufende EINGEFRORENE Betrag - eine spätere Preisänderung
    # verändert keinen historischen Betrag. `None` trotz erfasster Tokens heißt: das Modell war in
    # `pricing.py::MODEL_PRICING` nicht hinterlegt. `float`, nicht `Numeric`; gerundet wird erst
    # bei der Ausgabe. Tokens und Aufrufzahl werden OHNE eigenen Anzeigepfad mitgespeichert - ohne
    # sie ist ein historischer Betrag nach einer Preiskorrektur nicht mehr nachrechenbar, und der
    # Verbrauch existiert nur im Moment der API-Antwort.
    landmark_api_calls: Mapped[int | None] = mapped_column(default=0)
    landmark_input_tokens: Mapped[int | None] = mapped_column(default=0)
    landmark_output_tokens: Mapped[int | None] = mapped_column(default=0)
    landmark_cost_usd: Mapped[float | None] = mapped_column(default=0)

    # Die Modell-ID der Landmark-Phase dieses Laufs - die PREISGRUNDLAGE des eingefrorenen
    # `landmark_cost_usd` daneben. Der Provider allein sagt nicht, womit ein Lauf gerechnet hat.
    #
    # Nullable mit Default `None` - `NULL` heißt "nicht erfasst" (Altzeile), NICHT "kein Modell";
    # dasselbe Idiom wie bei den vier Kostenspalten oben. Geschrieben an derselben Stelle und mit
    # demselben Commit wie der eingefrorene Betrag, aus demselben lokalen Wert.
    #
    # An der LAUF-Zeile, nie an den `provider`-Spalten der Foto-Zeilen: eine Foto-Zeile entsteht
    # nur bei einem Treffer, ein Lauf ohne Erkennung hinterließe dort keine Spur des Modells.
    # Ohne Lesepfad in der Oberfläche - Adressat ist der Betreiber, nicht der Anwender.
    landmark_model: Mapped[str | None] = mapped_column(default=None)

    # Die LIVE-Zähler der Landmark-Phase - je asyncio.gather-Block fortgeschrieben und
    # committet, gemeinsam mit `last_progress_at`.
    #
    # STRIKT GETRENNT von den vier Kosten-Buchführungsspalten oben: `landmark_api_calls` wird
    # EINMAL am Phasenende zusammen mit dem eingefrorenen Betrag geschrieben und nie laufend
    # hochgezählt - sonst erfüllte jeder laufende Cloud-Lauf die Bedingung von Befund (b) und
    # färbte die Kostenseite mitten im Betrieb mit einem Fehlalarm ein.
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
    # Auslöse-Endpunkt berechnet und als Job-Argument durchgereicht. Festgehalten, weil die
    # Schätzung über den noch OFFENEN Kandidatenbestand rechnet: unmittelbar nach dem Lauf
    # schätzt derselbe Endpunkt nahe null.
    #
    # Ein BELEG, nie eine Eingabe: der Wert darf in keine spätere Rechnung, kein Budget-Gate und
    # keine Ableitung der Ist-Kosten eingehen - sonst würde eine Momentaufnahme autoritativ. Bei
    # `use_cloud=false` steht hier `NULL`, nicht `0.0`: ein Lauf ohne Cloud hat keine
    # Kostenschätzung, und `0.0` wäre eine Aussage, die niemand getroffen hat.
    estimated_cost_usd: Mapped[float | None] = mapped_column(default=None)

    # Der Remote-Lauf, der zu DIESEM Klassifizierungslauf gehört - gesetzt von
    # run_classification, BEVOR Phase 1 startet (die Oberfläche braucht den Anker schon während
    # der Remote-Phase). `NULL` = dieser Lauf hatte keine Remote-Phase, oder Altzeile.
    #
    # Nie über die Heuristik "die jüngste Remote-Zeile des Projekts" auflösen: ein Lauf ohne
    # Cloud-Phase erbte damit die Zahlen des Laufs davor und zeigte fremde Kosten als seine
    # eigenen.
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


class Event(Base):
    """Ein Abschnitt der Reise: eine zusammenhängende Folge von Kandidatenfotos EINES
    CriterionScoringRun, mit Anfang, Ende, Ort und ggf. Namen.

    Die Events eines Laufs sind chronologisch geordnet und überschneidungsfrei; `position` läuft
    lückenlos von 1 bis n. Träger ist der LAUF, nicht das Projekt - ein Projekt hat mehrere
    Lauf-Artefakte nebeneinander.

    Persistiert und nicht abgeleitet, weil Nummer und Zeitspanne Bestandteil des NAMENS sind und
    deshalb unabhängig davon feststehen müssen, welche Fotos eine Antwort gerade enthält. Ein
    Event ist ein Lauf-Artefakt wie PhotoRanking, kein reiner Funktionswert über `photos`; der
    Ortswert eines einzelnen Fotos bleibt weiterhin unpersistiert.

    FELDKOMBINATION (geprüfte Invariante, events.py::_place_of ist die einzige Schreibstelle):
    `place_kind='landmark'` ⇒ `landmark_name` gesetzt; `'coordinate'` ⇒ beide Koordinaten gesetzt;
    `'multiple'` ⇒ beide Koordinaten NULL - den einen Ort, den sie vertreten müssten, gibt es
    gerade nicht. `place_kind IS NULL` heißt "kein Ortsbezug".

    Die Koordinaten stehen GERUNDET (zwei Nachkommastellen, rund 1,1 km), nie in voller Präzision
    "für später", und entstehen ausschließlich aus GEMESSENEN Koordinaten - ein übernommener Ort
    speist sie nie.

    `landmark_name` ist freier, extern erzeugter LLM-Text und kommt ausschließlich über
    `worker.py::_landmark_names` (also durch `sanitize_landmark_name`) hierher - kein direkter
    Zugriff auf `PhotoLandmarkDetection.name` an der Schreibstelle, kein Abschneiden. Beim Rendern
    gilt dieselbe Auflage wie für `FineLabel.raw_label`: ausschließlich als regulärer
    React-Textknoten."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("criterion_scoring_run_id", "position", name="uq_event_run_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    criterion_scoring_run_id: Mapped[int] = mapped_column(ForeignKey("criterion_scoring_runs.id"))
    # 1-basiert, chronologisch je Lauf.
    position: Mapped[int]
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime]
    landmark_name: Mapped[str | None] = mapped_column(default=None)
    # "landmark" | "coordinate" | "multiple" (events.py::PLACE_KINDS). Freier String ohne Enum wie
    # `category_key`: der Lesepfad prüft die Mitgliedschaft und liefert bei einem unbekannten Wert
    # "kein Ortsbezug" statt einer 500.
    place_kind: Mapped[str | None] = mapped_column(default=None)
    place_lat: Mapped[float | None] = mapped_column(default=None)
    place_lon: Mapped[float | None] = mapped_column(default=None)


class PhotoRanking(Base):
    """Der volle, sortierte Kandidatenpool einer Partition (event_id x category_key) für einen
    CriterionScoringRun - NICHT nur die Top-N. "Zeig die besten X pro Kategorie" ist damit eine
    reine Lese-Query (GET /projects/{id}/photos?top_n_per_category=N), kein Job-Parameter, und
    Backfill ein Nebeneffekt eines erneuten Abrufs nach einer Rating-Änderung; kein Server-Code
    "rückt" je aktiv nach. `category_key` ist wie `criterion_key` ein freier String,
    `rank_position` ist 1-basiert innerhalb der Partition.

    MEHRFACHZUGEHÖRIGKEIT: ein Foto hat pro Lauf EINE ZEILE JE KATEGORIE, zu der es gehört - genau
    eine davon trägt `is_primary=True`. Daher der Unique-Constraint über
    `(run, photo, category_key)`: ein Foto steht pro Lauf höchstens einmal JE KATEGORIE, nicht
    höchstens einmal überhaupt.

    `rank_score` ist über alle Zugehörigkeitszeilen eines Fotos IDENTISCH (der ungedämpfte
    gewichtete Kriterien-Mittelwert). `rank_position` ist es NICHT und innerhalb einer Partition
    auch nicht monoton in `rank_score` - die Modellkonfidenz zum Schlüssel DIESER Partition dämpft
    den Sortierschlüssel (ranking.py::confidence_ordering_score). Gewollt, kein Defekt.

    Die zweite Invariante - GENAU EINE Zeile mit `is_primary=True` je (Lauf, Foto) - ist nicht
    als Datenbankbedingung ausdrückbar und wird stattdessen im Schreibpfad gehalten
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
    # ECHTER Fremdschlüssel und NOT NULL: die Löschzusage prüft Erreichbarkeit über die Kanten in
    # `Base.metadata`, eine bloß logische Spalte fiele still heraus. Nullbarkeit ist keine
    # Testfrage, sondern eine fachliche Festlegung - die Migration entwertet die Altläufe, damit
    # "jedes Kandidatenfoto gehört zu genau einem Event" ausnahmslos gilt und weder Lesepfad noch
    # Spec einen Ausnahmezweig für einen Zustand tragen, den die Anwendung selbst nie erzeugt.
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    category_key: Mapped[str]
    rank_score: Mapped[float]
    rank_position: Mapped[int]
    # BEWUSST OHNE Default, weder Python- noch Server-seitig: ein Schreibpfad, der die Spalte
    # vergisst, soll auffallen statt still eine zweite Hauptkategorie zu erzeugen.
    is_primary: Mapped[bool]


class PhotoLandmarkDetection(Base):
    """Der vom Vision-LLM identifizierte Sehenswürdigkeit-Name, 1:1 zu Photo, analog PhotoScore.

    `photo_id` ist Primary Key, weil dies eine optionale Detail-Zeile pro Foto ist, kein
    Mehrfach-Kriterien-Fact. Nur angelegt, wenn tatsächlich ein Name identifiziert wurde - kein
    Platzhalter-"unbekannt". `confidence` dupliziert den zugehörigen
    PhotoCriterionScore(criterion_key="landmark").value und hält diese Tabelle für eine Abfrage
    ohne Join selbsttragend; beide Werte stammen atomar aus derselben API-Antwort.

    `provider` hält fest, welcher Cloud-Provider diese Zeile erzeugt hat - sonst wäre die Herkunft
    bereits gescorter Fotos nach einem Umschalten von Settings.landmark_provider unklar. Atomar im
    selben Upsert wie name/confidence gesetzt (worker.py::_upsert_landmark_detection). Der Default
    "anthropic" deckt Zeilen aus der Zeit vor dieser Spalte ab; worker.py setzt den Wert im
    produktiven Pfad immer explizit."""

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

    PROJEKTÜBERGREIFEND, kein project_id-Bezug: reine Vokabular-Einträge ("hund" ist kein
    personenbezogenes Datum), keine Fotoinhalte. Die HÄUFIGKEITSABFRAGE ist deshalb zwingend über
    `photo_fine_labels -> photos.project_id` zu skopieren: ein globales SELECT auf diese Tabelle
    würde Label-Häufigkeiten ANDERER Projekte ausliefern.

    `canonical_key` ist ein URL-/Key-sicherer Slug (remote_classification.py::_slugify),
    `display_name` der zuerst gesehene Roh-Label-Text in Originalschreibweise (reine Anzeigehilfe,
    keine kuratierte Übersetzung). `embedding` ist der 384-dimensionale Text-Embedding-Vektor
    (label_embedding.py) als JSON-Liste von float.
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
    ist Primary Key: strukturell nie mehrere Zeilen pro Foto.

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
    # `detected_category_confidences.get(category_key)`. Bewusst redundant, damit die
    # Statistik-Aggregation in SQL laufen kann. Tragbar, weil es genau EINE schreibende Stelle
    # gibt (worker.py::run_remote_category_classification) und beide Werte dort aus derselben
    # Quelle in derselben Transaktion entstehen; die Invariante wird getestet.
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
    CriterionScoringRun/ScoringRun/ScanRun, aber OHNE scoring_run_id-FK: dieser Job schreibt
    ausschließlich in photo_category_classifications/photo_fine_labels/fine_labels, berührt weder
    cluster_key noch PhotoRanking direkt - kein 409-Staleness-Guard, kein
    Ausschuss-Gate-Erfordernis."""

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
    # Lauf hat genau einen Zweck. Nullable-Semantik, Zählweise von `api_calls` und das Einfrieren
    # von `cost_usd` gelten wortgleich wie bei den vier `landmark_*`-Kostenspalten an
    # CriterionScoringRun.
    api_calls: Mapped[int | None] = mapped_column(default=0)
    input_tokens: Mapped[int | None] = mapped_column(default=0)
    output_tokens: Mapped[int | None] = mapped_column(default=0)
    cost_usd: Mapped[float | None] = mapped_column(default=0)

    # Die Modell-ID dieses Laufs, Gegenstück zu `CriterionScoringRun.landmark_model` -
    # Nullable-Semantik ("NULL = nicht erfasst") und Schreibzeitpunkt wortgleich dort.
    model: Mapped[str | None] = mapped_column(default=None)

    # Der LIVE-Zähler der fehlgeschlagenen Einzelaufrufe dieser Phase - Gegenstück zu
    # `CriterionScoringRun.landmark_failed_calls`, Nullable-Semantik wortgleich dort. Geschrieben
    # am Block-Commit-Punkt (`photos_processed`/`last_progress_at`), NICHT im `finally`: die Zahl
    # muss WÄHREND des Laufs stimmen.
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
