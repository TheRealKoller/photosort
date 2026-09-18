# 0117 - Der Anlass ist die Einheit: eigene Schwellen, Dauergrenze statt Kalendertag, Mindestgröße als dritte Stufe

**Status:** Accepted
**Datum:** 2026-09-18
**Bezug:** Spec `specs/features/0506-*.md`, ADR
[`0087`](./0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md) (Abschnitt 5, letzter
Absatz — die Tagesgrenze — wird hier abgelöst), ADR
[`0109`](./0109-motivwechsel-trennt-in-einem-vorgelagerten-durchlauf.md) (die vorgelagerte Stufe,
hier um eine nachgelagerte ergänzt), ADR
[`0105`](./0105-ortsnamen-aus-dem-lokalen-datensatz-als-auszug-auf-einem-volume.md) (der
Ortsdatensatz, der die Grenze dessen setzt, was gemessen werden kann)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung sechs Punkte trägt und
zwei davon (die Riegel gegen Überverschmelzung, die Grenze der Ortsmessung) ohne ihre
Ausfallrichtung nicht anwendbar sind.

**Vermerk nach der Messung (2026-09-18).** Zwei Zusagen dieser ADR sind von der Messung an einem
echten Projekt überholt und gelten in der genannten Form **nicht**; alles übrige gilt unverändert.

1. **Punkt 1, letzter Halbsatz — die Kalibrierung findet nicht statt.** Die drei Schwellen
   (`EVENT_TIME_GAP`, `EVENT_STEP_MAX_METERS`, `EVENT_EXTENT_MAX_METERS`) ziehen zwar wie
   entschieden nach `events.py` um, behalten aber ihre heutigen Werte **und ihren Vermerk
   „unkalibriert"**. Grund: Sie bewegen zusammen höchstens 5,6 % der Grenzen, `schritt` und
   `ausdehnung` davon 0,0 %. Damit fällt auch der Satz aus Punkt 5, die Konstanten verlören ihren
   Vermerk „unkalibriert" — sie tun es nicht.
2. **Punkt 5, zweiter Absatz — es gibt keinen Kalibrierungslauf** und keine „vorab ausgeschriebene
   Auswahlregel", gegen die die Abnahme liefe. Die Abnahme läuft gegen die Nachmessung derselben
   Blöcke A und B. Die Injizierbarkeit von `build_events` bleibt davon unberührt und ist
   umgesetzt: Sie trägt jetzt die Empfindlichkeitsmessung und die drei Stufen-Parameter.

Die Begründung im Einzelnen steht im Abschnitt „Messprotokoll" der Spec
[`0506`](../features/0506-cluster-als-anlass.md).

## Kontext

