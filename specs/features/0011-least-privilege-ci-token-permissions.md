# 0011 - Least-Privilege GITHUB_TOKEN-Berechtigungen in ci.yml

**Status:** Accepted
**Erstellt:** 2026-08-02
**Akzeptiert:** 2026-08-02
**Bezug:** Ausgelöst durch 3 offene CodeQL-Findings (Rule `actions/missing-workflow-permissions`, `security_severity_level: medium`, Tags `security`/`maintainability`, CWE-275) — kein Chat-Wunsch von Daniel, sondern automatisierter Security-Scan des Repos. Idea-Sharpening-Gespräch mit Daniel im Chat, 2026-08-02.

## Ziel

`.github/workflows/ci.yml` setzt aktuell in keinem der vier Jobs (`backend`, `frontend`, `demo-scripts`, `docker-compose-check`) ein explizites `permissions:`-Block für den `GITHUB_TOKEN`. Der Token erbt dadurch die repository-weite Default-Berechtigung, die potenziell breiter ist als für einen reinen Lint/Test/Build-Workflow nötig. Ziel ist, für alle vier Jobs least-privilege durchzusetzen, damit ein kompromittierter Workflow-Schritt (z.B. über eine bösartige transitive npm-/pip-Dependency) nicht mehr Repo-Rechte hat als zwingend erforderlich.

**Korrektur nach Umsetzung (2026-08-02, Review durch test-engineer/architect/requirements-engineer):** Diese Spec sprach ursprünglich durchgehend von "drei Jobs" (`backend`, `frontend`, `docker-compose-check`) und ließ den bereits seit Spec 0009 existierenden vierten Job `demo-scripts` unerwähnt — eine Ungenauigkeit im Spec-Text selbst, nicht im umgesetzten Code. Der gewählte Top-Level-`permissions:`-Block deckt `demo-scripts` automatisch mit ab (das war auch vorher schon so, nur nicht explizit benannt); an der Umsetzung ändert sich dadurch nichts. Die Zählung wurde in diesem Dokument nachträglich auf vier Jobs korrigiert.

## User Story

Als Repo-Betreiber möchte ich, dass der `GITHUB_TOKEN` in `ci.yml` nur die minimal nötigen Berechtigungen (`contents: read`) besitzt, damit ein kompromittiertes CI-Skript keinen Schreibzugriff auf das Repository erlangen kann.

## Akzeptanzkriterien

- [x] `.github/workflows/ci.yml` enthält direkt unter `on:` genau einen Block `permissions:\n  contents: read`, ohne job-spezifische `permissions:`-Blöcke in `backend`, `frontend`, `demo-scripts` oder `docker-compose-check`.
- [ ] Nach dem Merge nach `main` (nächster automatischer CodeQL-Scan der Kategorie `/language:actions`, ausgelöst durch `push`) sind die drei Alerts #1, #2, #3 (`actions/missing-workflow-permissions`, `.github/workflows/ci.yml`) im Status `fixed`/`closed` — verifizierbar via `gh api repos/{owner}/{repo}/code-scanning/alerts/{1,2,3}` (Feld `state`).
- [x] Alle vier Jobs (`backend`, `frontend`, `demo-scripts`, `docker-compose-check`) laufen nach der Änderung unverändert erfolgreich durch (`checkout`, Dependency-Install, Lint, Typecheck, Test, Build/`docker compose config -q`) — kein Job scheitert an einem Permissions-Fehler.
- [ ] Kein Job in `ci.yml` führt einen Schritt aus, der mehr als Lesezugriff auf den Checkout benötigt (kein Push, kein PR-Kommentar, kein Release, kein Package-Publish).

## Datenmodell-Bezug

Keines. Reine CI-Konfigurationshärtung, kein Anwendungscode, kein Datenmodell betroffen.

## Architektur / Umsetzung

**Ansatz:** `.github/workflows/ci.yml` erhält einen einzigen Top-Level-`permissions:`-Block direkt unter `on:`, gültig für alle vier Jobs:

```yaml
permissions:
  contents: read
```

Ein einziger Top-Level-Block statt pro-Job-Blöcken, weil alle vier Jobs identische, minimale Bedürfnisse haben (nur Checkout-Lesezugriff, kein Push/PR-Kommentar/Release) — ein Block ist einfacher und dokumentiert die einheitliche Policy an einer Stelle, ohne Duplikation. Das setzt den `GITHUB_TOKEN` für `backend`, `frontend`, `demo-scripts` und `docker-compose-check` einheitlich auf Lesezugriff und behebt alle drei CodeQL-Findings in einer Änderung.

**Betroffene Dateien:** ausschließlich `.github/workflows/ci.yml`, ein zusätzlicher Top-Level-Block, keine Job-Änderungen.

**Kompatibilität mit Spec 0008 (`release-please.yml`):** Kein Konflikt. `release-please.yml` ist ein separater, eigener, künftiger Workflow mit eigenem, für seinen Zweck passenden `permissions:`-Block (`contents: write`, `pull-requests: write`) — Workflow-Permissions gelten nur innerhalb der jeweiligen Workflow-Datei, keine Überschneidung. Spec 0008s "`ci.yml` selbst bleibt unverändert" bezog sich nur darauf, keine Release-Please-Logik in `ci.yml` zu mischen, nicht auf ein generelles Änderungsverbot.

