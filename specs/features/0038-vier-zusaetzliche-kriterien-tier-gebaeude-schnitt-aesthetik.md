# 0038 - Vier zusätzliche Kriterien: Tier, Gebäude, Goldener Schnitt, Ästhetik

**Status:** Implemented ([PR #88](https://github.com/TheRealKoller/photosort/pull/88))
**Erstellt:** 2026-08-13
**Bezug:** Entscheidung mit Daniel am 2026-08-13 im Kontext der Recherche-Ergebnisse (Spec 0035, PR #72) zu lokalen vs. Cloud-Kriterien. Abhängig von Spec 0037 (gateführte Bewertungs-Pipeline, Status Accepted, noch nicht implementiert). Nicht Teil dieser Spec: Sehenswürdigkeit-Erkennung (Cloud-only, eigene Inbox-Notiz `specs/inbox/0017-sehenswuerdigkeit-erkennung-cloud.md`).

## Ziel

Spec 0037 führt eine erweiterbare Kriterien-Registry (`PhotoCriterionScore`, `CRITERIA_REGISTRY`) ein, implementiert anfangs aber nur vier Kriterien (`sharpness`, `exposure`, `content_people`, `content_landscape`). Diese Spec erweitert das Set um vier weitere, **lokal berechnete** Kriterien — Tier, Gebäude, Goldener Schnitt und Ästhetik — um die Kuratierungs-Qualität zu verbessern und die automatische Rangfolgen-Bildung differenzierter zu gestalten. Alle vier laufen ohne Cloud-Anbindung, ohne externe API-Aufrufe und ohne zusätzliche Datenschutz-Fragen.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich, dass die automatische Foto-Bewertung vier weitere, lokal berechnete Kriterien einbezieht — Tier (Anwesenheit von Tieren), Gebäude (architektonische Szenen), Goldener Schnitt (Komposition nach Drittelregel), Ästhetik (allgemeine Bildqualität/Schönheit) — damit die Top-Fotos nach Kriterien bewertet werden, die für meine spezifische Sammlung relevanter sind und die Kuratierung verfeinern.

## Akzeptanzkriterien

**Generischer Registrierungs-Mechanismus (Erbe von Spec 0037)**
- [ ] `backend/src/photosort/criteria.py::CRITERIA_REGISTRY` enthält Einträge für alle vier neuen Kriterien, jeweils mit Anzeigename, `source=local_ml` oder `source=local_heuristic`, und zugehöriger Compute-Funktion.
- [ ] Jedes Kriterium ist über seinen eindeutigen `criterion_key` (`"tier"`, `"gebaeude"`, `"goldener_schnitt"`, `"aesthetics"`) nachschlagbar.

**Tier-Erkennung**
- [ ] `criterion_key="tier"`: Gibt einen Score ∈ [0,1] zurück, der misst, ob/wie prominent Tiere im Foto sichtbar sind.
- [ ] Berechnung erfolgt lokal via mediapipe Object Detector Task API (Modell EfficientDet-Lite0, COCO-Klassen — siehe Architektur-Abschnitt).
- [ ] Deckt die COCO-Tierklassen ab (`bird`, `cat`, `dog`, `horse`, `sheep`, `cow`, `elephant`, `bear`, `zebra`, `giraffe`); Insekten/Fische sind eine dokumentierte, bewusst akzeptierte Lücke (COCO enthält keine entsprechende Klasse).

**Gebäude-Erkennung**
- [ ] `criterion_key="gebaeude"`: Gibt einen Score ∈ [0,1] zurück, der misst, ob/wie dominant architektonische Szenen im Foto sind.
- [ ] Berechnung erfolgt lokal via mediapipe Image Classifier Task API (ImageNet-1k-Modell EfficientNet-Lite0 + kuratierte Architektur-Klassen-Allow-Liste — siehe Architektur-Abschnitt).
- [ ] Deckt Außenarchitektur zuverlässig ab (Kirchen, Burgen, markante Gebäude); Innenräume sind eine dokumentierte, bewusst akzeptierte Lücke (ImageNet hat kaum Innenraum-Klassen — Daniels Entscheidung gegen Places365/PyTorch, siehe ADR 0022).

**Goldener Schnitt (Komposition)**
- [ ] `criterion_key="goldener_schnitt"`: Gibt einen Score ∈ [0,1] zurück, der misst, wie gut das Foto die Drittelregel/den Goldenen Schnitt erfüllt.
- [ ] Berechnung erfolgt **vollständig lokal, ohne ML-Modell**, reine geometrische Heuristik auf Basis vorhandener Detektionen aus Spec 0037 (`classification.py` — Gesichts-/Uniform-Flächen-Bounding-Boxen, Horizont-Linie falls vorhanden).
- [ ] Nutzung bestehender, bereits Fotos verarbeitender Infrastruktur (kein neuer Bildverarbeitungsschritt); falls neue Detektionen nötig, separate Spec.

**Ästhetik (Bildqualität/Schönheit)**
- [ ] `criterion_key="aesthetics"`: Gibt einen Score ∈ [0,1] zurück, der misst, wie ästhetisch/schön das Foto wahrgenommen wird.
- [ ] Berechnung erfolgt lokal über NIMA (`idealo/image-quality-assessment`, MobileNet, Apache-2.0) via `tensorflow-cpu` — siehe Architektur-Abschnitt.

**Persistierung und Integration**
- [ ] Alle vier Kriterien werden im Zuge eines `CriterionScoringRun` (Spec 0037) über `criteria.py` berechnet und in `PhotoCriterionScore` geschrieben, analog zu den bestehenden vier Kriterien.
- [ ] Jedes Kriterium folgt demselben Fehlerbehandlungs-Muster wie in Spec 0037 AK: einzelner fehlgeschlagener Berechnungsversuch bricht den Lauf nicht ab; das betroffene Kriterium bleibt ungeschrieben.
- [ ] Nach erfolgreicher Berechnung aller vier sind die neuen Kriterien im Ranking-Prozess (`ranking.py`) verfügbar, falls sie in den Gewichtungs-Vorgaben enthalten sind.

**Tests**
- [ ] Alle vier Compute-Funktionen bekommen ein injizierbares Test-Double statt eines echten Modells (`AnimalDetectorLike`/`SceneClassifierLike`/`AestheticsModelLike`-Protocols, analog `FaceDetectorLike`/`FakeFaceDetector` in `backend/tests/test_classification.py`) — die realen `build_object_detector()`/`build_scene_classifier()`/`build_aesthetics_model()`-Factories werden wie das bestehende `build_face_detector()` **nie** in einem automatisierten Test aufgerufen (Infrastruktur-/CI-Risiko laut Testkonzept).
- [ ] **Tier** (`detect_animals`/Tier-Score, `test_criteria.py`): typischer Haustier-Treffer (z.B. `dog` über Konfidenz-Schwellwert) → hoher Score; kein Tier im Bild → Score nahe 0; Konfidenz unterhalb des Schwellwerts wird analog `FACE_DETECTION_CONFIDENCE_THRESHOLD` nicht gewertet; mehrere Tiere im selben Bild → Aggregationsregel (z.B. höchste Konfidenz/größte Fläche zählt) muss dokumentiert **und** getestet sein, keine stillschweigende Auswahl. Die dokumentierte COCO-Lücke (keine Insekten-/Fisch-Klasse) wird nicht als eigene Assertion geprüft, aber der zugehörige Testfall referenziert per Kommentar die bekannte Limitierung (analog dem bestehenden `SHARPNESS_REJECT_THRESHOLD`-Unkalibriert-Kommentar), damit sie nicht stillschweigend aus dem Blick gerät.
- [ ] **Gebäude** (`classify_scene`/Gebäude-Score, `test_criteria.py`): Treffer aus der kuratierten ImageNet-Allow-Liste (z.B. `church`) → hoher Score; eine ImageNet-Klasse außerhalb der Allow-Liste mit hoher Modell-Konfidenz (z.B. `dog`) → niedriger/0 Score — Nachweis, dass tatsächlich die Allow-Liste filtert und nicht nur die rohe Modell-Konfidenz durchgereicht wird. Dokumentierte Innenraum-Lücke (`living_room`/`kitchen` nicht erkennbar) analog zur Tier-Lücke im Testfall-Kommentar referenziert.
- [ ] **Goldener Schnitt** (`compute_golden_ratio_score`, `test_criteria.py`, reine Geometrie ohne Modell-Double): Subjekt-Zentrum nah an einem der vier Drittel-Schnittpunkte → hoher Score; exakt mittig komponiertes Subjekt → spürbar niedrigerer Score; kein Gesicht erkannt, aber eine `AnimalDetection` vorhanden → Fallback auf deren (größte) Bounding-Box greift nachweislich (Testfall kombiniert eine leere Gesichtsliste mit einer nicht-leeren Tierliste); weder Gesicht noch Tier erkannt → dokumentierter neutraler/niedriger Fallback-Wert, **kein** Fehler/keine Exception, Rückgabewert bleibt in `[0,1]`; mehrere erkannte Gesichter → getestete, dokumentierte Auswahlregel (z.B. höchste Konfidenz oder größte Fläche), keine implizite/zufällige Auswahl der ersten Bounding-Box.
- [ ] **Ästhetik** (`aesthetics.py`, NIMA, `test_aesthetics.py` neu): synthetische Ratingverteilung mit Erwartungswert nahe 1 → normierter Score nahe 0 (`(mean-1)/9`); Erwartungswert nahe 10 → Score nahe 1; gleichverteilte/neutrale Verteilung → Score um 0.5; degenerierte Verteilung (gesamte Wahrscheinlichkeitsmasse auf einer einzelnen Ratingklasse) als Grenzfall — Score bleibt trotzdem in `[0,1]`, kein `NaN`/Overflow durch die Normierungsformel.
- [ ] **Fehlerpfade, alle vier Kriterien** (`test_worker_criterion_scoring.py`, Integration gegen echte In-Memory-DB): ein Modell-Ladefehler bzw. eine Exception in genau einer der vier neuen Compute-Funktionen darf `run_criterion_scoring` nicht abbrechen (best-effort, deckungsgleich mit dem entsprechenden AK oben) — die übrigen, erfolgreich berechneten Kriterien desselben Fotos werden trotzdem als `PhotoCriterionScore` geschrieben, das fehlgeschlagene bleibt ungeschrieben (kein `0`-Platzhalter). Je Kriterium mindestens ein eigener Fehlerfall-Testlauf, nicht nur ein generischer.
- [ ] **Degenerierte Eingaben:** sehr kleines Bild (analog `test_image_smaller_than_the_tile_grid_does_not_crash` in `test_classification.py`) für alle vier Compute-Funktionen — kein Crash, Rückgabewert bleibt in `[0,1]` bzw. löst nachweislich denselben, oben getesteten Fehlerpfad aus statt eines unspezifizierten Absturzes.
- [ ] **Registry-Ebene** (Ergänzung des bestehenden `test_criteria.py`-Musters aus Spec 0037): alle vier neuen `criterion_key`-Einträge (`tier`/`gebaeude`/`goldener_schnitt`/`aesthetics`) vorhanden, korrektes `source` (`local_ml` für Tier/Gebäude/Ästhetik, `local_heuristic` für Goldener Schnitt); Wiederverwendungsnachweis für `detect_person`/`AnimalDetection` im Goldener-Schnitt-Compute über Spy/Aufrufzähler statt Reimplementierung, konsistent mit dem in `specs/architecture/0002-testkonzept.md` bereits etablierten Wiederverwendungs-Nachweis-Muster.
- [ ] **Modellgewichts-Integrität:** je neuem gepinnten Asset (zwei `.tflite`-Dateien, ein NIMA-`.h5`) ein eigener SHA-256-Vergleichstest, analog `test_committed_tflite_model_matches_the_documented_sha256` in `test_classification.py`.
- [ ] **Integration mit `run_criterion_scoring`** (Spec-0037-Tests, `test_worker_criterion_scoring.py`): alle vier neuen Kriterien werden bei einem aktiven `CriterionScoringRun` tatsächlich als `PhotoCriterionScore`-Zeilen geschrieben, inkl. Upsert-Nachweis bei erneutem Lauf (Wert wird überschrieben, keine Duplikatzeile); bestehende Spec-0037-Tests für `sharpness`/`exposure`/`content_people`/`content_landscape` bleiben ohne Assertion-Anpassung grün.
- [ ] **Coverage-Gate:** die neuen `build_*()`-Factories bleiben wie `build_face_detector()` untestbar/ungetestet (Infrastruktur-Grund) — das darf nicht dazu führen, dass die eigentliche Entscheidungslogik (Allow-Listen-Filterung, Fallback-Kette, Normierungsformel) unter 80% Coverage bleibt, weil die reinen Compute-Funktionen selbst die Hauptlast der Abdeckung tragen müssen (siehe Aufgabe-2-Review-Hinweis: hohe Coverage durch triviale Pfade allein reicht nicht).

**Bekannte Limitierungen dokumentieren**
- [ ] Jedes Modell/jede Heuristik hat bekannte Fehlerquoten und Sonderfälle — diese werden im Code kommentiert/dokumentiert (z.B. "Places365 kann X nicht gut unterscheiden", "Goldener Schnitt misst nur die Drittelregel, nicht dynamische Komposition").
- [ ] Kalibrierung/Feinabstimmung der Modelle auf Daniel und seine Frau's spezifische Sammlung ist **nicht** Teil dieser Spec — nur die Bereitstellung und erste Integration.

## Datenmodell-Bezug

Keine neuen Tabellen oder Spalten — reine Erweiterung der bestehenden `PhotoCriterionScore`-Tabelle aus Spec 0037 (Upsert für neue `criterion_key`-Werte). Abhängigkeit: Spec 0037 muss vollständig implementiert sein.

## Architektur / Umsetzung

**Bezug:** ADR [`decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md`](../decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md) (neu, enthält die vollständige Begründung aller Modellwahlen) sowie [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md), [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md).

**Voraussetzung, verbindlich:** Diese Spec ist erst sinnvoll umsetzbar, **nachdem Spec 0037 vollständig implementiert ist** (`criteria.py`, `CRITERIA_REGISTRY`, `ranking.py`, `CriterionScoringRun`, `run_criterion_scoring` existieren im Code noch nicht — Stand dieser Konsultation, 2026-08-14). Keine sinnvolle Teil-Parallelisierung möglich: alle vier neuen Kriterien registrieren sich in einer Registry, die es noch nicht gibt, und werden über einen Job-Ablauf geschrieben, der ebenfalls noch nicht existiert. Ein vorzeitiger Start würde entweder doppelte Infrastruktur bauen (die dann beim 0037-Merge wieder verworfen werden müsste) oder gegen einen sich noch ändernden Vertrag entwickeln. Zusätzlich baut die Goldener-Schnitt-Umsetzung (siehe unten) auf einem erweiterten `detect_person`-Rückgabewert auf, der bereits **in Spec 0037** (nicht erst hier) eingeführt wird — siehe dortige Vorgriffs-Ergänzung vom selben Datum.

### Modellwahl (Offene Fragen 1-3 der Spec)

1. **Tier (`criterion_key="tier"`):** **mediapipe Object Detector Task API**, Modell **EfficientDet-Lite0** (Google, Apache-2.0, COCO-80-Klassen, ~4-7 MB `.tflite`). Keine neue Abhängigkeit — dieselbe, bereits produktiv genutzte `mediapipe`-Bibliothek, nur eine andere Task-API neben dem bestehenden `FaceDetector`. YOLOv8 verworfen (AGPL-3.0, Netzwerknutzungsklausel-Risiko für ein proprietäres, über die eigene API genutztes Backend). CLIP/`open_clip` verworfen (würde eine weitere, eigenständige Inferenz-Laufzeit für ein Signal einführen, das mediapipe strukturell gleichwertig liefert). Tier-relevante COCO-Klassen: `bird`, `cat`, `dog`, `horse`, `sheep`, `cow`, `elephant`, `bear`, `zebra`, `giraffe`. **Dokumentierte Lücke:** keine Insekten-/Fisch-Klasse in COCO — im Code als bekannte Limitierung zu kommentieren (AK-Pflicht).
2. **Gebäude (`criterion_key="gebaeude"`):** **mediapipe Image Classifier Task API** mit ImageNet-1k-Modell (EfficientNet-Lite0, Apache-2.0) und kuratierter Allow-Liste architekturbezogener Klassen (`church`, `castle`, `palace`, `dome`, `library`, `lighthouse`, `barn`, `mosque` u.a.). Keine neue Abhängigkeit — dieselbe `mediapipe`-Bibliothek wie Tier-Erkennung und bestehender `FaceDetector`. Daniel hat sich am 2026-08-14 per Rückfrage explizit gegen die ursprünglich erwogene Places365/PyTorch-Alternative entschieden (siehe ADR 0022, Punkt 2): dort wäre die AK-Kategorie "Innenräume" treuer erfüllt worden, aber auf Kosten eines zweiten schweren ML-Frameworks im Image. **Bekannte, akzeptierte Limitierung:** ImageNet hat kaum Innenraum-Klassen — `living_room`/`kitchen`/`office` werden strukturell nicht erkannt, nur Außenarchitektur (Kirchen, Burgen, markante Gebäude) zuverlässig.
3. **Ästhetik (`criterion_key="aesthetics"`):** **NIMA** (`idealo/image-quality-assessment`, Apache-2.0, MobileNet-Backbone, ~16 MB), wie von Daniel bereits präferiert. Läuft über **`tensorflow-cpu`** (nicht das volle `tensorflow`-Paket) — CPU-only, keine funktionale Einbuße auf einem GPU-losen Zielsystem. Score = Erwartungswert der NIMA-Ratingverteilung (1-10), normiert auf `[0,1]` via `(mean - 1) / 9`. `pyiqa`/IQA-PyTorch explizit verworfen (PolyForm-Noncommercial-/NTU-S-Lab-Lizenz, für ein privates Projekt nicht eindeutig geklärt).

### Integrationsmuster in `criteria.py`

- **`classification.py` (Erweiterung, kein neues Modul für Tier):** neue Funktionen `detect_animals(image, detector) -> list[AnimalDetection]` + `build_object_detector()`, exakt analog zum bestehenden `detect_person`/`build_face_detector()`-Paar (gepinnte `.tflite`-Datei, SHA-256-Verifikation, `AnimalDetectorLike`-Protocol für Tests ohne echtes Modell). `AnimalDetection` als kleine `@dataclass(frozen=True)` mit `category: str`, `confidence: float`, `bounding_box`-Feldern (normiert wie `FaceBoundingBox`).
- **`classification.py` (Erweiterung, kein neues Modul für Gebäude):** neue Funktionen `classify_scene(image, classifier) -> list[SceneLabel]` + `build_scene_classifier()`, analog zum Tier-Paar — dieselbe `mediapipe`-Bibliothek, nur ein drittes Task-API-Paar neben `FaceDetector`/`ObjectDetector`. Gebäude-Score wird aus der kuratierten ImageNet-Klassen-Allow-Liste (siehe oben) plus Konfidenz gebildet.
- **Neues Modul `backend/src/photosort/aesthetics.py`** (Ästhetik/NIMA): analoges Muster, lokaler `tensorflow`-Import, `build_aesthetics_model()`-Factory, injizierbares `AestheticsModelLike`-Protocol.
- **Goldener Schnitt: keine neue Datei, keine neue Abhängigkeit.** Reine geometrische Funktion direkt in `criteria.py` (`compute_golden_ratio_score` o.ä.): nutzt die (in Spec 0037 bereits erweiterten) `FaceBoundingBox`-Daten aus `detect_person`, hilfsweise die größte `AnimalDetection`-Bounding-Box, falls kein Gesicht erkannt wurde. Distanz des/der Subjekt-Zentren zu den vier Drittel-Schnittpunkten, invers auf `[0,1]` normiert. Horizont-Linien-Erkennung wird **nicht** umgesetzt (kein neuer Bildverarbeitungsschritt, siehe Out-of-Scope-Abschnitt dieser Spec) — ohne erkanntes Subjekt: dokumentierter neutraler/niedriger Fallback-Score, kein Fehler.
- **`CRITERIA_REGISTRY`-Einträge** (Spec-0037-Mechanismus): `tier`/`gebaeude`/`aesthetics` mit `source=local_ml`, `goldener_schnitt` mit `source=local_heuristic` — konsistent mit dem in ADR 0021 definierten `CriterionSource`-Enum.

### Performance-Überlegungen (Offene Frage 4)

**GPU/CUDA:** nicht vorgesehen, nicht nötig — konsistent mit der bestehenden "Bewusste Annahme" in `docs/architecture.md` ("CPU-only-Betrieb"). `tensorflow-cpu` wird ausdrücklich CPU-only installiert.

**Compute-Overhead pro Foto:** grobe, ungemessene Schätzung (nur durch echten Benchmark auf der Zielmaschine klärbar, analog zum bereits in Spec 0035 dokumentierten Vorbehalt) — EfficientDet-Lite0 (Tier) und das ImageNet-Modell (Gebäude) je niedriger bis mittlerer zweistelliger Millisekundenbereich pro Foto, NIMA/MobileNet ähnlich, Goldener Schnitt vernachlässigbar (reine Geometrie, keine Bildverarbeitung). In Summe zusätzlich zur bereits vorhandenen mediapipe-Gesichtserkennung potenziell mehrere hundert ms/Foto. **Verschärft** den in ADR 0021 bereits dokumentierten Trade-off ("kein Kandidatenpool-Vorfilter mehr, `run_criterion_scoring` verarbeitet alle Ausschuss-Überlebenden") — für große Projekte (mehrere tausend Fotos) ist ein spürbar langer `CriterionScoringRun` realistisch. Kein Blocker für diese Spec, verstärkt aber das Signal für das in ADR 0021 bereits vorgemerkte, separate Performance-Follow-up. Konkrete technische Konsequenz für die Umsetzung: `run_criterion_scoring`s Progress-Commit-Kadenz sollte sich an der bereits etablierten, kleineren Batch-Größe von `TopSelectionRun` orientieren (dort schon wegen mediapipe-Laufzeit gewählt, siehe `docs/architecture.md`), nicht an der größeren Batch-Größe von `ScoringRun`.

**Docker-Image-Wachstum:** moderat (grobe Schätzung ~0,8-1,2 GB Endzustand, vor Umsetzung per echtem `docker build` zu verifizieren) — deutlich moderater als die ursprünglich erwogene Places365/PyTorch-Variante (dort geschätzt 1,5-2,5 GB). Für den Homeserver kein Blocker, aber dokumentiert.

### Abhängigkeits-Management (Offene Frage 4, Fortsetzung)

Neuer `backend/pyproject.toml`-Eintrag: nur `tensorflow-cpu` (für Ästhetik). Tier und Gebäude brauchen keine neue Abhängigkeit. **Vor der Umsetzung zu verifizieren** (analog ADR 0015): Installierbarkeit von `tensorflow-cpu` auf der tatsächlichen Ziel-Architektur (x86_64/aarch64, `python:3.12-slim`) — historisch nicht für jede Version durchgängige `aarch64`-Wheels, explizit vor dem TDD-Einstieg für Ästhetik zu prüfen. Modellgewichte (EfficientDet-Lite0-`.tflite`, ImageNet-Klassifikator-`.tflite`, NIMA-`.h5`) werden analog zum bestehenden `blaze_face_short_range.tflite`-Muster als gepinnte, im Repository eingecheckte Assets mit dokumentierter Quelle + SHA-256 geführt, kein Laufzeit-Download.

### Reihenfolge der Implementierung (Offene Frage 6)

Empfohlene interne Reihenfolge, von geringstem zu höchstem neuen Abhängigkeits-/Risiko-Zuwachs (unabhängig davon, ob als ein oder mehrere PRs umgesetzt — das ist eine `requirements-engineer`/Umsetzungs-Detailfrage, keine architektonische):

1. **Goldener Schnitt** zuerst — validiert den (bereits in Spec 0037 gebauten) erweiterten `detect_person`-Vertrag end-to-end, keine neue Abhängigkeit.
2. **Tier** — mediapipe-Erweiterung, dieselbe Bibliothek wie bereits im Image, moderates Risiko (neues `.tflite`-Asset).
3. **Gebäude** — ebenfalls mediapipe-Erweiterung (drittes Task-API-Paar), keine neue Abhängigkeit, moderates Risiko (neues `.tflite`-Asset, kuratierte Klassen-Allow-Liste).
4. **Ästhetik** — einziges neues, schweres Framework (TensorFlow), größter Einzel-Zuwachs.

### Nicht architektonisch, an Daniel zurückgemeldet

**Offene Frage 5 (Gewichtung im Ranking)** ist eine Produktentscheidung, keine architektonische — bleibt hier bewusst offen. `ranking.py::rank_photos` (Spec 0037) ist bereits so gebaut, dass eine spätere Gewichtungsentscheidung ohne Schema-/Signatur-Änderung nachgezogen werden kann (ADR 0021, Punkt 3); ob/wie die vier neuen Kriterien ins Default-Gewicht einfließen, entscheidet Daniel separat.

## UI/UX

**Nicht relevant — rein Backend, keine sichtbare Oberfläche.** Vor-Einschätzung bestätigt (`ux-ui-designer`-Konsultation, 2026-08-14).

Begründung: Diese Spec fügt vier neue `criterion_key`-Werte zur bereits (in Spec 0037) definierten `PhotoCriterionScore`/`CRITERIA_REGISTRY`-Pipeline hinzu. Kein neuer Endpunkt, keine neue Route, keine neue Komponente:

- Die AK dieser Spec beschränken die vier neuen Kriterien explizit auf Persistierung (`PhotoCriterionScore`) und Verfügbarkeit für `ranking.py`, "falls sie in den Gewichtungs-Vorgaben enthalten sind" — die konkrete Gewichtung selbst ist als "Offene Frage 5" bewusst zurückgestellt (Produktentscheidung, nicht Teil dieser Spec).
- Die `category_key`-Ableitung (Spec 0037, Grundlage der Abschnittsüberschriften in der Kuratierungs-Ansicht `/projects/:projectId/curate`) bleibt unverändert an die bestehenden Inhalts-Kriterien (`content_people`/`content_landscape`) gebunden — diese Spec erweitert die Prioritätskette nicht um `tier`/`gebaeude`. Es entstehen also keine neuen Kategorie-Abschnitte/-Chips.
- Der einzig sichtbare Effekt wäre eine veränderte Rangfolge/Auswahl innerhalb der bereits bestehenden Top-N-Kacheln (welche Fotos als "beste" erscheinen) — das läuft vollständig durch die in Spec 0037 bereits spezifizierte Kuratierungs-Oberfläche, ohne dass dafür ein neues visuelles Element, ein neuer Zustand oder ein neues Muster nötig ist.
- Die Spec selbst hält das bereits explizit als Out-of-Scope fest: "UI-Exponierung der neuen Kriterien in der Kuratierungs-Oberfläche (falls diese später gewünscht, eigene Spec)."

Keine Änderung an `specs/architecture/0004-design-system.md` oder am Design-System-Skill nötig — kein neues Muster, keine neue Komponente, keine neue Abhängigkeit. Sollte künftig gewünscht werden, die vier Kriterien tatsächlich als Sortier-/Filter-Optionen oder Score-Anzeige sichtbar zu machen, ist das eine eigene, spätere Spec mit eigener UI/UX-Konsultation (u.a. Frage, wie viele zusätzliche Kriterien-Chips sich noch mit dem Prinzip "Die Fotos sind der Star" vertragen).

## Security

**Vorbewertung bestätigt, mit Ergänzungen** (`security-engineer`, 2026-08-14): Die Grundeinschätzung "sehr begrenzte Sicherheitsrelevanz" ist zutreffend — kein neuer Endpunkt, keine neue Cloud-Anbindung, kein neues Secret, keine Änderung am Auth-/Autorisierungsmodell (`decisions/0003-auth-model.md` unberührt). Drei konkrete Punkte gehen über die reine Bestätigung hinaus und sind als Muss-Kriterien für die spätere Umsetzung (Spec 0037 + 0038) festgehalten:

**1. Abhängigkeits-Sicherheit — kein Blocker, Beobachtung statt CVE-Fund.**
`mediapipe` ist bereits produktiv im Einsatz und im Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`, Vermerk zu Spec 0024) bereits geprüft (Apache-2.0, keine bekannten kritischen CVEs zum damaligen Stand) — Tier/Gebäude nutzen dieselbe Bibliothek über zwei weitere Task-APIs, kein qualitativ neues Risiko. `tensorflow-cpu` ist die einzige echte neue Abhängigkeit und mit Abstand der größte Footprint-Zuwachs des Projekts (ADR 0022) — vor der Umsetzung ein reguläres Audit (aktuelle CVEs, `pip-audit`/GitHub-Dependabot-Alerts) durchführen, analog zum bereits etablierten Muster (Spec 0015/0024). Kein dedizierter `dependabot.yml` nötig — GitHub Dependabot-Alerts erfassen `backend/pyproject.toml` (PEP-621-Format, kein Lockfile) bereits automatisch über den Dependency Graph, wie es aktuell schon für `frontend/package-lock.json` der Fall ist (Spec 0015); zu verifizieren ist nur, dass die Alerts nach Hinzufügen von `tensorflow-cpu` tatsächlich greifen (`gh api repos/.../dependabot/alerts` nach Merge), kein neuer CI-Schritt erforderlich.

**2. Ressourcen-Overhead — kein zusätzlicher Endpunkt-Schutz nötig, aber zwei bestehende Muster sind zwingend weiterzuverwenden.**
Der Scoring-Job ist ein interner Worker-Job (`arq`), ausgelöst über einen bereits authentifizierten Endpunkt (analog `/score`, `/select-top`) — kein von außen direkt triggerbarer Angriffsvektor, und laut Bedrohungsmodell besteht ohnehin kein Innentäter-Schutzbedarf zwischen den beiden legitimen Nutzern (`specs/architecture/0003-securitykonzept.md`, "Explizit kein Ziel"). Ein dediziertes Rate-Limit/Ressourcenkontingent für diesen Job ist daher **keine Sicherheits-, sondern eine reine Robustheitsfrage** — bereits als Performance-Follow-up in ADR 0021 vorgemerkt (Batch-Größe/Progress-Kadenz), hier nicht zusätzlich verschärft. Zwei bestehende, projektweit verbindliche Muster gelten unverändert auch für die vier neuen Kriterien und sind bei der Umsetzung **nicht optional**, sondern wörtlich zu übernehmen:
- **Größenbegrenzung:** Alle vier neuen Compute-Funktionen (Tier/Gebäude/Ästhetik-Modelle sowie die Goldener-Schnitt-Geometrie) laufen auf der bereits auf 2048×2048 begrenzten `display`-Cache-Variante, nie auf dem Originalbild — konsistent mit dem bestehenden Grundsatz aus dem Sicherheitskonzept ("Lokale Bildverarbeitung"), verhindert Decompression-Bomb-artigen Speicher-/CPU-Verbrauch durch ungewöhnlich große Originaldateien.
- **Best-effort/Job-Terminierung:** Einzelner Kriterien-Fehler pro Foto darf den `CriterionScoringRun` nicht abbrechen (bereits AK-Pflicht dieser Spec) und der Lauf selbst muss beim äußeren Fehlerfall zuverlässig auf `FAILED` terminieren (`except Exception`, `CancelledError` bewusst unberührt) — beides bereits als projektweiter Grundsatz im Sicherheitskonzept verankert (Spec 0003/0023/0019), hier nur als vierte/fünfte Anwendung bestätigt, keine neue Formulierung nötig.

**3. Zwei zusätzliche, im Vor-Assessment nicht genannte Punkte:**
- **Modell-Asset-Integrität, Risiko wächst mit der Anzahl der Assets.** ADR 0022 sieht für alle drei neuen Modellgewichte (EfficientDet-Lite0-`.tflite`, ImageNet-Klassifikator-`.tflite`, NIMA-`.h5`) korrekt dasselbe SHA-256-Pinning-Muster wie beim bestehenden `blaze_face_short_range.tflite` vor — das ist ausreichend gegen nachträgliche Manipulation/Bit-Rot, aber das bereits bestehende Nice-to-have aus dem Sicherheitskonzept ("kein automatisierter Test verifiziert den SHA-256", Vermerk zu Spec 0024) wird mit vier statt einem Asset spürbar relevanter. **Empfehlung, hier zum Muss-Kriterium hochgestuft:** ein automatisierter Test (`hashlib.sha256(...).hexdigest() == "…"`) für jedes der vier Modell-Assets, nicht nur "nice to have" wie bisher.
- **Keras/H5-Modell-Deserialisierung (spezifisch für NIMA/TensorFlow, neu gegenüber dem bisherigen mediapipe-Muster).** Anders als `.tflite` (reines Inferenz-Format ohne Python-Codeausführung beim Laden) kann das Laden eines Keras-`.h5`-Modells über `tf.keras.models.load_model()` bei Vorhandensein bestimmter Layer-Typen (insbesondere `Lambda`) beliebigen Python-Code zur Ladezeit ausführen — ein bekanntes, dokumentiertes Deserialisierungsrisiko der Keras-H5-Modellformats, unabhängig von der SHA-256-Integritätsprüfung (die nur Manipulation *nach* dem ursprünglichen Download erkennt, nicht ob das Original selbst unsicheren Code enthält). Da das NIMA-Asset einmalig aus einer vertrauenswürdigen Quelle (`idealo/image-quality-assessment`, Apache-2.0) bezogen und danach als Repo-Asset geführt wird, ist das reale Risiko gering — trotzdem als Muss-Kriterium für `aesthetics.py::build_aesthetics_model()`: das Modell vor dem Commit auf unerwartete `Lambda`-Layer/`custom_objects` prüfen (`model.summary()`/Layer-Inspektion) und, falls von der verwendeten TensorFlow/Keras-Version unterstützt, mit `safe_mode=True` (bzw. äquivalentem sicheren Lademodus) laden. Kurzer Kommentar im Code, analog zum bestehenden SHA-256-Kommentar-Muster.

**Adversarial Inputs durch die beiden Nutzer selbst:** kein relevantes Risiko — Fotos stammen ausschließlich aus der von Daniel/seiner Frau selbst kontrollierten OpenCloud-Struktur, kein externer Upload-Pfad, und das Bedrohungsmodell schließt explizit einen Schutz der beiden legitimen Nutzer gegeneinander aus. Ein absichtlich präpariertes Bild zum Provozieren eines Modell-Crashs wäre Selbstsabotage am eigenen Familienserver, kein Angriffsszenario im Sinne dieses Sicherheitskonzepts.

**Sicherheitskonzept-Update:** Nicht jetzt, sondern erst nach tatsächlicher Umsetzung (analog zum etablierten Muster bei Spec 0015/0024) — dann Ergänzung eines datierten Vermerks in `specs/architecture/0003-securitykonzept.md` unter "Angriffsflächen"/"Bekannte Lücken": zweites ML-Framework (TensorFlow neben mediapipe) im Backend, vier statt ein gepinntes Modell-Asset, Bestätigung der SHA-256-Tests, Bestätigung der Keras-Lademodus-Prüfung.

**Status: nicht sicherheitsrelevant im Sinne eines Blockers** — die drei oben genannten Punkte sind Muss-Kriterien für die Implementierungsqualität, kein Grund, die Spec nicht auf `Accepted` zu setzen.

## Offene Fragen

Fragen 1-4 und 6 sind durch die `architect`-Konsultation (siehe "Architektur / Umsetzung", ADR 0022) geklärt. Nur Frage 5 bleibt eine bewusst offene Produktentscheidung:

5. **Gewichtung im Ranking:** Sollen die vier neuen Kriterien im Default-Ranking-Gewicht berücksichtigt werden, oder bleiben sie erst mal ungewichtet (Nutzer muss explizit aktivieren)? `ranking.py::rank_photos` (Spec 0037) unterstützt eine spätere Entscheidung ohne Schema-/Signatur-Änderung — Daniel entscheidet das separat, sobald Spec 0037 implementiert ist und reale Gewichtungs-Erfahrung vorliegt.

## Entscheidungen (2026-08-13/14, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Alle vier Kriterien lokal, kein Cloud-Einsatz** (per Rückfrage bestätigt, 2026-08-13): konsistent mit ADR 0015 und der Spec-0035-Recherche. Sehenswürdigkeit-Erkennung (das einzige Kriterium, das strukturell Cloud bräuchte) bewusst zurückgestellt, siehe Inbox `0017-sehenswuerdigkeit-erkennung-cloud.md`.
- **Ästhetik: NIMA zuerst** (per Rückfrage bestätigt, 2026-08-13): explizite Präferenz vor der `architect`-Konsultation, dort bestätigt und umgesetzt.
- **Modellwahl Tier/Ästhetik** (`architect`-Konsultation, ADR 0022): mediapipe EfficientDet-Lite0 (Tier, keine neue Abhängigkeit), NIMA/`tensorflow-cpu` (Ästhetik, einzige neue Abhängigkeit dieser Spec) — siehe Architektur-Abschnitt.
- **Modellwahl Gebäude: mediapipe-Alternative statt Places365/PyTorch** (per Rückfrage bestätigt, 2026-08-14, nach Vorschlag von `architect`): schlankere, dependency-freie Lösung mit schwächerer Innenraum-Erkennung bewusst der treueren, aber ein zweites schweres ML-Framework einführenden Places365-Variante vorgezogen. ADR 0022 entsprechend aktualisiert.
- **`detect_person`-Vertrag wird erweitert** (`architect`-Konsultation, ADR 0022): Rückgabewert wechselt von `bool` zu `list[FaceBoundingBox]`, umgesetzt beim TDD-Einstieg von Spec 0037 (nicht erst hier), da Spec 0037 zum Zeitpunkt dieser Entscheidung noch nicht implementiert war.
- **UI/UX: nicht relevant** (`ux-ui-designer`-Konsultation, 2026-08-14): reine Backend-Erweiterung, keine neue Oberfläche — siehe UI/UX-Abschnitt.
- **Security: kein Blocker, drei Muss-Kriterien ergänzt** (`security-engineer`-Konsultation, 2026-08-14): Dependency-Audit für `tensorflow-cpu`, SHA-256-Tests für alle vier Modell-Assets (statt nur "nice to have"), Keras-Lademodus-Prüfung für das NIMA-`.h5`-Asset — siehe Security-Abschnitt.
- **Teststrategie verfeinert** (`test-engineer`-Konsultation, 2026-08-14): konkrete Testfälle/Edge-Cases pro Kriterium, Fallback-Ketten-Test für Goldener Schnitt, Coverage-Hinweis zu den untestbaren `build_*()`-Factories — siehe Tests-AK.
- **Reihenfolge:** Goldener Schnitt → Tier → Gebäude → Ästhetik, aufsteigend nach neuem Abhängigkeits-/Risiko-Zuwachs (`architect`-Konsultation).

## Out of Scope

- **Sehenswürdigkeit-Erkennung** (Cloud-only, separate Entscheidung, Inbox-Notiz `specs/inbox/0017-sehenswuerdigkeit-erkennung-cloud.md`).
- **Feinabstimmung der Modelle auf die spezifische Fotobibliothek** — nur Bereitstellung der Modelle/Heuristiken in Standard-Konfiguration.
- **UI-Exponierung der neuen Kriterien** in der Kuratierungs-Oberfläche (falls diese später gewünscht, eigene Spec).
- **Neue Bildverarbeitungs-Schritte für die Kompositions-Analyse** — nur Wiederverwendung bestehender Detektionen aus Spec 0037 (`classification.py`).
- **Export der Kriterien-Bewertungen** (bleibt bei Spec 0004).
