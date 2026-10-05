# 0563 - Größere, unbeschnittene Fotos im Album-Entwurf und in der Endauswahl

**Status:** Implemented ([PR #564](https://github.com/TheRealKoller/photosort/pull/564))
**Erstellt:** 2026-10-02
**Bezug:** [#563](https://github.com/TheRealKoller/photosort/issues/563), Nachbesserung zu [Spec 0558](./0558-album-entwurf-verstaendlich.md)

> **Teilweise abgelöst durch Spec [`0579`](./0579-kuratierungskacheln-foto-im-mittelpunkt.md) / ADR 0134:** AK1, AK2 (Spaltenleiter), AK4 (quadratische Bildfläche), `PHOTO_CARD_GRID_CLASS` und die Spaltenleiter 2/3/4 gelten nicht mehr — die Kuratierungsraster sind justierte Reihen im Seitenverhältnis des Fotos. AK3 (kein Beschnitt) gilt weiter.

## Ziel

Nachbesserung zu #558: Auf der Album-Entwurf-Seite sind die Fotos zu klein, und sie werden quadratisch beschnitten. Beim Kuratieren soll man jedes Foto groß genug und vollständig sehen, im Hoch- wie im Querformat. Dasselbe gilt für die Endauswahl, damit beide Seiten dieselbe Kachel zeigen.

Nicht Teil dieser Story: Bildbestand (Raster, Einzelbild), Großansicht, Verhalten der Handgriffe.

## User Story

Als Nutzer, der sein Album zusammenstellt, möchte ich die Fotos im Album-Entwurf und in der Endauswahl groß und unbeschnitten sehen, damit ich ohne Großansicht beurteilen kann, ob ein Foto ins Album gehört.

## Akzeptanzkriterien

- [ ] **AK1 – Spaltenleiter.** Das Foto-Raster im Album-Entwurf (Album-Zeile und Gestrichen-Zeile jedes Ereignisses) und in der Endauswahl (Arbeitssicht und Ergebnissicht) zeigt bei 360 px Breite genau 2, bei 800 px genau 3 und ab 1280 px genau 4 Fotos je Reihe; zu keiner Breite stehen mehr als 4 in einer Reihe. Die Ladeplatzhalter beider Seiten folgen derselben Leiter.
- [ ] **AK2 – Band und Panel.** Das Alternativen-Band und das Hinzufügen-Panel im Album-Entwurf folgen derselben Leiter (360 → 2, 800 → 3, 1280 → 4), einschließlich ihrer Platzhalter. Die Einfügestelle von Band und Panel liegt weiterhin direkt unter der Reihe der auslösenden Kachel.
- [ ] **AK3 – Kein Beschnitt.** Jedes Foto in Entwurfskachel, Endauswahl-Kachel, Alternativen-Band, Hinzufügen-Panel und Dialog „Alle Alternativen“ wird eingepasst (`object-fit: contain`), nie beschnitten: Ein Hochformat erscheint höher als breit, ein Querformat breiter als hoch – das sichtbare Bild hat das Seitenverhältnis der geladenen Datei (Toleranz ±2 %).
- [ ] **AK4 – Ruhige Reihe.** Die Bildfläche jeder Kachel ist quadratisch und in einer Reihe für alle Kacheln gleich groß (Breite und Höhe ±1 px), unabhängig vom Format des Fotos. Handgriffe, Kennzeichen und Dateiname stehen dadurch in jeder Kachel einer Reihe an derselben relativen Position (±1 px).
- [ ] **AK5 – 360 px.** Bei 360 px erzeugen weder der Album-Entwurf noch die Endauswahl (Arbeits- und Ergebnissicht) waagerechtes Scrollen (`scrollWidth ≤ clientWidth`), und alle Handgriffe der Kacheln (Streichen, Alternativen, Tauschen, Aufnehmen, Nicht aufnehmen, Herausnehmen) bestehen den bestehenden Treffbarkeitstest (≥ 24 × 24 px, keine Überlappung).
- [ ] **AK6 – Bildbestand unberührt.** Rasterkachel und Einzelbild des Bildbestands ändern sich nicht; ihre bestehenden Tests (`grid-columns.spec.ts`, `photoGridTile.structure.test.ts`) bleiben unverändert grün.

## Datenmodell-Bezug

Keiner. Reine Darstellungsänderung im Frontend.

## Architektur / Umsetzung

**Ansatz:** Es ändert sich nur das Frontend und dort nur die Darstellung. Es gibt keine neue Abhängigkeit, kein Datenmodell, keinen Endpunkt und keine ADR. Wiederverwendet wird das Muster, das das Alternativen-Band schon hat (`DraftAlternativesBand.tsx` Z. 131–137): eine **feste quadratische Bildfläche**, in die das Bild mit `object-contain` eingepasst wird. Die Fläche bleibt bei jedem Format gleich groß, deshalb stehen Ecken-Overlays, Kennzeichen, Dateiname und Fußzeile in jeder Kachel an derselben Stelle (AK 4). Das Bild wird nur eingepasst, nie beschnitten (AK 3). Ein Seitenverhältnis-Kasten nach `PhotoOut.aspect_ratio` wie bei `PhotoGridTile` scheidet aus: Er machte die Kachelhöhe vom Format abhängig und verletzte damit AK 4.

**Bildbestand bleibt unberührt:** `PhotoCard` wird nur noch von `CurationPhotoTile` (Album-Entwurf) und `SelectionPhotoTile` (Endauswahl) benutzt. Die Fotoübersicht rendert `PhotoGridTile` ohne `PhotoCard`, das sichert `photoGridTile.structure.test.ts`. Das Einzelbild nutzt die Karte nicht. ADR 0110 Punkt 5 legt die Fotokarte als Kartenkörper mit *fester quadratischer Bildfläche* fest, und die bleibt erhalten. Es ändert sich nur, wie das Bild darin sitzt (`object-fit`), also eine technische Detailfrage und kein Superseding.

**Bildvariante:** Es bleibt `variant="thumbnail"`. `thumbnails.py::generate_variants` schneidet nicht zu, `Image.thumbnail((400, 400))` skaliert die lange Kante auf höchstens 400 px und behält das Verhältnis. Der quadratische Beschnitt kommt allein aus dem Frontend (`object-cover`). Die Bildfläche misst bei `max-w-5xl` mit `sm:px-6`: 360 px → 140 CSS-px, `sm` bis 1023 px (3 Spalten) → höchstens 291 CSS-px, ab `lg` (4 Spalten) → 209 CSS-px. Bei DPR 1 reicht die Variante überall. Bei DPR 3 am Handy und DPR 2 ab `lg` steht sie etwa 1:1. Ein Querformat nutzt jetzt alle 400 px statt der bisher 267 px des beschnittenen Quadrats.

### Spaltenregel

Für alle betroffenen Raster gilt eine Klasse: `grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4`. Neu ist sie als `export const PHOTO_CARD_GRID_CLASS` in `components/PhotoCard.tsx`. Diese Datei teilen sich Entwurf und Endauswahl, ohne dass die Endauswahl Entwurfscode importiert (`albumSelection.structure.test.ts` bleibt grün).
- Bei 4 Spalten gilt `lg` und nicht `md`: Mit `md:grid-cols-4` fiele die Kachel bei 768 px von etwa 231 auf etwa 171 px und wäre dort kleiner als bei 3 Spalten. Mit `lg` wächst sie stetig: 158 px Kachel bei 360 px, bis 317 px bei 3 Spalten, 235 px ab 1024 px. `xl:grid-cols-6` entfällt.
- `DraftEventSection.columnCount` liest die Spaltenzahl aus dem gerenderten Raster. Die Einfügestelle von Band und Panel folgt deshalb ohne Änderung.

### Betroffene Dateien

1. `components/PhotoCard.tsx`: `PHOTO_CARD_GRID_CLASS` exportieren. `imageAreaClassName` bleibt `block aspect-square overflow-hidden rounded-md`. Doku-Block ergänzen: Die Bildfläche ist quadratisch, das Bild wird eingepasst, nie beschnitten.
2. `components/CurationPhotoTile.tsx` Z. 91 und `components/SelectionPhotoTile.tsx` Z. 136: `size-full object-cover` → `size-full object-contain`. `PhotoImage` setzt intern `object-cover`, und tailwind-merge lässt die übergebene Utility gewinnen (wie in `PhotoGridPage.tsx` Z. 292–294).
3. `components/DraftEventSection.tsx`: `GRID_CLASS` entfällt, beide Raster (Album und Gestrichen-Zeile) nutzen `PHOTO_CARD_GRID_CLASS`.
4. `components/DraftAlternativesBand.tsx`: Die Liste der Kandidaten und die Platzhalter-Liste (Z. 112, Z. 124) wechseln von `grid-cols-2 sm:grid-cols-4` auf `PHOTO_CARD_GRID_CLASS`. Das gilt für Band und Hinzufügen-Panel, weil `DraftAddPanel` dieselbe Gestalt rendert. Die Bildfläche ist schon `object-contain`.
5. `pages/AlbumDraftPage.tsx` Z. 481 (Platzhalter-Raster) und `pages/AlbumSelectionPage.tsx` Z. 101 und Z. 163 (Raster und Platzhalter): `PHOTO_CARD_GRID_CLASS`. Die Platzhalter bleiben `aspect-square w-full rounded-md`, denn die Bildfläche bleibt quadratisch.
6. `designSystem.contract.test.ts`: Der bestehende Wächter „kein Beschnitt“ (Z. 1016 ff., heute nur `PhotoGridTile.tsx`) prüft für `object-cover` zusätzlich `CurationPhotoTile.tsx`, `SelectionPhotoTile.tsx` und `DraftAlternativesBand.tsx`. `aspect-square` bleibt dort ausdrücklich erlaubt, es ist die feste Bildfläche aus AK 4.
7. E2E (`e2e/tests/album-entwurf.spec.ts`, das Muster liefert `grid-columns.spec.ts`), Album-Entwurf und Endauswahl:
   - Die Spaltenleiter misst 360 → 2, 800 → 3 und 1280 → 4.
   - Je Bild gilt `objectFit === 'contain'`. Die Bildfläche ist quadratisch und gleich groß über die Reihe.
   - Band und Panel bekommen dieselbe Leiter.
   - Der Demo-Bestand mischt Formate bereits (ADR 0110, Konsequenzen).
   - `no-horizontal-scroll` und `tap-targets` bleiben unverändert, bei 360 px bleibt die Spaltenzahl 2.
8. Doku:
   - In `.claude/skills/design-system/SKILL.md` den Eintrag „Foto-Karte“ (Z. 148) korrigieren. Er ist veraltet: Er nennt „Raster, Kuratierung, Vergleich“, richtig sind Album-Entwurf und Endauswahl. Neu sind außerdem die quadratische Bildfläche mit `object-contain` und die Spaltenregel.
   - In `docs/architecture.md` beim Album-Entwurf und bei der Endauswahl einen Satz zur Spaltenregel und zum fehlenden Beschnitt ergänzen. Z. 81 („`PhotoCard` selbst bleibt unverändert“) steht im Kontext von 0489 und wird auf „unverändert durch die Rasterkachel“ präzisiert.

**Reihenfolge:** zuerst 1 bis 2 (Karte und Kacheln, Wächter 6 zuerst rot), dann 3 bis 5 (Raster), dann 7 und 8.

**Nicht angefasst:** `PhotoGridTile`/`PhotoGridPage` (Bildbestand), `CurationLightbox` (Großansicht), `UndoToast`-Vorschaubild, Duplikat- und Ausschuss-Kacheln, Backend.

### Offene Punkte

- **Schärfe auf HiDPI zwischen 640 und 1023 px:** Bei 3 Spalten und DPR 2 wird die 400-px-Variante bis etwa 1,5-fach hochskaliert. Abhilfe wäre ein größeres `THUMBNAIL_MAX_SIZE`. Der Cache-Schlüssel ist aber nur `photo_id`+`etag`, vorhandene Vorschaubilder müssten verworfen und neu erzeugt werden, und es träfe auch die Dateigröße im Bildbestand. Das gehört nicht in diese Story. Bei der Abnahme auf einem Tablet ansehen, gegebenenfalls eine eigene Story.
- **Ecken bei Hoch- und Querformat:** `rounded-md` sitzt auf dem `<img>`-Kasten. Bei eingepasstem Nicht-Quadrat sind die Ecken des sichtbaren Fotos eckig, und die Leerfläche zeigt die Kartenfläche `--elevated`. Das Band sieht heute schon so aus. Wird eine sichtbare Rahmung der Bildfläche gewünscht, entscheidet das der Entwurf.
- **Band mit 4 Alternativen bei 3 Spalten:** Es ergibt eine Zeile mit 3 und eine mit 1, das Panel mit 8 ergibt 3+3+2. Das ist zulässig, aber sichtbar.
- **Penpot:** Das Brett `album-entwurf` zeigt laut Spec 0558 (`kachelmasse`) sechs Kacheln und beschnittene Bilder. Der Abgleich gehört zu einer Entwurfsrunde, nicht zur Umsetzung.

## UI/UX

**Ansatz:** Es entsteht keine neue Ansicht und kein neuer Baustein. Die Foto-Karte (`PhotoCard`) behält ihre feste quadratische Bildfläche (`aspect-square`). Neu ist nur, dass das Foto darin **eingepasst** wird (`object-contain`) statt beschnitten (`object-cover`). Hochformat erscheint als Hochformat, Querformat als Querformat (AK 3). Weil die Fläche bei jedem Format gleich groß bleibt, stehen Ecken-Overlays, Kennzeichen, Dateiname und die Handgriffe in jeder Kachel einer Reihe an derselben Stelle (AK 4). Dasselbe Muster hat das Alternativen-Band schon heute.

**Spaltenregel:** In Album-Entwurf und Endauswahl nutzt jedes Raster der Foto-Karte genau eine Klasse, `PHOTO_CARD_GRID_CLASS` (`grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4`). Das gilt für die Gruppen, die Gestrichen-Zeile, das Alternativen-Band, das Hinzufügen-Panel, die Platzhalter-Raster und das Raster der Endauswahl. Damit stehen am Telefon (360 px) 2 Kacheln je Reihe, dazwischen 3 und auf großen Bildschirmen höchstens 4 (AK 1, AK 2). Auf 4 Spalten springt das Raster bei `lg` und nicht schon bei `md`. Sonst würde die Kachel beim Wechsel von 3 auf 4 Spalten kleiner, als sie bei 3 Spalten war. `xl:grid-cols-6` entfällt. An keiner Aufrufstelle steht eine eigene Spaltenklasse.

**Leerfläche:** Neben einem nicht quadratischen Foto bleibt ein Teil der Bildfläche frei. Diese freie Fläche ist die Kartenfläche `--elevated`, ohne eigene Tönung und ohne Rahmen um die Bildfläche, genau wie im Band. `rounded-md` liegt auf dem Bildkasten, deshalb hat das sichtbare Foto bei Hoch- oder Querformat eckige Ecken. Das ist so beabsichtigt, weil es mit dem Band übereinstimmt.

**Zustände:** Es kommen keine neuen Zustände hinzu. Die Lade-Platzhalter bleiben `aspect-square w-full rounded-md` im selben Raster. Fehler- und Leerzustände ändern sich nicht. Ein aussortiertes oder gestrichenes Foto wird weiter in voller Helligkeit gezeigt.

**Dialog „Alle Alternativen“** (`DraftAlternativesDialog`): Er bekommt ebenfalls `object-contain`, damit dasselbe Foto auf der Entwurfsseite nicht an einer Stelle ganz und an einer anderen beschnitten erscheint. Seine Spalten (`2 / sm:3`) bleiben, denn er liegt schon bei höchstens 3.

**Barrierefreiheit / 360 px:** Trefferflächen, Fokusreihenfolge und zugängliche Namen bleiben unverändert. Bei 360 px bleibt es bei 2 Spalten, die Seiten scrollen nicht waagerecht, und `no-horizontal-scroll` sowie `tap-targets` bleiben grün (AK 5).

**Design-System:** In `specs/architecture/0004-design-system.md` hat der Eintrag „Foto-Karte“ zwei neue Regeln bekommen: „Bild eingepasst, nie beschnitten“ und „eine Spaltenregel“. Der Skill `design-system` ist nachgezogen. Dort ist auch der veraltete Hinweis korrigiert, die Karte werde in „Raster, Kuratierung, Vergleich“ benutzt; richtig sind Album-Entwurf und Endauswahl.

**Offene Punkte:**
- Das Penpot-Brett `album-entwurf` zeigt noch sechs Kacheln je Reihe und beschnittene Bilder. Der Abgleich gehört in eine Entwurfsrunde, nicht in die Umsetzung.
- Auf HiDPI-Bildschirmen zwischen 640 und 1023 px (3 Spalten) wird die 400-px-Vorschau bis etwa 1,5-fach hochskaliert. Bei der Abnahme auf einem Tablet ansehen und gegebenenfalls als eigene Story anlegen.
- Bei 3 Spalten verteilen sich die 4 Alternativen im Band auf zwei Reihen (3+1) und die 8 im Panel auf drei (3+3+2). Das ist zulässig, aber sichtbar.
- Die Sichtprüfung findet in Telefon- und Desktopbreite statt, mit gemischten Hoch- und Querformaten aus dem Demo-Bestand.

## Security

nicht relevant: keine neue Eingabe, kein Endpunkt, keine Auth-, Secret- oder Datensichtbarkeitsänderung; es ändern sich nur CSS-Klassen der Fotodarstellung.

## Teststrategie

**Vertragstest (vitest, `designSystem.contract.test.ts`):** Der bestehende Wächter „kein Beschnitt“ (Z. 1016 ff.) wird auf `CurationPhotoTile.tsx`, `SelectionPhotoTile.tsx`, `DraftAlternativesBand.tsx` und `DraftAlternativesDialog.tsx` ausgedehnt – nur für `object-cover`; `aspect-square` bleibt dort ausdrücklich erlaubt (feste Bildfläche, AK4). Zusätzlich: Alle betroffenen Raster (DraftEventSection, DraftAlternativesBand, AlbumDraftPage-Platzhalter, AlbumSelectionPage) verwenden `PHOTO_CARD_GRID_CLASS` und enthalten keine eigene `grid-cols-*`-Utility – fängt das Auseinanderlaufen der Leiter zwischen den Rastern. Zuerst rot schreiben (AK3).

**E2E (Playwright, `album-entwurf.spec.ts` bzw. neue Fälle nach Muster `grid-columns.spec.ts`, an ein Projekt gebunden mit eigenen Viewport-Breiten):**
- Spaltenleiter 360/800/1280 → 2/3/4 für Entwurfsraster, Band (geöffnet), Panel (geöffnet) und Endauswahl (Arbeitssicht; Ergebnissicht bei 1280) – gemessen über die `top`-Werte der ersten Reihe bzw. `grid-template-columns` (AK1, AK2). Die Grenzbreiten 639/640 und 1023/1024 werden NICHT einzeln geprüft; 800 belegt die mittlere Stufe.
- Je Bild `getComputedStyle(img).objectFit === 'contain'` und Bildfläche quadratisch, alle Bildflächen der ersten Reihe gleich groß ±1 px (AK3, AK4).
- Mindestens ein Hoch- und ein Querformat aus dem Demo-Bestand: `naturalWidth/naturalHeight` > 1 bzw. < 1 wird als Vorbedingung geprüft, damit der Test nicht an einem rein quadratischen Bestand vorbeiläuft (AK3).
- Gleiche relative Position des ersten Handgriffs in zwei Kacheln unterschiedlichen Formats derselben Reihe ±1 px (AK4).
- Einfügestelle von Band/Panel unter der auslösenden Reihe bei 3 Spalten (800 px) – deckt `columnCount` nach der Leiteränderung (AK2).

**Bestehende Specs unverändert:** `no-horizontal-scroll.spec.ts` (deckt Album-Entwurf, Endauswahl Arbeits- und Ergebnissicht schon ab) und `tap-targets.spec.ts` (Entwurf- und Endauswahl-Handgriffe) belegen AK5; `grid-columns.spec.ts` und `photoGridTile.structure.test.ts` belegen AK6. Keine neuen Unit-Tests für `PhotoCard` – reine Klassenweitergabe wäre Verdrahtungstest.

**Nicht getestet:** Bildschärfe auf HiDPI (visuelle Abnahme), Ecken-Rundung des eingepassten Bildes (Entwurfsfrage).

**Testkonzept:** unverändert – Vertragswächter, E2E-Spaltenleiter und Viewport-Bindung sind etablierte Muster.

## Entscheidungen

- Umfang, Spaltenzahl und „ganz sichtbar“ hat Daniel am 2026-10-02 entschieden: Album-Entwurf und Endauswahl, höchstens 4 je Reihe, kein Beschnitt.
- Der Dialog „Alle Alternativen“ wird ebenfalls eingepasst (gleiche Seite, kein widersprüchlicher Beschnitt); seine Spalten (2/3) bleiben.
- security-engineer nicht konsultiert (Schritt 3): Kein konkret benennbarer Bezug zu Auth, Eingaben, Secrets, Datenmodell oder Datensichtbarkeit; die Änderung betrifft ausschließlich Layout-Klassen.

## Offene Fragen

- Das Penpot-Brett `album-entwurf` zeigt noch sechs beschnittene Kacheln je Reihe; der Abgleich gehört in eine Entwurfsrunde.

## Out of Scope

Bildbestand (Raster, Einzelbild), Großansicht, Verhalten der Handgriffe, schärfere Bildvariante für HiDPI.
