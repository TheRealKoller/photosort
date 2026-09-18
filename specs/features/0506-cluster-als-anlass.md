# 0506 - Cluster entsprechen einem zusammenhängenden Anlass

**Status:** Accepted
**Erstellt:** 2026-09-18
**Bezug:** [Issue #506](https://github.com/TheRealKoller/photosort/issues/506), ADR
[`0117`](../decisions/0117-der-anlass-als-einheit-eigene-schwellen-dauergrenze-und-mindestgroesse.md)

**Umfang:** rund 370 Zeilen zu 100 Zeichen gegen einen Richtwert von 200. Die Story trägt zwei
Vorhaben in einem — erst messen, dann ändern —, und beide brauchen ihren Teil: vier Messblöcke mit
je eigener Auflage, was die Ausgabe tragen darf, sechs Konstanten, die kalibriert werden, und ein
Messprotokoll, das der Gegenstand der Abnahme ist. Dazu kommen die Zusicherungen, deren
Ausfallrichtung benannt sein muss, weil sie sonst still brechen.

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

**Zuerst belegen, was ist**

- [ ] `python -m photosort.event_probe --project-id <N>` gibt für den letzten erfolgreichen
      Kriterien-Lauf eines echten Projekts die Verteilung der Events nach Fotozahl aus (je Fotozahl
      die Eventzahl), dazu den Anteil der Ein-Bild-Cluster, den Median, das größte Event sowie die
      längste und kürzeste Eventdauer.
- [ ] Dieselbe Ausgabe weist je Trennursache aus dem geschlossenen Vorrat zwei Zahlen aus — „war
      beteiligt" und „war alleinige Ursache" — sowie den Anteil der Grenzen, die ein Segment unter
      `MIN_EVENT_PHOTOS` eröffnet haben. Die Zahl der Grenzen mit Ursache ist stets
      `Eventzahl − 1`: Das erste Segment eines Laufs trägt keine Ursache.
- [ ] Der beobachtete Ortsfehler ist **je Mechanismus getrennt** belegt oder widerlegt —
      übernommener Ort, aufgelöster Ortsname, Sehenswürdigkeitsname. Je Mechanismus ist
      nachvollziehbar, wie weit die Ortsaussage von der Aufnahmeposition abweicht und in welchem
      Anteil der Fälle sie eine festgelegte Entfernungsschwelle überschreitet; diese Schwelle
      vertritt „falsches Land", weil der Ländercode im Ortsauszug nicht geführt wird.
- [ ] Diese Messergebnisse stehen als Blöcke A, B und C im Abschnitt „Messprotokoll" dieser Spec,
      mit Projekt-Id und Laufkennung — und ohne jede Koordinate, ohne Orts- oder
      Sehenswürdigkeitsnamen und ohne OpenCloud-Pfad.

**Einen Anlass zusammenhalten**

- [ ] Eine Folge von Aufnahmen, deren größte Einzel-Zeitlücke unter `EVENT_TIME_GAP`, deren größter
      Einzelschritt unter `EVENT_STEP_MAX_METERS`, deren Ausdehnung unter
      `EVENT_EXTENT_MAX_METERS` und deren Gesamtdauer unter `EVENT_MAX_SPAN` liegt, bildet genau
      ein Event — gleich über wie viele Stunden, Kilometer und Kalendertage sie läuft.
- [ ] Eine Kalendertagsgrenze allein trennt nicht mehr: Zwei Aufnahmen beiderseits von Mitternacht,
      deren Zeitlücke unter `EVENT_TIME_GAP` liegt und deren Event-Gesamtdauer unter
      `EVENT_MAX_SPAN` bleibt, stehen im selben Event. Dessen Überschrift zeigt dann eine Spanne
      der Form `23:40–01:15 Uhr` und steht im Abschnitt seines **Anfangstags**.
- [ ] Ein Segment mit weniger als `MIN_EVENT_PHOTOS` Fotos wird genau einem **angrenzenden**
      Segment zugeschlagen: dem mit der kleineren Zeitlücke, bei Gleichstand dem mit der kleineren
      Entfernung, danach dem früheren — und nur, wenn alle vier Riegel halten. Hält keiner der
      beiden Nachbarn, bleibt das Segment unverändert bestehen; das ist ein gültiges Ergebnis, kein
      Fehlerfall.
- [ ] Nach der Änderung ist an denselben Daten messbar, dass der Anteil der Ein-Bild-Cluster
      **mindestens halbiert** ist gegenüber dem in „Messprotokoll" festgehaltenen Ausgangswert.

**Dabei nicht zu viel verschmelzen**

- [ ] Kein Event überschreitet `EVENT_MAX_SPAN`, und keines überschreitet
      `EVENT_EXTENT_MAX_METERS` — weder als Ergebnis des Signal-Durchlaufs noch als Ergebnis des
      Zusammenlegens.
- [ ] Eine Grenze, deren Ursachenmenge `motivwechsel` oder `sehenswuerdigkeit` enthält, wird vom
      Zusammenlegen nie aufgelöst — auch dann nicht, wenn beide Nachbarn alle vier Riegel erfüllen
      und das Segment aus einem einzigen Foto besteht.
- [ ] Die Nachmessung weist aus, welcher Anteil der Grenzen durch das Zusammenlegen aufgelöst wurde
      und welcher Anteil der Fotos dadurch das Event gewechselt hat.
- [ ] Weder Datenmodell noch API-Antwort noch Oberfläche bekommen ein Feld, einen Endpunkt oder
      eine Geste zum Bestätigen, Verschieben oder Korrigieren eines Clusters. Das Zusammenlegen
      wirkt allein im Lauf bzw. beim Neuaufbau.

**Die Ortszuordnung**

- [ ] Block C weist je Mechanismus aus, ob eine Auffälligkeit vorliegt. Ob sie eine Behebung
      innerhalb dieser Spec auslöst, entscheidet Daniel anhand der festgehaltenen Zahlen; der
      Umsetzungslauf hält an dieser Stelle an, statt selbst zu entscheiden.
- [ ] Bleibt es bei „keine Behebung", steht das mit Begründung im Messprotokoll, und an der
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
| `EVENT_TIME_GAP` | Zeitlücke, ab der ein neues Event beginnt | kalibriert (heute `TIME_CLUSTER_GAP`, 1 h) |
| `EVENT_STEP_MAX_METERS` | Schritt zwischen zwei Aufnahmen | kalibriert (heute 500 m aus Phase A) |
| `EVENT_EXTENT_MAX_METERS` | Diagonale der umschließenden Box | kalibriert (heute 1000 m, unkalibriert) |
| `EVENT_MAX_SPAN` | **neu** — Dauer vom eröffnenden bis zum betrachteten Foto | kalibriert |
| `MIN_EVENT_PHOTOS` | **neu** — Größe, unter der ein Segment zugeschlagen wird | kalibriert |
| `MERGE_MAX_GAP` | **neu** — Zeitlücke, die ein zu kleines Segment überbrücken darf | kalibriert, `> EVENT_TIME_GAP` |

Alle sechs bleiben Modulkonstanten, ausdrücklich **kein** Settings-/Env-Wert, und verlieren mit
der Kalibrierung ihren Vermerk „unkalibriert". Kein Test prüft einen Zahlwert — geprüft wird wie
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

**Doku** — im selben Pull Request wie die Umsetzung, nicht in einem Nachzieh-Commit:

- `docs/architecture.md`, Abschnitt **Event**: die Signalliste (Kalendertag raus, Dauer rein), die
  dritte Stufe, die eigenen Konstanten und der Wegfall des Vermerks „unkalibriert".
- `docs/setup.md`: das Messkommando neben dem Abschnitt zu `place_probe`.
- `specs/architecture/0003-securitykonzept.md`: Fortschreibung unter „Standortdaten" und zwei
  Zeilen in der Ankerliste (Security-Abschnitt, letzter Absatz).

**Nicht betroffen:** `models.py`, Alembic, jede API-Antwort, `frontend/`, `selection.py`,
`scoring.py`, `demo_state.py`.

### Zuschnitt: zwei Pull Requests, Daniels Messung dazwischen

Von Daniel am 2026-09-18 freigegeben — die Ausnahme von „ein PR pro Issue", und sie hat einen
zwingenden Grund: Die Schwellen werden an einem echten Reiseprojekt kalibriert, und dafür muss das
Messkommando erst auf dem Server liegen. Ein einziger PR müsste die kalibrierten Werte enthalten,
bevor die Messung existiert, die sie liefert; „der Anteil der Ein-Bild-Cluster ist halbiert" wäre
ohne den gemessenen Ausgangswert kein prüfbares Kriterium.

- **PR 1** — Schritte 1–2: `event_inputs.py` (Umzug), `event_probe.py` mit den Blöcken A–C, die
  Ursachenmenge in `events.py`. **Keine Verhaltensänderung an der Gliederung.** Danach misst Daniel
  an einem echten Projekt und gibt die Ausgabe zurück; sie geht als Ausgangsmessung ins
  Messprotokoll.
- **PR 2** — Schritte 4–7: Dauergrenze statt Kalendertag, eigene Konstanten, Block D und
  Kalibrierungslauf, die dritte Stufe, Nachmessung in dasselbe Messprotokoll.
- **Ein PR 3** entsteht nur, wenn Block C einen systematischen Ortsfehler belegt **und** Daniel
  dessen Behebung auslöst. Das entscheidet er nach der Messung, nicht der Lauf.

### Umsetzungsreihenfolge (testgetrieben)

1. `event_inputs.py` herausziehen — reiner Umzug, bestehende Worker-Tests bleiben grün.
2. `event_probe.py` mit Block A/B/C, dazu der dreiteilige Nachweis „rein lesend".
3. **Messen an einem echten Reiseprojekt**, Ergebnis in den Abschnitt „Messprotokoll".
4. `EventSpanSignal` und die eigenen Konstanten (unveränderte Startwerte → Gliederung unverändert).
5. Block D, Kalibrierungslauf, gewählte Werte eintragen.
6. Die dritte Stufe (Zusammenlegen).
7. Nachmessen mit demselben Kommando, Ergebnis in dasselbe Messprotokoll.

### Was sich ausdrücklich nicht ändert

- **`selection.py` wird nicht angefasst.** „Abdeckung zuerst" (`selection.py:238-241`, jedes Event
  bekommt zuerst einen Platz) ist richtig, sobald ein Event eine Einheit ist. Eine zweite
  Reparatur derselben Verzerrung am Kontingent verdeckte, ob die erste wirkt.
