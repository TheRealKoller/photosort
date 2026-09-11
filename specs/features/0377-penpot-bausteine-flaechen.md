# 0377 - Penpot-Bausteine tragen die Flächen des Produkts

**Status:** Accepted
**Erstellt:** 2026-09-11
**Bezug:** [GitHub-Issue #377](https://github.com/TheRealKoller/photosort/issues/377), ADR [`0083`](../decisions/0083-flaeche-binden-oder-leeren-und-ein-eigenes-korrekturskript.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Fall-Entscheidung je betroffener
Variante (Akzeptanzkriterium 2) und die Kontrastpaarungen (Kriterium 3) tabellarisch geführte
Zusicherungen sind, die nirgends sonst stehen — und weil drei Fallen benannt sind, die grün
durchlaufen würden, statt rot zu werden.

## Ziel

Seit der Umstellung auf Penpot als alleinige Gestaltungsquelle entsteht jede neue Ansicht dort als
Entwurf, bevor sie gebaut wird. Die Bausteinbibliothek bildet das Produkt an einer Stelle falsch
ab: Varianten, die im Produkt keine eigene Fläche tragen, erscheinen in Penpot als deckend weiße
Kästen. Auf dem dunklen Seitengrund erreicht die Beschriftung dort rund 2,2:1 und verfehlt die
Barrierefreiheits-Untergrenze deutlich.

Wer heute entwirft, muss die Flächen in jedem einzelnen Entwurf von Hand leeren; wer einen Entwurf
ansieht, beurteilt einen Kontrast, den das fertige Produkt gar nicht hat. Beides trifft die
Entwurfsarbeit selbst: Der Zweck der Umstellung war, eine Ansicht vor dem Bauen beurteilen zu
können.

## Befund

Ein neu erzeugtes Penpot-Board trägt eine **deckend weiße** Standardfüllung, nicht etwa keine.
`bindeRollen` in `design/penpot/seed-components.js` setzt `fill` ausschließlich dort, wo die
Variante eine Rolle `flaeche` führt; fehlt sie, bleibt Weiß stehen. Betroffen sind **29 der 158
Varianten** über vier Bausteine:

| Baustein | betroffen | welche |
|---|---|---|
| Schaltfläche | 24 von 90 | `ghost` und `link`, über alle Größen und vier der fünf Zustände |
| Kennzeichen | 1 von 9 | `neutral` |
| Schalter | 3 von 3 | alle |
| Fortschrittsanzeige | 1 von 2 | `determiniert` |

Nicht betroffen sind Bausteine, die eine Grundfläche für alle ihre Varianten führen. Der Zustand
`disabled` der Schaltfläche erbt über `tokensProAuspraegung.zustand.disabled` eine Fläche
(`color.surface`) — die sechs Varianten `ghost`/`link` × `disabled` sind deshalb **nicht** unter
den 29 und dürfen nicht geleert werden.

Die Zahl 158 ersetzt die 146 aus dem Issue-Text: `components.json` führt inzwischen zwölf
Bausteine (Kategorie-Chip und Schrittmarke kamen hinzu, beide mit Fläche je Ausprägung).

## User Story

Als Gestalter einer neuen Ansicht möchte ich, dass die Bausteine in Penpot dieselbe Fläche zeigen
wie im fertigen Produkt, damit ein Entwurf ohne Handgriffe belastbar ist und ich Kontrast und
Wirkung schon am Entwurf beurteilen kann statt erst am gebauten Bildschirm.

## Akzeptanzkriterien

Kriterium 1, 3, 4, 5 und 6 sind gegenüber dem Issue-Body auf Testbarkeit geschärft; der fachliche
Gehalt ist unverändert. Was daran geändert wurde und warum, steht unter "Entscheidungen".

- [ ] **1.** Von den 158 Variantenbrettern tragen nach der Korrektur **133** eine tokengebundene
      Fläche und **25** ein ausdrücklich geleertes `fills`. Kein Brett trägt eine Füllung ohne
      Tokenbindung: der Rückleser meldet `variantenMitFuellungOhneBindung` über alle Bausteine
      als 0.
- [ ] **2.** Für jede betroffene Variante ist entschieden und festgehalten, welcher der beiden
      Fälle vorliegt: Die Fläche ist im Produkt tatsächlich transparent — dann ist sie es in
      Penpot ebenfalls; oder es fehlt eine Fläche, die das Produkt zeigt — dann trägt die Variante
      sie. Festgehalten wird das in einer eingefrorenen Ausnahmeliste, nicht im Fließtext.
- [ ] **3.** Die Beschriftung jeder betroffenen Variante erreicht gegen den Untergrund, auf dem
      sie im Entwurf steht, mindestens die WCAG-AA-Untergrenze. Nachgewiesen wird die
      **Token-Paarung** (Schriftfarbe gegen gebundene Fläche, bei den transparenten Varianten
      gegen `color.bg`), gerechnet aus `design/penpot/tokens.json`. Ausgenommen sind inaktive
      Bedienelemente — die im Design-System dokumentierte WCAG-Ausnahme (1.4.3 / 1.4.11). Geführt
      wird sie über ihre **Bedingung**, nicht als Namensliste: Schriftfarbe `color.text-disabled`
      **und** eine Ausprägung `disabled` in der Kombination. Das trifft über alle Bausteine **21**
      Varianten (Schaltfläche 18, Eingabefeld 1, Auswahlkästchen 1, Schalter 1); die Zahl ist
      eingefroren, damit die Ausnahme nicht still um sich greift. Dass der Seitengrund tatsächlich
      `color.bg` ist, wird beim Nachziehen gesetzt und bleibt Sichtprüfung.
- [ ] **4.** Die Korrektur wirkt dauerhaft: Nach einem Verlust und Wiederaufbau der Penpot-Datei
      ist der Fehler nicht zurück. Nachgewiesen wird die **Bedingung** — dass
      `seed-components.js` und `components.json` den korrigierten Zustand erzeugen —, nicht die
      Wirkung eines tatsächlichen Wiederaufbaus.
- [ ] **5.** Der heutige Stand der Penpot-Datei ist nachgezogen — die betroffenen Varianten sehen
      auch in der bereits bespielten Datei richtig aus. Das setzt eine geöffnete, verbundene
      Penpot-Sitzung voraus und ist ohne Daniel nicht abschließbar. **Dieses Kriterium blockiert
      den Pull Request nicht; es wird nach dem Lauf gesondert quittiert.**
- [ ] **6.** Die Brettfüllung der 129 heute korrekt gebundenen Varianten bleibt unverändert —
      weder wird sie geleert noch an ein anderes Token gebunden. **Ausgenommen und beabsichtigt:**
      `progress/indeterminate` bekommt eine Beschriftungsfarbe, die es heute nicht trägt; seine
      Fläche bleibt unberührt.
- [ ] **7.** Die Regel, dass die Bausteine nach dem ersten Bespielen Penpot gehören und nicht von
      einem erneuten Aufbau überschrieben werden, bleibt unangetastet: Laufregel und
      fail-closed-Wächter von `seed-components.js` bleiben unverändert.

## Datenmodell-Bezug

Keiner. Die Story berührt ausschließlich die Penpot-Nutzlast unter `design/penpot/` und ihre
statischen Regeln; keine Entität, kein Endpunkt, kein Feld. `docs/architecture.md` und
`docs/setup.md` sind nicht betroffen.

## Architektur / Umsetzung

Grundlage: ADR [`0083`](../decisions/0083-flaeche-binden-oder-leeren-und-ein-eigenes-korrekturskript.md).

**Der Mechanismus.** `baueVariante` schließt jedes Brett mit genau einem von beidem ab: gebundene
Fläche **oder** ausdrücklich geleerte Füllung (`brett.fills = []`). Geleert wird **nach** dem
Binden und nur dort, wo `bindeRollen` nachweislich keine Eigenschaft `fill` auf das Brett
angewandt hat — `bindeRollen` gibt die gesetzten Brett-Eigenschaften dazu zurück. Die Bedingung
ist damit das Ergebnis der Bindungslogik und kann nicht von ihr abweichen; die 133 gebundenen
Bretter werden gar nicht erst angefasst.

**Fall-Entscheidung je betroffenem Baustein** (am Produktcode entschieden):

| Baustein / Ausprägung | Var. | Was das Produkt zeigt | Fall | Umsetzung in `components.json` |
|---|---|---|---|---|
| `button` / `ghost` | 12 | `bg-transparent` | transparent | keine `flaeche`; Eintrag in der Ausnahmeliste |
| `button` / `link` | 12 | `bg-transparent`, Unterstreichung statt Fläche | transparent | keine `flaeche`; Eintrag in der Ausnahmeliste |
| `badge` / `neutral` | 1 | nur `border-border` + `text-text`, kein `bg-*` | transparent | keine `flaeche`; Eintrag in der Ausnahmeliste |
| `switch` (alle 3) | 3 | `bg-overlay` / `bg-accent` / `disabled:bg-surface` | Fläche fehlt | Rolle `spur` → `flaeche` |
| `progress` / `determiniert` | 1 | `bg-separator` | Fläche fehlt | Rolle `spur` → `flaeche` |

**Warum `spur` → `flaeche` und nicht `ROLLE_ZU_EIGENSCHAFT` erweitern.** `spur` meint bei beiden
Bausteinen die Füllung des Wurzelelements, also genau das, was `flaeche` heißt — sie stand nur im
falschen Fach. Zwei Rollennamen auf derselben Penpot-Eigenschaft schrieben bei der
Fortschrittsanzeige beide auf dasselbe Brett, und welche gewänne, entschiede die Aufrufreihenfolge.
`knauf` und `fuellung` bleiben unverändert `nachzubinden` — sie sind Unterelemente und
ausdrücklich nicht Teil dieser Story.

**Schriftfarbe als Folge.** Schalter und Fortschrittsanzeige führen heute **keine** Rolle
`schrift`; ihre Beschriftung steht in Penpots Standardfarbe. Auf der bisherigen weißen Fläche fiel
das nicht auf — auf der gebundenen dunklen Fläche verfehlt es Kriterium 3. Beide bekommen je
Zustand eine `schrift`, abgeleitet aus der Tinte, die das Produkt an dieser Stelle führt:

| Variante | Fläche | Schrift | Kontrast |
|---|---|---|---|
| `switch` / `unchecked` | `color.overlay` | `color.text` | 5,71:1 |
| `switch` / `checked` | `color.accent` | `color.accent-fg` | 10,67:1 |
| `switch` / `disabled` | `color.surface` | `color.text-disabled` | 1,81:1 — WCAG-Ausnahme, siehe UI/UX |
| `progress` / `determiniert` | `color.separator` | `color.text-h` | 8,21:1 |
| `progress` / `indeterminate` | `color.accent` (unverändert) | `color.accent-fg` | 10,67:1 |

**Die Abwesenheit wird geführt, nicht geraten.** Eine fehlende Rolle `flaeche` heißt ab jetzt: im
Produkt ist diese Fläche transparent. Weil eine Abwesenheit sich nicht selbst begründen kann, kommt
in `frontend/penpot/payload.test.ts` eine eingefrorene Ausnahmeliste dazu, dazu eine zweite über
die Rollennamen: Jede Rolle in `components.json` bildet entweder auf eine Penpot-Eigenschaft ab
oder steht dort namentlich mit Grund. Die zweite Liste erzwingt zugleich, dass `spur` nach der
Umbenennung verschwindet — ein stehengebliebener Eintrag wird verwaist und rot.

**Zwei Wege, weil Kriterium 4 und Kriterium 5 verschiedene Fragen sind.**

- *Wiederaufbau (Kriterium 4):* `seed-components.js` + `components.json`. Laufregel unverändert
  `nur-auf-leerer-datei`, Wächter unverändert fail-closed.
- *Bespielter Stand (Kriterium 5):* ein neues, eng zugeschnittenes `design/penpot/fix-flaechen.js`,
  Laufregel `jederzeit-wiederholbar`, Einfügename `BAUSTEINE`. Es findet die Variantenkomponenten
  über die Plugin-Daten `schluessel` — nie am Anzeigenamen —, liest je Komponente `variantProps`,
  bestimmt das Soll aus `BAUSTEINE` und setzt **ausschließlich** die Füllung des Bretts und die
  Farbe seiner Beschriftung. Keine Struktur, keine Position, keine Löschung.
  Zielzustands-idempotent, mit Bericht über geänderte, bereits richtige, strukturell abweichende
  und nicht gefundene Varianten. Ein Wiederaufbau der Datei scheidet als Reparaturweg aus: Er
  kostet die von Hand entstandenen Ansichten, die nach einem Verlust nicht wiederherstellbar sind.

**Mechanischer Beleg.** `verify.js` kann die Abwesenheit heute nicht belegen — eine ungebundene
Standardfüllung ist keine Bindung und taucht in der Rückgabe nirgends auf; ein weißes Brett sieht
dort aus wie ein leeres. Ergänzt werden je Baustein zwei **Zählwerte**: `variantenOhneFuellung` und
`variantenMitFuellungOhneBindung`. Der zweite ist der eigentliche Befund und muss über alle
Bausteine 0 sein. Zurück kommen zwei Zahlen, **kein Farbwert**. Keine neue `ERWARTETE_*`-Konstante,
und die neuen Zeilen gehören **unter** die bestehenden Konstanten — die Freigabeliste der blanken
Zahlen ist an Zeilennummern gebunden.

**Umsetzungsreihenfolge, strikt test-first.** Vorbedingung: `npm ci` in `frontend/`, im Worktree
fehlen die Abhängigkeiten.

1. `frontend/penpot/payload.test.ts` — die beiden eingefrorenen Listen samt Gegenrichtung und
   synthetischer Proben. Rot, weil `spur` heute in keiner Kategorie steht.
2. `design/penpot/components.json` — `spur` → `flaeche` bei `switch` (3×) und `progress` (1×),
   `schrift` je Zustand bei beiden ergänzen. Grün.
3. `payload.test.ts` — die fünfteilige Reihenfolge-Zusicherung über den AST (siehe Teststrategie),
   dann `seed-components.js` entsprechend ändern.
4. `design/penpot/verify.js` — die zwei Zählwerte, mit Test über die Rückgabestruktur.
5. `design/penpot/fix-flaechen.js` — neu, zusammen mit seiner Aufnahme in `NUTZLAST_DATEIEN`,
   `MINDESTZEICHEN`, `LAUFREGELN`, `JS_NUTZLAST` und den geteilten Blöcken; `MINDESTZEILEN` neu
   messen und anheben.
6. `design/penpot/README.md` (Dateitabelle, Schritttabelle, Laufregel-Warnhinweis, die Invariante
   "binden oder leeren"; dabei die veralteten Angaben "elf Bausteine"/"146 Varianten" in den
   Absätzen mitziehen, die ohnehin umgeschrieben werden) und
   `.claude/skills/penpot-design/SKILL.md` (der Korrekturlauf als eigener, ausdrücklich
   anzustoßender Schritt — nie Teil des Normalablaufs), dazu eine Zeile in
   `e2e/tests/toolchain.spec.ts`: jede Datei aus `JS_NUTZLAST` kommt in der Schritttabelle des
   Skills mit ihrem Einfügenamen vor.
7. `specs/architecture/0002-testkonzept.md` — Zahlkorrektur "vier Skripte" → "fünf Skripte" samt
   dritter Rolle *korrigieren*, plus die zwei neuen Regeln aus der Teststrategie.

## Teststrategie

**Ebene.** Ausschließlich statisch, Vitest, `frontend/penpot/payload.test.ts` (plus eine Zeile in
`e2e/tests/toolchain.spec.ts`). Kein Backend, Coverage-Gate unberührt. Die Nutzlast ist zum
PR-Zeitpunkt unausgeführter Code — geprüft werden Erzeugung, Form und referentielle Integrität,
nie die Wirkung eines Plugin-Aufrufs.

**Tragendes Bauteil: eine Simulation, die ihre Tabellen aus der Nutzlast liest.** Eine exportierte
reine Funktion spielt die Bindungsreihenfolge von `baueVariante` nach, gespeist aus
`ROLLE_ZU_EIGENSCHAFT` und `TEXT_ROLLEN`, die über den geparsten Baum aus `seed-components.js`
gelesen werden. Sie liefert je Variante das **zuletzt** aufs Brett gebundene Flächentoken oder
`null`. Eine getippte Liste "diese Varianten haben keine Fläche" wäre eine zweite Wahrheit und ist
ausgeschlossen.

**Zwei eingefrorene Listen mit Gegenrichtung.** (a) Varianten ohne Fläche, je Ausprägung,
Schlüsselform `<schluessel>.<achse>.<auspraegung>`, mit Grund **und der Zahl der gedeckten
ungebundenen Varianten** (ghost 12, link 12, neutral 1, Summe 25). Jede ungebundene Variante ist
von **genau einem** Eintrag gedeckt. Die Zahl ist nötig, weil die Deckung 1:n ist: Eine
Teiländerung lässt einen Eintrag nicht verwaisen, sondern nur schrumpfen — die reine
Verwaisungsprüfung bliebe dabei grün. (b) Rollennamen ohne Penpot-Eigenschaft, je mit Grund, beide
Richtungen; `fuellung` und `knauf` gehören hinein.

**Reihenfolge-Zusicherung über den AST, fünfteilig.** Genau eine `fills`-Zuweisung in
`baueVariante`, Ziel `brett`, Wert leeres Array-Literal; Offset hinter dem letzten
`bindeRollen`-Aufruf; **außerhalb jedes Schleifenknotens**; innerhalb eines `if`, dessen Test den
Akkumulator nennt; kein `bindeRollen`-Aufruf als blankes `ExpressionStatement`. Vier synthetische
Gegenproben (davor, in der Schleife, unbedingt, falsches Ziel) — ohne sie ist das eine Beruhigung,
keine Zusicherung.

**Drei Fallen, die grün durchliefen statt rot zu werden** — sie sind der Grund für die Form oben:

1. **`schrift` bildet ebenfalls auf `fill` ab.** Eine Ableitung "kam eine Rolle vor, die auf `fill`
   abbildet?" zählt `schrift` mit, und `schrift` trägt praktisch jede der 29 Varianten. Der
   Akkumulator sammelt die Eigenschaften, die aufs **Brett** angewandt wurden, nicht die
   vorgekommenen Rollennamen. Wird das verwechselt, bleibt der Test dauerhaft grün, während der
   Fehler unverändert bestehen bleibt.
2. **Akkumulation über *alle* `bindeRollen`-Aufrufe, nicht nur den letzten.** `bindeRollen` läuft
   je Variante ein- bis viermal. Wertet die Ableitung nur den letzten Aufruf aus, werden 16 heute
   korrekte Varianten fälschlich geleert — `alert` (3), `card` (4), `input` (4), `checkbox` (1),
   `skeleton` (2) und, neu durch diese Story, `switch/unchecked` und `progress/determiniert`, deren
   ergänzte `schrift`-Rolle einen Eintrag erzeugt, der *nur* `schrift` führt.
3. **Ein Offset-Vergleich allein belegt die Reihenfolge nicht.** Steht `brett.fills = []` textlich
   hinter dem Aufruf, aber *innerhalb* der Achsenschleife, ist der Offset größer und die Ausführung
   trotzdem falsch. Genau das träfe `button/ghost/disabled`, dessen Fläche erst in der letzten
   Iteration kommt.

**`fix-flaechen.js`.** Der Eintrag in `NUTZLAST_DATEIEN` ist der Rot-Zuerst-Anker und kommt vor der
ersten Zeile der neuen Datei. Neu und inhaltlich tragend: eine **eingefrorene Weißliste der
Schreibaufrufe** (`applyToShapes`, sonst nichts) plus eine Prüfung über `AssignmentExpression` —
die bestehende Verbotsliste sieht Zuweisungen nicht, und `createBoard`, `appendChild`,
`setPluginData` oder eine Zuweisung an `x`/`y`/`name` stehen nicht darin. Ohne sie wäre "fasst
ausschließlich die Füllung an" eine Zusage statt einer Zusicherung. Dazu: keine Zeichenkette in der
Datei, die einem Bausteinschlüssel oder Ausprägungsnamen gleicht — die Gestaltungsabsicht kann
dann nicht im Skript stecken.

**Kontrast wird gerechnet, nicht abgeschrieben.** Kontrastverhältnis aus `tokens.json` gegen
Schwelle 4,5, Untergrund aus der Simulation bzw. `color.bg` bei den transparenten Varianten;
inaktive Bedienelemente als begründete Ausnahme, geführt über ihre Bedingung und mit
eingefrorener Zahl (siehe Kriterium 3 und "Entscheidungen"). Die nachgerechneten Einzelwerte werden **nicht**
eingefroren — sie wären die getippte Wertekopie, gegen die diese Testdatei sonst überall antritt.
Die Helferfunktion wird dupliziert statt geteilt, mit eigenem Referenzpaar-Selbsttest.

**Grenzen, ausdrücklich.** Kein Test liest Penpot. Ob `fills = []` dort Transparenz ergibt, ob der
Seitengrund `color.bg` ist und ob eine Beschriftung im Bild lesbar wirkt, bleibt Sichtprüfung.
Kriterium 4 ist in seiner Bedingung testbar, in seiner Wirkung nicht. Bei der Zusicherung aus
Falle 1 ist die **Form** der Bedingung gesichert, nicht ihre Wirkung — die Simulation ist ihr
eigenes Modell und merkte einen Fehler dort nicht.

## UI/UX

Betroffen ist allein das Entwurfsbild in Penpot; am ausgelieferten Produkt ändert sich nichts.

Die 29 Varianten tragen künftig entweder eine tokengebundene oder eine ausdrücklich leere Fläche
statt der weißen Standardfüllung. Schalter und Fortschrittsanzeige bekommen zusätzlich eine
Beschriftungsfarbe je Zustand. Neue Zustände entstehen keine, das Design-System wird nicht
erweitert — alle benötigten Tokens und Regeln existieren bereits; diese Story gleicht den
Penpot-Stand damit ab.

Alle Paarungen der Tabelle unter "Architektur / Umsetzung" sind aus `tokens.json` nachgerechnet und
halten die WCAG-AA-Schwelle von 4,5:1. Die transparent bleibenden Varianten messen gegen
`color.bg` zwischen 7,95:1 und 11,71:1.

**Die eine Ausnahme ist eine Paarung, kein Einzelfall:** `switch/disabled` liegt bei 1,81:1 —
`color.text-disabled` auf `color.surface`. Genau diese Paarung tragen im Zustand `disabled` auch
Schaltfläche, Eingabefeld und Auswahlkästchen, und zwar schon heute; über alle Bausteine sind es
**21** Varianten (Schaltfläche 18, Eingabefeld 1, Auswahlkästchen 1, Schalter 1). Sie fallen unter
die WCAG-Ausnahme für inaktive Bedienelemente (1.4.3 / 1.4.11), die das Design-System bereits führt
und die ein Vertragstest absichert (`--text-disabled` tritt ausschließlich als `disabled:`-Variante
auf). Der Schalter folgt damit einer bestehenden Regel, statt einen Mangel fortzuschreiben.

**Der Seitengrund gehört zur Nachführung.** Er steht nirgends im Repository und wird von keinem
Skript gesetzt. Für die transparent bleibenden Varianten ist Kriterium 3 deshalb nur gegen
`color.bg` rechenbar; beim Nachziehen (Kriterium 5) ist die Penpot-Seite auf `color.bg` zu setzen,
sonst prüft die Sichtprüfung gegen einen anderen Grund als die Rechnung.

## Security

Kein Produkt-Delta: kein Endpunkt, kein Feld, kein Secret, keine Abhängigkeit, keine Änderung an
Auth, Berechtigungen oder Datensichtbarkeit. Betroffen ist allein der Werkzeugkanal `execute_code`,
der in Daniels angemeldeter Sitzung ohne Sandbox läuft. Neu ist, dass erstmals eine Datei
**wiederholbar auf den bespielten Stand schreibt**, der das Original ist.

Die Laufregel `jederzeit-wiederholbar` trägt: `fix-flaechen.js` ist zielzustands-idempotent statt
konvergenz-idempotent, legt nichts an, verschiebt nichts, löscht nichts. Ein fail-closed-Wächter
ist hier **gegenstandslos** — die Schadensklasse, vor der er in `seed-components.js` bewahrt
(Strukturvernichtung ohne Rückweg), ist konstruktiv nicht erreichbar; eine falsch gesetzte Füllung
ist aus `components.json` ableitbar und durch denselben Lauf zurückzunehmen.

**Auflagen, Muss:**

1. `fix-flaechen.js` tritt der Liste `NUTZLAST_DATEIEN` bei, nicht einer daneben gestellten
   eigenen — nur diese eine Liste speist Wertfreiheit **und** abschließende Verbotsliste.
2. Die Schreibfläche ist geschlossen und geprüft, nicht zugesagt: erlaubt sind ausschließlich der
   Aufruf `applyToShapes` und die Zuweisung an `fills` mit einem leeren Array-Literal. Geprüft
   über den geparsten Baum, Aufrufe **und** `AssignmentExpression`.
3. **Fail-closed je Komponente statt je Lauf.** Eine Komponente mit passendem `schluessel` wird nur
   angefasst, wenn ihre Hauptinstanz ein Brett ist, genau ein direktes Textkind trägt und ihre
   `variantProps` in `components.json` auf ein bestimmtes Soll treffen. Sonst bleibt sie unberührt
   und erscheint im Bericht als eigener Ausgang ("Struktur abweichend"), nie als "bereits richtig"
   und nie mit einem geratenen Standard. Plugin-Daten sind von Hand setzbar, und mindestens ein
   Baustein (`skeleton`) ist in Penpot von Hand entstanden — eine Seed-Provenienz darf das Skript
   nirgends unterstellen.
4. **Der Bericht wird gelesen, nicht quittiert.** `geändert > 0` auf einem Lauf nach dem ersten
   bedeutet, dass jemand die Füllung in Penpot von Hand abweichend gesetzt hat; der Lauf hat sie
   überschrieben, und ihr voriger Wert steht in keiner Datei. Das ist ein Befund und gehört in den
   Abschlussbericht.
5. `verify.js` gibt zwei **Zahlen** je Baustein zurück — und kein gelesener Wert gelangt in eine
   **Fehlermeldung**. Eine Ausnahme geht denselben Weg in den Sitzungskontext wie die Rückgabe.
   Kein "Beispielwert" zur Fehlersuche.
6. `components.json` trägt keinen Schlüssel `__proto__` und keinen Schlüssel `constructor`, und das
   Rollenvokabular löst über **eigene** Schlüssel auf. Grund: Die Datei wird vom Test mit
   `JSON.parse` gelesen, von Penpot aber als Objektliteral ausgewertet — für `__proto__` sind die
   beiden nicht äquivalent, dort liefe die Prüfung auf einem anderen Substrat als die Ausführung.

Die Einfügestelle `const BAUSTEINE = <exakter Inhalt>;` ist **keine Injektionsfläche**: Gültiges
JSON kann als Literal nicht aus seiner Zeichenkette ausbrechen, die Datei wird im Test geparst
(ein Parse-Fehler färbt die Suite rot), und als Teil von `NUTZLAST_DATEIEN` schlagen Wertfreiheit
und Verbotsliste auch auf reinen Zeichenkettenwerten an.

**Restrisiko, bewusst getragen:** Eine von Hand in Penpot gesetzte, von `components.json`
abweichende Füllung wird von einem Wiederholungslauf überschrieben. Auflage 4 macht den Fall laut;
verhindern kann ihn nur, wer die Wiederholbarkeit aufgibt.

Im Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`) ist die Penpot-Kette um diese
fünfte Fortschreibung zu ergänzen: keine neue Angriffsflächen-Klasse, aber die erste Datei, die
wiederholbar auf das Original schreibt — die sechs Auflagen verdichtet, plus das Restrisiko.

## Entscheidungen

- **Alle vier Konsultationen sind gelaufen** (`architect`, `ux-ui-designer`, `test-engineer`,
  `security-engineer`); keine wurde übersprungen.
- **Nenner auf 158 korrigiert.** Die 146 aus dem Issue-Text stammen aus der Zeit vor Kategorie-Chip
  und Schrittmarke. Die Einzelzahlen des Befunds (24/1/3/1 = 29) sind unabhängig nachgerechnet und
  unverändert.
- **Akzeptanzkriterium 1 auf zwei messbare Größen umgestellt.** "Zeigt keine weiße Fläche" ist
  weder statisch noch beim Rücklesen beobachtbar — die Standardfüllung ist nirgends als Wert
  greifbar, nur die Abwesenheit einer Bindung. Der fachliche Gehalt ist unverändert.
- **Akzeptanzkriterium 6 auf die Fläche verengt, mit namentlicher Ausnahme.** Es kollidierte
  sonst mit der Umsetzung: `progress/indeterminate` bindet heute bereits eine Fläche, ist also
  "heute richtig", bekommt aber eine Beschriftungsfarbe. Verengt auf die Fläche, weil die Fläche
  der Defekt dieser Story ist; die Ausnahme steht namentlich im Kriterium statt in einer Fußnote.
- **Akzeptanzkriterium 5 blockiert den Pull Request nicht.** Sonst wäre er unabschließbar oder das
  Kriterium würde stillschweigend abgehakt.
- **Die Kontrastausnahme wird über ihre Bedingung geführt, nicht als Namensliste** (bei der
  Umsetzung entschieden, Kriterium 3 entsprechend nachgezogen). Die Zusicherung rechnet über
  **alle** 158 Varianten — anders hätte die Lücke bei `card`/`alert`/`skeleton` gar keinen Ort.
  Dabei zeigt sich: `switch/disabled` ist kein Einzelfall, sondern einer von 21 Fällen derselben
  Paarung. Eine Namensliste wäre bei jeder neuen `disabled`-Variante nachzupflegen und bei jedem
  Versäumnis rot, ohne dass etwas falsch wäre; die Bedingung (`color.text-disabled` **und**
  Ausprägung `disabled`) ist dieselbe Regel, die der Design-System-Vertragstest ohnehin erzwingt.
  Die eingefrorene Zahl 21 hält die Ausnahme trotzdem eng: Sie wächst nicht unbemerkt.
- **`ghost` × `hover` und `ghost` × `active` bleiben eine benannte Lücke.** Im Produkt zeigen sie
  sehr wohl eine Fläche (`hover:bg-overlay`, `active:bg-border`), aber Kriterium 2 legt für
  `ghost`/`link` pauschal "transparent" fest, und die Variantenmatrix kann eine Achsenkombination
  gar nicht adressieren — die Rollen `ueberfahren-flaeche`/`gedrueckt-flaeche` stehen genau deshalb
  ungebunden da. Sie zu füllen verlangte eine Tabelle für Achsenkombinationen in
  `components.json` und ist deutlich mehr als diese Story.
- **Die 13 Varianten ohne Beschriftungsfarbe werden geführt, nicht mitgenommen.** `card` (8),
  `alert/hinweis-*` (3) und `skeleton` (2) tragen keine Rolle `schrift` und zeigen ihre
  Beschriftung ebenfalls in Penpots Standardfarbe — derselbe Defekt wie bei `switch`/`progress`,
  nur ohne die weiße Fläche. Sie kommen als begründete Ausnahmeeinträge in die Kontrastzusicherung,
  damit die Lücke unübersehbar ist statt in einem Dokument geparkt; ein späterer Fix löscht nur
  einen Eintrag. Sie mitzunehmen wäre Scope Creep in einer Story, die ihren Umfang präzise begründet
  — und beträfe Bretter, die Kriterium 6 ausdrücklich schützt.
- **Die Achsenreihenfolge bleibt eine stille Abhängigkeit.** Welche Bindung gewinnt, entscheidet
  `Object.keys(varianten)` in `components.json`. Die Simulation liest dieselbe Reihenfolge, dass
  sie *richtig* ist, sagt kein Test. Ein Test dafür wäre eine getippte zweite Reihenfolge.

## Offene Fragen

Keine blockierenden. Die drei Punkte, die eine Entscheidung verlangten, sind unter "Entscheidungen"
getroffen und begründet; keiner davon ändert den Umfang der Story.

## Out of Scope

- Der verwandte Befund, dass ein Bibliotheks-Baustein ein Blatt ist und keine Unterelemente trägt
  (Knauf des Schalters, Füllbalken, Statuspille, Dateiname der Karte). Er hat dieselbe Wurzel — die
  Bibliothek trägt Tokens korrekt, ist aber keine visuelle Nachbildung des Produkts —, ist aber ein
  eigener Zuschnitt.
- Jede Änderung am Erscheinungsbild des ausgelieferten Produkts. Dort ist die Darstellung korrekt;
  diese Story gleicht den Entwurf an das Produkt an, nicht umgekehrt.
- Ein vollständiger Durchgang durch `design/penpot/README.md`. Mitgezogen werden die veralteten
  Zahlen in den Absätzen, die ohnehin umgeschrieben werden.
