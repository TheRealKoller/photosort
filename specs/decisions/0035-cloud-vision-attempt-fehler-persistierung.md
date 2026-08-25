# 0035 - Persistierte Attempt-/Fehler-Erfassung für Cloud-Vision-Status-Transparenz

**Status:** Accepted
**Datum:** 2026-08-24
**Bezug:** [`inbox/0032-cloud-status-transparenz-foto-details.md`](../inbox/0032-cloud-status-transparenz-foto-details.md) (Ursprung), künftige Feature-Spec 0058, [`decisions/0025-cloud-landmark-erkennung.md`](./0025-cloud-landmark-erkennung.md) (Punkt 3/6: best-effort/`continue`-Verhalten, `photo_landmark_detections`-Anlage nur bei Namen), [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (Punkt 5: identisches best-effort-Verhalten, `photo_category_detections`-Anlage immer 1-3 Zeilen bei Erfolg), [`decisions/0034-strukturiertes-logging-cloud-vision-fehler.md`](./0034-strukturiertes-logging-cloud-vision-fehler.md) (parallel in Arbeit, Spec 0056 — Logging derselben zwei Fehlerfälle, ergänzt hier um persistierte, per-API-abrufbare Sichtbarkeit), [`decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md`](./0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md) (bereits etabliertes Präzedenz-Muster: `api/photos.py::_category_candidates_out` rekonstruiert Schwellenwert-Zugehörigkeit read-time aus bereits persistierten `PhotoCriterionScore`-Werten, statt sie separat zu speichern — hier für dieselbe Denkweise wiederverwendet).

## Kontext

Daniel möchte in der Foto-Detailansicht für **jedes** Foto (auch Nicht-Kandidaten) für beide Cloud-Vision-Läufe (Landmark-Erkennung, ADR 0025; Remote-Kategorie-Klassifizierung, ADR 0032) sehen, welcher von fünf Zuständen zutrifft: noch kein Lauf angestoßen, kein Kandidat, Consent deaktiviert, Lauf gelaufen mit Fehler, Lauf gelaufen mit Ergebnis (inkl. "nichts gefunden" als Sonderfall bei Landmark). Drei der fünf Zustände sind bereits vollständig aus bestehenden Daten ableitbar (Consent-Schalter, Kandidaten-Schwellenwerte, Ergebnis-Zeilen); der eigentliche Auftrag dieser ADR ist, zu klären, was von den verbleibenden zwei Zuständen ("es gab einen Versuch, aber X") tatsächlich neu persistiert werden muss.

**Wichtiger Befund aus der Code-Verifikation (verändert die ursprüngliche Annahme des Klärungsauftrags):** Bei der Landmark-Phase (`worker.py::run_criterion_scoring`, Zeile ~1261-1270) wird bei einem *erfolgreichen* Cloud-Aufruf **immer** `_upsert_criterion(photo_id, "landmark", landmark_value, CriterionSource.CLOUD)` geschrieben — unabhängig davon, ob `detection.name is not None`. `compute_landmark_score` liefert `0.0` genau dann, wenn kein Name gefunden wurde (`criteria.py`, Zeile 352-362). Das bedeutet: "Lauf lief erfolgreich durch, nichts gefunden" hinterlässt in Wahrheit bereits heute eine Spur — eine `PhotoCriterionScore(criterion_key="landmark")`-Zeile **ohne** zugehörige `PhotoLandmarkDetection`-Zeile. Nur ein tatsächlicher **Fehlschlag** (Exception vor diesem Upsert) hinterlässt keine Spur. Bei der Remote-Kategorie-Phase gibt es den "erfolgreich, aber nichts gefunden"-Fall laut ADR 0032 Punkt 3 ohnehin nicht (Prompt erzwingt 1-3 Label bei Erfolg) — auch dort ist ausschließlich der Fehlschlag die unsichtbare Lücke.

**Konsequenz:** Der ursprünglich vom `requirements-engineer`-Entwurf vorgeschlagene Ansatz (eine Tabelle mit vollem Status-Enum inkl. `NOT_RUN`/`NOT_CANDIDATE`/`CONSENT_DISABLED`/`ERROR`/`NO_RESULT`/`RESULT` je Foto×Lauf-Typ) wäre eine Verdopplung bereits vorhandener Information für vier der sechs Werte. Diese ADR entscheidet sich für das schlankere Muster.

## Entscheidung

### 1. Nur Fehlschläge werden neu persistiert — alles andere bleibt read-time abgeleitet

Neue, kleine Tabelle `photo_cloud_vision_errors` (siehe Punkt 2) erfasst ausschließlich "der letzte bekannte Versuch für dieses Foto×Lauf-Typ ist fehlgeschlagen". Alle anderen vier Zustände werden zur Anfragezeit aus bereits vorhandenen Daten hergeleitet, in dieser Prioritätsreihenfolge (spiegelt die tatsächliche Ausführungsreihenfolge im Worker):

1. **Erfolgssignal zuerst** (stärkstes, konkretestes Signal, schlägt alles andere): Landmark → `photo.landmark_detection is not None` = Ergebnis vorhanden ("gefunden"); sonst existiert eine `PhotoCriterionScore(criterion_key="landmark")`-Zeile = Ergebnis vorhanden ("nichts gefunden", eigener Sonderfall). Remote-Kategorie → `photo.category_label_detections` nicht leer = Ergebnis vorhanden (es gibt hier keinen "nichts gefunden"-Fall, siehe Kontext).
2. **Sonst: Fehler-Zeile** (Punkt 2) für dieses Foto×Lauf-Typ vorhanden → Fehler. Eine Fehler-Zeile bleibt bewusst historische Evidenz eines tatsächlichen Versuchs, unabhängig vom *aktuellen* Consent-Zustand (ein Foto, das fehlschlug, während Consent aktiv war, zeigt weiterhin "Fehler", auch wenn Consent seither deaktiviert wurde — nicht "Consent deaktiviert", das würde die konkretere, bereits vorhandene Information verschleiern).
3. **Sonst:** `project.cloud_vision_detection_enabled == False` → Consent deaktiviert.
4. **Sonst:** Kandidaten-Prüfung schlägt fehl (Landmark: `criteria.py::is_landmark_candidate(...)`, neue reine Funktion, extrahiert aus `worker.py::_select_landmark_candidates` — siehe Punkt 3; Remote-Kategorie: `photo.score is not None and photo.score.suggested_status is None`, spiegelt exakt die WHERE-Klausel von `select_remote_category_candidates`) → kein Kandidat.
5. **Sonst:** noch kein Lauf angestoßen.

**Dokumentierte, bewusste Vereinfachung:** Wurde für ein Projekt noch nie ein `score-criteria`-Lauf ausgeführt, sind `content_landscape`/`gebaeude` beide implizit `0.0` (keine `PhotoCriterionScore`-Zeile vorhanden) — die Landmark-Kandidaten-Prüfung liefert dann `False`, das Foto erscheint als "kein Kandidat" statt eines separaten "lokale Vorstufe fehlt noch"-Zustands. Für die Zielgruppe dieser Spec (Foto-Detailansicht, kein Diagnose-Tool) ausreichend präzise, kein sechster Statuswert nötig.

### 2. Neue Tabelle `photo_cloud_vision_errors`, composite Primary Key, kein Verlaufs-/Historien-Log

```python
class CloudVisionPhase(enum.StrEnum):
    LANDMARK = "landmark"
    REMOTE_CATEGORY = "remote_category"


class PhotoCloudVisionError(Base):
    __tablename__ = "photo_cloud_vision_errors"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    phase: Mapped[CloudVisionPhase] = mapped_column(
        SQLEnum(CloudVisionPhase, native_enum=False, length=20), primary_key=True
    )
    error_type: Mapped[str]
    error_message: Mapped[str]
    attempted_at: Mapped[datetime]
```

- **Composite PK `(photo_id, phase)`**, kein `id`+`UniqueConstraint`-Paar (wie `PhotoCriterionScore`/`PhotoCategoryDetection`): es gibt strukturell höchstens eine sinnvolle "letzter Fehlschlag"-Zeile je Foto×Lauf-Typ, kein Mehrfach-Fact — dieselbe Konvention wie `PhotoScore`/`PhotoLandmarkDetection` (natürlicher Schlüssel als PK), hier nur um `phase` erweitert, da zwei Lauf-Typen dieselbe Struktur teilen.
- **Kein Verlauf, keine Historie:** ein erneuter Fehlschlag überschreibt (Upsert, analog `_upsert_landmark_detection`), keine zweite Zeile — konsistent mit dem projektweiten "ein erneuter Lauf überschreibt"-Prinzip (`PhotoCriterionScore`-Docstring).
- **`error_type`/`error_message`:** identischer Inhalt wie der `WARNING`-Log-Eintrag aus ADR 0034/Spec 0056 (`type(exc).__name__`, `str(exc)`) — an der jeweiligen Call-Site **einmal** berechnet, an **beide** Senken (Logger, DB) weitergereicht, keine zweite, potenziell abweichende Berechnung. `error_message` wird auf `_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH = 500` Zeichen gekappt (Modul-Konstante in `worker.py`, defensiver Schutz gegen eine entartete Fehlermeldung, analog `MAX_REMOTE_LABEL_LENGTH` aus ADR 0032 Punkt 3) — die in Spec 0056/ADR 0034 bereits verifizierte Sanitisierungs-Leitplanke (keine Secrets/Rohdaten in `str(exc)`) gilt hier unverändert, da dieselbe bereits sanitierte Quelle verwendet wird; **Security-Anmerkung:** diese ADR führt eine neue, per API abrufbare Persistenz-Senke für dieselben Werte ein (vorher nur `docker compose logs`) — die Prüfung, ob das für den bereits etablierten "kein Innentäter-Modell"-Kontext (Familienprojekt) unproblematisch bleibt, ist explizit an `security-engineer` delegiert (siehe Spec-Abschnitt Security), nicht hier final entschieden.
- **`attempted_at`:** Zeitpunkt des letzten Fehlschlags — reicht für die geforderte Anzeige ("Fehler beim Lauf vom ..."), keine weiteren Metadaten (keine HTTP-Statuscodes, kein Provider-Feld — die Fehlermeldung selbst enthält bereits genug Kontext, ADR 0034 Punkt 5, kein zusätzlicher strukturierter Wert nötig für eine reine Anzeige).
- **Aufräumen bei Erfolg:** Gelingt ein späterer Versuch für ein zuvor fehlgeschlagenes Foto (das Foto bleibt laut ADR 0025/0032 automatisch Kandidat, solange keine Erfolgszeile existiert), wird die zugehörige Fehler-Zeile **gelöscht**, nicht stehen gelassen — hält die Tabelle konsistent mit ihrer eigenen Bedeutung ("letzter bekannter bekannter Versuch ist fehlgeschlagen"), auch wenn die Priorisierung in Punkt 1 (Erfolg schlägt Fehler) einen vergessenen Lösch-Aufruf funktional abfangen würde. Kein Muss für die Korrektheit der API-Antwort, aber ein Muss für Datenhygiene bei einer direkten DB-Inspektion.

### 3. Verdrahtung: vier Call-Sites in `worker.py`, kein neuer, drittes Konzept neben ADR 0034

Kein Ersatz, keine Erweiterung des `_log_cloud_vision_failure`-Helfers aus Spec 0056/ADR 0034 — Logging (ephemer, reine Betriebssicht, bereits security-geprüft in genau dieser Form) und Persistierung (dauerhaft, per API abrufbar, neuer eigener Lebenszyklus mit Lösch-Pfad) sind bewusst zwei getrennte, parallele Aufrufe an derselben Stelle, nicht ein gemeinsamer Helfer — würde man sie verschmelzen, koppelt man zwei unabhängig bewertbare/änderbare Verhaltensweisen (z.B. künftige Log-Format-Änderung dürfte nicht versehentlich die Persistenz mitverändern) und der reine, synchrone `_log_cloud_vision_failure`-Helfer müsste async werden und Session-Zugriff bekommen, nur wegen dieser Spec. Beide Aufrufe teilen sich stattdessen dieselben, einmal berechneten Werte (`exc_type_name`, `exc_message`) — keine doppelte `type()`/`str()`-Auswertung.

- **Landmark-Fehlerpfad** (`run_criterion_scoring`, ~Zeile 1254-1260, vor dem bestehenden `continue`): `await _record_cloud_vision_error(session, photo_id, CloudVisionPhase.LANDMARK, result, now)`.
- **Landmark-Erfolgspfad** (~Zeile 1261-1270, nach dem bestehenden `_upsert_criterion(..., "landmark", ...)`): `await _clear_cloud_vision_error(session, photo_id, CloudVisionPhase.LANDMARK)`.
- **Remote-Kategorie-Fehlerpfad** (`run_remote_category_classification`, ~Zeile 1460-1465, vor dem bestehenden `continue`): `await _record_cloud_vision_error(session, photo.id, CloudVisionPhase.REMOTE_CATEGORY, result, now)`.
- **Remote-Kategorie-Erfolgspfad** (nach der bestehenden `best_by_canonical`-Schreibschleife, ~Zeile 1481-1500): `await _clear_cloud_vision_error(session, photo.id, CloudVisionPhase.REMOTE_CATEGORY)`.

`_record_cloud_vision_error`/`_clear_cloud_vision_error` sind neue, kleine `worker.py`-Helfer, strukturell analog `_upsert_landmark_detection` (kein Commit im Helfer selbst — reine `session.add`/`session.delete`, Persistierung läuft über die bereits bestehenden periodischen Commit-Punkte der jeweiligen Schleife).

### 4. `criteria.py::is_landmark_candidate` — neue, gemeinsam genutzte reine Funktion statt Logik-Duplikat

`worker.py::_select_landmark_candidates` prüft die Schwellenwerte heute inline. Diese ADR extrahiert genau diese Prüfung (nicht die Skip-bereits-gescort-Logik, die bleibt worker-spezifisch) in eine neue, reine Funktion `criteria.py::is_landmark_candidate(values: dict[str, float]) -> bool`, die sowohl vom Live-Lauf (`_select_landmark_candidates`, übergibt die In-Memory-`candidate_values` eines Fotos) als auch von der neuen API-seitigen Read-Time-Ableitung (`api/photos.py`, übergibt ein aus `photo.criterion_scores` gebautes `dict[str, float]`) aufgerufen wird. Verhindert, dass beide Stellen bei einer künftigen Schwellenwert-Änderung (z.B. `_LANDMARK_CATEGORY_PRESENCE_THRESHOLD`-Anpassung) auseinanderlaufen — derselbe DRY-Grundsatz, den das Projekt bereits für `CRITERIA_REGISTRY`-Schwellenwerte durchgehend verfolgt.

### 5. API-Exposition: additives Feld an `PhotoOut`, kein neuer Endpunkt

Kein neuer Endpunkt — die Foto-Detailansicht bezieht ihre Daten bereits vollständig über `PhotoOut` (`GET /projects/{id}/photos`, dasselbe Muster wie `criterion_scores`/`remote_category_labels`/`ranking`, keine separate `GET /photos/{id}`-Route existiert im Projekt). Neues Feld `PhotoOut.cloud_vision_status: list[CloudVisionStatusOut]`, **immer genau zwei Einträge** (einer je `CloudVisionPhase`, analog dem "immer eine Liste, nie `None`"-Muster von `ratings`/`criterion_scores`) statt eines Objekts mit zwei benannten Feldern (`landmark`/`remote_category`) — konsistent mit dem im Projekt etablierten Registry-/Listen-Muster (`CRITERIA_REGISTRY`, `CategoryLabel`), erweiterbar, falls je ein dritter Cloud-Vision-Lauf-Typ dazukommt, ohne das Schema erneut zu brechen.

```python
class CloudVisionStatus(enum.StrEnum):
    NOT_RUN = "not_run"
    NOT_CANDIDATE = "not_candidate"
    CONSENT_DISABLED = "consent_disabled"
    ERROR = "error"
    NO_RESULT = "no_result"
    RESULT = "result"


class CloudVisionStatusOut(BaseModel):
    phase: CloudVisionPhase
    status: CloudVisionStatus
    error_message: str | None = None  # nur bei status == ERROR gesetzt
    attempted_at: datetime | None = None  # nur bei status in {ERROR, NO_RESULT, RESULT} gesetzt
```

`_photos_by_id` (`api/photos.py`) bekommt ein zusätzliches `selectinload(Photo.cloud_vision_errors)` (neue `Photo`-Relationship, `list[PhotoCloudVisionError]`, `cascade="all, delete-orphan"`) — kein zusätzliches Query je Foto. Eine neue, reine Funktion `_cloud_vision_status_out(photo: Photo, project: Project) -> list[CloudVisionStatusOut]` wendet die Priorisierung aus Punkt 1 für beide `CloudVisionPhase`-Werte an.

## Begründung

- Vermeidet die vom `requirements-engineer`-Erstentwurf vorgeschlagene, aber bei genauerer Code-Prüfung unnötige Duplikation: vier der sechs benötigten Zustände sind bereits vollständig aus bestehenden `PhotoCriterionScore`/`PhotoLandmarkDetection`/`PhotoCategoryDetection`/`Project.cloud_vision_detection_enabled`-Daten ableitbar — dieselbe Denkweise, die `api/photos.py::_category_candidates_out` (ADR 0023) bereits etabliert hat (Schwellenwert-Zugehörigkeit read-time statt separat gespeichert).
- Die neue Tabelle bleibt bewusst minimal (drei fachliche Spalten, kein Verlauf) — deckt exakt die eine tatsächliche Lücke ab (ein Fehlschlag hinterlässt aktuell keine Spur), ohne ein neues, umfangreiches Status-Enum-Konzept parallel zu bereits vorhandenen Erfolgssignalen zu führen.
- Trennt Logging (ADR 0034, ephemer, Betriebssicht) und Persistierung (dieser ADR, dauerhaft, Produktsicht) bewusst als zwei unabhängige, aber wertgleiche Schreibvorgänge an derselben Stelle — vermeidet eine unnötige Kopplung zweier unterschiedlicher Lebenszyklen, ohne die bereits geprüfte Sanitisierung zu duplizieren.
- Wiederverwendet ein bereits etabliertes Prinzip (natürlicher Schlüssel als PK für "höchstens eine Zeile je Foto"-Tabellen) statt ein neues zu erfinden.

## Konsequenzen

- **Neue Backend-Abhängigkeit:** keine.
- **Neues Secret:** keines.
- **Neue Migration:** additiv, eine neue Tabelle `photo_cloud_vision_errors` (`photo_id`, `phase`, `error_type`, `error_message`, `attempted_at`, composite PK `(photo_id, phase)`), neuer Enum-Typ `CloudVisionPhase`.
- **Geänderte Dateien:** `models.py` (neue Klasse `PhotoCloudVisionError`, neuer Enum `CloudVisionPhase`, neue `Photo.cloud_vision_errors`-Relationship), `criteria.py` (neue Funktion `is_landmark_candidate`, `worker.py::_select_landmark_candidates` darauf umgestellt), `worker.py` (zwei neue Helfer `_record_cloud_vision_error`/`_clear_cloud_vision_error`, vier neue Call-Site-Aufrufe, neue Modul-Konstante `_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH`), `api/photos.py` (`CloudVisionStatus`/`CloudVisionStatusOut`, `PhotoOut.cloud_vision_status`, `_cloud_vision_status_out`, zusätzliches `selectinload`).
- **`docs/architecture.md`** (Owner `architect`) wird nach Umsetzung um die neue Tabelle, den neuen Enum und das neue `PhotoOut`-Feld ergänzt.
- **`specs/architecture/0003-securitykonzept.md`** braucht eine kurze Ergänzung (Zuständigkeit `security-engineer`, im Rahmen der Spec-0058-Konsultation): dieselben bereits sanitierten Fehlerdaten (ADR 0034 Punkt 5) bekommen mit dieser ADR erstmals eine dauerhafte, per API abrufbare zweite Senke neben dem Log — zu bestätigen, dass das im bestehenden Vertrauensmodell (kein Innentäter, Zwei-Personen-Familienprojekt) unproblematisch bleibt.
- Ein späterer Wunsch nach einer echten Attempt-**Historie** (mehrere Fehlschläge über Zeit nachvollziehbar, nicht nur der letzte) wäre eine eigene, neue ADR — diese ADR entscheidet sich bewusst gegen ein Historien-Log, da der aktuelle Produktbedarf (Spec 0058) nur den *aktuellen* Zustand verlangt.
