## `pr-scanbefunde-lesen` — offene Code-Scanning-Befunde am eigenen PR

**Wege:** `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Auswertungsgrenze:** `number`, `state`, `tool`, `rule.description`,
`rule.security_severity_level`, `message.text`, `location.path`, `location.start_line`, `url` —
und nichts sonst.
**Aufrufer:** `ship-feature` Schritt 9 und `ship-entwurf` Schritt 8 — je **genau einmal**, nachdem
der Endstand des Wartepunkts feststeht, auch bei einem Halt. Kein Wartefenster, keine Schonfrist,
keine Wiederholung.
**Kein `mcp`-Weg:** Die Verengung ist Teil des Aufrufs — das `--jq` kürzt den fremdbeschreibbaren
Rule- und Meldungstext und entfernt die unsichtbaren Steuerzeichen, bevor er den Kontext erreicht;
ein MCP-Werkzeug lieferte die Antwort vor jeder Verengung. Dazu filtert das Code-Scanning-Werkzeug
des MCP-Servers über `ref`, nicht über die Pull-Request-Nummer.
**`gh`:**

```bash
if out=$(gh api "repos/TheRealKoller/photosort/code-scanning/alerts?pr=<MMM>&state=open" --paginate --jq '
  def kurztext:
    (tostring
     | gsub("[\\p{Cc}\\p{Zl}\\p{Zp}]"; " ")
     | gsub("[\\p{Cf}]"; "")
     | gsub("\\s+"; " ")
     | ltrimstr(" ") | rtrimstr(" ")
     | .[0:200]) as $t
    | if ($t | length) == 0 then "Befund ohne darstellbaren Text" else $t end;
  .[]
  | select(.state == "open")
  | { number: .number,
      state: .state,
      tool: .tool.name,
      regel: .rule.description,
      stufe: .rule.security_severity_level,
      text: ((.most_recent_instance.message.text // .message.text // .rule.description // "")
             | kurztext),
      pfad: .most_recent_instance.location.path,
      zeile: .most_recent_instance.location.start_line,
      url: .html_url }
  | tojson
' 2>/dev/null); then
  printf '%s\n' "$out"
else
  printf 'nicht festgestellt\n'
fi
```

**Offen ist nur `state == "open"`.** Der Endpunkt wird mit `state=open` abgefragt, und der
`--jq`-Ausdruck verwirft zusätzlich jeden anderen Zustand — ein `dismissed`- oder `fixed`-Alert
erscheint damit in keinem Fall, auch dann nicht, wenn die Abfrage ihn lieferte. Damit gilt
dieselbe Zusage wie für die Review-Threads: Ein abgewiesener oder behobener Befund erscheint im
nächsten Lauf nicht mehr, ohne dass der Ablauf dafür einen eigenen Zustand führt.

**Herkunftsoffen.** Kein Werkzeug- und kein Regel-Filter: Das Feld `tool` steht als Herkunft an
jeder Ausgabezeile und schließt nichts aus. `rule.severity` bleibt draußen; berichtet wird die
Stufe aus `rule.security_severity_level`.

**Der Kurztext hat eine Fallback-Kette**: `most_recent_instance.message.text`, dann
`message.text`, dann `rule.description`, zuletzt der feste Ersatztext. Dieselbe Verengung wie bei
den Review-Threads greift auf jede dieser Quellen — die Meldung ist fremdbeschreibbar.

**Die Feldbezeichner sind flach, keine Objekte.** Ein Objektname in der Auswertungsgrenze
verdeckte, welche Textfelder tatsächlich in den Kontext kommen; `message.text` und
`location.path` sind die Zusage, `message` und `location` wären eine Andeutung.

**Vollständig durch Paginierung.** `--paginate` holt alle Seiten, und `--jq` wird je Seite
angewandt — die Ausgabe ist zeilenorientiert, eine Seite zählt also nicht neu. Eine halbe
Seitenfolge ist damit keine Liste: Bei Exit ≠ 0 wird die gesamte gefangene Ausgabe verworfen, auch
eine bereits geschriebene frühere Seite.

**Die Fangform trägt, nicht das `--jq` allein.** `gh api` schreibt bei HTTP ≥ 400 den vollständigen
Antwortkörper ungefiltert auf stdout und wendet `--jq` nicht an; deshalb wird stdout erst in `out`
gefangen und nur bei Exit `0` ausgegeben, stderr geht nach `/dev/null`, und die Ausgabe geht als
Argument an eine feste Formatzeichenkette (`printf '%s\n' "$out"`, nie `printf "$out"`). Bei
Exit ≠ 0 lautet das Ergebnis ausschließlich `nicht festgestellt`.

**Die Fehlermeldung des gescheiterten Aufrufs wird nicht berichtet** (enge Ausnahme von
Wegleiter-Regel 5): Sie ist die einzige Stelle, an der roher Antworttext in den Kontext gelangen
könnte. Die geforderte Aussage ist der Befundstand; die Ursache ist lokal mit diesem Befehl
reproduzierbar.

`<MMM>` ist die Pull-Request-Nummer aus `pr-erstellen` dieses Laufs, gegen `^[0-9]+$` geprüft, und
steht ausschließlich im `pr=`-Parameter dieses Aufrufs. Der REST-Pfad ist das benannte, typisierte
Mittel (Härtungsregel 4.5): kein `--input`, kein `-X`, kein selbst gebauter Request-Körper, und
kein Wert aus einer Antwort wird Teil eines Aufrufs, eines Dateipfads oder eines abgerufenen Links.

**Diese Operation trägt keine Nachhol-Zeile**, und das ist eine Feststellung, keine Auslassung: Ein
ausgebliebener Lesezugriff hinterlässt keinen Zustand, der nachzuziehen wäre. Was ein gescheiterter
Lesezugriff bedeutet, entscheidet der Ablauf: `nicht festgestellt` im Bericht, kein Anhalten.
