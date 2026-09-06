# 0178 - Release-Workflow ohne Selbst-Merge

**Status:** Accepted
**Erstellt:** 2026-09-06
**Bezug:** [Issue #178](https://github.com/TheRealKoller/photosort/issues/178). ADR: [`decisions/0060-release-pr-merge-von-hand-auto-merge-entfaellt.md`](../decisions/0060-release-pr-merge-von-hand-auto-merge-entfaellt.md). Revidiert den Self-Merge-Teil von Spec [`0008`](./0008-automated-semver-releases.md) / ADR [`0008`](../decisions/0008-automated-semver-releases.md).

## Ziel

Bei jedem Push auf `main` meldet der Release-Workflow einen Fehler — bei allen 40 zuletzt gelisteten Läufen, nicht nur gelegentlich. Die eigentliche Release-Arbeit ist zu diesem Zeitpunkt bereits erledigt: Version, Tag, GitHub-Release und Release-PR entstehen korrekt. Der Fehler betrifft ausschließlich den anschließenden Versuch, den Release-PR ohne Zutun zu mergen — ein Schritt, der seit seiner Einführung nie gegriffen hat.

Der Schaden ist deshalb nicht der ausgefallene Automatismus, sondern das dauerhafte Rot: Ein Signal, das immer auf Fehler steht, sagt nichts mehr aus. Ein echter Release-Fehler wäre darin nicht zu erkennen, und jeder Push erzeugt eine Meldung, die ignoriert werden muss. Wie berechtigt diese Sorge ist, hat sich beim Schärfen dieser Story unmittelbar gezeigt: Im selben Lauf-Log steckte ein zweiter, unabhängiger Defekt (Merge-Titel ohne Conventional-Commit-Präfix, seit `v0.35.0` deshalb kein Release mehr — [Issue #343](https://github.com/TheRealKoller/photosort/issues/343)), den das Dauerrot verdeckt hatte.

Daniel prüft und mergt Release-PRs bewusst selbst und will das beibehalten. Das automatische Mergen entfällt deshalb ersatzlos, statt repariert zu werden — damit verschwindet zugleich der einzige unbeaufsichtigte Merge-Pfad nach `main`. Ein Alarm für künftig fehlschlagende Release-Läufe bleibt weiterhin außen vor; diese Lücke ist in Spec 0008 bereits als bewusst akzeptiert festgehalten.

## User Story

Als Daniel möchte ich, dass der Release-Workflow nach jedem Push auf `main` fehlerfrei durchläuft, damit ein rotes Signal wieder bedeutet, dass tatsächlich etwas kaputt ist.

## Akzeptanzkriterien

- [ ] **AK 1 — Negativ-Fall (der heute bricht):** Der `release-please`-Lauf zum Merge-Commit dieser Story auf `main` endet mit `conclusion: success`. Nachweis: `gh run list --workflow=release-please.yml --branch=main --limit=1 --json databaseId,headSha,conclusion` zeigt `success` für genau den Merge-SHA dieses PRs, und der Lauf zeigt genau einen Step. Zusätzlich entsteht **kein** Release-PR — der PR-Titel ist bewusst `ci:` und damit nicht releasable.
- [ ] **AK 2 — Positiv-Fall (Beobachtungspflicht, bleibt zunächst offen):** Der erste nachfolgende Lauf auf `main`, dessen Merge-Commit mindestens einen `feat:`/`fix:`-Anteil trägt, endet ebenfalls mit `conclusion: success` und legt bzw. aktualisiert den Release-PR. Dieser Nachweis ist mit dem Merge dieser Story strukturell **nicht** führbar (der eigene Merge ist per Entwurf nicht releasable) und wird als benannte Beobachtungspflicht mit Ergebnisvermerk am Issue #178 festgehalten, nicht als abgehaktes Kriterium. Solange Issue #343 besteht, kann ein releasable Merge auf sich warten lassen — AK 2 bleibt dann sichtbar offen, statt stillschweigend als erfüllt zu gelten.
- [ ] **AK 3a — statisch, sofort prüfbar:** Der Diff an `release-please.yml` enthält ausschließlich Löschungen (der zweite Step, `id: release`) plus die Kommentar-Ergänzung — keine Änderung an Action-SHA, `with:`-Werten oder Trigger.
- [ ] **AK 3b — empirisch:** Die tatsächliche Entstehung von Version, Tag, GitHub-Release und Changelog ist an denselben Lauf gekoppelt wie AK 2.
- [ ] **AK 4 — kein Auto-Merge mehr:** Am ersten entstehenden Release-PR gilt `gh pr view <n> --json state,autoMergeRequest` → `state: OPEN`, `autoMergeRequest: null`. Ausdrücklich **nicht** Teil der Zusage ist das Repo-Setting „Allow auto-merge": Es bleibt unverändert `true`; ein aktiviertes Setting ohne aktivierte Auto-Merge-Anforderung mergt nichts und ist kein Restdefekt, der „nachgebessert" werden müsste.
- [ ] **AK 5 — Dokumentation nachgezogen, im selben PR:** Die Self-Merge-Zusage ist an allen vier Stellen als überholt gekennzeichnet: `specs/features/0008-*.md` (Statuszeile, `allow_auto_merge`-AK, Auto-Merge-AK, Datei-Beschreibung, Teststrategie, Rollback-Abschnitt, Offene Fragen), `specs/decisions/0008-*.md` (Statuszeile), `specs/architecture/0003-securitykonzept.md`, `specs/architecture/0002-testkonzept.md`. ADR 0060 hält die Revision nachvollziehbar fest.
- [ ] **AK 7 — Der Guard-Test blockiert, statt nur zu warnen:** Der CI-Job `demo-scripts` ist Required Status Check der Branch Protection auf `main`. Nachweis: `gh api repos/TheRealKoller/photosort/branches/main/protection --jq '.required_status_checks.contexts'` enthält `demo-scripts` zusätzlich zu den bisherigen vier (`backend`, `frontend`, `docker-compose-check`, `e2e`). **Fallstrick, zwingend zu beachten:** Die Branch-Protection-API ersetzt bei `PUT` das gesamte Objekt, nicht nur genannte Felder (bereits in Spec 0007 / im Testkonzept als Muster festgehalten) — vorher vollständig lesen, nur die `contexts`-Liste ergänzen, danach den Gesamtzustand gegen den Vorher-Stand diffen (`enforce_admins`, `required_approving_review_count`, `required_conversation_resolution` müssen unverändert sein).
- [ ] **AK 6 — Nachweis am echten Lauf:** Schritt 2 des Verifikationsmusters aus `specs/architecture/0002-testkonzept.md` entfällt strukturell (der Workflow triggert nur auf `push: branches: [main]`) und wird durch zwei benannte Proben am echten `main` ersetzt: Negativ-Probe = der eigene Merge (AK 1), sofort verfügbar; Positiv-Probe = der nächste releasable Merge (AK 2), Beobachtungspflicht. Kompensiert durch einen verschärften Schritt 1, der hier erstmals nicht nur aus Config-Prüfung besteht, sondern aus dem dauerhaft im Repo laufenden Guard-Test plus dem Diff-Review aus AK 3a.

## Datenmodell-Bezug

Nicht relevant — die Story berührt weder Entitäten noch Persistenz. Es ändern sich ausschließlich eine GitHub-Actions-Workflow-Datei, eine neue Testdatei und Dokumente unter `specs/`.

## Architektur / Umsetzung

### Neue ADR

[`decisions/0060-release-pr-merge-von-hand-auto-merge-entfaellt.md`](../decisions/0060-release-pr-merge-von-hand-auto-merge-entfaellt.md) (Accepted) hält die Revision der in ADR 0008 getroffenen Self-Merge-Entscheidung fest. ADR 0008 bleibt inhaltlich unangetastet und ist nur in seiner Statuszeile als an dieser einen Stelle teilweise revidiert gekennzeichnet — das im Repo dominante Muster (vgl. ADR 0025, 0047).

### Ursache und gewählter Ansatz

GitHub Actions wertet die `env:`-Ausdrücke eines Steps auch dann aus, wenn dessen `if:` zu `false` auswertet. `fromJson(steps.release.outputs.pr).number` bekommt ohne Release-PR-Output einen leeren String, der Lauf endet als Template-Fehler, der Job wird rot — obwohl Step 1 zu diesem Zeitpunkt fertig ist. Statt den Ausdruck abzusichern, verschwindet der ganze Step (bindende Produktentscheidung): eine Fehlerquelle weniger und zugleich der einzige unbeaufsichtigte Merge-Pfad nach `main` weniger.

Die Fehlerklasse ist unauffällig — der Ausdruck sieht durch das `if:` abgesichert aus und wurde über 40 Läufe hinweg als Rauschen ignoriert statt als Fehler erkannt. Ein Workflow-Kommentar allein hätte dieselbe Halbwertszeit; die Regel wird deshalb durch einen Guard-Test in der bestehenden `scripts/tests/`-Reihe (CI-Job `demo-scripts`) gehalten. Der Test ist zugleich der rote Ausgangspunkt des TDD-Zyklus für ein Feature, das sonst keinen ausführbaren Code hat.

### Betroffene Dateien

- **Geändert:** `.github/workflows/release-please.yml` — der Step „Auto-Merge fuer den Release-PR aktivieren" entfällt vollständig, samt `if:`, `env:` (`GH_TOKEN`, `PR_NUMBER`) und `run:`. Zusätzlich entfällt das nun tote `id: release` am verbleibenden Step (nichts referenziert es mehr; ein stehengelassenes `id:` lädt zur Wiedereinführung des Musters ein). Der Kopfkommentar wird um die Regel aus ADR 0060 ergänzt. `permissions:`-Block, Trigger, `with:`-Block und das SHA-Pinning bleiben unverändert. Zielzustand:

  ```yaml
  name: release-please

  # Laeuft additiv zu ci.yml (das unveraendert bleibt). Trigger bewusst strikt
  # auf "push: branches: [main]" begrenzt und darf laut Spec 0008/ADR 0008
  # (Security-Abschnitt) nie auf "pull_request_target" erweitert werden - das
  # Repo ist public, ein solcher Trigger wuerde Fork-PRs Zugriff auf das
  # RELEASE_PLEASE_TOKEN-Secret geben.
  #
  # Der Workflow besteht bewusst aus genau einem Step und wertet in keinem
  # "${{ }}"-Ausdruck einen Step-Output aus (ADR 0060): GitHub wertet die
  # Ausdruecke eines Steps auch dann aus, wenn dessen "if:" false ergibt - ein
  # "fromJson(steps.<id>.outputs.<x>)" auf einem leeren Output reisst den
  # gesamten Job als Template-Fehler mit. Wer hier je einen zweiten Step
  # ergaenzt, muss den Leer-Output-Fall selbst tragen; "if:" tut es nicht.
  # Gehalten von scripts/tests/test_release_workflow_ohne_selbstmerge.py.
  on:
    push:
      branches: [main]

  permissions:
    contents: write
    issues: write
    pull-requests: write

  jobs:
    release-please:
      runs-on: ubuntu-latest
      steps:
        # v4.4.1, gepinnt auf Commit-SHA statt auf den beweglichen Tag "v4"
        # (Supply-Chain-Haertung, siehe ADR 0008/Spec 0008 Security-Abschnitt).
        - uses: googleapis/release-please-action@5c625bfb5d1ff62eadeeb3772007f7f66fdcf071 # v4.4.1
          with:
            token: ${{ secrets.RELEASE_PLEASE_TOKEN }}
            config-file: release-please-config.json
            manifest-file: .release-please-manifest.json
  ```

- **Neu:** `scripts/tests/test_release_workflow_ohne_selbstmerge.py` — vier textbasierte Guard-Tests. Bewusst **keine** YAML-Bibliothek: PyYAML ist in `scripts/pyproject.toml` keine Abhängigkeit, und eine neue externe Abhängigkeit für vier Zusicherungen wäre unverhältnismäßig — die bestehenden Guard-Tests im selben Verzeichnis arbeiten genauso. Form nach dem Muster der Nachbardateien (`test_board_referenzfreiheit.py`): reine Prädikatfunktion auf übergebenem Text, dünner Leser für den echten Dateizustand, **Selbstschutz gegen leeren Suchraum** und **Gegenprobe gegen die drei historisch entfernten Zeilen**. Die Zusicherungen im Einzelnen:

  1. **Kein Step-Output-Verweis:** Im kommentarfreien Inhalt von `release-please.yml` kommen die Zeichenketten `steps.`, `needs.` und `fromJson(` **überhaupt nicht** vor. Bewusst ein Substring-Totalverbot statt eines Ausdruck-Regex: Ein Muster wie `\$\{\{[^}]*\bsteps\.` bricht an jeder geschweiften Klammer im Ausdruck ab und übersieht damit genau die Klasse, die es bewachen soll (`${{ format('{0}', steps.a.outputs.x) }}` enthält `}` in `'{0}'`), ebenso Zeilenumbrüche innerhalb von `${{ }}`. In einer 25-zeiligen Datei mit einem einzigen Zweck ist das Totalverbot zugleich schärfer und robuster. `needs.` ist mitverboten, weil dieselbe Auswertungsfalle bei Job-Outputs identisch auftritt. Die Fehlermeldung nennt die **Ursache** (Auswertung trotz `if: false`), nicht nur den Fund, und sagt, dass der Ausweg eine Regeländerung samt ADR-Revision ist — nicht das Aufweichen des Tests.
  2. **Kein Selbst-Merge in irgendeinem Workflow:** Keine Datei unter `.github/workflows/` (alle `*.yml`/`*.yaml`) enthält `\bgh\s+pr\s+merge\b`, `enablePullRequestAutoMerge`, `pulls/[^/\s"']+/merge\b` oder `auto[-_ ]?merge` — letzteres deckt die Marketplace-Actions (`peter-evans/enable-pull-request-automerge`, `pascalgn/automerge-action`) und `--auto`-Varianten mit ab, die ein späterer Wiedereinbau am ehesten hätte. Alle Muster case-insensitiv und umbruchtolerant (`\s+` statt festem Leerzeichen). Repo-weit statt nur für diese eine Datei, weil die Zusage aus AK 4 „CI mergt nichts von allein" lautet. Mit **benannter, begründeter Ausnahmeliste** nach dem Vorbild von `AUSNAHMEN` in `test_board_referenzfreiheit.py`, damit ein späteres bewusstes Dependabot-Auto-Merge eingetragen und begründet wird, statt den Test aufzuweichen.
  3. **Genau ein gepinnter Step:** Die Datei enthält **genau eine `uses:`-Zeile**, und diese lautet `googleapis/release-please-action@<40 Hex>`. Das kodiert „der Workflow besteht aus genau einem Step" mit, ohne Steps über Einrückung zählen zu müssen (der brüchige Weg), und hält zugleich die Supply-Chain-Härtung aus ADR 0008 fest, die beim Bearbeiten derselben Datei sonst still verloren gehen kann. 40-Hex-Muster statt festem SHA, damit ein Dependabot-Bump grün bleibt.
  4. **Der Workflow funktioniert noch, und `pull_request_target` kommt in keinem Workflow vor:** Trigger unverändert `push:` / `branches: [main]`; **kein** Workflow unter `.github/workflows/` verwendet `pull_request_target` (repo-weit geprüft, nicht nur in dieser Datei — das als Muss-Kriterium formulierte Verbot aus Spec 0008 für dieses public Repo, das bislang nur als Prosa im Kopfkommentar existierte und damit an genau der Datei hing, die diese Story anfasst); die drei `with:`-Werte sind vorhanden (`token: ${{ secrets.RELEASE_PLEASE_TOKEN }}`, `config-file:`, `manifest-file:`); die beiden dort referenzierten JSON-Dateien existieren im Repo. Diese vierte Zusicherung ist das Gegengewicht dazu, dass die ersten drei ausschließlich Verbote sind — eine mitgelöschte `with:`-Zeile passierte sie alle und fiele erst nach dem Merge auf. Im Datei-Docstring als „Sollzusagen aus Spec 0008, hier erstmals maschinell festgehalten" kennzeichnen, damit `review-requirements` sie nicht als Zusatzumfang liest.

  **Kommentar-Ausblendung ist zwingend:** Der Kopfkommentar der Workflow-Datei benennt die Verbote und enthält damit selbst die Wörter „Auto-Merge"/`fromJson(`. Ohne einen vorgeschalteten `wirksame_zeilen()`-Helfer, der **ganzzeilige** Kommentare überspringt (erstes Nicht-Leerzeichen ist `#`), macht genau die Dokumentation den Test rot, die er erzwingen soll. Bewusst **nicht** Inline-Kommentare abschneiden — ein naives Abschneiden an jedem `#` könnte Inhalt in Zeichenketten verstecken und den Test stillschweigend schwächen.

  **Ausdrücklich nicht getestet, obwohl naheliegend:** ein Verbot von `if:` im Workflow. Das übersprungene `if:` war der Auslöser, nicht die Ursache; ein `if:` an einem Step ohne Step-Output-Verweis ist harmlos, und ein Verbot würde eine legitime spätere Bedingung blockieren, ohne Risiko abzudecken.

- **Geändert:** `specs/decisions/0008-automated-semver-releases.md` — nur die Statuszeile (bereits erledigt).
- **Neu:** `specs/decisions/0060-release-pr-merge-von-hand-auto-merge-entfaellt.md` (bereits erledigt).
- **Geändert:** `specs/features/0008-automated-semver-releases.md` — punktuelle Nachträge im Repo-Muster (Durchstreichen plus datierter Verweis); historische Prosa wird nicht umgeschrieben (bereits erledigt).
- **Geändert:** `specs/architecture/0002-testkonzept.md` — zweite Anwendung des `push: main`-Ersatzmusters und Anpassung des Eintrags unter „Bekannte Lücken" (bereits erledigt).
- **Geändert:** `specs/architecture/0003-securitykonzept.md` — datierter Ergänzungseintrag, siehe `## Security`.

### Ausdrücklich unverändert

`.github/workflows/ci.yml`, `release-please-config.json`, `.release-please-manifest.json`, der `permissions:`-Block und das Action-Pinning in `release-please.yml`, das Repo-Setting `allow_auto_merge` (bleibt `true`, ADR 0060 Punkt 4), der Scope des `RELEASE_PLEASE_TOKEN` (ADR 0060 Punkt 5), `README.md` und `docs/` (geprüft: keine Datei dort erwähnt den Release-Workflow oder Auto-Merge — kein Nachzug nötig). **Ausnahme gegenüber der ursprünglichen Fassung dieser Spec:** Die Branch Protection auf `main` wird sehr wohl angefasst (AK 7, Entscheidung Daniels vom 2026-09-06) — ausschließlich durch Ergänzung von `demo-scripts` in `required_status_checks.contexts`, alle übrigen Felder bleiben unverändert.

### Umsetzungsreihenfolge

1. `scripts/tests/test_release_workflow_ohne_selbstmerge.py` schreiben — muss **rot** sein (`gh pr merge`, `fromJson(`, `steps.` sind alle noch da). Die Gegenprobe gegen die drei historischen Zeilen ist der belegte Rot-Nachweis.
2. Den Auto-Merge-Step samt `id: release` aus `.github/workflows/release-please.yml` entfernen, Kopfkommentar ergänzen → Test grün.
3. Nachtrag im Securitykonzept (siehe `## Security`).
4. Qualitätscheck: `ruff check .` und `pytest` im Verzeichnis `scripts/`.
5. **Branch Protection: `demo-scripts` als Required Status Check ergänzen (AK 7).** Erst den vollständigen Ist-Zustand lesen und sichern (`gh api repos/TheRealKoller/photosort/branches/main/protection`), dann ausschließlich die `contexts`-Liste um `demo-scripts` erweitern, danach den Gesamtzustand gegen den gesicherten Vorher-Stand vergleichen. Die API ersetzt bei `PUT` das gesamte Objekt — ein unvollständiger Aufruf löscht stillschweigend `enforce_admins`, `required_conversation_resolution` und die Review-Einstellungen. Dieser Schritt ist eine Änderung am echten Repo ohne Sandbox (Muster aus Spec 0007, Schritt 1) und **vor der Ausführung Daniel vorzulegen**.
6. Der PR-Titel lautet bewusst `ci: …` (nicht releasable): Damit ist der eigene Merge genau der Fall, der heute bricht — Push auf `main` ohne Release-relevante Änderung — und dient als direkter Nachweis für AK 1. Gleiches Vorgehen wie bei Spec 0008, die ihren eigenen Merge bewusst als Negativ-Probe genutzt hat.

Schritte 3–6 der ADR-/Spec-Nachträge sind zum Zeitpunkt der Spec-Erstellung bereits erledigt und liegen als Commit auf dem Feature-Branch.

## UI/UX

Nicht relevant — die Story berührt ausschließlich eine GitHub-Actions-Workflow-Datei, eine Testdatei und Dokumente unter `specs/`. Es gibt keine sichtbare Oberfläche, keine angezeigten Daten und keine Frontend-Komponente; `frontend/` wird nicht angefasst.

## Security

Sicherheitsrelevant, aber ausschließlich als **Reduktion**: Die Änderung entfernt den einzigen Workflow-Step, der ein Repo-Secret in die Umgebung einer Shell reicht, und den einzigen automatisierten Merge-Pfad nach `main`. Kein neuer Endpunkt, kein neuer Eingabepfad, keine geänderte Datensichtbarkeit, keine neue Abhängigkeit. Projektweite Einordnung: `specs/architecture/0003-securitykonzept.md`, Abschnitt „GitHub-Repository-Zugriff" (Nachtrag 2026-09-06).

**S1 — Der unbeaufsichtigte Merge-Pfad nach `main` entfällt; die ADR-0007-Bedingung gilt wieder ungeschmälert.** Das Sicherheitskonzept führt den Auto-Merge-Step seit 2026-07-29 als „neuen, unbeaufsichtigten automatisierten Merge-Pfad nach `main`" und hält fest, dass die Bedingung aus ADR 0007 zu `required_approving_review_count: 0` („nur sicher, solange ausschließlich Daniel Schreibzugriff hat") dadurch „im Geiste berührt" sei. Mit dem Wegfall schreibt kein Automatismus mehr ohne menschliche Einzelhandlung nach `main`. **Grenze der Aussage, bewusst benannt:** Der `RELEASE_PLEASE_TOKEN` behält `Contents: RW` + `Pull requests: RW` und kann die Merge-API weiterhin aufrufen — es entfällt der *Pfad*, nicht die *Fähigkeit*. Die Fähigkeit ist von den ohnehin nötigen Scopes nicht trennbar (S3), und ein Merge über den PAT unterläge derselben Branch Protection wie Daniel selbst (`enforce_admins: true`).

**S2 — Der Pfad war nie wirksam; die Änderung kodifiziert den Ist-Zustand.** Am 2026-09-06 gemessen (`gh api .../actions/workflows/release-please.yml/runs`): **alle 172 Läufe seit Bestehen** haben `conclusion: failure` — auch die auf Läufen mit existierendem Release-PR. Alle Release-PRs (#286 … #335) sind mit `mergedBy: TheRealKoller` gemergt. Der Auto-Merge-Step hat also nie erfolgreich gemergt. Das senkt das Risiko der Entfernung auf praktisch null (kein Verhalten geht verloren, das je funktioniert hätte) und ist zugleich der Grund, warum „ersatzlos" gegenüber „reparieren" auch sicherheitsseitig die bessere Wahl ist.

**S3 — Am PAT-Scope wird nichts frei, und das ist korrekt.** `Pull requests: RW`/`Contents: RW` braucht `release-please` unabhängig vom Auto-Merge (PR anlegen/aktualisieren, Release-Branch, Tag, Release), `Issues: RW` für die Zustands-Labels, `Metadata: R` als Pflichtminimum. Der PAT existiert zudem aus einem Grund, der mit Auto-Merge nichts zu tun hat: GitHubs Anti-Rekursionsregel — mit `GITHUB_TOKEN` liefe `ci.yml` auf dem Release-PR nicht an (ADR 0008, „Token/Berechtigungen"). Da der Release-PR weiterhin grüne Required Checks braucht, bleibt der PAT in vollem Umfang notwendig. Geprüft, nicht angenommen: **kein Scope reduzierbar.**

**S4 — Eine Fehlerklasse verschwindet mit dem Step, nicht nur der Defekt.** Nach der Änderung enthält der Workflow keinen `run:`-Step, keinen `env:`-Block mit einem Secret und keinen `${{ }}`-Ausdruck über einen Step-Output. Konkret: (a) `RELEASE_PLEASE_TOKEN` liegt in keiner Prozessumgebung einer Shell mehr und kommt im gesamten Repo genau einmal vor — als `with: token:`-Input der SHA-gepinnten Action; (b) die Ausgabe einer Drittanbieter-Action (`steps.release.outputs.pr`) fließt in keinen Ausdruckskontext mehr; (c) die im entfallenden Kommentar adressierte Script-Injection-Musterklasse hat in dieser Datei keinen Anknüpfungspunkt mehr. Die Überlegung, die dieser Kommentar trug, geht nicht verloren, sondern wandert in den Guard-Test (S6). (d) Nebenbefund zur Nachvollziehbarkeit: Ein Merge auf einem Release-PR, der `TheRealKoller` zugeschrieben ist, ist ab jetzt wirklich Daniel — vorher war die Zuschreibung nicht von einem PAT-Merge unterscheidbar, da der PAT unter seiner Identität läuft.

**S5 — `allow_auto_merge: true` und der `permissions:`-Block bleiben bewusst unverändert.** `allow_auto_merge` ist eine Fähigkeit, kein Pfad: sie muss pro PR von jemandem mit Schreibrecht aktiviert werden. Abschalten brächte keinen Schutzgewinn (mit dem PAT ließe sich ebenso direkt mergen, unter derselben Branch Protection), nähme aber eine manuelle Option — festzuhalten ist nur die Lesart für künftige Audits: `allow_auto_merge: true` belegt ab jetzt **nicht** mehr, dass ein automatisierter Merge-Pfad existiert. Der `permissions:`-Block (`contents`/`issues`/`pull-requests: write`) wirkt ausschließlich auf den `GITHUB_TOKEN` und nie auf ein als Secret hinterlegtes PAT; die Action nutzt den `GITHUB_TOKEN` nachweislich nicht (in `action.yml` @ `5c625bfb…` ist `${{ github.token }}` nur der Default des hier überschriebenen `token`-Inputs; `runs:` setzt keinen `env:`-Block; `src/index.ts` bezieht das Token einzig aus `core.getInput('token')`; `release-please` v17.3.0 `src/github.ts` enthält kein `process.env`). Der Block ist damit nach der Änderung **inert** — eine latente, nicht aktiv ausnutzbare Über-Privilegierung, die bewusst stehen bleibt. Er wird in dem Moment scharf, in dem der `token:`-Input entfiele oder ein `GITHUB_TOKEN`-verbrauchender Step (`actions/checkout`, `gh`) zurückkäme. Eine Reduktion auf `permissions: {}` wäre sauberes Least-Privilege im Sinne von Spec 0011 (die `release-please.yml` dort ausdrücklich offenließ), ist aber geringwertig und gehört nicht in diese Story — als Folgepunkt vermerkt, nicht als Auflage.

**S6 — Der Guard-Test ist die eigentliche Dauerwirkung, und er wird zur echten Schranke.** Er hält fest, was der entfallende Kommentar bisher nur behauptete. Aus Sicherheitssicht kommt zu den Invarianten des Testkonzepts eine dritte hinzu, die hier die wichtigste ist: **kein Workflow verwendet `pull_request_target`.** Das ist das schärfste Muss-Kriterium aus Spec 0008 (das Repo ist public — ein solcher Trigger gäbe Fork-PRs Zugriff auf `RELEASE_PLEASE_TOKEN`) und wurde bislang von nichts gehalten außer einem Kommentar in genau der Datei, die diese Story anfasst. Der Test beweist nicht, dass kein Workflow mergt; er verhindert die Rückkehr des bekannten Musters — das gehört so in seinen Docstring. **Damit die Invariante mehr ist als ein Hinweis**, wird der CI-Job `demo-scripts` in dieser Story zum Required Status Check der Branch Protection (AK 7) — bis dahin war er keiner (gemessen 2026-09-06: `backend`, `frontend`, `docker-compose-check`, `e2e`), ein Fehlschlag wäre sichtbar gewesen, hätte den Merge aber nicht blockiert. Für Konsistenztests an Prozess-Metadaten wäre das vertretbar; für eine Sicherheitsinvariante ist es die Differenz zwischen Hinweis und Schranke.

**Was durch die Änderung nicht besser wird (ehrlich benannt):** Das Leak-Risiko des `RELEASE_PLEASE_TOKEN` bleibt unverändert — er wird weiterhin bei jedem Push auf `main` an die Action gereicht. Die offene Lücke „Tag-Protection-Ruleset für `v*` fehlt" bleibt unberührt (am 2026-09-06 erneut geprüft: `gh api .../rulesets` liefert eine leere Liste). Und die bereits im Testkonzept geführte Lücke „kein Monitoring für hängende Release-PRs" bekommt mehr Gewicht: Warten ist jetzt der Normalzustand eines Release-PRs, ein *steckengebliebener* PR ist davon nicht mehr zu unterscheiden. Beides ist Verfügbarkeit/Prozess, keine Sicherheitsregression, und in dieser Story bewusst nicht adressiert.

## Teststrategie

**Testebene:** ausschließlich statische Guard-Tests in `scripts/tests/test_release_workflow_ohne_selbstmerge.py` (CI-Job `demo-scripts`, außerhalb des Backend-Coverage-Gates) — es gibt keinen ausführbaren Anwendungscode. Form nach dem Muster der Nachbartests: reine Prädikatfunktion auf übergebenem Text, dünner Leser für die echten Dateien, Selbstschutz gegen leeren Suchraum, Gegenprobe gegen die drei historisch entfernten Zeilen (zugleich der Rot-Nachweis des TDD-Zyklus). Die vier Zusicherungen stehen im Detail unter „Architektur / Umsetzung".

**Nicht getestet:** YAML-/Actions-Syntaxgültigkeit nach einer Änderung (keine YAML-Bibliothek in `scripts/`; `actionlint` geprüft und verworfen — es hätte genau diesen Defekt nicht gefunden, weil der Ausdruck statisch wohlgeformt war und der Fehler erst im Auswertungszeitpunkt entsteht) sowie das Laufzeitverhalten selbst. Dafür greift das `push: main`-Ersatzmuster: Negativ-Probe am eigenen `ci:`-Merge (AK 1), Positiv-Probe am nächsten releasable Merge (AK 2, Beobachtungspflicht, bis dahin offen).

**Edge Cases, die der Guard abdecken muss:** Kopfkommentar mit „Auto-Merge"/`fromJson(` (Kommentar-Ausblendung, der wahrscheinlichste Selbst-Rotfall); fehlende/umbenannte/leere Datei muss laut scheitern statt still grün zu werden; die Workflow-Aufzählung darf nicht leer sein und muss `ci.yml` enthalten; Dependabot-Bump der Action muss grün bleiben (40-Hex statt festem SHA); Groß-/Kleinschreibung und Mehrfach-Whitespace (`GH PR MERGE`, `gh  pr   merge`, `enablepullrequestautomerge`).

**Bewusstes Restrisiko:** Eine Kopie des Workflows unter anderem Namen (`release-please-2.yml`) wäre vom Merge-Verbot erfasst (das geht über alle Workflows), vom `steps.`-Verbot aber nicht — `ci.yml` referenziert legitim `steps.label-embedder-hash.outputs.sha256`, ein repo-weites `steps.`-Verbot wäre falsch.

**Testkonzept:** ergänzt (zweite Anwendung des `push: main`-Ersatzmusters, Anpassung des Auto-Merge-Eintrags unter „Bekannte Lücken") — bereits erledigt.

## Entscheidungen

- **Streichen statt Reparieren** (Produktentscheidung Daniels, 2026-09-06): Ein Guard im Ausdruck bekäme den Lauf grün, erhielte aber den unbeaufsichtigten Merge-Pfad. Daniel mergt Release-PRs bewusst selbst.
- **Doku wird im selben PR nachgezogen** (Produktentscheidung Daniels, 2026-09-06): Ohne den Nachzug beschriebe Spec 0008 ein Verhalten, das es nicht mehr gibt.
- **Revisions-Muster:** neue ADR 0060 plus annotierte Statuszeile in ADR 0008, nicht Änderung von ADR 0008 selbst. Das Repo praktiziert beides, die Statuszeilen-Annotation ist mit zehn Fällen (0017, 0023, 0025, 0032, 0037, 0041, 0047, 0048, 0052, 0056) das dominante Muster und lässt den Entscheidungstext unangetastet.
- **Substring-Totalverbot statt Ausdruck-Regex** im Guard-Test: Der ursprünglich vorgeschlagene Regex `\$\{\{[^}]*\bsteps\.` hat eine echte Lücke an geschweiften Klammern innerhalb des Ausdrucks und hätte genau die bewachte Klasse verfehlt.
- **Vierte Zusicherung ergänzt** (Trigger/`with:`-Werte unverändert): Die ersten drei Zusicherungen sind ausschließlich Verbote; ein zu weit gehendes Löschen fiele sonst erst nach dem Merge auf.
- **PAT-Scope bleibt unverändert, keine Folge-Story:** `gh pr merge --auto` brauchte `Pull requests: write` — genau das, was `release-please` zum Anlegen und Aktualisieren des Release-PRs ohnehin braucht. Durch den Wegfall wird keine Permission frei.
- **`allow_auto_merge` bleibt `true`:** Fähigkeit, kein Pfad — muss pro PR von einem Menschen aktiviert werden. Abschalten brächte keinen Sicherheitsgewinn, nähme aber eine manuelle Option.
- **Node-20-Deprecation-Warnung bleibt draußen, auch ohne Folge-Story:** Der Runner hebt bereits auf Node 24 an, die Action läuft durch. Kein Fehlerbild, nur eine Warnung, die mit dem nächsten regulären Versionssprung der Action verschwindet. Ein Sprung jetzt wäre eine Supply-Chain-Änderung (neuer SHA, neue Verifikation) und würde den einen verfügbaren Nachweis-Lauf mehrdeutig machen.
- **`actionlint` geprüft und verworfen:** ein neuer, extern nachzuladender Baustein, der genau diesen Defekt nicht gefunden hätte.
- **Wegwerf-Branch mit vorübergehend geweitetem Trigger geprüft und verworfen:** Er würde `release-please` mit dem echten Token gegen einen Nicht-`main`-Branch laufen lassen und dessen Zustand anfassen — höheres Risiko als der Erkenntnisgewinn.
- **AK 2 darf offen bleiben, die Spec trotzdem `Implemented` werden:** direkter Präzedenzfall in genau der Spec, die hier revidiert wird — Spec 0008 wurde mit ausdrücklich unabgehakten Kriterien gemergt („Nicht vorab prüfbar"). Die Offenheit bleibt sichtbar statt stillschweigend als erfüllt zu gelten.
- **`demo-scripts` wird Required Status Check** (Produktentscheidung Daniels, 2026-09-06, nach Vorlage der Abwägung): Der Guard-Test hält mit dem `pull_request_target`-Verbot eine echte Sicherheitsinvariante, lief aber in einem Job, der den Merge nicht blockiert. Preis, bewusst getragen: Ab jetzt kann jeder Test unter `scripts/tests/` einen Merge blockieren, nicht nur die Sicherheitsinvarianten — vertretbar, weil der Job netzwerkfrei und schnell ist.
- **`pull_request_target`-Verbot repo-weit statt nur in `release-please.yml`:** Die Zusage aus Spec 0008 gilt dem Repo, nicht einer Datei; sie hing bislang an einem Kommentar in genau der Datei, die diese Story anfasst.
- **SHA-Pinning-Prüfung bleibt auf `release-please.yml` beschränkt, nicht repo-weit auf alle Drittanbieter-Actions ausgedehnt:** Der Vorschlag war fachlich richtig (er erfasste auch künftig hinzukommende Actions), hätte aber eine Pinning-Konvention für `ci.yml` festgeschrieben, die nie entschieden wurde — `ci.yml` nutzt bewusst bewegliche Major-Tags für GitHub-eigene Actions. Das ist eine eigene Entscheidung und keine Nebenwirkung eines Workflow-Fixes.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story berührt ausschließlich eine GitHub-Actions-Workflow-Datei, eine Testdatei unter `scripts/tests/` und Dokumente unter `specs/`. Es gibt keinen konkret benennbaren Anhaltspunkt für eine sichtbare Oberfläche — kein Frontend-Verzeichnis im Diff, keine anzuzeigenden Daten, keine Eingabestelle.

## Offene Fragen

Keine offenen Fragen an Daniel. Die beiden Produktentscheidungen (ersatzloses Streichen, Doku-Nachzug im selben PR) sind getroffen; der beim Schärfen gefundene zweite Defekt ist als eigenes [Issue #343](https://github.com/TheRealKoller/photosort/issues/343) ausgelagert.

**Eskalationspunkt für später:** Sollte Issue #343 länger ungelöst bleiben, wird aus AK 2 „offen" faktisch „nie belegt". Dann ist die Frage an Daniel fällig, ob AK 2 anders belegt oder gestrichen wird.

## Out of Scope

- **Der Conventional-Commit-Präfix-Defekt** (Merge-Titel ohne Präfix, deshalb seit `v0.35.0` kein Release) — eigene Fehlerklasse, eigenes [Issue #343](https://github.com/TheRealKoller/photosort/issues/343). Bewusst getrennt, damit der eine verfügbare Nachweis-Lauf genau eine Änderung belegt.
- **Alarm/Monitoring für fehlschlagende Release-Läufe oder fehlerhafte Versions-Bumps** — in Spec 0008 bereits als bewusst akzeptierte Lücke geführt, bleibt es.
- **Anheben der `release-please-action`-Version** (Node-20-Warnung) — siehe Entscheidungen.
- **Reduktion des `RELEASE_PLEASE_TOKEN`-Scopes** — es wird durch den Wegfall keine Permission frei.
- **Änderung von Repo-Settings außer der Branch-Protection-Ergänzung aus AK 7** — insbesondere bleibt `allow_auto_merge` unangetastet.
- **Reduktion des `permissions:`-Blocks der `release-please.yml` auf `permissions: {}`** — nach der Änderung ist er inert (der einzige Step nutzt den `GITHUB_TOKEN` nicht), die Kürzung wäre sauberes Least-Privilege, aber geringwertig und mit dem Fallstrick, dass ein künftig ergänzter `GITHUB_TOKEN`-Verbraucher mit einem schwer zuzuordnenden Fehler bricht. Als Folgepunkt im Sicherheitskonzept unter „Bekannte Lücken" vermerkt.
- **Repo-weite SHA-Pinning-Prüfung für Drittanbieter-Actions** — siehe Entscheidungen.
- **Tag-Protection-Ruleset für `v*`** — bestehende offene Lücke aus Spec 0008, von dieser Story nicht berührt.
- **Nachträgliches Release für die drei bereits gemergten, nicht erfassten Änderungen** — gehört zu Issue #343.
