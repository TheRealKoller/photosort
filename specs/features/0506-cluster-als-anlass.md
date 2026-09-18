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
      **mindestens halbiert** ist gegenüber dem in „Messprotokoll" festgehaltenen Ausgangswert
      (24,2 %, also Ziel ≤ 12,1 %). **Dieses Kriterium steht unter Vorbehalt:** Die Ausgangsmessung
      hat gezeigt, dass die Schwellen nicht die Ursache sind und die Motivgrenze es ist; solange
      diese unantastbar bleibt, ist die Halbierung voraussichtlich nicht erreichbar. Ob das Ziel
      bleibt oder sinkt, entscheidet Daniel nach der Empfindlichkeitsmessung (Block E).

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

**Der Vorrat oben ist der Endzustand nach PR 2.** In PR 1 heißt die Ursache `kalendertag` statt
`dauer`: Die Dauergrenze entsteht erst in Schritt 4, und Block B soll den **Ist-Zustand** messen —
eine Ursache zu benennen, die noch gar nicht trennt, machte die Ausgangsmessung unbrauchbar. Mit
PR 2 tritt `dauer` an ihre Stelle, zusammen mit `EventSpanSignal`.

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

`MOTIF_CHANGE_CONFIRMING_PHOTOS` liegt in `events.py`, die Stärke-Schwelle als
`MOTIF_PRESENCE_THRESHOLD` in `selection.py`. **Beide werden in diesem Schritt nicht geändert**,
sondern nur variiert durchgerechnet; die Messung ist rein lesend wie die Blöcke A–C.

**Was die Messung entscheidbar macht, entscheidet sie nicht:** Ob die Motivgrenze unantastbar
bleibt, gelockert wird oder das Halbierungsziel sinkt, legt Daniel anhand der Zahlen fest. Der Lauf
hält an dieser Stelle an.

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

**Nicht betroffen:** `models.py`, Alembic, jede API-Antwort, `frontend/`, `scoring.py`,
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
- **PR 2** — **nach der Ausgangsmessung neu zugeschnitten** (Daniel am 2026-09-18): Die Messung hat
  gezeigt, dass die Schwellen nicht die Ursache sind und der Motivwechsel es ist. Statt direkt zu
  kalibrieren, misst PR 2 deshalb zuerst die **Empfindlichkeit des Motivwechsels** — ein Durchlauf
  über `MOTIF_CHANGE_CONFIRMING_PHOTOS` und die Motivstärke-Schwelle, der zeigt, wie Eventzahl und
  Ein-Bild-Anteil daran hängen. Danach misst Daniel erneut und entscheidet mit Zahlen, ob die
  Unantastbarkeit der Motivgrenze fällt, gelockert oder das Ziel gesenkt wird.
- **PR 3** — die eigentliche Änderung, deren Zuschnitt erst nach dieser zweiten Messung feststeht:
  die dritte Stufe (Zusammenlegen), die Dauergrenze als Vorsorge, und was die Empfindlichkeitsmessung
  an Schwellen nahelegt. Nachmessung in dasselbe Messprotokoll.

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
6. `EventSpanSignal` statt `DayBoundarySignal`, die eigenen Konstanten mit unveränderten Werten,
   und die dritte Stufe (Zusammenlegen) — **PR 3**.
7. Nachmessen mit demselben Kommando (Block A und B), Ergebnis in dasselbe Messprotokoll.

### Was sich ausdrücklich nicht ändert

- **Die Auswahllogik in `selection.py` wird nicht angefasst.** „Abdeckung zuerst" (`selection.py:238-241`, jedes Event
  bekommt zuerst einen Platz) ist richtig, sobald ein Event eine Einheit ist. Eine zweite
  Reparatur derselben Verzerrung am Kontingent verdeckte, ob die erste wirkt.
- **Phase A** (`scoring.py::assign_clusters`, `PhotoScore.cluster_key`, der Ausschuss) bleibt
  unberührt — deshalb die eigenen Konstanten.
- **Die Ortsbestimmung selbst** wird in dieser Spec nicht geändert; Block C misst, er behebt nicht.
- **Kein Handlabeln, kein Training, kein Modell-Asset, keine neue Abhängigkeit, kein Cloud-Aufruf.**
- **Der Motivwechsel** (Spec 0477 / ADR 0109) bleibt vollständig, einschließlich der Zusage, dass
  ein motivgetrenntes Einzelbild allein bestehen darf.

## Messprotokoll

Gegenstand der Abnahme.

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

- **Block A und B erneut**, mit demselben Kommando und demselben Projekt. Block C entfällt: Er hat
  keinen systematischen Fehler belegt, und an der Ortsbestimmung ändert diese Spec nichts.
- **Abnahme:** Anteil der Ein-Bild-Cluster mindestens halbiert (≤ 12,1 %); kein Event über
  `EVENT_MAX_SPAN`; die neu ausgewiesene Gegenanzeige (Anteil der aufgelösten Grenzen, Anteil der
  Fotos, die ihr Event gewechselt haben) bleibt erklärbar.

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

## Offene Fragen

Keine. Die drei bestehenden Schwellen behalten ihre heutigen Werte (Block D entfällt), und die drei
neuen entstehen aus dem gemessenen Bestand — ihre Herleitung steht bei der jeweiligen Konstante.

Eine Frage ist **beantwortet und hier festgehalten**, weil sie beim Lesen des Messprotokolls
naheliegt: Ob die Motivgrenze angetastet wird. Sie wird es nicht. Block E zeigt, dass jede Richtung
entweder den Anteil verschlechtert oder das Zielbild verfehlt; ADR 0109 und Spec 0477 bleiben damit
vollständig in Kraft.

## Out of Scope

- **Die Behebung des Ortsfehlers**, solange Block C keinen systematischen Fehler belegt. Belegt er
  einen, ist die Behebung Teil dieser Spec; welcher der drei Mechanismen betroffen ist, entscheidet
  die Messung.
- **Eine Plausibilitätsprüfung Name↔GPS für Sehenswürdigkeiten** gegen einen externen Dienst.
- **Änderungen am Auswahlvorschlag** (`selection.py`) und an Phase A (`scoring.py`).
- **Jede Form von Handarbeit** an Clustern — Bestätigen, Verschieben, Korrigieren.
- **Ein Settings-/Env-Wert für die Schwellen.**
