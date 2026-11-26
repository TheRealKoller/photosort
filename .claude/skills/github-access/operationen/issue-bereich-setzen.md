## `issue-bereich-setzen` — den Bereich eines Issues setzen

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Bereichsvorrat (geschlossen):** `bereich:frontend`, `bereich:backend`, `bereich:pipeline`, `bereich:ai-workflow`, `bereich:design`, `bereich:infra`
**Normalisierung (wegunabhängig, vor jeder Mengenbildung):** Aus der gelesenen Label-Menge wird
ausschließlich `labels[].name` verwendet. Ein Label ist in der Antwort ein **Objekt**
(`{id, name, description, color}`), keine Zeichenkette; die Präfix-Subtraktion unten ist über
Objekte nicht ausführbar, und auf dem `mcp`-Weg — der die vollständige Menge zurückschreibt —
fielen Nicht-Bereichs-Label dabei weg. Geschrieben wird ebenfalls über Namen.
**Aufrufer:** `refinement` Schritt 6 und der einmalige Nachlauf über die offenen Issues (Spec
0259). Sonst niemand.
**`mcp`:** das GitHub-MCP-Werkzeug, das die Label eines Issues setzt; die Label gehen als
typisierte Liste. Werkzeugname nicht notiert.
**`gh`:**

```bash
gh issue edit <NNN> --repo TheRealKoller/photosort --add-label bereich:frontend --remove-label bereich:backend
```

**Gegenstand ist der Zielzustand der Label-Menge, nicht ein Zuwachs.** Eine Nachschärfung, die den
Bereich korrigiert, muss den falschen entfernen, sonst weist der Board-Filter das Issue dauerhaft
unter einem Bereich aus, den es nicht mehr betrifft. Die beiden Wege erreichen denselben
Zielzustand verschieden: `gh` additiv und subtraktiv über `--add-label`/`--remove-label`, `mcp`
durch Übergabe der **vollständigen** Menge. **Auf dem `mcp`-Weg gehört `bug` deshalb mit in den
Aufruf**, sonst fällt es still weg.

**Die Schreibmenge wird mechanisch gebildet:** gelesene Menge desselben Laufs — als Namen nach der
Normalisierung oben —, minus aller Namen mit dem Präfix `bereich:`, plus der vorgesehenen Werte.
Kein Label wird erfunden, keines durch Auslassen entfernt. **Der übergebene Wert wird vor dem
Aufruf gegen das Vorrat-Literal oben abgeglichen**, weil der `mcp`-Weg einen unbekannten Wert
nicht abweist. **Der Bericht nennt je Issue die tatsächlich geschriebene Menge**, damit ein
stilles Wegfallen sichtbar wird.

**Drift-Prüfung (nur `mcp`) — der Unterschied zwischen einer Zusage und einer Schranke:** Dass
`approved-for-agent` von dieser Operation nie geschrieben wird, ist auf dem `mcp`-Weg **nicht**
dadurch eingelöst, dass Lesen und Schreiben im selben Lauf liegen — **ein Lauf ist kein Moment.**
Entfernt Daniel das Label zwischen dem Lesen und dem Schreiben, setzt die vollständige, inzwischen
veraltete Menge es **wieder** und stellt damit eine zurückgezogene Automatisierungsfreigabe her;
laut `CLAUDE.md` ist gerade der Label-Zustand zum Bearbeitungszeitpunkt maßgeblich. Deshalb gilt
auf dem `mcp`-Weg: **unmittelbar vor dem Schreiben erneut lesen und die Mengen vergleichen.**
Weicht die gelesene Menge von der zuvor gelesenen ab, wird **nicht geschrieben** — das Issue wird
übersprungen, der Fall erscheint als eigener, auffälliger Punkt im Bericht, und der Lauf macht mit
dem nächsten Issue weiter. Kein erneuter Versuch mit der aktualisierten Menge im selben Durchgang:
Wer auf eine Drift mit sofortigem Nachziehen antwortet, hat das Rennen verkürzt, nicht geschlossen.

**Auf dem `gh`-Weg entfällt die Drift-Prüfung** — kein Versäumnis, sondern derselbe wegabhängige
Unterschied wie die beiden oben benannten: `--add-label`/`--remove-label` wirken additiv und
subtraktiv auf genau die genannten Werte und fassen ein Label, das im Aufruf nicht vorkommt,
überhaupt nicht an. `approved-for-agent` steht in keinem dieser Aufrufe und ist dort damit
**strukturell** unerreichbar statt durch Disziplin geschützt. Trägt ein Issue das Label, bleibt es
auf beiden Wegen unberührt, und der Fall geht in den Bericht.

**Die beiden wegabhängigen Eigenheiten, benannt statt vorausgesetzt:** Ein unbekannter Wert
scheitert auf dem `gh`-Weg laut — am 2026-09-11 gemessen: `'bereich:tippfehler' not found`,
Exit 1, **und kein angelegtes Label** —, und auf dem `mcp`-Weg legt die Issues-API ihn laut
Dokumentation stillschweigend als neues Label an. Die zweite Eigenschaft ist in diesem Repository
**nicht nachgemessen** (der `mcp`-Schreibversuch wurde von der Umgebung abgelehnt, und auf dem
`gh`-Weg ist sie grundsätzlich nicht zu belegen). Das ändert nichts: Tragend ist der Abgleich
gegen das Vorrat-Literal, nicht die Nebenwirkung des einen Wegs — er greift unabhängig davon, wie
sich der `mcp`-Weg tatsächlich verhält.

**Die sechs Label existieren im Repository; diese Operation legt keines an.** Einmalige
Einrichtung durch Daniel, derselbe Umgang wie mit den Board-Feldern und ihren Optionen.

Die beiden Werte im Befehl oben stehen als Beispiel für einen Zielzustand. Eingesetzt wird
ausschließlich ein Wert aus der Vorrat-Zeile, als **Literal** — das Label-Argument trägt weder
eine Variable noch eine Substitution. Regel 4.1 greift dort nicht: Der Wert kommt aus einem
geschlossenen Vokabular und ist kein Freitext.

Diese Operation trägt **keine Nachhol-Zeile**, und das ist eine Feststellung, keine Auslassung:
Sie ist ein Issue-Zugriff, der remote trägt, ihr Fehlschlag ist also ein echter Fehlschlag und
keine Eigenschaft der Umgebung. Scheitert sie auf allen Wegen, entfallen alle nachfolgenden
Operationen und das Issue erreicht `Ready` nicht — dasselbe Regime wie bei
`issue-titel-schreiben`. Unter `## Lokal nachzuholen` steht nur, was sich nachholen lässt, ohne
den Abschluss zu wiederholen.
