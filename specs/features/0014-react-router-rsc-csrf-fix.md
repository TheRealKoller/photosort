# 0014 - react-router-Update (Dependabot-Alert #2: RSC-Mode-CSRF)

**Status:** Implemented
**Erstellt:** 2026-08-03
**Akzeptiert:** 2026-08-03
**Implementiert:** 2026-08-04, PR [#24](https://github.com/TheRealKoller/photosort/pull/24)
**Bezug:** Ausgelöst durch offenen Dependabot-Alert [#2](https://github.com/TheRealKoller/photosort/security/dependabot/2) (`state: open`, severity high, GHSA-qwww-vcr4-c8h2, kein CVE vergeben) für `react-router` in `frontend/package-lock.json` — kein Chat-Wunsch von Daniel, sondern automatisierter Dependabot-Scan des Repos. Analog zu Spec 0011 (least-privilege CI-Token-Permissions): rein mechanischer, technischer Dependency-Fix ohne Produktentscheidung, direkt akzeptiert ohne vollen idea-sharpener-Zyklus.

## Ziel

`frontend/package.json` deklariert `"react-router": "^8.2.0"`, `frontend/package-lock.json` hat davon Version `8.2.0` aufgelöst und installiert. Die Versionsspanne `>= 7.12.0, < 8.3.0` von `react-router` ist laut Advisory GHSA-qwww-vcr4-c8h2 von einer CSRF-Schwachstelle in den *unstable RSC (React Server Components)*-Codepfaden betroffen ("RSC Mode CSRF Bypass Allows Action Execution Before 400 Response"), behoben ab `8.3.0`. Ziel ist, den Dependabot-Alert durch ein Update auf `react-router@8.3.0` zu schließen — als Hygienemaßnahme, nicht weil die konkrete Schwachstelle in PhotoSort aktuell ausnutzbar wäre (siehe Security-Abschnitt).

## User Story

Als Repo-Betreiber möchte ich, dass keine offenen Dependabot-Alerts mit `severity: high` unadressiert im Repository stehen bleiben, damit die Dependency-Hygiene des Projekts nachvollziehbar sauber ist und ein späteres, tatsächlich relevantes Advisory nicht in der Alert-Liste untergeht.

## Akzeptanzkriterien

- [x] `frontend/package-lock.json` löst `react-router` auf Version `8.3.0` (oder neuer, innerhalb `^8.2.0`) auf — Update via `npm update react-router` bzw. `npm install` im Verzeichnis `frontend/`, **kein** manueller Edit der Lockfile-Hashes. **Erfüllt, aber ohne Verdienst des Feature-Branches:** bei erneuter Verifikation zu Umsetzungsbeginn (2026-08-04) bereits auf `8.3.0` — siehe "Update bei Umsetzung" in Architektur/Umsetzung.
- [x] `frontend/package.json` bleibt unverändert bei `"react-router": "^8.2.0"` (siehe Architektur/Umsetzung — die Caret-Range deckt `8.3.0` bereits ab, ein Bump der deklarierten Range ist nicht nötig), **es sei denn**, die Verifikation zum Zeitpunkt der Umsetzung ergibt ein abweichendes Bild (siehe Teststrategie, erster Schritt). Verifikation ergab kein abweichendes Bild bei `package.json` selbst — unverändert bei `^8.2.0`.
- [x] `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` laufen im `frontend/`-Verzeichnis nach dem Update unverändert erfolgreich durch (reines Patch-Level-Verhalten für unsere Nutzung, siehe Security-Abschnitt). Verifiziert am 2026-08-04, alle vier grün (200/200 Tests).
- [ ] Nach Merge nach `main` (nächster Dependabot-Scan) ist Alert [#2](https://github.com/TheRealKoller/photosort/security/dependabot/2) im Status `fixed`/`dismissed` — verifizierbar via `gh api repos/{owner}/{repo}/dependabot/alerts/2` (Feld `state`). **Bewusst offen gelassen:** Post-Merge-Schritt, nicht Teil von PR #24 (siehe Teststrategie).
- [x] `specs/architecture/0003-securitykonzept.md` erhält nach Umsetzung einen kurzen, datierten Vermerk analog zum bestehenden Muster (siehe Security-Abschnitt unten).

## Datenmodell-Bezug

Keines. Reine Frontend-Dependency-Aktualisierung, kein Datenmodell betroffen.

## Architektur / Umsetzung

**Verifizierter Sachverhalt (2026-08-03):**

- `frontend/package.json`, Zeile 18: `"react-router": "^8.2.0"`. Die Caret-Range `^8.2.0` erlaubt laut Semver-Semantik `>=8.2.0 <9.0.0` — `8.3.0` liegt bereits innerhalb dieser Range.
- `npm outdated react-router` im Verzeichnis `frontend/` bestätigt: `Current: 8.2.0`, `Wanted: 8.3.0`, `Latest: 8.3.0`. "Wanted" ist die von npm berechnete höchste Version, die die in `package.json` deklarierte Range noch erlaubt — `8.3.0` ist danach bereits ohne jede `package.json`-Änderung erreichbar.
- `npm view react-router versions --json` listet `8.3.0` als existierende, veröffentlichte Version (letzte in der Liste nach `8.2.0`).
- **Folgerung:** `frontend/package.json` muss **nicht** geändert werden. Es genügt, `frontend/package-lock.json` neu aufzulösen (`npm update react-router` oder `npm install` im `frontend/`-Verzeichnis), damit die dort gepinnte Version und der `integrity`-Hash von `8.2.0` auf `8.3.0` wechseln (aktuell `package-lock.json` Zeile ~6060: `resolved: .../react-router-8.2.0.tgz`).

**Update bei Umsetzung (2026-08-04):** Die erneute Verifikation zu Beginn der Umsetzung (siehe Teststrategie, erster Schritt) ergab ein abweichendes Bild gegenüber dem oben verifizierten Sachverhalt vom 2026-08-03: `frontend/package-lock.json` löste `react-router` zu diesem Zeitpunkt **bereits** auf `8.3.0` auf, `integrity`-Hash gegen die npm-Registry verifiziert. Ursache: Commit `2a615ef` ("feat: Tailwind CSS + Radix UI + shadcn/ui foundation for visual redesign", Feature-Branch von Spec 0012) führte rund eine Minute nach Akzeptanz dieser Spec ein `npm install` aus, das die gesamte Lockfile neu auflöste und dabei — als reiner Nebeneffekt, unabhängig von Spec 0014 — auch `react-router` auf die laut `package.json`-Range bereits erreichbare `8.3.0` hob. Die **betroffenen Dateien dieses Feature-Branches (`feature/0014-react-router-rsc-csrf-fix`) sind damit ausschließlich `specs/architecture/0003-securitykonzept.md`** (Verifikations-Vermerk) sowie diese Spec-Datei und `specs/roadmap.md` (Status-Pflege) — kein `frontend/package-lock.json`-Diff, kein `frontend/package.json`-Diff, kein Anwendungscode. Die ursprüngliche Umsetzungsplanung oben bleibt als Dokumentation des zum Akzeptanz-Zeitpunkt korrekten Plans stehen; sie wurde durch den tatsächlichen, unabhängig eingetretenen Verlauf überholt, nicht durch einen Fehler in der Planung selbst.

**Betroffene Dateien:** ausschließlich `frontend/package-lock.json` (neu aufgelöst durch `npm update`/`npm install`), keine Änderung an `frontend/package.json`, keine Anwendungscode-Änderung.

**ADR:** Keine neue ADR — reine technische Detailentscheidung ohne neue Technologie, ohne Datenmodell-Bezug, kein Wechsel der externen Abhängigkeit selbst (bleibt `react-router`, nur Patch-Version), analog zu Spec 0010/0011.

**Nicht betroffen:** `specs/architecture/0001-overview.md` (keine Systemarchitektur-Änderung), `README.md` (kein neuer lokaler Setup-Schritt).

## UI/UX

Nicht relevant. Reine Dependency-Versionsänderung ohne funktionale oder visuelle Auswirkung auf Nutzerinteraktion — `react-router` wird im Projekt ausschließlich client-seitig als `<BrowserRouter>` mit `<Routes>`/`<Route>` genutzt (siehe `frontend/src/main.tsx`, `frontend/src/App.tsx`), kein Verhaltensunterschied zwischen 8.2.0 und 8.3.0 für diesen Nutzungsstil zu erwarten (reiner Sicherheits-Patch in einem ungenutzten Codepfad, siehe unten).

## Security

**Bedrohung laut Advisory (GHSA-qwww-vcr4-c8h2):** In `react-router`-Versionen `>= 7.12.0, < 8.3.0` kann in den *unstable RSC (React Server Components)*-Codepfaden eine CSRF-Anfrage eine Server-Action ausführen, bevor die eigentlich vorgesehene 400-Antwort (Ablehnung wegen fehlendem/falschem CSRF-Schutz) zurückgegeben wird — ein Folge-Advisory zu einer vorherigen CVE zu verwandten CSRF-Flows in denselben unstable-RSC-Pfaden. Die Advisory-Beschreibung selbst benennt die Einschränkung explizit: *"This only affects your application if you are using the unstable RSC APIs."*

**Verifiziert, nicht exploitbar in PhotoSort:** `frontend/src/` wurde durchsucht (`grep -rn "unstable_RSC\|react-router/rsc\|createFromReadableStream\|react-server"`) — keine Treffer. PhotoSort ist eine reine Vite-SPA mit rein client-seitigem Routing (`<BrowserRouter>` in `frontend/src/main.tsx`, `<Routes>`/`<Route>` in `frontend/src/App.tsx`), keine RSC-APIs, kein Server-Rendering-Setup, keine Server-Actions im `react-router`-Sinn. Der konkrete betroffene Codepfad (RSC-Mode-Action-Handling) wird im Projekt schlicht nicht genutzt — die Schwachstelle ist für dieses Repo damit **nicht exploitbar**, unabhängig vom Update.

**Zusätzlich unabhängig entschärft durch bestehende Auth-Architektur:** Selbst falls RSC-Codepfade künftig genutzt würden, ist CSRF laut ADR 0005/`specs/architecture/0003-securitykonzept.md` (Abschnitt "Auth-Modell") bereits strukturell ausgeschlossen — PhotoSort transportiert das Session-Token ausschließlich über den `Authorization: Bearer`-Header (`localStorage`, kein Cookie), nie automatisch vom Browser an fremdinitiierte Requests angehängt. Die hier beschriebene Advisory-Klasse (CSRF gegen Server-Actions) setzt typischerweise Cookie-basierte, browserseitig automatisch mitgesendete Auth voraus — ein weiterer, von der RSC-Nichtnutzung unabhängiger Grund, warum das konkrete Risiko für PhotoSort gering ist.

**Warum trotzdem updaten:** Reine Hygienemaßnahme — ein offener `high`-severity-Alert im Repo ist unabhängig von der tatsächlichen Exploitierbarkeit unerwünschtes Rauschen (erschwert das Erkennen künftiger, tatsächlich relevanter Alerts) und das Update selbst ist ein risikoloser Patch-Bump ohne Breaking Changes innerhalb der bereits deklarierten `^8.2.0`-Range.

**Sicherheitskonzept:** `specs/architecture/0003-securitykonzept.md` wird **nach Umsetzung** (nicht bereits jetzt beim Spec-Erstellen) um einen kurzen, datierten Vermerk im Abschnitt "Angriffsflächen" → "Frontend" ergänzt, analog zum bestehenden Muster bei Spec 0011/0012 — mit dem Kernbefund, dass PhotoSort keine RSC-APIs nutzt und das CSRF-Modell (Bearer-Header, kein Cookie) strukturell unabhängig von dieser Advisory-Klasse ist.

## Teststrategie

- **Erster Schritt bei Umsetzung:** `npm outdated react-router` und `npm view react-router versions` im `frontend/`-Verzeichnis erneut ausführen, um zu bestätigen, dass sich der Sachverhalt seit Spec-Erstellung nicht geändert hat (z.B. falls zwischenzeitlich eine neuere Version mit Breaking Changes erschienen ist) — dann `npm update react-router` bzw. `npm install`.
- **Config-Ebene:** Diff-Review von `frontend/package-lock.json` — erwartungsgemäß nur der `react-router`-Eintrag (Version, `resolved`-URL, `integrity`-Hash) sowie ggf. mitversionierte reine `react-router`-interne Abhängigkeitsverschiebungen, kein `package.json`-Diff.
- **Funktionaler Nachweis:** Bestehende Test-Suite (`npm run test`, Vitest) muss unverändert grün bleiben — insbesondere Tests, die Routing berühren (`ProtectedRoute`, `useUnauthorizedRedirect`, Navigation zwischen Seiten). `npm run lint` (oxlint), `npm run typecheck` (`tsc -b --noEmit`) und `npm run build` (`tsc -b && vite build`) müssen ebenfalls unverändert erfolgreich durchlaufen — ein API-Bruch zwischen 8.2.0 und 8.3.0 (Patch-Release, laut Semver nicht erwartet) würde hier sichtbar.
- **CI:** Der PR selbst durchläuft die bestehenden CI-Jobs (`frontend`) mit der aktualisierten Lockfile — ein grüner Lauf ist der vollständige funktionale Beweis, analog zu Spec 0011.
- **Dependabot-Verifikation:** nach Merge per `gh api repos/{owner}/{repo}/dependabot/alerts/2` prüfen, dass `state` auf `fixed`/`dismissed` wechselt — einmaliger manueller Nachvollzug, kein automatisierter CI-Test.
- **`specs/architecture/0002-testkonzept.md`:** keine Ergänzung nötig — passt ins bestehende Muster "reine Dependency-/Konfigurationsaktualisierung ohne neues Testmuster", analog zu Spec 0011.

## Out of Scope

- Dependabot-Alerts #1 und #3 (`brace-expansion`, `state: auto_dismissed`) — bereits in Spec 0011 explizit als Out of Scope vermerkt, bleiben es hier ebenfalls: nicht actionable, transitive Dev-Dependency, bereits automatisch dismissed.
- Einführung von automatisiertem Dependency-Scanning (`npm audit`/Dependabot-Auto-Merge o.ä.) in CI — bereits in `specs/architecture/0003-securitykonzept.md` unter "Bekannte Lücken" als offener, aber separater Punkt geführt, nicht Teil dieser Spec.
- Migration auf RSC-APIs von `react-router` oder jede sonstige funktionale Nutzung des betroffenen Codepfads — nicht geplant, nicht Teil dieser Spec.
- Aktualisierung weiterer Frontend-Abhängigkeiten über `react-router` hinaus, auch wenn `npm outdated` ggf. weitere veraltete Pakete zeigt — diese Spec ist bewusst auf den einen konkreten Dependabot-Alert beschränkt.

## Entscheidungen

- Kein Edit an `frontend/package.json` — die bestehende `^8.2.0`-Range deckt `8.3.0` bereits ab, verifiziert per `npm outdated`/`npm view` (2026-08-03).
- Keine neue ADR — reine technische Detailentscheidung analog zu Spec 0010/0011.
- `specs/architecture/0003-securitykonzept.md` wird erst nach Umsetzung im Security-Review aktualisiert, nicht bereits beim Spec-Erstellen (analog zu Spec 0011).
- Direkt `Accepted` statt vollem idea-sharpener-Zyklus, da rein mechanischer, automatisiert entdeckter Security-Fix ohne Produktentscheidung — keine Rückfrage an Daniel nötig (analog zu Spec 0011).
