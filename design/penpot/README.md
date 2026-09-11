# Penpot-Nutzlast

Hier liegt alles, was den Stand der Penpot-Datei **„PhotoSort — Dark Utility Register"**
herstellt und zurückliest. Penpot ist seit ADR
[`0065`](../../specs/decisions/0065-penpot-als-design-quelle-rangfolge-umgekehrt.md) die
alleinige Design-Quelle: Welche Farbe, Form, Größe oder welchen Zustand ein Baustein haben *soll*,
entscheidet Penpot. Was heute *gilt und ausgeliefert wird*, steht weiterhin in
`frontend/src/index.css` — das ist keine zweite Quelle, sondern der Unterschied zwischen Absicht
und Zustand.

**Die Instanzadresse steht bewusst nicht im Repository.** Weder Hostname noch URL, Port,
Projekt-/Datei-ID noch Zugangsdaten. Der MCP-Server ist in Daniels lokaler Werkzeugkonfiguration
eingerichtet, nicht in einer Repo-Datei. Im Repository steht ausschließlich der **Dateiname** der
Penpot-Datei — er genügt, um sie zu finden, und verrät nichts über die Infrastruktur.

## Was hier liegt

| Datei | Art | Inhalt |
|---|---|---|
| `tokens.json` | **erzeugt** aus `frontend/src/index.css` | die 86 Tokens (Name, Typ, Wert): 64 `color`, 5 `borderRadius`, 8 `spacing`, 2 `fontFamilies`, 7 `typography` |
| `icons.json` | **erzeugt** aus `frontend/src/components/ui/icon.tsx` | die zwölf Symbole als SVG-Markup |
| `components.json` | handgeschrieben | Zustands-/Variantenmatrix der zwölf Bausteine, ausschließlich in Tokennamen |
| `views.json` | handgeschrieben | **keine Nutzlast** — die Soll-Struktur der Ansichtsentwürfe (siehe unten) |
| `seed-tokens.js` | handgeschrieben | legt den Token-Satz `photosort` an bzw. gleicht ihn ab |
| `seed-icons.js` | handgeschrieben | legt die zwölf Symbole als Komponenten an |
| `seed-components.js` | handgeschrieben | baut die zwölf Bausteine und ihre Varianten |
| `fix-flaechen.js` | handgeschrieben | zieht Fläche und Schriftfarbe im **bespielten** Stand nach (siehe unten) |
| `verify.js` | handgeschrieben | liest den Stand zurück und gibt ihn als JSON aus |

Die beiden erzeugten Dateien entstehen als Vitest-Dateischnappschuss in
`frontend/penpot/tokens.test.ts` bzw. `icons.test.ts` und sind damit in CI gegen Abweichung
gesichert: Wer `index.css` ändert und nicht neu erzeugt, bekommt einen roten Test — wer eine der
JSON-Dateien von Hand ändert, ebenfalls. Regeneriert wird mit `npm test -- -u` im Verzeichnis
`frontend/`. **Werte werden nie in eine Nutzlast getippt** (ADR
[`0066`](../../specs/decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md)).

Die statischen Regeln über die handgeschriebenen Dateien stehen in
`frontend/penpot/payload.test.ts` — insbesondere „kein wörtlicher Farb-/Größenwert", die
referentielle Integrität der Tokennamen und die abschließende Liste dessen, was die Nutzlast
aufrufen darf.

## Wie es ausgeführt wird

**Nicht von Hand und nicht aus einem Subagenten heraus, sondern ausschließlich über den Skill
`penpot-design` in der Hauptsession.** Gründe: Nur die Hauptsession hat MCP-Werkzeuge, und es
braucht ohnehin eine von Daniel geöffnete, verbundene Penpot-Sitzung — ohne sie antwortet der
MCP-Server mit „No Penpot instance connected", und der Ablauf bricht ab.

Die Nutzlast wird mechanisch zusammengesetzt und **unverändert** an `execute_code` übergeben:
genau **eine** Einfügestelle der Form

```
const <NAME> = <exakter Inhalt der Datendatei>;
```

gefolgt von der unveränderten Skriptdatei. `verify.js` bekommt keine Datendatei mitgegeben und
wird unverändert übergeben. Ist ein Wert falsch, wird `frontend/src/index.css` geändert und neu
erzeugt — nie der Aufruf angepasst.

