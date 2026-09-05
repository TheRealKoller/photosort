# 0320 - Design-System "Dark Utility Register" (Fundament)

**Status:** Implemented ([PR #322](https://github.com/TheRealKoller/photosort/pull/322))
**Erstellt:** 2026-09-04
**Bezug:** [GitHub-Issue #320](https://github.com/TheRealKoller/photosort/issues/320), ADR [`0055-dark-utility-register-fundament.md`](../decisions/0055-dark-utility-register-fundament.md), Board-Referenz [`architecture/0005-board-dark-utility-register.md`](../architecture/0005-board-dark-utility-register.md) (Figma „Photosort Dark", `photosort-design-system` V1.2)

## Ziel

PhotoSort wird beim Sichten und Bewerten von Fotos benutzt. Die Oberfläche steht dabei unmittelbar
neben dem Bild und beeinflusst, wie dessen Farben wahrgenommen werden. Das heutige Design-System
„Organic" setzt darauf einen warmen Creme-Grund; auch sein Dunkelmodus ist keine neutrale, sondern
eine warm getönte Spiegelung derselben Tonleitern (bräunlicher Grund, Terracotta-Akzent). Für die
Kernaufgabe der App ist ein farbneutrales, dunkles Umfeld die sachlich bessere Wahl — es tritt
hinter dem Bild zurück, statt es einzufärben.

Dazu kommt eine bewusste Änderung der Haltung: „Organic" ist warm, großzügig und persönlich
gestaltet (runde Formen, Pillen, Display-Schrift). PhotoSort ist in der Nutzung ein Arbeitswerkzeug
für lange Sichtungssitzungen. Die in Figma ausgearbeitete Alternative „Dark Utility Register" ist
entsprechend sachlich, kompakt und informationsdicht.

**Zuschnitt:** Diese Spec ist **Stufe 1 von zwei** und stellt ausschließlich das gestalterische
Fundament um — Farben, Schriften, Raster, Formsprache, die wiederverwendbaren Grundelemente und den
Symbolsatz. Die gestalterische Überarbeitung der einzelnen Ansichten ist **Stufe 2** und in
[#321](https://github.com/TheRealKoller/photosort/issues/321) erfasst.

## User Story

Als Nutzer von PhotoSort möchte ich die Anwendung in einer neutralen, dunklen und sachlichen
Gestaltung bedienen, damit die Oberfläche die Farbwahrnehmung meiner Fotos nicht verfälscht und
lange Sichtungssitzungen angenehm bleiben.

## Akzeptanzkriterien

### Farbe

- [x] Die Anwendung erscheint durchgehend in der dunklen Farbwelt des Boards — unabhängig davon, ob das Gerät auf hell oder dunkel eingestellt ist. Ein heller Grund existiert nicht mehr. Nachgewiesen über vier Prüfungen: kein `prefers-color-scheme` in `frontend/`, `color-scheme: dark` gesetzt (`light` kommt nicht vor), `theme-color`/`manifest.theme_color`/`manifest.background_color` auf Board-Werte, und **keiner der Organic-Hexwerte** (`#f5ead8`, `#ebddc5`, `#c67139`, `#8c491a`, `#201e1d`, `#2e2b25`, `#7a8a5e`, …) kommt irgendwo in `frontend/` noch vor.
- [x] Die vier Hintergrund- und Oberflächenstufen des Boards sind als Tokens mit den Board-Hexwerten deklariert **und über `@theme` als Utility auflösbar** (tiefster Grund, Standardfläche, erhöhte Fläche für Karten und Popups, Overlay für Dialoge).
- [x] Die vier Akzentfarben des Boards sind hinterlegt und in ihrer Bedeutung eindeutig belegt: Auswahl/Favorit, Information, Aussortiert, Album-würdig. Jede ist genau einem sprechend benannten Token zugeordnet; `--accent` und `--rating-favorite` teilen den Wert, aber nicht den Namen.
- [x] Die vier Textstufen des Boards sind hinterlegt (primär, sekundär, gedämpft, deaktiviert).
- [x] Jede Text- und Symbolfarbe erreicht gegen ihren tatsächlichen Untergrund WCAG-AA: 4,5:1 für Fließtext, 3:1 für grafische Elemente und Bedienelement-Umrisse. Gemessen über die deklarierte Matrix, die alle Textstufen × vier Flächen, alle 13 Chip-Paare, alle 3 Bewertungspaare, alle 4 Status-Pillen auf `--elevated` sowie `--border-control`/`--danger` bei 3:1 umfasst. Zwei benannte, begründete Ausnahmen: `--text-disabled` (WCAG 1.4.3 nimmt inaktive Bedienelemente aus) und `--border` (rein dekorativ, nie einziger Umriss eines Bedienelements).
- [x] Die drei Bewertungszustände (Favorit, Album-würdig, Aussortiert) bleiben auch ohne Farbwahrnehmung unterscheidbar — Farbe allein trägt die Bedeutung nicht. Nachgewiesen als achromatische Eigenschaft: je Zustand sind Textbadge, Symbolname (`data-icon`) und beim Aussortierten die Durchstreichung im DOM vorhanden und über alle drei Zustände **paarweise verschieden**. Hintergrund: Favorit und Album-würdig liegen in Graustufen bei nur 1,10:1 zueinander, die Mehrfachcodierung ist die einzige Stütze dieses Kriteriums.

### Schrift

- [x] Die Schriften des Boards sind eingebunden: eine serifenlose Schrift für alle Texte, eine dicktengleiche für Datenausgaben. Die bisherigen Schriften (Display- und Fließtextschrift des Organic-Systems) werden nicht mehr verwendet.
- [x] Die Größenstufen des Boards stehen zur Verfügung (64 / 40 / 24 / 20 / 16 / 12 px sowie 14 px für Datenausgaben), jeweils mit den dort festgelegten Schnitten, Zeilenhöhen und Laufweiten. `text-4xl` und größer erzeugen keine Regel mehr.
- [x] Die Anwendung funktioniert weiterhin offline — die Schriften werden nicht erst zur Laufzeit aus dem Netz geladen. Nachgewiesen über: kein `fonts.googleapis.com`/`fonts.gstatic.com` in `frontend/`, keine externe Schrift-URL in der gebauten CSS, und die `woff2`-Dateien sind vom `globPatterns`-Precache des Service Workers erfasst.

### Raster und Form

- [x] Die Abstandsskala folgt dem 8-Punkt-Raster des Boards: die acht Stufen 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 stehen zur Verfügung, und `--spacing-o1…o8` erzeugen keine Regel mehr.
- [x] Das 12-Spalten-Raster mit 12px Zwischenraum steht für Seitenlayouts zur Verfügung **und ist an mindestens einer Stelle verwendet** (sonst ist es totes Inventar und nicht abnehmbar).
- [x] Die Radienskala trägt die Board-Werte 4 / 6 / 8 / 12 / 16px.
- [x] `rounded-full` kommt nur noch an einer abschließenden Liste vor: Kategorie-Chips, Schalter-Spur und -Knauf, `StatusDot`, Button-Spinner, runde Backdrops der Popover-Trigger. Jede weitere Fundstelle ist ein Fehler.
- [x] Die Standardhöhe der Schaltfläche beträgt sichtbar 32px bei einer Trefferfläche von mindestens 44 × 44 CSS-Pixeln.
- [x] Bedienelemente bleiben auf Mobilgeräten zuverlässig mit dem Finger treffbar: Trefferfläche ≥ 44 × 44 CSS-px, sichtbar ≥ 32px; auf dem heißen Pfad (Bewertungsschaltflächen, Weiter/Zurück, Kategorie-Zuordnung) am Telefon **sichtbar** ≥ 44px. Automatisiert geprüft wird, dass die Trefferflächen-Utility an allen Primitiven gesetzt ist und **nirgends** auf einem Element mit `overflow-hidden` steht; die tatsächlich gerenderten Maße werden am Gerät geprüft. (WCAG 2.2 AA verlangt 24 × 24 — die 44 × 44 sind die strengere Projektregel.)

### Grundelemente

- [x] Die wiederverwendbaren Grundelemente folgen dem Board: Schaltflächen in ihren vier Ausprägungen (primär, sekundär, unaufdringlich, deaktiviert) und drei Zuständen (normal, überfahren, gedrückt), Schalter, Kontrollkästchen, Eingabefelder in den Zuständen normal / fokussiert / fehlerhaft, Karten, Kennzeichen und Kategorie-Chips, Fortschrittsanzeige mit Prozessstufen, Hinweis- und Meldungselemente in den Ausprägungen Erfolg / Warnung / Fehler, sowie Überlagerungen (Dialoge, Popups). Je Ausprägung/Zustand existiert eine ansteuerbare Prop-Kombination und ein Test, der sie rendert; für „überfahren"/„gedrückt" gilt der Nachweis über die Existenz einer `hover:`- bzw. `active:`-Variante am Primitive — mehr ist in jsdom nicht feststellbar.
- [x] Die zwölf Symbole des Boards stehen als wiederverwendbarer Satz bereit und ersetzen die heute benutzten Sonderzeichen **an den Stellen, für die der Zwölfer-Satz ein Symbol enthält**. Die fünf benannten Lücken (`×` Schließen, `✎` Übersteuerungs-Marker, `○` „nicht gelaufen", `●●○` Qualitätsmesser, `–` unbewertet) bleiben Textzeichen bzw. bestehende Komponenten und sind als Lücke dokumentiert; sie werden ausdrücklich **nicht** durch beliebige weitere Lucide-Symbole gefüllt.

### Übergang und Dokumentation

- [x] Alle bestehenden Ansichten sind nach der Umstellung weiterhin bedienbar und lesbar, auch wenn ihre gestalterische Überarbeitung erst in Stufe 2 erfolgt. Ein sichtbar uneinheitlicher Zwischenzustand ist zulässig, ein unbenutzbarer nicht. **Unbenutzbar** heißt: in einer der geprüften Ansichten trifft mindestens eines zu — (1) Text steht auf gleich- oder nahefarbigem Grund und ist nicht lesbar; (2) ein Bedienelement hat weder erkennbaren Umriss noch erkennbare Fläche; (3) Überlappung oder Abschneiden macht eine Beschriftung oder ein Bedienelement unerreichbar; (4) bei 360px Breite muss horizontal gescrollt werden. Alles Übrige — uneinheitliche Abstände, gemischte Formsprache, unpassende Größenverhältnisse — ist ausdrücklich zulässiger Zwischenzustand und kein Abnahmehindernis.
- [x] Die Design-Dokumentation des Projekts gibt den neuen Stand wieder: die sieben Board-Abweichungen und die sechs Rücknahmen sind namentlich in `specs/architecture/0004-design-system.md` und im Skill `.claude/skills/design-system/SKILL.md` aufgeführt. Zusätzlich sind die acht Kernwerte (vier Flächen, vier Akzente) über einen Test an den Code gebunden — bewusst nur diese acht, nicht alle ~60, sonst wird jede Wertkorrektur zur Doppelpflege.
- [ ] *(offen — Abnahme durch Daniel)* Die neun manuellen Prüfpunkte sind für jede Ansicht (Anmeldung, Projektliste inkl. Leerzustand, Projekt anlegen, Projekt-Einstellungen, Projekt-Statistik, die fünf Pipeline-Schritte, Kategorie-Kuratierung, Fotoraster, Foto-Detail, Foto-Vergleich) in Telefonbreite (360px) und Desktopbreite durchgeführt und mit **Screenshots im Pull Request belegt** — ein abgehaktes Häkchen ohne Artefakt ist im Nachhinein von „nicht gemacht" nicht unterscheidbar.
- [x] Die Rücknahme der Zusage aus Story 0285 („Der Dunkelmodus bleibt erhalten", „Kontrast in beiden Farbschemata") ist ausdrücklich als bewusste Entscheidung festgehalten — nicht als stillschweigende Abweichung.

## Datenmodell-Bezug

Keiner. Die Umstellung ist rein frontendseitig; es gibt keine neue oder geänderte Entität, keine
Migration und keine Backend-Änderung. Die einzige Berührung mit einem Backend-Begriff ist die nach
`category_key` geschlüsselte Chip-Farbtabelle im Frontend (siehe ADR 0055 Punkt 6) — sie liest
einen bestehenden Schlüssel, sie verändert ihn nicht.

## Entscheidungen

Getroffen im Verfeinerungsablauf zu dieser Spec; die vollständige Begründung steht jeweils in
ADR [`0055`](../decisions/0055-dark-utility-register-fundament.md).

- **Kein heller Modus mehr.** Die App ist unabhängig von der Systemeinstellung dunkel. Das nimmt
  Spec [`0285`](./0285-organic-design-import.md) AK 6 und AK 7 ausdrücklich zurück (ADR 0055 Punkt 1).
- **Text Muted wird von `#62677A` auf `#8D92A4` aufgehellt** (Daniel entschieden). Der Board-Wert
  verfehlt WCAG-AA auf allen vier Flächen (3,48 / 3,21 / 2,82 / 2,50), trägt im Board aber echten
  Fließtext. Bekannte Einschränkung: der Abstand zu Text Sekundär `#A0A5B5` wird gering; die
  Textstufen 2 und 3 tragen ihre Unterscheidung über die Verwendung, nicht über die Wahrnehmung
  (ADR 0055 Punkt 4a).
- **Kategorie-Chips bekommen 13 eigene Farbpaare** (Daniel entschieden, gegen die Empfehlung des
  `architect`): fünf aus dem Board, acht abgeleitet, „Nicht erkannt" neutral. Das dreht die
  frontendseitige, nach `category_key` geschlüsselte Tabelle aus Spec
  [`0289`](./0289-feste-kategorien.md) für die Chip-Farben wieder auf — für Anzeigenamen bleibt sie
  abgeschafft. Ausdrückliche Teil-Rücknahme, keine stillschweigende Abweichung (ADR 0055 Punkt 6).
- **Die Farbnähe zwischen Kategorie-Chips und Bewertungsfarben ist bewusst in Kauf genommen**
  („Menschen" `#FFC107` liegt 0° vom Favorit-Amber, „Landschaft" `#00B4D8` 2° vom Info-Cyan) und
  über drei strukturelle Regeln aufgefangen: gefüllt = Bewertung / getönt = Kategorie, Radius 6px
  vs. 16px, Gegenecken-Platzierung.
- **`lucide-react` als Abhängigkeit** (Daniel entschieden, gegen die Empfehlung des `architect`),
  gekapselt in einer einzigen `components/ui/icon.tsx`. Beantwortet die in Spec 0285 ausdrücklich
  vertagte Icon-Frage. Beim Abgleich hat sich gezeigt, dass **alle zwölf Board-SVGs Lucide-Pfade
  sind** — der Figma-Export hat lediglich Bögen in kubische Béziers aufgelöst und `star`
  gegenläufig gezeichnet; es gibt damit keine Geometrie-Abweichung zu dokumentieren (ADR 0055
  Punkt 7a).
- **Trefferflächen auf dem heißen Pfad** (Bewertungsschaltflächen, Weiter/Zurück,
  Kategorie-Zuordnung): am Telefon **sichtbar** mindestens 44px, am Desktop Board-Maß 32px. Alle
  übrigen Bedienelemente überall Board-Maß mit unsichtbar aufgespannter Trefferfläche (Daniel
  entschieden). Begründung: man zielt auf das, was man sieht, und ein Fehlgriff schreibt hier eine
  falsche Bewertung.
- **Visuelle Absicherung: Sichtprüfung mit Screenshot-Belegen im PR** (Daniel entschieden). Der
  `developer` fährt die App hoch, ruft die neun Ansichten in beiden Breiten auf und legt die
  Aufnahmen bei. Keine Browser-Testebene (Playwright o.ä.) — sie wäre ADR-pflichtig, kostete
  CI-Zeit und Flakiness-Pflege, und Stufe 2 machte einen Teil der Baseline sofort hinfällig.
- **Content-Security-Policy: eigene Story, hier nur als bekannte Lücke notiert** (Daniel
  entschieden). Siehe Out of Scope.
- **Transluzente Flächen werden auf die Board-Toast-Konstruktion umgestellt** (technische
  Detailentscheidung innerhalb dieser Spec). Drei Konstruktionen im Bestand liegen außerhalb der
  ADR und außerhalb jeder Kontrastmatrix: `badge.tsx`s `suggested`-Variante (`bg-rating-*/10` +
  `text-text-h` — eine PhotoSort-eigene Erfindung, die das Board nicht kennt) sowie `alert.tsx`s
  `bg-status-failed/10` + `border-status-failed/40`. Über einer Deckkraft-Tinte ist Kontrast
  statisch nicht rechenbar, sie wären damit dauerhaft ungeprüft. Beide gehen auf die
  Toast-Konstruktion aus ADR 0055 Punkt 5 (Fläche `--elevated`, farbiger Rand, farbige
  Beschriftung) — dadurch fallen sie automatisch in die Kontrastmatrix, und `alert.tsx`/`badge.tsx`
  werden zu Board-Konstruktionen statt zu zwei Sonderfällen. Das `⚠` in `alert.tsx` steht in
  keiner der beiden Symbollisten und wird durch `info` (Warnung) bzw. `x-circle` (Fehler) ersetzt.
- **Dialog-Hintergrundklick schließt nicht** (technische Detailentscheidung). Der erste Konsument
  ist ein Dialog vor einer kostenpflichtigen Aktion; undefiniert wäre keine Option, weil es
  getestet werden muss.
- **Fokusfalle und Esc des Dialogs werden in eigenem JS implementiert**, nicht dem nativen
  `<dialog>` überlassen — jsdom implementiert weder `showModal()` noch Fokusfalle noch
  Esc-Behandlung, die Zusage wäre sonst untestbar (Teststrategie, Abschnitt „jsdom-Fallstrick").
- **`architect` konsultiert** (Schritt 1), **`ux-ui-designer` konsultiert** (Schritt 2),
  **`test-engineer` und `security-engineer` konsultiert** (Schritt 3). Keine Skip-Entscheidung.

## Architektur / Umsetzung

Die technischen Entscheidungen sind in ADR [`0055-dark-utility-register-fundament.md`](../decisions/0055-dark-utility-register-fundament.md)
festgehalten — dort auch die ausdrückliche Rücknahme von [`0285`](./0285-organic-design-import.md)
AK 6/7 (Dunkelmodus/Kontrast in beiden Schemata) und die Teil-Rücknahme von
[`0289`](./0289-feste-kategorien.md) (frontendseitige Tabelle nach `category_key` — für
Anzeigenamen bleibt sie abgeschafft, für Chip-Farben kommt sie zurück), sowie die Auflösung aller
sechs Konflikte zwischen Board-Werten und dem Kontrast-Akzeptanzkriterium.

### Gewählter Ansatz

Die Umstellung ist **kein Architekturumbau, sondern ein Wertetausch an einer vorhandenen Naht.**
Die Token-Zweiteilung des Organic-Imports — Rohwerte in `:root`, Zuordnung zu Tailwind-Utilities im
`@theme`-Block (Tailwind v4, CSS-first, kein `tailwind.config.js`) — bleibt unverändert und ist
zugleich der Migrationsmechanismus: **wo ein Board-Token dieselbe semantische Rolle hat wie ein
bestehendes, behält das bestehende Token seinen Namen und bekommt nur einen neuen Wert.**

Dadurch tragen ~175 der rund 190 Farb-Aufrufstellen in den 91 `.tsx`-Dateien die Umstellung, ohne
angefasst zu werden (`--bg`→`#0B0C10`, `--surface`→`#14161F`, `--text-h`→`#FFFFFF`,
`--text`→`#A0A5B5`, `--border`→`#2A2E3D`, `--accent`/`--accent-strong`→`#FFB000`,
`--accent-fg`→`#0B0C10`, `--accent-2`/`--accent-2-strong`→`#00E676`, `--rating-*`, `--status-*`).
Die Nacharbeit reduziert sich auf sechs abzählbare, unten namentlich aufgeführte Listen. Das ist die
Antwort auf „wie bleiben 91 tsx-Dateien nach dem Token-Tausch benutzbar, ohne Stufe 2 vorwegzunehmen".

Neu hinzu kommen die Rollen ohne heutiges Token: `--elevated` (`#1E2230`), `--overlay` (`#262B3D`),
`--text-muted` (`#8D92A4`), `--text-disabled` (`#3E4252`), `--border-control` (`#727891`), `--info`
(`#00E5FF`), `--danger-text` (`#FF5A26`) sowie 26 Kategorie-Chip-Tokens (ADR 6a). Ersatzlos
gestrichen werden die drei Organic-Tonleitern (`--neutral-*`, `--accent-*`, `--accent-2-*`, 27
Tokens — das Board kennt keine Tonleitern), die drei Schatten-Tokens samt `shadow-warm*` (der
Dunkelmodus setzt sie heute schon auf `none`, das Board arbeitet flach; Tiefe tragen die vier
Flächenstufen), `--heading`/`font-heading` (keine Display-Schrift im Board), `--spacing-o1…o8` und
die Utility `.washed`.

### Betroffene Dateien und Reihenfolge

Die Reihenfolge ist bindend — jeder Schritt setzt auf dem vorigen auf.

**1. Abhängigkeiten und Schriften.** `frontend/package.json`: `@fontsource/caprasimo` und
`@fontsource/figtree` raus, `@fontsource/inter` (400/500/600/700), `@fontsource/jetbrains-mono`
(400) und **`lucide-react`** rein — Netto **+1** Abhängigkeit. Einbindung der Schriften bleibt
self-gehostet über `@fontsource` (Offline-Anspruch der PWA, unverändert gültige Begründung aus 0285
Abweichung 1); die `woff2`-Ergänzung in `vite.config.ts`s `globPatterns` bleibt dadurch nötig.

**2. `frontend/src/index.css` — vollständiger Neuaufbau der Token-Ebene.** Der einzige Schritt mit
echtem Umfang:
- `@media (prefers-color-scheme: dark)` entfällt ersatzlos; `color-scheme: light dark` → `dark`.
- Grundfläche zusätzlich auf `html` setzen, nicht nur auf `body` (sonst bleibt der Überroll-Bereich hell).
- `:root` trägt die vier Flächen, vier Akzente, vier Textstufen, `--border`/`--border-control`,
  `--danger`/`--danger-text`, die 26 Chip-Tokens und die unverändert benannten Bestandstokens
  (Tabellen in ADR 0055 Punkt 2 und 6a).
- `@theme`: Radienskala auf das Board (`--radius-xs: 4px`, `-sm: 6px`, `-md: 8px`, `-lg: 12px`,
  `-xl: 16px` — dadurch werden die bestehenden 15 `rounded-md` und 10 `rounded-xl` automatisch
  board-konform); Typoskala auf das Board (`text-lg`→20px, `text-xl`→24px, `text-2xl`→40px,
  `text-3xl`→64px; `text-xs`/`text-sm`/`text-base` unverändert 12/14/16, sie tragen 121 der 145
  Aufrufstellen; `text-4xl` und größer entfallen). Abstände: Tailwinds Default-`--spacing` liefert
  die 8-Punkt-Skala 4/8/12/16/24/32/48/64 bereits über `p-1…p-16` — kein eigenes Token, nur
  dokumentiert. 12-Spalten-Raster mit 12px Gutter = `grid-cols-12 gap-3`, ebenfalls nur dokumentiert.
- `@layer utilities`: `.washed` entfällt; **neu zwei** Trefferflächen-Utilities, die ein
  transparentes Pseudo-Element auf mindestens 44×44px aufspannen (ADR 0055 Punkt 8).
  **Korrigiert bei der Umsetzung:** Hier stand „eine einzige Utility“. Es sind zwei geworden,
  weil die erste der vier Aufspannungsregeln des UI/UX-Abschnitts („nur auf der kurzen Achse
  aufspannen“) mit einer einzigen Utility nicht umsetzbar ist: `tap-target` spannt nur vertikal
  auf (beschriftete Bedienelemente sind breit genug), `tap-target-square` beidachsig (Symbol-
  Schaltflächen, Kontrollkästchen). Eine beidachsige Aufspannung an einer breiten Schaltfläche
  erzeugte genau die breiten unsichtbaren Flächen, die dieselbe Regel verbietet.

**3. Kein heller Rest außerhalb der CSS.** `frontend/index.html`: `<meta name="theme-color">`
(heute `#111111`) → `#0B0C10`, zusätzlich `<meta name="color-scheme" content="dark">` (verhindert
das Weißblitzen vor dem ersten Paint). `frontend/vite.config.ts`: `manifest.theme_color` (heute
`#c67139`) → `#FFB000`, `manifest.background_color` (heute `#f5ead8`) → `#0B0C10` — sonst blitzt
beim PWA-Start die alte Palette auf.

**4. `frontend/src/components/ui/icon.tsx` (neu) + `icon.test.tsx` (neu).** Die einzige Datei im
Projekt, die aus `lucide-react` importieren darf. `name`-Prop als String-Union der zwölf
Board-Namen, intern statisch auf die Lucide-Komponenten abgebildet; `size`-Prop (Default 16, Board
nutzt 14/16/18/24), Strichstärke 2 zentral gesetzt, Einfärbung über `currentColor`,
`aria-hidden="true"` + `focusable="false"` als Regelfall, optionale `title`-Prop schaltet auf
`role="img"`. Eine Datei statt direkter Imports an ~10 Stellen, weil die Aufrufstellen ihr Symbol
datengetrieben wählen (`RatingBadge`s `SYMBOLS`-Record, `CloudVisionStatusList`s `glyph`) — ein
String-Name ist dort der Eins-zu-eins-Ersatz für das heutige Sonderzeichen.

Zwingend zu beachten (ADR 0055 Punkt 7b/7d):
- Zuordnung: `star`→`Star`, `book`→`Book`, `x-circle`→**`CircleX`** (Lucide hat das Symbol zu
  `circle-x` umbenannt; `XCircle` ist der Alt-Alias — gegen die tatsächlich installierte Version
  prüfen, nicht raten), `cog`→**`Cog`** (nicht `Settings`), `image`→**`Image as ImageIcon`**
  (kollidiert sonst mit dem DOM-Global `Image`), `check`→`Check`, `info`→`Info`,
  `chevron-down`→`ChevronDown`, `search`→`Search`, `folder`→`Folder`, `camera`→`Camera`, `tag`→`Tag`.
- Nur **benannte Importe** in einem **statischen Objektliteral**. Kein `import * as icons`, kein
  dynamischer Zugriff über einen berechneten Schlüssel auf das Paket-Objekt — beides hebelt das
  Tree-Shaking aus und zöge den vollen Lucide-Satz ins Bundle.

**5. Primitive unter `frontend/src/components/ui/`** (Board-Werte in ADR 0055 bzw. der
Board-Referenz, Abschnitt 6):
- `button.tsx` — Radius 6px statt `rounded-full`, `font-heading` raus, Höhe 32px statt `h-11` plus
  Trefferflächen-Utility. Varianten-Zuordnung: `default`→Primär, `secondary`→Sekundär (Fläche
  `--overlay`, Rand `--border-control`), `ghost`→Unaufdringlich, `outline`→ auf Sekundär
  vereinheitlichen (das Board kennt keine vierte gefüllte Ausprägung), `link` unverändert.
  `disabled`→Board-Zustand „Deaktiviert". Die `compoundVariants`-Absicherung für `link` und die
  `asChild`+`disabled`-Absicherung bleiben unverändert bestehen.
- `input.tsx` — drei Board-Zustände: normal (Rand `--border-control`), fokussiert (Rand 1,5px
  `--accent`, Caret `--accent`), fehlerhaft (Rand `--danger`, Beschriftung/Meldung `--danger-text`).
- `card.tsx` — Radius 12px, Fläche `--elevated`, Rand `--border`, kein Schatten mehr.
- `badge.tsx` — Radius 6px statt `rounded-full`; alle drei `--rating-*-fg` tragen jetzt `#0B0C10`
  (Konflikt 4e). Die drei getrennten Tokens und der bestehende Regressionstest bleiben.
- `alert.tsx` — drei Ausprägungen statt nur Fehler: Erfolg/Warnung/Fehler, Fläche `--elevated`,
  farbiger 1px-Rand, Symbol 18px (`check` / `info` / `x-circle` — `info` statt des Board-`star`,
  weil `star` im Produkt das Favorit-Symbol ist, ADR 0055 Punkt 7e). Das `⚠`-Textzeichen entfällt.
- `switch.tsx` — 48×24px, Knauf 20px, vollrund (eine der wenigen verbleibenden Rundformen).
- `checkbox.tsx` — Rand `--border-control`, `accent-color` auf `--accent`.
- `progress.tsx` — Spur `--border`, Füllung `--accent`, Höhe 8px, Radius 4px statt `rounded-full`.
- `popover.tsx` — Fläche `--elevated`, Radius 8px (`rounded-md` statt `rounded-lg`), kein Schatten.
- `dialog.tsx` (**neu**) — natives `<dialog>`, keine weitere Abhängigkeit (Linie von
  `switch`/`checkbox`: „Radix nur wo natives HTML nicht reicht"). Fläche `--overlay`, Rand
  `--border`, Radius 16px, Polsterung 24px. Die Grundelemente-Liste des Boards verlangt
  Überlagerungen als Teil des Fundaments; ein Primitiv vor seinem ersten Konsumenten ist genau das,
  was ein Grundelemente-Satz ist.

**6. Zusammengesetzte Komponenten unter `frontend/src/components/`:**
- `StatusTag.tsx` — Umstellung auf die Toast-Konstruktion des Boards: Fläche `--elevated`, farbiger
  Rand, farbige Beschriftung. Die acht `--status-*-tint`/`-strong`-Tokens werden darauf umdefiniert
  statt gestrichen, ihre Aufrufstellen bleiben unverändert (ADR 0055 Punkt 5).
- `RatingBadge.tsx` — `★`/`✓`/`✕` → `star`/**`book`**/`x-circle`; Vorschlags-Präfix `⚙` → `cog`.
  **Korrigiert bei der Umsetzung:** Diese Zeile nannte ursprünglich `check` für „Album-würdig“ und
  übersetzte damit die bisherigen Zeichen eins zu eins. Maßgeblich ist `book`, wie es die
  Board-Referenz (Abschnitt 6, „Album: Badge ALBUM … + `book`-Symbol 14px“) und ADR 0055 Punkt 6c
  („eigenes Symbol `star` / `book` / `x-circle`“) übereinstimmend festlegen. Grund über die
  Board-Treue hinaus: `check` ist im Produkt bereits das Symbol der Erfolgsmeldung (`alert.tsx`);
  eine Doppelbelegung bräche „Bewertungsstufen auf einen Blick unterscheidbar“.
  Das `–` für unbewertet bleibt Text (das Board zeigt für „Neu“ gar kein Badge).
- `CloudVisionStatusList.tsx` — `⚠` → `x-circle`, `✓` → `check`; die drei `○`-Zustände bekommen den
  vorhandenen `StatusDot` (kein leerer Kreis im Zwölfer-Satz).
- `CategoryBadge.tsx` — Board-Chipform (Radius 16px, Polsterung 12/6px, Inter Semi-Bold 12px) und
  **das Farbpaar der jeweiligen Kategorie** (ADR 0055 Punkt 6). Auflösung über eine nach
  `category_key` geschlüsselte Konstante mit vollständig ausgeschriebenen Klassennamen (kein
  Template-String — Tailwind erkennt nur statische, vollständige Strings, dieselbe Regel wie in
  `badge.tsx`). Unbekannter Key → neutrales Paar (Altwerte wie `"unerkannt"`/`"landscape"`
  existieren nachweislich, siehe `categoryLabels.ts`); kein leeres Badge, kein Absturz.
- `Stepper.tsx` — Prozessstufen nach Board (erledigt/kommend `--text`, aktuelle Stufe Bold
  `--accent`, noch nicht begonnen `--text-muted`); `×` im Popover bleibt Text.
- `BrandMark.tsx` — die drei überlappenden Kreise sind Organic-Formsprache; ersetzt durch eine
  schwach gerundete Akzentfläche (Radius 8px) mit dem `camera`-Symbol in `--accent-fg`.
- `RatingButtons.tsx` — Board-Bewertungspillen (Radius 6px, Fläche `--elevated`); die
  tonspezifische `--rating-*-fg`-Kopplung bleibt. Am Telefon sichtbar ≥44px hoch (heißer Pfad).
- `CategoryOverrideMarker.tsx` und `QualityMeter.tsx` bleiben bei ihren Zeichen (`✎` bzw. `●●○`) —
  dokumentierte Lücken des Zwölfer-Satzes bzw. bewusst ein Messglyph. Diese Lücken werden
  ausdrücklich **nicht** mit beliebigen weiteren Lucide-Symbolen gefüllt: der Satz des Boards ist
  zwölf Symbole groß, ihn stillschweigend zu erweitern wäre eine Gestaltungsentscheidung ohne Vorlage.

**7. Die sechs benannten Nacharbeitslisten** (kein Test erzwingt sie — eine unbekannte
Tailwind-Utility ist kein Buildfehler, sondern erzeugt still keine Regel):
- Tonleitern, 6 Zeilen: `pages/ProjectListPage.tsx` (Z. 54, 55, 66, 93), `components/Stepper.tsx` (Z. 160, 164).
- `shadow-warm*`, 4 Stellen: `ui/card.tsx`, `ui/button.tsx`, `ui/popover.tsx`, `ui/switch.tsx`
  (+ `ProjectListPage.tsx` Z. 93 aus derselben Liste).
- `font-heading`, 2 Stellen: `ui/button.tsx`, `pages/ProjectListPage.tsx` Z. 96.
- `rounded-full`, 30 Stellen in 16 Dateien — durchsehen: bleiben darf es nur bei Schalter-Spur/Knauf,
  `StatusDot`, Button-Spinner und den runden Backdrops der Popover-Trigger; alles andere geht auf
  `rounded-sm` (6px) bzw. `rounded-xl` (16px, Kategorie-Chips).
- `text-2xl`, 11 Stellen — echte Seitenüberschriften bleiben (jetzt 40px), Abschnittsüberschriften
  auf `text-xl` (24px, ihre heutige Größe). Die eine `text-4xl`-Stelle geht auf `text-3xl`.
- Vollständigkeits-Scan: jedes in `index.css` deklarierte Token gegen alle `.tsx`/`.ts` prüfen,
  damit keine verwaiste Referenz übrig bleibt.

**8. Dokumentation im selben PR:** `specs/architecture/0004-design-system.md` und
`.claude/skills/design-system/SKILL.md` vollständig auf den neuen Stand, inklusive der
**ausdrücklichen Rücknahmen** (kein Hellmodus; „Akzent und Bewertungsfarben getrennt halten";
„44×44px" als Größen- statt Trefferflächenregel; „volle Pillen für kleine Bedienelemente";
„Schatten für Karten, Rahmen im Dark Mode"; „Kategorie-Chips immer neutral"), der sieben
dokumentierten Board-Abweichungen, der bekannten Einschränkung aus ADR 4a (Textstufe 2 und 3 sind
nebeneinander nur schwach unterscheidbar und tragen ihre Unterscheidung über die Verwendung, nicht
über die Wahrnehmung) und der drei Regeln, die die Farbnähe zwischen Kategorie-Chips und
Bewertungsfarben auffangen (gefüllt = Bewertung / getönt = Kategorie; Radius 6px vs. 16px;
Gegenecken-Platzierung). `docs/architecture.md`, `docs/setup.md` und das Root-`README.md` sind
nicht betroffen — keine der drei beschreibt Design-System, Schriften oder Farben, und
`lucide-react` erzeugt keinen neuen Setup-Schritt (`npm ci` im `frontend/Dockerfile`, `npm install`
lokal, keine Systemabhängigkeit).

### Bewusst getragene Kollision

Die Kategorie-Chips „Menschen" (`#FFC107`, 0° vom Favorit-Amber) und „Landschaft" (`#00B4D8`, 2°
vom Info-Cyan) liegen farblich praktisch auf zwei der vier Board-Akzente. Das ist mit der
Entscheidung für farbige Chips bewusst in Kauf genommen und über die drei oben genannten Regeln
strukturell aufgefangen. Das Akzeptanzkriterium „Die drei Bewertungszustände bleiben auch ohne
Farbwahrnehmung unterscheidbar" bleibt davon unberührt und ist erfüllt: es ist ein achromatisches
Kriterium, die Kollision ein chromatisches Problem — Textbadge, eigenes Symbol, Durchstreichung und
das dreibuchstabige Chip-Kürzel bleiben in Graustufen vollständig erhalten und verschieden.

### Bewusst nicht Teil dieser Stufe

Bewertungsleiste, Navigationselement/Sidebar und die Anordnung der Ansichten stehen zwar im Board,
aber nicht in der Grundelemente-Liste dieser Story — sie gehören zu Stufe 2 (Issue #321).

## UI/UX

Dieser Abschnitt beschreibt ausschließlich das **Fundament** (Stufe 1): welche Zustände die
Grundelemente abdecken müssen, was Barrierefreiheit über die bereits in ADR 0055 aufgelöste
Kontrastrechnung hinaus verlangt, wie die Trefferflächen auf dem Telefon geregelt sind, wo die
Grenze des zulässigen Zwischenzustands liegt und wo Dichte hilft bzw. kippt. Die gestalterische
Überarbeitung der einzelnen Ansichten ist Stufe 2 (Issue #321) und hier ausdrücklich kein Thema —
kein Vorschlag in diesem Abschnitt ordnet eine Seite neu an.

Verbindliche Werte stehen in ADR [`0055`](../decisions/0055-dark-utility-register-fundament.md)
und in der Board-Referenz V1.2; hier steht nur, was daraus für die Bedienung folgt.

### 1. Grundelemente und ihre Zustände

Für jedes Element: was der Nutzer in welchem Zustand sieht. „Board" = Wert steht in der
Board-Referenz; „ergänzt" = das Board zeigt diesen Zustand nicht, wir brauchen ihn trotzdem.

**Schaltflächen** (4 Ausprägungen × 3 Zustände, Board)
- Primär: gefüllte Akzentfläche mit dunkler Tinte — sofort als die eine Hauptaktion lesbar.
  Überfahren/gedrückt nur über Deckkraft (85 % / 70 %), die Fläche bleibt dieselbe.
- Sekundär: dunkle Fläche mit sichtbarem Umriss in `--border-control`; der Umriss ist hier das
  Identifikationsmerkmal, nicht die Fläche (in einem Dialog ist die Fläche identisch zum Grund).
- Unaufdringlich: nur Beschriftung; erst beim Überfahren/Drücken entsteht eine Fläche.
- Deaktiviert: gedämpfte Fläche, Umriss in `--border`, Schrift in `--text-disabled`, kein Zeiger.
- **Ergänzt — „gedrückt" ist am Telefon der einzige Zustand, den es gibt.** Tailwind v4 bindet
  `hover:` von sich aus an `@media (hover: hover)`; auf dem Telefon fällt der Überfahren-Zustand
  also ersatzlos weg. Im heutigen Code gibt es **27 `hover:`-Stellen und null `active:`-Stellen** —
  das heißt, ein Fingertipp erzeugt dort aktuell gar keine sichtbare Rückmeldung. Jede
  Schaltflächen-Ausprägung bekommt deshalb den Board-Zustand „gedrückt" verbindlich als
  `active:`-Zustand, nicht nur als Hover-Variante.
- **Ergänzt — Ladezustand:** das bestehende Busy-Muster (erzwungene Deaktivierung + Inline-Spinner,
  Beschriftungswechsel beim Aufrufer) bleibt unverändert gültig; der Spinner erbt `currentColor`
  und damit die jeweilige Ausprägungsfarbe.

**Schalter** (Board liefert nur die Geometrie 48 × 24 px, Knauf 20 px — Farben ergänzt)
- Aus: Spur `--overlay`, Umriss `--border-control`, Knauf links in Sekundärtextfarbe.
- Ein: Spur `--accent`, Knauf rechts in `--accent-fg` (dunkel auf Amber) — „gefüllt = gesetzt",
  dieselbe Logik wie beim Bewertungs-Badge.
- Deaktiviert (ergänzt): Spur `--surface`, Umriss `--border`, Knauf `--text-disabled`.
- Der Zustand wird zusätzlich über die **Knaufposition** getragen, nicht nur über die Farbe.

**Kontrollkästchen** (das Board zeigt dieses Element **überhaupt nicht** — vollständig abgeleitet)
Abgeleitet aus dem Eingabefeld, damit es als dessen kleiner Bruder liest: 18 px Kasten, Radius
4 px, Umriss `--border-control`, Fläche `--surface`.
- Gesetzt: Fläche `--accent`, Haken (`check`, 14 px) in `--accent-fg`.
- Deaktiviert: Umriss `--border`, Haken in `--text-disabled`, keine Akzentfläche.
- Ein unbestimmter Zustand wird nicht eingeführt — es gibt keinen Anwendungsfall.
- Die Beschriftung bleibt Teil des Bedienelements (klickbares `<label>`); die Trefferfläche ist
  die ganze Zeile, nicht der 18-px-Kasten.

**Eingabefelder** (Board: normal / fokussiert / fehlerhaft)
- Normal: Fläche `--surface`, 1 px Umriss `--border-control`, Text Sekundärstufe.
- Fokussiert: 1,5 px Umriss in `--accent`, Text Primärstufe, Textmarke in `--accent`.
- Fehlerhaft: 1 px Umriss `--danger`, Beschriftung und Meldung in `--danger-text` (nicht in
  `--danger` — als Fließtext hält der Board-Ton auf erhöhten Flächen kein AA).
- **Ergänzt:** Platzhaltertext in `--text-muted` (nie in Text-Disabled — Platzhalter ist Inhalt),
  deaktiviertes Feld mit `--border`-Umriss und `--text-disabled`, sowie der Fall
  **fokussiert + fehlerhaft**: Akzent-Fokus und roter Fehlerumriss dürfen sich nicht gegenseitig
  auslöschen. Regel: der Fehlerumriss bleibt am Feld, die Fokusdarstellung liegt als abgesetzte
  Kontur außen herum (siehe Abschnitt 2) — beide sind gleichzeitig sichtbar.
- Das bestehende Fehler-Muster bleibt unverändert: Banner am Formularanfang mit unverändertem
  `detail`-Text, zusätzlich `aria-invalid` am eindeutig zuordenbaren Feld, Ausnahme Anmeldung
  (dort bewusst nur der Banner).

**Karten** (Board: Neu / Favorit / Album / Aussortiert / Ausgewählt)
- Grundform: Fläche `--elevated`, 1 px `--border`, Radius 12 px, flach (keine Schatten mehr).
- Bewertet: Textbadge + eigenes Symbol in der Zustandsfarbe, dunkle Tinte auf allen vier Badges.
- Aussortiert: Dateiname durchgestrichen in `--text-muted`, **gedämpft wird nur die Bildfläche**,
  nicht die ganze Karte — Badge, Symbol und Dateiname bleiben bei vollem Kontrast lesbar.
- Ausgewählt: 2 px Akzentkante direkt am Kartenrand (ohne Abstand) plus Akzent-Dateiname.
- **Ergänzt — Ladezustand:** Platzhalterkarte (Skeleton) in `--elevated` auf dem Seitengrund,
  dezenter Puls, `motion-reduce` respektiert; kein Lauflicht.
- **Ergänzt — Fehlerzustand des Bildes:** schlägt das Vorschaubild fehl, bleibt die Karte mit
  ihrer Struktur stehen und die Bildfläche zeigt ein `image`-Symbol in `--text-muted`, statt zu
  einer leeren Fläche zu kollabieren.

**Kennzeichen und Kategorie-Chips**
- Bewertungs-Badge: **voll gefüllte** Fläche, dunkle Tinte, Radius 6 px, Textkürzel + Symbol.
- Kategorie-Chip: **getönte** Fläche mit heller, bunter Schrift, Radius 16 px, dreibuchstabiges
  Kürzel, vollständiger Name als `aria-label`/`title`; „Nicht erkannt" neutral.
- Die drei Gegenmaßnahmen zur Farbnähe (gefüllt ↔ getönt, 6 px ↔ 16 px, Gegenecken-Platzierung)
  sind Bedienmerkmale, keine Kosmetik — sie sind bei der Sichtprüfung ausdrücklich zu prüfen:
  auf einer Kachel mit gleichzeitigem Favorit-Badge und Kategorie-Chip „Menschen" muss ohne
  Nachdenken erkennbar bleiben, welches von beiden die Bewertung ist.
- **Ergänzt:** unbewertetes Badge (Board zeigt für „Neu" gar keines) bleibt als neutrales „–"
  erhalten, weil das Raster sonst zwischen „nicht bewertet" und „Badge noch nicht geladen" nicht
  unterscheidbar wäre.

**Fortschrittsanzeige mit Prozessstufen**
- Balken: Spur `--border`, Füllung `--accent`, 8 px hoch; Kopfzeile mit Beschriftung und
  Prozentwert in dicktengleicher Schrift.
- Stufenzeile: erledigt/kommend in Sekundärtext, **aktuelle Stufe fett in `--accent`**, noch nicht
  begonnen in `--text-muted`. Die aktuelle Stufe wird über Schnitt **und** Farbe getragen, nicht
  über Farbe allein.
- **Ergänzt — indeterminierter Zustand:** das Board kennt ihn nicht, das Produkt braucht ihn
  (kurz nach dem Auslösen ist die Gesamtzahl noch 0). Darstellung: durchlaufender Akzentabschnitt
  auf der Spur, Prozentwert entfällt und wird durch „läuft…" ersetzt; bei `prefers-reduced-motion`
  eine statische, halbdeckende Füllung ohne Bewegung.
- Die gedrosselte `aria-live`-Ansage (10-%-Schritte) bleibt unverändert.

**Hinweis- und Meldungselemente** (Erfolg / Warnung / Fehler)
- Board-Konstruktion wird übernommen: Fläche `--elevated`, 1 px farbiger Umriss, Symbol 18 px,
  Titel in Primärtext, Beitext in Sekundärtext. Erfolg `check`, Warnung `info` (nicht `star` —
  `star` ist im Produkt das Favorit-Symbol), Fehler `x-circle` mit Meldungstext in `--danger-text`.
- **Bewusste Abgrenzung:** übernommen wird die **Optik** des Board-Toasts, nicht sein Verhalten.
  Meldungen bleiben inline und kontextnah (Banner über der betroffenen Ansicht, mit „Erneut
  versuchen", wo eine Wiederholung sinnvoll ist). Ein schwebendes, selbst verschwindendes
  Toast-System wäre neues Verhalten und damit eine funktionale Änderung, die diese Story
  ausschließt. Es bleibt bei der bestehenden `Alert`-Komponente, neu eingekleidet.
- **Ergänzt:** die Meldung trägt ihre Bedeutung nie allein über die Umrissfarbe — Symbol und
  Titeltext sind Pflicht, `role="alert"` bleibt.

**Überlagerungen** (Dialog, Popover)
- Dialog: Fläche `--overlay`, Radius 16 px, 24 px Polsterung, Titelzeile mit Symbol,
  Schaltflächenzeile rechtsbündig. Verdunkelter Hintergrund über `::backdrop`.
- Popover (existiert bereits): rückt von `--surface` auf `--elevated`, damit es als aufgesetzte
  Ebene liest und nicht als weitere Karte.
- **Ergänzt — alles Verhaltensrelevante** (das Board zeigt nur ein Standbild), siehe Abschnitt 2.

**Ergänzte Zustände, die das Board an keiner Stelle zeigt und die trotzdem projektweit gelten**
1. **Fokus per Tastatur** — kommt im Board überhaupt nicht vor (Abschnitt 2).
2. **Leerer Zustand** — bestehendes Muster bleibt: kurzer erklärender Text in Sekundärtext plus
   Handlungsoption, optional ein Symbol aus dem Zwölfer-Satz (`image`/`folder`/`search`); kein
   leeres Nichts, kein Fehler-Styling. Text bewusst **nicht** in `--text-muted`: ein Leerzustand
   ist die Hauptaussage der Seite, keine Metadatenzeile.
3. **Ladezustand** — Platzhalter statt Vollbild-Spinner, wo Inhalte flächig eintrudeln; dezenter
   Inline-Indikator, wo nur ein Ausschnitt nachlädt. Unverändert gültig.
4. **Deaktivierte Zustände** von Eingabefeld, Kontrollkästchen und Schalter (Board zeigt sie nur
   für die Schaltfläche).
5. **Gedrückt-Zustand auf Touch** (siehe oben — heute null Aufrufstellen).

### 2. Barrierefreiheit über die Kontrastrechnung hinaus

**Fokus-Sichtbarkeit.** Trägt auf dem neuen Grund — aber nicht unverändert:
- Der Akzent erreicht als Kontur auf allen vier Flächenstufen 7,67–10,67:1, also weit über den
  geforderten 3:1. Die Farbe selbst ist unproblematisch.
- **Problem 1: Der Akzent ist jetzt gleichzeitig die Auswahl-/Favorit-/Aktiv-Farbe.** Eine
  Akzentkante bedeutet auf dem Board an vier Stellen „ausgewählt" (Karte), „aktiv" (Navigation),
  „fokussiert" (Eingabefeld), „Favorit" (Badge). Ohne Trennung ist ein fokussiertes Element von
  einem ausgewählten nicht unterscheidbar. **Regel:** Auswahl/Aktiv ist immer eine durchgezogene
  Kante **am Element selbst** (ohne Abstand), Fokus immer eine **abgesetzte Kontur mit 2 px Luft**.
  Wo beides gleichzeitig gilt, liest man zwei Linien mit dunklem Spalt dazwischen. Der Fokus trägt
  damit zusätzlich zur Farbe eine Formaussage.
- **Problem 2: Akzentkontur auf der Akzentfläche.** Beim primären Button wäre ein Akzentring auf
  Akzentfüllung unsichtbar. Der 2-px-Versatz löst das, **wenn** der Versatzbereich den
  tatsächlichen Untergrund durchscheinen lässt. Die heutigen Primitive setzen stattdessen
  `focus-visible:ring-offset-bg`, also eine **hart auf den Seitengrund verdrahtete** Spaltfarbe —
  auf `--elevated` (Karte) und `--overlay` (Dialog) ist das der falsche Ton und erzeugt einen
  dunklen Kranz. **Entscheidung:** eine einzige globale `:focus-visible`-Regel (2 px `--accent`,
  2 px Versatz, transparent) ist die alleinige Fokusdarstellung; die hartkodierten
  Ring-Versatz-Kombinationen in den Primitiven entfallen. Das ist zugleich eine Vereinfachung,
  kein Zusatzaufwand.
- **Problem 3: Dichte frisst den Versatz.** Bei 4-px-Abständen läuft die abgesetzte Kontur in das
  Nachbarelement. Zwischen fokussierbaren Elementen ist der kleinste zulässige Abstand deshalb
  8 px, nicht 4 px (4 px bleibt für nicht-interaktive Innenabstände).

**Tastaturbedienbarkeit des neuen `dialog.tsx`.** Es gibt heute keinen Dialog im Produkt; das
Element entsteht neu und muss von Anfang an vollständig sein. Umgesetzt über das native
`<dialog>` mit `showModal()` — dieselbe Linie wie bei Schalter und Kontrollkästchen („Radix nur
dort, wo natives HTML nicht reicht"), und es bringt Fokusfalle, Esc-Schließen und das
Inertisieren des Hintergrunds mit, statt sie nachzubauen. Verbindlich:
- Beim Öffnen liegt der Fokus auf der **am wenigsten eingreifenden** Schaltfläche (Abbrechen),
  nie auf einer bestätigenden oder löschenden Aktion.
- Der Fokus bleibt im Dialog und kehrt beim Schließen zum auslösenden Element zurück.
- Esc schließt; ein Klick auf den verdunkelten Hintergrund schließt **nicht**, wenn im Dialog
  etwas eingegeben wurde (versehentliches Verwerfen).
- Titelzeile über `aria-labelledby` verknüpft, erklärender Text über `aria-describedby`.
- Der Hintergrund scrollt nicht mit.
- Keine Öffnungs-/Schließanimation — es gibt keine im Board, und für eine Anwendung, in der
  Dialoge während schneller Arbeit auftauchen, ist Sofortigkeit das bessere Verhalten.

**`prefers-reduced-motion`.** Heute an allen drei animierten Stellen (Puls-Skeleton, Spinner,
laufender Status-Punkt) über `motion-reduce:animate-none` respektiert — bleibt so. Neu hinzu kommt
der indeterminierte Fortschrittsbalken (siehe oben). **Regel für das Fundament:** die Umstellung
führt keine neue Bewegung ein; zulässig sind ausschließlich Farb- und Deckkraftübergänge bis
150 ms, nie Bewegung von Layout oder Position. Der Grund ist nicht nur Barrierefreiheit, sondern
das Designprinzip: nichts, was das zügige Durchsehen vieler Fotos optisch bremst.

**Bleiben die drei Bewertungszustände in Graustufen unterscheidbar?** Als **Flächen allein: nein**,
und das ist wichtiger als es in der ADR steht. Nachgerechnet in Graustufen-Luminanz:
Favorit `#FFB000` ≈ 0,48, Album-würdig `#00E676` ≈ 0,54, Aussortiert `#FF3D00` ≈ 0,23. Favorit und
Album-würdig liegen damit bei 1,10:1 zueinander — als reine Farbflächen praktisch identisch hell;
nur Aussortiert hebt sich ab (rund 1,9:1 gegen beide). Das Akzeptanzkriterium ist **trotzdem
erfüllt**, aber ausschließlich über die Mehrfachcodierung: Textbadge (FAVORIT / ALBUM /
AUSGESONDERT), eigenes Symbol (`star` / `book` / `x-circle`) und beim Aussortierten zusätzlich
Durchstreichung und gedämpfte Bildfläche. **Daraus folgt eine harte Regel:** kein Bewertungszustand
darf irgendwo allein durch seine Farbfläche dargestellt werden — insbesondere nicht als farbiger
Punkt, Rahmen oder Balkensegment ohne begleitendes Symbol oder Text. Das ist bei der Sichtprüfung
mit einem Graustufenfilter zu prüfen, nicht nach Augenmaß.

Zwei Stellen erfüllen das heute nur mit Hilfe des danebenstehenden Textes und sind als **bekannte
Lücke** zu führen (Behebung in Stufe 2, nicht hier): `StatusDot` (laufend/erfolgreich/fehlgeschlagen
als reiner Farbpunkt — der Punkt ist `aria-hidden`, die Aussage steht als Text daneben, in
Graustufen sind laufend und erfolgreich aber nahezu gleich) und `QualityMeter` (Punktglyph). Beide
sind bewusst begleitend, nicht alleintragend; die Regel oben verbietet, dass in Stufe 1 weitere
solche Stellen entstehen.

**Unverändert gültig:** semantisches HTML statt klickbarer `div`s, `aria-label` an
symbolgetriebenen Bedienelementen, `autocomplete` an den Anmeldefeldern, kein systematisches
Screenreader-Testing. Die neue `icon.tsx` liefert Symbole standardmäßig `aria-hidden` — ein Symbol
ersetzt nie ein Label, es begleitet es.

### 3. Trefferflächen auf Mobilgeräten

**Entschieden (Stakeholder):** Bedienelemente auf dem **heißen Pfad** — die während des Bewertens
wiederholt und schnell getroffen werden (Bewertungsschaltflächen, Weiter/Zurück,
Kategorie-Zuordnung) — sind am Telefon **sichtbar** mindestens 44 px hoch, am Desktop gilt das
Board-Maß 32 px. Alle übrigen Bedienelemente folgen überall dem Board-Maß und tragen die 44 px
unsichtbar über die Aufspannung. Begründung: man zielt auf das, was man sieht, und ein Fehlgriff
schreibt hier eine falsche Bewertung, kein bloßes Ärgernis.

Die Aufspannung über ein transparentes Pseudo-Element auf 44 × 44 px erfüllt beide Anforderungen,
statt eine gegen die andere auszuspielen. Sie **reicht aber nicht für sich allein**; ohne die
folgenden vier Regeln erzeugt sie neue, schlechter auffindbare Fehler als die, die sie behebt.
Alle vier sind im Review prüfbar:

1. **Nur auf der kurzen Achse aufspannen.** Eine Schaltfläche mit Beschriftung ist 32 px hoch,
   aber breit genug — dort wird nur vertikal aufgespannt. Beidachsig aufgespannt wird nur, was
   tatsächlich in beiden Achsen zu klein ist (Symbol-Schaltflächen, Kontrollkästchen, Schließen).
   Sonst entstehen breite unsichtbare Flächen, die Nachbarklicks schlucken.
2. **Mindestabstand 12 px zwischen aufgespannten Bedienelementen.** Die Aufspannung ragt 6 px pro
   Seite über das Sichtbare hinaus; bei 8 px Abstand (heute z.B. in der Bewertungsleiste) und erst
   recht bei 4 px überlappen die Trefferflächen benachbarter Elemente. In der Überlappung gewinnt
   das im Stapel obenliegende Element — ein Tipp nahe der Kante löst dann sichtbar etwas anderes
   aus als beabsichtigt, und das ist bei Bewertungsschaltflächen ein **falsch gesetzter
   Datenwert**, nicht bloß ein Schönheitsfehler. Wo 12 px nicht möglich sind, wird der Abstand
   erhöht — nicht die Aufspannung heimlich weggelassen.
3. **Zeilenweise Listen werden nicht aufgespannt.** In Listen und Tabellen (Ordner-Browser,
   Projektliste, Kategorie-Kuratierung) grenzen die Zeilen ohne Zwischenraum aneinander; eine
   Aufspannung würde jede Zeile 6 px in ihre Nachbarn schieben und Tipps nahe der Zeilengrenze
   auf den falschen Eintrag lenken. Dort ist die **Zeile selbst** die Trefferfläche und bleibt
   mindestens 44 px hoch. Das kostet kaum Dichte, weil Listenzeilen ohnehin von ihrem Inhalt
   bestimmt werden.
4. **Aufspannung darf nicht abgeschnitten werden.** Ein Elternelement mit `overflow: hidden`
   (Fotokacheln, Karten mit beschnittener Bildfläche) beschneidet das Pseudo-Element still — die
   Trefferfläche ist dann wieder 32 px, ohne dass irgendetwas sichtbar kaputt wäre und ohne dass
   ein Test es fände. Jede Aufspannung innerhalb eines beschneidenden Containers ist unzulässig;
   dort wird das Element sichtbar groß genug gemacht.

### 4. Informationsdichte

Dichte ist erklärtes Ziel und für diese Anwendung richtig — aber nicht gleichmäßig über alles.
Die tragfähige Trennung verläuft zwischen **Anzeige** und **Bedienung auf dem heißen Pfad**:

**Wo Dichte hilft:**
- Fotoraster und Kuratierungsansicht: mehr Kacheln je Bildschirm heißt weniger Scrollen je
  Sichtungsdurchgang — der unmittelbarste Gewinn der ganzen Umstellung.
- Metadaten, Kennzeichen, Kategorie-Chips, Tabellen- und Listenzeilen, Statistikwerte: hier
  zahlen die kompakteren Board-Maße direkt auf „mehr im Blick" ein.
- Der Wegfall der Schatten und der vollrunden Pillen: flache Flächen mit schwacher Rundung lassen
  sich enger stapeln, ohne unruhig zu wirken.
- Die dicktengleiche Schrift für Zahlen: gleiche Ziffernbreite macht untereinander stehende Werte
  vergleichbar, ohne zusätzlichen Abstand zu brauchen.

**Wo Dichte kippt:**
- **Bedienelemente auf dem heißen Pfad:** Bewerten ist eine schnelle, wiederholte,
  datenverändernde Handlung. Dichte spart hier Millimeter und kostet Treffsicherheit — deshalb
  die Entscheidung in Abschnitt 3.
- **Am Telefon generell:** die 12-px-Abstandsregel aus Abschnitt 3 ist die harte Untergrenze; die
  8-Punkt-Skala darf nach unten nicht ausgereizt werden, nur weil sie eine 4er-Stufe hat. 4 px
  ist eine Stufe für Innenabstände, nicht für Abstände zwischen Bedienelementen.
- **Längere Texte:** die Board-Größen 20/24 px machen Fließtext größer, nicht kleiner. Dichte
  entsteht hier über weniger Weißraum, nicht über kleinere Schrift. Kein Text unter 12 px, und
  12 px nur für Beschriftungen in Versalien, nicht für Sätze.
- **Zwei Textstufen sind nur schwach unterscheidbar** (Sekundär `#A0A5B5` vs. Muted `#8D92A4`,
  ADR 0055/4a). In einer dichten Ansicht bedeutet das: Hierarchie darf nicht über diese beiden
  Stufen allein aufgebaut werden — Abstand, Schnitt und Reihenfolge müssen sie tragen.
- **Sicherheitskritische und schwer rückgängig zu machende Aktionen** (Aussortieren, Löschen)
  dürfen durch die Verdichtung nicht näher an ihre harmlosen Nachbarn rücken, als die
  12-px-Regel erlaubt — eher weiter weg.

### 5. Der zulässige Zwischenzustand — Abnahmekriterien

Das Akzeptanzkriterium erlaubt einen sichtbar uneinheitlichen, aber keinen unbenutzbaren
Zwischenzustand. Hier die Grenze, prüfbar formuliert.

**Ausdrücklich zulässig (nicht als Fehler melden):**
- Gemischte Dichten und Größen nebeneinander (eine 44 px hohe Schaltfläche neben einer 32 px hohen).
- Anordnung, Reihenfolge und Abstände im Organic-Stand; Layouts, die nicht dem 12-Spalten-Raster
  folgen.
- Überschriften, die nach der Größenumstellung optisch zu groß oder zu klein für ihre Stelle wirken.
- Gemischte Radien, uneinheitliche Kartenzuschnitte, Weißraum, der jetzt zu großzügig wirkt.
- Textsonderzeichen an Stellen, für die der Zwölfer-Symbolsatz nichts hergibt (Schließen-Kreuz,
  Übersteuerungs-Marker, Qualitäts-Punkte) — das ist dokumentierte Absicht, keine Lücke.

**Nicht zulässig — das ist die Benutzbarkeitsgrenze.** Jede Ansicht wird einmal manuell geöffnet
(Anmeldung, Projektliste inkl. Leerzustand, Projekt anlegen, Projekt-Einstellungen,
Projekt-Statistik, die fünf Pipeline-Schritte Scan/Ausschuss/Gate/Kriterien/Kuratierung,
Kategorie-Kuratierung, Fotoraster, Foto-Detail, Foto-Vergleich), jeweils in Telefonbreite (360 px)
und in Desktopbreite, und gegen diese neun Punkte geprüft:

1. **Nichts ist unsichtbar geworden.** Kein Element steht ohne Fläche da, wo eine Fläche gemeint
   war. Das ist die wahrscheinlichste Fehlerart dieser Umstellung: eine gestrichene
   Utility-Klasse erzeugt in Tailwind **keinen Buildfehler**, sondern still gar keine Regel — die
   Fläche verschwindet, der Text steht auf dem Seitengrund. Betrifft insbesondere die
   Aufrufstellen der gestrichenen Tonleitern, Schatten und der Display-Schrift.
2. **Jeder Text ist lesbar.** Kein Text und kein bedeutungstragendes Symbol unter 4,5:1 gegen die
   Fläche, auf der es *tatsächlich* steht (nicht gegen die, für die das Token gedacht war).
   Besonders zu prüfen: Text, der jetzt auf `--elevated` oder `--overlay` landet statt auf `--bg`.
3. **Jedes Bedienelement ist als solches erkennbar.** Entweder gefüllte Fläche oder Umriss mit
   mindestens 3:1. Ein sekundärer Button, dessen Umriss verschwunden ist, ist auf dem dunklen
   Grund ein unsichtbarer Button — der häufigste Weg, wie eine Ansicht unbenutzbar wird, ohne
   kaputt auszusehen.
4. **Jedes Bedienelement ist erreichbar und auslösbar** — per Tastatur mit sichtbarem Fokus
   (Tab-Durchlauf einmal komplett), per Finger mit den Regeln aus Abschnitt 3.
5. **Nichts überlappt, nichts wird abgeschnitten.** Bei 360 px Breite: keine abgeschnittenen
   Beschriftungen, keine über den Rand laufenden Überschriften (die 40/64-px-Stufen sind der
   Risikopunkt), keine übereinanderliegenden Elemente, kein horizontales Scrollen der Seite.
6. **Zustände bleiben unterscheidbar.** Die drei Bewertungszustände (auch im Graustufenfilter,
   siehe Abschnitt 2), die vier Prozessstatus, aktiv/inaktiv, ausgewählt/fokussiert,
   deaktiviert/normal. Nirgends dürfen zwei zuvor unterscheidbare Zustände gleich aussehen.
7. **Kein Element sieht deaktiviert aus, ohne es zu sein** (und umgekehrt). `--text-disabled`
   ausschließlich auf tatsächlich deaktivierten Elementen — nirgends auf Inhaltstext.
8. **Fehler, Leerzustände und Ladezustände sind noch da und noch verständlich.** Formularfehler
   werden angezeigt und dem Feld zugeordnet; Leerzustände zeigen Text plus Handlungsoption;
   Ladezustände blockieren nicht die ganze Seite.
9. **Fotos werden nicht verfälscht.** Keine Filterung, Entsättigung oder Aufhellung auf
   Bewertungs- und Vergleichsbildern; die einzige zulässige Dämpfung ist die Bildfläche der
   aussortierten Karte.

**Merksatz für die Abnahme:** uneinheitlich heißt „sieht nach Baustelle aus"; unbenutzbar heißt
„ich sehe es nicht, ich treffe es nicht, ich verstehe nicht, in welchem Zustand es ist".

Diese Prüfung ist ausdrücklich **manuell**. Die Testsuite selektiert bewusst über Rollen,
`aria-label` und `data-*`-Attribute statt über CSS-Klassen; eine verschwundene Fläche, ein
unsichtbarer Umriss oder ein Umbruch bei 360 px wird von einem grünen CI-Lauf nicht gefunden.

### 6. Bezug zum Design-System

Das Design-System-Dokument (`specs/architecture/0004-design-system.md`) und der Skill
`.claude/skills/design-system/SKILL.md` werden im Umsetzungsschritt vollständig auf den neuen Stand
gezogen — beide gemeinsam im selben Schritt, damit die Kurzreferenz nicht driftet. Aus diesem
Abschnitt gehen dort verbindlich ein:

- die Fokus-Regel (eine globale abgesetzte Kontur; Auswahl anliegend, Fokus abgesetzt; keine
  hartkodierte Ring-Versatzfarbe),
- die vier Trefferflächen-Regeln (kurze Achse, 12 px Mindestabstand, Listen ohne Aufspannung,
  keine Aufspannung in beschneidenden Containern) samt der Entscheidung „heißer Pfad am Telefon
  sichtbar ≥ 44 px",
- die Regel „kein Bewertungszustand allein über die Farbfläche" samt der Graustufen-Nähe von
  Favorit und Album-würdig,
- die Trennung Anzeige-Dichte vs. Bedienelemente auf dem heißen Pfad,
- „gedrückt" als Pflichtzustand jedes Bedienelements (Touch hat keinen Hover),
- die abgeleiteten Werte für Kontrollkästchen und Schalter, die das Board nicht liefert,
- die Abgrenzung „Toast-Optik, kein Toast-Verhalten",
- die Dialog-Regeln (natives `<dialog>`, Erstfokus auf der harmlosesten Aktion, Esc, Fokusrückgabe),
- als **bekannte Lücken**: schwacher Abstand zwischen Textstufe 2 und 3, `StatusDot` und
  `QualityMeter` ohne achromatische Eigenunterscheidung, Ansichten im Organic-Aufbau bis Stufe 2.

Zurückgenommen werden dort ausdrücklich (nicht stillschweigend): „44 × 44 px" als Größen- statt
Trefferflächenregel, „volle Pillen für kleine Bedienelemente", „Schatten für Karten / Rahmen im
Dunkelmodus", „Akzent und Bewertungsfarben getrennt halten", „Kategorie-Chips immer neutral" und
der helle Modus.

## Teststrategie

Die bestehenden 538 Frontend-Tests selektieren konventionsgemäß über Rollen, `aria-*` und
semantische `data-*` und sind gegenüber einer reinen Umgestaltung **blind**. Diese Konvention
bleibt unangetastet — Komponententests bekommen **keine** CSS-Assertions, sonst überleben sie
Stufe 2 (#321) nicht. Stattdessen entsteht eine eigene, klar benannte Testebene für den
Design-Vertrag.

Zur Einordnung: Von den 538 Tests brechen durch die Umstellung **fünf Assertions in drei Dateien**
(`switch.test.tsx:82`, `Stepper.test.tsx:197/199`, `button.test.tsx:83/84`), alle reine
Erwartungswert-Anpassungen, kein echter Fund. Die Umstellung ist also nicht „gut abgesichert",
sondern für die heutige Suite praktisch unsichtbar — das ist die Begründung für die neue Ebene.
**Achtung bei `button.test.tsx:84`:** `not.toMatch(/h-11/)` wird nach der Umstellung *vacuously
true* — ein Test, der grün bleibt und nichts mehr prüft, ist schlimmer als ein gebrochener; er
muss aktiv auf das neue Maß umgezogen werden.

### Neue Ebene: `frontend/src/designSystem.contract.test.ts` (vitest, Umgebung `node`)

1. **Kontrastmatrix.** Werte ausschließlich aus `index.css`; Schwelle (4,5 / 3,0),
   WCAG-Luminanzformel und Vordergrund/Untergrund-Paarung sind die unabhängigen Sollgrößen im
   Test. **Der Tautologie-Brecher:** Die Formel wird gegen drei extern belegte Referenzpaare
   kalibriert — `#FFFFFF` auf `#000000` = 21,00 (mathematisches Maximum), `#FFFFFF` auf `#0B0C10`
   = 19,55, und `#FFFFFF` auf `#FF3D00` = 3,55, das **als Fehlschlag erkannt werden muss** (ohne
   diese Gegenprobe kann eine kaputte Formel alles durchwinken). Die Formel wird selbst gerechnet,
   nie werden die in der ADR ausgerechneten Zahlen als Erwartungswert abgeschrieben — sonst prüft
   der Test Abschreibefehler, nicht Kontrast.
   Chip-, Rating- und Status-Paare werden über die Namenskonvention **aus der CSS aufgezählt statt
   aufgelistet**, mit Kardinalitäts-Assertion (13 / 3 / 4) und Abgleich der Schlüsselmenge gegen
   das feste Kategorien-Set — so kann eine vierzehnte Kategorie nicht ungeprüft hinzukommen.
   Jedes deklarierte Vordergrund-Token muss in mindestens einer Zeile vorkommen; `--text-disabled`
   und `--border` sind die zwei begründeten Ausnahmen. Der Parser ist auf den `:root`-Block
   begrenzt und **schlägt fehl, statt Unparsebares zu überspringen** — ein still ausgelassenes
   Token wäre ein Loch mit grüner CI, also genau die Fehlerklasse, gegen die der Test antritt.
2. **Streich- und Positivprüfung** über `frontend/src/**`, `frontend/index.html` und
   `frontend/vite.config.ts` — nicht nur `index.css`, sonst blitzt beim PWA-Start weiterhin
   `background_color: '#f5ead8'` auf und die CI bleibt grün. Jedes gestrichene Token wird in
   **beiden** Schreibweisen gesucht (CSS-Variable `--neutral-500` *und* Utility
   `text-neutral-500`, `shadow-warm-sm`, `font-heading`, `.washed`, `--spacing-o4`) — der heutige
   Bestand trägt beide Formen an verschiedenen Stellen. Positive Gegenprobe: `color-scheme: dark`
   gesetzt, die neuen Tokens vorhanden, kein Organic-Hexwert mehr auffindbar (sonst bestünde der
   Test auch bei leerer `index.css`).
3. **Kompilier-Prüfung (Kernstück).** Jede in `src/**` verwendete Utility aus den
   Design-Namensräumen erzeugt beim tatsächlichen Tailwind-Lauf eine Regel. Über `compile()` aus
   `@tailwindcss/node` — liegt bereits transitiv über `@tailwindcss/vite` vor, wird aber als
   **explizite** `devDependency` versionsgleich zu `tailwindcss` eingetragen (sich auf eine
   transitive Auflösung zu verlassen wäre genau die stille Kopplung, gegen die dieser Test
   antritt). Prüfung als `build([kandidat]) !== build([])` — ein `output.includes('@layer
   utilities')` wäre **falsch**, weil die bloße Layer-Deklaration immer in der Ausgabe steht. Der
   Extraktor strippt Kommentare und überspringt String-Literale mit `${`, sonst entstehen
   Fehlalarme aus Prosa und Template-Strings.
   *Im Spike gegen den aktuellen Stand verifiziert: 103 Kandidaten, 0 Fehlalarme, 320 ms.*
   Schließt die Fehlerart „gestrichene Utility erzeugt still keine Regel", die weder Build noch
   Typprüfung noch Komponententest sieht.
4. **Statische Verwendungsregeln:** `text-text-disabled` nur als `disabled:`-Variante;
   `text-danger` verboten (nur `text-danger-text`); kein `border-border` in den
   Bedienelement-Primitiven; `lucide-react` genau ein benannter Import in genau einer Datei (kein
   `import * as`, kein berechneter Zugriff auf das Modulobjekt); keine zusammengebauten
   Klassennamen in `badge.tsx`/`icon.tsx`/`CategoryBadge.tsx`; kein `ring-offset`/`focus-visible:`
   in `.tsx`; **kein `className`, das Trefferflächen-Utility und `overflow-hidden` zugleich
   trägt** (im Bestand nachweislich relevant: `PhotoGridPage.tsx:205` und
   `PhotoComparePage.tsx:64` sind selbst das interaktive Element); in `components/ui/*.tsx` steht
   neben jeder `hover:`-Variante eine `active:`-Variante.
5. **Fokus-Regel:** `index.css` enthält **genau eine** `:focus-visible`-Regel (zählend geprüft,
   nicht nur „enthält") mit `outline: 2px solid var(--accent)` und `outline-offset: 2px`.

### Komponentenebene, semantisch

`Icon` exportiert `data-icon={name}` als semantischen Haken (im Stil der bestehenden
`data-suggested`/`data-status`-Konvention, kein Klassenname — hält Stufe 2 aus).

- **Mehrfachcodierung** der drei Bewertungszustände als *paarweise Verschiedenheit* von
  zugänglichem Namen und `data-icon`; Durchstreichung als DOM-Merkmal (Attribut oder `<s>`, nicht
  als Klassenname `line-through`). Analog für `RatingButtons` (`aria-pressed`) und die
  Toast-Ausprägungen. Das `–`-Badge für unbewertet inklusive `aria-label="Unbewertet"` bleibt
  ausdrücklich erhalten und darf beim Umkleiden nicht als Aufräumarbeit verschwinden.
- **`CategoryBadge`**: alle 13 `category_key` liefern ein Farbpaar (über das feste Set iterieren,
  nicht 13 Fälle abschreiben); unbekannter Key → neutrales Paar, kein Absturz, mit den
  nachweislich existierenden Altwerten `"unerkannt"`, `"landscape"`, `"people"` als konkrete
  Fälle; `aria-label`/`title` tragen weiterhin den vollen Anzeigenamen aus dem Server-Set (die
  Teil-Rücknahme von 0289 gilt nur für Farben, nicht für Namen — dieser Test hält das fest).
- **`CloudVisionStatusList`**: je Status ein sichtbarer, paarweise verschiedener Text; die drei
  „nicht gelaufen"-Zustände teilen sich den `StatusDot`, der Test muss also zulassen, dass das
  Symbol gleich ist, und die Unterscheidung am Text festmachen. Heute prüft **kein** Test die
  Glyphen dort — ihr Austausch bricht nichts, genau der stille Fall.
- **`Stepper`**: die drei Zustände erledigt/aktuell/blockiert ohne Farbe unterscheidbar
  (`aria-current` bzw. `data-state` + Text), statt der bisherigen `size-11`-Assertion.
- **`icon.tsx`**: alle 12 Namen rendern ein `<svg>` (parametrisiert über die exportierte
  Namensliste); Regelfall `aria-hidden="true"` + `focusable="false"`; mit `title` → `role="img"`;
  `data-icon` gesetzt; Größen-Default 16. Zwei Sonderfälle als eigene Tests: `name="image"`
  (greift ab, dass versehentlich das DOM-Global `Image` importiert wurde) und `name="x-circle"`
  (das ist der von ADR 7b geforderte Nachweis `CircleX` vs. `XCircle` gegen die **tatsächlich
  installierte** Version, statt zu raten).
- **`BrandMark`**: bewusst **kein** neuer Test — ein Test auf drei Kreise wäre wertlos.
  Stattdessen steht der Anmeldebildschirm auf der Sichtprüfungsliste, weil der heutige
  `bg-bg`-Ausstanz-Kreis auf dem neuen Grund voraussichtlich nicht mehr funktioniert. Ehrlicher
  Verzicht schlägt Schein-Abdeckung.

### jsdom-Fallstrick beim Dialog (entscheidungsrelevant)

jsdom implementiert **weder** `showModal()` (der Projekt-Polyfill in `setupTests.ts` setzt nur das
`open`-Attribut und feuert `close`) **noch** die native Fokusfalle **noch** die Esc-Behandlung des
`<dialog>`-Elements. Ein Test gegen ein natives `<dialog>` würde also den Polyfill prüfen, also
nichts. **Entscheidung: Fokusfalle und Esc werden in eigenem JS implementiert** — genau weil die
Alternative eine untestbare Zusage wäre. Getestet werden: Tab vom letzten auf das erste Element,
Shift+Tab rückwärts, Esc ruft `onClose`, `aria-modal` und `aria-labelledby` auf den Titel,
**Erstfokus auf der harmlosesten Aktion** (Abbrechen), **Fokusrückgabe** an das auslösende Element
nach dem Schließen. Der Hintergrundklick **schließt nicht** (der erste Konsument ist ein Dialog vor
einer kostenpflichtigen Aktion) — entschieden und getestet statt undefiniert.

### Bewusst nicht automatisiert

jsdom hat keine Layout-Engine: `getBoundingClientRect()` liefert 0, `getComputedStyle()` löst keine
Tailwind-Klassen auf. Damit ist prinzipiell nicht prüfbar — und jeder Test, der es vorgäbe, prüfte
in Wahrheit einen Klassennamen: tatsächlich gerenderte Größen, Abstände zwischen aufgespannten
Trefferflächen, Klippen durch einen *Vorfahren* mit `overflow: hidden` (der Fall auf demselben
Knoten ist dagegen abgedeckt, siehe Regel 4), Sichtbarkeit von Flächen, horizontales Scrollen bei
360px, visuelle Unterscheidbarkeit von Auswahl und Fokus, tatsächliches Tree-Shaking.

Abgedeckt über die neun Prüfpunkte des UI/UX-Abschnitts in 360px und Desktopbreite gegen die vier
harten Ausschlusskriterien, **mit Screenshot-Belegen im Pull Request** (Stakeholder-Entscheidung).

**Tree-Shaking:** testbar sind die *Bedingungen* (Regel 4), nicht die *Wirkung* — und das reicht,
weil die Bedingungen die Wirkung determinieren. Ein Bundle-Größen-Budget wird bewusst **nicht**
gebaut (langsam, laut bei jeder harmlosen Änderung, gegenüber Stufe 2 wertlos); stattdessen eine
einmalige Messung im Umsetzungslauf (Bundle-Größe vor/nach, Zahl in die Spec) — ein Beleg statt
eines Dauertests.

### Coverage

Für das Frontend existiert **kein** Coverage-Gate — `.github/workflows/ci.yml` fährt
`--cov-fail-under=80` ausschließlich im `backend`-Job, der `frontend`-Job läuft
Lint/Typecheck/Test/Build ohne Coverage-Messung. Dieser PR ist praktisch reines Frontend, das Gate
sagt hier buchstäblich nichts. Es wird auch **keines eingeführt**: Bei einer Umgestaltung wird eine
umgekleidete Komponente von den bestehenden Tests weiterhin zu 100 % *ausgeführt*, ohne dass eine
einzige Assertion die Umkleidung berührt — Coverage bliebe unverändert hoch und erzeugte exakt die
falsche Sicherheit. Ersatzmaß sind die benannten Vertragstests; die Lücke gehört ins Testkonzept.

### TDD-Reihenfolge

Vertragsdatei zuerst (Kontrastmatrix, Streichliste, Verwendungsregeln, Mehrfachcodierung, Icon- und
Dialog-Tests starten **rot**) → `index.css` → Primitive → die sechs Nacharbeitslisten →
Kompilier-Test als Abschluss-Scan. Der Kompilier-Test startet **grün** (heute gibt es keine
verwaisten Utilities); er ist Regressionsnetz, kein TDD-Treiber, und wird **nicht künstlich rot
gemacht** — ein erfundener roter Zustand wäre eine Lüge über die Testabsicht.

### Testkonzept

`specs/architecture/0002-testkonzept.md` **muss** im selben PR ergänzt werden, weil diese Spec eine
bestehende Festlegung teilweise zurücknimmt: Der Eintrag „Reine UI-Kosmetik (exakte Pixel-/
Farbwerte, CSS-Feinheiten) … nicht automatisiert testbar mit sinnvollem Aufwand" (Zeile 831) ist ab
jetzt nur noch zur Hälfte wahr. Drei Punkte: (1) neue Frontend-Sektion zum Design-Vertrag mit dem
Fünferblock, der Tautologie-Auflösung und der `compile()`-Prüfung samt der Warnung vor dem
`@layer utilities`-Fehlschluss; (2) **ausdrückliche Teil-Rücknahme** des Eintrags Zeile 831 —
exakte Farbwerte *sind* prüfbar geworden, sobald sie eine ausgerechnete Zusage tragen oder eine
Streichung belegen sollen; Pixelmaße, Layout und visuelle Wirkung bleiben es nicht; (3) drei neue
benannte Lücken: kein Frontend-Coverage-Gate, jsdom ohne Layout-Engine, natives `<dialog>` nicht
auf Fokusfalle/Esc prüfbar.

## Security

Sicherheitsrelevant ist an dieser Stufe ausschließlich die **Lieferkette**: Das Feature nimmt
drei neue npm-Laufzeitabhängigkeiten in das ausgelieferte Frontend-Bundle auf
(`lucide-react`, `@fontsource/inter`, `@fontsource/jetbrains-mono`) und entfernt zwei
(`@fontsource/caprasimo`, `@fontsource/figtree`), Nettobilanz +1 (ADR 0055, Konsequenzen).
Kein Backend-Diff, kein neuer Endpunkt, keine neue Eingabe von außen, keine Änderung an Auth,
Berechtigungen oder Datensichtbarkeit zwischen den beiden Nutzern — die übrigen Änderungen
(Farbwerte, `theme-color`/`color-scheme`, Manifest-Farben, `dialog.tsx`, Einkleidung von
`input.tsx`, Chip-Farbtabelle) berühren keine Vertrauensgrenze.

**Bedrohung 1 — untergeschobene oder kompromittierte Paketversion.** Eine bösartige Version
eines der drei Pakete liefe als JavaScript im Browser beider Nutzer, im selben Ursprung wie
die Anwendung, und käme damit an das im Browser gehaltene JWT. Bewertung der konkreten Pakete
(gegen die npm-Registry und die OSV-Advisory-Datenbank geprüft, nicht angenommen):
`lucide-react` 1.41.0, ISC, **null Laufzeit-Abhängigkeiten** (nur `react` als Peer),
~98 Mio. Downloads/Woche, keine Advisory in OSV — für ein privates Familienprojekt vertretbar.
Beide `@fontsource`-Pakete: 5.3.0, OFL-1.1, keine Abhängigkeiten, keine Advisory; sie sind
zudem derselbe, bereits seit Spec 0285 verwendete Paketstamm, nur andere Schriften.
Einziger nennenswerter Punkt: `lucide-react` wird von einem einzelnen npm-Konto veröffentlicht,
ein Kontoübernahme-Szenario ist damit nicht ausgeschlossen.
**Gegenmaßnahmen (bestehend, keine neue Mechanik nötig):** `frontend/package-lock.json` pinnt
Version und Integritäts-Hash, CI und `frontend/Dockerfile` installieren ausschließlich über
`npm ci` (nie `npm install`) — eine nachträglich veränderte Version desselben Version-Tags
schlägt hart fehl statt still durchzugehen. Dependabot-Sicherheitsupdates sind für das
Repository aktiv und haben in diesem Projekt nachweislich schon Alerts erzeugt (Specs 0014,
0015). Der Lockfile-Diff ist Teil des Reviews dieses PRs.

**Bedrohung 2 — Umfang des eingezogenen Fremdcodes.** `lucide-react` ist entpackt ~32 MB
(ein Modul je Symbol). Das Tree-Shaking-Gebot aus ADR 0055 (7d: nur benannte Importe, statisches
Objektliteral in `components/ui/icon.tsx`, nie Namespace-Import oder berechneter Schlüssel auf
das Paket-Objekt) ist deshalb auch aus dieser Sicht verbindlich: Es hält die Menge fremden,
tatsächlich ausgelieferten Codes bei zwölf Pfad-Definitionen statt beim gesamten Satz. Prüfbar
über die Größe der `dist/assets/*.js` vor/nach der Umstellung — erwartet wird ein Zuwachs im
niedrigen kB-Bereich, nicht im MB-Bereich.

**Bedrohung 3 — stiller Rückfall auf einen Fremdabruf der Schriften.** Der Grund für das
Selbsthosten (Spec 0285) ist unverändert gültig und ist zur Hälfte ein Datenschutzgrund: ein
CDN-Link würde bei jedem Aufruf IP-Adresse und Referrer beider Nutzer an einen Dritten geben,
und offline scheitern. Beim Schriftwechsel könnte das versehentlich brechen (z.B. ein
`@import url(https://fonts.googleapis.com/...)` statt der Paket-CSS).
**Gegenmaßnahme:** Die Schrift-CSS wird wie bisher gewichtsweise aus dem Paket importiert
(`@fontsource/inter/400.css` usw. in `frontend/src/index.css`), und nach dem Build wird
verifiziert, dass die erzeugte CSS **keine** externe URL enthält und die `woff2`-Dateien im
Precache-Manifest des Service Workers stehen — geprüft statt behauptet.

**Bestätigungspflicht — `detail`-Text in der neuen Fehlerdarstellung.** Die Meldung zeigt
weiterhin den unveränderten `detail`-Text des Servers. Das ist inhaltlich unverändert und bleibt
zulässig (die Werte sind bis auf drei OpenCloud-Pfade kuratierte Konstanten; die Anmeldung nutzt
eine einzige Konstante ohne Benutzer-Enumeration). Das mit Spec 0058 gesetzte Muss-Kriterium
gilt in der neuen Einkleidung unverändert weiter: **Fremdtext ausschließlich als regulärer
React-Textknoten**, kein `dangerouslySetInnerHTML`, kein Markdown-/Rich-Text-Rendering und keine
Verlinkung im neuen Meldungsbanner — der Titel ist kuratiert, nur der Beitext trägt `detail`.
Der eigentliche Risikopunkt ist nicht die Prominenz, sondern die Versuchung, die die neue Form
mitbringt: Ein Banner mit Titel und Beitext lädt dazu ein, den Beitext „schöner" zu machen. Genau
das wäre der erste echte Bruch, weil `detail` roher Exception-Text sein kann.

**Härtungsnotiz ohne Bedrohungsbezug** (kein Finding): Die Auflösung der Chip-Farbe über eine nach
`category_key` geschlüsselte Konstante sollte auf eigenen Schlüsseln arbeiten (`Object.hasOwn`,
`Map` oder ein `in`-Check), damit ein historischer Altwert wie `constructor` den Neutral-Fallback
bekommt statt eines geerbten Prototyp-Werts. Robustheit, kein Angriffspfad — die Keys stammen aus
der eigenen Datenbank.

**Ins Sicherheitskonzept** (`specs/architecture/0003-securitykonzept.md`, im selben PR): ein neuer
Angriffsflächen-Abschnitt mit der obigen Lieferketten-Bewertung; die **Richtigstellung** der
bekannten Lücke „Kein automatisiertes Dependency-Scanning" (Dependabot-Sicherheitsupdates und
Secret-Scanning inkl. Push-Protection *sind* aktiv und haben nachweislich gegriffen — es fehlt nur
ein blockierendes CI-Gate und eine `.github/dependabot.yml`); und ein neuer Lücken-Eintrag
„Keine Content-Security-Policy" (siehe Out of Scope).

## Offene Fragen

Keine. Die drei im Verfeinerungsablauf offenen Produktentscheidungen (Text-Muted-Wert,
Kategorie-Chip-Farbigkeit, Symbolsatz-Bezug) sowie die Trefferflächenfrage sind von Daniel
entschieden und im Abschnitt „Entscheidungen" festgehalten.

## Out of Scope

- Die gestalterische Überarbeitung der einzelnen Ansichten (Anmeldung, Projektliste, Foto-Raster,
  Bewertung, Kuratierung, Detailansicht, Statistik) — das ist **Stufe 2**, siehe
  [#321](https://github.com/TheRealKoller/photosort/issues/321).
- Ein Umschalter zwischen hellem und dunklem Erscheinungsbild. Ein heller Modus ist bewusst nicht
  mehr vorgesehen.
- Inhaltliche oder funktionale Änderungen an bestehenden Abläufen. Insbesondere entsteht **kein**
  schwebendes Toast-System — übernommen wird die Optik des Board-Toasts, nicht sein Verhalten.
- Bewertungsleiste, Navigationselement/Sidebar und die Anordnung der Ansichten: im Board
  vorhanden, aber nicht in der Grundelemente-Liste dieser Story.
- **Eine Content-Security-Policy.** PhotoSort hat heute keine (weder in `frontend/nginx.conf` noch
  als `<meta>`). Für die Zusage „Schriften self-gehostet, kein Fremdabruf zur Laufzeit" ist sie
  nicht erforderlich — die Bindung entsteht baulich über die gebündelten `@fontsource`-Pakete —,
  wäre aber ein Netz gegen einen künftig versehentlich eingebauten CDN-Link und ein Restschutz für
  die XSS-Konvention. Bewusst **nicht** als Beifang dieser Spec: `script-`/`style-`/`worker-src`
  betreffen die ganze Anwendung (Tailwind, React, Service Worker) und brauchen eigene
  Akzeptanzkriterien und einen eigenen Test. In diesem PR entsteht nur ein Eintrag unter „Bekannte
  Lücken" des Sicherheitskonzepts, damit das Thema nicht unsichtbar bleibt.
- **Ein blockierendes CI-Gate für Abhängigkeits-Schwachstellen** (`npm audit`/`pip-audit`) und eine
  `.github/dependabot.yml` für geplante Versions-Updates. Dependabot-Sicherheitsupdates sind
  bereits aktiv; was fehlt, ist das Gate. Eine Pipeline-Änderung mit eigener Folgenabwägung —
  bisher betraf jeder Alert in diesem Projekt reine Dev-Abhängigkeiten und wurde als nicht
  exploitbar bewertet, ein hartes Gate würde den Build daran künftig anhalten. Eigene Story.
- **Ein Frontend-Coverage-Gate.** Existiert heute nicht und wird hier nicht eingeführt: Bei einer
  Umgestaltung bliebe die Zeilenabdeckung unverändert hoch, ohne dass eine Assertion die Änderung
  berührt — es wäre falsche Sicherheit und erzeugte Druck, Assertions zu erfinden.
- **Ein Bundle-Größen-Budget als Dauertest.** Stattdessen eine einmalige Messung im Umsetzungslauf.

## Bundle-Größen-Messung (einmalig, Umsetzungslauf 2026-09-05)

`npm run build` in `frontend/`, jeweils der einzelne Anwendungs-Chunk bzw. die Anwendungs-CSS:

| | vorher (Organic) | nachher (Dark Utility Register) | Delta |
|---|---|---|---|
| `dist/assets/index-*.js` | 452,26 kB (gzip 138,73 kB) | 457,15 kB (gzip 141,12 kB) | **+4,89 kB / +2,39 kB gzip** |
| `dist/assets/index-*.css` | 44,12 kB (gzip 13,67 kB) | 57,15 kB (gzip 16,85 kB) | +13,03 kB / +3,18 kB gzip |

Der JS-Zuwachs liegt im erwarteten **niedrigen kB-Bereich, nicht im MB-Bereich** — das Tree-Shaking greift, es landen zwölf Pfad-Definitionen im Bundle statt des gesamten Lucide-Satzes (entpackt ~32 MB). Der CSS-Zuwachs stammt überwiegend aus den 26 Kategorie-Chip-Tokens und den zusätzlichen `@theme`-Einträgen und ist unabhängig von der Symbolfrage.

Ergänzend verifiziert (Sicherheits-Muss-Kriterium „Schriften self-gehostet"): die gebaute CSS enthält **keine externe URL** — nur `data:`-URIs und lokale `/assets/`-Pfade; das Precache-Manifest des Service Workers enthält 32 `woff2`-Einträge.
