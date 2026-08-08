# 0008 - Automatisierte SemVer-Releases bei Merge nach `main`

**Status:** Accepted
**Erstellt:** 2026-07-29
**Bezug:** `idea-sharpener`-Gespräch mit Daniel, 2026-07-29. ADR: [`decisions/0008-automated-semver-releases.md`](../decisions/0008-automated-semver-releases.md).

## Ziel

Bei jedem PR-Merge nach `main` soll automatisch geprüft werden, ob seit dem letzten Release eine "releasable" Änderung (mind. ein `feat:`/`fix:`/`BREAKING CHANGE`-Commit) aufgelaufen ist. Ist das der Fall, soll automatisch ein Release entstehen: ein Git-Tag + GitHub-Release mit generiertem Changelog, sowie ein synchroner Versions-Bump in `backend/pyproject.toml` und `frontend/package.json`. Die nächste Versionsnummer wird automatisch nach Semantic Versioning aus den Conventional-Commit-Typen der aufgelaufenen Commits bestimmt (`feat:`→MINOR, `fix:`→PATCH, `BREAKING CHANGE`/`!`→MAJOR). Reine `docs:`/`chore:`/`test:`-Merges lösen kein Release aus.

Explizit **kein** Docker-Image-Tagging und **keine** Kopplung an das künftige, noch nicht eingerichtete Deploy-Tool "Dockhand" (dessen Trigger-Bedingung noch unklar ist) — beides bewusst getrennt gehalten.

Motivation: aktuell gibt es weder Git-Tags noch GitHub-Releases, und die Versionsfelder in `backend/pyproject.toml` (`0.1.0`) und `frontend/package.json` (`0.0.0`) wurden nie synchron/bewusst gepflegt. Ein automatisierter, konsistenter Release-Prozess schafft nachvollziehbare Versionsstände, ohne dass Daniel das manuell pflegen muss.

## User Story

Als Daniel (alleiniger Entwickler und Betreiber von PhotoSort) möchte ich, dass nach jedem gemergten PR mit relevanten Änderungen automatisch ein korrekt versioniertes Release entsteht, damit ich jederzeit einen nachvollziehbaren, nach Semantic Versioning benannten Stand des Projekts habe, ohne das manuell pflegen zu müssen.

## Akzeptanzkriterien

**Teil 1 — Tooling & Bootstrap**

- [ ] `frontend/package.json` (aktuell `0.0.0`) und `frontend/package-lock.json` werden einmalig auf `0.1.0` gebracht — synchron zu `backend/pyproject.toml` (bereits `0.1.0`).
- [ ] `release-please-config.json` (Repo-Root) und `.release-please-manifest.json` (Repo-Root, Bootstrap-Inhalt `{".": "0.1.0"}`) werden gemäß ADR 0008 angelegt (`release-type: "simple"`, `extra-files` für `backend/pyproject.toml` und `frontend/package.json`/`package-lock.json`, `bump-minor-pre-major: false`, `bump-patch-for-minor-pre-major: false`, `include-component-in-tag: false`).
- [ ] Neuer Workflow `.github/workflows/release-please.yml` (Trigger `push: branches: [main]`, `permissions: contents: write, pull-requests: write`) läuft additiv zu `ci.yml` — `ci.yml` selbst bleibt unverändert.
- [ ] Repo-Setting `allow_auto_merge` wird von `false` auf `true` gesetzt.
- [ ] Fine-grained PAT (`RELEASE_PLEASE_TOKEN`) wird erstellt (Scope: nur `TheRealKoller/photosort`, Permissions `Contents: Read & write`, `Pull requests: Read & write`, `Issues: Read & write`, `Metadata: Read`, mit Ablaufdatum) und als Repo-Secret hinterlegt. (`Issues: Read & write` bei der Umsetzung ergänzt — `release-please` verwaltet seine Zustands-Labels am Release-PR über den Issues-Label-Endpunkt, siehe ADR 0008, Abschnitt "Token/Berechtigungen".)
- [ ] Nach Merge dieser Umsetzung: Tag `v0.1.0` + GitHub-Release "v0.1.0" wird manuell auf den Merge-Commit gesetzt (Bootstrap-Anker, damit `release-please` nicht die gesamte bisherige Commit-Historie auswertet). Bestätigt mit Daniel: `v0.1.0` ist der Anker, der nächste automatisch erzeugte Release baut darauf auf (z.B. `v0.1.1`/`v0.2.0`), ist nicht selbst nochmal `v0.1.0`.
- [ ] `googleapis/release-please-action` wird auf einen konkreten Commit-SHA gepinnt (Kommentar mit der entsprechenden `v4.x.x`-Version), nicht auf den beweglichen Tag `v4`.

