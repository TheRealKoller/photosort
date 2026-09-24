# 0123 - Der Sehenswürdigkeitsname wird lokal verortet und am fertigen Event geprüft

**Status:** Accepted
**Datum:** 2026-09-24
**Teilweise abgelöst:** ADR
[`0106`](./0106-grobe-ortsangabe-geht-in-die-sehenswuerdigkeits-erkennung.md) Punkt 5, und dort
ausschließlich die Begründung „Ein lokaler Abgleich … ist damit im Bestand nicht möglich" — sie ist
durch die Messung unten widerlegt. Die Auflage im Prompt bleibt in Kraft und wird nicht
zurückgenommen; die lokale Prüfung tritt **neben** sie, nicht an ihre Stelle. Punkt 1 bis 4 und 6
gelten unverändert. ADR [`0120`](./0120-der-sehenswuerdigkeitsname-braucht-rueckhalt-und-der-ortsname-tritt-daneben.md)
gilt vollständig weiter; ADR [`0107`](./0107-sehenswuerdigkeitsname-eine-grenze-und-ein-projektgebundenes-namensregister.md)
ebenso (das Register entscheidet **welchen** Namen, ADR 0120 **ob** er Rückhalt hat, diese
Entscheidung **ob** er am richtigen Ort liegt). ADR
[`0105`](./0105-ortsnamen-aus-dem-lokalen-datensatz-als-auszug-auf-einem-volume.md) Punkt 3 wird
**ergänzt**, nicht abgelöst: der dort beschriebene Ortsauszug bleibt unverändert, ein zweiter tritt
daneben.
**Bezug:** Issue #529

**Umfang:** rund 165 Zeilen gegen einen Richtwert von 100. Drei Zusagen, die ohne ihre Kehrseite
nicht anwendbar sind (die Dreiwertigkeit der Auskunft, das Verhalten ohne Datensatz, der
ausdrücklich getragene Namensverlust), und eine Messung, die eine geltende ADR-Aussage widerlegt und
deshalb belegt werden muss statt behauptet.

## Kontext

Ein Cluster einer Schottlandreise trug den Namen „Tower of London". Die Konfidenzgrenze (ADR 0107)
und der Trägeranteil (ADR 0120) greifen gegen die Unsicherheit des Modells, nicht gegen
geografische Falschheit: Ein Name, den das Modell sicher und auf vielen Fotos nennt, passiert beide
Riegel auch dann, wenn er tausend Kilometer daneben liegt. ADR 0106 Punkt 5 hat die Prüfung dem
Modell selbst übertragen, mit der Begründung, ein lokaler Abgleich sei im Bestand nicht möglich.

**Diese Begründung ist gemessen falsch.** Gemessen am vollständigen GeoNames-Bestand
(13.472.162 Zeilen, 2026-09-24) gegen 50 reale Sehenswürdigkeitsnamen in neun Ländern, deutsch und
englisch geschrieben: **45 von 50** sind in den Klassen `S`/`T`/`L`/`H`/`V` auffindbar, jeder davon
mit einem Treffer im erwarteten Land und ohne Fehltreffer in einem falschen. Drei Zahlen daraus
tragen je eine Festlegung unten:

- **12 der 45 nur über das Feld `alternatenames`** (u.a. `Eiffelturm`, `Brandenburger Tor`,
  `Karlsbrücke`, `Trevi-Brunnen`) — das Feld ist Bedingung, nicht Zugabe: ohne es fielen 33 von 50
  durch, mit ihm 5 (Punkt 1).
- **Homonyme sind häufig**: `Stonehenge` 48 Treffer, `Ben Nevis` 60, `Loch Lomond` 66 — geprüft
  werden muss Name **und** Umkreis, nie der Name allein (Punkt 5).
- **5 von 50 sind gar nicht auffindbar** (`Berner Münster`, `Elbphilharmonie`,
  `Glenfinnan Viaduct`, `Holyrood Palace`, `Zytglogge`) — der Preis in Punkt 2 Zustand (2).

## Entscheidung

### 1. Ein zweiter, eigener Auszug neben dem Ortsauszug

Der Ortsauszug aus ADR 0105 Punkt 3 (`P`+`A`, 5,77 Mio. Zeilen, 69 MB gepackt, 3,3 s je Durchgang)
bleibt **unverändert**. Daneben entsteht ein zweiter Auszug mit den Klassen `S`, `T`, `L`, `H`, `V`
und zusätzlich dem Feld `alternatenames` (gemessen: 7,62 Mio. Zeilen, rund 659 MB roh, rund 204 MB
gepackt; dieselbe Formatregel wie dort — Original-Spalten, ungebrauchte Felder leer, derselbe
Parser). `asciiname` wird nicht mitgelesen: In der Messung war kein Name allein über dieses Feld
auffindbar, den `alternatenames` nicht auch liefert. Beide Dateien entstehen aus **einem** Bezug
durch **ein** Kommando (`python -m photosort.place_dataset`), liegen auf demselben Volume und
tragen je ihre `*.sha256`-Datei.