| Schritt | Skript | Datendatei | Einfügename |
|---|---|---|---|
| 1 | `seed-tokens.js` | `tokens.json` | `TOKENS` |
| 2 | `seed-icons.js` | `icons.json` | `ICONS` |
| 3 | `seed-components.js` | `components.json` | `BAUSTEINE` |
| 4 | `verify.js` | — | — |
| K — nur auf ausdrückliche Anforderung | `fix-flaechen.js` | `components.json` | `BAUSTEINE` |

## ⚠ Warnhinweis zu `seed-components.js`

`seed-tokens.js`, `seed-icons.js` und `fix-flaechen.js` dürfen **jederzeit erneut laufen** — die
ersten beiden, weil ihr Inhalt vollständig erzeugt ist und in ihm keine Gestaltungsabsicht stecken
kann, die nicht auch im Repository stünde; das dritte, weil es nichts anlegt, nichts verschiebt,
nichts löscht und nur schreibt, wo Ist und Soll auseinanderliegen.

**`seed-components.js` läuft nur auf einer leeren oder neu aufgebauten Datei.** Nach dem ersten
Bespielen gehören die Bausteine Penpot: Dort wird entworfen, dort entstehen Änderungen, und ein
Skript, das sie überschreibt, machte den Zweck der ganzen Umstellung zunichte. Seine dauerhafte
Rolle ist die **Wiederherstellung nach Instanzverlust**, nicht die laufende Pflege. Die
Vorbedingung steht deshalb fail-closed im Skript selbst, vor dem ersten Schreibzugriff.

**Kein Skript löscht je etwas.** Findet ein Lauf in Penpot ein Token, das der Erzeuger nicht
kennt, bleibt es unangetastet und wird als **Befund** gemeldet — nicht als Fehler gewertet.

**⚠ Eine Zeitüberschreitung dieses Schritts ist kein Fehlschlag.** 158 Varianten mit je rund einem
Dutzend API-Aufrufen dauern länger, als `execute_code` auf eine Antwort wartet: Der Aufruf endet
mit „The operation timed out", **während die Arbeit vollständig ausgeführt wird** (beim ersten
echten Lauf gemessen). Vor jeder Reaktion wird der Stand **zurückgelesen** — erst das Ergebnis
entscheidet, ob etwas fehlt, nicht die Meldung. Fehlt tatsächlich etwas, ist die Datei nicht mehr
leer, und ein zweiter Lauf trifft den Wächter oben: Dessen Abbruch ist dann die **richtige**
Antwort und wird nicht umgangen. Der ausführliche Ablauf steht im Skill `penpot-design`,
Schritt 2.

Was `seed-components.js` aufbaut, ist der token-gebundene Rumpf: je Variante ein Brett mit
Beschriftung, dessen Fläche, Umriss, Radius, Innenabstände und Schriftmerkmale an Tokens gebunden
sind, daraus je eine Bibliotheks-Komponente, und daraus je Baustein ein Varianten-Container.

**Jedes Brett bindet eine Fläche oder wird ausdrücklich geleert — nie weggelassen.** Ein neu
erzeugtes Board trägt eine deckend **weiße** Standardfüllung, nicht etwa keine; wo nichts gebunden
wird, leuchtet es aus einem dunklen Entwurf heraus und die Beschriftung darauf erreicht rund 2,2:1.
Geleert wird **nach** dem Binden und nur dort, wo die Bindungslogik nachweislich keine Fläche auf
das Brett angewandt hat (ADR [`0081`](../../specs/decisions/0081-flaeche-binden-oder-leeren-und-ein-eigenes-korrekturskript.md)).
Eine fehlende Rolle `flaeche` in `components.json` heißt damit: **im Produkt ist diese Fläche
transparent** — eine Aussage, die je Ausprägung namentlich mit Grund geführt wird, samt
Gegenrichtung. Heute sind das 25 der 158 Varianten (`button/ghost`, `button/link`,
`badge/neutral`).

**Gebaut wird das vollständige Kreuzprodukt der Achsen** eines Bausteins (Schaltfläche 6 × 3 × 5 =
90 Varianten, über alle zwölf Bausteine **158**). Das ist keine Vorliebe, sondern eine Vorgabe der
Plugin-API: Ein Varianteneintrag muss für **jede** Varianteneigenschaft einen Wert nennen — ein
Eintrag, der nur `auspraegung=ghost` trägt und zu `groesse`/`zustand` schweigt, ist keine
wohldefinierte Variante.

