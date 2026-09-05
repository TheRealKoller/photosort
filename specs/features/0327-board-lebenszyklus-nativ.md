# 0327 - Board-Lebenszyklus nativ: `Todo` entfällt, `gh-board.py` wird gelöscht

**Status:** Implemented ([PR #328](https://github.com/TheRealKoller/photosort/pull/328))
**Erstellt:** 2026-09-05
**Bezug:** GitHub-Issue [`#327`](https://github.com/TheRealKoller/photosort/issues/327) („Flow für tickets neu denken"), löst [`#305`](https://github.com/TheRealKoller/photosort/issues/305) mit ab. Architekturentscheidung: ADR [`0057`](../decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md).

## Ziel

Der Ticket-Fluss von PhotoSort ist an zwei Stellen erkennbar schief.

**Erstens bildet die Board-Spalte `Todo` keinen Zustand ab, den Daniel je beobachtet.** Sie wird gesetzt, sobald eine Spec akzeptiert ist, und wenige Augenblicke später von der beginnenden Umsetzung überschrieben. Was dort tatsächlich liegenbleibt, sind Altlasten — Issues, an denen niemand arbeitet und die schlicht vergessen wurden. Die Spalte kostet einen Arbeitsschritt und liefert keine Übersicht. Dazu kommt eine zweite, bisher unbenannte Abweichung: Die Umsetzung soll als begonnen gelten, sobald sie beginnt — einschließlich des Schreibens der Spec. Heute entsteht die Spec, bevor die Story überhaupt als „in Arbeit" sichtbar wird.

**Zweitens hängt die gesamte Board-Pflege an einem selbstgebauten Werkzeug** von rund 1.500 Zeilen Code mit über 3.000 Zeilen Tests, dessen Aufgabe im Kern darin besteht, an einem Issue ein Auswahlfeld zu setzen und den Beschreibungstext zu schreiben. Jede Änderung am Ablauf zieht Pflegeaufwand an diesem Werkzeug nach sich; es ist bereits sechsmal nachgebessert worden. Das ist Eigenbau-Infrastruktur für etwas, das GitHub zu großen Teilen selbst kann.

Zur Begründung ausdrücklich festgehalten: Die ursprünglich vermutete Ersparnis an KI-Tokens trägt diesen Umbau **nicht** — ein Board-Schreibzugriff kostet heute praktisch nichts, die Tokens entstehen beim Nachdenken der Arbeitsschritte, nicht beim Board-Zugriff. Was den Umbau trägt, ist der Wartungsaufwand des Eigenbaus und ein Ablauf, der zur tatsächlichen Arbeitsweise passt. Ebenfalls festgehalten: Es gäbe billigere Teillösungen (nur die tote Spalte streichen, oder nur die von GitHub selbst erkennbaren Übergänge abgeben). Beide wurden bewusst zugunsten des vollständigen Umbaus verworfen.

## User Story

Als Daniel möchte ich den Fortschritt jeder Story an genau den Board-Spalten ablesen können, die sie tatsächlich durchläuft, ohne dass die Pflege dieses Boards von einem eigens dafür gebauten Werkzeug abhängt, damit das Board meine Arbeit abbildet statt sie zu verwalten.

## Akzeptanzkriterien

Die Kriterien folgen dem Issue-Body; fünf davon sind im `spec-writer`-Ablauf durch `test-engineer` auf Testbarkeit geschärft worden — die Schärfungen sind im Abschnitt „Entscheidungen" einzeln benannt.

### Lebenszyklus

- [ ] Der Lebenszyklus einer Story umfasst genau die Zustände `Unrefined` → `Ready` → `In Progress` → `Review` → `Done`. Die Spalte `Todo` kommt darin nicht mehr vor.
- [ ] `In Progress` wird erreicht, sobald die Umsetzung beginnt — einschließlich des Schreibens der Spec, nicht erst danach.
- [ ] `Review` wird erreicht, sobald der zugehörige Pull Request eröffnet bzw. als bereit markiert ist.
- [ ] `Done` wird erreicht, sobald der zugehörige Pull Request gemergt ist.
- [ ] Für jeden dieser Übergänge ist eindeutig benannt, wodurch er ausgelöst wird. Die vollständige Auslöser-Tabelle (ADR 0057, Abschnitt 2) steht in [`docs/ai-workflow.md`](../../docs/ai-workflow.md), damit sie an der Stelle nachlesbar ist, an der der Workflow beschrieben wird.
- [ ] Es ist festgelegt und nachlesbar, welchen Zustand eine Story einnimmt, wenn ihr Pull Request geschlossen wird, ohne gemergt zu werden: `In Progress`.
- [ ] **(a)** Nach dem Rollout tragen 0 Items den Wert `Todo`, und die Option ist aus dem Feld `Status` entfernt — einmalig zurückgelesen und belegt. **(b)** Keine Skill-/Agent-Datei schreibt einen Wert, den das Feld nicht kennt (CI-geprüft, siehe Teststrategie).

### Board-Zugriff

- [ ] Nach der Umstellung existieren `scripts/gh-board.py` und `scripts/tests/test_gh_board.py` nicht mehr, und **keine von Git verwaltete Datei außer `CHANGELOG.md` und `specs/**` erwähnt sie noch** — die Erwähnung ist dort historisch korrekt und bleibt stehen. Diese Fassung ersetzt die enger formulierte Fassung „keine Skill- oder Agent-Datei", weil der Ist-Zustand Fundstellen auch in `.github/workflows/ci.yml`, `docs/` und `scripts/tests/conftest.py` hat.
- [ ] Jeder Statuswechsel, den GitHub selbst erkennen kann, wird von GitHub ausgelöst und nicht von einer laufenden Session: `Unrefined` (`Item added to project`), `Review` (`Pull request linked to issue`), `Done` (`Item closed`).
- [ ] Die Prüfungen, die das bisherige Werkzeug geleistet hat, gehen nicht ersatzlos verloren. Für jede ist ein Ersatz benannt oder der Wegfall begründet (ADR 0057, Abschnitt 5):
  - Zurückweisung ungültiger Status- und Prioritätswerte → **ersetzt und verbessert**: `gh` prüft gegen die realen Board-Optionen statt gegen eine mitgeführte Konstantenliste, die abdriften konnte.
  - Ein bereits erreichter Zielzustand gilt als Erfolg, nicht als Fehler → **entfällt, weil seine Ursache entfällt**: Die Session schließt kein Issue mehr. Das Prinzip aus ADR 0048 bleibt in Kraft, ist jetzt aber strukturell erfüllt.
  - Die Priorität wird beim ersten Setzen vergeben und danach nie überschrieben → **ersetzt** durch explizites Lesen vor dem Schreiben in `refinement`. Verloren geht nur die Atomarität; folgenlos, weil es genau einen Schreiber gibt.
  - Beim Abschluss wird geprüft, dass Pull Request und Issue tatsächlich verknüpft sind → **doppelt ersetzt**: als Prüfschritt in `ship-feature` und strukturell, weil `Done` ausschließlich aus dem keyword-getriebenen Schließen entsteht.
- [ ] **(a)** Ein Fehlschlag beim Setzen eines Board-Werts bleibt sichtbar: Der Exit-Code jedes Board-Befehls wird ausgewertet, der Schritt wird nie geschluckt, sondern im Abschnitt `## Lokal nachzuholen` mit dem wiederholbaren Befehl aufgeführt (CI-geprüft, dass die Konvention in allen vier Ablauf-Skills steht). **(b)** Ein Fehlschlag lässt keine Story fälschlich fortgeschritten erscheinen — strukturell garantiert dadurch, dass beide Session-Schreibzugriffe **vor** der Arbeit stehen, die sie ankündigen; Gegenstand des Reviews, kein Testgegenstand.
- [ ] Lokal laufen alle fünf Übergänge durch. Remote geschehen die drei GitHub-seitigen Übergänge unbeeinflusst, und die zwei Session-Schreibzugriffe scheitern sichtbar mit wiederholbarem Befehl unter `## Lokal nachzuholen`. Nachgewiesen an je einem realen Durchlauf. Diese Fassung ersetzt „der vollständige Lebenszyklus läuft lokal und remote durch" — so formuliert war das Kriterium nicht erfüllbar und stand im Widerspruch zu ADR 0057, Abschnitt 7, der `Ready`/`In Progress` remote ausdrücklich als scheiternd führt.

### Ablösung der bestehenden Festlegungen

- [ ] Vor dem Umbau liegt ADR [`0057`](../decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md) vor, die die Festlegungen ablöst, dass ausschließlich das eigene Werkzeug das Board-Statusfeld schreiben darf und die native GitHub-Automatisierung abgeschaltet bleibt (ADR 0037 Abschnitt 5, ADR 0046 Abschnitt 5).
- [ ] Diese Entscheidung beantwortet den ursprünglichen Einwand ausdrücklich, statt ihn zu überstimmen (ADR 0057, Abschnitt 3).
- [ ] Alle durch den Umbau abgelösten Entscheidungen sind als abgelöst markiert, nicht stillschweigend übergangen — vollständig `Superseded`: 0037, 0048, 0052, 0056; teilweise abgelöst mit Nachtrag-Verweis: 0046 §5, 0043 §4, 0042 §2+§4, 0044 §3.
- [ ] Issue #305 wird mit dem Abschluss dieser Story geschlossen.

## Datenmodell-Bezug

Keiner. Die Story berührt ausschließlich Prozess-Metadaten auf GitHub (Board-Statusfeld, Issue-Close-Grund) sowie Skill-, Agent- und Doku-Dateien im Repo. Keine Entität der Anwendung, kein Feld in [`docs/architecture.md`](../../docs/architecture.md) ändert sich.

## Architektur / Umsetzung

Der gewählte Ansatz und seine vollständige Begründung stehen in ADR [`0057`](../decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md) („Der Board-Lebenszyklus wird nativ: GitHub schreibt, was GitHub erkennt, `gh-board.py` entfällt"). Dieser Abschnitt fasst das Ergebnis zusammen und legt die Umsetzung fest.

### Der Zielzustand in einem Satz

`Unrefined → Ready → In Progress → Review → Done`, wobei **GitHub selbst auslöst, was GitHub erkennen kann** (`Unrefined`, `Review`, `Done` über die eingebauten Projects-Workflows) und **die Session nur schreibt, was nur sie weiß** (`Ready`, `In Progress`) — mit je einem einzelnen `gh`-Befehl statt eines eigenen Werkzeugs.

| Übergang | Ausgelöst durch | Geschrieben von |
|---|---|---|
| → `Unrefined` | Issue wird ins Projekt aufgenommen | GitHub, Workflow `Item added to project` |
| → `Ready` | `refinement` hat die Story fachlich geschärft | Session (`refinement`, Schritt 6) |
| → `In Progress` | `spec-writer` beginnt — **vor** Branch und Spec-Datei | Session (`spec-writer`, Schritt 0) |
| → `Review` | Pull Request verweist per `Closes #NNN` auf das Issue | GitHub, Workflow `Pull request linked to issue` |
| → `Done` | Issue wird geschlossen (Regelweg: Merge über das Keyword) | GitHub, Workflow `Item closed` |
| → `In Progress` (zurück) | Pull Request wird ohne Merge geschlossen | Session (`ship-feature`) |

`Todo` entfällt ersatzlos. Der lokale Spec-Datei-Lebenszyklus (`Proposed → Accepted → Implemented → Superseded`, `specs/README.md`) bleibt unverändert.

### Warum kein Werkzeug mehr nötig ist

`scripts/gh-board.py` existierte laut eigenem Modulkopf, weil „die fehleranfällige Projects-V2-Logik (Projekt-/Feld-/Options-/Item-ID-Auflösung)" gebündelt werden musste. Diese Begründung ist entfallen: `gh` 2.97.0 (31.07.2026, `cli/cli#13807`) kennt eine namensbasierte Form ohne jede ID —

```bash
gh project item-edit 8 --owner TheRealKoller --url <issue-url> --field "Status" --value "In Progress"
```

— und validiert den Wert am echten Board (`option "Quatsch" not found on field "Status"; available options: …`, Exit 1). Am Live-Board verifiziert, ebenso die Idempotenz (Setzen des bereits gesetzten Werts = Exit 0, kein Fehler). Die verbindliche Befehlssammlung steht in ADR 0057, Abschnitt 4.

### Sichtbarkeit von Fehlschlägen

Keine Vorabmessung mehr (`doctor` und `capabilities` entfallen ersatzlos; ADR 0052 Abschnitt 2/3 „kein Urteil vor dem Versuch" bleibt tragend). Der Befehl wird abgesetzt; scheitert er, bricht der Ablauf nicht ab, führt den Schritt aber im wörtlich erhaltenen Abschnitt `## Lokal nachzuholen` mit dem wiederholbaren Befehl auf. Struktureller Zusatzschutz: Beide verbliebenen Session-Schreibzugriffe stehen **vor** der Arbeit, die sie ankündigen — ein Fehlschlag lässt die Story auf dem früheren, konservativeren Wert stehen, nie auf einem weiter fortgeschrittenen.

Weil drei von fünf Übergängen künftig an nativen Workflows hängen, deren Zustand per API weder les- noch überwachbar ist, dreht sich die Richtung des Fehlers um: Ein deaktivierter Workflow schreibt *gar nichts*. Deshalb liest `ship-feature` nach dem Eröffnen des Pull Requests den Board-Wert einmal zurück und führt ein ausgebliebenes `Review` unter `## Lokal nachzuholen` auf (ADR 0057, Abschnitt 6, Punkt 4).

### Remote-Sessions

Die Grenze aus ADR 0056 gilt unverändert (Projects ist GraphQL-only, Cloud-Sessions bedienen GraphQL nur für PR-Operationen) — sie **schrumpft** aber von vier Board-Schritten auf zwei: `Review` und `Done` laufen ab jetzt auf GitHubs Servern und sind von der Sperre nicht berührt. Remote fallen nur noch `Ready`, `In Progress` und die Board-Aufnahme eines neuen Issues aus.

### Umsetzungsplanung für `developer`

**Vorbedingung, die nicht beim `developer` liegt:** Die Board-Konfiguration (Workflows einschalten, vier Items umsetzen, Option `Todo` entfernen) und die Anhebung von `GH_VERSION` im Cloud-Setup-Script sind manuelle bzw. Orchestrator-Schritte und müssen **vor** Schritt 4 erledigt sein (siehe „Manuelle Schritte" unten). Der `developer` hat keinen GitHub-Schreibzugriff und führt sie nicht aus.

**Reihenfolge (Doku/Regeln vor Löschen, Löschen vor Aufräumen):**

1. **Abgelöste Entscheidungen markieren** (reine Markdown-Arbeit, zuerst, weil alles Folgende sich darauf beruft):
   - `specs/decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md` → Status **`Superseded`**, Nachtrag-Verweis auf ADR 0057 (abgelöst: Abschnitte 1, 3, 4, **5**, 6, 7).
   - `specs/decisions/0048-board-operationen-zielzustands-idempotent.md` → **`Superseded`**, Nachtrag: Prinzip aus Abschnitt 1 in ADR 0057 Abschnitt 5.2 übernommen.
   - `specs/decisions/0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md` → **`Superseded`**, Nachtrag: Abschnitt 2/3 („kein Urteil vor dem Versuch") bleibt tragend, Abschnitt 6 Punkt 2 wird umgekehrt.
   - `specs/decisions/0056-remote-grenze-gemessene-board-faehigkeit-statt-session-erkennung.md` → **`Superseded`**, Nachtrag: Befund zur Remote-Grenze bleibt gültig, `capabilities` entfällt.
   - `specs/decisions/0046-pr-issue-verknuepfung-closing-keyword.md` → bleibt **`Accepted`**, Nachtrag: **Abschnitt 5 abgelöst**; Abschnitte 1–4 bleiben gültig und werden tragend.
   - `specs/decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md` → bleibt **`Accepted`**, Nachtrag: **Abschnitt 4** abgelöst.
   - `specs/decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md` → bleibt **`Accepted`**, Nachtrag: **Abschnitt 2 und 4** abgelöst (1/3 bleiben: Spec-Statuszeile weiterhin vor dem Merge im Feature-PR).
   - `specs/decisions/0044-prioritaet-startwert-automatisch-im-board-setzen.md` → bleibt **`Accepted`**, Nachtrag: **Abschnitt 3** abgelöst.
   - Nicht anfassen: die Feature-Specs `0262`, `0278`, `0302`, `0309`, `0318` bleiben `Implemented` — sie beschreiben korrekt, was zu ihrer Zeit gebaut wurde.

2. **Tests zuerst (rot)**, in `scripts/tests/` — Bauvorgaben im Abschnitt „Teststrategie".

3. **`docs/setup.md`** grün machen: Mindestversion `2.97.0` als autoritative Prosa-Angabe mit dem verbindlichen Label `**Mindestversion:**` und Begründung, `GH_VERSION="2.97.0"` im dokumentierten Setup-Script-Block, Warnzeile im Block ohne `gh-board.py`, sämtliche `doctor`/`capabilities`-Absätze und der Remote-Abschnitt neu gefasst nach ADR 0057 Abschnitt 7.

4. **Skill-/Agent-Dateien umschreiben:**
   - `.claude/skills/github-board/SKILL.md` — vom Script-Wrapper zur Befehlssammlung (ADR 0057 Abschnitt 4) plus Lebenszyklus-Tabelle, Fehlerregel und der **wörtlich erhaltenen** `## Lokal nachzuholen`-Konvention inkl. der Regel „nur selbst erzeugter Inhalt ins dauerhafte Artefakt". Abschnitte zu `doctor`, `capabilities`, `finalize` und Vorabmessung entfallen. Die Frontmatter-`description` darf das Script nicht mehr nennen.
   - `.claude/skills/capture/SKILL.md` — Messschritt raus; `gh issue create` + `gh project item-add` als **zwei** Befehle (das Issue muss überleben, wenn der Board-Teil scheitert); `Unrefined` wird nicht mehr gesetzt.
   - `.claude/skills/refinement/SKILL.md` — Schritt 6: `gh issue edit` → Priorität lesen → nur bei leerem Feld schreiben → `Ready`. Verwerfen-Pfad in Schritt 5: `gh issue close --reason "not planned"`.
   - `.claude/skills/spec-writer/SKILL.md` — Schritt 0: Status per GraphQL-Einzeiler lesen, danach **`In Progress` setzen** (vor Branch und Spec). Das Gate bleibt fail-closed und nennt im Abbruchtext ausdrücklich den fremden Pull Request als mögliche Ursache. `set-status Todo` am Ende von Schritt 4 entfällt. Neu: Existiert bereits eine Spec-Datei zur Issue-Nummer, wird sie weiterverwendet statt eine neue anzulegen (betrifft #162/#167/#169).
   - `.claude/skills/ship-feature/SKILL.md` — Schritt 2.4 entfällt; Schritt 6.4 (`Review` setzen) entfällt im Regelfall und wird durch das **Zurücklesen** ersetzt; Schritt 8 wird: Verknüpfung prüfen → `**Status:**`-Zeile der Spec-Datei lokal auf `Implemented ([PR #MMM](url))` → mit den letzten Fixes pushen. **Kein Schließen des Issues vor dem Merge, kein vorgezogenes `Done`.** Neu: Pull Request ohne Merge geschlossen → `In Progress` zurücksetzen.
   - `.claude/agents/developer.md` — der „Hinweis an den Aufrufer" (`In Progress` setzen) entfällt.

5. **Löschen:** `scripts/gh-board.py`, `scripts/tests/test_gh_board.py`, die `gh_board`-Fixture in `scripts/tests/conftest.py`. Der CI-Job `demo-scripts` bleibt; nur sein erklärender Kommentar in `.github/workflows/ci.yml` wird nachgezogen.

6. **`docs/ai-workflow.md`:** Lebenszyklus ohne `Todo`, die Auslöser-Tabelle aus ADR 0057 Abschnitt 2 aufgenommen, Satz zur Vorabmessung raus.

7. **Abschlussprüfung:** `ruff check .` und `pytest` unter `scripts/` grün; der neue Referenz-Test belegt, dass keine von Git verwaltete Datei außer den benannten Ausnahmen das Werkzeug noch erwähnt.

**Entwurfsentscheidungen, die `developer` nicht selbst trifft** (alle in ADR 0057 begründet): namensbasierte statt ID-basierter `gh`-Aufrufe; `gh api graphql` zum Lesen statt `gh project item-list` (letzteres lädt die ganze Item-Liste und hat genau daraus schon einmal einen Fehler erzeugt, Spec 0302); zweistufiges Anlegen in `capture`; ersatzloser Wegfall von `doctor`/`capabilities`; `In Progress` bei `spec-writer` statt beim `developer`-Start; `Done` bedeutet „vom Board", nicht „ausgeliefert".

### Manuelle Schritte (Daniel bzw. Orchestrator, nicht `developer`)

**M1 — Projekt-UI „PhotoSort Roadmap" → Workflows.** Nicht skriptbar: Das GraphQL-Schema kennt für Workflows genau eine Mutation, `deleteProjectV2Workflow` — kein Aktivieren, kein Konfigurieren. Der `enabled`-Zustand ist nur *lesbar*.

| Workflow | Aktuell | Soll |
|---|---|---|
| `Item added to project` | aus | **einschalten** → Status `Unrefined` |
| `Pull request linked to issue` | aus | **einschalten** → Status `Review` |
| `Item closed` | aus | **einschalten** → Status `Done` |
| `Pull request merged` | aus | **bleibt aus** (unsere Items sind Issues, kein Gegenstand) |
| `Auto-add to project` | aus | **bleibt aus** (sonst landen fremde Issues automatisch als `Unrefined` auf dem Board) |
| `Auto-close issue` | an | **bleibt an**, unverändert |
| `Auto-add sub-issues to project` | an | **bleibt an**, unverändert |

**M2 — Die vier Issues auf `Todo` auf `Ready` setzen:** #174, #162, #167, #169. Alle vier tragen einen vollständig geschärften Issue-Body und an keinem wird gearbeitet — das ist die Definition von `Ready`. Die bei #162/#167/#169 bereits vorhandene akzeptierte Spec-Datei ist Vorarbeit, kein Zustand.

**M3 — Die Option `Todo` aus dem Feld `Status` entfernen.** Zwingend **nach** M2. Kein Löschen-und-Neuanlegen und keine Migration der übrigen Items nötig: `updateProjectV2Field` nimmt `singleSelectOptions` entgegen; werden die fünf verbleibenden Optionen mit ihren bestehenden IDs erneut gesendet, bleiben sie samt Zuordnungen unangetastet.

**M4 — `GH_VERSION` im Setup-Script der Cloud-Umgebung (Weboberfläche) auf `2.97.0` anheben.** Der seit ADR 0053/0054 als Pflichtschritt benannte, ungesicherte Übergang Doku → Weboberfläche. Ohne ihn hat die Remote-Umgebung weiter `gh` 2.72.0 und kennt die namensbasierte `item-edit`-Form nicht.

**Reihenfolge:** M1 → M2 → M3 vor Schritt 4 der Umsetzungsplanung. Ein Skill, der `Todo` nicht mehr kennt, während die Spalte noch existiert, ist folgenlos; eine entfernte Spalte, auf die ein Skill noch schreibt, ist ein Fehlschlag mitten im Ablauf.

## UI/UX

Nicht relevant — reine GitHub-Prozess-/Automatisierungsstory ohne sichtbare Oberfläche; `frontend/` wird nicht berührt.

## Teststrategie

**Kernaussage: Die Testfläche verschwindet nicht, sie wechselt die Klasse.** Jede wegfallende Prüfung wird genau einer von drei Klassen zugeordnet — (1) Repo-Konsistenztest, (2) struktureller Wegfall mit Begründung, (3) benannte Beobachtungspflicht. Die Zuordnung ist der eigentliche Prüfschritt; pauschales „ist halt jetzt GitHub" ist keine. Details in [`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md), Abschnitt „Erweiterung für ADR 0057".

**Ebene: ausschließlich Repo-Konsistenztests im `demo-scripts`-CI-Job** (`scripts/tests/`, kein Coverage-Gate). Kein Unit/Integration/E2E im üblichen Sinn — nach der Löschung gibt es keinen eigenen Code mehr, nur Text im Repo. Bauform durchgängig wie in `test_setup_docs.py`: reine Funktion auf übergebenem Text + dünner Leser für den echten Repo-Zustand; 0 und >1 Treffer sind laute Fehlerfälle mit eigener Meldung.

| Test | Deckt ab |
|---|---|
| Referenz-Freiheit `gh-board` / `gh_board` über alle von Git verwalteten Dateien | „Script samt Tests existiert nicht mehr; keine Datei verweist darauf" |
| Board-Wert-Parser über `.claude/**`: `--field`/`--value` ⊆ gültige Optionen | „Lebenszyklus genau fünf Werte, ohne `Todo`" + Ersatz für Prüfung 1 |
| `## Lokal nachzuholen` wörtlich in `capture`/`refinement`/`spec-writer`/`ship-feature` | „Ein Fehlschlag bleibt sichtbar" |
| `test_setup_docs.py`: Prosa-Mindestversion ↔ `GH_VERSION`-Block, plus Untergrenze `>= 2.97.0` | Voraussetzung der namensbasierten `item-edit`-Form |

**Bauvorgaben (verbindlich):**

- **Referenz-Test.** Suchraum = `git ls-files`, **nicht** eine feste Liste `.claude/`/`docs/`/`.github/` — ein neu angelegter oder umbenannter Skill fiele aus einer festen Liste heraus, und die `gh_board`-Fixture in `scripts/tests/conftest.py` sowie der Kommentar am `demo-scripts`-Job in `.github/workflows/ci.yml` lägen von vornherein außerhalb. Ausnahmen genau drei, per Pfadpräfix: `CHANGELOG.md`, `specs/**`, die Testdatei selbst. Byteweise suchen (`read_bytes()`) nach **beiden** Formen `gh-board` und `gh_board` — sonst Dekodierfehler an Binärdateien, und die Unterstrich-Form bleibt in Python-Bezeichnern zurück. Je Fund Pfad **und** Zeilennummer melden. Zwei Selbstschutz-Assertions, ohne die der Test bei kaputter Aufzählung grün wäre: Dateiliste nicht leer/plausible Größe, und Gegenprobe, dass dasselbe Muster in `specs/decisions/0057-*.md` sehr wohl trifft. Plus Pfadprüfung, dass Script und alte Testdatei weg sind.
- **`test_setup_docs.py`.** Nur *ein* bestehender Test hängt am Script (`test_die_dokumentierte_gh_version_entspricht_min_gh_version` über die `gh_board`-Fixture); alle übrigen Helfer-Tests bleiben unangetastet. Gegen Brüchigkeit wird die Prosa-Angabe ein **Vertrag, keine Formulierung**: zeilenanfangs-verankertes Label `**Mindestversion:**` mit genau einer dreiteiligen Version; `2.97` ergibt 0 Treffer und damit einen lauten Fehlschlag statt eines stillen Ungleich-Vergleichs. Zusätzlich eine Untergrenze `>= (2, 97, 0)`: Zwei Angaben in derselben Datei können einander sonst einträchtig auf einen zu niedrigen Wert folgen. Anheben berührt sie nicht, nur Absenken wird rot.
- **Board-Wert-Parser.** Bewusst **kein** freier `Todo`-Textscan über `.claude/`/`docs/` — „Todo" ist ein zu gewöhnliches Wort, das wäre Formulierungspolizei mit Falschmeldungen. Stattdessen `--field`/`--value`-Paare parsen und gegen die Optionsmengen prüfen (Platzhalter `<Wert>`, `<Hoch|Mittel|Niedrig>` explizit zugelassen); `Todo` ist dann schlicht kein zulässiger Wert. Im selben Parser mitprüfen: Projektnummer `8` und `--owner TheRealKoller` in jedem Aufruf.

**Nicht automatisierbar, ausdrücklich als manuelle Verifikation geführt:** die fünf Übergänge selbst, der Rollout am Live-Board, das Laufzeitverhalten der Skills. Nachweisform statt Häkchen: `Review`/`Done` am eigenen Pull Request dieser Story mit Beleg; `Unrefined`/`Ready`/`In Progress` als benannte Beobachtungspflicht beim nächsten Durchlauf (diese Story durchläuft sie noch unter dem alten Regime); remote ein realer Fehlschlag-Nachweis unter `## Lokal nachzuholen`.

**Der eine echte Verlust, benannt statt weggerechnet:** Priorität first-write-wins wird von einer Code-Eigenschaft mit Testfällen zu einer LLM-interpretierten Ablaufreihenfolge und ist nicht mehr automatisiert testbar. Als bekannte Lücke im Testkonzept eingetragen.

**Coverage-Gate: kein Risiko.** Der `backend`-Job misst ausschließlich `backend/src/photosort`; `backend/pyproject.toml` hat keinen `[tool.coverage]`-Abschnitt, der `scripts/` einbezöge, und der `demo-scripts`-Job hat gar kein Gate. Das Löschen bewegt die gemessene Zahl um exakt null.

**Edge Cases, die abgedeckt sein müssen:** `gh_board`-Fixture in `conftest.py` (eine session-scoped Fixture, die niemand anfordert, schlägt *nicht* fehl — latenter Fund); `ci.yml` Zeilen 80–83; die `github-board`-Frontmatter-`description` (der Scan muss die ganze Datei lesen, nicht nur den Body); Selbstausschluss des Referenz-Tests per Pfad; Binärdateien unter `scripts/demo_photos/`; leere Dateiliste muss laut scheitern; `2.97` statt `2.97.0`; zwei Versionsangaben in einer Label-Zeile als Mehrfachtreffer laut ablehnen statt „ersten nehmen"; ein Pull Request mit `Closes #NNN` **gegen einen anderen Basisbranch als `main`** — `ship-feature` liest `baseRefName` bereits mit, das gehört als Testfall der Prüfschritt-Beschreibung benannt.

## Security

Sicherheitsrelevant, kein Blocker. Vollständige Herleitung im Sicherheitskonzept ([`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md), Abschnitt „Board-Lebenszyklus nativ" unter „Angriffsflächen", plus je drei Einträge unter Restrisiken und Bekannten Lücken). Kein PhotoSort-Anwendungscode, kein Laufzeitrisiko für die Anwendung, keine Foto-/Projektdaten.

**Keine zusätzlichen Rechte.** Gemessen am 2026-09-05: Das aktive Konto trägt `gist`, `project`, `read:org`, `repo`. `gh project item-edit --field/--value` und der Lesezugriff `gh api graphql` auf `repository.issue.projectItems` laufen beide über `project` (enthält `read:project`) — derselbe Scope, den `gh-board.py` schon brauchte. `gh issue create/edit/close` und `gh pr view` laufen über `repo`. Kein `gh auth refresh` nötig, lokal wie remote dasselbe Rechteprofil. Der Bedarf sinkt sogar: Drei der fünf Übergänge laufen auf GitHubs Servern und brauchen unser Token gar nicht.

**Bedrohung 1 — ein Fremder löst einen Board-Zustand aus.** Das Repository ist `PUBLIC`. Für keyword-basierte PR↔Issue-Verknüpfung dokumentiert GitHub keine Berechtigungsprüfung des PR-Autors; ein beliebiger Nutzer kann forken und einen Pull Request mit `Closes #<Nummer>` eröffnen, und der Workflow `Pull request linked to issue` zieht die Karte dann auf `Review` — ohne Merge, ohne Repo-Recht. Die beiden anderen nativen Übergänge sind nicht fremdauslösbar (`Item added to project` verlangt Projekt-Schreibrecht; unsere Story-Issues kann ein Fremder nicht schließen). Die Issue-Freigabe-Policy (`approved-for-agent`) wird davon nicht berührt — sie hängt am Label-Zustand, nicht an der Board-Spalte; eine erzwungene Spalte gibt keine Story frei. *Als Restrisiko bewusst akzeptiert* (Entscheidung Daniel, 2026-09-05, ADR 0057 Abschnitt 2), weil der Gewinn — der Übergang funktioniert auch aus Remote-Sessions, in denen jeder Board-Zugriff scheitert — schwerer wiegt als ein sichtbarer, per Einzeiler behebbarer Schaden ohne Nutzerdaten-Bezug. *Gegenmaßnahme:* Das Statusgate in `spec-writer` bleibt **fail-closed** — ein Status ≠ `Ready` bricht ab, wird an Daniel gemeldet und nie automatisch „repariert" oder umgangen. Der Skill-Text nennt dabei ausdrücklich die zweite mögliche Ursache neben „schon einmal zu einer Spec geworden": ein fremder Pull Request, der auf dieses Issue verweist. Ohne diesen Satz wird eine gültige Story fälschlich als erledigt abgewiesen.

**Bedrohung 2 — Shell-Injection über eingesetzte Werte.** Mit `gh-board.py` entfällt die bisher testgeprüfte Zusicherung „kein `shell=True`, Argumente in Listenform, keine Interpolation" (ADR 0017 Abschnitt 5). Metazeichen, die im Werkzeug inert waren, sind in einer Shell-Zeile aktiv; der einzige Freitext-Parameter (`gh issue create --title`) trägt in diesem Projekt regelmäßig Backticks und Dollarzeichen, und `capture` kann einen Titel aus einem Fremd-Issue übernehmen. *Gegenmaßnahmen, verbindlich in den Skill-Dateien:*

- **Freitext gelangt nie in eine Kommandozeile.** Titel wie Bodies über eine Datei; verbindliche Form `--title "$(cat <pfad>)"`, Datei mit dem Schreib-Werkzeug angelegt (nicht per Shell-Umleitung mit interpoliertem Inhalt) und genau eine Zeile lang. `--body-file` bleibt Pflicht.
- **Nur geschlossene Werte werden eingesetzt.** Issue-/PR-Nummern gegen `^[0-9]+$`, Spec-Nummern gegen `^\d{4}$`, jeweils ausschließlich aus dem laufenden Ablauf; die Issue-URL wird aus der Nummer **gebildet** (`https://github.com/TheRealKoller/photosort/issues/<NNN>`), nie aus einer `gh`-Ausgabe übernommen; Status- und Prioritätswerte stehen als Literale im Skill-Text. Keine Zeichenkette aus `gh`-Ausgabe, Issue-Body oder Kommentar wird je Teil eines Befehls. Kein `eval`.
- **Die GraphQL-Query bleibt ein Literal in einfachen Anführungszeichen**, die Nummer geht ausschließlich als typisierte Variable `-F number=<NNN>` hinein. In doppelten Anführungszeichen expandierte die Shell `$number` zu leer — die Query wäre dann nicht fehlerhaft, sondern hätte klaglos eine andere Bedeutung.
- **Die Antwort wird auf das richtige Projekt bezogen:** ausgewertet wird der Knoten mit `project.number == 8`, nie schlicht `nodes[0]` — sonst entscheidet eine fremde Projektzugehörigkeit über ein Ablauf-Gate.

**Bedrohung 3 — Fremdtext bzw. Secrets auf dem Weg in ein öffentliches Artefakt.** Mit dem Werkzeug entfällt `redact_for_report()`, die einzige maschinelle Schwärzung von `gh`-Ausgaben. *Gegenmaßnahmen (unverändert fortgeführt, nicht neu erfunden):* Kanaltrennung — in `## Lokal nachzuholen` gelangt ausschließlich selbst erzeugter Inhalt (Schrittname, aus eigenen validierten Nummern gebildeter Wiederholbefehl, fester Begründungssatz); `gh`-stdout/-stderr bleibt dem Chat-Bericht vorbehalten, den ein Mensch liest. Der feste Satz ist neu zu fassen, weil er heute auf `capabilities` verweist — die Trennung selbst wird dabei nicht angetastet, und die Ausnahme des automatischen Pfads nie auf den manuellen ausgedehnt. Der Muss-Schritt „vor dem Einfügen lesen" gilt unverändert und jetzt ohne vorgeschalteten Filter, also strenger als zuvor.

**Prompt-Injection-Fläche: unverändert, in der Summe kleiner.** Kein neues von außen beschreibbares Feld gelangt in einen Agenten-Kontext. Der `gh api graphql`-Lesebefehl liefert nur Projektnummer und zwei Single-Select-Namen (nur mit Projekt-Schreibrecht setzbar). `gh pr view --json closingIssuesReferences,baseRefName` liefert gemessen (2026-09-05, PR #322) genau `id`, `number`, `repository{id,name,owner{login,id}}`, `url` und den Base-Branch — **keinen** Titel, **keinen** Body. *Muss-Kriterium:* Genau diese Feldmenge bleibt stehen; `title`, `body`, `author`, `headRefName`, `comments` werden nicht ergänzt, und ein blankes `gh pr view <MMM>` (gibt den Body aus) kommt im Ablauf nicht vor. „Nur `issue.body`, nie Kommentare" bleibt in `refinement`/`spec-writer` unverändert. Entlastend: Mit `doctor`/`capabilities` verschwinden die beiden einzigen Stellen, an denen `gh`-stderr als Fremdtext strukturiert weitergereicht wurde.

**Wegfall der Vorabmessung: kein Integritätsrisiko.** `capabilities` war fail-open und konnte nur Schritte auslassen; sein Wegfall kann keinen falschen Zustand erzeugen. Die Aussage trägt allein der strukturelle Schutz aus ADR 0057 Abschnitt 6.3. *Gegenmaßnahme gegen den einen realen Rest:* Der Exit-Code jedes Board-Einzeilers wird ausgewertet; ein Fehlschlag wird nie geschluckt, sondern führt den Schritt in `## Lokal nachzuholen`. Diese Prüfung wandert von getestetem Code in Skill-Disziplin und steht genau deshalb ausdrücklich dort.

**Unverändert:** keine neuen Secrets, keine geänderte Authentifizierung, keine neue externe Abhängigkeit, kein Effekt auf Auth-/Sichtbarkeitsmodell der Anwendung. Die Anhebung der Mindestversion auf `2.97.0` ist sicherheitsseitig eine Verbesserung (jüngere Toolchain, Asset und Prüfsumme weiterhin aus demselben Release). Die CI-Bindung zwischen Mindestversion und dokumentiertem Setup-Block muss dabei eine echte Gegenprüfung bleiben und darf nicht zu zwei Literalen in derselben Datei werden, die sich trivial selbst bestätigen.

## Entscheidungen

Im `spec-writer`-Ablauf am 2026-09-05 geklärt:

- **`architect` konsultiert (Schritt 1).** Ergebnis: ADR 0057, Abschnitt „Architektur / Umsetzung" oben.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story hat keinen konkret benennbaren Bezug zu einer sichtbaren Oberfläche — sie ändert ausschließlich GitHub-Prozess-Metadaten sowie Skill-, Agent- und Doku-Dateien; `frontend/` wird an keiner Stelle berührt.
- **`test-engineer` konsultiert (Schritt 3).** Ergebnis: Abschnitt „Teststrategie", Erweiterung des Testkonzepts, fünf geschärfte Akzeptanzkriterien.
- **`security-engineer` konsultiert (Schritt 3).** Ergebnis: Abschnitt „Security", Erweiterung des Sicherheitskonzepts.
- **`Done` heißt „vom Board", nicht „ausgeliefert"** (Daniel, gegen einen sechsten Wert `Verworfen`): Den Unterschied trägt GitHubs Close-Grund (`completed` vs. `not planned`), verbindlich gesetzt im Verwerfen-Pfad. Ein sechster Wert wäre nur von einer Session setzbar und kostete den Kern des Umbaus.
- **`doctor` und `capabilities` entfallen ersatzlos** (Daniel, gegen eine schlanke Rest-Diagnose): Ein Diagnosewerkzeug für zwei verbliebene Einzeiler wäre größer als sein Gegenstand.
- **Die vier `Todo`-Issues gehen auf `Ready`** (Daniel, gegen Schließen als Altlasten): Geschärfter Body plus niemand arbeitet daran ist die Definition von `Ready`; die Vorarbeit bleibt erhalten.
- **Ein ohne Merge geschlossener Pull Request setzt die Story auf `In Progress` zurück** (Daniel, gegen `Ready`): Die Umsetzung hat nachweislich begonnen, Spec und Branch existieren.
- **`Review` wird nativ ausgelöst, das Fremdschreib-Restrisiko wird akzeptiert** (Daniel, gegen „`Review` weiter in `ship-feature` setzen"): Der Übergang funktioniert damit auch aus Remote-Sessions — bisher der teuerste Ausfall.
- **`ship-feature` liest den Board-Wert nach dem Eröffnen des Pull Requests einmal zurück** (Daniel, gegen „als bekannte Lücke akzeptieren"): schließt die Lücke, dass ein versehentlich deaktivierter nativer Workflow *gar nichts* schreibt und damit unbemerkt bliebe.

### In der Review-Phase nachgezogen (2026-09-05)

Zwei Abweichungen von der ursprünglichen Fassung, hier benannt statt stillschweigend übernommen:

- **Der Board-Befehlsparser liest eine Befehlszeile nur am Zeilenanfang.** Die erste Fassung erkannte jedes Vorkommen von `gh project item-edit` im Text und meldete deshalb eine reine Prosa-Erwähnung („… erst ab dort kennt `gh project item-edit` die namensbasierte Form") als Aufruf ohne `--field`. Zugelassen sind am Zeilenanfang außerdem ein Listenpunkt und ein Inline-Code-Etikett (`- `status-review`: `gh project item-edit …``) — in dieser Form stehen die Nachhol-Befehle in den Berichtsvorlagen, die dem Parser sonst entgingen. Beide Richtungen sind als Testfälle belegt.
- **`ship-feature` liest bei Abweichung ein zweites Mal.** ADR 0057, Abschnitt 6, Punkt 4 sah einen einzigen Lesevorgang vor. GitHub verarbeitet die PR↔Issue-Verknüpfung asynchron; unmittelbar nach `gh pr create` steht deshalb regelmäßig noch der alte Wert. Ohne den zweiten Versuch meldete **jeder** Lauf einen Fehlschlag, den es nicht gibt. Die ADR ist entsprechend nachgezogen.

Ebenfalls in der Review-Phase korrigiert: ADR 0057, Abschnitt 6, Punkt 4 behauptete, der Zustand der Projects-Workflows sei „per API weder les- noch überwachbar" — Abschnitt 1 derselben ADR sagt das Gegenteil (über GraphQL lesbar, nur nicht schreibbar), und er wurde in der Review-Session gelesen. Die Begründung des Zurücklesens steht jetzt auf dem tragfähigen Grund: Zurückgelesen wird nicht der Workflow, sondern sein Ergebnis, und das trifft auch einen Workflow, der zwar läuft, aber auf einen falschen Zielwert konfiguriert ist.

**Bewusst nicht gebaut:** ein statischer Anker, der das Zurücklesen in `ship-feature` in CI festhält. Jeder brauchbare Anker müsste entweder den Lesebefehl in die Skill-Datei duplizieren (die Datei verweist bewusst auf die Sammlung in `github-board`, statt ihn zu wiederholen) oder auf eine Formulierung prüfen. Als benannte Beobachtungspflicht geführt, nicht als Test.

## Offene Fragen

Keine. Die vier Produktentscheidungen und die zwei Risiko-Abwägungen sind im Abschnitt „Entscheidungen" festgehalten.

## Out of Scope

- Die Schärfung des Issue-**Titels** im Refinement — das bleibt Issue #288.
- Zusätzliche Themen-Tags für Issues (frontend, backend, pipeline …) — das bleibt Issue #259.
- Änderungen am Rollenmodell oder an den fachlichen Arbeitsschritten selbst. Es ändert sich, **wo** und **wodurch** ein Zustand entsteht, nicht **welche** Arbeit geschieht.
- Autonom, ohne Daniels Session laufende Agenten. Der Lebenszyklus bleibt session-getriggert.
- Änderungen am Board selbst über die Statuswerte hinaus (Feldnamen, Prioritätswerte, Ansichten bleiben).