**Teil 2 — Laufendes Verhalten**

- [ ] Ein PR-Merge nach `main` mit mind. einem `feat:`/`fix:`/`BREAKING CHANGE`-Commit seit dem letzten Release führt dazu, dass `release-please` einen offenen Release-PR anlegt bzw. aktualisiert (korrekter SemVer-Bump, korrekt gruppierter Changelog-Eintrag).
- [ ] Ein PR-Merge nach `main`, der ausschließlich `docs:`/`chore:`/`test:`-Commits enthält, löst **keinen** neuen/aktualisierten Release-PR aus.
- [ ] Der offene Release-PR wird automatisch gemerged (GitHubs natives Auto-Merge), sobald `required_status_checks` (backend/frontend/docker-compose-check) grün sind und `required_conversation_resolution` erfüllt ist (keine offenen Konversationen) — ohne Klick von Daniel.
- [ ] Merge des Release-PRs erzeugt automatisch Git-Tag + GitHub-Release mit generiertem Changelog.
- [ ] Für Release-PRs wird bewusst **kein** Copilot-Review angefordert (dokumentierte Ausnahme von der sonstigen CLAUDE.md-Konvention, siehe ADR 0008/Security-Abschnitt).

**Teil 3 — Dokumentation**

- [ ] ADR [`decisions/0008-automated-semver-releases.md`](../decisions/0008-automated-semver-releases.md) — bereits angelegt, Status `Accepted`.
- [ ] `specs/architecture/0002-testkonzept.md` und `specs/architecture/0003-securitykonzept.md` enthalten die in dieser Spec beschriebenen Ergänzungen (siehe Teststrategie/Security unten).

## Datenmodell-Bezug

Keines — reine GitHub-Workflow-/Repo-Konfiguration, keine Berührung mit der PhotoSort-Datenbank oder Anwendungscode (außer den mechanischen Versions-Feldern in `pyproject.toml`/`package.json`).

## Architektur / Umsetzung

### Neue ADR

[`decisions/0008-automated-semver-releases.md`](../decisions/0008-automated-semver-releases.md) (Accepted) legt die technische Umsetzung des mit Daniel bereits geklärten Release-PR-Musters fest: Tooling, Datei-/Workflow-Struktur, Source of Truth für die Version, Token/Berechtigungen für den Self-Merge. Diese Spec setzt die ADR um, trifft selbst keine neuen Grundsatzentscheidungen.

### Tooling

`googleapis/release-please-action@<commit-sha> # v4.x.x` (gepinnt auf Commit-SHA, nicht auf den beweglichen Tag `v4`) als neue externe Abhängigkeit — implementiert das vorgegebene Release-PR-Muster produktionsreif (Conventional-Commit-Parsing, releasable/nicht-releasable Unterscheidung, Changelog-Grouping, Pre-1.0-Bump-Regeln). Details/Begründung siehe ADR 0008.

### Neue/geänderte Dateien

- **Neu:** `.github/workflows/release-please.yml` — additiv zu `ci.yml` (unverändert). Zwei Schritte: (1) `release-please-action` pflegt den Release-PR bzw. erzeugt bei dessen Merge Tag + GitHub-Release; (2) `gh pr merge --auto --squash` aktiviert Auto-Merge auf dem Release-PR.
- **Neu:** `release-please-config.json`, `.release-please-manifest.json` (Repo-Root) — siehe ADR 0008 für vollständigen Inhalt.
- **Neu (ab erstem automatischem Release):** `CHANGELOG.md` (Repo-Root), vom Tool generiert.
- **Geändert (einmalig, Bootstrap):** `frontend/package.json`/`package-lock.json` auf `0.1.0`. Danach werden beide Dateien **nicht mehr manuell** gepflegt.
- **Neues Repo-Secret:** `RELEASE_PLEASE_TOKEN` — siehe Akzeptanzkriterien/Security.
- **Neues Repo-Setting:** `allow_auto_merge: true`.

