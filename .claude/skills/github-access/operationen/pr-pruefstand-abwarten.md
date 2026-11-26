## `pr-pruefstand-abwarten` — blockierend auf das Ergebnis des CI-Laufs warten

**Wege:** `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Auswertungsgrenze:** keine Felder — ausgewertet wird ausschließlich der Ergebniswert aus der
Tabelle unten. Die Ausgabe wird verworfen, nicht gelesen und nicht gemeldet: Ihre Form ist
darstellungsabhängig, jede Auswertung an ihr wäre eine Annahme über ein Terminal, und aus einem
Aufruf, der nichts liest, gelangt weder Fremdtext noch ein Credential in Kontext oder Protokoll.
**Kein `mcp`-Weg:** Ein MCP-Werkzeug ist ein einzelner Aufruf mit einer Antwort und kann nicht
warten; ein aus MCP-Aufrufen gebautes Wiederholverfahren wäre genau die Eigenentwicklung, die
ADR 0092 ausschließt.
**`gh`:**

```bash
timeout 540 gh pr checks <MMM> --repo TheRealKoller/photosort --watch --fail-fast --interval 30 >/dev/null 2>&1
```

`--required` wird **nicht** gesetzt: Solange kein Check in der Branch Protection als erforderlich
eingetragen ist, filtert die Option alles weg, und die Prüfung wäre leer wahr.

Die Ausgabe wird umgeleitet und verworfen, **nie** in eine Pipe geleitet — hinter einer Pipe
stünde der Exit-Code des letzten Glieds, und ein Fehlschlag ginge als Erfolg durch. Der
Ergebniswert entsteht am Exit-Code des `gh`-Prozesses selbst:

| Ergebniswert | Entsteht aus | Folge |
|---|---|---|
| `gruen` | Exit `0`, und sonst nichts | der Ablauf schließt regulär ab |
| `rot` | Exit ≠ 0 **und** `pr-pruefstand-lesen` zeigt mindestens ein `bucket == fail` | Nachbesserung im Ablauf-Skill |
| `laeuft-noch` | Exit `124` des `timeout`-Aufrufs, oder Exit `8` | Wartefenster erneut, bis seine Obergrenze steht |
| `unbestimmt` | alles andere | der Ablauf hält an und meldet |

`unbestimmt` umfasst namentlich: Exit `2` bzw. `bucket == cancel` (ein abgebrochener Lauf ist kein
bestandener), Exit `4`, jeden unbekannten Exit-Code, „kein Check am Head-Commit" nach Ablauf der
Anlaufschonfrist, ein nicht verfügbares `gh` und eine Operation, die auf allen ihren Wegen
gescheitert ist. **Ein unbestimmtes Ergebnis gilt nie als grün**, und `rot` wird nie aus einem
Exit-Code allein geschlossen — Exit `1` ist zweideutig und steht auch für „noch kein Check
gemeldet". `bucket == skipping` ist kein Fehlschlag und wird toleriert. Ein `unbestimmt`, das aus
einem nicht tragenden Zugang entsteht, wird **nicht** durch ein zusätzlich beschafftes Credential
behoben.

**Die Betriebszahlen, jede an genau dieser einen Stelle** — was es nur einmal gibt, kann nicht
driften. Läuft ein Fenster regelmäßig ab, obwohl der Lauf gesund ist, wird die Zahl hier erhöht,
nicht je Ablauf:

- **Einzelaufruf:** das `timeout` der Befehlszeile oben, mit Reserve unter der
  600-Sekunden-Deckelung der Werkzeugumgebung. Ein abgelaufener Einzelaufruf ist `laeuft-noch`,
  nie `unbestimmt`.
- **Wartefenster je Lauf: 15 Minuten.** Innerhalb davon wird der Aufruf wiederholt; danach steht
  die Obergrenze, und das Ergebnis ist `unbestimmt`.
- **Wiederholintervall:** die `--interval`-Option der Befehlszeile oben.
- **Anlaufschonfrist: 120 Sekunden.** „Kein Check am Head-Commit" ist innerhalb dieses Fensters
  nach dem Push kein Befund, danach `unbestimmt`.
- **Nachbesserung: höchstens 2 Nachbesserungsrunden.** Erschöpft heißt anhalten und melden, nie
  weiterversuchen.

`<MMM>` ist die Pull-Request-Nummer aus `pr-erstellen` dieses Laufs, gegen `^[0-9]+$` geprüft. Die
argumentlose Form wird **nie** benutzt: Sie löst über den aktuellen Branch auf und kann in einem
Arbeitsbaum oder nach einem Branch-Wechsel einen anderen Pull Request treffen — ein Fix-Push ginge
dann an einen Stand, den der Ablauf nie gemessen hat.