Damit das Kreuzprodukt keine Kombinationen erfindet, die es im Produkt nicht gibt, gilt für die
Achsen selbst eine Regel: **Jede Achse muss unabhängig von den übrigen wählbar sein; wo zwei Dinge
nicht orthogonal sind, gehören sie in eine Achse.** Zwei Bausteine sind danach geschnitten:

- **Hinweis** führt *eine* Achse mit sieben Werten (`hinweis-success` … `status-failed`) statt zwei
  getrennter — in ihm fallen zwei Bauteile zusammen (`ui/alert.tsx` und `StatusTag.tsx`), und
  „Warnung × läuft" gibt es nicht. Die Präfixe sind nötig, weil `success` in beiden Hälften
  vorkommt und zweierlei meint.
- **Kennzeichen** führt *eine* Achse mit neun Werten (`favorite-solid` … `neutral`): Der neutrale
  Ton ignoriert die Füllung im Produkt vollständig, `neutral × suggested` hätte also keine
  Entsprechung.

Die Achsen sind eine Design-System-Aussage und stehen in `components.json`; ein Aufbauskript
schneidet sie nicht selbst. Dass eine Achse überhaupt Tokens trägt, ist statisch zugesichert —
eine tokenlose Achse multipliziert das Kreuzprodukt auf, ohne etwas zu beschreiben.

**Wiedererkannt werden die Bausteine an den Plugin-Daten `schluessel`**, die jede
Variantenkomponente trägt — nie am Namen: `createVariantContainer` benennt die Einzelkomponenten
in „Component" um, und der sprechende Name lebt am Container, der ein Board ist und gar nicht in
`penpot.library.local.components` steht. `seed-components.js` (Wächter) und `verify.js`
(Rückleser) benutzen dafür **wortgleich dieselbe Funktion**; die Übereinstimmung ist statisch
zugesichert.

Rollen, die zu Unterelementen gehören, die dieser Aufbau nicht selbst setzt (Knauf des Schalters,
Statuspille, Dateiname der Karte …), werden **nicht stillschweigend übergangen**, sondern als
`nachzubinden` zurückgegeben — ihre Bindung entsteht beim Entwerfen in Penpot, wo diese Elemente
ohnehin ihre Form bekommen.

## Den bespielten Stand nachziehen: `fix-flaechen.js`

„Nach einem Wiederaufbau richtig" und „im heutigen Stand richtig" sind **zwei Wege**, und sie
werden nicht zusammengeführt. Den ersten tragen `seed-components.js` und `components.json`. Den
zweiten trägt `fix-flaechen.js`: Es setzt in der bereits bespielten Datei die **Füllung** der
Variantenbretter und die **Farbe ihrer Beschriftung** auf das Soll aus `components.json`.

**Es läuft nie im Normalablauf**, sondern nur auf ausdrückliche Anforderung — etwa, wenn
`verify.js` einen Brettbestand mit Füllung ohne Tokenbindung meldet. Ein Wiederaufbau scheidet als
Reparaturweg aus: Er kostet die von Hand entstandenen Ansichten.

- **Abschließend, was es anfasst:** keine Struktur, keine Position, keine Größe, keine Benennung,
  keine Plugin-Daten, keine Löschung. Erlaubt sind allein `applyToShapes` und `fills = []` —
  statisch zugesichert über Aufrufe *und* Zuweisungen, denn die Verbotsliste sieht Zuweisungen
  nicht.
- **Fail-closed je Komponente, nicht je Lauf:** Angefasst wird nur, wessen Hauptinstanz ein Brett
  mit genau einem Textkind ist und wessen `variantProps` ein Soll aus `components.json` treffen.
  Alles andere bleibt unberührt und erscheint als eigener Ausgang „Struktur abweichend" — nie als
  „bereits richtig", nie mit einem geratenen Standard. Plugin-Daten sind von Hand setzbar, und der
  Platzhalter ist in Penpot von Hand entstanden: Eine Seed-Herkunft wird nirgends unterstellt.
- **Zielzustands-idempotent:** Geschrieben wird nur, wo Ist und Soll auseinanderliegen.
- **Der Bericht wird gelesen, nicht quittiert:** Ein „geändert" auf einem Lauf **nach dem ersten**
  bedeutet, dass jemand die Füllung in Penpot von Hand abweichend gesetzt hat; dieser Lauf hat sie
  überschrieben, und ihr voriger Wert steht in keiner Datei. Das ist ein Befund und gehört in den
  Abschlussbericht. Verhindern kann das nur, wer die Wiederholbarkeit aufgibt.

