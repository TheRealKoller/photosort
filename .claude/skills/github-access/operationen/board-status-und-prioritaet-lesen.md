## `board-status-und-prioritaet-lesen` — beide Board-Werte in einem Aufruf

**Wege:** `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Auswertungsgrenze:** je Projekt-Item `project.number`, das Feld `Status` und das Feld
`Priorität` — und nichts sonst.
**Aufrufer:** `spec-writer` Schritt 0, `ship-entwurf` Schritt 7 und `story-entwurf` **zweimal** —
einmal als Auslieferungsfreigabe vor der Ausarbeitung, einmal unmittelbar vor der Übergabe an den
Auslieferpfad. Zwischen beiden Lesungen liegt dort ein ganzer Ausarbeitungslauf, und ein Lauf ist
kein Moment.
**Kein `mcp`-Weg:** Die MCP-Werkzeuge bieten für Projects (V2) keine Operation an —
gemessen, nicht vermutet: Projects V2 spricht ausschließlich GraphQL, und im
Werkzeugkasten liegt nichts, was diese Operation ausführen könnte.
**Diese Operation ist remote auf keinem Weg erreichbar** — dieselbe Ursache wie bei
`board-aufnahme`.
**`gh`:**

```bash
gh api graphql -F number=<NNN> -f query='
  query($number: Int!) {
    repository(owner: "TheRealKoller", name: "photosort") {
      issue(number: $number) {
        projectItems(first: 5) {
          nodes {
            project { number }
            status: fieldValueByName(name: "Status") {
              ... on ProjectV2ItemFieldSingleSelectValue { name } }
            prio: fieldValueByName(name: "Priorität") {
              ... on ProjectV2ItemFieldSingleSelectValue { name } }
          }
        }
      }
    }
  }'
```

Ausgewertet wird der Knoten mit `project.number == 8`, **nie** schlicht `nodes[0]` — sonst
entscheidet eine fremde Projektzugehörigkeit über ein Ablauf-Gate. Findet sich kein solcher
Knoten, ist das Issue nicht auf unserem Board; das ist ein Befund, kein Statuswert.

Dies ist die eine begründete Ausnahme von Regel 4.5 (benanntes, typisiertes Mittel): Der listende
Unterbefehl lädt die gesamte Item-Liste und hat genau daraus schon einmal einen Fehler erzeugt.
Die Query bleibt ein **Literal in einfachen Anführungszeichen**, die Nummer geht ausschließlich
als typisierte Variable `-F number=<NNN>` hinein — in doppelten Anführungszeichen expandierte die
Shell `$number` zu leer, und die Query wäre dann nicht fehlerhaft, sondern hätte klaglos eine
andere Bedeutung.

Diese Operation trägt **keine Nachhol-Zeile**, und das ist eine Feststellung, keine Auslassung:
Ein ausgebliebener Lesezugriff hinterlässt keinen Zustand, der nachzuziehen wäre. Was ein
gescheiterter Lesezugriff bedeutet, entscheidet der Ablauf, der ihn braucht — in `spec-writer`
Schritt 0 etwa eine Rückfrage an Daniel, weil das Gate dort fail-closed ist.
