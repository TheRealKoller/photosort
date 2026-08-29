# 0043 - Spec-Nummer = Issue-Nummer, `github-project-sync` entfällt zugunsten eines dünnen Board-Helfers

**Status:** Accepted
**Datum:** 2026-08-29
**Bezug:** GitHub-Issue [`#262`](https://github.com/TheRealKoller/photosort/issues/262) ("github-project-sync-Tool komplett entfernen", führt die als Duplikat geschlossene Idee [`#184`](https://github.com/TheRealKoller/photosort/issues/184) zusammen), `specs/features/0262-github-project-sync-tool-entfernen.md` (neu, aus dieser ADR hervorgegangen), ADR [`0017`](./0017-github-projects-v2-spec-sync.md) (**Superseded** durch diese ADR), ADR [`0030`](./0030-github-sync-natives-status-feld-inbox-einbindung.md) (Abschnitt 2/6 — Superseded-Label und Story-Typ-Labels, teilweise abgelöst), ADR [`0036`](./0036-github-issue-natives-story-refinement-inbox-entfaellt.md) (Story-Lebenszyklus über GitHub-Issues — inhaltlich unverändert gültig, nur das ausführende Werkzeug wechselt), ADR [`0037`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) (Statuswerte und Übergänge — unverändert gültig, Baseline/Override-Mechanik entfällt), ADR [`0039`](./0039-prioritaet-nativ-im-board-roadmap-entfaellt.md), ADR [`0041`](./0041-feature-spec-content-sync-nur-noch-push.md) (**Superseded** durch diese ADR), ADR [`0042`](./0042-pre-merge-finalisierung-statt-nachzieh-pr.md) (Pre-Merge-Finalisierung bleibt Regelweg)

## Kontext

`scripts/github-project-sync` ist über ADR 0017 → 0030 → 0036 → 0037 → 0039 → 0041 gewachsen und bereits zweimal verschlankt worden. Nach dem letzten Schritt (ADR 0041, PR #261) bleiben ~2000 Zeilen Python, 198 Tests und ein eigener CI-Job für im Kern vier Aufgaben:

1. **Nummern-Mapping** Spec-Nummer ↔ Issue-Nummer, persistiert in `specs/.github-sync-state.json` (zusammen mit `item_id`, `pushed_state_hash`, `runtime_status`, `pr_number`).
2. **Content-Push** des vollen Spec-Inhalts in den Issue-Body, inklusive Marker-Kommentar (`<!-- photosort-spec: NNNN -->`), Hash-Berechnung, Klassifikation (`created`/`pushed`/`unchanged`), Waisen-Erkennung und Adoption (`--adopt-issue`).
3. **Status-Projektion** Datei-Status → Board-Spalte, verfeinert durch einen lokal gespiegelten Laufzeit-Override (`In Progress`/`Review`).
4. **Dateiloser Story-Pfad** (`--create-issue`, `--only issue:NNN`, `--show-status`) für Stories, die es nur als Issue gibt.

Punkt 1 ist der strukturelle Grund für fast alles andere: Weil eine Spec eine eigene, unabhängig hochzählende Nummer hat, braucht es eine persistierte Abbildung auf das Issue — und weil es diese Zustandsdatei ohnehin gibt, sind `item_id`, Hashes und Laufzeit-Override mit hineingewachsen. Nur Punkt 2 rechtfertigt für sich genommen einen echten Sync-Begriff; Punkt 3 und 4 sind einzelne, zustandslose Schreibzugriffe.

Daniel möchte das GitHub-Project-Board als alleinige zentrale Stelle für Issues und Status. Damit ist Punkt 2 nicht mehr gewollt (der Issue-Body soll die *Story* tragen, nicht eine zweite Kopie der technischen Spec), und Punkt 1 lässt sich strukturell auflösen, statt ihn weiter zu pflegen.

## Entscheidung

### 1. Neue Feature-Specs bekommen die Nummer ihres GitHub-Issues

Eine Spec, die aus Issue `#NNN` hervorgeht, heißt `specs/features/<NNN auf 4 Stellen>-titel.md` — die Spec für Issue #262 also `0262-github-project-sync-tool-entfernen.md`. Es gibt keine eigene, fortlaufende Spec-Nummerierung mehr.

Damit ist die Abbildung Spec ↔ Issue eine Identität statt einer gespeicherten Relation. Der Sprung in der Dateiliste (0066 → 0262) ist der bewusst in Kauf genommene Preis; die Nummer ist eine Kennung, keine Reihenfolgeangabe (die Reihenfolge lebt ohnehin im Board).

**Bestehende Specs 0001–0065 behalten ihre Nummer.** Keine retroaktive Umbenennung, keine Anpassung bestehender Querverweise — eine Umbenennung würde jeden Verweis in ADRs, Specs, Skills, Commits und PR-Beschreibungen brechen, ohne irgendetwas zu verbessern. Für sie gilt weiterhin, dass Spec-Nummer und Issue-Nummer auseinanderfallen; wo ein Werkzeug die Issue-Nummer einer Altspec braucht, wird sie explizit übergeben (siehe Abschnitt 4, `--issue`).

### 2. `specs/.github-sync-state.json` entfällt ersatzlos

Die vier gespeicherten Felder werden nicht mehr gebraucht bzw. anders beschafft:

- `issue_number`: entfällt (Identität, Abschnitt 1).
- `item_id`: wird zur Laufzeit aus `gh project item-list` über die Issue-Nummer aufgelöst, statt zwischengespeichert zu werden. Ein zusätzlicher Lesezugriff pro Schreiboperation ist bei der realen Aufrufhäufigkeit (wenige Aufrufe pro Feature) irrelevant und beseitigt die Klasse "State-Eintrag zeigt auf ein Item, das es nicht mehr gibt".
- `pushed_state_hash`: entfällt mit dem Content-Push (Abschnitt 3).
- `runtime_status` / `pr_number`: entfallen. Der Board-Wert *ist* der Status — er wird direkt gesetzt und direkt gelesen, statt lokal gespiegelt zu werden. Die PR-Nummer wird beim Finalisieren übergeben bzw. aus den verknüpften, schließenden PRs des Issues aufgelöst (Abschnitt 4).

Die Datei wird gelöscht. Für die 65 Altspecs geht damit eine historische Abbildung verloren; alle bis auf die Ausnahme unten sind abgeschlossen (`Implemented`/`Superseded`) und brauchen keinen Board-Zugriff mehr. Die Issue-Nummer einer Altspec steht weiterhin in deren `**Bezug:**`-Zeile.

### 3. Kein Content-Push mehr: Issue-Body = Story, Spec-Datei = Technik

Der Issue-Body trägt künftig ausschließlich das, was `refinement` hineinschreibt (Ziel, User Story, Akzeptanzkriterien, Priorisierungs-Empfehlung, Out of Scope). Der technische Teil der Spec (Architektur/Umsetzung, UI/UX, Security, Teststrategie, Entscheidungen) lebt nur in `specs/features/` und wird **nicht** in den Issue-Body gespiegelt.

Damit entfallen ersatzlos: Marker-Kommentar und dessen Integritätsprüfung, `hashing.py`, `classify.py`, `issue_body.py`, die Waisen-Erkennung (`orphaned`), der Adoptionsmodus (`--adopt-issue`) und der volle Lauf über alle Spec-Dateien.

Begründung: Die zweite Kopie war nie eine eigene Quelle der Wahrheit, sondern nur Bequemlichkeit beim Lesen im Browser — und genau sie hat den größten Teil der Komplexität (Hashes, Klassifikation, Marker, Konfliktbehandlung) erzeugt. Wer den technischen Stand braucht, liest die Spec-Datei im Repo; sie ist über die identische Nummer eindeutig zum Issue zugeordnet.

Folge für `Superseded`: Das automatisch verwaltete `superseded`-Label und das Leeren des Board-Feldes entfallen. Eine abgelöste Spec wird im Board wie eine erledigte behandelt (`Done`, Issue geschlossen); die Ablösung selbst steht in der Spec-Datei, wo sie ohnehin nachgelesen wird.

### 4. Ersatz ist ein einzelnes, dünnes Helferscript: `scripts/gh-board.py`

Die fehleranfällige Projects-V2-Logik (Projekt-/Feld-/Options-/Item-ID-Auflösung, Setzen eines Single-Select-Werts) bleibt an **einer** Stelle gebündelt und automatisiert getestet — sie wird ausdrücklich **nicht** als `gh`-Aufrufe über die Skill-Dateien verstreut. Das Script ist ein einzelnes Modul im bestehenden `scripts/`-Paket, kein eigenes Python-Package:

- Tests unter `scripts/tests/test_gh_board.py`, gegen ein injiziertes `run`-Callable (dieselbe Technik wie im bisherigen `test_gh_adapter.py`) — kein Netzwerk, kein echtes `gh` in CI.
- Abgedeckt vom bereits bestehenden CI-Job `demo-scripts` (ruff + pytest über `scripts/`). Der eigene CI-Job `github-project-sync` entfällt.
- Kein `shell=True`, Argumente ausschließlich in Listenform, Bodies über temporäre Dateien — die Härtungsregeln aus ADR 0017, Abschnitt 5, bleiben unverändert gültig.
- **Keine Selbst-Provisionierung mehr:** Projekt und Statusfeld werden nur noch aufgelöst, nicht angelegt. Das Anlegen war ein Bootstrap-Pfad für ein Board, das es längst gibt; ein versehentlich erzeugtes zweites Projekt oder ein neu angelegtes Feld mit abweichenden Optionen wäre deutlich schädlicher als ein klarer Fehler. Eine geänderte Optionsliste bleibt der einmalige manuelle Schritt aus ADR 0030, Abschnitt 3. Das Repo-Label `idee`/`bug` wird weiterhin bei Bedarf angelegt (billig, ohne Verwechslungsgefahr).

Befehlsoberfläche (JSON auf stdout, `{"error": "..."}` im Fehlerfall — Aufrufkonvention wie bisher):

| Befehl | Zweck | Aufrufer |
|---|---|---|
| `create-issue --type idee\|bug --title T --body-file P` | Issue anlegen, Label setzen, ins Project aufnehmen, Status `Unrefined` | `capture` |
| `set-body --issue N --body-file P` | Issue-Body überschreiben | `refinement` |
| `set-status --issue N --status S` | Board-Status setzen (`Done` schließt das Issue zusätzlich) | `refinement`, `spec-writer`, `developer`, `ship-feature` |
| `show-status --issue N` | Board-Status lesen (rein lesend) | `spec-writer` |
| `finalize --spec NNNN [--issue N] [--pr-number M]` | Spec-Datei auf `Implemented ([PR #M](url))`, Board `Done`, Issue schließen | `ship-feature` |

`set-status` akzeptiert alle sechs Board-Werte (`Unrefined`, `Ready`, `Todo`, `In Progress`, `Review`, `Done`) direkt. Die Baseline/Override-Mechanik aus ADR 0037, Abschnitt 2, entfällt: Sie existierte nur, weil ein voller Lauf den Board-Wert jederzeit aus der Datei neu berechnen können musste. Ohne vollen Lauf gibt es nichts zu überschreiben — die Statuswerte und die Übergänge zwischen ihnen (ADR 0037, Abschnitt 1/3/4/6) bleiben unverändert, nur ihre Berechnung entfällt.

`finalize` ohne `--pr-number` löst den gemergten, das Issue schließenden PR über `gh issue view --json closedByPullRequestsReferences` auf. Das ist der Ersatz für die bisherige automatische PR-Merge-Erkennung (`finalized_from_pr`, ADR 0037, Abschnitt 5) und deckt weiterhin den Ausnahmefall ab, dass ein PR ohne vorherige Finalisierung gemergt wurde. Regelweg bleibt die Pre-Merge-Finalisierung mit explizitem `--pr-number` (ADR 0042) — daran ändert sich nichts.

`--issue` ist der Ausweg für die Altspecs aus Abschnitt 1, deren Nummer nicht der Issue-Nummer entspricht; ohne die Angabe gilt die Identität.

### 5. Ein konsolidierender Skill statt eines Sync-Skills

`.claude/skills/github-project-sync/` wird durch `.claude/skills/github-board/` ersetzt: derselbe dünne Wrapper-Charakter (keine fachliche Entscheidung im Skill), aber ohne Sync-Begriff — es wird nichts mehr abgeglichen, es werden einzelne Board-Operationen ausgeführt. `capture`, `refinement`, `spec-writer`, `ship-feature` und der `developer`-Agent rufen das Script über diesen Skill auf.

Ein manuell angestoßener "voller Sync-Lauf" entfällt ersatzlos — es gibt nichts mehr, was auseinanderlaufen könnte.

## Konsequenzen

**Positiv:**

- ~2000 Zeilen Python, 198 Tests und ein CI-Job weniger; das Ersatzscript liegt in derselben Größenordnung wie ein einzelnes Modul des alten Pakets.
- Keine eingecheckte Zustandsdatei mehr, die bei jedem Feature mitgeführt und committet werden muss — auch der letzte Grund für den in ADR 0042 bekämpften Nachzieh-PR verschwindet.
- Kein Auseinanderlaufen zwischen drei Kopien derselben Information (Spec-Datei, Issue-Body, State-Datei) mehr möglich; es gibt nur noch zwei klar getrennte Inhalte (Story im Issue, Technik in der Spec-Datei).

**Negativ / bewusst in Kauf genommen:**

- Der technische Spec-Inhalt ist im Browser nicht mehr im Issue lesbar, sondern nur im Repo (Abschnitt 3).
- Kein selbstheilender voller Lauf mehr: Wird ein Board-Wert manuell verstellt, korrigiert ihn kein Werkzeug automatisch zurück. Das ist die logische Folge davon, das Board zur zentralen Stelle zu erklären.
- Die Dateiliste unter `specs/features/` ist nicht mehr lückenlos fortlaufend.
- Ein Board mit mehr als 100 Items bräuchte Pagination in `gh project item-list` (heute ~70 Items, dieselbe bereits in ADR 0017 dokumentierte und akzeptierte Grenze).

**Migrationsschritt (einmalig, manuell):** Spec `0065` steht auf `main` noch auf `Accepted`, obwohl ihr PR #261 gemergt ist — die bisherige Merge-Erkennung ist nie gelaufen. Sie wird mit demselben `finalize`-Aufruf nachgezogen (`--spec 0065 --issue 240`), sobald das neue Script auf `main` ist. Am Board selbst (Feldname, Optionen) ändert sich nichts, ein Migrationsschritt wie bei ADR 0030/0036/0037 ist nicht nötig.
