# 0126 - Personen: lokal erkannt mit YuNet und SFace, global festgelegt, Erkennung und Korrektur getrennt

**Status:** Accepted
**Teilweise abgelöst:** Punkt 3, Absatz „API-Prozess" (nur zum Festlegen), und in Punkt 6 die
Spaltensätze von `photo_person_detections` („keine Box") und `photo_person_corrections` durch ADR
[`0127`](./0127-personen-gesichtsbezug-nur-fuer-festgelegte-ohne-namen-auf-anfrage.md): Erkennung
und Korrektur tragen optional die Box des Gesichts einer festgelegten Person, die Korrektur
zusätzlich die daraus entstandene Referenz, und der API-Prozess listet auch die unbenannten
Gesichter eines Projekts auf. „Für unbekannte Gesichter wird nichts gespeichert" und alle übrigen
Punkte gelten unverändert.
**Datum:** 2026-09-27
**Bezug:** [GitHub-Issue #292](https://github.com/TheRealKoller/photosort/issues/292), Spec 0292
**Umfang:** über dem Richtwert, weil Verfahren und Datenmodell an denselben Zusicherungen hängen
(nichts über unbekannte Gesichter, Vorrang der Korrektur) und nur zusammen prüfbar sind.

## Kontext

PhotoSort soll erkennen, ob eine von höchstens zwei festgelegten Personen auf einem Foto ist. Eine
falsche Benennung wiegt schwerer als ein übersehenes Foto; Fotos und Gesichtsmerkmale verlassen
den Server nicht. Im Image liegen `opencv-contrib-python`, `mediapipe`, `onnxruntime`,
`tensorflow`, kein PyTorch. Die InsightFace-Gewichte sind nur für nicht-kommerzielle Forschung
freigegeben, dlib gibt es auf PyPI nur als Quellpaket.

## Entscheidung

### 1. Verfahren: YuNet (Detektion) und SFace (Merkmal) über OpenCV

- `face_detection_yunet_2023mar.onnx` (MIT) und `face_recognition_sface_2021dec.onnx` (Apache-2.0,
  fp32, 128 Dimensionen) über `cv2.FaceDetectorYN`/`cv2.FaceRecognizerSF` — **keine neue
  Python-Abhängigkeit** und kein `onnxruntime` im Personenpfad (das OpenCV-Wheel bringt keines
  mit). Ausgerichtet wird immer über `alignCrop` mit den fünf Landmarken.
- Beide Modelle liegen in genau einem Modul, `face_analysis.py`. Sein Adapter bekommt Detektor und
  Erkenner übergeben (schmale Protokolle), damit Arbeitsfassung, Boxumrechnung, Klemmen,
  Verwertbarkeit, Sortierung und Obergrenze ohne Modell prüfbar sind. Er bietet zwei Schritte:
  `detect(image)` liefert die verwertbaren Gesichter (Punkt 4.1), höchstens
  `MAX_FACES_PER_PHOTO` (20) — die größten, bei Gleichstand nach Position —, geordnet von links
  nach rechts, dann oben nach unten; `embed(image, face)` liefert das normierte Merkmal. Der Index
  eines Gesichts ist seine Stelle in dieser Liste und bei gleicher Datei stabil.
- Analysiert wird eine Arbeitsfassung mit langer Kante `ANALYSIS_MAX_SIDE = 1280`: YuNet wird bei
  großen Gesichtern ungenau, und verrutschte Landmarken verfälschen das Merkmal.
- **Personendaten und Netzwerk-Clients bleiben getrennt, in beide Richtungen.** `face_analysis.py`,
  `person_matching.py` und `model_assets.py` importieren weder `models`, `db` noch `config` —
  ihr **vollständiger** Importgraph enthält damit keinen Netzwerk-Client (`httpx`, `cloud_vision`,
  `landmark`, `remote_classification`). `persons.py` braucht `models` und importiert **direkt**
  keinen davon. Umgekehrt enthält der vollständige Importgraph der Cloud-Module und von
  `classification_prompt.py` keines der drei Personenmodule. Gilt in jedem Lauf, auch mit
  Cloud-Einwilligung; sonst wäre der Weg eines Gesichts oder Namens zu einem Dritten eine
  Codezeile. Ein Import-Graph-Wächter hält alle drei Aussagen fest.
- Ein Test läuft gegen die **echten** Assets, ausschließlich mit synthetischen Bildern (kein
  Gesicht einer realen Person): Detektor ohne Treffer auf einem leeren Bild, Merkmal 128 endliche
  Werte. Er fängt eine inkompatible OpenCV-Version, weil `opencv-contrib-python` nach oben offen
  ist.

### 2. Gewichte und Telemetrie

- Beide Dateien werden nicht eingecheckt, sondern beim Image-Build, in CI und im
  Bare-Metal-Setup geladen und gegen einen festen SHA256 geprüft, von huggingface.co mit fester
  Revision:
  - `opencv/face_detection_yunet` @ `3cc26e7f1014a5ee5d74a42acee58bafc9d0a310`, 232 589 Byte,
    SHA256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
  - `opencv/face_recognition_sface` @ `3d7082438a6e4551e840c9b2bb60b71e8da4b524`, 38 696 353
    Byte, SHA256 `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`
- Das Repository verbreitet die Gewichte damit nicht weiter; die Herkunft der
  SFace-Trainingsdaten ist öffentlich nicht dokumentiert.
- **Ein Mechanismus für alle geladenen Assets:** Manifest `backend/src/photosort/model_assets.py`
  (je Asset Dateiname, URL mit fester Revision, Größe, SHA256; nur Konstanten, nichts
  überschreibbar) und Ladeprogramm `backend/scripts/fetch_model_assets.py` (Standardbibliothek,
  nur `https` auch bei Umleitungen, Timeout, liest höchstens die Manifestgröße, schreibt in eine
  temporäre Datei im Zielverzeichnis und erst nach bestandener Prüfung per `os.replace`; sonst
  löschen, Exit ≠ 0). Es ersetzt `scripts/fetch-label-embedder-model.sh` und den eigenen
  `RUN`-Schritt im `backend/Dockerfile`; `LABEL_EMBEDDER_ONNX_SHA256` zieht ins Manifest, und auch
  dessen URL bekommt eine feste Revision. Kein Anwendungsmodul lädt selbst oder importiert das
  Ladeprogramm. Der CI-Cache schlüsselt über den Inhalt des Manifests.
- **`onnxruntime`-Telemetrie ist aus.** Offizielle Builds senden sie unter Linux standardmäßig an
  Microsoft. `label_embedding.py` setzt `os.environ["ORT_DISABLE_TELEMETRY"] = "1"` — zuweisend,
  nie `setdefault` — unmittelbar vor dem ersten `import onnxruntime`. Gilt für jeden Prozess, der
  `onnxruntime` lädt; ein weiterer Importort übernimmt dieselbe Zeile. Zusätzlich setzt
  `backend/tests/conftest.py` die Variable ganz oben (Tests importieren `onnxruntime` direkt), und
  das `backend/Dockerfile` setzt sie als `ENV` für beide Container.

### 3. Wo das Modell läuft

- **Worker:** neue, letzte Phase `persons` des Klassifizierungslaufs (nach `ranking`), rein lokal,
  über **alle** Fotos des Projekts auf der Display-Variante. Die Schwerpunkte werden einmal zu
  Beginn der Phase frisch aus der Datenbank gebildet und nirgends darüber hinaus gehalten; die
  Phase liest nur Id und Schwerpunkt, nie den Namen. Sie läuft nicht, wenn keine Person eine
  Referenz des geladenen Modells hat oder der Adapter nicht baubar ist (`_try_build`); dann bleiben
  ihre Zähler `NULL` und die vorhandenen Erkennungen stehen.
- **API-Prozess:** nur zum Festlegen — Gesichter eines Fotos auflisten, ihren Ausschnitt
  ausliefern, das Merkmal des gewählten Gesichts bilden. Der Adapter wird einmal je Prozess träge
  gebaut und läuft auf einem **eigenen Executor mit genau einem Thread**: `cv2`-Objekte sind nicht
  threadsicher, und Wartende belegen so keinen Platz im gemeinsamen Threadpool. Gelesen wird nur
  die lokale Display-Variante; fehlt sie, antwortet der Endpunkt `404`, ohne das Modell zu rufen.

### 4. Die Entscheidungsregel — fest, vorsichtig, von niemandem einzuschätzen

In `person_matching.py`; alle Konstanten stehen nur dort. Die Entscheidungsfunktion bekommt je
verwertbarem Gesicht die Ähnlichkeiten zu den Personen, keine Merkmale:

1. Verwertbar ist ein Gesicht ab `MIN_DETECTION_SCORE` und einer kürzeren Seite von
   `MIN_FACE_SIDE_PX` in der Arbeitsfassung. Andere Gesichter werden weder benannt noch bei den
   folgenden Regeln mitgezählt; es entsteht für sie auch kein Merkmal.
2. Die Ähnlichkeit zu einer Person ist der Kosinus zum **Schwerpunkt** ihrer Referenzmerkmale,
   nicht zum ähnlichsten Einzelmerkmal: eine schlechte Referenz allein trägt keinen Treffer.
3. Kandidat einer Person ist ein Gesicht, wenn die Ähnlichkeit `ACCEPT_SIMILARITY` erreicht **und**
   die zur anderen Person um mindestens `DISTINCT_MARGIN` übertrifft — damit ist jedes Gesicht
   höchstens einer Person Kandidat. Ist nur eine Person festgelegt, entfällt der Abstand.
4. Erkannt ist eine Person auf dem Foto, wenn **genau ein** Gesicht ihr Kandidat ist. Bei zwei
   oder mehr ist eines sicher falsch; sie wird dort nicht benannt.
5. Jeder Vergleich steht in Einschlussform (`>=`); eine NaN-Ähnlichkeit ergibt damit nie eine
   Benennung.
6. Eine neue Referenz, deren Ähnlichkeit zum Schwerpunkt der **anderen** Person
   `ACCEPT_SIMILARITY` erreicht, wird abgelehnt (`409`).

**Die Konstanten sind keine Einstellung** — keine Umgebungsvariable, kein Endpunkt, keine
Oberfläche. Startwerte: `MIN_DETECTION_SCORE = 0.90`, `MIN_FACE_SIDE_PX = 100`,
`ACCEPT_SIMILARITY = 0.50`, `DISTINCT_MARGIN = 0.10` (die OpenCV-Schwelle 0.363 ist ein
genauigkeitsoptimaler Punkt und zu locker). Nach einer falschen Benennung in der Abnahme
(Punkt 5) wird verschärft und erneut geprüft; gelockert wird nie ohne eine neue, fehlerfreie
Abnahme. Erkannte Gesichter werden nie von selbst zu Referenzen.

### 5. Abnahme im laufenden Betrieb, ohne Familienfotos im Repository

Abgenommen wird an einem echten Projekt mit Verwandten und Kindern, nicht an einem eigens
sortierten Bestand: Nach einem Klassifizierungslauf sieht Daniel je Person die Filteransicht durch
und entfernt jeden falschen Namen. **Bestanden heißt: kein erkannter Name musste entfernt werden.**

Rein lesendes Messkommando `photosort.person_probe --project-id <N>` (Muster `criterion_probe.py`),
ohne Modell, nur aus der Datenbank. Je Person:

- **erkannt** — Erkennungszeilen des Projekts;
- **falsch** — erkannt **und** Korrektur `applies = false`;
- **ergänzt** — Korrektur `applies = true` ohne Erkennung (übersehen);
- **entfernt, nicht mehr erkannt** — Korrektur `applies = false` ohne Erkennung (Spur früherer
  Fehlgriffe nach einer Verschärfung);
- **Quote als Obergrenze** — `(erkannt − falsch) / (erkannt − falsch + ergänzt)`; übersehene
  Fotos, die niemand ergänzt hat, fehlen im Nenner, die wahre Quote liegt also höchstens so hoch.
  Ohne Nenner steht „nicht bestimmbar".

**Nur Anzahlen, Personen als „Person 1/2" nach Slot** — kein Pfad, kein Name, keine Zeile je Foto;
nur so darf die Ausgabe in einen öffentlichen Pull Request. Kein Schreibzugriff, kein Log.

### 6. Datenmodell

Alle Fremdschlüssel sind echte, benannte Fremdschlüssel.

- **`persons`** — global, ohne Projektbezug: `id`, `slot` (`1`/`2`, `UNIQUE`, `CHECK`), `name`,
  `name_key` (`UNIQUE`: NFC und `casefold` des Namens), `created_at`. **Höchstens zwei und keine
  zwei gleichen Namen sind strukturell wahr:** ein gleichzeitiges Anlegen scheitert an einem der
  beiden Constraints und wird `409`.
- **`person_references`** — `id`, `person_id` → `persons`, `embedding` (JSON-Liste, 128 Werte),
  `model_key`, `created_at`. **Kein Bezug auf Foto oder Projekt**, damit eine Projektlöschung die
  Festlegung nicht berührt. Entsteht nur für ein ausdrücklich gezeigtes Gesicht und nur, wenn alle
  Werte endlich sind und die Norm im Toleranzband um 1 liegt (sonst `409`, ohne Schreiben).
  Höchstens `MAX_REFERENCES_PER_PERSON` (20) Referenzen des aktuellen `model_key` je Person.
  Referenzen eines anderen `model_key` gehen in keinen Vergleich und keine Zählung ein; die erste
  Referenz des aktuellen Modells löscht sie in derselben Transaktion.
- **`photo_person_detections`** — Schlüssel (`photo_id` → `photos`, `person_id` → `persons`),
  `computed_at`. Schreibt nur die Phase `persons`; sie ersetzt die Menge eines Fotos nur, wenn sie
  es tatsächlich verarbeitet hat. Kein Wert, keine Box, kein Merkmal.
- **`photo_person_corrections`** — `id`, `photo_id` → `photos`, `person_id` → `persons`, `user_id`
  → `users` (Audit, nur aus dem angemeldeten Nutzer), `applies`, `updated_at`,
  `UNIQUE(photo_id, person_id)` **ohne** `user_id`: die zuletzt geschriebene gilt für beide Nutzer.
  Kein Lauf schreibt oder löscht sie (Muster `photo_motif_corrections`); so kehrt ein entfernter
  Name nie von selbst zurück.
- **Die wirksame Zuordnung entsteht beim Lesen** und wird nie materialisiert: gibt es eine
  Korrektur, entscheidet sie; sonst die Erkennung. Herkunft `corrected` bei Korrektur mit
  `applies`, `recognized` bei Erkennung ohne Korrektur. Genau ein SQL-Konstrukt
  (`persons.py::effective_person_assignments`) trägt das für Filter und Anzeige.
- **Für unbekannte Gesichter wird nichts gespeichert.** Merkmale, Boxen und Ähnlichkeiten leben
  nur während der Verarbeitung eines Fotos im Speicher; gespeichert wird allein das Paar
  (Foto, Person) eines erkannten Gesichts. Kein Log, keine API-Antwort trägt ein Merkmal, einen
  Schwerpunkt oder eine Ähnlichkeit; Gesichtsausschnitte entstehen auf Anfrage und gehen mit
  `Cache-Control: no-store`.
- **Löschen:** eine Person in einer Transaktion samt Korrekturen, Erkennungen und Referenzen
  (`persons.py::delete_person`, Mengenanweisungen). Schreibt die laufende Phase danach noch, scheitert
  das am Fremdschlüssel; die Phase verwirft diesen Block und läuft weiter. Ein Projekt über
  `project_deletion.py` samt Erkennungen und Korrekturen seiner Fotos; `persons`/`person_references`
  sind von `projects` aus nicht erreichbar und bleiben. Ein beim Scan verschwundenes Foto über die
  Kaskade an `Photo`.

## Konsequenzen

- ADR 0033 ist in ihren Umsetzungspunkten 1 bis 3 abgelöst (Punkt 2 oben); die Entscheidung
  „Download mit SHA256 statt Commit" gilt weiter.
- Ein Modellwechsel verlangt neue Referenzen; bis dahin entsteht keine neue Erkennung.
- Datenbanksicherungen außerhalb der Anwendung halten gelöschte Referenzen bis zu ihrer Rotation.
- `docs/architecture.md` und `docs/setup.md` ziehen im selben Pull Request nach; das
  Sicherheitskonzept führt die Datenklasse und die Auflagen.
