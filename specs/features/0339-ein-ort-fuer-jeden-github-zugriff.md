# 0339 - Ein Ort für jeden GitHub-Zugriff: `github-access` mit Zugangswegen in fester Reihenfolge

**Status:** Accepted
**Erstellt:** 2026-09-06
**Bezug:** GitHub-Issue [`#339`](https://github.com/TheRealKoller/photosort/issues/339), Architekturentscheidung ADR [`0059`](../decisions/0059-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md), ADR [`0057`](../decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md) (Abschnitt 4 erster Satz und Abschnitt 7 teilweise abgelöst), ADR [`0017`](../decisions/0017-github-projects-v2-spec-sync.md) (Abschnitt 1 ergänzt, nicht abgelöst), ADR [`0048`](../decisions/0048-board-operationen-zielzustands-idempotent.md), ADR [`0052`](../decisions/0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md) / ADR [`0056`](../decisions/0056-remote-grenze-gemessene-board-faehigkeit-statt-session-erkennung.md) (Befund Remote-Grenze), Vorgänger-Specs [`0318`](./0318-remote-lebenszyklus-grenze.md) / [`0327`](./0327-board-lebenszyklus-nativ.md), Folge-Story [`#342`](https://github.com/TheRealKoller/photosort/issues/342), `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`, `specs/README.md`

## Ziel

PhotoSorts Entwicklungsablauf greift an vielen Stellen auf GitHub zu — Issues anlegen und
beschreiben, Board-Status und Priorität setzen, Pull Requests eröffnen und verknüpfen, ein
Copilot-Review anfordern. Jede dieser Stellen kennt heute genau **einen** Zugangsweg, und der
trägt in Cloud-Sessions nicht: Dort ist sowohl der GraphQL- als auch der REST-Weg gesperrt,
während dieselbe Session Issues und Pull Requests über einen anderen Weg problemlos liest und
schreibt. Ergebnis ist ein Ablauf, der remote auch an den Schritten scheitert, die eigentlich
gehen würden.

Der Schaden ist wiederkehrend, nicht einmalig: Er fällt in jeder Cloud-Session an, unabhängig
davon, woran gearbeitet wird. Wer eine Story dort beginnt, produziert am Ende eine Liste
„lokal nachzuholen", die zum großen Teil vermeidbar wäre.

Gelöst wird das, indem der GitHub-Zugriff **eine einzige Stelle** bekommt, die pro Operation
mehrere Wege kennt und sie der Reihe nach probiert. Alle Abläufe, `CLAUDE.md` und die Agenten
verweisen dann nur noch dorthin, statt eigene Befehle mitzuführen. Was auch dann nirgends
trägt — die vier Board-Operationen —, bleibt ehrlich als solches benannt und fällt auf den
bestehenden Bericht `## Lokal nachzuholen` zurück.

Die Zusammenführung ist für sich genommen bereits ein Sicherheitsgewinn: Sechzehn Operationen an
sechs Stellen mit je zwei Wegen wären zweiunddreißig Orte, an denen eine Härtungsregel richtig
oder falsch stehen kann; an einem Ort sind es sechzehn Einträge und eine Regel.

## User Story

Als Daniel möchte ich, dass jeder GitHub-Zugriff meines Entwicklungsablaufs aus einer einzigen
Stelle kommt, die selbst weiß, welche Wege es gibt und sie der Reihe nach probiert, damit eine
Story in einer Cloud-Session genauso weit kommt wie lokal und mir am Ende nur das übrig bleibt,
was dort wirklich unmöglich ist.

## Akzeptanzkriterien

Fachlich abgeleitet aus dem Issue-Body von [`#339`](https://github.com/TheRealKoller/photosort/issues/339),
durch `test-engineer` auf Testbarkeit geschärft. Kriterien ohne Marker werden automatisiert
geprüft; `(Review-Kriterium)` kennzeichnet, was nur im Review prüfbar ist. Wo ein Kriterium
gegenüber dem Issue-Body geschärft oder geteilt wurde, steht der Grund dabei — die
Prüfgegenstände sind dieselben.

### Eine Stelle für jeden GitHub-Zugriff

- [ ] Der Skill liegt unter `.claude/skills/github-access/SKILL.md` mit Frontmatter
      `name: github-access`; `.claude/skills/github-board/` existiert nicht mehr.
- [ ] **(geschärft)** Keine Datei unter `.claude/**` außer `.claude/skills/github-access/SKILL.md`
      und keine Zeile in `CLAUDE.md` enthält ein Vorkommen von `gh <unterbefehl>` oder
      `mcp__github__` — an beliebiger Stelle der Zeile, Frontmatter eingeschlossen.
      *Warum geschärft:* „Befehl" gegen „bloße Erwähnung" abzugrenzen ist eine Auslegungsfrage
      und damit nicht prüfbar. „Kein Vorkommen des Musters" ist strenger, maschinell
      entscheidbar und deckt sich mit ADR 0059: Erlaubt bleibt außerhalb des Katalogs
      ausschließlich der **Name** einer Operation.
- [ ] Keine von Git verwaltete Datei verweist noch auf `github-board`.
- [ ] **(geteilt aus „keine Operation geht verloren")** Der Katalog führt genau die 17
      Operations-IDs der ADR-Tabelle, jede genau einmal, jede in kebab-case. Die sechs bisher in
      `ship-feature` beheimateten PR-Operationen sind darunter.
- [ ] **(neu)** Jede unter `.claude/**` verwendete Operations-ID existiert im Katalog.
      Erkennungsraum sind die geschlossenen Präfixe `issue-`, `board-`, `pr-`, `copilot-`. Die
      Gegenrichtung („jede Katalog-Operation wird irgendwo verwendet") wird ausdrücklich **nicht**
      geprüft. *Warum:* Eine vertippte ID ist ein Verweis ins Leere, den kein Ablauf bemerkt, bis
      eine Story daran hängt — genau die Fehlerklasse, die das ID-Vokabular statisch prüfbar
      machen soll.
- [ ] **(Review-Kriterium)** Die Ablauf-Logik der Ablauf-Skills ist vollständig erhalten
      (Reihenfolge, Bedingungen, Auswertung, die Wartezeit vor dem zweiten Lesen der
      PR↔Issue-Verknüpfung, die Copilot-Skip-Regel, die Finalisierung); rein lokales `git` steht
      unverändert dort, wo es heute steht.

### Mehrere Wege pro Operation, in fester Reihenfolge

- [ ] Jede Katalog-Operation nennt ihre Wege als **geordnete** Liste aus dem geschlossenen
      Vokabular `{mcp, gh}`. Wo beide vorkommen, steht `mcp` vor `gh`. Die vier
      Board-Operationen nennen genau `gh`. `pr-reviewkommentar-beantworten` trägt die wörtliche
      Markierung „`mcp` unbelegt".
- [ ] **(neu)** Der Katalog enthält mindestens einen literalen `mcp__github__…`-Hinweis.
      *Warum als Akzeptanzkriterium:* Ohne ein einziges Vorkommen im Repository ist das
      `mcp__github__`-Muster nie ausgeübt; ein Tippfehler darin (`mcp_github_`) bliebe dauerhaft
      grün.
- [ ] **(geschärft, schwacher Wächter)** Unter `.claude/**` und in `CLAUDE.md` kommt keiner der
      enumerierten Messbegriffe vor: `gh auth status`, `gh api rate_limit`, `CODESPACES`,
      `GITHUB_ACTIONS`, `GH_TOKEN`. *Warum geteilt:* „Es wird nicht vorab gemessen und aus keinem
      Umgebungsmerkmal geschlossen" ist als Ganzes eine Laufzeiteigenschaft ohne Testgegenstand;
      prüfbar ist nur die Abwesenheit der bekannten Mittel. Bewusst enumeriert, kein freier
      Wortscan — das wäre Formulierungspolizei.
- [ ] **(Review-Kriterium)** Ein vorhandener Weg wird immer versucht statt beurteilt; ein
      fehlendes Werkzeug wird übersprungen, ohne dass daraus auf die Umgebung geschlossen wird;
      jede Operation beginnt oben an ihrer Leiter (kein Gedächtnis über Operationen hinweg); ein
      Wegwechsel wird nicht berichtet; die Meldung des **zuletzt** versuchten Wegs geht wörtlich
      in den Chat-Bericht und in kein GitHub-Artefakt.

### Was nirgends trägt, bleibt ehrlich benannt

- [ ] Die vier Board-Operationen tragen im Katalog die wörtliche Kennzeichnung, dass sie remote
      auf keinem Weg erreichbar sind, samt Ursache — als Eigenschaft der Umgebung, nicht als
      offene Aufgabe.
- [ ] **(verschärft)** Die vier Ablauf-Skills führen `## Lokal nachzuholen` **und den festen
      Satz** wörtlich. Im Katalog steht je Operation eine Nachhol-Zeile in `gh`-Form, deren
      Feld/Wert-Paare der bestehende Board-Wert-Parser prüft. *Warum verschärft:* Nach dem Umzug
      der Befehlszeile in den Katalog prüft die heutige Assertion nur noch eine Überschrift — und
      eine Überschrift ohne Inhalt besteht sie.
- [ ] **(Review-Kriterium)** Kein Abbruch, keine Zustandsdatei, kein Nachhol-Automatismus, kein
      Ersatzträger; der Abschnitt ist als Normalfall einer Cloud-Session gerahmt.

### Leitplanken gelten wegunabhängig

- [ ] **(geschärft)** Jede `SKILL.md` und jede Datei unter `.claude/agents/` — über den
      entdeckten Bestand (`git ls-files -- .claude`), nicht über eine gepflegte Liste — trägt
      **genau eine** der drei Erlaubnisstufen wörtlich, verglichen gegen eine eingefrorene
      Erwartungstabelle. *Warum geschärft:* „Jede Datei, die GitHub berührt oder plausibel
      berühren könnte" ist nicht maschinell entscheidbar. Über den entdeckten Bestand kann sich
      ein künftig neu angelegter Skill der Einstufung nicht dadurch entziehen, dass niemand an
      die Liste denkt. „Genau eine" statt „mindestens eine", weil zwei Stufen in einer Datei ein
      Widerspruch sind.
- [ ] Die fünf Perspektiven-Skills (`review-architecture`, `review-requirements`,
      `review-security`, `review-tests`, `review-ux`) tragen die Stufe **„kein GitHub-Zugriff"**;
      der `review`-Orchestrator trägt „nur lesend". Alle sechs tragen die wegunabhängige
      Verbotsformel; die alte Aufzählung von `gh`-Befehlsnamen ist verschwunden.
      **Der Absatz ist danach bewusst nicht mehr in allen sechs Dateien wortgleich** — fünf tragen
      die engere Fassung, `review` eine eigene. Das ist kein Redaktionsversehen: Lesen hieße für
      die fünf, fremdbeschreibbaren Text in einen Kontext zu holen, der anschließend Fix-Aufträge
      formuliert.
- [ ] **(erhalten, neuer Pfad)** Die bestehenden Formprüfungen laufen unverändert: `--repo` an
      schreibenden Verben, `--body-file` statt `--body`, `--title "$(cat …)"`, gültige
      Board-Feld/Wert-Paare, Projektnummer `8`, `--owner TheRealKoller`.
- [ ] **(neu verankert)** In `refinement` steht die Ausführungsstelle von `issue-body-schreiben`
      vor der von `issue-titel-schreiben`, und diese vor **jeder** Ausführungsstelle von
      `board-status-setzen` mit Wert `Ready`. Beide Existenz-Zusicherungen stehen mit eigener
      Meldung daneben. Eine Ausführungsstelle nennt ihre ID zeilenanfangs-verankert in Backticks
      (nach optionaler Einrückung, Listenpunkt oder Schrittnummer) — ohne diese Form fiele die
      Prüfung auf eine Textstellen-Suche zurück, die Spec 0288 ausdrücklich verbietet.
- [ ] **(Review-Kriterium)** Die vier Härtungsregeln sind wegunabhängig formuliert und **je Regel**
      konkretisiert; auf dem `mcp`-Weg ist Regel 4.1 als „strukturell erfüllt" bezeichnet, nicht
      als „nicht anwendbar", und die Regeln 4.2/4.3/4.4 sind dort ausdrücklich als offen geführt.
- [ ] `owner`/`repo` stehen auf jedem Weg als Literal im Katalogtext, nie aus einer Antwort,
      einem Issue-Body oder einem Kommentar. Die Ausnahme für die Nummer aus einer Anlege-Antwort
      gilt auf beiden Wegen nur für eine gegen `^[0-9]+$` validierte **Zahl**; die URL wird auch
      auf dem `mcp`-Weg aus der geprüften Zahl gebildet.
- [ ] Jede lesende Operation nennt ihre Feldmenge als Obergrenze der Auswertung. Es gibt im
      Katalog **keine** Operation, die Issue-Kommentare liest; einzige Ausnahme bleibt
      `pr-reviewkommentare-lesen` für die Copilot-Findings am eigenen PR.
- [ ] **(Review-Kriterium)** Für `issue-anlegen`, `pr-erstellen` und `issue-kommentieren` wird
      nach einem Fehlschlag, der die Wirkung nicht eindeutig ausschließt, nicht blind der nächste
      Weg versucht — erst lesend verifizieren, sonst an Daniel melden.

## Datenmodell-Bezug

Keiner. Die Story fasst keine Zeile PhotoSort-Anwendungscode an, berührt weder Entitäten noch
Persistenz noch das Auth-/Sichtbarkeitsmodell und ändert an
[`docs/architecture.md`](../../docs/architecture.md) nichts. Sie liegt vollständig im
Entwicklungsablauf des Projekts — dieselbe Einordnung wie ADR 0037/0043/0046/0052/0056/0057.

## Architektur / Umsetzung

> **Gewählter Ansatz** (ADR [`0059`](../decisions/0059-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md)):
> Der Skill `github-board` wird zu `github-access` und nimmt **jeden** GitHub-Zugriff des
> Entwicklungsablaufs auf — Issue, Board, Pull Request, Copilot-Review, inklusive der sechs
> bisher in `ship-feature` liegenden PR-Operationen. Er bleibt Text; kein Werkzeug, kein Skript.
>
> Er führt einen **Operationskatalog** aus 17 Operationen mit stabilen kebab-case-IDs
> (`issue-anlegen`, `board-status-setzen`, `pr-erstellen`, …). Diese ID ist die einzige Form, in
> der eine andere Datei auf einen GitHub-Zugriff verweist — der Mechanismus, der „genau ein Ort"
> statisch prüfbar macht. Ablauf-Logik (wann, unter welcher Bedingung, wie ausgewertet) bleibt im
> jeweiligen Ablauf-Skill.
>
> Jede Operation nennt ihre **Zugangswege in fester Reihenfolge** (`mcp`, `gh`). Es wird nicht
> vorab gemessen und aus keinem Umgebungsmerkmal auf eine Session-Art geschlossen; ein Weg, dessen
> Werkzeug in der Session gar nicht existiert, wird übersprungen, ohne dass daraus ein Schluss
> gezogen wird; jede Operation beginnt oben an ihrer Leiter; erst wenn alle Wege scheitern, gilt
> die Operation als fehlgeschlagen, und die Meldung des zuletzt versuchten Wegs geht wörtlich in
> den Chat-Bericht.
>
> Die vier **Board-Operationen** haben genau einen Weg und tragen remote auf keinem — benannt als
> Eigenschaft der Umgebung. `## Lokal nachzuholen` bleibt unverändert in Form und Regeln, wird
> aber als Normalfall einer Cloud-Session gerahmt. Kein Abbruch, keine Zustandsdatei, kein
> Ersatzträger.
>
> Die Härtungsregeln werden auf **vier wegunabhängige Regeln** zurückgeführt (Freitext als
> abgegrenzter Wert; steuernde Werte geschlossen und selbst gebildet; dauerhafte Artefakte nur mit
> selbst erzeugtem Inhalt; Titel-Wohlgeformtheit als Werteigenschaft) plus die Formregel 4.5
> („auf jedem Weg das benannte, typisierte Mittel — nie eine selbst zusammengesetzte Anfrage").
> ADR 0017 Abschnitt 1 wird dadurch **ergänzt, nicht abgelöst**: Die Regel war nie eine Aussage
> über `gh`, sondern über die Form eines Aufrufs, und ein MCP-Werkzeug erfüllt genau diese
> Eigenschaft. Jede Skill- und Agenten-Datei spricht eine von drei **Erlaubnisstufen** aus
> (lesend+schreibend / nur lesend / kein GitHub-Zugriff).
>
> **Betroffene Dateien:** `.claude/skills/github-access/SKILL.md` (umbenannt, neu gefasst);
> `.claude/skills/{ship-feature,capture,refinement,spec-writer}/SKILL.md`; die sechs
> Review-Skills; `CLAUDE.md`; die Dateien unter `.claude/agents/`;
> `scripts/tests/{test_issue_befehle_in_skills,test_board_befehle_in_skills,test_board_referenzfreiheit}.py`
> plus ein neuer Test; `docs/setup.md`, `docs/ai-workflow.md`; der erläuternde Kommentar am
> `demo-scripts`-Job in `.github/workflows/ci.yml`.

### Umsetzungsreihenfolge

Jeder Schritt ein eigener Commit, Test zuerst:

1. **Umbenennung mechanisch, isoliert.** `git mv .claude/skills/github-board
   .claude/skills/github-access`, Frontmatter-`name` und `description`, alle Verweise (die vier
   Ablauf-Skills, `docs/setup.md`, die Testkonstante `BEFEHLSSAMMLUNG` in
   `test_issue_befehle_in_skills.py`, Kommentare in `test_board_befehle_in_skills.py`). Zuerst,
   weil ein reiner Rename mechanisch prüfbar ist und alle folgenden Diffs lesbar hält.
2. **Neuer Test „GitHub-Zugriff nur an einer Stelle" (rot).** Suchraum `.claude/**` **und**
   `CLAUDE.md`. Muster generisch `\bgh [a-z][a-z-]*` sowie `mcp__github__`, **ohne**
   Zeilenanfangs-Verankerung. Einzige erlaubte Fundstelle:
   `.claude/skills/github-access/SKILL.md`. Nicht im Suchraum: `docs/`, `specs/`, `CHANGELOG.md`,
   `.github/workflows/` (das `gh pr merge` in `release-please.yml` läuft in Actions, kein
   Session-Zugriff).
3. **`github-access/SKILL.md` neu fassen (grün, Teil 1).** Operationskatalog mit IDs und Wegen;
   die sechs PR-Operationen hereinholen; vier Härtungsregeln plus Formregel; Erlaubnisstufen;
   Lebenszyklus-Tabelle unverändert; `## Lokal nachzuholen` wörtlich unverändert, als Normalfall
   gerahmt.
4. **`ship-feature` entkernen**, dann `capture`, `refinement`, `spec-writer` (grün, Teil 2). Die
   Ablauf-Logik bleibt vollständig, nur die Befehlszeilen weichen Operations-IDs.
5. **Die sechs Review-Skills**, **`CLAUDE.md`**, **die Dateien unter `.claude/agents/`**.
6. **Bestandstests anpassen** (siehe Teststrategie).
7. **`docs/setup.md`, `docs/ai-workflow.md`** und der `demo-scripts`-Kommentar in
   `.github/workflows/ci.yml` — im selben Pull Request.

### Drei Fallen, die vorab benannt sind

- **Die Berichtsvorlagen unter `## Lokal nachzuholen` enthalten heute `gh`-Befehlszeilen** in
  `capture`, `refinement`, `spec-writer` und `ship-feature`. Das kollidiert mit „keine andere
  Datei enthält einen GitHub-Befehl". **Auflösung:** Die Befehlszeile wandert in den Katalog (je
  Operation eine Nachhol-Zeile); die vier Skills behalten Überschrift, festen Satz und Regeln.
- **`test_issue_befehle_in_skills.py::test_refinement_schreibt_den_titel_zwischen_body_und_ready`**
  verliert seinen Gegenstand. **Nicht löschen** — über die Operations-IDs neu verankern. Die
  Reihenfolge ist eine Eigenschaft des Ablaufs und gehört ohnehin dorthin.
- **`test_board_referenzfreiheit.py`** um das Muster `github-board` erweitern (kollidiert nicht
  mit `gh-board` — kein Teilstring). In `docs/setup.md` gibt es **keine** `gh-board.py`-Altlast
  mehr nachzuziehen; sie ist mit ADR 0057 / Spec 0327 entfallen. Wer dort danach sucht, sucht
  vergeblich.

### Was `developer` nicht selbst kann

Er hat als Subagent die `mcp__github__*`-Werkzeuge nicht und kann keinen Werkzeugnamen
verifizieren. Deshalb ist der `mcp`-Weg **auf Operationsebene** normiert; exakte Werkzeugnamen
stehen nur als „am 2026-09-06 beobachtet"-Hinweis daneben.
`pr-reviewkommentar-beantworten` ist ausdrücklich als „`mcp` unbelegt" zu führen und **nicht** mit
einem geratenen Namen aufzufüllen.

## Teststrategie

Vollständige Herleitung und die daraus abgeleiteten allgemeinen Regeln:
[`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md), Abschnitt
„Erweiterung für ADR 0059".

**Kernaussage: Die tragende Zusicherung dieser Story ist eine Abwesenheit — und ein
Abwesenheits-Test ist per Konstruktion grün, wenn er nichts sieht, auch dann, wenn er nichts sehen
*kann*.** Der Aufwand liegt deshalb nicht im Muster, sondern im Selbstschutz.

**Ebene: ausschließlich Repo-Konsistenztests** (`scripts/tests/`, CI-Job `demo-scripts`). Kein
Unit-/Integrations-/E2E-Test, weil kein ausführbarer Code entsteht. Bauform durchgängig der
bewährte Zweischnitt: reine Funktion auf übergebenem Text-/Datei-Abbild plus dünner Leser für den
echten Repo-Zustand; 0 und >1 Treffer sind laute Fehlerfälle mit eigener Meldung.

| Test | Deckt ab |
|---|---|
| Abwesenheits-Test `gh <unterbefehl>` / `mcp__github__` über `.claude/**` + `CLAUDE.md` | „Genau ein Ort", Wegfall der alten Befehlsaufzählung in den Review-Skills und in `CLAUDE.md` |
| Referenz-Freiheit erweitert um `github-board` | Umbenennung vollständig nachgezogen (erfasst auch `docs/setup.md`) |
| Katalog-Form: 17 IDs, geordnete Wege ⊆ `{mcp, gh}`, `mcp` vor `gh`, vier Board-Operationen mit genau einem Weg | „Keine Operation geht verloren", „feste Reihenfolge" |
| Referentielle Integrität: jede verwendete ID existiert im Katalog (einseitig) | Vertippte Verweise ins Leere |
| Erlaubnisstufen: jede Skill-/Agenten-Datei genau eine Stufe, gegen eingefrorene Tabelle | „Jede Stelle sagt, was sie darf" |
| `## Lokal nachzuholen` **plus fester Satz** wörtlich in vier Skills | Fehlschlag bleibt sichtbar, auch nachdem der Befehl ausgezogen ist |
| Bestehende Formprüfungen (`gh issue`, `gh project item-edit`), neuer Pfad | Härtungsregeln am `gh`-Weg, unverändert |
| Reihenfolge Body → Titel → `Ready`, über Ausführungsstellen von IDs | Ablauf-Gate aus Spec 0288, neu verankert |

**Zwei Korrekturen an der ursprünglichen Testvorgabe, beide am Bestand belegt:**

- **Keine Zeilenanfangs-Verankerung.** Die Verankerung existiert, um in einer Datei, in der
  Befehle *legitim* sind, Aufruf von Erwähnung zu trennen. In einem Raum, in dem null Vorkommen
  legitim sind, ist sie ein Loch — nachweisbar an `capture/SKILL.md` (Prosa, die mit einem
  Befehl in Backticks *beginnt*) und an der Befehlsaufzählung im Schreibverbots-Absatz der sechs
  Review-Skills.
- **Generisch `\bgh [a-z][a-z-]*` statt der Vierer-Liste.** `gh auth status` ist exakt die von
  ADR 0059 verbotene Vorabmessung und entginge einer Aufzählung aus `gh issue|gh pr|gh
  project|gh api`. Am Bestand gemessen: fünf Befehlsformen, 88 Fundstellen in 13 Dateien,
  **null** Fließtext-Fehlalarme (deutscher Fließtext schreibt die CLI als `` `gh` `` mit
  anliegendem Backtick). Regex-Falle derselben Klasse wie `--body`/`--body-file`: `gh pr` ist
  Präfix von `gh project`; eine Alternation ohne `\b` etikettiert jeden Board-Befehl als
  PR-Befehl. Der Messwert gehört als Kommentar an den Test, damit die nächste Änderung ihn
  nachrechnet statt ihn zu glauben.

**Dreifacher Selbstschutz** — damit der Test nicht stillschweigend nichts mehr prüft:

1. Plausible Größenordnung des Suchraums (Mindestzahl gelesener Dateien) — fängt den Totalausfall
   der Aufzählung.
2. Der erlaubte Ort liegt nachweislich **im** Suchraum, als Pfad-Assertion. Ebenso: `CLAUDE.md`
   liegt **nicht** unter `.claude/` und braucht einen zweiten Aufzählungszweig plus eigene
   Anwesenheits-Assertion — der wahrscheinlichste Defekt dieses Tests ist ein stillschweigend
   nicht mitgelesenes `CLAUDE.md`.
3. Gegenprobe **je Musterfamilie**. Eine Gegenprobe, die nur das `gh`-Muster belegt, sagt über
   `mcp__github__` nichts.

**Rot-Nachweis:** Der Abwesenheits-Test ist auf `main` durch den Bestand trivial rot — das ist
kein aussagekräftiger Nachweis. Der tragende Nachweis kommt **nach** Grün als Mutationsprobe je
Musterfamilie: je eine `gh pr view`-Zeile und ein `mcp__github__…`-Token probeweise in einer
Review-Skill-Datei, beide müssen den Test rot färben; danach zurücknehmen.

**Coverage-Gate: nicht berührt.** Der `backend`-Job misst `backend/src/photosort`; weder
`backend/pyproject.toml` noch `scripts/pyproject.toml` beziehen `scripts/` ein, und der
`demo-scripts`-Job hat kein Gate. Die Story fasst keine Zeile Anwendungscode an.

**Der benannte Verlust:** Nach dieser Story läuft der Alltag über den `mcp`-Weg, für den es im
Repository keine prüfbare Form gibt, während die statisch geprüften `gh`-Formen zum selten
gelaufenen Rückfallweg werden. Die Formprüfungen werden deshalb **nicht** mit dem Argument
abgebaut, sie prüften einen Nebenweg — ihr Wert steigt, je seltener der Weg läuft.

## UI/UX

Nicht relevant. `ux-ui-designer` nicht konsultiert (spec-writer, Schritt 2): Die Story berührt
ausschließlich Skill-, Anweisungs- und Dokumentationsdateien des Entwicklungsablaufs. Es gibt
keine anzeigende oder eingebende Stelle, keine neuen darzustellenden Daten und keine berührte
Frontend-Komponente — kein konkret benennbarer Anhaltspunkt für eine sichtbare Oberfläche.

## Security

Sicherheitsrelevant, kein Blocker. Vollständige Herleitung in
[`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md), Abschnitt
„Ein zweiter Zugangsweg zu GitHub: `github-access` mit `mcp` vor `gh`".

**Neu sind drei Dinge, und nur das erste ist eine Verbesserung:** die Zusammenführung an einem
Ort, ein Schreibweg ohne Shell, ein zweiter Client mit eigener, nie gemessener Anmeldung — und ein
Leseweg, der von sich aus mehr Felder liefert als die heutige `--json`-Verengung.

**„Strukturell erfüllt" gilt je Regel, nie je Weg.** Auf dem `mcp`-Weg ist **allein** Regel 4.1
strukturell erfüllt; 4.2, 4.3 und 4.4 sind dort unverändert offen und schlechter abgesichert als
heute. Die Zuordnung „welche Regel ist auf welchem Weg wodurch erfüllt" steht je Regel im Katalog,
nie als Sammelaussage über den Weg — „nicht anwendbar" wäre die erste Stufe, auf der eine
Sicherheitsregel verschwindet.

**Bedrohung 1 — die Wahl des falschen Ziels (Regel 4.2), und ein sicherer Vorgabewert entfällt.**
Eine Issue-Nummer aus fremdem Text schickt einen Schreibzugriff an ein fremdes Issue, über ein
MCP-Werkzeug genauso zuverlässig wie über eine Kommandozeile, nur ohne Metazeichen-Alarm; das
Repository ist öffentlich, ein Fehlgriff ist nicht zurücknehmbar. Neu: `gh issue edit <NNN>` ohne
`--repo` wirkt auf das Repository des Arbeitsverzeichnisses, fällt bei einem Fehler in der
Repo-Angabe also auf das *richtige* Repo zurück. Ein MCP-Werkzeug kennt kein Arbeitsverzeichnis —
`owner`/`repo` sind Pflichtparameter ohne Rückfallwert. Gegenmaßnahmen als Akzeptanzkriterien
oben.

**Bedrohung 2 — Prompt-Injection über den Leseumfang: der schwerwiegendste neue Punkt.** Die
heutige Verengung ist strukturell: `gh pr view --json closingIssuesReferences,baseRefName` liefert
weder Titel noch Body noch Autor, `gh issue view --json body,title,labels,state` liefert keine
Kommentare — fremdbeschreibbarer Freitext entsteht im Agenten-Kontext gar nicht erst. Ein
MCP-Lesewerkzeug liefert das Objekt mit mehr Feldern in einem Aufruf; übrig bleibt eine
Auswertungsgrenze, die erst wirkt, wenn die Daten schon im Kontext sind. **Das ist ein Rückschritt
und wird nicht als gleichwertiger Ersatz ausgegeben** (siehe „Bewusst getragene Restrisiken").

Was stattdessen trägt: Der geschlossene Katalog wird zur Durchsetzungsstelle für „nie Kommentare"
— es gibt keine Operation, die Issue-Kommentare liest, und keine andere Datei darf einen
GitHub-Zugriff enthalten. Aus einer Feldliste wird damit eine Eigenschaft des Vokabulars, statisch
prüfbar und in der Sache **stärker** als bisher. Entlastend, aber nicht freisprechend: Die
PR-Leseoperationen laufen im Ablauf ausschließlich gegen den eigenen, selbst eröffneten Pull
Request, dessen Titel und Body der Ablauf selbst geschrieben hat.

**Bedrohung 3 — Wohlgeformtheit (Regel 4.4) wird schlechter prüfbar, nicht gleich gut.**
Bidi-Overrides und Zero-Width-Zeichen sind genau die Klasse Zeichen, die ein Modell im eigenen
Kontext nicht zuverlässig sieht; eine Datei ist das einzige Substrat, an dem sich die Prüfung
mechanisch ausführen ließe. Der zu schreibende Titel wird deshalb **auch auf dem `mcp`-Weg** als
Datei materialisiert und unmittelbar vor dem Aufruf daran geprüft. Preis: ein
Dateischreibvorgang, den der Transport nicht bräuchte.

**Bedrohung 4 — zwei Wege, ein Artefakt: Duplikat beim Wegwechsel.** Bei einem *mehrdeutigen*
Fehlschlag einer anlegenden Operation kann der Schreibzugriff dennoch angekommen sein; der zweite
Weg erzeugt dann ein zweites öffentliches, nicht zurücknehmbares Artefakt. Mit genau einem Weg gab
es diese Klasse nicht. Gegenmaßnahme als Akzeptanzkriterium oben; für die zielzustands-idempotenten
Operationen (ADR 0048) bleibt der zweite Versuch der Normalfall, und ein *eindeutiger* Fehlschlag
(403, „Werkzeug existiert hier nicht", Authentifizierungsfehler) schließt die Wirkung aus.

**Bedrohung 5 — Fremdtext in dauerhaften Artefakten hat eine zweite Quelle (Regel 4.3).** Eine
MCP-Fehlermeldung ist genauso Fremdtext wie `gh`-stderr; neu ist allein, dass pro fehlgeschlagener
Operation **zwei** Fehlertexte anfallen. In `## Lokal nachzuholen` gelangt weiterhin ausschließlich
selbst erzeugter Inhalt. „Die Meldung des zuletzt versuchten Wegs geht wörtlich in den
Chat-Bericht" bleibt damit vereinbar, solange „Chat-Bericht" wörtlich gemeint ist.

**Schreibverbot der Review-Skills: strikt stärker — durchgesetzt von nichts.** Die heutige
Aufzählung von `gh`-Befehlsnamen erlaubt versehentlich jedes MCP-Schreibwerkzeug; die
wegunabhängige Fassung schließt das. Zwei Einschränkungen werden ausgesprochen statt in der
stärkeren Formulierung untergehen zu lassen: Der statische Test sieht nur **Dateiinhalte** — ein
Werkzeugaufruf, dessen Name in keiner Datei steht, entzieht sich ihm vollständig; und es gibt im
Repository keine `.claude/settings.json`, also keine technische Berechtigungsschranke. Die
Erlaubnisstufen sind reine Laufzeitdisziplin. Deshalb tragen die fünf Perspektiven-Skills die
engere Stufe „kein GitHub-Zugriff" statt „nur lesend" — ein Recht, das keiner von ihnen braucht,
wird auch nicht eingeräumt.

**„Subagenten haben keinen GitHub-Zugriff": beobachtet, nicht zugesichert.** Der Befund stammt aus
der Client-Konfiguration der Umgebung; es gibt keine `.mcp.json`, das Repository kann den Zustand
weder herstellen noch prüfen noch seine Änderung bemerken. Als Verteidigung in der Tiefe
willkommen, als tragende Zusicherung unbrauchbar. Tragende Kontrolle bleibt die Konvention in den
Agenten-Dateien.

**Berechtigungen: ein zweiter Pfad, den dieses Projekt nie gemessen hat.** Die Scope-Messung des
Projekts deckt allein den `gh`-Weg ab; die MCP-Werkzeuge sprechen unter eigener Anmeldung mit
GitHub, deren wirksamer Umfang aus dem Repository nicht ersichtlich und potenziell breiter ist als
der Ablauf braucht. Kein neues Secret im Repository, kein Blocker (derselbe Kontoinhaber, dieselbe
Vertrauensbasis) — als bekannte Lücke geführt.

**Trigger-Blindfleck, dritter dokumentierter Fall.** Der Diff dieser Story liegt vollständig unter
`.claude/**`, `scripts/tests/**`, `specs/**`, `docs/**` und `CLAUDE.md`; die Trigger-Tabelle in
`.claude/skills/review/SKILL.md` nennt nur Pfade unter `backend/`, `frontend/`, `.env.example`,
`.github/workflows/**` und Docker-Compose-Netzwerkkonfiguration. Der `review-security`-Trigger löst
also nicht aus, obwohl der Diff die Härtungsregeln des GitHub-Zugriffs vollständig umschreibt.

**Unverändert:** kein PhotoSort-Anwendungscode, keine Foto-/Projekt-/Auth-Daten, kein Effekt auf
das Auth-/Sichtbarkeits- oder Datenmodell, kein neues Repo-Secret, keine neue Abhängigkeit, kein
neues Netzwerkziel (weiterhin nur github.com), keine Änderung an der
`approved-for-agent`-Freigabepolitik. Fehlt die MCP-Anbindung, verhält sich der Ablauf exakt wie
heute.

## Bewusst getragene Restrisiken

Beide Punkte sind Daniel am 2026-09-06 im Chat mit dem jeweiligen Preis vorgelegt und von ihm
entschieden worden:

1. **Der Alltagsweg ist der ungeprüfte.** `mcp` vor `gh` bedeutet, dass die statischen
   Formprüfungen ab jetzt den selten gelaufenen Rückfallweg bewachen. Entschieden gegen die
   Gegenoption „`gh` zuerst", die in jeder Cloud-Session je Operation einen sicher scheiternden
   Aufruf gekostet hätte.
2. **Der Leseumfang ist nicht mehr strukturell verengbar.** Die PR-Leseoperationen folgen wie alle
   anderen `mcp` vor `gh`; die Auswertungsgrenze im Katalog ersetzt `--json` **nicht**
   gleichwertig. Entschieden gegen die Gegenoption, `pr-verknuepfung-lesen` und
   `pr-reviewstand-lesen` als benannte Ausnahmen `gh` zuerst gehen zu lassen — das hätte für diese
   zwei Operationen genau den Preis wieder eingeführt, der unter Punkt 1 abgelehnt wurde.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR [`0059`](../decisions/0059-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md)
  angelegt. Zwei Punkte hat er Daniel vorgelegt statt sie selbst zu entscheiden (Reihenfolge der
  Wege; Ablöseform gegenüber ADR 0057); beide wurden am 2026-09-06 wie empfohlen bestätigt.
- `ux-ui-designer` nicht konsultiert (Schritt 2): kein konkret benennbarer Bezug zu einer
  sichtbaren Oberfläche — die Story berührt ausschließlich Skill-, Anweisungs- und
  Dokumentationsdateien des Entwicklungsablaufs.
- `test-engineer` konsultiert (Schritt 3): Testkonzept um die Sektion „Erweiterung für ADR 0059"
  ergänzt, zwei Testvorgaben korrigiert (Verankerung, Musterumfang), zwei bekannte Lücken
  eingetragen.
- `security-engineer` konsultiert (Schritt 3): Sicherheitskonzept um den Angriffsflächen-Abschnitt
  „Ein zweiter Zugangsweg zu GitHub" ergänzt. Vier Punkte, die in ADR 0059 fehlten, sind
  nachgetragen; zwei Trade-off-Fragen gingen an Daniel (siehe „Bewusst getragene Restrisiken").
- **Abweichung von ADR 0057, Abschnitt 4/7:** per Teil-Vermerk statt vollständigem `Superseded`.
  Die dafür nötige Abstufung ist in [`specs/README.md`](../README.md) als Konvention
  festgeschrieben, mit einer Zulässigkeitsschranke — Teil-Vermerk nur, wenn der abgelöste Teil
  nicht der Kern ist und die überwiegende Mehrheit der Abschnitte weitergilt.
- **Abweichung von der Erlaubnisstufen-Tabelle in ADR 0059:** Die fünf Perspektiven-Skills tragen
  „kein GitHub-Zugriff" statt „nur lesend", nachdem `security-engineer` geprüft hat, dass keiner
  von ihnen heute einen GitHub-Zugriff ausführt.
- **Branch-Abweichung:** Diese Spec entsteht auf `claude/refinement-339-mp6has` statt auf dem vom
  `spec-writer`-Ablauf vorgesehenen `feature/0339-…`, weil die Session-Vorgabe diesen Branch
  verbindlich setzt.
- **Board-Status nicht gesetzt.** Der Statuswechsel auf `In Progress` (Schritt 0) ist in dieser
  Cloud-Session gescheitert — genau der Fall, den diese Story beschreibt.

## Offene Fragen

Keine. Die vier Punkte, die über eine technische Detailfrage hinausgingen, sind am 2026-09-06 mit
Daniel geklärt: Zuschnitt des Skills, Skill-Name, Reihenfolge der Wege, Ablöseform gegenüber
ADR 0057, Leseumfang und Durchsetzung der Erlaubnisstufen.

## Out of Scope

- **Kein eigenes Werkzeug und kein Skript** für den GitHub-Zugriff. Der Skill bleibt Text, den die
  Session liest. ADR 0057 / Spec 0327 haben `scripts/gh-board.py` bewusst gelöscht; an seine
  Stelle tritt kein neues Werkzeug.
- **Board-Operationen werden nicht cloud-fähig gemacht.** Projects V2 spricht ausschließlich
  GraphQL, GraphQL ist in Cloud-Sessions gesperrt, und die MCP-Werkzeuge bieten dafür keine
  Operation an. Es wird auch kein Ersatzträger (Labels, Issue-Kommentare) nachgebaut.
- **Die Installation der Claude-GitHub-App** auf Daniels Account ist ein Handgriff auf GitHub, kein
  Bestandteil dieser Story. Der Skill muss auch dann mehrere Wege kennen, wenn dadurch ein
  weiterer Weg hinzukäme.
- **Der native Board-Lebenszyklus** (welcher Übergang von GitHub selbst ausgelöst wird und welcher
  von einer Session) bleibt unverändert.
- **Eine technische Durchsetzung der Erlaubnisstufen** über Berechtigungsregeln in einer
  `.claude/settings.json` — eigene Folge-Story
  [`#342`](https://github.com/TheRealKoller/photosort/issues/342).
- **Der Trigger-Blindfleck** der Perspektiven-Tabelle in `review/SKILL.md` wird hier nur als
  dritter dokumentierter Fall festgehalten, nicht behoben.