**Der Seitengrund gehört zur selben Nachführung** und steht in keiner Datei: Die Seite ist in
Penpot von Hand auf `color.bg` zu setzen, sonst prüft das Auge gegen einen anderen Untergrund als
den, gegen den der Kontrast gerechnet ist.

## Ansichtsentwürfe: `views.json` ist die Soll-Struktur, kein Generator

Seit ADR [`0069`](../../specs/decisions/0069-ansichtsentwuerfe-als-handarbeit-mit-soll-struktur-im-repository.md)
entsteht ein **Ansichtsentwurf von Hand in Penpot** — es gibt bewusst kein `seed-views.js` und
keine fünfte Zeile in der Schritttabelle oben. Eine Ansicht besteht fast vollständig aus Werten
(Position, Größe, Reihenfolge, Schachtelung, Beispieltext), und es gibt keine Quelle, aus der sie
erzeugt werden könnten: Die Ansicht existiert im Produkt noch nicht — das ist der Zweck eines
Entwurfs. Eine Datendatei mit Koordinaten wäre die erste getippte Wertekopie des Projekts.

`views.json` ist deshalb **keine Nutzlast**: Sie wird nie ausgeführt und an kein Skript übergeben
(eingefroren als `'views.json': null` in der Laufregel-Zuordnung von `payload.test.ts`). Sie ist
die Soll-Aussage, gegen die zurückgelesen wird — je Ansicht der maschinelle Schlüssel, der
Anzeigename, der Seitenname, die Produktdatei(en), die Breiten, die Zustände, die
Bausteinschlüssel, die instanziiert sein müssen, und die benannten **Lücken**. Ohne sie wäre ein
Instanzverlust bei den Ansichten nicht einmal erkennbar: eine Datei ohne Ansichten sähe für
`verify.js` aus wie eine vollständige.

**Sie trägt keine Koordinate, keine Größe, keinen Farbwert und keinen Beispieltext** — und nach der
Maskierung der Tokennamen **keine einzige Ziffer**. Das ist eine eigene, nur für sie geltende
Musterfamilie in `frontend/penpot/payload.test.ts`: Die vier übrigen Familien schweigen an
`"360x740"` (die blanke Zahl endet vor dem `x`) und an `"0b0c10"` (der Hexwert braucht ein `#`) —
genau die Schreibweisen, in denen eine Koordinate oder ein Farbwert in eine JSON-Datei rutscht.
Sie tritt der Suchraumliste `NUTZLAST_DATEIEN` **selbst** bei statt einer daneben gestellten
zweiten Liste: Diese Konstante speist beide Zusicherungsblöcke — Wertfreiheit *und* die
abschließende Verbotsliste.

**Das Ablagemuster** (verbindlich für jede weitere Ansicht): eine Penpot-Seite je Ansicht, benannt
`Ansicht — <Anzeigename>`; ein Brett je Breite, nebeneinander auf derselben Seite; die zwei Breiten
sind die Prüfbreiten des Projekts aus `e2e/lib/viewports.ts` und werden dort **gelesen**, nicht
getippt; Zustände sind eine Variantenachse `zustand`, die **Breite ausdrücklich keine**;
wiedererkannt wird an den Plugin-Daten `ansicht` und `breite`, nie am Namen.

`verify.js` liefert dazu je Brett die Plugin-Daten, die Varianteneigenschaften samt Zahl ihrer
Ausprägungen, die Zahl der **Bibliotheks-Instanzen**, die Zahl der Formen, die **keine** Instanz
sind, und die Tokenbindungen des Unterbaums. **Die Zahl der Nicht-Instanzen ist ein Hinweis, keine
Schwelle** — Texte und Rahmen sind legitim keine Instanzen; sie wird berichtet, nicht gefahren.
Die Kardinalitäten `ERWARTETE_ANSICHTEN` und `ERWARTETE_ANSICHTSBRETTER` stehen neben den vier
bestehenden; die Brettzahl entsteht in `views.json` als **Summe** über Breiten × Zustände, nicht
als zweite getippte Zahl.

