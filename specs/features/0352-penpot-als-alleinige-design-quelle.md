# 0352 - Penpot als alleinige Design-Quelle

**Status:** Accepted
**Erstellt:** 2026-09-08
**Bezug:** [GitHub-Issue #352](https://github.com/TheRealKoller/photosort/issues/352)

## Ziel

Das Design-System „Dark Utility Register" wird heute in einer Figma-Datei gepflegt. Der Zugang
dorthin hängt an einem Starter-Plan mit hartem Aufruflimit — zuletzt war es nach einem einzigen
Zugriff pro Sitzung erschöpft. Entwurfsarbeit über dieses Werkzeug ist damit nicht mehr
durchführbar: Gestaltungsänderungen landen zwangsläufig direkt im Code, ohne den Zwischenschritt,
sie vorher zu sehen.

Daniel hat dafür eine eigene, selbst gehostete Penpot-Instanz aufgesetzt. Diese Spec bringt das
bestehende Design-System dorthin und macht Penpot zur alleinigen Design-Quelle. Die Gestaltung
selbst ändert sich dabei ausdrücklich **nicht** — sie wechselt nur den Aufbewahrungsort. Was sich
ändert, ist die Rangfolge: Bei Widerspruch gewinnt künftig Penpot, nicht mehr das Repo. Genau
deshalb muss der heute im Code umgesetzte Stand nach Penpot wandern und nicht der ältere Stand
des Figma-Boards — sonst kehren die begründet korrigierten, schlechter lesbaren Farbwerte durch
die Hintertür zurück.

Nutzen im Alltag: Entwürfe für neue Ansichten entstehen wieder auf einer Fläche statt direkt im
Code, und zwar so, dass sie von sich aus die richtigen Farben, Schriften und Abstände tragen.
Bekannte Nutzungsbedingung: Design-Arbeit über Penpot setzt eine offene, verbundene
Penpot-Sitzung voraus — anders als beim bisherigen Werkzeug läuft nichts im Hintergrund ohne
Daniel.

## User Story

Als Gestalter und Entwickler von PhotoSort in Personalunion möchte ich das Design-System in
meiner eigenen Penpot-Instanz führen, damit ich neue Ansichten wieder entwerfen kann, bevor ich
sie baue — ohne von einem fremden Aufruflimit ausgebremst zu werden.

## Akzeptanzkriterien

Die Kriterien 1–6 und 8 sind gegenüber dem Issue-Wortlaut auf Testbarkeit geschärft (siehe
Abschnitt „Entscheidungen"); 7, 9 und 10 stehen unverändert, weil sie dokumentarische Handlungen
sind und im Diff bzw. auf GitHub direkt entscheidbar bleiben.

- [ ] **1.** Farben, Typografie, Abstandsskala und Radien liegen in Penpot als benannte,
  wiederverwendbare Tokens vor: **64 Farb-, 5 Radien-, 8 Abstands-, 2 Schriftfamilien- und 7
  Typografie-Verbundtoken** in einem Satz namens `photosort`, benannt nach `<gruppe>.<blatt>`.
  Jedes der sieben Typografie-Tokens trägt Größe, Zeilenhöhe, Schnitt und Laufweite einer
  Schriftstufe zusammen und **verweist** für die Familie auf eines der beiden Familientokens
  (`{font-family.sans}`), sodass die Familie nicht doppelt im System steht. **„Zentral änderbar" heißt:** jede Eigenschaft
  eines Bausteins, für die ein Token existiert, ist an dieses Token **gebunden** und nicht als
  Wert gesetzt — nachgewiesen durch das Rücklesen der Tokenbindungen je Baustein, nicht durch die
  bloße Existenz der Tokenliste.
- [ ] **2.** Übertragen wird der Stand aus `frontend/src/index.css`, nicht der Figma-Stand. Für
  die **fünf wertetragenden** der acht dokumentierten Abweichungen (Nr. 1–5) trägt Penpot
  nachweislich den Projektwert und nicht den Board-Wert; Nr. 6 (Symbolwahl), Nr. 7
  (Verwendungsregel) und Nr. 8 (Randbreite) sind keine Tokenwerte und wandern nicht als solche
  mit.
- [ ] **3.** Zehn Bausteine liegen als **Bibliotheks-Komponenten** vor (nicht als Formen oder
  Gruppen gleichen Namens), mit den maschinellen Schlüsseln `button`, `input`, `badge`, `card`,
  `alert`, `checkbox`, `switch`, `progress`, `dialog`, `chip` und den deutschen Anzeigenamen
  (Schaltfläche, Eingabefeld, Kennzeichen, Karte, Hinweis, Auswahlkästchen, Schalter,
  Fortschrittsanzeige, Dialog, Kategorie-Chip). Die Menge ist **geschlossen**: weder mehr noch
  weniger.
- [ ] **4.** Jeder Baustein trägt seine Zustände als **Penpot-Variants** — auswählbar, nicht als
  zweites Bild danebengestellt. Prüfbar heißt: **(a) im Repo** — trägt die Produktdatei eines
  Bausteins eine Variante aus dem Zustandsvokabular
  `hover`/`active`/`focus-visible`/`disabled`/`aria-disabled`/`data-[state=checked]`/`data-[state=open]`/`indeterminate`,
  dann führt `components.json` diesen Zustand; **(b) in Penpot** — `verify.js` liest je Baustein
  die Varianteneigenschaften und die Zahl der Ausprägungen zurück und vergleicht sie gegen
  `components.json`. Der Kategorie-Chip trägt **dreizehn** Ausprägungen, deckungsgleich mit dem
  Kategorien-Set.
- [ ] **5.** Genau die zwölf Symbole aus `ICON_NAMES` sind in Penpot als Komponenten verfügbar,
  **gerendert über die projekteigene `Icon`-Komponente**, mit erhaltenem `viewBox` und
  Strichstärke 2, ohne feste Pixelgröße. Die namentliche Übereinstimmung wird zurückgelesen,
  ebenso die **Struktur** jedes Symbols: Blattformen des importierten Baums nach Anzahl und
  Typreihenfolge gegen `icons.json`. Jede Blattform trägt die Strichbindung an
  `color.text-h` — eine Bindung auf der Gruppe griffe nicht, die Symbole kämen schwarz an.
- [ ] **6.** Ein neu in Penpot zusammengesetzter Entwurf trägt die richtigen Farben, Schriften
  und Abstände, ohne dass dafür Werte von Hand eingetragen werden — auch ein Entwurf, den Claude
  erstellt. **Nachgewiesen durch Vorführung (exportiertes Bild plus zurückgelesene
  Tokenbindungen am Pull Request), nicht durch Test gesichert**; es gelten die fünf Punkte der
  Vorführungsregel unter „Teststrategie".
- [ ] **7.** Penpot ist als maßgebliche Design-Quelle festgehalten: Die Stellen, die heute Figma
  als Quelle benennen, nennen danach Penpot, und die Umkehrung der Rangfolge (bei Widerspruch
  gewinnt Penpot) ist ausdrücklich als bewusste Rücknahme der bisherigen Festlegung dokumentiert
  — nicht stillschweigend.
- [ ] **8.** Die Werte bleiben im Repo nachvollziehbar, auch wenn die Penpot-Instanz nicht
  erreichbar ist: `frontend/src/index.css` ist die Werteliste, `design/penpot/tokens.json` und
  `icons.json` sind das daraus erzeugte, eingecheckte Abbild, und **aus ihnen ist der
  Penpot-Stand ohne Handeintrag wieder aufbaubar**. Ein drittes, handgepflegtes Wertedokument
  entsteht nicht.
- [ ] **9.** Figma wird nicht mehr gepflegt. Der letzte gültige Stand ist als Archiv vermerkt,
  damit später nachvollziehbar bleibt, woher das System kam.
- [ ] **10.** Die noch offene Arbeit, die ausschließlich das Figma-Board wartbar machen sollte
  ([Issue #336](https://github.com/TheRealKoller/photosort/issues/336)), ist ohne Umsetzung
  verworfen — sie wäre nach der Ablösung wertlos. Die beiden Farbkorrekturen daraus sind im Code
  bereits umgesetzt (ADR [`0055`](../decisions/0055-dark-utility-register-fundament.md) Punkt 4a
  und 4f) und gehen dabei nicht verloren.

## Datenmodell-Bezug

Keiner. Es entsteht keine Entität, kein Feld und keine Migration; weder Backend noch Datenbank
werden berührt. [`docs/architecture.md`](../../docs/architecture.md) ändert sich aus demselben
Grund nicht (siehe „Out of Scope").

## Architektur / Umsetzung

**Zwei ADRs tragen diese Spec:**
[`decisions/0064-penpot-als-design-quelle-rangfolge-umgekehrt.md`](../decisions/0064-penpot-als-design-quelle-rangfolge-umgekehrt.md)
entscheidet, *dass* Penpot die Quelle ist und was das für die Rangfolge heißt;
[`decisions/0065-penpot-stand-als-erzeugte-idempotente-nutzlast.md`](../decisions/0065-penpot-stand-als-erzeugte-idempotente-nutzlast.md)
entscheidet, *wie* das System dorthin kommt und wer es ausführt. Die Trennung ist Absicht: Die
Rangfolge soll auch dann noch gelten, wenn der Mechanismus einmal ausgetauscht wird. Der
Kreislauf aus beidem steht als Diagramm in
[`diagrams/design-quelle-penpot.svg`](../diagrams/design-quelle-penpot.svg).

### Die Rangfolge (AK 7 und AK 8 zusammen)

Die scheinbare Spannung zwischen „bei Widerspruch gewinnt Penpot" und „das Repo muss die Werte
weiterhin kennen" löst sich auf, sobald man trennt, *worüber* jeweils entschieden wird:

1. **Gestaltung — Penpot gewinnt.** Welche Farbe/Form/Größe/welchen Zustand ein Baustein haben
   *soll*, entscheidet Penpot. Weicht das Repo ab, ist das ein Mangel des Repos. Bis heute galt
   das Gegenteil.
2. **Gültiger Wert — `frontend/src/index.css` gewinnt.** Was heute *gilt und ausgeliefert wird*,
   steht dort. Eine Penpot-Änderung wird erst wirksam, wenn sie über den normalen Weg
   (Story → Spec → PR) im Repo ankommt. Das ist keine zweite Quelle, sondern der Unterschied
   zwischen Absicht und Zustand.
3. **Die einzige Ausnahme von 1: die Kontrast-Untergrenze.** Ein Penpot-Wert unter WCAG-AA wird
   nach der Regel aus ADR 0055 Punkt 4 korrigiert übernommen (Fläche bleibt, Schrift- oder
   Linienfarbe wird angepasst) **und die Korrektur wird nach Penpot zurückgeschrieben**. Der
   Vorgang endet also in Penpot — er führt die beiden Orte zusammen, statt dem Repo ein Veto zu
   geben.

Ein drittes, handgepflegtes Wertedokument entsteht **nicht**.
`specs/architecture/0005-board-dark-utility-register.md` wird **als Archiv eingefroren** (AK 9):
angefasst wird ausschließlich der Kopf (Status `Archiv — abgelöste Design-Quelle`), der Rumpf
bleibt wortgetreu stehen — eine nachträglich umgeschriebene Momentaufnahme wäre eine Fälschung.
Die maßgebliche Werteliste im Repo ist ab jetzt `frontend/src/index.css` (jedes Token trägt dort
einen ausgeschriebenen Hexwert, nie `var()`), die Regeln dazu bleiben in
[`architecture/0004-design-system.md`](../architecture/0004-design-system.md).

### `index.css` ↔ Penpot-Tokens

**In dieser Spec wird kein Frontend-Produktcode geändert** — kein `.tsx`, kein Wert in
`index.css`, keine `package.json`.

Die Richtung ist **`index.css` → Penpot, erzeugt statt abgeschrieben**. Der Penpot-Plugin-Kontext
hat kein Dateisystem, die Werte müssen also in der Nutzlast stehen; die Frage ist nicht, ob es
diese Kopie gibt, sondern ob sie erzeugt oder getippt ist. Sie wird erzeugt:
`design/penpot/tokens.json` entsteht per Vitest-Dateischnappschuss (`toMatchFileSnapshot`) aus
dem `:root`- und `@theme`-Block und ist damit in CI gegen Abweichung gesichert — wer `index.css`
ändert und nicht neu erzeugt, bekommt einen roten Test. Das kostet keine neue Abhängigkeit und
kein neues Kommando: Die Erzeugung *ist* ein Test, regeneriert wird mit `npm test -- -u`.

Übersetzt werden: 64 Farbtokens, 5 Radien, 8 Abstandsstufen, 2 Schriftfamilien und 7
Typografie-Verbundtokens. **Penpot kennt keinen Token-Typ für Zeilenhöhen** (gemessen, siehe
unten) — die sieben Schriftstufen werden deshalb als `typography`-Verbundtokens abgebildet, die
Größe, Zeilenhöhe, Schnitt und Laufweite gemeinsam tragen und für die Familie auf die beiden
Familientokens verweisen. Das ist zugleich die Form, in der eine Schriftstufe beim Entwerfen in
einem Zug angewandt wird, statt in vier Einzelwerten. Die Abstandsstufen sind die einzige Gruppe ohne
eigene Deklaration in `index.css` (Tailwinds `--spacing`-Basis 0.25rem × Stufen
1/2/3/4/6/8/12/16 = 4…64px); sie werden abgeleitet und zusätzlich gegen den echten Tailwind-Lauf
geprüft. Die sechs auf `initial` gestrichenen Stufen `--text-4xl` bis `--text-9xl` werden
ausgeschlossen und dabei gezählt. Einzige bewusste Übersetzung: Schriftfamilien tragen nur die
Primärfamilie (`Inter`, `JetBrains Mono`), nicht den CSS-Fallback-Stack.

**Benennung in Penpot:** `<gruppe>.<blatt>`, Blatt = exakt der CSS-Tokenname ohne `--`
(`color.text-muted`, `color.chip-menschen-bg`, `radius.sm`, `space.3` = `p-3`). Die einzige
Ausnahme von der Blatt-Regel sind die sieben Schriftstufen: Sie tragen die Gruppe **`text`** und
als Blatt die Stufe (`text.xs` … `text.3xl`), spiegeln damit `--text-xs` unmittelbar und
versprechen nicht — wie ein Gruppenname `font-size` es täte — weniger, als das Verbundtoken
tatsächlich trägt.
Ein Token-Satz namens `photosort`, kein zweites Set und kein Theme — es gibt nur ein Farbschema.

### Was im Repo entsteht

| Datei | Art |
|---|---|
| `frontend/tsconfig.penpot.json` (+ Referenz in `tsconfig.json`) | eigenes TS-Projekt für die Erzeuger, nach dem Vorbild von `tsconfig.contract.json` — aber **zusätzlich** mit `"jsx": "react-jsx"` und DOM-/React-Typen, weil `icons.ts` JSX über `react-dom/server` rendert |
| `frontend/penpot/tokens.ts` / `tokens.test.ts` | Erzeugung + Prüfung der Tokenliste aus `index.css` |
| `frontend/penpot/icons.ts` / `icons.test.ts` | rendert die zwölf Symbole über die **projekteigene** `components/ui/icon.tsx` (nicht über `lucide-react` direkt) nach SVG |
| `frontend/penpot/payload.test.ts` | statische Regeln über die Nutzlast |
| `design/penpot/tokens.json`, `icons.json` | **erzeugt**, eingecheckt |
| `design/penpot/components.json` | handgeschriebene Zustands-/Variantenmatrix der zehn Bausteine, ausschließlich in Tokennamen |
| `design/penpot/seed-tokens.js`, `seed-icons.js`, `seed-components.js`, `verify.js` | handgeschriebene, zielzustands-idempotente Aufbau-/Rücklese-Nutzlast |
| `design/penpot/README.md` | was hier liegt, wie es ausgeführt wird, Warnhinweis auf `seed-components.js` |
| `.claude/skills/penpot-design/SKILL.md` | neuer Skill für die Hauptsession, Erlaubnisstufe „kein GitHub-Zugriff" |

Die Zustandsmatrix der zehn Bausteine wird **aus dem Code abgeleitet, nicht erfunden**:
`ui/button.tsx` · `ui/input.tsx` · `ui/badge.tsx` + `RatingBadge.tsx` · `ui/card.tsx` +
`PhotoCard.tsx` · `ui/alert.tsx` + `StatusTag.tsx` · `ui/checkbox.tsx` · `ui/switch.tsx` ·
`ui/progress.tsx` · `ui/dialog.tsx` · `CategoryBadge.tsx`. **Achtung:** neun der zehn liegen unter
`frontend/src/components/ui/`, der Kategorie-Chip liegt als `src/components/CategoryBadge.tsx`
daneben — die Zuordnungstabelle spannt zwei Verzeichnisse, wer nur `ui/` aufzählt, verliert den
zehnten still.

### Umsetzungsreihenfolge

1. `frontend/tsconfig.penpot.json` anlegen und in `tsconfig.json` referenzieren (Wegbereiter,
   kein Test). **Vor dem Bau kurz prüfen**, ob `tsc -b` die Doppelzuordnung von `icon.tsx` zu
   zwei TS-Projekten quittiert (`tsconfig.app.json` hat `include: ["src"]`, das neue Projekt
   zieht `../src/components/ui/icon.tsx` transitiv). Klemmt es: **melden, nicht still
   ausweichen** — die naheliegende Alternative (Erzeuger in `tsconfig.app.json` aufnehmen)
   hebelte die Node-Typ-Trennung aus, die der Kommentar dort ausdrücklich schützt.
2. **Rot→Grün Token-Erzeugung**: `tokens.test.ts` zuerst (Vollständigkeit je Gruppe, kein
   `var()` im Ergebnis, `initial`-Ausschluss mit Zählung, Abstandsstufen gegen den echten
   Tailwind-Lauf, die fünf wertetragenden Abweichungen namentlich, Dateischnappschuss), dann
   `tokens.ts`.
3. **Rot→Grün Symbol-Erzeugung**: `icons.test.ts` (genau zwölf, Namen exakt die String-Union aus
   `icon.tsx`, Strichstärke 2, `currentColor`, kein `width`/`height`, Dateischnappschuss), dann
   `icons.ts`.
4. **Rot→Grün Nutzlast-Regeln**: `payload.test.ts` — zuerst die synthetischen
   Erkenner-Selbsttests und die Struktur-Zusicherungen (ohne Bestand schreibbar und sofort rot),
   danach die JS-Nutzlast, danach im grünen Schritt Messzahlen und Freigabeliste.
5. `design/penpot/README.md`.
6. Skill `penpot-design`.
7. **Doku nachziehen**: Kopf von `0005` (Archiv), `0004` (Quellensatz auf Penpot,
   Abweichungstabelle bleibt und wird als *Herkunft* etikettiert, Archivverweis),
   `.claude/skills/design-system/SKILL.md` (Quellenzeile nennt Penpot und den neuen Skill),
   Trigger-Tabelle in `.claude/skills/review/SKILL.md` samt der beiden synchronpflichtigen ADRs,
   sowie die Ergänzungen in `specs/architecture/0002-testkonzept.md` und
   `specs/architecture/0003-securitykonzept.md`. Der `**Teilweise abgelöst:**`-Vermerk im Kopf
   von ADR 0055 liegt bereits auf dem Branch.
8. Gesamt-Qualitätscheck (`npm run lint`, `npm run typecheck`, `npm run test -- --run`,
   `npm run build`, `pytest` unter `scripts/`).

### Zweite Hälfte: die Arbeit an der Instanz

Subagenten dieses Repositorys haben keine MCP-Werkzeuge, und es braucht ohnehin eine von Daniel
verbundene Sitzung. **Die Penpot-Hälfte läuft deshalb in der Hauptsession über den Skill
`penpot-design`**, nicht im `developer`: Vorprüfung (kommt „No Penpot instance connected",
**bricht der Ablauf ab** — kein Ersatzweg, keine Teilausführung), dann Tokens → Symbole →
Bausteine → Varianten → Rücklesen, jeder Schritt einzeln. Die Nutzlast wird mechanisch aus
Datendatei + Skriptdatei zusammengesetzt und **unverändert** an `execute_code` übergeben; ist ein
Wert falsch, wird `index.css` geändert und neu erzeugt.

**Nachprüfbarer Abschluss:** `verify.js` liest zurück, der Vergleich gegen
`tokens.json`/`icons.json`/`components.json` ergibt keine Abweichung bei den erzeugten Objekten,
dazu eine Sichtprüfung über `export_shape`. Zusätzlich in Penpot vorhandene Tokens sind ein
**Befund**, kein Fehlschlag. Das Ergebnis wird als selbst formulierte Aussage im PR festgehalten,
**nicht als Datei eingecheckt** und nie als eingefügte Werkzeugausgabe.

**Was ein erneuter Lauf überschreiben darf, ist nach Art verschieden:**
`seed-tokens.js`/`seed-icons.js` dürfen jederzeit erneut laufen (ihr Inhalt ist vollständig
erzeugt). `seed-components.js` läuft **nur auf einer leeren oder neu aufgebauten Datei** — nach
dem ersten Bespielen gehören die Bausteine Penpot, seine dauerhafte Rolle ist die
Wiederherstellung nach Instanzverlust. Diese Vorbedingung steht **fail-closed im Skript selbst**,
vor dem ersten Schreibzugriff, nicht nur als Prosa im Skill. **Kein Skript löscht je etwas.**

### Harte Regeln und bekannte Fallen

- **Keine pauschale Ersetzung Figma → Penpot.** Geändert wird nur, was Figma **als geltende
  Quelle** benennt (die Stellen aus Schritt 7). Umgesetzte Feature-Specs (`0320`, `0321`), der
  Rumpf von ADR 0055 und die Wörter „Board"/„Board-Maß" in Code-Kommentaren und Tests bleiben:
  Sie berichten zutreffend die *Herkunft* einer Zahl. Sie umzuschreiben machte ausgerechnet die
  acht Abweichungen unerklärlich. Eine gut gemeinte Suchen-und-Ersetzen-Runde ist hier der
  wahrscheinlichste Fehler.
- **Die Instanzadresse kommt nicht ins Repo** — kein Hostname, keine URL, keine Zugangsdaten.
  Im Repo steht nur der Dateiname der Penpot-Datei.
- `frontend/penpot/**` liegt bewusst **außerhalb** von `frontend/src/`: Der Vertragstest läuft
  über `src/**` und würde Token-Namensliterale mit den Präfixen `bg`/`text`/`border`/`font`/
  `rounded` als tote Tailwind-Utilities melden (`border-control` wäre so ein Fehlalarm).
- `icons.ts` importiert **nicht** aus `lucide-react` — das darf statisch geprüft nur `icon.tsx`.
  Weil `frontend/penpot/` außerhalb des Vertragstest-Suchraums liegt, wird diese Regel dort
  **eigenständig wiederholt** statt vorausgesetzt.
- **`currentColor` hat in Penpot keine Entsprechung.** Die Strichfarbe der freistehenden
  Symbolbibliothek wird über `color.text-h` gesetzt; `width`/`height` werden aus dem gerenderten
  Markup entfernt, `viewBox` bleibt. Zusätzlich ist nach `createShapeFromSvg` das automatisch
  eingehängte Kind `base-background` zu entfernen.
- **Die `seed-*.js` sind zum PR-Zeitpunkt unausgeführter Code.** CI prüft Erzeugung,
  Vollständigkeit, Benennung und die Wertfreiheit — nicht, ob ein API-Aufruf funktioniert. Ein
  bis zwei Korrekturrunden nach dem ersten echten Lauf sind eingeplant, kein Fehlschlag.
- **Die Plugin-API ist am 2026-09-08 an einer verbundenen Instanz gemessen worden** (leere
  Scratch-Datei, danach rückstandsfrei abgeräumt). Ergebnis — es wird nicht mehr vermutet:
  - **Tokenbindung wirkt.** `applyToken`/`applyToShapes` bindet Fläche, Radius, Padding, Gap,
    Schriftgröße, Schnitt, Laufweite und Textfarbe; `shape.tokens` liefert danach die Zuordnung
    Eigenschaft → Tokenname, und die Werte greifen tatsächlich. Eine Bibliotheks-Instanz **erbt**
    diese Bindungen — das ist der Mechanismus hinter AK 6.
  - **Varianten tragen.** `penpotUtils.createVariantContainer` erzeugt einen echten
    `VariantContainer`, `variantProps` stimmt, `switchVariant` schaltet um, kein `variantError`.
    AK 4 ist damit erfüllbar. **Nebenwirkung:** Die Einzelkomponenten werden dabei in „Component"
    umbenannt — der sprechende Name lebt am Container.
  - **`createShapeFromSvg(svgString)` existiert** und liefert eine `Group`. **Sie hängt ein
    zusätzliches Kind `base-background` (Rechteck) an**, das beim Symbolimport zu entfernen ist —
    sonst trägt jedes Symbol eine unsichtbare Fläche.
  - **Vier Abweichungen von der API-Doku**, alle gemessen: (1) es gibt **keinen** Token-Typ
    `lineHeight`/`lineHeights` — der Aufruf scheitert hart; (2) die Eigenschaft für die
    Schriftfamilie heißt **`fontFamily`** (Singular), der dokumentierte Name `fontFamilies` wirft;
    (3) der **Schreibwert** eines `typography`-Tokens benutzt die **Singular**-Schlüssel
    (`fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing`, `textCase`,
    `textDecoration`) — die Pluralformen aus `TokenTypographyValue` sind die **Lese**form;
    (4) ein Token-Satz wirkt erst nach `toggleActive()`, vorher bleibt `resolvedValue` `null` und
    nichts greift.
  - **Laufweite muss eine blanke Zahl in px sein.** `-0.02em` wird als Tokenwert akzeptiert und
    löst zu `-0.02` auf, kommt an der Textform aber als `0` an. Der Erzeuger rechnet em gegen die
    Schriftgröße der Stufe um (`-0.02em` bei 64px → `-1.28`); als Zahl greift sie nachweislich.
  - **Referenzen im Verbundtoken funktionieren:** eine Referenz der Form `{font-family.sans}`
    löst innerhalb eines `typography`-Werts korrekt auf, sowohl für die Familie als auch für die
    Größe.
- `design/` ist ein neues Wurzelverzeichnis. Von `scripts/tests/test_verweisnummern_in_markdown.py`
  erfasst — `design/penpot/README.md` muss die Nummernregel bei Verweisen auf ADR 0064/0065
  einhalten.

## UI/UX

**Keine sichtbare Anwendungsoberfläche.** Der Quellenwechsel und der Aufbau der Penpot-Datei sind
Werkzeugarbeit; sie ändern weder die ausgelieferte Oberfläche noch den Bestand von PhotoSort.
Kein `.tsx` und kein Wert in `index.css` wird angefasst.

Zwei Punkte fallen trotzdem in die Design-System-Zuständigkeit und sind hier entschieden:

**1. Die Achter-Tabelle in `0004-design-system.md` bleibt, wechselt aber ihre Bedeutung.** Heute
steht sie unter „damit sie bei der nächsten Board-Aktualisierung nicht stillschweigend
zurückrepariert werden". Künftige Überschrift: **„Acht dokumentierte Abweichungen — Herkunft der
heute geltenden Werte"**. Sie beschreibt ab jetzt nicht mehr einen offenen Abgleich gegen eine
fremde, noch gepflegte Quelle, sondern die Herkunft der Werte, die Penpot bereits korrekt trägt.
Die Begründung jedes Eintrags bleibt für künftige Änderungen bindend. **Die Warnung vor der
„stillschweigenden Rückreparatur" verliert ihren Gegenstand und wird ersatzlos gestrichen** — es
gibt keine zweite, weitergepflegte Quelle mehr, gegen die zu schützen wäre. Sie stehen zu lassen
machte sie zur bloßen Formel.

Der Quellensatz nennt danach die Penpot-Datei als alleinige Design-Quelle (Gestaltung) mit
Verweis auf ADR 0064, hält fest, dass die maßgebliche Werteliste im Repo `frontend/src/index.css`
ist, und kennzeichnet den Verweis auf `0005` ausdrücklich als **Archivverweis** (Momentaufnahme
des Figma-Stands, wird nicht mehr gepflegt, normativ abgelöst).

**2. Die Zustandsmatrix ist eine Design-System-Aussage, kein Umsetzungsdetail.** Sie ist aus den
zehn Produktdateien abgeleitet, nicht aus dem Denkbaren. **Jede Achse eines Bausteins muss
unabhängig von den übrigen wählbar sein** — in Penpot entsteht daraus das Kreuzprodukt, und jede
Kombination, die das Produkt nicht kennt, wäre dort ein Angebot, das in die Irre führt. Wo zwei
Dinge nicht orthogonal sind, gehören sie in **eine** Achse, nicht in zwei:

| Baustein | Zustände / Ausprägungen in Penpot |
|---|---|
| `button` Schaltfläche | Ausprägungen `default`/`secondary`/`outline`/`ghost`/`destructive`/`link`, Größen `default`/`sm`/`icon`; Zustände normal, hover, active, disabled, busy |
| `input` Eingabefeld | normal, fokussiert, fehlerhaft, **fokussiert+fehlerhaft** (tritt gleichzeitig auf, beide Merkmale bleiben sichtbar), disabled |
| `badge` Kennzeichen | **Eine** Ton-Achse (`favorite`/`album-worthy`/`rejected`/`accent`/`neutral`, dazu `unbewertet` aus `RatingBadge`, falls es sich visuell von `neutral` unterscheidet) × Füllung `solid`/`suggested`. „Unbewertet" ist **kein** eigener Zustand neben dem Ton — die Kombination „favorite und zugleich unbewertet" gibt es im Produkt nicht. |
| `card` Karte | über `PhotoCard`: unbewertet („Neu"), favorite, album_worthy, rejected, jeweils mit/ohne `suggested` |
| `alert` Hinweis | **Eine** Achse mit sieben Werten, weil zwei verschiedene Bauteile in diesem Baustein zusammenfallen: `hinweis-success`/`hinweis-warning`/`hinweis-error` (aus `ui/alert.tsx`) und `status-never`/`status-running`/`status-success`/`status-failed` (aus `StatusTag.tsx`, `running` mit Spinner). Getrennte Achsen erzeugten Kombinationen wie „Warnung × läuft", die es nicht gibt; die Präfixe sind nötig, weil `success` sonst in beiden Hälften vorkäme. |
| `checkbox` Auswahlkästchen | checked, unchecked, disabled |
| `switch` Schalter | checked, unchecked, disabled (Zustand wird über Knaufposition **und** Farbe getragen, nicht über Farbe allein) |
| `progress` Fortschrittsanzeige | determiniert (Wert 0–100), unbestimmt (Puls) |
| `dialog` Dialog | offen/geschlossen; Variante `cancelDisabled` |
| `chip` Kategorie-Chip | dreizehn Ausprägungen, deckungsgleich mit dem Kategorien-Set |

**Der Board-Kartenzustand „ausgewählt" wird ausdrücklich nicht nach Penpot übernommen.** `0004`
hält fest, dass er bewusst nicht umgesetzt ist, weil PhotoSort keine Foto-Auswahl kennt;
`PhotoCard` hat weder eine `selected`-Prop noch ein `data-selected`. Ihn in Penpot vorzubauen wäre
eine Vorwegnahme — er kommt mit der Story, die eine Foto-Auswahl tatsächlich einführt. Penpot ist
ab jetzt die Gestaltungsquelle, aber „zur Vorsorge" wird dort nichts angelegt, was das Produkt
nicht hat.

`.claude/skills/design-system/SKILL.md` nennt Figma heute nicht namentlich; nachzuziehen ist
allein die Quellenzeile, die zusätzlich Penpot als Design-Quelle und `penpot-design` als den Weg
dorthin nennt.

## Security

**Einstufung: sicherheitsrelevant, kein Blocker.** Das Produkt selbst ist unberührt — kein
Backend- und kein Frontend-Produktcode, kein neuer Endpunkt, keine neue npm-Abhängigkeit im
ausgelieferten Bundle, keine Datenmodell-Änderung, keine neue Eingabe von außen, keine Änderung
an Auth, Berechtigungen oder Datensichtbarkeit zwischen den beiden Nutzern. Die Angriffsfläche
liegt vollständig im KI-Entwicklungsablauf. Wirklich neu sind genau zwei Dinge:

1. Ein **öffentliches** Repository beschreibt ab jetzt eine **private, selbst gehostete
   Infrastruktur**.
2. Eine **Datei im Repository wird zu Code, der in Daniels angemeldeter Browsersitzung ausgeführt
   wird** — mit den Rechten dieser Sitzung, nicht in einer Sandbox.

### 1. Die Instanz bleibt unbenennbar

Im Repository steht ausschließlich der **Dateiname** der Penpot-Datei. Nirgends — nicht in ADR,
Spec, Skill, `design/penpot/README.md`, Nutzlast, Kommentar, Testdatei, Commit-Text, Diagramm
oder PR-Body — steht Adresse, Hostname, Port, Instanz-ID, Datei-/Projekt-ID, Benutzername oder
Token. Es entsteht **keine `.mcp.json` im Repository** und **kein `PENPOT_*`-Eintrag in
`.env.example`** — Letzteres ausdrücklich benannt, weil das die naheliegendste Stelle wäre, an
der eine Instanzadresse als „Vorlage" doch noch ins Repo geriete. Ebenfalls nicht ins Repository
gelangen ein `.penpot`-Export der Instanz oder ein Bildschirmfoto mit Adresszeile; die
Sichtprüfung läuft über `export_shape` auf eine Form, nicht über einen Fensterabzug.

**Der Prüfbericht des Rücklesens ist der Kanal, auf dem diese Regel am ehesten bricht.** Ein
PR-Body ist öffentlich und nicht zurücknehmbar, und eine rohe Werkzeugausgabe trägt typischerweise
IDs und Pfade mit. Es gilt deshalb Härtungsregel 4.3 aus
[`github-access`](../../.claude/skills/github-access/SKILL.md) unverändert auch hier: In ein
dauerhaftes GitHub-Artefakt gelangt ausschließlich **selbst formulierter** Inhalt — ein Urteil,
nie die eingefügte Ausgabe von `verify.js` oder eine Fehlermeldung des MCP-Servers. Rohausgaben
gehen in den Chat, den ein Mensch liest.

**Struktureller Anker (Soll, empfohlen):** ein Test nach dem Vorbild der bestehenden
`scripts/tests/`-Wächter, der für `design/penpot/**`, `frontend/penpot/**` und
`.claude/skills/penpot-design/**` festhält, dass dort kein `://` außer den bekannten Doku-/
GitHub-Links und keine IP-Adresse vorkommt, und dass `.env.example` keinen `PENPOT_`-Eintrag
trägt. Das ist genau die Klasse Regel, die still verfällt — sie steht in Prosa, gilt für Dateien,
die künftig von Agenten bearbeitet werden, und ihr Bruch ist in einem öffentlichen Repo nicht
zurücknehmbar.

### 2. Die Nutzlast ist reviewpflichtiger Code

`execute_code` führt den übergebenen JavaScript-Text im Plugin-Kontext von Daniels
**angemeldeter** Sitzung aus. Der Blast-Radius ist nicht die eine Design-Datei, sondern alles, was
diese Sitzung erreichen kann. CI kann die Skripte nicht ausführen — **das Review ist das einzige
Gate.** Die abschließende Liste dessen, was die Nutzlast darf, steht in ADR 0065 Abschnitt 5
Punkt 6 (erlaubt: Plugin-API auf der einen Datei; verboten und statisch geprüft: Netzwerkzugriff,
dynamische Codeerzeugung, DOM-Zugriff, Zugriff auf andere Dateien der Instanz, fremde
`storage`-Schlüssel, Löschen fremder Objekte). Sie wird mit demselben Mittel geprüft, das ohnehin
für „kein wörtlicher Farb-/Größenwert" gebaut wird — weitere verbotene Bezeichner in einem
bereits geplanten Test, kein neuer Mechanismus.

**Herkunft (Muss):** Die Nutzlast stammt ausschließlich aus den Dateien des Feature-Branches, zum
Ausführungszeitpunkt gelesen. Nie aus einer Chat-Nachricht, einem Modell-Nachbau, einem
eingefügten Schnipsel, nie „mit einer kleinen Anpassung im Aufruf". Die Regel „unverändert
übergeben" ist damit **zugleich eine Sicherheitsregel**: Sie ist die Stelle, an der sonst eine
Zeile in die Ausführung käme, die kein Review gesehen hat.

**Zusammensetzung.** Härtungsregel 4.1 („Freitext ist immer ein abgegrenzter Wert, nie Teil der
Aufrufstruktur") ist hier über die **Herkunft** eingelöst, nicht über Maskierung — der eingefügte
Text ist vollständig selbst erzeugt. Sie gilt trotzdem und liefert drei Auflagen: genau **eine**
Einfügestelle (`const <NAME> = <exakter Dateiinhalt>;` plus unveränderte Skriptdatei, kein
zweiter interpolierter Wert); die Datendatei wird vor dem Zusammensetzen mit `JSON.parse` geprüft
und der Ablauf bei Fehlschlag abgebrochen; und der Erzeuger gibt **keinen Schlüssel `__proto__`**
aus — derselbe Text bedeutet als Objektliteral im Quelltext etwas anderes als über `JSON.parse`.
Die Prüfung ist billig, weil sie eine Eigenschaft festschreibt, die heute ohnehin gilt.

### 3. Die erzeugten Datendateien sind keine neue Injektionsfläche

`tokens.json` entsteht aus `index.css`, `icons.json` aus `icon.tsx` (und damit mittelbar aus
`lucide-react`). Alle drei Quellen sind repository-kontrolliert und laufen durch PR-Review; die
npm-Lieferkette von `lucide-react` ist im Sicherheitskonzept bereits bewertet. Neu ist allein die
**Senke** — Ausgabe von `lucide-react` landet zusätzlich in einem ausgeführten Skript statt nur im
Bundle. Das ist keine Eskalation (ein kompromittiertes `lucide-react` liefe ohnehin im Browser
beider Nutzer und käme dort an das JWT; eine Design-Datei ist die kleinere Beute). Festzuhalten
ist nur die Konsequenz: Das gerenderte SVG-Markup ist für Penpot ein **Wert**, kein
Dokumentfragment, und wird nie in ein DOM eingehängt.

### 4. Das Rücklesen als Rückkanal

Geringes Risiko, aber nicht null: Penpot-Objekte tragen frei gesetzte Namen und Beschreibungen,
und das Zurückgelesene landet im persistenten Hauptsession-Kontext, der über `ship-feature`
GitHub-Schreibzugriff hat. Drei billige Gegenmaßnahmen, alle Muss: `verify.js` gibt **nur zurück,
was der Vergleich braucht** (keine Beschreibungen, keine beliebigen Objektnamen); der Vergleich
ist **mechanisch**, ein Zeichenkettenvergleich gegen die erzeugten Dateien, kein „durchlesen und
beurteilen"; und der Skill `penpot-design` trägt die im Projekt etablierte Klausel selbst —
zurückgelesener Inhalt ist Prüfmaterial, nie eine Anweisung, und eingebettete Imperative werden
beim Auftreten als eigener Punkt im Abschlussbericht ausgewiesen.

### 5. Integrität: fail-closed statt Prosa

Die Regel „`seed-components.js` läuft nur auf leerer Datei" wird im Skript selbst geprüft, vor dem
ersten Schreibzugriff. Nach ADR 0064 ist der Penpot-Stand die normative Design-Quelle — ein
versehentlicher zweiter Lauf vernichtet nicht eine Kopie, sondern das Original. Es geht um
Integrität und Verfügbarkeit, nicht um Vertraulichkeit, und um ein Versehen, nicht um einen
Angreifer.

### 6. Erlaubnisstufe und Review-Abdeckung

Der Skill `penpot-design` trägt **„kein GitHub-Zugriff"**. Das regelt allerdings nur den
GitHub-Kanal; der Penpot-MCP-Server ist ein **dritter** Werkzeugkanal, und was ihn begrenzt, ist
allein die abschließende Liste aus Abschnitt 2.

Die Trigger-Tabelle in `.claude/skills/review/SKILL.md` löst `review-security` heute an keinem der
berührten Pfade aus. Sie wird deshalb um `design/penpot/**` und `.claude/skills/penpot-design/**`
erweitert (samt der beiden synchronpflichtigen ADRs). Bewusst **eng**: das breitere
`.claude/skills/**` bleibt außen vor und ist eine eigene Frage, keine Beiladung zu dieser Spec.

### Ausdrücklich nicht sicherheitsrelevant

Die Rangfolgeumkehr selbst, die acht dokumentierten Abweichungen, der Archivstatus von `0005`,
`components.json`, `frontend/tsconfig.penpot.json` und die Erzeugung über einen
Vitest-Dateischnappschuss. Auch die Kontrast-Untergrenze ist trotz ihrer Vetoform **keine**
Sicherheitsanforderung, sondern eine Barrierefreiheits-/Produktanforderung — sie steht hier nur,
damit niemand sie später für ein Sicherheitskriterium hält und aus dem falschen Grund verteidigt
oder aufgibt.

## Teststrategie

### Die Grenze, entlang der gebaut wird

Die Spec zerfällt in eine **Repo-Hälfte** (erzeugte Datendateien, handgeschriebene Nutzlast,
statische Regeln — vollständig in CI) und eine **Penpot-Hälfte** (Aufbau und Rücklesen an der
Instanz — für kein Werkzeug dieses Repositorys erreichbar). Die Teststrategie folgt dieser
Grenze. Wer sie quer liest, hält die Penpot-Hälfte für eine Testlücke; sie ist eine
Zuständigkeitsgrenze, und sie ist unten benannt.

Kein Backend-Code, keine Python-Zeile, kein `.tsx`. **Das Coverage-Gate
(`--cov-fail-under=80`) bewegt sich um exakt null.** Die neue Ebene läuft im bestehenden
`frontend`-CI-Job mit — ohne neuen Job, ohne neues Kommando, ohne neue Abhängigkeit.

### Ebene 1 — Der Erzeuger *ist* der Test

`toMatchFileSnapshot` wird als **Erzeuger** verwendet, nicht als Regressionsnetz. In CI legt
Vitest eine **fehlende** Schnappschussdatei nicht an, sondern schlägt fehl — die beiden
JSON-Dateien müssen eingecheckt sein.

Schnappschussgleichheit sagt nur „unverändert", nicht „richtig". Daneben stehen deshalb
Inhaltszusicherungen, die auch bei einem frisch erzeugten Schnappschuss greifen:

**`tokens.test.ts`:** eingefrorene Kardinalitäten je Gruppe (64 `color`, 5 `borderRadius`,
8 `spacing`, 2 `fontFamilies`, 7 `typography`); je Typografie-Token die Vollständigkeit seiner
fünf Felder (Familie als Referenz, Größe, Zeilenhöhe, Schnitt, Laufweite) und die **Umrechnung
der Laufweite von em in eine blanke px-Zahl**, mit der Stufe als Bezugsgröße; **Fehlschlagen
statt Überspringen** bei jeder nicht verstandenen Deklaration; `initial`-Werte ausgeschlossen und
**gezählt** (genau sechs); parserunabhängige Gegenprobe (für jedes Farbtoken steht `--<blatt>:`
wörtlich in `index.css`); Abstandsstufen gegen den echten Tailwind-Lauf mit **eigenem
`compile()`-Lauf je Stufe** (`build()` arbeitet inkrementell — sonst färbt der erste Treffer alle
folgenden grün) und geprüft wird der **erzeugte Deklarationswert**, nicht „erzeugt eine Regel";
Schriftfamilie ohne Anführungszeichen und ohne Ausweichkette, beide Hälften als eigene Testfälle
(ein naives `split(',')[0]` liefert die Apostrophe mit, und ein Schriftname mit Anführungszeichen
findet in Penpot keine Schrift); **die fünf wertetragenden Abweichungen namentlich** (`#8D92A4`
statt `#62677A`, `#727891` statt `#2A2E3D`, `#FF5A26` statt `#FF3D00` als Textfarbe, `#0B0C10`
als Badge-Tinte, `#FF44A1` statt `#FF007F`) — das ist die eingefrorene Tabelle, die AK 2 **ist**;
Reihenfolge = Deklarationsreihenfolge, Serialisierung festgelegt auf
`JSON.stringify(x, null, 2) + '\n'`.

**`icons.test.ts`:** genau zwölf, Schlüsselmenge deckungsgleich mit `ICON_NAMES`; gerendert über
die projekteigene `Icon`-Komponente, **nie** über einen Direktzugriff auf `lucide-react` (die
Regel wird hier eigenständig wiederholt, weil `frontend/penpot/` außerhalb des
Vertragstest-Suchraums liegt); festgelegte Normalisierung (entfernt: `data-icon`, `focusable`,
`aria-hidden`, `width`, `height`; erhalten: `viewBox`, `stroke-width="2"`,
`stroke="currentColor"`, `fill="none"`, `stroke-linecap`/`-linejoin`), jede Zusage ein eigener
Testfall, damit sie bei einem Paket-Update nicht still kippt.

### Ebene 2 — Statische Regeln über die Nutzlast (`payload.test.ts`)

Suchraum sind die **handgeschriebenen** Dateien unter `design/penpot/`: `seed-tokens.js`,
`seed-icons.js`, `seed-components.js`, `verify.js`, `components.json`. Ausdrücklich **nicht**
`tokens.json`/`icons.json` — sie sind erzeugt, sie **müssen** Werte tragen, und genau deshalb sind
sie die Gegenprobe. `README.md` ist Prosa und bleibt außen vor.

1. **Kein wörtlicher Farb-/Größenwert in der handgeschriebenen Nutzlast** — die tragende
   Zusicherung, ausgeführt im eigenen Abschnitt unten.
2. **Referentielle Integrität, einseitig:** jeder in `components.json`/`seed-components.js`
   genannte Tokenname existiert in `tokens.json`. Die Gegenrichtung wird **nicht** geprüft (sie
   zwänge zum Ausdünnen eines bewusst vollständigen Satzes); stattdessen eine
   **Gruppen**-Zusicherung: jede Tokengruppe wird von mindestens einem Baustein verwendet.
3. **Namensform:**
   `^(color|radius|space|font-family|text)\.[a-z0-9-]+$` — geschlossenes Gruppenvokabular,
   damit eine neue Gruppe bewusst eingetragen wird statt als Tippfehler durchzulaufen. Das
   Vokabular ist **erschöpfend**: Es nennt genau die fünf Gruppen, die `tokens.json` führt, und
   keine auf Vorrat. Eine erlaubte, aber unbenutzte Gruppe wäre eine Zusicherung, die nichts
   zusichert.
4. **Die zehn Bausteine als geschlossene Namensmenge, nicht als Kardinalität.** „Genau zehn"
   bestünden auch zehn beliebige.
5. **Zustandsabdeckung gegen den Produktcode, nicht gegen eine gepflegte Liste.** „Mindestens ein
   Zustand" wäre erfüllt, wenn jeder genau `default` trägt — das ist AK 4 nicht. Trägt die
   Produktdatei eine Variante aus dem geschlossenen Zustandsvokabular, führt `components.json`
   den Zustand. Breakpoint- und Layout-Varianten (`sm:`, `lg:`, `motion-reduce:`) zählen **nicht**
   — sonst ist die Regel eine Fehlalarm-Maschine.
6. **Der Kategorie-Chip trägt dreizehn Ausprägungen**, deckungsgleich mit dem Kategorien-Set, das
   der Vertragstest bereits einfriert. Sie sind erzeugt, nicht getippt.
7. **Die Idempotenz-Asymmetrie als Form, nicht als Suche.** Jede Aufbaudatei trägt **genau eine**
   Zeile `// LAUFREGEL: jederzeit-wiederholbar` bzw. `// LAUFREGEL: nur-auf-leerer-datei` an
   fester Stelle, aus geschlossenem Vokabular; die Zuordnung Datei → Regel ist eingefroren. Eine
   Erwähnung im Fließtext des Dateikopfs löst nichts aus und erfüllt nichts — ein Kopftext darf
   über seinen eigenen früheren Zustand reden.
8. **Die Vorbedingung von `seed-components.js` steht vor dem ersten Schreibzugriff** —
   Reihenfolge-Zusicherung über die **geparste Aufrufstelle**, nie über `text.index`.
9. **Die Verdrahtung des neuen TS-Projekts wird selbst zugesichert:** `tsconfig.json` referenziert
   `./tsconfig.penpot.json`, dessen `include` nennt die drei Dateien. Ohne diese Zusicherung ist
   der stille Fehlermodus, dass `frontend/penpot/**` von `tsc -b` **gar nicht** geprüft wird.

### Die Abwesenheits-Zusicherung im Einzelnen

Die Selbstschutz-Regel des Testkonzepts verlangt Suchraum-Untergrenze, Gegenprobe je
Musterfamilie und Mutationsnachweis; weil der Bestand bei Testentstehung grün ist, greift
zusätzlich die vierte Auflage (Untergrenze für das, was der Test **gesehen** hat).

**Suchraum:** die fünf Pfade **namentlich** als Schlüssel behauptet, nicht „mindestens fünf
Dateien"; je Datei eine Mindest-Zeichenzahl > 0; zusätzlich eine **Mindestzahl gescannter
Zeilen** nach Vorbehandlung, sonst ist ein kaputter Vorbehandlungsschritt von einem sauberen
Bestand nicht zu unterscheiden. Ein Selbstausschluss ist **nicht** nötig und wird nicht
vorsorglich mitkopiert: `payload.test.ts` liegt unter `frontend/penpot/`, außerhalb des
Suchraums.

**Zwei Vorbehandlungsschritte, beide mit eigenem Selbsttest:** zeilentreue Kommentarstreichung
(ein Wert in einem Kommentar erreicht Penpot nicht; die Zeilenzahl muss erhalten bleiben, sonst
zeigen Meldungen nach einem Blockkommentar auf die falsche Zeile) und **zeilentreue Maskierung
der Tokennamen-Literale** — ohne sie schlagen `space.3`, `space.16`, `text.2xl` als blanke
Zahlen an, und das ist der Fehlalarm, der die Regel sofort unbrauchbar machte.

**Vier Musterfamilien:** Hex (`3`–`8`-stellig — eine auf `{6}` verengte Suche wäre genau das
Loch, gegen das der Test antritt), Farbfunktion (`rgb`/`hsl`/`lab`/`oklch`/`color-mix`, mit
Wortgrenze **und** `\(`, sonst trifft `lab` in `label`), Länge mit Einheit, blanke Zahl (mit
Allowlist `{0, 1, 2, -1}` und **fundstellengenauer** Freigabeliste). Die Freigabeliste ist
bewusst nicht dateiweise: `verify.js` braucht legitim `12`, `10`, `64`, `13` als Kardinalitäten,
und eine dateiweise Freigabe wäre ein stiller Selbstausschalter.

**Gegenprobe:** Die erzeugten Datendateien sind der Positivkorpus für Hex, Länge und blanke Zahl.
**Die Farbfunktions-Familie hat keine repo-seitige Gegenprobe** — das Design-System führt
ausschließlich Hex. Sie bekommt deshalb den vom Testkonzept vorgesehenen namentlichen Kommentar
plus einen synthetischen Erkenner-Selbsttest; ein Muster ohne mögliche Gegenprobe wird nicht
heimlich mitgeführt. Dazu je Familie ein tabellengetriebener Mikrotest mit Muss-Treffern **und**
Muss-Nicht-Treffern; die zu durchsuchenden Dateien sind ein Parameter, damit gegen literal
geschriebene Eingaben geprüft werden kann (kein Dateisystem, keine Fixtures).

**Mutationsnachweis** — von Hand ausgeführt, Protokoll in den PR-Text (Datei, eingesetzter Wert,
Name des rot gewordenen Tests, Bestätigung der Rücknahme): Hex-Wert einsetzen; `rgb()` einsetzen
(die wichtigste der Proben, weil das die Familie ohne Bestandsgegenprobe ist); `"12px"` in
`components.json`; `600` als Schnittwert; eine freigegebene Fundstelle um eine Zeile verschieben
(verwaiste Freigabe); Freigabe-Ausschnitt durch den bloßen Suchbegriff ersetzen; und die
`LAUFREGEL`-Zeile in **beide** Richtungen mutieren (fehlend **und** überzählig — die überzählige
ist die, die erfahrungsgemäß fehlt).

### Ebene 3 — Der Abschluss der Penpot-Hälfte

`verify.js` trägt: AK 1 (Name + Wert je Token **und** die Tokenbindung je Baustein — ohne
Letztere bliebe „zentral änderbar" unbelegt), AK 3 (Namensmenge, Kardinalität und **Typ**: es sind
Bibliotheks-Komponenten, nicht Formen, die so heißen), AK 4 zur Hälfte (`variantProps` und Zahl
der Ausprägungen je Eigenschaft; die andere Hälfte — der Bezug zum Produktcode — trägt Ebene 2
Regel 5, **einzeln keine von beiden**), AK 5 namentlich und geometrisch nur, wenn die API die
Pfaddaten hergibt.

Für **AK 2, 7 und 8 entsteht kein neuer Test** — das ist eine Feststellung, keine Auslassung:
AK 2 über die fünf eingefrorenen Abweichungswerte, AK 7 über die Existenz von ADR 0064 im Status
`Accepted`, AK 8 über `index.css` plus den bestehenden Vertragstest.

### Der Kontrast-Vertragstest

Der Test mit den Kontrastzusagen ist `frontend/src/designSystem.contract.test.ts`, Block
„Design-Vertrag: Kontrastmatrix". **Diese Spec berührt seine Zusagen nicht — und das gehört
ausdrücklich in den PR-Text**, sonst liest ein Review „Design-System-Story ohne eine Zeile im
Vertragstest" als Lücke. Drei Berührungen ohne Codeänderung: seine Rolle wächst (er ist ab ADR
0064 Abschnitt 4 die Stelle, an der ein zurückgewanderter Wert unter AA auffällt); seine
Zusicherung „jedes `:root`-Token ist ein 6-stelliger Hexwert" trägt jetzt zwei Dinge (sie ist
zusätzlich die Voraussetzung der Penpot-Erzeugung — `tokens.ts` muss bei einem nicht-Hex-Wert
nach derselben Regel **scheitern statt zu überspringen**); und sein Suchraum endet bei `src/**`,
womit `frontend/penpot/**` von der Streichliste nicht erfasst ist.

### Vorführungsregel zu AK 6

Die Vorführung gilt als bestanden, wenn am Pull Request (nicht im Repository — ein eingechecktes
Bild wäre eine dritte Wertekopie) alle fünf Punkte vorliegen:

1. Ein per `export_shape` exportiertes Bild eines **neu zusammengesetzten Entwurfs**, der selbst
   keiner der zehn Bausteine ist. Ein Bild der Bausteinübersicht belegt AK 6 nicht.
2. Der Entwurf enthält **mindestens drei verschiedene Bausteine** und **mindestens einen
   umgeschalteten Zustand** (`switchVariant`), damit die Variantenzusage tatsächlich ausgeübt
   wird.
3. Daneben eine **zurückgelesene** Auflistung (per `execute_code` ermittelt, nicht behauptet): je
   Form die gesetzten Eigenschaften mit dem Tokennamen, der sie trägt — und **keine** Eigenschaft
   mit direktem Zahl- oder Hexwert, für die ein Token existiert. Das Bild zeigt „sieht richtig
   aus"; die Auflistung zeigt „ohne Handeintrag", und das ist die Zusage.
4. Der Entwurf wurde **von Claude** zusammengesetzt, im Ablauf des Skills `penpot-design`.
5. Ausdrücklich mitgeschrieben: **was die Vorführung nicht belegt** — dass es beim nächsten Mal
   auch so ist. Sie ist ein Einzelnachweis zu einem Zeitpunkt.

### Was CI hier nicht prüfen kann

Verbindlicher Bestandteil der Spec, nicht eine Entschuldigung am Rand; steht wörtlich auch im
Kopf jeder `seed-*.js` und in `design/penpot/README.md`.

1. **Die `seed-*.js` und `verify.js` sind zum PR-Zeitpunkt unausgeführter Code.** Geprüft sind
   Erzeugung, Vollständigkeit, Benennung, referentielle Integrität und Wertefreiheit. Ob ein
   Plugin-API-Aufruf funktioniert, kann kein Test hier sagen. Ein oder zwei Korrekturrunden nach
   dem ersten echten Lauf sind eingeplant.
2. **Kein Test kann Penpot lesen.** Der Abgleich ist eine Handlung, keine Zusicherung.
3. **Die Dauerregel „entwerfen nur mit Tokens" ist LLM-interpretierter Text.** Statisch verankert
   ist nur, *dass* sie im Skill steht.

**Für `review-tests`:** Ein Finding der Form „`seed-components.js` hat keine Tests" ist hier
**kein** gültiger Befund. Gültige Befunde sind: eine fehlende Zusicherung aus Ebene 1–2; eine
Musterfamilie ohne Gegenprobe und ohne Kommentar; eine Freigabe-Zeile ohne Fundstelle; oder eine
der oben benannten Grenzen, die **nicht** benannt wurde.

### Zu ergänzende Konzeptdokumente

- [`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md): neue `###`-Sektion
  „Erzeugte Datendateien als Testgegenstand" (der Dateischnappschuss als Codegenerator, mit den
  fünf Regeln, die über diese Spec hinaus gelten), ein Eintrag unter „Was bewusst nicht getestet
  wird" und vier Einträge unter „Bekannte Lücken". Die bestehenden Sektionen zum Design-Vertrag
  bleiben wortgetreu stehen.
- [`architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md): Ergänzung bei
  Vertrauensgrenzen (Penpot-MCP als dritter Werkzeugkanal, erstmals mit Ausführung von
  Repository-Code in einer angemeldeten Sitzung) und bei schützenswerten Assets (der Inhalt der
  Penpot-Datei ist ab ADR 0064 selbst Teil des Assets), ein neuer Angriffsflächen-Unterabschnitt
  im Vorausschau-Muster, sowie ein Restrisiko-Eintrag zu den unausgeführten Aufbauskripten.

## Entscheidungen

- **Keine der vier Konsultationen wurde übersprungen.** `architect` (Schritt 1), `ux-ui-designer`
  (Schritt 2), `test-engineer` und `security-engineer` (Schritt 3) sind alle gelaufen; für jeden
  lag mindestens ein konkret benennbarer Anhaltspunkt vor.
- **Zwei ADRs statt einer** (`0064` Rangfolge, `0065` Mechanismus): Die Rangfolge soll auch dann
  noch gelten, wenn der Mechanismus einmal ausgetauscht wird.
- **Idempotenz asymmetrisch** — Tokens/Symbole jederzeit wiederholbar, Bausteine nur beim
  Neuaufbau. *Von Daniel entschieden (2026-09-08), gegen „alles jederzeit neu erzeugbar" (machte
  Handarbeit in Penpot dauerhaft wertlos) und gegen „einmalig" (machte den Instanzverlust zum
  Totalverlust).*
- **Kein Skript löscht je etwas**; ein in Penpot zusätzlich vorhandenes Token ist ein Befund, kein
  Fehlschlag. *Von Daniel entschieden (2026-09-08).* Die konservative Richtung ist jederzeit
  verschärfbar, die Gegenrichtung nicht.
- **Die WCAG-AA-Kontrastuntergrenze schlägt auch einen Penpot-Wert**, und die Korrektur wird nach
  Penpot zurückgeschrieben. *Von Daniel entschieden (2026-09-08).* Ohne diese Klausel wäre AK 2
  nicht haltbar.
- **AK 6 wird als Vorführung präzisiert**, nicht als Zusicherung. *Von Daniel entschieden
  (2026-09-08).* Kein Test im Repo kann Penpot lesen; der Beleg liegt außerhalb.
- **Die Security-Trigger-Tabelle wird eng erweitert** (`design/penpot/**`,
  `.claude/skills/penpot-design/**`), das breitere `.claude/skills/**` ausdrücklich nicht. *Von
  Daniel entschieden (2026-09-08).*
- **Die Zahlen der Schrift-Tokens sind am Bestand ausgemessen, nicht überschlagen:** 7 Größen, 7
  Zeilenhöhen, aber nur 5 Schnitte und 1 Laufweite. Ein erfundener Standardschnitt `400` für
  `xs`/`sm` wäre genau die getippte Wertekopie, die ADR 0065 verbietet.
- **Der Kartenzustand „ausgewählt" wird nicht nach Penpot übernommen** — PhotoSort kennt keine
  Foto-Auswahl; ihn vorzubauen wäre eine Vorwegnahme.

## Offene Fragen

Keine. Die fünf Produktentscheidungen dieser Spec sind Daniel im `spec-writer`-Ablauf vorgelegt
und beantwortet worden (siehe „Entscheidungen"). Die drei nicht gemessenen Punkte der Plugin-API
(SVG-Import, `applyToken` auf Schriftfamilie/Schnitt, `currentColor`-Ersatz) sind keine offenen
Fragen an den Stakeholder, sondern **vor dem Bau** über `penpot_api_info` zu klären — und bei
Nichtverfügbarkeit zu melden statt zu umgehen.

## Out of Scope

- **Frontend-Produktcode.** Kein `.tsx`, kein Wert in `index.css`, keine neue npm-Abhängigkeit,
  keine Wertänderung. Die Gestaltung wechselt den Aufbewahrungsort, sie ändert sich nicht.
- **Ein Penpot→Repo-Automatismus.** Der Rückweg ist der normale Story-Weg, bewusst.
- **Das Nachziehen der Ansichten an den Entwurf.**
  [Issue #333](https://github.com/TheRealKoller/photosort/issues/333) bleibt unberührt.
- **`docs/architecture.md`, `docs/setup.md`, `docs/ai-workflow.md`.** Penpot ist eine
  Werkzeugabhängigkeit der Entwicklung, keine Laufzeitkomponente; Build, Tests, CI und Betrieb
  laufen unverändert ohne Penpot, und ein Ad-hoc-Werkzeugskill steht auch bei `browse-app` nicht
  im Workflow-Dokument.
- **Das breitere `.claude/skills/**` als allgemeiner Security-Trigger.** Ein erkannter, breiterer
  blinder Fleck — bewusst nicht in diese Spec beigeladen.
- **Komponententests für die vier Primitive ohne eigene Testdatei** (`card.tsx`, `progress.tsx`,
  `popover.tsx`, `skeleton.tsx`). Für diese Spec unschädlich, weil die Zustandsableitung die
  `.tsx` direkt liest; sie nachzuziehen wäre Scope Creep.
