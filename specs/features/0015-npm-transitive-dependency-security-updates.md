# 0015 - npm-Sicherheitsupdates für transitive Dependencies (fast-uri, undici)

**Status:** Implemented ([PR #22](https://github.com/TheRealKoller/photosort/pull/22))
**Erstellt:** 2026-08-04
**Akzeptiert:** 2026-08-04
**Implementiert:** 2026-08-04
**Bezug:** Ausgelöst durch 6 offene Dependabot-Alerts (`state: open`) in `frontend/package-lock.json` — kein Chat-Wunsch von Daniel, sondern automatisierter Dependabot-Scan des Repos. Analog zu Spec 0011/0014: rein mechanischer, automatisiert entdeckter Security-Fix ohne Produktentscheidung, direkt akzeptiert ohne vollen idea-sharpener-Zyklus.

## Ziel

Sechs offene Dependabot-Alerts für zwei transitive npm-Dependencies in `frontend/package-lock.json` schließen:

| Alert(s) | Paket | Severity | Advisory | Behoben ab |
|---|---|---|---|---|
| #4 | `fast-uri` | high | [GHSA-7p8r-x3mc-p8w7](https://github.com/TheRealKoller/photosort/security/dependabot/4) — Host-Confusion via Backslash-Authority-Introducer | `3.1.5` |
| #5 | `undici` | high | [GHSA-4cwx-7wf7-3272](https://github.com/TheRealKoller/photosort/security/dependabot/5) — Cross-User-Info-Disclosure/Parse-Crash via Cache-Control-Direktiven | `7.29.0` |
| #6 | `undici` | medium | [GHSA-8xcm-r25x-g524](https://github.com/TheRealKoller/photosort/security/dependabot/6) — Response-Desync via Retry-Interceptor | `7.29.0` |
| #7 | `undici` | medium | [GHSA-v3r7-h72x-cjcm](https://github.com/TheRealKoller/photosort/security/dependabot/7) — Cookie-Attribut-Injection via `setCookie()` | `7.29.0` |
| #8 | `undici` | medium | [GHSA-jr45-8vmc-qm54](https://github.com/TheRealKoller/photosort/security/dependabot/8) — Cross-User-Info-Disclosure via Whitespace in Cache-Control | `7.29.0` |
| #9 | `undici` | medium | [GHSA-m8rv-5g2x-5cg5](https://github.com/TheRealKoller/photosort/security/dependabot/9) — CRLF-Injection via Blob-Body `type`-Property | `7.29.0` |

Dependabot hat bereits einen eigenen PR mit der passenden Lockfile-Aktualisierung geöffnet: [PR #22](https://github.com/TheRealKoller/photosort/pull/22) (`chore(deps): bump the npm_and_yarn group across 1 directory with 2 updates`, `fast-uri` 3.1.4→3.1.5, `undici` 7.28.0→7.29.0), CI bereits grün. Ziel dieser Spec ist, diesen PR um die Dokumentationspflicht (Sicherheitskonzept) zu ergänzen und regulär zu mergen statt ihn nur durchzuwinken.

## User Story

Als Repo-Betreiber möchte ich, dass keine offenen Dependabot-Alerts mit `severity: high` (oder in Häufung `medium`) unadressiert im Repository stehen bleiben, damit die Dependency-Hygiene nachvollziehbar sauber bleibt und ein späteres, tatsächlich relevantes Advisory nicht in der Alert-Liste untergeht.

## Akzeptanzkriterien

- [x] `frontend/package-lock.json` löst `fast-uri` auf `3.1.5` (oder neuer) und `undici` auf `7.29.0` (oder neuer) auf — via PR #22 oder äquivalentem `npm update`/`npm install` in `frontend/`, kein manueller Lockfile-Edit.
- [x] `frontend/package.json` unverändert — beide Pakete sind transitive Dependencies (siehe Architektur/Umsetzung), keine direkten Einträge dort.
- [x] `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` im `frontend/`-Verzeichnis laufen nach dem Update unverändert erfolgreich durch.
- [ ] Nach Merge nach `main` (nächster Dependabot-Scan) sind Alerts #4–#9 im Status `fixed`/`dismissed` — verifizierbar via `gh api repos/{owner}/{repo}/dependabot/alerts/{4..9}` (Feld `state`). **Steht noch aus** — manueller Post-Merge-Schritt, nicht Teil dieser Umsetzung (siehe Auftrag).
- [x] `specs/architecture/0003-securitykonzept.md` erhält nach Umsetzung einen kurzen, datierten Vermerk analog zum bestehenden Muster (siehe Security-Abschnitt).

## Datenmodell-Bezug

Keines. Reine Frontend-Dependency-Aktualisierung (Dev-/Build-Toolchain), kein Datenmodell betroffen.

## Architektur / Umsetzung

**Verifizierter Sachverhalt (2026-08-04, Stand vor dem Update — siehe "Update bei Umsetzung" unten für den implementierten Zielzustand):**

- `npm ls fast-uri undici` im Verzeichnis `frontend/` zeigt beide Pakete als rein transitiv:
  - `undici@7.28.0` ← `jsdom@29.1.1` (Vitest-Testumgebung, ausschließlich zur Testlaufzeit, nicht im ausgelieferten Bundle).
  - `fast-uri@3.1.4` ← `vite-plugin-pwa@1.3.0` → `workbox-build@7.4.1` → `ajv@8.20.0` (Build-Zeit-Tool zur Service-Worker-Generierung, nicht im Browser-Runtime-Code).
- Beide Pakete tauchen nicht in `frontend/package.json` auf — kein direkter Versions-Constraint anzupassen, das Update läuft ausschließlich über die Lockfile-Neuauflösung ihrer jeweiligen Elternpakete.
- Dependabot hat die passende Lockfile-Änderung bereits als PR #22 vorbereitet (`npm_and_yarn`-Group-Update), CI (`backend`, `frontend`, `demo-scripts`, `docker-compose-check`, CodeQL, GitGuardian) bereits grün zum Zeitpunkt der Spec-Erstellung.

**Update bei Umsetzung (2026-08-04):** PR #22 wie geplant als Basis übernommen (Branch `dependabot/npm_and_yarn/frontend/npm_and_yarn-294b92ad74` ausgecheckt, Doku-Commits auf diesem Branch ergänzt). `frontend/package-lock.json` löst auf diesem Branch bereits `undici@7.29.0` (weiterhin ausschließlich über `jsdom`) und `fast-uri@3.1.5` (weiterhin ausschließlich über `vite-plugin-pwa`→`workbox-build`→`ajv`) auf — die transitive Abhängigkeitskette selbst ist unverändert, nur die Versionen wurden auf die gefixten Stände gehoben. `frontend/package.json` bleibt unverändert. Merge nach `main` folgt nach Abschluss dieses Reviews.

**Vorgehen:** PR #22 als Basis übernehmen (Branch auschecken oder Änderung äquivalent nachvollziehen), um den nach Umsetzung fälligen Sicherheitskonzept-Vermerk (siehe Security-Abschnitt) ergänzen, dann reguläre CI-Prüfung + Merge — analog zum Vorgehen bei Spec 0014 (dort war der Dependency-Bump bereits anderweitig gelandet, hier liegt er als eigener Dependabot-PR vor).

**Betroffene Dateien:** `frontend/package-lock.json` (durch PR #22 bzw. äquivalentes `npm update`), `specs/architecture/0003-securitykonzept.md` (neuer Vermerk), keine Anwendungscode-Änderung.

**ADR:** Keine neue ADR — reine technische Detailentscheidung ohne neue Technologie, ohne Datenmodell-Bezug, kein Wechsel der externen Abhängigkeiten selbst (bleiben transitiv, nur Patch-Versionen), analog zu Spec 0011/0014.

**Nicht betroffen:** `specs/architecture/0001-overview.md`, `README.md`.

## UI/UX

Nicht relevant. Reine Dependency-Versionsänderung an Dev-/Build-Toolchain-Paketen ohne jede Laufzeit-Berührung des ausgelieferten Frontends.

## Security

**Bedrohung laut Advisories:** Alle sechs Advisories betreffen HTTP-Client-/URI-Parsing-Verhalten von `undici` bzw. `fast-uri` — CRLF-Injection, Cookie-Attribut-Injection, Cache-Control-Parsing-Fehler mit Cross-User-Info-Disclosure, Response-Desynchronisation, Host-Confusion. Alle sind für Szenarien relevant, in denen das jeweilige Paket **zur Laufzeit** echte, potenziell von außen beeinflusste HTTP-Requests/-Responses verarbeitet (z.B. als HTTP-Client oder in einem Cache/Proxy-Pfad).

**Verifiziert, nicht exploitbar in PhotoSort:** Weder `undici` noch `fast-uri` werden im ausgelieferten Frontend-Code ausgeführt:
- `undici` kommt ausschließlich über `jsdom` (Vitest-Testumgebung) — läuft nur während `npm run test` in der CI/lokal, nie im Browser der Nutzer, verarbeitet nie echte Netzwerk-Requests von Dritten.
- `fast-uri` kommt ausschließlich über `vite-plugin-pwa`/`workbox-build`/`ajv` — läuft nur während `npm run build` zur Generierung des Service-Workers, nicht als Laufzeit-Code im Browser.

Beide Advisory-Klassen setzen eine Laufzeit-Nutzung als aktiver HTTP-Client/-Parser voraus, die in PhotoSort für diese beiden Pakete nicht vorliegt — die Schwachstellen sind für dieses Repo damit **nicht exploitbar**, unabhängig vom Update.

**Warum trotzdem updaten:** Reine Hygienemaßnahme, analog zu Spec 0011/0014 — offene `high`/`medium`-Alerts sind unabhängig von der tatsächlichen Exploitierbarkeit unerwünschtes Rauschen und die Updates sind risikolose Patch-Bumps ohne Breaking Changes (Dependabot-PR bereits mit grüner CI).

**Sicherheitskonzept:** `specs/architecture/0003-securitykonzept.md` wird **nach Umsetzung** um einen kurzen, datierten Vermerk im Abschnitt "Angriffsflächen" → "Frontend" ergänzt, analog zum bestehenden Muster bei Spec 0011/0012/0014 — mit dem Kernbefund, dass beide Pakete reine Dev-/Build-Zeit-Dependencies ohne Laufzeit-Exposition im Browser sind.

## Teststrategie

- **Erster Schritt bei Umsetzung:** Zustand von PR #22 erneut prüfen (CI-Status, ob zwischenzeitlich neue Commits/Konflikte hinzugekommen sind) — dann als Basis übernehmen statt eigenständig neu aufzulösen.
- **Config-Ebene:** Diff-Review von `frontend/package-lock.json` — erwartungsgemäß nur `fast-uri`- und `undici`-Einträge (Version, `resolved`, `integrity`) sowie ggf. rein interne Abhängigkeitsverschiebungen dieser beiden Pakete, kein `package.json`-Diff.
- **Funktionaler Nachweis:** Bestehende Test-Suite (`npm run test`, Vitest — nutzt `jsdom`/`undici` selbst zur Testlaufzeit) muss unverändert grün bleiben. `npm run lint`, `npm run typecheck` und `npm run build` (nutzt `vite-plugin-pwa`/`fast-uri` zur Build-Zeit) müssen ebenfalls unverändert erfolgreich durchlaufen.
- **CI:** Der PR durchläuft die bestehenden CI-Jobs — ein grüner Lauf ist der vollständige funktionale Beweis, analog zu Spec 0011/0014.
- **Dependabot-Verifikation:** nach Merge per `gh api repos/{owner}/{repo}/dependabot/alerts/{4..9}` prüfen, dass `state` auf `fixed`/`dismissed` wechselt — einmaliger manueller Nachvollzug, kein automatisierter CI-Test.
- **`specs/architecture/0002-testkonzept.md`:** keine Ergänzung nötig — passt ins bestehende Muster "reine Dependency-/Konfigurationsaktualisierung ohne neues Testmuster", analog zu Spec 0011/0014.

## Out of Scope

- Dependabot-Alerts #1–#3 (`brace-expansion`, `state: auto_dismissed`) — bereits in Spec 0011 explizit als Out of Scope vermerkt, bleiben es hier ebenfalls.
- Einführung von automatisiertem Dependency-Scanning/Auto-Merge in CI — bereits in `specs/architecture/0003-securitykonzept.md` unter "Bekannte Lücken" als offener, separater Punkt geführt.
- Aktualisierung weiterer Frontend-Abhängigkeiten über `fast-uri`/`undici` hinaus, auch wenn `npm outdated` ggf. weitere veraltete Pakete zeigt — diese Spec ist bewusst auf die sechs konkreten Dependabot-Alerts beschränkt.
- Entfernung oder Ersatz von `vite-plugin-pwa`/`jsdom` selbst — beide bleiben unverändert im Einsatz, nur ihre transitive Dependency wird gepatcht.

## Entscheidungen

- Kein Edit an `frontend/package.json` — beide Pakete sind rein transitiv, verifiziert per `npm ls` (2026-08-04).
- Bestehenden Dependabot-PR #22 als Basis übernehmen statt eigenständig neu aufzulösen — spart eine bereits erledigte, identische Arbeit.
- Keine neue ADR — reine technische Detailentscheidung analog zu Spec 0011/0014.
- `specs/architecture/0003-securitykonzept.md` wird erst nach Umsetzung im Security-Review aktualisiert, nicht bereits beim Spec-Erstellen (analog zu Spec 0011/0014).
- Direkt `Accepted` statt vollem idea-sharpener-Zyklus, da rein mechanischer, automatisiert entdeckter Security-Fix ohne Produktentscheidung — keine Rückfrage an Daniel nötig (analog zu Spec 0011/0014).