### Explizit unverändert

- `.github/workflows/ci.yml`, `docs/architecture.md`, `README.md` (kein lokales Setup-Bezug), keine Kopplung an Dockhand, kein Docker-Image-Tagging.

### Umsetzungsreihenfolge

1. `frontend/package.json`/`package-lock.json` auf `0.1.0` bringen.
2. `release-please-config.json` + `.release-please-manifest.json` anlegen.
3. Fine-grained PAT erstellen, als Repo-Secret `RELEASE_PLEASE_TOKEN` hinterlegen.
4. `.github/workflows/release-please.yml` anlegen (Action auf Commit-SHA gepinnt).
5. Repo-Setting `allow_auto_merge: true` setzen.
6. PR mergen; danach Tag `v0.1.0` + GitHub-Release "v0.1.0" manuell auf den Merge-Commit setzen.
7. Tag-Protection für `v*` ergänzen (siehe Security).
8. Verifikation empirisch nach dem ersten echten `feat:`/`fix:`-Merge nach main (siehe Teststrategie).

## UI/UX

Nicht relevant im engeren Sinn — reine CI/Tooling-Änderung, keine Berührung von `frontend/src/`, kein Bezug zum Design-System (`architecture/0004-design-system.md`). Bestätigt durch `ux-ui-designer`.

Im weiteren Sinn ist der von `release-please` gepflegte Release-PR sowie die generierte GitHub-Release-Seite die einzige "Oberfläche" dieses Features für Daniel als alleinigen Betrachter. Empfehlungen (Standardverhalten von `release-please`, keine Zusatzkonfiguration nötig):

- Changelog-Gruppierung nach Commit-Typ (`feat` → "Features", `fix` → "Bug Fixes") auf Englisch belassen, nicht individuell übersetzen — kein Mehrwert für einen technischen Alleinbetrachter, nur Pflegeaufwand.
- Standard-PR-Titel-Format des Release-PRs (`chore(main): release X.Y.Z`) beibehalten, damit er sich klar von Feature-PRs unterscheidet.
- Genau ein fortlaufend aktualisierter Release-PR statt mehrerer parallel offener — Standardverhalten, aber explizit als gewünscht in dieser Spec verankert.
- "BREAKING CHANGES"-Abschnitt im generierten Changelog optisch hervorgehoben belassen.
- Keine zusätzlichen Vorlagen/Emojis/Badges — reine Kosmetik ohne Nutzen hier.

## Security

**Sicherheitsrelevant:** Ja — neues Repo-Secret mit Schreibzugriff auf `main`, ein neuer automatisiert selbst-mergender Workflow-Akteur, eine bewusste Ausnahme von der Copilot-Review-Pflicht, öffentliches Repo.

**Bedrohungsmodell:**

- **Neues Asset:** `RELEASE_PLEASE_TOKEN` (fine-grained PAT unter Daniels eigenem Account, gescoped auf `TheRealKoller/photosort`, minimale Permissions, kein Admin). Ein Leak dieses Tokens ermöglicht faktisch dieselben Aktionen wie Daniels eigenes Push-Recht auf dieses eine Repo — aber ohne 2FA-Abfrage im Moment der Nutzung.
- **Fork-PRs (Repo ist public):** irrelevant, da `release-please.yml` ausschließlich auf `push: branches: [main]` triggert, nie auf `pull_request`/`pull_request_target` eines Forks. **Muss-Kriterium:** der Trigger darf nie auf `pull_request_target` erweitert werden, ohne dies neu zu bewerten.
- **Supply-Chain:** `googleapis/release-please-action` wird auf Commit-SHA gepinnt (nicht auf den beweglichen Tag `v4`), um das Risiko einer kompromittierten Upstream-Action zu reduzieren.
- **Kein neues Ziel gegenüber dem projektweiten Modell:** kein Schutz vor vollständiger Kompromittierung von Daniels eigenem GitHub-Account (2FA bleibt außerhalb des Scopes, wie in Spec 0007 festgehalten).

