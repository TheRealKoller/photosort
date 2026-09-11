# 0395 - Dateiarbeit läuft über die dedizierten Werkzeuge; die Shell ist die begründete Ausnahme

**Status:** Implemented (PR-Verweis wird nach dem Eröffnen nachgetragen)
**Erstellt:** 2026-09-11
**Bezug:** GitHub-Issue [`#395`](https://github.com/TheRealKoller/photosort/issues/395), Architekturentscheidung ADR [`0078`](../decisions/0078-dateiarbeit-ueber-dedizierte-werkzeuge-als-vorgabe.md), ADR [`0061`](../decisions/0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md) (Härtungsregel 4.1 — ergänzt, nicht abgelöst), `CLAUDE.md`, `.claude/skills/github-access/SKILL.md`, `.claude/agents/developer.md`, `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`

## Ziel

Die Werkzeugwahl während der Entwicklung folgt heute dem, was gerade am reibungsärmsten ist,
statt einer Festlegung. Der `/insights`-Report vom 2026-09-10 zählt **6.394 Shell-Aufrufe** gegen
**277 lesende, 336 ändernde und 338 schreibende** Aufrufe der dedizierten Werkzeuge. Dateien
werden also weit überwiegend per `sed`, `grep`, Heredoc und Umleitung gelesen und geändert.

**Der Kontextverbrauch ist dabei ausdrücklich nicht das Argument.** Ein gezielter Ausschnitt über
`sed -n '120,180p'` ist sparsamer als das vollständige Einlesen, das eine gezielte Änderung
voraussetzt. Wer die Umkehr mit Sparsamkeit begründete, begründete sie falsch und verlöre die
Begründung beim ersten Nachrechnen.

**Was trägt, ist die Fehlerklasse.** Eine gezielte Änderung über das Änderungs-Werkzeug scheitert
**laut**, wenn die zu ersetzende Stelle nicht eindeutig ist — sie verlangt Eindeutigkeit und
meldet deren Fehlen. Eine Ersetzung über die Shell greift in derselben Lage **still** daneben:
Sie trifft die erste Fundstelle, oder alle, oder keine, und meldet in allen drei Fällen Erfolg.
Dazu kommen die Quoting-Fallen beim Schreiben — ein Heredoc mit nicht maskiertem Inhalt
expandiert `$…` und Backticks, ein `sed`-Ausdruck mit ungeschütztem `&` oder `/` schreibt etwas
anderes als gemeint.

Das Projekt hat diese Lektion an einer Stelle bereits bezahlt: Für Freitext, der in
GitHub-Artefakte gelangt, gilt seit ADR 0061 verbindlich, dass er nie als Zeichenkette in eine
Kommandozeile interpoliert wird, sondern auf dem `gh`-Weg über eine Datei und auf dem `mcp`-Weg
als typisierter Parameter läuft (Härtungsregel 4.1). Diese Einsicht gilt bisher nur punktuell und
sicherheitsbegründet, nicht als allgemeine Arbeitsweise.

Betroffen ist ausschließlich die Arbeitsweise der Entwicklung selbst — für die Nutzer der
Anwendung ändert sich nichts, und es wird keine Zeile Anwendungscode angefasst.

## User Story

Als Stakeholder des KI-getriebenen Entwicklungsprozesses möchte ich, dass Dateien standardmäßig
über die dedizierten Werkzeuge gelesen und geändert werden und die Shell nur dort zum Einsatz
kommt, wo sie sachlich die bessere Wahl ist, damit Änderungen verlässlicher, nachvollziehbarer
und mit weniger stillen Fehlgriffen entstehen.

## Akzeptanzkriterien

Fachlich abgeleitet aus dem Issue-Body von [`#395`](https://github.com/TheRealKoller/photosort/issues/395),
durch `test-engineer` auf Testbarkeit geschärft und durch `security-engineer` an zwei Stellen
verschärft. Kriterien ohne Marker werden automatisiert geprüft; `(Review-Kriterium)` kennzeichnet,
was nur im Review prüfbar ist. Wo ein Kriterium gegenüber dem Issue-Body geschärft, geteilt oder
ergänzt wurde, steht der Grund dabei — die Prüfgegenstände sind dieselben.

### Der eine Ort

- [ ] **(geschärft)** `CLAUDE.md` enthält **genau eine** Überschriftszeile
      `## Werkzeugwahl bei Dateiarbeit`, und sie steht **nach** `## Konventionen` und **vor**
      `## Doku-Pflege`. *Warum geschärft:* „an einer Stelle festgehalten" ist als Formulierung
      nicht entscheidbar; „genau eine Überschrift, an dieser Position in der Reihenfolge der
      `## `-Überschriften" ist es. Die Position ist mitgeprüft, weil der Abschnitt sonst beim
      nächsten Umbau an eine Stelle rutschen kann, an der ihn niemand erwartet — und weil die
      Abschnittsgrenze des Tests an derselben Stelle festmacht.
- [ ] **(neu, Abwesenheitshälfte)** Keine andere Datei unter `.claude/**` und keine weitere
      Stelle in `CLAUDE.md` trägt eine der sieben Markerzeilen. Suchraum ausdrücklich **ohne**
      `specs/` — ADR 0078 und diese Spec zitieren die Markernamen legitim. *Warum neu:* „Ein Ort"
      hat zwei Hälften, und im Issue steht nur die Anwesenheitshälfte. Ohne die
      Abwesenheitshälfte ist die bewusste Abweichung vom `github-access`-Muster (keine
      Wiederholung in den 24 Agenten-/Skill-Dateien) unbewacht — und sie zurückzudrehen ist genau
      der naheliegende „Verbesserungs"-Griff eines späteren Umbaus.

### Die sieben Markerzeilen

- [ ] **(geschärft)** Innerhalb des am nächsten `## ` abgegrenzten Abschnitts steht **jede** der
      sieben Markerzeilen `**Vorgabe:**`, `**Grund:**`, `**Shell ist die bessere Wahl bei:**`,
      `**Bündelung:**`, `**Vorrang:**`, `**Hintergrund-Läufe:**`, `**Unberührt:**` **genau
      einmal**, jeweils zeilenanfangs-verankert und mit nicht-leerem Inhalt dahinter. *Warum
      geschärft:* Form statt Suche über den Block (Lehre aus ADR 0061). „Genau einmal" statt
      „mindestens einmal" aus demselben Grund wie bei den Erlaubnisstufen: Zwei Fassungen
      derselben Aussage sind ein Widerspruch und müssen laut auffallen, statt sich gegenseitig zu
      verdecken. Gemessen am 2026-09-11: `CLAUDE.md` führt heute **null** Zeilen dieser Form —
      der Marker ist trennscharf und kollidiert mit nichts.
- [ ] **(Reihenfolge ausdrücklich nicht geprüft)** Die Reihenfolge der sieben Marker ist frei.
      *Warum:* Sie trägt keine Aussage; eine Reihenfolge-Assertion erzeugte nur Rot bei
      kosmetischen Umbauten. Das ist der Unterschied zur Wege-Reihenfolge in `github-access`, wo
      „`mcp` vor `gh`" die Zusicherung *ist*.
- [ ] **(geschärft)** `**Grund:**` trägt mindestens 80 Zeichen Inhalt. *Warum geschärft:* Bewusst
      eine **schwache** Schranke, ausdrücklich als solche geführt — sie fängt den Platzhalter,
      nicht die schlechte Begründung (dasselbe Konstruktionsprinzip wie
      `MINDESTLAENGE_BEGRUENDUNG` im ADR-0061-Wächter). 80 statt 20, weil diese Zeile zwei Gründe
      tragen muss.
- [ ] **(Review-Kriterium)** Der unter `**Grund:**` genannte Grund ist *der* Grund: laut
      scheiterndes gegen still danebengreifendes Ersetzen, plus die Quoting-Fallen. Ausdrücklich
      **nicht** Kontextsparsamkeit — diese Begründung ist in ADR 0078 als falsch ausgewiesen und
      verlöre beim ersten Nachrechnen. *Warum nur Review:* Ob ein Text eine Begründung trägt oder
      eine falsche, entscheidet kein Muster; ein Wortscan darauf wäre Formulierungspolizei.

### Default, kein Verbot

- [ ] **(geschärft, Form statt Wortlaut)** Auf `**Shell ist die bessere Wahl bei:**` folgen
      unmittelbar mindestens **drei** Listenpunkte. *Warum so geschärft:* Das Issue verlangt, dass
      die Fälle „benannt" sind. Auf die drei konkreten Fälle per Stichwortsuche zu prüfen wäre
      Formulierungspolizei und ginge beim ersten legitimen Umformulieren rot; die *Zahl* der
      benannten Fälle ist dagegen Form und fängt genau den Schaden, um den es geht — dass die
      Gegenfälle bei einem Umbau zu „in begründeten Fällen auch anders" eindampfen und die Regel
      damit still zum Verbot mit Feigenblatt wird.
- [ ] **(Review-Kriterium)** Die drei benannten Fälle decken Versionsverwaltung/Paketmanager/
      Testläufe/Builds, gezieltes Ausschnittslesen großer Dateien und gebündelte
      Mehrschritt-Aufrufe ab, und der Abschnitt formuliert nirgends ein Verbot.

### Härtungsregel 4.1 bleibt unberührt

- [ ] **(geschärft, und durch `security-engineer` verschärft)** Über **absatzweise**
      whitespace-normalisiertem Text und **ausschließlich über dem Block zwischen den
      Zeilenanfängen `**4.1 ` und `**4.2 `** von `.claude/skills/github-access/SKILL.md` sind
      weiterhin zu finden: der tragende Satz
      `Freitext ist immer ein abgegrenzter Wert, nie Teil der Aufrufstruktur`, dazu
      `mit dem Schreib-Werkzeug angelegt`,
      `nie per Shell-Umleitung mit interpoliertem Inhalt` und
      ``Bodies **immer** über `--body-file` ``. *Warum geschärft:* Die zweite Zeichenkette hat im
      Bestand **null** rohe Treffer (nachgerechnet 2026-09-11) — sie steht über einen
      Zeilenumbruch mit zweistelliger Folgeeinrückung verteilt; ohne Normalisierung wäre der
      Wächter beim ersten Umbruch-Wechsel rot geworden, ohne dass sich an der Regel etwas
      geändert hätte, und der naheliegende Reparaturgriff wäre gewesen, die Zusicherung zu
      lockern statt sie zu normalisieren. *Warum zusätzlich blockgebunden:*
      `mit dem Schreib-Werkzeug angelegt` kommt in der Datei **zweimal** vor — einmal in 4.1
      (Zeile 529) und einmal in der Operation `issue-body-schreiben` (Zeile 196). Über die ganze
      Datei gesucht bliebe die Zusicherung grün, **wenn der gesamte 4.1-Block gelöscht würde**.
      Ein Wächter, der die Löschung der Regel, die er bewacht, nicht bemerkt, ist ein Scheintest.
      *Warum der tragende Satz dazugehört:* Die beiden Bullet-Zitate sind die
      `gh`-Konkretisierung; ohne die Regel-Überschrift bliebe ein Umbau möglich, der die
      Konkretisierungen stehen lässt und die Regel selbst umschreibt. *Nachgeschärft am
      2026-09-11 (Copilot-Review), strenger als hier gefordert:* Der tragende Satz wird **an der
      Überschriftszeile** geprüft, nicht als Vorkommen irgendwo im Block. Über den Blockinhalt
      gesucht wäre er durch ein historisches Zitat des alten Wortlauts zu retten, während die
      Überschrift bereits umgeschrieben ist — grün aus dem falschen Grund, bei genau der
      Zusicherung, die am meisten trägt.
- [ ] **(neu)** Die `**Unberührt:**`-Zeile nennt `github-access` und `4.1`. *Warum neu:* Eine
      Abgrenzungszeile, die ihren Gegenstand nicht benennt, grenzt nichts ab. Zwei Literale sind
      die billigste Form, die das entscheidet.
- [ ] **(Review-Kriterium, durch `security-engineer` verschärft)** Die `**Unberührt:**`-Zeile
      stellt 4.1 als **Verbot** dar, nicht als weiteren Default, und schließt die Gegenfälle der
      neuen Konvention dort **namentlich** aus — die Bündelung eingeschlossen. *Warum
      verschärft:* Der Gegenfall „mehrere zusammengehörige Schritte in einem Aufruf" trifft
      `gh`-Aufrufe unmittelbar und wäre die Begründung, mit der jemand ein `--body "…"` inline
      schreibt und dabei subjektiv regelkonform handelt. Eine Zeile, die 4.1 nur *nennt*, deckt
      diese Lesart nicht ab.

### Vorrang und Hintergrund-Läufe

- [ ] `**Vorrang:**` ist vorhanden und nicht leer und nennt den Fall des zur Shell ratenden
      Umgebungshinweises ausdrücklich.
- [ ] **(Review-Kriterium)** Die Konvention wirkt tatsächlich gegen einen solchen Hinweis. *Warum
      nur Review — und warum das ehrlich zu sagen ist:* Es gibt dafür keinen Testgegenstand.
      Siehe den Beleg unter „Bewusst getragene Restrisiken": Der Fall ist beim Erstellen dieser
      Spec real eingetreten.
- [ ] **(geteilt)** `**Hintergrund-Läufe:**` ist vorhanden und nicht leer **und**
      `.claude/agents/developer.md` trägt in `## Schritt 0: Vorbereitung` einen Schritt, der das
      Herstellen des isolierten Arbeitsstands vor der ersten Repo-Änderung verlangt. *Warum
      geteilt:* Das Issue-Kriterium („der Ablauf stellt die Voraussetzung her") hat zwei Träger an
      zwei Orten — die Regel in `CLAUDE.md`, den Ablaufschritt in `developer.md`. Ein Test nur auf
      die Markerzeile ließe das Verschwinden des Ablaufschritts still durchgehen, und genau der
      ist der Teil, der in einem Hintergrund-Lauf tatsächlich greift. Gemessen am 2026-09-11:
      `developer.md` enthält heute **kein** Vorkommen von „Worktree"/„isolierter Arbeitsstand" —
      der Schritt entsteht neu und hat keinen Bestandsschutz, der ihn zufällig grün hielte.

### Bündelung

- [ ] `**Bündelung:**` ist vorhanden und nicht leer.
- [ ] **(Review-Kriterium)** Zusammengehörige Shell-Aufrufe werden tatsächlich gebündelt
      abgesetzt. *Warum nur Review:* dieselbe Klasse wie die Vorrangklausel — kein Artefakt im
      Repository zeichnet auf, in wie vielen Aufrufen eine Frage beantwortet wurde.

### Ausdrücklich nicht Gegenstand

- [ ] **(Nicht-Ziel, benannt)** Die **Befolgung** der Konvention wird nicht geprüft, und es
      entsteht kein Artefakt, das sie zu prüfen vorgibt. *Warum als Kriterium formuliert:* Ein
      Nicht-Ziel, das nur in der ADR steht, wird beim nächsten Review als Lücke gemeldet und dann
      „geschlossen" — mit einer Heuristik über Commit-Muster oder Sitzungsprotokolle. Die wäre
      grün, ohne etwas zu wissen, und damit schädlicher als gar kein Test, weil sie die offene
      Flanke aus ADR 0078 Abschnitt 7 zudeckte.

## Datenmodell-Bezug

Nicht relevant. Es entsteht keine Entität, keine Migration und keine Änderung an
[`docs/architecture.md`](../../docs/architecture.md) — betroffen ist ausschließlich die
Arbeitsweise der Entwicklung, nicht die Anwendung.

## Architektur / Umsetzung

Vollständig festgelegt in ADR [`0078`](../decisions/0078-dateiarbeit-ueber-dedizierte-werkzeuge-als-vorgabe.md);
hier steht das Ergebnis, nicht dessen Begründung.

### Genau ein Ort: ein eigener Abschnitt in `CLAUDE.md`

Die Konvention steht als eigener Abschnitt `## Werkzeugwahl bei Dateiarbeit` in `CLAUDE.md`,
zwischen `## Konventionen` und `## Doku-Pflege`. **Keine andere Datei formuliert die Regel noch
einmal.**

- **Kein Skill:** Ein Skill wird über einen Auslöser geladen. Eine Konvention, die bei *jeder*
  Dateiänderung gilt, hat keinen Auslöser — sie wäre in einem Teil der Läufe nicht geladen, ohne
  dass auffiele, in welchem.
- **Kein Bullet in `## Konventionen`:** Die Regel braucht Begründung, benannte Gegenfälle und
  Vorrangklausel (drei eigene Akzeptanzkriterien). Als Punkt in einer Liste heterogener Einzeiler
  ginge die Struktur unter; eine eigene Überschrift ist zugleich der stabile Anker der statischen
  Prüfung.
- **Keine Wiederholung in den 24 Agenten-/Skill-Dateien** — bewusste Abweichung vom
  `github-access`-Muster: Dort trägt jede Datei eine eigene `**GitHub-Erlaubnisstufe:**`-Zeile,
  *weil sich die Stufe je Datei unterscheidet*. Die Werkzeugwahl ist für alle identisch; 24
  gleichlautende Zeilen transportieren keine Information, und `CLAUDE.md` untersagt Verweise in
  Skills/Agents, die nicht funktional nötig sind.

In andere Dateien wandert nur **Ablauf-Logik, nicht die Regel** — dieselbe Trennung wie bei
`github-access`. Konkret genau eine Stelle: Der `developer`-Agent bekommt in `## Schritt 0:
Vorbereitung` den Schritt, vor der ersten Repo-Änderung den isolierten Arbeitsstand herzustellen.
Das ist ein Ablaufschritt mit einem Zeitpunkt, keine Wiederholung der Begründung.

### Der Abschnitt: sieben Markerzeilen, kein Fließtext daneben

`CLAUDE.md` wird bei jedem Lauf vollständig gelesen; jede Zeile hat laufende Kosten. Der
Abschnitt bleibt deshalb auf das begrenzt, was die Akzeptanzkriterien verlangen. Jeder Marker
deckt genau ein Kriterium:

| Marker | Inhalt |
|---|---|
| `**Vorgabe:**` | Lesen/Ändern/Schreiben von Dateien über die dedizierten Werkzeuge, Suchen über die Such-Werkzeuge |
| `**Grund:**` | gezielte Änderung scheitert **laut** bei Mehrdeutigkeit, Shell-Ersetzung greift **still** daneben; keine Quoting-Fallen (Heredoc-Expansion, `&`/`/` in `sed`) |
| `**Shell ist die bessere Wahl bei:**` | Versionsverwaltung, Paketmanager, Testläufe, Builds; gezieltes Lesen eines Ausschnitts großer Dateien; mehrere zusammengehörige Schritte in einem Aufruf |
| `**Bündelung:**` | zusammengehörige Shell-Aufrufe in einem Aufruf statt als Kette |
| `**Vorrang:**` | gilt auch gegen einen Hinweis der Arbeitsumgebung, der zur Shell rät; eine Abweichung wird benannt |
| `**Hintergrund-Läufe:**` | isolierten Arbeitsstand herstellen, statt auf die Shell auszuweichen |
| `**Unberührt:**` | Härtungsregel 4.1 aus `github-access` bleibt ein **Verbot**, kein Default (Wortlaut siehe `## Security`) |

### Betroffene Dateien, in Umsetzungsreihenfolge

1. `specs/decisions/0078-dateiarbeit-ueber-dedizierte-werkzeuge-als-vorgabe.md` — **liegt
   bereits an** (Abschnitt 7 nach Daniels Entscheidung vom 2026-09-11 geschlossen).
2. `scripts/tests/test_werkzeugwahl_verankert.py` — neu, zuerst rot (TDD).
3. `CLAUDE.md` — neuer Abschnitt, macht 2. grün.
4. `.claude/agents/developer.md` — **ein** Ablaufschritt in Schritt 0.
5. `specs/architecture/0002-testkonzept.md` und `specs/architecture/0003-securitykonzept.md` —
   je ein Abschnitt (Wortlaut in `## Teststrategie` bzw. `## Security`).
6. Diese Spec — Status auf `Implemented` plus PR-Verweis, ganz am Schluss.

**Ausdrücklich nicht berührt**, damit das Review es nicht als Lücke meldet:
[`docs/architecture.md`](../../docs/architecture.md) (Systemarchitektur und Datenmodell ändern
sich nicht), [`docs/setup.md`](../../docs/setup.md) (kein Setup-Schritt, keine
Umgebungsvariable), [`docs/ai-workflow.md`](../../docs/ai-workflow.md) (Workflow und Rollenmodell
ändern sich nicht; die Seite verweist ohnehin auf `CLAUDE.md` als verbindliche Regelquelle),
`.claude/settings.json` (entsteht nicht, siehe unten). Kein Backend-/Frontend-Code, das
Coverage-Gate ist nicht berührt.

### Kein Hook, keine mechanische Durchsetzung

Abgewogen wurde gegen einen nicht-blockierenden `PreToolUse`-Hook in einem eingecheckten
`.claude/settings.json`, der Shell-Aufrufe auf Änderungsmuster absucht. **Daniel hat sich am
2026-09-11 gegen den Hook und für reinen Text entschieden** (ADR 0078, Abschnitt 7). Gründe: Ein
eingecheckter Hook wirkte auf jede Session in diesem Repository, nicht nur auf Agentenläufe;
blockieren dürfte er nicht (das wäre das ausgeschlossene Verbot), und ein Hinweis, der bei jedem
legitimen Einzeiler mit `>>` mitfeuert, wird binnen Tagen überlesen — ein überlesener Wächter ist
schlechter als keiner. Der Preis ist unter „Bewusst getragene Restrisiken" benannt.

## Teststrategie

**Ebene:** ausschließlich statisch, ein neuer Test `scripts/tests/test_werkzeugwahl_verankert.py`
im CI-Job `demo-scripts` (`working-directory: scripts`, kein Coverage-Gate). Reines Dateilesen,
kein Netz, keine MCP-Werkzeuge. Kein Unit-/Integrations-/E2E-Anteil, weil es keinen ausführbaren
Gegenstand gibt: Der „Code" dieses Features ist Text, den ein Modell zur Laufzeit interpretiert.
Aufbau nach dem Vorbild `test_github_zugriff_an_einer_stelle.py` — reine Funktionen über einem
`Mapping[str, str]`-Abbild, dünner Leser daneben, damit jede Zusicherung eine synthetische
Gegenprobe bekommt, ohne das Repository anzufassen.

**Fünf Zusicherungen:**

1. **Verankerung in `CLAUDE.md`:** eine Überschrift, an der richtigen Position; sieben Marker je
   genau einmal, zeilenanfangs-verankert, mit nicht-leerem Inhalt; `**Grund:**` ≥ 80 Zeichen;
   ≥ 3 Listenpunkte nach `**Shell ist die bessere Wahl bei:**`; zwei Literale in
   `**Unberührt:**`.
2. **Anti-Erosion für Härtungsregel 4.1:** absatzweise normalisiert **und auf den Block zwischen
   `**4.1 ` und `**4.2 ` eingeschränkt**; der tragende Satz an der **Überschriftszeile** geprüft,
   die drei `gh`-Konkretisierungen über dem Blockinhalt.
3. **Der Ablaufschritt in `developer.md`, Schritt 0.**
4. **Kein Marker außerhalb des einen Abschnitts** im Suchraum `.claude/**` + `CLAUDE.md`.
5. **Markerzeilen innerhalb eines Codeblocks zählen nicht** — Codefences werden vor dem Parsen
   entfernt.

**Normalisierung — gemessen, nicht angenommen (2026-09-11, zweimal unabhängig nachgerechnet):**

| Zeichenkette | roh | `\s+`→` ` normalisiert |
|---|---|---|
| `mit dem Schreib-Werkzeug angelegt` | 2 | 2 |
| `nie per Shell-Umleitung mit interpoliertem Inhalt` | **0** | 1 |
| ``Bodies **immer** über `--body-file` `` | 1 | 1 |

Normalisiert wird **absatzweise** (`re.split(r"\n\s*\n", …)`), nicht über die ganze Datei: Eine
Normalisierung über Absatzgrenzen hinweg meldete einen in zwei Absätze zerrissenen Satz
weiterhin als vorhanden. Nachgerechnet ergeben beide Varianten am Bestand dieselben Treffer — die
absatzweise ist also gratis strenger. Die Nadeln werden **normalisiert im Test hinterlegt**, nicht
roh aus der Datei kopiert. Der Roh-Null-Befund gehört **nicht** als Assertion gegen die lebende
Datei: Er würde beim ersten legitimen Neuumbruch rot, also genau bei dem Ereignis, das die
Normalisierung absorbieren soll. Die Normalisierung wird stattdessen an **synthetischem** Text
ausgeübt; der Messwert steht als Kommentar am Test, damit die nächste Änderung ihn nachrechnet
statt ihn zu glauben.

**Selbstschutz — vier Assertions, weil vier der fünf Zusicherungen Form- bzw.
Abwesenheitsaussagen sind:**

- **(a) Beide Dateien existieren und sind plausibel groß.** Untergrenzen weit unter dem Ist-Stand
  — `CLAUDE.md` ≥ 3.000 Zeichen (ist: 7.615), `github-access/SKILL.md` ≥ 20.000 (ist: 45.059).
  Ein leerer Suchraum wirft mit eigener Meldung, statt still als Nullbefund durchzugehen.
- **(b) Die Abschnittsgrenze greift wirklich.** Eigener Test: Der extrahierte Abschnitt ist echt
  kürzer als die Datei und enthält `## Doku-Pflege` **nicht**. Ohne diese Assertion zöge der
  Abschnitt bei kaputter Grenze den Rest der Datei in sich und bestünde jede Marker-Zusicherung
  zufällig — hier der wahrscheinlichste stille Defekt.
- **(c) Gegenprobe je Zusicherung an synthetischem Text:** fehlender Marker, doppelter Marker,
  leerer Rest, `**Grund:**` zu kurz, nur zwei Listenpunkte, Nadel über Umbruch+Einrückung (wird
  nach Normalisierung gefunden), gelöschte Nadel (wird nicht gefunden), Marker nur im Codeblock
  (zählt nicht).
- **(d) Mutationsprobe am echten Bestand, nach Grün geführt und dokumentiert.** Der Bestand ist
  nach der Umsetzung sauber, der Test startet also grün — ein Rot-Lauf davor belegt nichts.
  Tragend ist allein: je einen Marker probeweise entfernen und je eine 4.1-Zeichenkette
  probeweise umformulieren, rot sehen, zurücknehmen. Das Ergebnis gehört als Kommentar an den
  Test.

**Bewusst nicht getestet:** die Befolgung der Konvention; der Wortlaut der Gegenfälle; die
Reihenfolge der Marker.

**Bewusste Brüchigkeit, benannt:** Die 4.1-Literale sind eingefrorene Zitate. Eine *legitime*
Neuformulierung von 4.1 macht diesen Test rot und zwingt zum bewussten Nachziehen der Konstante.
Das ist kein Defekt, sondern der Zweck: Genau dieser Moment — 4.1 wird angefasst — ist der, in
dem jemand die Regel mit dem Argument „die neue Konvention deckt das ab" weichschreiben könnte,
und ein rotes CI ist die einzige Stelle, an der das auffällt. Eine Restschwäche bleibt und wird
nicht geschlossen: Normalisierung ist blind für einen Umbruch *innerhalb* eines Wortes; kein
Werkzeug im Projekt bricht so um, das steht als Kommentar am Test.

### Kollisionen mit bestehenden Tests — beim Formulieren des Abschnitts zu beachten

Sonst wird ein *anderer* Test rot:

- **`test_github_zugriff_an_einer_stelle.py` liest `CLAUDE.md` mit.** Der neue Abschnitt darf
  kein `gh <unterbefehl>` und kein `mcp__github__…` enthalten (gemessen: `CLAUDE.md` hat heute
  null Treffer beider Muster). Nennt der `**Shell ist die bessere Wahl bei:**`-Marker einen
  Beispielbefehl zur Versionsverwaltung, muss es `git …` sein, nie `gh …`.
- **Derselbe Test prüft Abschnittszitate:** Jede Zeile, die `github-access` nennt **und** ein
  `Abschnitt „X"` enthält, muss mit einer echten Katalogüberschrift übereinstimmen — die lautet
  wörtlich „Die vier Härtungsregeln, wegunabhängig". Sauberster Ausweg: kein
  `Abschnitt „…"`-Zitat, nur die Regelnummer `4.1`.
- **Derselbe Test scannt auf Messbegriffe** (`GH_TOKEN`, `GITHUB_ACTIONS`, …) — im neuen
  Abschnitt fernzuhalten.
- **`test_verweisnummern_in_markdown.py`:** Nennt ein Link im neuen Abschnitt oder im Test eine
  Nummer im Linktext, muss sie zur Zieldatei passen.
- **`ERWARTETE_STUFEN` in `test_github_zugriff_an_einer_stelle.py`** ist eine eingefrorene
  Tabelle über den `.claude`-Bestand. Diese Story legt keine neue Skill-/Agenten-Datei an; käme
  doch eine dazu, ist die Tabelle mitzuziehen.

### Testkonzept

`specs/architecture/0002-testkonzept.md` wird ergänzt: eine neue `###`-Untersektion am Ende von
`## Repo-Konfiguration & Dokumentation (kein Anwendungscode)`, in der dort etablierten Form
`### Erweiterung für ADR 0078`, plus ein Eintrag unter `## Bekannte Lücken`. Drei Regeln gehen
über diesen Branch hinaus und gehören deshalb ins lebende Dokument:

1. **Ein Wächter, der eine Formulierung aus einer Markdown-Datei zitiert, normalisiert Whitespace
   — absatzweise.** Ein Zitat aus Fließtext ist kein Zitat aus einer Zeile; Markdown darf
   jederzeit neu umbrechen, und ein Wächter, der daran rot wird, wird beim Reparieren gelockert
   statt normalisiert.
2. **Wird neben eine harte Regel eine weichere derselben Materie gestellt, braucht die harte
   einen Anti-Erosions-Wächter** — sonst ist die Abgrenzung nur eine Absichtserklärung.
3. **Bei einem Formtest über einen Markdown-Abschnitt ist die Abschnittsgrenze selbst der
   wahrscheinlichste stille Defekt** und bekommt eine eigene Assertion, nicht nur einen
   Kommentar.

## UI/UX

Nicht relevant. Das Feature hat keine sichtbare Oberfläche, auch keine mittelbare: Es entsteht
keine Anzeige, keine Eingabe und keine neue Information, die irgendwo dargestellt würde.
Betroffen ist ausschließlich die Arbeitsweise der Entwicklung. Der `ux-ui-designer` wurde daher
nicht konsultiert (siehe `## Entscheidungen`).

## Security

**Sicherheitsrelevant, schmal:** kein Anwendungscode, kein Endpunkt, kein Datenmodell, keine
Eingabe von außen, kein Secret, keine Auth-/Berechtigungsänderung, keine neue Abhängigkeit. Der
gesamte Gehalt ist der Erosionsschutz für Härtungsregel 4.1 aus
`.claude/skills/github-access/SKILL.md`.

**Bedrohung.** Neben ein Verbot über Freitext-in-Aufrufstrukturen tritt ein Default über dieselbe
Materie. Der realistische Schadensweg ist nicht die Umgehung von 4.1, sondern ihre spätere
Subsumtion unter den weicheren Default („die neue Konvention deckt das ab"). Zweite, konkretere
Lesart: Der Gegenfall „mehrere zusammengehörige Schritte in einem Aufruf" trifft `gh`-Aufrufe
direkt und wäre die Begründung für ein inline übergebenes `--body "…"`. Der Unterschied ist der
**Schutzzweck**, nicht die Härte: 4.1 schützt vor **fremdem** Text in der Aufrufstruktur, die
Konvention vor einem stillen Fehlgriff in **eigenem** Text. Gleiche Fehlerklasse, unvergleichbarer
Schaden.

**Gegenmaßnahme 1 — Wortlaut der `**Unberührt:**`-Zeile.** Sie nennt 4.1 nicht nur, sondern
grenzt sie ab: Verbot statt Default; keiner der oben genannten Gegenfälle gilt dort, die
Bündelung eingeschlossen; anderer Schutzzweck; eine Lockerung dieses Abschnitts lockert 4.1 nicht
mit. Als Vorlage:

> **Unberührt:** Freitext, der in ein GitHub-Artefakt gelangt (Titel, Bodys, Kommentare), fällt
> nicht unter diesen Abschnitt, sondern unter Härtungsregel 4.1 in `github-access` — nie als
> Zeichenkette in eine Kommandozeile interpoliert, sondern auf dem `gh`-Weg über eine Datei und
> auf dem `mcp`-Weg als typisierter Parameter; der Titel geht auf **beiden** Wegen über eine
> Datei, weil die Prüfung auf unsichtbare Zeichen ein Substrat braucht (Härtungsregel 4.4). Das
> ist ein **Verbot, kein Default**: Keiner der oben genannten Gegenfälle gilt dort, auch die
> Bündelung mehrerer Schritte in einem Aufruf nicht.

**Nachgeschärft am 2026-09-11 (Copilot-Review).** Die ursprüngliche Vorlage lautete „immer über
eine Datei, nie als Zeichenkette in einer Kommandozeile" und behauptete damit mehr, als der
Katalog sagt: Auf dem `mcp`-Weg führt `github-access` 4.1 als **strukturell erfüllt**, der Text
geht dort als typisierter Parameter und nicht über eine Datei. Wegunabhängig ist der harte Kern
(nie in eine Kommandozeile interpoliert) und der Titel-Sonderfall aus 4.4; wegabhängig ist allein
die Form der Übergabe. Die Verbots-Natur und der namentliche Ausschluss der Gegenfälle bleiben
unverändert — die Korrektur betrifft die Genauigkeit, nicht die Härte.

**Gegenmaßnahme 2 — Zuschnitt der Anti-Erosion-Zusicherung.** Siehe `## Teststrategie`,
Zusicherung 2: blockgebunden zwischen `**4.1 ` und `**4.2 `, der tragende Satz an der
Überschriftszeile. Ohne die Blockbindung bliebe die Zusicherung grün, wenn 4.1 vollständig
gelöscht würde — der zweite Treffer von `mit dem Schreib-Werkzeug angelegt` liegt in der
Operation `issue-body-schreiben`. Ohne die Überschriftsbindung bliebe sie grün, wenn die Regel
umgeschrieben und ihr alter Wortlaut als Zitat daneben stehen gelassen würde.

**Nebenbefund für die Umsetzung:** Der Gegenfall „gezieltes Lesen eines Ausschnitts" darf nicht
als Erlaubnis gelesen werden, die mechanische Titelprüfung nach Härtungsregel 4.4 durch Lesen und
Hinsehen zu ersetzen — Bidi-Overrides und Zero-Width-Zeichen sind in jeder Darstellung
unsichtbar, die Prüfung bleibt mechanisch an der Datei. Ein Halbsatz im
`**Shell ist die bessere Wahl bei:**`-Marker („Lesen zum Sichten, nicht als Ersatz einer
mechanischen Prüfung") genügt.

**Bewusst nicht zugesichert.** Der Test erkennt das **Verschwinden** von 4.1, nicht ihre
**Relativierung** durch einen später eingefügten Weichmacher-Halbsatz — ein solcher ließe jeden
Treffer bestehen. Eine Negativliste verbotener Formulierungen wird ausdrücklich **nicht** gebaut:
unvollständig, fehlalarmanfällig, und sie erzeugte genau das Sicherheitsgefühl ohne Absicherung,
das ADR 0078 Abschnitt 7 beim Hook ablehnt. Die Lücke steht im Test-Docstring, nicht nur hier.

**Sicherheitskonzept.** `specs/architecture/0003-securitykonzept.md` wird um einen Abschnitt
„Werkzeugwahl bei Dateiarbeit als weiche Konvention neben der harten Härtungsregel 4.1" vor
`## Bewusst akzeptierte Restrisiken` ergänzt.

**Ausdrücklich nicht sicherheitsrelevant:** die Werkzeugwahl als solche, die Bündelungsregel, die
Vorrangklausel, der Ablaufschritt in `developer.md`, und der Verzicht auf Hook und
`.claude/settings.json` — ein nicht befolgter Default richtet hier keinen irreversiblen Schaden
an.

## Bewusst getragene Restrisiken

- **Die Konvention wirkt allein über Befolgung, und das ist nicht messbar.** Kein Artefakt im
  Repository zeichnet auf, welches Werkzeug eine Zeile geschrieben hat. Der einzige verfügbare
  Messpunkt ist derselbe, der diese Story ausgelöst hat: die Werkzeug-Zählung eines künftigen
  `/insights`-Reports, von Hand gelesen (Ausgangswert 2026-09-10: 6.394 gegen 277/336/338).
  Bleibt die Verteilung nach einigen Wochen unverändert, ist die Entscheidung gegen den Hook
  widerlegt, und er ist die naheliegende Nachfolge — als neue ADR.
- **Gegen einen näher am Zug stehenden gegenteiligen Hinweis hat ein Abschnitt in `CLAUDE.md`
  einen Stellungsnachteil.** Das ist kein hypothetischer Fall: Sowohl die Hauptsession, die diese
  Spec erstellt hat, als auch die beiden konsultierten Fachagenten liefen unter einer
  Umgebungsanweisung, die ausdrücklich verlangte, Dateien über die Shell statt über die
  dedizierten Werkzeuge zu lesen und zu ändern. Der Fall, den die Vorrangklausel adressiert, ist
  damit belegt eingetreten — und **kein Test dieses Features kann ihn sehen**. Diese Zeile ist
  einer von zwei Orten, an denen er aktenkundig wird; der zweite steht unter „Bekannte Lücken" im
  Testkonzept. **Nachtrag aus der Umsetzung (2026-09-11):** Der umsetzende `developer`-Lauf lief
  unter derselben Anweisung. Er hat die Vorrangklausel angewandt, bevor sie im Repository stand —
  Dateiarbeit über die dedizierten Werkzeuge, die Shell für Testläufe, Messungen und `git`, und
  die Abweichung vom Umgebungshinweis zu Beginn benannt statt stillschweigend vollzogen. Das ist
  eine einzelne Beobachtung und keine Messung, aber es ist die erste, die es gibt.
- **Der Test prüft die Verankerung, nicht die Wirkung.** Eine grüne CI ist hier keine Aussage
  über die tatsächliche Werkzeugwahl — derselbe ehrliche Vorbehalt wie bei `test_setup_docs.py`.
- **`CLAUDE.md` wächst um einen Abschnitt.** Das ist die Datei, die bei jedem Lauf vollständig
  gelesen wird; jede Zeile hat laufende Kosten. Die Länge ist deshalb auf das begrenzt, was die
  Akzeptanzkriterien verlangen.

## Entscheidungen

- **Verankerungstiefe (Daniel, 2026-09-11):** nur Text in `CLAUDE.md`, **kein** eingechecktes
  `.claude/settings.json` mit `PreToolUse`-Hook. Vorgelegt, weil die Entscheidung über eine
  technische Detailfrage hinausgeht — ein eingecheckter Hook wirkte auf jede Session in diesem
  Repository, auch auf Daniels eigene. ADR 0078, Abschnitt 7 ist entsprechend geschlossen.
- **`architect` konsultiert (Schritt 1):** Verankerungsort, Dateiliste, Testzuschnitt und ADR
  0078.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Es besteht kein konkret benennbarer Bezug
  zu einer sichtbaren Oberfläche — das Feature ändert ausschließlich die Arbeitsweise der
  Entwicklung, es entsteht keine Anzeige, keine Eingabe und kein darzustellendes Datum.
- **`test-engineer` konsultiert (Schritt 3):** Der statische Test ist nicht-triviales, testbares
  Verhalten unter dem TDD-Regime. Ergebnis: drei ergänzte Zusicherungen (Ablaufschritt in
  `developer.md`, Abwesenheit außerhalb des einen Orts, Codefence-Behandlung), absatzweise statt
  dateiweite Normalisierung, und die Kollisionsliste mit bestehenden Tests.
- **`security-engineer` konsultiert (Schritt 3):** Es besteht ein konkret benennbarer Bezug — die
  neue weiche Konvention steht neben der harten Härtungsregel 4.1 über dieselbe Materie.
  Ergebnis: Die Anti-Erosion-Zusicherung wird blockgebunden statt dateiweit (sie hätte sonst die
  Löschung von 4.1 nicht bemerkt), der tragende Satz kommt hinzu, und die `**Unberührt:**`-Zeile
  schließt die Gegenfälle namentlich aus.
- **Kein Test auf die Befolgung.** Eine Heuristik über Commit-Muster oder Sitzungsprotokolle wäre
  grün, ohne etwas zu wissen, und damit schädlicher als kein Test.

## Offene Fragen

Keine. Die einzige Frage, die über eine technische Detailfrage hinausging, ist oben unter
`## Entscheidungen` beantwortet.

## Out of Scope

- **Mechanische Durchsetzung** der Konvention (Hook, eingechecktes `.claude/settings.json`,
  Berechtigungsregeln) — bewusst verworfen, siehe `## Entscheidungen`.
- **Messung der Befolgung** und jedes Artefakt, das sie zu messen vorgibt.
- **Änderungen an Härtungsregel 4.1 selbst.** Sie bleibt wörtlich wie sie ist; diese Story
  bewacht sie nur zusätzlich.
- **Wiederholung der Konvention in den Agenten-/Skill-Dateien.** Dorthin wandert ausschließlich
  der eine Ablaufschritt in `developer.md`.
- **Anwendungscode jeder Art** — Backend, Frontend, Datenmodell, Migrationen.
