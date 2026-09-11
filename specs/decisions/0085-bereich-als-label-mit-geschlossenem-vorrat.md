# 0085 - Der Bereich eines Issues ist ein Label mit geschlossenem Vorrat, kein Board-Feld

**Status:** Accepted
**Datum:** 2026-09-11
**Bezug:** GitHub-Issue [`#259`](https://github.com/TheRealKoller/photosort/issues/259), Spec
`specs/features/0259-*.md`

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung sieben Punkte trägt —
Träger, Vorrat, Ort des Vorrats, seine Schranke, die schreibende Operation, die Ausführungsstelle
und den einmaligen Nachlauf.

## Kontext

Das Board führt die gesamte offene Arbeit in einer Liste. Woran ein Issue rührt — Oberfläche,
Backend, Verarbeitungskette, KI-Ablauf, Design, Betrieb — ist dort kein Merkmal. Als Träger kommen
zwei Dinge in Frage: ein Feld des Projects-V2-Boards oder ein GitHub-Label. Drei Eigenschaften
entscheiden die Wahl, und alle drei sind gemessen, nicht vermutet:

- Projects (V2) kennt Single-Select und Text, **kein** Multi-Select. Ein Issue soll mehrere
  Bereiche gleichzeitig tragen können.
- Die vier Board-Operationen des Katalogs sind remote über keinen Weg erreichbar (ADR
  [`0061`](./0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md)). Ein
  Board-Feld fiele in einer Cloud-Session genau an der Stelle aus, an der der Wert entstehen soll.
- Labels reiten auf den Issue-Operationen, und die tragen remote vollständig.

Ein Label-Vorrat als Literal im Operationskatalog existiert bereits: `idee`/`bug` bei
`issue-anlegen`.

## Entscheidung

### 1. Träger ist ein GitHub-Label mit dem Präfix `bereich:`

Sechs Startwerte: `bereich:frontend`, `bereich:backend`, `bereich:pipeline`,
`bereich:ai-workflow`, `bereich:design`, `bereich:infra`. Das Präfix grenzt sie gegen `idee`,
`bug` und `approved-for-agent` ab und macht die Menge maschinell erkennbar. Status und Priorität
bleiben Board-Felder und werden von dieser Entscheidung nicht berührt.

### 2. Der Vorrat steht als Literal im Operationskatalog — dort und an keiner zweiten Stelle

Ein Label ist ein **steuernder Wert** (Härtungsregel 4.2), und steuernde Werte stehen als Literal
im Katalogtext; eine zweite Stelle (`CLAUDE.md`, ein eigenes Dokument) driftete von der ersten
weg. Ablauf-Skills nennen ausschließlich die Operations-ID, nie einen der sechs Werte.

### 3. Ein neuer Wert kommt über einen Wächtertest hinzu, nicht über eine Zusage

`scripts/tests/`, CI-Job `demo-scripts`: Der Vorrat wird als geschlossene Menge gegen den
Katalogtext geprüft — dieselbe Bauart wie `ERWARTETE_OPERATIONEN`. Ein siebter Wert färbt rot, bis
er auch im Test steht. „Neue Werte nur durch bewusste Ergänzung" ist damit eine Schranke statt
einer Absichtserklärung. Derselbe Test prüft die Gegenrichtung, also eine Abwesenheit: kein
Bereichswert außerhalb des Katalogs.

### 4. Die sechs Label existieren im Repository; keine Operation legt sie an

Einmalige Einrichtung durch Daniel — derselbe Umgang wie mit den Board-Feldern und ihren Optionen.
Auf dem `gh`-Weg scheitert `--add-label` mit einem unbekannten Wert laut; das ist eine geschenkte
zweite Schranke. **Auf dem `mcp`-Weg gilt sie nicht:** Die Issues-API legt ein unbekanntes Label
beim Setzen stillschweigend an. Tragend ist deshalb Punkt 3, nicht diese Nebenwirkung.

### 5. Eine Operation schreibt den Bereich, und sie schreibt einen Zielzustand

`issue-bereich-setzen`, Wege `mcp` und `gh`. Gegenstand ist die **Menge** der Bereiche des Issues,
nicht ein Zuwachs: Eine Nachschärfung, die den Bereich korrigiert, muss den falschen entfernen,
sonst weist der Board-Filter das Issue dauerhaft unter einem Bereich aus, den es nicht mehr
betrifft. Die beiden Wege erreichen denselben Zielzustand verschieden — `gh` additiv und
subtraktiv über `--add-label`/`--remove-label`, `mcp` durch Übergabe der **vollständigen**
Label-Menge. Auf dem `mcp`-Weg gehören `idee`/`bug` deshalb mit in den Aufruf, sonst fallen sie
still weg.

Es entsteht ausdrücklich **keine** generische „Label setzen"-Operation: ein steuernder Wert ohne
geschlossenen Vorrat ist genau das, was Regel 4.2 ausschließt.

### 6. Der Bereich entsteht beim Schärfen, und sein Ausbleiben hält die Story zurück

Ausführungsstelle ist `refinement`, Schritt 6, hinter `issue-titel-schreiben` und vor den
Board-Zugriffen. `capture` bleibt unverändert — die Leere beim Erfassen ist das Fehlen eines
Schritts, nicht ein neuer Schritt.

Scheitert die Operation auf allen Wegen, entfallen alle nachfolgenden, und das Issue erreicht
`Ready` nicht. Dieselbe Behandlung wie beim Titel und aus demselben Grund: Es ist ein
Issue-Zugriff, der remote trägt, sein Fehlschlag ist also ein echter Fehlschlag und keine
Eigenschaft der Umgebung. Sie erscheint deshalb **nie** unter `## Lokal nachzuholen` — dort steht
nur, was sich nachholen lässt, ohne den Abschluss zu wiederholen.

### 7. Der einmalige Nachlauf ist ein Sitzungslauf, kein eingechecktes Skript

Ein Skript unter `scripts/` wäre eine zweite Stelle mit GitHub-Zugriff (ADR 0061), erreichte die
MCP-Werkzeuge gar nicht und trüge danach dauerhaft Lint-, Format- und Testlast für einen Lauf, den
niemand wiederholt. Der Nachlauf braucht die Liste der offenen Issues; dafür bekommt der Katalog
`issue-liste-lesen` (Wege `mcp` und `gh`, Auswertungsgrenze `number`, `title`, `labels`, `state`)
— die bewusste Erweiterung einer geschlossenen Liste um eine Lesemöglichkeit, die ihr heute fehlt,
nicht ihre Aufweichung.

## Begründung

- **Die Mehrfachzuordnung beendet die Abwägung, bevor sie beginnt.** Sie ist ein hartes
  Akzeptanzkriterium, und Projects V2 kann sie nicht. Ein Textfeld mit selbst geparstem Inhalt
  wäre ein Datentyp aus Zeichenketten-Konvention, ohne Filter und ohne Vollständigkeitsprüfung.
- **Ein Wert, der remote nicht entstehen kann, entsteht nicht.** Der Bereich soll beim Schärfen
  anfallen; `refinement` läuft auch dort, wo jeder Board-Schreibzugriff ausfällt.
- **Wiederverwendung statt neuem Muster:** Label mit geschlossenem Vorrat im Katalogtext gibt es
  seit `idee`/`bug`; hier kommt ein zweiter Vorrat neben einen bestehenden, keine neue Bauart.
- **Sichtbarkeit und Filter kosten keine Zeile Code.** Projects-Karten zeigen Label, die
  Filterleiste kennt `label:` — ein Board-Feld hätte beides auch gekonnt, aber nur einfach belegt.

## Konsequenzen

- Der Katalog wächst von 17 auf 19 Operationen. `test_github_zugriff_an_einer_stelle.py` zieht
  `ERWARTETE_OPERATIONEN` samt Zählung mit; `test_issue_befehle_in_skills.py` nimmt `list` in
  `LESENDE_VERBEN` auf, sonst meldet es den neuen Lesebefehl als unbekanntes Verb.
- Kein Produktcode: Backend, Frontend und Pipeline bleiben unberührt, das Coverage-Gate ebenso.
  `docs/architecture.md` und `docs/setup.md` ändern sich nicht — weder Systemarchitektur noch
  lokales Setup sind betroffen. `docs/ai-workflow.md` bekommt einen Satz, weil der Ablauf selbst
  einen Schritt dazubekommt.
- Zeigt eine Board-Karte die Label wider Erwarten nicht, ist das eine Ansichtseinstellung des
  Boards, die Daniel einmal setzt — keine Umsetzungsaufgabe.
- Bereiche an Pull Requests, Auswertung über Bereiche und die automatische Herleitung aus
  geänderten Dateien bleiben außen vor. Ein späterer Wechsel des Trägers braucht eine neue, diese
  ADR als „Superseded" markierende ADR.
