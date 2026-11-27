## `pr-reviewbefunde-lesen` — offene Review-Threads und Änderungsanforderungen am eigenen PR

**Wege:** `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Auswertungsgrenze:** `isResolved`, `isOutdated`, `path`, `line`, `url`, `author`, `bodyText`,
`totalCount` — und nichts sonst.
**Aufrufer:** `ship-feature` Schritt 9 und `ship-entwurf` Schritt 8 — je **genau einmal**, nachdem
der Endstand des Wartepunkts feststeht, auch bei einem Halt. Kein Wartefenster, keine Schonfrist,
keine Wiederholung.
**Kein `mcp`-Weg:** Die Verengung ist Teil des Aufrufs — das `--jq` kürzt den fremdbeschreibbaren
Freitext und entfernt die unsichtbaren Steuerzeichen, bevor er den Kontext erreicht; ein
MCP-Werkzeug lieferte die Antwort vor jeder Verengung. Dazu hat `latestOpinionatedReviews` keine
MCP-Entsprechung: „je Autor der letzte Review" wäre dort aus einer vollen Review-Liste nachzubauen,
und genau diese Ableitung ist Sache der API.
**`gh`:**

```bash
if out=$(gh api graphql -f query='
  query($number: Int!) {
    repository(owner: "TheRealKoller", name: "photosort") {
      pullRequest(number: $number) {
        reviewThreads(first: 100) {
          totalCount
          nodes {
            isResolved
            isOutdated
            comments(first: 1) {
              nodes { path line url author { login } bodyText }
            }
          }
        }
        latestOpinionatedReviews(first: 100) {
          totalCount
          nodes { state url author { login } bodyText }
        }
      }
    }
  }' -F number=<MMM> --jq '
  def kurztext:
    (tostring
     | gsub("[\\p{Cc}\\p{Zl}\\p{Zp}]"; " ")
     | gsub("[\\p{Cf}]"; "")
     | gsub("\\s+"; " ")
     | ltrimstr(" ") | rtrimstr(" ")
     | .[0:200]) as $t
    | if ($t | length) == 0 then "Befund ohne darstellbaren Text" else $t end;
  (.data.repository.pullRequest) as $pr
  | ([
      ($pr.reviewThreads.nodes[] | select(.isResolved == false)
       | { art: "thread",
           veraltet: (.isOutdated == true),
           pfad: .comments.nodes[0].path,
           zeile: .comments.nodes[0].line,
           url: .comments.nodes[0].url,
           herkunft: .comments.nodes[0].author.login,
           text: ((.comments.nodes[0].bodyText // "") | kurztext) }),
      ($pr.latestOpinionatedReviews.nodes[] | select(.state == "CHANGES_REQUESTED")
       | { art: "review",
           veraltet: false,
           pfad: null,
           zeile: null,
           url: .url,
           herkunft: .author.login,
           text: ((.bodyText // "") | kurztext) })
    ]) as $befunde
  | ($befunde[] | tojson),
    ({ threads: ([$befunde[] | select(.art == "thread")] | length),
       threadsGesamt: $pr.reviewThreads.totalCount,
       reviews: ([$befunde[] | select(.art == "review")] | length),
       reviewsGesamt: $pr.latestOpinionatedReviews.totalCount } | tojson)
' 2>/dev/null); then
  printf '%s\n' "$out"
else
  printf 'nicht festgestellt\n'
fi
```

**Offen heißt: in GitHub schließbar.** Gelesen werden Review-Threads mit `isResolved == false` —
auch solche mit `isOutdated == true`; veraltet heißt, die Zeile hat sich verschoben, nicht, der
Punkt ist erledigt, und der Befund wird mit dem Vermerk „veraltet" berichtet. Dazu je Autor der
letzte Review, wenn er `CHANGES_REQUESTED` ist; ein späteres `APPROVED` oder ein `DISMISS` desselben
Autors ersetzt ihn und fällt damit aus der Auswahl. **`COMMENTED`-Reviews und die
Konversationskommentare des Pull Requests bleiben draußen**: Beide tragen in GitHub keinen offenen
Zustand, ließen sich also nie wieder schließen und verletzten die Zusage, dass ein abgewiesener
Befund im nächsten Lauf nicht mehr erscheint.

`state` wird ausschließlich als Auswahlkriterium innerhalb des `--jq`-Ausdrucks ausgewertet; es
steht in keiner Ausgabezeile und ist deshalb nicht Teil der Auswertungsgrenze.

**Herkunftsoffen.** Es gibt keinen Autor- und keinen Werkzeugfilter: Der Autorenkreis an einem
öffentlichen Repository ist „jeder eingeloggte GitHub-Nutzer", und eine Vorauswahl nach Herkunft
wäre eine Heuristik über fremden Text. Die Herkunft steht als Feld `herkunft` an jeder Ausgabezeile
und schließt nichts aus.

**Die Vollständigkeit entscheidet der Ablauf, nicht das `--jq`.** Beide Verbindungen werden mit
`first: 100` gelesen, und beide `totalCount` stehen in der Ausgabe. Meldet ein `totalCount` mehr
Einträge, als gelesen wurden, ist diese Quelle **nicht festgestellt** — nicht nachblättern, nicht
aufstocken. Die Zahl der Befunde wird nicht begrenzt: Gefiltert wird ausschließlich nach dem
offenen Zustand.

**Die Fangform trägt, nicht das `--jq` allein.** `gh api` schreibt bei HTTP ≥ 400 und bei einem
GraphQL-`errors`-Feld den vollständigen Antwortkörper ungefiltert auf stdout und wendet `--jq`
nicht an; deshalb wird stdout erst in `out` gefangen und nur bei Exit `0` ausgegeben, stderr geht
nach `/dev/null`, und die Ausgabe geht als Argument an eine feste Formatzeichenkette
(`printf '%s\n' "$out"`, nie `printf "$out"`). Bei Exit ≠ 0 lautet das Ergebnis ausschließlich
`nicht festgestellt`. Der Aufruf lautet exakt `gh api graphql` — nur diese Form löst `gh`s
Fehlererkennung aus.

**Die Fehlermeldung des gescheiterten Aufrufs wird nicht berichtet** (enge Ausnahme von
Wegleiter-Regel 5): Sie ist die einzige Stelle, an der roher Antworttext in den Kontext gelangen
könnte. Die geforderte Aussage ist der Befundstand; die Ursache ist lokal mit diesem Befehl
reproduzierbar.

`<MMM>` ist die Pull-Request-Nummer aus `pr-erstellen` dieses Laufs, gegen `^[0-9]+$` geprüft, und
geht ausschließlich als typisierte Variable `-F number=<MMM>` in die Query. Die Query selbst steht
als Literal in einfachen Anführungszeichen; kein `--input`, kein `-X`, kein `eval`, und kein Wert
aus einer Antwort wird Teil eines Aufrufs, eines Dateipfads oder eines abgerufenen Links.

**Diese Operation trägt keine Nachhol-Zeile**, und das ist eine Feststellung, keine Auslassung: Ein
ausgebliebener Lesezugriff hinterlässt keinen Zustand, der nachzuziehen wäre. Was ein gescheiterter
Lesezugriff bedeutet, entscheidet der Ablauf: `nicht festgestellt` im Bericht, kein Anhalten.
