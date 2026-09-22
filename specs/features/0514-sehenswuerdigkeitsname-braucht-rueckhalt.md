# 0514 - Sehenswürdigkeitsname benennt ein Event erst ab einem Anteil seiner Fotos

**Status:** Implemented ([PR #524](https://github.com/TheRealKoller/photosort/pull/524))
**Erstellt:** 2026-09-20
**Bezug:** [Issue #514](https://github.com/TheRealKoller/photosort/issues/514)

## Ziel

Ein Anlass wird beim Durchsehen an seiner Überschrift wiedererkannt. Trägt ein Event den Namen
einer Sehenswürdigkeit, weil ein einzelnes Foto sie erkannt hat, ist diese Überschrift eine
Vermutung, die als Tatsache erscheint. Weil Events größer ausfallen und der Name bleibt, benennt
ein einzelnes Foto heute einen ganzen Ausflug und nimmt ihm zugleich Ortsnamen und Koordinate weg —
aus „Paris (14:00–16:30 Uhr)" wird „Eiffelturm (14:00–16:30 Uhr)".

Diese Spec bindet die Benennung an den Rückhalt der Fotos eines Events und lässt den aufgelösten
Ortsnamen daneben sichtbar, statt ihn zu verdrängen.

## User Story

Als Person, die die Fotos einer Reise kuratiert, möchte ich, dass ein Event nur dann den Namen
einer Sehenswürdigkeit trägt, wenn dieser von einem Anteil seiner Fotos bezeugt wird, und dass der
Ortsname daneben sichtbar bleibt, damit die Überschrift den Anlass zuverlässig bezeichnet und ich
keiner Vermutung folge, die auf einem einzelnen Foto beruht.

## Akzeptanzkriterien

- [ ] Ein Sehenswürdigkeitsname benennt ein Event nur, wenn ihn **mindestens ein Zehntel (10 %) der
      Fotos dieses Events** bezeugt. Der Anteil ist die Zahl der tragenden Fotos geteilt durch die
      Gesamtzahl der Fotos des Events (alle Mitglieder, nicht nur die mit Namen); genau 10 % genügen
      (inklusiv). Träger ist ein Foto, dessen verwendbarer Name nach `_usable_name` genau der
      Gewinnername ist; ein nach der Sanitisierung leerer Name zählt weder als Träger noch kann er
      gewinnen.
- [ ] Trägt ein Event Fotos mit **verschiedenen** Sehenswürdigkeitsnamen, benennt der von den
      **meisten** Fotos bezeugte Name das Event; bei gleicher Zahl der **frühere** (kleinerer Index
      in der nach `(taken_at, photo_id)` sortierten Mitgliederfolge). Nach dem Gewinner wird kein
      weiterer Name geprüft: reißt er den Anteil nicht, trägt das Event **keinen** Namen.
- [ ] Ein Event aus einem einzelnen Foto darf seinen Sehenswürdigkeitsnamen tragen — 1 von 1
      erfüllt den Anteil.
- [ ] Erreicht ein Name den Anteil nicht, verhält sich das Event in jeder Hinsicht wie ein Event
      **ohne** Sehenswürdigkeitsnamen: es trägt keinen Namen, keinen Hinweis auf die verworfene
      Vermutung und keinen eigenen Anzeigezustand, und seine Überschrift folgt der gewohnten
      Reihenfolge (aufgelöster Ortsname, sonst Nummer und Zeitspanne). Auf Datenebene heißt das:
      die `events`-Zeile ist — außer `id` und Laufbezug — identisch mit der Zeile, die derselbe Lauf
      ohne die verworfene Erkennung schriebe; insbesondere fällt das Event auf die Koordinatenstufe
      zurück (`place_kind='coordinate'`, `place_lat`/`place_lon` gesetzt), wenn es eine gemessene
      Koordinate trägt.
- [ ] Ein Event mit tragendem Namen zeigt in seiner Überschrift **beides**: erst den Namen, dann den
      Ortsnamen, durch ein Komma getrennt — zum Beispiel `Eiffelturm, Paris (14:00–16:30 Uhr)`.
      Zeitspanne und Nummer bleiben wie bisher.
- [ ] Der Ortsname ist **derselbe**, den dasselbe Event ohne Sehenswürdigkeitsnamen zeigen würde,
      und in derselben Form (einschließlich einer vorhandenen Viertel-Ergänzung). Es entsteht keine
      zweite Ortsregel. Bei Viertel-Ergänzung lautet die Überschrift
      `Eiffelturm, Paris, Gros-Caillou (14:00–16:30 Uhr)` — zwei Kommata, weil das zweite die
      bestehende Ortsform trägt.
- [ ] Lässt sich kein Ortsname auflösen, steht der Name allein — kein Trennzeichen ohne zweiten
      Teil und keine leere Klammer. Ein leerer String gilt wie `null` (Projektkonvention
      `usableName`).
- [ ] Die **Koordinatenstufe** bleibt weiterhin verdrängt: sichtbar wird zusätzlich der Ortsname,
      nicht die gerundete Koordinate.
- [ ] Eine Erkennung **ohne Ortshinweis** zählt für den Anteil wie jede andere: keine Bevorzugung,
      kein Ausschluss und keine Plausibilitätsprüfung des Namens gegen einen Ortsdatensatz. Ein
      Foto ohne eigene Koordinate wird weiterhin erkannt; das Fehlen bleibt ein zulässiger Zustand
      und kein Fehlerfall.
- [ ] Name und Ortsname erscheinen als reiner Text — die bestehende Auflage gilt für die
      zusammengesetzte Form unverändert mit.
- [ ] Die Prüfung geschieht beim Benennen des Events, nicht beim Erkennen: Eine geänderte Schwelle
      wirkt beim nächsten Aufbau der Gruppierung (`rebuild_run_grouping`) und löst **keinen** neuen
      bezahlten Erkennungsaufruf aus; die vorhandenen Erkennungsergebnisse
      (`photo_landmark_detections`) bleiben zeilen- und wertgleich erhalten.
- [ ] Nach der Umsetzung trägt **kein** Event einen Namen, dessen tragende Fotos weniger als ein
      Zehntel seiner Fotos ausmachen — **und** es gibt weiterhin benannte Events. Die zweite Hälfte
      ist die Gegenanzeige: Eine Schwelle, die jede Benennung abschaltet, verfehlt den Zweck.

## Datenmodell-Bezug

Kein Schemawechsel, keine Migration, kein neues Feld. `events.landmark_name`, `events.place_name`,
`events.place_kind` und `events.place_lat`/`place_lon` behalten ihre Bedeutung; die
Überschriftsform `"<Name>, <Ortsname>"` ist eine reine Anzeigeform und wird nicht persistiert.
Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

Die Entscheidung ist als ADR
[`0120`](../decisions/0120-der-sehenswuerdigkeitsname-braucht-rueckhalt-und-der-ortsname-tritt-daneben.md)
festgehalten. Sie löst ADR 0118 Punkt 3 („der früheste Name gewinnt"; „Ein Event mit Namen bekommt
keinen Ortsnamen") ab und in ADR 0102 die Konsequenz, dass der Ortsname die zweite *Stufe* der
Überschrift ist. ADR 0107 gilt vollständig weiter: Das Namensregister entscheidet, **welchen** Namen
ein Event trägt — diese Spec entscheidet, **ob**.

Drei Änderungen, alle innerhalb des bestehenden Wegs. Kein neues Modul, keine neue Tabelle, kein
neues Feld, kein neuer Cloud-Aufruf, keine neue Abhängigkeit:

1. `events.py::_name_of` — aus „der erste Name gewinnt" wird „meiste Träger, bei Gleichstand der
   frühere, danach den Anteil prüfen".
2. `events.py::locality_of_event` — die Sehenswürdigkeits-Sperre fällt; **eine** Ortsregel für alle
   Events.
3. `frontend/src/utils/timeOfDay.ts::eventPlaceName` — Sehenswürdigkeitsname und Ortsname stehen
   nebeneinander.

`_place_of` bleibt **unverändert**, `_built` bleibt die einzige Stelle, an der Name, Zellen und
`place_kind` eines Events entstehen.

### Die Schwelle und der Gewinner in `_name_of`

- **Neue Konstante** `LANDMARK_MIN_SHARE = Fraction(1, 10)` im Konstantenblock von `events.py`. Sie
  wird überall als **Modulattribut** gelesen, nie als Default-Parameterwert gebunden — sonst liefe
  `monkeypatch.setattr` ins Leere und ein Prüfsatz könnte die Schwelle nicht verschieben.
- **Ein Durchgang** über `members` (bereits nach `(taken_at, photo_id)` sortiert): je Name die
  Trägerzahl zählen und den **ersten** Index merken. Gewinner ist das Maximum nach
  `(Trägerzahl, −erster Index)` — die Sortierung wird nicht ein zweites Mal hergestellt.
- **Danach** die Anteilsprüfung, kreuzmultipliziert in ganzen Zahlen:
  `Träger * LANDMARK_MIN_SHARE.denominator >= len(members) * LANDMARK_MIN_SHARE.numerator`. Kein
  Float-Vergleich — `1/10` ist an der Rundungsgrenze keine Entscheidung, die ein Kriterium tragen
  darf.
- **Kein Nachrücken.** Der Gewinner trägt das Maximum; scheitert er, ist `_name_of` → `None`, und
  `_place_of` fällt auf Koordinate bzw. mehrere Orte zurück.
- `_usable_name` bleibt der Filter davor. Der Docstring von `_name_of` wird ersetzt — die Regel
  heißt jetzt „Rückhalt, dann der frühere".

### Eine Ortsregel, und der Ortsname tritt daneben

- `locality_of_event`: der Zweig `if event.landmark_name is not None: return None` **entfällt**, der
  Rest bleibt.
- `assign_place_names`: Rumpf **unverändert** — Zwei-Durchgangsstruktur, Viertel-Regel und die
  Längengrenze `MAX_PLACE_NAME_LENGTH` bleiben. Nur der Docstring zieht nach. `landmark_name` wird
  danach an keiner Stelle dieses Moduls mehr gelesen.
- **Der Server setzt nichts zusammen.** `events.place_name` bleibt der reine Ortsname („Ort" bzw.
  „Ort, Viertel"). Die Form „Name, Ort" entsteht im Frontend — sie ist eine reine Anzeigefrage, und
  eine zweite Quelle derselben Form erzeugte genau die Divergenz, gegen die
  `photoDetail.structure.test.ts` als Wächter steht.
- **`_place_of` wird nicht angefasst:** Ein Event mit verwendbarem Namen bleibt
  `place_kind='landmark'` mit `place_lat`/`place_lon = NULL`. Verdrängt bleibt die
  **Koordinatenstufe** — der Ortsname nicht mehr.

### Der Worker fragt jetzt auch die Zellen benannter Events

In `worker.py::_build_grouping_and_rankings` fällt der Zellenfilter:

```python
# vorher
cells = {cell for built in built_events if built.landmark_name is None for cell in built.place_cells}
# nachher
cells = {cell for built in built_events for cell in built.place_cells}
```

Der Kommentar darüber wird auf die neue Regel umgeschrieben: Der Ortsname steht neben dem Namen,
also muss seine Zelle gefragt werden. Die Reihenfolge bleibt Event-Bildung → `_place_infos` →
`assign_place_names` → Schreiben der Zeilen.

### Frontend: eine Funktion, keine zweite Rangfolge

`eventPlaceName` in `frontend/src/utils/timeOfDay.ts` liefert die zusammengesetzte Form:

| Lage | Ergebnis |
|---|---|
| Name **und** Ortsname vorhanden | `"<Name>, <Ortsname>"` |
| nur Name | `"<Name>"` |
| nur Ortsname | `"<Ortsname>"` |
| keins von beiden | `null` |

- **`formatEventHeading` wird nicht angefasst.** Es bleibt in der Form `<Name> (<Zeitspanne>)` bzw.
  `Position <n> (<Zeitspanne>)`; dadurch zeigen Bilddetailansicht (`PhotoDetailPage.tsx`,
  `place-line`), Ereignis-/Album-Gruppierung (`eventGrouping.ts`) und der Titel von
  `DraftAlternativesDialog.tsx` die neue Form ohne eigene Änderung.
- Der `null`/`''`-Rückfall je Teil bleibt über `usableName` defensiv; beide Teile sind Fremdtext und
  werden weiterhin ausschließlich als regulärer React-Textknoten gerendert.
- **Keine Längengrenze im Frontend.** Dort wird nichts gekürzt; `MAX_PLACE_NAME_LENGTH` bleibt eine
  Servergrenze für die Serverform „Ort, Viertel".

### Die Prüfkommandos ziehen mit

- **`place_probe.py::heading_counts` (Block D)** — die Partition wird neu gebildet:
  `events_named` zählt alle Events mit Namen (jetzt einschließlich der benannten),
  `events_keeping_position = len(probe.events) - named`. `events_with_landmark` bleibt als eigene
  Zeile, ist aber ab jetzt eine **Teilmenge** von `events_named` und darf nicht mehr abgezogen
  werden.
- **`event_probe.py` Block C3 (`LandmarkCounts`/`landmark_counts`)** — die für die Gegenanzeige
  nötigen Zeilen kommen hinzu: Zahl der **benannten Events** (muss `> 0` sein) und der **kleinste
  Trägeranteil** unter den benannten Events bzw. die Zahl der Events mit einem Anteil **unter** der
  Schwelle (muss `0` sein). Gerechnet über die Trägerzählung, die der Block ohnehin führt
  (`name_by_photo`). Der kleinste Anteil wird als **Bruch** ausgegeben, nicht auf Prozent gerundet.
- Beide Kommandos bleiben rein lesend; keine Ausgabezeile trägt einen Namen oder eine Koordinate.

### Was ausdrücklich nicht passiert

- Kein Datenmodell-/Schemawechsel, keine Migration, kein neues API-Feld, kein neuer Cloud-Aufruf,
  keine neue Abhängigkeit.
- Keine Änderung an `_place_of`, an `landmark.py`, an der Erkennung, am Namensregister
  (`landmark_names`) oder an der Gliederung (Motivwechsel-Stufe, Signalschwellen, die vier Riegel
  des Zusammenlegens). Diese Entscheidung ändert nur, **ob** ein Event einen Namen trägt und **was**
  daneben steht.
- Kein Backfill: Bestehende Läufe behalten ihre Namen und Ortsnamen, bis sie neu berechnet werden.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `backend/src/photosort/events.py` | `LANDMARK_MIN_SHARE`; `_name_of` (Gewinner + Anteil); `locality_of_event` (Sperre entfällt); Docstrings |
| `backend/src/photosort/worker.py` | Zellenfilter in `_build_grouping_and_rankings` samt Kommentar |
| `backend/src/photosort/event_probe.py` | Block C3: `LandmarkCounts`, `landmark_counts`, Berichtszeilen |
| `backend/src/photosort/place_probe.py` | Block D: Partition in `heading_counts`, Docstring, Berichtszeilen |
| `backend/src/photosort/demo_state.py` | `_DEMO_PLACE_NAMES` samt Kommentar: das Landmark-Event trägt seinen Ortsnamen daneben |
| `backend/src/photosort/api/photos.py` | Docstrings `EventPlaceOut`/`EventOut` |
| `frontend/src/utils/timeOfDay.ts` | `eventPlaceName` setzt zusammen; Docstring zieht nach |
| `frontend/src/api/types.ts` | Kommentare an `EventPlace`/`EventOut` |
| `docs/architecture.md` | Antwortbeschreibung (drei Stufen) und `events.place_name` |
| `specs/architecture/0003-securitykonzept.md` | M9-Fortschreibung und Restrisiko — siehe `## Security` |
| `specs/architecture/0002-testkonzept.md` | vier Muster — siehe `## Teststrategie` |

`backend/src/photosort/demo_state.py` ist **betroffen**: `_create_demo_events` setzt `place_name`
für die Demo-Events, und `_DEMO_PLACE_NAMES` gibt dem Landmark-Event seinen Ortsnamen daneben —
die beiden Demo-Tests, die dort die abgelöste Zusage behaupteten, ziehen mit (siehe
`## Teststrategie`).

## UI/UX

**Sichtbare Oberfläche: ja, ohne neue Form.** Die Story ändert den *Text* bereits bestehender
Überschriften in vier Ansichten. Es entsteht keine neue Ansicht, keine neue Komponente, kein
Bedienelement, keine neue Zustandsdarstellung, keine neue Farbe — und kein Entwurf.

### Wo die neue Form erscheint

Sie erscheint an genau den vier Stellen, die heute schon über `eventPlaceName` /
`formatEventHeading` laufen; alle vier erben sie ohne eigene Änderung. Rollen und Typostufen
bleiben unverändert:

| Stelle | Element (unverändert) | Neu darin |
|---|---|---|
| `AlbumDraftPage.tsx`, Ereignisgruppe | `h3` `text-base` | `Eiffelturm, Paris (14:00–16:30 Uhr)` |
| `AlbumSelectionPage.tsx`, Ereignisgruppe | `h3` `text-base` | dieselbe Überschrift |
| `PhotoDetailPage.tsx`, Ortszeile (`place-line`) | `p` `text-xs text-text-muted` | `Eiffelturm, Paris` — ohne Zeitspanne, wie bisher |
| `DraftAlternativesDialog.tsx`, Dialogtitel | `h2` `text-lg font-bold` | dieselbe Überschrift |

Die Überschrift bleibt je Stelle **ein** Textknoten.

### Zustände

**Keine neuen.** Eine Überschrift ist Inhalt einer bereits geladenen Zeile; keiner der bestehenden
Zustände ändert sich. Die Textfälle sind vollständig:

- **Name und Ortsname** → `Eiffelturm, Paris (…)`.
- **Nur Name**, wenn sich kein Ortsname auflösen lässt → `Eiffelturm (…)`.
- **Nur Ortsname** → `Paris (…)` (heutige Form).
- **Keins von beidem** → `Position n (…)` in der Überschrift, `nicht bestimmbar` in der Ortszeile.

Ein Event, dessen Name die Schwelle reißt, ist ausdrücklich **kein fünfter Zustand**: es fällt in
die dritte oder vierte Form und trägt keinen Hinweis auf den verworfenen Namen — keine
Auszeichnung, kein Zähler, kein Text.

### Umbruch und Design-System

Keine der vier Stellen beschneidet Text (kein `truncate`, kein `line-clamp`); eine lange
Überschrift bricht um, statt still gekürzt zu werden. Das Komma steht hinter einem Leerzeichen und
damit an einer Umbruchstelle.

**Design-System nicht berührt — keine Ergänzung nötig.** Kein neues Token, keine neue Farb-, Typo-,
Abstands- oder Radiusentscheidung, kein neuer Baustein, keine neue Interaktion. Die
Überschriftenleiter bleibt unangetastet, `designSystem.contract.test.ts` wird nicht getroffen. Die
Design-Quelle (Penpot) und der Entwurfsweg sind nicht betroffen.

Die beiden Teile bleiben **gleichrangig ausgezeichnet** (ein Textknoten, kein zweiter Schnitt, kein
gedämpfter Ortsname) — die Produktseite ist durch die Kriterien entschieden, und „reiner Text" ist
dort verlangt.

## Security

**Sicherheitsrelevant, kein Blocker.** Kein neuer Endpunkt, kein Auth-Pfad, kein neues API-Feld,
keine Schema-/Datenmodelländerung, keine neue Abhängigkeit, kein neuer Cloud-Aufruf, keine neue
Eingabe von außen, kein neuer Kostenpfad. Relevanz entsteht an drei Stellen: eine zusammengesetzte
Überschrift aus zwei fremderzeugten Texten, eine schrumpfende eventübergreifende Wirkung des
Namens, und ein wachsender Ortsabfluss.

- **S1 — Die zusammengesetzte Überschrift bleibt Text und bleibt Anzeige.** Mit `eventPlaceName`
  treffen erstmals `place.landmark_name` (Modellantwort) und `place_name` (Ortsdatensatz Dritter)
  in **einem** Wert zusammen. **Muss:** Der zusammengesetzte Wert wird ausschließlich als regulärer
  React-Textknoten gerendert — nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in
  `href`/`src`/`style`, nie als React-`key`, nie als Gleichheits- oder Aufsuchschlüssel. Die
  Identität eines Events bleibt seine `id` (`eventGrouping.ts::groupPhotosByDay`). Bei Verletzung
  entsteht aus einer Modellantwort oder einer Ortsdatensatz-Zeile ausführbares Markup bzw. eine
  still zusammengeführte Eventgruppe.
- **S2 — Der Name wird durch die Schwelle schwerer steuerbar, nicht leichter.** Ein präpariertes
  Bild kann weiterhin einen Namen erzwingen, erreicht die Überschrift aber nur noch bei einem
  Zehntel der Mitglieder; ein zweiter Kandidat rückt nicht nach. Der Name bewegt weiterhin keine
  Event-Grenze, keinen Riegel und keinen Partitionsschlüssel — und hebt erstmals auch keinen Zähler
  mehr.
- **S3 — Der wachsende Ortsabfluss ist begrenzt.** Drei Bewegungen: (a) ein benanntes Event trägt
  seinen Ortsnamen in `EventOut.place_name` hinaus, (b) die Zellen benannter Events werden
  aufgelöst und landen in `place_lookups`, (c) ein Event, das seinen Namen verliert, rückt in die
  Koordinatenstufe und schreibt `events.place_lat`/`place_lon`. **Kein neuer Empfänger** (dieselben
  zwei authentifizierten Nutzer), **keine neue Körnung**, **kein neuer ausgehender Pfad**;
  `place_name` ist seit Spec 0434 ein ausgeliefertes Feld, die Ortsspur ist projektgebunden, auf
  zwei Nachkommastellen vergröbert, ohne Personen- und ohne Zeitbezug, und gröber als die volle
  EXIF-Koordinate, die `PhotoOut.location` derselben Antwort ohnehin führt. Unverändert Muss:
  Projektbindung der Abfrage ohne Rückfall auf ein Nachbarprojekt, Request-Pfad mit literal `None`
  als Auflöser, Hash-Prüfung des Ortsdatensatzes vor jedem Gebrauch.
- **S4 — Kein neuer Kanal, nichts Neues in Log oder Fehlerzeile.** `_name_of` loggt nichts; die
  Auflage „keine Koordinate, kein Name in irgendeiner Logzeile, in `LandmarkApiError` oder in
  `photo_cloud_vision_errors.error_message`" gilt wortgleich weiter. `LANDMARK_MIN_SHARE` ist
  **keine** Sicherheitsschwelle: sie verschiebt nur, welches von zwei bereits getragenen
  Ort-Regimes ein Event bekommt. Die Messausgaben bleiben Aggregate.

### Nachzuziehen im Sicherheitskonzept

`specs/architecture/0003-securitykonzept.md`, Abschnitt „Standortdaten":

1. **Neue Fortschreibung** `Spec 0514/ADR 0120` nach dem ADR-0119-Block: Einstufung, korrigierte
   Pfad-Tabelle ((1) bleibt nur für die Koordinatenstufe, (2) und (3) fallen weg), der in drei
   Bewegungen ausgeschriebene Ortsabfluss mit der Begrenzung aus S3, S1–S4 als Auflagen, M9-e in
   der neuen Fassung.
2. **Z. 472 — Teil-Vermerk.** „Alle drei wirken ausschließlich ortsmindernd, und (3) ist monoton"
   ist ab hier falsch; Rücknahme im dort schon verwendeten Muster. Die Pfad-Beschreibung ist zudem
   ungenau: die Unterdrückung des Ortsnamens saß nie in `_place_of`, sondern in
   `locality_of_event`.
3. **Z. 486, 497, 500 — Korrektur.** Die drei Entlastungs-Aussagen („größeres benanntes Event
   unterdrückt mehr Koordinaten, löst weniger Zellen auf, hängt seltener ein Viertel an") sind
   gegenstandslos. Die zugehörigen „Neu zu stellen"-Auslöser sind **nicht** ausgelöst.
4. **Z. 478 — M9-e enger fassen.** Die Ausnahme „die Gleichnamigkeitszählung … darf einen Zähler
   nur senken" entfällt ersatzlos; die zweite Hälfte wird zu „der Name hat **keine**
   eventübergreifende Wirkung mehr". Der Kern der Auflage ist damit heute durch keinen Test gedeckt
   — zu belegen mit einem Syntaxbaum-Wächter (Muster
   `test_selection.py::TestOnlyTheMeasuringPathPassesItsOwnThreshold`), oder die Zeile sagt
   ausdrücklich „kein Test".
5. **Z. 1267 — Restrisiko neu fassen, nicht neu entscheiden.** Der Verweis „die Plausibilisierung
   ist Issue #514" ist ein erledigter Vorgang; die Abfluss-Entlastung wird durch die
   Schranken-Begründung aus S3 ersetzt. Die Daniel-Entscheidung („die Benennung bekommt keine
   eigene Auflage"; Schaden = Anzeigequalität) bleibt für das stehen, was sie tatsächlich
   entschieden hat.
6. **Z. 480 — Teil-Vermerk.** Neben `_usable_name` kommt der Doku-Block von `_name_of` hinzu (er
   behauptet heute „der FRÜHEHSTE gewinnt"), ebenso die Begründungen in `worker.py` und in
   `PhotoDetailPage.tsx`.

## Teststrategie

Die Akzeptanzkriterien sind testbar. Die Schwelle liegt als exakter Bruch `1/10` fest und ist ein
Testgegenstand (1 von 10 genügt, 1 von 11 nicht) — eine bewusste Ausnahme von „kein Test pinnt
einen Zahlwert", weil der Wert der Nenner des Kriteriums selbst ist und laut ADR nicht kalibriert
wird. Schwellwert-Fälle werden aus dem Symbol gebaut (`Fraction.numerator`/`.denominator`).

| Ebene | Ort | Gegenstand |
|---|---|---|
| Backend Unit (DB-frei) | `test_events.py`, neue Klasse | `_name_of`/`_built`: Mehrheit, Gleichstand, Anteil inklusiv, kein Nachrücken, Ein-Foto-Event, unbrauchbare Namen; `locality_of_event`/`assign_place_names`: eine Ortsregel |
| Backend Integration (In-Memory-DB) | `test_worker_place_names.py` | Zellenfilter gefallen, `place_name` neben dem Namen, Koordinatenstufe verdrängt, Namensverlust → Koordinatenstufe, Identität zweier Datenlagen |
| Backend Integration (Request-Pfad) | `test_worker_place_names.py` | `rebuild_run_grouping`: geänderte Schwelle wirkt, keine Erkennung, Detektionszeilen unverändert |
| Messkommando (rein) | `test_place_probe.py`, `test_event_probe.py` | Block D: überlappende Partition; Block C3: benannte Events, kleinster Trägeranteil, Events unter der Schwelle |
| Frontend Unit (`vitest`) | `timeOfDay.test.ts` | `eventPlaceName`: vier Ausgänge; `formatEventHeading` unverändert |
| Frontend Renderstelle | `DraftAlternativesDialog.test.tsx`, `AlbumDraftPage.test.tsx` | kombinierte Form als **ein** Textknoten, auch bei feindlichem Inhalt in beiden Feldern |
| Strukturwächter | `photoDetail.structure.test.ts` | bleibt **unverändert** gültig |
| Nicht | — | kein neuer E2E-Fall; kein Netz; kein echter Landmark-Client |

### Wichtigste Edge Cases

- **Inklusive Grenze aus dem Symbol:** `denominator` Fotos und `numerator` Träger → benannt;
  `denominator + 1` Fotos und `numerator` Träger → nicht.
- **Nenner ist die Mitgliederzahl:** 3 Fotos, 1 Träger → benannt; 30 Fotos, 2 Träger → nicht.
- **Mehrheit schlägt Frühe; Gleichstand → früherer; kein Nachrücken.**
- **Invariante in `assert_event_invariants`:** Für jedes gebaute Event gilt `landmark_name is None`
  **oder** `Träger · denominator ≥ len(photo_ids) · numerator`. Jeder Fall der Datei trägt damit die
  Gegenanzeige mit.
- **Differentielle Probe für die eine Ortsregel:** dieselbe Eventliste zweimal durch
  `assign_place_names` — einmal mit `landmark_name`, einmal mit `None` → positionsweise identische
  Ortsnamen.
- **Ein benanntes und ein unbenanntes Event mit demselben Ortsnamen** lösen gegenseitig die
  Viertel-Ergänzung aus.
- **Identität zweier Datenlagen:** zwei Läufe mit identischen Fotos, der eine mit einer zu
  schwachen Erkennung, der andere ohne jede Erkennung → gleiche `Event`-Form über alle Spalten;
  Gegenprobe: es gibt mindestens ein Event.
- **Neuaufbau statt Erkennung:** Lauf, `monkeypatch` der Schwelle, `rebuild_run_grouping` →
  Name nach neuer Schwelle, `photo_landmark_detections` zeilen- und wertgleich, kein
  Landmark-Client.
- **Block D:** fünf Events über alle vier Kombinationen; der tragende Fall ist das **benannte Event
  ohne auflösbare Zelle**; Bilanz `named + keeping_position == len(events)`.
- **Block C3:** keine benannten Events → kleinster Anteil **undefiniert** (kein `min()` über eine
  leere Folge); genau auf der Schwelle ist nicht „unter"; ein Event unter der Schwelle setzt die
  Gegenanzeige.
- **Bewusst nicht getestet:** die Kalibrierung des Zehntels gegen echte Fotos (kein Ground-Truth-
  Korpus) — die Gegenanzeige auf echten Daten bleibt eine Messung des Prüfkommandos. Ebenso nicht
  behandelt: der Fall „Sehenswürdigkeitsname gleich Ortsname" (Überschrift `Paris, Paris`); aus den
  Kriterien folgt keine Dedup-Vorschrift, eine wäre eine zweite, ungeschriebene Regel.

### Zu ersetzende Tests

Ein grüner Fall, der die abgelöste Regel behauptet, wird **ersetzt, nicht nachgezogen**:

- `test_events.py::test_the_earliest_name_wins_across_a_merge_of_the_third_stage` (Z. 1437)
- `test_events.py::test_an_event_with_two_different_names_carries_the_earlier_one` (Z. 1422) —
  wird zum Gleichstandsfall
- `test_events.py::test_a_landmark_event_gets_no_place_name_and_triggers_no_district` (Z. 1882)
- `test_worker_place_names.py::test_only_events_without_a_landmark_are_asked_for` (Z. 345)
- `test_place_probe.py::TestBlockDHeadings::test_a_landmark_event_never_counts_towards_homonymy`
  (Z. 424) und der Begründungskommentar in `test_homonymy_one_resolvable_by_district_and_one_not`
- `test_demo_state.py::TestTheDemoStateShowsTheDistrictRule::…` — erste Hälfte behauptet die
  abgelöste Zusage
- `test_api_photos.py` — Kommentar „Ein Event MIT Sehenswürdigkeit trägt keinen Ortsnamen"
- `frontend/src/utils/timeOfDay.test.ts` (`laesst der Sehenswuerdigkeit den Vorrang …` Z. 119,
  `eventPlaceName > nimmt die erkannte Sehenswürdigkeit zuerst` Z. 229)

### Nachzuziehen im Testkonzept

`specs/architecture/0002-testkonzept.md` bekommt vier Punkte:

1. **Stellschraube neuen Typs.** `test_event_probe.py::_adjustable_constants_of_events` liest nur
   `int | float | timedelta`; `Fraction` fällt durch, und der Wächter
   `test_the_module_binds_no_adjustable_constant` liefe leer. Der Typ wird um `Fraction` erweitert.
2. **Anteils-Schwellen über eine Mitgliedermenge:** inklusive Grenze, Nenner ist die Gesamtmenge,
   kreuzmultiplizierter Ganzzahlvergleich, kein Nachrücken.
3. **Überlappende Partitionen werden aus der Vereinigung gezählt, nie durch Subtraktion** — eine
   Teilmenge, die in die Hauptmenge hineinwächst, wird sonst doppelt abgezogen.
4. **Feldunabhängigkeit als differentielle Probe** („dieselbe Auskunft, egal ob Feld X gesetzt
   ist").

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR [`0120`](../decisions/0120-der-sehenswuerdigkeitsname-braucht-rueckhalt-und-der-ortsname-tritt-daneben.md) angelegt.
- `ux-ui-designer` konsultiert (Schritt 2): reine Textänderung, Design-System unberührt.
- `test-engineer` und `security-engineer` konsultiert (Schritt 3): Teststrategie und
  Sicherheits-Fortschreibung wie oben.
- **Selbst entschieden (architect):** eine Ortsregel statt zwei Klassen von Events; die
  Zusammensetzung sitzt allein in `eventPlaceName`, `formatEventHeading` bleibt unangetastet.
- **Selbst entschieden (ux-ui-designer):** die beiden Teile bleiben gleichrangig ausgezeichnet.
- **Selbst entschieden (test-engineer):** keine Dedup von Name und Ortsname im Frontend; keine
  Erweiterung der E2E-Ebene.
- **Entschieden (`developer`, im Rahmen des Offenen Punktes dieser Spec — keine Produktentscheidung):**
  Das Demo-Landmark-Event trägt seinen Ortsnamen daneben (`_DEMO_PLACE_NAMES`), damit die kombinierte
  Form auch in den Demo-Daten sichtbar ist. Es teilt seine Zelle mit dem „Mehrere Orte“-Event und
  bekommt deshalb dasselbe Viertel (`Paris, Gros-Caillou`); das Ein-Zellen-Event behält
  `Paris, Montmartre`. Die beiden davon berührten Demo-Tests wurden ersetzt, nicht nachgezogen
  (siehe `## Teststrategie`). Ein Sichtprüflauf (`browse-app`) war dafür nicht nötig — die Lage ist
  über Demo- und Frontend-Tests belegt.

## Offene Fragen

- Keine.

## Out of Scope

- Die Event-Bildung: keine Grenze, keine Schwelle und kein Zusammenlegen wird bewegt (das war #506).
- Eine lokale Plausibilitätsprüfung des Namens gegen einen Ortsdatensatz und jede Änderung der
  Erkennung selbst.
- Die Konfidenzgrenze je Erkennung und das projektgebundene Namensregister — unverändert.
- Ein Nachziehen bereits berechneter Läufe und ein erneuter bezahlter Erkennungsaufruf.
- Umbenennen, Bestätigen oder Korrigieren eines Eventnamens von Hand; ein sichtbarer Hinweis auf
  einen verworfenen Namen; ein Anzeigen des Anteils.
- Eine Karte oder eine neue Ansicht.

---

*Umfang: Diese Spec liegt über dem Richtwert von ~200 Zeilen, weil sie die vier
Fachkonsultationen (Architektur, UI/UX, Security, Teststrategie) samt Umsetzungsplan und
Nachzieh-Listen vollständig trägt — das ist die Arbeitsgrundlage des anschließenden
`developer`-Laufs und keine Wiederholung; der Inhalt steht nirgends sonst.*
