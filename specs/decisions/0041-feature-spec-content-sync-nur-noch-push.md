# 0041 - Bidirektionaler Content-Sync für Feature-Specs entfällt, Issue-Body bleibt reiner Push-Spiegel

**Status:** Accepted
**Datum:** 2026-08-28
**Bezug:** GitHub-Issue [`#240`](https://github.com/TheRealKoller/photosort/issues/240) (führt die separat erfasste Idee [`#219`](https://github.com/TheRealKoller/photosort/issues/219)/`specs/inbox/0042-adr-0017-content-sync-vereinfachen.md` zusammen — `#219` wurde als Duplikat geschlossen, die Inbox-Datei wird mit Umsetzung dieser ADR gelöscht), `architect`-Konsultation im `spec-writer`-Ablauf für die daraus hervorgehende Feature-Spec. Löst ADR [`decisions/0017-github-projects-v2-spec-sync.md`](./0017-github-projects-v2-spec-sync.md) Abschnitt 4 (Pull-Teil) und Abschnitt 6 (Hash-Konfliktmechanismus) ab — siehe Abschnitt "Abgelöste Vorentscheidungen". Ergänzt die bereits laufende iterative Vereinfachung aus ADR [`0036`](./0036-github-issue-natives-story-refinement-inbox-entfaellt.md)/[`0037`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md)/[`0039`](./0039-prioritaet-nativ-im-board-roadmap-entfaellt.md).

## Kontext

`scripts/github-project-sync` synct seit ADR 0017 Feature-Specs bidirektional mit GitHub Issues: der volle Spec-Inhalt (Inhalts-Zone ab `## Ziel`) wird in den Issue-Body gespiegelt (Push), und eine dort direkt vorgenommene Änderung wird per Hash-Vergleich gegen eine committete Baseline erkannt und automatisch in die Spec-Datei zurückgeschrieben (Pull, Klassifikation `pulled`), inklusive `conflict`-Fall (beide Seiten geändert) und anschließender fachlicher Bewertung eines Pulls durch `requirements-engineer`.

Seit der mit ADR 0036 vollzogenen Trennung von Story-Refinement (fachliche Klärung passiert jetzt vollständig vorher im GitHub-Issue, bevor überhaupt eine Spec-Datei entsteht) sind Feature-Specs unter `specs/features/*.md` nur noch technische Umsetzungspläne. Niemand bearbeitet diesen Inhalt mehr im GitHub-Issue-Textfeld — die einzige Instanz, die daran je etwas ändert, ist der Sync selbst (Push). Der gesamte Pull-Zweig (Hash-Vergleich der Issue-Body-Inhalts-Zone, `pulled`/`conflict`-Klassifikation, `--resolve`-Konfliktauflösung, `requirements-engineer`-Bewertung zurückgespielter Inhalte) beantwortet damit ein Problem, das strukturell nicht mehr auftritt: eine zweite, potenziell abweichende Kopie des Inhalts entsteht gar nicht mehr, da niemand mehr am Issue-Body schreibt.

Verifiziert (Code-Lesung `scripts/github-project-sync/src/github_project_sync/`): `extract_content_zone_from_issue_body` (`issue_body.py`) und `replace_content_zone` (`spec_parser.py`) haben ausschließlich den Pull-Pfad in `sync.py::_sync_one()` als Aufrufer — beide sind vollständig entfernbar, ohne einen anderen Verwendungszweck zu berühren. Der Status-/Priorität-Sync (Abschnitt 4, Push-Teil, unverändert Einbahnstraße), die automatische PR-Merge-Erkennung (ADR 0037) und der dateilose Story-Pfad (ADR 0036) sind vom Pull-Mechanismus vollständig unabhängig und bereits heute rein push-/lese-basiert.

Diese ADR ist wie 0017/0036/0037/0039 eine Prozess-/Tooling-Entscheidung für den KI-Entwicklungsprozess selbst, kein Eingriff in PhotoSorts Technologie-Stack, Datenmodell oder Laufzeitsystem. Sie wird als ADR festgehalten, weil sie eine als architekturrelevant markierte Grundsatzentscheidung (ADR 0017, bidirektionaler Content-Sync samt Konfliktmodell) revidiert.

## Entscheidung

### 1. Pull-Mechanismus, Hash-Konfliktmodell und `pulled`/`conflict`-Klassifikation entfallen vollständig für Feature-Specs

Entfernt werden:

- Das Lesen/Extrahieren der Issue-Body-Inhalts-Zone zum Vergleich (`issue_body.py::extract_content_zone_from_issue_body`).
- Das Zurückschreiben in die Spec-Datei (`spec_parser.py::replace_content_zone`).
- Die Klassifikationswerte `pulled`/`conflict` (`classify.py::SyncClassification` wird auf `Literal["created", "pushed", "unchanged"]` verengt).
- Das Feld `pulled_body_hash` im `SyncStateEntry` (`classify.py`) sowie im persistierten `specs/.github-sync-state.json` (`state.py`) — die verbleibende Klassifikation basiert ausschließlich auf einem Vergleich von `push_state_hash(status, content_zone)` gegen die gespeicherte `pushed_state_hash`-Baseline.
- `ConflictDiff`, `SpecSyncResult.conflict`, `SpecSyncResult.pulled_content_zone`, der `resolutions`-Parameter von `run_sync()`, das CLI-Flag `--resolve` (inkl. `_parse_resolutions`).
- Die zugehörige "Aufgabe 3" (Refinement-Bewertung zurückgespielter Inhalte) in `.claude/agents/requirements-engineer.md` — entfällt ersatzlos, da der Fall, den sie behandelt, nicht mehr eintreten kann.
- Der bereits seit ADR 0039 tote `hashing.py::push_state_hash_inbox` (kein Aufrufer mehr seit Spec 0059) — wird bei dieser Gelegenheit mit entfernt, da diese ADR ohnehin dieselben Dateien anfasst und explizit auf Codevolumen-Reduktion zielt.

### 2. Content-**Push** (Spec-Inhalt → Issue-Body) bleibt unverändert vollständig erhalten — keine Kurzfassung

Bewusst **nicht** übernommen wird der in der zusammengeführten Idee #219 vorgeschlagene weitergehende Schnitt ("nur noch Status/Priorität + Link/kurze fachliche Zusammenfassung ins Issue pushen"). Der volle Spec-Inhalt (Marker-Kommentar + komplette Inhalts-Zone, `issue_body.py::build_issue_body`) wird weiterhin bei jeder inhaltlichen Änderung in den Issue-Body geschrieben (`gh.edit_issue_body`), exakt wie heute — nur eben nie mehr zurückgelesen.

Begründung gegen die Kurzfassung:

- Keines der Akzeptanzkriterien der zugehörigen Story fordert eine Reduktion des Push-Inhalts — sie fordern ausschließlich den Wegfall von Rückfluss/Konflikterkennung/Klassifikation `pulled`/`conflict`. Das mit "spürbar sinkender Codeumfang" formulierte Kriterium ist bereits durch den Wegfall des gesamten Pull-/Hash-Konflikt-Zweigs erfüllt (siehe Konsequenzen) — eine zusätzliche Reduktion des Push-Inhalts würde denselben Zielwert nicht nennenswert weiter verbessern, aber zusätzliche, hier nicht geforderte Änderungen an einem bereits dokumentierten, aktiv genutzten Skill-Verhalten erzwingen.
- `spec-writer`, letzter Schritt (`--adopt-issue`), dokumentiert explizit und aktuell genutzt: "schreibt erstmals den Marker-Kommentar ... plus den vollen Spec-Inhalt in den Issue-Body". Eine Kurzfassung hätte dieses bereits etablierte, funktionierende Verhalten ohne zwingenden Grund gebrochen.
- Der volle Spiegel behält für Daniel den Wert, den vollständigen technischen Umsetzungsplan direkt auf GitHub (auch mobil) lesen zu können, ohne den Umweg über den Checkout des Repos — dieser Lesenutzen entfällt nicht dadurch, dass niemand mehr *schreibend* darin arbeitet.
- Der Push-Mechanismus selbst (`build_issue_body`, `edit_issue_body`, unveränderte `push_state_hash`-Berechnung aus Status+Inhalts-Zone) ist bereits heute einfacher, einseitiger, ungetesteter Komplexität nicht ausgesetzt — er war nie Teil des in Abschnitt 1 entfernten Mechanismus.

### 3. Vereinfachte Klassifikation: reiner Baseline-Vergleich statt Vier-Wege-Fallunterscheidung

`classify()` (`classify.py`) reduziert sich auf einen einzigen Vergleich: `stored is None → "created"`, sonst `push_hash_now != stored.pushed_state_hash → "pushed"`, sonst `"unchanged"`. Der `push_state_hash(status, content_zone)`-Aufbau selbst (Statuswert + Inhalts-Zone, unverändert seit ADR 0039) bleibt bestehen — er entscheidet weiterhin, ob `edit_issue_body` überhaupt aufgerufen wird (Vermeidung unnötiger API-Calls) und liefert weiterhin eine sinnvolle Zusammenfassung ("N Specs gepusht, M unverändert") an Daniel.

`_sync_one()` (`sync.py`) behält die Marker-Integritätsprüfung (`parse_marker(issue.body)` gegen die erwartete Spec-Nummer) unverändert bei — sie schützt weiterhin davor, versehentlich in ein falsch zugeordnetes Issue zu schreiben, ein von Pull/Konflikt unabhängiges Schutzbedürfnis, das durch diese ADR nicht berührt wird.

### 4. Kein neuer manueller Migrationsschritt nötig

Anders als bei den Statuswert-Änderungen in ADR 0030/0036/0037 (die eine Board-Feld-Neuanlage erzwangen) betrifft diese Änderung ausschließlich das Format der lokalen, eingecheckten `specs/.github-sync-state.json` sowie internen Python-Code — kein GitHub-seitiges Feld ändert sich. Ein bereits vorhandener `pulled_body_hash`-Schlüssel in einem bestehenden State-Eintrag wird von der angepassten `state.py::_parse_namespace()` beim Lesen schlicht nicht mehr referenziert (kein `KeyError`, kein Absturz) und beim nächsten `save_state()`-Aufruf stillschweigend nicht mehr mitgeschrieben — selbstheilend, ohne manuellen Eingriff.

## Abgelöste Vorentscheidungen

- **ADR 0017 Abschnitt 4, Satz 2** ("Nur der Inhalt unterhalb des Metadaten-Blocks ist bidirektional") ist für Feature-Specs abgelöst: der Inhalt ist ab jetzt strikt unidirektional (Spec-Datei → Issue-Body), identisch zur bereits bestehenden Status-Einbahnstraße im selben Abschnitt (Satz 1, unverändert gültig).
- **ADR 0017 Abschnitt 6** (Hash-basierte Vier-Wege-Konflikterkennung `created`/`pushed`/`pulled`/`conflict`/`unchanged`) ist für Feature-Specs abgelöst — ersetzt durch die in Abschnitt 3 dieser ADR beschriebene Drei-Wege-Klassifikation ohne Pull/Konflikt-Fall.
- **ADR 0017 Abschnitt 5** (Aufzählung der Komponenten) bleibt im Übrigen unverändert gültig, verweist aber nach Umsetzung dieser ADR auf einen entsprechend schmaleren Funktionsumfang.
- Alle übrigen Abschnitte von ADR 0017 (1–3, 7) sowie ADR 0036/0037/0039 vollständig bleiben unverändert gültig — diese ADR editiert sie nicht nachträglich, sondern löst die oben einzeln benannten Teile ab (gleiches Muster wie in ADR 0039 Abschnitt "Abgelöste Vorentscheidungen").

## Begründung

- **Strukturwegfall statt Abbau eines noch benötigten Mechanismus:** wie schon bei ADR 0036 (Wegfall des Inbox-Pull, weil eine Story nur eine Kopie der Wahrheit hat) ist die tragende Beobachtung, dass das Problem, das der Pull-/Konfliktmechanismus lösen sollte (zwei divergierende Kopien desselben Inhalts), für Feature-Specs seit ADR 0036 strukturell nicht mehr auftreten kann — Entfernen des Mechanismus ist deshalb kein Funktionsverlust, sondern das Aufräumen von totem Code für einen bereits verschwundenen Anwendungsfall.
- **Push bleibt voll, keine Kurzfassung:** siehe Abschnitt 2 — die Akzeptanzkriterien fordern das nicht, und eine Kurzfassung hätte unnötig ein bereits dokumentiertes, funktionierendes Skill-Verhalten (`spec-writer`/`--adopt-issue`) gebrochen, ohne den Codevolumen-Zielwert nennenswert weiter zu verbessern.
- **Kein neuer Migrationsschritt:** das JSON-Zustandsformat verträgt den Wegfall eines Feldes bereits über das bestehende `dict.get()`/explizite-Schlüssel-Muster in `state.py`, ohne eigene Migrationslogik — konsistent mit dem in ADR 0037 etablierten Prinzip, Migrationsaufwand proportional zum tatsächlichen Risiko zu halten (hier: kein Risiko, da rein additiv/subtraktiv über bereits vorhandene, defensive Lesepfade).

## Konsequenzen

- **`scripts/github-project-sync/src/github_project_sync/`:**
  - `issue_body.py`: `extract_content_zone_from_issue_body` entfernt; `build_issue_body`/`parse_marker` unverändert.
  - `spec_parser.py`: `replace_content_zone` entfernt; `set_status_line`/`parse_spec_file`/`validate_spec_number` unverändert.
  - `classify.py`: `SyncClassification` auf `Literal["created", "pushed", "unchanged"]` verengt; `classify()` auf Baseline-Vergleich reduziert; `SyncStateEntry.pulled_body_hash` entfernt (`runtime_status`/`pr_number` aus ADR 0037 bleiben unverändert).
  - `hashing.py`: `push_state_hash_inbox` entfernt (tot seit ADR 0039); `push_state_hash`/`text_hash` unverändert.
  - `state.py`: `_parse_namespace`/`_serialize_namespace` lesen/schreiben `pulled_body_hash` nicht mehr.
  - `sync.py`: `_sync_one()` verliert den gesamten Pull-/Konflikt-Zweig (`ConflictDiff`, `resolution`-Parameter, `effective`-Auflösung, `elif effective == "pulled"`-Zweig); `Resolution`-Typalias entfernt; `run_sync()` verliert den `resolutions`-Parameter; `SpecSyncResult` verliert `conflict`/`pulled_content_zone`. `_adopt_story_and_push_first_content()` verhaltensunverändert (nutzt bereits nur den Push-Pfad) — verliert lediglich mechanisch das `pulled_body_hash`-Feld aus dem `SyncStateEntry`-Konstruktoraufruf, erzwungen durch den Wegfall des Dataclass-Felds selbst.
  - `cli.py`: `--resolve`-Flag und `_parse_resolutions` entfernt (nach demselben, bereits etablierten Muster wie `--supersede-inbox`/`inbox:`-Stub: ein versehentlich noch verwendetes `--resolve` liefert eine klare `{"error": "..."}`-Meldung statt eines generischen argparse-Fehlers); `_result_to_dict` verliert `conflict`/`pulled_content_zone`.
  - Tests entsprechend gekürzt: `test_classify.py`, `test_issue_body.py`, `test_spec_parser.py` (jeweils die auf Pull/`replace_content_zone`/`extract_content_zone_from_issue_body` bezogenen Fälle), `test_sync_integration.py`/`test_cli.py` (alle `conflict`/`pulled`/`--resolve`-Testfälle) — deutliche Reduktion der 216 bestehenden Tests, konkrete Zielzahl legt `test-engineer` im weiteren `spec-writer`-Ablauf fest.
- **`.claude/agents/requirements-engineer.md`:** "Aufgabe 3" (Refinement-Bewertung zurückgespielter GitHub-Inhalte) entfällt vollständig; Frontmatter-Beschreibung (Punkt 2) entsprechend gekürzt.
- **`.claude/skills/github-project-sync/SKILL.md`:** Frontmatter-Beschreibung (kein "inhaltliche Änderungen ... fließen zurück" mehr), Abschnitte "Konflikte — nie automatisch auflösen" und "`pulled`-Fälle — Refinement-Bewertung durch `requirements-engineer`" entfallen, "Pro-Spec-Ergebnisse auswerten" entsprechend gekürzt (kein `conflict`/`pulled_content_zone` mehr im JSON).
- **`.claude/skills/spec-writer/SKILL.md`:** keine Änderung — der dort beschriebene volle Content-Push bei `--adopt-issue` bleibt unverändert gültig (siehe Abschnitt 2).
- **`specs/inbox/0042-adr-0017-content-sync-vereinfachen.md`:** wird mit Umsetzung dieser ADR gelöscht (durch Issue #240/diese ADR inhaltlich aufgelöst, analog zum bereits etablierten Muster "nach erfolgreicher Verfeinerung wird die Inbox-Datei gelöscht").
- **Kein** Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md` — reines Entwickler-/Prozess-Tooling ohne PhotoSort-System-/Datenmodell-Bezug, identische Einordnung wie ADR 0017/0036/0037/0039. `docs/ai-workflow.md` ist ebenfalls nicht betroffen (beschreibt den Skill-Workflow auf einer Flughöhe, die den internen Pull-/Push-Mechanismus nicht referenziert).
- **Kein manueller Migrationsschritt** — siehe Abschnitt 4.
- Ein späterer Wiedereinstieg in einen bidirektionalen Content-Sync für Feature-Specs oder eine nachträgliche Reduktion des Push-Inhalts auf eine Kurzfassung bleibt architekturrelevant und braucht eine neue, diese ADR als "Superseded" markierende ADR.