Die Gliederung zerfällt in sehr kleine Einheiten, oft in Einzelbilder. Weil der Auswahlvorschlag
sein Kontingent je Event vergibt und dabei **jedem** Event zuerst einen Platz gibt
(`selection.py::_quotas`, „Abdeckung zuerst"), bekommt ein Einzelbild dasselbe Gewicht wie ein
ganzer Reisetag. Die Einheit selbst muss stimmen; am Kontingent ist nichts zu reparieren.

Zwei Eigenschaften der heutigen Bildung tragen das nicht: Die Schwellen sind unkalibriert und
teilen sich mit Phase A eine Konstante, und der Kalendertag trennt jeden Anlass, der über
Mitternacht läuft.

## Entscheidung

### 1. Die Event-Bildung bekommt eigene Schwellen; Phase A bleibt unberührt

`TimeGapSignal` und `StepDistanceSignal` stehen heute auf `scoring.TIME_CLUSTER_GAP` und
`scoring.GPS_CLUSTER_SPLIT_DISTANCE_METERS`. **Dieselben zwei Konstanten steuern
`assign_clusters`**, also die grobe Gliederung **vor** dem Ausschuss-Gate und damit, welche Fotos im
Ausschuss gegeneinander antreten. Eine Kalibrierung an ihnen verschöbe still, welche Bilder
überhaupt Kandidaten werden.

`events.py` führt deshalb eigene Konstanten (`EVENT_TIME_GAP`, `EVENT_STEP_MAX_METERS`, neben dem
bestehenden `EVENT_EXTENT_MAX_METERS`). Sie bleiben Modulkonstanten, ausdrücklich **kein** Settings-
oder Env-Wert: eine fachliche Festlegung, keine Betriebseinstellung — ihre Änderung ist eine Zahl
plus ein Neuaufbau der Gliederung, keine Migration.

### 2. Die Dauer des Events tritt an die Stelle des Kalendertags

`DayBoundarySignal` entfällt. An seine Stelle tritt ein zustandsbehaftetes Signal im Muster von
`ExtentSignal`: Ein neues Event beginnt, wenn die Spanne vom **eröffnenden** Foto bis zum gerade
betrachteten `EVENT_MAX_SPAN` überschreitet — geprüft **einschließlich** des betrachteten Fotos,
sonst begänne das neue Event ein Foto zu spät.

Damit läuft ein Anlass über Mitternacht (Silvester, langer Abend, Nachtflug) in **einem** Event, und
mehrere Reisetage laufen es nicht: Die Grenze ist die Dauer, nicht das Datum. Sie ist zugleich der
einzige zeitliche Riegel gegen Überverschmelzung und wirkt deshalb auch in Punkt 3.

Die Dauer braucht eine Zahl, wo der Kalendertag keine brauchte — und ist dafür **zonenfrei
richtig**: `taken_at` ist zonenlos, ein Kalendertag ist eine Aussage der lokalen Zeitzone, eine
Zeitspanne dagegen die Differenz zweier naiver Zeitstempel.

### 3. Die Mindestgröße wirkt als dritte Stufe **nach** dem Durchlauf, nicht als Signal

Ein Segment mit weniger als `MIN_EVENT_PHOTOS` Fotos wird dem angrenzenden Segment zugeschlagen, zu
dem es zeitlich und örtlich gehört. Das ist im `BoundarySignal`-Protokoll nicht ausdrückbar —
dieselbe Begründung wie bei ADR 0109, nur in die andere Richtung: Ob ein Segment zu klein ist, steht
erst fest, wenn es abgeschlossen ist.

**Der Nachbar** ist der mit der kleineren Zeitlücke zum Rest; bei Gleichstand der mit der kleineren
Entfernung, danach der frühere. Ausschließlich **angrenzende** Segmente, sonst entstünde eine
zeitlich zerrissene Einheit.

**Vier Riegel, und sie sind die Zusage „höchstens ein Anlass":** Zugeschlagen wird nur, wenn (a) die
Zeitlücke zum Nachbarn `MERGE_MAX_GAP` nicht überschreitet, (b) die Dauer des Ergebnisses
`EVENT_MAX_SPAN` nicht überschreitet, (c) die Ausdehnung des Ergebnisses `EVENT_EXTENT_MAX_METERS`
nicht überschreitet und (d) das Segment selbst unter der Mindestgröße liegt — ein normal großes
Event wird nie zugeschlagen. Ist kein Nachbar zulässig, **bleibt das Segment allein**; das ist ein
gültiges Ergebnis und kein Ausnahmezweig.

`MERGE_MAX_GAP` ist dabei größer als `EVENT_TIME_GAP` und muss es sein: Ein Rest von ein, zwei
Bildern trägt keinen eigenen Beleg dafür, dass mit ihm ein neuer Anlass begann.

**Zwei Grenzen sind unantastbar:** Eine Grenze, die ein Motivwechsel oder ein Wechsel der
Sehenswürdigkeit gemeldet hat, wird nie aufgelöst. Sie sind die einzigen Signale, die zwei
verschiedene Anlässe **am selben Ort zur selben Zeit** trennen; ohne diesen Vorrang wäre die Zusage
„zwei erkennbar verschiedene Anlässe bleiben getrennt" nicht durchsetzbar. Ein durch Motivwechsel
abgetrenntes Einzelbild kann dadurch allein bleiben — ADR 0109 sagt genau das bereits zu.

Der Durchgang läuft bis zum Stillstand, höchstens so viele Runden wie es Segmente gibt. Je Runde
wird das kleinste Segment behandelt, **das nicht bereits als gesperrt feststeht**, bei Gleichstand
das frühere — der Stillstand ist damit deterministisch und hängt nicht an einer
Iterationsreihenfolge.

**Der Zusatz „nicht bereits gesperrt" trägt die Terminierung**, nicht die Rundenzahl: Ein Segment,
das an einem der vier Riegel scheitert, wird durch keine spätere Runde zulässig, und ohne den
Zusatz wählte jede Runde dasselbe gesperrte Segment erneut. Die Rundenobergrenze **wirft** dann
auch, statt abzubrechen — ein Abbruch ließe eine halb zusammengelegte Gliederung zurück, die
plausibel aussieht und an der niemandem etwas auffiele.

### 4. Die Trennursache entsteht im Durchlauf und wird nicht persistiert

Jedes Signal trägt einen Namen aus einem geschlossenen Vorrat; jede Grenze trägt die **Menge** der
Signale, die sie gemeldet haben — nie ein einzelnes: Der Durchlauf wertet alle Signale aus (ADR 0087
Abschnitt 3), und mehrere dürfen gleichzeitig zutreffen. Ein Bericht, der je Grenze eine Ursache
nennt, addierte sich zu mehr als hundert Prozent oder unterschlüge Ursachen.

Die Menge ist **kein** Spaltenwert: Stufe 3 liest sie im selben Durchlauf, das Messkommando bildet
sie ohnehin neu, und eine Spalte wäre nach jeder Schwellenänderung veraltet, ohne dass es auffiele.

### 5. Gemessen wird mit den Mitteln des Laufs, nicht mit einer Nachbildung

Der Aufbau der `EventCandidate`-Menge zieht aus `worker.py` in ein eigenes, **rein lesendes** Modul
und bekommt damit zwei Aufrufer: den Lauf und ein rein lesendes Messkommando im Muster von
`place_probe.py` (Aufruf in der Container-Konsole; es gibt auf dem Server keine Shell, und
`scripts/` liegt nicht im Image). Eine zweite, nachbildende Fassung maße etwas anderes, als der Lauf
tut, während beide für sich grün blieben.

**Kalibriert wird ohne Handarbeit**, als Durchrechnung derselben Kandidatenmenge unter mehreren
Schwellenkombinationen — möglich, weil `build_events` seine Signale injizierbar entgegennimmt und
rein ist. Gewählt wird nach einer in der Spec **vorab** ausgeschriebenen Regel; Tabelle und gewählte
Zeile werden dort festgehalten und sind die Grundlage der Abnahme. Die Konstanten verlieren damit
ihren Vermerk „unkalibriert".

**Die Ausgabe trägt keine Koordinate, keinen Orts- oder Sehenswürdigkeitsnamen und keinen
OpenCloud-Pfad** — dieselbe Auflage wie bei `place_probe.py`, hier zusätzlich die Bedingung dafür,
dass die Zahlen als Ganzes ins Repository dürfen. Ein Ortsname *ist* die Ortsangabe.

### 6. Der Ortsfehler wird je Mechanismus gemessen; „anderes Land" wird durch eine Entfernung vertreten

Drei Wege führen zu einer falschen Ortsaussage, sie haben verschiedene Behebungen, und eine
Gesamtzahl über alle drei wäre für keine davon eine Grundlage. Gemessen wird deshalb getrennt: die
Herleitung eines Orts für ein Foto ohne eigene Koordinate, die Auflösung eines Ortsnamens aus dem
Ortsdatensatz, und der vom Modell gemeldete Sehenswürdigkeitsname.

**Ein Land ist im Bestand nicht berechenbar.** Der Auszug führt Orte und Verwaltungsebenen, keine
Grenzen und keine Bauwerke, und der Ländercode steht nicht in den behaltenen Feldern. „Falsches
Land" wird deshalb durch eine **Entfernungsschwelle** vertreten: Eine Zuordnung, die um mehr als
diese Entfernung von der Aufnahmeposition abweicht, ist falsch, ob sie eine Grenze überschreitet
oder nicht.

**Die Lücke wird benannt statt geschlossen:** Ein Sehenswürdigkeitsname, der in sich stimmig ist —
ein einzelnes Vorkommen, kein Widerspruch zu einem anderen Foto desselben Namens —, ist ohne eine
Rückfrage bei einem bezahlten Dienst nicht überprüfbar. Die Diagnose kann diesen Weg **belegen**
(über Widersprüche und über den Anteil der Erkennungen, die ganz ohne Ortshinweis entstanden),
aber nicht **widerlegen**. Ein Messergebnis „kein systematischer Fehler" gilt für die beiden
anderen Wege vollständig und für diesen nur, soweit die Widersprüche reichen.

## Konsequenzen

- ADR 0087 bekommt einen zweiten Teil-Vermerk: Abschnitt 5, letzter Absatz (die Tagesgrenze) gilt
  nicht mehr. Die Ausdehnung als Diagonale der umschließenden Box, das Protokoll und die Liste als
  Erweiterungspunkt bleiben unberührt.
- Die Gliederung ändert sich für **jeden** Lauf, auch ohne neue Cloud-Aufrufe. Bestehende Läufe
  behalten ihre Events, bis sie neu berechnet werden; Event-Ids überleben einen Neuaufbau nicht.
- `selection.py` wird nicht angefasst. „Abdeckung zuerst" ist richtig, sobald ein Event eine Einheit
  ist; eine zweite Reparatur derselben Verzerrung am Kontingent verdeckte, ob die erste wirkt.
- Eine Überschrift kann jetzt `23:40–01:15 Uhr` lauten. Das Event bleibt im Abschnitt seines
  **Anfangstags** (`dayKey` kommt aus `started_at`); ob die Spanne einen Datumshinweis braucht,
  entscheidet die Oberfläche.
- Keine Migration, keine Schemaänderung, kein neues Feld in der API.
- Der Zusatzaufwand ist ein weiterer Durchgang über die Segmente, nicht über die Fotos.
- `docs/architecture.md` zieht im selben Pull Request nach.
