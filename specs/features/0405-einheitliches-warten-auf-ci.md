# 0405 - Einheitliches Warten auf den CI-Lauf

**Status:** Accepted
**Erstellt:** 2026-09-12
**Bezug:** [GitHub-Issue #405](https://github.com/TheRealKoller/photosort/issues/405), ADR [`0091`](../decisions/0091-ci-ergebnis-abwarten-und-begrenzt-nachbessern.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil der Security-Abschnitt eine Fähigkeit
absichert, die als erste im Ablauf nach jedem Prüferblick selbstständig Code schreibt — die
Klassengrenze des Zulässigen ist die tragende Zusage dieser Story und steht vollständig.

## Ziel

`CLAUDE.md` verlangt einen grünen CI-Lauf, bevor ein Pull Request gemerged wird. Kein
Ablaufschritt stellt dieses Ergebnis fest: `ship-feature` endet am gepushten, finalisierten Pull
Request, `ship-entwurf` am eröffneten. Jede Session schließt die Lücke deshalb selbst und baut
dafür ein eigenes Wegwerf-Skript — jedes Mal neu, jedes Mal anders, ohne gemeinsame Regel für
Zeitgrenzen, Abbruch oder den Fehlerfall.

Daniel soll sich darauf verlassen können, dass ein abgeschlossener Ablauf eine Aussage über den
CI-Stand trägt, statt ihn selbst nachzuverfolgen. Für die Sessions verschwindet ein
wiederkehrender Handgriff samt seiner Streuung.

## User Story

Als Daniel möchte ich, dass der Entwicklungsablauf nach dem Eröffnen eines Pull Requests selbst
feststellt, ob der CI-Lauf grün ist, und bei einem Fehlschlag in begrenztem Rahmen selbst
nachbessert, damit ich den Stand nicht von Hand nachverfolgen muss und keine Session sich dafür
ein eigenes Skript ausdenkt.

## Akzeptanzkriterien

- [ ] Der Ablauf wartet an **genau einem** Punkt je Ablauf — nach dem letzten Push des Laufs, vor
      dem Abschlussbericht — auf das Ergebnis des CI-Laufs.
- [ ] Es gibt dafür genau einen benannten, dokumentierten Weg: zwei Operationen im Katalog
      `github-access`. Kein Ablauf-Skill nennt die Befehlsform, nur die Operations-ID.
- [ ] Eine Eigenentwicklung entsteht nur, wenn belegt ist, dass die vorhandene Werkzeugausstattung
      das Warten nicht abdeckt. Der Beleg ist die Messung in ADR 0091.
- [ ] Ist der Lauf grün, folgt auf den Wartepunkt kein weiterer Ablaufschritt außer dem
      Abschlussbericht, und dieser führt den Ergebniswert.
- [ ] Ist der Lauf rot, bessert der Ablauf nach — ausschließlich was sich lokal mit
      `./scripts/check.sh` und dem Testlauf reproduzieren lässt, und nur an Pfaden, die dieser
      Branch ohnehin geändert hat. **Eine Nachbesserung schwächt nie eine bestehende Zusicherung
      ab:** keine Assertion entfernt oder aufgeweicht, keine Erwartungskonstante eines Tests
      geändert, um ihn grün zu bekommen. Ist die Änderung an der Erwartung der einzige Weg zu
      Grün, hält der Ablauf an und meldet.
- [ ] Höchstens zwei Runden. Die Zahl steht an **genau einer** Stelle und wird von keinem
      Ablauf-Skill wiederholt. Erschöpft heißt anhalten und melden, nie weiterversuchen.
- [ ] Wartefenster 15 Minuten je Lauf, Einzelaufruf 540 Sekunden, Wiederholintervall 30 Sekunden,
      Anlaufschonfrist 120 Sekunden — jede Zahl an genau einer Stelle. Die Befehlszeile trägt
      `--watch`, `--fail-fast`, `--interval 30` und trägt **nicht** `--required`.
- [ ] Je Runde genau ein Commit und genau ein Push.
- [ ] Der Abschlussbericht führt einen fest benannten Block mit drei Feldern: Endstand (einer der
      vier Ergebniswerte), Zahl der Nachbesserungsrunden, Art je Runde. Der Block ist an genau
      einer Stelle definiert; beide Abläufe führen ihn.
- [ ] Der Ergebniswert ist vierwertig und geschlossen: `gruen`, `rot`, `laeuft-noch`,
      `unbestimmt`. `gruen` entsteht ausschließlich aus Exit 0; `rot` nie aus einem Exit-Code
      allein. Jeder nicht zugeordnete Fall ist `unbestimmt` und hält den Ablauf an. Die Zuordnung
      steht an genau einer Stelle; kein Ablauf-Skill definiert sie erneut.

## Datenmodell-Bezug

Keiner. Die Story berührt weder eine Entität noch ein Schema; `docs/architecture.md` bleibt
unverändert.

## Architektur / Umsetzung

Vollständig in ADR [`0091`](../decisions/0091-ci-ergebnis-abwarten-und-begrenzt-nachbessern.md) —
dort stehen die Messung, die Wegwahl, die Ergebnistabelle, die Klassengrenze der Nachbesserung und
die Zahlen. Hier nur, was für die Umsetzung zu tun ist.

**Der vorhandene Weg trägt; es wird nichts gebaut.** Gemessen am 2026-09-12 mit `gh` 2.100.0
(dokumentierte Mindestversion 2.97.0): `gh pr checks [<nummer>] --watch --fail-fast --interval <s>
--json bucket,name,state,workflow` deckt Wiederholintervall, Abbruch beim ersten Fehlschlag und
maschinenlesbares Ergebnis als Optionen eines einzigen Befehls ab. Kein Skript unter `scripts/`,
keine Schleife aus Einzelabfragen, kein eigenes Wiederholverfahren.

**Zwei neue Operationen im Katalog `github-access`**, beide mit `gh` als einzigem Weg:

| ID | Art | Auswertungsgrenze |
|---|---|---|
| `pr-pruefstand-abwarten` | blockierend, `--watch --fail-fast --interval 30`, `timeout 540` | nur der Ergebniswert; die Ausgabe wird verworfen |
| `pr-pruefstand-lesen` | nicht blockierend, `--json` | `bucket`, `name`, `state`, `workflow` |

`pr-pruefstand-abwarten` trägt eine `**Kein \`mcp\`-Weg:**`-Zeile: Ein MCP-Werkzeug ist ein
einzelner Aufruf mit einer Antwort und kann nicht warten; ein aus MCP-Aufrufen gebautes
Wiederholverfahren wäre genau die ausgeschlossene Eigenentwicklung.

**Betroffene Dateien:**

| Datei | Änderung |
|---|---|
| `.claude/skills/github-access/SKILL.md` | zwei neue Katalogeinträge; die Betriebszahlen stehen hier, je an **einer** Stelle |
| `.claude/skills/ship-feature/SKILL.md` | neuer Schritt 9 (Wartepunkt); zwei neue Anker in der Trigger-Liste von Schritt 0 |
| `.claude/agents/developer.md` | neuer Folgeauftrag „CI-Fehlschlag" samt der beiden Anker — **nur hier** definiert |
| `.claude/skills/ship-entwurf/SKILL.md` | neuer Warteschritt hinter dem Push, Nachbesserung in der Hauptsession |
| `scripts/tests/test_ci_warten_verankert.py` | **neu** |
| `scripts/tests/test_github_zugriff_an_einer_stelle.py` | `ERWARTETE_OPERATIONEN` 19 → 21, **und** `LESENDE_OPERATIONEN`, **und** `ERWARTETE_AUSWERTUNGSGRENZE` |
| `scripts/tests/test_ship_entwurf_skill.py` | `ERWARTETE_OPERATIONEN` um den Wartepunkt erweitern |
| `.github/workflows/ci.yml` | Kommentar des Jobs `demo-scripts` nennt wörtlich „19 Operationen" |
| `docs/ai-workflow.md` | neue Zeile in der Schritt-Tabelle (endet heute bei „7b") |
| `specs/architecture/0002-testkonzept.md` | neue Sektion (siehe Teststrategie) |
| `specs/architecture/0003-securitykonzept.md` | neuer Abschnitt unter `## Angriffsflächen` mit B1–B6 und der Klassengrenze als Auflage, dazu **eine** Zeile in der Ankerliste — im selben Pull Request, wie bei jeder vergleichbaren Änderung |

**Zwei Entscheidungen, die vor der Umsetzung fallen mussten:**

1. In `ship-entwurf` wird der Wartepunkt als **neuer letzter Schritt hinter dem Board-Rücklesen**
   eingehängt, nicht davor. Eine Einfügung davor verschöbe die Nummerierung und machte
   `UEBERSCHRIFT_BOARD` in `test_ship_entwurf_skill.py` rot — Kollateralschaden ohne Gegenwert.
   Die Zusage aus ADR 0091 („nach dem letzten Push") bleibt gewahrt, weil das Board-Rücklesen
   nichts pusht.
2. Ein Fix-Diff stößt **keine** erneute Review-Runde an, auch wenn er mehr als Formatierung
   enthält. Getragen wird das von der engen Klasse in AK 5, den Pfadsperren aus M-S2, der
   Selbstmessung aus M-S3 und Daniels Merge.

## UI/UX

Nicht relevant. Die Story betrifft ausschließlich den Entwicklungsablauf (Skill-Dateien,
Katalogoperationen, Wächtertests); es gibt keine Stelle, an der etwas angezeigt oder eingegeben
wird, keine berührte Frontend-Komponente und keine neuen Daten, die dargestellt werden.

## Security

**Einstufung: sicherheitsrelevant** — nicht wegen des Wartens, sondern wegen der
Nachbesserungsschleife. Sie ist die erste Fähigkeit des Ablaufs, die **nach** Review-Runde und
Copilot-Review selbstständig Code ändert und pusht; in `ship-entwurf` gibt es davor überhaupt
keine Perspektivenrunde. Jede Zeile, die sie schreibt, erreicht den Pull Request, ohne dass ein
Prüfer dieses Projekts sie gesehen hat. Die Klasse des Zugelassenen ist deshalb die tragende
Sicherheitszusage dieser Story, nicht die Zahl der Runden. Kein Endpunkt, keine Auth-Änderung,
keine Änderung an der Sichtbarkeit von Daten zwischen den beiden Nutzern.

**B1 — Den Prüfer grün machen statt den Fehler beheben.** Der Job `demo-scripts` fährt `pytest`
über alle Wächtertests unter `scripts/tests/`, der Job `frontend` fährt mit `npm run test -- --run`
auch `frontend/penpot/payload.test.ts`. Ein roter Wächter ist damit die zugelassene Klasse
„fehlschlagender Test" und reproduziert sich lokal einwandfrei — der kürzeste Weg zu Grün ist, den
Wächter oder das von ihm geprüfte Artefakt zu ändern. Betroffen wären namentlich: das Verbot von
`pull_request_target`, die SHA-Pinnung der `release-please`-Action, die Signaturprüfung je
npm-Paketsatz, die Erlaubnisstufen des Operationskatalogs und die statische Verbotsliste der
Penpot-Nutzlast. Gegenmaßnahme: M-S1 bis M-S3.

**B2 — Fremdbeschreibbarer Text aus dem Prüfstand.** `state` und `bucket` sind geschlossene
Wertemengen, `name` und `workflow` nicht: Jede installierte GitHub-App darf einen Check-Run mit
beliebigem Namen anlegen. Der Text landet in einem Kontext, der unmittelbar danach Code ändert und
pusht. Gegenmaßnahme: M-S4 — und die strukturelle: **Welche Klasse von Fix zulässig ist,
entscheidet ausschließlich die lokale Reproduktion, nie der Text eines Checks.**

**B3 — Das falsche Ziel.** Warten, Lesen und der Fix-Push müssen denselben Pull Request meinen,
den dieser Lauf eröffnet hat. Gegenmaßnahme: M-S5.

**B4 — Ein fremd ausgelöster Fehlschlag als Auslöser.** Ein Dritter kann die Checks *dieses* Pull
Requests nicht direkt rot machen: Er hat keinen Schreibzugriff auf den Branch, und die Checks am
Head-Commit entstehen aus den Workflows dieses Repositories. Ein fremder Pull Request erzeugt
Check-Runs an seinem eigenen Head-Commit, nicht an unserem; der Ablauf fragt ausschließlich seine
eigene, selbst gebildete Nummer ab. Was ein Dritter mittelbar erreichen kann, ist eine Störung
gemeinsam genutzter Infrastruktur (Registry, Runner, Image-Bau) — ein solcher Fehlschlag
**reproduziert sich lokal nicht** und hält den Ablauf an. Die lokale Reproduktion ist damit selbst
der Filter gegen fremd beeinflusste Auslöser, nicht nur eine Aufwandsgrenze.

**B5 — Token-Reichweite: kein neuer Scope.** `gh pr checks` liest Check-Runs eines öffentlichen
Repositories mit der vorhandenen Anmeldung; kein `gh auth refresh`, kein zweites Credential, kein
Repo-Secret. Der Aufruf läuft auf dem Entwicklungsrechner, nicht in einem Workflow —
`permissions: contents: read` in `ci.yml` und `permissions: {}` in `pr-titel.yml` bleiben
unberührt, kein Workflow wird geändert. Trägt der Zugang in einer Cloud-Session nicht, scheitert
die Operation auf allen ihren Wegen, das Ergebnis ist `unbestimmt` und der Ablauf hält an; **das
wird nicht durch ein zusätzlich beschafftes Credential behoben.**

**B6 — `--watch` ist eine Betriebseigenschaft, kein Risiko.** Bei 30 s Intervall fallen je
Wartefenster rund 30, je Lauf höchstens rund 90 Abfragen an — weit unterhalb jeder Ratengrenze.
Der Aufruf ist durch `timeout 540` hart begrenzt, seine Ausgabe wird verworfen; damit gelangt aus
dem blockierenden Aufruf weder Fremdtext noch ein Credential in Kontext oder Protokoll. Hier ist
nichts zu härten; der Punkt steht, damit er nicht erneut aufgemacht wird.

**Muss-Kriterien:**

- **M-S1 — Die Nachbesserung ändert nur, was dieser Lauf ohnehin geändert hat.** Zwei getrennte
  Klassen, jede mit eigener Grenze:
  - **Formatierung:** Der Fix-Commit entsteht ausschließlich aus dem Lauf von `scripts/format.sh`,
    ohne eine einzige von Hand geschriebene Zeile. Steht danach im Arbeitsbaum eine Änderung, die
    der Formatierer nicht erzeugt hat, hält der Ablauf an.
  - **Lint, Typen, Tests (inhaltlich):** ausschließlich an Pfaden, die bereits in
    `git diff --name-only origin/main...HEAD` dieses Branches stehen. Ein Fehlschlag in einer
    Datei, die der Branch nicht angefasst hat, ist kein Fix-Fall, sondern ein Befund — anhalten
    und melden.
- **M-S2 — Fünf Pfadklassen bleiben ausgeschlossen, auch wenn der Branch sie selbst geändert
  hat.** Genau das ist der Fall, den M-S1 allein nicht fängt: `.github/**` (nicht nur
  `workflows/`), `scripts/tests/**`, `.claude/**` und `CLAUDE.md`, `design/penpot/**` samt
  `frontend/penpot/payload.test.ts`, sowie Abhängigkeits- und Fixierungsdateien (`package.json`,
  `package-lock.json`, `pyproject.toml`, `uv.lock`, `Dockerfile*`, `docker-compose*.yml`,
  `.env.example`); `specs/**` bleibt ausgeschlossen wie in ADR 0091. Ein roter Wächtertest ist eine
  Aussage über den Arbeitsstand, nie ein zu reparierender Test. Formatierung nach M-S1 bleibt auch
  hier zulässig, weil `ruff format` und Prettier die Bedeutung nicht ändern.
- **M-S3 — Die Selbstmessung steht vor dem Push, nicht in der Absicht.** Vor jedem Fix-Push misst
  der Ablauf den Diff des Fix-Commits selbst (`git diff --name-only` gegen den Stand davor) und
  hält bei einem Treffer aus M-S2 an. In `ship-entwurf` durchläuft der Fix-Commit **Schritt 1 und
  Schritt 2 vollständig** — Pfadmenge, Wächter-Halt, Bilddatei-Halt, Beispieldaten-Prüfung —,
  nicht nur die Pfad-Zulassungsmenge. Ohne das wäre ein rotes `payload.test.ts` durch eine
  zusätzliche `BEZEICHNER_FREIGABEN`-Zeile grün zu bekommen: dieselbe Datei, die die Aufweichung
  verhindern soll, läge im selben Diff, und die Nutzlast läuft in Daniels angemeldeter Sitzung.
- **M-S4 — Prüfstands-Text steuert nichts und gelangt in kein dauerhaftes Artefakt.** Steuernd
  sind allein `bucket` und `state` (geschlossene Wertemengen). `name` und `workflow` sind reine
  Anzeigewerte: Chat-Bericht ja; PR-Body, Issue-Kommentar, Spec-Datei und **Commit-Nachricht**
  nein. Die Commit-Nachricht steht ausdrücklich dabei: Das Repository squasht mit
  `COMMIT_MESSAGES`, jeder Commit-Body wandert in den Merge-Commit auf `main`, in das Changelog
  und in den Body des release-please-Pull-Requests — ein `Closes #NNN` im Namen eines Checks wäre
  dort scharf. Vor der Anzeige werden `Cc`/`Cf`-Zeichen entfernt und auf 200 Zeichen gekürzt;
  bleibt nichts übrig, lautet die Meldung „Check ohne darstellbaren Namen".
- **M-S5 — Beide Operationen bekommen die Nummer aus `pr-erstellen` dieses Laufs**, gegen
  `^[0-9]+$` geprüft. Die argumentlose Form von `gh pr checks` (Auflösung über den aktuellen
  Branch) wird nie benutzt — sie kann in einem Worktree oder nach einem Branch-Wechsel einen
  anderen Pull Request treffen, und der Fix-Push ginge an einen Stand, den der Ablauf nie gemessen
  hat. Gepusht wird nur der Feature-Branch, nie `main`, nie mit `--force`.
- **M-S6 — Der Ergebniswert entsteht am Exit-Code des `gh`-Prozesses selbst.** Exit `124` des
  `timeout`-Aufrufs ist namentlich `laeuft-noch`; jeder nicht namentlich zugeordnete Exit-Code ist
  `unbestimmt` und hält an. Die Ausgabe wird mit `>/dev/null 2>&1` verworfen, **nicht** in eine
  Pipe geleitet — hinter einer Pipe stünde der Exit-Code des letzten Glieds, und ein Fehlschlag
  ginge als Erfolg durch.

**Bewusst getragene Restrisiken:**

- M-S1/M-S2 sind durch den Schritttext und die Selbstmessung aus M-S3 getragen, nicht durch einen
  Test, der den tatsächlich geschriebenen Fix beurteilt. Der Wächtertest prüft die Verdrahtung,
  nicht das Verhalten der Schleife im Fehlerfall.
- Ein Check-Name bleibt fremdbeschreibbar, sobald Daniel eine weitere GitHub-App installiert.
  Gehärtet ist die Darstellung, nicht die Quelle.

## Teststrategie

Eine Ebene: statische Wächtertests unter `scripts/tests/`, Job `demo-scripts`, kein echtes `gh`,
kein Netzwerk, gelesen werden ausschließlich Dateien des Repositories. Kein Backend-, Frontend-
oder E2E-Anteil; das Backend-Coverage-Gate (80 %, Job `backend`, `--cov=photosort`) wird nicht
berührt, `demo-scripts` hat kein Gate — der Abdeckungsanspruch ist diese Liste, keine Prozentzahl.

Zugesichert wird ausschließlich Nachweisbares: die **Kardinalität** des Wartepunkts (genau einmal
je Ablauf), seine **Platzierung** über Zeichenoffsets (nach dem letzten Push, vor dem Bericht), die
**Form der einen Befehlszeile** im Katalog (`--watch`, `--fail-fast`, `--interval 30`,
`timeout 540`, kein `--required`), das **geschlossene Ergebnisvokabular** als Whitelist-Gleichheit
über die Tabellenspalte, die **Einmaligkeit** jeder Betriebszahl im Suchraum `.claude/**`, die
**exakte Feldmenge** von `pr-pruefstand-lesen` und die **leere** Feldmenge von
`pr-pruefstand-abwarten`, sowie die einzige **Definitionsstelle** des Berichtsblocks bei
Anwesenheit in beiden Abläufen.

Nicht zugesichert und deshalb Review-Kriterium: die Laufzeitentscheidungen selbst (AK 3, 5, 8 sowie
die Verhaltenshälften von 4, 9, 10). Ein Prüfer, der aus Prosa herausliest, dass ein unbestimmtes
Ergebnis anhält, wäre grün, weil ein Satz dasteht, und fröre die Formulierung ein. **Keine
Abwesenheitsprüfung auf Prosa** — in Markdown ist der erklärende Satz nicht vom anweisenden zu
trennen; Abwesenheiten werden nur auf Befehls- und Formzeilen geprüft.

Selbstschutz wie bei den übrigen Repo-Konsistenztests: Untergrenze für den Suchraum, Nachweis der
tragenden Dateien im Suchraum, Gegenprobe je Musterfamilie, lautes Scheitern bei leerem Suchraum,
und der Mutationsnachweis **nach** Grün, als Kommentar an der Testdatei — je Muster einmal rot
gesehen, plus zwei geforderte Nicht-Reaktionen: eine erklärende Erwähnung von `gh pr checks` im
Fließtext des Katalogs darf nicht rot werden, und eine dritte Datei, die den Berichtsblock zitiert
statt ihn zu definieren, ebenfalls nicht.

**Rot-Grün-Reihenfolge:**

1. `test_github_zugriff_an_einer_stelle.py`: `ERWARTETE_OPERATIONEN` 19 → 21,
   `pr-pruefstand-lesen` zusätzlich in `LESENDE_OPERATIONEN` und in `ERWARTETE_AUSWERTUNGSGRENZE`
   mit `("bucket", "name", "state", "workflow")` → rot.
2. `test_ci_warten_verankert.py` neu schreiben → rot (Kardinalität zuerst, zählt 0).
3. `test_ship_entwurf_skill.py`: `ERWARTETE_OPERATIONEN` um den Wartepunkt erweitern → rot.
4. Katalogeinträge in `github-access` → Schritt 1 grün.
5. `developer.md` (Folgeauftrag + Anker), dann `ship-feature`, dann `ship-entwurf` → 2 und 3 grün.
6. Mutationsnachweis nach Grün, `docs/ai-workflow.md` und Testkonzept nachziehen,
   `./scripts/check.sh`.

**Mitzuziehen, sonst rot oder still grün:** Nur die Mitgliedschaft in `LESENDE_OPERATIONEN` löst
die Pflicht zur `**Auswertungsgrenze:**`-Zeile aus — steht `pr-pruefstand-lesen` allein in
`ERWARTETE_OPERATIONEN`, ist ein Katalogeintrag ohne Auswertungsgrenze **grün**, und das ist genau
die Fehlerklasse, gegen die diese Datei gebaut ist. Ebenso: der Kommentar „19 Operationen" in
`.github/workflows/ci.yml` und die Schritt-Tabelle in `docs/ai-workflow.md`. Markerzeilen aus
`test_werkzeugwahl_verankert.py` dürfen im neuen Text nicht auftauchen.

**Testkonzept:** `specs/architecture/0002-testkonzept.md` bekommt eine neue Sektion unter
`## Externe CLI-Werkzeuge als dünne Adapter-Schicht (subprocess)`, hinter der Sektion für Spec
0404. Sie führt die zwei neuen Prüfformen, die dort noch nirgends stehen: eine Auswertungsgrenze,
deren Zusage eine **leere** Feldmenge ist, und Whitelist-Gleichheit über eine
Markdown-Tabellenspalte statt über eine ID-Menge. Nicht hinein gehört eine Wiederholung der Zahlen
aus ADR 0091 — das wäre genau die Drift, gegen die AK 6 gebaut ist.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR 0091 angelegt, Messung von `gh` durchgeführt.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Die Story berührt keine sichtbare Oberfläche —
  kein Anzeige- oder Eingabeort, keine Frontend-Komponente, keine darzustellenden Daten.
- `test-engineer` konsultiert (Schritt 3): Teststrategie und geschärfte Akzeptanzkriterien oben.
- `security-engineer` konsultiert (Schritt 3): Security-Abschnitt oben.
- Die Ausschlussliste aus ADR 0091 wurde nach beiden Konsultationen erweitert: Sie verbot nur
  `.github/workflows/**`, während in diesem Repository die halbe Prüferwirkung an Assertions unter
  `scripts/tests/` hängt. `test-engineer` und `security-engineer` fanden die Lücke unabhängig
  voneinander.
- Daniel entschied: Ein Fix-Diff stößt **keine** erneute Review-Runde an, auch nicht bei
  inhaltlichen Änderungen.
- Wartepunkt in `ship-entwurf` als neuer letzter Schritt, keine Umnummerierung.

## Offene Fragen

Keine.

## Out of Scope

- Der CI-Stand **nach** dem Merge. Der gewartete Lauf hängt am Head-Commit des Pull Requests,
  nicht am Merge-Commit auf `main`.
- Das Holen von CI-Protokollen. Nachgebessert wird nur, was sich lokal reproduzieren lässt.
- Der Merge selbst. Er bleibt bei Daniel.
