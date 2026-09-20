# 0506 - Cluster entsprechen einem zusammenhängenden Anlass

**Status:** Implemented — neun Pull Requests:
[#512](https://github.com/TheRealKoller/photosort/pull/512),
[#515](https://github.com/TheRealKoller/photosort/pull/515),
[#516](https://github.com/TheRealKoller/photosort/pull/516),
[#517](https://github.com/TheRealKoller/photosort/pull/517),
[#518](https://github.com/TheRealKoller/photosort/pull/518),
[#519](https://github.com/TheRealKoller/photosort/pull/519),
[#520](https://github.com/TheRealKoller/photosort/pull/520),
[#521](https://github.com/TheRealKoller/photosort/pull/521),
[#522](https://github.com/TheRealKoller/photosort/pull/522)
**Erstellt:** 2026-09-18
**Bezug:** [Issue #506](https://github.com/TheRealKoller/photosort/issues/506), ADR
[`0117`](../decisions/0117-der-anlass-als-einheit-eigene-schwellen-dauergrenze-und-mindestgroesse.md),
ADR
[`0118`](../decisions/0118-sehenswuerdigkeit-trennt-nicht-mehr-und-eine-eigene-ausdehnungsgrenze-fuers-zusammenlegen.md),
ADR [`0119`](../decisions/0119-der-motivwechsel-vermerkt-eine-grenze-statt-eine-zu-eroeffnen.md)

**Umfang:** rund 1300 Zeilen zu 100 Zeichen gegen einen Richtwert von 200. Die Story trägt zwei
Vorhaben in einem — erst messen, dann ändern —, und beide brauchen ihren Teil: sechs Messblöcke mit
je eigener Auflage, was die Ausgabe tragen darf, sieben Konstanten, und ein Messprotokoll, das der
Gegenstand der Abnahme ist. Dazu kommen die Zusicherungen, deren Ausfallrichtung benannt sein muss,
weil sie sonst still brechen. Den größten Teil trägt das **Messprotokoll**: Fünf Messungen haben
nacheinander vier tragende Annahmen dieser Spec widerlegt, zuletzt ihr eigenes Abnahmemaß. Der Weg
dorthin ist der Gegenstand der Abnahme und wird deshalb nicht gekürzt — die jeweils überholte
Fassung bleibt mit ihrem Datum stehen, damit nachvollziehbar ist, was wann galt.

## Ziel

Bei der Kuratierung sollen die Bilder in Einheiten erscheinen, die einem tatsächlichen Anlass
entsprechen — ein Ausflug, ein Abend, ein Kindergeburtstag. Heute zerfällt das in viele sehr
kleine Cluster, oft mit nur einem einzigen Bild.

Das trifft nicht nur die Ansicht. Die Richtwerte für die Albumauswahl werden je Cluster vergeben:
Ein Cluster mit einem einzigen Bild bekommt damit dasselbe Kontingent wie ein ganzer Reisetag,
und die Auswahl verzerrt sich zugunsten von Ausreißern. Die Kuratierung als Albumauswahl setzt
voraus, dass ein Cluster eine sinnvolle Einheit ist — trifft das nicht zu, taugt das Ergebnis
nicht.

Zusätzlich beobachtet, aber noch nicht eingegrenzt: Bilder werden teilweise einem ganz anderen
Land zugeordnet. Ob und wie stark das zur Zerstückelung beiträgt, ist offen. Diese Story belegt
es zuerst, bevor daran etwas geändert wird — sonst ließe sich an einer Behebung nichts abnehmen.

Nutzer sind Daniel und seine Frau, die nach einer Reise ihre Fotos durchsehen.

## User Story

Als jemand, der nach einer Reise seine Fotos durchsieht, möchte ich die Bilder in Clustern
vorfinden, die einem zusammenhängenden Anlass entsprechen, damit ich sie am Stück beurteilen kann
und die Albumauswahl nicht von Ein-Bild-Ausreißern verzerrt wird.

## Akzeptanzkriterien

Auf Testbarkeit geschärft gegenüber dem Issue-Body; die Aussage ist unverändert, außer beim
Ortsfehler (siehe „Entscheidungen").

**20 von 21 erfüllt.** Das eine offene ist das vierte — die fehlende Laufkennung im
Messprotokoll; es trägt seine Begründung und Daniels Entscheidung bei sich und bleibt bewusst
unabgehakt, statt nachträglich weichgeschrieben zu werden.

**Zuerst belegen, was ist**

- [x] `python -m photosort.event_probe --project-id <N>` gibt für den letzten erfolgreichen
      Kriterien-Lauf eines echten Projekts die Verteilung der Events nach Fotozahl aus (je Fotozahl
      die Eventzahl), dazu den Anteil der Ein-Bild-Cluster, den Median, das größte Event sowie die
      längste und kürzeste Eventdauer.
- [x] Dieselbe Ausgabe weist je Trennursache aus dem geschlossenen Vorrat zwei Zahlen aus — „war
      beteiligt" und „war alleinige Ursache" — sowie den Anteil der Grenzen, die ein Segment unter
      `MIN_EVENT_PHOTOS` eröffnet haben. Die Zahl der Grenzen mit Ursache ist stets
      `Eventzahl − 1`: Das erste Segment eines Laufs trägt keine Ursache.
- [x] Der beobachtete Ortsfehler ist **je Mechanismus getrennt** belegt oder widerlegt —
      übernommener Ort, aufgelöster Ortsname, Sehenswürdigkeitsname. Je Mechanismus ist
      nachvollziehbar, wie weit die Ortsaussage von der Aufnahmeposition abweicht und in welchem
      Anteil der Fälle sie eine festgelegte Entfernungsschwelle überschreitet; diese Schwelle
      vertritt „falsches Land", weil der Ländercode im Ortsauszug nicht geführt wird.
- [ ] Diese Messergebnisse stehen als Blöcke A, B und C im Abschnitt „Messprotokoll" dieser Spec,
      mit Projekt-Id und Laufkennung — und ohne jede Koordinate, ohne Orts- oder
      Sehenswürdigkeitsnamen und ohne OpenCloud-Pfad.
      **Als einziges Kriterium dieser Spec nicht erfüllt, und das bleibt so sichtbar stehen.** Die
      Blöcke stehen im Messprotokoll, die Projekt-Id steht darin, und keine der vier verbotenen
      Angaben ist darin — aber **keine Laufkennung**: Der Bericht hat sie bis PR 9 nicht
      ausgegeben, obwohl `read_event_probe_input` sie intern ermittelt. Kein Eintrag des
      Messprotokolls trägt sie deshalb; identifiziert wird der Lauf dort relativ („letzter
      erfolgreicher Kriterien-Lauf"), was zum Zeitpunkt der Messung eindeutig ist und später nicht
      mehr. **Von Daniel am 2026-09-20 entschieden:** Die Ursache wird beseitigt (PR 9 gibt die
      Laufkennung ab jetzt aus), eine Wiederholung der Messungen allein dafür lohnt nicht. Das
      Kriterium bleibt für die bereits festgehaltenen Einträge unerfüllt; jede künftige Messung
      erfüllt es.

**Einen Anlass zusammenhalten**

- [x] Eine Folge von Aufnahmen, deren größte Einzel-Zeitlücke unter `EVENT_TIME_GAP`, deren größter
      Einzelschritt unter `EVENT_STEP_MAX_METERS`, deren Ausdehnung unter
      `EVENT_EXTENT_MAX_METERS` und deren Gesamtdauer unter `EVENT_MAX_SPAN` liegt, bildet genau
      ein Event — gleich über wie viele Stunden, Kilometer und Kalendertage sie läuft.
- [x] Eine Kalendertagsgrenze allein trennt nicht mehr: Zwei Aufnahmen beiderseits von Mitternacht,
      deren Zeitlücke unter `EVENT_TIME_GAP` liegt und deren Event-Gesamtdauer unter
      `EVENT_MAX_SPAN` bleibt, stehen im selben Event. Dessen Überschrift zeigt dann eine Spanne
      der Form `23:40–01:15 Uhr` und steht im Abschnitt seines **Anfangstags**.
- [x] Ein Segment mit weniger als `MIN_EVENT_PHOTOS` Fotos wird genau einem **angrenzenden**
      Segment zugeschlagen: dem mit der kleineren Zeitlücke, bei Gleichstand dem mit der kleineren
      Entfernung, danach dem früheren — und nur, wenn alle vier Riegel halten. Hält keiner der
      beiden Nachbarn, bleibt das Segment unverändert bestehen; das ist ein gültiges Ergebnis, kein
      Fehlerfall.
- [x] Ein Wechsel des Sehenswürdigkeitsnamens trennt keine Events mehr. Zwei Fotos, die sich
      allein in ihrem Namen unterscheiden, stehen im selben Event.
- [x] Der Name bleibt am Event: `events.landmark_name`, `place_kind` und die Anzeige sind
      unverändert. Ein Event, dessen Fotos verschiedene Namen tragen, trägt den des **frühesten**
      benannten Fotos — das ist ab jetzt die Regel, nicht mehr ein defensiver Zweig.
- [x] `sehenswuerdigkeit` bleibt im Ursachenvorrat und steht in der Nachmessung bei 0 (0,0 %).
      Die Zeile ist der Nachweis der Änderung; sie verschwindet nicht aus dem Bericht.
- [x] **Ein Motivwechsel trennt keine Events mehr allein.** Zwei Fotos, die sich allein im
      getragenen Motiv unterscheiden und zwischen denen kein anderes Signal trennt, stehen im
      selben Event — gleich wie lange der Wechsel bestätigt bleibt.
- [x] **Die Gliederung hängt nicht mehr an der ersten Stufe.** `explain_events` liefert unter einem
      nie erreichbaren Bestätigungsfenster dieselbe Eventfolge wie am Betriebswert; verschieden
      sind allein die Ursachenmengen. Das ist die starke Form des Kriteriums darüber und die
      eigentliche Zusage. Sichtbar wird sie auch im Bericht: In Block E sind die Spalten „Events",
      „Ein-Bild-Cluster", „größtes Event" und „längste Dauer" über **alle** Zeilen einschließlich
      „aus" gleich.
- [x] **`motivwechsel` steht nie allein.** Der Name bleibt im Ursachenvorrat und wird weiter als
      „beteiligt" gezählt; in der Spalte „alleinige Ursache" steht er auf 0 (0,0 %). Jede
      Ursachenmenge, die ihn enthält, enthält mindestens eine weitere Ursache.
- [x] **Der Vermerk wird nicht aufgeschoben.** Fällt ein bestätigter Motivwechsel auf einen Index,
      an dem kein Signal meldet, trägt **keine** spätere Grenze deswegen `motivwechsel`. Die
      Ursachenmenge einer Grenze nennt nur, was an ihr selbst gemeldet hat.
- [x] **Das Abnahmemaß ist der Album-Richtwert.** Nach der Änderung weist Block A an denselben
      Daten (Projekt 3, letzter erfolgreicher Kriterien-Lauf) alle drei Größen zugleich aus:
      Eventzahl **echt kleiner** als der Richtwert, freie Plätze **echt größer** als 0, und das
      Urteil, dass die Gewichtung nach Größe beginnt. Die drei sind nicht unabhängig — die dritte
      ist die Aussage, die ersten beiden sind ihre Bedingung —, und alle drei stehen ausgeschrieben
      im Bericht.
      **Warum dieses Maß und nicht mehr der Ein-Bild-Anteil:** Jenes Kriterium stand unter Daniels
      Vorbehalt und hat in die Irre geführt. Der Anteil fiel von 24,2 % auf 13,6 %, während die
      Verzerrung, um die es der Story geht, unverändert bestand: 81 Events auf 41 Plätze. Es war ein
      Hilfsmaß für „ein Cluster = ein Anlass" und ersetzt durch das Maß, an dem der Schaden hängt.
      Der Ein-Bild-Anteil wird weiter **ausgewiesen**, aber nicht mehr abgenommen — er **steigt**
      unter dieser Änderung (die Grundmenge schrumpft stärker als der Zähler), und das ist
      hingenommen.

**Dabei nicht zu viel verschmelzen**

- [x] Kein Event überschreitet `EVENT_MAX_SPAN`. Kein Event überschreitet
      `MERGE_EXTENT_MAX_METERS`, und kein Event **aus dem Signal-Durchlauf** überschreitet
      `EVENT_EXTENT_MAX_METERS`. Die frühere Fassung — beide Stufen gegen dieselbe Zahl — gilt
      seit ADR 0118 nicht mehr; sie machte Stufe 3 für ausdehnungsgetrennte Segmente strukturell
      unpassierbar.
- [x] **Keine Grenze ist mehr unantastbar.** Eine Grenze, deren Ursachenmenge `motivwechsel`
      enthält, wird vom Zusammenlegen aufgelöst wie jede andere, sobald die drei Riegel halten.
      Die frühere Fassung — eine solche Grenze wird nie aufgelöst — gilt seit ADR 0119 nicht mehr,
      und mit ihr ist `UNBREAKABLE_CAUSES` entfallen. Der Berichtsgrund `unantastbar` bleibt in der
      Riegel-Diagnose stehen und steht dort dauerhaft auf 0; die Zeile ist der Nachweis, nicht ein
      Rest. Der Schutz gegen Überverschmelzung liegt damit **allein** bei den drei Schwellen des
      Kriteriums darüber — sie gelten unverändert und sind ab jetzt der ganze Schutz.
- [x] Die Nachmessung weist aus, welcher Anteil der Grenzen durch das Zusammenlegen aufgelöst wurde
      und welcher Anteil der Fotos dadurch das Event gewechselt hat.
- [x] Weder Datenmodell noch API-Antwort noch Oberfläche bekommen ein Feld, einen Endpunkt oder
      eine Geste zum Bestätigen, Verschieben oder Korrigieren eines Clusters. Das Zusammenlegen
      wirkt allein im Lauf bzw. beim Neuaufbau.

**Die Ortszuordnung**

- [x] Block C weist je Mechanismus aus, ob eine Auffälligkeit vorliegt. Ob sie eine Behebung
      innerhalb dieser Spec auslöst, entscheidet Daniel anhand der festgehaltenen Zahlen; der
      Umsetzungslauf hält an dieser Stelle an, statt selbst zu entscheiden.
- [x] Bleibt es bei „keine Behebung", steht das mit Begründung im Messprotokoll, und an der
      Ortsbestimmung wird nichts geändert. Löst Daniel eine Behebung aus, ist der belegte Anteil
      nach der Änderung messbar gesunken.

## Datenmodell-Bezug

**Keine Änderung.** Weder `models.py` noch eine Alembic-Migration noch eine API-Antwort sind
betroffen. Die Trennursache einer Grenze entsteht im Durchlauf und wird bewusst nicht persistiert
(ADR 0117, Punkt 4). Betroffen ist allein die Bildung der `Event`-Einheit, deren Struktur
unverändert bleibt; siehe [`docs/architecture.md`](../../docs/architecture.md), Abschnitt „Event".

Bestehende Läufe behalten ihre Events, bis sie neu berechnet werden; Event-Ids überleben einen
Neuaufbau ohnehin nicht.

## Architektur / Umsetzung

Die Entscheidung ist als ADR
[`0117`](../decisions/0117-der-anlass-als-einheit-eigene-schwellen-dauergrenze-und-mindestgroesse.md)
festgehalten. Sie löst ADR
[`0087`](../decisions/0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md)
Abschnitt 5, letzter Absatz ab und ergänzt ADR
[`0109`](../decisions/0109-motivwechsel-trennt-in-einem-vorgelagerten-durchlauf.md) um eine
nachgelagerte Stufe.

### Gewählter Ansatz

Die Event-Bildung in `backend/src/photosort/events.py` wird von zwei auf **drei Stufen** erweitert
und bekommt **eigene Schwellen**:

1. **Motivgrenzen** (`motif_change_starts`) — unverändert.
2. **Der Signal-Durchlauf** — unverändert im Aufbau, mit drei Änderungen: die Kalendertagsgrenze
   entfällt, eine Dauergrenze tritt an ihre Stelle, und jedes Signal trägt einen Namen, sodass
   jede Grenze ihre **Ursachenmenge** mitführt.
3. **Neu: das Zusammenlegen zu kleiner Segmente** — ein Durchgang über die Segmente, bevor aus
   ihnen `BuiltEvent`s werden.

Erst danach bildet `_built(position, members)` die Events. Weil das die einzige Stelle bleibt, an
der Name, Zellen und `place_kind` eines Events entstehen, stimmen diese Werte für ein
zusammengelegtes Event ohne eigenen Zweig, und `position` läuft ohne Nacharbeit lückenlos ab 1.

**Drei Konstanten stehen dabei nicht mehr, wo sie stehen dürfen.** `TimeGapSignal` und
`StepDistanceSignal` lesen heute `scoring.TIME_CLUSTER_GAP` und
`scoring.GPS_CLUSTER_SPLIT_DISTANCE_METERS` (`events.py:26-27`) — **dieselben Konstanten steuern
`assign_clusters`** (`scoring.py:195-196`), also Phase A vor dem Ausschuss-Gate und damit, welche
Fotos im Ausschuss gegeneinander antreten. Eine Kalibrierung an ihnen verschöbe still die
Kandidatenmenge. `events.py` bekommt deshalb eigene Konstanten; Phase A wird nicht angefasst.

### Die Konstanten in `events.py`

| Name | Bedeutung | Herkunft des Werts |
|---|---|---|
| `EVENT_TIME_GAP` | Zeitlücke, ab der ein neues Event beginnt | **unverändert** 1 h (heute `TIME_CLUSTER_GAP`) |
| `EVENT_STEP_MAX_METERS` | Schritt zwischen zwei Aufnahmen | **unverändert** 500 m (heute aus Phase A) |
| `EVENT_EXTENT_MAX_METERS` | Diagonale der umschließenden Box | **unverändert** 1000 m |
| `EVENT_MAX_SPAN` | **neu** — Dauer vom eröffnenden bis zum betrachteten Foto | begründet gesetzt, siehe unten |
| `MIN_EVENT_PHOTOS` | **neu** — Größe, unter der ein Segment zugeschlagen wird | begründet gesetzt, siehe unten |
| `MERGE_MAX_GAP` | **neu** — Zeitlücke, die ein zu kleines Segment überbrücken darf | begründet gesetzt, `> EVENT_TIME_GAP` |

**Die drei bestehenden Schwellen werden nicht kalibriert** (Block D entfällt, Begründung im
Messprotokoll): Sie bewegen zusammen höchstens 5,6 % der Grenzen, `schritt` und `ausdehnung` davon
0,0 %. Sie ziehen aus `scoring.py` nach `events.py` um, damit eine spätere Kalibrierung nicht
länger Phase A mitverschiebt — mit **unveränderten Werten**, und ihr Vermerk „unkalibriert" bleibt
stehen.

**Die drei neuen Werte entstehen aus dem gemessenen Bestand und aus Daniels Zielbild, nicht aus
einem Kalibrierungslauf** — die Herleitung steht bei der jeweiligen Konstante im Code und ist damit
nachprüfbar statt geraten:

- **`EVENT_MAX_SPAN = 8 h`** (Daniel am 2026-09-18). Trägt einen ganzen Ausflugstag — Stadtbummel,
  Zoobesuch, Wanderung — und ebenso Silvester oder einen Nachtflug über Mitternacht; zwei Reisetage
  passen nicht hinein. Der Wert liegt weit über der längsten heute gemessenen Eventdauer
  (1 h 32 min), zerschneidet also nichts, was heute zusammengehört, und unter 24 h, was die
  Vorbedingung der Überschriftenform ist.
- **`MERGE_MAX_GAP = 2 h`**, also das Doppelte von `EVENT_TIME_GAP`. Größer als diese muss es sein,
  sonst ist die dritte Stufe wirkungslos — ein Rest von ein, zwei Bildern trägt keinen eigenen Beleg
  dafür, dass mit ihm ein neuer Anlass begann. Bewusst nicht größer: Über eine Lücke von mehr als
  zwei Stunden hinweg anzuhängen hieße, eine echte Pause zu überspringen, und die Dauergrenze
  finge das erst bei 8 h ab.
- **`MIN_EVENT_PHOTOS = 2`** (Daniel am 2026-09-18, mit ausdrücklichem Vorbehalt): Zunächst gilt
  nur ein **einzelnes** Foto als zu klein — das trifft genau die 22 Fälle, um die es geht, und
  lässt die 15 Zwei-Foto-Cluster unberührt. **Bleibt der Anteil nach der Nachmessung über 12,1 %,
  wird auf 3 erhöht und erneut gemessen.** Entschieden wird an den Zahlen, nicht vorab.

Alle sechs bleiben Modulkonstanten, ausdrücklich **kein** Settings-/Env-Wert. Kein Test prüft einen
Zahlwert — geprüft wird wie
bisher „Wert unter/über Schwelle → erwartetes Verhalten" über injizierte Signale.

### Die Mitternachtsgrenze

`DayBoundarySignal` entfällt ersatzlos. An seine Stelle tritt `EventSpanSignal`, zustandsbehaftet
im Muster von `ExtentSignal`: Grenze, sobald `candidate.taken_at - <erstes Foto des Events>` über
`EVENT_MAX_SPAN` liegt, geprüft **einschließlich** des betrachteten Fotos — sonst begänne das neue
Event ein Foto zu spät.

Silvester, ein langer Abend und ein Nachtflug liegen unter der Dauergrenze und bleiben ein
Cluster; zwei Reisetage liegen darüber und werden es nicht.

### Das Zusammenlegen zu kleiner Segmente

Ein Segment mit weniger als `MIN_EVENT_PHOTOS` Fotos wird dem **angrenzenden** Segment
zugeschlagen, zu dem es gehört:

- **Wahl des Nachbarn:** kleinere Zeitlücke zum Rest; bei Gleichstand kleinere Entfernung; danach
  der frühere. Nur angrenzende Segmente.
- **Vier Riegel gegen Überverschmelzung.** Zugeschlagen wird nur, wenn (a) die Zeitlücke zum
  Nachbarn `MERGE_MAX_GAP` nicht überschreitet, (b) die Dauer des Ergebnisses `EVENT_MAX_SPAN`
  nicht überschreitet, (c) die Ausdehnung des Ergebnisses `EVENT_EXTENT_MAX_METERS` nicht
  überschreitet und (d) das Segment selbst unter der Mindestgröße liegt — ein normal großes Event
  wird nie zugeschlagen. Ist kein Nachbar zulässig, **bleibt das Segment allein**: ein gültiges
  Ergebnis, kein Ausnahmezweig.
- **Zwei unantastbare Grenzen:** Eine Grenze, deren Ursachenmenge `motivwechsel` oder
  `sehenswuerdigkeit` enthält, wird nie aufgelöst. Sie sind die einzigen Signale, die zwei Anlässe
  am selben Ort zur selben Zeit trennen; ohne ihren Vorrang wäre das Akzeptanzkriterium „zwei
  erkennbar verschiedene Anlässe bleiben getrennt" nicht durchsetzbar.
  **Überholt:** ADR 0118 hat die Sehenswürdigkeit daraus entfernt, ADR 0119 den Vorrat selbst
  (siehe „PR 5" und „PR 8"). Es gibt keine unantastbare Grenze mehr; der Absatz steht als Stand
  von PR 3.
- **Stillstand:** Der Durchgang läuft, bis keine Zusammenlegung mehr stattfindet, höchstens so
  viele Runden wie es Segmente gibt. Je Runde das kleinste Segment, **das nicht bereits als
  gesperrt feststeht**, bei Gleichstand das frühere — der Stillstand hängt nicht an einer
  Iterationsreihenfolge. Der Zusatz trägt die Terminierung: Ein an einem Riegel gescheitertes
  Segment wird durch keine spätere Runde zulässig, und ohne ihn wählte jede Runde dasselbe
  gesperrte Segment erneut. Die Rundenobergrenze **wirft**, statt abzubrechen.
- **Injizierbar:** `build_events` nimmt `min_event_photos` und `merge_max_gap` injizierbar
  entgegen (`None` = Modulkonstante), und die sechs Konstanten werden im Code als **Modulattribut**
  gelesen, nie als Default-Parameterwert gebunden. Ohne das laufen 26 bestehende Fälle in
  `test_events.py` still durch die neue Stufe, und Block D kann die beiden Werte nicht variieren —
  sie sind keine Signale.
- **Kein Handgriff:** Es gibt keine Bestätigung, keine Korrekturgeste, kein Feld. Das
  Zusammenlegen findet im Lauf statt; eine Änderung wirkt beim nächsten Lauf bzw. Neuaufbau.

### Die Trennursache

`BoundarySignal` bekommt einen `name` aus geschlossenem Vorrat (`zeitluecke`, `dauer`, `schritt`,
`ausdehnung`, `sehenswuerdigkeit`), dazu `motivwechsel` für einen erzwungenen Start. Jede Grenze
trägt die **Menge** der meldenden Signale, nie ein einzelnes: Der Durchlauf wertet alle aus,
mehrere dürfen gleichzeitig zutreffen, und ein Bericht mit einer Ursache je Grenze addierte sich
zu mehr als hundert Prozent oder unterschlüge Ursachen.

**Der Vorrat oben ist der Endzustand nach PR 3.** In PR 1 und PR 2 heißt die Ursache `kalendertag`
statt `dauer`: Die Dauergrenze entsteht erst in Schritt 6, und Block B soll bis dahin den
**Ist-Zustand** messen — eine Ursache zu benennen, die noch gar nicht trennt, machte die
Ausgangsmessung unbrauchbar. Mit PR 3 tritt `dauer` an ihre Stelle, zusammen mit
`EventSpanSignal`.

**Das erste Segment eines Laufs hat keine Ursache** — seine Menge ist leer. `TimeGapSignal` meldet
beim ersten Foto `True` (`_previous is None`); ohne diese Ausnahme trüge jeder Lauf eine erfundene
Zeitlücke in der Statistik.

### Das Messkommando

Neu: `backend/src/photosort/event_probe.py`, **rein lesend**, im Muster von `place_probe.py`:

```bash
docker compose exec -T backend python -m photosort.event_probe --project-id <N>
```

Aufrufbar in der Container-Konsole ohne Host-Shell — `scripts/` liegt nicht im Image, ein Skript
dort trägt für den Betrieb nicht. Rein lesend ist eine **geprüfte Zusage**: kein
`INSERT`/`UPDATE`/`DELETE`, kein Aufrufpfad aus `main.py`/`worker.py`, kein Endpunkt, kein
Compose-`command`; Nachweis dreiteilig wie in `tests/test_place_probe.py` (Import-Graph,
Syntaxbaum-Wächter, echter `main()`-Lauf mit Tabellen-Schnappschuss davor und danach).

**Gemessen wird mit den Mitteln des Laufs.** Der Aufbau der `EventCandidate`-Menge zieht aus
`worker.py::_build_grouping_and_rankings` in ein eigenes, rein lesendes Modul
(`backend/src/photosort/event_inputs.py`) und bekommt zwei Aufrufer: den Lauf und das Kommando.
Mitgezogen werden `_landmark_names` und `_plain_strengths`. Eine nachbildende zweite Fassung maße
etwas anderes, als der Lauf tut, während beide für sich grün blieben.

**Die Ausgabe ist Markdown auf stdout und trägt keine Koordinate, keinen Orts- oder
Sehenswürdigkeitsnamen und keinen OpenCloud-Pfad.** Das ist zugleich die Bedingung dafür, dass die
Zahlen als Ganzes ins Repository dürfen — ein Ortsname *ist* die Ortsangabe.

#### Block A — wie sich die Bilder heute über die Cluster verteilen

Events des letzten erfolgreichen Kriterien-Laufs nach Fotozahl: Verteilung (`1 Foto: n`, `2: n`,
…), Anteil der Ein-Bild-Cluster, Median, größtes Event, längste und kürzeste Eventdauer. Dauern
stehen als Dauer, nie als Anfang oder Ende (Security S2).

**Dazu das Maß, auf das es eigentlich ankommt: reicht der Album-Richtwert für eine Gewichtung?**
Nachgetragen am 2026-09-20, nachdem Daniel in der Kuratierung gesehen hat, dass jedes Cluster
genau ein Bild zeigt. `selection.py::_quotas` vergibt nach „Abdeckung zuerst" jedem Event einen
Platz, **auch wenn der Vorschlag dadurch größer wird als der Richtwert**, und bricht ab, sobald
keine Plätze mehr übrig sind. Liegt die Eventzahl **auf oder über** dem Richtwert, bekommt jedes
Event genau einen Platz und die Gewichtung nach Größe beginnt gar nicht erst. Der Bericht weist
deshalb Richtwert, Eventzahl, freie Plätze und das Urteil als ausgeschriebenen Satz aus.

Der Richtwert kommt über `selection.effective_target`, nicht nachgebildet. **Zwei Grenzen gehören
zur Aussage und stehen im Bericht:** `effective_target` rechnet auf **allen** Fotos des Projekts,
nicht auf der Kandidatenmenge des Laufs — weichen beide voneinander ab, sagt der Bericht es in
einer eigenen Zeile. Und `_quotas` sieht nur Events mit mindestens einem auswählbaren Foto,
während das Kommando alle Events der Gliederung zählt; die gemeldete Eventzahl ist damit eine
**Obergrenze** dessen, was die Vergabe sieht. Den Eingaberand der Auswahl nachzubauen wäre die
zweite Fassung, die diese Spec durchgehend ausschließt.

**Damit ist das Abnahmemaß dieser Spec korrigiert.** Der Anteil der Ein-Bild-Cluster war ein
Hilfsmaß und hat in die Irre geführt: Er fiel von 24,2 % auf 13,6 %, während die Verzerrung der
Albumauswahl — der eigentliche Grund der Story — unverändert bestand, weil 81 Events auf 38 Plätze
trafen.

#### Block B — welche Trennursache wie oft trennt

Je Ursache **zwei** Zahlen: „war beteiligt" und „war alleinige Ursache". Nur die zweite ist
handlungsleitend — eine Schwelle anzuheben hilft dort, wo sie allein getrennt hat. Dazu je Ursache
der Anteil der Grenzen, die ein Segment unter `MIN_EVENT_PHOTOS` eröffnet haben.

#### Block C — die Ortszuordnung, je Mechanismus getrennt

Drei Wege führen zu einer falschen Ortsaussage, sie haben verschiedene Behebungen, und eine
Gesamtzahl über alle drei wäre für keine davon eine Grundlage:

1. **Übernommener Ort** (`infer_locations`, speist `StepDistanceSignal`/`EventSpanSignal` und
   damit die Grenzen): Anteil der Kandidatenfotos ohne eigene Koordinate; Verteilung des
   Zeitabstands zum übernommenen Anker; und die **Ankerspanne** — die Entfernung zwischen dem
   vorherigen und dem nächsten koordinatentragenden Foto. Liegen die beiden weit auseinander, ist
   die Übernahme ein Münzwurf, und das ist ohne jede äußere Wahrheit belegbar. **Beide Größen nur
   in vorab festgelegten Klassen** (Security S5) — sie entstehen aus voller EXIF-Präzision, und
   eine geordnete Folge daraus wäre ein Streckenabdruck.
2. **Aufgelöster Ortsname** (`geonames_answer`): Entfernung zwischen der Aufnahmeposition und dem
   Eintrag, der den Namen geliefert hat — `geonames_answer` rechnet sie bereits (`geonames.py:153`)
   und wirft sie weg. Verteilung plus Anteil oberhalb der Entfernungsschwelle. Strukturell
   begrenzt durch `GEONAMES_MAX_DISTANCE_METERS` (25 km).
3. **Sehenswürdigkeitsname** (der Weg, über den eine Ortsaussage am weitesten danebenliegen kann —
   ein Name benennt das **ganze** Event und verdrängt dessen Koordinatenstufe): Anteil der
   Erkennungen, die **ohne jeden Ortshinweis** entstanden (`landmark.py::place_hint_for` liefert
   für ein Foto ohne eigenes GPS `None`); Zahl der Namen, deren Trägerfotos weiter als die
   Entfernungsschwelle auseinanderliegen — ein innerer Widerspruch, für den es keine äußere
   Wahrheit braucht; und die Zahl der Events, deren Name auf genau einem von vielen Fotos beruht.

**Ein Land ist im Bestand nicht berechenbar** — der Auszug führt Orte und Verwaltungsebenen, keine
Grenzen und keine Bauwerke, und der Ländercode steht nicht in den fünf behaltenen Feldern
(`GEONAMES_KEPT_FIELDS`). „Falsches Land" wird deshalb durch eine **Entfernungsschwelle**
vertreten: Eine Zuordnung, die um mehr als diese Entfernung von der Aufnahmeposition abweicht, ist
falsch, ob sie eine Grenze überschreitet oder nicht.

**Die Lücke wird benannt statt geschlossen:** Ein Sehenswürdigkeitsname, der in sich stimmig ist,
ist ohne Rückfrage bei einem bezahlten Dienst nicht überprüfbar. Die Diagnose **belegt** diesen Weg,
wo Widersprüche auftreten, kann ihn aber nicht **widerlegen**. „Kein systematischer Fehler" gilt
für die Wege 1 und 2 vollständig, für Weg 3 nur so weit, wie die Widersprüche reichen. Das begrenzt,
was das Akzeptanzkriterium „belegt oder widerlegt" einlösen kann.

#### Block F — woran eine Zusammenlegung scheitert (`--riegel`)

**Nach der Nachmessung eingefügt.** Sie hat gezeigt, dass Stufe 3 nur 3 von 90 Grenzen aufgelöst hat
und das Halbierungsziel damit verfehlt (20,5 % statt ≤ 12,1 %). Die Stufe hat nicht zu viel
verschmolzen, sondern fast nichts — **warum**, weist der Bericht heute nicht aus.

Je zu kleinem Segment, das **nicht** zugeschlagen werden konnte, wird ausgewiesen, welcher Grund an
seinen Kanten stand. Vorrat, geschlossen und in der Prüfreihenfolge von `_may_merge`:

| Grund | Bedeutung |
|---|---|
| `unantastbar` | die eröffnende Grenze trägt `motivwechsel` oder `sehenswuerdigkeit` |
| `zeitluecke` | Riegel (a): Lücke zum Nachbarn über `MERGE_MAX_GAP` |
| `dauer` | Riegel (b): das Ergebnis überschritte `EVENT_MAX_SPAN` |
| `ausdehnung` | Riegel (c): das Ergebnis überschritte `EVENT_EXTENT_MAX_METERS` |
| `kein_nachbar` | das Segment liegt am Rand und hat auf dieser Seite keinen |

**Eine Kante trägt die Menge ihrer Gründe, nie einen einzelnen** — dieselbe Auflage wie bei den
Trennursachen und aus demselben Grund: `ausdehnung` wird zuletzt geprüft, und ein Abbruch beim
ersten Treffer unterschlüge ausgerechnet die Zahl, an der die Frage dieses Blocks hängt. Wer
daraufhin einen früheren Riegel lockert, steht danach vor dem verdeckten.

Gezählt wird wie in Block B **zweifach**: „war an einer Kante beteiligt" und „war an allen Kanten
**der** Grund". Die zweite Zahl ist die handlungsleitende, und sie ist streng zu lesen: an jeder
Kante stand er, und an keiner stand etwas daneben. Nur dann löst seine Behebung das Segment
tatsächlich auf — die strikte Entsprechung zu „alleinige Ursache" aus Block B, eine Ebene tiefer.

**Ein Segment hat so viele Kanten, wie es Nachbarn hat.** Eine fehlende Seite am Rand des Laufs ist
keine Kante: Sie ist kein Hindernis, und sie als solches zu zählen nähme einem Randsegment die
zweite Spalte, obwohl an seiner einen echten Kante sehr wohl ein Grund stand. `kein_nachbar` greift
deshalb nur, wenn es überhaupt keinen Nachbarn gibt — die Zeile ist damit fast immer null, und das
ist die ehrliche Form.

**Seit ADR 0119 gibt es die Sperre nicht mehr**, und die Zeile `unantastbar` steht dauerhaft auf 0.
Sie bleibt im Vorrat, damit ein Block-F-Lauf gegen den vom 2026-09-19 zu halten ist — dort war sie
der größte Blocker. Der folgende Absatz begründet, warum sie überhaupt eine eigene Zeile bekam, und
gilt für die Lesart dieser früheren Messung weiter.

**Die Unantastbarkeit zählt als eigener Grund und nicht als Riegel.** Sie ist keine Schwelle,
sondern eine Zusage, und ihre Behebung wäre eine andere Entscheidung als die Änderung einer Zahl.
Ohne diese Trennung bliebe nach der Messung offen, ob Riegel (c) oder die Sperre blockiert hat —
beide Erklärungen sind heute unbelegt und schließen einander nicht aus.

**Rein lesend wie die übrigen Blöcke**, keine Verhaltensänderung an der Gliederung. Der Modus
rechnet dieselbe Gliederung wie Block A und B und beobachtet dabei Stufe 3, statt sie zu verändern.

#### Block E — die Empfindlichkeit des Motivwechsels (`--motiv`)

**Nach der Ausgangsmessung eingefügt.** Sie hat den Motivwechsel als alleinige Ursache von 62,2 %
der Grenzen ausgewiesen, während `schritt` und `ausdehnung` bei 0,0 % stehen — die vorgesehene
Kalibrierung trifft die Ursache nicht. Bevor an der Unantastbarkeit der Motivgrenze etwas geändert
wird, wird sie deshalb gemessen, nach demselben Grundsatz wie der Rest dieser Story.

Dieselbe Kandidatenmenge wird unter mehreren Werten von `MOTIF_CHANGE_CONFIRMING_PHOTOS` (heute 3)
und der Motivstärke-Schwelle durchgerechnet. Je Kombination werden ausgewiesen: Eventzahl, Anteil
der Ein-Bild-Cluster, Zahl der Grenzen mit `motivwechsel` als alleiniger Ursache, und — als
Gegenanzeige gegen zu grobes Zusammenfassen — das größte entstehende Event und die längste Dauer.

**Die Tabelle führt den unveränderten Betriebswert als eigene erste Zeile mit**, ohne jede
Überschreibung — nicht als Rasterzelle: So trägt sie ihren eigenen Nullpunkt auch dann noch, wenn
einer der beiden Werte später wandert und in keiner Zelle des Rasters mehr steht. Ein Test pinnt
diese Zeile gegen `explain_events(candidates)`.

**Eine zweite Bezugszeile: „aus".** Nachgetragen am 2026-09-20. Die erste Fassung von Block E hat
den Fall „Motivgrenze ganz aus" ausgelassen, weil er einen Abschaltpfad im Produktivcode gebraucht
hätte — er ist aber die Zeile, an der sich entscheidet, ob der Motivwechsel der Hebel ist: Er ist
mit 71,2 % alleinige Ursache aller Grenzen. Gemessen wird er **ohne** Abschaltpfad: Ein
Bestätigungsfenster größer als die Zahl der Kandidatenfotos kann nie bestätigt werden. Keine neue
Argumentform, kein Schalter an `motif_change_starts`, kein zweiter Rechenweg.

`MOTIF_CHANGE_CONFIRMING_PHOTOS` liegt in `events.py`, die Stärke-Schwelle als
`MOTIF_PRESENCE_THRESHOLD` in `selection.py`. **Beide werden in diesem Schritt nicht geändert**,
sondern nur variiert durchgerechnet; die Messung ist rein lesend wie die Blöcke A–C.

**Was die Messung entscheidbar macht, entscheidet sie nicht:** Ob die Motivgrenze unantastbar
bleibt, gelockert wird oder das Halbierungsziel sinkt, legt Daniel anhand der Zahlen fest. Der Lauf
hält an dieser Stelle an. **Erledigt:** Daniel hat am 2026-09-20 entschieden — der Motivwechsel
begründet nur noch mit (ADR 0119). Der Halteort ist damit vergangen, kein offener Schritt.

#### Block D — die Kalibrierung (`--schwellen`)

Dieselbe Kandidatenmenge wird unter mehreren Schwellenkombinationen durchgerechnet; je Kombination
werden Eventzahl, Anteil der Ein-Bild-Cluster, größte Eventdauer und Anteil der Events über einem
Tag ausgegeben. Möglich, weil `build_events` seine Signale bereits injizierbar entgegennimmt und
rein ist.

**Ohne Handlabeln und ohne Training:** Nichts an diesem Verfahren setzt eine Bewertung eines Bildes
voraus. **Die Auswahlregel steht vor dem Lauf fest** und wird nicht nachträglich zurechtgelegt: Es
gilt die Kombination mit der **kleinsten** Zeitlücke, die (a) den Anteil der Ein-Bild-Cluster
gegenüber Block A mindestens halbiert und (b) kein Event über `EVENT_MAX_SPAN` erzeugt; bei
Gleichstand die mit der kleineren Ausdehnungsgrenze, danach dem kleineren `MERGE_MAX_GAP`, danach
dem kleineren `MIN_EVENT_PHOTOS` — **die Regel ist damit total**, sonst bliebe eine Flanke offen,
an der sich das Ergebnis nachträglich zurechtlegen ließe. Alle vier Stufen laufen in dieselbe
Richtung: so wenig verschmelzen wie nötig. Die Tabelle **und** die gewählte Zeile werden im
Abschnitt „Messprotokoll" festgehalten, und die Abnahme läuft gegen sie.

**Erfüllt keine Kombination die Regel, hält der Umsetzungslauf an** und legt die Wahl zwischen
„Halbierungsziel lockern", „`EVENT_MAX_SPAN` lockern" und „hinnehmen und festhalten" Daniel vor,
statt eine davon selbst zu treffen.

**Die Gegenanzeige zur Überverschmelzung wird mitgemessen**, weil beide Abnahmezahlen von einer zu
aggressiven Verschmelzung *besser* erfüllt würden: Anteil der Grenzen, die Stufe 3 aufgelöst hat,
und Anteil der Fotos, die dadurch ihr Event gewechselt haben. Beides ohne willkürliche Schwelle,
rein messend, in Block B und D.

#### Block H — entspricht ein Event einem Anlass? (`--kohaerenz`)

Beantwortet die eine Frage, die die Abnahmezahlen offenlassen: Ist ein großes, langes Event **ein**
Ausflug oder sind darin mehrere Anlässe verschmolzen? Der Ein-Bild-Anteil kann das nicht sagen, und
die Eventzahl auch nicht.

Der Bericht stellt **zwei Gliederungen nebeneinander** — Betriebswert und Motivwechsel „aus" —,
weil die Frage ein Vergleich ist: Das große Event der zweiten Gliederung ist nur gegen die erste zu
beurteilen. Je Gliederung stehen höchstens `COHERENCE_TOP_EVENTS` Events mit **Anzahlen, sonst
nichts**: Fotozahl, Dauer, Zahl der verschiedenen Ortszellen, Zahl der verschiedenen getragenen
Motive. Darüber je Gliederung die Klassenverteilung der Zell- und der Motivzahlen über *alle*
Events — ohne sie ließe sich am Ausschnitt nicht ablesen, ob er den Regelfall zeigt oder die
Ausnahme.

**Die Zellzahl gilt nur, soweit gemessen wurde.** `_cells_of` zählt ausschließlich Fotos mit
eigener Koordinate; ein übernommener Ort speist den Ortsbezug eines Events nie. Bei einem gemessenen
Anteil von 30,0 % Kandidatenfotos ohne eigene Koordinate (Block C1) wäre eine kleine Zellzahl sonst
nicht von „wenig gemessen" zu unterscheiden. Der Bericht führt deshalb je Event die **Zahl der
Fotos mit gemessener Koordinate** mit; ohne sie trüge eine unbelegte Zahl die Entscheidung.

**Gemessen mit den Mitteln des Laufs** (ADR 0117 Punkt 5): Zellen aus `BuiltEvent.place_cells`,
Motive über `selection.carried_motifs`, die zweite Gliederung über `explain_events` mit dem
unerreichbaren Bestätigungsfenster aus Block E. Kein Abschalter im Produktivcode, kein weiterer
Parameter, keine Nachbildung. Was die Ausgabe nie trägt, steht als S9 im Security-Abschnitt.

### PR 5 — die Sehenswürdigkeit trennt nicht mehr, Stufe 3 bekommt ihre eigene Ausdehnungsgrenze

Entschieden von Daniel am 2026-09-19 an den Zahlen der Blöcke B, C3 und F; festgehalten als ADR
[`0118`](../decisions/0118-sehenswuerdigkeit-trennt-nicht-mehr-und-eine-eigene-ausdehnungsgrenze-fuers-zusammenlegen.md).
Sie löst ADR 0087 Abschnitt 3, zweiter Absatz und ADR 0117 Punkt 3 in zwei benannten Teilen ab.

**1. `LandmarkChangeSignal` entfällt** — aus `default_signals()` und als Klasse; die Liste führt
vier Signale. `BOUNDARY_LANDMARK` **bleibt** in `BOUNDARY_CAUSES` (die Nachmessung braucht die
Zeile, um mit der Ausgangsmessung vergleichbar zu bleiben — die Null ist der Nachweis) und
**fällt** aus `UNBREAKABLE_CAUSES`, wo allein `motivwechsel` bleibt. Ein Wortschatz darf eine
ehrliche Null führen, eine an jeder Kante gelesene Regel nicht.

**Der Name bleibt.** `_name_of` liefert weiterhin den Namen des frühesten benannten Fotos, und die
Feldinvariante `place_kind='landmark'` ⇒ `landmark_name` gesetzt läuft unverändert über die eine
Aufrufstelle `_built`. Was sich ändert, ist der Status dieser Regel: Bisher stellte
`LandmarkChangeSignal` sicher, dass die Frage gar nicht auftrat; ab jetzt darf ein Event Fotos mit
verschiedenen Namen enthalten, und der früheste gewinnt. Der Docstring in `events.py` wird
entsprechend umgeschrieben, und die Regel bekommt ihren eigenen Testfall — heute ist dieser Zweig
nur defensiv erreichbar und damit ungeprüft.

**Getragene Kehrseite:** Ein Name benennt jetzt ein potenziell größeres Event und verdrängt dort
weiterhin Ortsnamen und Koordinate. Eine einzelne, zu 42,3 % ortsblinde Erkennung kann einem
ganzen Ausflug ihren Namen geben. Das ist größere Reichweite der bestehenden Fehlerquelle, keine
neue; ihre Behebung ist die Plausibilisierung des Namens und gehört zu Issue
[#514](https://github.com/TheRealKoller/photosort/issues/514).

**2. Riegel (c) prüft `MERGE_EXTENT_MAX_METERS = 1500,0`** statt `EVENT_EXTENT_MAX_METERS`. Heute
prüft er dieselbe Bedingung, deren Überschreitung die Trennung ausgelöst hat — für
ausdehnungsgetrennte Segmente ist die Stufe damit strukturell unpassierbar.

Der Wert ist hergeleitet, nicht kalibriert: die Trennschwelle plus **einen** Schritt
(`EVENT_EXTENT_MAX_METERS + EVENT_STEP_MAX_METERS`). Zugeschlagen wird ein Segment unter
`MIN_EVENT_PHOTOS`, heute also ein einzelnes Foto ohne eigene Ausdehnung; die Box wächst genau um
dessen Abstand zur Box des Nachbarn. Ein Schritt über `EVENT_STEP_MAX_METERS` ist im Maßstab
dieses Projekts bereits ein Ortswechsel — mehr als einen zuzulassen hieße, eine Trennung
aufzulösen, die das Projekt selbst so nennt. Als **Literal**, nicht als gerechnete Summe: Eine
beim Import gebundene Summe folgte `monkeypatch.setattr` nicht, und die Fixture über die
verschobenen Konstanten liefe ins Leere.

**Die Zusage, die dabei fällt:** „Kein Event überschreitet `EVENT_EXTENT_MAX_METERS`, weder als
Ergebnis des Durchlaufs noch als Ergebnis des Zusammenlegens" gilt so nicht mehr. An ihre Stelle
treten **zwei** Zusagen mit je eigener Grenze (siehe Akzeptanzkriterien). Die Invariante
`assert_full_signal_invariants` wird entsprechend **zweigeteilt statt gelockert**; eine bloße
Lockerung gäbe die Schranke des Durchlaufs stillschweigend mit auf.

### PR 8 — der Motivwechsel begründet nur noch mit, und die Unantastbarkeit entfällt

Entschieden von Daniel am 2026-09-20 an den Zahlen von Block H und dem Album-Richtwert;
festgehalten als ADR
[`0119`](../decisions/0119-der-motivwechsel-vermerkt-eine-grenze-statt-eine-zu-eroeffnen.md). Sie
löst ADR 0109 Punkt 1, ADR 0117 Punkt 3 und ADR 0118 Punkt 2 (zweiter Absatz) in benannten Teilen
ab.

**1. Die erste Stufe vermerkt, statt zu erzeugen.** `motif_change_starts` bleibt unverändert — die
Funktion, ihr Bestätigungsfenster, der Wechselbegriff, wer mitredet. Verändert wird allein, was
`explain_events` mit ihrem Ergebnis tut:

- Ein gelieferter Index eröffnet **kein** Event mehr. Die Bedingung, die ein neues Segment öffnet,
  ist `reporting or not events` — der Index steht nicht mehr darin.
- Fällt der Index mit einer Grenze des Signal-Durchlaufs zusammen, kommt `motivwechsel` zur
  Ursachenmenge **dieser** Grenze hinzu. Fällt er auf keine, ist er wirkungslos und wird
  **verworfen, nie auf die nächste Grenze übertragen**.
- Die Ausnahme an Index 0 bleibt, wo sie ist: Sie hängt an der Position, nicht an einem Signal.
  `motif_change_starts` liefert die 0 ohnehin nie.

**Die Signal-Rücksetzung fällt damit weg, und das ist die eine Stelle, an der die Änderung
zusätzliche Grenzen erzeugen kann.** Ein erzwungener Start rief `begin` auf allen Signalen;
`ExtentSignal` und `EventSpanSignal` starteten dort neu. Ohne ihn laufen beide über den
Motivwechsel hinweg weiter und melden früher. Die Eventzahl fällt deshalb nicht um genau die Zahl
der entfallenen erzwungenen Starts — das ist erwartet und hat seinen eigenen Testfall.

**2. `UNBREAKABLE_CAUSES` entfällt ersatzlos.** Der Vorrat verschwindet aus `events.py`, das erste
Paar aus dem `checked`-Tupel in `_may_merge`, und damit liest die dritte Stufe keine Ursachenmenge
mehr. Die Nicht-Kurzschluss-Zusage von `_may_merge` bleibt für die drei verbliebenen Riegel
unberührt. `Segment.causes` bleibt bestehen — das Ergebnissegment trägt weiter die Menge des
früheren der beiden, und `EventFormation.causes` speist den Bericht.

**Was bewusst stehen bleibt**, beides als Berichtswortschatz mit ehrlicher Null bzw. beweglicher
Zahl:

- `BOUNDARY_MOTIF_CHANGE` in `BOUNDARY_CAUSES` — „beteiligt" bewegt sich weiter und ist die Größe,
  an der eine spätere Änderung dieser Entscheidung gemessen würde.
- `MERGE_BLOCK_UNBREAKABLE` in `MERGE_BLOCK_REASONS` — dauerhaft 0, damit ein Block-F-Lauf gegen
  den vom 2026-09-19 zu halten bleibt, in dem `unantastbar` der größte Blocker war.

**Nicht geändert:** `motif_change_starts`, `_motif_picture`, `MOTIF_CHANGE_CONFIRMING_PHOTOS`,
`selection.py` (auch nicht die durchreichbare Grenze), `worker.py`, `event_inputs.py`, die sechs
übrigen Schwellen, das Datenmodell, jede API-Antwort, das Frontend.

**Block E bleibt und wird vakuum-richtig**, statt entfernt zu werden: Seine Spalten „Events",
„Ein-Bild-Cluster", „größtes Event" und „längste Dauer" sind danach über alle Zeilen einschließlich
„aus" gleich — und genau diese Gleichheit ist der ausgewiesene Nachweis, dass die Stufe keine
Grenze mehr erzeugt. Die Spalte „`motivwechsel` allein" steht dabei auf 0, „beteiligt" nicht.

**Die vorhergesagte Wirkung ist schon gemessen.** Weil der Vermerk die Gliederung nicht anfasst und
die Unantastbarkeit mit entfällt, ist die neue Betriebsgliederung **dieselbe**, die Block E am
2026-09-20 in der Zeile „aus" ausgewiesen hat: 26 Events statt 81, größtes Event 80 Fotos, längste
Dauer 5 h 3 min, Ein-Bild-Anteil 26,9 %. Weicht die Nachmessung davon ab, ist das ein Befund und
kein Rundungseffekt.

**Die getragene Kehrseite, benannt statt entdeckt:** Ein Event kann danach ein Fünftel der
Kandidaten eines Laufs umfassen. Block H hat dafür die Grundlage geliefert — die großen Events der
Zeile „aus" zeigen je genau **eine** Ortszelle, und die Motivzahl wächst unterlinear. Gegen
Überverschmelzung stehen ab jetzt allein Zeitlücke, Dauer, Schritt und Ausdehnung.

### Betroffene Dateien

**Backend**

- `backend/src/photosort/events.py` — eigene Konstanten, `EventSpanSignal` statt
  `DayBoundarySignal`, `name` am Protokoll, Ursachenmenge je Grenze, dritte Stufe, ein gemeinsamer
  innerer Durchlauf für `build_events` und die Erklärform.
- `backend/src/photosort/event_inputs.py` — **neu**, rein lesend: der Aufbau der
  `EventCandidate`-Menge, herausgezogen aus `worker.py`.
- `backend/src/photosort/event_probe.py` — **neu**, rein lesend: das Messkommando.
- `backend/src/photosort/worker.py` — ruft `event_inputs` auf; `_landmark_names`/`_plain_strengths`
  ziehen dorthin um. Beide Aufrufer (`run_criterion_scoring`, `rebuild_run_grouping`) bekommen die
  neue Gliederung über denselben Weg.
- `backend/src/photosort/geonames.py` — die bereits gerechnete Trefferentfernung (`geonames.py:153`)
  wird herausgegeben, aber **über einen eigenen, nur vom Messkommando benutzten Rückgabeweg, nicht
  auf `PlaceAnswer`**. Sie wird nicht persistiert und erreicht damit den `PlaceLookup`-Schreibrand
  in `worker.py` nicht (Security S4).

**In PR 8 ist von diesen genau eine Datei betroffen — `events.py`**, und darin drei Stellen: die
Bedingung in `explain_events`, die den Vermerk vom erzwungenen Start trennt; der Wegfall von
`UNBREAKABLE_CAUSES` samt seines Paars in `_may_merge`; und die Doku-Blöcke an
`BOUNDARY_MOTIF_CHANGE`, `MERGE_BLOCK_UNBREAKABLE`, `motif_change_starts`, `_may_merge` und
`explain_events`, die heute die entfallende Trennwirkung als geltende Regel beschreiben.
`event_probe.py` bleibt unangetastet: Es liest seinen Vorrat aus `events.py`, und Block E misst
danach von selbst das Richtige.

**Doku** — im selben Pull Request wie die Umsetzung, nicht in einem Nachzieh-Commit:

- `docs/architecture.md`, Abschnitt **Event**: die Signalliste (Kalendertag raus, Dauer rein), die
  dritte Stufe, die eigenen Konstanten und der Wegfall des Vermerks „unkalibriert".
- `docs/setup.md`: das Messkommando neben dem Abschnitt zu `place_probe`.
- `specs/architecture/0003-securitykonzept.md`: Fortschreibung unter „Standortdaten" und vier
  Zeilen in der Ankerliste (Security-Abschnitt, letzter Absatz).

**Nicht betroffen:** `models.py`, Alembic, jede API-Antwort, `frontend/`-**Produktivcode** (zwei
Testdateien wachsen, siehe Teststrategie), `scoring.py`,
`demo_state.py`.

**`selection.py` ist genau in einem Punkt betroffen, additiv:** `motif_is_present` und
`carried_motifs` nehmen einen optionalen `threshold` entgegen (`None` = Modulkonstante, Verhalten
dann unverändert). Das ist der einzige Weg, die Präsenzgrenze für Block E zu variieren, **ohne eine
zweite Fassung des Vergleichs zu bauen** — eine Nachbildung maße etwas anderes, als der Lauf tut.
**Kein auswählender Pfad gibt je einen Wert mit**, und der mitgegebene Wert ist ein Skalar für alle
Motive: Die Eindämmung aus ADR 0091 Punkt 1 (eine für alle Motive gleiche Grenze) bleibt damit
unangetastet. Durchgesetzt von
`tests/test_selection.py::TestOnlyTheMeasuringPathPassesItsOwnThreshold` — ein Aufrufer außerhalb
des Messwegs lässt den Test rot werden. Die **Auswahllogik** selbst (Kontingente, „Abdeckung
zuerst") bleibt unberührt.

### Zuschnitt: mehrere Pull Requests, Daniels Messung dazwischen

Ursprünglich zwei, mit jeder Messung um einen gewachsen — jeder Zuwachs steht unten mit seinem
Anlass. Von Daniel am 2026-09-18 freigegeben — die Ausnahme von „ein PR pro Issue", und sie hat einen
zwingenden Grund: Die Schwellen werden an einem echten Reiseprojekt kalibriert, und dafür muss das
Messkommando erst auf dem Server liegen. Ein einziger PR müsste die kalibrierten Werte enthalten,
bevor die Messung existiert, die sie liefert; „der Anteil der Ein-Bild-Cluster ist halbiert" wäre
ohne den gemessenen Ausgangswert kein prüfbares Kriterium.

- **PR 1** — Schritte 1–2: `event_inputs.py` (Umzug), `event_probe.py` mit den Blöcken A–C, die
  Ursachenmenge in `events.py`. **Keine Verhaltensänderung an der Gliederung.** Danach misst Daniel
  an einem echten Projekt und gibt die Ausgabe zurück; sie geht als Ausgangsmessung ins
  Messprotokoll.
- **PR 2** — **nach der Ausgangsmessung neu zugeschnitten** (Daniel am 2026-09-18): Die Messung hat
  gezeigt, dass die Schwellen nicht die Ursache sind und der Motivwechsel es ist. Statt direkt zu
  kalibrieren, misst PR 2 deshalb zuerst die **Empfindlichkeit des Motivwechsels** — ein Durchlauf
  über `MOTIF_CHANGE_CONFIRMING_PHOTOS` und die Motivstärke-Schwelle, der zeigt, wie Eventzahl und
  Ein-Bild-Anteil daran hängen. Danach misst Daniel erneut und entscheidet mit Zahlen, ob die
  Unantastbarkeit der Motivgrenze fällt, gelockert oder das Ziel gesenkt wird.
- **PR 3** — die eigentliche Änderung, deren Zuschnitt erst nach dieser zweiten Messung feststeht:
  die dritte Stufe (Zusammenlegen), die Dauergrenze als Vorsorge, und was die Empfindlichkeitsmessung
  an Schwellen nahelegt. Nachmessung in dasselbe Messprotokoll.
- **PR 4** — **nach der Nachmessung nötig geworden.** Sie hat die Abnahme verfehlt, und der Grund
  ist unbelegt: Stufe 3 hat nur 3 von 90 Grenzen aufgelöst. PR 4 liefert **Block F**, der misst,
  woran eine Zusammenlegung scheitert — wieder ohne Verhaltensänderung, nach demselben Grundsatz,
  der in dieser Story bereits zwei falsche Annahmen aufgedeckt hat. Was danach geändert wird,
  entscheidet Daniel an diesen Zahlen.
- **PR 5** — die Sehenswürdigkeit trennt nicht mehr, Riegel (c) bekommt `MERGE_EXTENT_MAX_METERS`
  (ADR 0118). Danach: Abnahme knapp verfehlt, und die Verzerrung der Albumauswahl unverändert.
- **PR 6 und PR 7** — wieder ohne Verhaltensänderung: der Album-Richtwert im Bericht, die Zeile
  „aus" in Block E, und Block H (`--kohaerenz`). Sie haben das Abnahmemaß korrigiert und die
  Entscheidung von PR 8 messbar gemacht.
- **PR 8** — die letzte Verhaltensänderung: Der Motivwechsel begründet nur noch mit, die
  Unantastbarkeit entfällt (ADR 0119). Nachmessung in dasselbe Messprotokoll; die Abnahme läuft
  gegen den Album-Richtwert.

**Der Ortsfehler ist abgeschlossen.** Block C hat keinen systematischen Fehler belegt; an der
Ortsbestimmung wird in dieser Spec nichts geändert. Der dabei abgefallene Befund zum
Sehenswürdigkeitsnamen ist als eigenes Issue
[#514](https://github.com/TheRealKoller/photosort/issues/514) festgehalten und ausdrücklich nicht
Teil dieser Story.

### Umsetzungsreihenfolge (testgetrieben)

1. ✅ `event_inputs.py` herausziehen — reiner Umzug (PR 1, #512).
2. ✅ `event_probe.py` mit Block A/B/C, dreiteiliger Nachweis „rein lesend" (PR 1, #512).
3. ✅ **Gemessen an Projekt 3** — Ergebnis im Messprotokoll; es hat die Annahme der Spec widerlegt.
4. ✅ Block E, Empfindlichkeitsmessung des Motivwechsels (PR 2, #515), und **gemessen** — sie hat
   auch den zweiten Hebel ausgeschlossen.
5. ~~Block D, Kalibrierungslauf~~ — **entfällt**, Begründung im Messprotokoll.
6. ✅ `EventSpanSignal` statt `DayBoundarySignal`, die eigenen Konstanten mit unveränderten Werten,
   und die dritte Stufe (Zusammenlegen) — **PR 3**. Block B weist zusätzlich die Gegenanzeige aus
   (Anteil der aufgelösten Grenzen, Anteil der Fotos, die dadurch ihr Event gewechselt haben).
7. ✅ Nachmessen mit demselben Kommando (Block A und B), Ergebnis in dasselbe Messprotokoll —
   danach PR 4 (Block F), PR 5 (Sehenswürdigkeit/Ausdehnung), PR 6/7 (Album-Richtwert, Zeile „aus",
   Block H) und Daniels Kohärenzmessung.

**PR 8 — testgetrieben, in dieser Reihenfolge.** Zwei Änderungen, die sich trennen lassen, und die
Trennung ist nicht Kosmetik: Nach Schritt 8 ist messbar, was der Wegfall des erzwungenen Starts
allein tut, und Schritt 9 fügt nichts hinzu, was Schritt 8 verdecken könnte.

8. **Der Vermerk statt des erzwungenen Starts** in `explain_events`. Rot zuerst, je eigener Fall:
   (a) zwei Fotos, die sich allein im getragenen Motiv unterscheiden, ohne trennendes Signal
   dazwischen → **ein** Event; (b) dieselbe Kandidatenmenge unter dem Betriebswert und unter einem
   nie erreichbaren Bestätigungsfenster → **identische** Eventfolge, verschiedene Ursachenmengen;
   (c) ein bestätigter Motivwechsel, der mit einer Zeitlücken-Grenze zusammenfällt →
   `{zeitluecke, motivwechsel}`; (d) ein bestätigter Motivwechsel ohne meldendes Signal → **keine**
   spätere Grenze trägt `motivwechsel`; (e) eine Lage, in der die entfallende Signal-Rücksetzung
   den Durchlauf **später** trennen lässt, als er es mit erzwungenem Start getan hätte — die eine
   Richtung, in der diese Änderung eine Grenze hinzufügt statt wegzunehmen.
9. **`UNBREAKABLE_CAUSES` entfernen.** Rot zuerst: (a) ein zu kleines Segment, dessen eröffnende
   Grenze `motivwechsel` trägt und dessen Nachbar alle drei Riegel erfüllt, wird zugeschlagen —
   die wörtliche Umkehrung des bis hierher geltenden Falls, ersetzt statt angepasst; (b)
   `MERGE_BLOCK_UNBREAKABLE` bleibt im Vorrat und wird von `_may_merge` unter keiner Lage geliefert.
10. **Doku im selben PR:** `docs/architecture.md` (Abschnitt Event), die Doku-Blöcke in `events.py`,
    diese Spec, ADR 0119 und die drei Teil-Vermerke, `specs/architecture/0003-securitykonzept.md`
    (`security-engineer`).
11. **Nachmessen** an Projekt 3 mit `--project-id 3` (Block A samt Album-Richtwert), `--riegel`,
    `--motiv` und `--kohaerenz`; Ergebnis in dasselbe Messprotokoll. Die Abnahme läuft gegen den
    Album-Richtwert.

**Bestehende Fälle, die das Gegenteil der neuen Zusage behaupten, werden ersetzt statt angepasst**
— ein angepasster Fall behält seinen Namen und prüft danach etwas anderes, als er verspricht.
Betroffen sind die Fälle in `test_events.py`, die einen bestätigten Motivwechsel **durch**
`build_events`/`explain_events` hindurch als Trennung prüfen, sowie der Fall zur unantastbaren
Grenze in Stufe 3. Die Fälle, die `motif_change_starts` **direkt** prüfen
(`test_events.py:883` ff.), bleiben unverändert gültig: Der Begriff ändert sich nicht, nur seine
Wirkung. Ebenfalls nachzuziehen: der Import von `UNBREAKABLE_CAUSES` in `test_events.py` und sein
Eintrag in der Gegenprobe `test_event_probe.py::test_the_closed_vocabularies_are_not_mistaken_for_adjustable`
samt der Aufzählung im Doku-Block von `_adjustable_constants_of_events` — ein Name, den es nicht
mehr gibt, macht die Gegenprobe an dieser Stelle still vakuum-grün.

### Was sich ausdrücklich nicht ändert

- **Die Auswahllogik in `selection.py` wird nicht angefasst.** „Abdeckung zuerst" (`selection.py:238-241`, jedes Event
  bekommt zuerst einen Platz) ist richtig, sobald ein Event eine Einheit ist. Eine zweite
  Reparatur derselben Verzerrung am Kontingent verdeckte, ob die erste wirkt.
- **Phase A** (`scoring.py::assign_clusters`, `PhotoScore.cluster_key`, der Ausschuss) bleibt
  unberührt — deshalb die eigenen Konstanten.
- **Die Ortsbestimmung selbst** wird in dieser Spec nicht geändert; Block C misst, er behebt nicht.
- **Kein Handlabeln, kein Training, kein Modell-Asset, keine neue Abhängigkeit, kein Cloud-Aufruf.**
- **Der Begriff des Motivwechsels** (Spec 0477 / ADR 0109) bleibt vollständig: Motivbild,
  symmetrische Differenz gegen das eröffnende Foto, Bestätigungsfenster, rückwirkende Lage, wer
  mitredet, und die mit dem Auswahlvorschlag geteilte Grenze. **Seine Trennwirkung bleibt es
  nicht** — sie fällt mit ADR 0119, und mit ihr die Zusage, dass ein motivgetrenntes Einzelbild
  allein bestehen darf. Geändert wird ausschließlich, was `explain_events` mit dem Ergebnis der
  ersten Stufe tut.

## Messprotokoll

Gegenstand der Abnahme.

**Kein Eintrag dieses Protokolls trägt eine Laufkennung** — der Bericht hat sie bis PR 9 nicht
ausgegeben. Jeder Eintrag identifiziert seinen Lauf relativ, als „letzter erfolgreicher
Kriterien-Lauf" des genannten Projekts zum genannten Datum. Das ist die offene Flanke des vierten
Akzeptanzkriteriums; ab PR 9 steht die Kennung im Kopf jedes Berichts.

### Ausgangsmessung (vor der Änderung)

Gemessen am 2026-09-18 an Projekt 3, letzter erfolgreicher Kriterien-Lauf, mit
`python -m photosort.event_probe --project-id 3` auf dem Stand von PR 1 (`de02a402`).

**Block A — Verteilung**

91 Events über 373 Fotos. **22 Ein-Bild-Cluster (24,2 %.)** Median der Fotozahl 3, größtes Event
28 Fotos. Verteilung: 1 Foto: 22, 2: 15, 3: 26, 4: 7, 5: 2, 6: 4, 7: 3, 8: 3, 9: 2, 10: 1, 11: 1,
13: 1, 16: 1, 19: 1, 21: 1, 28: 1.

**Längste Eventdauer 1 h 32 min, kürzeste 0 s.** Kein einziges Event reicht auch nur nahe an einen
Tag heran.

**Block B — Trennursachen** (90 Grenzen mit Ursache, Mindestgröße 2 Fotos)

| Ursache | beteiligt | alleinige Ursache | eröffnet ein zu kleines Segment |
|---|---|---|---|
| `zeitluecke` | 13 (14,4 %) | 5 (5,6 %) | 6 (46,2 %) |
| `kalendertag` | 4 (4,4 %) | 0 (0,0 %) | 2 (50,0 %) |
| `schritt` | 16 (17,8 %) | 0 (0,0 %) | 8 (50,0 %) |
| `ausdehnung` | 16 (17,8 %) | 0 (0,0 %) | 8 (50,0 %) |
| `sehenswuerdigkeit` | 10 (11,1 %) | 7 (7,8 %) | 6 (60,0 %) |
| `motivwechsel` | 62 (68,9 %) | **56 (62,2 %)** | 6 (9,7 %) |

**Block C — Ortszuordnung**

- **C1 (übernommener Ort):** 112 von 373 Kandidatenfotos (30,0 %) ohne eigene Koordinate, alle 112
  mit tatsächlicher Übernahme. Zeitabstand zum Anker: 93 (83,0 %) unter 1 min, 12 (10,7 %) unter
  5 min — und **7 (6,2 %) bei 12 h und mehr**. Ankerspanne: 107 (96,4 %) unter 250 m, 2 (1,8 %)
  zwischen 1 und 5 km, **2 (1,8 %) bei 10 km und mehr**, 1 ohne Spanne.
- **C2 (aufgelöster Ortsname):** 10 gefragte Zellen, alle 10 mit Namen. Entfernung zum
  namengebenden Eintrag: 1 unter 250 m, 4 unter 1 km, 4 unter 5 km, 1 unter 10 km. **0 über der
  Entfernungsschwelle.**
- **C3 (Sehenswürdigkeitsname):** 26 Erkennungen unter den Kandidaten, davon **11 (42,3 %) ohne
  jeden Ortshinweis**. 18 verschiedene Namen, davon 0 mit Trägerfotos über der Schwelle
  auseinander. **18 Events werden von genau einem von vielen Fotos benannt.**

### Was die Messung an dieser Spec widerlegt

Drei tragende Annahmen halten der Messung nicht stand. Das ist der Zweck des Vorgehens „erst
belegen, dann ändern" — es ist eingetreten, nicht schiefgegangen.

1. **Die vermutete Hauptursache ist es nicht.** Die Story ging davon aus, dass die Cluster an der
   Zeitlücke und der Ausdehnungsgrenze zerfallen. Tatsächlich ist der **Motivwechsel zu 62,2 % die
   alleinige Ursache** einer Grenze; die Zeitlücke kommt auf 5,6 %.
2. **Zwei der drei zu kalibrierenden Schwellen trennen nie allein.** `schritt` und `ausdehnung`
   stehen bei 0,0 % alleiniger Ursache — sie melden nur mit. Ihre Kalibrierung kann für sich
   **keine einzige** Grenze auflösen. Zusammen mit der Zeitlücke sind höchstens 5,6 % der Grenzen
   überhaupt erreichbar; der Ein-Bild-Anteil lässt sich daran nicht halbieren.
3. **Die Dauergrenze hat in diesen Daten keinen Gegenstand.** `kalendertag` ist 0,0 % alleinige
   Ursache, und die längste Eventdauer beträgt 1 h 32 min. Eine Dauergrenze statt des Kalendertags
   bleibt sinnvoll als Vorsorge (Silvester, Nachtflug), ist hier aber **keine Reparatur** und
   verändert an der Zerstückelung nichts.

**Damit ist die Auswahlregel aus Block D nicht erfüllbar**, und der in ihr vorgesehene Halteort
greift: Keine Schwellenkombination kann den Anteil der Ein-Bild-Cluster halbieren, weil die
Schwellen nicht die Ursache sind.

### Empfindlichkeitsmessung des Motivwechsels (Block E)

Gemessen am 2026-09-18 an Projekt 3 mit `python -m photosort.event_probe --motiv --project-id 3`
auf dem Stand von PR 2. Auszug der tragenden Zeilen; der Betriebswert ist `(3 | 0,5)`.

| bestätigende Fotos | Stärke-Grenze | Events | Ein-Bild-Cluster | `motivwechsel` allein | größtes Event | längste Dauer |
|---|---|---|---|---|---|---|
| **Betriebswert** | **Betriebswert** | **91** | **22 (24,2 %)** | **56 (62,2 %)** | **28** | **1 h 32 min** |
| 2 | 0,3 | 127 | 18 (14,2 %) | 93 (73,8 %) | 19 | 1 h 22 min |
| 4 | 0,3 | 82 | 16 (19,5 %) | 44 (54,3 %) | 20 | 1 h 31 min |
| 5 | 0,3 | 62 | 13 (21,0 %) | 24 (39,3 %) | **40** | **3 h 25 min** |
| 6 | 0,5 | 57 | 14 (24,6 %) | 18 (32,1 %) | **38** | **3 h 24 min** |

**Der Befund: Die Empfindlichkeit des Motivwechsels ist kein Hebel für dieses Ziel.** Drei
Beobachtungen tragen das, und sie schließen einander nicht aus, sondern verstärken sich.

1. **Ein unempfindlicherer Motivwechsel senkt die Eventzahl, nicht den Anteil.** Von Fenster 3 auf
   6 fällt die Eventzahl von 91 auf 57 und die Zahl der Ein-Bild-Cluster von 22 auf 14 — ihr
   **Anteil** bleibt bei 24,2 % gegen 24,6 %. Die Einzelbilder verschwinden nicht, die Grundmenge
   schrumpft mit. Genau diese Verwechslung fängt die Wahl des Anteils als Abnahmezahl ab.
2. **Die Gegenanzeige schlägt an, bevor der Anteil sich bewegt.** Ab Fenster 5 entstehen Events mit
   38 bis 40 Fotos und über 3 h Dauer, gegenüber 28 Fotos und 1 h 32 min am Betriebswert. Das ist
   die Richtung „mehrere Anlässe in einem Cluster", die Daniels Zielbild ausschließt — erkauft für
   einen Anteil, der sich nicht verbessert.
3. **Die Stärke-Grenze bewegt fast nichts.** Bei Fenster 6 liefern 0,4 bis 0,7 identische Zahlen
   (57 Events, 14 Ein-Bild-Cluster, 18 allein); bei Fenster 2 unterscheiden sich 0,4 bis 0,7 um
   zwei Events. Nur 0,3 fällt heraus. Als Stellschraube ist sie damit praktisch stumpf.

**Der beste Anteil der ganzen Tabelle kommt aus der Gegenrichtung** und ist trotzdem unbrauchbar:
`(2 | 0,3)` erreicht 14,2 % — mit **127** Events statt 91, also einer noch feineren Gliederung.
Das verfehlt das Zielbild „ein Cluster = ein Tag bzw. ein Anlass" in der anderen Richtung.

### Was daraus für die Umsetzung folgt

**Der erste Satz dieses Abschnitts ist am 2026-09-20 überholt worden** (siehe „Der Richtwert und der
Motivwechsel" weiter unten): Block E hatte den Fall „Motivgrenze ganz aus" nicht gemessen, und genau
er ist der Hebel. Die Motivgrenze ist seit ADR 0119 nicht mehr unantastbar. Der Abschnitt bleibt als
Stand vom 2026-09-18 stehen — er begründet, warum Block D entfallen ist, und das gilt weiter.

**Der Betriebswert des Motivwechsels bleibt unverändert** (`MOTIF_CHANGE_CONFIRMING_PHOTOS = 3`,
`MOTIF_PRESENCE_THRESHOLD = 0,5`), und die Motivgrenze bleibt **unantastbar**. Keine Messung stützt
eine Änderung: Jede Richtung verschlechtert entweder den Anteil oder das Zielbild.

**Block D (Kalibrierung der drei Schwellen) entfällt ersatzlos.** Die Ausgangsmessung hat gezeigt,
dass `schritt` und `ausdehnung` nie allein trennen und die Zeitlücke 5,6 % erreicht; ein
Kalibrierungslauf über Werte, die zusammen höchstens 5,6 % der Grenzen bewegen können, wäre Aufwand
ohne Aussicht. Die drei Schwellen behalten ihre heutigen Werte und ihren Vermerk „unkalibriert".

**Damit bleibt Stufe 3 — das nachträgliche Zusammenlegen — das einzige wirksame Mittel.** Es war
von Anfang an Teil des Plans (Daniels Leitplanke „beide Mittel, nicht nur eines"); die Messung
macht aus „auch" ein „allein".

Die Erwartung, gerechnet am Betriebswert: Von den 22 Ein-Bild-Clustern sind 6 durch `motivwechsel`
und 6 durch `sehenswuerdigkeit` eröffnet und damit gesperrt (Überschneidung unbekannt). Die
übrigen 10 bis 16 sind Kandidaten, soweit die vier Riegel halten. Bleiben 6 bis 12 bestehen, liegt
der Anteil danach zwischen 8 % und 15 % — das Ziel von ≤ 12,1 % ist erreichbar, aber nicht sicher.
**Die Nachmessung entscheidet es, nicht diese Schätzung.**

### Kalibrierung (Block D) — entfallen

Nicht durchgeführt und nicht gebaut. Begründung oben: Die zu kalibrierenden Schwellen bewegen
zusammen höchstens 5,6 % der Grenzen, `schritt` und `ausdehnung` davon 0,0 %. Sie behalten ihre
heutigen Werte und ihren Vermerk „unkalibriert".

### Nachmessung (nach der Änderung)

Gemessen am 2026-09-18 an Projekt 3, nach dem Merge von PR 3.

| | vorher | nachher | Ziel |
|---|---|---|---|
| Events | 91 | 88 | — |
| Ein-Bild-Cluster | 22 (24,2 %) | **18 (20,5 %)** | ≤ 12,1 % |
| längste Eventdauer | 1 h 32 min | 2 h 8 min | < 8 h |

**Gegenanzeige:** 3 von 90 Grenzen aufgelöst (3,3 %), 3 von 373 Fotos haben ihr Event gewechselt
(0,8 %).

**Die Abnahme ist verfehlt, und die Gegenanzeige sagt warum.** Der Anteil ist von 24,2 % auf 20,5 %
gefallen — das Ziel war ≤ 12,1 %. Stufe 3 hat dabei **nur drei** Grenzen aufgelöst. Sie hat also
nicht zu viel verschmolzen, sondern fast gar nichts; die 0,8 % gewechselter Fotos belegen, dass in
der anderen Richtung Luft ist.

**Der begründete Verdacht: Riegel (c) prüft dieselbe Bedingung, die die Trennung verursacht hat.**
Ein Segment, das wegen `ausdehnung` oder `schritt` abgetrennt wurde, lässt sich nicht
zurück-zusammenlegen — das Ergebnis überschritte `EVENT_EXTENT_MAX_METERS` erneut, weil genau diese
Überschreitung die Trennung ausgelöst hat. Beide Ursachen zusammen eröffnen 7 bzw. 7 der zu kleinen
Segmente. Das wäre ein Entwurfsfehler der dritten Stufe, kein Kalibrierungsproblem.

**Nicht belegt, sondern erschlossen.** An welchem der vier Riegel eine Zusammenlegung tatsächlich
scheitert, weist das Messkommando heute nicht aus. Bevor daran etwas geändert wird, gehört genau
das gemessen — nach demselben Grundsatz, der in dieser Story bereits zwei falsche Annahmen
aufgedeckt hat.

**Was funktioniert hat:** Die Dauergrenze trägt. `dauer` meldet an denselben vier Stellen, an denen
vorher `kalendertag` meldete, und in beiden Fällen nie allein — dort trennt ohnehin die Zeitlücke.
Die längste Eventdauer ist von 1 h 32 min auf 2 h 8 min gestiegen: Anlässe über Mitternacht bleiben
jetzt zusammen. Kein Event kommt `EVENT_MAX_SPAN` (8 h) auch nur nahe.

### Riegel-Diagnose (Block F), gemessen am 2026-09-19

An Projekt 3 nach dem Merge von PR 4, mit `python -m photosort.event_probe --riegel --project-id 3`.
Bezug: 88 Events, 18 Ein-Bild-Cluster, 3 durch Stufe 3 aufgelöste Grenzen, **18 zu kleine Segmente,
die bestehen blieben**.

| Grund | an einer Kante beteiligt | an allen Kanten **der** Grund |
|---|---|---|
| **`unantastbar`** | **14 (77,8 %)** | **7 (38,9 %)** |
| `ausdehnung` | 7 (38,9 %) | 3 (16,7 %) |
| `zeitluecke` | 5 (27,8 %) | 0 (0,0 %) |
| `dauer` | 4 (22,2 %) | 0 (0,0 %) |
| `kein_nachbar` | 0 (0,0 %) | 0 (0,0 %) |

**Die Unantastbarkeit ist der größte Blocker, der Ausdehnungs-Riegel der zweitgrößte.** An 14 von 18
Segmenten steht die Sperre an mindestens einer Kante, bei 7 ist sie der alleinige Grund; `ausdehnung`
kommt auf 3.

**`zeitluecke` und `dauer` sind nie allein der Grund.** `MERGE_MAX_GAP` zu erhöhen — der billigste
denkbare Eingriff — löste damit **kein einziges** Segment auf. Sichtbar wurde das erst, nachdem der
Kurzschluss in der Riegelprüfung behoben war: Vorher verdeckte der zuerst zutreffende Riegel die
späteren, und `ausdehnung` wird zuletzt geprüft.

**Eine Unschärfe, die diese Messung nicht auflöst:** `unantastbar` fasst `motivwechsel` und
`sehenswuerdigkeit` zusammen. Welcher der beiden wie oft sperrt, weist der Bericht nicht aus; aus
Block B lässt sich nur abschätzen, dass es grob hälftig ist (Motivwechsel eröffnet 5 zu kleine
Segmente, Sehenswürdigkeit 6). Mit PR 5 erledigt sich die Frage von selbst: Danach ist `unantastbar`
eindeutig der Motivwechsel.

### Abnahmemessung nach PR 5, gemessen am 2026-09-20

An Projekt 3, mit `python -m photosort.event_probe --project-id 3`.

| | Ausgang | nach PR 3 | **nach PR 5** | Ziel |
|---|---|---|---|---|
| Events | 91 | 88 | **81** | — |
| Ein-Bild-Cluster | 22 (24,2 %) | 18 (20,5 %) | **11 (13,6 %)** | ≤ 12,1 % |
| längste Eventdauer | 1 h 32 min | 2 h 8 min | 2 h 8 min | < 8 h |

**Das Ziel ist knapp verfehlt: 13,6 % gegen 12,1 %** — eine Reduktion um 44 % statt der
zugesagten 50 %. Es fehlen **zwei** Zusammenlegungen: Bei 10 Ein-Bild-Clustern stünde der Anteil
bei 12,5 %, erst bei 9 fiele er auf 11,4 %.

**Die Zusagen von PR 5 sind eingelöst.** `sehenswuerdigkeit` steht bei **0 (0,0 %)** — die als
Nachweis eingeplante ehrliche Null; kein Signal meldet den Namen mehr. Sieben Events und sieben
Ein-Bild-Cluster weniger als nach PR 3, exakt die sieben, die Block F als „unantastbar allein"
ausgewiesen hatte. `motivwechsel` ist unverändert absolut (56 → 57), steigt aber relativ auf
71,2 %, weil die Bezugsmenge kleiner wurde.

**Die neue Ausdehnungsgrenze hat nichts bewirkt, und das ist unerklärt.** Stufe 3 löst weiterhin
genau **3** Grenzen auf (3 von 90 nach PR 3, 3 von 83 nach PR 5). Die drei Segmente, die Block F
als „`ausdehnung` allein" auswies, sind trotz `MERGE_EXTENT_MAX_METERS = 1500 m` nicht
zusammengelegt worden. Zwei Erklärungen sind denkbar und beide unbelegt: Die Segmente liegen
weiter auseinander als die neue Grenze, oder nach dem Wegfall der Sehenswürdigkeits-Sperre
blockiert dort inzwischen ein anderer Riegel. Ein erneuter Block-F-Lauf würde es entscheiden.

**Die Gegenanzeige bleibt unauffällig:** 3 von 373 Fotos (0,8 %) haben ihr Event gewechselt. Zu
viel verschmolzen wurde nicht — eher zu wenig.

**Die Verteilung ist gesund**, auch wenn die Abnahmezahl es nicht ist: Median 3, **31 Events mit
genau drei Fotos**, größtes Event 28, längste Dauer 2 h 8 min. Der Anteil war ein Hilfsmaß für
„ein Cluster = ein Anlass"; ob das Zielbild getroffen ist, entscheidet der Blick in die
Kuratierung, nicht diese Tabelle.

### Der Richtwert und der Motivwechsel, gemessen am 2026-09-20

Das korrigierte Maß, an denselben Daten. **Der Album-Richtwert beträgt 41** (abgeleitet aus 408
Fotos des Projekts, ein Zehntel aufgerundet). Daniel hatte zwischenzeitlich 60 eingestellt; ohne
diese Einstellung ist der Konflikt **größer**, nicht kleiner.

> Die Kontingentvergabe kann nicht gewichten: 81 Events auf 41 Plätze — jedes Event bekommt genau
> einen Platz, und kein Restplatz bleibt übrig, bevor die Gewichtung nach Größe überhaupt beginnt.

Dazu die Auswertungsgrenze aus dem Bericht: Der Richtwert rechnet auf **408** Fotos des Projekts,
die Gliederung auf den **373** Kandidaten des letzten erfolgreichen Laufs. Beide Mengen fallen hier
auseinander.

**Block E mit der Zeile „aus":**

| | Events | Ein-Bild-Cluster | `motivwechsel` allein | größtes Event | längste Dauer |
|---|---|---|---|---|---|
| Betriebswert (3 / 0,5) | 81 | 11 (13,6 %) | 57 (71,2 %) | 28 | 2 h 8 min |
| **aus** | **26** | 7 (26,9 %) | 0 (0,0 %) | **80** | **5 h 3 min** |
| 6 / 0,4 (bester Rasterwert) | 44 | 8 (18,2 %) | 18 (41,9 %) | 38 | 3 h 24 min |

**Nur das Abschalten bringt die Eventzahl unter den Richtwert.** Das Minimum über das ganze Raster
ist 44 — immer noch über 41. Die Empfindlichkeit zu verstellen reicht damit grundsätzlich nicht;
das ist die dritte Maßnahme dieser Story, die eine Messung ausschließt.

**Der Preis steht daneben:** ein Event mit 80 Fotos über 5 Stunden, gegen 28 Fotos und 2 h 8 min am
Betriebswert. Ein Fünftel der Kandidaten läge in einem einzigen Cluster.

**Ein Hinweis darauf, warum das Maß korrigiert werden musste:** Der Ein-Bild-Anteil **steigt** bei
„aus" auf 26,9 %, während er absolut von 11 auf 7 fällt — die Grundmenge schrumpft stärker als der
Zähler. Nach dem alten Maß wäre die einzige wirksame Maßnahme als deutliche Verschlechterung
erschienen.

**Offen und Gegenstand der nächsten Messung:** ob das 80-Foto-Event ein langer Ausflug ist oder
mehrere verschmolzene Anlässe. Entschieden wird das an der Zahl der Ortszellen und der Motive je
Event — Anzahlen, keine Namen (Security S2/S3).

### Abnahmemessung nach PR 8, gemessen am 2026-09-20 — die Vorhersage ist eingetroffen

Vorgabe-Aufruf ohne Schalter, Projekt 3, letzter erfolgreicher Kriterien-Lauf (373 Kandidaten).

> **Die Kontingentvergabe kann gewichten: 26 Events auf 41 Plaetze — nach „Abdeckung zuerst"
> bleiben 15 Plaetze, die nach Groesse verteilt werden.**

Damit ist das Abnahmemaß erfüllt: Eventzahl echt kleiner als der Richtwert, freie Plätze echt
größer als 0, und das Urteil steht ausgeschrieben im Bericht.

**Die Gliederung ist bitgleich die vorhergesagte.** ADR 0119 sagte zu, dass die neue
Betriebsgliederung dieselbe ist wie die Zeile „aus" der Empfindlichkeitsmessung, weil der Vermerk
die Gliederung nicht anfasst und die Unantastbarkeit mit entfällt. Alle vier Größen treffen zu:

| | vorhergesagt | gemessen |
|---|---|---|
| Events | 26 | **26** |
| größtes Event | 80 Fotos | **80** |
| längste Dauer | 5 h 3 min | **5 h 3 min 34 s** |
| Ein-Bild-Anteil | 26,9 % | **26,9 % (7 von 26)** |

**Block A:** Median 3, kürzeste Eventdauer 0 s. Verteilung: 1 Foto: 7, 2: 4, 3: 3, 6: 2, 7: 1,
11: 1, 15: 1, 16: 1, 25: 1, 26: 1, 38: 1, 43: 1, 76: 1, 80: 1.

**Block B — beide Zusagen von ADR 0119 sind gemessen eingelöst.** 25 Grenzen mit Ursache
(Eventzahl − 1):

| Ursache | beteiligt | alleinige Ursache | eröffnet ein zu kleines Segment |
|---|---|---|---|
| zeitluecke | 12 (48,0 %) | **4 (16,0 %)** | 2 |
| dauer | 4 (16,0 %) | 0 (0,0 %) | 1 |
| schritt | 16 (64,0 %) | 0 (0,0 %) | 5 |
| ausdehnung | 16 (64,0 %) | 0 (0,0 %) | 5 |
| sehenswuerdigkeit | 0 (0,0 %) | 0 (0,0 %) | 0 |
| **motivwechsel** | **5 (20,0 %)** | **0 (0,0 %)** | 1 |

`motivwechsel` steht bei 0 allein und wird weiter als „beteiligt" gezählt — genau die bewegliche
Zahl, an der eine spätere Änderung dieser Entscheidung gemessen würde. `sehenswuerdigkeit` steht
seit PR 5 auf 0 und bleibt im Vorrat.

**Die Gliederung ist mehrfach belegt statt einfach.** Über 25 Grenzen verteilen sich 53
Beteiligungen, also gut zwei Ursachen je Grenze; nur **4** Grenzen tragen eine einzige Ursache, und
das ist jedes Mal die Zeitlücke. Die Ortssignale `schritt` und `ausdehnung` sind mit je 64 %
beteiligt, trennen aber weiterhin **nie allein** — dieselbe Aussage wie in der Ausgangsmessung,
jetzt aber bei einer Gliederung, die überhaupt erst von der Geografie bestimmt wird.

**Gegenanzeige gegen Überverschmelzung:** Stufe 3 löst **1 von 26** Grenzen auf (3,8 %), **1 von
373** Fotos wechselt dadurch das Event (0,3 %). Die Stufe greift damit fast nicht mehr — nicht,
weil sie gesperrt wäre (die Unantastbarkeit ist entfallen), sondern weil kaum noch zu kleine
Segmente entstehen.

**Die sieben Ein-Bild-Cluster bleiben, und das ist hier kein Rest.** Sie überstehen Stufe 3, obwohl
keine Grenze mehr unantastbar ist — es halten die Schwellen selbst. Ein einzelnes Foto, dessen
Nachbarn jenseits von `MERGE_EXTENT_MAX_METERS` liegen, ist ein eigener Ort und kein Ausreißer. Der
Anteil steigt gegenüber der Ausgangsmessung (24,2 % → 26,9 %), die absolute Zahl fällt von **22 auf
7**; beides war im Akzeptanzkriterium vorweggenommen.

**Block C ist gegenüber der Ausgangsmessung unverändert** und bestätigt sie: C1 112 von 373 ohne
eigene Koordinate (30,0 %), alle mit Übernahme, 7 mit 12 h und mehr Abstand zum Anker, 2 mit einer
Ankerspanne über 10 km. C2 10 gefragte Zellen, alle mit Namen, **0** über der Entfernungsschwelle.
C3 26 Erkennungen, davon 11 ohne jeden Ortshinweis (42,3 %), 18 verschiedene Namen, **0** mit
Trägerfotos über der Schwelle auseinander.

**Eine Zahl aus C3 hat sich mit der Gliederung bewegt:** Events, deren Name auf genau einem von
vielen Fotos beruht, gehen von 18 auf **8** zurück — bei zugleich weniger und größeren Events. Der
Befund selbst bleibt bestehen und gehört zu Issue
[#514](https://github.com/TheRealKoller/photosort/issues/514): Ein Name beruht weiterhin
regelmäßig auf einem einzigen, zu 42,3 % ortsblind erkannten Foto, und er reicht jetzt über ein
größeres Event. Genau dafür trägt das Sicherheitskonzept seit PR 8 einen eigenen Auslöser.


### Befund zur Ortszuordnung

Je Mechanismus getrennt, wie das Akzeptanzkriterium es verlangt:

- **C2 (aufgelöster Ortsname): kein systematischer Fehler, widerlegt.** Alle zehn gefragten Zellen
  bekommen einen Namen, keine einzige Zuordnung liegt über der Entfernungsschwelle, die weiteste
  unter 10 km. An der GeoNames-Auflösung wird nichts geändert.
- **C1 (übernommener Ort): kein systematischer Fehler, aber zwei benannte Ausreißer.** 96,4 % der
  Übernahmen haben eine Ankerspanne unter 250 m und 83,0 % einen Zeitabstand unter einer Minute —
  das ist eine Kamera ohne GPS neben einer mit, kein Fehler. Auffällig sind **7 Fotos mit 12 h und
  mehr Abstand zum Anker** und **2 mit einer Ankerspanne über 10 km**: Dort ist die Übernahme ein
  Münzwurf, und diese Fotos speisen `StepDistanceSignal`. Bei 373 Fotos sind das Einzelfälle, keine
  Systematik — sie erklären die Zerstückelung nicht.
- **C3 (Sehenswürdigkeitsname): ein Befund, aber nicht der vermutete.** Ein „falsches Land" ist
  nicht belegbar: 0 von 18 Namen haben Trägerfotos über der Schwelle auseinander. Belegt ist etwas
  anderes — **11 von 26 Erkennungen (42,3 %) entstanden ohne jeden Ortshinweis**, und **18 Events
  werden von genau einem von vielen Fotos benannt**. Der Name eines Events beruht also regelmäßig
  auf einem einzigen, ortsblind erkannten Foto und wirkt von dort als Trennsignal
  (`sehenswuerdigkeit`: 7,8 % alleinige Ursache, eröffnet zu 60 % ein zu kleines Segment).

Die im Architektur-Abschnitt benannte Grenze gilt: Ein in sich stimmiger Sehenswürdigkeitsname ist
offline nicht widerlegbar. Der Block belegt Widersprüche, er schließt sie nicht aus.

## UI/UX

Nicht relevant — das Feature hat keine sichtbare Oberflächenänderung. Event-Überschriften können
künftig Zeitspannen wie `23:40–01:15 Uhr` zeigen; im Kontext der Tagesgliederung ist das
selbsterklärend, ein zusätzlicher Datumshinweis ist nicht nötig. `formatEventHeading` und
`eventGrouping.ts` bleiben unverändert, weil `dayKey` aus `started_at` kommt und das Event damit im
Abschnitt seines Anfangstags steht.

## Security

**Sicherheitsrelevant.** Kein neuer Endpunkt, kein Auth-Pfad, keine Datenmodell-Änderung, keine
neue Abhängigkeit, kein Cloud-Aufruf, keine neue Eingabe von außen (`--project-id` ist ein `int`).
Relevanz entsteht an zwei Stellen: ein neues Kommando auf echten Familiendaten, und Zahlen daraus,
die dauerhaft in ein **öffentliches** Repository gehen.

- **S1 — Rein lesend, dreiteilig nachgewiesen wie `place_probe`, mit einer Stelle mehr.** Der
  Syntaxbaum-Wächter läuft über `event_probe.py` **und** `event_inputs.py`; die Import-Graph-Zusage
  gilt nur für `event_probe.py`, weil `event_inputs.py` per Konstruktion im Graph von `worker.py`
  liegt — eine Gegenprobe pinnt diese Richtung. Der Schnappschuss-Lauf deckt **jeden** Modus, die
  Vorgabe wie `--motiv`, `--riegel` und `--kohaerenz`; ein Modus ohne eigenen Fall liefe ungeprüft
  mit. Der Wächter wird nicht entschärft: beide Module verzichten auf `add`/`update`/
  `merge`/`delete` auch als Sammlungs-Methoden. Keine Stellschraube aus `events.py` wird beim
  Import gebunden — sie werden als Modulattribut gelesen, sonst zählt der Bericht gegen eine andere
  Größe als die, nach der gegliedert wurde. Der Syntaxbaum-Wächter erzwingt das und liest den
  Vorrat der Stellschrauben aus `events.py`, statt ihn zu führen.
- **S2 — Was die Ausgabe nie trägt:** keine Koordinate, keinen Orts- oder Sehenswürdigkeitsnamen,
  keinen OpenCloud-Pfad, **keinen Projektnamen** und **keinen Zeitstempel**. Ein Projektname ist
  eine Ortsangabe, ein `taken_at` ist der Zeitpunkt; ausgewiesen wird die Projekt-**Id**. Geprüft
  wie `test_place_probe.py::TestTheOutputSeparatesNumbersFromPlaces`, über alle sechs Klassen: Die
  Messlage trägt je einen unterscheidbaren Wert, und keiner steht im Bericht.
- **S3 — Kein Namens-Schalter.** `event_probe` bekommt kein `--namen`-Äquivalent: Bei `place_probe`
  waren die Namen der Messgegenstand, hier ist es die **Zahl** der Widersprüche. Pseudonymisierung
  (Hash, Kürzel, Präfix) ist kein Ausweg und untersagt — die Menge der Sehenswürdigkeitsnamen ist
  klein und öffentlich, ein stabiler Hash ist per Wörterbuch rückrechenbar.
- **S4 — Die Trefferentfernung bleibt eine Zahl ohne Namen.** Sie kommt **nicht** auf
  `PlaceAnswer` (dessen geschlossener Stufenvorrat ist selbst eine Zusage) und damit nicht an den
  `PlaceLookup`-Schreibrand; sie wird nicht persistiert, erreicht weder `PlaceInfo` noch
  `place_hint_for` und keinen Modell-Prompt, und steht im Bericht nie je Zelle und nie neben Name
  oder Ebene. Grund: Die Entfernung zu einem benannten, öffentlich enumerierbaren GeoNames-Eintrag
  ist ein Trilaterationsmittel — `locality` und `neighbourhood` derselben Zelle schneiden sich zu
  rund zwei Punkten und unterlaufen die 1,1-km-Körnung, die `PLACE_CELL_DIGITS = 2` zusichert.
- **S5 — Verteilungen nur in vorab festgelegten Klassen, nie als Einzelwert, nie in Reihenfolge.**
  Betroffen sind Ankerspannen und Zeitabstände zum Anker (Block C1): Beide entstehen aus voller
  EXIF-Präzision (`infer_locations` arbeitet auf `photos.gps_lat`/`gps_lon`, nicht auf Zellen) und
  sind zusammen ein Bewegungsprofil. Eine geordnete Folge von Spannen und Zeitlücken ist ein
  Streckenabdruck, eine Klassenverteilung ist es nicht. Eine Klassengrenze **ist** die
  Entfernungsschwelle, damit die Abnahme ohne Einzelwerte auskommt. Eventdauern stehen als Dauer,
  nie als Anfang/Ende.
- **S6 — Ins Messprotokoll kommt die stdout-Ausgabe, nichts daneben.** Der Umsetzungslauf sieht
  beim Messen echte Daten; die Zusage gilt der Ausgabe des Kommandos, nicht dem, was ein Lauf
  daneben notiert. Kein aus der Datenbank stammender Wert wird ergänzt. Ebenso: keine echten Werte
  in Testdaten — die Messlage der Tests ist erfunden.
- **S7 — Ausfallrichtung von Block C.** Fehlt der Ortsdatensatz oder weicht er von seinem Hash ab,
  meldet Block C „nicht gemessen", nie „0 %". Ein fehlendes Aggregat, das als gutes Messergebnis
  gelesen wird, trüge hier die Entscheidung, an der Ortsbestimmung nichts zu ändern (Muster
  `place_probe.py::CandidateResult.absent_reason`).
- **S8 — Unverändert weiter gilt:** keine Koordinate und kein Name in irgendeiner Logzeile von
  `events.py`/`event_inputs.py`/`event_probe.py` (festes Grund-Token plus Id); ein
  `SQLAlchemyError` nur mit Typnamen, nie `str(exc)` (die `DATABASE_URL` kann Zugangsdaten tragen);
  kein Compose-`command`, kein Endpunkt, kein automatischer Pfad.
- **S9 — Eine Ortsgröße je Event verlässt das System nur als Anzahl, nur für die größten wenigen,
  und nie in der Reihenfolge des Laufs.** Betroffen ist die Zahl der verschiedenen Ortszellen eines
  Events (Block H). Eine Zeile je Event wäre über diese Zahlen eine Bewegungsspur: Wie viele Orte
  ein Anlass berührt hat, ist einzeln eine Anzahl, über den ganzen Lauf gelesen das Profil einer
  Reise. Deshalb drei Riegel zugleich: **höchstens `COHERENCE_TOP_EVENTS` Zeilen** je Gliederung,
  **geordnet nach den gemessenen Werten statt nach der Zeit**, und **keine Position und keine
  Kennung des Events** — sonst ließen sich zwei Zeilen wieder einem Zeitpunkt zuordnen. Über
  *alle* Events geht ausschließlich die Klassenverteilung „Zellzahl → Zahl der Events", die selbst
  keine Reihenfolge trägt. Die Dauer daneben steht als Dauer (S5); aus ihr und der Zellzahl ist
  eine mittlere Verweildauer je Zelle ableitbar, und das trägt nur, solange keine Zelle benannt ist
  — eine Verweildauer ohne Ort lokalisiert nichts.
- **S10 (PR 8) — Die Kontrollflusswirkung der Motivstärke fällt auf null, und drei Auflagen ziehen
  nach.** Nach ADR 0119 bewegt keine vom Modell gelieferte Zahl mehr eine Event-Grenze; der
  Motivwechsel vermerkt nur noch eine Ursache. Daraus folgt dreierlei. (a) Das Vergleichsverbot aus
  ADR 0091 Punkt 1 bleibt in `events.py` **Muss**, obwohl sein Gegenstand dort auf ein
  Berichtssymbol schrumpft — `carried_motifs` bleibt geteilt, und ein zweiter Begriff von „dieses
  Foto zeigt X" bekäme seine Wirkung beim nächsten Leser zurück. (b) M9-e wird **umformuliert, nicht
  aufgehoben**: Sie nennt die vier Riegel statt `UNBREAKABLE_CAUSES`, sonst verwiese ein Muss auf
  ein Symbol, das es nicht mehr gibt. Die Zahl der Riegel bleibt vier — die Unantastbarkeit war
  keiner von ihnen, sondern ein eigener Sperrgrund daneben. (c) `MERGE_BLOCK_UNBREAKABLE` nennt
  nichts mehr und führt eine ehrliche Null; er bleibt als Berichtswortschatz stehen, damit ein
  Block-F-Lauf gegen den vom 2026-09-19 zu halten ist. Neu als Muss: `COHERENCE_TOP_EVENTS` bleibt
  eine **absolute** Zahl — hinter derselben Zeile stehen danach mehr Fotos, und ein als Anteil
  gefasster Deckel wüchse mit den größer werdenden Events mit.

**Sicherheitskonzept:** `specs/architecture/0003-securitykonzept.md` wird im selben Pull Request
fortgeschrieben — unter „Standortdaten" (erstmals gehen Messzahlen aus echten Familiendaten
dauerhaft ins öffentliche Repository; S2, S4, S5 und S9 als neue Auflagen) und mit drei Zeilen in
der Ankerliste (Messkommando rein lesend einschließlich `event_inputs.py`; Trefferentfernung
namenlos und unpersistiert; Ortsgröße je Event nur als gedeckelte, größengeordnete Anzahl). Mit
PR 8 kommt eine eigene Fortschreibung zu ADR 0119 dazu (S10), dazu ein Teil-Vermerk am Abschnitt zu
ADR 0109 und ein Restrisiko-Eintrag: Die ausgeschöpfte Reichweite eines einzelnen
Sehenswürdigkeitsnamens wächst auf rund ein Fünftel der Kandidaten eines Laufs. Die Bezifferung
trägt und die Abflussrichtung bleibt entlastend; **Daniel hat am 2026-09-20 entschieden, dass die
Benennung keine eigene Auflage bekommt** — der Schaden ist Anzeigequalität, die Plausibilisierung
des Namens bleibt Issue #514, und ein eigener Auslöser stellt die Frage neu, sobald ein Name über
mehr als ein Viertel der Kandidaten reicht oder große Events mehrere Ortszellen zeigen.

## Teststrategie

**Schwerpunkt Unit, DB-frei** (`backend/tests/test_events.py`). **Kein Test pinnt einen Zahlwert
der sechs Konstanten**; geprüft wird „unter/über der Schwelle → erwartetes Verhalten" über
injizierte Signale, `>` gegen `>=` über einen injizierten, vorher gemessenen Wert. Eine
`autouse`-Fixture setzt die sechs Konstanten per `monkeypatch.setattr` auf mehrere Werte und
erzwingt diese Zusage, statt sie zu behaupten — dafür werden sie im Code als **Modulattribut**
gelesen, nie als Default-Parameterwert gebunden. Zulässig bleiben genau drei Aussagen über
Zahlwerte, und alle drei sind Ungleichungen: `MERGE_MAX_GAP > EVENT_TIME_GAP`,
`MIN_EVENT_PHOTOS >= 2`, `EVENT_MAX_SPAN < 24 h` (letzteres ist die Vorbedingung der
Überschriftenform `23:40–01:15 Uhr`).

**Stufe 3 ist eine öffentliche reine Funktion über den Segmenten** und wird direkt geprüft, nicht
durch `build_events` hindurch; `build_events` nimmt ihre Parameter injizierbar entgegen, sonst
laufen 26 bestehende Fälle still durch sie hindurch und Block D kann sie nicht variieren. Geprüft
werden: die drei Tie-Break-Stufen je an einem gebauten Gleichstand, die vier Riegel je einzeln
(jeweils greift genau einer, die anderen drei halten), ~~beide unantastbaren Grenzen~~ — seit ADR
0119 stattdessen die Umkehrung: eine Grenze mit `motivwechsel` **wird** aufgelöst, sobald die drei
Riegel halten —, „kein Nachbar
zulässig → bleibt allein", **Idempotenz** als maschinenprüfbare Form des Stillstands, eine je
Runde strikt fallende Segmentzahl, und eine Rundenobergrenze, die **wirft statt abzubrechen**.
Ein stiller Frühabbruch ließe eine halb zusammengelegte Gliederung zurück, die niemandem auffiele.

**Die Ursachenmenge** trägt am Index 0 die leere Menge — die Ausnahme hängt an der Position, nicht
an `TimeGapSignal`, sonst braucht jedes künftige Signal seine eigene. Gepinnt durch ein
eingeschleustes, immer trennendes Signal, durch den Zwilling (leer am Anfang / `{zeitluecke}` an
der zweiten Grenze in identischer Lage) und durch die Invariante **`Ursachen == Events − 1`**.

**Invariante über jede Event-Folge aus dem vollen Signalsatz:** kein Event über `EVENT_MAX_SPAN`,
keines über `EVENT_EXTENT_MAX_METERS` — als Nachsatz über der ganzen Fallmenge, nicht als
Einzelfall.

**„Rein lesend" wird zweimal geführt.** Für `event_probe.py` dreiteilig nach dem Muster von
`tests/test_place_probe.py` (Import-Graph, Syntaxbaum-Wächter mit Mikrotests und
Positiv-Gegenproben, echter `main()`-Lauf mit Tabellen-Schnappschuss davor und danach) — **je
Argumentform einmal**, `--schwellen` eingeschlossen. Der Formwächter gilt **je Modul, nicht je
Import-Graph**: Über die Import-Hülle angewandt schlägt er auf `events.py`, `selection.py` und
`geonames.py` an (Sammlungs-Methoden, falsch positiv). `event_inputs.py` bekommt deshalb einen
eigenen und erbt dessen Auflage (kein `set.add`, kein `dict.update` in dieser Datei). Der
Compose-Wächter läuft über **beide** Modulnamen; nur mit dem alten Namen kopiert wäre er still
vakuum-grün.

**Gemessen wird mit den Mitteln des Laufs** — ein eigener Fall, den „rein lesend" nicht mitdeckt:
ein Datensatz, `event_inputs` einmal über den Worker-Pfad und einmal über den Probe-Pfad, die
beiden `EventCandidate`-Mengen feldgleich.

**Integration** (`test_worker_criterion_scoring.py`, `test_worker_rebuild_run_grouping.py`) prüft
nur noch das Verdrahten und die eine Bindung beider Aufrufer. Keine Migration, kein E2E-Bezug —
`demo_state.py` schreibt `Event`-Zeilen direkt.

**Frontend** ändert sich nicht, der Eingaberaum schon: je ein neuer Fall in
`utils/timeOfDay.test.ts` und `utils/eventGrouping.test.ts` für ein Event über Mitternacht
(Spanne `23:40–01:15 Uhr`, Abschnitt des **Anfangstags**). Der bestehende Fall „liefert den
Kalendertag des EVENT-ANFANGS" (`timeOfDay.test.ts:170`, 23:50–23:59) unterscheidet diese
Möglichkeit heute nicht.

**Vor Schritt 6 der Umsetzungsreihenfolge** laufen die Konstanten einmal probeweise verschoben
durch den ganzen Prüfsatz. Bereits gemessen (`EVENT_TIME_GAP` 3 h, Schritt 1500 m, Ausdehnung
4000 m): sieben Fälle bauen ihre Testlage aus Zahlen, die nur gegen die heutigen Werte aufgehen,
und müssen vorher umgebaut werden — `test_events.py:495`, `:508`, `:639`, `:652`, `:674`,
`test_worker_criterion_scoring.py:4601`, `test_worker_rebuild_run_grouping.py:181`. Vier weitere
behaupten das Gegenteil der neuen Zusage und werden ersetzt statt angepasst: `test_events.py:379`
(`TestDayBoundarySignal`), `:1013` (prüft `started_at.date() == ended_at.date()` je Event),
`:1119`/`:1130` samt der Referenz in `:1095`, `:1234`.

**Coverage.** `event_probe.py` und `event_inputs.py` liegen innerhalb des Gates
(`--cov-fail-under=80`); die Blöcke A–D brauchen je eigene Zähl-Tests gegen einen von Hand
ausgerechneten Projektgraphen.

**Zwei Halteorte für den Umsetzungslauf** (Produktentscheidung, nicht ersatzweise selbst treffen):
ob Block C eine Auffälligkeit als behebungswürdig ausweist, und der Fall, dass keine
Schwellenkombination die Auswahlregel aus Block D erfüllt.

**Testkonzept:** `specs/architecture/0002-testkonzept.md` wird im selben Pull Request um vier
Muster ergänzt, die über dieses Feature hinausgehen — eine Stufe nach dem Durchlauf samt Idempotenz
als Stillstandsnachweis; ein Terminierungsargument, das nicht trägt, sobald eine Runde nichts tun
darf; der Formwächter „rein lesend" gilt je Modul, nicht je Import-Graph; und: steht eine
Kalibrierung an, ist jede aus einem Zahlwert gebaute Testlage eine Zeitbombe, auch wenn sie die
Konvention formal einhält.

## Entscheidungen

- **Zwei Mittel, nicht eines** (Daniel im Refinement): Schwellen kalibrieren **und** zu kleine
  Cluster nachträglich anhängen. Nur zu kalibrieren reicht nicht.
- **Zielbild** (Daniel): ein Cluster = ein Tag bzw. ein Anlass. Ein Ausflug über mehrere Stunden
  und Orte ist ein Cluster, mehrere Reisetage sind es nicht.
- **Die Kalendertagsgrenze wird gelockert** (Daniel): Ein Anlass darf über Mitternacht laufen.
- **Der Ortsfehler wird zuerst belegt, nicht auf Verdacht behoben** (Daniel): ohne Messung ließe
  sich an einer Behebung nichts abnehmen.
- **Eigene Konstanten für `events.py`** (architect, technisch): Die geteilten Konstanten steuern
  auch Phase A vor dem Ausschuss-Gate; eine Kalibrierung an ihnen verschöbe still die
  Kandidatenmenge.
- **„Falsches Land" wird durch eine Entfernungsschwelle vertreten** (architect, technisch): Der
  Ländercode steht nicht in den behaltenen Feldern des Ortsauszugs.
- **Die Trennursache wird nicht persistiert** (architect, technisch).
- **`ux-ui-designer` konsultiert (Schritt 2), Ergebnis „nicht relevant"** — keine
  Oberflächenänderung.
- **Das AK zum Ortsfehler ist in der Aussage geändert, nicht nur geschärft** (test-engineer): „in
  welchem Anteil der Fälle ein falsches Land herauskommt" ist mit dem gewählten Ortsauszug nicht
  berechenbar und wäre als geschrieben nie erfüllbar gewesen. An seine Stelle tritt die
  Entfernungsschwelle je Mechanismus.
- **Ob eine Auffälligkeit in Block C eine Behebung auslöst, entscheidet Daniel** (test-engineer):
  „systematischer Fehler" ist ohne vorab festgelegte Schwelle nicht entscheidbar; die ehrliche
  Auflösung ist ein benannter Halteort statt einer erfundenen Prozentzahl.
- **Das Terminierungsargument in ADR 0117 war falsch und wurde korrigiert** (test-engineer): „jede
  Runde nimmt mindestens eines weg" gilt nicht, sobald ein Segment an einem Riegel scheitert.
- **Der Motivwechsel darf eine Grenze mitbegründen, aber nie allein eröffnen; die Unantastbarkeit
  fällt mit weg** (Daniel am 2026-09-20, an den Zahlen von Block H und dem Album-Richtwert). Damit
  ist die frühere Festlegung „die Motivgrenze bleibt unantastbar" aufgehoben: Sie beruhte auf
  Block E, und Block E hatte den Fall „ganz aus" noch nicht gemessen.
- **Das Abnahmemaß ist der Album-Richtwert statt des Ein-Bild-Anteils** (Daniel am 2026-09-20): Der
  Anteil fiel, während die Verzerrung blieb; er war ein Hilfsmaß und wird weiter ausgewiesen, aber
  nicht mehr abgenommen.
- **`UNBREAKABLE_CAUSES` verschwindet ganz, statt als leerer Vorrat stehen zu bleiben** (architect,
  technisch): Es ist kein Wortschatz, sondern eine an jeder Kante gelesene Regel — das Kriterium aus
  ADR 0118 Punkt 2, hier auf den ganzen Vorrat angewandt. Der Berichtsgrund
  `MERGE_BLOCK_UNBREAKABLE` bleibt dagegen mit ehrlicher Null stehen.
- **`MIN_EVENT_PHOTOS` bleibt bei 2** (architect, technisch, in Daniels Vorbehalt): Der Vorbehalt
  hing am Ein-Bild-Anteil, und der ist nicht mehr das Abnahmemaß. Mit rund 26 statt 81 Events hat
  eine höhere Mindestgröße keinen Gegenstand mehr und räumte echte kleine Anlässe weg.

## Offene Fragen

Keine. Die drei bestehenden Schwellen behalten ihre heutigen Werte (Block D entfällt), und die drei
neuen entstehen aus dem gemessenen Bestand — ihre Herleitung steht bei der jeweiligen Konstante.

Eine Frage ist **beantwortet und hier festgehalten**, weil sie beim Lesen des Messprotokolls
naheliegt: Ob die Motivgrenze angetastet wird. **Sie wird es — seit dem 2026-09-20.** Die frühere
Antwort („sie wird es nicht") beruhte auf Block E in seiner ersten Fassung, der die
*Empfindlichkeit* des Motivwechsels durchgerechnet, den Fall „ganz aus" aber ausgelassen hatte. Die
nachgetragene Zeile „aus" und Block H haben die Antwort gedreht: Nur das Abschalten bringt die
Eventzahl unter den Album-Richtwert, und die großen Events, die dabei entstehen, zeigen je genau
eine Ortszelle. ADR 0119 hält die Auflösung fest — der Motivwechsel begründet mit, eröffnet aber
nicht mehr allein.

## Out of Scope

- **Die Behebung des Ortsfehlers**, solange Block C keinen systematischen Fehler belegt. Belegt er
  einen, ist die Behebung Teil dieser Spec; welcher der drei Mechanismen betroffen ist, entscheidet
  die Messung.
- **Eine Plausibilitätsprüfung Name↔GPS für Sehenswürdigkeiten** gegen einen externen Dienst.
- **Änderungen am Auswahlvorschlag** (`selection.py`) und an Phase A (`scoring.py`).
- **Jede Form von Handarbeit** an Clustern — Bestätigen, Verschieben, Korrigieren.
- **Ein Settings-/Env-Wert für die Schwellen.**
