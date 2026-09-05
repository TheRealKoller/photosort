# 0055 - Dark Utility Register: dunkel als einziges Farbschema, Token-Architektur, Kategorie-Farbpalette und Symbolsatz

**Status:** Accepted
**Datum:** 2026-09-04
**Bezug:** [GitHub-Issue #320](https://github.com/TheRealKoller/photosort/issues/320), `specs/features/0320-dark-utility-register.md`, Figma-Board „Photosort Dark" (`photosort-design-system` V1.2)

**Nimmt ausdrücklich zurück (jeweils Akzeptanzkriterien bzw. Entwurfsentscheidungen früherer Feature-Specs, keine ADRs):**
- [`features/0285-organic-design-import.md`](../features/0285-organic-design-import.md) AK 6 „Der Dunkelmodus bleibt erhalten" und AK 7 „Kontrast … in **beiden** Farbschemata", sowie die dortige Abweichung 6 („Dunkelmodus abgeleitet, nicht übernommen … wird nicht aufgegeben"). Beide setzen zwei Farbschemata voraus; ab dieser ADR gibt es nur noch eines. Punkt 1 begründet das.
- [`features/0289-feste-kategorien.md`](../features/0289-feste-kategorien.md) / [`decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md`](./0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md), Umsetzungsschritt 7: die Abschaffung jeder frontendseitigen, nach `category_key` geschlüsselten Tabelle. Für **Anzeigenamen** bleibt sie abgeschafft (die kommen weiterhin zur Laufzeit über `GET /categories`); für **Chip-Farben** wird sie mit Punkt 6 wieder eingeführt. Das ist eine bewusste Teil-Rücknahme, keine stillschweigende Abweichung.

**Berührt außerdem (keine Ablösung):**
- [`decisions/0011-ui-component-library.md`](./0011-ui-component-library.md): Tailwind v4 (CSS-first, `@theme`) + Radix + shadcn-Copy-in-Repo bleiben unverändert die gewählte Grundlage. Diese ADR tauscht Werte und Tokens innerhalb dieser Wahl und ergänzt **eine** neue Laufzeit-Abhängigkeit (Punkt 7); die Bibliothekswahl selbst ändert sie nicht.
- [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) und [`.claude/skills/design-system/SKILL.md`](../../.claude/skills/design-system/SKILL.md): beide werden im selben PR auf den neuen Stand gezogen.

## Kontext

PhotoSorts Kernaufgabe ist das Sichten und Bewerten von Fotos. Die Oberfläche steht dabei unmittelbar neben dem Bild und beeinflusst, wie dessen Farben wahrgenommen werden. Das seit Spec 0285 verwendete Design-System „Organic" setzt einen warmen Creme-Grund (`#f5ead8`); sein Dunkelmodus ist keine neutrale Alternative, sondern eine warm getönte Spiegelung derselben Tonleitern (`#201e1d`/`#2e2b25`). Beide Modi färben das Bild ein, statt hinter es zurückzutreten.

Das Figma-Board „Dark Utility Register" (V1.2) ist der vollständig ausgearbeitete Gegenentwurf: neutral-dunkel, vier Hintergrundstufen, vier Akzente, vier Textstufen, Inter + JetBrains Mono, 8-Punkt-Raster, schwach abgerundet, **kein heller Modus**. Es ist damit — wie schon das Organic-Mockup vor ihm — die eigentliche Spezifikation der Gestaltung. Was das Board **nicht** entscheidet und was diese ADR deshalb entscheidet:

1. ob der helle Modus wegfällt oder als zweites Schema erhalten bleibt,
2. wie die Board-Werte im Code abgelegt werden, ohne dass 91 `.tsx`-Dateien im selben Schritt umgeschrieben werden müssen,
3. wie die sechs Stellen aufgelöst werden, an denen die Board-Werte das Kontrast-Akzeptanzkriterium verfehlen,
4. wie aus fünf Kategorie-Chip-Beispielen des Boards dreizehn werden,
5. wie die zwölf Symbole des Boards ins Produkt kommen (Spec 0285 hatte genau diese Frage als ADR-pflichtig vertagt: „Ein Icon-Set ist eine neue Abhängigkeit und damit ADR-pflichtig").

Diese ADR betrifft **nur das Fundament** (Stufe 1). Die Überarbeitung der einzelnen Ansichten ist Stufe 2 (Issue #321) und ausdrücklich nicht Gegenstand.

Die Punkte 4a, 6 und 7 wurden Daniel im Verfeinerungsablauf zur Entscheidung vorgelegt, weil sie das Erscheinungsbild des Boards spürbar verändern bzw. eine Abhängigkeitsfrage betreffen. Seine Antworten sind eingearbeitet; in zwei von drei Fällen (6 und 7) gegen die Empfehlung des `architect`. Das ist jeweils an Ort und Stelle vermerkt.

## Entscheidung

### 1. Dunkel ist das einzige Farbschema — kein heller Modus, kein Umschalter

`@media (prefers-color-scheme: dark)` entfällt ersatzlos, `color-scheme: light dark` wird zu `color-scheme: dark`. Ein Hell/Dunkel-Umschalter wird **nicht** eingeführt.

Begründung: Ein zweites Farbschema ist kein kostenloser Zusatz, sondern verdoppelt dauerhaft die Kontrastprüfpflicht (0285 AK 7 verlangte genau das) und zwingt jede künftige Farbentscheidung, in zwei Tonwelten gleichzeitig zu funktionieren. Der Nutzen dieser Verdopplung wäre hier negativ: der helle Grund ist für die Kernaufgabe die **schlechtere** Wahl, nicht eine gleichwertige Alternative. Ein Umschalter würde ihn als gleichwertige Option anbieten und damit dem Zweck dieser Umstellung widersprechen.

Bewusst nicht gewählt: die `:root`-Werte behalten und nur den `prefers-color-scheme`-Block auf „dark" festnageln. Das ließe die hellen Werte als toten, jederzeit reaktivierbaren Rest im Repo stehen — genau das, was das Akzeptanzkriterium („ein heller Grund existiert nicht mehr") ausschließt.

**Vollständigkeit über die CSS hinaus** (sonst blitzt der alte Zustand beim PWA-Start oder vor dem ersten Paint auf): `frontend/index.html` (`<meta name="theme-color">`, heute `#111111`; zusätzlich `<meta name="color-scheme" content="dark">`), `frontend/vite.config.ts` (`manifest.theme_color`, heute `#c67139`; `manifest.background_color`, heute `#f5ead8`) und die Grundfläche auf `html` (nicht nur `body`, sonst bleibt der Überroll-Bereich hell).

### 2. Die Token-Zweiteilung bleibt — Werte werden getauscht, Namen so weit wie möglich nicht

Die heutige Naht bleibt unverändert: **Rohwerte in `:root`, Zuordnung zu Utilities im `@theme`-Block** (Tailwind v4, CSS-first, kein `tailwind.config.js`). Sie ist bereits beim Organic-Import der Grund gewesen, dass der Großteil der Komponenten ohne Änderung mitzog; dasselbe gilt hier.

Konkret: Wo ein Board-Token dieselbe semantische Rolle hat wie ein bestehendes, **behält das bestehende Token seinen Namen und bekommt nur einen neuen Wert**. Das trägt die 91 `.tsx`-Dateien ohne Anfassen über die Umstellung:

| Bestehendes Token | Neuer Wert (Board) | Aufrufstellen heute |
|---|---|---|
| `--bg` | `#0B0C10` (Hintergrund) | `bg-bg` (10) |
| `--surface` | `#14161F` (Oberfläche) | `bg-surface` (5) |
| `--text-h` | `#FFFFFF` (Text Primär) | `text-text-h` (55) |
| `--text` | `#A0A5B5` (Text Sekundär) | `text-text` (125) |
| `--border` | `#2A2E3D` (Rahmen, **nur dekorativ**, s. 4c) | `border-border` (26), `bg-border` (20) |
| `--accent` / `--accent-strong` | beide `#FFB000` (Akzent Primär) | `bg-accent`, `ring-accent`, `text-accent-strong` |
| `--accent-fg` | `#0B0C10` (10,67:1) | `text-accent-fg` (6) |
| `--accent-2` / `--accent-2-strong` | beide `#00E676` (Album-würdig) | `bg-accent-2` |
| `--rating-favorite` | `#FFB000` | |
| `--rating-album-worthy` | `#00E676` | |
| `--rating-rejected` | `#FF3D00` | |
| `--rating-*-fg` | alle drei `#0B0C10` (s. 4e) | |
| `--status-running` / `-success` / `-failed` | `#FFB000` / `#00E676` / `#FF3D00` | |

`--accent-strong` und `--accent-2-strong` zeigen auf denselben Wert wie `--accent`/`--accent-2` — auf dunklem Grund trägt der Akzent selbst genug Kontrast (7,67–10,67:1), eine getrennte Textstufe ist nicht nötig. Das ist exakt die Konstruktion, die der bestehende Dunkelmodus schon heute verwendet. Die Namen bleiben trotzdem erhalten, damit die Aufrufstellen unverändert bleiben und eine spätere Wiederauftrennung möglich ist, ohne sie anzufassen.

**Neu hinzu** kommen genau die Rollen, für die es heute kein Token gibt: `--elevated` (`#1E2230`), `--overlay` (`#262B3D`), `--text-muted`, `--text-disabled` (`#3E4252`), `--border-control` (4c), `--info` (`#00E5FF`), `--danger-text` (4d) sowie die 26 Kategorie-Chip-Tokens (Punkt 6).

**Ersatzlos gestrichen** (jeweils mit der Zahl der tatsächlich betroffenen Aufrufstellen):

- Die drei Tonleitern `--neutral-100…900`, `--accent-100…900`, `--accent-2-100…900` (27 Tokens). Sie sind eine Konstruktion des Organic-Systems (OKLCH auf einer gemeinsamen Helligkeitsskala); das Board kennt keine Tonleitern. 27 dunkle Stufen zu erfinden, die im Board nirgends vorkommen, wäre eine Erfindung, keine Übernahme. Tatsächlich betroffen: **6 Zeilen in 2 Dateien** (`pages/ProjectListPage.tsx`, `components/Stepper.tsx`).
- `--shadow-sm` / `--shadow` / `--shadow-lg` und die Utilities `shadow-warm*`. Der bestehende Dunkelmodus setzt sie bereits auf `none`, das Board arbeitet durchgehend flach — Tiefe entsteht über die vier Flächenstufen und den Rahmen. Ein Token, dessen einziger Wert `none` ist, ist kein Token. **4 Aufrufstellen.**
- `--heading` und die Utility `font-heading` (Caprasimo). Das Board hat keine Display-Schrift; Überschriften sind Inter in unterschiedlichen Schnitten. **2 Aufrufstellen.**
- `--spacing-o1…o8` (Organic-Dichte 1,10×). **0 Aufrufstellen.**
- Die Utility `.washed` (Fotos entsättigen/aufhellen, damit sie in die warme Fläche zurücktreten). Ein neutral-dunkler Grund braucht das nicht — das Zurücktreten der Oberfläche hinter das Bild ist gerade der Zweck der Umstellung. **0 Aufrufstellen.**

Diese Liste ist vollständig: eine Suche über alle deklarierten Tokens gegen alle `.tsx`/`.ts`-Dateien ist Teil des Umsetzungsschritts, damit keine verwaiste Referenz übrig bleibt. Der Build deckt das nicht ab — eine unbekannte Tailwind-Utility ist kein Fehler, sondern erzeugt still keine Regel.

### 3. Typografie: Inter + JetBrains Mono, self-gehostet über `@fontsource`

`@fontsource/caprasimo` und `@fontsource/figtree` entfallen, `@fontsource/inter` (400/500/600/700) und `@fontsource/jetbrains-mono` (400) kommen hinzu. Die Einbindungsart bleibt unverändert und aus unverändert gültigem Grund: PhotoSort ist eine PWA mit Offline-Anspruch, ein Google-Fonts-CDN-Link wäre offline ein Fehlschlag und zusätzlich ein Abfluss von Nutzungsdaten an einen Dritten (0285 Abweichung 1; die `woff2`-Ergänzung in `vite.config.ts`s `globPatterns` bleibt dadurch weiterhin nötig und richtig).

Die Größenstufen des Boards werden auf Tailwinds bestehende Skala gelegt, statt eine zweite, parallele Skala danebenzustellen — sonst wären die 133 vorhandenen `text-sm`/`text-xs`-Aufrufstellen dauerhaft außerhalb des Systems:

| Utility | bisher | neu (Board) |
|---|---|---|
| `text-xs` | 12px | 12px — Beschriftung, Semi-Bold, uppercase (unverändert) |
| `text-sm` | 14px | 14px — Komponententext / Monospace-Daten (unverändert) |
| `text-base` | 16px | 16px — Fließtext Klein (unverändert) |
| `text-lg` | 18px | **20px** — Fließtext |
| `text-xl` | 20px | **24px** — Überschrift 3 |
| `text-2xl` | 24px | **40px** — Überschrift 2 |
| `text-3xl` | 30px | **64px** — Überschrift 1 |
| `text-4xl` und größer | 36px+ | entfallen (das Board hat keine weiteren Stufen) |

Die drei unveränderten Stufen tragen 121 der 145 Aufrufstellen. Der einzige spürbare Sprung ist `text-2xl` (24 → 40px, 11 Stellen) — diese elf werden im Umsetzungsschritt einzeln durchgesehen: echte Seitenüberschriften bleiben auf `text-2xl`, Abschnittsüberschriften wandern auf `text-xl` (24px, ihre heutige Größe). Das ist eine benannte, abzählbare Nacharbeit, keine Überarbeitung der Ansichten.

### 4. Auflösung der sechs Konflikte zwischen Board-Werten und dem Kontrast-Akzeptanzkriterium

Das Akzeptanzkriterium verlangt: *jede Text-/Symbolfarbe erreicht gegen ihren tatsächlichen Untergrund WCAG-AA (4,5:1 Fließtext, 3:1 grafisch und Bedienelement-Umrisse)*. Für die Zielgrößen der Bedienelemente hat Daniel bereits entschieden: *wo das Board der Untergrenze widerspricht, gilt die Untergrenze*. **Dieselbe Logik wird hier auf den Kontrast übertragen** — mit demselben Argument und einer zusätzlichen Verschärfung: eine zu kleine Zielfläche ist umständlich, ein zu schwacher Kontrast ist auf einem Gerät bei ungünstigem Umgebungslicht schlicht nicht lesbar, und das Board ist ein Desktop-Entwurf an einem kalibrierten Monitor.

Leitlinie für die Art der Abweichung, übernommen aus Spec 0285 (Abweichungen 2 und 3): **Flächenfarben des Boards bleiben unangetastet, korrigiert wird die Schrift- oder Linienfarbe darauf.** Die Flächen tragen das Farbbild der Oberfläche; sie zu verschieben verfehlte die Übernahme in ihrem sichtbarsten Merkmal.

#### 4a. Text Muted `#62677A` — verfehlt 4,5:1 auf allen vier Flächen (3,48 / 3,21 / 2,82 / 2,50)

**Entscheidung Daniels (Empfehlung gefolgt): aufhellen auf `#8D92A4`** — 6,31 / 5,82 / 5,11 / 4,53, AA auf allen vier Flächen. Es ist der dunkelste Wert derselben Farbfamilie, der das noch schafft; die „gedämpfte" Wirkung bleibt damit so weit erhalten wie möglich.

Begründung: Das Board setzt Muted für echten Text ein (Panel-Überschriften, Tabellenköpfe, Karten-Status „Neu", inaktive Stepper-Stufe), und das Akzeptanzkriterium fordert ausdrücklich **vier** Textstufen. Die Alternative, den Board-Hexwert zu behalten und Muted zur reinen Grafikfarbe zu erklären, hätte jede dieser Stellen auf „Text Sekundär" zurückfallen lassen — die vierte Textstufe wäre faktisch weg, das Akzeptanzkriterium also auf anderem Weg verfehlt. Ein Mittelweg (`#828798`, 5,46 / 5,04 / 4,42 / 3,92) hielte AA nur auf den beiden unteren Flächen und stünde und fiele mit der Regel „Muted-Text nie auf Karten oder in Modalen" — eine Regel, die im Alltag gebrochen wird, ohne dass es auffällt.

**Bekannte, ausdrücklich akzeptierte Einschränkung:** Der Abstand zu „Text Sekundär" (`#A0A5B5`) ist klein; die Textstufen 2 und 3 sind nebeneinander nur schwach unterscheidbar. Sie tragen ihre Unterscheidung deshalb praktisch über die Verwendung (Fließtext vs. Metadaten/Hotkeys), nicht über die Wahrnehmung. Das ist als Einschränkung im Design-System-Dokument zu führen, damit spätere Arbeit sich nicht auf einen sichtbaren Unterschied verlässt, den es nicht gibt.

#### 4b. Text Disabled `#3E4252` — unter 3:1 auf allen vier Flächen (1,96 / 1,81 / 1,59 / 1,41)

**Board-Wert bleibt unverändert.** WCAG 1.4.3 (und 1.4.11) nehmen inaktive Bedienelemente ausdrücklich aus. Die Ausnahme wird an eine harte Regel gebunden: `--text-disabled` ist **ausschließlich** auf Elementen mit `disabled`/`aria-disabled` zulässig, nie auf Inhaltstext.

Damit gilt sie **nicht** für die eine Board-Stelle, an der Text Disabled Inhalt trägt: den durchgestrichenen Dateinamen der aussortierten Foto-Karte. Dort wird `--text-muted` verwendet — der Dateiname ist Inhalt, den man auch im aussortierten Zustand lesen können muss.

Aus demselben Grund entfällt die Board-Angabe **„ganze Karte Deckkraft 40 %"** für die aussortierte Karte. Deckkraft auf einem Container ist nicht kontrastprüfbar (dasselbe Argument, mit dem 0285 Abweichung 5 den Sekundärtext von `opacity` auf einen eigenen Ton umgestellt hat) und würde Badge, Symbol und Dateiname gemeinsam unter jede Schwelle drücken. Das gewollte Zurücktreten wird dort erzeugt, wo es nichts kostet: gedämpfte Bildfläche (Deckkraft/Filter **nur** auf dem Vorschaubild), Dateiname in `--text-muted` mit Durchstreichung, Badge und Symbol bei vollem Kontrast. Der Zustand bleibt damit dreifach codiert (Textbadge, eigenes Symbol, Durchstreichung) und ohne Farbwahrnehmung unterscheidbar.

#### 4c. Rahmen `#2A2E3D` — 1,04–1,45:1, trägt im Board trotzdem Sekundär-Button und Eingabefeld

**Das Rahmen-Token wird in zwei Rollen aufgeteilt:**

- `--border` = `#2A2E3D` (Board-Wert, unverändert): reine Trenn-/Dekorlinie — Panel-Kanten, Tabellenlinien, Karten-Umriss, Modal-Umriss. Für Dekoration gilt keine Kontrastschwelle.
- `--border-control` = **`#727891`** (4,48 / 4,13 / 3,63 / 3,22 — ≥3:1 auf allen vier Flächen, gleiche Farbfamilie und Sättigung wie die neutrale Textleiter des Boards): der sichtbare Umriss eines Bedienelements — Sekundär-Button, Eingabefeld (Normalzustand), Kontrollkästchen, Schalter, Navigationselement.

Begründung: Für Bedienelemente fordert das Akzeptanzkriterium 3:1 auf den Umriss. Beim Sekundär-Button ist der Umriss auch tatsächlich das einzige Identifikationsmerkmal — seine Fläche (`#262B3D`) hebt sich von der Oberfläche (`#14161F`) nur mit 1,28:1 ab, in einem Modal (`#262B3D`) überhaupt nicht. Ohne belastbaren Umriss wäre der Button dort unsichtbar. `--border-control` ist auf die **hellste** Fläche kalibriert, auf der ein Bedienelement stehen kann (Overlay), damit dieselbe Linie überall trägt und keine flächenabhängige Sonderregel entsteht.

Bewusst nicht gewählt: die Fläche des Sekundär-Buttons aufhellen statt den Rahmen. Das hätte eine der vier Board-Flächenstufen verschoben und die Leitlinie aus Punkt 4 verletzt.

#### 4d. Aussortiert `#FF3D00` als Textfarbe — 4,46 auf „Erhöht", 3,96 auf „Overlay"

**Aufgeteilt in zwei Tokens, exakt nach dem Muster `--accent`/`--accent-strong` aus 0285 (Abweichung 2):**

- `--danger` = `#FF3D00` (Board-Wert, unverändert): Flächen, Rahmen, Symbole, Fehlerrand am Eingabefeld. Erreicht auf allen vier Flächen ≥3:1 (5,51 / 5,08 / 4,46 / 3,96) und ist damit für grafische Verwendung durchgehend zulässig.
- `--danger-text` = **`#FF5A26`** (6,28 / 5,79 / 5,08 / 4,51): Text in Fließtextgröße in der Aussortiert-Farbe — Fehlermeldung unter einem Eingabefeld, Beschriftung der Status-Pille, Meldungstext.

Kein einziger Board-Flächenwert ändert sich dadurch; der Unterschied zwischen den beiden Rot-Tönen ist nebeneinander kaum wahrnehmbar. `--rating-rejected` bleibt der Board-Wert (Fläche); `--rating-rejected` als **Text** ist keine gültige Verwendung mehr.

#### 4e. Weiße Badge-Schrift auf Aussortiert `#FF3D00` — 3,55

**Dunkle Tinte `#0B0C10` statt Weiß** (5,51:1). Das Board setzt für die Badges FAVORIT und ALBUM bereits dunkle Tinte ein; AUSGESONDERT ist die einzige Ausnahme. Die Korrektur macht die vier Badges also **einheitlicher**, nicht uneinheitlicher, ändert nur die Schriftfarbe und lässt die Fläche exakt. Dieselbe Richtung wie 0285 Abweichung 3.

Damit tragen alle drei Bewertungs-Vordergründe (`--rating-*-fg`) denselben Wert `#0B0C10`. Sie bleiben trotzdem drei getrennte Tokens: dass eine gemeinsame Tinte auf allen drei Tönen hält, ist beim Organic-System nachweislich nicht der Fall gewesen (0285 Abweichung 4) und wäre eine Eigenschaft dieser konkreten Palette, keine Regel — ein Ton-Wechsel würde die Kopplung sonst still brechen. Der bestehende Regressionstest in `badge.test.tsx` hält genau das fest und bleibt gültig.

#### 4f. Kategorie-Chip „Gebäude" `#FF007F` auf `#3B1F43` — 3,80

Sechster Konflikt, in der Board-Referenz nicht gelistet, beim Nachrechnen der fünf Chip-Paare aufgefallen. Die Chip-Beschriftung ist Inter Semi-Bold 12px, also kein Large Text — 4,5:1 gilt. Die übrigen vier Board-Paare halten (6,81 / 8,39 / 5,68 / 7,27).

**Korrektur: Schriftfarbe auf `#FF44A1`** (4,51). Wieder nur die Schrift, die Fläche `#3B1F43` bleibt der Board-Wert.

### 5. Akzent und Favorit teilen sich einen Farbwert, aber nicht ihren Tokennamen

Das Board benennt `#FFB000` gleichzeitig als „Auswahl & Favoriten". Das Design-System hält bisher fest, Akzent und Bewertungsfarben getrennt zu halten, „damit Aktion und Status nicht verwechselbar sind". Das Board hebt diese Trennung auf.

**Entscheidung:** Der Board-Wert gilt (`--accent` und `--rating-favorite` tragen beide `#FFB000`), die **Token-Namen bleiben getrennt**. Die semantische Unterscheidung überlebt damit im Code und ist später wieder auftrennbar, ohne eine einzige Aufrufstelle anzufassen. Die Regel „getrennt halten" wird im Design-System-Dokument als **zurückgenommen** vermerkt, nicht stillschweigend übergangen — die Unterscheidbarkeit trägt beim Favorit ohnehin zusätzlich das `star`-Symbol und der Textbadge.

Aus demselben Grund werden die Status-Pillen (`StatusTag`) auf die Toast-Konstruktion des Boards umgestellt, statt eigene Tint-/Strong-Paare zu erfinden, die das Board nicht kennt: Fläche `--elevated` (`#1E2230`), farbiger 1px-Rand, farbige Beschriftung. Alle vier Zustände halten damit AA auf `#1E2230` (Akzent 8,64 / Album 9,48 / `--danger-text` 5,08 / `--text` 6,44). Die acht Tokens `--status-*-tint`/`--status-*-strong` werden darauf umdefiniert statt gestrichen — ihre Aufrufstellen bleiben unverändert.

### 6. Kategorie-Chips: dreizehn eigene Farbpaare

**Entscheidung Daniels, gegen die Empfehlung des `architect`** (der ein einziges neutrales Paar für alle dreizehn vorgeschlagen hatte, um die unter „Bewusst getragene Kollision" beschriebene Nähe zu vermeiden und um keine frontendseitige Farbtabelle einzuführen). Entschieden ist: die fünf Board-Paare bleiben, acht werden abgeleitet.

#### 6a. Die dreizehn Paare

Ableitungsregel, aus den fünf Board-Paaren gemessen und für die abgeleiteten angewandt, damit der Satz als **eine** Familie liest: Fläche = derselbe Farbton bei **S 46 % / L 18 %** (Board-Bandbreite: S 37–59 %, L 16–20 %), Schrift = derselbe Farbton bei **S 100 %**, Helligkeit von 42 % aufwärts so weit angehoben, bis mindestens 4,75:1 erreicht ist (kleiner Sicherheitsabstand über der 4,5-Schwelle, damit ein späteres Nachjustieren der Fläche nicht sofort durch die Schwelle fällt).

| Kategorie (`display_name`) | Fläche | Schrift | Kontrast | Herkunft |
|---|---|---|---|---|
| Menschen | `#4D3814` | `#FFC107` | 6,81 | Board |
| Tier | `#163E3C` | `#00F5D4` | 8,39 | Board |
| Pflanze | `#194321` | `#00D627` | 5,71 | abgeleitet (H 131) |
| Landschaft | `#1F2B49` | `#00B4D8` | 5,68 | Board |
| Gebäude & Bauwerk | `#3B1F43` | `#FF44A1` | 4,51 | Board, Schrift korrigiert (4f) |
| Innenraum | `#1E1943` | `#8C7AFF` | 4,97 | abgeleitet (H 248) |
| Essen & Trinken | `#143C22` | `#70E000` | 7,27 | Board |
| Fahrzeug | `#192743` | `#578FFF` | 4,80 | abgeleitet (H 220) |
| Gegenstand | `#43191C` | `#FF5260` | 4,75 | abgeleitet (H 355) |
| Dokument & Screenshot | `#424319` | `#CFD600` | 6,48 | abgeleitet (H 62) |
| Kunst & Kreatives | `#431940` | `#FF2EF1` | 4,76 | abgeleitet (H 304) |
| Sport & Aktivität | `#321943` | `#C266FF` | 4,90 | abgeleitet (H 276) |
| **Nicht erkannt** | `#262B3D` | `#A0A5B5` | 5,71 | **neutral, keine eigene Farbe** |

Alle dreizehn erreichen ≥ 4,5:1 (nachgerechnet, nicht geschätzt).

Die Farbtöne der abgeleiteten Paare sind so gelegt, dass sie die größten Lücken im Farbkreis zwischen den fünf Board-Tönen füllen (45 / 90 / 172 / 192 / 330). Der weite Bereich 192→330 nimmt vier auf (220 / 248 / 276 / 304), die übrigen drei liegen bei 62, 131 und 355.

**„Nicht erkannt" bekommt bewusst keine eigene Farbe.** Die Kategorie drückt kein Erkennungsergebnis aus, sondern dessen Fehlen; das Design-System hält dafür bereits fest, dass sie „kein Fehler" ist und deshalb keine Fehleroptik bekommt. Eine zwölfte Buntfarbe würde ihr eine Aussage geben, die sie nicht hat — das neutrale Paar (Overlay-Fläche, Sekundärtext) sagt genau das Richtige: hier steht ein Chip, aber keine Einordnung. Damit bleibt sie zugleich die einzige Kategorie, die man auch ohne jede Farbwahrnehmung sofort von den übrigen zwölf unterscheidet.

#### 6b. Ablage: eine Tabelle, geschlüsselt nach `category_key`

Die 26 Werte liegen als CSS-Tokens in `index.css` (`--chip-<key>-bg` / `--chip-<key>-fg`) und werden über eine nach `category_key` geschlüsselte Konstante in `CategoryBadge` aufgelöst; ein unbekannter Key fällt auf das neutrale Paar zurück (Altwerte aus der Laufhistorie wie `"unerkannt"`/`"landscape"` existieren nachweislich, siehe `categoryLabels.ts`). Vollständig ausgeschriebene Klassennamen, kein Zusammenbauen per Template-String — dieselbe Regel wie in `badge.tsx` (Tailwind erkennt nur statische, vollständige Strings).

**Das ist die in der Kopfzeile vermerkte Teil-Rücknahme von Spec 0289.** Dort wurde jede frontendseitige, nach `category_key` geschlüsselte Tabelle abgeschafft, weil Anzeigenamen zur Laufzeit vom Server kommen. Für Anzeigenamen bleibt das so. Für Farben entsteht hier eine neue solche Tabelle, weil der Server keine Farben liefert und auch keine liefern sollte: eine Chip-Farbe ist eine Gestaltungs-, keine Fachentscheidung, und gehört damit ins Design-System, nicht in `categories.py`. Die Kopplung, die dadurch entsteht, ist real und wird bewusst getragen: kommt je eine vierzehnte Kategorie hinzu, braucht sie ein Farbpaar, sonst zeigt sie neutral. Der Fallback verhindert, dass das ein Fehler wird — es bleibt eine sichtbare Lücke, kein Absturz und kein leeres Badge.

#### 6c. Bewusst getragene Kollision mit den Bewertungsfarben

Die vom `architect` benannte Nähe bleibt bestehen und ist mit dieser Entscheidung in Kauf genommen. Nachgerechnet ist sie **enger als zunächst beschrieben, und zwar ausschließlich bei den Board-Paaren selbst**, nicht bei den abgeleiteten:

- Menschen `#FFC107` (H 45) liegt **0°** vom Favorit-Amber `#FFB000` (H 45) entfernt — praktisch derselbe Ton.
- Landschaft `#00B4D8` (H 190) liegt **2°** vom Info-Cyan `#00E5FF` (H 192) entfernt.
- Gegenstand `#FF5260` (H 355) liegt 19° vom Aussortiert-Rot (H 14), Dokument `#CFD600` (H 62) 17° vom Favorit-Amber — die engsten der acht abgeleiteten.
- Die ursprünglich vermutete Nähe Essen `#70E000` ↔ Album `#00E676` beträgt tatsächlich 60° und ist damit unkritisch; diese Einschätzung wird hiermit korrigiert.

**Prüfung gegen das Akzeptanzkriterium „Die drei Bewertungszustände bleiben auch ohne Farbwahrnehmung unterscheidbar": bestätigt, das Kriterium trägt weiterhin.** Es ist ein achromatisches Kriterium, die Kollision ist ein chromatisches Problem. Jeder Bewertungszustand ist dreifach codiert (Textbadge FAVORIT/ALBUM/AUSGESONDERT, eigenes Symbol `star`/`book`/`x-circle`, beim Aussortierten zusätzlich Durchstreichung und gedämpfte Bildfläche); der Kategorie-Chip trägt seinerseits ein dreibuchstabiges Kürzel plus `aria-label`/`title`. In einer Graustufen-Umsetzung bleiben alle diese Signale vollständig erhalten und voneinander verschieden. Die Kollision schwächt die Bewertungsfarben also **visuell**, nicht semantisch.

**Gegenmaßnahme, ausschließlich an den Chips** (die vier Board-Akzente bleiben unangetastet) — und sie kostet nichts, weil sie bereits in der Konstruktion des Boards steckt:

1. **Struktureller Gegensatz gefüllt ↔ getönt.** Eine Bewertung ist immer eine **voll gefüllte Fläche mit dunkler Tinte** (`--rating-*` + `#0B0C10`), ein Kategorie-Chip immer eine **dunkel getönte Fläche mit heller, bunter Schrift** (L 18 % Fläche, S 100 % Schrift). Selbst bei identischem Farbton lesen die beiden dadurch als verschiedene Objektarten — das ist der eigentliche Unterscheidungsträger, nicht der Ton.
2. **Formunterschied.** Der Kategorie-Chip behält den Board-Radius 16px (die einzige verbleibende Pillenform); Bewertungs-Badges haben Radius 6px.
3. **Platzierung.** Die bestehende Regel „Kategorie-Badge in der Gegenecke zur Rating-Badge" bleibt unverändert gültig; die beiden treffen sich auf der Kachel nicht.

Diese drei Punkte sind als verbindliche Regeln ins Design-System-Dokument zu übernehmen, damit die Kollision nicht bei der nächsten Änderung unbemerkt scharf wird.

### 7. Symbolsatz: `lucide-react` als neue Laufzeit-Abhängigkeit

**Entscheidung Daniels, gegen die Empfehlung des `architect`** (der die zwölf Board-SVGs als Copy-in-Repo vorgeschlagen hatte). Entschieden ist: `lucide-react` kommt als Laufzeit-Abhängigkeit in `frontend/package.json`. Damit beantwortet diese ADR die von Spec 0285 ausdrücklich vertagte Icon-Frage („Ein Icon-Set ist eine neue Abhängigkeit und damit ADR-pflichtig").

#### 7a. Korrektur einer Tatsachenbehauptung: das Board **ist** Lucide

Die Board-Referenz vermerkt, das `star` sei „als Pfad ausgearbeitet", und der `architect` hatte daraus zunächst geschlossen, die Board-Geometrie weiche von Lucide ab. Ein Abgleich der exportierten Pfaddaten gegen die Lucide-Originale widerlegt das:

- `check`: Board `M19.9992 6L9.0003 16.9992L4.0008 11.9996` = Lucide `m20 6 9 17l-5-5`.
- `chevron-down`: Board `M6 9L12 15L18 9` = Lucide `m6 9 6 6 6-6`.
- `search`: Board `M21.0002 21.0002L16.6602 16.6602` + Kreis r8 bei (11,11) = Lucide `search`.
- `star`: Board `…L11.526 2.29409…16.381 8.13309…2.161 9.79409…` = dieselben Stützpunkte wie Lucides `star` (`M11.525 2.295…5.166.756…2.16 9.795…`), lediglich in Gegenrichtung gezeichnet und mit vom Figma-Export in kubische Béziers aufgelösten Bögen.

**Alle zwölf Board-Symbole sind Lucide-Symbole.** Der vermeintliche Sonderfall `star` existiert nicht; die Aussage „das Board-`star` weicht von Lucide ab" wird hiermit ausdrücklich zurückgenommen. Damit entfällt auch die Frage, ob ein einzelnes lokales SVG danebengestellt werden muss: **`lucide-react` liefert die Board-Geometrie exakt**, und es gibt an dieser Stelle keine dokumentierungspflichtige Abweichung vom Board mehr.

Das stärkt die getroffene Entscheidung erheblich — der zentrale Einwand des `architect` gegen ein Paket (nur *ähnliche*, nicht *dieselben* Symbole) ist damit gegenstandslos.

#### 7b. Namensabdeckung

Alle zwölf sind in `lucide-react` vorhanden:

| Board-Name | Import aus `lucide-react` | Anmerkung |
|---|---|---|
| `star` | `Star` | |
| `book` | `Book` | |
| `x-circle` | `CircleX` | Lucide hat das Symbol zu `circle-x` umbenannt; `XCircle` besteht als Alt-Alias weiter. Der kanonische Name ist zu verwenden, der Alias nur, falls die installierte Version `CircleX` noch nicht exportiert — **gegen die tatsächlich installierte Version prüfen, nicht raten.** |
| `cog` | `Cog` | Nicht `Settings`. Die Board-Pfaddaten (Speichenlinien `M11 10.27 6.99 3.34` …) sind die von Lucides `cog`, nicht die des sechszahnigen `settings`. |
| `image` | `Image` | **Kollidiert mit dem DOM-Global `Image`.** Beim Import umbenennen (`Image as ImageIcon`) — genau der Grund, warum der Import an genau einer Stelle liegen soll (7c). |
| `check` | `Check` | |
| `info` | `Info` | |
| `chevron-down` | `ChevronDown` | |
| `search` | `Search` | |
| `folder` | `Folder` | |
| `camera` | `Camera` | |
| `tag` | `Tag` | |

#### 7c. Kapselung bleibt: `components/ui/icon.tsx`

`lucide-react` wird **nicht** direkt an den rund zehn Aufrufstellen importiert, sondern ausschließlich in einer projekteigenen Komponente `frontend/src/components/ui/icon.tsx`:

- `name`-Prop als String-Union der zwölf Board-Namen, intern auf die Lucide-Komponenten abgebildet.
- Board-Strichstärke 2 und die Board-Größen (14/16/18/24, Default 16) werden dort **zentral** gesetzt, nicht an jeder Aufrufstelle wiederholt.
- Einfärbung über `currentColor` (Lucides Default), Zugänglichkeit zentral: `aria-hidden="true"` + `focusable="false"` als Regelfall, optionale `title`-Prop schaltet auf `role="img"` für den seltenen Alleinstand.

Gründe für die Kapselung: (1) Die heutigen Aufrufstellen wählen ihr Symbol **datengetrieben** (`RatingBadge`s `SYMBOLS`-Record, `CloudVisionStatusList`s `glyph`-Tabelle) — ein String-Name ist dort der Eins-zu-eins-Ersatz für das heutige Sonderzeichen, eine Komponenten-Referenz wäre eine Umschreibung. (2) Umbenennungen im Paket (siehe `x-circle` → `circle-x`) und Namenskollisionen (`Image`) bleiben auf eine Datei begrenzt. (3) Ein späterer Ausstieg aus dem Paket wäre eine reine Innensache dieser einen Datei.

#### 7d. Bündelgröße

`lucide-react` liefert ES-Module mit einer Komponente pro Symbol und ist damit tree-shakebar; bei zwölf tatsächlich importierten Symbolen landen zwölf Pfad-Definitionen im Bundle, nicht der gesamte Satz. Voraussetzung ist der **benannte Import** (`import { Star } from 'lucide-react'`), nie ein Namespace-Import (`import * as icons`) und nie ein dynamischer Zugriff über einen berechneten Schlüssel auf das Paket-Objekt — beides hebelt das Tree-Shaking aus und zöge den vollständigen Satz ein. Die Abbildung in `icon.tsx` muss deshalb ein **statisches** Objektliteral aus benannt importierten Komponenten sein. Das ist bei einer PWA mit Mobilfunk-Nutzung (Bundle-Size-Begründung aus ADR 0011) keine Kosmetik, sondern die Bedingung, unter der diese Abhängigkeit vertretbar ist.

#### 7e. Zwei Abweichungen bei der Symbol**zuordnung** (nicht bei der Geometrie)

- Das Board setzt für den **Warnungs**-Toast das `star`-Symbol. `star` ist in PhotoSort das Favorit-Symbol; dieselbe Form für „Warnung" zu verwenden bräche „Bewertungsstufen auf einen Blick unterscheidbar". Warnung nutzt stattdessen `info`.
- `x-circle` ist im Board das Aussortiert-Symbol und bleibt es. Die heutigen `×`-Zeichen an Schließen-/Entfernen-Schaltflächen werden deshalb **nicht** durch `x-circle` ersetzt — der Zwölfer-Satz enthält kein neutrales Kreuz. Sie bleiben Textzeichen.

Ebenfalls dokumentierte Lücken des Zwölfer-Satzes: `✎` (Kategorie-Übersteuerungs-Marker — kein Stift im Satz), `○` (die drei „nicht gelaufen"-Zustände in `CloudVisionStatusList` — kein leerer Kreis im Satz; sie bekommen stattdessen den vorhandenen `StatusDot`), `●●○` (`QualityMeter` — bewusst ein Messglyph, kein Symbol) und `–` (unbewertetes Badge — das Board zeigt für „Neu" gar kein Badge). Diese Lücken sind ausdrücklich **nicht** durch beliebige weitere Lucide-Symbole zu füllen: der Satz des Boards ist zwölf Symbole groß, und ihn stillschweigend zu erweitern wäre eine Gestaltungsentscheidung ohne Vorlage.

### 8. Zielflächen: 32px sichtbar, 44px treffbar

Das Board ist ein Desktop-Entwurf (Schaltflächen 31px hoch); PhotoSort ist zugleich eine PWA am Telefon, und das Design-System fordert bisher 44×44px für jedes interaktive Element — was der Grund dafür ist, dass heute überall `h-11` steht und die Oberfläche gerade nicht dicht ist. WCAG 2.2 „Target Size (Minimum)" (AA) verlangt 24×24 CSS-Pixel; das Board erfüllt das bereits.

**Entscheidung:** Die bisherige 44px-Regel wird von einer **Größen**regel zu einer **Trefferflächen**regel. Bedienelemente werden auf die kompakten Board-Maße gebracht (Standard-Schaltfläche 32px hoch statt 44px), und die Trefferfläche wird über ein transparentes Pseudo-Element auf mindestens 44×44px erweitert — eine einzige Utility (`@layer utilities`), die von Button, Switch, Checkbox und Icon-Button gemeinsam genutzt wird.

Damit werden beide Anforderungen erfüllt, statt eine gegen die andere auszuspielen: das Board bekommt seine Dichte, das Telefon seine Trefferfläche. Das Pseudo-Element wird über die Mitte aufgespannt und liegt innerhalb der 8-Punkt-Abstände; es überlappt bei den vorgesehenen Abständen (≥12px) keine Nachbarelemente.

## Begründung

Der Kern ist Punkt 2: Die Umstellung ist **kein Umbau der Architektur, sondern ein Wertetausch an einer bereits vorhandenen Naht.** Die Token-Zweiteilung aus dem Organic-Import hat genau diesen Fall vorweggenommen — deshalb tragen rund 175 der etwa 190 Farb-Aufrufstellen in 91 `.tsx`-Dateien die Umstellung, ohne angefasst zu werden, und die Nacharbeit reduziert sich auf sechs abzählbare, namentlich benannte Listen.

Der zweite Kern ist die Konfliktauflösung: Board-Werte sind eine Vorlage, kein Gesetz. Wo sie das Kontrast-Akzeptanzkriterium verfehlen, gilt dieselbe Logik, die Daniel für die Zielflächen bereits festgelegt hat — die Untergrenze gewinnt. Die Abweichung wird dabei jedes Mal an derselben Stelle vorgenommen wie schon 2026-08-30 beim Organic-Import: **an der Schrift- oder Linienfarbe, nie an der Fläche.** Von den sechs Konflikten ändern vier (4b, 4d, 4e, 4f) und der Rahmen aus 4c den sichtbaren Eindruck des Boards praktisch nicht; der einzige spürbare ist 4a, und genau der ist Daniel vorgelegt worden.

Bei den beiden Punkten, die gegen die Empfehlung entschieden wurden, ist die Begründungslage nach der Detailarbeit unterschiedlich: Beim Symbolsatz (7) hat sich der zentrale Einwand des `architect` beim Nachprüfen als schlicht falsch erwiesen — das Board *ist* Lucide, das Paket liefert die Geometrie exakt, die Entscheidung ist damit besser begründet als die Empfehlung. Bei den Kategorie-Chips (6) bleibt der Einwand sachlich bestehen (eine neue frontendseitige Farbtabelle und eine Farbnähe zu zwei der vier Akzente); er ist als Kosten dokumentiert, mit drei strukturellen Gegenmaßnahmen abgefedert und gegen den Gewinn an Scanbarkeit der Kuratierungsansicht abgewogen — das ist eine Produktentscheidung, und sie liegt bei Daniel.

## Konsequenzen

- **Positiv:** Ein einziges Farbschema halbiert die Kontrastprüfpflicht dauerhaft und macht jede künftige Farbentscheidung eindeutig. Die vier Flächenstufen ersetzen Schatten als Tiefenmittel, wodurch drei Tokens und eine Utility ersatzlos entfallen. Der Symbolsatz beendet die heute über sieben Dateien verstreuten Sonderzeichen und liefert die Board-Geometrie exakt. Alle dreizehn Kategorien sind farblich unterscheidbar und erreichen nachgerechnet AA.
- **Negativ / bewusst getragen:**
  - Ein heller Modus ist ohne neue ADR nicht zurückholbar — beabsichtigt.
  - Der Abstand zwischen Textstufe 2 und 3 ist klein (4a); sie unterscheiden sich praktisch über die Verwendung, nicht über die Wahrnehmung.
  - **Netto-Abhängigkeitsbilanz +1** (zwei `@fontsource`-Pakete raus, zwei rein, `lucide-react` neu). Das Tree-Shaking-Gebot aus 7d ist damit eine dauerhafte Auflage, keine einmalige.
  - Eine frontendseitige, nach `category_key` geschlüsselte Farbtabelle entsteht neu (Teil-Rücknahme von 0289); eine vierzehnte Kategorie bräuchte dort einen Eintrag und zeigt sonst neutral.
  - Die Farbnähe Menschen↔Favorit (0°) und Landschaft↔Info (2°) bleibt bestehen und wird nur strukturell (gefüllt ↔ getönt), formal (Radius) und räumlich (Gegenecke) aufgefangen.
  - Sieben Board-Werte weichen ab (Text Muted, Rahmen für Bedienelemente, Aussortiert als Text, Badge-Tinte, Gebäude-Chip-Schrift, Warnungs-Symbol, Karten-Deckkraft) und müssen im Design-System-Dokument als Abweichung geführt werden, damit sie bei der nächsten Board-Aktualisierung nicht stillschweigend „zurückrepariert" werden.
  - Vier `.tsx`-Dateien und die Primitive tragen benannte Nacharbeit, die kein Test erzwingt (verwaiste Utility-Klassen erzeugen in Tailwind keinen Buildfehler) — dafür ist der Vollständigkeits-Scan aus Punkt 2 ein eigener Umsetzungsschritt.
- **Zwischenzustand:** Nach dieser Stufe ist die Oberfläche sichtbar uneinheitlich — die Ansichten tragen die neuen Tokens, sind aber noch in der Anordnung des Organic-Stands. Das ist ausdrücklich zulässig (Akzeptanzkriterium „Übergang"); unbenutzbar darf sie nicht sein, weshalb die Nacharbeitslisten nicht optional sind.
- **Folgearbeit:** Issue #321 (Stufe 2) überarbeitet die Ansichten auf dieser Grundlage. Bewertungsleiste, Navigationselement und die Prozessstufen der Fortschrittsanzeige stehen zwar im Board, aber nicht in der Grundelemente-Liste dieser Stufe und gehören dorthin.
- **Dokumentation:** `specs/architecture/0004-design-system.md` und `.claude/skills/design-system/SKILL.md` werden im selben PR vollständig auf den neuen Stand gezogen (inklusive der ausdrücklichen Rücknahmen: kein Hellmodus; „Akzent und Bewertungsfarben getrennt halten"; „44×44px" als Größen- statt Trefferflächenregel; „volle Pillen für kleine Bedienelemente"; „Schatten für Karten, Rahmen im Dark Mode"; „Kategorie-Chips immer neutral"). `docs/architecture.md`, `docs/setup.md` und das Root-`README.md` bleiben unberührt: keine der drei beschreibt Design-System, Schriften oder Farben, und `lucide-react` erzeugt keinen neuen Setup-Schritt — `npm ci` in `frontend/Dockerfile` und `npm install` in der lokalen Anleitung decken sie ohne Systemabhängigkeit ab.
