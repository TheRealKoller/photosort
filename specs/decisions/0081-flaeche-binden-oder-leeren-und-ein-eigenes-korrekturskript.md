# 0081 - Eine Variante bindet ihre Fläche oder leert sie ausdrücklich; der bespielte Stand wird über ein eigenes Korrekturskript nachgezogen

**Status:** Accepted
**Datum:** 2026-09-11
**Bezug:** [GitHub-Issue #377](https://github.com/TheRealKoller/photosort/issues/377), [`decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md), [`decisions/0065-penpot-als-design-quelle-rangfolge-umgekehrt.md`](./0065-penpot-als-design-quelle-rangfolge-umgekehrt.md)

## Kontext

Ein neu erzeugtes Penpot-Board trägt eine **deckend weiße** Standardfüllung, nicht etwa keine.
`seed-components.js` setzt eine Füllung ausschließlich dort, wo die Variante eine Rolle `flaeche`
führt; wo sie fehlt, bleibt die weiße Standardfüllung stehen. Betroffen sind 29 der 158 Varianten.

Damit fallen zwei unterschiedliche Sachverhalte auf dieselbe Darstellung zusammen: „im Produkt
transparent" und „Fläche vergessen". Beide sehen in der Datei gleich aus, und der Rückleser
`verify.js` kann sie nicht unterscheiden — eine nicht gebundene Standardfüllung ist keine Bindung
und taucht in seiner Rückgabe nirgends auf.

Der Fehler lässt sich außerdem nicht durch einen erneuten Lauf beheben: `seed-components.js` trägt
die Laufregel `nur-auf-leerer-datei` und einen fail-closed-Wächter, weil der bespielte Stand nach
ADR 0065 das Original ist, keine Kopie. Ein Wiederaufbau zur Reparatur vernichtete die von Hand in
Penpot entstandenen Ansichten, die nach einem Verlust nicht wiederherstellbar sind.

## Entscheidung

### 1. Jedes Variantenbrett bindet eine Fläche **oder** wird ausdrücklich geleert

`baueVariante` schließt jedes Brett mit genau einem von beidem ab. Ob geleert wird, wird **aus der
tatsächlich vollzogenen Bindung abgeleitet**, nicht aus einer zweiten Auswertung der Datendatei:
Wurde auf das Brett keine Eigenschaft `fill` angewandt, wird `fills = []` gesetzt. Die Bedingung
kann von der Bindungslogik damit nicht abweichen, weil sie ihr Ergebnis ist.

Geleert wird **nach** dem Binden, nicht davor. Eine Bindung, die auf ein geleertes Brett folgt,
ist unbelegt; das Leeren an der Stelle, an der nachweislich nichts gebunden wurde, ist es nicht —
und es fasst kein Brett an, das seine Fläche bereits trägt.

### 2. Eine fehlende Rolle `flaeche` ist eine Aussage, keine Lücke

In `components.json` heißt die Abwesenheit einer Rolle `flaeche` ab jetzt: **im Produkt ist diese
Fläche transparent.** Weil eine Abwesenheit sich nicht begründen kann, wird sie **je Ausprägung
namentlich mit Grund geführt** — in derselben Bauart wie die Ausnahmeliste der tokenlosen Achsen,
einschließlich der Gegenrichtung (kein verwaister Eintrag, kein ungeführter Fall).

Daraus folgt für die Rollen insgesamt: Eine Rolle in `components.json` bildet entweder auf eine
Penpot-Eigenschaft ab, oder sie gehört namentlich und mit Grund zu den Unterelementen, die dieser
Aufbau nicht selbst setzt. Eine dritte Möglichkeit — eine Rolle, die stillschweigend im Bericht
`nachzubinden` landet, obwohl sie die Fläche des Bretts selbst meint — gibt es nicht. `spur` war
genau dieser Fall und ist deshalb dort, wo sie die Fläche des Bausteins meint, die Rolle `flaeche`.

### 3. Kriterium „nach Wiederaufbau richtig" und Kriterium „heutiger Stand richtig" sind zwei Wege

Sie werden **nicht** in einem Weg zusammengeführt.

- **Wiederaufbau:** `seed-components.js` und `components.json`. Laufregel unverändert
  `nur-auf-leerer-datei`, Wächter unverändert fail-closed.
- **Bespielter Stand:** ein eigenes, eng zugeschnittenes Korrekturskript `fix-flaechen.js` neben
  den Aufbauskripten, Laufregel `jederzeit-wiederholbar`.

Das Korrekturskript fasst **ausschließlich die Füllung der Variantenbretter** an — keine Struktur,
keine Beschriftung außer ihrer Farbe, keine Position, keine Löschung. Es leitet sein Soll
vollständig aus `components.json` ab; eine Gestaltungsabsicht, die nicht im Repository steht, kann
in ihm nicht stecken. Was es mit `seed-components.js` teilt, steht in beiden Dateien **wortgleich**
und ist statisch zugesichert — dieselbe Vorkehrung, die die Bausteinerkennung trägt.

Ein Handgriff außerhalb des Repositories scheidet aus: Bei `execute_code` ist das Review die
einzige Instanz zwischen einer Zeile und ihrer Ausführung in einer angemeldeten Sitzung. Ad-hoc-Code
hat diese Instanz nicht, und 29 Varianten von Hand nachzuziehen ist weder wiederholbar noch prüfbar.

### 4. Der Rückleser belegt die Abwesenheit als Zählwert, nicht als Wert

`verify.js` gibt je Baustein zwei Zählwerte zurück: die Zahl der Variantenbretter **ohne Füllung**
und die Zahl der Bretter mit Füllung **ohne Tokenbindung darauf**. Der zweite ist der eigentliche
Befund — eine Fläche, die aus keinem Token stammt — und muss über alle Bausteine null sein.

Zurück kommen zwei Zahlen, **kein Farbwert**. Der Vergleich gegen das Soll entsteht wie jeder
andere außerhalb, gegen `components.json`.

## Begründung

Die Alternative zu Abschnitt 1 wäre, das Brett unbedingt vor dem Binden zu leeren. Sie ist kürzer,
verlässt sich aber auf ein ungemessenes Zusammenspiel zweier Schreibvorgänge an 158 Stellen und
fasst dabei 129 Bretter an, die heute richtig sind. Die gewählte Form fasst genau die an, die es
nicht sind.

Die Alternative zu Abschnitt 2 wäre, `spur` zusätzlich auf `fill` abzubilden. Dann trügen zwei
Rollennamen dieselbe Penpot-Eigenschaft, und bei der Fortschrittsanzeige schrieben beide auf
dasselbe Brett — welche gewinnt, entschiede die Aufrufreihenfolge. Ein Sonderweg für den Einzelfall
ist genau die Stelle, an der es später wieder auseinanderläuft.

Die Alternative zu Abschnitt 3 wäre, den bespielten Stand über einen Wiederaufbau zu heilen. Sie
kostet die Ansichten und ist damit keine.

## Konsequenzen

- Die Nutzlast hat eine fünfte handgeschriebene Datei und damit eine dritte Rolle neben „aufbauen"
  und „zurücklesen": **korrigieren**. Sie tritt dem Suchraum der statischen Regeln bei; ihre
  Laufregel, ihr Mindestumfang und ihre geteilten Blöcke werden wie bei den übrigen eingefroren.
- Ein künftiger Baustein ohne Fläche muss seinen Fall eintragen und begründen. Das ist die Absicht.
- Ob eine Beschriftung auf ihrem Untergrund lesbar ist, bleibt eine Sichtprüfung: Der Grund der
  Penpot-Seite steht nicht im Repository, und kein Skript setzt ihn.
- Was diese Entscheidung nicht leistet: Sie macht aus einem Bibliotheks-Baustein kein Gebilde mit
  Unterelementen. Knauf, Füllbalken und Statuspille bleiben ungebaut und weiterhin als
  `nachzubinden` berichtet.