**Ein Entwurf kann in Runden entstehen** (Skill `penpot-entwurfsrunden`): Ein Rundenlauf legt eine
eigene Arbeitsseite `Entwurf — <Bezeichnung>` an und legt dort je Vorschlag ein Brett ab,
vereinfacht auf eine Breite und einen Zustand. Solche Seiten sind **Arbeitsstand und nicht Teil der
Soll-Struktur** — sie stehen nicht in `views.json`, und ihre Bretter tragen ausdrücklich **nicht**
die Plugin-Daten `ansicht`/`breite`. Für `verify.js` ist ein laufender Entwurf damit nicht
vorhanden: Er kann den Abgleich weder rot färben noch Zählwerte verschieben. Weggeworfen wird eine
Arbeitsseite von Daniel in Penpot; kein Skript entfernt sie.

**Die Bildexporte werden nicht eingecheckt.** Je Ansichtsbrett ein Export über `export_shape` auf
die **Form** (nie ein Fensterabzug — ein Bildschirmfoto trüge die Adresszeile).

**`export_shape` legt keine Datei an** (2026-09-09 gemessen): Es liefert das Bild in die laufende
Sitzung — dort ist der Entwurf vorführbar —, aber die Plugin-API bietet keinen Weg auf die Platte.
Die Datei für den PR-Anhang entsteht in **Penpots eigenem Export**, nicht in der Session. Liegt sie
lokal, gehört sie unter `design/penpot/ansichten/`: Das Verzeichnis ist **ungetrackt**
(`.gitignore`), und der CI-Schritt „keine Bilddatei im Git-Index" deckt seit dieser Erweiterung
`e2e design` ab — er bleibt auch dann richtig, wenn die Session das Verzeichnis nie selbst befüllt.

Das Anhängen an den Pull Request ist **Daniels Handgriff im Browser** — `gh` kennt keinen
Bild-Upload, und der Operationskatalog `github-access` führt aus demselben Grund keine Operation
dafür.

**Was daraus folgt und man wissen muss:** Eine Ansicht ist nach einem Instanzverlust **nicht
wiederherstellbar und nicht einmal ansehbar**. Tokens, Symbole und Bausteine kommen aus den
Skripten zurück; von einer Ansicht bleiben nur `views.json` und der UI/UX-Abschnitt ihrer Spec —
welche Bretter es gab, nicht, wie sie aussahen.

## Was CI hier nicht prüfen kann

Verbindlicher Bestandteil der Spec, nicht eine Entschuldigung am Rand; steht wörtlich auch im Kopf
jeder `seed-*.js`:

1. **Die `seed-*.js` und `verify.js` sind zum PR-Zeitpunkt unausgeführter Code.** Geprüft sind
   Erzeugung, Vollständigkeit, Benennung, referentielle Integrität und Wertefreiheit. Ob ein
   Plugin-API-Aufruf funktioniert, kann kein Test hier sagen. Ein oder zwei Korrekturrunden nach
   dem ersten echten Lauf sind eingeplant, kein Fehlschlag.
2. **Kein Test kann Penpot lesen.** Der Abgleich ist eine Handlung, keine Zusicherung.
3. **Die Dauerregel „entwerfen nur mit Tokens" ist LLM-interpretierter Text.** Statisch verankert
   ist nur, *dass* sie im Skill steht.

## Was an der Plugin-API gemessen ist

Am 2026-09-08 an einer verbundenen Instanz gemessen (leere Scratch-Datei, danach rückstandsfrei
abgeräumt) — es wird an diesen Stellen nicht mehr vermutet (ADR `0066`, Abschnitt 7):

- **Tokenbindung wirkt**, und eine Bibliotheks-Instanz **erbt** die Bindungen. `shape.tokens`
  liefert die Zuordnung Eigenschaft → Tokenname; `verify.js` liest genau das zurück.
- **Varianten tragen** (`createVariantContainer`, `variantProps`, `switchVariant`).
  **Nebenwirkung:** Die Einzelkomponenten werden dabei in „Component" umbenannt — der sprechende
  Name lebt am Container, und `verify.js` erkennt die Bausteine deshalb am maschinellen Schlüssel
  aus den Plugin-Daten, nicht am Namen.
- **`createShapeFromSvg(svgString)` existiert** und liefert eine `Group`, hängt aber ein
  zusätzliches Kind `base-background` an. `seed-icons.js` entfernt es — die einzige Stelle, an der
  eines dieser Skripte etwas entfernt, und von der abschließenden Liste gedeckt, weil das Rechteck
  im selben Lauf vom Skript selbst entstanden ist.
