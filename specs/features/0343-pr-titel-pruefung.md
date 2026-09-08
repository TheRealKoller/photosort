# 0343 - Vollständiger Changelog durch geprüfte Pull-Request-Titel

**Status:** Accepted
**Erstellt:** 2026-09-08
**Bezug:** [Issue #343](https://github.com/TheRealKoller/photosort/issues/343)

## Ziel

Pull Requests werden in diesem Repository mit `COMMIT_OR_PR_TITLE` gesquasht — der PR-Titel wird damit
zum Titel des Merge-Commits auf `main`, und genau diese Commit-Titel wertet `release-please`
(ADR [`0008`](../decisions/0008-automated-semver-releases.md)) aus. Trägt ein Titel kein
Conventional-Commit-Präfix, kann der Parser den Commit nicht klassifizieren und übergeht ihn **still**:
keine Fehlermeldung, kein rotes Signal, kein Changelog-Eintrag, kein Versions-Bump. Der Defekt ist
nicht theoretisch und nicht abgeschlossen — nachgemessen am 2026-09-07 über die letzten 80
First-Parent-Merges auf `origin/main` sind es **fünf** Titel ohne zulässiges Präfix; der jüngste
(`Projekte löschen mit Namensbestätigung (Spec 0044) (#351)`) wurde gemergt, nachdem das Issue bereits
geschrieben war.

Gelöst ist das Problem nur, wenn ein präfixloser Titel **vor** dem Merge auffällt. Danach ist er nicht
mehr korrigierbar: Der Commit steht auf `main`, `release-please` hat ihn bereits übergangen, und der
fehlende Changelog-Eintrag bleibt dauerhaft fehlen. Eine Regel, die nur dokumentiert ist, hat dabei
dieselbe Halbwertszeit wie der Kommentar, der über 40 Läufe hinweg niemanden erreicht hat
(ADR [`0060`](../decisions/0060-release-pr-merge-von-hand-auto-merge-entfaellt.md)) — deshalb ist das
Ziel dieser Spec ein **maschinelles Gate**, keine weitere Zeile Prosa.

## User Story

Als Daniel möchte ich, dass ein Pull Request mit unbrauchbarem Titel gar nicht erst mergebar ist,
damit jede Änderung auf `main` klassifiziert wird und keine Arbeit mehr still aus dem Changelog fällt.

## Akzeptanzkriterien

- [ ] **AK 1 — Jeder PR-Titel wird automatisch auf ein Conventional-Commit-Präfix geprüft.** Der Workflow
      `.github/workflows/pr-titel.yml` läuft auf `pull_request` mit den Typen
      `[opened, edited, reopened, synchronize]`.
- [ ] **AK 2 — Ein fehlschlagender PR kann tatsächlich nicht nach `main` gemergt werden.** *Gilt als
      **offen**, bis der Job-Name `pr-titel` als sechster Kontext in `required_status_checks.contexts`
      der Branch Protection auf `main` steht.* Das ist eine Repository-Einstellung außerhalb des Codes,
      die kein Agent dieses Projekts setzt und die erst **nach** dem Merge gesetzt werden kann — ein
      geforderter Kontext ohne meldenden Lauf blockierte sonst jeden offenen PR dauerhaft mit
      `Expected — waiting for status to be reported`. Das Kommando steht im PR-Body unter
      `## Lokal nachzuholen`. Bis der Wert gesetzt ist, ist die Prüfung sichtbar, aber nicht bindend;
      dieses AK gilt nicht deshalb als erfüllt, weil der Workflow rot werden kann.
- [ ] **AK 3 — Die Prüfung greift unabhängig davon, wie der PR entstanden ist.** Sie hängt am Ereignis
      `pull_request`, nicht am Ablauf `ship-feature` — ein von Hand über die GitHub-Oberfläche
      eröffneter PR wird genauso geprüft.
- [ ] **AK 4 — Die Fehlermeldung sagt, was fehlt und welche Präfixe zulässig sind**, ohne dass jemand
      eine Datei nachschlagen muss. Sie nennt alle zehn Typen und die zulässige Form
      (`typ(scope)!: Beschreibung`).
- [ ] **AK 5 — Ein korrigierter Titel wird ohne weiteren Handgriff erneut geprüft und der PR wieder
      mergebar.** Getragen vom Ereignistyp `edited`; `synchronize` ist ebenfalls nötig, weil Required
      Status Checks pro Head-SHA ausgewertet werden.
- [ ] **AK 6 — Ein korrekter Titel besteht unverändert, ohne zusätzlichen Handgriff im Normalfall.**
      Am Bestand belegt: von den letzten 80 Merges bestehen alle bis auf die fünf bekannten
      präfixlosen Titel.
- [ ] **AK 7 — Die Titelregel ist dort dokumentiert, wo PRs entstehen:** `.github/pull_request_template.md`,
      `CLAUDE.md`, die Operation `pr-erstellen` des Skills `github-access` und der Skill `ship-feature`.
      Testgebunden ist davon die Existenz der Erwähnung in der PR-Vorlage (ohne Wortlautbindung) sowie
      die Deckungsgleichheit der Typenliste in `CLAUDE.md` mit dem Regex.
- [ ] **AK 8 — Die bestehende Regel zu `Closes #NNN` bleibt unangetastet.** Der Bezug-Block der
      PR-Vorlage wird wörtlich unverändert übernommen; das Schlüsselwort gehört weiterhin
      ausschließlich in den Body, nie in den Titel.

## Datenmodell-Bezug

Nicht betroffen. Reine CI-/Prozess-Änderung ohne Anwendungscode, ohne Entität, ohne Migration.
[`docs/architecture.md`](../../docs/architecture.md) bleibt unverändert — das Dokument beschreibt
weder CI-Workflows noch Repository-Einstellungen.

## Architektur / Umsetzung

Festgelegt in ADR [`0064`](../decisions/0064-pr-titel-pruefung-eigener-blockierender-workflow.md)
(„PR-Titel-Prüfung als eigener, blockierender Workflow statt externer Action"). Kurzfassung mit den
beiden Korrekturen aus der Security-Konsultation, die die dortige Skriptskizze ändern:

1. **Eigener Workflow, nicht ein Job in `ci.yml`.** Der Ereignistyp `edited` trägt AK 5 — in `ci.yml`
   ergänzt, ließe er bei jeder Titel- oder Body-Bearbeitung den gesamten Prüfsatz (backend, frontend,
   e2e, docker-compose-check, demo-scripts) neu laufen. `ci.yml` bleibt unverändert.
2. **Eigene Prüfung, keine externe Action.** Die Fachlichkeit ist ein einziger erweiterter regulärer
   Ausdruck, geprüft mit `grep -E`. Gründe: Verhältnismäßigkeit (eine Zeile Regex gegen eine
   Dauerabhängigkeit mit Drittanbieter-JavaScript im PR-Kontext und eigenem SHA-Pinning), die frei
   formulierbare deutsche Meldung (AK 4) und die Testbarkeit — der Regex steht als Shell-Variable in
   der Workflow-Datei und wird von `scripts/tests/` **von dort ausgelesen und ausgeführt**, ohne zweite
   Kopie, die driften könnte.
3. **Der Titel erreicht das Skript ausschließlich über `env:`** (`PR_TITLE: ${{ github.event.pull_request.title }}`)
   und darin ausschließlich als `"$PR_TITLE"`, nie als Kommandoargument — er geht über stdin an `grep`.
   Kein `actions/checkout`, `permissions: {}`, `LC_ALL: C.UTF-8`.
4. **Zehn zulässige Typen**, Scope und Breaking-Marker erlaubt:
   `^(build|chore|ci|docs|feat|fix|perf|refactor|revert|test)(\([^()]+\))?!?: [^[:space:]]`.
   `CLAUDE.md` wird im selben PR von sechs auf diese zehn Typen erweitert (von Daniel am 2026-09-07
   ausdrücklich so entschieden) — Anlass ist, dass `ci:` auf `main` bereits in Gebrauch ist und die enge
   Liste einen etablierten, korrekten Titel ablehnen würde.
5. **Korrektur gegenüber der ADR-Skizze — Steuerzeichen-Wache vor jeder Verarbeitung und vor jeder
   Ausgabe.** Zwei Gründe, beide tragend und beide nachgemessen: `grep` arbeitet zeilenweise, ein
   mehrzeiliger Titel bestünde, sobald *irgendeine* Zeile passt (`ohne Präfix\nfeat: zweite Zeile`
   besteht in der ADR-Fassung); und der Actions-Runner liest jede Zeile der Step-Ausgabe auf
   Workflow-Kommandos (`::error::`, `::stop-commands::`, GHSA-mfwh-5m23-j46w). Umgesetzt als
   `if [[ "$PR_TITLE" == *[[:cntrl:]]* ]]` **vor** allem anderen. Der Titel wird in dieser einen
   Meldung bewusst **nicht** ausgegeben.
6. **Korrektur gegenüber der ADR-Skizze — mehrzeilige Titel werden abgewiesen, nicht auf ihre erste
   Zeile reduziert.** Wie GitHub einen zeilenumbruchhaltigen Titel in die Commit-Betreffzeile
   überführt, ist nicht dokumentiert (Recherche 2026-09-07: die REST-/GraphQL-Referenz nennt für
   `title` weder Zeichen- noch Längenbeschränkung noch Normalisierung). Sich darauf zu stützen wäre
   geraten — in genau der Fehlerklasse, gegen die diese Story antritt.
7. **Kein Befund, dreimal nachgemessen** (damit es nicht ein viertes Mal geprüft wird): `set -euo pipefail`
   reißt den Step bei einem `grep`-Nichttreffer **nicht** ab, weil das `grep -q` in einer `if`-Bedingung
   steht und `errexit` dort abgeschaltet ist — die Fehlermeldung wird erreicht. `pipefail` + `grep -q`
   erzeugt keine SIGPIPE-Falschablehnung. Die Anführungszeichen um `"$MUSTER"` sind tragend, nicht
   kosmetisch (das Muster enthält ein Leerzeichen).
8. **`concurrency`-Gruppe** über `${{ github.workflow }}-${{ github.event.pull_request.number }}` mit
   `cancel-in-progress: true` — der Schlüssel ist eine von GitHub vergebene Zahl, nie `github.head_ref`
   und nie der Titel.
9. **Der Job-Schlüssel lautet `pr-titel` und trägt kein `name:`.** Er *ist* der Kontextname der Branch
   Protection; ein Override oder eine Umbenennung bräche die Zusage nicht sichtbar, sondern ließe den
   geforderten Kontext dauerhaft auf `Expected` stehen und blockierte jeden PR des Repositories.

**Betroffene Dateien, in dieser Reihenfolge (Test zuerst, rot):**

1. `scripts/tests/test_pr_titel_pruefung.py` (neu)
2. `.github/workflows/pr-titel.yml` (neu)
3. `scripts/tests/test_release_workflow_ohne_selbstmerge.py` (`pr-titel.yml` in `PFLICHT_WORKFLOWS`,
   `MINDESTZAHL_WORKFLOWS` auf 3)
4. `CLAUDE.md` (Typenliste auf zehn, PR-Konvention um die Titelregel)
5. `.github/pull_request_template.md` (Titelregel ergänzen, Bezug-Block wörtlich unverändert)
6. `.claude/skills/github-access/SKILL.md` (ein Satz an der Operation `pr-erstellen`; **keine**
   achtzehnte Operation)
7. `.claude/skills/ship-feature/SKILL.md` (Titelregel beim Formulieren des PR-Titels)

**Falle beim Umsetzen:** Das Kommando zum Setzen der Branch Protection darf **nicht** in `CLAUDE.md`
oder eine Datei unter `.claude/` geschrieben werden — dort ist jeder `gh`-Aufruf außerhalb des
Operationskatalogs verboten (ADR [`0061`](../decisions/0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md),
gehalten von `scripts/tests/test_github_zugriff_an_einer_stelle.py`). Es gehört in diese Spec bzw. den
PR-Body; `specs/` liegt außerhalb jenes Suchraums.

## Teststrategie

Festgelegt in [`../architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md), Abschnitt
„Dritte Anwendung seit Spec 0343". Kern:

- **Die statische Workflow-Zusicherung wird ausführend.** `scripts/tests/test_pr_titel_pruefung.py`
  extrahiert den `run:`-Blockskalar aus `.github/workflows/pr-titel.yml`, dedentet ihn und lässt ihn
  mit `bash` und gesetztem `PR_TITLE` gegen eine Positiv- und eine Negativtabelle laufen. Zugesichert
  wird je Fall **Exit-Code und Ausgabe** — ein Skript, das den Fehler erkennt, ihn aber nur ausgibt
  statt mit `exit 1` zu enden, wäre sonst grün und wirkungslos.
- **Injektions-Härte als Whitelist, nicht als Blacklist:** eine **ortsgebundene Allowlist** über
  jeden `${{ }}`-Ausdruck der Datei — jeder Ausdruck ist namentlich festgelegt und muss auf seiner
  vorgesehenen Zeile stehen, ein weiterer fällt auf; im `run:`-Block steht überhaupt keiner,
  `github.` kommt außerhalb der Ausdrücke nicht vor, `PR_TITLE` wird nur in Anführungszeichen
  verwendet, **keine einzige** `uses:`-Zeile, kein `secrets.`-Verweis, `permissions: {}` vorhanden.
  *(Die zunächst vorgesehene Fassung „genau ein `${{`-Vorkommen in der ganzen Datei" ist verworfen:
  Sie ist mit dem ebenfalls verbindlichen `concurrency`-Schlüssel nicht gleichzeitig erfüllbar — es
  sind drei Ausdrücke. Die Allowlist ist nicht schwächer und trägt beide Vorgaben.)*
- **Die Locale ist testgebunden, nicht nur festgeschrieben:** `LC_ALL` muss im `env:`-Block stehen und
  einen UTF-8-Wert tragen. `[[:cntrl:]]` ist locale-abhängig — unter `LC_ALL=C` fielen U+0085, U+2028
  und U+2029 aus der Wache heraus (gemessen), ohne dass irgendetwas rot würde. Belegt wird das
  Verhalten, nicht nur die Zeichenkette: je ein Negativfall mit diesen drei Zeichen.
- **Job-Identität:** genau ein Job, Schlüssel `pr-titel`, kein `name:`.
- **Deckungsgleichheit** der Typenmenge im extrahierten Regex mit der Liste in `CLAUDE.md`; die
  Präfixe der Fehlermeldung werden aus dem extrahierten Muster abgeleitet, nicht abgeschrieben.
- **Mehrzeiliger Titel als eigener Negativfall**, mit der Zusicherung, dass die Meldung der Wache den
  Titel nicht ausgibt.
- **AK 7 als reine Existenzprüfung:** `.github/pull_request_template.md` enthält das Wort „Titel" und
  mindestens ein Präfixbeispiel der Form `feat:`. Keine Wortlautbindung.
- **Selbstschutz gegen einen leeren Suchraum:** jede Extraktion scheitert laut mit `ValueError`
  (Muster `_pruefe_nicht_leer` des Nachbartests), und der Ausführungs-Helfer selbst besteht eine
  Gegenprobe — ein bewusst unpassendes Muster darf einen Positivfall nicht bestehen lassen.
- **Gegenprobe im Workflow selbst:** Der `run:`-Block hält einen bekannt guten und einen bekannt
  schlechten Beispieltitel gegen dasselbe Muster, bevor der echte Titel geprüft wird. Das ist die
  einzige Zusage, die im Runner-Environment selbst greift (Locale, `grep`-Variante) und die der
  lokale Testlauf strukturell nicht geben kann.

Der Test läuft im CI-Job `demo-scripts`, also außerhalb des Backend-Coverage-Gates.

**Was kein Test dieses Repositories beweist** (Beobachtungspflichten am offenen PR, gehören in den
PR-Body): dass der Merge tatsächlich verhindert wird (Branch-Protection-Einstellung, siehe AK 2), und
dass GitHub bei `edited` erneut auswertet und der PR danach wieder mergebar wird — der Umsetzungs-PR
selbst ist dieser Lauf und kann durch eine einmalige, absichtliche Titeländerung Negativfall und
Wiederfreigabe in derselben Timeline zeigen.

## UI/UX

**Nicht relevant.** Das Feature hat keine sichtbare Oberfläche: Es besteht aus einer
GitHub-Actions-Workflow-Datei, einem Repo-Konsistenztest und Dokumentationszeilen. Kein Frontend-Code,
keine Komponente, kein Design-System-Bezug. Die einzige menschenlesbare Ausgabe ist die Fehlermeldung
des Workflow-Laufs — sie ist als AK 4 geführt und inhaltlich, nicht gestalterisch festgelegt.
`ux-ui-designer` wurde deshalb nicht konsultiert.

## Security

Aufgenommen in [`../architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md),
Sektion „PR-Titel-Prüfung als eigener, blockierender Workflow" unter „Angriffsflächen". Einstufung:
**sicherheitsrelevant, kein Blocker — mit zwei Muss-Kriterien**, die die Skriptfassung aus dem ADR
ändern (oben als Punkte 5 und 6 eingearbeitet).

Neu ist genau **eine** Eigenschaft, und sie rechtfertigt den Abschnitt: Zum ersten Mal reicht ein
Workflow dieses Repositories **von außen frei wählbaren Fremdtext** in einen `run:`-Step. Das
Repository ist öffentlich; einen PR-Titel setzt jeder, der einen Fork-PR eröffnet, und ändert ihn
danach beliebig oft weiter (`types: [edited]`). Alles Übrige ist Reduktion gegenüber jedem bestehenden
Workflow: kein `actions/checkout`, kein Secret, keine externe Action, `permissions: {}`, ein Step.

- **Die `env:`-Form schließt die Script-Injection** — nachgemessen: ``feat: `id` $(id) "x" ; rm -rf /``
  läuft durch und wird unverändert als Text behandelt, kein Teilstring wird ausgeführt. Testgehalten
  statt kommentiert (Whitelist-Zusicherung oben).
- **`permissions: {}` ist richtig; `contents: read` wäre bereits zu viel.** Der Job liest kein
  Repository-Dateisystem und ruft keine GitHub-API — der Titel kommt aus der Ereignis-Nutzlast, das
  Melden des Check-Ergebnisses macht der Actions-Dienst. **Anker für später:** Kommt je ein
  `actions/checkout` oder ein `gh`-Aufruf hinzu, ist `contents: read` fällig und der Job führt erstmals
  Inhalte aus dem PR aus — dann ist der Sicherheitsabschnitt neu zu schreiben.
- **`pull_request_target` ist ausgeschlossen** (repo-weites Verbot aus Spec 0008, maschinell gehalten
  von `scripts/tests/test_release_workflow_ohne_selbstmerge.py`); der neue Workflow fällt ab sofort
  unter diesen Test.
- **Ressourcenmissbrauch über `edited`** ist real, aber gering (keine Kosten bei öffentlichen
  Repositories, kein Secret, keine Rechte) — die `concurrency`-Gruppe genügt.
- **Kein Schutz gegen böswillige Umgehung:** Bei `pull_request` stammt die ausgeführte Workflow-Datei
  aus dem Merge-Stand des PRs. Das gilt unverändert für `backend`, `frontend`, `e2e`,
  `docker-compose-check` und `demo-scripts` und ist kein neuer Umstand. Löschen hilft dem Angreifer
  nicht (der geforderte Kontext bliebe auf `Expected` stehen und blockierte den Merge); es bliebe
  allein das Aufweichen des Musters, und das ist eine sichtbare Zeile im Diff, den ein Mensch merged.
- **Bewusst offen: ein Bidi-Override hinter dem Präfix** (`feat: ‮…`) besteht die Prüfung. Der Workflow
  prüft *Klassifizierbarkeit*, nicht Wohlgeformtheit; die volle Wohlgeformtheit (Bidi, Zero-Width,
  U+0085/U+2028/U+2029) ist ein zweites Kriterium mit eigener Zeichenliste, eigener Meldung und eigenen
  Falschalarmen und wäre hier Scope Creep. Als bekannte Lücke im Sicherheitskonzept geführt, nicht
  wegformuliert — die Steuerzeichen-Wache ist der Teil davon, der aus eigenem Recht mitkommt.

## Entscheidungen

- **`architect` konsultiert (Schritt 1):** Der Ansatz war offen (eigener Workflow vs. Job in `ci.yml`
  vs. externe Action) und die Wahl hat Dauerfolgen (Trigger-Kosten, externe Abhängigkeit) → ADR 0064.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Das Feature erzeugt keine sichtbare Oberfläche —
  eine Workflow-Datei, ein Test, Dokumentationszeilen. Es gibt keine Komponente, keinen Zustand und
  keinen Design-System-Bezug, zu dem er etwas festlegen könnte.
- **`test-engineer` konsultiert (Schritt 3):** Der zu prüfende Gegenstand ist ein Shell-Skript in einer
  YAML-Datei, für das es im Projekt bisher nur *statische* Zusicherungen gab — die Frage, wie weit ein
  Test hier gehen kann, war offen und ist mit „ausführend statt textlich" beantwortet.
- **`security-engineer` konsultiert (Schritt 4):** Der Workflow reicht erstmals von außen frei
  wählbaren Fremdtext in einen `run:`-Step eines öffentlichen Repositories — die Standard-Angriffsfläche
  für Script-Injection in Actions.
- **Zehn statt sechs Conventional-Commit-Typen** (von Daniel am 2026-09-07 entschieden, Option „Auf
  zehn erweitern"): `build`, `ci`, `perf`, `revert` kommen hinzu. Anlass ist `ci:`, das auf `main`
  bereits in Gebrauch ist — eine Prüfung, die korrekte Praxis ablehnt, wird umgangen oder aufgeweicht.
- **Mehrzeilige Titel werden abgewiesen, nicht auf die erste Zeile reduziert** (technische
  Detailentscheidung innerhalb des akzeptierten Rahmens): Das Verhalten von GitHub beim Squash ist
  nicht dokumentiert, und eine unbelegte Serverseite darf nicht als Schutz eingeplant werden.
- **AK 7 wird über eine reine Existenzprüfung testgebunden** (technische Detailentscheidung): Ohne sie
  hielte AK 7 gar nichts. Ohne Wortlautbindung, damit die Prüfung nicht bei jeder Umformulierung der
  Vorlage rot wird — das bleibt im Rahmen von ADR 0064 („nur die Präfixliste testgebunden, die Prosa
  nicht"), weil geprüft wird, *dass* die Regel dasteht, nicht *wie*.
- **Kein achtzehnter Eintrag im Operationskatalog `github-access`:** Die Titelregel ist eine
  Eigenschaft des Titels, den `pr-erstellen` ohnehin schon setzt — ein Satz an der bestehenden
  Operation, keine neue.

## Offene Fragen

Keine. Die einzige Produktentscheidung (Umfang der Typenliste) ist am 2026-09-07 von Daniel
beantwortet.

## Out of Scope

- **Nachtragen der bestehenden Changelog-Lücke** (#341, #340, #337 und der inzwischen hinzugekommene
  #351). Die Commits stehen auf `main`, `release-please` hat sie übergangen; diese Story verhindert
  den nächsten Fall, sie repariert keinen vergangenen.
- **Prüfung der Einzel-Commit-Nachrichten** innerhalb eines PRs. Beim Squash zählt allein der Titel.
- **Volle Wohlgeformtheit des Titels** (Bidi-Overrides, Zero-Width-Zeichen hinter dem Präfix) — siehe
  „Security"; eigenes, zweites Kriterium, gehört in eine eigene Story, die Issue- und PR-Titel an
  **einem** Maßstab misst.
- **Inhaltliche Richtigkeit der Klassifikation.** Ein `chore:`-Titel für eine Funktionsänderung besteht
  die Prüfung und erscheint trotzdem nicht im Changelog — zugesichert ist, dass klassifiziert *wird*,
  nicht dass gut klassifiziert wird.
- **Der Defekt des Release-Workflows** aus #178 (dauerhaft rot) ist unabhängig und bereits behoben.
