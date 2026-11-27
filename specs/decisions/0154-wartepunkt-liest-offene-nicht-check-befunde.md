# 0154 - Der Wartepunkt liest offene Nicht-Check-Befunde, und zwar ungefiltert nach Herkunft

**Status:** Accepted
**Datum:** 2026-11-27
**Bezug:** GitHub-Issue [#505](https://github.com/TheRealKoller/photosort/issues/505), Story
„Wartepunkt meldet offene Nicht-Check-Befunde am Pull Request"; Feature-Spec
[`0505`](../features/0505-befunde-am-wartepunkt.md) (die Spec trägt die Nummer des Issues, ADR 0043).
**Ergänzt, ohne abzulösen:** ADR [`0092`](./0092-ci-ergebnis-abwarten-und-begrenzt-nachbessern.md),
Abschnitte 3 bis 6 (der Wartepunkt, seine Zahlen und die Nachbesserungsklasse bleiben unverändert);
ADR [`0061`](./0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md), Abschnitte 2
und 4.5 — dort wird die Aussage „die eine Ausnahme" auf zwei benannte Ausnahmen erweitert
(Abschnitt 4 dieser ADR).

**Umfang:** rund 250 statt 100 Zeilen. Die Entscheidung trägt neben der Quellenwahl vier eigene
Zusicherungen mit je eigener Fehlerfolge — die Verengung des Freitexts, die Fangform samt ihrer
engen Ausnahme von Wegleiter-Regel 5, die „nicht festgestellt"-Regel und die zweite
GraphQL-Ausnahme; sie gehen in keiner Zusammenfassung auf.

## Kontext

Der Wartepunkt stellt heute ausschließlich das Check-Ergebnis fest (`pr-pruefstand-abwarten`,
danach bei Bedarf `pr-pruefstand-lesen`). Befunde am Pull Request, die nicht als Check erscheinen,
kommen dort nicht vor. An Pull Request #503 standen alle elf Checks auf `pass`, während am selben
Pull Request ein offener Code-Scanning-Befund der Stufe `medium` hing (Review-Thread von
`github-advanced-security[bot]` zum Alert #7). Der Bericht „Endstand: grün" war für die Checks wahr
und als Auskunft über den Pull Request unvollständig.

Drei Eigenschaften der Quellen sind gemessen (2026-11-27, PR #503):

- Der Review-Thread trägt `isResolved`/`isOutdated`; der dahinterliegende Alert trägt `state`
  (`open`/`dismissed`/`fixed`). Beides sind Zustände in GitHub, die sich dort schließen lassen.
- Für den Thread-Zustand gibt es weder einen `gh`-Unterbefehl noch ein REST-Feld: `gh pr view
  --json` kennt kein Review-Thread-Feld, und die REST-Kommentarliste trägt keinen
  Auflösungszustand. GraphQL ist der einzige Weg.
- Code-Scanning-Alerts zum Pull Request liefert `GET /repos/{owner}/{repo}/code-scanning/alerts`
  mit dem Parameter `pr` (offene Doku; gemessen am Alert #7 von PR #503).

## Entscheidung

### 1. Offen heißt: in GitHub schließbar

Gelesen werden zwei Quellen, beide ausschließlich lesend und beide zum **eigenen**, selbst
eröffneten Pull Request:

- **Review-Threads mit `isResolved == false`**, beliebiger Autoren einschließlich Bots. Ein
  `isOutdated == true` ist **kein** Ausschluss: veraltet heißt, die Zeile hat sich verschoben,
  nicht, der Punkt ist erledigt; der Befund wird mit dem Vermerk „veraltet" berichtet.
- **Code-Scanning-Alerts mit `state == open`** zum Pull Request.
- **Reviews mit `CHANGES_REQUESTED`**, je Autor der letzte solche Stand (`latestOpinionatedReviews`
  liefert je Autor den letzten Review; ein späteres `APPROVED` ersetzt ihn, ein `DISMISS` lässt ihn
  verschwinden oder als `DISMISSED` erscheinen — beides fällt aus dem Filter).

**Ausgeschlossen bleiben Reviews mit `COMMENTED` sowie die Konversationskommentare des Pull
Requests.** Beide tragen in GitHub keinen offenen Zustand: Ein `COMMENTED`-Review lässt sich nicht
abweisen, ein Issue-Kommentar nur ausblenden. Sie könnten nie wieder verschwinden und verletzten
damit die Zusage, dass ein abgewiesener Befund nicht mehr erscheint. Die Konversationskommentare
bleiben zusätzlich aus dem Grund draußen, der schon heute gilt: keine Operation liest
Issue-Kommentare. Das ist eine Entscheidung knapp unterhalb der Produktschwelle — sie folgt aus
dem Kriterium „am Pull Request abgewiesen oder zurückgezogen", nicht aus einer Abwägung über
Sichtbarkeit.

Ein Befund kann doppelt erscheinen (der Sicherheits-Bot legt zu einem Alert einen Thread an). Es
wird **nicht** zusammengeführt: Die Zuordnung wäre eine Heuristik über fremden Text, und der Thread
verschwindet nicht mit dem Alert. Jeder Eintrag nennt seine Herkunft, damit Daniel die beiden
zusammen erledigen kann.

### 2. Zwei neue Operationen, `gh` allein, ohne Nachhol-Zeile

- **`pr-reviewbefunde-lesen`** — Review-Threads und offene Änderungsanforderungen in **einem**
  GraphQL-Aufruf in der Fangform aus Abschnitt 3, dessen Ausgabe ein `--jq`-Ausdruck auf die
  ausgewerteten Felder verengt.
- **`pr-scanbefunde-lesen`** — Code-Scanning-Alerts zum Pull Request über `gh api` (REST), paginiert.

Beide tragen **keinen `mcp`-Weg**. Der Grund ist strukturell, nicht „belegt/unbelegt": Die Zusage
beider Operationen ist, dass der Freitext eines Befunds den Kontext **nur gekürzt und von
Steuerzeichen befreit** erreicht (Abschnitt 5); das leistet der `--jq`-Ausdruck, der Teil des
Aufrufs ist. Ein MCP-Werkzeug liefert die Antwort, bevor eine solche Verengung greifen kann — der
Weg führte dieselbe Operation mit einer anderen Zusage aus. Für `pr-reviewbefunde-lesen` kommt
hinzu: `latestOpinionatedReviews` hat keine MCP-Entsprechung; die Auswahl „je Autor der letzte
Review" müsste aus einer vollen Review-Liste nachgebaut werden, und genau diese Ableitung ist
Sache der API. Für `pr-scanbefunde-lesen`: das Code-Scanning-Werkzeug des MCP-Servers liegt nicht
im Standard-Werkzeugsatz und filtert über `ref`, nicht über die Pull-Request-Nummer. Wer ein
Werkzeug findet, das die Verengung selbst trägt, trägt den Weg dort nach.

**Keine Nachhol-Zeile:** Ein ausgebliebener Lesezugriff hinterlässt keinen Zustand, der
nachzuziehen wäre. Die Nachhol-Zeile ist der Form nach ein Wiederholbefehl für einen Schreibzugriff.

### 3. „Nicht festgestellt" entsteht am Exit-Code, nie am Ausbleiben von Einträgen

Festgestellt ist eine Quelle nur, wenn ihr Aufruf mit Exit `0` endet **und** die Antwort vollständig
gelesen wurde. Alles andere ist **nicht festgestellt**:

- Exit ≠ 0 — HTTP 403/404, Authentifizierungsfehler, ein GraphQL-`errors`-Feld auch bei partiellen
  Daten (der `gh`-Weg bricht dann mit Exit `1` ab, ohne den `--jq`-Ausdruck anzuwenden), ein
  gescheiterter `--jq`-Ausdruck, ein nicht verfügbares `gh`.
- Beide Verbindungen von `pr-reviewbefunde-lesen` werden mit `first: 100` gelesen; meldet
  `totalCount` mehr, ist die Liste unvollständig und die Quelle **nicht festgestellt**. Auf dem
  REST-Weg wird paginiert, damit diese Lücke dort nicht entsteht.

Die Reihenfolge ist tragend: **erst prüfen, ob gelesen wurde, dann zählen.** Eine leere Liste nach
Exit `0` ist „keine offen"; eine leere Liste nach Exit ≠ 0 ist „nicht festgestellt". Ein
nicht festgestellter Stand hält den Lauf **nicht** an und wird nie als „keine Befunde" berichtet;
die Befunde der anderen Quelle werden trotzdem gelistet.

**Die Fangform ist Teil des Befehls, nicht eine Vorschrift danach.** `gh api` schreibt bei HTTP ≥ 400
und bei einem GraphQL-`errors`-Feld den **vollständigen** Antwortkörper ungefiltert auf stdout, gibt
eine abgeleitete Meldung auf stderr aus, endet mit Exit `1` und wendet `--jq` **nicht** an
(`pkg/cmd/api/api.go::processResponse`, Gate `FilterOutput != "" && serverError == ""`). Ein `--jq`
allein verengt also nur den Erfolgsfall; im Fehlerfall stünde der rohe Kommentartext im Kontext und
die Aussage aus Abschnitt 5 wäre falsch. Beide Befehle stehen deshalb in dieser Form:

```bash
if out=$(gh api graphql -f query='<Query>' -F number=<MMM> --jq '<Verengung>' 2>/dev/null); then
  printf '%s\n' "$out"
else
  printf 'nicht festgestellt\n'
fi
```

`pr-scanbefunde-lesen` trägt dieselbe Form mit `--paginate`. Vier Einzelheiten tragen: **stdout wird
gefangen, bevor es ausgegeben wird** — eine bei `--paginate` bereits geschriebene frühere Seite ist
damit ebenfalls verworfen, und das ist gewollt: eine unvollständige Liste ist keine Liste; **stderr
geht nach `/dev/null`**, weil die Meldung den Antwortkörper zitieren kann; **die Ausgabe geht als
Argument an eine feste Formatzeichenkette** (`printf '%s\n' "$out"`, nie `printf "$out"`), damit im
Text enthaltene `%`-Formate nichts auslösen; und der Aufruf lautet **exakt `gh api graphql`** —
nicht `/graphql`, nicht die absolute URL. Nur diese Form löst `gh`s Fehlererkennung aus; die anderen
liefern bei HTTP 200 mit `errors` Exit `0` und eine gefilterte Ausgabe, also fälschlich „keine offen".

**Die enge Ausnahme von Wegleiter-Regel 5** („die Meldung des zuletzt versuchten Wegs geht wörtlich
in den Chat-Bericht") gilt für genau diese zwei Operationen: Die Fehlermeldung wird **nicht**
berichtet. Sie ist die einzige Stelle, an der roher Antworttext in den Kontext gelangen könnte; die
geforderte Aussage ist der Befundstand, und die Ursache ist lokal mit dem Katalogbefehl
reproduzierbar.

### 4. Der GraphQL-Lesezugriff ist eine zweite benannte Ausnahme

Härtungsregel 4.5 nennt heute genau eine begründete Ausnahme (`board-status-und-prioritaet-lesen`).
Der Review-Thread-Zustand ist über keinen `gh`-Unterbefehl erreichbar; die Query steht deshalb als
**Literal in einfachen Anführungszeichen** im Katalogeintrag, die Pull-Request-Nummer geht
ausschließlich als typisierte Variable `-F number=` hinein. Dasselbe gilt für die
`latestOpinionatedReviews`-Verbindung derselben Query. Die Regel selbst bleibt unverändert: kein
`--input`, kein `-X`, kein selbst gebauter Request-Körper; `gh api` mit REST-Pfad ist auf dem
`gh`-Weg das benannte Mittel, wo kein Unterbefehl existiert.

Der Aufruf lautet exakt `gh api graphql` (Abschnitt 3); `pr-scanbefunde-lesen` bleibt beim benannten
REST-Pfad.

### 5. Der Kurztext wird mechanisch gebildet, bevor er den Kontext erreicht

Der `--jq`-Ausdruck ist Teil des Aufrufs, nicht eine nachgelagerte Vorschrift. Er

- verengt die Ausgabe auf die ausgewerteten Felder (Abschnitt 6),
- ersetzt `Cc`- und Zeilentrenner-Zeichen durch ein Leerzeichen (ein mehrzeiliger Kommentar würde
  beim Löschen zusammenkleben),
- entfernt `Cf`-Zeichen (Bidi-Overrides, Zero-Width, BOM) — die Klasse, die ein Modell im eigenen
  Kontext nicht sieht,
- faltet Leerraumfolgen und schneidet auf **200 Zeichen** (Codepoints).

Bleibt nichts übrig, lautet der Kurztext „Befund ohne darstellbaren Text". Das ist die
Verschärfung der Regel aus `pr-pruefstand-lesen` (dort wird am Anzeigewert gearbeitet, hier schon am
Aufruf): Erst der `--jq`-Ausdruck **und** die Fangform aus Abschnitt 3 zusammen tragen die Aussage,
dass der volle Kommentartext **auf keinem Schritt** in den Kontext gelangt — auch nicht im
Fehlerfall, in dem `gh` den Antwortkörper ungefiltert auf stdout schriebe. Er wird **nirgends
dauerhaft abgelegt** — nicht in eine Datei, nicht in den PR-Body, nicht in einen Issue-Kommentar,
nicht in eine Commit-Nachricht. Die Fundstelle wird aus der geprüften Pull-Request-Nummer und den
Zahlenfeldern der Antwort **gebildet**; die Antwort-URL wird nur angezeigt, nie Teil eines Aufrufs.

### 6. Die Berichtsform: ein eigener Block neben dem CI-Ergebnis

Der Block `## CI-Ergebnis` behält seine drei Felder und seine Bedeutung unverändert; der Befundstand
steht daneben, definiert einmal im Skill `github-access`:

```markdown
## Befunde am Pull Request

**Befundstand:** <keine offen | offen | nicht festgestellt>
**Quellen:** Review-Threads: <Zahl | nicht festgestellt>; Änderungsanforderungen: <Zahl | nicht festgestellt>; Code-Scanning: <Zahl | nicht festgestellt>
```

Je Befund eine Zeile: Fundstelle, Herkunft (Anmeldename bzw. Werkzeugname), Kurztext; bei
Code-Scanning zusätzlich die Stufe. Der Block steht **nur** im Chat-Bericht. `nicht festgestellt`
hat Vorrang: Steht eine Quelle aus, ist der Befundstand nie `keine offen` und nie `offen`.

**Ein Befund löst nichts aus** — kein Anhalten, kein Nachbesserungsauftrag, kein Push. Diese Regel
steht einmal im Blockabschnitt des Katalogs, nicht in beiden Abläufen.

### 7. Gelesen wird einmal, am Ende, nach dem letzten Push

Beide Operationen laufen **genau einmal je Lauf**, unmittelbar nachdem der Endstand des
Wartepunkts feststeht — bei `gruen` wie bei einem Halt (`unbestimmt`, erschöpfte
Nachbesserungsrunden). Innerhalb der Nachbesserungsrunden wird nicht gelesen: Ein Befund treibt
keine Runde, und die letzte Runde soll nicht auf einem Befundstand aufsetzen, der sich mit ihrem
Push ohnehin ändert. Auch ein Halt liest noch, weil der Bericht sonst genau an der Stelle
unvollständig bliebe, an der er heute unvollständig war.

Die Befundlesung ist **keine zweite Wartestelle**: Sie wiederholt sich nicht, hat kein Fenster und
keine Schonfrist. Der Befund der Sicherheitsprüfung ist zum Endstand des Wartepunkts da, weil der
CodeQL-Check selbst erst dann fertig ist — der Check trägt diesen Befund, die Befundlesung macht
ihn sichtbar.

### 8. Durchgesetzt wird es an der Form der Befehle

Erweitert wird der vorhandene Wächter `test_ci_warten_verankert.py` (Wächter `warten`): beide
Lesebefehle stehen in der **Fangform** aus Abschnitt 3 — Zuweisung an eine Variable, `if`, Ausgabe
über `printf '%s\n' "$out"`, `2>/dev/null`, und der GraphQL-Aufruf lautet exakt `gh api graphql`;
der REST-Weg trägt `--paginate`. Dazu tragen beide Befehle `--jq`, die GraphQL-Query steht in
einfachen Anführungszeichen, die Nummer geht als typisierte Variable hinein, beide Verbindungen
nennen `first: 100` und `totalCount`, der REST-Weg nennt den `pr`-Parameter, und beide
`--jq`-Ausdrücke enthalten die Kürzung auf 200 Zeichen sowie die Entfernung der `Cc`/`Cf`-Zeichen.
Dazu kommen der Katalogtest (zwei Operationen mehr, beide lesend, mit exakter Auswertungsgrenze, die
zweite benannte Kommentar-Ausnahme) und die Whitelist in `test_ship_entwurf_skill.py`.

**Was ausdrücklich nicht gebaut wird:** ein Prüfer, der aus dem Prosa-Satz „ein Befund hält nicht
an" liest, dass ein Befund nicht anhält. Er wäre grün, weil der Satz dasteht.

## Begründung

Die Alternative zu Abschnitt 5 ist, die Antworten ungefiltert zu lesen und den Kurztext im Bericht
zu kürzen. Sie ist billiger und an zwei Stellen schlechter: Der volle Text — bis zu hundert
Threads, beliebig lang, von beliebigen Dritten — läge im Kontext einer Hauptsession mit
Schreibzugriff, und unsichtbare Steuerzeichen würden erst im Bericht behandelt, wo niemand sie
sieht. Der `--jq`-Ausdruck ist die einzige Stelle, an der die Kürzung mechanisch und vor dem
Kontext ausführbar ist; dieselbe Einsicht trägt heute die Titel-Datei aus Härtungsregel 4.4.

Die Alternative zur Fangform ist, `--jq` zu vertrauen und den Fehlerfall nachgelagert zu regeln
(„Ausgabe bei Exit ≠ 0 nicht auswerten", `2>/dev/null` allein, `>/dev/null`). Sie ist verworfen:
Eine Vorschrift danach kann den Text nicht mehr aus dem Kontext halten, `2>/dev/null` allein lässt
stdout stehen, und `>/dev/null` macht die Operation ergebnislos. `--jq` wegzulassen hieße, den
Erfolgsfall ungekürzt zu lesen — die Fläche, die Abschnitt 5 gerade schließt.

Die Alternative zu Abschnitt 1 — nur die Sicherheitsbefunde lesen — wäre billiger und verletzte
das Kriterium „unabhängig davon, welche Anwendung sie abgegeben hat". Die Verschärfung kostet
keine zusätzliche Operation, nur einen zweiten Filter in derselben Query.

## Konsequenzen

- Ein grüner Wartepunkt trägt jetzt zwei Aussagen: das Check-Ergebnis und den Befundstand. Beide
  bleiben getrennt; ein Befund macht kein `grün` zu `rot`.
- Eine Antwort von Copilot, die an einem Thread bereits beantwortet wurde, bleibt offen, bis jemand
  sie in GitHub auflöst. Der Ablauf führt dafür keinen Zustand; er berichtet sie.
- In einer Cloud-Session scheitert der GraphQL-Weg an der dortigen GraphQL-Grenze (ADR 0061,
  Abschnitt 3). Der Befundstand ist dann „nicht festgestellt", der Lauf hält deswegen nicht an.
  Für die Befundlesung ist das dieselbe Lage wie für den Wartepunkt selbst, der ebenfalls nur den
  `gh`-Weg trägt.
- Fällt ein Antwortfeld weg oder ändert GraphQL seine Semantik für `latestOpinionatedReviews`,
  scheitert die Query laut (Exit ≠ 0) und der Befundstand ist „nicht festgestellt" — nie „keine".
- **Was die Fangform nicht leistet:** Sie ist eine Text- und Wächtertest-Schranke, keine
  Laufzeitschranke. `errors`-Einträge ohne `message` ergeben bei `gh` Exit `0` mit angewendetem
  `--jq` — dann fälschlich „keine offen"; ein `errors`-Zähler als Feld der Auswertungsgrenze wurde
  verworfen, weil die GraphQL-Spezifikation `message` erzwingt und das fünfte Feld den leeren Fall
  mit dem Fehlerfall vermischt hätte.
- Was diese Entscheidung nicht leistet: Sie liest keine Issue- und keine Konversationskommentare,
  keine Check-Run-Annotationen und keine Repository-Alerts ohne Pull-Request-Bezug.
