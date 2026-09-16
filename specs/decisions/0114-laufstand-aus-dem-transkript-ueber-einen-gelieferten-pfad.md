# 0114 - Der Schrittstand wird aus dem Transkript des Laufs gelesen, über einen gelieferten Pfad

**Status:** Accepted
**Datum:** 2026-09-16
**Bezug:** [GitHub-Issue #493](https://github.com/TheRealKoller/photosort/issues/493), Spec 0493

Löst Punkt 4 von ADR [`0093`](./0093-laufstand-in-der-ausgabe-des-laufs-gelesen-nicht-erfragt.md)
in seiner Begründung ab, nicht in seiner Regel. Die Punkte 1, 2, 3 und 5 jener ADR gelten
unverändert: Die Auskunft bleibt ein Lesevorgang, `SendMessage` bleibt als Statuskanal
ausgeschlossen, der Block `## Laufstand` bleibt der einzige Ort des Fortschritts und bleibt
ausschließlich in `.claude/agents/developer.md` definiert, der Arbeitsort bleibt gemessen statt
gemeldet, und die Auskunft bleibt auf den Umsetzungslauf beschränkt.

## Kontext

Der in ADR 0093 gewählte Lesekanal `TaskOutput` trägt nicht. **Gemessen am Bestand (2026-09-16,
Claude Code 2.1.273):** Die Werkzeugbeschreibung beginnt mit `DEPRECATED:` und weist für Läufe
dieser Art ausdrücklich an, das Ergebnis des Agent-Werkzeugs zu verwenden und die Ausgabedatei
nicht roh zu lesen — sie ist kein Ausgabefenster, sondern ein Verweis auf das vollständige
Sitzungstranskript im JSONL-Format. Die Auskunft bekommt damit rohes JSONL statt lesbaren Texts,
die Formprüfung auf den Block scheitert, und sie fällt in den Zweig „Kein abrufbarer
Schrittstand" — also genau in dem Fall in nichts, für den es sie gibt.

Dasselbe Transkript trägt den Schrittstand jedoch vollständig. Am Lauf zu Spec 0486 gemessen: 18
Vorkommen des Blocks, je Zeile ein `timestamp` in ISO-8601, je Zeile ein `version`-Feld mit der
Version der Arbeitsumgebung. Die Datei wird fortlaufend angehängt, während der Lauf läuft. Daneben
liegt eine `meta.json` mit dem `agentType` des Laufs.

## Entscheidung

### 1. Gelesen wird das Transkript, gezielt extrahiert statt roh

Der Schrittstand entsteht aus einer Extraktion über `jq` auf die JSONL-Zeilen des Laufs: die
Textblöcke der Assistenz-Zeilen, daraus das **letzte** formgültige Vorkommen des Blocks
`## Laufstand`, und der `timestamp` eben jener Zeile als Alter des zuletzt gemeldeten
Fortschritts. **Die Datei wird nie als Ganzes gelesen** — sie erreicht Megabytes und liefe dem
Kontext der Hauptsession über; die Arbeitsumgebung untersagt das rohe Lesen an zwei Stellen
ausdrücklich. Bei Verletzung ist die Sitzung, die die Auskunft geben sollte, selbst unbrauchbar.

### 2. Der Pfad wird nie gebildet, sondern entgegengenommen — zwei Wege in fester Reihenfolge

Der Ablageort ist ein undokumentiertes Innenleben der Arbeitsumgebung, und er ist nicht
herleitbar: Für ein und dieselbe Sitzung tragen die beiden beteiligten Verzeichnisbäume
**verschiedene** Projekt-Kennungen — die eine folgt dem Arbeitsverzeichnis der Sitzung, die andere
dem des Laufs. Am Bestand gemessen an einem Lauf in einem Arbeitsbaum. Ein selbst gebildeter Pfad
träfe deshalb regelmäßig daneben.

- **Weg A (Vorrang):** der Wert `output_file` aus dem Ergebnis des Agent-Starts, wie er im Kontext
  der Sitzung vorliegt. Er ist ein Symlink; sein aufgelöstes Ziel ist die Transkriptdatei.
- **Weg B (nur wenn A nicht vorliegt):** eine Suche über die Agenten-Kennung aus `ListAgents` als
  Schlüssel, mit **genau einem** geforderten Treffer. Die Kennung ist von der Sitzung selbst
  bezogen und eindeutig; null oder mehr als ein Treffer ergeben keinen Pfad.

Scheitern beide, gibt es keinen Schrittstand (Punkt 3, Ausgang A). **Ein Pfad wird nie geraten und
nie aus dem Transkript selbst entnommen.**

### 3. Vier getrennte Ausgänge — „kein Block" und „Format verschoben" werden nie verschmolzen

Die Auskunft unterscheidet vier Lagen und benennt die eingetretene:

- **A — kein Pfad.** Weder Weg A noch Weg B liefert einen. Kein Schrittstand.
- **B — Pfad liegt vor, Ziel trägt nicht.** Symlink unauflösbar, Ziel fehlt oder liegt außerhalb
  des Transkriptbaums. **Strukturbefund.**
- **C — Datei liegt vor, die Extraktion fördert nichts zutage.** Keine Zeile parst als JSON mit
  `type` und `timestamp`, oder aus einer Datei nennenswerter Größe kommt **kein einziger**
  Textblock. Ein laufender Umsetzungslauf erzeugt stets Text; nichts zu finden ist deshalb keine
  Aussage über den Lauf, sondern über die Extraktion. **Strukturbefund.**
- **D — alles extrahiert, kein formgültiger Block.** Der Regelfall eines gerade gestarteten Laufs.
  Kein Schrittstand.

**Ein Strukturbefund wird als solcher ausgesprochen, nie als „kein Schrittstand".** Er nennt die
Stufe, an der es brach, und die gemessene Version der Arbeitsumgebung. Grund: Die Lösung hängt an
einem versionsabhängigen Ablageformat; ohne diese Trennung sähe ein Wechsel der Arbeitsumgebung
exakt aus wie ein Lauf, der noch nichts gemeldet hat — und die Auskunft verstummte still.

Jede Auskunft nennt zusätzlich die gelesene Version der Arbeitsumgebung. Sie wird **berichtet,
nicht verglichen**: Ein Abgleich gegen die Messversion schlüge bei jeder Wartungsversion an und
verbrauchte die Aufmerksamkeit, die der Strukturbefund braucht. Die Version ist die Angabe, die
einem Strukturbefund seine Ursache gibt, kein Alarm für sich.

### 4. Der Lauftyp kommt aus der `meta.json`, nicht aus einer Deutung

Die Beschränkung auf den Umsetzungslauf wird am Feld `agentType` der neben dem Transkript
liegenden `meta.json` entschieden: Gleichheit mit `developer`, kein Teilstring-Abgleich. Fehlt die
Datei oder trägt sie einen anderen Wert, wird die Auskunft verweigert.

## Konsequenzen

- `.claude/skills/laufstand/SKILL.md` ersetzt Schritt 2 vollständig; die Sicherheitsauflage zum
  Ausgabefenster bezieht sich künftig auf den Transkriptauszug, und eine Auflage zur Herkunft des
  Pfades kommt hinzu.
- Die Auskunft wird belastbarer, aber nicht unfehlbar: Sie liest ein Artefakt, das die
  Arbeitsumgebung für sich selbst führt und ohne Ankündigung ändern darf. Punkt 3 macht einen
  solchen Wechsel sichtbar; er verhindert ihn nicht.
- `.claude/agents/developer.md` bleibt unberührt. Der Lauf ändert sich nicht, und es entsteht kein
  zweiter Ort, an dem der Fortschritt geführt wird.
- Eine mitlaufende, von sich aus meldende Fortschrittsanzeige ist von dieser Entscheidung nicht
  gedeckt; sie bräuchte einen dauerhaft lesenden Prozess und damit eine eigene Abwägung.
