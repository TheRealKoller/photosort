# 0569 - Ersatzvorschläge zeitlich geordnet

**Status:** Implemented ([PR #576](https://github.com/TheRealKoller/photosort/pull/576))
**Erstellt:** 2026-10-04
**Bezug:** [Issue #569](https://github.com/TheRealKoller/photosort/issues/569)

**Umfang:** über dem Richtwert von ~200 Zeilen, weil Fensterregel, Markenposition und neue Endpunkt-Auflagen je eigene Randfälle tragen.

## Ziel

Wer im Album-Entwurf ein Bild ersetzen will, bekommt heute Ersatzvorschläge, deren Reihenfolge zufällig wirkt: Zusammengehörige Aufnahmen derselben Situation stehen nicht beieinander, es ist nicht erkennbar, nach welchem Kriterium die Vorschläge geordnet sind, und man sieht nicht, ob ein Vorschlag als albumtauglich eingestuft ist. Beide Nutzer kuratieren und müssen dadurch mühsam suchen.

Künftig erscheinen die Ersatzvorschläge in zeitlicher Reihenfolge, das zu ersetzende Bild ist in dieser Reihe sichtbar eingeordnet, und das Ordnungskriterium ist benannt. Die bisherige Regel „zuerst gleiches Motiv, dann nach Qualität; zeitliche Nähe ist kein Sortierkriterium“ wird damit bewusst aufgehoben. Eine deutlichere Markierung der Albumtauglichkeit ist nachrangig.

## User Story

Als Nutzer, der im Album-Entwurf ein Bild ersetzen will, möchte ich die Ersatzvorschläge zeitlich geordnet rund um das zu ersetzende Bild sehen und erkennen, welche davon als albumtauglich eingestuft sind, damit ich zusammengehörige Aufnahmen derselben Situation nebeneinander vergleichen und schnell eine nachvollziehbare Wahl treffen kann.

## Akzeptanzkriterien

- [ ] **AK1 (Dialog, volle Reihe):** Mit `photo_id` liefert `GET /projects/{id}/draft-alternatives` `items` aufsteigend nach `(Photo.taken_at, photo_id)` geordnet. Das gilt über alle Seiten: Werden Seite 1 und Seite 2 aneinandergehängt, ergibt das dieselbe Folge wie die Ordnung der vollen Restmenge.
- [ ] **AK2 (Motiv/Qualität ohne Einfluss):** Zwei Aufbauten, die sich nur in Motivstärken und `rank_score` unterscheiden, ergeben dieselbe Id-Folge. Ein zeitlich früheres Bild mit niedrigerer Qualität und ohne gemeinsames Motiv steht vor einem späteren mit höherer Qualität und gemeinsamem Motiv.
- [ ] **AK3 (Band = zeitlich nächste):** Mit `nearest=4` gilt `offset = clamp(reference_index − 2, 0, max(0, total − 4))`. Die Antwort enthält genau `min(4, total)` Bilder, zeitlich geordnet. Im Normalfall liegen 2 vor und 2 nach dem Bezugsbild. Am Anfang oder Ende der Reihe wird von der anderen Seite aufgefüllt. Der verwendete `offset` wird zurückgegeben.
- [ ] **AK4 (Markierung):** `reference_index` ist die Zahl der Kandidaten, die nach demselben Schlüssel vor dem Bezugsbild liegen. Ohne `photo_id` ist er `null`. Das Band zeigt die Markierung des Bezugsbildes an der Stelle `reference_index − offset`, wenn dieser Wert in `[0, items.length]` liegt (beide Fenstergrenzen zulässig); sonst keine. Der Dialog legt die geladenen Seiten zu einer Reihe zusammen und zeigt die Markierung darin genau einmal an der Stelle `reference_index`; am Ende der geladenen Reihe nur, wenn keine Seite mehr folgt. Folgt noch eine, steht bis zum Nachladen der Hinweis „Das zu ersetzende Bild folgt weiter hinten in der Reihe.“ Bei `total = 0` gibt es keine Markierung, nur den bestehenden Leertext.
- [ ] **AK5 (Wortlaut):** Band und Dialog zeigen den Wortlaut `Zeitlich geordnet, von früh nach spät` (eine Konstante, siehe UI/UX).
- [ ] **AK6 (Gleichstand):** Bei gleichem `taken_at` entscheidet die kleinere `photo_id`, unabhängig von der Reihenfolge der Eingabe (geprüft über alle Permutationen). Das gilt auch, wenn das Bezugsbild selbst im Gleichstand steht.
- [ ] **AK7 (ohne EXIF):** Ein Foto, dessen `taken_at` aus `last_modified` stammt, ordnet sich nach diesem Wert ein. Es gibt keinen Sonderzweig.
- [ ] **AK8 (Menge unverändert):** Die Id-Menge (ohne Ordnung) und `total` sind vor und nach der Umstellung gleich. Die bestehenden Mengen-Tests bleiben grün.
- [ ] **AK9 (beide Nutzer):** Für zwei Nutzer mit derselben Restmenge ist die Id-Folge identisch. Bei unterschiedlichen Restmengen ist die relative Ordnung der gemeinsamen Ids identisch.
- [ ] **AK10 (nachrangig):** Jeder Vorschlag in Band und Dialog trägt die Albumtauglichkeit (`QualityMeter` aus `rank_score`) mit eigener Beschriftung. Das Kennzeichen „Album-würdig“ erscheint davon getrennt und nur bei eigener Bewertung.
- [ ] **AK11 (Hinzufügen-Panel unverändert):** Ohne `photo_id` bleibt die Ordnung nach Qualität (`None` zuletzt, dann kleinere Id). `reference_index` ist `null`; `nearest` ohne `photo_id` ergibt `422`.
- [ ] **AK12 (Validierung):** `nearest` außerhalb von `1..BAND_MAX` ergibt `422`.

## Datenmodell-Bezug

Keine Änderung. Gelesen wird `Photo.taken_at` (NOT NULL, ohne EXIF-Zeit aus `last_modified`); Antwortform des Endpunkts siehe unten.

## Architektur / Umsetzung

**Ansatz:** Die Reihenfolge entsteht weiter allein im Backend am bestehenden Endpunkt `GET /projects/{id}/draft-alternatives`. Der Zweig **mit** `photo_id` wird von „Motivgruppe, dann Qualität“ auf eine zeitliche Ordnung umgestellt. Das Frontend sortiert nie selbst. Entscheidung und Teil-Ablösung stehen in ADR [`0132`](../decisions/0132-alternativen-zeitlich-geordnet-mit-bezugsposition.md). Sie löst aus ADR 0098 Punkt 5 nur die Sortierregel ab; ADR 0098 trägt einen entsprechenden Kopfvermerk.

**Sortier- und Tie-Breaker-Regel:** Bezugsbild und Kandidaten werden aufsteigend nach `(Photo.taken_at, photo_id)` geordnet, also früh nach spät.
- `taken_at` ist die um den Kamera-Versatz korrigierte, wirksame Zeit (ADR 0090).
- Bei gleichem Zeitpunkt entscheidet die kleinere `photo_id`. Das ergibt eine Totalordnung, die bei jedem Öffnen gleich ist.
- Motiv, Qualität und Nutzer gehen nicht in den Schlüssel ein. Deshalb sehen beide Nutzer dieselbe Reihenfolge; die Menge selbst bleibt je Nutzer, wie bisher.
- „Ohne Aufnahmezeitpunkt“ ist strukturell leer: `Photo.taken_at` ist NOT NULL und fällt auf `last_modified` zurück. Ein solches Bild ordnet sich nach dieser Zeit ein. Ein eigener Zweig dafür wird nicht gebaut (siehe offene Frage).

**Das zu ersetzende Bild in der Reihe:** Das Bezugsbild gehört zum Entwurf und ist nie in `items`. Der Server liefert `reference_index`: die Zahl der Kandidaten der vollen Restmenge, die nach demselben Schlüssel vor dem Bezugsbild liegen. Im Band setzt das Frontend die Markierung an die Stelle `reference_index − offset`, wenn dieser Wert in `[0, items.length]` liegt; beide Fenstergrenzen sind zulässig. Im Dialog legt es die geladenen Seiten zu einer Reihe zusammen und setzt die Markierung darin genau einmal an die Stelle `reference_index`: am Ende der geladenen Reihe nur, wenn keine Seite mehr folgt, sonst steht bis zum Nachladen der Hinweis „Das zu ersetzende Bild folgt weiter hinten in der Reihe.“

**Auswahlregel des Bands:** Neuer Query-Parameter `nearest` (int, `ge=1, le=BAND_MAX`, nur zusammen mit `photo_id` zulässig, sonst `422`). Der Server setzt `offset = clamp(reference_index − ⌊N/2⌋, 0, max(0, total − N))`, liefert genau dieses Fenster mit `N = BAND_SIZE = 4` und gibt den verwendeten `offset` zurück.
- Im Normalfall stehen 2 Bilder davor und 2 danach.
- Am Anfang oder Ende der Reihe wird von der anderen Seite aufgefüllt.
- Bei `total < N` werden alle Bilder gezeigt.
- Bei `total = 0` bleibt der bestehende Leertext; die Markierung entfällt.
- Innerhalb des Fensters bleibt die zeitliche Ordnung erhalten.
- Der bestehende clientseitige Filter `excludedIds` (optimistisch getauschte Bilder) kann das Fenster vorübergehend verkürzen. Das ist unverändert und wird nicht ausgeglichen.

**API-Vertrag (ändert sich):**
- Neue Antwortform `DraftAlternativesOut { items, total, offset, reference_index: int | None }` statt `PhotoListOut`, nur an diesem Endpunkt.
- `reference_index` ist `null` ohne `photo_id`.
- Neuer optionaler Parameter `nearest`.
- Ohne `photo_id` (Hinzufügen-Panel) gelten Ordnung nach Qualität und Verhalten unverändert.
- Auflagen S2/S3/S4/S8 bleiben gültig. Das Bezugsbild wird weiterhin ausschließlich über eine Rangzeile desselben Laufs und desselben Events aufgelöst. Neu ist, dass aus der Reihenfolge die Zeitposition des Bezugsbildes ablesbar ist; das ist nur durch genau dieses Prädikat gedeckt (Hinweis an security-engineer).

**Datenfluss:**
1. Bezugsbild auflösen (Rangzeile + Join auf `Photo.taken_at`).
2. Kandidatenabfrage wie bisher, ergänzt um `Photo.taken_at` per Join.
3. Ordnen mit `order_alternatives_chronologically`, `reference_index` bestimmen.
4. Die Seite bzw. das Fenster schneiden.
5. Hydratation nur über die Seite, einschließlich `load_effective_strengths` nur noch für die Seiten-Ids.

**Betroffene Dateien/Symbole (Reihenfolge):**
1. `backend/src/photosort/selection.py`
   - `AlternativeCandidate` und `order_alternatives` aufteilen: neue reine Funktion `order_alternatives_chronologically(reference, candidates) -> (ids, reference_index)` mit Kandidaten `(photo_id, taken_at)` sowie die Qualitätsordnung für den Zweig ohne Bezugsbild (`order_by_quality`).
   - Die Motivstufe entfällt ersatzlos, ebenso der Docstring-Satz „KEINE `taken_at`“.
   - Neue reine Funktion für das Band-Fenster (`nearest_window_offset(reference_index, total, n)`).
2. `backend/src/photosort/api/photos.py::draft_alternatives`: Abfragen, Parameter `nearest`, Antwortmodell `DraftAlternativesOut`, Docstring (Reihenfolge, S3-Satz zur Sortierung).
3. `backend/tests/test_selection*.py` und `test_api_photos.py` (Alternativen-Tests): Erwartungen zur Motivreihenfolge werden durch zeitliche Erwartungen ersetzt.
4. Frontend:
   - `frontend/src/api/types.ts` (neuer Typ), `frontend/src/api/photos.ts::listDraftAlternatives` (Parameter `nearest`, Rückgabetyp).
   - `frontend/src/hooks/usePhotos.ts::useDraftAlternativesQuery`: Band ohne Folgeseiten.
   - `components/DraftAlternativesBand.tsx`: `nearest=BAND_SIZE`, Markierung des Bezugsbildes, Text „zeitlich geordnet“.
   - `components/DraftAlternativesDialog.tsx`: Markierung genau einmal über die geladenen Seiten (am Ende nur ohne Folgeseite, sonst Hinweis), Ordnungstext. Der Kommentar „hängt an den Motiven“ wird angepasst.
   - Die zugehörigen Tests.
5. Albumtauglichkeit: Die bestehende `QualityMeter` (Albumtauglichkeit aus `rank_score`) bleibt je Vorschlag stehen. Sie wird nicht mit dem Kennzeichen „Album-würdig“ (eigene Bewertung) zusammengelegt; Abgrenzung und Wortlaut übernimmt ux.

**Nicht betroffen:** `DraftAddPanel` / Zweig ohne `photo_id`, Austausch-Schreibweg, Kandidatenmenge.

## UI/UX

**Sichtbare Oberfläche:** ja. Betroffen sind das Alternativen-Band (`DraftAlternativesBand.tsx`) und der Dialog „Alle Alternativen“ (`DraftAlternativesDialog.tsx`). `DraftAddPanel` bleibt unverändert, ebenso die gemeinsame Gestalt in `CandidatePanel`, soweit unten nichts anderes steht.

**Ordnungstext (wörtlich, eine Konstante für Band und Dialog):** `Zeitlich geordnet, von früh nach spät` (Konstante `ALTERNATIVES_ORDER_TEXT` in `DraftAlternativesBand.tsx`, vom Dialog importiert).
- Ort im Band: als `<p className="text-xs text-text">` direkt unter der `h4` „Alternativen zu {Dateiname}“.
- Ort im Dialog: unter der Bezugsbild-Zeile, über dem Raster.
- Der Text erscheint nur, wenn mindestens ein Kandidat da ist. Bei Laden, Fehler und Leerzustand fehlt er, denn eine Ordnung ohne Reihe sagt nichts.
- Kein Pfeilzeichen („→“): Ein Screenreader liest es als „Pfeil nach rechts“, und der Satz trägt die Richtung schon in Worten.

**Raster als geordnete Liste:** Das Kandidaten-Raster wird in Band und Dialog von `<ul>` zu `<ol>`, weil die Reihenfolge jetzt Bedeutung trägt. Die Gitterklassen bleiben (`PHOTO_CARD_GRID_CLASS` bzw. `ALTERNATIVES_GRID_CLASS`). Die Lade-Platzhalter bleiben ein `<ul role="status">`.

**Bezugsmarke (das zu ersetzende Bild in der Reihe):** ein eigenes `<li>` im selben Raster, an der zeitlichen Stelle des Bezugsbildes.
- Inhalt: dieselbe quadratische Bildfläche (`PhotoImage variant="thumbnail"`, `object-contain`, `rounded-md`) mit dem Bezugsbild.
- Darunter das Wort **„Wird ersetzt“** in `text-xs font-semibold text-text-h`. Im Band steht zusätzlich der Dateiname in `truncate font-mono text-xs text-text`, wie bei den Kandidaten.
- Abgesetzt wird die Marke durch eine **anliegende** Akzentkante `ring-2 ring-accent` an der Bildfläche. Das folgt der Regel „Auswahl/Aktiv anliegend, Fokus abgesetzt“, sodass die Marke nie wie ein fokussiertes Element aussieht.
- Die Unterscheidung trägt nie allein die Farbe. Entscheidend sind das Wort und das Fehlen der Aktion.
- Die Marke ist **kein Bedienelement**:
  - kein Button, kein „Tauschen“, keine Trefferfläche, kein Fokus;
  - keine `QualityMeter`, kein Kennzeichen.
- Das Bezugsbild steht dem Nutzer nicht zur Wahl. Eine Einstufung daran lädt zum Vergleichen ein, ist aber nicht Teil der Story und bleibt weg.
- Die Bildfläche hat dieselben Maße wie die Kandidaten. So bleibt die Rasterzeile bündig, und die Marke verschiebt keine Aktionshöhen.
- Die kleine Bezugsbild-Zeile oben im Dialog bleibt bestehen (Einstieg „wogegen tausche ich?“). Die Marke im Raster beantwortet die neue Frage „wo liegt es zeitlich?“.

**Position der Marke:**
- **Band:** Die Marke steht vor dem Kandidaten mit dem Index `reference_index − offset` der **ungefilterten** Serverantwort. Bei `= items.length` steht sie am Ende.
  - Fällt dieser Kandidat durch `excludedIds` (optimistisch getauscht) heraus, steht sie vor dem nächsten verbliebenen.
  - Die Position wird also vor dem Filtern bestimmt, nicht über den gefilterten Index. Sonst rutscht die Marke beim Tausch um eine Stelle.
  - Das Band zeigt damit bis zu 5 Zellen (Marke + 4). Bei 2/3/4 Spalten bricht die Zeile um; das ist hingenommen.
- **Dialog (Seitenabruf):** Der Dialog legt alle geladenen Seiten zu einer Reihe zusammen. Die Marke steht deshalb einmal an der Stelle `reference_index` dieser Reihe, sobald `reference_index < geladene Anzahl` gilt. Im Fall `reference_index = geladene Anzahl` steht sie nur, wenn **keine** weitere Seite folgt (`!hasNextPage`), dann am Ende. Folgt noch eine Seite, erscheint sie erst nach „Weitere Alternativen laden“ an deren Anfang. Sie erscheint nie doppelt.
  - Noch nicht geladen: Unter dem Ordnungstext steht der Hinweis `Das zu ersetzende Bild folgt weiter hinten in der Reihe.` (`text-xs text-text`). So fehlt die Marke nicht kommentarlos. Nach dem Nachladen verschwindet der Hinweis.
- **Rand:** Liegt das Bezugsbild am Anfang (`reference_index = 0`), steht die Marke als erste Zelle. Am Ende steht sie als letzte. Das Band füllt serverseitig von der anderen Seite auf, hier gibt es nichts weiter zu tun.
- **Leer (`total = 0`):** keine Marke, kein Ordnungstext. Die bestehenden Leertexte bleiben unverändert (`CANDIDATES_NONE_TEXT` im Band, `ALTERNATIVES_NONE_TEXT` im Dialog).
- **`reference_index === null`** (darf mit `photo_id` nicht vorkommen): keine Marke, Kandidaten wie geliefert. Es gibt keine geratene Position.

**Zustände:**
- **Laden:** wie bisher Skeleton-Platzhalter. Die Marke wird nicht vorab gezeigt, weil ihre Position erst mit der Antwort feststeht.
- **Fehler:** wie bisher `Alert` mit „Erneut versuchen“, ohne Marke und ohne Ordnungstext.
- **Leer:** siehe oben.
- **Nachladen (Dialog):** Der Button „Weitere Alternativen laden“ bleibt unverändert.
- **Tausch läuft:** Die Sperre der Kandidaten bleibt wie bisher. Die Marke ist davon nicht betroffen, sie ist nicht bedienbar.

**Albumtauglichkeit je Vorschlag (Systemeinstufung):**
- Bleibt die bestehende `QualityMeter` aus `qualityLevel(ranking?.rank_score ?? null)` mit den Wörtern „Wenig/Bedingt/Gut albumtauglich“ bzw. dem Text für „noch nicht eingestuft“.
- Keine neue Komponente, kein neues Token, kein neues Feld: `PhotoOut.ranking.rank_score` liegt im Frontend-Typ schon vor.
- Abgrenzung zur eigenen Bewertung nach Design-System-Regel „Die Schätzung eines Modells trägt nie die Form der Entscheidung eines Menschen“ (Spec 0428):
  - Die Einstufung bleibt schmuckloser Text mit dem neutralen Punkte-Meter;
  - keine `Badge`, keine Farbe `--accent-2`, kein `book`-Symbol.
- Die menschliche Haltung zeigt im Album-Kontext ausschließlich `AlbumStateBadge` mit den Zustandswörtern des Albums (Spec 0558). Im Album-Entwurf heißt sie also nicht „Album-würdig“; heute zeigen Band und Dialog davon nur „Gestrichen“. Das bleibt so.
- Die Unterscheidung trägt damit über **Wortlaut** („… albumtauglich“ gegen Kennzeichenwort) **und Form** (Text gegen Badge), nicht über Farbe.
- **Im Dialog** bekommt die `QualityMeter` dieselbe Größe wie im Band (`text-xs`). Die `font-normal`-Korrektur im Button bleibt.

**Barrierefreiheit:**
- Raster als `<ol aria-label="Alternativen, zeitlich geordnet">`; die Position ergibt sich aus der Listenreihenfolge.
- Bezugsmarke: `<li aria-label="Wird ersetzt: {relative_path}">`. Das Bild darin trägt `alt=""`, damit der Pfad nicht doppelt vorgelesen wird. Auf der Marke gibt es kein `aria-current`, weil sie weder aktuelle Seite noch aktueller Schritt ist.
- Zugängliche Namen der Aktionen unverändert („Tauschen: {Pfad}“). Die Tab-Reihenfolge läuft nur über die Kandidaten und überspringt die Marke.
- Der Ordnungstext ist sichtbarer Fließtext und keine Live-Region. Der Nachlade-Hinweis im Dialog bekommt ebenfalls keine Live-Region: Er ändert sich nur durch eine Aktion des Nutzers, und die neue Zelle ist im Raster auffindbar.
- Kontrast: `--text-h` bzw. `--text` auf `--surface` sind etablierte Paare. Der Akzentring ist begleitend; die Aussage trägt das Wort.
- 360px: Es kommt keine neue Breite hinzu. Die Marke nutzt die Rasterzelle und es entsteht kein waagerechtes Scrollen.

**Bezug zum Design-System / Ergänzung:**
- Neues Muster „Bezugsmarke in einer geordneten Kandidatenreihe“: nicht bedienbares `<li>` mit derselben Bildfläche, anliegendem `ring-accent` und Wort, ohne Aktion. Die Position wird vor clientseitigem Filtern bestimmt; beim Seitenabruf erscheint sie erst mit der zugehörigen Seite, sonst steht ein Hinweis.
- Nach der Umsetzung kommt das Muster in `specs/architecture/0004-design-system.md` unter „Wiederkehrende Muster“ und in den Skill `design-system`.
- Zu ändernde Kommentare: Dialog-Docstring („hängt an den Motiven“ → zeitliche Ordnung aus dem Backend); Band-Docstring („Höchstens vier Alternativen“ → „die vier zeitlich nächsten“).

**Offene Punkte:**
1. (an architect, technisch) Die Architekturregel „Markierung bei `reference_index − offset ∈ [0, items.length]` je Seite“ ergibt an einer Seitengrenze zwei Treffer, nämlich Ende von Seite k und Anfang von Seite k+1. Hier ist sie als „genau einmal, am Ende nur auf der letzten Seite“ aufgelöst; der Dialog rechnet über die zusammengelegte Reihe. Die Spec-Formulierung im Architekturabschnitt sollte dem folgen.
2. Keine Produktfrage offen. Wortlaut, Position und Abgrenzung der Einstufung folgen aus Story und Design-System (Regeln Spec 0428/0558).

## Security

**Einstufung:** sicherheitsrelevant, kein Blocker. Kein Secret, kein externer Dienst, kein Fremdtext, keine Migration, keine neue Auth-Logik. Geändert wird ein bestehender authentifizierter Lesepfad (`GET /projects/{id}/draft-alternatives`). Er bekommt eine neue Eingabe (`nearest`) und zwei neue Antwortfelder (`offset`, `reference_index`). Mit der Umstellung wechselt die Information, die über die Reihenfolge nach außen geht: Sie liegt nicht mehr im **Motivprofil**, sondern in der **Zeitposition** des Bezugsbildes. Die Auflagen S1/S2/S3/S4/S8 aus dem Docstring des Endpunkts gelten unverändert. Unten sind sie für die neue Form neu gefasst.

### Bedrohungen und Bewertung

- **`reference_index` als Orakel über fremde Bilder.** `reference_index` verrät die Zeitposition des Bezugsbildes relativ zur Restmenge. Für ein Bild aus einem fremden Projekt kann der Wert nie entstehen: Das Bezugsbild wird weiterhin **ausschließlich** über eine `PhotoRanking`-Zeile des jüngsten erfolgreichen Laufs **dieses** Projekts **und** desselben Events aufgelöst (S3). Eine fremde Id scheitert dort. Innerhalb des eigenen Projekts ist `taken_at` jedes Fotos dieses Laufs ohnehin für beide Nutzer sichtbar (`PhotoOut`, Fotoliste). `reference_index` fügt also für ein Bild, das die Auflösung besteht, keine neue Information hinzu. Das Restrisiko hängt damit **allein** an diesem einen Prädikat, so wie bisher das Motivprofil. Wird das Prädikat gelockert (etwa `session.get(Photo, …)` mit nachgelagerter Projektprüfung, Auflösung ohne Event- oder ohne Laufbedingung, `taken_at` aus einer zweiten Abfrage über `Photo` per Id), wird die Zeitposition eines fremden Fotos ablesbar, ohne dass eine Antwortzeile es benennt. Das gilt für `reference_index`, für `offset` (abgeleitet aus `reference_index`) und für die Auswahl des Bandfensters.
- **Existenz-Orakel über den Fehlerpfad.** Neu sind zwei Felder. Unterscheidet sich die Antwort einer gescheiterten Auflösung von der einer unbekannten Id, auch nur in einem dieser Felder, wird daraus ein Existenzorakel.
- **Sichtbarkeit zwischen den beiden Nutzern.** Der Ordnungsschlüssel `(Photo.taken_at, photo_id)` enthält keinen Nutzer. Die **Menge** bleibt je Nutzer (Abzug des eigenen Entwurfs über `own_rating.user_id == current_user.id`). Damit sind `total`, `offset` und `reference_index` Funktionen des **anfragenden** Nutzers. Aus ihnen lässt sich keine Entscheidung des anderen Nutzers ablesen, solange kein zweiter `Rating`-Alias ohne Nutzerbedingung entsteht. Die Cache-Schlüssel-Auflage (Securitykonzept, Abschnitt „Der Album-Entwurf je Nutzer“: Schlüssel muss den Nutzer enthalten) gilt für die neue Antwortform unverändert und hat mit `reference_index` einen dritten Träger.
- **`nearest` als Last-Hebel.** `nearest` bestimmt die Fenstergröße und damit die Hydratation über `_photos_by_id` mit ihren `selectinload`s. Diese muss gedeckelt bleiben wie `limit`.
- **Wegfall der Motivstufe:** Für diesen Endpunkt entfällt das bisherige Motivprofil-Leck über die Sortierung. Die Motivabfrage (`load_effective_strengths`) läuft nur noch über die Seiten-Ids, ist also strenger begrenzt als bisher.

### Auflagen (Muss) mit Nachweis

1. **S4: `nearest` ist deklarativ begrenzt, vor jeder Verwendung.** `nearest: int | None = Query(None, ge=1, le=BAND_MAX)`, wobei `BAND_MAX` eine Modulkonstante `<= 200` ist (Deckel der Hydratation wie `limit`). `0`, negative Werte, Werte über `BAND_MAX`, Kommazahlen und Nicht-Zahlen ergeben `422`. Den Rohwert im `input`-Feld rendert die Oberfläche ausschließlich als React-Textknoten, und er wird nicht geloggt (wie bei `event_id`). *Nachweis:* parametrisierte Tabelle in `TestDraftAlternativesKeys` (`0`, `-1`, `BAND_MAX+1`, `2**63`, `1.5`, `abc` ⇒ `422`) plus Gegenprobe `nearest=BAND_MAX` ⇒ `200`. Ein Test sichert zusätzlich `BAND_MAX <= 200`.
2. **`nearest` ohne `photo_id` scheitert laut statt still** (Muster wie der `draft: None`-Riegel dieses Routers): `nearest` ohne `photo_id` ergibt `422` und keine Abfrage. Wird ein Parameter, der die Seitenbildung umsteuert, still ignoriert, liefert ein fehlerhafter Client eine Liste, die wie ein Band aussieht, aber keines ist. *Nachweis:* `test_nearest_without_a_reference_is_refused`.
3. **Mit `nearest` stammt das Fenster allein vom Server.** Ein vom Client mitgeschicktes `offset`/`limit` hat dann keine Wirkung. Der zurückgegebene `offset` ist `nearest_window_offset(reference_index, total, nearest)` und liegt stets in `[0, max(0, total − nearest)]`. Kein Client-Wert geht in die Fensterrechnung ein. `len(items) <= nearest`. *Nachweis:* Ein Test mit `offset=999999&limit=200&nearest=4` liefert dasselbe Fenster und denselben `offset` wie ohne diese Werte. Ein Test der reinen Funktion deckt die Ränder ab (Anfang, Ende, `total < N`, `total = 0`).
4. **S3: Das Bezugsbild samt `taken_at` kommt aus genau einer Abfrage mit beiden Prädikaten.** `taken_at` des Bezugsbildes wird per Join an **derselben** Abfrage gelesen, die `criterion_scoring_run_id == latest_run_id`, `event_id == event_id` und `photo_id == photo_id` ausgeschrieben trägt. Untersagt sind `session.get(Photo, photo_id)`, ein zweites `select(Photo.taken_at).where(Photo.id == photo_id)` und jede Auflösung, die eine der drei Bedingungen weglässt. Die Kandidatenabfrage holt `Photo.taken_at` per **innerem** Join über `Photo.id == PhotoRanking.photo_id`. Der Join fügt keine Zeile hinzu, und Lauf- **und** Event-Prädikat bleiben die einzige Mengenbindung (S2). *Nachweis:* Ein Test nimmt ein Bezugsfoto aus Projekt B mit einer `taken_at`, die in Projekt A eine andere Position ergäbe. Unter `/projects/A/…?event_id=<A-Event>&photo_id=<B-Foto>&nearest=4` muss die Antwort gleich der Antwort für eine nie vergebene Id sein. Zweiter Fall: ein Foto desselben Projekts aus einem **anderen** Event bzw. einem **älteren** Lauf, mit gleichem Ergebnis.
5. **Ein Fehlerpfad, eine Antwort.** Scheitert die Auflösung des Bezugsbildes, gibt es keinen erfolgreichen Lauf oder ist die `event_id` unbekannt bzw. projektfremd, endet die Anfrage mit `200` und **byte-gleichem** Körper `{"items": [], "total": 0, "offset": 0, "reference_index": null}`. Das gilt unabhängig davon, ob `nearest`, `offset` oder `limit` gesetzt sind. Es gibt keinen Fehlertext und keine Rückspiegelung der Werte. Bei aufgelöstem Bezugsbild **mit** leerer Restmenge ist `reference_index = 0`. Diese Unterscheidung betrifft nur Fotos, die der Anfragende ohnehin sieht, und ist zulässig. *Nachweis:* Ein Test vergleicht die Körper von fremder Id, nie vergebener Id und Foto eines anderen Events auf Gleichheit (nicht nur `items == []`).
6. **`reference_index` und `offset` entstehen aus derselben Kandidatenmenge wie `total` und `items`.** Es gibt keine eigene Zähl- oder Positionsabfrage. `reference_index` ist die Zahl der Kandidaten mit `(taken_at, photo_id) < (ref.taken_at, ref.photo_id)`, also **strikt kleiner**, gerechnet über die volle Restmenge vor dem Schnitt. Eine zweite Abfrage ohne Lauf-Prädikat lieferte eine plausible Position zu einer anderen Menge, und nichts würde rot. *Nachweis:* Ein Test prüft `reference_index` und Fensterinhalt gegen die aus `items` aller Seiten zusammengesetzte Reihenfolge, auch für ein Bezugsbild am Anfang, am Ende und mit gleichem `taken_at` wie ein Kandidat (Tie-Break über die Id).
7. **S8 unverändert: Ohne `photo_id` entfällt nur die Zeitordnung, nie die Bindung.** Ohne `photo_id` sind `reference_index = null` und `offset` das angefragte Client-`offset`. Die Kandidatenabfrage trägt Lauf- und Event-Prädikat. Untersagt bleibt ein Ersatz-Bezugsbild (etwa „das früheste Foto des Events“, das in der Zeitordnung jetzt besonders naheläge). *Nachweis:* `test_without_a_reference_a_foreign_event_yields_nothing` auf die neue Antwortform erweitern und `reference_index is None` prüfen.
8. **Gleiche Reihenfolge für beide Nutzer, Menge je Nutzer.** Der Ordnungsschlüssel enthält weder `user_id` noch eine Bewertung, und es gibt nur einen `Rating`-Alias mit `user_id == current_user.id` in der Join-Bedingung. *Nachweis:* Zwei Nutzer, gleiche Kandidaten, unterschiedliche eigene Entwürfe. Die Reihenfolge der gemeinsamen Fotos ist gleich. Eine `album_worthy`-/`rejected`-Entscheidung des **anderen** Nutzers ändert weder `items` noch `total`, `offset` oder `reference_index` des Anfragenden.
9. **S1 unverändert:** Die Auth-Dependency bleibt ausgeschrieben, und der bestehende 401-Test läuft weiter, jetzt auch mit gesetztem `nearest`. Der Router hat weiterhin kein Vollständigkeitsnetz.
10. **Keine Zeit und keine Position im Log.** Weder `taken_at` noch `reference_index`, `offset` oder `nearest` gehen in eine Logzeile.
11. **Frontend:** Die Markierung des Bezugsbildes wird allein aus `reference_index − offset` positioniert und nur gesetzt, wenn der Wert eine Ganzzahl in `[0, items.length]` ist. Sonst entfällt sie, ohne Fehler und ohne Fallback-Position. Der Wert geht in keinen `key`, in kein `style` als zusammengesetzte Zeichenkette und in keine URL. Der Hinweis „zeitlich geordnet“ ist statischer Text.

### Securitykonzept fortschreiben

- Die Begründung zu S3 im Docstring von `draft_alternatives` wird umgeschrieben, nicht gelöscht: „`photo_id` steuert allein die zeitliche Position (`reference_index`, Bandfenster); ohne das Prädikat würde die Zeitposition eines fremden Fotos ablesbar“. Der Satz zur Motivstufe entfällt.
- Securitykonzept, Abschnitt „Der Album-Entwurf je Nutzer“: Die Cache-Schlüssel-Auflage nennt `reference_index`/`offset` als weitere nutzerabhängige Antwortbestandteile. Die Zeile „Ein optionaler Bezugsparameter darf beim Fehlen nur die Sortierung verlieren, nie die Bindung“ gilt wortgleich weiter.
- Ankerliste: neue Zeile „Das Bezugsbild des Alternativen-Endpunkts samt `taken_at` wird ausschließlich über eine Rangzeile desselben Laufs und desselben Events aufgelöst; jede gescheiterte Auflösung ergibt den byte-gleichen Leerkörper (Spec 0569, S3)“ mit Codestelle `api/photos.py::draft_alternatives` und den Nachweisen aus Auflage 4/5.

**Ausdrücklich geprüft und ohne Befund:** keine Änderung an Auth oder Rollen, keine neue Sichtbarkeit zwischen den Nutzern, kein Fremdtext und keine Persistenz, die Kandidatenmenge ist unverändert, keine neue Abhängigkeit.

## Teststrategie

**Ebenen**
- **Reine Funktionen, pytest (`test_selection.py`):**
  - `order_alternatives_chronologically` deckt AK1, AK2, AK6 und AK7 ab, außerdem die Berechnung von `reference_index`.
  - `nearest_window_offset` deckt AK3 ab.
  - `order_by_quality` deckt AK11 ab; die Fälle ohne Bezugsbild werden übernommen.
  - AK2 wird hier strukturell gezeigt: Die Kandidaten tragen nur `(photo_id, taken_at)`, Motiv und Qualität sind also gar nicht als Eingabe vorhanden.
- **API, pytest mit DB (`test_api_photos.py`):**
  - AK1: Folge über zwei Seiten.
  - AK2: Motiv- und Qualitäts-Gegenprobe am Endpunkt.
  - AK3: `nearest`-Fenster.
  - AK4: `reference_index`/`offset` in der Antwort, `null` ohne `photo_id`.
  - AK7: ein Foto mit `taken_at = last_modified`.
  - AK8: bestehende Mengen-Tests, auf die neue Antwortform umgestellt.
  - AK9: zwei Nutzer.
  - AK11 und AK12.
  - Die Auflagen S2/S3/S4/S8 bleiben, nur angepasst an `DraftAlternativesOut`.
- **vitest:**
  - `api/photos.test.ts`: Der Parameter `nearest` wird gesendet bzw. weggelassen, der Rückgabetyp stimmt.
  - `usePhotos.test.tsx`: Das Band holt eine einzige Seite mit `nearest`, es gibt kein `fetchNextPage`. Band, Dialog und Panel behalten getrennte Schlüssel.
  - `DraftAlternativesDialog.test.tsx` und die Band-Tests: Markierung an `reference_index − offset`, Wortlaut (AK5), Albumtauglichkeit getrennt von „Album-würdig“ (AK10), keine zweite Sortierung im Frontend. Die Band-Tests laufen über `AlbumDraftPage.test.tsx` oder eine neue `DraftAlternativesBand.test.tsx`.
- **Bestehende Strukturwächter** (`designSystem.contract.test.ts`, `albumSelection.structure.test.ts`) bleiben unverändert grün.

**Wichtigste Edge Cases**
- **Gleichstand:**
  - Drei Kandidaten mit gleichem `taken_at`, geprüft über alle Permutationen.
  - Das Bezugsbild hat dasselbe `taken_at` wie Kandidaten mit kleinerer und mit größerer Id. `reference_index` zählt dann genau die kleineren Ids.
- **Randfenster** (`total = 10`): `reference_index` gleich 0, 1, 2, 8, 9 und 10 ergibt `offset` 0, 0, 0, 6, 6 und 6. Mit `reference_index = 5` ergibt sich `offset = 3`, also 2 vor und 2 nach dem Bezugsbild.
- **total < 4:** `total` gleich 1, 2 und 3 ergibt `offset = 0` und alle Bilder. Die Markierung steht korrekt, auch ganz vorn (`reference_index = 0`) und ganz hinten (`reference_index = total`).
- **total = 0:** `items = []`, `reference_index = 0`. Im Frontend erscheint der Leertext und keine Markierung.
- **Markierung bei Pagination:**
  - Liegt `reference_index` auf Seite 2, zeigt Seite 1 keine Markierung, sondern den Hinweis „Das zu ersetzende Bild folgt weiter hinten in der Reihe.“; nach dem Nachladen erscheint die Markierung genau einmal, und der Hinweis verschwindet.
  - Fällt `reference_index` genau auf das Ende der geladenen Reihe (`= offset + items.length`) und folgt noch eine Seite, steht die Markierung **nicht** am Ende von Seite 1, sondern der Hinweis. Nach dem Nachladen steht sie genau einmal am Anfang von Seite 2. Folgt keine Seite mehr, steht sie am Ende.
  - **Technische Festlegung:** Die Marke wird über alle geladenen Seiten genau einmal gerendert. Der Wert `items.length` ist inklusiv, darum wäre an einer Seitengrenze sonst eine doppelte Markierung möglich.
- **Markierung bei `excludedIds`:** Ein optimistisch ausgeblendetes Bild vor dem Bezugsbild darf die Markierung nicht falsch verschieben. Die Position muss sich nach dem verbleibenden Vorgänger richten, nicht nach dem rohen Index. Der Test prüft die Marke direkt nach dem richtigen Nachbarn. Das Fenster darf sich dabei verkürzen, eine Nachfüllung erfolgt nicht.
- **Beide Nutzer:**
  - Nutzer A und B mit identischer Restmenge erhalten eine identische Folge.
  - Hat A ein Bild in seinem Entwurf, fehlt es nur bei A. Die übrigen Bilder behalten die relative Ordnung. `reference_index` unterscheidet sich zulässig je nach Restmenge.
- **Unabhängigkeit von Qualität:** Ein Kandidat mit `rank_score = None` steht zeitlich korrekt und nicht am Ende.
- **Gegenprobe Endpunkt:** Liefert die DB die Zeilen in Id-Reihenfolge, muss die Antwort davon abweichen (`order != sorted(ids)`). Sonst wäre der Test leer.

**Entfallende bzw. umzuschreibende Tests:**

- backend/tests/test_selection.py::TestTheOrderOfTheAlternatives::test_a_shared_motif_comes_before_a_better_picture_without_one
- …::test_a_candidate_without_quality_and_with_a_shared_motif_beats_every_stranger
- …::test_a_quality_of_zero_is_not_a_missing_quality (nur der Zweig mit Bezugsbild; die Aussage zu 0.0 vs. None wandert in einen order_by_quality-Fall)
- …::test_three_shared_motifs_do_not_beat_one
- …::test_the_motif_boundary_of_the_grouping_is_inclusive
- …::test_the_input_carries_no_time_at_all (wird ins Gegenteil gedreht: Der Kandidat trägt taken_at, aber weder quality noch motif_strengths)
- …::test_a_reference_without_a_carried_motif_leaves_a_plain_quality_order
- …::test_a_tie_breaks_over_the_smaller_photo_id_in_every_permutation (Motiv-/Qualitäts-Aufbau entfällt; wird als Gleichstand bei taken_at neu geschrieben)
- Umgezogen statt gestrichen (auf order_by_quality/chronologisch umgestellt): test_an_empty_candidate_list_stays_empty, test_the_reference_is_never_among_its_own_alternatives, test_without_a_reference_a_shared_motif_does_not_jump_ahead, test_without_a_reference_every_permutation_gives_quality_none_last_then_smaller_id
- backend/tests/test_api_photos.py::test_the_order_is_the_one_of_order_alternatives (wird ersetzt durch einen Test, der die zeitliche Ordnung am Endpunkt prüft)
- backend/tests/test_api_photos.py::test_temporal_proximity_is_not_a_sorting_criterion (Aussage wird ins Gegenteil gedreht)
- frontend/src/components/DraftAlternativesDialog.test.tsx 'keeps the ORDER OF THE ANSWER and does not sort again': bleibt, nur der Kommentar „hängt an den Motiven“ wird angepasst
- Mitzuprüfen: Alle Tests, die den Endpunkt aufrufen und `PhotoListOut` erwarten, darunter test_the_alternatives_response_is_identical_before_and_after_a_joint_decision und test_without_a_reference_*: Die Antwortform wird angepasst, die Erwartung bleibt.

## Entscheidungen

- „Ohne Aufnahmezeitpunkt am Ende“ ist im Datenmodell nicht erreichbar (`taken_at` NOT NULL, Rückfall auf Dateizeit). Daniel hat die Umformulierung bestätigt: Solche Bilder ordnen sich nach ihrer Dateizeit ein (AK7); keine Datenmodelländerung.
- Bandgröße bleibt `BAND_SIZE = 4` (2 davor, 2 danach, Randauffüllung).
- Reihenfolge und Bezugsposition berechnet allein der Server (`reference_index`); das Frontend sortiert nie.
- Das Hinzufügen-Panel (ohne `photo_id`) bleibt nach Qualität geordnet.
- Ordnungstext ohne Pfeilzeichen (Screenreader); AK5 entsprechend auf den UX-Wortlaut gezogen.
- `0002-testkonzept.md` bleibt unverändert.

## Offene Fragen

- keine

## Out of Scope

- Ordnung im Hinzufügen-Panel.
- Speichern der Zeitquelle (EXIF vs. Datei).
- Änderung der Kandidatenmenge.