**ADR:** Keine neue ADR — reine technische Detailentscheidung ohne neue Technologie, ohne Datenmodell-Bezug, ohne externe Abhängigkeit, analog zu Spec 0010. Verwandt, aber kein Auslöser: ADR 0007 (GitHub-Repo-Zugriffshärtung) behandelt die Issue-Freigabe-Policy und Branch-Protection-Baseline, nicht den CI-Workflow-Token — kein Widerspruch.

**Nicht betroffen:** `specs/architecture/0001-overview.md` (keine Systemarchitektur-Änderung) und `README.md` (kein neuer lokaler Setup-Schritt).

## UI/UX

Nicht relevant. Reine CI-Konfigurationsänderung ohne Berührung von Anwendungscode, Frontend oder Nutzerinteraktion.

## Security

**Bedrohung:** `.github/workflows/ci.yml` setzt aktuell in keinem der vier Jobs einen expliziten `permissions:`-Block. Der `GITHUB_TOKEN` erbt dadurch die repository-weite Default-Berechtigung, die potenziell breiter ist als nötig (CodeQL-Finding `actions/missing-workflow-permissions`, CWE-275, medium). Ein kompromittiertes transitives npm-/pip-Paket, das während `npm ci`/`uv pip install` oder eines Test-/Lint-Laufs Code ausführt, könnte den Token sonst missbrauchen, um z.B. Commits zu pushen, Issues/PRs zu manipulieren oder Packages zu veröffentlichen — bei einem öffentlichen Repo ein reales Supply-Chain-Risiko.

**Gegenmaßnahme:** Ein einziger Top-Level-`permissions:`-Block mit `contents: read`, gültig für alle vier Jobs. Nicht aufgeführte Scopes (`issues`, `pull-requests`, `packages`, …) fallen laut GitHub-Actions-Semantik automatisch auf `none` — ein redundantes explizites `none`-Listing ist nicht nötig, `contents: read` allein ist ausreichend für alle vier Jobs' Bedürfnisse (nur `actions/checkout`).

**Sicherheitskonzept:** `specs/architecture/0003-securitykonzept.md`, Sektion "GitHub-Repository-Zugriff", wird **nach Umsetzung** (nicht bereits jetzt beim Spec-Sharpening) im Security-Review um einen kurzen, datierten Absatz ergänzt — analog zur bestehenden Baseline aus ADR 0007, und beantwortet damit auch den dort bereits als offen vermerkten Prüfpunkt zu `default_workflow_permissions` (Vorausschau Spec 0008, Zeile 78). Kein Widerspruch zu ADR 0007 (Branch Protection/Collaborators) — andere Ebene (Workflow-Token statt Repo-Zugriff).

## Teststrategie

- **Config-Ebene:** Diff-Review der wenigen Zeilen in `ci.yml` — reine YAML-Änderung, kein Anwendungscode, kein `pytest`/`vitest` nötig.
- **Funktionaler Nachweis:** Der PR selbst, der die Änderung einführt, durchläuft alle vier CI-Jobs mit den neuen `permissions:` (der PR-Workflow läuft bereits mit der geänderten Datei, kein Wegwerf-Branch nötig wie bei Spec 0007, da `ci.yml` auf `pull_request` triggert). Ein grüner CI-Lauf ist hier der vollständige Beweis: `contents: read` ist entweder ausreichend (alle vier Jobs laufen durch) oder nicht (ein Job schlägt mit einem expliziten Permissions-Fehler fehl) — kein stiller Fehlerzustand dazwischen.
- **CodeQL-Verifikation:** nach Merge per `gh api .../code-scanning/alerts/{1,2,3}` prüfen, dass `state` auf `fixed`/`closed` wechselt — einmaliger manueller Nachvollzug, kein automatisierter CI-Test.
- **Edge Case (kein Risiko, sondern gewünschter Effekt):** Ein künftiger Step, der mehr Rechte braucht (z.B. ein PR-Kommentar-Schritt), schlägt mit explizitem Permissions-Fehler fehl statt still falsch zu funktionieren — das ist der gewünschte Fail-Fast-Effekt von least-privilege.
- **`specs/architecture/0002-testkonzept.md`:** keine Ergänzung nötig — passt ins bestehende Muster "Repo-Konfiguration & Dokumentation (kein Anwendungscode)" aus Spec 0007, die Änderung ist zu mechanisch (wenige Zeilen YAML) für ein neues Verifikationsmuster.

## Out of Scope

- Der Dependabot-Alert zu `brace-expansion` (transitive npm-Dev-Dependency, high severity) — Status `auto_dismissed`, aktuell nicht actionable, kein Teil dieser Spec.
- Ein eigener `permissions:`-Block für den künftigen `release-please.yml`-Workflow (Spec 0008) — bereits dort geplant, separater Workflow.
- Änderung der repository-weiten Default-Workflow-Permissions in den GitHub-Einstellungen selbst (`Settings → Actions → General`) — diese Spec härtet `ci.yml` explizit, unabhängig vom Repo-Default; eine Änderung des Defaults wäre eine eigene, künftige Entscheidung.

## Entscheidungen

- Ein einziger Top-Level-`permissions:`-Block statt pro-Job-Blöcken, da alle vier Jobs identische minimale Bedürfnisse haben (architect-Konsultation, 2026-08-02).
- Keine neue ADR — reine technische Detailentscheidung analog zu Spec 0010 (architect-Konsultation, 2026-08-02).
- `specs/architecture/0003-securitykonzept.md` wird erst nach Umsetzung im Security-Review aktualisiert, nicht bereits beim Spec-Sharpening (security-engineer-Konsultation, 2026-08-02).
