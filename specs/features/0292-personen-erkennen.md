# 0292 - Die beiden Nutzer auf Fotos erkennen und benennen

**Status:** Accepted
**Erstellt:** 2026-09-27
**Bezug:** [Issue #292](https://github.com/TheRealKoller/photosort/issues/292), ADR [`0126`](../decisions/0126-personen-lokal-erkennen-global-festlegen-korrektur-getrennt.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Die Story bringt eine neue biometrische Datenklasse, eine Pipeline-Phase, sieben Endpunkte und drei Oberflächen, und jede davon hat eigene Zusagen zu Test und Sicherheit.

## Ziel

PhotoSort erkennt heute auf einem Foto nur, dass Menschen darauf sind. Wer das ist, erkennt es nicht. Daniel und seine Frau wollen die Fotos, auf denen einer von ihnen oder beide zu sehen sind, gezielt finden und beim Zusammenstellen des Albums gezielt ansehen können. Alle anderen Menschen bleiben wie bisher unbenannt.

Eine falsche Benennung wiegt schwerer als ein übersehenes Foto. Deshalb benennt PhotoSort nur, wenn die Zuordnung sicher ist. Eine Zuordnung lässt sich von Hand korrigieren. Gesichter sind besonders schützenswerte Daten, darum geschieht die Erkennung ausschließlich auf dem eigenen Server: Kein Foto und kein Merkmal verlässt ihn für diesen Zweck.

Dass der automatische Auswahlvorschlag die Personen berücksichtigt, ist nicht Teil dieser Story. Das regelt die Folge-Story #548.

## User Story

Als einer der beiden Nutzer möchte ich, dass PhotoSort auf den Fotos erkennt, ob Daniel, seine Frau oder beide abgebildet sind, und sie dort mit Namen führt, damit ich Fotos von uns gezielt finde und im Album-Entwurf gezielt ansehen kann, ohne dass ein Foto fälschlich einem von uns zugeschrieben wird.

## Akzeptanzkriterien

**Die zwei Personen festlegen**

- [ ] Es lassen sich höchstens zwei benannte Personen festlegen.
  - Der Versuch, eine dritte anzulegen, wird abgewiesen und legt nichts an, auch wenn zwei Anlagen gleichzeitig eintreffen.
  - Nach dem Entfernen einer Person lässt sich wieder eine anlegen.
- [ ] Eine Person wird festgelegt, indem ein Nutzer auf einem Foto ein gefundenes Gesicht auswählt und ihm einen Namen gibt. Weitere gezeigte Gesichter derselben Person kommen dazu.
  - Weder Oberfläche noch Schnittstelle noch eine Einstellung verlangen oder zeigen dafür eine Zahl oder Schwelle.
  - Angezeigt wird allein, wie oft ein Gesicht gezeigt wurde.
- [ ] Die Festlegung gilt einmal für alle Projekte. Eine Person, deren Gesicht in Projekt A gezeigt wurde, wird in Projekt B erkannt und dort in Filter und Detailansicht angeboten, ohne dass in B etwas festgelegt wird.
- [ ] Eine festgelegte Person lässt sich wieder entfernen.
  - Danach trägt kein Foto in keinem Projekt mehr ihren Namen, weder erkannt noch von Hand zugeordnet.
  - In der Datenbank der Anwendung bleibt nichts mit Bezug auf sie, insbesondere kein gezeigtes Gesichtsmerkmal.
  - Die andere Person bleibt unverändert.
- [ ] Wird ein Projekt gelöscht, verschwinden Erkennungen und Korrekturen seiner Fotos. Die festgelegten Personen und ihre gezeigten Gesichter bleiben, auch wenn diese Gesichter von Fotos des gelöschten Projekts stammen, und werden in anderen Projekten weiter erkannt.

**Erkennung**

- [ ] Ist eine festgelegte Person auf einem Foto sicher erkennbar, trägt das Foto nach dem nächsten Klassifizierungslauf ihren Namen mit der Herkunft „Erkannt“. Ein Foto kann beide Namen tragen.
- [ ] Ist die Zuordnung nicht sicher, trägt das Foto keinen Namen. „Nicht sicher“ heißt nach einer festen, nicht einstellbaren Regel:
  - das Gesicht gleicht der Person nicht genug;
  - es gleicht der anderen Person nicht deutlich weniger;
  - oder mehr als ein Gesicht des Fotos kommt für dieselbe Person in Frage.

  Zu kleine oder unsicher gefundene Gesichter werden nie benannt und zählen dabei nicht mit. Ein Wert genau auf einer Schwelle gilt als erreicht. Ein übersehenes Foto ist zulässig, eine falsche Benennung nicht.
- [ ] Auf einem Foto wird jedes Gesicht höchstens einer Person zugeordnet und jede Person höchstens einem Gesicht. Kommen für eine Person zwei Gesichter in Frage, trägt das Foto ihren Namen nicht; die andere Person kann es trotzdem tragen.
- [ ] Menschen, die nicht festgelegt sind, bekommen nie einen Namen. Für sie wird nichts gespeichert:
  - Ein Lauf über Fotos mit unbekannten Gesichtern hinterlässt dieselben Daten wie ein Lauf über dieselben Fotos ohne Gesicht.
  - Kein Protokolleintrag, keine Antwort der Schnittstelle und keine Anfrage an einen Dritten enthält ein Gesichtsmerkmal oder einen Ähnlichkeitswert.
- [ ] Die Erkennung läuft ausschließlich auf dem eigenen Server, unabhängig davon, ob Cloud-Dienste eingeschaltet sind.
  - Ein Lauf mit Cloud-Einwilligung schickt mit festgelegten Personen dieselben Anfragen an Dritte wie ohne.
  - Keine dieser Anfragen enthält einen Personennamen, ein Gesichtsmerkmal oder einen Gesichtsausschnitt.
- [ ] Die Personenangabe ist kein Motiv. Die acht Motive mit ihren Stärken, die Statistik und der Auswahlvorschlag sind nach einem Lauf mit erkannten Personen dieselben wie nach demselben Lauf ohne Personen.
- [ ] Auch Fotos bereits bestehender Projekte bekommen ihre Namen, spätestens nach einem erneuten Klassifizierungslauf; ein neuer Scan ist nicht nötig. Die Erkennung umfasst alle Fotos des Projekts, auch die im Ausschuss.
- [ ] Abnahme im laufenden Betrieb:
  - **Ablauf:** Nach einem Klassifizierungslauf in einem echten Projekt, in dem auch Verwandte und Kinder vorkommen, sieht Daniel die eingeschränkte Ansicht jeder Person vollständig durch und entfernt jeden falschen Namen.
  - **Bestanden:** Ein vollständiger Durchgang, in dem kein erkannter Name entfernt werden musste. Das Messkommando zählt dann null Fotos, die erkannt sind und zugleich einen von Hand entfernten Namen tragen.
  - **Bei einem Fehlgriff:** Die Regel wird verschärft, der Lauf wiederholt und die Durchsicht vollständig wiederholt, nicht nur an den früheren Fehlern.
  - **Ausweisung:** Nur aus der Datenbank, nur Anzahlen, Personen als „Person 1/2“, je Person:
    - richtig erkannt;
    - falsch erkannt, also erkannt und von Hand entfernt;
    - von Hand ergänzt, also ohne Erkennung;
    - von Hand entfernt und nicht mehr erkannt;
    - die Quote richtig erkannt ÷ (richtig erkannt + ergänzt).
  - **Die Quote überschätzt die tatsächliche Erkennungsquote:** Übersehene Fotos, die niemand ergänzt hat, fehlen im Nenner. Eine Mindestquote gilt nicht.
  - Erkannte Gesichter werden nie von selbst zu gezeigten Gesichtern.

**Anzeigen und korrigieren**

- [ ] In der Detailansicht eines Fotos steht jede festgelegte Person mit ihrem Zustand: „Erkannt“, „Von Hand zugeordnet“ oder „Nicht zugeordnet“. Ein von Hand entfernter Name steht als „Nicht zugeordnet“.
- [ ] Ein Nutzer kann je Foto eine übersehene Person ergänzen und eine falsch zugeordnete entfernen. Die Änderung ist sofort in der Detailansicht sichtbar und beim nächsten Laden in Bildbestand, Filter und Album-Entwurf.
- [ ] Eine Korrektur geht der Erkennung für dieses Foto und diese Person vor.
  - Sie bleibt über beliebig viele weitere Klassifizierungsläufe erhalten, auch wenn inzwischen weitere Gesichter gezeigt wurden.
  - Ein entfernter Name kehrt auf diesem Foto nicht von selbst zurück; ein ergänzter verschwindet nicht von selbst.
- [ ] Korrekturen gelten für beide Nutzer gemeinsam. Beide sehen für ein Foto und eine Person dieselbe Zuordnung, und es gilt die zuletzt vorgenommene Korrektur, gleich von welchem Nutzer.

**Finden**

- [ ] Im Bildbestand eines Projekts und im Album-Entwurf lässt sich die Ansicht auf die Fotos einer Person einschränken, oder – wenn zwei festgelegt sind – auf die Fotos, die beide zeigen.
  - „Alle“ hebt die Einschränkung auf.
  - Im Bildbestand gilt sie zusammen mit dem Bewertungsfilter: Ein Foto muss beide Bedingungen erfüllen.
  - Die Detailansicht blättert innerhalb der eingeschränkten Folge.
- [ ] Die eingeschränkte Ansicht zeigt genau die Fotos, die den Namen tragen, ob erkannt oder von Hand ergänzt; bei „Beide“ genau die Fotos mit beiden Namen. Ein von Hand entfernter Name zählt nicht.
- [ ] Die Einschränkung verändert weder den Album-Entwurf noch den Auswahlvorschlag. Sie blendet nur aus: Der Kopf des Entwurfs zählt weiter den ganzen Entwurf, und nach dem Aufheben ist die Ansicht dieselbe wie vorher.

**Nebenbefund (auf Entscheidung in diese Story aufgenommen)**

- [ ] `onnxruntime`, die Laufzeit des lokalen Textmodells, überträgt keine Telemetrie.
  - Kein Prozess von PhotoSort legt dafür eine Geräte-Kennung oder einen Telemetrie-Zwischenspeicher an.
  - Das gilt auch außerhalb der CI, wo sich die Telemetrie nicht von selbst abschaltet.

## Datenmodell-Bezug

Neu sind vier Tabellen (`persons`, `person_references`, `photo_person_detections`, `photo_person_corrections`) und zwei Zählerspalten an `criterion_scoring_runs`. Form, Kaskaden und Migration stehen im Unterabschnitt „Datenmodell“ unten und in [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Entscheidung:** ADR [`0126`](../decisions/0126-personen-lokal-erkennen-global-festlegen-korrektur-getrennt.md) — Verfahren, Bezug der Gewichte, Telemetrie, Ort der Ausführung, Entscheidungsregel, Abnahme, Datenmodell. ADR 0033 ist damit in ihren Umsetzungspunkten 1–3 abgelöst (Kopfzeile dort). Das System nach der Umsetzung beschreiben `docs/architecture.md` und `docs/setup.md`; beide sind im selben PR schon nachgezogen.

### Ansatz

- **Erkennung lokal mit YuNet und SFace über `cv2`.**
  - Keine neue Python-Abhängigkeit, kein `onnxruntime` im Personenpfad. Das OpenCV-Wheel bringt kein ORT mit.
  - Gewichte unter MIT bzw. Apache-2.0. Sie werden nicht eingecheckt, sondern von fixierten huggingface.co-Revisionen geladen und per SHA256 geprüft.
  - `face_analysis.py` kapselt beide Modelle. Der Adapter bekommt Detektor und Erkenner übergeben und bietet zwei Schritte:
    - `detect(image)`: nur verwertbare Gesichter, höchstens `MAX_FACES_PER_PHOTO = 20` (die größten), geordnet links→rechts, dann oben→unten. Der Index eines Gesichts ist stabil.
    - `embed(image, face)`: das normierte Merkmal.
  - Arbeitsfassung mit langer Kante 1280 px; Ausrichtung immer über `alignCrop`.
- **Wann erkannt wird:** in einer neuen, letzten Phase `persons` des Klassifizierungslaufs, nach `ranking` und vor dem Erfolgsvermerk.
  - Läuft über **alle** Fotos des Projekts, auf der Display-Variante, immer lokal, unabhängig von `use_cloud` und Einwilligung.
  - Schwerpunkte werden einmal je Lauf frisch aus der DB gebildet. Den Namen liest die Phase nie.
  - Bestehende Projekte bekommen ihre Namen mit dem nächsten Klassifizierungslauf.
- **Festlegen einer Person:** Gesichter und Merkmale entstehen auf Anfrage im API-Prozess, auf einem **eigenen Executor mit genau einem Thread** (`run_in_executor`). Der Adapter wird einmal je Prozess träge gebaut. Eine Person entsteht nur zusammen mit ihrer ersten Referenz.
- **„Sicher“** ist eine feste, vorsichtige Regel in `person_matching.py`; die Entscheidungsfunktion bekommt Ähnlichkeiten, keine Merkmale:
  1. Verwertbar ist ein Gesicht erst ab Mindestgröße und Mindest-Detektionswert. Unverwertbare Gesichter werden weder benannt noch mitgezählt, und es entsteht kein Merkmal für sie.
  2. Die Ähnlichkeit wird zum **Schwerpunkt** der Referenzen einer Person gerechnet und muss `ACCEPT_SIMILARITY` erreichen.
  3. Sie muss die Ähnlichkeit zur anderen Person um mindestens `DISTINCT_MARGIN` übertreffen. Mit nur einer festgelegten Person entfällt dieser Abstand.
  4. Eine Person wird nur benannt, wenn genau ein Gesicht ihr Kandidat ist.
  5. Alle Vergleiche stehen in Einschlussform (`>=`): eine NaN-Ähnlichkeit führt nie zu einer Benennung.
  - Die Konstanten sind keine Einstellung. Startwerte: 0.90 / 100 px / 0.50 / 0.10.
  - Nach einer falschen Benennung in der Abnahme wird verschärft und erneut geprüft.
  - Erkannte Gesichter werden nie von selbst zu Referenzen.
- **Datenmodell:** Muster `PhotoMotifCorrection`. Erkennung und Korrektur liegen getrennt am Foto. Die wirksame Zuordnung entsteht nur beim Lesen, Korrektur vor Erkennung.
- **Unbekannte Gesichter:** Für sie wird nichts gespeichert. Gespeichert wird allein das Paar (Foto, Person) eines erkannten Gesichts.
- **`onnxruntime`-Telemetrie aus (S15):** `label_embedding.py` setzt `os.environ["ORT_DISABLE_TELEMETRY"] = "1"` zuweisend, nie über `setdefault`, unmittelbar vor dem ersten `import onnxruntime`.

### Datenmodell

Migration `1f4027405ea5_personen.py`, `down_revision = 2c5472d41548`; Kennung aus `scripts/nummern.py migration personen`. Alle Fremdschlüssel sind echt und benannt.

| Tabelle/Spalte | Inhalt | Löschen |
|---|---|---|
| `persons` | `id`, `slot SMALLINT NOT NULL UNIQUE` + `CHECK (slot IN (1,2))`, `name`, `name_key` (NFC + casefold, `UNIQUE`), `created_at` | `persons.py::delete_person` |
| `person_references` | `id`, `person_id` → `persons`, `embedding` (JSON, 128 Werte, endlich, Norm ≈ 1), `model_key`, `created_at`; **kein** Foto-/Projektbezug; ≤ 20 je Person im aktuellen `model_key`. Die erste Referenz des aktuellen Modells löscht Referenzen anderer `model_key` derselben Person. | mit der Person |
| `photo_person_detections` | PK (`photo_id` → `photos`, `person_id` → `persons`), `computed_at` | mit Foto (ORM-Kaskade), Projekt (`project_deletion.py`), Person |
| `photo_person_corrections` | `id`, `photo_id` → `photos`, `person_id` → `persons`, `user_id` → `users` (Audit), `applies`, `updated_at`, `UNIQUE(photo_id, person_id)` ohne `user_id` | wie oben |
| `criterion_scoring_runs.persons_photos_total` / `persons_photos_processed` | `INT NULL`; `NULL` = die Phase lief nicht (keine Referenz des aktuellen Modells oder Adapter nicht baubar) | — |

`ClassificationPhase.PERSONS = "persons"` wird angehängt. Dafür ist keine Migration nötig: VARCHAR ohne Prüfeinschränkung.

### Betroffene Dateien

**Backend, neu:**
- `model_assets.py`: Manifest mit Dateiname, URL mit fester Revision, Größe und SHA256; nur Konstanten.
- `backend/scripts/fetch_model_assets.py`:
  - nur Standardbibliothek, nur `https` auch bei Umleitungen, Timeout, liest höchstens die Manifestgröße;
  - lädt in eine temporäre Datei, ersetzt per `os.replace` erst nach der Prüfung;
  - sonst Datei löschen und Exit ≠ 0.
- `face_analysis.py`: Protokolle für Detektor und Erkenner, Adapter, `MODEL_KEY`, `build_face_analyzer()`.
- `person_matching.py`, rein:
  - `is_usable`, `centroid`, `validated_embedding` (endlich, 128, Norm);
  - `decide_assignments(similarities)`, `conflicts_with_other_person`;
  - alle Konstanten einschließlich `MAX_FACES_PER_PHOTO`, `MAX_REFERENCES_PER_PERSON`.
- `persons.py`:
  - `effective_person_assignments()` (das eine SQL-Konstrukt);
  - `load_effective_persons`, `create_person` (Slotwahl, `name_key`), `add_reference`, `set_correction`, `delete_person`, `current_centroids`.
- `api/persons.py`, `person_probe.py`.

**Backend, geändert:**
- `models.py`: vier Modelle, zwei Spalten, Relationships an `Photo` mit `cascade="all, delete-orphan"`.
- `worker.py`:
  - `build_face_analyzer` wird durch `run_classification` und `run_criterion_scoring` durchgereicht;
  - `_recognize_persons` läuft zwischen `_build_grouping_and_rankings` und `SUCCESS`;
  - ein FK-Fehler nach einer Personenlöschung verwirft nur den Block.
- `api/projects.py`:
  - `_phase_progress` ordnet `persons` den neuen Zählern zu;
  - `CriterionScoringRunSummary.persons_photos_total/_processed: int | None`.
- `api/photos.py`:
  - `person_id: list[int]` im Listenzweig: Rohzahl ≤ 2, je `ge=1, le=MAX_QUERY_POSITION`, danach dedupliziert, UND-verknüpft;
  - mit `draft=true` → `422`; eine unbekannte Id ergibt eine leere Liste;
  - `PhotoOut.persons: list[{person_id, origin}]` als **pflichtiger Keyword-Parameter** von `_to_photo_out`.
- `main.py`: Router einbinden.
- `project_deletion.py`: zwei Anweisungen.
- `label_embedding.py`: Hash aus dem Manifest, URL mit fester Revision, `ORT_DISABLE_TELEMETRY` (maßgebliche Stelle).
- `backend/tests/conftest.py`: setzt `os.environ["ORT_DISABLE_TELEMETRY"] = "1"` ganz oben, weil `TestRealAssetOutputDimension` `onnxruntime` direkt importiert.
- Infrastruktur:
  - `backend/Dockerfile`: `COPY scripts`, Ladeprogramm statt des eigenen `RUN`, zusätzlich `ENV ORT_DISABLE_TELEMETRY=1` für backend und worker als zweite Absicherung.
  - `.github/workflows/ci.yml`: Cache-Schlüssel `hashFiles('backend/src/photosort/model_assets.py')`, drei Pfade.
  - `.gitignore`.
- `demo_state.py`: zwei erfundene Personen mit synthetischen Einheitsvektoren als Referenz, einige Erkennungen, eine Korrektur, ein Name mit 40 Zeichen.

**Backend, entfällt:** `scripts/fetch-label-embedder-model.sh`.

**Frontend:**
- `api/types.ts`: `PhotoPersonOut {person_id, origin}`, `PersonOut {id, name, reference_count}`, Laufzähler als `number | null`.
- `api/persons.ts`, `hooks/usePersons.ts`.
- `components/PhotoPersonsSection.tsx` in `PhotoDetailPage`:
  - Zeile je Person: zugeordnet bzw. „Nicht zugeordnet“, dazu die Herkunft; Namen aus `GET /persons`;
  - Schalter ergänzen/entfernen; eine Korrektur aktualisiert das Foto im Cache und markiert die Listen nur als veraltet, ohne die aktive Folge sofort neu zu laden;
  - Gesichterwahl als Ausschnitt-Kacheln unter der Bühne; Bilder als Blob-URL, freigegeben beim Zuklappen oder Fotowechsel.
- `pages/PersonsPage.tsx`: Route `/persons`.
- `utils/personFilter.ts`.
- Filter in `PhotoGridPage` (serverseitig), `AlbumDraftPage` (clientseitig) und `PhotoDetailPage` (Blättern).
- `utils/classificationSteps.ts`: neuer Schritt `persons`, ausgeblendet bei beendetem Lauf mit `total === null`.

### API

Der Router trägt `dependencies=[Depends(get_current_user)]` und steht in `test_auth_guard.py`. Alle Eingabeschemata haben `extra="forbid"`.

- `GET /persons`: `[{id, name, reference_count}]`, nach Slot sortiert. Gezählt werden nur Referenzen des aktuellen `model_key`.
- `POST /persons` `{name, photo_id, face_index}` → `201`.
  - `422`: Name ungültig (S4).
  - `409`: schon zwei Personen, doppelter Name (auch über den Constraint), Gesicht an diesem Index fehlt, Merkmal ungültig, Gesicht gleicht der anderen Person.
  - `404`: Foto unbekannt oder Display-Variante fehlt.
- `POST /persons/{id}/references` `{photo_id, face_index}` → `201`. Dieselben Fälle, dazu `409` bei erreichter Obergrenze.
- `DELETE /persons/{id}` → `204`.
- `GET /photos/{id}/faces` → `[{index, box}]`. `404` „Bild wird noch verarbeitet.“, wenn die Display-Variante fehlt; das Modell wird dann nicht aufgerufen.
- `GET /photos/{id}/faces/{index}/image`: JPEG mit `Cache-Control: no-store` und `X-Content-Type-Options: nosniff`. `404` bei fehlender Variante oder Index außerhalb.
- `PUT /photos/{id}/persons/{person_id}` `{applies}` → die wirksame Liste des Fotos.
  - Upsert; `user_id` kommt aus `current_user`.
  - Schreibt kein `FeedbackEvent`.
- Eine Referenz zu zeigen ordnet die Person diesem Foto zugleich per Korrektur `applies=true` zu.

### Invarianten

Die Auswahl der Tests bleibt beim test-engineer.

- Kein Lauf schreibt oder löscht `photo_person_corrections`.
- Die Phase ersetzt Erkennungen nur für Fotos, die sie wirklich verarbeitet hat.
- `person_matching`:
  - Schwellen sind inklusiv;
  - zwei Kandidaten für dieselbe Person → keine Benennung;
  - ein Gesicht nahe an beiden Personen → keine Benennung;
  - NaN → keine Benennung;
  - Referenzen eines fremden `model_key` werden ignoriert.
- Importregeln (ADR 0126 Punkt 1):
  - `face_analysis`, `person_matching` und `model_assets` importieren weder `models` noch `db` noch `config`; ihr vollständiger Importgraph enthält keinen Netzwerk-Client.
  - `persons.py` importiert direkt keinen Netzwerk-Client.
  - Im vollständigen Importgraph der Cloud-Module und von `classification_prompt` kommt keines der Personenmodule vor.
- Die Personendaten erreichen nie `selection.py`, `quality.py`, `ranking.py`, `motifs.py` oder `api/stats.py`.
- Kein Log und keine Antwort enthält Namen (außer `GET /persons`), Merkmale, Schwerpunkte, Ähnlichkeiten oder Boxen unbekannter Gesichter.
- Löschen:
  - nach `delete_person` bleibt keine Zeile mit dieser `person_id`;
  - die Projektlöschung lässt `persons` und `person_references` unberührt.
- Ein Test läuft gegen die echten Assets, nur mit synthetischen Bildern: ein leeres Bild ergibt 0 Gesichter, das Merkmal hat 128 endliche Werte.

### Abnahme

Produktentscheidung Daniel: Abnahme im laufenden Betrieb.

- An einem echten Projekt mit Verwandten und Kindern läuft ein Klassifizierungslauf.
- Daniel sieht je Person die Filteransicht durch und entfernt falsche Namen.
- **Bestanden heißt: kein erkannter Name musste entfernt werden.** Nach einem Fehlgriff werden die Konstanten verschärft, der Lauf wiederholt und erneut geprüft.
- `person_probe --project-id <N>` braucht kein Modell und liest nur die DB. Es zählt je Person (als „Person 1/2“, nach Slot):
  - erkannt;
  - falsch = erkannt + `applies=false`;
  - ergänzt = `applies=true` ohne Erkennung;
  - entfernt und nicht mehr erkannt = `applies=false` ohne Erkennung;
  - Quote = (erkannt − falsch) / (erkannt − falsch + ergänzt). Sie ist eine Obergrenze der tatsächlichen Erkennungsquote: Übersehene Fotos, die niemand ergänzt hat, fehlen im Nenner.
- Die Ausgabe enthält nur Anzahlen, keinen Pfad, keinen Namen und keine Zeile je Foto. Sie geht in den PR-Body.

### Reihenfolge der Umsetzung

1. **Modell-Assets und Telemetrie:**
   - Manifest und Ladeprogramm;
   - `label_embedding.py` mit Hash aus dem Manifest, fester Revision und `ORT_DISABLE_TELEMETRY` vor dem Import;
   - `backend/tests/conftest.py` mit `ORT_DISABLE_TELEMETRY` ganz oben;
   - Dockerfile (inkl. `ENV ORT_DISABLE_TELEMETRY=1`), CI, `.gitignore`; altes Skript entfernen;
   - Integritätstests der Assets; Telemetrie-Test im Subprozess.
2. **`person_matching.py`**, rein.
3. **`face_analysis.py`:** Adapter mit Fake-Detektor und Fake-Erkenner, dann der Echt-Asset-Test mit synthetischem Bild.
4. **Datenmodell, Migration `1f4027405ea5`:**
   - Modelle, Kaskaden, `name_key`, benannte FKs;
   - `project_deletion.py`, `tests/project_graph.py`, Migrationstest.
5. **`persons.py`**.
6. **Worker-Phase `persons`:** Enum, Durchreichen, `_recognize_persons`, Zähler und `last_progress_at` je Block, FK-Fehler je Block.
7. **API:**
   - `api/persons.py` mit dem Ein-Thread-Executor;
   - Filter und `PhotoOut.persons` in `api/photos.py`;
   - Laufzusammenfassung und Restdauer in `api/projects.py`.
8. **`person_probe.py`**, rein lesend.
9. **Frontend:** Typen, API, Hooks, Detailabschnitt, `/persons`, Filter, Teilschritt.
10. **Demo-Bestand und Oberflächenprüfung** im Prüfstack.
11. **Abnahme auf der Zielinstanz vor dem Merge:**
    - Daniel legt beide Personen an;
    - Klassifizierungslauf in einem echten Projekt;
    - Sichtung der Filteransicht je Person, falsche Namen entfernen;
    - `person_probe`;
    - bei falsch > 0: verschärfen, erneut laufen lassen und prüfen, bis falsch = 0;
    - die Ausgabe in den PR-Body und in den Abnahmeabschnitt der Spec.

### Gegenprüfung

- Download beider Modelle von der fixierten Revision: SHA256 stimmt mit dem Manifest.
- OpenCV 5.0.0: `FaceDetectorYN` (2023mar) und `FaceRecognizerSF` (1×128) laufen.
- Kosten: ca. 20 ms Detektion bei 1280 px, ca. 5 ms je Gesicht.
- `cv2.abi3.so` enthält keinen ORT-Bezug.

## UI/UX

Zur Story gibt es keinen `## Design`-Block und keinen Penpot-Entwurf. Maßgeblich sind `specs/architecture/0004-design-system.md` und der Skill `design-system`. Es kommen keine neue Abhängigkeit, kein neues Symbol und kein neues Farbtoken hinzu. Namen sind Fremdtext und werden nur als React-Textknoten gerendert.

### 1. Personenabschnitt in der Detailansicht (`PhotoPersonsSection`)

**Ort:** ein eigener Abschnitt direkt nach der Urteilsfläche und vor dem Einzelwerte-Raster.
- Er liegt nicht in der Urteilsfläche, weil eine Person kein Motiv ist. Er liegt nicht über der Bühne, weil ihre Höhe aus dem Sichtfenster gerechnet ist.
- Auf dem Bild gibt es keine Markierung.
- Form: `section` mit `aria-labelledby`, Panel `rounded-md border border-border bg-surface p-4`.
- Kopfzeile: links ein `h2` „Personen“ in Beschriftungsrolle (`text-xs font-semibold uppercase tracking-wide text-text-h`), rechts „Personen verwalten“ (`Button asChild variant="ghost" size="sm"` → `/persons`).

**Zeilen:** Je festgelegter Person gibt es eine Zeile in einem `ul`, in der Reihenfolge von `GET /persons`. Die Reihenfolge ist auf jedem Foto gleich und wird nie nach Zustand sortiert.
- Links stehen der Name (`text-sm font-medium text-text-h`) und das Zustandswort (`text-sm text-text`): „Erkannt“, „Von Hand zugeordnet“ oder „Nicht zugeordnet“. Die Herkunft ist nur ein Wort: kein Badge, keine Farbe, kein Symbol. `user-round` ist das Motivsymbol „Menschen“.
- Rechts steht eine Schaltfläche `outline size="sm"`: „Entfernen“, wenn die Person zugeordnet ist, sonst „Ergänzen“. `aria-label` „Entfernen: {Name}“ bzw. „Ergänzen: {Name}“. Nie `destructive`, denn auf Foto-Ansichten gilt die Kollisionsregel.
- Jede Person hat einen eigenen Busy-Zustand. Er sperrt nur ihre Zeile.
- Nach der Antwort zeigt die Zeile die gelieferte wirksame Liste.
- **Das aktuelle Foto bleibt stehen**, auch wenn es nach der Korrektur nicht mehr zum aktiven Personenfilter passt. Weiter/Zurück laufen auf der geladenen Folge weiter. Gefilterte Listen werden nur als veraltet markiert und laden beim nächsten Aufruf neu. Sonst stünde mitten in der Korrektur „Foto nicht in der aktuellen Auswahl gefunden.“
- Fehler: ein `Alert` mit wörtlichem `detail` unter den Zeilen, ohne „Erneut versuchen“, denn die Schaltfläche ist die Wiederholung. Bei `404` (Person inzwischen entfernt) wird zusätzlich die Personenliste neu geladen.

**Zustände des Abschnitts:**
- Personen laden: zwei Skeleton-Zeilen in Zeilenhöhe, `role="status"` „Personen werden geladen…“.
- Ladefehler: `Alert` mit „Erneut versuchen“; die Gesichterwahl entfällt.
- Keine Person festgelegt: statt der Zeilen der Satz „Noch keine Person festgelegt.“, darunter die Gesichterwahl. Sie ist der einzige Weg, eine Person festzulegen.

**Gesichterwahl:**
- **Auslöser:** „Gesicht zeigen“ (`secondary size="sm"`, `aria-expanded`/`aria-controls`) unter den Zeilen.
  - Zu Beginn ist sie zugeklappt. Bei jedem Fotowechsel klappt sie zu und setzt sich zurück.
  - `GET /photos/{id}/faces` läuft erst beim Aufklappen, nie beim Blättern.
  - Ausschnitte werden nur als Blob-URL geladen und beim Zuklappen bzw. Fotowechsel freigegeben. Es gibt kein Vorladen.
- **Kacheln:** ein `ul flex flex-wrap gap-3`. Jede Kachel ist ein `button` `size-16 rounded-md border-2` mit einem Bild `object-cover`, `alt=""`, und dem Namen „Gesicht {i} von {n}“.
  - Ruhezustand: `border-border-control`.
  - Gewählt: `border-accent` und `aria-pressed`. Die Auswahl ist eine anliegende Kante, der Fokus bleibt die globale abgesetzte Kontur.
  - Der Ausschnitt wird nie gedämpft.
  - Ein erneuter Druck hebt die Wahl auf, ein Druck auf eine andere Kachel wechselt sie.
- **Nach der Wahl eines Gesichts** erscheint darunter eine `role="group"` mit der sichtbaren Beschriftung „Wer ist das?“ (`text-sm text-text-h`, `aria-labelledby`):
  - Je festgelegte Person eine Schaltfläche `outline size="sm"` mit ihrem Namen (→ `POST /persons/{id}/references`).
  - Bei weniger als zwei Personen zusätzlich ein `<form>` mit dem Feld „Name der neuen Person“ (`label` + `Input`, `autoComplete="off"`) und „Festlegen“ (`default`, → `POST /persons`). Die Schaltfläche ist deaktiviert, solange der getrimmte Name leer ist. Enter sendet ab.
  - Bei zwei Personen gibt es kein Formular. Weitere Namensregeln werden nicht clientseitig gespiegelt, darüber entscheidet die `422`.
  - „Abbrechen“ (`ghost`) klappt zu. Der Fokus geht zurück auf „Gesicht zeigen“.
- **Busy:** Während der Anfrage sind alle Kacheln und Wahl-Schaltflächen gesperrt. Die gedrückte Schaltfläche zeigt „Wird gespeichert…“.
- **Erfolg:**
  - Die Wahl klappt zu, der Fokus geht auf „Gesicht zeigen“.
  - Die Personenliste lädt neu, die Zeile steht auf „Von Hand zugeordnet“.
  - Eine dauerhaft vorhandene Statuszeile (`p role="status" text-sm text-text`, ohne Text ohne Höhe) meldet „Gesicht als {Name} gezeigt.“ bzw. „{Name} ist festgelegt.“
- **Zustände der Gesichterwahl:**
  - Laden: drei Skeleton-Kacheln `size-16`, `role="status"` „Gesichter werden gesucht…“.
  - Leere Liste: „Auf diesem Foto ist kein Gesicht zu finden, das sich zeigen lässt.“ Das ist ein ruhiger Satz ohne `Alert`; „Ergänzen“ bleibt möglich.
  - `404`/`409` beim Abruf der Gesichter (Display-Variante fehlt): „Für dieses Foto gibt es noch keine Vorschau – Gesichter lassen sich erst danach zeigen.“, ebenfalls ohne `Alert`.
  - Sonstige Fehler: `Alert` mit „Erneut versuchen“.
  - Ein einzelner Ausschnitt lädt nicht: Die Kachel bleibt mit Platzhalterfläche `--separator` stehen, `aria-disabled`, Name „Gesicht {i} von {n} – Ausschnitt nicht verfügbar“.
- **`409`/`422` beim Festlegen oder Zeigen:** ein `Alert` mit wörtlichem `detail` direkt über den Wahl-Schaltflächen, ohne „Erneut versuchen“. Die Gesichtswahl bleibt stehen, damit ein anderes Gesicht oder ein anderer Name möglich ist.
  - Doppelter oder ungültiger Name: zusätzlich `aria-invalid` am Namensfeld, die Meldung ist per `aria-describedby` verknüpft.
  - „Schon zwei Personen“: Die Personenliste lädt neu, das Formular verschwindet.
  - „Kein Gesicht an diesem Index“: Die Gesichter laden neu, die Wahl wird aufgehoben.
  - „Gleicht der anderen Person“ und „Obergrenze der Referenzen“: nur die Meldung. Die Obergrenze wird im Frontend nicht gespiegelt.

### 2. Seite `/persons`

**Einstieg:**
- Auf `ProjectListPage` im Kopfbereich eine Schaltfläche „Personen“ (`Button asChild variant="secondary"`), links neben „Neues Projekt anlegen“ und in allen vier Zuständen der Projektliste.
- Außerdem „Personen verwalten“ im Personenabschnitt der Detailansicht.
- Kein Eintrag in der Kopfzeile: Sie hat eine feste Höhe und bricht nicht um. Keine `ProjectNav`.

**Aufbau:**
- `h1` „Personen“ (`text-xl sm:text-2xl`), darunter „Gilt für alle Projekte.“ (`text-sm text-text`).
- Liste `ul flex flex-col gap-3`. Je Person eine Karte `rounded-lg border border-border bg-surface p-4` mit dem Namen als `h2 text-lg` und darunter `text-sm text-text`:
  - „{n}-mal gezeigt“, bei 1 „einmal gezeigt“;
  - bei 0: „Noch kein Gesicht gezeigt – ohne gezeigtes Gesicht wird die Person nicht erkannt.“ Das tritt nach einem Modellwechsel ein.
- Auf der Karte gibt es keine Aktion.

**Zustände:**
- Laden: zwei Skeleton-Karten, `role="status"` „Personen werden geladen…“.
- Fehler: `Alert` mit „Erneut versuchen“.
- Leer, ohne `Alert`: „Noch keine Person festgelegt. Eine Person legst du in der Detailansicht eines Fotos fest, im Abschnitt „Personen“ mit „Gesicht zeigen“.“ Dazu „Zu den Projekten“ (`secondary`).

**Entfernen** nach dem Muster „Harte Bestätigung vor irreversibler Datenlöschung“:
- **Gefahrenzone** am Seitenende, nur wenn mindestens eine Person festgelegt ist:
  - eine `--separator`-Linie, darunter ein Panel `rounded-lg border border-danger bg-surface p-4` mit dem `h2` „Person entfernen“;
  - der Satz „Entfernt den Namen auf allen Fotos in allen Projekten, auch von Hand vorgenommene Zuordnungen, und alle gezeigten Gesichter. Die Fotos und ihre Bewertungen bleiben unverändert.“;
  - je Person eine Schaltfläche `destructive` „{Name} entfernen“ in einem `flex flex-wrap gap-3`.
- **Dialog** nach dem Vorbild von `DeleteProjectDialog`:
  - Titel „Person entfernen?“ ohne `icon`.
  - Text: „{Name} wird auf allen Fotos in allen Projekten entfernt, samt der von Hand vorgenommenen Zuordnungen und aller gezeigten Gesichter. Das lässt sich nicht rückgängig machen.“
  - Tippbestätigung: „Zur Bestätigung den Namen eingeben:“, dazu der Name sichtbar in `font-mono`. Das Feld steht in `font-mono`, Autokorrektur und Großschreibung sind aus, der Vergleich ist exakt. Der Inhalt ist kein `<form>`.
  - Schaltflächen: „Abbrechen“ mit Erstfokus und „Entfernen“ (`destructive`). „Entfernen“ bleibt bis zur Übereinstimmung deaktiviert; während der Anfrage zeigt sie „Wird entfernt…“, `cancelDisabled` ist gesetzt und `onClose` wird ignoriert.
  - Fehler: ein `Alert` über der Schaltflächenzeile, der eingegebene Text bleibt erhalten, die Schaltfläche ist die Wiederholung.
- **Erfolg**, auch bei `404` (die Person war schon entfernt):
  - Der Dialog schließt, die Liste lädt neu.
  - Der Fokus geht auf das `h1`, weil der Auslöser nicht mehr existiert.
  - Die Statuszeile (`role="status"`) meldet „{Name} ist entfernt.“
  - Alle Foto-Listen aller Projekte gelten danach als veraltet.

### 3. Personenfilter

**Gemeinsamer Baustein:**
- Eine `role="group"` mit der sichtbaren Beschriftung „Personen“ (`text-xs font-semibold uppercase tracking-wide text-text-h`, `aria-labelledby`). Ohne die Beschriftung stünden zwei „Alle“ untereinander.
- Einträge: „Alle“, je Person ihr Name, und „Beide“ nur bei zwei Personen (`aria-label` „Beide: {A} und {B}“).
  - Die Einträge sind `Button size="sm"`: der aktive `default` mit `aria-pressed`, die übrigen `outline`. Genau einer ist aktiv.
  - Die Personen stehen in derselben Reihenfolge wie überall.
  - Unter `sm` ist die Gruppe ein eigener waagerechter Scrollbereich wie der Bewertungsfilter. Namen werden nie gekürzt.
- Die Gruppe erscheint erst, wenn die Personen geladen sind und mindestens eine festgelegt ist. Bei einem Ladefehler steht an ihrer Stelle ein `Alert` „Die Personen konnten nicht geladen werden.“ mit „Erneut versuchen“.
- Adresse: `?person=<id>`, einmal oder zweimal. Eine unbekannte Id wird nach dem Laden der Personen per `replace` aus der Adresse entfernt.

**Bildbestand:**
- Die Gruppe ist eine zweite Zeile unter dem Bewertungsfilter. Beide Filter gelten zusammen (UND).
- Der Leerzustand bleibt „Keine Fotos mit diesem Filter.“ „Filter zurücksetzen“ erscheint, sobald einer der beiden Filter aktiv ist, und hebt beide auf.
- Die Kachel-Links und „Zurück zum Grid“ tragen `person` mit. Die Detailansicht blättert in der gefilterten Folge, ihr Zähler bezieht sich auf diese Folge.

**Album-Entwurf** (nur clientseitig):
- Die Gruppe steht zwischen Kopf und „Alle Tage auf-/zuklappen“, nur wenn der Entwurf Fotos hat.
- Der Kopf mit Richtwert und Ist-Zahl zählt immer den ganzen Entwurf.
- Bei aktivem Filter:
  - Eine Statuszeile (`p role="status" text-sm text-text`) meldet „{n} von {m} Fotos des Entwurfs sichtbar.“
  - Tage und Eventgruppen ohne sichtbares Foto entfallen. Dort steht nicht „Kein Bild im Entwurf“, weil das eine falsche Aussage wäre.
  - Die Gruppenzahlen und die Motivzeile beziehen sich auf die sichtbaren Fotos. Auf- und Zuklappen wirkt auf die sichtbaren Tage.
  - Leer: „Keine Fotos des Entwurfs mit diesem Filter.“ und „Filter zurücksetzen“ (`outline`).
- Der Alternativen-Dialog bleibt ungefiltert.
- Fällt das eingetauschte Foto aus dem Filter, geht der Fokus auf das `h1`, und die Statuszeile meldet „Das eingetauschte Foto ist durch den Filter ausgeblendet.“

### 4. Laufanzeige

„Personen-Erkennung“ ist der letzte Eintrag in `ClassificationProgress`, in derselben Zeilenform wie die anderen lokalen Schritte:
- Zustandswort, `{x}/{y}`, bestimmter Balken und Restdauerzeile; kein Cloud-Detail.
- Keine Namen und keine Trefferzahl.
- Vor der Phase steht der Schritt auf „ausstehend“. Das gilt auch, wenn die Phase mangels Person gar nicht läuft.
- Nach Laufende mit `total === null` wird der Schritt nicht gezeigt.

### Design-System ergänzen (im Umsetzungs-PR, in `0004` und im Skill `design-system`)

1. **Gesichtsausschnitt-Kachel:**
   - Sie ist eine wählbare Bildkachel mit sichtbaren 64 px (keine Aufspannung) und `gap-3`.
   - Die Auswahl zeigt sie über die anliegende Akzentkante und `aria-pressed`. Das Bild wird nicht gedämpft.
   - Der Ausschnitt wird nur auf Anforderung geladen, als Blob, und beim Schließen freigegeben.
   - Von Hand ins Penpot-Bausteinregister übernehmen.
2. **Beschriftete Filtergruppe:**
   - Sie ist eine zweite Filterdimension auf einer Ansicht und trägt eine sichtbare Beschriftung.
   - Jede Gruppe hat ihr eigenes „Alle“, und beide Gruppen gelten zusammen (UND).
   - Ein „Filter zurücksetzen“ hebt alle auf.
3. **Gefahrenzone mit mehreren Objekten:** eine Zone und darin je Objekt eine `destructive`-Schaltfläche „{Name} entfernen“. Getippt wird der Name des Objekts.
4. **Zuordnung mit Herkunft:** Die Herkunft („Erkannt“/„Von Hand zugeordnet“) ist ein Wort. Nie Badge, Farbe oder Symbol.

## Security

**Einstufung:** Das Feature ist sicherheitsrelevant, aber kein Blocker. Neu sind:

- eine neue Datenklasse, die biometrischen Referenzmerkmale;
- sieben Endpunkte mit Freitext- und Id-Eingaben, davon zwei mit einem Modelllauf je Aufruf;
- ein gemeinsamer Bezugsweg für Modelldateien.

Es gibt kein neues Secret, keinen neuen Empfänger und keinen externen Dienst zur Laufzeit. Die projektweiten Aussagen stehen in `specs/architecture/0003-securitykonzept.md`: im Asset „Biometrische Referenzmerkmale“, im Abschnitt „Personen auf Fotos erkennen“ und in der bekannten Lücke „onnxruntime-Telemetrie“.

**Bedrohungen**

- **B1:** Referenzmerkmale fließen ab, etwa über einen Datenbankauszug, das Log oder die API. Wer sie zusammen mit dem öffentlichen Modell hat, findet beide Nutzer in jedem fremden Bildbestand wieder.
- **B2:** Personendaten erreichen einen Cloud-Anbieter, zum Beispiel ein Name im Prompt oder ein Merkmal in einer Nutzlast. Das ist auch mit Einwilligung ausgeschlossen.
- **B3:** Dritte (Kinder, Verwandte) werden wiedererkennbar, weil Boxen oder Merkmale unbekannter Gesichter gespeichert werden.
- **B4:** Falsche Benennungen durch eine untergeschobene Referenz (gestohlenes JWT) oder eine entartete Referenz (NaN, Nullvektor).
- **B5:** Die Löschung bleibt unvollständig: Zwischenspeicher im Prozess, verwaiste Zeilen, Browser-Cache.
- **B6:** Die API wird über die Gesichts-Endpunkte ausgelastet.
- **B7:** Eine manipulierte Modelldatei kommt in die Lieferkette, oder ein Modell wird zur Laufzeit nachgeladen.
- **B8:** Ein Name manipuliert Anzeige oder Bedienung (Bidi-Zeichen, unsichtbare Zeichen, XSS).
- **B9:** Personendaten gelangen in öffentliche Artefakte: PR-Body, Repository, CI-Traces.
- **B10:** Nebenbefund: `onnxruntime` sendet Telemetrie an Microsoft.

**Auflagen.** **Muss** ist eine Abnahmebedingung. **Soll** ist empfohlen; eine Abweichung wird im PR begründet.

- **S1 – Muss – Auth an jedem neuen Endpunkt.**
  - `persons.router` trägt `dependencies=[Depends(get_current_user)]`. Das gilt für alle sieben Endpunkte, auch `GET /photos/{id}/faces`, `…/faces/{index}/image` und `PUT /photos/{id}/persons/{person_id}`.
  - Der Router steht in `test_auth_guard.py::_protected_router_operations()` und in der Torwächter-Zeile der Ankerliste in 0003.
  - Der neue Filter `person_id` in `GET /projects/{id}/photos` behält die ausgeschriebene Auth-Dependency.
  - Nachweis: der Vollständigkeitstest, dazu je ein 401-Fall für den Bild-Endpunkt und die beiden schreibenden Personen-Endpunkte.
- **S2 – Muss – Gemeinsame Sichtbarkeit, keine nutzergebundene Aufsuche.**
  - Personen und Korrekturen gelten für beide Nutzer. Das ist konsistent mit dem Bedrohungsmodell: Es gibt kein Innentäter-Modell.
  - `photo_person_corrections.user_id` kommt ausschließlich aus `current_user.id`. Er ist ein Auditfeld und nie Aufsuch- oder Zugriffsschlüssel. Die Aufsuche läuft über `(photo_id, person_id)`, dasselbe Muster wie bei den Motivkorrekturen.
  - Alle Eingabeschemata haben `extra="forbid"` und genau die genannten Felder: `{name, photo_id, face_index}`, `{photo_id, face_index}`, `{applies}`.
  - Ein `IntegrityError` wird `409`, nie `500`. Das gilt für den Slot-Konflikt, den Namenskonflikt und das Upsert der Korrektur.
  - Die Antworten tragen keine `user_id`.
  - Nachweis: Ein eingeschmuggeltes `user_id` wird abgewiesen. Der PUT des zweiten Nutzers überschreibt die Zeile des ersten. Ein gleichzeitiges Anlegen ergibt `409`.
- **S3 – Muss – Begrenzte Eingaben.**
  - Alle Ids haben `ge=1, le=MAX_QUERY_POSITION`.
  - `face_index` hat `ge=0, lt=MAX_FACES_PER_PHOTO`.
  - `person_id` im Listenfilter: höchstens 2 Werte. Zusammen mit `draft=true` ergibt das `422`.
  - Ein Wert außerhalb dieser Grenzen ergibt `422`, nie `500`.
  - Nachweis: Grenzfälle je Parameter.
- **S4 – Muss – Name.**
  - An der API-Grenze gilt Pydantic `max_length=200`, vor jeder weiteren Verarbeitung.
  - Danach NFC, trimmen und 1–40 Codepunkte.
  - **Abgewiesen** wird mit `422`, nicht bereinigt: jedes Zeichen der Kategorien `Cc`, `Cf`, `Cs`, `Co`, `Cn`, `Zl`, `Zp` und jeder Leerraum außer U+0020.
  - Ein doppelter Name (Vergleich nach `casefold`) ergibt `409`.
  - Warum abweisen statt entfernen: Der Entfernen-Dialog verlangt den Namen exakt getippt. Ein unsichtbares Zeichen machte die Person über die Oberfläche unlöschbar, und ein Bidi-Override dreht die Anzeige.
  - Im Frontend erscheint der Name nur als React-Textknoten. Er landet nie in `href`, `src`, `style` oder `dangerouslySetInnerHTML`.
  - Der Name steht nie in einem URL-Pfad oder Query-Parameter; gefiltert wird über die Id.
  - Nachweis: eine Tabelle der abgewiesenen Zeichen, darunter U+202E, U+200B, U+0000, U+2028 und ein Tabulator; die Längengrenzen beidseitig nach NFC; der `casefold`-Konflikt.
- **S5 – Muss – Nichts über unbekannte Gesichter, keine Merkmale nach außen.**
  - Die Spaltensätze sind per Test auf Gleichheit festgehalten:
    - `photo_person_detections`: nur `photo_id`, `person_id`, `computed_at`.
    - `photo_person_corrections`: nur die Felder aus dem Datenmodell.
  - `PersonReference` wird genau an einer Stelle geschrieben (`persons.py`), und zwar nur aus den beiden Referenz-Endpunkten.
  - Kein Antwortschema trägt Merkmal, Schwerpunkt oder Ähnlichkeit:
    - `/faces` liefert nur `{index, box}`.
    - `GET /persons` liefert nur `{id, name, reference_count}`.
    - `PhotoOut.persons` liefert nur `{person_id, origin}`.
  - Nachweis:
    - ein Lauf über ein Foto mit einem erkannten und zwei unbekannten Gesichtern: danach genau eine neue Zeile, sonst keine;
    - die Feldmengen der Schemata auf Gleichheit.
- **S6 – Muss – Erkennung nur lokal, auch mit Cloud-Einwilligung.**
  - Es gilt der Import-Graph-Wächter in beide Richtungen (ADR 0126 Punkt 1).
  - Zusätzlich, weil `worker.py` beide Seiten importiert: Die Phase `persons` liest nur Id und Schwerpunkt über `current_centroids`, nie `Person.name`.
  - `face_analysis.py` kennt nur Dateinamen aus dem Manifest, keine URL. Kein Anwendungsmodul importiert das Ladeprogramm.
  - Kein Cloud-Prompt wird für Personen geändert.
  - Nachweis: ein Klassifizierungslauf mit `use_cloud=True`, Einwilligung und zwei festgelegten Personen, mit Fake-Clients für beide Cloud-Pfade, die jeden Anfragekörper aufzeichnen:
    - Keiner der beiden Namen und kein Merkmalswert kommt in einer Nutzlast vor.
    - Die Menge der Cloud-Aufrufe gleicht der desselben Laufs ohne Personen.
- **S7 – Muss – CPU-Grenzen der Gesichts-Endpunkte.**
  - Die Modellaufrufe des API-Prozesses laufen auf einem **eigenen Executor mit genau einem Thread**, awaited über `run_in_executor`. So sind sie serialisiert, ohne auf eine Sperre im gemeinsamen Threadpool zu warten. Wartende Anfragen belegen damit keinen Platz, den Bild- und Dateiantworten anderer Endpunkte brauchen.
  - Je Foto werden höchstens `MAX_FACES_PER_PHOTO = 20` Gesichter gelistet und adressiert. Die Grenze greift nach dem Verwertbarkeitsfilter, danach gilt die deterministische Sortierung.
  - Gelesen wird ausschließlich die lokale `display`-Variante über `thumbnails.variant_path`. Nie das Original, nie ein Abruf von OpenCloud im Anfragepfad, nie ein Pfad aus der Anfrage.
  - Fehlt die Variante, antwortet der Endpunkt mit `404` „Bild wird noch verarbeitet.“, **ohne** das Modell aufzurufen.
  - Die Box wird vor dem Zuschneiden auf die Bildgrenzen geklemmt.
  - Es gibt kein eigenes Rate-Limit: Ein gestohlenes JWT gewinnt damit nichts Neues.
  - Nachweis:
    - Obergrenze der Gesichter;
    - fehlende Variante ergibt null Aufrufe des Fake-Analyzers;
    - der Executor hat einen Thread (Beobachtung über den Fake).
- **S8 – Muss – Gesichtsausschnitt.**
  - Der Ausschnitt ist ein neu codiertes JPEG mit `Cache-Control: no-store` und `X-Content-Type-Options: nosniff`.
  - Im Frontend wird er nur als Blob-URL geladen und beim Zuklappen bzw. beim Fotowechsel freigegeben.
  - Nachweis: die Header im API-Test.
- **S9 – Muss – Integrität der Referenzen und Regel.**
  - Ein Merkmal wird nur gespeichert, wenn alle 128 Werte endlich sind und die Norm im Toleranzband um 1 liegt. Die Prüfung steht in Einschlussform. Sonst `409` ohne Schreiben.
  - Alle Vergleiche in `person_matching.py` stehen in Einschlussform (`sim >= ACCEPT_SIMILARITY`, `sim_a - sim_b >= DISTINCT_MARGIN`). Ein NaN fällt damit auf „nicht benannt“, nie auf „benannt“.
  - Nachweis: NaN-, Inf- und Nullvektor werden als Referenz abgewiesen; eine NaN-Ähnlichkeit ergibt keine Benennung.
- **S10 – Muss – Löschen.**
  - `delete_person` löscht in **einer** Transaktion Korrekturen, Erkennungen, Referenzen und die Person.
  - Auf `person_id` liegen echte Fremdschlüssel in allen drei Tabellen. Ein Schreiben der Phase nach der Löschung scheitert dadurch; die Phase behandelt den Fehler je Batch als „übersprungen“, und alte Zeilen bleiben stehen.
  - Schwerpunkte werden je Lauf bzw. Anfrage frisch aus der Datenbank gebildet und nie darüber hinaus zwischengespeichert.
  - `project_deletion.py` führt beide Foto-Tabellen, und `tests/project_graph.py::build_project_graph` legt in beiden eine Zeile an. Ohne diese Zeilen prüfen die Vollständigkeitstests die neuen Kanten nicht.
  - Nachweis:
    - nach `delete_person` bleibt keine Zeile mit dieser `person_id`;
    - die Projektlöschung lässt `persons` und `person_references` unberührt;
    - Löschen, dann eine neue Person, dann eine Referenz: die alte Person wird nicht mehr erkannt.
  - Außerhalb der Anwendung, bewusst und im Konzept vermerkt: Datenbanksicherungen bis zu ihrer Rotation und nicht überschriebene PostgreSQL-Seiten bis `VACUUM`.
- **S11 – Muss – Log-Hygiene.**
  - Keine Logzeile, kein Fehlertext, kein arq-Job-Argument und keine `photo_cloud_vision_errors`-Zeile trägt einen Namen, ein Merkmal, einen Schwerpunkt, eine Ähnlichkeit oder eine Box.
  - Die Phase loggt nur Anzahlen, feste Grund-Token und `photo_id`. Ausnahmen je Foto erscheinen als `type(exc).__name__`.
  - Nachweis: Lauf und Anlegen mit einprägsamen Namen und Merkmalswerten; `caplog` enthält keinen davon.
- **S12 – Muss – Messkommando `person_probe`.**
  - Das Kommando ist rein lesend und gibt nur auf stdout aus, als Markdown mit ausschließlich Anzahlen. Personen erscheinen als „Person 1/2“, ohne Namen, Pfad oder Zeile je Foto. Es gibt keinen Schalter, der Namen ergänzt, und keine Datei-Ausgabe.
  - Es ist von keinem automatischen Pfad aus erreichbar: kein Import aus `main.py` oder `worker.py`, kein Endpunkt, kein Compose-`command`.
  - Muster ist die Ankerzeile von `criterion_probe` in 0003. Die Ausgabe geht in einen öffentlichen PR.
  - Nachweis: dieselben Wächterklassen wie `test_criterion_probe.py`.
- **S13 – Muss – Modell-Download über das Manifest.**
  - Hashes und URLs stehen ausschließlich als Konstanten in `model_assets.py`. Keine Umgebungsvariable, kein Build-Argument und kein Schalter überschreibt sie.
  - Die URLs sind `https://` mit fester Revision.
  - Heruntergeladen wird in eine temporäre Datei im Zielverzeichnis; erst nach bestandener SHA256-Prüfung folgt `os.replace` an den Zielpfad. Bei Abweichung wird gelöscht und mit Exit ≠ 0 abgebrochen, ohne Fallback.
  - Der CI-Cache schlüsselt über den Inhalt des Manifests.
  - `face_analysis.py` und `label_embedding.py` laden nie selbst.
  - Soll:
    - eine Umleitung auf ein anderes Schema als `https` abweisen;
    - höchstens die im Manifest genannte Größe lesen;
    - einen Timeout setzen;
    - auch den Label-Embedder auf eine feste Revision statt `resolve/main` setzen (Verfügbarkeit, nicht Integrität).
  - Nachweis: Integritätstest der Assets gegen das Manifest; das Ladeprogramm mit falschem Hash hinterlässt keine Datei am Zielpfad und endet mit Exit ≠ 0.
- **S14 – Muss – Keine echten Gesichter in Repository, Tests, Demo und CI.**
  - Die Demo-Personen tragen erfundene Namen. Ihre Referenzen sind synthetische Einheitsvektoren und stammen nie aus einem Gesicht.
  - Kein Foto einer realen Person liegt im Repository oder in Test-Fixtures, auch kein Bild aus einem öffentlichen Datensatz.
  - Die echten Modelle laufen in keinem Test außer dem markierten Echt-Asset-Test, und der nur mit synthetischen Bildern.
  - Playwright-Traces sind öffentlich; sie zeigen nur den Demo-Bestand.
- **S15 – Muss – onnxruntime-Telemetrie aus (Nebenbefund, von Daniel dieser Story zugeordnet).**
  - `os.environ["ORT_DISABLE_TELEMETRY"] = "1"` wird **vor dem ersten** `import onnxruntime` gesetzt, heute in `label_embedding.py::build_label_embedder()` unmittelbar vor dem lokalen Import. Es ist kein `setdefault`, damit niemand die Telemetrie wieder einschalten kann.
  - `onnxruntime.disable_telemetry_events()` reicht nicht: Es lässt den Upload-Dienst laufen.
  - Nachweis: ein Subprozess mit minimaler Umgebung (ohne `CI`, eigenes `HOME` und `XDG_CACHE_HOME` in `tmp_path`) ruft `build_label_embedder()` auf. Danach existiert `…/Microsoft/DeveloperTools/.onnxruntime/` nicht. In CI zeigt sich der Fehler sonst nie, weil das SDK sich bei gesetztem `CI` selbst abschaltet.

**Restrisiken (akzeptiert, im Konzept vermerkt)**

- Ein gestohlenes JWT kann Personen lesen, anlegen, entfernen und Referenzen unterschieben. Das ist keine neue Fähigkeit: Das Token erlaubt schon heute, Projekte zu löschen.
- Merkmale aller Gesichter eines Fotos, auch von Dritten, entstehen während der Verarbeitung kurz im Speicher. Gespeichert wird davon nichts.
- Mit Cloud-Einwilligung geht die `display`-Variante wie bisher an den Anbieter, einschließlich der Gesichter darauf. Die Zusage „nur lokal“ betrifft die Erkennung und die Personendaten.

## Teststrategie

Grundlage ist das Testkonzept 0002, Sektion „Biometrische Merkmale ohne echtes Modell …“. Dazu kommen die bestehenden Muster zu Lesepfad-Wirksamkeit (Motivkorrektur), Messkommando, Projektlöschung, Import-Graph und Fremdschlüssel-Durchsetzung. Die Pflichtfälle unten sind namentlich verbindlich und werden nie aus der Coverage-Zahl abgeleitet.

### Gesichtserkennung ohne echtes Modell

- **Sperre:** Eine `autouse`-Fixture lässt `cv2.FaceDetectorYN.create`, `cv2.FaceRecognizerSF.create`, `cv2.FaceDetectorYN_create` und `cv2.FaceRecognizerSF_create` einen Fehler erheben. Ausgenommen ist allein die markierte Klasse gegen die echten Assets (unten). `build_face_analyzer()` läuft in keinem Test.
- **Fake-Analyzer** (Hilfsmodul unter `backend/tests/`, kein `test_*`) erfüllt `FaceAnalyzerLike`:
  - erkennt das Bild an einer eindeutigen Vollfarbe der geschriebenen Display-Variante; so läuft der echte Lesepfad mit;
  - liefert nur verwertbare Gesichter mit Box und einem Merkmal aus Basisvektoren (Kosinus exakt 1 oder 0), dazu eine einprägsame Sentinel-Komponente;
  - kann die Reihenfolge je Aufruf vertauschen, bei einem bestimmten Bild werfen, über einen Haken eine Person mitten im Lauf löschen und Aufrufe samt Thread-Namen zählen.
- **Worker:** bekommt `build_face_analyzer=lambda: fake`.
- **API-Prozess:** bekommt den Analyzer über eine überschreibbare Dependency.
- **Adapter in `face_analysis.py`:** wird gegen Attrappen seiner übergebenen Detektor- und Erkennerprotokolle geprüft:
  - Arbeitsfassung höchstens `ANALYSIS_MAX_SIDE`, nie vergrößert;
  - Box auf das Bild normiert und an die Bildgrenzen geklemmt;
  - Merkmal L2-normiert;
  - die volle Detektionszeile samt Landmarken geht an die Ausrichtung.
- **Echte Assets (eine markierte Klasse, nur synthetische Bilder, kein echtes Gesicht):**
  - Der Adapter mit echtem YuNet/SFace liefert auf einem leeren Bild null Gesichter.
  - Eine von Hand gesetzte Detektionszeile auf einem synthetischen Bild ergibt über `alignCrop`/`feature` 128 endliche Werte mit Norm 1.
- **Schwellen:** Die Grenzfälle laufen auf Ähnlichkeitsebene mit binär exakten Konstanten (autouse-Parametrierung). Die kalibrierten Werte stehen genau einmal als Literal im Test. Integrationslagen bauen Merkmale fern jeder Schwelle.

### Ebene je Kriterium

| Kriterium | Ebene | Ort |
|---|---|---|
| Höchstens zwei | Integration API, Migration | `test_api_persons.py`, `test_migration_personen.py` |
| Festlegen ohne Zahl | API-Schema, Struktur, vitest | `test_api_persons.py`, `test_person_matching.py`, `PhotoPersonsSection.test.tsx` |
| Gilt für alle Projekte | Integration Worker | `test_worker_persons.py` |
| Person entfernen | Integration, vitest | `test_persons.py`, `test_api_persons.py`, `PersonsPage.test.tsx` |
| Projekt löschen | Integration | `project_graph.py`, `test_project_deletion.py` |
| Sicher → Name, nicht sicher, 1:1 | Unit + Integration Worker | `test_person_matching.py`, `test_face_analysis.py`, `test_worker_persons.py` |
| Nichts über Unbekannte | Integration (Zwilling + Sentinel), Schema | `test_worker_persons.py`, `test_api_persons.py`, `test_models.py` |
| Nur lokal | Struktur + Integration | Import-Graph-Wächter, `test_worker_persons.py` |
| Kein Motiv | Integration (Zwilling) | `test_worker_persons.py` |
| Bestehende Projekte | Integration, Migration, vitest | `test_worker_persons.py`, `classificationSteps.test.ts` |
| Abnahme | Messkommando + manuell im Betrieb | `test_person_probe.py`, Abschnitt „Abnahme“ |
| Anzeige, Ergänzen/Entfernen | API + vitest | `test_api_persons.py`, `PhotoPersonsSection.test.tsx` |
| Vorrang, gemeinsam | Integration Worker + API | `test_worker_persons.py`, `test_api_persons.py` |
| Finden, genau, blendet nur aus | API + vitest (+ e2e) | `test_api_photos.py`, `personFilter.test.ts`, Seiten-Tests |
| Telemetrie aus | Unterprozess + Struktur | `test_label_embedding.py` |

### Backend – Unit

**`test_person_matching.py`**

- **Schwerpunkt:**
  - Verglichen wird mit dem Schwerpunkt der Referenzen, nicht mit dem ähnlichsten Einzelmerkmal. Lage: eine Referenz gleich dem Gesicht, zwei orthogonal → kein Kandidat.
  - Das Ergebnis hängt nicht von der Länge der Vektoren ab.
  - Bei einer einzigen Referenz ist der Schwerpunkt diese Referenz.
  - Referenzen mit fremdem `model_key` fließen nicht ein.
  - Eine Person ohne gültige Referenz ist nie Kandidat.
- **Annahme und Abstand:**
  - Beide Schwellen sind inklusiv, genau auf der Schwelle gilt als erreicht.
  - Ist ein Gesicht beiden Personen gleich ähnlich, bekommt es keine.
  - Gibt es nur eine Person, gilt nur die Annahmeschwelle (festgehaltenes Verhalten).
  - Eine NaN-Ähnlichkeit ergibt keine Benennung (Einschlussform).
- **1:1:**
  - Zwei Kandidaten für P → P wird nicht benannt, Q über ein drittes Gesicht trotzdem.
  - Ein Gesicht wird nie beiden Personen zugeordnet.
  - Je ein Kandidat für P und Q → beide Namen.
  - Null Gesichter → kein Name.
  - Vertauschte Reihenfolge von Gesichtern und Referenzen ergibt dasselbe.
- **Nicht-Monotonie:** Dieselben Ähnlichkeiten ergeben bei der Startschwelle zwei Kandidaten (kein Name) und bei einer höheren Annahmeschwelle einen Kandidaten (Name). Das belegt, dass eine Verschärfung neue Namen erzeugen kann.
- **Gezeigtes Gesicht abweisen (ADR 0126, Regel 5):** Ähnlichkeit zum Schwerpunkt der anderen Person genau auf der Annahmeschwelle → abgelehnt.
- **Merkmalsprüfung (S9):** NaN, Inf, Nullvektor und eine Norm außerhalb des Toleranzbands werden abgewiesen.
- **Konstanten:** ein Literal-Fall; ein Syntaxbaum-Wächter stellt sicher, dass sie nur in `person_matching.py` zugewiesen werden und das Modul weder Umgebung noch `settings` liest.

**`test_face_analysis.py`**

- **Verwertbarkeit:**
  - Detektionswert genau `MIN_DETECTION_SCORE` ist verwertbar, knapp darunter nicht.
  - Kürzere Seite genau `MIN_FACE_SIDE_PX` ist verwertbar, knapp darunter nicht.
  - Maßgeblich ist die kürzere Seite in der Arbeitsfassung.
- **Obergrenze `MAX_FACES_PER_PHOTO`:**
  - greift nach dem Verwertbarkeitsfilter; 25 verwertbare Gesichter ergeben die 20 größten;
  - 25 Gesichter, davon die 10 größten unverwertbar, ergeben die 15 verwertbaren.
- **Reihenfolge:**
  - links nach rechts, dann oben nach unten;
  - die Sortierung ist total (zwei Gesichter gleicher Position);
  - eine vertauschte Ausgabe des Detektors ergibt dieselbe Liste.

### Backend – Integration

**Worker (`test_worker_persons.py`)**

- **Reihenfolge:** Phase `persons` nach `ranking`, vor `SUCCESS`; `assert_phase_binding` gilt.
- **Umfang:** alle Fotos, auch der Ausschuss.
- **Fortschritt:** Zähler total/processed und `last_progress_at` je Batch (Batchgröße per `monkeypatch` klein).
- **Phase läuft nicht:**
  - ohne Person;
  - nur mit Referenzen fremden `model_key`;
  - bei gescheitertem Builder.

  Dann ist `SUCCESS`, ein explodierender Analyzer wird nie gerufen, die Zähler bleiben `NULL`, und alte Erkennungen bleiben stehen.
- **Nur verarbeitete Fotos werden ersetzt**, als Zwilling im selben Lauf:
  - Foto A wurde verarbeitet und hat jetzt keinen Kandidaten → seine Zeile verschwindet.
  - Foto B hat keinen Cache oder der Analyzer wirft → seine Zeile bleibt.
- **Person mitten im Lauf gelöscht** (Haken im Fake, Fremdschlüssel durchgesetzt):
  - Der Lauf endet mit `SUCCESS`.
  - Keine Zeile trägt die gelöschte `person_id`.
  - Die übrigen Batches sind geschrieben.
- **Korrekturen:**
  - Schnappschuss von `photo_person_corrections` (samt `user_id`, `updated_at`) ist vor und nach zwei Läufen gleich.
  - Wächter: `worker.py` enthält keine Schreibform auf diese Tabelle.
- **Vorrang über Läufe:**
  - `applies=false` plus erneute Erkennung → wirksam nicht zugeordnet.
  - `applies=true` ohne Erkennung → wirksam „von Hand“.
  - Beides unverändert nach einer neuen Referenz und einem weiteren Lauf.
- **Unbekannte:**
  - Zwillingslauf (drei unbekannte Gesichter gegen kein Gesicht) → Schnappschuss aller Tabellen gleich.
  - Die Sentinel-Komponente taucht nirgends auf (Tabellen außer `person_references`, `caplog`).
  - Gegenprobe: Nach einem gezeigten Gesicht steht sie in `person_references`.
- **Lokal:**
  - `use_cloud=True` mit Einwilligung und aufzeichnenden Doubles beider Cloud-Pfade: Zahl und Inhalt der Anfragen mit und ohne Personen gleich.
  - Weder Name noch Sentinel in einer Nutzlast.
  - Die Phase läuft auch mit `use_cloud=False`.
- **Kein Motiv:** Zwillingslauf mit und ohne erkannte Personen → Motivstärken, Rangfolge/Auswahl und `GET …/stats` identisch.
- **Bestand:** erster Lauf ohne Person, dann Person anlegen, zweiter Lauf → Namen.
- **Global:** Referenz aus Projekt A, Lauf in Projekt B.
- **Scan:** Ein verschwundenes Foto nimmt Erkennung und Korrektur mit (Kaskade).
- **Log (S11):** Lauf mit einprägsamen Namen und Merkmalswerten; `caplog` enthält keinen davon.

**Wirksame Zuordnung und Personen (`test_persons.py`)**

- **Matrix:** Erkennung {nein, ja} × Korrektur {keine, `applies=true`, `applies=false`} ergibt {—, von Hand, —, erkannt, von Hand, —}.
- **Quelltext-Wächter:** genau eine Stelle im Lesepfad nennt die Korrekturspalte.
- **`delete_person`:** Danach hat keine der drei Tabellen eine Zeile mit dieser `person_id`; die andere Person bleibt unverändert (Zwilling).
- **Löschen und neu anlegen:** Löschen, eine neue Person anlegen, eine Referenz zeigen → die alte Person wird nicht mehr erkannt.
- **Modellwechsel:**
  - Eine Person mit 20 Referenzen eines alten `model_key` bekommt eine Referenz des aktuellen Modells.
  - In derselben Transaktion sind die alten gelöscht, der Zähler steht auf 1.
  - Vorher zählt `reference_count` 0.
- **Obergrenze:** Das 20. gezeigte Gesicht des aktuellen Modells geht, das 21. wird abgewiesen, gleich wie viele Referenzen fremden `model_key` es gibt.
- **Speicherstelle:** `PersonReference` wird genau an einer Stelle in `persons.py` geschrieben (Wächter).

**API (`test_api_persons.py`, `test_api_photos.py`)**

- **`POST /persons`:**
  - Person und erste Referenz entstehen atomar; nach einem abgewiesenen Gesicht bleibt keine Person übrig.
  - `409` bei: dritter Person, gleichzeitigem Slot-Konflikt, doppeltem Namen, Gesicht jenseits der Liste, Gleichheit mit der anderen Person.
  - Nachweis für den Slot- und den Namenskonflikt: die Vorabprüfung per `monkeypatch` umgehen, damit der Unique-Constraint auf `slot` bzw. `name_key` greift → `409`, nie `500`.
  - Doppelter Name über `name_key` (NFC + casefold): „Anna“/„ANNA“, „Straße“/„STRASSE“, „é“ zusammengesetzt/zerlegt.
  - `422` bei:
    - leerem Namen oder nur Leerraum;
    - 41 Codepunkten nach NFC (40 ist erlaubt);
    - über 200 Zeichen vor jeder Normalisierung;
    - Zeichen der Tabelle aus S4: U+202E, U+200B, U+0000, U+2028, Tabulator und je Kategorie `Cc`/`Cf`/`Zl`/`Zp`;
    - eingeschmuggeltem `user_id` oder anderem Zusatzfeld;
    - `face_index` < 0 oder ≥ 20.
  - Fehlt die Display-Variante: `404` „Bild wird noch verarbeitet.“, null Aufrufe des Analyzers.
- **`POST …/references`:**
  - dieselben Fälle wie oben, dazu die Obergrenze;
  - schreibt eine Korrektur `applies=true` für dieses Foto;
  - kein `FeedbackEvent`; Gegenprobe: eine Motivkorrektur im selben Aufbau schreibt eines.
- **Stabiler Gesichtsindex:** Der Fake liefert beim zweiten Aufruf eine andere Reihenfolge; gespeichert wird das Gesicht, das die Auflistung unter diesem Index zeigte.
- **`GET /photos/{id}/faces`:**
  - Schlüsselmenge exakt `{index, box}`;
  - höchstens 20 Einträge;
  - fehlende Display-Variante → `404`, null Aufrufe des Analyzers.
- **Ausschnittbild:**
  - JPEG mit `Cache-Control: no-store` und `X-Content-Type-Options: nosniff`;
  - Index jenseits der Liste → `404`;
  - keine Datei im Cache-Verzeichnis (Verzeichnisschnappschuss vorher/nachher).
- **Executor (S7):** Zwei gleichzeitige Anfragen laufen im selben Thread und nie überlappend (Fake zeichnet Beginn/Ende und Thread-Namen auf).
- **`GET /persons`:**
  - sortiert nach Slot;
  - `reference_count` zählt nur den aktuellen `model_key`;
  - Schlüsselmenge exakt `{id, name, reference_count}`.
- **`DELETE /persons/{id}`:** `204`, danach `404`.
- **`PUT /photos/{id}/persons/{pid}`:**
  - Antwort ist die wirksame Liste;
  - zwei Nutzer ergeben eine Zeile, es gilt die letzte (beide Reihenfolgen geprüft);
  - `user_id` steht in keiner Antwort;
  - unbekannte Person → `404`;
  - kein `FeedbackEvent`.
- **`PhotoOut.persons`:**
  - Schlüsselmenge je Eintrag exakt `{person_id, origin}`;
  - an jedem Lesepfad, der `_to_photo_out` aufruft, mit den beiden Lagen, in denen Erkennung und Wirkung auseinanderfallen (Erkennung + `applies=false`, keine Erkennung + `applies=true`).
- **Filter `person_id`:**
  - je Person, beide zusammen (UND), zusammen mit dem Bewertungsfilter;
  - Paarprüfung über die Matrix: „im Filterergebnis“ genau dann, wenn „in `PhotoOut.persons`“;
  - `[1,1]` wirkt wie `[1]`, `[1,1,2]` → `422`;
  - unbekannte Id → leere Liste;
  - 0, negativ, über dem Maximum → `422`;
  - zusammen mit `draft=true` → `422`.
- **Laufzusammenfassung:** Zwilling `null` gegen Zahl; `_phase_progress` und Restdauer für `persons`.
- **Register:** alle neuen Endpunkte in `test_auth_guard.py` (ohne Token `401`) und in `test_openapi_beschreibungen.py`.

**Migration und Modelle**

- Upgrade und Downgrade laufen.
- Benannter `CHECK (slot IN (1,2))`, `UNIQUE(slot)`, `UNIQUE(name_key)`, `UNIQUE(photo_id, person_id)` ohne `user_id`.
- Echte Fremdschlüssel auf `person_id` in allen drei Tabellen.
- `person_references` hat keinen Fremdschlüssel auf `photos` oder `projects`.
- Spaltensätze von `photo_person_detections` und `photo_person_corrections` auf Gleichheit festgehalten.
- Bestandsläufe haben `persons_*` = `NULL`.
- Postgres-DDL-Kompatibilität.

**Projektlöschung**

- `project_graph.py` legt Zeilen in beiden Foto-Tabellen an; gezählt wird je Tabelle.
- `persons` und `person_references` bleiben unverändert.
- Eine Referenz aus dem gelöschten Projekt wirkt in einem anderen Projekt weiter.

**Import-Graph**

- Der vollständige Importgraph von `face_analysis`, `person_matching` und `model_assets` enthält weder `models`/`db`/`config` noch `httpx`/`cloud_vision`/`landmark`/`remote_classification`.
- Für `persons.py`, `api/persons.py` und `person_probe.py` gilt das für die direkten Importe.
- Rückrichtung: Der vollständige Importgraph der Cloud-Module und von `classification_prompt` enthält keines der Personenmodule.
- Je Richtung eine Gegenprobe, dass der Walker etwas findet.

**Modell-Assets (`test_model_assets.py`)**

- **Manifest:** je Eintrag Name, URL und SHA256 (64 Hex-Zeichen); die URL ist `https` auf eine feste 40-Hex-Revision, nicht auf `main`.
- **Integrität:** beider neuer Dateien (Muster `TestLabelEmbedderAssets`).
- **`label_embedding.py`** liest seinen Hash aus dem Manifest.
- **Ladeprogramm** mit eingeschleustem Öffner (die Netzsperre gilt):
  - korrekte Datei vorhanden → keine Anfrage;
  - falscher Hash → keine Datei am Zielpfad, Exit ≠ 0;
  - `http://` → abgewiesen vor jeder Anfrage.

**Messkommando (`test_person_probe.py`)**

- **Rein lesend:**
  - nicht im Import-Graphen von `main`/`worker`, in keinem Compose-`command`, hinter keinem Endpunkt;
  - Formwächter je Modul;
  - Tabellenschnappschuss vorher/nachher gleich, mit Gegenprobe.
- **Kein Modell:** Das Kommando importiert weder `face_analysis` noch `cv2` (Wächter).
- **Zählung** je Person aus der Datenbank, eine Lage mit allen fünf Zuständen:
  - Erkennung ohne Korrektur → richtig;
  - Erkennung + `applies=true` → richtig;
  - Erkennung + `applies=false` → falsch;
  - `applies=true` ohne Erkennung → ergänzt;
  - `applies=false` ohne Erkennung → entfernt und nicht mehr erkannt.
  - Gezählt wird die rohe Erkennung, nie die wirksame Zuordnung. Rot-Anker: Eine Zählung über die wirksame Zuordnung meldet in dieser Lage null falsche.
- **Projektbindung:** Zeilen eines anderen Projekts zählen nicht.
- **Quote:** richtig ÷ (richtig + ergänzt), mit exaktem Erwartungswert. Bei Nenner 0 steht ein Platzhalter, kein Fehler.
- **Ausgabe:** Gegen einprägsame Namen, Pfade und Ids: nur Anzahlen, „Person 1/2“, kein Schalter, der Namen ergänzt.

**Demo-Zustand (`test_demo_state.py`)**

- zwei erfundene Personen mit synthetischen Referenzen unter dem aktuellen `MODEL_KEY`;
- Fotos in den Zuständen erkannt, von Hand zugeordnet, von Hand entfernt;
- ein Name mit 40 Zeichen.

**Telemetrie aus (S15, `test_label_embedding.py`)**

- **Unterprozess** mit von Grund auf gebauter Umgebung:
  - kein `CI`/`GITHUB_ACTIONS`;
  - `HOME`, `XDG_CACHE_HOME` und Arbeitsverzeichnis in `tmp_path`;
  - `https_proxy` auf einen geschlossenen lokalen Port.

  Er ruft `build_label_embedder()` auf und rechnet ein Embedding. Danach sind alle drei Verzeichnisse leer.
- **Rot-Beleg im Docstring:** Ohne Abschaltung entstehen unter `onnxruntime` 1.29.0 schon beim bloßen `import onnxruntime` `…/Microsoft/DeveloperTools/.onnxruntime/deviceid` und `onnxruntime.db`, gemessen lokal am 2026-09-27. Er steht dort wörtlich und ist kein Testfall.
- **Syntaxbaum-Wächter:** `onnxruntime` wird im Quellbaum an genau einer Stelle importiert, und davor steht im selben Funktionskörper die Zuweisung `os.environ["ORT_DISABLE_TELEMETRY"] = "1"`.
- **Testprozess:** `conftest.py` setzt die Variable auf Modulebene, weil `TestRealAssetOutputDimension` `onnxruntime` direkt importiert.

### Frontend (vitest)

- **`utils/personFilter`:**
  - Parser: einmal, zweimal, doppelt, nicht numerisch, 0, drei Werte.
  - Filter als reine Funktion über `PhotoOut.persons`: einzeln; beide (UND); ein von Hand entfernter Name fehlt.
  - Ein → aus stellt alle Fotos wieder her.
- **`PhotoGridPage`:**
  - `person` steht im Query-Key und geht als `person_id` an den Server, zusammen mit dem Bewertungsfilter.
  - „Filter zurücksetzen“ hebt beide Filter auf.
  - Kachel-Links und „Zurück zum Grid“ tragen `person` weiter.
  - Eine unbekannte Id wird erst nach dem Laden der Personen per `replace` entfernt; solange die Liste noch lädt, bleibt die Adresse unverändert.
  - Die Filtergruppe erscheint erst ab einer Person; „Beide“ nur bei zwei.
  - Ladefehler der Personen → `Alert`.
- **`PhotoDetailPage`:**
  - Blättern und Zähler beziehen sich auf die gefilterte Folge.
  - Nach dem Entfernen des Namens bleibt das Foto stehen, Weiter/Zurück laufen weiter.
  - Die aktive Folge wird nicht neu geladen (Anfragezähler); Listen werden nur als veraltet markiert.
- **`PhotoPersonsSection`:**
  - Zeilen in der Reihenfolge von `GET /persons`.
  - Drei Zustände über ein semantisches Attribut; jeder Wortlaut wird einmal wörtlich geprüft.
  - „Ergänzen“/„Entfernen“ senden `applies` true/false.
  - Busy sperrt nur die eigene Zeile.
  - Fehler-`Alert` mit `detail`; bei `404` wird die Personenliste neu geladen.
  - Der Abschnitt steht nach der Urteilsfläche und nicht in `motifs-section`.
- **Gesichterwahl:**
  - Anfangs zugeklappt.
  - `GET faces` läuft nur beim Aufklappen, nie beim Blättern (Anfragezähler).
  - Ein Fotowechsel klappt zu.
  - Blob-URLs werden beim Zuklappen und beim Fotowechsel freigegeben (`revokeObjectURL`-Spion).
  - `aria-pressed` schaltet um.
  - Das Namensformular gibt es nur bei weniger als zwei Personen.
  - Bei getrimmt leerem Namen ist „Festlegen“ gesperrt.
  - Enter sendet ab; der Fall hat einen aktivierten Button als Vorbedingung.
  - Je `409`-/`422`-Fall die festgelegte Folge: `aria-invalid`, Liste neu, Gesichter neu, nur Meldung.
  - Der Fokus geht zurück auf „Gesicht zeigen“.
  - `404` „Bild wird noch verarbeitet.“ ergibt den ruhigen Vorschau-Satz ohne `Alert`.
  - Zustände: leere Liste, ein einzelner Ausschnitt fehlt.
- **`PersonsPage`:**
  - Zustände: Laden, Fehler, leer, Liste.
  - Zähltext: „einmal gezeigt“, „n-mal gezeigt“, bei 0 der Hinweis.
  - Die Gefahrenzone erscheint nur bei mindestens einer Person.
  - Die Tippbestätigung ist exakt („anna“ ≠ „Anna“); bis dahin bleibt „Entfernen“ gesperrt.
  - Erfolg, auch bei `404`: Dialog zu, Liste neu, Fokus auf `h1`, Statusmeldung, Foto-Listen aller Projekte werden invalidiert.
- **`AlbumDraftPage`:**
  - Der Kopf zählt den ganzen Entwurf; die Statuszeile lautet „{n} von {m}“.
  - Tage und Gruppen ohne sichtbares Foto entfallen.
  - Filter ein → aus: alle Tage und der Aufklappzustand sind wieder da.
  - Der Alternativen-Dialog bleibt ungefiltert.
  - Fällt das eingetauschte Foto aus dem Filter, gehen Fokus auf `h1` und Meldung raus.
  - Der Filter löst keine schreibende Anfrage aus.
- **`classificationSteps`:**
  - `persons` ist der letzte Schritt.
  - Vor der Phase „ausstehend“; nach Laufende mit `total === null` ausgeblendet.
  - Fortschritt kommt aus den Zählern.
- **`ProjectListPage`:** Der Einstieg „Personen“ erscheint in allen vier Zuständen.
- **Fremdtext:** Ein Name mit Markup erscheint an jeder Renderstelle als Text (Abschnitt, Filtergruppe, `/persons`, Dialog).

### E2E und Prüfstack

- `no-horizontal-scroll.spec.ts`:
  - Route `/persons` kommt dazu.
  - Die Personen-Filtergruppe mit dem 40-Zeichen-Demonamen scrollt bei schmaler Breite in sich; die Seite selbst scrollt nicht waagerecht.
- `tap-targets.spec.ts`: „Ergänzen“/„Entfernen“ und ein Eintrag der Personen-Filtergruppe.
- Manuell im Prüfstack:
  - Personenabschnitt in der Detailansicht ansehen.
  - „Gesicht zeigen“ auf einem Demo-Foto zeigt den Leerzustand; das belegt, dass das Modell im Image lädt.

### Abnahme im laufenden Betrieb (Zielinstanz, vor dem Merge)

1. Daniel zeigt in einem beliebigen Projekt je Person einige Gesichter. Einen eigenen Prüfbestand, eine Ordnerkonvention oder ein Kalibrierprojekt gibt es nicht.
2. Klassifizierungslauf in einem echten Projekt, in dem auch Verwandte und Kinder vorkommen.
3. Daniel öffnet im Bildbestand die Einschränkung auf Person 1, dann auf Person 2, und sieht jede vollständig durch.
   - Jeden falschen Namen entfernt er.
   - Übersehene Personen ergänzt er, wo sie ihm auffallen.
4. `python -m photosort.person_probe --project-id <id>` gibt je Person aus (nur Anzahlen, „Person 1/2“):
   - richtig erkannt;
   - falsch erkannt, also Erkennung + `applies=false`;
   - ergänzt, also `applies=true` ohne Erkennung;
   - entfernt und nicht mehr erkannt;
   - Quote richtig ÷ (richtig + ergänzt).
5. **Bestanden:** Falsch = 0 für beide Personen nach einer vollständigen Durchsicht.
6. **Sonst:** Die Konstanten in `person_matching.py` werden verschärft und der Literal-Test angepasst.
   - Die Schritte 2–4 folgen erneut, mit vollständiger Durchsicht, weil eine Verschärfung neue Namen erzeugen kann.
   - Die früher entfernten Namen stehen weiter als Korrektur und müssen nun unter „entfernt und nicht mehr erkannt“ zählen.
7. Die Ausgabe des bestandenen Durchgangs kommt wörtlich in den PR-Body und in den Abschnitt „Abnahme“ der Spec. Dazu die Angabe, dass die Quote eine Obergrenze ist (übersehene, nicht ergänzte Fotos fehlen im Nenner) und dass in diesem Projekt gezeigte Gesichter die Quote heben.

Eine Mindestquote gilt nicht. Erkannte Gesichter werden nie von selbst zu gezeigten Gesichtern.

## Entscheidungen

- **Abnahme im laufenden Betrieb** (Daniel, 2026-09-27): Es gibt keinen kuratierten Prüfbestand und keinen Mindestumfang. Nachgewiesen wird über eine vollständige Durchsicht der Filteransicht je Person in einem echten Projekt. Ausgewiesen wird die Quote richtig ÷ (richtig + ergänzt). Sie ist eine Obergrenze.
- **Kein Trainingslauf, kein automatisches Lernen** (Daniel, 2026-09-27): Das Modell ist vortrainiert. Personen lernt PhotoSort allein über gezeigte Gesichter. Erkannte Gesichter werden nie von selbst zu Referenzen.
- **onnxruntime-Telemetrie wird in dieser Story abgeschaltet** (Daniel, 2026-09-27; Security S15).
- **Telemetrie an drei Stellen abgeschaltet:** Maßgeblich ist die Zeile vor dem ORT-Import in `label_embedding.py`. Dazu kommen `backend/tests/conftest.py`, für Tests, die `onnxruntime` direkt importieren, und `ENV` im Dockerfile als zweite Absicherung.
- architect konsultiert (Schritt 1): ADR 0126, ADR 0033 teilweise abgelöst, `docs/architecture.md` und `docs/setup.md` nachgezogen.
- ux-ui-designer konsultiert (Schritt 2): Die Ergänzungen des Design-Systems (vier Punkte) kommen im Umsetzungs-PR.
- test-engineer konsultiert (Schritt 3): Testkonzept 0002 ergänzt.
- security-engineer konsultiert (Schritt 3): Sicherheitskonzept 0003 ergänzt, veraltete Verweise auf `fetch-label-embedder-model.sh` nachgezogen.

## Offene Fragen

- keine

## Out of Scope

- Die Berücksichtigung der Personen im automatischen Auswahlvorschlag regelt die Folge-Story #548.
- Mehr als zwei benannte Personen; Namen für andere Menschen.
- Die Gesichtsausschnitt-Kachel im Penpot-Bausteinregister wird von Hand nachgetragen, nicht in diesem PR.
