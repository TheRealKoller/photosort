# 0069 - Ansichtsentwürfe sind Handarbeit in Penpot; das Repository führt nur ihre Soll-Struktur

**Status:** Accepted
**Datum:** 2026-09-09
**Bezug:** [GitHub-Issue #358](https://github.com/TheRealKoller/photosort/issues/358), [`features/0358-projektverwaltung-entwurf.md`](../features/0358-projektverwaltung-entwurf.md), [`decisions/0065-penpot-als-design-quelle-rangfolge-umgekehrt.md`](./0065-penpot-als-design-quelle-rangfolge-umgekehrt.md), [`decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md)

**Berührt außerdem (keine Ablösung):**
- [`decisions/0066`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md) Abschnitt 1 (die Nutzlast liegt im Repository, getrennt in erzeugte Daten und handgeschriebene Aufbaulogik): unverändert gültig **für Tokens, Symbole und Bausteine**. Diese ADR entscheidet, dass die Konstruktion auf **Ansichten** ausdrücklich *nicht* ausgedehnt wird, und begründet, warum das kein Bruch, sondern die Konsequenz derselben Regel ist.
- [`decisions/0066`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md) Abschnitt 6, letzter Absatz („Nichts aus der Instanz wird eingecheckt"): **unverändert und wortgleich bestätigt**, ausdrücklich auch für Bilder — siehe Abschnitt 7 unten. Diese ADR nimmt nichts zurück.
- [`decisions/0058-browsergestuetzte-oberflaechenpruefung.md`](./0058-browsergestuetzte-oberflaechenpruefung.md) Punkt 7 (die zwei festen Viewports): unverändert gültig und hier **übernommen** statt danebengestellt — siehe Abschnitt 3.

## Kontext

Penpot ist seit ADR 0065 die alleinige Design-Quelle und trägt seit Spec 0352 den Tokensatz, die
zwölf Symbole und die Bausteine. Was es dort bis heute **nicht** gibt, ist eine einzige
Produktansicht. Spec 0358 entwirft die erste — und legt damit zwangsläufig das Muster fest, dem
jeder weitere Entwurf folgt.

Die naheliegende Antwort wäre, das Muster von ADR 0066 fortzuschreiben: eine fünfte Nutzlast
(`seed-views.js` + `views.json`) in derselben mechanischen Form wie die vier bestehenden Schritte.
Sie ist falsch, und zwar aus dem Grund, der ADR 0066 selbst trägt.

**Ein Ansichtsentwurf besteht fast vollständig aus Werten.** Position, Größe, Reihenfolge,
Schachtelung, Beispieltexte, Umbruchverhalten — das ist die Ansicht. ADR 0066 Abschnitt 1 verbietet
genau das im Repository: „Werte werden nie in eine Nutzlast getippt." Für Tokens und Symbole ließ
sich die Regel einhalten, weil deren Werte aus `index.css` bzw. `icon.tsx` **erzeugt** werden. Für
eine Ansicht gibt es keine solche Quelle: Die Ansicht existiert im Produkt noch nicht (das ist der
Zweck der Story), es gibt also nichts, woraus man sie erzeugen könnte. Eine `views.json` mit
Koordinaten wäre keine Ableitung, sondern eine getippte Wertekopie — und noch dazu die erste, die
niemand gegen eine Quelle prüfen könnte.

**Der zweite Grund ist die Rangfolge.** Nach ADR 0065 entscheidet Penpot, wie eine Ansicht
aussehen *soll*. Ein Generator im Repository holte diese Entscheidung durch die Hintertür zurück:
Jede Layoutänderung liefe dann über einen Pull Request auf eine JSON-Datei statt über die Fläche,
auf der man sie sieht. Das ist genau der Zustand, den Spec 0352 abgeschafft hat.

**Der dritte Grund ist die Lebensdauer.** `seed-components.js` trägt die Laufregel
`nur-auf-leerer-datei`: Nach dem ersten Bespielen gehören die Bausteine Penpot. Ein `seed-views.js`
stünde vom ersten Tag an unter derselben Regel — es dürfte genau einmal laufen und wäre danach
unausgeführter, alternder Code, dessen Kosten sich über keine einzige Iteration amortisieren.

Was dagegen **nicht** entfällt, ist die Nachprüfbarkeit. Ohne irgendeine Soll-Aussage im
Repository ist ein Instanzverlust bei den Ansichten nicht einmal *erkennbar*: `verify.js` zählt
heute Tokens, Symbole und Bausteine, und eine Datei ohne Ansichten sähe für es aus wie eine
vollständige.

## Entscheidung

### 1. Kein `seed-views.js`. Der Ansichtsentwurf entsteht von Hand in Penpot

Ansichten werden über den Skill `penpot-design`, Schritt „Entwerfen mit der Bibliothek", in der
Hauptsession aufgebaut — aus Bibliotheks-Instanzen und Tokens, nicht aus einer Datendatei. Es
entsteht **keine** fünfte Zeile in der Schritttabelle „Skript / Datendatei / Einfügename"; die
Tabelle bleibt bei vier Einträgen.

Das ist keine Aufweichung von ADR 0066, sondern ihre Anwendung: Die Regel lautet nicht „alles muss
ein Skript sein", sondern „**Werte werden nie getippt**". Wo ein Wert aus einer Quelle erzeugbar
ist, wird er erzeugt (Tokens, Symbole). Wo eine Struktur aus dem Produktcode ableitbar ist, steht
sie als Matrix im Repository (Bausteine). Wo etwas **neu entschieden** wird und nirgends
vorliegt — eine Ansicht — gehört es an den Ort, an dem entschieden wird.

### 2. Das Repository führt die Soll-Struktur: `design/penpot/views.json`

Eine sechste Datei tritt zu `design/penpot/` hinzu, aber **nicht als Nutzlast**: `views.json` wird
nie ausgeführt und an kein Skript übergeben. Sie ist die **Soll-Aussage**, gegen die das Rücklesen
vergleicht — dieselbe Rolle, die `components.json` für die Bausteine spielt, nur eine Ebene
gröber.

Sie führt je Ansicht: den maschinellen Schlüssel, den Anzeigenamen, den Namen der Penpot-Seite, die
Produktdatei(en), auf die sich der Entwurf bezieht (leer, solange es sie nicht gibt), die Liste der
Breiten, die Liste der Zustände, die Liste der **Bausteinschlüssel**, die in der Ansicht
instanziiert sein müssen, und die benannten **Lücken** (Abschnitt 5).

Sie führt **keine** Koordinate, keine Größe, keinen Farbwert und keinen Beispieltext. Sie tritt der
Suchraumliste der Wertfreiheits-Zusicherung in `frontend/penpot/payload.test.ts` bei (heute fünf
Dateien, danach sechs) — dieselben vier Musterfamilien wie für die handgeschriebene Nutzlast. Wo
`views.json` einen Tokennamen nennt, gilt für ihn dieselbe referentielle Integrität wie für
`components.json`.

Damit ist im Diff überprüfbar, **dass** und **wie** eine Ansicht abgelegt ist, ohne dass das
Repository behauptet, wie sie aussieht.

### 3. Das Ablagemuster: eine Seite je Ansicht, ein Brett je Breite, Zustände als Variantenachse

Verbindlich für diese und jede weitere Ansicht:

- **Eine Penpot-Seite je Ansicht**, benannt `Ansicht — <Anzeigename>`. Ansichten werden nicht auf
  einer gemeinsamen Seite gestapelt: Eine Seite ist die einzige Gliederungsebene, die Penpot
  oberhalb des Bretts anbietet, und sie kostet nichts.
- **Ein Brett je Breite**, nebeneinander auf derselben Seite. Zwei Breiten, keine dritte:
  `mobile` und `desktop`. Die Maße sind **nicht neu gewählt**, sondern die beiden bereits
  festgelegten Prüfbreiten des Projekts (`e2e/lib/viewports.ts`, ADR 0058 Punkt 7): 360 × 740 und
  1280 × 800. Ein Entwurf in einer dritten, nur hier gültigen Breite wäre mit dem späteren
  Browser-Nachweis (`browse-app`) nicht mehr vergleichbar — und genau dieser Vergleich ist der
  Sinn eines Entwurfs vor dem Bau.
- **Zustände sind eine Variantenachse `zustand`, keine zweite Zeichnung.** Hat eine Ansicht mehr
  als einen Zustand, wird je Breite ein Varianten-Container mit der Achse `zustand` angelegt
  (`penpotUtils.createVariantContainer`, gemessen tragfähig); umgeschaltet wird über
  `switchVariant`. Hat eine Ansicht nur einen Zustand, bleibt es beim einfachen Brett — eine Achse
  mit genau einem Wert beschriebe nichts und ist an der Plugin-API zudem ungemessen.
- **Die Breite ist ausdrücklich keine Variantenachse.** Beide Breiten sollen **gleichzeitig zu
  sehen** sein; eine umschaltbare Breite zeigte immer nur eine von beiden und machte den Vergleich
  der Aufteilungen unmöglich, der der Zweck der zweiten Breite ist.

### 4. Wiedererkannt wird an Plugin-Daten, nie am Namen

Jedes Ansichtsbrett trägt die Plugin-Daten `ansicht` (Schlüssel der Ansicht) und `breite`
(`mobile`/`desktop`); ein Varianten-Container trägt zusätzlich seine Achse über `variantProps`.

Das ist wortgleich das Muster, das ADR 0066 für die Bausteine gemessen hat und aus demselben Grund:
`createVariantContainer` benennt Einzelkomponenten in „Component" um, ein Anzeigename ist frei
änderbar, und ein Vergleich am Namen geht nach der ersten Umbenennung ins Leere. Der Anzeigename
darf sich ändern, ohne dass das Rücklesen bricht.

### 5. Eine Eigenschaft ohne Token ist eine ausgewiesene Lücke, nie ein erledigter Punkt

Beim Entwerfen gilt die Dauerregel des Skills unverändert: Jede Eigenschaft, für die ein Token
existiert, wird über das Token gesetzt. Wo es keines gibt, wird der Wert gesetzt **und die Stelle
als Lücke in `views.json` geführt** — mit Stelle und Grund, in Worten, ohne den Wert selbst.

Zwei Lücken sind schon jetzt absehbar und werden nicht stillschweigend geschlossen: Es gibt
**kein Breakpoint-Token** (die beiden Brettbreiten stehen nur in `e2e/lib/viewports.ts`), und es
gibt **kein Token für Bewegung** (der Platzhalter pulsiert im Produkt; Penpot bildet das nicht ab).
Beides ist eine Lücke des Tokensatzes, keine Erlaubnis zum freien Wert — ob sie geschlossen wird,
entscheidet eine eigene Story.

### 6. `verify.js` liest Ansichten mit zurück; der Vergleich bleibt außerhalb

`verify.js` bekommt weiterhin **keine** Datendatei mitgegeben (statisch eingefroren) und
entscheidet weiterhin nichts. Es liefert zusätzlich zum heutigen Ergebnis eine Ansichtsliste:
je Brett die Plugin-Daten `ansicht`/`breite`, die Varianteneigenschaften und die Zahl ihrer
Ausprägungen, die Zahl der enthaltenen **Bibliotheks-Instanzen**, die Zahl der Formen, die
**keine** Instanz sind, und die im Unterbaum gesetzten Tokenbindungen.

Zwei dieser Zahlen tragen je ein Akzeptanzkriterium und sind deshalb keine Zierde: Die Zahl der
Nicht-Instanzen ist der einzige mechanische Hinweis auf „nachgezeichnet statt zusammengesetzt", und
die Bindungsliste ist derselbe Nachweis, den ADR 0066 Abschnitt 6 für die Bausteine führt.

Dazu treten neue erwartete Kardinalitäten (`ERWARTETE_ANSICHTEN`, `ERWARTETE_ANSICHTSBRETTER`) neben
die vier bestehenden — aus demselben Grund wie diese: Ohne sie wäre ein abgeschnittenes Ergebnis
von einem vollständigen nicht zu unterscheiden, und ein Instanzverlust bei den Ansichten fiele
niemandem auf. **Achtung bei der Umsetzung:** Die Freigabeliste der blanken Zahlen in
`payload.test.ts` ist an Datei **und Zeilennummer** gebunden; jede Zeile, die oberhalb der
bestehenden vier Konstanten eingefügt wird, verschiebt alle vier Einträge.

Der Vergleich gegen `views.json` findet wie bisher **außerhalb** statt, mechanisch, in der
Hauptsession — nicht in `verify.js`.

### 7. Der Bildexport wird **nicht** eingecheckt — die Regel wird bei ihrer ersten Belastungsprobe nicht aufgeweicht

ADR 0066 Abschnitt 6 schließt aus, dass etwas aus der Instanz eingecheckt wird. Ein Ansichtsentwurf
ist die **erste Gelegenheit, an der man diese Regel hätte aufweichen können** — und der Grund wäre
gut gewesen: Ein Formexport zeigt keine Adresszeile, ein Bild trägt keinen maschinenlesbaren Wert
und kann mit `index.css` nicht in Widerspruch geraten, und Binärdateien sind im Repository nicht
neu (`scripts/demo_photos/*.jpg`). Die Regel wird trotzdem **nicht** aufgeweicht.

Der Ausschlag gibt die Menge, nicht der Einzelfall: Vierzehn Bretter allein in dieser Story, und
jede weitere Ansichts-Story folgte demselben Muster. Eine Ausnahme, die mit jeder Story wächst, ist
keine Ausnahme mehr, sondern eine zweite Ablage — und zwar eine, die ab dem Tag ihrer Erstellung
veraltet, weil in Penpot weiterentworfen wird und niemand ein Bild nachzieht. Genau diese Sorte
mitwachsender, still veraltender Kopie ist der Gegenstand der ursprünglichen Regel.

**Der Ablauf ist deshalb:** `export_shape` auf die **Form** (nie ein Fensterabzug — ein
Bildschirmfoto trüge die Adresszeile), Ablage als Datei im Arbeitsbaum **außerhalb der
Versionskontrolle**, Übergabe an Daniel, Anhängen an den Pull Request.

**Das Anhängen ist ein Handgriff von Daniel im Browser, kein automatisierbarer Schritt.** Das steht
hier ausdrücklich und nicht als Randnotiz, weil die Formulierung „die Bilder hängen am Pull
Request" sonst zwangsläufig für automatisierbar gehalten wird: `gh` kennt keinen Bild-Upload,
GitHubs Anhang-Endpunkt für Kommentare ist nicht öffentlich dokumentiert, und der
Operationskatalog `github-access` führt aus demselben Grund keine Operation dafür. Wer hier eine
Automatisierung sucht, sucht etwas, das es nicht gibt. Der Abschluss einer Ansichts-Story hängt an
diesem Handgriff — er gehört in die Übergabe an Daniel, nicht in eine Erledigt-Meldung.

**Ablageort:** `design/penpot/ansichten/` — neben der Nutzlast, auf die sich die Bilder beziehen.
Der Pfad ist heute von `.gitignore` **nicht** gedeckt (geprüft: kein Treffer); der Eintrag entsteht
mit dieser Story. Er wird ausdrücklich nicht auf ein bestehendes ignoriertes Verzeichnis
umgebogen: `e2e/artifacts/` gehört der browsergestützten Oberflächenprüfung, und seine Begründung
in `.gitignore` benennt genau diese Herkunft. Zwei Werkzeuge in einem Ausgabeverzeichnis wären ab
dem ersten Aufräumen ein Rätsel.

**Was weiterhin nicht eingecheckt wird, ist damit vollständig:** kein `.penpot`-Export, kein
Fensterabzug, kein Prüfbericht als Datei, keine eingefügte Werkzeugausgabe — und kein Bild.

**Der Preis wird bewusst getragen:** Wer diese Spec in einem Jahr liest, hat **kein Bild im
Repository**. Er muss den Pull Request heraussuchen oder Penpot öffnen. Die dauerhafte Spur des
Entwurfs im Repository sind `views.json` (welche Ansichten in welchen Breiten und Zuständen
existieren, aus welchen Bausteinen sie bestehen, welche Lücken sie tragen) und der UI/UX-Abschnitt
der Spec, der die Aufteilung in Worten beschreibt. Das ist weniger als ein Bild und mehr als
nichts — und es ist die einzige Fassung, die nicht veraltet, weil sie Struktur beschreibt statt
Aussehen.

### 8. Ausführungsteilung: was die Hauptsession tut und was ein Subagent tun kann

Unverändert nach ADR 0066 Abschnitt 5, hier nur für Ansichten ausbuchstabiert: Subagenten dieses
Repositorys haben keine MCP-Werkzeuge. **Jede** Handlung an der Instanz — Vorprüfung, Entwerfen,
Varianten, Rücklesen, Bildexport zur Übergabe — läuft in der Hauptsession über den Skill
`penpot-design` und setzt eine von Daniel geöffnete, verbundene Sitzung voraus. Das Anhängen der
Bilder an den Pull Request ist danach Daniels Handgriff (Abschnitt 7) und liegt außerhalb jeder
Session. Alles Repositoryseitige (`views.json`,
`components.json`, `payload.test.ts`, `verify.js`, Skript- und Skill-Texte, Doku) ist gewöhnliche
Subagenten-Arbeit im TDD-Zyklus.

## Begründung

Der tragende Gedanke ist eine Unterscheidung, die ADR 0066 implizit schon trifft und die hier
ausgesprochen wird: **Das Repository führt, was ableitbar oder abzählbar ist; Penpot führt, was
entschieden wird.** Tokens sind ableitbar (aus `index.css`), Bausteinvarianten sind abzählbar (aus
dem Produktcode), eine Ansicht ist weder das eine noch das andere — sie ist die Entscheidung
selbst.

Die zweite Überlegung betrifft die Nachprüfbarkeit. Der Verzicht auf einen Generator hätte fast dazu
verführt, auch auf die Soll-Aussage zu verzichten („die Ansicht lebt ja in Penpot"). Das wäre die
teure Hälfte des Fehlers gewesen: Ein Instanzverlust bliebe unentdeckt, und „aus Instanzen
zusammengesetzt statt nachgezeichnet" bliebe eine Behauptung. `views.json` kostet wenig und macht
beides mechanisch prüfbar, ohne eine Layoutsprache zu erfinden.

Die dritte ist die Wahl der Brettbreiten. Zwei neue Zahlen zu setzen wäre bequemer gewesen, hätte
aber dauerhaft zwei Sätze von „Handy-Breite" im Projekt hinterlassen — und der Entwurf wäre
gegenüber dem einzigen Werkzeug, das ihn später am laufenden Produkt nachprüfen kann, nicht mehr
deckungsgleich.

## Konsequenzen

- **Positiv:** Kein Generator, der nach einem Lauf altert. Das Layout bleibt dort, wo es entschieden
  wird. Ein Instanzverlust ist für Ansichten erkennbar, nicht nur für Tokens und Bausteine. Der
  Entwurf entsteht in derselben Breite, in der er später am laufenden Produkt geprüft wird. Das
  Repository bleibt frei von mitwachsenden Binärdateien, die niemand nachzieht.
- **Negativ / bewusst getragen:**
  - **Ansichten sind nach einem Instanzverlust nicht wiederherstellbar — und seit Abschnitt 7 nicht
    einmal ansehbar.** Tokens, Symbole und Bausteine kommen aus den Skripten zurück. Von einer
    Ansicht bleiben **nur** diese Spec und `views.json`: welche Bretter in welchen Breiten und
    Zuständen es gab, aus welchen Bausteinen sie bestanden, welche Lücken sie trugen — nicht, wie
    sie aussahen. Sie kommt ausschließlich durch **erneutes Entwerfen von Hand** zurück, und zwar
    ohne Vorlage. Das ist die schärfste Grenze dieser Konstruktion und der Preis zweier bewusster
    Entscheidungen zugleich (kein Generator, kein eingechecktes Bild); sie wird hier benannt, damit
    später niemand die Skripte für vollständig hält.
  - **Der Entwurf ist im Repository nicht vorführbar.** Wer ihn sehen will, braucht den Pull
    Request oder Penpot.
  - **Der Abschluss einer Ansichts-Story hängt an einem Handgriff von Daniel** (Bilder an den Pull
    Request hängen, Abschnitt 7). Automatisieren lässt er sich nicht.
  - **Jede Ansicht kostet Hauptsessionzeit mit verbundener Instanz.** Es gibt keinen
    Hintergrundlauf, der Ansichten nachzieht.
  - **`views.json` kann inhaltlich lügen.** Sie sichert Struktur, nicht Gestaltung: Dass vier
    Bretter existieren, heißt nicht, dass der Entwurf gut ist. Diese Beurteilung bleibt eine
    Handlung — wie schon der Wertabgleich in ADR 0066 Abschnitt 7.
- **Folgearbeit:** Der Bau der Ansicht im Code ist eine eigene Story. Ob die beiden hier benannten
  Lücken (Breakpoint-Token, Bewegungstoken) geschlossen werden, entscheidet ebenfalls eine eigene
  Story — diese ADR entscheidet nur, dass sie als Lücken geführt werden statt als freie Werte.
