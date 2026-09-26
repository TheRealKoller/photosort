# 0531 - Bild in der Kuratierung groß ansehen, ohne die Stelle zu verlieren

**Status:** Implemented ([PR #538](https://github.com/TheRealKoller/photosort/pull/538))
**Erstellt:** 2026-09-26
**Bezug:** [Issue #531](https://github.com/TheRealKoller/photosort/issues/531)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Die Teststrategie führt die bewusst
geänderten Bestandstests und die Rot-Anker der E2E-Fälle namentlich, und `## Security` trägt vier
Auflagen in der geschützten Dreiteilung.

## Ziel

Beim Kuratieren entscheidet sich an jedem einzelnen Bild, ob es ins Album kommt. Auf einer
Rasterkachel ist das oft nicht zu erkennen: ob das Bild scharf ist, ob jemand die Augen zu hat, ob
der Ausschnitt trägt. Heute gibt es aus der Kuratierung heraus keinen Weg, ein Bild groß
anzusehen, ohne die Arbeit zu unterbrechen — die bestehende Detailseite wechselt die Seite,
springt nach oben und lässt die Stelle im Raster verlieren.

Die Großansicht schließt genau diese Lücke: hinsehen, schließen, weiterkuratieren. Sie bewertet
nichts und ersetzt die Detailseite nicht; sie liefert nur die Information, die die Entscheidung an
der Kachel braucht. Betroffen sind beide Kuratierungsschritte — der eigene Album-Entwurf und die
gemeinsame Endauswahl.

## User Story

Als kuratierende Person möchte ich ein Bild aus dem Raster heraus groß ansehen können, ohne meinen
Platz in der Kuratierung zu verlieren, damit ich sicher entscheiden kann, ob es ins Album gehört.

## Akzeptanzkriterien

- [ ] **AK1 – Öffnen im Album-Entwurf.** Im Album-Entwurf ist die Bildfläche jeder Kachel eine Schaltfläche mit dem zugänglichen Namen „Großansicht: {relative_path}“. Klick, Enter und Leertaste öffnen die Großansicht **dieses** Fotos. „Im Album/Gestrichen“, „Alternativen: …“ und der Info-Auslöser öffnen sie nicht und verhalten sich wie bisher.
- [ ] **AK2 – Öffnen in der Endauswahl.** Wie AK1, und zwar in **beiden** Sichten („Unterschiede“ und „Endauswahl“). Die Entscheidungsflächen („Aufnehmen“, „Nicht aufnehmen“, „Herausnehmen“) öffnen die Großansicht nicht.
- [ ] **AK3 – Genau das angeklickte Bild.**
  - Die Überschrift des Dialogs ist der Basisname des angeklickten Fotos. Das Bild ist dessen Display-Variante, `alt` ist der volle `relative_path`, und die Fußzeile zeigt diesen Pfad.
  - Weder eine Taste (Pfeiltasten, Bild↑/↓, Pos1/Ende) noch eine Wischgeste noch ein Bedienelement wechselt zu einem anderen Foto. Es wird kein anderes Bild angefragt.
- [ ] **AK4 – Keine Bewertung.**
  - Die Großansicht enthält genau diese Bedienelemente: „Schließen“ und „Details“, dazu nur im Fehler- oder 404-Zustand „Erneut versuchen“. Sie hat weder ein Bewertungs- noch ein Entscheidungskennzeichen.
  - Öffnen, Betrachten, Aufklappen und Schließen senden keinen schreibenden Request.
  - Nach dem Schließen trägt die Kachel denselben Album- bzw. Endauswahl-Zustand wie vorher.
- [ ] **AK5 – Bildgröße.**
  - Das Bild steht vollständig und unbeschnitten auf der Bühne, der Fläche zwischen Kopf- und Fußzeile. Sein gerendertes Seitenverhältnis entspricht dem natürlichen (±1 %).
  - Es füllt die Bühne in mindestens einer Richtung ganz aus (±1 px), auch wenn die Display-Variante dafür hochskaliert werden muss.
  - Das gilt auch bei aufgeklappten Details: Die Bühne wird kleiner, und das Bild passt sich neu ein.
- [ ] **AK6 – Ab 640 px Fensterbreite.**
  - Die Großansicht liegt als Überlagerung mit 48 px Rand links und rechts und 24 px Rand oben und unten über der Kuratierung.
  - Die Kuratierung bleibt darunter montiert und ist abgedunkelt: Die Abdunklung hat eine Deckkraft > 0.
  - Ein Treffer auf dem Rand liefert den Dialog-Hintergrund (Backdrop), nicht die Seite.
- [ ] **AK7 – Unter 640 px.** Die Großansicht deckt das Fenster randlos vollständig ab (±1 px). Grenzfall: 639 px ist randlos, 640 px hat den Rand.
- [ ] **AK8 – Motivkennung ohne Handgriff.**
  - Beim Öffnen steht ohne weitere Aktion in der Kopfzeile die Liste „Motive“: acht Einträge in Registry-Reihenfolge, jeder mit dem Namen „{Motiv}: {Wert}“. Der Wert ist eine Zahl oder „lokal nicht beurteilbar“ und für jedes Motiv derselbe wie auf der Bilddetailseite.
  - Nichts davon ist fokussierbar oder bedienbar, und kein Eintrag hat ein `title`.
  - `motif_assessment = null` ergibt statt der Liste den Satz „Noch nicht klassifiziert — …“.
  - Solange das Motivset lädt, stehen Platzhalter da. Scheitert es, erscheint eine Meldung mit „Erneut versuchen“.
- [ ] **AK9 – Bilddetails.**
  - „Details“ hat bei **jedem** Öffnen `aria-expanded="false"`. `aria-controls` zeigt auf einen vorhandenen, verborgenen Bereich.
  - Aufgeklappt steht der Bereich zwischen Bühne und Fußzeile und zeigt „Qualität“ und „Bildinhalt“ mit ihren Einzelwerten (im Bildinhalt zusätzlich „Rang im Ereignis“, entfällt ohne Rang), „Feinlabels“ (die Überschrift fehlt ganz, wenn es keine gibt) und „Aufnahme“ (Zeit mit Korrekturzeile, Kamera). Der Ort steht in der Fußzeile, nicht im Bereich.
  - Zuklappen verbirgt den Bereich wieder.
- [ ] **AK10 – Schließwege.**
  - Die Großansicht schließt über (a) „Schließen“, (b) Escape, auch bei aufgeklappten Details, (c) einen Klick auf die Abdunklung oder auf die freie Bühnenfläche neben dem Bild und (d) Browser-Zurück.
  - Sie schließt **nicht** bei einem Klick auf das Bild bzw. den Bildkasten, die Kopf- oder Fußzeile, den Detailbereich oder den Innenabstand des Panels.
  - Jede Öffnung verbraucht genau einen Verlaufsschritt. Zweimal Escape oder ein Doppelklick vor dem Abschluss der Zurück-Navigation verlässt die Kuratierung nicht.
  - Nach dem Schließen führt Browser-Zurück dorthin, wohin es vor dem Öffnen geführt hätte, und öffnet die Großansicht nicht wieder.
- [ ] **AK11 – Zustand nach dem Schließen.**
  - Nach jedem der vier Schließwege gilt: gleiche URL, gleiche Scroll-Position (±1 px), gleiche Sicht der Endauswahl, gleiche Tagesklappung, gleiche Entscheidungen. Die Liste wird nicht neu geladen.
  - Der Tastaturfokus liegt auf dem Auslöser des geöffneten Bildes, und die Rückgabe scrollt nicht.
  - Gibt es diesen Auslöser nicht mehr, weil das Foto aus der Liste verschwunden oder in der aktuellen Sicht nicht gerendert ist, liegt der Fokus auf der Seitenüberschrift.
- [ ] **AK12 – Bedienung ohne Maus.**
  - Der Auslöser ist per Tab erreichbar und steht in der Tab-Folge vor den übrigen Bedienelementen der Kachel. Enter und Leertaste öffnen.
  - Der Erstfokus liegt auf „Schließen“. Tab bleibt in der Großansicht und erreicht „Schließen“, gegebenenfalls „Erneut versuchen“, „Details“ und den aufgeklappten Detailbereich. Escape schließt (AK10/AK11).
- [ ] **AK13 – Laden und Fehler.**
  - Kopf- und Fußzeile stehen sofort. Die Bildfläche hat schon ihre endgültige Größe und zeigt einen Ladezustand mit dem Namen „{relative_path} wird geladen…“.
  - Ein Fehlschlag ≠ 404 zeigt eine Meldung (`role=alert`) mit dem Titel „Das Bild lässt sich nicht laden.“ und darunter, falls vorhanden, dem Server-`detail`; unter der Meldung steht eine eigene Schaltfläche „Erneut versuchen“. Die Pfadzeile der Fußzeile zeigt während des Ladens „Bild wird geladen …“ und im Fehlerzustand „Das Bild lässt sich nicht laden.“. Das Erneut-Versuchen startet einen neuen Abruf, und der Fokus geht danach auf die Bühne, nicht auf `<body>`.
  - Ein 404 zeigt sichtbar „Bild wird noch verarbeitet.“ mit „Erneut versuchen“, **ohne** Fehleroptik und ohne `role=alert`.
  - Alle Schließwege funktionieren in jedem Zustand.
- [ ] **AK14 – Kein Weg zur Detailseite.** Die Großansicht enthält keinen Link. Die Kacheln der Kuratierung verlinken wie bisher nicht auf die Detailseite. Die Detailseite ist wie bisher über die Fotoübersicht erreichbar und sieht unverändert aus: ihre bestehenden Tests bleiben ohne Änderung grün.
- [ ] **AK15 – Neuladen bei offener Großansicht** (aus der Architektur abgeleitet).
  - Nach dem Neuladen der Seite öffnet sich die Großansicht desselben Fotos wieder, sobald die Liste geladen ist. Solange die Liste lädt, wird nichts geschlossen.
  - Steht das Foto nicht in der geladenen Liste, erscheint keine Großansicht und keine Fehlermeldung, und der Öffnungszustand wird aus dem Verlaufseintrag entfernt.
  - Ein späteres Browser-Zurück öffnet nichts.
- [ ] **AK16 – Das Foto verschwindet bei offener Großansicht aus der Liste** (Vorgabe des Orchestrators, z. B. durch ein Neuladen der Endauswahl). Die Großansicht schließt, im Verlauf bleibt kein unsichtbarer Eintrag zurück, und der Fokus liegt auf der Seitenüberschrift.

## Datenmodell-Bezug

Keiner. Kein neues Feld, kein neuer Endpunkt, keine Migration. Gelesen wird das bereits geladene
`PhotoOut` von Album-Entwurf (`GET /projects/{id}/photos?draft=true`) und Endauswahl
(`GET /projects/{id}/album-selection`) sowie die bestehende Display-Variante
`GET /photos/{id}/image?variant=display`.

## Architektur / Umsetzung

**Ansatz.** Das Feature betrifft nur das Frontend: Das Backend ändert sich nicht, und es entsteht keine ADR, weil weder eine neue Technologie noch eine neue Abhängigkeit noch eine Änderung am Datenmodell dazukommt. Die Großansicht ist eine modale Überlagerung (natives `<dialog>` über `showModal()`). Dadurch liegt sie im Top-Layer über Kopfzeile und Schrittleiste. Sie wird **innerhalb** der gerade montierten Kuratierungsseite gerendert. Geöffnet wird sie über einen eigenen Verlaufseintrag auf **derselben URL** mit `location.state`. Die Seite wird dabei nicht neu montiert.

### Datenquellen

- **Großes Bild:** `GET /photos/{id}/image?variant=display`. Das ist die bestehende Display-Variante mit 2048 px an der längsten Kante (`thumbnails.py::DISPLAY_MAX_SIZE`). Sie wird wie auf der Detailseite über `PhotoImage variant="display"` geladen.
- **Motivkennung und Details:** Sie stehen im `PhotoOut`, das die Seite schon geladen hat. Der Entwurf (`GET /projects/{id}/photos?draft=true`) und die Endauswahl (`GET /projects/{id}/album-selection`) bauen jedes Foto über `api/photos.py::_to_photo_out`. Damit liefern beide `motif_assessment`, `motifs`, `criterion_scores`, `fine_labels`, `taken_at`/`taken_at_original`/`time_offset_minutes`, `camera`, `event` und `aspect_ratio`. Die Großansicht holt das Foto per `items.find(id)` aus der geladenen Liste der Seite (Muster `alternativesPhoto` in `AlbumDraftPage`) und legt keine Kopie im Zustand ab.
- **Motivset** (Registry-Reihenfolge, Namen, Bänder): Die Großansicht ruft selbst `useMotifsQuery()` auf (`staleTime: Infinity`). Im Entwurf liegt das Set schon im Cache. In der Endauswahl löst das erste Öffnen genau einen Abruf aus.
- **Backend: nein.** Endpunkt, Bildgröße und alle Felder gibt es schon. Es kommt kein neues Feld und kein neuer Endpunkt dazu.

### Öffnen, Schließen, Browser-Zurück

Der neue Hook `hooks/useCurationLightbox.ts` wird von beiden Seiten gleich benutzt:

- **Der Zustand ist der Verlaufseintrag.** `openPhotoId` wird nur aus `location.state.grossansicht` gelesen. Gilt der Wert nicht als `Number.isSafeInteger`, ist er `null`. Daneben gibt es keinen eigenen `useState`.
- `open(photoId)` legt mit `navigate({ pathname, search }, { state: { grossansicht: photoId } })` einen neuen Eintrag an (Push). Weil die Route gleich bleibt, bleiben `AlbumDraftPage` und `AlbumSelectionPage` montiert. Ihr lokaler Zustand bleibt unberührt: Tagesklappung, Sicht „Unterschiede“/„Endauswahl“, laufende Entscheidungen und `knownEventGroupsRef`. Auch der Query-Cache bleibt unberührt. `BrowserRouter` stellt keine Scroll-Position wieder her, und `lockBodyScroll` hält die Seite fest, solange die Überlagerung offen ist.
- `close()` gilt für die Schließen-Schaltfläche, Escape und den Klick neben das Bild. Wurde der Eintrag in dieser Montierung per `open` angelegt, ruft `close()` `navigate(-1)` auf. Stammt er aus einem Reload oder aus Vorwärts-Navigation, ersetzt es ihn mit `navigate({ pathname, search }, { replace: true, state: null })`. So verhält sich jeder Schließweg wie Browser-Zurück, und im Verlauf bleibt kein „offener“ Eintrag zurück, den ein späteres Zurück wieder öffnen würde.
- **Invariante:** `close()` wirkt je Öffnung höchstens einmal. Ein Riegel sperrt weitere Aufrufe, bis `openPhotoId` wechselt. Ohne ihn würde ein zweites Escape oder ein Doppelklick vor dem asynchronen `popstate` zwei Einträge zurückgehen und die Kuratierung verlassen.
- Browser-Zurück schließt ohne eigenen Code: Der Eintrag mit dem State wird verlassen, `openPhotoId` wird `null`, und die Überlagerung wird nicht mehr gerendert.
- Die URL ändert sich nicht. Sicht und Filter der Seiten sind lokaler Zustand, deshalb könnte eine URL mit geöffnetem Bild nach einem Reload nicht an dieselbe Stelle führen. Bei einem Reload mit offener Großansicht bleibt `history.state` erhalten, und die Großansicht öffnet sich nach dem Laden der Liste erneut. Steht das Foto nicht (mehr) in der geladenen Liste, rendert die Seite keine Überlagerung.

### Fokus-Rückgabe

- Der Hook führt eine Zuordnung von `photoId` zum Auslöser-Element. Sie wird über den Callback-Ref `triggerRef(photoId)` befüllt, der an die Kachel durchgereicht wird.
- Wechselt `openPhotoId` von einer Id auf `null`, setzt ein Effekt den Fokus mit `focus({ preventScroll: true })` auf den Auslöser dieser Id. Das gilt für jeden Schließweg, auch für Browser-Zurück.
- Die Rückgabe hängt **nicht** am vorher fokussierten Element. Safari fokussiert einen angeklickten Button nicht, und nach einem Reload gibt es kein solches Element.
- Die Großansicht schaltet die Fokus-Rückgabe des Modal-Hooks ab (`useModalDialog({ …, returnFocus: false })`; Standard ist `true`, der `Dialog` ist unverändert). Jene fokussiert ohne `preventScroll`; den Fokus setzt allein der Effekt in `useCurationLightbox`.

### Komponenten

| Datei | Änderung |
|---|---|
| `frontend/src/lib/useModalDialog.ts` (neu) | Wird **ohne Verhaltensänderung** aus `components/ui/dialog.tsx` herausgelöst. Enthält `showModal()`/`close()`, die Fokusfalle, die Absprache zwischen Esc und `cancel`, `lockBodyScroll`, die Fokus-Rückgabe an das vorher fokussierte Element und den Erstfokus über `initialFocusRef`. Die Option `returnFocus` (Standard `true`) schaltet die Fokus-Rückgabe ab, für Aufrufer, die den Fokus selbst setzen. `Dialog` nutzt den Hook, seine bestehenden Tests bleiben unverändert grün. |
| `frontend/src/components/CurationLightbox.tsx` (neu) | Die Großansicht. Props: `photo: PhotoOut` und `onClose`. Eigenes `<dialog>` über `useModalDialog`. Den zugänglichen Namen liefert der Dateiname in der Kopfzeile, der Erstfokus liegt auf „Schließen“.<br>Aufbau nach Entwurf: Kopfzeile mit Dateiname, Motivreihe und Schließen; darunter Bildfläche und Fußzeile mit dem Pfad. Dazu kommt eine Detail-Schaltfläche (`aria-expanded`/`aria-controls`, lokaler Zustand, anfangs zu). Sie klappt Einzelwerte, Feinlabels und Aufnahmeangaben auf. Der Zustand setzt sich bei jedem Öffnen über `key={photo.id}` zurück.<br>Auf schmaler Breite füllt das `<dialog>` den Sichtbereich (`dvh`/`vw`). Auf breiter Breite steht es eingerückt, und `::backdrop` dunkelt die Seite ab.<br>Ein Klick schließt, wenn sein Ziel das `<dialog>` selbst ist (Backdrop) oder die Bildbühne außerhalb des Bildkastens.<br>Die Datei importiert **keine** Mutation, kein `Link` und keinen Pfad auf die Detailseite. Sie liest keines der drei Endauswahl-Felder und nicht `isInAlbum`. |
| Bildfläche in `CurationLightbox` | Der Bildkasten hat genau die eingepasste Bildgröße. Die Bühne trägt `container-type: size`, der Kasten `aspect-ratio` aus `photo.aspect_ratio` und `width: min(100cqw, <ratio>·100cqh)` als numerischen Inline-Stil (wie in `PhotoGridTile`). Darin steht `PhotoImage variant="display"` in `size-full`. Fehlt `aspect_ratio`, füllt der Kasten die Bühne mit `object-contain`, und „neben das Bild“ ist dann nur noch der Backdrop. Den Stil liefert `frontend/src/utils/imageFit.ts::fittedImageBoxStyle`: Nur eine endliche positive Zahl ergibt `aspectRatio` und Breite, jeder andere Wert `undefined` (Auflage S4). |
| `frontend/src/components/PhotoImage.tsx` | Neue optionale Props `retryable` und `onRetry`. Mit `retryable` zeigt der Fehlerzustand ein `Alert` mit „Erneut versuchen“ und der 404-Platzhalter sichtbar „Bild wird noch verarbeitet.“ mit „Erneut versuchen“ (ohne `role=alert`, nicht unter `role=img`). Der Druck erhöht einen internen Versuchszähler (Abhängigkeit des Lade-Effekts) und ruft danach `onRetry`, über das der Aufrufer den Fokus setzt. Ohne `retryable` bleibt alles wie bisher. |
| `frontend/src/components/MotifStrengthRow.tsx` (neu) | Schreibgeschützte Motivreihe für die Kopfzeile (Baustein `motiv-reihe`). Zeigt acht `MotifStrengthSymbol` in Registry-Reihenfolge, nicht bedienbar, jedes mit dem zugänglichen Namen „Motiv: Wert“. Während des Ladens erscheint ein Skeleton, bei einem Fehler des Motivsets ein `Alert` mit Retry. Bei `motif_assessment === null` steht der Satz statt der Reihe. |
| `frontend/src/utils/motifStrength.ts` | Die Ableitung je Motiv zieht aus `MotifStrengthSection.tsx` hierher: Anzeigename, Füllstufe, Füllhöhe und Werttext samt Korrektur und „lokal nicht beurteilbar“. Reihe **und** Bereich lesen sie von hier, damit der zugängliche Name nur an einer Stelle entsteht. Auch `UNASSESSED_TEXT` wird hier geteilt. |
| `frontend/src/components/PhotoCaptureFacts.tsx` (neu) | Wird aus `PhotoDetailPage.tsx` herausgelöst: Aufnahmezeit mit Korrekturzeile, Kamera und Ort (`eventPlaceName`). Die Test-Handles `taken-at-section` und `place-line` bleiben, die Überschriftenstufe kommt als Prop. Die Detailseite rendert die Komponente und sieht unverändert aus. |
| Inhalt der Details | `CriterionScoreGrid` (Bewertungskriterien; neue Props `titles`, `contentRows` für „Rang im Ereignis“ und `className`, mit `contents` reihen sich beide Blöcke in das Dreispaltenraster der Großansicht ein; Detailseite unverändert), `FineLabelList` und `PhotoCaptureFacts` (neue Props `heading` und `showPlace`; die Großansicht zeigt „Aufnahme“ ohne Ort). Den Ort zeigt die Fußzeile über `eventPlaceName`; `PhotoImage` meldet seinen Ladezustand über `onStatusChange` für die Pfadzeile. **Nicht** `CriterionDetailsList`, die bleibt dem Kachel-Popover vorbehalten (`photoDetail.structure.test.ts`). |
| `frontend/src/components/PhotoCard.tsx` | Die Bildfläche wird zum Auslöser: `onImageActivate`, `imageTriggerRef` und `imageTriggerLabel` legen einen `<button type="button">` um die Bildfläche. Die Ecken-Overlays bleiben Geschwister. Die Prop `to` (Link) entfällt, weil sie keinen Aufrufer im Produktionscode mehr hat. Die Bildfläche behält so genau einen Aktivierungsweg. |
| `frontend/src/components/CurationPhotoTile.tsx`, `frontend/src/components/SelectionPhotoTile.tsx` | Neue Props `onOpenLarge` und `largeTriggerRef`, durchgereicht an `PhotoCard`. Der zugängliche Name des Auslösers enthält den Dateinamen, wie die übrigen Schaltflächen der Kachel. |
| `frontend/src/pages/AlbumDraftPage.tsx`, `frontend/src/pages/AlbumSelectionPage.tsx` | Rufen `useCurationLightbox({ items, headingRef })` auf (`items` ist die geladene Liste, `undefined` während des Ladens) und verdrahten die Kacheln. Der Hook schlägt das Foto per `items.find(…)` nach und liefert es als `photo`; am Seitenende steht `{photo && <CurationLightbox key={photo.id} … />}`. In der Endauswahl kommt das Foto aus `items`, nicht aus der gefilterten Sicht. |

### Begleitende Pflege im selben PR

- `docs/architecture.md`: neuer Eintrag zur Großansicht (Komponente, Verlaufseintrag als Öffnungszustand, Fokus-Rückgabe).
- `frontend/src/designSystem.contract.test.ts`: Freigabeeintrag für die Abdunklung des neuen `<dialog>`, nach dem Vorbild des Eintrags für `ui/dialog.tsx`. Der Wert kommt aus dem Entwurf (Lücke `abdunklung`).
- `frontend/src/photoDetail.structure.test.ts`: Die Prüfung, ob `eventPlaceName` importiert wird, zieht von `pages/PhotoDetailPage.tsx` auf `components/PhotoCaptureFacts.tsx` um.
- `design/penpot/views.json`: `src/components/CurationLightbox.tsx` in `kuratierung-grossansicht.produktdateien` aufnehmen.

### Reihenfolge

1. `useModalDialog` herauslösen; die grünen Dialog-Tests sind der Nachweis.
2. `PhotoImage.retryable` ergänzen.
3. `PhotoCaptureFacts` und die Motiv-Ableitung herauslösen; die Detailseite bleibt unverändert.
4. `MotifStrengthRow` bauen.
5. `CurationLightbox` bauen.
6. `useCurationLightbox` bauen.
7. Auslöser in `PhotoCard` und die beiden Kacheln.
8. Beide Seiten verdrahten.
9. Begleitende Pflege.

### Ergänzungen aus der Konsultation

- **Foto verschwindet bei offener Großansicht** (z. B. Neuladen der Endauswahl): Erst wenn die Liste
  erfolgreich geladen ist und `openPhotoId` darin fehlt, ruft `useCurationLightbox` selbst `close()` — es bleibt kein
  unsichtbarer Verlaufseintrag stehen. Während die Liste lädt, wird nicht geschlossen.
- **Fokus-Rückfall:** Existiert der Auslöser des geöffneten Fotos nicht (mehr) — Foto aus der Liste
  verschwunden oder in der aktuellen Sicht nicht gerendert —, geht der Fokus auf die
  Seitenüberschrift `h1` (`tabIndex={-1}`). Die Zuordnung `photoId → Auslöser` löscht ihren Eintrag,
  wenn der Callback-Ref mit `null` gerufen wird; ein abgehängter Knoten wird nie fokussiert.
- **Schließen per Klick neben das Bild** greift nur, wenn **sowohl** das `pointerdown`- **als auch**
  das `click`-Ziel eine schließende Fläche ist (`<dialog>`/Backdrop oder freie Bühne). Ein auf dem
  Bild oder der Kopfzeile begonnener und neben dem Bild beendeter Zug (z. B. Markieren des
  Dateinamens) schließt nicht.
- **Riegel** gegen doppeltes Zurück sitzt in `useCurationLightbox`, nicht in `useModalDialog`: Das
  Grundelement ruft `onClose` bei jedem Escape (`ui/dialog.test.tsx`).
- `onOpenLarge` und `largeTriggerRef` sind an beiden Kacheln **Pflicht**-Props.
- Die 404-Fläche von `PhotoImage` mit `retryable` trägt ihre Schaltfläche nicht unter einem Vorfahren
  mit `role="img"`.

## UI/UX

**Stand:** ausgearbeitet
**Penpot-Seite:** Ansicht — Kuratierung Großansicht
**Schlüssel:** kuratierung-grossansicht

Der Entwurf ist in beiden Prüfbreiten `mobile` (360 × 740) und `desktop` (1280 × 800) ausgearbeitet. Die Zustandsachse `zustand` hat die Werte `gefuellt`, `details-offen`, `ladend` und `fehler`. Verwendete Bausteine: `button`, `motiv-reihe`, `alert`, `skeleton`.

### Auslöser in der Kachel

- In Album-Entwurf und Endauswahl wird die Bildfläche der Kachel zu einem nativen `<button type="button">` mit dem zugänglichen Namen **„Großansicht: {relative_path}“**. Das ist dieselbe Form `{Aktion}: {Pfad}` wie bei „Im Album: …“ und „Alternativen: …“. Enter und Leertaste öffnen die Großansicht, ein eigener Tastatur-Handler ist nicht nötig.
- Der Zeiger über der Bildfläche ist `cursor-zoom-in`. Die Bildfläche ändert beim Überfahren sonst nichts: keine Deckkraft, kein Filter, denn keine Bildfläche wird gedämpft. Fokus zeigt allein die globale Kontur.
- In der Tab-Reihenfolge steht der Auslöser vor dem Info-Auslöser und den Schaltflächen der Fußzeile. Die Ecken-Overlays bleiben Geschwister der Bildfläche.

### Layout je Breite

Maße nach dem Penpot-Entwurf (gemessen 2026-09-26). **Umbruch bei Tailwind `sm` (640 px).**

| | unter `sm` (Telefon) | ab `sm` |
|---|---|---|
| Ausdehnung | Füllt den Sichtbereich: `inset-0` | Überlagerung mit 48 px seitlich und 24 px oben/unten: `sm:inset-x-12 sm:inset-y-6` |
| Form | Kein Radius, kein Rand | `sm:rounded-lg sm:border sm:border-border` |
| Innenabstand / Zeilenabstand | `p-4` / `gap-4` | `sm:p-6` / `gap-4` |
| Abdunklung | Nicht sichtbar, weil alles verdeckt ist | `backdrop:bg-bg/72` |
| Kopfzeile | Dateiname und „Schließen“, darunter die Motivreihe | Dateiname links, Motivreihe rechts; kein „Schließen“ |
| „Schließen“ | in der Kopfzeile | rechts in der Bedienzeile (dasselbe Element; positioniert wird ein Wrapper mit `sm:absolute sm:right-6 sm:bottom-6`, weil `tap-target` am Button selbst `position: relative` setzt) |
| Fußzeile | Pfad und Ort untereinander | Pfad links, Ort ab Panelmitte (`sm:grid-cols-2`) |
| Detailblock | einspaltig | drei Spalten |

Gemeinsam für beide Breiten:

- Das `<dialog>` hebt die UA-Maße auf (`m-0 h-auto w-auto max-h-none max-w-none`); die Ausdehnung kommt allein aus `inset`. Panel `bg-elevated`. Keine Öffnungs- oder Schließanimation, kein Weichzeichner.
- **Aufbau von oben nach unten** als Flex-Spalte:
  1. **Kopfzeile:** Dateiname als `h2`, Basisname, `min-w-0 flex-1 truncate text-lg font-medium text-text-h` (20 px, Schnitt 500, auf beiden Breiten gleich). Motivreihe `order-last w-full sm:order-none sm:w-auto`.
  2. **Bühne:** `flex-1 min-h-0` ohne eigene Grundfläche, Bildkasten nach Architektur, das Bild `rounded-md`. Zeiger in der freien Bühnenfläche: `cursor-zoom-out`.
  3. **Detailblock** (nur aufgeklappt): eigene Karte `max-h-1/2 overflow-y-auto rounded-md border border-border bg-surface p-6`.
  4. **Fußzeile:** Pfadzeile mit `relative_path` und Ortsname (`eventPlaceName`, sonst „nicht bestimmbar“), beide `text-sm text-text`, keine Monospace-Schrift; darunter die Bedienzeile mit „Details“ links.
- **Bildgröße:** Das Bild ist so groß, wie die Bühne zulässt. Es gibt keine Obergrenze, auch wenn die Display-Variante dafür hochskaliert wird.

### Zustände

- **`gefuellt`:** Kopfzeile mit Dateiname und Motivreihe; Bild eingepasst; Fußzeile mit Pfad und Ort; Details zugeklappt. Die Großansicht zeigt weder Bewertungszustand noch Bewertungskennzeichen noch Entscheidungsschaltfläche.
- **`details-offen`:** Zwischen Bühne und Fußzeile steht ein Bereich (`<section aria-label="Bilddetails" tabIndex={0}>`), weil er ohne Tastaturfokus nicht scrollbar wäre.
  - Inhalt (ab `sm` drei Spalten, darunter einspaltig in dieser Reihenfolge): „Qualität“ mit Einzelwerten, „Bildinhalt“ mit Einzelwerten und „Rang im Ereignis“ (`rank_position` von `partition_size`, entfällt ohne Rang) — beides über `CriterionScoreGrid` mit eigenen Überschriften; dann „Feinlabels“ (`h3`, fehlt ganz ohne Feinlabels) mit `FineLabelList` und „Aufnahme“ (`PhotoCaptureFacts` ohne Ort).
  - Typografie aus Penpot gemessen (Brett „details-offen“, alle Texte Inter 14 px, ohne Versalien): Überschriften „Qualität“, „Bildinhalt“, „Feinlabels“ und „Aufnahme“ `text-sm text-text-h`, Schnitt 400; Zeilen: Name in `--text`, Wert in `--text-h`, Schnitt 400 (`valueClassName`); Aufnahmezeit in Inter (nicht Monospace) und Kamera in `--text` (`PhotoCaptureFacts appearance="compact"`, `headingClassName` an beiden Bausteinen).
  - Belichtungsdaten des Entwurfs entfallen; es gibt sie im Datenmodell nicht.
  - Der Bereich nimmt höchstens die halbe Panelhöhe ein und scrollt darüber hinaus in sich. Die Bühne schrumpft entsprechend, und das Bild passt sich neu ein.
  - Der Container steht immer im DOM und ist zugeklappt `hidden`. So zeigt `aria-controls` nie ins Leere.
- **`ladend`:** Kopf- und Fußzeile stehen sofort. Der Bildkasten hat bereits seine endgültige Größe und trägt den `Skeleton` (Zugänglicher Name: „{relative_path} wird geladen…“); die Pfadzeile zeigt „Bild wird geladen …“. Solange das Motivset lädt, stehen an Stelle der Reihe acht Platzhalter, `size-6`, `gap-2`.
- **`fehler`:** In der Bühne ein `Alert` (Ausprägung `error`) mit dem Titel „Das Bild lässt sich nicht laden.“ und, falls vorhanden, `ApiError.detail` wörtlich; darunter eine eigene Hauptschaltfläche „Erneut versuchen“. Die Pfadzeile zeigt „Das Bild lässt sich nicht laden.“. Nach „Erneut versuchen“ geht der Fokus auf die Bühne (`tabIndex={-1}`). Scheitert das Laden des Motivsets, ersetzt das bestehende `Alert` mit Retry die Motivreihe.
- **Platzhalter bei 404** (kein eigener Entwurfszustand): „Bild wird noch verarbeitet.“ und darunter die Hauptschaltfläche „Erneut versuchen“, ohne Fehleroptik.

### Motivreihe (`MotifStrengthRow`)

Die schreibgeschützte Reihe genügt dem Entwurf und der Anforderung „Motivkennung ohne weiteren Handgriff“. Dafür gelten diese Bedingungen:

- `<ul aria-label="Motive" class="flex gap-2">` enthält acht `<li>` in Registry-Reihenfolge. Jedes `<li>` trägt ein `<span role="img" aria-label="{Motiv}: {Wert}">` um das `MotifStrengthSymbol` in Größe 24.
- Der Wert ist die Zahl oder „lokal nicht beurteilbar“, nie ein Bandwort.
- Nicht fokussierbar, keine Trefferflächen-Aufspannung, kein `title`-Attribut, keine Grundlagenzeile und kein Glossar.
- Bei `motif_assessment === null` steht statt der Reihe der geteilte Satz „Noch nicht klassifiziert — …“ in `text-xs text-text`.
- Bei `excluded_document` steht die Reihe unverändert und ohne Satz. Ein Weg zur Korrektur gehört an die Stelle, an der korrigiert wird, und das ist nicht die Großansicht.

### Beschriftungen und zugängliche Namen

| Element | Sichtbar | Zugänglich |
|---|---|---|
| Auslöser in der Kachel | – (Bildfläche) | „Großansicht: {relative_path}“ |
| Dialog | – | `aria-labelledby` → `h2` (Basisname), `aria-modal="true"` |
| Schließen | „Schließen“, Hauptschaltfläche (`default`), 32 px mit `tap-target` | derselbe Text, kein abweichendes `aria-label` |
| Details | Symbol `chevron-down` (offen: `rotate-180`, ohne Übergang) und „Details“; `ghost`, 32 px mit `tap-target` | „Details“, `aria-expanded`, `aria-controls` |
| Bild | – | `alt` = `relative_path` |
| Detailbereich | – | `section`, „Bilddetails“ |

Dateiname, Pfad, Feinlabels und Orts- bzw. Kameratexte erscheinen ausschließlich als React-Textknoten.

### Schließen, Fokus, Tastatur

- **Schließwege:** „Schließen“, Escape (schließt auch bei offenen Details sofort), Browser-Zurück, Klick auf die **Abdunklung** oder auf die **freie Bühnenfläche** neben dem Bildkasten.
- **Kein Schließweg:** ein Klick auf das Bild selbst, auf Kopf- oder Fußzeile, auf den Detailbereich oder in den Innenabstand des Panels. Der Klick auf `::backdrop` trifft das `<dialog>`-Element selbst; der Innenabstand liegt deshalb auf einem inneren Container, damit ihn keine Schließprüfung mit dem Backdrop verwechselt.
- **Bewusste Abweichung vom `Dialog`:** Ein Klick auf den Hintergrund schließt hier. Es geht nichts verloren, und der Klick neben das Bild ist ein Akzeptanzkriterium.
- **Erstfokus** liegt auf „Schließen“. Die Fokusfalle umfasst Schließen → ggf. „Erneut versuchen“ → ggf. Detailbereich → „Details“.
- **Nach jedem Schließweg** liegt der Fokus auf dem Auslöser des geöffneten Bildes (`preventScroll`). Die globale Fokuskontur erscheint dort nach Heuristik von `:focus-visible`. Scroll-Position, Tagesklappung, Sicht und Auswahl bleiben unverändert.
- Pfeiltasten und Wischgesten haben keine Funktion. Es gibt kein nächstes oder voriges Bild und keinen Weg zur Detailseite.

### Abgleich mit den Lücken der Nutzlast

| Lücke | Festlegung |
|---|---|
| `behaelter` | Panel `bg-elevated` (ab `sm` `rounded-lg`, Rand `--border`); Bühne ohne Grundfläche, Bild `rounded-md`; Detailblock als Karte `bg-surface rounded-md border-border p-6`. |
| `chipbaustein` | Umgesetzt über die bestehende `FineLabelList`; kein neuer Baustein. |
| `bildschirmfuellend` | Umbruch bei `sm` (640 px): darunter `inset-0` ohne Rand, darüber `sm:inset-x-12 sm:inset-y-6` mit Radius und Rand. |
| `bildmasse` | Keine festen Maße: Bühne `flex-1 min-h-0`, Bildkasten per Container-Einheiten eingepasst. |
| `abdunklung` | `backdrop:bg-bg/72` — Deckkraft 0.72 über `--bg` nach Entwurf. |
| `fokus` | Siehe „Schließen, Fokus, Tastatur“; es gilt ausschließlich die globale Fokuskontur. |
| `trefferflaeche` | „Schließen“ und „Details“: 32 px sichtbar, `tap-target` auf der kurzen Achse. Abstand zur schließenden Bühnenfläche 12 px (`gap-3`), damit die Aufspannung nicht in die Bühne ragt. |
| `schriftschnitt` | Dateiname `font-medium` (500) in Inter, `text-lg`. |
| `seitengrund` | Betrifft nur Penpot; nichts umzusetzen. |
| `rueckweg` | Verhalten nach Architektur; die Großansicht zeigt keinerlei Bewertungselement. |
| `bewegung` | Puls des `Skeleton` mit `motion-reduce:animate-none`; sonst keine Bewegung. |

### Design-System

Im selben Pull Request ergänzen, in `specs/architecture/0004-design-system.md` und im Skill `design-system`:

- **Neues Muster „Großansicht aus dem Raster“:**
  - Bildfläche als Auslöser mit `cursor-zoom-in`.
  - Unter `sm` bildschirmfüllend, darüber Überlagerung mit `inset-x-12`/`inset-y-6`.
  - Panel `bg-elevated`, Bühne ohne Grundfläche, Detailblock als Karte `bg-surface`.
  - Schließt auch per Hintergrundklick und Browser-Zurück, als bewusste Abweichung vom `Dialog`.
  - Erstfokus auf „Schließen“; Fokus-Rückgabe an den Auslöser.
  - Bewertet nichts.
- **Freigabeliste der Abdunklungen** um `backdrop:bg-bg/72` der Großansicht erweitern.
- **Muster „Füllstandsreihe“:** schreibgeschützte, nicht bedienbare Kopfzeilenfassung mit `role="img"` je Symbol als dritte Verwendungsstelle aufnehmen.

## Security

Sicherheitsrelevant, kein Blocker: kein Backend-Anteil, kein neuer Endpunkt, kein Secret, keine
Änderung an Auth oder an der Sichtbarkeit zwischen den beiden Nutzern. Neu sind drei Dinge: Der
Öffnungszustand liegt im Browser-Verlauf (`location.state`), Fremdtexte erscheinen an einer neuen
Renderstelle, und ein API-Wert geht in eine zusammengesetzte Stilangabe.

**S1 — Aus `location.state` wird nur eine Id gelesen, und sie wird nur nachgeschlagen.**
`openPhotoId` ist `location.state.grossansicht`, wenn `Number.isSafeInteger` gilt, sonst `null`;
kein `as`-Cast auf den Zustand. Die Id wählt per `items.find` ausschließlich ein Foto der bereits
geladenen Liste; Bildabruf, Auslöser-Zuordnung und jede weitere Verwendung nehmen `photo.id` des
gefundenen Objekts, nie den Rohwert. Kein Treffer heißt: keine Überlagerung, kein Abruf. Gilt für
`useCurationLightbox` und beide Seiten. Angriffsmodell: Der Verlaufszustand überlebt Reload,
Sitzungswiederherstellung und App-Updates, seine Form garantiert also nicht die laufende Fassung.
Bricht bei Verletzung: Ein ungeprüfter Wert in `/photos/${…}/image` macht aus dem Bildabruf eine
GET-Anfrage mit Bearer-Token an einen beliebigen API-Pfad (`1/../../…` normalisiert der
URL-Parser weg), und ein Abruf per Rohwert statt per Nachschlagen öffnet Fotos außerhalb der
Kuratierung.

**S2 — Der Verlaufszustand trägt nur die Id.** In `location.state` steht `{ grossansicht: <id> }`
und nichts sonst: kein `relative_path`, kein Dateiname, kein `PhotoOut`, keine Feinlabels. Gilt
für jeden Eintrag, den `open()` oder `close()` schreibt. Bricht bei Verletzung: Der Browser legt
den Verlaufszustand in seiner Sitzungswiederherstellung auf der Platte ab. Dateinamen und
Ordnerstruktur, die das Projekt als sensibles Datum führt, lägen dort über Abmelden und Löschen des
Tokens hinaus, außerhalb jeder Bereinigung durch die Anwendung.

**S3 — Fremdtext steht nur als React-Textknoten.** Dateiname (`h2`), `relative_path` (Fußzeile),
Feinlabels, Ortsname, Kameralabel und `ApiError.detail` im Fehler-`Alert` sind ausschließlich
React-Kinder; `relative_path` steht darüber hinaus nur in `alt` und `aria-label`. Untersagt:
`dangerouslySetInnerHTML`, HTML-String-Props und jede Verwendung in `href`, `src`, `style` oder
`url()`. Kriterien, Feinlabels und Aufnahmeangaben laufen über die bestehenden
`CriterionScoreGrid` und `FineLabelList` sowie das herausgelöste `PhotoCaptureFacts`; für keinen
dieser Werte entsteht eine zweite Renderstelle. Der Test `rendert einen feindlich belegten
Ortsnamen aus $name als reinen Textknoten` und der Sicherheitskommentar an der Ortszeile ziehen
mit der Renderstelle nach `PhotoCaptureFacts`. Bricht bei Verletzung: Ein eingeschleustes Skript
liest das Session-Token aus `localStorage`, das sind bis zu 30 Tage Sitzungsübernahme ohne
Widerrufsweg.

**S4 — Das Seitenverhältnis geht nur als geprüfte Zahl in den Stil.** `aspectRatio` wird als
Zahl gesetzt. Die Breite `min(100cqw, <r> * 100cqh)` ist zwangsläufig eine zusammengesetzte
Zeichenkette. Sie entsteht nur, wenn `typeof r === 'number' && Number.isFinite(r) && r > 0`, und
nur aus dieser Zahl und festen Literalen; sonst gilt der Rückfall ohne eingepassten Bildkasten.
Wandert der Wert in eine CSS-Custom-Property (etwa für eine Utility in `index.css`), gilt dieselbe
Bedingung, und die Utility liest ihn nur in `calc()`/`min()` einer Eigenschaft ohne
`url()`-Kontext. Untersagt: `r` ungeprüft oder als Zeichenkette durchreichen, `url()`, `href`,
`src`. Nachweis: Ein Test mit feindlich belegtem `aspect_ratio` (Zeichenkette mit `url(` und `;`)
belegt, dass weder der Text noch `url(` im Stil landet und der Rückfall greift. Bricht bei
Verletzung: Eine Custom-Property nimmt beliebige Token-Folgen auf und trägt sie über `var()`
dorthin, wo sie wieder als CSS gelesen werden. Serverseitig schließt nur die Bereichsprüfung des
einen Schreibpfads den Wert ab.

**Geprüft und ohne Befund:**

- **Sichtbarkeit in der Endauswahl:** Die Großansicht zeigt Motivreihe, Kriterien, Feinlabels und
  Zeit, Kamera und Ort. Das sind Projektaussagen aus demselben `PhotoOut`, das die Seite schon
  geladen hat, und dieselben Angaben, die die Detailseite jedem angemeldeten Nutzer zu jedem Foto
  zeigt. Die Motivkorrektur ist eine Aussage über das Foto; ihr `user_id` wird nicht
  ausgeliefert. Nutzerbezogenes (`ratings[]`, `suggestion`) zeigt die Großansicht nicht. Es
  entsteht keine neue Datenklasse zwischen den beiden Nutzern.
- **Bild-Endpunkt unverändert:** `GET /photos/{id}/image` mit `get_current_user`, `variant` als
  `Literal`, `nosniff`; Abruf id-basiert über `apiFetchBlob` und Object-URL.
- **Keine neue Abfrage und keine Persistenz des Query-Caches:** Die Cache-Schlüssel-Auflage aus
  Album-Entwurf und Endauswahl ist unberührt; `useMotifsQuery` liest die statische Registry.
- **Schutz der Route bleibt:** Die Großansicht rendert innerhalb der Seite unter `ProtectedRoute`
  und hängt nach einem 401 mit ihr ab. `LoginPage` übernimmt aus `from` nur `pathname`, der
  Zustand geht also nicht durch den Login.
- **URL unverändert:** Keine Foto-Id in URL, Referrer oder Server-Log.
- **„Erneut versuchen" nur auf Handgriff:** keine automatische oder periodische Wiederholung,
  also kein Anfragensturm.

## Teststrategie

Leitsatz aus dem Testkonzept: Jede Zusage wird auf der niedrigsten Ebene geprüft, die sie widerlegen kann. jsdom deckt Struktur, Rollen, Tastaturwege, Verlaufslogik (MemoryRouter) und Fokus ab. Nach E2E kommt nur, was echte Geometrie, den Top-Layer, echtes `popstate`/Reload oder echtes Scrollen braucht. Das Backend ändert sich nicht, daher gibt es keine pytest-Fälle.

### Ebene je Akzeptanzkriterium

| AK | Unit (Hook/reine Funktion) | Komponente/Seite (vitest + Testing Library) | E2E (Playwright) |
|---|---|---|---|
| AK1/AK2 | – | Kacheltests: Name des Auslösers, Klick → `onOpenLarge(id)`; Entscheidungsflächen rufen ihn nicht. Seitentests: Öffnen in beiden Seiten und in beiden Sichten der Endauswahl | – |
| AK3 | – | `CurationLightbox.test.tsx`: Überschrift, `alt`, Fußzeilenpfad, Abruf `(id,'display')`; Pfeil-/Bild-/Pos1-Tasten ändern nichts und lösen keinen Abruf aus | – |
| AK4 | – | Dialog: exakte Menge der Schaltflächen (Gleichheit, nicht „enthält“), 0 Links. Seiten: keine Mutations-API aufgerufen, Kachelzustand vorher = nachher. Strukturwächter (siehe unten) | – |
| AK5 | – | – (jsdom hat kein Layout) | Inhaltsrechteck in der Bühne, eine Achse bündig, Verhältnis gleich dem natürlichen; zwei Formate; mit aufgeklappten Details |
| AK6/AK7 | – | – (Polyfill, kein `::backdrop`) | Ausdehnung bei 639 vs. 640 px, Treffertest auf dem Rand, Deckkraft von `::backdrop` |
| AK8 | – | `MotifStrengthRow.test.tsx` | – |
| AK9 | – | `CurationLightbox.test.tsx` | Nur die Bühnenschrumpfung (unter AK5) |
| AK10 | `useCurationLightbox.test.tsx`: push/back/replace, Riegel | Lightbox: Aufteilung der Klickziele in schließend und nicht schließend. Seiten: alle vier Wege, Zurück über eine Verlaufssonde | Klick neben/auf das Bild geometrisch, zweimal Escape (echt und synthetisch), `page.goBack()` |
| AK11 | Fokus-Rückgabe an das registrierte Element | Seiten: Fokus je Schließweg, lokaler Zustand, keine Neuladung | scrollY je Schließweg, Auslöser teilweise außerhalb des Sichtbereichs (`preventScroll` selbst: Unit) |
| AK12 | – | Kachel: Tab-Folge, Enter/Leertaste. Lightbox: Erstfokus, Tab-Zyklus einschließlich Detailbereich | `tap-targets` (schmal): „Schließen“ und „Details“ |
| AK13 | – | `PhotoImage.test.tsx` (`retryable`), `CurationLightbox.test.tsx` | – (Skelett-/Ladezustände sind laut Testkonzept kein E2E-Gegenstand) |
| AK14 | – | Lightbox: 0 Links. Detailseite: bestehende Tests ohne Diff | – |
| AK15 | Hook: Zustand aus dem Eintrag, `replace` beim Schließen | Seiten: `initialEntries` mit State, Liste pending → resolve | Ein Fall mit `page.reload()` |
| AK16 | – | Seiten: Invalidierung mit einer neuen Liste ohne das Foto | – |

### Neue Testdateien und Pflichtfälle

**`hooks/useCurationLightbox.test.tsx`** (`renderHook` im `MemoryRouter` mit Verlaufssonde; Startzustand `initialEntries=['/stub', '/projects/1/album?x=1']`, `initialIndex=1`)

- `openPhotoId` wird parametrisiert aus dem State gelesen: `{grossansicht:5}`→5; `'5'`, `5.5`, `NaN`, `Infinity`, `2**53`, `null`, `{}`, `{andere:1}` und ein Nicht-Objekt → `null`.
- `open(id)` behält `pathname` **und** `search`, setzt `state.grossansicht` und legt genau einen Eintrag an.
- `close()` nach eigenem `open` geht genau einen Schritt zurück.
- `close()` auf einem Eintrag, der nicht in dieser Montierung angelegt wurde (Reload-Simulation über `initialEntries` mit State), ersetzt den Eintrag: Der State ist danach `null`, der Index unverändert, und ein Zurück landet auf `/stub`.
- **Riegel:** zwei `close()` in **einem** `act()` gehen nur einen Schritt zurück. Ohne Riegel landet man auf `/stub`: per Wegwerfprobe gegen react-router 8 belegt (siehe Verifikation).
- Der Riegel wird zurückgesetzt: open → close → open → close schließt auch beim zweiten Mal.
- `close()` ohne offene Großansicht, z. B. nach Browser-Zurück von außen, navigiert nicht.
- Wechselt `openPhotoId` von einer Id auf `null`, bekommt das über `triggerRef(id)` registrierte Element den Fokus. Nach `triggerRef(id)(null)` bleibt kein totes Element in der Zuordnung.

**`components/CurationLightbox.test.tsx`** (PhotoImage-API gemockt, QueryClient für Motive)

Fokusfalle, Scroll-Sperre und die Absprache zwischen Esc und `cancel` werden **nicht** wiederholt. Sie gehören dem Grundelement bzw. `useModalDialog` und sind über `ui/dialog.test.tsx` belegt (Konsumenten-Regel des Testkonzepts). Geprüft werden die **Abweichungen und Entscheidungen** dieses Konsumenten:

- Zugänglicher Name, `alt`, Fußzeilenpfad; Erstfokus auf „Schließen“.
- Exakte Menge der Schaltflächen je Zustand (gefüllt, Fehler, 404); `queryAllByRole('link')` ist leer.
- **Aufteilung der Klickziele:** Ein Klick mit dem Ziel `<dialog>` oder dem Bühnenelement ruft `onClose` genau einmal. Klicks auf `img`/Bildkasten, Kopf-, Fußzeile, Detailbereich und den inneren Panel-Container rufen ihn nicht (`fireEvent.click` auf das jeweilige Element; ein Klick auf das Bild erreicht die Bühne per Bubbling, und genau das ist der Rot-Fall).
- Escape schließt auch bei aufgeklappten Details.
- Tab-Zyklus: Schließen → (aufgeklappt) Detailbereich → Details → Schließen.
- Details: anfangs zu, `aria-controls` zeigt auf ein vorhandenes, verborgenes Element; Inhalt nach dem Aufklappen (Raster, „Feinlabels“ als `h3`, Aufnahmeangaben mit `h3` und den Handles `taken-at-section`/`place-line`); ohne Feinlabels fehlt die Überschrift.
- Lade- und Fehlerzustände aus AK13, einschließlich Fokus auf der Bühne nach „Erneut versuchen“ und Escape im Fehlerzustand.
- Feindlicher `relative_path` in Überschrift, Fußzeile und `alt` bleibt reiner Textknoten (Muster aus `PhotoCard.test.tsx`).

**`components/MotifStrengthRow.test.tsx`**

- Acht `listitem` in Registry-Reihenfolge. Die Fixture hat eine Registry-Reihenfolge, die weder alphabetisch noch nach Wert sortiert ist.
- **Gleichheit mit `MotifStrengthSection`:** Beide werden für dasselbe Foto (mit Korrektur und „lokal nicht beurteilbar“) gerendert, und die Namensmengen müssen gleich sein. Das ist die Regel „ein Wert an zwei Stellen“ aus Spec 0490; sonst liefen beide still auseinander.
- Keine fokussierbaren Nachfahren, kein `title`.
- Ladezustand → Platzhalter, keine Liste. Fehler → Alert mit Retry, und `listMotifs` wird ein zweites Mal aufgerufen.
- `null`-Einstufung → Satz statt Liste. `excluded_document` → Liste unverändert, kein Satz.

**Erweitert: `PhotoImage.test.tsx`**

- Ohne `retryable` gibt es kein „Erneut versuchen“: Die bestehenden Fälle bleiben unverändert, dazu kommt die Negativ-Assertion.
- Mit `retryable` und 500: Alert mit Titel und `detail` → Retry → zweiter Abruf → `img`.
- Ein Fehler, der kein `ApiError` ist, zeigt den Rückfallsatz.
- Mit `retryable` und 404: sichtbarer Text und Schaltfläche, **kein** `role=alert`, und die Schaltfläche hat keinen Vorfahren mit `role=img`. Kinder von `role=img` sind präsentational, der Knopf wäre sonst für Hilfstechnik unsichtbar.

**Erweitert: Kacheltests** (`CurationPhotoTile.test.tsx`, `SelectionPhotoTile.test.tsx`)

- Name „Großansicht: {relative_path}“; Klick ruft genau `onOpenLarge(photo.id)` und keine Entscheidung auf.
- Die Entscheidungs- und Alternativenflächen rufen `onOpenLarge` nicht.
- Der Auslöser ist das erste tabbare Element der Kachel; `largeTriggerRef` erhält den Button.

**Erweitert: Seitentests** (`AlbumDraftPage.test.tsx`, `AlbumSelectionPage.test.tsx`; `MemoryRouter` mit einer Stub-Route vor der Seite als Verlaufssonde)

- Öffnen über `fireEvent.click`, **nicht** `userEvent.click`: Das bildet Safari nach, das einen angeklickten Button nicht fokussiert. Eine Rückgabe über das vorher fokussierte Element wäre damit rot.
- Für jeden der vier Schließwege (Browser-Zurück über `navigate(-1)` aus der Sonde): Dialog weg, Fokus auf dem Auslöser, Zahl der API-Aufrufe unverändert (keine Neumontierung, keine Neuladung), keine Mutation.
- Lokaler Zustand bleibt: Im Entwurf bleibt eine zugeklappte Tagesgruppe B zu, während ein Foto aus A offen war; in der Endauswahl bleibt die Ergebnissicht gewählt.
- Reload-Simulation (AK15) mit wartender Liste: Die Sonde zeigt weiter den State. Nach dem Resolve öffnet sich die Großansicht; nach dem Schließen führt Zurück auf `/stub`.
- Id nicht in der Liste: kein Dialog, der State wird geleert, keine Meldung.
- AK16: Die Query wird mit einer Liste ohne das Foto invalidiert → der Dialog ist weg, Zurück führt auf `/stub`, `h1` hat den Fokus.
- **Endauswahl-Filter:** Reload-State für ein Foto, das in `items` steht, aber nur in der Ergebnissicht sichtbar ist (die Standardsicht ist „Unterschiede“). Die Großansicht öffnet sich trotzdem, weil das Foto aus `items` kommt und nicht aus der gefilterten Sicht. Nach dem Schließen liegt der Fokus auf `h1`, die Sicht bleibt „Unterschiede“.

**Neu: `e2e/tests/kuratierung-grossansicht.spec.ts`** (lesend, Demo-Projekt „bewertet“, läuft in beiden Breiten; in `toolchain.spec.ts` unter `beidbreitig` eintragen)

1. **Ausdehnung an der `sm`-Grenze.** Bei geöffnetem Dialog `setViewportSize` 639 → Dialogrechteck = Viewport (±1); 640 → Einrückung 48 px links/rechts und 24 px oben/unten (±1). Die beiden Messungen **müssen sich unterscheiden**. Bei 640 liefert `elementFromPoint(8,8)` das `<dialog>`, der Alphawert von `getComputedStyle(dialog,'::backdrop').backgroundColor` ist > 0, und die Seitenüberschrift ist weiter `attached`.
2. **Bild füllt die Bühne.** Vorbedingung: zwei Fotos mit paarweise verschiedenem natürlichem Format, aus `naturalWidth/Height` gelesen. Je Foto liegt das Inhaltsrechteck in der Bühne, ist in einer Achse bündig (±1) und hat ein Verhältnis gleich dem natürlichen (±1 %). Nach dem Aufklappen der Details: Vorbedingung, dass der Bereich sichtbar ist und die Bühne kleiner als vorher; die Einpassung gilt weiter.
3. **Klick neben das Bild bzw. auf das Bild** (breite Ansicht, Hochformat). Vorbedingung: Die seitliche Lücke ist ≥ 20 px, und `elementFromPoint` liefert dort die Bühne. Klick in die Bildmitte → bleibt offen; Klick auf die Kopfzeile → bleibt offen; Klick in die Lücke → geschlossen; neu öffnen, Klick auf (8,8) → geschlossen.
4. **Schließwege, Platz und Fokus.** Einstieg über `/projects/{id}` → Album. Scrollen, bis der Auslöser **teilweise** unter dem Fensterrand liegt (Vorbedingungen: `scrollY > 0` und Auslöser-Unterkante > `innerHeight`), dann auf den sichtbaren Teil klicken. Für jeden der vier Wege (Schließen, Escape, Klick daneben, `page.goBack()`): scrollY gleich (±1) während offen und nach dem Schließen, URL gleich, Auslöser `toBeFocused()`. Danach genau **ein** `goBack()` → `/projects/{id}`. Das belegt, dass kein Eintrag übrig bleibt. Dieselben Zusagen gelten bei einem Öffnen über einen Klick ohne Fokus (wie Safari). Dass die Fokus-Rückgabe mit `preventScroll` fokussiert, erzwingt nicht dieser Fall, sondern der Unit-Test `useCurationLightbox.test.tsx > focuses the registered trigger without scrolling when the photo closes`: Chromium scrollt hier auch ohne `preventScroll` nicht.
5. **Zweimal Escape.** (a) Zwei synthetische `keydown`-Escape in **einem** `page.evaluate` am Dialog, also sicher vor dem asynchronen `popstate`. (b) Zweimal nativ `keyboard.press('Escape')`: Das ist der CloseWatcher-Pfad von Chromium, der ein zweites Esc nicht mehr abbrechen lässt. In beiden Fällen bleibt die Album-URL, die Überschrift ist sichtbar, und ein `goBack()` → `/projects/{id}`.
6. **Reload.** Öffnen, `page.reload()` → der Dialog mit demselben Dateinamen ist wieder offen. Escape → der Fokus liegt auf dem Auslöser. Ein zweites `reload()` → kein Dialog.

Dazu kommen die Regeln des Testkonzepts: exakte Kardinalität, eine Vorbedingung je Fall und ein Rot-Nachweis im PR. Vorschlag für den Rot-Nachweis: `width:min(…)` aus dem Bildkasten streichen (Fall 2 wird rot) und `sm:inset-x-12` entfernen (Fall 1 wird rot).

**Erweitert: `e2e/tests/tap-targets.spec.ts`** (schmal): Großansicht öffnen, dann `assertTappable` für „Schließen“ und „Details“. Ihre Aufspannung liegt 12 px neben der schließenden Bühne, ein Fehlgriff schließt dort statt aufzuklappen.

**Strukturwächter und Design-Vertrag**

- `albumSelection.structure.test.ts`: `components/CurationLightbox.tsx` kommt in `DRAFT_FILES` (nennt keines der drei Endauswahl-Felder) **und** in `SELECTION_FILES` (importiert `isInAlbum` nicht). Beide Seiten montieren die Komponente, und die Architektur sagt genau das zu.
- `designSystem.contract.test.ts`: `COLOR_OPACITY_ALLOWLIST` bekommt einen Eintrag `CurationLightbox.tsx`/`backdrop:bg-bg/72`. Die Bilddämpfungsregel greift ohne Zutun, weil die Datei `PhotoImage` nennt, und muss ohne Ausnahme grün bleiben. Braucht `container-type: size` eine willkürliche Tailwind-Klasse, ist das ein eigener, begründeter Eintrag in `ARBITRARY_VALUE_ALLOWLIST`.

### Wichtigste Edge Cases

- **Zweimal Escape oder Doppelklick vor `popstate`:** jsdom per zwei `close()` in einem `act`, E2E synthetisch und nativ. `ui/dialog.test.tsx` legt fest, dass das Grundelement `onClose` **bei jedem** Escape aufruft (Fall „two Escapes → 2“). Der Riegel muss deshalb in `useCurationLightbox` sitzen, nicht in `useModalDialog`.
- **Reload mit offenem State:** Das Schließen muss den Eintrag ersetzen statt zurückzugehen. Während die Liste lädt, darf nicht geschlossen werden: `items=[]` beim Laden ist kein „verschwunden“.
- **Foto verschwindet aus der Liste:** schließen, kein verwaister Eintrag, Fokus auf `h1`. `h1` braucht dafür `tabIndex={-1}`. Die Zuordnung muss beim Unmount des Auslösers den Eintrag löschen, sonst wird ein abgehängter Knoten fokussiert und der Fokus fällt still auf `body`.
- **404-Platzhalter vs. Fehler:** unterschiedliche Rolle (kein `alert` bei 404), beide mit Retry, der Knopf nicht unter `role=img`.
- **Klick auf das Bild vs. daneben:** In jsdom wird die Aufteilung über das Klickziel geprüft, im Browser über Geometrie mit Treffertest. Fehlt `aspect_ratio`, ist „daneben“ nur noch der Backdrop.
- **Fokus-Rückgabe bei jedem Schließweg:** einschließlich Browser-Zurück und Reload (kein vorher fokussiertes Element). Geöffnet wird über `fireEvent.click`, wie in Safari.
- **Endauswahl-Filter:** Das Foto kommt aus `items`, nicht aus `visible`. Ist sein Auslöser in der aktuellen Sicht nicht gerendert, greift der Rückfall auf `h1`.
- **Details bei jedem Öffnen zu:** Details bei Foto A öffnen, schließen, Foto B öffnen → zu (Seitentest).

### Bewusst geänderte Bestandstests

- **`components/PhotoCard.test.tsx`** (die Prop `to` entfällt):
  - Der `MemoryRouter`-Wrapper in `renderCard` fällt weg; ohne `Link` braucht es keinen Router mehr.
  - „renders as a listitem containing the tile link“ wird **gelöscht**. Der Kommentar zur e2e-Vertragsfläche ist veraltet: `photoTiles()` in `e2e/lib/demo.ts` greift auf `PhotoGridTile`, das nicht betroffen ist.
  - „renders the image area as a non-link when no target is given“ wird zu: „ohne `onImageActivate` ist die Bildfläche weder Link noch Button“.
  - „keeps the corner slots siblings of the tile link“ zielt jetzt auf den **Auslöser-Button**. Das ist jetzt schärfer: Ein Button in einem Button ist ungültiges HTML.
  - „renders footer children outside the tile link“ gilt jetzt außerhalb des Auslösers.
  - „keeps the file name outside the link and out of its accessible name“ zielt auf den Auslöser: Der Name ist exakt `imageTriggerLabel` („Großansicht: 2024/07/IMG_0042.jpg“), und der Dateiname-Span liegt außerhalb.
  - Neu: Ein Klick ruft `onImageActivate` einmal auf, `type="button"`, `imageTriggerRef` erhält den Button.
  - Unverändert: Zustandsfälle, Textknoten-Sicherheit, „selected“.
- **`photoDetail.structure.test.ts`:** Im Fall „lässt beide Aufrufstellen die Funktion importieren“ wird für `eventPlaceName` die Datei `components/PhotoCaptureFacts.tsx` gelesen statt `pages/PhotoDetailPage.tsx`. Die übrigen Fälle bleiben unverändert und werden damit zum Wächter: Die Großansicht nutzt `CriterionScoreGrid`, **nicht** `CriterionDetailsList` (die Aufrufmenge bleibt `['components/CriterionDetailsPopover.tsx']`), und `PhotoCaptureFacts` liest `landmark_name` nicht selbst.
- **`components/SelectionPhotoTile.test.tsx`:** Die Zeilen 150 und 158 (`getAllByRole('button')).toHaveLength(1)`) und die Schleife in Zeile 184 (`tap-target` und kein `h-11` an **jedem** Button) werden auf die Entscheidungsflächen eingegrenzt. Der Bild-Auslöser ist eine zusätzliche Schaltfläche und braucht keine Aufspannung. Voraussetzung: `onOpenLarge` und `largeTriggerRef` sind an beiden Kacheln **Pflicht**-Props, weil beide Produktivaufrufer sie immer übergeben. Optionale Props ließen die Kacheltests an der Wirklichkeit vorbeiprüfen.
- **`albumSelection.structure.test.ts`:** Die beiden Dateilisten werden erweitert (siehe oben).
- **`designSystem.contract.test.ts`:** ein Freigabeeintrag (siehe oben).
- **`e2e/tests/toolchain.spec.ts`:** neuer Eintrag in `beidbreitig`. **`e2e/tests/tap-targets.spec.ts`:** Ergänzung.

**Nachweis ohne Rot-Grün** (Testkonzept, bereichsübergreifend) für die verhaltensneutralen Schritte 1 und 3 der Reihenfolge:

- Das Herauslösen von `useModalDialog` hat **keinen** Diff in `ui/dialog.test.tsx`, `DeleteProjectDialog.test.tsx`, `CameraTimeOffsetDialog.test.tsx`, `DraftAlternativesDialog.test.tsx` und `ProjectSettingsPage.test.tsx`.
- Das Herauslösen von `PhotoCaptureFacts` und der Motiv-Ableitung hat keinen Diff in `PhotoDetailPage.test.tsx` und `MotifStrengthSection.test.tsx`.
- In beiden Fällen bleibt die Menge der Testknoten gleich, mit gleichem Ausgang. Einzige angekündigte Ausnahme ist der eine Pfad in `photoDetail.structure.test.ts`.

**Unberührt und bleiben grün:** `photoGridTile.structure.test.ts` (`PhotoCard` behält genau die beiden Kachel-Aufrufer), `no-horizontal-scroll`, `popover-position`, `bilddetail-buehne` und die übrigen E2E-Specs.

### Bekannte Lücken (manuell zu prüfen, im Testkonzept führen)

- Android-Zurück-Geste bzw. CloseWatcher am echten Gerät (dort schließt die Geste über `cancel` statt über den Verlauf).
- Safari: echte Fokus- und Klicksemantik.
- `dvh` gegen eine ein- und ausfahrende Browserleiste. Das ist dieselbe Lücke wie bei Spec 0497.

## Entscheidungen

- Alle vier Konsultationen gelaufen (architect, ux-ui-designer, test-engineer, security-engineer);
  keine Produktentscheidung offen.
- Keine ADR: weder neue Technologie noch Abhängigkeit noch Datenmodell-Änderung.
- Öffnungszustand im Verlaufseintrag (`location.state`) statt URL-Parameter: kein Kriterium
  verlangt eine teilbare URL, und Sicht/Filter der Seiten sind lokaler Zustand.
- Modal-Mechanik als `lib/useModalDialog.ts` aus `ui/dialog.tsx` herausgelöst statt `Dialog` um
  Varianten zu erweitern: Die Großansicht schließt per Hintergrundklick, `Dialog` bewusst nicht.
- AK15 (Neuladen bei offener Großansicht) und AK16 (Foto verschwindet) sind aus dem
  Verlaufszustand abgeleitet, kein neues Produktverhalten.
- Maße, Flächen und Abdunklung folgen dem Penpot-Entwurf (gemessen 2026-09-26). Daniels Entscheidungen
  dazu (2026-09-26): Angleichung im selben Pull Request; die Belichtungsdaten des Entwurfs
  (Verschlusszeit/Blende/ISO) entfallen, weil es sie im Datenmodell nicht gibt; die Überlagerung ab
  `sm` hat 48 px seitlich und 24 px oben/unten (`sm:inset-x-12 sm:inset-y-6`) statt der
  rasterfremden 40/20 px des Bretts.
- Ein Doppelklick auf eine Kachel öffnet mit dem ersten Klick; trifft der zweite die freie Bühne
  oder den Rand, schließt er wieder. Der Verlauf bleibt konsistent; kein eigener Schutz.
- Kein eigener E2E-Fall für die Endauswahl: dieselbe Komponente und derselbe Hook sind im Entwurf
  geometrisch geprüft.

## Offene Fragen

Keine.

## Out of Scope

- Blättern zum nächsten/vorigen Bild, Zoomen oder Verschieben im Bild.
- Jede Bewertungs- oder Auswahlhandlung in der Großansicht.
- Eine teilbare URL für ein geöffnetes Bild.
- Änderungen an der Bilddetailseite und an ihrer Erreichbarkeit.
- Großansicht außerhalb der beiden Kuratierungsschritte.
