# 0489 - Fotoübersicht mit vollständig sichtbaren Bildern

**Status:** Accepted
**Erstellt:** 2026-09-14
**Bezug:** [GitHub-Issue #489](https://github.com/TheRealKoller/photosort/issues/489), ADR [`0110`](../decisions/0110-seitenverhaeltnis-als-serverdatum-und-rasterkachel-neben-der-fotokarte.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Die Story berührt beide Hälften des Systems
(neue Spalte samt Migration und Nachhol-Runde im Backend, neue Kachel und neues Layout im
Frontend) und trägt sieben benannte Sicherheitsauflagen; keine davon lässt sich streichen, ohne
eine Zusicherung zu verlieren.

## Ziel

Die Übersicht aller Fotos eines Projekts soll einen schnellen Überblick geben und dabei jedes Bild
vollständig zeigen. Heute werden die Bilder auf ein quadratisches Format beschnitten, und jede
Kachel trägt so viel Beiwerk, dass der Blick nicht beim Motiv bleibt. Beides zusammen macht die
Ansicht anstrengend — gerade am Telefon, wo vor dem ersten Foto zwei Zeilen Filter stehen und unter
den Bildern leerer Platz bleibt.

Zielgruppe sind die beiden Nutzer des Projekts beim Durchsehen eines frisch eingelesenen Bestands:
Sie wollen erkennen, was da ist, in welchem Zustand ein Bild ist, und mit einem Griff in die
Einzelansicht wechseln.

## User Story

Als Nutzer möchte ich alle Fotos eines Projekts in einer ruhigen Übersicht sehen, in der kein Bild
beschnitten ist und der Zustand jedes Bildes auf einen Blick erkennbar bleibt, damit ich den
Bestand schnell erfassen und gezielt einzelne Bilder öffnen kann.

## Akzeptanzkriterien

- [x] AK1 — Kein Bild der Übersicht wird beschnitten; jedes Foto ist vollständig sichtbar.
- [x] AK2 — Die Bilder stehen in zeilenweise justierten Reihen. Innerhalb einer Zeile haben alle
      Bilder dieselbe Höhe; die Summe der Bildbreiten und der Zwischenräume einer Zeile entspricht
      **exakt** der verfügbaren Breite, und ein verbleibender Rundungsrest liegt auf dem letzten
      Bild der Zeile. Die letzte, unvollständige Zeile wird **nicht** aufgezogen: sie behält die
      Zielzeilenhöhe und steht linksbündig. Um ein einzelnes Bild entsteht kein leerer Rand.
- [x] AK3 — Im Ruhezustand trägt ein Bild **genau zwei** Zeichen, gemeinsam in einer Ecke: einen
      Stern und einen Punkt. Weitere Ecken-Elemente gibt es in dieser Ansicht nicht — der
      Info-Auslöser der Bewertungsdetails (`CriterionDetailsPopover`) und der Motiv-Marker
      (`MotifAssessmentMarker`) entfallen in der Übersicht ersatzlos.
- [x] AK4 — Der Stern zeigt allein durch seine An- oder Abwesenheit, ob das Bild ein **eigener**
      Favorit ist. Kein leerer Stern als Gegenzustand: Er steht da oder er ist nicht im Dokument.
      Das Favoriten-Kennzeichen einer anderen Person erzeugt keinen Stern.
- [x] AK5 — Der Punkt zeigt die Albumentscheidung: **gefüllt** bei eigener Entscheidung
      (album-würdig oder verworfen), als **Ring** bei noch nicht bestätigtem Vorschlag, **gar
      nicht**, wenn weder das eine noch das andere vorliegt. Füllung und Ring desselben Zustands
      benutzen denselben Farbwert, sodass auch bei einem Vorschlag erkennbar bleibt, wofür
      vorgeschlagen wird.
- [x] AK6 — Ein verworfenes Bild tritt zusätzlich optisch zurück. Der Rücktritt liegt ausschließlich
      auf der Bildfläche, nie auf dem Kachelkörper und nie auf den beiden Zeichen; der Zustand ist
      dadurch auch ohne Farbwahrnehmung erkennbar.
- [x] AK7 — Dateiname und weitere Angaben stehen nicht dauerhaft in der Übersicht. Sie sind im
      Ruhezustand **nicht im Dokument** und erscheinen erst auf Anforderung als Zeile bündig an der
      Unterkante der Bildfläche; die Zeile überdeckt höchstens **ein Viertel** der Bildhöhe.
- [x] AK8 — Die Zeile wird an einem Gerät mit feinem Zeiger und Hover-Fähigkeit durch Überfahren
      ausgelöst, sonst durch einen Druck von mindestens **500 ms**. Ein kürzerer Druck öffnet die
      Detailansicht und blendet die Zeile nicht ein; ein langer Druck blendet die Zeile ein und
      öffnet die Detailansicht **nicht**.
- [x] AK9 — Ein Klick oder Tippen auf ein Bild öffnet weiterhin die bestehende Detailansicht, unter
      Beibehaltung des aktiven Filters.
- [x] AK10 — Weitere Fotos werden beim Weiterscrollen nachgeladen, ohne dass eine Schaltfläche
      gedrückt werden muss; eine Schaltfläche zum Nachladen gibt es nicht mehr. Die Ansicht nennt
      durchgehend, wie viele Bilder von wie vielen geladen sind, und zeigt an derselben Stelle einen
      Fehler samt Wiederholmöglichkeit, wenn das Nachladen scheitert.
- [x] AK11 — Die bestehenden Filter bleiben unverändert nutzbar. Bei 360 px erzeugt die Seite kein
      horizontales Scrollen des Dokuments; die Filterleiste ist dort ein eigener horizontaler
      Scrollbereich und scrollt nachweislich selbst. Die beiden Zeichen bleiben erkennbar; die
      Kachel selbst bleibt auf 44 × 44 px treffbar.
- [x] AK12 — Der Modus zum Sichten des erkannten Ausschusses (`?gate=1`) funktioniert unverändert
      weiter. „Übernehmen" und „Vergleichen" erscheinen **ausschließlich** im Gate-Modus dauerhaft
      unter dem Bild, in der normalen Übersicht gar nicht.
- [x] AK13 — Die übrigen Foto-Ansichten (Kuratierung, gemeinsame Endauswahl, Duplikatsvergleich)
      bleiben unverändert: ihre bestehenden Tests bleiben ohne jede Anpassung grün, und `PhotoCard`
      behält genau ihre drei Aufrufstellen.

## Datenmodell-Bezug

`Photo` bekommt eine nullbare Spalte `aspect_ratio: float | None` (Breite ÷ Höhe des **gezeigten**
Bildes, also nach EXIF-Orientierung). `NULL` ist ein regulärer Zustand: Fotos aus dem Bestand
tragen ihn, bis die Nachhol-Runde greift, und jeder Lesepfad beantwortet ihn fehlerfrei. Die
Migration ist additiv und ohne Datenwanderung. Siehe [`docs/architecture.md`](../../docs/architecture.md),
Abschnitt Datenmodell.

## Architektur / Umsetzung

Getragen von ADR [`0110`](../decisions/0110-seitenverhaeltnis-als-serverdatum-und-rasterkachel-neben-der-fotokarte.md):
Das Seitenverhältnis wird persistiert und mit jedem Foto ausgeliefert, und die Rasterkachel wird
eine eigene Komponente neben `PhotoCard`. Eine additive Alembic-Migration kommt hinzu, eine neue
Abhängigkeit **nicht** — das justierte Raster ist eine reine Funktion im Frontend.

### Betroffene Dateien

**Backend**

| Datei | Änderung |
|---|---|
| `backend/src/photosort/thumbnails.py` | `aspect_ratio_of(image) -> float \| None` (nach `exif_transpose`, Grenzen `0.05…20.0`) und `aspect_ratio_of_cached_thumbnail(path)`. `generate_variants` gibt das Verhältnis statt `bool` zurück (`None` = nicht erzeugt). |
| `backend/src/photosort/models.py` | `Photo.aspect_ratio: Mapped[float \| None]`. |
| `backend/alembic/versions/<kennung>_seitenverhaeltnis.py` | **neu.** Nullbare Spalte, keine Datenwanderung. Revisionskennung über `scripts/nummern.py migration <slug>`. |
| `backend/src/photosort/worker.py` | `ScanExifResult.aspect_ratio`; `_generate_thumbnails` reicht den Rückgabewert durch; `_process_scan_block` schreibt ihn im sequentiellen Teil. Neu: die Nachhol-Runde zu Beginn von `run_project_scan` über die Fotos des Projekts mit `aspect_ratio IS NULL`, gelesen aus dem lokalen Vorschaubild. |
| `backend/src/photosort/api/photos.py` | `PhotoOut.aspect_ratio: float \| None = None`, gefüllt in `_to_photo_out` — auf **allen** Lesepfaden, nicht nur dem der Rasteransicht. |
| `backend/src/photosort/demo_state.py` | `_IMAGE_SIZE` wird zu einem deterministisch aus `slug`/`index` gewählten Format aus einem festen Satz (hoch, quer, breit, quadratisch). Die Zusage der Byte-Identität zweier Läufe bleibt. |

**Frontend**

| Datei | Änderung |
|---|---|
| `frontend/src/utils/justifiedRows.ts` | **neu.** Reine Funktion: Verhältnisse + Containerbreite + Zwischenraum + Zielzeilenhöhe + Untergrenze → Zeilen mit ganzzahliger Breite je Bild und gemeinsamer Zeilenhöhe. |
| `frontend/src/hooks/useElementWidth.ts` | **neu.** Containerbreite über `ResizeObserver`. Die Breite kommt aus `entry.contentRect.width`, **nie** aus dem Element — in jsdom sind `clientWidth` und `getBoundingClientRect().width` konstant 0, und ein Raster, das daraus liest, ist im Komponententest nicht prüfbar. |
| `frontend/src/components/PhotoGridTile.tsx` | **neu.** Die Rasterkachel: Bildfläche im eigenen Verhältnis, Zeichenplättchen in der oberen Ecke, eingeblendete Zeile über dem unteren Bildrand. Benutzt `PhotoCard` **nicht**. |
| `frontend/src/api/types.ts` | `PhotoOut.aspect_ratio: number \| null`. |
| `frontend/src/pages/PhotoGridPage.tsx` | Spaltenraster → justiertes Zeilenraster, Nachladen am Sichtbarkeitsanker statt an der Schaltfläche, Zählzeile „x von y geladen", Info-Auslöser und Motiv-Marker entfallen, Gate-Aktionen nur noch bei `gate=1`. |
| `frontend/src/designSystem.contract.test.ts` | Je ein fundstellengenauer Eintrag in der `opacity-*`- und der `rounded-full`-Freigabe für die neue Kachel. |
| `frontend/src/components/PhotoCard.tsx` und die drei `*PhotoTile` | **unverändert.** |

**Prüfstack und Doku**

| Datei | Änderung |
|---|---|
| `e2e/tests/grid-columns.spec.ts` | Der Foto-Teil misst nicht mehr „2/3/4 gleiche Spalten", sondern die Zusagen des justierten Rasters. Der Duplikat-Teil bleibt. |
| `e2e/tests/popover-position.spec.ts` | Braucht eine Ersatzroute: Der Popover-Auslöser verschwindet aus der Fotoübersicht (AK3). |
| `docs/architecture.md` | `aspect_ratio` samt Nachhol-Regel unter **Photo**; die neue Kachel neben `PhotoCard` in der Komponentenübersicht. |
| `specs/architecture/0004-design-system.md` | Zwei Festlegungen der Foto-Karte werden eingeschränkt, ein Eintrag kommt hinzu (siehe UI/UX). |
| `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md` | Fortschreibung (siehe Teststrategie und Security). |
| `design/penpot/views.json` | Die Lücken der Ansicht `fotos` beschreiben die Fotokarte (`behaelter`, `daempfung`, `eckenoverlay`, `textkuerzung`) und gelten für die Rasteransicht nicht mehr; sie werden neu gefasst. Der Strukturtest schlägt dabei nicht an, das Soll-Dokument würde also still falsch. |

### Datenfluss

Der Scan kennt das Bild nach `exif_transpose` bereits: `generate_variants` liefert sein Verhältnis
mit zurück, `_fetch_and_thumbnail` trägt es in `ScanExifResult`, und `_process_scan_block` schreibt
es dort, wo auch `taken_at` geschrieben wird. Kein zusätzlicher Abruf, kein zweites Dekodieren.

Für den Bestand läuft zu Beginn jedes Projekt-Scans die Nachhol-Runde: Fotos mit
`aspect_ratio IS NULL` bekommen ihr Verhältnis aus dem **lokal zwischengespeicherten Vorschaubild**
— ohne Netz und ohne das Original. Fehlt die Cache-Datei, bleibt der Wert `NULL`; der nächste Scan
versucht es erneut. Das so gelesene Verhältnis ist wegen der Ganzzahl-Skalierung beim Erzeugen der
Vorschau **nicht exakt** das des Originals; zugesichert ist es nur innerhalb einer benannten
Toleranz.

Im Frontend fließt `aspect_ratio` aus der bereits bestehenden `usePhotoSequenceQuery` (unverändert)
zusammen mit der gemessenen Containerbreite in `justifiedRows`. Heraus kommen je Bild eine ganze
Pixelbreite und je Zeile eine Höhe; die Kacheln stehen als **eine** flache Liste
(`<ul class="flex flex-wrap">`, ein `<li>` je Foto) mit diesen Maßen als Inline-Stil. Die Zeilen
entstehen dadurch, dass die Breiten einer Zeile plus Zwischenräume **exakt** die Containerbreite
ergeben — der Rundungsrest geht auf das letzte Bild der Zeile. Ein Foto ohne `aspect_ratio` wird
mit 3:2 eingeplant.

### Entwurfsentscheidungen

- **Eine eigene Kachel statt einer Ausprägung der Fotokarte** (ADR 0110 Punkt 5). Die drei übrigen
  Foto-Ansichten bleiben dadurch nicht nur fachlich, sondern im Code unberührt.
- **Flache Liste mit gerechneten Breiten statt eines Elements je Zeile.** Ein `<ul>` je Zeile
  zerlegte eine Liste von Fotos in viele Listen; der Bildschirmleser zählte je Zeile neu, und der
  Auffinde-Ausdruck des Prüfstacks (`listitem` mit Foto-Link) bräche — daran hängen vier E2E-Specs.
- **Das Nachladen hängt an einem Sichtbarkeitsanker** (`IntersectionObserver` auf einem Element
  unter dem Raster), nicht an einem Scroll-Ereignis. Die Zählzeile „x von y geladen" ist zugleich
  die Fehlerstelle: Scheitert das Nachladen, steht dort die Meldung mit „Erneut versuchen".
- **Zeichenplättchen und eingeblendete Zeile stehen auf der undurchsichtigen Fläche `--overlay`**,
  nicht auf einer teildeckenden. Über einer Bildfläche ist ein Kontrast mit Deckkraft statisch
  nicht nachrechenbar, und der Vertragstest weist Deckkraft-Modifikatoren auf Farb-Utilities
  zurück.
- **Die Bedeutung der Zeichen steht zusätzlich als unsichtbarer Text in der Kachel.** Der Stern und
  der Punkt ersetzen das bisherige beschriftete Kennzeichen; ohne diesen Text verlöre die Ansicht
  ihre Aussage für Bildschirmleser.

## UI/UX

**Stand:** ausgearbeitet · **Penpot-Seite:** Ansicht — Fotos · **Schlüssel:** `fotos`

### Layout

Ein justiertes Zeilenraster der Projektfotos ohne Beschnitt, als eine flache Liste mit gerechneten
Inline-Maßen je Kachel. Am Zeigegerät zeigt die Filterleiste alle Einträge ohne Scroll. Am Telefon
(< 640 px) ist sie ein **eigener** horizontaler Scrollbereich, einzeilig und am Rand angeschnitten;
die Seite selbst scrollt nie seitlich.

### Zustände

- **Gefüllt:** das justierte Raster.
- **Leer:** keine Fotos im Projekt oder kein Treffer nach Filter — eine Mitteilung statt eines
  Rasters. Der Nachlade-Anker steht dort **nicht**, sonst löste er sofort einen Abruf aus.
- **Ladend:** Skeleton-Platzhalter im gerechneten Zeilenbild.
- **Nachladend:** die Zählzeile unter dem Raster nennt den Fortschritt.
- **Fehler beim Nachladen:** an der Stelle der Zählzeile eine Meldung mit „Erneut versuchen"; die
  bereits geladenen Bilder bleiben sichtbar.

### Die zwei Zeichen

Gemeinsam in der oberen Ecke, nebeneinander in einem `flex gap-1`-Container, auf der
undurchsichtigen Fläche `--overlay`.

- **Stern** — vorhanden genau dann, wenn das Bild ein eigener Favorit ist (`--accent`). Kein leerer
  Stern als Gegenzustand.
- **Punkt** — gefüllt bei eigener Entscheidung, als Ring bei offenem Vorschlag, gar nicht ohne
  beides. Farbe in beiden Formen dieselbe: album-würdig `--accent-2`, verworfen `--danger`.

Unter Graustufen sind Favorit und Album-würdig als Flächen nicht unterscheidbar; die Unterscheidung
trägt hier über die **Silhouette** (Stern gegen Kreis), nicht über die Farbe. Verworfen trennt sich
zusätzlich über die gedämpfte Bildfläche.

Jeder Zustand steht zusätzlich als unsichtbarer Text in der Kachel („Favorit", „Album-würdig
vorgeschlagen", „Verworfen").

### Interaktion

- **Kurzer Klick/Tipp:** Detailansicht, unter Beibehaltung des aktiven Filters.
- **Überfahren** (Gerät mit `(hover: hover) and (pointer: fine)`) **oder Fokus:** die Angabenzeile
  erscheint.
- **Druck ≥ 500 ms** auf einem Gerät ohne feinen Zeiger: die Angabenzeile erscheint, **ohne** zu
  navigieren.
- **Tastatur:** Fokus zeigt die Zeile, `Enter` öffnet die Detailansicht. Fokusreihenfolge folgt der
  DOM-Ordnung des Rasters; die Filterleiste kommt davor.

### Barrierefreiheit

Die Kachel bleibt auf 44 × 44 px treffbar. Die beiden Zeichen sind **keine** Bedienelemente — sie
tragen keine eigene Trefferfläche und keinen eigenen Fokus. Kontrast wird gegen `--overlay`
gemessen, nicht gegen das Bild. Jede Kachel ist ein `<li>` mit genau einem Link auf
`/photos/<id>`.

### Was am Design-System zu ändern ist

In `specs/architecture/0004-design-system.md`, Eintrag `components/PhotoCard.tsx`:

1. **„Sie lebt genau einmal und wird von allen drei Foto-Ansichten benutzt (Raster, Kuratierung,
   Vergleich)"** — die Aufzählung wird auf Kuratierung, gemeinsame Endauswahl und
   Duplikatsvergleich geändert; die Rasteransicht fällt **heraus**.
2. **„Das Kennzeichen sitzt im Kartenkörper, nicht in der Bildecke"** — gilt unverändert **für die
   Fotokarte** und ausdrücklich nicht für die Rasterkachel. Die Begründung (ein Textbadge braucht
   mehr Platz, als die Ecke hat) trägt genau deshalb: Die Rasterkachel trägt kein Textbadge,
   sondern zwei Zeichen.
3. **Neuer Eintrag `components/PhotoGridTile.tsx`:** keine feste Bildform, kein Kartenkörper, keine
   Fußzeile; genau zwei Zeichen im Ruhezustand auf einem Plättchen in der oberen Bildecke; Angaben
   erst auf Anforderung; die Dämpfung sitzt auf der Bildfläche, nie auf den Zeichen. Der Punkt
   trägt zusätzlich die Ringform für Vorschläge — eine Unterscheidung, die `PhotoCard` nicht kennt.

Unverändert gilt die Kollisionsregel: Die Ausprägung `destructive` steht auf keiner Ansicht, die
Bewertungs-Kennzeichen zeigt — die Gate-Aktionen tragen sie nicht.

## Security

Sicherheitsrelevant, kein Blocker: kein Secret, kein neuer Endpunkt, keine Änderung an Auth und
keine Änderung an der Sichtbarkeit zwischen den beiden Nutzern. Neu sind drei Dinge — eine
**Verarbeitungsphase, die dem Scan-Lauf vorausläuft**, ein **zweiter Lesepfad in das
Vorschaubild-Verzeichnis**, und die **erste Stelle im Frontend, die einen gerechneten Wert in einen
Inline-Stil schreibt**.

**S1 — Die Nachhol-Runde schreibt `last_progress_at` an eigenen Commit-Punkten.** Sie arbeitet in
Blöcken; je Block wird committet und `ScanRun.last_progress_at` gesetzt. Geladen werden je Foto nur
`id` und `etag`, nie ganze `Photo`-Objekte über den gesamten Bestand. Bricht bei Verletzung:
`reap_stalled_runs` setzt einen Lauf, dessen Nachhol-Runde über 15 Minuten (`STALL_THRESHOLD`) ohne
Stempel arbeitet, auf `FAILED` — und bricht die Coroutine dabei bewusst nicht ab. Der Scan liefe
weiter, während die Oberfläche „fehlgeschlagen" sagt. Die Runde läuft vor Phase 1 und damit vor dem
ersten Stempel, den `run_project_scan` heute setzt.

**S2 — Je Foto isoliert, mit bewusst breitem `except Exception`.** Eine fehlende, beschädigte oder
nicht dekodierbare Cache-Datei lässt `aspect_ratio` auf `NULL` und die Runde weiterlaufen. Eine
engere Exception-Liste ist untersagt: `PIL.Image.DecompressionBombError` erbt nicht von `OSError`
und liefe durch. Bricht bei Verletzung: ein einzelnes Foto reißt den gesamten Projekt-Scan — und
zwar vor jeder anderen Arbeit, also bei jedem Versuch erneut.

**S3 — Gelesen wird der Kopf der Datei, nicht ihr Bildinhalt.**
`aspect_ratio_of_cached_thumbnail` entnimmt `Image.open(...).size` innerhalb eines `with`-Blocks
und ruft weder `load()` noch `exif_transpose` auf — die Cache-Variante ist beim Schreiben bereits
gedreht worden und trägt keinen Orientierungs-Tag. Bricht bei Verletzung: Dekodieren zieht die
volle Pixelfläche in den Speicher, ein offen gelassener Dateizeiger erschöpft über zehntausende
Bestandsfotos die Dateizeiger des Worker-Prozesses.

**S4 — Der Pfad entsteht ausschließlich über `thumbnails.thumbnail_path`/`variant_path`.** Der
`etag` kommt vom WebDAV-Server, ist damit Fremdtext, und geht dort nur in `cache_key` als
SHA-256-Eingabe ein — nie in einen Dateinamen. Untersagt bleibt jede zweite Pfadbildung, die `etag`
oder `relative_path` als Namensbestandteil verwendet. Bricht bei Verletzung: ein `etag` mit `../`
liest aus einem beliebigen Pfad außerhalb des Cache-Verzeichnisses.

**S5 — Die Bereichsprüfung wird als Einschluss geschrieben: `0.05 <= r <= 20.0`.** Die Umkehrform
(`not (r < 0.05 or r > 20.0)`) ist untersagt. Bricht bei Verletzung: `NaN` und `inf` sind gegen
jeden Vergleich falsch und passieren die Umkehrform. Ein `NaN` in der Spalte ist kein Fehler eines
Fotos, sondern der Antwort: `json.dumps` schreibt das Literal `NaN`, `JSON.parse` weist den Körper
ab — die gesamte Fotoliste des Projekts fällt aus.

**S6 — Das gerechnete Maß geht als Zahl in eine gewöhnliche CSS-Eigenschaft.** `width`/`height`
entstehen aus Arithmetik der reinen Rasterfunktion und werden als `style={{ width: n }}` gesetzt.
Untersagt: der `style`-Wert als aus API-Daten zusammengesetzte Zeichenkette, eine
CSS-Custom-Property als Träger des Wertes, jede Verwendung in einem `url()`-Kontext,
`dangerouslySetInnerHTML`. Angriffsmodell: Eine Custom-Property nimmt anders als eine gewöhnliche
Eigenschaft nahezu beliebige Token-Folgen auf und trägt sie über `var()` an eine Stelle, an der sie
wieder als CSS gelesen werden — der einzige Weg, auf dem aus einem Zahlenfeld doch ein
Einschleusungsweg würde.

**S7 — Das Nachladen hat eine Sperre und ein Ende.** Ein Abruf gleichzeitig; kein neuer Abruf,
solange einer offen ist oder die letzte Antwort kürzer als die angeforderte Seite war. Bricht bei
Verletzung: Der Beobachter feuert bei jedem Scroll-Schritt und erzeugt einen Anfragensturm — je
Antwort bis zu 200 Fotos samt ihrer Bildabrufe — gegen den Homeserver, auf dem PhotoSort und
OpenCloud zusammen laufen.

**Geprüft und ohne Befund:** `aspect_ratio` gibt auf keinem Lesepfad etwas Neues preis (Projekte
tragen keine Nutzerbindung, jeder angemeldete Nutzer darf jedes Foto ohnehin abrufen; getrennt ist
die *Bewertung*, nicht die *Sichtbarkeit*). Die Autorisierung bleibt unverändert — `_to_photo_out`
bekommt ein Ausgabefeld, keinen geänderten Parameter. Die Migration ist additiv und nullbar.

Das Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`) wird im selben PR
fortgeschrieben: eine neue Unterrubrik unter „Angriffsflächen" (Verarbeitungsphase vor dem ersten
Fortschrittsstempel; NaN-feste Einschlussschreibweise als projektweites Muster; die
Inline-Stil-Grenze aus S6) plus je eine Zeile in der Ankerliste für S1, S4 und S5 mit der brechenden
Testfunktion.

## Teststrategie

Der Schwerpunkt liegt auf der Unit-Ebene: `utils/justifiedRows.ts` ist eine reine Funktion ohne DOM
und trägt die Zusagen „kein Beschnitt", „gemeinsame Zeilenhöhe", „bündiges Zeilenende" und
„Rundungsrest auf dem letzten Bild" allein — tabellengetrieben, inklusive unbekanntem Verhältnis
(3:2-Ausfallrichtung), Containerbreite 0, einer nicht glatt aufgehenden Breite und der
unvollständigen letzten Zeile.

Auf Komponentenebene werden die Zustandszeichen tabellengetrieben über alle Kombinationen geprüft,
paarweise verschieden und über zugängliche Namen bzw. semantische `data-*`, nie über Klassennamen.
Die Interaktion braucht **vier** Fälle: Überfahren mit und ohne hover-fähiges Gerät, Druck oberhalb
und unterhalb der 500-ms-Schwelle, jeweils mit der Negativ-Assertion zur Navigation. Zeit kommt über
Fake-Timer, nie über echtes Warten.

`ResizeObserver` und `IntersectionObserver` fehlen in jsdom 29.1.1 und bekommen **treibbare** Stubs
— die Containerbreite wird in den Test hineingegeben, nicht aus dem DOM gelesen (dort ist sie
konstant 0). Daraus folgt für die Umsetzung: `useElementWidth` liest die Breite aus dem
Observer-Eintrag.

Im Vertragstest kommen zwei fundstellengenaue Freigaben hinzu (`opacity-*` für die gedämpfte
Bildfläche, `rounded-full` für den Punkt) sowie zwei statische Regeln: die neue Kachel enthält weder
`object-cover` noch `aspect-square`, und der Zwischenraum-Wert existiert nur einmal — ein Test hält
die `gap-3`-Utility und die Rechenkonstante aneinander.

Im Backend wird das Seitenverhältnis auf Unit-Ebene geprüft (Orientierung, Gültigkeitsband, `None`
in allen Fehlerfällen) und auf Integrationsebene an beiden Schreibwegen und **allen fünf**
Lesepfaden. Die Nachhol-Runde braucht drei eigene Fälle: sie überschreibt keinen gefüllten Wert, sie
gibt bei fehlender Cache-Datei nicht dauerhaft auf (über einen Spion nachgewiesen, nicht über den
Endzustand), und sie berührt kein Netz. Das aus dem Vorschaubild gelesene Verhältnis wird gegen eine
**Toleranz** geprüft, nie auf Gleichheit mit dem Scan-Weg. Der Demo-Bestand muss deterministisch
mindestens drei verschiedene Verhältnisse liefern, darunter ein Hoch- und ein Breitformat, und seine
Byte-Identität über zwei Läufe behalten.

Auf E2E-Ebene wird `grid-columns.spec.ts` für den Foto-Teil neu gefasst (gemeinsame Zeilenhöhe,
bündiges Zeilenende, Kastenverhältnis gegen `naturalWidth`/`naturalHeight`, zwei Breiten mit
verschiedenen Zeilenhöhen) — mit erneutem Rot-Nachweis im Pull Request; der Duplikat-Teil bleibt.
Dazu das echte Nachladen beim Scrollen und die Filterleiste als eigener Scrollbereich, belegt über
**zwei** Messungen (die Leiste scrollt, das Dokument nicht). `popover-position.spec.ts` braucht eine
Ersatzroute. Die Kachel bleibt ein `<li>` mit genau einem Foto-Link — daran hängen vier E2E-Specs,
und ein eigener Komponententest sichert die Struktur ab, damit ein Bruch in `vitest` auffällt.

Der Umbau macht 13 Fälle in `PhotoGridPage.test.tsx` und 5 in `test_thumbnails.py` rot; sie werden
umgeschrieben, nicht gestrichen. Die Fälle zu „Übernehmen"/„Vergleichen" **ziehen in den Gate-Modus
um** — blieben sie stehen, wo sie sind, wären sie ab sofort nicht mehr rot zu bekommen. Die Tests
von `PhotoCard` und den drei `*PhotoTile` bleiben ohne jede Anpassung grün; ein Wächter hält fest,
dass `PhotoCard` genau drei Aufrufstellen hat und `PhotoGridTile` sie nicht importiert.

Das Testkonzept (`specs/architecture/0002-testkonzept.md`) wird im selben PR fortgeschrieben: die
jsdom-Fallstricke (beide Observer, konstante Breite 0), die Regel „treibbarer Stub statt No-op-Stub"
samt der daraus folgenden Bauvorgabe an den Produktivcode, das Vier-Fälle-Muster für eine
gerätegebundene Geste mit Zeitschwelle, das Muster „zwei Wahrheiten desselben Werts", die neu
gefasste `grid-columns`-Zeile und zwei neue bekannte Lücken (Rundungsabweichung des aus der Vorschau
gelesenen Verhältnisses; die Verdeckung des Motivs durch die Angabenzeile bleibt ein gemessener
Anteil, kein gestalterisches Urteil).

## Entscheidungen

- **Gate-Aktionen nur im Gate-Modus** (Daniel, 2026-09-14): „Übernehmen" und „Vergleichen"
  erscheinen ausschließlich bei `?gate=1` dauerhaft unter dem Bild, in der normalen Übersicht gar
  nicht. Damit bleiben AK3 und AK12 gleichzeitig wörtlich wahr.
- **Filterleiste am Telefon** (Daniel, 2026-09-14): Die Seite scrollt nie seitlich, die Leiste
  selbst ist dort ein eigener horizontaler Scrollbereich.
- **Info-Auslöser und Motiv-Marker entfallen in der Übersicht** (Daniel, 2026-09-14). Getragener
  Preis: Die Bewertungsdetails sind aus dem Raster nicht mehr erreichbar, nur noch in der
  Detailansicht.
- **Die letzte, unvollständige Zeile wird nicht aufgezogen** — sonst entstünde aus einem einzelnen
  Restbild eine bildschirmhohe Kachel.
- `architect` konsultiert (Schritt 1) → ADR 0110.
- `ux-ui-designer` konsultiert (Schritt 2).
- `test-engineer` konsultiert (Schritt 3).
- `security-engineer` konsultiert (Schritt 3) → sieben Auflagen S1–S7.

## Offene Fragen

Keine.

## Out of Scope

- Die Detailansicht selbst wird nicht überarbeitet.
- Ein eigener Indikator dafür, ob ein Bild zur gemeinsamen Endauswahl gehört. Die Angabe liegt
  serverseitig vor und kann später ohne Vorarbeit ergänzt werden.
- Die drei übrigen Foto-Ansichten und `PhotoCard` selbst.
