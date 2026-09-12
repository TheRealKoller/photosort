# 0404 - Signaturprüfung für jeden npm-Paketsatz

**Status:** Accepted
**Erstellt:** 2026-09-12
**Bezug:** [GitHub-Issue #404](https://github.com/TheRealKoller/photosort/issues/404), ADR
[`0088`](../decisions/0088-signaturpruefung-haengt-am-paketsatz-nicht-am-installationsaufruf.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil der Gegenstand eine mechanisch erzwungene
Zusicherung ist: Die Erkennungsregel des Wächters, seine Gegenproben und die fünf gemessenen
Grenzen der Prüfung sind selbst der Inhalt und nicht auslagerbar, ohne die Zusicherung zu
verkürzen.

## Ziel

Das Projekt sagt eine Signaturprüfung für npm-Abhängigkeiten zu, wendet sie aber nur auf den
Paketsatz an, der nichts ausliefert (die Browser-Prüfwerkzeuge), und nicht auf den, der als
einziger in das an beide Nutzer ausgelieferte Frontend-Bundle eingeht. Diese Asymmetrie ist der
Gegenstand — kein akuter Fund: Am Bestand endet `npm audit signatures` in `frontend/` mit Exit 0,
496 von 496 Paketen tragen eine verifizierte Registry-Signatur.

Der Nutzen ist eng und wird nicht größer dargestellt, als er ist. Die Prüfung belegt „npm hat
dieses Paket signiert", nicht „dieses Paket stammt aus dem Quell-Repository". Was sie ändert:
Eine Abhängigkeit, deren `name@version` die Registry nicht signiert ausliefert, fällt beim
Hinzukommen oder Anheben auf — bevor der Lockfile-Hash sie dauerhaft festschreibt. Ein Eintrag
mit fremdem Host und passendem Hash bleibt dagegen grün; dagegen tragen weiterhin allein
Lockfile-Hash, `npm ci` und der gelesene Lockfile-Diff im Review.

Der zweite Nutzen ist organisatorisch: Die Lücke stand als „Bekannte Lücke" im Sicherheitskonzept
und wurde bei jeder Sicherheitskonsultation neu abgewogen. Sie zu schließen beendet diesen
wiederkehrenden Aufwand.

## User Story

Als Verantwortlicher für die Lieferkette von PhotoSort möchte ich, dass jeder npm-Paketsatz des
Repositories signaturgeprüft installiert wird, damit die zugesagte Prüfung genau dort gilt, wo
Code entsteht, der bei den Nutzern ankommt — und nicht nur dort, wo sie nichts kostet.

## Akzeptanzkriterien

- [ ] **Jeder npm-Paketsatz des Repositoriums hat in `.github/workflows/ci.yml` einen
      Signaturschritt.** Ein Paketsatz ist ein von Git verwaltetes `package-lock.json` außerhalb
      von `node_modules` (heute genau zwei: `frontend`, `e2e`). Für jeden gilt: mindestens ein
      Schritt mit `npm ci` in seinem wirksamen Arbeitsverzeichnis, und **jeder** solche Schritt
      hat als unmittelbaren Nachfolger im **selben Job** einen Schritt mit `npm audit signatures`
      im **selben** wirksamen Arbeitsverzeichnis. Die Paketsatzmenge wird abgeleitet
      (`git ls-files -z`), nicht gepflegt; es gibt keine Ausnahmeliste, auch keine leere
      vorbereitete. Ein künftiger dritter Paketsatz färbt den Job `demo-scripts` rot, bis das
      Schritt-Paar ergänzt ist. Der Installationsaufruf in `frontend/Dockerfile` ist ausdrücklich
      **nicht** erfasst (ADR 0088, Abschnitt 5).
- [ ] **Die Prüfung ist blockierend, und das ist mechanisch dreierlei:** Der Signaturschritt trägt
      weder `continue-on-error` noch ein `if:` noch ein `|| true`. Alle drei ließen den Job grün
      melden, obwohl die Prüfung nicht greift. Kein neuer Job, also auch keine Nachtragung in
      `required_status_checks.contexts` — die Prüfung liegt in bereits geführten Jobs.
      *Vorausgesetzt, nicht zugesichert:* dass `npm audit signatures` bei einer **fehlenden**
      Signatur genauso mit Exit ≠ 0 endet wie bei einer falschen. Das ist Fremdverhalten und wird
      einmal gemessen, bevor dieses Kriterium als erfüllt gilt.
- [ ] **Die `run:`-Nutzlast lautet in jedem Signaturschritt genau `npm audit signatures`** — kein
      zusätzliches Flag, keine Provenance-Forderung, keine Herabsetzung der Prüfstufe. Von den 496
      auditierten Frontend-Paketen tragen alle eine Registry-Signatur, aber nur 188 eine
      Attestierung; eine Attestierungsforderung wäre dauerhaft rot, ohne dass das Projekt sie
      erfüllen könnte.
- [ ] **In jedem Paketsatz trägt jeder Lockfile-Eintrag außer dem Wurzeleintrag ein `resolved`
      unter `https://registry.npmjs.org/` und ein `integrity`.** Ohne diese Zusicherung wäre ein
      `file:`- oder `git+https:`-Eintrag ein ungeprüftes Paket innerhalb eines geprüften
      Paketsatzes: `npm audit signatures` überspringt ihn **still** und meldet Exit 0.
- [ ] **Der Signaturschritt ist der erste Schritt nach der Installation** — vor Formatprüfung,
      Lint, Typprüfung, Test und Build. „Unmittelbar" ist eine Aussage über **Schritte**:
      Kommentar- und Leerzeilen zwischen beiden brechen die Nachbarschaft nicht, ein
      dazwischengeschobener Schritt und eine Job-Grenze sehr wohl. Nicht zugesichert: dass der
      Schritt vor jeder Ausführung fremden Codes liegt — `npm ci` führt Installationsskripte aus,
      bevor er läuft.
- [ ] **Der Prüflauf des Umsetzungs-PRs ist grün, ohne Paket-Ausnahme, ohne Abschwächung.**
      Mechanisch gegen den Diff prüfbar: keine Änderung an `frontend/package-lock.json`,
      `e2e/package-lock.json` oder einer `package.json`. Der grüne Lauf selbst ist eine benannte
      Beobachtungspflicht im PR-Body, kein Repo-Test — eine Registry-Störung kann ihn unabhängig
      von dieser Änderung rot machen.
- [ ] **Der Eintrag unter „Bekannte Lücken" im Sicherheitskonzept ist ersatzlos entfernt;** der
      Abschnitt „Signaturprüfung je npm-Paketsatz statt je Installationsaufruf" unter
      „Angriffsflächen" beschreibt den erreichten Zustand und benennt, was die Prüfung
      ausdrücklich nicht belegt. Eine geschlossene Lücke in einer Liste offener Lücken wäre eine
      falsche Auskunft an den nächsten Leser.

## Datenmodell-Bezug

Nicht relevant. Die Story berührt keine Entität, keine Tabelle und keine Migration.

## Architektur / Umsetzung

**Grundlage:** ADR
[`0088`](../decisions/0088-signaturpruefung-haengt-am-paketsatz-nicht-am-installationsaufruf.md).
Die Zusicherung hängt am **Paketsatz**, nicht am Installationsaufruf. Damit ist sie
selbsterweiternd, und sie muss nicht in Shell- und Doku-Text zwischen einem ausgeführten und einem
bloß genannten `npm ci` unterscheiden — `scripts/check.sh` nennt den Befehl in einer Meldung und
darf ihn genau nicht ausführen. Verworfen sind eine Composite Action, ein Skript unter `scripts/`
und ein neuer CI-Job.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `.github/workflows/ci.yml` | ein neuer Schritt im Job `frontend`, unmittelbar hinter `npm ci` (Zeile 79), **oberhalb** des Kommentarblocks zu `Formatierung pruefen (prettier)` (Zeilen 80–82), der zum Prettier-Schritt gehört |
| `scripts/tests/test_signaturpruefung_je_paketsatz.py` | neu — der Wächter, der die Regel mechanisch erzwingt |
| `specs/architecture/0003-securitykonzept.md` | Eintrag unter „Bekannte Lücken" ersatzlos entfernen; der neue Abschnitt unter „Angriffsflächen" liegt bereits auf dem Branch |
| `specs/architecture/0002-testkonzept.md` | liegt bereits auf dem Branch |
| `specs/decisions/0088-…md` | liegt bereits auf dem Branch |

**Nicht angefasst:** `specs/features/0400-einheitliche-code-formatierung.md` (Zeilen 1008, 1112)
und ADR `0080` — Spec 0400 ist `Implemented`, abgeschlossene Feature-Specs werden nicht
nachträglich umgeschrieben, und der Abschnitt „Entscheidung" einer angenommenen ADR ist
unveränderlich. Ein Review-Finding der Form „Spec 0400 sagt noch das Alte" ist kein gültiger
Befund. `docs/architecture.md`, `docs/setup.md` und das Root-`README.md` bleiben ebenfalls
unberührt: kein neuer Setup-Schritt, keine neue Umgebungsvariable, keine neue Komponente, und
keines der drei zählt CI-Schritte auf.

### Entwurfsentscheidungen

- **Der neue Schritt ist wortgleich zum bestehenden** im `e2e`-Job: `name: Lieferkette -
  Registry-Signaturen pruefen`, `run: npm audit signatures`. Das Arbeitsverzeichnis kommt aus
  `defaults.run.working-directory: frontend` des Jobs; ein zusätzliches `working-directory` am
  Schritt stünde als zweite Quelle daneben.
- **Der Wächter prüft `run:`, nie den Schrittnamen.** Die beiden `npm ci`-Schritte heißen heute
  unterschiedlich. Eine Zusicherung am Namen wäre zugleich zu schwach (ein umbenannter Schritt mit
  demselben Befehl entkäme) und zu streng (eine Umbenennung bräche eine Lieferkettenzusage ohne
  Sachgrund).
- **Der Leser ist textbasiert, ohne YAML-Bibliothek** — konsistent mit
  `test_release_workflow_ohne_selbstmerge.py`, `test_pr_titel_pruefung.py` und
  `test_keine_automatische_formatierung.py`. PyYAML ist in `scripts/pyproject.toml` keine
  Abhängigkeit und wird keine; eine neue externe Abhängigkeit in einer Lieferketten-Story wäre die
  falsche Richtung.
- **Erkennungsregel für einen Installationsschritt:** eine Befehlszeile der `run:`-Nutzlast, deren
  erste zwei Token `npm ci` sind — als einzeiliger Skalar oder Blockskalar (`run: |`), auch wenn
  weitere Zeilen folgen und auch nicht in der ersten Zeile. Zeilen, die mit `#` beginnen, zählen
  nicht. Positiv: `npm ci --omit=dev`, `npm␣␣ci`, `npm ci` hinter `set -euo pipefail`. Negativ:
  `#`-Zeilen und **`npx playwright install --with-deps chromium`** — ein Muster auf dem Wort
  `install` statt auf den ersten zwei Token schlägt dort an.
- **Wirksames Arbeitsverzeichnis aus zwei Quellen:** Schritt-`working-directory` oder
  `defaults.run.working-directory` des Jobs. Die dritte Quelle (`defaults:` auf Workflow-Ebene)
  wird **nicht** unterstützt, sondern ihre Abwesenheit zugesichert — sonst rechnet der Leser nach
  einer Umstellung weiter und liefert ein Ergebnis, das niemand mehr als falsch erkennt.
  Pfadschreibweisen werden normalisiert (`./frontend`, `frontend/`, `frontend/.` sind dasselbe),
  ohne `frontends` oder `frontend/sub` mitzutreffen.
- **Die Paketsatzmenge wird abgeleitet, nicht gepflegt:** `git ls-files -z`, NUL-getrennt (ein
  Pfad mit Zeilenumbruch verbärge sonst einen Paketsatz, und `core.quotePath` liefert
  Sonderzeichen-Pfade in Anführungszeichen). Ein `git`-Aufruf mit Exit ≠ 0 bricht den Test ab
  statt eine leere Menge auszuwerten. **Nie `rglob`** — aus dem Haupt-Checkout sähe es die
  verbundenen Arbeitsbäume unter `.claude/worktrees/` mit.
- **Nicht tragend, aber behalten:** die Zusicherung „kein Installationsaufruf in einem Verzeichnis
  außerhalb der abgeleiteten Paketsatzmenge" (empfohlen auf die Familie `npm {ci,i,install,add}`
  geweitet, heute null Treffer). Sie greift bei keiner realistischen Mutation zuerst — die
  Existenzhälfte fängt dieselben Fälle früher —, macht aber die Arbeitsverzeichnis-Rechnung ein
  zweites, unabhängiges Mal beobachtbar. Sie ist als *nicht tragend* markiert, damit sie später
  nicht wie eine Zusicherung verteidigt wird.

### Reihenfolge der Umsetzung

1. **Rot:** `scripts/tests/test_signaturpruefung_je_paketsatz.py`. Gegen den unveränderten
   `ci.yml` muss er für `frontend` rot und für `e2e` grün sein — dieser Lauf ist der Beleg, dass
   der Wächter die Lücke tatsächlich sieht, und gehört wörtlich in den Abschlussbericht.
2. **Grün:** der neue Schritt in `.github/workflows/ci.yml`.
3. `pytest` im Verzeichnis `scripts/` vollständig (Bestand: 1082 grün), danach `scripts/check.sh`.
4. Den Eintrag unter „Bekannte Lücken" im Sicherheitskonzept ersatzlos entfernen.

### Nicht überprüfbare Annahme

Der Wächter blockiert nur, solange der Job `demo-scripts` als Kontext in
`required_status_checks.contexts` der Branch Protection auf `main` steht. Das ist eine
Repository-Einstellung außerhalb des Codes. Trifft sie nicht zu, ist der Wächter informativ statt
blockierend — dann ist das ein eigener Befund, keine Abschwächung dieser Story.

## UI/UX

Nicht relevant. Die Story ändert ausschließlich CI-Konfiguration, einen Repo-Konsistenztest und
zwei Konzeptdokumente; es gibt keine Stelle, an der etwas angezeigt oder eingegeben wird, und
keine berührte Frontend-Komponente. `ux-ui-designer` wurde deshalb nicht konsultiert.

## Security

**Einstufung: sicherheitsrelevant** (Lieferkette), aber ohne Produkt-Diff: kein Endpunkt, keine
neue Eingabe von außen, keine Änderung an Auth, Berechtigungen oder Datensichtbarkeit zwischen den
beiden Nutzern. Neu geschützt wird mit dem `frontend`-Satz erstmals die Lieferkette, die als
einzige in das an beide Nutzer ausgelieferte Bundle eingeht. Vollständige Bewertung samt
Messungen: `specs/architecture/0003-securitykonzept.md`, Abschnitt „Signaturprüfung je
npm-Paketsatz statt je Installationsaufruf".

**Bedrohung und Gegenmaßnahme.** Eine untergeschobene oder kompromittierte Paketversion des
Frontend-Satzes liefe als JavaScript im Browser beider Nutzer, im selben Ursprung wie die
Anwendung, und käme damit an das dort gehaltene JWT. Gegenmaßnahme dieser Story: Jeder Paketsatz
wird im Prüflauf signaturgeprüft installiert, blockierend, ohne Paket-Ausnahme — mechanisch
erzwungen durch `scripts/tests/test_signaturpruefung_je_paketsatz.py`, nicht durch Disziplin.

**Grenzen der Prüfung — sie ist enger, als „Signaturprüfung" klingt** (gemessen mit npm 10.9.8):

- Sie belegt: Für jedes im installierten Baum liegende Registry-Paket existiert eine über den
  Registry-Schlüssel prüfbare Signatur über die Registry-Metadaten. Fehlende und falsche Signatur
  sind derselbe Befund (Exit 1); ein Lauf ohne installierten Baum endet ebenfalls rot, nicht grün.
- Sie belegt **nicht**, dass die installierten Bytes zu dieser Signatur gehören: `resolved` und
  `integrity` des Lockfiles gehen nicht in die Prüfung ein (gemessen: fremder `resolved`-Host plus
  `integrity` einer anderen Version meldet „verified", Exit 0). Bytes↔Lockfile bindet allein
  `npm ci`, Lockfile↔Registry allein der gelesene Lockfile-Diff im Review.
- Sie belegt nicht „stammt aus dem Quell-Repository"; Provenance wird bewusst nicht gefordert.
  Gegen Kontoübernahme und kompromittierte Release-Pipeline tragen weiterhin allein Lockfile-Hash
  und `npm ci`.
- Geprüft wird der installierte Baum der CI-Plattform, nicht das Lockfile: nicht installierte
  optionale Plattformpakete fallen heraus (496 auditierte gegen 570 Lockfile-Einträge).
- Sie liegt hinter der Ausführung fremden Codes, nicht davor (`npm ci` führt Installationsskripte
  aus). Verhindert wird die *Aufnahme* einer unsignierten Abhängigkeit in `main`, nicht ihre
  Ausführung im Lauf, der sie einführt.

**Muss-Kriterien, die über ADR 0088 hinausgehen:**

- **M-S1 — Der Wächter prüft Wirkung, nicht nur Position.** Er weist einen Signaturschritt mit
  `continue-on-error`, mit `if:` oder mit `|| true` zurück. Ohne das belegt er, dass der Schritt an
  der richtigen Stelle *steht*, nicht dass er den Job rot machen kann.
- **M-S2 — Nicht aus der Registry aufgelöste Abhängigkeiten fallen still aus der Prüfung**
  (gemessen: zwei installierte Pakete, eines `file:` → „audited 1 package", Exit 0, kein Hinweis).
  Derselbe Wächter verlangt deshalb `resolved` unter `https://registry.npmjs.org/` und `integrity`
  für jeden Eintrag außer dem Wurzeleintrag. Am Bestand erfüllt (571 bzw. 8 Einträge, kein
  `.npmrc` im Repository).
- **M-S3 — Die Paketsatzmenge wird NUL-getrennt gelesen** (`git ls-files -z`), und ein
  `git`-Aufruf mit Exit ≠ 0 bricht den Test ab statt eine leere Menge auszuwerten. Der Erfolgsfall
  des Wächters ist „nichts gefunden" und muss gegen stille Leere geschützt sein.
- **M-S4 — Die Gleichbehandlung von fehlender und falscher Signatur wird gemessen**, bevor das
  zweite Akzeptanzkriterium als erfüllt gilt.

**Der Wächtertest schafft keine Angriffsfläche:** er liest Repository-Dateien und ruft
`git ls-files` — kein Netz, keine Ausführung von Repository-Inhalt, keine neue Abhängigkeit. Der
neue CI-Schritt referenziert kein `secrets.*`, fordert keine Rechte (`permissions: contents: read`
unverändert), legt keinen Job an und gibt nur öffentliche Paketnamen und -versionen ins Protokoll.
Ein fremder Pull Request kann über eine zusätzliche `package-lock.json` allein seinen eigenen Lauf
rot machen.

**Die beiden bewussten Ausnahmen sind tragfähig.** `frontend/Dockerfile`: Die Übertragung des
CI-Nachweises trägt, weil das Image aus demselben eingecheckten Lockfile baut, das der
`frontend`-Job im selben Lauf prüft; sie hängt daran, dass der Image-Bau ausschließlich `npm ci`
gegen dieses Lockfile fährt — als Restrisiko im Sicherheitskonzept geführt, weil kein Test das
festhält. `scripts/check.sh`: richtig ohne Prüfung, eine Netzabhängigkeit im netzfreien
Schnellprüflauf wäre ein Schaden ohne Gegenwert.

## Teststrategie

**Ebene.** Es gibt keinen Unit-, Integrations- oder E2E-Anteil: Der Gegenstand ist keine
ausführbare Funktion, sondern eine Form des Repositoriums. Die Ebene ist ausschließlich der
Repo-Konsistenztest im Job `demo-scripts`, ohne Coverage-Bezug. Zweite, nicht automatisierbare
Ebene: der Prüflauf des Umsetzungs-PRs selbst, als benannte Beobachtungspflicht im PR-Body.

**Muster.** Aufbau, Selbstschutz und Gegenproben von `test_release_workflow_ohne_selbstmerge.py`
(reine Funktionen, die eine **Befundliste** mit Datei/Zeile liefern statt eines Urteils; lauter
`ValueError` bei leerem Suchraum; dünne Leser am Dateiende; Mindestzahl plus namentliche
Pflichteinträge; parametrisierte Gegenproben in beide Richtungen), Ableitung des Suchraums von
`test_keine_automatische_formatierung.py`. **Nicht** `test_pr_titel_pruefung.py` (ausführender
Ansatz): `npm audit signatures` braucht Netz und `node_modules`, zugesichert wird hier Struktur,
nicht Verhalten — ein Test nach diesem Muster könnte in `demo-scripts` nicht laufen.

**Gegenproben am mutierten Textabbild** des echten `ci.yml` (zur Laufzeit gelesen, keine
eingecheckte Fixture-Kopie — die wäre eine zweite Quelle der Wahrheit und liefe still
auseinander):

- Signaturschritt entfernt; Reihenfolge getauscht; ein Schritt zwischen die beiden geschoben.
- Arbeitsverzeichnis **am Signaturschritt** verfälscht (`working-directory: e2e` im
  `frontend`-Job): läuft gegen den signierten e2e-Baum, endet grün, `frontend/` bleibt ungeprüft —
  der stillere und schlimmere Fall. Dazu als eigener Codepfad die **entfernte**
  `working-directory`-Zeile am e2e-Installationsschritt (wirksames Verzeichnis wird die
  Repo-Wurzel, `None` statt falscher Zeichenkette).
- `npm ci` als **letzter** Schritt eines Jobs: muss ein Befund sein, nie ein `IndexError` — eine
  Ausnahme im Leser riss sonst die Befunde der übrigen Paketsätze mit. Ebenso: Signaturschritt an
  den Anfang des Folgejobs verschoben (die Job-Grenze bricht die Nachbarschaft).
- Ein fiktiver dritter Paketsatz (synthetisches Paar aus Lockfile-Menge und Workflow-Text) muss
  als fehlend gemeldet werden.
- Pfadschreibweisen: drei gleichwertige Formen grün, `frontends` und `frontend/sub` rot.

**Selbstschutz, weil der Erfolgsfall „nichts gefunden" ist.** Der Struktur-Leser ist der erste im
Repository, der Jobs und Schritte aufbaut statt Zeilen zu filtern — ein Leser, der bei einem
Defekt *nichts* zurückgibt, macht jede Abwesenheits-Assertion leer-grün. Er braucht deshalb
Positiv-Assertions über die **gelesene Struktur**, nicht nur über das Urteil: Zahl der Jobs (≥ 5,
darunter `frontend` und `e2e`), Schrittzahl je Job, und die Position des Signaturschritts als
Index unmittelbar hinter dem Installationsschritt. Dazu: Die Ableitung muss überhaupt etwas finden
(Anzahl > 0), und `frontend` und `e2e` müssen darunter sein (zwei Kanarienvögel, keine gepflegte
Liste).

## Entscheidungen

- ADR 0088 angelegt: Die Zusicherung hängt am Paketsatz, nicht am Installationsaufruf. Nötig, weil
  eine selbsterweiternde, blockierende Regel in den Prüflauf einzieht und zwei bewusste Ausnahmen
  (Image-Bau, `scripts/check.sh`) namentlich festzuhalten sind.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Die Story berührt CI-Konfiguration, einen
  Repo-Konsistenztest und Konzeptdokumente — keine sichtbare Oberfläche, kein Anzeige- oder
  Eingabeort, keine Frontend-Komponente.
- Akzeptanzkriterium 6 gegenüber dem Issue-Body geändert: Der Eintrag unter „Bekannte Lücken" wird
  **ersatzlos entfernt** statt auf den erreichten Zustand umgeschrieben. Was bleibt („was die
  Prüfung nicht belegt"), ist keine Lücke, sondern die Grenze einer erfüllten Zusicherung, und
  steht bei der Zusicherung.
- Die Nutzenaussage des Issue-Bodys ist in dieser Spec enger gefasst: Aufzufallen hat nur eine
  Abhängigkeit, deren `name@version` die Registry nicht signiert ausliefert — ein Eintrag mit
  fremdem Host und passendem Hash bleibt grün (gemessen).
- Ein zusätzliches Akzeptanzkriterium gegenüber dem Issue-Body: `resolved`/`integrity` je
  Lockfile-Eintrag. Ohne es wäre ein `file:`- oder `git+https:`-Eintrag ein ungeprüftes Paket
  innerhalb eines geprüften Paketsatzes.
- Die Zählangaben des Issue-Bodys (497/189) sind hier 496/188: `npm audit` zählt die Wurzel des
  Baums nicht mit. Zählweise, kein Paket.

## Offene Fragen

Keine.

## Out of Scope

- **Der Image-Bau in `frontend/Dockerfile`** bekommt keinen Signaturschritt (ADR 0088, Abschnitt
  5). Jeder Image-Bau — auch Daniels lokaler `docker compose build` — bräuchte dann Netzzugang zur
  Signatur-API und scheiterte ohne ihn.
- **`scripts/check.sh`** bleibt unverändert netzfrei; die zehn Aufrufe bleiben zehn.
- **Provenance-Attestierung** wird nicht gefordert.
- **Der Python-Abhängigkeitssatz.** Für `ruff` und die Backend-Abhängigkeiten gibt es kein
  Lockfile; die exakte Angabe in `pyproject.toml` ist die Fixierung, ohne Integritäts-Hash. Eine
  eigene Frage, nicht diese.
- **Die Ankerliste des Sicherheitskonzepts** um die Prozess-Wächter zu erweitern. Sie führt heute
  ausschließlich Auflagen im Anwendungscode; ein einzelner Eintrag wäre eine halbe Migration.
