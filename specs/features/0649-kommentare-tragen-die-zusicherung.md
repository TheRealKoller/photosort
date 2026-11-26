# 0649 - Code-Kommentare tragen die Zusicherung, nicht die Entstehungsgeschichte

**Status:** Accepted
**Erstellt:** 2026-11-26
**Bezug:** [Issue #649](https://github.com/TheRealKoller/photosort/issues/649)
**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Spec acht Pull Requests trägt und
die Stellen vollständig führen muss, an denen ein Kommentar still etwas bricht — eine gekürzte
Fassung verlöre genau die Fundstellen, deren Verlust sie verhindern soll.

## Ziel

Der Produktivcode trägt wieder rund ein Drittel Kommentar. Der Ballast hat eine erkennbare Form:
Abläufe werden Schritt für Schritt nacherzählt, obwohl der Code sie zeigt; Specs und
Entscheidungen werden als Begründung zitiert, ohne dass man sie lesen müsste, um die Stelle zu
ändern; Entstehungsgeschichte und Messungen stehen im Kommentar. Alles davon wird bei jedem Lesen
und jeder Änderung mitgelesen.

Ein Kommentar trägt die geltende Zusicherung — was gilt, wofür, und was bei Verletzung passiert —
und, wo sie einen konkreten Fehlgriff verhindert, ihre kurze Begründung. Erzählung, Historie und
belegende Verweise fallen.

## User Story

Als Person, die PhotoSort ändert — Mensch wie KI — möchte ich in Kommentaren und Docstrings nur
die Aussagen finden, die sich aus dem Code nicht ablesen lassen: die geltende Zusicherung und, wo
sie einen konkreten Fehlgriff verhindert, den Grund dafür — damit ich eine Datei lese, um die
Sache zu verstehen, statt ihre Entstehungsgeschichte, und damit jede Änderung weniger Kontext und
weniger Fehlgriff-Risiko mit sich bringt.

## Akzeptanzkriterien

- [ ] **Zusicherungs-Abgleich vor und nach.** Im PR-Body steht je geänderter Datei eine Tabelle mit
      einer Zeile pro aufgenommener Aussage und drei Pflichtspalten: *was gilt* (tragende Stelle als
      Symbol oder Kommentarzeile), *wofür*, *was bei Verletzung passiert*. Eine leere Zelle ist ein
      Fehlschlag. Jede Zeile ist im Text nach dem Schnitt wiederzufinden; eine Aussage, die dort ganz
      oder in einem Teil fehlt, ist ein Fehlschlag. Der Abgleich steht im Pull Request, nicht als Datei
      im Repository.
- [ ] **Nur die fünf Ballast-Klassen fallen.** Der PR-Body nennt je Datei die entfernten
      Inhaltsklassen. `review-tests` liest die entfernten Zeilen aus dem Vorher-Bild des Diffs und
      ordnet jede genau einer der fünf Klassen zu; eine Zeile, die keine trifft, ist ein Finding. Ein
      Ersatzsatz, der eine entfernte Aussage wiederholt, ist ein Finding. Ein Verweis ist funktional
      nötig, wenn der genannte Pfad das ist, was der Code bearbeitet.
- [ ] **Begründung bleibt, wo sie einen konkreten Fehlgriff verhindert.** Für jede Stelle, an der der
      bisherige Text eine scheinbar gleichwertige Änderung abwehrt, nennt der Text nach dem Schnitt den
      drohenden Fehlgriff in seiner konkreten Form (etwa „`null` statt `0` lesen") und die Bedingung,
      unter der er eintritt. Eine allgemeine Risikobemerkung erfüllt das Kriterium nicht. Prüfung: die
      Spalte *was bei Verletzung passiert* aus dem Abgleich nennt die konkrete Form, und
      `review-tests` findet sie im Text wieder. Die zugehörige Historie fällt.
- [ ] **Verhalten und ausgelieferte Beschreibungen unverändert.** Belegt durch drei Beobachtungen:
      `scripts/check.sh` läuft mit derselben Prüfungszahl durch; der OpenAPI-Vergleich ändert
      ausschließlich `description`-Werte und macht keine vorher nicht-leere Beschreibung leer;
      Knotenmenge und Ausgang der Suiten sind identisch. Ein verlorenes `# pragma: no cover` zeigt sich
      als gesunkenes `Cover`.
- [ ] **Keine Testanpassung.** In Backend, `scripts/` und Frontend sind Knotenmenge und Ausgang je
      Knoten identisch (Befehle und Vergleichsform in der Teststrategie); `e2e/` läuft unverändert im
      CI-Job jedes PRs. Jede Abweichung ist ein Halt. Die Ausnahme für
      `scripts/tests/waechter_aussagen.json` aus dem Testkonzept gilt hier nicht, weil sie eine
      Teständerung wäre.
- [ ] **Kein Umfangs-Gate und keine Zielquote.** Dateien ohne Ballast bleiben unverändert; eine Datei
      darf danach weiter über dem Richtwert liegen. Keine Vorgabe verlangt eine prozentuale oder
      zeilenweise Reduktion, und kein Pull Request, kein Commit und kein Abschnitt nennt einen
      Reduktions-Zielwert. Vorher/Nachher-Zahlen je Datei sind Messung, keine Zielgröße.

## Datenmodell-Bezug

Nicht relevant: Es ändern sich ausschließlich Kommentare und Docstrings, keine Entität, kein Feld und keine Migration.

## Architektur / Umsetzung

Kein neuer Baustein und keine neue ADR. Die Doku-Ballast-Regel aus `CLAUDE.md` wird erneut auf den Produktivcode angewendet, begrenzt auf zwei geschlossene Aufnahmemengen und aufgeteilt auf acht Pull Requests.

### Ist-Stand, gemessen am 26.11.2026

**Messweg** (Wegwerf-Auswertung, nicht eingecheckt, vorher und nachher derselbe):
- **Dateimenge:** `git ls-files backend/src frontend/src frontend/penpot scripts` mit den Endungen `.py`, `.sh`, `.ts`, `.tsx`. Ausgenommen sind `*.test.ts(x)` (darunter alle `*.contract.test.ts`), `frontend/src/test/**`, `frontend/src/setupTests.ts` und unter `scripts/` alles außer den Dateien direkt im Verzeichnis.
- **Doku-Zeile:** eine nicht-leere Zeile, deren gesamter Nicht-Leerraum in einem Kommentar oder Docstring liegt.
  - Python: `tokenize`-Kommentare auf Zeilen, die mit `#` beginnen, plus jede Zeile einer Ausdrucksanweisung, die nur aus einem String besteht (`ast`).
  - Shell: Zeilen, die mit `#` beginnen; die Shebang-Zeile zählt nicht.
  - TS/TSX: Kommentarbereiche aus dem TypeScript-Parser (`frontend/node_modules/typescript`, Trivia jedes Knotens) plus JSX-Kommentare `{/* */}`.
- **Verweiszeile:** eine Doku-Zeile, auf die `specs/|decisions/|\bADR\b|\b(PR|Issue|Story|Spec|Pull Request)\s*#?\s*\d{2,4}\b|\(#\d{2,4}\)|(?<![\w#&])#\d{3}\b` passt.
- **Kennzeichenzeile:** eine Doku-Zeile ohne Verweis, auf die `\bAK ?\d+\b|\bZusicherung(en)? \d+\b|\bAuflage S\d+\b|(?<![\w/.-])S\d{1,2}(/S?\d{1,2})?\b(?!\w)` passt.

319 Nicht-Test-Quelldateien mit 63.777 nicht-leeren Zeilen, davon **19.761 Doku-Zeilen (31,0 %)**. Dazu kommen **550 Verweiszeilen** und **457 Kennzeichenzeilen** in Doku-Blöcken. 212 Dateien liegen über dem Richtwert von 25 %.

| Bereich | Dateien | Doku-Zeilen | Anteil | über 25 % | Verweis- / Kennzeichenzeilen | A | B | A ∪ B |
|---|---|---|---|---|---|---|---|---|
| `backend/src` | 112 | 12.106 | 34,5 % | 84 | 376 / 369 | 80 | 46 | 88 |
| `frontend/src` | 198 | 6.985 | 26,4 % | 123 | 167 / 84 | 94 | 38 | 106 |
| `frontend/penpot` | 2 | 124 | 35,5 % | 2 | 0 / 0 | 0 | 0 | 0 |
| `scripts` | 7 | 546 | 28,3 % | 3 | 7 / 4 | 4 | 2 | 5 |
| **Summe** | **319** | **19.761** | **31,0 %** | **212** | **550 / 457** | **178** | **86** | **199** |

### Aufnahmemengen

Gegenstand ist genau A ∪ B: **199 Dateien mit 17.309 Doku-Zeilen**. Die übrigen 120 Dateien (2.452 Doku-Zeilen) sind nicht Gegenstand. Eine Datei aus A ∪ B ohne Ballast bleibt unverändert.

- **A, Verweise und Kennzeichen:** Datei mit mindestens einer Verweis- oder Kennzeichenzeile, 178 Dateien. Über jede Fundstelle wird einzeln entschieden: Ist sie funktional nötig, bleibt sie; belegt sie nur, fällt sie.
  - Funktional sind zum Beispiel `scripts/render-diagrams.sh:2` und `scripts/nummern.py:68`/`:429`: Dort sind die genannten `specs/`-Pfade das, was der Code bearbeitet.
  - Ein Testverweis ist kein belegender Verweis.
- **B, Doku-Blöcke:** Doku-Anteil ≥ 35 % **und** ≥ 60 nicht-leere Zeilen, 86 Dateien mit 10.195 Doku-Zeilen.

### Zuschnitt: acht Pull Requests

Jeder PR ist die Schnittmenge aus A ∪ B und seiner Pfadregel; die Dateien darin stehen absteigend nach Doku-Masse, angegeben als Doku-Zeilen / nicht-leere Zeilen. Die PRs laufen nacheinander. Jeder zweigt von einem aktuellen `origin/main` ab, nachdem der vorige gemergt ist:
- PR 1 auf dem bestehenden Branch `feature/0649-kommentare-tragen-die-zusicherung`,
- PR k ≥ 2 auf `feature/0649-kommentare-tragen-die-zusicherung-teil-<k>`.

1. **Spec und `scripts/`**: 5 Dateien, 428 Zeilen. `nummern.py` (192/805), `merge-main-into-branch.sh` (94/179), `produktentscheidung.py` (87/260), `format.sh` (49/113), `render-diagrams.sh` (6/27).
2. **Frontend-Logik** (`frontend/src/{api,utils,hooks,lib}/`): 48 Dateien, 2.766 Zeilen. Angeführt von `api/types.ts` (701/1460), `utils/pipelineSteps.ts` (140/324), `utils/albumDraft.ts` (111/247), `hooks/usePhotos.ts` (108/391).
3. **Frontend-Oberfläche** (`frontend/src/{components,pages}/` und `App.tsx`): 58 Dateien, 2.678 Zeilen. Angeführt von `components/MotifStrengthSection.tsx` (144/401), `components/ClassificationSection.tsx` (131/504), `components/Stepper.tsx` (120/330), `pages/PhotoDetailPage.tsx` (110/479).
4. **Worker** (`backend/src/photosort/worker/**`): 14 Dateien, 1.461 Zeilen. Angeführt von `scan.py` (298/772), `_runs.py` (162/381), `criterion_scoring.py` (152/470), `_criterion/landmark.py` (142/438).
5. **Orte, Events, Duplikate, Bilddateien**: 10 Dateien, 1.743 Zeilen. `events.py` (592/1284), `duplicates.py` (226/474), `geonames.py` (193/494), `landmark.py` (189/425), `thumbnails.py` (173/379), `opencloud/exif.py` (115/223), `places.py` (86/129), `event_inputs.py` (72/161), `cameras.py` (58/104), `landmark_names.py` (39/82).
6. **Bewertung, Klassifizierung, Auswahl**: alle übrigen Module direkt unter `backend/src/photosort/` in A ∪ B, 28 Dateien, 2.633 Zeilen. Angeführt von `criteria.py` (320/606), `cloud_vision.py` (300/553), `classification.py` (230/485), `remote_classification.py` (208/529), `scoring.py` (160/426).
7. **API** (`backend/src/photosort/api/**`): 23 Dateien, 2.844 Zeilen. Angeführt von `projects.py` (414/1295), `photos/_conversion.py` (405/826), `photos/draft_exchange.py` (206/604), `classification_reviews.py` (204/1301). Dieser PR trägt 1.468 der 1.542 Docstring-Zeilen, die als OpenAPI-Beschreibung ausgeliefert werden.
8. **Datenmodell, Konfiguration, Betriebskommandos**: 13 Dateien, 2.756 Zeilen. `models.py` (983/1862), `demo_state.py` (637/2202), `event_probe.py` (434/1480), `criterion_probe.py` (144/355), `config.py` (123/202), `project_deletion.py` (118/348), `place_probe.py` (115/566), `place_dataset.py` (74/218), `cache_cleanup.py` (45/76), `duplicate_probe.py` (37/365), `person_probe.py` (23/166), `clock.py` (12/16), `db.py` (11/40).

**Reihenfolge innerhalb eines PR:**
1. Zusicherungen je Datei aufnehmen (was gilt, wofür, was bei Verletzung passiert).
2. Verweise und Kennzeichen schneiden.
3. Doku-Blöcke inhaltlich schneiden.
4. Abgleich nachher.

Commits werden je Datei-Untergruppe und Inhaltsklasse geschnitten. Der PR-Body trägt je geänderter Datei:
- eine Zeile in der Form Pfad → entfernte Inhaltsklasse(n) → Doku-Zeilen vorher/nachher,
- dazu den Zusicherungs-Abgleich.

Überschreitet der Body 60.000 Zeichen, steht der Abgleich je Datei in weiteren Kommentaren am selben Pull Request, nie in einer Datei im Repository.

### Schlüsselwort-Regel

- **Nur PR 8 schließt das Issue.** Nur sein Body trägt die Zeile `Closes #649`.
- **PR 1 bis 7 tragen stattdessen** die Zeile `Teil von #649 (PR <k> von 8)`. Der Kommentarblock der Vorlage rund um die Closing-Zeile entfällt dort.
- **Verbotene Form:** In keinem Titel, Body oder Kommentar von PR 1 bis 7 und in keiner Commit-Nachricht eines der acht PRs steht eines der Wörter `close`, `closes`, `closed`, `fix`, `fixes`, `fixed`, `resolve`, `resolves` oder `resolved` (beliebige Schreibweise) vor einem Issue-Bezug. Das gilt auch zitiert oder erklärend. Beim Squash wandert jeder Commit-Body in den Merge-Commit, und GitHub wertet ihn dort aus.
- **`ship-feature` 6.5 bei PR 1 bis 7:** `closingIssuesReferences` muss **leer** sein, `baseRefName` muss `main` sein. Enthält die Liste #649, wird zuerst der Body korrigiert, vor jedem weiteren Schritt.
- **6.6 (Statuszeile) nur in PR 8:** Bis dahin bleibt die Spec auf `Accepted`.
- **Schritt 7 bei PR 1 bis 7:** Der Board-Wert wird nur gelesen, nicht gesetzt. Ohne Closing-Zeile wandert die Karte nicht von selbst.

### Fallen, die still brechen

**Funktionstragende Kommentare.** Die Direktive bleibt in ihrer wirksamen Form; ein nachgestellter Erklärtext darf fallen.
- `# pragma: no cover`: `criterion_probe.py:432`, `demo_state.py:890` und `:2436`, `event_probe.py:1738`, `events.py:319`, `person_probe.py:197`, `place_dataset.py:255`, `place_probe.py:670`.
- `# type: ignore[…]`: `api/feedback.py:148`, `api/persons.py:278`, `motif_strengths.py:122` und `api/photos/_conversion.py:534`. An der letzten Stelle darf das zweite `# caller already checked not None` fallen.
- `# noqa`: `duplicate_probe.py:45`, `opencloud/exif.py:13`, `thumbnails.py:19`, `face_analysis.py:71`/`:77`, `worker/classification_review.py:693`/`:694`.
- `// prettier-ignore`: `frontend/src/components/StepMarker.tsx:44` und `:74`.
- `eslint-disable`, `oxlint-disable`, `@ts-expect-error`, `@ts-ignore` und `/// <reference` kommen nicht vor.

**Kommentare, die eine Prüfung braucht.** Fällt der Text weg, wird der Test rot:
- `frontend/src/components/SelectionPhotoTile.tsx:94`: Das einzige Vorkommen von `draftMembership` in der Datei ist dieser Kommentar. `albumSelection.structure.test.ts:101` verlangt, dass es da ist.
- `backend/src/photosort/models.py:436`: Das Token `` `api/ratings.py::_drop_when_empty` `` bleibt byte-gleich stehen. `scripts/tests/test_doku_pfade_existieren.py` prüft die Menge der toten Verweise auf **Gleichheit**; ein entfernter Altverweis macht den Test also ebenso rot wie ein neuer toter.

**Begriffe, die kein Kommentar neu einführen darf.** Diese Tests lesen den Rohtext samt Kommentaren:
- `func.min(Photo.taken_at)` steht genau einmal, in `photo_aggregates.py` (`test_api_stats.py:1852`).
- `MOTIF_PRESENCE_THRESHOLD` steht nur in `selection.py`, dort genau einmal als `>= MOTIF_PRESENCE_THRESHOLD`; `selection.py` nennt weder `photosort.motifs` noch `motifs.py` (`test_selection.py:1375–1402`).
- Die Bandkonstanten `MOTIF_STRENGTH_BAND_*` stehen nur in `motifs.py`, `api/motifs.py` und `api/stats.py` (`scripts/tests/test_kategorien_restlos_entfernt.py:121`). Dieselbe Datei verbietet in `backend/src` und `frontend/src` die Wörter `category_key`, `is_primary`, `category_override`, `nicht_erkannt`, `precedence` und `CONFIDENCE_RANK_PENALTY` (`:40–47`).
- `PhotoMotifCorrection.applies` steht nur in `motif_strengths.py` (`test_motif_strengths.py:702`).
- `_EVENT_PLACE_COORDINATE_DIGITS` steht nirgends (`test_events_lookup_and_cells.py:163`).
- Die Formen `suggested_status.is_(None)` und `suggested_status is None` stehen außerhalb von `duplicates.py` nirgends (`test_ausschuss_ueberlebende.py:343`).
- `ModelSet` steht nicht in `worker/_criterion/ranking.py` (`test_criterion_phases_standalone.py:197`).
- `APIRouter` und `fastapi` stehen nicht in den Probe-Modulen und nicht in `place_dataset.py` (zum Beispiel `test_criterion_probe.py:700`, `test_place_probe.py:140`).
- `build_place_resolver` und `GeoNamesResolver` stehen nicht in `demo_state.py` (`test_demo_state_coverage_states.py:442`).
- In `api/photos/image.py` steht hinter `set_motif_correction` weder `.with_for_update(` noch `_lock_photo_score` (`test_api_motif_corrections.py:594`).
- In `api/stats.py` stehen weder `PhotoLandmarkDetection.confidence` noch `.canonical_name` (`test_api_stats.py:1038`).
- `worker.py` und `api/photos.py` stehen nirgends in der Doku von `backend/src`, und jedes neue Pfad-Token muss auflösbar sein (`test_doku_pfade_existieren.py`).
- In den Dateien des Einzelentwurfs stehen weder `final_selection_decision` noch `in_final_selection` noch `contested` (`albumSelection.structure.test.ts:71`).
- Die Texte von `DRAFT_EMPTY_TEXT`, `ALBUM_SUITABILITY_NOT_RATED_TEXT` und `ALBUM_SUITABILITY_ORIGIN_LABEL` werden nicht zitiert (`:125`, `:148`).
- `Vorschlag`, `Aufgenommen` und `Gestrichen` stehen nicht in Anführungszeichen oder Backticks (`albumStateLabels.structure.test.ts:39`).
- `<PhotoCard` steht nicht in `PhotoGridTile.tsx` (`photoGridTile.structure.test.ts:79`).
- In `scripts/` wird die Merge-Nachricht nicht zitiert (`test_main_abgleich_verdrahtung.py:946`), und `main...HEAD` steht dort ohne `origin/` nirgends.

**Zeilen, die die e2e-Toolchain bindet** (`e2e/tests/toolchain.spec.ts`). Diese Zeilen bekommen auch keinen nachgestellten Kommentar:
- `^DEMO_PROJECT_PREFIX = "…"$` in `demo_state.py:153` und `^CONFIRM_LITERAL = "…"$` in `demo_state.py:166`,
- dazu die Projekt- und Personennamen in `demo_state.py` (`:238`, `:246`),
- `^const TOKEN_STORAGE_KEY = '…'$` in `frontend/src/auth/token.ts:1`.

**Freigabelisten des Design-Vertrags.** `stripComments` entfernt `//` nur am Zeilenanfang. Die 53 `file`+`snippet`-Einträge treffen heute keine Zeile mit einem nachgestellten Kommentar. Der einzige nachgestellte Kommentar in Produktiv-`.tsx` ist `ProjectSettingsPage.tsx:144`. Vor dem Entfernen wird er gegen die Freigabe-Snippets abgeglichen.

**Python-Körper und Statements.**
- Ein Körper, der nur aus einem Docstring besteht, behält ihn; sonst `SyntaxError`. Fundstellen in A ∪ B:
  - `criterion_probe.py:91`, `demo_state.py:582`, `duplicate_probe.py:103`, `event_probe.py:145`, `events.py:1006`,
  - `eye_client.py:47`/`:57`, `eye_mapping.py:478`, `geonames.py:58`, `landmark.py:102`, `model_choice.py:22`,
  - `person_probe.py:47`, `place_probe.py:75`, `remote_classification.py:109`,
  - `worker/criterion_scoring.py:63`/`:71`, `scripts/nummern.py:91`.
- **Attribut-Docstrings zählt Coverage als Statement** (nachgemessen). An `cache_cleanup.py:37` und `thumbnails.py:300` wird gekürzt, aber weder gelöscht noch in einen `#`-Kommentar umgewandelt; sonst ändert sich `Stmts`.

**Ausgelieferte Beschreibungen.**
- 59 der 68 Routen-Docstrings werden zur OpenAPI-`description` der Operation, zusammen 757 Zeilen.
- Die Docstrings von 108 Schema-Klassen werden zu `components.schemas.*.description`, zusammen 785 Zeilen. Davon liegen 58 in `models.py` und 6 in `feedback.py`, der Rest unter `api/`.
- Kein Docstring enthält `\f`.
- **Prüfung je PR, der eine dieser Dateien ändert:** `create_app().openapi()` vorher und nachher als sortiertes JSON ausgeben und vergleichen. Der Diff darf ausschließlich `description`-Werte berühren. Jede vorher nicht-leere Beschreibung bleibt nicht-leer. Je geänderter Beschreibung zeigt der PR-Body vorher/nachher, damit das Review „inhaltlich gleich" prüft.

**Argparse.**
- `__doc__` speist nur in `scripts/seed-opencloud-demo.py:302` eine `--help`-Ausgabe; die Datei ist nicht Gegenstand.
- Die `description=`/`help=`-Argumente in `demo_state.py:2395`, `criterion_probe.py:383`, `duplicate_probe.py:396`, `event_probe.py:1568`, `person_probe.py:167`, `place_dataset.py:204` und `place_probe.py:570` sind Anweisungen, keine Doku, und bleiben unverändert.

**Halt statt Anpassung.** Keine Testdatei, keine Testkonfiguration und kein `waechter_aussagen.json` wird angefasst. Wird eine Prüfung rot, geht der Halt an den Aufrufer zurück.

### Doku-Update

Kein `docs/`- und kein Konzept-Update: Weder Systemarchitektur noch Datenmodell noch lokales Setup ändern sich. Die Ankerliste im Sicherheitskonzept nennt Funktionen statt Zeilen und bleibt deshalb gültig.

## UI/UX

Nicht relevant. Im Frontend ändern sich ausschließlich Kommentartexte; kein Renderpfad, kein
Zustand, keine Eingabe, keine dargestellten Daten.

## Security

Die Story öffnet keine Angriffsfläche und fasst keinen Kontrollpfad an. Der Schaden ist eine
Regression bestehender Kontrollen: Liegt die Auflage nur noch im Kommentar an der durchsetzenden
Stelle, nimmt der nächste Refactoring wer die Datei liest den Schutz heraus und niemand merkt es.

Gegenstand sind 89 der 199 Dateien aus A ∪ B, die eine Sicherheitsauflage tragen oder das
Sicherheitskonzept nennen — PR 1: 3, PR 2: 7, PR 3: 13, PR 4: 9, PR 5: 9, PR 6: 16, PR 7: 23,
PR 8: 9. In zehn davon steht ein Verweis auf `0003-securitykonzept.md`, verteilt auf PR 1
(`format.sh`, `merge-main-into-branch.sh`), PR 3 (`PhotoDetailStage.tsx`), PR 4 (`_runs.py`),
PR 5 (`duplicates.py`, `event_inputs.py`, `opencloud/exif.py`) und PR 7 (`api/cameras.py`,
`api/photos/_conversion.py`). **Regel:** Ein Verweis auf das Sicherheitskonzept fällt nur, wenn der
Satz danach die Auflage vollständig trägt; das Konzept nennt die durchsetzende Stelle von seiner
Seite, die Verbindung hängt nicht am Rückverweis im Code.

`security.py`, `main.py`, `api/auth.py`, `api/deps.py`, `rate_limit.py`, `frontend/src/auth/jwt.ts`
und `frontend/src/api/client.ts` liegen außerhalb von A ∪ B und bleiben unberührt.

**S1–S4 aus Spec 0411 tragen weiter und stehen bereits** — S1 und S2 in ADR 0086 Abschnitt 1 und
`CLAUDE.md`, S3 dort ebenfalls („ohne am Bestand nachgewiesenen Test bleibt sie in voller Aussage
stehen"), S4 in der Fassung „der Kommentar nennt sie in einem Satz und nennt den Test". Hier nicht
wiederholt. Daraus nur die zwei für den Schnitt bindenden Folgen:

- Das Angriffsmodell bleibt *wofür*: benannter Angriff und die eine untersagte Alternative fallen
  nie mit dem Verweis.
- Eine Sicherheitsauflage wird **nicht** auf einen Testverweis verkürzt. Damit entfällt der
  Mutationsversuch aus S3; Testverweise, die schon dastehen, bleiben.

**Ankerliste.** Sie nennt Funktionen statt Zeilen und überlebt den Kommentarschnitt. Eine Zeile
hängt an einem Kommentar: `api/persons.py::person_write_lock` verweist auf den Kommentar an der
Sperre, der die Voraussetzung „genau ein API-Prozess, ohne `WEB_CONCURRENCY`" nennt — dieser Satz
bleibt in PR 7 in voller Aussage.

**`review-security` läuft an jedem der acht PRs.** Mechanisch ausgelöst wird es nur von PR 1
(`scripts/nummern.py`), 5 (`opencloud/exif.py`), 7 (`api/**`) und 8 (`config.py`); die Trigger-Tabelle
ist pfadlisten-blind, PR 2, 3, 4 und 6 träfen keinen Eintrag. Prüffrage je PR: Welche Auflage trug
jede geänderte Stelle, welcher Angriff und welche Alternative waren benannt, und stehen beide noch?
Ein Verlust ist ein Halt, kein Nachbesserungsauftrag.

## Teststrategie

Keine Verhaltensaussage, kein Rot-Grün-Zyklus: Je PR tritt der Vorher-Nachher-Vergleich (`origin/main`
→ Branch-Spitze) nach „Nachweis ohne Rot-Grün" aus `specs/architecture/0002-testkonzept.md` an seine
Stelle — (a) kein Testdiff, (b) identische Testknoten und Ausgänge, (c) `Stmts` je Datei gleich,
`Cover` nirgends kleiner.

Dieselben Befehle vorher und nachher, je mit `--junitxml`:

- **Backend:** `pytest -n auto -q --tb=no --cov=photosort --cov-report=term`. Verglichen werden
  `(classname, name, Ausgang)` je `testcase` sortiert und die Coverage-Tabelle spaltenweise. Heute
  6.677 Knoten, 1 übersprungen (`eye_meta.json` fehlt lokal), `TOTAL 11890`, `Cover 92 %`.
- **`scripts/`:** `pytest -q --tb=no`, wie oben. Heute 1.746 bestanden.
- **Frontend:** `npm run test -- --run --reporter=junit`. Wie oben. Heute 3.679 bestanden; kein
  Coverage-Wert, (a) und (b) tragen allein.
- **`check.sh`:** heute 10 von 10. `ruff format --check` reagiert auf Zeilenlage, `E501` (ab 111
  Zeichen) auf einen zu lang geratenen Satz, `mypy --strict` auf ein verlorenes `# type: ignore`,
  `prettier --check` auf ein verlorenes `// prettier-ignore`.
- **`e2e/`:** läuft unverändert im CI-Job jedes PRs.

**Ein Baum für beide Seiten.** Die drei ONNX-Modelle unter `backend/src/photosort/assets/` sind
gitignoriert. Beide Seiten laufen deshalb mit derselben Ausstattung — alle drei kopiert oder in beiden
nicht; fehlen sie, scheitern sechs Knoten in `test_label_embedding.py`, `test_model_assets.py` und
`test_face_analysis.py`. Nicht-Grün ist zulässig, Gleichheit nicht.

**OpenAPI** in jedem PR: `create_app().openapi()` geparst vergleichen, nicht als Text; der Diff berührt
nur `description`, keine vorher nicht-leere wird leer.

**Diff-Pfade:** `git diff --name-only origin/main...HEAD` gegen
`^(backend/tests/|backend/\.test_durations$|scripts/tests/|frontend/src/test/|frontend/penpot/[^/]*\.test\.ts$|frontend/src/setupTests\.ts$|e2e/|eye/test/)|.test.tsx?$`
muss leer sein.

## Entscheidungen

- Menge A umfasst neben Dokumentverweisen auch Kennzeichen ohne Dokument (`AK n`, `(Sn)`, `Auflage Sn`, `Zusicherung n`). Ohne Dokumentnummer sind sie nicht auflösbar und deshalb nur belegend; über jede Fundstelle wird einzeln entschieden.
- Routen- und Schema-Docstrings werden wie jeder andere Doku-Block gekürzt. Nachgewiesen wird „inhaltlich gleich" über den OpenAPI-Vergleich, der ausschließlich `description`-Werte berühren darf.
- Acht PRs nacheinander, je von einem aktuellen `origin/main`. PR 1 trägt Spec und `scripts/`, es gibt also keinen reinen Spec-PR. Nur PR 8 trägt die Closing-Zeile und die Statuszeile `Implemented`; PR 1 bis 7 tragen `Teil von #649`.
- Testinfrastruktur unter `frontend/src/test/` und `frontend/src/setupTests.ts` zählt als Testdatei und ist nicht Gegenstand.
- Keine neue ADR und kein eingechecktes Messskript: Die Regel bleibt, wie sie ist, und der Messweg steht in diesem Abschnitt.
- S1–S4 werden nicht erneut geführt: Sie stehen in ADR 0086 und `CLAUDE.md`; Spec 0649 legt nur die
  zwei Folgen fest, die der Schnitt an Sicherheitsstellen braucht.
- Sicherheitsauflagen bleiben in voller Aussage — auch dort, wo ein Test sie erzwingt. Der Verzicht
  auf die Verkürzung zum Testverweis erspart die Mutationsprüfung je Stelle und deckt sich mit dem
  Zusicherungs-Abgleich, der den Test als Beleg ohnehin nicht kennt.
- Kennungen wie `(S4)`/`Auflage S4` fallen, solange die Datei die Herkunftsspec nicht selbst nennt
  (sie zeigen dann auf nichts Auflösbares); die Markierung `SICHERHEIT` und der volle Satz bleiben.
  `Sicherheitskonzept S4` und `Bedrohung 1` in PR 1 sind ebenso unauflösbar — die Auflage daneben
  steht vollständig, also fällt nur die Kennung.
- Beide Vergleichsseiten laufen im frischen Worktree, mit dem venv des Haupt-Checkouts und
  `PYTHONPATH=<worktree>/backend/src`, im Frontend über ein `node_modules`-Symlink: Der Ausgang hängt
  an der Asset-Ausstattung des Baums, nicht am Produktverhalten.
- Der OpenAPI-Vergleich läuft in jedem PR, nicht nur in denen mit API-Dateien: zwei Sekunden, und eine
  `description` kann aus jeder Datei des Schnitts stammen.
- Kein neuer Test, kein Wächter und keine Ergänzung des Testkonzepts; die Ausnahme für eine Zeile in
  `waechter_aussagen.json` wird nicht in Anspruch genommen, weil jede Änderung unter einem Testpfad
  ausgeschlossen ist.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Im Frontend ändern sich ausschließlich
  Kommentartexte — kein Renderpfad, kein Zustand, keine Eingabe, keine dargestellten Daten.

## Offene Fragen

Keine.

## Out of Scope

- Die Doku-Ballast-Regel und ihre Schutzgrenze — sie bleiben, wie sie sind; diese Story wendet sie an.
- Abgeschlossene Feature-Specs und angenommene Entscheidungen.
- Die CI-Konfiguration.
- Alembic-Migrationen: Ihre Docstrings beschreiben den Rückweg samt Datenverlust.
