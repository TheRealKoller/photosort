# 0638 - Duplikatsansicht: Bilder im Originalformat ohne Beschnitt anzeigen

**Status:** Implemented ([PR #644](https://github.com/TheRealKoller/photosort/pull/644))
**Erstellt:** 2026-11-15
**Bezug:** [#638](https://github.com/TheRealKoller/photosort/issues/638)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil Rastergeometrie, Grenzwerte und die rechnerische Absicherung jedes AK für die testgetriebene Umsetzung ausformuliert sein müssen.

## Ziel

In der Vergleichsansicht einer Duplikat-Gruppe werden Fotos heute quadratisch beschnitten. Gerade
bei ähnlichen Aufnahmen fehlen dadurch Bildränder, die bei der Entscheidung „behalten/Ausschuss"
helfen. Nach dieser Änderung erscheint jede Aufnahme im natürlichen Seitenverhältnis, vollständig
und ohne Beschnitt: Querformat breit, Hochformat hoch. Das Raster ordnet die Bilder in
gestaffelten Zeilen; der Vorschau-Streifen der Großansicht verliert ebenfalls den Beschnitt,
während die Großansicht selbst bereits vollständig darstellt.

## User Story

Als Nutzer, der eine Duplikat-Gruppe im Ausschuss durchgeht, möchte ich jede Aufnahme im Raster
und im Vorschau-Streifen der Großansicht in ihrem natürlichen Seitenverhältnis und unbeschnitten
sehen, damit ich Schärfe, Belichtung und Motiv ohne Umschalten beurteilen und die richtige
Aufnahme behalten kann.

## Akzeptanzkriterien

- [ ] **Kein Beschnitt.** Liegt das Seitenverhältnis einer Datei zwischen 0,56 und 7 (beide Grenzen eingeschlossen), hat die Bildfläche im Raster genau das Verhältnis der Datei. Hochformat ist höher als breit, Querformat breiter als hoch; zulässig ist eine Abweichung von höchstens 2 %. Ist das Verhältnis unbekannt (fehlt oder ungültig), ist die Bildfläche ein 3:2-Feld. Bei einem extremen Verhältnis ist sie ein Feld im Grenzverhältnis: 0,56 für Hochformate unter 0,56, 7 für Panoramen über 7. In beiden Fällen steht das Bild vollständig und eingepasst darin. Ein Rand in der Kartenfläche ist erlaubt, ein Beschnitt nie.
- [ ] **Gestaffelte Zeilen.** Alle Bildflächen einer Zeile sind gleich hoch (±1 px) und oben bündig. In jeder vollen Zeile ergeben die Kachelbreiten plus die Zwischenräume die Breite der Liste (±2 px). Die letzte Zeile wird nicht gestreckt: Sie steht linksbündig in Zielhöhe und ist kürzer als die Liste. Eine Zeile, die bündig höher als die Höchsthöhe würde, steht wie die letzte Zeile. Es gibt keine feste Spaltenzahl: Bei gemischten Formaten tragen Kacheln derselben Gruppe verschiedene Breiten, und die Zahl der Kacheln je Zeile hängt von der Fensterbreite ab.
- [ ] **Breite und Wahl.** Jede Kachel ist mindestens 100 px breit, auch bei extremen und unbekannten Verhältnissen und bei 360 px Fensterbreite. Die Wahl „Behalten/Ausschuss“ bricht in beiden gedrückten Zuständen um und liegt immer vollständig im Rechteck ihrer Kachel. Bei 360 px gilt: Die Seite scrollt nicht waagerecht, jedes Bedienelement der Kachel ist mindestens 44 × 44 px groß und an seiner Fläche einzeln treffbar, und auch eine Panorama-Bildfläche ist mindestens 44 px hoch.
- [ ] **Alles sichtbar.** Ohne Aufklappen und ohne Interaktion sind gleichzeitig sichtbar: Zustandskennzeichen, Dateiname, Bewertungszeile sowie die Wahlzeile oder, wenn keine Wahl möglich ist, der Grund. Das Bild hat in beiden Zuständen volle Helligkeit (kein `data-dimmed`). Die Kacheln einer Zeile sind oben bündig, darunter dürfen sie verschieden hoch sein (zum Beispiel Wahlzeile gegenüber Grund).
- [ ] **Großansicht unverändert erreichbar.** Die Bildfläche bleibt ein natives `button`, das die Großansicht öffnet, per Klick, Enter und Leertaste. Nach dem Schließen über Esc oder „Vergrößerung schließen“ liegt der Fokus auf der Bildfläche der zuletzt gezeigten Aufnahme. Scrollen und Tastaturweg bleiben wie bisher, auch die Pfeiltasten wirken im Raster nicht.
- [ ] **Ladezustand ohne Sprung.** Solange die Gruppe lädt, zeigt eine Platzhalterliste mit `role="status"` und unverändertem `aria-label` 3:2-Bildflächen in derselben Kachelgeometrie wie das spätere Raster (Liste, Kachelrand, Textzeilen). Treffen die Gruppendaten ein, darf sich die Zeilenaufteilung genau einmal ändern, weil die echten Verhältnisse die 3:2-Planung ersetzen. Das spätere Eintreffen der Bilddaten verändert Lage und Größe keiner Kachel (±1 px).
- [ ] **Vorschau-Streifen vollständig.** Alle Aufnahmen einer Streifenreihe sind gleich hoch (±1 px). Die Breite jeder Aufnahme folgt ihrem Verhältnis (Höhe × Verhältnis, ±2 px für den Rahmen) und wird nur durch die Mindestbreite von 44 px und die Streifenbreite begrenzt. Das Bild ist eingepasst und nie beschnitten.
- [ ] **Streifen bedienbar.** Jede Aufnahme im Streifen ist mindestens 44 × 44 px groß. Ein Hochformat schmaler als 44 px bei Streifenhöhe steht eingepasst und mit Rand in einem 44 px breiten Feld. Kein Feld ist breiter als der Streifen, auch nicht bei einem Panorama über 7 bei 360 px. Der Streifen bricht um und scrollt nie waagerecht.
- [ ] **Streifen-Auszeichnung unverändert.** Der Streifen führt alle Mitglieder in Gruppenreihenfolge. Genau eines trägt `aria-current="true"` und den bisherigen Rahmen. Zugänglicher Name („Aufnahme n von m: Datei, Zustand“), Zustandssymbol und Reihenfolge bleiben wörtlich unverändert.
- [ ] **Nur diese Ansicht.** Geändert werden nur Raster, Platzhalter und Vorschau-Streifen der Vergleichsansicht. Fotoübersicht, Kuratierung, Bühne der Großansicht, Entscheidungen, Abkürzungen, Abschluss, Zustände und Rückwege verhalten sich unverändert. Die bestehenden Verhaltenstests dazu bleiben ohne Erwartungsänderung grün.

## Datenmodell-Bezug

Keine Änderung. `PhotoOut.aspect_ratio` reist bereits in `DuplicateGroupItem.photo` mit (`backend/src/photosort/api/photos.py::_to_photo_out`).

## Architektur / Umsetzung

**Ansatz:** Das Raster der Vergleichsansicht wird ein justiertes Zeilenraster nach dem Muster aus
ADR 0110 (`utils/justifiedRows.ts`, ungeändert), mit eigenen Parametern für diese Ansicht. Der
Vorschau-Streifen der Großansicht wird nicht justiert: Er bekommt eine feste Zeilenhöhe, und die
Breite folgt dem Verhältnis über CSS `aspect-ratio`, begrenzt durch Mindest- und Höchstbreite. Die
Bühne bleibt unverändert. Kein Backend, keine API, keine Migration: `PhotoOut.aspect_ratio` reist
schon in `DuplicateGroupItem.photo` mit (`api/photos.py::_to_photo_out`). Keine neue ADR, denn es
gibt keine neue Technologie, keine neue Abhängigkeit und keine neue Datenstruktur.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/utils/duplicateLayout.ts` (neu) + `.test.ts` | Konstanten, `duplicatePlanningRatio`, `duplicateGridRows` (reine Funktionen) |
| `frontend/src/components/DuplicatePhotoTile.tsx` (+ Test) | neue Props `imageWidth`/`imageHeight`; Bildfläche mit gerechneten Maßen und `object-contain`; Kachelbreite = Bildbreite + Rand; `aspect-square` und `object-cover` fallen weg |
| `frontend/src/pages/DuplicateComparePage.tsx` (+ Test) | `useElementWidth` an der Liste; `grid grid-cols-*` wird zu `flex w-full flex-wrap items-start gap-3`; Platzhalter in derselben Geometrie |
| `frontend/src/components/DuplicateEnlargedView.tsx` (+ Test) | Streifen: `size-16 sm:size-20` + `object-cover` werden zu `h-16 sm:h-20` + `aspect-ratio` + `min-w-11 max-w-full` + `object-contain` |
| `frontend/src/designSystem.*.contract.test.ts` | die drei Dateien in die Regel „kein `object-cover`/`aspect-square`/`grid-cols-`“ und in die Kopplung `gap-3` ↔ `GRID_GAP_PX` aufnehmen |
| `e2e/tests/grid-columns.spec.ts` | den Duplikat-Fall (feste Spaltenzahl 2/3, gleiche Breiten) durch die Zusagen des justierten Rasters ersetzen |
| `e2e/tests/duplikat-vergleich.spec.ts` | Streifen: gleiche Höhe je Reihe, ≥ 44×44, kein Beschnitt (Kastenverhältnis gegen `naturalWidth/naturalHeight`) |
| `e2e/tests/no-horizontal-scroll.spec.ts` | nur den Kommentar „zwei Spalten“ anpassen, die Messung bleibt |
| `specs/architecture/0004-design-system.md`, `.claude/skills/design-system/SKILL.md`, `docs/architecture.md` | Eintrag „Vergleichsansicht: justiertes Raster, Streifen ohne Beschnitt“ |

Wiederverwendet werden `justifiedRows`, `naturalTiles`, `GRID_GAP_PX`, `FALLBACK_ASPECT_RATIO`,
`planningRatio` (bereinigt den API-Wert, bevor er in einen Inline-Stil geht), `useElementWidth` und
die Testattrappe `test/observers.ts`. `useJustifiedRows` und `curationRows` werden nicht
wiederverwendet: Sie sind fest auf die Kuratierungsparameter verdrahtet und kennen keinen Rand an
der Kachel.

### Datenfluss Raster

`items[].photo.aspect_ratio` → `duplicatePlanningRatio` → `duplicateGridRows(ratios, gemesseneBreite)`
→ je Index `{width, height}` der Bildfläche → `DuplicatePhotoTile` (`li` mit `style.width = width + 20`,
Bild-`button` mit `style = {width, height}`).

### Parameter (`utils/duplicateLayout.ts`)

| Konstante | Wert | Herleitung |
|---|---|---|
| `DUPLICATE_TARGET_ROW_HEIGHT_PX` | 280 | Zielhöhe der Bildfläche; bei 976 px Inhaltsbreite stehen drei 4:3 mit ≈ 223 px nebeneinander, etwa so groß wie heute |
| `DUPLICATE_MIN_ROW_HEIGHT_PX` | 200 | gilt für Zeilen mit mehr als einem Bild; zusammen mit der Mindestbreite bleibt 9:16 unverzerrt (siehe unten) |
| `DUPLICATE_MAX_ROW_HEIGHT_PX` | 350 | eine volle Zeile, die bündig höher würde, steht wie die letzte Zeile (Zielhöhe, linksbündig); so wird z. B. ein einzelnes 3:4 am Telefon nicht 410 px hoch |
| `DUPLICATE_TILE_INSET_X_PX` | 20 | Kachelrand waagerecht: 2 × (`px-2` 8 + `border-2` 2). Die Kachel trägt dafür `px-2` an **allen** Breiten (senkrecht weiter `py-2 sm:py-3`), sonst hinge die Rechnung an einem Breakpoint. Kopplung wie bei `GRID_GAP_PX`: Kommentar plus Test |
| `DUPLICATE_MIN_IMAGE_WIDTH_PX` | 112 | breiteste einzelne Wahlschaltfläche (gedrückt „Ausschuss“, `size="sm"`: 2 × 12 + Symbol 14 + 8 + Wort ≈ 55 ≈ 101 px) plus Reserve |
| `DUPLICATE_MIN_PLANNING_RATIO` | 112/200 = 0,56 | schmaler wird nicht geplant; liegt unter 9:16 = 0,5625, also bleiben alle üblichen Hochformate (9:16, 2:3, 3:4) unverzerrt |
| `DUPLICATE_MAX_PLANNING_RATIO` | (360 − 2·16 − 20) / 44 = 7 | breiter wird nicht geplant; damit ist die Bildfläche auch allein in einer Zeile an der schmalsten Breite (360 px) mindestens 44 px hoch |

- `duplicatePlanningRatio(r) = min(max(planningRatio(r), 0,56), 7)`. `planningRatio` bereinigt
  `null`, NaN und Zeichenketten auf 3:2. Die Kuration bleibt dabei unberührt.
- `duplicateGridRows(ratios, W)`:
  - Ist `W <= 0` (noch nicht gemessen): `naturalTiles(planned, 280)` in einer Zeile.
  - Sonst: `justifiedRows({ ratios: planned, containerWidth: W − 20, gap: GRID_GAP_PX + 20,
    targetRowHeight: 280, minRowHeight: 200, maxRowHeight: 350 })`.
  - **Der Rechentrick:** Für eine volle Zeile mit n Kacheln gilt
    Σbᵢ + (n−1)(12+20) = W − 20, also Σ(bᵢ+20) + (n−1)·12 = W.
    Die äußeren Kachelbreiten schließen damit exakt bündig ab, und `justifiedRows` bleibt ungeändert.

### Wie die AK rechnerisch gesichert sind

- **AK1:** Die Bildfläche ist der geplante Kasten, das Bild darin `object-contain`. Bei einem
  Verhältnis zwischen 0,56 und 7 entspricht der Kasten genau dem Dateiverhältnis. Unbekannt heißt
  3:2-Kasten mit Rand. Nie `object-cover` (Vertragstest).
- **AK2:** Gleiche Zeilenhöhe, bündige volle Zeile und ungestreckte letzte Zeile kommen aus
  `justifiedRows`. Die Höhe ist eine gemeinsame Zahl je Zeile. Die Spaltenzahl ergibt sich aus der
  Rechnung, nicht aus `grid-cols`.
- **AK3, Breite:**
  - Zeile mit mehreren Bildern: h ≥ 200, also b ≥ 0,56·200 = 112. Das letzte Bild trägt den
    Rundungsrest von höchstens ±(n−1)·0,5 px, bleibt also bei ≥ 110.
  - Letzte Zeile oder Zeile über 350: h = 280, also b ≥ 156.
  - Einzelbild in einer Zeile: b = W − 20.
  - Kachel damit immer ≥ 130 px ≥ 100 px, und der Inhalt (≥ 110 px) trägt die breiteste Schaltfläche.
- **AK3, Wahl:** Die Wahlzeile hat schon `flex flex-wrap gap-3`, die Knöpfe `grow`. Überlaufen kann
  nur ein einzelner Knopf, der breiter als der Inhalt ist; das schließt die Mindestbreite aus.
  Zustandskennzeichen (≈ 68) + `gap-2` + Dateiname (`min-w-6`, `truncate`) ≈ 100 ≤ 110.
  Die Bewertungszeile bricht schon um.
- **AK3, Telefon:**
  - Bei 360 px ist W = 328, also W′ = 308. Zwei Bilder nebeneinander gehen nur, wenn r₁+r₂ ≤ 1,38
    (zwei Hochformate); sonst ein Bild je Zeile. Das folgt zwingend aus AK1: Eine tiefere
    Mindesthöhe würde 9:16 und 2:3 verzerren.
  - Die Bildfläche bleibt ≥ 44 px hoch (Obergrenze 7 beim Planungsverhältnis), die Wahlknöpfe
    `h-11` bleiben.
  - Kein waagerechtes Scrollen: Jede gerechnete Breite ist ≤ W. Vor der ersten Messung tragen `li`
    und Bild-`button` zusätzlich `max-w-full`.
- **AK4:** Die Liste ist `items-start`, damit sind die Kacheln oben bündig; der Teil unter dem Bild
  bleibt frei hoch. Inhalt der Kachel und volle Helligkeit bleiben (ADR 0112).
- **AK5:** Bild-`button`, `imageRef`, `aria-label`, `data-testid="duplicate-image"` und `onOpen`
  bleiben, nur die Maße kommen von außen. Die Fokusrückgabe in der Seite bleibt unverändert.
- **AK6:** Zwei Ebenen.
  - Hat `PhotoImage` noch kein Blob, steht sein Skeleton `size-full` im schon gerechneten Kasten:
    exakt die spätere Form.
  - Lädt die Gruppe noch: Es gibt einen `useElementWidth`-Ref in der Seite. Der Callback-Ref hängt
    an der jeweils gerenderten Liste (Platzhalterliste oder Raster, nie beide). Die Platzhalter sind
    `duplicateGridRows(4 × null, width)`, also 3:2-Kästen in derselben Kachelgeometrie samt Rand und
    Textzeilen-Skeletons.
  - Die echte Form ist vor den Daten nicht bekannt, 3:2 ist die festgelegte Ausfallrichtung.
- **AK7/8, Streifen:** Jeder Knopf bekommt
  `h-16 sm:h-20 min-w-11 max-w-full overflow-hidden rounded-md border-2` plus
  `style={{ aspectRatio: planningRatio(item.photo.aspect_ratio) }}`, die Breite bleibt `auto`. Das
  `li` bekommt `relative max-w-full`, das Bild `size-full object-contain`. Daraus folgt:
  - Gleiche Höhe in der Reihe: die feste Höhe.
  - Breite gleich Höhe × Verhältnis: CSS rechnet sie und begrenzt sie mit `min-width`/`max-width`.
  - ≥ 44 × 44: Höhe 64 bzw. 80, Mindestbreite 44. Ein Hochformat unter 44/64 ≈ 0,69 steht
    eingepasst im 44-px-Feld.
  - Nie breiter als der Streifen: `max-w-full`. Die Liste bleibt `flex flex-wrap gap-3`, also
    Umbruch und kein waagerechtes Scrollen.
  - Der API-Wert erreicht den Stil nur als bereinigte Zahl (`planningRatio`).
  - Hinweis zum Rand: Mit `border-box` gilt `aspect-ratio` für den Kasten samt 2-px-Rahmen. Der
    Bildinhalt hat deshalb höchstens ≈ 2 px Rand und wird nie beschnitten.
- **AK9:** Reihenfolge, `aria-current`, Rahmen `border-text-h`/`border-transparent`, Knopfname und
  Zustandssymbol (`absolute bottom-1 left-1`, 22 px, passt in 44 px) bleiben unverändert.
- **AK10:** Nur die drei Dateien plus das neue Modul. `curationLayout.ts`, `justifiedRows.ts`,
  `PhotoCard` und die Bühne (`h-96 lg:h-144`, `object-contain`) bleiben unberührt.

### Reihenfolge

1. `duplicateLayout.ts` testgetrieben: Bereinigung und Grenzen des Planungsverhältnisses; bündiges
   Zeilenende der äußeren Breiten bei 328/976 px; jede Kachel ≥ 130; Einzelpanorama ≥ 44 hoch;
   letzte Zeile 280; nicht gemessen ergibt natürliche Breiten.
2. `DuplicatePhotoTile`: Props und Maße. Den Test „`aspect-square` reserviert die Höhe“ durch
   „Inline-Breite/-Höhe vor dem Laden gesetzt“ ersetzen.
3. `DuplicateComparePage`: Messung, Flex-Liste, Platzhalter (Rows-Test über `test/observers.ts`).
4. `DuplicateEnlargedView`: Streifen.
5. Vertragstest, E2E, Doku.

### Konsequenzen

- Spec 0374, AK3 („bei 360 px genau 2, bei 1280 px genau 3 Spalten“, gleiche Kachelbreiten) gilt
  nicht mehr, sie wird durch AK2 dieser Story ersetzt. Die zugehörige E2E-Prüfung in
  `grid-columns.spec.ts` wird ersetzt, nicht bloß gelockert.
- Am Telefon steht meist ein Bild je Zeile, nur zwei Hochformate passen nebeneinander. Das folgt aus
  AK1 und ist gewollt.
- Hochformate schmaler als 0,56 und Panoramen breiter als 7:1 bekommen im Raster einen Rand statt
  ihres exakten Kastens (siehe offener Punkt).

## UI/UX

**Ablauf:** Der Ablauf bleibt gleich. Man sieht das Raster, tippt auf eine Bildfläche, die Großansicht ersetzt das Raster an derselben Stelle, und „Vergrößerung schließen“ gibt den Fokus an die Bildfläche zurück. Neu ist nur die Geometrie, Bedienung und Tastaturweg ändern sich nicht (AK5).

**Raster (geladen):**
- Das Raster wird ein justiertes Zeilenraster wie in der Fotoübersicht und der Kuratierung (0004 „Kuratierungskachel / Raster“, „Rasterkachel“).
  - Die Liste ist `flex flex-wrap items-start gap-3`, die Spaltenklassen entfallen.
  - Jede Kachel ist so breit wie ihre Bildfläche plus 20 px Rand. Die Bildfläche trägt Breite und Höhe als Inline-Maß, das Bild darin ist `object-contain`.
- Eine volle Zeile schließt links und rechts bündig ab. Die letzte Zeile steht linksbündig in Zielhöhe und wird nicht gestreckt (AK2).
- Der Kartenkörper bleibt, wie er ist. Zustandsrahmen, Kennzeichen, Dateiname (`truncate`), Bewertungszeile und Wahl bzw. Grund stehen unter dem Bild, alle gleichzeitig sichtbar. Das Bild hat in beiden Zuständen volle Helligkeit (AK4, ADR 0112).
- Die Kacheln sind oben bündig, der Teil unter dem Bild darf je Kachel verschieden hoch sein. Ein Ausrichten der Unterkanten gibt es nicht. Das wird bewusst anders gehandhabt als bei der Foto-Karte (0004 Z. 250): Wo Bildhöhen je Zeile gleich sind, stehen Kennzeichen und Dateiname einer Zeile ohnehin auf einer Linie.
- Bei unbekanntem oder extremem Verhältnis (unter 0,56 oder über 7) ist die Bildfläche ein geplanter Kasten, z. B. 3:2. Der Rand neben dem eingepassten Bild ist die Kartenfläche `--elevated`, ohne eigene Tönung und ohne Rahmen. Das ist dieselbe Regel wie bei der Foto-Karte (0004 Z. 250).
- Der Kachelrand ist an allen Breiten `px-2`, senkrecht weiter `py-2 sm:py-3`. Das ist eine reine Rechengröße und ändert die Wirkung nicht sichtbar.

**Telefon (360 px):**
- Meist steht ein Bild je Zeile. Nur zwei Hochformate passen nebeneinander.
- Es gibt kein waagerechtes Scrollen. Die Wahlknöpfe bleiben `h-11` und brechen innerhalb der Kachel um (AK3).
- Eine Panorama-Bildfläche ist mindestens 44 px hoch.

**Desktop (≈ 976 px Inhaltsbreite):** Bei einer Zielhöhe von 280 px stehen etwa drei Querformate nebeneinander. Die Kachelgröße ist damit ungefähr so wie heute.

**Lädt:**
- *Gruppe lädt:* Die Platzhalterliste nutzt dieselbe Geometrie, also 4 × 3:2-Kästen mit Kachelrand und Textzeilen-Skeletons. `role="status"` und das `aria-label` bleiben, der Skeleton-Ton bleibt `--text-disabled`.
- *Einzelbild lädt:* Das Skeleton von `PhotoImage` füllt den schon gerechneten Kasten, das Raster springt nicht (AK6).

**Fehler, leer, Gruppenaktionen, Abschluss:** unverändert.

**Großansicht:** Bühne (`h-96 lg:h-144`, `object-contain`) und Seitenspalte bleiben unverändert.

**Großansicht-Streifen:**
- Jede Aufnahme hat eine feste Höhe (`h-16 sm:h-20`), die Breite folgt dem Verhältnis über `aspect-ratio`. Die Breite liegt zwischen `min-w-11` und `max-w-full`, das Bild ist `object-contain` (AK7, AK8).
- Ein schmales Hochformat steht eingepasst im 44-px-Feld. Den Rand trägt `bg-surface` am Knopf, derselbe Ton wie bei der Bühne. So bleibt das Trefferfeld eine geschlossene Fläche, und der Rahmen der aktuellen Aufnahme umschließt das ganze Feld.
- Der Streifen bricht um und scrollt nie waagerecht.
- Die Auszeichnung bleibt unverändert: `border-text-h` mit `aria-current`, Zustandssymbol unten links auf `--overlay`, zugänglicher Name und Reihenfolge (AK9).

**Bezug zum Design-System:** Das Raster folgt dem Muster „justierte Reihen ohne Beschnitt“ (ADR 0110 und 0134, 0004 „Kuratierungskachel“ und „Rasterkachel“). Die Trefferflächen-Regel (32 px sichtbar, 44 px treffbar) und der heiße Pfad `h-11 sm:h-8` bleiben. Es kommt keine neue Bewegung und keine neue Abhängigkeit dazu.

## Security

**Ich stufe die Story als sicherheitsrelevant ein, aber nur gering.** Sie bringt kein Secret, keinen Endpunkt und keine neue Eingabe von außen. Auth und Sichtbarkeit zwischen den Nutzern ändern sich nicht. Neu ist nur, dass der API-Wert `PhotoOut.aspect_ratio` in zwei weitere Inline-Stile fließt. Das ist dasselbe Muster wie in Spec 0489 und 0531, die Auflagen gelten hier unverändert.

- **Bedrohung:** Ein manipuliertes oder fehlerhaftes `aspect_ratio` (Zeichenkette mit CSS-Anteil, `NaN`, `Infinity`, ≤ 0) gelangt in einen `style`. Es könnte dort CSS einschleusen oder das Raster sprengen, etwa durch eine riesige Breite, waagerechtes Scrollen oder eine unbedienbare Kachel.
- **Muss 1:** Der Wert erreicht einen Stil nur über `planningRatio` (hier über `duplicatePlanningRatio` = `min(max(planningRatio(r), 0,56), 7)`). Das gilt im Raster für `{width, height}` und `width + 20` und im Streifen für `aspectRatio`. Jeder andere Wert fällt auf 3:2 zurück. Kein Zugriff auf `item.photo.aspect_ratio` am Bereiniger vorbei.
- **Muss 2:** Gesetzt wird nur eine Zahl in einer gewöhnlichen CSS-Eigenschaft. Nicht erlaubt sind eine aus dem Wert zusammengesetzte Zeichenkette, eine CSS-Custom-Property als Träger, ein `url()`-Kontext und `dangerouslySetInnerHTML`.
- **Muss 3:** Der Dateiname bleibt reiner React-Textknoten. Er fließt nicht in `style`, `href`, `src` oder `key`, wie bisher.
- **Muss 4, Test:** Je ein Test in `duplicateLayout.test.ts` und `DuplicateEnlargedView.test.tsx` gibt `aspect_ratio` wider seinen Typ feindlich belegt ein, z. B. `"1;background:url(x)"`, `NaN`, `-1`, `Infinity`. Erwartet wird: Der Stil enthält weder `url(` noch `;` noch den Text. Raster und Streifen rechnen mit 3:2.
- **Die Obergrenze 7 wirkt nebenbei als Schutz:** Ein extremes Verhältnis kann Kachel oder Streifen weder unbegrenzt breit noch unter 44 px hoch machen. Im Streifen begrenzt `max-w-full` die Breite zusätzlich.

## Teststrategie

**Reine Funktion (vitest, `utils/duplicateLayout.test.ts`, tabellengetrieben, ohne DOM; trägt AK1–3 rechnerisch):**
- `duplicatePlanningRatio`:
  - `null`, `NaN`, `0`, negativ, `Infinity` und Zeichenkette ergeben jeweils 3:2.
  - Genau 0,56 und genau 7 bleiben stehen (einschließend), 0,5 und 20 werden auf die Grenze geklemmt.
  - 9:16 = 0,5625 bleibt unverändert.
- `duplicateGridRows`:
  - Je volle Zeile gilt Σ(Bildbreite + 20) + (n−1)·12 = W, geprüft bei 328, 976 und einer nicht glatt aufgehenden Breite. Geprüft wird die **Summe**, nie eine nachgerechnete Einzelbreite.
  - Gleiche Höhe je Zeile, die letzte Zeile in Zielhöhe.
  - Eine Zeile über der Höchsthöhe steht wie die letzte.
  - Bei W ≤ 0 natürliche Breiten in Zielhöhe, ohne `NaN`.
- Untergrenzen als Streifzug über Verhältnis-Mischungen (0,5 / 0,56 / 0,75 / 1 / 2,4 / 7 / 20 / unbekannt) × Breiten (328 / 700 / 976), als feste Liste:
  - jede Kachel ≥ 130,
  - jede Bildfläche ≥ 44 hoch,
  - jede Kachel ≤ W,
  - alle Indizes kommen genau einmal und in Reihenfolge vor.
- Pflichtfälle: Gruppe mit 2 Mitgliedern, Einzelbild, zwei Hochformate bei 328 nebeneinander (Summe der Verhältnisse ≤ 1,38) und der Gegenfall knapp darüber, der umbricht.

**Komponente (vitest + Testing Library, `test/observers.ts` treibt die Breite):**
- `DuplicatePhotoTile`:
  - Der Test „`aspect-square` reserviert die Höhe“ wird ersetzt: Bildfläche und `li` tragen die übergebenen Inline-Maße schon vor dem Laden (PhotoImage gemockt), das `li` ist Breite + 20, das Bild trägt `object-contain`.
  - Die bestehenden Fälle zu Aufbau, Zuständen, Wahl, Vergrößern und Enter/Leertaste bleiben unverändert (AK4, AK5).
- `DuplicateComparePage`:
  - Nach `resize(976)` trägt die Liste `flex flex-wrap items-start gap-3`, die Kachelmaße kommen aus dem Raster.
  - Eine zweite Breite ergibt andere Maße.
  - Die Platzhalterliste hat dieselbe Achse und dieselben Klassen sowie 3:2-Inline-Maße samt Rand. Geprüft wird die Form, nicht die Anzahl (Testkonzept 0490 Punkt 7).
  - Der gemessene Ref hängt nach dem Laden an der echten Liste: Eine Breitenmeldung danach wirkt.
  - Die bestehenden Fokusrückgabe-Fälle bleiben.
- `DuplicateEnlargedView`:
  - Jeder Streifenknopf trägt `h-16 sm:h-20 min-w-11 max-w-full` und `aspectRatio` als bereinigte Zahl: Aus einem `null`-Verhältnis wird 1,5, nie `NaN`, nie eine Zeichenkette.
  - Das Bild trägt `object-contain`.
  - Der bestehende Fall zu Name und `aria-current` bleibt wörtlich (AK9), dazu `border-text-h` am aktuellen und `border-transparent` an den übrigen Knöpfen.
- Vertrag (`designSystem.*.contract.test.ts`):
  - Die drei Dateien kommen in die Regel „kein `object-cover`/`aspect-square`/`grid-cols-`“.
  - Kopplung `gap-3` ↔ `GRID_GAP_PX` an der Duplikatliste.
  - **Neue Kopplung** `DUPLICATE_TILE_INSET_X_PX` = 20 ↔ `px-2` an allen Breiten plus `border-2`: Ein `sm:px-3` an der Kachel muss rot werden.

**E2E (Playwright, beide Projekte 360/1280, nur was jsdom nicht kann):**
- `grid-columns.spec.ts`: Der Duplikat-Fall „2/3 Spalten, gleiche Breiten“ wird **ersetzt**, nicht gelockert; das ist eine benannte Erwartungsänderung (Spec 0374 AK3 entfällt). Gemessen wird an `duplicate-image` und am `li`, die Breite kommt vom Container:
  - gleiche Höhe und gleiche Oberkante je Zeile,
  - bündiges Ende jeder vollen Zeile,
  - die letzte Zeile ist nachweislich kürzer,
  - Kastenverhältnis gegen `naturalWidth/naturalHeight` (Demo: 4:3, 3:4, 12:5, 1:1, Vorbedingung ≥ 3 Formate),
  - verschiedene Kachelbreiten in der 7er-Gruppe,
  - jede Kachel ≥ 100 px.
- Extreme über `page.route` auf `**/duplicate-groups/*` mit `aspect_ratio` 0,3 / 20 / `null` (Muster `foto-karte-raster.spec.ts`), bei 360 px:
  - Das Kastenverhältnis ist die Grenze bzw. 3:2.
  - `objectFit` des Bildes ist `contain`.
  - Die Kachel ist ≥ 100 px, die Wahl liegt in der Kachel, die Bildfläche ist ≥ 44 px hoch, `scrollWidth ≤ clientWidth`.
- AK6, kein Sprung:
  - `page.route` hält `**/photos/*/image*` an.
  - Die Rechtecke aller Kacheln werden gemessen, dann werden die Anfragen freigegeben und erneut gemessen: identisch (±1).
  - Vorbedingung: Vor der Freigabe ist kein Bild geladen.
- `duplikat-vergleich.spec.ts`, Streifen:
  - gleiche Höhe je Reihe,
  - ≥ 44 × 44,
  - Breite gleich Höhe × Verhältnis innerhalb der Grenzen,
  - kein Feld breiter als der Streifen, kein waagerechtes Scrollen.
  - Extreme 0,3 und 20 über dieselbe Route: 44-px-Feld bzw. Breite gleich Streifenbreite.
- `tap-targets.spec.ts` und `no-horizontal-scroll.spec.ts` decken die Wahlknöpfe und den Duplikat-Pfad schon ab. Neu ist nur ein Streifenknopf mit Verhältnis 0,3 in `assertTappable`; beim Raster ändert sich nur der Kommentar „zwei Spalten“.

**Edge Cases:**
- Verhältnis genau auf 0,56 bzw. 7.
- `null` neben bekannten Verhältnissen in derselben Zeile.
- Gruppe mit 2 Mitgliedern.
- Mitglied ohne Wahl (Grund statt Wahlzeile, andere Kachelhöhe, Kacheln trotzdem oben bündig).
- „Ausschuss“ gedrückt (breiteste Schaltfläche) in der schmalsten Kachel.
- Größenänderung des Fensters bei geöffnetem Raster.
- Rundungsrest auf dem letzten Bild.
- Wechsel Großansicht → Raster: Die Messung greift wieder.

**Testkonzept `0002`: ergänzen**, als kurzer Abschnitt zu Spec 0638:
1. Abschnitt 0489, Punkt 8: „Der Duplikat-Teil bleibt unverändert“ ist überholt. Er misst jetzt die Zusagen des justierten Rasters.
2. Eine dritte „Wahrheit desselben Werts“: der Kachelrand als Rechengröße, gekoppelt an Klassen, die nicht von der Bildschirmbreite abhängen.
3. Ein neues E2E-Muster „kein Sprung beim Eintreffen“: Bildanfragen per Route anhalten und vorher/nachher messen statt warten. Dazu die Regel, dass sich eine Platzhalterform einmal durch die echten Verhältnisse ändern darf, beim Eintreffen der Bilddaten aber gar nicht.
4. Extreme Verhältnisse werden per Route am Gruppen-JSON geprüft, weil der Demo-Bestand bewusst nur Verhältnisse im Normalband trägt.

## Entscheidungen

- architect konsultiert (Schritt 1): keine neue ADR, Muster aus ADR 0110 mit eigenen Parametern.
- ux-ui-designer konsultiert (Schritt 2): Rand im Raster `--elevated`, im Streifen `bg-surface`; Kacheln unten nicht ausgeglichen.
- test-engineer konsultiert (Schritt 3): AK auf Testbarkeit geschärft (Toleranzen, Grenzverhältnisse 0,56/7).
- security-engineer konsultiert (Schritt 3): gering relevant, Auflagen aus Spec 0489/0531 gelten; Sicherheitskonzept bleibt unverändert.
- Daniel (Produktentscheidung, 2026-11-15): Eine volle Zeile, die bündig höher als 350 px würde, steht wie die letzte Zeile (280 px, linksbündig).
- Extreme Verhältnisse (< 0,56, > 7) werden im Grenzverhältnis eingepasst statt exakt dargestellt; sonst wären AK1 und AK3 gleichzeitig nicht haltbar.
- Spec 0374 AK3 (feste 2/3 Spalten, gleiche Kachelbreiten) gilt für die Vergleichsansicht nicht mehr; `e2e/tests/grid-columns.spec.ts` wird ersetzt, nicht gelockert.
- Am Telefon steht meist ein Bild je Zeile; das folgt aus AK1.
- Der Wechsel von Platzhaltern zum Raster darf die Zeilenaufteilung einmal ändern; „kein Sprung" gilt für das Eintreffen der Bilddaten.
- Testkonzept `0002` bekommt einen kurzen Abschnitt zu dieser Spec (Punkte aus der Teststrategie unten); Design-System `0004` und `docs/architecture.md` werden in der Umsetzung nachgezogen.

## Out of Scope

- Ausschuss-Übersicht samt Duplikat-Stapeln, Fotoübersicht, Kuratierung, Endauswahl, Einzelbild-
  und Detailansicht.
- Die Bühne der Großansicht (stellt bereits vollständig dar).
- Jede Änderung an Entscheidungen, Gruppenabschluss, Zuständen und Rückwegen.