**Warum zwei Dateien und nicht eine erweiterte.** Drei Gründe, jeder für sich tragend:
- Der Ortsdurchgang bliebe sonst nicht bei 3,3 s, sondern liefe über 13,27 Mio. Zeilen — eine
  Verschlechterung an einem Weg, der die Frage gar nicht stellt.
- Die beiden Durchgänge sammeln nach **verschiedenen** Kriterien: der Ortsdurchgang nach
  Kachelnachbarschaft, der Namensdurchgang nach Namensgleichheit.
- **Nur getrennt ist ein fehlender Sehenswürdigkeits-Auszug für sich feststellbar** — und daran
  hängt Punkt 3. In einer gemeinsamen Datei fiele mit der Plausibilisierung auch die Ortsauflösung
  aus, und der Ausfall wäre von „dieser Name existiert nicht" nicht zu unterscheiden.

**Keine Code-Liste innerhalb der Klassen.** Behalten werden die fünf Klassen vollständig, nicht eine
kuratierte Auswahl ihrer `featureCode`s. Eine solche Liste wäre eine Wertung darüber, was eine
Sehenswürdigkeit sein darf, die niemand pflegt und deren Lücken still Namen kosten.

### 2. Die Auskunft ist DREIWERTIG, und die drei Werte sind verschieden

Zu einem Namen gibt es genau drei Zustände, und sie dürfen nicht zusammenfallen (Muster
`place_lookups`, ADR 0102 Punkt 5):

1. **Nie nachgeschlagen** — keine Zeile. Keine Plausibilität feststellbar; der Name wird behandelt
   wie vor dieser Entscheidung.
2. **Nachgeschlagen, ohne Fund** — Zeile mit leerer Punktmenge. Der Name gilt als **nicht
   bestätigt** und wird verworfen.
3. **Nachgeschlagen, mit Punkten** — Zeile mit den Fundorten. Der Name gilt als bestätigt, wenn
   einer davon im Umkreis liegt.

Fällt (1) mit (2) zusammen, verwirft ein Lauf ohne Datensatz jeden Namen; fällt (2) mit (3)
zusammen, gibt es die Regel nicht. Abgelegt wird das **projektgebunden und lauf-unabhängig** in einer
neuen Tabelle `landmark_place_lookups` (Muster und Schlüsselbildung wie `place_lookups`), unter dem
normalisierten Namen — dieselbe Lebensdauer und dieselbe Begründung wie bei `landmark_names`:
Ein Sehenswürdigkeitsname benennt einen Ort, an dem diese Familie war.

### 3. Ohne Datensatz wird nichts verworfen

Fehlt der Sehenswürdigkeits-Auszug oder weicht er von seinem Hash ab, entsteht **kein** Durchgang,
**kein** Ersatzweg und **keine** Zeile — und damit bleibt jeder Name im Zustand (1) und unverändert
bestehen. Es wird eine laute Logzeile mit festem Grund-Token geschrieben, wie bei der
Ortsauflösung. Das ist der Zustand von heute, kein Fehlerzustand, und ausdrücklich **nicht** der
Zustand „nicht bestätigt".

**Das ist die Deckung des Übergangs:** Bis der Auszug auf einem Volume einmal erzeugt ist, verhält
sich das System exakt wie vorher. Ein Betriebszustand, in dem diese Entscheidung alle
Sehenswürdigkeitsnamen auf einmal entfernt, existiert nicht.

### 4. Die Prüfung sitzt am fertigen Event, hinter der Mehrheitsregel

Die Prüfung steht in `events.py::_built`, **nach** `_name_of` und **vor** `_place_of`. Der
Aufnahmeort ist eine Eigenschaft des Events (`_cells_of`), nicht des einzelnen Fotos, und das
Kriterium spricht vom Cluster — dieselbe Begründung wie in ADR 0120 Punkt 3, und dieselbe eine
Aufrufstelle, an der die Zusicherung `place_kind='landmark'` ⇒ `landmark_name` gesetzt nicht
auseinanderlaufen kann.

Die Ortsplausibilität ist eine **zusätzliche** Bedingung hinter einer unveränderten: Mehrheitsname,
`LANDMARK_MIN_SHARE` und `LANDMARK_CONFIDENCE_THRESHOLD` gelten wörtlich weiter, und es rückt
weiterhin **kein zweiter Kandidat nach**. Ein verworfener Name wird verworfen, nie ersetzt oder
gekürzt (Muster `_usable_name`).

**Hat das Event keine einzige gemessene Zelle, findet keine Prüfung statt** und der Name bleibt.
Geprüft wird ausschließlich gegen gemessene Zellen; eine über `infer_locations` übernommene
Koordinate erreicht diese Prüfung nie (ADR 0106 Punkt 4).

### 5. Die Grenze: `LANDMARK_PLAUSIBILITY_RADIUS_METERS = 50_000.0`

