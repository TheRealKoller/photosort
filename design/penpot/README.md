# Penpot-Nutzlast

Hier liegt alles, was den Stand der Penpot-Datei **„PhotoSort — Dark Utility Register"**
herstellt und zurückliest. Penpot ist seit ADR
[`0064`](../../specs/decisions/0064-penpot-als-design-quelle-rangfolge-umgekehrt.md) die
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
| `components.json` | handgeschrieben | Zustands-/Variantenmatrix der zehn Bausteine, ausschließlich in Tokennamen |
| `seed-tokens.js` | handgeschrieben | legt den Token-Satz `photosort` an bzw. gleicht ihn ab |
| `seed-icons.js` | handgeschrieben | legt die zwölf Symbole als Komponenten an |
| `seed-components.js` | handgeschrieben | baut die zehn Bausteine und ihre Varianten |
| `verify.js` | handgeschrieben | liest den Stand zurück und gibt ihn als JSON aus |

Die beiden erzeugten Dateien entstehen als Vitest-Dateischnappschuss in
`frontend/penpot/tokens.test.ts` bzw. `icons.test.ts` und sind damit in CI gegen Abweichung
gesichert: Wer `index.css` ändert und nicht neu erzeugt, bekommt einen roten Test — wer eine der
JSON-Dateien von Hand ändert, ebenfalls. Regeneriert wird mit `npm test -- -u` im Verzeichnis
`frontend/`. **Werte werden nie in eine Nutzlast getippt** (ADR
[`0065`](../../specs/decisions/0065-penpot-stand-als-erzeugte-idempotente-nutzlast.md)).

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

## ⚠ Warnhinweis zu `seed-components.js`

`seed-tokens.js` und `seed-icons.js` dürfen **jederzeit erneut laufen** — ihr Inhalt ist
vollständig erzeugt, in ihm kann keine Gestaltungsabsicht stecken, die nicht auch im Repository
stünde.

**`seed-components.js` läuft nur auf einer leeren oder neu aufgebauten Datei.** Nach dem ersten
Bespielen gehören die Bausteine Penpot: Dort wird entworfen, dort entstehen Änderungen, und ein
Skript, das sie überschreibt, machte den Zweck der ganzen Umstellung zunichte. Seine dauerhafte
Rolle ist die **Wiederherstellung nach Instanzverlust**, nicht die laufende Pflege. Die
Vorbedingung steht deshalb fail-closed im Skript selbst, vor dem ersten Schreibzugriff.

**Kein Skript löscht je etwas.** Findet ein Lauf in Penpot ein Token, das der Erzeuger nicht
kennt, bleibt es unangetastet und wird als **Befund** gemeldet — nicht als Fehler gewertet.

Was `seed-components.js` aufbaut, ist der token-gebundene Rumpf: je Ausprägung ein Brett mit
Beschriftung, dessen Fläche, Umriss, Radius, Innenabstände und Schriftmerkmale an Tokens gebunden
sind. Rollen, die zu Unterelementen gehören, die dieser Aufbau nicht selbst setzt (Knauf des
Schalters, Statuspille, Dateiname der Karte …), werden **nicht stillschweigend übergangen**,
sondern als `nachzubinden` zurückgegeben — ihre Bindung entsteht beim Entwerfen in Penpot, wo
diese Elemente ohnehin ihre Form bekommen.

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
abgeräumt) — es wird an diesen Stellen nicht mehr vermutet (ADR `0065`, Abschnitt 7):

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
- **Laufweite als blanke px-Zahl.** `-0.02em` wird als Tokenwert akzeptiert, kommt an der Textform
  aber als `0` an; der Erzeuger rechnet gegen die Schriftgröße der Stufe um (`-0.02em` bei 64px →
  `-1.28`).

Die beiden gekapselten Stellen (`formAusMarkup`, `wendeTokenAn`) bleiben trotzdem gekapselt: Sie
sind der Ort, an dem eine spätere API-Änderung eine Korrektur braucht statt zwölf. Stellt sich
künftig ein Punkt als nicht verfügbar heraus, wird das **gemeldet, nicht umgangen** — ein Zustand
als danebengestelltes Bild erfüllt Akzeptanzkriterium 4 nicht, und ein von Hand gesetzter
Schriftwert ist als dokumentierte Lücke zu führen.
