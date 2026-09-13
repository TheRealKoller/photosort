# 0093 - Der Laufstand steht in der Ausgabe des Laufs und wird gelesen, nicht erfragt

**Status:** Accepted
**Datum:** 2026-09-13
**Bezug:** [GitHub-Issue #449](https://github.com/TheRealKoller/photosort/issues/449), Spec 0449

## Kontext

Der Umsetzungslauf (`developer`) ist ein über das `Agent`-Werkzeug gestarteter Subagent. Sein
Abschlussbericht ist heute seine einzige Äußerung nach außen: Wer den Lauf gestartet hat, sieht
bis dahin nichts — nicht, wie weit er ist, nicht, was noch aussteht, und nicht, ob überhaupt noch
etwas vorangeht.

**Gemessen am Bestand (2026-09-13, Claude Code 2.1.270, Standard-Modell).** Der Werkzeugsatz, den
ein Subagent zur Laufzeit tatsächlich zugeteilt bekommt, ist `Read`, `Write`, `Edit`, `Bash`,
`Skill`. `TaskCreate`, `TaskUpdate`, `TaskGet` und `TaskList` stehen in der `tools:`-Zeile der
Agenten-Dateien, werden dem Subagenten aber **nicht** zugeteilt; eine zweite Probe mit einem
anderen Subagententyp ergab dasselbe. Eine Hauptsitzung hat sie. Daraus folgt zweierlei: Eine
Aufgabenliste des Laufs existiert nicht und kann nicht vorausgesetzt werden, und Schritt 2 der
Agenten-Datei verweist auf Werkzeuge, die dort keine sind.

Was sich von einer Hauptsitzung aus lesen lässt, **ohne den Lauf anzufassen**:

- `ListAgents` — ob der Lauf noch läuft und unter welcher Kennung.
- `TaskOutput` — die letzten Zeichen der laufenden Ausgabe des Laufs; das Fenster ist endlich
  (Vorgabe 32 000 Zeichen).
- `git` selbst — `git worktree list --porcelain` nennt den Arbeitsbaum je Branch, und der Lauf
  committet nach jeder abgeschlossenen Einheit.

## Entscheidung

### 1. Die Auskunft ist ein Lesevorgang, nie eine Frage an den Lauf

Sie entsteht ausschließlich aus den drei Lesewegen oben. `SendMessage` ist als Statuskanal
**ausgeschlossen**: Eine Nachricht landet im Kontext des Laufs und verbraucht einen seiner Züge —
das ist eine Veränderung des Laufs, nicht eine Beobachtung —, und solange er in einem Zug steckt,
antwortet er erst Minuten später. Auf einem Weg, der den Lauf nicht anfasst, ist „keine Antwort"
die Ausnahme; über `SendMessage` wäre sie der Regelfall.

### 2. Ein Ort für den Fortschritt: der Block `## Laufstand` in der Ausgabe des Laufs

Der Lauf gibt seinen Schrittplan als festen Block mit dieser Überschrift aus — jeder Teilschritt
eine Zeile, genau einer davon als der gerade bearbeitete markiert. Ausgegeben wird er an drei
Zeitpunkten: einmal vor dem ersten Rot-Schritt der ersten Einheit (dann steht der Plan
vollständig, der erste Schritt in Arbeit, alle übrigen offen), danach nach jeder abgeschlossenen
Einheit, und zu Beginn jedes Folgeauftrags. Jedes Mal **vollständig**, nie als Änderung zum
vorigen: Gelesen wird immer nur das letzte Vorkommen.

Das Blockformat und die Überschrift sind **ausschließlich** in `.claude/agents/developer.md`
definiert, wie die übrigen Anker dieses Laufs; keine zweite Datei führt eine Kopie.

Es entsteht **kein** weiterer Ort: kein Fortschrittsprotokoll, keine Statusdatei im Arbeitsbaum,
kein Eintrag in der Aufgabenliste der Hauptsitzung. Der Fortschritt steht an genau dieser einen
Stelle — wer zwei Stellen führt, hat bei der ersten Abweichung keine.

### 3. Der Arbeitsort wird gemessen, nicht gemeldet

Maßgeblich ist `git worktree list --porcelain`: gesucht wird der Arbeitsbaum, in dem der
Feature-Branch ausgecheckt ist. Git trägt ihn in demselben Moment ein, in dem `git worktree add`
zurückkommt — der Arbeitsort ist damit bekannt, sobald er feststeht. Arbeitet der Lauf im
Haupt-Checkout, liefert derselbe Befehl diesen. Deshalb meldet der Lauf seinen Arbeitsort
nirgends: Eine gemeldete Angabe wäre eine zweite, alternde Fassung einer Tatsache, die git führt.

Über den so bestimmten Arbeitsort wird auch der gesicherte Zwischenstand gelesen (Commits des
Branches gegen `origin/main`, Sauberkeit des Arbeitsbaums, Alter des letzten Commits).

### 4. Fehlt der Block, sagt die Auskunft genau das

Zeigt `ListAgents` keinen laufenden Umsetzungslauf, oder enthält das abrufbare Ausgabefenster
keinen `## Laufstand`-Block, nennt die Auskunft genau diesen Grund und unterscheidet die beiden
Fälle. Sie trägt dann nur den gemessenen Commit-Stand, ausdrücklich als solchen bezeichnet.

**Ein Commit-Stand wird nie als Schrittstand ausgegeben, und keine frühere Auskunft wird als
aktuelle wiederholt.** Eine veraltete oder erfundene Antwort ist schlechter als keine: Sie sieht
aus wie eine Auskunft und lässt einen steckengebliebenen Lauf für einen laufenden durchgehen.

### 5. Geltungsbereich: ausschließlich der Umsetzungslauf

Die Pflicht aus Punkt 2 gilt nur für `developer`. Kein anderer Agent bekommt sie; die kurzen
Konsultationsläufe (`architect`, `test-engineer`, `security-engineer`, `ux-ui-designer`,
`requirements-engineer`, `research-engineer`) bleiben unberührt. Die Auskunft antwortet für einen
Umsetzungslauf und verweigert sie für jeden anderen Lauf, statt aus dessen Ausgabe etwas
herauszulesen, was dort nicht in fester Form steht.

## Konsequenzen

- `.claude/agents/developer.md` verliert in Schritt 2 den Verweis auf die Task-Werkzeuge und
  bekommt die Pflicht aus Punkt 2 samt Blockformat; die drei Folgeauftrags-Abschnitte bekommen je
  einen Satz dazu, damit der letzte sichtbare Stand nicht „alles fertig" behauptet, während noch
  gearbeitet wird.
- Es entsteht ein neuer Skill in der Hauptsession, rein lesend und ohne GitHub-Zugriff. Er ist die
  einzige Stelle, an der die Auskunft zusammengesetzt wird.
- Das Ausgabefenster ist endlich: Nach einer sehr langen Einheit kann der letzte Block
  herausfallen. Das ist der Fall aus Punkt 4 und keine falsche Auskunft.
- Die `tools:`-Zeilen der Agenten-Dateien versprechen mehr, als die Laufzeit zuteilt. Diese
  Entscheidung ändert daran nichts — sie macht den Ablauf unabhängig davon.
