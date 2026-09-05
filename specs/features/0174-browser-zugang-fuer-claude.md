# 0174 - KI soll die Anwendung lokal im Browser ansehen können

**Status:** Accepted
**Erstellt:** 2026-09-05
**Akzeptiert:** 2026-09-05
**Bezug:** [GitHub-Issue #174](https://github.com/TheRealKoller/photosort/issues/174) (Story-Refinement über den `refinement`-Ablauf), technische Konsultation über den `spec-writer`-Ablauf am 2026-09-05

## Ziel

Claude entwickelt und reviewt PhotoSorts Oberfläche heute blind. Die UI/UX-Review-Perspektive urteilt über Design-System-Konformität, ohne die Oberfläche je gesehen zu haben, und alles, was eine echte Layout-Engine braucht, ist im Testkonzept ausdrücklich als „manueller visueller Smoke-Test vor Merge" ausgewiesen — CSS-Grid-Spaltenzahl, sticky Header, Popover-Positionierung, Breakpoint-Verhalten. Diese Prüfarbeit landet per Konstruktion bei Daniel. Dasselbe gilt für Fehler, die sich erst zur Laufzeit im Browser zeigen: Daniel muss sie reproduzieren und beschreiben, bevor Claude sie überhaupt bearbeiten kann.

Das Fundament dafür existiert bereits: Die Anwendung lässt sich vollständig lokal starten (Spec [`0009`](./0009-local-opencloud-demo-stack.md)) und wird von einem Demo-Datenbestand aus synthetischen Fotos versorgt, ohne Verbindung zu einer echten OpenCloud-Instanz. Was fehlt, ist der Zugang für Claude selbst.

Nutznießer ist in erster Linie Daniel — weniger manuelle Sichtung, schnellere Rückmeldung, weniger Runden zwischen „Claude liefert" und „Daniel prüft". Mittelbar profitieren beide Nutzer, weil visuelle Fehler vor dem Merge auffallen statt im Betrieb. **Zeitfenster:** Stufe 2 der Design-System-Umstellung (Issue #321) zieht sämtliche Ansichten auf „Dark Utility Register" nach; der Nutzen dieser Spec ist deutlich höher, wenn sie vorher verfügbar ist.

## User Story

Als Daniel möchte ich, dass Claude die lokal laufende PhotoSort-Instanz selbst im Browser ansehen und bedienen kann, damit visuelle Prüfung, funktionale Verifikation, Fehlerdiagnose und UI-Iteration nicht mehr an meiner manuellen Sichtung hängen.

## Akzeptanzkriterien

Die Kriterien der Story sind vom `test-engineer` dort geschärft worden, wo die ursprüngliche Formulierung nicht entscheidbar machte, ob ein Test sie erfüllt. Die fachliche Aussage ist unverändert.

**Lokale Instanz und Datengrundlage**

- [ ] Claude startet und stoppt auf Zuruf zwei benannte Konfigurationen ohne Zutun Daniels: den **Prüfstack** (`postgres`, `redis`, `backend`, `frontend` — ohne OpenCloud, ohne Worker; identisch zu dem, was CI fährt) und optional den **vollen lokalen Stack** (zusätzlich Worker und das bestehende OpenCloud-Demo-Overlay aus Spec 0009). Die Unterscheidung ist nötig, weil der automatisierte Lauf bewusst unvollständig ist.
- [ ] Die Instanz arbeitet ausschließlich mit synthetischen Testdaten. Keine Verbindung zu einer echten OpenCloud-Instanz, keine Familienfotos — auch nicht vorübergehend oder „nur für diese Session". Strukturell gesichert durch M1/M4/M5/M7 im Abschnitt Security, nicht durch Sorgfalt.
- [ ] Der Demo-Datenbestand wird um vier Projekte mit dem Präfix `Demo — ` erweitert, jedes über eine messbare Eigenschaft definiert: **leer** (0 Fotos); **große Sammlung** (Fotoanzahl gemäß einer benannten Konstante im Band 60–80); **bewertet** (alle drei Bewertungsstatus vertreten, mindestens ein offener Ausschuss-Vorschlag, Kriterien-Lauf mit Kriterien-Bewertungen, alle Kategorie-Schlüssel des festen Sets belegt); **Fehlerzustand** (fehlgeschlagener Lauf mit nicht-leerem Fehlertext, mindestens ein Foto ohne Cache-Datei, mindestens eine Cloud-Vision-Fehlerzeile). Drei verschiedene Fehlerdarstellungen im Frontend hängen daran — „mindestens ein Fehlerzustand" wäre zu unbestimmt.
- [ ] Die lokal gestartete Instanz ist nur lokal erreichbar. Nachgewiesen statt behauptet: aus `docker compose config` wird verifiziert, dass (1) die **Anzahl** veröffentlichter Bindungen der erwarteten Zahl entspricht, (2) jede auf `127.0.0.1` liegt, und (3) die Prüfung eine absichtlich ungebundene Bindung nachweislich als Fehler meldet (einmaliger Rot-Nachweis im PR). Ohne (1) und (3) bestünde die Prüfung auch dann, wenn sie gar nichts findet.

**Ansehen und Bedienen**

- [ ] Für einen **beliebig übergebenen Pfad** erzeugt `npm run shot -- <pfad>` je Viewport eine PNG-Datei und ein Protokoll. Erfüllt ist das Kriterium durch die Allgemeinheit des Befehls, nicht durch eine Aufzählung von Ansichten.
- [ ] Claude kann die Oberfläche bedienen (klicken, tippen, navigieren) und dadurch Zustände erreichen, die erst durch Interaktion entstehen: geöffnete Popover, ausgeklappte Bereiche, abgeschickte Formulare, Bestätigungsdialoge.
- [ ] Konsolenmeldungen, unbehandelte Seitenfehler und Netzwerkaufrufe mit Status ≥ 400 werden mitgeschrieben, **ohne dass das aufrufende Skript etwas dafür tut**. Nachweis: ein Aufruf gegen eine Seite, die nachweislich einen Konsolenfehler und einen 404 auslöst, führt beide im Protokoll. Der Zusatz „ohne Zutun des Aufrufers" ist der eigentliche Gehalt — sonst wäre es eine Disziplinanforderung, keine Zusage.
- [ ] Zwei feste Viewport-Projekte sind prüfbar: `mobile` 360 × 740 und `desktop` 1280 × 800. Breakpoint-Leiter-Specs setzen ihre Breite selbst (siehe Edge Case E1 in der Teststrategie).

**Auslösung**

- [ ] Der Ablauf startet ausschließlich ad hoc auf Zuruf (Daniel im Chat oder ein Skill, der ihn gezielt anstößt) — er ist nicht automatisch Teil jedes Frontend-Durchlaufs.
- [ ] `.claude/skills/review-ux/SKILL.md` enthält eine ausdrücklich unverbindliche Formulierung („darf, muss nicht") und **keinen** Schritt, der eine laufende Instanz voraussetzt. Geprüft nach dem im Testkonzept etablierten Muster für Agenten-/Skill-Dateien (Fundstellen-Assertion), nicht durch Interpretation.

**Automatisierte Prüfungen gegen die laufende Anwendung**

- [ ] Ein Satz automatisierter Prüfungen läuft gegen die real laufende Anwendung und deckt genau die als **manueller *visueller* Smoke-Test vor Merge** geführten Punkte ab: CSS-Grid-Spaltenzahl über den Breakpoint, sticky Header beim Scrollen, Popover-Kollisionsvermeidung, Trefferflächengröße, kein horizontales Scrollen bei 360 px, sowie leerer Zustand und Fehlerzustand rendern sichtbar statt weiß. Alle übrigen „manueller Smoke-Test"-Einträge des Testkonzepts (OpenCloud-Vollstack, Worker-SIGTERM, Postgres-Migrationen, D2-Diagramme, `gh-board`-Läufe, Scoring-Kalibrierung) bleiben ausdrücklich manuell und werden im selben PR als solche kenntlich gemacht.
- [ ] Der CI-Job ist **blockierend** (kein `continue-on-error`, kein Pfadfilter — ein Backend-Change kann die Oberfläche brechen). Jeder Layout-Spec belegt bei seiner Einführung einen **roten Lauf im PR** (Eigenschaft mutwillig kaputt gemacht); ohne diese Klausel ist „schlägt bei einem gebrochenen Ablauf fehl" nicht nachweisbar, sondern nur behauptet.
- [ ] Die bestehende Festlegung des Testkonzepts, kein dediziertes E2E-Test-Setup zu betreiben, wird bewusst und sichtbar abgelöst — mit dokumentierter Begründung in ADR [`0057`](../decisions/0057-browsergestuetzte-oberflaechenpruefung.md) und im selben PR im Testkonzept nachgezogen, an beiden Stellen („Was bewusst nicht getestet wird" und Frontend-Sektion „E2E-Ebene").
- [ ] Ein Fehlschlag ist ein verlässliches Signal: `retries: 0`, `forbidOnly: true`, `workers: 1` sind per Assertion an die Konfiguration gebunden, damit ein späteres „die Flakes wegkonfigurieren" laut scheitert statt still zu gelingen. Sprunghafte Prüfungen werden repariert oder entfernt, nie durch Wiederholen übergangen. Wird ein Spec **entfernt**, wandert die dadurch wieder offene Zusage zurück in „Bekannte Lücken" des Testkonzepts — sonst verschwindet mit dem Spec auch das Wissen, dass etwas ungeprüft ist.

## Datenmodell-Bezug

Keine Schemaänderung, keine Migration. Der neue Seeder schreibt ausschließlich über die **bestehenden** Modelle (`Project`, `Photo`, `Rating`, `PhotoScore`, Lauf-Entitäten) und die **bestehende** `thumbnails.py`-Logik in den Cache — bewusst kein zweites Abbild des Datenmodells, das bei einer Modelländerung stillschweigend veralten könnte. Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Ansatz:** Ein Werkzeug (Playwright, nur Chromium) bedient beide Zwecke — Claudes Ad-hoc-Blick auf die laufende Instanz und den automatisierten Prüfsatz in CI. Ein Ad-hoc-Skript, mit dem ein Fehler reproduziert wurde, kann unverändert zum CI-Spec werden. Die Prüfzustände entstehen nicht aus echten Scan-/Bewertungsläufen (langsam, nichtdeterministisch, braucht OpenCloud + Worker + Modell-Inferenz), sondern aus einem deterministischen Seeder, der direkt Datenbank und Thumbnail-Cache füllt. Rein additiv: `docker-compose.yml` und der Produktivpfad bleiben unangetastet; das Demo-Overlay aus Spec 0009 bleibt unverändert und lokal zuschaltbar. Vollständige Begründung inkl. Alternativenvergleich: ADR [`0057`](../decisions/0057-browsergestuetzte-oberflaechenpruefung.md).

**Neue/betroffene Komponenten:**

- **`e2e/`** (neues Top-Level-npm-Paket, neben `backend/`, `frontend/`, `scripts/`): `@playwright/test`, eigene `package.json`/`package-lock.json`/`tsconfig.json`. Bewusst nicht in `frontend/` eingehängt — `vitest` und `@playwright/test` kollidieren über `test`/`expect`, der `frontend`-CI-Job soll ohne Browser-Download bleiben, und E2E läuft in Node statt im DOM-Kontext.
  - `e2e/lib/session.ts` — erzeugt jeden Browser-Kontext und schreibt dabei **immer** Konsolenmeldungen, unbehandelte Seitenfehler und fehlgeschlagene/≥ 400-Netzwerkaufrufe mit. Das Akzeptanzkriterium „Claude kann Laufzeitfehler wahrnehmen" ist damit eine Eigenschaft des Werkzeugs, keine Disziplinanforderung.
  - `e2e/lib/fixtures.ts` — Playwright-Fixture auf `session.ts`, setzt für alle Specs zentral durch: keine unbehandelten Seitenfehler, keine 5xx.
  - `e2e/bin/shot.ts` / `e2e/bin/drive.ts` — `npm run shot -- <pfad> [viewport]` (aufrufen, in beiden Viewports abfotografieren, Protokoll schreiben) und `npm run drive -- <skript>` (beliebige Interaktionsfolge). Ausgaben nach `e2e/artifacts/`, Ad-hoc-Skripte unter `e2e/scratch/` — beides gitignoriert.
  - `e2e/setup/auth.setup.ts` — einmalige Anmeldung, gespeicherter Sitzungszustand (Token liegt in `localStorage`, `storageState` trägt das). Schlägt bei Misserfolg **hart** fehl, ohne Fallback auf einen anonymen Lauf (siehe M7).
  - `e2e/tests/*.spec.ts` — sieben Specs, siehe Teststrategie.
  - `e2e/playwright.config.ts` — `retries: 0` auch in CI, `forbidOnly: true`, `workers: 1`, `fullyParallel: false`, zwei Chromium-Projekte `mobile` 360 × 740 und `desktop` 1280 × 800, `baseURL` fest auf `http://localhost:8080` (bewusst `localhost`, nicht `127.0.0.1`: die beiden Schreibweisen sind CORS-seitig verschiedene Origins, siehe Edge Case E5).
- **`docker-compose.e2e.yml`** (neu, Root, additives Overlay analog `docker-compose.demo.yml`): eigener Compose-Projektname `photosort-e2e` (M5), Ports auf `127.0.0.1` per **`ports: !override`** (Compose *ergänzt* `ports`-Listen beim Überlagern — eine naive Überlagerung ließe die offene Bindung bestehen), **jede** Variable des Produktivstacks als expliziter Wert (M4, nicht nur die in ADR 0057 zunächst aufgezählten), kein OpenCloud.
- **`backend/src/photosort/demo_state.py`** (neu, mit `python -m`-Einstieg): legt die vier Demo-Projekte an, erzeugt die Bilder synthetisch mit Pillow und schreibt sie über die **echte** `thumbnails.py`-Logik in den Cache. Dreiteilige fail-closed Sperre vor dem ersten Schreibzugriff (M1), Löschen nur entlang eigener Zeilen und berechneter Pfade (M2), kein Aufrufpfad aus der laufenden Anwendung (M3). Zielzustands-idempotent (Muster aus ADR 0048). Kein Netzwerk, kein Worker, kein Hintergrundjob. Einstiegspunkt-Form bindend nach dem Muster von `category_diff.py`: `main(argv=None, *, database_url=None) -> int`, `asyncio.run()` innerhalb `main()`, `__main__`-Dispatch als einzige `pragma: no cover`-Zeile.
- **`.github/workflows/ci.yml`**: neuer Job `e2e` — Stack per Overlay hochfahren (`postgres`/`redis`/`backend`/`frontend`, kein `worker`, kein OpenCloud), seeden, Prüfungen laufen lassen, bei Fehlschlag Screenshots/Traces als Artefakt hochladen (M9). Zusätzliche Schritte: Port-Bindungs-Nachweis (M6), Köder-`.env`-Sentinel-Nachweis (M4), Compose-Projektname (M5), keine Bilddatei unter `e2e/` im Git-Index (M10).
- **`.claude/skills/browse-app/SKILL.md`** (neu): Stack starten → seeden → ansehen/bedienen → aufräumen. Ad hoc auf Zuruf. **`.claude/skills/review-ux/SKILL.md`**: ein ausdrücklich unverbindlicher Absatz („darf, muss nicht"); die Prüfpunkte werden **nicht** auf ein laufendes System umgeschrieben, der Skill bleibt ohne Instanz voll funktionsfähig.
- **Doku im selben PR:** `docs/setup.md` (neuer Abschnitt), `docs/architecture.md` (`e2e/` als vierter Baustein, Annahme „automatisierter Lauf bewusst ohne OpenCloud"), `README.md`, `.gitignore`; `specs/architecture/0002-testkonzept.md` (durch `test-engineer` bereits eingearbeitet) und `specs/architecture/0003-securitykonzept.md` (durch `security-engineer` bereits eingearbeitet).

**Datenfluss:** Seeder → Postgres + Thumbnail-Cache-Volume → Backend-API → Frontend-nginx → Chromium (Playwright) → Screenshots/Protokolle als Dateien → Claude liest die PNG. Kein OpenCloud im Pfad, keine Hintergrundjobs, keine echten Fotos.

**Wiederverwendet vs. neu:** Wiederverwendet werden die Compose-Overlay-Konvention (Spec 0009), das Muster „funktionaler Compose-Check in CI" (Specs 0010/0013/0016), die Schutz-vor-echten-Daten-Logik des bestehenden Seeders (`validate_demo_base_url`) und die Paket-neben-Paket-Struktur von `scripts/`. Neu und bewusst begrenzt: die Browser-Abhängigkeit selbst, der Prüfsatz gegen die laufende Anwendung, und ein Demo-Seeder im Backend-Paket.

**Ausdrücklich abgelöst:** Die Testkonzept-Festlegung „kein dediziertes E2E-Test-Setup (kein Playwright o.ä.)". Der dort selbst formulierte Vorbehalt tritt ein — allerdings aus einem anderen Grund als damals vermutet: nicht ein Regressionsrisiko im Zusammenspiel mehrerer Systeme, sondern die Wahrnehmungslücke eines KI-Entwicklers, den es damals nicht gab.

**Umsetzungsreihenfolge für `developer`:**

1. **`demo_state.py` + Backend-Tests** (rot→grün): Schutzabbruch, Zielzustands-Idempotenz, die vier Zustände, Wiederverwendung der echten Thumbnail-Erzeugung. Erster Nutzen ohne jede neue Abhängigkeit.
2. **`docker-compose.e2e.yml`**: Stack hochfahren, seeden, im Browser sichtbar; Projektname, `!override`-Bindung und Sentinel-Nachweis prüfen.
3. **`e2e/`-Gerüst + `session.ts` + `shot`/`drive`**: Nachweis, dass ein Screenshot entsteht und ein Konsolen-/Netzwerkprotokoll geschrieben wird. Ab hier kann Claude bereits hinsehen — die restlichen Schritte sind Absicherung.
4. **Playwright-Specs**, einer nach dem anderen, jeder zuerst gegen den Ist-Zustand rot/grün abgesichert (ein Spec, der auch bei kaputtem Layout grün ist, ist wertlos).
5. **CI-Job `e2e`** inkl. der vier Nachweis-Schritte und Artefakt-Upload bei Fehlschlag.
6. **Skill `browse-app`** + unverbindlicher Absatz in `review-ux`.
7. **Doku**: `docs/setup.md`, `docs/architecture.md`, `README.md`, `.gitignore`.

**Bewusste Grenzen:** Kein Pixelvergleich gegen gespeicherte Referenzbilder. Kein Spec dupliziert eine bestehende Vitest-/Pytest-Zusicherung — automatisiert wird nur, was jsdom prinzipiell nicht kann. Contract-Drift gegen den echten OpenCloud-Server bleibt eine offene Projektlücke; sie war es vorher auch.

## UI/UX

**Nicht relevant.** Das Feature ändert weder Frontend-Code noch sichtbare Zustände der Anwendung — es ist Entwicklungs-Infrastruktur, die Claude ermöglicht, die **bestehende** Oberfläche zu betrachten und zu bedienen, vergleichbar mit dem Hinzufügen eines Test-Frameworks oder CI-Jobs. Kein neues Layout, keine neue Interaktion, keine neue Zustandsdarstellung.

Die inhaltlichen Hinweise des `ux-ui-designer` zum Prüfumfang sind stattdessen in die Teststrategie eingeflossen: die drei wichtigsten browser-visuellen Zusagen sind CSS-Grid-Spaltenwechsel über den Breakpoint, Popover-Positionierung/Kollisionsvermeidung (Radix-Popover in `CurateCategoriesPage`/`ProjectStatsPage`) und der sticky Header beim Scrollen; ergänzend hilfreich, aber nicht kritisch: Unterscheidbarkeit der Bewertungs-Badge-Farben bei 360 px und 1280 px sowie sichtbare Skelett-/Ladezustände. Der Seeder deckt alle Kategorie-Schlüssel des festen Sets ab, damit die Chip-Darstellung vollständig prüfbar ist.

## Teststrategie

**Unit (pytest, `backend/tests/`):** reine Erzeuger von `demo_state.py` — Bildbytes, Zustandsbeschreibung, Präfix-/Guard-Prädikat. Ohne DB, ohne Docker.

**Integration (pytest, `db_session`-Fixture / dateibasierte SQLite in `tmp_path`):** die DB-Schreibschicht und `main()`, nach dem Muster von `category_diff.py` (synchrone `main()`-Tests).

**`demo_state.py` konkret:**

- **Schutzabbruch:** sechs Fälle (Variable fehlt / Variable mit unbrauchbarem Wert wie `""`/`0`/`false` / Fremdprojekt in der DB / nur Demo-Projekte / **leere** DB muss laufen / Präfix-Randfall `Demo` bzw. `Demonstration` ohne `Demo — ` gilt als fremd). Entscheidend: **jeder Abbruch-Fall assertiert zusätzlich den unveränderten Vorzustand** (Zeilenzahlen je Tabelle, Dateimenge im Cache). Ein Guard, der erst nach dem ersten `DELETE` greift, bestünde einen reinen Exit-Code-Test und wäre genau der Fehler, gegen den er antritt.
- **Idempotenz:** nicht „zweimal laufen ohne Absturz", sondern **normalisierter Zustands-Schnappschuss** (Projektnamen, Fotoanzahl je Projekt, Bewertungsverteilung, Vorschlagszahl, Lauf-Status, Cache-Dateimenge) vor/nach. Der aussagekräftige Fall: laufen → Zustand mutwillig verfälschen (Foto löschen, Bewertung ändern, fünftes Demo-Projekt anlegen, Cache-Datei löschen) → erneut laufen → Schnappschuss identisch zum ersten. Nur das unterscheidet Zielzustands- von Anhänge-Idempotenz.
- **Die vier Zustände:** geprüft über ihre prüfrelevante Eigenschaft, nie über die Implementierung. Die Fotoanzahl ist eine **Kardinalitäts-Assertion gegen die benannte Konstante**, nicht gegen den Testparameter — sonst prüfte der Test sich selbst.
- **Determinismus + Drift:** zwei Läufe in getrennten `tmp_path` liefern **byte-identische** Bilddateien (Hash). Der Test fragt nicht den Seeder, wohin er geschrieben hat, sondern berechnet den Pfad unabhängig über die Funktionen aus `thumbnails.py` — damit wird eine Änderung der Cache-Schlüssel-Bildung rot statt still.
- **Coverage-Gate (≥ 80 %):** kein `omit`, kein pauschales `pragma`, um das Gate zu halten — die Antwort auf einen Rückgang sind Tests. Die Laufzeit bleibt beherrschbar, weil die Fotoanzahl ein Parameter mit der Produktionskonstante als Default ist: die Masse der Tests läuft klein, **genau ein** Test fährt die echte Größe.

**E2E (`e2e/`, Playwright/Chromium):** sieben Specs — `grid-columns`, `sticky-header`, `popover-position`, `tap-targets`, `no-horizontal-scroll`, `empty-and-error-states`, `login`. Die vollständige Tabelle inklusive „was ihn bei kaputtem Layout rot macht" steht in `specs/architecture/0002-testkonzept.md`.

**Drei verbindliche Regeln, damit kein Spec bei kaputtem Layout grün bleibt:**

1. **Exakte Kardinalität statt Mindestwert** (`genau 3 Spalten`, nicht `≥ 2`).
2. **Eine Vorbedingungs-Assertion im selben Spec**, die den trivialen Grün-Fall ausschließt: die Seite ist wirklich gescrollt, bevor sticky geprüft wird; der gewählte Trigger liegt wirklich am Rand, bevor Kollisionsvermeidung geprüft wird; die Route trägt wirklich Inhalt, bevor „kein horizontales Scrollen" geprüft wird. In der schärferen Form: **zwei Messungen, die sich unterscheiden müssen** — so fällt ein Grid auf, das gar nicht mehr auf den Breakpoint reagiert, selbst wenn eine der Zahlen zufällig stimmt.
3. **Rot-Nachweis im PR** bei Einführung: Eigenschaft einmal kaputt machen, roten Lauf belegen. E2E-Pendant zum TDD-Rot-Schritt.

**Trefferflächen brauchen einen Treffertest, keine Kastenmessung:** Trefferflächen sind seit dem Dark Utility Register sichtbar 32 px und werden per `::after` (`tap-target`/`tap-target-square` in `index.css`) auf 44 × 44 aufgespannt. Ein Pseudo-Element taucht in **keiner** `boundingBox()` auf — eine Messung des Elementkastens meldete dauerhaft 32 px und wäre entweder falsch-rot oder auf 32 px „kalibriert" und wertlos. Geprüft wird deshalb per `document.elementFromPoint()` an den vier Ecken des 44 × 44-Bereichs. Dasselbe Verfahren deckt zwei bislang als unprüfbar geführte Fehlerklassen mit ab: Klippen durch einen Vorfahren mit `overflow: hidden` und überlappende aufgespannte Trefferflächen benachbarter Elemente.

**Edge Cases:**

- **E1 — Die Breakpoint-Leiter passt nicht zu den zwei Viewport-Projekten.** Das Grid ist `grid-cols-2 sm:grid-cols-3 md:grid-cols-4`: bei 360 px → 2, bei **1280 px → 4**, nicht 3. Der Wechsel 2→3 ist bei keinem der beiden Projekt-Viewports sichtbar. `grid-columns.spec.ts` setzt seine Breite deshalb **selbst** (360 / 700 / 1280) und wird an ein einziges Projekt gebunden, sonst läuft er doppelt mit identischem Ergebnis.
- **E2 — Zwei sticky Elemente mit `top-0 z-10`.** `AppShell`-Header und `Stepper` sind beide `sticky top-0 z-10` und können sich auf den Pipeline-Routen überlagern. Der Spec prüft deshalb zusätzlich disjunkte y-Bereiche im gescrollten Zustand — eine Fehlerklasse, die ohne Layout-Engine unsichtbar ist.
- **E3 — Die globale „keine 5xx"-Fixture gegen den bewusst fehlenden OpenCloud.** Der Ordner-Browser erzeugt in CI **erwartete** Fehler. Zulässig ist nur eine eng umrissene, im jeweiligen Spec sichtbare Erwartung (dieser Endpunkt, dieser Statuscode) — keine globale Ausnahmeliste in der Fixture und kein Herabsetzen der Schwelle, sonst ist die zentrale Zusage praktisch abgeschaltet.
- **E4 — Der Port-Bindungs-Check besteht leer.** Findet er wegen Tippfehler, geänderter Ausgabestruktur oder falschem `-f` **null** Bindungen, ist er grün. Anzahl-Assertion und Gegenprobe sind Pflicht.
- **E5 — `localhost` vs. `127.0.0.1` sind CORS-seitig verschiedene Origins.** Die Specs sprechen `http://localhost:8080` an; die 127.0.0.1-Bindung betrifft nur, wer von außen verbinden darf. Eine „Vereinheitlichung" auf `127.0.0.1` in der `baseURL` bricht CORS und sähe wie ein Anwendungsfehler aus.
- **E6 — Seeder-Laufzeit in der Testsuite.** 60–80 Pillow-Bilder pro Testfall wären unverhältnismäßig; Anzahl als Parameter, Produktionsgröße als Konstante, genau ein Test fährt die echte Größe.
- **E7 — Guard vs. lokale Entwicklungsdatenbank.** Der Schutz bricht ab, sobald **irgendein** Nicht-Demo-Projekt in der DB liegt — im normalen lokalen Dev-Stack der Regelfall. Deshalb bekommt der Prüfstack ein eigenes Postgres-Volume und einen eigenen Cache (siehe M5).
- **E8 — Leere Datenbank muss den eigenen Schutz passieren.** Der Erstlauf darf nicht daran scheitern, dass „keine Demo-Projekte vorhanden" als „nicht ausschließlich Demo-Projekte" gewertet wird.
- **E9 — Präfix-Prüfung als lockeres `startswith("Demo")`.** Ein reales Projekt namens „Demolition Sommer 2019" wäre dann freigegeben und würde gelöscht. Eigener Testfall.
- **E10 — Der Fehlerzustands-Spec prüft eine leere Fläche.** „Kein Dauer-Ladezustand" und „nicht weiß" sind nur zusammen mit einer Höhen-/Sichtbarkeitsassertion aussagekräftig; ein gerendertes, aber kollabiertes Element bestünde sonst.
- **E11 — Chromium-Version driftet mit `@playwright/test`.** Browserbinaries sind an die Paketversion gebunden; ein Minor-Update kann Rendering verändern. Beim Aktualisieren gilt: einmal vollständig laufen lassen, nicht blind mergen — die Alternative wäre Wiederholung, die das Regime ausschließt.

## Security

Das Feature ändert weder Auth noch Berechtigungen noch Datensichtbarkeit und fügt der Anwendung keinen Endpunkt hinzu. Sicherheitsrelevant sind vier neue Kanten: eine neue externe Abhängigkeit (Lieferkette), Secrets im Klartext in einer eingecheckten Datei, ein destruktiver Codepfad im Produktiv-Image, und veröffentlichte Laufzeit-Artefakte aus einem **öffentlichen** Repo. Das Schutzgut ist durchgehend das **Versehen**, nicht ein Angreifer. Projektweite Einordnung: `specs/architecture/0003-securitykonzept.md`, Abschnitt „Browsergestützte Oberflächenprüfung".

**M1 — Dreiteilige, fail-closed Sperre in `demo_state.py`, vollständig ausgewertet vor dem ersten Schreibzugriff:** (a) Umgebungsvariable trägt einen **exakten Literalwert** (nicht „gesetzt"/truthy — `1`/`true` setzt man versehentlich, einen Satz-Literal wie `yes-wipe-and-seed-demo-data` nicht); (b) kein Projekt ohne den `Demo — `-Präfix in der Datenbank; (c) `settings.opencloud_base_url` ist leer **oder** zeigt auf einen bekannten Demo-Host (Muster aus `scripts/seed-opencloud-demo.py::validate_demo_base_url` wiederverwenden, inkl. der dortigen Port-Pflicht). Begründung für (c): Auf einer frisch aufgesetzten Produktivinstanz ist die Datenbank leer, (b) also **leer erfüllt** — (c) ist die einzige Bedingung, die dort noch greift. Jede der drei Bedingungen einzeln testseitig als Abbruchgrund abgesichert.

**M2 — Gelöscht wird nur, was der Seeder selbst angelegt hat.** Zeilenweise entlang der eigenen Demo-Projekte; im Thumbnail-Cache ausschließlich über die aus den eigenen `(photo_id, etag)`-Paaren berechneten Pfade. **Kein** `glob`, **kein** `rmtree` auf dem Cache-Verzeichnis — die Dateinamen sind flache Hash-Schlüssel ohne Projektzuordnung, bei geteiltem Volume träfe ein Glob echte Familien-Thumbnails. Fehlermeldungen geben nur Bedingung und Status aus, nie Konfigurationswerte.

**M3 — Kein Aufrufpfad aus der laufenden Anwendung:** kein Import aus `main.py`/`worker.py`, kein Endpunkt, kein Compose-`command`. Ein Test hält das fest (Import-Graph von `photosort.main` enthält `photosort.demo_state` nicht), statt es nur zu behaupten.

**M4 — Keine Variable des Produktivstacks bleibt im e2e-Overlay interpolierbar.** Ein expliziter Literalwert im Overlay schlägt die `.env`-Interpolation der Basisdatei — aber nur für Variablen, die das Overlay auch setzt. Deshalb müssen **alle** explizit gesetzt sein, insbesondere `OPENCLOUD_BASE_URL`/`_USERNAME`/`_APP_TOKEN`/`_DRIVE_NAME`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `POSTGRES_*`, `CORS_ALLOWED_ORIGINS` und die Ports (OpenCloud- und Cloud-Schlüssel auf `""`). Andernfalls zieht der Prüfstack aus einer echten `.env` den echten App-Token — der kürzeste Pfad zu echten Familienfotos. CI-Nachweis: Köder-`.env` mit Sentinel-Werten anlegen, danach darf kein Sentinel in `docker compose -f docker-compose.yml -f docker-compose.e2e.yml config` vorkommen. Der Check wirkt automatisch auch für künftig hinzukommende Variablen.

**M5 — Eigener Compose-Projektname.** Top-Level `name: photosort-e2e` im Overlay. Sonst benutzt der Prüfstack die Volumes eines lokal laufenden Produktiv-/Demo-Stacks mit — der Seeder liefe dann gegen dessen Datenbank und Cache. CI prüft den Projektnamen mit.

**M6 — Der 127.0.0.1-Nachweis ist Bedingung, nicht Beiwerk.** Eine naive Überlagerung erzeugt zwei Bindungen, davon eine weiterhin offene — `ports: !override` ist Pflicht. CI-Assertion: jede veröffentlichte Bindung jedes Dienstes hat `host_ip == "127.0.0.1"`, und kein Dienst hat mehr als eine. Fällt dieser Schritt weg, werden die Klartext-Zugangsdaten aus dem öffentlichen Repo zu weltweit bekannten Zugangsdaten eines erreichbaren Dienstes.

**M7 — Zielabsicherung der Werkzeuge.** `shot`/`drive` sprechen die im Playwright-Config fest hinterlegte lokale Adresse an; eine frei überschreibbare Basis-URL ist nicht vorgesehen (falls doch, nur gegen eine `localhost`/`127.0.0.1`-Allowlist analog `validate_demo_base_url`). Der Anmeldeschritt schlägt bei Misserfolg **hart** fehl, ohne Fallback auf einen anonymen Lauf — die Demo-Zugangsdaten existieren nur in einer demo-geseedeten Datenbank, ein fehlschlagender Login ist damit selbst die Anzeige „falsches Ziel".

**M8 — Lieferkette.** `e2e/package-lock.json` eingecheckt, Installation ausschließlich `npm ci` (nie `npm install`), `@playwright/test` **exakt gepinnt ohne Caret** (die Paketversion legt über die eingecheckte `browsers.json` zugleich die Chromium-Revision fest), Version ≥ 1.55.1 (darunter CVE-2025-59288 / GHSA-7mvr-c777-76hp). Zusätzlicher CI-Schritt `npm audit signatures` — das npm-Paket trägt Registry-Signatur und SLSA-Provenance und ist damit, anders als das Browser-Archiv, kryptografisch prüfbar. `PLAYWRIGHT_DOWNLOAD_HOST`/`PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST` bleiben ungesetzt. `--with-deps` nur im CI-Job, **nie** in `docs/setup.md` oder im `browse-app`-Skill für Daniels Rechner (installiert als Root per `apt-get` eine aus dem npm-Paket stammende Paketliste und greift auf Fedora ohnehin nicht).

**M9 — CI-Artefakte.** Upload nur bei Fehlschlag, `retention-days: 7` explizit gesetzt, Pfad ausschließlich `e2e/artifacts/`, der gespeicherte Anmeldezustand explizit ausgenommen. Der `e2e`-Job referenziert **kein** `secrets.*` und erweitert die Workflow-`permissions` nicht. Traces enthalten Login-Request und JWT; zulässig ist der Upload nur, weil M1/M4/M5 strukturell sichern, dass im Lauf nichts Echtes vorkommt.

**M10 — Anmeldezustand und Bilddateien bleiben außerhalb von Git.** `.gitignore` deckt `e2e/artifacts/`, `e2e/scratch/` und den Ablageort des `storageState` (eigenes Verzeichnis, z.B. `e2e/.auth/`) ab; die Datei wird pro Lauf neu erzeugt und beim Aufräumen entfernt, nie geloggt, nie als Artefakt hochgeladen (JWT: 30 Tage gültig, laut ADR 0005 nicht widerrufbar). Ergänzend ein CI-Schritt, der sicherstellt, dass unter `e2e/` **keine** Bilddatei im Git-Index liegt — zwei Zeilen, die die wichtigste Projektregel („nie Bilddaten der Familie im Repo") strukturell absichern, jetzt wo erstmals ein Werkzeug Bilddateien in den Arbeitsbaum schreibt.

**Bewusst akzeptiertes Restrisiko:** Der Chromium-Download erfolgt ohne Checksummen-/Signaturprüfung (nur HTTPS zum Playwright-CDN); reproduzierbar ist die URL, nicht die Byte-Identität. Eingeordnet als dieselbe Klasse wie das bereits akzeptierte `gh`-Risiko. Gegen einen Angreifer mit `docker exec` schützt keine der Sperren M1–M7 — sie sollen es auch nicht.

## Entscheidungen

- **Werkzeug: Playwright allein, kein MCP-Server in dieser Stufe** — von Daniel am 2026-09-05 bestätigt (ADR 0057, Punkt 1). Ein Werkzeug für Ad-hoc-Blick und CI-Prüfsatz; ein Skript, mit dem ein Fehler reproduziert wurde, wird unverändert zum CI-Spec. Ein MCP-Server kann später ergänzt werden, wenn sich Bedarf zeigt.
- **Der automatisierte Lauf kommt ohne den OpenCloud-Container aus** — von Daniel am 2026-09-05 bestätigt (ADR 0057, Punkt 5). Das ungepinnte Rolling-Image wäre eine Sprunghaftigkeitsquelle und stünde damit direkt gegen das Akzeptanzkriterium „ein Fehlschlag ist ein verlässliches Signal".
- **Der Demo-Zustands-Seeder liegt im Backend-Paket, nicht in `scripts/`** — von Daniel am 2026-09-05 bestätigt (ADR 0057, Punkt 4). Kein zweites Abbild von Datenmodell und Thumbnail-Cache-Schlüssel; Preis ist ein per M1–M3 geschützter Demo-Codepfad im Produktiv-Image.
- **Screenshot-Belegpflicht aus Spec 0320 entfällt nur für automatisiert Abgedecktes** — von Daniel am 2026-09-05 entschieden. Für die vom Prüfsatz gemessenen Punkte ersetzt der grüne Lauf den Beleg; für gestalterisches Urteil (ästhetische Wirkung, Unterscheidbarkeit von Auswahl und Fokus) bleibt die Belegpflicht unverändert bestehen.
- **Kein Ad-hoc-Blick auf Daniels bestehenden lokalen Datenbestand** — von Daniel am 2026-09-05 entschieden. Der Blick bleibt auf den isolierten Prüfstack mit Demo-Daten beschränkt; das entspricht dem Akzeptanzkriterium wörtlich („ausschließlich synthetische Testdaten … auch nicht vorübergehend") und macht die feste Ziel-Adresse (M7) zur strukturellen Sperre statt zu einer Konvention.
- **Alle vier Fachkonsultationen sind gelaufen, keine übersprungen:** `architect` (Schritt 1, ADR 0057 angelegt), `ux-ui-designer` (Schritt 2, Ergebnis „nicht relevant" mit Begründung), `test-engineer` und `security-engineer` (Schritt 3, beide mit Nachzug im jeweils eigenen lebenden Dokument).
- **ADR 0057 Punkt 6 wurde nach der Security-Konsultation nachgeschärft:** die dort zunächst aufgezählte Variablenliste war unvollständig (M4) und ist jetzt als Mindestmenge samt CI-Nachweis formuliert; der eigene Compose-Projektname (M5) ist als Punkt 6d ergänzt.

## Offene Fragen

Keine. Die fünf Punkte, die über eine technische Detailfrage hinausgingen, sind am 2026-09-05 von Daniel entschieden (siehe „Entscheidungen").

## Out of Scope

- Kein Zugriff auf die produktive Instanz und keine echten Familienfotos, in keiner Variante.
- Keine feste Verankerung in der Review-Phase — die Auslösung bleibt bewusst ad hoc, und `review-ux` bleibt ohne laufende Instanz voll funktionsfähig.
- Kein pixelbasiertes visuelles Regressionsverfahren mit gespeicherten Referenzbildern — naheliegende Erweiterung, aber eigene, spätere Frage.
- Keine Ausweitung des Demo-Datenbestands über die genannten Zustände hinaus (etwa realistisch große Fotomengen für Performance-Messungen).
- Kein Schließen der Contract-Drift-Lücke gegen einen echten OpenCloud-Server; sie bleibt als bekannte Lücke bestehen.
- Keine Anpassung der `review-security`-Trigger-Tabelle um `e2e/package*.json` (vom `security-engineer` als Folgelücke vermerkt, erfordert die Sync-Reihenfolge über ADR 0040 Teil 2 und gehört damit in eine eigene Story).