- **Vier Abweichungen von der API-Doku:** kein Token-Typ `lineHeight`/`lineHeights` (deshalb die
  Verbundtokens); die Eigenschaft für die Schriftfamilie heißt `fontFamily` (Singular); der
  **Schreibwert** eines `typography`-Tokens benutzt die **Singular**-Schlüssel (`fontFamily`,
  `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing`) — die Pluralformen sind die Leseform;
  und ein Token-Satz wirkt erst nach `toggleActive()` (`seed-tokens.js` schaltet ihn ein, aber nur
  wenn er nachweislich inaktiv ist — `toggleActive` schaltet um und wäre sonst nicht wiederholbar).
- **Im Verbundwert trägt ein Feld einen Wert oder fehlt ganz.** Eine leere Zeichenkette ist ein
  **ungültiger** Wert und lässt den ganzen Aufruf scheitern (`Field 0.value is invalid`) — daran
  ist der erste echte Lauf abgebrochen. `--text-xs`/`--text-sm` tragen deshalb schlicht kein
  `fontWeight`-Feld, `--text-3xl` als einzige ein `letterSpacing`. An der Zusage dahinter ändert
  das nichts: Es wird weiterhin kein Standardschnitt erfunden. Ein leeres Feld irgendwo im
  Erzeugnis ist seither ein roter Test.
- **`fontSize` trägt seine Einheit** (`"12px"`) — gemessen gültig; der letzte offene Punkt aus der
  ersten Umsetzungsrunde ist damit erledigt.
- **Eine neu erzeugte Form landet im zuletzt angelegten Container.** Bei `createShapeFromSvg`
  gemessen: Ohne ausdrückliches `penpot.root.appendChild(...)` steckten im ersten echten Lauf alle
  zwölf Symbolgruppen ineinander, weil `createComponent` aus dem ersten Symbol ein Board macht.
  **Eine nachträglich gesetzte Position behebt das nicht** — der Elternknoten wird beim Erzeugen
  entschieden. `seed-icons.js` verankert deshalb ausdrücklich; `seed-components.js` tut dasselbe
  vorsorglich für seine Bretter (dort nicht gemessen, aber billig und bei 158 Ausprägungen ungleich
  teurer zu entwirren).
- **`/` ist ein Pfadtrenner, kein Namensbestandteil.** `symbol/star` liegt als
  `{ name: "star", path: "symbol" }` vor; die volle Zeichenkette steht in keinem einzelnen Feld.
  Die Gruppierung bleibt (sie ist in der Oberfläche nützlich), aber verglichen wird über **beide**
  Felder — sonst trifft die Suche nie, ein zweiter Lauf legte Dubletten an und das Rücklesen meldete
  einen leeren Stand. Kein Baustein- und kein Ausprägungsname trägt einen Schrägstrich; das ist
  statisch zugesichert.
- **Eine Gruppe trägt keinen eigenen Strich.** Das Strichfarben-Token auf das Ergebnis von
  `createShapeFromSvg` anzuwenden lief ins Leere (Gruppe ohne Bindung, der Pfad darunter schwarz).
  `seed-icons.js` wendet es deshalb auf die **Blattformen** an, rekursiv eingesammelt — die
  heutigen Symbolgruppen sind flach, ein künftiges Symbol mit verschachtelter Gruppe verlöre sonst
  still seine Farbe. `verify.js` liest die Bindungen aus demselben Grund über den **ganzen**
  Unterbaum statt über eine Ebene.
- **Penpot kennt keine Sammel-Eigenschaften.** `border-radius` und `padding` werfen beide
  (`Field 1 is invalid: should be a set of strings`); es gibt nur die vier Radius-Ecken bzw. die
  vier Polster-Seiten einzeln. Jede Rolle in `ROLLE_ZU_EIGENSCHAFT` bildet deshalb auf eine
  **Liste** ab — auch dort, wo es nur eine Eigenschaft ist; eine Sonderform für den Einzelfall
  wäre die Stelle, an der es später wieder auseinanderläuft. Dass jeder genannte Name aus einer
  geschlossenen Liste stammt, ist statisch zugesichert: Der Eigenschaftsname war zweimal die
  Fehlerquelle, und ein erfundener fällt seither in CI auf statt beim Lauf.
