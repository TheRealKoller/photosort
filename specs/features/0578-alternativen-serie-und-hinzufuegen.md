# 0578 - Alternativen als Aufnahmeserie, aufklappbar, mit Tauschen und Hinzufügen

**Status:** Implemented ([PR #580](https://github.com/TheRealKoller/photosort/pull/580))
**Erstellt:** 2026-10-05
**Bezug:** Issue [#578](https://github.com/TheRealKoller/photosort/issues/578) (enthält die zusammengeführte Story #577), ADR [`0133`](../decisions/0133-band-zeigt-aufnahmeserie.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil zwei zusammengeführte Stories mit Backend-Fensterregel, ersetztem Dialog und neuen Handgriffen samt Sicherheitsauflagen in einer Spec stehen.

## Ziel

Im Album-Entwurf tauscht man ein Foto meist gegen eine andere Aufnahme desselben Augenblicks. Heute zeigt das Band unter dem Foto immer genau die vier zeitlich nächsten Aufnahmen. Bei Serien — vielen Bildern in kurzer Zeit — ist das zu wenig: Der Rest der Serie ist nicht zu sehen. Der Weg zu allen Fotos des Events ist leicht zu übersehen, öffnet eine eigene Ansicht, zeigt die Fotos dort klein und ohne sichtbare Tausch-Schaltfläche. Außerdem kann man in den Alternativen nur tauschen: Wer dabei ein oder zwei Fotos entdeckt, die zusätzlich ins Album sollen, muss die Alternativen verlassen, „Foto hinzufügen" des Events öffnen und das Foto dort erneut suchen.

Ziel: Das Band zeigt die Serie, zu der das Foto gehört. Wer mehr sehen will, klappt an derselben Stelle alle Fotos des Events auf — in gleicher Größe und mit sichtbaren Schaltflächen, ohne die Ansicht zu verlassen. Jede Alternative lässt sich dort tauschen oder zusätzlich hinzufügen; nach einem Hinzufügen bleibt man in den Alternativen. Die Schaltfläche „Foto hinzufügen" je Event bekommt ein Plus-Zeichen, damit sie auf einen Blick als Hinzufügen erkennbar ist. Betrifft beide Nutzer gleichermaßen, jeweils im eigenen Entwurf.

Nicht Teil dieser Story: welche Fotos überhaupt Alternativen sein können (im Ausschuss aussortierte Duplikate bleiben weiterhin draußen), das Hinzufügen-Panel selbst (außer seiner Schaltfläche), die Endauswahl, die Großansicht.

## User Story

Als Nutzer, der im Album-Entwurf ein Foto gegen eine bessere Aufnahme tauschen will, möchte ich unter dem Foto die ganze Aufnahmeserie sehen, zu der es gehört, bei Bedarf alle Fotos des Events an derselben Stelle groß aufklappen und jede Alternative dort tauschen oder zusätzlich hinzufügen können, damit ich die beste Aufnahme eines Augenblicks finde und passende weitere Fotos gleich mitnehme, ohne die Ansicht zu verlassen oder versteckte Schaltflächen suchen zu müssen.

## Akzeptanzkriterien

**Serie im Band**

- [ ] Das Band unter einem Foto zeigt dessen Serie: die Alternativen desselben Events, die mit dem Foto eine lückenlose Folge bilden. Zwei zeitlich aufeinanderfolgende Aufnahmen (Ordnung nach Aufnahmezeit, bei Gleichstand nach Foto-Id) gehören zur selben Serie, solange zwischen ihnen höchstens 2 Minuten liegen; ein Abstand von genau 2 Minuten (120 s) gehört noch zur Serie, 120 s plus 1 s nicht mehr. Die Schwelle ist fest und nicht vom Nutzer einstellbar.
- [ ] Die Serie endet vor und nach dem Foto unabhängig voneinander jeweils an der ersten Pause von mehr als 2 Minuten; spätere dichte Aufnahmen jenseits der Pause gehören nicht dazu. Fotos, die bereits im Entwurf stehen, überbrücken keine Pause (die Serie besteht nur aus Alternativen).
- [ ] Hat die Serie weniger als 4 Alternativen, füllt das Band mit den zeitlich nächsten Fotos des Events auf genau 4 auf; hat das Event weniger als 4 Alternativen, zeigt das Band alle. Bei gleich großem Zeitabstand zweier Kandidaten zum Foto wird der frühere zuerst genommen. Das Band zeigt immer einen lückenlosen Ausschnitt der zeitlichen Reihe.
- [ ] Hat die Serie 4 bis 12 Alternativen, zeigt das Band genau die Serie — nicht mehr und nicht weniger — und keinen Hinweis auf weitere Aufnahmen.
- [ ] Hat die Serie mehr als 12 Alternativen, zeigt das Band genau 12: die zeitlich nächsten um das Foto, alle innerhalb der Serie (Gleichstand: der frühere gewinnt). Darunter nennt ein Hinweis die Zahl der übrigen Serienaufnahmen (Seriengröße − 12): „1 weitere Aufnahme dieser Serie unter „Alle Fotos des Events“.“ bzw. „{n} weitere Aufnahmen dieser Serie unter „Alle Fotos des Events“.“ Ohne Rest (≤ 12) gibt es keinen Hinweis.
- [ ] Das Band ordnet weiterhin zeitlich von früh nach spät und markiert die Stelle des Fotos mit genau einer Marke „Wird ersetzt“, wie bisher.
- [ ] Welche Fotos als Alternative in Frage kommen, bleibt unverändert (gestrichene sichtbar als „Gestrichen“, aussortierte nie); gestrichene zählen wie jede andere Alternative zu Serie und Lücke.
- [ ] Ein Foto ohne Alternativen im Event zeigt wie bisher den Leertext „Keine weiteren Fotos in diesem Event.“ und keinen Umschalter.

**Alle Fotos des Events an Ort und Stelle**

- [ ] Im geöffneten Band steht über den Fotos eine umrandete Schaltfläche „Alle Fotos des Events“ (nicht als Textlink), die ihren Zustand per `aria-expanded` meldet; aufgeklappt heißt sie „Weniger anzeigen“. Während die Serie erstmals lädt und bei leerer Serie fehlt sie.
- [ ] Ein Druck darauf öffnet keine eigene Ansicht und keinen Dialog (kein `role="dialog"` im Dokument): Das Band wächst an derselben Stelle zur vollständigen zeitlichen Reihe aller Alternativen des Events, mit genau einer Marke „Wird ersetzt“ an der Stelle des Fotos. Die Scrollposition der Seite bleibt unverändert, der Fokus bleibt auf der Schaltfläche.
- [ ] Hat das Event mehr Alternativen als eine Seite (60), lädt „Weitere Fotos“ die nächste Seite nach. Liegt die Stelle des Fotos auf einer noch nicht geladenen Seite, steht unter der Reihe „Das zu ersetzende Bild folgt weiter hinten in der Reihe.“, und die Marke erscheint erst, wenn ihre Seite geladen ist — nie doppelt.
- [ ] Lange Reihen brechen im Raster um und werden mit der Seite senkrecht gescrollt; die Seite scrollt bei 360 px nicht waagerecht.
- [ ] Die Fotos in der aufgeklappten Reihe haben dieselbe Kachel- und Bildgröße wie im Band und sind vollständig zu sehen (nicht beschnitten).
- [ ] „Weniger anzeigen“ führt zur Serie zurück, ohne die Serie neu zu laden; erneutes Aufklappen lädt die Reihe nicht neu. Schließen (Schaltfläche oder Esc, auch im aufgeklappten Zustand) schließt Band und Reihe gemeinsam, der Fokus geht an „Alternativen“ des Fotos zurück.
- [ ] Auf der Seite ist weiterhin höchstens ein Band offen, aufgeklappt oder nicht; das Öffnen eines anderen Bands schließt das vorige samt Reihe, und ein neu geöffnetes Band startet zugeklappt.
- [ ] Die bisherige separate Ansicht „Alle Alternativen“ samt Schaltfläche gibt es nicht mehr.

**Tauschen und Hinzufügen an jeder Alternative**

- [ ] Jede Alternative in Band und aufgeklappter Reihe trägt zwei sichtbare, beschriftete Schaltflächen untereinander, erst „Tauschen“, dann „Hinzufügen“; ihre zugänglichen Namen sind „Tauschen: {Dateipfad}“ und „Hinzufügen: {Dateipfad}“. Die Markierung „Wird ersetzt“ bietet keine von beiden. Im Hinzufügen-Panel bleibt nur „Hinzufügen“.
- [ ] Ein Tausch aus der aufgeklappten Reihe wirkt genau wie aus dem Band: Band und Reihe schließen, Hinweis „Getauscht“ mit „Rückgängig“, kein Neuladen der Seite.
- [ ] Nach „Hinzufügen“ steht das Foto im Entwurf an seiner zeitlichen Stelle im Event und hat den Zustand „Aufgenommen“ — auch wenn es vorher gestrichen war. Die Zahl der Fotos im Entwurf (Gruppenkopf und Kopfleiste) steigt um genau eins; kein anderes Foto ändert Zustand oder Stelle, insbesondere bleibt das Foto, zu dem die Alternativen geöffnet wurden, unverändert im Entwurf.
- [ ] Nach „Hinzufügen“ bleiben Band bzw. aufgeklappte Reihe offen; das hinzugefügte Foto steht nicht mehr unter den Alternativen, kein anderes Foto rückt nach (die Zahl der gezeigten Alternativen sinkt um genau eins, der Serienrest-Hinweis bleibt unverändert), und es wird nichts nachgeladen. Der Fokus geht auf „Hinzufügen“ der nachfolgenden Alternative, sonst der vorigen, sonst auf die Band-Überschrift. Ohne erneutes Öffnen kann man ein weiteres Foto hinzufügen oder tauschen.
- [ ] Ein „Tauschen“ nach einem oder mehreren Hinzufügungen ersetzt das Foto, zu dem die Alternativen geöffnet wurden; die hinzugefügten Fotos bleiben im Entwurf, und „Rückgängig“ nimmt nur den Tausch zurück (die Hinzufügungen bleiben).
- [ ] Das Hinzufügen aus den Alternativen verhält sich wie das Hinzufügen über „Foto hinzufügen“: ohne Rückfrage, ohne Rückgängig-Hinweis, auch über den Richtwert hinaus ohne Warnung; ein offener Hinweis eines vorherigen Handgriffs (z. B. „Getauscht“) verschwindet.
- [ ] Scheitert Tauschen oder Hinzufügen, ändert sich nichts am Entwurf; Band bzw. Reihe bleiben offen, die Alternative bleibt in der Liste und wieder bedienbar, und im Band unter der Überschrift erscheint eine Meldung (`role="alert"`) mit dem Grund vom Server; der Fokus bleibt auf dem ausgelösten Handgriff.
- [ ] Während ein Hinzufügen oder ein Tausch läuft, sind beide Schaltflächen derselben Alternative gesperrt und nehmen keinen zweiten Druck an (genau ein Schreibaufruf); andere Alternativen bleiben bedienbar.

**Erkennbare Schaltfläche „Foto hinzufügen“**

- [ ] Die Schaltfläche „Foto hinzufügen“ am Ende jedes Events trägt vor dem Wort ein Plus-Zeichen „+“.
- [ ] Ihr zugänglicher Name bleibt exakt „Foto hinzufügen: {Eventname}“; das Zeichen ist für Hilfstechnik verborgen und wird nicht vorgelesen.
- [ ] Das Zeichen gibt es nur an dieser Schaltfläche, nicht an den einzelnen „Hinzufügen“-Handgriffen in Band, Reihe und Hinzufügen-Panel.

**Telefonbreite**

- [ ] Bei 360 px Breite sind in Serie und aufgeklappter Reihe „Tauschen“ und „Hinzufügen“ jeder Alternative mindestens 44 px hoch und mit 12 px Abstand untereinander, Umschalter, „Weitere Fotos“ und „Schließen“ einzeln per Touch treffbar (Treffertest an allen vier Ecken liefert das Element selbst), nichts überlappt, und die Seite scrollt nicht waagerecht.

## Datenmodell-Bezug

Keine Änderung am Datenmodell und keine Migration. Die Antwort von `GET /projects/{id}/draft-alternatives` bekommt das Feld `series_rest`; Grundlage der Serie ist das bestehende `Photo.taken_at`.

## Architektur / Umsetzung

**Neue ADR:** [`0133`](../decisions/0133-band-zeigt-aufnahmeserie.md). Sie löst Punkt 3 von ADR 0132 ab (Bandfenster `nearest`). ADR 0132 Punkte 1, 2 und 4 sowie ADR 0098 Punkt 5 (Menge, Lauf-/Eventbindung) gelten unverändert.

### 1. Serie im Band – Backend

- **`selection.py`:** neue Konstanten `SERIES_GAP = timedelta(minutes=2)`, `BAND_MIN = 4` und `BAND_MAX_SERIES = 12`. Dazu kommt eine reine Funktion `series_window(times, reference_taken_at, reference_index) -> SeriesWindow(offset, size, rest)` über die nach `(taken_at, photo_id)` geordneten Zeiten der Kandidaten.
  - **Serie** = zusammenhängender Abschnitt `[a, b)`. Er wächst vom Bezugsbild aus nach beiden Seiten, solange der Abstand zum jeweils vorigen Nachbarn höchstens `SERIES_GAP` ist. Der erste Nachbar ist das Bezugsbild selbst. Die erste Lücke `> SERIES_GAP` beendet die Seite.
  - **Fenster** = immer zusammenhängend. Es wächst vom Bezugsbild aus um den zeitlich näheren Nachbarn; bei Gleichstand gewinnt der frühere. Grenzen:
    - Serie mit 4–12 Bildern: genau die Serie.
    - Längere Serie: 12 Bilder innerhalb der Serie, `rest = (b − a) − 12`.
    - Kürzere Serie: über die Serie hinaus im ganzen Event, bis 4 Bilder erreicht sind oder das Event erschöpft ist.
  - `nearest_window_offset` entfällt samt seinen Tests.
- **`order_alternatives_chronologically`** liefert zusätzlich die geordneten `taken_at`, also aus derselben Sortierung, ohne zweite Abfrage.
- **`api/photos.py::draft_alternatives`:**
  - `nearest` wird durch `series: bool = Query(False)` ersetzt. `series` gilt nur zusammen mit `photo_id`; ohne `photo_id` antwortet der Endpunkt laut mit `422`, wie bisher bei `nearest`.
  - `nearest` bleibt als Riegel stehen (`nearest: None = Query(None, include_in_schema=False)`, jede Belegung `422`), damit ein noch nicht aktualisierter Client nicht still die erste Seite der vollen Reihe als Band bekommt — Muster des `draft`-Riegels (Security, Auflage 2).
  - Mit `series` kommen `offset` und `limit` allein aus `series_window`; ein mitgeschicktes `offset`/`limit` ist wirkungslos.
  - `BAND_MAX` (50) entfällt; den Hydratationsdeckel trägt `BAND_MAX_SERIES`.
  - `DraftAlternativesOut` bekommt das Pflichtfeld `series_rest: int`. Ohne `series` und im Leerkörper `_no_alternatives` ist es `0`, der Leerkörper bleibt byte-gleich für alle Fehlerursachen.
  - Unverändert bleiben `total`, `offset`, `reference_index` (Marke bei `reference_index − offset`), S1–S4 und S8.
- Fotos des Entwurfs überbrücken keine Lücke: Die Serie besteht aus Alternativen.

### 2. Frontend – Abfrage und Band

- **API-Schicht** (`api/photos.ts`, `api/types.ts`, `hooks/usePhotos.ts`):
  - `nearest` wird durch `series: true` ersetzt, ebenso im Abfrageschlüssel.
  - `DraftAlternativesOut.series_rest` kommt hinzu.
  - Das Band holt weiterhin genau ein Fenster ohne Folgeseiten.
- **`DraftAlternativesBand.tsx`:**
  - `BAND_SIZE` geht auf, und die Prop `limit` an `CandidatePanel` entfällt, denn der Server schneidet.
  - Für die vier Lade-Platzhalter bleibt die reine Darstellungskonstante `BAND_SKELETON_COUNT = 4`.
  - Bei `series_rest > 0` steht der Hinweis auf weitere Serienaufnahmen unter dem Ordnungstext. Seine Zahl kommt allein aus `series_rest`; den Wortlaut legt UX fest.

### 3. „Alle Fotos des Events“ an Ort und Stelle – ersetzt den Dialog

- **`DraftAlternativesBand`** bekommt den lokalen Zustand `expanded`. Ein Umschalter (`outline sm`, `aria-expanded`, Wortlaut von UX) wechselt zwischen Serie und voller Reihe in **demselben** `CandidatePanel`-`<li>`.
  - Zwei Abfragen: Serie mit `series: true`, volle Reihe mit `photoId` und Seitenabruf `PHOTOS_PAGE_SIZE = 60`.
  - Die volle Reihe lädt erst bei `expanded` (`enabled`). Danach bleibt ihr Cache, das Zurückschalten lädt nichts neu.
  - Nachgeladen wird über die bestehende Schaltfläche `moreLabel`.
  - Eine Abfrage mit `limit=200` in einem Zug scheidet aus: Ein Event kann mehr Fotos haben, und der Deckel ist zugleich eine Sicherheitsgrenze.
- **`CandidatePanel`** übernimmt die Markenlogik des Dialogs über mehrere Seiten:
  - Die Marke steht genau einmal an `reference_index − pages[0].offset` der zusammengelegten Seiten.
  - Liegt sie am Ende der geladenen Reihe, erscheint sie nur ohne Folgeseite. Sonst steht der Hinweis `REFERENCE_LATER_TEXT`, der aus dem Dialog hierher wandert.
  - Die Bildfläche ist dieselbe wie im Band, mit `PHOTO_CARD_GRID_CLASS` und `object-contain`. Die Reihe bricht im Raster um und wird mit der Seite senkrecht gescrollt. Es gibt keinen eigenen waagerechten Scrollcontainer und damit kein waagerechtes Scrollen der Seite.
- **Fokus und Scroll:**
  - Der Umschalter behält beim Auf- und Zuklappen den Fokus.
  - Es gibt kein programmatisches Scrollen. Das Fokussieren der Überschrift beim ersten Öffnen bleibt bei `preventScroll`; die Scrollposition der Seite bleibt erhalten.
  - Esc und „Schließen“ laufen wie heute über `onKeyDown`/`onClose` des Panels: Sie schließen Band und Reihe gemeinsam, der Fokus geht an „Alternativen“ des Fotos zurück.
  - Eine Fokusfalle entfällt bewusst: Die Reihe ist Teil der Seite und kein Modal. Damit fallen auch die Zusagen von `ui/dialog`/`useModalDialog` an dieser Stelle weg.
- **Höchstens ein Band:** bleibt über das bestehende `openPanel` der Seite gewahrt; `expanded` lebt im Band und verschwindet mit ihm.
- **Entfernt:**
  - `components/DraftAlternativesDialog.tsx` samt Test.
  - In `AlbumDraftPage.tsx`: `allAlternativesPhotoId`/`setAllAlternativesPhotoId`, die Prop `onOpenAll`, die Fehlerstelle `'dialog'` und der Import.
  - Die Dialog-Einträge in `designSystem.contract.test.ts` und der Dialog-Abschnitt in `e2e/tests/no-horizontal-scroll.spec.ts`. Letzterer wird durch die aufgeklappte Reihe ersetzt.

### 4. Tauschen und Hinzufügen an jeder Alternative

- **`CandidatePanel`:** Die Einzelaktion `actionLabel`/`actionKey`/`onAction` wird zu `actions: readonly CandidateAction[]` mit `{ label: 'Tauschen' | 'Hinzufügen', key: 'exchange' | 'add', onAction(photo, neighborId) }`.
  - Band und Reihe: `[Tauschen, Hinzufügen]`; `DraftAddPanel`: `[Hinzufügen]`.
  - Namen `"{label}: {relative_path}"`, Fokusschlüssel `"{key}-{id}"`.
  - Beide Knöpfe stehen untereinander (erst „Tauschen", dann „Hinzufügen"), volle Kachelbreite, `h-11 sm:h-8`, 12px Abstand — Lage und Begründung siehe `## UI/UX`.
  - `busy` gilt je Kandidat für beide Knöpfe (bestehendes `lock`).
- **`AlbumDraftPage.tsx::handleAdd`** wird verallgemeinert zu `handleAdd(candidate, neighborId, where, fallbackFocusKey)`.
  - Das Panel übergibt `panel-{eventId}` / `panel-heading-{eventId}`, das Band `band` / `band-heading`.
  - `endUndo()`, `decisionMutation` mit `album_worthy` und `insert` bleiben, ebenso kein Rückgängig. Das Foto landet damit an seiner zeitlichen Stelle als „Aufgenommen“.
  - `handleAdd` schließt nichts: Das Band bleibt offen.
- **`handleExchange`** bleibt unverändert und wird aus Serie und Reihe mit `(bandPhoto, chosen, 'band')` aufgerufen.
  - `setOpenPanel(null)` schließt Band und Reihe.
  - Ersetzt wird immer `bandPhoto`, auch nach vorherigen Hinzufügungen. Rückgängig gilt nur dem Tausch.
- **Kein Nachrücken:** Das hinzugefügte Foto verlässt die Liste sofort über das bestehende `excludedIds` (Entwurfsmenge).
  - `usePhotos.ts::invalidateAllButTheDraft` markiert das Segment `'alternatives'` nur noch als veraltet (`refetchType: 'none'`), statt es aktiv nachzuladen.
  - Grund: Sonst holte das offene Band nach dem Hinzufügen ein neu geschnittenes Fenster mit nachgerücktem Foto, und `series_rest` stimmte nicht mehr.
  - Beim nächsten Öffnen lädt die veraltete Abfrage frisch. Das gilt gleichermaßen für das Hinzufügen-Panel, das dadurch ebenfalls nicht mehr nachrückt.

### 5. Plus an „Foto hinzufügen“

- Textzeichen statt eines neuen Lucide-Symbols: `<span aria-hidden="true">+</span>` vor dem Wort in `DraftEventSection.tsx`.
  - Der zugängliche Name bleibt über das vorhandene `aria-label` „Foto hinzufügen: {Eventname}“.
- Begründung:
  - Der Symbolsatz ist geschlossen. Ein neues Symbol zieht vier Stellen nach (`ui/icon.tsx`, `penpot/icons.test.ts`, `design/penpot/verify.js`, `penpot/payload.test.ts`).
  - Das Zeichen trägt allein die Wiedererkennung, wie die bereits dokumentierten Lücken `×`/`–`.
- Das Zeichen wird in `specs/architecture/0004-design-system.md` als sechste dokumentierte Lücke eingetragen, nur an dieser Schaltfläche.

### 6. Doku und abgelöste Aussagen

- **`docs/architecture.md`** im Abschnitt Album-Entwurf/Alternativen:
  - `nearest=BAND_SIZE` wird ersetzt durch `series` / `series_rest` / Serienregel.
  - Die Dialog-Sätze werden ersetzt durch „aufgeklappte Reihe im Band“: Zeilen ~665–671, ~682–687 (Austausch nur noch am Ort), ~764 und ~774.
- **`specs/architecture/0004-design-system.md`:** die Symbollücke `+`. Das Muster „Band mit aufklappbarer voller Reihe“ ersetzt den Dialog-Bezug.
- **Abgelöste Aussagen** (mit Verweis auf 0578 als ~~durchgestrichen~~ markieren, nicht löschen):
  - **Spec 0569:** AK1 (Dialogteil), AK3, AK4 (Dialogteil), AK5, AK10 („Band und Dialog“), AK12 (`nearest`), „Auswahlregel des Bands“ sowie die Dialog-Absätze der UI/UX-Sektion (Ort, Seitenabruf, Hinweis, Nachladen).
  - **Spec 0558:** „Das Band zeigt höchstens vier Alternativen“ (Z. 118), „Alle Alternativen öffnet den Dialog“ (Z. 131), „Tauschen: {Pfad} … im Dialog“ (Z. 88/744), „Hinzufügen: {Pfad} im Hinzufügen-Panel“ (Z. 89, jetzt auch Band/Reihe), die Handgriffliste bei 360px (Z. 155, ohne „Alle Alternativen“), Z. 244/270/373/376/475 und der Schlüsselsatz Z. 730.
- `docs/setup.md` und `README.md` bleiben unberührt.

### Reihenfolge

1. `selection.py::series_window` mit Konstanten, als reine Tests.
2. Endpunkt `series`/`series_rest`, `nearest` als Riegel; Backend-Tests umstellen.
3. API-Typen, Hook und Schlüssel.
4. `CandidatePanel`: `actions`, Marke über Seiten.
5. Band: Serie, Hinweis, aufgeklappte Reihe.
6. Seite: `handleAdd` verallgemeinern, Dialog entfernen; Invalidierung `refetchType: 'none'` für `'alternatives'`.
7. Plus-Zeichen.
8. E2E (360px, Reihe) und Doku.

## UI/UX

Sichtbare Oberfläche: ja — Alternativen-Band im Album-Entwurf (`DraftAlternativesBand.tsx`, `CandidatePanel`) und die Schaltfläche „Foto hinzufügen“ (`DraftEventSection.tsx`). Es gibt keinen `## Design`-Abschnitt und keinen Penpot-Entwurf. Maßgeblich sind dieser Abschnitt und `specs/architecture/0004-design-system.md`. Es kommt keine neue Abhängigkeit hinzu, kein neues Symbol und keine neue Bewegung.

### Aufbau des Bands (Serie und aufgeklappte Reihe)

Gleiche Fläche wie bisher (Muster „Band am gewählten Element“: `col-span-full rounded-lg border border-border bg-surface p-3`, `gap-3`). Von oben nach unten, zugleich DOM- und Fokusreihenfolge:

1. **Überschrift** `h4` „Alternativen zu {Dateiname}“ (unverändert, `tabIndex={-1}`, Fokusziel beim Öffnen mit `preventScroll`).
2. **Ordnungstext** „Zeitlich geordnet, von früh nach spät“ (unverändert, `text-xs text-text`, nur wenn Kandidaten da sind).
3. **Serienrest-Hinweis** (nur Serie, nur bei `series_rest > 0`), `text-xs text-text`, keine Live-Region, Zahl allein aus `series_rest`:
   - `series_rest === 1`: „1 weitere Aufnahme dieser Serie unter „Alle Fotos des Events“.“
   - sonst: „{n} weitere Aufnahmen dieser Serie unter „Alle Fotos des Events“.“
   - Der Hinweis nennt den Weg zum Rest wortgleich mit dem Umschalter und steht nicht in der aufgeklappten Reihe, denn dort ist der Rest sichtbar. Nach einem Hinzufügen bleibt die Zahl stehen; sie wird beim nächsten Öffnen frisch geladen (ADR 0133, kein Nachrücken).
4. **Umschalter** – eine eigene Zeile direkt **über** dem Raster, nicht in der Fußzeile. `Button variant="outline" size="sm"` mit `aria-expanded`, `aria-controls` = Id des Rasters. Beschriftung (Muster der Gestrichen-Zeile: Beschriftung nennt die Handlung):
   - zugeklappt: „Alle Fotos des Events“
   - aufgeklappt: „Weniger anzeigen“
   - Begründung für die Lage: Das Raster wächst **unter** dem Umschalter. Er bleibt beim Auf- und Zuklappen ohne programmatisches Scrollen an seiner Stelle im Blick, und der Fokus bleibt darauf (ADR 0133). In der Fußzeile würde er beim Aufklappen aus dem Bild geschoben.
   - `outline` statt `ghost`: AK „deutlich sichtbar, kein unauffälliger Textlink“. Der sichtbare Umriss `--border-control` unterscheidet ihn von „Schließen“ (ghost).
   - „Weniger anzeigen“ statt „Nur die Serie“: Das Band füllt eine kurze Serie mit den zeitlich nächsten Fotos auf 4 auf und zeigt dann mehr als die Serie.
   - Der Umschalter fehlt, wenn die Serie geladen und leer ist (dann gibt es im Event auch keine Reihe) sowie während des ersten Ladens der Serie. Bei einem Ladefehler der Serie bleibt er stehen.
5. **Raster** `<ol aria-label="Alternativen, zeitlich geordnet">` mit `PHOTO_CARD_GRID_CLASS` (2 Spalten am Telefon, 3 ab `sm`, 4 ab `lg`). Bildfläche wie bisher `aspect-square` mit `object-contain`. Die Bezugsmarke „Wird ersetzt“ steht an ihrer Stelle, ohne Handgriffe. In der aufgeklappten Reihe gilt dieselbe Kachel: gleiche Größe, Umbruch im Raster, senkrechtes Scrollen mit der Seite, kein eigener Scrollcontainer und kein waagerechtes Scrollen. Liegt die Stelle der Marke auf einer noch nicht geladenen Seite, steht unter dem Raster „Das zu ersetzende Bild folgt weiter hinten in der Reihe.“ (`REFERENCE_LATER_TEXT`, `text-xs text-text`, nicht live).
6. **Fußzeile** `flex flex-wrap gap-3` (bisher `gap-2`, das ist zwischen aufgespannten Trefferflächen unter der 12px-Regel). Darin:
   - nur in der aufgeklappten Reihe, wenn es eine Folgeseite gibt: `ghost sm` „Weitere Fotos“ (gleiches Wort wie im Hinzufügen-Panel), `busy` beim Nachladen;
   - immer `ghost sm` „Schließen“.
   - Die Schaltfläche „Alle Alternativen“ entfällt.

### Handgriffe je Alternative

- Je Kachel unter Dateiname, Qualitätsmesser und ggf. dem Kennzeichen „Gestrichen“ stehen **zwei Schaltflächen untereinander**, in dieser Reihenfolge: „Tauschen“, dann „Hinzufügen“.
  - Beide `Button variant="outline" size="sm"`, `className="h-11 sm:h-8"`, volle Kachelbreite, Container `flex flex-col gap-3`.
  - Zugängliche Namen: „Tauschen: {relative_path}“ und „Hinzufügen: {relative_path}“, die sichtbare Beschriftung ist das erste Wort davon. Fokusschlüssel `exchange-{id}` / `add-{id}`.
- **Begründung „untereinander“ statt nebeneinander:**
  - Bei 360px und zwei Spalten bleibt einer Kachel rund 146px (360 − 2×16 Seitenrand − 2×12 Bandpolster − 12 Spaltenabstand).
  - Nebeneinander bräuchten beide Schaltflächen mit Polster und 12px Abstand rund 190px. Ab `sm` wäre es bei 3 Spalten ebenfalls knapp.
  - Ein Umbruch je nach Breite ließe die Lage der Handgriffe von Kachel zu Kachel und Breite zu Breite springen.
  - Untereinander ist das bestehende Muster der Entscheidungsfläche (`CurationPhotoTile`/`SelectionPhotoTile`). Das ist eine visuell-technische Entscheidung und verfeinert ADR 0133 §4 („nebeneinander, bei Bedarf umbrechend“); der Abstand von 12px bleibt.
- **Gleichrangig, beide `outline`:** Keine der beiden Handlungen ist die Hauptaktion des Bands. Eine primäre Füllung an „Tauschen“ in jeder Kachel ergäbe eine Fläche voller Akzentknöpfe.
- **Telefon:** Beide Schaltflächen sind sichtbar 44px hoch (Kategorie „heißer Pfad“: ein Fehlgriff tauscht oder fügt ein falsches Foto ein), Abstand 12px. Ab `sm` 32px plus Aufspannung `tap-target`, Abstand 12px. Damit sind beide bei 360px einzeln treffbar, ohne Überlappung.
- **Gestrichene Alternative:** Kennzeichen „Gestrichen“ wie bisher, beide Handgriffe vorhanden. „Hinzufügen“ nimmt sie als „Aufgenommen“ auf.
- **Hinzufügen-Panel:** nur „Hinzufügen“, unverändert in Aussehen und Lage.

### Plus an „Foto hinzufügen“

- In `DraftEventSection.tsx` steht vor dem Wort ein Textzeichen: `<span aria-hidden="true">+</span>`.
  - Der Knopf bekommt `gap-2`, das Zeichen `text-lg leading-none` (Stufe der Schriftskala, kein willkürlicher Wert), Farbe wie die Beschriftung (`text-text-h`).
  - Der zugängliche Name bleibt das vorhandene `aria-label` „Foto hinzufügen: {Eventname}“. `aria-hidden` stellt zusätzlich sicher, dass das Zeichen nie vorgelesen wird, auch wenn das `aria-label` einmal entfällt.
- **Textzeichen statt neuem Lucide-Symbol `plus`:**
  - Der Symbolsatz ist geschlossen („wird nicht stillschweigend erweitert“). Eine Erweiterung gehört in eine eigene Story und zöge vier Stellen nach.
  - Das Zeichen begleitet hier ein ausgeschriebenes Label, genau wie die dokumentierten Lücken `×` und `–`.
  - Wo es neben dem Wort steht, ist `+` in der Systemschrift eindeutig.
- Das Zeichen gibt es nur an dieser Schaltfläche, nicht an den „Hinzufügen“-Handgriffen in Band, Reihe und Hinzufügen-Panel.

### Fokus

- **Öffnen des Bands:** Fokus auf die Überschrift, ohne Scrollen (unverändert).
- **Auf- und Zuklappen:** Der Fokus bleibt auf dem Umschalter, kein programmatisches Scrollen, die Scrollposition der Seite bleibt.
- **Nach „Hinzufügen“** (das Foto verlässt die Liste):
  - Der Fokus geht auf „Hinzufügen“ der nachfolgenden Alternative, sonst der vorigen (`add-{neighborId}`).
  - Gibt es keine mehr, geht er auf die Band-Überschrift (`band-heading`).
  - Das ist dasselbe Muster wie im Hinzufügen-Panel und bei „Fokus nach dem Ausblenden“: dieselbe Handlung am Nachbarn, nie `body`, kein Scrollsprung.
  - Die Marke „Wird ersetzt“ ist nie Fokusziel.
- **Nach „Tauschen“:** unverändert wie bisher aus dem Band. Band und Reihe schließen, der Fokus folgt dem bestehenden Tausch-Ablauf, der Hinweis „Getauscht“ erscheint mit „Rückgängig“.
- **Esc im Band (auch in der aufgeklappten Reihe) und „Schließen“:** Band und Reihe schließen gemeinsam, der Fokus geht an „Alternativen“ des Fotos (`alternatives-{photoId}`).
- **Keine Fokusfalle:** Die Reihe ist Teil der Seite, kein Modal. Tab verlässt das Band regulär.

### Zustände

- **Serie lädt:** vier Platzhalterkacheln `Skeleton aspect-square rounded-md` in `<ul role="status" aria-label="Fotos werden geladen…">` (`BAND_SKELETON_COUNT = 4`). Kein Ordnungstext, kein Umschalter.
- **Reihe lädt (erstes Aufklappen):** dieselben vier Platzhalter an Stelle des Rasters. Der Umschalter bleibt fokussiert und bedienbar; Zuklappen zeigt sofort wieder die Serie aus dem Cache. Späteres Aufklappen lädt nicht neu, also keine Platzhalter.
- **Nachladen der Reihe:** „Weitere Fotos“ ist `busy`, das Raster bleibt stehen.
- **Ladefehler (Serie oder Reihe):** `Alert` mit Server-`detail` (sonst „Fehler beim Laden der Fotos.“) und „Erneut versuchen“, im Band unter Ordnungstext und Umschalter. Bei einem Fehler der Reihe bleibt der Umschalter bedienbar, „Weniger anzeigen“ führt zur geladenen Serie zurück.
- **Leer:** „Keine weiteren Fotos in diesem Event.“ (`text-sm text-text`, kein Alert), ohne Umschalter. Die Marke ist dann ebenfalls nicht zu sehen; das ist bisheriges Verhalten.
- **Alle Alternativen hinzugefügt** (Liste nach Hinzufügungen leer): derselbe Leertext. Umschalter und „Schließen“ bleiben.
- **Handlung läuft:** Beide Schaltflächen der betroffenen Alternative sind `busy` (deaktiviert mit Spinner, bestehendes `lock`) und nehmen keinen zweiten Druck an. Andere Alternativen bleiben bedienbar.
- **Handlung scheitert:**
  - Der Entwurf bleibt unverändert, Band bzw. Reihe bleiben offen, die Alternative bleibt in der Liste und wieder bedienbar.
  - Die Meldung erscheint als `Alert` (`role="alert"`, Server-`detail` als Textknoten) im Band unter der Überschrift (Fehlerstelle `band`).
  - Der Fokus bleibt auf dem ausgelösten Handgriff.
- **„Hinzufügen“ ohne Rückmeldungs-Hinweis:** Keine Rückfrage, kein Rückgängig-Hinweis. Ein offener Hinweis eines vorherigen Handgriffs endet. Die Rückmeldung tragen das Verschwinden aus der Liste, der weitergewanderte Fokus und die steigende Zahl in Gruppenkopf und Kopfleiste.

### Telefonbreite (360px)

Prüfpunkte für die Sichtprüfung und für `e2e/tests/no-horizontal-scroll.spec.ts` (der Dialog-Abschnitt wird durch das aufgeklappte Band ersetzt):

- Kein waagerechtes Scrollen, weder in der Serie noch in der aufgeklappten Reihe.
- „Tauschen“ und „Hinzufügen“ jeder Alternative sind sichtbar ≥44px hoch, mit 12px Abstand, ohne Überlappung.
- Umschalter, „Weitere Fotos“ und „Schließen“ sind einzeln treffbar, mit 12px Abstand.
- Der Dateiname wird gekürzt (`truncate`), der vollständige Pfad steht in den zugänglichen Namen.

### Bezug zum Design-System

Wiederverwendet werden:

- „Band am gewählten Element“
- „Bezugsmarke in einer geordneten Kandidatenreihe“
- „Die Entscheidungsfläche nennt die Handlung“
- Trefferflächen-Regeln
- Ladezustand, Fehlerzustand und Leerer Zustand
- Busy-Button

Neu ist das Muster „aufklappbare volle Reihe im Band“. Es ersetzt den Dialog „Alle Alternativen“. Die Änderungen am Design-System sind unten aufgeführt.

## Security

**Einstufung:** sicherheitsrelevant, kein Blocker. Es gibt kein Secret, keinen externen Dienst, keinen Fremdtext, keine Migration, keine neue Auth-Logik und keinen neuen Schreibendpunkt. Geändert wird der bestehende authentifizierte Lesepfad `GET /projects/{id}/draft-alternatives`:

- eine Eingabe wird ersetzt (`nearest` → `series`),
- ein Deckel wandert (`BAND_MAX` → `BAND_MAX_SERIES`),
- ein Antwortfeld kommt hinzu (`series_rest`).

Im Frontend kommt ein schon vorhandener Schreibweg an eine neue Stelle: Hinzufügen über `PUT /photos/{id}/rating` mit `album_worthy`. Die Auflagen S1–S4 und S8 der Spec 0558 sowie S3 der Spec 0569 gelten unverändert und werden hier nicht wiederholt.

### Bedrohungen und Bewertung

- **`series_rest` als Informationsabfluss.** Der Wert zählt Kandidaten **desselben Laufs und Events**, abzüglich des **eigenen** Entwurfs. Er ist also eine Funktion des anfragenden Nutzers, genau wie `total`, `offset` und `reference_index`. Neu ablesbar wird nur die Dichte der Aufnahmezeiten im Event. Die ist über die zeitlich geordnete volle Reihe desselben Endpunkts ohnehin lesbar, und beide Nutzer sehen alle Projekte. Damit entsteht keine neue Datenklasse. Ein Leck entstünde erst, wenn der Wert aus einer zweiten Abfrage käme: ohne Lauf- oder Eventprädikat oder mit einem zweiten `Rating`-Alias ohne Nutzerbedingung. Dann stünde dort eine plausible Zahl zu einer fremden Menge, und nichts würde rot.
- **Last über den Fensterdeckel.** Mit `series` bestimmt allein der Server die Fenstergröße. Die Hydratation (`_photos_by_id` mit `selectinload`) ist auf `BAND_MAX_SERIES = 12` begrenzt. Die Serienbildung braucht nur die `taken_at` der ohnehin geladenen Kandidatenreihe, eine zusätzliche Abfrage gibt es nicht.
- **Alter Client nach dem Wegfall von `nearest`.** FastAPI ignoriert unbekannte Query-Parameter. Ein vom Service Worker (`registerType: 'autoUpdate'`) noch nicht ersetzter Client schickt `photo_id` und `nearest=4` und bekäme damit still die erste Seite der vollen Reihe. Das sähe aus wie ein Band, wäre aber keines. Es ist derselbe Fall wie der `draft`-Riegel (S3 der Spec 0558).
- **Aufgeklappte Reihe.** Sie nutzt den vorhandenen Seitenabruf mit `photo_id`, `offset` und `limit=60`. Der vorhandene Deckel `limit ≤ 200` bleibt die Sicherheitsgrenze, ein Abruf aller Fotos in einem Zug ist ausgeschlossen. Neue Eingabe von außen gibt es nicht.
- **Hinzufügen aus Band und Reihe.** Es entsteht kein neuer Endpunkt. Es ist derselbe `decisionMutation`-Weg wie im Hinzufügen-Panel: eigene Bewertungszeile, `user_id` aus dem JWT, Bindung an die globale `photo_id` wie bisher. Eine Projekt-Mitgliedschaft gibt es nicht, das ist akzeptiert. Geschrieben wird nie die Zeile des anderen Nutzers. Ein Hinzufügen kann nichts, was das Panel nicht schon kann.
- **Darstellung.** Dateinamen erscheinen in sichtbaren Beschriftungen und in den Namen `"Tauschen: {relative_path}"` / `"Hinzufügen: {relative_path}"`. Dazu kommt `series_rest` im Hinweistext. Dafür gilt S11 der Spec 0558.

### Auflagen (Muss) mit Nachweis

1. **`series` ist ein strikt geparster Wahrheitswert und gilt nur mit `photo_id`.**
   - Signatur: `series: bool = Query(False)`.
   - `series=true` ohne `photo_id` ergibt `422` vor jeder Abfrage.
   - Ein nicht als bool lesbarer Wert (`series=2`, `series=abc`) ergibt `422`.
   - `series=false` verhält sich wie ein fehlender Parameter.
   - Der Rohwert wird nicht geloggt und im Frontend nur als Textknoten gezeigt.
   - *Nachweis:* `test_series_without_a_reference_is_refused` ersetzt `test_nearest_without_a_reference_is_refused`. Dazu kommt eine parametrisierte Tabelle in `TestDraftAlternativesKeys` für ungültige Werte.
2. **`nearest` scheitert laut statt still.**
   - Signatur: `nearest: None = Query(None, include_in_schema=False)`, Antwort `422` bei jeder Belegung. Das ist dasselbe Muster wie der `draft`-Riegel an `GET …/photos`.
   - *Nachweis:* `test_the_retired_nearest_parameter_is_refused`, mit und ohne `photo_id`.
   - *Abweichung von der Architektursektion,* die „ersatzlos“ sagt: Die Entscheidung ist rein technisch und folgt dem bestehenden Muster dieses Routers.
3. **Mit `series` stammt das Fenster allein vom Server, gedeckelt durch `BAND_MAX_SERIES`.**
   - Ein mitgeschicktes `offset`/`limit` wirkt nicht.
   - Es gilt `len(items) ≤ BAND_MAX_SERIES ≤ 200`, und `offset` liegt in `[0, max(0, total − len(items))]`.
   - `BAND_MAX_SERIES` ist eine Modulkonstante in `selection.py`. Kein Client-Wert geht in die Fensterrechnung ein.
   - Die Hydratation lädt nur die Ids des Fensters.
   - *Nachweise:*
     - `offset=999999&limit=200&series=true` liefert dasselbe Fenster und dieselben Werte für `offset` und `series_rest` wie ohne diese Werte.
     - Eine Serie mit mehr als 12 Bildern liefert genau 12 `items`.
     - Ein Test hält fest, dass `BAND_MAX_SERIES` kleiner oder gleich dem `limit`-Deckel ist.
4. **`series_rest` entsteht aus derselben Kandidatenmenge wie `total`, `offset` und `reference_index`.**
   - Es gibt keine eigene Zähl- oder Positionsabfrage.
   - Es gilt `0 ≤ series_rest ≤ total − len(items)`.
   - Ohne `series` und im Leerkörper `_no_alternatives` ist der Wert `0`. Der Leerkörper bleibt für jede Fehlerursache byte-gleich: `{"items": [], "total": 0, "offset": 0, "reference_index": null, "series_rest": 0}`.
   - *Nachweise:*
     - `test_every_failed_resolution_gives_the_same_bytes` wird auf die neue Form erweitert, auch mit `series=true`.
     - Ein Test mit zwei Nutzern und unterschiedlichen eigenen Entwürfen in derselben Serie: Eine `album_worthy`- oder `rejected`-Entscheidung des **anderen** Nutzers ändert weder `items` noch `total`, `offset`, `reference_index` oder `series_rest` des Anfragenden. Das ist die Erweiterung von Auflage 8 der Spec 0569.
     - Ein Kandidat aus einem fremden Event oder älteren Lauf mit `taken_at` innerhalb der Serie überbrückt keine Lücke und zählt nicht in `series_rest`.
5. **Cache-Schlüssel.** `series_rest` ist ein weiterer nutzerabhängiger Antwortbestandteil.
   - Der Client-Schlüssel der Serienabfrage trägt die Identität hinter dem Präfix `['photos', projectId]`, wie bisher der Alternativen-Schlüssel. `series: true` ersetzt `nearest` im Schlüssel.
   - Die volle Reihe bekommt einen eigenen Schlüssel, ebenfalls mit Identität.
   - Auf HTTP-Ebene kommt weiterhin kein `ETag`/`Cache-Control` über `no-store` hinaus ohne Nutzer im Schlüssel.
   - *Nachweis:* `useDraftAlternativesQuery`-Test: Die Schlüssel beider Abfragen enthalten die Identität und unterscheiden sich zwischen Serie und Reihe.
6. **Die aufgeklappte Reihe nutzt nur den vorhandenen Seitenabruf.**
   - `limit = PHOTOS_PAGE_SIZE = 60`. Der serverseitige Deckel `limit ≤ 200` und die Grenzen von `offset` bleiben unverändert.
   - Es gibt keinen Abruf ohne `photo_id` und Event-Prädikat und keinen Ersatz-Bezug.
   - *Nachweis:* Der bestehende Test `test_without_a_reference_a_foreign_event_yields_nothing` und die bestehende `limit`-Grenztabelle laufen unverändert weiter.
7. **Hinzufügen aus Band und Reihe ist derselbe Schreibweg wie im Panel.**
   - `handleAdd` ruft ausschließlich die bestehende `decisionMutation` auf (`PUT /photos/{id}/rating`, `album_worthy`).
   - Kein zweiter Schreibpfad, kein Body-Feld `user_id`, keine Id aus einem Attribut des DOM, nur aus dem Kandidatenobjekt der Antwort.
   - *Nachweise:*
     - Seitentest: Hinzufügen aus Band und Reihe sendet genau einen `PUT` auf die Kandidaten-Id mit demselben Body wie das Panel.
     - Der bestehende `test_put_rating_never_overwrites_another_users_rating` läuft unverändert weiter.
8. **Dateiname und Zahl bleiben Text (S11 der Spec 0558, erweitert).**
   - Der Geltungsbereich umfasst nun `CandidatePanel` (`actions`), die aufgeklappte Reihe und den Serienhinweis.
   - `relative_path` erscheint nur als React-Textknoten oder als `aria-label`-Prop. Nie in `key`, `id`, Fokusschlüssel, `href`, `src`, `style` oder `dangerouslySetInnerHTML`.
   - Der Fokusschlüssel `"{key}-{id}"` besteht aus dem festen Aktionsschlüssel und der numerischen Id.
   - `series_rest` wird nur angezeigt, wenn es eine Ganzzahl > 0 ist. Sonst entfällt der Hinweis, ohne Fehler und ohne Fallback.
   - *Nachweis:* Komponententest mit einem Dateinamen wie `<img src=x onerror=alert(1)>.jpg`. Er erscheint wörtlich im Namen, und es entsteht kein `img`-Element.
9. **S1 unverändert.**
   - Die Auth-Dependency bleibt ausgeschrieben. Der Router hat kein Vollständigkeitsnetz.
   - *Nachweis:* Der bestehende 401-Test läuft weiter, jetzt mit `series=true`.
10. **Kein Log.** Weder `taken_at` noch `reference_index`, `offset`, `series` oder `series_rest` gehen in eine Logzeile.

**Ausdrücklich geprüft und ohne Befund:**

- keine neue Datenklasse zwischen den beiden Nutzern,
- keine Berührung von Secrets, `.env`, Consent-Schalter, Kostenschätzung oder Bilddatenfluss,
- kein Rate-Limiting nötig, konsistent mit der übrigen API.

Die entfallene Fokusfalle des Dialogs ist eine Frage der Barrierefreiheit, keine Sicherheitsfrage. Das `+`-Zeichen ist statischer Text.

### Securitykonzept fortschreiben

Im Abschnitt „Der Album-Entwurf je Nutzer“, im Absatz „Fortschreibung Spec 0569/ADR 0132“, wird der `nearest`-Satz mit Verweis auf Spec 0578 / ADR 0133 durchgestrichen, nicht gelöscht. Neu kommt hinzu:

- `series` (nur mit `photo_id`, sonst `422`), Fenster allein vom Server, gedeckelt durch `BAND_MAX_SERIES = 12`;
- `nearest` bleibt als Riegel mit `422` stehen;
- `series_rest` ist der vierte nutzerabhängige Träger der Cache-Schlüssel-Auflage, neben `total`, `offset` und `reference_index`;
- `series` und `series_rest` stehen in der Liste der nicht geloggten Werte.

Die Ankerzeile zum Bezugsbild (Spec 0569, S3) bleibt unverändert. Ihr Test-Nachweis nennt den Leerkörper mit `series_rest: 0`.

Der Docstring von `draft_alternatives` wird umgeschrieben, nicht gelöscht: `photo_id` steuert allein die zeitliche Position (`reference_index`, Serienfenster, `series_rest`).

## Teststrategie

**Backend Unit (`test_selection.py`, DB-frei) — `series_window` erschöpfend.** Tabellengetrieben über synthetische Zeitreihen; Schwelle am Symbol `SERIES_GAP` (± 1 s), nie als abgeschriebene Zahl, `BAND_MIN`/`BAND_MAX_SERIES` ebenso. Pflichtfälle:
- Lücke genau `SERIES_GAP` → gehört dazu; `SERIES_GAP + 1 s` → trennt. Beide Seiten einzeln (Lücke vor vs. nach dem Bezugsbild), damit ein `>` statt `>=` auf nur einer Seite auffällt.
- Kette: Abstände je ≤ Schwelle, Gesamtspanne weit darüber → ganze Kette gehört dazu (Nachbarabstand, nicht Abstand zum Bezugsbild).
- Einseitige Serie: Bezugsbild am Serienanfang bzw. -ende, Bezugsbild Index 0 und letzter Index des Events.
- Dichte Aufnahmen jenseits der ersten Lücke zählen nicht (zweite Serie dahinter).
- Serie < 4: Auffüllen über die Lücke hinaus, einseitig und beidseitig; Event mit 0, 1, 2, 3 Kandidaten → Fenster = ganzes Event, `rest = 0`.
- Serie genau 4 und genau 12 → genau die Serie, `rest = 0`; Serie 13 → 12, `rest = 1`; Serie 30 mit Bezugsbild am Rand → 12 innerhalb der Serie (nie über die Seriengrenze), `rest = 18`.
- Gleichstand: zwei Nachbarn mit exakt gleichem Abstand → der frühere gewinnt (beim Füllen auf 4 und beim Kappen auf 12). Gleiche `taken_at` mehrerer Fotos (Abstand 0) → Ordnung nach `photo_id`.
- Invarianten über alle Fälle: Fenster zusammenhängend, enthält `reference_index`, `size = min(max(Serie, min(4, n)), 12)` sinngemäß, `rest ≥ 0`, `offset + size ≤ n`. Erschöpfende Aufzählung kleiner Folgen (Abstände aus {0, Schwelle, Schwelle+1 s}, Länge bis ~15, alle Bezugsindizes) gegen eine im Test nachgebildete Referenz statt Property-Testing (Muster der Sektion zu ADR 0109, Punkt 3).
- `nearest_window_offset` samt Tests entfällt.

**Backend Integration (`test_api_photos.py`, `draft_alternatives`).**
- `series=true` liefert das Fenster aus `series_window` samt `series_rest`; ein mitgeschicktes `offset`/`limit` ändert nichts (gleiche Antwort mit und ohne).
- `series=true` ohne `photo_id` → `422`; `nearest` wird nicht mehr angenommen bzw. wirkt nicht (Abwesenheit belegen).
- `series_rest = 0` ohne `series` und im Leerkörper; Leerkörper byte-gleich über alle Fehlerursachen (bestehender Test, nur um das Feld erweitert).
- Gestrichene Alternative zählt in der Serie; aussortiertes Duplikat steht in keiner Serie und überbrückt keine Lücke; ein Foto aus dem Entwurf zwischen zwei Alternativen überbrückt keine Lücke (Datenlage: Entwurfsfoto mittig, Alternativen links/rechts > Schwelle auseinander).
- `total`, `offset`, `reference_index` konsistent (Marke bei `reference_index − offset`); S1–S4/S8 unverändert grün (Nachweis ohne Rot-Grün).
- Hydratationsdeckel: Serie > 12 lädt nicht mehr als 12 Fotos (Abfragezählung oder Antwortlänge).

**Frontend vitest.**
- `CandidatePanel`: `actions` rendert je Kandidat „Tauschen“ dann „Hinzufügen“ mit Namen `"{label}: {relative_path}"`, Marke ohne Handgriffe; `DraftAddPanel` nur „Hinzufügen“; `busy` sperrt beide Knöpfe derselben Kachel, andere bleiben bedienbar; Doppeldruck → genau ein Aufruf.
- Marke über Seiten: Marke auf Seite 1 / am Seitenende mit und ohne Folgeseite / auf Seite 2 (Hinweis `REFERENCE_LATER_TEXT`, nach „Weitere Fotos“ Marke genau einmal, Hinweis weg). Wird aus dem gelöschten Dialogtest übernommen, nicht neu erfunden.
- `DraftAlternativesBand`: Abfrage mit `series: true` im Schlüssel; Serienrest-Hinweis bei 0 (fehlt), 1 (Singular), n (Plural), nicht in der aufgeklappten Reihe; Umschalter-Zustände (`aria-expanded`, Wortlaut, fehlt beim Laden/leer, bleibt bei Fehler); volle Reihe lädt erst beim Aufklappen (Spion: kein Aufruf vorher), Zurückschalten und erneutes Aufklappen ohne weiteren Aufruf; Fokus bleibt auf dem Umschalter; kein `scrollIntoView`/`scrollTo`; Esc im aufgeklappten Zustand schließt beides, Fokus auf `alternatives-{photoId}`; kein Element mit `role="dialog"`.
- `AlbumDraftPage`: Hinzufügen aus Band und Reihe → Band bleibt offen, Foto verschwindet, Fokus Nachfolger/Vorgänger/Überschrift (drei Fälle), Entwurfszahl +1, Bezugsfoto unverändert, gestrichene Alternative wird „Aufgenommen“, offener „Getauscht“-Hinweis endet, kein Rückgängig-Hinweis, keine Richtwert-Warnung. **Hinzufügen-dann-Tauschen** als Folge (Muster 2 der Sektion zu #558, Cache = Serverantwort nach jedem Schritt): zwei Hinzufügungen, dann Tausch → ersetzt wird das Bezugsfoto; Rückgängig → nur der Tausch zurück, beide Hinzufügungen bleiben. Tausch aus der Reihe = Tausch aus dem Band (Band zu, „Getauscht“, kein Neuladen). Fehlschlag Hinzufügen und Tauschen je einzeln: Entwurf unverändert, Band offen, `role="alert"` mit Server-`detail` im Band, Kachel wieder bedienbar, Fokus bleibt. Höchstens ein Band: zweites Öffnen schließt das erste samt Reihe; neues Band startet zugeklappt.
- **Kein Nachrücken:** `invalidateAllButTheDraft` markiert `'alternatives'` nur veraltet — Spion: nach Hinzufügen kein Alternativen-Abruf, Liste −1, Serienrest-Zahl unverändert; Gegenfall: nach Schließen und erneutem Öffnen genau ein frischer Abruf. Gleiches für das Hinzufügen-Panel (ebenfalls kein Nachrücken mehr — benannte Erwartungsänderung, kein Regress).
- `DraftEventSection`: „+“ in `aria-hidden`-Span, zugänglicher Name exakt „Foto hinzufügen: {Eventname}“; das „+“ kommt in Band/Reihe/Panel nicht vor.
- Entfernen: `DraftAlternativesDialog` samt Test, Dialog-Einträge in `designSystem.contract.test.ts`, `onOpenAll`/Fehlerstelle `'dialog'` — benannte Löschungen abgelöster Zusagen.

**E2E (Playwright, 360 px).**
- `no-horizontal-scroll.spec.ts`: Dialog-Abschnitt ersetzt durch geöffnetes Band zugeklappt **und** aufgeklappt (Vorbedingung: Raster mit ≥ 1 Alternative und Umschalter `aria-expanded=true` sichtbar); dazu Höhe ≥ 44 px von „Tauschen“/„Hinzufügen“ und 12 px Abstand.
- `tap-targets.spec.ts`: „Tauschen“ und „Hinzufügen“ der ersten Alternative, Umschalter, „Schließen“ und „Weitere Fotos“ der aufgeklappten Reihe; `EXPECTED_CONTROL_COUNT` bewusst anheben, die Dialog-Einträge fallen weg. Weil der Demo-Bestand kein Event mit mehr als 60 Alternativen hat, hebt der Spec per `page.route` allein `total` der echten Serverantwort der vollen Reihe an, damit „Weitere Fotos“ erscheint (Regel im Testkonzept, Nachtrag zur Tabelle „Umfang“).
- Schreibender Hinzufügen-Fall nur, wenn nötig, dann nach Muster 7 der Sektion zu #558 (Wiederherstellung im `finally` über die API). Die Paginierungslogik (Marke auf späterer Seite) bleibt in vitest; jsdom kann sie vollständig prüfen, der Demo-Bestand hat dafür kein Event mit > 60 Alternativen.

**Bewusst nicht automatisiert:** Erhalt der Scrollposition als gemessene Pixel (jsdom ohne Layout; belegt wird die Abwesenheit programmatischen Scrollens plus `preventScroll`), Sichtwirkung des „+“ — Sichtprüfung bei 360 px.

## Entscheidungen

- Stories #577 und #578 auf Daniels Wunsch zu einer Story zusammengeführt; #577 ist mit Verweis geschlossen.
- Pausenschwelle etwa 2 Minuten, fest; kleine Serien auf 4 auffüllen; höchstens 12 im Band; aussortierte Duplikate bleiben draußen; Band füllt nach einem Hinzufügen nicht nach (Daniel, Refinement).
- `nearest` bleibt als `422`-Riegel statt ersatzlos zu entfallen (security-engineer, Auflage 2).
- „Tauschen" und „Hinzufügen" stehen untereinander statt nebeneinander (ux-ui-designer, 360 px und zwei Spalten).
- Plus an „Foto hinzufügen" als Textzeichen statt neuem Lucide-Symbol (geschlossener Symbolsatz).
- `specs/architecture/0002-testkonzept.md`: keine Strategieänderung; Zeilen `no-horizontal-scroll` und `tap-targets` werden im Umsetzungs-PR nachgezogen (test-engineer).
- `specs/architecture/0003-securitykonzept.md` wird im Umsetzungs-PR an `series`/`series_rest`/`nearest`-Riegel angepasst (security-engineer).

## Offene Fragen

- keine

## Out of Scope

- Welche Fotos überhaupt Alternativen sein können (Kandidatenmenge), Ausschuss-Duplikate.
- Das Hinzufügen-Panel selbst, außer seiner Schaltfläche „Foto hinzufügen".
- Endauswahl, Großansicht, Gestaltung der Kacheln (Story #579).
