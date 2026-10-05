# 0579 - Kuratierungskacheln mit Foto im Mittelpunkt und Details bei Bedarf

**Status:** Accepted
**Erstellt:** 2026-10-05
**Bezug:** Issue [#579](https://github.com/TheRealKoller/photosort/issues/579), ADR [`0134`](../decisions/0134-kuratierungskachel-im-eigenen-seitenverhaeltnis-knoepfe-schrumpfen-aufs-symbol.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil Raster, Kachelaufbau, Symbolknöpfe und Bei-Bedarf-Leiste für Entwurf, Endauswahl und Alternativen in einer Spec stehen.

## Ziel

Beim Kuratieren (Album-Entwurf und Endauswahl) zeigen die Fotokacheln heute viel Beiwerk um ein kleines Bild: Hoch- und Querformate sitzen mit Leerraum in einer quadratischen Fläche, der Bewertungsgrund wird mit „…" abgeschnitten, die Wort-Kennzeichen „Vorschlag"/„Aufgenommen" und die Text-Schaltflächen brauchen viel Platz, und ein Info-„i" bietet Angaben, die beim Kuratieren nicht gebraucht werden.

Ziel: Das Foto steht im Mittelpunkt und füllt seine Kachel ohne Leerraum. Immer sichtbar ist nur, was für die Entscheidung zählt — der Zustand als kompaktes Symbol und die beiden Handgriffe. Bewertungsgrund, Albumtauglichkeit und Dateiname erscheinen bei Bedarf vollständig. Betrifft beide Nutzer gleichermaßen.

Gilt für alle Fotokacheln der Kuratierung: Album-Entwurf, Endauswahl sowie die Alternativen in Band und aufgeklappter Reihe.

Abhängigkeit: nach #578 und #577 umsetzen, die dieselben Kacheln verändern.

Entwurf: Penpot-Arbeitsseite „Entwurf — Kuratierungskarte", Brett „R3 V2 — Symbol + Kurzwort, Pfeile im Kreis" (Zeilenhöhe dort 260 px; vereinbart sind etwa 280 px).

## User Story

Als Nutzer, der beim Kuratieren viele Fotos sichtet, möchte ich Kacheln, auf denen das Foto groß und vollständig zu sehen ist und nur das Nötige immer sichtbar steht, während Grund und Details bei Bedarf vollständig erscheinen, damit ich schneller und besser entscheiden kann.

## Akzeptanzkriterien

**Foto und Raster**

- [ ] AK1 — Jedes Foto mit Seitenverhältnis ≥ 1:2 ist unbeschnitten und randlos zu sehen: Die Bildfläche hat das Seitenverhältnis des Fotos (±1 px), ohne Polsterung, Kartenfläche oder Rahmen. Alle Kacheln einer Reihe sind gleich hoch (±1 px). Jede volle Reihe endet bündig mit der Containerbreite (±1 px).
- [ ] AK2 — Ein Foto schmaler als 1:2 belegt ein Feld im Verhältnis 1:2 und ist darin vollständig eingepasst (`object-contain`). Ein Foto ohne bekanntes Seitenverhältnis (`aspect_ratio = null`) wird wie 3:2 geplant und ebenfalls eingepasst. In beiden Fällen gibt es keinen Beschnitt.
- [ ] AK3 — Bei 1280 px Breite ist eine volle Reihe zwischen 200 und 350 px hoch, Ziel 280 px. Eine Reihe, die bündig höher als 350 px würde, steht stattdessen wie eine letzte Reihe: 280 px hoch, linksbündig, nicht gestreckt. Das gilt auch für ein einzelnes Hochformat bei 360 px.
- [ ] AK4 — Jede Kachel ist mindestens 100 px breit. Damit passen zwei 44-px-Knöpfe mit 12 px Abstand nebeneinander.
- [ ] AK5 — Gilt für die Eventgruppen, die Gestrichen-Zeile, das Alternativen-Band, die aufgeklappte Reihe, das Hinzufügen-Panel, die Bezugsmarke „Wird ersetzt“, die Arbeits- und Ergebnissicht der Endauswahl und die Ladeplatzhalter. Nirgends bleibt eine quadratische Bildfläche (`aspect-square`) oder ein Spaltenraster (`PHOTO_CARD_GRID_CLASS`).
- [ ] AK6 — Das Band und das Hinzufügen-Panel stehen direkt nach der gerechneten Reihe ihrer auslösenden Kachel, nicht nach einer festen Spaltenzahl.

**Immer sichtbar**

- [ ] AK7 — Oben links in der Bildecke steht ein Zustandszeichen nur aus Symbolen, auf undurchsichtigem Chip: Vorschlag `cog`+`book`, Aufgenommen `book` (gefüllt), Gestrichen/Herausgenommen `x-circle` (gefüllt). Ohne Farbe sind die drei an Anzahl und Form der Symbole unterscheidbar. Sichtbares Wort: keines. Das Zeichen hat `role="img"`. Sein zugänglicher Name ist genau „Vorschlag“, „Aufgenommen“, „Aufgenommen, nicht vorgeschlagen“ oder „Gestrichen“, und zwar aus `utils/albumStateLabels.ts`.
- [ ] AK8 — Die Entwurfskachel trägt unter dem Bild nebeneinander „Streichen“ (`x-circle`) und „Alternativen“ (`repeat`). „Alternativen“ öffnet das Band dieses Fotos wie bisher (`aria-expanded`/`aria-controls`). „Tauschen“ (`repeat`) steht ausschließlich an Alternativen in Band und aufgeklappter Reihe. *(Entscheidung Daniel)*
- [ ] AK9 — Knöpfe je Variante: Gestrichen-Zeile „Wieder aufnehmen“ (`book`). Band/Reihe „Tauschen“ + „Hinzufügen“ (`plus`). Hinzufügen-Panel „Hinzufügen“. Endauswahl strittig „Aufnehmen“ (`book`) + „Nicht aufnehmen“ (`x-circle`). Endauswahl einfach „Aufnehmen“ bzw. „Herausnehmen“ (`x-circle`). In beiden Formen lautet der zugängliche Name jedes Knopfs `{Handlung}: {Dateipfad}`.
- [ ] AK10 — Ist eine Kachel schmaler als die volle Knopfzeile ihrer Variante (Entwurf 208, Gestrichen 146, Band/Reihe 206, Panel 102, Endauswahl strittig 248, Endauswahl einfach 124 px), zeigen **alle** ihre Knöpfe nur das Symbol, sonst alle Symbol und Wort. Gemischte Zeilen gibt es nicht. Die Entscheidung hängt allein an der gerechneten Kachelbreite. Genau an der Schwelle steht das Wort. Im Symbolmodus erscheint das Kurzwort beim Überfahren und bei Tastaturfokus über dem Knopf, nie außerhalb der Kachel. Am Telefon erscheint es nicht.
- [ ] AK11 — Die Knopfzeile bricht nie um und ist nicht breiter als ihre Kachel. Kein Knopf ragt in eine Nachbarkachel.
- [ ] AK12 — Läuft ein Handgriff, ersetzt der Spinner das Symbol. Breite und Wort des Knopfs bleiben, der Knopf ist deaktiviert. Ein Fehler des Handgriffs steht wie bisher als `role="alert"` unter der Knopfzeile und bricht innerhalb der Kachelbreite um.
- [ ] AK13 — Auf keiner Kuratierungskachel gibt es noch einen Auslöser „Bewertungsdetails anzeigen“ (Info-„i“) oder einen Motiv-Marker. Feinlabels, Motive und Kriterien entfallen dort ersatzlos. Ebenso entfallen die Statuszeile mit Dateiname, „Neu“ und `RatingBadge`.

**Bei Bedarf**

- [ ] AK14 — Über dem unteren Bildrand steht eine undurchsichtige Leiste mit dieser Reihenfolge: (1) Bewertungsgrund, (2) Albumtauglichkeit als Stufe mit Wort, gegebenenfalls „· nicht vorgeschlagen“, (3) Dateiname, bei Gestrichen durchgestrichen. Sichtbar wird sie: beim Überfahren, nur auf Geräten mit `(hover: hover) and (pointer: fine)`; bei Fokus auf **jedem** Bedienelement der Kachel (Bildauslöser, beide Knöpfe); nach einem Druck von ≥ 500 ms. Ein Druck < 500 ms zeigt sie nicht.
- [ ] AK15 — Ein langer Druck öffnet weder die Großansicht noch einen Knopf. Ein Tipp anderswo oder Scrollen schließt die Leiste wieder.
- [ ] AK16 — Der Bewertungsgrund steht vollständig, auch bei 160 Zeichen in einer 100 px breiten Kachel: kein „…“, kein `line-clamp`, keine Kürzung der Zeichenkette, kein Lauftext, keine Animation. Die Leiste ist höchstens so hoch wie das Bild.
- [ ] AK17 — Hat ein Foto keinen Grund (`reason = null`), fehlt seine Zeile vollständig: kein Platzhalter, kein leeres Element. Die Leiste beginnt dann mit der Albumtauglichkeit.
- [ ] AK18 — Die Leiste steht immer im DOM, im Ruhezustand `sr-only`. Ein Bildschirmleser liest je Kachel in dieser Reihenfolge: Bildname, Zustandswort, Grund, Tauglichkeit, Dateiname, Knöpfe. Kurzbeschriftungen und Symbole sind `aria-hidden`.

**Allgemein**

- [ ] AK19 — Entwurf, Endauswahl, Band, aufgeklappte Reihe und Panel nutzen dieselbe Kachel. Zustandsbegriffe und Knopfwörter sind in Entwurf und Endauswahl gleich. Die Haltungszeilen der Endauswahl zeigen je Teilnehmer dasselbe Symbolzeichen, das Wort ist ihr zugänglicher Name.
- [ ] AK20 — „Foto hinzufügen“ bleibt die letzte Zelle jeder Eventgruppe: Verhältnis 2:3, so hoch wie Bild plus Knopfzeile der Reihe, Symbol `plus` statt Textzeichen `+`, bestehendes `aria-label`.
- [ ] AK21 — Bei 360 px scrollt keine der folgenden Ansichten waagerecht (`scrollWidth ≤ clientWidth`): Album-Entwurf im Ruhezustand, mit offenem Band (zugeklappt und aufgeklappt), mit offenem Panel und mit eingeblendeten Gestrichenen; Endauswahl in Arbeits- und Ergebnissicht.
- [ ] AK22 — Bei 360 px sind alle Handgriffe der Kacheln sichtbar ≥ 44 × 44 px groß, stehen nebeneinander mit ≥ 12 px Abstand und sind einzeln treffbar (Treffertest an allen vier Ecken). Ab `sm` sind sie sichtbar 32 px hoch.

Zur Spec: AK „Tauschen öffnet die Alternativen“ aus der Story ist durch AK8 ersetzt. Option C (rund 280 px Zeilenhöhe, randlos, Symbolknöpfe bei schmalen Kacheln, Wort wird vorgelesen) steckt in AK1, AK3, AK10 und AK18.

## Datenmodell-Bezug

Keine Änderung. Genutzt wird das vorhandene `PhotoOut.aspect_ratio`.

## Architektur / Umsetzung

**Ansatz.** Nur das Frontend ändert sich: kein Endpunkt, kein Feld, keine Abhängigkeit. `PhotoOut.aspect_ratio` liegt auf allen Lesepfaden vor, auch für Entwurf, Alternativen und Endauswahl (ADR 0110 Punkt 1). Wiederverwendet werden das justierte Zeilenraster der Fotoübersicht (`utils/justifiedRows.ts`) und der Bei-Bedarf-Mechanismus von `PhotoGridTile`. Entscheidung: ADR [`0134`](../decisions/0134-kuratierungskachel-im-eigenen-seitenverhaeltnis-knoepfe-schrumpfen-aufs-symbol.md). Sie löst ADR 0110 Punkt 5 für die Fotokarte ab.

### 1. Raster: justierte Reihen statt Spaltenraster

- **`PHOTO_CARD_GRID_CLASS` entfällt.** Betroffen sind die Eventgruppe samt Hinzufügen-Feld, die Gestrichen-Zeile, Band und aufgeklappte Reihe, das Hinzufügen-Panel, die Gruppen der Endauswahl und alle Platzhalter. Jedes dieser Raster wird `ul`/`ol` mit `flex flex-wrap gap-3`, wie in `PhotoGridPage`. Kachelbreite und Bildhöhe gehen als gerechnete **Zahl** in `style`, nie als Zeichenkette oder Custom-Property (Auflage S6 wie bei `PhotoGridTile`).
- **Konstanten** in `utils/curationLayout.ts`:
  - `CURATION_TARGET_ROW_HEIGHT_PX = 280`, `CURATION_MIN_ROW_HEIGHT_PX = 200`, `CURATION_MAX_ROW_HEIGHT_PX = 350`. Der Abstand ist `GRID_GAP_PX` (12 = `gap-3`).
  - `ICON_HANDLES_WIDTH_PX = 100`: zwei 44-px-Symbolknöpfe mit 12 px Abstand.
  - `MIN_PLANNING_RATIO = ICON_HANDLES_WIDTH_PX / CURATION_MIN_ROW_HEIGHT_PX` (= 0,5).
- **Planung je Foto:** `max(aspect_ratio ?? 3/2, MIN_PLANNING_RATIO)`. Jedes Foto ab 1:2 ist damit randlos; 9:16 und 9:19,5 liegen darüber. Ein noch schmaleres Foto wird in seinem Feld eingepasst (`object-contain`). Das ist dieselbe Ausfallrichtung wie bei `null` (ADR 0110).
- **`justifiedRows` bekommt einen optionalen Parameter `maxRowHeight`.** Eine Reihe, deren bündige Höhe darüber läge, wird wie die letzte Reihe gesetzt: Zielhöhe, natürliche Breiten, linksbündig. So steht ein einzelnes Hochformat am Telefon nicht auf voller Breite (≈ 490 px hoch). Ohne den Parameter bleibt alles wie bisher; `PhotoGridPage` und `AusschussStepPage` sind nicht betroffen.
- **Neuer Hook `hooks/useJustifiedRows.ts`:** `useElementWidth` plus Verhältnisse plus Konstanten ergeben **Reihen** (`JustifiedRow[]`). Vor der ersten Messung gilt `naturalTiles`. Die Reihen braucht das Band.
- **Band und Hinzufügen-Panel** sind ein `<li class="w-full">` (statt `col-span-full`) direkt nach dem letzten `<li>` der **gerechneten** Reihe der auslösenden Kachel. `columnCount()` und der `resize`-Listener in `DraftEventSection` entfallen. Im Inneren rechnet ein eigener `useJustifiedRows` mit der Innenbreite; die Bezugsmarke „Wird ersetzt“ ist darin eine Zelle mit eigenem Verhältnis.
- **Hinzufügen-Feld:** Zelle mit festem Planungsverhältnis 2:3, gleiche Höhe wie die Kacheln seiner Reihe (Bild plus Knopfzeile), letzte Zelle der Gruppe. Das Textzeichen `+` wird zu `<Icon name="plus" />`.
- **Platzhalter:** `naturalTiles(nulls, CURATION_TARGET_ROW_HEIGHT_PX)` wie in `PhotoGridPage`. `aspect-square` entfällt.
- **Am Telefon (360 px, Inhalt ≈ 328 px):** Zwei Hochformate 2:3 teilen sich eine Reihe (≈ 237 px hoch, je ≈ 158 px breit, Symbolknöpfe). Ein Querformat steht allein (≈ 328 × 219 px, Kurzwörter). Waagerechtes Scrollen kann nicht entstehen, weil jede volle Reihe bündig auf die Containerbreite gerechnet ist.

### 2. Die Kachel: `PhotoCard` wird die eine formatfolgende Kuratierungskachel

`components/PhotoCard.tsx` wird umgebaut, nicht verdoppelt. Neu benutzt sie auch die Kandidaten in Band, Reihe und Panel, die bisher in `DraftAlternativesBand.tsx` von Hand gebaut sind. Aufbau, zugleich DOM- und Fokusreihenfolge:

1. Bildfläche: `width`/`height` gerechnet, `object-contain`, keine Polsterung um das Bild. Sie bleibt Auslöser der Großansicht, wo sie es heute ist.
2. Zustandskennzeichen oben links, als Geschwister der beschneidenden Fläche.
3. Bei-Bedarf-Leiste über dem unteren Bildrand.
4. Knopfzeile `flex gap-3`, ohne Umbruch, Breite = Kachelbreite.
5. Fehlermeldung des Handgriffs (wie bisher).

Es entfallen die Statuszeile mit Dateiname, `Neu` und `RatingBadge`, die von keinem Aufrufer gesetzten Props `status`/`favorite`/`suggested`, `topRight` und `aspect-square`. Erhalten bleiben `setAside` (durchgestrichener Dateiname, jetzt in der Leiste), `anchored` und ADR 0112.

### 3. Zustand als Symbol in der Bildecke

- `AlbumStateBadge` zeigt nur noch Symbole, mit `role="img"` und dem vollen Wort als `aria-label`:
  - Vorschlag: `cog`+`book` auf der Vorschlags-Konstruktion.
  - Aufgenommen: `book`, gefüllt.
  - Gestrichen: `x-circle`, gefüllt.
- Die Fläche des Badges ist undurchsichtig, der Kontrast bleibt also nachrechenbar. Die drei Zustände sind ohne Farbe an der Symbolfolge unterscheidbar.
- **`utils/albumStateLabels.ts` bleibt unverändert die eine Begriffsquelle**; die Wörter werden zu zugänglichen Namen.
- „nicht vorgeschlagen“ (`NOT_PROPOSED_BADGE_TEXT`) erscheint in der Leiste und im Namen des Kennzeichens („Aufgenommen, nicht vorgeschlagen“).
- Endauswahl: Die Haltungszeilen je Teilnehmer bleiben sichtbar. Ihr Kennzeichen wird dasselbe Symbolzeichen (Name davor `truncate`, Wort als zugänglicher Name).

### 4. Knöpfe: Symbol + Kurzwort, in schmalen Kacheln nur Symbol

- **Neuer Baustein `components/TileAction.tsx`.** Props: `icon`, `label`, `accessibleName`, `iconOnly`, `busy`, `align: 'start' | 'end'` und die Button-Props. Darunter liegt `Button`, je nach Modus in einer von zwei Größen:
  - **beschriftet:** neue Größe `compact` in `ui/button.tsx` (`h-8 min-w-8 gap-1 px-2`, `tap-target`), Symbol 14 px plus Wort;
  - **nur Symbol:** bestehende Größe `icon` (`size-8`, `tap-target-square`).
  - Auf dem heißen Pfad am Telefon sind beide sichtbar 44 px (`h-11 sm:h-8` bzw. `size-11 sm:size-8`). Die Fundstellen kommen in `TALL_CONTROL_ALLOWLIST`.
  - Der zugängliche Name ist in beiden Formen `{Handlung}: {Pfad}`.
  - Bei `busy` **ersetzt** der Spinner das Symbol, statt neben ihm zu stehen. Sonst wüchse ein beschrifteter Knopf über die angesetzte Breite.
- **Wann eine Kachel auf „nur Symbol“ schaltet:** `iconOnly = tile.width < HANDLES_FULL_WIDTH_PX[kind]`. Die Entscheidung ist eine reine Funktion der gerechneten Breite, ohne DOM-Messung, damit nichts pendelt. Sie gilt für **alle** Knöpfe der Kachel; gemischte Zeilen gibt es nicht. Die Werte stehen je Kachel als Konstante. Grundlage sind die Inter-600-Laufweiten bei 12 px plus Symbol 14, Abstand 4, Polsterung 2 × 8 und 12 px zwischen zwei Knöpfen:
  - Entwurf (`Streichen` `x-circle` + `Alternativen` `repeat`): **208**
  - Gestrichene Kachel (`Wieder aufnehmen` `book`): **146**
  - Band/Reihe (`Tauschen` `repeat` + `Hinzufügen` `plus`): **206**
  - Hinzufügen-Panel (`Hinzufügen` `plus`): **102**
  - Endauswahl strittig (`Aufnehmen` `book` + `Nicht aufnehmen` `x-circle`): **248**
  - Endauswahl einfach (`Aufnehmen` / `Herausnehmen` `x-circle`): **124**
- **Kurzbeschriftung bei Überfahren und Fokus** (nur im Symbol-Modus):
  - Ein `<span aria-hidden>` mit dem Kurzwort steht `absolute bottom-full` über dem Knopf.
  - Am ersten Knopf ist es linksbündig ausgerichtet (`left-0`), am zweiten rechtsbündig (`right-0`).
  - `max-w` ist die Kachelbreite, Umbruch ist erlaubt. So verlässt es die Kachel nie.
  - Fläche `bg-overlay`, Rand `border-border-control`, `text-xs text-text-h`, `pointer-events-none`. Es liegt über der Leiste.
  - Sichtbar wird es über `group-hover` (Tailwind bindet `hover:` an `(hover: hover)`) und `group-focus-visible`.
  - Am Telefon gibt es keine Kurzbeschriftung; Symbol und vorgelesener Name tragen. Die Symbole sind auf breiten Kacheln dieselben, mit Wort.
- **Touch-Treffbarkeit:** Symbolknöpfe sind am Telefon sichtbar 44 × 44 mit 12 px Abstand und damit einzeln treffbar. Die Planungsuntergrenze aus Abschnitt 1 sichert die 100 px dafür in jeder Kachel.
- **Symbolsatz +2: `repeat`, `plus`** über die vier Stellen: `ui/icon.tsx` (Zählzusage im Doku-Block), `frontend/penpot/icons.test.ts`, `design/penpot/verify.js::ERWARTETE_SYMBOLE` und der Freigabeeintrag in `frontend/penpot/payload.test.ts`. Dazu die Namensliste in `ui/icon.test.tsx` (22). Die Lücke `+` als Textzeichen entfällt.

### 5. Bei Bedarf: Leiste über dem unteren Bildrand

- **`hooks/useRevealOnDemand.ts`** wird aus `PhotoGridTile` herausgezogen:
  - Herkunft `hover`/`focus`/`press`; `(hover: hover) and (pointer: fine)` wird einmal gelesen.
  - `LONG_PRESS_MS = 500`.
  - Nach einem Druck schließt `pointerdown` (capture) oder `scroll` die Leiste.
  - Der Klick nach einem langen Druck wird unterdrückt.
  - `PhotoGridTile` wird verhaltensgleich umgestellt; seine Tests sind das Regressionsnetz.
  - In der Kuratierung unterdrückt der lange Druck das Öffnen der Großansicht.
  - Fokus auf einem beliebigen Bedienelement der Kachel blendet die Leiste ein (`onFocus` am `<li>`).
- **Inhalt:**
  - Bewertungsgrund **vollständig**, ohne `line-clamp` und ohne Bewegung. Er erscheint nur bei `album_suitability.reason !== null`; ohne Grund gibt es keinen Platzhalter und keine leere Zeile.
  - `QualityMeter` (Stufe mit Wort).
  - bei Bedarf „nicht vorgeschlagen“.
  - Dateiname (`font-mono break-all`, durchgestrichen bei `setAside`).
  - Fläche `bg-overlay`, undurchsichtig, `pointer-events-none`.
- **Steht immer im DOM**, im Ruhezustand `sr-only`. Das ist bewusst anders als bei `PhotoGridTile`, damit der Grund für Bildschirmleser erreichbar bleibt.
- **Höhe:** keine Viertel-Schranke, als Sicherung `maxHeight` = Bildhöhe (Zahl). Ein Grund hat höchstens 160 Zeichen. In einer schmalen Kachel (≥ 100 px) kann die Leiste damit höher werden als ein Viertel; der Grund bleibt trotzdem vollständig, weil `maxHeight` erst bei der Bildhöhe greift.
- **Der Info-Auslöser entfällt ersatzlos.** `CriterionDetailsPopover` hat nur die Aufrufstelle `CurationPhotoTile`; die Datei samt Test wird gelöscht. Ebenso `MotifAssessmentMarker`, dessen einziger Aufrufer dieselbe Kachel ist.
  - `CurationPhotoTile` verliert `motifSet*` und `onMotifSetRetry`.
  - `AlbumDraftPage` behält `useMotifsQuery`, weil die Motivzeile je Event es liest.
  - `ui/popover.tsx` bleibt (`Stepper`, Kopfzeile). Seine Kommentare verweisen künftig auf `Stepper.tsx`.

### Reihenfolge

1. `justifiedRows` (`maxRowHeight`), `utils/curationLayout.ts` und `hooks/useJustifiedRows.ts`, reine Funktionen zuerst.
2. `hooks/useRevealOnDemand.ts`, dann `PhotoGridTile` umstellen (Bestandstests grün).
3. `ui/button.tsx` `compact`; Symbole `repeat` und `plus` an allen vier Stellen; `TileAction`.
4. `AlbumStateBadge`.
5. `PhotoCard`.
6. `CurationPhotoTile`, `SelectionPhotoTile`, Kandidaten und `ReferenceMarker`.
7. Raster in `DraftEventSection`, `AlbumDraftPage`, `AlbumSelectionPage` und `DraftAlternativesBand`.
8. Löschungen samt Freigabeeinträgen.
9. E2E und Doku.

### Abgelöste Aussagen

Die Specs bleiben als Historie unverändert. Die laufende Doku wird nachgezogen.

- ADR 0110 Punkt 5 für die Fotokarte: abgelöst durch ADR 0134.
- Spec 0563: AK4, quadratische Fläche, `PHOTO_CARD_GRID_CLASS`, Spaltenleiter 2/3/4.
- Spec 0558: Handgriffe „untereinander“, Kennzeichen als Wort im Kartenkörper.
- Spec 0569 und Spec 0578 Punkt 5: Bezugsmarke und Raster `aspect-square`.
- Spec 0428: Grund per `line-clamp`, Popover in der Kuratierung.
- 0004-design-system: Lücke `+` (Spec 0578).

## UI/UX

## Design

**Stand:** Arbeitsstand
**Penpot-Seite:** Entwurf — Kuratierungskarte
**Schlüssel:** kuratierungskarte

**Offener Punkt Entwurf:** `kuratierungskarte` ist der Schlüssel einer Penpot-Arbeitsseite und steht nicht in `design/penpot/views.json`. Breiten, Zustände und Lücken lassen sich deshalb nicht aus dem Register übernehmen. Maßgeblich ist der folgende Text. Das Brett „R3 V2 — Symbol + Kurzwort, Pfeile im Kreis“ zeigt 260 px Zeilenhöhe; vereinbart und umgesetzt werden 280 px (`CURATION_TARGET_ROW_HEIGHT_PX`).

**Gilt für** Album-Entwurf (Eventgruppen, Gestrichen-Zeile, Band, aufgeklappte Reihe, Hinzufügen-Panel) und Endauswahl. Alle diese Kacheln sind dieselbe `PhotoCard`.

### Kachelaufbau (von oben nach unten, zugleich Fokusreihenfolge)

1. **Bildfläche** im eigenen Seitenverhältnis, `object-contain`, `rounded-md`, ohne Polsterung, ohne Kartenfläche dahinter und ohne Rahmen. Volle Helligkeit auch bei Gestrichen/Herausgenommen (ADR 0112). Ein Foto schmaler als 1:2 wird in seinem Planungsfeld eingepasst; der Rest des Feldes ist `--bg`, also kein eigener Ton.
2. **Zustandszeichen oben links** (`left-1 top-1`) als Geschwister der beschneidenden Fläche. Aufbau wie das Eckzeichen der Rasterkachel: undurchsichtiger Chip `bg-overlay rounded-sm p-1`, `pointer-events-none`, darin die Symbole in 14 px, ohne Wort.
   - Vorschlag: `cog` + `book` in `--accent-2` als Umriss-Konstruktion des Vorschlags. Der Ring der Vorschlags-Badge sitzt auf dem undurchsichtigen Chip, nie unmittelbar auf dem Foto, weil die 10–12-%-Fläche über einem Foto keinen nachrechenbaren Kontrast hat.
   - Aufgenommen: `book` in `--accent-2`, gefüllt.
   - Gestrichen/Herausgenommen: `x-circle` in `--danger`, gefüllt.
   - Ohne Farbe unterscheidbar über Anzahl und Form der Symbole (zwei Symbole, ein Buch, ein Kreuz im Kreis).
   - `role="img"`. Der zugängliche Name ist das volle Wort aus `utils/albumStateLabels.ts` („Vorschlag“, „Aufgenommen“, „Gestrichen“), gegebenenfalls „Aufgenommen, nicht vorgeschlagen“. Kein `title`, kein Fokus, keine Trefferfläche.
3. **Bei-Bedarf-Leiste** über dem unteren Bildrand (siehe unten).
4. **Knopfzeile** direkt unter dem Bild, Abstand `mt-2`, `flex gap-3`, ohne Umbruch, genau so breit wie die Kachel. Erster Knopf am linken Rand, zweiter am rechten (`justify-between`), sodass in jeder Kachel die gleiche Handlung an der gleichen Stelle steht.
5. **Fehlermeldung des Handgriffs** unter der Knopfzeile, unverändert (`text-xs text-danger-text`, `role="alert"`). Sie bricht innerhalb der Kachelbreite um.

Es entfallen: das Info-„i“, die Statuszeile mit Dateiname/`Neu`/`RatingBadge`, die quadratische Fläche, die Kartenfläche `--elevated` hinter dem Bild und der gekürzte Grund in der Fußzeile.

### Kompakte Schaltflächen (`TileAction`)

- **Variante `outline`** (Sekundär: Umriss `--border-control`, Fläche `--overlay`). Die Ausprägung `destructive` bleibt nach der Kollisionsregel in der Kuratierung verboten, auch für „Streichen“.
- **Beschriftet:** Größe `compact`, Symbol 14 px, Wort `text-xs font-semibold` (Inter 600, 12 px), `gap-1 px-2`. Am Telefon `h-11`, ab `sm:` `h-8`.
- **Nur Symbol:** Größe `icon`, am Telefon `size-11`, ab `sm:` `size-8`, Symbol 14 px.
- **Umschaltschwelle:** `iconOnly = Kachelbreite < HANDLES_FULL_WIDTH_PX[kind]` (Entwurf 208, Gestrichen 146, Band/Reihe 206, Panel 102, Endauswahl strittig 248, Endauswahl einfach 124). Sie gilt immer für alle Knöpfe einer Kachel, gemischte Zeilen gibt es nicht. Grundlage ist allein die gerechnete Breite, damit beim Laden nichts umspringt.
- **Symbole und Wörter:** Streichen `x-circle` · Alternativen `repeat` · Wieder aufnehmen `book` · Tauschen `repeat` · Hinzufügen `plus` · Aufnehmen `book` · Nicht aufnehmen / Herausnehmen `x-circle`. „Tauschen“ steht nur an Alternativen in Band und Reihe (Spec 0578). Der Knopf an der Entwurfskachel heißt „Alternativen“, Entscheidung Daniel.
- **Zugänglicher Name** in beiden Modi `{Handlung}: {Dateipfad}`.
- **Kurzbeschriftung im Symbolmodus:** Bei Überfahren und bei `:focus-visible` erscheint über dem Knopf das Kurzwort (`aria-hidden`, `bg-overlay`, Rand `border-border-control`, `rounded-sm px-1.5 py-0.5`, `text-xs text-text-h`, `pointer-events-none`). Am ersten Knopf ist sie linksbündig, am zweiten rechtsbündig, höchstens kachelbreit, mit Umbruch. Sie liegt über der Leiste und erscheint ohne Animation. Am Telefon gibt es keine Kurzbeschriftung.
- **Busy:** Der Spinner ersetzt das Symbol, Wort und Breite bleiben, der Knopf ist deaktiviert (Busy-Button-Muster).
- **Touch bei 360 px:** Die Knöpfe sind sichtbar 44 × 44 mit 12 px Abstand; jede Kachel ist mindestens 100 px breit (Planungsuntergrenze 1:2). Zwei 2:3-Fotos teilen sich eine Reihe (je ≈ 158 px breit, Symbolmodus), ein Querformat steht allein (≈ 328 px, mit Wort). Waagerechtes Scrollen ist ausgeschlossen. Die Knopfzeile liegt außerhalb jedes beschneidenden Containers, damit `tap-target` nicht abgeschnitten wird.

### Bei-Bedarf-Leiste

- **Auslöser** aus `useRevealOnDemand`, verhaltensgleich zur Rasterkachel: Überfahren nur bei `(hover: hover) and (pointer: fine)`, Fokus auf irgendeinem Bedienelement der Kachel (Bildauslöser, Knöpfe), am Telefon ein Druck von mindestens 500 ms. Der lange Druck öffnet die Großansicht ausdrücklich nicht. Ein Tipp anderswo oder Scrollen schließt die Leiste wieder. Keine Angabe ist nur per Maus erreichbar.
- **Inhalt in dieser Reihenfolge** (zuerst, was die Entscheidung trägt):
  1. Bewertungsgrund, vollständig, `text-xs text-text-h`, Umbruch frei, ohne `line-clamp`, ohne Lauftext, ohne Bewegung.
  2. Eine Zeile Albumtauglichkeit: `QualityMeter` (Punkte `aria-hidden` plus Stufenwort), `text-xs text-text`. Wo zutreffend folgt „· nicht vorgeschlagen“ in derselben Zeile. Kein Badge, keine Bewertungsfarbe (Muster „Schätzung eines Modells“).
  3. Dateiname als Basisname, `font-mono text-xs text-text`, `break-all`. Bei `setAside` durchgestrichen in `--text-muted`.
- **Fläche** `bg-overlay`, undurchsichtig, `px-2 py-1.5`, Zeilenabstand `gap-1`, bündig an der Unterkante der Bildfläche, Ecken unten folgen `rounded-md`. Keine Ein- oder Ausblendanimation.
- **Ohne Grund** (`reason === null`) entfällt Zeile 1 restlos: kein Platzhalter, kein Leerraum, die Leiste beginnt mit der Albumtauglichkeit.
- **Höhe:** Es gibt keine Viertel-Schranke; die Leiste wächst mit dem Inhalt bis höchstens zur Bildhöhe. Bei höchstens 160 Zeichen und einer Kachel von mindestens 100 px Breite bleibt der Grund vollständig. In schmalen Kacheln darf sie einen großen Teil des Bildes überdecken, solange sie offen ist.
- **Bildschirmleser:** Die Leiste steht immer im DOM, im Ruhezustand `sr-only`. Sie folgt im Lesefluss auf das Zustandszeichen und steht vor den Knöpfen.

### Varianten

- **Entwurf:** Streichen + Alternativen. Die Kachel, deren Alternativen offen sind, behält ihre bestehende Bezugsmarkierung. Die Bezugsmarke „Wird ersetzt“ im Band ist eine Zelle mit eigenem Verhältnis und derselben Bildbehandlung.
- **Gestrichen-Zeile:** `x-circle`-Zeichen und ein Knopf „Wieder aufnehmen“ (`book`).
- **Band / aufgeklappte Reihe:** Tauschen + Hinzufügen. **Hinzufügen-Panel:** nur Hinzufügen. Die Zustandszeichen folgen den Daten des Kandidaten.
- **Endauswahl:** Aufnehmen / Nicht aufnehmen bzw. ein Knopf. Die Haltungszeilen je Teilnehmer unter der Knopfzeile bleiben: Name `truncate` `text-xs text-text`, dahinter dasselbe Symbolzeichen ohne Wort, das volle Wort ist der zugängliche Name. Begriffe wie im Entwurf.

### „Foto hinzufügen“-Zelle

Letzte Zelle der Eventgruppe mit Planungsverhältnis 2:3, gleich hoch wie Bild plus Knopfzeile der Nachbarkacheln. Sie bleibt der gestrichelte Leerplatz (Rand `--separator` gestrichelt, `rounded-md`), mittig `<Icon name="plus" />` (20 px, aria-hidden) über dem Wort „Foto hinzufügen“ (`text-sm text-text`). Die ganze Zelle ist der Knopf mit dem bestehenden `aria-label`.

### Zustände

- **Laden:** Skeleton-Kacheln in `--text-disabled` in natürlicher Breite zur Zielhöhe (`naturalTiles`), mit einem Block für die Knopfzeile darunter, damit beim Eintreffen nichts springt. Ohne quadratische Platzhalter.
- **Bild lädt nicht:** die Platzhalterfläche des Bildes (`--separator`) im geplanten Format; Zeichen, Leiste und Knöpfe bleiben bedienbar.
- **Leer** (Gruppe ohne Fotos, keine Alternativen): unverändert. Die Hinzufügen-Zelle steht weiterhin.
- **Fehler:** Seitenladefehler unverändert als Alert mit „Erneut versuchen“. Fehler eines Handgriffs inline unter der Knopfzeile der betroffenen Kachel.

### Tastatur und Bildschirmleser

- Tab-Reihenfolge je Kachel: Bildauslöser (Großansicht, wo heute vorhanden) → erster Knopf → zweiter Knopf. Jeder Fokus in der Kachel blendet Leiste und Kurzbeschriftung ein. Fokusdarstellung allein über die globale `:focus-visible`-Regel.
- Vorgelesen werden je Kachel: Bildname wie bisher, Zustandswort, Grund/Tauglichkeit/Dateiname aus der Leiste, dann Knöpfe mit `{Handlung}: {Pfad}`. Symbole sind `aria-hidden`, die Kurzbeschriftung ist `aria-hidden`.

### Design-System

Das Design-System (`specs/architecture/0004-design-system.md`) und die Schnellreferenz `.claude/skills/design-system/SKILL.md` werden nachgezogen, siehe Liste der Doku-Änderungen.

## Security

**Sicherheitsrelevant, aber mit geringer Tragweite.** Das Feature bringt weder einen Endpunkt noch eine Nutzereingabe noch eine Sichtbarkeitsänderung zwischen den beiden Nutzern. Neu ist eine **Renderstelle** für einen Wert, der schon als Angriffsträger bekannt ist: `album_suitability.reason`. Der Grund ist freier Modelltext zu einem Bild, das selbst Text enthalten kann, und lässt sich damit per Prompt-Injection steuern. Serverseitig ist er saniert (`_sanitize_label_text`) und auf höchstens 160 Zeichen gekürzt (Securitykonzept, Ankerzeile Spec 0428). Er wird künftig **vollständig** und ohne `line-clamp` gezeigt. Das Session-Token liegt in `localStorage`, deshalb wäre jede XSS-Senke ein Tokendiebstahl.

**Bedrohungen**

1. **XSS über den Grund oder den Dateinamen** in der neuen Leiste, in der Kurzbeschriftung oder im zugänglichen Namen der Knöpfe.
2. **Täuschung durch vollständigen Modelltext.** Mit „…“ war ein eingeschleuster Satz bisher abgeschnitten; künftig steht er ganz da. Ein präpariertes Bild kann so einen Text erzeugen, der wie eine Meldung der Anwendung aussieht, etwa „Sitzung abgelaufen, bitte unter … neu anmelden“.
3. **CSS-Injection über Inline-Stile.** Kachelbreite, Bildhöhe und `maxHeight` der Leiste werden gerechnet und als Inline-Stil gesetzt.
4. **Wegfall des Regressionsnetzes.** Mit `CriterionDetailsPopover` wird eine Renderstelle samt Test gelöscht, und der bestehende Kacheltest prüft heute `line-clamp-2`. Wird der Test beim Umbau „mit aufgeräumt“, fehlt der XSS-Nachweis an der Stelle, die den Grund tatsächlich rendert.

**Muss-Auflagen**

- **S1 — Der Grund ist an jeder Renderstelle nur ein React-Textknoten.** Das gilt für die Leiste in `CurationPhotoTile` (und jeden daraus ausgelagerten Baustein). Untersagt sind `dangerouslySetInnerHTML`, ein HTML-String-Prop sowie `href`/`src`/`style`/`url()`, `title`, `aria-label`/`aria-description`, React-`key` und eine automatische Link-Erkennung. Der Grund geht auch nicht in den zugänglichen Namen von Bild oder Knöpfen: Der Name bleibt `{Handlung}: {Pfad}`, der Grund wird nur über den Lesefluss der `sr-only`-Leiste erreicht. **Der Test wandert mit der Renderstelle.** In `CurationPhotoTile.test.tsx` bleiben `never renders the reason as markup` und der Link-Fall (Nutzlasten `<img src=x onerror=…>` und `<a href=…>` ⇒ kein `img`/`a` im Container, Text wörtlich sichtbar) erhalten. Die Assertion `line-clamp-2` in `keeps the full reason in the DOM…` wird durch `carrier.textContent === reason` **ohne** `line-clamp` ersetzt. Neu ist `the reason never reaches an attribute`: Die Nutzlast taucht in keinem Attributwert eines Elements der Kachel auf. Geprüft wird das über `querySelectorAll('*')` und alle `attributes`.
- **S2 — Der Grund ist als Aussage des Modells erkennbar.** Im Träger `[data-album-suitability-reason]` steht vor dem Grund die Zuschreibung `Begründung des Modells` als Textknoten, wie in `PhotoVerdict.tsx` (S4 dort). Dafür wird dieselbe Konstante verwendet, keine zweite Fassung. Sichtbar oder nur `sr-only` entscheidet die Gestaltung. Gestaltungsvertrag „Schätzung eines Modells“: keine `Badge`, keine Bewertungsfarbe, kein Symbol, keine Form einer Systemmeldung (`Alert`, `role="alert"/"status"`). Test in `CurationPhotoTile.test.tsx`: `attributes the reason to the model inside its carrier` (Zuschreibung im selben Träger vor dem Grund, `toHaveTextContent(/Begründung des Modells.*<Grund>/)`) und `the reason carrier is no alert` (kein `role=alert/status` im oder um den Träger).
- **S3 — Dateinamen nur als Textknoten und als gewöhnlicher React-Attributwert.** In der Leiste steht der Basisname, und `{Handlung}: {Pfad}` dient als `aria-label`. Beides wird ausschließlich über React gesetzt, nie per HTML-Zusammensetzung. Die Kurzbeschriftung im Symbolmodus ist ein festes Literal aus der Konstantentabelle, nie ein API-Wert. Test in `CurationPhotoTile.test.tsx` und `TileAction.test.tsx`: `a hostile file name stays text` (Dateiname `<img src=x onerror=…>.jpg` ⇒ kein `img` außer dem Foto selbst, der Name steht wörtlich im zugänglichen Namen).
- **S4 — Inline-Stile tragen nur Zahlen (Securitykonzept, Auflage S6 / Abschnitt „gerechneter Wert in einen Inline-Stil“).** `width`, `height` und `maxHeight` werden als `style={{ width: n }}` mit `n` aus `justifiedRows`/`useJustifiedRows` gesetzt. Untersagt sind eine Zeichenkette mit API-Anteil, eine Custom-Property und `url()`. `aspect_ratio` geht nur über `typeof … === 'number' && Number.isFinite(…)` samt Bereichsbedingung in die Planung, sonst gilt der Rückfall `3/2`. Test in `useJustifiedRows.test.ts` bzw. `curationLayout.test.ts`: `a non-finite or non-numeric ratio falls back` (`NaN`, `Infinity`, `"1;background:url(x)"` ⇒ Rückfallverhältnis, alle ausgegebenen Maße endliche Zahlen). In `CurationPhotoTile.test.tsx`: `inline styles carry only numeric pixel values` (jeder `style`-Wert passt auf `/^\d+(\.\d+)?px$/`, kein `url(`, kein `var(`).
- **S5 — Symbole nur als statische benannte Importe.** `repeat` und `plus` kommen über die bestehenden statischen Einzelimporte in `ui/icon.tsx` in die geschlossene Namensmenge. `name` bleibt ein Literal-Union-Typ und wird nie aus API-Daten gebildet. Untersagt sind ein dynamischer `import()`, ein Namespace-Import (`import * as`) und ein Nachschlagen per Zeichenkette aus Daten. Abgesichert durch die bestehende Namensliste in `ui/icon.test.tsx` (künftig 22 Einträge, Gleichheit statt Teilmenge).

**Geprüft und ohne eigene Auflage**

- **Wegfall von `CriterionDetailsPopover` und `MotifAssessmentMarker`.** Die Angriffsfläche schrumpft: Feinlabels und Motivtexte, ebenfalls Modelltext, werden auf der Kachel nicht mehr gerendert. Bedingung ist nur S1, also dass das Netz an der verbleibenden Renderstelle bleibt. Die Renderstellen in `CriterionDetailsList`/`PhotoVerdict` bleiben samt ihren Tests unverändert. `ui/popover.tsx` bleibt bestehen; nur seine Kommentare ändern sich.
- **Langer Druck (`useRevealOnDemand`).** Er ist ein reiner Anzeigezustand ohne Schreibwirkung. Der unterdrückte Klick verhindert nur das Öffnen der Großansicht und löst keine Handlung aus. Der Timer wird beim Unmount und beim Schließen geräumt; das ist Korrektheit, keine Sicherheitsfrage. Das Regressionsnetz bilden die bestehenden `PhotoGridTile`-Tests.
- **Immer im DOM, im Ruhezustand `sr-only`.** Das macht nichts sichtbar, was der Nutzer nicht ohnehin sehen darf. Grund und Dateiname liegen schon heute in der Antwort, und es gibt kein Innentäter-Modell zwischen den beiden Nutzern.
- Kein CSRF (Bearer-Header), keine neue Aufzählbarkeit, keine neue Netzwerkverbindung.

## Teststrategie

Die Ebenen folgen dem Testkonzept: reine Funktionen vor dem DOM (Sektion 0489, Punkt 3). E2E nur für das, was jsdom nicht kann: Geometrie, Treffbarkeit, waagerechtes Scrollen. Keine neue Testebene, kein neues Werkzeug.

**Unit, tabellengetrieben, ohne DOM**
- `justifiedRows` mit `maxRowHeight`: ohne Parameter Ausgabe identisch zu heute (ein Regressionsfall mit der bestehenden Tabelle). Eine Reihe über `maxRowHeight` wird als Zielhöhe-linksbündig gesetzt. Genau auf der Grenze bleibt sie bündig (einschließend, eigener Fall). Ein einzelnes 2:3-Bild bei 328 px ergibt 280 hoch statt ≈ 490.
- `curationLayout`: Planungsverhältnis `max(ratio ?? 3/2, MIN_PLANNING_RATIO)` mit den Fällen `null`, 0,4 (< 1:2), genau 0,5, 9:16, 3:2. Jede Konstante wird **einmal** an ihren Zahlwert gebunden (280/200/350/100, die sechs `HANDLES_FULL_WIDTH_PX`), alle anderen Tests importieren sie. `iconOnly(width, kind)` je Variante bei Schwelle − 1, Schwelle und Schwelle + 1. Die Grenze ist streng `<`.
- Telefonrechnung aus der Architektur als Tabellenfall: zwei 2:3 bei 328 px ergeben eine Reihe mit Breiten je ≥ 100 und < 208 (also Symbolmodus). Ein 3:2 steht allein mit Wort.

**Hooks/Komponenten (vitest + Testing Library, treibbare `ResizeObserver`-Attrappe, Fake-Timer)**
- `useRevealOnDemand`: die vier Pflichtfälle aus Sektion 0489, Punkt 4, je mit Negativ-Assertion: Hover mit und ohne fine pointer, Druck 499 und 500 ms. Dazu: Schließen per `pointerdown` außerhalb und per `scroll`, unterdrückter Klick nach langem Druck. `PhotoGridTile`-Bestandstests bleiben unverändert grün; das ist der Verhaltensgleichheits-Nachweis.
- `TileAction`: beide Modi, zugänglicher Name gleich, Kurzbeschriftung nur im Symbolmodus und `aria-hidden`, `busy` ersetzt das Symbol (genau ein Spinner, kein Symbol, Wort bleibt), deaktiviert.
- `AlbumStateBadge`: je Zustand `role=img`, exakter Name, kein sichtbarer Text. Symbolfolge per `data-icon`.
- `PhotoCard` / `CurationPhotoTile` / `SelectionPhotoTile`: DOM- und Fokusreihenfolge. Fokus auf jedem Bedienelement blendet die Leiste ein. Leiste im Ruhezustand im DOM und `sr-only`. Ein Grund mit 160 Zeichen hat vollen `textContent`, keine Klasse `line-clamp-*`/`truncate`. Ohne Grund ist kein Element mit leerem Text da. „nicht vorgeschlagen“ erscheint in Leiste und Badge-Name. `setAside` zeigt den Dateinamen durchgestrichen. Info-Auslöser und Motiv-Marker fehlen (Abwesenheit im `within(tile)`-Rahmen). Die Knöpfe öffnen die Großansicht nicht. Langer Druck öffnet sie nicht. Struck-Variante mit genau einem Knopf. Endauswahl strittig mit zwei Knöpfen und Haltungszeilen mit Symbolzeichen und Namen.
- `DraftAlternativesBand`: Kandidaten sind `PhotoCard`. Die Bezugsmarke ist eine Zelle mit eigenem Verhältnis.

**Seitentests (`AlbumDraftPage`, `AlbumSelectionPage`)**: Band/Panel als `li.w-full` hinter der gerechneten Reihe der auslösenden Kachel, über die Attrappe bei zwei Breiten. Die Hinzufügen-Zelle ist die letzte und trägt Symbol `plus`. Die bestehenden Abläufe (Alternativen → Tauschen/Hinzufügen, Streichen/Rückgängig) bleiben grün, keine Namensänderung (Knopf heißt weiter „Alternativen: …“).

**Design-Vertrag / Symbolsatz**: `compact`-Größe und `h-11 sm:h-8`/`size-11 sm:size-8` als fundstellengenaue Einträge in `TALL_CONTROL_ALLOWLIST`. `repeat`/`plus` an allen vier Stellen plus `icon.test.tsx` (22). `GRID_GAP_PX` gegen `gap-3` (Sektion 0489, Punkt 5) gilt jetzt auch für die Kuratierungsraster. Löschungen: `CriterionDetailsPopover(.test)`, `MotifAssessmentMarker(.test)`.

**E2E (Playwright, 360 und 1280 px)**
- `foto-karte-raster.spec.ts` wird **ersetzt statt angepasst**: Spaltenleiter 2/3/4, `gridTemplateColumns` und quadratische Fläche sind abgelöste Zusagen. Neu gemessen wird je Raster (Entwurf, Band, Panel, Endauswahl Arbeits- und Ergebnissicht):
  - Bildfläche = natürliches Seitenverhältnis (±1 px),
  - gleiche Höhe je Reihe,
  - volle Reihe bündig,
  - Reihenhöhe bei 1280 px in [200, 350],
  - jede Kachel ≥ 100 px breit,
  - Knopfzeile ≤ Kachelbreite und einzeilig,
  - Symbolmodus genau dann, wenn Breite < Schwelle (Wort sichtbar/nicht sichtbar).
  
  Der Fall „Band unter seiner Reihe“ bleibt, aber gegen die gerechnete Reihe statt gegen drei Spalten. Vorbedingung: Hoch- und Querformat in einer Reihe. Das einzige Hochformat des Demo-Entwurfs ist gestrichen; das bestehende Auffüllen oder Aufklappen der Gestrichenen trägt das.
- `tap-targets.spec.ts`: Kommentar und Erwartung „untereinander“ werden zu „nebeneinander“. Streichen/Alternativen der Entwurfskachel und Tauschen/Hinzufügen im Band und in der Reihe im **Symbolmodus** (zwei 2:3 nebeneinander, sonst Vorbedingung rot). `EXPECTED_CONTROL_COUNT` nur ändern, wenn sich die Zahl geprüfter Elemente tatsächlich ändert, mit Begründung.
- `no-horizontal-scroll.spec.ts`: Routen und offene Zustände bleiben. Die Nachtrag-0578-Zusage „Tauschen/Hinzufügen untereinander mit ≥ 12 px Abstand“ wird zu „nebeneinander, ≥ 44 px hoch und breit, ≥ 12 px waagerechter Abstand“ (`boundingBox`).
- Neu im 1280er-Lauf: Die Leiste erscheint per Hover und per Tab-Fokus und bleibt innerhalb der Bildfläche. Die Kurzbeschriftung bleibt innerhalb der Kachel (erster Knopf links, zweiter rechts bündig).
- 360 px, langer Druck per `page.touchscreen`/Pointer mit Haltezeit: Leiste sichtbar, kein Dialog.
- `kuratierung-grossansicht.spec.ts`: Der Auslöser bleibt die Bildfläche. Mitprüfen, dass Locator/Rahmenrechnung nicht an `aspect-square` hingen.
- Jede neue E2E-Zusage braucht einen Rot-Nachweis (Testkonzept-Regime).

**Edge Cases (Pflicht)**
- `aspect_ratio = null` → 3:2-Planung, eingepasst.
- Verhältnis < 1:2 (z. B. 0,4) → Feld 1:2, eingepasst, Kachel ≥ 100 px.
- Einzelnes Hochformat am Telefon → 280 px hoch, linksbündig, nicht ≈ 490.
- Leerer Grund (`null`) → keine Zeile.
- Leerer String `""` → ebenfalls keine Zeile. Das ist die rein technische Festlegung, damit `!== null` keinen leeren Knoten erzeugt; Rückfrage an Architektur, falls das Backend `""` nie liefert.
- Langer Grund (160 Zeichen) in einer 100-px-Kachel → vollständig, Leiste ≤ Bildhöhe.
- Tastaturfokus auf dem zweiten Knopf → Leiste sichtbar, Kurzbeschriftung rechtsbündig.
- Langer Druck (< 500 vs. ≥ 500 ms) → keine Großansicht, Schließen per Tipp/Scroll.
- Gestrichene Kacheln → voller Helligkeitswert (ADR 0112 unverändert), Dateiname durchgestrichen, ein Knopf.
- Endauswahl strittig → zwei Knöpfe bei Schwelle 248, Haltungszeilen mit Symbol und Namen.
- Busy → keine Breitenänderung.
- Bild lädt nicht → Platzhalter im geplanten Format, Knöpfe bedienbar.
- Ladeplatzhalter: `naturalTiles` in Zeilenform (Achse `flex`, nicht quadratisch; Sektion 0489, Punkt 7).

**Bewusst nicht automatisiert:**
- Unterscheidbarkeit der Symbole ohne Farbe als Wahrnehmung: nur am Diff bzw. im Design-Review. Automatisiert ist nur die Symbolfolge.
- Tatsächliches Bildschirmleser-Verhalten.
- Pixelvergleich.

## Entscheidungen

- Der Knopf an der Entwurfskachel heißt weiterhin „Alternativen" (Symbol `repeat`); „Tauschen" bleibt allein der Sofort-Tausch an einer Alternative (Daniel, spec-writer).
- Schmale Fotos: Zeilen bleiben etwa 280 px hoch und randlos; ist eine Kachel schmaler als ihre Knopfzeile, zeigen die Knöpfe nur das Symbol, das Wort wird vorgelesen (Daniel, Produktentscheidung aus der Architekturkonsultation, Option C).
- Symbolsatz um `repeat` und `plus` erweitert; das Textzeichen `+` an „Foto hinzufügen" wird zum Symbol (architect, ADR 0134).
- „Tauschen" trägt dasselbe Symbol `repeat` wie „Alternativen" (architect).
- Grund in der Leiste mit Zuschreibung „Begründung des Modells" (security-engineer, S2).
- `foto-karte-raster.spec.ts` wird ersetzt statt erweitert; Testkonzept: Nachtrag 0578 und Sektion 0489/ADR 0110 werden im Umsetzungs-PR nachgezogen (test-engineer).
- Securitykonzept bekommt im Umsetzungs-PR die neue Ankerzeile zur Leiste (security-engineer).

## Offene Fragen

- keine

## Out of Scope

- Bildbestand (Fotoübersicht, Einzelbild), Großansicht, Bildung des Vorschlags.
- Verhalten der Handgriffe selbst (Spec 0578).
- Ausarbeitung der Penpot-Ansicht „Album-Entwurf" (Design-Abschnitt ist Arbeitsstand).