- **Der Pfad-Präfix wird genau einmal gesetzt** — am Formnamen. Ihn danach noch einmal über
  `komponente.name` zu setzen, hängt ihn ein zweites Mal vor (`path: "symbol / symbol"`). Der
  Trenner im gelesenen `path` ist bei mehrstufigen Pfaden übrigens `" / "` mit Leerzeichen; der
  Vergleich hier gilt dem einstufigen Fall.
- **Penpot normalisiert einen `fontFamilies`-Wert beim Ablegen zu einem Array** (`"Inter"` →
  `["Inter"]`). Der Abgleich in `seed-tokens.js` behandelt ein einelementiges Array deshalb wie
  seinen Skalar — sonst meldete jeder Lauf beide Schriftfamilien als „nicht schreibbar".
- **`execute_code` führt den Text als Funktionsrumpf aus** und liefert nur zurück, was ein
  `return` zurückgibt. Jede Skriptdatei endet deshalb auf ein `return`; ein blanker Ausdruck ginge
  still verloren — bei `verify.js` wäre das der gesamte nachprüfbare Abschluss.
- **Argumentformen, die von der Doku abweichen:** `addSet({ name })` und
  `addToken({ type, name, value })` nehmen je **ein Objekt**; die Strichfarbe heißt `strokeColor`
  (nicht `stroke`); `applyToShapes` nimmt ein Formen-Array und die Eigenschaft als blanke
  Zeichenkette; `createVariantContainer` nimmt `[{ shape, properties }]` mit der **Hauptinstanz**
  einer Komponente, nicht das Board; `variantProps` ist ein **Objekt** je Komponente und nennt die
  Werte dieser einen Ausprägung. Die Formen sind in `frontend/penpot/payload.test.ts` als Tabelle
  statisch zugesichert — genau diese Fehlerklasse hat eine Review-Runde siebenmal gefunden.
- **Ein Bibliotheks-Baustein ist ein Blatt, und eine Instanz nimmt keine Kinder auf.** Am 2026-09-09
  an jedem damals vorhandenen Baustein einzeln gemessen: je ein Brett mit genau **einer** Textbeschriftung;
  `appendChild` an eine Instanz scheitert mit „Cannot change the structure of a component copy".
  Karte und Dialog sind im Produkt Behälter, in der Bibliothek aber Blätter. Ein Ansichtsentwurf
  setzt deshalb **Blatt-Elemente als echte Instanzen** (überschriebene Beschriftung) und **Behälter
  als tokengebundene Rahmen** — und führt das als Lücke in `views.json`, nicht als erledigt.
- **Laufweite als blanke px-Zahl.** `-0.02em` wird als Tokenwert akzeptiert, kommt an der Textform
  aber als `0` an; der Erzeuger rechnet gegen die Schriftgröße der Stufe um (`-0.02em` bei 64px →
  `-1.28`).

Die beiden gekapselten Stellen (`formAusMarkup`, `wendeTokenAn`) bleiben trotzdem gekapselt: Sie
sind der Ort, an dem eine spätere API-Änderung eine Korrektur braucht statt zwölf. Stellt sich
künftig ein Punkt als nicht verfügbar heraus, wird das **gemeldet, nicht umgangen** — ein Zustand
als danebengestelltes Bild erfüllt Akzeptanzkriterium 4 nicht, und ein von Hand gesetzter
Schriftwert ist als dokumentierte Lücke zu führen.

### Layout-Eigenheiten der Plugin-API (2026-09-09 gemessen)

Beim ersten Ansichtsentwurf gemessen, hier festgehalten, damit der nächste ihn nicht neu entdeckt:

- Das Flex-Layout eines Bretts rechnet **nur bei wachsender Höhe**. Eine feste Höhe unterdrückt es
  still — die Kinder liegen dann alle übereinander, ohne Fehlermeldung. Ein Brett trägt deshalb feste
  Breite plus `verticalSizing = 'auto'`, und beide Sizings müssen ausdrücklich gesetzt sein.
- Eine exakte Prüfbreite **und** -höhe braucht zwei Stufen: äußerer Rahmen ohne Layout, darin ein
  Inhaltsbrett mit Layout.
- Kind-Sizing sitzt auf `shape.layoutChild`, nicht am Shape. Am Shape wirft `'fill'`; ein Shape ist
  nicht erweiterbar.
