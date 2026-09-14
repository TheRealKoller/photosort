# 0434 - Ortsnamen aus Koordinaten für Events ohne erkannte Sehenswürdigkeit

**Status:** Accepted
**Erstellt:** 2026-09-14
**Bezug:** [Issue #434](https://github.com/TheRealKoller/photosort/issues/434)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Story in zwei Auslieferungen zerfällt
(Messkommando, dann Auflösung auf dem gemessenen Weg) und beide Teile ihren eigenen Umsetzungs-,
Test- und Sicherheitsteil tragen. Ein Aufteilen auf zwei Spec-Dateien trennte die Messung von der
Entscheidung, die sie begründet.

## Ziel

Nach einer Reise gliedert sich der Album-Entwurf in Events. Trägt ein Event eine erkannte
Sehenswürdigkeit, heißt es nach ihr. Alle übrigen heißen nach ihrer Nummer und ihrer Zeitspanne —
auch dann, wenn eine Ortsangabe vorliegt, denn eine Koordinate ist als Überschrift wertlos. Bei
einer Reise mit dreißig Events ist die Gliederung damit über weite Strecken eine Liste von Nummern,
und wer sie durchgeht, muss aus Uhrzeiten erschließen, wo er war.

Diese Story gibt diesen Events einen sprechenden Namen: den Ort, an dem sie stattfanden. Nutzen
haben beide Nutzer beim Durchsehen und beim Nacharbeiten des Entwurfs — die Gliederung folgt dann
auch sichtbar der Reise, nicht nur strukturell.

Der Name ist nicht umsonst zu haben: Er muss aus der Ortsangabe aufgelöst werden, und genau das ist
im Projekt heute ausdrücklich ausgeschlossen, weil Ortsdaten der Familie dabei das System verlassen
könnten. Diese Story macht die Entscheidung bewusst wieder auf, statt sie nebenbei zu übergehen.

## User Story

Als Nutzer, der nach einer Reise den Album-Entwurf durchgeht, möchte ich, dass ein Event nach seinem
Ort heißt statt nach seiner Nummer, damit ich die Gliederung lesen kann, ohne mich an Uhrzeiten zu
erinnern.

## Akzeptanzkriterien

**Wie ein Event heißt**

- [ ] Ein Event mit erkannter Sehenswürdigkeit heißt unverändert nach ihr. Der aufgelöste Ortsname
      ersetzt sie nicht und tritt auch nicht daneben.
- [ ] Ein Event ohne Sehenswürdigkeit heißt nach dem aufgelösten Ortsnamen, wenn über alle seine
      Ortszellen **genau ein** Ortsname aufgelöst wird. Zellen ohne aufgelösten Namen zählen dabei
      nicht mit: ein Event aus zwei Zellen, von denen nur eine einen Namen liefert, trägt diesen
      Namen.
- [ ] Ein Event ohne jede Ortsangabe behält seine heutige Bezeichnung aus Nummer und Zeitspanne.
- [ ] Ein Event, dessen Zellen **zwei verschiedene** Ortsnamen liefern, behält die heutige
      Bezeichnung — für eine Menge von Orten gibt es keinen einen Namen. Mehrere Zellen mit
      demselben Namen sind kein solcher Fall.
- [ ] Ein Event mit Sehenswürdigkeit zählt bei der Gleichnamigkeitsprüfung nicht mit: es trägt
      keinen Ortsnamen und löst deshalb auch bei keinem anderen Event die Viertel-Ergänzung aus.
- [ ] Die Zeitspanne bleibt in jedem Fall Teil der Überschrift.
- [ ] Eine Koordinate erscheint weiterhin nie als Name.

**Wie genau der Name ist**

- [ ] Regelfall ist der Ort: „Split", „Garmisch-Partenkirchen".
- [ ] Trügen mehrere Events desselben Laufs denselben Ortsnamen, wird bei genau diesen zusätzlich
      das Viertel ergänzt („Berlin, Kreuzberg" neben „Berlin, Mitte"). Ein einzelnes Event in Berlin
      heißt weiterhin schlicht „Berlin".
- [ ] Ist für die gleichnamigen Events kein Viertel verfügbar, bleiben sie beim Ortsnamen;
      unterscheidbar bleiben sie dann über ihre Zeitspanne.
- [ ] Die Viertel-Ergänzung gilt **je Event einzeln**: trägt von zwei gleichnamigen Events nur
      eines ein Viertel, bekommt nur dieses den Zusatz. Liefern die Zellen eines Events zwei
      verschiedene Viertel, bekommt es keines.
- [ ] Die Auskunft über einen Ort wird in ihren Stufen festgehalten — Ort, Viertel und was sonst an
      Ebenen geliefert wird —, nicht als fertig zusammengesetzter Anzeigename.
- [ ] Aus der Auskunft geht hervor, auf welcher Ebene sie tatsächlich getroffen hat. Ein Treffer,
      der nur eine Region oder ein Land benennt, gilt als „kein Name aufgelöst" — nicht als
      dürftiger, aber brauchbarer Name.

**Wenn es nicht klappt**

- [ ] Lässt sich kein Name auflösen — keine Antwort, kein Treffer, unbrauchbare Antwort —, behält
      das Event die heutige Bezeichnung. Der Lauf läuft weiter und scheitert nicht daran.
- [ ] Eine **ausgebliebene Antwort** hinterlässt keine Auskunft — die Zelle wird beim nächsten Lauf
      erneut gefragt. Eine **Antwort ohne brauchbare Ebene** hinterlässt eine Auskunft ohne
      Namensstufen — dieselbe Zelle wird nicht erneut gefragt.
- [ ] Ein leerer oder überlanger Name wird verworfen, nie gekürzt übernommen — dasselbe Verhalten
      wie heute beim Namen einer Sehenswürdigkeit. Das gilt auch für die zusammengesetzte Form
      „Ort, Viertel": reißt sie die Grenze, bleibt der Ortsname allein stehen. Gekürzt wird nie —
      zwei verschiedene, auf dieselbe Länge gekappte Namen wären ein Name, und die Viertel-Regel
      griffe dann für Events an verschiedenen Orten.
- [ ] Ein aufgelöster Name erscheint in der Oberfläche ausschließlich als regulärer Textknoten:
      ein Name mit HTML-artigem Inhalt erscheint wörtlich und erzeugt kein Element.

**Dass der Name bleibt**

Hier stehen zwei verschiedene Dinge nebeneinander, die nicht zu einem werden dürfen: die Auskunft
darüber, was an einem Ort liegt, und der Name, den ein Event in einem bestimmten Lauf trägt.

- [ ] Die Auskunft über einen Ort wird einmal beschafft und danach wiederverwendet, statt für jedes
      Event erneut abgefragt zu werden: ein zweiter Lauf über dieselben Zellen stellt keine erneute
      Anfrage, auch dann nicht, wenn die erste Antwort keine brauchbare Ebene traf. Dieselbe Zelle
      in einem zweiten Projekt wird dagegen erneut gefragt; die Auskunft des einen Projekts wird
      für das andere nie gelesen.
- [ ] Diese Auskunft hängt an der Ortsangabe, nicht an einem Event und nicht an einem Lauf.
- [ ] Der Name eines Events wird dagegen mit dem Event festgehalten, nicht bei jeder Anzeige neu
      zusammengesetzt. Die Überschrift steht damit auch dann, wenn die Quelle gerade nicht
      erreichbar ist.
- [ ] Wird ein Lauf neu berechnet, entstehen die **Event-Namen** neu; es bleibt kein Name eines
      früheren Laufs stehen. Das gilt ausdrücklich nicht für die Auskunft über einen Ort: Sie ist
      lauf-unabhängig und wird bewusst wiederverwendet.
- [ ] Auch der Neuaufbau der Gliederung im Zeitversatz-Endpunkt bildet die Namen neu —
      ausschließlich aus bereits abgelegten Auskünften; er fragt niemanden und legt keine neue
      Auskunft an.
- [ ] Mit dem Projekt verschwinden beide: die festgehaltenen Event-Namen und die für dieses
      Projekt beschafften Ortsauskünfte. Die Auskunft wird deshalb je Projekt gehalten, nicht
      projektübergreifend.

**Woher der Name kommt**

- [ ] Bevor der Weg festgelegt wird, wird an einem echten Projekt gemessen: für welchen Anteil der
      Events liegt überhaupt eine Ortsangabe vor, und welche Namen liefert ein lokal verfügbarer
      Ortsdatensatz gegenüber einem externen Dienst für die tatsächlich bereisten Ziele. Fällt die
      Messung dürftig aus, ist das ein Ergebnis und keine Vorstufe.
- [ ] Die Messung deckt beide Verwendungen ab, nicht nur die Überschrift: Die Ortsauskunft geht
      auch in die Sehenswürdigkeitserkennung ein (#469), und dort wird auf anderer Ebene und zu
      einem anderen Zeitpunkt gefragt.
- [ ] Das Messkommando verändert am Datenbestand nichts: kein Lauf von ihm hinterlässt eine
      geänderte, gelöschte oder neue Zeile. Seine Vorgabe-Ausgabe enthält keine Koordinate und
      keinen aufgelösten Ortsnamen; beides steht ausschließlich im abschaltbaren
      `--namen`-Abschnitt.
- [ ] Die Wahl zwischen lokalem Datenbestand und externem Dienst wird auf dieser Grundlage
      getroffen und als Entscheidung festgehalten.
- [ ] Verlässt dabei etwas das System, dann ausschließlich die bereits vergröberte Ortsangabe des
      Events, nie die genaue Koordinate eines einzelnen Fotos.
- [ ] Die heute geltenden Festlegungen „Ortsnamen aus Koordinaten sind ausgeschlossen" und „keine
      Persistenz abgeleiteter Ortswerte" (ADR 0029, ADR 0072) werden ausdrücklich abgelöst.
- [ ] Die wiederverwendete Ortsauskunft überdauert den einzelnen Lauf und ist damit die
      dauerhafteste Ortsspur, die im System entsteht. Wie grob die Ortsangabe ist, unter der sie
      abgelegt wird, gehört deshalb zur Sicherheitsentscheidung und nicht zur Bequemlichkeit.

## Datenmodell-Bezug

Neu: `place_lookups` (projektgebundene Ortsauskunft je vergröberter Zelle, lauf-unabhängig).
Erweitert: `events.place_name` (Lauf-Artefakt, nullable, additiv). Beide hängen am Projekt und
verschwinden mit ihm. Einzelheiten in ADR 0102 und im Abschnitt „Architektur / Umsetzung";
`docs/architecture.md` zieht im selben Pull Request nach.

## Architektur / Umsetzung

**Grundlage:** ADR 0102. Die dortigen sechs Entscheidungen sind bindend; hier steht ihre Umsetzung.
Der architektonische Kern ist die Trennung zweier Dinge, die nicht eines werden dürfen: die
**Auskunft** über eine vergröberte Ortszelle (projektgebunden, lauf-unabhängig) und der **Name**,
den ein Event in einem Lauf trägt.

### 0. Reihenfolge: die Messung steht vor der Auflösung

Die Wegwahl ist eine Entscheidung Daniels und kann nicht vorweggenommen werden. Umgesetzt wird
deshalb zuerst das Messkommando, dann misst Daniel an seinem echten Projekt, dann fällt die
Wegwahl und wird als eigene ADR festgehalten, dann entsteht die eigentliche Auflösung. Fällt die
Messung dürftig aus, endet die Story dort — das ist ein Ergebnis.

### 1. Messkommando `backend/src/photosort/place_probe.py`

Aufruf `python -m photosort.place_probe --project-id N`, Muster `demo_state`, aber **rein lesend**:
kein `INSERT`/`UPDATE`/`DELETE`, kein Aufrufpfad aus `main.py`/`worker.py`, kein Endpunkt, kein
Compose-`command`. Ein Test hält beides über den Import-Graphen und über einen Lauf gegen einen
unveränderten Datenbestand fest.

Gemessen wird in fünf Blöcken, und die Blöcke D und E sind die beiden Verwendungen:

- **A — Abdeckung.** Fotos des Projekts mit gemessener Koordinate gegen alle Fotos. Events des
  letzten erfolgreichen Kriterien-Laufs nach Zustand: mit Sehenswürdigkeit (bereits benannt),
  `place_kind='coordinate'`, `'multiple'`, ohne Ortsbezug. Das ist die Obergrenze dessen, was
  überhaupt benannt werden kann.
- **B — Zellen.** Anzahl verschiedener vergröberter Zellen im Projekt, und Zellen je Event. Das
  ist zugleich die Zahl der Anfragen, die ein Lauf je Weg tatsächlich stellte.
- **C — Vergleich.** Je Kandidat (lokaler Datensatz / externer Dienst) und je Zelle: getroffene
  Ebene, ob ein Ortsname vorliegt, ob ein Viertel vorliegt. Aggregiert: Zellen mit Ortsnamen, mit
  Viertel, nur Region/Land, ohne Treffer. Die Aufschlüsselung nach Ebene ist tragend — ob ein
  lokaler Datensatz die Viertel-Ebene überhaupt führt, entscheidet, ob die Viertel-Regel je greift.
- **D — Verwendung „Überschrift".** Wie viele Events bekämen einen Namen, wie viele blieben bei
  Nummer und Zeitspanne, bei wie vielen tritt Gleichnamigkeit im selben Lauf auf, und wie viele
  davon ließen sich per Viertel unterscheiden.
- **E — Verwendung #469.** Für welchen Anteil der **Fotos mit Koordinate** — nicht der Events —
  liefert die Zelle einen unspezifischen Ortsnamen. #469 fragt vor der Event-Bildung; eine Messung,
  die nur Events zählt, misst den halben Nutzen.

Ausgabe: Markdown nach stdout, **Zahlen ohne Koordinaten**. Aufgelöste Namensbeispiele stehen in
einem eigenen, standardmäßig abgeschalteten Abschnitt (`--namen`), damit die Zahlen für sich
weitergegeben werden können. Kein Log dieses Kommandos trägt je eine Koordinate.

Beide Kandidaten stehen bewusst in **wegwerfbarer** Form — die Messung darf die Abhängigkeit nicht
vorwegnehmen, deren Anschaffung sie erst begründen soll:

- **Lokal: GeoNames `allCountries`** (rund 400 MB gepackt, CC-BY-4.0), bezogen per eigenständigem
  Skript, naiv durchsucht — kein Index, keine neue Laufzeit-Abhängigkeit, nicht im Docker-Image.
  **Ausdrücklich nicht `cities1000`/`cities500`:** die filtern nach Bevölkerungszahl,
  nicht nach Feature-Code, und viele `PPLX`-Einträge („section of populated place" — die
  Viertel-Ebene) tragen `population = 0`. Mit dem kleinen Extrakt zu messen hieße, die Frage nach
  der Viertel-Abdeckung negativ vorwegzunehmen, statt sie zu beantworten. Die Ebene kommt aus
  `featureClass`/`featureCode`: Klasse `P` ist ein Ort, Klasse `A` (ADM1–ADM5) ist genau der als
  wertlos eingestufte Fall.
- **Extern: Photon** (öffentliche Instanz, OSM-Daten, Apache-2.0 mit Selbst-Hosting-Pfad). Die
  getroffene Ebene steht in der Antwort im Feld **`type`** — nicht in `layer`, das ausschließlich
  ein Filter-Parameter der **Anfrage** ist und in der Antwort gar nicht vorkommt (belegt am
  CHANGELOG 0.3.3/0.4.0 und an zwei Live-Abrufen, 2026-09-14). `matched_level` kommt damit aus
  `type`. Bewusst **nicht** die öffentliche Nominatim-Instanz (untersagt rasterförmige
  Reverse-Abfragen), **nicht** LocationIQ/Mapbox (befristen bzw. verkaufen das dauerhafte
  Zwischenspeichern, das diese Story als Akzeptanzkriterium trägt), **nicht** OpenCage
  (Gratisstufe ist „testing only").

  **Achtung, Namenskollision — Photons `locality` ist nicht unser `locality`.** Photon staffelt
  `locality` ⊂ `district` ⊂ `city` („Ritterkiez" ⊂ „Kreuzberg" ⊂ „Berlin"). Unser `locality` ist
  der **Ort**, entspricht also Photons `city`; unser `neighbourhood` entspricht Photons
  `district`. Die Abbildung lautet damit `city → locality`, `district → neighbourhood`; Photons
  `locality` wird verworfen. Eine Umsetzung, die Photons `locality` direkt übernimmt, setzt
  systematisch die falsche Ebene als Überschrift — „Ritterkiez" statt „Berlin". Die
  Viertel-Ebene kommt in der Antwort ausschließlich als `district`: `suburb`, `borough` und
  `city_district` erscheinen dort nicht (`suburb` nur als roher `osm_value`).

**Bezug des lokalen Datensatzes — `scripts/fetch-ortsdatensatz.sh`.** Die Datei wird **einmal**
bezogen und liegt dann lokal; sie wird nicht bei jedem Lauf neu geholt. Das Skript bildet den
Hash beim Erstbezug **selbst** und legt ihn daneben; jeder spätere Lauf prüft die lokale Datei
dagegen und bricht bei Abweichung laut ab — kein stiller Rückfall auf den externen Weg und keine
stillschweigend beschädigte Datei. **Ungeschützt bleibt ausdrücklich der Erstbezug**: Dort tragen
allein HTTPS und das Vertrauen in GeoNames.

Ein fester, vorab eingetragener Hash nach dem Muster von `fetch-label-embedder-model.sh` ist hier
**nicht** möglich, und das ist kein Versäumnis, sondern eine Eigenschaft der Quelle: GeoNames
erzeugt `allCountries.zip` nächtlich neu (gemessen am 2026-09-14: Last-Modified 02:58 UTC,
421 MB) und veröffentlicht **keine Prüfsummen** — im Download-Verzeichnis liegen nur die
ZIP-Dateien, keine `.md5`, `.sha256` oder Signatur. Es gibt damit weder einen stabilen Sollwert
noch eine vertrauenswürdige Quelle für einen. Das Modell-Muster trägt dort nur, weil die
Modelldatei unveränderlich und versioniert ist. Ein Neubezug im Quartalsrhythmus ist eine Option
für den **Betriebsfall** und wird von der Wegwahl-ADR entschieden, nicht hier.

Gemessen wird auch, **welche** Schlüssel tatsächlich zurückkommen: ob ein Stadtteil bei der
gewählten Quelle als `suburb`, `borough`, `city_district` oder `district` erscheint, hängt an der
Modellierung des einzelnen Ortes und variiert zwischen Ländern. Die Zuordnung auf `PLACE_LEVELS`
entsteht aus dem Messergebnis, nicht aus einer Doku-Tabelle.

### 2. Datenmodell und Migration (`models.py`, `alembic/versions/<neu>.py`, `project_deletion.py`)

Rein additiv, keine Datenlöschung, kein Nachziehen bestehender Läufe.

- `PlaceLookup` (`__tablename__ = "place_lookups"`): `id`, `project_id` (echter FK auf
  `projects.id`, NOT NULL), `cell_lat`, `cell_lon`, `neighbourhood`, `locality`, `region`,
  `country` (alle `str | None`), `matched_level: str | None`, `source: str`, `resolved_at`.
  `UniqueConstraint(project_id, cell_lat, cell_lon)`.
- `Event.place_name: str | None` — additiv, nullable. Altläufe behalten `NULL`.
- `project_deletion.py`: `place_lookups` ergänzen, Position aus `Base.metadata` **gemessen**, nicht
  geraten. `tests/project_graph.py::build_project_graph` legt eine Zeile an — sonst prüfen die
  beiden Vollständigkeitstests die neue Kante nicht.
- Kein Beutel-Feld für alles, was eine Antwort sonst trägt: Straße und Hausnummer werden am
  Parser-Rand verworfen und erreichen die Datenbank nie.

### 3. Neues Modul `backend/src/photosort/places.py` — rein und DB-frei

```python
PLACE_CELL_DIGITS = 2                  # aus events.py::_EVENT_PLACE_COORDINATE_DIGITS umbenannt
PLACE_LEVELS = ("neighbourhood", "locality", "region", "country")
MAX_PLACE_NAME_LENGTH = 80

def place_cell(lat, lon) -> tuple[float, float]
def sanitize_place_name(raw: object) -> str | None      # Muster sanitize_landmark_name
@dataclass(frozen=True) class PlaceAnswer:  neighbourhood, locality, region, country, matched_level
@dataclass(frozen=True) class PlaceInfo:    neighbourhood, locality, matched_level
class PlaceResolver(Protocol):
    async def resolve(self, cell: tuple[float, float]) -> PlaceAnswer | None: ...
def usable_locality(info: PlaceInfo | None) -> str | None
```

`place_cell` ist die **eine** Rundung; `events.py::_rounded` geht darin auf und `events.py`
importiert sie (Richtung `events → places`, beide rein, kein Zyklus — Muster `haversine_meters`).

`usable_locality` ist die Stufenprüfung an einer Stelle: ein Name gilt als aufgelöst, wenn
`matched_level ∈ {"neighbourhood", "locality"}` **und** `locality` gesetzt ist. Ein Wert außerhalb
von `PLACE_LEVELS` ergibt „kein Name", nie eine 500 (Mitgliedschaftsprüfung statt Cast, Muster
`place_kind`). `matched_level` ist die Angabe des Anbieters, keine Ableitung daraus, welche Spalten
gefüllt sind — eine Antwort auf Regionsebene nennt oft trotzdem eine Stadt, und die gilt hier
nicht.

### 4. Die Namensvergabe in `events.py` — rein, vollständig unit-testbar

- `BuiltEvent` bekommt `place_cells: tuple[tuple[float, float], ...]` — die verschiedenen
  gerundeten **gemessenen** Zellen des Events, sortiert. `_place_of` berechnet sie heute schon und
  wirft sie weg.
- Neu: `assign_place_names(built_events, info_by_cell) -> list[str | None]`, ausgerichtet auf die
  Eventliste. Zwei Durchgänge:
  1. Je Event: trägt es einen Sehenswürdigkeits-Namen → **kein** Ortsname (er ersetzt sie nicht und
     tritt nicht daneben). Sonst die Ortsnamen seiner Zellen sammeln; **genau einer** → das ist
     sein Name, null oder mehrere → keiner.
  2. Über den ganzen Lauf: Ortsnamen zählen. Für jeden mehrfach vergebenen Namen bekommt **genau
     jedes** dieser Events zusätzlich sein Viertel (`"Ort, Viertel"`), sofern über seine Zellen
     genau eines vorliegt — je Event einzeln, die übrigen bleiben beim Ortsnamen. Reißt die
     zusammengesetzte Form `MAX_PLACE_NAME_LENGTH`, bleibt der Ortsname allein stehen.
- Deterministisch, ohne Abhängigkeit von der Eingabereihenfolge; ein einzelnes Event in Berlin
  heißt „Berlin".

**Bewusst so und nicht enger:** die Auflösung läuft über **alle** Zellen des Events, nicht nur über
`place_kind='coordinate'`. Ein Event darf die Zellgrenze streifen (die Ausdehnungsschwelle liegt
bei 1000 m, eine Zelle bei rund 1,1 km) und wäre dann `'multiple'`, obwohl alle Aufnahmen in
derselben Stadt liegen. Trägt eine Menge von Orten genau einen Namen, ist sie keine Menge von
Orten. Ein Event über zwei verschiedene Ortsnamen bleibt dagegen bei Nummer und Zeitspanne.
`place_kind`/`place_lat`/`place_lon` bleiben davon vollständig unberührt.

### 5. Verdrahtung im Worker (`worker.py`)

Neu: `_place_infos(session, project_id, cells, resolver)` — unmittelbar neben `_landmark_names`
und nach demselben Muster (die reine Logik im Modul, der Datenbankzugriff hier). Sie liest die
vorhandenen `place_lookups`-Zeilen **mit ausgeschriebener `project_id`-Bindung**, fragt den
Auflöser nur für die fehlenden Zellen, schreibt jede Antwort als Zeile und committet nicht (die
Transaktionsgrenze gehört dem Aufrufer, Muster `project_deletion`).

In `_build_grouping_and_rankings`, nach `build_events(...)` und vor dem Anlegen der `Event`-Zeilen:

```python
cells = {cell for built in built_events if built.landmark_name is None
         for cell in built.place_cells}
info_by_cell = await _place_infos(session, project_id, cells, resolver)
place_names = assign_place_names(built_events, info_by_cell)
```

Gefragt wird also nur für Events **ohne** Sehenswürdigkeit — das spart Anfragen und setzt das
Akzeptanzkriterium strukturell um.

`resolver` ist ein Parameter von `_build_grouping_and_rankings`, injizierbar wie
`build_landmark_client`; kein automatisierter Test erreicht je ein Netz.

- `run_criterion_scoring` reicht den konfigurierten Auflöser durch.
- `rebuild_run_grouping` reicht **`None`** durch — einen Auflöser, der nur den Bestand liest und
  niemanden fragt. Dieser Pfad läuft in einem Request (Versatz-Endpunkt); ohne diese Grenze könnte
  ein Request-Pfad nach außen wirken. Die Kehrseite ist harmlos: eine noch nie gefragte Zelle
  bleibt dort ohne Namen, bis der nächste Kriterien-Lauf sie beschafft.

Fehlverhalten, drei unterschiedene Ausgänge: **keine Antwort** (Netzfehler, Zeitüberschreitung)
schreibt keine Zeile, sonst vergiftete eine vorübergehende Störung die Zelle dauerhaft; **eine
Antwort ohne brauchbare Ebene** schreibt eine Zeile mit leeren Namensstufen und wird nicht erneut
gefragt; **mehrere Ortsnamen im Event** ergeben keinen Namen. In allen drei Fällen behält das Event
Nummer und Zeitspanne und der Lauf läuft weiter. Geloggt wird ohne Koordinate und ohne Namen; es
entsteht **keine** neue Zählspalte an der Lauf-Zeile.

### 6. Antwort und Oberfläche

- `api/photos.py`: `EventOut.place_name: str | None = None`. Bewusst **nicht** in `EventPlaceOut`:
  `_event_place_out` liefert bei unbekanntem `place_kind` `None`, und ein persistierter Name darf
  damit nicht mitfallen. `EventPlaceOut` bleibt unverändert; eine Koordinate erscheint weiterhin
  nie als Name.
- `frontend/src/utils/timeOfDay.ts::formatEventHeading`: eine dritte Stufe zwischen
  Sehenswürdigkeit und Nummer — `landmark_name` → `place_name` → `Position N`. Die Zeitspanne
  bleibt in jedem Fall Teil der Überschrift. Alle Ansichten (`AlbumDraftPage`,
  `AlbumSelectionPage`, `DraftAlternativesDialog`, `eventGrouping.ts`) gehen durch diese Funktion,
  eine Änderung genügt.
- `place_name` ist freier, extern erzeugter Text und trägt die Auflage von `landmark_name`
  wortgleich: ausschließlich als regulärer React-Textknoten, nie `dangerouslySetInnerHTML`, nie als
  HTML-String-Prop, nie in `href`/`src`/`style`, nie als React-`key`; abgesichert durch einen Test
  im Muster des bestehenden Falls für den Sehenswürdigkeits-Namen.
- `demo_state.py` gibt mindestens einem Demo-Event einen Ortsnamen und zwei weiteren denselben
  Ortsnamen mit verschiedenen Vierteln, damit die Viertel-Regel im Browser sichtbar ist.

### 7. Die Schnittstelle für #469 — bereitgestellt, nicht verwendet

#469 ruft `_place_infos(...)` und `places.usable_locality(...)`. Es bekommt damit die
**unspezifische** Stufe („Berlin"), nie die zusammengesetzte Form — die entsteht ausschließlich in
`events.py::assign_place_names` über die Events eines Laufs und ist von `places.py` aus
strukturell nicht erreichbar. Diese Story verwendet die Auskunft in der Sehenswürdigkeitserkennung
nicht; sie stellt sie nur bereit.

### 8. Doku

`docs/architecture.md` (Datenmodell: `place_lookups`, `events.place_name`; Lesepfad: die dritte
Stufe der Überschrift) und `docs/setup.md` (Aufruf des Messkommandos, ggf. Bezug des lokalen
Ortsdatensatzes) ziehen im selben Pull Request nach — Owner `architect`.

Die Namensnennungspflicht der gewählten Quelle wird sichtbar erfüllt (GeoNames: CC-BY; OSM-basiert:
ODbL) — die Stelle dafür legt die Wegwahl-ADR fest, zusammen mit dem Weg.

### 9. Zuschnitt der zwei Auslieferungen

**Teil 1 — „Messen, bevor gewählt wird"** (Abschnitte 0 und 1, plus das Wegwahl-unabhängige aus 3):
`places.py` nur mit `PLACE_CELL_DIGITS`, `place_cell`, `PLACE_LEVELS`, `MAX_PLACE_NAME_LENGTH`,
`sanitize_place_name`, `PlaceAnswer`, `PlaceInfo`, `PlaceResolver`, `usable_locality`; die
Umbenennung von `events.py::_EVENT_PLACE_COORDINATE_DIGITS`/`_rounded` auf die gemeinsame Stelle;
`place_probe.py` mit beiden wegwerfbaren Auflösern und den fünf Messblöcken;
`scripts/fetch-ortsdatensatz.sh`; `docs/setup.md`. **Nicht** dabei: Migration, `PlaceLookup`,
`events.place_name`, Worker-Verdrahtung, API, Frontend.

**Dazwischen:** Daniel lässt das Kommando laufen, gibt die Zahlen zurück und wählt den Weg (oder
bricht ab). Die Wegwahl-ADR entsteht danach, ihre Nummer wird erst dann vergeben.

**Teil 2 — „Der Name steht"** (Abschnitte 2, 4, 5, 6, 7, 8): Migration, `PlaceLookup`,
`events.place_name`, `project_deletion.py`, `project_graph.py`; der gewählte Auflöser als
`PlaceResolver`-Implementierung; `_place_infos` und die Verdrahtung im Worker;
`assign_place_names` samt `BuiltEvent.place_cells`; `EventOut.place_name`, `formatEventHeading`,
Demo-Daten, Namensnennung; `docs/architecture.md`.

## UI/UX

**Überschriftenform — drei Stufen, sequenziell:**

1. Erkannte Sehenswürdigkeit: `${landmark_name} (${timeRange})` — z.B. `Eiffelturm (10:30–11:45 Uhr)`
2. Aufgelöster Ortsname (neu): `${place_name} (${timeRange})` — z.B.
   `Garmisch-Partenkirchen (10:30–11:45 Uhr)` oder `Berlin, Kreuzberg (10:30–11:45 Uhr)`
3. Keine Ortsangabe: `Position ${position} (${timeRange})`

Die Zeitspanne bleibt in jedem Fall Teil der Überschrift; sie trägt die Unterscheidbarkeit, wenn
mehrere Events denselben Namen tragen und kein Viertel vorliegt.

**Zustände:**

- Event ohne Ortsnamen: Rückfall auf Position N, unverändert zum heutigen Verhalten.
- Zusammengesetzte Form reißt `MAX_PLACE_NAME_LENGTH`: Viertel verwerfen, Ortsname allein; ist
  auch der unbrauchbar, Rückfall auf Position N.
- Umbruch: Die Überschrift ist ein `<h3 className="text-base">` an vier Stellen (`AlbumDraftPage`,
  `AlbumSelectionPage`, `DraftAlternativesDialog` als Dialog-Titel, `eventGrouping.ts` als
  Gruppierungseintrag). Längere Ortsnamen brechen normal um; die Umbruchprobleme des
  Design-Systems auf 360 px betreffen `text-xl sm:text-2xl`, nicht `text-base`.

**Screenreader:** Der Ortsname ist regulärer React-Textknoten, die Zeitspanne wird mitgelesen —
beide gehören semantisch zur Überschrift.

**Design-System:** Keine neuen Token, keine neuen Komponenten; `h3 text-base`, Farbe `--text-h` auf
`--bg`-Grund. Kein Penpot-Entwurf nötig — die Änderung bewegt sich vollständig im bestehenden
Muster.

## Teststrategie

**Grundlage:** `specs/architecture/0002-testkonzept.md`, Sektionen „Ein rein lesendes Kommando im
Produktivpaket, ein gleitkomma-geschlüsselter Zwischenspeicher und eine Vergabe, die über die Menge
entscheidet" (Backend) und „Ein Fremdtext-Nachweis, der mit seiner Seite verschwunden ist"
(Frontend) — dort die Muster, hier die Fälle. Beide Auslieferungen sind für sich grün und für sich
auslieferbar; das Coverage-Gate (Backend ≥ 80 %) gilt je Pull Request.

**Für beide Teile:** kein automatisierter Test erreicht ein Netz. Teil 1 macht das aus einer
Konvention eine Sperre — autouse-Fixture in `backend/tests/conftest.py`, `socket.socket.connect`/
`connect_ex`/`socket.create_connection` erheben einen Fehler. Gegen den Bestand geprüft: die
Backend-Suite bleibt vollständig grün. Jeder Auflöser kommt injiziert herein; ein Test, der den
echten baut, wird laut rot statt still online zu gehen.

### Teil 1 — „Messen, bevor gewählt wird"

Neu: `backend/tests/test_places.py`, `backend/tests/test_place_probe.py`,
`backend/tests/import_closure.py` (der `_import_closure`-Helfer zieht aus `test_demo_state.py` in
ein geteiltes Nicht-`test_*`-Modul, Muster `project_graph.py`). Geändert: `conftest.py`,
`test_events.py`.

**Unit — `test_places.py`** (rein, ohne DB):

- `place_cell`: zwei 40 m auseinanderliegende Punkte ergeben dieselbe Zelle, zwei über die
  Zellgrenze verschiedene; `-0.0 → 0.0` für Breite und Länge **getrennt**; ein Wert auf der
  Rundungsgrenze; `PLACE_CELL_DIGITS == 2` als Literal, weil die Konstante eine
  Datenschutzentscheidung trägt.
- `sanitize_place_name`, im Schnitt der acht Fälle von `TestLandmarkNameSanitisation`: Nicht-String,
  leer, nur Leerzeichen, `\x00`, U+200B, U+202E, Zeilenumbruch zwischen zwei Wörtern, genau
  `MAX_PLACE_NAME_LENGTH` (bleibt), ein Zeichen mehr (`None`, **nicht** gekürzt). Dazu ein
  Gleichheitsfall gegen `sanitize_landmark_name` über eine gemeinsam parametrisierte Tabelle — er
  bricht, sobald jemand eine zweite Sanitisierungsfassung einführt.
- `usable_locality`, als Matrix über `PLACE_LEVELS` × (`locality` gesetzt / `None`). Einzeln:
  `matched_level` auf `region`/`country` **mit** gesetzter `locality` → kein Name (die
  Anbieterangabe gewinnt, nicht die gefüllte Spalte); ein Wert außerhalb des Vorrats → kein Name,
  keine Ausnahme, keine 500; `info` `None` → kein Name. `PLACE_LEVELS` wird in Länge und
  Reihenfolge als Literal festgehalten, sonst liefe eine fünfte Ebene ungeprüft durch die Matrix.
- Strukturell: `places.py` importiert weder `sqlalchemy` noch `models`, und nirgends darin entsteht
  die zusammengesetzte Form „Ort, Viertel" — die Modulgrenze aus ADR 0102 Punkt 4.

**`test_place_probe.py`:**

- **Rein lesend, drei Teile, kein Teil trägt allein:** Import-Graph (`place_probe` steht in keiner
  Hülle von `main`/`worker`, in keinem `command:` einer Compose-Datei, hinter keinem `APIRouter`,
  mit Gegenprobe, dass der Walker überhaupt etwas findet); Syntaxbaum-Wächter gegen jede
  Schreibform (`session.add`/`add_all`/`merge`/`delete`, `commit`, `flush`, `sa.insert`/`update`/
  `delete`, `text(...)` mit DML) mit Mikrotests je Form und Positiv-Gegenproben; und ein echter
  `main()`-Lauf gegen eine dateibasierte SQLite mit Schnappschuss **jeder** Tabelle aus
  `Base.metadata.sorted_tables` davor und danach — gemessen, nie als handgeschriebene Liste. Der
  Formwächter allein bestünde gegen ein Modul, das über eine Hilfsfunktion schreibt; der
  Laufvergleich allein gegen einen Schreibpfad, den die Testlage nicht betritt.
- **Die fünf Blöcke A–E** je gegen einen von Hand ausgerechneten Projektgraphen, je mit einem
  entarteten Fall: A ohne jedes Foto mit Koordinate und ohne erfolgreichen Lauf; B mit einem Event
  über zwei Zellen; C mit je einem Treffer auf jeder der vier Ebenen und einem ohne Treffer; D mit
  Gleichnamigkeit, davon eine per Viertel auflösbar und eine nicht; E mit Fotos in einer Zelle,
  deren Event keinen Namen bekäme — **E zählt Fotos, D zählt Events**, und eine Umsetzung, die E
  aus D ableitet, ist genau hier rot.
- Unbekannte `--project-id`, Projekt ohne erfolgreichen Lauf: laute, leere Ausgabe mit Exit-Code,
  nicht Traceback und nicht stille Null.
- **Ausgabe**, beide Hälften in einem Fall: ohne `--namen` weder Koordinatenziffern noch ein
  aufgelöster Name, mit `--namen` genau die Namen. Die gesuchte Zeichenfolge stammt aus der
  Messlage, nie aus einem allgemeinen Zahlenmuster.
- **Schalter aus ist die Vorgabe:** der externe Auflöser wird gar nicht erst gebaut — eine Fabrik,
  die beim Aufruf bricht, und der Lauf geht trotzdem durch. Die Ausgabe meldet das Ausbleiben,
  statt eine leere Spalte zu zeigen, die als schlechtes Messergebnis gelesen würde.
- **Der ausgehende Rand:** eine ungerundete Eingabe erzeugt in der abgesetzten Anfrage zwei Zahlen
  mit genau `PLACE_CELL_DIGITS` Nachkommastellen (`httpx.MockTransport`, geprüft an der Ziel-URL).
  Der Ziel-Host ist Konstante oder Einstellung, nie ein Wert aus Datenbank oder Parameter
  (Syntaxbaum-Wächter, kein SSRF-Pfad). Zeitgrenze und Mindestabstand über injizierte Zeit.
- **Lokaler Auflöser:** Stufen aus literal geschriebenen GeoNames-Zeilen — `featureClass='A'`/ADM*
  ergibt keine verwendbare Ebene, `P`/`PPLX` die Viertel-Ebene; fehlende Datei bricht laut, ohne
  stillen Rückfall auf den externen Weg. Bezugsskript: der beim Erstbezug selbst gebildete Hash
  wird beim nächsten Lauf geprüft, eine veränderte lokale Datei bricht laut ab.
- **Coverage:** `place_probe.py` liegt in `--cov=photosort` und bekommt **keine** `omit`-Zeile, auch
  nicht für die wegwerfbaren Auflöser.

**`test_events.py` (Bestand):** Die Umbenennung auf `places.place_cell` ändert kein Verhalten und
hat keinen Rot-Zustand — Nachweis nach der Sektion „Nachweis ohne Rot-Grün": kein Testdiff,
identische Testknoten-Menge mit identischem Ausgang, `Stmts` je Datei unverändert. Dazu ein
struktureller Wächter, weil „die Rundung steht an einer Stelle" (ADR 0102 Punkt 2) eine Zusage über
eine **Anzahl** ist: keine zweite Rundung mit Stellenliteral, der alte Konstantenname kommt im
Quellbaum nicht mehr vor.

**Frontend, E2E, `scripts/tests`: in Teil 1 nichts.** `fetch-ortsdatensatz.sh` folgt der Festlegung
zu `scripts/*.sh` (Bezugs-/Verifikations-Wrapping ohne eigene Testsuite).

### Teil 2 — „Der Name steht"

Neu: `backend/tests/test_migration_ortsauskunft.py`, `backend/tests/test_worker_place_names.py`.
Geändert: `test_models.py`, `tests/project_graph.py`, `test_project_deletion.py`,
`test_postgres_ddl_compatibility.py`, `test_events.py`, `test_worker_rebuild_run_grouping.py`,
`test_api_photos.py`, `test_demo_state.py`, `frontend/src/utils/timeOfDay.test.ts`,
`frontend/src/pages/AlbumDraftPage.test.tsx`.

**Migration und Modell.** Muster `test_migration_events.py`: Schema-Nachbau vor der Revision,
`upgrade()`/`downgrade()`, Tabelle und Spalte da beziehungsweise weg, bestehende `events`-Zeilen
überleben beides, und `events.place_name` bleibt nach dem `upgrade` `NULL` — **kein Nachziehen** ist
eine geprüfte Zusage, keine Auslassung. Die Revision kommt in `test_postgres_ddl_compatibility.py`
(der `UniqueConstraint` und die Float-Spalten im Postgres-Dialekt gerendert; SQLite zeigt diese
Fehlerklasse strukturell nicht). `test_models.py`: eine zweite Zeile derselben Zelle im selben
Projekt scheitert am Constraint, **dieselbe Zelle in einem zweiten Projekt geht durch**,
`project_id` trägt einen echten Fremdschlüssel, `Event.place_name` ist nullable. `project_graph.py`
legt eine `PlaceLookup`-Zeile an — ohne sie prüfen die beiden Vollständigkeitstests in
`test_project_deletion.py` die neue Kante nicht.

**`assign_place_names` (`test_events.py`, rein und vollständig unit-testbar):**

- Ein Event, dessen Zellen genau einen Namen liefern, bekommt ihn — auch über **mehrere** Zellen,
  und auch dann, wenn eine der Zellen gar keinen Namen liefert.
- Zwei verschiedene Namen im Event: kein Name.
- Ein einzelnes Event in Berlin heißt „Berlin", ohne Viertel.
- Drei Events, davon zwei gleichnamig — nur diese beiden bekommen ihr Viertel, das dritte bleibt
  unberührt.
- Zwei gleichnamige Events, **nur eines mit Viertel**: nur dieses bekommt den Zusatz.
- Zwei gleichnamige Events ohne verfügbares Viertel: beide bleiben beim Ortsnamen.
- Ein Event mit zwei **verschiedenen** Vierteln über seine Zellen: kein Viertel.
- Die zusammengesetzte Form reißt `MAX_PLACE_NAME_LENGTH`: der Ortsname bleibt allein stehen, **je
  Event einzeln** — ein zweites gleichnamiges Event mit kurzem Viertel behält seinen.
- **Ein Event mit Sehenswürdigkeit bekommt keinen Ortsnamen — und die Messlage muss so gebaut sein,
  dass es einen bekommen könnte:** seine `place_cells` sind nicht leer und lösen auf. `_place_of`
  kehrt bei gesetztem `landmark_name` zurück, bevor es die Zellen bildet; ein Fall mit leeren
  Zellen wäre vakuum-grün und bliebe es auch, wenn die Ausnahme ersatzlos entfiele. Zweite Hälfte
  im selben Fall: ein Landmark-Event in Berlin löst bei einem gleichnamigen Nicht-Landmark-Event
  **keine** Viertel-Ergänzung aus.
- Determinismus über **Permutationen** der Eingabe, verglichen je Event, nicht je Position; dazu
  die positionstreue Rückgabe — eine um eins verschobene Zuordnung ist der zweite stille Fehler
  dieser Form.
- `BuiltEvent.place_cells` ist sortiert und dublettenfrei; `place_kind`/`place_lat`/`place_lon`
  bleiben unverändert (Regressionsfall an den bestehenden Erwartungen).

**Worker (`test_worker_place_names.py`, Auflöser als zählendes Test-Double):**

- `_place_infos`: leere Zellmenge → keine Anfrage und keine Abfrage; nur die fehlenden Zellen
  werden gefragt; dieselbe Zelle in zwei Events desselben Laufs → **genau eine** Anfrage; die
  Zeilen eines **anderen** Projekts werden nicht gelesen; kein `commit` innerhalb.
- **Der Treffernachweis nach echtem Rundgang:** zweiter Lauf über dieselben Zellen nach
  `flush`/`expire` und erneutem `select` stellt **null** Anfragen. Der Gleitkomma-Schlüssel ist
  genau die Stelle, an der ein nie treffender Speicher still entsteht — ein Test, der aus derselben
  In-Memory-Abbildung wiederliest, in die er geschrieben hat, beweist das nicht.
- **Die drei Ausgänge, je zweimal gemessen.** Auflöser bricht: keine Zeile, Event ohne Namen, Lauf
  `successful`, **zweiter Lauf fragt erneut**. Antwort ohne brauchbare Ebene: genau eine Zeile mit
  leeren Namensstufen, Event ohne Namen, **zweiter Lauf fragt nicht erneut**. Zwei Namen im Event:
  kein Name, beide Zellen aber abgelegt. Ohne den jeweils zweiten Lauf sehen die ersten beiden
  Ausgänge gleich aus — und genau diese Verwechslung vergiftet eine Zelle dauerhaft.
- Gefragt wird nur für Events **ohne** Sehenswürdigkeit: ein Lauf mit einem Landmark-Event, dessen
  Zelle nirgends sonst vorkommt, stellt für diese Zelle keine Anfrage.
- **Log:** `caplog` über `places.py`, `place_probe.py` und `worker.py` — kein Datensatz trägt eine
  Koordinatenziffer der Messlage oder einen aufgelösten Namen, geprüft über `record.getMessage()`
  **und** `record.args`, sonst rutscht ein `%s`-Argument durch. Keine neue Zählspalte an der
  Lauf-Zeile.
- `run_criterion_scoring` reicht den konfigurierten Auflöser durch; steht
  `EXTERNAL_PLACE_LOOKUP_ENABLED` auf `false`, wird keiner gebaut und der Lauf geht durch.
- Umsetzungsauflage aus der Testbarkeit: `resolver` bekommt in `_build_grouping_and_rankings`
  **keinen Vorgabewert**. Mit Vorgabe `None` wäre eine vergessene Aufrufstelle ein stiller
  Totalausfall der Auflösung; ohne Vorgabe meldet ihn `mypy --strict`.

**`rebuild_run_grouping`.** Ein Fall mit beiden Hälften: eine Zelle **mit** abgelegter Auskunft
trägt nach dem Neuaufbau ihren Namen, eine Zelle **ohne** bleibt namenlos, und die Zeilenzahl in
`place_lookups` ist unverändert. Die erste Hälfte allein bestünde auch dann, wenn dieser Pfad das
Merkmal gar nicht mehr kennte. Dazu ein Syntaxbaum-Wächter auf die Aufrufstelle (kein beschaffender
Auflöser), mit der Gegenprobe, dass er die Aufrufstelle in `run_criterion_scoring` nicht mitfängt.

**API.** `place_name` steht an `EventOut`, nicht an `EventPlaceOut`; der tragende Fall ist ein Event
**mit** Namen und **unbekanntem** `place_kind`: `place` ist `null`, der Name steht da. Bei einer
Unterbringung in `EventPlaceOut` fiele er still mit. Dazu: `place_kind='multiple'` mit Namen liefert
weiterhin keine Koordinate, ein Altlauf ohne Namen liefert `null` und nicht `""`.

**Demo.** Ein Demo-Event mit Ortsnamen und zwei mit **demselben** Ortsnamen und verschiedenen
Vierteln — ohne diesen Kardinalitätsfall ist die Viertel-Regel im Browser unsichtbar und
`browse-app` kann sie nicht zeigen. Die Literale bestehen `sanitize_place_name` unverändert, und
`demo_state` erreicht keinen Auflöser (Import-Graph).

**Frontend.** `utils/timeOfDay.test.ts`, drei Stufen: alle drei belegt → die Sehenswürdigkeit
gewinnt; `landmark` mit `landmark_name: null` **und** gesetztem `place_name` → der Ortsname, nicht
`Position N`; `place: null` mit `place_name` → der Ortsname; `place_name: ''` → `Position N`; die
zusammengesetzte Form unverändert; die Zeitspanne in jedem Fall.
**Der XSS-Nachweis gehört an die Rendering-Stelle**, nicht in `timeOfDay.test.ts`: Der bestehende
Fall für `landmark_name` dort belegt nur, dass die Funktion nichts interpretiert — das Escaping
leistet React, und der zugehörige DOM-Fall lag in `CurateCategoriesPage.test.tsx` und ist mit dem
Umbau auf die Albumauswahl ersatzlos entfallen. Neu in `AlbumDraftPage.test.tsx`, Form von
`PhotoCard.test.tsx`: feindlicher `place_name`, der Text erscheint wörtlich,
`document.querySelector('img[src="x"]')` ist leer, `window.__pwned` bleibt `undefined`. Der
Docstring-Verweis in `api/photos.py` zeigt auf die verschwundene Datei und wird umgestellt.
`eventGrouping.test.ts` und `DraftAlternativesDialog.test.tsx` bekommen je einen Fall, dass die
Überschrift mit Ortsnamen dort ankommt.

**E2E: nichts.** Das Aufnahmekriterium (nur, was jsdom prinzipiell nicht kann) ist nicht erfüllt;
die Überschrift bleibt `h3 text-base` und ist über `no-horizontal-scroll.spec.ts` gedeckt.

### Was diese Strategie nicht abdeckt

Ob ein Ortsdienst für eine Zelle den **richtigen** Ort nennt; die Zahlen des Messlaufs gegen
Daniels echtes Projekt; Durchsatz und Speicherverhalten des naiven Durchgangs durch den lokalen
Datensatz; die Integrität des Erstbezugs dieses Datensatzes.

## Security

**Einstufung: sicherheitsrelevant und tragend.** Die Story löst die beiden Aussagen ab, die das
Projekt bisher als Schutz geführt hat: „Ortsnamen aus Koordinaten sind ausgeschlossen" (ADR 0029
Punkt 6) und „ein abgeleiteter Ortswert wird nie persistiert" (ADR 0072). Damit entstehen ein
möglicher **zweiter Empfänger** von Ortsdaten der Familie und mit `place_lookups` die
**dauerhafteste Ortsspur** des Systems. Die projektweite Einschätzung ist im selben Zug neu
gestellt: `specs/architecture/0003-securitykonzept.md`, Abschnitt „Standortdaten".

### S1 — Der Schalter: `EXTERNAL_PLACE_LOOKUP_ENABLED`, Vorgabe `false`

Betriebseinstellung (`Settings.external_place_lookup_enabled: bool = False`, `.env.example`), kein
Projektfeld, kein UI-Element, keine Einwilligungsmechanik. Er schaltet genau eines: **ob ein
externer Dienst nach einem Ort gefragt wird** — im Worker und im Messkommando gleichermaßen.

Steht er auf `false`: kein externer Auflöser wird gebaut (Muster `build_landmark_client` bei
fehlender Einwilligung — kein Client-Aufbau „auf Verdacht"), keine Anfrage geht hinaus, keine neue
Zeile wird beschafft. Bereits vorhandene `place_lookups`-Zeilen werden weiter gelesen; Events ohne
Auskunft behalten Nummer und Zeitspanne, der Lauf läuft weiter. Der Prozess startet normal — die
Vorgabe muss ein arbeitsfähiger Zustand sein, kein Startfehler.

**Ausschalten stoppt den Abfluss, es löscht die Spur nicht** — das tut allein die Projektlöschung.
Fällt die Wegwahl auf den lokalen Datenbestand, ist der Schalter wirkungslos und bleibt es; er wird
dann nicht für etwas anderes umgewidmet, weil sein Name genau eine Sache benennt.

### S2 — Was das System verlässt, ist strukturell begrenzt, nicht zugesagt

`PlaceResolver.resolve` nimmt ausschließlich `tuple[float, float]` aus `places.py::place_cell`
entgegen. Weder Foto noch Event noch eine ungerundete Koordinate sind über diese Signatur
erreichbar. **Zweite, unabhängige Schranke am ausgehenden Rand:** Der externe Auflöser formatiert
beide Zahlen mit genau `PLACE_CELL_DIGITS` Nachkommastellen in die Anfrage — eine ungerundete Zahl
ist in der abgesetzten Zeichenkette nicht darstellbar, selbst wenn sie ihn erreichte. Ohne diese
zweite Schranke hinge das Akzeptanzkriterium an einer Aufrufstelle statt an dem Rand, an dem die
Daten tatsächlich abfließen.

### S3 — `PLACE_CELL_DIGITS = 2` — geprüft und bestätigt, als Sicherheitsentscheidung

Die Zelle misst rund 1,1 km × 0,7 km (mittlere Breiten). Sie bleibt bei zwei Nachkommastellen:

- Es ist **dieselbe** Körnung, die `events.place_lat`/`place_lon` bereits persistiert und
  `PhotoOut.cluster_place` bereits an den Browser ausliefert. Die neue Tabelle führt keine feinere
  Auflösung ein als der Bestand.
- Gröber verfehlt den Zweck: eine Zelle von rund 11 km (eine Nachkommastelle) trifft in einer Stadt
  mehrere Gemeinden, macht die Viertel-Regel strukturell unerfüllbar und liefert regelmäßig den
  falschen Ortsnamen. Der Schutzgewinn wäre zudem gering — die Aussage liegt nicht in der Auflösung
  der einzelnen Zelle, sondern in der **Menge** der Zellen eines Projekts, und die überlebt jede
  Vergröberung.
- Feiner ist untersagt: drei Nachkommastellen (rund 110 m) treffen Wohnadress-Auflösung.

**Eine Änderung dieser Konstante ist eine Datenschutzänderung und nimmt `place_lookups` mit:** die
Migration, die sie ändert, leert die Tabelle. Sonst bleiben die unter der alten Körnung abgelegten
Zeilen unerreichbar, aber vorhanden liegen — eine Vergröberung wäre gerade für den Altbestand
wirkungslos, für den sie gedacht war.

### S4 — Der Messlauf ist der erste tatsächliche Abfluss, nicht seine Vorstufe

`place_probe.py` fragt beide Kandidaten über die Zellen eines **echten** Projekts. Auflagen:

- Der externe Kandidat läuft nur bei gesetztem `EXTERNAL_PLACE_LOOKUP_ENABLED` und **meldet sein
  Ausbleiben in der Ausgabe**, statt eine leere Spalte zu zeigen, die als schlechtes Messergebnis
  gelesen würde.
- Gefragt wird über **alle** verschiedenen Zellen des Projekts (Daniel, 2026-09-14) — kein Deckel,
  keine Stichprobe. Eine gedeckelte Ziehung wurde erwogen und verworfen, weil die Blöcke D und E
  sonst Hochrechnungen statt Auszählungen lieferten. Die Folge steht unten als Restrisiko.
- Gefragt wird über die **Menge** der verschiedenen Zellen, nie je Event — sonst ginge die
  Verweildauer je Ort mit hinaus.
- Jede Anfrage trägt eine Zeitgrenze und einen Mindestabstand zur vorigen (Muster `cloud_vision`).
- Das Kommando bleibt von jedem Endpunkt, jedem Compose-`command` und jedem automatischen Pfad
  fern — der Abfluss tritt nur ein, wenn Daniel ihn tippt.
- **Die Bedingungsprüfung des Anbieters gehört vor den Messlauf, nicht in die Wegwahl-ADR danach.**
  Die beiden Ausschlussgründe aus ADR 0102 Punkt 6 (dauerhaftes Zwischenspeichern untersagt,
  rasterförmige Abfragen untersagt) treffen den Messlauf genauso wie den Betrieb; wer sie erst
  hinterher am Wortlaut belegt, hat die untersagte Abfrage bereits abgesetzt. **Geführt am
  2026-09-14, Ergebnis: beide Kandidaten zulässig.** Photons Bedingungen untersagen weder das
  dauerhafte Speichern noch rasterförmige Abfragen; die dauerhafte Speicherung ist über die
  OSM-Geocoding-Guideline ausdrücklich erlaubt („Geocoding Results may be stored (either
  permanently or temporarily)"). GeoNames ist über CC BY 4.0 unbefristet abgedeckt.
- **Die Grenze der OSM-Guideline ist die Flächendeckung, nicht das Raster.** Eine Sammlung von
  Ergebnissen darf kein „systematic attempt to aggregate all or substantially all Primary
  Features … within a geographic area city-sized or larger" sein. Daraus folgt eine
  Umsetzungsauflage: Gefragt wird ausschließlich über die **tatsächlich besuchten** Zellen aus dem
  Projektbestand. Ein Messkommando, das ein Rechteck flächendeckend abrastert, risse diese Grenze.
- **Ratenbegrenzung:** Photon nennt **keine Zahl** — nur „please be fair, extensive usage will be
  throttled". Der Mindestabstand im Messkommando ist deshalb eine begründete Selbstauflage und
  lässt sich aus keiner Quelle ableiten. Die öffentliche Instanz ist erklärtermaßen eine
  Demo-Instanz; für den Dauerbetrieb ist das ein Verfügbarkeitsrisiko, das die Wegwahl-ADR
  bewerten muss (Selbst-Hosting ist der vom Betreiber genannte Ausweg).
- **Namensnennung:** an die Anwendung, nicht an die einzelne `place_lookups`-Zeile — OSM/ODbL
  („credit OpenStreetMap and its contributors") bzw. GeoNames/CC-BY.
- Betriebshinweis in `docs/setup.md`: gemessen wird an einem Reiseprojekt, nicht am Alltagsbestand
  — die Zellen des Wohnorts tragen zur Messung nichts bei, gehen aber mit hinaus.

### S5 — Die Ausgabe trennt Zahlen von Ortsangaben

Die Vorgabe-Ausgabe trägt **keine Koordinate, keinen aufgelösten Ortsnamen und keinen
OpenCloud-Pfad des Projekts** — nur Kennzahlen und die Projekt-Id. Damit sind die Zahlen als Ganzes
weitergebbar, ohne Einzelfallprüfung. Aufgelöste Namen stehen ausschließlich im abschaltbaren
`--namen`-Abschnitt, und der trägt seinen eigenen Warnsatz: ein Ortsname **ist** die Ortsangabe —
ihn wegzugeben ist dasselbe wie die Zelle wegzugeben. Block C wird aggregiert ausgewiesen; eine
Zeile je Zelle trägt die Zelle nie als Kennung.

### S6 — `place_lookups` als dauerhafte Ortsspur

- Echter Fremdschlüssel auf `projects.id`, `NOT NULL`. Der Lesepfad bindet `project_id`
  ausgeschrieben und fällt **nie** auf die Zeile eines anderen Projekts zurück, wenn die eigene
  fehlt — ein solcher Rückfall wäre der stille Weg, auf dem die Lebensdauer-Bindung aufhört zu
  gelten.
- `project_deletion.py` führt die Tabelle (Position aus `Base.metadata` gemessen),
  `tests/project_graph.py::build_project_graph` legt eine Zeile an. Ohne diese Zeile prüfen die
  beiden Vollständigkeitstests die neue Kante nicht, und „mit dem Projekt verschwindet die
  Ortsspur" wäre unbelegt.
- Kein Beutel-Feld: Straße und Hausnummer fallen am Parser-Rand und erreichen die Datenbank nie.
  Das ist **Datensparsamkeit, keine Injektionsabwehr** (siehe S9).

### S7 — `place_name` und die Namensstufen sind Fremdtext — auf beiden Wegen

Ein Ortsdatensatz wie GeoNames ist ebenso von Dritten geschrieben wie eine Dienstantwort; die
Auflage hängt an der Herkunft des Textes, nicht an der Anwesenheit eines Netzwerks.

- Zeichensanitisierung am Parser-Rand mit **derselben** Funktion wie die beiden Cloud-Pfade
  (`cloud_vision.py::_sanitize_label_text`, nie eine zweite Fassung davon), danach die Längengrenze
  `MAX_PLACE_NAME_LENGTH`.
- **Verworfen wird ganz, nie abgeschnitten.** Das ist hier nicht Hygiene, sondern Korrektheit:
  `assign_place_names` **vergleicht** Ortsnamen über die Events eines Laufs — zwei verschiedene, auf
  dieselbe Länge gekappte Namen wären ein Name, und die Viertel-Regel griffe für Events, die gar
  nicht am selben Ort liegen.
- Je Stufe einzeln geprüft: eine unbrauchbare Stufe wird `NULL`, nicht die ganze Antwort verworfen.
  Ist `locality` darunter, gilt „kein Name aufgelöst".
- Die zusammengesetzte Form „Ort, Viertel" entsteht aus zwei bereits sanierten Stufen und wird
  gegen `MAX_PLACE_NAME_LENGTH` erneut geprüft; reißt sie, bleibt der Ortsname allein stehen.
- `matched_level` wird an **beiden** Rändern gegen `PLACE_LEVELS` geprüft: Schreibrand — außerhalb
  des Vorrats heißt `NULL`; Lesepfad — Mitgliedschaftsprüfung statt Cast, nie eine 500. `source`
  stammt aus einem geschlossenen eigenen Vorrat und nie aus der Antwort.

### S8 — Rendering und Kontrollflusswirkung

`place_name` erscheint ausschließlich als regulärer React-Textknoten — nie
`dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in `href`/`src`/`style`, **nie als
React-`key`**. Die Schlüssel-Auflage ist hier nicht nur XSS-Hygiene: Gleichnamigkeit ist der
Normalfall, den diese Story eigens behandelt, und ein doppelter Schlüssel bringt die
Listenabgleichung durcheinander.

Bezifferte obere Schranke: Der Name wirkt ausschließlich auf die **Überschrift** eines Events —
nicht auf `place_kind`, nicht auf Event-Grenzen, nicht auf einen Partitionsschlüssel, nicht auf
eine Kategorie- oder Rangfolgeentscheidung. Eine bösartige Antwort erreicht höchstens, dass alle
Events eines Laufs gleich heißen und deshalb ihr Viertel angehängt bekommen.

### S9 — Die Antwort des Dienstes ist eine fremde HTTP-Antwort, nicht nur ein Textfeld

- Zeitgrenze je Anfrage und Mindestabstand zwischen zwei Anfragen sind Muss: eine hängende
  Fremdantwort hielte sonst den Kriterien-Lauf an, bis der Fortschritts-Watchdog ihn für hängend
  erklärt (dieselbe Rechnung wie ADR 0074).
- Größe und Struktur der Antwort werden begrenzt gelesen.
- **Straße und Hausnummer am Parser-Rand zu verwerfen reicht als Injektionsabwehr nicht** — es ist
  Datensparsamkeit. Gegen Injektion tragen Sanitisierung (S7), die Längengrenze und der Umstand,
  dass der Text in **dieser** Story in keine Modellanfrage eingeht.
- Der Ziel-Host ist eine Konstante oder eine Betriebseinstellung, nie ein Wert aus Datenbank oder
  Request — kein SSRF-Pfad.

### S10 — Der Request-Pfad `rebuild_run_grouping` fragt niemanden

Er bekommt `None` als Auflöser, weil er in einem Request läuft. Ohne diese Grenze könnte ein
Request-Pfad nach außen wirken: eine authentifizierte Anfrage — auch eine mit gestohlenem JWT —
löste Anfragen an einen Dritten aus, die Antwortzeit eines Fremddienstes würde zur Antwortzeit des
Endpunkts, und der Abfluss wäre von dem bewusst gestarteten Lauf abgekoppelt, an dem er hängen
soll. Die Kehrseite ist harmlos: eine nie gefragte Zelle bleibt dort ohne Namen. Ebenso:
`demo_state.py` schreibt Ortsnamen als Literale und ruft nie einen Auflöser.

### S11 — Logs

Koordinaten und Ortsnamen gehören in kein Log — weder ein angenommener noch ein verworfener Wert,
in keinem der beteiligten Module (`places.py`, `place_probe.py`, `worker.py::_place_infos`).
Geloggt wird ein festes Grund-Token plus Id, nach dem Muster von `exif.py` und
`remote_classification.py::_CONFIDENCE_REASON_*`. Ein Log ist eine schwächer geschützte und länger
lebende Oberfläche als die Datenbank.

### S12 — Die Schnittstelle für #469 trägt die eigentliche Injektionsfrage

Diese Story stellt `usable_locality(...)` bereit; #469 führt die Ortsauskunft in die
Sehenswürdigkeitserkennung ein, also in einen Pfad mit einer Modellanfrage. Ein fremderzeugter
Ortsname in einer Modellanfrage ist ein **Datum, nie eine Anweisung**: er gehört in ein
abgegrenztes Feld, und seine Längengrenze ist die Obergrenze der einschleusbaren Nutzlast. Die
Auflage steht hier, weil die Schnittstelle hier entsteht; #469 bekommt ihretwegen eine eigene
Security-Konsultation.

### Bewusste Abweichung: keine projektweite Einwilligung

Der Cloud-Vision-Schalter gated Bilddaten, auf denen Dritte abgebildet sind (Kinder, Art. 8 DSGVO)
— er dokumentiert einen Einwilligungsmoment für Daten von Personen, die die App nicht bedienen. Die
vergröberte Ortsangabe betrifft ausschließlich das Unterwegssein der beiden Nutzer selbst. Eine
projektweite Ja/Nein-Schaltfläche, die beide gleichermaßen umlegen können, fügte dem nichts hinzu,
was der Betriebsschalter nicht schon leistet. Nicht technisch lösbar und deshalb benannt: dass der
zweite Nutzer weiß, dass dieser Schalter existiert und was er tut, ist eine Absprache, kein
Mechanismus.

### Ausdrücklich geprüft und ohne Befund

Kein neuer Endpunkt und kein neuer Auth-Pfad (`EventOut.place_name` ist ein additives Feld an einem
bereits geschützten Lesepfad); keine nutzerabhängige Antwortmenge, die Cache-Schlüssel-Auflage aus
`api/photos.py::_to_photo_out` wächst nicht; kein neues Secret (der Weg trägt keinen API-Key;
bekäme er einen, gilt das `anthropic_api_key`-Muster unverändert); keine Bilddaten in diesem Pfad;
kein Kostenpfad, der ein gestohlenes JWT interessant machte, weil der einzige beschaffende Pfad der
Worker-Lauf ist.

**Mit Befund: der lokale Ortsdatensatz lässt sich nicht gegen einen festen Hash pinnen.** Das
`fetch-label-embedder-model.sh`-Muster trägt hier nicht — GeoNames erzeugt `allCountries.zip`
nächtlich neu (Stand 2026-09-14: 02:58 UTC, 421 MB), ein fester Hash wäre am Folgetag rot, und
GeoNames veröffentlicht **überhaupt keine Prüfsummen** (keine `.md5`/`.sha256`, keine Signatur), es
gibt also gar keinen vertrauenswürdigen Sollwert. Beim Modell trägt der Pin nur, weil die Datei
unveränderlich und versioniert ist. **Regelung (Daniel, 2026-09-14):** Die Datei wird **einmal**
bezogen und liegt dann lokal, nicht bei jedem Lauf neu; `scripts/fetch-ortsdatensatz.sh` bildet den
Hash beim Erstbezug selbst und legt ihn daneben, jeder spätere Lauf prüft die lokale Datei dagegen
und bricht bei Abweichung **laut** ab. Das erkennt jede Veränderung **nach** dem Erstbezug; der
Erstbezug selbst bleibt ungeschützt und ist als Restrisiko geführt. Die Datei liegt weiterhin nicht
im Image und nicht im Repository.

### Bewusst akzeptierte Restrisiken (Daniel, 2026-09-14)

Alle drei stehen mit voller Begründung im Sicherheitskonzept; hier die Entscheidung und ihre Folge.

- **Die Ortsspur fällt erst mit dem Projekt.** `place_lookups` ist lauf-unabhängig. Wer GPS aus
  einer Quelldatei entfernt, erreicht die bereits abgelegte Ortsauskunft damit **nicht** — sie
  bleibt unter ihrer Zelle stehen, bis das Projekt gelöscht wird. Es gibt dafür bewusst keinen
  zweiten Weg: keine dokumentierte `DELETE`-Anweisung, kein Leeren je Lauf. Getragen von der
  Körnung (rund 1,1 km, kein Personen- und kein Zeitbezug an der Zeile), davon, dass kein neuer
  Empfänger entsteht, und von der testgeprüften Vollständigkeit der Projektlöschung.
- **Der Messlauf fragt über alle Zellen.** Die Reiseroute des gemessenen Projekts geht in ihrer
  vollen Auflösung von rund 1,1 km **einmalig und nicht rücknehmbar** an einen Dritten — zu einem
  Zeitpunkt, an dem noch nicht entschieden ist, ob dieser Weg überhaupt genommen wird. Fällt die
  Messung dürftig aus und die Wegwahl lautet „lokal", macht das diesen Abfluss nicht ungeschehen.
  Getragen davon, dass es ein einzelnes, von Daniel selbst getipptes Kommando ist, dass die
  Zellmenge ohne Verweildauer und ohne Zeitbezug hinausgeht und der Empfänger keinen Personenbezug
  dazu erhält.
- **Der Erstbezug des lokalen Ortsdatensatzes ist ungeschützt** — ein Integritäts-, nicht nur ein
  Verfügbarkeitsrisiko, und darin anders als ADR 0033. Der selbst gebildete Hash schützt jede
  spätere Prüfung, nicht den ersten Abruf; dort tragen allein HTTPS und das Vertrauen in GeoNames.
  Eine an der Quelle oder auf dem Weg veränderte Datei würde als Sollwert übernommen und von jeder
  Folgeprüfung bestätigt. Getragen davon, dass der Schaden auf falsche Ortsnamen in
  Event-Überschriften begrenzt ist: die Werte laufen durch dieselbe Sanitisierung und Längengrenze
  wie jeder andere Fremdtext (S7), steuern keinen Kontrollfluss außerhalb der Überschrift (S8) und
  erreichen keinen Secrets-, Auth- oder Bilddatenpfad.

## Entscheidungen

- **Zuschnitt (Daniel, 2026-09-14):** Zwei Pull Requests an #434 — Teil 1 liefert nur das
  Messkommando, Teil 2 die Auflösung auf dem gemessenen Weg. Closing-Keyword nur im letzten PR.
- **Sicherheitsreihenfolge (Daniel, 2026-09-14):** Die Standortdaten-Einschätzung wird neu
  gestellt, **bevor** das Messkommando gebaut wird; die externe Anfrage hängt zusätzlich an einem
  standardmäßig ausgeschalteten Schalter.
- **ADR 0102** (neu, `Accepted`) trägt die sechs Architekturentscheidungen. ADR 0029 (Punkt 6) und
  ADR 0072 sind im Kopf als teilweise abgelöst vermerkt; ihre übrigen Aussagen gelten weiter.
- **Wegwahl-ADR:** noch offen, entsteht nach dem Messlauf mit den gemessenen Zahlen als Begründung.
  Prüft am Wortlaut des Anbieters: dauerhaftes Zwischenspeichern erlaubt, rasterförmige Abfragen
  nicht untersagt, Namensnennungspflicht.
- **Anbieter-Ausschlüsse vor jeder Messung:** Mapbox, LocationIQ und OpenCage scheiden aus, weil
  sie dauerhaftes Zwischenspeichern befristen, verkaufen oder nur zum Testen erlauben — die
  Wiederverwendung der Auskunft ist hier Akzeptanzkriterium. Die öffentliche Nominatim-Instanz
  scheidet aus, weil sie rasterförmige Reverse-Abfragen wörtlich untersagt und PhotoSort
  bauartbedingt so fragt. Selbst gehostetes Nominatim bleibt unberührt.
- **Ortsspur (Daniel, 2026-09-14):** Die Ortsauskunft fällt erst mit dem Projekt — kein zweiter
  Weg, sie loszuwerden, kein Leeren je Lauf. Als Restrisiko ausgeschrieben (`## Security`).
- **Messumfang (Daniel, 2026-09-14):** Der Messlauf fragt über **alle** Zellen des Projekts, keine
  Stichprobe — damit die Blöcke D und E Auszählungen statt Hochrechnungen liefern. Als Restrisiko
  ausgeschrieben.
- **Bezug des Ortsdatensatzes (Daniel, 2026-09-14):** Einmaliger Bezug statt Bezug je Lauf; der
  Hash entsteht beim Erstbezug selbst und trägt jede spätere Prüfung der lokalen Datei. Ein Pin
  gegen einen veröffentlichten Sollwert ist bei GeoNames nicht möglich — die Datei wird nächtlich
  neu erzeugt und es gibt keine Prüfsummen (gemessen 2026-09-14). Quartalsweiser Neubezug ist eine
  Option für den Betriebsfall und Sache der Wegwahl-ADR.
- `architect` konsultiert (Schritt 1): ADR 0102 und der Abschnitt „Architektur / Umsetzung".
- `ux-ui-designer` konsultiert (Schritt 2): dritte Stufe der Event-Überschrift, kein Entwurf nötig.
- `test-engineer` konsultiert (Schritt 3): Teststrategie je Auslieferung, neun geschärfte
  Akzeptanzkriterien, Testkonzept ergänzt.
- `security-engineer` konsultiert (Schritt 3): zwölf Auflagen, Schalter, drei akzeptierte
  Restrisiken, Sicherheitskonzept fortgeschrieben.
- **Prüftiefe der wegwerfbaren Auflöser** (`test-engineer`, technische Detailentscheidung):
  Zählblöcke in voller Tiefe, weil ihre Zahlen eine nicht rücknehmbare Wegwahl tragen; die Auflöser
  selbst nur an ihren Rändern; kein `omit` im Coverage-Setup.

## Offene Fragen

- Löst Nominatim im `admin`-Stil (ohne Straßendaten) beliebige Zellen brauchbar auf? Nur für den
  Selbst-Hosting-Fall erheblich; die öffentliche Instanz bleibt ausgeschlossen.
- **Beantwortet am 2026-09-14:** Photons Ebenenangabe steht in der Antwort als `type`; `layer` ist
  nur Anfrage-Filter. Die Viertel-Ebene kommt ausschließlich als `district`.
- Trägt Photons `city` auch außerhalb Deutschlands den Ort, oder rutscht die Ebene in manchen
  Ländern auf `county`/`state`? Die beiden Belegabrufe lagen beide in Berlin — die Ländervarianz
  ist ungeprüft und ist genau das, was Block C des Messlaufs beantwortet.

## Out of Scope

- Events von Hand umbenennen.
- Eine Karte oder eine andere neue Ansicht.
- Ortsnamen für einzelne Fotos statt für Events.
- Namen für bereits berechnete Läufe nachziehen.
- Die Verwendung der Ortsauskunft in der Sehenswürdigkeitserkennung selbst — diese Spec stellt sie
  bereit, #469 entscheidet, wie sie dort eingeht.
