# 0287 - Fünf Design-Richtungen an drei Kernansichten vergleichen

**Status:** Implemented ([PR #306](https://github.com/TheRealKoller/photosort/pull/306))
**Erstellt:** 2026-08-31
**Bezug:** [Issue #287](https://github.com/TheRealKoller/photosort/issues/287)

## Ziel

Die visuelle Identität von PhotoSort soll erstmals das Ergebnis einer bewussten Wahl sein statt eines Imports. Das heute verwendete Design-System „Organic" stammt aus einem Design-Werkzeug-Bundle (Spec [`0285`](./0285-organic-design-import.md)), wurde nicht für PhotoSort entworfen und liegt als zweite Schicht über der ursprünglichen Gestaltungsrichtung — es gab nie eine Alternative zu sehen. PhotoSort ist eine App für Familien-Urlaubsfotos; wie sie aussieht, ist Teil des Produkts, nicht Beiwerk.

Deshalb werden mehrere Gestaltungsrichtungen an denselben Ansichten durchgespielt und verglichen, bevor eine davon die App langfristig prägt. Der Vergleich passiert jetzt, solange das Frontend klein ist — jede weitere Ansicht verteuert einen späteren Wechsel.

## User Story

Als Daniel möchte ich mehrere eigenständige Design-Richtungen an den wichtigsten Ansichten von PhotoSort nebeneinander sehen, damit ich bewusst entscheiden kann, welche visuelle Sprache die App künftig trägt, statt die zuletzt importierte Vorlage einfach zu behalten.

## Akzeptanzkriterien

- [ ] Es liegen Design-Entwürfe für genau diese drei Ansichten vor: **Fotogrid** (Kernansicht), **Foto-Detailseite** und **Pipeline-Stepper/Kuratierung**. Projektliste und Projekt-Anlage sind ausdrücklich nicht Teil des Vergleichs.
- [ ] Es treten **fünf Richtungen** gegeneinander an: vier neu entworfene — *konservativ/klar*, *verspielt*, *minimalistisch*, *ganz kreativ* — sowie **„Organic" als fünfter, gleichwertiger Kandidat** in derselben Machart. Organic wird nicht vorab verworfen.
- [ ] Jede Richtung zeigt jede der drei Ansichten in **hellem und dunklem Modus**.
- [ ] Jede Richtung hat eine erkennbar eigene Handschrift: eigene Farbwelt, eigene Schriftwahl, eigene Formsprache (Rundungen, Abstände, Tiefe). Zwei Richtungen dürfen nicht als Variationen derselben Idee durchgehen; nachweisbar entlang der Achsentabelle im Abschnitt „UI/UX": je zwei Richtungen unterscheiden sich in mindestens vier der dort genannten Achsen deutlich.
- [ ] **Alle Richtungen zeigen identische Beispielinhalte** (dieselben Fotos, Bewertungen, Kategorien, Fortschrittszustände), damit der Vergleich die Gestaltung trifft und nicht den Inhalt.
- [ ] Die Entwürfe sind **im Browser durchklickbar** und über einen gemeinsamen Einstieg erreichbar, der alle Richtungen und Ansichten nebeneinander zugänglich macht.
- [ ] Die Entwürfe sind ein **Wegwerf-Artefakt**: sie sind von der laufenden Anwendung getrennt, beeinflussen deren Verhalten nicht und werden nach der Entscheidung wieder entfernt.
- [ ] **Umsetzbarkeits-Vorbehalt:** Jede vorgelegte Richtung muss sich mit den für das Frontend bereits gewählten technischen Mitteln umsetzen lassen, ohne dass dafür eine neue externe Abhängigkeit nötig wird — der Vergleich darf keinen Gewinner hervorbringen, der nicht baubar ist. Prüfbare Fassung: Jede vorgelegte Richtung definiert den vollständigen Tokenvertrag aus `frontend/src/index.css` in beiden Modi, referenziert nichts außerhalb ihrer eigenen Datei und lädt keine externe Ressource.
- [ ] Daniel hat sich für **genau eine** Richtung entschieden, und die Entscheidung ist samt kurzer Begründung festgehalten. **„Keine der neuen Richtungen überzeugt, Organic bleibt" ist ein gültiges Ergebnis** und kein Fehlschlag. Die Entscheidung wird nach dem Durchklicken in `specs/decisions/0050-visuelle-gestaltungsrichtung.md` festgehalten und ist **nicht Bestandteil der Umsetzungs-PR**.

## Datenmodell-Bezug

Keiner. Das Design-Labor ist ein reines Frontend-Wegwerf-Artefakt ohne Backend-Zugriff, ohne API-Aufrufe und ohne Persistenz; sämtliche dargestellten Inhalte stammen aus einem statischen Fixture-Modul. `docs/architecture.md` wird deshalb bewusst nicht angefasst.

## Architektur / Umsetzung

### Ort und Isolation: dev-only Zweiteinstieg unter `frontend/design-lab/`

Das Labor liegt als eigener Ordner `frontend/design-lab/` **innerhalb** des Vite-Roots, aber **außerhalb** von `frontend/src/`. Vite serviert im Dev-Modus jede HTML-Datei unterhalb des Roots (`http://localhost:5173/design-lab/`), baut aber nur die in `build.rollupOptions.input` konfigurierten Einstiege — Default ist ausschließlich `frontend/index.html`. Daraus folgt ohne eine einzige Zeile Vite-Konfiguration:

- **Kein Bundle-/Deploy-Leck:** Das Labor landet nie in `dist/`, nie im nginx-Image, nie im PWA-Precache. `vite-plugin-pwa` wird nicht angefasst.
- **Kein Laufzeit-Einfluss:** Die App importiert nichts aus dem Labor; das Labor importiert nichts aus `frontend/src/` (Einbahnstraße in beide Richtungen, siehe Schutzgeländer unten). Kein Router-Eintrag, kein Link aus der App ins Labor.
- **Trotzdem geprüft:** `oxlint` läuft ohne Pfadargument über das gesamte Frontend, erfasst das Labor also automatisch. Für `tsc -b` wird `frontend/tsconfig.app.json` einmalig um `"design-lab"` in `include` erweitert (eine Zeile, mit dem Labor wieder zu entfernen) — bewusst statt eines eigenen Projekt-Referenz-Tsconfigs, weil die einzeilige Variante restlos reversibel ist.

Gegen Tailwinds automatische Quellsuche (v4 scannt den Projektbaum, nicht nur `src/`) bekommt `frontend/src/index.css` eine Zeile `@source not "../design-lab";`, damit das Labor die generierte Produktiv-CSS nicht anfassen kann. Sollte die Direktive mit der installierten Version scheitern, ist ihr Wegfall unkritisch — das Labor benutzt keine einzige Tailwind-Klasse (siehe unten) —, dann entfällt sie ersatzlos.

**Verworfene Alternativen:** (a) *Eigene Vite-App auf Repo-Ebene* (`design-lab/` mit eigener `package.json`) — beste Isolation, aber ein zweites `node_modules`/Lockfile und ein zweiter Installationsschritt für ein Wegwerf-Artefakt; die Isolation, die sie erkauft, liefert der dev-only Einstieg bereits. (b) *Zweiter Rollup-Input in `vite.config.ts`* — würde das Labor in den Produktions-Build und damit ins Deploy ziehen und genau das Akzeptanzkriterium „getrennt von der laufenden Anwendung" verletzen.

### Bautechnik: React + TS für die Struktur, gescopte reine CSS-Skins für die Gestaltung

Die Prototypen werden **im Zielstack** gebaut (React-Komponenten, TypeScript, derselbe Vite-Dev-Server), gestaltet aber mit **handgeschriebener, pro Richtung gescopter CSS auf Basis von CSS-Custom-Properties — ohne Tailwind im Labor**. Begründung:

1. **Das Design-System von PhotoSort *ist* bereits eine CSS-Variablen-Tokenschicht.** `index.css` definiert Rohwerte in `:root`, der `@theme`-Block mappt sie auf Utilities; die Komponenten kennen nur Tokennamen. Eine Richtung, die als Tokensatz plus Komponentenregeln vorliegt, ist damit keine Skizze, sondern eine fast mechanische Vorlage für die spätere Übernahme.
2. **Fünf Richtungen brauchen fünf Token-Sätze gleichzeitig im selben Dokument.** Tailwinds `@theme` ist global und pro Build genau einmal vorhanden — fünf verschiedene Radien-, Abstands- und Schriftskalen ließen sich darin nur über Präfix-Hacks nebeneinanderstellen. Gescopte CSS-Variablen können das von Haus aus.
3. **Statisches HTML pro Richtung/Ansicht wurde verworfen:** 15 Dateien (3 Ansichten × 5 Richtungen) mit kopiertem Inhalt widersprechen dem Akzeptanzkriterium „alle Richtungen zeigen identische Beispielinhalte" konstruktiv — jede Korrektur am Inhalt müsste 15-mal nachgezogen werden. Geteilte React-Komponenten garantieren Inhaltsgleichheit dagegen mechanisch.

**Markup-Vertrag:** Es gibt genau **drei** Ansichtskomponenten, die für alle fünf Richtungen dasselbe DOM erzeugen. Sie vergeben stabile, laborinterne Klassennamen (`dl-grid`, `dl-tile`, `dl-badge`, `dl-step`, …) und `data-*`-Zustände (`data-state="done|current|pending|blocked"`, `data-rating="favorite|album_worthy|rejected|none"`). Eine Richtung gestaltet ausschließlich über diese Haken. Wo eine Handschrift Dekor braucht, das andere nicht haben, rendert das gemeinsame Markup ein leeres `aria-hidden`-Element (`dl-tile__decor`), das die meisten Richtungen ausblenden.

**Umsetzbarkeits-Vorbehalt, operationalisiert:** Jede Richtungs-CSS **muss** dieselben Tokennamen definieren, die `frontend/src/index.css` heute im `:root`-Vertrag führt (`--bg`, `--surface`, `--border`, `--text`, `--text-h`, `--accent`, `--accent-strong`, `--accent-fg`, `--accent-bg`, `--accent-border`, `--accent-2`, `--accent-2-strong`, die drei `--rating-*`/`--rating-*-fg`-Paare, die `--status-*`-Familie, `--shadow*`, `--sans`, `--heading`, `--mono`) — zusätzliche eigene Tokens sind erlaubt, Weglassen nicht. Damit ist „lässt sich mit den vorhandenen Mitteln bauen" nicht länger eine Einschätzung, sondern eine prüfbare Eigenschaft (siehe Schutzgeländer), und die spätere Übernahme reduziert sich im Kern auf einen Wertetausch in `:root` — genau der Weg, den Spec 0285 schon einmal gegangen ist.

**Schriften:** Die vier neuen Richtungen nutzen **ausschließlich bereits installierte Familien und Plattform-/Web-Safe-Stacks** (`system-ui`, `ui-serif`/Georgia, `ui-rounded`, `ui-monospace`, Verdana/Trebuchet, Times/Palatino). Caprasimo und Figtree bleiben der Richtung „Organic" vorbehalten, sonst verwischt der Vergleich. Keine neue `@fontsource`-Abhängigkeit — das Akzeptanzkriterium „ohne dass dafür eine neue externe Abhängigkeit nötig wird" ist wörtlich zu nehmen. Typografische Eigenständigkeit entsteht über Familienwahl, Skala, Gewicht, Laufweite, Versalien und Zeilenmaß.

### Beispielinhalte: ein Fixture-Modul, prozedural erzeugte Motive, optional lokale Fotos

`frontend/design-lab/fixtures.ts` ist die einzige Inhaltsquelle für alle fünf Richtungen: 12 Fotos (Dateiname, Aufnahmezeit, eigene Bewertung bzw. automatischer Vorschlag, Kategorie samt Feinlabel, Kriterien-Scores, Ranking/Cluster, ein Foto mit Kategorie-Override), das Kategorien-Set (Menschen, Landschaft, Essen & Trinken, Gebäude/Bauwerk, „Nicht erkannt" inkl. des neutralen Erklärtexts), die fünf Pipeline-Schritte mit gemischten Zuständen (Scan erledigt, Ausschuss-Erkennung erledigt, Ausschuss-Gate aktuell, Kriterien-Bewertung ausstehend, Kategorie-Kuratierung blockiert) sowie Tages-/Cluster-Überschriften.

Die Bilder erzeugt `photoSvg.ts` deterministisch als SVG-Data-URI: flächige, naturalistisch getönte Urlaubsmotive (Küste, Bergkamm, Gasse, Wald, Tisch, Gruppensilhouette) in 4:3 und zwei Hochformaten, mit einer **bewusst neutralen Palette**, die keiner der fünf Richtungen entgegenkommt. Kein Netzabruf zur Laufzeit (kein picsum/Unsplash) — das Labor bleibt offline durchklickbar und holt sich keine Drittquelle ins Haus. Die vorhandenen `scripts/demo_photos/*.jpg` sind bewusst **nicht** die Quelle: es sind abstrakte Formfixtures für die Scoring-Pipeline (Farbklötze auf Verlauf), die als „Urlaubsfoto" nichts zeigen.

Wer den Vergleich mit echten Fotos sehen will, legt beliebige JPGs in `frontend/design-lab/photos-local/` ab — per `.gitignore` ausgeschlossen, per `import.meta.glob('./photos-local/*.{jpg,jpeg,png}', { eager: true, query: '?url', import: 'default' })` nach Dateinamen sortiert eingelesen und positionsgleich über die generierten Motive gelegt. Damit bleibt CLAUDE.mds Verbot („keine Bilddaten der Familie im Repository") unangetastet, ohne den Vergleich auf Vektorattrappen festzunageln.

### Hell/Dunkel und Token-Isolation

Kein `prefers-color-scheme` im Labor. Jede Richtung rendert in einen eigenen Wurzelknoten mit `data-direction="<id>" data-mode="light|dark"`; die zugehörige CSS-Datei definiert ihre Tokens vollständig in beiden Blöcken:

```css
[data-direction='minimal'][data-mode='light'] { --bg: …; /* vollständiger Tokensatz */ color-scheme: light; }
[data-direction='minimal'][data-mode='dark']  { --bg: …; /* vollständiger Tokensatz */ color-scheme: dark; }
[data-direction='minimal'] .dl-tile { … }
```

**Jede** Regel einer Richtungsdatei beginnt mit ihrem eigenen `[data-direction="…"]` — dadurch können fünf gleichzeitig geladene Stylesheets, die dieselben `dl-`-Klassen ansprechen, sich nicht gegenseitig beeinflussen, und dieselbe Ansicht lässt sich in fünf Richtungen × zwei Modi gleichzeitig auf einer Seite zeigen. `color-scheme` pro Modus sorgt dafür, dass native Bedienelemente (Zahlfeld der Kuratierung, Scrollbalken) mitziehen. Die Labor-Hülle selbst nutzt einen eigenen, absichtlich unauffälligen Klassenraum (`lab-*`) mit neutralem Grau, damit die Rahmung keine Richtung bevorzugt.

### Gemeinsamer Einstieg

`App.tsx` ist eine Hülle mit drei Umschaltern — **Richtung** (5), **Ansicht** (Fotogrid / Foto-Detail / Pipeline & Kuratierung), **Modus** (hell/dunkel) — plus zwei Zusatzmodi, die den eigentlichen Vergleich tragen:

- **Nebeneinander:** die gewählte Ansicht in allen fünf Richtungen in einer horizontal scrollbaren Reihe fester Rahmenbreite (~390 px, Mobilbreite), jede Kachel mit Richtungsnamen und Ein-Satz-Charakterisierung.
- **Beide Modi:** die gewählte Richtung/Ansicht hell und dunkel direkt nebeneinander.

Der Zustand steht in der URL (`/design-lab/?dir=minimal&view=grid&mode=dark&compare=1`; `compare` ist eine strikte Positivliste mit `1` = Nebeneinander und `modes` = Beide Modi, jeder andere Wert fällt auf „Einzeln" zurück) über `URLSearchParams` + `history.replaceState` — kein React Router im Labor, damit es keine zweite Routing-Realität neben der App gibt. Die Ansichten sind **Mockups**: Filterleiste, Bewertungsbuttons, Stepper-Schritte usw. zeigen feste Zustände und lösen keine Zustandsänderung aus. Einzige Interaktion sind die Umschalter der Hülle — das hält das Wegwerf-Artefakt klein und verhindert, dass hier nebenbei eine zweite Anwendung entsteht.

Die drei Ansichten bilden den heutigen realen Inhalt ab: **Fotogrid** (`PhotoGridPage`) mit sechs Filter-Pillen, Kachelraster, Bewertungs-/Vorschlags-Badge oben rechts, Override-Marker oben links, „Übernehmen"-Knopf unter Vorschlagskacheln, „Weitere laden"; **Foto-Detail** (`PhotoDetailPage`) mit Positionszähler, Shortcut-Zeile, großem Bild, Cloud-Vision-Status, permanentem Bewertungsdetail-Block (Kriterien mit Qualitätsbalken, Kategorie-Kandidaten, Feinlabels), Vorschlagskasten, Zurück/Weiter und den drei Bewertungsknöpfen; **Pipeline & Kuratierung** (`Stepper` + `KuratierungStepPage`/`CurateCategoriesPage`) mit klebender Fünf-Schritt-Leiste in allen vier Zuständen, Tages- und Cluster-Überschrift, Kategorie-Abschnitten inklusive „Nicht erkannt" am Ende samt Erklärtext, Top-N-Eingabe.

### Betroffene Dateien

**Neu:**
- `frontend/design-lab/index.html` — Zweiteinstieg (dev-only)
- `frontend/design-lab/main.tsx`, `frontend/design-lab/App.tsx`, `frontend/design-lab/shell.css` — Hülle, Umschalter, URL-Zustand, neutrale Labor-Chrome
- `frontend/design-lab/base.css` — richtungsinvariante Struktur (Rasterspalten 2/3/4, Bildseitenverhältnisse, Sticky-Verhalten, Reset), ungescopte `.dl-*`-Selektoren, von G2 ausgenommen; wird **vor** den Richtungsdateien geladen (siehe Teststrategie, „Folgen für die Umsetzung")
- `frontend/design-lab/fixtures.ts` — die eine gemeinsame Inhaltsquelle
- `frontend/design-lab/photoSvg.ts` — deterministische Motive + optionale `photos-local/`-Übersteuerung
- `frontend/design-lab/views/GridView.tsx`, `DetailView.tsx`, `PipelineView.tsx` — gemeinsames DOM für alle Richtungen
- `frontend/design-lab/views/PhotoTile.tsx` — die von Fotogrid und Kuratierung geteilte Kachel. Es bleibt bei drei *Ansichten*; ohne diese vierte Datei hätten Grid und Kuratierung zwei Kopien desselben Kachel-Markups, mit genau dem Driftrisiko, das der Markup-Vertrag ausschließen soll
- `frontend/design-lab/directions/index.ts` — Registry (Id, Anzeigename, Ein-Satz-Charakter, CSS-Import)
- `frontend/design-lab/directions/{organic,klar,verspielt,minimal,kreativ}.css` — die fünf Handschriften
- `frontend/design-lab/guards.test.ts` — Schutzgeländer (siehe unten)

**Geändert (jeweils minimal und mit dem Labor wieder zu entfernen):**
- `frontend/tsconfig.app.json` — `"include": ["src", "design-lab"]` **plus** `"exclude": ["design-lab/guards.test.ts"]`
- `frontend/tsconfig.node.json` — `"include": ["vite.config.ts", "design-lab/guards.test.ts"]`; dieses Projekt trägt bereits `"types": ["node"]`, das App-Projekt dagegen nur `"vite/client"` — ohne diese Aufteilung scheitert `tsc -b` am `node:fs`-Import des Geländers (siehe Teststrategie, „Mechanik")
- `frontend/src/index.css` — eine Zeile `@source not "../design-lab";` mit Entfernungshinweis im Kommentar
- `.gitignore` — `frontend/design-lab/photos-local/`
- `docs/setup.md` — kurzer, als temporär gekennzeichneter Abschnitt „Design-Labor (temporär, Spec 0287)" unter „Quick Start (Entwicklung)": `cd frontend && npm run dev`, dann `http://localhost:5173/design-lab/`

**Ausdrücklich nicht angefasst:** `frontend/vite.config.ts`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/package.json`, `.github/workflows/ci.yml`, `docs/architecture.md` (das Labor ist kein Bestandteil des laufenden Systems und gehört deshalb nicht in die Komponentenübersicht).

### Reihenfolge der Umsetzung

1. **Gerüst + G1:** `index.html`, `main.tsx`, `App.tsx`, `shell.css`, die `tsconfig`-Zeilen — Hülle läuft, Umschalter schalten, Ansichten noch leer. Das Trennungs-Geländer **G1** entsteht hier mit, nicht später: es ist ein Regressionsgeländer und steht ab dem ersten Commit scharf. Früh prüfen: `npm run build` erzeugt weiterhin kein `design-lab`-Artefakt in `dist/` (Security-Auflage B1).
2. **Inhalt:** `fixtures.ts` + `photoSvg.ts` — die Beispieldaten stehen fest, bevor irgendeine Richtung gestaltet wird (sonst driftet der Inhalt der Gestaltung hinterher). `photoSvg.ts` verkraftet ein fehlendes/leeres `photos-local/` klaglos (Security-Auflage A3), und die Hülle zeigt den Glob-Zustand selbstdiagnostisch an.
3. **Markup-Vertrag:** die drei Ansichtskomponenten plus `base.css`, ungestylt, aber vollständig — Klassennamen und `data-*`-Zustände sind ab hier eingefroren.
4. **Schutzgeländer G2/G3/G4** (`guards.test.ts`) — **vor** der ersten Richtungsdatei und damit **rot**: fünf Richtungen werden erwartet, null existieren. Diese parametrisierte Suite ist der fehlschlagende Test, der die Schritte 5 und 6 treibt; ohne diese Reihenfolge wäre das Geländer Nachdokumentation statt TDD.
5. **Richtung „Organic" zuerst:** portiert die heutigen Tokens aus `index.css` in `organic.css`. Sie ist gleichzeitig der fünfte Kandidat und der Beweis, dass der Markup-Vertrag trägt und der Tokensatz vollständig ist. Achtung: `var()`-Verweise auf die Tonleitern **müssen** auf ihren Hexwert aufgelöst werden — das Labor lädt `index.css` nicht (G3e).
6. **Die vier neuen Richtungen**, je eine Datei nacheinander (`klar`, `minimal`, `verspielt`, `kreativ`) — jede für sich fertig inkl. beider Modi, bevor die nächste beginnt; jede nimmt einen weiteren Teil der Geländer-Suite auf Grün.
7. **Vergleichsmodi** (Nebeneinander, Beide Modi) + URL-Zustand mit Positivlisten-Validierung (Security-Auflage D3).
8. **Dokumentation:** `docs/setup.md`, die Ergänzung von `specs/architecture/0002-testkonzept.md` und `specs/architecture/0003-securitykonzept.md`.

Die inhaltliche Ausgestaltung der vier neuen Handschriften (Farbwelt, Formsprache, Dichte) legt der Abschnitt „UI/UX" fest — dieser Abschnitt gibt nur den Rahmen vor, in dem sie sich bewegen müssen.

### Warum hier keine ADR — und welche danach fällig ist

Das Labor führt keine neue Technologie, keine neue externe Abhängigkeit und keine Datenmodell-Struktur ein; es ist ein zeitlich befristetes Entwurfswerkzeug innerhalb der bereits per ADR [`0011`](../decisions/0011-ui-component-library.md) gesetzten Frontend-Wahl. Eine ADR wäre hier Zeremonie ohne Gegenwert.

ADR-pflichtig ist dagegen das **Ergebnis**: Sobald Daniel sich entschieden hat, hält `specs/decisions/0050-visuelle-gestaltungsrichtung.md` fest, welche Richtung gewonnen hat und warum (auch im Fall „Organic bleibt" — dann als bewusste Bestätigung, nicht als Nicht-Entscheidung). Diese ADR ist der Ort, an den das Akzeptanzkriterium „Entscheidung samt kurzer Begründung festgehalten" zeigt; sie entsteht nach dem Durchklicken, nicht mit dem Code.

### Entfernung (Wegwerf-Checkliste)

Die Entfernung des Labors gehört zum **Folge-Issue** (Übernahme der gewählten Richtung), damit die Vorlage während der Portierung noch als Referenz danebensteht. Vollständig ist sie mit:

1. `frontend/design-lab/` löschen
2. `"design-lab"` aus `include` **und** `"exclude": ["design-lab/guards.test.ts"]` aus `frontend/tsconfig.app.json` entfernen
3. `"design-lab/guards.test.ts"` aus `include` in `frontend/tsconfig.node.json` entfernen
4. `@source not "../design-lab";` samt Kommentar aus `frontend/src/index.css` entfernen
5. den `.gitignore`-Eintrag `frontend/design-lab/photos-local/` entfernen
6. den temporären Abschnitt aus `docs/setup.md` entfernen
7. die Labor-Einträge in `specs/architecture/0002-testkonzept.md` und `0003-securitykonzept.md` auf „entfernt" umschreiben statt löschen — die dort festgehaltenen Muster (Schutzgeländer-Regel, `.gitignore`-Unzulänglichkeit bei privaten Bilddaten) gelten projektweit weiter

Danach ist kein Rückstand im Repo, im Build oder in der CI vorhanden. Ein nach dem Löschen vergessenes `"design-lab"` in `tsconfig.app.json` wäre harmlos — TypeScript meldet nur dann einen Fehler, wenn **überhaupt keine** Eingabedatei gefunden wird, und `"src"` matcht weiterhin.

## UI/UX

### Was verglichen wird — und was in allen fünf Richtungen identisch bleibt

Der Vergleich soll die **Gestaltung** treffen, nicht den Inhalt. Deshalb ist alles Folgende über alle fünf Richtungen hinweg festgeschrieben und darf von keiner Richtungs-CSS verändert werden:

- **Informationsarchitektur und Reihenfolge der Elemente** in allen drei Ansichten (siehe Architektur-Abschnitt, „Die drei Ansichten bilden den heutigen realen Inhalt ab"). Eine Richtung darf ein Element visuell umplatzieren (z.B. eine Badge vom Foto in die Kachel-Fußzeile), aber nichts weglassen, hinzufügen oder in der DOM-Reihenfolge verschieben.
- **Alle Beschriftungstexte** wörtlich: Filter „Alle / Unbewertet / Vorgeschlagen / Favorit / Album-würdig / Verworfen"; „Übernehmen", „Weitere laden", „Vorschlag übernehmen", „Verwerfen", „Zurück"/„Weiter", „Zurück zum Grid"; „Shortcuts: 1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ navigieren"; „Kategorie-Kuratierung", „Deine Auswahl", „Für diese Fotos war kein Bildmotiv sicher bestimmbar.", „Kein weiteres Foto verfügbar"; Schrittnamen „Scan / Ausschuss-Erkennung / Ausschuss-Gate / Kriterien-Bewertung / Kategorie-Kuratierung"; Qualitätsstufen-Namen; „Automatischer Vorschlag: …".
- **Dargestellte Zustände** (aus `fixtures.ts`): dieselben 12 Fotos in derselben Reihenfolge, dieselben Bewertungen/Vorschläge, derselbe Override, dieselben Kriterien-Prozentwerte, dieselbe Schrittzustands-Mischung.
- **Spaltenzahl des Rasters**: 2 Spalten bis 640 px, 3 ab 640 px, 4 ab 768 px — in **jeder** Richtung gleich (wie heute), gemessen jedoch **am Vergleichsrahmen statt am Browserfenster** (Container-Query in `base.css`, nicht Viewport-Media-Query). Grund: die Rahmen im Modus „Nebeneinander" sind bewusst ~390 px breit, das Fenster nicht — mit Viewport-Breakpoints hätte ein Mobilrahmen auf dem Desktop vier Spalten gezeigt und der Vergleich hätte Informationsmenge statt Gestaltung getroffen. Dichte drückt sich über Abstände, Rahmen, Radien und Schriftgrad aus, nicht über die Menge sichtbarer Fotos; sonst verglichen wir Informationsmenge statt Gestaltung.
- **Symbole der Bewertungsstufen**: ★ Favorit, ✓ album-würdig, ✕ aussortiert, ⚙-Präfix für einen unbestätigten Vorschlag, ✎ für den Kategorie-Override, ●●○ für die Qualitätsstufe, ♦ Haken/Schloss im Stepper. Keine Richtung darf ein Symbol durch reine Farbcodierung ersetzen.
- **Keine Bildbehandlung**: `.washed`-artige Filter (Entsättigung/Aufhellung) sind auf den Fotos aller drei Ansichten **verboten** — dort ist die Bildwirkung selbst der Gegenstand der Entscheidung (Design-System, „Bildbehandlung"). Auch die „kreative" Richtung darf keinen Duotone-/Graustufen-Effekt über die Fotos legen.
- **Touch-Ziel ≥ 44 × 44 px** für jedes interaktive Element in jeder Richtung — auch dort, wo die sichtbare Fläche kleiner wirkt (dann über Innenabstand, nicht über eine kleinere Trefferfläche).
- **`prefers-reduced-motion: reduce`** schaltet in jeder Richtung Transform-/Skalierungs-Animationen ab; Farbübergänge dürfen bleiben.

**Nicht Teil des Vergleichs:** Lade-, Fehler- und Leerzustände (Skeleton, `Alert`, „Keine Fotos mit diesem Filter"). Die Ansichten sind Mockups fester Zustände; drei zusätzliche Zustände × 5 Richtungen × 2 Modi würden das Wegwerf-Artefakt verdreifachen, ohne die Richtungen zu unterscheiden — sie folgen mechanisch aus den ohnehin gesetzten Tokens (Skeleton = `--border`-Tinte mit Puls, Fehlerbanner = `--status-failed-tint` + `--status-failed-strong`) und werden erst im Folge-Issue ausgestaltet. **Einzige Ausnahme**, weil sie fester Bestandteil des realen Inhalts ist: die gestrichelte Platzhalterkachel „Kein weiteres Foto verfügbar" in der Kuratierung.

**Zwei zusätzliche Haken im gemeinsamen Markup** (ergänzt den Markup-Vertrag des Architektur-Abschnitts):

- `dl-tile__decor` — leeres `aria-hidden`-Element in jeder Kachel. Nur „verspielt" (Farbkreis hinter der Badge) und „kreativ" (Lime-Randbalken) machen es sichtbar; die übrigen drei setzen `display: none`.
- `dl-meter` — schmaler Wertbalken in jeder Kriterienzeile, **redundant** zum bereits daneben stehenden Prozentwert. Weil er keine eigene Information trägt, darf eine Richtung ihn ausblenden (minimal tut das); der Prozentwert und die Kriterien-Beschriftung dürfen nie entfallen.

---

### Richtung 1 — `organic` · „Organic"

**Charakterisierung (Untertitel im Vergleich):** „Warme Erdtöne, weiche Rundungen, Display-Serife — die heutige Oberfläche."

**Gestalterische These:** Urlaubsfotos gehören ins Wohnzimmer, nicht ins Werkzeug. Die Oberfläche ist ein warmer Papiergrund, auf dem Fotos wie aufgelegte Abzüge liegen; die Software tritt hinter das Familienalbum zurück. Handschrift: Terrakotta und Salbei auf Creme, großzügige Radien, weiche Tiefe.

**Farbwelt:** `organic.css` übernimmt die Werte **1:1** aus `frontend/src/index.css` — den `:root`-Block in `[data-direction='organic'][data-mode='light']`, den `@media (prefers-color-scheme: dark)`-Block (auf dem Hellmodus-Block als Basis) in `[data-direction='organic'][data-mode='dark']`. `var()`-Verweise auf die Tonleitern (`--accent-2-600`, `--neutral-100`, …) entweder mitkopieren oder auf ihren Hexwert auflösen; **keine** Werte „verbessern". Verbindlich ist damit u.a.: `--bg #f5ead8` / `--surface #ebddc5` / `--text #645c50` / `--text-h #201e1d` / `--accent #c67139` / `--accent-strong #8c491a` / `--accent-fg #201e1d` / `--accent-2 #7a8a5e` / Bewertungen Ocker `#c9962c`, Salbei `#728157`, Ziegel `#a8442c`; dunkel `--bg #201e1d` / `--surface #2e2b25` / `--text #c0b6a5` / `--accent #f6a06b` / Bewertungen `#e0b455` / `#aebf92` / `#e08a6f`.

**Schrift:** `--sans: 'Figtree', system-ui, 'Segoe UI', Roboto, sans-serif` · `--heading: 'Caprasimo', Georgia, serif` · `--mono: ui-monospace, Consolas, monospace`. Skala: Fließtext 15 px/1.55; h1 30 px, h2 22 px, h3 18 px, h4 15 px — Überschriften **immer** `font-weight: 400` (Caprasimo hat nur einen Schnitt, alles andere wäre ein synthetischer Fettschnitt), `line-height: 1.12`, `letter-spacing: -0.015em`. Fließtext-Gewichte 400/600/700. Keine Versalien.

**Formsprache:** Radien 16 px (Kacheln/Panels), 28 px (aufgesetzte Ebenen), 32 px (Karten); alle kleinen Bedienelemente — Buttons, Filter, Chips, Eingabefeld, Balken — **volle Pillen**. Abstandsskala 4.4 / 8.8 / 13.2 / 17.6 / 26.4 / 35.2 px. Fläche vor Rahmen: Gruppen werden über getönte `--surface`-Flächen gebildet, Rahmen sind eine schwache Tinte. Tiefe: weicher, warm getönter Schlagschatten hell (`0 3px 10px`), im Dunkelmodus **keine** Schatten, dort Rahmen. Bewegung: 150 ms `ease`, nur Farbe. Fokus: `2px solid var(--accent)`, Offset 2 px. Dichte mittel.

**Die drei Ansichten:** **Grid** — Kacheln als abgerundete Karten mit Schatten; Badge und Info-Trigger sitzen oben rechts auf einem halbtransparenten `--bg`-Kreis mit Backdrop-Blur (Lesbarkeit über beliebigem Foto), Override-Marker oben links; Filter als Pillenreihe, aktiver Filter voll in Terrakotta gefüllt. **Detail** — Bild in 32 px gerundeter Karte; der Vorschlagskasten ist eine große getönte `--accent-bg`-Fläche mit `--accent-border` und 28 px Radius; Bewertungsknöpfe drei volle Pillen, der aktive gefüllt. **Pipeline** — 44 px-Kreise, erledigt in Salbei-Tinte mit Haken, aktuell voll Terrakotta, blockiert mit Schloss; Verbindungslinie 2 px. **Sofort erkennbar:** die Caprasimo-Überschrift über cremefarbenem Grund plus durchgängige Pillenform.

---

### Richtung 2 — `klar` · „Klar"

**Charakterisierung:** „Sachlich, gerahmt, dicht — eine Oberfläche, die sich wie ein sauber geführtes Archiv liest."

**Gestalterische These:** Zwei Menschen sortieren tausende Fotos, oft über Wochen verteilt. Diese Richtung optimiert auf Wiedererkennbarkeit und Übersicht: alles hat einen Rahmen, eine Zeile, eine Spalte. Familienfotos werden ernst genommen wie ein Archivbestand — nicht verspielt, aber auch nicht kalt: die Serifen-Überschrift gibt dem Ganzen den Ton eines gedruckten Registers statt eines Dashboards.

**Farbwelt (Tokens vollständig):**

```css
[data-direction='klar'][data-mode='light'] {
  color-scheme: light;
  --bg: #eef1f5;            --surface: #ffffff;
  --border: #7c8896;        --text: #4a5b6e;        --text-h: #0f1b2a;
  --accent: #1f5c8b;        --accent-strong: #14496f; --accent-fg: #ffffff;
  --accent-bg: color-mix(in srgb, #1f5c8b 10%, transparent);
  --accent-border: color-mix(in srgb, #1f5c8b 45%, transparent);
  --accent-2: #17636b;      --accent-2-strong: #0f4d54;
  --rating-favorite: #a06a00;      --rating-favorite-fg: #ffffff;
  --rating-album-worthy: #2f7a45;  --rating-album-worthy-fg: #ffffff;
  --rating-rejected: #b3261e;      --rating-rejected-fg: #ffffff;
  --status-running: #1f5c8b; --status-success: #2f7a45; --status-success-fg: #ffffff;
  --status-failed: #b3261e;
  --status-running-tint: #dce8f2; --status-running-strong: #14496f;
  --status-success-tint: #dcefe2; --status-success-strong: #1f5a32;
  --status-failed-tint:  #f7dedc; --status-failed-strong:  #8c1d16;
  --status-idle-tint:    #e6eaef; --status-idle-strong:    #43546a;
  --shadow-sm: none; --shadow: none;
  --shadow-lg: 0 10px 28px color-mix(in srgb, #0f1b2a 16%, transparent);
  --sans: system-ui, 'Segoe UI', Roboto, Arial, sans-serif;
  --heading: Georgia, 'Times New Roman', ui-serif, serif;
  --mono: ui-monospace, 'Cascadia Mono', Consolas, monospace;
}
[data-direction='klar'][data-mode='dark'] {
  color-scheme: dark;
  --bg: #12181f;            --surface: #1b232c;
  --border: #697787;        --text: #b3c1cf;        --text-h: #f0f5fa;
  --accent: #7fb4e0;        --accent-strong: #9cc7ec; --accent-fg: #0d1620;
  --accent-bg: color-mix(in srgb, #7fb4e0 16%, transparent);
  --accent-border: color-mix(in srgb, #7fb4e0 50%, transparent);
  --accent-2: #6fc3cd;      --accent-2-strong: #93d6de;
  --rating-favorite: #e0b04a;      --rating-favorite-fg: #12181f;
  --rating-album-worthy: #6fc08a;  --rating-album-worthy-fg: #12181f;
  --rating-rejected: #f08b80;      --rating-rejected-fg: #12181f;
  --status-running: #7fb4e0; --status-success: #6fc08a; --status-success-fg: #12181f;
  --status-failed: #f08b80;
  --status-running-tint: color-mix(in srgb, #7fb4e0 22%, #12181f); --status-running-strong: #b9d8f2;
  --status-success-tint: color-mix(in srgb, #6fc08a 22%, #12181f); --status-success-strong: #a8dcbc;
  --status-failed-tint:  color-mix(in srgb, #f08b80 22%, #12181f); --status-failed-strong:  #f7bdb4;
  --status-idle-tint:    color-mix(in srgb, #8b98a6 22%, #12181f); --status-idle-strong:    #c8d2dc;
  --shadow-sm: none; --shadow: none; --shadow-lg: none;
  --sans: system-ui, 'Segoe UI', Roboto, Arial, sans-serif;
  --heading: Georgia, 'Times New Roman', ui-serif, serif;
  --mono: ui-monospace, 'Cascadia Mono', Consolas, monospace;
}
```

**Schrift:** Fließtext 15 px/1.50, Gewichte 400/600. Überschriften in Georgia 700: h1 26 px/1.2 (`letter-spacing: -0.005em`), h2 20 px, h3 17 px, h4 14 px. Mikro-Labels (Feldbeschriftungen im Datenblock, Kategorie-Kürzel): 11 px, system-ui 600, **Versalien**, `letter-spacing: 0.06em`, in `--text`. Alle Zahlen `font-variant-numeric: tabular-nums`. Zeilenhöhe in Datenlisten 1.4 (kompakt).

**Formsprache:** Radien 2 px (Badges), 4 px (Buttons, Eingabefeld, Kacheln), 6 px (Karten/Panels) — **keine Pillen, keine Kreise**, das ist der bewusste Gegenpol zu organic/verspielt. Abstandsskala 4 / 8 / 12 / 16 / 24 / 32 px, im Raster 8 px Lücke. Rahmen statt Tiefe: jede Gruppe hat einen 1 px `--border`; Ebenen entstehen durch den Flächenwechsel `--surface` auf `--bg`, nicht durch Schatten (`--shadow-sm`/`--shadow` sind `none`; `--shadow-lg` existiert nur für das Popover, im Dunkelmodus auch das nicht). Bewegung: 120 ms, nur Farbe, keine Transforms. Fokus: `2px solid var(--accent)`, Offset 1 px, rechteckig. Dichte: hoch.

**Die drei Ansichten:** **Grid** — die sechs Filter sind **ein zusammenhängender Segmentschalter**: ein 4-px-gerundeter Block mit 1 px Trennlinien zwischen den Segmenten, aktives Segment in Petrol gefüllt mit weißer Schrift; Kacheln mit 1 px Rahmen, Badge als kleines Rechteck oben rechts auf halbtransparentem `--surface`-Feld. **Detail** — der Bewertungsdetail-Block ist eine **echte Tabelle**: linksbündige Versal-Labels, rechtsbündige tabellarische Prozentwerte, 1 px Zeilenlinien zwischen den Kriterien, `dl-meter` als 3 px hoher, eckiger Petrol-Balken unter der Zeile; Blocküberschriften „Qualität"/„Kategorien" mit voller Trennlinie. **Pipeline** — Schritte als **Quadrate (4 px Radius) mit Nummer** auf einer durchgezogenen 1 px-Linie; erledigt = gefüllte Petrol-Fläche mit Haken, aktuell = weiße Fläche mit 2 px Petrol-Rahmen **plus** 3 px Petrol-Unterkante der gesamten klebenden Leiste, blockiert = schwacher Rahmen mit Schloss. **Sofort erkennbar:** der zusammenhängende Segmentschalter und die tabellarischen, rechtsbündigen Werte mit Zeilenlinien.

---

### Richtung 3 — `verspielt` · „Verspielt"

**Charakterisierung:** „Kräftige Farben, dicke Konturen, gestempelte Sticker — Fotosortieren als Bastelbogen."

**Gestalterische These:** Fotos durchsehen soll sich leicht anfühlen. Diese Richtung nimmt die Bewertung als Spiel ernst: große, greifbare Ziele, satte Farben, ein Knopf, der sich beim Drücken sichtbar bewegt. Sie ist die einzige Richtung mit einer **taktilen** Metapher (Sticker/Aufkleber, harter Versatzschatten) statt einer Papier- oder Bildschirmmetapher.

**Farbwelt (Tokens vollständig):**

```css
[data-direction='verspielt'][data-mode='light'] {
  color-scheme: light;
  --bg: #f6f2ff;            --surface: #ffffff;
  --border: #6a4bb0;        --text: #57468a;        --text-h: #2b1055;
  --accent: #7c3aed;        --accent-strong: #6425cf; --accent-fg: #ffffff;
  --accent-bg: color-mix(in srgb, #7c3aed 12%, transparent);
  --accent-border: color-mix(in srgb, #7c3aed 55%, transparent);
  --accent-2: #0e9aa7;      --accent-2-strong: #0a6f78;
  --rating-favorite: #f5a524;      --rating-favorite-fg: #2b1055;
  --rating-album-worthy: #22b455;  --rating-album-worthy-fg: #0a2a14;
  --rating-rejected: #e11d48;      --rating-rejected-fg: #ffffff;
  --status-running: #7c3aed; --status-success: #22b455; --status-success-fg: #0a2a14;
  --status-failed: #e11d48;
  --status-running-tint: #e6dcfb; --status-running-strong: #4c1d95;
  --status-success-tint: #d4f1f4; --status-success-strong: #065c68;
  --status-failed-tint:  #fbdde4; --status-failed-strong:  #8f0f2e;
  --status-idle-tint:    #e9e6f2; --status-idle-strong:    #4b4266;
  --shadow-sm: 2px 2px 0 #6a4bb0; --shadow: 4px 4px 0 #6a4bb0; --shadow-lg: 8px 8px 0 #6a4bb0;
  --sans: ui-rounded, 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;
  --heading: ui-rounded, 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;
  --mono: ui-monospace, Consolas, monospace;
}
[data-direction='verspielt'][data-mode='dark'] {
  color-scheme: dark;
  --bg: #1c1136;            --surface: #2a1c4d;
  --border: #7a5fd0;        --text: #cbbde9;        --text-h: #fbf6ff;
  --accent: #c084fc;        --accent-strong: #d2a6ff; --accent-fg: #1c1136;
  --accent-bg: color-mix(in srgb, #c084fc 20%, transparent);
  --accent-border: color-mix(in srgb, #c084fc 60%, transparent);
  --accent-2: #2dd4e0;      --accent-2-strong: #6fe6ee;
  --rating-favorite: #f7c14a;      --rating-favorite-fg: #1c1136;
  --rating-album-worthy: #4ade80;  --rating-album-worthy-fg: #1c1136;
  --rating-rejected: #ff7a9c;      --rating-rejected-fg: #1c1136;
  --status-running: #c084fc; --status-success: #4ade80; --status-success-fg: #1c1136;
  --status-failed: #ff7a9c;
  --status-running-tint: color-mix(in srgb, #c084fc 24%, #1c1136); --status-running-strong: #dcc0ff;
  --status-success-tint: color-mix(in srgb, #2dd4e0 24%, #1c1136); --status-success-strong: #9beef4;
  --status-failed-tint:  color-mix(in srgb, #ff7a9c 24%, #1c1136); --status-failed-strong:  #ffb8c8;
  --status-idle-tint:    color-mix(in srgb, #9c8fc4 24%, #1c1136); --status-idle-strong:    #d5cce9;
  --shadow-sm: 2px 2px 0 #c084fc; --shadow: 4px 4px 0 #c084fc; --shadow-lg: 8px 8px 0 #c084fc;
  --sans: ui-rounded, 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;
  --heading: ui-rounded, 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;
  --mono: ui-monospace, Consolas, monospace;
}
```

**Schrift:** eine einzige, gerundete Familie für alles. Fließtext 16 px/1.60, Gewicht 500; Überschriften 800: h1 32 px (`letter-spacing: -0.01em`), h2 24 px, h3 19 px, h4 16 px. Button-Beschriftungen 16 px/700. Mikro-Text 12 px/700, `letter-spacing: 0.02em`, **keine Versalien** (Versalien wirken streng — das ist hier der falsche Ton). Zahlen proportional (nicht tabellarisch) — der Zahlenblock soll nicht wie eine Tabelle wirken.

**Formsprache:** Radien 18 px (Kacheln), 26 px (Karten), 34 px (Dialoge/Panels), volle Pillen für Bedienelemente, Bewertungs-Badges als **volle Kreise, 32 px**. Abstandsskala 6 / 12 / 18 / 24 / 36 / 48 px (großzügig). Rahmen **und** Fläche: jede Karte, Kachel und jeder Button trägt eine 2 px `--border`-Kontur zusätzlich zur Füllung. Tiefe: **harter Versatzschatten ohne Weichzeichnung** — das ist die Signatur dieser Richtung und in beiden Modi vorhanden (hell in `--border`, dunkel in `--accent`). Bewegung: 180 ms `cubic-bezier(.34,1.56,.64,1)` (leichter Überschwinger); der gedrückte Zustand verschiebt das Element um `translate(2px, 2px)` und halbiert den Versatzschatten („Knopf gedrückt"). Fokus: `3px solid var(--accent)`, Offset 3 px. Dichte: niedrig (große Elemente, viel Luft).

**Die drei Ansichten:** **Grid** — jede Kachel mit 2 px Kontur und 4 px Versatzschatten; der Bewertungs-Sticker ist ein **32-px-Kreis mit 3 px hellem Ring, der über die Kachelecke hinausragt** (`dl-tile__decor` liefert den Farbkreis darunter); der Override-Marker ist ein zweiter, kleinerer Kreis in der Gegenecke. Filter als große Pillen mit Kontur, aktive Pille gefüllt und um 2 px versetzt („eingedrückt"). **Detail** — das Foto sitzt in einer **Polaroid-Rahmung**: 12 px heller Rand ringsum, 28 px unten, 26 px Radius, harter Versatzschatten; die drei Bewertungsknöpfe sind gleich große Pillen mit Symbol vor dem Wort. **Pipeline** — 52 px-Kreise mit 2 px Kontur und Versatzschatten, aktueller Schritt auf 1.12 skaliert, Verbindung als **dicke gestrichelte Linie**; blockierter Schritt mit Schloss und gestrichelter statt durchgezogener Kontur. **Sofort erkennbar:** der überstehende Sticker-Kreis auf der Kachelecke plus der harte Versatzschatten überall.

---

### Richtung 4 — `minimal` · „Minimal"

**Charakterisierung:** „Weißraum statt Rahmen, Grautöne statt Farbe — Farbe bedeutet hier ausschließlich Zustand."

**Gestalterische These:** Alles, was nicht Foto ist, tritt zurück. Es gibt keine Kartenflächen, keine Schatten, keine Rundungen und keine dekorative Farbe — die einzige Farbe im Bild ist Bewertungs- oder Prozessfarbe, deshalb ist sie sofort auffindbar. Nichts liegt auf einem Foto. Hierarchie entsteht aus Abstand und Laufweite, nicht aus Größe.

**Farbwelt (Tokens vollständig):**

```css
[data-direction='minimal'][data-mode='light'] {
  color-scheme: light;
  --bg: #fbfbfa;            --surface: #ffffff;
  --border: #8b8b84;        --text: #5b5b57;        --text-h: #111111;
  --accent: #1a1a1a;        --accent-strong: #1a1a1a; --accent-fg: #ffffff;
  --accent-bg: color-mix(in srgb, #1a1a1a 6%, transparent);
  --accent-border: color-mix(in srgb, #1a1a1a 32%, transparent);
  --accent-2: #5c6b7d;      --accent-2-strong: #4a5766;
  --rating-favorite: #7d6414;      --rating-favorite-fg: #ffffff;
  --rating-album-worthy: #3d6b4c;  --rating-album-worthy-fg: #ffffff;
  --rating-rejected: #8f3b2f;      --rating-rejected-fg: #ffffff;
  --status-running: #4a5b6e; --status-success: #3d6b4c; --status-success-fg: #ffffff;
  --status-failed: #8f3b2f;
  --status-running-tint: #eceef1; --status-running-strong: #3a4756;
  --status-success-tint: #e8efe9; --status-success-strong: #2f5a3d;
  --status-failed-tint:  #f4e9e7; --status-failed-strong:  #7a3226;
  --status-idle-tint:    #f0f0ee; --status-idle-strong:    #4a4a45;
  --shadow-sm: none; --shadow: none; --shadow-lg: none;
  --sans: system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif;
  --heading: system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif;
  --mono: ui-monospace, 'SF Mono', Consolas, monospace;
}
[data-direction='minimal'][data-mode='dark'] {
  color-scheme: dark;
  --bg: #0e0e0e;            --surface: #171717;
  --border: #6d6d6d;        --text: #a5a5a5;        --text-h: #f5f5f5;
  --accent: #f0f0f0;        --accent-strong: #f0f0f0; --accent-fg: #0e0e0e;
  --accent-bg: color-mix(in srgb, #f0f0f0 10%, transparent);
  --accent-border: color-mix(in srgb, #f0f0f0 38%, transparent);
  --accent-2: #93a3b5;      --accent-2-strong: #b3c0ce;
  --rating-favorite: #cba94a;      --rating-favorite-fg: #0e0e0e;
  --rating-album-worthy: #7fae8c;  --rating-album-worthy-fg: #0e0e0e;
  --rating-rejected: #d08a7c;      --rating-rejected-fg: #0e0e0e;
  --status-running: #8fa3b8; --status-success: #7fae8c; --status-success-fg: #0e0e0e;
  --status-failed: #d08a7c;
  --status-running-tint: color-mix(in srgb, #8fa3b8 20%, #0e0e0e); --status-running-strong: #c3d1df;
  --status-success-tint: color-mix(in srgb, #7fae8c 20%, #0e0e0e); --status-success-strong: #b6d5bf;
  --status-failed-tint:  color-mix(in srgb, #d08a7c 20%, #0e0e0e); --status-failed-strong:  #e8b6ac;
  --status-idle-tint:    color-mix(in srgb, #8a8a85 20%, #0e0e0e); --status-idle-strong:    #ccccc6;
  --shadow-sm: none; --shadow: none; --shadow-lg: none;
  --sans: system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif;
  --heading: system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif;
  --mono: ui-monospace, 'SF Mono', Consolas, monospace;
}
```

**Schrift:** eine Familie, nur die Gewichte 400 und 500 — **nie fett**. Fließtext 13 px/1.70. h1 20 px/400 (`letter-spacing: -0.02em`) — bewusst **kleiner als in jeder anderen Richtung**, h2 16 px/400, h3 13 px/500, h4 11 px/500 Versalien `letter-spacing: 0.16em`. Mikro-Labels 10 px/500, Versalien, `letter-spacing: 0.18em`, in `--text`. Alle Zahlen `font-variant-numeric: tabular-nums`, rechtsbündig.

**Formsprache:** **Radius 0 ausnahmslos** — auch Badges, Buttons, Eingabefeld, Fokusring und Bildkanten. Abstandsskala 4 / 8 / 16 / 24 / 40 / 64 px (weite Sprünge; das Raster nutzt 24 px Lücke). Weder Fläche noch Rahmen als Gruppierungsmittel: Gruppen entstehen durch Weißraum, Trenner sind 1 px `color-mix(in srgb, var(--border) 45%, transparent)` und ausdrücklich dekorativ. Der volle `--border`-Wert ist Bedienelementen vorbehalten (Buttons, Eingabefeld, Segmentgrenzen) — dort 1 px, sichtbar. Tiefe: **keine, in beiden Modi**. Bewegung: 90 ms linear, nur `opacity`/Farbe. Fokus: `1px solid var(--accent)`, Offset 2 px. Dichte: kleine Elemente bei viel Luft (der Gegenpol zu „verspielt", das großzügig **und** groß ist).

**Die drei Ansichten:** **Grid** — Fotos randlos und rahmenlos, 24 px Lücke; **auf dem Foto liegt nichts**: Bewertungs-Badge, Info-Trigger und Override-Marker sitzen als statische, quadratische 18-px-Elemente in einer Fußzeile **unter** dem Bild (sichtbar 18 px, Zeilenhöhe jedoch 44 px: der Info-Trigger darin ist interaktiv, und die projektweite Regel „Touch-Ziel ≥ 44 × 44 px" geht der ursprünglich genannten 20-px-Fußzeile vor — die Untergrenze steht zentral in `base.css`, damit keine Richtung sie unterschreiten kann) (identisches DOM, nur `position: static` statt `absolute`); Filter als Textzeile mit 1 px Unterstrich am aktiven Eintrag statt gefüllter Pillen. **Detail** — das Bild läuft über die volle Breite ohne Rahmen; alle Blöcke sind nur durch Haarlinien und 40 px Luft getrennt; Kriterienzeilen als Label links / Prozentwert rechtsbündig tabellarisch, **`dl-meter` ist ausgeblendet** (die Zahl genügt) — minimal ist die einzige Richtung ohne Wertbalken. **Pipeline** — kein Kreis, keine Fläche: eine 1 px durchgehende Linie mit **8-px-Punkten**; erledigt = ausgefüllter Punkt mit kleinem Haken darüber, aktuell = 12-px-Punkt in `--accent` mit darunterstehendem Label, ausstehend = hohler Punkt, blockiert = hohler Punkt mit 10 px Schloss daneben. Trefferflächen bleiben 44 px (transparenter Innenabstand um den Punkt). **Sofort erkennbar:** die Punktlinie statt der Schrittkreise und die leere, unangetastete Fotofläche.

---

### Richtung 5 — `kreativ` · „Plakat"

**Charakterisierung:** „Beton, Ink-Konturen, Signalfarben und eine Times-Schlagzeile — die Oberfläche als Plakat."

**Gestalterische These:** Ein Urlaub ist ein Ereignis, kein Datensatz. Diese Richtung inszeniert die Sortierung wie ein Plakat: gewaltige Serifen-Schlagzeile, Fließtext in Monospace als Gegenstimme, harte Ink-Konturen ohne jede Rundung, zwei Signalfarben (Vermillon, Säure-Lime), die nur dort auftauchen, wo etwas passiert. Bewertung ist ein **Stempel** — und die stärkste Umdeutung: „aussortiert" ist nicht rot, sondern schwarz durchgestempelt.

**Farbwelt (Tokens vollständig):**

```css
[data-direction='kreativ'][data-mode='light'] {
  color-scheme: light;
  --bg: #e9e7e0;            --surface: #f7f6f2;
  --border: #14120f;        --text: #2f2c26;        --text-h: #14120f;
  --accent: #d63410;        --accent-strong: #b8290a; --accent-fg: #ffffff;
  --accent-bg: color-mix(in srgb, #d63410 14%, transparent);
  --accent-border: #14120f;
  --accent-2: #d7f205;      --accent-2-strong: #4f5c00;
  --rating-favorite: #f2b705;      --rating-favorite-fg: #14120f;
  --rating-album-worthy: #1f7a5a;  --rating-album-worthy-fg: #ffffff;
  --rating-rejected: #14120f;      --rating-rejected-fg: #f7f6f2;
  --status-running: #a9bf00; --status-success: #1f7a5a; --status-success-fg: #ffffff;
  --status-failed: #b8290a;
  --status-running-tint: #eef5c2; --status-running-strong: #4a5600;
  --status-success-tint: #d8ebe3; --status-success-strong: #175c43;
  --status-failed-tint:  #f6ddd6; --status-failed-strong:  #96230a;
  --status-idle-tint:    #dedcd4; --status-idle-strong:    #3a3730;
  --shadow-sm: none; --shadow: none; --shadow-lg: 0 0 0 2px #14120f;
  --sans: ui-monospace, 'Cascadia Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  --heading: 'Times New Roman', Times, ui-serif, Georgia, serif;
  --mono: ui-monospace, 'Cascadia Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
}
[data-direction='kreativ'][data-mode='dark'] {
  color-scheme: dark;
  --bg: #0d0d0b;            --surface: #171712;
  --border: #f2efe6;        --text: #cfcbbd;        --text-h: #ffffff;
  --accent: #ff5a33;        --accent-strong: #ff7a5c; --accent-fg: #0d0d0b;
  --accent-bg: color-mix(in srgb, #ff5a33 18%, transparent);
  --accent-border: #f2efe6;
  --accent-2: #d7f205;      --accent-2-strong: #d7f205;
  --rating-favorite: #f2c14e;      --rating-favorite-fg: #0d0d0b;
  --rating-album-worthy: #4fbf95;  --rating-album-worthy-fg: #0d0d0b;
  --rating-rejected: #f2efe6;      --rating-rejected-fg: #0d0d0b;
  --status-running: #d7f205; --status-success: #4fbf95; --status-success-fg: #0d0d0b;
  --status-failed: #ff7a5c;
  --status-running-tint: color-mix(in srgb, #d7f205 20%, #0d0d0b); --status-running-strong: #d7f205;
  --status-success-tint: color-mix(in srgb, #4fbf95 20%, #0d0d0b); --status-success-strong: #8fe0c2;
  --status-failed-tint:  color-mix(in srgb, #f2efe6 20%, #0d0d0b); --status-failed-strong:  #f2efe6;
  --status-idle-tint:    color-mix(in srgb, #b8b3a5 20%, #0d0d0b); --status-idle-strong:    #d8d4c8;
  --shadow-sm: none; --shadow: none; --shadow-lg: 0 0 0 2px #f2efe6;
  --sans: ui-monospace, 'Cascadia Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  --heading: 'Times New Roman', Times, ui-serif, Georgia, serif;
  --mono: ui-monospace, 'Cascadia Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
}
```

**Schrift:** `--sans` ist hier bewusst mit einer **Monospace-Familie** belegt — die UI-Stimme ist Mono, das ist die Handschrift, nicht ein Versehen. Fließtext/Bedienelemente 13 px/1.60. Überschriften in Times 700: h1 40 px/0.95 (`letter-spacing: -0.03em`), h2 28 px/1.0, h3 20 px **kursiv**, h4 13 px Mono Versalien `letter-spacing: 0.12em`. Werte/Zahlen 13 px Mono 700. Sekundärtext bleibt 13 px (kein Kleinsatz) — die Hierarchie kommt aus dem Kontrast Times/Mono, nicht aus abgestuften Größen.

**Formsprache:** **Radius 0 für alle Flächen** — mit genau **einer** Ausnahme: der Bewertungs-Stempel ist ein voller Kreis (36 px). Er ist der einzige runde Punkt im ganzen System und dadurch unübersehbar. Abstandsskala 4 / 8 / 12 / 20 / 32 / 56 px (asymmetrisch, große Sprünge zwischen Blöcken, enge Zeilen innerhalb). Rahmen statt Fläche: 2 px solide `--border` (Ink hell, Papier dunkel) an Kacheln, Buttons, Kategorieblöcken und Stempeln; Überschriften mit 3 px `--accent`-Unterstreichung. Tiefe: **keine Schatten**; `--shadow-lg` ist ein 2-px-Kontur-Ring statt einer Weichzeichnung. Bewegung: **keine Übergänge** (`transition: none`) — Zustandswechsel sind hart; einzige Bewegung ist ein 2 px Versatz beim gedrückten Zustand. Fokus: `3px solid var(--accent)`, Offset 2 px (Vermillon, **nicht** Lime — Lime trägt allein zu wenig Kontrast). Dichte: mittel-hoch im Text, sehr großzügig um die Überschriften.

**Pflichtregel Lime:** `--accent-2` (`#d7f205`) erreicht auf hellem Grund nur 1.02:1 und darf deshalb **niemals allein eine Fläche begrenzen**. Jede Lime-Fläche trägt zwingend eine 2 px Ink-Kontur (15.11:1) — die Abgrenzung leistet die Kontur, nicht die Farbe. Für Lime **als Text** ist `--accent-2-strong` (`#4f5c00`, 5.93:1) zu verwenden. Im Dunkelmodus entfällt die Einschränkung (Lime auf Schwarz: 15.37:1).

**Die drei Ansichten:** **Grid** — h1 „Fotos" 40 px Times mit 3 px Vermillon-Unterstreichung; die Filterzeile ist Mono in Versalien, aktiver Filter als Ink-Vollton-Block mit Papierschrift, inaktive nur unterstrichen; jede Kachel mit 2 px Ink-Kontur und einem 6 px breiten **Lime-Randbalken an der linken Kante** (`dl-tile__decor`); Bewertungs-Stempel als Kreis mit 2 px Ink-Kontur in der Ecke, „aussortiert" als schwarzer Stempel mit Papier-✕. **Detail** — der Positionszähler wird zur Schlagzeile: „3" in 48 px Times neben einem kleinen Mono-„/12"; das Bild bricht mit negativem Außenabstand über das Textmaß hinaus auf die volle Rahmenbreite und trägt eine 2 px Ink-Kontur; `dl-meter` ist ein 6 px hoher Lime-Balken **mit** Ink-Kontur hinter dem Prozentwert. **Pipeline** — keine Kreise: fünf **rechteckige Blöcke** mit Mono-Nummern, erledigt = Ink-Vollton mit Papier-Haken, aktuell = Lime-Vollton mit Ink-Kontur und Ink-Ziffer, ausstehend = nur Kontur, blockiert = **diagonal schraffierte Fläche** (`repeating-linear-gradient`, 4 px) mit Schloss. **Sofort erkennbar:** Times-Schlagzeile über Mono-Text, plus die schraffierte Sperrfläche im Stepper.

---

### Unterscheidbarkeits-Nachweis

| Achse | organic | klar | verspielt | minimal | kreativ |
|---|---|---|---|---|---|
| **Farbtemperatur Grund** | warm (Creme `#f5ead8`) | kühl (Blaugrau `#eef1f5`) | kühl-bunt (Flieder `#f6f2ff`) | neutral (`#fbfbfa`) | warm-stumpf (Beton `#e9e7e0`) |
| **Sättigung/Farbstrategie** | mittel, gedämpfte Erdtöne | niedrig, ein Petrol-Akzent | **hoch**, mehrere Vollfarben | **minimal** — Farbe nur als Zustand | **extrem** (Signalfarben) auf achromatischem Grund |
| **Akzentfamilie** | Terrakotta + Salbei | Petrol + Teal | Violett + Cyan | Ink + Graublau | Vermillon + Säure-Lime |
| **Grundfläche vs. Rahmen** | Fläche (getönt), Rahmen schwach | Rahmen 1 px **und** Flächenwechsel | Rahmen 2 px **und** Vollfläche | **weder noch** — Weißraum | Rahmen 2 px Ink, Fläche nur als Signal |
| **Radius** | 16/28/32 + Pillen | **2/4/6, keine Pillen** | 18/26/34 + Pillen + Kreise | **0, ausnahmslos** | **0** + genau ein Kreis (Stempel) |
| **Tiefe** | weicher Schlagschatten (hell) | **keine** (nur Popover) | **harter Versatzschatten** | **keine, beide Modi** | keine — stattdessen Kontur-Ring |
| **Dichte** | mittel | **hoch** (8 px Raster, 1.4 Zeilen) | **niedrig**, Elemente groß | **niedrig**, Elemente klein | mittel-hoch im Text, sehr luftig um Überschriften |
| **Schriftcharakter** | Display-Serife (Caprasimo) + geometrische Sans | Serifen-Überschrift (Georgia) + System-Sans, tabellarisch | gerundete Sans durchgehend, 800er Gewicht | System-Sans durchgehend, 400/500, **klein** | **Times-Schlagzeile + Monospace-Fließtext** |
| **h1-Größe/Gewicht** | 30 px/400 | 26 px/700 Serife | 32 px/800 | **20 px/400** | **40 px/700 Times** |
| **Bewegung** | 150 ms Farbe | 120 ms Farbe | 180 ms mit Überschwinger + Versatz | 90 ms, nur Deckkraft | **keine Übergänge** |
| **Signatur-Element** | Pillen auf Creme | Segmentschalter + Zeilenlinien | überstehender Sticker-Kreis | Punktlinie statt Schrittkreise | Ink-Konturen + Schraffur |

**Nächstes Paar und wie es getrennt wurde:** `organic` und `verspielt` liegen auf der Achse *Radius* nah beieinander (beide stark gerundet, beide mit Pillen). Sie sind deshalb auf fünf weiteren Achsen bewusst auseinandergezogen: Farbtemperatur (warm-gedämpft vs. kühl-bunt), Sättigung (mittel vs. hoch), Tiefe (weich verlaufend vs. hart versetzt), Rahmen (nahezu rahmenlos vs. 2 px Kontur überall) und Schrift (Display-Serife vs. gerundete Fett-Sans). Zweitnächstes Paar ist `minimal`/`kreativ` auf der Achse *Radius/Tiefe* (beide 0, beide flach) — getrennt durch Farbstrategie (achromatisch vs. Signalfarben), Rahmenstärke (Haarlinie vs. 2 px Ink), Schriftgrad (h1 20 px vs. 40 px) und Schriftcharakter (System-Sans vs. Times+Mono). Als Nachschärfung gegenüber dem ersten Entwurf wurden `minimal` bewusst **kleine** Elemente bei viel Luft und `kreativ` die Monospace-Fließtextstimme zugewiesen — ohne diese beiden Eingriffe wären die Paare zu nah gewesen.

---

### Barrierefreiheit

**Schwelle (gilt für alle fünf, auch für „kreativ"):** Text/Symbole ≥ 4.5:1 gegen ihren tatsächlichen Untergrund; Fokusring, Umrisse umrandeter Bedienelemente, Stepper-Konturen und Eingabefeld-Rahmen ≥ 3:1 gegen den angrenzenden Grund. Nicht unter diese Regel fallen **gefüllte Statusflächen** (Bewertungs-Chip, gefüllter Stepper-Kreis): dort trägt der Inhalt den Kontrast (Symbol gegen Füllung ≥ 4.5:1), die Füllung selbst muss sich nicht zusätzlich vom Seitengrund abheben.

**Gerechnete Werte der kritischen Paarungen** (sRGB-Kontrastverhältnis, nachgerechnet, nicht geschätzt):

| Paarung | organic | klar | verspielt | minimal | kreativ |
|---|---|---|---|---|---|
| `--text` auf `--bg` (hell/dunkel) | 5.53 / 8.28 | 6.15 / 9.73 | 7.20 / 10.14 | 6.59 / 7.84 | 11.25 / 11.98 |
| `--text` auf `--surface` (hell) | 4.92 | 6.97 | 7.93 | 6.82 | 12.87 |
| `--accent-strong` auf `--bg` (hell) | 5.72 | 8.38 | 7.04 | 16.81 | 5.05 |
| `--accent` auf `--bg` (hell/dunkel, Fokus/Chrome ≥ 3) | 3.03 / 8.03 | 6.26 / 8.08 | 5.17 / 6.72 | 16.81 / 16.94 | 3.89 / 6.26 |
| `--accent-fg` auf `--accent` (hell/dunkel) | 4.60 / 8.03 | 7.09 / 8.25 | 5.70 / 6.72 | 17.40 / 16.94 | 4.82 / 6.26 |
| `--text` auf `--accent-bg`-Tinte (hell/dunkel) | 4.90 / 6.14 | 5.32 / 7.24 | 6.06 / 7.21 | 5.87 / 6.22 | 9.26 / 9.65 |
| Favorit-Symbol auf Favorit-Füllung (hell/dunkel) | 7.88 / 8.56 | 4.61 / 8.91 | 7.87 / 10.72 | 5.67 / 8.56 | 10.28 / 11.59 |
| Album-Symbol auf Album-Füllung (hell/dunkel) | 4.99 / 8.43 | 5.26 / 8.15 | 5.71 / 10.19 | 6.17 / 7.66 | 5.26 / 8.54 |
| Aussortiert-Symbol auf Füllung (hell/dunkel) | 5.00 / 6.35 | 6.54 / 7.41 | 4.70 / 7.20 | 7.41 / 6.99 | 17.29 / 16.92 |
| Status-Pillen (`-strong` auf `-tint`), Minimum über alle vier | 7.06 | 6.40 | 6.46 | 6.77 | 6.39 |
| `--border` gegen `--bg` (hell/dunkel) | **1.37 / 1.69** | 3.19 / 3.90 | 5.87 / 3.70 | 3.31 / 3.73 | 15.11 / 16.92 |

**Bekannte Lücke der Richtung `organic`:** ihr `--border` erreicht nur 1.37:1 (hell) bzw. 1.69:1 (dunkel) — und dieser Token begrenzt in der laufenden App die umrandeten Bedienelemente (`Button variant="outline"`, `border-border`). Damit verfehlt der einzige bereits produktive Kandidat die oben gesetzte 3:1-Schwelle für Umrisse. Der Port wird **trotzdem 1:1 übernommen** und nicht stillschweigend repariert: Organic tritt als das an, was heute ausgeliefert ist, sonst verglichen wir eine Version, die es nicht gibt. Die Lücke ist hier festgehalten, weil sie entscheidungsrelevant ist — gewinnt Organic, gehört ihre Behebung in das Folge-Issue; gewinnt eine andere Richtung, erledigt sich der Punkt mit der Portierung. Die vier neuen Richtungen erfüllen die Schwelle ohne Ausnahme.

**Bewertungszustände nie allein über Farbe:** in **jeder** Richtung tragen die drei Stufen zusätzlich zur Farbe ihr Symbol (★ / ✓ / ✕), ihr vollständiges `aria-label` und die Unterscheidung *voll gefüllt = entschieden* vs. *umrandet + gedämpfte Tinte + ⚙-Präfix = unbestätigter Vorschlag*. Darüber hinaus differenziert jede Richtung die Stufen zusätzlich über die Form ihres Chips (organic: Pille · klar: Rechteck 2 px Radius · verspielt: Kreis mit hellem Ring · minimal: Quadrat ohne Radius, unter dem Bild · kreativ: Kreisstempel mit Ink-Kontur). Keine Richtung darf das Symbol weglassen oder die Voll/Umrandet-Unterscheidung durch eine reine Farbnuance ersetzen. Der Prozess-Status im Stepper ist ebenfalls doppelt codiert (Haken / Ziffer / Schloss / Schraffur zusätzlich zur Farbe).

Ergänzend in allen fünf: `color-scheme` pro Modus gesetzt (nativer Scrollbalken und Zahlenfeld ziehen mit), sichtbarer Fokusring in einer Richtungsfarbe statt des Browser-Blaus, Trefferflächen ≥ 44 px, `prefers-reduced-motion` respektiert.

---

### Bezug zum Design-System-Dokument

`specs/architecture/0004-design-system.md` wird in dieser Spec **nicht** geändert — die Aktualisierung gehört zum Folge-Issue nach der Entscheidung (Out of Scope). Damit der Vergleich aber realistisch ist und nicht an einer geschönten Oberfläche stattfindet, müssen die Prototypen diese bereits dokumentierten wiederkehrenden Muster in **jeder** Richtung abbilden:

- **Auffangkorb-Kategorie mit erklärend dezentem Signal** — der Abschnitt „Nicht erkannt" steht innerhalb seines Clusters **immer zuletzt**, trägt den Erklärtext „Für diese Fotos war kein Bildmotiv sicher bestimmbar." direkt unter der Überschrift und hat **keine Fehler-Optik**: kein Alert-Rahmen, keine `--status-failed`-Farbe, kein Warnicon. Auf Kachelebene ist er identisch zu jeder anderen Kategorie. Das gilt auch für „kreativ" — die Versuchung, hier die Schraffur oder Vermillon einzusetzen, ist genau der Fehler, den das Muster verbietet.
- **Bewertungs-/Vorschlags-Badge** — volle Füllung = von einem Menschen entschieden (Symbol in der tonspezifischen `--rating-*-fg`); Umrandung + 10–12 % Tinte + ⚙-Präfix = offener maschineller Vorschlag (Symbol dann in `--text-h`, nicht in der gegen die Vollfüllung kalibrierten Farbe). Der unbewertete Zustand ist ein neutrales „–" ohne Farbe.
- **Kategorie-Kennzeichnung getrennt von der Bewertung** — Kategorie-Badge in einem neutralen Ton (nie in einer Bewertungsfarbe), 3-Zeichen-Kürzel auf der Kachel, ausgeschriebener Name als Abschnittsüberschrift in der Kuratierung.
- **Feinlabel-Chips visuell klar von der Kategorie unterschieden** — anderer Ton bzw. umrandet statt gefüllt, kleiner, räumlich getrennt (eigene Zeile), **kein** Symbol darauf.
- **Override-Marker** ✎ in der zur Bewertungs-Badge gegenüberliegenden Ecke, auf halbtransparentem `--bg`-Kreis, damit er über jedem Bildinhalt lesbar bleibt.
- **Grobe Qualitäts-Einordnung statt Rohwert** — `●●○` als `aria-hidden`-Dekor plus ausgeschriebener Stufenname als eigentlicher Text; kein Stern (Kollision mit ★), keine Prozess-Status-Farbe.
- **Sticky Stepper mit vier Zuständen** — klebende Leiste, „aktuell" gewinnt gegen „erledigt", blockierter Schritt mit Schloss und Info-Trigger, Farbe nie alleiniges Signal, 44 px Trefferfläche, Skip-Link davor.
- **Info-Popover-Trigger** — der `i`-Knopf ist im Labor ein statisches Element (die Mockups lösen nichts aus), muss aber in jeder Richtung als 44-px-Ziel gestaltet sein, damit sichtbar wird, wie stark er im jeweiligen Bild aufträgt.

Was der Vergleich am Design-System-Dokument **auslösen wird** (Folge-Issue, nicht hier): die Abschnitte „Farbpalette, Schrift und Formsprache" werden durch die Gewinner-Richtung ersetzt, `.claude/skills/design-system/SKILL.md` wird im selben Arbeitsschritt nachgezogen, und die oben festgehaltene Organic-Rahmenlücke wird entweder behoben oder mit der Richtung obsolet.

## Security

Das Labor hat **keine** klassische Angriffsfläche: kein Backend-Zugriff, kein API-Aufruf, keine Auth, kein Secret, keine Persistenz, kein Netzabruf zur Laufzeit. Es ist trotzdem sicherheitsrelevant, aus zwei Gründen: `photos-local/` legt erstmals im Projekt **echte Familienfotos in den Repo-Arbeitsbaum**, und der URL-Zustand der Hülle ist die **einzige Fremdeingabe** im gesamten Artefakt. Beides ist mit den unten stehenden Auflagen beherrschbar; alle Auflagen sind so formuliert, dass die Review-Phase sie nachhalten kann.

### 1. Lokale Fotos: `.gitignore` allein genügt nicht

**Bedrohung:** Familienfotos gelangen ins Repository und damit dauerhaft in die Git-Historie — der Verstoß gegen die Verfassungsregel aus `CLAUDE.md` ist nicht rückholbar, sobald gepusht wurde.

Das vorgesehene Muster ist korrekt und wirkt wie erwartet (in einem Wegwerf-Repo nachgestellt): Der Eintrag ist auf das Repo-Wurzelverzeichnis verankert (er enthält Schrägstriche), der abschließende Schrägstrich beschränkt ihn auf ein Verzeichnis, `git add -A` aus dem Repo-Root übergeht ihn, und ein explizites `git add frontend/design-lab/photos-local/foto.jpg` wird mit Hinweis **abgelehnt**. Da die Datei im Repo-Root liegt und mitversioniert ist, gilt sie auch in jedem Worktree.

Er hat aber zwei nachgewiesene Grenzen:

- **Er schützt nur `photos-local/`.** Ein Foto, das *daneben* landet (`frontend/design-lab/kueste.jpg`), wurde im Nachstellversuch von `git add -A` **kommentarlos gestaged**. Genau dieser Fall ist realistisch: Wer schnell „mal ein echtes Bild reinziehen" will, trifft nicht zwingend den richtigen Unterordner.
- **`git add -f` umgeht ihn**, und auf einen bereits getrackten Pfad wirkt `.gitignore` grundsätzlich nicht mehr.

Prävention allein reicht deshalb nicht — es braucht eine Prüfung, die den **Zustand** feststellt statt die Aktion zu verhindern:

- **A1 — Muster.** Die Root-`.gitignore` erhält exakt eine Zeile: `frontend/design-lab/photos-local/` (mit abschließendem Schrägstrich; ohne führenden Schrägstrich, aber durch die enthaltenen Schrägstriche bereits auf das Root verankert). Keine Negation (`!…`), kein `.gitkeep` — ein Negationseintrag wäre genau die Aufweichung, die hier vermieden werden soll.
- **A2 — Zweite Sicherung als Guard-Test (verbindlich).** `frontend/design-lab/guards.test.ts` prüft, dass `git ls-files -- frontend/design-lab` **keinen** Pfad mit einer Rasterbild-/Video-Endung (`jpg`, `jpeg`, `png`, `heic`, `heif`, `webp`, `tif`, `tiff`, `mp4`, `mov`, Groß-/Kleinschreibung egal) liefert. Bewusst auf `frontend/design-lab` begrenzt, damit die bestehenden `scripts/demo_photos/*.jpg` nicht fälschlich anschlagen. Der Test deckt damit alle drei Lücken auf einmal ab: falsch abgelegte Datei, `git add -f`, bereits getrackter Pfad. Schlägt der `git`-Aufruf fehl, ist der Test **rot, nicht übersprungen** — ein still übersprungener Wächter ist kein Wächter.
- **A3 — Der Guard darf keinen Commit-Druck erzeugen.** Sämtliche Labor-Tests müssen sowohl bei **fehlendem/leerem** `photos-local/` (Normalfall nach jedem Klon, da Git leere Verzeichnisse nicht führt) als auch bei beliebigem Inhalt darin grün sein. Begründung: Ein Test, der ohne lokale Fotos rot ist, erzeugt genau den Anreiz, „Beispielfotos" einzuchecken. Entsprechend muss auch `photoSvg.ts` ein fehlendes Verzeichnis und null Treffer aus `import.meta.glob` klaglos verkraften und auf die generierten Motive zurückfallen.
- **A4 — Kein Rasterbild neu im Repo.** Das Labor bringt kein einziges `.jpg`/`.png` mit; sämtliche Motive entstehen als generierte SVG-Data-URI (bereits so in „Architektur / Umsetzung" festgelegt, hier als prüfbare Auflage wiederholt).
- **A5 — Ein Satz in `docs/setup.md`.** Der ohnehin geplante Labor-Abschnitt hält fest: Der Vite-Dev-Server bindet standardmäßig nur an `localhost`; wer den Vergleich per `npm run dev -- --host` auf dem Handy ansieht (naheliegend, weil die Vergleichsrahmen bewusst Mobilbreite haben), macht damit **auch `photos-local/` für jedes Gerät im selben Netz abrufbar**. Bewusste Entscheidung im Moment des Aufrufs, keine Voreinstellung.

**Bewusst akzeptiertes Restrisiko:** `frontend/Dockerfile` kopiert per `COPY . .` den gesamten Build-Kontext in die Build-Stufe, also auch `photos-local/`, falls dort beim Image-Bau Fotos liegen. Das **ausgelieferte** Image ist nicht betroffen (Multi-Stage, die finale Stufe übernimmt nur `/app/dist` — siehe Auflage B1), betroffen ist nur eine lokale Zwischenschicht im Docker-Cache. Da kein Workflow Images in eine Registry pusht (`.github/workflows/` enthält ausschließlich `ci.yml` und `release-please.yml`), verlassen die Fotos den Rechner nicht, auf dem sie ohnehin liegen — kein zusätzlicher Schutz nötig. Wer den Build dennoch entkoppeln will, legt `frontend/.dockerignore` mit `design-lab/` an; das ist eine Bau-Beschleunigung, keine Sicherheitsmaßnahme.

### 2. Dev-only Zweiteinstieg: Annahme geprüft, trägt

**Bedrohung:** Landete `design-lab/index.html` im Produktions-Bundle, wäre es ein ungeschützter, öffentlich erreichbarer Endpunkt der ausgelieferten App — ohne Auth erreichbar über den nginx-SPA-Fallback und zusätzlich per Service Worker offline vorgehalten.

Die Annahme wurde **nicht geglaubt, sondern nachgebaut**: eine Kopie des Frontends mit der echten `vite.config.ts` (Vite 8.1.5, `vite-plugin-pwa` 1.3.0), ergänzt um ein zusätzliches `design-lab/index.html` mit Sentinel-Zeichenkette und eine Datei in `photos-local/`, per `vite build` gebaut. Ergebnis:

- `dist/` enthält acht Dateien (`index.html`, `assets/index-*.js`, `assets/index-*.css`, `favicon.svg`, `manifest.webmanifest`, `registerSW.js`, `sw.js`, `workbox-*.js`) — **keine** davon aus dem Labor.
- `grep -r "design-lab\|<Sentinel>" dist/` liefert **keinen** Treffer, auch nicht für die Datei aus `photos-local/`.
- Das Precache-Manifest in `dist/sw.js` enthält **exakt sieben** Einträge, keiner aus dem Labor.

Damit sind auch die beiden im Spec-Text vermuteten Umgehungen ausgeschlossen: `workbox.globPatterns` globbt das **Ausgabeverzeichnis** und kann Nichtgebautes prinzipiell nicht erfassen; `includeAssets: ['favicon.svg']` löst gegen `frontend/public/` auf, nicht gegen den Vite-Root. `vite-plugin-pwa` bleibt unangetastet.

- **B1 — Regressionsprüfung (verbindlich, gehört in Schritt 1 der Umsetzungsreihenfolge).** Nach `npm run build` gilt: `find dist -path '*design-lab*'` ist leer, `grep -rl design-lab dist/` ist leer, und das Precache-Manifest in `dist/sw.js` enthält keinen Labor-Eintrag. Nicht einmalig prüfen und abhaken — die Prüfung ist das, was Auflage B2 durchsetzbar macht.
- **B2 — Was nicht passieren darf.** `build.rollupOptions.input` bleibt unkonfiguriert (ein zweiter Input würde das Labor exakt in das oben beschriebene Deploy-Leck ziehen), und kein Teil des Labors wandert nach `frontend/public/` (dessen Inhalt wird unverändert nach `dist/` kopiert und landet über `globPatterns` zusätzlich im Precache).
- **B3 — Die gefährliche Importrichtung.** `guards.test.ts` prüft beide Richtungen der Einbahnstraße, die sicherheitskritische ist aber **`frontend/src/` → `design-lab/`**: Ein einziger solcher Import zöge das Labor in den Modulgraphen des Produktions-Bundles und damit ins Deploy — anders als der umgekehrte Fall, der lediglich unsauber wäre.
- Der Vite-**Dev**-Server serviert das Labor erwartungsgemäß (das ist der Zweck); nginx kann es nicht ausliefern, weil es nie in `dist/` ankommt. `nginx.conf` und `docker-compose.yml` bleiben unberührt, die exponierten Ports ändern sich nicht.

### 3. Eingriffe in Dateien der laufenden Anwendung

Beide Eingriffe sind unkritisch, aber jeweils aus einem anderen Grund als vermutet:

- **`tsconfig.app.json`** kann kein Bündel-Risiko erzeugen: `tsc` läuft mit `noEmit: true`, `include` steuert ausschließlich, **was typgeprüft wird** — was gebündelt wird, entscheidet allein der Rollup-Input (siehe B1/B2). Die einzige reale Folge ist eine Kopplung in die Gegenrichtung: Ein Typfehler im Labor bricht `npm run build` und damit CI. Das ist gewollt (das Wegwerf-Artefakt unterliegt denselben Qualitätstoren) und wird von CI sofort sichtbar gemacht. Entlastend für die Entfernungs-Checkliste: Ein nach dem Löschen vergessenes `"design-lab"` in `include` ist harmlos, weil TypeScript nur dann einen Fehler meldet, wenn **überhaupt keine** Eingabedatei gefunden wird — `"src"` matcht weiterhin.
- **`@source not "../design-lab";`** ist ab Tailwind 4.1 verfügbar, installiert ist `tailwindcss@^4.3.3`. Der Pfad ist relativ zur CSS-Datei und löst korrekt auf `frontend/design-lab` auf. Zusätzlich entlastend: Tailwinds automatische Quellsuche respektiert `.gitignore` (`photos-local/` wäre also ohnehin ausgeschlossen) und scannt `.css`-Dateien nicht als Quellen (die fünf Richtungsdateien wären also ohnehin nicht erfasst). Greift die Direktive wider Erwarten nicht, ist die Folge ausschließlich CSS-Volumen, kein Verhalten — das Labor benutzt keine Tailwind-Klasse.
- **C1 — Prüfbare Auflage statt Vertrauen.** Die generierte Produktiv-CSS muss durch das Labor **unverändert** bleiben. Prüfung: `dist/assets/index-*.css` auf `main` und auf dem Branch vergleichen — der inhaltsbasierte Hash im Dateinamen muss identisch sein. Weicht er ab, greift entweder die Direktive nicht wie gedacht oder das Labor beeinflusst die Produktiv-CSS; beides ist dann vor dem PR zu klären. Fällt die Direktive ersatzlos weg (wie in „Architektur / Umsetzung" vorgesehen), muss dieselbe Prüfung trotzdem bestehen.

### 4. SVG-Data-URIs und die einzige Fremdeingabe

**SVG-Motive: kein Einschleusungspfad.** Ein über `data:image/svg+xml,…` in ein `img`-Element geladenes SVG wird vom Browser skriptlos gerendert: kein `<script>`, kein Abruf externer Ressourcen, kein Zugriff auf das umgebende DOM. Zusammen damit, dass keinerlei Fremdeingabe in die Motive einfließt (alle Werte sind Konstanten aus `photoSvg.ts`/`fixtures.ts`), bleibt kein Angriffspfad. Damit das so bleibt:

- **D1** — Die Motive werden ausschließlich als `src` eines `img`-Elements verwendet; **kein** `dangerouslySetInnerHTML`, kein aus einer Zeichenkette zusammengesetztes Inline-`<svg>`, kein `<object>`/`<embed>`/`<iframe>`. Das ist derselbe Grundsatz, den das Sicherheitskonzept für die laufende App führt — dort trägt er zusätzlich die Auth-Entscheidung aus ADR 0005, weshalb im Repo auch keine Ausnahme „nur im Wegwerf-Code" entstehen soll.
- **D2** — Der SVG-String wird vor dem Einbetten mit `encodeURIComponent` kodiert. Kein Sicherheits-, sondern ein Korrektheitspunkt mit sofortiger Wirkung: Ein unkodiertes `#` aus einer Hex-Farbe beendet die Data-URI und macht das Motiv unsichtbar.

**Der URL-Zustand ist die einzige Fremdeingabe im Labor.** `?dir=…&view=…&mode=…&compare=…` wird per `URLSearchParams` gelesen. Diese Werte stammen definitionsgemäß von außen (geteilter Link, manipulierte Adresszeile), auch wenn im Alltag nur Daniel sie erzeugt.

- **D3** — Jeder URL-Parameter wird **gegen eine feste Positivliste** aufgelöst, bevor er irgendetwas beeinflusst: `dir` gegen die Ids der Richtungs-Registry, `view` gegen die drei Ansichts-Ids, `mode` gegen `light|dark`, `compare` gegen einen booleschen Wert. Trifft ein Wert nicht, gilt der Standard. Ein nicht validierter Wert darf **niemals** in `data-direction`/`data-mode`, in einen Klassennamen, in einen CSS-Selektor oder -Wert, in einen SVG-String oder in `history.replaceState` durchgereicht werden. React maskiert Attributwerte zwar, aber der Umweg über CSS oder eine Selektorkonstruktion tut das nicht — und die Positivliste ist hier ohnehin die natürliche Implementierung, weil aus der Id ein Registry-Eintrag aufgelöst werden muss.

### Abgleich mit dem Sicherheitskonzept

`specs/architecture/0003-securitykonzept.md` **muss ergänzt werden** — nicht wegen einer neuen Angriffsfläche der laufenden Anwendung (die entsteht nicht), sondern weil das Labor das erste Artefakt ist, das absichtlich Familienfotos in den Repo-Arbeitsbaum legt. Genau dafür ist das Konzept der richtige Ort: damit ein späteres Feature das Muster nicht lockerer neu erfindet. Aufzunehmen unter „Angriffsflächen" als eigener Unterabschnitt, in der dort üblichen Form; die Ergänzung gehört in denselben PR wie die Umsetzung, nicht in einen Nachzieh-Commit.

## Teststrategie

### Linie: Schutzgeländer statt Testabdeckung — begründet, nicht erlaubt-weil-bequem

Für das Design-Labor werden **keine Komponenten-, Render- oder Interaktionstests** geschrieben. Stattdessen sichern vier dateilesende Schutzgeländer in `frontend/design-lab/guards.test.ts` genau die Eigenschaften ab, die die Akzeptanzkriterien *strukturell* zusagen. Das ist eine bewusste Abweichung von der Regel „kein PR ohne Tests für die geänderte Funktionalität" aus `CLAUDE.md`, und sie wird hier so begründet:

1. **Es gibt kein Produktionsverhalten, das brechen könnte.** Das Labor hat kein Backend, keine API, keine Persistenz, keinen Router-Eintrag, keinen Build-Output und keinen Nutzer außer Daniel während des Vergleichs. `App.test.tsx` & Co. schützen Verhalten, das nach dem Merge unbeobachtet läuft — hier ist der einzige Nutzungszeitpunkt genau der Moment, in dem ein Mensch auf das Ergebnis schaut.
2. **Das Fehlverhalten ist für seinen einzigen Nutzer im Moment der Nutzung sichtbar.** Genau daran unterscheidet sich das Labor von `scripts/seed-opencloud-demo.py`, für das das Testkonzept (Abschnitt „Lokales Dev-/Demo-Tooling außerhalb des Coverage-Gates") trotz Lage außerhalb des Coverage-Gates eigene Unit-Tests fordert, „sobald es mehr als reine Konfiguration ist": dort läuft Verzweigungslogik (Retry, Idempotenz) unbeaufsichtigt und scheitert *still*. Im Labor ist jede Verzweigung — falscher Modus, falsche Ansicht, nicht wiederhergestellter URL-Zustand — beim Durchklicken unmittelbar zu sehen.
3. **Was das Labor an echtem Risiko trägt, liegt nicht im Labor, sondern an seinen Rändern:** dass es in den Produktions-Build leckt, dass eine Richtung in die anderen vier durchschlägt (dann vergleicht Daniel Artefakte statt Gestaltung), und dass eine Richtung gewinnt, die sich hinterher nicht bauen lässt. Alle drei sind statisch prüfbar — und werden geprüft.
4. **Für die TS-Qualität des Laborcodes greifen die vorhandenen CI-Netze bereits:** `oxlint` läuft ohne Pfadargument über das gesamte Frontend, `tsc -b` erfasst das Labor über die eine Zeile in `tsconfig.app.json`. Beide Schritte sind Pflichtschritte im `frontend`-CI-Job.

Was der `architect` als drei Prüfungen vorgeschlagen hat, wird dabei um **eine vierte** ergänzt (Kontrast-Untergrenze, G4) und in Prüfung 3 um die `var()`-Selbstgenügsamkeit verschärft. Begründung siehe dort: beides schützt nicht das Wegwerf-Artefakt, sondern die **Gültigkeit der Entscheidung**, die auf seiner Grundlage getroffen wird und die App für Jahre prägt.

### Was bewusst nicht getestet wird

- **Rendering der drei Ansichtskomponenten** (`GridView`/`DetailView`/`PipelineView`), die Umschalter der Hülle, der URL-Zustand, `fixtures.ts` und `photoSvg.ts`. Für `photoSvg.ts` gilt zusätzlich: sein Korrektheitsmaßstab ist ein Bildeindruck; ein Snapshot des SVG-Strings würde nur die aktuelle Implementierung festnageln, nicht ihre Eigenschaft. Die für den Vergleich relevante Eigenschaft — *alle fünf Richtungen zeigen dasselbe* — ist strukturell garantiert (eine Fixture-Quelle, drei geteilte Komponenten, ein Seitenaufbau), nicht test-, sondern bauartbedingt.
- **`prefers-reduced-motion`-Konformität je Richtung.** Prüfbar wäre sie (Datei enthält Transform-/Animations-Deklarationen ⇒ Datei enthält einen `reduce`-Block), sie ist aber im Wegwerf-Artefakt folgenlos: Daniel entscheidet nicht danach, und beim Port in die echte App wird die CSS ohnehin neu geschrieben. Bleibt Review-Punkt des `review-ux`-Skills, kein Test.
- **Optische Qualität, „eigene Handschrift", Touch-Zielgrößen, Layout.** Reine UI-Kosmetik ist laut Testkonzept ausdrücklich kein Testgegenstand; Trefferflächen und Layout sind in jsdom mangels Layout-Engine ohnehin nicht messbar.
- **Kein `dist/`-Assertion-Test.** Dass der Produktionsbuild kein Labor-Artefakt enthält, wird einmalig manuell nachgewiesen (siehe „Manuelle Nachweise"); G1 sichert die *Ursache* (kein zweiter Rollup-Input, keine Kante aus `src`/`index.html`), und die ist die prüfbare Eigenschaft. Ein CI-Job, der `dist/` durchsucht, wäre dauerhafte Infrastruktur für ein befristetes Artefakt.

### Die vier Schutzgeländer

Alles in **einer** Datei `frontend/design-lab/guards.test.ts` (~250 Zeilen, davon ~80 der gemeinsame CSS-Scanner), ohne neue Abhängigkeit, ohne Fixture-Dateien. Fünf Richtungs-Ids sind im Test **hart hinterlegt** (`organic`, `klar`, `verspielt`, `minimal`, `kreativ`) — das ist keine Doppelpflege, sondern die wörtliche Wiedergabe von Akzeptanzkriterium 2 und zugleich der Motor der Rot-Grün-Zyklen (siehe „Reihenfolge").

#### G1 — Trennung von der laufenden Anwendung

| | |
|---|---|
| **Liest** | alle Dateien unter `frontend/src/**` (rekursiv, alle Endungen), `frontend/vite.config.ts`, `frontend/index.html`, alle Dateien unter `frontend/design-lab/**` außer `guards.test.ts` |
| **Sichert zu** | (a) Keine Datei unter `src/**` enthält eine Import-Kante ins Labor: kein `from '…design-lab…'`, kein `import('…design-lab…')`, kein `require('…design-lab…')`, kein `@import '…design-lab…'`. (b) `vite.config.ts` und `frontend/index.html` enthalten die Zeichenkette `design-lab` **gar nicht** (kein zweiter Rollup-Input, kein Einstiegs-Link, kein PWA-Precache-Eintrag). (c) Keine Datei unter `design-lab/**` importiert aus `../src` — die Einbahnstraße gilt in beide Richtungen. |
| **Fallstrick** | `frontend/src/index.css` **muss** `design-lab` erwähnen (`@source not "../design-lab";` plus Entfernungshinweis im Kommentar). Ein pauschales Zeichenketten-Verbot über `src/**` wäre also sofort rot. Deshalb: für `src/index.css` gilt die Ausnahme, dass Vorkommen erlaubt sind, solange keines davon eine Import-Kante ist, und der Test verlangt zusätzlich positiv, dass genau eine Zeile `/^\s*@source\s+not\s+['"]\.\.\/design-lab['"];/` matcht — die Direktive ist damit nicht nur erlaubt, sondern eingefordert. Fällt sie laut Architektur-Abschnitt ersatzlos weg, weil die installierte Tailwind-Version sie nicht kennt, wird diese eine Assertion mit Begründung im Test entfernt, nicht das ganze Geländer. |
| **`guards.test.ts` selbst** ist von (c) ausgenommen: es liest `../src/index.css` per `readFileSync` als *Text*. Das ist keine Modulkante und landet in keinem Bundle. Die Ausnahme steht als Kommentar im Test. |
| **Fehlermeldung** | `` `src/pages/PhotoGridPage.tsx:12 importiert aus dem Design-Labor ('../../design-lab/fixtures'). Das Labor ist ein Wegwerf-Artefakt und darf keine Kante in die laufende Anwendung haben (AK "getrennt von der laufenden Anwendung").` `` bzw. `` `frontend/vite.config.ts erwähnt 'design-lab' (Zeile 63). Ein zweiter Rollup-Input zöge das Labor in dist/ und ins nginx-Image.` `` |

#### G2 — Richtungs-Isolation (jede Regel auf ihr eigenes `[data-direction]` gescopt)

| | |
|---|---|
| **Liest** | `frontend/design-lab/directions/*.css`, je Datei über den gemeinsamen Scanner |
| **Sichert zu** | (a) **Jeder** Selektor jeder Regel beginnt mit `[data-direction='<basename>']` — dem Namen der eigenen Datei, nicht irgendeinem. (b) Keine Deklaration außerhalb einer Regel. (c) Verbotene At-Rules: `@import`, `@font-face`, `@media (prefers-color-scheme: …)`. (d) Kein `url(` mit `http:`, `https:` oder `//`. (e) `@keyframes`-Namen beginnen mit der Richtungs-Id. (f) `content:`-Deklarationen nur mit leerem String oder `none`. (g) Regeln, deren Selektor `.dl-grid` enthält, deklarieren kein `grid-template-columns`. |
| **Warum (c)/(d)** | Sie sind der maschinelle Teil des Umsetzbarkeits-Vorbehalts: eine Richtung, die sich eine Schrift oder ein Bild aus dem Netz zieht, verletzt „ohne dass dafür eine neue externe Abhängigkeit nötig wird" und wäre offline nicht durchklickbar. `prefers-color-scheme` ist verboten, weil der Modus im Labor ausschließlich über `data-mode` gesteuert wird — ein Media-Query würde die Ansicht „Beide Modi" unterlaufen. |
| **Warum (e)/(f)/(g)** | Keyframe-Namen sind global und kollidieren zwischen fünf gleichzeitig geladenen Stylesheets. `content:` mit Text würde Inhalt hinzufügen, den die anderen Richtungen nicht zeigen — Verstoß gegen „alle Richtungen zeigen identische Beispielinhalte". `grid-template-columns` auf `.dl-grid` würde die im UI/UX-Abschnitt festgeschriebene Spaltenzahl 2/3/4 verändern; dann verglichen wir Informationsmenge statt Gestaltung. |
| **So erkennt der Scanner eine ungescopte Regel zuverlässig** | Kein Regex über die Datei, sondern ein ~80-zeiliger Zeichen-Scanner: (1) Kommentare werden längentreu durch Leerzeichen ersetzt (`m.replace(/[^\n]/g, ' ')`), damit Zeilennummern und Offsets erhalten bleiben. (2) Zeichenweiser Lauf mit Klammertiefe und einem Stack der offenen At-Rules; der „Prelude" ist der Text seit dem letzten `{`, `}` oder `;` derselben Tiefe. (3) Beginnt ein Prelude mit `@`, ist er At-Rule, kein Selektor — Regeln *innerhalb* von `@media`/`@supports` werden ganz normal weitergeprüft, Zeilen innerhalb von `@keyframes` (`0%`, `from`, `to`) dagegen übersprungen. (4) Selektorlisten werden an Kommata **auf Klammertiefe 0** getrennt, sodass `:is(a, b)`/`:where(…)` nicht zerfallen. (5) Jeder Teil wird nach `trim()` gegen `^\[data-direction=(['"]?)<id>\1\]` geprüft — **am Anfang verankert**, damit `.dl-tile [data-direction='minimal']` (Nachfahre statt Wurzel) nicht durchrutscht. |
| **Nicht Gegenstand von G2** | `shell.css` (`lab-*`-Hülle) und die gemeinsame `base.css` (siehe „Folgen für die Umsetzung") — beide sind absichtlich richtungsneutral. |
| **Fehlermeldung** | `` `directions/minimal.css:47 – Selektor ".dl-tile:hover" ist nicht auf [data-direction='minimal'] gescopt. Fünf Stylesheets sind gleichzeitig geladen; diese Regel schlägt in die anderen vier Richtungen durch und macht den Vergleich ungültig. Erwartet: [data-direction='minimal'] .dl-tile:hover` `` |

#### G3 — Umsetzbarkeits-Vorbehalt: vollständiger Tokensatz in beiden Modi, ohne offene Enden

| | |
|---|---|
| **Liest** | `frontend/src/index.css` (Sollwert) und `frontend/design-lab/directions/*.css` sowie `frontend/design-lab/directions/index.ts` |
| **Ableitung des Pflicht-Tokensatzes (keine Doppelpflege)** | Aus `index.css` werden **beide** `:root`-Blöcke geholt (Hellmodus und der Block im `@media (prefers-color-scheme: dark)` — der Dunkelblock ist ein Delta und deklariert z.B. `--sans`/`--status-running` gar nicht, deshalb ist die **Vereinigung** die richtige Quelle). Aus der Vereinigung werden die Tonleiter-Sprossen entfernt: alles, was auf eine dreistellige Hunderterstufe endet (`/^--.*-[1-9]00$/`, also `--neutral-100…900`, `--accent-100…900`, `--accent-2-100…900`). **Verifiziert:** übrig bleiben exakt **36** Tokens, und zwar genau die im Architektur-Abschnitt aufgezählten (`--bg`, `--surface`, `--border`, `--text`, `--text-h`, die sieben `--accent*`, die sechs `--rating-*`, die zwölf `--status-*`, `--shadow`/`-sm`/`-lg`, `--sans`, `--heading`, `--mono`). Der Test gibt die Zahl aus und behauptet sie nicht — ändert sich `index.css`, ändert sich der Sollwert automatisch mit. |
| **Sichert zu** | (a) Die Basisnamen der `directions/*.css` sind exakt die fünf erwarteten Ids. (b) `directions/index.ts` registriert exakt dieselben fünf Ids — eine Datei ohne Registry-Eintrag wäre im Labor unsichtbar, ein Registry-Eintrag ohne Datei ein Ladefehler. (c) Jede Richtungsdatei enthält einen Block `[data-direction='<id>'][data-mode='light']` **und** einen `…[data-mode='dark']`, und **jeder** der beiden deklariert **alle 36** Tokens. Zusatztokens sind erlaubt, Weglassen nicht. Ein gemeinsamer `[data-direction='<id>']`-Basisblock darf existieren, erfüllt die Pflicht aber nicht — die Ansicht „Beide Modi" zeigt beide Blöcke gleichzeitig, ein vergessener Dunkelwert muss harter Fehler sein statt stiller Vererbung. (d) Jeder Block setzt `color-scheme` passend zum Modus. (e) **`var()`-Selbstgenügsamkeit:** jeder in einer Richtungsdatei per `var(--x)` referenzierte Name ist in derselben Datei auch deklariert. |
| **Warum (e) — der wichtigste Einzelpunkt** | `index.css` definiert Vertragstokens teilweise *über* die Tonleitern: `--status-success: var(--accent-2-600)`, `--status-running-tint: var(--accent-200)`, `--status-idle-strong: var(--neutral-800)`. Die Spec erlaubt beim Portieren von „Organic" ausdrücklich, `var()`-Verweise „mitzukopieren oder auf ihren Hexwert aufzulösen" — **„mitkopieren" ist im Labor aber kaputt**, weil das Labor `index.css` nicht lädt und die Tonleitern dort schlicht nicht existieren. Die betroffenen Tokens wären leer, `organic` — der Referenzkandidat und der Beweis, dass der Markup-Vertrag trägt — hätte still fehlende Statusfarben, und der Vergleich wäre gegen genau die Richtung verzerrt, die als Titelverteidiger antritt. G3(e) macht daraus einen Testfehler. |
| **Fehlermeldung** | `` `directions/verspielt.css: Block [data-direction='verspielt'][data-mode='dark'] definiert 34 von 36 Pflicht-Tokens. Fehlen: --status-idle-tint, --shadow-lg. Der Pflichtsatz stammt aus frontend/src/index.css (Vereinigung beider :root-Bloecke, ohne Tonleitern) - eine Richtung, die ihn nicht vollstaendig fuellt, ist nicht ohne Zusatzarbeit in die App uebernehmbar (AK "Umsetzbarkeits-Vorbehalt").` `` bzw. `` `directions/organic.css:31 – var(--accent-2-600) verweist auf ein Token, das in dieser Datei nicht definiert ist. Das Labor laedt frontend/src/index.css nicht; die Tonleitern existieren dort nicht. Wert auf seinen Hexwert aufloesen.` `` |

#### G4 — Kontrast-Untergrenze

| | |
|---|---|
| **Liest** | dieselben Richtungsdateien, dieselbe bereits vorhandene Token-Tabelle aus G3 |
| **Sichert zu** | Für jede Richtung und jeden Modus erreichen die Text-/Symbolpaarungen ≥ 4.5:1: `--text` und `--text-h` je auf `--bg` und `--surface`, `--accent-fg` auf `--accent`, die drei `--rating-*-fg` auf ihrem `--rating-*`, `--status-success-fg` auf `--status-success`, die vier `--status-*-strong` auf ihrem `--status-*-tint`. Die Paare werden **aus der Namenskonvention abgeleitet** (`X-fg` gehört zu `X`, `-strong` zu `-tint`), nicht aus der Kontrasttabelle des UI/UX-Abschnitts abgeschrieben. |
| **Rechenweg** | sRGB-Relativluminanz nach WCAG, ~25 Zeilen, keine Abhängigkeit. Unterstützt werden `#rgb`/`#rrggbb` und die Form `color-mix(in srgb, <hex> <p>%, <hex>)` (deckt die Dunkelmodus-Tints der Spec ab). **Übersprungen** wird jedes Paar, bei dem ein Operand `transparent`, ein anderer Farbraum oder eine nicht auflösbare Funktion ist — ein Wert über halbtransparentem Grund hat kein statisch bestimmbares Kontrastverhältnis. Der Test zählt die übersprungenen Paare und gibt sie aus, damit „grün" nicht „nichts geprüft" bedeuten kann. |
| **Warum überhaupt, entgegen „reine UI-Kosmetik wird nicht getestet"** | Weil hier nicht Kosmetik geprüft wird, sondern eine im UI/UX-Abschnitt **verbindlich gesetzte Schwelle** („gilt für alle fünf, auch für kreativ"), deren Zahlenwerte dort bereits von Hand ausgerechnet vorliegen — und weil ~350 handgetippte Hexwerte über 10 Blöcke die klassische Übertragungsfehler-Fläche sind. Ein Zahlendreher macht keine Richtung sichtbar hässlich, aber unbenutzbar; wenn eine solche Richtung gewinnt, erbt die echte App den Fehler. Die Kosten sind gering, weil G3 die Token-Tabelle ohnehin schon geparst hat. |
| **Bewusst ausgenommen** | `--border` gegen `--bg` und `--accent` als Chrome (Schwelle 3:1 statt 4.5:1). Der UI/UX-Abschnitt weist für `organic` ausdrücklich **1.37 / 1.69** aus — die bekannte „Organic-Rahmenlücke". `organic.css` übernimmt die heutigen Werte 1:1 und darf sie nicht „verbessern"; eine Assertion darauf würde die Richtung zwingen, unehrlich anzutreten. Diese Lücke bleibt eine dokumentierte Eigenschaft, kein Testfall. |
| **Fehlermeldung** | `` `directions/kreativ.css [data-mode='light']: --rating-album-worthy-fg (#8a8a80) auf --rating-album-worthy (#a3c93a) erreicht 2.31:1, gefordert sind 4.5:1 (Symbol auf gefuellter Flaeche, UI/UX-Abschnitt "Barrierefreiheit"). 3 von 26 Paaren uebersprungen (nicht statisch aufloesbar): …` `` |

### Mechanik: läuft das im bestehenden vitest-Setup? (geprüft)

- **Einsammeln:** `vite.config.ts` überschreibt `test.include` nicht. Die Vorgabe von vitest (`**/*.{test,spec}.?(c|m)[jt]s?(x)` relativ zum Vite-Root `frontend/`, ohne `node_modules`/`dist`) erfasst `design-lab/guards.test.ts` **ohne jede Konfigurationsänderung**. CI ruft `npm run test -- --run` mit `working-directory: frontend` — greift also automatisch.
- **Node-Dateizugriff aus jsdom heraus:** unkritisch. `environment: 'jsdom'` ist keine Browser-Sandbox — vitest läuft im Node-Prozess und jsdom stellt nur DOM-Globals bereit; `node:fs` ist voll verfügbar. Der Test bleibt deshalb in der globalen jsdom-Umgebung. Ein `/** @vitest-environment node */`-Docblock wird bewusst **nicht** gesetzt: er würde `src/setupTests.ts` (Import von `@testing-library/jest-dom/vitest`) in einer Umgebung ohne `document` ausführen und damit ein zweites, unnötiges Risiko eröffnen, um ein nicht vorhandenes zu lösen.
- **Pfadanker:** kein `process.cwd()` (hängt vom Startverzeichnis und vom Pool ab). Verwendet wird `fileURLToPath(import.meta.url)` + `node:path`. **`new URL('./x', import.meta.url)` ist in einem Vite-transformierten Test ausdrücklich nicht brauchbar** — Vite erkennt dieses Literal-Muster und schreibt es in eine Asset-URL um (gemessen: es löste zu `http://localhost:3000/design-lab/…` auf, `readFileSync` scheiterte mit *The URL must be of scheme file*). Für Fehlermeldungen werden lesbare Relativpfade aus den Namen zusammengesetzt.
- **Der eigentliche Stolperstein ist `tsc`, nicht vitest.** `tsconfig.app.json` setzt `"types": ["vite/client"]`; damit ist `@types/node` nicht Teil des Programms und `import { readFileSync } from 'node:fs'` scheitert im CI-Schritt „Type check" (`tsc -b --noEmit`) mit *Cannot find module 'node:fs'*. Auflösung, ohne die App-Typen aufzuweichen:
  - `frontend/tsconfig.node.json`: `"include": ["vite.config.ts", "design-lab/guards.test.ts"]` (dieses Projekt hat bereits `"types": ["node"]`)
  - `frontend/tsconfig.app.json`: `"include": ["src", "design-lab"]` **plus** `"exclude": ["design-lab/guards.test.ts"]`

  Beides je eine Zeile und mit dem Labor wieder zu entfernen. **Verworfene Alternative:** `"types": ["vite/client", "node"]` in `tsconfig.app.json` — eine Zeile weniger, aber sie schiebt Node-Globals (`process`, `Buffer`, Node-`setTimeout` mit `NodeJS.Timeout` statt `number`) in den gesamten `src`-Baum und schwächt für die Lebensdauer des Labors die Typprüfung des Produktivcodes. Für einen Testkomfort nicht vertretbar.
  - Praktische Folge für die Umsetzung: `guards.test.ts` importiert nur `vitest` und `node:fs` und enthält seinen CSS-Scanner **selbst** (keine ausgelagerte `guards.parse.ts`) — eine Hilfsdatei läge im App-Projekt und würde eine Projektgrenze überqueren.
- **Coverage:** unberührt. Das Frontend hat kein Coverage-Gate (bekannte Lücke im Testkonzept), das Backend-Gate `--cov-fail-under=80` wird nicht angefasst, weil kein Python-Code entsteht.
- **Laufzeit:** ~12 gelesene Dateien, kein Rendering — im Rauschen des `frontend`-Jobs.

### Reihenfolge (TDD-konform statt zeremoniell)

Die Schutzgeländer werden **vor Schritt 4** der Umsetzungsreihenfolge geschrieben, nicht als Schritt 7 — sonst schreibt der Test nur ab, was schon da ist:

- G1 wird zusammen mit Schritt 1 (Gerüst) geschrieben. Es ist ehrlicherweise kein Rot-Grün-Test, sondern ein Regressionsgeländer — es steht ab dem ersten Commit scharf und bleibt es.
- G2/G3/G4 werden **vor** Schritt 4 („Organic zuerst") geschrieben und sind dann **rot**: fünf Richtungsdateien werden erwartet, null existieren. Jede fertiggestellte Richtungsdatei nimmt einen Teil der Suite auf Grün; die parametrisierte Suite ist damit der fehlschlagende Test, der jede der fünf Richtungen treibt — inklusive „Dunkelmodus-Block vergessen" und „Token vergessen", den beiden wahrscheinlichsten Fehlern bei je 36 handgetippten Werten pro Block.
- Zwischenzeitliches Rot ist auf dem Feature-Branch erwünscht und muss vor dem PR grün sein.

### Edge Cases, die die Geländer erwischen sollen

- Kommentar mit `{`/`}`/`;` oder ein `/* … */` mitten in einer Selektorliste (längentreue Kommentar-Entfernung, Zeilennummern bleiben korrekt).
- Mehrfachselektor, bei dem nur der **erste** Teil gescopt ist: `[data-direction='klar'] .dl-badge, .dl-chip { … }` — der zweite Teil schlägt in alle fünf Richtungen durch. Klassischer Copy-Paste-Fehler, G2 fängt ihn.
- Komma **innerhalb** von `:is()`/`:where()`/`:not()` — darf die Selektorliste nicht zerteilen (sonst falscher Alarm).
- Regel innerhalb `@media (min-width: 640px)` ohne Scope — wird geprüft, weil der At-Rule-Kontext den Selektor nicht entschuldigt.
- Keyframe-Prozentzeilen innerhalb `@keyframes` — werden **nicht** als ungescopte Selektoren gemeldet, wohl aber der globale Keyframe-Name.
- Falsches `data-direction` in der eigenen Datei (`minimal.css` scopt versehentlich auf `klar`) — G2 prüft gegen den Dateinamen, nicht gegen „irgendein Scope vorhanden".
- Scope als Nachfahre statt als Wurzel: `.dl-tile [data-direction='minimal']`.
- `organic.css` mit mitkopiertem `var(--accent-2-600)`/`var(--neutral-800)` → still leere Tokens (G3e).
- Dunkelmodus-Block existiert, ist aber unvollständig, weil der Entwickler „nur die Farben, die sich ändern" gesetzt hat (G3c).
- Richtungsdatei angelegt, Registry-Eintrag vergessen (oder umgekehrt) → die Richtung fehlt im Vergleich, ohne dass etwas kaputtaussieht (G3b).
- `@import url('https://fonts.googleapis.com/…')` in einer Richtungsdatei — neue externe Abhängigkeit durch die Hintertür, Labor nicht mehr offline durchklickbar (G2c/d).
- `content: "NEU"` oder ein zusätzliches Symbol per `::after` in einer Richtung → ungleiche Beispielinhalte (G2f).
- `grid-template-columns` auf `.dl-grid` in einer Richtung → andere Spaltenzahl, damit vergleicht Daniel Informationsmenge statt Gestaltung (G2g).
- `frontend/index.html`/`vite.config.ts` bekommen doch einen Labor-Eintrag → Deploy-Leck (G1b).
- Zahlendreher in einem Hexwert, der ein Symbol auf gefüllter Fläche unter 4.5:1 drückt (G4).

### Edge Cases, die sie bewusst **nicht** erwischen

- Eine Richtung, die zwar formal gescopt ist, aber gestalterisch wie eine andere aussieht (AK „erkennbar eigene Handschrift") — Sichtprüfung gegen die Achsentabelle.
- Kontrast auf halbtransparenten Tinten (`color-mix(… , transparent)`) und auf Fotos — statisch nicht bestimmbar, übersprungen und im Testausgabetext gezählt.
- `--border`/Chrome-Kontraste (3:1-Familie) — siehe Organic-Rahmenlücke.
- Trefferflächen ≥ 44 px, `prefers-reduced-motion`, Fokusringe, Sticky-Verhalten, Scrollbarkeit der Nebeneinander-Reihe — kein Layout in jsdom, kein E2E im Projekt.
- Ob eine Richtung ein Element visuell umplatziert statt es wegzulassen (UI/UX-Regel „nichts weglassen, hinzufügen oder in der DOM-Reihenfolge verschieben") — ein `display: none` auf einem Pflichtelement bleibt unentdeckt; nur `dl-tile__decor` und `dl-meter` dürfen ausgeblendet werden. Review-Punkt, kein Test (eine Positivliste ausblendbarer Klassen wäre bei jeder Gestaltungsentscheidung zu pflegen und stünde dem Zweck des Labors im Weg).
- Ob `photos-local/` tatsächlich greift (siehe „Folgen für die Umsetzung", Punkt 2).
- Ob das Labor am Ende auch wirklich entfernt wird — das ist die Checkliste des Folge-Issues.

### Verifikation der Akzeptanzkriterien

| AK | maschinell | Sichtprüfung | gar nicht in diesem PR |
|---|---|---|---|
| 1 — drei Ansichten | – | ✓ (Durchklicken aller drei Ansichten × 5 Richtungen) | |
| 2 — fünf Richtungen, Organic gleichwertig | ✓ G3a/b (Dateien + Registry = genau die fünf Ids) | ✓ (dass Organic gleich sorgfältig ausgeführt ist) | |
| 3 — hell und dunkel je Ansicht | ✓ G3c/d (beide Modus-Blöcke vollständig, `color-scheme`) | ✓ (dass beide auch gut aussehen) | |
| 4 — erkennbar eigene Handschrift | – | ✓ (gegen die Achsentabelle) | |
| 5 — identische Beispielinhalte | ✓ strukturell (eine Fixture-Quelle) + G2f (`content:`) | ✓ | |
| 6 — durchklickbar, gemeinsamer Einstieg | – | ✓ (manueller Smoke-Test, siehe unten) | |
| 7 — Wegwerf-Artefakt, getrennt | ✓ G1 (a/b/c) | ✓ (einmaliger `dist/`-Nachweis) | Entfernung selbst: Folge-Issue |
| 8 — Umsetzbarkeits-Vorbehalt | ✓ G3c/e (Tokenvertrag), G4 (Kontrast), G2c/d (keine externe Ressource) | ✓ (Schriftstacks ohne neues `@fontsource`-Paket) | |
| 9 — Daniel hat sich entschieden | – | – | **ja** — wird durch ADR `0050` nach dem Durchklicken erfüllt |

**Für die Review-Phase verbindlich:** AK 9 ist von diesem PR **nicht** erfüllbar und darf nicht als offen bemängelt werden; der PR liefert die Entscheidungs*grundlage*. AK 4 und 6 sind ausdrücklich nicht maschinell prüfbar — ein Review-Finding „fehlender Test für …" ist an diesen beiden Kriterien unbegründet.

### Manuelle Nachweise (im Abschlussbericht zu dokumentieren)

Kein E2E-Setup im Projekt (Testkonzept, „Was bewusst nicht getestet wird") — die folgenden Punkte werden einmalig manuell nachgewiesen und im Abschlussbericht mit Ergebnis genannt:

1. `npm run build` in `frontend/` und danach `grep -r design-lab dist/ ; ls dist/` — kein Labor-Artefakt, kein zusätzlicher Einstieg, `dist/index.html` unverändert erzeugt. **Früh** durchführen (nach Schritt 1), nicht erst am Ende.
2. `npm run dev`, `http://localhost:5173/design-lab/`: alle drei Umschalter, beide Vergleichsmodi, URL-Zustand nach Reload wiederhergestellt, alle 5 × 3 × 2 Kombinationen einmal gesehen.
3. Die App selbst (`http://localhost:5173/`) sieht unverändert aus — die `@source not`-Zeile hat die generierte Tailwind-CSS nicht verändert (vgl. Security-Auflage C1).
4. Stichprobe „Organic gegen die echte App": eine Ansicht im Labor unter `dir=organic` neben derselben Ansicht der laufenden App — sichtbare Abweichungen sind Portierungsfehler in `organic.css`, nicht Gestaltung.

### Folgen für die Umsetzung (aus der Teststrategie abgeleitet)

1. **`frontend/design-lab/base.css`** wird als eigene Datei eingeführt: sie trägt die richtungsinvariante Struktur (Rasterspalten 2/3/4, Bildseitenverhältnisse, Sticky-Verhalten, Reset) mit ungescopten `.dl-*`-Selektoren und ist von G2 ausgenommen. Ohne diese Trennung müsste jede der fünf Richtungen die Struktur wiederholen — mit Driftrisiko genau bei den Eigenschaften, die laut UI/UX-Abschnitt in allen fünf identisch bleiben müssen. Richtungsdateien laden nach `base.css`; ihre `[data-direction]`-Selektoren haben ohnehin die höhere Spezifität.
2. **`photos-local/` meldet seinen Zustand sichtbar:** die Laborhülle zeigt in ihrer neutralen Chrome „N lokale Fotos aktiv" bzw. „keine lokalen Fotos gefunden (`frontend/design-lab/photos-local/`)". Der Glob-Override ist der einzige Mechanismus im Labor, dessen Fehlschlag *still* wäre (Daniel sähe generierte Motive und wüsste nicht, ob seine Dateien am falschen Ort liegen oder der Import nicht greift) — statt eines Tests dafür wird der Zustand selbstdiagnostisch angezeigt.
3. Die **Wegwerf-Checkliste** bekommt zwei zusätzliche Einträge: `"design-lab/guards.test.ts"` aus `tsconfig.node.json` entfernen und `"exclude"` aus `tsconfig.app.json` entfernen.

### Testkonzept

`specs/architecture/0002-testkonzept.md` **muss ergänzt werden** — hier entsteht das erste bewusst weitgehend ungetestete Artefakt mit echtem Anwendungscode, und das Muster „Schutzgeländer statt Testabdeckung" soll für künftige Wegwerf-Artefakte eine Regel sein statt ein Präzedenzfall, auf den man sich beliebig berufen kann. Die Ergänzung (neue Sektion plus zwei Einträge unter „Bekannte Lücken") gehört in denselben PR wie die Umsetzung.

## Entscheidungen

- **Wegwerf-Artefakt als dev-only Vite-Zweiteinstieg** statt eigener App oder zweitem Rollup-Input: erfüllt die geforderte Trennung von der laufenden Anwendung ohne zweites `node_modules` und ohne Deploy-Leck.
- **Gescopte reine CSS-Skins statt Tailwind im Labor:** fünf Token-Sätze müssen gleichzeitig im selben Dokument existieren; Tailwinds `@theme` ist pro Build global und genau einmal vorhanden.
- **Umsetzbarkeits-Vorbehalt als Token-Vertrag operationalisiert:** jede Richtung muss den vollständigen `:root`-Tokensatz aus `frontend/src/index.css` in beiden Modi definieren — dadurch wird „baubar" maschinell prüfbar statt eine Einschätzung.
- **Schriftwahl strikt ohne neue Abhängigkeit** (nur vorhandene Familien + System-/Web-Safe-Stacks): Das Akzeptanzkriterium „ohne dass dafür eine neue externe Abhängigkeit nötig wird" wird wörtlich gelesen. Erkannter Zielkonflikt zum Kriterium „eigene Schriftwahl je Richtung" — „verspielt" und „ganz kreativ" verlieren ohne eigenen Display-Schnitt an Ausdruck. Nachträglich billig änderbar (nur der Schriften-Absatz je Richtungsdatei); eine Lockerung wäre eine bewusste, ADR-pflichtige Erweiterung im Folge-Issue.
- **Keine ADR zur Umsetzung, ADR zum Ergebnis:** `specs/decisions/0050-visuelle-gestaltungsrichtung.md` entsteht nach Daniels Entscheidung und trägt die Begründung.
- **`docs/architecture.md` bleibt unangetastet:** das Labor ist kein Bestandteil des laufenden Systems.
- **Schutzgeländer statt Testabdeckung, bewusst gegen den TDD-Grundsatz aus `CLAUDE.md`:** vier dateilesende Strukturtests statt Komponententests. Zulässig nur, weil alle vier Bedingungen gleichzeitig gelten (kein Produktionsverhalten · Fehlverhalten für den einzigen Nutzer im Moment der Nutzung sichtbar · Lebensdauer endet mit einer benannten Entscheidung · Entfernung als Checkliste festgehalten). Die Geländer entstehen **vor** den Richtungsdateien, sonst wäre es Nachdokumentation statt TDD.
- **Viertes Geländer (Kontrast-Untergrenze) ergänzt** gegenüber dem ursprünglichen Architekturvorschlag: ~350 handgetippte Hexwerte über zehn Modus-Blöcke sind die klassische Zahlendreher-Fläche, und ein Fehler dort macht keine Richtung sichtbar hässlich, sondern unbenutzbar — gewinnt sie, erbt die echte App den Fehler.
- **`var()`-Selbstgenügsamkeit je Richtungsdatei erzwungen:** `frontend/src/index.css` definiert fünf Vertragstokens über Tonleitern (`--status-success: var(--accent-2-600)` u.a.). Das Labor lädt `index.css` nicht — mitkopierte `var()`-Verweise ergäben dort still leere Tokens, ausgerechnet beim Referenzkandidaten `organic`.
- **`base.css` als richtungsneutrale Strukturdatei:** ohne sie müssten alle fünf Richtungen die Struktur wiederholen, mit Driftrisiko genau bei den Eigenschaften, die laut UI/UX-Abschnitt in allen fünf identisch bleiben müssen.
- **`.gitignore` allein sichert `photos-local/` nicht** (empirisch nachgestellt: eine Bilddatei *neben* dem Ordner wird von `git add -A` kommentarlos gestaged; `git add -f` und bereits getrackte Pfade umgehen ihn ohnehin). Deshalb zusätzlich ein zustandsprüfender Guard über `git ls-files`. Der Guard darf ohne lokale Fotos **nicht** rot sein — sonst erzeugt er selbst den Anreiz, Beispielbilder einzuchecken.
- **Drei Akzeptanzkriterien sprachlich geschärft** (AK 4, 8, 9 — Formulierung, keine inhaltliche Änderung), damit die Review-Phase Belegbares einfordert: AK 4 verweist auf die Achsentabelle, AK 8 ersetzt das unprüfbare „wird gar nicht erst vorgelegt" durch den Tokenvertrag, AK 9 hält fest, dass die Entscheidung selbst nicht Bestandteil dieser PR ist.

## Offene Fragen

- Keine blockierenden. Der Schriften-Zielkonflikt (siehe „Entscheidungen") ist unter der wörtlichen Lesart des Akzeptanzkriteriums entschieden und nachträglich revidierbar.

## Out of Scope

- Die **Übernahme** der gewählten Richtung in die echte Anwendung: Design-Tokens, Komponenten, Migration aller Ansichten, Aktualisierung von `specs/architecture/0004-design-system.md` und das Kennzeichnen der überholten Vorgänger-Specs. Eigenes Folge-Issue, das erst nach der Entscheidung geschärft wird.
- Die **Entfernung** des Design-Labors (gehört zum Folge-Issue, damit die Vorlage während der Portierung als Referenz danebensteht).
- Projektliste und Projekt-Anlage als Vergleichsansichten.
- Echte Interaktivität in den Mockups (Filtern, Bewerten, Navigieren lösen bewusst keine Zustandsänderung aus).
