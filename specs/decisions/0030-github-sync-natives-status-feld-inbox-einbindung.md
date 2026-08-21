# 0030 - GitHub-Sync: natives Status-Feld statt eigenem Custom-Field, Superseded als Label, Inbox-Einbindung

**Status:** Accepted
**Datum:** 2026-08-21
**Bezug:** `specs/inbox/0028-github-sync-status-feld-und-inbox.md`, ADR [`decisions/0017-github-projects-v2-spec-sync.md`](./0017-github-projects-v2-spec-sync.md) (Abschnitt 3 wird hiermit teilweise abgelöst, die ADR selbst bleibt für alle übrigen Abschnitte gültig), `idea-sharpener`-Konsultation mit Daniel am 2026-08-21.

## Kontext

Seit Umsetzung von Spec [`0031`](../features/0031-zweiwege-sync-specs-github-projekt.md) (PR #115 ff.) läuft der Zwei-Wege-Sync produktiv gegen das GitHub Project "PhotoSort Roadmap" (Owner `TheRealKoller`), mit 51 gesyncten Feature-Specs. Ein Live-Check gegen das echte Project hat zwei Dinge bestätigt:

- Das bei Projekt-Erstellung automatisch von GitHub angelegte, native Single-Select-Feld `Status` (Optionen `Todo`/`In Progress`/`Done`) existiert, wird aber von keinem Sync-Code beschrieben — es liegt seit Anfang an ungenutzt brach.
- Das eigene Custom-Field `Spec Status` (bewusst nicht `Status` genannt, siehe `gh_adapter.py` Zeilen 95–104 und ADR 0017 Abschnitt 3 — Namensgleichheit mit dem nativen Feld hätte `ensure_fields()` bei jedem Lauf zum Absturz gebracht) ist produktiv befüllt.

Daniel möchte das umdrehen: das native `Status`-Feld soll die eigentlich gemeinte Spalte sein (einfachere GitHub-Views, "die richtige Spalte mit den richtigen Werten"), das separate `Spec Status`-Feld entfällt. Zusätzlich soll `specs/inbox/*.md` (bisher laut ADR 0017 Randbedingungen und Spec 0031 Out-of-Scope explizit ausgeschlossen) ebenfalls 1:1 gesynct werden, mit einem neuen Statuswert `Unrefined`. `Superseded` verschwindet als Feldwert vollständig und wird stattdessen ein Label; zwei zusätzliche Labels (`idee`, `bug`) markieren den `**Typ:**` eines Inbox-Eintrags.

Zwei technische Fakten bestimmen die Umsetzbarkeit maßgeblich:

1. **`gh` (2.97.0, unverändert seit ADR 0017) kennt kein `field-edit`** — nur `field-create`, `field-delete`, `field-list` (per `gh project --help` verifiziert). Ein bestehendes Single-Select-Feld lässt sich also nicht "umbenennen"/"Optionen ändern", nur löschen und neu anlegen.
2. **Zwei Feature-Specs tragen bereits real `**Status:** Superseded`** (`0003`, `0024`) — der Superseded-Fall ist kein hypothetischer Rand-, sondern ein produktiv vorkommender Fall, der beim Feldmodell-Wechsel korrekt behandelt werden muss.
3. **Inbox- und Feature-Nummernkreise sind unabhängig** (`.claude/skills/capture/SKILL.md`) — Kollisionen (z.B. `inbox/0004` und `features/0004` gleichzeitig) sind real, nicht nur theoretisch.

Diese ADR löst wie 0017 selbst kein PhotoSort-Anwendungsproblem, sondern eine Prozess-/Tooling-Frage für die Verwaltung der Specs selbst — wird aber als ADR festgehalten, weil sie eine bereits per ADR 0017 explizit als architekturrelevant markierte Grundsatzentscheidung (Abschnitt 3, Datenmodell auf GitHub) revidiert (ADR 0017, letzter Konsequenzen-Satz: "Ein späterer Wechsel des Grundprinzips ... bleibt architekturrelevant und braucht eine neue, diese ADR als 'Superseded' markierende ADR" — hier: teilweise, siehe unten).

## Entscheidung

### 1. Ein gemeinsames natives Feld `Status` für Features *und* Inbox, `Spec Status` entfällt

Ein einziges Single-Select-Feld im bestehenden Project, exakt `Status` genannt, mit den Optionen `Proposed`, `Accepted`, `Implemented`, `Unrefined` — **kein** `Superseded` mehr als Option (siehe Abschnitt 2). `Unrefined` wird ausschließlich von Inbox-Einträgen benutzt, die drei übrigen weiterhin ausschließlich von Feature-Specs; beide Entitäten teilen sich dasselbe Feld/Project, kein zweites Project.

### 2. `Superseded` wird Label, nicht Feldwert — Statusfeld wird für Superseded-Specs geleert

Für eine Spec mit `**Status:** Superseded` wird das `Status`-Feld des zugehörigen Items **geleert** (`clear_item_field`, exakt dasselbe bereits bestehende Verhalten wie beim Leeren des `Priorität`-Felds für Implemented/Superseded-Specs) und stattdessen das Label `superseded` gesetzt. Der native Issue-Zustand bleibt wie bisher geschlossen. Kein neuer "leerer Wert bedeutet X"-Interpretationsaufwand nötig — das Leeren ist bereits ein etabliertes Muster im Code (`_apply_fields`, Zweig `priority is None`), wird hier nur auf das zweite Feld übertragen.

### 3. Migration: einmalig, manuell, **kein** permanenter Auto-Heal-Codepfad

Da `gh` kein `field-edit` kennt (siehe Kontext), lässt sich das native `Status`-Feld nicht in-place umbenennen — es muss gelöscht und neu angelegt werden. Ein produktionsdauerhafter Code-Pfad, der bei jedem Lauf prüft "hat das Feld namens `Status` die falschen Optionen? Dann löschen und neu anlegen" widerspräche dem in ADR 0017/PR #115 bereits bewusst etablierten Prinzip, Board-Drift (manuell verändertes Feld) **nie** stillschweigend zu reparieren, sondern hart abzubrechen (`_apply_fields`, Kommentar "Board-Drift ... darf nie still hingenommen werden"). Deshalb bleibt `ensure_fields()` inhaltlich unverändert (create-if-missing, hard-fail bei fehlender Option) — die Feld-Bereinigung ist ein **einmaliger, manueller Rollout-Schritt außerhalb der Skript-Logik**, kein Feature-Code, analog zum bereits etablierten manuellen `gh auth refresh -s project`-Schritt (ADR 0017 Abschnitt 2) und dem manuellen Smoke-Test-Vorgehen (Spec 0031, Teststrategie):

1. `gh project field-list <number> --owner TheRealKoller --format json` — IDs des nativen `Status`-Felds (Todo/In Progress/Done, ungenutzt) und des `Spec Status`-Custom-Felds ermitteln.
2. `gh project field-delete --id <status-field-id>` und `gh project field-delete --id <spec-status-field-id>` — beide löschen. **Kein Datenverlust**: Status/Priorität sind laut ADR 0017 Abschnitt 4 eine reine, bei jedem Lauf neu berechnete Push-Spiegelung der Spec-Datei (nie Source of Truth) — das Löschen entfernt nur einen jederzeit reproduzierbaren Spiegelwert.
3. Aktualisierten Code deployen (`STATUS_FIELD_NAME = "Status"`, neue `STATUS_OPTIONS`).
4. Einen vollen Sync-Lauf ausführen (kein `--only`) — `ensure_fields()` findet kein Feld mehr namens `Status`, legt es über den bestehenden Self-Provisioning-Pfad frisch mit den vier neuen Optionen an; die anschließende reguläre Item-Verarbeitung pusht Status (und unverändert Priorität) für alle 51 Items neu, setzt für `0003`/`0024` das Feld auf leer + Label `superseded`. Die bereits bestehende Abbruchresilienz (`try/finally` um `save_state`, Item-für-Item-Verarbeitung, siehe `sync.py`) deckt einen Abbruch mitten in diesem Lauf bereits vollständig ab — dafür ist keine neue Logik nötig, exakt weil Status/Priorität nie eigenständiger Zustand sind, sondern jederzeit neu aus den Spec-Dateien ableitbar.

Dieser Rollout-Schritt braucht keine eigene Testabdeckung (er ist kein Code, sondern eine einmalige, gegen das echte Project ausgeführte Kommandofolge) — exakt dieselbe Einordnung wie der bestehende manuelle Smoke-Test in Spec 0031.

### 4. Marker-Namensraum: `photosort-spec` vs. `photosort-inbox`

Erste Zeile jedes Issue-Bodys bleibt ein versteckter Marker, aber mit Entitäts-Präfix: `<!-- photosort-spec: NNNN -->` (Features, unverändert) bzw. `<!-- photosort-inbox: NNNN -->` (neu, Inbox). Notwendig, weil die Nummernkreise unabhängig sind (Kontext, Punkt 3) — eine reine Zahl reicht nicht mehr als Identität.

### 5. Zustandsdatei: zwei Namensräume, rückwärtskompatibel

`specs/.github-sync-state.json` wechselt von einem flachen `{NNNN: entry}`-Objekt zu `{"features": {NNNN: entry}, "inbox": {NNNN: entry}}`. Kein manueller Migrationsschritt nötig: `load_state()` erkennt das alte, flache Format (keine Top-Level-Schlüssel `features`/`inbox`) und behandelt es transparent als `{"features": <bisheriger Inhalt>, "inbox": {}}`; jeder folgende `save_state()`-Aufruf schreibt bereits im neuen, genesteten Format. Einmalig selbstmigrierend, analog zum bereits etablierten Muster "Datei fehlt komplett → leerer Zustand" in `load_state()`.

### 6. Labels: neues generisches Self-Provisioning, `bug` wiederverwendet

Neuer `ensure_label(name, *, description, color)`-Baustein im `GhAdapter`-Protokoll (`gh label list --json name --limit 100` zur Existenzprüfung, `gh label create <name> --description ... --color ...` falls fehlend) — bewusst **ohne** die "hart abbrechen bei Drift"-Regel der Felder: Labels haben keine geschützte Options-Identität wie Single-Select-Felder (ein manuell umbenanntes/umgefärbtes Label ist unproblematisch, ändert keine Sync-Semantik). Neu provisioniert werden `idee` und `superseded`; das bereits vorhandene Repo-Label `bug` ("Something isn't working") wird für Inbox-Einträge mit `**Typ:** Bug (vermeintlich)` **wiederverwendet**, kein eigenes spezifischeres Label — inhaltlich deckungsgleich genug (ein Inbox-Bug-Eintrag *ist* ein Verdacht auf "etwas funktioniert nicht"), keine Rückfrage nötig, reine technische Detailentscheidung innerhalb der bereits akzeptierten Richtung. Labels werden pro Sync-Lauf voll reconciled (gesetzt, wenn zutreffend; entfernt, wenn nicht mehr zutreffend), symmetrisch zum bestehenden `_apply_fields`-Prinzip "jeder Lauf stellt den korrekten Zustand her".

### 7. CLI: `--only` bleibt rückwärtskompatibel, `inbox:NNNN` neu, `--supersede-inbox` für den Sharpening-Übergang

`--only NNNN` (nackte Zahl) bleibt unverändert Feature-Spec-Scope (kein Bruch für bestehende Aufrufer, insbesondere `idea-sharpener` Schritt 7). `--only inbox:NNNN` adressiert einen einzelnen Inbox-Eintrag. Ein voller Lauf ohne `--only` synct künftig automatisch **beide** Verzeichnisse (`specs/features/*.md` und `specs/inbox/*.md`) in einem Aufruf — kein separates Kommando für Inbox.

Neuer Flag `--supersede-inbox MMMM` (kombiniert mit `--only NNNN` beim Anlegen der neuen Spec): schließt gezielt das Issue des Inbox-Eintrags `MMMM` mit einem Kommentar, der auf das im selben Aufruf erzeugte/aktualisierte Spec-Issue verlinkt, und entfernt dessen State-Eintrag im `inbox`-Namensraum. Genau der Fall aus Rohtext-Punkt 5 des Inbox-Eintrags: `idea-sharpener` kennt zu diesem Zeitpunkt sowohl die alte Inbox- als auch die neue Spec-Nummer und ruft ohnehin `github-project-sync --only NNNN` auf (ADR 0017 Abschnitt 7) — die Erweiterung um `--supersede-inbox MMMM` liefert die Verlinkung, ohne einen vollen Repo-Scan zu benötigen.

Der bereits bestehende, generische Orphan-Cleanup-Pfad (`find_orphaned_numbers`, nur im Voll-Lauf ohne `--only` aktiv) wird symmetrisch auf den `inbox`-Namensraum erweitert, für den Fall, dass ein Inbox-Eintrag *nicht* über den Sharpening-Übergang, sondern anderweitig verschwindet (z.B. Daniel verwirft die Idee und löscht die Datei manuell) — dann mit generischem statt verlinkendem Kommentar ("Inbox-Eintrag wurde entfernt."), exakt analog zum bestehenden Verhalten für gelöschte Spec-Dateien.

### 8. Parsing: `inbox_parser.py` als schlanke Ergänzung, keine Duplikation

Das Markdown-Format von `specs/inbox/*.md` (H1 `# NNNN - Titel`, `**Status:**`-Zeile, Inhalts-Zone ab der ersten `## `-Überschrift) ist strukturell identisch zu dem der Feature-Specs — die bereits bestehende, generische Parsing-Funktion in `spec_parser.py` (H1/Status/Inhalts-Zone-Erkennung) wird direkt wiederverwendet statt dupliziert. Neu ist nur ein schlankes `inbox_parser.py`, das zusätzlich `**Typ:**` extrahiert (Werte: `Idee` | `Bug (vermeintlich)`, ansonsten nicht-fataler Warnfall wie ein unbekannter Spec-Status heute schon) und eine eigene Menge gültiger Statuswerte prüft (nur `Unrefined`). Kein `**Bezug:**`-Feld wird erwartet/geparst — die bestehende Parsing-Funktion sucht dieses Feld ohnehin nicht (nur H1, Status, Inhalts-Zone), betrifft die Wiederverwendung also gar nicht.

## Begründung

- **Delete+Recreate statt In-Place-Edit fürs Feld:** einzig technisch mögliche Option mit `gh` 2.97.0 (kein `field-edit`); Alternative wäre roher `gh api graphql`, den ADR 0017 bewusst vermeidet, wo native Subcommands ausreichen — und sie reichen hier aus, wenn man Löschen+Neuanlegen statt Editieren akzeptiert.
- **Migration außerhalb des Dauerbetrieb-Codes:** verhindert einen permanenten, riskanten "Feld bei Optionsabweichung automatisch neu anlegen"-Pfad, der dem in PR #115 bewusst gehärteten Hart-Abbruch-Prinzip bei Board-Drift widersprechen würde. Ein Einmalschritt ist ausreichend, weil danach nie wieder ein Feld namens `Status` mit falschen Optionen entstehen sollte (der Bug, der ADR 0017 zur Umbenennung in `Spec Status` bewogen hatte, entsteht nur bei automatischer Neuanlage eines *neuen* Projects — für das bereits bestehende, jetzt bereinigte Project tritt er nicht wieder auf).
- **Kein Datenverlust bei der Migration:** Status/Priorität sind laut ADR 0017 Abschnitt 4 explizit reine Einbahnstraßen-Spiegelung, nie Source of Truth — Löschen und Neu-Pushen ist datentechnisch folgenlos, exakt der Grund, warum keine gesonderte "lies alten Wert, schreib neuen Wert"-Migrationslogik nötig ist (vereinfacht Daniels ursprüngliche Annahme, dass eine Item-für-Item-Übertragung nötig wäre).
- **Superseded als Label statt Feldwert:** entspricht Daniels expliziter Entscheidung; das Leeren des Feldes statt eines Ersatzwerts vermeidet eine künstliche Bedeutungszuweisung (z.B. "letzter bekannter Wert") und nutzt ein bereits im Code etabliertes Muster (Feld leeren, wenn nicht zutreffend).
- **Gemeinsames Custom-Label-Provisioning ohne Drift-Härte:** Labels sind, anders als Single-Select-Feld-Optionen, keine strukturelle Enum-Identität mit Bedeutung für die Klassifikationslogik — ein manuell geändertes Label ist harmlos, ein manuell geändertes Feld-Options-Set ist es nicht (siehe bestehende `_apply_fields`-Begründung). Die unterschiedliche Behandlung ist daher konsistent, keine Inkonsistenz.
- **`bug`-Label wiederverwenden statt neu anlegen:** vermeidet Label-Wildwuchs für einen inhaltlich bereits abgedeckten Fall; Rückfrage an Daniel wäre hier unverhältnismäßig für eine rein technische Wahl innerhalb der bereits akzeptierten Richtung.
- **Marker-Präfix statt reiner Nummer:** einzige robuste Lösung für kollidierende Nummernkreise; Alternative (ein gemeinsamer Nummernkreis für Inbox+Features) hätte tief in ein etabliertes, unabhängiges Verzeichnis-/Nummerierungsschema eingegriffen (`.claude/skills/capture/SKILL.md`) und wäre eine viel größere, hier nicht angefragte Änderung gewesen.
- **Zustandsdatei-Migration automatisch statt manuell:** die Datei ist bereits ein reines Sync-Artefakt (kein von Menschen editiertes Format) — automatisches Erkennen des Altformats ist risikofrei und erspart einen weiteren manuellen Rollout-Schritt.
- **`inbox_parser.py` per Wiederverwendung statt Duplikation:** identisches Datei-Grundformat, keine Notwendigkeit für Parallel-Regex-Wartung zweier praktisch gleicher Parser.

## Konsequenzen

- **Betrifft `scripts/github-project-sync/src/github_project_sync/`:**
  - `gh_adapter.py`: `STATUS_FIELD_NAME` zurück auf `"Status"`, `STATUS_OPTIONS` auf `["Proposed", "Accepted", "Implemented", "Unrefined"]`; neue `ensure_label()`-Methode im `GhAdapter`-Protokoll (+ `GhCliAdapter`-Implementierung, + `FakeGhAdapter` in `tests/fakes.py`).
  - `spec_parser.py`: unverändert (Kern-Parsing-Funktion wird von `inbox_parser.py` wiederverwendet).
  - Neu: `inbox_parser.py` (Parsing inkl. `**Typ:**`, Status-Validierung nur `Unrefined`).
  - `issue_body.py`: Marker-Funktionen um Entitäts-Präfix (`photosort-spec`/`photosort-inbox`) erweitert.
  - `state.py`: Umstellung auf `{"features": {...}, "inbox": {...}}`, rückwärtskompatibles Lesen des alten Flach-Formats.
  - `sync.py`: `_apply_fields`/`_sync_one` um Label-Reconciliation (`superseded`/`idee`/`bug`), Superseded-Feld-Leerung, Inbox-Sync-Pfad (eigene Statusmenge, keine Priorität, `Unrefined` = offen), erweiterten Orphan-Cleanup (Inbox-Namensraum), `--supersede-inbox`-Verhalten erweitert.
  - `cli.py`: `--only` um `inbox:NNNN`-Präfix, neuer Flag `--supersede-inbox`, JSON-Ausgabe um `"inbox"`-Zweig ergänzt.
  - `roadmap_parser.py`: unverändert (Inbox hat keine Priorität).
- **`.claude/skills/github-project-sync/SKILL.md`:** muss den neuen `"inbox"`-Ausgabezweig, `inbox:NNNN`-Scope und `--supersede-inbox` dokumentieren.
- **`.claude/skills/idea-sharpener/SKILL.md`:** letzter Schritt ruft künftig `github-project-sync --only NNNN --supersede-inbox MMMM` auf (statt nur `--only NNNN`), wenn die Spec aus einem Inbox-Eintrag hervorging.
- **Rollout:** einmaliger, manueller Feld-Bereinigungsschritt gegen das echte Project (siehe Abschnitt 3) muss vor bzw. unmittelbar nach dem Deploy des neuen Codes ausgeführt werden — kein CI-Schritt, keine automatisierte Migration.
- **Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/`docs/ai-workflow.md`/Root-`README.md`** — unverändert reines Entwickler-/Prozess-Tooling ohne PhotoSort-System-/Datenmodell-Bezug, exakt dieselbe Einordnung wie ADR 0017/Spec 0031.
- **ADR 0017 bleibt Accepted und in Kraft** für alle Abschnitte außer dem hier abgelösten Teil von Abschnitt 3 (Feldname/-optionen); erhält einen kurzen, klar markierten Nachtrag-Verweis auf diese ADR, keine Änderung an Kontext/Begründung/Konsequenzen von 0017 selbst.
- Ein späterer, erneuter Wechsel des Feld-/Label-Modells bleibt architekturrelevant und braucht wiederum eine neue ADR.
