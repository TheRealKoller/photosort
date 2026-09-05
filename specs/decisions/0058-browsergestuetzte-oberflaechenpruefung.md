# 0058 - Browsergestützte Oberflächenprüfung: Playwright, seedbare Demo-Zustände, E2E in CI

**Status:** Accepted — die drei Daniel vorgelegten Punkte (1, 4, 5) sind am 2026-09-05 im Chat wie empfohlen bestätigt worden, siehe „Zur Bestätigung vorgelegt" unten.
**Datum:** 2026-09-05
**Bezug:** [GitHub-Issue #174](https://github.com/TheRealKoller/photosort/issues/174), `specs/features/0174-browser-zugang-fuer-claude.md`

**Löst ausdrücklich ab (Festlegung eines lebenden Dokuments, keine ADR):**
- [`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md), Abschnitt „Was bewusst nicht getestet wird": „Automatisiertes E2E-Testing (Playwright o.ä.): explizite Entscheidung aus Spec 0002, Aufwand für Zwei-Personen-Projekt aktuell nicht gerechtfertigt." Der dort selbst formulierte Vorbehalt — „wird neu bewertet, falls ein Feature auftaucht, dessen Risiko … das nicht mehr rechtfertigt" — tritt hier ein, allerdings aus einem anderen Grund als dort vermutet (siehe Kontext). Ebenso abgelöst: der Satz „**E2E-Ebene:** kein dediziertes E2E-Test-Setup (kein Playwright o.ä.)" in der Frontend-Sektion. Der `test-engineer` zieht das Testkonzept im selben PR nach; diese ADR ändert es nicht selbst (ein Dokument, ein Owner).

**Berührt außerdem (keine Ablösung):**
- [`decisions/0009-local-opencloud-demo-stack.md`](./0009-local-opencloud-demo-stack.md) / [`0010`](./0010-demo-seed-script-as-compose-service.md): das Demo-Overlay mit echtem `opencloud-rolling`-Container bleibt unverändert bestehen und weiterhin lokal zuschaltbar. Punkt 5 entscheidet nur, dass es **nicht** Teil des automatisierten Laufs wird.
- [`decisions/0027-single-origin-api-proxy-ueber-frontend-nginx.md`](./0027-single-origin-api-proxy-ueber-frontend-nginx.md) / `features/0049` (Status `Accepted`, noch nicht umgesetzt): solange der `/api`-Proxy fehlt, spricht der Browser zwei Origins an. Punkt 6 ist so gewählt, dass die spätere Umsetzung von 0049 nur eine Zeile im Overlay betrifft.
- [`decisions/0055-dark-utility-register-fundament.md`](./0055-dark-utility-register-fundament.md) und Stufe 2 (Issue #321): diese ADR liefert das Werkzeug, mit dem Stufe 2 überhaupt sichtbar geprüft werden kann. Sie trifft keine Gestaltungsentscheidung.

## Kontext

Claude entwickelt und prüft PhotoSorts Oberfläche ohne sie je zu sehen. Das ist kein Komfortproblem, sondern eine strukturelle Lücke, die das Testkonzept selbst an mehreren Stellen ausdrücklich benennt: „**jsdom hat keine Layout-Engine** … `getBoundingClientRect()` liefert 0, `getComputedStyle()` löst keine Tailwind-Klassen auf. Damit ist prinzipiell nicht prüfbar — und jeder Test, der es vorgäbe, prüfte in Wahrheit einen Klassennamen". Aufgezählt sind dort unter anderem: CSS-Grid-Spaltenzahl über einen Breakpoint hinweg, `position: sticky`, Popover-Kollisionsvermeidung am Bildschirmrand, Größe von Trefferflächen, horizontales Scrollen bei 360 px. Das jeweils benannte Ersatzverfahren ist immer dasselbe: manueller visueller Smoke-Test vor Merge, seit Spec 0320 sogar mit Screenshot-Beleg im PR. Diese Arbeit landet per Konstruktion bei Daniel — genau die Rolle, die das Projekt sonst so weit wie möglich entlastet.

Der ursprüngliche Verzicht auf E2E-Tests war richtig begründet und ist es teilweise noch: „Aufwand für ein Zwei-Personen-Projekt nicht gerechtfertigt", und der als Trigger vorgemerkte Fall (Regressionsrisiko im Zusammenspiel Backend+Worker+Frontend) ist bis heute nicht eingetreten — die Integrationsebene mit echtem Router/QueryClient und gemockter API deckt ihn ab. Eingetreten ist ein anderer: nicht ein Regressionsrisiko, sondern eine **Wahrnehmungslücke des Entwicklers**. Das ist ein Grund, den die damalige Festlegung nicht vorwegnehmen konnte, weil es damals keinen KI-Entwickler mit dieser Einschränkung gab.

Das Fundament ist vorhanden: Der Stack läuft vollständig lokal (`docker-compose.yml`), es gibt synthetische Demo-Fotos und ein Demo-Overlay ohne echte OpenCloud-Instanz (Spec 0009). Was fehlt, sind drei Dinge: ein Browser, den Claude bedienen kann; Datenzustände, die eine Prüfung überhaupt lohnend machen (ein leeres Projekt zeigt kein Grid-Verhalten); und ein automatisierter Teil, der das Ergebnis dauerhaft festhält, statt bei jeder Prüfung erneut vom Wohlwollen des Prüfers abzuhängen.

## Entscheidung

### 1. Playwright als einzige neue Werkzeug-Abhängigkeit — kein MCP-Server in dieser Stufe

Neue Abhängigkeit: `@playwright/test` (npm, Apache-2.0, Microsoft), Browser-Umfang **nur Chromium**. Sie bedient beide Nutzungsarten aus einem Werkzeug: die automatisierten Prüfungen in CI **und** das Ad-hoc-Ansehen/Bedienen durch Claude.

Begründung: Ein einziges Werkzeug bedeutet eine Installation, ein Versionspinning, eine Lernkurve und — der eigentliche Gewinn — dass ein Ad-hoc-Skript, mit dem Claude einen Fehler reproduziert hat, unverändert zu einem CI-Spec werden kann. Playwright bringt genau die drei Fähigkeiten mit, die die Akzeptanzkriterien verlangen und die eine Layout-Engine voraussetzen: echtes Rendering mit Screenshot als Bilddatei, echte Bedienung (Klick/Eingabe/Navigation, dadurch erst erreichbare Zustände wie geöffnete Popover), und Zugriff auf Konsolenausgaben sowie fehlgeschlagene Netzwerkaufrufe. Browserbinaries sind an die Paketversion gebunden, also reproduzierbar — anders als ein systeminstallierter Chrome.

Bewusst **nicht** in dieser Stufe gewählt: ein zusätzlicher MCP-Server (`playwright-mcp` oder `chrome-devtools-mcp`) für das interaktive Bedienen. Er wäre beim Fehlersuchen spürbar angenehmer (schrittweises Klicken, erhaltener Browserzustand zwischen den Werkzeugaufrufen, kein Skript-Schreiben). Dagegen spricht: eine zweite Werkzeugkette für denselben Zweck, eine Abhängigkeit, deren Nutzung selbst durch keinen Test abgesichert ist, und ein Ergebnis, das nicht als Artefakt im Repo landet und deshalb nicht zu einem dauerhaften Prüfsatz reifen kann. Die Tür bleibt ausdrücklich offen: Erweist sich das Schreiben kleiner Skripte im Alltag als zu umständlich, ist das Nachrüsten eines MCP-Servers eine eigene, spätere Story — und dann eine reine Ergänzung, kein Ersatz.

Ebenfalls bewusst nicht gewählt: Puppeteer (kein Testrunner, keine Viewport-Projekte, keine Trace-Artefakte — man baute die halbe Infrastruktur nach), Cypress (eigene Laufzeitwelt, schwergewichtiger, mehrere Viewports weniger sauber), `webdriverio`/Selenium (deutlich mehr bewegliche Teile für denselben Zweck).

### 2. Eigenes Top-Level-Paket `e2e/`, nicht in `frontend/` einhängen

`e2e/` wird ein eigenständiges npm-Paket mit eigener `package.json`/`package-lock.json`, eigenem `tsconfig.json` und eigenem CI-Job — analog dazu, dass `scripts/` bereits ein eigenständiges Python-Paket neben `backend/` ist.

Begründung, drei Gründe, jeder für sich hinreichend: (a) `vitest` und `@playwright/test` exportieren beide `test`/`expect` und kollidieren in einem gemeinsamen Paket regelmäßig über Typ- und Auflösungswege; die Trennung schließt das strukturell aus statt es per `exclude`-Regeln zu bändigen. (b) Der bestehende `frontend`-CI-Job soll weiterhin ein reines `npm ci` ohne Browser-Download machen — Playwright dort mitzuschleppen verlängert jeden Frontend-Lauf ohne Gegenwert. (c) Die E2E-Seite läuft in Node gegen eine laufende Anwendung, nicht im DOM-Kontext des Frontends; sie hat eine andere `tsconfig`-Welt.

Preis: ein drittes `package-lock.json` und ein weiterer CI-Job. Bewusst in Kauf genommen.

### 3. Ein einziger, immer instrumentierter Sitzungsbaustein für beide Nutzungsarten

`e2e/lib/session.ts` erzeugt den Browser-Kontext für **jede** Nutzung und schreibt dabei ohne Zutun des Aufrufers mit: alle Konsolenmeldungen, alle unbehandelten Seitenfehler und alle fehlgeschlagenen bzw. mit Status ≥ 400 beantworteten Netzwerkaufrufe. Darauf setzen zwei Verwendungen auf:

- **CI-Specs** über eine Playwright-Fixture, die zusätzlich nach jedem Test durchsetzt, dass keine unbehandelten Seitenfehler und keine 5xx-Antworten aufgetreten sind (dieselbe Zusicherung für alle Specs, an einer Stelle formuliert).
- **Ad-hoc** über zwei Befehle: `npm run shot -- <pfad> [viewport]` (aufrufen, in beiden Viewports abfotografieren, Protokoll schreiben — der häufigste Fall, ohne dass Claude eine Zeile Code schreibt) und `npm run drive -- <skript>` (beliebige Interaktionsfolge, gleiche Instrumentierung, gleiche Ausgabe).

Ausgaben (PNG, Protokolldateien, Traces) landen unter `e2e/artifacts/` und sind gitignoriert; Claude liest die PNG-Datei direkt. Ad-hoc-Skripte liegen unter `e2e/scratch/` und sind ebenfalls gitignoriert.

Begründung: Das Akzeptanzkriterium „Claude kann Fehler wahrnehmen, die nur zur Laufzeit auftreten" darf nicht davon abhängen, dass Claude bei jedem Ad-hoc-Skript daran denkt, `page.on('console')` zu verdrahten. Es ist eine Eigenschaft des Werkzeugs, nicht eine Disziplinanforderung an den Nutzer.

Bewusst nicht gewählt: eine deklarative Mini-Kommandosprache für Interaktionen (`--click … --type …`). Sie ist für den einfachen Fall überflüssig (dafür gibt es `shot`) und für den interessanten Fall immer zu eng; jede Erweiterung wäre neue, selbst zu wartende Syntax neben der bereits vorhandenen von Playwright.

### 4. Prüfzustände entstehen durch einen deterministischen Seeder im Backend-Paket, nicht durch echte Scan-/Bewertungsläufe

Neues Modul `backend/src/photosort/demo_state.py`, ausgeführt im laufenden Backend-Container (`docker compose … exec -T backend python -m photosort.demo_state`). Es legt vier Projekte mit festem Namenspräfix `Demo — ` an und erzeugt die Bilddateien synthetisch mit Pillow (deterministisch, fester Zufallskeim, erkennbar durchnummeriert) direkt in den Thumbnail-Cache:

1. `Demo — Leeres Projekt` (kein Foto),
2. `Demo — Große Sammlung` (Größenordnung 60–80 Fotos: genug für Scrollen und Listendichte, bewusst keine Performance-Größenordnung — das Akzeptanzkriterium schließt sie aus),
3. `Demo — Bewertet` (Bewertungen aller drei Status, gesetzte Ausschuss-Vorschläge, Kriterien-Bewertungen samt Lauf und Kategorien — ohne sie ist die Bewertungsdetails-Ansicht leer und der Grid-/Popover-Test wertlos),
4. `Demo — Fehlerzustand` (fehlgeschlagener Scan-Lauf mit Fehlermeldung, mindestens ein Foto ohne Cache-Datei für den „wird noch verarbeitet"-Platzhalter, mindestens eine Cloud-Vision-Fehlerzeile).

Drei Eigenschaften sind verbindlich: **Schutz** — das Modul bricht ab, solange nicht eine ausdrückliche Umgebungsvariable gesetzt ist *und* die Datenbank ausschließlich Projekte mit dem Demo-Präfix enthält (dasselbe Muster wie die bestehende Ziel-URL-Prüfung in `scripts/seed-opencloud-demo.py`, Spec 0009). **Zielzustands-Idempotenz** — ein erneuter Lauf löscht die eigenen Demo-Projekte und legt sie neu an, das Ergebnis ist unabhängig vom Vorzustand identisch (Muster aus ADR 0048). **Keine Netzwerkabhängigkeit** — kein OpenCloud, kein Worker, keine Hintergrundjobs.

Begründung für den Ort: Das Modul braucht die echten SQLAlchemy-Modelle und die echte Cache-Schlüssel-/Thumbnail-Erzeugung (`thumbnails.py`). Ein Zweitabbild davon in `scripts/` wäre exakt die Contract-Drift, vor der das Testkonzept an anderer Stelle ausdrücklich warnt: Ändert sich der Cache-Schlüssel oder eine Spalte, driftet der Seeder still ab und die Prüfungen prüfen einen Zustand, den die Anwendung so nie erzeugt. Im Backend-Paket unterliegt er zudem automatisch `mypy --strict`, `ruff` und dem Coverage-Gate.

Preis, bewusst in Kauf genommen: ein Demo-Codepfad liegt im Produktiv-Image. Er startet nie von selbst (kein Aufruf aus `main.py`/`worker.py`, kein Endpunkt), und der Schutz oben verhindert, dass ein versehentlicher Aufruf gegen eine echte Datenbank etwas anrichtet. Bewusst nicht gewählt: Zustände über echte Scan-/Bewertungsläufe erzeugen — das braucht OpenCloud, den Worker und Modell-Inferenz, dauert Minuten und ist in seinem Ergebnis nicht deterministisch; ein Prüfsatz, dessen Datengrundlage von Lauf zu Lauf schwankt, kann kein verlässliches Signal sein.

### 5. Der automatisierte Lauf kommt ohne den OpenCloud-Container aus

Der CI-Job startet `postgres`, `redis`, `backend` und `frontend` — nicht `opencloud-demo`, nicht `worker`. Der Ordner-Browser ist die einzige Ansicht, die eine erreichbare OpenCloud-Instanz braucht; er wird in CI in seinem **Fehlerzustand** geprüft (Anfrage schlägt fehl → die Ansicht muss eine erkennbare Fehlermeldung zeigen, keine leere Fläche, kein Dauer-Ladezustand). Für seinen Normalfall bleibt lokal das unveränderte Demo-Overlay aus Spec 0009 zuschaltbar (eine zusätzliche `-f`-Datei).

Begründung: `opencloudeu/opencloud-rolling` ist ein ungepinntes Rolling-Image mit mehrstufigem Startvorgang. Es wäre mit Abstand die wahrscheinlichste Ursache sprunghaft fehlschlagender Läufe — und damit ein direkter Verstoß gegen das Akzeptanzkriterium, dass ein Fehlschlag ein verlässliches Signal sein muss. Hinzu kommt: Keine der Prüfungen, um die es hier geht (Grid-Spalten, sticky Header, Popover-Position, Trefferflächen, Breakpoints), berührt OpenCloud überhaupt. Der Preis ist ehrlich zu benennen: Contract-Drift gegen den echten OpenCloud-Server bleibt eine offene Lücke des Projekts — sie war es vorher auch, diese ADR schließt sie nicht und gibt auch nicht vor, es zu tun.

Der Worker bleibt draußen, weil kein Spec einen Hintergrundjob auslöst (Punkt 7). Lokal startet er wie gewohnt mit, damit Claude auch echte Abläufe ausprobieren kann.

### 6. Ein Compose-Overlay `docker-compose.e2e.yml` für beide Zwecke — lokal wie in CI derselbe Stack

Neue Overlay-Datei, rein additiv wie `docker-compose.demo.yml`. Sie leistet genau drei Dinge:

a) **Nur lokal erreichbar.** Der Hauptstack bindet seine Ports bewusst ungebunden (PhotoSort soll produktiv aus dem Netz erreichbar sein). Das Overlay bindet sie auf `127.0.0.1`. **Fallstrick, vorab gelöst:** Compose *ergänzt* `ports`-Listen beim Überlagern, statt sie zu ersetzen — eine naive Überlagerung ergäbe zwei Bindungen, davon weiterhin eine offene. Deshalb `ports: !override [...]`, plus ein CI-Schritt, der aus `docker compose config` verifiziert, dass jeder Dienst genau eine veröffentlichte Bindung hat und diese auf `127.0.0.1` liegt. Ohne diesen Nachweis wäre das Akzeptanzkriterium „nicht aus dem Netz erreichbar" eine Behauptung.

b) **Eigene, feste Werte statt `.env`-Abhängigkeit.** Zugangsdaten der Demo-Konten, `SECRET_KEY` und `VITE_API_BASE_URL` stehen als explizite `environment:`/`build.args`-Werte im Overlay. **Nachträglich geschärft durch die Security-Konsultation zu Spec 0174 (M4): diese Aufzählung war unvollständig und ist als Mindestmenge zu lesen, nicht als Liste.** Ein expliziter Wert im Overlay schlägt die `.env`-Interpolation der Basisdatei — aber ausschließlich für Variablen, die das Overlay auch tatsächlich setzt. Jede Variable des Produktivstacks muss daher explizit gesetzt sein, insbesondere `OPENCLOUD_BASE_URL`/`_USERNAME`/`_APP_TOKEN`/`_DRIVE_NAME`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `POSTGRES_*`, `CORS_ALLOWED_ORIGINS` und die Ports (OpenCloud- und Cloud-Schlüssel auf `""`). Andernfalls zieht der Prüfstack aus einer echten `.env` den echten OpenCloud-App-Token — der kürzeste Pfad zu echten Familienfotos. Abgesichert wird das nicht durch Sorgfalt beim Pflegen der Liste, sondern durch einen CI-Nachweis, der auch für künftig hinzukommende Variablen wirkt: Köder-`.env` mit Sentinel-Werten anlegen, danach darf kein Sentinel in `docker compose … config` vorkommen. Damit läuft der Stack ohne vorheriges `cp … .env`, und eine im Arbeitsverzeichnis liegende echte `.env` kann ihn nicht stillschweigend umkonfigurieren — Compose liest `.env` immer automatisch, und die bestehenden CI-Schritte tragen bereits sichtbar an diesem Problem (`rm -f .env` zwischen den Prüfschritten).

c) **Kein OpenCloud, keine Änderung am Produktivpfad.** `docker-compose.yml` bleibt unangetastet.

d) **Eigener Compose-Projektname (`name: photosort-e2e`), nachgetragen aus der Security-Konsultation (M5).** Ohne ihn teilt der Prüfstack die Volumes `postgres_data`/`photo_cache` eines lokal laufenden Produktiv- oder Demo-Stacks — der Seeder liefe dann gegen dessen Datenbank und Thumbnail-Cache. Der eigene Projektname trennt beides strukturell; CI prüft ihn mit.

**Adresse:** Die Prüfungen sprechen `http://localhost:8080` an — bewusst `localhost`, nicht `127.0.0.1`: Die Origin des Browsers muss zu `CORS_ALLOWED_ORIGINS` passen, und die beiden Schreibweisen sind CORS-seitig verschiedene Origins. Die 127.0.0.1-Bindung betrifft nur, wer von außen verbinden darf, nicht die verwendete URL. Wird ADR 0027/Spec 0049 später umgesetzt (`/api`-Proxy im Frontend-nginx, kein Backend-Port mehr), entfällt im Overlay die Backend-Bindung und `VITE_API_BASE_URL` wird `/api` — eine Zeile, sonst nichts.

### 7. Verlässlichkeitsregime: keine Wiederholungen, keine Wartezeiten, feste Viewports

Das Akzeptanzkriterium „ein Fehlschlag ist ein verlässliches Signal" wird als konkretes Regime festgeschrieben, nicht als Absichtserklärung:

- `retries: 0`, auch in CI (Playwrights Vorlage setzt dort standardmäßig 2 — ausdrücklich abgewählt: Wiederholen macht aus einem sprunghaften Test einen unsichtbar sprunghaften Test). `forbidOnly: true`. `workers: 1`, `fullyParallel: false` — alle Specs teilen sich einen geseedeten Datenbestand.
- **Keine festen Wartezeiten.** Kein `waitForTimeout`, kein `sleep`. Gewartet wird ausschließlich über Playwrights Zusicherungen auf einen Zielzustand.
- **Zwei feste Viewport-Projekte:** `mobile` = 360 × 740 (die schmalste im Testkonzept dokumentierte Breite, an der „kein horizontales Scrollen" zugesichert ist) und `desktop` = 1280 × 800. Nur Chromium.
- **Anmeldung einmal**, in einem vorgelagerten Setup-Projekt, gespeicherter Sitzungszustand für alle übrigen Specs; ein einzelner Spec prüft das Anmeldeformular selbst. Kein wiederholtes Anmelden pro Test.
- **Specs sind lesend.** Wo eine Interaktion Zustand ändern würde (eine Bewertung setzen), nutzt der Spec ein eigenes Demo-Projekt und der Job seedet vor dem Lauf neu. Kein Spec löst einen Hintergrundjob aus.
- Bei einem Fehlschlag lädt der CI-Job Screenshots und Traces als Artefakt hoch — ein roter E2E-Lauf ohne Bild wäre für Claude so blind wie der Zustand vorher.
- **Umgang mit Sprunghaftigkeit:** Ein Test, der ohne Codeänderung mal fehlschlägt und mal nicht, wird repariert oder entfernt. Nicht wiederholt, nicht „quarantänisiert", nicht mit einer längeren Zeitgrenze zugedeckt.

### 8. Umfangsgrenze: nur, was jsdom prinzipiell nicht kann

Der automatisierte Prüfsatz bleibt klein und deckt genau die im Testkonzept als „manueller visueller Smoke-Test vor Merge" ausgewiesenen Punkte ab — Grid-Spaltenzahl über den Breakpoint, sticky Header beim Scrollen, Popover öffnet und bleibt im sichtbaren Bereich, Trefferflächengröße, kein horizontales Scrollen bei 360 px, sowie leerer Zustand und Fehlerzustand rendern sichtbar statt weiß. Was auf jsdom-Ebene prüfbar ist, **bleibt** dort: E2E-Specs sind teuer, langsam und altern schneller. Kein Spec dupliziert eine bestehende Vitest-/Pytest-Zusicherung.

Ausdrücklich **nicht** Gegenstand: pixelbasierter Vergleich gegen gespeicherte Referenzbilder (`toHaveScreenshot`). Keine Referenzbilder im Repo. Das ist eine naheliegende, aber eigene spätere Frage — und sie hätte ein eigenes Sprunghaftigkeitsproblem (Schriftrasterung, Renderer-Version), das Punkt 7 gerade ausschließen soll.

### 9. Auslösung ad hoc über einen eigenen Skill, keine Verankerung in der Review-Phase

Neuer Skill `browse-app`: Stack starten, Zustände seeden, ansehen/bedienen, aufräumen. Er wird auf Zuruf aufgerufen, nicht automatisch. Der bestehende Skill `review-ux` erhält einen ausdrücklich unverbindlichen Absatz („darf, muss nicht") und bleibt ohne laufende Instanz vollständig funktionsfähig — seine Prüfpunkte werden nicht auf ein laufendes System umgeschrieben.

Begründung: Der Nutzen liegt im gezielten Hinsehen, nicht im reflexhaften Mitlaufen. Eine harte Kopplung machte jeden Frontend-Review von einem laufenden Docker-Stack abhängig und damit im Zweifel unbenutzbar.

## Konsequenzen

- **Neu:** `e2e/` (Paket, Konfiguration, Sitzungsbaustein, Ad-hoc-Befehle, Specs), `docker-compose.e2e.yml`, `backend/src/photosort/demo_state.py` samt Tests, Skill `.claude/skills/browse-app/`.
- **Geändert:** `.github/workflows/ci.yml` (neuer Job `e2e`), `.gitignore` (Artefakte, Ad-hoc-Skripte, gespeicherter Sitzungszustand), `.claude/skills/review-ux/SKILL.md` (ein unverbindlicher Absatz).
- **Doku (Owner `architect`, im selben PR):** `docs/setup.md` bekommt einen Abschnitt zum lokalen Prüfstack und zum Seeder; `docs/architecture.md` nimmt `e2e/` als vierten Baustein neben `backend/`, `frontend/`, `scripts/` auf und vermerkt unter „Bewusste Annahmen", dass der automatisierte Lauf bewusst ohne OpenCloud arbeitet; `README.md` nennt den zusätzlichen Testpfad.
- **Testkonzept (Owner `test-engineer`, im selben PR):** die oben zitierte Festlegung wird abgelöst, die betroffenen „bleibt manueller visueller Smoke-Test"-Einträge werden auf den neuen Stand gezogen, und die Umfangsgrenze aus Punkt 8 samt Sprunghaftigkeitsregime aus Punkt 7 wird dort verankert.
- **CI-Laufzeit:** Der neue Job baut das Backend-Image (mediapipe/tensorflow, 113-MiB-Modell-Asset) ein zweites Mal — `docker-compose-check` tut das bereits. Bewusst hingenommen: eigenständiger Job heißt eindeutige Fehlerzuordnung, eigene Artefakte und paralleler Lauf. Wird die CI-Laufzeit zum Problem, ist die naheliegende Nachbesserung, beide Jobs zusammenzulegen oder das Image einmal zu bauen und zu teilen — eine spätere Optimierung, keine Vorwegnahme.
- **Dauerhafte Pflegelast:** eine Browser-Abhängigkeit mehr, die regelmäßig aktualisiert werden will, und ein Prüfsatz, der bei jeder Umgestaltung einer Ansicht nachgezogen werden muss. Punkt 8 (kleiner Umfang) und Punkt 7 (Entfernen statt Dulden) sind die Gegenmittel.

## Zur Bestätigung vorgelegt

Diese drei Punkte gehen über eine technische Detailfrage hinaus und wurden Daniel vor dem Umsetzen vorgelegt. **Alle drei sind am 2026-09-05 im Chat wie empfohlen bestätigt worden**; die Entscheidungen 1, 4 und 5 oben gelten damit unverändert:

1. **Bestätigt.** **Punkt 1 — Playwright allein, MCP-Server später bei Bedarf** statt sofort zusätzlich einen MCP-Server einzurichten (angenehmer beim Fehlersuchen, aber zweite Werkzeugkette ohne Testabsicherung).
2. **Bestätigt.** **Punkt 5 — automatisierter Lauf ohne OpenCloud-Container** statt des vollen Demo-Stacks (realitätsnäher, deckt Contract-Drift ab, kostet mehrere Minuten CI-Laufzeit je PR und bringt ein ungepinntes Rolling-Image als Sprunghaftigkeitsquelle mit).
3. **Bestätigt.** **Punkt 4 — Seeder im Backend-Paket** statt in `scripts/` (kein zweites Abbild des Datenmodells, dafür ein geschützter Demo-Codepfad im Produktiv-Image).