- **Phase A** (`scoring.py::assign_clusters`, `PhotoScore.cluster_key`, der Ausschuss) bleibt
  unberührt — deshalb die eigenen Konstanten.
- **Die Ortsbestimmung selbst** wird in dieser Spec nicht geändert; Block C misst, er behebt nicht.
- **Kein Handlabeln, kein Training, kein Modell-Asset, keine neue Abhängigkeit, kein Cloud-Aufruf.**
- **Der Motivwechsel** (Spec 0477 / ADR 0109) bleibt vollständig, einschließlich der Zusage, dass
  ein motivgetrenntes Einzelbild allein bestehen darf.

## Messprotokoll

Gegenstand der Abnahme. Wird im Lauf der Umsetzung gefüllt; bis dahin steht hier, was hineingehört.

### Ausgangsmessung (vor der Änderung)

- **Block A:** _(Verteilung, Anteil Ein-Bild-Cluster, Median, größtes Event, längste/kürzeste Dauer)_
- **Block B:** _(je Ursache „beteiligt" / „alleinige Ursache", Anteil der zu kleinen Segmente)_
- **Block C:** _(je Mechanismus die dort genannten Kennzahlen)_

### Kalibrierung (Block D)

- **Tabelle:** _(je Schwellenkombination Eventzahl, Anteil Ein-Bild-Cluster, größte Dauer, Anteil
  über einem Tag)_