**Bezug zu ADR 0007:** `required_approving_review_count: 0` war laut ADR 0007 nur sicher, solange Daniel alleiniger Schreibzugriffs-Inhaber ist. Ein sich selbst mergender Release-Bot mit eigenem PAT erweitert den automatisierten Blast-Radius (ein Merge nach `main` kann jetzt ohne menschlichen Klick passieren), auch wenn der PAT formal unter Daniels eigenem Account läuft und kein neuer GitHub-Collaborator entsteht. Daniel wurde dies direkt vorgelegt und hat bestätigt, dass dies für seine eigene Automatisierung akzeptabel ist.

**Härtungsmaßnahmen (Teil der Umsetzung):**

1. Action auf Commit-SHA statt `@v4` gepinnt.
2. Trigger bleibt strikt `push: branches: [main]`, nie `pull_request_target`.
3. `permissions:` im Workflow explizit minimal (`contents: write`, `pull-requests: write`, kein `write-all`).
4. PAT-Rotation: bei Erstellung sofort ein GitHub-Issue mit dem Ablaufdatum als Erinnerungs-Anker anlegen — **mit Daniel bestätigt:** Ablaufdatum + Erinnerungs-Issue reicht als Rotationsprozess (pragmatisch für ein Solo-/Familienprojekt; Folgeschaden bei vergessener Rotation ist gering — Releases bleiben einfach aus, kein Sicherheitsvorfall). Eine GitHub-App-Migration ist erst zu revisitieren, falls das Projekt einen zweiten menschlichen Collaborator bekommt.
5. Tag-Protection für `v*`-Tags ergänzen (aktuell keine vorhanden) — verhindert versehentliches/böswilliges Überschreiben bestehender Release-Tags.
6. Keine zusätzliche Audit-Logik nötig — GitHub zeigt PAT-Merges weiterhin unter Daniels Account, `release-please` setzt eigene Label (`autorelease: pending`/`tagged`) am Release-PR.
7. Secret-Scanning/Push-Protection für dieses public Repo verifizieren (`gh api repos/TheRealKoller/photosort --jq .security_and_analysis`) — reine Verifikation, kein neuer Aufwand.

**Bewertung "kein Copilot-Review auf Release-PRs":** Akzeptabel, kein zusätzlich zu benennendes Restrisiko. Der Diff eines Release-PRs (Versionsfelder, Changelog) ist kein Ort, an dem ein Code-Review Injection-/Auth-Fehler finden würde, und `required_conversation_resolution: true` würde ein dauerhaft ungelöstes Copilot-Kommentar-Thread sonst zu einem echten Blocker der gewünschten Vollautomatisierung machen. Eng gefasste Ausnahme, nur für Release-PRs.

**Explizit dokumentiert (Konsequenz, kein Blocker):** aktuell keine Tag-Protection-Regeln vorhanden — wird als Umsetzungsschritt ergänzt (siehe Akzeptanzkriterien/Architektur).

`specs/architecture/0003-securitykonzept.md`, Sektion "GitHub-Repository-Zugriff" (aus ADR 0007), wird um den neuen PAT-Akteur ergänzt.

## Teststrategie

Reines CI-/Tooling-Feature ohne Anwendungscode — `pytest`/`vitest` und das Backend-Coverage-Gate sind **nicht anwendbar**. Verifikation folgt dem dreistufigen Muster aus Spec 0007 (`architecture/0002-testkonzept.md`), mit einer Abweichung bei Schritt 2 sowie zwei zusätzlichen Punkten.

**1. Config-Check (vorab, ohne `main` zu berühren):**

- `release-please-config.json` gegen das offizielle JSON-Schema validieren; `.release-please-manifest.json` auf korrekte Struktur/Konsistenz mit `pyproject.toml`/`package.json` prüfen.
- `release-please.yml` per Workflow-Linter (`actionlint`) prüfen; Diff verifizieren, dass `ci.yml` unverändert bleibt.
- `allow_auto_merge` vorher/nachher per `gh api` prüfen; Vorhandensein (nicht Inhalt) des Secrets `RELEASE_PLEASE_TOKEN` bestätigen.

**2. Funktionaler Nachweis — live am Hauptrepo (mit Daniel bestätigt):**