Bestätigt ist ein Name, wenn **mindestens ein** Fundort **mindestens einer** gemessenen Zelle des
Events näher liegt als diese Grenze. Eigene Konstante in `geonames.py`, nicht
`GEONAMES_MAX_DISTANCE_METERS`: Dort geht es darum, ab wann ein Ortsname keiner mehr ist, hier
darum, ab wann eine Entfernung eine Verwechslung beweist. Beide müssen sich unabhängig bewegen
können.

**Der Name muss im Datensatz stehen** — als gefalteter Schlüssel (Kleinschreibung, getrennte
Diakritika, Trennzeichen zu Leerzeichen), gegen `name` und gegen jedes Element von
`alternatenames`. Einen Ähnlichkeitsrückfall gibt es hier nicht: Die Ähnlichkeitsstufe bleibt das
Namensregister (ADR 0107 Punkt 4), und ein Name ohne Eintrag fällt unter Zustand (2), nicht unter
einen zweiten Versuch. Sonst zöge die Prüfung genau die Namen zusammen, gegen die das Register
gebaut ist.

**Großzügig, und mit Absicht in diese Richtung schief.** Ein Berg, eine Skyline oder ein Viadukt
wird aus Entfernung fotografiert, und der Fehler, gegen den diese Entscheidung steht, misst
hunderte Kilometer. Der teure Fehler ist der verworfene richtige Name, nicht der durchgelassene
falsche in 40 km Entfernung. Dokumentiert-unkalibriert, gleiche Klasse wie
`LANDMARK_CONFIDENCE_THRESHOLD`: Es gibt keinen Korpus im Repository, gegen den sie kalibriert
werden könnte. Erkennungsweg ist die Abnahme an einer echten Reise.

## Konsequenzen

- **Rund ein Zehntel der richtig erkannten Namen geht verloren** — 5 von 50 in der Messung sind im
  Gazetteer nicht auffindbar und fallen damit unter Zustand (2). Das ist kein Nebeneffekt, sondern
  der ausgesprochene Preis des Akzeptanzkriteriums „im Zweifel kein Name". Die betroffenen Cluster
  tragen danach ihren Ortsnamen, nie gar nichts (ADR 0120 Punkt 2).
- **Ein neues Volume-Artefakt und ein erneuter Handgriff je Volume.** Derselbe Bezug erzeugt zwei
  Ausgabedateien; das Volume trägt statt 69 MB rund 273 MB. `docs/setup.md` zieht im selben Pull
  Request nach.
- **Ein zusätzlicher Dateidurchgang je Lauf, nur bei offenen Namen.** Gemessen auf der Rohdatei mit
  vollem `alternatenames`-Zerlegen: 43 s für 13,47 Mio. Zeilen — für den Auszug dieselbe
  Größenordnung. Er läuft einmal je Lauf, nach der Landmark-Phase, und nur, wenn ein Name noch
  nicht nachgeschlagen ist; ein zweiter Lauf über dasselbe Projekt löst keinen aus. Ein billiger
  Vorfilter vor der vollen Namensfaltung ist **zulässig, aber entbehrlich**, solange die
  Größenordnung Sekunden bleibt und nicht Minuten — die Umsetzung faltet deshalb jeden Namen ohne
  Vorauswahl. Er wird nötig, sobald der Durchgang die Sekunden-Größenordnung verlässt; dann tritt
  mit ihm auch sein Pflichtfall in Kraft („vom Vorfilter verworfen, von der Normalisierung
  gefunden", siehe `specs/architecture/0002-testkonzept.md`).
- **Der Request-Pfad bleibt unberührt.** `rebuild_run_grouping` liest die abgelegte Auskunft und
  schlägt nichts nach; ein dort unbekannter Name bleibt im Zustand (1) und behält seinen Namen.
  Keine Datei, kein Modell, kein Netz in einem Request (Spec 0469 S10).
- **Neue Tabelle, also Migration.** Kein bestehendes Feld ändert seine Bedeutung, kein Backfill:
  bestehende Läufe behalten ihre Namen, bis sie neu berechnet werden.
- **Die Logging-Auflage gilt unverändert weiter.** Weder ein Sehenswürdigkeitsname noch eine
  Koordinate noch eine Entfernung gehört je in eine Logzeile — die Nachvollziehbarkeit eines
  verworfenen Namens entsteht über die abgelegte Zeile, nie über ein Log und nicht über die API.
- Das Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`, Owner `security-engineer`)
  braucht die Fortschreibung um die neue Tabelle als weitere projektgebundene Ortsspur und um den
  Restrisiko-Eintrag zu ADR 0106 Punkt 5, der damit erledigt ist. `docs/architecture.md` zieht im
  selben Pull Request nach. Keine neue Abhängigkeit und keine neue Betriebseinstellung: der zweite
  Auszug liegt als Geschwisterdatei neben dem konfigurierten `place_dataset_path`.