- Ein leerer Text ist ungültig — eine unerwünschte Beschriftung wird ausgeblendet, nicht geleert.
- `penpot.openPage` wirkt nicht zuverlässig im selben Aufruf; Wechsel und Prüfung gehören getrennt.

### Layout-Eigenheiten der Plugin-API (2026-09-10 gemessen)

Im Entwurfsrundenlauf zur Fotoansicht gemessen. Wie die Punkte darüber scheitert jeder von ihnen
**still** — kein Fehler, nur ein falsches Bild:

- **Layoutwerte stehen erst im FOLGENDEN `execute_code`-Aufruf.** Im selben Aufruf gelesen, ist die
  Brett-Höhe noch `1` und alle Kinder liegen auf `0,0`. Das sieht wie der Feste-Höhe-Fehler oben
  aus, ist aber keiner: Bauen und Messen gehören in getrennte Aufrufe.
- **Ein Brett, das Kind eines Flex-Layouts ist, wächst nie in der Höhe** — auch
  `layoutChild.verticalSizing = 'auto'` bewirkt nichts. Die Kinder werden horizontal trotzdem
  korrekt gesetzt, nur die Höhe bleibt `1`. Griff: nach dem Einhängen aller Kinder einmal
  `resize(breite, ausgerechneteHoehe)`. Das innere Layout bleibt dabei intakt, und das äußere Brett
  wächst korrekt mit.
- **`switchVariant(pos, value)` nimmt die POSITION der Achse, nicht ihren Namen.** Die Reihenfolge
  ist `Object.keys(komponente.variantProps)`. Sowohl `switchVariant({achse: wert})` als auch
  `switchVariant('achse', wert)` scheitern mit „Value not valid … Code: :pos".
- **Ein neu erzeugtes Board hat eine WEISSE Fläche, nicht etwa keine.** Jedes Struktur-Brett ohne
  gebundene Fläche (Statuszeile, Rasterzeile, Inhaltsspalte …) leuchtet weiß aus einem dunklen
  Entwurf heraus. `fills = []` macht es transparent. Auf schmalen Streifen sieht das nach Absicht
  aus und rutscht durch: Beim Bauen entweder Fläche binden ODER ausdrücklich leeren, nie weglassen.
- **`penpot.library.local.components` listet je Baustein genau EINE Komponente**, nicht ihre
  Varianten. `komponente.instance()` erzeugt eine Kopie; deren erstes Textkind lässt sich
  überschreiben, und die Kopie schrumpft danach auf ihre Inhaltsbreite. An einer solchen Kopie
  lassen sich Tokens binden und Ecken-Radien setzen.
- **Eine Penpot-SEITE trägt Plugin-Daten** (`setPluginData`/`getPluginData` am `Page`-Objekt).
  Marken brauchen also kein eigens angelegtes Trägerbrett.
- **`textDecoration = 'line-through'` wirkt an einer Textform.**

### Bilder in die Datei bringen (2026-09-10 gemessen)

- `await penpot.uploadMediaData(name, Uint8Array, 'image/jpeg')` legt ein Bild **dauerhaft als
  Medium in der Datei** ab (`await` wird unterstützt); gesetzt wird es über
  `shape.fills = [{ fillOpacity: 1, fillImage: imageData }]`.
- **Base64 durch den Aufruftext ist unzuverlässig.** Zeichen gehen verloren ODER werden ersetzt —
  bei gleicher Länge. Eine Längenprüfung genügt deshalb NICHT: ein so hochgeladenes Bild kam durch
  die Prüfung und war trotzdem reines Farbrauschen. Nötig ist eine Inhalts-Prüfsumme, lokal und im
  Aufruf gleich berechnet. Von acht Bildern scheiterten drei, eines davon dreimal hintereinander.
- **Der verlässliche Weg ist ein anderer:** Die Bilder von Hand in Penpot hochladen (Drag & Drop auf
  eine Seite). Die Formen tragen die Bilddaten dann in `fills[0].fillImage`, und von dort sind sie
  ohne jedes Kopierrisiko und in voller Auflösung weiterverwendbar. Die acht Beispielbilder aus
  `assets/beispielbilder/` liegen so auf der Seite `Material — Beispielbilder`, jede Fläche mit
  Herkunftsdatei, Seitenverhältnis und Lage in den Plugin-Daten.