- **Gewählte Zeile:** _(nach der oben festgelegten Auswahlregel)_

### Nachmessung (nach der Änderung)

- **Block A, B, C erneut**, mit demselben Kommando und demselben Projekt.
- **Abnahme:** Anteil der Ein-Bild-Cluster mindestens halbiert; kein Event über `EVENT_MAX_SPAN`.

### Befund zur Ortszuordnung

_(Ausfüllen nach Block C: systematischer Fehler belegt — dann Behebung und Nachmessung — oder
nicht belegt, dann bleibt die Ortsbestimmung unverändert. Die Grenze der Aussage für Weg 3
(Sehenswürdigkeitsname) ist im Architektur-Abschnitt benannt und gilt hier.)_

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
  liegt — eine Gegenprobe pinnt diese Richtung. Der Schnappschuss-Lauf deckt **beide** Modi, auch
  `--schwellen`. Der Wächter wird nicht entschärft: beide Module verzichten auf `add`/`update`/
  `merge`/`delete` auch als Sammlungs-Methoden.
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

**Sicherheitskonzept:** `specs/architecture/0003-securitykonzept.md` wird im selben Pull Request
fortgeschrieben — unter „Standortdaten" (erstmals gehen Messzahlen aus echten Familiendaten
dauerhaft ins öffentliche Repository; S2, S4 und S5 als neue Auflagen) und mit zwei Zeilen in der
Ankerliste (Messkommando rein lesend einschließlich `event_inputs.py`; Trefferentfernung namenlos
und unpersistiert).

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
(jeweils greift genau einer, die anderen drei halten), beide unantastbaren Grenzen, „kein Nachbar
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

**Vor Schritt 4 der Umsetzungsreihenfolge** laufen die Konstanten einmal probeweise verschoben
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

## Offene Fragen

Keine. Die Schwellenwerte selbst sind nicht offen, sondern durch die Auswahlregel in Block D
festgelegt; ihre Zahlen entstehen im Kalibrierungslauf und werden im Messprotokoll festgehalten.

## Out of Scope

- **Die Behebung des Ortsfehlers**, solange Block C keinen systematischen Fehler belegt. Belegt er
  einen, ist die Behebung Teil dieser Spec; welcher der drei Mechanismen betroffen ist, entscheidet
  die Messung.
- **Eine Plausibilitätsprüfung Name↔GPS für Sehenswürdigkeiten** gegen einen externen Dienst.
- **Änderungen am Auswahlvorschlag** (`selection.py`) und an Phase A (`scoring.py`).
- **Jede Form von Handarbeit** an Clustern — Bestätigen, Verschieben, Korrigieren.
- **Ein Settings-/Env-Wert für die Schwellen.**