Anders als bei Spec 0007 lässt sich das Kernverhalten nicht an einem Wegwerf-Branch nachstellen, da `release-please.yml` ausschließlich auf `push: branches: [main]` triggert. Der reale erste Lauf ist Teil des Merges dieser Spec selbst — kein isoliertes Test-Repo/Fork wird vorab aufgesetzt (Aufwand steht in keinem Verhältnis zum Restrisiko bei einem Solo-Projekt ohne Release-SLA; die Config-Validierung in Schritt 1 fängt die meisten Fehlerklassen vorab ab):

- **Negativ-Probe:** Der Merge der Umsetzungs-PR selbst (Commit-Typ `chore:`/`ci:`) löst keinen Release-PR aus.
- **Positiv-Probe:** Der nächste ohnehin anfallende reguläre `feat:`/`fix:`-Merge — Release-PR entsteht, SemVer-Bump und Changelog sind korrekt.
- **Self-Merge vs. Branch Protection:** am selben ersten echten Release-PR beobachtet — bleibt er blockiert bei rotem CI/offener Konversation, mergt er sich nach Grün-/Auflösen selbst? `mergeable_state` per `gh api` vor/nach vergleichen (GitHubs eigene Einschätzung statt Selbstbericht).

**3. Bootstrap-Verifikation:** Tag `v0.1.0` + GitHub-Release nach Merge gesetzt; Versions-Sync in `pyproject.toml`/`package.json`/`package-lock.json` geprüft; der erste automatisch erzeugte Release baut auf `v0.1.0` auf (nicht erneut `v0.1.0`, nicht aus der gesamten Repo-Historie hochgerechnet).

**4. Dokumentations-Review:** ADR 0008, diese Spec, Testkonzept-/Securitykonzept-Ergänzungen vollständig und konsistent.

**5. Rollback-/Fehlerfall:** Kein automatisierter Alarm für falschen Versions-Bump oder hängenden Auto-Merge — bewusste, dokumentierte Lücke für ein Solo-Projekt ohne Release-SLA; Erkennung bleibt manueller Blick ins Repo (Daniel erhält ohnehin GitHub-Notifications für neue PRs). Ad-hoc-Korrektur (Tag löschen/neu setzen, Release-Notes editieren) statt eigenes Rollback-Tooling.

`specs/architecture/0002-testkonzept.md` wurde um einen Absatz ergänzt: das 3-Stufen-Muster aus Spec 0007 gilt nicht uneingeschränkt, sobald der zu prüfende Workflow selbst nur auf `push: branches: [main]` triggert (kein Wegwerf-Branch möglich) — Ersatzmuster: realer erster Lauf als Negativ-/Positiv-Probe plus verschärfte Vorab-Config-Validierung. Ergänzt außerdem unter "Bekannte Lücken": fehlendes Monitoring für hängende Release-Auto-Merges/fehlerhafte Versions-Bumps.

## Offene Fragen

Keine mehr — beide im Schärfungsprozess aufgeworfenen Rückfragen wurden mit Daniel geklärt:

1. Verifikationsansatz für den ersten Release-Zyklus: live am Hauptrepo beobachten (kein isoliertes Test-Repo).
2. PAT-Rotationsprozess: Ablaufdatum + Erinnerungs-Issue genügt.

Die Interpretation "Startversion v0.1.0 = Bootstrap-Anker, ab dem automatisch weitergezählt wird" (nicht: der erste automatische Release heißt selbst `v0.1.0`) ist im Bootstrap-Abschnitt der Akzeptanzkriterien festgehalten.

## Out of Scope

- Implementierung/Anbindung des externen Deploy-Tools "Dockhand" (separate, künftige Spec, außerhalb dieses Repos) — keine Kopplung.
- Docker-Image-Tagging.
- Getrennte Versionierung von Backend und Frontend.
- Migration von PAT zu einer GitHub App (erst zu revisitieren, falls ein zweiter menschlicher Collaborator hinzukommt).
- Isoliertes Test-Repo/Fork-Setup zur Vorab-Erprobung (siehe Teststrategie — bewusst nicht gewählt).
- Automatisierter Alarm/Monitoring für hängende Auto-Merges oder fehlerhafte Versions-Bumps.
- Rückwirkende Release-Erstellung für die bisherige Commit-Historie (Specs 0001–0007) — Versionierung beginnt bei `v0.1.0` als Bootstrap-Anker.
