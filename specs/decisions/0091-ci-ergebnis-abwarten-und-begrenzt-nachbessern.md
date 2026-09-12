# 0091 - Das CI-Ergebnis wird über den vorhandenen `gh`-Weg abgewartet und begrenzt nachgebessert

**Status:** Accepted
**Datum:** 2026-09-12
**Bezug:** [GitHub-Issue #405](https://github.com/TheRealKoller/photosort/issues/405), Spec [`0405`](../features/0405-einheitliches-warten-auf-ci.md)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung neben der Wegwahl eine
vollständige Ergebnis-Klassifikation trägt, an der die Fail-Closed-Zusage hängt.

## Kontext

`CLAUDE.md` verlangt einen grünen CI-Lauf vor dem Merge. Kein Ablaufschritt stellt dieses Ergebnis
fest: `ship-feature` endet am gepushten, finalisierten Pull Request, `ship-entwurf` am eröffneten.

**Gemessen am Bestand (2026-09-12, `gh` 2.100.0; dokumentierte Mindestversion 2.97.0,
`docs/setup.md`).** Gegen GitHub wurde dabei nichts abgesetzt — gelesen wurden die Hilfetexte und
die Meldungstexte im Binary:

- `gh pr checks [<nummer>] --watch --fail-fast --interval <s> --json bucket,name,state,workflow`
  existiert vollständig. `--watch` wartet bis zum Endstand, `--fail-fast` bricht beim ersten
  fehlgeschlagenen Check ab, `--interval` setzt das Wiederholintervall, `--json` liefert den
  maschinenlesbaren Stand mit dem Feld `bucket` (`pass`/`fail`/`pending`/`skipping`/`cancel`).
- Exit-Codes: `0` erfolgreich, `8` „Checks pending" (eigens dokumentiert), `1` Fehlschlag,
  `2` abgebrochen, `4` Authentifizierung nötig.
- **Exit `1` ist zweideutig.** Im Binary stehen sowohl die Fehlschlag-Ausgabe als auch
  `no checks reported on the '%s' branch` und `no commit found on the pull request`. Ein Ablauf,
  der allein am Exit-Code entscheidet, hält „es gibt noch gar keinen Check" für „ein Check ist
  fehlgeschlagen".
- `gh run watch <run-id>` deckt nur **einen** Workflow-Lauf ab. Das Repository hat zwei am Pull
  Request hängende Workflows (`ci.yml` mit fünf Jobs, `pr-titel.yml`).

Die Werkzeugumgebung deckelt einen einzelnen Shell-Aufruf auf 600 Sekunden. Ein CI-Lauf dieses
Repositories kann länger dauern; der lange Pol ist der Job `e2e` (Image-Bau, Compose-Stack,
Playwright).

## Entscheidung

### 1. Es wird nichts gebaut — der vorhandene Weg trägt

Das Warten ist vollständig von `gh pr checks` abgedeckt: Wiederholintervall, Abbruch beim ersten
Fehlschlag und maschinenlesbares Ergebnis sind Optionen dieses Befehls. Es entsteht kein Skript
unter `scripts/`, keine Schleife aus Einzelabfragen und kein eigenes Wiederholverfahren.

### 2. `gh pr checks`, nicht `gh run watch`

Drei Gründe, jeder für sich tragend: `gh run watch` deckt nur einen der beiden Workflows ab; es
braucht eine `run-id`, die aus einer Antwort stammen müsste und damit gegen Härtungsregel 4.2 des
Katalogs liefe (ein steuernder Wert kommt nie aus einer Antwort); und sein Hilfetext schließt
feingranulare PATs aus, weil `checks:read` dort nicht vergeben werden kann. `gh pr checks` hängt
an der Pull-Request-Nummer, die der Ablauf aus `pr-erstellen` bereits geprüft besitzt, und erfasst
jeden Check am Head-Commit.

`--required` wird **nicht** gesetzt: Solange kein Check in der Branch Protection als erforderlich
eingetragen ist, liefert die Filterung nichts und die Prüfung wäre leer wahr.

### 3. Zwei Katalog-Operationen, und ein `gruen` entsteht ausschließlich aus Exit 0

Der Zugriff läuft — wie jeder GitHub-Zugriff — über den Skill `github-access`. Zwei neue
Operationen:

- **`pr-pruefstand-abwarten`** — blockierend, begrenzt. **Ausgewertet wird ausschließlich der
  Ergebniswert; die Ausgabe wird verworfen**, nicht gelesen und nicht gemeldet. Die Ausgabe von
  `--watch` ist darstellungsabhängig; jede Auswertung an ihr wäre eine Annahme über ein Terminal.
- **`pr-pruefstand-lesen`** — nicht blockierend, `--json`. Auswertungsgrenze `bucket`, `name`,
  `state`, `workflow`. Steuernd sind allein `bucket` und `state`, beides geschlossene
  Wertemengen. `name` und `workflow` sind fremdbeschreibbar (jede installierte App darf einen
  Check-Run mit beliebigem Namen anlegen) und damit reine Anzeigewerte: Chat-Bericht ja;
  PR-Body, Issue-Kommentar, Spec-Datei und **Commit-Nachricht** nein. Die Commit-Nachricht steht
  ausdrücklich dabei, weil das Repository mit `COMMIT_MESSAGES` squasht — jeder Commit-Body
  wandert in den Merge-Commit auf `main`, ins Changelog und in den release-please-Pull-Request,
  wo ein `Closes #NNN` im Namen eines Checks scharf wäre. Vor der Anzeige werden `Cc`/`Cf`-Zeichen
  entfernt und auf 200 Zeichen gekürzt; bleibt nichts übrig, lautet die Meldung „Check ohne
  darstellbaren Namen".

Beide tragen `gh` als einzigen Weg. `pr-pruefstand-abwarten` hat **strukturell** keinen
`mcp`-Weg: Ein MCP-Werkzeug ist ein einzelner Aufruf mit einer Antwort und kann nicht warten; ein
aus MCP-Aufrufen gebautes Wiederholverfahren wäre genau die Eigenentwicklung, die Abschnitt 1
ausschließt.

Der Ergebniswert ist wegunabhängig und vierwertig:

| Wert | Entsteht aus | Folge |
|---|---|---|
| `gruen` | Exit `0`, **und sonst nichts** | Ablauf schließt regulär ab |
| `rot` | Exit ≠ 0 **und** `pr-pruefstand-lesen` zeigt mindestens ein `bucket == fail` | Nachbesserung (Abschnitt 5) |
| `laeuft-noch` | Exit `124` des `timeout`-Aufrufs, oder Exit `8` | Fenster erneut, bis die Obergrenze steht |
| `unbestimmt` | alles andere | **Ablauf hält an und meldet** |

`unbestimmt` umfasst namentlich: Exit `2` bzw. `bucket == cancel` (ein abgebrochener Lauf ist kein
bestandener), Exit `4`, jeden unbekannten Exit-Code, „kein Check am Head-Commit" nach Ablauf der
Anlaufschonfrist, ein nicht verfügbares `gh` und eine Operation, die auf allen ihren Wegen
gescheitert ist. **Ein unbestimmtes Ergebnis gilt nie als grün**, und `rot` wird nie aus einem
Exit-Code allein geschlossen, sondern nur mit Beleg aus `pr-pruefstand-lesen` — das ist die
Auflösung der in „Kontext" gemessenen Zweideutigkeit von Exit `1`.

`bucket == skipping` ist kein Fehlschlag und wird toleriert.

Der Ergebniswert entsteht am Exit-Code des `gh`-Prozesses selbst. Die Ausgabe wird mit
`>/dev/null 2>&1` verworfen, **nie** in eine Pipe geleitet: Hinter einer Pipe stünde der
Exit-Code des letzten Glieds, und ein Fehlschlag ginge als Erfolg durch.

Beide Operationen bekommen die Pull-Request-Nummer aus `pr-erstellen` dieses Laufs, gegen
`^[0-9]+$` geprüft. Die argumentlose Form von `gh pr checks` — Auflösung über den aktuellen
Branch — wird nie benutzt: Sie kann in einem Worktree oder nach einem Branch-Wechsel einen
anderen Pull Request treffen, und der Fix-Push ginge an einen Stand, den der Ablauf nie gemessen
hat.

### 4. Genau ein Wartepunkt, am Ende des Laufs

Gewartet wird **nach dem letzten Push eines Ablaufs**, nicht nach jedem: in `ship-feature` als
neuer Schritt hinter der Finalisierung, in `ship-entwurf` hinter dem Push. Jeder frühere Push
gehört zu einem Stand, der noch in Bewegung ist; auf ihn zu warten kostete Wartezeit für ein
Ergebnis, das ohnehin überschrieben wird. Der Stand, auf den es ankommt, ist der, den Daniel
merged.

### 5. Nachgebessert wird nur, was sich lokal reproduzieren lässt

Der Ablauf holt **keine CI-Protokolle**. Er stellt den Fehlschlag mit den vorhandenen lokalen
Befehlen nach — `./scripts/check.sh` für Formatierung, Lint und Typen, dazu die Testläufe des
abschließenden Qualitätschecks. Reproduziert sich der Fehlschlag, wird er behoben; reproduziert er
sich nicht, hält der Ablauf an und meldet.

Das schließt zwei Dinge zugleich aus: eine neue Operation, die fremden Freitext in beliebiger
Menge in den Kontext zieht, und die Klasse von Fehlschlägen, die nur in der CI-Umgebung entsteht
(`e2e`, Image-Bau, Registry-Störung) — dort ist eine selbstständige Korrektur eine Vermutung, kein
Fix.

Zulässig ist ausschließlich die Klasse, die `scripts/check.sh` und der Testlauf abdecken:
Formatierung, Lint, Typen, fehlschlagende Tests — und davon nur, was an Pfaden liegt, die dieser
Branch ohnehin schon geändert hat (`git diff --name-only origin/main...HEAD`). Ein Fehlschlag in
einer Datei, die der Branch nicht angefasst hat, ist kein Fix-Fall, sondern ein Befund: anhalten
und melden. Reine Formatierung entsteht ausschließlich aus dem Lauf von `scripts/format.sh`, ohne
eine von Hand geschriebene Zeile.

**Eine Nachbesserung schwächt nie eine bestehende Zusicherung ab.** Keine Assertion wird entfernt
oder aufgeweicht, keine Erwartungskonstante eines Tests geändert, damit er besteht. Ist die
Änderung an der Erwartung der einzige Weg zu Grün, hält der Ablauf an und meldet. Der Prüfer
dieses Repositories ist nur zur Hälfte eine Workflow-Datei; die andere Hälfte ist eine Assertion
unter `scripts/tests/` oder `backend/tests/`, die der Job `demo-scripts` bzw. `backend` fährt.
Ein roter Wächtertest fällt damit unter „fehlschlagender Test" und reproduziert sich lokal
einwandfrei — der kürzeste Weg zu Grün wäre, den Wächter selbst zu ändern. Betroffen wären
namentlich das Verbot von `pull_request_target`, die SHA-Pinnung der `release-please`-Action, die
Signaturprüfung je npm-Paketsatz und die Erlaubnisstufen des Operationskatalogs.

**Nicht** zulässig sind deshalb eine fachliche Änderung, eine Änderung an der Spec und jede
Änderung an diesen Pfaden, auch wenn der Branch sie selbst angefasst hat: `.github/**` (nicht nur
`workflows/`), `scripts/tests/**`, `.claude/**` und `CLAUDE.md`, `design/penpot/**` samt
`frontend/penpot/payload.test.ts`, sowie Abhängigkeits- und Fixierungsdateien (`package.json`,
`package-lock.json`, `pyproject.toml`, `uv.lock`, `Dockerfile*`, `docker-compose*.yml`,
`.env.example`). Formatierung nach dem Absatz oben bleibt auch dort zulässig, weil `ruff format`
und Prettier die Bedeutung nicht ändern.

**Gemessen wird vor dem Push, nicht in der Absicht:** Der Ablauf misst den Diff des Fix-Commits
selbst und hält bei einem Treffer aus der Liste an.

Je Runde entsteht **ein** Commit und **ein** Push. Der bestehende Grundsatz, keine zusätzlichen
CI-Läufe zu erzeugen, bleibt damit gewahrt: Eine Runde kostet genau einen weiteren Lauf.

Wer korrigiert, ergibt sich aus der Rollenteilung des jeweiligen Ablaufs. In `ship-feature` der
weiterhin offene `developer`-Subagent per `SendMessage` — Code und Tests bleiben bei ihm, der
Orchestrator führt keinen eigenen Testlauf. In `ship-entwurf` die Hauptsession selbst; dort gibt
es keinen Subagenten, und der Fix-Commit durchläuft **Schritt 1 und Schritt 2 vollständig** —
Pfad-Zulassungsmenge, Wächter-Halt, Bilddatei-Halt, Beispieldaten-Prüfung —, nicht nur die
Pfadmenge. Ein rotes `frontend/penpot/payload.test.ts` wäre sonst durch eine zusätzliche
`BEZEICHNER_FREIGABEN`-Zeile grün zu bekommen: Die Datei, die die Aufweichung verhindern soll,
läge im selben Diff, und die Nutzlast läuft in Daniels angemeldeter Penpot-Sitzung.

Ein Fix-Diff stößt **keine** erneute Review-Runde an. Getragen wird das von der engen Klasse
oben, der Messung vor dem Push und Daniels Merge.

### 6. Die Obergrenzen als Zahlen

- **Einzelaufruf: 540 Sekunden.** Aus der 600-Sekunden-Deckelung der Werkzeugumgebung, mit
  Reserve. Der Aufruf wird bis zur Obergrenze aus dem nächsten Punkt wiederholt; ein abgelaufener
  Einzelaufruf ist `laeuft-noch`, nie `unbestimmt`.
- **Wartefenster je Lauf: 15 Minuten.** Deckt die fünf Jobs samt `e2e` mit Reserve ab.
- **Wiederholintervall: 30 Sekunden.** Bei einem Lauf dieser Länge reicht das; der Vorgabewert von
  10 Sekunden erzeugte nur das Dreifache an Abfragen.
- **Anlaufschonfrist: 120 Sekunden.** „Kein Check am Head-Commit" ist innerhalb dieses Fensters
  nach dem Push kein Befund, danach `unbestimmt`.
- **Nachbesserungsrunden: 2.** Die erste fängt den Einzelfehler, die zweite den Folgefehler, den
  die erste Korrektur auslöst. Ist die dritte nötig, liegt die Ursache in aller Regel außerhalb
  der in Abschnitt 5 zugelassenen Klasse. Erschöpft heißt: anhalten und melden, nie
  weiterversuchen.

Schlechtester Fall: drei Wartefenster, 45 Minuten. Die Zahlen sind Startwerte mit benannter
Widerlegung — läuft das Fenster regelmäßig ab, obwohl der Lauf gesund ist, wird die Zahl an ihrer
einen Stelle im Katalogeintrag erhöht, nicht je Ablauf.

### 7. Durchgesetzt wird die Verdrahtung durch einen Wächtertest

Neuer Test unter `scripts/tests/`, gefahren vom Job `demo-scripts`, nach dem Vorbild von
`test_main_abgleich_verdrahtung.py`. Zugesichert wird ausschließlich **Nachweisbares**: dass beide
Operationen im Katalog stehen und ihre Form halten; dass jedes Ablauf-Skill den Wartepunkt genau
einmal und an der in Abschnitt 4 festgelegten Stelle nennt (Reihenfolge über Zeichenoffsets); dass
die eine `gh pr checks`-Befehlszeile des Katalogs `--watch`, `--fail-fast`, `--interval 30` und
`timeout 540` trägt und `--required` **nicht**; dass das Ergebnisvokabular als Whitelist-Gleichheit
über die Wertespalte der Tabelle oben genau `{gruen, rot, laeuft-noch, unbestimmt}` ist; dass jede
Betriebszahl aus Abschnitt 6 im Suchraum `.claude/**` **genau einmal** vorkommt; und dass die
Auswertungsgrenze von `pr-pruefstand-lesen` exakt die vier Felder nennt, die von
`pr-pruefstand-abwarten` **keines**.

Die Zahl kommt einmal vor, statt dass zwei Vorkommen auf Gleichheit geprüft werden: Was es nur
einmal gibt, kann nicht driften.

**Was ausdrücklich nicht gebaut wird:** ein Prüfer, der aus dem Prosatext herausliest, dass ein
unbestimmtes Ergebnis anhält. Er wäre grün, weil ein Satz dasteht, und fröre nebenbei die
Formulierung ein. Ebenso wenig eine Abwesenheitsprüfung auf Prosa („nirgends steht *Warteskript*"
o.ä.): In Markdown ist der erklärende Satz nicht vom anweisenden zu trennen, ein solcher Prüfer
färbte die Dokumentation rot, die er erzwingen soll. Abwesenheit wird nur auf Befehls- und
Formzeilen geprüft; dass kein Wegwerf-Skript entsteht, ist über die **Anwesenheit** des einen Wegs
zugesichert.

## Begründung

Die naheliegende Alternative zu Abschnitt 5 ist, die CI-Protokolle zu holen und daraus zu
korrigieren. Sie ist mächtiger und an zwei Stellen schlechter: Sie zieht fremdbeschreibbaren
Freitext in unbekannter Menge in den Kontext — heute liest der Ablauf solchen Text an genau einer
Stelle, den Copilot-Inline-Kommentaren am eigenen Pull Request, und das bewusst eng gefasst. Und
sie verführt dazu, auch das zu „reparieren", was lokal gar nicht reproduzierbar ist. Der lokale
Prüflauf ist die schärfere Schranke: Was er nicht zeigt, wird nicht geraten.

## Konsequenzen

- Ein Feature-Lauf endet später — im Regelfall um die Dauer eines CI-Laufs, im schlechtesten Fall
  um 45 Minuten. Das ist der Preis dafür, dass ein abgeschlossener Ablauf eine Aussage über den
  CI-Stand trägt.
- Ein CI-Fehlschlag außerhalb der zugelassenen Klasse (`e2e`, Image-Bau, Registry-Störung) landet
  weiterhin bei Daniel. Die Alternative wäre, ihn raten zu lassen.
- Wird `pr-titel.yml` oder ein Job in `ci.yml` ergänzt, ändert sich hier nichts: `gh pr checks`
  erfasst jeden Check am Head-Commit, ohne gepflegte Liste.
- Was diese Entscheidung nicht leistet: Sie sagt nichts über den Stand **nach** dem Merge. Der
  gewartete Lauf hängt am Head-Commit des Pull Requests, nicht am Merge-Commit auf `main`.
